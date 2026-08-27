"""Measure the R2 39f/65T decoded-audio transition around the chunk boundary."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import subprocess
from typing import Any

import numpy as np


def _decode_audio(path: Path, ffmpeg: Path, sample_rate: int) -> np.ndarray:
    completed = subprocess.run(
        [
            str(ffmpeg),
            "-v",
            "error",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-f",
            "f32le",
            "-acodec",
            "pcm_f32le",
            "-ac",
            "2",
            "-ar",
            str(sample_rate),
            "pipe:1",
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    values = np.frombuffer(completed.stdout, dtype="<f4")
    if values.size % 2:
        raise RuntimeError(f"decoded stereo PCM has odd sample count: {values.size}")
    return values.reshape(-1, 2).astype(np.float64, copy=False)


def _rms(value: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(value)))) if value.size else 0.0


def _spectral_distance(before: np.ndarray, after: np.ndarray) -> float:
    count = min(len(before), len(after))
    if count < 8:
        return math.nan
    window = np.hanning(count)[:, None]
    left = np.abs(np.fft.rfft(before[-count:] * window, axis=0)).reshape(-1)
    right = np.abs(np.fft.rfft(after[:count] * window, axis=0)).reshape(-1)
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    if denominator <= 1e-20:
        return 0.0
    return float(1.0 - np.dot(left, right) / denominator)


def _zero_crossing_rate(value: np.ndarray) -> float:
    if len(value) < 2:
        return 0.0
    signs = np.signbit(value)
    return float(np.mean(signs[1:] != signs[:-1]))


def boundary_metrics(
    audio: np.ndarray,
    *,
    sample_rate: int,
    boundary_sample: int,
) -> dict[str, Any]:
    if not 1 <= boundary_sample < len(audio):
        raise ValueError(
            f"boundary sample {boundary_sample} is outside decoded audio length {len(audio)}"
        )
    short = max(1, int(round(sample_rate * 0.05)))
    long = max(short, int(round(sample_rate * 0.25)))
    before_short = audio[boundary_sample - short : boundary_sample]
    after_short = audio[boundary_sample : boundary_sample + short]
    before_long = audio[boundary_sample - long : boundary_sample]
    after_long = audio[boundary_sample : boundary_sample + long]
    neighborhood = audio[boundary_sample - long : boundary_sample + long]
    differences = np.abs(np.diff(neighborhood, axis=0)).reshape(-1)
    global_differences = np.abs(np.diff(audio, axis=0)).reshape(-1)
    sample_jump = float(np.max(np.abs(audio[boundary_sample] - audio[boundary_sample - 1])))
    p50 = float(np.percentile(differences, 50)) if differences.size else 0.0
    p99 = float(np.percentile(differences, 99)) if differences.size else 0.0
    before_rms = _rms(before_short)
    after_rms = _rms(after_short)
    before_peak = float(np.max(np.abs(before_short)))
    after_peak = float(np.max(np.abs(after_short)))
    dc_jump = float(
        np.max(np.abs(np.mean(after_short, axis=0) - np.mean(before_short, axis=0)))
    )
    return {
        "decoded_samples_per_channel": int(len(audio)),
        "decoded_duration_seconds": float(len(audio) / sample_rate),
        "boundary_sample": int(boundary_sample),
        "boundary_seconds": float(boundary_sample / sample_rate),
        "sample_jump": sample_jump,
        "local_abs_diff_p50": p50,
        "local_abs_diff_p99": p99,
        "sample_jump_over_local_p99": sample_jump / p99 if p99 > 0 else math.inf,
        "global_abs_diff_p99": float(np.percentile(global_differences, 99)),
        "global_abs_diff_max": float(np.max(global_differences)),
        "sample_jump_global_percentile": float(
            100.0 * np.mean(global_differences <= sample_jump)
        ),
        "dc_jump_50ms": dc_jump,
        "rms_before_50ms": before_rms,
        "rms_after_50ms": after_rms,
        "rms_ratio_after_over_before": after_rms / before_rms if before_rms > 0 else math.inf,
        "peak_before_50ms": before_peak,
        "peak_after_50ms": after_peak,
        "peak_ratio_after_over_before": after_peak / before_peak if before_peak > 0 else math.inf,
        "zero_crossing_before_250ms": _zero_crossing_rate(before_long),
        "zero_crossing_after_250ms": _zero_crossing_rate(after_long),
        "spectral_cosine_distance_250ms": _spectral_distance(before_long, after_long),
        "finite": bool(np.isfinite(audio).all()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--masked", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, default=Path(r"C:\FFmpeg\bin\ffmpeg.exe"))
    parser.add_argument("--sample-rate", type=int, default=32000)
    parser.add_argument("--boundary-frame", type=int, default=124)
    parser.add_argument("--fps", type=float, default=24.0)
    args = parser.parse_args()

    boundary_sample = int(round(args.boundary_frame * args.sample_rate / args.fps))
    result = {
        "format": "h3-continuum-v36-r2-audio-boundary-v1",
        "sample_rate": int(args.sample_rate),
        "boundary_frame": int(args.boundary_frame),
        "fps": float(args.fps),
        "boundary_sample_rounding": "round(frame * sample_rate / fps)",
        "reference": {
            "path": str(args.reference),
            **boundary_metrics(
                _decode_audio(args.reference, args.ffmpeg, args.sample_rate),
                sample_rate=args.sample_rate,
                boundary_sample=boundary_sample,
            ),
        },
        "masked": {
            "path": str(args.masked),
            **boundary_metrics(
                _decode_audio(args.masked, args.ffmpeg, args.sample_rate),
                sample_rate=args.sample_rate,
                boundary_sample=boundary_sample,
            ),
        },
    }
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
