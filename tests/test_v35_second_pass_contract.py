from __future__ import annotations

import copy

import pytest
import torch

from ComfyUI_H3_Continuum_Join.v3.plan import _attach_second_pass_contract
from ComfyUI_H3_Continuum_Join.v3.second_pass import (
    SecondPassContractError,
    derive_refine_seed,
    passthrough_audio_latents,
    update_second_pass_geometry,
    validate_second_pass_inputs,
)


def _latent(samples: torch.Tensor) -> dict[str, torch.Tensor]:
    return {"samples": samples}


def _physical_entry(t: int, audio_t: int, *, prompt: str = "") -> dict:
    return {
        "video": torch.zeros((1, 24, t, 40, 40)),
        "audio": torch.zeros((1, 8, audio_t)),
        "prompt": prompt,
    }


def _plan_and_latents(*, terminal: bool = False):
    if terminal:
        logical = [
            _physical_entry(31, 100, prompt="first"),
            _physical_entry(35, 110, prompt="middle"),
            _physical_entry(35, 110, prompt="last"),
        ]
        physical = [logical[0], _physical_entry(65, 220)]
        plan = {
            "width": 640,
            "height": 640,
            "chunks": [
                {"total_frames": 124, "trim_frames": 0},
                {"total_frames": 141, "trim_frames": 22},
                {"total_frames": 141, "trim_frames": 22},
            ],
            "decode_groups": [
                {
                    "logical_chunk_indices": [1],
                    "terminal_merged": False,
                    "total_frames": 124,
                    "trim_frames": 0,
                },
                {
                    "logical_chunk_indices": [2, 3],
                    "terminal_merged": True,
                    "total_frames": 260,
                    "trim_frames": 22,
                },
            ],
        }
    else:
        logical = [_physical_entry(31, 100, prompt="single")]
        physical = list(logical)
        plan = {
            "width": 640,
            "height": 640,
            "chunks": [{"total_frames": 124, "trim_frames": 0}],
        }
    _attach_second_pass_contract(
        plan,
        logical_entries=logical,
        physical_entries=physical,
        chunk_seconds=5.0,
    )
    videos = [_latent(entry["video"]) for entry in physical]
    audios = [_latent(entry["audio"]) for entry in physical]
    return plan, videos, audios


def test_terminal_contract_preserves_physical_group_and_prompt() -> None:
    plan, videos, audios = _plan_and_latents(terminal=True)
    result = validate_second_pass_inputs(videos, audios, plan)
    groups = plan["second_pass_contract"]["physical_groups"]
    assert result["physical_group_count"] == 2
    assert groups[1]["logical_chunks"] == [2, 3]
    assert groups[1]["physical_frames"] == 260
    assert groups[1]["trim_prefix_frames"] == 22
    assert groups[1]["prompt_policy"] == "paired_timeline_v1"
    assert groups[1]["physical_prompt"] == "[0-5s]\nmiddle\n\n[5-10s]\nlast"


def test_spatial_upscale_updates_only_target_geometry() -> None:
    plan, videos, audios = _plan_and_latents(terminal=True)
    upscaled = [
        _latent(item["samples"].new_zeros((1, 24, item["samples"].shape[2], 60, 60)))
        for item in videos
    ]
    validate_second_pass_inputs(upscaled, audios, plan)
    updated = update_second_pass_geometry(plan, upscaled)
    assert (plan["width"], plan["height"]) == (640, 640)
    assert (updated["width"], updated["height"]) == (960, 960)
    assert updated["second_pass_contract"]["target_width"] == 960


@pytest.mark.parametrize("channels", [23, 25])
def test_rejects_non_h3_video_channels(channels: int) -> None:
    plan, videos, audios = _plan_and_latents()
    videos[0] = _latent(torch.zeros((1, channels, 31, 40, 40)))
    with pytest.raises(SecondPassContractError, match="24 channels"):
        validate_second_pass_inputs(videos, audios, plan)


def test_rejects_temporal_or_group_count_changes() -> None:
    plan, videos, audios = _plan_and_latents(terminal=True)
    changed_t = copy.deepcopy(videos)
    changed_t[1] = _latent(torch.zeros((1, 24, 64, 40, 40)))
    with pytest.raises(SecondPassContractError, match="temporal length"):
        validate_second_pass_inputs(changed_t, audios, plan)
    with pytest.raises(SecondPassContractError, match="group count"):
        validate_second_pass_inputs(videos[:1], audios, plan)


def test_rejects_group_order_and_inconsistent_spatial_sizes() -> None:
    plan, videos, audios = _plan_and_latents(terminal=True)
    with pytest.raises(SecondPassContractError):
        validate_second_pass_inputs(list(reversed(videos)), list(reversed(audios)), plan)
    videos[1] = _latent(torch.zeros((1, 24, 65, 48, 48)))
    with pytest.raises(SecondPassContractError, match="same target H/W"):
        validate_second_pass_inputs(videos, audios, plan)


def test_audio_passthrough_is_bit_exact_and_keeps_latent_objects() -> None:
    _, _, audios = _plan_and_latents(terminal=True)
    output = passthrough_audio_latents(audios)
    assert all(before is after for before, after in zip(audios, output, strict=True))
    assert all(
        torch.equal(before["samples"], after["samples"])
        for before, after in zip(audios, output, strict=True)
    )


def test_refine_seed_is_deterministic_and_namespaced_per_group() -> None:
    assert derive_refine_seed(42, 0) == derive_refine_seed(42, 0)
    assert derive_refine_seed(42, 0) != derive_refine_seed(42, 1)
    assert derive_refine_seed(42, 0) != derive_refine_seed(43, 0)
