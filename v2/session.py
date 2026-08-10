"""In-memory session model for accepted chunks, resume, and branch-safe rerolls."""

from __future__ import annotations

import copy
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

import torch

from ..constants import SESSION_MAGIC, STATE_MAGIC
from ..state import validate_plan
from ..temporal import (
    audio_grid_offset,
    audio_latent_t,
    context_slots,
    is_valid_frame_count,
    pixel_frames_for_latent_t,
    video_latent_t,
)
from ..version import PACKAGE_VERSION, SESSION_SCHEMA_VERSION, STATE_SCHEMA_VERSION
from .sampling import latent_from_cpu, latent_to_cpu


class SessionValidationError(ValueError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def model_fingerprint(
    model: Any, *, extra_wrapper_keys: tuple[str, ...] = ()
) -> str:
    base = getattr(model, "model", None)
    inner = getattr(base, "diffusion_model", None)
    options = getattr(model, "model_options", {}) or {}
    transformer = options.get("transformer_options", {}) or {}
    wrappers = getattr(model, "wrappers", {}) or {}
    wrapper_keys: list[str] = []
    if isinstance(wrappers, dict):
        for group in wrappers.values():
            if isinstance(group, dict):
                wrapper_keys.extend(str(key) for key in group)
    if extra_wrapper_keys:
        wrapper_keys = sorted(set(wrapper_keys).union(map(str, extra_wrapper_keys)))
    descriptor = {
        "base": f"{type(base).__module__}.{type(base).__name__}" if base is not None else "missing",
        "inner": f"{type(inner).__module__}.{type(inner).__name__}" if inner is not None else "missing",
        "dtype": str(getattr(model, "model_dtype", lambda: "unknown")()),
        "model_size": int(getattr(model, "model_size", lambda: 0)() or 0),
        "wrappers": sorted(wrapper_keys),
        "has_attention_override": transformer.get("optimized_attention_override") is not None,
        "has_sol_compose": transformer.get("sol_compose") is not None,
    }
    raw = json.dumps(descriptor, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def make_chunk_entry(
    *,
    latent: dict[str, Any],
    plan: dict[str, Any],
    prompt: str,
    prompt_hash: str,
    seed: int,
    context_frames: int,
    motion_score: float,
    reused: bool,
) -> dict[str, Any]:
    plan = validate_plan(plan)
    video, audio = latent_to_cpu(latent)
    actual_frames = pixel_frames_for_latent_t(int(video.shape[2]))
    if actual_frames != int(plan["total_frames"]):
        raise SessionValidationError(
            f"chunk latent represents {actual_frames} frames but plan declares {plan['total_frames']}"
        )
    return {
        "sequence_index": 0,  # populated by make_session
        "clip_index": int(plan["clip_index"]),
        "prompt": str(prompt),
        "prompt_hash": str(prompt_hash),
        "seed": int(seed),
        "context_frames": int(context_frames),
        "motion_score": float(motion_score),
        "reused": bool(reused),
        "plan": copy.deepcopy(plan),
        "video": video,
        "audio": audio,
    }


def validate_chunk_entry(entry: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(entry, dict):
        raise SessionValidationError("session chunk must be a dictionary")
    video, audio = entry.get("video"), entry.get("audio")
    if not torch.is_tensor(video) or video.ndim != 5 or tuple(video.shape[:2]) != (1, 24):
        raise SessionValidationError("session chunk video must be [1,24,T,H,W]")
    if not torch.is_tensor(audio) or audio.ndim != 4 or tuple(audio.shape[:3]) != (1, 32, 2):
        raise SessionValidationError("session chunk audio must be [1,32,2,T]")
    if video.device.type != "cpu" or audio.device.type != "cpu":
        raise SessionValidationError("session tensors must remain on CPU")
    if not bool(torch.isfinite(video.float()).all().item()):
        raise SessionValidationError("session video contains NaN or Inf")
    if not bool(torch.isfinite(audio.float()).all().item()):
        raise SessionValidationError("session audio contains NaN or Inf")
    plan = validate_plan(entry.get("plan"))
    actual_frames = pixel_frames_for_latent_t(int(video.shape[2]))
    if actual_frames != int(plan["total_frames"]):
        raise SessionValidationError("session chunk video length does not match its plan")
    if not isinstance(entry.get("prompt"), str) or not entry["prompt"].strip():
        raise SessionValidationError("session chunk prompt is empty")
    if not isinstance(entry.get("prompt_hash"), str) or len(entry["prompt_hash"]) != 64:
        raise SessionValidationError("session chunk prompt hash is invalid")
    if int(entry.get("seed", -1)) < 0:
        raise SessionValidationError("session chunk seed is invalid")
    if int(entry.get("context_frames", 0)) not in (0, 5, 22, 39):
        raise SessionValidationError("session chunk context_frames is invalid")
    return entry


def make_session(
    *,
    chunks: list[dict[str, Any]],
    width: int,
    height: int,
    chunk_seconds: float,
    identity_hash: str,
    model_fingerprint_value: str,
    parent_session_id: str | None,
    reroll_from_chunk: int,
    settings: dict[str, Any],
) -> dict[str, Any]:
    session_id = uuid.uuid4().hex
    normalized: list[dict[str, Any]] = []
    for index, entry in enumerate(chunks, start=1):
        item = dict(entry)
        item["plan"] = copy.deepcopy(entry["plan"])
        item["sequence_index"] = index
        validate_chunk_entry(item)
        normalized.append(item)
    return {
        "magic": SESSION_MAGIC,
        "schema_version": SESSION_SCHEMA_VERSION,
        "package_version": PACKAGE_VERSION,
        "session_id": session_id,
        "parent_session_id": parent_session_id,
        "created_utc": _now_iso(),
        "reroll_from_chunk": int(reroll_from_chunk),
        "width": int(width),
        "height": int(height),
        "chunk_seconds": float(chunk_seconds),
        "identity_hash": str(identity_hash),
        "model_fingerprint": str(model_fingerprint_value),
        "settings": copy.deepcopy(settings),
        "chunks": normalized,
    }


def validate_session(session: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(session, dict) or session.get("magic") != SESSION_MAGIC:
        raise SessionValidationError("invalid H3 Continuum session")
    if int(session.get("schema_version", -1)) != SESSION_SCHEMA_VERSION:
        raise SessionValidationError(
            f"unsupported session schema {session.get('schema_version')}; "
            f"expected {SESSION_SCHEMA_VERSION}"
        )
    if int(session.get("width", 0)) <= 0 or int(session.get("height", 0)) <= 0:
        raise SessionValidationError("session dimensions are invalid")
    if float(session.get("chunk_seconds", 0.0)) <= 0:
        raise SessionValidationError("session chunk_seconds is invalid")
    chunks = session.get("chunks")
    if not isinstance(chunks, list) or not chunks:
        raise SessionValidationError("session contains no chunks")
    previous_clip_index = None
    for index, entry in enumerate(chunks, start=1):
        validate_chunk_entry(entry)
        if int(entry.get("sequence_index", index)) != index:
            raise SessionValidationError("session chunk sequence indices are not contiguous")
        clip_index = int(entry["plan"]["clip_index"])
        if previous_clip_index is not None and clip_index != previous_clip_index + 1:
            raise SessionValidationError("session clip indices are not contiguous")
        previous_clip_index = clip_index
        video = entry["video"]
        if int(video.shape[-1]) * 16 != int(session["width"]):
            raise SessionValidationError("session width does not match chunk latent")
        if int(video.shape[-2]) * 16 != int(session["height"]):
            raise SessionValidationError("session height does not match chunk latent")
    return session


def entry_to_latent(entry: dict[str, Any]) -> dict[str, Any]:
    entry = validate_chunk_entry(entry)
    return latent_from_cpu(entry["video"], entry["audio"])


def entry_to_state(entry: dict[str, Any], *, capacity_frames: int | None = None) -> dict[str, Any]:
    """Build a V1-compatible continuation state directly from a CPU chunk.

    This deliberately avoids reconstructing a ComfyUI ``NestedTensor``. Session
    inspection, persistence tests, and branch selection therefore remain usable
    outside a live ComfyUI process, while the returned state is byte-for-byte
    compatible with the V1 state contract.
    """

    entry = validate_chunk_entry(entry)
    plan = entry["plan"]
    video = entry["video"]
    audio = entry["audio"]
    source_frames = int(plan["total_frames"])
    clip_index = int(plan["clip_index"])
    capacity = int(capacity_frames or plan["state_capacity_frames"])

    actual_video_t = int(video.shape[2])
    actual_frames = pixel_frames_for_latent_t(actual_video_t)
    if actual_frames != source_frames:
        raise SessionValidationError(
            f"chunk plan says {source_frames} frames but latent represents {actual_frames}"
        )
    if not is_valid_frame_count(actual_frames) or video_latent_t(actual_frames) != actual_video_t:
        raise SessionValidationError(
            f"chunk video latent T={actual_video_t} is not on the native H3 temporal grid"
        )

    slots = context_slots(capacity)
    audio_steps = audio_latent_t(capacity)
    if int(video.shape[2]) < slots or int(audio.shape[-1]) < audio_steps:
        raise SessionValidationError(
            f"chunk is too short for a {capacity}-frame continuation state"
        )
    grid_offset = audio_grid_offset(source_frames, int(audio.shape[-1]))
    if not (-0.500001 <= grid_offset <= 0.500001):
        raise SessionValidationError(
            f"unexpected signed audio-grid offset {grid_offset:.6f}"
        )

    video_tail = video[:, :, -slots:].contiguous().clone()
    audio_tail = audio[..., -audio_steps:].contiguous().clone()
    return {
        "magic": STATE_MAGIC,
        "schema_version": STATE_SCHEMA_VERSION,
        "clip_index": clip_index,
        "source_frame_count": source_frames,
        "capacity_frames": capacity,
        "width": int(video.shape[-1]) * 16,
        "height": int(video.shape[-2]) * 16,
        "video_tail": video_tail,
        "audio_tail": audio_tail,
        "audio_overhang": float(grid_offset),
        "source_mode": "latent_direct",
    }


def session_summary(session: dict[str, Any]) -> str:
    session = validate_session(session)
    reused = sum(1 for item in session["chunks"] if item.get("reused"))
    frames = sum(int(item["plan"]["net_frames"]) for item in session["chunks"])
    return (
        f"Session {session['session_id'][:8]}: {len(session['chunks'])} chunks, "
        f"{frames} retained frames, {reused} reused, {session['width']}x{session['height']}."
    )
