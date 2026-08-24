"""Phase 2A P2-5 GPU/RSS acceptance probe for the V3.5 assembler.

The probe reuses a completed three-chunk Run Storage revision.  It restores
the logical AV latents, losslessly reconstructs the accepted Long Terminal
Merge physical decode groups, runs the installed Core Video/Audio VAE Decode
nodes, and compares independent RAM and Disk-backed assembler processes.

No sampler/model/CLIP execution is performed and no browser interaction is
required.  Each backend runs in a fresh process so its RSS peak is not
contaminated by the other backend's ComfyUI cache.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
from types import SimpleNamespace
from typing import Any

import psutil
import torch
from safetensors.torch import load_file


class ProbeFailure(RuntimeError):
    pass


class _Server:
    def __init__(self):
        self.client_id = None
        self.last_node_id = None
        self.messages: list[tuple[str, dict[str, Any], Any]] = []

    def send_sync(self, event, data, client_id):
        self.messages.append((event, data, client_id))


class _ResourceMonitor:
    def __init__(self, interval: float = 0.05):
        self.interval = float(interval)
        self.process = psutil.Process()
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.samples = 0
        self.peak_rss = 0
        self.minimum_system_available = 1 << 63
        self.minimum_cuda_free = 1 << 63

    def _sample(self) -> None:
        try:
            self.peak_rss = max(self.peak_rss, int(self.process.memory_info().rss))
            self.minimum_system_available = min(
                self.minimum_system_available,
                int(psutil.virtual_memory().available),
            )
            if torch.cuda.is_available():
                free, _total = torch.cuda.mem_get_info()
                self.minimum_cuda_free = min(self.minimum_cuda_free, int(free))
            self.samples += 1
        except Exception:
            pass

    def _run(self) -> None:
        while not self.stop_event.wait(self.interval):
            self._sample()

    def start(self) -> None:
        self._sample()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self) -> dict[str, Any]:
        self._sample()
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=5.0)
        return {
            "samples": int(self.samples),
            "peak_rss_bytes": int(self.peak_rss),
            "minimum_system_available_bytes": int(self.minimum_system_available),
            "minimum_cuda_free_bytes": (
                int(self.minimum_cuda_free)
                if self.minimum_cuda_free != 1 << 63
                else None
            ),
        }


def _install_paths(comfy_root: Path) -> None:
    for value in (
        comfy_root,
        comfy_root / "custom_nodes" / "comfyui-videohelpersuite",
    ):
        text = str(value)
        if text not in sys.path:
            sys.path.insert(0, text)


def _load_package(package_root: Path):
    name = "h3_continuum_p25_probe"
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


def _hash_tensor(tensor: torch.Tensor, batch: int = 8) -> str:
    digest = hashlib.sha256()
    value = tensor.detach().cpu()
    if value.ndim == 0:
        digest.update(value.numpy().tobytes(order="C"))
        return digest.hexdigest()
    for start in range(0, int(value.shape[0]), int(batch)):
        block = value[start : start + int(batch)].contiguous()
        digest.update(block.numpy().tobytes(order="C"))
    return digest.hexdigest()


def _tensor_is_finite_batched(tensor: torch.Tensor, batch: int = 8) -> bool:
    value = tensor.detach().cpu()
    if value.ndim == 0:
        return bool(torch.isfinite(value).item())
    for start in range(0, int(value.shape[0]), int(batch)):
        if not bool(torch.isfinite(value[start : start + int(batch)]).all().item()):
            return False
    return True


def _process_memory_snapshot() -> dict[str, int]:
    values = psutil.Process().memory_full_info()._asdict()
    return {key: int(value) for key, value in values.items()}


def _managed_files(root: Path, suffix: str) -> list[Path]:
    return sorted(root.glob(f"h3c-p20-*.{suffix}"))


def _collect_until_empty(manager, root: Path) -> None:
    for _ in range(20):
        gc.collect()
        manager.collect_ready()
        if not _managed_files(root, "bin") and not _managed_files(root, "json"):
            return
        time.sleep(0.1)
    raise ProbeFailure("released Disk-backed output was not reclaimed")


def _register_probe_nodes(
    core_nodes,
    package_module,
    revision_root: Path,
    results,
    video_combine=None,
    stress_size: int = 0,
):
    plan_module = importlib.import_module(f"{package_module.__name__}.v3.plan")

    class P25StoredLongTerminalFixture:
        @classmethod
        def INPUT_TYPES(cls):
            return {"required": {"nonce": ("INT", {"default": 0})}}

        RETURN_TYPES = ("LATENT", "LATENT", "H3_CONTINUUM_ASSEMBLY_PLAN")
        RETURN_NAMES = ("video_latents", "audio_latents", "assembly_plan")
        OUTPUT_IS_LIST = (True, True, False)
        FUNCTION = "load"
        CATEGORY = "P2-5 Probe"

        def load(self, nonce):
            del nonce
            manifest_path = revision_root / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            records = sorted(
                manifest["chunks"],
                key=lambda item: int(item["sequence_index"]),
            )
            entries = []
            for record in records:
                tensors = load_file(
                    str(revision_root / "chunks" / record["filename"]),
                    device="cpu",
                )
                entry = dict(record["entry"])
                entry["video"] = tensors["video"]
                entry["audio"] = tensors["audio"]
                entry["prompt"] = f"stored:{entry.get('prompt_hash', '')}"
                entries.append(entry)
            decode_entries, plan = plan_module.prepare_physical_decode_entries(
                entries,
                chunk_seconds=float(manifest["contract"]["global"]["chunk_seconds"]),
                preserve_final_frame=manifest.get("last_frame_hash") not in (None, "none"),
                terminal_merged=True,
            )
            results["fixture"] = {
                "revision_id": manifest["revision_id"],
                "logical_chunks": len(entries),
                "physical_decode_groups": len(decode_entries),
                "video_shapes": [list(item["video"].shape) for item in decode_entries],
                "audio_shapes": [list(item["audio"].shape) for item in decode_entries],
                "width": int(plan["width"]),
                "height": int(plan["height"]),
                "target_frames": int(plan["target_frames"]),
                "prompt_mode": manifest["contract"]["prompt_mode"],
                "conditioning_mode": manifest["contract"]["global"]["conditioning_mode"],
                "sampler": manifest["contract"]["global"]["sampler"]["function"],
                "sigma_count": int(manifest["contract"]["global"]["sigmas"]["shape"][0]),
                "base_seed": int(manifest["contract"]["global"]["base_seed"]),
            }
            return (
                [{"samples": item["video"]} for item in decode_entries],
                [{"samples": item["audio"]} for item in decode_entries],
                plan,
            )

    class P25DigestOutput:
        @classmethod
        def INPUT_TYPES(cls):
            return {
                "required": {
                    "images": ("IMAGE",),
                    "audio": ("AUDIO",),
                    "report": ("STRING",),
                    "backend": (["Auto", "RAM", "Disk-backed"],),
                }
            }

        RETURN_TYPES = ("STRING",)
        FUNCTION = "consume"
        OUTPUT_NODE = True
        CATEGORY = "P2-5 Probe"

        def consume(self, images, audio, report, backend):
            waveform = audio["waveform"]
            hash_batch = 1 if results.get("stress") else 8
            results["pre_digest_memory"] = _process_memory_snapshot()
            results["digest"] = {
                "backend": str(backend),
                "video_shape": list(images.shape),
                "video_dtype": str(images.dtype),
                "video_sha256": _hash_tensor(images, batch=hash_batch),
                "video_finite": _tensor_is_finite_batched(
                    images, batch=hash_batch
                ),
                "audio_shape": list(waveform.shape),
                "audio_dtype": str(waveform.dtype),
                "audio_sha256": _hash_tensor(waveform),
                "audio_finite": _tensor_is_finite_batched(waveform),
                "audio_sample_rate": int(audio["sample_rate"]),
                "report": str(report),
            }
            return {"ui": {"p25": [str(backend)]}, "result": (str(backend),)}

    class P25SyntheticDecodedStressFixture:
        """Large decoded IMAGE fixture with O(H*W), not O(T*H*W), source RAM."""

        @classmethod
        def INPUT_TYPES(cls):
            return {"required": {"nonce": ("INT", {"default": 0})}}

        RETURN_TYPES = ("IMAGE", "AUDIO", "H3_CONTINUUM_ASSEMBLY_PLAN")
        RETURN_NAMES = ("images", "audio", "assembly_plan")
        OUTPUT_IS_LIST = (True, True, False)
        FUNCTION = "load"
        CATEGORY = "P2-5 Probe"

        def load(self, nonce):
            del nonce
            if stress_size <= 0:
                raise ProbeFailure("synthetic stress fixture requires --stress-size")

            # Reuse the accepted Long Terminal Merge plan instead of inventing a
            # synthetic grouping contract. Only the already-decoded pixel frames
            # are replaced. Expanded frame views keep source RAM bounded while
            # the assembler must still write every byte of the final IMAGE.
            _video, _audio, plan = P25StoredLongTerminalFixture().load(0)
            del _video, _audio
            gc.collect()
            plan = dict(plan)
            plan["width"] = int(stress_size)
            plan["height"] = int(stress_size)
            units = list(plan.get("decode_groups") or plan["chunks"])

            axis = torch.linspace(0.0, 1.0, stress_size, dtype=torch.float32)
            yy = axis.view(stress_size, 1)
            xx = axis.view(1, stress_size)
            frames = []
            waveforms = []
            sample_rate = 32000
            for index, unit in enumerate(units):
                base = torch.empty(
                    (1, stress_size, stress_size, 3), dtype=torch.float32
                )
                base[0, ..., 0].copy_((xx + index * 0.07).remainder(1.0))
                base[0, ..., 1].copy_((yy + index * 0.11).remainder(1.0))
                base[0, ..., 2].copy_(((xx + yy) * 0.5 + index * 0.13).remainder(1.0))
                total_frames = int(unit["total_frames"])
                frames.append(base.expand(total_frames, -1, -1, -1))

                total_samples = int(round(total_frames / 24.0 * sample_rate))
                phase = torch.linspace(
                    0.0,
                    (index + 1) * 24.0,
                    total_samples,
                    dtype=torch.float32,
                )
                wave = (0.05 * torch.sin(phase)).reshape(1, 1, -1)
                waveforms.append(
                    {
                        "waveform": wave.expand(1, 2, -1),
                        "sample_rate": sample_rate,
                    }
                )

            final_bytes = (
                int(plan["target_frames"])
                * stress_size
                * stress_size
                * 3
                * torch.tensor([], dtype=torch.float32).element_size()
            )
            results["stress"] = {
                "size": int(stress_size),
                "target_frames": int(plan["target_frames"]),
                "final_image_bytes": int(final_bytes),
                "final_image_gib": round(final_bytes / (1024**3), 3),
                "source_frame_storage_bytes": int(
                    sum(frame.untyped_storage().nbytes() for frame in frames)
                ),
                "source_frames_are_expanded_views": all(
                    int(frame.stride(0)) == 0 for frame in frames
                ),
            }
            return frames, waveforms, plan

    class P25ClearOutput:
        @classmethod
        def INPUT_TYPES(cls):
            return {"required": {"token": ("INT", {"default": 0})}}

        RETURN_TYPES = ("STRING",)
        FUNCTION = "finish"
        OUTPUT_NODE = True
        CATEGORY = "P2-5 Probe"

        def finish(self, token):
            return (f"clear-{int(token)}",)

    class P25InterruptAfterAllocation:
        @classmethod
        def INPUT_TYPES(cls):
            return {
                "required": {
                    "images": ("IMAGE",),
                    "audio": ("AUDIO",),
                    "assembly_plan": ("H3_CONTINUUM_ASSEMBLY_PLAN",),
                }
            }

        RETURN_TYPES = ("IMAGE", "AUDIO", "H3_CONTINUUM_ASSEMBLY_PLAN")
        RETURN_NAMES = ("images", "audio", "assembly_plan")
        INPUT_IS_LIST = True
        OUTPUT_IS_LIST = (True, True, False)
        FUNCTION = "arm"
        CATEGORY = "P2-5 Probe"

        def arm(self, images, audio, assembly_plan):
            backing_root = Path(results["backing_root"])

            def trigger():
                deadline = time.monotonic() + 30.0
                while time.monotonic() < deadline:
                    if _managed_files(backing_root, "bin"):
                        results["interrupt_observed_allocation"] = True
                        time.sleep(0.05)
                        core_nodes.interrupt_processing(True)
                        return
                    time.sleep(0.005)
                results["interrupt_observed_allocation"] = False
                core_nodes.interrupt_processing(True)

            threading.Thread(target=trigger, daemon=True).start()
            return images, audio, assembly_plan[0]

    from comfy_extras.nodes_audio import VAEDecodeAudio

    core_nodes.NODE_CLASS_MAPPINGS.update(package_module.NODE_CLASS_MAPPINGS)
    core_nodes.NODE_CLASS_MAPPINGS.update(
        {
            "VAEDecodeAudio": VAEDecodeAudio,
            "P25StoredLongTerminalFixture": P25StoredLongTerminalFixture,
            "P25SyntheticDecodedStressFixture": P25SyntheticDecodedStressFixture,
            "P25DigestOutput": P25DigestOutput,
            "P25ClearOutput": P25ClearOutput,
            "P25InterruptAfterAllocation": P25InterruptAfterAllocation,
        }
    )
    if video_combine is not None:
        core_nodes.NODE_CLASS_MAPPINGS["P25VHSVideoCombine"] = video_combine


def _prompt(
    backend: str,
    *,
    downstream: bool = False,
    interrupt_after_allocation: bool = False,
    stress: bool = False,
) -> dict[str, Any]:
    if stress:
        return {
            "1": {
                "class_type": "P25SyntheticDecodedStressFixture",
                "inputs": {"nonce": 0},
            },
            "6": {
                "class_type": "H3ContinuumAssembleSeamV35",
                "inputs": {
                    "images": ["1", 0],
                    "audio": ["1", 1],
                    "assembly_plan": ["1", 2],
                    "exact_total_duration": True,
                    "audio_seam": "Auto",
                    "video_seam": "Auto",
                    "buffer_backend": str(backend),
                    "diagnostics": "Detailed Report",
                },
            },
            "7": {
                "class_type": "P25DigestOutput",
                "inputs": {
                    "images": ["6", 0],
                    "audio": ["6", 1],
                    "report": ["6", 2],
                    "backend": str(backend),
                },
            },
        }
    prompt = {
        "1": {
            "class_type": "P25StoredLongTerminalFixture",
            "inputs": {"nonce": 0},
        },
        "2": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"},
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "minimax_h3_audio_vae_fp32.safetensors"},
        },
        "4": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["1", 0], "vae": ["2", 0]},
        },
        "5": {
            "class_type": "VAEDecodeAudio",
            "inputs": {"samples": ["1", 1], "vae": ["3", 0]},
        },
        "6": {
            "class_type": "H3ContinuumAssembleSeamV35",
            "inputs": {
                "images": ["4", 0],
                "audio": ["5", 0],
                "assembly_plan": ["1", 2],
                "exact_total_duration": True,
                "audio_seam": "Auto",
                "video_seam": "Auto",
                "buffer_backend": str(backend),
                "diagnostics": "Detailed Report",
            },
        },
        "7": {
            "class_type": "P25DigestOutput",
            "inputs": {
                "images": ["6", 0],
                "audio": ["6", 1],
                "report": ["6", 2],
                "backend": str(backend),
            },
        },
    }
    if interrupt_after_allocation:
        prompt["11"] = {
            "class_type": "P25InterruptAfterAllocation",
            "inputs": {
                "images": ["4", 0],
                "audio": ["5", 0],
                "assembly_plan": ["1", 2],
            },
        }
        prompt["6"]["inputs"].update(
            {
                "images": ["11", 0],
                "audio": ["11", 1],
                "assembly_plan": ["11", 2],
            }
        )
    if downstream:
        prompt.update(
            {
                "8": {
                    "class_type": "SaveImage",
                    "inputs": {
                        "images": ["6", 0],
                        "filename_prefix": "P25/Save",
                    },
                },
                "9": {
                    "class_type": "PreviewImage",
                    "inputs": {"images": ["6", 0]},
                },
                "10": {
                    "class_type": "P25VHSVideoCombine",
                    "inputs": {
                        "images": ["6", 0],
                        "audio": ["6", 1],
                        "frame_rate": 24,
                        "loop_count": 0,
                        "filename_prefix": "P25/VHS",
                        "format": "video/h264-mp4",
                        "pingpong": False,
                        "save_output": True,
                    },
                },
            }
        )
    return prompt


def _downstream_result(history: dict[str, Any]) -> dict[str, Any]:
    outputs = history.get("outputs", {})
    save_items = outputs.get("8", {}).get("images", [])
    preview_items = outputs.get("9", {}).get("images", [])
    video_items = outputs.get("10", {}).get("gifs", [])
    if len(save_items) != 360 or len(preview_items) != 360 or len(video_items) != 1:
        raise ProbeFailure(
            "unexpected downstream output counts: "
            f"save={len(save_items)} preview={len(preview_items)} vhs={len(video_items)}"
        )
    video_path = Path(video_items[0]["fullpath"])
    if not video_path.is_file() or video_path.stat().st_size <= 0:
        raise ProbeFailure(f"VHS output is missing: {video_path}")
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        raise ProbeFailure("ffprobe is required for P2-5 downstream acceptance")
    inspected = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-count_frames",
            "-show_entries",
            (
                "stream=codec_type,codec_name,width,height,r_frame_rate,"
                "nb_read_frames,sample_rate,channels,duration:format=duration,size"
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
    expected = (
        int(video_stream.get("width", 0)) == 640
        and int(video_stream.get("height", 0)) == 640
        and int(video_stream.get("nb_read_frames", 0)) == 360
        and video_stream.get("r_frame_rate") == "24/1"
        and int(audio_stream.get("sample_rate", 0)) == 32_000
    )
    if not expected:
        raise ProbeFailure(f"unexpected VHS media contract: {media}")
    return {
        "save_frames": len(save_items),
        "preview_frames": len(preview_items),
        "vhs_file": str(video_path),
        "vhs_bytes": int(video_path.stat().st_size),
        "video_codec": video_stream.get("codec_name"),
        "video_frames": int(video_stream["nb_read_frames"]),
        "video_fps": video_stream["r_frame_rate"],
        "video_duration": float(video_stream["duration"]),
        "audio_codec": audio_stream.get("codec_name"),
        "audio_sample_rate": int(audio_stream["sample_rate"]),
        "container_duration": float(media["format"]["duration"]),
    }


def _clear_prompt() -> dict[str, Any]:
    return {"9": {"class_type": "P25ClearOutput", "inputs": {"token": 1}}}


def _has_event(executor, wanted: str) -> bool:
    return any(event == wanted for event, _data in executor.status_messages)


def _cached_nodes(executor) -> set[str]:
    for event, data in executor.status_messages:
        if event == "execution_cached":
            return {str(value) for value in data.get("nodes", [])}
    return set()


def _run_backend(args, package_root: Path) -> dict[str, Any]:
    _install_paths(args.comfy_root)
    import folder_paths
    import nodes as core_nodes
    import server as comfy_server
    from execution import CacheType, PromptExecutor

    if not hasattr(comfy_server.PromptServer, "instance"):
        comfy_server.PromptServer.instance = SimpleNamespace(
            prompt_queue=SimpleNamespace(currently_running={}, put=lambda _item: None),
            number=0,
        )

    work_root = args.work_root.resolve()
    output_root = work_root / "output"
    temp_root = work_root / "temp"
    backing_root = temp_root / "h3-continuum-v35-file-backed"
    for path in (output_root, temp_root, backing_root):
        path.mkdir(parents=True, exist_ok=True)

    package = _load_package(package_root)
    results: dict[str, Any] = {"backing_root": str(backing_root)}
    video_combine = None
    if args.downstream:
        from videohelpersuite.nodes import VideoCombine

        video_combine = VideoCombine
    _register_probe_nodes(
        core_nodes,
        package,
        args.revision_root,
        results,
        video_combine=video_combine,
        stress_size=int(args.stress_size),
    )
    buffers = importlib.import_module(f"{package.__name__}.v3.file_backed_buffer")

    folder_paths.set_output_directory(str(output_root))
    folder_paths.set_temp_directory(str(temp_root))

    prompt = _prompt(
        args.backend,
        downstream=bool(args.downstream),
        interrupt_after_allocation=bool(args.interrupt_after_allocation),
        stress=bool(args.stress_size),
    )
    (work_root / "p25_prompt_graph.json").write_text(
        json.dumps(prompt, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    executor = PromptExecutor(
        _Server(),
        cache_type=CacheType.CLASSIC,
        cache_args={"ram": 64.0, "ram_inactive": 0.0},
    )
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
    monitor = _ResourceMonitor()
    monitor.start()
    started = time.perf_counter()
    execute_outputs = ["7", "8", "9", "10"] if args.downstream else ["7"]
    executor.execute(
        prompt,
        f"p25-{args.backend.lower()}",
        extra_data={},
        execute_outputs=execute_outputs,
    )
    cache_requeue = None
    if args.cache_requeue and executor.success:
        first_pairs = (
            len(_managed_files(backing_root, "bin")),
            len(_managed_files(backing_root, "json")),
        )
        executor.execute(
            prompt,
            f"p25-{args.backend.lower()}-requeue",
            extra_data={},
            execute_outputs=execute_outputs,
        )
        cached = _cached_nodes(executor)
        second_pairs = (
            len(_managed_files(backing_root, "bin")),
            len(_managed_files(backing_root, "json")),
        )
        cache_requeue = {
            "cached_nodes": sorted(cached),
            "assembler_cached": "6" in cached,
            "first_pair_count": list(first_pairs),
            "second_pair_count": list(second_pairs),
            "pair_count_bounded": first_pairs == second_pairs,
        }
        if not executor.success or not cache_requeue["assembler_cached"]:
            raise ProbeFailure(f"large-output requeue cache miss: {cache_requeue}")
        if not cache_requeue["pair_count_bounded"]:
            raise ProbeFailure(f"large-output requeue grew backing files: {cache_requeue}")
    elapsed = time.perf_counter() - started
    resources = monitor.stop()
    manager = buffers.get_file_backed_image_manager(backing_root)
    if args.interrupt_after_allocation:
        interrupted = _has_event(executor, "execution_interrupted")
        core_nodes.interrupt_processing(False)
        executor.execute(_clear_prompt(), "p25-clear", extra_data={}, execute_outputs=["9"])
        del executor
        _collect_until_empty(manager, backing_root)
        result = {
            "backend": args.backend,
            "stage": "interrupt-after-allocation",
            "status": "PASS" if interrupted else "FAIL",
            "execution_interrupted": bool(interrupted),
            "allocation_observed_before_interrupt": bool(
                results.get("interrupt_observed_allocation", False)
            ),
            "fixture": results.get("fixture"),
            "elapsed_seconds": round(elapsed, 3),
            "managed_bin_after_interrupt": len(_managed_files(backing_root, "bin")),
            "managed_json_after_interrupt": len(_managed_files(backing_root, "json")),
            "resources": resources,
            "work_root": str(work_root),
        }
        if not interrupted or not result["allocation_observed_before_interrupt"]:
            raise ProbeFailure(f"post-allocation interrupt was not proven: {result}")
        (work_root / "p25_interrupt_result.json").write_text(
            json.dumps(result, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return result
    if not executor.success or _has_event(executor, "execution_error"):
        raise ProbeFailure(f"{args.backend} PromptExecutor failed")
    if "digest" not in results or "fixture" not in results:
        raise ProbeFailure(f"{args.backend} probe outputs were not captured")

    bin_files = _managed_files(backing_root, "bin")
    json_files = _managed_files(backing_root, "json")
    resources.update(
        {
            "elapsed_seconds": round(elapsed, 3),
            "cuda_peak_allocated_bytes": (
                int(torch.cuda.max_memory_allocated()) if torch.cuda.is_available() else 0
            ),
            "cuda_peak_reserved_bytes": (
                int(torch.cuda.max_memory_reserved()) if torch.cuda.is_available() else 0
            ),
            "backing_bin_count_while_cached": len(bin_files),
            "backing_json_count_while_cached": len(json_files),
            "backing_bytes_while_cached": sum(item.stat().st_size for item in bin_files),
            "pre_digest_memory": results.get("pre_digest_memory"),
        }
    )
    downstream = _downstream_result(executor.history_result) if args.downstream else None
    executor.execute(_clear_prompt(), "p25-clear", extra_data={}, execute_outputs=["9"])
    del executor
    _collect_until_empty(manager, backing_root)
    resources["managed_bin_after_cache_release"] = len(
        _managed_files(backing_root, "bin")
    )
    resources["managed_json_after_cache_release"] = len(
        _managed_files(backing_root, "json")
    )
    resources["nonmanaged_root_entries_after_cache_release"] = len(
        [
            item
            for item in backing_root.iterdir()
            if item.name != ".h3c-p20.lock"
        ]
    )
    result = {
        "backend": args.backend,
        "status": "PASS",
        "fixture": results["fixture"],
        "stress": results.get("stress"),
        "digest": results["digest"],
        "resources": resources,
        "cache_requeue": cache_requeue,
        "downstream": downstream,
        "work_root": str(work_root),
    }
    (work_root / "p25_backend_result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return result


def _last_json(stdout: str) -> dict[str, Any]:
    marker = "P25_RESULT_JSON="
    line = next(
        (value for value in reversed(stdout.splitlines()) if value.startswith(marker)),
        "",
    )
    if not line:
        raise ProbeFailure("backend child did not emit a result marker")
    return json.loads(line[len(marker) :])


def _summarize_results(work_root: Path, results: dict[str, Any] | None = None):
    work_root = work_root.resolve()
    if results is None:
        results = {
            "RAM": json.loads(
                (work_root / "ram" / "p25_backend_result.json").read_text(
                    encoding="utf-8"
                )
            ),
            "Disk-backed": json.loads(
                (work_root / "disk" / "p25_backend_result.json").read_text(
                    encoding="utf-8"
                )
            ),
        }
    ram = results["RAM"]
    disk = results["Disk-backed"]
    disk_backing_root = (
        work_root / "disk" / "temp" / "h3-continuum-v35-file-backed"
    )
    managed_bin_after = len(_managed_files(disk_backing_root, "bin"))
    managed_json_after = len(_managed_files(disk_backing_root, "json"))
    disk["resources"]["managed_bin_after_cache_release"] = managed_bin_after
    disk["resources"]["managed_json_after_cache_release"] = managed_json_after
    comparisons = {
        "fixture_equal": ram["fixture"] == disk["fixture"],
        "video_shape_equal": ram["digest"]["video_shape"] == disk["digest"]["video_shape"],
        "video_sha256_equal": ram["digest"]["video_sha256"] == disk["digest"]["video_sha256"],
        "audio_shape_equal": ram["digest"]["audio_shape"] == disk["digest"]["audio_shape"],
        "audio_sha256_equal": ram["digest"]["audio_sha256"] == disk["digest"]["audio_sha256"],
        "audio_sample_rate_equal": ram["digest"]["audio_sample_rate"] == disk["digest"]["audio_sample_rate"],
        "both_finite": bool(
            ram["digest"]["video_finite"]
            and disk["digest"]["video_finite"]
            and ram["digest"]["audio_finite"]
            and disk["digest"]["audio_finite"]
        ),
        "disk_backing_reclaimed": managed_bin_after == 0 and managed_json_after == 0,
    }
    if not all(comparisons.values()):
        raise ProbeFailure(f"RAM/Disk-backed comparison failed: {comparisons}")
    peak_delta = (
        int(ram["resources"]["peak_rss_bytes"])
        - int(disk["resources"]["peak_rss_bytes"])
    )
    result = {
        "phase": "P2-5",
        "stage": "small-long-terminal-ab",
        "status": "PASS",
        "gpu_used": True,
        "comparisons": comparisons,
        "rss_peak_reduction_bytes": peak_delta,
        "rss_peak_reduction_percent": round(
            peak_delta / max(1, int(ram["resources"]["peak_rss_bytes"])) * 100.0,
            3,
        ),
        "backends": results,
        "work_root": str(work_root),
    }
    (work_root / "p25_result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return result


def _run_parent(args, package_root: Path) -> dict[str, Any]:
    work_root = args.work_root.resolve()
    work_root.mkdir(parents=True, exist_ok=True)
    common = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--comfy-root",
        str(args.comfy_root),
        "--package-root",
        str(package_root),
        "--revision-root",
        str(args.revision_root),
    ]
    results = {}
    for backend, folder in (("RAM", "ram"), ("Disk-backed", "disk")):
        child = subprocess.run(
            [*common, "--work-root", str(work_root / folder), "--backend", backend],
            check=True,
            capture_output=True,
            text=True,
        )
        (work_root / f"{folder}_stdout.txt").write_text(child.stdout, encoding="utf-8")
        (work_root / f"{folder}_stderr.txt").write_text(child.stderr, encoding="utf-8")
        results[backend] = _last_json(child.stdout)
    return _summarize_results(work_root, results)


def _parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comfy-root", type=Path, required=True)
    parser.add_argument("--package-root", type=Path)
    parser.add_argument("--revision-root", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--backend", choices=("Auto", "RAM", "Disk-backed"))
    parser.add_argument("--summarize-existing", action="store_true")
    parser.add_argument("--downstream", action="store_true")
    parser.add_argument("--interrupt-after-allocation", action="store_true")
    parser.add_argument("--cache-requeue", action="store_true")
    parser.add_argument(
        "--stress-size",
        type=int,
        default=0,
        help="Use a synthetic decoded square fixture of this size; 1536 is 9.49 GiB.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    args.comfy_root = args.comfy_root.resolve()
    args.revision_root = args.revision_root.resolve()
    args.work_root = args.work_root.resolve()
    package_root = (
        args.package_root.resolve()
        if args.package_root is not None
        else Path(__file__).resolve().parents[1]
    )
    if args.backend is not None:
        result = _run_backend(args, package_root)
        print("P25_RESULT_JSON=" + json.dumps(result, sort_keys=True))
        return 0
    if args.summarize_existing:
        result = _summarize_results(args.work_root)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    result = _run_parent(args, package_root)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
