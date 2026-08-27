"""Run one V3.6-R1 masked-prefix A/B case through the ComfyUI API."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys
import uuid


TOOLS_ROOT = Path(__file__).resolve().parent
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from p32_api_runner import submit_and_wait


def configure_prompt(
    source: dict,
    *,
    transport: str,
    output_prefix: str,
    seed: int,
) -> dict:
    prompt = copy.deepcopy(source)
    for node_id in ("250", "292", "302", "304"):
        prompt.pop(node_id, None)

    sampler = prompt["305"]
    sampler["class_type"] = "H3ContinuumMaskedPrefixR1Diagnostic"
    sampler["_meta"] = {"title": "H3 Continuum V3.6-R1 Masked Prefix Diagnostic"}
    sampler["inputs"].update(
        {
            "prompt_mode": "Fixed — one prompt",
            "chunks": 2,
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
        }
    )
    prompt["188"]["inputs"]["value"] = (
        "A cinematic live-action tracking shot of one skateboarder moving "
        "continuously along a waterfront promenade. The subject maintains "
        "forward momentum, body pose, direction, and camera-relative speed "
        "throughout the shot. Natural city ambience, rolling skateboard wheels, "
        "and distant traffic are audible."
    )
    prompt["226"]["inputs"]["samples"] = ["305", 0]
    prompt["227"]["inputs"]["samples"] = ["305", 1]
    prompt["306"]["inputs"].update(
        {
            "audio_seam": "Off",
            "video_seam": "Off",
            "assembly_plan": ["305", 2],
            "driving_audio": ["305", 4],
        }
    )
    prompt["249"]["inputs"]["source"] = ["305", 3]
    prompt["191"]["inputs"]["filename_prefix"] = str(output_prefix)
    return prompt


def run(args) -> dict:
    source = json.loads(args.prompt.read_text(encoding="utf-8"))
    configured = configure_prompt(
        source,
        transport=args.transport,
        output_prefix=f"video/V36_R1_{args.transport}_seed{args.seed}",
        seed=args.seed,
    )
    args.output_root.mkdir(parents=True, exist_ok=True)
    prompt_path = args.output_root / f"prompt_{args.transport}.json"
    prompt_path.write_text(
        json.dumps(configured, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    prompt_id, history, elapsed = submit_and_wait(
        server=args.server,
        prompt=configured,
        client_id=f"v36-r1-{uuid.uuid4().hex}",
        timeout_seconds=args.timeout_seconds,
        poll_seconds=2.0,
    )
    history_path = args.output_root / f"history_{args.transport}.json"
    history_path.write_text(
        json.dumps(history, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    summary = {
        "format": "h3-continuum-v36-r1-api-run-v1",
        "transport": args.transport,
        "prompt_id": prompt_id,
        "api_elapsed_seconds": elapsed,
        "prompt": str(prompt_path),
        "history": str(history_path),
    }
    (args.output_root / f"summary_{args.transport}.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return summary


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default="http://127.0.0.1:8188")
    parser.add_argument("--prompt", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--transport",
        choices=("reference_context_v1", "masked_video_prefix_v1"),
        required=True,
    )
    parser.add_argument("--timeout-seconds", type=float, default=1800.0)
    parser.add_argument("--seed", type=int, default=238985343135586)
    return parser


def main() -> int:
    print(json.dumps(run(_parser().parse_args()), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
