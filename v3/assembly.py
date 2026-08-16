"""Decoded chunk assembly for latent-first H3 Continuum V3."""

from __future__ import annotations

from typing import Any

import torch

from ..media import validate_audio
from ..v2.decoder import _slice_audio_for_timeline, enforce_total_frames
from ..constants import (
    DIAGNOSTICS_FULL,
    DIAGNOSTICS_OFF,
    DIAGNOSTICS_OPTIONS,
    normalize_diagnostics_mode,
)
from ..v2.seam_guard import correct_audio_seam
from .plan import FPS, validate_assembly_plan

AUDIO_SEAM_OFF = "Off"
AUDIO_SEAM_AUTO = "Auto"
AUDIO_SEAM_OPTIONS = (AUDIO_SEAM_OFF, AUDIO_SEAM_AUTO)
VIDEO_SEAM_OFF = "Off"
VIDEO_SEAM_ANALYZE = "Analyze Only"
VIDEO_SEAM_AUTO = "Auto"
VIDEO_SEAM_AUTO_2 = "Auto 2"
VIDEO_SEAM_ANALYSIS_OPTIONS = (
    VIDEO_SEAM_AUTO,
    VIDEO_SEAM_AUTO_2,
    VIDEO_SEAM_ANALYZE,
    VIDEO_SEAM_OFF,
)


def _singleton(value: Any, name: str) -> Any:
    while isinstance(value, list):
        if len(value) != 1:
            raise ValueError(f"{name} must contain exactly one value")
        value = value[0]
    return value


def _chunk_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        if len(value) == 1 and isinstance(value[0], list):
            return list(value[0])
        return list(value)
    return [value]


def assemble_decoded_chunks(
    *,
    images: list[Any],
    audio: list[Any],
    assembly_plan: dict[str, Any],
    exact_total_duration: bool,
    audio_seam: str,
    diagnostics: str,
):
    plan = validate_assembly_plan(assembly_plan)
    diagnostics_mode = normalize_diagnostics_mode(diagnostics)
    if audio_seam not in AUDIO_SEAM_OPTIONS:
        raise ValueError(f"unknown Audio Seam mode: {audio_seam!r}")

    chunk_plans = list(plan["chunks"])
    if len(images) != len(chunk_plans) or len(audio) != len(chunk_plans):
        raise ValueError(
            "decoded chunk count does not match the V3 assembly plan: "
            f"images={len(images)}, audio={len(audio)}, plan={len(chunk_plans)}"
        )

    total_retained_frames = sum(int(item["net_frames"]) for item in chunk_plans)
    image_buffer = None
    audio_buffer = None
    audio_rate = None
    frame_cursor = 0
    reports = [
        "H3 Continuum Assemble V3",
        f"Audio Seam: {audio_seam}. Video seam correction is disabled.",
    ]

    for index, (raw_images, raw_audio, chunk) in enumerate(
        zip(images, audio, chunk_plans), start=1
    ):
        if not torch.is_tensor(raw_images) or raw_images.ndim != 4:
            raise ValueError(f"decoded image chunk {index} must be [frames,H,W,C]")
        raw_images = raw_images.detach().to("cpu")
        total_frames = int(chunk["total_frames"])
        trim_frames = int(chunk["trim_frames"])
        net_frames = int(chunk["net_frames"])
        if int(raw_images.shape[0]) < total_frames:
            raise ValueError(
                f"decoded image chunk {index} has {raw_images.shape[0]} frames; "
                f"expected at least {total_frames}"
            )
        segment_images = raw_images[:total_frames][trim_frames:].contiguous()
        if int(segment_images.shape[0]) != net_frames:
            raise ValueError(
                f"decoded image chunk {index} retained {segment_images.shape[0]} frames; "
                f"plan expects {net_frames}"
            )

        waveform, sample_rate = validate_audio(raw_audio)
        waveform = waveform.detach().to("cpu")
        sample_rate = int(sample_rate)
        raw_audio_cpu = {"waveform": waveform, "sample_rate": sample_rate}
        if audio_rate is None:
            audio_rate = sample_rate
        elif sample_rate != audio_rate:
            raise ValueError(
                f"audio sample rate changed between chunks: {audio_rate} -> {sample_rate}"
            )

        frame_stop = frame_cursor + net_frames
        segment_waveform = _slice_audio_for_timeline(
            raw_audio_cpu,
            trim_frames=trim_frames,
            frame_start=frame_cursor,
            frame_stop=frame_stop,
        )

        if image_buffer is None:
            image_buffer = torch.empty(
                (total_retained_frames, *segment_images.shape[1:]),
                dtype=segment_images.dtype,
                device="cpu",
            )
        elif tuple(segment_images.shape[1:]) != tuple(image_buffer.shape[1:]):
            raise ValueError(f"decoded image geometry changed at chunk {index}")
        image_buffer[frame_cursor:frame_stop].copy_(segment_images)

        if audio_buffer is None:
            audio_buffer = torch.empty(
                (
                    *waveform.shape[:-1],
                    int(round(total_retained_frames / FPS * sample_rate)),
                ),
                dtype=waveform.dtype,
                device="cpu",
            )
        elif tuple(segment_waveform.shape[:-1]) != tuple(audio_buffer.shape[:-1]):
            raise ValueError(
                "decoded audio batch/channel structure changed between chunks"
            )

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
                    f"corr={metrics.correlation_before:.4f}->{metrics.correlation_after:.4f}, "
                    f"jump={metrics.boundary_jump_before:.6f}->{metrics.boundary_jump_after:.6f}, "
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

        audio_buffer[..., sample_start:sample_stop].copy_(segment_waveform)
        if diagnostics_mode != DIAGNOSTICS_OFF:
            reports.append(
                f"assembled decoded chunk {index}: {net_frames} retained frames, "
                f"cumulative {frame_stop}/{total_retained_frames}"
            )
            if seam_report:
                reports.append(seam_report)
        frame_cursor = frame_stop

    if image_buffer is None or audio_buffer is None or audio_rate is None:
        raise RuntimeError("V3 assembler failed to allocate output buffers")
    if frame_cursor != total_retained_frames:
        raise RuntimeError(
            f"V3 assembly cursor mismatch: {frame_cursor} != {total_retained_frames}"
        )

    result_audio = {
        "waveform": audio_buffer.contiguous(),
        "sample_rate": audio_rate,
    }
    duration_report = ""
    if exact_total_duration:
        image_buffer, result_audio, duration_report = enforce_total_frames(
            image_buffer.contiguous(),
            result_audio,
            target_frames=int(plan["target_frames"]),
            preserve_final_frame=bool(plan.get("preserve_final_frame")),
        )

    reports.append(
        f"Assembled {len(chunk_plans)} externally decoded chunks into "
        f"{image_buffer.shape[0]} frames with cumulative sample-boundary alignment."
    )
    if duration_report:
        reports.append(duration_report)
    return image_buffer.contiguous(), result_audio, "\n".join(reports)


class H3ContinuumAssembleV3:
    DESCRIPTION = (
        "Assemble full AV chunks decoded by ComfyUI Core. Trims decoded context, "
        "aligns audio on cumulative frame boundaries, and optionally applies Audio Seam Auto."
    )
    SEARCH_ALIASES = ["H3 latent assemble", "H3 external VAE decode"]

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "audio": ("AUDIO",),
                "assembly_plan": ("H3_CONTINUUM_ASSEMBLY_PLAN",),
                "exact_total_duration": ("BOOLEAN", {"default": True}),
                "audio_seam": (
                    AUDIO_SEAM_OPTIONS,
                    {
                        "default": AUDIO_SEAM_AUTO,
                        "display_name": "Audio Seam",
                        "tooltip": (
                            "Auto corrects only decoded audio boundaries; "
                            "video frames are never altered."
                        ),
                    },
                ),
                "diagnostics": (
                    DIAGNOSTICS_OPTIONS,
                    {
                        "default": DIAGNOSTICS_OPTIONS[0],
                        "display_name": "Report Detail",
                    },
                ),
            }
        }

    INPUT_IS_LIST = True
    RETURN_TYPES = ("IMAGE", "AUDIO", "STRING")
    RETURN_NAMES = ("images", "audio", "report")
    FUNCTION = "assemble"
    CATEGORY = "MiniMax H3/Continuum"

    def assemble(
        self,
        images,
        audio,
        assembly_plan,
        exact_total_duration,
        audio_seam,
        diagnostics,
    ):
        return assemble_decoded_chunks(
            images=_chunk_list(images),
            audio=_chunk_list(audio),
            assembly_plan=_singleton(assembly_plan, "assembly_plan"),
            exact_total_duration=bool(
                _singleton(exact_total_duration, "exact_total_duration")
            ),
            audio_seam=str(_singleton(audio_seam, "audio_seam")),
            diagnostics=str(_singleton(diagnostics, "diagnostics")),
        )
# V3.0.1 hardening integration: preflight before allocation; Detailed Report only.
from ..hardening import assemble_with_hardening as _assemble_with_hardening

_assemble_decoded_chunks_v300 = assemble_decoded_chunks


def assemble_decoded_chunks(*args, **kwargs):
    return _assemble_with_hardening(_assemble_decoded_chunks_v300, args, kwargs)


class H3ContinuumAssembleSeamExperimental(H3ContinuumAssembleV3):
    DEPRECATED = False
    CATEGORY = "MiniMax H3/Continuum"
    DESCRIPTION = (
        "Analyze decoded chunk boundaries and apply guarded video seam correction."
    )
    SEARCH_ALIASES = ["H3 seam analysis", "H3 boundary flicker analysis"]

    @classmethod
    def INPUT_TYPES(cls):
        schema = super().INPUT_TYPES()
        required = dict(schema["required"])
        diagnostics = required.pop("diagnostics")
        required["video_seam"] = (
            VIDEO_SEAM_ANALYSIS_OPTIONS,
            {
                "default": VIDEO_SEAM_AUTO,
                "display_name": "Video Seam",
                "tooltip": (
                    "Analyze Only reports decoded video boundaries without changing them. "
                    "Auto applies the validated transient and micro-flash correction. "
                    "Auto 2 experimentally adds qualified exposure-ramp smoothing."
                ),
            },
        )
        required["diagnostics"] = diagnostics
        schema["required"] = required
        return schema

    def assemble(
        self,
        images,
        audio,
        assembly_plan,
        exact_total_duration,
        audio_seam,
        video_seam,
        diagnostics,
    ):
        mode = str(_singleton(video_seam, "video_seam"))
        if mode not in VIDEO_SEAM_ANALYSIS_OPTIONS:
            raise ValueError(f"unknown Video Seam mode: {mode!r}")
        if mode == VIDEO_SEAM_OFF:
            return super().assemble(
                images,
                audio,
                assembly_plan,
                exact_total_duration,
                audio_seam,
                diagnostics,
            )

        image_chunks = _chunk_list(images)
        plan = _singleton(assembly_plan, "assembly_plan")
        analyses = []
        analysis_error = None
        actions = {}
        try:
            from .video_seam import (
                analyze_decoded_boundaries,
                correct_decoded_boundaries,
                format_video_boundary_analysis,
            )

            analyses = analyze_decoded_boundaries(
                images=image_chunks,
                assembly_plan=plan,
            )
            if mode in (VIDEO_SEAM_AUTO, VIDEO_SEAM_AUTO_2):
                image_chunks, actions = correct_decoded_boundaries(
                    images=image_chunks,
                    assembly_plan=plan,
                    analyses=analyses,
                    enable_exposure_ramp=mode == VIDEO_SEAM_AUTO_2,
                )
        except Exception as exc:
            analysis_error = exc

        result_images, result_audio, report = assemble_decoded_chunks(
            images=image_chunks,
            audio=_chunk_list(audio),
            assembly_plan=plan,
            exact_total_duration=bool(
                _singleton(exact_total_duration, "exact_total_duration")
            ),
            audio_seam=str(_singleton(audio_seam, "audio_seam")),
            diagnostics=str(_singleton(diagnostics, "diagnostics")),
        )
        if mode == VIDEO_SEAM_ANALYZE:
            status = "Video Seam: Analyze Only; decoded frames and audio are unchanged."
        elif mode == VIDEO_SEAM_AUTO:
            status = (
                "Video Seam: Auto; guarded transient and micro-flash correction enabled."
            )
        else:
            status = (
                "Video Seam: Auto 2 (Experimental); guarded transient, micro-flash, "
                "and exposure-ramp correction enabled."
            )
        report = report.replace("Video seam correction is disabled.", status, 1)
        if analysis_error is None:
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
                lines = [f"Video Seam {mode}: no decoded chunk boundary to analyze."]
        else:
            lines = [
                f"Video Seam {mode}: native output preserved; analysis unavailable "
                f"({type(analysis_error).__name__}: {analysis_error})"
            ]
        return result_images, result_audio, report.rstrip() + "\n" + "\n".join(lines)
