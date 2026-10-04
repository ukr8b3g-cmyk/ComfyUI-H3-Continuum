"""Use Core audio DSP; retain the existing adapter for older Core versions."""

from __future__ import annotations

import importlib


def resample_audio(waveform, source_rate: int, target_rate: int):
    if source_rate == target_rate:
        return waveform
    try:
        core_audio = importlib.import_module("comfy.audio")
    except ModuleNotFoundError as exc:
        if exc.name not in {"comfy", "comfy.audio"}:
            raise
        core_audio = None
    core_resample = getattr(core_audio, "resample", None)
    if core_resample is not None:
        # Errors from an available Core API are real errors, not API absence.
        return core_resample(waveform, source_rate, target_rate)
    try:
        torchaudio = importlib.import_module("torchaudio")
    except ModuleNotFoundError as exc:
        if exc.name != "torchaudio":
            raise
        raise RuntimeError(
            "Audio resampling requires comfy.audio.resample or legacy torchaudio"
        ) from exc
    return torchaudio.functional.resample(waveform, source_rate, target_rate)
