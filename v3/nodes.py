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
from .plan import make_assembly_plan, make_review_audio_projection, REVIEW_AUDIO_PROJECTION_KEY
from .execution_planner import (
    PROJECTION_CURRENT_REVIEW_UNIT,
    PROJECTION_FULL_ACCEPTED_PREFIX,
    resolve_projection_decision as _resolve_projection_decision,
)
from .planning_types import ProjectionDecision
from .review_control import REVISION_STATUS_REVIEW_READY
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


_PARTIAL_REVIEW_SECOND_PASS_WARNING = (
    "Warning: Review is incomplete. Second Pass refinement of a partial review "
    "sequence is not yet supported."
)


def resolve_projection_decision(
    *,
    review_execution,
    effective_result_status: str,
    session,
    physical_group_facts: tuple[tuple[int, ...], ...],
) -> ProjectionDecision:
    """Compatibility adapter for the R1 pure resolver API."""

    entries = session.get("chunks") if isinstance(session, dict) else None
    return _resolve_projection_decision(
        review_execution=review_execution,
        effective_result_status=effective_result_status,
        accepted_chunks=(len(entries) if isinstance(entries, list) else 0),
        physical_group_facts=physical_group_facts,
    )


def _physical_group_facts(assembly_plan) -> tuple[tuple[int, ...], ...]:
    """Extract immutable logical membership facts from an existing assembly plan."""

    if not isinstance(assembly_plan, dict):
        return ()
    groups = assembly_plan.get("decode_groups") or assembly_plan.get("chunks")
    if not isinstance(groups, list):
        return ()
    facts = []
    for group in groups:
        if not isinstance(group, dict):
            return ()
        indices = group.get("logical_chunk_indices")
        if indices is None:
            indices = [group.get("chunk_index")]
        if not isinstance(indices, list) or not indices:
            return ()
        try:
            normalized = tuple(int(index) for index in indices)
        except (TypeError, ValueError):
            return ()
        if any(index < 1 for index in normalized):
            return ()
        facts.append(normalized)
    return tuple(facts)


def _partial_review_warning(storage, *, capture_refine_context: bool) -> str:
    execution = getattr(storage, "review_execution", None)
    if (
        bool(capture_refine_context)
        and execution is not None
        and bool(getattr(execution, "partial_review", False))
    ):
        return _PARTIAL_REVIEW_SECOND_PASS_WARNING
    return ""


def _review_decode_chunk_range(storage, *, capture_refine_context: bool):
    # Refine context is a separate, preserved output; capturing it does not
    # require external VAE nodes to decode the entire accepted prefix.
    if getattr(storage, "review_generation_mode", None) != "Review Each Chunk":
        return None
    execution = getattr(storage, "review_execution", None)
    if execution is None or bool(getattr(execution, "finish_remaining", False)):
        return None
    start = getattr(execution, "next_review_unit_start", None)
    end = getattr(execution, "next_review_unit_end", None)
    if start is None or end is None:
        return None
    if not (
        bool(getattr(execution, "partial_review", False))
        or bool(getattr(execution, "smart_regenerate", False))
    ):
        return None
    return int(start), int(end)


def _apply_review_decode_scope(
    outputs,
    *,
    storage,
    capture_refine_context: bool,
    configured_chunks: int,
    chunk_seconds: float,
    first_frame,
    last_frame,
    timeline_video_source,
):
    _, _, assembly_plan, result, *tail = outputs
    session = result.get("session") if isinstance(result, dict) else None
    entries = session.get("chunks") if isinstance(session, dict) else None
    if not isinstance(entries, list):
        return outputs
    execution_plan = getattr(storage, "execution_plan", None)
    decision = getattr(execution_plan, "projection", None)
    if not isinstance(decision, ProjectionDecision):
        # Compatibility for isolated callers that replace the sequence runtime
        # and therefore cannot carry its Queue-local plan.  The same pure
        # resolver remains the only Projection owner.
        effective_status = (
            REVISION_STATUS_REVIEW_READY
            if getattr(storage, "review_generation_mode", None)
            == "Review Each Chunk"
            else "complete"
        )
        decision = resolve_projection_decision(
            review_execution=getattr(storage, "review_execution", None),
            effective_result_status=effective_status,
            session=session,
            physical_group_facts=_physical_group_facts(assembly_plan),
        )
    if decision.kind != PROJECTION_CURRENT_REVIEW_UNIT:
        return outputs
    start = int(decision.start_chunk)
    end = int(decision.end_chunk)
    audio_projection = make_review_audio_projection(
        assembly_plan, start_chunk=start, end_chunk=end,
    )

    selected_entries = entries[start - 1 : end]
    sequence_complete = len(entries) == int(configured_chunks)
    from ..v2.sequence import _terminal_flf_merge_enabled
    from .plan import prepare_physical_decode_entries

    terminal_merged = sequence_complete and _terminal_flf_merge_enabled(
        multi_chunk_flf=(
            first_frame is not None
            and last_frame is not None
            and int(configured_chunks) > 1
        ),
        chunks=int(configured_chunks),
        chunk_seconds=float(chunk_seconds),
        prompt_hashes=[str(entry["prompt_hash"]) for entry in entries],
        timeline_video_source=timeline_video_source,
    )
    selected_terminal_merged = terminal_merged and (
        end == int(configured_chunks)
        and start <= int(configured_chunks) - 1
    )
    decode_entries, scoped_plan = prepare_physical_decode_entries(
        selected_entries,
        chunk_seconds=float(chunk_seconds),
        preserve_final_frame=(
            sequence_complete
            and end == int(configured_chunks)
            and last_frame is not None
        ),
        terminal_merged=selected_terminal_merged,
        terminal_initial_pair=(start == 1),
    )
    scoped_plan[REVIEW_AUDIO_PROJECTION_KEY] = audio_projection
    # Projection narrows the AV decode view, not the already-verified routing
    # decision. Keep that Queue-local plan available to the public Inspector.
    route_plan = assembly_plan.get("reference_routing_v1")
    if isinstance(route_plan, dict):
        scoped_plan = dict(scoped_plan)
        scoped_plan["reference_routing_v1"] = route_plan
    scoped_video = [{"samples": entry["video"]} for entry in decode_entries]
    scoped_audio = [{"samples": entry["audio"]} for entry in decode_entries]
    scoped_result = dict(result)
    scoped_result["report"] = str(scoped_result.get("report", "")).rstrip() + (
        f"\nDecode preview: Chunk {start}"
        if start == end
        else f"\nDecode preview: Chunks {start}-{end}"
    )
    return (scoped_video, scoped_audio, scoped_plan, scoped_result, *tail)


def _format_review_status(storage, *, detailed: bool = False) -> str:
    """Format Phase D facts after finalize without reading storage in frontend."""

    execution = getattr(storage, "review_execution", None)
    if execution is None:
        return ""
    if getattr(storage, "review_generation_mode", None) != "Review Each Chunk":
        return str(getattr(execution, "status_hint", "")).strip()

    manifest = getattr(storage, "manifest", None)
    contract = getattr(storage, "contract", None)
    if not isinstance(manifest, dict) or not isinstance(contract, dict):
        return str(getattr(execution, "status_hint", "")).strip()
    total = int(contract.get("chunk_count", 0))
    completed = len(list(manifest.get("chunks") or []))
    unit = manifest.get("review_unit")
    if not isinstance(unit, dict):
        unit = None

    if bool(getattr(execution, "finish_remaining", False)):
        return "\n".join(
            (
                "Review completed",
                (
                    f"{int(getattr(storage, 'reused_count', 0))} reused; "
                    f"{int(getattr(storage, 'generated_count', 0))} generated; "
                    f"{total} total"
                ),
                "Sequence complete",
            )
        )

    if unit is None:
        if completed >= total > 0:
            return "Review Mode\nSequence complete"
        return str(getattr(execution, "status_hint", "")).strip()

    start = int(unit.get("start", 0))
    end = int(unit.get("end", 0))
    terminal = start != end
    if bool(getattr(execution, "smart_regenerate", False)):
        regenerated = (
            f"Chunk {start} regenerated"
            if not terminal
            else f"Chunks {start}-{end} regenerated"
        )
        lines = ["Smart Regenerate", regenerated]
        if start > 1:
            lines.append(f"Preserved: Chunks 1-{start - 1}")
        if terminal:
            lines.append("Terminal Merge: 1 physical review unit")
        if detailed:
            variation = getattr(execution, "requested_effective_nonce", None)
            if variation is not None:
                lines.append(f"Variation: {int(variation)}")
        lines.append("Ready for review")
        if completed >= total > 0:
            lines.append("Sequence complete")
        return "\n".join(lines)

    ready = (
        f"Chunk {start} / {total} ready"
        if not terminal
        else f"Chunks {start}-{end} / {total} ready"
    )
    lines = ["Review Mode", ready]
    if terminal:
        lines.append("Terminal Merge: 1 physical review unit")
    if completed > 0:
        lines.append(f"Completed: Chunks 1-{completed}")
    if completed >= total > 0:
        lines.append("Sequence complete")
    else:
        lines.extend(
            (
                "Next: Queue again = Accept + Continue",
                "Options: Regenerate Current / Finish Remaining",
            )
        )
    return "\n".join(lines)


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
        reference_encode_cache=False,
        continuation_transport="reference_context_v1",
        max_new_physical_groups=None,
        reference_routing_request=None,
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
            "_diagnostic_continuation_policy": None,
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
            reference_encode_cache=bool(reference_encode_cache),
            continuation_transport=str(continuation_transport),
            max_new_physical_groups=max_new_physical_groups,
            reference_routing_request=reference_routing_request,
            _diagnostic_continuation_policy=advanced_values[
                "_diagnostic_continuation_policy"
            ],
            **clip_prompt_inputs,
        )
        if bool(capture_refine_context):
            entries, last_state, session, report, refine_context = sequence_outputs
        else:
            entries, last_state, session, report = sequence_outputs

        from ..v2.sequence import _terminal_flf_merge_enabled
        from .plan import prepare_physical_decode_entries

        configured_chunks = int(chunks)
        completed_chunks = len(entries)
        sequence_complete = completed_chunks == configured_chunks
        terminal_merged = sequence_complete and _terminal_flf_merge_enabled(
            multi_chunk_flf=(
                first_frame is not None
                and advanced_values["last_frame"] is not None
                and configured_chunks > 1
            ),
            chunks=configured_chunks,
            chunk_seconds=float(chunk_seconds),
            prompt_hashes=[str(entry["prompt_hash"]) for entry in entries],
            timeline_video_source=timeline_video_source,
        )
        decode_entries, assembly_plan = prepare_physical_decode_entries(
            entries,
            chunk_seconds=float(chunk_seconds),
            preserve_final_frame=(
                sequence_complete and advanced_values["last_frame"] is not None
            ),
            terminal_merged=terminal_merged,
        )
        if reference_routing_request is not None:
            from .reference_plan_inspector import project_reference_plan
            runtime = reference_routing_request.runtime
            if runtime is None:
                raise RuntimeError("Reference Routing completed without its runtime Plan")
            assembly_plan = dict(assembly_plan)
            assembly_plan["reference_routing_v1"] = project_reference_plan(runtime)
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
                "model": (
                    "MODEL",
                    {
                        "tooltip": (
                            "MiniMax H3 diffusion model used for every Continuum chunk."
                        )
                    },
                ),
                "clip": (
                    "CLIP",
                    {
                        "tooltip": (
                            "MiniMax H3 text encoder used to encode the complete Sequence Prompt."
                        )
                    },
                ),
                "video_vae": (
                    "VAE",
                    {
                        "tooltip": (
                            "Used only to encode image conditioning. T2VA does "
                            "not use it; Continuum never decodes with it."
                        ),
                    },
                ),
                "sampler": (
                    "SAMPLER",
                    {
                        "tooltip": (
                            "ComfyUI sampler algorithm used unchanged for every generated chunk."
                        )
                    },
                ),
                "sigmas": (
                    "SIGMAS",
                    {
                        "tooltip": (
                            "ComfyUI noise schedule used unchanged for every generated chunk."
                        )
                    },
                ),
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
                        "tooltip": "Controls the detail level of the read-only Status report. It does not change generated tensors.",
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
                    {
                        "default": True,
                        "advanced": True,
                        "tooltip": "Legacy saved-workflow input. V3.8 keeps it loadable but ignores its value.",
                    },
                ),
                "debug": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "advanced": True,
                        "tooltip": "Developer diagnostics controlled by the H3 Continuum settings panel.",
                    },
                ),
                "show_preview": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "advanced": True,
                        "tooltip": "Show live sampling previews. Disable only to reduce preview overhead.",
                    },
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
                    {
                        "tooltip": (
                            "First Image conditioning for I2VA or FL2VA. With Output Size = "
                            "First Image, its aspect ratio also defines the output canvas. Leave "
                            "it disconnected and use Manual Width/Height for T2VA."
                        )
                    },
                ),
                "last_frame": (
                    "IMAGE",
                    {"tooltip": "Optional last-frame anchor for FL2VA. Leave disconnected for T2VA and normal I2VA."},
                ),
                "reference_image_1": (
                    "IMAGE",
                    {"tooltip": "Optional Reference Image 1 for appearance, identity, subject, or scene guidance."},
                ),
                "reference_image_2": (
                    "IMAGE",
                    {"tooltip": "Optional Reference Image 2. Prompt references follow the connected image order."},
                ),
                "reference_image_3": (
                    "IMAGE",
                    {"tooltip": "Optional Reference Image 3. Prompt references follow the connected image order."},
                ),
                "reference_audio_1": (
                    "AUDIO",
                    {"tooltip": "Legacy optional single Reference Audio. Do not connect it together with Audio References."},
                ),
                "reference_audio_vae": (
                    "VAE",
                    {"tooltip": "Audio VAE used only by the legacy single Reference Audio input."},
                ),
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
        reference_encode_cache=False,
        continuation_transport="reference_context_v1",
        max_new_physical_groups=None,
        generation_mode=None,
        review_action=None,
        take_group=0,
        take_revision_id="",
        take_action="Automatic",
        _diagnostic_continuation_policy=None,
        audio_references=None,
        reference_image_4=None,
        reference_image_5=None,
        image_references=None,
        _reference_routing_settings=None,
    ):
        runtime_started_at = time.perf_counter()
        from ..reference import prepare_reference_assets
        from ..reference_audio import resolve_reference_audio_input
        regenerate_from = _regenerate_from_value(
            reroll_from_chunk,
            chunks=int(chunks),
        )
        review_requested = generation_mode is not None or review_action is not None
        take_requested = str(take_action) != "Automatic"
        if review_requested and (generation_mode is None or review_action is None):
            raise ValueError(
                "internal review execution requires both generation_mode and review_action"
            )
        if review_requested and max_new_physical_groups is not None:
            raise ValueError(
                "internal review execution owns max_new_physical_groups"
            )
        if take_requested and generation_mode != "Review Each Chunk":
            raise ValueError("Take selection requires Review Each Chunk")
        reference_routing_request = None
        if _reference_routing_settings is None:
            reference_assets = prepare_reference_assets(
                reference_image_1=reference_image_1,
                reference_image_2=reference_image_2,
                output_width=int(width),
                output_height=int(height),
                size_mode=reference_size,
                reference_image_3=reference_image_3,
                reference_image_4=reference_image_4,
                reference_image_5=reference_image_5,
                image_references=image_references,
            )
        else:
            from .reference_runtime import ReferenceInputSet, ReferenceRoutingRequest
            reference_assets = None
            reference_routing_request = ReferenceRoutingRequest(
                selectors_by_slot=dict(_reference_routing_settings),
                inputs=ReferenceInputSet.from_inputs(
                    reference_image_1=reference_image_1,
                    reference_image_2=reference_image_2,
                    reference_image_3=reference_image_3,
                    reference_image_4=reference_image_4,
                    reference_image_5=reference_image_5,
                    image_references=image_references,
                    output_width=int(width),
                    output_height=int(height),
                    size_mode=reference_size,
                ),
            )
        reference_audio_source, resolved_reference_audio_vae = resolve_reference_audio_input(
            reference_audio_1,
            reference_audio_vae,
            audio_references,
        )
        def mark_runtime_start(assembly_plan):
            marked = dict(assembly_plan)
            marked["_runtime_started_at"] = runtime_started_at
            return marked

        def append_reference_plan(report, assembly_plan):
            if reference_routing_request is None:
                return str(report)
            from .reference_plan_inspector import format_reference_plan
            plan_view = assembly_plan.get("reference_routing_v1")
            if not isinstance(plan_view, dict):
                raise RuntimeError("Reference Routing output has no verified Plan")
            return str(report).rstrip() + "\n" + format_reference_plan(plan_view)

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
                reference_audio_vae=resolved_reference_audio_vae,
                driving_audio_source=driving_audio_source,
                driving_audio_vae=driving_audio_vae,
                reference_video_source=reference_video_source,
                timeline_video_source=timeline_video_source,
                guide_source=guide_source,
                capture_refine_context=bool(capture_refine_context),
                memory_attribution=bool(memory_attribution),
                prompt_conditioning_cache=bool(prompt_conditioning_cache),
                reference_encode_cache=bool(reference_encode_cache),
                reference_routing_request=reference_routing_request,
                continuation_transport=str(continuation_transport),
                max_new_physical_groups=max_new_physical_groups,
                advanced={
                    "audio_continuity": bool(audio_continuity),
                    "diagnostics": diagnostics,
                    "reroll_from_chunk": regenerate_from,
                    "reroll_nonce": int(reroll_nonce),
                    "strict_compatibility": False,
                    "debug": bool(debug),
                    "show_preview": bool(show_preview),
                    "last_frame": last_frame,
                    "_diagnostic_continuation_policy": _diagnostic_continuation_policy,
                },
            )

        if run_storage == "Off":
            if take_requested:
                raise ValueError(
                    "Use This Take / Continue From Here requires Run Storage = Save + Auto Resume."
                )
            if review_requested:
                from .review_control import GENERATION_MODE_REVIEW

                if generation_mode == GENERATION_MODE_REVIEW:
                    raise ValueError(
                        "Review Each Chunk requires Run Storage = Save + Auto Resume."
                    )
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
                append_reference_plan(result["report"], assembly_plan),
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
            if review_requested:
                storage.configure_review(
                    generation_mode=str(generation_mode),
                    review_action=str(review_action),
                    manual_regenerate_from=regenerate_from,
                    take_group=int(take_group),
                    take_revision_id=str(take_revision_id),
                    take_action=str(take_action),
                )
            execute_outputs = execute()
            execute_outputs = _apply_review_decode_scope(
                execute_outputs,
                storage=storage,
                capture_refine_context=bool(capture_refine_context),
                configured_chunks=int(chunks),
                chunk_seconds=float(chunk_seconds),
                first_frame=first_frame,
                last_frame=last_frame,
                timeline_video_source=timeline_video_source,
            )
            if bool(capture_refine_context):
                video_latents, audio_latents, assembly_plan, result, refine_context = execute_outputs
            else:
                video_latents, audio_latents, assembly_plan, result = execute_outputs
            result = dict(result)
            report = append_reference_plan(result["report"], assembly_plan) + "\n" + storage.summary(
                detailed=diagnostics == DIAGNOSTICS_FULL
            )
            warning = _partial_review_warning(
                storage,
                capture_refine_context=bool(capture_refine_context),
            )
            if warning:
                report += "\n" + warning
            result["report"] = report
            storage.finalize(
                session=result["session"],
                report=report,
                review_pause_metadata=storage.review_pause_metadata(),
            )
            review_status = _format_review_status(
                storage,
                detailed=diagnostics == DIAGNOSTICS_FULL,
            )
            if review_status:
                report += "\n" + review_status
            result["report"] = report
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
