"""Conservative latent-motion analysis for automatic context selection."""

from __future__ import annotations

import math
from typing import Any

import torch

from ..constants import CONTINUITY_FRAMES, V2_CONTINUITY_AUTO
from ..state import validate_state

# Conservative defaults. Borderline values intentionally fall back to 22 frames.
_AUTO_STATIC_MAX = 0.035
_AUTO_STRONG_MIN = 0.120


def latent_motion_score(state: dict[str, Any]) -> float:
    state = validate_state(state)
    video = state["video_tail"].detach().to(dtype=torch.float32)
    if video.shape[2] < 2:
        return 0.0
    temporal_delta = video[:, :, 1:] - video[:, :, :-1]
    delta_rms = torch.sqrt(torch.mean(temporal_delta.square()))
    signal_rms = torch.sqrt(torch.mean(video.square())).clamp_min(1e-6)
    score = float((delta_rms / signal_rms).item())
    if not math.isfinite(score):
        return _AUTO_STRONG_MIN
    return max(0.0, min(score, 1000.0))


def choose_context_frames(mode: str, state: dict[str, Any]) -> tuple[int, float, str]:
    state = validate_state(state)
    capacity = int(state["capacity_frames"])
    score = latent_motion_score(state)

    if mode != V2_CONTINUITY_AUTO:
        if mode not in CONTINUITY_FRAMES:
            raise ValueError(f"unknown continuity mode: {mode!r}")
        requested = int(CONTINUITY_FRAMES[mode])
        if requested > capacity:
            raise ValueError(
                f"state retains {capacity} frames but continuity requests {requested}"
            )
        return requested, score, "fixed profile"

    if capacity < 22:
        return 5, score, "state capacity below 22 frames"
    if score <= _AUTO_STATIC_MAX:
        return 5, score, "low latent motion"
    if score >= _AUTO_STRONG_MIN and capacity >= 39:
        return 39, score, "high latent motion"
    return 22, score, "conservative balanced fallback"
