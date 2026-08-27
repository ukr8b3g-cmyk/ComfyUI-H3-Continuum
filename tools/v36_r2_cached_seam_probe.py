"""Reassemble an accepted R2 prompt with Audio Seam Auto via ComfyUI cache."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import uuid


TOOLS_ROOT = Path(__file__).resolve().parent
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from p32_api_runner import submit_and_wait


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default="http://127.0.0.1:8188")
    parser.add_argument("--prompt", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--filename-prefix", required=True)
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    args = parser.parse_args()

    prompt = json.loads(args.prompt.read_text(encoding="utf-8"))
    prompt["306"]["inputs"]["audio_seam"] = "Auto"
    prompt["191"]["inputs"]["filename_prefix"] = str(args.filename_prefix)
    args.output_root.mkdir(parents=True, exist_ok=True)
    prompt_path = args.output_root / "prompt.json"
    prompt_path.write_text(
        json.dumps(prompt, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    prompt_id, history, elapsed = submit_and_wait(
        server=args.server,
        prompt=prompt,
        client_id=f"v36-r2-seam-{uuid.uuid4().hex}",
        timeout_seconds=args.timeout_seconds,
        poll_seconds=1.0,
    )
    history_path = args.output_root / "history.json"
    history_path.write_text(
        json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    result = {
        "prompt_id": prompt_id,
        "api_elapsed_seconds": float(elapsed),
        "prompt": str(prompt_path),
        "history": str(history_path),
    }
    (args.output_root / "summary.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
