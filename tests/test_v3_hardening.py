from copy import deepcopy
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch


_SPEC = importlib.util.spec_from_file_location(
    "h3_continuum_v3_hardening",
    Path(__file__).parents[1] / "hardening.py",
)
hardening = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(hardening)


def _plan():
    plan = {
        "schema_version": 1,
        "fps": 24,
        "width": 448,
        "height": 672,
        "chunk_seconds": 5.0,
        "target_frames": 240,
        "preserve_final_frame": True,
        "chunks": [
            {
                "sequence_index": 0,
                "chunk_index": 7,
                "total_frames": 124,
                "trim_frames": 0,
                "net_frames": 124,
                "context_frames": 5,
                "expected_video_latent_t": 32,
                "expected_audio_latent_t": 207,
            },
            {
                "sequence_index": 1,
                "chunk_index": 8,
                "total_frames": 141,
                "trim_frames": 22,
                "net_frames": 119,
                "context_frames": 22,
                "expected_video_latent_t": 36,
                "expected_audio_latent_t": 235,
            },
        ],
    }
    return hardening.enrich_assembly_plan(plan)


def _decoded():
    images = [
        torch.zeros((124, 8, 8, 3), dtype=torch.float32),
        torch.zeros((141, 8, 8, 3), dtype=torch.float32),
    ]
    audio = [
        {"waveform": torch.zeros((1, 2, 160000)), "sample_rate": 32000},
        {"waveform": torch.zeros((1, 2, 188000)), "sample_rate": 32000},
    ]
    return images, audio


def test_plan_records_natural_boundaries_without_equating_target():
    plan = _plan()
    assert plan["chunk_count"] == 2
    assert plan["natural_frames"] == 243
    assert plan["target_frames"] == 240
    assert plan["chunks"][0]["frame_start"] == 0
    assert plan["chunks"][0]["frame_stop"] == 124
    assert plan["chunks"][1]["frame_start"] == 124
    assert plan["chunks"][1]["frame_stop"] == 243
    hardening.validate_assembly_plan_contract(plan)


def test_plan_uses_canonical_latent_length_fields():
    plan = _plan()
    chunk = plan["chunks"][0]
    assert chunk["expected_video_latent_t"] == 32
    assert chunk["expected_audio_latent_t"] == 207

    chunk["expected_video_t"] = chunk.pop("expected_video_latent_t")
    with pytest.raises(ValueError, match="expected_video_latent_t"):
        hardening.validate_assembly_plan_contract(plan)


def test_plan_builder_reads_audio_time_from_last_axis():
    source = (Path(__file__).parents[1] / "v3" / "plan.py").read_text(
        encoding="utf-8"
    )
    assert '"expected_video_latent_t": int(video.shape[2])' in source
    assert '"expected_audio_latent_t": int(audio.shape[-1])' in source


def test_plan_accepts_resumed_indices_but_rejects_discontinuity():
    plan = _plan()
    hardening.validate_assembly_plan_contract(plan)
    plan["chunks"][1]["chunk_index"] = 9
    with pytest.raises(ValueError, match="chunk_index"):
        hardening.validate_assembly_plan_contract(plan)


def test_plan_rejects_invalid_h3_grid_and_arithmetic():
    plan = _plan()
    plan["chunks"][1]["total_frames"] = 140
    with pytest.raises(ValueError, match=r"17k\+5"):
        hardening.validate_assembly_plan_contract(plan)

    plan = _plan()
    plan["chunks"][1]["net_frames"] = 118
    with pytest.raises(ValueError, match="total_frames - trim_frames"):
        hardening.validate_assembly_plan_contract(plan)


def test_legacy_schema_one_plan_without_redundant_fields_is_accepted():
    plan = _plan()
    plan.pop("chunk_count")
    plan.pop("natural_frames")
    for chunk in plan["chunks"]:
        chunk.pop("frame_start")
        chunk.pop("frame_stop")
    hardening.validate_assembly_plan_contract(plan)


def test_decoded_preflight_rejects_geometry_before_assembly():
    plan = _plan()
    images, audio = _decoded()
    images[1] = torch.zeros((141, 9, 8, 3), dtype=torch.float32)
    with pytest.raises(ValueError, match="geometry"):
        hardening.preflight_decoded_chunks(images, audio, plan)


def test_decoded_preflight_rejects_sample_rate_change():
    plan = _plan()
    images, audio = _decoded()
    audio[1]["sample_rate"] = 44100
    with pytest.raises(ValueError, match="sample_rate"):
        hardening.preflight_decoded_chunks(images, audio, plan)


def test_decoded_preflight_accepts_current_two_chunk_contract():
    plan = _plan()
    images, audio = _decoded()
    hardening.preflight_decoded_chunks(images, audio, plan)


def test_storage_stats_deduplicate_shared_storage():
    tensor = torch.zeros((2, 3))
    stats = hardening.tensor_storage_stats(tensor, tensor)
    assert stats["references"] == 2
    assert stats["unique_storages"] == 1


def test_session_storage_audit_reports_shared_cpu_storage():
    video = torch.zeros((1, 2, 3))
    audio = torch.zeros((1, 2, 4))
    entry = {"video": video, "audio": audio}
    text = hardening.format_latent_storage_audit([entry], {"chunks": [dict(entry)]})
    assert "session_shared=yes" in text
    assert "all_cpu=yes" in text


def test_core_chunked_io_capability_is_optional():
    supported_model = SimpleNamespace(
        comfy_has_chunked_io=True,
        decode_output_shape=lambda *args: None,
    )
    unsupported_model = SimpleNamespace()
    assert (
        hardening.core_video_vae_chunked_io_status(
            SimpleNamespace(first_stage_model=supported_model)
        )
        == "Supported"
    )
    assert (
        hardening.core_video_vae_chunked_io_status(
            SimpleNamespace(first_stage_model=unsupported_model)
        )
        == "Unsupported"
    )
    assert hardening.core_video_vae_chunked_io_status(object()) == "Unknown"
