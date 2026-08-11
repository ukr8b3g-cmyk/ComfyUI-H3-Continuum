"""Public latent-first facade nodes for H3 Continuum V3."""

from __future__ import annotations

from ..v2.nodes import (
    CATEGORY,
    DIAGNOSTICS_OPTIONS,
    H3ContinuumSamplerV2,
    PROMPT_FORMAT_OPTIONS,
    SEAM_CORRECTION_OFF,
    SPARSE_OVERRIDE_SCHEMA_VERSION,
    V2_CONTINUITY_OPTIONS,
    validate_sparse_prompt_overrides,
)
from .assembly import H3ContinuumAssembleV3
from .plan import make_assembly_plan


class H3ContinuumAdvancedV3:
    DESCRIPTION = (
        "Optional continuation, session, reroll, and diagnostics settings for V3."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "audio_continuity": ("BOOLEAN", {"default": True}),
                "diagnostics": (
                    DIAGNOSTICS_OPTIONS,
                    {
                        "default": DIAGNOSTICS_OPTIONS[0],
                        "display_name": "Report Detail",
                    },
                ),
                "reroll_from_chunk": (
                    "INT",
                    {"default": 0, "min": 0, "max": 16, "step": 1},
                ),
                "reroll_nonce": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 0xFFFFFFFF,
                        "step": 1,
                    },
                ),
                "strict_compatibility": ("BOOLEAN", {"default": True}),
                "debug": ("BOOLEAN", {"default": False}),
                "show_preview": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "last_frame": ("IMAGE",),
                "session": ("H3_CONTINUUM_SESSION",),
                "initial_state": ("H3_CONTINUUM_STATE",),
                "prompt_plan": ("H3_CONTINUUM_PROMPT_PLAN",),
            },
        }

    RETURN_TYPES = ("H3_CONTINUUM_ADVANCED_V3",)
    RETURN_NAMES = ("advanced",)
    FUNCTION = "pack"
    CATEGORY = CATEGORY

    def pack(
        self,
        audio_continuity,
        diagnostics,
        reroll_from_chunk,
        reroll_nonce,
        strict_compatibility,
        debug,
        show_preview,
        last_frame=None,
        session=None,
        initial_state=None,
        prompt_plan=None,
    ):
        return (
            {
                "audio_continuity": bool(audio_continuity),
                "diagnostics": diagnostics,
                "reroll_from_chunk": int(reroll_from_chunk),
                "reroll_nonce": int(reroll_nonce),
                "strict_compatibility": bool(strict_compatibility),
                "debug": bool(debug),
                "show_preview": bool(show_preview),
                "last_frame": last_frame,
                "session": session,
                "initial_state": initial_state,
                "prompt_plan": prompt_plan,
            },
        )


class H3ContinuumSamplerV3:
    DESCRIPTION = (
        "Latent-first N-chunk MiniMax H3 sampler. Sampling, native continuation, "
        "State/Session, and Spectrum interop stay inside Continuum; ComfyUI Core "
        "performs video and audio VAE decoding."
    )
    SEARCH_ALIASES = [
        "H3 Continuum V3",
        "H3 latent first",
        "MiniMax H3 external VAE decode",
    ]

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
                "clip": ("CLIP",),
                "video_vae": (
                    "VAE",
                    {
                        "tooltip": (
                            "Used only to encode first/last-frame conditioning; "
                            "V3 never decodes with it."
                        ),
                    },
                ),
                "sampler": ("SAMPLER",),
                "sigmas": ("SIGMAS",),
                "sequence_prompt": (
                    "STRING",
                    {
                        "forceInput": True,
                        "display_name": "Sequence Prompt",
                        "tooltip": (
                            "Connect one Text (Multiline) for the complete sequence."
                        ),
                    },
                ),
                "prompt_mode": (
                    PROMPT_FORMAT_OPTIONS,
                    {
                        "default": PROMPT_FORMAT_OPTIONS[0],
                        "display_name": "Prompt Format",
                    },
                ),
                "chunks": ("INT", {"default": 3, "min": 1, "max": 16, "step": 1}),
                "chunk_seconds": (
                    "FLOAT",
                    {"default": 5.0, "min": 4.0, "max": 15.0, "step": 0.1},
                ),
                "width": (
                    "INT",
                    {"default": 1344, "min": 32, "max": 16384, "step": 32},
                ),
                "height": (
                    "INT",
                    {"default": 768, "min": 32, "max": 16384, "step": 32},
                ),
                "continuity": (
                    V2_CONTINUITY_OPTIONS,
                    {"default": V2_CONTINUITY_OPTIONS[1]},
                ),
                "base_seed": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 0xFFFFFFFFFFFFFFFF,
                        "control_after_generate": True,
                    },
                ),
            },
            "optional": {
                "first_frame": ("IMAGE",),
                "prompt_overrides": ("H3_CONTINUUM_CLIP_OVERRIDES",),
                "advanced": ("H3_CONTINUUM_ADVANCED_V3",),
            },
        }

    RETURN_TYPES = (
        "LATENT",
        "LATENT",
        "H3_CONTINUUM_ASSEMBLY_PLAN",
        "H3_CONTINUUM_RESULT",
    )
    RETURN_NAMES = (
        "video_latents",
        "audio_latents",
        "assembly_plan",
        "result",
    )
    OUTPUT_IS_LIST = (True, True, False, False)
    FUNCTION = "run"
    CATEGORY = CATEGORY

    def run(
        self,
        model,
        clip,
        video_vae,
        sampler,
        sigmas,
        sequence_prompt,
        prompt_mode,
        chunks,
        chunk_seconds,
        width,
        height,
        continuity,
        base_seed,
        first_frame=None,
        prompt_overrides=None,
        advanced=None,
    ):
        if prompt_overrides is not None and not isinstance(prompt_overrides, dict):
            raise TypeError(
                "prompt_overrides must be an H3_CONTINUUM_CLIP_OVERRIDES pack"
            )
        if advanced is not None and not isinstance(advanced, dict):
            raise TypeError("advanced must be an H3_CONTINUUM_ADVANCED_V3 pack")

        advanced_values = {
            "audio_continuity": True,
            "diagnostics": DIAGNOSTICS_OPTIONS[0],
            "reroll_from_chunk": 0,
            "reroll_nonce": 0,
            "strict_compatibility": True,
            "debug": False,
            "show_preview": True,
            "last_frame": None,
            "session": None,
            "initial_state": None,
            "prompt_plan": None,
        }
        if advanced:
            advanced_values.update(advanced)

        clip_prompt_inputs = {}
        if prompt_overrides:
            if (
                type(prompt_overrides.get("schema_version")) is not int
                or prompt_overrides.get("schema_version")
                != SPARSE_OVERRIDE_SCHEMA_VERSION
            ):
                raise ValueError("unsupported H3_CONTINUUM_CLIP_OVERRIDES schema")
            sparse_overrides = validate_sparse_prompt_overrides(
                prompt_overrides.get("overrides"), chunks=int(chunks)
            )
            for index, prompt in sparse_overrides.items():
                clip_prompt_inputs[f"clip_{index}_prompt"] = prompt

        entries, last_state, session, report = H3ContinuumSamplerV2().run(
            model=model,
            clip=clip,
            video_vae=video_vae,
            audio_vae=None,
            sampler=sampler,
            sigmas=sigmas,
            prompt_mode=prompt_mode,
            prompt_script=sequence_prompt,
            chunks=chunks,
            chunk_seconds=chunk_seconds,
            width=width,
            height=height,
            continuity=continuity,
            base_seed=base_seed,
            audio_continuity=advanced_values["audio_continuity"],
            exact_total_duration=False,
            diagnostics=advanced_values["diagnostics"],
            reroll_from_chunk=advanced_values["reroll_from_chunk"],
            reroll_nonce=advanced_values["reroll_nonce"],
            strict_compatibility=advanced_values["strict_compatibility"],
            debug=advanced_values["debug"],
            seam_correction=SEAM_CORRECTION_OFF,
            first_frame=first_frame,
            last_frame=advanced_values["last_frame"],
            session=advanced_values["session"],
            initial_state=advanced_values["initial_state"],
            prompt_plan=advanced_values["prompt_plan"],
            sequence_prompt=sequence_prompt,
            show_preview=advanced_values["show_preview"],
            latent_only=True,
            **clip_prompt_inputs,
        )

        assembly_plan = make_assembly_plan(
            entries,
            chunk_seconds=float(chunk_seconds),
            preserve_final_frame=advanced_values["last_frame"] is not None,
        )
        video_latents = [{"samples": entry["video"]} for entry in entries]
        audio_latents = [{"samples": entry["audio"]} for entry in entries]
        result = {
            "last_state": last_state,
            "session": session,
            "report": report,
        }
        return video_latents, audio_latents, assembly_plan, result


NODE_CLASS_MAPPINGS = {
    "H3ContinuumSamplerV3": H3ContinuumSamplerV3,
    "H3ContinuumAdvancedV3": H3ContinuumAdvancedV3,
    "H3ContinuumAssembleV3": H3ContinuumAssembleV3,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "H3ContinuumSamplerV3": "H3 Continuum Sampler V3",
    "H3ContinuumAdvancedV3": "H3 Continuum Advanced V3",
    "H3ContinuumAssembleV3": "H3 Continuum Assemble V3",
}
