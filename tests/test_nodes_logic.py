import pytest
import torch

from ComfyUI_H3_Continuum_Join.constants import (
    MARK_AUDIO_CONTEXT,
    MARK_VIDEO_CONTEXT,
)
from ComfyUI_H3_Continuum_Join.nodes import (
    POLICY_REPLACE,
    H3ContinuumAssemble,
    _conditioning_diagnostics,
    _prepare_conditioning,
    _trim_audio,
)


def test_prepare_conditioning_uses_one_video_audio_ref_and_moves_last():
    old_first = torch.zeros(1, 24, 1, 2, 2)
    old_last = torch.ones(1, 24, 1, 2, 2)
    tags = torch.tensor([1, 0, 0, 1])
    conditioning = [
        [
            torch.zeros(1, 4, 3),
            {
                "minimax_token_tags": tags,
                "minimax_frame_count": 124,
                "minimax_keyframes": [
                    {"resolved_frame_index": 0, "latent": old_first},
                    {"resolved_frame_index": 123, "latent": old_last},
                ],
            },
        ]
    ]
    video_context = torch.randn(1, 24, 7, 2, 2)
    audio_context = torch.randn(1, 32, 2, 37)
    out = _prepare_conditioning(
        conditioning,
        video_context=video_context,
        audio_context=audio_context,
        audio_grid_offset=1 / 3,
        context_frames=22,
        new_frame_count=141,
        first_frame_policy=POLICY_REPLACE,
        preserve_last_frame=True,
    )
    meta = out[0][1]
    assert len(meta["minimax_keyframes"]) == 1
    assert meta["minimax_keyframes"][0]["resolved_frame_index"] == 140
    assert len(meta["minimax_refs"]) == 1
    ref = meta["minimax_refs"][0]
    assert ref["kind"] == "video_audio"
    assert ref[MARK_VIDEO_CONTEXT] is True
    assert ref[MARK_AUDIO_CONTEXT] is True
    assert ref["latent"] is video_context
    assert ref["audio_latent"] is audio_context
    assert _conditioning_diagnostics(conditioning)["visual_tokens"] == 2


def test_prepare_conditioning_uses_source_frame_count_when_core_metadata_is_absent():
    old_last = torch.ones(1, 24, 1, 2, 2)
    conditioning = [[torch.zeros(1, 2, 3), {"minimax_keyframes": [{"resolved_frame_index": 123, "latent": old_last}]}]]
    out = _prepare_conditioning(
        conditioning,
        video_context=torch.randn(1, 24, 7, 2, 2),
        audio_context=None,
        audio_grid_offset=0.0,
        context_frames=22,
        new_frame_count=141,
        first_frame_policy=POLICY_REPLACE,
        preserve_last_frame=True,
        source_frame_count=124,
    )
    keyframes = out[0][1]["minimax_keyframes"]
    assert len(keyframes) == 1
    assert keyframes[0]["resolved_frame_index"] == 140


def test_prepare_conditioning_still_rejects_arbitrary_current_core_guides():
    conditioning = [[torch.zeros(1, 2, 3), {"minimax_keyframes": [{"resolved_frame_index": 60, "latent": torch.ones(1, 24, 1, 2, 2)}]}]]
    with pytest.raises(ValueError, match="unsupported existing H3 keyframe index 60"):
        _prepare_conditioning(
            conditioning,
            video_context=torch.randn(1, 24, 7, 2, 2),
            audio_context=None,
            audio_grid_offset=0.0,
            context_frames=22,
            new_frame_count=141,
            first_frame_policy=POLICY_REPLACE,
            preserve_last_frame=True,
            source_frame_count=124,
        )


def test_prepare_video_only_context():
    conditioning = [[torch.zeros(1, 2, 3), {}]]
    video_context = torch.randn(1, 24, 2, 2, 2)
    out = _prepare_conditioning(
        conditioning,
        video_context=video_context,
        audio_context=None,
        audio_grid_offset=0.0,
        context_frames=5,
        new_frame_count=124,
        first_frame_policy=POLICY_REPLACE,
        preserve_last_frame=True,
    )
    ref = out[0][1]["minimax_refs"][0]
    assert ref["kind"] == "video"
    assert ref["ref_audio_t"] == 0
    assert MARK_AUDIO_CONTEXT not in ref


def test_trim_audio_matches_video_duration():
    audio = {"waveform": torch.arange(1 * 2 * 4000).reshape(1, 2, 4000), "sample_rate": 1000}
    out = _trim_audio(audio, trim_frames=24, output_frames=48)
    assert out["waveform"].shape == (1, 2, 2000)
    assert out["waveform"][0, 0, 0] == audio["waveform"][0, 0, 1000]


def test_assemble_segments():
    node = H3ContinuumAssemble()
    a_images = torch.zeros(24, 4, 6, 3)
    b_images = torch.ones(12, 4, 6, 3)
    a_audio = {"waveform": torch.zeros(1, 2, 1000), "sample_rate": 1000}
    # One extra sample is tolerated and corrected at the final total boundary.
    b_audio = {"waveform": torch.ones(1, 2, 501), "sample_rate": 1000}
    images, audio, report = node.assemble(a_images, a_audio, b_images, b_audio)
    assert images.shape[0] == 36
    assert audio["waveform"].shape[-1] == 1500
    assert torch.all(images[-12:] == 1)
    assert "sync correction -1" in report
