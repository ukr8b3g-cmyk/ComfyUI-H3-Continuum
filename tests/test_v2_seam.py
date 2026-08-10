import torch

from ComfyUI_H3_Continuum_Join.v2.seam_guard import (
    apply_color_guard,
    choose_adaptive_cut,
    choose_video_blend,
    correct_audio_seam,
    correct_seam,
)
from ComfyUI_H3_Continuum_Join.v2.seam_types import VideoSeamMetrics


def _frames(values):
    return torch.tensor(values, dtype=torch.float32).reshape(-1, 1, 1, 1).expand(-1, 12, 12, 3).clone()


def test_adaptive_cut_detects_a_two_frame_earlier_clean_boundary():
    previous = _frames([0.0, 0.0, 0.0, 0.05, 0.10, 0.20, 0.30, 0.40])
    current = _frames([0.05, 0.10, 0.95, 0.205, 0.21, 0.90, 0.90, 0.90])

    rewind, legacy, selected = choose_adaptive_cut(
        previous,
        current,
        context_frames=5,
    )

    assert rewind == 2
    assert selected.score < legacy.score


def test_corrected_cut_preserves_the_total_frame_count():
    previous = _frames([0.0, 0.0, 0.0, 0.05, 0.10, 0.20, 0.30, 0.40])
    current = _frames([0.05, 0.10, 0.95, 0.205, 0.21, 0.90, 0.90, 0.90])
    corrected, decision, _patch = correct_seam(
        previous,
        current,
        context_frames=5,
    )
    legacy_total = previous.shape[0] + current.shape[0] - 5
    corrected_total = (
        previous.shape[0] - decision.cut_rewind_frames + corrected.shape[0]
    )
    assert corrected_total == legacy_total


def test_auto_keeps_a_clean_legacy_video_boundary():
    previous = _frames([0.2, 0.2, 0.2, 0.2])
    current = _frames([0.2, 0.2, 0.2, 0.2])

    corrected, decision, patch = correct_seam(
        previous,
        current,
        context_frames=2,
        automatic=True,
    )

    assert torch.equal(corrected, current[2:])
    assert decision.cut_rewind_frames == 0
    assert decision.corrected_score == decision.legacy_score
    assert decision.fallback_reason.startswith("Auto kept the legacy video seam")
    assert patch is None


def test_high_motion_disables_video_blend():
    metrics = VideoSeamMetrics(
        pixel_mae_norm=0.1,
        luma_norm=0.1,
        chroma_norm=0.1,
        edge_norm=0.1,
        temporal_norm=0.1,
        motion=0.2,
        score=0.1,
    )
    assert choose_video_blend(metrics) == 0


def test_excessive_color_request_is_not_applied():
    previous = _frames([0.01, 0.01])
    current = _frames([1.0, 1.0, 1.0, 1.0])
    corrected, gain, bias, _metrics = apply_color_guard(previous, current)
    assert gain == 1.0
    assert bias == (0.0, 0.0, 0.0)
    assert torch.equal(corrected, current)


def test_audio_seam_uses_one_offset_for_all_stereo_channels_and_keeps_a_local_patch():
    sample_rate = 1000
    time = torch.arange(800, dtype=torch.float32) / sample_rate
    signal = torch.sin(2.0 * torch.pi * 20.0 * time)
    previous = torch.stack((signal[:500], signal[:500]), dim=0).unsqueeze(0)
    current = torch.stack((signal, signal), dim=0).unsqueeze(0)

    patch, metrics, fade_samples, _gain, _dc = correct_audio_seam(
        previous,
        current,
        sample_rate=sample_rate,
        cut_sample=500,
    )

    assert isinstance(metrics.offset_samples, int)
    assert fade_samples <= round(sample_rate * 0.060)
    if patch is not None:
        assert patch.shape[1] == 2
        assert patch.shape[-1] == fade_samples
