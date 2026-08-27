import torch
import pytest

from ComfyUI_H3_Continuum_Join.v2.decoder import (
    _slice_audio_for_timeline,
    enforce_total_frames,
)


def _audio(samples=200000, rate=32000):
    waveform = torch.arange(samples, dtype=torch.float32).reshape(1, 1, -1)
    return {"waveform": waveform, "sample_rate": rate}


def test_cumulative_audio_boundaries_do_not_accumulate_rounding_error():
    audio = _audio()
    cursor = 124
    pieces = []
    for _ in range(2):
        stop = cursor + 119
        piece = _slice_audio_for_timeline(
            audio,
            trim_frames=22,
            frame_start=cursor,
            frame_stop=stop,
        )
        pieces.append(piece)
        assert piece.shape[-1] == round(stop / 24 * 32000) - round(cursor / 24 * 32000)
        cursor = stop
    assert sum(piece.shape[-1] for piece in pieces) == round(362 / 24 * 32000) - round(124 / 24 * 32000)


@pytest.mark.parametrize("chunks", (2, 3, 5))
def test_long_audio_timeline_uses_cumulative_sample_boundaries(chunks):
    audio = _audio(samples=1_000_000)
    frame_starts = [0]
    for index in range(chunks):
        frame_starts.append(124 + 119 * index)

    total_samples = 0
    for index in range(chunks):
        frame_start = frame_starts[index]
        frame_stop = frame_starts[index + 1]
        trim_frames = 0 if index == 0 else 22
        piece = _slice_audio_for_timeline(
            audio,
            trim_frames=trim_frames,
            frame_start=frame_start,
            frame_stop=frame_stop,
        )
        expected = round(frame_stop / 24 * 32000) - round(
            frame_start / 24 * 32000
        )
        assert piece.shape[-1] == expected
        total_samples += expected

    assert total_samples == round(frame_starts[-1] / 24 * 32000)


def test_exact_duration_aligns_video_and_audio():
    images = torch.zeros(362, 4, 6, 3)
    audio = {"waveform": torch.zeros(1, 2, round(362 / 24 * 32000)), "sample_rate": 32000}
    images, audio, report = enforce_total_frames(images, audio, target_frames=360)
    assert images.shape[0] == 360
    assert audio["waveform"].shape[-1] == 480000
    assert "362->360" in report


def test_exact_duration_preserves_user_final_anchor_when_trimming():
    images = torch.arange(362, dtype=torch.float32).reshape(362, 1, 1, 1)
    rate = 32000
    samples = round(362 / 24 * rate)
    waveform = torch.linspace(-1.0, 1.0, samples).reshape(1, 1, -1)
    audio = {"waveform": waveform, "sample_rate": rate}

    result_images, result_audio, report = enforce_total_frames(
        images,
        audio,
        target_frames=360,
        preserve_final_frame=True,
    )

    assert result_images.shape[0] == 360
    assert float(result_images[-1]) == 361.0
    assert float(result_images[-2]) == 358.0
    assert result_audio["waveform"].shape[-1] == 480000
    assert "final anchor preserved" in report
