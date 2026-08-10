"""Integrated N-chunk Continuum runtime.

V2 deliberately reuses the proven V1 continuation core. It changes execution
orchestration only: all text/image conditioning is prepared first, H3 sampling
runs for every chunk without intermediate VAE decoding, and decoding/assembly
happens after the sampling phase.
"""

from __future__ import annotations

import copy
import logging
from typing import Any

import torch

from ..compatibility import accelerator_summary, check_comfy_h3_runtime
from ..constants import (
    DIAGNOSTICS_FULL,
    DIAGNOSTICS_OFF,
    DIAGNOSTICS_OPTIONS,
    FPS,
    CONTINUUM_ACTUAL_PREFIX_STEPS,
    SEAM_CORRECTION_AUTO,
    SEAM_CORRECTION_OFF,
    SEAM_CORRECTION_OPTIONS,
    V2_CONTINUITY_AUTO,
)
from ..continuation import POLICY_REPLACE, prepare_conditioning
from ..model_patch import clone_model_for_chunk, patch_model
from ..state import (
    assert_context_unchanged,
    context_fingerprint,
    make_plan,
    select_context,
    validate_state,
)
from ..temporal import (
    align_frame_count_up,
    largest_context_capacity,
    make_extension_shape,
)
from ..version import PACKAGE_VERSION
from .decoder import decode_sequence, decode_sequence_with_seam, enforce_total_frames
from .h3_builder import (
    attach_keyframes,
    empty_h3_latent,
    encode_identity_latents,
    encode_prompt_conditioning,
    prepare_identity_assets,
)
from .motion import choose_context_frames
from .prompts import prompt_plan_report, validate_prompt_plan
from .sampling import sample_chunk
from .seeds import derive_chunk_seed
from .session import (
    SessionValidationError,
    entry_to_state,
    make_chunk_entry,
    make_session,
    model_fingerprint,
    session_summary,
    validate_chunk_entry,
    validate_session,
)

LOG = logging.getLogger("h3_continuum_join")


class SequenceRuntimeError(RuntimeError):
    pass


def _check_decode_memory_budget(
    *, width: int, height: int, chunks: int, chunk_seconds: float
) -> tuple[float, float | None]:
    """Fail before sampling when the eventual CPU IMAGE output is unsafe.

    ComfyUI IMAGE tensors are normally float32. V2 preallocates the final output
    once, but one raw VAE chunk and normal process headroom still coexist with it.
    The estimate is conservative and intentionally protects long/high-resolution
    jobs from failing only after every expensive H3 chunk has completed.
    """

    target_frames = max(1, int(round(chunks * chunk_seconds * FPS)))
    max_chunk_frames = max(5, int(round(chunk_seconds * FPS)) + 39)
    image_bytes = target_frames * width * height * 3 * 4
    transient_bytes = max_chunk_frames * width * height * 3 * 4
    required_bytes = image_bytes + int(transient_bytes * 1.5) + 1 * 1024**3
    estimate_gib = required_bytes / 1024**3
    available_gib: float | None = None
    try:
        import psutil

        available = int(psutil.virtual_memory().available)
        available_gib = available / 1024**3
        if required_bytes > int(available * 0.75):
            raise SequenceRuntimeError(
                "estimated decoded output requires about "
                f"{estimate_gib:.1f} GiB including one-chunk headroom, but only "
                f"{available_gib:.1f} GiB RAM is currently available. Reduce chunks, "
                "chunk_seconds, or resolution before sampling."
            )
    except ImportError:
        pass
    return estimate_gib, available_gib


def _clone_entry_for_reuse(entry: dict[str, Any]) -> dict[str, Any]:
    entry = validate_chunk_entry(entry)
    result = dict(entry)
    result["plan"] = copy.deepcopy(entry["plan"])
    result["reused"] = True
    return result


def _preserved_prefix(
    *,
    session: dict[str, Any] | None,
    prompt_hashes: list[str],
    chunks: int,
    reroll_from_chunk: int,
    width: int,
    height: int,
    chunk_seconds: float,
    identity_hash: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    if session is None:
        return [], []
    session = validate_session(session)
    notes: list[str] = []
    if int(session["width"]) != int(width) or int(session["height"]) != int(height):
        raise SessionValidationError(
            f"session is {session['width']}x{session['height']} but V2 is configured for {width}x{height}"
        )
    if abs(float(session["chunk_seconds"]) - float(chunk_seconds)) > 1e-6:
        raise SessionValidationError(
            f"session chunk_seconds={session['chunk_seconds']} does not match {chunk_seconds}"
        )
    if str(session.get("identity_hash", "none")) != str(identity_hash):
        raise SessionValidationError(
            "the current first-frame identity image does not match the saved session"
        )

    if reroll_from_chunk < 0 or reroll_from_chunk > chunks:
        raise SessionValidationError("reroll_from_chunk must be 0 or a valid one-based chunk index")
    limit = min(len(session["chunks"]), chunks)
    if reroll_from_chunk > 0:
        limit = min(limit, reroll_from_chunk - 1)

    preserved: list[dict[str, Any]] = []
    for index in range(limit):
        entry = validate_chunk_entry(session["chunks"][index])
        if entry["prompt_hash"] != prompt_hashes[index]:
            notes.append(
                f"session reuse stopped before chunk {index + 1}: prompt changed"
            )
            break
        preserved.append(_clone_entry_for_reuse(entry))
    if reroll_from_chunk == 0 and len(preserved) == min(len(session["chunks"]), chunks):
        if len(session["chunks"]) < chunks:
            notes.append(f"resuming after accepted chunk {len(session['chunks'])}")
        else:
            notes.append("all requested chunks reused from the session")
    elif reroll_from_chunk > 0:
        notes.append(
            f"preserved chunks 1-{len(preserved)}; regenerated from chunk {reroll_from_chunk}"
        )
    return preserved, notes


def _conditioning_cache(
    *,
    clip: Any,
    prompts: list[str],
    assets: Any,
    final_has_last_frame: bool,
) -> dict[tuple[str, bool], list]:
    cache: dict[tuple[str, bool], list] = {}
    final_index = len(prompts) - 1
    for index, prompt in enumerate(prompts):
        include_last = bool(final_has_last_frame and index == final_index)
        key = (prompt, include_last)
        if key in cache:
            continue
        cache[key] = encode_prompt_conditioning(
            clip,
            prompt,
            first_image=assets.first_image,
            last_image=assets.last_image if include_last else None,
        )
    return cache


def run_sequence(
    *,
    model: Any,
    clip: Any,
    video_vae: Any,
    audio_vae: Any,
    sampler: Any,
    sigmas: torch.Tensor,
    first_frame: torch.Tensor | None,
    last_frame: torch.Tensor | None,
    prompt_plan: dict[str, Any],
    width: int,
    height: int,
    continuity: str,
    base_seed: int,
    audio_continuity: bool,
    exact_total_duration: bool,
    diagnostics_mode: str,
    reroll_from_chunk: int,
    reroll_nonce: int,
    strict_compatibility: bool,
    debug: bool,
    seam_correction: str = SEAM_CORRECTION_OFF,
    enable_preview: bool = True,
    session: dict[str, Any] | None = None,
    initial_state: dict[str, Any] | None = None,
) -> tuple[torch.Tensor, dict[str, Any], dict[str, Any], dict[str, Any], str]:
    """Generate or resume a complete Continuum sequence."""

    plan = validate_prompt_plan(prompt_plan)
    chunks = int(plan["chunks"])
    chunk_seconds = float(plan["chunk_seconds"])
    prompts = list(plan["prompts"])
    prompt_hashes = list(plan["hashes"])
    width, height = int(width), int(height)
    if width <= 0 or height <= 0 or width % 32 or height % 32:
        raise SequenceRuntimeError("width and height must be positive multiples of 32")
    if session is not None and initial_state is not None:
        raise SequenceRuntimeError("connect either a session or an initial_state, not both")
    if diagnostics_mode not in DIAGNOSTICS_OPTIONS:
        raise SequenceRuntimeError(f"unknown diagnostics mode: {diagnostics_mode!r}")
    if seam_correction not in SEAM_CORRECTION_OPTIONS:
        raise SequenceRuntimeError(f"unknown seam correction mode: {seam_correction!r}")
    if not (0 <= int(reroll_from_chunk) <= chunks):
        raise SequenceRuntimeError(
            "reroll_from_chunk must be 0 or a valid one-based chunk index"
        )
    if initial_state is not None and int(reroll_from_chunk) not in (0, 1):
        raise SequenceRuntimeError(
            "with initial_state, reroll_from_chunk can only be 0 or 1"
        )
    decode_estimate_gib, available_ram_gib = _check_decode_memory_budget(
        width=width,
        height=height,
        chunks=chunks,
        chunk_seconds=chunk_seconds,
    )

    issues = check_comfy_h3_runtime()
    if issues and strict_compatibility:
        raise SequenceRuntimeError("H3 runtime is incompatible: " + "; ".join(issues))

    # Phase 1: all CLIP and VAE encoding happens before H3 sampling. This is the
    # key residency optimization: no text encoder or VAE is requested between
    # H3 chunks.
    assets = prepare_identity_assets(
        video_vae,
        width=width,
        height=height,
        first_frame=first_frame,
        last_frame=last_frame,
        encode_latents=False,
    )

    patched_model = patch_model(
        model,
        strict=bool(strict_compatibility),
        debug=bool(debug),
    )
    current_model_fingerprint = model_fingerprint(patched_model)
    preserved, reuse_notes = _preserved_prefix(
        session=session,
        prompt_hashes=prompt_hashes,
        chunks=chunks,
        reroll_from_chunk=int(reroll_from_chunk),
        width=width,
        height=height,
        chunk_seconds=chunk_seconds,
        identity_hash=assets.identity_hash,
    )
    if session is not None:
        old_fingerprint = str(session.get("model_fingerprint", ""))
        if old_fingerprint and old_fingerprint != current_model_fingerprint:
            reuse_notes.append(
                "model/accelerator fingerprint differs from the saved session; accepted chunks were kept"
            )

    cache: dict[tuple[str, bool], list] = {}
    if len(preserved) < chunks:
        assets = encode_identity_latents(video_vae, assets)
        cache = _conditioning_cache(
            clip=clip,
            prompts=prompts,
            assets=assets,
            final_has_last_frame=last_frame is not None,
        )

    entries: list[dict[str, Any]] = preserved[:]
    previous_state = None
    if entries:
        previous_state = entry_to_state(entries[-1])
    elif initial_state is not None:
        previous_state = validate_state(initial_state)
        if int(previous_state["width"]) != width or int(previous_state["height"]) != height:
            raise SequenceRuntimeError(
                f"initial_state is {previous_state['width']}x{previous_state['height']} "
                f"but V2 is configured for {width}x{height}"
            )

    initial_frame_count = align_frame_count_up(int(round(chunk_seconds * FPS)))
    retained_frames = sum(int(entry["plan"]["net_frames"]) for entry in entries)
    sampling_reports: list[str] = []

    # Phase 2: H3-only loop. Each chunk gets a MODEL clone so accelerator runtime
    # history cannot leak across chunks. Sampler/sigmas remain shared, and decoded
    # media is deliberately not requested until every chunk is done.
    for sequence_index in range(len(entries), chunks):
        prompt = prompts[sequence_index]
        prompt_hash_value = prompt_hashes[sequence_index]
        is_final = sequence_index == chunks - 1
        seed = derive_chunk_seed(base_seed, sequence_index, reroll_nonce)
        motion_score = 0.0
        video_context = None
        audio_context = None
        context_before = None

        if previous_state is None:
            total_frames = initial_frame_count
            latent = empty_h3_latent(width, height, total_frames)
            conditioning = attach_keyframes(
                cache[(prompt, bool(last_frame is not None and is_final))],
                frame_count=total_frames,
                first_latent=assets.first_latent,
                last_latent=assets.last_latent if is_final else None,
            )
            clip_index = 1
            context_frames = 0
            chunk_plan = make_plan(
                continuation=False,
                clip_index=clip_index,
                total_frames=total_frames,
                trim_frames=0,
                width=width,
                height=height,
                context_frames=5,
                state_capacity_frames=largest_context_capacity(total_frames),
                requested_extend_seconds=chunk_seconds,
                debug=debug,
            )
            reason = "initial clip"
        else:
            context_frames, motion_score, reason = choose_context_frames(
                continuity, previous_state
            )
            desired_cumulative = int(round((sequence_index + 1) * chunk_seconds * FPS))
            requested_new_frames = max(1, desired_cumulative - retained_frames)
            shape = make_extension_shape(
                context_frames, requested_new_frames / FPS
            )
            latent = empty_h3_latent(width, height, shape.total_frames)
            base_conditioning = attach_keyframes(
                cache[(prompt, bool(last_frame is not None and is_final))],
                frame_count=shape.total_frames,
                first_latent=assets.first_latent,
                last_latent=assets.last_latent if is_final else None,
            )
            video_context, audio_context, grid_offset = select_context(
                previous_state,
                context_frames,
                include_audio=bool(audio_continuity),
            )
            context_before = context_fingerprint(video_context, audio_context)
            conditioning = prepare_conditioning(
                base_conditioning,
                video_context=video_context,
                audio_context=audio_context,
                audio_grid_offset=grid_offset,
                context_frames=context_frames,
                new_frame_count=shape.total_frames,
                first_frame_policy=POLICY_REPLACE,
                preserve_last_frame=True,
            )
            clip_index = int(previous_state["clip_index"]) + 1
            chunk_plan = make_plan(
                continuation=True,
                clip_index=clip_index,
                total_frames=shape.total_frames,
                trim_frames=context_frames,
                width=width,
                height=height,
                context_frames=context_frames,
                state_capacity_frames=largest_context_capacity(shape.net_new_frames),
                requested_extend_seconds=chunk_seconds,
                debug=debug,
            )

        chunk_model = clone_model_for_chunk(
            patched_model,
            strict=bool(strict_compatibility),
            debug=bool(debug),
            chunk_index=clip_index,
            context_frames=context_frames if previous_state is not None else None,
        )
        sampled = sample_chunk(
            model=chunk_model,
            conditioning=conditioning,
            latent=latent,
            sampler=sampler,
            sigmas=sigmas,
            seed=seed,
            enable_preview=bool(enable_preview),
        )
        if context_before is not None and video_context is not None:
            assert_context_unchanged(
                video_context,
                audio_context,
                context_before,
            )
        # Commit the full chunk to CPU once, then derive the small next-state tail
        # from that CPU entry. This avoids a second device-to-host transfer.
        entry = make_chunk_entry(
            latent=sampled,
            plan=chunk_plan,
            prompt=prompt,
            prompt_hash=prompt_hash_value,
            seed=seed,
            context_frames=context_frames,
            motion_score=motion_score,
            reused=False,
        )
        previous_state = entry_to_state(entry)
        entries.append(entry)
        retained_frames += int(chunk_plan["net_frames"])
        sampling_reports.append(
            f"chunk {sequence_index + 1}/{chunks}: seed={seed}, "
            f"frames={chunk_plan['total_frames']}, trim={chunk_plan['trim_frames']}, "
            f"retained_total={retained_frames}, context={context_frames} "
            f"({reason}), motion={motion_score:.6f}, "
            + (
                f"interop=emitted actual_prefix={CONTINUUM_ACTUAL_PREFIX_STEPS} "
                "consumer=not_observable"
                if context_before is not None
                else "interop=not_emitted"
            )
        )
        del sampled, latent, conditioning, chunk_model

    if len(entries) != chunks:
        raise SequenceRuntimeError(
            f"internal sequence length mismatch: expected {chunks}, got {len(entries)}"
        )

    # Phase 3: VAE decode only after all H3 sampling is complete.
    if seam_correction == SEAM_CORRECTION_OFF:
        images, audio, decode_reports = decode_sequence(
            entries=entries,
            video_vae=video_vae,
            audio_vae=audio_vae,
            diagnostics_full=diagnostics_mode == DIAGNOSTICS_FULL,
        )
    else:
        images, audio, decode_reports = decode_sequence_with_seam(
            entries=entries,
            video_vae=video_vae,
            audio_vae=audio_vae,
            diagnostics_mode=diagnostics_mode,
            automatic=seam_correction == SEAM_CORRECTION_AUTO,
        )
    duration_report = ""
    if exact_total_duration:
        target_frames = int(round(chunks * chunk_seconds * FPS))
        images, audio, duration_report = enforce_total_frames(
            images,
            audio,
            target_frames=target_frames,
            preserve_final_frame=last_frame is not None,
        )

    last_state = entry_to_state(entries[-1])
    parent_id = session.get("session_id") if session is not None else None
    settings = {
        "continuity": continuity,
        "audio_continuity": bool(audio_continuity),
        "exact_total_duration": bool(exact_total_duration),
        "prompt_mode": plan["mode"],
        "base_seed": int(base_seed),
        "reroll_nonce": int(reroll_nonce),
        "diagnostics_mode": diagnostics_mode,
        "initial_state_source": initial_state is not None,
    }
    new_session = make_session(
        chunks=entries,
        width=width,
        height=height,
        chunk_seconds=chunk_seconds,
        identity_hash=assets.identity_hash,
        model_fingerprint_value=current_model_fingerprint,
        parent_session_id=parent_id,
        reroll_from_chunk=int(reroll_from_chunk),
        settings=settings,
    )

    decoded_gib = (
        float(images.shape[0]) * float(width) * float(height) * 3.0 * 4.0 / (1024.0 ** 3)
    )
    report_lines = [
        f"H3 Continuum V2 {PACKAGE_VERSION}",
        prompt_plan_report(plan),
        f"Seam correction: {seam_correction}.",
        accelerator_summary(patched_model),
        "Execution: conditioning precomputed; call-local MODEL clone per chunk; decode deferred until sampling completed.",
        *reuse_notes,
    ]
    if diagnostics_mode != DIAGNOSTICS_OFF:
        report_lines.extend(
            [
                (
                    f"Decode RAM estimate: {decode_estimate_gib:.2f} GiB including transient headroom"
                    + (
                        f"; available at start {available_ram_gib:.2f} GiB."
                        if available_ram_gib is not None
                        else "."
                    )
                ),
                *sampling_reports,
                *decode_reports,
            ]
        )
    if duration_report:
        report_lines.append(duration_report)
    report_lines.extend(
        [
            session_summary(new_session),
            f"Output: {images.shape[0]} frames ({images.shape[0]/FPS:.3f}s), "
            f"audio samples={audio['waveform'].shape[-1]}, decoded tensor≈{decoded_gib:.2f} GiB.",
        ]
    )
    return images, audio, last_state, new_session, "\n".join(report_lines)
