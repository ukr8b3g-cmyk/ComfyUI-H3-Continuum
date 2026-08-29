"""V3.5 Second Pass public node."""

from __future__ import annotations

from typing import Any

from .second_pass import run_second_pass_groups


def _single_list_input(name: str, value: Any) -> Any:
    if not isinstance(value, list) or len(value) != 1:
        raise ValueError(f"{name} must contain exactly one value")
    return value[0]


class H3ContinuumSecondPassV35:
    """Low-sigma refinement over complete physical decode groups."""

    DEPRECATED = False
    DESCRIPTION = (
        "V3.5 context-aware Second Pass. Connect externally upscaled H3 video "
        "latents, the matching first-pass audio latents, and the original assembly plan. "
        "Connect the optional Continuum refine context to preserve the physical group's "
        "First/Last/Reference conditioning. "
        "SIGMAS controls the low-denoise refine schedule; audio output is preserved "
        "bit-exact from the first pass."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
                "clip": ("CLIP",),
                "sampler": ("SAMPLER",),
                "sigmas": ("SIGMAS",),
                "video_latents": ("LATENT",),
                "audio_latents": ("LATENT",),
                "assembly_plan": ("H3_CONTINUUM_ASSEMBLY_PLAN",),
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
                "refine_context": ("H3_CONTINUUM_REFINE_CONTEXT",),
                "video_vae": ("VAE",),
            },
        }

    INPUT_IS_LIST = True
    RETURN_TYPES = ("LATENT", "LATENT", "H3_CONTINUUM_ASSEMBLY_PLAN", "STRING")
    RETURN_NAMES = (
        "refined_video_latents",
        "audio_latents",
        "updated_assembly_plan",
        "status",
    )
    OUTPUT_IS_LIST = (True, True, False, False)
    FUNCTION = "refine"
    CATEGORY = "MiniMax H3/Continuum/Advanced"

    def refine(
        self,
        model,
        clip,
        sampler,
        sigmas,
        video_latents,
        audio_latents,
        assembly_plan,
        refine_seed,
        refine_context=None,
        video_vae=None,
        refine_schedule=None,
    ):
        return run_second_pass_groups(
            model=_single_list_input("model", model),
            clip=_single_list_input("clip", clip),
            sampler=_single_list_input("sampler", sampler),
            sigmas=_single_list_input("sigmas", sigmas),
            video_latents=video_latents,
            audio_latents=audio_latents,
            assembly_plan=_single_list_input("assembly_plan", assembly_plan),
            refine_seed=int(_single_list_input("refine_seed", refine_seed)),
            refine_context=(
                None
                if refine_context is None
                else _single_list_input("refine_context", refine_context)
            ),
            video_vae=(
                None
                if video_vae is None
                else _single_list_input("video_vae", video_vae)
            ),
            refine_schedule=refine_schedule,
        )


NODE_CLASS_MAPPINGS = {
    "H3ContinuumSecondPassV35": H3ContinuumSecondPassV35,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "H3ContinuumSecondPassV35": "H3 Continuum Second Pass V3.5",
}
