"""Run one-seed V3.6-R2 Joint AV GPU structure gates."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys
import time
import uuid
from typing import Any, Mapping


TOOLS_ROOT = Path(__file__).resolve().parent
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from p32_api_runner import submit_and_wait
from v36_r1_stress_gate_runner import ResourceMonitor, _extract_evidence


PROFILES = {
    "r2-1-39": {
        "continuity": "Strong — 39 frames (Experimental)",
        "transport": "masked_av_prefix_39_v1",
        "reference_label": "reference_39f",
        "masked_label": "masked_av_39f_65t",
        "output_tag": "R2_Gate1",
    },
    "r2-2-22": {
        "continuity": "Balanced — 22 frames",
        "transport": "masked_av_prefix_22_v1",
        "reference_label": "reference_22f",
        "masked_label": "masked_av_22f_37t",
        "output_tag": "R2_Gate2",
    },
}
PROMPT = (
    "A continuous cinematic live-action tracking shot of one skateboarder "
    "moving steadily along a waterfront promenade while the camera follows at "
    "constant speed. Preserve forward motion, body pose, direction, and camera "
    "movement through the entire shot. Natural city ambience, rolling skateboard "
    "wheels, wind, and distant traffic continue without interruption."
)


def configure_prompt(
    source: Mapping[str, Any],
    *,
    transport: str,
    output_prefix: str,
    seed: int,
    synchronize_sampling: bool,
    diagnostic_nonce: int,
    chunks: int,
    continuity: str,
) -> dict[str, Any]:
    prompt = copy.deepcopy(dict(source))
    sampler = prompt["305"]
    sampler["class_type"] = "H3ContinuumMaskedPrefixR1Diagnostic"
    sampler["_meta"] = {"title": "H3 Continuum V3.6-R2 Joint AV Diagnostic"}
    sampler["inputs"].pop("first_frame", None)
    sampler["inputs"].update(
        {
            "prompt_mode": "Fixed — one prompt",
            "chunks": int(chunks),
            "chunk_seconds": 5.0,
            "width": 640,
            "height": 640,
            "continuity": str(continuity),
            "base_seed": int(seed),
            "audio_continuity": True,
            "diagnostics": "Detailed Report",
            "show_preview": False,
            "run_storage": "Off",
            "continuation_transport": str(transport),
            "synchronize_sampling": bool(synchronize_sampling),
            "diagnostic_nonce": int(diagnostic_nonce),
        }
    )
    prompt["188"]["inputs"]["value"] = PROMPT
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


def _validate_masked(diagnostic: Mapping[str, Any]) -> None:
    calls = list(diagnostic.get("sample_calls") or [])
    if len(calls) != 2:
        raise RuntimeError(f"expected two physical Sampling calls, got {len(calls)}")
    continuation = calls[1]
    if continuation.get("minimax_ref_kinds"):
        raise RuntimeError(
            f"masked AV continuation unexpectedly emitted refs: "
            f"{continuation.get('minimax_ref_kinds')}"
        )
    if bool(continuation.get("continuum_interop_emitted")):
        raise RuntimeError("masked AV continuation emitted old Spectrum interop")
    checks = {
        "source_tail_matches_target_prefix": True,
        "source_audio_tail_matches_target_prefix": True,
        "video_mask_prefix_zero": True,
        "video_mask_generated_one": True,
        "audio_mask_prefix_zero": True,
        "audio_mask_generated_one": True,
    }
    for name, expected in checks.items():
        if continuation.get(name) is not expected:
            raise RuntimeError(f"masked AV evidence failed {name}: {continuation.get(name)!r}")
    pairs = list(diagnostic.get("final_prefix_pairs") or [])
    if len(pairs) != 1:
        raise RuntimeError(f"expected one finalized AV prefix pair, got {len(pairs)}")
    pair = pairs[0]
    if not bool(pair.get("bit_exact")) or float(pair.get("max_abs_diff", 1.0)) != 0.0:
        raise RuntimeError(f"final video prefix is not bit-exact: {pair}")
    if not bool(pair.get("audio_bit_exact")) or float(
        pair.get("audio_max_abs_diff", 1.0)
    ) != 0.0:
        raise RuntimeError(f"final audio prefix is not bit-exact: {pair}")


def _validate_reference(diagnostic: Mapping[str, Any]) -> None:
    calls = list(diagnostic.get("sample_calls") or [])
    if len(calls) != 2:
        raise RuntimeError(f"expected two physical Sampling calls, got {len(calls)}")
    continuation = calls[1]
    kinds = list(continuation.get("minimax_ref_kinds") or [])
    separate_av = "video" in kinds and "audio" in kinds
    combined_av = "video_audio" in kinds
    if not separate_av and not combined_av:
        raise RuntimeError(f"39f reference route lacks AV refs: {kinds}")
    if not bool(continuation.get("continuum_interop_emitted")):
        raise RuntimeError("39f reference route lacks Continuum interop")


def _run_one(
    *,
    source: Mapping[str, Any],
    args,
    transport: str,
    label: str,
    nonce: int,
    chunks: int,
    warmup: bool,
) -> dict[str, Any]:
    run_root = args.output_root / label
    run_root.mkdir(parents=True, exist_ok=True)
    profile = PROFILES[args.profile]
    output_prefix = f"video/V36_{profile['output_tag']}_{label}_seed{args.seed}"
    prompt = configure_prompt(
        source,
        transport=transport,
        output_prefix=output_prefix,
        seed=args.seed,
        synchronize_sampling=not warmup,
        diagnostic_nonce=nonce,
        chunks=chunks,
        continuity=str(profile["continuity"]),
    )
    prompt_path = run_root / "prompt.json"
    prompt_path.write_text(
        json.dumps(prompt, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"START {label} transport={transport} chunks={chunks}", flush=True)
    with ResourceMonitor(args.backend_pid, args.monitor_interval) as monitor:
        prompt_id, history, elapsed = submit_and_wait(
            server=args.server,
            prompt=prompt,
            client_id=f"v36-r2-{uuid.uuid4().hex}",
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
        "seed": int(args.seed),
        "chunks": int(chunks),
        "synchronize_sampling": not warmup,
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
        raise RuntimeError(f"measured run did not use Prompt/CLIP cache HIT: {cache}")
    if not warmup:
        diagnostic = result.get("diagnostic") or {}
        if transport.startswith("masked_av_prefix_"):
            _validate_masked(diagnostic)
        else:
            _validate_reference(diagnostic)
    print(f"DONE {label} elapsed={elapsed:.3f}s cache={cache}", flush=True)
    return result


def run(args) -> dict[str, Any]:
    source = json.loads(args.prompt.read_text(encoding="utf-8"))
    profile = PROFILES[args.profile]
    args.output_root.mkdir(parents=True, exist_ok=True)
    nonce = int(time.time()) & 0x7FFFFFFF
    runs = []
    schedule = [(str(profile["transport"]), str(profile["masked_label"]))]
    if not args.resume_masked_only:
        runs.append(
            _run_one(
                source=source,
                args=args,
                transport=str(profile["transport"]),
                label="warmup",
                nonce=nonce,
                chunks=1,
                warmup=True,
            )
        )
        schedule.insert(0, ("reference_context_v1", str(profile["reference_label"])))
    for transport, label in schedule:
        nonce += 1
        runs.append(
            _run_one(
                source=source,
                args=args,
                transport=transport,
                label=label,
                nonce=nonce,
                chunks=2,
                warmup=False,
            )
        )
    result = {
        "format": "h3-continuum-v36-r2-gpu-structure-gate-v1",
        "server": args.server,
        "seed": int(args.seed),
        "profile": args.profile,
        "continuity": str(profile["continuity"]),
        "audio_continuity": True,
        "synchronized_sampling": True,
        "runs": runs,
    }
    (args.output_root / "gate_summary.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default="http://127.0.0.1:8188")
    parser.add_argument("--prompt", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=238985343135604)
    parser.add_argument("--profile", choices=tuple(PROFILES), default="r2-1-39")
    parser.add_argument("--backend-pid", type=int)
    parser.add_argument("--timeout-seconds", type=float, default=2400.0)
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument("--monitor-interval", type=float, default=1.0)
    parser.add_argument(
        "--resume-masked-only",
        action="store_true",
        help="Resume after a completed Reference run without repeating it.",
    )
    return parser


def main() -> int:
    print(json.dumps(run(_parser().parse_args()), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
