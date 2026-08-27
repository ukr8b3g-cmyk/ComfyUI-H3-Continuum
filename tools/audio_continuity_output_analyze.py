"""Analyze finalized Audio Continuity research outputs without changing them."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

import numpy as np
import torch

from v36_r2_audio_boundary_analyze import _decode_audio, boundary_metrics


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "ComfyUI_H3_Continuum_Join"


def _load_package() -> None:
    if PACKAGE_NAME in sys.modules:
        return
    spec = importlib.util.spec_from_file_location(
        PACKAGE_NAME,
        ROOT / "__init__.py",
        submodule_search_locations=[str(ROOT)],
    )
    if spec is None:
        raise RuntimeError("could not create the Continuum package spec")
    module = importlib.util.module_from_spec(spec)
    module.__path__ = [str(ROOT)]
    sys.modules[PACKAGE_NAME] = module


_load_package()
from ComfyUI_H3_Continuum_Join.v2.seam_guard import _correlation  # noqa: E402


def _window_rms_floor(value: np.ndarray, *, sample_rate: int) -> float:
    frame = max(1, int(round(sample_rate * 0.010)))
    usable = len(value) // frame * frame
    if usable <= 0:
        return 0.0
    blocks = value[:usable].reshape(-1, frame, value.shape[1])
    rms = np.sqrt(np.mean(np.square(blocks), axis=(1, 2)))
    return float(np.percentile(rms, 10))


def _adjacent_alignment(
    audio: np.ndarray,
    *,
    sample_rate: int,
    boundary_sample: int,
) -> dict[str, Any]:
    mono = torch.from_numpy(audio.mean(axis=1).astype(np.float32, copy=False))
    window = max(8, int(round(sample_rate * 0.080)))
    max_lag = max(1, int(round(sample_rate * 0.020)))
    before = mono[:boundary_sample]
    after = mono[boundary_sample:]
    if before.numel() < window + max_lag or after.numel() < window + max_lag:
        raise ValueError("insufficient decoded audio for adjacent-window alignment")

    def correlation_at(lag: int) -> float:
        if lag >= 0:
            left = before[-window:]
            right = after[lag : lag + window]
        else:
            stop = int(before.numel()) + lag
            left = before[stop - window : stop]
            right = after[:window]
        return float(_correlation(left, right))

    baseline = correlation_at(0)
    candidates = [(lag, correlation_at(lag)) for lag in range(-max_lag, max_lag + 1)]
    best_lag, best_correlation = max(candidates, key=lambda item: item[1])
    return {
        "window_ms": 80.0,
        "search_ms": 20.0,
        "correlation_at_zero": baseline,
        "best_correlation": best_correlation,
        "best_lag_samples": int(best_lag),
        "best_lag_ms": float(best_lag * 1000.0 / sample_rate),
    }


def _probe(path: Path, ffprobe: Path) -> dict[str, Any]:
    completed = subprocess.run(
        [
            str(ffprobe),
            "-v",
            "error",
            "-count_frames",
            "-show_entries",
            "stream=index,codec_type,width,height,nb_read_frames,duration,sample_rate,channels",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return json.loads(completed.stdout)


def analyze(
    path: Path,
    *,
    ffmpeg: Path,
    ffprobe: Path,
    sample_rate: int,
    fps: float,
    boundary_frames: list[int],
    expected_frames: int,
) -> dict[str, Any]:
    audio = _decode_audio(path, ffmpeg, sample_rate)
    pcm = audio.astype("<f4", copy=False).tobytes(order="C")
    boundaries: list[dict[str, Any]] = []
    long = max(1, int(round(sample_rate * 0.250)))
    for frame in boundary_frames:
        sample = int(round(frame * sample_rate / fps))
        before = audio[max(0, sample - long) : sample]
        after = audio[sample : min(len(audio), sample + long)]
        boundaries.append(
            {
                "frame": int(frame),
                **boundary_metrics(audio, sample_rate=sample_rate, boundary_sample=sample),
                **_adjacent_alignment(
                    audio,
                    sample_rate=sample_rate,
                    boundary_sample=sample,
                ),
                "rms_floor_before_250ms_p10_10ms": _window_rms_floor(
                    before, sample_rate=sample_rate
                ),
                "rms_floor_after_250ms_p10_10ms": _window_rms_floor(
                    after, sample_rate=sample_rate
                ),
            }
        )
    expected_duration = expected_frames / fps
    decoded_duration = len(audio) / sample_rate
    return {
        "format": "h3-continuum-audio-continuity-output-analysis-v1",
        "path": str(path),
        "sample_rate": int(sample_rate),
        "fps": float(fps),
        "expected_frames": int(expected_frames),
        "expected_duration_seconds": expected_duration,
        "decoded_samples_per_channel": int(len(audio)),
        "decoded_duration_seconds": decoded_duration,
        "decoded_duration_error_seconds": decoded_duration - expected_duration,
        "pcm_f32le_md5": hashlib.md5(pcm).hexdigest(),
        "finite": bool(np.isfinite(audio).all()),
        "probe": _probe(path, ffprobe),
        "boundaries": boundaries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, default=Path(r"C:\FFmpeg\bin\ffmpeg.exe"))
    parser.add_argument("--ffprobe", type=Path, default=Path(r"C:\FFmpeg\bin\ffprobe.exe"))
    parser.add_argument("--sample-rate", type=int, default=32000)
    parser.add_argument("--fps", type=float, default=24.0)
    parser.add_argument("--expected-frames", type=int, default=360)
    parser.add_argument("--boundary-frames", type=int, nargs="+", default=[124, 243])
    args = parser.parse_args()
    result = analyze(
        args.input,
        ffmpeg=args.ffmpeg,
        ffprobe=args.ffprobe,
        sample_rate=args.sample_rate,
        fps=args.fps,
        boundary_frames=list(args.boundary_frames),
        expected_frames=args.expected_frames,
    )
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
