"""Crash-safe V3.1B raw-latent storage and deterministic auto-resume."""

from __future__ import annotations

import contextvars
import copy
import hashlib
import functools
import inspect
import json
import marshal
import os
import re
import shutil
import time
import socket
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

import torch
from safetensors import safe_open
from safetensors.torch import save_file

from .branch_provenance import (
    BRANCH_PROVENANCE_VERSION,
    TAKE_ACTION_AUTOMATIC,
    TAKE_ACTION_CONTINUE,
    TAKE_ACTION_OPTIONS,
    TAKE_ACTION_USE,
    BranchProvenanceError,
    active_revision_map,
    make_group_revision,
    physical_groups,
    resolve_chain,
)
from .constants import CONTINUUM_ACTUAL_PREFIX_STEPS, continuity_storage_mode
from .v2.session import make_session, validate_chunk_entry
from .v3.review_control import (
    GENERATION_MODE_REVIEW,
    REVIEW_ACTION_CONTINUE,
    REVIEW_ACTION_REGENERATE_CURRENT,
    REVISION_STATUS_COMPLETE,
    REVISION_STATUS_IN_PROGRESS,
    REVISION_STATUS_INTERRUPTED,
    REVISION_STATUS_REVIEW_READY,
    RUN_STORAGE_SAVE_AUTO_RESUME,
    ReviewControlError,
    ReviewUnit,
    make_review_pause_metadata,
    resolve_review_execution,
    resolve_take_execution,
    validate_review_prefix_metadata,
)
from .v3.planning_types import PrefixFacts
from .v3.reference_storage_contract import (
    REFERENCE_ROUTING_CONTRACT_VERSION,
    ReferenceStoragePlan,
    ReferenceStorageContractError,
    session_routing_settings,
    validate_reference_group_contracts,
)


RUN_STORAGE_SCHEMA_VERSION = 3
RUN_STORAGE_READABLE_SCHEMA_VERSIONS = (2, RUN_STORAGE_SCHEMA_VERSION)
from .conditioning import (
    CONDITIONING_MODES,
    conditioning_mode_from_presence,
    conditioning_mode_uses_video_vae,
)


SAMPLING_CONTRACT_VERSION = 6
SAMPLING_READABLE_CONTRACT_VERSIONS = {5, 6}
RUNTIME_SIGNATURE_VERSION = 1
_OBSERVATION_MAX_ITEMS = 4096
REVIEW_CONTROL_VERSION = 1
RUN_STORAGE_OFF = "Off"
RUN_STORAGE_AUTO = "Save + Auto Resume"
RUN_STORAGE_OPTIONS = (RUN_STORAGE_OFF, RUN_STORAGE_AUTO)

_ACTIVE: contextvars.ContextVar["RunStorageController | None"] = contextvars.ContextVar(
    "h3_continuum_run_storage", default=None
)
_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
_ADDRESS = re.compile(r"0x[0-9a-fA-F]+")


class RunStorageError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ValidatedPrefix:
    """One immutable Run Storage prefix after manifest/raw/group validation."""

    entries: tuple[dict[str, Any], ...]
    records: tuple[dict[str, Any], ...]
    manifest: Mapping[str, Any] | None
    revision_id: str | None
    status: str | None
    review_unit: ReviewUnit | None
    effective_nonce: int
    branch_regenerate_from: int
    physical_group_boundaries: tuple[tuple[int, int], ...]
    configured_chunks: int

    def to_planning_facts(self) -> PrefixFacts:
        return PrefixFacts(
            accepted_chunks=len(self.entries),
            configured_chunks=int(self.configured_chunks),
            revision_id=self.revision_id,
            status=self.status,
            review_unit=self.review_unit,
            effective_nonce=int(self.effective_nonce),
            branch_regenerate_from=int(self.branch_regenerate_from),
            physical_group_boundaries=self.physical_group_boundaries,
        )


@dataclass(frozen=True, slots=True)
class EmptyValidatedPrefix:
    """The absence of a Run Storage prefix, not of other continuation sources."""

    configured_chunks: int
    entries: tuple = ()
    records: tuple = ()
    manifest: None = None
    revision_id: None = None
    status: None = None
    review_unit: None = None
    effective_nonce: int = 0
    branch_regenerate_from: int = 0
    physical_group_boundaries: tuple = ()

    def to_planning_facts(self) -> PrefixFacts:
        return PrefixFacts(
            accepted_chunks=0,
            configured_chunks=int(self.configured_chunks),
            revision_id=None,
            status=None,
            review_unit=None,
            effective_nonce=0,
            branch_regenerate_from=0,
            physical_group_boundaries=(),
        )


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _review_contract_mismatches(stored: dict, current: dict) -> list[str]:
    """Diagnostic hashes only; never relax identity or print payload values."""
    result: list[str] = []

    def compare(left: Any, right: Any, path: str) -> None:
        if _hash(left) == _hash(right):
            return
        # Split known contract containers, but not arbitrary wrapper/prompt data.
        containers = {
            "global", "global.model", "global.model.runtime",
            "global.clip", "global.clip.runtime", "global.video_vae",
            "global.video_vae.runtime",
        }
        if path in containers and isinstance(left, dict) and isinstance(right, dict):
            for key in sorted(left.keys() | right.keys()):
                if key not in left or key not in right:
                    result.append(f"{path}.{key}: field missing on one side")
                else:
                    compare(left[key], right[key], f"{path}.{key}")
            return
        result.append(f"{path}: saved={_hash(left)[:16]} current={_hash(right)[:16]}")

    # Match the inputs to _nonce_lineage_hash, not derived nonce/branch fields.
    for key in (
        "global", "chunk_count", "prompt_mode", "prompt_hashes",
        "last_frame_hash", "timeline_video_chunk_contracts",
    ):
        compare(stored.get(key), current.get(key), key)
    return result


def _canonical_optional_hash(value: Any) -> str:
    """Normalize legacy absent-value spellings without changing real hashes."""

    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"", "none", "null"} else text


def sanitize_run_name(value: str) -> str:
    name = str(value)
    if not name or name != name.strip() or len(name) > 96:
        raise RunStorageError("Run Name must be 1-96 characters without surrounding spaces")
    if any(ord(char) < 32 or char in '<>:"/\\|?*' for char in name):
        raise RunStorageError("Run Name contains a reserved path character")
    if name.endswith((".", " ")) or name in {".", ".."}:
        raise RunStorageError("Run Name must not be a relative path or end with dot/space")
    if name.split(".", 1)[0].upper() in _RESERVED:
        raise RunStorageError(f"Run Name {name!r} is reserved by Windows")
    return name


def resolve_run_storage_name(
    *, project_id: str, legacy_run_name: str = "", automatic_key: str = ""
) -> str:
    """Resolve a stable storage folder while preserving old Run Name workflows."""
    legacy = str(legacy_run_name)
    if legacy:
        return sanitize_run_name(legacy)
    raw_project_id = str(project_id).strip()
    if not raw_project_id:
        key = str(automatic_key).strip()
        if not key:
            raise RunStorageError(
                "Automatic Resume ID is unavailable; enter a Run Name for this workflow"
            )
        digest = hashlib.sha256(
            f"H3ContinuumSamplerProduction:{key}".encode("utf-8")
        ).hexdigest()[:24]
        return f"run_auto_{digest}"
    try:
        parsed = uuid.UUID(raw_project_id)
    except (ValueError, AttributeError, TypeError) as exc:
        raise RunStorageError(
            "Automatic Project ID is missing or invalid; reload ComfyUI and the workflow"
        ) from exc
    if parsed.int == 0:
        raise RunStorageError("Automatic Project ID must not be the nil UUID")
    return f"run_{parsed.hex}"


def automatic_project_key(prompt: Any, unique_id: Any) -> str:
    """Build a stable key from sampler identity and graph topology only."""
    node_id = str(unique_id).strip()
    if not node_id:
        raise RunStorageError("Automatic Resume ID requires the sampler node ID")
    if not isinstance(prompt, dict):
        raise RunStorageError(
            "Automatic Resume ID requires the ComfyUI prompt graph; enter a Run Name"
        )
    def visit(current_id: str, stack: set[str]) -> dict[str, Any]:
        if current_id in stack:
            return {"node_id": current_id, "cycle": True}
        raw = prompt.get(current_id)
        if not isinstance(raw, dict):
            return {"node_id": current_id, "missing": True}
        links = []
        inputs = raw.get("inputs") or {}
        next_stack = set(stack)
        next_stack.add(current_id)
        if isinstance(inputs, dict):
            for name in sorted(inputs):
                if current_id == node_id and name == "reference_audio_vae":
                    audio_link = inputs.get("reference_audio_1")
                    if not (
                        isinstance(audio_link, (list, tuple))
                        and len(audio_link) == 2
                        and isinstance(audio_link[0], (str, int))
                        and isinstance(audio_link[1], int)
                        and str(audio_link[0]) in prompt
                    ):
                        continue
                if current_id == node_id and name == "audio_vae":
                    audio_link = inputs.get("driving_audio")
                    if not (
                        isinstance(audio_link, (list, tuple))
                        and len(audio_link) == 2
                        and isinstance(audio_link[0], (str, int))
                        and isinstance(audio_link[1], int)
                        and str(audio_link[0]) in prompt
                    ):
                        continue
                value = inputs[name]
                if (
                    isinstance(value, (list, tuple))
                    and len(value) == 2
                    and isinstance(value[0], (str, int))
                    and isinstance(value[1], int)
                    and str(value[0]) in prompt
                ):
                    child_id = str(value[0])
                    links.append(
                        {
                            "input": str(name),
                            "output": int(value[1]),
                            "node": visit(child_id, next_stack),
                        }
                    )
        return {
            "node_id": current_id,
            "class_type": str(raw.get("class_type", "")),
            "links": links,
        }
    return _hash({"sampler_node_id": node_id, "topology": visit(node_id, set())})


def _output_root() -> Path:
    try:
        import folder_paths

        return Path(folder_paths.get_output_directory())
    except Exception:
        return Path.cwd() / "output"


def _fsync_file(path: Path) -> None:
    # Windows requires a writable descriptor for fsync(). The file contents
    # are already complete at this point; opening r+b does not modify them.
    with path.open("r+b") as handle:
        os.fsync(handle.fileno())


def _fsync_dir(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


_WINDOWS_REPLACE_RETRY_SECONDS = (0.02, 0.05, 0.10, 0.20, 0.40)
_WINDOWS_REPLACE_RETRY_WINERRORS = frozenset({5, 32})


def _replace_json_atomically(temporary: Path, destination: Path) -> None:
    """Publish a complete JSON file without weakening replace atomicity.

    Windows virus scanners and indexers can briefly hold either side of an
    otherwise complete replacement. Retry only those transient Windows errors;
    all other failures retain the old destination and fail with diagnostics.
    """

    attempts = 0
    for delay in (*_WINDOWS_REPLACE_RETRY_SECONDS, None):
        try:
            os.replace(temporary, destination)
            return
        except PermissionError as exc:
            winerror = getattr(exc, "winerror", None)
            error_code = winerror if winerror is not None else exc.errno
            transient = (
                error_code in _WINDOWS_REPLACE_RETRY_WINERRORS
                and delay is not None
            )
            if transient:
                attempts += 1
                time.sleep(delay)
                continue
            source_exists = temporary.exists()
            destination_exists = destination.exists()
            readonly = False
            if destination_exists:
                try:
                    readonly = not bool(destination.stat().st_mode & 0o200)
                except OSError:
                    readonly = False
            raise RunStorageError(
                "Run Storage atomic manifest replace failed "
                f"after {attempts + 1} attempt(s): src={temporary}; "
                f"dst={destination}; src_exists={source_exists}; "
                f"dst_exists={destination_exists}; dst_readonly={readonly}; "
                f"parent={destination.parent}; winerror={winerror}; "
                f"errno={exc.errno}"
            ) from exc


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        _replace_json_atomically(temporary, path)
        _fsync_dir(path.parent)
    finally:
        if temporary.exists():
            temporary.unlink()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RunStorageError(f"{path.name} must contain a JSON object")
    return value


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _qualified(value: Any) -> str:
    if value is None:
        return "none"
    target = value if isinstance(value, type) or callable(value) else type(value)
    module = getattr(target, "__module__", "")
    name = getattr(target, "__qualname__", getattr(target, "__name__", type(target).__name__))
    return f"{module}.{name}"


def _tensor_probe(tensor: torch.Tensor, *, dtype: torch.dtype | None = None) -> dict[str, Any]:
    flat = tensor.detach().reshape(-1)
    count = int(flat.numel())
    positions = sorted({0, count // 4, count // 2, 3 * count // 4, count - 1}) if count else []
    if positions:
        index = torch.tensor(positions, device=flat.device)
        values = flat[index]
        if dtype is not None and dtype != tensor.dtype:
            values = values.to(dtype=dtype)
        sample = values.contiguous().cpu().view(torch.uint8).numpy().tobytes()
    else:
        sample = b""
    return {
        "shape": list(tensor.shape),
        "dtype": str(dtype if dtype is not None else tensor.dtype),
        "sample_sha256": hashlib.sha256(sample).hexdigest(),
    }


def _tensor_exact(tensor: torch.Tensor) -> dict[str, Any]:
    value = tensor.detach().contiguous().cpu()
    raw = value.view(torch.uint8).numpy().tobytes()
    return {
        "shape": list(value.shape),
        "dtype": str(value.dtype),
        "exact_sha256": hashlib.sha256(raw).hexdigest(),
    }


def _observe(value: Any, *, depth: int = 0) -> tuple[Any, bool]:
    try:
        return _observe_value(value, depth=depth)
    except Exception as exc:
        return {"type": _qualified(value), "observation_error": type(exc).__name__}, False


def _observe_value(value: Any, *, depth: int = 0) -> tuple[Any, bool]:
    if depth > 10:
        return {"type": _qualified(value), "truncated": True}, False
    if value is None or isinstance(value, (bool, int, float, str)):
        return value, True
    if isinstance(value, Path):
        return str(value), True
    if torch.is_tensor(value):
        try:
            return {"tensor": _tensor_probe(value)}, True
        except Exception:
            return {"tensor_type": _qualified(value)}, False
    if isinstance(value, dict):
        if len(value) > _OBSERVATION_MAX_ITEMS:
            return {"type": _qualified(value), "items": len(value), "truncated": True}, False
        result: dict[str, Any] = {}
        safe = True
        for key in sorted(value, key=lambda item: str(item)):
            observed, item_safe = _observe(value[key], depth=depth + 1)
            result[str(key)] = observed
            safe = safe and item_safe
        return result, safe
    if isinstance(value, (list, tuple)):
        if len(value) > _OBSERVATION_MAX_ITEMS:
            return {"type": _qualified(value), "items": len(value), "truncated": True}, False
        result = []
        safe = True
        for item in value:
            observed, item_safe = _observe(item, depth=depth + 1)
            result.append(observed)
            safe = safe and item_safe
        return result, safe
    if isinstance(value, (set, frozenset)):
        if len(value) > _OBSERVATION_MAX_ITEMS:
            return {"type": _qualified(value), "items": len(value), "truncated": True}, False
        # Set repr order varies with PYTHONHASHSEED; keep every item and its type.
        items = [_observe(item, depth=depth + 1) for item in value]
        return {
            "type": _qualified(value),
            "items": sorted((item for item, _ in items), key=_canonical),
        }, all(safe for _, safe in items)
    if isinstance(value, torch.nn.Module):
        # Never traverse every parameter through a wrapper's bound owner.
        return {"type": _qualified(value), "module_state_unobserved": True}, False
    if callable(value):
        if isinstance(value, functools.partial):
            observed, safe = _observe({
                "function": value.func, "args": value.args,
                "keywords": value.keywords, "attributes": vars(value),
            }, depth=depth + 1)
            return {"partial": observed}, safe
        code = getattr(value, "__code__", None)
        descriptor: dict[str, Any] = {"callable": _qualified(value)}
        safe = True
        if code is not None:
            descriptor["code_sha256"] = hashlib.sha256(
                marshal.dumps(code)
            ).hexdigest()
            defaults, defaults_safe = _observe(getattr(value, "__defaults__", None), depth=depth + 1)
            kwdefaults, kw_safe = _observe(getattr(value, "__kwdefaults__", None), depth=depth + 1)
            closure_values = tuple(cell.cell_contents for cell in (getattr(value, "__closure__", None) or ()))
            closure, closure_safe = _observe(closure_values, depth=depth + 1)
            descriptor.update(defaults=defaults, kwdefaults=kwdefaults, closure=closure)
            safe = defaults_safe and kw_safe and closure_safe
            if inspect.ismethod(value):
                owner, owner_safe = _observe(value.__self__, depth=depth + 1)
                descriptor["bound_self"] = owner
                safe = safe and owner_safe
        elif hasattr(value, "__dict__"):
            attributes, attributes_safe = _observe(vars(value), depth=depth + 1)
            descriptor["attributes"] = attributes
            # Callable instances need both state and executable implementation.
            # An empty __dict__ is not evidence for an opaque extension wrapper.
            implementation = getattr(type(value), "__call__", None)
            if inspect.isfunction(implementation):
                call, call_safe = _observe(implementation, depth=depth + 1)
                descriptor["implementation"] = call
                slots = any(getattr(cls, "__slots__", ()) for cls in type(value).__mro__)
                safe = attributes_safe and call_safe and bool(vars(value)) and not slots
            else:
                safe = False
        else:
            safe = False
        return descriptor, safe
    if hasattr(value, "__dict__"):
        attributes, safe = _observe(vars(value), depth=depth + 1)
        return {"type": _qualified(value), "attributes": attributes}, safe
    rendered = _ADDRESS.sub("0x...", repr(value))
    return {"type": _qualified(value), "repr": rendered[:256]}, False


def _model_signature(model: Any, legacy_fingerprint: str) -> tuple[dict[str, Any], bool]:
    base = getattr(model, "model", None)
    inner = getattr(base, "diffusion_model", None)
    wrappers, wrappers_safe = _observe(getattr(model, "wrappers", {}) or {})
    patches, patches_safe = _observe(getattr(model, "patches", {}) or {})
    options = getattr(model, "model_options", {}) or {}
    if not isinstance(options, dict):
        return {"model_patcher": _qualified(model), "error": "model_options is not a mapping"}, False
    observed_options = dict(options)
    transformer = dict(observed_options.get("transformer_options", {}) or {})
    transformer.pop("h3_continuum_join_context", None)
    if "transformer_options" in observed_options:
        observed_options["transformer_options"] = transformer
    observed_options, options_safe = _observe(observed_options)
    weights: list[dict[str, Any]] = []
    weights_safe = True
    try:
        parameters = list(inner.named_parameters()) if inner is not None else []
        for position in sorted({0, len(parameters) // 2, len(parameters) - 1}) if parameters else []:
            name, parameter = parameters[position]
            weights.append({"name": str(name), **_tensor_probe(parameter)})
    except Exception:
        weights_safe = False
    descriptor = {
        "legacy_fingerprint": str(legacy_fingerprint),
        "model_patcher": _qualified(model),
        "base": _qualified(base),
        "inner": _qualified(inner),
        "dtype": str(getattr(model, "model_dtype", lambda: "unknown")()),
        "model_size": int(getattr(model, "model_size", lambda: 0)() or 0),
        "wrappers": wrappers,
        "model_options": observed_options,
        "patches": patches,
        "weight_probe": weights,
        "runtime_observation": {
            "wrappers_complete": bool(wrappers_safe),
            "patches_complete": bool(patches_safe),
            "model_options_complete": bool(options_safe),
        },
    }
    return descriptor, weights_safe and bool(weights) and wrappers_safe and patches_safe and options_safe


def _sampler_signature(sampler: Any) -> tuple[dict[str, Any], bool]:
    function = getattr(sampler, "sampler_function", None)
    observed, safe = _observe({
        "function": function,
        "extra_options": getattr(sampler, "extra_options", {}) or {},
        "inpaint_options": getattr(sampler, "inpaint_options", {}) or {},
    })
    return {
        "type": _qualified(sampler),
        "options": observed,
    }, function is not None and safe


def _signature_observation(observer, *args, **kwargs):
    try:
        return observer(*args, **kwargs)
    except Exception as exc:
        return {"observation_error": type(exc).__name__}, False


def _reusable_sampling_contract(contract: dict[str, Any], *, resume_safe: bool = True) -> bool:
    global_contract = contract.get("global") or {}
    return bool(
        resume_safe
        and global_contract.get("sampling_contract_version") == SAMPLING_CONTRACT_VERSION
        and global_contract.get("runtime_signature_version") == RUNTIME_SIGNATURE_VERSION
        and contract.get("reuse_policy") != "disabled_unobservable_contract"
    )


def _reusable_manifest(manifest: dict[str, Any]) -> bool:
    return bool(
        manifest.get("sampling_contract_version") == SAMPLING_CONTRACT_VERSION
        and manifest.get("resume_safe") is True
        and _reusable_sampling_contract(manifest.get("contract") or {})
    )


def _module_parameter_dtype(module: Any, name: str, parameter: torch.Tensor) -> torch.dtype:
    """Observe ordinary weights at Core's declared load dtype without casting them."""
    # Quantized/custom Tensor representations retain their original fingerprint.
    if type(parameter) not in (torch.Tensor, torch.nn.Parameter):
        return parameter.dtype
    owner_name, _, local_name = name.rpartition(".")
    if owner_name and not hasattr(module, "get_submodule"):
        return parameter.dtype
    owner = module.get_submodule(owner_name) if owner_name else module
    dtype = getattr(owner, local_name + "_comfy_model_dtype", None)
    if isinstance(dtype, torch.dtype) and dtype.is_floating_point and parameter.is_floating_point():
        return dtype
    return parameter.dtype


def _module_signature(module: Any) -> tuple[dict[str, Any], bool]:
    descriptor: dict[str, Any] = {"type": _qualified(module)}
    if module is None or not hasattr(module, "named_parameters"):
        descriptor["error"] = "named_parameters unavailable"
        return descriptor, False
    try:
        parameters = list(module.named_parameters())
        dtypes = {
            name: _module_parameter_dtype(module, name, parameter)
            for name, parameter in parameters
        }
    except Exception as exc:
        descriptor["error"] = f"named_parameters failed: {type(exc).__name__}"
        return descriptor, False
    layout = [
        {
            "name": str(name),
            "shape": list(parameter.shape),
            "dtype": str(dtypes[name]),
        }
        for name, parameter in parameters
    ]
    descriptor.update(
        tensor_count=len(parameters),
        parameter_count=sum(int(parameter.numel()) for _, parameter in parameters),
        parameter_layout_sha256=_hash(layout),
    )
    probes = []
    probes_safe = bool(parameters)
    for position in sorted({0, len(parameters) // 2, len(parameters) - 1}) if parameters else []:
        name, parameter = parameters[position]
        try:
            probes.append({"name": str(name), **_tensor_probe(parameter, dtype=dtypes[name])})
        except Exception as exc:
            probes.append({"name": str(name), "error": type(exc).__name__})
            probes_safe = False
    descriptor["weight_probe"] = probes
    return descriptor, probes_safe


def _patcher_signature(patcher: Any) -> tuple[dict[str, Any], bool]:
    if patcher is None:
        return {"type": "missing"}, False
    state, safe = _observe({
        "wrappers": getattr(patcher, "wrappers", {}) or {},
        "patches": getattr(patcher, "patches", {}) or {},
        "object_patches": getattr(patcher, "object_patches", {}) or {},
        "model_options": getattr(patcher, "model_options", {}) or {},
    })
    return {
        "type": _qualified(patcher),
        "model_type": _qualified(getattr(patcher, "model", None)),
        "state": state,
    }, safe


def _clip_signature(clip: Any) -> tuple[dict[str, Any], bool]:
    cond_stage = getattr(clip, "cond_stage_model", None)
    tokenizer = getattr(clip, "tokenizer", None)
    tokenizer_wrapper = getattr(tokenizer, "qwen3vl_32b", None)
    tokenizer_core = getattr(tokenizer_wrapper, "tokenizer", None)
    module_value, module_safe = _module_signature(cond_stage)
    patcher_value, patcher_safe = _patcher_signature(getattr(clip, "patcher", None))
    options, options_safe = _observe({
        "tokenizer_options": getattr(clip, "tokenizer_options", {}) or {},
        "layer_idx": getattr(clip, "layer_idx", None),
        "use_clip_schedule": bool(getattr(clip, "use_clip_schedule", False)),
    })
    tokenizer_config = {
        "wrapper_type": _qualified(tokenizer),
        "model_wrapper_type": _qualified(tokenizer_wrapper),
        "core_type": _qualified(tokenizer_core),
    }
    for name in (
        "name_or_path", "vocab_size", "model_max_length", "padding_side",
        "truncation_side", "bos_token_id", "eos_token_id", "pad_token_id",
    ):
        value = getattr(tokenizer_core, name, None)
        if value is None or isinstance(value, (bool, int, float, str)):
            tokenizer_config[name] = value
    tokenizer_safe = tokenizer is not None and tokenizer_wrapper is not None and tokenizer_core is not None
    descriptor = {
        "wrapper_type": _qualified(clip),
        "conditioner": module_value,
        "patcher": patcher_value,
        "tokenizer": tokenizer_config,
        "options": options,
        "runtime_observation": {
            "patcher_complete": bool(patcher_safe),
            "options_complete": bool(options_safe),
        },
    }
    return descriptor, module_safe and tokenizer_safe


def _video_vae_signature(video_vae: Any, *, required: bool) -> tuple[dict[str, Any], bool]:
    if not required:
        return {"required": False}, True
    first_stage = getattr(video_vae, "first_stage_model", None)
    module_value, module_safe = _module_signature(first_stage)
    patcher_value, patcher_safe = _patcher_signature(getattr(video_vae, "patcher", None))
    config = {
        "required": True,
        "wrapper_type": _qualified(video_vae),
        "first_stage": module_value,
        "patcher": patcher_value,
        "vae_dtype": str(getattr(video_vae, "vae_dtype", "unknown")),
        "latent_channels": getattr(video_vae, "latent_channels", None),
        "downscale_ratio": getattr(video_vae, "downscale_ratio", None),
        "upscale_ratio": getattr(video_vae, "upscale_ratio", None),
        "chunked_io": bool(getattr(first_stage, "comfy_has_chunked_io", False)),
    }
    observed, config_safe = _observe(config)
    observed["runtime_observation"] = {
        "patcher_complete": bool(patcher_safe),
        "config_complete": bool(config_safe),
    }
    return observed, module_safe


def _audio_vae_signature(audio_vae: Any) -> tuple[dict[str, Any], bool]:
    first_stage = getattr(audio_vae, "first_stage_model", None)
    module_value, module_safe = _module_signature(first_stage)
    patcher_value, patcher_safe = _patcher_signature(getattr(audio_vae, "patcher", None))
    config = {
        "wrapper_type": _qualified(audio_vae),
        "first_stage": module_value,
        "patcher": patcher_value,
        "vae_dtype": str(getattr(audio_vae, "vae_dtype", "unknown")),
        "audio_sample_rate": getattr(audio_vae, "audio_sample_rate", 32000),
        "latent_channels": getattr(audio_vae, "latent_channels", None),
    }
    observed, config_safe = _observe(config)
    observed["runtime_observation"] = {
        "patcher_complete": bool(patcher_safe),
        "config_complete": bool(config_safe),
    }
    return observed, module_safe


def _apply_nonce_contract(
    contract: dict[str, Any], *, requested_nonce: int, effective_nonce: int,
) -> dict[str, Any]:
    result = dict(contract)
    result["last_frame_hash"] = _canonical_optional_hash(
        result.get("last_frame_hash")
    )
    boundary = int(result["reroll_from_chunk"])
    if boundary <= 0:
        mode = "inactive"
        requested_nonce = 0
        effective_nonce = 0
    else:
        mode = "explicit" if int(requested_nonce) >= 1 else "auto"
    global_hash = _hash(result["global"])
    chunk_contracts = []
    chunk_hashes = []
    routed_groups = result.get("reference_group_contracts")
    routed_by_chunk = {}
    if routed_groups is not None:
        for group_record in routed_groups:
            for chunk in group_record["descriptor"]["logical_chunks"]:
                routed_by_chunk[int(chunk)] = group_record["sha256"]
    for position, prompt_hash in enumerate(result["prompt_hashes"]):
        number = position + 1
        affected = boundary > 0 and number >= boundary
        chunk_contract = {
            "global_hash": global_hash,
            "chunk_number": number,
            "prompt_hash": str(prompt_hash),
            "reroll_boundary": boundary if affected else 0,
            "effective_reroll_nonce": int(effective_nonce) if affected else 0,
            "last_frame_hash": str(result["last_frame_hash"]) if number == int(result["chunk_count"]) else "",
        }
        if routed_groups is not None:
            chunk_contract["physical_group_reference_sha256"] = routed_by_chunk[number]
        timeline_chunks = result.get("timeline_video_chunk_contracts") or []
        if position < len(timeline_chunks):
            chunk_contract["timeline_video"] = dict(timeline_chunks[position])
        chunk_contracts.append(chunk_contract)
        chunk_hashes.append(_hash(chunk_contract))
    result.update(
        effective_reroll_nonce=int(effective_nonce),
        chunk_contracts=chunk_contracts,
        chunk_contract_hashes=chunk_hashes,
        nonce_lifecycle={
            "mode": mode,
            "requested_nonce": int(requested_nonce),
            "effective_nonce": int(effective_nonce),
            "lineage_sha256": str(result["nonce_lineage_sha256"]),
            "request_sha256": str(result["nonce_request_sha256"]),
        },
    )
    return result


def _nonce_lineage_hash(
    contract: dict[str, Any],
    *,
    timeline_video_chunk_contracts: list[dict[str, Any]] | None = None,
) -> str:
    """Recompute the nonce-independent compatible sampling lineage."""

    identity = {
        "global_hash": _hash(contract["global"]),
        "chunk_count": int(contract["chunk_count"]),
        "prompt_mode": str(contract["prompt_mode"]),
        "prompt_hashes": [str(value) for value in contract["prompt_hashes"]],
        "last_frame_hash": str(contract.get("last_frame_hash", "")),
        "timeline_video_chunk_contracts": list(
            timeline_video_chunk_contracts
            if timeline_video_chunk_contracts is not None
            else contract.get("timeline_video_chunk_contracts") or []
        ),
    }
    if "reference_group_contracts" in contract:
        identity["reference_group_hashes"] = [
            record["sha256"] for record in contract["reference_group_contracts"]
        ]
    return _hash(identity)


def _apply_reroll_branch_contract(
    contract: dict[str, Any],
    *,
    boundary: int,
    requested_nonce: int,
    effective_nonce: int,
) -> dict[str, Any]:
    """Apply the existing reroll/seed contract to a resolved review branch."""

    result = dict(contract)
    result["reroll_from_chunk"] = int(boundary)
    result["nonce_request_sha256"] = _hash({
        "lineage_sha256": str(result["nonce_lineage_sha256"]),
        "reroll_from_chunk": int(boundary),
    })
    return _apply_nonce_contract(
        result,
        requested_nonce=int(requested_nonce),
        effective_nonce=int(effective_nonce),
    )


def _legacy_absent_last_frame_compatible(
    *,
    stored_contract: dict[str, Any],
    current_contract: dict[str, Any],
    position: int,
    stored_hash: str,
    current_hash: str,
) -> bool:
    """Accept only the V3.6.1 ``none`` versus ``""`` Last Frame mismatch."""

    if not isinstance(stored_contract, dict) or not isinstance(current_contract, dict):
        return False
    if _canonical_optional_hash(stored_contract.get("last_frame_hash")):
        return False
    if _canonical_optional_hash(current_contract.get("last_frame_hash")):
        return False
    stored_chunks = stored_contract.get("chunk_contracts") or []
    current_chunks = current_contract.get("chunk_contracts") or []
    if position >= len(stored_chunks) or position >= len(current_chunks):
        return False
    stored_chunk = stored_chunks[position]
    current_chunk = current_chunks[position]
    if not isinstance(stored_chunk, dict) or not isinstance(current_chunk, dict):
        return False
    if _hash(stored_chunk) != str(stored_hash):
        return False
    if _hash(current_chunk) != str(current_hash):
        return False
    stored_normalized = dict(stored_chunk)
    current_normalized = dict(current_chunk)
    stored_normalized["last_frame_hash"] = _canonical_optional_hash(
        stored_normalized.get("last_frame_hash")
    )
    current_normalized["last_frame_hash"] = _canonical_optional_hash(
        current_normalized.get("last_frame_hash")
    )
    return stored_normalized == current_normalized


def build_sampling_contract(
    *, model: Any, model_fingerprint_value: str, clip: Any, video_vae: Any,
    sampler: Any,
    sigmas: torch.Tensor, prompt_plan: dict[str, Any], width: int,
    height: int, chunk_seconds: float, continuity: str,
    audio_continuity: bool, base_seed: int, reroll_from_chunk: int,
    reroll_nonce: int, first_frame_hash: str, last_frame_hash: str,
    strict_compatibility: bool, reference_contract: dict[str, Any] | None = None,
    conditioning_mode: str | None = None,
    upstream_graph_contract: dict[str, Any] | None = None,
    upstream_graph_safe: bool | None = None,
    upstream_graph_reasons: list[str] | None = None,
    reference_audio_contract: dict[str, Any] | None = None,
    reference_audio_vae: Any = None,
    driving_audio_contract: dict[str, Any] | None = None,
    driving_audio_vae: Any = None,
    reference_video_contract: dict[str, Any] | None = None,
    timeline_video_contract: dict[str, Any] | None = None,
    guide_contract: dict[str, Any] | None = None,
    execution_semantics: dict[str, Any] | None = None,
    reference_storage_plan: ReferenceStoragePlan | None = None,
) -> tuple[dict[str, Any], bool, list[str]]:
    if reference_storage_plan is not None and reference_contract is not None:
        raise RunStorageError("routed Reference plan cannot use legacy Reference contract")
    last_frame_hash = _canonical_optional_hash(last_frame_hash)
    model_value, model_safe = _signature_observation(_model_signature, model, model_fingerprint_value)
    clip_value, clip_safe = _clip_signature(clip)
    has_first = str(first_frame_hash).lower() not in {"", "none", "null"}
    has_last = str(last_frame_hash).lower() not in {"", "none", "null"}
    inferred_mode = conditioning_mode_from_presence(
        has_first=has_first,
        has_last=has_last,
        has_reference=reference_contract is not None,
    )
    conditioning_mode = inferred_mode if conditioning_mode is None else str(conditioning_mode)
    if conditioning_mode not in CONDITIONING_MODES:
        raise RunStorageError(f"unknown conditioning mode: {conditioning_mode!r}")
    if conditioning_mode != inferred_mode:
        raise RunStorageError(
            "conditioning mode does not match the connected image inputs: "
            f"declared={conditioning_mode}, inferred={inferred_mode}"
        )
    uses_video_vae = (
        reference_storage_plan is not None
        or
        conditioning_mode_uses_video_vae(conditioning_mode)
        or reference_video_contract is not None
        or timeline_video_contract is not None
        or guide_contract is not None
    )
    if uses_video_vae:
        video_vae_value, video_vae_safe = _video_vae_signature(
            video_vae, required=True
        )
    else:
        video_vae_value, video_vae_safe = None, True
    sampler_value, sampler_safe = _signature_observation(_sampler_signature, sampler)
    if reference_audio_contract is not None:
        audio_vae_value, audio_vae_safe = _audio_vae_signature(reference_audio_vae)
    else:
        audio_vae_value, audio_vae_safe = None, True
    if driving_audio_contract is not None:
        driving_audio_vae_value, driving_audio_vae_safe = _audio_vae_signature(
            driving_audio_vae
        )
    else:
        driving_audio_vae_value, driving_audio_vae_safe = None, True
    if not torch.is_tensor(sigmas) or sigmas.ndim != 1:
        raise RunStorageError("Run Storage requires a one-dimensional SIGMAS tensor")
    chunks = int(prompt_plan["chunks"])
    prompt_hashes = [str(value) for value in prompt_plan["hashes"]]
    boundary = int(reroll_from_chunk)
    graph_authoritative = upstream_graph_contract is not None
    if graph_authoritative:
        routes = upstream_graph_contract.get("routes", {})
        model_value = {
            "runtime": model_value,
            "graph_route": routes.get("model"),
        }
        clip_value = {
            "runtime": clip_value,
            "graph_route": routes.get("clip"),
        }
        if uses_video_vae:
            video_vae_value = {
                "runtime": video_vae_value,
                "graph_route": routes.get("video_vae"),
            }
        if reference_audio_contract is not None:
            audio_vae_value = {
                "runtime": audio_vae_value,
                "graph_route": routes.get("reference_audio_vae"),
            }
        if driving_audio_contract is not None:
            driving_audio_vae_value = {
                "runtime": driving_audio_vae_value,
                "graph_route": routes.get("audio_vae"),
            }
    global_contract = {
        "sampling_contract_version": SAMPLING_CONTRACT_VERSION,
        "runtime_signature_version": RUNTIME_SIGNATURE_VERSION,
        "conditioning_mode": conditioning_mode,
        "model": model_value,
        "clip": clip_value,
        "sampler": sampler_value,
        "sigmas": _tensor_exact(sigmas),
        "width": int(width), "height": int(height),
        "chunk_seconds": float(chunk_seconds),
        "continuity": continuity_storage_mode(continuity),
        "audio_continuity": bool(audio_continuity),
        "base_seed": int(base_seed),
        "strict_compatibility": bool(strict_compatibility),
        "continuum_interop_api": 1,
        "actual_prefix_steps": CONTINUUM_ACTUAL_PREFIX_STEPS,
    }
    if graph_authoritative:
        global_contract["upstream_graph"] = dict(upstream_graph_contract)
    if execution_semantics is not None:
        semantics = dict(execution_semantics)
        if reference_storage_plan is not None:
            semantics.pop("terminal_prompt_policy", None)
        global_contract["execution_semantics"] = semantics
    if reference_storage_plan is not None:
        global_contract["reference_routing_contract_version"] = REFERENCE_ROUTING_CONTRACT_VERSION
    if uses_video_vae:
        global_contract["video_vae"] = video_vae_value
    if has_first:
        global_contract["first_frame_hash"] = str(first_frame_hash)
    if reference_contract is not None:
        global_contract["reference"] = dict(reference_contract)
        if has_first or has_last:
            from .reference import HYBRID_PRESENTATION_VERSION

            picture_order: list[str] = []
            if has_first:
                picture_order.append("first_frame")
            if has_last:
                picture_order.append("last_frame")
            picture_order.extend(
                f"reference_image_{index}"
                for index in range(1, int(reference_contract.get("count", 0)) + 1)
            )
            global_contract["hybrid_qwen_presentation"] = {
                "version": HYBRID_PRESENTATION_VERSION,
                "picture_order": picture_order,
            }
    if reference_audio_contract is not None:
        global_contract["reference_audio"] = dict(reference_audio_contract)
        global_contract["reference_audio_vae"] = audio_vae_value
    if driving_audio_contract is not None:
        global_contract["driving_audio"] = dict(driving_audio_contract)
        global_contract["driving_audio_vae"] = driving_audio_vae_value
    if reference_video_contract is not None:
        global_contract["reference_video"] = dict(reference_video_contract)
    if guide_contract is not None:
        global_contract["guide"] = dict(guide_contract)
    timeline_chunk_contracts = []
    if timeline_video_contract is not None:
        timeline_value = dict(timeline_video_contract)
        timeline_chunk_contracts = list(timeline_value.pop("chunk_slices", []))
        if len(timeline_chunk_contracts) != chunks:
            raise RunStorageError(
                "Timeline Video contract does not match the configured chunk count"
            )
        global_contract["timeline_video"] = timeline_value
    contract = {
        "global": global_contract,
        "chunk_count": chunks,
        "prompt_mode": str(prompt_plan["mode"]),
        "prompt_hashes": prompt_hashes,
        "reroll_from_chunk": boundary,
        "last_frame_hash": str(last_frame_hash),
    }
    if reference_storage_plan is not None:
        routed_groups = reference_storage_plan.group_contracts
        validate_reference_group_contracts(
            routed_groups, chunk_count=chunks,
            terminal_merge_enabled=(
                (execution_semantics or {}).get("flf_execution") == "terminal_merged_10s_seed_v2"
            ),
        )
        contract["reference_group_contracts"] = routed_groups
    lineage_sha256 = _nonce_lineage_hash(
        contract,
        timeline_video_chunk_contracts=timeline_chunk_contracts,
    )
    contract["nonce_lineage_sha256"] = lineage_sha256
    contract = _apply_reroll_branch_contract(
        contract,
        boundary=boundary,
        requested_nonce=int(reroll_nonce),
        effective_nonce=int(reroll_nonce) if boundary > 0 else 0,
    )
    reasons = list(upstream_graph_reasons or []) if graph_authoritative else []
    if not model_safe:
        reasons.append("MODEL wrapper/patch contract is not completely observable")
    if not sampler_safe:
        reasons.append("SAMPLER function/options are not completely observable")
    if not clip_safe:
        reasons.append("CLIP/Qwen encoder contract is not completely observable")
    if not video_vae_safe:
        reasons.append("Video VAE contract is not completely observable")
    if not audio_vae_safe:
        reasons.append("Reference Audio VAE contract is not completely observable")
    if not driving_audio_vae_safe:
        reasons.append("Driving Audio VAE contract is not completely observable")
    graph_safe = bool(upstream_graph_safe) if graph_authoritative else True
    return contract, model_safe and clip_safe and video_vae_safe and audio_vae_safe and driving_audio_vae_safe and sampler_safe and graph_safe, reasons


def revision_identity(contract: dict[str, Any]) -> tuple[str, str]:
    full = _hash(contract)
    return full[:16], full


def _pid_exists_windows(pid: int) -> bool:
    """Probe a Windows PID without sending a console event or terminating it."""
    import ctypes
    from ctypes import wintypes

    process_query_limited_information = 0x1000
    error_access_denied = 5
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = (
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.DWORD,
    )
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    ctypes.set_last_error(0)
    handle = kernel32.OpenProcess(
        process_query_limited_information,
        False,
        int(pid),
    )
    if handle:
        kernel32.CloseHandle(handle)
        return True
    return ctypes.get_last_error() == error_access_denied


def _pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if os.name == "nt":
        return _pid_exists_windows(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


class _RunLock:
    def __init__(self, path: Path):
        self.path = path
        self.token = uuid.uuid4().hex
        self.acquired = False

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "pid": os.getpid(), "hostname": socket.gethostname(),
            "started_utc": _now(), "token": self.token,
        }
        encoded = (_canonical(payload) + "\n").encode("utf-8")
        for _ in range(2):
            try:
                descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                try:
                    existing = _read_json(self.path)
                except Exception as exc:
                    raise RunStorageError(f"Run Storage lock exists and is unreadable: {self.path}") from exc
                if str(existing.get("hostname", "")) == socket.gethostname() and not _pid_exists(int(existing.get("pid", -1))):
                    self.path.unlink()
                    continue
                raise RunStorageError(
                    f"Run Name is locked by pid={existing.get('pid')} host={existing.get('hostname')}"
                )
            else:
                try:
                    os.write(descriptor, encoded)
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
                self.acquired = True
                return
        raise RunStorageError("failed to recover stale Run Storage lock")

    def release(self) -> None:
        if not self.acquired:
            return
        try:
            existing = _read_json(self.path)
            if existing.get("token") == self.token:
                self.path.unlink()
        finally:
            self.acquired = False


def _entry_metadata(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "sequence_index": int(entry["sequence_index"]),
        "clip_index": int(entry["clip_index"]),
        "prompt_hash": str(entry["prompt_hash"]),
        "seed": int(entry["seed"]),
        "context_frames": int(entry["context_frames"]),
        "motion_score": float(entry["motion_score"]),
        "plan": dict(entry["plan"]),
    }


def _resume_session_settings(
    *,
    contract: dict[str, Any],
    revision_id: str,
    first_frame_hash: str,
    last_frame_hash: str,
    reference_storage_plan: ReferenceStoragePlan | None = None,
    accepted_chunks: int = 0,
) -> dict[str, Any]:
    settings = {
        "run_storage_validated_prefix": True,
        "revision_id": str(revision_id),
        "first_frame_hash": str(first_frame_hash),
        "last_frame_hash": str(last_frame_hash),
    }
    settings.update(
        dict((contract.get("global") or {}).get("execution_semantics") or {})
    )
    if reference_storage_plan is not None:
        settings["reference_routing_v1"] = session_routing_settings(
            reference_storage_plan, accepted_chunks,
        )
    return settings


def _terminal_merge_enabled(contract: dict[str, Any]) -> bool:
    semantics = (contract.get("global") or {}).get("execution_semantics") or {}
    return semantics.get("flf_execution") == "terminal_merged_10s_seed_v2"


def _manifest_sampling_identity(manifest: dict[str, Any]) -> tuple[str, str]:
    contract = manifest.get("contract")
    if not isinstance(contract, dict):
        raise RunStorageError("stored sampling contract is missing")
    routed_version = (contract.get("global") or {}).get("reference_routing_contract_version")
    routed_groups = contract.get("reference_group_contracts")
    if routed_version is not None or routed_groups is not None:
        if routed_version != REFERENCE_ROUTING_CONTRACT_VERSION:
            raise RunStorageError("stored Reference routing contract version is incompatible")
        try:
            groups = validate_reference_group_contracts(
                routed_groups, chunk_count=int(contract["chunk_count"]),
                terminal_merge_enabled=_terminal_merge_enabled(contract),
            )
        except (ReferenceStorageContractError, KeyError, TypeError, ValueError) as exc:
            raise RunStorageError(f"stored Reference group contract is invalid: {exc}") from exc
        expected = {
            int(chunk): record["sha256"]
            for record in groups for chunk in record["descriptor"]["logical_chunks"]
        }
        chunks = contract.get("chunk_contracts")
        if (not isinstance(chunks, list) or len(chunks) != len(expected)
                or any(not isinstance(item, dict) or
                       item.get("physical_group_reference_sha256") != expected[index + 1]
                       for index, item in enumerate(chunks))):
            raise RunStorageError("stored Reference group/chunk contracts disagree")
    contract_revision_id, contract_sha256 = revision_identity(contract)
    if str(manifest.get("contract_sha256", "")) != contract_sha256:
        raise RunStorageError("stored sampling contract SHA-256 is invalid")
    schema = int(manifest.get("run_storage_schema_version", -1))
    if schema not in RUN_STORAGE_READABLE_SCHEMA_VERSIONS:
        raise RunStorageError("stored Run Storage schema is incompatible")
    stored_sampling_id = str(
        manifest.get("sampling_revision_id", manifest.get("revision_id", ""))
    )
    if stored_sampling_id != contract_revision_id:
        raise RunStorageError("stored sampling revision identity is invalid")
    if schema == 2 and str(manifest.get("revision_id", "")) != contract_revision_id:
        raise RunStorageError("legacy storage revision identity is invalid")
    return contract_revision_id, contract_sha256


def _storage_revision_identity(
    *,
    contract_sha256: str,
    take_action: str,
    selected_revision_id: str,
    effective_nonce: int,
    branch_boundary: int,
) -> str:
    return _hash(
        {
            "run_storage_schema_version": RUN_STORAGE_SCHEMA_VERSION,
            "contract_sha256": str(contract_sha256),
            "take_action": str(take_action),
            "selected_revision_id": str(selected_revision_id),
            "effective_nonce": int(effective_nonce),
            "branch_boundary": int(branch_boundary),
        }
    )[:16]


class RunStorageController:
    def __init__(self, run_name: str):
        self.run_name = sanitize_run_name(run_name)
        self.run_root = _output_root() / "h3_continuum" / "runs" / self.run_name
        self.revisions_root = self.run_root / "revisions"
        self.lock = _RunLock(self.run_root / ".lock")
        self.context_token = None
        self.contract: dict[str, Any] | None = None
        self.contract_sha256 = ""
        self.revision_id = ""
        self.revision_root: Path | None = None
        self.manifest: dict[str, Any] | None = None
        self.prompts: list[str] = []
        self.reused_count = 0
        self.generated_count = 0
        self.disabled_reasons: list[str] = []
        self.notes: list[str] = []
        self.resume_safe = False
        self.effective_reroll_nonce = 0
        self.nonce_decision = "inactive"
        self.prompt_graph: dict[str, Any] | None = None
        self.sampler_node_id: str | None = None
        self.review_generation_mode: str | None = None
        self.review_action: str | None = None
        self.review_manual_regenerate_from: int = 0
        self.review_execution = None
        self.review_head: dict[str, Any] | None = None
        self.validated_prefix: ValidatedPrefix | EmptyValidatedPrefix | None = None
        self.review_runtime_metrics = {
            "review_decision_created": 0,
            "review_reconcile": 0,
        }
        self.inherited_review_unit: dict[str, int] | None = None
        self.pending_review_pause_metadata: dict[str, Any] | None = None
        self.take_action = TAKE_ACTION_AUTOMATIC
        self.take_group = 0
        self.take_revision_id = ""
        self.selected_take_chain: list[dict[str, Any]] = []
        self.selected_take_records: list[dict[str, Any]] = []
        self.selected_take_revision: dict[str, Any] | None = None
        self.pending_branch_cut: dict[str, Any] | None = None
        self.storage_revision_id_override = ""
        # Lock-scoped metadata only. Never cache tensors or skip raw integrity checks.
        self._manifest_snapshot = None
        self._plan_import = None
        self.io_metrics = {"manifest_scans": 0, "manifest_reads": 0,
                           "raw_loads": 0, "raw_bytes": 0,
                           "manifest_seconds": 0.0, "raw_seconds": 0.0}

    def set_prompt_graph(self, prompt: Any, unique_id: Any) -> None:
        self.prompt_graph = prompt if isinstance(prompt, dict) else None
        self.sampler_node_id = None if unique_id is None else str(unique_id)

    def configure_review(
        self,
        *,
        generation_mode: str,
        review_action: str,
        manual_regenerate_from: int = 0,
        take_action: str = TAKE_ACTION_AUTOMATIC,
        take_group: int = 0,
        take_revision_id: str = "",
    ) -> None:
        """Attach a non-identity review intent before Production preparation."""

        self.review_generation_mode = str(generation_mode)
        self.review_action = str(review_action)
        self.review_manual_regenerate_from = int(manual_regenerate_from)
        if str(take_action) not in TAKE_ACTION_OPTIONS:
            raise RunStorageError(f"unknown Take action: {take_action!r}")
        self.take_action = str(take_action)
        self.take_group = int(take_group)
        self.take_revision_id = str(take_revision_id).strip()
        if self.take_action != TAKE_ACTION_AUTOMATIC and (
            self.take_group < 1 or not self.take_revision_id
        ):
            raise RunStorageError(
                "Use This Take / Continue From Here requires a group and revision ID"
            )

    def __enter__(self) -> "RunStorageController":
        self.lock.acquire()
        self._manifest_snapshot = None
        self.context_token = _ACTIVE.set(self)
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        try:
            if exc is not None and self.manifest is not None:
                self.manifest.pop("review_unit", None)
                self.manifest.pop("review_pause_reason", None)
                self.manifest.update(status="interrupted", updated_utc=_now(), last_error=f"{type(exc).__name__}: {exc}"[:2048])
                self._write_manifest()
                self._write_project()
        finally:
            if self.context_token is not None:
                _ACTIVE.reset(self.context_token)
                self.context_token = None
            self._manifest_snapshot = None
            self._plan_import = None
            self.lock.release()

    def _manifest_path(self) -> Path:
        if self.revision_root is None:
            raise RunStorageError("Run Storage revision is not prepared")
        return self.revision_root / "manifest.json"

    def _write_manifest(self) -> None:
        if self.manifest is not None:
            _write_json(self._manifest_path(), self.manifest)
            self._manifest_snapshot = None

    def _read_manifests(self) -> dict[str, dict[str, Any]]:
        if self.context_token is not None and self._manifest_snapshot is not None:
            return self._manifest_snapshot
        started = time.perf_counter()
        manifests: dict[str, dict[str, Any]] = {}
        self.io_metrics["manifest_scans"] += 1
        for path in sorted(self.revisions_root.glob("*/manifest.json")):
            try:
                self.io_metrics["manifest_reads"] += 1
                value = _read_json(path)
                _manifest_sampling_identity(value)
                revision_id = str(value.get("revision_id", ""))
                if not revision_id or revision_id != path.parent.name:
                    raise RunStorageError("storage revision path identity is invalid")
                manifests[revision_id] = value
            except Exception as exc:
                self.notes.append(f"provenance manifest {path.parent.name} rejected: {exc}")
        self.io_metrics["manifest_seconds"] += time.perf_counter() - started
        if self.context_token is not None:
            self._manifest_snapshot = manifests
        return manifests

    def _manifest_provenance_chain(
        self,
        manifest: dict[str, Any],
        manifests: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        contract = manifest.get("contract") or {}
        records = list(manifest.get("chunks") or [])
        groups = physical_groups(
            chunks=int(contract.get("chunk_count", 0)),
            terminal_merge_enabled=_terminal_merge_enabled(contract),
        )
        chain: list[dict[str, Any]] = []
        parent_revision_id: str | None = None
        for group in groups:
            if group.end > len(records):
                break
            group_records = records[group.start - 1 : group.end]
            sources = {str(record.get("storage_revision_id", "")) for record in group_records}
            if len(sources) != 1 or "" in sources:
                raise RunStorageError("physical group has ambiguous storage sources")
            source_id = next(iter(sources))
            source_manifest = manifests.get(source_id)
            if source_manifest is None:
                raise RunStorageError(
                    f"physical group source manifest is missing: {source_id}"
                )
            _, source_contract_sha256 = _manifest_sampling_identity(source_manifest)
            source_contract = source_manifest.get("contract") or {}
            source_lineage = str(source_contract.get("nonce_lineage_sha256", ""))
            if source_lineage != str(contract.get("nonce_lineage_sha256", "")):
                raise RunStorageError("physical group source crosses sampling lineages")
            source_boundary = int(source_contract.get("reroll_from_chunk", 0))
            source_nonce = int(source_contract.get("effective_reroll_nonce", 0))
            variation_nonce = (
                source_nonce if source_boundary > 0 and group.start >= source_boundary else 0
            )
            branch_cut = None
            if source_nonce > 0 and source_boundary == group.start:
                branch_cut = {
                    "selected_revision_id": parent_revision_id or "",
                    "after_physical_group": group.start - 1,
                }
            revision = make_group_revision(
                parent_revision_id=parent_revision_id,
                group=group,
                variation_nonce=variation_nonce,
                created_utc=str(
                    source_manifest.get("created_utc")
                    or source_manifest.get("updated_utc")
                    or ""
                ),
                storage_revision_id=source_id,
                generation_contract_sha256=source_contract_sha256,
                lineage_sha256=source_lineage,
                records=group_records,
                branch_cut=branch_cut,
            )
            chain.append(revision)
            parent_revision_id = revision["revision_id"]
        persisted = manifest.get("branch_provenance")
        if persisted is not None:
            if not isinstance(persisted, dict):
                raise RunStorageError("branch provenance metadata must be an object")
            if int(persisted.get("version", -1)) != BRANCH_PROVENANCE_VERSION:
                raise RunStorageError("branch provenance version is unsupported")
            expected = [revision["revision_id"] for revision in chain]
            if list(persisted.get("active_chain") or []) != expected:
                raise RunStorageError("persisted active chain does not match stored records")
        return chain

    def _provenance_catalog(
        self,
        *,
        lineage_sha256: str | None = None,
    ) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, list[str]]]:
        manifests = self._read_manifests()
        catalog: dict[str, dict[str, Any]] = {}
        chains: dict[str, list[str]] = {}
        for revision_id, manifest in manifests.items():
            if str(manifest.get("status", "")) not in {
                REVISION_STATUS_REVIEW_READY,
                REVISION_STATUS_COMPLETE,
            }:
                continue
            contract = manifest.get("contract") or {}
            if lineage_sha256 is not None and str(
                contract.get("nonce_lineage_sha256", "")
            ) != str(lineage_sha256):
                continue
            try:
                chain = self._manifest_provenance_chain(manifest, manifests)
            except Exception as exc:
                self.notes.append(f"provenance chain {revision_id} rejected: {exc}")
                continue
            if not chain:
                continue
            chains[revision_id] = [item["revision_id"] for item in chain]
            for item in chain:
                existing = catalog.get(item["revision_id"])
                if existing is not None and existing != item:
                    raise RunStorageError("immutable group revision collision")
                catalog[item["revision_id"]] = item
        return manifests, catalog, chains

    def _canonical_project_selection(
        self,
        *,
        catalog: dict[str, dict[str, Any]],
        chains: dict[str, list[str]],
    ) -> tuple[str | None, list[str]]:
        path = self.run_root / "project.json"
        if path.exists():
            try:
                project = _read_json(path)
                if int(project.get("run_storage_schema_version", -1)) == RUN_STORAGE_SCHEMA_VERSION:
                    storage_revision_id = str(project.get("canonical_storage_revision_id", ""))
                    chain = list(project.get("canonical_chain") or [])
                    if storage_revision_id in chains and chain == chains[storage_revision_id]:
                        if chain and chain[-1] in catalog:
                            return storage_revision_id, chain
            except Exception as exc:
                self.notes.append(f"canonical project head rejected: {exc}")
        candidates: list[tuple[int, str, str, str, list[str]]] = []
        legacy_candidates: list[tuple[int, str, str, list[str]]] = []
        manifests = self._read_manifests()
        for storage_revision_id, chain in chains.items():
            manifest = manifests[storage_revision_id]
            provenance = manifest.get("branch_provenance") or {}
            committed = str(provenance.get("canonical_committed_utc", ""))
            if committed:
                candidates.append(
                    (
                        int(provenance.get("canonical_sequence", 0)),
                        committed,
                        storage_revision_id,
                        chain[-1],
                        chain,
                    )
                )
            else:
                contract = manifest.get("contract") or {}
                legacy_candidates.append(
                    (
                        int(contract.get("effective_reroll_nonce", 0)),
                        str(manifest.get("updated_utc", "")),
                        storage_revision_id,
                        chain,
                    )
                )
        if candidates:
            _, _, storage_revision_id, _, chain = max(candidates)
            return storage_revision_id, chain
        if legacy_candidates:
            _, _, storage_revision_id, chain = max(legacy_candidates)
            return storage_revision_id, chain
        return None, []

    def _write_project(self, *, set_canonical: bool = False) -> None:
        manifests, catalog, chains = self._provenance_catalog()
        revisions = []
        for revision_id, value in sorted(manifests.items()):
            lifecycle = value.get("nonce_lifecycle") or {}
            revision = {
                key: value.get(key)
                for key in (
                    "revision_id",
                    "sampling_revision_id",
                    "contract_sha256",
                    "status",
                    "updated_utc",
                    "resume_safe",
                )
            }
            revision.update(
                sampling_contract_version=value.get("sampling_contract_version"),
                generation_reusable=_reusable_manifest(value),
                nonce_mode=lifecycle.get("mode"),
                effective_reroll_nonce=lifecycle.get("effective_nonce"),
                reroll_from_chunk=(value.get("contract") or {}).get("reroll_from_chunk"),
                review_control_version=value.get("review_control_version"),
                review_unit=value.get("review_unit"),
                review_pause_reason=value.get("review_pause_reason"),
                branch_regenerate_from=value.get("branch_regenerate_from"),
                active_chain=chains.get(revision_id, []),
            )
            revisions.append(revision)
        canonical_storage_revision_id, canonical_chain = self._canonical_project_selection(
            catalog=catalog,
            chains=chains,
        )
        if set_canonical and self.revision_id in chains:
            canonical_storage_revision_id = self.revision_id
            canonical_chain = chains[self.revision_id]
        canonical_head = canonical_chain[-1] if canonical_chain else None
        _write_json(
            self.run_root / "project.json",
            {
                "run_storage_schema_version": RUN_STORAGE_SCHEMA_VERSION,
                "branch_provenance_version": BRANCH_PROVENANCE_VERSION,
                "run_name": self.run_name,
                "updated_utc": _now(),
                "canonical_storage_revision_id": canonical_storage_revision_id,
                "canonical_head_revision_id": canonical_head,
                "canonical_chain": canonical_chain,
                "active_revisions": active_revision_map(
                    [catalog[revision_id] for revision_id in canonical_chain]
                ) if canonical_chain else {},
                "group_revisions": sorted(
                    [dict(item,
                          sampling_contract_version=(manifests.get(str(item.get("storage_revision_id"))) or {}).get("sampling_contract_version"),
                          generation_reusable=_reusable_manifest(manifests.get(str(item.get("storage_revision_id"))) or {}))
                     for item in catalog.values()],
                    key=lambda item: (
                        int(item["group"]["physical_group"]),
                        str(item["revision_order"]),
                        str(item["revision_id"]),
                    ),
                ),
                "revisions": revisions,
            },
        )

    def _load_entry(self, record: dict[str, Any], prompt: str) -> dict[str, Any]:
        source = str(record["storage_revision_id"])
        filename = str(record["filename"])
        if Path(filename).name != filename or any(c in filename for c in "/\\") or filename in {"", ".", ".."}:
            raise RunStorageError("stored chunk filename is invalid")
        if source in {"", ".", ".."} or any(c in source for c in "/\\"):
            raise RunStorageError("stored revision directory is invalid")
        path = self.revisions_root / source / "chunks" / filename
        if not path.resolve().is_relative_to(self.revisions_root.resolve()):
            raise RunStorageError("stored chunk escapes the Run Storage directory")
        started = time.perf_counter()
        if path.stat().st_size != int(record["file_size"]):
            raise RunStorageError(f"stored chunk size mismatch: {filename}")
        expected_sha256 = str(record.get("file_sha256", ""))
        if not expected_sha256:
            raise RunStorageError(f"stored chunk SHA-256 is missing: {filename}")
        if _file_sha256(path) != expected_sha256:
            raise RunStorageError(f"stored chunk SHA-256 mismatch: {filename}")
        self.io_metrics["raw_bytes"] += int(record["file_size"])
        self.io_metrics["raw_loads"] += 1
        with safe_open(str(path), framework="pt", device="cpu") as handle:
            if set(handle.keys()) != {"audio", "video"}:
                raise RunStorageError(f"stored chunk tensors are invalid: {filename}")
            video, audio = handle.get_tensor("video"), handle.get_tensor("audio")
        entry = dict(record["entry"])
        entry.update(prompt=str(prompt), video=video, audio=audio, reused=False)
        result = validate_chunk_entry(entry)
        self.io_metrics["raw_seconds"] += time.perf_counter() - started
        return result

    def _valid_prefix(
        self,
        manifest: dict[str, Any],
        hashes: list[str],
        *,
        current_contract: dict[str, Any] | None = None,
        prompts: list[str] | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        stored_contract = manifest.get("contract") or {}
        prompts = self.prompts if prompts is None else prompts
        active_contract = self.contract if current_contract is None else current_contract
        stored = list(stored_contract.get("chunk_contract_hashes") or [])
        stored_prompt_hashes = list(stored_contract.get("prompt_hashes") or [])
        records = list(manifest.get("chunks") or [])
        entries, accepted = [], []
        for position, current in enumerate(hashes):
            if position >= len(stored):
                break
            compatible_absent_last_frame = False
            if stored[position] != current:
                compatible_absent_last_frame = _legacy_absent_last_frame_compatible(
                    stored_contract=stored_contract,
                    current_contract=active_contract or {},
                    position=position,
                    stored_hash=stored[position],
                    current_hash=current,
                )
            if stored[position] != current and not compatible_absent_last_frame:
                break
            if position >= len(records) or int(records[position].get("sequence_index", -1)) != position:
                break
            try:
                entry = self._load_entry(records[position], prompts[position])
            except Exception as exc:
                self.notes.append(f"stored chunk {position + 1} rejected: {exc}")
                break
            if (
                position < len(stored_prompt_hashes)
                and str(entry.get("prompt_hash", ""))
                != str(stored_prompt_hashes[position])
            ):
                self.notes.append(
                    f"stored chunk {position + 1} rejected: prompt lineage mismatch"
                )
                break
            entries.append(entry)
            accepted.append(records[position])
            if compatible_absent_last_frame:
                self.notes.append(
                    f"stored chunk {position + 1} reused through V3.6.1 absent "
                    "Last Frame compatibility"
                )
        return entries, accepted

    def _valid_provenance_prefix(
        self,
        manifest: dict[str, Any],
        *,
        current_contract: dict[str, Any],
        enforce_sampling_contract: bool = False,
        prompts: list[str] | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        prompts = self.prompts if prompts is None else prompts
        manifests = self._read_manifests()
        storage_revision_id = str(manifest.get("revision_id", ""))
        if storage_revision_id not in manifests:
            return [], []
        chain = self._manifest_provenance_chain(manifest, manifests)
        if chain and str(chain[-1].get("lineage_sha256", "")) != str(
            current_contract.get("nonce_lineage_sha256", "")
        ):
            raise RunStorageError("provenance prefix belongs to another sampling lineage")
        records = list(manifest.get("chunks") or [])
        if sum(
            int(item["group"]["end"]) - int(item["group"]["start"]) + 1
            for item in chain
        ) != len(records):
            raise RunStorageError("provenance chain length does not match stored records")
        expected_prompts = list(current_contract.get("prompt_hashes") or [])
        entries: list[dict[str, Any]] = []
        for position, record in enumerate(records):
            if position >= len(prompts) or position >= len(expected_prompts):
                raise RunStorageError("provenance prefix exceeds the current prompt plan")
            if enforce_sampling_contract:
                boundary = int(current_contract.get("reroll_from_chunk", 0))
                # Ancestry proves where a Take came from, not that it satisfies a
                # new reroll. Preserve the accepted prefix before the branch cut;
                # after it, compare the actual producing revision's contract.
                # Same-nonce interrupted work remains reusable.
                if boundary <= 0 or position + 1 >= boundary:
                    producer_id = str(record.get("storage_revision_id", storage_revision_id))
                    producer = (manifests.get(producer_id) or {}).get("contract") or {}
                    produced_hashes = list(producer.get("chunk_contract_hashes") or [])
                    requested_hashes = list(current_contract.get("chunk_contract_hashes") or [])
                    if (
                        position >= len(produced_hashes)
                        or position >= len(requested_hashes)
                        or produced_hashes[position] != requested_hashes[position]
                    ):
                        break
            entry = self._load_entry(record, prompts[position])
            if str(entry.get("prompt_hash", "")) != str(expected_prompts[position]):
                raise RunStorageError("provenance prefix prompt lineage is incompatible")
            entries.append(entry)
        return entries, records[:len(entries)]

    def _compatible_plan_prefix(
        self, manifest: dict[str, Any], current_contract: dict[str, Any],
        *, stop_before: int = 0, resume_safe: bool = True,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Certify a prefix for import, not for cross-lineage Take selection.

        Original provenance is validated first. Every reused physical group must
        retain its topology and actual producing per-chunk contract. New plans
        get their own raw copies below; no foreign lineage is spliced into a DAG.
        """
        if not _reusable_sampling_contract(current_contract, resume_safe=resume_safe) or not _reusable_manifest(manifest):
            return [], []
        manifests = self._read_manifests()
        source_contract = manifest.get("contract") or {}
        _manifest_sampling_identity(manifest)
        if _hash(source_contract.get("global")) != _hash(current_contract.get("global")):
            return [], []
        chain = self._manifest_provenance_chain(manifest, manifests)
        records = list(manifest.get("chunks") or [])
        allowed = {g.start: g for g in physical_groups(
            chunks=int(current_contract["chunk_count"]),
            terminal_merge_enabled=_terminal_merge_enabled(current_contract),
        )}
        accepted = []
        requested_by_producer = {}
        for revision in chain:
            group = revision["group"]
            expected = allowed.get(int(group["start"]))
            if (expected is None or expected.as_metadata() != group
                    or (stop_before > 0 and expected.end >= stop_before)):
                break
            group_records = records[expected.start - 1:expected.end]
            if len(group_records) != expected.end - expected.start + 1:
                break
            compatible = True
            for position, record in zip(range(expected.start - 1, expected.end), group_records):
                producer = manifests.get(str(record.get("storage_revision_id", "")))
                if producer is None or not _reusable_manifest(producer):
                    compatible = False
                    break
                if "reference_group_contracts" in (producer.get("contract") or {}):
                    _manifest_sampling_identity(producer)
                producing = producer.get("contract") or {}
                hashes = producing.get("chunk_contract_hashes") or []
                # Accepted earlier Takes can come from several nonce branches.
                # Compare each producing contract against the new plan while
                # preserving that producer's verified variation, not the latest
                # branch's nonce for the entire ancestry.
                producer_id = str(record["storage_revision_id"])
                if producer_id not in requested_by_producer:
                    requested_by_producer[producer_id] = _apply_reroll_branch_contract(
                        current_contract,
                        boundary=int(producing.get("reroll_from_chunk", 0)),
                        requested_nonce=int(producing.get("effective_reroll_nonce", 0)),
                        effective_nonce=int(producing.get("effective_reroll_nonce", 0)),
                    )["chunk_contract_hashes"]
                requested_hashes = requested_by_producer[producer_id]
                producer_records = producer.get("chunks") or []
                if (position >= len(hashes) or position >= len(requested_hashes)
                        or hashes[position] != requested_hashes[position]
                        or position >= len(producer_records)
                        or producer_records[position] != record):
                    compatible = False
                    break
            if not compatible:
                break
            accepted.extend(group_records)
        entries = []
        # Only now load the certified prefix. A corrupt group never becomes reusable.
        for position, record in enumerate(accepted):
            item = self._load_entry(record, self.prompts[position])
            if item["prompt_hash"] != current_contract["prompt_hashes"][position]:
                raise RunStorageError("imported prefix prompt does not match its producing contract")
            entries.append(item)
        return entries, accepted

    def _find_plan_import(
        self, contract: dict[str, Any], *, stop_before: int = 0, resume_safe: bool = True,
    ) -> dict[str, Any] | None:
        """Find a verified plan prefix, stopping before explicit regeneration."""
        if stop_before == 1 or not _reusable_sampling_contract(contract, resume_safe=resume_safe):
            return None
        manifests = self._read_manifests()
        # A matching plan already owns its history. Do not reload an older plan
        # merely because that older plan also supplies a compatible prefix.
        if any((m.get("contract") or {}).get("nonce_lineage_sha256")
               == contract.get("nonce_lineage_sha256") for m in manifests.values()):
            return None
        canonical_id = ""
        try:
            project = _read_json(self.run_root / "project.json")
            canonical_id = str(project.get("canonical_storage_revision_id", ""))
            selected = manifests.get(canonical_id) or {}
            expected_chain = (selected.get("branch_provenance") or {}).get("active_chain")
            if expected_chain is not None and project.get("canonical_chain") != expected_chain:
                canonical_id = ""
        except (OSError, ValueError, RunStorageError):
            pass
        ordered = sorted(manifests.values(), key=lambda m: (
            str(m.get("revision_id", "")) == canonical_id,
            int((m.get("branch_provenance") or {}).get("canonical_sequence", 0)),
            str(m.get("updated_utc", "")), str(m.get("revision_id", "")),
        ), reverse=True)
        for manifest in ordered:
            source = manifest.get("contract") or {}
            if (not _reusable_manifest(manifest)
                    or manifest.get("status") not in {"complete", "review_ready", "interrupted"}
                    or source.get("nonce_lineage_sha256") == contract.get("nonce_lineage_sha256")
                    or _hash(source.get("global")) != _hash(contract.get("global"))):
                continue
            # Preserve accepted variations when extending/editing a plan. Explicit
            # regeneration still uses the existing nonce resolver, not this path.
            boundary = int(source.get("reroll_from_chunk", 0))
            nonce = int(source.get("effective_reroll_nonce", 0))
            if boundary > int(contract["chunk_count"]):
                boundary = nonce = 0
            requested = _apply_reroll_branch_contract(
                contract, boundary=boundary, requested_nonce=nonce, effective_nonce=nonce,
            )
            try:
                entries, records = self._compatible_plan_prefix(
                    manifest, requested, stop_before=stop_before,
                )
            except (RunStorageError, ValueError, OSError) as exc:
                self.notes.append(f"plan prefix {manifest.get('revision_id', '')} rejected: {exc}")
                continue
            if not entries:
                continue
            if boundary > len(entries):
                boundary = nonce = 0
                requested = _apply_reroll_branch_contract(
                    contract, boundary=0, requested_nonce=0, effective_nonce=0,
                )
            groups = physical_groups(chunks=int(contract["chunk_count"]),
                                     terminal_merge_enabled=_terminal_merge_enabled(contract))
            unit = next(g for g in groups if g.end == len(entries))
            return {"revision_id": str(manifest["revision_id"]),
                    "status": "complete" if len(entries) == int(contract["chunk_count"]) else "review_ready",
                    "validated_prefix_count": len(entries), "review_unit": unit.as_metadata(),
                    "branch_regenerate_from": boundary, "effective_reroll_nonce": nonce,
                    "manifest": manifest, "entries": entries, "records": records,
                    "contract": requested, "updated_utc": str(manifest.get("updated_utc", ""))}
        return None

    def _adopt_plan_prefix(self, imported: dict[str, Any]) -> list[dict[str, Any]]:
        """Copy verified tensors into the new plan; keep every old revision intact."""
        if not _reusable_sampling_contract(self.contract, resume_safe=self.resume_safe) or not _reusable_manifest(imported.get("manifest") or {}):
            raise RunStorageError("plan prefix has no reusable Sampling v6 identity")
        self.manifest["prefix_import"] = {
            "version": 1, "source_revision_id": imported["revision_id"],
            "source_contract_sha256": imported["manifest"]["contract_sha256"],
            "records": [
                {"sequence_index": position,
                 "storage_revision_id": original["storage_revision_id"],
                 "filename": original["filename"], "file_sha256": original["file_sha256"]}
                for position, original in enumerate(imported["records"])
            ],
        }
        if imported.get("selected_take_import") is not None:
            self.manifest["prefix_import"]["selected_take"] = dict(
                imported["selected_take_import"]
            )
        self._write_manifest()
        records = []
        imported_entries = list(imported["entries"])
        groups = physical_groups(
            chunks=int((self.contract or {})["chunk_count"]),
            terminal_merge_enabled=_terminal_merge_enabled(self.contract or {}),
        )
        for group in groups:
            if group.end > len(imported_entries):
                break
            positions = tuple(range(group.start - 1, group.end))
            self.commit_group(
                tuple(imported_entries[position] for position in positions),
                positions=positions,
            )
            records.extend(
                dict(record)
                for record in self.manifest["chunks"][-len(positions):]
            )
        self.generated_count = 0  # Copies are reused work, never new Sampling.
        if imported.get("selected_take_import") is not None:
            local_chain = self._manifest_provenance_chain(
                self.manifest, self._read_manifests(),
            )
            if not local_chain:
                raise RunStorageError("imported Take has no new-plan provenance")
            self.pending_branch_cut = {
                "selected_revision_id": local_chain[-1]["revision_id"],
                "after_physical_group": int(local_chain[-1]["group"]["physical_group"]),
            }
        self.notes.append(f"Imported {len(records)} verified prefix chunks into the new plan; originals preserved")
        return records

    def _highest_lineage_nonce(self, lineage_sha256: str) -> int:
        highest = 0
        for manifest in self._read_manifests().values():
            contract = manifest.get("contract") or {}
            if str(contract.get("nonce_lineage_sha256", "")) != str(lineage_sha256):
                continue
            highest = max(highest, int(contract.get("effective_reroll_nonce", 0)))
        return highest

    def _validated_take_selection(
        self,
        contract: dict[str, Any],
        *, source_lineage: str | None = None, resume_safe: bool = True,
    ) -> dict[str, Any]:
        if not _reusable_sampling_contract(contract, resume_safe=resume_safe):
            raise RunStorageError("selected Take cannot be reused: current sampling identity is unobservable or unsupported")
        lineage = str(source_lineage or contract.get("nonce_lineage_sha256", ""))
        manifests, catalog, _ = self._provenance_catalog(
            lineage_sha256=lineage,
        )
        try:
            chain = resolve_chain(catalog, self.take_revision_id)
        except BranchProvenanceError as exc:
            raise RunStorageError(f"selected Take provenance is invalid: {exc}") from exc
        selected = chain[-1]
        group = selected["group"]
        if int(group["physical_group"]) != self.take_group:
            raise RunStorageError(
                "selected Take group does not match its immutable revision"
            )
        allowed = {
            item.physical_group: item
            for item in physical_groups(
                chunks=int(contract["chunk_count"]),
                terminal_merge_enabled=_terminal_merge_enabled(contract),
            )
        }
        records: list[dict[str, Any]] = []
        entries: list[dict[str, Any]] = []
        for revision in chain:
            revision_group = revision["group"]
            physical_group = int(revision_group["physical_group"])
            expected_group = allowed.get(physical_group)
            if expected_group is None or (
                expected_group.start != int(revision_group["start"])
                or expected_group.end != int(revision_group["end"])
            ):
                raise RunStorageError(
                    "selected Take splits or changes a physical group"
                )
            if str(revision.get("lineage_sha256", "")) != lineage:
                raise RunStorageError("selected Take belongs to another sampling lineage")
            source_id = str(revision["storage_revision_id"])
            source_manifest = manifests.get(source_id)
            if source_manifest is None:
                raise RunStorageError("selected Take source manifest is unavailable")
            if not _reusable_manifest(source_manifest):
                raise RunStorageError("selected Take is read-only: Sampling v6 with an observable identity is required")
            source_records = list(source_manifest.get("chunks") or [])
            for position in range(expected_group.start - 1, expected_group.end):
                if position >= len(source_records):
                    raise RunStorageError("selected Take source record is incomplete")
                record = source_records[position]
                if int(record.get("sequence_index", -1)) != position:
                    raise RunStorageError("selected Take source record position is invalid")
                try:
                    entry = self._load_entry(record, self.prompts[position])
                except Exception as exc:
                    raise RunStorageError(
                        f"selected Take chunk {position + 1} failed integrity validation: {exc}"
                    ) from exc
                expected_prompt = str(contract["prompt_hashes"][position])
                if str(entry.get("prompt_hash", "")) != expected_prompt:
                    raise RunStorageError("selected Take prompt lineage is incompatible")
                records.append(record)
                entries.append(entry)
        if len(records) != int(group["end"]):
            raise RunStorageError("selected Take does not resolve to a complete prefix")
        branch_start = 0
        for revision in chain:
            cut = revision.get("branch_cut")
            if isinstance(cut, dict):
                candidate = int(cut.get("after_physical_group", 0)) + 1
                if candidate > 0:
                    branch_start = candidate
        selected_nonce = int(selected.get("variation_nonce", 0))
        if selected_nonce == 0:
            branch_start = 0
        elif branch_start == 0:
            raise RunStorageError("selected Take nonce has no branch cut provenance")
        return {
            "revision_id": selected["revision_id"],
            "status": (
                REVISION_STATUS_COMPLETE
                if len(records) == int(contract["chunk_count"])
                else REVISION_STATUS_REVIEW_READY
            ),
            "validated_prefix_count": len(records),
            "review_unit": dict(group),
            "branch_regenerate_from": branch_start,
            "effective_reroll_nonce": selected_nonce,
            "updated_utc": str(selected["created_utc"]),
            "records": records,
            "entries": entries,
            "chain": chain,
            "manifest": manifests.get(str(selected["storage_revision_id"])),
        }

    def _validated_review_head(
        self,
        manifest: dict[str, Any],
        *,
        current_contract: dict[str, Any] | None = None,
        for_reuse: bool = True,
        resume_safe: bool = True,
    ) -> dict[str, Any]:
        """Validate stored integrity first; optionally certify current reuse."""

        schema = int(manifest.get("run_storage_schema_version", -1))
        if schema not in RUN_STORAGE_READABLE_SCHEMA_VERSIONS:
            raise RunStorageError("review head uses an incompatible Run Storage schema")
        stored_contract = manifest.get("contract")
        if not isinstance(stored_contract, dict):
            raise RunStorageError("review head sampling contract is missing")
        if for_reuse and (
            current_contract is None
            or not _reusable_sampling_contract(current_contract, resume_safe=resume_safe)
            or not _reusable_manifest(manifest)
        ):
            raise RunStorageError("review head is read-only or its sampling identity is unobservable")
        if for_reuse and str(stored_contract.get("nonce_lineage_sha256", "")) != str(
            current_contract.get("nonce_lineage_sha256", "")
        ):
            raise RunStorageError("review head belongs to a different sampling lineage")
        _, contract_sha256 = _manifest_sampling_identity(manifest)
        revision_id = str(manifest.get("revision_id", ""))
        if int(manifest.get("sampling_contract_version", -1)) not in SAMPLING_READABLE_CONTRACT_VERSIONS:
            raise RunStorageError("review head sampling contract version is incompatible")

        status = str(manifest.get("status", ""))
        if status not in {
            REVISION_STATUS_IN_PROGRESS,
            REVISION_STATUS_INTERRUPTED,
            REVISION_STATUS_REVIEW_READY,
            REVISION_STATUS_COMPLETE,
        }:
            raise RunStorageError(f"review head status is invalid: {status!r}")
        chunks = int(stored_contract.get("chunk_count", 0))
        if chunks <= 0:
            raise RunStorageError("review head configured chunk count is invalid")
        hashes = list(stored_contract.get("chunk_contract_hashes") or [])
        if len(hashes) != chunks:
            raise RunStorageError("review head chunk contract is incomplete")
        records = list(manifest.get("chunks") or [])
        stored_prompts = None if for_reuse else [""] * chunks
        if schema == RUN_STORAGE_SCHEMA_VERSION and manifest.get("branch_provenance"):
            entries, accepted = self._valid_provenance_prefix(
                manifest,
                current_contract=stored_contract,
                prompts=stored_prompts,
            )
        else:
            entries, accepted = self._valid_prefix(
                manifest,
                hashes,
                current_contract=stored_contract,
                prompts=stored_prompts,
            )
        if len(accepted) != len(records):
            raise RunStorageError("review head stored prefix failed validation")
        prefix = len(entries)
        if prefix > chunks:
            raise RunStorageError("review head stored prefix exceeds configured chunks")
        if status == REVISION_STATUS_COMPLETE and prefix != chunks:
            raise RunStorageError("complete review head does not contain every chunk")
        if status != REVISION_STATUS_COMPLETE and prefix == chunks:
            raise RunStorageError("incomplete review head status contains every chunk")

        lifecycle = manifest.get("nonce_lifecycle") or stored_contract.get(
            "nonce_lifecycle"
        ) or {}
        contract_boundary = int(stored_contract.get("reroll_from_chunk", 0))
        contract_nonce = int(stored_contract.get("effective_reroll_nonce", 0))
        if int(lifecycle.get("effective_nonce", contract_nonce)) != contract_nonce:
            raise RunStorageError("review head nonce lifecycle is inconsistent")
        branch_boundary = int(
            manifest.get("branch_regenerate_from", contract_boundary)
        )
        effective_nonce = int(
            manifest.get("effective_reroll_nonce", contract_nonce)
        )
        if branch_boundary != contract_boundary or effective_nonce != contract_nonce:
            raise RunStorageError("review head branch metadata is inconsistent")

        review_version = manifest.get("review_control_version")
        if review_version is not None and int(review_version) != REVIEW_CONTROL_VERSION:
            raise RunStorageError("review head control version is unsupported")
        review_unit = manifest.get("review_unit")
        pause_reason = manifest.get("review_pause_reason")
        if review_unit is not None and pause_reason != "review_each_chunk":
            raise RunStorageError("review head pause reason is inconsistent")
        if review_unit is None and pause_reason is not None:
            raise RunStorageError("review head pause reason has no review unit")
        if status == REVISION_STATUS_REVIEW_READY and review_unit is None:
            raise RunStorageError("review_ready head is missing review_unit metadata")
        if status in {REVISION_STATUS_IN_PROGRESS, REVISION_STATUS_INTERRUPTED}:
            if review_unit is not None:
                raise RunStorageError("unfinished review execution has stale review_unit metadata")

        semantics = (stored_contract.get("global") or {}).get(
            "execution_semantics"
        ) or {}
        terminal_merge_enabled = (
            semantics.get("flf_execution") == "terminal_merged_10s_seed_v2"
        )
        terminal_pair_start = chunks - 1 if terminal_merge_enabled else None
        try:
            normalized_review_unit = validate_review_prefix_metadata(
                configured_chunks=chunks,
                validated_prefix_count=prefix,
                terminal_merge_enabled=terminal_merge_enabled,
                terminal_pair_start=terminal_pair_start,
                latest_review_unit=review_unit,
                latest_revision_status=status,
                latest_effective_nonce=effective_nonce,
                latest_branch_regenerate_from=branch_boundary,
            )
        except ReviewControlError as exc:
            raise RunStorageError(f"review head metadata is invalid: {exc}") from exc

        updated_utc = str(
            manifest.get("updated_utc") or manifest.get("created_utc") or ""
        )
        try:
            datetime.fromisoformat(updated_utc)
        except ValueError as exc:
            raise RunStorageError("review head update timestamp is invalid") from exc
        return {
            "revision_id": revision_id,
            "status": status,
            "validated_prefix_count": prefix,
            "review_unit": review_unit,
            "branch_regenerate_from": branch_boundary,
            "effective_reroll_nonce": effective_nonce,
            "updated_utc": updated_utc,
            "manifest": manifest,
            "entries": entries,
            "records": accepted,
            "normalized_review_unit": normalized_review_unit,
        }

    def find_latest_review_head(
        self,
        contract: dict[str, Any],
        *,
        smart_regenerate_only: bool = False,
        resume_safe: bool = True,
    ) -> dict[str, Any] | None:
        """Return the latest validated compatible disk head deterministically."""

        if not _reusable_sampling_contract(contract, resume_safe=resume_safe):
            self.notes.append("auto-resume disabled: current sampling identity is unobservable or unsupported")
            return None
        if not self.revisions_root.exists():
            return None
        compatible_lineage = str(contract.get("nonce_lineage_sha256", ""))
        mismatched_contracts: list[tuple[str, dict]] = []
        manifests = self._read_manifests()
        canonical_id = ""
        try:
            project = _read_json(self.run_root / "project.json")
            canonical_id = str(project.get("canonical_storage_revision_id", ""))
            selected = manifests.get(canonical_id) or {}
            expected_chain = (selected.get("branch_provenance") or {}).get("active_chain")
            if expected_chain is not None and project.get("canonical_chain") != expected_chain:
                canonical_id = ""
        except (OSError, ValueError, RunStorageError):
            pass
        ordered = sorted(manifests.items(), key=lambda item: (
            item[0] == canonical_id,
            int((item[1].get("contract") or {}).get("effective_reroll_nonce", 0)),
            str(item[1].get("updated_utc", "")), item[0],
        ), reverse=True)
        for revision_id, manifest in ordered:
            stored_contract = manifest.get("contract") or {}
            if not _reusable_manifest(manifest):
                self.notes.append(f"review head {revision_id} is read-only: observable Sampling v6 required")
                continue
            if str(stored_contract.get("nonce_lineage_sha256", "")) != compatible_lineage:
                mismatched_contracts.append((revision_id, stored_contract))
                continue
            try:
                head = self._validated_review_head(
                    manifest,
                    current_contract=contract,
                )
            except Exception as exc:
                self.notes.append(f"review head {revision_id} rejected: {exc}")
                continue
            if smart_regenerate_only and not (
                head["status"] == REVISION_STATUS_REVIEW_READY
                or (
                    head["status"] == REVISION_STATUS_COMPLETE
                    and head["review_unit"] is not None
                )
            ):
                continue
            return head
        # Explain a missing head without changing which heads are reusable.
        # Evaluate only after lookup fails; successful runs are unaffected.
        candidates = []
        for revision_id, stored_contract in mismatched_contracts:
            try:
                delta = _review_contract_mismatches(stored_contract, contract)
                candidates.append((len(delta), revision_id, delta))
            except Exception as exc:
                self.notes.append(
                    f"review head {revision_id} diagnostic unavailable: {type(exc).__name__}"
                )
        for _, revision_id, delta in sorted(candidates)[:3]:
            detail = "; ".join(delta[:12]) or "lineage digest differs; inspect stored integrity"
            if len(delta) > 12:
                detail += f"; {len(delta) - 12} more differing sections"
            self.notes.append(f"review head {revision_id} incompatible: {detail}")
        return None

    def _freeze_validated_prefix(
        self,
        candidate: dict[str, Any] | None,
        *,
        contract: dict[str, Any],
    ) -> ValidatedPrefix | EmptyValidatedPrefix:
        """Freeze the one repository result that may drive this Queue."""

        configured_chunks = int(contract["chunk_count"])
        if candidate is None:
            return EmptyValidatedPrefix(configured_chunks=configured_chunks)
        entries = tuple(dict(entry) for entry in candidate.get("entries") or ())
        records = tuple(dict(record) for record in candidate.get("records") or ())
        if len(entries) != len(records):
            raise RunStorageError("validated prefix entry/record counts differ")
        if int(candidate.get("validated_prefix_count", -1)) != len(entries):
            raise RunStorageError("validated prefix count does not match loaded raw entries")
        status = str(candidate.get("status", "")) or None
        terminal_merge_enabled = _terminal_merge_enabled(contract)
        review_unit = validate_review_prefix_metadata(
            configured_chunks=configured_chunks,
            validated_prefix_count=len(entries),
            terminal_merge_enabled=terminal_merge_enabled,
            terminal_pair_start=(
                configured_chunks - 1 if terminal_merge_enabled else None
            ),
            latest_review_unit=candidate.get("review_unit"),
            latest_revision_status=status,
            latest_effective_nonce=int(candidate.get("effective_reroll_nonce", 0)),
            latest_branch_regenerate_from=int(
                candidate.get("branch_regenerate_from", 0)
            ),
        )
        boundaries = tuple(
            (group.start, group.end)
            for group in physical_groups(
                chunks=configured_chunks,
                terminal_merge_enabled=terminal_merge_enabled,
            )
            if group.end <= len(entries)
        )
        if boundaries and boundaries[-1][1] != len(entries):
            raise RunStorageError("validated prefix ends inside a physical group")
        if entries and not boundaries:
            raise RunStorageError("validated prefix has no complete physical group")
        source_manifest = candidate.get("manifest")
        frozen_manifest = (
            None
            if source_manifest is None
            else MappingProxyType(copy.deepcopy(dict(source_manifest)))
        )
        revision_id = str(candidate.get("revision_id", "")) or None
        return ValidatedPrefix(
            entries=entries,
            records=records,
            manifest=frozen_manifest,
            revision_id=revision_id,
            status=status,
            review_unit=review_unit,
            effective_nonce=int(candidate.get("effective_reroll_nonce", 0)),
            branch_regenerate_from=int(candidate.get("branch_regenerate_from", 0)),
            physical_group_boundaries=boundaries,
            configured_chunks=configured_chunks,
        )

    def _load_validated_review_prefix(
        self,
        contract: dict[str, Any],
        *,
        resume_safe: bool,
    ) -> ValidatedPrefix | EmptyValidatedPrefix:
        """Select, fully validate, load, and freeze one branch-neutral prefix."""

        if self.review_generation_mode is None or self.review_action is None:
            raise RunStorageError("review execution intent is incomplete")
        candidate = None
        if self.take_action != TAKE_ACTION_AUTOMATIC:
            if self.review_generation_mode != GENERATION_MODE_REVIEW:
                raise RunStorageError("Take selection requires Review Each Chunk")
            if self.review_manual_regenerate_from:
                raise RunStorageError(
                    "Take selection cannot be combined with manual Regenerate From"
                )
            source_lineage = str(contract.get("nonce_lineage_sha256", ""))
            if "reference_group_contracts" in contract:
                _, all_takes, _ = self._provenance_catalog()
                selected_take = all_takes.get(self.take_revision_id)
                if selected_take is not None:
                    source_lineage = str(selected_take.get("lineage_sha256", ""))
            candidate = self._validated_take_selection(
                contract, source_lineage=source_lineage, resume_safe=resume_safe,
            )
            if source_lineage != str(contract.get("nonce_lineage_sha256", "")):
                source_manifest = candidate.get("manifest")
                if not isinstance(source_manifest, dict):
                    raise RunStorageError("selected Take source manifest is unavailable")
                source_contract = source_manifest.get("contract") or {}
                if _hash(source_contract.get("global")) != _hash(contract.get("global")):
                    raise RunStorageError("selected Take has a different common execution contract")
                manifests = self._read_manifests()
                source_chain = self._manifest_provenance_chain(source_manifest, manifests)
                selected_chain = candidate["chain"]
                if ([item["revision_id"] for item in source_chain[:len(selected_chain)]]
                        != [item["revision_id"] for item in selected_chain]):
                    raise RunStorageError("selected Take is not the source manifest's validated prefix")
                selected_end = int(candidate["validated_prefix_count"])
                try:
                    compatible_entries, compatible_records = self._compatible_plan_prefix(
                        source_manifest, contract, stop_before=selected_end + 1,
                    )
                except (OSError, ValueError) as exc:
                    raise RunStorageError(f"selected Take prefix cannot be imported: {exc}") from exc
                if (len(compatible_entries) != selected_end
                        or compatible_records != candidate["records"]):
                    failed_group = len(compatible_entries) + 1
                    raise RunStorageError(
                        f"selected Take is incompatible with the new Reference plan "
                        f"at physical group starting with chunk {failed_group}; "
                        "choose an earlier compatible Take or deselect Take and Regenerate From"
                    )
                candidate["entries"] = compatible_entries
                candidate["records"] = compatible_records
                candidate["selected_take_import"] = {
                    "revision_id": self.take_revision_id,
                    "physical_group": self.take_group,
                }
                self._plan_import = candidate
            else:
                self.selected_take_chain = list(candidate["chain"])
                self.selected_take_records = list(candidate["records"])
            self.selected_take_revision = dict(candidate)
        else:
            smart_only = self.review_action == REVIEW_ACTION_REGENERATE_CURRENT
            candidate = self.find_latest_review_head(
                contract,
                smart_regenerate_only=smart_only,
                resume_safe=resume_safe,
            )
            if candidate is None and not smart_only and resume_safe:
                self._plan_import = self._find_plan_import(
                    contract,
                    stop_before=self.review_manual_regenerate_from,
                    resume_safe=resume_safe,
                )
                candidate = self._plan_import
            if candidate is None and smart_only:
                details = "\n".join(self.notes[-6:]) or (
                    "No compatible saved review head was found."
                )
                raise ReviewControlError(
                    "Regenerate Current requires an existing reviewed unit. "
                    "The saved review could not be matched to this execution.\n"
                    + details
                )
        self.review_head = candidate
        self.inherited_review_unit = (
            None
            if candidate is None or candidate.get("review_unit") is None
            else dict(candidate["review_unit"])
        )
        frozen = self._freeze_validated_prefix(candidate, contract=contract)
        self.validated_prefix = frozen
        return frozen

    def _record_review_decision_created(self) -> None:
        created = int(self.review_runtime_metrics["review_decision_created"])
        if created != 0:
            raise RunStorageError("Review Decision was already created for this Queue")
        self.review_runtime_metrics["review_decision_created"] = 1

    def _resolve_review_contract(
        self,
        contract: dict[str, Any],
        *,
        requested_nonce: int,
        resume_safe: bool,
        validated_prefix: ValidatedPrefix | EmptyValidatedPrefix | None = None,
    ) -> tuple[dict[str, Any], int, str]:
        """Create the single Review Decision from an immutable validated prefix."""

        if self.review_generation_mode is None or self.review_action is None:
            raise RunStorageError("review execution intent is incomplete")
        if validated_prefix is None:
            validated_prefix = self._load_validated_review_prefix(
                contract,
                resume_safe=resume_safe,
            )
        if self.validated_prefix is None:
            self.validated_prefix = validated_prefix
        elif self.validated_prefix is not validated_prefix:
            raise RunStorageError(
                "Review Decision cannot replace the fixed ValidatedPrefix"
            )
        facts = validated_prefix.to_planning_facts()
        if self.take_action != TAKE_ACTION_AUTOMATIC:
            next_nonce = self._highest_lineage_nonce(
                str(contract["nonce_lineage_sha256"])
            ) + 1
            self._record_review_decision_created()
            execution = resolve_take_execution(
                take_action=self.take_action,
                configured_chunks=int(contract["chunk_count"]),
                selected_prefix_count=facts.accepted_chunks,
                terminal_merge_enabled=_terminal_merge_enabled(contract),
                terminal_pair_start=(
                    int(contract["chunk_count"]) - 1
                    if _terminal_merge_enabled(contract)
                    else None
                ),
                selected_review_unit=facts.review_unit,
                selected_effective_nonce=facts.effective_nonce,
                selected_branch_regenerate_from=facts.branch_regenerate_from,
                next_effective_nonce=next_nonce,
            )
            boundary = int(execution.effective_regenerate_from)
            effective_nonce = int(execution.requested_effective_nonce or 0)
            resolved = _apply_reroll_branch_contract(
                contract,
                boundary=boundary,
                requested_nonce=effective_nonce,
                effective_nonce=effective_nonce,
            )
            self.review_execution = execution
            self.pending_branch_cut = {
                "selected_revision_id": str(facts.revision_id),
                "after_physical_group": int(facts.review_unit.physical_group),
            }
            self.storage_revision_id_override = _storage_revision_identity(
                contract_sha256=revision_identity(resolved)[1],
                take_action=self.take_action,
                selected_revision_id=str(facts.revision_id),
                effective_nonce=effective_nonce,
                branch_boundary=boundary,
            )
            return resolved, effective_nonce, (
                "select_take" if self.take_action == TAKE_ACTION_USE else "branch_from_take"
            )
        semantics = (contract.get("global") or {}).get("execution_semantics") or {}
        terminal_merge_enabled = (
            semantics.get("flf_execution") == "terminal_merged_10s_seed_v2"
        )
        configured_chunks = int(contract["chunk_count"])
        self._record_review_decision_created()
        execution = resolve_review_execution(
            generation_mode=self.review_generation_mode,
            review_action=self.review_action,
            configured_chunks=configured_chunks,
            validated_prefix_count=facts.accepted_chunks,
            terminal_merge_enabled=terminal_merge_enabled,
            terminal_pair_start=(
                configured_chunks - 1 if terminal_merge_enabled else None
            ),
            manual_regenerate_from=self.review_manual_regenerate_from,
            run_storage_mode=RUN_STORAGE_SAVE_AUTO_RESUME,
            latest_review_unit=facts.review_unit,
            latest_revision_status=facts.status,
            latest_effective_nonce=facts.effective_nonce,
            latest_branch_regenerate_from=facts.branch_regenerate_from,
        )
        boundary = int(execution.effective_regenerate_from)
        if execution.requested_effective_nonce is None:
            draft = _apply_reroll_branch_contract(
                contract,
                boundary=boundary,
                requested_nonce=int(requested_nonce),
                effective_nonce=(int(requested_nonce) if boundary > 0 else 0),
            )
            effective_nonce, decision = self._resolve_effective_nonce(
                draft,
                requested_nonce=int(requested_nonce),
                resume_safe=resume_safe,
            )
            applied_requested_nonce = int(requested_nonce)
        else:
            effective_nonce = int(execution.requested_effective_nonce)
            applied_requested_nonce = effective_nonce
            decision = str(execution.nonce_policy)
        resolved = _apply_reroll_branch_contract(
            contract,
            boundary=boundary,
            requested_nonce=applied_requested_nonce,
            effective_nonce=effective_nonce,
        )
        self.review_execution = execution
        return resolved, effective_nonce, decision

    def _resolve_effective_nonce(
        self, contract: dict[str, Any], *, requested_nonce: int, resume_safe: bool,
    ) -> tuple[int, str]:
        boundary = int(contract["reroll_from_chunk"])
        requested = int(requested_nonce)
        if boundary <= 0:
            return 0, "inactive"
        if requested >= 1:
            return requested, "explicit"
        lineage = str(contract["nonce_lineage_sha256"])
        request = str(contract["nonce_request_sha256"])
        highest = 0
        matching: dict[int, dict[str, Any]] = {}
        if self.revisions_root.exists():
            for path in self.revisions_root.glob("*/manifest.json"):
                try:
                    manifest = _read_json(path)
                    lifecycle = manifest.get("nonce_lifecycle") or (manifest.get("contract") or {}).get("nonce_lifecycle") or {}
                    if str(lifecycle.get("lineage_sha256", "")) != lineage:
                        continue
                    nonce = int(lifecycle.get("effective_nonce", 0))
                    highest = max(highest, nonce)
                    if str(lifecycle.get("request_sha256", "")) == request:
                        current = matching.get(nonce)
                        if current is None or str(manifest.get("updated_utc", "")) >= str(current.get("updated_utc", "")):
                            matching[nonce] = manifest
                except Exception:
                    continue
        if resume_safe and matching:
            latest_nonce = max(matching)
            latest = matching[latest_nonce]
            if latest_nonce == highest and str(latest.get("status", "")) != "complete":
                return latest_nonce, "resume_interrupted"
        return highest + 1, "new_revision"

    def prepare(
        self, *, model: Any, model_fingerprint_value: str, clip: Any,
        video_vae: Any, sampler: Any,
        sigmas: torch.Tensor, prompt_plan: dict[str, Any], width: int,
        height: int, chunk_seconds: float, continuity: str,
        audio_continuity: bool, base_seed: int, reroll_from_chunk: int,
        reroll_nonce: int, first_frame_hash: str, last_frame_hash: str,
        identity_hash: str, strict_compatibility: bool,
        existing_session: dict[str, Any] | None,
        reference_contract: dict[str, Any] | None = None,
        conditioning_mode: str | None = None,
        reference_audio_contract: dict[str, Any] | None = None,
        reference_audio_vae: Any = None,
        driving_audio_contract: dict[str, Any] | None = None,
        driving_audio_vae: Any = None,
        reference_video_contract: dict[str, Any] | None = None,
        timeline_video_contract: dict[str, Any] | None = None,
        guide_contract: dict[str, Any] | None = None,
        execution_semantics: dict[str, Any] | None = None,
        reference_storage_plan: ReferenceStoragePlan | None = None,
    ) -> dict[str, Any] | None:
        if existing_session is not None:
            raise RunStorageError("Run Storage cannot be combined with an explicit Session")
        self.prompts = [str(value) for value in prompt_plan["prompts"]]
        from .graph_contract import build_upstream_graph_contract
        graph_contract, graph_safe, graph_reasons = build_upstream_graph_contract(
            self.prompt_graph,
            self.sampler_node_id,
            require_video_vae=(
                reference_storage_plan is not None
                or
                conditioning_mode_uses_video_vae(str(conditioning_mode))
                or reference_video_contract is not None
                or timeline_video_contract is not None
                or guide_contract is not None
            ),
            require_reference_audio_vae=reference_audio_contract is not None,
            reference_audio_route=(
                "audio_references"
                if "reference_audio_bundle_contract_version" in (reference_audio_contract or {})
                else "reference_audio_vae"
            ),
            require_audio_vae=driving_audio_contract is not None,
        )
        contract, safe, reasons = build_sampling_contract(
            model=model, model_fingerprint_value=model_fingerprint_value,
            clip=clip, video_vae=video_vae,
            sampler=sampler, sigmas=sigmas, prompt_plan=prompt_plan,
            width=width, height=height, chunk_seconds=chunk_seconds,
            continuity=continuity, audio_continuity=audio_continuity,
            base_seed=base_seed, reroll_from_chunk=reroll_from_chunk,
            reroll_nonce=reroll_nonce, first_frame_hash=first_frame_hash,
            last_frame_hash=last_frame_hash,
            strict_compatibility=strict_compatibility,
            reference_contract=reference_contract,
            conditioning_mode=conditioning_mode,
            upstream_graph_contract=graph_contract,
            upstream_graph_safe=graph_safe,
            upstream_graph_reasons=graph_reasons,
            reference_audio_contract=reference_audio_contract,
            reference_audio_vae=reference_audio_vae,
            driving_audio_contract=driving_audio_contract,
            driving_audio_vae=driving_audio_vae,
            reference_video_contract=reference_video_contract,
            timeline_video_contract=timeline_video_contract,
            guide_contract=guide_contract,
            execution_semantics=execution_semantics,
            reference_storage_plan=reference_storage_plan,
        )
        self.contract = contract
        if self.review_generation_mode is not None or self.review_action is not None:
            validated_prefix = self._load_validated_review_prefix(
                contract,
                resume_safe=safe,
            )
            contract, effective_nonce, nonce_decision = self._resolve_review_contract(
                contract,
                requested_nonce=int(reroll_nonce),
                resume_safe=safe,
                validated_prefix=validated_prefix,
            )
        else:
            if safe:
                self._plan_import = self._find_plan_import(
                    contract, stop_before=int(reroll_from_chunk),
                )
            inherited_import = self._plan_import is not None and int(reroll_from_chunk) == 0
            requested = (self._plan_import["effective_reroll_nonce"]
                         if inherited_import else int(reroll_nonce))
            if inherited_import:
                contract = self._plan_import["contract"]
            effective_nonce, nonce_decision = self._resolve_effective_nonce(
                contract, requested_nonce=requested, resume_safe=safe,
            )
            contract = _apply_nonce_contract(
                contract, requested_nonce=requested, effective_nonce=effective_nonce,
            )
        self.resume_safe = bool(safe)
        self.effective_reroll_nonce = int(effective_nonce)
        self.nonce_decision = nonce_decision
        if not safe:
            contract = dict(contract)
            contract["reuse_policy"] = "disabled_unobservable_contract"
            contract["execution_nonce"] = uuid.uuid4().hex
            self.disabled_reasons = reasons
        self.contract = contract
        sampling_revision_id, self.contract_sha256 = revision_identity(contract)
        # A selected, shorter canonical Take is not interchangeable with an old
        # longer revision having the same sampling inputs. Continue in its own
        # storage revision when the contract is unchanged; preserve old Takes.
        head_manifest = (self.review_head or {}).get("manifest")
        if (not self.storage_revision_id_override and self._plan_import is None
                and isinstance(head_manifest, dict)
                and head_manifest.get("contract_sha256") == self.contract_sha256):
            self.storage_revision_id_override = str(head_manifest["revision_id"])
        self.revision_id = self.storage_revision_id_override or _storage_revision_identity(
            contract_sha256=self.contract_sha256,
            take_action=TAKE_ACTION_AUTOMATIC,
            selected_revision_id="",
            effective_nonce=int(effective_nonce),
            branch_boundary=int(contract.get("reroll_from_chunk", 0)),
        )

        self.revision_root = self.revisions_root / self.revision_id
        self.revision_root.mkdir(parents=True, exist_ok=True)
        exact = None
        if self._manifest_path().exists():
            try:
                exact = _read_json(self._manifest_path())
            except Exception as exc:
                self.notes.append(f"exact manifest rejected: {exc}")
            if exact is not None and exact.get("contract_sha256") != self.contract_sha256:
                raise RunStorageError(f"short revision id collision: {self.revision_id}")

        hashes = list(contract["chunk_contract_hashes"])
        best_entries: list[dict[str, Any]] = []
        best_records: list[dict[str, Any]] = []
        review_queue = self.review_generation_mode is not None or self.review_action is not None
        if exact is not None and not review_queue:
            self._plan_import = None
        if review_queue:
            if self.validated_prefix is None:
                raise RunStorageError("Review Decision has no fixed ValidatedPrefix")
            if self.validated_prefix.entries and not _reusable_sampling_contract(contract, resume_safe=safe):
                raise RunStorageError("Review prefix has no reusable Sampling v6 identity")
            best_entries = list(self.validated_prefix.entries)
            best_records = list(self.validated_prefix.records)
            if self._plan_import is not None:
                # Imported raw tensors become records owned by the new plan only
                # after the initial manifest has been created.
                best_records = []
            execution = self.review_execution
            if execution is None:
                raise RunStorageError("Review Decision was not created")
            if bool(execution.smart_regenerate) or self.review_manual_regenerate_from:
                reusable = max(0, int(execution.effective_regenerate_from) - 1)
                best_entries = best_entries[:reusable]
                if self._plan_import is None:
                    best_records = best_records[:reusable]
        elif self._plan_import is not None:
            best_entries = list(self._plan_import["entries"])
            best_records = []  # Populated with new-plan-owned copies after manifest creation.
        else:
            candidates = [exact] if exact is not None and safe else []
            if safe and exact is None and self.revisions_root.exists():
                if isinstance(head_manifest, dict):
                    candidates.append(head_manifest)
                else:
                    candidates.extend(self._read_manifests().values())
            candidates.sort(key=lambda m: (len(m.get("chunks") or []),
                int((m.get("branch_provenance") or {}).get("canonical_sequence", 0))), reverse=True)
            for candidate in candidates:
                if not _reusable_sampling_contract(contract, resume_safe=safe) or not _reusable_manifest(candidate):
                    self.notes.append(f"stored revision {candidate.get('revision_id', '')} is read-only or unobservable")
                    continue
                if len(candidate.get("chunks") or []) <= len(best_entries):
                    continue
                if int(candidate.get("run_storage_schema_version", -1)) not in RUN_STORAGE_READABLE_SCHEMA_VERSIONS:
                    continue
                if (
                    int(candidate.get("run_storage_schema_version", -1))
                    == RUN_STORAGE_SCHEMA_VERSION
                    and candidate.get("branch_provenance")
                ):
                    try:
                        entries, records = self._valid_provenance_prefix(
                            candidate,
                            current_contract=contract,
                            enforce_sampling_contract=True,
                        )
                    except Exception as exc:
                        self.notes.append(
                            f"provenance prefix {candidate.get('revision_id', '')} rejected: {exc}"
                        )
                        continue
                else:
                    entries, records = self._valid_prefix(candidate, hashes)
                if len(entries) > len(best_entries):
                    best_entries, best_records = entries, records

        self.reused_count = len(best_entries)
        now = _now()
        self.manifest = {
            "run_storage_schema_version": RUN_STORAGE_SCHEMA_VERSION,
            "sampling_contract_version": SAMPLING_CONTRACT_VERSION,
            "run_name": self.run_name,
            "revision_id": self.revision_id,
            "sampling_revision_id": sampling_revision_id,
            "contract_sha256": self.contract_sha256,
            "contract": contract,
            "resume_safe": bool(safe),
            "resume_disabled_reasons": list(reasons),
            "nonce_lifecycle": dict(contract["nonce_lifecycle"]),
            "status": "in_progress",
            "created_utc": (exact or {}).get("created_utc", now),
            "updated_utc": now,
            "chunks": best_records,
            "report_summary": (exact or {}).get("report_summary", ""),
        }
        if reference_storage_plan is not None:
            self.manifest["reference_routing_audit"] = (
                (exact or {}).get("reference_routing_audit")
                or reference_storage_plan.audit()
            )
        if exact is not None and isinstance(exact.get("prefix_import"), dict):
            self.manifest["prefix_import"] = dict(exact["prefix_import"])
        if self.selected_take_chain:
            self.manifest["branch_provenance"] = {
                "version": BRANCH_PROVENANCE_VERSION,
                "active_chain": [
                    item["revision_id"] for item in self.selected_take_chain
                ],
                "selection": {
                    "action": self.take_action,
                    "revision_id": self.take_revision_id,
                    "physical_group": self.take_group,
                },
                "branch_cut": dict(self.pending_branch_cut or {}),
            }
        if self.review_execution is not None:
            self.manifest.update(
                review_control_version=REVIEW_CONTROL_VERSION,
                branch_regenerate_from=int(contract["reroll_from_chunk"]),
                effective_reroll_nonce=int(effective_nonce),
            )
        self._write_manifest()
        if self._plan_import is not None:
            best_records = self._adopt_plan_prefix(self._plan_import)
            self._plan_import = None
        self._write_project()
        if not best_entries:
            return None
        session_settings = _resume_session_settings(
            contract=contract,
            revision_id=self.revision_id,
            first_frame_hash=first_frame_hash,
            last_frame_hash=last_frame_hash,
            reference_storage_plan=reference_storage_plan,
            accepted_chunks=len(best_entries),
        )
        return make_session(
            chunks=best_entries, width=int(width), height=int(height),
            chunk_seconds=float(chunk_seconds), identity_hash=str(identity_hash),
            model_fingerprint_value=str(model_fingerprint_value),
            parent_session_id=None, reroll_from_chunk=0,
            settings=session_settings,
        )

    def mark_review_group(
        self,
        *,
        start: int,
        end: int,
        physical_group: int,
    ) -> None:
        """Record an atomic group only after every logical commit has succeeded."""

        execution = self.review_execution
        if execution is None or self.review_generation_mode != GENERATION_MODE_REVIEW:
            return
        actual = (int(start), int(end), int(physical_group))
        if execution.max_new_physical_groups is not None:
            expected = (
                execution.next_review_unit_start,
                execution.next_review_unit_end,
                execution.next_review_physical_group,
            )
            if expected != actual:
                raise RunStorageError(
                    f"completed review group {actual} does not match resolved unit {expected}"
                )
            if self.pending_review_pause_metadata is not None:
                raise RunStorageError(
                    "more than one review group completed in one execution"
                )
        self.pending_review_pause_metadata = make_review_pause_metadata(
            ReviewUnit(
                start=actual[0],
                end=actual[1],
                physical_group=actual[2],
            )
        )

    def review_pause_metadata(self) -> dict[str, Any] | None:
        if self.review_generation_mode != GENERATION_MODE_REVIEW:
            return None
        if self.pending_review_pause_metadata is not None:
            return dict(self.pending_review_pause_metadata)
        if self.review_execution is None or self.inherited_review_unit is None:
            return None
        unit = self.inherited_review_unit
        return make_review_pause_metadata(
            ReviewUnit(
                start=int(unit["start"]),
                end=int(unit["end"]),
                physical_group=int(unit["physical_group"]),
            )
        )

    def commit_chunk(self, entry: dict[str, Any], *, position: int) -> None:
        """Compatibility entry point for one-logical-chunk physical groups."""

        self.commit_group((entry,), positions=(position,))

    def commit_group(
        self,
        entries: tuple[dict[str, Any], ...] | list[dict[str, Any]],
        *,
        positions: tuple[int, ...] | list[int],
    ) -> None:
        """Durably publish one complete physical group with one manifest switch."""

        if self.manifest is None or self.revision_root is None:
            return
        entry_values = tuple(entries)
        position_values = tuple(positions)
        if not entry_values or len(entry_values) != len(position_values):
            raise RunStorageError(
                "Run Storage physical group entries and positions must be non-empty and equal"
            )
        if any(
            isinstance(position, bool) or not isinstance(position, int)
            for position in position_values
        ):
            raise RunStorageError("Run Storage chunk positions must be integers")
        expected = int((self.contract or {}).get("chunk_count", 0))
        if any(position < 0 or position >= expected for position in position_values):
            raise RunStorageError(
                "Run Storage physical group position is outside "
                f"0..{expected - 1}: {position_values}"
            )
        groups = physical_groups(
            chunks=expected,
            terminal_merge_enabled=_terminal_merge_enabled(self.contract or {}),
        )
        matched_group = next(
            (
                group
                for group in groups
                if position_values == tuple(range(group.start - 1, group.end))
            ),
            None,
        )
        if matched_group is None:
            raise RunStorageError(
                "Run Storage physical group is incomplete or crosses a group boundary: "
                f"{position_values}"
            )
        validated_entries = tuple(
            validate_chunk_entry(entry) for entry in entry_values
        )
        existing_records = list(self.manifest.get("chunks") or [])
        first_position = position_values[0]
        if len(existing_records) < first_position:
            raise RunStorageError(
                "Run Storage cannot commit physical group starting at chunk "
                f"{first_position + 1} before chunk {first_position}"
            )
        chunks_root = self.revision_root / "chunks"
        chunks_root.mkdir(parents=True, exist_ok=True)
        revision_id = str(self.revision_id or "")
        if not revision_id or not re.fullmatch(r"[A-Za-z0-9._-]+", revision_id):
            raise RunStorageError("Run Storage revision id is invalid for raw storage")
        transaction_id = uuid.uuid4().hex
        new_records: list[dict[str, Any]] = []
        for validated, position in zip(
            validated_entries, position_values, strict=True
        ):
            filename = (
                f"rev-{revision_id}-txn-{transaction_id}-"
                f"chunk-{position + 1:04d}.safetensors"
            )
            target = chunks_root / filename
            temporary = chunks_root / f".{filename}.{uuid.uuid4().hex}.tmp"
            if target.exists():
                raise RunStorageError(
                    f"immutable Run Storage raw already exists: {filename}"
                )
            tensors = {
                "video": validated["video"].detach().to("cpu").contiguous(),
                "audio": validated["audio"].detach().to("cpu").contiguous(),
            }
            try:
                save_file(tensors, str(temporary), metadata={
                    "h3_continuum_run_storage": str(RUN_STORAGE_SCHEMA_VERSION),
                    "revision_id": revision_id,
                    "chunk_number": str(position + 1),
                })
                _fsync_file(temporary)
                os.replace(temporary, target)
            finally:
                if temporary.exists():
                    temporary.unlink()
            file_size = target.stat().st_size
            file_sha256 = _file_sha256(target)
            with safe_open(str(target), framework="pt", device="cpu") as handle:
                if set(handle.keys()) != {"audio", "video"}:
                    raise RunStorageError(
                        f"persisted physical group tensors are invalid: {filename}"
                    )
                metadata = handle.metadata() or {}
                if (
                    metadata.get("h3_continuum_run_storage")
                    != str(RUN_STORAGE_SCHEMA_VERSION)
                    or metadata.get("revision_id") != revision_id
                    or metadata.get("chunk_number") != str(position + 1)
                ):
                    raise RunStorageError(
                        f"persisted physical group metadata is invalid: {filename}"
                    )
            if (
                target.stat().st_size != file_size
                or _file_sha256(target) != file_sha256
            ):
                raise RunStorageError(
                    f"persisted physical group SHA-256 verification failed: {filename}"
                )
            storage_entry = dict(validated)
            storage_entry["sequence_index"] = position
            new_records.append({
                "sequence_index": position,
                "storage_revision_id": revision_id,
                "filename": filename,
                "file_size": file_size,
                "file_sha256": file_sha256,
                "entry": _entry_metadata(storage_entry),
            })
        _fsync_dir(chunks_root)
        records = existing_records[:first_position]
        records.extend(new_records)
        candidate_manifest = dict(self.manifest)
        candidate_manifest.update(
            chunks=records,
            updated_utc=_now(),
            status="in_progress",
        )
        # Assign only after every raw in the physical group is complete and
        # verified. __exit__ may then recover this complete candidate after a
        # catchable manifest-write exception, preserving the R0 contract.
        self.manifest = candidate_manifest
        self._write_manifest()
        self.generated_count += len(new_records)

    def summary(self, *, detailed: bool = False) -> str:
        total = int((self.contract or {}).get("chunk_count", 0))
        resume = self.reused_count + 1 if self.reused_count < total else "complete"
        policy = (" auto-resume disabled: " + "; ".join(self.disabled_reasons) + ".") if self.disabled_reasons else ""
        shown_notes = self.notes if detailed else list(dict.fromkeys(self.notes))[:3]
        note = (" " + " ".join(shown_notes)) if shown_notes else ""
        if not detailed and len(self.notes) > len(shown_notes):
            note += f" ({len(self.notes) - len(shown_notes)} additional diagnostics; enable Detailed Report.)"
        basic = (
            f"Run Storage: {self.run_name} / revision {self.revision_id}; "
            f"{self.reused_count} reused, {self.generated_count} generated, "
            f"{total} total; resume={resume}; nonce={self.effective_reroll_nonce} "
            f"({self.nonce_decision}).{policy}{note}"
        )
        if not detailed or self.manifest is None:
            return basic
        records = list(self.manifest.get("chunks") or [])
        lines = [basic, f"Run Storage path: {self.revision_root}",
                 "Run Storage I/O: " + _canonical(self.io_metrics)]
        for record in records:
            lines.append(
                f"stored chunk {int(record['sequence_index']) + 1}: "
                f"{record['storage_revision_id']}/chunks/{record['filename']} "
                f"({int(record['file_size']) / (1024.0 ** 2):.1f} MiB)"
            )
        try:
            free_gib = shutil.disk_usage(self.run_root).free / (1024.0 ** 3)
            lines.append(f"Run Storage free disk: {free_gib:.2f} GiB")
        except OSError:
            lines.append("Run Storage free disk: unknown")
        first_invalid = self.reused_count + 1 if self.reused_count < total else "none"
        lines.append(f"Run Storage first regenerated chunk: {first_invalid}")
        return "\n".join(lines)

    def finalize(
        self,
        *,
        session: dict[str, Any],
        report: str,
        review_pause_metadata: dict[str, Any] | None = None,
    ) -> None:
        if self.manifest is None:
            return
        expected = int((self.contract or {}).get("chunk_count", 0))
        records = list(self.manifest.get("chunks") or [])
        entries, accepted = self._valid_prefix(
            self.manifest,
            list((self.contract or {}).get("chunk_contract_hashes") or []),
            current_contract=self.contract,
        )
        if len(accepted) != len(records):
            raise RunStorageError("Run Storage finalize rejected the committed prefix")
        completed = len(entries)
        if completed > expected:
            raise RunStorageError("Run Storage finalize found too many committed chunks")
        session_chunks = list(session.get("chunks") or [])
        if len(session_chunks) != completed:
            raise RunStorageError(
                "Run Storage finalize session does not match the committed prefix"
            )

        canonical_pause = None
        if review_pause_metadata is not None:
            value = review_pause_metadata.get("review_unit")
            if not isinstance(value, dict):
                raise RunStorageError("review pause metadata is missing review_unit")
            canonical_pause = make_review_pause_metadata(
                ReviewUnit(
                    start=int(value.get("start", 0)),
                    end=int(value.get("end", 0)),
                    physical_group=int(value.get("physical_group", 0)),
                )
            )
            if review_pause_metadata.get("review_pause_reason") != canonical_pause[
                "review_pause_reason"
            ]:
                raise RunStorageError("review pause reason is invalid")
            semantics = (self.contract or {}).get("global", {}).get(
                "execution_semantics"
            ) or {}
            terminal_merge_enabled = (
                semantics.get("flf_execution") == "terminal_merged_10s_seed_v2"
            )
            candidate_status = (
                REVISION_STATUS_COMPLETE
                if completed == expected
                else REVISION_STATUS_REVIEW_READY
            )
            try:
                validate_review_prefix_metadata(
                    configured_chunks=expected,
                    validated_prefix_count=completed,
                    terminal_merge_enabled=terminal_merge_enabled,
                    terminal_pair_start=(
                        expected - 1 if terminal_merge_enabled else None
                    ),
                    latest_review_unit=canonical_pause["review_unit"],
                    latest_revision_status=candidate_status,
                    latest_effective_nonce=int(self.effective_reroll_nonce),
                    latest_branch_regenerate_from=int(
                        (self.contract or {}).get("reroll_from_chunk", 0)
                    ),
                )
            except ReviewControlError as exc:
                raise RunStorageError(f"review pause metadata is invalid: {exc}") from exc

        status = REVISION_STATUS_COMPLETE if completed == expected else REVISION_STATUS_INTERRUPTED
        intentional_review_pause = (
            completed < expected
            and canonical_pause is not None
            and self.review_execution is not None
            and self.review_execution.max_new_physical_groups is not None
            and (
                self.pending_review_pause_metadata is not None
                or self.review_execution.max_new_physical_groups == 0
            )
        )
        if intentional_review_pause:
            status = REVISION_STATUS_REVIEW_READY

        for key in ("review_unit", "review_pause_reason"):
            self.manifest.pop(key, None)
        if canonical_pause is not None and status in {
            REVISION_STATUS_REVIEW_READY,
            REVISION_STATUS_COMPLETE,
        }:
            self.manifest.update(canonical_pause)
        if self.review_execution is not None:
            self.manifest.update(
                review_control_version=REVIEW_CONTROL_VERSION,
                branch_regenerate_from=int(
                    (self.contract or {}).get("reroll_from_chunk", 0)
                ),
                effective_reroll_nonce=int(self.effective_reroll_nonce),
            )
        self.manifest.pop("last_error", None)
        pending_provenance = dict(self.manifest.pop("branch_provenance", {}) or {})
        self.manifest.update(
            status=status, updated_utc=_now(),
            session_id=str(session.get("session_id", "")),
            report_summary=str(report)[-8192:],
        )
        self._write_manifest()
        manifests = self._read_manifests()
        try:
            active_chain = self._manifest_provenance_chain(self.manifest, manifests)
        except (BranchProvenanceError, RunStorageError) as exc:
            raise RunStorageError(
                f"finalized Branch Provenance Contract is invalid: {exc}"
            ) from exc
        canonical_sequence = 1 + max(
            (
                int((value.get("branch_provenance") or {}).get("canonical_sequence", 0))
                for value in manifests.values()
            ),
            default=0,
        )
        provenance = pending_provenance
        provenance.update(
            version=BRANCH_PROVENANCE_VERSION,
            active_chain=[item["revision_id"] for item in active_chain],
            canonical_committed_utc=_now(),
            canonical_sequence=canonical_sequence,
        )
        if self.pending_branch_cut is not None:
            provenance["branch_cut"] = dict(self.pending_branch_cut)
        self.manifest["branch_provenance"] = provenance
        self._write_manifest()
        self._write_project(set_canonical=True)


def get_active_run_storage() -> RunStorageController | None:
    return _ACTIVE.get()


def run_storage_scope(
    run_name: str, *, prompt: Any = None, unique_id: Any = None
) -> RunStorageController:
    controller = RunStorageController(run_name)
    controller.set_prompt_graph(prompt, unique_id)
    return controller
