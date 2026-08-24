"""V3.5 Core-compatible spatial resize for physical video latents."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


UPSCALE_METHODS = (
    "nearest-exact",
    "bilinear",
    "area",
    "bicubic",
    "bislerp",
)


def _single_list_input(name: str, value: Any) -> Any:
    if not isinstance(value, list) or len(value) != 1:
        raise ValueError(f"{name} must contain exactly one value")
    return value[0]


def resize_video_latents(
    video_latents: list[dict[str, Any]],
    *,
    upscale_method: str,
    scale_by: float,
    upscale_fn: Callable[..., Any] | None = None,
) -> list[dict[str, Any]]:
    """Resize only spatial H/W through the ComfyUI Core latent implementation."""

    if upscale_fn is None:
        from comfy.utils import common_upscale

        upscale_fn = common_upscale

    resized: list[dict[str, Any]] = []
    for latent in video_latents:
        samples = latent["samples"]
        width = round(samples.shape[-1] * scale_by)
        height = round(samples.shape[-2] * scale_by)
        output = latent.copy()
        output["samples"] = upscale_fn(
            samples,
            width,
            height,
            upscale_method,
            "disabled",
        )
        resized.append(output)
    return resized


def resize_video_latents_to_size(
    video_latents: list[dict[str, Any]],
    *,
    upscale_method: str,
    target_width: int,
    target_height: int,
    upscale_fn: Callable[..., Any] | None = None,
) -> list[dict[str, Any]]:
    """Resize every physical video group to one exact latent H/W."""

    if target_width < 1 or target_height < 1:
        raise ValueError("target latent width and height must be positive")
    if upscale_fn is None:
        from comfy.utils import common_upscale

        upscale_fn = common_upscale

    resized: list[dict[str, Any]] = []
    for latent in video_latents:
        samples = latent["samples"]
        output = latent.copy()
        output["samples"] = upscale_fn(
            samples,
            int(target_width),
            int(target_height),
            upscale_method,
            "disabled",
        )
        resized.append(output)
    return resized


class H3ContinuumLatentResizeV35:
    """List-aware Core spatial resize for Continuum physical video groups."""

    DEPRECATED = False
    DESCRIPTION = (
        "V3.5 Hi-res fix resize. Spatially resizes every Continuum "
        "physical video LATENT with the selected ComfyUI Core interpolation method. "
        "B/C/T, physical group order, and LATENT metadata are preserved."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "video_latents": ("LATENT",),
                "upscale_method": (UPSCALE_METHODS,),
                "scale_by": (
                    "FLOAT",
                    {
                        "default": 2.0,
                        "min": 0.01,
                        "max": 8.0,
                        "step": 0.01,
                    },
                ),
            }
        }

    INPUT_IS_LIST = True
    RETURN_TYPES = ("LATENT",)
    RETURN_NAMES = ("resized_video_latents",)
    OUTPUT_IS_LIST = (True,)
    FUNCTION = "resize"
    CATEGORY = "MiniMax H3/Continuum/Utilities"

    def resize(self, video_latents, upscale_method, scale_by):
        return (
            resize_video_latents(
                video_latents,
                upscale_method=str(
                    _single_list_input("upscale_method", upscale_method)
                ),
                scale_by=float(_single_list_input("scale_by", scale_by)),
            ),
        )


NODE_CLASS_MAPPINGS = {
    "H3ContinuumLatentResizeV35": H3ContinuumLatentResizeV35,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "H3ContinuumLatentResizeV35": "H3 Continuum Latent Resize V3.5",
}
