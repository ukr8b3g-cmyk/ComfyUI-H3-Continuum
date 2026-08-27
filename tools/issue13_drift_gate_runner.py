"""Run the Issue #13 long-form contrast/style drift diagnostic matrix.

This tool is diagnostic-only.  It mutates an accepted API prompt in memory and
does not import into or change the Production node path.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import uuid


TOOLS_ROOT = Path(__file__).resolve().parent
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from p32_api_runner import submit_and_wait


BASE_PROMPT = (
    "A continuous cinematic live-action tracking shot of one woman in an "
    "orange jacket riding a skateboard steadily forward along a waterfront "
    "promenade. The camera follows her in one smooth direction. Preserve her "
    "face, clothing, skateboard, warm sunlight, detailed texture, rich color, "
    "and continuous forward motion. Natural skateboard wheels, wind, and "
    "distant city ambience are audible."
)

VARIED_PROMPTS = (
    BASE_PROMPT,
    BASE_PROMPT
    + " Keep the lighting natural and avoid increasing contrast or saturation.",
    BASE_PROMPT
    + " Use restrained color, soft highlight rolloff, and matte natural skin texture.",
    BASE_PROMPT
    + " Maintain neutral exposure, stable white balance, and gentle midtone contrast.",
    BASE_PROMPT
    + " Preserve the original natural color and texture without glossy or oily buildup.",
)

CASE_ORDER = (
    "fixed_standard",
    "list_same_standard",
    "timeline_same_standard",
    "list_varied_standard",
    "fixed_compatibility",
)


def _script_for_case(case: str) -> tuple[str, str, str]:
    if case == "fixed_standard":
        return "Fixed", BASE_PROMPT, "Standard"
    if case == "list_same_standard":
        return "List", "\n---\n".join([BASE_PROMPT] * 5), "Standard"
    if case == "timeline_same_standard":
        return (
            "Timeline",
            "\n\n".join(
                f"[Chunk {index}]\n{BASE_PROMPT}" for index in range(1, 6)
            ),
            "Standard",
        )
    if case == "list_varied_standard":
        return "List", "\n---\n".join(VARIED_PROMPTS), "Standard"
    if case == "fixed_compatibility":
        return "Fixed", BASE_PROMPT, "Compatibility"
    raise ValueError(f"unknown Issue #13 case: {case}")


def configure_prompt(
    source: dict,
    *,
    case: str,
    output_prefix: str,
    seed: int,
    steps: int,
    size: int,
) -> dict:
    prompt = copy.deepcopy(source)
    prompt_mode, script, backend = _script_for_case(case)

    sampler = prompt["305"]
    sampler["class_type"] = "H3ContinuumSamplerV36"
    sampler["_meta"] = {"title": f"Issue #13 Drift Diagnostic — {case}"}
    inputs = sampler["inputs"]
    inputs.update(
        {
            "prompt_mode": prompt_mode,
            "chunks": 5,
            "chunk_seconds": 5.0,
            "width": int(size),
            "height": int(size),
            "continuity": "Balanced — 22 frames",
            "base_seed": int(seed),
            "audio_continuity": True,
            "diagnostics": "Detailed Report",
            "reroll_from_chunk": "Auto",
            "reroll_nonce": 0,
            "strict_compatibility": False,
            "debug": False,
            "show_preview": False,
            "run_storage": "Off",
            "run_name": "",
            "project_id": "",
            "continuation_backend": backend,
            "first_frame": ["119", 0],
        }
    )
    for key in (
        "continuation_transport",
        "synchronize_sampling",
        "diagnostic_nonce",
        "last_frame",
    ):
        inputs.pop(key, None)

    prompt["188"]["inputs"]["value"] = script
    prompt["153"]["inputs"].update(
        {"scheduler": "simple", "steps": int(steps), "denoise": 1.0}
    )
    prompt["297"]["inputs"]["value"] = max(0.05, (float(size) * size) / 1_000_000.0)
    prompt["306"]["inputs"].update(
        {
            "audio_seam": "Off",
            "video_seam": "Off",
            "buffer_backend": "Auto",
            "diagnostics": "Detailed Report",
        }
    )
    prompt["191"]["inputs"]["filename_prefix"] = str(output_prefix)
    prompt["249"]["inputs"]["source"] = ["305", 3]
    return prompt


def _output_video(history: dict, prompt_id: str) -> dict | None:
    entry = history.get(str(prompt_id), {})
    outputs = entry.get("outputs", {}) if isinstance(entry, dict) else {}
    save = outputs.get("191", {}) if isinstance(outputs, dict) else {}
    images = save.get("images", []) if isinstance(save, dict) else []
    return images[0] if images else None


def _status_text(history: dict, prompt_id: str) -> str:
    entry = history.get(str(prompt_id), {})
    outputs = entry.get("outputs", {}) if isinstance(entry, dict) else {}
    preview = outputs.get("249", {}) if isinstance(outputs, dict) else {}
    values = preview.get("text", []) if isinstance(preview, dict) else []
    return str(values[0]) if values else ""


def run(args: argparse.Namespace) -> dict:
    source = json.loads(args.prompt.read_text(encoding="utf-8"))
    cases = list(args.cases or CASE_ORDER)
    unknown = [case for case in cases if case not in CASE_ORDER]
    if unknown:
        raise SystemExit(f"unknown --cases: {', '.join(unknown)}")

    args.output_root.mkdir(parents=True, exist_ok=True)
    summary_path = args.output_root / "summary.json"
    results = []
    if summary_path.exists():
        existing = json.loads(summary_path.read_text(encoding="utf-8"))
        results = list(existing.get("cases") or [])
    completed_cases = {str(item.get("case")) for item in results}
    for case in cases:
        if case in completed_cases:
            print(f"ISSUE13 SKIP completed case={case}", flush=True)
            continue
        configured = configure_prompt(
            source,
            case=case,
            output_prefix=f"video/issue13/Issue13_{case}_seed{args.seed}",
            seed=args.seed,
            steps=args.steps,
            size=args.size,
        )
        case_root = args.output_root / case
        case_root.mkdir(parents=True, exist_ok=True)
        prompt_path = case_root / "prompt.json"
        prompt_path.write_text(
            json.dumps(configured, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"ISSUE13 START case={case}", flush=True)
        prompt_id, history, elapsed = submit_and_wait(
            server=args.server,
            prompt=configured,
            client_id=f"issue13-{uuid.uuid4().hex}",
            timeout_seconds=args.timeout_seconds,
            poll_seconds=3.0,
        )
        history_path = case_root / "history.json"
        history_path.write_text(
            json.dumps(history, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        text = _status_text(history, prompt_id)
        result = {
            "case": case,
            "prompt_id": prompt_id,
            "api_elapsed_seconds": elapsed,
            "prompt": str(prompt_path),
            "history": str(history_path),
            "output_video": _output_video(history, prompt_id),
            "status_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "status": text,
        }
        (case_root / "summary.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        results.append(result)
        print(
            f"ISSUE13 COMPLETE case={case} prompt_id={prompt_id} "
            f"elapsed={elapsed:.3f}s",
            flush=True,
        )

    summary = {
        "format": "h3-continuum-issue13-drift-gate-v1",
        "server": args.server,
        "source_prompt": str(args.prompt),
        "seed": int(args.seed),
        "steps": int(args.steps),
        "size": int(args.size),
        "chunks": 5,
        "chunk_seconds": 5.0,
        "cases": results,
    }
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return summary


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default="http://127.0.0.6:8188")
    parser.add_argument("--prompt", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=130013)
    parser.add_argument("--steps", type=int, default=8)
    parser.add_argument("--size", type=int, default=384)
    parser.add_argument("--timeout-seconds", type=float, default=3600.0)
    parser.add_argument("--cases", nargs="*", choices=CASE_ORDER)
    return parser


def main() -> int:
    summary = run(_parser().parse_args())
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
