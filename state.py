"""State and plan containers for H3 Continuum Join."""

from __future__ import annotations

from typing import Any

import torch

from .constants import DEFAULT_STATE_CAPACITY_FRAMES, PLAN_MAGIC, STATE_MAGIC
from .temporal import (
    audio_latent_t_from_grid_offset,
    audio_grid_offset,
    audio_latent_t,
    context_slots,
    is_valid_frame_count,
    make_av_context_window,
    pixel_frames_for_latent_t,
    video_latent_t,
)
from .version import PLAN_SCHEMA_VERSION, STATE_SCHEMA_VERSION


class StateValidationError(ValueError):
    pass


def extract_av_streams(latent: dict[str, Any]) -> tuple[torch.Tensor, torch.Tensor]:
    if not isinstance(latent, dict) or "samples" not in latent:
        raise StateValidationError("expected LATENT dictionary containing 'samples'")
    samples = latent["samples"]
    if hasattr(samples, "unbind"):
        parts = list(samples.unbind())
    elif isinstance(samples, (tuple, list)):
        parts = list(samples)
    else:
        raise StateValidationError(
            "expected MiniMax H3 NestedTensor samples; got " + type(samples).__name__
        )
    if len(parts) < 2:
        raise StateValidationError("MiniMax H3 latent must contain video and audio")
    video, audio = parts[0], parts[1]
    if video.ndim == 4:
        video = video.unsqueeze(0)
    if audio.ndim == 3:
        audio = audio.unsqueeze(0)
    if video.ndim != 5 or audio.ndim != 4:
        raise StateValidationError(
            f"unexpected H3 latent shapes: video={tuple(video.shape)}, audio={tuple(audio.shape)}"
        )
    if video.shape[0] != 1 or audio.shape[0] != 1:
        raise StateValidationError("H3 Continuum Join supports batch size 1")
    if video.shape[1] != 24:
        raise StateValidationError(f"expected 24 video channels, got {video.shape[1]}")
    if audio.shape[1] != 32 or audio.shape[2] != 2:
        raise StateValidationError(f"expected stereo [1,32,2,T] audio, got {tuple(audio.shape)}")
    return video, audio


def make_plan(
    *, continuation: bool, clip_index: int, total_frames: int, trim_frames: int,
    width: int, height: int, context_frames: int, state_capacity_frames: int,
    requested_extend_seconds: float, debug: bool,
) -> dict[str, Any]:
    return {
        "magic": PLAN_MAGIC,
        "schema_version": PLAN_SCHEMA_VERSION,
        "continuation": bool(continuation),
        "clip_index": int(clip_index),
        "total_frames": int(total_frames),
        "trim_frames": int(trim_frames),
        "net_frames": int(total_frames) - int(trim_frames),
        "width": int(width),
        "height": int(height),
        "context_frames": int(context_frames),
        "state_capacity_frames": int(state_capacity_frames),
        "requested_extend_seconds": float(requested_extend_seconds),
        "debug": bool(debug),
    }


def validate_plan(plan: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(plan, dict) or plan.get("magic") != PLAN_MAGIC:
        raise StateValidationError("invalid H3 Continuum plan")
    if int(plan.get("schema_version", -1)) != PLAN_SCHEMA_VERSION:
        raise StateValidationError(
            f"unsupported plan schema {plan.get('schema_version')}; expected {PLAN_SCHEMA_VERSION}"
        )
    for key in (
        "total_frames",
        "trim_frames",
        "net_frames",
        "width",
        "height",
        "clip_index",
        "state_capacity_frames",
    ):
        if not isinstance(plan.get(key), int):
            raise StateValidationError(f"plan field '{key}' is missing or invalid")
    if plan["total_frames"] < 5 or plan["width"] <= 0 or plan["height"] <= 0:
        raise StateValidationError("plan dimensions or frame count are invalid")
    if plan["trim_frames"] < 0 or plan["trim_frames"] >= plan["total_frames"]:
        raise StateValidationError("plan trim range is invalid")
    if plan["net_frames"] != plan["total_frames"] - plan["trim_frames"]:
        raise StateValidationError("plan net_frames does not match total_frames - trim_frames")
    if plan["clip_index"] < 1:
        raise StateValidationError("plan clip_index must be at least 1")
    if plan["state_capacity_frames"] not in (5, 22, 39):
        raise StateValidationError("plan state_capacity_frames must be 5, 22, or 39")
    if plan["state_capacity_frames"] > plan["net_frames"]:
        raise StateValidationError("plan state capacity exceeds retained output frames")
    continuation = bool(plan.get("continuation", False))
    if continuation and plan["trim_frames"] <= 0:
        raise StateValidationError("continuation plan must trim a positive overlap")
    if not continuation and plan["trim_frames"] != 0:
        raise StateValidationError("initial plan cannot trim an overlap")
    return plan


def capture_state(
    latent: dict[str, Any], *, source_frame_count: int, clip_index: int,
    capacity_frames: int = DEFAULT_STATE_CAPACITY_FRAMES,
) -> dict[str, Any]:
    video, audio = extract_av_streams(latent)
    actual_video_t = int(video.shape[2])
    actual_frames = pixel_frames_for_latent_t(actual_video_t)
    if actual_frames != int(source_frame_count):
        raise StateValidationError(
            f"plan says {source_frame_count} frames but latent represents {actual_frames}"
        )
    if not is_valid_frame_count(actual_frames) or video_latent_t(actual_frames) != actual_video_t:
        raise StateValidationError(
            f"sampler video latent T={actual_video_t} is not on the native H3 temporal grid"
        )
    try:
        window = make_av_context_window(
            source_frame_count,
            int(audio.shape[-1]),
            capacity_frames,
        )
    except ValueError as exc:
        raise StateValidationError(str(exc)) from exc
    slots = context_slots(capacity_frames)
    audio_steps = window.audio_steps
    if video.shape[2] < slots or audio.shape[-1] < audio_steps:
        raise StateValidationError("sampler output is too short for requested state capacity")
    grid_offset = audio_grid_offset(source_frame_count, int(audio.shape[-1]))
    if not (-0.500001 <= grid_offset <= 0.500001):
        raise StateValidationError(f"unexpected signed audio-grid offset {grid_offset:.6f}")
    video_tail = video[:, :, -slots:].detach().to("cpu").contiguous().clone()
    audio_tail = audio[..., -audio_steps:].detach().to("cpu").contiguous().clone()
    if not bool(torch.isfinite(video_tail.float()).all().item()):
        raise StateValidationError("video continuation state contains NaN or Inf")
    if not bool(torch.isfinite(audio_tail.float()).all().item()):
        raise StateValidationError("audio continuation state contains NaN or Inf")
    return {
        "magic": STATE_MAGIC,
        "schema_version": STATE_SCHEMA_VERSION,
        "clip_index": int(clip_index),
        "source_frame_count": int(source_frame_count),
        "capacity_frames": int(capacity_frames),
        "width": int(video.shape[-1]) * 16,
        "height": int(video.shape[-2]) * 16,
        "video_tail": video_tail,
        "audio_tail": audio_tail,
        # Schema-v1 field name retained. The value is signed and represents
        # audio-grid end offset, not only positive overhang.
        "audio_overhang": float(grid_offset),
        "source_mode": "latent_direct",
    }


def validate_state(state: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(state, dict) or state.get("magic") != STATE_MAGIC:
        raise StateValidationError("invalid H3 Continuum state")
    if int(state.get("schema_version", -1)) != STATE_SCHEMA_VERSION:
        raise StateValidationError(
            f"unsupported state schema {state.get('schema_version')}; expected {STATE_SCHEMA_VERSION}"
        )
    video, audio = state.get("video_tail"), state.get("audio_tail")
    if not torch.is_tensor(video) or video.ndim != 5 or tuple(video.shape[:2]) != (1, 24):
        raise StateValidationError("state video_tail must be [1,24,T,H,W]")
    if not torch.is_tensor(audio) or audio.ndim != 4 or tuple(audio.shape[:3]) != (1, 32, 2):
        raise StateValidationError("state audio_tail must be [1,32,2,T]")
    if int(state.get("width", 0)) != int(video.shape[-1]) * 16:
        raise StateValidationError("state width does not match video_tail")
    if int(state.get("height", 0)) != int(video.shape[-2]) * 16:
        raise StateValidationError("state height does not match video_tail")
    capacity = int(state.get("capacity_frames", 0))
    if capacity not in (5, 22, 39):
        raise StateValidationError("state capacity must be 5, 22, or 39 frames")
    expected_video_t = context_slots(capacity)
    expected_audio_t = audio_latent_t(capacity)
    if int(video.shape[2]) != expected_video_t or int(audio.shape[-1]) != expected_audio_t:
        raise StateValidationError(
            "state tensor lengths do not match declared capacity: "
            f"video T={video.shape[2]} (expected {expected_video_t}), "
            f"audio T={audio.shape[-1]} (expected {expected_audio_t})"
        )
    source_frames = int(state.get("source_frame_count", 0))
    if not is_valid_frame_count(source_frames):
        raise StateValidationError("state source_frame_count is not on the H3 17k+5 grid")
    if int(state.get("clip_index", 0)) < 1:
        raise StateValidationError("state clip_index must be at least 1")
    grid_offset = float(state.get("audio_overhang", 0.0))
    if not (-0.500001 <= grid_offset <= 0.500001):
        raise StateValidationError("state signed audio-grid offset is outside [-0.5,0.5]")
    if not bool(torch.isfinite(video.float()).all().item()):
        raise StateValidationError("state video_tail contains NaN or Inf")
    if not bool(torch.isfinite(audio.float()).all().item()):
        raise StateValidationError("state audio_tail contains NaN or Inf")
    return state


def select_context(
    state: dict[str, Any], context_frames: int, *, include_audio: bool,
) -> tuple[torch.Tensor, torch.Tensor | None, float]:
    state = validate_state(state)
    if int(context_frames) > int(state["capacity_frames"]):
        raise StateValidationError(
            f"state retains {state['capacity_frames']} frames; {context_frames} requested"
        )
    source_frames = int(state["source_frame_count"])
    grid_offset = float(state["audio_overhang"])
    try:
        source_audio_t = audio_latent_t_from_grid_offset(source_frames, grid_offset)
        window = make_av_context_window(
            source_frames,
            source_audio_t,
            int(context_frames),
        )
    except ValueError as exc:
        raise StateValidationError(
            "Native Continuity unavailable for this state: " + str(exc)
        ) from exc
    slots = context_slots(int(context_frames))
    video = state["video_tail"][:, :, -slots:].contiguous()
    audio = None
    if include_audio:
        if int(state["audio_tail"].shape[-1]) < window.audio_steps:
            raise StateValidationError(
                "Native Continuity state does not retain the required source audio-grid tail"
            )
        audio = state["audio_tail"][..., -window.audio_steps:].contiguous()
    return video, audio, grid_offset


def _tensor_fingerprint(tensor: torch.Tensor | None) -> tuple[Any, ...] | None:
    if tensor is None:
        return None
    value = tensor.detach().to(device="cpu", dtype=torch.float32)
    finite = bool(torch.isfinite(value).all().item())
    if not finite:
        raise StateValidationError("continuation context contains NaN or Inf")
    flat = value.reshape(-1)
    if flat.numel() <= 64:
        sample = flat
    else:
        indices = torch.linspace(0, flat.numel() - 1, 64, dtype=torch.long)
        sample = flat.index_select(0, indices)
    weights = torch.arange(1, sample.numel() + 1, dtype=torch.float32)
    return (
        tuple(int(part) for part in tensor.shape),
        str(tensor.dtype),
        finite,
        float(value.mean().item()),
        float(value.std(unbiased=False).item()),
        float((sample * weights).sum().item()),
    )


def context_fingerprint(
    video: torch.Tensor,
    audio: torch.Tensor | None,
) -> tuple[Any, ...]:
    return (_tensor_fingerprint(video), _tensor_fingerprint(audio))


def assert_context_unchanged(
    video: torch.Tensor,
    audio: torch.Tensor | None,
    expected: tuple[Any, ...],
) -> None:
    if context_fingerprint(video, audio) != expected:
        raise StateValidationError(
            "Native Continuity context tensor changed during sampling"
        )
