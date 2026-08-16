"""Crash-safe V3.1B raw-latent storage and deterministic auto-resume."""

from __future__ import annotations

import contextvars
import hashlib
import json
import marshal
import os
import re
import shutil
import socket
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
from safetensors import safe_open
from safetensors.torch import save_file

from .constants import CONTINUUM_ACTUAL_PREFIX_STEPS
from .v2.session import make_session, validate_chunk_entry


RUN_STORAGE_SCHEMA_VERSION = 2
from .conditioning import (
    CONDITIONING_MODES,
    conditioning_mode_from_presence,
    conditioning_mode_uses_video_vae,
)


SAMPLING_CONTRACT_VERSION = 5
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


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
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


def _tensor_probe(tensor: torch.Tensor) -> dict[str, Any]:
    flat = tensor.detach().reshape(-1)
    count = int(flat.numel())
    positions = sorted({0, count // 4, count // 2, 3 * count // 4, count - 1}) if count else []
    if positions:
        index = torch.tensor(positions, device=flat.device)
        sample = flat[index].contiguous().cpu().view(torch.uint8).numpy().tobytes()
    else:
        sample = b""
    return {
        "shape": list(tensor.shape),
        "dtype": str(tensor.dtype),
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
        result: dict[str, Any] = {}
        safe = True
        for key in sorted(value, key=lambda item: str(item)):
            observed, item_safe = _observe(value[key], depth=depth + 1)
            result[str(key)] = observed
            safe = safe and item_safe
        return result, safe
    if isinstance(value, (list, tuple)):
        result = []
        safe = True
        for item in value:
            observed, item_safe = _observe(item, depth=depth + 1)
            result.append(observed)
            safe = safe and item_safe
        return result, safe
    if callable(value):
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
        elif hasattr(value, "__dict__"):
            attributes, safe = _observe(vars(value), depth=depth + 1)
            descriptor["attributes"] = attributes
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
    transformer = options.get("transformer_options", {}) or {}
    transformer_values = {
        str(key): transformer[key]
        for key in transformer
        if key not in {"h3_continuum_join_context"}
    }
    observed_transformer, transformer_safe = _observe(transformer_values)
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
        "transformer_options": observed_transformer,
        "patches": patches,
        "weight_probe": weights,
        "runtime_observation": {
            "wrappers_complete": bool(wrappers_safe),
            "patches_complete": bool(patches_safe),
            "transformer_options_complete": bool(transformer_safe),
        },
    }
    return descriptor, weights_safe and bool(weights)


def _sampler_signature(sampler: Any) -> tuple[dict[str, Any], bool]:
    function = getattr(sampler, "sampler_function", None)
    observed, safe = _observe({
        "extra_options": getattr(sampler, "extra_options", {}) or {},
        "inpaint_options": getattr(sampler, "inpaint_options", {}) or {},
    })
    return {
        "type": _qualified(sampler),
        "function": _qualified(function) if function is not None else "unknown",
        "options": observed,
    }, function is not None and safe


def _module_signature(module: Any) -> tuple[dict[str, Any], bool]:
    descriptor: dict[str, Any] = {"type": _qualified(module)}
    if module is None or not hasattr(module, "named_parameters"):
        descriptor["error"] = "named_parameters unavailable"
        return descriptor, False
    try:
        parameters = list(module.named_parameters())
    except Exception as exc:
        descriptor["error"] = f"named_parameters failed: {type(exc).__name__}"
        return descriptor, False
    layout = [
        {
            "name": str(name),
            "shape": list(parameter.shape),
            "dtype": str(parameter.dtype),
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
            probes.append({"name": str(name), **_tensor_probe(parameter)})
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
    timeline_video_contract: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], bool, list[str]]:
    model_value, model_safe = _model_signature(model, model_fingerprint_value)
    clip_value, clip_safe = _clip_signature(clip)
    inferred_mode = conditioning_mode_from_presence(
        has_first=str(first_frame_hash).lower() not in {"", "none", "null"},
        has_last=str(last_frame_hash).lower() not in {"", "none", "null"},
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
        conditioning_mode_uses_video_vae(conditioning_mode)
        or timeline_video_contract is not None
    )
    if uses_video_vae:
        video_vae_value, video_vae_safe = _video_vae_signature(
            video_vae, required=True
        )
    else:
        video_vae_value, video_vae_safe = None, True
    sampler_value, sampler_safe = _sampler_signature(sampler)
    if reference_audio_contract is not None:
        audio_vae_value, audio_vae_safe = _audio_vae_signature(reference_audio_vae)
    else:
        audio_vae_value, audio_vae_safe = None, True
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
    global_contract = {
        "sampling_contract_version": SAMPLING_CONTRACT_VERSION,
        "conditioning_mode": conditioning_mode,
        "model": model_value,
        "clip": clip_value,
        "sampler": sampler_value,
        "sigmas": _tensor_exact(sigmas),
        "width": int(width), "height": int(height),
        "chunk_seconds": float(chunk_seconds),
        "continuity": str(continuity),
        "audio_continuity": bool(audio_continuity),
        "base_seed": int(base_seed),
        "strict_compatibility": bool(strict_compatibility),
        "continuum_interop_api": 1,
        "actual_prefix_steps": CONTINUUM_ACTUAL_PREFIX_STEPS,
    }
    if graph_authoritative:
        global_contract["upstream_graph"] = dict(upstream_graph_contract)
    if uses_video_vae:
        global_contract["video_vae"] = video_vae_value
    if conditioning_mode in {"i2va", "fl2va"}:
        global_contract["first_frame_hash"] = str(first_frame_hash)
    if reference_contract is not None:
        global_contract["reference"] = dict(reference_contract)
    if reference_audio_contract is not None:
        global_contract["reference_audio"] = dict(reference_audio_contract)
        global_contract["reference_audio_vae"] = audio_vae_value
    timeline_chunk_contracts = []
    if timeline_video_contract is not None:
        timeline_value = dict(timeline_video_contract)
        timeline_chunk_contracts = list(timeline_value.pop("chunk_slices", []))
        if len(timeline_chunk_contracts) != chunks:
            raise RunStorageError(
                "Timeline Video contract does not match the configured chunk count"
            )
        global_contract["timeline_video"] = timeline_value
    lineage_sha256 = _hash({
        "global_hash": _hash(global_contract),
        "chunk_count": chunks,
        "prompt_mode": str(prompt_plan["mode"]),
        "prompt_hashes": prompt_hashes,
        "last_frame_hash": str(last_frame_hash),
        "timeline_video_chunk_contracts": timeline_chunk_contracts,
    })
    contract = {
        "global": global_contract,
        "chunk_count": chunks,
        "prompt_mode": str(prompt_plan["mode"]),
        "prompt_hashes": prompt_hashes,
        "reroll_from_chunk": boundary,
        "last_frame_hash": str(last_frame_hash),
        "nonce_lineage_sha256": lineage_sha256,
        "nonce_request_sha256": _hash({
            "lineage_sha256": lineage_sha256,
            "reroll_from_chunk": boundary,
        }),
    }
    contract = _apply_nonce_contract(
        contract,
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
    graph_safe = bool(upstream_graph_safe) if graph_authoritative else True
    return contract, model_safe and clip_safe and video_vae_safe and audio_vae_safe and sampler_safe and graph_safe, reasons


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

    def set_prompt_graph(self, prompt: Any, unique_id: Any) -> None:
        self.prompt_graph = prompt if isinstance(prompt, dict) else None
        self.sampler_node_id = None if unique_id is None else str(unique_id)

    def __enter__(self) -> "RunStorageController":
        self.lock.acquire()
        self.context_token = _ACTIVE.set(self)
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        try:
            if exc is not None and self.manifest is not None:
                self.manifest.update(status="interrupted", updated_utc=_now(), last_error=f"{type(exc).__name__}: {exc}"[:2048])
                self._write_manifest()
        finally:
            if self.context_token is not None:
                _ACTIVE.reset(self.context_token)
                self.context_token = None
            self.lock.release()

    def _manifest_path(self) -> Path:
        if self.revision_root is None:
            raise RunStorageError("Run Storage revision is not prepared")
        return self.revision_root / "manifest.json"

    def _write_manifest(self) -> None:
        if self.manifest is not None:
            _write_json(self._manifest_path(), self.manifest)

    def _write_project(self) -> None:
        revisions = []
        if self.revisions_root.exists():
            for path in sorted(self.revisions_root.glob("*/manifest.json")):
                try:
                    value = _read_json(path)
                    lifecycle = value.get("nonce_lifecycle") or {}
                    revision = {key: value.get(key) for key in ("revision_id", "contract_sha256", "status", "updated_utc", "resume_safe")}
                    revision.update(
                        nonce_mode=lifecycle.get("mode"),
                        effective_reroll_nonce=lifecycle.get("effective_nonce"),
                        reroll_from_chunk=(value.get("contract") or {}).get("reroll_from_chunk"),
                    )
                    revisions.append(revision)
                except Exception:
                    continue
        _write_json(self.run_root / "project.json", {
            "run_storage_schema_version": RUN_STORAGE_SCHEMA_VERSION,
            "run_name": self.run_name, "updated_utc": _now(), "revisions": revisions,
        })

    def _load_entry(self, record: dict[str, Any], prompt: str) -> dict[str, Any]:
        source = str(record["storage_revision_id"])
        filename = str(record["filename"])
        if Path(filename).name != filename:
            raise RunStorageError("stored chunk filename is invalid")
        path = self.revisions_root / source / "chunks" / filename
        if path.stat().st_size != int(record["file_size"]):
            raise RunStorageError(f"stored chunk size mismatch: {filename}")
        expected_sha256 = str(record.get("file_sha256", ""))
        if not expected_sha256:
            raise RunStorageError(f"stored chunk SHA-256 is missing: {filename}")
        if _file_sha256(path) != expected_sha256:
            raise RunStorageError(f"stored chunk SHA-256 mismatch: {filename}")
        with safe_open(str(path), framework="pt", device="cpu") as handle:
            if set(handle.keys()) != {"audio", "video"}:
                raise RunStorageError(f"stored chunk tensors are invalid: {filename}")
            video, audio = handle.get_tensor("video"), handle.get_tensor("audio")
        entry = dict(record["entry"])
        entry.update(prompt=str(prompt), video=video, audio=audio, reused=False)
        return validate_chunk_entry(entry)

    def _valid_prefix(self, manifest: dict[str, Any], hashes: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        stored = list((manifest.get("contract") or {}).get("chunk_contract_hashes") or [])
        records = list(manifest.get("chunks") or [])
        entries, accepted = [], []
        for position, current in enumerate(hashes):
            if position >= len(stored) or stored[position] != current:
                break
            if position >= len(records) or int(records[position].get("sequence_index", -1)) != position:
                break
            try:
                entry = self._load_entry(records[position], self.prompts[position])
            except Exception as exc:
                self.notes.append(f"stored chunk {position + 1} rejected: {exc}")
                break
            entries.append(entry)
            accepted.append(records[position])
        return entries, accepted

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
        timeline_video_contract: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        if existing_session is not None:
            raise RunStorageError("Run Storage cannot be combined with an explicit Session")
        self.prompts = [str(value) for value in prompt_plan["prompts"]]
        from .graph_contract import build_upstream_graph_contract
        graph_contract, graph_safe, graph_reasons = build_upstream_graph_contract(
            self.prompt_graph,
            self.sampler_node_id,
            require_video_vae=(
                conditioning_mode_uses_video_vae(str(conditioning_mode))
                or timeline_video_contract is not None
            ),
            require_reference_audio_vae=reference_audio_contract is not None,
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
            timeline_video_contract=timeline_video_contract,
        )
        effective_nonce, nonce_decision = self._resolve_effective_nonce(
            contract, requested_nonce=int(reroll_nonce), resume_safe=safe
        )
        contract = _apply_nonce_contract(
            contract,
            requested_nonce=int(reroll_nonce),
            effective_nonce=effective_nonce,
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
        self.revision_id, self.contract_sha256 = revision_identity(contract)

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
        candidates = [exact] if exact is not None and safe else []
        if safe and exact is None and self.revisions_root.exists():
            for path in self.revisions_root.glob("*/manifest.json"):
                try:
                    candidates.append(_read_json(path))
                except Exception:
                    continue
        for candidate in candidates:
            if int(candidate.get("run_storage_schema_version", -1)) != RUN_STORAGE_SCHEMA_VERSION:
                continue
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
        self._write_manifest()
        self._write_project()
        if not best_entries:
            return None
        return make_session(
            chunks=best_entries, width=int(width), height=int(height),
            chunk_seconds=float(chunk_seconds), identity_hash=str(identity_hash),
            model_fingerprint_value=str(model_fingerprint_value),
            parent_session_id=None, reroll_from_chunk=0,
            settings={
                "run_storage_validated_prefix": True,
                "revision_id": self.revision_id,
                "first_frame_hash": str(first_frame_hash),
                "last_frame_hash": str(last_frame_hash),
            },
        )

    def commit_chunk(self, entry: dict[str, Any], *, position: int) -> None:
        if self.manifest is None or self.revision_root is None:
            return
        validated = validate_chunk_entry(entry)
        if isinstance(position, bool) or not isinstance(position, int):
            raise RunStorageError("Run Storage chunk position must be an integer")
        expected = int((self.contract or {}).get("chunk_count", 0))
        if position < 0 or position >= expected:
            raise RunStorageError(
                f"Run Storage chunk position {position} is outside 0..{expected - 1}"
            )
        existing_records = list(self.manifest.get("chunks") or [])
        if len(existing_records) < position:
            raise RunStorageError(
                f"Run Storage cannot commit chunk {position + 1} before chunk {position}"
            )
        chunks_root = self.revision_root / "chunks"
        chunks_root.mkdir(parents=True, exist_ok=True)
        filename = f"chunk_{position + 1:04d}.safetensors"
        target = chunks_root / filename
        temporary = chunks_root / f".{filename}.{uuid.uuid4().hex}.tmp"
        tensors = {
            "video": validated["video"].detach().to("cpu").contiguous(),
            "audio": validated["audio"].detach().to("cpu").contiguous(),
        }
        try:
            save_file(tensors, str(temporary), metadata={
                "h3_continuum_run_storage": str(RUN_STORAGE_SCHEMA_VERSION),
                "revision_id": self.revision_id,
                "chunk_number": str(position + 1),
            })
            _fsync_file(temporary)
            os.replace(temporary, target)
            _fsync_dir(chunks_root)
        finally:
            if temporary.exists():
                temporary.unlink()
        storage_entry = dict(validated)
        storage_entry["sequence_index"] = position
        record = {
            "sequence_index": position,
            "storage_revision_id": self.revision_id,
            "filename": filename,
            "file_size": target.stat().st_size,
            "file_sha256": _file_sha256(target),
            "entry": _entry_metadata(storage_entry),
        }
        records = existing_records[:position]
        records.append(record)
        self.manifest.update(chunks=records, updated_utc=_now(), status="in_progress")
        self._write_manifest()
        self.generated_count += 1

    def summary(self, *, detailed: bool = False) -> str:
        total = int((self.contract or {}).get("chunk_count", 0))
        resume = self.reused_count + 1 if self.reused_count < total else "complete"
        policy = (" auto-resume disabled: " + "; ".join(self.disabled_reasons) + ".") if self.disabled_reasons else ""
        note = (" " + " ".join(self.notes)) if self.notes else ""
        basic = (
            f"Run Storage: {self.run_name} / revision {self.revision_id}; "
            f"{self.reused_count} reused, {self.generated_count} generated, "
            f"{total} total; resume={resume}; nonce={self.effective_reroll_nonce} "
            f"({self.nonce_decision}).{policy}{note}"
        )
        if not detailed or self.manifest is None:
            return basic
        records = list(self.manifest.get("chunks") or [])
        lines = [basic, f"Run Storage path: {self.revision_root}"]
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

    def finalize(self, *, session: dict[str, Any], report: str) -> None:
        if self.manifest is None:
            return
        expected = int((self.contract or {}).get("chunk_count", 0))
        status = "complete" if len(self.manifest.get("chunks") or []) == expected else "interrupted"
        self.manifest.update(
            status=status, updated_utc=_now(),
            session_id=str(session.get("session_id", "")),
            report_summary=str(report)[-8192:],
        )
        self._write_manifest()
        self._write_project()


def get_active_run_storage() -> RunStorageController | None:
    return _ACTIVE.get()


def run_storage_scope(
    run_name: str, *, prompt: Any = None, unique_id: Any = None
) -> RunStorageController:
    controller = RunStorageController(run_name)
    controller.set_prompt_graph(prompt, unique_id)
    return controller
