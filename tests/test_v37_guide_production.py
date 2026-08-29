from __future__ import annotations

import copy

import pytest
import torch

from ComfyUI_H3_Continuum_Join import guide_timeline as guide_module
from ComfyUI_H3_Continuum_Join import run_storage as run_storage_module
from ComfyUI_H3_Continuum_Join.guide_timeline import (
    GUIDE_MODE_STILL_IMAGE,
    GUIDE_SCHEMA_VERSION,
    GUIDE_TYPE,
    MARK_STILL_IMAGE_GUIDE,
    GuideTargetError,
    StillImageGuideAssets,
    attach_still_image_guide,
    combine_guide_identity,
    make_still_image_guide,
    prepare_still_image_guide_source,
    resolve_guide_for_physical_group,
)
from ComfyUI_H3_Continuum_Join.v3.driving_nodes import (
    H3ContinuumSamplerV36,
    H3ContinuumSamplerV37,
    H3ContinuumStillImageGuideV37,
    NODE_CLASS_MAPPINGS,
)
from ComfyUI_H3_Continuum_Join.v2 import nodes as v2_nodes_module
from ComfyUI_H3_Continuum_Join.v2.nodes import H3ContinuumSamplerV2
from ComfyUI_H3_Continuum_Join.run_storage import (
    build_sampling_contract,
    revision_identity,
)


def _prepare(monkeypatch, image, frame):
    monkeypatch.setattr(
        guide_module,
        "_resize_guide_image",
        lambda value, width, height: value[:1, ..., :3].contiguous(),
    )
    return prepare_still_image_guide_source(
        make_still_image_guide(image, frame),
        output_width=576,
        output_height=576,
    )


def test_public_guide_payload_is_frame_based_and_versioned():
    image = torch.zeros((1, 4, 4, 3), dtype=torch.float32)
    payload = H3ContinuumStillImageGuideV37().pack(image, 183)[0]
    assert payload["schema_version"] == GUIDE_SCHEMA_VERSION
    assert payload["mode"] == GUIDE_MODE_STILL_IMAGE
    assert payload["absolute_frame"] == 183
    assert payload["image"] is image
    assert H3ContinuumStillImageGuideV37.RETURN_TYPES == (GUIDE_TYPE,)


@pytest.mark.parametrize("absolute_frame", [-1, 1.5, True])
def test_public_guide_rejects_non_strict_frames(absolute_frame):
    image = torch.zeros((1, 4, 4, 3), dtype=torch.float32)
    with pytest.raises(GuideTargetError, match="absolute_frame"):
        make_still_image_guide(image, absolute_frame)


@pytest.mark.parametrize("batch", [0, 2, 5])
def test_public_guide_rejects_non_single_image_batches(batch):
    image = torch.zeros((batch, 4, 4, 3), dtype=torch.float32)
    with pytest.raises(GuideTargetError, match="batch must be exactly 1"):
        make_still_image_guide(image, 0)


def test_prepare_rejects_non_single_image_batch_defensively(monkeypatch):
    image = torch.zeros((2, 4, 4, 3), dtype=torch.float32)
    payload = {
        "schema_version": GUIDE_SCHEMA_VERSION,
        "mode": GUIDE_MODE_STILL_IMAGE,
        "absolute_frame": 0,
        "image": image,
    }
    with pytest.raises(GuideTargetError, match="batch must be exactly 1"):
        prepare_still_image_guide_source(
            payload, output_width=576, output_height=576
        )


def test_run_storage_identity_scopes_image_frame_mode_and_schema(monkeypatch):
    image = torch.zeros((1, 4, 4, 3), dtype=torch.float32)
    source_a = _prepare(monkeypatch, image, 60)
    source_same = _prepare(monkeypatch, image.clone(), 60)
    source_frame = _prepare(monkeypatch, image.clone(), 61)
    changed = image.clone()
    changed[0, 0, 0, 0] = 1.0
    source_image = _prepare(monkeypatch, changed, 60)

    identity = combine_guide_identity("base", source_a)
    assert identity == combine_guide_identity("base", source_same)
    assert identity != combine_guide_identity("base", source_frame)
    assert identity != combine_guide_identity("base", source_image)
    assert source_a.contract["mode"] == GUIDE_MODE_STILL_IMAGE
    assert source_a.contract["schema_version"] == GUIDE_SCHEMA_VERSION
    assert source_a.contract["absolute_frame"] == 60
    assert source_a.contract["source_image_sha256"]


def test_prepared_guide_owns_the_original_source_image(monkeypatch):
    image = torch.rand((1, 6, 8, 3), dtype=torch.float32)
    source = _prepare(monkeypatch, image, 60)
    assert source.source_image is not image
    assert source.source_image.device.type == "cpu"
    assert torch.equal(source.source_image, image)
    image.fill_(0)
    assert not bool((source.source_image == 0).all())
    assert source.contract["source_width"] == 8
    assert source.contract["source_height"] == 6


def test_prepare_rejects_future_mode_or_schema(monkeypatch):
    image = torch.zeros((1, 4, 4, 3), dtype=torch.float32)
    payload = make_still_image_guide(image, 0)
    bad_schema = dict(payload, schema_version=GUIDE_SCHEMA_VERSION + 1)
    bad_mode = dict(payload, mode="audio")
    with pytest.raises(GuideTargetError, match="schema"):
        prepare_still_image_guide_source(
            bad_schema, output_width=576, output_height=576
        )
    with pytest.raises(GuideTargetError, match="mode"):
        prepare_still_image_guide_source(
            bad_mode, output_width=576, output_height=576
        )


def test_runtime_group_resolver_uses_context_prefix_and_visible_tail():
    target = resolve_guide_for_physical_group(
        183,
        target_frames=360,
        physical_group_index=1,
        logical_chunks=(2,),
        global_visible_start=124,
        natural_visible_stop=243,
        context_prefix_frames=22,
        physical_frames=141,
        terminal_merged=False,
    )
    assert target["local_visible_frame"] == 59
    assert target["resolved_frame_index"] == 81
    assert resolve_guide_for_physical_group(
        359,
        target_frames=360,
        physical_group_index=2,
        logical_chunks=(3,),
        global_visible_start=243,
        natural_visible_stop=362,
        context_prefix_frames=22,
        physical_frames=141,
        terminal_merged=False,
    )["resolved_frame_index"] == 138


def test_runtime_group_resolver_supports_terminal_merge():
    target = resolve_guide_for_physical_group(
        243,
        target_frames=360,
        physical_group_index=1,
        logical_chunks=(2, 3),
        global_visible_start=124,
        natural_visible_stop=362,
        context_prefix_frames=22,
        physical_frames=260,
        terminal_merged=True,
    )
    assert target["logical_chunks"] == [2, 3]
    assert target["resolved_frame_index"] == 141
    assert target["terminal_merged"] is True


def test_keyframe_injection_clones_and_preserves_existing_order():
    original = [[torch.zeros(1), {"minimax_keyframes": [
        {"resolved_frame_index": 0, "latent": torch.tensor([1.0])},
        {"resolved_frame_index": 123, "latent": torch.tensor([2.0])},
    ], "minimax_frame_count": 124}]]
    before = copy.deepcopy(original)
    source = guide_module.StillImageGuideSource(
        image=torch.zeros((1, 4, 4, 3)),
        absolute_frame=60,
        contract={
            "schema_version": GUIDE_SCHEMA_VERSION,
            "mode": GUIDE_MODE_STILL_IMAGE,
            "absolute_frame": 60,
            "image_sha256": "x",
        },
    )
    assets = StillImageGuideAssets(source=source, latent=torch.tensor([3.0]))
    output = attach_still_image_guide(
        original,
        assets,
        {"resolved_frame_index": 60},
    )
    assert output is not original
    assert [item["resolved_frame_index"] for item in output[0][1]["minimax_keyframes"]] == [0, 123, 60]
    assert torch.equal(
        original[0][1]["minimax_keyframes"][0]["latent"],
        before[0][1]["minimax_keyframes"][0]["latent"],
    )
    assert len(original[0][1]["minimax_keyframes"]) == 2
    assert output[0][1]["minimax_keyframes"][2][MARK_STILL_IMAGE_GUIDE] is True


def test_v36_schema_is_unchanged_and_v37_adds_only_typed_guide():
    v36 = H3ContinuumSamplerV36.INPUT_TYPES()
    v37 = H3ContinuumSamplerV37.INPUT_TYPES()
    assert "guide" not in v36.get("required", {})
    assert "guide" not in v36.get("optional", {})
    assert v37["required"] == v36["required"]
    expected_optional = dict(v36["optional"])
    expected_optional["guide"] = v37["optional"]["guide"]
    assert v37["optional"] == expected_optional
    assert v37["optional"]["guide"][0] == GUIDE_TYPE


def test_v37_nodes_are_registered_without_replacing_v36():
    assert NODE_CLASS_MAPPINGS["H3ContinuumSamplerV36"] is H3ContinuumSamplerV36
    assert NODE_CLASS_MAPPINGS["H3ContinuumSamplerV37"] is H3ContinuumSamplerV37
    assert (
        NODE_CLASS_MAPPINGS["H3ContinuumStillImageGuideV37"]
        is H3ContinuumStillImageGuideV37
    )


def test_v2_orchestration_forwards_guide_source_to_sequence(monkeypatch):
    captured = {}
    guide_source = object()

    def fake_run_sequence(**kwargs):
        captured.update(kwargs)
        return "ok"

    monkeypatch.setattr(v2_nodes_module, "run_sequence", fake_run_sequence)
    result = H3ContinuumSamplerV2().run(
        model=object(),
        clip=object(),
        video_vae=object(),
        audio_vae=None,
        sampler=object(),
        sigmas=torch.tensor([1.0, 0.0]),
        prompt_mode="Fixed",
        prompt_script="Prompt",
        chunks=1,
        chunk_seconds=5.0,
        width=384,
        height=384,
        continuity="Balanced — 22 frames",
        base_seed=1,
        audio_continuity=True,
        exact_total_duration=False,
        diagnostics="Off",
        reroll_from_chunk=0,
        reroll_nonce=0,
        strict_compatibility=False,
        debug=False,
        guide_source=guide_source,
    )
    assert result == "ok"
    assert captured["guide_source"] is guide_source


def test_run_storage_revision_tracks_every_guide_identity_field(monkeypatch):
    monkeypatch.setattr(
        run_storage_module, "_model_signature", lambda model, value: ({}, True)
    )
    monkeypatch.setattr(run_storage_module, "_clip_signature", lambda clip: ({}, True))
    monkeypatch.setattr(
        run_storage_module,
        "_video_vae_signature",
        lambda vae, required: ({}, True),
    )
    monkeypatch.setattr(
        run_storage_module, "_sampler_signature", lambda sampler: ({}, True)
    )

    base_guide = {
        "schema_version": GUIDE_SCHEMA_VERSION,
        "mode": GUIDE_MODE_STILL_IMAGE,
        "absolute_frame": 60,
        "image_sha256": "a" * 64,
        "width": 384,
        "height": 384,
    }

    def build(guide_contract):
        contract, safe, reasons = build_sampling_contract(
            model=object(),
            model_fingerprint_value="m" * 64,
            clip=object(),
            video_vae=object(),
            sampler=object(),
            sigmas=torch.tensor([1.0, 0.0]),
            prompt_plan={"chunks": 1, "hashes": ["p" * 64], "mode": "fixed"},
            width=384,
            height=384,
            chunk_seconds=5.0,
            continuity="Balanced — 22 frames",
            audio_continuity=True,
            base_seed=1,
            reroll_from_chunk=0,
            reroll_nonce=0,
            first_frame_hash="none",
            last_frame_hash="none",
            strict_compatibility=False,
            conditioning_mode="t2va",
            guide_contract=guide_contract,
        )
        assert safe is True
        assert reasons == []
        return contract

    baseline = build(base_guide)
    assert baseline["global"]["guide"] == base_guide
    baseline_revision = revision_identity(baseline)
    for field, changed_value in (
        ("absolute_frame", 61),
        ("image_sha256", "b" * 64),
        ("mode", "video"),
        ("schema_version", GUIDE_SCHEMA_VERSION + 1),
    ):
        changed = dict(base_guide, **{field: changed_value})
        assert revision_identity(build(changed)) != baseline_revision
