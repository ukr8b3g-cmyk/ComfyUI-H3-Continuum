"""ComfyUI node layer for H3 Continuum V2."""

from __future__ import annotations

import logging

from ..constants import (
    DIAGNOSTICS_ACCEPTED_OPTIONS,
    DIAGNOSTICS_OPTIONS,
    PROMPT_FORMAT_OPTIONS,
    PROMPT_MODE_OPTIONS,
    SEAM_CORRECTION_AUTO,
    SEAM_CORRECTION_OFF,
    SEAM_CORRECTION_OPTIONS,
    V2_CONTINUITY_OPTIONS,
    normalize_diagnostics_mode,
)
from .prompts import (
    apply_prompt_overrides,
    build_sampler_prompt_plan,
    make_prompt_plan,
    prompt_plan_report,
)
from .sequence import run_sequence
from .session import entry_to_state, session_summary, validate_session
from .session_io import (
    load_session,
    save_session,
    session_mtime,
    session_paths,
)

CATEGORY = "MiniMax H3/Continuum"
LOG = logging.getLogger("h3_continuum_join")


def _repair_v200_example_widget_shift(
    *,
    audio_continuity,
    exact_total_duration,
    diagnostics,
    reroll_from_chunk,
    reroll_nonce,
    strict_compatibility,
    debug,
):
    """Repair the malformed bundled 2.0.0 example workflow in memory.

    ``base_seed`` uses ComfyUI's ``control_after_generate`` option, which owns an
    additional serialized widget. The original hand-authored V2 example omitted
    that widget, shifting every following widget by one slot. A distinctive
    signature is therefore ``exact_total_duration == 'Basic'/'Full'/'Off'`` and
    numeric ``diagnostics``. Valid workflows never have a diagnostics label in
    the BOOLEAN exact-duration input, so this migration is narrow and safe.

    The missing exact-duration value cannot be recovered from the malformed JSON;
    restore its documented V2 default (True). The remaining values can be shifted
    back losslessly.
    """

    if isinstance(exact_total_duration, str) and exact_total_duration in DIAGNOSTICS_ACCEPTED_OPTIONS:
        if isinstance(diagnostics, (int, float, bool)) and not isinstance(diagnostics, str):
            LOG.warning(
                "H3 Continuum V2 detected the malformed 2.0.0 bundled workflow widget "
                "layout; repairing shifted settings in memory. exact_total_duration "
                "is restored to its default True. Save the workflow again after this run."
            )
            return (
                bool(audio_continuity),
                True,
                normalize_diagnostics_mode(exact_total_duration),
                int(diagnostics),
                int(reroll_from_chunk),
                bool(reroll_nonce),
                bool(strict_compatibility),
            )
    return (
        bool(audio_continuity),
        bool(exact_total_duration),
        normalize_diagnostics_mode(diagnostics),
        int(reroll_from_chunk),
        int(reroll_nonce),
        bool(strict_compatibility),
        bool(debug),
    )


class H3ContinuumSamplerV2:
    DESCRIPTION = (
        "Integrated N-chunk MiniMax H3 continuation sampler. Precomputes prompt/image "
        "conditioning, isolates accelerator runtime state per chunk, captures "
        "latent state before decoding, then decodes and assembles the final AV stream."
    )
    SEARCH_ALIASES = [
        "H3 long video sampler",
        "MiniMax H3 integrated continuation",
        "H3 Continuum V2",
    ]

    @classmethod
    def VALIDATE_INPUTS(cls, diagnostics):
        return True if diagnostics in DIAGNOSTICS_ACCEPTED_OPTIONS else f"unknown report detail: {diagnostics!r}"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
                "clip": ("CLIP",),
                "video_vae": ("VAE",),
                "audio_vae": ("VAE",),
                "sampler": ("SAMPLER",),
                "sigmas": ("SIGMAS",),
                "prompt_mode": (
                    PROMPT_FORMAT_OPTIONS,
                    {
                        "default": PROMPT_FORMAT_OPTIONS[0],
                        "tooltip": (
                            "Auto detects Fixed text, --- separated List text, or "
                            "[0-5s] / [Chunk 1] Timeline sections."
                        ),
                    },
                ),
                "prompt_script": (
                    "STRING",
                    {
                        "default": "Describe one continuous MiniMax H3 shot with audio.",
                        "multiline": True,
                        "dynamicPrompts": True,
                        "tooltip": (
                            "Fixed: one prompt. List: separate chunks with a line containing ---. "
                            "Timeline: use [0-5s], [5-10s], ... or [Chunk 1] headers."
                        ),
                    },
                ),
                "chunks": (
                    "INT",
                    {"default": 3, "min": 1, "max": 16, "step": 1},
                ),
                "chunk_seconds": (
                    "FLOAT",
                    {"default": 5.0, "min": 4.0, "max": 15.0, "step": 0.1, "tooltip": "Native H3 is trained for roughly 4–15 second outputs."},
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
                    {
                        "default": V2_CONTINUITY_OPTIONS[1],
                        "tooltip": (
                            "Balanced 22f reproduces the V1 default. Auto uses a conservative "
                            "latent-motion score and falls back to 22f near thresholds."
                        ),
                    },
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
                "audio_continuity": ("BOOLEAN", {"default": True}),
                "exact_total_duration": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "Trim or minimally pad the assembled result to chunks × seconds × 24fps.",
                    },
                ),
                "diagnostics": (
                    DIAGNOSTICS_OPTIONS,
                    {
                        "default": DIAGNOSTICS_OPTIONS[0],
                        "display_name": "Report Detail",
                        "tooltip": "Controls report verbosity only; it does not change generation or seam correction.",
                    },
                ),
                "reroll_from_chunk": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 16,
                        "step": 1,
                        "tooltip": (
                            "0 resumes/reuses every matching accepted chunk from the optional session. "
                            "N preserves chunks before N and regenerates N onward."
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
                        "tooltip": "Change this to derive new seeds for regenerated chunks only.",
                    },
                ),
                "strict_compatibility": ("BOOLEAN", {"default": True}),
                "debug": ("BOOLEAN", {"default": False}),
                "seam_correction": (
                    SEAM_CORRECTION_OPTIONS,
                    {
                        "default": SEAM_CORRECTION_AUTO,
                        "tooltip": (
                            "Auto keeps native video unless a no-blend candidate improves the boundary "
                            "and five-frame transition without component regression; audio is guarded "
                            "independently. Off preserves the decode path. Basic applies the decoded "
                            "A/V correction including conservative video blend."
                        ),
                    },
                ),
            },
            "optional": {
                "sequence_prompt": (
                    "STRING",
                    {
                        "forceInput": True,
                        "tooltip": (
                            "Connect one Text (Multiline). Prompt Format parses it for "
                            "the complete sequence without changing this socket."
                        ),
                    },
                ),
                "first_frame": ("IMAGE",),
                "last_frame": ("IMAGE",),
                "session": ("H3_CONTINUUM_SESSION",),
                "initial_state": ("H3_CONTINUUM_STATE",),
                "prompt_plan": ("H3_CONTINUUM_PROMPT_PLAN",),
                "show_preview": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "Show the in-progress latent thumbnail for this sampler node.",
                    },
                ),
                **{
                    f"clip_{index}_prompt": (
                        "STRING",
                        {
                            "forceInput": True,
                            "tooltip": f"Optional prompt override for Clip {index}.",
                        },
                    )
                    for index in range(1, 17)
                },
            },
        }

    RETURN_TYPES = (
        "IMAGE",
        "AUDIO",
        "H3_CONTINUUM_STATE",
        "H3_CONTINUUM_SESSION",
        "STRING",
    )
    RETURN_NAMES = ("images", "audio", "last_state", "session", "report")
    FUNCTION = "run"
    CATEGORY = CATEGORY

    def run(
        self,
        model,
        clip,
        video_vae,
        audio_vae,
        sampler,
        sigmas,
        prompt_mode,
        prompt_script,
        chunks,
        chunk_seconds,
        width,
        height,
        continuity,
        base_seed,
        audio_continuity,
        exact_total_duration,
        diagnostics,
        reroll_from_chunk,
        reroll_nonce,
        strict_compatibility,
        debug,
        seam_correction=SEAM_CORRECTION_OFF,
        first_frame=None,
        last_frame=None,
        session=None,
        initial_state=None,
        prompt_plan=None,
        sequence_prompt=None,
        show_preview=True,
        **clip_prompt_inputs,
    ):
        (
            audio_continuity,
            exact_total_duration,
            diagnostics,
            reroll_from_chunk,
            reroll_nonce,
            strict_compatibility,
            debug,
        ) = _repair_v200_example_widget_shift(
            audio_continuity=audio_continuity,
            exact_total_duration=exact_total_duration,
            diagnostics=diagnostics,
            reroll_from_chunk=reroll_from_chunk,
            reroll_nonce=reroll_nonce,
            strict_compatibility=strict_compatibility,
            debug=debug,
        )

        # V2.0.2 workflows stored show_preview in this newly inserted widget slot.
        if isinstance(seam_correction, bool):
            seam_correction = SEAM_CORRECTION_OFF

        prompt_plan = build_sampler_prompt_plan(
            prompt_mode=prompt_mode,
            prompt_script=prompt_script,
            sequence_prompt=sequence_prompt,
            prompt_plan=prompt_plan,
            chunks=int(chunks),
            chunk_seconds=float(chunk_seconds),
        )
        prompt_plan = apply_prompt_overrides(
            prompt_plan,
            [
                clip_prompt_inputs.get(f"clip_{index}_prompt")
                for index in range(1, int(chunks) + 1)
            ],
        )
        return run_sequence(
            model=model,
            clip=clip,
            video_vae=video_vae,
            audio_vae=audio_vae,
            sampler=sampler,
            sigmas=sigmas,
            first_frame=first_frame,
            last_frame=last_frame,
            prompt_plan=prompt_plan,
            width=int(width),
            height=int(height),
            continuity=continuity,
            base_seed=int(base_seed),
            audio_continuity=bool(audio_continuity),
            exact_total_duration=bool(exact_total_duration),
            diagnostics_mode=diagnostics,
            reroll_from_chunk=int(reroll_from_chunk),
            reroll_nonce=int(reroll_nonce),
            strict_compatibility=bool(strict_compatibility),
            debug=bool(debug),
            seam_correction=seam_correction,
            enable_preview=bool(show_preview),
            session=session,
            initial_state=initial_state,
        )


class H3ContinuumPromptPlanPreview:
    DESCRIPTION = "Validate and preview Fixed/List/Timeline prompt parsing without sampling."

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt_mode": (
                    PROMPT_FORMAT_OPTIONS,
                    {
                        "default": PROMPT_FORMAT_OPTIONS[0],
                        "tooltip": (
                            "Auto detects Fixed text, --- separated List text, or "
                            "[0-5s] / [Chunk 1] Timeline sections."
                        ),
                    },
                ),
                "prompt_script": ("STRING", {"default": "Prompt", "multiline": True}),
                "chunks": ("INT", {"default": 3, "min": 1, "max": 16, "step": 1}),
                "chunk_seconds": (
                    "FLOAT",
                    {"default": 5.0, "min": 4.0, "max": 15.0, "step": 0.1, "tooltip": "Native H3 is trained for roughly 4–15 second outputs."},
                ),
            }
        }

    RETURN_TYPES = ("H3_CONTINUUM_PROMPT_PLAN", "STRING")
    RETURN_NAMES = ("prompt_plan", "report")
    FUNCTION = "build"
    CATEGORY = CATEGORY

    def build(self, prompt_mode, prompt_script, chunks, chunk_seconds):
        plan = make_prompt_plan(
            mode=prompt_mode,
            script=prompt_script,
            chunks=int(chunks),
            chunk_seconds=float(chunk_seconds),
        )
        report = prompt_plan_report(plan) + "\n" + "\n\n".join(
            f"Chunk {index + 1}:\n{prompt}" for index, prompt in enumerate(plan["prompts"])
        )
        return plan, report


class H3ContinuumSaveSession:
    DESCRIPTION = "Atomically save every accepted V2 chunk latent plus session metadata."
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "session": ("H3_CONTINUUM_SESSION",),
                "prefix": ("STRING", {"default": "h3_continuum_session"}),
                "slot": ("INT", {"default": 1, "min": 1, "max": 9999, "step": 1}),
            }
        }

    RETURN_TYPES = ("H3_CONTINUUM_SESSION", "STRING")
    RETURN_NAMES = ("session", "path")
    FUNCTION = "save"
    CATEGORY = CATEGORY

    def save(self, session, prefix, slot):
        tensor_path, _json_path = save_session(session, prefix=prefix, slot=int(slot))
        return session, str(tensor_path)


class H3ContinuumLoadSession:
    DESCRIPTION = "Load an explicitly numbered V2 session for resume or reroll."

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prefix": ("STRING", {"default": "h3_continuum_session"}),
                "slot": ("INT", {"default": 1, "min": 1, "max": 9999, "step": 1}),
            }
        }

    RETURN_TYPES = ("H3_CONTINUUM_SESSION", "STRING")
    RETURN_NAMES = ("session", "path")
    FUNCTION = "load"
    CATEGORY = CATEGORY

    @classmethod
    def IS_CHANGED(cls, prefix, slot):
        return session_mtime(prefix=prefix, slot=int(slot))

    def load(self, prefix, slot):
        session = load_session(prefix=prefix, slot=int(slot))
        tensor_path, _json_path = session_paths(prefix, int(slot))
        return session, str(tensor_path)


class H3ContinuumSessionInfo:
    DESCRIPTION = "Inspect a V2 session and expose its final V1-compatible continuation state."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"session": ("H3_CONTINUUM_SESSION",)}}

    RETURN_TYPES = ("H3_CONTINUUM_SESSION", "H3_CONTINUUM_STATE", "STRING")
    RETURN_NAMES = ("session", "last_state", "report")
    FUNCTION = "inspect"
    CATEGORY = CATEGORY

    def inspect(self, session):
        session = validate_session(session)
        state = entry_to_state(session["chunks"][-1])
        report = session_summary(session)
        return session, state, report


class H3ContinuumClipOverrides:
    """Build a static prompt-override pack without per-clip sockets."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt_mode": (
                    PROMPT_FORMAT_OPTIONS,
                    {
                        "default": PROMPT_FORMAT_OPTIONS[0],
                        "display_name": "Prompt Format",
                    },
                ),
                "override_script": (
                    "STRING",
                    {
                        "forceInput": True,
                        "display_name": "Override Script",
                        "tooltip": (
                            "Connect one Text (Multiline). Use ---, [Chunk N], or "
                            "timeline sections according to Prompt Format."
                        ),
                    },
                ),
            }
        }

    RETURN_TYPES = ("H3_CONTINUUM_CLIP_OVERRIDES",)
    RETURN_NAMES = ("prompt_overrides",)
    FUNCTION = "build"
    CATEGORY = CATEGORY

    def build(self, prompt_mode, override_script):
        return (
            {
                "prompt_mode": str(prompt_mode),
                "prompt_script": str(override_script),
            },
        )


class H3ContinuumAdvanced:
    """Package optional continuation inputs and infrequent sampler settings."""

    @classmethod
    def VALIDATE_INPUTS(cls, diagnostics):
        return True if diagnostics in DIAGNOSTICS_ACCEPTED_OPTIONS else f"unknown report detail: {diagnostics!r}"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "audio_continuity": ("BOOLEAN", {"default": True}),
                "exact_total_duration": ("BOOLEAN", {"default": True}),
                "diagnostics": (
                    DIAGNOSTICS_OPTIONS,
                    {
                        "default": DIAGNOSTICS_OPTIONS[0],
                        "display_name": "Report Detail",
                        "tooltip": "Controls report verbosity only; it does not change generation or seam correction.",
                    },
                ),
                "reroll_from_chunk": (
                    "INT",
                    {"default": 0, "min": 0, "max": 16, "step": 1},
                ),
                "reroll_nonce": (
                    "INT",
                    {"default": 0, "min": 0, "max": 0xFFFFFFFF, "step": 1},
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

    RETURN_TYPES = ("H3_CONTINUUM_ADVANCED",)
    RETURN_NAMES = ("advanced",)
    FUNCTION = "build"
    CATEGORY = CATEGORY

    def build(
        self,
        audio_continuity,
        exact_total_duration,
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
                "exact_total_duration": bool(exact_total_duration),
                "diagnostics": normalize_diagnostics_mode(diagnostics),
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


class H3ContinuumSampler:
    """Stable, compact facade over the fully compatible V2 sampler core."""

    DESCRIPTION = (
        "Compact H3 Continuum sampler facade. Uses the legacy V2 execution core "
        "without dynamic sockets or frontend display patches."
    )
    SEARCH_ALIASES = ["H3 Continuum", "MiniMax H3 long video"]

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
                "clip": ("CLIP",),
                "video_vae": ("VAE",),
                "audio_vae": ("VAE",),
                "sampler": ("SAMPLER",),
                "sigmas": ("SIGMAS",),
                "sequence_prompt": (
                    "STRING",
                    {
                        "forceInput": True,
                        "display_name": "Sequence Prompt",
                        "tooltip": "Connect one Text (Multiline) for the complete sequence.",
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
                "width": ("INT", {"default": 1344, "min": 32, "max": 16384, "step": 32}),
                "height": ("INT", {"default": 768, "min": 32, "max": 16384, "step": 32}),
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
                "seam_correction": (
                    SEAM_CORRECTION_OPTIONS,
                    {
                        "default": SEAM_CORRECTION_AUTO,
                        "tooltip": (
                            "Auto is native-first: video correction is adopted only when the boundary "
                            "and five-frame transition clearly improve; audio is guarded independently."
                        ),
                    },
                ),
            },
            "optional": {
                "first_frame": ("IMAGE",),
                "prompt_overrides": ("H3_CONTINUUM_CLIP_OVERRIDES",),
                "advanced": ("H3_CONTINUUM_ADVANCED",),
            },
        }

    RETURN_TYPES = ("IMAGE", "AUDIO", "H3_CONTINUUM_RESULT")
    RETURN_NAMES = ("images", "audio", "result")
    FUNCTION = "run"
    CATEGORY = CATEGORY

    def run(
        self,
        model,
        clip,
        video_vae,
        audio_vae,
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
        seam_correction,
        first_frame=None,
        prompt_overrides=None,
        advanced=None,
    ):
        if prompt_overrides is not None and not isinstance(prompt_overrides, dict):
            raise TypeError("prompt_overrides must be an H3_CONTINUUM_CLIP_OVERRIDES pack")
        if advanced is not None and not isinstance(advanced, dict):
            raise TypeError("advanced must be an H3_CONTINUUM_ADVANCED pack")

        advanced_values = {
            "audio_continuity": True,
            "exact_total_duration": True,
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
            override_plan = make_prompt_plan(
                mode=prompt_overrides.get("prompt_mode", PROMPT_FORMAT_OPTIONS[0]),
                script=prompt_overrides.get("prompt_script", ""),
                chunks=int(chunks),
                chunk_seconds=float(chunk_seconds),
            )
            for index, prompt in enumerate(override_plan.get("prompts", []), start=1):
                if isinstance(prompt, str) and prompt.strip():
                    clip_prompt_inputs[f"clip_{index}_prompt"] = prompt

        images, audio, last_state, session, report = H3ContinuumSamplerV2().run(
            model=model,
            clip=clip,
            video_vae=video_vae,
            audio_vae=audio_vae,
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
            exact_total_duration=advanced_values["exact_total_duration"],
            diagnostics=advanced_values["diagnostics"],
            reroll_from_chunk=advanced_values["reroll_from_chunk"],
            reroll_nonce=advanced_values["reroll_nonce"],
            strict_compatibility=advanced_values["strict_compatibility"],
            debug=advanced_values["debug"],
            seam_correction=seam_correction,
            first_frame=first_frame,
            last_frame=advanced_values["last_frame"],
            session=advanced_values["session"],
            initial_state=advanced_values["initial_state"],
            prompt_plan=advanced_values["prompt_plan"],
            sequence_prompt=sequence_prompt,
            show_preview=advanced_values["show_preview"],
            **clip_prompt_inputs,
        )
        return (
            images,
            audio,
            {
                "last_state": last_state,
                "session": session,
                "report": report,
            },
        )


class H3ContinuumResult:
    """Expand the compact facade result pack only when advanced outputs are needed."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"result": ("H3_CONTINUUM_RESULT",)}}

    RETURN_TYPES = ("H3_CONTINUUM_STATE", "H3_CONTINUUM_SESSION", "STRING")
    RETURN_NAMES = ("last_state", "session", "report")
    FUNCTION = "unpack"
    CATEGORY = CATEGORY

    def unpack(self, result):
        if not isinstance(result, dict):
            raise TypeError("result must be an H3_CONTINUUM_RESULT pack")
        missing = {"last_state", "session", "report"} - set(result)
        if missing:
            raise ValueError("H3_CONTINUUM_RESULT is missing: " + ", ".join(sorted(missing)))
        return result["last_state"], result["session"], str(result["report"])


NODE_CLASS_MAPPINGS = {
    "H3ContinuumSampler": H3ContinuumSampler,
    "H3ContinuumClipOverrides": H3ContinuumClipOverrides,
    "H3ContinuumAdvanced": H3ContinuumAdvanced,
    "H3ContinuumResult": H3ContinuumResult,
    "H3ContinuumSamplerV2": H3ContinuumSamplerV2,
    "H3ContinuumPromptPlanPreview": H3ContinuumPromptPlanPreview,
    "H3ContinuumSaveSession": H3ContinuumSaveSession,
    "H3ContinuumLoadSession": H3ContinuumLoadSession,
    "H3ContinuumSessionInfo": H3ContinuumSessionInfo,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "H3ContinuumSampler": "H3 Continuum Sampler",
    "H3ContinuumClipOverrides": "H3 Continuum Clip Overrides",
    "H3ContinuumAdvanced": "H3 Continuum Advanced",
    "H3ContinuumResult": "H3 Continuum Result",
    "H3ContinuumSamplerV2": "H3 Continuum Sampler V2",
    "H3ContinuumPromptPlanPreview": "H3 Continuum Prompt Plan",
    "H3ContinuumSaveSession": "H3 Continuum Save Session",
    "H3ContinuumLoadSession": "H3 Continuum Load Session",
    "H3ContinuumSessionInfo": "H3 Continuum Session Info",
}
