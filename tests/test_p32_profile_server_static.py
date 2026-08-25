from pathlib import Path


SERVER_PATH = Path(__file__).parents[1] / "tools" / "p32_profile_server.py"


def test_phase32_api_profiler_is_diagnostic_only_and_synchronized():
    source = SERVER_PATH.read_text(encoding="utf-8")
    assert "torch.cuda.synchronize()" in source
    assert "torch.cuda.reset_peak_memory_stats()" in source
    assert 'PROFILE_MODE == "global"' in source
    assert 'PROFILE_MODE == "interval"' in source
    assert "original_execute_async" in source
    assert "original_get_output_data" in source
    assert "NODE_CLASS_MAPPINGS" not in source
    assert "class H3" not in source


def test_phase32_api_profiler_records_required_pipeline_phases():
    source = SERVER_PATH.read_text(encoding="utf-8") + (
        Path(__file__).parents[1] / "tools" / "p32_gpu_profile_probe.py"
    ).read_text(encoding="utf-8")
    for value in (
        "phase_totals_seconds",
        "cuda_global_peak_allocated_bytes",
        "peak_private_bytes",
        "peak_uss_bytes",
        "minimum_cuda_free_bytes",
        "route_observed",
        "spectrum_enabled",
    ):
        assert value in source
