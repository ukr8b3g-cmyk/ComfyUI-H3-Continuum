"""V3.5 Continuum-aware Hi-res fix convenience node."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from .pixel_vae_resize import (
    resize_video_latents_via_vae,
    resolve_pixel_latent_scale,
)
from .second_pass import SecondPassContractError, run_second_pass_groups


_MISSING = object()
HIRES_UPSCALE_METHODS = (
    "lanczos",
    "nearest-exact",
    "bilinear",
    "area",
    "bicubic",
    "bislerp",
)
_CONDITIONING_UPSCALE_METHOD = "bilinear"


def _single_list_input(name: str, value: Any) -> Any:
    if not isinstance(value, list) or len(value) != 1:
        raise ValueError(f"{name} must contain exactly one value")
    return value[0]


def _enabled_value(value: Any) -> bool:
    if isinstance(value, list):
        value = _single_list_input("enabled", value)
    return bool(value)


def _lazy_missing(value: Any) -> bool:
    return value is None or (
        isinstance(value, (list, tuple))
        and len(value) == 1
        and value[0] is None
    )


def h3_core_native_canvas(
    width: int,
    height: int,
    *,
    adapt_canvas_fn: Callable[[int, int], tuple[int, int]] | None = None,
) -> tuple[int, int]:
    """Return the native canvas selected by ComfyUI Core for this aspect ratio."""

    if width < 1 or height < 1:
        raise SecondPassContractError("source pixel width and height must be positive")
    if adapt_canvas_fn is None:
        from comfy_extras.nodes_minimax_h3 import adapt_canvas

        adapt_canvas_fn = adapt_canvas
    target = adapt_canvas_fn(int(width), int(height))
    if not isinstance(target, Sequence) or len(target) != 2:
        raise SecondPassContractError("ComfyUI Core adapt_canvas returned invalid geometry")
    target_width, target_height = (int(value) for value in target)
    if target_width < 1 or target_height < 1:
        raise SecondPassContractError("ComfyUI Core adapt_canvas returned invalid geometry")
    return target_width, target_height


def align_h3_manual_canvas(
    current_latent_width: int,
    current_latent_height: int,
    scale_by: float,
    *,
    pixel_scale_width: int,
    pixel_scale_height: int,
    canvas_multiple: int | None = None,
) -> dict[str, int]:
    """Scale and align a manual target to ComfyUI Core's H3 canvas grid."""

    if canvas_multiple is None:
        from comfy_extras.nodes_minimax_h3 import CANVAS_MULTIPLE

        canvas_multiple = int(CANVAS_MULTIPLE)
    current_latent_width = int(current_latent_width)
    current_latent_height = int(current_latent_height)
    pixel_scale_width = int(pixel_scale_width)
    pixel_scale_height = int(pixel_scale_height)
    canvas_multiple = int(canvas_multiple)
    scale_by = float(scale_by)
    if min(
        current_latent_width,
        current_latent_height,
        pixel_scale_width,
        pixel_scale_height,
        canvas_multiple,
    ) < 1:
        raise SecondPassContractError("manual H3 canvas geometry is invalid")
    if (
        canvas_multiple % pixel_scale_width
        or canvas_multiple % pixel_scale_height
    ):
        raise SecondPassContractError(
            "ComfyUI Core H3 canvas multiple is not aligned to the latent scale"
        )

    def aligned_target(current_latent: int, pixel_scale: int) -> int:
        current_pixels = current_latent * pixel_scale
        scaled_pixels = current_pixels * scale_by
        nearest_core_canvas = max(
            canvas_multiple,
            round(scaled_pixels / canvas_multiple) * canvas_multiple,
        )
        preserved_core_canvas = (
            (current_pixels + canvas_multiple - 1) // canvas_multiple
        ) * canvas_multiple
        return max(nearest_core_canvas, preserved_core_canvas)

    target_width = aligned_target(current_latent_width, pixel_scale_width)
    target_height = aligned_target(current_latent_height, pixel_scale_height)
    return {
        "target_width": target_width,
        "target_height": target_height,
        "target_latent_width": target_width // pixel_scale_width,
        "target_latent_height": target_height // pixel_scale_height,
    }


def resolve_h3_native_latent_target(
    video_latents: Sequence[Mapping[str, Any]],
    assembly_plan: Mapping[str, Any],
    *,
    adapt_canvas_fn: Callable[[int, int], tuple[int, int]] | None = None,
) -> dict[str, int | bool]:
    """Resolve Core's native canvas without shrinking an existing video latent."""

    contract = assembly_plan.get("second_pass_contract")
    if not isinstance(contract, Mapping):
        raise SecondPassContractError("assembly_plan has no second_pass_contract")
    groups = contract.get("physical_groups")
    if not isinstance(groups, list) or not groups:
        raise SecondPassContractError(
            "second_pass_contract.physical_groups must be non-empty"
        )
    if not isinstance(video_latents, Sequence) or not video_latents:
        raise SecondPassContractError("video_latents must be a non-empty sequence")
    if len(video_latents) != len(groups):
        raise SecondPassContractError("video latent group count changed")

    first_group = groups[0]
    if not isinstance(first_group, Mapping):
        raise SecondPassContractError("physical group metadata must be a mapping")
    source_width = int(first_group.get("source_width", -1))
    source_height = int(first_group.get("source_height", -1))
    source_latent_width = int(first_group.get("source_latent_w", -1))
    source_latent_height = int(first_group.get("source_latent_h", -1))
    if min(source_width, source_height, source_latent_width, source_latent_height) < 1:
        raise SecondPassContractError("source pixel/latent geometry is invalid")
    if source_width % source_latent_width or source_height % source_latent_height:
        raise SecondPassContractError("source pixel/latent geometry is not integral")
    pixel_scale_width = source_width // source_latent_width
    pixel_scale_height = source_height // source_latent_height

    current_geometry: tuple[int, int] | None = None
    for position, (latent, group) in enumerate(zip(video_latents, groups, strict=True)):
        if not isinstance(group, Mapping):
            raise SecondPassContractError("physical group metadata must be a mapping")
        if int(group.get("source_width", -1)) != source_width or int(
            group.get("source_height", -1)
        ) != source_height:
            raise SecondPassContractError("source geometry differs between physical groups")
        if int(group.get("source_latent_w", -1)) != source_latent_width or int(
            group.get("source_latent_h", -1)
        ) != source_latent_height:
            raise SecondPassContractError(
                "source latent geometry differs between physical groups"
            )
        if not isinstance(latent, Mapping) or "samples" not in latent:
            raise SecondPassContractError(
                f"video_latents[{position}] must be a LATENT mapping with samples"
            )
        samples = latent["samples"]
        if not hasattr(samples, "shape") or len(samples.shape) != 5:
            raise SecondPassContractError("video latent must have shape [B,C,T,H,W]")
        geometry = (int(samples.shape[-2]), int(samples.shape[-1]))
        if current_geometry is None:
            current_geometry = geometry
        elif geometry != current_geometry:
            raise SecondPassContractError(
                "all physical groups must use the same current H/W"
            )

    assert current_geometry is not None
    native_width, native_height = h3_core_native_canvas(
        source_width,
        source_height,
        adapt_canvas_fn=adapt_canvas_fn,
    )
    if native_width % pixel_scale_width or native_height % pixel_scale_height:
        raise SecondPassContractError(
            "ComfyUI Core native canvas is not aligned to the H3 latent scale"
        )
    native_latent_width = native_width // pixel_scale_width
    native_latent_height = native_height // pixel_scale_height
    current_height, current_width = current_geometry
    preserve_current = (
        native_latent_width < current_width
        or native_latent_height < current_height
    )
    if preserve_current:
        target_latent_width = current_width
        target_latent_height = current_height
    else:
        target_latent_width = native_latent_width
        target_latent_height = native_latent_height

    return {
        "source_width": source_width,
        "source_height": source_height,
        "native_width": native_width,
        "native_height": native_height,
        "target_width": target_latent_width * pixel_scale_width,
        "target_height": target_latent_height * pixel_scale_height,
        "target_latent_width": target_latent_width,
        "target_latent_height": target_latent_height,
        "preserved_current": preserve_current,
    }


def _prepend_resize_status(
    second_pass_status: str,
    *,
    backend: str,
    mode: str,
    upscale_method: str,
    scale_by: float,
    source_width: int,
    source_height: int,
    target_width: int,
    target_height: int,
    native_width: int,
    native_height: int,
) -> str:
    lines = [
        "H3 Continuum Hi-Res Fix V3.5",
        "Pixel/VAE resize: "
        f"backend={backend}, mode={mode}, method={upscale_method}, "
        f"scale_by={scale_by:g}, "
        f"source={source_width}x{source_height}, "
        f"target={target_width}x{target_height}, "
        f"core_native={native_width}x{native_height}.",
    ]
    if target_width > native_width or target_height > native_height:
        lines.append(
            "INFO: target exceeds the ComfyUI Core H3 base canvas; the Pixel/VAE "
            "roundtrip is preserved and resource use may increase."
        )
    lines.append(second_pass_status)
    return "\n".join(lines)


class H3ContinuumHiResFixV35:
    """Pixel/VAE resize and low-sigma refine complete physical video groups."""

    DEPRECATED = False
    DESCRIPTION = (
        "Continuum-aware Hi-res fix. When enabled, each first-pass physical video "
        "LATENT is decoded with the connected H3 Video VAE, resized in pixel space, "
        "re-encoded with the same VAE, and refined once with the workflow SIGMAS. "
        "scale_by 0 uses ComfyUI Core's H3 native canvas; positive values use the "
        "manual multiplier. Connect the optional Continuum refine context to preserve "
        "First/Last/Reference conditioning at the target geometry. "
        "When disabled, first-pass video/audio LATENT objects and the original assembly "
        "plan are returned unchanged."
    )

    @classmethod
    def INPUT_TYPES(cls):
        lazy = {"lazy": True}
        return {
            "required": {
                "model": ("MODEL", lazy),
                "clip": ("CLIP", lazy),
                "sampler": ("SAMPLER", lazy),
                "sigmas": ("SIGMAS", lazy),
                "video_latents": ("LATENT",),
                "audio_latents": ("LATENT",),
                "assembly_plan": ("H3_CONTINUUM_ASSEMBLY_PLAN",),
                "enabled": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": (
                            "Enable Resize + Second Pass. Off returns the first-pass "
                            "video/audio LATENT objects and assembly plan unchanged."
                        ),
                    },
                ),
                "upscale_method": (
                    HIRES_UPSCALE_METHODS,
                    {"default": "lanczos"},
                ),
                "scale_by": (
                    "FLOAT",
                    {
                        "default": 2.0,
                        "min": 0.0,
                        "max": 4.0,
                        "step": 0.01,
                        "tooltip": (
                            "2.0 = validated 2x Pixel/VAE Hi-res Fix. 0 uses the "
                            "ComfyUI Core H3 native canvas automatically. Manual "
                            "values follow the existing Second Pass contract and must "
                            "be 1.0 or greater."
                        ),
                    },
                ),
                "refine_seed": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 0xFFFFFFFFFFFFFFFF,
                        "control_after_generate": True,
                        "tooltip": "Base seed independently derived once per physical group.",
                    },
                ),
            },
            "optional": {
                "refine_context": (
                    "H3_CONTINUUM_REFINE_CONTEXT",
                    {"lazy": True},
                ),
                "video_vae": (
                    "VAE",
                    {
                        "lazy": True,
                        "tooltip": (
                            "Required while enabled for the safe Pixel/VAE roundtrip; "
                            "not evaluated while disabled."
                        ),
                    },
                ),
            },
        }

    INPUT_IS_LIST = True
    RETURN_TYPES = ("LATENT", "LATENT", "H3_CONTINUUM_ASSEMBLY_PLAN", "STRING")
    RETURN_NAMES = (
        "video_latents",
        "audio_latents",
        "updated_assembly_plan",
        "status",
    )
    OUTPUT_IS_LIST = (True, True, False, False)
    FUNCTION = "apply"
    CATEGORY = "MiniMax H3/Continuum"

    def check_lazy_status(
        self,
        enabled,
        model=None,
        clip=None,
        sampler=None,
        sigmas=None,
        refine_context=_MISSING,
        video_vae=_MISSING,
        **_kwargs,
    ):
        if not _enabled_value(enabled):
            return []
        required = [
            name
            for name, value in (
                ("model", model),
                ("clip", clip),
                ("sampler", sampler),
                ("sigmas", sigmas),
            )
            if _lazy_missing(value)
        ]
        required.extend(
            name
            for name, value in (
                ("refine_context", refine_context),
                ("video_vae", video_vae),
            )
            if value is not _MISSING and _lazy_missing(value)
        )
        return required

    def apply(
        self,
        model,
        clip,
        sampler,
        sigmas,
        video_latents,
        audio_latents,
        assembly_plan,
        enabled,
        upscale_method,
        scale_by,
        refine_seed,
        refine_context=None,
        video_vae=None,
        refine_schedule=None,
    ):
        plan = _single_list_input("assembly_plan", assembly_plan)
        if not _enabled_value(enabled):
            return (
                video_latents,
                audio_latents,
                plan,
                "H3 Continuum Hi-Res Fix V3.5: disabled; first-pass video/audio "
                "LATENT objects and assembly_plan returned unchanged.",
            )

        method = str(_single_list_input("upscale_method", upscale_method))
        scale = float(_single_list_input("scale_by", scale_by))
        if 0.0 < scale < 1.0:
            raise SecondPassContractError(
                "scale_by must be 0 for H3 native Auto or at least 1.0; the "
                "existing Second Pass contract preserves or enlarges spatial size"
            )
        vae = (
            None
            if video_vae is None
            else _single_list_input("video_vae", video_vae)
        )
        if vae is None:
            raise SecondPassContractError(
                "Hi-Res Fix enabled requires video_vae for the safe Pixel/VAE "
                "roundtrip; legacy direct latent interpolation is disabled"
            )
        source_width = int(plan["width"])
        source_height = int(plan["height"])
        native_width, native_height = h3_core_native_canvas(
            source_width,
            source_height,
        )
        first_samples = video_latents[0]["samples"]
        current_geometry = (
            int(first_samples.shape[-2]),
            int(first_samples.shape[-1]),
        )
        if scale == 0.0:
            native_target = resolve_h3_native_latent_target(video_latents, plan)
            target_latent_width = int(native_target["target_latent_width"])
            target_latent_height = int(native_target["target_latent_height"])
            target_width = int(native_target["target_width"])
            target_height = int(native_target["target_height"])
            resize_mode = "h3_native_canvas_auto"
        else:
            pixel_scale_width, pixel_scale_height = resolve_pixel_latent_scale(plan)
            manual_target = align_h3_manual_canvas(
                current_geometry[1],
                current_geometry[0],
                scale,
                pixel_scale_width=pixel_scale_width,
                pixel_scale_height=pixel_scale_height,
            )
            target_latent_width = int(manual_target["target_latent_width"])
            target_latent_height = int(manual_target["target_latent_height"])
            target_width = int(manual_target["target_width"])
            target_height = int(manual_target["target_height"])
            resize_mode = "manual_scale_by"

        if current_geometry == (target_latent_height, target_latent_width):
            resized_video_latents = list(video_latents)
            resize_backend = "direct_second_pass_no_resize"
        else:
            resized_video_latents = resize_video_latents_via_vae(
                video_latents,
                plan,
                video_vae=vae,
                target_width=target_width,
                target_height=target_height,
                upscale_method=method,
            )
            resize_backend = "sequential_pixel_vae_roundtrip"

        refined_video, output_audio, updated_plan, status = run_second_pass_groups(
            model=_single_list_input("model", model),
            clip=_single_list_input("clip", clip),
            sampler=_single_list_input("sampler", sampler),
            sigmas=_single_list_input("sigmas", sigmas),
            video_latents=resized_video_latents,
            audio_latents=audio_latents,
            assembly_plan=plan,
            refine_seed=int(_single_list_input("refine_seed", refine_seed)),
            refine_context=(
                None
                if refine_context is None
                else _single_list_input("refine_context", refine_context)
            ),
            video_vae=vae,
            conditioning_upscale_method=_CONDITIONING_UPSCALE_METHOD,
            refine_schedule=refine_schedule,
        )
        return (
            refined_video,
            output_audio,
            updated_plan,
            _prepend_resize_status(
                status,
                backend=resize_backend,
                mode=resize_mode,
                upscale_method=method,
                scale_by=scale,
                source_width=source_width,
                source_height=source_height,
                target_width=int(updated_plan["width"]),
                target_height=int(updated_plan["height"]),
                native_width=native_width,
                native_height=native_height,
            ),
        )


NODE_CLASS_MAPPINGS = {
    "H3ContinuumHiResFixV35": H3ContinuumHiResFixV35,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "H3ContinuumHiResFixV35": "H3 Continuum Hi-Res Fix V3.5",
}
