"""Frame-based Still Image Guide support for H3 Continuum V3.7."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
from typing import Any

import torch

from .continuation import clone_conditioning


GUIDE_SCHEMA_VERSION = 1
GUIDE_MODE_STILL_IMAGE = "still_image"
GUIDE_TYPE = "H3_CONTINUUM_STILL_IMAGE_GUIDE"
MARK_STILL_IMAGE_GUIDE = "h3_continuum_still_image_guide_v1"


class GuideTargetError(ValueError):
    pass


@dataclass(slots=True)
class StillImageGuideSource:
    image: torch.Tensor
    absolute_frame: int
    contract: dict[str, Any]
    source_image: torch.Tensor | None = None


@dataclass(slots=True)
class StillImageGuideAssets:
    source: StillImageGuideSource
    latent: torch.Tensor


def _resize_guide_image(
    image: torch.Tensor,
    width: int,
    height: int,
) -> torch.Tensor:
    # Lazy import keeps the V2 package initializer from cycling back through
    # sequence.py while this standalone resolver module is being imported.
    from .v2.h3_builder import resize_h3_image

    return resize_h3_image(image, width, height, "center")


def _strict_int(name: str, value: Any, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise GuideTargetError(f"{name} must be an integer >= {minimum}")
    return value


def _tensor_fingerprint(tensor: torch.Tensor) -> str:
    sample = tensor.detach().to("cpu").contiguous()
    digest = hashlib.sha256()
    digest.update(str(tuple(int(value) for value in sample.shape)).encode("ascii"))
    digest.update(str(sample.dtype).encode("ascii"))
    digest.update(sample.numpy().tobytes())
    return digest.hexdigest()


def _validate_still_image_tensor(image: Any) -> torch.Tensor:
    if not torch.is_tensor(image) or image.ndim != 4 or image.shape[-1] < 3:
        raise GuideTargetError(
            "Still Image Guide input must be [B,H,W,C] with at least three channels"
        )
    if int(image.shape[0]) != 1:
        raise GuideTargetError("Still Image Guide input batch must be exactly 1")
    return image


def make_still_image_guide(image: torch.Tensor, absolute_frame: int) -> dict[str, Any]:
    """Create the small public guide payload without output-size assumptions."""

    image = _validate_still_image_tensor(image)
    return {
        "schema_version": GUIDE_SCHEMA_VERSION,
        "mode": GUIDE_MODE_STILL_IMAGE,
        "absolute_frame": _strict_int("absolute_frame", absolute_frame),
        "image": image,
    }


def prepare_still_image_guide_source(
    guide: Mapping[str, Any] | None,
    *,
    output_width: int,
    output_height: int,
) -> StillImageGuideSource | None:
    if guide is None:
        return None
    if not isinstance(guide, Mapping):
        raise GuideTargetError("Still Image Guide must be a mapping")
    if guide.get("schema_version") != GUIDE_SCHEMA_VERSION:
        raise GuideTargetError(
            f"unsupported Still Image Guide schema {guide.get('schema_version')!r}"
        )
    if guide.get("mode") != GUIDE_MODE_STILL_IMAGE:
        raise GuideTargetError(f"unsupported Guide mode {guide.get('mode')!r}")
    absolute_frame = _strict_int("absolute_frame", guide.get("absolute_frame"))
    image = _validate_still_image_tensor(guide.get("image"))
    resized = _resize_guide_image(
        image,
        int(output_width),
        int(output_height),
    )
    contract = {
        "schema_version": GUIDE_SCHEMA_VERSION,
        "mode": GUIDE_MODE_STILL_IMAGE,
        "absolute_frame": absolute_frame,
        "image_sha256": _tensor_fingerprint(resized),
        "source_image_sha256": _tensor_fingerprint(image),
        "source_width": int(image.shape[-2]),
        "source_height": int(image.shape[-3]),
        "width": int(output_width),
        "height": int(output_height),
    }
    return StillImageGuideSource(
        image=resized,
        absolute_frame=absolute_frame,
        contract=contract,
        source_image=image.detach().to(device="cpu").clone().contiguous(),
    )


def validate_guide_visible_range(
    source: StillImageGuideSource | None,
    *,
    target_frames: int,
) -> None:
    if source is None:
        return
    target_frames = _strict_int("target_frames", target_frames, minimum=1)
    if source.absolute_frame >= target_frames:
        raise GuideTargetError(
            f"absolute_frame {source.absolute_frame} is outside visible range "
            f"0-{target_frames - 1}"
        )


def encode_still_image_guide(
    video_vae: Any,
    source: StillImageGuideSource | None,
) -> StillImageGuideAssets | None:
    if source is None:
        return None
    return StillImageGuideAssets(source=source, latent=video_vae.encode(source.image))


def combine_guide_identity(
    base_identity: str,
    source: StillImageGuideSource | None,
) -> str:
    """Scope resume identity by image, absolute frame, mode, and schema version."""

    if source is None:
        return str(base_identity)
    payload = {
        "base_identity": str(base_identity),
        "guide": source.contract,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def _physical_groups(physical_plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(physical_plan, Mapping):
        raise GuideTargetError("physical_plan must be a mapping")
    target_frames = _strict_int(
        "physical_plan.target_frames",
        physical_plan.get("target_frames"),
        minimum=1,
    )
    raw_groups = physical_plan.get("decode_groups")
    if raw_groups is None:
        raw_groups = physical_plan.get("chunks")
    if not isinstance(raw_groups, list) or not raw_groups:
        raise GuideTargetError("physical_plan has no physical groups")

    groups: list[dict[str, Any]] = []
    natural_cursor = 0
    for group_index, raw_group in enumerate(raw_groups):
        if not isinstance(raw_group, Mapping):
            raise GuideTargetError(f"physical group {group_index} is not a mapping")
        frame_start = _strict_int(
            f"physical group {group_index}.frame_start",
            raw_group.get("frame_start", natural_cursor),
        )
        net_frames = _strict_int(
            f"physical group {group_index}.net_frames",
            raw_group.get("net_frames"),
            minimum=1,
        )
        natural_frame_stop = _strict_int(
            f"physical group {group_index}.frame_stop",
            raw_group.get("frame_stop", frame_start + net_frames),
            minimum=1,
        )
        context_prefix_frames = _strict_int(
            f"physical group {group_index}.trim_frames",
            raw_group.get("trim_frames", raw_group.get("context_frames", 0)),
        )
        physical_frames = _strict_int(
            f"physical group {group_index}.total_frames",
            raw_group.get("total_frames"),
            minimum=1,
        )
        if frame_start != natural_cursor:
            raise GuideTargetError("physical group visible ranges are not contiguous")
        if natural_frame_stop != frame_start + net_frames:
            raise GuideTargetError("physical group visible range differs from net_frames")
        if physical_frames - context_prefix_frames != net_frames:
            raise GuideTargetError(
                "physical group total/context frames differ from visible net frames"
            )

        visible_frame_stop = min(natural_frame_stop, target_frames)
        if visible_frame_stop > frame_start:
            logical_chunks = raw_group.get("logical_chunk_indices")
            if logical_chunks is None:
                logical_chunks = [raw_group.get("chunk_index", group_index + 1)]
            groups.append(
                {
                    "physical_group_index": group_index,
                    "logical_chunks": [int(value) for value in logical_chunks],
                    "global_visible_start": frame_start,
                    "global_visible_stop": visible_frame_stop,
                    "natural_frame_stop": natural_frame_stop,
                    "context_prefix_frames": context_prefix_frames,
                    "physical_frames": physical_frames,
                    "net_new_frames": net_frames,
                    "terminal_merged": bool(raw_group.get("terminal_merged", False)),
                }
            )
        natural_cursor = natural_frame_stop

    if not groups or groups[-1]["global_visible_stop"] != target_frames:
        raise GuideTargetError("physical groups do not cover the visible target timeline")
    return groups


def _resolved_target(
    absolute_frame: int,
    group: Mapping[str, Any],
) -> dict[str, Any] | None:
    start = int(group["global_visible_start"])
    stop = int(group["global_visible_stop"])
    if not start <= absolute_frame < stop:
        return None
    local_visible_frame = absolute_frame - start
    resolved_frame_index = int(group["context_prefix_frames"]) + local_visible_frame
    if resolved_frame_index < int(group["context_prefix_frames"]):
        raise GuideTargetError("resolved guide overlaps the continuation prefix")
    if resolved_frame_index >= int(group["physical_frames"]):
        raise GuideTargetError("resolved guide lies outside its physical group")
    return {
        **dict(group),
        "absolute_frame": absolute_frame,
        "local_visible_frame": local_visible_frame,
        "resolved_frame_index": resolved_frame_index,
    }


def resolve_guide_target(
    absolute_frame: int,
    physical_plan: Mapping[str, Any],
) -> dict[str, Any]:
    """Resolve one visible absolute frame to Core MiniMaxH3AddGuide frame_idx."""

    absolute_frame = _strict_int("absolute_frame", absolute_frame)
    target_frames = _strict_int(
        "physical_plan.target_frames",
        physical_plan.get("target_frames")
        if isinstance(physical_plan, Mapping)
        else None,
        minimum=1,
    )
    if absolute_frame >= target_frames:
        raise GuideTargetError(
            f"absolute_frame {absolute_frame} is outside visible range 0-{target_frames - 1}"
        )
    for group in _physical_groups(physical_plan):
        result = _resolved_target(absolute_frame, group)
        if result is not None:
            return result
    raise GuideTargetError("absolute frame was not owned by any physical group")


def resolve_guide_for_physical_group(
    absolute_frame: int,
    *,
    target_frames: int,
    physical_group_index: int,
    logical_chunks: tuple[int, ...] | list[int],
    global_visible_start: int,
    natural_visible_stop: int,
    context_prefix_frames: int,
    physical_frames: int,
    terminal_merged: bool,
) -> dict[str, Any] | None:
    """Resolve against one authoritative runtime chunk/terminal physical group."""

    absolute_frame = _strict_int("absolute_frame", absolute_frame)
    target_frames = _strict_int("target_frames", target_frames, minimum=1)
    if absolute_frame >= target_frames:
        raise GuideTargetError(
            f"absolute_frame {absolute_frame} is outside visible range 0-{target_frames - 1}"
        )
    start = _strict_int("global_visible_start", global_visible_start)
    natural_stop = _strict_int(
        "natural_visible_stop", natural_visible_stop, minimum=1
    )
    context = _strict_int("context_prefix_frames", context_prefix_frames)
    physical = _strict_int("physical_frames", physical_frames, minimum=1)
    if natural_stop <= start or physical - context != natural_stop - start:
        raise GuideTargetError("runtime physical group geometry is contradictory")
    group = {
        "physical_group_index": _strict_int(
            "physical_group_index", physical_group_index
        ),
        "logical_chunks": [int(value) for value in logical_chunks],
        "global_visible_start": start,
        "global_visible_stop": min(natural_stop, target_frames),
        "natural_frame_stop": natural_stop,
        "context_prefix_frames": context,
        "physical_frames": physical,
        "net_new_frames": natural_stop - start,
        "terminal_merged": bool(terminal_merged),
    }
    return _resolved_target(absolute_frame, group)


def attach_still_image_guide(
    conditioning: list,
    assets: StillImageGuideAssets | None,
    target: Mapping[str, Any] | None,
) -> list:
    if assets is None or target is None:
        return conditioning
    output = clone_conditioning(conditioning)
    keyframe = {
        "resolved_frame_index": int(target["resolved_frame_index"]),
        "latent": assets.latent,
        MARK_STILL_IMAGE_GUIDE: True,
    }
    for _, metadata in output:
        keyframes = [dict(item) for item in (metadata.get("minimax_keyframes") or [])]
        keyframes.append(dict(keyframe))
        metadata["minimax_keyframes"] = keyframes
    return output
