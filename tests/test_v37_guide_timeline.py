from __future__ import annotations

import pytest

from ComfyUI_H3_Continuum_Join.guide_timeline import (
    GuideTargetError,
    resolve_guide_target,
)


def _standard_three_chunk_plan() -> dict[str, Any]:
    return {
        "target_frames": 360,
        "chunks": [
            {
                "chunk_index": 1,
                "frame_start": 0,
                "frame_stop": 124,
                "total_frames": 124,
                "trim_frames": 0,
                "context_frames": 0,
                "net_frames": 124,
            },
            {
                "chunk_index": 2,
                "frame_start": 124,
                "frame_stop": 243,
                "total_frames": 141,
                "trim_frames": 22,
                "context_frames": 22,
                "net_frames": 119,
            },
            {
                "chunk_index": 3,
                "frame_start": 243,
                "frame_stop": 362,
                "total_frames": 141,
                "trim_frames": 22,
                "context_frames": 22,
                "net_frames": 119,
            },
        ],
    }


@pytest.mark.parametrize(
    ("absolute_frame", "group_index", "local_frame", "context", "resolved"),
    [
        (0, 0, 0, 0, 0),
        (60, 0, 60, 0, 60),
        (123, 0, 123, 0, 123),
        (124, 1, 0, 22, 22),
        (183, 1, 59, 22, 81),
        (242, 1, 118, 22, 140),
        (243, 2, 0, 22, 22),
        (302, 2, 59, 22, 81),
        (359, 2, 116, 22, 138),
    ],
)
def test_standard_three_chunk_absolute_mapping(
    absolute_frame,
    group_index,
    local_frame,
    context,
    resolved,
):
    result = resolve_guide_target(absolute_frame, _standard_three_chunk_plan())
    assert result["physical_group_index"] == group_index
    assert result["local_visible_frame"] == local_frame
    assert result["context_prefix_frames"] == context
    assert result["resolved_frame_index"] == resolved
    assert result["resolved_frame_index"] >= result["context_prefix_frames"]


def test_single_group_uses_visible_target_not_native_tail():
    plan = {
        "target_frames": 120,
        "chunks": [
            {
                "chunk_index": 1,
                "frame_start": 0,
                "frame_stop": 124,
                "total_frames": 124,
                "trim_frames": 0,
                "net_frames": 124,
            }
        ],
    }
    result = resolve_guide_target(119, plan)
    assert result["resolved_frame_index"] == 119
    with pytest.raises(GuideTargetError, match="outside visible range"):
        resolve_guide_target(120, plan)


def test_negative_and_total_duration_overflow_are_rejected():
    plan = _standard_three_chunk_plan()
    with pytest.raises(GuideTargetError, match="absolute_frame"):
        resolve_guide_target(-1, plan)
    with pytest.raises(GuideTargetError, match="outside visible range"):
        resolve_guide_target(360, plan)


def test_physical_boundaries_are_owned_by_the_following_group():
    plan = _standard_three_chunk_plan()
    assert resolve_guide_target(123, plan)["physical_group_index"] == 0
    assert resolve_guide_target(124, plan)["physical_group_index"] == 1
    assert resolve_guide_target(242, plan)["physical_group_index"] == 1
    assert resolve_guide_target(243, plan)["physical_group_index"] == 2


def test_terminal_merge_uses_physical_group_mapping():
    plan = {
        "target_frames": 360,
        "decode_groups": [
            {
                "logical_chunk_indices": [1],
                "frame_start": 0,
                "frame_stop": 124,
                "total_frames": 124,
                "trim_frames": 0,
                "net_frames": 124,
                "terminal_merged": False,
            },
            {
                "logical_chunk_indices": [2, 3],
                "frame_start": 124,
                "frame_stop": 362,
                "total_frames": 260,
                "trim_frames": 22,
                "net_frames": 238,
                "terminal_merged": True,
            },
        ],
    }
    start = resolve_guide_target(124, plan)
    logical_boundary = resolve_guide_target(243, plan)
    final = resolve_guide_target(359, plan)
    assert start["physical_group_index"] == 1
    assert start["logical_chunks"] == [2, 3]
    assert start["resolved_frame_index"] == 22
    assert logical_boundary["physical_group_index"] == 1
    assert logical_boundary["resolved_frame_index"] == 141
    assert final["resolved_frame_index"] == 257
    assert final["resolved_frame_index"] < final["physical_frames"]


def test_contradictory_physical_group_is_rejected():
    plan = _standard_three_chunk_plan()
    plan["chunks"][1]["frame_start"] = 120
    with pytest.raises(GuideTargetError, match="not contiguous"):
        resolve_guide_target(124, plan)
