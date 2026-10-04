"""MiniMax H3 standalone audio-reference adapter for the V3 sampler."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any

import torch

from .audio_compat import resample_audio


REFERENCE_AUDIO_CONTRACT_VERSION = 1
REFERENCE_AUDIO_PREPROCESS_VERSION = 1
REFERENCE_AUDIO_BUNDLE_CONTRACT_VERSION = 1
REFERENCE_AUDIOS_TYPE = "H3_CONTINUUM_AUDIO_REFERENCES"
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


@dataclass(frozen=True)
class ReferenceAudioBundle:
    """Ordered Reference Audio sources plus their shared Core Audio VAE."""

    sources: tuple[ReferenceAudioSource, ...]
    reference_audio_vae: Any
    combined_hash: str

    @property
    def count(self) -> int:
        return len(self.sources)

    @property
    def contract(self) -> dict[str, Any]:
        return {
            "reference_audio_bundle_contract_version": (
                REFERENCE_AUDIO_BUNDLE_CONTRACT_VERSION
            ),
            "count": self.count,
            "items": [
                {
                    "audio_index": index,
                    "reference_audio": source.contract,
                }
                for index, source in enumerate(self.sources, start=1)
            ],
            "combined_hash": self.combined_hash,
        }


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


def _prepare_reference_audio_source(
    reference_audio: Any,
    reference_audio_vae: Any,
    *,
    name: str,
) -> ReferenceAudioSource | None:
    if reference_audio is None:
        return None
    if reference_audio_vae is None:
        raise ReferenceAudioError(
            "reference_audio_vae is required when reference audio is connected"
        )
    if not isinstance(reference_audio, dict):
        raise ReferenceAudioError(f"{name} must be a ComfyUI AUDIO value")
    waveform = _validate_waveform(name, reference_audio.get("waveform"))
    sample_rate_value = reference_audio.get("sample_rate")
    if isinstance(sample_rate_value, bool):
        raise ReferenceAudioError(f"{name} sample_rate must be positive")
    try:
        source_sample_rate = int(sample_rate_value)
    except (TypeError, ValueError) as exc:
        raise ReferenceAudioError(f"{name} sample_rate must be positive") from exc
    if source_sample_rate <= 0:
        raise ReferenceAudioError(f"{name} sample_rate must be positive")
    resolved_rate = int(getattr(reference_audio_vae, "audio_sample_rate", 32000))
    if resolved_rate <= 0:
        raise ReferenceAudioError("Reference Audio VAE sample rate must be positive")
    resampled = waveform
    if source_sample_rate != resolved_rate:
        try:
            resampled = resample_audio(
                waveform, source_sample_rate, resolved_rate
            ).contiguous()
        except Exception as exc:
            raise ReferenceAudioError(
                f"{name} could not be resampled for the Audio VAE"
            ) from exc
    if not bool(torch.isfinite(resampled).all().item()):
        raise ReferenceAudioError(
            f"{name} contains NaN or infinity after resampling"
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


def prepare_reference_audio_source(
    reference_audio_1: Any,
    reference_audio_vae: Any,
) -> ReferenceAudioSource | None:
    """Prepare the unchanged legacy single-Reference-Audio path."""

    if reference_audio_1 is None:
        return None
    if reference_audio_vae is None:
        # Preserve the established user-facing legacy validation text exactly.
        raise ReferenceAudioError(
            "reference_audio_vae is required when reference_audio_1 is connected"
        )
    return _prepare_reference_audio_source(
        reference_audio_1,
        reference_audio_vae,
        name="Reference Audio 1",
    )


def prepare_reference_audio_bundle(
    reference_audio_1: Any,
    reference_audio_2: Any,
    reference_audio_3: Any,
    reference_audio_vae: Any,
) -> ReferenceAudioBundle | None:
    """Prepare up to three ordered Core-native standalone audio references."""

    values = (reference_audio_1, reference_audio_2, reference_audio_3)
    connected = tuple(value is not None for value in values)
    if not any(connected):
        return None
    first_gap = next((index for index, present in enumerate(connected) if not present), 3)
    if any(connected[first_gap + 1 :]):
        raise ReferenceAudioError(
            "Reference Audio inputs must be connected in order without gaps so "
            "<Audio 1>, <Audio 2>, and <Audio 3> keep their exact Core numbering"
        )
    sources = tuple(
        _prepare_reference_audio_source(
            value,
            reference_audio_vae,
            name=f"Reference Audio {index}",
        )
        for index, value in enumerate(values, start=1)
        if value is not None
    )
    contract_base = {
        "reference_audio_bundle_contract_version": (
            REFERENCE_AUDIO_BUNDLE_CONTRACT_VERSION
        ),
        "count": len(sources),
        "items": [
            {
                "audio_index": index,
                "reference_audio": source.contract,
            }
            for index, source in enumerate(sources, start=1)
        ],
    }
    return ReferenceAudioBundle(
        sources=sources,
        reference_audio_vae=reference_audio_vae,
        combined_hash=_canonical_hash(contract_base),
    )


def resolve_reference_audio_input(
    reference_audio_1: Any,
    reference_audio_vae: Any,
    audio_references: Any,
) -> tuple[ReferenceAudioSource | ReferenceAudioBundle | None, Any]:
    """Resolve legacy or bundled input without silently mixing contracts."""

    if audio_references is not None:
        if not isinstance(audio_references, ReferenceAudioBundle):
            raise ReferenceAudioError(
                "Audio References must come from H3 Continuum Reference Audios"
            )
        if reference_audio_1 is not None:
            raise ReferenceAudioError(
                "Use either legacy Reference Audio or Audio References, not both"
            )
        return audio_references, audio_references.reference_audio_vae
    return (
        prepare_reference_audio_source(reference_audio_1, reference_audio_vae),
        reference_audio_vae,
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


def encode_reference_audio_cached(
    reference_audio_vae: Any,
    source: ReferenceAudioSource,
    *,
    cache_event=None,
) -> ReferenceAudioAssets:
    """Cache Reference Audio only when its established output is already CPU."""

    from .v3.ref_encode_cache import (
        get_ref_encode_cache,
        make_ref_encode_cache_key,
    )

    cache = get_ref_encode_cache()
    key = make_ref_encode_cache_key(
        "reference_audio",
        REFERENCE_AUDIO_PREPROCESS_VERSION,
        source.combined_hash,
    )
    latent = cache.lookup(reference_audio_vae, key, event_sink=cache_event)
    if latent is not None:
        return ReferenceAudioAssets(source=source, audio_latent=latent)
    assets = encode_reference_audio(reference_audio_vae, source)
    if cache.supports_vae(reference_audio_vae):
        cache.store(
            reference_audio_vae,
            key,
            assets.audio_latent,
            event_sink=cache_event,
        )
    return assets


def encode_reference_audio_input(
    reference_audio_vae: Any,
    source: ReferenceAudioSource | ReferenceAudioBundle,
    *,
    cache_enabled: bool,
    cache_event=None,
) -> ReferenceAudioAssets | tuple[ReferenceAudioAssets, ...]:
    """Encode one legacy source or each ordered bundle source independently."""

    encoder = encode_reference_audio_cached if cache_enabled else encode_reference_audio
    if isinstance(source, ReferenceAudioBundle):
        if cache_enabled:
            return tuple(
                encoder(reference_audio_vae, item, cache_event=cache_event)
                for item in source.sources
            )
        return tuple(encoder(reference_audio_vae, item) for item in source.sources)
    if cache_enabled:
        return encoder(reference_audio_vae, source, cache_event=cache_event)
    return encoder(reference_audio_vae, source)


def validate_reference_audio_prompts(
    prompts: list[str], source: ReferenceAudioSource | ReferenceAudioBundle | None
) -> str:
    found: set[int] = set()
    for prompt in prompts:
        found.update(int(value) for value in _AUDIO_TAG.findall(str(prompt)))
    warnings: list[str] = []
    active_count = source.count if isinstance(source, ReferenceAudioBundle) else int(source is not None)
    unavailable = sorted(
        value for value in found if not 1 <= value <= active_count
    )
    for value in unavailable:
        warnings.append(
            f"H3C-P102 Warning: prompt references unavailable <Audio {value}>; only "
            f"{active_count} active reference audio item(s) reached the Sampler. "
            "Core-compatible generation will continue; the tag may be ignored "
            "or hallucinated."
        )
    for value in range(1, active_count + 1):
        if value not in found:
            warnings.append(
                f"H3C-P103 Warning: Reference Audio {value} is connected but the prompt "
                f"contains no <Audio {value}> tag; audio still conditions generation, "
                "but an explicit tag is recommended."
            )
    return "\n".join(warnings)


def combine_reference_audio_identity(
    visual_identity_hash: str,
    source: ReferenceAudioSource | ReferenceAudioBundle | None,
) -> str:
    if source is None:
        return str(visual_identity_hash)
    if isinstance(source, ReferenceAudioBundle):
        return _canonical_hash(
            {
                "reference_audio_identity_version": 2,
                "visual_identity_hash": str(visual_identity_hash),
                "ordered_reference_audio_hashes": [
                    item.combined_hash for item in source.sources
                ],
            }
        )
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


def reference_audio_asset_items(
    assets: ReferenceAudioAssets | tuple[ReferenceAudioAssets, ...],
) -> tuple[ReferenceAudioAssets, ...]:
    if isinstance(assets, tuple):
        return assets
    return (assets,)


class H3ContinuumReferenceAudios:
    """Compact public helper for one to three ordered H3 Reference Audios."""

    DEPRECATED = False
    CATEGORY = "MiniMax H3/Continuum/Input"
    DESCRIPTION = (
        "Bundle up to three ordered standalone Reference Audios for the V3.8 "
        "sampler. Connected inputs map directly to <Audio 1>, <Audio 2>, and "
        "<Audio 3>; generated final audio is never replaced."
    )
    SEARCH_ALIASES = [
        "H3 Continuum Reference Audios",
        "MiniMax H3 multiple reference audio",
    ]

    @classmethod
    def INPUT_TYPES(cls):
        audio_tooltip = (
            "Optional standalone voice or sound reference. Connect inputs in order "
            "without gaps; their order maps to the matching <Audio N> prompt tags."
        )
        return {
            "optional": {
                "reference_audio_1": (
                    "AUDIO",
                    {"display_name": "Reference Audio 1 (Optional)", "tooltip": audio_tooltip},
                ),
                "reference_audio_2": (
                    "AUDIO",
                    {"display_name": "Reference Audio 2 (Optional)", "tooltip": audio_tooltip},
                ),
                "reference_audio_3": (
                    "AUDIO",
                    {"display_name": "Reference Audio 3 (Optional)", "tooltip": audio_tooltip},
                ),
                "reference_audio_vae": (
                    "VAE",
                    {
                        "display_name": "Reference Audio VAE",
                        "tooltip": (
                            "Shared Core Audio VAE used to encode every connected "
                            "Reference Audio. Required when any audio is connected."
                        ),
                    },
                ),
            }
        }

    RETURN_TYPES = (REFERENCE_AUDIOS_TYPE,)
    RETURN_NAMES = ("audio_references",)
    FUNCTION = "pack"

    def pack(
        self,
        reference_audio_1=None,
        reference_audio_2=None,
        reference_audio_3=None,
        reference_audio_vae=None,
    ):
        return (
            prepare_reference_audio_bundle(
                reference_audio_1,
                reference_audio_2,
                reference_audio_3,
                reference_audio_vae,
            ),
        )
