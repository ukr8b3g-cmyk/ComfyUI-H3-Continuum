"""Runtime-only First Pass conditioning for Continuum-aware refinement.

The context deliberately remains outside the persisted Assembly Plan contract.  It
owns CPU copies of the First Pass conditioning tensors and records them in physical
sampling order.  Second Pass callers may then derive a target-canvas conditioning
without mutating the captured source context.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Any

import torch

from ..constants import MARK_VIDEO_CONTEXT


MAGIC = "H3_CONTINUUM_REFINE_CONTEXT"
VERSION = 1


class RefineContextError(ValueError):
    """Raised when the runtime-only refine context is structurally invalid."""


class RefineConditioningAdaptationError(RefineContextError):
    """Raised when a valid captured conditioning cannot be adapted safely."""


def _cpu_tensor(value: torch.Tensor) -> torch.Tensor:
    return value.detach().to(device="cpu").clone().contiguous()


def _freeze(value: Any) -> Any:
    if torch.is_tensor(value):
        return _cpu_tensor(value)
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze(item) for item in value)
    return value


def freeze_conditioning(conditioning: Any) -> tuple[tuple[torch.Tensor, Mapping], ...]:
    """Return a CPU-owned conditioning clone with immutable containers.

    Tensors are detached and cloned, so later mutation or device movement of the
    original First Pass conditioning cannot affect the refine context.  Container
    immutability makes the result safe to share until target adaptation performs
    copy-on-write replacement of visual fields.
    """

    if not isinstance(conditioning, Sequence) or isinstance(
        conditioning, (str, bytes, bytearray)
    ):
        raise RefineContextError("conditioning must be a non-empty sequence")
    output: list[tuple[torch.Tensor, Mapping]] = []
    for index, entry in enumerate(conditioning):
        if not isinstance(entry, Sequence) or isinstance(
            entry, (str, bytes, bytearray)
        ) or len(entry) != 2:
            raise RefineContextError(
                f"conditioning entry {index} is not [tensor, metadata]"
            )
        tensor, metadata = entry
        if not torch.is_tensor(tensor):
            raise RefineContextError(
                f"conditioning entry {index} text value is not a tensor"
            )
        if not isinstance(metadata, Mapping):
            raise RefineContextError(
                f"conditioning entry {index} metadata is not a mapping"
            )
        output.append((_cpu_tensor(tensor), _freeze(metadata)))
    if not output:
        raise RefineContextError("conditioning is empty")
    return tuple(output)


def _optional_image(value: Any, name: str) -> torch.Tensor | None:
    if value is None:
        return None
    if not torch.is_tensor(value) or value.ndim != 4 or int(value.shape[-1]) < 3:
        raise RefineContextError(
            f"{name} must be an IMAGE tensor [B,H,W,C] with at least three channels"
        )
    return _cpu_tensor(value)


def _validate_optional_image(value: Any, name: str) -> None:
    if value is not None and (
        not torch.is_tensor(value) or value.ndim != 4 or int(value.shape[-1]) < 3
    ):
        raise RefineContextError(
            f"{name} must be an IMAGE tensor [B,H,W,C] with at least three channels"
        )


def make_refine_group(
    *,
    conditioning: Any,
    group_id: int,
    logical_chunks: Sequence[int],
    physical_frames: int,
    prompt_policy: str,
    physical_prompt: str,
    source_video_shape: Sequence[int],
    physical_clip_index: int,
    context_frames: int,
    first_image: torch.Tensor | None = None,
    last_image: torch.Tensor | None = None,
) -> dict[str, Any]:
    """Capture one physical First Pass sampling group's effective conditioning."""

    group_id = int(group_id)
    physical_frames = int(physical_frames)
    physical_clip_index = int(physical_clip_index)
    context_frames = int(context_frames)
    chunks = tuple(int(value) for value in logical_chunks)
    shape = tuple(int(value) for value in source_video_shape)
    if group_id < 0:
        raise RefineContextError("refine group id must be non-negative")
    if not chunks or any(value <= 0 for value in chunks):
        raise RefineContextError("refine group logical chunks are invalid")
    if tuple(sorted(chunks)) != chunks or len(set(chunks)) != len(chunks):
        raise RefineContextError("refine group logical chunks must be ordered and unique")
    if physical_frames <= 0:
        raise RefineContextError("refine group physical frame count is invalid")
    if not str(prompt_policy):
        raise RefineContextError("refine group prompt policy is empty")
    if len(shape) != 5 or any(value <= 0 for value in shape):
        raise RefineContextError("refine group source video shape must be [B,C,T,H,W]")
    if physical_clip_index <= 0:
        raise RefineContextError("refine group physical clip index is invalid")
    if context_frames < 0:
        raise RefineContextError("refine group context frame count is invalid")
    return {
        "group_id": group_id,
        "logical_chunks": chunks,
        "physical_frames": physical_frames,
        "prompt_policy": str(prompt_policy),
        "physical_prompt": str(physical_prompt),
        "source_video_shape": shape,
        "physical_clip_index": physical_clip_index,
        "context_frames": context_frames,
        "conditioning": freeze_conditioning(conditioning),
        "first_image": _optional_image(first_image, "first_image"),
        "last_image": _optional_image(last_image, "last_image"),
    }


def make_refine_context(
    groups: Sequence[Mapping[str, Any]],
    *,
    source_width: int,
    source_height: int,
    conditioning_mode: str,
    complete: bool = True,
    notes: Sequence[str] = (),
) -> dict[str, Any]:
    """Build and validate a physical-order runtime refine context."""

    context = {
        "magic": MAGIC,
        "version": VERSION,
        "source_width": int(source_width),
        "source_height": int(source_height),
        "conditioning_mode": str(conditioning_mode),
        "complete": bool(complete),
        "groups": tuple(dict(group) for group in groups),
        "notes": tuple(str(note) for note in notes),
    }
    return validate_refine_context(context)


def _validate_frozen_conditioning(value: Any, *, group_id: int) -> None:
    if not isinstance(value, tuple) or not value:
        raise RefineContextError(f"refine group {group_id} conditioning is invalid")
    for index, entry in enumerate(value):
        if not isinstance(entry, tuple) or len(entry) != 2:
            raise RefineContextError(
                f"refine group {group_id} conditioning entry {index} is invalid"
            )
        tensor, metadata = entry
        if not torch.is_tensor(tensor) or tensor.device.type != "cpu":
            raise RefineContextError(
                f"refine group {group_id} conditioning tensor {index} is not CPU-owned"
            )
        if not isinstance(metadata, Mapping):
            raise RefineContextError(
                f"refine group {group_id} conditioning metadata {index} is invalid"
            )


def _group_field_tuple(group: Mapping[str, Any], name: str) -> tuple[int, ...]:
    value = group.get(name)
    if not isinstance(value, (tuple, list)):
        raise RefineContextError(f"refine group {group.get('group_id')} {name} is invalid")
    try:
        return tuple(int(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise RefineContextError(
            f"refine group {group.get('group_id')} {name} is invalid"
        ) from exc


def validate_refine_context(
    context: Any, assembly_plan: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Validate a runtime context and, when supplied, its Assembly Plan pairing."""

    if not isinstance(context, dict) or context.get("magic") != MAGIC:
        raise RefineContextError("invalid H3 Continuum refine context")
    if type(context.get("version")) is not int or context["version"] != VERSION:
        raise RefineContextError(
            f"unsupported refine context version {context.get('version')!r}"
        )
    if int(context.get("source_width", 0)) <= 0 or int(
        context.get("source_height", 0)
    ) <= 0:
        raise RefineContextError("refine context source dimensions are invalid")
    if not str(context.get("conditioning_mode", "")):
        raise RefineContextError("refine context conditioning mode is empty")
    if type(context.get("complete")) is not bool:
        raise RefineContextError("refine context complete flag is invalid")
    groups = context.get("groups")
    if not isinstance(groups, tuple):
        raise RefineContextError("refine context groups must be an immutable tuple")
    if context["complete"] and not groups:
        raise RefineContextError("complete refine context contains no physical groups")
    notes = context.get("notes")
    if not isinstance(notes, tuple) or any(not isinstance(note, str) for note in notes):
        raise RefineContextError("refine context notes must be an immutable string tuple")

    previous_clip_index = 0
    for expected_id, group in enumerate(groups):
        if not isinstance(group, Mapping):
            raise RefineContextError(f"refine group {expected_id} is not a mapping")
        if type(group.get("group_id")) is not int or group["group_id"] != expected_id:
            raise RefineContextError("refine context physical group order is not contiguous")
        logical_chunks = _group_field_tuple(group, "logical_chunks")
        if not logical_chunks or any(value <= 0 for value in logical_chunks):
            raise RefineContextError(f"refine group {expected_id} logical chunks are invalid")
        if tuple(sorted(logical_chunks)) != logical_chunks or len(
            set(logical_chunks)
        ) != len(logical_chunks):
            raise RefineContextError(
                f"refine group {expected_id} logical chunks are not ordered and unique"
            )
        if int(group.get("physical_frames", 0)) <= 0:
            raise RefineContextError(f"refine group {expected_id} physical frames are invalid")
        if not str(group.get("prompt_policy", "")):
            raise RefineContextError(f"refine group {expected_id} prompt policy is empty")
        if "physical_prompt" not in group:
            raise RefineContextError(f"refine group {expected_id} physical prompt is absent")
        shape = _group_field_tuple(group, "source_video_shape")
        if len(shape) != 5 or any(value <= 0 for value in shape):
            raise RefineContextError(f"refine group {expected_id} source shape is invalid")
        clip_index = int(group.get("physical_clip_index", 0))
        if clip_index <= previous_clip_index:
            raise RefineContextError(
                "refine context physical clip indices are not strictly increasing"
            )
        previous_clip_index = clip_index
        if int(group.get("context_frames", -1)) < 0:
            raise RefineContextError(f"refine group {expected_id} context frames are invalid")
        _validate_frozen_conditioning(group.get("conditioning"), group_id=expected_id)
        _validate_optional_image(group.get("first_image"), "first_image")
        _validate_optional_image(group.get("last_image"), "last_image")

    if assembly_plan is not None:
        if not isinstance(assembly_plan, Mapping):
            raise RefineContextError("assembly plan paired with refine context is invalid")
        if int(assembly_plan.get("width", 0)) != int(context["source_width"]) or int(
            assembly_plan.get("height", 0)
        ) != int(context["source_height"]):
            raise RefineContextError("refine context source dimensions differ from assembly plan")
        contract = assembly_plan.get("second_pass_contract")
        plan_groups = contract.get("physical_groups") if isinstance(contract, Mapping) else None
        if not isinstance(plan_groups, Sequence):
            raise RefineContextError("assembly plan has no Second Pass physical-group contract")
        # An incomplete context is diagnostic-only (for example, Run Storage may
        # have reused an earlier group that was never sampled in this execution).
        # Its local group ids describe capture order, not Assembly Plan position;
        # validating those partial entries by index would incorrectly turn the
        # intended prompt-only fallback into a broken typed-contract hard error.
        if not context["complete"]:
            return context
        if context["complete"] and len(plan_groups) != len(groups):
            raise RefineContextError(
                "complete refine context physical-group count differs from assembly plan"
            )
        for group in groups:
            group_id = int(group["group_id"])
            if group_id >= len(plan_groups) or not isinstance(plan_groups[group_id], Mapping):
                raise RefineContextError(
                    f"refine group {group_id} has no matching assembly-plan group"
                )
            planned = plan_groups[group_id]
            comparisons = (
                ("logical_chunks", tuple(int(v) for v in group["logical_chunks"]),
                 tuple(int(v) for v in planned.get("logical_chunks", ()))),
                ("physical_frames", int(group["physical_frames"]),
                 int(planned.get("physical_frames", 0))),
                ("prompt_policy", str(group["prompt_policy"]),
                 str(planned.get("prompt_policy", ""))),
                ("physical_prompt", str(group["physical_prompt"]),
                 str(planned.get("physical_prompt", ""))),
                ("context_frames", int(group["context_frames"]),
                 int(planned.get("trim_prefix_frames", -1))),
            )
            for name, actual, expected in comparisons:
                if actual != expected:
                    raise RefineContextError(
                        f"refine group {group_id} {name} differs from assembly plan"
                    )
            expected_shape = (
                int(planned.get("source_batch", 0)),
                int(planned.get("latent_channels", 0)),
                int(planned.get("source_latent_t", 0)),
                int(planned.get("source_latent_h", 0)),
                int(planned.get("source_latent_w", 0)),
            )
            if tuple(group["source_video_shape"]) != expected_shape:
                raise RefineContextError(
                    f"refine group {group_id} source shape differs from assembly plan"
                )
    return context


def _common_upscale(
    samples: torch.Tensor,
    width: int,
    height: int,
    method: str,
    crop: str,
) -> torch.Tensor:
    try:
        import comfy.utils
    except Exception as exc:  # pragma: no cover - ComfyUI runtime only
        raise RefineConditioningAdaptationError(
            f"ComfyUI Core resize support is unavailable: {exc}"
        ) from exc
    return comfy.utils.common_upscale(samples, width, height, method, crop)


def _resize_latent(
    latent: Any,
    *,
    target_h: int,
    target_w: int,
    method: str,
) -> torch.Tensor:
    if not torch.is_tensor(latent) or latent.ndim != 5:
        raise RefineConditioningAdaptationError(
            "H3 visual conditioning latent must be [B,C,T,H,W]"
        )
    batch, channels, temporal, _, _ = (int(value) for value in latent.shape)
    flat = latent.permute(0, 2, 1, 3, 4).reshape(
        batch * temporal, channels, int(latent.shape[-2]), int(latent.shape[-1])
    )
    try:
        resized = _common_upscale(flat, target_w, target_h, method, "disabled")
    except RefineConditioningAdaptationError:
        raise
    except Exception as exc:
        raise RefineConditioningAdaptationError(
            f"visual conditioning latent resize failed: {exc}"
        ) from exc
    if not torch.is_tensor(resized) or tuple(resized.shape[-2:]) != (
        target_h,
        target_w,
    ):
        raise RefineConditioningAdaptationError(
            "Core resize returned an incompatible visual conditioning shape"
        )
    return (
        resized.reshape(batch, temporal, channels, target_h, target_w)
        .permute(0, 2, 1, 3, 4)
        .contiguous()
    )


def _encode_keyframe_image(
    image: torch.Tensor,
    *,
    target_h: int,
    target_w: int,
    crop: str,
    video_vae: Any,
) -> torch.Tensor:
    pixels_h = target_h * 16
    pixels_w = target_w * 16
    samples = image[:1, ..., :3].movedim(-1, 1)
    try:
        resized = _common_upscale(samples, pixels_w, pixels_h, "lanczos", crop)
        latent = video_vae.encode(resized.movedim(1, -1).contiguous())
    except RefineConditioningAdaptationError:
        raise
    except Exception as exc:
        raise RefineConditioningAdaptationError(
            f"target keyframe VAE encode failed: {exc}"
        ) from exc
    if not torch.is_tensor(latent) or latent.ndim != 5 or tuple(
        int(value) for value in latent.shape[-2:]
    ) != (target_h, target_w):
        raise RefineConditioningAdaptationError(
            "target keyframe VAE encode returned an incompatible latent shape"
        )
    return latent.contiguous()


def adapt_group_conditioning(
    group: Mapping[str, Any],
    target_latent_h: int,
    target_latent_w: int,
    video_vae: Any = None,
    upscale_method: str = "bilinear",
) -> tuple[list[list[Any]], dict[str, Any]]:
    """Copy-on-write target adaptation for keyframes and Continuum video context.

    Ordinary MiniMax references, all audio latents, and text conditioning tensors
    remain shared with the frozen source.  Only keyframe video latents and
    ``MARK_VIDEO_CONTEXT`` reference video latents are target-sized.
    """

    if not isinstance(group, Mapping):
        raise RefineConditioningAdaptationError("refine group is not a mapping")
    group_id = int(group.get("group_id", -1))
    _validate_frozen_conditioning(group.get("conditioning"), group_id=group_id)
    target_h = int(target_latent_h)
    target_w = int(target_latent_w)
    if target_h <= 0 or target_w <= 0:
        raise RefineConditioningAdaptationError("target latent dimensions are invalid")
    physical_frames = int(group.get("physical_frames", 0))
    if physical_frames <= 0:
        raise RefineConditioningAdaptationError("refine group physical frames are invalid")

    warnings: list[str] = []
    stats: dict[str, Any] = {
        "group_id": group_id,
        "target_latent_h": target_h,
        "target_latent_w": target_w,
        "keyframes_resized": 0,
        "keyframes_reencoded": 0,
        "keyframes_latent_fallback": 0,
        "context_refs_resized": 0,
    }
    output: list[list[Any]] = []
    for text_tensor, frozen_metadata in group["conditioning"]:
        metadata = dict(frozen_metadata)
        keyframes = frozen_metadata.get("minimax_keyframes")
        if keyframes is not None:
            adapted_keyframes = []
            for frozen_keyframe in keyframes:
                if not isinstance(frozen_keyframe, Mapping):
                    raise RefineConditioningAdaptationError(
                        f"refine group {group_id} contains an invalid keyframe"
                    )
                keyframe = dict(frozen_keyframe)
                latent = keyframe.get("latent")
                if not torch.is_tensor(latent) or latent.ndim != 5:
                    raise RefineConditioningAdaptationError(
                        f"refine group {group_id} keyframe latent is invalid"
                    )
                if tuple(int(value) for value in latent.shape[-2:]) != (
                    target_h,
                    target_w,
                ):
                    frame_index = int(keyframe.get("resolved_frame_index", -1))
                    image = None
                    crop = "disabled"
                    if frame_index == 0:
                        image = group.get("first_image")
                    elif frame_index == physical_frames - 1:
                        image = group.get("last_image")
                        crop = "center"
                    if video_vae is not None and torch.is_tensor(image):
                        keyframe["latent"] = _encode_keyframe_image(
                            image,
                            target_h=target_h,
                            target_w=target_w,
                            crop=crop,
                            video_vae=video_vae,
                        )
                        stats["keyframes_reencoded"] += 1
                    else:
                        keyframe["latent"] = _resize_latent(
                            latent,
                            target_h=target_h,
                            target_w=target_w,
                            method=str(upscale_method),
                        )
                        stats["keyframes_latent_fallback"] += 1
                        warning = (
                            f"group {group_id} keyframe {frame_index} used latent resize "
                            "because its source image and video VAE were not both available"
                        )
                        warnings.append(warning)
                    stats["keyframes_resized"] += 1
                adapted_keyframes.append(keyframe)
            metadata["minimax_keyframes"] = adapted_keyframes

        refs = frozen_metadata.get("minimax_refs")
        if refs is not None:
            adapted_refs = []
            refs_changed = False
            for frozen_ref in refs:
                if not isinstance(frozen_ref, Mapping):
                    raise RefineConditioningAdaptationError(
                        f"refine group {group_id} contains an invalid MiniMax reference"
                    )
                if bool(frozen_ref.get(MARK_VIDEO_CONTEXT)):
                    latent = frozen_ref.get("latent")
                    if not torch.is_tensor(latent) or latent.ndim != 5:
                        raise RefineConditioningAdaptationError(
                            f"refine group {group_id} Continuum video context is invalid"
                        )
                    if tuple(int(value) for value in latent.shape[-2:]) != (
                        target_h,
                        target_w,
                    ):
                        adapted_ref = dict(frozen_ref)
                        adapted_ref["latent"] = _resize_latent(
                            latent,
                            target_h=target_h,
                            target_w=target_w,
                            method=str(upscale_method),
                        )
                        adapted_ref["latent_h"] = target_h
                        adapted_ref["latent_w"] = target_w
                        adapted_refs.append(adapted_ref)
                        refs_changed = True
                        stats["context_refs_resized"] += 1
                        continue
                adapted_refs.append(frozen_ref)
            if refs_changed:
                metadata["minimax_refs"] = adapted_refs

        output.append([text_tensor, metadata])
    stats["warnings"] = tuple(warnings)
    return output, stats
