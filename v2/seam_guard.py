"""Conservative CPU-only decoded seam correction for H3 Continuum V2.1."""
from __future__ import annotations
import math
import torch
import torch.nn.functional as F
from .seam_types import AudioSeamMetrics, SeamDecision, VideoSeamMetrics
COMPARE_SIZE=96; MAX_CUT_REWIND=3; MIN_RELATIVE_IMPROVEMENT=0.10; MIN_ABSOLUTE_IMPROVEMENT=0.003; SAFE_SCORE_LIMIT=0.35
AUTO_MIN_RELATIVE_IMPROVEMENT=0.20; AUTO_WINDOW_FRAMES=5; AUTO_MIN_WINDOW_RELATIVE_IMPROVEMENT=0.05; AUTO_MIN_WINDOW_ABSOLUTE_IMPROVEMENT=0.0005
AUTO_COMPONENT_RELATIVE_TOLERANCE=0.01; AUTO_COMPONENT_ABSOLUTE_TOLERANCE=0.0001
WEIGHT_PIXEL=0.35; WEIGHT_LUMA=0.20; WEIGHT_CHROMA=0.10; WEIGHT_EDGE=0.15; WEIGHT_TEMPORAL=0.20

def _video_shape(frames,label):
    if not torch.is_tensor(frames) or frames.ndim!=4 or frames.shape[-1]<3: raise ValueError(f"{label} must be an IMAGE tensor [T,H,W,C]")
def _downsample_rgb(frames):
    _video_shape(frames,"video seam frames"); rgb=frames[...,:3].detach().to(device="cpu",dtype=torch.float32).permute(0,3,1,2)
    if tuple(rgb.shape[-2:])!=(COMPARE_SIZE,COMPARE_SIZE): rgb=F.interpolate(rgb,size=(COMPARE_SIZE,COMPARE_SIZE),mode="bilinear",align_corners=False)
    rgb=rgb.permute(0,2,3,1).clamp(0.0,1.0)
    if not bool(torch.isfinite(rgb).all().item()): raise ValueError("video seam comparison contains NaN or Inf")
    return rgb
def _luma(frame): return torch.sum(frame*frame.new_tensor((0.2126,0.7152,0.0722)),dim=-1)
def _boundary_metrics(previous_images,next_images):
    if previous_images.shape[0]<2 or next_images.shape[0]<2: raise ValueError("video seam scoring needs two frames on each side")
    prev=_downsample_rgb(previous_images[-2:]); nxt=_downsample_rgb(next_images[:2]); prev_before,prev_edge=prev[0],prev[1]; next_edge,next_after=nxt[0],nxt[1]
    pixel=torch.mean(torch.abs(prev_edge-next_edge)).clamp(0,1); prev_y=_luma(prev_edge); next_y=_luma(next_edge); luma=torch.mean(torch.abs(prev_y-next_y)).clamp(0,1)
    prev_chroma=prev_edge-prev_y.unsqueeze(-1); next_chroma=next_edge-next_y.unsqueeze(-1); chroma=(torch.mean(torch.abs(prev_chroma-next_chroma))/2.0).clamp(0,1)
    prev_gx=prev_y[:,1:]-prev_y[:,:-1]; next_gx=next_y[:,1:]-next_y[:,:-1]; prev_gy=prev_y[1:,:]-prev_y[:-1,:]; next_gy=next_y[1:,:]-next_y[:-1,:]
    edge=((torch.mean(torch.abs(prev_gx-next_gx))+torch.mean(torch.abs(prev_gy-next_gy)))/4.0).clamp(0,1)
    prev_delta=prev_edge-prev_before; next_delta=next_after-next_edge; temporal=(torch.mean(torch.abs(prev_delta-next_delta))/2.0).clamp(0,1)
    motion=max(float(torch.mean(torch.abs(prev_delta)).item()),float(torch.mean(torch.abs(next_delta)).item()))
    score=WEIGHT_PIXEL*float(pixel.item())+WEIGHT_LUMA*float(luma.item())+WEIGHT_CHROMA*float(chroma.item())+WEIGHT_EDGE*float(edge.item())+WEIGHT_TEMPORAL*float(temporal.item())
    if not math.isfinite(score): raise ValueError("video seam score is not finite")
    return VideoSeamMetrics(float(pixel.item()),float(luma.item()),float(chroma.item()),float(edge.item()),float(temporal.item()),motion,max(0.0,min(1.0,score)))
def analyze_video_seam(previous_images,next_raw_images,*,context_frames,rewind_frames=0):
    context_frames=int(context_frames); rewind_frames=int(rewind_frames); cut_index=context_frames-rewind_frames; previous_stop=int(previous_images.shape[0])-rewind_frames
    if rewind_frames<0 or rewind_frames>MAX_CUT_REWIND: raise ValueError("rewind_frames is outside the V2.1 safe range")
    if cut_index<0 or previous_stop<2 or cut_index+2>next_raw_images.shape[0]: raise ValueError("insufficient frames for the requested adaptive cut")
    return _boundary_metrics(previous_images[previous_stop-2:previous_stop],next_raw_images[cut_index:cut_index+2])
def choose_adaptive_cut(previous_images,next_raw_images,*,context_frames):
    legacy=analyze_video_seam(previous_images,next_raw_images,context_frames=context_frames,rewind_frames=0); best_rewind=0; best=legacy
    maximum=min(MAX_CUT_REWIND,max(0,int(context_frames)),max(0,int(previous_images.shape[0])-2))
    for rewind in range(1,maximum+1):
        try: candidate=analyze_video_seam(previous_images,next_raw_images,context_frames=context_frames,rewind_frames=rewind)
        except ValueError: continue
        if candidate.score<best.score: best_rewind,best=rewind,candidate
    absolute=legacy.score-best.score; relative=absolute/max(legacy.score,1e-12)
    accepted=best_rewind>0 and relative>=MIN_RELATIVE_IMPROVEMENT and absolute>=MIN_ABSOLUTE_IMPROVEMENT and best.score<=SAFE_SCORE_LIMIT
    return (best_rewind,legacy,best) if accepted else (0,legacy,legacy)
def apply_color_guard(previous_images,current_images):
    before=_boundary_metrics(previous_images[-2:],current_images[:2]); count=min(4,int(current_images.shape[0]))
    if count<2: return current_images,1.0,(0.0,0.0,0.0),before
    prev_rgb=_downsample_rgb(previous_images[-2:]); current_rgb=_downsample_rgb(current_images[:2]); prev_luma=float(_luma(prev_rgb).mean().item()); current_luma=float(_luma(current_rgb).mean().item()); requested_gain=prev_luma/max(current_luma,1e-6)
    if not 0.85<=requested_gain<=1.15: return current_images,1.0,(0.0,0.0,0.0),before
    gain=max(0.94,min(1.06,requested_gain)); prev_y=_luma(prev_rgb).unsqueeze(-1); current_y=_luma(current_rgb).unsqueeze(-1); requested_bias=(prev_rgb-prev_y).mean(dim=(0,1,2))-(current_rgb-current_y).mean(dim=(0,1,2))
    if float(torch.max(torch.abs(requested_bias)).item())>0.08: return current_images,1.0,(0.0,0.0,0.0),before
    bias=requested_bias.clamp(-0.02,0.02); result=current_images.clone().contiguous(); original=result[:count].clone(); fade=result.new_tensor((1.0,0.65,0.30,0.0))[:count]; luma_weights=result.new_tensor((0.2126,0.7152,0.0722))
    for index in range(count):
        weight=fade[index]; rgb=result[index,...,:3]; y=torch.sum(rgb*luma_weights,dim=-1,keepdim=True); chroma=rgb-y; frame_gain=1.0+(gain-1.0)*weight; frame_bias=bias.to(dtype=rgb.dtype)*weight; result[index,...,:3]=(y*frame_gain+chroma+frame_bias).clamp(0.0,1.0)
    after=_boundary_metrics(previous_images[-2:],result[:2])
    if after.score>before.score*1.01: result[:count].copy_(original); return result,1.0,(0.0,0.0,0.0),before
    return result,gain,tuple(float(v) for v in bias.tolist()),after
def choose_video_blend(metrics):
    if metrics.motion<=0.015: return 2
    if metrics.motion<=0.040: return 1
    return 0
def apply_video_blend(previous_frames,aligned_next_frames,*,blend_frames):
    blend_frames=min(int(blend_frames),int(previous_frames.shape[0]),int(aligned_next_frames.shape[0]),2)
    if blend_frames<=0: return previous_frames[:0].clone()
    previous=previous_frames[-blend_frames:].clone(); current=aligned_next_frames[-blend_frames:].to(dtype=previous.dtype)
    for index in range(blend_frames):
        progress=float(index+1)/float(blend_frames+1); alpha=0.5-0.5*math.cos(math.pi*progress); previous[index].mul_(1.0-alpha).add_(current[index],alpha=alpha)
    return previous
def _seam_window_peak(previous_images,next_images,*,window_frames=AUTO_WINDOW_FRAMES):
    if previous_images.shape[0]<1 or next_images.shape[0]<2: raise ValueError("video seam window scoring needs one previous and two next frames")
    count=min(max(2,int(window_frames)),int(next_images.shape[0])); sequence=torch.cat((previous_images[-1:],next_images[:count]),dim=0); rgb=_downsample_rgb(sequence)
    pixel_delta=torch.mean(torch.abs(rgb[1:]-rgb[:-1]),dim=(1,2,3)); mean_luma=_luma(rgb).mean(dim=(1,2)); luma_delta=torch.abs(mean_luma[1:]-mean_luma[:-1]); combined=0.75*pixel_delta+0.25*luma_delta
    peak=float(torch.max(combined).item())
    if not math.isfinite(peak): raise ValueError("video seam window score is not finite")
    return max(0.0,min(1.0,peak))
def _auto_rejection_reason(legacy,candidate,*,improvement,absolute_improvement,native_window_peak,candidate_window_peak):
    if candidate.score>SAFE_SCORE_LIMIT: return "Auto kept native video; candidate score exceeded the safe limit"
    if improvement<AUTO_MIN_RELATIVE_IMPROVEMENT or absolute_improvement<MIN_ABSOLUTE_IMPROVEMENT: return "Auto kept native video; candidate improvement was below the conservative threshold"
    for label in ("pixel_mae_norm","luma_norm","chroma_norm","edge_norm","temporal_norm","motion"):
        before=float(getattr(legacy,label)); after=float(getattr(candidate,label)); limit=before*(1.0+AUTO_COMPONENT_RELATIVE_TOLERANCE)+AUTO_COMPONENT_ABSOLUTE_TOLERANCE
        if after>limit: return f"Auto kept native video; {label} regressed"
    window_absolute=native_window_peak-candidate_window_peak; window_relative=window_absolute/max(native_window_peak,1e-12)
    if window_relative<AUTO_MIN_WINDOW_RELATIVE_IMPROVEMENT or window_absolute<AUTO_MIN_WINDOW_ABSOLUTE_IMPROVEMENT: return "Auto kept native video; the five-frame transition peak did not clearly improve"
    return None
def correct_seam(previous_images,next_raw_images,*,context_frames,automatic=False):
    native_current=next_raw_images[int(context_frames):]; native_window_peak=_seam_window_peak(previous_images,native_current); rewind,legacy,selected=choose_adaptive_cut(previous_images,next_raw_images,context_frames=context_frames); cut_index=int(context_frames)-rewind; previous_stop=int(previous_images.shape[0])-rewind
    if previous_stop<2 or cut_index<0: raise ValueError("adaptive cut would exhaust a seam side")
    current=next_raw_images[cut_index:].clone().contiguous(); kept_previous=previous_images[:previous_stop]; current,gain,bias,corrected=apply_color_guard(kept_previous,current)
    blend_frames=0 if automatic else min(choose_video_blend(selected),cut_index,previous_stop); video_patch=None; score_previous=kept_previous[-2:].clone()
    if blend_frames>0:
        video_patch=apply_video_blend(kept_previous[-blend_frames:],next_raw_images[cut_index-blend_frames:cut_index],blend_frames=blend_frames); replaced=min(blend_frames,2); score_previous[-replaced:].copy_(video_patch[-replaced:]); corrected=_boundary_metrics(score_previous,current[:2])
    candidate_window_peak=_seam_window_peak(score_previous,current); improvement=(legacy.score-corrected.score)/max(legacy.score,1e-12); absolute_improvement=legacy.score-corrected.score
    if corrected.score>legacy.score*1.01:
        return native_current.clone().contiguous(),SeamDecision(legacy_score=legacy.score,cut_score=selected.score,candidate_score=corrected.score,corrected_score=legacy.score,native_window_peak=native_window_peak,candidate_window_peak=candidate_window_peak,fallback_reason="corrected score was worse than native video"),None
    if automatic:
        fallback_reason=_auto_rejection_reason(legacy,corrected,improvement=improvement,absolute_improvement=absolute_improvement,native_window_peak=native_window_peak,candidate_window_peak=candidate_window_peak)
        if fallback_reason is not None:
            return native_current.clone().contiguous(),SeamDecision(legacy_score=legacy.score,cut_score=selected.score,candidate_score=corrected.score,corrected_score=legacy.score,improvement=improvement,native_window_peak=native_window_peak,candidate_window_peak=candidate_window_peak,fallback_reason=fallback_reason),None
    return current,SeamDecision(cut_rewind_frames=rewind,legacy_score=legacy.score,cut_score=selected.score,candidate_score=corrected.score,corrected_score=corrected.score,improvement=improvement,native_window_peak=native_window_peak,candidate_window_peak=candidate_window_peak,video_blend_frames=blend_frames,luma_gain=gain,chroma_bias=bias),video_patch

def _audio_mid(waveform):
    if not torch.is_tensor(waveform) or waveform.ndim!=3: raise ValueError("audio seam waveform must be [B,C,S]")
    value=waveform.detach().to(device="cpu",dtype=torch.float32)
    if not bool(torch.isfinite(value).all().item()): raise ValueError("audio seam waveform contains NaN or Inf")
    return value.mean(dim=(0,1))
def _correlation(a,b):
    length=min(int(a.numel()),int(b.numel()))
    if length<8: return 0.0
    a=a[:length]-a[:length].mean(); b=b[:length]-b[:length].mean(); denominator=torch.sqrt(torch.sum(a.square())*torch.sum(b.square())).clamp_min(1e-12); value=float((torch.sum(a*b)/denominator).item()); return max(-1.0,min(1.0,value)) if math.isfinite(value) else 0.0
def analyze_audio_seam(previous_waveform,next_raw_waveform,*,sample_rate,cut_sample):
    sample_rate=int(sample_rate); cut_sample=int(cut_sample); previous=_audio_mid(previous_waveform); current=_audio_mid(next_raw_waveform); max_lag=max(1,int(round(sample_rate*0.020))); window=min(max(8,int(round(sample_rate*0.080))),int(previous.shape[-1]),max(0,cut_sample-max_lag))
    if sample_rate<=0 or window<8: raise ValueError("insufficient audio for seam alignment")
    previous_tail=previous[-window:]
    def correlation_at(lag):
        stop=cut_sample+int(lag); start=stop-window
        if start<0 or stop>current.shape[-1]: return None
        return _correlation(previous_tail,current[start:stop])
    baseline=correlation_at(0)
    if baseline is None: raise ValueError("audio seam cut is outside the decoded waveform")
    best_lag,best_correlation=0,baseline
    for lag in range(-max_lag,max_lag+1):
        corr=correlation_at(lag)
        if corr is not None and corr>best_correlation: best_lag,best_correlation=lag,corr
    if best_correlation<0.20 or best_correlation-baseline<0.02: best_lag,best_correlation=0,baseline
    else:
        center=max(0,min(int(current.shape[-1])-1,cut_sample+best_lag)); radius=max(1,int(round(sample_rate*0.001))); start=max(0,center-radius); stop=min(int(current.shape[-1]),center+radius+1)
        if stop>start: best_lag=int(torch.argmin(torch.abs(current[start:stop])).item())+start-cut_sample
    before_jump=float(torch.mean(torch.abs(previous_waveform[...,-1]-next_raw_waveform[...,cut_sample])).item())
    return AudioSeamMetrics(baseline,best_correlation,before_jump,before_jump,int(best_lag))
def _audio_crossfade_ms(previous_waveform,next_raw_waveform,*,cut_sample,sample_rate):
    probe=max(8,int(round(sample_rate*0.020)))
    if previous_waveform.shape[-1]<probe or cut_sample<probe: return 10
    previous=_audio_mid(previous_waveform)[-probe:]; current=_audio_mid(next_raw_waveform)[cut_sample-probe:cut_sample]; rms=torch.sqrt(torch.mean(torch.cat((previous,current)).square())).clamp_min(1e-6); transient=max(float(torch.mean(torch.abs(torch.diff(previous))).item()),float(torch.mean(torch.abs(torch.diff(current))).item()))/float(rms.item())
    if transient>0.80:return 10
    if transient>0.35:return 20
    if transient>0.15:return 40
    return 60
def apply_audio_seam(previous_waveform,next_raw_waveform,metrics,*,sample_rate,cut_sample):
    if metrics.correlation_after<0.20:return None,metrics,0,1.0,0.0
    fade_ms=_audio_crossfade_ms(previous_waveform,next_raw_waveform,cut_sample=cut_sample,sample_rate=sample_rate); fade_samples=min(int(round(sample_rate*fade_ms/1000.0)),int(previous_waveform.shape[-1]),int(cut_sample))
    if fade_samples<2:return None,metrics,0,1.0,0.0
    progress=torch.linspace(0.0,1.0,fade_samples,dtype=torch.float32,device="cpu"); base_indices=torch.arange(cut_sample-fade_samples,cut_sample,dtype=torch.long); offsets=torch.round(float(metrics.offset_samples)*(1.0-progress)).to(dtype=torch.long); indices=(base_indices+offsets).clamp(0,int(next_raw_waveform.shape[-1])-1)
    current=next_raw_waveform.detach().to("cpu").index_select(-1,indices); previous=previous_waveform[...,-fade_samples:].detach().to("cpu"); previous_rms=torch.sqrt(torch.mean(previous.float().square())).clamp_min(1e-6); current_rms=torch.sqrt(torch.mean(current.float().square())).clamp_min(1e-6); requested_db=20.0*math.log10(float((previous_rms/current_rms).item())); level_db=max(-1.5,min(1.5,requested_db)) if abs(requested_db)<=6.0 else 0.0; level_gain=10.0**(level_db/20.0); requested_dc=float((previous.float().mean()-current.float().mean()).item()); dc_bias=max(-0.02,min(0.02,requested_dc)) if abs(requested_dc)<=0.10 else 0.0; current=current*level_gain+dc_bias
    shape=[1]*(previous.ndim-1)+[fade_samples]; fade_in=torch.sin(progress*(math.pi/2.0)).reshape(shape); fade_out=torch.cos(progress*(math.pi/2.0)).reshape(shape); patch=previous*fade_out+current.to(dtype=previous.dtype)*fade_in; input_peak=max(float(previous.abs().max().item()),float(current.abs().max().item()),1e-6); patch_peak=float(patch.abs().max().item())
    if patch_peak>input_peak*1.05: patch=patch*((input_peak*1.05)/patch_peak)
    after_jump=float(torch.mean(torch.abs(patch[...,-1]-next_raw_waveform[...,cut_sample])).item()); updated=AudioSeamMetrics(metrics.correlation_before,metrics.correlation_after,metrics.boundary_jump_before,after_jump,metrics.offset_samples); return patch.contiguous(),updated,fade_samples,level_gain,dc_bias
def correct_audio_seam(previous_waveform,next_raw_waveform,*,sample_rate,cut_sample):
    metrics=analyze_audio_seam(previous_waveform,next_raw_waveform,sample_rate=sample_rate,cut_sample=cut_sample); return apply_audio_seam(previous_waveform,next_raw_waveform,metrics,sample_rate=sample_rate,cut_sample=cut_sample)
