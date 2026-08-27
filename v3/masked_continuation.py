"""Private V3.6 masked-prefix continuation experiments.

This module is intentionally not registered as a public node contract.  It
builds H3 AV targets whose protected prefixes are preserved by Core's denoise
mask. R1 protects video only; R2-0 can protect matching video and audio tails.
"""

from __future__ import annotations

from typing import Any

import torch

from ..state import extract_av_streams
from ..temporal import audio_latent_t, context_slots


REFERENCE_CONTEXT_V1 = "reference_context_v1"
MASKED_VIDEO_PREFIX_V1 = "masked_video_prefix_v1"
MASKED_AV_PREFIX_22_V1 = "masked_av_prefix_22_v1"
MASKED_AV_PREFIX_39_V1 = "masked_av_prefix_39_v1"
CONTINUATION_TRANSPORTS = (
    REFERENCE_CONTEXT_V1,
    MASKED_VIDEO_PREFIX_V1,
    MASKED_AV_PREFIX_22_V1,
    MASKED_AV_PREFIX_39_V1,
)


def _build_masked_prefix_latent(
    target_latent: dict[str, Any],
    video_context: torch.Tensor,
    context_frames: int,
    *,
    audio_context: torch.Tensor | None,
) -> dict[str, Any]:
    """Copy normalized AV tails into a target and attach stream masks."""

    try:
        import comfy.nested_tensor
    except Exception as exc:  # pragma: no cover - ComfyUI runtime only
        raise RuntimeError(f"ComfyUI NestedTensor helper unavailable: {exc}") from exc

    target_video, target_audio = extract_av_streams(target_latent)
    frames = int(context_frames)
    slots = context_slots(frames)
    if not torch.is_tensor(video_context) or video_context.ndim != 5:
        raise ValueError("masked video context must be a five-dimensional Tensor")
    if tuple(video_context.shape[:2]) != tuple(target_video.shape[:2]):
        raise ValueError(
            "masked video context batch/channel shape does not match the target: "
            f"context={tuple(video_context.shape)}, target={tuple(target_video.shape)}"
        )
    if int(video_context.shape[2]) != slots:
        raise ValueError(
            f"masked video context has T={video_context.shape[2]}; expected {slots} "
            f"for {frames} frames"
        )
    if tuple(video_context.shape[-2:]) != tuple(target_video.shape[-2:]):
        raise ValueError(
            "masked video context geometry does not match the target: "
            f"context={tuple(video_context.shape[-2:])}, "
            f"target={tuple(target_video.shape[-2:])}"
        )
    if int(target_video.shape[2]) <= slots:
        raise ValueError("masked video target must contain generated slots after the prefix")

    normalized_video = video_context.detach().to(
        device=target_video.device,
        dtype=target_video.dtype,
    ).contiguous()
    if not bool(torch.isfinite(normalized_video.float()).all().item()):
        raise ValueError("masked video context contains NaN or Inf")

    normalized_audio = None
    audio_steps = 0
    if audio_context is not None:
        audio_steps = audio_latent_t(frames)
        if not torch.is_tensor(audio_context) or audio_context.ndim != 4:
            raise ValueError("masked audio context must be a four-dimensional Tensor")
        if tuple(audio_context.shape[:3]) != tuple(target_audio.shape[:3]):
            raise ValueError(
                "masked audio context batch/channel shape does not match the target: "
                f"context={tuple(audio_context.shape)}, target={tuple(target_audio.shape)}"
            )
        if int(audio_context.shape[-1]) != audio_steps:
            raise ValueError(
                f"masked audio context has T={audio_context.shape[-1]}; expected "
                f"{audio_steps} for {frames} frames"
            )
        if int(target_audio.shape[-1]) <= audio_steps:
            raise ValueError("masked audio target must contain generated ticks after the prefix")
        normalized_audio = audio_context.detach().to(
            device=target_audio.device,
            dtype=target_audio.dtype,
        ).contiguous()
        if not bool(torch.isfinite(normalized_audio.float()).all().item()):
            raise ValueError("masked audio context contains NaN or Inf")

    video = target_video.clone()
    audio = target_audio.clone()
    video[:, :, :slots].copy_(normalized_video)
    if normalized_audio is not None:
        audio[..., :audio_steps].copy_(normalized_audio)

    video_mask = torch.ones(
        (
            int(video.shape[0]),
            1,
            int(video.shape[2]),
            int(video.shape[3]),
            int(video.shape[4]),
        ),
        device=video.device,
        dtype=torch.float32,
    )
    video_mask[:, :, :slots] = 0.0
    audio_mask = torch.ones(
        (
            int(audio.shape[0]),
            1,
            int(audio.shape[2]),
            int(audio.shape[3]),
        ),
        device=audio.device,
        dtype=torch.float32,
    )
    if normalized_audio is not None:
        audio_mask[..., :audio_steps] = 0.0

    result = dict(target_latent)
    result["samples"] = comfy.nested_tensor.NestedTensor((video, audio))
    result["noise_mask"] = comfy.nested_tensor.NestedTensor(
        (video_mask, audio_mask)
    )
    return result


def build_masked_video_prefix_latent(
    target_latent: dict[str, Any],
    video_context: torch.Tensor,
    context_frames: int,
) -> dict[str, Any]:
    """Copy a normalized video tail into the target and attach AV noise masks."""
    return _build_masked_prefix_latent(
        target_latent,
        video_context,
        context_frames,
        audio_context=None,
    )


def build_masked_av_prefix_latent(
    target_latent: dict[str, Any],
    video_context: torch.Tensor,
    audio_context: torch.Tensor,
    context_frames: int,
) -> dict[str, Any]:
    """Copy matching video/audio tails and preserve both with denoise masks."""

    return _build_masked_prefix_latent(
        target_latent,
        video_context,
        context_frames,
        audio_context=audio_context,
    )


def _restore_masked_prefix(
    sampled_latent: dict[str, Any],
    target_latent: dict[str, Any],
    context_frames: int,
    *,
    restore_audio: bool,
) -> dict[str, Any]:
    """Reapply only protected prefix regions after sampler integration."""

    try:
        import comfy.nested_tensor
    except Exception as exc:  # pragma: no cover - ComfyUI runtime only
        raise RuntimeError(f"ComfyUI NestedTensor helper unavailable: {exc}") from exc

    sampled_video, sampled_audio = extract_av_streams(sampled_latent)
    target_video, target_audio = extract_av_streams(target_latent)
    slots = context_slots(int(context_frames))
    if tuple(sampled_video.shape) != tuple(target_video.shape):
        raise ValueError(
            "sampled video shape does not match the masked target: "
            f"sampled={tuple(sampled_video.shape)}, target={tuple(target_video.shape)}"
        )
    restored_video = sampled_video.clone()
    restored_video[:, :, :slots].copy_(target_video[:, :, :slots])
    restored_audio = sampled_audio
    if restore_audio:
        if tuple(sampled_audio.shape) != tuple(target_audio.shape):
            raise ValueError(
                "sampled audio shape does not match the masked target: "
                f"sampled={tuple(sampled_audio.shape)}, target={tuple(target_audio.shape)}"
            )
        audio_steps = audio_latent_t(int(context_frames))
        restored_audio = sampled_audio.clone()
        restored_audio[..., :audio_steps].copy_(target_audio[..., :audio_steps])
    result = dict(sampled_latent)
    result["samples"] = comfy.nested_tensor.NestedTensor(
        (restored_video, restored_audio)
    )
    return result


def restore_masked_video_prefix(
    sampled_latent: dict[str, Any],
    target_latent: dict[str, Any],
    context_frames: int,
) -> dict[str, Any]:
    """Reapply only the preserved prefix after sampler integration rounding."""
    return _restore_masked_prefix(
        sampled_latent,
        target_latent,
        context_frames,
        restore_audio=False,
    )


def restore_masked_av_prefix(
    sampled_latent: dict[str, Any],
    target_latent: dict[str, Any],
    context_frames: int,
) -> dict[str, Any]:
    """Reapply only protected video and audio prefixes after Sampling."""

    return _restore_masked_prefix(
        sampled_latent,
        target_latent,
        context_frames,
        restore_audio=True,
    )
