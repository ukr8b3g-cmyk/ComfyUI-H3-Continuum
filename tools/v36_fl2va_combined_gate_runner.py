"""Run the private V3.6 FL2VA 3x5 Terminal Merge combined GPU gate."""

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


TIMELINE_PROMPT = """[0-5s]
A continuous cinematic live-action tracking shot begins from the supplied First Frame. The woman in the orange jacket rides her skateboard forward along the waterfront promenade while the low camera tracks beside her. Natural rolling skateboard wheels, wind, and distant city traffic.

[5-10s]
She accelerates through smooth continuous S-turns without stopping. Her hair and jacket react to speed while the camera maintains the same forward direction with a steady pan and partial orbit. Preserve her face, orange jacket, white trousers, skateboard, waterfront, and natural contrast.

[10-15s]
Still moving forward, she approaches the blue waterfront sculpture, gradually eases her speed, turns toward the camera, and converges naturally to the supplied Last Frame pose and composition. Continuous city ambience and skateboard sound."""

CONDITIONS = {
    "a1_reference_video": ("reference_context_v1", False),
    "a2_masked_video": ("masked_video_prefix_v1", False),
    "b1_reference_av": ("reference_context_v1", True),
    "b2_masked_av": ("masked_av_prefix_22_v1", True),
}


def configure_prompt(
    source: Mapping[str, Any],
    *,
    transport: str,
    audio_continuity: bool,
    output_prefix: str,
    seed: int,
    diagnostic_nonce: int,
    steps: int = 20,
    audio_seam: str = "Auto",
) -> dict[str, Any]:
    prompt = copy.deepcopy(dict(source))
    prompt["290"] = {
        "class_type": "LoadImage",
        "_meta": {"title": "Last Frame"},
        "inputs": {"image": "exec-758fca62-818a-446e-a279-829cc126d899.png"},
    }
    prompt["292"] = {
        "class_type": "ImageScaleToTotalPixels",
        "_meta": {"title": "Scale Last Frame"},
        "inputs": {
            "upscale_method": "area",
            "megapixels": ["297", 0],
            "resolution_steps": 32,
            "image": ["290", 0],
        },
    }
    sampler = prompt["305"]
    sampler["class_type"] = "H3ContinuumMaskedPrefixR1Diagnostic"
    sampler["_meta"] = {"title": "V3.6 FL2VA Combined Gate Diagnostic"}
    sampler["inputs"].update(
        {
            "prompt_mode": "Timeline — [0-5s] sections",
            "chunks": 3,
            "chunk_seconds": 5.0,
            "width": 640,
            "height": 640,
            "continuity": "Balanced — 22 frames",
            "base_seed": int(seed),
            "audio_continuity": bool(audio_continuity),
            "diagnostics": "Detailed Report",
            "show_preview": False,
            "run_storage": "Off",
            "continuation_transport": str(transport),
            "synchronize_sampling": True,
            "diagnostic_nonce": int(diagnostic_nonce),
            "last_frame": ["292", 0],
        }
    )
    sampler["inputs"]["first_frame"] = ["119", 0]
    prompt["188"]["inputs"]["value"] = TIMELINE_PROMPT
    prompt["153"]["inputs"].update(
        {"scheduler": "simple", "steps": int(steps), "denoise": 1.0}
    )
    prompt["306"]["inputs"].update(
        {
            "exact_total_duration": True,
            "audio_seam": str(audio_seam),
            "video_seam": "Off",
            "buffer_backend": "Auto",
            "diagnostics": "Detailed Report",
        }
    )
    prompt["191"]["inputs"]["filename_prefix"] = str(output_prefix)
    return prompt


def _validate_diagnostic(
    diagnostic: Mapping[str, Any],
    *,
    transport: str,
    audio_continuity: bool,
) -> None:
    calls = list(diagnostic.get("sample_calls") or [])
    if len(calls) != 2:
        raise RuntimeError(f"expected 2 physical Sampling calls, got {len(calls)}")
    if int(diagnostic.get("logical_chunk_count", 0)) != 3:
        raise RuntimeError(f"logical chunk count mismatch: {diagnostic.get('logical_chunk_count')}")
    if int(diagnostic.get("physical_group_count", 0)) != 2:
        raise RuntimeError(f"physical group count mismatch: {diagnostic.get('physical_group_count')}")
    if int(diagnostic.get("physical_decode_group_count", 0)) != 2:
        raise RuntimeError("physical decode group count mismatch")
    groups = list(diagnostic.get("decode_groups") or [])
    if len(groups) != 2:
        raise RuntimeError(f"expected 2 decode groups, got {len(groups)}")
    terminal = groups[1]
    expected = {
        "logical_chunk_indices": [2, 3],
        "terminal_merged": True,
        "total_frames": 260,
        "trim_frames": 22,
        "expected_video_latent_t": 77,
        "expected_audio_latent_t": 433,
    }
    for key, value in expected.items():
        if terminal.get(key) != value:
            raise RuntimeError(f"terminal contract mismatch {key}: {terminal.get(key)!r}")
    first, second = calls
    if first.get("minimax_keyframe_indices") != [0]:
        raise RuntimeError(f"Group 1 First Frame contract mismatch: {first.get('minimax_keyframe_indices')}")
    if second.get("minimax_keyframe_indices") != [259]:
        raise RuntimeError(f"Terminal Last Frame contract mismatch: {second.get('minimax_keyframe_indices')}")
    if int(second.get("input_video", {}).get("shape", [0, 0, 0])[2]) != 77:
        raise RuntimeError("Terminal input Video T is not 77")
    masked = transport != "reference_context_v1"
    if masked:
        if second.get("minimax_ref_kinds"):
            raise RuntimeError(f"masked Terminal emitted refs: {second.get('minimax_ref_kinds')}")
        if bool(second.get("continuum_interop_emitted")):
            raise RuntimeError("masked Terminal emitted old Spectrum interop")
        required = {
            "source_tail_matches_target_prefix": True,
            "video_mask_prefix_zero": True,
            "video_mask_generated_one": True,
        }
        if transport == "masked_av_prefix_22_v1":
            required.update(
                {
                    "source_audio_tail_matches_target_prefix": True,
                    "audio_mask_prefix_zero": True,
                    "audio_mask_generated_one": True,
                }
            )
        else:
            required["audio_mask_all_one"] = True
        for key, value in required.items():
            if second.get(key) is not value:
                raise RuntimeError(f"masked evidence failed {key}: {second.get(key)!r}")
        pairs = list(diagnostic.get("final_prefix_pairs") or [])
        if len(pairs) != 1:
            raise RuntimeError(f"expected one final prefix pair, got {len(pairs)}")
        pair = pairs[0]
        if pair.get("bit_exact") is not True or float(pair.get("max_abs_diff", 1)) != 0:
            raise RuntimeError(f"final Video prefix is not exact: {pair}")
        if transport == "masked_av_prefix_22_v1":
            if pair.get("audio_bit_exact") is not True or float(
                pair.get("audio_max_abs_diff", 1)
            ) != 0:
                raise RuntimeError(f"final Audio prefix is not exact: {pair}")
    else:
        kinds = list(second.get("minimax_ref_kinds") or [])
        if "video" not in kinds and "video_audio" not in kinds:
            raise RuntimeError(f"Reference Terminal lacks Video context: {kinds}")
        if audio_continuity and "audio" not in kinds and "video_audio" not in kinds:
            raise RuntimeError(f"Reference AV Terminal lacks Audio context: {kinds}")
        if not bool(second.get("continuum_interop_emitted")):
            raise RuntimeError("Reference Terminal lacks Continuum interop")


def _run_prompt(
    *,
    prompt: dict[str, Any],
    run_root: Path,
    args,
    label: str,
    require_diagnostic: bool,
) -> dict[str, Any]:
    run_root.mkdir(parents=True, exist_ok=True)
    prompt_path = run_root / "prompt.json"
    prompt_path.write_text(json.dumps(prompt, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"START {label}", flush=True)
    with ResourceMonitor(args.backend_pid, args.monitor_interval) as monitor:
        prompt_id, history, elapsed = submit_and_wait(
            server=args.server,
            prompt=prompt,
            client_id=f"v36-fl2va-{uuid.uuid4().hex}",
            timeout_seconds=args.timeout_seconds,
            poll_seconds=args.poll_seconds,
        )
    history_path = run_root / "history.json"
    history_path.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
    evidence = _extract_evidence(history)
    result = {
        "label": label,
        "prompt_id": prompt_id,
        "api_elapsed_seconds": float(elapsed),
        "prompt": str(prompt_path),
        "history": str(history_path),
        "resources": monitor.as_dict(),
        **evidence,
    }
    if require_diagnostic and not result.get("diagnostic"):
        raise RuntimeError(f"{label} returned no V3.6 diagnostic evidence")
    (run_root / "summary.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"DONE {label} elapsed={elapsed:.3f}s", flush=True)
    return result


def _run_condition(
    *,
    source: Mapping[str, Any],
    args,
    label: str,
    transport: str,
    audio_continuity: bool,
    seed: int,
    nonce: int,
    cache_only_off: bool,
) -> list[dict[str, Any]]:
    output_prefix = f"video/V36_FL2VA_{label}_seed{seed}_Auto"
    prompt = configure_prompt(
        source,
        transport=transport,
        audio_continuity=audio_continuity,
        output_prefix=output_prefix,
        seed=seed,
        diagnostic_nonce=nonce,
        audio_seam="Auto",
    )
    result = _run_prompt(
        prompt=prompt,
        run_root=args.output_root / label,
        args=args,
        label=label,
        require_diagnostic=True,
    )
    cache = result.get("prompt_clip_cache")
    if not cache or int(cache.get("encode_calls", -1)) != 0:
        raise RuntimeError(f"measured run was not Prompt/CLIP cache HIT: {cache}")
    _validate_diagnostic(
        result["diagnostic"],
        transport=transport,
        audio_continuity=audio_continuity,
    )
    outputs = [result]
    if cache_only_off:
        raw = copy.deepcopy(prompt)
        raw["306"]["inputs"]["audio_seam"] = "Off"
        raw["191"]["inputs"]["filename_prefix"] = (
            f"video/V36_FL2VA_{label}_seed{seed}_SeamOff"
        )
        raw_result = _run_prompt(
            prompt=raw,
            run_root=args.output_root / f"{label}_seam_off_cache",
            args=args,
            label=f"{label}_seam_off_cache",
            require_diagnostic=False,
        )
        raw_result["cache_only_expected"] = True
        outputs.append(raw_result)
    return outputs


def run(args) -> dict[str, Any]:
    source = json.loads(args.prompt.read_text(encoding="utf-8"))
    args.output_root.mkdir(parents=True, exist_ok=True)
    nonce = int(time.time()) & 0x7FFFFFFF
    runs: list[dict[str, Any]] = []

    if not args.skip_warmup:
        warm = configure_prompt(
            source,
            transport="reference_context_v1",
            audio_continuity=False,
            output_prefix="video/V36_FL2VA_cache_warmup",
            seed=args.seeds[0],
            diagnostic_nonce=nonce,
            steps=1,
            audio_seam="Off",
        )
        runs.append(
            _run_prompt(
                prompt=warm,
                run_root=args.output_root / "cache_warmup",
                args=args,
                label="cache_warmup",
                require_diagnostic=True,
            )
        )

    schedule: list[tuple[int, str]]
    if args.phase == "gate-a":
        schedule = [(args.seeds[0], label) for label in CONDITIONS]
    elif args.phase == "joint-multiseed":
        schedule = [
            (args.seeds[0], "b1_reference_av"),
            (args.seeds[0], "b2_masked_av"),
            (args.seeds[1], "b2_masked_av"),
            (args.seeds[1], "b1_reference_av"),
            (args.seeds[2], "b1_reference_av"),
            (args.seeds[2], "b2_masked_av"),
        ]
    else:
        schedule = [
            (args.seeds[1], "b1_reference_av"),
            (args.seeds[1], "b2_masked_av"),
            (args.seeds[2], "b2_masked_av"),
        ]
    for index, (seed, condition) in enumerate(schedule, start=1):
        nonce += 1
        transport, audio_continuity = CONDITIONS[condition]
        label = f"{index:02d}_seed{seed}_{condition}"
        runs.extend(
            _run_condition(
                source=source,
                args=args,
                label=label,
                transport=transport,
                audio_continuity=audio_continuity,
                seed=seed,
                nonce=nonce,
                cache_only_off=(
                    condition.startswith("b")
                    and (
                        args.phase == "gate-a"
                        or (args.phase == "r2-short" and seed == args.seeds[1])
                    )
                ),
            )
        )

    measured = [run for run in runs if run.get("diagnostic") and run["label"] != "cache_warmup"]
    first_video_hashes = {
        run["diagnostic"]["physical_video_groups"][0]["sha256"] for run in measured
    }
    first_audio_hashes = {
        run["diagnostic"]["physical_audio_groups"][0]["sha256"] for run in measured
    }
    first_seeds_by_requested: dict[int, set[int]] = {}
    first_video_hashes_by_requested: dict[int, set[str]] = {}
    first_audio_hashes_by_requested: dict[int, set[str]] = {}
    for run in measured:
        requested = int(run["label"].split("_seed", 1)[1].split("_", 1)[0])
        actual = int(run["diagnostic"]["sample_calls"][0]["seed"])
        first_seeds_by_requested.setdefault(requested, set()).add(actual)
        first_video_hashes_by_requested.setdefault(requested, set()).add(
            run["diagnostic"]["physical_video_groups"][0]["sha256"]
        )
        first_audio_hashes_by_requested.setdefault(requested, set()).add(
            run["diagnostic"]["physical_audio_groups"][0]["sha256"]
        )
    if args.phase == "gate-a" and (len(first_video_hashes) != 1 or len(first_audio_hashes) != 1):
        raise RuntimeError("Gate A physical Group 1 hashes differ across conditions")
    if any(len(values) != 1 for values in first_seeds_by_requested.values()):
        raise RuntimeError(
            f"physical Group 1 seeds differ within a Base Seed: {first_seeds_by_requested}"
        )
    if any(len(values) != 1 for values in first_video_hashes_by_requested.values()):
        raise RuntimeError(
            "physical Group 1 Video hashes differ within a Base Seed: "
            f"{first_video_hashes_by_requested}"
        )
    if any(len(values) != 1 for values in first_audio_hashes_by_requested.values()):
        raise RuntimeError(
            "physical Group 1 Audio hashes differ within a Base Seed: "
            f"{first_audio_hashes_by_requested}"
        )

    result = {
        "format": "h3-continuum-v36-fl2va-combined-gate-v1",
        "phase": args.phase,
        "server": args.server,
        "seeds": [int(value) for value in args.seeds],
        "conditions": CONDITIONS,
        "group1_video_hash_count": len(first_video_hashes),
        "group1_audio_hash_count": len(first_audio_hashes),
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
    parser.add_argument(
        "--phase",
        choices=("gate-a", "joint-multiseed", "r2-short"),
        default="gate-a",
    )
    parser.add_argument(
        "--seeds",
        type=int,
        nargs=3,
        default=(238985343135606, 238985343135607, 238985343135608),
    )
    parser.add_argument("--backend-pid", type=int)
    parser.add_argument("--timeout-seconds", type=float, default=3600.0)
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument("--monitor-interval", type=float, default=1.0)
    parser.add_argument("--skip-warmup", action="store_true")
    return parser


def main() -> int:
    result = run(_parser().parse_args())
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
