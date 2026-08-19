"""Lightweight installation verifier for a local ComfyUI environment."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


def load_package(root: Path):
    name = "h3_continuum_join_verify"
    spec = importlib.util.spec_from_file_location(
        name,
        root / "__init__.py",
        submodule_search_locations=[str(root)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot create package import specification")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comfy-root", type=Path, required=True)
    args = parser.parse_args()
    comfy_root = args.comfy_root.resolve()
    package_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(comfy_root))

    module = load_package(package_root)
    from h3_continuum_join_verify.compatibility import (
        check_comfy_h3_runtime,
        run_native_layout_self_test,
    )
    from h3_continuum_join_verify.constants import PROMPT_MODE_FIXED
    from h3_continuum_join_verify.v2.prompts import make_prompt_plan
    from h3_continuum_join_verify.version import PACKAGE_VERSION

    issues = check_comfy_h3_runtime()
    if issues:
        print("H3 Continuum Join runtime verification FAILED:")
        for issue in issues:
            print(f"  - {issue}")
        return 1
    try:
        layout_report = run_native_layout_self_test()
    except Exception as exc:
        print(f"Native PackedLayout self-test FAILED: {exc}")
        return 1

    try:
        prompt_plan = make_prompt_plan(
            mode=PROMPT_MODE_FIXED,
            script="Continuum runtime verification prompt",
            chunks=3,
            chunk_seconds=5.0,
        )
        if len(prompt_plan["prompts"]) != 3 or len(set(prompt_plan["hashes"])) != 1:
            raise RuntimeError("unexpected Fixed prompt-plan result")
    except Exception as exc:
        print(f"V2 prompt/session core self-test FAILED: {exc}")
        return 1

    expected = {
        "H3ContinuumJoin",
        "H3ContinuumFinish",
        "H3ContinuumAssemble",
        "H3ContinuumSaveState",
        "H3ContinuumLoadState",
        "H3ContinuumSamplerV2",
        "H3ContinuumPromptPlanPreview",
        "H3ContinuumSaveSession",
        "H3ContinuumLoadSession",
        "H3ContinuumSessionInfo",
        "H3ContinuumSampler",
        "H3ContinuumClipOverrides",
        "H3ContinuumAdvanced",
        "H3ContinuumResult",
        "H3ContinuumSamplerProduction",
        "H3ContinuumSamplerTimelineVideo",
        "H3ContinuumSamplerV3",
        "H3ContinuumAdvancedV3",
        "H3ContinuumAssembleV3",
        "H3ContinuumAssembleSeamExperimental",
        "H3ContinuumSamplerV34",
        "H3ContinuumAssembleSeamV34",
    }
    actual = set(module.NODE_CLASS_MAPPINGS)
    if actual != expected:
        print(f"Node registration mismatch: expected {sorted(expected)}, got {sorted(actual)}")
        return 1
    print(f"H3 Continuum Join {PACKAGE_VERSION} runtime verification passed.")
    print(layout_report)
    print(f"V{PACKAGE_VERSION} Fixed 3x5s prompt-plan self-test passed.")
    print("Registered nodes:")
    for key in sorted(actual):
        print(f"  - {module.NODE_DISPLAY_NAME_MAPPINGS[key]}")
    print("GPU checkpoint generation was not run by this lightweight verifier.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
