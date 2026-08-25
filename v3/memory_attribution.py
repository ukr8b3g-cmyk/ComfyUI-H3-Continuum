"""V3.5-only, non-synchronizing memory attribution helpers."""

from __future__ import annotations

from dataclasses import dataclass
import math
import time
from typing import Any, Mapping

import torch

from ..constants import FPS
from ..hardening import tensor_storage_stats
from ..state import extract_av_streams
from .plan import validate_assembly_plan


_MIB = 1024**2

_CONDITIONING_SUBPHASES = (
    "conditioning_identity_video_vae",
    "conditioning_reference_image_vae",
    "conditioning_reference_audio_vae",
    "conditioning_driving_audio_vae",
    "conditioning_reference_video_vae",
    "conditioning_timeline_video_vae",
    "conditioning_prompt_clip",
)


def _mib(value: int | None) -> str:
    if value is None:
        return "n/a"
    return f"{int(value) / _MIB:.1f} MiB"


def _bytes_and_mib(value: int) -> str:
    return f"{int(value)} bytes ({int(value) / _MIB:.1f} MiB)"


def _process_counters() -> tuple[int | None, int | None]:
    try:
        import psutil

        return (
            int(psutil.Process().memory_info().rss),
            int(psutil.virtual_memory().available),
        )
    except Exception:
        return None, None


def _cuda_counters() -> tuple[int | None, int | None, int | None]:
    """Read counters only; never synchronize, clear caches, or reset peaks."""

    try:
        if torch.cuda.is_available():
            return (
                int(torch.cuda.memory_allocated()),
                int(torch.cuda.memory_reserved()),
                int(torch.cuda.max_memory_allocated()),
            )
    except Exception:
        pass
    return None, None, None


def _retained_stream_bytes(
    entries: Any,
    stream: str,
) -> int:
    values: list[Any] = []
    if isinstance(entries, (list, tuple)):
        for entry in entries:
            if isinstance(entry, Mapping):
                values.append(entry.get(stream))
    stats = tensor_storage_stats(values)
    return int(stats["cpu_bytes"]) + int(stats["gpu_bytes"])


def _observed_streams(latent: Any) -> tuple[Any, ...]:
    if latent is None:
        return ()
    if isinstance(latent, Mapping) and "samples" in latent:
        try:
            return tuple(extract_av_streams(latent))
        except Exception:
            return ()
    return (latent,)


def format_attribution_snapshot(
    label: str,
    *,
    retained_entries: Any = None,
    observed_latent: Any = None,
    retained_refine_context: Any = None,
) -> str:
    """Format one fail-soft snapshot without changing allocator state."""
    try:
        rss, available = _process_counters()
        cuda_allocated, cuda_reserved, cuda_peak = _cuda_counters()
        retained_video = _retained_stream_bytes(retained_entries, "video")
        retained_audio = _retained_stream_bytes(retained_entries, "audio")
        observed = tensor_storage_stats(_observed_streams(observed_latent))
        refine_context = tensor_storage_stats(retained_refine_context)
        return (
            f"Memory [{label}]: RSS={_mib(rss)}, "
            f"system_available={_mib(available)}, "
            f"CUDA_allocated={_mib(cuda_allocated)}, "
            f"CUDA_reserved={_mib(cuda_reserved)}, "
            f"CUDA_peak_allocated_since_external_reset={_mib(cuda_peak)}, "
            f"retained_video={_bytes_and_mib(retained_video)}, "
            f"retained_audio={_bytes_and_mib(retained_audio)}, "
            "retained_refine_context_CPU="
            f"{_bytes_and_mib(int(refine_context['cpu_bytes']))}, "
            "retained_refine_context_GPU="
            f"{_bytes_and_mib(int(refine_context['gpu_bytes']))}, "
            f"observed_CPU_storage={_bytes_and_mib(int(observed['cpu_bytes']))}, "
            f"observed_GPU_storage={_bytes_and_mib(int(observed['gpu_bytes']))}"
        )
    except Exception as exc:
        return (
            f"Memory [{label}]: unavailable "
            f"({type(exc).__name__}: {exc})"
        )


class MemoryAttributionCollector:
    """Keep V3.5 memory events in chronological order until report assembly."""

    def __init__(self):
        self.lines: list[str] = []
        self._sequence_started_at: float | None = None
        self._phase_started_at: dict[tuple[str, int | None, tuple[int, ...]], float] = {}
        self._phase_totals: dict[str, float] = {}
        self._phase_counts: dict[str, int] = {}
        self._group_totals: dict[
            tuple[int, tuple[int, ...]], dict[str, float]
        ] = {}

    def capture_sequence_start(self) -> None:
        self._sequence_started_at = time.perf_counter()
        self.lines.append(format_attribution_snapshot("V3.5 sequence start"))
        self.start_phase(phase="preparation")

    def start_phase(
        self,
        *,
        phase: str,
        physical_group: int | None = None,
        logical_chunks: tuple[int, ...] = (),
    ) -> None:
        key = (
            str(phase),
            None if physical_group is None else int(physical_group),
            tuple(int(value) for value in logical_chunks),
        )
        self._phase_started_at[key] = time.perf_counter()

    def finish_phase(
        self,
        *,
        phase: str,
        physical_group: int | None = None,
        logical_chunks: tuple[int, ...] = (),
    ) -> None:
        phase = str(phase)
        group = None if physical_group is None else int(physical_group)
        logical = tuple(int(value) for value in logical_chunks)
        key = (phase, group, logical)
        started = self._phase_started_at.pop(key, None)
        if started is None:
            return
        elapsed = time.perf_counter() - started
        if not math.isfinite(elapsed) or elapsed < 0.0:
            return
        self._phase_totals[phase] = self._phase_totals.get(phase, 0.0) + elapsed
        self._phase_counts[phase] = self._phase_counts.get(phase, 0) + 1
        if group is not None:
            phases = self._group_totals.setdefault((group, logical), {})
            phases[phase] = phases.get(phase, 0.0) + elapsed

    @staticmethod
    def _format_seconds(value: float | None) -> str:
        return "n/a" if value is None else f"{float(value):.6f}s"

    def _performance_lines(self) -> list[str]:
        now = time.perf_counter()
        host_wall = None
        if self._sequence_started_at is not None:
            candidate = now - self._sequence_started_at
            if math.isfinite(candidate) and candidate >= 0.0:
                host_wall = candidate
        ordered = (
            "preparation",
            "conditioning",
            *_CONDITIONING_SUBPHASES,
            "group_prepare",
            "sampling",
            "cpu_commit_validation",
            "refine_context",
            "finalization",
        )
        lines = []
        for (group, logical), phases in sorted(self._group_totals.items()):
            logical_label = ",".join(str(value) for value in logical)
            fields = ", ".join(
                f"{name}={self._format_seconds(phases.get(name))}"
                for name in (
                    "group_prepare",
                    "sampling",
                    "cpu_commit_validation",
                    "refine_context",
                )
            )
            lines.append(
                f"Performance [V3.5 physical group {group} "
                f"logical=[{logical_label}]]: {fields}"
            )
        totals = ", ".join(
            f"{name}={self._format_seconds(self._phase_totals.get(name))}"
            for name in ordered
        )
        counts = ", ".join(
            f"{name}={int(self._phase_counts.get(name, 0))}"
            for name in (
                "group_prepare",
                "sampling",
                "cpu_commit_validation",
                "refine_context",
            )
        )
        conditioning_counts = ", ".join(
            f"{name}={int(self._phase_counts.get(name, 0))}"
            for name in _CONDITIONING_SUBPHASES
        )
        lines.append(
            "Performance [V3.5 summary]: "
            f"host_wall_including_diagnostics={self._format_seconds(host_wall)}, "
            f"{totals}; "
            f"phase_counts({counts}); "
            f"conditioning_counts({conditioning_counts}); "
            "CUDA_synchronize=not_used"
        )
        return lines

    def capture_group(
        self,
        *,
        physical_group: int,
        logical_chunks: tuple[int, ...],
        stage: str,
        retained_entries: Any,
        observed_latent: Any = None,
        retained_refine_context: Any = None,
    ) -> None:
        logical = ",".join(str(int(value)) for value in logical_chunks)
        self.lines.append(
            format_attribution_snapshot(
                f"V3.5 physical group {int(physical_group)} "
                f"logical=[{logical}] {stage}",
                retained_entries=retained_entries,
                observed_latent=observed_latent,
                retained_refine_context=retained_refine_context,
            )
        )

    def capture_sequence_complete(
        self,
        entries: Any,
        retained_refine_context: Any = None,
    ) -> None:
        self.lines.extend(self._performance_lines())
        self.lines.append(
            format_attribution_snapshot(
                "V3.5 sequence complete",
                retained_entries=entries,
                retained_refine_context=retained_refine_context,
            )
        )


def capture_attribution_fail_soft(
    collector: Any,
    method: str,
    **kwargs: Any,
) -> None:
    """A diagnostics failure must never replace a sampling result."""

    try:
        getattr(collector, method)(**kwargs)
    except Exception as exc:
        try:
            collector.lines.append(
                f"Memory attribution [{method}]: unavailable "
                f"({type(exc).__name__}: {exc})"
            )
        except Exception:
            pass


@dataclass(frozen=True)
class AssemblyBufferProjection:
    natural_frames: int
    target_frames: int
    natural_image_bytes: int
    natural_audio_bytes: int
    final_image_bytes: int
    final_audio_bytes: int
    frame_count_adjustment_required: bool


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        if len(value) == 1 and isinstance(value[0], list):
            return list(value[0])
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _singleton(value: Any, name: str) -> Any:
    while isinstance(value, list):
        if len(value) != 1:
            raise ValueError(f"{name} must contain exactly one value")
        value = value[0]
    return value


def project_assembly_buffers(
    *,
    images: Any,
    audio: Any,
    assembly_plan: Any,
    exact_total_duration: Any,
) -> AssemblyBufferProjection:
    """Calculate natural and final buffer sizes without allocating a buffer."""

    plan = validate_assembly_plan(_singleton(assembly_plan, "assembly_plan"))
    image_chunks = _as_list(images)
    audio_chunks = _as_list(audio)
    if not image_chunks or not audio_chunks:
        raise ValueError("decoded image/audio chunks are required for projection")

    first_image = _singleton(image_chunks[0], "decoded image chunk")
    if not torch.is_tensor(first_image) or first_image.ndim != 4:
        raise ValueError("decoded image chunk must be [frames,H,W,C]")
    frame_shape = tuple(int(value) for value in first_image.shape[1:])
    for index, value in enumerate(image_chunks, start=1):
        tensor = _singleton(value, f"decoded image chunk {index}")
        if (
            not torch.is_tensor(tensor)
            or tensor.ndim != 4
            or tuple(int(item) for item in tensor.shape[1:]) != frame_shape
            or tensor.dtype != first_image.dtype
        ):
            raise ValueError("decoded image geometry or dtype changed between chunks")

    first_audio = _singleton(audio_chunks[0], "decoded audio chunk")
    if not isinstance(first_audio, Mapping):
        raise ValueError("decoded audio chunk must be an AUDIO mapping")
    waveform = first_audio.get("waveform")
    sample_rate = first_audio.get("sample_rate")
    if not torch.is_tensor(waveform) or waveform.ndim < 1 or sample_rate is None:
        raise ValueError("decoded audio chunk has an invalid waveform or sample rate")
    sample_rate = int(sample_rate)
    if sample_rate <= 0:
        raise ValueError("decoded audio sample rate must be positive")

    decode_units = list(plan.get("decode_groups") or plan["chunks"])
    natural_frames = sum(int(unit["net_frames"]) for unit in decode_units)
    exact = bool(_singleton(exact_total_duration, "exact_total_duration"))
    target_frames = int(plan["target_frames"]) if exact else natural_frames
    if natural_frames <= 0 or target_frames <= 0:
        raise ValueError("assembly frame counts must be positive")

    frame_elements = math.prod(frame_shape)
    audio_streams = math.prod(int(value) for value in waveform.shape[:-1])
    natural_samples = int(round(natural_frames / FPS * sample_rate))
    target_samples = int(round(target_frames / FPS * sample_rate))
    return AssemblyBufferProjection(
        natural_frames=natural_frames,
        target_frames=target_frames,
        natural_image_bytes=(
            natural_frames * frame_elements * first_image.element_size()
        ),
        natural_audio_bytes=(
            natural_samples * audio_streams * waveform.element_size()
        ),
        final_image_bytes=(
            target_frames * frame_elements * first_image.element_size()
        ),
        final_audio_bytes=(
            target_samples * audio_streams * waveform.element_size()
        ),
        frame_count_adjustment_required=bool(
            exact and target_frames != natural_frames
        ),
    )


def format_assembly_projection(projection: AssemblyBufferProjection) -> str:
    return (
        "Projected assembly buffers [V3.5]: "
        f"natural_frames={projection.natural_frames}, "
        f"projected_natural_IMAGE={_bytes_and_mib(projection.natural_image_bytes)}, "
        "projected_natural_generated_AUDIO="
        f"{_bytes_and_mib(projection.natural_audio_bytes)}, "
        f"target_frames={projection.target_frames}, "
        f"final_IMAGE={_bytes_and_mib(projection.final_image_bytes)}, "
        f"final_generated_AUDIO={_bytes_and_mib(projection.final_audio_bytes)}, "
        "frame_count_adjustment_required="
        f"{'yes' if projection.frame_count_adjustment_required else 'no'}"
    )
