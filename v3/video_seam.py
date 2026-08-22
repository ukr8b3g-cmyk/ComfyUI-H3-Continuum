"""Read-only decoded video-boundary analysis for H3 Continuum V3."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import torch
import torch.nn.functional as F

from .plan import validate_assembly_plan


COMPARE_LONG_SIDE = 192
MAX_REWIND_FRAMES = 2
FLASH_WINDOW_FRAMES = 6
FLASH_TILE_GRID = 4
MIN_FLASH_LUMA_SHIFT = 0.01
MIN_FLASH_REVERSAL = 0.35
MIN_FLASH_GLOBAL_FRACTION = 0.75
MIN_ANOMALY_RATIO = 1.35
MIN_RELATIVE_IMPROVEMENT = 0.06
MIN_AUTO_FLASH_REVERSAL = 0.70
MIN_AUTO_FLASH_IMPROVEMENT = 0.70
SMALLER_SHIFT_TOLERANCE = 0.03
MIN_MICRO_FLASH_LUMA_SHIFT = 0.003
MIN_MICRO_FLASH_REVERSAL = 0.25
MIN_MICRO_FLASH_GLOBAL_FRACTION = 0.70
MAX_EXPOSURE_RAMP_REVERSAL = 0.25
MIN_MOTION_CROSS_DELTA = 0.006
MIN_MOTION_JUMP_RATIO = 1.60


@dataclass(frozen=True)
class VideoBoundaryAnalysis:
    boundary_index: int
    nominal_error: float
    baseline_error: float
    anomaly_ratio: float
    recommended_rewind: int
    best_error: float
    improvement: float
    luma_delta: float
    chroma_delta: float
    edge_delta: float
    scene_cut_score: float
    scene_cut: bool
    flash_luma_shift: float
    flash_reversal: float
    flash_global_fraction: float
    transient_flash_candidate: bool
    cross_frame_delta: float
    motion_baseline_delta: float
    motion_jump_ratio: float
    micro_flash_candidate: bool
    exposure_ramp_candidate: bool
    motion_hitch_candidate: bool
    classification: str
    reason: str


def _validate_frames(frames: Any, label: str) -> None:
    if not torch.is_tensor(frames) or frames.ndim != 4 or frames.shape[-1] < 3:
        raise ValueError(f"{label} must be an IMAGE tensor [T,H,W,C]")
    if int(frames.shape[0]) < 1 or int(frames.shape[1]) < 1 or int(frames.shape[2]) < 1:
        raise ValueError(f"{label} must not be empty")


def _downsample_rgb(frames: torch.Tensor) -> torch.Tensor:
    _validate_frames(frames, "video seam frames")
    rgb = frames[..., :3].detach().to(device="cpu", dtype=torch.float32)
    rgb = rgb.permute(0, 3, 1, 2)
    height, width = int(rgb.shape[-2]), int(rgb.shape[-1])
    scale = min(1.0, COMPARE_LONG_SIDE / float(max(height, width)))
    target_height = max(1, int(round(height * scale)))
    target_width = max(1, int(round(width * scale)))
    if (target_height, target_width) != (height, width):
        rgb = F.interpolate(
            rgb,
            size=(target_height, target_width),
            mode="bilinear",
            align_corners=False,
        )
    rgb = rgb.permute(0, 2, 3, 1).clamp(0.0, 1.0)
    if not bool(torch.isfinite(rgb).all().item()):
        raise ValueError("video seam comparison contains NaN or Inf")
    return rgb


def _luma(frame: torch.Tensor) -> torch.Tensor:
    weights = frame.new_tensor((0.2126, 0.7152, 0.0722))
    return torch.sum(frame * weights, dim=-1)


def _frame_delta(left: torch.Tensor, right: torch.Tensor) -> float:
    return float(torch.mean(torch.abs(left - right)).item())


def _prediction_error(history: torch.Tensor, candidate: torch.Tensor) -> float:
    if int(history.shape[0]) < 3:
        raise ValueError("temporal prediction requires three history frames")
    recent_velocity = history[-1] - history[-2]
    prior_velocity = history[-2] - history[-3]
    predicted = (
        history[-1] + recent_velocity * 0.65 + prior_velocity * 0.35
    ).clamp(0.0, 1.0)
    motion = torch.mean(torch.abs(recent_velocity), dim=-1)
    motion_scale = motion / motion.mean().clamp_min(1.0e-6)
    weights = (1.0 + motion_scale).clamp(1.0, 4.0).unsqueeze(-1)
    value = float(torch.mean((predicted - candidate).square() * weights).item())
    if not math.isfinite(value):
        raise ValueError("video seam prediction score is not finite")
    return max(0.0, value)


def _baseline_prediction_error(previous: torch.Tensor) -> float:
    recent = previous[-min(8, int(previous.shape[0])) :]
    errors = [
        _prediction_error(recent[:index], recent[index])
        for index in range(3, int(recent.shape[0]))
    ]
    if not errors:
        return 0.0
    return float(torch.tensor(errors, dtype=torch.float64).median().item())


def _edge_delta(left: torch.Tensor, right: torch.Tensor) -> float:
    left_y = _luma(left)
    right_y = _luma(right)
    left_x = left_y[:, 1:] - left_y[:, :-1]
    right_x = right_y[:, 1:] - right_y[:, :-1]
    left_v = left_y[1:, :] - left_y[:-1, :]
    right_v = right_y[1:, :] - right_y[:-1, :]
    horizontal = torch.mean(torch.abs(left_x - right_x)) if left_x.numel() else left_y.new_tensor(0.0)
    vertical = torch.mean(torch.abs(left_v - right_v)) if left_v.numel() else left_y.new_tensor(0.0)
    return float(((horizontal + vertical) * 0.5).item())


def _scene_cut_metrics(previous: torch.Tensor, current: torch.Tensor) -> tuple[float, bool]:
    cross_delta = _frame_delta(previous[-1], current[0])
    previous_internal = _frame_delta(previous[-2], previous[-1])
    if int(current.shape[0]) >= 3:
        current_internal = 0.5 * (
            _frame_delta(current[0], current[1])
            + _frame_delta(current[1], current[2])
        )
    elif int(current.shape[0]) == 2:
        current_internal = _frame_delta(current[0], current[1])
    else:
        current_internal = cross_delta
    denominator = cross_delta + previous_internal + current_internal + 1.0e-8
    score = cross_delta / denominator
    persistent_new_scene = (
        int(current.shape[0]) >= 3
        and cross_delta >= 0.12
        and current_internal <= cross_delta * 0.35
        and cross_delta >= max(0.12, previous_internal * 3.0)
    )
    return max(0.0, min(1.0, score)), persistent_new_scene


def _transient_flash_metrics(
    previous: torch.Tensor,
    current: torch.Tensor,
) -> tuple[float, float, float]:
    """Measure a broad boundary exposure pulse that quickly returns."""

    previous_y = _luma(previous[-1])
    current_y = _luma(current[:FLASH_WINDOW_FRAMES])
    shifts = torch.mean(current_y - previous_y.unsqueeze(0), dim=(1, 2))
    initial_shift = float(torch.abs(shifts[0]).item())
    if int(shifts.shape[0]) > 1 and initial_shift > 1.0e-8:
        closest_later = float(torch.min(torch.abs(shifts[1:])).item())
        reversal = max(0.0, min(1.0, 1.0 - closest_later / initial_shift))
    else:
        reversal = 0.0

    height, width = int(previous_y.shape[0]), int(previous_y.shape[1])
    tile_height = max(1, height // FLASH_TILE_GRID)
    tile_width = max(1, width // FLASH_TILE_GRID)
    delta = current_y[0] - previous_y
    sign = 1.0 if float(shifts[0].item()) >= 0.0 else -1.0
    tile_matches = []
    for top in range(0, height, tile_height):
        for left in range(0, width, tile_width):
            tile = delta[
                top : min(height, top + tile_height),
                left : min(width, left + tile_width),
            ]
            tile_shift = float(torch.mean(tile).item())
            tile_matches.append(
                tile_shift * sign >= min(MIN_FLASH_LUMA_SHIFT * 0.5, initial_shift * 0.5)
            )
    global_fraction = sum(tile_matches) / max(1, len(tile_matches))
    return initial_shift, reversal, float(global_fraction)


def _temporal_motion_metrics(
    previous: torch.Tensor,
    current: torch.Tensor,
) -> tuple[float, float, float]:
    """Compare the boundary transition with nearby native frame motion."""

    cross_delta = _frame_delta(previous[-1], current[0])
    internal_deltas: list[float] = []
    previous_start = max(1, int(previous.shape[0]) - 5)
    for index in range(previous_start, int(previous.shape[0])):
        internal_deltas.append(_frame_delta(previous[index - 1], previous[index]))
    current_limit = min(5, int(current.shape[0]))
    for index in range(1, current_limit):
        internal_deltas.append(_frame_delta(current[index - 1], current[index]))
    if internal_deltas:
        baseline = float(
            torch.tensor(internal_deltas, dtype=torch.float64).median().item()
        )
    else:
        baseline = 0.0
    if cross_delta <= 1.0e-8:
        ratio = 0.0
    else:
        ratio = cross_delta / max(baseline, 1.0e-5)
    return cross_delta, baseline, ratio


def analyze_video_boundary(
    previous_images: torch.Tensor,
    current_raw_images: torch.Tensor,
    *,
    trim_frames: int,
    boundary_index: int = 1,
) -> VideoBoundaryAnalysis:
    """Analyze one boundary without modifying either input tensor."""

    _validate_frames(previous_images, "previous decoded image chunk")
    _validate_frames(current_raw_images, "current decoded image chunk")
    trim_frames = int(trim_frames)
    if int(previous_images.shape[0]) < 4:
        raise ValueError("video seam analysis requires four previous frames")
    if trim_frames < 0 or trim_frames >= int(current_raw_images.shape[0]):
        raise ValueError("video seam trim position is outside the current chunk")
    if trim_frames + 3 > int(current_raw_images.shape[0]):
        raise ValueError("video seam analysis requires three retained current frames")

    previous = _downsample_rgb(previous_images[-8:])
    candidate_start = max(0, trim_frames - MAX_REWIND_FRAMES)
    current = _downsample_rgb(
        current_raw_images[
            candidate_start : trim_frames + FLASH_WINDOW_FRAMES
        ]
    )
    nominal_index = trim_frames - candidate_start
    nominal = current[nominal_index]

    candidate_errors: dict[int, float] = {}
    maximum_rewind = min(MAX_REWIND_FRAMES, trim_frames)
    for rewind in range(maximum_rewind + 1):
        candidate = current[nominal_index - rewind]
        candidate_errors[rewind] = _prediction_error(previous, candidate)

    nominal_error = candidate_errors[0]
    minimum_error = min(candidate_errors.values())
    tolerance = minimum_error * SMALLER_SHIFT_TOLERANCE + 1.0e-10
    best_rewind = min(
        rewind
        for rewind, error in candidate_errors.items()
        if error <= minimum_error + tolerance
    )
    best_error = candidate_errors[best_rewind]
    baseline_error = _baseline_prediction_error(previous)
    anomaly_ratio = nominal_error / max(baseline_error, 1.0e-5)
    improvement = (nominal_error - best_error) / max(nominal_error, 1.0e-12)

    previous_edge = previous[-1]
    previous_y = _luma(previous_edge)
    nominal_y = _luma(nominal)
    luma_delta = float(torch.mean(torch.abs(previous_y - nominal_y)).item())
    previous_chroma = previous_edge - previous_y.unsqueeze(-1)
    nominal_chroma = nominal - nominal_y.unsqueeze(-1)
    chroma_delta = float(
        torch.mean(torch.abs(previous_chroma - nominal_chroma)).item()
    )
    edge_delta = _edge_delta(previous_edge, nominal)
    scene_score, scene_cut = _scene_cut_metrics(
        previous,
        current[nominal_index : nominal_index + 3],
    )
    flash_luma_shift, flash_reversal, flash_global_fraction = (
        _transient_flash_metrics(previous, current[nominal_index:])
    )
    cross_frame_delta, motion_baseline_delta, motion_jump_ratio = (
        _temporal_motion_metrics(previous, current[nominal_index:])
    )
    transient_flash_candidate = (
        not scene_cut
        and flash_luma_shift >= MIN_FLASH_LUMA_SHIFT
        and flash_reversal >= MIN_FLASH_REVERSAL
        and flash_global_fraction >= MIN_FLASH_GLOBAL_FRACTION
    )
    micro_flash_candidate = (
        not scene_cut
        and not transient_flash_candidate
        and flash_luma_shift >= MIN_MICRO_FLASH_LUMA_SHIFT
        and flash_reversal >= MIN_MICRO_FLASH_REVERSAL
        and flash_global_fraction >= MIN_MICRO_FLASH_GLOBAL_FRACTION
    )
    exposure_ramp_candidate = (
        not scene_cut
        and not transient_flash_candidate
        and not micro_flash_candidate
        and anomaly_ratio >= MIN_ANOMALY_RATIO
        and flash_luma_shift >= MIN_FLASH_LUMA_SHIFT
        and flash_reversal < MAX_EXPOSURE_RAMP_REVERSAL
        and flash_global_fraction >= MIN_FLASH_GLOBAL_FRACTION
    )
    motion_hitch_candidate = (
        not scene_cut
        and not transient_flash_candidate
        and not micro_flash_candidate
        and not exposure_ramp_candidate
        and cross_frame_delta >= MIN_MOTION_CROSS_DELTA
        and motion_jump_ratio >= MIN_MOTION_JUMP_RATIO
    )
    if scene_cut:
        classification = "scene_cut"
    elif transient_flash_candidate:
        classification = "transient_flash"
    elif micro_flash_candidate:
        classification = "micro_flash"
    elif exposure_ramp_candidate:
        classification = "exposure_ramp"
    elif motion_hitch_candidate:
        classification = "motion_hitch"
    else:
        classification = "clean_boundary"

    recommended_rewind = 0
    if scene_cut:
        reason = "kept nominal boundary; persistent content change resembles a scene cut"
    elif best_rewind == 0:
        reason = "kept nominal boundary; it has the lowest prediction error"
    elif (
        transient_flash_candidate
        and flash_reversal >= MIN_AUTO_FLASH_REVERSAL
        and improvement >= MIN_AUTO_FLASH_IMPROVEMENT
    ):
        recommended_rewind = best_rewind
        reason = f"mild transient flash recommends correcting {best_rewind} frame(s)"
    elif anomaly_ratio < MIN_ANOMALY_RATIO:
        reason = "kept nominal boundary; anomaly ratio is below the analysis threshold"
    elif improvement < MIN_RELATIVE_IMPROVEMENT:
        reason = "kept nominal boundary; candidate improvement is below 6%"
    else:
        recommended_rewind = best_rewind
        reason = f"analysis recommends shift {-best_rewind:+d} frame(s)"

    return VideoBoundaryAnalysis(
        boundary_index=int(boundary_index),
        nominal_error=nominal_error,
        baseline_error=baseline_error,
        anomaly_ratio=anomaly_ratio,
        recommended_rewind=recommended_rewind,
        best_error=best_error,
        improvement=improvement,
        luma_delta=luma_delta,
        chroma_delta=chroma_delta,
        edge_delta=edge_delta,
        scene_cut_score=scene_score,
        scene_cut=scene_cut,
        flash_luma_shift=flash_luma_shift,
        flash_reversal=flash_reversal,
        flash_global_fraction=flash_global_fraction,
        transient_flash_candidate=transient_flash_candidate,
        cross_frame_delta=cross_frame_delta,
        motion_baseline_delta=motion_baseline_delta,
        motion_jump_ratio=motion_jump_ratio,
        micro_flash_candidate=micro_flash_candidate,
        exposure_ramp_candidate=exposure_ramp_candidate,
        motion_hitch_candidate=motion_hitch_candidate,
        classification=classification,
        reason=reason,
    )


def analyze_decoded_boundaries(
    *,
    images: list[Any],
    assembly_plan: dict[str, Any],
) -> list[VideoBoundaryAnalysis]:
    """Analyze every decoded chunk boundary without changing decoded content."""

    plan = validate_assembly_plan(assembly_plan)
    chunks = list(
        plan["decode_groups"] if "decode_groups" in plan else plan["chunks"]
    )
    if len(images) != len(chunks):
        raise ValueError("decoded image count does not match the assembly plan")
    analyses: list[VideoBoundaryAnalysis] = []
    for index in range(1, len(chunks)):
        previous_raw = images[index - 1]
        current_raw = images[index]
        previous_plan = chunks[index - 1]
        current_plan = chunks[index]
        _validate_frames(previous_raw, f"decoded image chunk {index}")
        _validate_frames(current_raw, f"decoded image chunk {index + 1}")
        previous_total = int(previous_plan["total_frames"])
        previous_trim = int(previous_plan["trim_frames"])
        current_total = int(current_plan["total_frames"])
        current_trim = int(current_plan["trim_frames"])
        previous_segment = previous_raw[:previous_total][previous_trim:]
        current_segment = current_raw[:current_total]
        analyses.append(
            analyze_video_boundary(
                previous_segment,
                current_segment,
                trim_frames=current_trim,
                boundary_index=index,
            )
        )
    return analyses


def correct_decoded_boundaries(
    *,
    images: list[Any],
    assembly_plan: dict[str, Any],
    analyses: list[VideoBoundaryAnalysis],
    enable_exposure_ramp: bool = False,
) -> tuple[list[Any], dict[int, str]]:
    """Normalize qualified transient exposure shifts without changing motion."""

    plan = validate_assembly_plan(assembly_plan)
    chunks = list(
        plan["decode_groups"] if "decode_groups" in plan else plan["chunks"]
    )
    if len(images) != len(chunks):
        raise ValueError("decoded image count does not match the assembly plan")
    corrected = list(images)
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
            actions[boundary] = "kept native boundary; correction guard rejected candidate"
            continue
        previous_index = boundary - 1
        current_index = boundary
        if previous_index < 0 or current_index >= len(images):
            raise ValueError("video seam boundary index is outside decoded chunks")
        previous_raw = images[previous_index]
        current_raw = images[current_index]
        _validate_frames(previous_raw, f"decoded image chunk {previous_index + 1}")
        _validate_frames(current_raw, f"decoded image chunk {current_index + 1}")
        previous_plan = chunks[previous_index]
        current_plan = chunks[current_index]
        previous_total = int(previous_plan["total_frames"])
        previous_trim = int(previous_plan["trim_frames"])
        current_total = int(current_plan["total_frames"])
        current_trim = int(current_plan["trim_frames"])
        if current_trim + replace_frames >= current_total:
            raise ValueError("video seam correction has no retained recovery frame")
        previous_segment = previous_raw[:previous_total][previous_trim:]
        if int(previous_segment.shape[0]) < 1:
            raise ValueError("video seam correction has no previous retained frame")
        current_cpu = current_raw.detach().to(device="cpu").clone()
        previous_anchor = previous_segment[-1].detach().to(
            device="cpu", dtype=torch.float32
        )
        recovery_anchor = current_cpu[current_trim + replace_frames].to(
            dtype=torch.float32
        )
        if tuple(previous_anchor.shape) != tuple(recovery_anchor.shape):
            raise ValueError("decoded image geometry changed at video seam")
        for offset in range(replace_frames):
            alpha = float(offset + 1) / float(replace_frames + 1)
            original = current_cpu[current_trim + offset].to(dtype=torch.float32)
            target = torch.lerp(previous_anchor, recovery_anchor, alpha)
            original_mean = original.mean(dim=(0, 1), keepdim=True)
            target_mean = target.mean(dim=(0, 1), keepdim=True)
            normalized = (original + target_mean - original_mean).clamp(0.0, 1.0)
            current_cpu[current_trim + offset].copy_(
                normalized.to(dtype=current_cpu.dtype)
            )
        corrected[current_index] = current_cpu
        actions[boundary] = (
            f"normalized exposure/color on {replace_frames} {correction_kind} "
            "boundary frame(s)"
        )
    return corrected, actions


def format_video_boundary_analysis(
    analysis: VideoBoundaryAnalysis,
    *,
    action: str = "analysis only",
) -> str:
    shift = -int(analysis.recommended_rewind)
    return (
        f"video seam {analysis.boundary_index}->{analysis.boundary_index + 1}: "
        f"anomaly={analysis.anomaly_ratio:.3f}, "
        f"prediction={analysis.nominal_error:.6f}->{analysis.best_error:.6f}, "
        f"improvement={analysis.improvement:.1%}, shift={shift:+d}, "
        f"luma={analysis.luma_delta:.6f}, chroma={analysis.chroma_delta:.6f}, "
        f"edge={analysis.edge_delta:.6f}, "
        f"scene_cut={'yes' if analysis.scene_cut else 'no'} "
        f"flash_shift={analysis.flash_luma_shift:.6f}, "
        f"flash_reversal={analysis.flash_reversal:.1%}, "
        f"flash_global={analysis.flash_global_fraction:.1%}, "
        f"flash_candidate={'yes' if analysis.transient_flash_candidate else 'no'} "
        f"class={analysis.classification}, "
        f"cross={analysis.cross_frame_delta:.6f}, "
        f"motion_base={analysis.motion_baseline_delta:.6f}, "
        f"motion_jump={analysis.motion_jump_ratio:.2f}x, "
        f"micro_flash={'yes' if analysis.micro_flash_candidate else 'no'}, "
        f"exposure_ramp={'yes' if analysis.exposure_ramp_candidate else 'no'}, "
        f"motion_hitch={'yes' if analysis.motion_hitch_candidate else 'no'} "
        f"({analysis.reason}); action={action}"
    )
