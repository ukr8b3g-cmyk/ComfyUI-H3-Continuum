from __future__ import annotations

import pytest
import torch

from ComfyUI_H3_Continuum_Join.v3 import plan as plan_module


def _logical_plan():
    return {
        "chunks": [
            {
                "sequence_index": 0,
                "chunk_index": 1,
                "total_frames": 124,
                "trim_frames": 0,
                "net_frames": 124,
                "context_frames": 0,
                "expected_video_latent_t": 37,
                "expected_audio_latent_t": 207,
                "frame_start": 0,
                "frame_stop": 124,
            },
            {
                "sequence_index": 1,
                "chunk_index": 2,
                "total_frames": 141,
                "trim_frames": 22,
                "net_frames": 119,
                "context_frames": 22,
                "expected_video_latent_t": 42,
                "expected_audio_latent_t": 235,
                "frame_start": 124,
                "frame_stop": 243,
            },
        ],
        "target_frames": 240,
    }


def _terminal_entries():
    physical_video = torch.arange(72, dtype=torch.float32).reshape(1, 1, 72, 1, 1)
    physical_audio = torch.arange(405, dtype=torch.float32).reshape(1, 1, 405)
    entries = [
        {
            "video": physical_video[:, :, 0:37].clone(),
            "audio": physical_audio[..., 0:207].clone(),
        },
        {
            "video": physical_video[:, :, 30:72].clone(),
            "audio": physical_audio[..., 170:405].clone(),
        },
    ]
    return entries, physical_video, physical_audio


def test_terminal_logical_entries_recombine_bit_exact(monkeypatch):
    entries, physical_video, physical_audio = _terminal_entries()
    monkeypatch.setattr(
        plan_module,
        "make_assembly_plan",
        lambda *args, **kwargs: _logical_plan(),
    )
    monkeypatch.setattr(plan_module, "validate_assembly_plan", lambda plan: plan)

    decode_entries, assembly_plan = plan_module.prepare_physical_decode_entries(
        entries,
        chunk_seconds=5.0,
        preserve_final_frame=True,
        terminal_merged=True,
    )

    assert len(decode_entries) == 1
    assert torch.equal(decode_entries[0]["video"], physical_video)
    assert torch.equal(decode_entries[0]["audio"], physical_audio)
    assert assembly_plan["logical_chunk_count"] == 2
    assert assembly_plan["physical_decode_group_count"] == 1
    assert assembly_plan["decode_groups"][0]["logical_chunk_indices"] == [1, 2]
    assert assembly_plan["decode_groups"][0]["total_frames"] == 243
    assert assembly_plan["decode_groups"][0]["trim_frames"] == 0
    assert assembly_plan["decode_groups"][0]["net_frames"] == 243


def test_terminal_recombine_rejects_changed_overlap(monkeypatch):
    entries, _, _ = _terminal_entries()
    entries[1]["video"][:, :, 0].add_(1.0)
    monkeypatch.setattr(
        plan_module,
        "make_assembly_plan",
        lambda *args, **kwargs: _logical_plan(),
    )

    with pytest.raises(ValueError, match="overlap differs"):
        plan_module.prepare_physical_decode_entries(
            entries,
            chunk_seconds=5.0,
            preserve_final_frame=True,
            terminal_merged=True,
        )


def test_three_logical_chunks_use_two_physical_decode_groups(monkeypatch):
    from ComfyUI_H3_Continuum_Join.v2.sequence import (
        _split_terminal_merged_latents,
        _terminal_pair_contract,
    )

    contract = _terminal_pair_contract(initial_pair=False, chunk_seconds=5.0)
    video_t = contract["video_slices"][-1][1]
    audio_t = contract["audio_slices"][-1][1]
    physical_video = torch.arange(video_t, dtype=torch.float32).reshape(1, 1, video_t, 1, 1)
    physical_audio = torch.arange(audio_t, dtype=torch.float32).reshape(1, 1, audio_t)
    terminal_parts = _split_terminal_merged_latents(physical_video, physical_audio, contract)
    first_entry = {
        "video": torch.zeros((1, 1, 37, 1, 1), dtype=torch.float32),
        "audio": torch.zeros((1, 1, 207), dtype=torch.float32),
    }
    logical_plan = {
        "chunks": [
            {"sequence_index": 0, "chunk_index": 1, "total_frames": 124, "trim_frames": 0, "net_frames": 124, "context_frames": 0, "expected_video_latent_t": 37, "expected_audio_latent_t": 207, "frame_start": 0, "frame_stop": 124},
            {"sequence_index": 1, "chunk_index": 2, "total_frames": 141, "trim_frames": 22, "net_frames": 119, "context_frames": 22, "expected_video_latent_t": 42, "expected_audio_latent_t": 235, "frame_start": 124, "frame_stop": 243},
            {"sequence_index": 2, "chunk_index": 3, "total_frames": 141, "trim_frames": 22, "net_frames": 119, "context_frames": 22, "expected_video_latent_t": 42, "expected_audio_latent_t": 235, "frame_start": 243, "frame_stop": 362},
        ],
        "target_frames": 360,
    }
    entries = [
        first_entry,
        {"video": terminal_parts[0][0], "audio": terminal_parts[0][1]},
        {"video": terminal_parts[1][0], "audio": terminal_parts[1][1]},
    ]
    monkeypatch.setattr(plan_module, "make_assembly_plan", lambda *args, **kwargs: logical_plan)
    monkeypatch.setattr(plan_module, "validate_assembly_plan", lambda plan: plan)

    decode_entries, assembly_plan = plan_module.prepare_physical_decode_entries(
        entries,
        chunk_seconds=5.0,
        preserve_final_frame=True,
        terminal_merged=True,
    )

    assert len(decode_entries) == 2
    assert torch.equal(decode_entries[1]["video"], physical_video)
    assert torch.equal(decode_entries[1]["audio"], physical_audio)
    assert assembly_plan["physical_decode_group_count"] == 2
    terminal_group = assembly_plan["decode_groups"][1]
    assert terminal_group["logical_chunk_indices"] == [2, 3]
    assert terminal_group["total_frames"] == 260
    assert terminal_group["trim_frames"] == 22
    assert terminal_group["net_frames"] == 238
