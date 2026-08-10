"""Deferred VAE decoding, overlap trimming, assembly, and exact-duration correction."""

from __future__ import annotations

from typing import Any

import torch
import torch.nn.functional as F

from ..constants import DIAGNOSTICS_FULL, DIAGNOSTICS_OFF, FPS
from ..media import validate_audio
from ..state import validate_plan
from .diagnostics import format_join_metrics, format_seam_decision, overlap_diagnostics
from .seam_guard import correct_audio_seam, correct_seam
from .seam_types import SeamDecision
from .session import entry_to_latent, validate_chunk_entry


def decode_video(video_vae: Any, latent: dict[str, Any]) -> torch.Tensor:
    samples = latent["samples"]
    if hasattr(samples, "unbind"):
        video = list(samples.unbind())[0]
    else:
        video = samples[0]
    images = video_vae.decode(video)
    if images.ndim == 5:
        images = images.reshape(-1, images.shape[-3], images.shape[-2], images.shape[-1])
    if images.ndim != 4:
        raise ValueError(f"video VAE returned unexpected shape {tuple(images.shape)}")
    # Long sequences must not leave decoded frames resident on the GPU. ComfyUI
    # IMAGE tensors are conventionally CPU float tensors, so transfer each chunk
    # immediately and release its raw decode before moving to the next chunk.
    return images.detach().to("cpu").contiguous()


def decode_audio(audio_vae: Any, latent: dict[str, Any]) -> dict[str, Any]:
    samples = latent["samples"]
    if hasattr(samples, "unbind"):
        audio_latent = list(samples.unbind())[-1]
    else:
        audio_latent = samples[-1]
    audio = audio_vae.decode(audio_latent).movedim(-1, 1)
    std = torch.std(audio, dim=[1, 2], keepdim=True) * 5.0
    std[std < 1.0] = 1.0
    audio = (audio / std).detach().to("cpu").contiguous()
    sample_rate = getattr(
        audio_vae,
        "audio_sample_rate_output",
        getattr(audio_vae, "audio_sample_rate", 32000),
    )
    return {"waveform": audio, "sample_rate": int(sample_rate)}


def _trim_images(images: torch.Tensor, plan: dict[str, Any]) -> torch.Tensor:
    plan = validate_plan(plan)
    total_frames = int(plan["total_frames"])
    trim_frames = int(plan["trim_frames"])
    if images.shape[0] < total_frames:
        raise ValueError(
            f"decoded batch has {images.shape[0]} frames; expected at least {total_frames}"
        )
    return images[:total_frames][trim_frames:].contiguous()


def _slice_audio_for_timeline(
    audio: dict[str, Any],
    *,
    trim_frames: int,
    frame_start: int,
    frame_stop: int,
) -> torch.Tensor:
    """Return one segment at its exact cumulative 24fps sample interval.

    Segment-local rounding drifts by one sample on common 119-frame Continuum
    chunks. Deriving every boundary from cumulative frame counts guarantees that
    the assembled audio length is always ``round(total_frames / 24 * rate)``.
    """

    waveform, sample_rate = validate_audio(audio)
    trim_samples = int(round(float(trim_frames) / FPS * sample_rate))
    target_start = int(round(float(frame_start) / FPS * sample_rate))
    target_stop = int(round(float(frame_stop) / FPS * sample_rate))
    wanted = target_stop - target_start
    if wanted < 0:
        raise ValueError("audio timeline interval is negative")
    result = waveform[..., trim_samples : trim_samples + wanted]
    if result.shape[-1] < wanted:
        missing = wanted - int(result.shape[-1])
        if result.shape[-1] > 0:
            tail = result[..., -1:].expand(*result.shape[:-1], missing).clone()
            result = torch.cat((result, tail), dim=-1)
        else:
            result = F.pad(result, (0, missing))
    return result.contiguous()


def decode_sequence(
    *,
    entries: list[dict[str, Any]],
    video_vae: Any,
    audio_vae: Any,
    diagnostics_full: bool,
) -> tuple[torch.Tensor, dict[str, Any], list[str]]:
    """Decode and assemble all chunks with bounded transient memory.

    The final IMAGE tensor is preallocated once. Each raw VAE decode is copied
    into its destination range and released before the next chunk, avoiding the
    repeated full-sequence copies produced by progressive ``torch.cat``.
    """

    if not entries:
        raise ValueError("cannot decode an empty Continuum sequence")
    checked = [validate_chunk_entry(entry) for entry in entries]
    plans = [validate_plan(entry["plan"]) for entry in checked]
    total_retained_frames = sum(int(plan["net_frames"]) for plan in plans)
    if total_retained_frames < 1:
        raise ValueError("Continuum sequence contains no retained frames")

    image_buffer: torch.Tensor | None = None
    audio_buffer: torch.Tensor | None = None
    audio_rate: int | None = None
    frame_cursor = 0
    previous_segment_images: torch.Tensor | None = None
    previous_segment_audio: dict[str, Any] | None = None
    reports: list[str] = []

    for index, (entry, plan) in enumerate(zip(checked, plans), start=1):
        latent = entry_to_latent(entry)
        raw_images = decode_video(video_vae, latent)
        raw_audio = decode_audio(audio_vae, latent)

        if diagnostics_full and previous_segment_images is not None:
            metrics = overlap_diagnostics(
                previous_images=previous_segment_images,
                previous_audio=previous_segment_audio,
                next_raw_images=raw_images,
                next_raw_audio=raw_audio,
                context_frames=int(plan["trim_frames"]),
            )
            reports.append(format_join_metrics(index, metrics))

        images = _trim_images(raw_images, plan)
        segment_frames = int(images.shape[0])
        if segment_frames != int(plan["net_frames"]):
            raise ValueError(
                f"chunk {index} retained {segment_frames} frames; plan expects {plan['net_frames']}"
            )
        frame_stop = frame_cursor + segment_frames

        waveform, sample_rate = validate_audio(raw_audio)
        if audio_rate is None:
            audio_rate = sample_rate
        elif sample_rate != audio_rate:
            raise ValueError(
                f"audio sample rate changed between chunks: {audio_rate} -> {sample_rate}"
            )
        segment_waveform = _slice_audio_for_timeline(
            raw_audio,
            trim_frames=int(plan["trim_frames"]),
            frame_start=frame_cursor,
            frame_stop=frame_stop,
        )

        if image_buffer is None:
            image_buffer = torch.empty(
                (total_retained_frames, *images.shape[1:]),
                dtype=images.dtype,
                device="cpu",
            )
        elif tuple(images.shape[1:]) != tuple(image_buffer.shape[1:]):
            raise ValueError(
                f"decoded image geometry changed at chunk {index}: "
                f"{tuple(images.shape[1:])} vs {tuple(image_buffer.shape[1:])}"
            )
        image_buffer[frame_cursor:frame_stop].copy_(images)

        if audio_buffer is None:
            total_samples = int(round(total_retained_frames / FPS * sample_rate))
            audio_buffer = torch.empty(
                (*waveform.shape[:-1], total_samples),
                dtype=waveform.dtype,
                device="cpu",
            )
        elif tuple(segment_waveform.shape[:-1]) != tuple(audio_buffer.shape[:-1]):
            raise ValueError("decoded audio batch/channel structure changed between chunks")
        sample_start = int(round(frame_cursor / FPS * sample_rate))
        sample_stop = int(round(frame_stop / FPS * sample_rate))
        audio_buffer[..., sample_start:sample_stop].copy_(segment_waveform)

        # Retain only what Full diagnostics needs for the next seam. Audio is
        # small, while video is bounded to the next overlap instead of a full clip.
        next_context = int(plans[index]["trim_frames"]) if index < len(plans) else 0
        if next_context > 0:
            previous_segment_images = images[-next_context:].contiguous()
            previous_segment_audio = {
                "waveform": segment_waveform,
                "sample_rate": sample_rate,
            }
        else:
            previous_segment_images = None
            previous_segment_audio = None

        reports.append(
            f"decoded chunk {index}: {segment_frames} retained frames, "
            f"cumulative {frame_stop}/{total_retained_frames}"
        )
        frame_cursor = frame_stop
        del latent, raw_images, raw_audio, images, segment_waveform

    if image_buffer is None or audio_buffer is None or audio_rate is None:
        raise RuntimeError("Continuum decoder failed to allocate output buffers")
    if frame_cursor != total_retained_frames:
        raise RuntimeError(
            f"Continuum decode cursor mismatch: {frame_cursor} != {total_retained_frames}"
        )
    audio = {"waveform": audio_buffer.contiguous(), "sample_rate": audio_rate}
    reports.append(
        f"assembled {len(entries)} chunks into {total_retained_frames} frames with "
        "cumulative sample-boundary alignment"
    )
    return image_buffer.contiguous(), audio, reports


def decode_sequence_with_seam(
    *,
    entries: list[dict[str, Any]],
    video_vae: Any,
    audio_vae: Any,
    diagnostics_mode: str,
    automatic: bool = False,
) -> tuple[torch.Tensor, dict[str, Any], list[str]]:
    """Decode with guarded V2.1 correction while preserving legacy output length."""

    if not entries:
        raise ValueError("cannot decode an empty Continuum sequence")
    checked = [validate_chunk_entry(entry) for entry in entries]
    plans = [validate_plan(entry["plan"]) for entry in checked]
    total_retained_frames = sum(int(plan["net_frames"]) for plan in plans)
    if total_retained_frames < 1:
        raise ValueError("Continuum sequence contains no retained frames")

    image_buffer: torch.Tensor | None = None
    audio_buffer: torch.Tensor | None = None
    audio_rate: int | None = None
    frame_cursor = 0
    reports: list[str] = []

    for index, (entry, plan) in enumerate(zip(checked, plans), start=1):
        latent = entry_to_latent(entry)
        raw_images = decode_video(video_vae, latent)
        raw_audio = decode_audio(audio_vae, latent)
        waveform, sample_rate = validate_audio(raw_audio)
        if audio_rate is None:
            audio_rate = sample_rate
        elif sample_rate != audio_rate:
            raise ValueError(
                f"audio sample rate changed between chunks: {audio_rate} -> {sample_rate}"
            )

        legacy_frames = int(plan["net_frames"])
        legacy_frame_stop = frame_cursor + legacy_frames
        frame_start = frame_cursor
        trim_frames = int(plan["trim_frames"])
        decision: SeamDecision | None = None
        video_patch: torch.Tensor | None = None
        audio_patch: torch.Tensor | None = None

        if index == 1:
            images = _trim_images(raw_images, plan)
        else:
            try:
                if image_buffer is None or audio_buffer is None:
                    raise RuntimeError("seam buffers are unavailable")
                limited_raw_images = raw_images[: int(plan["total_frames"])]
                images, decision, video_patch = correct_seam(
                    image_buffer[:frame_cursor],
                    limited_raw_images,
                    context_frames=trim_frames,
                    automatic=automatic,
                )
                frame_start = frame_cursor - int(decision.cut_rewind_frames)
                trim_frames -= int(decision.cut_rewind_frames)
                if frame_start < 0 or trim_frames < 0:
                    raise ValueError("adaptive cut produced a negative boundary")
                if frame_start + int(images.shape[0]) != legacy_frame_stop:
                    raise ValueError("adaptive cut changed the cumulative frame boundary")

                sample_start = int(round(frame_start / FPS * sample_rate))
                cut_sample = int(round(trim_frames / FPS * sample_rate))
                (
                    audio_patch,
                    audio_metrics,
                    crossfade_samples,
                    level_gain,
                    dc_bias,
                ) = correct_audio_seam(
                    audio_buffer[..., :sample_start],
                    waveform,
                    sample_rate=sample_rate,
                    cut_sample=cut_sample,
                )
                decision.audio_metrics = audio_metrics
                decision.audio_crossfade_samples = crossfade_samples
                decision.audio_level_gain = level_gain
                decision.audio_dc_bias = dc_bias
            except Exception as exc:
                images = _trim_images(raw_images, plan)
                frame_start = frame_cursor
                trim_frames = int(plan["trim_frames"])
                video_patch = None
                audio_patch = None
                decision = SeamDecision(
                    fallback_reason=f"{type(exc).__name__}: {exc}",
                )

        segment_frames = int(images.shape[0])
        frame_stop = frame_start + segment_frames
        if frame_stop != legacy_frame_stop:
            raise ValueError(
                f"chunk {index} corrected boundary ends at {frame_stop}; "
                f"expected {legacy_frame_stop}"
            )
        segment_waveform = _slice_audio_for_timeline(
            raw_audio,
            trim_frames=trim_frames,
            frame_start=frame_start,
            frame_stop=frame_stop,
        )

        if image_buffer is None:
            image_buffer = torch.empty(
                (total_retained_frames, *images.shape[1:]),
                dtype=images.dtype,
                device="cpu",
            )
        elif tuple(images.shape[1:]) != tuple(image_buffer.shape[1:]):
            raise ValueError(
                f"decoded image geometry changed at chunk {index}: "
                f"{tuple(images.shape[1:])} vs {tuple(image_buffer.shape[1:])}"
            )
        if video_patch is not None and video_patch.shape[0] > 0:
            patch_start = frame_start - int(video_patch.shape[0])
            if patch_start < 0:
                raise ValueError("video seam patch starts before the output")
            image_buffer[patch_start:frame_start].copy_(video_patch)
        image_buffer[frame_start:frame_stop].copy_(images)

        if audio_buffer is None:
            total_samples = int(round(total_retained_frames / FPS * sample_rate))
            audio_buffer = torch.empty(
                (*waveform.shape[:-1], total_samples),
                dtype=waveform.dtype,
                device="cpu",
            )
        elif tuple(segment_waveform.shape[:-1]) != tuple(audio_buffer.shape[:-1]):
            raise ValueError("decoded audio batch/channel structure changed between chunks")
        sample_start = int(round(frame_start / FPS * sample_rate))
        sample_stop = int(round(frame_stop / FPS * sample_rate))
        if audio_patch is not None and audio_patch.shape[-1] > 0:
            patch_start = sample_start - int(audio_patch.shape[-1])
            if patch_start < 0:
                raise ValueError("audio seam patch starts before the output")
            audio_buffer[..., patch_start:sample_start].copy_(audio_patch)
        audio_buffer[..., sample_start:sample_stop].copy_(segment_waveform)

        if decision is not None and diagnostics_mode != DIAGNOSTICS_OFF:
            reports.append(
                format_seam_decision(
                    index,
                    decision,
                    full=diagnostics_mode == DIAGNOSTICS_FULL,
                )
            )
        reports.append(
            f"decoded chunk {index}: {segment_frames} retained/corrected frames, "
            f"cumulative {frame_stop}/{total_retained_frames}"
        )
        frame_cursor = frame_stop
        del latent, raw_images, raw_audio, images, segment_waveform

    if image_buffer is None or audio_buffer is None or audio_rate is None:
        raise RuntimeError("Continuum seam decoder failed to allocate output buffers")
    if frame_cursor != total_retained_frames:
        raise RuntimeError(
            f"Continuum seam decode cursor mismatch: {frame_cursor} != {total_retained_frames}"
        )
    audio = {"waveform": audio_buffer.contiguous(), "sample_rate": audio_rate}
    reports.append(
        f"assembled {len(entries)} chunks into {total_retained_frames} frames with "
        f"V2.1 {'Auto' if automatic else 'Basic'} seam correction and "
        "cumulative sample-boundary alignment"
    )
    return image_buffer.contiguous(), audio, reports


def enforce_total_frames(
    images: torch.Tensor,
    audio: dict[str, Any],
    *,
    target_frames: int,
    preserve_final_frame: bool = False,
) -> tuple[torch.Tensor, dict[str, Any], str]:
    target_frames = int(target_frames)
    if target_frames < 1:
        raise ValueError("target_frames must be positive")
    current = int(images.shape[0])
    adjustment = target_frames - current
    anchor_preserved = bool(preserve_final_frame and adjustment < 0 and target_frames >= 2)
    if adjustment < 0:
        if anchor_preserved:
            # H3's valid temporal grid rarely lands on an exact whole-second total.
            # When a user supplied a final FL2VA frame, trimming only from the end
            # would discard the very anchor they requested. Remove the small excess
            # immediately before the final decoded frame instead.
            images = torch.cat((images[: target_frames - 1], images[-1:]), dim=0).contiguous()
        else:
            images = images[:target_frames].contiguous()
    elif adjustment > 0:
        if current == 0:
            raise ValueError("cannot pad an empty image sequence")
        pad = images[-1:].expand(adjustment, *images.shape[1:]).clone()
        images = torch.cat((images, pad), dim=0).contiguous()

    waveform = audio["waveform"]
    sample_rate = int(audio["sample_rate"])
    original_samples = int(waveform.shape[-1])
    target_samples = int(round(target_frames / FPS * sample_rate))
    delta_samples = target_samples - original_samples
    if delta_samples < 0:
        if anchor_preserved and target_samples > 1:
            # Preserve the final video-frame interval of audio as well. A short
            # 5 ms interpolation at the deletion boundary suppresses a hard click
            # without changing the exact output length.
            tail_samples = min(
                max(1, int(round(sample_rate / FPS))),
                target_samples,
                original_samples,
            )
            head_samples = target_samples - tail_samples
            head = waveform[..., :head_samples]
            tail = waveform[..., -tail_samples:].clone()
            fade = min(int(round(sample_rate * 0.005)), head_samples, tail_samples)
            if fade > 0:
                start = head[..., -1:].to(dtype=tail.dtype)
                alpha = torch.linspace(
                    0.0, 1.0, fade, dtype=tail.dtype, device=tail.device
                ).reshape(*([1] * (tail.ndim - 1)), fade)
                tail[..., :fade] = start * (1.0 - alpha) + tail[..., :fade] * alpha
            waveform = torch.cat((head, tail), dim=-1).contiguous()
        else:
            waveform = waveform[..., :target_samples].contiguous()
    elif delta_samples > 0:
        # Repeat the final sample instead of introducing a zero click.
        if waveform.shape[-1] == 0:
            waveform = F.pad(waveform, (0, delta_samples))
        else:
            tail = waveform[..., -1:].expand(*waveform.shape[:-1], delta_samples).clone()
            waveform = torch.cat((waveform, tail), dim=-1).contiguous()
    audio = {**audio, "waveform": waveform, "sample_rate": sample_rate}
    mode = "final anchor preserved; pre-tail trim" if anchor_preserved else "tail trim/pad"
    report = (
        f"Exact-duration adjustment: frames {current}->{target_frames} ({adjustment:+d}), "
        f"audio samples correction {delta_samples:+d}; {mode}."
    )
    return images, audio, report
