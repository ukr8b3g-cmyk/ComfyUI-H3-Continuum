"""Small decoded-boundary patches for the V3.5 direct-write assembler.

The established V3.4 seam analyzer remains the source of all boundary
decisions.  This module reproduces only the correction step while avoiding the
full physical-group clone performed by ``correct_decoded_boundaries``.
"""

from __future__ import annotations

from typing import Any

import torch

from .plan import validate_assembly_plan
from .video_seam import VideoBoundaryAnalysis, _validate_frames


def build_boundary_patches(
    images: list[Any],
    assembly_plan: dict[str, Any],
    analyses: list[VideoBoundaryAnalysis],
    *,
    enable_exposure_ramp: bool = False,
) -> tuple[dict[int, torch.Tensor], dict[int, str]]:
    """Return qualified 1--4 frame corrections without changing ``images``.

    Patch keys are the existing one-based ``boundary_index`` values.  They are
    also the zero-based index of the current physical decode group, so the
    direct writer can add its natural-frame cursor without this module knowing
    the final buffer layout.

    The result is transactional: all patches and actions are built in local
    containers and are returned only after every requested boundary succeeds.
    Any exception therefore leaves the caller with no partial correction set.
    """

    plan = validate_assembly_plan(assembly_plan)
    groups = list(
        plan["decode_groups"] if "decode_groups" in plan else plan["chunks"]
    )
    if len(images) != len(groups):
        raise ValueError("decoded image count does not match the assembly plan")

    patches: dict[int, torch.Tensor] = {}
    actions: dict[int, str] = {}
    for analysis in analyses:
        boundary = int(analysis.boundary_index)
        correction_kind = "transient flash"
        replace_frames = int(analysis.recommended_rewind)
        if analysis.micro_flash_candidate:
            correction_kind = "micro-flash"
            replace_frames = 1
        elif enable_exposure_ramp and analysis.exposure_ramp_candidate:
            correction_kind = "exposure ramp"
            replace_frames = 4

        if replace_frames <= 0:
            actions[boundary] = "kept native boundary"
            continue
        if analysis.scene_cut or not (
            analysis.transient_flash_candidate
            or analysis.micro_flash_candidate
            or (enable_exposure_ramp and analysis.exposure_ramp_candidate)
        ):
            actions[boundary] = (
                "kept native boundary; correction guard rejected candidate"
            )
            continue

        previous_index = boundary - 1
        current_index = boundary
        if previous_index < 0 or current_index >= len(images):
            raise ValueError("video seam boundary index is outside decoded chunks")

        previous_raw = images[previous_index]
        current_raw = images[current_index]
        _validate_frames(
            previous_raw,
            f"decoded image chunk {previous_index + 1}",
        )
        _validate_frames(
            current_raw,
            f"decoded image chunk {current_index + 1}",
        )
        previous_plan = groups[previous_index]
        current_plan = groups[current_index]
        previous_total = int(previous_plan["total_frames"])
        previous_trim = int(previous_plan["trim_frames"])
        current_total = int(current_plan["total_frames"])
        current_trim = int(current_plan["trim_frames"])
        if current_trim + replace_frames >= current_total:
            raise ValueError("video seam correction has no retained recovery frame")

        previous_segment = previous_raw[:previous_total][previous_trim:]
        if int(previous_segment.shape[0]) < 1:
            raise ValueError("video seam correction has no previous retained frame")

        # Only the frames that may be changed are cloned.  The recovery frame
        # and previous anchor remain read-only views of their physical groups.
        patch = current_raw[
            current_trim : current_trim + replace_frames
        ].detach().to(device="cpu").clone()
        if int(patch.shape[0]) != replace_frames:
            raise ValueError("video seam correction frames are outside the current chunk")
        previous_anchor = previous_segment[-1].detach().to(
            device="cpu",
            dtype=torch.float32,
        )
        recovery_anchor = current_raw[current_trim + replace_frames].detach().to(
            device="cpu",
            dtype=torch.float32,
        )
        if tuple(previous_anchor.shape) != tuple(recovery_anchor.shape):
            raise ValueError("decoded image geometry changed at video seam")

        for offset in range(replace_frames):
            alpha = float(offset + 1) / float(replace_frames + 1)
            original = patch[offset].to(dtype=torch.float32)
            target = torch.lerp(previous_anchor, recovery_anchor, alpha)
            original_mean = original.mean(dim=(0, 1), keepdim=True)
            target_mean = target.mean(dim=(0, 1), keepdim=True)
            normalized = (original + target_mean - original_mean).clamp(0.0, 1.0)
            patch[offset].copy_(normalized.to(dtype=patch.dtype))

        patches[boundary] = patch
        actions[boundary] = (
            f"normalized exposure/color on {replace_frames} {correction_kind} "
            "boundary frame(s)"
        )

    return patches, actions
