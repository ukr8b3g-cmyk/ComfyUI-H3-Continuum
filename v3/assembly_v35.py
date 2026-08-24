"""V3.5 direct-write assembly with a manual RAM or file-backed IMAGE buffer."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
import math
from pathlib import Path
import time
from typing import Any, Callable, Mapping

import torch

from ..constants import (
    DIAGNOSTICS_FULL,
    DIAGNOSTICS_OFF,
    normalize_diagnostics_mode,
)
from ..hardening import assemble_with_hardening
from ..media import validate_audio
from ..v2.seam_guard import correct_audio_seam
from .assembly import (
    AUDIO_SEAM_AUTO,
    AUDIO_SEAM_OPTIONS,
    VIDEO_SEAM_ANALYZE,
    VIDEO_SEAM_ANALYSIS_OPTIONS,
    VIDEO_SEAM_AUTO,
    VIDEO_SEAM_AUTO_2,
    VIDEO_SEAM_OFF,
)
from .file_backed_buffer import (
    BUFFER_BACKEND_AUTO,
    BUFFER_BACKEND_DISK,
    BUFFER_BACKEND_OPTIONS,
    BUFFER_BACKEND_RAM,
    allocate_file_backed_image,
    format_auto_buffer_decision,
    select_auto_buffer_backend,
)
from .plan import FPS, validate_assembly_plan


_COPY_BATCH_FRAMES = 8


def _check_interrupted(
    interrupt_check: Callable[[], None] | None,
) -> None:
    """Honor ComfyUI's normal ESC interrupt without requiring Core in tests."""

    if interrupt_check is not None:
        interrupt_check()
        return
    try:
        from comfy.model_management import throw_exception_if_processing_interrupted
    except ModuleNotFoundError:
        return
    throw_exception_if_processing_interrupted()


@dataclass(frozen=True)
class CopySpan:
    """Map a half-open natural-timeline interval into the output buffer."""

    source_start: int
    source_stop: int
    destination_start: int


class _RamAllocation(AbstractContextManager):
    """Match the provisional file-backed allocation interface for RAM."""

    def __init__(self, shape: tuple[int, ...], dtype: torch.dtype):
        self.tensor = torch.empty(shape, dtype=dtype, device="cpu")
        self.record = None
        self._published = False

    def publish(self) -> torch.Tensor:
        if self._published:
            raise RuntimeError("RAM assembly buffer was already published")
        self._published = True
        return self.tensor

    def __exit__(self, exc_type, exc, traceback) -> bool:
        return False


def _video_copy_spans(
    *,
    natural_frames: int,
    output_frames: int,
    preserve_final_frame: bool,
) -> tuple[CopySpan, ...]:
    if output_frames >= natural_frames:
        return (CopySpan(0, natural_frames, 0),)
    if preserve_final_frame and output_frames >= 2:
        return (
            CopySpan(0, output_frames - 1, 0),
            CopySpan(natural_frames - 1, natural_frames, output_frames - 1),
        )
    return (CopySpan(0, output_frames, 0),)


def _copy_natural_interval(
    destination: torch.Tensor,
    source: torch.Tensor,
    *,
    natural_start: int,
    spans: tuple[CopySpan, ...],
    interrupt_check: Callable[[], None] | None = None,
) -> None:
    natural_stop = natural_start + int(source.shape[0])
    for span in spans:
        overlap_start = max(natural_start, int(span.source_start))
        overlap_stop = min(natural_stop, int(span.source_stop))
        if overlap_stop <= overlap_start:
            continue
        source_start = overlap_start - natural_start
        destination_start = int(span.destination_start) + (
            overlap_start - int(span.source_start)
        )
        frame_count = overlap_stop - overlap_start
        for offset in range(0, frame_count, _COPY_BATCH_FRAMES):
            _check_interrupted(interrupt_check)
            batch_frames = min(_COPY_BATCH_FRAMES, frame_count - offset)
            source_batch_start = source_start + offset
            destination_batch_start = destination_start + offset
            destination[
                destination_batch_start : destination_batch_start + batch_frames
            ].copy_(
                source[source_batch_start : source_batch_start + batch_frames]
            )


def _repeat_final_video_frame(
    destination: torch.Tensor,
    *,
    natural_frames: int,
    output_frames: int,
    interrupt_check: Callable[[], None] | None,
) -> None:
    for destination_start in range(
        natural_frames,
        output_frames,
        _COPY_BATCH_FRAMES,
    ):
        _check_interrupted(interrupt_check)
        destination_stop = min(
            output_frames,
            destination_start + _COPY_BATCH_FRAMES,
        )
        destination[destination_start:destination_stop].copy_(
            destination[natural_frames - 1 : natural_frames].expand(
                destination_stop - destination_start,
                *destination.shape[1:],
            )
        )


def _copy_audio_segment(
    destination: torch.Tensor,
    waveform: torch.Tensor,
    *,
    trim_samples: int,
) -> None:
    """Reproduce timeline slicing/padding without concatenating a waveform."""

    wanted = int(destination.shape[-1])
    trim_samples = max(0, int(trim_samples))
    available = max(0, min(wanted, int(waveform.shape[-1]) - trim_samples))
    if available > 0:
        destination[..., :available].copy_(
            waveform[..., trim_samples : trim_samples + available]
        )
    if available >= wanted:
        return
    if available > 0:
        destination[..., available:].copy_(
            destination[..., available - 1 : available].expand(
                *destination.shape[:-1],
                wanted - available,
            )
        )
    else:
        destination.zero_()


def adjust_audio_duration_direct(
    audio: Mapping[str, Any],
    *,
    target_frames: int,
    preserve_final_audio_anchor: bool,
) -> tuple[dict[str, Any], int]:
    """Apply the legacy audio trim/pad values using direct allocation and copy."""

    waveform, sample_rate = validate_audio(audio)
    waveform = waveform.detach().to(device="cpu")
    sample_rate = int(sample_rate)
    target_samples = int(round(int(target_frames) / FPS * sample_rate))
    original_samples = int(waveform.shape[-1])
    delta_samples = target_samples - original_samples
    if delta_samples == 0:
        return {"waveform": waveform, "sample_rate": sample_rate}, 0

    output = torch.empty(
        (*waveform.shape[:-1], target_samples),
        dtype=waveform.dtype,
        device="cpu",
    )
    if delta_samples < 0:
        if preserve_final_audio_anchor and target_samples > 1:
            tail_samples = min(
                max(1, int(round(sample_rate / FPS))),
                target_samples,
                original_samples,
            )
            head_samples = target_samples - tail_samples
            if head_samples > 0:
                output[..., :head_samples].copy_(waveform[..., :head_samples])
            output[..., head_samples:].copy_(waveform[..., -tail_samples:])
            fade = min(
                int(round(sample_rate * 0.005)),
                head_samples,
                tail_samples,
            )
            if fade > 0:
                start = output[..., head_samples - 1 : head_samples].to(
                    dtype=output.dtype
                )
                alpha = torch.linspace(
                    0.0,
                    1.0,
                    fade,
                    dtype=output.dtype,
                    device=output.device,
                ).reshape(*([1] * (output.ndim - 1)), fade)
                tail_head = output[..., head_samples : head_samples + fade]
                tail_head.copy_(start * (1.0 - alpha) + tail_head * alpha)
        else:
            output.copy_(waveform[..., :target_samples])
    else:
        if original_samples > 0:
            output[..., :original_samples].copy_(waveform)
            output[..., original_samples:].copy_(
                waveform[..., -1:].expand(
                    *waveform.shape[:-1],
                    delta_samples,
                )
            )
        else:
            output.zero_()
    return {"waveform": output, "sample_rate": sample_rate}, delta_samples


def _prepare_video_seam(
    *,
    images: list[Any],
    plan: dict[str, Any],
    mode: str,
) -> tuple[list[Any], dict[int, torch.Tensor], dict[int, str], Exception | None]:
    if mode == VIDEO_SEAM_OFF:
        return [], {}, {}, None
    analyses: list[Any] = []
    try:
        from .video_seam import analyze_decoded_boundaries

        analyses = analyze_decoded_boundaries(
            images=images,
            assembly_plan=plan,
        )
        patches: dict[int, torch.Tensor] = {}
        actions: dict[int, str] = {}
        if mode in (VIDEO_SEAM_AUTO, VIDEO_SEAM_AUTO_2):
            from .video_seam_v35 import build_boundary_patches

            patches, actions = build_boundary_patches(
                images=images,
                assembly_plan=plan,
                analyses=analyses,
                enable_exposure_ramp=mode == VIDEO_SEAM_AUTO_2,
            )
        return analyses, patches, actions, None
    except Exception as exc:
        # Match V3.4's all-native fallback: no partial patch is retained.
        return analyses, {}, {}, exc


def _video_seam_status(mode: str) -> str:
    if mode == VIDEO_SEAM_OFF:
        return "Video seam correction is disabled."
    if mode == VIDEO_SEAM_ANALYZE:
        return "Video Seam: Analyze Only; decoded frames and audio are unchanged."
    if mode == VIDEO_SEAM_AUTO:
        return "Video Seam: Auto; guarded transient and micro-flash correction enabled."
    return (
        "Video Seam: Auto 2 (Experimental); guarded transient, micro-flash, "
        "and exposure-ramp correction enabled."
    )


def _format_video_seam_lines(
    *,
    mode: str,
    analyses: list[Any],
    actions: dict[int, str],
    error: Exception | None,
) -> list[str]:
    if mode == VIDEO_SEAM_OFF:
        return []
    if error is not None:
        return [
            f"Video Seam {mode}: native output preserved; analysis unavailable "
            f"({type(error).__name__}: {error})"
        ]
    from .video_seam import format_video_boundary_analysis

    lines = [
        format_video_boundary_analysis(
            item,
            action=(
                "analysis only"
                if mode == VIDEO_SEAM_ANALYZE
                else actions.get(item.boundary_index, "kept native boundary")
            ),
        )
        for item in analyses
    ]
    if not lines:
        lines.append(f"Video Seam {mode}: no decoded chunk boundary to analyze.")
    return lines


def _format_elapsed(seconds: float) -> str:
    total = max(0.0, float(seconds))
    hours, remainder = divmod(total, 3600.0)
    minutes, seconds = divmod(remainder, 60.0)
    return f"{int(hours):02d}:{int(minutes):02d}:{seconds:05.2f}"


def _write_assembly(
    *,
    image_buffer: torch.Tensor,
    images: list[Any],
    audio: list[Any],
    plan: dict[str, Any],
    exact_total_duration: bool,
    audio_seam: str,
    video_seam: str,
    diagnostics: str,
    natural_frames: int,
    output_frames: int,
    video_spans: tuple[CopySpan, ...],
    seam_patches: dict[int, torch.Tensor],
    seam_analyses: list[Any],
    seam_actions: dict[int, str],
    seam_error: Exception | None,
    buffer_backend: str,
    auto_decision_report: str | None,
    final_audio_override: Mapping[str, Any] | None,
    final_audio_source: str | None,
    interrupt_check: Callable[[], None] | None,
) -> tuple[dict[str, Any], str]:
    diagnostics_mode = normalize_diagnostics_mode(diagnostics)
    units = list(plan.get("decode_groups") or plan["chunks"])
    first_waveform, audio_rate = validate_audio(audio[0])
    first_waveform = first_waveform.detach().to(device="cpu")
    audio_rate = int(audio_rate)
    natural_samples = int(round(natural_frames / FPS * audio_rate))
    audio_buffer = torch.empty(
        (*first_waveform.shape[:-1], natural_samples),
        dtype=first_waveform.dtype,
        device="cpu",
    )
    reports = [
        "H3 Continuum Assemble V3.5",
        f"Audio Seam: {audio_seam}. {_video_seam_status(video_seam)}",
        f"Buffer Backend: {buffer_backend}; IMAGE direct-write "
        f"frames={output_frames}, bytes={image_buffer.numel() * image_buffer.element_size()}; "
        "no final full IMAGE copy.",
    ]
    if auto_decision_report is not None:
        reports.append(auto_decision_report)

    frame_cursor = 0
    for index, (raw_images, raw_audio, unit) in enumerate(
        zip(images, audio, units),
        start=1,
    ):
        _check_interrupted(interrupt_check)
        total_frames = int(unit["total_frames"])
        trim_frames = int(unit["trim_frames"])
        net_frames = int(unit["net_frames"])
        raw_images_cpu = raw_images.detach().to(device="cpu")
        retained_images = raw_images_cpu[trim_frames:total_frames]
        if int(retained_images.shape[0]) != net_frames:
            raise ValueError(
                f"decoded image chunk {index} retained {retained_images.shape[0]} "
                f"frames; plan expects {net_frames}"
            )
        _copy_natural_interval(
            image_buffer,
            retained_images,
            natural_start=frame_cursor,
            spans=video_spans,
            interrupt_check=interrupt_check,
        )

        _check_interrupted(interrupt_check)
        waveform, sample_rate = validate_audio(raw_audio)
        waveform = waveform.detach().to(device="cpu")
        sample_rate = int(sample_rate)
        if sample_rate != audio_rate:
            raise ValueError(
                f"audio sample rate changed between chunks: {audio_rate} -> {sample_rate}"
            )
        frame_stop = frame_cursor + net_frames
        sample_start = int(round(frame_cursor / FPS * sample_rate))
        sample_stop = int(round(frame_stop / FPS * sample_rate))
        seam_report = None
        if index > 1 and audio_seam == AUDIO_SEAM_AUTO:
            try:
                cut_sample = int(round(trim_frames / FPS * sample_rate))
                patch, metrics, fade_samples, level_gain, dc_bias = correct_audio_seam(
                    audio_buffer[..., :sample_start],
                    waveform,
                    sample_rate=sample_rate,
                    cut_sample=cut_sample,
                )
                if patch is not None and int(patch.shape[-1]) > 0:
                    patch_start = sample_start - int(patch.shape[-1])
                    if patch_start < 0:
                        raise ValueError("audio seam patch starts before the output")
                    audio_buffer[..., patch_start:sample_start].copy_(patch)
                seam_report = (
                    f"audio seam {index-1}->{index}: "
                    f"corr={metrics.correlation_before:.4f}->"
                    f"{metrics.correlation_after:.4f}, "
                    f"jump={metrics.boundary_jump_before:.6f}->"
                    f"{metrics.boundary_jump_after:.6f}, "
                    f"fade={fade_samples} samples"
                )
                if diagnostics_mode == DIAGNOSTICS_FULL:
                    seam_report += (
                        f", offset={metrics.offset_samples:+d}, "
                        f"gain={level_gain:.4f}, dc={dc_bias:+.6f}"
                    )
            except Exception as exc:
                seam_report = (
                    f"audio seam {index-1}->{index}: fallback to native boundary "
                    f"({type(exc).__name__}: {exc})"
                )

        trim_samples = int(round(trim_frames / FPS * sample_rate))
        _copy_audio_segment(
            audio_buffer[..., sample_start:sample_stop],
            waveform,
            trim_samples=trim_samples,
        )
        if diagnostics_mode != DIAGNOSTICS_OFF:
            reports.append(
                f"assembled decoded chunk {index}: {net_frames} retained frames, "
                f"cumulative {frame_stop}/{natural_frames}"
            )
            if seam_report:
                reports.append(seam_report)
        frame_cursor = frame_stop

    if frame_cursor != natural_frames:
        raise RuntimeError(
            f"V3.5 assembly cursor mismatch: {frame_cursor} != {natural_frames}"
        )

    unit_starts: list[int] = []
    cursor = 0
    for unit in units:
        unit_starts.append(cursor)
        cursor += int(unit["net_frames"])
    for boundary, patch in seam_patches.items():
        _check_interrupted(interrupt_check)
        if boundary <= 0 or boundary >= len(unit_starts):
            raise ValueError("V3.5 video seam patch boundary is outside decode groups")
        _copy_natural_interval(
            image_buffer,
            patch,
            natural_start=unit_starts[boundary],
            spans=video_spans,
            interrupt_check=interrupt_check,
        )

    if output_frames > natural_frames:
        _repeat_final_video_frame(
            image_buffer,
            natural_frames=natural_frames,
            output_frames=output_frames,
            interrupt_check=interrupt_check,
        )

    _check_interrupted(interrupt_check)
    result_audio: dict[str, Any] = {
        "waveform": audio_buffer,
        "sample_rate": audio_rate,
    }
    duration_report = ""
    if exact_total_duration:
        preserve_anchor = bool(
            plan.get("preserve_final_frame", False)
            and output_frames < natural_frames
            and output_frames >= 2
        )
        result_audio, delta_samples = adjust_audio_duration_direct(
            result_audio,
            target_frames=output_frames,
            preserve_final_audio_anchor=preserve_anchor,
        )
        adjustment = output_frames - natural_frames
        mode = (
            "final anchor preserved; pre-tail trim"
            if preserve_anchor
            else "tail trim/pad"
        )
        duration_report = (
            f"Exact-duration adjustment: frames {natural_frames}->{output_frames} "
            f"({adjustment:+d}), audio samples correction {delta_samples:+d}; {mode}."
        )

    driving_audio_report = ""
    if final_audio_override is not None:
        result_audio = dict(final_audio_override)
        if exact_total_duration:
            result_audio, _ = adjust_audio_duration_direct(
                result_audio,
                target_frames=output_frames,
                preserve_final_audio_anchor=False,
            )
        waveform, selected_rate = validate_audio(result_audio)
        result_audio = {
            "waveform": waveform,
            "sample_rate": int(selected_rate),
        }
        driving_audio_report = (
            "Driving Audio: preserved source selected from "
            f"{final_audio_source or 'direct input'}; "
            f"sample_rate={int(selected_rate)}, samples={int(waveform.shape[-1])}; "
            "generated audio and Audio Seam bypassed."
        )

    reports.append(
        f"Assembled {len(units)} physical decoded group(s) into "
        f"{output_frames} frames with cumulative sample-boundary alignment."
    )
    if duration_report:
        reports.append(duration_report)
    if driving_audio_report:
        reports.append(driving_audio_report)
    runtime_started_at = plan.get("_runtime_started_at")
    if isinstance(runtime_started_at, (int, float)):
        elapsed = time.perf_counter() - float(runtime_started_at)
        if math.isfinite(elapsed) and elapsed >= 0.0:
            reports.append(f"Total workflow elapsed: {_format_elapsed(elapsed)}")
    reports.extend(
        _format_video_seam_lines(
            mode=video_seam,
            analyses=seam_analyses,
            actions=seam_actions,
            error=seam_error,
        )
    )
    return result_audio, "\n".join(reports)


def _assemble_decoded_chunks_v35_core(
    *,
    images: list[Any],
    audio: list[Any],
    assembly_plan: dict[str, Any],
    exact_total_duration: bool,
    audio_seam: str,
    video_seam: str,
    diagnostics: str,
    buffer_backend: str,
    backing_root: str | Path | None = None,
    final_audio_override: Mapping[str, Any] | None = None,
    final_audio_source: str | None = None,
    interrupt_check: Callable[[], None] | None = None,
):
    plan = validate_assembly_plan(assembly_plan)
    if audio_seam not in AUDIO_SEAM_OPTIONS:
        raise ValueError(f"unknown Audio Seam mode: {audio_seam!r}")
    if video_seam not in VIDEO_SEAM_ANALYSIS_OPTIONS:
        raise ValueError(f"unknown Video Seam mode: {video_seam!r}")
    if buffer_backend not in BUFFER_BACKEND_OPTIONS:
        raise ValueError(f"unknown Buffer Backend: {buffer_backend!r}")
    units = list(plan.get("decode_groups") or plan["chunks"])
    natural_frames = sum(int(unit["net_frames"]) for unit in units)
    output_frames = (
        int(plan["target_frames"])
        if bool(exact_total_duration)
        else natural_frames
    )
    if natural_frames <= 0 or output_frames <= 0:
        raise ValueError("V3.5 assembly frame counts must be positive")
    first_image = images[0]
    shape = (output_frames, *tuple(int(value) for value in first_image.shape[1:]))
    video_spans = _video_copy_spans(
        natural_frames=natural_frames,
        output_frames=output_frames,
        preserve_final_frame=bool(plan.get("preserve_final_frame", False)),
    )
    analyses, patches, actions, analysis_error = _prepare_video_seam(
        images=images,
        plan=plan,
        mode=video_seam,
    )

    resolved_backend = buffer_backend
    resolved_backing_root = backing_root
    auto_decision_report = None
    if buffer_backend == BUFFER_BACKEND_AUTO:
        final_image_bytes = (
            math.prod(shape) * first_image.element_size()
        )
        decision = select_auto_buffer_backend(
            final_image_bytes,
            backing_root=backing_root,
        )
        resolved_backend = decision.selected_backend
        resolved_backing_root = decision.backing_root
        auto_decision_report = format_auto_buffer_decision(decision)

    allocation: Any
    if resolved_backend == BUFFER_BACKEND_RAM:
        allocation = _RamAllocation(shape, first_image.dtype)
    else:
        allocation = allocate_file_backed_image(
            shape,
            dtype=first_image.dtype,
            backing_root=resolved_backing_root,
        )
    with allocation:
        # The file exists at this point, so an ESC received immediately before
        # assembly exercises the same unpublished cleanup path as a mid-copy
        # cancellation.
        _check_interrupted(interrupt_check)
        result_audio, report = _write_assembly(
            image_buffer=allocation.tensor,
            images=images,
            audio=audio,
            plan=plan,
            exact_total_duration=bool(exact_total_duration),
            audio_seam=audio_seam,
            video_seam=video_seam,
            diagnostics=diagnostics,
            natural_frames=natural_frames,
            output_frames=output_frames,
            video_spans=video_spans,
            seam_patches=patches,
            seam_analyses=analyses,
            seam_actions=actions,
            seam_error=analysis_error,
            buffer_backend=(
                resolved_backend
                if buffer_backend != BUFFER_BACKEND_AUTO
                else f"Auto -> {resolved_backend}"
            ),
            auto_decision_report=auto_decision_report,
            final_audio_override=final_audio_override,
            final_audio_source=final_audio_source,
            interrupt_check=interrupt_check,
        )
        result_images = allocation.publish()
    return result_images, result_audio, report


def assemble_decoded_chunks_v35(
    *,
    images: list[Any],
    audio: list[Any],
    assembly_plan: dict[str, Any],
    exact_total_duration: bool,
    audio_seam: str,
    video_seam: str,
    diagnostics: str,
    buffer_backend: str,
    backing_root: str | Path | None = None,
    final_audio_override: Mapping[str, Any] | None = None,
    final_audio_source: str | None = None,
    interrupt_check: Callable[[], None] | None = None,
):
    """Preflight all inputs, then execute the independent V3.5 writer."""

    kwargs = {
        "images": images,
        "audio": audio,
        "assembly_plan": assembly_plan,
        "exact_total_duration": bool(exact_total_duration),
        "audio_seam": str(audio_seam),
        "video_seam": str(video_seam),
        "diagnostics": str(diagnostics),
        "buffer_backend": str(buffer_backend),
        "backing_root": backing_root,
        "final_audio_override": final_audio_override,
        "final_audio_source": final_audio_source,
        "interrupt_check": interrupt_check,
    }
    return assemble_with_hardening(
        _assemble_decoded_chunks_v35_core,
        (),
        kwargs,
    )


__all__ = [
    "BUFFER_BACKEND_DISK",
    "BUFFER_BACKEND_AUTO",
    "BUFFER_BACKEND_OPTIONS",
    "BUFFER_BACKEND_RAM",
    "CopySpan",
    "adjust_audio_duration_direct",
    "assemble_decoded_chunks_v35",
]
