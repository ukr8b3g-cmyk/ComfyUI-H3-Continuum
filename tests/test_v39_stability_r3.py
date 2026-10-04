from __future__ import annotations

import copy
import gc
from types import SimpleNamespace

import pytest
import torch

from ComfyUI_H3_Continuum_Join import driving_audio
from ComfyUI_H3_Continuum_Join.v3 import driving_nodes
from ComfyUI_H3_Continuum_Join.v3.nodes import _apply_review_decode_scope
from ComfyUI_H3_Continuum_Join.v3.plan import (
    AssemblyPlanError, REVIEW_AUDIO_PROJECTION_KEY, make_review_audio_projection,
    prepare_physical_decode_entries, validate_assembly_plan,
)
from ComfyUI_H3_Continuum_Join.v3.second_pass import update_second_pass_geometry
from ComfyUI_H3_Continuum_Join.v3.file_backed_buffer import get_file_backed_image_manager
from . import test_v38_review_run_storage as review
from . import test_p23_assembly_v35 as assembly


def scope(*, chunk=2, finish=False):
    contract = review._contract(chunks=4)
    entries = [review._entry(position, contract) for position in range(3)]
    decoded, full_plan = prepare_physical_decode_entries(
        entries, chunk_seconds=5, preserve_final_frame=False, terminal_merged=False,
    )
    result = {"session": {"chunks": entries}, "report": "source"}
    outputs = ([{"samples": entry["video"]} for entry in decoded],
               [{"samples": entry["audio"]} for entry in decoded], full_plan, result)
    storage = SimpleNamespace(review_generation_mode="Review Each Chunk",
                              review_execution=SimpleNamespace(finish_remaining=finish,
                                  next_review_unit_start=chunk, next_review_unit_end=chunk,
                                  partial_review=True, smart_regenerate=False))
    scoped = _apply_review_decode_scope(
        outputs, storage=storage, capture_refine_context=False, configured_chunks=4,
        chunk_seconds=5, first_frame=None, last_frame=None, timeline_video_source=None,
    )
    return scoped, outputs


def finalize(plan, source, *, exact=False, backend="RAM", direct=False):
    images, generated = assembly._decoded(plan, sample_rate=32000)
    if not direct:
        plan = dict(plan, _h3_continuum_driving_audio_v1=source)
    return driving_nodes.H3ContinuumAssembleSeamV35().assemble(
        images, generated, plan, exact, "Off", "Off", backend, "Off",
        driving_audio=source if direct else None,
    )


@pytest.fixture
def buffer_root(tmp_path, monkeypatch):
    original = driving_nodes.assemble_decoded_chunks_v35
    def assemble_at_test_root(**kwargs):
        return original(**kwargs, backing_root=tmp_path)
    monkeypatch.setattr(driving_nodes, "assemble_decoded_chunks_v35", assemble_at_test_root)
    yield tmp_path
    gc.collect()
    get_file_backed_image_manager(tmp_path).collect_ready()


@pytest.mark.parametrize("rate", [32000, 44100, 48000])
@pytest.mark.parametrize("channels", [1, 2])
@pytest.mark.parametrize("exact", [False, True])
@pytest.mark.parametrize("backend", ["RAM", "Disk-backed", "Auto"])
def test_finalize_uses_natural_absolute_pcm_origin(rate, channels, exact, backend, buffer_root):
    scoped, original = scope()
    plan = scoped[2]
    unit = original[2]["chunks"][1]
    samples = round(20 * rate)
    waveform = torch.arange(samples, dtype=torch.float32).view(1, 1, -1).repeat(1, channels, 1)
    source = {"waveform": waveform, "sample_rate": rate}
    frozen = waveform.clone()
    start = round(unit["frame_start"] * rate / 24)
    stop = round(unit["frame_stop"] * rate / 24)
    assert unit["frame_start"] == 124 and unit["frame_stop"] == 243
    expected = waveform[..., start:stop]
    if exact:
        wanted = round(plan["target_frames"] * rate / 24)
        padding = max(0, wanted - expected.shape[-1])
        # The unchanged V3.9 Exact rule repeats the final available PCM sample.
        expected = torch.cat((expected[..., :wanted], expected[..., -1:].expand(1, channels, padding)), dim=-1)
    for direct in (False, True):
        images, audio, _ = finalize(plan, source, exact=exact, backend=backend, direct=direct)
        assert torch.equal(audio["waveform"], expected)
        assert audio["sample_rate"] == rate
        assert images.shape[0] == (120 if exact else 119)
        del images, audio
    assert torch.equal(waveform, frozen)
    assert scoped[3]["session"] is original[3]["session"]
    assert len(original[3]["session"]["chunks"]) == 3
    assert REVIEW_AUDIO_PROJECTION_KEY not in original[2]
    assert REVIEW_AUDIO_PROJECTION_KEY not in original[3]["session"]


@pytest.mark.parametrize("length", [160000, 0])
@pytest.mark.parametrize("exact", [False, True])
def test_short_or_empty_review_audio_only_pads_when_required(length, exact, buffer_root):
    plan = scope()[0][2]
    waveform = torch.ones((1, 2, length), dtype=torch.float64)
    source = {"waveform": waveform, "sample_rate": 32000}
    images, output, report = finalize(plan, source, exact=exact)
    assert output["waveform"].dtype == waveform.dtype
    # Chunk 2 begins after these short sources. Use the selected output's real size.
    assert output["waveform"].shape == (1, 2, round(images.shape[0] * 32000 / 24))
    assert not torch.count_nonzero(output["waveform"])
    assert "Empty Review interval" in report
    assert torch.equal(source["waveform"], waveform)


def test_partial_short_audio_is_not_padded_with_exact_off(buffer_root):
    plan = scope()[0][2]
    start = round(124 * 32000 / 24)
    waveform = torch.arange(start + 1000, dtype=torch.float32).view(1, 1, -1)
    _, output, report = finalize(plan, {"waveform": waveform, "sample_rate": 32000})
    assert torch.equal(output["waveform"], waveform[..., start:])
    assert output["waveform"].shape[-1] == 1000
    assert "silence added" not in report


def test_finalize_repeat_does_not_cut_the_pcm_twice(buffer_root):
    plan = scope()[0][2]
    source = {"waveform": torch.arange(640000, dtype=torch.float32).view(1, 1, -1), "sample_rate": 32000}
    plan["_h3_continuum_driving_audio_v1"] = source
    before = source["waveform"].clone()
    first = finalize(plan, source)
    second = finalize(plan, source)
    assert torch.equal(first[1]["waveform"], second[1]["waveform"])
    assert first[1]["waveform"][0, 0, 0] == round(124 * 32000 / 24)
    assert torch.equal(plan["_h3_continuum_driving_audio_v1"]["waveform"], before)


def test_full_projection_keeps_source_pcm_unchanged(buffer_root):
    scoped, full = scope(finish=True)
    assert scoped is full
    assert REVIEW_AUDIO_PROJECTION_KEY not in full[2]
    source = {"waveform": torch.arange(640000, dtype=torch.float32).view(1, 1, -1), "sample_rate": 32000}
    _, output, _ = finalize(full[2], source, exact=False)
    assert torch.equal(output["waveform"], source["waveform"])


def test_terminal_physical_group_cannot_be_split():
    plan = assembly._plan("long_terminal_3x5")
    projection = make_review_audio_projection(plan, start_chunk=2, end_chunk=3)
    group = plan["decode_groups"][1]
    assert (projection["source_start_frame"], projection["source_stop_frame"]) == (group["frame_start"], group["frame_stop"])
    with pytest.raises(AssemblyPlanError, match="split"):
        make_review_audio_projection(plan, start_chunk=3, end_chunk=3)


@pytest.mark.parametrize("field,value", [
    ("version", 2), ("coordinate_space", "local"), ("fps", 30),
    ("start_chunk", 1), ("source_start_frame", -1), ("source_stop_frame", 242),
    ("source_stop_frame", 124),
])
def test_broken_metadata_has_no_first_audio_fallback(field, value):
    plan = scope()[0][2]
    plan[REVIEW_AUDIO_PROJECTION_KEY][field] = value
    with pytest.raises(AssemblyPlanError, match="Review audio projection"):
        driving_audio.slice_review_source_audio({"waveform": torch.ones(1, 1, 200), "sample_rate": 32000}, plan)


def test_second_pass_geometry_copy_preserves_projection_and_source():
    scoped, _ = scope()
    plan = scoped[2]
    source = {"waveform": torch.arange(100, dtype=torch.float32).view(1, 1, -1), "sample_rate": 32000}
    plan["_h3_continuum_driving_audio_v1"] = source
    before = copy.deepcopy(plan[REVIEW_AUDIO_PROJECTION_KEY])
    group = plan["second_pass_contract"]["physical_groups"][0]
    shape = (group["source_batch"], group["latent_channels"], group["source_latent_t"],
             group["source_latent_h"] * 2, group["source_latent_w"] * 2)
    updated = update_second_pass_geometry(plan, [{"samples": torch.zeros(shape)}])
    assert updated[REVIEW_AUDIO_PROJECTION_KEY] == before
    assert torch.equal(updated["_h3_continuum_driving_audio_v1"]["waveform"], source["waveform"])
    assert plan[REVIEW_AUDIO_PROJECTION_KEY] == before
    validate_assembly_plan(updated)
