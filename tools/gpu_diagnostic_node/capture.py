"""Deterministic tensor capture and comparison helpers for the GPU runner."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any

import torch


STAGE_ORDER = (
    "A_pre_sampler",
    "B_first_model_call",
    "C_physical_sample",
    "D_split_recombine",
    "E1_decode_243",
    "E2_final_240",
)


def _dense_cpu(tensor: torch.Tensor) -> torch.Tensor:
    return tensor.detach().to("cpu").contiguous()


def _raw_sha256(tensor: torch.Tensor) -> str:
    value = _dense_cpu(tensor)
    raw = value.view(torch.uint8).numpy().tobytes()
    return sha256(raw).hexdigest()


def tensor_fingerprint(tensor: torch.Tensor) -> dict[str, Any]:
    value = _dense_cpu(tensor)
    return {
        "shape": list(value.shape),
        "dtype": str(value.dtype),
        "sha256": _raw_sha256(value),
        "numel": int(value.numel()),
    }


@dataclass(frozen=True)
class TensorDifference:
    comparable: bool
    bit_exact: bool
    allclose: bool
    max_abs_diff: float | None
    mean_abs_diff: float | None
    reason: str | None = None

    @property
    def matches(self) -> bool:
        return self.comparable and (self.bit_exact or self.allclose)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["matches"] = self.matches
        return value


def compare_tensors(
    left: torch.Tensor,
    right: torch.Tensor,
    *,
    rtol: float = 1.0e-4,
    atol: float = 1.0e-5,
) -> TensorDifference:
    a = _dense_cpu(left)
    b = _dense_cpu(right)
    if tuple(a.shape) != tuple(b.shape):
        return TensorDifference(False, False, False, None, None, "shape mismatch")
    if a.dtype != b.dtype:
        return TensorDifference(False, False, False, None, None, "dtype mismatch")
    bit_exact = bool(torch.equal(a, b))
    if not (a.is_floating_point() or a.is_complex()):
        return TensorDifference(True, bit_exact, bit_exact, 0.0 if bit_exact else None, 0.0 if bit_exact else None)
    af = a.to(torch.float64)
    bf = b.to(torch.float64)
    delta = (af - bf).abs()
    max_abs = float(delta.max().item()) if delta.numel() else 0.0
    mean_abs = float(delta.mean().item()) if delta.numel() else 0.0
    close = bool(torch.allclose(af, bf, rtol=rtol, atol=atol, equal_nan=True))
    return TensorDifference(True, bit_exact, close, max_abs, mean_abs)


def _safe_tensor_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "tensor"


def _is_primitive(value: Any) -> bool:
    return value is None or isinstance(value, (bool, int, float, str))


def _primitive_sequence(value: Any) -> bool:
    return isinstance(value, (list, tuple)) and all(_is_primitive(item) for item in value)


class DiagnosticCapture:
    def __init__(self, side: str):
        self.side = side
        self.manifest: dict[str, Any] = {
            "format": "h3-core-continuum-gpu-diagnostic-v1",
            "side": side,
            "stages": {},
        }
        self.tensors: dict[str, torch.Tensor] = {}
        self.runtime: dict[str, Any] = {}

    def _stage(self, stage: str) -> dict[str, Any]:
        return self.manifest["stages"].setdefault(stage, {"values": {}, "tensors": {}})

    def add_value(self, stage: str, field: str, value: Any) -> None:
        if not (_is_primitive(value) or _primitive_sequence(value)):
            value = json.loads(json.dumps(value, default=str))
        self._stage(stage)["values"][field] = value

    def add_tensor(self, stage: str, field: str, tensor: torch.Tensor, *, persist: bool = True) -> None:
        if not torch.is_tensor(tensor):
            raise TypeError(f"{field} is not a tensor")
        if getattr(tensor, "is_nested", False):
            parts = list(tensor.unbind())
            self.add_value(stage, f"{field}.components", len(parts))
            for index, part in enumerate(parts):
                self.add_tensor(stage, f"{field}.component_{index}", part, persist=persist)
            return
        value = _dense_cpu(tensor)
        key = _safe_tensor_key(f"{stage}.{field}")
        self._stage(stage)["tensors"][field] = {
            **tensor_fingerprint(value),
            "stored_as": key if persist else None,
        }
        if persist:
            self.tensors[key] = value.clone()

    def capture_value(
        self,
        stage: str,
        field: str,
        value: Any,
        *,
        persist_tensors: bool = True,
        depth: int = 0,
    ) -> None:
        if depth > 7:
            self.add_value(stage, f"{field}.truncated", True)
            return
        if torch.is_tensor(value):
            self.add_tensor(stage, field, value, persist=persist_tensors)
            return
        if _is_primitive(value):
            self.add_value(stage, field, value)
            return
        if _primitive_sequence(value):
            self.add_value(stage, field, list(value))
            return
        if isinstance(value, Mapping):
            keys = sorted(str(key) for key in value.keys())
            self.add_value(stage, f"{field}.keys", keys)
            for key in keys[:256]:
                try:
                    child = value[key]
                except (KeyError, TypeError):
                    child = next((item for raw, item in value.items() if str(raw) == key), None)
                self.capture_value(
                    stage,
                    f"{field}.{key}",
                    child,
                    persist_tensors=persist_tensors,
                    depth=depth + 1,
                )
            return
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            self.add_value(stage, f"{field}.length", len(value))
            for index, child in enumerate(value[:256]):
                self.capture_value(
                    stage,
                    f"{field}.{index}",
                    child,
                    persist_tensors=persist_tensors,
                    depth=depth + 1,
                )
            return
        if hasattr(value, "unbind") and value.__class__.__name__ == "NestedTensor":
            parts = list(value.unbind())
            self.add_value(stage, f"{field}.components", len(parts))
            for index, child in enumerate(parts):
                label = ("video", "audio")[index] if index < 2 else f"component_{index}"
                self.capture_value(
                    stage,
                    f"{field}.{label}",
                    child,
                    persist_tensors=persist_tensors,
                    depth=depth + 1,
                )
            return
        if all(hasattr(value, name) for name in ("signature", "segments", "position_ids")):
            self.add_value(stage, f"{field}.type", value.__class__.__name__)
            self.add_value(stage, f"{field}.signature", list(value.signature))
            self.add_value(stage, f"{field}.segments", [list(item) for item in value.segments])
            for name in ("position_ids", "img_pos", "img_update", "audio_pos", "audio_update"):
                child = getattr(value, name, None)
                if torch.is_tensor(child):
                    self.add_tensor(stage, f"{field}.{name}", child, persist=persist_tensors)
            return
        self.add_value(stage, f"{field}.type", value.__class__.__name__)

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        from safetensors.torch import save_file

        save_file(self.tensors, str(directory / "tensors.safetensors"))
        (directory / "manifest.json").write_text(
            json.dumps(self.manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


def compare_stage(
    left: DiagnosticCapture,
    right: DiagnosticCapture,
    stage: str,
) -> dict[str, Any]:
    a = left.manifest["stages"].get(stage, {"values": {}, "tensors": {}})
    b = right.manifest["stages"].get(stage, {"values": {}, "tensors": {}})
    details: dict[str, Any] = {}
    first_field: str | None = None

    value_fields = list(a["values"].keys()) + [key for key in b["values"] if key not in a["values"]]
    for field in value_fields:
        av = a["values"].get(field, {"missing": True})
        bv = b["values"].get(field, {"missing": True})
        matches = av == bv
        details[field] = {"kind": "value", "matches": matches, "left": av, "right": bv}
        if not matches and first_field is None:
            first_field = field

    tensor_fields = list(a["tensors"].keys()) + [key for key in b["tensors"] if key not in a["tensors"]]
    for field in tensor_fields:
        a_meta = a["tensors"].get(field)
        b_meta = b["tensors"].get(field)
        if a_meta is None or b_meta is None:
            result = {"kind": "tensor", "matches": False, "reason": "missing tensor"}
        else:
            a_key = a_meta.get("stored_as")
            b_key = b_meta.get("stored_as")
            if a_key in left.tensors and b_key in right.tensors:
                result = {"kind": "tensor", **compare_tensors(left.tensors[a_key], right.tensors[b_key]).to_dict()}
            else:
                matches = a_meta == b_meta
                result = {"kind": "fingerprint", "matches": matches, "left": a_meta, "right": b_meta}
        details[field] = result
        if not result["matches"] and first_field is None:
            first_field = field

    return {
        "status": "MATCH" if first_field is None else "DIFFER",
        "first_field": first_field,
        "fields": details,
    }


def recombine_terminal_streams(
    first: torch.Tensor,
    second: torch.Tensor,
    *,
    first_range: tuple[int, int] | list[int],
    second_range: tuple[int, int] | list[int],
    dim: int,
) -> torch.Tensor:
    first_start, first_stop = (int(value) for value in first_range)
    second_start, second_stop = (int(value) for value in second_range)
    overlap = first_stop - second_start
    if first_start != 0 or overlap < 0:
        raise ValueError("terminal split ranges do not form an overlapping sequence")
    if first.shape[dim] != first_stop - first_start:
        raise ValueError("first logical stream length does not match its range")
    if second.shape[dim] != second_stop - second_start:
        raise ValueError("second logical stream length does not match its range")
    if overlap > second.shape[dim]:
        raise ValueError("terminal overlap exceeds the second logical stream")
    slices = [slice(None)] * second.ndim
    slices[dim] = slice(overlap, None)
    return torch.cat((first, second[tuple(slices)]), dim=dim).contiguous()


def format_comparison(comparison: Mapping[str, Any], output_directory: Path) -> str:
    lines = []
    first_divergence = None
    for stage in STAGE_ORDER:
        result = comparison.get(stage, {"status": "NOT_RUN", "first_field": None})
        lines.append(f"{stage}: {result['status']}")
        if first_divergence is None and result["status"] == "DIFFER":
            field = result.get("first_field")
            first_divergence = f"{stage}.{field}" if field else stage
    lines.append("")
    lines.append(f"First divergence: {first_divergence or 'none'}")
    lines.append(f"Output: {output_directory}")
    return "\n".join(lines)
