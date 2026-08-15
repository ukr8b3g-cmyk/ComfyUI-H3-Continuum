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


REGENERATE_AUTO = "Auto"
REGENERATE_OPTIONS = (REGENERATE_AUTO,) + tuple(
    f"Chunk {index}" for index in range(1, 17)
)


def _regenerate_from_value(value, *, chunks: int) -> int:
    if isinstance(value, str):
        text = value.strip()
        if text == REGENERATE_AUTO:
            resolved = 0
        elif text.startswith("Chunk ") and text[6:].isdigit():
            resolved = int(text[6:])
        elif text.isdigit():
            resolved = int(text)
        else:
            raise ValueError(f"unknown Regenerate From value: {value!r}")
    else:
        resolved = int(value)
    if resolved < 0 or resolved > int(chunks):
        raise ValueError(
            f"Regenerate From Chunk {resolved} is outside the configured "
            f"1-{int(chunks)} chunk range"
        )
    return resolved


def _validate_regenerate_storage(run_storage: str, regenerate_from: int) -> None:
    if str(run_storage) == "Off" and int(regenerate_from) > 0:
        raise ValueError(
            "Regenerate From requires Run Storage = Save + Auto Resume"
        )


def _validate_reference_checkpoint(
    prompt, unique_id, *, strict_compatibility: bool
) -> str:
    from ..graph_contract import classify_h3_checkpoint

    # Checkpoint choice is diagnostic only. Strict Compatibility remains
    # reserved for H3 contracts that are actually unsafe or unsupported.
    _ = strict_compatibility
    return classify_h3_checkpoint(prompt, unique_id)


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
                            "Used only to encode image conditioning. T2VA does "
                            "not use it; V3 never decodes with it."
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
                "first_frame": (
                    "IMAGE",
                    {"tooltip": "Optional. Leave image inputs disconnected for T2VA."},
                ),
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
        reference_assets=None,
        reference_audio_source=None,
        reference_audio_vae=None,
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
            reference_assets=reference_assets,
            reference_audio_source=reference_audio_source,
            reference_audio_vae=reference_audio_vae,
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


class H3ContinuumSamplerProduction(H3ContinuumSamplerV3):
    """Stable single-entry sampler UI for V3.2 and later releases."""

    DEPRECATED = False
    CATEGORY = CATEGORY
    DESCRIPTION = (
        "Production H3 Continuum sampler with first/last-frame or image-reference conditioning and "
        "ComfyUI-native advanced widgets. Video/audio VAE decoding remains in "
        "ComfyUI Core."
    )
    SEARCH_ALIASES = [
        "H3 Continuum Sampler V3.2",
        "H3 Continuum Production",
        "MiniMax H3 long video",
    ]
    RETURN_TYPES = (
        "LATENT",
        "LATENT",
        "H3_CONTINUUM_ASSEMBLY_PLAN",
        "STRING",
    )
    RETURN_NAMES = (
        "video_latents",
        "audio_latents",
        "assembly_plan",
        "status",
    )

    @classmethod
    def INPUT_TYPES(cls):
        advanced = {"advanced": True}
        return {
            "required": {
                "model": ("MODEL",),
                "clip": ("CLIP",),
                "video_vae": (
                    "VAE",
                    {
                        "tooltip": (
                            "Used only to encode image conditioning. T2VA does "
                            "not use it; Continuum never decodes with it."
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
                        **advanced,
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
                "audio_continuity": (
                    "BOOLEAN",
                    {"default": True, "advanced": True},
                ),
                "diagnostics": (
                    DIAGNOSTICS_OPTIONS,
                    {
                        "default": DIAGNOSTICS_OPTIONS[0],
                        "display_name": "Report Detail",
                        "advanced": True,
                    },
                ),
                "reroll_from_chunk": (
                    REGENERATE_OPTIONS,
                    {
                        "default": REGENERATE_AUTO,
                        "display_name": "Regenerate From",
                        "advanced": True,
                        "tooltip": (
                            "Auto resumes the longest compatible saved prefix. "
                            "Choosing a chunk reuses earlier chunks and regenerates "
                            "that chunk and everything after it."
                        ),
                    },
                ),
                "reroll_nonce": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 0xFFFFFFFF,
                        "step": 1,
                        "advanced": True,
                    },
                ),
                "strict_compatibility": (
                    "BOOLEAN",
                    {"default": True, "advanced": True},
                ),
                "debug": (
                    "BOOLEAN",
                    {"default": False, "advanced": True},
                ),
                "show_preview": (
                    "BOOLEAN",
                    {"default": True, "advanced": True},
                ),
                "run_storage": (
                    ("Off", "Save + Auto Resume"),
                    {
                        "default": "Off",
                        "display_name": "Run Storage",
                        "advanced": True,
                        "tooltip": "Atomically save raw AV chunks and resume a compatible saved run.",
                    },
                ),
                "run_name": (
                    "STRING",
                    {
                        "default": "",
                        "display_name": "Run Name (Optional Override)",
                        "advanced": True,
                        "tooltip": "Enter a stable name for this saved run. Compatible chunks are selected automatically.",
                    },
                ),
                "reference_size": (
                    ("Match Output", "Max Identity"),
                    {
                        "default": "Match Output",
                        "display_name": "Reference Size",
                        "advanced": True,
                        "tooltip": "Match Output is the practical default; Max Identity preserves more reference detail.",
                    },
                ),
                "project_id": (
                    "STRING",
                    {
                        "default": "",
                        "display_name": "Auto Resume ID Override",
                        "advanced": True,
                        "tooltip": "Optional. Leave blank to derive a stable ID from this sampler node. Run Name remains the explicit override.",
                    },
                ),
            },
            "optional": {
                "first_frame": (
                    "IMAGE",
                    {"tooltip": "Optional. Leave all image inputs disconnected for T2VA."},
                ),
                "last_frame": ("IMAGE",),
                "reference_image_1": ("IMAGE",),
                "reference_image_2": ("IMAGE",),
                "reference_image_3": ("IMAGE",),
                "reference_audio_1": ("AUDIO",),
                "reference_audio_vae": ("VAE",),
            },
            "hidden": {
                "prompt": "PROMPT",
                "unique_id": "UNIQUE_ID",
            },
        }

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
        audio_continuity,
        diagnostics,
        reroll_from_chunk,
        reroll_nonce,
        strict_compatibility,
        debug,
        show_preview,
        run_storage="Off",
        run_name="",
        reference_size="Match Output",
        project_id="",
        first_frame=None,
        last_frame=None,
        reference_image_1=None,
        reference_image_2=None,
        prompt_overrides=None,
        prompt=None,
        unique_id=None,
        reference_image_3=None,
        reference_audio_1=None,
        reference_audio_vae=None,
    ):
        from ..reference import prepare_reference_assets
        from ..reference_audio import prepare_reference_audio_source
        regenerate_from = _regenerate_from_value(
            reroll_from_chunk,
            chunks=int(chunks),
        )
        reference_assets = prepare_reference_assets(
            reference_image_1=reference_image_1,
            reference_image_2=reference_image_2,
            output_width=int(width),
            output_height=int(height),
            size_mode=reference_size,
            reference_image_3=reference_image_3,
        )
        reference_audio_source = prepare_reference_audio_source(
            reference_audio_1,
            reference_audio_vae,
        )
        if reference_assets is not None and (first_frame is not None or last_frame is not None):
            raise ValueError(
                "Reference Images cannot be combined with First Frame or Last Frame"
            )
        reference_checkpoint = None
        if reference_assets is not None:
            reference_checkpoint = _validate_reference_checkpoint(
                prompt,
                unique_id,
                strict_compatibility=bool(strict_compatibility),
            )

        def report_with_reference_status(report):
            if reference_checkpoint is None:
                return str(report)
            if reference_checkpoint == "ref2va":
                status = "Ref2VA verified."
            elif reference_checkpoint == "fl2va":
                status = "FL2VA; allowed, but reference fidelity may differ from Ref2VA."
            else:
                status = "unverified; execution allowed, Core contract errors remain fatal."
            return str(report) + "\nReference MODEL: " + status

        def execute():
            return super(H3ContinuumSamplerProduction, self).run(
                model=model,
                clip=clip,
                video_vae=video_vae,
                sampler=sampler,
                sigmas=sigmas,
                sequence_prompt=sequence_prompt,
                prompt_mode=prompt_mode,
                chunks=chunks,
                chunk_seconds=chunk_seconds,
                width=width,
                height=height,
                continuity=continuity,
                base_seed=base_seed,
                first_frame=first_frame,
                prompt_overrides=prompt_overrides,
                reference_assets=reference_assets,
                reference_audio_source=reference_audio_source,
                reference_audio_vae=reference_audio_vae,
                advanced={
                    "audio_continuity": bool(audio_continuity),
                    "diagnostics": diagnostics,
                    "reroll_from_chunk": regenerate_from,
                    "reroll_nonce": int(reroll_nonce),
                    "strict_compatibility": bool(strict_compatibility),
                    "debug": bool(debug),
                    "show_preview": bool(show_preview),
                    "last_frame": last_frame,
                },
            )

        if run_storage == "Off":
            _validate_regenerate_storage(run_storage, regenerate_from)
            video_latents, audio_latents, assembly_plan, result = execute()
            return (
                video_latents,
                audio_latents,
                assembly_plan,
                report_with_reference_status(result["report"]),
            )
        if run_storage != "Save + Auto Resume":
            raise ValueError(f"unknown Run Storage mode: {run_storage!r}")
        from ..run_storage import (
            automatic_project_key,
            resolve_run_storage_name,
            run_storage_scope,
        )
        storage_name = resolve_run_storage_name(
            project_id=project_id,
            legacy_run_name=run_name,
            automatic_key=automatic_project_key(prompt, unique_id),
        )
        with run_storage_scope(
            storage_name, prompt=prompt, unique_id=unique_id
        ) as storage:
            video_latents, audio_latents, assembly_plan, result = execute()
            result = dict(result)
            report = report_with_reference_status(result["report"]) + "\n" + storage.summary(
                detailed=diagnostics == DIAGNOSTICS_OPTIONS[-1]
            )
            result["report"] = report
            storage.finalize(session=result["session"], report=report)
            return video_latents, audio_latents, assembly_plan, report


NODE_CLASS_MAPPINGS = {
    "H3ContinuumSamplerProduction": H3ContinuumSamplerProduction,
    "H3ContinuumSamplerV3": H3ContinuumSamplerV3,
    "H3ContinuumAdvancedV3": H3ContinuumAdvancedV3,
    "H3ContinuumAssembleV3": H3ContinuumAssembleV3,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "H3ContinuumSamplerProduction": "H3 Continuum Sampler V3.2",
    "H3ContinuumSamplerV3": "H3 Continuum Sampler V3",
    "H3ContinuumAdvancedV3": "H3 Continuum Advanced V3",
    "H3ContinuumAssembleV3": "H3 Continuum Assemble V3",
}
