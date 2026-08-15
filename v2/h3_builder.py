"""Native MiniMax H3 conditioning and latent construction for V2.

All expensive image/VAE work is performed before the sampling phase. Prompt
conditioning is cached per unique prompt and image presentation.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

import torch

from ..continuation import clone_conditioning
from ..temporal import audio_latent_t, video_latent_t


@dataclass(slots=True)
class IdentityAssets:
    first_image: torch.Tensor | None
    first_latent: torch.Tensor | None
    last_image: torch.Tensor | None
    last_latent: torch.Tensor | None
    identity_hash: str

    @property
    def first_frame_hash(self) -> str:
        """Version-neutral alias retained alongside the legacy identity hash."""
        return self.identity_hash

    @property
    def last_frame_hash(self) -> str:
        """Fingerprint the resized final keyframe independently from identity."""
        return _tensor_fingerprint(self.last_image)


def _tensor_fingerprint(tensor: torch.Tensor | None) -> str:
    if tensor is None:
        return "none"
    sample = tensor.detach().to("cpu").contiguous()
    digest = hashlib.sha256()
    digest.update(str(tuple(int(value) for value in sample.shape)).encode("ascii"))
    digest.update(str(sample.dtype).encode("ascii"))
    digest.update(sample.view(torch.uint8).numpy().tobytes(order="C"))
    return digest.hexdigest()


def resize_h3_image(image: torch.Tensor, width: int, height: int, crop: str) -> torch.Tensor:
    try:
        import comfy.utils
    except Exception as exc:  # pragma: no cover - ComfyUI runtime only
        raise RuntimeError(f"ComfyUI resize helper unavailable: {exc}") from exc
    if not torch.is_tensor(image) or image.ndim != 4 or image.shape[-1] < 3:
        raise ValueError("H3 image input must be [B,H,W,C] with at least three channels")
    samples = image[:1, ..., :3].movedim(-1, 1)
    resized = comfy.utils.common_upscale(samples, int(width), int(height), "lanczos", crop)
    return resized.movedim(1, -1).contiguous()


def prepare_identity_assets(
    video_vae: Any,
    *,
    width: int,
    height: int,
    first_frame: torch.Tensor | None,
    last_frame: torch.Tensor | None,
    encode_latents: bool = True,
) -> IdentityAssets:
    first_image = first_latent = last_image = last_latent = None
    if first_frame is not None:
        first_image = resize_h3_image(first_frame, width, height, "disabled")
        if encode_latents:
            first_latent = video_vae.encode(first_image)
    if last_frame is not None:
        last_image = resize_h3_image(last_frame, width, height, "center")
        if encode_latents:
            last_latent = video_vae.encode(last_image)
    return IdentityAssets(
        first_image=first_image,
        first_latent=first_latent,
        last_image=last_image,
        last_latent=last_latent,
        identity_hash=_tensor_fingerprint(first_image),
    )


def encode_prompt_conditioning(
    clip: Any,
    prompt: str,
    *,
    first_image: torch.Tensor | None,
    last_image: torch.Tensor | None,
    reference_audio_assets=None,
) -> list:
    images = []
    if first_image is not None:
        images.append(first_image)
    if last_image is not None:
        images.append(last_image)
    tokenize_options = {"images": images}
    if reference_audio_assets is not None:
        from ..reference_audio import reference_audio_item

        tokenize_options = {
            "minimax_ref_items": [
                *({"type": "image", "data": image} for image in images),
                reference_audio_item(),
            ]
        }
    tokens = clip.tokenize(str(prompt), **tokenize_options)
    conditioning = clip.encode_from_tokens_scheduled(tokens)
    if reference_audio_assets is None:
        return conditioning
    from ..reference_audio import reference_audio_block

    audio_ref = reference_audio_block(reference_audio_assets)
    return [
        [tensor, {**dict(metadata), "minimax_refs": [dict(audio_ref)]}]
        for tensor, metadata in conditioning
    ]


def attach_keyframes(
    conditioning: list,
    *,
    frame_count: int,
    first_latent: torch.Tensor | None,
    last_latent: torch.Tensor | None,
) -> list:
    output = clone_conditioning(conditioning)
    keyframes: list[dict[str, Any]] = []
    if first_latent is not None:
        keyframes.append({"resolved_frame_index": 0, "latent": first_latent})
    if last_latent is not None:
        keyframes.append(
            {"resolved_frame_index": int(frame_count) - 1, "latent": last_latent}
        )
    for _, metadata in output:
        if keyframes:
            metadata["minimax_keyframes"] = [dict(item) for item in keyframes]
            metadata["minimax_frame_count"] = int(frame_count)
        else:
            metadata.pop("minimax_keyframes", None)
            metadata["minimax_frame_count"] = int(frame_count)
    return output


def empty_h3_latent(width: int, height: int, frame_count: int) -> dict[str, Any]:
    try:
        import comfy.model_management
        import comfy.nested_tensor
    except Exception as exc:  # pragma: no cover - ComfyUI runtime only
        raise RuntimeError(f"ComfyUI H3 latent helpers unavailable: {exc}") from exc
    width = int(width)
    height = int(height)
    frame_count = int(frame_count)
    if width <= 0 or height <= 0 or width % 32 or height % 32:
        raise ValueError("H3 width and height must be positive multiples of 32")
    device = comfy.model_management.intermediate_device()
    video = torch.zeros(
        (1, 24, video_latent_t(frame_count), height // 16, width // 16),
        device=device,
        dtype=torch.float32,
    )
    audio = torch.zeros(
        (1, 32, 2, audio_latent_t(frame_count)),
        device=device,
        dtype=torch.float32,
    )
    return {"samples": comfy.nested_tensor.NestedTensor((video, audio))}


def encode_identity_latents(video_vae: Any, assets: IdentityAssets) -> IdentityAssets:
    """Encode already-resized identity images without changing their fingerprint."""

    first_latent = assets.first_latent
    last_latent = assets.last_latent
    if first_latent is None and assets.first_image is not None:
        first_latent = video_vae.encode(assets.first_image)
    if last_latent is None and assets.last_image is not None:
        last_latent = video_vae.encode(assets.last_image)
    return IdentityAssets(
        first_image=assets.first_image,
        first_latent=first_latent,
        last_image=assets.last_image,
        last_latent=last_latent,
        identity_hash=assets.identity_hash,
    )
