from __future__ import annotations

import pytest
import torch

from ComfyUI_H3_Continuum_Join.v3.refine_schedule import (
    AUDIO_POLICY_LOCKED_PASSTHROUGH,
    MODE_EXTERNAL,
    MODE_FULL,
    MODE_PARTIAL,
    MODE_TAIL,
    NOISE_MODE_VIDEO_RANDOM_AUDIO_ZERO,
    RefineScheduleError,
    make_external_schedule,
    make_full_schedule,
    make_partial_schedule,
    make_tail_schedule,
    resolve_refine_schedule,
    sigma_hash,
)


BASE = torch.tensor(
    [
        0.86998779,
        0.85072654,
        0.82778585,
        0.80000001,
        0.76671618,
        0.72347587,
        0.66692579,
        0.59232169,
        0.48214287,
        0.30945560,
        0.0,
    ],
    dtype=torch.float32,
)


def test_external_preserves_the_exact_existing_sigmas_object():
    schedule = make_external_schedule(BASE)
    resolved = resolve_refine_schedule(BASE, schedule)
    assert schedule.sigmas is BASE
    assert resolved is schedule
    assert schedule.contract["mode"] == MODE_EXTERNAL
    assert schedule.contract["sigma_hash"] == sigma_hash(BASE)
    assert schedule.contract["evaluation_count"] == 10
    assert schedule.contract["noise_mode"] == NOISE_MODE_VIDEO_RANDOM_AUDIO_ZERO
    assert schedule.contract["audio_policy"] == AUDIO_POLICY_LOCKED_PASSTHROUGH


def test_missing_schedule_is_external_compatibility():
    resolved = resolve_refine_schedule(BASE)
    assert resolved.sigmas is BASE
    assert resolved.contract["mode"] == MODE_EXTERNAL


def test_full_preserves_values_but_has_distinct_semantic_identity():
    external = make_external_schedule(BASE)
    full = make_full_schedule(BASE)
    assert full.sigmas is BASE
    assert full.contract["mode"] == MODE_FULL
    assert full.contract["sigma_hash"] == external.contract["sigma_hash"]
    assert full.contract["schedule_hash"] != external.contract["schedule_hash"]


def test_tail_10_and_tail_6_are_exact_suffixes_of_the_baseline():
    tail10 = make_tail_schedule(BASE, evaluation_count=10)
    tail6 = make_tail_schedule(BASE, evaluation_count=6)
    assert tail10.sigmas is BASE
    assert tail10.contract["mode"] == MODE_TAIL
    assert tail10.contract["start_index"] == 0
    assert torch.equal(tail6.sigmas, BASE[4:])
    assert tail6.contract["start_index"] == 4
    assert tail6.contract["end_index"] == 10
    assert tail6.contract["evaluation_count"] == 6
    assert tail6.contract["start_sigma"] == pytest.approx(float(BASE[4]))
    assert tail6.contract["end_sigma"] == 0.0


def test_partial_uses_the_requested_inclusive_sigma_range():
    partial = make_partial_schedule(BASE, start_index=2, end_index=7)
    assert partial.contract["mode"] == MODE_PARTIAL
    assert partial.contract["evaluation_count"] == 5
    assert torch.equal(partial.sigmas, BASE[2:8])


def test_schedule_rejects_a_different_source_even_when_shape_matches():
    schedule = make_tail_schedule(BASE, evaluation_count=6)
    changed = BASE.clone()
    changed[0] += 0.01
    with pytest.raises(RefineScheduleError, match="different source"):
        resolve_refine_schedule(changed, schedule)


@pytest.mark.parametrize(
    "value, message",
    [
        (torch.tensor([1.0]), "at least two"),
        (torch.tensor([0.0, 1.0]), "non-increasing"),
        (torch.tensor([1.0, float("nan")]), "NaN or Inf"),
    ],
)
def test_invalid_sigmas_are_rejected(value, message):
    with pytest.raises(RefineScheduleError, match=message):
        make_external_schedule(value)


@pytest.mark.parametrize("count", [0, 11, True])
def test_invalid_tail_counts_are_rejected(count):
    with pytest.raises(RefineScheduleError, match="evaluation_count"):
        make_tail_schedule(BASE, evaluation_count=count)


@pytest.mark.parametrize("start, end", [(-1, 2), (2, 2), (2, 11)])
def test_invalid_partial_ranges_are_rejected(start, end):
    with pytest.raises(RefineScheduleError, match="outside"):
        make_partial_schedule(BASE, start_index=start, end_index=end)
