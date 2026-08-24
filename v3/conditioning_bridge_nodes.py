"""V3.5 Advanced bridge from Continuum refine context to Core conditioning."""

from __future__ import annotations

from typing import Any

from .second_pass import prepare_physical_refine_groups
from .second_pass_nodes import _single_list_input


class H3ContinuumConditioningBridgeV35:
    """Publish paired physical-group MODEL and CONDITIONING values."""

    DEPRECATED = False
    DESCRIPTION = (
        "Advanced interoperability bridge for Basic Guider and external samplers. "
        "It adapts the captured Continuum refine context to externally processed "
        "physical-group video latents, then returns one paired MODEL and complete "
        "CONDITIONING per physical group plus the target-geometry Assembly Plan. "
        "Nested AV LATENT construction, Audio LATENT, Noise, Audio Lock, and external "
        "sampling behavior remain the workflow's responsibility."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
                "clip": ("CLIP",),
                "video_latents": ("LATENT",),
                "assembly_plan": ("H3_CONTINUUM_ASSEMBLY_PLAN",),
                "refine_context": ("H3_CONTINUUM_REFINE_CONTEXT",),
            },
            "optional": {
                "video_vae": (
                    "VAE",
                    {
                        "tooltip": (
                            "When available, First/Last keyframes are re-encoded at "
                            "the target geometry. Otherwise the existing conditioning "
                            "adapter uses its documented latent-resize fallback."
                        )
                    },
                ),
            },
        }

    INPUT_IS_LIST = True
    RETURN_TYPES = (
        "MODEL",
        "CONDITIONING",
        "H3_CONTINUUM_ASSEMBLY_PLAN",
        "STRING",
    )
    RETURN_NAMES = (
        "group_models",
        "conditioning",
        "updated_assembly_plan",
        "status",
    )
    OUTPUT_IS_LIST = (True, True, False, False)
    FUNCTION = "prepare"
    CATEGORY = "MiniMax H3/Continuum/Advanced"

    def prepare(
        self,
        model,
        clip,
        video_latents,
        assembly_plan,
        refine_context,
        video_vae=None,
    ):
        prepared = prepare_physical_refine_groups(
            model=_single_list_input("model", model),
            clip=_single_list_input("clip", clip),
            video_latents=video_latents,
            assembly_plan=_single_list_input("assembly_plan", assembly_plan),
            refine_context=_single_list_input("refine_context", refine_context),
            video_vae=(
                None
                if video_vae is None
                else _single_list_input("video_vae", video_vae)
            ),
        )
        group_models = prepared["group_models"]
        conditioning = prepared["conditioning"]
        physical_group_count = int(prepared["physical_group_count"])
        if not len(group_models) == len(conditioning) == physical_group_count:
            raise ValueError(
                "Conditioning Bridge MODEL/CONDITIONING physical group counts differ"
            )

        status_lines = [
            "H3 Continuum Conditioning Bridge V3.5",
            f"Physical groups: {physical_group_count}.",
            "Output contract: one paired MODEL and one complete CONDITIONING per "
            "physical group; CONDITIONING entries remain grouped.",
            "Scope: Advanced MODEL + CONDITIONING interoperability only; AV LATENT, "
            "Noise, and Audio Lock are controlled by the external workflow.",
            *prepared["warnings"],
        ]
        for detail in prepared["details"]:
            group = detail["group"]
            status_lines.append(
                "group "
                f"{int(detail['group_index']) + 1}: "
                f"logical_chunks={group.get('logical_chunks')}, "
                f"prompt_policy={group.get('prompt_policy', 'unknown')}, "
                f"conditioning_source={detail['conditioning_source']}, "
                f"physical_clip_index={detail['physical_clip_index']}, "
                f"context_frames={detail['context_frames']}"
            )
        status_lines.append(
            "Target geometry: "
            f"{prepared['updated_assembly_plan']['width']}x"
            f"{prepared['updated_assembly_plan']['height']}."
        )
        return (
            group_models,
            conditioning,
            prepared["updated_assembly_plan"],
            "\n".join(status_lines),
        )


NODE_CLASS_MAPPINGS = {
    "H3ContinuumConditioningBridgeV35": H3ContinuumConditioningBridgeV35,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "H3ContinuumConditioningBridgeV35": (
        "H3 Continuum Conditioning Bridge V3.5"
    ),
}
