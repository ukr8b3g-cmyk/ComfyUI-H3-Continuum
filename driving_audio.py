"""Core-aligned Driving Audio preparation for H3 Continuum V3.4."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

import torch


DRIVING_AUDIO_CONTRACT_VERSION = 1
DRIVING_AUDIO_PREPROCESS_VERSION = 1
H3_AUDIO_LATENT_FPS = 40


def _tensor_sha256(value: torch.Tensor) -> str:
    tensor = value.detach().to("cpu").contiguous()
    digest = hashlib.sha256()
    digest.update(str(tuple(int(v) for v in tensor.shape)).encode("ascii"))
    digest.update(str(tensor.dtype).encode("ascii"))
    digest.update(tensor.numpy().tobytes(order="C"))
    return digest.hexdigest()


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class DrivingAudioSource:
    source_audio: dict[str, Any]
    resampled_waveform: torch.Tensor
    resolved_vae_sample_rate: int
    contract: dict[str, Any]
    combined_hash: str


@dataclass(frozen=True)
class DrivingAudioAssets:
    source: DrivingAudioSource
    audio_latent: torch.Tensor


def prepare_driving_audio_source(
    audio: dict[str, Any] | None,
    audio_vae: Any,
    *,
    target_frames: int,
    fps: int,
) -> DrivingAudioSource | None:
    """Prepare only the effective target-duration prefix; never pad a short source."""
    if audio is None:
        return None
    if audio_vae is None:
        raise ValueError("anchoring guide audio needs the audio_vae input")

    waveform = audio["waveform"]
    sample_rate = int(audio["sample_rate"])
    if not isinstance(waveform, torch.Tensor):
        raise TypeError("AUDIO waveform must be a torch.Tensor")

    target_samples = max(0, round(int(target_frames) * sample_rate / int(fps)))
    effective_waveform = waveform[..., : min(int(waveform.shape[-1]), target_samples)]
    source_audio = {
        "waveform": effective_waveform,
        "sample_rate": sample_rate,
    }

    resolved_rate = int(getattr(audio_vae, "audio_sample_rate", 32000))
    resampled = effective_waveform
    if sample_rate != resolved_rate:
        import torchaudio

        resampled = torchaudio.functional.resample(
            effective_waveform,
            sample_rate,
            resolved_rate,
        )

    contract = {
        "driving_audio_contract_version": DRIVING_AUDIO_CONTRACT_VERSION,
        "source_sample_rate": sample_rate,
        "source_shape": list(effective_waveform.shape),
        "source_dtype": str(effective_waveform.dtype),
        "source_sha256": _tensor_sha256(effective_waveform),
        "resolved_vae_sample_rate": resolved_rate,
        "resampled_shape": list(resampled.shape),
        "resampled_dtype": str(resampled.dtype),
        "resampled_sha256": _tensor_sha256(resampled),
        "preprocess_version": DRIVING_AUDIO_PREPROCESS_VERSION,
    }
    return DrivingAudioSource(
        source_audio=source_audio,
        resampled_waveform=resampled,
        resolved_vae_sample_rate=resolved_rate,
        contract=contract,
        combined_hash=_canonical_sha256(contract),
    )


def encode_driving_audio(
    source: DrivingAudioSource | None,
    audio_vae: Any,
) -> DrivingAudioAssets | None:
    if source is None:
        return None
    latent = audio_vae.encode(source.resampled_waveform[:1].movedim(1, -1))
    return DrivingAudioAssets(source=source, audio_latent=latent)


def slice_driving_audio_latent(
    assets: DrivingAudioAssets | None,
    *,
    cumulative_retained_before: int,
    total_frames: int,
    trim_frames: int,
    fps: int,
) -> torch.Tensor | None:
    if assets is None:
        return None
    source_start_frame = max(
        0,
        int(cumulative_retained_before) - int(trim_frames),
    )
    source_end_frame = source_start_frame + int(total_frames)
    latent_start = round(source_start_frame * H3_AUDIO_LATENT_FPS / int(fps))
    latent_end = round(source_end_frame * H3_AUDIO_LATENT_FPS / int(fps))
    latent_length = int(assets.audio_latent.shape[-1])
    latent_start = min(max(0, latent_start), latent_length)
    latent_end = min(max(latent_start, latent_end), latent_length)
    if latent_end <= latent_start:
        return None
    return assets.audio_latent[..., latent_start:latent_end].clone()


def combine_driving_audio_identity(
    visual_identity_hash: str,
    source: DrivingAudioSource | None,
) -> str:
    if source is None:
        return visual_identity_hash
    return _canonical_sha256(
        {
            "driving_audio_identity_version": 1,
            "visual_identity_hash": visual_identity_hash,
            "driving_audio_hash": source.combined_hash,
        }
    )


def attach_driving_audio(
    conditioning: list,
    audio_latent: torch.Tensor | None,
) -> list:
    """Attach a Core-compatible guide-audio keyframe without tokenizer refs."""
    if audio_latent is None:
        return conditioning
    output = []
    for tokens, metadata in conditioning:
        copied = dict(metadata)
        keyframes = list(copied.get("minimax_keyframes", []))
        keyframes.append(
            {
                "resolved_frame_index": 0,
                "audio_latent": audio_latent,
            }
        )
        copied["minimax_keyframes"] = keyframes
        output.append([tokens, copied])
    return output
