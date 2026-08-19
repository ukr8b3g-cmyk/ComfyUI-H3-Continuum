"""Read-only diagnostics for the latent video context passed between chunks."""
from __future__ import annotations

from dataclasses import dataclass
import math

import torch
import torch.nn.functional as F


@dataclass(frozen=True)
class VideoContextStats:
    shape: tuple[int, ...]
    mean: float
    std: float
    low_frequency_rms: float
    high_frequency_rms: float
    temporal_delta_rms: float
    outlier_ratio: float


def _rms(value: torch.Tensor) -> float:
    return float(torch.sqrt(torch.mean(value.square())).item()) if value.numel() else 0.0


def measure_video_context(video: torch.Tensor) -> VideoContextStats:
    """Measure a context tensor without modifying or retaining it."""
    if not torch.is_tensor(video) or video.ndim != 5:
        raise ValueError("video context must be a 5D tensor")
    value = video.detach().to(device="cpu", dtype=torch.float32)
    if not bool(torch.isfinite(value).all().item()):
        raise ValueError("video context contains NaN or Inf")

    mean = float(value.mean().item())
    std = float(value.std(unbiased=False).item())
    low = F.avg_pool3d(
        value,
        kernel_size=(1, 3, 3),
        stride=1,
        padding=(0, 1, 1),
        count_include_pad=False,
    )
    high = value - low
    temporal = value[:, :, 1:] - value[:, :, :-1] if value.shape[2] > 1 else value[:, :, :0]
    if std > 0.0:
        outlier_ratio = float(((value - mean).abs() > 6.0 * std).float().mean().item())
    else:
        outlier_ratio = 0.0
    return VideoContextStats(
        shape=tuple(int(part) for part in video.shape),
        mean=mean,
        std=std,
        low_frequency_rms=_rms(low),
        high_frequency_rms=_rms(high),
        temporal_delta_rms=_rms(temporal),
        outlier_ratio=outlier_ratio,
    )


def _ratio(value: float, reference: float) -> float:
    if reference == 0.0:
        return 1.0 if value == 0.0 else math.inf
    return value / reference


def _format_ratio(value: float) -> str:
    return f"{value:.4f}" if math.isfinite(value) else "inf"


class ContextDiagnosticsTracker:
    """Track first-context and previous-context ratios for one sequence run."""

    def __init__(self) -> None:
        self._baseline: VideoContextStats | None = None
        self._previous: VideoContextStats | None = None

    def observe(
        self,
        video: torch.Tensor,
        *,
        source_chunk: int,
        context_frames: int,
        reused: bool,
    ) -> str:
        try:
            stats = measure_video_context(video)
        except Exception as exc:
            return f"context diagnostics source chunk {source_chunk}: unavailable ({exc})"

        if self._baseline is None:
            self._baseline = stats
        previous = self._previous or stats
        baseline = self._baseline
        self._previous = stats
        return (
            f"context diagnostics source chunk {source_chunk}: frames={int(context_frames)}, "
            f"shape={stats.shape}, reused={'yes' if reused else 'no'}, "
            f"mean={stats.mean:.6f}, std={stats.std:.6f}, "
            f"hf={stats.high_frequency_rms:.6f}, motion={stats.temporal_delta_rms:.6f}, "
            f"outliers={stats.outlier_ratio:.6f}, "
            f"std_prev={_format_ratio(_ratio(stats.std, previous.std))}, "
            f"std_base={_format_ratio(_ratio(stats.std, baseline.std))}, "
            f"hf_prev={_format_ratio(_ratio(stats.high_frequency_rms, previous.high_frequency_rms))}, "
            f"hf_base={_format_ratio(_ratio(stats.high_frequency_rms, baseline.high_frequency_rms))}, "
            f"motion_prev={_format_ratio(_ratio(stats.temporal_delta_rms, previous.temporal_delta_rms))}, "
            f"motion_base={_format_ratio(_ratio(stats.temporal_delta_rms, baseline.temporal_delta_rms))}, "
            "action=observe"
        )
