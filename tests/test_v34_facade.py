import torch

from ComfyUI_H3_Continuum_Join.nodes import NODE_CLASS_MAPPINGS
from ComfyUI_H3_Continuum_Join.reference import ReferenceImageBundle
from ComfyUI_H3_Continuum_Join.v3.driving_nodes import (
    H3ContinuumAssembleSeamV34,
    H3ContinuumSamplerV34,
)
from ComfyUI_H3_Continuum_Join.v3.nodes import H3ContinuumSamplerProduction


def test_v34_public_nodes_are_registered():
    assert NODE_CLASS_MAPPINGS["H3ContinuumSamplerV34"] is H3ContinuumSamplerV34
    assert NODE_CLASS_MAPPINGS["H3ContinuumAssembleSeamV34"] is H3ContinuumAssembleSeamV34


def test_v34_sampler_extends_official_contract_to_eight_references_only():
    v34_optional = H3ContinuumSamplerV34.INPUT_TYPES()["optional"]
    legacy_optional = H3ContinuumSamplerProduction.INPUT_TYPES()["optional"]

    for index in range(1, 9):
        assert v34_optional[f"reference_image_{index}"][0] == "IMAGE"
    for index in range(1, 4):
        assert legacy_optional[f"reference_image_{index}"][0] == "IMAGE"
    for index in range(4, 9):
        assert f"reference_image_{index}" not in legacy_optional

    assert v34_optional["reference_video_1"][0] == "IMAGE"
    assert v34_optional["driving_audio"][0] == "AUDIO"
    assert v34_optional["audio_vae"][0] == "VAE"
    assert "reference_audio_1" not in v34_optional
    assert "reference_audio_vae" not in v34_optional
    assert H3ContinuumSamplerV34.RETURN_NAMES == (
        "video_latents",
        "audio_latents",
        "assembly_plan",
        "status",
        "driving_audio",
    )
    assert H3ContinuumSamplerV34.OUTPUT_IS_LIST == (True, True, False, False, False)


def test_v34_reference_mode_precedence_and_extra_reference_bundle(monkeypatch):
    captured = {}
    ref3 = torch.zeros((1, 8, 8, 3))
    ref4 = torch.ones((1, 10, 6, 3))
    ref8 = torch.full((1, 4, 12, 3), 8.0)

    def fake_run(self, **kwargs):
        captured.update(kwargs)
        return ["v"], ["a"], {"target_frames": 120}, "status"

    monkeypatch.setattr(H3ContinuumSamplerProduction, "run", fake_run)
    outputs = H3ContinuumSamplerV34().run(
        chunks=1,
        chunk_seconds=5.0,
        width=64,
        height=64,
        first_frame="first",
        last_frame="last",
        reference_image_3=ref3,
        reference_image_4=ref4,
        reference_image_8=ref8,
    )

    assert captured["first_frame"] is None
    assert captured["last_frame"] is None
    bundle = captured["reference_image_3"]
    assert isinstance(bundle, ReferenceImageBundle)
    assert bundle.images == (ref3, ref4, ref8)
    assert "reference_image_4" not in captured
    assert "reference_image_8" not in captured
    assert captured["driving_audio_source"] is None
    assert captured["reference_video_source"] is None
    assert outputs == (["v"], ["a"], {"target_frames": 120}, "status", None)
