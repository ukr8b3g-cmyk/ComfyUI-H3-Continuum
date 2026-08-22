"""Tests-only capture and comparison helpers for Terminal Merge diagnostics.

This module deliberately has no production imports or runtime hooks. Tests can
monkeypatch Core and Continuum boundaries, feed the captured values here, and
identify the first pipeline stage that differs without changing generation
semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

import torch


STAGE_ORDER = (
    "A_pre_sampler",
    "B_first_model_call",
    "C_sampled_physical_av",
    "D_split_recombine",
    "E_decode_assembly",
)


@dataclass(frozen=True)
class TensorFingerprint:
    shape: tuple[int, ...]
    dtype: str
    sha256: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "shape": list(self.shape),
            "dtype": self.dtype,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class TensorDifference:
    same_shape: bool
    same_dtype: bool
    bit_exact: bool
    allclose: bool
    max_abs_diff: float | None
    mean_abs_diff: float | None


@dataclass(frozen=True)
class StageSnapshot:
    name: str
    sha256: str
    payload: Any


@dataclass(frozen=True)
class StageComparison:
    name: str
    equal: bool
    core_sha256: str | None
    continuum_sha256: str | None
    missing_from: str | None = None


def _tensor_raw_bytes(tensor: torch.Tensor) -> bytes:
    value = tensor.detach().to("cpu").contiguous()
    if value.numel() == 0:
        return b""
    return value.reshape(-1).view(torch.uint8).numpy().tobytes()


def tensor_fingerprint(tensor: torch.Tensor) -> TensorFingerprint:
    if not torch.is_tensor(tensor):
        raise TypeError("tensor_fingerprint expects a torch.Tensor")
    return TensorFingerprint(
        shape=tuple(int(size) for size in tensor.shape),
        dtype=str(tensor.dtype),
        sha256=sha256(_tensor_raw_bytes(tensor)).hexdigest(),
    )


def tensor_difference(
    core: torch.Tensor,
    continuum: torch.Tensor,
    *,
    rtol: float = 1.0e-5,
    atol: float = 1.0e-6,
) -> TensorDifference:
    if not torch.is_tensor(core) or not torch.is_tensor(continuum):
        raise TypeError("tensor_difference expects two torch.Tensor values")

    same_shape = tuple(core.shape) == tuple(continuum.shape)
    same_dtype = core.dtype == continuum.dtype
    bit_exact = (
        same_shape
        and same_dtype
        and tensor_fingerprint(core).sha256 == tensor_fingerprint(continuum).sha256
    )
    if not same_shape:
        return TensorDifference(
            same_shape=False,
            same_dtype=same_dtype,
            bit_exact=False,
            allclose=False,
            max_abs_diff=None,
            mean_abs_diff=None,
        )

    core_value = core.detach().to("cpu")
    continuum_value = continuum.detach().to("cpu")
    if core_value.is_complex() or continuum_value.is_complex():
        core_numeric = core_value.to(torch.complex128)
        continuum_numeric = continuum_value.to(torch.complex128)
    else:
        core_numeric = core_value.to(torch.float64)
        continuum_numeric = continuum_value.to(torch.float64)

    if core_numeric.numel() == 0:
        max_abs_diff = 0.0
        mean_abs_diff = 0.0
    else:
        absolute = (core_numeric - continuum_numeric).abs()
        max_abs_diff = float(absolute.max().item())
        mean_abs_diff = float(absolute.mean().item())

    return TensorDifference(
        same_shape=True,
        same_dtype=same_dtype,
        bit_exact=bit_exact,
        allclose=bool(
            torch.allclose(
                core_numeric,
                continuum_numeric,
                rtol=rtol,
                atol=atol,
                equal_nan=True,
            )
        ),
        max_abs_diff=max_abs_diff,
        mean_abs_diff=mean_abs_diff,
    )


def packed_layout_snapshot(layout: Any) -> dict[str, Any]:
    return {
        "signature": stable_snapshot(getattr(layout, "signature", None)),
        "segments": stable_snapshot(getattr(layout, "segments", None)),
        "position_ids": stable_snapshot(getattr(layout, "position_ids", None)),
    }


def stable_snapshot(value: Any) -> Any:
    """Convert diagnostic data to deterministic JSON-compatible state."""

    if torch.is_tensor(value):
        return {"kind": "tensor", **tensor_fingerprint(value).as_dict()}
    if isinstance(value, TensorFingerprint):
        return {"kind": "tensor", **value.as_dict()}
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return {"kind": "float", "hex": value.hex()}
    if isinstance(value, bytes):
        return {
            "kind": "bytes",
            "length": len(value),
            "sha256": sha256(value).hexdigest(),
        }
    if isinstance(value, (Path, torch.device, torch.dtype)):
        return str(value)
    if isinstance(value, Enum):
        return {
            "kind": "enum",
            "type": f"{type(value).__module__}.{type(value).__qualname__}",
            "value": stable_snapshot(value.value),
        }
    if isinstance(value, slice):
        return {
            "kind": "slice",
            "start": value.start,
            "stop": value.stop,
            "step": value.step,
        }
    if isinstance(value, Mapping):
        return {
            "kind": "mapping",
            "items": [
                [str(key), stable_snapshot(item)]
                for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            ],
        }
    if isinstance(value, tuple):
        return {"kind": "tuple", "items": [stable_snapshot(item) for item in value]}
    if isinstance(value, list):
        return {"kind": "list", "items": [stable_snapshot(item) for item in value]}
    if isinstance(value, (set, frozenset)):
        items = [stable_snapshot(item) for item in value]
        items.sort(key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")))
        return {"kind": type(value).__name__, "items": items}
    if callable(value):
        return {
            "kind": "callable",
            "module": getattr(value, "__module__", type(value).__module__),
            "qualname": getattr(value, "__qualname__", type(value).__qualname__),
        }
    if all(hasattr(value, name) for name in ("signature", "segments", "position_ids")):
        return {"kind": "packed_layout", **packed_layout_snapshot(value)}
    if hasattr(value, "__dict__"):
        public_state = {
            key: item
            for key, item in vars(value).items()
            if not key.startswith("_") and not callable(item)
        }
        return {
            "kind": "object",
            "type": f"{type(value).__module__}.{type(value).__qualname__}",
            "state": stable_snapshot(public_state),
        }
    raise TypeError(f"Unsupported diagnostic value: {type(value)!r}")


def snapshot_sha256(payload: Any) -> str:
    normalized = stable_snapshot(payload)
    encoded = json.dumps(
        normalized,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


class DiagnosticCapture:
    def __init__(self) -> None:
        self._stages: dict[str, StageSnapshot] = {}

    @property
    def stages(self) -> Mapping[str, StageSnapshot]:
        return self._stages

    def capture(self, stage: str, **payload: Any) -> StageSnapshot:
        if stage not in STAGE_ORDER:
            raise ValueError(f"Unknown diagnostic stage: {stage}")
        if stage in self._stages:
            raise ValueError(f"Diagnostic stage already captured: {stage}")
        normalized = stable_snapshot(payload)
        snapshot = StageSnapshot(
            name=stage,
            sha256=snapshot_sha256(normalized),
            payload=normalized,
        )
        self._stages[stage] = snapshot
        return snapshot

    def capture_pre_sampler(
        self,
        *,
        physical_frames: int,
        seed: int,
        conditioning: Any,
        latent: Any,
        noise: torch.Tensor,
        keyframes: Any = None,
        qwen_images: Any = None,
        minimax_refs: Any = None,
    ) -> StageSnapshot:
        return self.capture(
            "A_pre_sampler",
            physical_frames=physical_frames,
            seed=seed,
            conditioning=conditioning,
            latent=latent,
            noise=noise,
            keyframes=keyframes,
            qwen_images=qwen_images,
            minimax_refs=minimax_refs,
        )

    def capture_first_model_call(
        self,
        *,
        minimax_payload: Any,
        transformer_options: Any,
    ) -> StageSnapshot:
        return self.capture(
            "B_first_model_call",
            minimax_payload=minimax_payload,
            transformer_options=transformer_options,
        )

    def capture_sampled_physical_av(
        self,
        *,
        video: torch.Tensor,
        audio: torch.Tensor,
    ) -> StageSnapshot:
        return self.capture(
            "C_sampled_physical_av",
            video=video,
            audio=audio,
        )

    def capture_split_recombine(
        self,
        *,
        physical_video: torch.Tensor,
        physical_audio: torch.Tensor,
        recombined_video: torch.Tensor,
        recombined_audio: torch.Tensor,
    ) -> StageSnapshot:
        return self.capture(
            "D_split_recombine",
            physical_video=physical_video,
            physical_audio=physical_audio,
            recombined_video=recombined_video,
            recombined_audio=recombined_audio,
            video_difference=tensor_difference(physical_video, recombined_video).__dict__,
            audio_difference=tensor_difference(physical_audio, recombined_audio).__dict__,
        )

    def capture_decode_assembly(
        self,
        *,
        physical_decoded: torch.Tensor,
        assembled_decoded: torch.Tensor,
    ) -> StageSnapshot:
        return self.capture(
            "E_decode_assembly",
            physical_decoded=physical_decoded,
            assembled_decoded=assembled_decoded,
            difference=tensor_difference(physical_decoded, assembled_decoded).__dict__,
        )


def compare_captures(
    core: DiagnosticCapture,
    continuum: DiagnosticCapture,
) -> tuple[StageComparison, ...]:
    comparisons = []
    for stage in STAGE_ORDER:
        core_stage = core.stages.get(stage)
        continuum_stage = continuum.stages.get(stage)
        missing = None
        if core_stage is None and continuum_stage is None:
            missing = "both"
        elif core_stage is None:
            missing = "core"
        elif continuum_stage is None:
            missing = "continuum"
        comparisons.append(
            StageComparison(
                name=stage,
                equal=(
                    core_stage is not None
                    and continuum_stage is not None
                    and core_stage.sha256 == continuum_stage.sha256
                ),
                core_sha256=None if core_stage is None else core_stage.sha256,
                continuum_sha256=None if continuum_stage is None else continuum_stage.sha256,
                missing_from=missing,
            )
        )
    return tuple(comparisons)


def first_divergent_stage(
    core: DiagnosticCapture,
    continuum: DiagnosticCapture,
) -> str | None:
    for comparison in compare_captures(core, continuum):
        if not comparison.equal:
            return comparison.name
    return None
