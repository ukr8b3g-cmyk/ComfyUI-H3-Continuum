from __future__ import annotations

import sys
from types import ModuleType

import pytest
import torch

from ComfyUI_H3_Continuum_Join.constants import (
    PROMPT_MODE_FIXED,
    STATE_MAGIC,
    V2_CONTINUITY_AUTO,
    V2_CONTINUITY_OPTIONS,
)
from ComfyUI_H3_Continuum_Join.masked_continuation import (
    CONTINUATION_GUIDE,
    CONTINUATION_NATIVE_MASKED,
    NATIVE_MASK_CONTRACT_VERSION,
    NativeMaskedContinuationError,
    apply_native_masked_continuation,
    choose_continuation_context_frames,
    continuation_method_scope,
    continuation_storage_plan,
    current_continuation_method,
    exact_audio_prefix_steps,
    plan_continuation_contract,
    prepare_masked_conditioning,
    require_native_mask_support,
    stored_plan_matches_method,
)
from ComfyUI_H3_Continuum_Join.temporal import audio_latent_t, context_slots
from ComfyUI_H3_Continuum_Join.v2.prompts import make_prompt_plan
from ComfyUI_H3_Continuum_Join.version import STATE_SCHEMA_VERSION


class Nested:
    def __init__(self, parts):
        self.parts = list(parts)

    def unbind(self):
        return self.parts


def _install_fake_nested_tensor(monkeypatch):
    comfy = sys.modules.get("comfy")
    if comfy is None:
        comfy = ModuleType("comfy")
        comfy.__path__ = []
        monkeypatch.setitem(sys.modules, "comfy", comfy)
    nested = ModuleType("comfy.nested_tensor")
    nested.NestedTensor = Nested
    monkeypatch.setitem(sys.modules, "comfy.nested_tensor", nested)
    monkeypatch.setattr(comfy, "nested_tensor", nested, raising=False)


def _state(capacity=39):
    return {
        "magic": STATE_MAGIC,
        "schema_version": STATE_SCHEMA_VERSION,
        "clip_index": 1,
        "source_frame_count": 124,
        "capacity_frames": capacity,
        "width": 32,
        "height": 32,
        "video_tail": torch.zeros(1, 24, context_slots(capacity), 2, 2),
        "audio_tail": torch.zeros(1, 32, 2, audio_latent_t(capacity)),
        "audio_overhang": 0.0,
        "source_mode": "latent_direct",
    }


def _target(*, dtype=torch.float32):
    video = torch.full((1, 24, 20, 2, 2), -3.0, dtype=dtype)
    audio = torch.full((1, 32, 2, 100), -4.0, dtype=dtype)
    return {"samples": Nested((video, audio))}


@pytest.mark.parametrize("frames,expected", [(39, 65), (90, 150), (141, 235)])
def test_exact_av_context_mapping(frames, expected):
    assert exact_audio_prefix_steps(frames) == expected


@pytest.mark.parametrize("frames", [5, 22])
def test_non_exact_generated_audio_context_is_rejected(frames):
    with pytest.raises(NativeMaskedContinuationError, match="cannot silently round"):
        exact_audio_prefix_steps(frames)


def test_native_auto_generated_audio_resolves_to_exact_39_frame_boundary():
    frames, _score, reason = choose_continuation_context_frames(
        method=CONTINUATION_NATIVE_MASKED,
        continuity=V2_CONTINUITY_AUTO,
        state=_state(),
        audio_continuity=True,
        driving_audio_active=False,
    )
    assert frames == 39
    assert "65 audio steps" in reason


@pytest.mark.parametrize(
    "continuity,frames",
    [
        (V2_CONTINUITY_OPTIONS[1], 22),
        (V2_CONTINUITY_OPTIONS[2], 5),
        (V2_CONTINUITY_OPTIONS[3], 39),
    ],
)
def test_native_video_only_keeps_existing_valid_context_profiles(continuity, frames):
    selected, _score, _reason = choose_continuation_context_frames(
        method=CONTINUATION_NATIVE_MASKED,
        continuity=continuity,
        state=_state(),
        audio_continuity=False,
        driving_audio_active=False,
    )
    assert selected == frames


def test_native_driving_audio_does_not_force_generated_audio_boundary():
    frames, _score, _reason = choose_continuation_context_frames(
        method=CONTINUATION_NATIVE_MASKED,
        continuity=V2_CONTINUITY_OPTIONS[1],
        state=_state(),
        audio_continuity=True,
        driving_audio_active=True,
    )
    assert frames == 22


def test_native_mask_reports_precise_old_core_compatibility_error(monkeypatch):
    import ComfyUI_H3_Continuum_Join.masked_continuation as masked

    monkeypatch.setattr(
        masked,
        "native_mask_support_issues",
        lambda: ["MiniMaxH3._denoise_mask_conds is missing"],
    )
    with pytest.raises(NativeMaskedContinuationError) as exc_info:
        require_native_mask_support()
    message = str(exc_info.value)
    assert "PR #15375" in message
    assert "ff6c8a8af144fc9e9e7bc436b1b202f9316848d8" in message
    assert "Guide / Motion Context" in message
    assert "_denoise_mask_conds" in message


def test_native_mask_copies_exact_video_and_audio_prefix_and_preserves_source(monkeypatch):
    import ComfyUI_H3_Continuum_Join.masked_continuation as masked

    _install_fake_nested_tensor(monkeypatch)
    monkeypatch.setattr(masked, "require_native_mask_support", lambda: None)
    video_context = torch.arange(1 * 24 * 12 * 2 * 2, dtype=torch.float32).reshape(
        1, 24, 12, 2, 2
    )
    audio_context = torch.arange(1 * 32 * 2 * 65, dtype=torch.float32).reshape(
        1, 32, 2, 65
    )
    video_before = video_context.clone()
    audio_before = audio_context.clone()
    latent = _target(dtype=torch.float16)

    output = apply_native_masked_continuation(
        latent,
        video_context=video_context,
        audio_context=audio_context,
        context_frames=39,
    )
    video, audio = output["samples"].unbind()
    video_mask, audio_mask = output["noise_mask"].unbind()

    assert video.dtype == torch.float16 and audio.dtype == torch.float16
    assert torch.equal(video[:, :, :12], video_context.to(torch.float16))
    assert torch.equal(audio[..., :65], audio_context.to(torch.float16))
    assert torch.all(video_mask[:, :, :12] == 0)
    assert torch.all(video_mask[:, :, 12:] == 1)
    assert torch.all(audio_mask[..., :65] == 0)
    assert torch.all(audio_mask[..., 65:] == 1)
    assert video_mask.shape == (1, 1, 20, 2, 2)
    assert audio_mask.shape == (1, 1, 2, 100)
    assert video_mask.dtype == torch.float32
    assert audio_mask.dtype == torch.float32
    assert video_mask.device == video.device
    assert audio_mask.device == audio.device
    assert torch.equal(video_context, video_before)
    assert torch.equal(audio_context, audio_before)


def test_native_mask_rejects_video_target_without_generatable_region(monkeypatch):
    import ComfyUI_H3_Continuum_Join.masked_continuation as masked

    _install_fake_nested_tensor(monkeypatch)
    monkeypatch.setattr(masked, "require_native_mask_support", lambda: None)
    latent = {
        "samples": Nested(
            (
                torch.zeros(1, 24, 12, 2, 2),
                torch.zeros(1, 32, 2, 100),
            )
        )
    }

    with pytest.raises(NativeMaskedContinuationError, match="video latent contains no generatable region"):
        apply_native_masked_continuation(
            latent,
            video_context=torch.zeros(1, 24, 12, 2, 2),
            audio_context=None,
            context_frames=39,
        )


def test_native_mask_rejects_audio_target_without_generatable_region(monkeypatch):
    import ComfyUI_H3_Continuum_Join.masked_continuation as masked

    _install_fake_nested_tensor(monkeypatch)
    monkeypatch.setattr(masked, "require_native_mask_support", lambda: None)
    latent = {
        "samples": Nested(
            (
                torch.zeros(1, 24, 20, 2, 2),
                torch.zeros(1, 32, 2, 65),
            )
        )
    }

    with pytest.raises(NativeMaskedContinuationError, match="audio latent contains no generatable region"):
        apply_native_masked_continuation(
            latent,
            video_context=torch.zeros(1, 24, 12, 2, 2),
            audio_context=torch.zeros(1, 32, 2, 65),
            context_frames=39,
        )


def test_native_mask_rejects_spatial_geometry_mismatch(monkeypatch):
    import ComfyUI_H3_Continuum_Join.masked_continuation as masked

    _install_fake_nested_tensor(monkeypatch)
    monkeypatch.setattr(masked, "require_native_mask_support", lambda: None)

    with pytest.raises(NativeMaskedContinuationError, match="geometry does not match"):
        apply_native_masked_continuation(
            _target(),
            video_context=torch.zeros(1, 24, 12, 4, 4),
            audio_context=None,
            context_frames=39,
        )


def test_video_only_native_mask_leaves_entire_audio_stream_generatable(monkeypatch):
    import ComfyUI_H3_Continuum_Join.masked_continuation as masked

    _install_fake_nested_tensor(monkeypatch)
    monkeypatch.setattr(masked, "require_native_mask_support", lambda: None)
    video_context = torch.ones(1, 24, context_slots(22), 2, 2)
    latent = _target()

    output = apply_native_masked_continuation(
        latent,
        video_context=video_context,
        audio_context=None,
        context_frames=22,
    )
    video_mask, audio_mask = output["noise_mask"].unbind()
    assert torch.all(video_mask[:, :, : context_slots(22)] == 0)
    assert torch.all(audio_mask == 1)


def test_masked_conditioning_removes_competing_prefix_keyframes_and_keeps_last_and_refs():
    refs = [
        {"kind": "image", "name": f"ref-{index}"}
        for index in range(8)
    ] + [
        {"kind": "video", "name": "video-reference"},
        {"kind": "audio", "name": "standalone-reference-audio"},
    ]
    conditioning = [[
        torch.zeros(1, 1, 2),
        {
            "minimax_frame_count": 141,
            "minimax_keyframes": [
                {"resolved_frame_index": 0, "latent": "first"},
                {"resolved_frame_index": 10, "latent": "inside-prefix"},
                {"resolved_frame_index": 140, "latent": "last"},
            ],
            "minimax_refs": refs,
        },
    ]]

    output = prepare_masked_conditioning(
        conditioning,
        context_frames=39,
        new_frame_count=141,
    )
    metadata = output[0][1]
    assert metadata["minimax_keyframes"] == [
        {"resolved_frame_index": 140, "latent": "last"}
    ]
    assert metadata["minimax_refs"] == refs
    assert metadata["minimax_refs"] is refs  # shallow metadata clone keeps read-only ref list
    assert conditioning[0][1]["minimax_keyframes"][0]["latent"] == "first"


def test_masked_conditioning_keeps_keyframe_at_first_unprotected_frame():
    conditioning = [[
        torch.zeros(1, 1, 2),
        {"minimax_keyframes": [{"resolved_frame_index": 39, "latent": "guide"}]},
    ]]
    output = prepare_masked_conditioning(
        conditioning,
        context_frames=39,
        new_frame_count=141,
    )
    assert output[0][1]["minimax_keyframes"][0]["resolved_frame_index"] == 39


def test_run_storage_fingerprint_salts_only_continuation_chunks():
    plan = make_prompt_plan(
        mode=PROMPT_MODE_FIXED,
        script="continuous shot",
        chunks=3,
        chunk_seconds=5.0,
    )
    native = continuation_storage_plan(plan, CONTINUATION_NATIVE_MASKED)
    guide = continuation_storage_plan(plan, CONTINUATION_GUIDE)
    assert guide is plan
    assert native["hashes"][0] == plan["hashes"][0]
    assert native["hashes"][1:] != plan["hashes"][1:]
    assert all(value.startswith("h3c-native-mask-v1:") for value in native["hashes"][1:])


def test_stored_chunk_contract_rejects_legacy_guide_chunk_for_native_but_keeps_chunk_one():
    legacy = {"continuation": True}
    native = plan_continuation_contract(legacy, CONTINUATION_NATIVE_MASKED)
    assert stored_plan_matches_method(legacy, CONTINUATION_NATIVE_MASKED, chunk_number=1)
    assert not stored_plan_matches_method(legacy, CONTINUATION_NATIVE_MASKED, chunk_number=2)
    assert stored_plan_matches_method(legacy, CONTINUATION_GUIDE, chunk_number=2)
    assert stored_plan_matches_method(native, CONTINUATION_NATIVE_MASKED, chunk_number=2)
    assert native["native_mask_contract_version"] == NATIVE_MASK_CONTRACT_VERSION


def test_continuation_method_scope_is_reentrant_and_does_not_leak_state():
    assert current_continuation_method() == CONTINUATION_GUIDE
    with continuation_method_scope(CONTINUATION_NATIVE_MASKED):
        assert current_continuation_method() == CONTINUATION_NATIVE_MASKED
        with continuation_method_scope(CONTINUATION_GUIDE):
            assert current_continuation_method() == CONTINUATION_GUIDE
        assert current_continuation_method() == CONTINUATION_NATIVE_MASKED
    assert current_continuation_method() == CONTINUATION_GUIDE