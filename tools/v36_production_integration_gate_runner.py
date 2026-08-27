"""Run the private V3.6 Production Integration Run Storage GPU gate."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import re
import sys
import time
import uuid
from typing import Any, Mapping


TOOLS_ROOT = Path(__file__).resolve().parent
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from p32_api_runner import submit_and_wait
from v36_r1_stress_gate_runner import _extract_evidence, _walk_strings


DEFAULT_SOURCE = Path(
    r"D:\Codex\_test_results\ComfyUI-H3-Continuum\v36-fl2va-combined-20260826"
    r"\gate-a\04_seed238985343135606_b2_masked_av\prompt.json"
)
DEFAULT_OUTPUT_ROOT = Path(
    r"D:\Codex\_test_results\ComfyUI-H3-Continuum\v36-production-integration"
)
RUN_STORAGE_ROOT = Path(
    r"D:\output\video\comfy_video\h3_continuum\runs"
)


def _run_storage_lines(history: Mapping[str, Any]) -> list[str]:
    lines: list[str] = []
    for text in _walk_strings(history):
        lines.extend(
            line for line in text.splitlines() if line.startswith("Run Storage:")
        )
    return list(dict.fromkeys(lines))


def _summary_counts(lines: list[str]) -> tuple[int, int, str]:
    if not lines:
        raise RuntimeError("Run Storage summary was not returned")
    line = lines[-1]
    match = re.search(
        r"revision ([0-9a-f]+); (\d+) reused, (\d+) generated", line
    )
    if not match:
        raise RuntimeError(f"unrecognized Run Storage summary: {line}")
    return int(match.group(2)), int(match.group(3)), match.group(1)


def configure_prompt(
    source: Mapping[str, Any],
    *,
    run_name: str,
    regenerate_from: str,
    reroll_nonce: int,
    diagnostic_nonce: int,
    output_prefix: str,
) -> dict[str, Any]:
    prompt = copy.deepcopy(dict(source))
    sampler = prompt["305"]
    sampler["class_type"] = "H3ContinuumMaskedPrefixR1Diagnostic"
    sampler["_meta"] = {"title": "V3.6 Production Integration Gate"}
    sampler["inputs"].update(
        {
            "chunks": 3,
            "chunk_seconds": 5.0,
            "width": 384,
            "height": 384,
            "continuity": "Balanced — 22 frames",
            "audio_continuity": True,
            "diagnostics": "Detailed Report",
            "reroll_from_chunk": str(regenerate_from),
            "reroll_nonce": int(reroll_nonce),
            "show_preview": False,
            "run_storage": "Save + Auto Resume",
            "run_name": str(run_name),
            "project_id": "",
            "continuation_transport": "masked_av_prefix_22_v1",
            "synchronize_sampling": True,
            "diagnostic_nonce": int(diagnostic_nonce),
        }
    )
    prompt["153"]["inputs"].update(
        {"scheduler": "simple", "steps": 1, "denoise": 1.0}
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
    prompt["191"]["inputs"]["filename_prefix"] = str(output_prefix)
    return prompt


def run_one(
    *,
    source: Mapping[str, Any],
    server: str,
    output_root: Path,
    run_name: str,
    label: str,
    regenerate_from: str,
    reroll_nonce: int,
    diagnostic_nonce: int,
    timeout_seconds: float,
) -> dict[str, Any]:
    run_root = output_root / label
    run_root.mkdir(parents=True, exist_ok=True)
    prompt = configure_prompt(
        source,
        run_name=run_name,
        regenerate_from=regenerate_from,
        reroll_nonce=reroll_nonce,
        diagnostic_nonce=diagnostic_nonce,
        output_prefix=f"video/V36_PIG2_{run_name}_{label}",
    )
    (run_root / "prompt.json").write_text(
        json.dumps(prompt, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    started = time.perf_counter()
    prompt_id, history, elapsed = submit_and_wait(
        server=server,
        prompt=prompt,
        client_id=f"v36-pig2-{uuid.uuid4().hex}",
        timeout_seconds=timeout_seconds,
        poll_seconds=1.0,
    )
    wall = time.perf_counter() - started
    (run_root / "history.json").write_text(
        json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    evidence = _extract_evidence(history)
    storage_lines = _run_storage_lines(history)
    reused, generated, revision = _summary_counts(storage_lines)
    result = {
        "label": label,
        "prompt_id": prompt_id,
        "api_elapsed_seconds": float(elapsed),
        "wall_seconds": float(wall),
        "regenerate_from": regenerate_from,
        "reroll_nonce": int(reroll_nonce),
        "run_storage_lines": storage_lines,
        "reused": reused,
        "generated": generated,
        "revision": revision,
        **evidence,
    }
    (run_root / "summary.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return result


def _manifest_records(run_name: str) -> list[dict[str, Any]]:
    run_root = RUN_STORAGE_ROOT / run_name
    records: list[dict[str, Any]] = []
    for path in sorted(run_root.glob("revisions/*/manifest.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        records.append({"path": str(path), "manifest": payload})
    return records


def validate(results: list[dict[str, Any]], manifests: list[dict[str, Any]]) -> None:
    expected_counts = [(0, 3, 2), (3, 0, 0), (1, 2, 1), (1, 2, 1)]
    for result, (reused, generated, sample_calls) in zip(
        results, expected_counts, strict=True
    ):
        if (result["reused"], result["generated"]) != (reused, generated):
            raise RuntimeError(
                f"{result['label']} storage counts mismatch: "
                f"{result['reused']}/{result['generated']}"
            )
        diagnostic = result.get("diagnostic") or {}
        calls = list(diagnostic.get("sample_calls") or [])
        if len(calls) != sample_calls:
            raise RuntimeError(
                f"{result['label']} expected {sample_calls} Sampling calls, got {len(calls)}"
            )
        if sample_calls == 1:
            shape = list(calls[0].get("input_video", {}).get("shape") or [])
            audio_shape = list(calls[0].get("input_audio", {}).get("shape") or [])
            if len(shape) < 3 or shape[2] != 77:
                raise RuntimeError(f"{result['label']} did not regenerate Terminal 77T")
            if not audio_shape or audio_shape[-1] != 433:
                raise RuntimeError(f"{result['label']} did not regenerate Terminal Audio 433T")

    if results[0]["revision"] != results[1]["revision"]:
        raise RuntimeError("Auto Resume did not select the saved masked revision")
    if not manifests:
        raise RuntimeError("Run Storage created no revision manifests")
    for record in manifests:
        manifest = record["manifest"]
        semantics = (
            (manifest.get("contract") or {}).get("global", {}).get(
                "execution_semantics", {}
            )
        )
        if semantics.get("continuation_transport") != "masked_av_prefix_22_v1":
            raise RuntimeError(
                f"manifest lacks masked transport identity: {record['path']}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default="http://127.0.0.1:8188")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--timeout-seconds", type=float, default=1800.0)
    parser.add_argument("--run-name", default="")
    args = parser.parse_args()

    stamp = time.strftime("%Y%m%d_%H%M%S")
    run_name = args.run_name or f"v36_pig2_masked_{stamp}"
    output_root = args.output_root / run_name
    output_root.mkdir(parents=True, exist_ok=True)
    source = json.loads(args.source.read_text(encoding="utf-8"))
    specifications = (
        ("01_initial_save", "Auto", 0, 9101),
        ("02_auto_resume", "Auto", 0, 9102),
        ("03_regenerate_chunk2", "Chunk 2", 1, 9103),
        ("04_regenerate_chunk3", "Chunk 3", 2, 9104),
    )
    results = []
    for label, regenerate_from, reroll_nonce, diagnostic_nonce in specifications:
        print(f"START {label}", flush=True)
        result = run_one(
            source=source,
            server=args.server,
            output_root=output_root,
            run_name=run_name,
            label=label,
            regenerate_from=regenerate_from,
            reroll_nonce=reroll_nonce,
            diagnostic_nonce=diagnostic_nonce,
            timeout_seconds=args.timeout_seconds,
        )
        results.append(result)
        print(
            f"DONE {label} elapsed={result['api_elapsed_seconds']:.3f}s "
            f"reused={result['reused']} generated={result['generated']}",
            flush=True,
        )
    manifests = _manifest_records(run_name)
    validate(results, manifests)
    summary = {
        "gate": "V3.6 PIG-2 Run Storage / Session identity",
        "status": "PASS",
        "run_name": run_name,
        "source_prompt": str(args.source),
        "results": results,
        "manifests": manifests,
    }
    (output_root / "gate_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps({"status": "PASS", "output_root": str(output_root)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
