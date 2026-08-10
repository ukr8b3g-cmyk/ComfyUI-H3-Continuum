"""Lightweight join diagnostics without external vision/audio models."""
from __future__ import annotations
import math
from typing import Any
import torch
from ..constants import FPS
from .seam_types import SeamDecision
def _audio_waveform(audio:dict[str,Any]):
    waveform=audio.get("waveform"); sample_rate=int(audio.get("sample_rate",0))
    if not torch.is_tensor(waveform) or waveform.ndim!=3: raise ValueError("audio waveform must be [B,C,S]")
    if sample_rate<=0: raise ValueError("audio sample_rate is invalid")
    return waveform.to(dtype=torch.float32),sample_rate
def _normalized_correlation(a,b):
    length=min(int(a.numel()),int(b.numel()))
    if length<8:return 0.0
    a=a.reshape(-1)[:length].float(); b=b.reshape(-1)[:length].float(); a=a-a.mean(); b=b-b.mean(); denom=torch.sqrt(torch.sum(a.square())*torch.sum(b.square())).clamp_min(1e-12); value=float((torch.sum(a*b)/denom).item()); return max(-1.0,min(1.0,value)) if math.isfinite(value) else 0.0
def overlap_diagnostics(*,previous_images,previous_audio,next_raw_images,next_raw_audio,context_frames):
    frame_count=min(int(context_frames),int(previous_images.shape[0]),int(next_raw_images.shape[0]))
    if frame_count<=0:return {"video_overlap_mae":0.0,"video_overlap_psnr":99.0,"audio_overlap_correlation":0.0,"audio_boundary_jump":0.0}
    prev=previous_images[-frame_count:].detach().to(dtype=torch.float32); nxt=next_raw_images[:frame_count].detach().to(dtype=torch.float32); mse=float(torch.mean((prev-nxt).square()).item()); mae=float(torch.mean(torch.abs(prev-nxt)).item()); psnr=99.0 if mse<=1e-12 else max(0.0,-10.0*math.log10(mse))
    prev_wave,prev_sr=_audio_waveform(previous_audio); next_wave,next_sr=_audio_waveform(next_raw_audio)
    if prev_sr!=next_sr: raise ValueError("diagnostic audio sample rates do not match")
    samples=min(int(round(frame_count/FPS*prev_sr)),int(prev_wave.shape[-1]),int(next_wave.shape[-1])); correlation=_normalized_correlation(prev_wave[...,-samples:],next_wave[...,:samples]) if samples>0 else 0.0; jump=float(torch.mean(torch.abs(prev_wave[...,-1]-next_wave[...,0])).item()) if prev_wave.shape[-1] and next_wave.shape[-1] else 0.0
    return {"video_overlap_mae":mae,"video_overlap_psnr":psnr,"audio_overlap_correlation":correlation,"audio_boundary_jump":jump}
def av_duration_error_samples(images,audio):
    waveform,sample_rate=_audio_waveform(audio); return int(waveform.shape[-1])-int(round(float(images.shape[0])/FPS*sample_rate))
def format_join_metrics(index,metrics): return f"join {index-1}->{index}: video MAE={metrics['video_overlap_mae']:.6f}, PSNR={metrics['video_overlap_psnr']:.2f}dB, audio corr={metrics['audio_overlap_correlation']:.4f}, boundary jump={metrics['audio_boundary_jump']:.6f}"
def format_seam_decision(index,decision:SeamDecision,*,full:bool):
    fallback=decision.fallback_reason or "none"
    if not full:return f"seam {index-1}->{index}: cut=-{decision.cut_rewind_frames}f, native score {decision.legacy_score:.4f}->{decision.corrected_score:.4f}, video blend={decision.video_blend_frames}f, audio offset={decision.audio_metrics.offset_samples:+d} samples, fallback={fallback}"
    return (f"Seam {index-1}->{index}\n  Native score      : {decision.legacy_score:.6f}\n  Selected cut      : -{decision.cut_rewind_frames} frames\n  Cut score         : {decision.cut_score:.6f}\n  Candidate score   : {decision.candidate_score:.6f}\n  Final score       : {decision.corrected_score:.6f}\n  Improvement       : {decision.improvement*100.0:.2f}%\n  Native 5f peak    : {decision.native_window_peak:.6f}\n  Candidate 5f peak : {decision.candidate_window_peak:.6f}\n  Luminance gain    : {decision.luma_gain:.4f}\n  Chroma bias       : {decision.chroma_bias}\n  Video blend       : {decision.video_blend_frames} frames\n  Audio correlation : {decision.audio_metrics.correlation_before:.4f}->{decision.audio_metrics.correlation_after:.4f}\n  Audio jump        : {decision.audio_metrics.boundary_jump_before:.6f}->{decision.audio_metrics.boundary_jump_after:.6f}\n  Audio offset      : {decision.audio_metrics.offset_samples:+d} samples\n  Audio crossfade   : {decision.audio_crossfade_samples} samples\n  Fallback          : {fallback}")
