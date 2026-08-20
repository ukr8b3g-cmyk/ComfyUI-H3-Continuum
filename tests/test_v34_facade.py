import pytest
import torch

from ComfyUI_H3_Continuum_Join.constants import V2_CONTINUITY_OPTIONS
from ComfyUI_H3_Continuum_Join.masked_continuation import (
    CONTINUATION_GUIDE,
    CONTINUATION_METHODS,
    CONTINUATION_NATIVE_MASKED,
    NativeMaskedContinuationError,
)
from ComfyUI_H3_Continuum_Join.nodes import NODE_CLASS_MAPPINGS
from ComfyUI_H3_Continuum_Join.reference import ReferenceImageBundle
from ComfyUI_H3_Continuum_Join.v3.driving_nodes import (
    V34_CONTINUITY_OPTIONS,
    V34_CONTINUITY_STRONG,
    H3ContinuumAssembleSeamV34,
    H3ContinuumSamplerV34,
)
from ComfyUI_H3_Continuum_Join.v3.nodes import H3ContinuumSamplerProduction


def test_v34_public_nodes_are_registered():
    assert NODE_CLASS_MAPPINGS["H3ContinuumSamplerV34"] is H3ContinuumSamplerV34
    assert NODE_CLASS_MAPPINGS["H3ContinuumAssembleSeamV34"] is H3ContinuumAssembleSeamV34


def test_v34_native_masked_is_default_without_changing_v33_contract():
    v34_required = H3ContinuumSamplerV34.INPUT_TYPES()["required"]
    legacy_required = H3ContinuumSamplerProduction.INPUT_TYPES()["required"]

    method = v34_required["continuation_method"]
    assert method[0] == CONTINUATION_METHODS
    assert method[1]["default"] == CONTINUATION_NATIVE_MASKED
    assert v34_required["continuity"][0] == V34_CONTINUITY_OPTIONS
    assert v34_required["continuity"][1]["default"] == V34_CONTINUITY_STRONG
    assert V34_CONTINUITY_STRONG == "Strong — 39 frames"
    assert V2_CONTINUITY_OPTIONS[3] in V34_CONTINUITY_OPTIONS
    assert "continuation_method" not in legacy_required
    assert legacy_required["continuity"][1]["default"] != V2_CONTINUITY_OPTIONS[3]


@pytest.mark.parametrize(
    "continuity",
    [V34_CONTINUITY_STRONG, V2_CONTINUITY_OPTIONS[3]],
)
def test_v34_strong_values_normalize_before_legacy_sequence_engine(monkeypatch, continuity):
    captured = {}

    def fake_run(self, **kwargs):
        captured.update(kwargs)
        return ["v"], ["a"], {"target_frames": 120}, "status"

    monkeypatch.setattr(H3ContinuumSamplerProduction, "run", fake_run)
    outputs = H3ContinuumSamplerV34().run(
        chunks=1,
        chunk_seconds=5.0,
        width=64,
        height=64,
        continuity=continuity,
        audio_continuity=True,
        continuation_method=CONTINUATION_NATIVE_MASKED,
    )

    assert captured["continuity"] == V2_CONTINUITY_OPTIONS[3]
    assert outputs == (["v"], ["a"], {"target_frames": 120}, "status", None)


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


def test_v34_invalid_native_generated_audio_profile_fails_before_parent_sampling(monkeypatch):
    parent_called = False

    def fake_run(self, **kwargs):
        nonlocal parent_called
        parent_called = True
        raise AssertionError("invalid native AV settings must fail before parent sampling")

    monkeypatch.setattr(H3ContinuumSamplerProduction, "run", fake_run)
    with pytest.raises(NativeMaskedContinuationError, match="22 video frames"):
        H3ContinuumSamplerV34().run(
            chunks=2,
            chunk_seconds=5.0,
            width=64,
            height=64,
            continuity=V2_CONTINUITY_OPTIONS[1],
            audio_continuity=True,
            continuation_method=CONTINUATION_NATIVE_MASKED,
        )
    assert parent_called is False


@pytest.mark.parametrize("continuation_method", [CONTINUATION_NATIVE_MASKED, CONTINUATION_GUIDE])
@pytest.mark.parametrize(
    ("first_frame", "last_frame"),
    [
        ("first", None),
        (None, "last"),
        ("first", "last"),
    ],
)
def test_v34_preserves_hybrid_keyframes_with_reference_for_both_continuation_methods(
    monkeypatch, continuation_method, first_frame, last_frame
):
    captured = {}
    ref = torch.zeros((1, 8, 8, 3))

    def fake_run(self, **kwargs):
        captured.update(kwargs)
        return ["v"], ["a"], {"target_frames": 120}, "status"

    monkeypatch.setattr(H3ContinuumSamplerProduction, "run", fake_run)
    H3ContinuumSamplerV34().run(
        chunks=1,
        chunk_seconds=5.0,
        width=64,
        height=64,
        first_frame=first_frame,
        last_frame=last_frame,
        reference_image_1=ref,
        continuation_method=continuation_method,
    )

    assert captured["first_frame"] == first_frame
    assert captured["last_frame"] == last_frame
    assert captured["reference_image_1"] is ref


def test_v34_preserves_hybrid_keyframes_and_bundles_extra_references(monkeypatch):
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

    assert captured["first_frame"] == "first"
    assert captured["last_frame"] == "last"
    bundle = captured["reference_image_3"]
    assert isinstance(bundle, ReferenceImageBundle)
    assert bundle.images == (ref3, ref4, ref8)
    assert "reference_image_4" not in captured
    assert "reference_image_8" not in captured
    assert captured["driving_audio_source"] is None
    assert captured["reference_video_source"] is None
    assert captured["continuity"] == V2_CONTINUITY_OPTIONS[3]
    assert outputs == (["v"], ["a"], {"target_frames": 120}, "status", None)
