import torch

from ComfyUI_H3_Continuum_Join.v2.context_diagnostics import (
    ContextDiagnosticsTracker,
    measure_video_context,
)


def test_measure_video_context_is_read_only():
    video = torch.linspace(-1.0, 1.0, 1 * 24 * 3 * 5 * 7).reshape(1, 24, 3, 5, 7)
    original = video.clone()
    stats = measure_video_context(video)
    assert stats.shape == tuple(video.shape)
    assert stats.std > 0.0
    assert stats.high_frequency_rms > 0.0
    assert stats.temporal_delta_rms > 0.0
    assert torch.equal(video, original)


def test_constant_context_has_no_high_frequency_or_motion():
    stats = measure_video_context(torch.ones(1, 24, 2, 4, 4))
    assert stats.std == 0.0
    assert stats.high_frequency_rms == 0.0
    assert stats.temporal_delta_rms == 0.0
    assert stats.outlier_ratio == 0.0


def test_tracker_reports_baseline_and_previous_ratios():
    tracker = ContextDiagnosticsTracker()
    first = torch.linspace(-1.0, 1.0, 1 * 24 * 2 * 4 * 4).reshape(1, 24, 2, 4, 4)
    first_report = tracker.observe(first, source_chunk=1, context_frames=22, reused=False)
    second_report = tracker.observe(first * 2.0, source_chunk=2, context_frames=22, reused=False)
    assert "hf_base=1.0000" in first_report
    assert "std_base=2.0000" in second_report
    assert "hf_prev=2.0000" in second_report
    assert "action=observe" in second_report


def test_tracker_never_turns_diagnostic_failure_into_execution_error():
    report = ContextDiagnosticsTracker().observe(
        torch.zeros(1, 24, 2, 4),
        source_chunk=1,
        context_frames=22,
        reused=False,
    )
    assert "unavailable" in report
