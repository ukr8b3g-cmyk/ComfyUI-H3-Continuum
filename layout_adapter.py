"""Per-run H3 payload normalization and MM-RoPE timeline adaptation.

No ComfyUI class is monkey-patched. ComfyUI builds a normal H3 PackedLayout;
this module then changes only its coordinates in place. Keeping the same
``position_ids`` Tensor identity preserves Sol-Attn's native-H3 span registry.

The preferred Continuum representation is one native H3 ``video`` or
``video_audio`` reference block. Its latent rows are moved onto the beginning
of the target timeline. The older marked-keyframe form remains supported as an
internal compatibility path, but the UI does not emit it.
"""

from __future__ import annotations

import logging
from typing import Any

import torch

from .constants import (
    CONTINUUM_INTEROP_API,
    CONTINUUM_REFERENCE_METADATA_KEY,
    FRAME_RESCALE,
    LAYOUT_DEVICE_CACHE_ATTR,
    LAYOUT_ORIGINAL_TIME_ATTR,
    LAYOUT_SIGNATURE_ATTR,
    MARK_AUDIO_CONTEXT,
    MARK_AUDIO_END_FRAME,
    MARK_AUDIO_OVERHANG,
    MARK_CONTEXT_FRAMES,
    MARK_VIDEO_CONTEXT,
    MARK_VIDEO_SLOT,
)

LOG = logging.getLogger("h3_continuum_join")


class LayoutCompatibilityError(RuntimeError):
    pass


def _reference_metadata(ref: dict[str, Any]) -> dict[str, Any]:
    value = ref.get(CONTINUUM_REFERENCE_METADATA_KEY)
    return value if isinstance(value, dict) else {}


def _is_video_context(ref: dict[str, Any]) -> bool:
    return bool(
        ref.get(MARK_VIDEO_CONTEXT)
        or _reference_metadata(ref).get("role") == "video_context"
    )


def _is_audio_context(ref: dict[str, Any]) -> bool:
    metadata = _reference_metadata(ref)
    return bool(
        ref.get(MARK_AUDIO_CONTEXT)
        or metadata.get("role") == "audio_context"
        or metadata.get("audio_role") == "audio_context"
    )


def payload_has_continuum(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    keyframes = payload.get("keyframes") or ()
    refs = payload.get("refs") or ()
    return any(MARK_VIDEO_SLOT in item for item in keyframes) or any(
        _is_video_context(item) or _is_audio_context(item) for item in refs
    )


def normalize_condition_latents(payload: dict[str, Any]) -> None:
    """Keep keyframe rows first and reference rows second, matching PackedLayout."""
    keyframes = list(payload.get("keyframes") or ())
    refs = list(payload.get("refs") or ())
    video_latents = [item["latent"] for item in keyframes if item.get("latent") is not None]
    video_latents.extend(item["latent"] for item in refs if item.get("latent") is not None)
    audio_latents = [
        item["audio_latent"] for item in refs if item.get("audio_latent") is not None
    ]
    payload["cond_video_latents"] = video_latents
    payload["cond_audio_latents"] = audio_latents


def _input_device(x: Any) -> torch.device | None:
    device = getattr(x, "device", None)
    if isinstance(device, torch.device):
        return device
    if hasattr(x, "unbind"):
        try:
            parts = x.unbind()
            if parts:
                part_device = getattr(parts[0], "device", None)
                if isinstance(part_device, torch.device):
                    return part_device
        except Exception:
            return None
    return None


def materialize_continuum_latents(
    payload: dict[str, Any], x: Any, *, debug: bool = False,
) -> None:
    """Move only Continuum context tensors to the active device once per run.

    Native H3 intentionally keeps payload dictionaries outside BaseModel's
    generic dtype/device conversion. Without this cache, a CPU continuation
    state would be transferred again on every solver step. Existing user refs
    are left untouched to avoid unexpectedly pinning large Ref2VA inputs in
    VRAM.
    """
    layout = payload.get("layout")
    device = _input_device(x)
    if layout is None or device is None or device.type == "cpu":
        return

    keyframes = [dict(item) for item in (payload.get("keyframes") or ())]
    refs = [dict(item) for item in (payload.get("refs") or ())]
    marked_tensors: list[tuple[str, int, torch.Tensor]] = []
    for index, item in enumerate(keyframes):
        if MARK_VIDEO_SLOT in item and torch.is_tensor(item.get("latent")):
            marked_tensors.append(("keyframe", index, item["latent"]))
    for index, item in enumerate(refs):
        if _is_video_context(item) and torch.is_tensor(item.get("latent")):
            marked_tensors.append(("ref_video", index, item["latent"]))
        if _is_audio_context(item) and torch.is_tensor(item.get("audio_latent")):
            marked_tensors.append(("ref_audio", index, item["audio_latent"]))
    if not marked_tensors:
        return

    cache_key = (
        str(device),
        tuple(
            (kind, index, id(tensor), tuple(tensor.shape), str(tensor.dtype))
            for kind, index, tensor in marked_tensors
        ),
    )
    cached = getattr(layout, LAYOUT_DEVICE_CACHE_ATTR, None)
    if not isinstance(cached, dict) or cached.get("key") != cache_key:
        values: dict[tuple[str, int], torch.Tensor] = {}
        for kind, index, tensor in marked_tensors:
            values[(kind, index)] = tensor.to(
                device=device, dtype=torch.float32, non_blocking=True
            ).contiguous()
        cached = {"key": cache_key, "values": values}
        setattr(layout, LAYOUT_DEVICE_CACHE_ATTR, cached)
        if debug:
            total_bytes = sum(t.numel() * t.element_size() for t in values.values())
            LOG.info(
                "Continuum context cached on %s: %d tensors, %.2f MiB",
                device,
                len(values),
                total_bytes / (1024 * 1024),
            )

    values = cached["values"]
    for index, item in enumerate(keyframes):
        replacement = values.get(("keyframe", index))
        if replacement is not None:
            item["latent"] = replacement
    for index, item in enumerate(refs):
        replacement = values.get(("ref_video", index))
        if replacement is not None:
            item["latent"] = replacement
        replacement = values.get(("ref_audio", index))
        if replacement is not None:
            item["audio_latent"] = replacement
    payload["keyframes"] = keyframes
    payload["refs"] = refs


def _single_segment(layout: Any, kind: str) -> tuple[int, int]:
    matches = [(int(a), int(b)) for a, b, k in layout.segments if k == kind]
    if len(matches) != 1:
        raise LayoutCompatibilityError(f"expected one H3 '{kind}' segment, found {len(matches)}")
    return matches[0]


def _map_refs_to_segments(
    layout: Any, refs: list[dict[str, Any]],
) -> list[dict[str, tuple[int, int] | None]]:
    available = [
        (int(a), int(b), str(kind))
        for a, b, kind in layout.segments
        if kind in ("ref_img", "ref_audio")
    ]
    cursor = 0
    result: list[dict[str, tuple[int, int] | None]] = []

    def consume(expected: str) -> tuple[int, int]:
        nonlocal cursor
        if cursor >= len(available):
            raise LayoutCompatibilityError(f"layout ended while mapping '{expected}'")
        a, b, kind = available[cursor]
        cursor += 1
        if kind != expected:
            raise LayoutCompatibilityError(
                f"reference layout mismatch: expected '{expected}', found '{kind}'"
            )
        return a, b

    for ref in refs:
        kind = ref.get("kind")
        mapping: dict[str, tuple[int, int] | None] = {"audio": None, "video": None}
        if kind == "image":
            mapping["video"] = consume("ref_img")
        elif kind == "audio":
            if int(ref.get("ref_audio_t", 0)) > 0:
                mapping["audio"] = consume("ref_audio")
        elif kind in ("video", "video_audio"):
            if int(ref.get("ref_audio_t", 0)) > 0:
                mapping["audio"] = consume("ref_audio")
            mapping["video"] = consume("ref_img")
        else:
            raise LayoutCompatibilityError(f"unsupported H3 reference kind: {kind!r}")
        result.append(mapping)
    if cursor != len(available):
        raise LayoutCompatibilityError(
            f"layout contains {len(available)-cursor} unmapped reference segments"
        )
    return result


def _patch_signature(payload: dict[str, Any], layout: Any) -> tuple[Any, ...]:
    return (
        tuple(
            (
                int(kf.get("resolved_frame_index", -1)),
                int(kf.get(MARK_VIDEO_SLOT, -1)),
            )
            for kf in (payload.get("keyframes") or ())
        ),
        tuple(
            (
                bool(ref.get(MARK_VIDEO_CONTEXT)),
                tuple(sorted(_reference_metadata(ref).items())),
                int(ref.get("latent_t", 0)),
                int(ref.get(MARK_CONTEXT_FRAMES, 0)),
                bool(ref.get(MARK_AUDIO_CONTEXT)),
                int(ref.get("ref_audio_t", 0)),
                float(ref.get(MARK_AUDIO_END_FRAME, 0.0)),
                float(ref.get(MARK_AUDIO_OVERHANG, 0.0)),
            )
            for ref in (payload.get("refs") or ())
        ),
        tuple(getattr(layout, "signature", ())),
        tuple((int(a), int(b), str(k)) for a, b, k in layout.segments),
    )


def _branch_key(transformer_options: dict[str, Any]) -> tuple[Any, ...]:
    conds = transformer_options.get("cond_or_uncond")
    uuids = transformer_options.get("uuids")
    if conds is None or uuids is None:
        return ("default",)
    try:
        cond_values = tuple(int(value) for value in conds)
        uuid_values = tuple(str(value) for value in uuids)
    except (TypeError, ValueError):
        return ("default",)
    if not cond_values or len(cond_values) != len(uuid_values):
        return ("default",)
    return tuple(
        (cond_values[index], uuid_values[index])
        for index in range(len(cond_values))
    )


def _sampled_tensor_signature(tensor: torch.Tensor | None) -> tuple[Any, ...] | None:
    if tensor is None:
        return None
    value = tensor.detach().to(dtype=torch.float32)
    flat = value.reshape(-1)
    if flat.numel() <= 64:
        sample = flat
    else:
        indices = torch.linspace(
            0,
            flat.numel() - 1,
            64,
            dtype=torch.long,
            device=flat.device,
        )
        sample = flat.index_select(0, indices)
    sample = sample.to("cpu")
    finite = bool(torch.isfinite(sample).all().item())
    if not finite:
        raise LayoutCompatibilityError("Continuum layout/context contains NaN or Inf")
    weights = torch.arange(1, sample.numel() + 1, dtype=torch.float32)
    return (
        tuple(int(part) for part in tensor.shape),
        str(tensor.dtype),
        finite,
        float(sample.mean().item()),
        float(sample.std(unbiased=False).item()),
        float((sample * weights).sum().item()),
    )


def _ranges_overlap(left: tuple[int, int], right: tuple[int, int]) -> bool:
    return max(left[0], right[0]) < min(left[1], right[1])


def validate_native_continuity_layout(
    payload: dict[str, Any],
    *,
    transformer_options: dict[str, Any] | None,
    branch_baselines: dict[tuple[Any, ...], tuple[Any, ...]],
) -> dict[str, Any]:
    """Validate immutable native-H3 Context/Target topology per logical branch."""

    layout = payload.get("layout")
    if layout is None:
        raise LayoutCompatibilityError("Native Continuity payload has no PackedLayout")
    position_ids = getattr(layout, "position_ids", None)
    segments = tuple(
        (int(start), int(stop), str(kind))
        for start, stop, kind in getattr(layout, "segments", ())
    )
    if not torch.is_tensor(position_ids) or position_ids.ndim != 2:
        raise LayoutCompatibilityError("Native Continuity position_ids are unavailable")
    seq_len = int(getattr(layout, "seq_len", position_ids.shape[0]))
    if seq_len != int(position_ids.shape[0]):
        raise LayoutCompatibilityError("PackedLayout seq_len does not match position_ids")

    previous_stop = 0
    for start, stop, kind in segments:
        if start < previous_stop or stop <= start or stop > seq_len:
            raise LayoutCompatibilityError(
                f"PackedLayout segment {kind!r} has an overlapping or invalid row range"
            )
        previous_stop = stop

    target_audio = [(a, b) for a, b, kind in segments if kind == "audio"]
    target_video = [(a, b) for a, b, kind in segments if kind == "video"]
    if len(target_audio) != 1 or len(target_video) != 1:
        raise LayoutCompatibilityError(
            "Native Continuity requires one target audio and one target video segment"
        )
    audio_range, video_range = target_audio[0], target_video[0]
    if audio_range[1] != video_range[0] or video_range[1] != seq_len:
        raise LayoutCompatibilityError(
            "target segments must be the contiguous packed tail [audio | video]"
        )

    refs = list(payload.get("refs") or ())
    mappings = _map_refs_to_segments(layout, refs)
    context_ranges: list[tuple[int, int, str]] = []
    context_descriptors: list[tuple[Any, ...]] = []
    for ref, mapping in zip(refs, mappings):
        metadata = _reference_metadata(ref)
        if metadata:
            if (
                type(metadata.get("api")) is not int
                or int(metadata["api"]) != CONTINUUM_INTEROP_API
            ):
                raise LayoutCompatibilityError("unsupported Continuum reference metadata")
            if _is_video_context(ref) and metadata.get("role") != "video_context":
                raise LayoutCompatibilityError("Continuum video reference role is invalid")
            if _is_audio_context(ref) and metadata.get("audio_role") not in (
                None,
                "audio_context",
            ):
                raise LayoutCompatibilityError("Continuum audio reference role is invalid")

        if _is_video_context(ref):
            row_range = mapping.get("video")
            if row_range is None:
                raise LayoutCompatibilityError("Continuum video context has no reference rows")
            context_ranges.append((*row_range, "video_context"))
        if _is_audio_context(ref):
            row_range = mapping.get("audio")
            if row_range is None:
                raise LayoutCompatibilityError("Continuum audio context has no reference rows")
            context_ranges.append((*row_range, "audio_context"))
        if _is_video_context(ref) or _is_audio_context(ref):
            context_descriptors.append(
                (
                    ref.get("kind"),
                    int(ref.get("latent_t", 0)),
                    int(ref.get("latent_h", 0)),
                    int(ref.get("latent_w", 0)),
                    int(ref.get("ref_audio_t", 0)),
                    tuple(sorted(metadata.items())),
                    _sampled_tensor_signature(ref.get("latent")),
                    _sampled_tensor_signature(ref.get("audio_latent")),
                )
            )

    if not context_ranges:
        raise LayoutCompatibilityError("Native Continuity payload has no context rows")
    for start, stop, role in context_ranges:
        row_range = (start, stop)
        if _ranges_overlap(row_range, audio_range) or _ranges_overlap(row_range, video_range):
            raise LayoutCompatibilityError(f"{role} rows overlap target rows")

    topology = (
        tuple(getattr(layout, "signature", ())),
        segments,
        audio_range,
        video_range,
        tuple(context_ranges),
        tuple(context_descriptors),
        int(payload.get("frame_count", 0) or 0),
        _sampled_tensor_signature(position_ids),
    )
    options = transformer_options if isinstance(transformer_options, dict) else {}
    if options.get("spectrum_h3_actual") is False:
        return {"status": "forecast_validated", "branch": _branch_key(options)}

    branch = _branch_key(options)
    baseline = branch_baselines.get(branch)
    if baseline is None:
        branch_baselines[branch] = topology
        return {"status": "baseline_created", "branch": branch}
    if baseline != topology:
        raise LayoutCompatibilityError(
            f"Native Continuity topology changed during sampling for branch {branch!r}"
        )
    return {"status": "baseline_matched", "branch": branch}


def patch_layout_in_place(
    payload: dict[str, Any], *, strict: bool = True, debug: bool = False,
) -> dict[str, Any]:
    layout = payload.get("layout")
    if layout is None:
        raise LayoutCompatibilityError(
            "H3 payload has no prebuilt PackedLayout; use ComfyUI v0.31.0 or newer"
        )
    missing = [name for name in ("position_ids", "segments", "signature") if not hasattr(layout, name)]
    if missing:
        raise LayoutCompatibilityError("PackedLayout is missing: " + ", ".join(missing))
    position_ids = layout.position_ids
    if not torch.is_tensor(position_ids) or position_ids.ndim != 2 or position_ids.shape[1] < 3:
        raise LayoutCompatibilityError("position_ids must be an [S,3] Tensor")

    signature = _patch_signature(payload, layout)
    if getattr(layout, LAYOUT_SIGNATURE_ATTR, None) == signature:
        return {"status": "already_patched", "position_ids_id": id(position_ids)}

    if not hasattr(layout, LAYOUT_ORIGINAL_TIME_ATTR):
        setattr(layout, LAYOUT_ORIGINAL_TIME_ATTR, position_ids[:, 0].clone())
    original_time = getattr(layout, LAYOUT_ORIGINAL_TIME_ATTR)
    if not torch.is_tensor(original_time) or original_time.shape != position_ids[:, 0].shape:
        raise LayoutCompatibilityError("stored layout baseline is incompatible")
    position_ids[:, 0].copy_(original_time)

    keyframes = list(payload.get("keyframes") or ())
    refs = list(payload.get("refs") or ())
    cond_segments = [(int(a), int(b)) for a, b, kind in layout.segments if kind == "cond"]
    if len(cond_segments) != len(keyframes):
        raise LayoutCompatibilityError(
            f"layout has {len(cond_segments)} cond segments for {len(keyframes)} keyframes"
        )

    video_start, video_stop = _single_segment(layout, "video")
    _single_segment(layout, "audio")
    text_segments = [(int(a), int(b)) for a, b, kind in layout.segments if kind == "text"]
    if len(text_segments) != 1 or text_segments[0][0] != 0:
        raise LayoutCompatibilityError("unexpected H3 text segment")
    text_len = text_segments[0][1]

    latent_t = int(layout.signature[1])
    video_rows = video_stop - video_start
    if latent_t <= 0 or video_rows % latent_t:
        raise LayoutCompatibilityError(
            f"video rows {video_rows} are incompatible with latent T={latent_t}"
        )
    frame_rows = video_rows // latent_t
    target_origin = float(position_ids[video_start, 0])
    reference_shift = target_origin - float(text_len)

    # Existing first/last-frame keyframes are text-relative in stock H3. Once
    # refs are present, move them by the target-origin shift. The legacy marked
    # slot path is retained for compatibility with early development states.
    patched_video_slots = 0
    for (start, stop), keyframe in zip(cond_segments, keyframes):
        if stop - start != frame_rows:
            raise LayoutCompatibilityError("keyframe rows no longer equal one target slot")
        if MARK_VIDEO_SLOT in keyframe:
            slot = int(keyframe[MARK_VIDEO_SLOT])
            if not (0 <= slot < latent_t):
                raise LayoutCompatibilityError(
                    f"context slot {slot} is outside target latent T={latent_t}"
                )
            target_row = video_start + slot * frame_rows
            position_ids[start:stop].copy_(
                position_ids[target_row : target_row + frame_rows]
            )
            patched_video_slots += 1
        elif reference_shift:
            position_ids[start:stop, 0].add_(reference_shift)

    ref_mappings = _map_refs_to_segments(layout, refs)
    patched_video_refs = 0
    patched_audio = 0
    for ref, mapping in zip(refs, ref_mappings):
        if _is_video_context(ref):
            segment = mapping.get("video")
            if segment is None:
                raise LayoutCompatibilityError("Continuum video ref has no video segment")
            start, stop = segment
            context_t = int(ref.get("latent_t", 0))
            expected_rows = context_t * frame_rows
            if context_t <= 0 or stop - start != expected_rows:
                raise LayoutCompatibilityError(
                    f"video-context rows {stop-start} do not match latent T={context_t}"
                )
            if context_t > latent_t:
                raise LayoutCompatibilityError(
                    f"video context T={context_t} exceeds target latent T={latent_t}"
                )
            target_stop = video_start + expected_rows
            # Copy all (t,h,w) coordinates. Resolution equality is already
            # enforced by state validation; this also fails safely if row geometry changes.
            position_ids[start:stop].copy_(position_ids[video_start:target_stop])
            patched_video_refs += 1

        if _is_audio_context(ref):
            segment = mapping.get("audio")
            if segment is None:
                raise LayoutCompatibilityError("Continuum audio ref has no audio segment")
            start, stop = segment
            rt = int(ref.get("ref_audio_t", 0))
            if rt <= 0 or stop - start != rt * 2:
                raise LayoutCompatibilityError(
                    f"audio rows {stop-start} do not match {rt} stereo steps"
                )
            end_frame = float(ref.get(MARK_AUDIO_END_FRAME, 0.0))
            grid_offset = float(ref.get(MARK_AUDIO_OVERHANG, 0.0))
            desired_end = target_origin + FRAME_RESCALE * end_frame + grid_offset
            desired_start = desired_end - float(rt)
            old_start = float(position_ids[start, 0])
            position_ids[start:stop, 0].add_(desired_start - old_start)
            patched_audio += 1

    patched_video = patched_video_slots + patched_video_refs
    if patched_video == 0:
        message = "no marked Continuum video context was found"
        if strict:
            raise LayoutCompatibilityError(message)
        LOG.warning(message)

    setattr(layout, LAYOUT_SIGNATURE_ATTR, signature)
    if debug:
        LOG.info(
            "Continuum layout: video_refs=%d legacy_slots=%d audio_windows=%d "
            "origin=%.6f rows=%d pos_id=%s",
            patched_video_refs,
            patched_video_slots,
            patched_audio,
            target_origin,
            position_ids.shape[0],
            id(position_ids),
        )
    return {
        "status": "patched",
        "video_contexts": patched_video,
        "video_refs": patched_video_refs,
        "legacy_video_slots": patched_video_slots,
        "audio_windows": patched_audio,
        "target_origin": target_origin,
        "position_ids_id": id(position_ids),
    }
