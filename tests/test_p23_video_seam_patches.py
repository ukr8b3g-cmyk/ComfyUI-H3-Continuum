from __future__ import annotations

from dataclasses import replace

import pytest
import torch

from ComfyUI_H3_Continuum_Join.hardening import enrich_assembly_plan
from ComfyUI_H3_Continuum_Join.v3.plan import ASSEMBLY_PLAN_MAGIC
from ComfyUI_H3_Continuum_Join.v3.video_seam import (
    analyze_decoded_boundaries,
    correct_decoded_boundaries,
)
from ComfyUI_H3_Continuum_Join.v3.video_seam_v35 import (
    build_boundary_patches,
)


def _plan():
    return enrich_assembly_plan(
        {
            "magic": ASSEMBLY_PLAN_MAGIC,
            "schema_version": 1,
            "fps": 24,
            "width": 8,
            "height": 8,
            "chunk_seconds": 5.0,
            "target_frames": 240,
            "preserve_final_frame": True,
            "chunks": [
                {
                    "sequence_index": 1,
                    "chunk_index": 1,
                    "total_frames": 124,
                    "trim_frames": 0,
                    "net_frames": 124,
                    "context_frames": 0,
                    "expected_video_latent_t": 37,
                    "expected_audio_latent_t": 207,
                },
                {
                    "sequence_index": 2,
                    "chunk_index": 2,
                    "total_frames": 141,
                    "trim_frames": 22,
                    "net_frames": 119,
                    "context_frames": 22,
                    "expected_video_latent_t": 42,
                    "expected_audio_latent_t": 235,
                },
            ],
        }
    )


def _decoded(case: str) -> list[torch.Tensor]:
    images = [
        torch.full((124, 8, 8, 3), 0.25, dtype=torch.float32),
        torch.full((141, 8, 8, 3), 0.25, dtype=torch.float32),
    ]
    if case == "transient":
        images[1][22] = 1.0
    elif case == "micro":
        images[1][22] = 0.258
    elif case == "exposure":
        images[1][22:] = 0.33
        images[1][22:26] = torch.tensor(
            [0.27, 0.29, 0.31, 0.33],
            dtype=torch.float32,
        ).view(4, 1, 1, 1)
    elif case != "clean":
        raise AssertionError(f"unknown test case: {case}")
    return images


@pytest.mark.parametrize(
    ("case", "enable_exposure_ramp", "expected_patch_frames"),
    (
        ("transient", False, 1),
        ("micro", False, 1),
        ("exposure", False, 0),
        ("exposure", True, 4),
        ("clean", False, 0),
    ),
)
def test_small_patches_are_bit_exact_with_v34_correction(
    case,
    enable_exposure_ramp,
    expected_patch_frames,
):
    plan = _plan()
    images = _decoded(case)
    originals = [value.clone() for value in images]
    analyses = analyze_decoded_boundaries(images=images, assembly_plan=plan)

    legacy, legacy_actions = correct_decoded_boundaries(
        images=images,
        assembly_plan=plan,
        analyses=analyses,
        enable_exposure_ramp=enable_exposure_ramp,
    )
    patches, actions = build_boundary_patches(
        images,
        plan,
        analyses,
        enable_exposure_ramp=enable_exposure_ramp,
    )

    assert actions == legacy_actions
    assert all(torch.equal(value, original) for value, original in zip(images, originals))
    if expected_patch_frames == 0:
        assert patches == {}
        assert torch.equal(legacy[1], images[1])
        return

    assert set(patches) == {1}
    patch = patches[1]
    assert patch.device.type == "cpu"
    assert patch.shape == (expected_patch_frames, 8, 8, 3)
    assert 1 <= int(patch.shape[0]) <= 4
    trim = int(plan["chunks"][1]["trim_frames"])
    assert torch.equal(
        patch,
        legacy[1][trim : trim + expected_patch_frames],
    )
    assert torch.equal(legacy[1][:trim], images[1][:trim])
    assert torch.equal(
        legacy[1][trim + expected_patch_frames :],
        images[1][trim + expected_patch_frames :],
    )


def test_guarded_candidate_returns_native_action_without_a_patch():
    plan = _plan()
    images = _decoded("transient")
    analysis = analyze_decoded_boundaries(
        images=images,
        assembly_plan=plan,
    )[0]
    guarded = replace(analysis, scene_cut=True)

    legacy, legacy_actions = correct_decoded_boundaries(
        images=images,
        assembly_plan=plan,
        analyses=[guarded],
    )
    patches, actions = build_boundary_patches(images, plan, [guarded])

    assert patches == {}
    assert actions == legacy_actions == {
        1: "kept native boundary; correction guard rejected candidate"
    }
    assert legacy == images


def test_patch_storage_is_independent_and_inputs_remain_unchanged():
    plan = _plan()
    images = _decoded("transient")
    original = images[1].clone()
    analysis = analyze_decoded_boundaries(
        images=images,
        assembly_plan=plan,
    )[0]

    patches, _ = build_boundary_patches(images, plan, [analysis])
    patches[1].zero_()

    assert torch.equal(images[1], original)


def test_planning_error_does_not_mutate_inputs_or_return_a_partial_result():
    plan = _plan()
    images = _decoded("transient")
    originals = [value.clone() for value in images]
    analysis = analyze_decoded_boundaries(
        images=images,
        assembly_plan=plan,
    )[0]
    invalid = replace(analysis, boundary_index=2)

    with pytest.raises(
        ValueError,
        match="boundary index is outside decoded chunks",
    ):
        build_boundary_patches(images, plan, [analysis, invalid])

    assert all(torch.equal(value, original) for value, original in zip(images, originals))
