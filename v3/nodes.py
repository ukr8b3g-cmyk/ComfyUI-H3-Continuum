"""Public latent-first facade nodes for H3 Continuum V3."""

from __future__ import annotations

import time

from ..constants import (
    CHUNK_SECONDS_DEFAULT,
    CHUNK_SECONDS_MAX,
    CHUNK_SECONDS_MIN,
    CHUNK_SECONDS_STEP,
    CHUNK_SECONDS_TOOLTIP,
    DIAGNOSTICS_FULL,
)
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
from .assembly import H3ContinuumAssembleSeamExperimental, H3ContinuumAssembleV3
from .plan import make_assembly_plan
from ..timeline_video import TIMELINE_VIDEO_SIZE_OPTIONS


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
                "strict_compatibility": ("BOOLEAN", {"default": False}),
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
                "strict_compatibility": False,
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
                    {
                        "default": CHUNK_SECONDS_DEFAULT,
                        "min": CHUNK_SECONDS_MIN,
                        "max": CHUNK_SECONDS_MAX,
                        "step": CHUNK_SECONDS_STEP,
                        "tooltip": CHUNK_SECONDS_TOOLTIP,
                    },
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
        driving_audio_source=None,
        driving_audio_vae=None,
        reference_video_source=None,
        timeline_video_source=None,
        guide_source=None,
        capture_refine_context=False,
        memory_attribution=False,
        prompt_conditioning_cache=False,
        continuation_transport="reference_context_v1",
    ):
        if prompt_overrides is not None and not isinstance(prompt_overrides, dict):
            prompt_overrides = None
        if advanced is not None and not isinstance(advanced, dict):
            advanced = None

        advanced_values = {
            "audio_continuity": True,
            "diagnostics": DIAGNOSTICS_OPTIONS[0],
            "reroll_from_chunk": 0,
            "reroll_nonce": 0,
            "strict_compatibility": False,
            "debug": False,
            "show_preview": True,
            "last_frame": None,
            "session": None,
            "initial_state": None,
            "prompt_plan": None,
        }
        if advanced:
            advanced_values.update(advanced)
        advanced_values["strict_compatibility"] = False

        clip_prompt_inputs = {}
        if prompt_overrides:
            if (
                type(prompt_overrides.get("schema_version")) is not int
                or prompt_overrides.get("schema_version")
                != SPARSE_OVERRIDE_SCHEMA_VERSION
            ):
                prompt_overrides = None
            if prompt_overrides is not None:
                try:
                    sparse_overrides = validate_sparse_prompt_overrides(
                        prompt_overrides.get("overrides"), chunks=int(chunks)
                    )
                except (TypeError, ValueError):
                    sparse_overrides = {}
                for index, prompt in sparse_overrides.items():
                    clip_prompt_inputs[f"clip_{index}_prompt"] = prompt

        sequence_outputs = H3ContinuumSamplerV2().run(
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
            strict_compatibility=False,
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
            driving_audio_source=driving_audio_source,
            driving_audio_vae=driving_audio_vae,
            reference_video_source=reference_video_source,
            timeline_video_source=timeline_video_source,
            guide_source=guide_source,
            capture_refine_context=bool(capture_refine_context),
            memory_attribution=bool(memory_attribution),
            prompt_conditioning_cache=bool(prompt_conditioning_cache),
            continuation_transport=str(continuation_transport),
            **clip_prompt_inputs,
        )
        if bool(capture_refine_context):
            entries, last_state, session, report, refine_context = sequence_outputs
        else:
            entries, last_state, session, report = sequence_outputs

        from ..v2.sequence import _terminal_flf_merge_enabled
        from .plan import prepare_physical_decode_entries

        terminal_merged = _terminal_flf_merge_enabled(
            multi_chunk_flf=(
                first_frame is not None
                and advanced_values["last_frame"] is not None
                and len(entries) > 1
            ),
            chunks=len(entries),
            chunk_seconds=float(chunk_seconds),
            prompt_hashes=[str(entry["prompt_hash"]) for entry in entries],
            timeline_video_source=timeline_video_source,
        )
        decode_entries, assembly_plan = prepare_physical_decode_entries(
            entries,
            chunk_seconds=float(chunk_seconds),
            preserve_final_frame=advanced_values["last_frame"] is not None,
            terminal_merged=terminal_merged,
        )
        video_latents = [{"samples": entry["video"]} for entry in decode_entries]
        audio_latents = [{"samples": entry["audio"]} for entry in decode_entries]
        if terminal_merged:
            report = str(report).rstrip() + (
                "\nDecode: terminal merged latent retained as one physical external "
                "Core VAE decode group; logical Run Storage entries are unchanged."
            )
        result = {
            "last_state": last_state,
            "session": session,
            "report": report,
        }
        outputs = (video_latents, audio_latents, assembly_plan, result)
        if bool(capture_refine_context):
            return (*outputs, refine_context)
        return outputs


class H3ContinuumSamplerProduction(H3ContinuumSamplerV3):
    """Stable single-entry sampler UI for V3.3 and later releases."""

    DEPRECATED = False
    CATEGORY = CATEGORY
    DESCRIPTION = (
        "Production H3 Continuum sampler with first/last-frame or image-reference conditioning and "
        "ComfyUI-native advanced widgets. Video/audio VAE decoding remains in "
        "ComfyUI Core."
    )
    SEARCH_ALIASES = [
        "H3 Continuum Sampler V3.3",
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
                        "tooltip": "Auto accepts Fixed, list-separated, and timeline prompt styles.",
                        **advanced,
                    },
                ),
                "chunks": (
                    "INT",
                    {
                        "default": 3,
                        "min": 1,
                        "max": 16,
                        "step": 1,
                        "tooltip": "Number of sequential Continuum chunks to generate.",
                    },
                ),
                "chunk_seconds": (
                    "FLOAT",
                    {
                        "default": CHUNK_SECONDS_DEFAULT,
                        "min": CHUNK_SECONDS_MIN,
                        "max": CHUNK_SECONDS_MAX,
                        "step": CHUNK_SECONDS_STEP,
                        "tooltip": CHUNK_SECONDS_TOOLTIP,
                    },
                ),
                "width": (
                    "INT",
                    {
                        "default": 1344,
                        "min": 32,
                        "max": 16384,
                        "step": 32,
                        "tooltip": "Output width. Use a multiple of 32.",
                    },
                ),
                "height": (
                    "INT",
                    {
                        "default": 768,
                        "min": 32,
                        "max": 16384,
                        "step": 32,
                        "tooltip": "Output height. Use a multiple of 32.",
                    },
                ),
                "continuity": (
                    V2_CONTINUITY_OPTIONS,
                    {
                        "default": V2_CONTINUITY_OPTIONS[1],
                        "tooltip": "Amount of prior video context retained at each chunk boundary.",
                    },
                ),
                "base_seed": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 0xFFFFFFFFFFFFFFFF,
                        "control_after_generate": True,
                        "tooltip": "Base seed used to derive deterministic per-chunk seeds.",
                    },
                ),
                "audio_continuity": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "advanced": True,
                        "tooltip": (
                            "On passes prior audio context into continuation chunks. "
                            "Turn it off only to isolate or replace generated audio."
                        ),
                    },
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
                        "display_name": "Variation Nonce",
                        "tooltip": (
                            "Change only when regenerating an explicit chunk and you want "
                            "a new variation with otherwise identical settings."
                        ),
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
        driving_audio_source=None,
        driving_audio_vae=None,
        reference_video_source=None,
        timeline_video_source=None,
        guide_source=None,
        capture_refine_context=False,
        memory_attribution=False,
        prompt_conditioning_cache=False,
        continuation_transport="reference_context_v1",
    ):
        runtime_started_at = time.perf_counter()
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
        def mark_runtime_start(assembly_plan):
            marked = dict(assembly_plan)
            marked["_runtime_started_at"] = runtime_started_at
            return marked

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
                driving_audio_source=driving_audio_source,
                driving_audio_vae=driving_audio_vae,
                reference_video_source=reference_video_source,
                timeline_video_source=timeline_video_source,
                guide_source=guide_source,
                capture_refine_context=bool(capture_refine_context),
                memory_attribution=bool(memory_attribution),
                prompt_conditioning_cache=bool(prompt_conditioning_cache),
                continuation_transport=str(continuation_transport),
                advanced={
                    "audio_continuity": bool(audio_continuity),
                    "diagnostics": diagnostics,
                    "reroll_from_chunk": regenerate_from,
                    "reroll_nonce": int(reroll_nonce),
                    "strict_compatibility": False,
                    "debug": bool(debug),
                    "show_preview": bool(show_preview),
                    "last_frame": last_frame,
                },
            )

        if run_storage == "Off":
            _validate_regenerate_storage(run_storage, regenerate_from)
            execute_outputs = execute()
            if bool(capture_refine_context):
                video_latents, audio_latents, assembly_plan, result, refine_context = execute_outputs
            else:
                video_latents, audio_latents, assembly_plan, result = execute_outputs
            outputs = (
                video_latents,
                audio_latents,
                mark_runtime_start(assembly_plan),
                str(result["report"]),
            )
            if bool(capture_refine_context):
                return (*outputs, refine_context)
            return outputs
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
            execute_outputs = execute()
            if bool(capture_refine_context):
                video_latents, audio_latents, assembly_plan, result, refine_context = execute_outputs
            else:
                video_latents, audio_latents, assembly_plan, result = execute_outputs
            result = dict(result)
            report = str(result["report"]) + "\n" + storage.summary(
                detailed=diagnostics == DIAGNOSTICS_FULL
            )
            result["report"] = report
            storage.finalize(session=result["session"], report=report)
            outputs = (
                video_latents,
                audio_latents,
                mark_runtime_start(assembly_plan),
                report,
            )
            if bool(capture_refine_context):
                return (*outputs, refine_context)
            return outputs


class H3ContinuumSamplerTimelineVideo(H3ContinuumSamplerProduction):
    """V3.3 sampler with optional chunk-local Timeline Video conditioning."""

    DEPRECATED = False
    CATEGORY = CATEGORY
    DESCRIPTION = (
        "Timeline Video sampler. It slices one Core VIDEO per chunk, "
        "resizes only that slice, and reuses the stable Continuum sampling engine."
    )
    SEARCH_ALIASES = [
        "H3 Continuum Timeline Video",
        "MiniMax H3 video reference timeline",
    ]

    @classmethod
    def INPUT_TYPES(cls):
        schema = super().INPUT_TYPES()
        required = {}
        for name, definition in schema["required"].items():
            required[name] = definition
            if name == "reference_size":
                required["timeline_video_size"] = (
                    TIMELINE_VIDEO_SIZE_OPTIONS,
                    {
                        "default": TIMELINE_VIDEO_SIZE_OPTIONS[0],
                        "display_name": "Timeline Video Size",
                        "advanced": True,
                        "tooltip": (
                            "Efficient limits each chunk-local reference slice to about 0.4 MP. "
                            "Match Output uses the output pixel area and may be substantially heavier."
                        ),
                    },
                )
        schema["required"] = required
        optional = dict(schema.get("optional", {}))
        optional["timeline_video"] = (
            "VIDEO",
            {
                "tooltip": (
                    "Optional. One continuous Core VIDEO covering every configured chunk. "
                    "When omitted or bypassed, the node uses the standard conditioning path. "
                    "Its audio is ignored; use the normal audio inputs for generated audio."
                )
            },
        )
        schema["optional"] = optional
        return schema

    def run(
        self,
        timeline_video=None,
        timeline_video_size=TIMELINE_VIDEO_SIZE_OPTIONS[0],
        **kwargs,
    ):
        if timeline_video is None:
            return super().run(**kwargs)

        from ..timeline_video import prepare_timeline_video_source

        source = prepare_timeline_video_source(
            timeline_video,
            chunks=int(kwargs["chunks"]),
            chunk_seconds=float(kwargs["chunk_seconds"]),
            output_width=int(kwargs["width"]),
            output_height=int(kwargs["height"]),
            size_mode=str(timeline_video_size),
        )
        return super().run(timeline_video_source=source, **kwargs)


NODE_CLASS_MAPPINGS = {
    "H3ContinuumSamplerProduction": H3ContinuumSamplerProduction,
    "H3ContinuumSamplerTimelineVideo": H3ContinuumSamplerTimelineVideo,
    "H3ContinuumSamplerV3": H3ContinuumSamplerV3,
    "H3ContinuumAdvancedV3": H3ContinuumAdvancedV3,
    "H3ContinuumAssembleV3": H3ContinuumAssembleV3,
    "H3ContinuumAssembleSeamExperimental": H3ContinuumAssembleSeamExperimental,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "H3ContinuumSamplerProduction": "H3 Continuum Sampler V3.2.4",
    "H3ContinuumSamplerTimelineVideo": "H3 Continuum Sampler V3.3",
    "H3ContinuumSamplerV3": "H3 Continuum Sampler V3",
    "H3ContinuumAdvancedV3": "H3 Continuum Advanced V3",
    "H3ContinuumAssembleV3": "H3 Continuum Assemble V3.2.4",
    "H3ContinuumAssembleSeamExperimental": "H3 Continuum Assemble + Seam",
}
