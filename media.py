"""Reusable video/audio trim and assembly helpers."""

from __future__ import annotations

from typing import Any

import torch
import torch.nn.functional as F

from .constants import FPS


def validate_audio(audio: dict[str, Any], *, name: str = "AUDIO") -> tuple[torch.Tensor, int]:
    if not isinstance(audio, dict) or "waveform" not in audio or "sample_rate" not in audio:
        raise ValueError(f"{name} must contain waveform and sample_rate")
    waveform = audio["waveform"]
    sample_rate = int(audio["sample_rate"])
    if not torch.is_tensor(waveform) or waveform.ndim != 3:
        raise ValueError(f"{name} waveform must be [B,C,samples]")
    if waveform.shape[0] != 1:
        raise ValueError(f"{name} batch size must be 1")
    if sample_rate <= 0:
        raise ValueError(f"{name} sample_rate must be positive")
    return waveform, sample_rate


def trim_audio(audio: dict[str, Any], *, trim_frames: int, output_frames: int):
    """Trim a decoded stream by video-frame time and normalize final duration."""

    waveform, sample_rate = validate_audio(audio)
    trim_samples = int(round(float(trim_frames) / FPS * sample_rate))
    wanted = int(round(float(output_frames) / FPS * sample_rate))
    result = waveform[..., trim_samples : trim_samples + wanted]
    if result.shape[-1] < wanted:
        result = F.pad(result, (0, wanted - result.shape[-1]))
    return {**audio, "waveform": result.contiguous(), "sample_rate": sample_rate}


def assemble_segments(previous_images, previous_audio, next_images, next_audio):
    """Append two Finish-normalized AV segments and correct rounding drift."""

    if not all(
        torch.is_tensor(value) and value.ndim == 4
        for value in (previous_images, next_images)
    ):
        raise ValueError("both IMAGE inputs must be [frames,H,W,C]")
    if tuple(previous_images.shape[1:]) != tuple(next_images.shape[1:]):
        raise ValueError(
            f"image segment shapes differ: {tuple(previous_images.shape[1:])} vs "
            f"{tuple(next_images.shape[1:])}"
        )
    previous_waveform, previous_rate = validate_audio(previous_audio, name="previous_audio")
    next_waveform, next_rate = validate_audio(next_audio, name="next_audio")
    if previous_rate != next_rate:
        raise ValueError("audio sample rates differ; resample before assembling")
    if tuple(previous_waveform.shape[:2]) != tuple(next_waveform.shape[:2]):
        raise ValueError("audio batch/channel shapes differ")
    if previous_waveform.device != next_waveform.device:
        raise ValueError("audio segments are on different devices")
    if previous_images.device != next_images.device:
        raise ValueError("image segments are on different devices")

    expected_previous = int(round(float(previous_images.shape[0]) / FPS * previous_rate))
    expected_next = int(round(float(next_images.shape[0]) / FPS * previous_rate))
    tolerance = max(2, int(round(previous_rate * 0.020)))  # 20 ms safety bound
    for name, waveform_part, expected in (
        ("previous", previous_waveform, expected_previous),
        ("next", next_waveform, expected_next),
    ):
        delta = int(waveform_part.shape[-1]) - expected
        if abs(delta) > tolerance:
            raise ValueError(
                f"{name} segment audio differs from its video duration by "
                f"{delta} samples; pass segments through H3 Continuum Finish first"
            )

    images = torch.cat((previous_images, next_images), dim=0).contiguous()
    waveform = torch.cat((previous_waveform, next_waveform), dim=-1).contiguous()
    expected_total = int(round(float(images.shape[0]) / FPS * previous_rate))
    correction = expected_total - int(waveform.shape[-1])
    if correction < 0:
        waveform = waveform[..., :expected_total].contiguous()
    elif correction > 0:
        waveform = F.pad(waveform, (0, correction)).contiguous()
    audio = {**previous_audio, "waveform": waveform, "sample_rate": previous_rate}
    report = (
        f"Assembled {previous_images.shape[0]} + {next_images.shape[0]} = "
        f"{images.shape[0]} frames ({images.shape[0]/FPS:.3f}s), "
        f"audio samples {waveform.shape[-1]} (sync correction {correction:+d})."
    )
    return images, audio, report
