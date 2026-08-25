"""Persistent MiniMax H3 video-reference conditioning for the V3.4 sampler."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any

import torch

from .temporal import align_frame_count_up


REFERENCE_VIDEO_CONTRACT_VERSION = 1
REFERENCE_VIDEO_PREPROCESS_VERSION = 3
REFERENCE_VIDEO_SIZE_EFFICIENT = "Efficient - 0.4 MP"
REFERENCE_VIDEO_SIZE_BALANCED = "Balanced - 0.6 MP"
REFERENCE_VIDEO_SIZE_MATCH_OUTPUT = "Match Output"
REFERENCE_VIDEO_SIZE_OPTIONS = (
    REFERENCE_VIDEO_SIZE_EFFICIENT,
    REFERENCE_VIDEO_SIZE_BALANCED,
    REFERENCE_VIDEO_SIZE_MATCH_OUTPUT,
)
_CANVAS_MULTIPLE = 32
_EFFICIENT_AREA = 400_000
_BALANCED_AREA = 600_000
_SOURCE_FPS = 24
_HASH_CHUNK_FRAMES = 8


class ReferenceVideoError(ValueError):
    pass


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _tensor_hash(value: torch.Tensor) -> str:
    tensor = value.detach()
    digest = hashlib.sha256()
    digest.update(str(tuple(int(v) for v in tensor.shape)).encode("ascii"))
    digest.update(str(tensor.dtype).encode("ascii"))
    for start in range(0, int(tensor.shape[0]), _HASH_CHUNK_FRAMES):
        chunk = tensor[start : start + _HASH_CHUNK_FRAMES].to(
            device="cpu"
        ).contiguous()
        digest.update(chunk.numpy().tobytes(order="C"))
    return digest.hexdigest()


def _round_canvas(value: float) -> int:
    return max(
        _CANVAS_MULTIPLE,
        int(round(float(value) / _CANVAS_MULTIPLE)) * _CANVAS_MULTIPLE,
    )


def _resolved_size(
    source_width: int,
    source_height: int,
    *,
    output_width: int,
    output_height: int,
    size_mode: str,
) -> tuple[int, int]:
    if size_mode == REFERENCE_VIDEO_SIZE_MATCH_OUTPUT:
        target_area = int(output_width) * int(output_height)
    elif size_mode == REFERENCE_VIDEO_SIZE_BALANCED:
        target_area = _BALANCED_AREA
    else:
        target_area = _EFFICIENT_AREA
    source_area = int(source_width) * int(source_height)
    scale = min(1.0, math.sqrt(float(target_area) / float(source_area)))
    target_width = _round_canvas(int(source_width) * scale)
    target_height = _round_canvas(int(source_height) * scale)
    if source_width >= _CANVAS_MULTIPLE:
        target_width = min(
            target_width,
            max(_CANVAS_MULTIPLE, (int(source_width) // _CANVAS_MULTIPLE) * _CANVAS_MULTIPLE),
        )
    if source_height >= _CANVAS_MULTIPLE:
        target_height = min(
            target_height,
            max(_CANVAS_MULTIPLE, (int(source_height) // _CANVAS_MULTIPLE) * _CANVAS_MULTIPLE),
        )
    return target_width, target_height


@dataclass(frozen=True)
class ReferenceVideoSource:
    frames: torch.Tensor
    source_shape: tuple[int, ...]
    source_dtype: str
    source_sha256: str
    size_mode: str
    target_width: int
    target_height: int
    frame_count: int
    combined_hash: str

    @property
    def contract(self) -> dict[str, Any]:
        return {
            "reference_video_contract_version": REFERENCE_VIDEO_CONTRACT_VERSION,
            "source_shape": list(self.source_shape),
            "source_dtype": self.source_dtype,
            "source_sha256": self.source_sha256,
            "source_fps": _SOURCE_FPS,
            "size_mode": self.size_mode,
            "target_width": self.target_width,
            "target_height": self.target_height,
            "frame_count": self.frame_count,
            "preprocess_version": REFERENCE_VIDEO_PREPROCESS_VERSION,
            "combined_hash": self.combined_hash,
        }


@dataclass(frozen=True)
class ReferenceVideoAssets:
    source: ReferenceVideoSource
    item: dict[str, Any]
    block: dict[str, Any]


def _resolve_reference_frame_count(source_frames: int, target_frames: int) -> int:
    source_count = int(source_frames)
    target_count = int(target_frames)
    if source_count < 5 or target_count < 5:
        raise ReferenceVideoError("Video Reference requires at least 5 frames")
    target_cap = align_frame_count_up(target_count)
    available_count = min(source_count, target_cap)
    return min(align_frame_count_up(available_count), target_cap)


def _fit_reference_frames(frames: torch.Tensor, frame_count: int) -> torch.Tensor:
    requested_count = int(frame_count)
    current_count = int(frames.shape[0])
    if current_count >= requested_count:
        return frames[:requested_count].contiguous()
    if current_count < 1:
        raise ReferenceVideoError("Video Reference contains no frames")
    padding = frames[-1:].expand(requested_count - current_count, -1, -1, -1)
    return torch.cat((frames, padding), dim=0).contiguous()


def _prepare_reference_frames(
    value: torch.Tensor,
    *,
    frame_count: int,
) -> tuple[torch.Tensor, tuple[int, ...], str, str]:
    """Hash the full normalized source while retaining only its used prefix."""

    source_shape = (
        int(value.shape[0]),
        int(value.shape[1]),
        int(value.shape[2]),
        3,
    )
    source_dtype = str(torch.float32)
    retained_count = min(int(source_shape[0]), int(frame_count))
    retained = torch.empty(
        (retained_count, *source_shape[1:]),
        dtype=torch.float32,
        device="cpu",
    )
    digest = hashlib.sha256()
    digest.update(str(source_shape).encode("ascii"))
    digest.update(source_dtype.encode("ascii"))

    for start in range(0, source_shape[0], _HASH_CHUNK_FRAMES):
        stop = min(start + _HASH_CHUNK_FRAMES, source_shape[0])
        chunk = value[start:stop, :, :, :3].detach().to(
            device="cpu", dtype=torch.float32
        ).contiguous()
        if not bool(torch.isfinite(chunk).all().item()):
            raise ReferenceVideoError("Video Reference contains NaN or infinity")
        digest.update(chunk.numpy().tobytes(order="C"))
        if start < retained_count:
            retained_stop = min(stop, retained_count)
            retained[start:retained_stop].copy_(chunk[: retained_stop - start])

    return retained, source_shape, source_dtype, digest.hexdigest()


def prepare_reference_video_source(
    reference_video_1: Any,
    *,
    target_frames: int,
    output_width: int,
    output_height: int,
    size_mode: str = REFERENCE_VIDEO_SIZE_EFFICIENT,
) -> ReferenceVideoSource | None:
    if reference_video_1 is None:
        return None
    if not torch.is_tensor(reference_video_1) or reference_video_1.ndim != 4:
        raise ReferenceVideoError(
            "Video Reference must be a ComfyUI IMAGE batch with shape [T, H, W, C]"
        )
    if int(reference_video_1.shape[-1]) < 3:
        raise ReferenceVideoError("Video Reference must contain RGB channels")
    frame_count = _resolve_reference_frame_count(
        int(reference_video_1.shape[0]),
        int(target_frames),
    )
    frames, source_shape, source_dtype, source_sha256 = _prepare_reference_frames(
        reference_video_1,
        frame_count=frame_count,
    )
    normalized_size_mode = (
        str(size_mode)
        if str(size_mode) in REFERENCE_VIDEO_SIZE_OPTIONS
        else REFERENCE_VIDEO_SIZE_EFFICIENT
    )
    target_width, target_height = _resolved_size(
        int(source_shape[2]),
        int(source_shape[1]),
        output_width=int(output_width),
        output_height=int(output_height),
        size_mode=normalized_size_mode,
    )
    contract_base = {
        "reference_video_contract_version": REFERENCE_VIDEO_CONTRACT_VERSION,
        "source_shape": list(source_shape),
        "source_dtype": source_dtype,
        "source_sha256": source_sha256,
        "source_fps": _SOURCE_FPS,
        "size_mode": normalized_size_mode,
        "target_width": target_width,
        "target_height": target_height,
        "frame_count": frame_count,
        "preprocess_version": REFERENCE_VIDEO_PREPROCESS_VERSION,
    }
    return ReferenceVideoSource(
        frames=frames,
        source_shape=source_shape,
        source_dtype=source_dtype,
        source_sha256=source_sha256,
        size_mode=normalized_size_mode,
        target_width=target_width,
        target_height=target_height,
        frame_count=frame_count,
        combined_hash=_canonical_hash(contract_base),
    )


def encode_reference_video(
    video_vae: Any,
    source: ReferenceVideoSource,
) -> ReferenceVideoAssets:
    available_count = min(int(source.frames.shape[0]), int(source.frame_count))
    frames = source.frames[:available_count]
    if (
        int(frames.shape[2]) != source.target_width
        or int(frames.shape[1]) != source.target_height
    ):
        try:
            import comfy.utils
        except Exception as exc:
            raise ReferenceVideoError(
                "ComfyUI Core image resize support is unavailable"
            ) from exc
        frames = comfy.utils.common_upscale(
            frames.movedim(-1, 1),
            source.target_width,
            source.target_height,
            "lanczos",
            "disabled",
        ).movedim(1, -1).contiguous()
    frames = _fit_reference_frames(frames, source.frame_count)
    try:
        latent = video_vae.encode(frames).detach().to("cpu").contiguous()
    except Exception as exc:
        raise ReferenceVideoError("Video Reference VAE Encode failed") from exc
    qwen_frames = frames[::_SOURCE_FPS // 2].contiguous()
    item = {
        "type": "video",
        "data": qwen_frames,
        "timestamps": [index / 2.0 for index in range(int(qwen_frames.shape[0]))],
    }
    block = {
        "kind": "video",
        "latent_t": int(latent.shape[2]),
        "latent_h": source.target_height // 16,
        "latent_w": source.target_width // 16,
        "ref_audio_t": 0,
        "latent": latent,
        "audio_latent": None,
    }
    return ReferenceVideoAssets(source=source, item=item, block=block)


def combine_reference_video_identity(
    visual_identity_hash: str,
    source: ReferenceVideoSource | None,
) -> str:
    if source is None:
        return str(visual_identity_hash)
    return _canonical_hash(
        {
            "reference_video_identity_version": 1,
            "visual_identity_hash": str(visual_identity_hash),
            "reference_video_hash": source.combined_hash,
        }
    )


def validate_reference_video_prompts(
    prompts: list[str], source: ReferenceVideoSource | None
) -> str:
    if source is None or any("<Video 1>" in str(prompt) for prompt in prompts):
        return ""
    return (
        "H3C-P103 Warning: Video Reference is connected but the prompt contains no "
        "<Video 1> tag; video still conditions generation, but an explicit tag is "
        "recommended."
    )
