from collections.abc import Mapping
import copy
import json

import pytest
import torch

from ComfyUI_H3_Continuum_Join.graph_contract import build_upstream_graph_contract
from ComfyUI_H3_Continuum_Join.v2.prompts import make_prompt_plan
from ComfyUI_H3_Continuum_Join.v2.session import make_session
from ComfyUI_H3_Continuum_Join.constants import PROMPT_MODE_LIST
from . import test_v38_review_execution_cap as cap
from .test_v36_masked_video_prefix import _install_nested_tensor
from .test_v35_context_sampler import _capture_sequence
from .test_v31_run_storage import _controller


def test_v3_reference_video_imports_the_shared_temporal_helper():
    from ComfyUI_H3_Continuum_Join.temporal import align_frame_count_up as shared
    from ComfyUI_H3_Continuum_Join.v3.reference_video import align_frame_count_up

    assert align_frame_count_up is shared


def test_reference_bundle_fingerprint_ignores_unused_legacy_vae():
    graph = {
        "1": {"class_type": "H3ContinuumSamplerV38", "inputs": {
            "model": ["2", 0], "clip": ["3", 0], "sampler": ["8", 0],
            "audio_references": ["4", 0], "reference_audio_vae": ["5", 0]}},
        "2": {"class_type": "UNETLoader", "inputs": {"unet_name": "model"}},
        "3": {"class_type": "CLIPLoader", "inputs": {"clip_name": "clip"}},
        "4": {"class_type": "H3ContinuumReferenceAudios", "inputs": {
            "reference_audio_vae": ["6", 0], "reference_audio_1": ["7", 0]}},
        "5": {"class_type": "VAELoader", "inputs": {"vae_name": "unused"}},
        "6": {"class_type": "VAELoader", "inputs": {"vae_name": "active"}},
        "7": {"class_type": "LoadAudio", "inputs": {"audio": "voice.wav"}},
        "8": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
    }

    def contract(value):
        result, safe, _ = build_upstream_graph_contract(
            value, "1", require_video_vae=False, require_reference_audio_vae=True)
        assert safe
        return result

    original = contract(graph)
    assert original["routes"]["reference_audio_vae"]["node"]["node_id"] == "4"
    active = copy.deepcopy(graph)
    active["6"]["inputs"]["vae_name"] = "new-active"
    assert contract(active)["sha256"] != original["sha256"]
    unused = copy.deepcopy(graph)
    unused["5"]["inputs"]["vae_name"] = "new-unused"
    assert contract(unused) == original
    legacy = copy.deepcopy(graph)
    del legacy["1"]["inputs"]["audio_references"]
    assert contract(legacy)["routes"]["reference_audio_vae"]["node"]["node_id"] == "5"

    # A connected but empty bundle can return None; execution then uses legacy
    # audio. Run Storage supplies this resolved route, not just graph priority.
    resolved, safe, _ = build_upstream_graph_contract(
        graph, "1", require_video_vae=False, require_reference_audio_vae=True,
        reference_audio_route="reference_audio_vae")
    assert safe
    assert resolved["routes"]["reference_audio_vae"]["node"]["node_id"] == "5"


def assert_nested_equal(actual, expected):
    if torch.is_tensor(expected):
        torch.testing.assert_close(actual, expected, rtol=0, atol=0)
    elif isinstance(expected, Mapping):
        assert actual.keys() == expected.keys()
        for key in expected:
            assert_nested_equal(actual[key], expected[key])
    elif isinstance(expected, (tuple, list)):
        assert len(actual) == len(expected)
        for a, b in zip(actual, expected, strict=True):
            assert_nested_equal(a, b)
    else:
        assert actual == expected


@pytest.mark.parametrize("transport", ["reference_context_v1", "masked_av_prefix_22_v1", "masked_video_prefix_v1"])
@pytest.mark.parametrize("anchors", ["none", "first", "first_last"])
@pytest.mark.parametrize("chunks", [1, 3, 6])
def test_review_and_complete_reuse_preserve_full_refine_context(monkeypatch, transport, anchors, chunks):
    _install_nested_tensor(monkeypatch)
    first = torch.zeros(1, 64, 96, 3) if anchors != "none" else None
    last = torch.ones(1, 64, 96, 3) if anchors == "first_last" else None
    runtime = cap._install_fake_runtime(monkeypatch, first_frame=first, last_frame=last)
    real = cap.sequence.run_sequence

    def run(**kwargs):
        kwargs["continuation_transport"] = transport
        return real(**kwargs)

    monkeypatch.setattr(cap.sequence, "run_sequence", run)
    options = dict(chunks=chunks, first_frame=first, last_frame=last, capture_refine_context=True)
    full = cap._run_sequence(runtime, **options)
    assert full[4]["complete"]
    expected_sample_count = len(runtime.samples)
    runtime.samples.clear()
    session = None
    for _ in range(chunks):
        before = len(runtime.samples)
        reviewed = cap._run_sequence(runtime, **options, limit=1, session=session)
        session = reviewed[2]
        assert len(runtime.samples) - before == 1
        if len(reviewed[0]) == chunks:
            break
        assert not reviewed[4]["complete"]
    assert len(runtime.samples) == expected_sample_count
    cap._assert_entry_parity(reviewed[0], full[0])
    assert reviewed[4]["complete"]
    assert_nested_equal(reviewed[4], full[4])
    runtime.samples.clear()
    reused = cap._run_sequence(runtime, **options, session=session)
    assert runtime.samples == []
    cap._assert_entry_parity(reused[0], full[0])
    assert_nested_equal(reused[4], full[4])


def test_review_does_not_encode_future_prompts(monkeypatch):
    runtime = cap._install_fake_runtime(monkeypatch)
    real = cap.sequence.run_sequence
    encoded = []
    encoder = runtime.clip.encode_from_tokens_scheduled
    monkeypatch.setattr(runtime.clip, "encode_from_tokens_scheduled",
                        lambda prompt: (encoded.append(prompt), encoder(prompt))[1])

    def run(**kwargs):
        kwargs["prompt_plan"] = make_prompt_plan(
            mode=PROMPT_MODE_LIST, script=json.dumps([f"action {i}" for i in range(6)]),
            chunks=6, chunk_seconds=5.0)
        return real(**kwargs)

    monkeypatch.setattr(cap.sequence, "run_sequence", run)
    cap._run_sequence(runtime, chunks=6, limit=1, capture_refine_context=True)
    assert len(runtime.samples) == 1
    assert encoded == ["action 0"]


@pytest.mark.parametrize("transport", ["reference_context_v1", "masked_av_prefix_22_v1", "masked_video_prefix_v1"])
@pytest.mark.parametrize("terminal", [False, True])
@pytest.mark.parametrize("image,audio", [(True, False), (False, True), (True, True)])
def test_review_reconstructs_reference_conditions(monkeypatch, transport, terminal, image, audio):
    real = cap.sequence.run_sequence
    state = {"limit": None, "samples": 0}

    def run(**kwargs):
        sample = cap.sequence.sample_chunk

        def counted(**sample_kwargs):
            state["samples"] += 1
            return sample(**sample_kwargs)

        monkeypatch.setattr(cap.sequence, "sample_chunk", counted)
        kwargs["max_new_physical_groups"] = state["limit"]
        return real(**kwargs)

    monkeypatch.setattr(cap.sequence, "run_sequence", run)
    options = dict(terminal=terminal, reference_image=image, reference_audio=audio,
                   continuation_transport=transport)
    full = _capture_sequence(monkeypatch, **options)
    assert state["samples"] == 2
    state.update(limit=1, samples=0)
    first = _capture_sequence(monkeypatch, **options)
    assert state["samples"] == 1
    assert not first[4]["complete"]
    final = _capture_sequence(monkeypatch, **options, session=first[2])
    assert state["samples"] == 2
    assert_nested_equal(final[4], full[4])
    state.update(limit=None, samples=0)
    reused = _capture_sequence(monkeypatch, **options, session=final[2])
    assert state["samples"] == 0
    assert_nested_equal(reused[4], full[4])


def test_full_reuse_without_refine_capture_does_not_encode_or_sample(monkeypatch):
    runtime = cap._install_fake_runtime(monkeypatch)
    full = cap._run_sequence(runtime, chunks=3)
    runtime.samples.clear()

    def unexpected(*args, **kwargs):
        pytest.fail("Full reuse without refine capture must not encode or sample")

    monkeypatch.setattr(cap.sequence, "encode_identity_latents", unexpected)
    monkeypatch.setattr(runtime.clip, "encode_from_tokens_scheduled", unexpected)
    monkeypatch.setattr(cap.sequence, "sample_chunk", unexpected)
    reused = cap._run_sequence(runtime, chunks=3, session=full[2])
    assert len(reused) == 4
    cap._assert_entry_parity(reused[0], full[0])


@pytest.mark.parametrize("terminal", [False, True])
def test_refine_context_rebuild_after_safetensors_storage_roundtrip(monkeypatch, tmp_path, terminal):
    _install_nested_tensor(monkeypatch)
    first = torch.zeros(1, 64, 96, 3) if terminal else None
    last = torch.ones(1, 64, 96, 3) if terminal else None
    runtime = cap._install_fake_runtime(monkeypatch, first_frame=first, last_frame=last)
    options = dict(chunks=3, first_frame=first, last_frame=last, capture_refine_context=True)
    full = cap._run_sequence(runtime, **options)
    writer, hashes = _controller(tmp_path)
    writer.prompts = ["continuous shot"] * 3
    for index, entry in enumerate(full[0]):
        writer.commit_chunk(entry, position=index)
    reader, _ = _controller(tmp_path)
    reader.prompts = writer.prompts[:]
    reader.manifest = json.loads(writer._manifest_path().read_text(encoding="utf-8"))
    loaded, records = reader._valid_prefix(reader.manifest, hashes)
    assert len(records) == len(loaded) == 3
    assert loaded[0]["video"].data_ptr() != full[0][0]["video"].data_ptr()
    prior = full[2]
    # The normal storage adapter invokes make_session to convert disk positions
    # (zero-based) to Session indices (one-based); exercise that owner as well.
    session = make_session(
        chunks=loaded, width=prior["width"], height=prior["height"],
        chunk_seconds=prior["chunk_seconds"], identity_hash=prior["identity_hash"],
        model_fingerprint_value=prior["model_fingerprint"],
        parent_session_id=prior["session_id"], reroll_from_chunk=0,
        settings=prior["settings"])
    runtime.samples.clear()
    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    restored = cap._run_sequence(runtime, **options, session=session)
    assert runtime.samples == []
    assert_nested_equal(restored[4], full[4])
    cap._assert_entry_parity(restored[0], full[0])
    assert {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()} == before
