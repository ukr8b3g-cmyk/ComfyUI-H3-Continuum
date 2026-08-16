"""Integrated N-chunk Continuum runtime.

V2 deliberately reuses the proven V1 continuation core. It changes execution
orchestration only: all text/image conditioning is prepared first, H3 sampling
runs for every chunk without intermediate VAE decoding, and decoding/assembly
happens after the sampling phase.
"""
from __future__ import annotations
import copy, logging
from typing import Any
import torch
from ..compatibility import accelerator_summary, check_comfy_h3_runtime
from ..constants import (
    DIAGNOSTICS_FULL, DIAGNOSTICS_OFF, DIAGNOSTICS_OPTIONS, FPS,
    CONTINUUM_ACTUAL_PREFIX_STEPS, SEAM_CORRECTION_AUTO, SEAM_CORRECTION_OFF,
    SEAM_CORRECTION_OPTIONS, V2_CONTINUITY_AUTO, normalize_diagnostics_mode,
)
from ..continuation import POLICY_REPLACE, prepare_conditioning
from ..model_patch import clone_model_for_chunk
from ..state import assert_context_unchanged, context_fingerprint, make_plan, select_context, validate_state
from ..temporal import align_frame_count_up, largest_context_capacity, make_extension_shape
from ..version import PACKAGE_VERSION
from .decoder import decode_sequence, decode_sequence_with_seam, enforce_total_frames
from .h3_builder import attach_keyframes, empty_h3_latent, encode_identity_latents, encode_prompt_conditioning, prepare_identity_assets
from .motion import choose_context_frames
from .prompts import prompt_plan_report, validate_prompt_plan
from .sampling import sample_chunk
from .seeds import derive_chunk_seed
from .session import (
    SessionValidationError, entry_to_state, make_chunk_entry, make_session, model_fingerprint,
    session_summary, validate_chunk_entry, validate_session,
)
LOG=logging.getLogger("h3_continuum_join")
class SequenceRuntimeError(RuntimeError): pass

def _check_decode_memory_budget(*,width,height,chunks,chunk_seconds):
    target_frames=max(1,int(round(chunks*chunk_seconds*FPS))); max_chunk_frames=max(5,int(round(chunk_seconds*FPS))+39)
    image_bytes=target_frames*width*height*3*4; transient_bytes=max_chunk_frames*width*height*3*4
    required_bytes=image_bytes+int(transient_bytes*1.5)+1*1024**3; estimate_gib=required_bytes/1024**3; available_gib=None
    try:
        import psutil
        available=int(psutil.virtual_memory().available); available_gib=available/1024**3
        if required_bytes>int(available*0.75):
            raise SequenceRuntimeError(f"estimated decoded output requires about {estimate_gib:.1f} GiB including one-chunk headroom, but only {available_gib:.1f} GiB RAM is currently available. Reduce chunks, chunk_seconds, or resolution before sampling.")
    except ImportError: pass
    return estimate_gib,available_gib

def _clone_entry_for_reuse(entry):
    entry=validate_chunk_entry(entry); result=dict(entry); result["plan"]=copy.deepcopy(entry["plan"]); result["reused"]=True; return result

def _preserved_prefix(*,session,prompt_hashes,chunks,reroll_from_chunk,width,height,chunk_seconds,identity_hash):
    if session is None: return [],[]
    session=validate_session(session); notes=[]
    if int(session["width"])!=int(width) or int(session["height"])!=int(height): raise SessionValidationError(f"session is {session['width']}x{session['height']} but V2 is configured for {width}x{height}")
    if abs(float(session["chunk_seconds"])-float(chunk_seconds))>1e-6: raise SessionValidationError(f"session chunk_seconds={session['chunk_seconds']} does not match {chunk_seconds}")
    if str(session.get("identity_hash","none"))!=str(identity_hash): raise SessionValidationError("the current first-frame identity image does not match the saved session")
    if reroll_from_chunk<0 or reroll_from_chunk>chunks: raise SessionValidationError("reroll_from_chunk must be 0 or a valid one-based chunk index")
    limit=min(len(session["chunks"]),chunks)
    if reroll_from_chunk>0: limit=min(limit,reroll_from_chunk-1)
    preserved=[]
    for index in range(limit):
        entry=validate_chunk_entry(session["chunks"][index])
        if entry["prompt_hash"]!=prompt_hashes[index]: notes.append(f"session reuse stopped before chunk {index+1}: prompt changed"); break
        preserved.append(_clone_entry_for_reuse(entry))
    if reroll_from_chunk==0 and len(preserved)==min(len(session["chunks"]),chunks):
        notes.append(f"resuming after accepted chunk {len(session['chunks'])}" if len(session["chunks"])<chunks else "all requested chunks reused from the session")
    elif reroll_from_chunk>0: notes.append(f"preserved chunks 1-{len(preserved)}; regenerated from chunk {reroll_from_chunk}")
    return preserved,notes

def _conditioning_cache(*,clip,prompts,assets,final_has_last_frame,reference_assets=None,reference_audio_assets=None,timeline_video_assets=None):
    cache={}; final_index=len(prompts)-1
    for index,prompt in enumerate(prompts):
        include_last=bool(final_has_last_frame and index==final_index); key=(prompt,include_last)
        if key in cache: continue
        if reference_assets is not None:
            from ..reference import encode_reference_prompt
            cache[key]=encode_reference_prompt(clip,prompt,reference_assets,reference_audio_assets=reference_audio_assets,timeline_video_assets=timeline_video_assets)
        else:
            cache[key]=encode_prompt_conditioning(clip,prompt,first_image=assets.first_image,last_image=assets.last_image if include_last else None,reference_audio_assets=reference_audio_assets,timeline_video_assets=timeline_video_assets)
    return cache

def run_sequence(*,model:Any,clip:Any,video_vae:Any,audio_vae:Any,sampler:Any,sigmas:torch.Tensor,first_frame:torch.Tensor|None,last_frame:torch.Tensor|None,prompt_plan:dict[str,Any],width:int,height:int,continuity:str,base_seed:int,audio_continuity:bool,exact_total_duration:bool,diagnostics_mode:str,reroll_from_chunk:int,reroll_nonce:int,strict_compatibility:bool,debug:bool,seam_correction:str=SEAM_CORRECTION_OFF,enable_preview:bool=True,session:dict[str,Any]|None=None,initial_state:dict[str,Any]|None=None,latent_only:bool=False,reference_assets=None,reference_audio_source=None,reference_audio_vae=None,timeline_video_source=None):
    from ..conditioning import detect_conditioning_mode, conditioning_mode_label
    from ..run_storage import get_active_run_storage
    storage_controller=get_active_run_storage()
    diagnostics_mode=normalize_diagnostics_mode(diagnostics_mode); plan=validate_prompt_plan(prompt_plan); chunks=int(plan["chunks"]); chunk_seconds=float(plan["chunk_seconds"]); prompts=list(plan["prompts"]); prompt_hashes=list(plan["hashes"]); width,height=int(width),int(height)
    if width<=0 or height<=0 or width%32 or height%32: raise SequenceRuntimeError("width and height must be positive multiples of 32")
    if session is not None and initial_state is not None: raise SequenceRuntimeError("connect either a session or an initial_state, not both")
    if diagnostics_mode not in DIAGNOSTICS_OPTIONS: raise SequenceRuntimeError(f"unknown diagnostics mode: {diagnostics_mode!r}")
    if seam_correction not in SEAM_CORRECTION_OPTIONS: raise SequenceRuntimeError(f"unknown seam correction mode: {seam_correction!r}")
    if not 0<=int(reroll_from_chunk)<=chunks: raise SequenceRuntimeError("reroll_from_chunk must be 0 or a valid one-based chunk index")
    if initial_state is not None and int(reroll_from_chunk) not in (0,1): raise SequenceRuntimeError("with initial_state, reroll_from_chunk can only be 0 or 1")
    try: conditioning_mode=detect_conditioning_mode(first_frame=first_frame,last_frame=last_frame,reference_assets=reference_assets)
    except ValueError as exc: raise SequenceRuntimeError(str(exc)) from exc
    reference_warning=""
    if reference_assets is not None:
        from ..reference import validate_reference_prompts
        if first_frame is not None or last_frame is not None: raise SequenceRuntimeError("Reference images cannot be combined with First Frame or Last Frame in V3.2")
        reference_warning=validate_reference_prompts(prompts,reference_assets.count)
    from ..reference_audio import (
        combine_reference_audio_identity,
        validate_reference_audio_prompts,
    )
    reference_audio_warning=validate_reference_audio_prompts(prompts,reference_audio_source)
    from ..timeline_video import (
        combine_timeline_video_identity,
        validate_timeline_video_prompts,
    )
    timeline_video_warning=validate_timeline_video_prompts(prompts,timeline_video_source)
    decode_estimate_gib=0.0; available_ram_gib=None
    if not latent_only: decode_estimate_gib,available_ram_gib=_check_decode_memory_budget(width=width,height=height,chunks=chunks,chunk_seconds=chunk_seconds)
    issues=check_comfy_h3_runtime()
    if issues and strict_compatibility: raise SequenceRuntimeError("H3 runtime is incompatible: "+"; ".join(issues))
    assets=prepare_identity_assets(video_vae,width=width,height=height,first_frame=first_frame,last_frame=last_frame,encode_latents=False)
    visual_identity_hash=reference_assets.combined_hash if reference_assets is not None else assets.identity_hash
    sequence_identity_hash=combine_reference_audio_identity(visual_identity_hash,reference_audio_source)
    sequence_identity_hash=combine_timeline_video_identity(sequence_identity_hash,timeline_video_source)
    current_model_fingerprint=model_fingerprint(model,extra_wrapper_keys=("h3_continuum_join.apply_model.v1",))
    if storage_controller is not None:
        stored_session=storage_controller.prepare(model=model,model_fingerprint_value=current_model_fingerprint,clip=clip,video_vae=video_vae,sampler=sampler,sigmas=sigmas,prompt_plan=plan,width=width,height=height,chunk_seconds=chunk_seconds,continuity=continuity,audio_continuity=audio_continuity,base_seed=base_seed,reroll_from_chunk=reroll_from_chunk,reroll_nonce=reroll_nonce,first_frame_hash=assets.first_frame_hash,last_frame_hash=assets.last_frame_hash,identity_hash=sequence_identity_hash,strict_compatibility=strict_compatibility,existing_session=session,reference_contract=reference_assets.contract if reference_assets is not None else None,conditioning_mode=conditioning_mode,reference_audio_contract=reference_audio_source.contract if reference_audio_source is not None else None,reference_audio_vae=reference_audio_vae,timeline_video_contract=timeline_video_source.contract if timeline_video_source is not None else None)
        reroll_nonce=storage_controller.effective_reroll_nonce
        if stored_session is not None: session=stored_session
    accelerators=accelerator_summary(model)
    if "Continuum APPLY_MODEL wrapper installed" not in accelerators: accelerators+="; Continuum APPLY_MODEL wrapper installed"
    effective_reroll_from_chunk=0 if storage_controller is not None and session is not None and bool((session.get("settings") or {}).get("run_storage_validated_prefix")) else int(reroll_from_chunk)
    preserved,reuse_notes=_preserved_prefix(session=session,prompt_hashes=prompt_hashes,chunks=chunks,reroll_from_chunk=effective_reroll_from_chunk,width=width,height=height,chunk_seconds=chunk_seconds,identity_hash=sequence_identity_hash)
    if reference_assets is not None:
        reuse_notes.insert(0,f"Reference conditioning: {reference_assets.count} image(s), size={reference_assets.size_mode}; persistent across all chunks.")
        if reference_warning: reuse_notes.append(reference_warning)
    if reference_audio_source is not None:
        reuse_notes.insert(0,"Reference Audio 1 conditioning: persistent across all chunks.")
        if reference_audio_warning: reuse_notes.append(reference_audio_warning)
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
        if timeline_video_source is None:
            cache=_conditioning_cache(clip=clip,prompts=prompts,assets=assets,final_has_last_frame=last_frame is not None,reference_assets=reference_assets,reference_audio_assets=reference_audio_assets)
    entries=preserved[:]; previous_state=None
    if entries: previous_state=entry_to_state(entries[-1])
    elif initial_state is not None:
        previous_state=validate_state(initial_state)
        if int(previous_state["width"])!=width or int(previous_state["height"])!=height: raise SequenceRuntimeError(f"initial_state is {previous_state['width']}x{previous_state['height']} but V2 is configured for {width}x{height}")
    initial_frame_count=align_frame_count_up(int(round(chunk_seconds*FPS))); retained_frames=sum(int(entry["plan"]["net_frames"]) for entry in entries); sampling_reports=[]
    for sequence_index in range(len(entries),chunks):
        prompt=prompts[sequence_index]; prompt_hash_value=prompt_hashes[sequence_index]; is_final=sequence_index==chunks-1; effective_reroll_nonce=int(reroll_nonce) if int(reroll_from_chunk)>0 and sequence_index+1>=int(reroll_from_chunk) else 0; seed=derive_chunk_seed(base_seed,sequence_index,effective_reroll_nonce); motion_score=0.0; video_context=None; audio_context=None; context_before=None
        timeline_video_assets=None
        chunk_cache=cache
        if timeline_video_source is not None:
            from ..timeline_video import encode_timeline_video_chunk
            timeline_video_assets=encode_timeline_video_chunk(video_vae,timeline_video_source,sequence_index)
            chunk_cache=_conditioning_cache(clip=clip,prompts=[prompt],assets=assets,final_has_last_frame=bool(last_frame is not None and is_final),reference_assets=reference_assets,reference_audio_assets=reference_audio_assets,timeline_video_assets=timeline_video_assets)
        if previous_state is None:
            total_frames=initial_frame_count; latent=empty_h3_latent(width,height,total_frames); conditioning=attach_keyframes(chunk_cache[(prompt,bool(last_frame is not None and is_final))],frame_count=total_frames,first_latent=assets.first_latent,last_latent=assets.last_latent if is_final else None); clip_index=1; context_frames=0
            chunk_plan=make_plan(continuation=False,clip_index=clip_index,total_frames=total_frames,trim_frames=0,width=width,height=height,context_frames=5,state_capacity_frames=largest_context_capacity(total_frames),requested_extend_seconds=chunk_seconds,debug=debug); reason="initial clip"
        else:
            context_frames,motion_score,reason=choose_context_frames(continuity,previous_state); desired_cumulative=int(round((sequence_index+1)*chunk_seconds*FPS)); requested_new_frames=max(1,desired_cumulative-retained_frames); shape=make_extension_shape(context_frames,requested_new_frames/FPS); latent=empty_h3_latent(width,height,shape.total_frames)
            base_conditioning=attach_keyframes(chunk_cache[(prompt,bool(last_frame is not None and is_final))],frame_count=shape.total_frames,first_latent=assets.first_latent,last_latent=assets.last_latent if is_final else None)
            video_context,audio_context,grid_offset=select_context(previous_state,context_frames,include_audio=bool(audio_continuity)); context_before=context_fingerprint(video_context,audio_context)
            conditioning=prepare_conditioning(base_conditioning,video_context=video_context,audio_context=audio_context,audio_grid_offset=grid_offset,context_frames=context_frames,new_frame_count=shape.total_frames,first_frame_policy=POLICY_REPLACE,preserve_last_frame=True)
            clip_index=int(previous_state["clip_index"])+1; chunk_plan=make_plan(continuation=True,clip_index=clip_index,total_frames=shape.total_frames,trim_frames=context_frames,width=width,height=height,context_frames=context_frames,state_capacity_frames=largest_context_capacity(shape.net_new_frames),requested_extend_seconds=chunk_seconds,debug=debug)
        chunk_model=clone_model_for_chunk(model,strict=bool(strict_compatibility),debug=bool(debug),chunk_index=clip_index,context_frames=context_frames if previous_state is not None else None)
        sampled=sample_chunk(model=chunk_model,conditioning=conditioning,latent=latent,sampler=sampler,sigmas=sigmas,seed=seed,enable_preview=bool(enable_preview))
        if context_before is not None and video_context is not None: assert_context_unchanged(video_context,audio_context,context_before)
        entry=make_chunk_entry(latent=sampled,plan=chunk_plan,prompt=prompt,prompt_hash=prompt_hash_value,seed=seed,context_frames=context_frames,motion_score=motion_score,reused=False); previous_state=entry_to_state(entry); entries.append(entry)
        if storage_controller is not None: storage_controller.commit_chunk(entry, position=sequence_index)
        retained_frames+=int(chunk_plan["net_frames"])
        sampling_reports.append(f"chunk {sequence_index+1}/{chunks}: seed={seed}, frames={chunk_plan['total_frames']}, trim={chunk_plan['trim_frames']}, retained_total={retained_frames}, context={context_frames} ({reason}), motion={motion_score:.6f}, "+(f"interop=emitted actual_prefix={CONTINUUM_ACTUAL_PREFIX_STEPS} consumer=not_observable" if context_before is not None else "interop=not_emitted"))
        del sampled,latent,conditioning,chunk_model,chunk_cache
        if timeline_video_assets is not None: del timeline_video_assets
    if len(entries)!=chunks: raise SequenceRuntimeError(f"internal sequence length mismatch: expected {chunks}, got {len(entries)}")
    if latent_only:
        last_state=entry_to_state(entries[-1]); parent_id=session.get("session_id") if session is not None else None
        settings={"continuity":continuity,"audio_continuity":bool(audio_continuity),"exact_total_duration":False,"prompt_mode":plan["mode"],"conditioning_mode":conditioning_mode,"base_seed":int(base_seed),"reroll_nonce":int(reroll_nonce),"diagnostics_mode":diagnostics_mode,"initial_state_source":initial_state is not None,"latent_first":True,"first_frame_hash":assets.first_frame_hash,"last_frame_hash":assets.last_frame_hash,"reference_contract":reference_assets.contract if reference_assets is not None else None}
        if reference_audio_source is not None: settings["reference_audio_contract"]=reference_audio_source.contract
        if timeline_video_source is not None: settings["timeline_video_contract"]=timeline_video_source.contract
        new_session=make_session(chunks=entries,width=width,height=height,chunk_seconds=chunk_seconds,identity_hash=sequence_identity_hash,model_fingerprint_value=current_model_fingerprint,parent_session_id=parent_id,reroll_from_chunk=int(reroll_from_chunk),settings=settings)
        report_lines=[f"H3 Continuum V3 {PACKAGE_VERSION}",f"Conditioning mode: {conditioning_mode_label(conditioning_mode)}.",prompt_plan_report(plan),"Decode: external ComfyUI Core VAE nodes; full raw AV chunks retained.",accelerators,"Execution: conditioning precomputed; single call-local MODEL clone per chunk; no internal VAE decode.",*reuse_notes]
        if diagnostics_mode!=DIAGNOSTICS_OFF: report_lines.extend(sampling_reports)
        report_lines.extend([session_summary(new_session),f"Output: {len(entries)} raw AV latent chunk(s); connect Core VAE Decode nodes, then H3 Continuum Assemble V3."])
        return entries,last_state,new_session,"\n".join(report_lines)
    if seam_correction==SEAM_CORRECTION_OFF: images,audio,decode_reports=decode_sequence(entries=entries,video_vae=video_vae,audio_vae=audio_vae,diagnostics_full=diagnostics_mode==DIAGNOSTICS_FULL)
    else: images,audio,decode_reports=decode_sequence_with_seam(entries=entries,video_vae=video_vae,audio_vae=audio_vae,diagnostics_mode=diagnostics_mode,automatic=seam_correction==SEAM_CORRECTION_AUTO)
    duration_report=""
    if exact_total_duration:
        target_frames=int(round(chunks*chunk_seconds*FPS)); images,audio,duration_report=enforce_total_frames(images,audio,target_frames=target_frames,preserve_final_frame=last_frame is not None)
    last_state=entry_to_state(entries[-1]); parent_id=session.get("session_id") if session is not None else None
    settings={"continuity":continuity,"audio_continuity":bool(audio_continuity),"exact_total_duration":bool(exact_total_duration),"prompt_mode":plan["mode"],"base_seed":int(base_seed),"reroll_nonce":int(reroll_nonce),"diagnostics_mode":diagnostics_mode,"initial_state_source":initial_state is not None,"first_frame_hash":assets.first_frame_hash,"last_frame_hash":assets.last_frame_hash,"reference_contract":reference_assets.contract if reference_assets is not None else None}
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
