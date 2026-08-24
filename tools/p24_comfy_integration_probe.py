"""Phase 2A P2-4 probe against the installed ComfyUI execution/cache stack.

The probe uses deterministic decoded CPU IMAGE/AUDIO fixtures.  It does not
load a model, run a VAE, or use CUDA.  Its purpose is to exercise the real
ComfyUI cache, Core Preview/Save nodes, installed VHS Video Combine, Core ESC
interrupt propagation, and restart-style stale cleanup around the V3.5
Disk-backed assembler.
"""

from __future__ import annotations

import argparse
import gc
import importlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from types import SimpleNamespace
from typing import Any

import torch


class ProbeFailure(RuntimeError):
    pass


class _Server:
    def __init__(self):
        self.client_id = None
        self.last_node_id = None
        self.messages: list[tuple[str, dict[str, Any], Any]] = []

    def send_sync(self, event, data, client_id):
        self.messages.append((event, data, client_id))


def _load_package(package_root: Path):
    name = "h3_continuum_p24_probe"
    spec = importlib.util.spec_from_file_location(
        name,
        package_root / "__init__.py",
        submodule_search_locations=[str(package_root)],
    )
    if spec is None or spec.loader is None:
        raise ProbeFailure("cannot create Continuum package import specification")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _install_paths(comfy_root: Path) -> None:
    for value in (
        comfy_root,
        comfy_root / "custom_nodes" / "comfyui-videohelpersuite",
    ):
        text = str(value)
        if text not in sys.path:
            sys.path.insert(0, text)


def _single_plan(package_name: str) -> dict[str, Any]:
    hardening = importlib.import_module(f"{package_name}.hardening")
    temporal = importlib.import_module(f"{package_name}.temporal")
    plan_module = importlib.import_module(f"{package_name}.v3.plan")
    total_frames = 124
    chunk = {
        "sequence_index": 1,
        "chunk_index": 1,
        "total_frames": total_frames,
        "trim_frames": 0,
        "net_frames": total_frames,
        "context_frames": 0,
        "expected_video_latent_t": temporal.video_latent_t(total_frames),
        "expected_audio_latent_t": temporal.audio_latent_t(total_frames),
    }
    return hardening.enrich_assembly_plan(
        {
            "magic": plan_module.ASSEMBLY_PLAN_MAGIC,
            "schema_version": 1,
            "fps": 24,
            "width": 16,
            "height": 16,
            "chunk_seconds": 5.0,
            "target_frames": 120,
            "preserve_final_frame": True,
            "chunks": [chunk],
        }
    )


def _register_probe_nodes(core_nodes, package_module, video_combine):
    package_name = package_module.__name__

    class P24DecodedFixture:
        @classmethod
        def INPUT_TYPES(cls):
            return {
                "required": {
                    "nonce": ("INT", {"default": 0}),
                    "interrupt_before_assembly": (
                        "BOOLEAN",
                        {"default": False},
                    ),
                }
            }

        RETURN_TYPES = (
            "IMAGE",
            "AUDIO",
            "H3_CONTINUUM_ASSEMBLY_PLAN",
        )
        RETURN_NAMES = ("images", "audio", "assembly_plan")
        FUNCTION = "build"
        CATEGORY = "P2-4 Probe"

        def build(self, nonce, interrupt_before_assembly):
            total_frames = 124
            values = (
                torch.arange(total_frames, dtype=torch.float32)
                + float(int(nonce) % 7)
            ) / float(total_frames + 7)
            images = values.reshape(-1, 1, 1, 1).expand(
                -1,
                16,
                16,
                3,
            )
            sample_rate = 32_000
            samples = int(round(total_frames / 24 * sample_rate))
            audio = {
                "waveform": torch.linspace(
                    -0.05,
                    0.05,
                    samples,
                    dtype=torch.float32,
                ).reshape(1, 1, -1),
                "sample_rate": sample_rate,
            }
            plan = _single_plan(package_name)
            if bool(interrupt_before_assembly):
                core_nodes.interrupt_processing(True)
            return images, audio, plan

    class P24FailOrPass:
        @classmethod
        def INPUT_TYPES(cls):
            return {
                "required": {
                    "images": ("IMAGE",),
                    "fail": ("BOOLEAN", {"default": True}),
                }
            }

        RETURN_TYPES = ("IMAGE",)
        FUNCTION = "consume"
        OUTPUT_NODE = True
        CATEGORY = "P2-4 Probe"

        def consume(self, images, fail):
            if bool(fail):
                raise RuntimeError("P2-4 intentional downstream failure")
            return {
                "ui": {"p24": ["downstream pass"]},
                "result": (images,),
            }

    class P24ClearCacheOutput:
        @classmethod
        def INPUT_TYPES(cls):
            return {"required": {"token": ("INT", {"default": 0})}}

        RETURN_TYPES = ("STRING",)
        FUNCTION = "finish"
        OUTPUT_NODE = True
        CATEGORY = "P2-4 Probe"

        def finish(self, token):
            return (f"clear-{int(token)}",)

    core_nodes.NODE_CLASS_MAPPINGS.update(package_module.NODE_CLASS_MAPPINGS)
    core_nodes.NODE_CLASS_MAPPINGS.update(
        {
            "P24DecodedFixture": P24DecodedFixture,
            "P24FailOrPass": P24FailOrPass,
            "P24ClearCacheOutput": P24ClearCacheOutput,
            "P24VHSVideoCombine": video_combine,
        }
    )


def _base_prompt(*, nonce: int, interrupt_before_assembly: bool) -> dict[str, Any]:
    return {
        "1": {
            "class_type": "P24DecodedFixture",
            "inputs": {
                "nonce": int(nonce),
                "interrupt_before_assembly": bool(interrupt_before_assembly),
            },
        },
        "2": {
            "class_type": "H3ContinuumAssembleSeamV35",
            "inputs": {
                "images": ["1", 0],
                "audio": ["1", 1],
                "assembly_plan": ["1", 2],
                "exact_total_duration": True,
                "audio_seam": "Off",
                "video_seam": "Off",
                "buffer_backend": "Disk-backed",
                "diagnostics": "Basic",
            },
        },
    }


def _failure_prompt(*, fail: bool, nonce: int = 0) -> dict[str, Any]:
    prompt = _base_prompt(nonce=nonce, interrupt_before_assembly=False)
    prompt["3"] = {
        "class_type": "P24FailOrPass",
        "inputs": {"images": ["2", 0], "fail": bool(fail)},
    }
    return prompt


def _compatibility_prompt() -> dict[str, Any]:
    prompt = _base_prompt(nonce=0, interrupt_before_assembly=False)
    prompt.update(
        {
            "4": {
                "class_type": "SaveImage",
                "inputs": {
                    "images": ["2", 0],
                    "filename_prefix": "P24/Save",
                },
            },
            "5": {
                "class_type": "PreviewImage",
                "inputs": {"images": ["2", 0]},
            },
            "6": {
                "class_type": "P24VHSVideoCombine",
                "inputs": {
                    "images": ["2", 0],
                    "audio": ["2", 1],
                    "frame_rate": 24,
                    "loop_count": 0,
                    "filename_prefix": "P24/VHS",
                    "format": "video/h264-mp4",
                    "pingpong": False,
                    "save_output": True,
                },
            },
        }
    )
    return prompt


def _interrupt_prompt() -> dict[str, Any]:
    prompt = _base_prompt(nonce=99, interrupt_before_assembly=True)
    prompt["3"] = {
        "class_type": "P24FailOrPass",
        "inputs": {"images": ["2", 0], "fail": False},
    }
    return prompt


def _clear_prompt(token: int) -> dict[str, Any]:
    return {
        "9": {
            "class_type": "P24ClearCacheOutput",
            "inputs": {"token": int(token)},
        }
    }


def _cached_nodes(executor) -> set[str]:
    for event, data in executor.status_messages:
        if event == "execution_cached":
            return {str(value) for value in data.get("nodes", [])}
    return set()


def _has_event(executor, wanted: str) -> bool:
    return any(event == wanted for event, _ in executor.status_messages)


def _execute(executor, prompt, prompt_id: str, outputs: list[str]) -> None:
    executor.execute(
        prompt,
        prompt_id,
        extra_data={},
        execute_outputs=outputs,
    )


def _managed_files(backing_root: Path, suffix: str) -> list[Path]:
    return sorted(backing_root.glob(f"h3c-p20-*.{suffix}"))


def _all_output_files(root: Path) -> set[str]:
    if not root.exists():
        return set()
    return {
        str(path.relative_to(root))
        for path in root.rglob("*")
        if path.is_file()
    }


def _assert_output_paths(output_root: Path, temp_root: Path, history: dict) -> dict:
    outputs = history.get("outputs", {})
    save_items = outputs.get("4", {}).get("images", [])
    preview_items = outputs.get("5", {}).get("images", [])
    gifs = outputs.get("6", {}).get("gifs", [])
    if len(save_items) != 120:
        raise ProbeFailure(f"Core SaveImage wrote {len(save_items)} frames, expected 120")
    if len(preview_items) != 120:
        raise ProbeFailure(
            f"Core PreviewImage wrote {len(preview_items)} frames, expected 120"
        )
    if len(gifs) != 1:
        raise ProbeFailure(f"VHS returned {len(gifs)} previews, expected 1")

    for item in save_items:
        path = output_root / item.get("subfolder", "") / item["filename"]
        if not path.is_file() or path.stat().st_size <= 0:
            raise ProbeFailure(f"Core SaveImage output missing: {path}")
    for item in preview_items:
        path = temp_root / item.get("subfolder", "") / item["filename"]
        if not path.is_file() or path.stat().st_size <= 0:
            raise ProbeFailure(f"Core PreviewImage output missing: {path}")
    video_path = Path(gifs[0]["fullpath"])
    if not video_path.is_file() or video_path.stat().st_size <= 0:
        raise ProbeFailure(f"VHS output missing: {video_path}")
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        raise ProbeFailure("ffprobe is required for P2-4 VHS acceptance")
    inspected = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-count_frames",
            "-show_entries",
            (
                "stream=codec_type,codec_name,width,height,r_frame_rate,"
                "nb_read_frames,sample_rate,channels,duration:"
                "format=duration,size"
            ),
            "-of",
            "json",
            str(video_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    media = json.loads(inspected.stdout)
    video_stream = next(
        (item for item in media.get("streams", []) if item.get("codec_type") == "video"),
        None,
    )
    audio_stream = next(
        (item for item in media.get("streams", []) if item.get("codec_type") == "audio"),
        None,
    )
    if video_stream is None or audio_stream is None:
        raise ProbeFailure("VHS output does not contain both video and audio")
    if (
        video_stream.get("codec_name") != "h264"
        or int(video_stream.get("nb_read_frames", 0)) != 120
        or video_stream.get("r_frame_rate") != "24/1"
        or int(video_stream.get("width", 0)) != 16
        or int(video_stream.get("height", 0)) != 16
        or int(audio_stream.get("sample_rate", 0)) != 32_000
    ):
        raise ProbeFailure(f"unexpected VHS media contract: {media}")
    return {
        "save_frames": len(save_items),
        "preview_frames": len(preview_items),
        "vhs_file": str(video_path),
        "vhs_bytes": int(video_path.stat().st_size),
        "vhs_video_frames": int(video_stream["nb_read_frames"]),
        "vhs_video_fps": video_stream["r_frame_rate"],
        "vhs_video_duration": float(video_stream["duration"]),
        "vhs_audio_sample_rate": int(audio_stream["sample_rate"]),
        "vhs_container_duration": float(media["format"]["duration"]),
    }


def _collect_until_empty(manager, backing_root: Path) -> None:
    for _ in range(8):
        gc.collect()
        manager.collect_ready()
        if not _managed_files(backing_root, "bin") and not _managed_files(
            backing_root,
            "json",
        ):
            return
        time.sleep(0.05)
    raise ProbeFailure("released cache storage did not become reclaimable")


def _run_child_mode(args, package_root: Path) -> int:
    _install_paths(args.comfy_root)
    package = _load_package(package_root)
    buffers = importlib.import_module(f"{package.__name__}.v3.file_backed_buffer")
    root = args.backing_root.resolve()
    if args.child_mode == "create-stale":
        manager = buffers.get_file_backed_image_manager(root)
        allocation = manager.allocate((2, 8, 8, 3), dtype=torch.float32)
        tensor = allocation.publish()
        tensor.fill_(0.25)
        os._exit(0)
    if args.child_mode == "clean-stale":
        buffers.get_file_backed_image_manager(root)
        payload = {
            "bin": len(_managed_files(root, "bin")),
            "json": len(_managed_files(root, "json")),
        }
        print(json.dumps(payload, sort_keys=True))
        return 0
    raise ProbeFailure(f"unknown child mode: {args.child_mode}")


def _restart_stale_probe(args, package_root: Path, stale_root: Path) -> dict:
    common = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--comfy-root",
        str(args.comfy_root),
        "--package-root",
        str(package_root),
        "--backing-root",
        str(stale_root),
    ]
    subprocess.run(
        [*common, "--child-mode", "create-stale"],
        check=True,
        capture_output=True,
        text=True,
    )
    created = (
        len(_managed_files(stale_root, "bin")),
        len(_managed_files(stale_root, "json")),
    )
    if created != (1, 1):
        raise ProbeFailure(f"crash child left unexpected files: {created}")
    cleaned = subprocess.run(
        [*common, "--child-mode", "clean-stale"],
        check=True,
        capture_output=True,
        text=True,
    )
    line = next(
        (value for value in reversed(cleaned.stdout.splitlines()) if value.startswith("{")),
        "",
    )
    payload = json.loads(line)
    if payload != {"bin": 0, "json": 0}:
        raise ProbeFailure(f"restart stale cleanup failed: {payload}")
    return {"created_pairs": 1, "remaining_pairs_after_restart": 0}


def run_probe(args, package_root: Path) -> dict:
    _install_paths(args.comfy_root)
    import folder_paths
    import nodes as core_nodes
    import server as comfy_server
    from execution import CacheType, PromptExecutor

    # A normal ComfyUI process installs this singleton before loading custom
    # nodes.  The headless probe supplies only the queue fields VHS imports;
    # Video Combine itself does not use them without a meta-batch.
    if not hasattr(comfy_server.PromptServer, "instance"):
        comfy_server.PromptServer.instance = SimpleNamespace(
            prompt_queue=SimpleNamespace(
                currently_running={},
                put=lambda _item: None,
            ),
            number=0,
        )
    from videohelpersuite.nodes import VideoCombine

    package = _load_package(package_root)
    _register_probe_nodes(core_nodes, package, VideoCombine)
    buffers = importlib.import_module(f"{package.__name__}.v3.file_backed_buffer")

    work_root = args.work_root.resolve()
    output_root = work_root / "output"
    temp_root = work_root / "temp"
    backing_root = temp_root / "h3-continuum-v35-file-backed"
    stale_root = work_root / "restart-stale"
    for path in (output_root, temp_root, backing_root, stale_root):
        path.mkdir(parents=True, exist_ok=True)

    old_output = folder_paths.get_output_directory()
    old_temp = folder_paths.get_temp_directory()
    folder_paths.set_output_directory(str(output_root))
    folder_paths.set_temp_directory(str(temp_root))
    prompt_graphs = {
        "downstream_error": _failure_prompt(fail=True),
        "recovery": _failure_prompt(fail=False),
        "compatibility": _compatibility_prompt(),
        "interrupt": _interrupt_prompt(),
        "clear": _clear_prompt(1),
    }
    (work_root / "p24_prompt_graphs.json").write_text(
        json.dumps(prompt_graphs, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    server = _Server()
    executor = PromptExecutor(
        server,
        cache_type=CacheType.CLASSIC,
        cache_args={"ram": 16.0, "ram_inactive": 0.0},
    )
    manager = buffers.get_file_backed_image_manager(backing_root)
    started = time.perf_counter()
    try:
        _execute(executor, prompt_graphs["downstream_error"], "p24-error", ["3"])
        if executor.success or not _has_event(executor, "execution_error"):
            raise ProbeFailure("intentional downstream error was not reported")
        if (len(_managed_files(backing_root, "bin")), len(_managed_files(backing_root, "json"))) != (1, 1):
            raise ProbeFailure("completed assembler output was not retained by Core cache")
        retained = manager.collect_ready()
        if retained.deferred < 1:
            raise ProbeFailure("Core cache did not keep mapped storage alive after error")

        _execute(executor, prompt_graphs["recovery"], "p24-recovery", ["3"])
        recovery_cached = _cached_nodes(executor)
        if not executor.success or "2" not in recovery_cached:
            raise ProbeFailure("requeue did not reuse cached V3.5 assembler output")
        if len(_managed_files(backing_root, "bin")) != 1:
            raise ProbeFailure("same-input requeue created another backing file")

        _execute(
            executor,
            prompt_graphs["compatibility"],
            "p24-compatibility",
            ["4", "5", "6"],
        )
        if not executor.success or "2" not in _cached_nodes(executor):
            raise ProbeFailure("downstream compatibility run did not reuse assembler cache")
        downstream = _assert_output_paths(
            output_root,
            temp_root,
            executor.history_result,
        )
        output_files_before = _all_output_files(output_root)
        temp_files_before = _all_output_files(temp_root)

        _execute(
            executor,
            prompt_graphs["compatibility"],
            "p24-compatibility-requeue",
            ["4", "5", "6"],
        )
        second_cached = _cached_nodes(executor)
        if not {"2", "4", "5", "6"}.issubset(second_cached):
            raise ProbeFailure(
                f"compatibility requeue cache miss: {sorted(second_cached)}"
            )
        if output_files_before != _all_output_files(output_root):
            raise ProbeFailure("cached requeue unexpectedly rewrote output files")
        if temp_files_before != _all_output_files(temp_root):
            raise ProbeFailure("cached requeue unexpectedly rewrote temp files")

        _execute(executor, prompt_graphs["clear"], "p24-clear", ["9"])
        gc.collect()
        if manager.tracked_count() != 1:
            raise ProbeFailure("cache eviction lost lifetime-manager tracking state")

        replacement = _failure_prompt(fail=False, nonce=2)
        _execute(executor, replacement, "p24-replacement", ["3"])
        if not executor.success or len(_managed_files(backing_root, "bin")) != 1:
            raise ProbeFailure("post-eviction allocation did not keep backing pairs bounded")
        _execute(executor, _clear_prompt(2), "p24-final-clear", ["9"])
        _collect_until_empty(manager, backing_root)

        _execute(executor, prompt_graphs["interrupt"], "p24-interrupt", ["3"])
        if executor.success or not _has_event(executor, "execution_interrupted"):
            raise ProbeFailure("Core interrupt was not propagated as execution_interrupted")
        if _managed_files(backing_root, "bin") or _managed_files(backing_root, "json"):
            raise ProbeFailure("interrupted unpublished allocation left backing files")
        _execute(executor, _clear_prompt(3), "p24-interrupt-clear", ["9"])
        _collect_until_empty(manager, backing_root)

        stale = _restart_stale_probe(args, package_root, stale_root)
        elapsed = time.perf_counter() - started
        result = {
            "phase": "P2-4",
            "status": "PASS",
            "gpu_used": False,
            "fixture": {
                "source": "deterministic decoded CPU IMAGE/AUDIO",
                "frames": 124,
                "assembled_frames": 120,
                "width": 16,
                "height": 16,
                "fps": 24,
                "audio_sample_rate": 32_000,
                "model": "not applicable",
                "lora": "not applicable",
                "sampler": "not applicable",
                "prompt": "not applicable",
                "media_inputs": "none",
            },
            "cache": {
                "implementation": "ComfyUI PromptExecutor CLASSIC / HierarchicalCache",
                "downstream_error_retained": True,
                "same_input_requeue_cached": True,
                "recovery_cached_nodes": sorted(recovery_cached),
                "compatibility_requeue_cached_nodes": sorted(second_cached),
                "post_eviction_pair_count_bounded": True,
                "final_pairs": 0,
            },
            "downstream": downstream,
            "interrupt": {
                "core_execution_interrupted": True,
                "unpublished_pairs_remaining": 0,
            },
            "restart_stale_cleanup": stale,
            "elapsed_seconds": round(elapsed, 3),
            "work_root": str(work_root),
        }
        (work_root / "p24_result.json").write_text(
            json.dumps(result, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return result
    finally:
        core_nodes.interrupt_processing(False)
        folder_paths.set_output_directory(old_output)
        folder_paths.set_temp_directory(old_temp)


def _parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comfy-root", type=Path, required=True)
    parser.add_argument("--package-root", type=Path)
    parser.add_argument("--work-root", type=Path)
    parser.add_argument("--child-mode", choices=("create-stale", "clean-stale"))
    parser.add_argument("--backing-root", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    args.comfy_root = args.comfy_root.resolve()
    package_root = (
        args.package_root.resolve()
        if args.package_root is not None
        else Path(__file__).resolve().parents[1]
    )
    if args.child_mode is not None:
        if args.backing_root is None:
            raise ProbeFailure("--backing-root is required in child mode")
        return _run_child_mode(args, package_root)
    if args.work_root is None:
        raise ProbeFailure("--work-root is required")
    result = run_probe(args, package_root)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
