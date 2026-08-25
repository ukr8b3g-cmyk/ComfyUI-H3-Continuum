from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).parents[1] / "tools" / "p32_gpu_profile_probe.py"
SPEC = importlib.util.spec_from_file_location("h3_p32_profile_probe", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def _base_prompt():
    return {
        "1": {"class_type": "UNETLoader", "inputs": {}},
        "2": {
            "class_type": "MiniMaxH3MemoryEfficientSageAttentionPatch",
            "inputs": {"model": ["1", 0]},
        },
        "3": {
            "class_type": "SpectrumApplyMiniMaxH3",
            "inputs": {"model": ["2", 0], "enabled": False},
        },
        "4": {
            "class_type": "H3ContinuumSamplerV35",
            "inputs": {"model": ["3", 0], "base_seed": 1},
        },
        "5": {
            "class_type": "SaveVideo",
            "inputs": {"filename_prefix": "original", "video": ["4", 0]},
        },
    }


@pytest.mark.parametrize(
    ("profile", "spectrum_enabled", "has_sol"),
    (
        ("sage", False, False),
        ("sage_sol", False, True),
        ("sage_spectrum", True, False),
        ("sage_sol_spectrum", True, True),
    ),
)
def test_configure_profile_builds_exact_route(profile, spectrum_enabled, has_sol):
    source = _base_prompt()
    result = probe.configure_profile(source, profile)
    assert source["3"]["inputs"]["enabled"] is False
    assert result["3"]["inputs"]["enabled"] is spectrum_enabled
    sol_nodes = probe._find_nodes(result, "SolAttnPatch")
    assert bool(sol_nodes) is has_sol
    if has_sol:
        sol_id = sol_nodes[0]
        assert result[sol_id]["inputs"]["model"] == ["2", 0]
        assert result["3"]["inputs"]["model"] == [sol_id, 0]
        assert result[sol_id]["inputs"]["verbose"] is True
    else:
        assert result["3"]["inputs"]["model"] == ["2", 0]


def test_mutate_run_changes_only_seed_and_filename():
    source = _base_prompt()
    result = probe.mutate_run(source, seed=99, filename_prefix="p32/test")
    assert source["4"]["inputs"]["base_seed"] == 1
    assert source["5"]["inputs"]["filename_prefix"] == "original"
    assert result["4"]["inputs"]["base_seed"] == 99
    assert result["5"]["inputs"]["filename_prefix"] == "p32/test"


def test_summarize_runs_uses_median_and_keeps_missing_cuda_peak():
    runs = [
        {
            "elapsed_seconds": 9.0,
            "phase_totals_seconds": {"sampling": 7.0, "video_vae_decode": 1.0},
            "resources": {
                "peak_rss_bytes": 90,
                "peak_private_bytes": 70,
                "peak_uss_bytes": 60,
                "minimum_cuda_free_bytes": 40,
            },
            "cuda_global_peak_allocated_bytes": None,
        },
        {
            "elapsed_seconds": 5.0,
            "phase_totals_seconds": {"sampling": 3.0, "video_vae_decode": 0.5},
            "resources": {
                "peak_rss_bytes": 50,
                "peak_private_bytes": 30,
                "peak_uss_bytes": 20,
                "minimum_cuda_free_bytes": 10,
            },
            "cuda_global_peak_allocated_bytes": None,
        },
        {
            "elapsed_seconds": 7.0,
            "phase_totals_seconds": {"sampling": 5.0, "video_vae_decode": 0.8},
            "resources": {
                "peak_rss_bytes": 70,
                "peak_private_bytes": 50,
                "peak_uss_bytes": 40,
                "minimum_cuda_free_bytes": 20,
            },
            "cuda_global_peak_allocated_bytes": None,
        },
    ]
    result = probe.summarize_runs(runs)
    assert result["median_elapsed_seconds"] == 7.0
    assert result["median_phase_seconds"]["sampling"] == 5.0
    assert result["median_peak_rss_bytes"] == 70.0
    assert result["median_peak_private_bytes"] == 50.0
    assert result["median_peak_uss_bytes"] == 40.0
    assert result["median_cuda_global_peak_allocated_bytes"] is None


def test_phase_classification_is_explicit():
    assert probe._phase_for_class("H3ContinuumSamplerV35") == "sampling"
    assert probe._phase_for_class("VAEDecode") == "video_vae_decode"
    assert probe._phase_for_class("VAEDecodeAudio") == "audio_vae_decode"
    assert probe._phase_for_class("H3ContinuumAssembleSeamV35") == "assemble_seam"
    assert probe._phase_for_class("CreateVideo") == "video_create"
    assert probe._phase_for_class("SaveVideo") == "mp4_encode_save"
    assert probe._phase_for_class("UnknownNode") == "other"


def test_resource_monitor_does_not_poll_cuda_runtime():
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "torch.cuda.mem_get_info" not in source.replace(
        '``torch.cuda.mem_get_info``', ""
    )
    assert "pynvml.nvmlDeviceGetMemoryInfo" in source


def test_resource_monitor_does_not_poll_full_process_info():
    source = MODULE_PATH.read_text(encoding="utf-8")
    sample_body = source.split("def _sample(self) -> None:", 1)[1].split(
        "def _run(self) -> None:", 1
    )[0]
    assert "_memory_snapshot()" not in sample_body
    assert "self.process.memory_info()" in sample_body
