"""Reusable native-H3 continuation preparation independent of ComfyUI UI nodes."""

from __future__ import annotations

from typing import Any

import torch

from .constants import (
    CONTINUUM_INTEROP_API,
    CONTINUUM_REFERENCE_METADATA_KEY,
    MARK_AUDIO_CONTEXT,
    MARK_AUDIO_END_FRAME,
    MARK_AUDIO_OVERHANG,
    MARK_CONTEXT_FRAMES,
    MARK_SCHEMA,
    MARK_VIDEO_CONTEXT,
)
from .state import extract_av_streams
from .version import STATE_SCHEMA_VERSION

POLICY_REPLACE = "Use Continuum context; keep visual identity tokens (Recommended)"
POLICY_ERROR = "Error if a first-frame keyframe exists"
POLICY_KEEP = "Keep first-frame keyframe too (Advanced)"
FIRST_FRAME_POLICIES = (POLICY_REPLACE, POLICY_ERROR, POLICY_KEEP)


def clone_conditioning(conditioning):
    """Clone the outer conditioning list and metadata dictionaries."""
    output = []
    for index, item in enumerate(conditioning):
        if not isinstance(item, (tuple, list)) or len(item) != 2:
            raise ValueError(f"conditioning entry {index} is not [tensor, metadata]")
        if not isinstance(item[1], dict):
            raise ValueError(f"conditioning entry {index} metadata is not a dictionary")
        output.append([item[0], dict(item[1])])
    if not output:
        raise ValueError("conditioning is empty")
    return output


def conditioning_diagnostics(conditioning) -> dict[str, int]:
    """Return non-authoritative cues used in the Join report."""
    first_keyframes = 0
    visual_tokens = 0
    for item in conditioning:
        if not isinstance(item, (tuple, list)) or len(item) != 2:
            continue
        metadata = item[1] if isinstance(item[1], dict) else {}
        for keyframe in metadata.get("minimax_keyframes") or ():
            if int(keyframe.get("resolved_frame_index", 0)) == 0:
                first_keyframes += 1
        tags = metadata.get("minimax_token_tags")
        if torch.is_tensor(tags):
            visual_tokens += int((tags == 0).sum().item())
    return {"first_keyframes": first_keyframes, "visual_tokens": visual_tokens}


def prepare_conditioning(
    conditioning,
    *,
    video_context: torch.Tensor,
    audio_context: torch.Tensor | None,
    audio_grid_offset: float,
    context_frames: int,
    new_frame_count: int,
    first_frame_policy: str,
    preserve_last_frame: bool,
    source_frame_count: int | None = None,
):
    """Add one native H3 video/video-audio reference as timeline context."""
    if first_frame_policy not in FIRST_FRAME_POLICIES:
        raise ValueError(f"unknown first-frame policy: {first_frame_policy!r}")
    if not torch.is_tensor(video_context) or video_context.ndim != 5:
        raise ValueError("video_context must be [1,24,T,H,W]")
    if tuple(video_context.shape[:2]) != (1, 24):
        raise ValueError("video_context must have shape [1,24,T,H,W]")
    if audio_context is not None:
        if not torch.is_tensor(audio_context) or audio_context.ndim != 4:
            raise ValueError("audio_context must be [1,32,2,T]")
        if tuple(audio_context.shape[:3]) != (1, 32, 2):
            raise ValueError("audio_context must have shape [1,32,2,T]")

    context_t = int(video_context.shape[2])
    context_ref: dict[str, Any] = {
        "kind": "video_audio" if audio_context is not None else "video",
        "latent_t": context_t,
        "latent_h": int(video_context.shape[-2]),
        "latent_w": int(video_context.shape[-1]),
        "ref_audio_t": int(audio_context.shape[-1]) if audio_context is not None else 0,
        "latent": video_context.contiguous(),
        MARK_SCHEMA: STATE_SCHEMA_VERSION,
        MARK_VIDEO_CONTEXT: True,
        MARK_CONTEXT_FRAMES: int(context_frames),
        CONTINUUM_REFERENCE_METADATA_KEY: {
            "api": CONTINUUM_INTEROP_API,
            "role": "video_context",
            "audio_role": "audio_context" if audio_context is not None else None,
        },
    }
    if audio_context is not None:
        context_ref.update(
            {
                "audio_latent": audio_context.contiguous(),
                MARK_AUDIO_CONTEXT: True,
                MARK_AUDIO_END_FRAME: float(context_frames),
                MARK_AUDIO_OVERHANG: float(audio_grid_offset),
            }
        )

    output = clone_conditioning(conditioning)
    for _, metadata in output:
        old_frame_count = metadata.get("minimax_frame_count")
        if old_frame_count is None:
            old_frame_count = source_frame_count
        old_keyframes = [dict(item) for item in (metadata.get("minimax_keyframes") or [])]
        kept = []
        for keyframe in old_keyframes:
            frame_index = int(keyframe.get("resolved_frame_index", 0))
            if frame_index == 0:
                if first_frame_policy == POLICY_ERROR:
                    raise ValueError(
                        "conditioning already has a first-frame keyframe. Disconnect the image "
                        "for continuation, or use the recommended identity-token policy."
                    )
                if first_frame_policy == POLICY_KEEP:
                    kept.append(keyframe)
                continue
            is_last = old_frame_count is not None and frame_index == int(old_frame_count) - 1
            if is_last and preserve_last_frame:
                keyframe["resolved_frame_index"] = int(new_frame_count) - 1
                kept.append(keyframe)
            elif is_last:
                continue
            else:
                # Core H3 accepts arbitrary guide positions. Preserve them and
                # let the native keyframe/layout path decide their semantics.
                kept.append(keyframe)
        if kept:
            metadata["minimax_keyframes"] = kept
        else:
            metadata.pop("minimax_keyframes", None)
        metadata["minimax_frame_count"] = int(new_frame_count)
        refs = [
            dict(item)
            for item in (metadata.get("minimax_refs") or [])
            if not (item.get(MARK_VIDEO_CONTEXT) or item.get(MARK_AUDIO_CONTEXT))
        ]
        refs.append(dict(context_ref))
        metadata["minimax_refs"] = refs
    return output


def new_h3_latent(template: dict[str, Any], *, video_t: int, audio_t: int):
    """Create an empty native H3 AV latent matching the template geometry/dtype."""
    try:
        import comfy.model_management
        import comfy.nested_tensor
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"ComfyUI H3 latent helpers unavailable: {exc}") from exc
    video, audio = extract_av_streams(template)
    device = comfy.model_management.intermediate_device()
    new_video = torch.zeros(
        (1, 24, int(video_t), int(video.shape[-2]), int(video.shape[-1])),
        device=device,
        dtype=video.dtype,
    )
    new_audio = torch.zeros((1, 32, 2, int(audio_t)), device=device, dtype=audio.dtype)
    return {"samples": comfy.nested_tensor.NestedTensor((new_video, new_audio))}
