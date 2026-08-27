"""Run the research-only Reference 22f/37T vs 22f/40T GPU screen."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
import uuid


TOOLS_ROOT = Path(__file__).resolve().parent
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from p32_api_runner import submit_and_wait
from v36_r1_stress_gate_runner import (
    ResourceMonitor,
    _extract_evidence,
    configure_prompt,
)


PROMPTS = {
    "music": (
        "A continuous cinematic performance driven by a steady electronic dance "
        "beat at 120 BPM. The percussion, bass pulse, and musical phrase continue "
        "without stopping while the camera glides smoothly through a neon studio."
    ),
    "dialogue": (
        "A single radio host speaks continuously in a calm natural voice inside a "
        "quiet studio, maintaining the same speaker, room tone, cadence, and breath "
        "throughout the shot. <d>Tonight we follow the lights along the harbor, and "
        "every turn reveals another part of the city.</d>"
    ),
    "ambient": (
        "A continuous locked cinematic shot of steady rain falling outside a quiet "
        "workshop. Rainfall, a low ventilation hum, and distant machinery form an "
        "uninterrupted ambient sound bed with stable texture and level."
    ),
}

TRANSPORTS = {
    "baseline37": "reference_context_v1",
    "experimental40": "reference_context_audio40_research_v1",
}


def _configure(source, *, label, transport, seed, output_prefix, nonce):
    prompt = configure_prompt(
        source,
        transport=transport,
        output_prefix=output_prefix,
        seed=seed,
        chunks=3,
        synchronize_sampling=True,
        diagnostic_nonce=nonce,
    )
    prompt["188"]["inputs"]["value"] = PROMPTS[label]
    prompt["305"]["inputs"].update(
        {
            "width": 576,
            "height": 576,
            "audio_continuity": True,
            "continuation_transport": transport,
        }
    )
    prompt["306"]["inputs"].update(
        {
            "audio_seam": "Off",
            "video_seam": "Off",
            "exact_total_duration": True,
        }
    )
    prompt["191"]["inputs"]["filename_prefix"] = output_prefix
    return prompt


def _run_one(args, source, *, content, variant, order_index):
    transport = TRANSPORTS[variant]
    run_root = args.output_root / f"{order_index:02d}_{content}_{variant}"
    run_root.mkdir(parents=True, exist_ok=True)
    output_prefix = f"video/AudioResearch_{content}_{variant}_seed{args.seed}"
    prompt = _configure(
        source,
        label=content,
        transport=transport,
        seed=args.seed,
        output_prefix=output_prefix,
        nonce=order_index,
    )
    prompt_path = run_root / "prompt.json"
    prompt_path.write_text(json.dumps(prompt, indent=2), encoding="utf-8")
    with ResourceMonitor(args.backend_pid) as monitor:
        prompt_id, history, elapsed = submit_and_wait(
            server=args.server,
            prompt=prompt,
            client_id=f"audio-research-{uuid.uuid4().hex}",
            timeout_seconds=args.timeout_seconds,
            poll_seconds=2.0,
        )
    history_path = run_root / "history.json"
    history_path.write_text(json.dumps(history, indent=2), encoding="utf-8")
    summary = {
        "content": content,
        "variant": variant,
        "transport": transport,
        "seed": args.seed,
        "prompt_id": prompt_id,
        "api_elapsed_seconds": elapsed,
        "resources": monitor.as_dict(),
        "evidence": _extract_evidence(history),
        "output_prefix": output_prefix,
        "prompt": str(prompt_path),
        "history": str(history_path),
    }
    (run_root / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--server", default="http://127.0.0.6:8188")
    parser.add_argument("--seed", type=int, default=238985343135609)
    parser.add_argument("--backend-pid", type=int, default=None)
    parser.add_argument("--timeout-seconds", type=float, default=2400.0)
    args = parser.parse_args()

    source = json.loads(args.prompt.read_text(encoding="utf-8"))
    args.output_root.mkdir(parents=True, exist_ok=True)
    schedule = (
        ("music", "baseline37"),
        ("music", "experimental40"),
        ("dialogue", "experimental40"),
        ("dialogue", "baseline37"),
        ("ambient", "baseline37"),
        ("ambient", "experimental40"),
    )
    started = time.perf_counter()
    results = [
        _run_one(args, source, content=content, variant=variant, order_index=index)
        for index, (content, variant) in enumerate(schedule, start=1)
    ]
    aggregate = {
        "format": "h3-continuum-audio-context-research-v1",
        "elapsed_seconds": time.perf_counter() - started,
        "schedule": [list(item) for item in schedule],
        "results": results,
    }
    (args.output_root / "aggregate.json").write_text(
        json.dumps(aggregate, indent=2), encoding="utf-8"
    )
    print(json.dumps(aggregate, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
