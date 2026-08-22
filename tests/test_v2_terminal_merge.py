from __future__ import annotations

import pytest
import torch

from ComfyUI_H3_Continuum_Join.v2.sequence import (
    _atomic_terminal_prefix,
    _split_terminal_merged_latents,
    _terminal_flf_merge_enabled,
    _terminal_pair_prompt,
    _terminal_physical_seed_plan,
    _terminal_pair_contract,
    _terminal_sampling_plan,
)
from ComfyUI_H3_Continuum_Join.v2.seeds import derive_chunk_seed


@pytest.mark.parametrize(
    ("initial_pair", "physical_frames", "logical_frames", "video_slices", "audio_slices"),
    [
        (True, 243, (124, 141), ((0, 37), (30, 72)), ((0, 207), (170, 405))),
        (False, 260, (141, 141), ((0, 42), (35, 77)), ((0, 235), (198, 433))),
    ],
)
def test_terminal_pair_contract_uses_native_temporal_grid(
    initial_pair,
    physical_frames,
    logical_frames,
    video_slices,
    audio_slices,
):
    contract = _terminal_pair_contract(initial_pair=initial_pair, chunk_seconds=5.0)
    assert contract["physical_frames"] == physical_frames
    assert contract["logical_frames"] == logical_frames
    assert contract["video_slices"] == video_slices
    assert contract["audio_slices"] == audio_slices


@pytest.mark.parametrize("initial_pair", [True, False])
def test_terminal_pair_split_preserves_expected_overlap(initial_pair):
    contract = _terminal_pair_contract(initial_pair=initial_pair, chunk_seconds=5.0)
    video_t = contract["video_slices"][-1][1]
    audio_t = contract["audio_slices"][-1][1]
    video = torch.arange(video_t, dtype=torch.float32).reshape(1, 1, video_t, 1, 1)
    audio = torch.arange(audio_t, dtype=torch.float32).reshape(1, 1, 1, audio_t)
    first, second = _split_terminal_merged_latents(video, audio, contract)
    assert first[0].shape[2] == contract["video_slices"][0][1]
    assert first[1].shape[-1] == contract["audio_slices"][0][1]
    assert second[0][0, 0, 0, 0, 0].item() == contract["video_slices"][1][0]
    assert second[1][0, 0, 0, 0].item() == contract["audio_slices"][1][0]


def test_two_by_five_uses_one_physical_sample():
    normal, terminal = _terminal_sampling_plan(chunks=2, completed=0, merge_enabled=True)
    assert normal == ()
    assert terminal is True
    assert len(normal) + int(terminal) == 1


def test_three_by_five_uses_one_normal_and_one_terminal_sample():
    normal, terminal = _terminal_sampling_plan(chunks=3, completed=0, merge_enabled=True)
    assert normal == (0,)
    assert terminal is True
    assert len(normal) + int(terminal) == 2


def test_terminal_merge_accepts_distinct_prompts_but_not_timeline_video():
    common = dict(multi_chunk_flf=True, chunks=2, chunk_seconds=5.0)
    assert _terminal_flf_merge_enabled(**common, prompt_hashes=["same", "same"], timeline_video_source=None)
    assert _terminal_flf_merge_enabled(**common, prompt_hashes=["a", "b"], timeline_video_source=None)
    assert not _terminal_flf_merge_enabled(**common, prompt_hashes=["same", "same"], timeline_video_source=object())


def test_terminal_pair_prompt_preserves_shared_prompt_exactly():
    prompt, policy = _terminal_pair_prompt(["same", "same"], pair_start=0, chunk_seconds=5.0)
    assert prompt == "same"
    assert policy == "shared_prompt_v1"


def test_terminal_pair_prompt_rebases_distinct_sections_to_local_timeline():
    prompt, policy = _terminal_pair_prompt(["first action", "second action"], pair_start=0, chunk_seconds=5.0)
    assert prompt == "[0-5s]\nfirst action\n\n[5-10s]\nsecond action"
    assert policy == "paired_timeline_v1"


def test_partial_terminal_pair_is_discarded_for_atomic_resume():
    preserved = [{"chunk": 1}, {"chunk": 2}]
    result, reset = _atomic_terminal_prefix(preserved, chunks=3, reroll_from_chunk=0)
    assert result == preserved[:1]
    assert reset is True


def test_rerolling_final_chunk_regenerates_both_terminal_chunks():
    preserved = [{"chunk": 1}, {"chunk": 2}, {"chunk": 3}]
    result, reset = _atomic_terminal_prefix(preserved, chunks=3, reroll_from_chunk=3)
    assert result == preserved[:1]
    assert reset is True


def test_complete_terminal_pair_remains_reusable_without_reroll():
    preserved = [{"chunk": 1}, {"chunk": 2}, {"chunk": 3}]
    result, reset = _atomic_terminal_prefix(preserved, chunks=3, reroll_from_chunk=0)
    assert result == preserved
    assert reset is False


@pytest.mark.parametrize("base_seed", [42, 123456789])
def test_initial_terminal_pair_uses_base_seed_directly(base_seed):
    plan = _terminal_physical_seed_plan(
        base_seed=base_seed,
        physical_window_start_index=0,
        reroll_nonce=0,
    )
    assert plan["physical_seed"] == base_seed
    assert plan["logical_entry_seeds"] == (base_seed, base_seed)


def test_later_terminal_pair_derives_once_from_pair_start():
    plan = _terminal_physical_seed_plan(
        base_seed=42,
        physical_window_start_index=2,
        reroll_nonce=0,
    )
    assert plan["physical_seed"] == derive_chunk_seed(42, 2, 0)
    assert plan["physical_seed"] == 1808285636802909398
    assert plan["logical_entry_seeds"] == (plan["physical_seed"],) * 2


def test_terminal_pair_reroll_derives_once_and_shares_new_seed():
    original = _terminal_physical_seed_plan(
        base_seed=42,
        physical_window_start_index=2,
        reroll_nonce=0,
    )
    rerolled = _terminal_physical_seed_plan(
        base_seed=42,
        physical_window_start_index=2,
        reroll_nonce=1,
    )
    assert rerolled["physical_seed"] == derive_chunk_seed(42, 2, 1)
    assert rerolled["physical_seed"] == 4306926667627841302
    assert rerolled["physical_seed"] != original["physical_seed"]
    assert rerolled["logical_entry_seeds"] == (rerolled["physical_seed"],) * 2


def test_non_terminal_seed_derivation_golden_values_are_unchanged():
    assert derive_chunk_seed(42, 0, 0) == 15348518480342951850
    assert derive_chunk_seed(42, 1, 0) == 13021120982267964226


def test_last_frame_absent_does_not_enable_terminal_merge():
    assert not _terminal_flf_merge_enabled(
        multi_chunk_flf=False,
        chunks=2,
        chunk_seconds=5.0,
        prompt_hashes=["same", "same"],
        timeline_video_source=None,
    )


def test_one_chunk_keeps_normal_sampling_and_seed_behavior():
    normal, terminal = _terminal_sampling_plan(chunks=1, completed=0, merge_enabled=False)
    assert normal == (0,)
    assert terminal is False
    assert derive_chunk_seed(42, normal[0], 0) == 15348518480342951850
