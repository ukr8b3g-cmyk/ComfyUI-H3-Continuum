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
        return {
            "reference_contract_version": REFERENCE_CONTRACT_VERSION,
            "count": self.count,
            "size_mode": self.size_mode,
            "image_hashes": list(self.image_hashes),
            "combined_hash": self.combined_hash,
        }


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
    if int(image.shape[-1]) < 3:
        raise ReferenceConditioningError(f"{name} must have RGB channels")
    return image[:1, :, :, :3]


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
) -> ReferenceAssets | None:
    if reference_image_1 is None:
        if reference_image_2 is not None:
            raise ReferenceConditioningError(
                "Reference Image 2 requires Reference Image 1"
            )
        return None
    inputs = [reference_image_1]
    if reference_image_2 is not None:
        inputs.append(reference_image_2)
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


def validate_reference_prompts(prompts: list[str], reference_count: int) -> str:
    found: set[int] = set()
    for prompt in prompts:
        found.update(int(value) for value in _PICTURE_TAG.findall(str(prompt)))
    invalid = sorted(value for value in found if value < 1 or value > reference_count)
    if invalid:
        raise ReferenceConditioningError(
            f"Prompt references unavailable <Picture {invalid[0]}>; "
            f"connected reference count is {reference_count}"
        )
    if not found:
        return (
            "Reference images are connected but the prompt contains no "
            "<Picture N> tag; images still condition generation, but explicit "
            "identity references are recommended."
        )
    return ""


def encode_reference_prompt(
    clip: Any,
    prompt: str,
    assets: ReferenceAssets,
) -> list[list[Any]]:
    if any(latent is None for latent in assets.latents):
        raise ReferenceConditioningError("reference latents were not encoded")
    reference_items = [
        {"type": "image", "data": image}
        for image in assets.images
    ]
    try:
        tokens = clip.tokenize(str(prompt), minimax_ref_items=reference_items)
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
    return [
        [tensor, {**dict(metadata), "minimax_refs": list(refs)}]
        for tensor, metadata in conditioning
    ]
