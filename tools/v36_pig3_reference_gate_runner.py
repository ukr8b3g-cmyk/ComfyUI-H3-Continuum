"""Run V3.6 PIG-3 Reference Image + Audio with Masked AV continuation."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys
import time
import uuid


TOOLS_ROOT = Path(__file__).resolve().parent
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from p32_api_runner import submit_and_wait
from v36_r1_stress_gate_runner import _extract_evidence


DEFAULT_SOURCE = Path(
    r"D:\Codex\_test_results\ComfyUI-H3-Continuum\v36-fl2va-combined-20260826"
    r"\gate-a\04_seed238985343135606_b2_masked_av\prompt.json"
)
DEFAULT_OUTPUT = Path(
    r"D:\Codex\_test_results\ComfyUI-H3-Continuum\v36-production-integration"
    r"\pig3-reference-masked"
)
PROMPT = (
    "A continuous cinematic shot of <Picture 1> walking forward with clear body "
    "motion while the camera tracks smoothly. Preserve the person's identity, "
    "clothing, colors, and environment. Use <Audio 1> as the persistent voice and "
    "sound reference across both five-second chunks."
)


def configure(source: dict, *, seed: int, diagnostic_nonce: int) -> dict:
    prompt = copy.deepcopy(source)
    prompt["400"] = {
        "class_type": "LoadAudio",
        "_meta": {"title": "PIG-3 Reference Audio"},
        "inputs": {"audio": "V36_PIG3_reference_audio.mp3"},
    }
    sampler = prompt["305"]
    sampler["class_type"] = "H3ContinuumMaskedPrefixR1Diagnostic"
    sampler["_meta"] = {"title": "V3.6 PIG-3 Reference + Masked AV"}
    sampler["inputs"].update(
        {
            "prompt_mode": "Fixed",
            "chunks": 2,
            "chunk_seconds": 5.0,
            "width": 384,
            "height": 384,
            "continuity": "Balanced — 22 frames",
            "base_seed": int(seed),
            "audio_continuity": True,
            "diagnostics": "Detailed Report",
            "reroll_from_chunk": "Auto",
            "reroll_nonce": 0,
            "show_preview": False,
            "run_storage": "Off",
            "run_name": "",
            "project_id": "",
            "reference_size": "Match Output",
            "continuation_transport": "masked_av_prefix_22_v1",
            "synchronize_sampling": True,
            "diagnostic_nonce": int(diagnostic_nonce),
            "reference_image_1": ["119", 0],
            "reference_audio_1": ["400", 0],
            "reference_audio_vae": ["136", 0],
        }
    )
    sampler["inputs"].pop("last_frame", None)
    prompt["188"]["inputs"]["value"] = PROMPT
    prompt["153"]["inputs"].update(
        {"scheduler": "simple", "steps": 4, "denoise": 1.0}
    )
    prompt["306"]["inputs"].update(
        {
            "exact_total_duration": True,
            "audio_seam": "Auto",
            "video_seam": "Off",
            "buffer_backend": "Auto",
            "diagnostics": "Detailed Report",
        }
    )
    prompt["191"]["inputs"]["filename_prefix"] = (
        "video/V36_PIG3_Reference_Image_Audio_Masked_AV"
    )
    return prompt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default="http://127.0.0.1:8188")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seed", type=int, default=238985343135610)
    parser.add_argument("--timeout-seconds", type=float, default=1800.0)
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    source = json.loads(args.source.read_text(encoding="utf-8"))
    prompt = configure(source, seed=args.seed, diagnostic_nonce=9301)
    (args.output / "prompt.json").write_text(
        json.dumps(prompt, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    started = time.perf_counter()
    prompt_id, history, elapsed = submit_and_wait(
        server=args.server,
        prompt=prompt,
        client_id=f"v36-pig3-{uuid.uuid4().hex}",
        timeout_seconds=args.timeout_seconds,
        poll_seconds=1.0,
    )
    wall = time.perf_counter() - started
    (args.output / "history.json").write_text(
        json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    evidence = _extract_evidence(history)
    diagnostic = evidence.get("diagnostic") or {}
    calls = list(diagnostic.get("sample_calls") or [])
    if len(calls) != 2:
        raise RuntimeError(f"expected two physical groups, got {len(calls)}")
    for index, call in enumerate(calls, start=1):
        kinds = list(call.get("minimax_ref_kinds") or [])
        if kinds.count("image") != 1 or kinds.count("audio") != 1:
            raise RuntimeError(f"group {index} Reference kinds mismatch: {kinds}")
        if "video" in kinds or "video_audio" in kinds:
            raise RuntimeError(f"group {index} emitted old Continuation refs: {kinds}")
    continuation = calls[1]
    for key in (
        "source_tail_matches_target_prefix",
        "source_audio_tail_matches_target_prefix",
        "video_mask_prefix_zero",
        "video_mask_generated_one",
        "audio_mask_prefix_zero",
        "audio_mask_generated_one",
    ):
        if continuation.get(key) is not True:
            raise RuntimeError(f"continuation evidence failed {key}")
    pairs = list(diagnostic.get("final_prefix_pairs") or [])
    if len(pairs) != 1:
        raise RuntimeError(f"expected one finalized prefix pair, got {len(pairs)}")
    pair = pairs[0]
    if pair.get("bit_exact") is not True or pair.get("audio_bit_exact") is not True:
        raise RuntimeError(f"final protected prefixes are not bit-exact: {pair}")
    result = {
        "gate": "V3.6 PIG-3 Reference + Masked AV",
        "status": "PASS",
        "prompt_id": prompt_id,
        "api_elapsed_seconds": float(elapsed),
        "wall_seconds": float(wall),
        "seed": int(args.seed),
        "prompt": PROMPT,
        **evidence,
    }
    (args.output / "gate_summary.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps({"status": "PASS", "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
