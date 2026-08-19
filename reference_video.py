"""Persistent MiniMax H3 video-reference conditioning for the V3.4 sampler."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any

import torch


REFERENCE_VIDEO_CONTRACT_VERSION = 1
REFERENCE_VIDEO_PREPROCESS_VERSION = 2
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


class ReferenceVideoError(ValueError):
    pass


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _tensor_hash(value: torch.Tensor) -> str:
    tensor = value.detach().to(device="cpu").contiguous()
    digest = hashlib.sha256()
    digest.update(str(tuple(int(v) for v in tensor.shape)).encode("ascii"))
    digest.update(str(tensor.dtype).encode("ascii"))
    digest.update(tensor.numpy().tobytes(order="C"))
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
    frames = reference_video_1[:, :, :, :3].detach().to(
        device="cpu", dtype=torch.float32
    ).contiguous()
    if not bool(torch.isfinite(frames).all().item()):
        raise ReferenceVideoError("Video Reference contains NaN or infinity")
    source_shape = tuple(int(value) for value in frames.shape)
    source_sha256 = _tensor_hash(frames)
    frame_count = min(int(frames.shape[0]), int(target_frames))
    if frame_count < 5:
        raise ReferenceVideoError("Video Reference requires at least 5 frames")
    while frame_count > 5 and frame_count % 17 != 5:
        frame_count -= 1
    normalized_size_mode = (
        str(size_mode)
        if str(size_mode) in REFERENCE_VIDEO_SIZE_OPTIONS
        else REFERENCE_VIDEO_SIZE_EFFICIENT
    )
    target_width, target_height = _resolved_size(
        int(frames.shape[2]),
        int(frames.shape[1]),
        output_width=int(output_width),
        output_height=int(output_height),
        size_mode=normalized_size_mode,
    )
    contract_base = {
        "reference_video_contract_version": REFERENCE_VIDEO_CONTRACT_VERSION,
        "source_shape": list(source_shape),
        "source_dtype": str(frames.dtype),
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
        source_dtype=str(frames.dtype),
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
    frames = source.frames[: source.frame_count]
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
