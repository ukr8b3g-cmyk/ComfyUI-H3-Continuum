"""Assembly-plan contract for latent-first H3 Continuum V3."""

from __future__ import annotations

from typing import Any

import torch

from ..state import validate_plan

ASSEMBLY_PLAN_MAGIC = "H3_CONTINUUM_ASSEMBLY_PLAN"
ASSEMBLY_PLAN_SCHEMA_VERSION = 1
FPS = 24


class AssemblyPlanError(ValueError):
    pass


def make_assembly_plan(
    entries: list[dict[str, Any]],
    *,
    chunk_seconds: float,
    preserve_final_frame: bool,
) -> dict[str, Any]:
    if not entries:
        raise AssemblyPlanError("cannot create an assembly plan for an empty sequence")

    chunks: list[dict[str, Any]] = []
    width = height = None
    for sequence_index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise AssemblyPlanError(f"chunk {sequence_index} entry is not a dictionary")
        plan = validate_plan(entry.get("plan"))
        video = entry.get("video")
        audio = entry.get("audio")
        if not torch.is_tensor(video) or video.ndim < 3:
            raise AssemblyPlanError(f"chunk {sequence_index} video latent is invalid")
        if not torch.is_tensor(audio) or audio.ndim < 3:
            raise AssemblyPlanError(f"chunk {sequence_index} audio latent is invalid")

        plan_width = int(plan["width"])
        plan_height = int(plan["height"])
        if width is None:
            width, height = plan_width, plan_height
        elif (plan_width, plan_height) != (width, height):
            raise AssemblyPlanError("chunk dimensions changed within the sequence")

        chunks.append(
            {
                "sequence_index": sequence_index,
                "chunk_index": int(plan["clip_index"]),
                "total_frames": int(plan["total_frames"]),
                "trim_frames": int(plan["trim_frames"]),
                "net_frames": int(plan["net_frames"]),
                "context_frames": int(plan["context_frames"]),
                "expected_video_latent_t": int(video.shape[2]),
                "expected_audio_latent_t": int(audio.shape[-1]),
            }
        )

    result = {
        "magic": ASSEMBLY_PLAN_MAGIC,
        "schema_version": ASSEMBLY_PLAN_SCHEMA_VERSION,
        "fps": FPS,
        "width": int(width),
        "height": int(height),
        "chunk_seconds": float(chunk_seconds),
        "target_frames": int(round(len(chunks) * float(chunk_seconds) * FPS)),
        "preserve_final_frame": bool(preserve_final_frame),
        "chunks": chunks,
    }
    return validate_assembly_plan(result)


def validate_assembly_plan(plan: Any) -> dict[str, Any]:
    if not isinstance(plan, dict) or plan.get("magic") != ASSEMBLY_PLAN_MAGIC:
        raise AssemblyPlanError("invalid H3 Continuum V3 assembly plan")
    if (
        type(plan.get("schema_version")) is not int
        or plan["schema_version"] != ASSEMBLY_PLAN_SCHEMA_VERSION
    ):
        raise AssemblyPlanError(
            f"unsupported assembly plan schema {plan.get('schema_version')!r}"
        )
    if int(plan.get("fps", 0)) != FPS:
        raise AssemblyPlanError("assembly plan FPS must be 24")
    if int(plan.get("width", 0)) <= 0 or int(plan.get("height", 0)) <= 0:
        raise AssemblyPlanError("assembly plan dimensions are invalid")
    if float(plan.get("chunk_seconds", 0.0)) <= 0:
        raise AssemblyPlanError("assembly plan chunk duration is invalid")
    if int(plan.get("target_frames", 0)) <= 0:
        raise AssemblyPlanError("assembly plan target frame count is invalid")

    chunks = plan.get("chunks")
    if not isinstance(chunks, list) or not chunks:
        raise AssemblyPlanError("assembly plan contains no chunks")
    for expected_index, chunk in enumerate(chunks, start=1):
        if not isinstance(chunk, dict):
            raise AssemblyPlanError(f"assembly chunk {expected_index} is invalid")
        if int(chunk.get("sequence_index", 0)) != expected_index:
            raise AssemblyPlanError("assembly chunk order is not contiguous")
        total = int(chunk.get("total_frames", 0))
        trim = int(chunk.get("trim_frames", -1))
        net = int(chunk.get("net_frames", 0))
        if total <= 0 or trim < 0 or net <= 0 or total - trim != net:
            raise AssemblyPlanError(
                f"assembly chunk {expected_index} frame plan is invalid"
            )
        if int(chunk.get("context_frames", -1)) < 0:
            raise AssemblyPlanError(
                f"assembly chunk {expected_index} context is invalid"
            )
        if int(chunk.get("expected_video_latent_t", 0)) <= 0:
            raise AssemblyPlanError(
                f"assembly chunk {expected_index} video latent length is invalid"
            )
        if int(chunk.get("expected_audio_latent_t", 0)) <= 0:
            raise AssemblyPlanError(
                f"assembly chunk {expected_index} audio latent length is invalid"
            )
    return plan
# V3.0.1 hardening integration: redundant metadata plus fail-closed validation.
from ..hardening import (
    enrich_assembly_plan as _enrich_assembly_plan,
    validate_assembly_plan_contract as _validate_assembly_plan_contract,
)

_make_assembly_plan_v300 = make_assembly_plan
_validate_assembly_plan_v300 = validate_assembly_plan


def validate_assembly_plan(plan):
    result = _validate_assembly_plan_v300(plan)
    _validate_assembly_plan_contract(plan)
    return result


def make_assembly_plan(*args, **kwargs):
    plan = _make_assembly_plan_v300(*args, **kwargs)
    _enrich_assembly_plan(plan)
    validate_assembly_plan(plan)
    return plan


def _recombine_terminal_tensor(
    first,
    second,
    *,
    slices,
    time_dim: int,
    name: str,
):
    """Invert the terminal logical split without changing any tensor value."""

    import torch

    if not torch.is_tensor(first) or not torch.is_tensor(second):
        raise ValueError(f"terminal {name} entries must be tensors")
    if first.ndim != second.ndim:
        raise ValueError(f"terminal {name} tensor ranks differ")
    dim = int(time_dim)
    if dim < 0:
        dim += first.ndim
    if dim < 0 or dim >= first.ndim:
        raise ValueError(f"terminal {name} time dimension is invalid")
    for axis, (left, right) in enumerate(zip(first.shape, second.shape)):
        if axis != dim and int(left) != int(right):
            raise ValueError(f"terminal {name} tensor geometry differs")

    (first_start, first_stop), (second_start, second_stop) = slices
    first_start = int(first_start)
    first_stop = int(first_stop)
    second_start = int(second_start)
    second_stop = int(second_stop)
    if first_start != 0 or second_start > first_stop or second_stop <= first_stop:
        raise ValueError(f"terminal {name} split ranges do not form one physical unit")
    if int(first.shape[dim]) != first_stop - first_start:
        raise ValueError(f"terminal {name} first slice length is inconsistent")
    if int(second.shape[dim]) != second_stop - second_start:
        raise ValueError(f"terminal {name} second slice length is inconsistent")

    overlap_start = max(first_start, second_start)
    overlap_stop = min(first_stop, second_stop)
    overlap_length = max(0, overlap_stop - overlap_start)
    if overlap_length:
        first_overlap = first.narrow(dim, overlap_start - first_start, overlap_length)
        second_overlap = second.narrow(dim, overlap_start - second_start, overlap_length)
        if not torch.equal(first_overlap, second_overlap):
            raise ValueError(
                f"terminal {name} overlap differs; refusing lossy physical reconstruction"
            )

    output_shape = list(first.shape)
    output_shape[dim] = second_stop
    output = first.new_empty(output_shape)
    output.narrow(dim, first_start, first_stop - first_start).copy_(first)
    output.narrow(dim, second_start, second_stop - second_start).copy_(second)
    return output.contiguous()


def prepare_physical_decode_entries(
    entries,
    *,
    chunk_seconds: float,
    preserve_final_frame: bool,
    terminal_merged: bool,
):
    """Return external-VAE decode units while preserving logical plan metadata."""

    logical_entries = list(entries)
    plan = make_assembly_plan(
        logical_entries,
        chunk_seconds=float(chunk_seconds),
        preserve_final_frame=bool(preserve_final_frame),
    )
    if not terminal_merged:
        return logical_entries, plan
    if len(logical_entries) < 2:
        raise ValueError("terminal physical decode requires two logical entries")

    from ..v2.sequence import _terminal_pair_contract

    initial_pair = len(logical_entries) == 2
    contract = _terminal_pair_contract(
        initial_pair=initial_pair,
        chunk_seconds=float(chunk_seconds),
    )
    first_entry = logical_entries[-2]
    second_entry = logical_entries[-1]
    physical_video = _recombine_terminal_tensor(
        first_entry["video"],
        second_entry["video"],
        slices=contract["video_slices"],
        time_dim=2,
        name="video",
    )
    physical_audio = _recombine_terminal_tensor(
        first_entry["audio"],
        second_entry["audio"],
        slices=contract["audio_slices"],
        time_dim=-1,
        name="audio",
    )

    physical_entry = dict(first_entry)
    physical_entry["video"] = physical_video
    physical_entry["audio"] = physical_audio
    decode_entries = [*logical_entries[:-2], physical_entry]

    logical_chunks = list(plan["chunks"])
    decode_groups = []
    for chunk in logical_chunks[:-2]:
        group = dict(chunk)
        group["logical_chunk_indices"] = [int(chunk["chunk_index"])]
        group["terminal_merged"] = False
        decode_groups.append(group)

    first_chunk = logical_chunks[-2]
    second_chunk = logical_chunks[-1]
    frame_start = int(first_chunk.get("frame_start", 0))
    net_frames = int(contract["physical_frames"]) - int(
        contract["physical_context_frames"]
    )
    terminal_group = dict(first_chunk)
    terminal_group.update(
        {
            "total_frames": int(contract["physical_frames"]),
            "trim_frames": int(contract["physical_context_frames"]),
            "net_frames": net_frames,
            "context_frames": int(contract["physical_context_frames"]),
            "expected_video_latent_t": int(physical_video.shape[2]),
            "expected_audio_latent_t": int(physical_audio.shape[-1]),
            "frame_start": frame_start,
            "frame_stop": frame_start + net_frames,
            "logical_chunk_indices": [
                int(first_chunk["chunk_index"]),
                int(second_chunk["chunk_index"]),
            ],
            "terminal_merged": True,
        }
    )
    decode_groups.append(terminal_group)

    plan = dict(plan)
    plan["decode_group_version"] = 1
    plan["logical_chunk_count"] = len(logical_chunks)
    plan["physical_decode_group_count"] = len(decode_groups)
    plan["decode_groups"] = decode_groups
    validate_assembly_plan(plan)
    return decode_entries, plan
