"""Phase 3-2 diagnostic-only ComfyUI workflow profiler.

This tool runs an API-format prompt through ComfyUI's installed PromptExecutor
in a dedicated process.  It does not register a Continuum node or modify the
normal ComfyUI server.  CUDA phases are synchronized immediately before and
after each node so GPU work is attributed to the node that launched it.

Two measurement modes are intentionally separate:

``global``
    Resets CUDA peak statistics once per workflow execution.  The result is
    the true process allocator peak for that run.  Per-node wall time and
    process-memory peaks are still collected, but per-node CUDA peaks are not.

``interval``
    Resets CUDA peak statistics before every node.  This provides isolated
    node allocator peaks, but the workflow-level allocator peak is therefore
    not meaningful and is reported as unavailable.

The first execution is a warm-up.  Subsequent executions change only the
Continuum base seed and output filename so model/CLIP objects stay warm while
the V3.5 Prompt/CLIP cache remains eligible for a HIT.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import os
from pathlib import Path
import statistics
import sys
import threading
import time
from typing import Any, Mapping

import psutil
import torch


PROFILE_NAMES = (
    "sage",
    "sage_sol",
    "sage_spectrum",
    "sage_sol_spectrum",
)
MEASUREMENT_MODES = ("global", "interval")

_NVML_LOCK = threading.Lock()
_NVML_HANDLE: Any = None
_NVML_UNAVAILABLE = False

_SAMPLER_CLASSES = {
    "H3ContinuumSamplerV35",
    "H3ContinuumSamplerV34",
}
_VIDEO_DECODE_CLASSES = {"VAEDecode", "VAEDecodeTiled"}
_AUDIO_DECODE_CLASSES = {"VAEDecodeAudio"}
_ASSEMBLY_CLASSES = {"H3ContinuumAssembleSeamV35"}
_VIDEO_CREATE_CLASSES = {"CreateVideo"}
_SAVE_CLASSES = {"SaveVideo", "VHS_VideoCombine"}


class ProbeFailure(RuntimeError):
    pass


def _phase_for_class(class_type: str) -> str:
    if class_type in _SAMPLER_CLASSES:
        return "sampling"
    if class_type in _VIDEO_DECODE_CLASSES:
        return "video_vae_decode"
    if class_type in _AUDIO_DECODE_CLASSES:
        return "audio_vae_decode"
    if class_type in _ASSEMBLY_CLASSES:
        return "assemble_seam"
    if class_type in _VIDEO_CREATE_CLASSES:
        return "video_create"
    if class_type in _SAVE_CLASSES:
        return "mp4_encode_save"
    return "other"


def _memory_snapshot() -> dict[str, int | None]:
    result: dict[str, int | None] = {
        "rss_bytes": None,
        "private_bytes": None,
        "uss_bytes": None,
    }
    try:
        info = psutil.Process().memory_full_info()
        result["rss_bytes"] = int(getattr(info, "rss", 0)) or None
        private = getattr(info, "private", None)
        uss = getattr(info, "uss", None)
        result["private_bytes"] = None if private is None else int(private)
        result["uss_bytes"] = None if uss is None else int(uss)
    except Exception:
        pass
    return result


def _nvml_free_bytes() -> int | None:
    """Read device-global free VRAM without calling the CUDA runtime.

    Calling ``torch.cuda.mem_get_info`` from the polling thread measurably
    serialized H3 Sampling on Windows.  NVML observes the device externally
    and avoids that profiler-induced slowdown.
    """

    global _NVML_HANDLE, _NVML_UNAVAILABLE
    if _NVML_UNAVAILABLE:
        return None
    try:
        import pynvml

        with _NVML_LOCK:
            if _NVML_HANDLE is None:
                pynvml.nvmlInit()
                index = int(torch.cuda.current_device()) if torch.cuda.is_available() else 0
                _NVML_HANDLE = pynvml.nvmlDeviceGetHandleByIndex(index)
            return int(pynvml.nvmlDeviceGetMemoryInfo(_NVML_HANDLE).free)
    except Exception:
        _NVML_UNAVAILABLE = True
        return None


class ResourceMonitor:
    """Poll process and device counters without changing allocator state."""

    def __init__(self, interval: float = 0.05):
        self.interval = float(interval)
        self.process = psutil.Process()
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.samples = 0
        self.peak_rss = 0
        self.peak_private: int | None = None
        self.peak_uss: int | None = None
        self.minimum_system_available = 1 << 63
        self.minimum_cuda_free = 1 << 63

    def _sample(self) -> None:
        try:
            # Full process memory inspection is too expensive to poll during
            # H3 Sampling on Windows. RSS/private use the cheap counters;
            # USS is sampled only at monitor start and stop.
            memory = self.process.memory_info()
            self.peak_rss = max(self.peak_rss, int(memory.rss))
            private = getattr(memory, "private", None)
            if private is not None:
                self.peak_private = max(self.peak_private or 0, int(private))
            self.minimum_system_available = min(
                self.minimum_system_available,
                int(psutil.virtual_memory().available),
            )
            free = _nvml_free_bytes()
            if free is not None:
                self.minimum_cuda_free = min(self.minimum_cuda_free, int(free))
            self.samples += 1
        except Exception:
            pass

    def _run(self) -> None:
        while not self.stop_event.wait(self.interval):
            self._sample()

    def start(self) -> None:
        full = _memory_snapshot()
        uss = full.get("uss_bytes")
        if uss is not None:
            self.peak_uss = int(uss)
        self._sample()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self) -> dict[str, int | None]:
        self._sample()
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=5.0)
        full = _memory_snapshot()
        uss = full.get("uss_bytes")
        if uss is not None:
            self.peak_uss = max(self.peak_uss or 0, int(uss))
        return {
            "samples": int(self.samples),
            "peak_rss_bytes": int(self.peak_rss),
            "peak_private_bytes": self.peak_private,
            "peak_uss_bytes": self.peak_uss,
            "uss_peak_scope": "monitor_start_end_only",
            "minimum_system_available_bytes": (
                None
                if self.minimum_system_available == 1 << 63
                else int(self.minimum_system_available)
            ),
            "minimum_cuda_free_bytes": (
                None
                if self.minimum_cuda_free == 1 << 63
                else int(self.minimum_cuda_free)
            ),
        }


class _ExecutionServer:
    def __init__(self):
        self.client_id = None
        self.last_node_id = None
        self.messages: list[tuple[str, dict[str, Any], Any]] = []

    def send_sync(self, event, data, client_id):
        self.messages.append((str(event), dict(data), client_id))


def _find_nodes(prompt: Mapping[str, Any], class_type: str) -> list[str]:
    return [
        str(node_id)
        for node_id, node in prompt.items()
        if str(node.get("class_type")) == class_type
    ]


def _one_node(prompt: Mapping[str, Any], class_type: str) -> str:
    values = _find_nodes(prompt, class_type)
    if len(values) != 1:
        raise ProbeFailure(
            f"expected exactly one {class_type} node, found {len(values)}"
        )
    return values[0]


def _next_node_id(prompt: Mapping[str, Any]) -> str:
    numeric = [int(value) for value in prompt if str(value).isdigit()]
    return str((max(numeric) if numeric else 0) + 1)


def _sol_inputs(model_link: list[Any]) -> dict[str, Any]:
    return {
        "model": list(model_link),
        "tau": 1.3,
        "start_percent": 0.2,
        "end_percent": 0.9,
        "min_tokens": 4096,
        "int8_qk": True,
        "sink_conditioning": "exact_kv_and_rows",
        "morton": False,
        "morton_curve": "2d_frame",
        "int8_pv": True,
        "verbose": True,
        "use_tma": False,
        "dense_blocks": "",
    }


def configure_profile(prompt: Mapping[str, Any], profile: str) -> dict[str, Any]:
    """Return a copied prompt with one explicit attention/Spectrum route."""

    if profile not in PROFILE_NAMES:
        raise ValueError(f"unknown profile: {profile!r}")
    result = copy.deepcopy(dict(prompt))
    sage = _one_node(result, "MiniMaxH3MemoryEfficientSageAttentionPatch")
    spectrum = _one_node(result, "SpectrumApplyMiniMaxH3")
    if not isinstance(result[sage].get("inputs", {}).get("model"), list):
        raise ProbeFailure("Sage node has no MODEL link")
    spectrum_inputs = result[spectrum].setdefault("inputs", {})
    upstream = spectrum_inputs.get("model")
    if not isinstance(upstream, list) or len(upstream) != 2:
        raise ProbeFailure("Spectrum node has no MODEL link")

    use_sol = profile in {"sage_sol", "sage_sol_spectrum"}
    use_spectrum = profile in {"sage_spectrum", "sage_sol_spectrum"}
    if use_sol:
        sol_id = _next_node_id(result)
        result[sol_id] = {
            "class_type": "SolAttnPatch",
            "inputs": _sol_inputs(list(upstream)),
            "_meta": {"title": "Patch Sol-Attn"},
        }
        spectrum_inputs["model"] = [sol_id, 0]
    spectrum_inputs["enabled"] = bool(use_spectrum)
    return result


def mutate_run(
    prompt: Mapping[str, Any],
    *,
    seed: int,
    filename_prefix: str,
) -> dict[str, Any]:
    result = copy.deepcopy(dict(prompt))
    sampler_nodes = _find_nodes(result, "H3ContinuumSamplerV35")
    if len(sampler_nodes) != 1:
        raise ProbeFailure(
            f"expected one H3ContinuumSamplerV35, found {len(sampler_nodes)}"
        )
    result[sampler_nodes[0]].setdefault("inputs", {})["base_seed"] = int(seed)
    save_nodes = _find_nodes(result, "SaveVideo")
    if not save_nodes:
        save_nodes = _find_nodes(result, "VHS_VideoCombine")
    for node_id in save_nodes:
        inputs = result[node_id].setdefault("inputs", {})
        if "filename_prefix" in inputs:
            inputs["filename_prefix"] = str(filename_prefix)
    return result


def _route(prompt: Mapping[str, Any], profile: str) -> list[str]:
    route = ["MiniMaxH3MemoryEfficientSageAttentionPatch"]
    if profile in {"sage_sol", "sage_sol_spectrum"}:
        route.append("SolAttnPatch")
    if profile in {"sage_spectrum", "sage_sol_spectrum"}:
        route.append("SpectrumApplyMiniMaxH3")
    return route


def _execute_outputs(prompt: Mapping[str, Any]) -> list[str]:
    values = _find_nodes(prompt, "SaveVideo") + _find_nodes(
        prompt, "VHS_VideoCombine"
    )
    if not values:
        raise ProbeFailure("prompt has no SaveVideo/VHS output node")
    return values


def _median_or_none(values: list[float | int | None]) -> float | None:
    clean = [float(value) for value in values if value is not None]
    return None if not clean else float(statistics.median(clean))


def summarize_runs(runs: list[Mapping[str, Any]]) -> dict[str, Any]:
    phases = sorted(
        {
            phase
            for run in runs
            for phase in run.get("phase_totals_seconds", {}).keys()
        }
    )
    return {
        "run_count": len(runs),
        "median_elapsed_seconds": _median_or_none(
            [run.get("elapsed_seconds") for run in runs]
        ),
        "median_phase_seconds": {
            phase: _median_or_none(
                [run.get("phase_totals_seconds", {}).get(phase) for run in runs]
            )
            for phase in phases
        },
        "median_peak_rss_bytes": _median_or_none(
            [run.get("resources", {}).get("peak_rss_bytes") for run in runs]
        ),
        "median_peak_private_bytes": _median_or_none(
            [run.get("resources", {}).get("peak_private_bytes") for run in runs]
        ),
        "median_peak_uss_bytes": _median_or_none(
            [run.get("resources", {}).get("peak_uss_bytes") for run in runs]
        ),
        "median_cuda_global_peak_allocated_bytes": _median_or_none(
            [run.get("cuda_global_peak_allocated_bytes") for run in runs]
        ),
        "median_minimum_cuda_free_bytes": _median_or_none(
            [run.get("resources", {}).get("minimum_cuda_free_bytes") for run in runs]
        ),
    }


def _install_comfy_paths(comfy_root: Path) -> None:
    values = (
        comfy_root,
        comfy_root / "custom_nodes" / "comfyui-videohelpersuite",
    )
    for path in values:
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)


def _initialize_comfy(comfy_root: Path):
    _install_comfy_paths(comfy_root)
    os.chdir(comfy_root)
    from comfy.cli_args import args as comfy_args

    # Load only the custom-node packages present in the accepted workflows.
    # In particular, do not start ComfyUI-Manager's network/cache workers in a
    # short-lived diagnostic process.
    comfy_args.disable_all_custom_nodes = True
    comfy_args.whitelist_custom_nodes = [
        "ComfyUI-H3-Continuum",
        "ComfyUI-Spectrum-MiniMax-H3",
        "ComfyUI-SolAttn_triton",
        "comfyui-easy-use",
        "comfyui-kjnodes",
        "rgthree-comfy",
    ]
    import folder_paths
    import nodes
    import server

    loop = asyncio.new_event_loop()
    prompt_server = server.PromptServer(loop)
    loop.run_until_complete(nodes.init_extra_nodes())
    return folder_paths, nodes, prompt_server, loop


class NodeProfiler:
    def __init__(
        self,
        execution_module,
        prompt: Mapping[str, Any],
        mode: str,
        monitor_interval: float,
    ):
        self.execution = execution_module
        self.prompt = prompt
        self.mode = mode
        self.monitor_interval = float(monitor_interval)
        self.records: list[dict[str, Any]] = []
        self._original = None

    def install(self) -> None:
        if self._original is not None:
            raise RuntimeError("profiler is already installed")
        self._original = self.execution.get_output_data
        original = self._original

        async def profiled_get_output_data(
            prompt_id,
            unique_id,
            obj,
            input_data_all,
            execution_block_cb=None,
            pre_execute_cb=None,
            v3_data=None,
        ):
            node_id = str(unique_id)
            class_type = str(
                self.prompt.get(node_id, {}).get(
                    "class_type", type(obj).__name__
                )
            )
            if torch.cuda.is_available():
                torch.cuda.synchronize()
                if self.mode == "interval":
                    torch.cuda.reset_peak_memory_stats()
            memory_start = _memory_snapshot()
            cuda_start_allocated = (
                int(torch.cuda.memory_allocated()) if torch.cuda.is_available() else None
            )
            cuda_start_reserved = (
                int(torch.cuda.memory_reserved()) if torch.cuda.is_available() else None
            )
            monitor = ResourceMonitor(self.monitor_interval)
            monitor.start()
            started = time.perf_counter()
            try:
                result = await original(
                    prompt_id,
                    unique_id,
                    obj,
                    input_data_all,
                    execution_block_cb=execution_block_cb,
                    pre_execute_cb=pre_execute_cb,
                    v3_data=v3_data,
                )
                if torch.cuda.is_available():
                    torch.cuda.synchronize()
                return result
            finally:
                elapsed = time.perf_counter() - started
                resources = monitor.stop()
                memory_end = _memory_snapshot()
                self.records.append(
                    {
                        "node_id": node_id,
                        "class_type": class_type,
                        "phase": _phase_for_class(class_type),
                        "elapsed_seconds": float(elapsed),
                        "memory_start": memory_start,
                        "memory_end": memory_end,
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
                            if torch.cuda.is_available() and self.mode == "interval"
                            else None
                        ),
                        "cuda_synchronized": bool(torch.cuda.is_available()),
                    }
                )

        self.execution.get_output_data = profiled_get_output_data

    def uninstall(self) -> None:
        if self._original is not None:
            self.execution.get_output_data = self._original
            self._original = None


def _phase_totals(records: list[Mapping[str, Any]]) -> dict[str, float]:
    result: dict[str, float] = {}
    for item in records:
        phase = str(item.get("phase", "other"))
        result[phase] = result.get(phase, 0.0) + float(
            item.get("elapsed_seconds", 0.0)
        )
    return result


def _cached_nodes(executor) -> list[str]:
    for event, data in executor.status_messages:
        if event == "execution_cached":
            return sorted(str(value) for value in data.get("nodes", []))
    return []


def _run_once(
    *,
    executor,
    execution_module,
    prompt: Mapping[str, Any],
    prompt_id: str,
    mode: str,
    monitor_interval: float,
    measured: bool,
) -> dict[str, Any]:
    if not torch.cuda.is_available():
        raise ProbeFailure("Phase 3-2 GPU profiling requires CUDA")
    profiler = NodeProfiler(
        execution_module,
        prompt,
        mode=mode,
        monitor_interval=monitor_interval,
    )
    if measured:
        profiler.install()
    torch.cuda.synchronize()
    if mode == "global":
        torch.cuda.reset_peak_memory_stats()
    run_monitor = ResourceMonitor(monitor_interval)
    run_monitor.start()
    started = time.perf_counter()
    try:
        executor.execute(
            dict(prompt),
            prompt_id,
            extra_data={},
            execute_outputs=_execute_outputs(prompt),
        )
        torch.cuda.synchronize()
    finally:
        elapsed = time.perf_counter() - started
        resources = run_monitor.stop()
        profiler.uninstall()
    if not executor.success:
        errors = [
            data
            for event, data in executor.status_messages
            if event == "execution_error"
        ]
        raise ProbeFailure(f"PromptExecutor failed: {errors[-1:]}")
    records = list(profiler.records)
    return {
        "prompt_id": prompt_id,
        "measured": bool(measured),
        "elapsed_seconds": float(elapsed),
        "phase_totals_seconds": _phase_totals(records),
        "nodes": records,
        "cached_nodes": _cached_nodes(executor),
        "resources": resources,
        "cuda_global_peak_allocated_bytes": (
            int(torch.cuda.max_memory_allocated()) if mode == "global" else None
        ),
        "cuda_peak_scope": (
            "whole_workflow" if mode == "global" else "per_node_only"
        ),
    }


def _validate_classes(nodes_module, prompt: Mapping[str, Any]) -> None:
    missing = sorted(
        {
            str(node.get("class_type"))
            for node in prompt.values()
            if str(node.get("class_type")) not in nodes_module.NODE_CLASS_MAPPINGS
        }
    )
    if missing:
        raise ProbeFailure(f"installed ComfyUI is missing prompt nodes: {missing}")


def run(args) -> dict[str, Any]:
    prompt_source = json.loads(args.prompt.read_text(encoding="utf-8"))
    configured = configure_profile(prompt_source, args.profile)
    folder_paths, nodes_module, _prompt_server, loop = _initialize_comfy(
        args.comfy_root
    )
    _validate_classes(nodes_module, configured)
    if args.validate_only:
        loop.close()
        return {
            "status": "PASS",
            "validate_only": True,
            "profile": args.profile,
            "route": _route(configured, args.profile),
            "node_count": len(configured),
        }

    from execution import CacheType, PromptExecutor
    import execution as execution_module

    work_root = args.work_root.resolve()
    output_root = work_root / "output"
    temp_root = work_root / "temp"
    output_root.mkdir(parents=True, exist_ok=True)
    temp_root.mkdir(parents=True, exist_ok=True)
    folder_paths.set_output_directory(str(output_root))
    folder_paths.set_temp_directory(str(temp_root))

    executor = PromptExecutor(
        _ExecutionServer(),
        cache_type=CacheType.CLASSIC,
        cache_args={"ram": float(args.cache_ram_gib), "ram_inactive": 0.0},
    )
    base_seed = int(args.seed)
    warm_prompt = mutate_run(
        configured,
        seed=base_seed,
        filename_prefix=f"p32/{args.case}_{args.profile}_warmup",
    )
    warmup = _run_once(
        executor=executor,
        execution_module=execution_module,
        prompt=warm_prompt,
        prompt_id=f"p32-{args.case}-{args.profile}-warmup",
        mode=args.mode,
        monitor_interval=args.monitor_interval,
        measured=False,
    )
    measured_runs = []
    for index in range(int(args.runs)):
        prompt = mutate_run(
            configured,
            seed=base_seed + index + 1,
            filename_prefix=f"p32/{args.case}_{args.profile}_{args.mode}_{index + 1}",
        )
        measured_runs.append(
            _run_once(
                executor=executor,
                execution_module=execution_module,
                prompt=prompt,
                prompt_id=f"p32-{args.case}-{args.profile}-{args.mode}-{index + 1}",
                mode=args.mode,
                monitor_interval=args.monitor_interval,
                measured=True,
            )
        )
    result = {
        "status": "PASS",
        "format": "h3-continuum-phase3-2-profile-v1",
        "case": args.case,
        "profile": args.profile,
        "route": _route(configured, args.profile),
        "mode": args.mode,
        "cuda_synchronize_before_after_nodes": True,
        "warmup_excluded": True,
        "warmup": warmup,
        "runs": measured_runs,
        "summary": summarize_runs(measured_runs),
        "prompt": str(args.prompt.resolve()),
        "work_root": str(work_root),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    loop.close()
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comfy-root", type=Path, required=True)
    parser.add_argument("--prompt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--profile", choices=PROFILE_NAMES, required=True)
    parser.add_argument("--mode", choices=MEASUREMENT_MODES, default="global")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--seed", type=int, default=32000)
    parser.add_argument("--cache-ram-gib", type=float, default=64.0)
    parser.add_argument("--monitor-interval", type=float, default=0.05)
    parser.add_argument("--validate-only", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.runs < 1:
        raise SystemExit("--runs must be at least 1")
    result = run(args)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
