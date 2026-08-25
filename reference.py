"""MiniMax H3 image-reference adapter for the V3 production sampler.

This module only builds the public Core conditioning contract.  It does not
own model loading, sampling, VAE decoding, or any optimizer implementation.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import math
import re
from typing import Any

import torch


REFERENCE_CONTRACT_VERSION = 1
REFERENCE_PREPROCESS_VERSION = 1
HYBRID_PRESENTATION_VERSION = 1
REFERENCE_SIZE_MATCH_OUTPUT = "Match Output"
REFERENCE_SIZE_MAX_IDENTITY = "Max Identity"
REFERENCE_SIZE_OPTIONS = (
    REFERENCE_SIZE_MATCH_OUTPUT,
    REFERENCE_SIZE_MAX_IDENTITY,
)
_CANVAS_MULTIPLE = 32
_MAX_IDENTITY_SHORT_EDGE = 2048
_PICTURE_TAG = re.compile(r"<Picture\s+(\d+)>")


class ReferenceConditioningError(ValueError):
    pass


@dataclass(frozen=True)
class ReferenceAssets:
    images: tuple[torch.Tensor, ...]
    latents: tuple[torch.Tensor | None, ...]
    image_hashes: tuple[str, ...]
    combined_hash: str
    size_mode: str

    @property
    def count(self) -> int:
        return len(self.images)

    @property
    def contract(self) -> dict[str, Any]:
        result = {
            "reference_contract_version": REFERENCE_CONTRACT_VERSION,
            "count": self.count,
            "size_mode": self.size_mode,
            "image_hashes": list(self.image_hashes),
            "combined_hash": self.combined_hash,
        }
        # Preserve the V3.2.2 JSON contract byte-for-byte for zero, one, and
        # two references. The V3.2.3 extension exists only when Image 3 is
        # connected, so removing it can resolve back to an older Revision.
        if self.count == 3:
            image = self.images[2]
            result["reference_image_3"] = {
                "reference_position": 3,
                "shape": [int(value) for value in image.shape],
                "dtype": str(image.dtype),
                "sha256": self.image_hashes[2],
                "preprocess_version": REFERENCE_PREPROCESS_VERSION,
            }
        return result


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
    return max(_CANVAS_MULTIPLE, int(round(value / _CANVAS_MULTIPLE)) * _CANVAS_MULTIPLE)


def _validate_image(name: str, image: torch.Tensor) -> torch.Tensor:
    if not torch.is_tensor(image) or image.ndim != 4:
        raise ReferenceConditioningError(f"{name} must be a ComfyUI IMAGE tensor")
    if int(image.shape[0]) < 1 or int(image.shape[1]) < 1 or int(image.shape[2]) < 1:
        raise ReferenceConditioningError(f"{name} is empty")
    if int(image.shape[0]) != 1:
        raise ReferenceConditioningError(
            f"{name} must contain exactly one image (batch size B=1)"
        )
    if int(image.shape[-1]) < 3:
        raise ReferenceConditioningError(f"{name} must have RGB channels")
    return image[:, :, :, :3]


def _resize_reference(
    image: torch.Tensor,
    *,
    output_width: int,
    output_height: int,
    size_mode: str,
) -> torch.Tensor:
    if size_mode not in REFERENCE_SIZE_OPTIONS:
        raise ReferenceConditioningError(f"unknown Reference Size: {size_mode!r}")
    source_height = int(image.shape[1])
    source_width = int(image.shape[2])
    if size_mode == REFERENCE_SIZE_MATCH_OUTPUT:
        target_area = float(int(output_width) * int(output_height))
        scale = min(1.0, math.sqrt(target_area / float(source_width * source_height)))
    else:
        scale = min(1.0, float(_MAX_IDENTITY_SHORT_EDGE) / min(source_width, source_height))
    target_width = _round_canvas(source_width * scale)
    target_height = _round_canvas(source_height * scale)
    if target_width == source_width and target_height == source_height:
        return image.contiguous()
    try:
        import comfy.utils
    except Exception as exc:
        raise ReferenceConditioningError(
            "ComfyUI Core image resize support is unavailable"
        ) from exc
    channels_first = image.movedim(-1, 1)
    resized = comfy.utils.common_upscale(
        channels_first,
        target_width,
        target_height,
        "lanczos",
        "disabled",
    )
    return resized.movedim(1, -1).contiguous()


def prepare_reference_assets(
    *,
    reference_image_1: torch.Tensor | None,
    reference_image_2: torch.Tensor | None,
    output_width: int,
    output_height: int,
    size_mode: str,
    reference_image_3: torch.Tensor | None = None,
) -> ReferenceAssets | None:
    # Match Core's dynamic Reference inputs: bypassed or otherwise absent
    # sockets are ignored, then active images are numbered contiguously in
    # connection order as Picture 1..N.
    inputs = [
        image
        for image in (reference_image_1, reference_image_2, reference_image_3)
        if image is not None
    ]
    if not inputs:
        return None
    images = tuple(
        _resize_reference(
            _validate_image(f"Reference Image {index}", image),
            output_width=int(output_width),
            output_height=int(output_height),
            size_mode=size_mode,
        )
        for index, image in enumerate(inputs, start=1)
    )
    image_hashes = tuple(_tensor_hash(image) for image in images)
    combined_hash = _canonical_hash(
        {
            "reference_contract_version": REFERENCE_CONTRACT_VERSION,
            "size_mode": size_mode,
            "image_hashes": list(image_hashes),
        }
    )
    return ReferenceAssets(
        images=images,
        latents=tuple(None for _ in images),
        image_hashes=image_hashes,
        combined_hash=combined_hash,
        size_mode=size_mode,
    )


def encode_reference_latents(video_vae: Any, assets: ReferenceAssets) -> ReferenceAssets:
    if all(latent is not None for latent in assets.latents):
        return assets
    latents = tuple(video_vae.encode(image) for image in assets.images)
    return replace(assets, latents=latents)


def build_hybrid_presentation_items(
    reference_items: list[dict[str, Any]],
    *,
    first_image: torch.Tensor | None = None,
    last_image: torch.Tensor | None = None,
) -> list[dict[str, Any]]:
    """Build the Core Qwen Picture list without changing DiT payloads."""
    items: list[dict[str, Any]] = []
    if first_image is not None:
        items.append({"type": "image", "data": first_image})
    if last_image is not None:
        items.append({"type": "image", "data": last_image})
    items.extend(dict(item) for item in reference_items)
    return items


def combine_hybrid_visual_identity(
    *,
    keyframe_identity_hash: str,
    reference_assets: ReferenceAssets | None,
    has_first: bool,
    has_last: bool,
) -> str:
    """Preserve pure-mode identity and version only the hybrid contract."""
    if reference_assets is None:
        return str(keyframe_identity_hash)
    if not has_first and not has_last:
        return reference_assets.combined_hash
    return _canonical_hash(
        {
            "hybrid_visual_identity_version": 1,
            "hybrid_presentation_version": HYBRID_PRESENTATION_VERSION,
            "keyframe_identity_hash": str(keyframe_identity_hash),
            "reference_hash": reference_assets.combined_hash,
        }
    )


def validate_reference_prompts(
    prompts: list[str],
    reference_count: int,
    picture_offset: int = 0,
) -> str:
    reference_count = max(0, int(reference_count))
    picture_offset = max(0, int(picture_offset))
    found: set[int] = set()
    for prompt in prompts:
        found.update(int(value) for value in _PICTURE_TAG.findall(str(prompt)))

    first_reference = picture_offset + 1
    last_reference = picture_offset + reference_count
    found_references = {
        value for value in found if first_reference <= value <= last_reference
    }
    invalid = sorted(value for value in found if value < 1 or value > last_reference)
    warnings: list[str] = []
    if invalid:
        unavailable = ", ".join(f"<Picture {value}>" for value in invalid)
        warnings.append(
            f"H3C-P102 Warning: prompt references unavailable {unavailable}; only "
            f"{reference_count} active reference image(s) reached the Sampler. "
            "ComfyUI Core permits this and generation will continue, but the "
            "unavailable reference may be ignored or hallucinated. Enable the "
            "corresponding Reference Image input or remove the unavailable tag."
        )

    expected_references = set(range(first_reference, last_reference + 1))
    missing = sorted(expected_references - found_references)
    if missing:
        labels = ", ".join(f"<Picture {value}>" for value in missing)
        detail = (
            "the prompt contains no <Picture N> tag"
            if picture_offset == 0 and not found
            else f"connected reference {labels} is not explicitly mentioned in the prompt"
        )
        warnings.append(
            f"H3C-P103 Warning: {detail}; images still condition generation, but "
            "explicit identity references are recommended."
        )
    return "\n".join(warnings)


def encode_reference_prompt(
    clip: Any,
    prompt: str,
    assets: ReferenceAssets,
    first_image: torch.Tensor | None = None,
    last_image: torch.Tensor | None = None,
    reference_audio_assets=None,
    timeline_video_assets=None,
) -> list[list[Any]]:
    if any(latent is None for latent in assets.latents):
        raise ReferenceConditioningError("reference latents were not encoded")
    reference_items = [
        {"type": "image", "data": image}
        for image in assets.images
    ]
    if timeline_video_assets is not None:
        reference_items.append(dict(timeline_video_assets.item))
    if reference_audio_assets is not None:
        from .reference_audio import reference_audio_item

        reference_items.append(reference_audio_item())
    presentation_items = build_hybrid_presentation_items(
        reference_items,
        first_image=first_image,
        last_image=last_image,
    )
    try:
        tokens = clip.tokenize(str(prompt), minimax_ref_items=presentation_items)
    except TypeError as exc:
        raise ReferenceConditioningError(
            "This ComfyUI Core/CLIP does not support MiniMax H3 image references"
        ) from exc
    conditioning = clip.encode_from_tokens_scheduled(tokens)
    refs = []
    for image, latent in zip(assets.images, assets.latents, strict=True):
        refs.append(
            {
                "kind": "image",
                "latent_h": int(image.shape[1]) // 16,
                "latent_w": int(image.shape[2]) // 16,
                "latent": latent,
            }
        )
    if timeline_video_assets is not None:
        refs.append(dict(timeline_video_assets.block))
    if reference_audio_assets is not None:
        from .reference_audio import reference_audio_block

        refs.append(reference_audio_block(reference_audio_assets))
    return [
        [tensor, {**dict(metadata), "minimax_refs": list(refs)}]
        for tensor, metadata in conditioning
    ]
