"""Transient types used by V2.1 decoded seam correction."""
from __future__ import annotations
from dataclasses import dataclass
@dataclass(frozen=True)
class VideoSeamMetrics:
    pixel_mae_norm: float
    luma_norm: float
    chroma_norm: float
    edge_norm: float
    temporal_norm: float
    motion: float
    score: float
@dataclass(frozen=True)
class AudioSeamMetrics:
    correlation_before: float = 0.0
    correlation_after: float = 0.0
    boundary_jump_before: float = 0.0
    boundary_jump_after: float = 0.0
    offset_samples: int = 0
@dataclass
class SeamDecision:
    cut_rewind_frames: int = 0
    legacy_score: float = 0.0
    cut_score: float = 0.0
    corrected_score: float = 0.0
    improvement: float = 0.0
    video_blend_frames: int = 0
    luma_gain: float = 1.0
    chroma_bias: tuple[float,float,float] = (0.0,0.0,0.0)
    audio_metrics: AudioSeamMetrics = AudioSeamMetrics()
    audio_crossfade_samples: int = 0
    audio_level_gain: float = 1.0
    audio_dc_bias: float = 0.0
    fallback_reason: str | None = None
