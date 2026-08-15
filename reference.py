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


def validate_reference_prompts(prompts: list[str], reference_count: int) -> str:
    found: set[int] = set()
    for prompt in prompts:
        found.update(int(value) for value in _PICTURE_TAG.findall(str(prompt)))
    invalid = sorted(value for value in found if value < 1 or value > reference_count)
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
    missing = sorted(set(range(1, reference_count + 1)) - found)
    if missing:
        labels = ", ".join(f"<Picture {value}>" for value in missing)
        detail = (
            "the prompt contains no <Picture N> tag"
            if not found
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
    reference_audio_assets=None,
) -> list[list[Any]]:
    if any(latent is None for latent in assets.latents):
        raise ReferenceConditioningError("reference latents were not encoded")
    reference_items = [
        {"type": "image", "data": image}
        for image in assets.images
    ]
    if reference_audio_assets is not None:
        from .reference_audio import reference_audio_item

        reference_items.append(reference_audio_item())
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
    if reference_audio_assets is not None:
        from .reference_audio import reference_audio_block

        refs.append(reference_audio_block(reference_audio_assets))
    return [
        [tensor, {**dict(metadata), "minimax_refs": list(refs)}]
        for tensor, metadata in conditioning
    ]
