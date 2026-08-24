"""Sequential pixel/VAE resize for Continuum physical video groups."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

import torch

from .plan import SECOND_PASS_CONTRACT_VERSION


PIXEL_UPSCALE_METHODS = (
    "nearest-exact",
    "bilinear",
    "area",
    "bicubic",
    "bislerp",
    "lanczos",
)
_PIXEL_RESIZE_FRAME_BATCH = 8


class PixelVaeResizeError(ValueError):
    """Raised when a pixel/VAE resize would violate the physical-group contract."""


def _contract_groups(assembly_plan: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    if not isinstance(assembly_plan, Mapping):
        raise PixelVaeResizeError("assembly_plan must be a mapping")
    contract = assembly_plan.get("second_pass_contract")
    if not isinstance(contract, Mapping):
        raise PixelVaeResizeError("assembly_plan has no second_pass_contract")
    if contract.get("version") != SECOND_PASS_CONTRACT_VERSION:
        raise PixelVaeResizeError("unsupported second_pass_contract version")
    groups = contract.get("physical_groups")
    if (
        not isinstance(groups, list)
        or not groups
        or not all(isinstance(group, Mapping) for group in groups)
    ):
        raise PixelVaeResizeError(
            "second_pass_contract.physical_groups must be non-empty"
        )
    return groups


def resolve_pixel_latent_scale(
    assembly_plan: Mapping[str, Any],
) -> tuple[int, int]:
    """Return plan-derived pixel-per-latent ratios as ``(width, height)``."""

    groups = _contract_groups(assembly_plan)
    scale: tuple[int, int] | None = None
    for position, group in enumerate(groups):
        if int(group.get("group_id", -1)) != position:
            raise PixelVaeResizeError("physical group order or group_id changed")
        source_width = int(group.get("source_width", -1))
        source_height = int(group.get("source_height", -1))
        source_latent_width = int(group.get("source_latent_w", -1))
        source_latent_height = int(group.get("source_latent_h", -1))
        if min(
            source_width,
            source_height,
            source_latent_width,
            source_latent_height,
        ) < 1:
            raise PixelVaeResizeError("source pixel/latent geometry is invalid")
        if (
            source_width % source_latent_width
            or source_height % source_latent_height
        ):
            raise PixelVaeResizeError(
                "source pixel/latent geometry is not integral"
            )
        group_scale = (
            source_width // source_latent_width,
            source_height // source_latent_height,
        )
        if scale is None:
            scale = group_scale
        elif scale != group_scale:
            raise PixelVaeResizeError(
                "source pixel/latent scale differs between physical groups"
            )

    assert scale is not None
    return scale


def _latent_samples(
    latent: Any,
    *,
    position: int,
    group: Mapping[str, Any],
) -> torch.Tensor:
    if not isinstance(latent, Mapping) or "samples" not in latent:
        raise PixelVaeResizeError(
            f"video_latents[{position}] must be a LATENT mapping with samples"
        )
    samples = latent["samples"]
    if not isinstance(samples, torch.Tensor) or samples.ndim != 5:
        raise PixelVaeResizeError("video latent must have shape [B,C,T,H,W]")
    batch, channels, temporal, height, width = (
        int(value) for value in samples.shape
    )
    expected = (
        int(group.get("source_batch", -1)),
        int(group.get("latent_channels", -1)),
        int(group.get("source_latent_t", -1)),
        int(group.get("source_latent_h", -1)),
        int(group.get("source_latent_w", -1)),
    )
    if (batch, channels, temporal, height, width) != expected:
        raise PixelVaeResizeError(
            "video latent shape or physical group order changed"
        )
    if channels != 24:
        raise PixelVaeResizeError("MiniMax H3 video latent must have 24 channels")
    if not bool(torch.isfinite(samples).all()):
        raise PixelVaeResizeError("input video latent contains NaN or Inf")
    return samples


def _resize_one_group(
    samples: torch.Tensor,
    *,
    video_vae: Any,
    source_width: int,
    source_height: int,
    target_width: int,
    target_height: int,
    target_latent_width: int,
    target_latent_height: int,
    upscale_method: str,
    upscale_fn: Callable[..., Any],
) -> torch.Tensor:
    """Decode, resize, and encode one group so its pixel buffer dies per call."""

    decoded_pixels = video_vae.decode(samples)
    if not isinstance(decoded_pixels, torch.Tensor) or decoded_pixels.ndim != 5:
        raise PixelVaeResizeError(
            "Video VAE decode must return pixels with shape [B,F,H,W,C]"
        )
    batch, frames, pixel_height, pixel_width, channels = (
        int(value) for value in decoded_pixels.shape
    )
    if batch != int(samples.shape[0]):
        raise PixelVaeResizeError("Video VAE decode changed the batch size")
    if frames < 1 or channels != 3:
        raise PixelVaeResizeError(
            "Video VAE decode returned invalid frame or channel geometry"
        )
    if (pixel_width, pixel_height) != (source_width, source_height):
        raise PixelVaeResizeError(
            "Video VAE decode geometry differs from the assembly plan"
        )
    for frame_start in range(0, frames, _PIXEL_RESIZE_FRAME_BATCH):
        if not bool(
            torch.isfinite(
                decoded_pixels[
                    :,
                    frame_start : frame_start + _PIXEL_RESIZE_FRAME_BATCH,
                ]
            ).all()
        ):
            raise PixelVaeResizeError("Video VAE decode contains NaN or Inf")

    # Pixel resizing is intentionally CPU-owned. Core's Lanczos implementation
    # is CPU/PIL-based already, and this also avoids retaining a full video-sized
    # resize workspace in VRAM under --gpu-only configurations.
    pixels = decoded_pixels.detach().to("cpu").contiguous()
    del decoded_pixels

    # Core common_upscale is a 4D image boundary. Make B*F explicit so video
    # frame order is unambiguous. Resize bounded frame batches into one CPU
    # [B,F,H,W,C] buffer required by the temporal H3 VAE encoder.
    source_flat = pixels.reshape(
        batch * frames, pixel_height, pixel_width, channels
    )
    resized_pixels = torch.empty(
        (batch, frames, target_height, target_width, channels),
        dtype=pixels.dtype,
        device="cpu",
    )
    target_flat = resized_pixels.reshape(
        batch * frames, target_height, target_width, channels
    )
    for frame_start in range(
        0,
        batch * frames,
        _PIXEL_RESIZE_FRAME_BATCH,
    ):
        frame_stop = min(
            frame_start + _PIXEL_RESIZE_FRAME_BATCH,
            batch * frames,
        )
        pixel_nchw = (
            source_flat[frame_start:frame_stop]
            .movedim(-1, 1)
            .contiguous()
        )
        resized_nchw = upscale_fn(
            pixel_nchw,
            int(target_width),
            int(target_height),
            upscale_method,
            "disabled",
        )
        expected_resize_shape = (
            frame_stop - frame_start,
            channels,
            target_height,
            target_width,
        )
        if not isinstance(resized_nchw, torch.Tensor) or tuple(
            resized_nchw.shape
        ) != expected_resize_shape:
            raise PixelVaeResizeError("Core pixel resize returned invalid geometry")
        resized_nchw = resized_nchw.detach().to("cpu")
        if not bool(torch.isfinite(resized_nchw).all()):
            raise PixelVaeResizeError("Core pixel resize contains NaN or Inf")
        target_flat[frame_start:frame_stop].copy_(
            resized_nchw.movedim(1, -1)
        )
        del pixel_nchw, resized_nchw

    del pixels, source_flat, target_flat

    # Match Core VAEEncode exactly: H3's VAE wrapper expects a 4D IMAGE batch
    # and promotes its frame axis to one temporal video batch. Passing the 5D
    # [B,F,H,W,C] tensor directly makes Core crop F as if it were spatial.
    # Encode each Continuum batch independently, then restore B explicitly.
    encoded_batches: list[torch.Tensor] = []
    expected_batch_shape = (
        1,
        int(samples.shape[1]),
        int(samples.shape[2]),
        int(target_latent_height),
        int(target_latent_width),
    )
    for batch_index in range(batch):
        encoded_batch = video_vae.encode(resized_pixels[batch_index])
        if not isinstance(encoded_batch, torch.Tensor) or encoded_batch.ndim != 5:
            raise PixelVaeResizeError(
                "Video VAE encode must return a latent with shape [B,C,T,H,W]"
            )
        if int(encoded_batch.shape[0]) != 1:
            raise PixelVaeResizeError(
                "Core Video VAE Encode must return one batch per IMAGE sequence"
            )
        encoded_batch_shape = tuple(int(value) for value in encoded_batch.shape)
        if encoded_batch_shape != expected_batch_shape:
            raise PixelVaeResizeError(
                "Video VAE encode changed B/C/T or returned the wrong target H/W "
                f"for batch {batch_index}: expected {expected_batch_shape}, "
                f"got {encoded_batch_shape}"
            )
        encoded_batches.append(encoded_batch)
    encoded = (
        encoded_batches[0]
        if len(encoded_batches) == 1
        else torch.cat(encoded_batches, dim=0)
    )
    if not isinstance(encoded, torch.Tensor) or encoded.ndim != 5:
        raise PixelVaeResizeError(
            "Video VAE encode must return a latent with shape [B,C,T,H,W]"
        )
    expected_shape = (
        int(samples.shape[0]),
        int(samples.shape[1]),
        int(samples.shape[2]),
        int(target_latent_height),
        int(target_latent_width),
    )
    if tuple(int(value) for value in encoded.shape) != expected_shape:
        raise PixelVaeResizeError(
            "Video VAE encode changed B/C/T or returned the wrong target H/W: "
            f"expected {expected_shape}, got {tuple(int(value) for value in encoded.shape)}"
        )
    if not bool(torch.isfinite(encoded).all()):
        raise PixelVaeResizeError("Video VAE encode contains NaN or Inf")

    # Continuum stores accepted physical latents on CPU; do not retain one GPU
    # allocation per physical group while later groups are being converted.
    output = encoded.detach().to("cpu").contiguous()
    del resized_pixels, encoded_batches, encoded
    return output


@torch.inference_mode()
def resize_video_latents_via_vae(
    video_latents: Sequence[Mapping[str, Any]],
    assembly_plan: Mapping[str, Any],
    *,
    video_vae: Any,
    target_width: int,
    target_height: int,
    upscale_method: str = "lanczos",
    upscale_fn: Callable[..., Any] | None = None,
) -> list[dict[str, Any]]:
    """Resize physical groups sequentially through the connected H3 Video VAE.

    ``target_width`` and ``target_height`` are pixel dimensions. The expected
    encoded latent geometry is derived exclusively from assembly-plan metadata.
    VAE failures are intentionally not caught: Core owns its OOM/tiled fallback,
    and this path must never fall back to direct latent interpolation.
    """

    groups = _contract_groups(assembly_plan)
    if (
        not isinstance(video_latents, Sequence)
        or isinstance(video_latents, (str, bytes))
        or len(video_latents) != len(groups)
    ):
        raise PixelVaeResizeError("video latent group count changed")
    if (
        video_vae is None
        or not callable(getattr(video_vae, "decode", None))
        or not callable(getattr(video_vae, "encode", None))
    ):
        raise PixelVaeResizeError("a usable H3 Video VAE is required")
    if upscale_method not in PIXEL_UPSCALE_METHODS:
        raise PixelVaeResizeError(
            f"unsupported pixel upscale method {upscale_method!r}"
        )
    target_width = int(target_width)
    target_height = int(target_height)
    if target_width < 1 or target_height < 1:
        raise PixelVaeResizeError("target pixel width and height must be positive")

    scale_width, scale_height = resolve_pixel_latent_scale(assembly_plan)
    if target_width % scale_width or target_height % scale_height:
        raise PixelVaeResizeError(
            "target pixel geometry is not aligned to the plan-derived latent scale"
        )
    target_latent_width = target_width // scale_width
    target_latent_height = target_height // scale_height
    if upscale_fn is None:
        from comfy.utils import common_upscale

        upscale_fn = common_upscale

    outputs: list[dict[str, Any]] = []
    for position, (latent, group) in enumerate(
        zip(video_latents, groups, strict=True)
    ):
        samples = _latent_samples(latent, position=position, group=group)
        source_width = int(group["source_width"])
        source_height = int(group["source_height"])
        resized_samples = _resize_one_group(
            samples,
            video_vae=video_vae,
            source_width=source_width,
            source_height=source_height,
            target_width=target_width,
            target_height=target_height,
            target_latent_width=target_latent_width,
            target_latent_height=target_latent_height,
            upscale_method=upscale_method,
            upscale_fn=upscale_fn,
        )
        output = dict(latent)
        output["samples"] = resized_samples
        outputs.append(output)

    return outputs
