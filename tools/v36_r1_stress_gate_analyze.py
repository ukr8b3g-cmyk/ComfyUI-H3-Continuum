#!/usr/bin/env python3
"""Aggregate V3.6-R1 Stress Gate timings and boundary video metrics."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

import cv2
import numpy as np


SAMPLING_RE = re.compile(r"sampling=([0-9.]+)s")


def _median(values: list[float]) -> float:
    values = sorted(values)
    middle = len(values) // 2
    if len(values) % 2:
        return values[middle]
    return (values[middle - 1] + values[middle]) / 2.0


def _read_summary(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sampling_seconds(run: dict) -> list[float]:
    values: list[float] = []
    for line in run["performance_lines"]:
        if "physical group" not in line:
            continue
        match = SAMPLING_RE.search(line)
        if match:
            values.append(float(match.group(1)))
    return values


def _video_path(output_prefix: str, output_dir: Path) -> Path:
    stem = Path(output_prefix).name
    matches = sorted(output_dir.glob(f"{stem}_*.mp4"), key=lambda path: path.stat().st_mtime)
    if not matches:
        raise FileNotFoundError(f"No output video for {stem}")
    return matches[-1]


def _read_frames(path: Path) -> tuple[list[np.ndarray], float]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"Unable to open {path}")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    frames: list[np.ndarray] = []
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        frames.append(frame)
    capture.release()
    return frames, fps


def _safe_cosine(left: np.ndarray, right: np.ndarray) -> float:
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    if denominator <= 1e-12:
        return 1.0
    return float(np.dot(left, right) / denominator)


def _boundary_metrics(frames: list[np.ndarray], boundary: int) -> dict:
    first = max(0, boundary - 12)
    last = min(len(frames) - 1, boundary + 24)
    magnitudes: list[float] = []
    mean_vectors: list[np.ndarray] = []
    for index in range(first, last):
        previous = cv2.cvtColor(frames[index], cv2.COLOR_BGR2GRAY)
        current = cv2.cvtColor(frames[index + 1], cv2.COLOR_BGR2GRAY)
        previous = cv2.resize(previous, (320, 320), interpolation=cv2.INTER_AREA)
        current = cv2.resize(current, (320, 320), interpolation=cv2.INTER_AREA)
        flow = cv2.calcOpticalFlowFarneback(
            previous,
            current,
            None,
            0.5,
            3,
            21,
            3,
            5,
            1.2,
            0,
        )
        magnitude = np.linalg.norm(flow, axis=2)
        magnitudes.append(float(np.median(magnitude)))
        mean_vectors.append(np.mean(flow.reshape(-1, 2), axis=0))

    transition_index = boundary - first - 1
    pre = magnitudes[max(0, transition_index - 6) : max(0, transition_index)]
    post = magnitudes[transition_index + 1 : transition_index + 7]
    pre_magnitude = float(np.median(pre)) if pre else 0.0
    post_magnitude = float(np.median(post)) if post else 0.0
    magnitude_ratio = post_magnitude / pre_magnitude if pre_magnitude > 1e-12 else math.inf

    pre_vectors = mean_vectors[max(0, transition_index - 6) : max(0, transition_index)]
    post_vectors = mean_vectors[transition_index + 1 : transition_index + 7]
    pre_vector = np.mean(pre_vectors, axis=0) if pre_vectors else np.zeros(2, dtype=np.float32)
    post_vector = np.mean(post_vectors, axis=0) if post_vectors else np.zeros(2, dtype=np.float32)

    accelerations = np.diff(np.asarray(magnitudes, dtype=np.float64))
    jerks = np.diff(accelerations)
    local_jerk = jerks[max(0, transition_index - 3) : transition_index + 4]

    before_frames = frames[max(0, boundary - 12) : boundary]
    after_frames = frames[boundary : min(len(frames), boundary + 24)]

    def color_stats(items: list[np.ndarray]) -> tuple[float, float, float]:
        if not items:
            return 0.0, 0.0, 0.0
        luma: list[float] = []
        contrast: list[float] = []
        saturation: list[float] = []
        for item in items:
            gray = cv2.cvtColor(item, cv2.COLOR_BGR2GRAY)
            hsv = cv2.cvtColor(item, cv2.COLOR_BGR2HSV)
            luma.append(float(gray.mean()))
            contrast.append(float(gray.std()))
            saturation.append(float(hsv[:, :, 1].mean()))
        return float(np.mean(luma)), float(np.mean(contrast)), float(np.mean(saturation))

    before_luma, before_contrast, before_saturation = color_stats(before_frames)
    after_luma, after_contrast, after_saturation = color_stats(after_frames)
    return {
        "boundary_frame": boundary,
        "flow_magnitude_pre": pre_magnitude,
        "flow_magnitude_post": post_magnitude,
        "flow_magnitude_ratio_post_over_pre": magnitude_ratio,
        "flow_direction_cosine": _safe_cosine(pre_vector, post_vector),
        "flow_peak_abs_jerk": float(np.max(np.abs(local_jerk))) if len(local_jerk) else 0.0,
        "luma_delta": after_luma - before_luma,
        "contrast_delta": after_contrast - before_contrast,
        "saturation_delta": after_saturation - before_saturation,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--normal-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()

    runs = []
    for summary_path in sorted(args.normal_root.glob("normal_*/summary.json")):
        run = _read_summary(summary_path)
        sampling = _sampling_seconds(run)
        diagnostics = run["diagnostic"]
        calls = diagnostics["sample_calls"]
        continuation_calls = calls[1:]
        video_path = _video_path(run["output_prefix"], args.output_dir)
        frames, fps = _read_frames(video_path)
        layouts = [call["packed_layouts"][0] for call in continuation_calls]
        runs.append(
            {
                "label": run["label"],
                "seed": run["seed"],
                "transport": run["transport"],
                "api_elapsed_seconds": run["api_elapsed_seconds"],
                "sampling_seconds": sampling,
                "continuation_sampling_seconds": sum(sampling[1:]),
                "sample_host_continuation_seconds": sum(
                    float(call["sample_host_elapsed_seconds"]) for call in continuation_calls
                ),
                "packed_seq_len": [layout["seq_len"] for layout in layouts],
                "packed_rows_by_kind": [layout["rows_by_kind"] for layout in layouts],
                "final_prefix_bit_exact": [
                    pair["bit_exact"] for pair in diagnostics["final_prefix_pairs"]
                ],
                "final_prefix_max_abs_diff": [
                    pair["max_abs_diff"] for pair in diagnostics["final_prefix_pairs"]
                ],
                "peak_process_rss_bytes": run["resources"]["peak_process_rss_bytes"],
                "peak_process_uss_bytes": run["resources"]["peak_process_uss_bytes"],
                "peak_device_used_bytes": run["resources"]["peak_device_used_bytes"],
                "video": str(video_path),
                "video_width": int(frames[0].shape[1]),
                "video_height": int(frames[0].shape[0]),
                "video_frames": len(frames),
                "video_fps": fps,
                "video_duration_seconds": len(frames) / fps,
                "boundaries": [_boundary_metrics(frames, boundary) for boundary in (120, 240)],
            }
        )

    pairs = []
    for seed in sorted({run["seed"] for run in runs}):
        by_transport = {run["transport"]: run for run in runs if run["seed"] == seed}
        reference = by_transport["reference_context_v1"]
        masked = by_transport["masked_video_prefix_v1"]
        pairs.append(
            {
                "seed": seed,
                "reference_api_seconds": reference["api_elapsed_seconds"],
                "masked_api_seconds": masked["api_elapsed_seconds"],
                "api_masked_faster_seconds": reference["api_elapsed_seconds"]
                - masked["api_elapsed_seconds"],
                "api_masked_faster_percent": 100.0
                * (reference["api_elapsed_seconds"] - masked["api_elapsed_seconds"])
                / reference["api_elapsed_seconds"],
                "reference_continuation_sampling_seconds": reference[
                    "continuation_sampling_seconds"
                ],
                "masked_continuation_sampling_seconds": masked[
                    "continuation_sampling_seconds"
                ],
                "continuation_masked_faster_percent": 100.0
                * (
                    reference["continuation_sampling_seconds"]
                    - masked["continuation_sampling_seconds"]
                )
                / reference["continuation_sampling_seconds"],
            }
        )

    result = {
        "format": "h3-continuum-v36-r1-stress-gate-analysis-v1",
        "runs": runs,
        "pairs": pairs,
        "medians": {
            "reference_api_seconds": _median(
                [run["api_elapsed_seconds"] for run in runs if run["transport"] == "reference_context_v1"]
            ),
            "masked_api_seconds": _median(
                [run["api_elapsed_seconds"] for run in runs if run["transport"] == "masked_video_prefix_v1"]
            ),
            "api_masked_faster_percent": _median(
                [pair["api_masked_faster_percent"] for pair in pairs]
            ),
            "reference_continuation_sampling_seconds": _median(
                [pair["reference_continuation_sampling_seconds"] for pair in pairs]
            ),
            "masked_continuation_sampling_seconds": _median(
                [pair["masked_continuation_sampling_seconds"] for pair in pairs]
            ),
            "continuation_masked_faster_percent": _median(
                [pair["continuation_masked_faster_percent"] for pair in pairs]
            ),
        },
    }
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"pairs": pairs, "medians": result["medians"]}, indent=2))


if __name__ == "__main__":
    main()
