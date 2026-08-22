from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import torch


MODULE_PATH = Path(__file__).parents[1] / "tools" / "gpu_diagnostic_node" / "capture.py"
SPEC = importlib.util.spec_from_file_location("h3_gpu_diagnostic_capture", MODULE_PATH)
capture = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = capture
SPEC.loader.exec_module(capture)


def test_tensor_fingerprint_is_deterministic():
    value = torch.arange(12, dtype=torch.float32).reshape(1, 3, 4)
    assert capture.tensor_fingerprint(value) == capture.tensor_fingerprint(value.clone())


def test_tensor_comparison_records_numerical_difference():
    left = torch.tensor([1.0, 2.0], dtype=torch.float32)
    right = torch.tensor([1.0, 2.000001], dtype=torch.float32)
    result = capture.compare_tensors(left, right)
    assert not result.bit_exact
    assert result.allclose
    assert result.matches
    assert result.max_abs_diff > 0.0


def test_terminal_video_recombine_is_bit_exact():
    physical = torch.arange(72, dtype=torch.float32).reshape(1, 1, 72, 1, 1)
    first = physical[:, :, 0:37]
    second = physical[:, :, 30:72]
    rebuilt = capture.recombine_terminal_streams(
        first,
        second,
        first_range=(0, 37),
        second_range=(30, 72),
        dim=2,
    )
    assert torch.equal(rebuilt, physical)


def test_terminal_audio_recombine_is_bit_exact():
    physical = torch.arange(405, dtype=torch.float32).reshape(1, 1, 405)
    first = physical[..., 0:207]
    second = physical[..., 170:405]
    rebuilt = capture.recombine_terminal_streams(
        first,
        second,
        first_range=(0, 207),
        second_range=(170, 405),
        dim=-1,
    )
    assert torch.equal(rebuilt, physical)


def test_stage_comparison_reports_first_field():
    left = capture.DiagnosticCapture("core")
    right = capture.DiagnosticCapture("continuum")
    left.add_value("A_pre_sampler", "seed", 42)
    right.add_value("A_pre_sampler", "seed", 43)
    left.add_tensor("A_pre_sampler", "sigmas", torch.ones(2))
    right.add_tensor("A_pre_sampler", "sigmas", torch.ones(2))
    result = capture.compare_stage(left, right, "A_pre_sampler")
    assert result["status"] == "DIFFER"
    assert result["first_field"] == "seed"


def test_summary_uses_stage_order_and_first_divergence(tmp_path):
    comparison = {
        "A_pre_sampler": {"status": "MATCH", "first_field": None},
        "B_first_model_call": {"status": "DIFFER", "first_field": "position_ids"},
    }
    text = capture.format_comparison(comparison, tmp_path)
    assert "A_pre_sampler: MATCH" in text
    assert "B_first_model_call: DIFFER" in text
    assert "First divergence: B_first_model_call.position_ids" in text
