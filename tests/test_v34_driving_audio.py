from __future__ import annotations

import pytest
import torch

from ComfyUI_H3_Continuum_Join.driving_audio import (
    DrivingAudioAssets,
    DrivingAudioSource,
    attach_driving_audio,
    encode_driving_audio,
    prepare_driving_audio_source,
    slice_driving_audio_latent,
)
from ComfyUI_H3_Continuum_Join.run_storage import automatic_project_key
from ComfyUI_H3_Continuum_Join.reference_video import (
    REFERENCE_VIDEO_SIZE_BALANCED,
    REFERENCE_VIDEO_SIZE_EFFICIENT,
    REFERENCE_VIDEO_SIZE_MATCH_OUTPUT,
    REFERENCE_VIDEO_SIZE_OPTIONS,
    _resolved_size,
)
from ComfyUI_H3_Continuum_Join.v3.assembly import (
    H3ContinuumAssembleSeamExperimental,
)
from ComfyUI_H3_Continuum_Join.v3.driving_nodes import (
    H3ContinuumAssembleSeamV34,
    H3ContinuumSamplerV34,
)


def test_v34_video_reference_schema_uses_image_batch():
    schema = H3ContinuumSamplerV34.INPUT_TYPES()
    assert schema["optional"]["reference_video_1"][0] == "IMAGE"
    size_schema = schema["required"]["video_reference_size"]
    assert size_schema[0] == REFERENCE_VIDEO_SIZE_OPTIONS
    assert size_schema[1]["default"] == REFERENCE_VIDEO_SIZE_EFFICIENT


def test_v34_requests_one_chunk_video_reference(monkeypatch):
    import ComfyUI_H3_Continuum_Join.reference_video as reference_video

    captured = {}

    class _Captured(RuntimeError):
        pass

    def capture_target(
        _video,
        *,
        target_frames,
        output_width,
        output_height,
        size_mode,
    ):
        captured["target_frames"] = target_frames
        captured["output_size"] = (output_width, output_height)
        captured["size_mode"] = size_mode
        raise _Captured

    monkeypatch.setattr(
        reference_video,
        "prepare_reference_video_source",
        capture_target,
    )
    with pytest.raises(_Captured):
        H3ContinuumSamplerV34().run(
            reference_video_1=torch.zeros((243, 8, 8, 3)),
            driving_audio=None,
            audio_vae=None,
            chunks=2,
            chunk_seconds=5.0,
            width=800,
            height=800,
            video_reference_size=REFERENCE_VIDEO_SIZE_BALANCED,
        )
    assert captured["target_frames"] == 124
    assert captured["output_size"] == (800, 800)
    assert captured["size_mode"] == REFERENCE_VIDEO_SIZE_BALANCED


def test_video_reference_size_modes_preserve_source_and_avoid_upscale():
    assert _resolved_size(
        768,
        768,
        output_width=800,
        output_height=800,
        size_mode=REFERENCE_VIDEO_SIZE_EFFICIENT,
    ) == (640, 640)
    assert _resolved_size(
        768,
        768,
        output_width=800,
        output_height=800,
        size_mode=REFERENCE_VIDEO_SIZE_BALANCED,
    ) == (768, 768)
    assert _resolved_size(
        768,
        768,
        output_width=800,
        output_height=800,
        size_mode=REFERENCE_VIDEO_SIZE_MATCH_OUTPUT,
    ) == (768, 768)


def test_video_reference_match_output_preserves_source_aspect_ratio():
    width, height = _resolved_size(
        1920,
        1080,
        output_width=1344,
        output_height=768,
        size_mode=REFERENCE_VIDEO_SIZE_MATCH_OUTPUT,
    )
    assert width % 32 == 0
    assert height % 32 == 0
    assert width <= 1920
    assert height <= 1080
    assert abs((width / height) - (1920 / 1080)) < 0.06

class _AudioVAE:
    audio_sample_rate = 10

    def __init__(self):
        self.calls = []

    def encode(self, waveform):
        self.calls.append(waveform)
        return torch.arange(400, dtype=torch.float32).reshape(1, 1, 1, 400)


def _audio(seconds: int, *, tail_value: float = 0.0):
    waveform = torch.zeros((1, 2, seconds * 10), dtype=torch.float32)
    if seconds > 15:
        waveform[..., 150:] = tail_value
    return {"waveform": waveform, "sample_rate": 10}


def test_v34_public_schema_replaces_reference_audio_with_driving_audio():
    schema = H3ContinuumSamplerV34.INPUT_TYPES()
    assert "driving_audio" in schema["optional"]
    assert "audio_vae" in schema["optional"]
    assert schema["optional"]["reference_video_1"][1]["display_name"] == (
        "Video Guide Frames"
    )
    assert schema["optional"]["driving_audio"][1]["display_name"] == "Driving Audio"
    assert schema["optional"]["audio_vae"][1]["display_name"] == "Driving Audio VAE"
    assert schema["required"]["video_reference_size"][1]["display_name"] == (
        "Video Guide Size"
    )
    assert "reference_audio_1" not in schema["optional"]
    assert "reference_audio_vae" not in schema["optional"]

    from ComfyUI_H3_Continuum_Join import nodes as root_nodes

    assert root_nodes.NODE_DISPLAY_NAME_MAPPINGS["H3ContinuumSamplerV34"] == (
        "H3 Continuum Sampler V3.4"
    )
    assert root_nodes.NODE_DISPLAY_NAME_MAPPINGS[
        "H3ContinuumSamplerTimelineVideo"
    ].startswith("[Legacy]")


def test_unused_long_audio_tail_does_not_change_contract_or_output():
    vae = _AudioVAE()
    first = prepare_driving_audio_source(
        _audio(30, tail_value=1.0), vae, target_frames=360, fps=24
    )
    second = prepare_driving_audio_source(
        _audio(30, tail_value=9.0), vae, target_frames=360, fps=24
    )
    assert first.combined_hash == second.combined_hash
    assert first.source_audio["waveform"].shape[-1] == 150
    assert second.source_audio["waveform"].shape[-1] == 150


def test_short_driving_audio_is_accepted_without_padding():
    source = prepare_driving_audio_source(
        _audio(4), _AudioVAE(), target_frames=360, fps=24
    )
    assert source.source_audio["waveform"].shape == (1, 2, 40)
    assert source.resampled_waveform.shape == (1, 2, 40)


def test_encode_is_core_layout_and_absolute_slices_are_drift_free():
    vae = _AudioVAE()
    source = prepare_driving_audio_source(
        _audio(30), vae, target_frames=360, fps=24
    )
    assets = encode_driving_audio(source, vae)
    assert len(vae.calls) == 1
    assert vae.calls[0].shape == (1, 150, 2)

    first = slice_driving_audio_latent(
        assets,
        cumulative_retained_before=0,
        total_frames=124,
        trim_frames=0,
        fps=24,
    )
    second = slice_driving_audio_latent(
        assets,
        cumulative_retained_before=124,
        total_frames=141,
        trim_frames=22,
        fps=24,
    )
    third = slice_driving_audio_latent(
        assets,
        cumulative_retained_before=243,
        total_frames=141,
        trim_frames=22,
        fps=24,
    )
    assert first.flatten()[0].item() == 0
    assert second.flatten()[0].item() == round(102 * 40 / 24)
    assert third.flatten()[0].item() == round(221 * 40 / 24)


def test_driving_audio_uses_keyframe_payload_not_audio_reference_tokens():
    conditioning = [[torch.zeros((1, 2, 3)), {"minimax_ref_items": []}]]
    latent = torch.zeros((1, 32, 2, 10))
    output = attach_driving_audio(conditioning, latent)
    keyframe = output[0][1]["minimax_keyframes"][-1]
    assert keyframe == {"resolved_frame_index": 0, "audio_latent": latent}
    assert output[0][1]["minimax_ref_items"] == []


def test_audio_vae_topology_is_ignored_when_driving_audio_is_disconnected():
    base = {
        "1": {"class_type": "H3ContinuumSamplerV34", "inputs": {}},
        "2": {"class_type": "VAELoader", "inputs": {}},
    }
    connected_vae_only = {
        **base,
        "1": {
            "class_type": "H3ContinuumSamplerV34",
            "inputs": {"audio_vae": ["2", 0]},
        },
    }
    assert automatic_project_key(base, "1") == automatic_project_key(
        connected_vae_only, "1"
    )


def test_v34_assembler_selects_original_driving_audio_and_bypasses_seam(
    monkeypatch,
):
    images = torch.zeros((10, 8, 8, 3))
    generated = {"waveform": torch.ones((1, 2, 20)), "sample_rate": 10}
    driving = {"waveform": torch.zeros((1, 2, 20)), "sample_rate": 10}

    monkeypatch.setattr(
        H3ContinuumAssembleSeamExperimental,
        "assemble",
        lambda self, *args, **kwargs: (images, generated, "base report"),
    )
    output_images, output_audio, report = H3ContinuumAssembleSeamV34().assemble(
        images=[],
        audio=[],
        assembly_plan={"target_frames": 10},
        exact_total_duration=False,
        audio_seam="Auto",
        video_seam="Auto",
        diagnostics="Basic",
        driving_audio=driving,
    )
    assert output_images is images
    assert torch.equal(output_audio["waveform"], driving["waveform"])
    assert "Audio Seam bypassed" in report


def test_v34_assembly_plan_audio_wins_when_direct_input_is_generated_audio(
    monkeypatch,
):
    images = torch.zeros((10, 8, 8, 3))
    generated = {
        "waveform": torch.zeros((1, 2, 320000), dtype=torch.float32),
        "sample_rate": 32000,
    }
    original = {
        "waveform": torch.linspace(-1.0, 1.0, 480000, dtype=torch.float32)
        .reshape(1, 1, -1)
        .repeat(1, 2, 1),
        "sample_rate": 48000,
    }
    plan = {
        "target_frames": 10,
        "_h3_continuum_driving_audio_v1": original,
    }

    monkeypatch.setattr(
        H3ContinuumAssembleSeamExperimental,
        "assemble",
        lambda self, *args, **kwargs: (images, generated, "base report"),
    )
    _, output_audio, report = H3ContinuumAssembleSeamV34().assemble(
        images=[],
        audio=[],
        assembly_plan=[plan],
        exact_total_duration=False,
        driving_audio=[generated],
    )

    assert output_audio["sample_rate"] == 48000
    assert torch.equal(output_audio["waveform"], original["waveform"])
    assert output_audio["waveform"].data_ptr() != original["waveform"].data_ptr()
    assert "selected from assembly plan" in report
