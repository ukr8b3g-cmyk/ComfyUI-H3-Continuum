"""V3.0.x validation and diagnostics that do not alter generation semantics."""

from __future__ import annotations

import inspect
import math
from collections.abc import Mapping
from typing import Any

import torch


_MIB = 1024.0 * 1024.0


def _strict_int(name: str, value: Any, minimum: int | None = None) -> int:
    if type(value) is not int:
        raise ValueError(f"{name} must be an integer")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


def _assembly_decode_units(plan: Mapping[str, Any]) -> list[Any]:
    if "decode_groups" not in plan:
        return plan["chunks"]
    groups = plan["decode_groups"]
    if not isinstance(groups, list) or not groups:
        raise ValueError("assembly_plan.decode_groups must be a non-empty list")
    return groups


def enrich_assembly_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Add redundant metadata without correcting any existing value."""
    chunks = plan.get("chunks")
    if not isinstance(chunks, list) or not chunks:
        return plan

    cursor = 0
    for chunk in chunks:
        if not isinstance(chunk, dict):
            return plan
        net_frames = chunk.get("net_frames")
        if type(net_frames) is not int:
            return plan
        chunk.setdefault("frame_start", cursor)
        chunk.setdefault("frame_stop", cursor + net_frames)
        cursor += net_frames

    plan.setdefault("chunk_count", len(chunks))
    plan.setdefault("natural_frames", cursor)
    return plan


def validate_assembly_plan_contract(plan: Mapping[str, Any]) -> None:
    """Fail closed on contradictions while accepting valid legacy schema-1 plans."""
    if not isinstance(plan, Mapping):
        raise ValueError("assembly_plan must be a mapping")

    chunks = plan.get("chunks")
    if not isinstance(chunks, list) or not chunks:
        raise ValueError("assembly_plan.chunks must be a non-empty list")

    width = _strict_int("assembly_plan.width", plan.get("width"), 1)
    height = _strict_int("assembly_plan.height", plan.get("height"), 1)
    if width <= 0 or height <= 0:
        raise ValueError("assembly_plan dimensions must be positive")

    fps = plan.get("fps")
    if not isinstance(fps, (int, float)) or isinstance(fps, bool):
        raise ValueError("assembly_plan.fps must be numeric")
    fps = float(fps)
    if not math.isfinite(fps) or fps <= 0:
        raise ValueError("assembly_plan.fps must be finite and positive")

    chunk_seconds = plan.get("chunk_seconds")
    if not isinstance(chunk_seconds, (int, float)) or isinstance(chunk_seconds, bool):
        raise ValueError("assembly_plan.chunk_seconds must be numeric")
    chunk_seconds = float(chunk_seconds)
    if not math.isfinite(chunk_seconds) or chunk_seconds <= 0:
        raise ValueError("assembly_plan.chunk_seconds must be finite and positive")

    target_frames = _strict_int("assembly_plan.target_frames", plan.get("target_frames"), 1)
    expected_target = int(round(len(chunks) * chunk_seconds * fps))
    if target_frames != expected_target:
        raise ValueError(
            "assembly_plan.target_frames does not match chunks * chunk_seconds * fps"
        )

    if "chunk_count" in plan:
        chunk_count = _strict_int("assembly_plan.chunk_count", plan["chunk_count"], 1)
        if chunk_count != len(chunks):
            raise ValueError("assembly_plan.chunk_count does not match chunks")

    if "preserve_final_frame" in plan and type(plan["preserve_final_frame"]) is not bool:
        raise ValueError("assembly_plan.preserve_final_frame must be a boolean")

    natural_frames = 0
    previous_sequence_index: int | None = None
    previous_chunk_index: int | None = None

    for position, chunk in enumerate(chunks, start=1):
        if not isinstance(chunk, Mapping):
            raise ValueError(f"assembly_plan chunk {position} must be a mapping")

        sequence_index = _strict_int(
            f"assembly_plan chunk {position}.sequence_index",
            chunk.get("sequence_index"),
            0,
        )
        chunk_index = _strict_int(
            f"assembly_plan chunk {position}.chunk_index",
            chunk.get("chunk_index"),
            1,
        )
        if previous_sequence_index is not None and sequence_index != previous_sequence_index + 1:
            raise ValueError("assembly_plan sequence_index values must be contiguous")
        if previous_chunk_index is not None and chunk_index != previous_chunk_index + 1:
            raise ValueError("assembly_plan chunk_index values must be contiguous")
        previous_sequence_index = sequence_index
        previous_chunk_index = chunk_index

        total_frames = _strict_int(
            f"assembly_plan chunk {position}.total_frames",
            chunk.get("total_frames"),
            5,
        )
        trim_frames = _strict_int(
            f"assembly_plan chunk {position}.trim_frames",
            chunk.get("trim_frames"),
            0,
        )
        net_frames = _strict_int(
            f"assembly_plan chunk {position}.net_frames",
            chunk.get("net_frames"),
            1,
        )
        context_frames = _strict_int(
            f"assembly_plan chunk {position}.context_frames",
            chunk.get("context_frames"),
            0,
        )
        expected_video_t = _strict_int(
            f"assembly_plan chunk {position}.expected_video_latent_t",
            chunk.get("expected_video_latent_t"),
            1,
        )
        expected_audio_t = _strict_int(
            f"assembly_plan chunk {position}.expected_audio_latent_t",
            chunk.get("expected_audio_latent_t"),
            1,
        )

        if (total_frames - 5) % 17 != 0:
            raise ValueError(
                f"assembly_plan chunk {position}.total_frames is not on the H3 17k+5 grid"
            )
        if total_frames - trim_frames != net_frames:
            raise ValueError(
                f"assembly_plan chunk {position}: total_frames - trim_frames != net_frames"
            )
        if trim_frames > 0 and context_frames != trim_frames:
            raise ValueError(
                f"assembly_plan chunk {position}: continuation context and trim differ"
            )
        if expected_video_t <= 0 or expected_audio_t <= 0:
            raise ValueError(f"assembly_plan chunk {position}: latent lengths must be positive")

        if "frame_start" in chunk or "frame_stop" in chunk:
            frame_start = _strict_int(
                f"assembly_plan chunk {position}.frame_start",
                chunk.get("frame_start"),
                0,
            )
            frame_stop = _strict_int(
                f"assembly_plan chunk {position}.frame_stop",
                chunk.get("frame_stop"),
                1,
            )
            if frame_start != natural_frames or frame_stop != natural_frames + net_frames:
                raise ValueError(
                    f"assembly_plan chunk {position}: natural frame boundary is discontinuous"
                )

        natural_frames += net_frames

    if "natural_frames" in plan:
        recorded_natural = _strict_int(
            "assembly_plan.natural_frames", plan["natural_frames"], 1
        )
        if recorded_natural != natural_frames:
            raise ValueError(
                "sum(chunk.net_frames) does not match assembly_plan.natural_frames"
            )

    if "decode_groups" in plan:
        decode_groups = _assembly_decode_units(plan)
        if "physical_decode_group_count" in plan:
            group_count = _strict_int(
                "assembly_plan.physical_decode_group_count",
                plan["physical_decode_group_count"],
                1,
            )
            if group_count != len(decode_groups):
                raise ValueError(
                    "assembly_plan.physical_decode_group_count does not match decode_groups"
                )
        expected_logical_indices = [int(chunk["chunk_index"]) for chunk in chunks]
        covered_logical_indices: list[int] = []
        decode_natural_frames = 0
        for position, group in enumerate(decode_groups, start=1):
            if not isinstance(group, Mapping):
                raise ValueError(
                    f"assembly_plan decode group {position} must be a mapping"
                )
            total_frames = _strict_int(
                f"assembly_plan decode group {position}.total_frames",
                group.get("total_frames"),
                5,
            )
            trim_frames = _strict_int(
                f"assembly_plan decode group {position}.trim_frames",
                group.get("trim_frames"),
                0,
            )
            net_frames = _strict_int(
                f"assembly_plan decode group {position}.net_frames",
                group.get("net_frames"),
                1,
            )
            context_frames = _strict_int(
                f"assembly_plan decode group {position}.context_frames",
                group.get("context_frames"),
                0,
            )
            _strict_int(
                f"assembly_plan decode group {position}.expected_video_latent_t",
                group.get("expected_video_latent_t"),
                1,
            )
            _strict_int(
                f"assembly_plan decode group {position}.expected_audio_latent_t",
                group.get("expected_audio_latent_t"),
                1,
            )
            if (total_frames - 5) % 17 != 0:
                raise ValueError(
                    f"assembly_plan decode group {position}.total_frames is not on "
                    "the H3 17k+5 grid"
                )
            if total_frames - trim_frames != net_frames:
                raise ValueError(
                    f"assembly_plan decode group {position}: "
                    "total_frames - trim_frames != net_frames"
                )
            if trim_frames > 0 and context_frames != trim_frames:
                raise ValueError(
                    f"assembly_plan decode group {position}: "
                    "continuation context and trim differ"
                )
            logical_indices = group.get("logical_chunk_indices")
            if not isinstance(logical_indices, list) or not logical_indices:
                raise ValueError(
                    f"assembly_plan decode group {position}.logical_chunk_indices "
                    "must be a non-empty list"
                )
            covered_logical_indices.extend(
                _strict_int(
                    f"assembly_plan decode group {position}.logical_chunk_indices",
                    value,
                    1,
                )
                for value in logical_indices
            )
            if "terminal_merged" in group and type(group["terminal_merged"]) is not bool:
                raise ValueError(
                    f"assembly_plan decode group {position}.terminal_merged must be boolean"
                )
            frame_start = _strict_int(
                f"assembly_plan decode group {position}.frame_start",
                group.get("frame_start"),
                0,
            )
            frame_stop = _strict_int(
                f"assembly_plan decode group {position}.frame_stop",
                group.get("frame_stop"),
                1,
            )
            if (
                frame_start != decode_natural_frames
                or frame_stop != decode_natural_frames + net_frames
            ):
                raise ValueError(
                    f"assembly_plan decode group {position}: natural frame boundary "
                    "is discontinuous"
                )
            decode_natural_frames += net_frames
        if covered_logical_indices != expected_logical_indices:
            raise ValueError(
                "assembly_plan.decode_groups do not cover logical chunks exactly once"
            )
        if decode_natural_frames != natural_frames:
            raise ValueError(
                "sum(decode_group.net_frames) does not match logical natural frames"
            )


def preflight_decoded_chunks(
    images: Any,
    audio: Any,
    plan: Mapping[str, Any],
) -> None:
    """Validate all decoded chunks before the assembler allocates output buffers."""
    validate_assembly_plan_contract(plan)
    chunks = _assembly_decode_units(plan)

    if not isinstance(images, (list, tuple)):
        raise ValueError("decoded images must be a chunk list")
    if not isinstance(audio, (list, tuple)):
        raise ValueError("decoded audio must be a chunk list")
    if len(images) != len(chunks) or len(audio) != len(chunks):
        raise ValueError("decoded chunk counts do not match assembly_plan")

    image_signature: tuple[Any, ...] | None = None
    audio_signature: tuple[Any, ...] | None = None
    sample_rate: int | None = None

    for position, (image, audio_item, chunk) in enumerate(
        zip(images, audio, chunks), start=1
    ):
        if not torch.is_tensor(image) or image.ndim != 4:
            raise ValueError(f"decoded image chunk {position} must be a 4D tensor")
        total_frames = int(chunk["total_frames"])
        if int(image.shape[0]) < total_frames:
            raise ValueError(
                f"decoded image chunk {position} has fewer frames than assembly_plan"
            )

        current_image_signature = (
            int(image.shape[1]),
            int(image.shape[2]),
            int(image.shape[3]),
            image.dtype,
        )
        if image_signature is None:
            image_signature = current_image_signature
        elif current_image_signature != image_signature:
            raise ValueError("decoded image chunk geometry or dtype changed")

        if not isinstance(audio_item, Mapping):
            raise ValueError(f"decoded audio chunk {position} must be an AUDIO mapping")
        waveform = audio_item.get("waveform")
        current_rate = audio_item.get("sample_rate")
        if not torch.is_tensor(waveform) or waveform.ndim != 3:
            raise ValueError(
                f"decoded audio chunk {position}.waveform must be a 3D tensor"
            )
        if type(current_rate) is not int or current_rate <= 0:
            raise ValueError(
                f"decoded audio chunk {position}.sample_rate must be positive"
            )
        if int(waveform.shape[-1]) <= 0:
            raise ValueError(f"decoded audio chunk {position} is empty")

        current_audio_signature = (
            int(waveform.shape[0]),
            int(waveform.shape[1]),
            waveform.dtype,
        )
        if audio_signature is None:
            audio_signature = current_audio_signature
            sample_rate = current_rate
        elif current_audio_signature != audio_signature:
            raise ValueError("decoded audio chunk batch, channels, or dtype changed")
        if current_rate != sample_rate:
            raise ValueError("decoded audio sample_rate changed between chunks")


def _iter_tensors(value: Any, seen_containers: set[int] | None = None):
    if seen_containers is None:
        seen_containers = set()

    if torch.is_tensor(value):
        if bool(getattr(value, "is_nested", False)):
            try:
                for item in value.unbind():
                    yield from _iter_tensors(item, seen_containers)
                return
            except Exception:
                pass
        yield value
        return

    if isinstance(value, Mapping):
        identity = id(value)
        if identity in seen_containers:
            return
        seen_containers.add(identity)
        for item in value.values():
            yield from _iter_tensors(item, seen_containers)
        return

    if isinstance(value, (list, tuple, set)):
        identity = id(value)
        if identity in seen_containers:
            return
        seen_containers.add(identity)
        for item in value:
            yield from _iter_tensors(item, seen_containers)


def _storage_key(tensor: torch.Tensor) -> tuple[Any, ...]:
    device = (tensor.device.type, tensor.device.index)
    try:
        storage = tensor.untyped_storage()
        pointer = int(storage.data_ptr())
        byte_count = int(storage.nbytes())
    except Exception:
        pointer = int(tensor.data_ptr()) if tensor.numel() else 0
        byte_count = int(tensor.numel() * tensor.element_size())
    if pointer == 0:
        return device + ("empty", id(tensor), byte_count)
    return device + (pointer, byte_count)


def tensor_storage_stats(*values: Any) -> dict[str, Any]:
    references = 0
    storages: dict[tuple[Any, ...], tuple[int, str]] = {}
    for value in values:
        for tensor in _iter_tensors(value):
            references += 1
            key = _storage_key(tensor)
            storages.setdefault(key, (int(key[-1]), tensor.device.type))

    cpu_bytes = sum(size for size, device in storages.values() if device == "cpu")
    gpu_bytes = sum(size for size, device in storages.values() if device != "cpu")
    return {
        "references": references,
        "unique_storages": len(storages),
        "cpu_bytes": cpu_bytes,
        "gpu_bytes": gpu_bytes,
        "all_cpu": all(device == "cpu" for _, device in storages.values()),
        "keys": frozenset(storages),
    }


def _mib(value: int | None) -> str:
    if value is None:
        return "n/a"
    return f"{value / _MIB:.1f} MiB"


def format_memory_snapshot(label: str, *values: Any) -> str:
    """Capture non-synchronizing process/system/CUDA counters for Detailed Report."""
    rss: int | None = None
    available: int | None = None
    try:
        import psutil

        rss = int(psutil.Process().memory_info().rss)
        available = int(psutil.virtual_memory().available)
    except Exception:
        pass

    cuda_allocated: int | None = None
    cuda_reserved: int | None = None
    cuda_free: int | None = None
    try:
        if torch.cuda.is_available():
            cuda_allocated = int(torch.cuda.memory_allocated())
            cuda_reserved = int(torch.cuda.memory_reserved())
            cuda_free = int(torch.cuda.mem_get_info()[0])
    except Exception:
        pass

    stats = tensor_storage_stats(*values)
    return (
        f"Memory [{label}]: RSS={_mib(rss)}, system_available={_mib(available)}, "
        f"CUDA_allocated={_mib(cuda_allocated)}, CUDA_reserved={_mib(cuda_reserved)}, "
        f"CUDA_free={_mib(cuda_free)}, tensor_refs={stats['references']}, "
        f"unique_storage={stats['unique_storages']}, "
        f"CPU_storage={_mib(stats['cpu_bytes'])}, GPU_storage={_mib(stats['gpu_bytes'])}"
    )


def format_latent_storage_audit(entries: Any, session: Any) -> str:
    entry_values: list[Any] = []
    if isinstance(entries, (list, tuple)):
        for entry in entries:
            if isinstance(entry, Mapping):
                entry_values.extend((entry.get("video"), entry.get("audio")))

    session_values: list[Any] = []
    if isinstance(session, Mapping):
        session_chunks = session.get("chunks")
        if isinstance(session_chunks, (list, tuple)):
            for entry in session_chunks:
                if isinstance(entry, Mapping):
                    session_values.extend((entry.get("video"), entry.get("audio")))

    entry_stats = tensor_storage_stats(entry_values)
    session_stats = tensor_storage_stats(session_values)
    session_keys = session_stats["keys"]
    if not session_keys:
        shared = "n/a"
    else:
        shared = "yes" if session_keys.issubset(entry_stats["keys"]) else "no"

    return (
        "CPU latent storage audit: "
        f"entry_refs={entry_stats['references']}, "
        f"entry_unique={entry_stats['unique_storages']}, "
        f"entry_bytes={_mib(entry_stats['cpu_bytes'])}, "
        f"session_shared={shared}, "
        f"all_cpu={'yes' if entry_stats['all_cpu'] else 'no'}"
    )


def core_video_vae_chunked_io_status(video_vae: Any) -> str:
    first_stage_model = getattr(video_vae, "first_stage_model", None)
    if first_stage_model is None:
        return "Unknown"
    capability = getattr(first_stage_model, "comfy_has_chunked_io", None)
    if capability is True:
        return (
            "Supported"
            if callable(getattr(first_stage_model, "decode_output_shape", None))
            else "Unknown"
        )
    if capability is None or capability is False:
        return "Unsupported"
    return "Unknown"


def diagnostics_is_full(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.strip().lower()
    return "detailed" in normalized or normalized == "full"


def _bound_arguments(function: Any, args: tuple[Any, ...], kwargs: dict[str, Any]):
    try:
        return inspect.signature(function).bind_partial(*args, **kwargs).arguments
    except Exception:
        return {}


def _first_argument(arguments: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in arguments:
            return arguments[name]
    return None


def _append_report(result: Any, lines: list[str]) -> Any:
    if not lines:
        return result
    suffix = "\n".join(lines)

    if isinstance(result, tuple):
        items = list(result)
        for index in range(len(items) - 1, -1, -1):
            if isinstance(items[index], str):
                items[index] = items[index].rstrip() + "\n" + suffix
                return tuple(items)
        return result

    if isinstance(result, list):
        items = list(result)
        for index in range(len(items) - 1, -1, -1):
            if isinstance(items[index], str):
                items[index] = items[index].rstrip() + "\n" + suffix
                return items
        return result

    if isinstance(result, dict) and isinstance(result.get("report"), str):
        updated = dict(result)
        updated["report"] = updated["report"].rstrip() + "\n" + suffix
        return updated

    if isinstance(result, str):
        return result.rstrip() + "\n" + suffix
    return result


def run_sequence_with_hardening(base: Any, args: tuple[Any, ...], kwargs: dict[str, Any]):
    arguments = _bound_arguments(base, args, kwargs)
    latent_only = bool(_first_argument(arguments, "latent_only"))
    diagnostics = _first_argument(arguments, "diagnostics", "diagnostics_mode")
    if not latent_only or not diagnostics_is_full(diagnostics):
        return base(*args, **kwargs)

    video_vae = _first_argument(arguments, "video_vae")
    lines = [
        f"Core Video VAE chunked I/O: {core_video_vae_chunked_io_status(video_vae)}",
        format_memory_snapshot("sequence start"),
    ]
    result = base(*args, **kwargs)

    entries = result[0] if isinstance(result, (tuple, list)) and len(result) > 0 else None
    session = result[2] if isinstance(result, (tuple, list)) and len(result) > 2 else None
    lines.append(format_latent_storage_audit(entries, session))
    lines.append(format_memory_snapshot("sequence complete", entries, session))
    return _append_report(result, lines)


def assemble_with_hardening(base: Any, args: tuple[Any, ...], kwargs: dict[str, Any]):
    arguments = _bound_arguments(base, args, kwargs)
    plan = _first_argument(arguments, "assembly_plan", "plan")
    images = _first_argument(arguments, "images", "decoded_images")
    audio = _first_argument(arguments, "audio", "decoded_audio")

    if plan is None:
        for value in arguments.values():
            if isinstance(value, Mapping) and "chunks" in value and "target_frames" in value:
                plan = value
                break
    if images is None:
        for value in arguments.values():
            if isinstance(value, (list, tuple)) and value and torch.is_tensor(value[0]):
                images = value
                break
    if audio is None:
        for value in arguments.values():
            if (
                isinstance(value, (list, tuple))
                and value
                and isinstance(value[0], Mapping)
                and "waveform" in value[0]
            ):
                audio = value
                break

    preflight_decoded_chunks(images, audio, plan)

    diagnostics = _first_argument(arguments, "diagnostics", "diagnostics_mode")
    lines: list[str] = []
    if diagnostics_is_full(diagnostics):
        lines.append(format_memory_snapshot("assemble preflight", images, audio))
        natural_frames = sum(
            int(chunk["net_frames"]) for chunk in _assembly_decode_units(plan)
        )
        target_frames = int(plan["target_frames"])
        correction = target_frames - natural_frames
        if abs(correction) > 2:
            sign = "+" if correction > 0 else ""
            lines.append(
                f"Warning: Exact Duration requires {sign}{correction} trailing frames; "
                "existing tail trim/pad policy is unchanged."
            )

    result = base(*args, **kwargs)
    if diagnostics_is_full(diagnostics):
        lines.append(format_memory_snapshot("assemble complete", result))
    return _append_report(result, lines)
