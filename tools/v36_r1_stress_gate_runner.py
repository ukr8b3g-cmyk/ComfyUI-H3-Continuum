"""Run the V3.6-R1 three-chunk I2VA Strong Motion Stress Gate."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import re
import sys
import threading
import time
import uuid
from typing import Any, Mapping


TOOLS_ROOT = Path(__file__).resolve().parent
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from p32_api_runner import submit_and_wait


STRONG_MOTION_PROMPT = (
    "A dynamic cinematic live-action shot of the woman in the orange jacket "
    "accelerating rapidly on her skateboard along the waterfront promenade. "
    "She performs fast continuous S-turns, leaning deeply from side to side "
    "while her hair and jacket react to speed. The low tracking camera sweeps "
    "alongside her with a strong continuous pan and partial orbit, maintaining "
    "motion through the sequence while preserving her face, orange jacket, "
    "white trousers, skateboard, city skyline, cool daylight, and natural contrast."
)

TRANSPORTS = ("reference_context_v1", "masked_video_prefix_v1")


def _walk_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from _walk_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_strings(item)


def _extract_evidence(history: Mapping[str, Any]) -> dict[str, Any]:
    lines: list[str] = []
    diagnostic = None
    for text in _walk_strings(history):
        for line in text.splitlines():
            if line.startswith(("Prompt/CLIP cache [V3.5]", "Performance [V3.5")):
                lines.append(line)
            marker = "V3.6-R1 diagnostic: "
            if marker in line:
                diagnostic = json.loads(line.split(marker, 1)[1])
    cache_line = next(
        (line for line in lines if line.startswith("Prompt/CLIP cache [V3.5]")),
        None,
    )
    cache = None
    if cache_line:
        match = re.search(
            r"hits=(\d+), misses=(\d+), bypasses=(\d+), encode_calls=(\d+)",
            cache_line,
        )
        if match:
            cache = {
                "hits": int(match.group(1)),
                "misses": int(match.group(2)),
                "bypasses": int(match.group(3)),
                "encode_calls": int(match.group(4)),
            }
    return {
        "prompt_clip_cache": cache,
        "performance_lines": lines,
        "diagnostic": diagnostic,
    }


class ResourceMonitor:
    def __init__(self, backend_pid: int | None, interval_seconds: float = 1.0):
        self.backend_pid = int(backend_pid) if backend_pid else None
        self.interval_seconds = float(interval_seconds)
        self.peak_process_rss_bytes = 0
        self.peak_process_uss_bytes = 0
        self.minimum_system_available_bytes: int | None = None
        self.peak_device_used_bytes = 0
        self.samples = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._psutil = None
        self._process = None
        self._nvml = None
        self._nvml_handle = None

    def __enter__(self):
        try:
            import psutil

            self._psutil = psutil
            if self.backend_pid:
                self._process = psutil.Process(self.backend_pid)
        except Exception:
            self._psutil = None
            self._process = None
        try:
            import pynvml

            pynvml.nvmlInit()
            self._nvml = pynvml
            self._nvml_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        except Exception:
            self._nvml = None
            self._nvml_handle = None
        self._sample()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(2.0, self.interval_seconds * 2.0))
        self._sample()
        if self._nvml is not None:
            try:
                self._nvml.nvmlShutdown()
            except Exception:
                pass

    def _loop(self):
        while not self._stop.wait(self.interval_seconds):
            self._sample()

    def _sample(self):
        self.samples += 1
        if self._psutil is not None:
            try:
                available = int(self._psutil.virtual_memory().available)
                if self.minimum_system_available_bytes is None:
                    self.minimum_system_available_bytes = available
                else:
                    self.minimum_system_available_bytes = min(
                        self.minimum_system_available_bytes, available
                    )
            except Exception:
                pass
        if self._process is not None:
            try:
                self.peak_process_rss_bytes = max(
                    self.peak_process_rss_bytes,
                    int(self._process.memory_info().rss),
                )
                full = self._process.memory_full_info()
                self.peak_process_uss_bytes = max(
                    self.peak_process_uss_bytes,
                    int(getattr(full, "uss", 0) or 0),
                )
            except Exception:
                pass
        if self._nvml is not None and self._nvml_handle is not None:
            try:
                used = int(self._nvml.nvmlDeviceGetMemoryInfo(self._nvml_handle).used)
                self.peak_device_used_bytes = max(self.peak_device_used_bytes, used)
            except Exception:
                pass

    def as_dict(self) -> dict[str, Any]:
        return {
            "backend_pid": self.backend_pid,
            "samples": int(self.samples),
            "peak_process_rss_bytes": int(self.peak_process_rss_bytes),
            "peak_process_uss_bytes": int(self.peak_process_uss_bytes),
            "minimum_system_available_bytes": self.minimum_system_available_bytes,
            "peak_device_used_bytes": int(self.peak_device_used_bytes),
        }


def configure_prompt(
    source: Mapping[str, Any],
    *,
    transport: str,
    output_prefix: str,
    seed: int,
    chunks: int,
    synchronize_sampling: bool,
    diagnostic_nonce: int,
) -> dict[str, Any]:
    prompt = copy.deepcopy(dict(source))
    sampler = prompt["305"]
    sampler["class_type"] = "H3ContinuumMaskedPrefixR1Diagnostic"
    sampler["_meta"] = {"title": "H3 Continuum V3.6-R1 Stress Diagnostic"}
    sampler["inputs"].update(
        {
            "prompt_mode": "Fixed — one prompt",
            "chunks": int(chunks),
            "chunk_seconds": 5.0,
            "width": 640,
            "height": 640,
            "continuity": "Balanced — 22 frames",
            "base_seed": int(seed),
            "audio_continuity": False,
            "diagnostics": "Detailed Report",
            "show_preview": False,
            "run_storage": "Off",
            "continuation_transport": str(transport),
            "synchronize_sampling": bool(synchronize_sampling),
            "diagnostic_nonce": int(diagnostic_nonce),
        }
    )
    prompt["188"]["inputs"]["value"] = STRONG_MOTION_PROMPT
    prompt["306"]["inputs"].update(
        {
            "exact_total_duration": True,
            "audio_seam": "Off",
            "video_seam": "Off",
            "buffer_backend": "Auto",
            "diagnostics": "Detailed Report",
        }
    )
    prompt["191"]["inputs"]["filename_prefix"] = str(output_prefix)
    return prompt


def _run_one(
    *,
    source: Mapping[str, Any],
    args,
    label: str,
    transport: str,
    seed: int,
    chunks: int,
    synchronize_sampling: bool,
    nonce: int,
    warmup: bool,
) -> dict[str, Any]:
    run_root = args.output_root / label
    run_root.mkdir(parents=True, exist_ok=True)
    output_prefix = f"video/V36_R1_Stress_{label}_seed{seed}"
    prompt = configure_prompt(
        source,
        transport=transport,
        output_prefix=output_prefix,
        seed=seed,
        chunks=chunks,
        synchronize_sampling=synchronize_sampling,
        diagnostic_nonce=nonce,
    )
    prompt_path = run_root / "prompt.json"
    prompt_path.write_text(
        json.dumps(prompt, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(
        f"START label={label} transport={transport} seed={seed} chunks={chunks} "
        f"sync={synchronize_sampling}",
        flush=True,
    )
    with ResourceMonitor(args.backend_pid, args.monitor_interval) as monitor:
        prompt_id, history, elapsed = submit_and_wait(
            server=args.server,
            prompt=prompt,
            client_id=f"v36-r1-stress-{uuid.uuid4().hex}",
            timeout_seconds=args.timeout_seconds,
            poll_seconds=args.poll_seconds,
        )
    history_path = run_root / "history.json"
    history_path.write_text(
        json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    evidence = _extract_evidence(history)
    result = {
        "label": label,
        "warmup": bool(warmup),
        "transport": transport,
        "seed": int(seed),
        "chunks": int(chunks),
        "synchronize_sampling": bool(synchronize_sampling),
        "prompt_id": prompt_id,
        "api_elapsed_seconds": float(elapsed),
        "output_prefix": output_prefix,
        "prompt": str(prompt_path),
        "history": str(history_path),
        "resources": monitor.as_dict(),
        **evidence,
    }
    (run_root / "summary.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    cache = result.get("prompt_clip_cache")
    if not warmup and (not cache or cache.get("encode_calls") != 0):
        raise RuntimeError(
            f"measured run {label} did not use the required Prompt/CLIP cache HIT: {cache}"
        )
    diagnostic = result.get("diagnostic") or {}
    calls = list(diagnostic.get("sample_calls") or [])
    if transport == "masked_video_prefix_v1" and chunks >= 2:
        for call in calls[1:]:
            layouts = list(call.get("packed_layouts") or [])
            if not layouts:
                raise RuntimeError(f"masked continuation call has no PackedLayout evidence: {label}")
            rows = dict(layouts[0].get("rows_by_kind") or {})
            if int(rows.get("cond", 0)) != 0 or int(rows.get("ref_img", 0)) != 0:
                raise RuntimeError(
                    f"masked continuation retained unfair I2VA/reference rows in {label}: {rows}"
                )
        final_pairs = list(diagnostic.get("final_prefix_pairs") or [])
        if len(final_pairs) != chunks - 1 or not all(
            bool(item.get("bit_exact")) for item in final_pairs
        ):
            raise RuntimeError(
                f"masked final prefix contract failed in {label}: {final_pairs}"
            )
    print(
        f"DONE label={label} elapsed={elapsed:.3f}s cache={cache} "
        f"rss={monitor.peak_process_rss_bytes / 2**30:.3f}GiB",
        flush=True,
    )
    return result


def run(args) -> dict[str, Any]:
    source = json.loads(args.prompt.read_text(encoding="utf-8"))
    args.output_root.mkdir(parents=True, exist_ok=True)
    seeds = [int(args.seed) + index for index in range(3)]
    if args.mode == "normal":
        schedule = [
            (seeds[0], "reference_context_v1"),
            (seeds[0], "masked_video_prefix_v1"),
            (seeds[1], "masked_video_prefix_v1"),
            (seeds[1], "reference_context_v1"),
            (seeds[2], "reference_context_v1"),
            (seeds[2], "masked_video_prefix_v1"),
        ]
    else:
        schedule = [
            (seeds[0], "reference_context_v1"),
            (seeds[0], "masked_video_prefix_v1"),
        ]

    results = []
    nonce = int(time.time()) & 0x7FFFFFFF
    if not args.skip_warmup:
        results.append(
            _run_one(
                source=source,
                args=args,
                label=f"warmup_{args.mode}",
                transport="masked_video_prefix_v1",
                seed=seeds[0],
                chunks=int(args.warmup_chunks),
                synchronize_sampling=False,
                nonce=nonce,
                warmup=True,
            )
        )
        nonce += 1

    for index, (seed, transport) in enumerate(schedule, start=1):
        short = "reference" if transport.startswith("reference") else "masked"
        label = f"{args.mode}_{index:02d}_seed{seed}_{short}"
        results.append(
            _run_one(
                source=source,
                args=args,
                label=label,
                transport=transport,
                seed=seed,
                chunks=3,
                synchronize_sampling=args.mode == "sync",
                nonce=nonce,
                warmup=False,
            )
        )
        nonce += 1

    summary = {
        "format": "h3-continuum-v36-r1-stress-gate-v1",
        "mode": args.mode,
        "server": args.server,
        "base_seed": int(args.seed),
        "warmup_excluded": True,
        "pinned_memory_required_disabled": True,
        "runs": results,
    }
    (args.output_root / "stress_gate_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return summary


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default="http://127.0.0.1:8188")
    parser.add_argument("--prompt", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--mode", choices=("normal", "sync"), default="normal")
    parser.add_argument("--seed", type=int, default=238985343135601)
    parser.add_argument("--backend-pid", type=int)
    parser.add_argument("--timeout-seconds", type=float, default=2400.0)
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument("--monitor-interval", type=float, default=1.0)
    parser.add_argument("--skip-warmup", action="store_true")
    parser.add_argument("--warmup-chunks", type=int, choices=(1, 2), default=1)
    return parser


def main() -> int:
    args = _parser().parse_args()
    print(json.dumps(run(args), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
