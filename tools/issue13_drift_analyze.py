"""Measure chunk-wise color/contrast drift and build an Issue #13 contact sheet."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def _video_path(output_root: Path, record: dict, video_root: Path) -> Path:
    item = record.get("output_video") or {}
    return video_root / str(item.get("subfolder", "")) / str(item.get("filename", ""))


def _read_frames(path: Path) -> tuple[list[np.ndarray], float]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"cannot open video: {path}")
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 24.0)
    frames = []
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    capture.release()
    if not frames:
        raise RuntimeError(f"video contains no frames: {path}")
    return frames, fps


def _frame_metrics(frame: np.ndarray) -> dict[str, float]:
    rgb = frame.astype(np.float32) / 255.0
    y = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV).astype(np.float32)
    saturation = hsv[..., 1] / 255.0
    return {
        "luma_mean": float(np.mean(y)),
        "luma_std": float(np.std(y)),
        "red_mean": float(np.mean(rgb[..., 0])),
        "green_mean": float(np.mean(rgb[..., 1])),
        "blue_mean": float(np.mean(rgb[..., 2])),
        "saturation_mean": float(np.mean(saturation)),
        "saturation_p95": float(np.percentile(saturation, 95)),
        "contrast_p95_p05": float(np.percentile(y, 95) - np.percentile(y, 5)),
        "highlight_clip_fraction": float(np.mean(y >= (250.0 / 255.0))),
        "shadow_clip_fraction": float(np.mean(y <= (5.0 / 255.0))),
    }


def _chunk_metrics(frames: list[np.ndarray], *, chunks: int, radius: int) -> tuple[list[dict], list[np.ndarray]]:
    frame_count = len(frames)
    rows = []
    representatives = []
    for index in range(chunks):
        center = int(round((index + 0.5) * frame_count / chunks))
        center = min(max(center, 0), frame_count - 1)
        start = max(0, center - radius)
        end = min(frame_count, center + radius + 1)
        values = [_frame_metrics(frame) for frame in frames[start:end]]
        merged = {
            key: float(np.mean([item[key] for item in values])) for key in values[0]
        }
        merged.update(
            {
                "chunk": index + 1,
                "center_frame": center,
                "sample_start": start,
                "sample_end_exclusive": end,
                "sample_count": end - start,
            }
        )
        rows.append(merged)
        representatives.append(frames[center])
    return rows, representatives


def _contact_sheet(rows: list[tuple[str, list[np.ndarray]]], output: Path) -> None:
    thumb_w, thumb_h = 256, 256
    label_w, top_h = 220, 42
    width = label_w + thumb_w * 5
    height = top_h + thumb_h * len(rows)
    sheet = Image.new("RGB", (width, height), (9, 15, 25))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for column in range(5):
        draw.text(
            (label_w + column * thumb_w + 8, 14),
            f"Chunk {column + 1}",
            fill=(210, 225, 245),
            font=font,
        )
    for row_index, (label, frames) in enumerate(rows):
        y = top_h + row_index * thumb_h
        draw.text((10, y + 16), label, fill=(115, 210, 255), font=font)
        for column, frame in enumerate(frames):
            image = Image.fromarray(frame).resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
            sheet.paste(image, (label_w + column * thumb_w, y))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def run(args: argparse.Namespace) -> dict:
    summary = json.loads((args.output_root / "summary.json").read_text(encoding="utf-8"))
    all_rows = []
    sheets = []
    videos = {}
    for record in summary["cases"]:
        case = str(record["case"])
        path = _video_path(args.output_root, record, args.video_root)
        frames, fps = _read_frames(path)
        metrics, representatives = _chunk_metrics(
            frames, chunks=5, radius=args.radius
        )
        for row in metrics:
            row["case"] = case
            row["video"] = str(path)
            row["fps"] = fps
            row["frame_count"] = len(frames)
            all_rows.append(row)
        sheets.append((case, representatives))
        videos[case] = {
            "path": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "fps": fps,
            "frame_count": len(frames),
            "metrics": metrics,
            "drift_chunk5_minus_chunk1": {
                key: metrics[-1][key] - metrics[0][key]
                for key in (
                    "luma_mean",
                    "luma_std",
                    "saturation_mean",
                    "saturation_p95",
                    "contrast_p95_p05",
                    "highlight_clip_fraction",
                    "shadow_clip_fraction",
                )
            },
        }

    csv_path = args.output_root / "chunk_metrics.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(all_rows[0]))
        writer.writeheader()
        writer.writerows(all_rows)
    contact_path = args.output_root / "contact_sheet.png"
    _contact_sheet(sheets, contact_path)
    result = {
        "format": "h3-continuum-issue13-drift-analysis-v1",
        "sample_radius_frames": args.radius,
        "videos": videos,
        "csv": str(csv_path),
        "contact_sheet": str(contact_path),
    }
    (args.output_root / "analysis.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False))
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--video-root", type=Path, default=Path(r"D:\output\video\comfy_video")
    )
    parser.add_argument("--radius", type=int, default=12)
    return parser


if __name__ == "__main__":
    run(_parser().parse_args())
