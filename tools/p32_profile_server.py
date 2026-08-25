"""Launch the installed ComfyUI API with Phase 3-2 diagnostics enabled.

The wrapper imports the normal ComfyUI ``main.py``, installs an in-process
measurement hook, and then starts the unmodified API server.  No custom node
or Production file is installed.  Every completed prompt appends one JSON
record to ``--profile-output``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import threading
import time
from typing import Any


def _bootstrap_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--comfy-root", type=Path, required=True)
    parser.add_argument("--profile-output", type=Path, required=True)
    parser.add_argument(
        "--profile-mode", choices=("global", "interval"), default="global"
    )
    parser.add_argument("--profile-monitor-interval", type=float, default=0.05)
    return parser


BOOTSTRAP, COMFY_ARGS = _bootstrap_parser().parse_known_args()
COMFY_ROOT = BOOTSTRAP.comfy_root.resolve()
PROFILE_OUTPUT = BOOTSTRAP.profile_output.resolve()
PROFILE_MODE = str(BOOTSTRAP.profile_mode)
MONITOR_INTERVAL = float(BOOTSTRAP.profile_monitor_interval)
sys.argv = [str(COMFY_ROOT / "main.py"), *COMFY_ARGS]
sys.path.insert(0, str(COMFY_ROOT))
os.chdir(COMFY_ROOT)

import torch  # noqa: E402

import main as comfy_main  # noqa: E402
import execution  # noqa: E402

from p32_gpu_profile_probe import (  # noqa: E402
    ResourceMonitor,
    _memory_snapshot,
    _phase_for_class,
    _phase_totals,
)


_WRITE_LOCK = threading.Lock()
_CONTEXT_LOCK = threading.Lock()
_CONTEXTS: dict[str, dict[str, Any]] = {}


def _class_type(prompt: dict[str, Any], node_id: str, obj: Any) -> str:
    configured = prompt.get(str(node_id), {}).get("class_type")
    if configured:
        return str(configured)
    if isinstance(obj, type):
        return str(obj.__name__)
    return str(type(obj).__name__)


def _write_record(record: dict[str, Any]) -> None:
    PROFILE_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
    with _WRITE_LOCK:
        with PROFILE_OUTPUT.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()


def _install_profiler() -> None:
    original_get_output_data = execution.get_output_data
    original_execute_async = execution.PromptExecutor.execute_async

    async def profiled_get_output_data(
        prompt_id,
        unique_id,
        obj,
        input_data_all,
        execution_block_cb=None,
        pre_execute_cb=None,
        v3_data=None,
    ):
        with _CONTEXT_LOCK:
            context = _CONTEXTS.get(str(prompt_id))
        if context is None:
            return await original_get_output_data(
                prompt_id,
                unique_id,
                obj,
                input_data_all,
                execution_block_cb=execution_block_cb,
                pre_execute_cb=pre_execute_cb,
                v3_data=v3_data,
            )

        node_id = str(unique_id)
        class_type = _class_type(context["prompt"], node_id, obj)
        if torch.cuda.is_available():
            torch.cuda.synchronize()
            if PROFILE_MODE == "interval":
                torch.cuda.reset_peak_memory_stats()
        memory_start = _memory_snapshot()
        cuda_start_allocated = (
            int(torch.cuda.memory_allocated()) if torch.cuda.is_available() else None
        )
        cuda_start_reserved = (
            int(torch.cuda.memory_reserved()) if torch.cuda.is_available() else None
        )
        monitor = ResourceMonitor(MONITOR_INTERVAL)
        monitor.start()
        started = time.perf_counter()
        error = None
        try:
            return await original_get_output_data(
                prompt_id,
                unique_id,
                obj,
                input_data_all,
                execution_block_cb=execution_block_cb,
                pre_execute_cb=pre_execute_cb,
                v3_data=v3_data,
            )
        except BaseException as exc:
            error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            try:
                if torch.cuda.is_available():
                    torch.cuda.synchronize()
            finally:
                elapsed = time.perf_counter() - started
                resources = monitor.stop()
                record = {
                    "node_id": node_id,
                    "class_type": class_type,
                    "phase": _phase_for_class(class_type),
                    "elapsed_seconds": float(elapsed),
                    "memory_start": memory_start,
                    "memory_end": _memory_snapshot(),
                    "resources": resources,
                    "cuda_start_allocated_bytes": cuda_start_allocated,
                    "cuda_start_reserved_bytes": cuda_start_reserved,
                    "cuda_end_allocated_bytes": (
                        int(torch.cuda.memory_allocated())
                        if torch.cuda.is_available()
                        else None
                    ),
                    "cuda_end_reserved_bytes": (
                        int(torch.cuda.memory_reserved())
                        if torch.cuda.is_available()
                        else None
                    ),
                    "cuda_interval_peak_allocated_bytes": (
                        int(torch.cuda.max_memory_allocated())
                        if torch.cuda.is_available() and PROFILE_MODE == "interval"
                        else None
                    ),
                    "cuda_synchronized": bool(torch.cuda.is_available()),
                    "error": error,
                }
                with _CONTEXT_LOCK:
                    active = _CONTEXTS.get(str(prompt_id))
                    if active is not None:
                        active["nodes"].append(record)

    async def profiled_execute_async(
        self,
        prompt,
        prompt_id,
        extra_data={},
        execute_outputs=[],
    ):
        prompt_key = str(prompt_id)
        context: dict[str, Any] = {
            "prompt": dict(prompt),
            "nodes": [],
            "started_at_unix": time.time(),
        }
        with _CONTEXT_LOCK:
            _CONTEXTS[prompt_key] = context
        if torch.cuda.is_available():
            torch.cuda.synchronize()
            if PROFILE_MODE == "global":
                torch.cuda.reset_peak_memory_stats()
        monitor = ResourceMonitor(MONITOR_INTERVAL)
        monitor.start()
        started = time.perf_counter()
        error = None
        try:
            return await original_execute_async(
                self,
                prompt,
                prompt_id,
                extra_data=extra_data,
                execute_outputs=execute_outputs,
            )
        except BaseException as exc:
            error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            try:
                if torch.cuda.is_available():
                    torch.cuda.synchronize()
            finally:
                elapsed = time.perf_counter() - started
                resources = monitor.stop()
                with _CONTEXT_LOCK:
                    completed = _CONTEXTS.pop(prompt_key, context)
                nodes = list(completed["nodes"])
                class_types = [str(item["class_type"]) for item in nodes]
                spectrum_nodes = [
                    node
                    for node in prompt.values()
                    if str(node.get("class_type")) == "SpectrumApplyMiniMaxH3"
                ]
                spectrum_enabled = any(
                    bool(node.get("inputs", {}).get("enabled", False))
                    for node in spectrum_nodes
                )
                configured_class_types = {
                    str(node.get("class_type")) for node in prompt.values()
                }
                _write_record(
                    {
                        "format": "h3-continuum-phase3-2-api-profile-v1",
                        "prompt_id": prompt_key,
                        "mode": PROFILE_MODE,
                        "started_at_unix": completed["started_at_unix"],
                        "elapsed_seconds": float(elapsed),
                        "phase_totals_seconds": _phase_totals(nodes),
                        "nodes": nodes,
                        "resources": resources,
                        "cuda_global_peak_allocated_bytes": (
                            int(torch.cuda.max_memory_allocated())
                            if torch.cuda.is_available() and PROFILE_MODE == "global"
                            else None
                        ),
                        "cuda_peak_scope": (
                            "whole_workflow"
                            if PROFILE_MODE == "global"
                            else "per_node_only"
                        ),
                        "cuda_synchronize_before_after_nodes": bool(
                            torch.cuda.is_available()
                        ),
                        "route_observed": {
                            "sage_node_configured": (
                                "MiniMaxH3MemoryEfficientSageAttentionPatch"
                                in configured_class_types
                            ),
                            "sol_node_configured": "SolAttnPatch"
                            in configured_class_types,
                            "spectrum_node_configured": (
                                "SpectrumApplyMiniMaxH3" in configured_class_types
                            ),
                            "sage_node_executed": (
                                "MiniMaxH3MemoryEfficientSageAttentionPatch"
                                in class_types
                            ),
                            "sol_node_executed": "SolAttnPatch" in class_types,
                            "spectrum_node_executed": (
                                "SpectrumApplyMiniMaxH3" in class_types
                            ),
                            "spectrum_enabled": bool(spectrum_enabled),
                        },
                        "success": bool(getattr(self, "success", False)),
                        "error": error,
                    }
                )

    execution.get_output_data = profiled_get_output_data
    execution.PromptExecutor.execute_async = profiled_execute_async


def main() -> int:
    _install_profiler()
    loop, _server, start_all = comfy_main.start_comfyui()
    try:
        loop.run_until_complete(start_all())
    except KeyboardInterrupt:
        pass
    finally:
        try:
            comfy_main.asset_seeder.shutdown()
        except Exception:
            pass
        comfy_main.cleanup_temp()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
