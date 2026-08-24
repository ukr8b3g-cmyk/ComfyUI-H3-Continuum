"""Integrated N-chunk Continuum runtime.

V2 deliberately reuses the proven V1 continuation core. It changes execution
orchestration only: all text/image conditioning is prepared first, H3 sampling
runs for every chunk without intermediate VAE decoding, and decoding/assembly
happens after the sampling phase.
"""
from __future__ import annotations
import copy, hashlib, logging
from typing import Any
import torch
from ..compatibility import accelerator_summary, check_comfy_h3_runtime
from ..constants import (
    DIAGNOSTICS_FULL, DIAGNOSTICS_OFF, DIAGNOSTICS_OPTIONS, FPS,
    CONTINUUM_ACTUAL_PREFIX_STEPS, SEAM_CORRECTION_AUTO, SEAM_CORRECTION_OFF,
    SEAM_CORRECTION_OPTIONS, V2_CONTINUITY_AUTO, normalize_diagnostics_mode,
)
from ..continuation import POLICY_REPLACE, prepare_conditioning
from ..driving_audio import (
    attach_driving_audio,
    combine_driving_audio_identity,
    encode_driving_audio,
    slice_driving_audio_latent,
)
from ..model_patch import clone_model_for_chunk
from ..state import assert_context_unchanged, context_fingerprint, make_plan, select_context, validate_state
from ..temporal import (
    align_frame_count_up,
    audio_latent_t,
    context_slots,
    largest_context_capacity,
    make_extension_shape,
    video_latent_t,
)
from ..version import PACKAGE_VERSION
from .decoder import decode_sequence, decode_sequence_with_seam, enforce_total_frames
from .context_diagnostics import ContextDiagnosticsTracker
from .h3_builder import attach_keyframes, empty_h3_latent, encode_identity_latents, encode_prompt_conditioning, prepare_identity_assets
from .motion import choose_context_frames
from .prompts import prompt_plan_report, validate_prompt_plan
from .sampling import latent_from_cpu, latent_to_cpu, sample_chunk
from .seeds import derive_chunk_seed
from .session import (
    SessionValidationError, entry_to_state, make_chunk_entry, make_session, model_fingerprint,
    session_summary, validate_chunk_entry, validate_session,
)
LOG=logging.getLogger("h3_continuum_join")
class SequenceRuntimeError(RuntimeError): pass

def _record_context_diagnostics(*,tracker,reports,state,continuity,reused):
    if tracker is None: return
    try:
        context_frames,_,_=choose_context_frames(continuity,state)
        video_context,_,_=select_context(state,context_frames,include_audio=False)
        reports.append(tracker.observe(video_context,source_chunk=int(state["clip_index"]),context_frames=context_frames,reused=bool(reused)))
    except Exception as exc:
        reports.append(f"context diagnostics source chunk {state.get('clip_index','?')}: unavailable ({exc})")

def _check_decode_memory_budget(*,width,height,chunks,chunk_seconds):
    target_frames=max(1,int(round(chunks*chunk_seconds*FPS))); max_chunk_frames=max(5,int(round(chunk_seconds*FPS))+39)
    image_bytes=target_frames*width*height*3*4; transient_bytes=max_chunk_frames*width*height*3*4
    required_bytes=image_bytes+int(transient_bytes*1.5)+1*1024**3; estimate_gib=required_bytes/1024**3; available_gib=None
    try:
        import psutil
        available=int(psutil.virtual_memory().available); available_gib=available/1024**3
    except ImportError: pass
    return estimate_gib,available_gib

def _clone_entry_for_reuse(entry):
    entry=validate_chunk_entry(entry); result=dict(entry); result["plan"]=copy.deepcopy(entry["plan"]); result["reused"]=True; return result

def _preserved_prefix(*,session,prompt_hashes,chunks,reroll_from_chunk,width,height,chunk_seconds,identity_hash,last_frame_hash):
    if session is None: return [],[]
    notes=[]
    try: session=validate_session(session)
    except SessionValidationError as exc: return [],[f"saved session was ignored; generated a fresh run ({exc})"]
    if int(session["width"])!=int(width) or int(session["height"])!=int(height): return [],["saved session resolution differs; generated a fresh run"]
    if abs(float(session["chunk_seconds"])-float(chunk_seconds))>1e-6: return [],["saved session chunk duration differs; generated a fresh run"]
    if str(session.get("identity_hash","none"))!=str(identity_hash): return [],["saved session identity differs; generated a fresh run"]
    saved_last_frame_hash=(session.get("settings") or {}).get("last_frame_hash")
    if str(saved_last_frame_hash or "none")!=str(last_frame_hash or "none"): return [],["saved session Last Frame differs; generated a fresh run"]
    if reroll_from_chunk<0 or reroll_from_chunk>chunks: raise SessionValidationError("reroll_from_chunk must be 0 or a valid one-based chunk index")
    limit=min(len(session["chunks"]),chunks)
    if reroll_from_chunk>0: limit=min(limit,reroll_from_chunk-1)
    preserved=[]
    for index in range(limit):
        try: entry=validate_chunk_entry(session["chunks"][index])
        except SessionValidationError as exc:
            notes.append(f"session reuse stopped before chunk {index+1}: stored chunk was rejected ({exc})")
            break
        if entry["prompt_hash"]!=prompt_hashes[index]: notes.append(f"session reuse stopped before chunk {index+1}: prompt changed"); break
        preserved.append(_clone_entry_for_reuse(entry))
    if reroll_from_chunk==0 and len(preserved)==min(len(session["chunks"]),chunks):
        notes.append(f"resuming after accepted chunk {len(session['chunks'])}" if len(session["chunks"])<chunks else "all requested chunks reused from the session")
    elif reroll_from_chunk>0: notes.append(f"preserved chunks 1-{len(preserved)}; regenerated from chunk {reroll_from_chunk}")
    return preserved,notes

def _conditioning_cache_key(prompt, *, include_last, reference_assets=None):
    return (prompt, False if reference_assets is not None else bool(include_last))


def _conditioning_cache(*,clip,prompts,assets,final_has_last_frame,reference_assets=None,reference_audio_assets=None,timeline_video_assets=None):
    cache={}; final_index=len(prompts)-1
    for index,prompt in enumerate(prompts):
        include_last=bool(final_has_last_frame and index==final_index); key=_conditioning_cache_key(prompt,include_last=include_last,reference_assets=reference_assets)
        if key in cache: continue
        if reference_assets is not None:
            from ..reference import encode_reference_prompt
            cache[key]=encode_reference_prompt(clip,prompt,reference_assets,first_image=assets.first_image,last_image=assets.last_image,reference_audio_assets=reference_audio_assets,timeline_video_assets=timeline_video_assets)
        else:
            cache[key]=encode_prompt_conditioning(clip,prompt,first_image=assets.first_image,last_image=assets.last_image if include_last else None,reference_audio_assets=reference_audio_assets,timeline_video_assets=timeline_video_assets)
    return cache


FLF_STRATEGY = "terminal_merged_10s_seed_v2"
TERMINAL_SEED_POLICY = "physical_window_seed_v2"
TERMINAL_MERGE_CHUNK_SECONDS = 5.0
TERMINAL_MERGE_CONTEXT_FRAMES = 22
TERMINAL_PROMPT_POLICY_SHARED = "shared_prompt_v1"
TERMINAL_PROMPT_POLICY_TIMELINE = "paired_timeline_v1"


def _flf_contract_identity(base_hash: str) -> str:
    payload = f"{base_hash}|flf_strategy={FLF_STRATEGY}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _terminal_flf_merge_enabled(
    *,
    multi_chunk_flf: bool,
    chunks: int,
    chunk_seconds: float,
    prompt_hashes: list[str],
    timeline_video_source,
) -> bool:
    return bool(
        multi_chunk_flf
        and int(chunks) >= 2
        and abs(float(chunk_seconds) - TERMINAL_MERGE_CHUNK_SECONDS) <= 1e-6
        and timeline_video_source is None
        and len(prompt_hashes) >= 2
    )


def _terminal_pair_prompt(
    prompts: list[str],
    *,
    pair_start: int,
    chunk_seconds: float,
) -> tuple[str, str]:
    """Build one physical prompt without changing either logical prompt."""

    first = str(prompts[int(pair_start)])
    second = str(prompts[int(pair_start) + 1])
    if first == second:
        return first, TERMINAL_PROMPT_POLICY_SHARED
    split = f"{float(chunk_seconds):g}"
    stop = f"{float(chunk_seconds) * 2.0:g}"
    return (
        f"[0-{split}s]\n{first}\n\n[{split}-{stop}s]\n{second}",
        TERMINAL_PROMPT_POLICY_TIMELINE,
    )


def _atomic_terminal_prefix(
    preserved: list[dict[str, Any]],
    *,
    chunks: int,
    reroll_from_chunk: int,
) -> tuple[list[dict[str, Any]], bool]:
    """Never reuse only one logical half of a shared terminal sample."""
    pair_start = int(chunks) - 2
    reroll_hits_pair = int(reroll_from_chunk) in (int(chunks) - 1, int(chunks))
    partial_pair = pair_start < len(preserved) < int(chunks)
    if (reroll_hits_pair or partial_pair) and len(preserved) > pair_start:
        return preserved[:pair_start], True
    return preserved, False


def _terminal_sampling_plan(
    *,
    chunks: int,
    completed: int,
    merge_enabled: bool,
) -> tuple[tuple[int, ...], bool]:
    if completed >= int(chunks):
        return (), False
    if not merge_enabled:
        return tuple(range(completed, int(chunks))), False
    pair_start = int(chunks) - 2
    if completed > pair_start:
        raise SequenceRuntimeError("terminal merged pair cannot resume from only one logical half")
    return tuple(range(completed, pair_start)), True


def _terminal_physical_seed_plan(
    *,
    base_seed: int,
    physical_window_start_index: int,
    reroll_nonce: int,
) -> dict[str, Any]:
    """Return the one physical seed and the matching logical-entry metadata."""
    start_index = int(physical_window_start_index)
    nonce = int(reroll_nonce)
    if start_index < 0:
        raise ValueError("physical_window_start_index must be non-negative")
    if nonce < 0:
        raise ValueError("reroll_nonce must be non-negative")
    if start_index == 0 and nonce == 0:
        physical_seed = int(base_seed)
    else:
        physical_seed = derive_chunk_seed(base_seed, start_index, nonce)
    return {
        "physical_seed": physical_seed,
        "logical_entry_seeds": (physical_seed, physical_seed),
    }


def _terminal_execution_semantics(
    *,
    merge_enabled: bool,
    prompt_policy: str | None = None,
) -> dict[str, str] | None:
    if not merge_enabled:
        return None
    semantics = {
        "flf_execution": FLF_STRATEGY,
        "terminal_seed_policy": TERMINAL_SEED_POLICY,
    }
    if prompt_policy:
        semantics["terminal_prompt_policy"] = str(prompt_policy)
    return semantics


def _terminal_pair_contract(*, initial_pair: bool, chunk_seconds: float) -> dict[str, Any]:
    """Derive physical and logical AV ranges without fixed latent indices."""
    if abs(float(chunk_seconds) - TERMINAL_MERGE_CHUNK_SECONDS) > 1e-6:
        raise SequenceRuntimeError("terminal merged sampling currently requires 5-second logical chunks")
    initial_frames = align_frame_count_up(int(round(float(chunk_seconds) * FPS)))
    extension = make_extension_shape(
        TERMINAL_MERGE_CONTEXT_FRAMES,
        float(chunk_seconds),
    )
    if initial_pair:
        physical_frames = align_frame_count_up(int(round(2.0 * float(chunk_seconds) * FPS)))
        logical_frames = (initial_frames, extension.total_frames)
        logical_trims = (0, TERMINAL_MERGE_CONTEXT_FRAMES)
        first_video_stop = video_latent_t(initial_frames)
        first_audio_stop = audio_latent_t(initial_frames)
    else:
        physical_frames = make_extension_shape(
            TERMINAL_MERGE_CONTEXT_FRAMES,
            2.0 * float(chunk_seconds),
        ).total_frames
        logical_frames = (extension.total_frames, extension.total_frames)
        logical_trims = (
            TERMINAL_MERGE_CONTEXT_FRAMES,
            TERMINAL_MERGE_CONTEXT_FRAMES,
        )
        first_video_stop = video_latent_t(extension.total_frames)
        first_audio_stop = audio_latent_t(extension.total_frames)
    physical_video_stop = video_latent_t(physical_frames)
    physical_audio_stop = audio_latent_t(physical_frames)
    video_overlap = context_slots(TERMINAL_MERGE_CONTEXT_FRAMES)
    audio_overlap = audio_latent_t(TERMINAL_MERGE_CONTEXT_FRAMES)
    video_slices = (
        (0, first_video_stop),
        (first_video_stop - video_overlap, physical_video_stop),
    )
    audio_slices = (
        (0, first_audio_stop),
        (first_audio_stop - audio_overlap, physical_audio_stop),
    )
    for index in range(2):
        expected_video = video_latent_t(logical_frames[index])
        expected_audio = audio_latent_t(logical_frames[index])
        if video_slices[index][1] - video_slices[index][0] != expected_video:
            raise SequenceRuntimeError("derived terminal video split does not match its logical frame count")
        if audio_slices[index][1] - audio_slices[index][0] != expected_audio:
            raise SequenceRuntimeError("derived terminal audio split does not match its logical frame count")
    return {
        "initial_pair": bool(initial_pair),
        "physical_frames": int(physical_frames),
        "physical_context_frames": 0 if initial_pair else TERMINAL_MERGE_CONTEXT_FRAMES,
        "logical_frames": logical_frames,
        "logical_trims": logical_trims,
        "video_slices": video_slices,
        "audio_slices": audio_slices,
    }


def _split_terminal_merged_latents(
    video: torch.Tensor,
    audio: torch.Tensor,
    contract: dict[str, Any],
) -> tuple[tuple[torch.Tensor, torch.Tensor], tuple[torch.Tensor, torch.Tensor]]:
    expected_video = video_latent_t(int(contract["physical_frames"]))
    expected_audio = audio_latent_t(int(contract["physical_frames"]))
    if int(video.shape[2]) != expected_video or int(audio.shape[-1]) != expected_audio:
        raise SequenceRuntimeError(
            "terminal merged sampler output does not match the derived physical AV grid: "
            f"video T={video.shape[2]} (expected {expected_video}), "
            f"audio T={audio.shape[-1]} (expected {expected_audio})"
        )
    parts=[]
    for video_range,audio_range in zip(contract["video_slices"],contract["audio_slices"]):
        video_part=video[:,:,video_range[0]:video_range[1],...].contiguous()
        audio_part=audio[...,audio_range[0]:audio_range[1]].contiguous()
        parts.append((video_part,audio_part))
    return parts[0],parts[1]


def _attach_terminal_flf_keyframes(
    conditioning,
    *,
    video_context: torch.Tensor,
    context_frames: int,
    frame_count: int,
    last_latent: torch.Tensor,
):
    final_index = int(frame_count) - 1
    boundary_index = max(0, min(final_index - 1, int(context_frames) - 1))
    boundary_latent = video_context[:, :, -1:, ...].contiguous()
    excluded = {boundary_index, final_index}
    for _, metadata in conditioning:
        keyframes = [
            dict(item)
            for item in (metadata.get("minimax_keyframes") or [])
            if int(item.get("resolved_frame_index", -1)) not in excluded
        ]
        keyframes.extend(
            [
                {"resolved_frame_index": boundary_index, "latent": boundary_latent},
                {"resolved_frame_index": final_index, "latent": last_latent},
            ]
        )
        keyframes.sort(key=lambda item: int(item.get("resolved_frame_index", 0)))
        metadata["minimax_keyframes"] = keyframes
        metadata["minimax_frame_count"] = int(frame_count)
    return conditioning

def run_sequence(*,model:Any,clip:Any,video_vae:Any,audio_vae:Any,sampler:Any,sigmas:torch.Tensor,first_frame:torch.Tensor|None,last_frame:torch.Tensor|None,prompt_plan:dict[str,Any],width:int,height:int,continuity:str,base_seed:int,audio_continuity:bool,exact_total_duration:bool,diagnostics_mode:str,reroll_from_chunk:int,reroll_nonce:int,strict_compatibility:bool,debug:bool,seam_correction:str=SEAM_CORRECTION_OFF,enable_preview:bool=True,session:dict[str,Any]|None=None,initial_state:dict[str,Any]|None=None,latent_only:bool=False,reference_assets=None,reference_audio_source=None,reference_audio_vae=None,driving_audio_source=None,driving_audio_vae=None,reference_video_source=None,timeline_video_source=None,capture_refine_context:bool=False,memory_attribution:bool=False,_memory_attribution_collector:Any=None):
    from ..conditioning import detect_conditioning_mode, conditioning_display_label
    from ..run_storage import get_active_run_storage
    storage_controller=get_active_run_storage()
    capture_refine_context=bool(capture_refine_context and latent_only)
    memory_attribution=bool(memory_attribution and capture_refine_context)
    memory_collector=None
    refine_groups=[]
    make_refine_group=make_refine_context=None
    if bool(capture_refine_context):
        from ..v3.refine_context import make_refine_context, make_refine_group
    diagnostics_mode=normalize_diagnostics_mode(diagnostics_mode); memory_collector=_memory_attribution_collector if memory_attribution and diagnostics_mode==DIAGNOSTICS_FULL else None; capture_memory=None
    if memory_collector is not None:
        from ..v3.memory_attribution import capture_attribution_fail_soft
        capture_memory=capture_attribution_fail_soft
    plan=validate_prompt_plan(prompt_plan); chunks=int(plan["chunks"]); chunk_seconds=float(plan["chunk_seconds"]); prompts=list(plan["prompts"]); prompt_hashes=list(plan["hashes"]); width,height=int(width),int(height)
    # Legacy workflow input only. Runtime compatibility is advisory in V3.4.
    strict_compatibility=False
    if width<=0 or height<=0 or width%32 or height%32: raise SequenceRuntimeError("width and height must be positive multiples of 32")
    if session is not None and initial_state is not None:
        LOG.warning("Both session and initial_state were supplied; using the session and ignoring initial_state")
        initial_state=None
    if diagnostics_mode not in DIAGNOSTICS_OPTIONS: raise SequenceRuntimeError(f"unknown diagnostics mode: {diagnostics_mode!r}")
    if seam_correction not in SEAM_CORRECTION_OPTIONS: raise SequenceRuntimeError(f"unknown seam correction mode: {seam_correction!r}")
    if not 0<=int(reroll_from_chunk)<=chunks: raise SequenceRuntimeError("reroll_from_chunk must be 0 or a valid one-based chunk index")
    if initial_state is not None and int(reroll_from_chunk) not in (0,1): raise SequenceRuntimeError("with initial_state, reroll_from_chunk can only be 0 or 1")
    try: conditioning_mode=detect_conditioning_mode(first_frame=first_frame,last_frame=last_frame,reference_assets=reference_assets)
    except ValueError as exc: raise SequenceRuntimeError(str(exc)) from exc
    conditioning_display=conditioning_display_label(has_first=first_frame is not None,has_last=last_frame is not None,has_reference=reference_assets is not None)
    reference_warning=""
    if reference_assets is not None:
        from ..reference import validate_reference_prompts
        reference_warning=validate_reference_prompts(prompts,reference_assets.count,picture_offset=int(first_frame is not None)+int(last_frame is not None))
    from ..reference_audio import (
        combine_reference_audio_identity,
        validate_reference_audio_prompts,
    )
    reference_audio_warning=validate_reference_audio_prompts(prompts,reference_audio_source)
    from ..reference_video import (
        combine_reference_video_identity,
        validate_reference_video_prompts,
    )
    reference_video_warning=validate_reference_video_prompts(prompts,reference_video_source)
    from ..timeline_video import (
        combine_timeline_video_identity,
        validate_timeline_video_prompts,
    )
    timeline_video_warning=validate_timeline_video_prompts(prompts,timeline_video_source)
    decode_estimate_gib=0.0; available_ram_gib=None
    if not latent_only: decode_estimate_gib,available_ram_gib=_check_decode_memory_budget(width=width,height=height,chunks=chunks,chunk_seconds=chunk_seconds)
    issues=check_comfy_h3_runtime()
    assets=prepare_identity_assets(video_vae,width=width,height=height,first_frame=first_frame,last_frame=last_frame,encode_latents=False)
    multi_chunk_flf=bool(chunks>=2 and first_frame is not None and last_frame is not None)
    terminal_merge_enabled=_terminal_flf_merge_enabled(multi_chunk_flf=multi_chunk_flf,chunks=chunks,chunk_seconds=chunk_seconds,prompt_hashes=prompt_hashes,timeline_video_source=timeline_video_source)
    terminal_prompt=None
    terminal_prompt_policy=None
    if terminal_merge_enabled:
        terminal_prompt,terminal_prompt_policy=_terminal_pair_prompt(prompts,pair_start=chunks-2,chunk_seconds=chunk_seconds)
    from ..reference import combine_hybrid_visual_identity
    visual_identity_hash=combine_hybrid_visual_identity(keyframe_identity_hash=assets.identity_hash,reference_assets=reference_assets,has_first=first_frame is not None,has_last=last_frame is not None)
    sequence_identity_hash=combine_reference_audio_identity(visual_identity_hash,reference_audio_source)
    sequence_identity_hash=combine_driving_audio_identity(sequence_identity_hash,driving_audio_source)
    sequence_identity_hash=combine_reference_video_identity(sequence_identity_hash,reference_video_source)
    sequence_identity_hash=combine_timeline_video_identity(sequence_identity_hash,timeline_video_source)
    if multi_chunk_flf:
        sequence_identity_hash=_flf_contract_identity(sequence_identity_hash)
    current_model_fingerprint=model_fingerprint(model,extra_wrapper_keys=("h3_continuum_join.apply_model.v1",))
    if storage_controller is not None:
        stored_session=storage_controller.prepare(model=model,model_fingerprint_value=current_model_fingerprint,clip=clip,video_vae=video_vae,sampler=sampler,sigmas=sigmas,prompt_plan=plan,width=width,height=height,chunk_seconds=chunk_seconds,continuity=continuity,audio_continuity=audio_continuity,base_seed=base_seed,reroll_from_chunk=reroll_from_chunk,reroll_nonce=reroll_nonce,first_frame_hash=assets.first_frame_hash,last_frame_hash=assets.last_frame_hash,identity_hash=sequence_identity_hash,strict_compatibility=strict_compatibility,existing_session=session,reference_contract=reference_assets.contract if reference_assets is not None else None,conditioning_mode=conditioning_mode,reference_audio_contract=reference_audio_source.contract if reference_audio_source is not None else None,reference_audio_vae=reference_audio_vae,driving_audio_contract=driving_audio_source.contract if driving_audio_source is not None else None,driving_audio_vae=driving_audio_vae,reference_video_contract=reference_video_source.contract if reference_video_source is not None else None,timeline_video_contract=timeline_video_source.contract if timeline_video_source is not None else None,execution_semantics=_terminal_execution_semantics(merge_enabled=terminal_merge_enabled,prompt_policy=terminal_prompt_policy))
        reroll_nonce=storage_controller.effective_reroll_nonce
        if stored_session is not None: session=stored_session
    accelerators=accelerator_summary(model)
    if "Continuum APPLY_MODEL wrapper installed" not in accelerators: accelerators+="; Continuum APPLY_MODEL wrapper installed"
    effective_reroll_from_chunk=0 if storage_controller is not None and session is not None and bool((session.get("settings") or {}).get("run_storage_validated_prefix")) else int(reroll_from_chunk)
    preserved,reuse_notes=_preserved_prefix(session=session,prompt_hashes=prompt_hashes,chunks=chunks,reroll_from_chunk=effective_reroll_from_chunk,width=width,height=height,chunk_seconds=chunk_seconds,identity_hash=sequence_identity_hash,last_frame_hash=assets.last_frame_hash)
    if multi_chunk_flf and session is not None:
        saved_strategy=str((session.get("settings") or {}).get("flf_execution", ""))
        if saved_strategy!=FLF_STRATEGY:
            preserved=[]
            reuse_notes.append("FLF chunk contract changed; regenerated the requested FLF sequence.")
    if terminal_merge_enabled:
        preserved,atomic_reset=_atomic_terminal_prefix(preserved,chunks=chunks,reroll_from_chunk=int(reroll_from_chunk))
        if atomic_reset:
            reuse_notes.append("terminal merged pair is atomic; regenerated both final logical chunks")
    if multi_chunk_flf:
        if terminal_merge_enabled:
            reuse_notes.insert(0,"FLF execution: terminal merged 10s seed v2; the final two 5-second logical chunks share one physical sample and are split back into normal chunk entries.")
        else:
            reuse_notes.insert(0,"FLF execution: terminal merge unavailable for this request; retained one sampling pass per logical chunk.")
    if reference_assets is not None:
        reuse_notes.insert(0,f"Reference conditioning: {reference_assets.count} image(s), size={reference_assets.size_mode}; persistent across all chunks.")
        if reference_warning: reuse_notes.append(reference_warning)
    if reference_audio_source is not None:
        reuse_notes.insert(0,"Reference Audio 1 conditioning: persistent across all chunks.")
        if reference_audio_warning: reuse_notes.append(reference_audio_warning)
    if driving_audio_source is not None:
        reuse_notes.insert(0,"Driving Audio: absolute-time guide slices enabled; original audio is preserved for final output.")
    if reference_video_source is not None:
        reuse_notes.insert(0,f"Video Reference conditioning: persistent across all chunks, 24 fps, resolved={reference_video_source.target_width}x{reference_video_source.target_height}, frames={reference_video_source.frame_count}.")
        if reference_video_warning: reuse_notes.append(reference_video_warning)
    if timeline_video_source is not None:
        reuse_notes.insert(0,f"Timeline Video conditioning: chunk-local slices, size={timeline_video_source.size_mode}, resolved={timeline_video_source.target_width}x{timeline_video_source.target_height}.")
        if timeline_video_warning: reuse_notes.append(timeline_video_warning)
    if session is not None:
        old_fingerprint=str(session.get("model_fingerprint",""))
        if old_fingerprint and old_fingerprint!=current_model_fingerprint: reuse_notes.append("model/accelerator fingerprint differs from the saved session; accepted chunks were kept")
    cache={}
    if len(preserved)<chunks:
        assets=encode_identity_latents(video_vae,assets)
        if reference_assets is not None:
            from ..reference import encode_reference_latents
            reference_assets=encode_reference_latents(video_vae,reference_assets)
        reference_audio_assets=None
        if reference_audio_source is not None:
            from ..reference_audio import encode_reference_audio
            reference_audio_assets=encode_reference_audio(reference_audio_vae,reference_audio_source)
        driving_audio_assets=encode_driving_audio(driving_audio_source,driving_audio_vae)
        reference_video_assets=None
        if reference_video_source is not None:
            from ..reference_video import encode_reference_video
            reference_video_assets=encode_reference_video(video_vae,reference_video_source)
        if timeline_video_source is None:
            cache=_conditioning_cache(clip=clip,prompts=prompts,assets=assets,final_has_last_frame=last_frame is not None,reference_assets=reference_assets,reference_audio_assets=reference_audio_assets,timeline_video_assets=reference_video_assets)
            if terminal_merge_enabled and terminal_prompt is not None:
                terminal_key=_conditioning_cache_key(terminal_prompt,include_last=True,reference_assets=reference_assets)
                if terminal_key not in cache:
                    cache.update(_conditioning_cache(clip=clip,prompts=[terminal_prompt],assets=assets,final_has_last_frame=True,reference_assets=reference_assets,reference_audio_assets=reference_audio_assets,timeline_video_assets=reference_video_assets))
    entries=preserved[:]; previous_state=None
    if entries:
        try: previous_state=entry_to_state(entries[-1])
        except (SessionValidationError, ValueError) as exc:
            reuse_notes.append(f"saved continuation state was rejected; generated a fresh run ({exc})")
            entries=[]; previous_state=None
    elif initial_state is not None:
        try:
            candidate=validate_state(initial_state)
            if int(candidate["width"])!=width or int(candidate["height"])!=height:
                reuse_notes.append("initial_state resolution differs; generated a fresh run")
            else: previous_state=candidate
        except ValueError as exc:
            reuse_notes.append(f"initial_state was rejected; generated a fresh run ({exc})")
    initial_frame_count=align_frame_count_up(int(round(chunk_seconds*FPS))); retained_frames=sum(int(entry["plan"]["net_frames"]) for entry in entries); sampling_reports=[]
    context_diagnostics=ContextDiagnosticsTracker() if bool(debug) else None
    if context_diagnostics is not None:
        if entries:
            for reused_entry in entries:
                _record_context_diagnostics(tracker=context_diagnostics,reports=sampling_reports,state=entry_to_state(reused_entry),continuity=continuity,reused=True)
        elif previous_state is not None:
            _record_context_diagnostics(tracker=context_diagnostics,reports=sampling_reports,state=previous_state,continuity=continuity,reused=True)
    normal_indices,terminal_merge_pending=_terminal_sampling_plan(chunks=chunks,completed=len(entries),merge_enabled=terminal_merge_enabled)
    for sequence_index in normal_indices:
        prompt=prompts[sequence_index]; prompt_hash_value=prompt_hashes[sequence_index]; is_final=sequence_index==chunks-1; effective_reroll_nonce=int(reroll_nonce) if int(reroll_from_chunk)>0 and sequence_index+1>=int(reroll_from_chunk) else 0; seed=derive_chunk_seed(base_seed,sequence_index,effective_reroll_nonce); motion_score=0.0; video_context=None; audio_context=None; context_before=None
        timeline_video_assets=reference_video_assets
        chunk_cache=cache
        if timeline_video_source is not None:
            from ..timeline_video import encode_timeline_video_chunk
            timeline_video_assets=encode_timeline_video_chunk(video_vae,timeline_video_source,sequence_index)
        chunk_assets=assets
        if timeline_video_source is not None:
            chunk_cache=_conditioning_cache(clip=clip,prompts=[prompt],assets=assets,final_has_last_frame=bool(last_frame is not None and is_final),reference_assets=reference_assets,reference_audio_assets=reference_audio_assets,timeline_video_assets=timeline_video_assets)
        if previous_state is None:
            include_chunk_last=bool(last_frame is not None and is_final)
            conditioning_key=_conditioning_cache_key(prompt,include_last=include_chunk_last,reference_assets=reference_assets)
            total_frames=initial_frame_count; latent=empty_h3_latent(width,height,total_frames); conditioning=attach_keyframes(chunk_cache[conditioning_key],frame_count=total_frames,first_latent=chunk_assets.first_latent,last_latent=chunk_assets.last_latent if include_chunk_last else None); clip_index=1; context_frames=0
            chunk_plan=make_plan(continuation=False,clip_index=clip_index,total_frames=total_frames,trim_frames=0,width=width,height=height,context_frames=5,state_capacity_frames=largest_context_capacity(total_frames),requested_extend_seconds=chunk_seconds,debug=debug); reason="initial clip"
        else:
            context_frames,motion_score,reason=choose_context_frames(continuity,previous_state); desired_cumulative=int(round((sequence_index+1)*chunk_seconds*FPS)); requested_new_frames=max(1,desired_cumulative-retained_frames); shape=make_extension_shape(context_frames,requested_new_frames/FPS); latent=empty_h3_latent(width,height,shape.total_frames)
            include_chunk_last=bool(last_frame is not None and is_final)
            conditioning_key=_conditioning_cache_key(prompt,include_last=include_chunk_last,reference_assets=reference_assets)
            base_conditioning=attach_keyframes(chunk_cache[conditioning_key],frame_count=shape.total_frames,first_latent=chunk_assets.first_latent,last_latent=chunk_assets.last_latent if include_chunk_last else None)
            video_context,audio_context,grid_offset=select_context(previous_state,context_frames,include_audio=bool(audio_continuity)); context_before=context_fingerprint(video_context,audio_context)
            conditioning=prepare_conditioning(base_conditioning,video_context=video_context,audio_context=audio_context,audio_grid_offset=grid_offset,context_frames=context_frames,new_frame_count=shape.total_frames,first_frame_policy=POLICY_REPLACE,preserve_last_frame=True)
            clip_index=int(previous_state["clip_index"])+1; chunk_plan=make_plan(continuation=True,clip_index=clip_index,total_frames=shape.total_frames,trim_frames=context_frames,width=width,height=height,context_frames=context_frames,state_capacity_frames=largest_context_capacity(shape.net_new_frames),requested_extend_seconds=chunk_seconds,debug=debug)
        driving_audio_latent=slice_driving_audio_latent(driving_audio_assets,cumulative_retained_before=retained_frames,total_frames=int(chunk_plan["total_frames"]),trim_frames=int(chunk_plan["trim_frames"]),fps=FPS)
        conditioning=attach_driving_audio(conditioning,driving_audio_latent)
        chunk_model=clone_model_for_chunk(model,strict=bool(strict_compatibility),debug=bool(debug),chunk_index=clip_index,context_frames=context_frames if previous_state is not None else None)
        if bool(capture_refine_context):
            from ..state import extract_av_streams
            source_video,_=extract_av_streams(latent)
            refine_groups.append(make_refine_group(
                conditioning=conditioning,
                group_id=len(refine_groups),
                logical_chunks=(sequence_index+1,),
                physical_frames=int(chunk_plan["total_frames"]),
                prompt_policy="single",
                physical_prompt=prompt,
                source_video_shape=tuple(int(value) for value in source_video.shape),
                physical_clip_index=int(clip_index),
                context_frames=int(context_frames),
                first_image=assets.first_image,
                last_image=assets.last_image if include_chunk_last else None,
            ))
            del source_video,_
        if memory_collector is not None:
            capture_memory(memory_collector, "capture_group",
                physical_group=sequence_index+1,
                logical_chunks=(sequence_index+1,),
                stage="before sampling",
                retained_entries=entries,
                observed_latent=latent,
                retained_refine_context=refine_groups,
            )
        sampled=sample_chunk(model=chunk_model,conditioning=conditioning,latent=latent,sampler=sampler,sigmas=sigmas,seed=seed,enable_preview=bool(enable_preview))
        if memory_collector is not None:
            capture_memory(memory_collector, "capture_group",
                physical_group=sequence_index+1,
                logical_chunks=(sequence_index+1,),
                stage="after sampling",
                retained_entries=entries,
                observed_latent=sampled,
                retained_refine_context=refine_groups,
            )
        if context_before is not None and video_context is not None: assert_context_unchanged(video_context,audio_context,context_before)
        entry=make_chunk_entry(latent=sampled,plan=chunk_plan,prompt=prompt,prompt_hash=prompt_hash_value,seed=seed,context_frames=context_frames,motion_score=motion_score,reused=False); previous_state=entry_to_state(entry); entries.append(entry)
        _record_context_diagnostics(tracker=context_diagnostics,reports=sampling_reports,state=previous_state,continuity=continuity,reused=False)
        if storage_controller is not None: storage_controller.commit_chunk(entry, position=sequence_index)
        retained_frames+=int(chunk_plan["net_frames"])
        sampling_reports.append(f"chunk {sequence_index+1}/{chunks}: seed={seed}, frames={chunk_plan['total_frames']}, trim={chunk_plan['trim_frames']}, retained_total={retained_frames}, context={context_frames} ({reason}), motion={motion_score:.6f}, "+(f"interop=emitted actual_prefix={CONTINUUM_ACTUAL_PREFIX_STEPS} consumer=not_observable" if context_before is not None else "interop=not_emitted"))
        del sampled,latent,conditioning,chunk_model,chunk_cache
        if timeline_video_source is not None and timeline_video_assets is not None: del timeline_video_assets
        if memory_collector is not None:
            capture_memory(memory_collector, "capture_group",
                physical_group=sequence_index+1,
                logical_chunks=(sequence_index+1,),
                stage="after CPU commit",
                retained_entries=entries,
                retained_refine_context=refine_groups,
            )
    if terminal_merge_pending:
        pair_start=chunks-2
        if len(entries)!=pair_start:
            raise SequenceRuntimeError(f"terminal merged pair expected {pair_start} completed chunks, got {len(entries)}")
        prompt=terminal_prompt
        seed_nonce=int(reroll_nonce) if int(reroll_from_chunk)>0 else 0
        terminal_seed_plan=_terminal_physical_seed_plan(base_seed=base_seed,physical_window_start_index=pair_start,reroll_nonce=seed_nonce)
        physical_seed=int(terminal_seed_plan["physical_seed"])
        initial_pair=previous_state is None
        contract=_terminal_pair_contract(initial_pair=initial_pair,chunk_seconds=chunk_seconds)
        physical_frames=int(contract["physical_frames"])
        physical_context_frames=int(contract["physical_context_frames"])
        latent=empty_h3_latent(width,height,physical_frames)
        conditioning_key=_conditioning_cache_key(prompt,include_last=True,reference_assets=reference_assets)
        base_conditioning=attach_keyframes(cache[conditioning_key],frame_count=physical_frames,first_latent=assets.first_latent,last_latent=assets.last_latent)
        video_context=None; audio_context=None; context_before=None; motion_score=0.0
        if initial_pair:
            conditioning=base_conditioning
            physical_clip_index=1
            reason="terminal merged initial 10-second sample"
        else:
            selected_context,motion_score,selected_reason=choose_context_frames(continuity,previous_state)
            video_context,audio_context,grid_offset=select_context(previous_state,TERMINAL_MERGE_CONTEXT_FRAMES,include_audio=bool(audio_continuity))
            context_before=context_fingerprint(video_context,audio_context)
            conditioning=prepare_conditioning(base_conditioning,video_context=video_context,audio_context=audio_context,audio_grid_offset=grid_offset,context_frames=TERMINAL_MERGE_CONTEXT_FRAMES,new_frame_count=physical_frames,first_frame_policy=POLICY_REPLACE,preserve_last_frame=True)
            physical_clip_index=int(previous_state["clip_index"])+1
            reason=f"terminal merged 10-second sample with 22-frame context; continuity selection was {selected_context} ({selected_reason})"
        driving_audio_latent=slice_driving_audio_latent(driving_audio_assets,cumulative_retained_before=retained_frames,total_frames=physical_frames,trim_frames=physical_context_frames,fps=FPS)
        conditioning=attach_driving_audio(conditioning,driving_audio_latent)
        chunk_model=clone_model_for_chunk(model,strict=bool(strict_compatibility),debug=bool(debug),chunk_index=physical_clip_index,context_frames=physical_context_frames if not initial_pair else None)
        if bool(capture_refine_context):
            from ..state import extract_av_streams
            source_video,_=extract_av_streams(latent)
            refine_groups.append(make_refine_group(
                conditioning=conditioning,
                group_id=len(refine_groups),
                logical_chunks=(pair_start+1,chunks),
                physical_frames=physical_frames,
                prompt_policy=str(terminal_prompt_policy),
                physical_prompt=str(prompt),
                source_video_shape=tuple(int(value) for value in source_video.shape),
                physical_clip_index=int(physical_clip_index),
                context_frames=int(physical_context_frames),
                first_image=assets.first_image,
                last_image=assets.last_image,
            ))
            del source_video,_
        terminal_physical_group=pair_start+1
        terminal_logical_chunks=(pair_start+1,chunks)
        if memory_collector is not None:
            capture_memory(memory_collector, "capture_group",
                physical_group=terminal_physical_group,
                logical_chunks=terminal_logical_chunks,
                stage="before sampling",
                retained_entries=entries,
                observed_latent=latent,
                retained_refine_context=refine_groups,
            )
        sampled=sample_chunk(model=chunk_model,conditioning=conditioning,latent=latent,sampler=sampler,sigmas=sigmas,seed=physical_seed,enable_preview=bool(enable_preview))
        if memory_collector is not None:
            capture_memory(memory_collector, "capture_group",
                physical_group=terminal_physical_group,
                logical_chunks=terminal_logical_chunks,
                stage="after sampling",
                retained_entries=entries,
                observed_latent=sampled,
                retained_refine_context=refine_groups,
            )
        if context_before is not None and video_context is not None:
            assert_context_unchanged(video_context,audio_context,context_before)
        sampled_video,sampled_audio=latent_to_cpu(sampled)
        logical_parts=_split_terminal_merged_latents(sampled_video,sampled_audio,contract)
        sampling_reports.append(f"terminal physical sample: terminal_pair={pair_start+1}-{chunks}, physical_seed={physical_seed}, physical_frames={physical_frames}, sampling_passes=1, shared_physical_sample=true, terminal_prompt_policy={terminal_prompt_policy}, trim={physical_context_frames}, reason={reason}")
        for offset,(video_part,audio_part) in enumerate(logical_parts):
            sequence_index=pair_start+offset
            total_frames=int(contract["logical_frames"][offset])
            trim_frames=int(contract["logical_trims"][offset])
            continuation=bool(trim_frames)
            clip_index=physical_clip_index+offset
            context_frames=trim_frames if continuation else 5
            chunk_plan=make_plan(continuation=continuation,clip_index=clip_index,total_frames=total_frames,trim_frames=trim_frames,width=width,height=height,context_frames=context_frames,state_capacity_frames=largest_context_capacity(total_frames-trim_frames),requested_extend_seconds=chunk_seconds,debug=debug)
            logical_latent=latent_from_cpu(video_part,audio_part)
            logical_seed=int(terminal_seed_plan["logical_entry_seeds"][offset])
            entry=make_chunk_entry(latent=logical_latent,plan=chunk_plan,prompt=prompts[sequence_index],prompt_hash=prompt_hashes[sequence_index],seed=logical_seed,context_frames=trim_frames,motion_score=motion_score,reused=False)
            entries.append(entry)
            previous_state=entry_to_state(entry)
            _record_context_diagnostics(tracker=context_diagnostics,reports=sampling_reports,state=previous_state,continuity=continuity,reused=False)
            if storage_controller is not None:
                storage_controller.commit_chunk(entry,position=sequence_index)
            retained_frames+=int(chunk_plan["net_frames"])
            sampling_reports.append(f"chunk {sequence_index+1}/{chunks}: seed={logical_seed}, frames={total_frames}, trim={trim_frames}, retained_total={retained_frames}, context={trim_frames}, shared_physical_sample=terminal_10s_seed_v2")
            del logical_latent
        del sampled,sampled_video,sampled_audio,logical_parts,latent,conditioning,chunk_model
        del video_part,audio_part
        if memory_collector is not None:
            capture_memory(memory_collector, "capture_group",
                physical_group=terminal_physical_group,
                logical_chunks=terminal_logical_chunks,
                stage="after CPU commit",
                retained_entries=entries,
                retained_refine_context=refine_groups,
            )
    if len(entries)!=chunks: raise SequenceRuntimeError(f"internal sequence length mismatch: expected {chunks}, got {len(entries)}")
    if latent_only:
        last_state=entry_to_state(entries[-1]); parent_id=session.get("session_id") if session is not None else None
        settings={"continuity":continuity,"audio_continuity":bool(audio_continuity),"exact_total_duration":False,"prompt_mode":plan["mode"],"conditioning_mode":conditioning_mode,"base_seed":int(base_seed),"reroll_nonce":int(reroll_nonce),"diagnostics_mode":diagnostics_mode,"initial_state_source":initial_state is not None,"latent_first":True,"first_frame_hash":assets.first_frame_hash,"last_frame_hash":assets.last_frame_hash,"reference_contract":reference_assets.contract if reference_assets is not None else None}
        if multi_chunk_flf: settings["flf_execution"]=FLF_STRATEGY
        if reference_audio_source is not None: settings["reference_audio_contract"]=reference_audio_source.contract
        if driving_audio_source is not None: settings["driving_audio_contract"]=driving_audio_source.contract
        if reference_video_source is not None: settings["reference_video_contract"]=reference_video_source.contract
        if timeline_video_source is not None: settings["timeline_video_contract"]=timeline_video_source.contract
        new_session=make_session(chunks=entries,width=width,height=height,chunk_seconds=chunk_seconds,identity_hash=sequence_identity_hash,model_fingerprint_value=current_model_fingerprint,parent_session_id=parent_id,reroll_from_chunk=int(reroll_from_chunk),settings=settings)
        report_lines=[f"H3 Continuum V3 {PACKAGE_VERSION}",f"Conditioning mode: {conditioning_display}.",prompt_plan_report(plan),"Decode: external ComfyUI Core VAE nodes; full raw AV chunks retained.",accelerators,"Execution: conditioning precomputed; single call-local MODEL clone per chunk; no internal VAE decode.",*reuse_notes]
        if diagnostics_mode!=DIAGNOSTICS_OFF: report_lines.extend(sampling_reports)
        report_lines.extend([session_summary(new_session),f"Output: {len(entries)} raw AV latent chunk(s); connect Core VAE Decode nodes, then H3 Continuum Assemble V3."])
        outputs=(entries,last_state,new_session,"\n".join(report_lines))
        if bool(capture_refine_context):
            expected_groups=chunks-(1 if terminal_merge_enabled else 0)
            complete=len(refine_groups)==expected_groups
            notes=[]
            if not complete:
                notes.append(
                    "Refine context is incomplete because accepted session/Run Storage "
                    f"entries were reused; captured {len(refine_groups)} of "
                    f"{expected_groups} physical sampling groups."
                )
            raw_refine_context=make_refine_context(
                refine_groups,
                source_width=width,
                source_height=height,
                conditioning_mode=conditioning_mode,
                complete=complete,
                notes=notes,
            )
            return (*outputs,raw_refine_context)
        return outputs
    if seam_correction==SEAM_CORRECTION_OFF: images,audio,decode_reports=decode_sequence(entries=entries,video_vae=video_vae,audio_vae=audio_vae,diagnostics_full=diagnostics_mode==DIAGNOSTICS_FULL)
    else: images,audio,decode_reports=decode_sequence_with_seam(entries=entries,video_vae=video_vae,audio_vae=audio_vae,diagnostics_mode=diagnostics_mode,automatic=seam_correction==SEAM_CORRECTION_AUTO)
    duration_report=""
    if exact_total_duration:
        target_frames=int(round(chunks*chunk_seconds*FPS)); images,audio,duration_report=enforce_total_frames(images,audio,target_frames=target_frames,preserve_final_frame=last_frame is not None)
    last_state=entry_to_state(entries[-1]); parent_id=session.get("session_id") if session is not None else None
    settings={"continuity":continuity,"audio_continuity":bool(audio_continuity),"exact_total_duration":bool(exact_total_duration),"prompt_mode":plan["mode"],"base_seed":int(base_seed),"reroll_nonce":int(reroll_nonce),"diagnostics_mode":diagnostics_mode,"initial_state_source":initial_state is not None,"first_frame_hash":assets.first_frame_hash,"last_frame_hash":assets.last_frame_hash,"reference_contract":reference_assets.contract if reference_assets is not None else None}
    if multi_chunk_flf: settings["flf_execution"]=FLF_STRATEGY
    new_session=make_session(chunks=entries,width=width,height=height,chunk_seconds=chunk_seconds,identity_hash=sequence_identity_hash,model_fingerprint_value=current_model_fingerprint,parent_session_id=parent_id,reroll_from_chunk=int(reroll_from_chunk),settings=settings)
    decoded_gib=float(images.shape[0])*float(width)*float(height)*3.0*4.0/(1024.0**3)
    report_lines=[f"H3 Continuum V2 {PACKAGE_VERSION}",prompt_plan_report(plan),f"Seam correction: {seam_correction}.",accelerators,"Execution: conditioning precomputed; single call-local MODEL clone per chunk; decode deferred until sampling completed.",*reuse_notes]
    if diagnostics_mode!=DIAGNOSTICS_OFF: report_lines.extend([f"Decode RAM estimate: {decode_estimate_gib:.2f} GiB including transient headroom"+(f"; available at start {available_ram_gib:.2f} GiB." if available_ram_gib is not None else "."),*sampling_reports,*decode_reports])
    if duration_report: report_lines.append(duration_report)
    report_lines.extend([session_summary(new_session),f"Output: {images.shape[0]} frames ({images.shape[0]/FPS:.3f}s), audio samples={audio['waveform'].shape[-1]}, decoded tensor≈{decoded_gib:.2f} GiB."])
    return images,audio,last_state,new_session,"\n".join(report_lines)
# V3.0.1 hardening integration: Detailed Report only; generation semantics unchanged.
from ..hardening import run_sequence_with_hardening as _run_sequence_with_hardening

_run_sequence_v300 = run_sequence


def run_sequence(*args, **kwargs):
    return _run_sequence_with_hardening(_run_sequence_v300, args, kwargs)
