"""MiniMax H3 standalone audio-reference adapter for the V3 sampler."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any

import torch


REFERENCE_AUDIO_CONTRACT_VERSION = 1
REFERENCE_AUDIO_PREPROCESS_VERSION = 1
_AUDIO_TAG = re.compile(r"<Audio\s+(\d+)>")


class ReferenceAudioError(ValueError):
    pass


@dataclass(frozen=True)
class ReferenceAudioSource:
    waveform: torch.Tensor
    source_sample_rate: int
    source_shape: tuple[int, ...]
    source_dtype: str
    source_sha256: str
    resolved_vae_sample_rate: int
    resampled_shape: tuple[int, ...]
    resampled_dtype: str
    resampled_sha256: str
    combined_hash: str

    @property
    def contract(self) -> dict[str, Any]:
        return {
            "reference_audio_contract_version": REFERENCE_AUDIO_CONTRACT_VERSION,
            "source_sample_rate": self.source_sample_rate,
            "source_shape": list(self.source_shape),
            "source_dtype": self.source_dtype,
            "source_sha256": self.source_sha256,
            "resolved_vae_sample_rate": self.resolved_vae_sample_rate,
            "resampled_shape": list(self.resampled_shape),
            "resampled_dtype": self.resampled_dtype,
            "resampled_sha256": self.resampled_sha256,
            "preprocess_version": REFERENCE_AUDIO_PREPROCESS_VERSION,
            "combined_hash": self.combined_hash,
        }


@dataclass(frozen=True)
class ReferenceAudioAssets:
    source: ReferenceAudioSource
    audio_latent: torch.Tensor

    @property
    def combined_hash(self) -> str:
        return self.source.combined_hash


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _tensor_hash(value: torch.Tensor) -> str:
    tensor = value.detach().to(device="cpu").contiguous()
    digest = hashlib.sha256()
    digest.update(str(tuple(int(v) for v in tensor.shape)).encode("ascii"))
    digest.update(str(tensor.dtype).encode("ascii"))
    digest.update(tensor.view(torch.uint8).numpy().tobytes(order="C"))
    return digest.hexdigest()


def _validate_waveform(name: str, waveform: Any) -> torch.Tensor:
    if not torch.is_tensor(waveform) or waveform.ndim != 3:
        raise ReferenceAudioError(f"{name} waveform must have shape [B, C, L]")
    if int(waveform.shape[0]) != 1:
        raise ReferenceAudioError(f"{name} waveform batch size must be exactly 1")
    if int(waveform.shape[1]) < 1 or int(waveform.shape[2]) < 1:
        raise ReferenceAudioError(f"{name} waveform must contain channels and samples")
    if not waveform.is_floating_point():
        raise ReferenceAudioError(f"{name} waveform must use a floating-point dtype")
    if not bool(torch.isfinite(waveform).all().item()):
        raise ReferenceAudioError(f"{name} waveform contains NaN or infinity")
    return waveform.detach().to(device="cpu").contiguous()


def prepare_reference_audio_source(
    reference_audio_1: Any,
    reference_audio_vae: Any,
) -> ReferenceAudioSource | None:
    if reference_audio_1 is None:
        return None
    if reference_audio_vae is None:
        raise ReferenceAudioError(
            "reference_audio_vae is required when reference_audio_1 is connected"
        )
    if not isinstance(reference_audio_1, dict):
        raise ReferenceAudioError("Reference Audio 1 must be a ComfyUI AUDIO value")
    waveform = _validate_waveform(
        "Reference Audio 1", reference_audio_1.get("waveform")
    )
    sample_rate_value = reference_audio_1.get("sample_rate")
    if isinstance(sample_rate_value, bool):
        raise ReferenceAudioError("Reference Audio 1 sample_rate must be positive")
    try:
        source_sample_rate = int(sample_rate_value)
    except (TypeError, ValueError) as exc:
        raise ReferenceAudioError(
            "Reference Audio 1 sample_rate must be positive"
        ) from exc
    if source_sample_rate <= 0:
        raise ReferenceAudioError("Reference Audio 1 sample_rate must be positive")
    resolved_rate = int(getattr(reference_audio_vae, "audio_sample_rate", 32000))
    if resolved_rate <= 0:
        raise ReferenceAudioError("Reference Audio VAE sample rate must be positive")
    resampled = waveform
    if source_sample_rate != resolved_rate:
        try:
            import torchaudio

            resampled = torchaudio.functional.resample(
                waveform, source_sample_rate, resolved_rate
            ).contiguous()
        except Exception as exc:
            raise ReferenceAudioError(
                "Reference Audio 1 could not be resampled for the Audio VAE"
            ) from exc
    if not bool(torch.isfinite(resampled).all().item()):
        raise ReferenceAudioError(
            "Reference Audio 1 contains NaN or infinity after resampling"
        )
    source_shape = tuple(int(value) for value in waveform.shape)
    resampled_shape = tuple(int(value) for value in resampled.shape)
    source_sha256 = _tensor_hash(waveform)
    resampled_sha256 = _tensor_hash(resampled)
    contract_base = {
        "reference_audio_contract_version": REFERENCE_AUDIO_CONTRACT_VERSION,
        "source_sample_rate": source_sample_rate,
        "source_shape": list(source_shape),
        "source_dtype": str(waveform.dtype),
        "source_sha256": source_sha256,
        "resolved_vae_sample_rate": resolved_rate,
        "resampled_shape": list(resampled_shape),
        "resampled_dtype": str(resampled.dtype),
        "resampled_sha256": resampled_sha256,
        "preprocess_version": REFERENCE_AUDIO_PREPROCESS_VERSION,
    }
    return ReferenceAudioSource(
        waveform=resampled,
        source_sample_rate=source_sample_rate,
        source_shape=source_shape,
        source_dtype=str(waveform.dtype),
        source_sha256=source_sha256,
        resolved_vae_sample_rate=resolved_rate,
        resampled_shape=resampled_shape,
        resampled_dtype=str(resampled.dtype),
        resampled_sha256=resampled_sha256,
        combined_hash=_canonical_hash(contract_base),
    )


def encode_reference_audio(
    reference_audio_vae: Any,
    source: ReferenceAudioSource,
) -> ReferenceAudioAssets:
    try:
        latent = reference_audio_vae.encode(source.waveform.movedim(1, -1))
    except Exception as exc:
        raise ReferenceAudioError("Reference Audio VAE Encode failed") from exc
    if (
        not torch.is_tensor(latent)
        or latent.ndim != 4
        or int(latent.shape[0]) != 1
        or int(latent.shape[1]) != 32
        or int(latent.shape[2]) != 2
        or int(latent.shape[3]) < 1
    ):
        raise ReferenceAudioError(
            "Reference Audio VAE must produce latent shape [1, 32, 2, T]"
        )
    if not bool(torch.isfinite(latent).all().item()):
        raise ReferenceAudioError("Reference Audio latent contains NaN or infinity")
    return ReferenceAudioAssets(source=source, audio_latent=latent)


def validate_reference_audio_prompts(
    prompts: list[str], source: ReferenceAudioSource | None
) -> str:
    found: set[int] = set()
    for prompt in prompts:
        found.update(int(value) for value in _AUDIO_TAG.findall(str(prompt)))
    warnings: list[str] = []
    active_count = 1 if source is not None else 0
    unavailable = sorted(
        value for value in found if source is None or value != 1
    )
    for value in unavailable:
        warnings.append(
            f"H3C-P102 Warning: prompt references unavailable <Audio {value}>; only "
            f"{active_count} active reference audio item(s) reached the Sampler. "
            "Core-compatible generation will continue; the tag may be ignored "
            "or hallucinated."
        )
    if source is not None and 1 not in found:
        warnings.append(
            "H3C-P103 Warning: Reference Audio 1 is connected but the prompt contains no <Audio 1> "
            "tag; audio still conditions generation, but an explicit tag is recommended."
        )
    return "\n".join(warnings)


def combine_reference_audio_identity(
    visual_identity_hash: str,
    source: ReferenceAudioSource | None,
) -> str:
    if source is None:
        return str(visual_identity_hash)
    return _canonical_hash(
        {
            "reference_audio_identity_version": 1,
            "visual_identity_hash": str(visual_identity_hash),
            "reference_audio_hash": source.combined_hash,
        }
    )


def reference_audio_item() -> dict[str, str]:
    return {"type": "audio"}


def reference_audio_block(assets: ReferenceAudioAssets) -> dict[str, Any]:
    return {
        "kind": "audio",
        "ref_audio_t": int(assets.audio_latent.shape[-1]),
        "audio_latent": assets.audio_latent,
    }
