"""Submit warm-up and measured Phase 3-2 workflows through the ComfyUI API."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request
import uuid
from typing import Any, Mapping

TOOLS_ROOT = Path(__file__).resolve().parent
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from p32_gpu_profile_probe import configure_profile, mutate_run


class ApiFailure(RuntimeError):
    pass


def _json_request(url: str, payload: Mapping[str, Any] | None = None) -> Any:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ApiFailure(f"ComfyUI API request failed for {url}: {exc}") from exc


def _history_complete(value: Mapping[str, Any], prompt_id: str) -> bool:
    entry = value.get(str(prompt_id))
    if not isinstance(entry, Mapping):
        return False
    status = entry.get("status")
    if not isinstance(status, Mapping):
        return bool(entry.get("outputs"))
    return bool(status.get("completed", False))


def _history_error(value: Mapping[str, Any], prompt_id: str) -> str | None:
    entry = value.get(str(prompt_id))
    if not isinstance(entry, Mapping):
        return None
    status = entry.get("status")
    messages = status.get("messages", []) if isinstance(status, Mapping) else []
    for item in messages:
        if isinstance(item, list) and item and item[0] in {
            "execution_error",
            "execution_interrupted",
        }:
            return json.dumps(item, ensure_ascii=False)
    return None


def submit_and_wait(
    *,
    server: str,
    prompt: Mapping[str, Any],
    client_id: str,
    timeout_seconds: float,
    poll_seconds: float,
) -> tuple[str, dict[str, Any], float]:
    started = time.perf_counter()
    response = _json_request(
        f"{server.rstrip('/')}/prompt",
        {"prompt": dict(prompt), "client_id": str(client_id)},
    )
    prompt_id = str(response.get("prompt_id", ""))
    if not prompt_id:
        raise ApiFailure(f"ComfyUI did not return a prompt_id: {response}")
    while time.perf_counter() - started <= float(timeout_seconds):
        history = _json_request(
            f"{server.rstrip('/')}/history/{prompt_id}"
        )
        error = _history_error(history, prompt_id)
        if error is not None:
            raise ApiFailure(f"ComfyUI prompt {prompt_id} failed: {error}")
        if _history_complete(history, prompt_id):
            return prompt_id, dict(history), time.perf_counter() - started
        time.sleep(float(poll_seconds))
    raise ApiFailure(f"ComfyUI prompt {prompt_id} timed out")


def run(args) -> dict[str, Any]:
    source = json.loads(args.prompt.read_text(encoding="utf-8"))
    configured = configure_profile(source, args.profile)
    args.output_root.mkdir(parents=True, exist_ok=True)
    client_id = f"p32-{uuid.uuid4().hex}"
    results = []
    total = 1 + int(args.runs)
    for index in range(total):
        warmup = index == 0
        label = "warmup" if warmup else f"run-{index}"
        seed = int(args.seed) + index
        prompt = mutate_run(
            configured,
            seed=seed,
            filename_prefix=f"p32/{args.case}_{args.profile}_{label}",
        )
        prompt_path = args.output_root / f"prompt_{label}.json"
        prompt_path.write_text(
            json.dumps(prompt, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(
            f"P32 API start case={args.case} profile={args.profile} "
            f"label={label} seed={seed}",
            flush=True,
        )
        prompt_id, history, elapsed = submit_and_wait(
            server=args.server,
            prompt=prompt,
            client_id=client_id,
            timeout_seconds=args.timeout_seconds,
            poll_seconds=args.poll_seconds,
        )
        history_path = args.output_root / f"history_{label}.json"
        history_path.write_text(
            json.dumps(history, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        results.append(
            {
                "label": label,
                "warmup": warmup,
                "seed": seed,
                "prompt_id": prompt_id,
                "api_elapsed_seconds": float(elapsed),
                "prompt": str(prompt_path),
                "history": str(history_path),
            }
        )
        print(
            f"P32 API complete prompt_id={prompt_id} elapsed={elapsed:.3f}s",
            flush=True,
        )
    summary = {
        "format": "h3-continuum-phase3-2-api-run-v1",
        "case": args.case,
        "profile": args.profile,
        "server": args.server,
        "warmup_excluded": True,
        "runs": results,
    }
    (args.output_root / "api_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return summary


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default="http://127.0.0.6:8188")
    parser.add_argument("--prompt", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument(
        "--profile",
        choices=("sage", "sage_sol", "sage_spectrum", "sage_sol_spectrum"),
        required=True,
    )
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--seed", type=int, default=32000)
    parser.add_argument("--timeout-seconds", type=float, default=3600.0)
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.runs < 1:
        raise SystemExit("--runs must be at least 1")
    print(json.dumps(run(args), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
