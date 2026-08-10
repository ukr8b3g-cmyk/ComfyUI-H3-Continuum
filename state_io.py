"""Crash-resistant safetensors state persistence with a JSON mirror.

The safetensors file is the authoritative single-file commit. All non-tensor
metadata is embedded in its header, while the sidecar JSON remains human
readable. Save replaces the JSON mirror first and the safetensors file last, so
a process interruption cannot commit tensors without their matching metadata.
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from pathlib import Path
from typing import Any

from safetensors import safe_open
from safetensors.torch import save_file

from .state import validate_state

LOG = logging.getLogger("h3_continuum_join")
_SAFE_PREFIX = re.compile(r"[^A-Za-z0-9._-]+")
_HEADER_KEY = "h3_continuum_state_json"


def sanitize_prefix(prefix: str) -> str:
    value = _SAFE_PREFIX.sub("_", str(prefix).strip()).strip("._")
    return value or "h3_continuum"


def state_directory() -> Path:
    try:
        import folder_paths
        root = Path(folder_paths.get_output_directory())
    except Exception:
        root = Path.cwd()
    path = root / "h3_continuum_states"
    path.mkdir(parents=True, exist_ok=True)
    return path


def state_paths(prefix: str, slot: int) -> tuple[Path, Path]:
    slot = int(slot)
    if not (1 <= slot <= 9999):
        raise ValueError("state slot must be between 1 and 9999")
    name = f"{sanitize_prefix(prefix)}_slot{slot:04d}"
    root = state_directory()
    return root / f"{name}.safetensors", root / f"{name}.json"



def _fsync_file(path: Path) -> None:
    """Best-effort durability before atomic replacement."""

    try:
        with path.open("rb") as handle:
            os.fsync(handle.fileno())
    except OSError:
        # Atomic replace still protects against partial readers; some filesystems
        # or Windows configurations do not expose meaningful fsync semantics.
        pass


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    try:
        descriptor = os.open(str(path), os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError:
        pass

def save_state(state: dict[str, Any], *, prefix: str, slot: int) -> tuple[Path, Path]:
    state = validate_state(state)
    tensor_path, json_path = state_paths(prefix, slot)
    token = uuid.uuid4().hex
    tensor_tmp = tensor_path.with_name(f".{tensor_path.name}.{token}.tmp")
    json_tmp = json_path.with_name(f".{json_path.name}.{token}.tmp")
    tensors = {
        "video_tail": state["video_tail"].detach().to("cpu").contiguous(),
        "audio_tail": state["audio_tail"].detach().to("cpu").contiguous(),
    }
    metadata = {k: v for k, v in state.items() if k not in ("video_tail", "audio_tail")}
    metadata["_state_id"] = token
    serialized = json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    try:
        save_file(tensors, str(tensor_tmp), metadata={_HEADER_KEY: serialized})
        _fsync_file(tensor_tmp)
        with json_tmp.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(metadata, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        # The sidecar is informational. Commit the authoritative safetensors
        # file last so its embedded metadata always matches its tensor payload.
        os.replace(json_tmp, json_path)
        os.replace(tensor_tmp, tensor_path)
        _fsync_directory(tensor_path.parent)
    finally:
        for path in (tensor_tmp, json_tmp):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
    return tensor_path, json_path


def _load_authoritative(tensor_path: Path) -> dict[str, Any]:
    with safe_open(str(tensor_path), framework="pt", device="cpu") as handle:
        header = handle.metadata() or {}
        serialized = header.get(_HEADER_KEY)
        if serialized is None:
            raise ValueError("state safetensors has no embedded Continuum metadata")
        state = json.loads(serialized)
        state["video_tail"] = handle.get_tensor("video_tail")
        state["audio_tail"] = handle.get_tensor("audio_tail")
    return state


def load_state(*, prefix: str, slot: int) -> dict[str, Any]:
    tensor_path, json_path = state_paths(prefix, slot)
    if not tensor_path.is_file():
        raise FileNotFoundError(f"state slot does not exist: {tensor_path.name}")
    try:
        state = _load_authoritative(tensor_path)
    except ValueError as exc:
        # Backward-compatible path for early development states that stored
        # metadata only in the JSON sidecar.
        if not json_path.is_file():
            raise
        LOG.warning("Loading legacy Continuum state without embedded metadata: %s", exc)
        with json_path.open("r", encoding="utf-8") as handle:
            state = json.load(handle)
        with safe_open(str(tensor_path), framework="pt", device="cpu") as tensors:
            state["video_tail"] = tensors.get_tensor("video_tail")
            state["audio_tail"] = tensors.get_tensor("audio_tail")

    # The JSON mirror is not authoritative, but report stale/mismatched files.
    if json_path.is_file():
        try:
            with json_path.open("r", encoding="utf-8") as handle:
                mirror = json.load(handle)
            if mirror.get("_state_id") != state.get("_state_id"):
                LOG.warning("Ignoring stale Continuum JSON mirror: %s", json_path.name)
        except (OSError, ValueError, TypeError) as exc:
            LOG.warning("Ignoring unreadable Continuum JSON mirror %s: %s", json_path.name, exc)
    return validate_state(state)


def state_mtime(*, prefix: str, slot: int) -> tuple[float, float]:
    tensor_path, json_path = state_paths(prefix, slot)
    return (
        tensor_path.stat().st_mtime if tensor_path.exists() else -1.0,
        json_path.stat().st_mtime if json_path.exists() else -1.0,
    )
