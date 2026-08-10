"""MiniMax H3 temporal-grid helpers."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .constants import AUDIO_LATENT_FPS, FPS, FRAME_PER_TOKEN

_AUDIO_TICKS_PER_FRAME = Fraction(int(AUDIO_LATENT_FPS), int(FPS))

@dataclass(frozen=True, slots=True)
class ExtensionShape:
    context_frames: int
    requested_new_frames: int
    total_frames: int
    net_new_frames: int
    video_latent_t: int
    audio_latent_t: int
    @property
    def actual_extend_seconds(self) -> float:
        return self.net_new_frames / FPS

@dataclass(frozen=True, slots=True)
class AVContextWindow:
    source_frame_count: int
    context_frames: int
    video_start_slot: int
    video_stop_slot: int
    audio_start_tick: int
    audio_stop_tick: int
    audio_grid_offset: float
    @property
    def audio_steps(self) -> int:
        return self.audio_stop_tick - self.audio_start_tick

def is_valid_frame_count(frame_count: int) -> bool:
    return frame_count >= 5 and frame_count % 17 == 5

def align_frame_count_up(frame_count: int) -> int:
    n = max(5, int(frame_count))
    remainder = (n - 5) % 17
    return n if remainder == 0 else n + (17 - remainder)

def align_frame_count_nearest(frame_count: int, *, minimum: int = 5) -> int:
    target = max(int(frame_count), int(minimum), 5)
    min_valid = align_frame_count_up(minimum)
    k_floor = max(0, (target - 5) // 17)
    low = max(5 + 17 * k_floor, min_valid)
    high = max(low + 17, min_valid)
    return low if abs(target - low) < abs(high - target) else high

def video_latent_t(frame_count: int) -> int:
    if not is_valid_frame_count(frame_count):
        raise ValueError(f"H3 frame count must satisfy 17k+5; got {frame_count}")
    return 2 if frame_count <= 5 else ((frame_count - 5) // 17) * 5 + 2

def pixel_frames_for_latent_t(latent_t: int) -> int:
    if int(latent_t) < 1:
        raise ValueError("video latent T must be positive")
    return sum(FRAME_PER_TOKEN[index % 5] for index in range(int(latent_t)))

def latent_slot_offsets(latent_t: int) -> tuple[int, ...]:
    if int(latent_t) < 1:
        raise ValueError("video latent T must be positive")
    out=[]; cursor=0
    for index in range(int(latent_t)):
        out.append(cursor); cursor += FRAME_PER_TOKEN[index % 5]
    return tuple(out)

def context_slots(context_frames: int) -> int:
    target=int(context_frames)
    for slots in range(1,256):
        frames=pixel_frames_for_latent_t(slots)
        if frames==target: return slots
        if frames>target: break
    raise ValueError(f"context_frames={context_frames} is not representable; use 5, 22, or 39")

def audio_latent_t(frame_count: int) -> int:
    return int(round(Fraction(int(frame_count)) * _AUDIO_TICKS_PER_FRAME))

def audio_grid_offset(frame_count: int, actual_audio_t: int) -> float:
    value = Fraction(int(actual_audio_t)) - Fraction(int(frame_count)) * _AUDIO_TICKS_PER_FRAME
    value=float(value)
    return 0.0 if abs(value)<1e-9 else value

def audio_overhang(frame_count: int, actual_audio_t: int) -> float:
    return audio_grid_offset(frame_count, actual_audio_t)

def audio_latent_t_from_grid_offset(frame_count: int, grid_offset: float) -> int:
    exact_end=float(Fraction(int(frame_count))*_AUDIO_TICKS_PER_FRAME)
    candidate=int(round(exact_end+float(grid_offset)))
    recovered=audio_grid_offset(int(frame_count),candidate)
    if abs(recovered-float(grid_offset))>1e-6:
        raise ValueError("source audio-grid phase cannot be recovered from frame count and signed offset")
    return candidate

def make_av_context_window(source_frame_count:int, actual_audio_t:int, context_frames:int)->AVContextWindow:
    source_frames=int(source_frame_count); context=int(context_frames)
    if not is_valid_frame_count(source_frames):
        raise ValueError(f"source_frame_count={source_frames} is not on the native H3 17k+5 grid")
    if context not in (5,22,39) or context>source_frames:
        raise ValueError(f"unsupported {context}-frame context for {source_frames} source frames")
    source_video_t=video_latent_t(source_frames); context_video_t=context_slots(context)
    video_start=source_video_t-context_video_t
    if video_start<0 or video_start % len(FRAME_PER_TOKEN):
        raise ValueError("video context tail does not begin at a uniquely recoverable H3 latent-cycle phase")
    audio_stop=int(actual_audio_t); grid_offset=audio_grid_offset(source_frames,audio_stop)
    if not (-0.500001<=grid_offset<=0.500001):
        raise ValueError(f"source audio-grid offset {grid_offset:.6f} is outside [-0.5,0.5]")
    audio_steps=audio_latent_t(context); audio_start=audio_stop-audio_steps
    if audio_start<0: raise ValueError("source audio latent is too short for the requested context")
    return AVContextWindow(source_frames,context,video_start,source_video_t,audio_start,audio_stop,grid_offset)

def make_extension_shape(context_frames:int, extend_seconds:float)->ExtensionShape:
    context_frames=int(context_frames); context_slots(context_frames)
    requested_new=max(1,int(round(float(extend_seconds)*FPS)))
    total=align_frame_count_nearest(context_frames+requested_new,minimum=context_frames+1)
    net=total-context_frames
    if net<1: raise RuntimeError("computed continuation contains no new frames")
    return ExtensionShape(context_frames,requested_new,total,net,video_latent_t(total),audio_latent_t(total))

def largest_context_capacity(frame_count:int)->int:
    available=int(frame_count)
    for capacity in (39,22,5):
        if available>=capacity: return capacity
    raise ValueError(f"at least 5 retained frames are required for a continuation state; got {available}")

def run_temporal_self_test()->None:
    expected={5:(2,(0,1)),22:(7,(0,1,5,9,13,17,18)),39:(12,(0,1,5,9,13,17,18,22,26,30,34,35))}
    for frames,(slots,offsets) in expected.items():
        assert context_slots(frames)==slots
        assert latent_slot_offsets(slots)==offsets
        assert pixel_frames_for_latent_t(slots)==frames
    shape=make_extension_shape(22,5.0)
    assert (shape.total_frames,shape.net_new_frames)==(141,119)
    assert (shape.video_latent_t,shape.audio_latent_t)==(42,235)
    window=make_av_context_window(141,235,22)
    assert (window.video_start_slot,window.video_stop_slot)==(35,42)
    assert (window.audio_start_tick,window.audio_stop_tick)==(198,235)
