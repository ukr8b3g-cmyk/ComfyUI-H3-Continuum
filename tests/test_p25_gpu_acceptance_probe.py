import importlib.util
import os
from pathlib import Path

import pytest
import torch


def _probe_module():
    path = Path(__file__).resolve().parents[1] / "tools" / "p25_gpu_acceptance_probe.py"
    spec = importlib.util.spec_from_file_location("p25_gpu_acceptance_probe_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_p25_bounded_finite_check_and_hash_are_deterministic():
    probe = _probe_module()
    value = torch.arange(48, dtype=torch.float32).reshape(4, 3, 4)

    assert probe._tensor_is_finite_batched(value, batch=1) is True
    assert probe._hash_tensor(value, batch=1) == probe._hash_tensor(value, batch=3)

    invalid = value.clone()
    invalid[2, 1, 1] = float("nan")
    assert probe._tensor_is_finite_batched(invalid, batch=1) is False


def test_p25_stress_prompt_bypasses_vae_and_preserves_assembler_contract():
    probe = _probe_module()
    prompt = probe._prompt("Disk-backed", stress=True)

    assert set(prompt) == {"1", "6", "7"}
    assert prompt["1"]["class_type"] == "P25SyntheticDecodedStressFixture"
    assert prompt["6"]["class_type"] == "H3ContinuumAssembleSeamV35"
    assert prompt["6"]["inputs"]["images"] == ["1", 0]
    assert prompt["6"]["inputs"]["audio"] == ["1", 1]
    assert prompt["6"]["inputs"]["assembly_plan"] == ["1", 2]
    assert prompt["6"]["inputs"]["buffer_backend"] == "Disk-backed"
    assert prompt["6"]["inputs"]["exact_total_duration"] is True
    assert prompt["6"]["inputs"]["video_seam"] == "Auto"


def test_p25_process_memory_snapshot_reports_portable_fields():
    probe = _probe_module()
    snapshot = probe._process_memory_snapshot()

    assert snapshot["rss"] > 0
    if "uss" in snapshot:
        assert snapshot["uss"] > 0


@pytest.mark.skipif(os.name != "nt", reason="Windows private commit field")
def test_p25_process_memory_snapshot_reports_windows_commit_field():
    probe = _probe_module()
    snapshot = probe._process_memory_snapshot()

    assert snapshot["private"] > 0
