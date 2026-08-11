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
                "expected_audio_latent_t": int(audio.shape[2]),
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
