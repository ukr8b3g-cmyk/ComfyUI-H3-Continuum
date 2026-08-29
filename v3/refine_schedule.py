"""Versioned, UI-independent sigma contracts for Continuum refinement.

The public Second Pass SIGMAS socket remains authoritative.  These helpers attach
meaning to that tensor without recreating it: External and Full retain the exact
input object, while Tail and Partial return views into the same source values.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

import torch


MAGIC = "H3_CONTINUUM_REFINE_SCHEDULE"
SCHEMA_VERSION = 1

MODE_EXTERNAL = "external"
MODE_FULL = "full"
MODE_TAIL = "tail"
MODE_PARTIAL = "partial"
MODES = (MODE_EXTERNAL, MODE_FULL, MODE_TAIL, MODE_PARTIAL)

NOISE_MODE_VIDEO_RANDOM_AUDIO_ZERO = "video_random_mask_1_audio_zero_mask_0"
AUDIO_POLICY_LOCKED_PASSTHROUGH = "locked_first_pass_bit_exact_passthrough"


class RefineScheduleError(ValueError):
    """Raised when a refinement schedule cannot safely describe its SIGMAS."""


@dataclass(frozen=True)
class RefineSchedule:
    """One validated effective SIGMAS tensor and its serializable identity."""

    sigmas: torch.Tensor
    contract: Mapping[str, Any]
    source_sigma_hash: str


def _validate_sigmas(sigmas: Any, *, name: str) -> torch.Tensor:
    if not torch.is_tensor(sigmas) or sigmas.ndim != 1 or sigmas.numel() < 2:
        raise RefineScheduleError(f"{name} must be a one-dimensional tensor with at least two values")
    detached = sigmas.detach()
    if not bool(torch.isfinite(detached.float()).all().item()):
        raise RefineScheduleError(f"{name} contains NaN or Inf")
    values = detached.float().to(device="cpu")
    if bool((values[1:] > values[:-1]).any().item()):
        raise RefineScheduleError(f"{name} must be monotonically non-increasing")
    return sigmas


def sigma_hash(sigmas: torch.Tensor) -> str:
    """Hash dtype, shape, and exact tensor bytes without changing the input."""

    _validate_sigmas(sigmas, name="sigmas")
    cpu = sigmas.detach().to(device="cpu").contiguous()
    payload = cpu.view(torch.uint8).numpy().tobytes()
    digest = hashlib.sha256()
    digest.update(str(cpu.dtype).encode("ascii"))
    digest.update(b"|")
    digest.update(str(tuple(int(value) for value in cpu.shape)).encode("ascii"))
    digest.update(b"|")
    digest.update(payload)
    return digest.hexdigest()


def _schedule_identity(contract: Mapping[str, Any]) -> str:
    payload = {
        key: value
        for key, value in contract.items()
        if key != "schedule_hash"
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _build_schedule(
    source_sigmas: torch.Tensor,
    *,
    mode: str,
    start_index: int,
    end_index: int,
) -> RefineSchedule:
    source = _validate_sigmas(source_sigmas, name="source_sigmas")
    canonical_mode = str(mode).lower()
    if canonical_mode not in MODES:
        raise RefineScheduleError(f"unsupported refine schedule mode {mode!r}")
    source_evaluations = int(source.numel()) - 1
    if type(start_index) is not int or type(end_index) is not int:
        raise RefineScheduleError("schedule indices must be integers")
    if start_index < 0 or end_index <= start_index or end_index > source_evaluations:
        raise RefineScheduleError(
            f"schedule range {start_index}:{end_index} is outside 0:{source_evaluations}"
        )

    if start_index == 0 and end_index == source_evaluations:
        effective = source
    else:
        effective = source[start_index : end_index + 1]
    _validate_sigmas(effective, name="effective sigmas")
    effective_hash = sigma_hash(effective)
    source_hash = sigma_hash(source)
    values = tuple(float(value) for value in effective.detach().to(device="cpu").tolist())
    contract: dict[str, Any] = {
        "magic": MAGIC,
        "schema_version": SCHEMA_VERSION,
        "mode": canonical_mode,
        "sigma_values": values,
        "sigma_hash": effective_hash,
        "source_sigma_hash": source_hash,
        "start_sigma": values[0],
        "end_sigma": values[-1],
        "evaluation_count": len(values) - 1,
        "source_evaluation_count": source_evaluations,
        "start_index": start_index,
        "end_index": end_index,
        "noise_mode": NOISE_MODE_VIDEO_RANDOM_AUDIO_ZERO,
        "audio_policy": AUDIO_POLICY_LOCKED_PASSTHROUGH,
    }
    contract["schedule_hash"] = _schedule_identity(contract)
    return RefineSchedule(
        sigmas=effective,
        contract=MappingProxyType(contract),
        source_sigma_hash=source_hash,
    )


def make_external_schedule(sigmas: torch.Tensor) -> RefineSchedule:
    evaluations = int(_validate_sigmas(sigmas, name="sigmas").numel()) - 1
    return _build_schedule(
        sigmas,
        mode=MODE_EXTERNAL,
        start_index=0,
        end_index=evaluations,
    )


def make_full_schedule(sigmas: torch.Tensor) -> RefineSchedule:
    evaluations = int(_validate_sigmas(sigmas, name="sigmas").numel()) - 1
    return _build_schedule(
        sigmas,
        mode=MODE_FULL,
        start_index=0,
        end_index=evaluations,
    )


def make_tail_schedule(
    sigmas: torch.Tensor,
    *,
    evaluation_count: int,
) -> RefineSchedule:
    source_evaluations = int(_validate_sigmas(sigmas, name="sigmas").numel()) - 1
    if type(evaluation_count) is not int or not 1 <= evaluation_count <= source_evaluations:
        raise RefineScheduleError(
            f"tail evaluation_count must be between 1 and {source_evaluations}"
        )
    return _build_schedule(
        sigmas,
        mode=MODE_TAIL,
        start_index=source_evaluations - evaluation_count,
        end_index=source_evaluations,
    )


def make_partial_schedule(
    sigmas: torch.Tensor,
    *,
    start_index: int,
    end_index: int,
) -> RefineSchedule:
    return _build_schedule(
        sigmas,
        mode=MODE_PARTIAL,
        start_index=start_index,
        end_index=end_index,
    )


def resolve_refine_schedule(
    sigmas: torch.Tensor,
    schedule: RefineSchedule | None = None,
) -> RefineSchedule:
    """Return External compatibility or validate an explicit internal schedule."""

    source = _validate_sigmas(sigmas, name="sigmas")
    if schedule is None:
        return make_external_schedule(source)
    if not isinstance(schedule, RefineSchedule):
        raise RefineScheduleError("refine_schedule must be a RefineSchedule")
    if sigma_hash(source) != schedule.source_sigma_hash:
        raise RefineScheduleError("refine_schedule was derived from different source SIGMAS")
    rebuilt = _build_schedule(
        source,
        mode=str(schedule.contract.get("mode", "")),
        start_index=int(schedule.contract.get("start_index", -1)),
        end_index=int(schedule.contract.get("end_index", -1)),
    )
    if rebuilt.contract["schedule_hash"] != schedule.contract.get("schedule_hash"):
        raise RefineScheduleError("refine_schedule contract identity is inconsistent")
    return schedule


def serializable_schedule_contract(schedule: RefineSchedule) -> dict[str, Any]:
    """Return a mutable JSON-safe copy for Assembly/diagnostic identity."""

    if not isinstance(schedule, RefineSchedule):
        raise RefineScheduleError("schedule must be a RefineSchedule")
    return dict(schedule.contract)
