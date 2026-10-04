"""V3.5 Second Pass contracts and the physical-group sampling runtime."""

from __future__ import annotations

import copy
import hashlib
from collections.abc import Mapping, Sequence
from typing import Any

import torch

from ..model_patch import clone_model_for_chunk
from ..state import extract_av_streams
from ..v2.h3_builder import encode_prompt_conditioning
from ..v2.sampling import latent_from_cpu
from .plan import SECOND_PASS_CONTRACT_VERSION
from .refine_context import (
    MAGIC as REFINE_CONTEXT_MAGIC,
    OUTPUT_SCOPE_KEY,
    RefineConditioningAdaptationError,
    RefineContextError,
    adapt_group_conditioning,
    validate_refine_context,
)
from .refine_schedule import (
    RefineSchedule,
    RefineScheduleError,
    resolve_refine_schedule,
    serializable_schedule_contract,
)
from .refine_sampling import sample_refine_chunk


class SecondPassContractError(ValueError):
    """Raised only when a Second Pass structural contract is impossible."""


def derive_refine_seed(refine_seed: int, physical_group_index: int) -> int:
    """Derive one deterministic seed per physical group in an independent namespace."""
    if type(refine_seed) is not int or refine_seed < 0:
        raise SecondPassContractError("refine_seed must be a non-negative integer")
    if type(physical_group_index) is not int or physical_group_index < 0:
        raise SecondPassContractError("physical_group_index must be a non-negative integer")
    payload = f"h3-continuum-refine-v1:{refine_seed}:{physical_group_index}".encode("ascii")
    return int.from_bytes(hashlib.blake2b(payload, digest_size=8).digest(), "big")


def _latent_samples(value: Any, *, name: str) -> torch.Tensor:
    if not isinstance(value, Mapping) or "samples" not in value:
        raise SecondPassContractError(f"{name} must be a LATENT mapping with samples")
    samples = value["samples"]
    if not isinstance(samples, torch.Tensor):
        raise SecondPassContractError(f"{name}.samples must be a tensor")
    return samples


def _require_finite_samples(samples: torch.Tensor, *, name: str) -> None:
    """Reject unusable processor output before it reaches Second Pass Sampling."""

    if not bool(torch.isfinite(samples).all().item()):
        raise SecondPassContractError(f"{name}.samples contains NaN or Inf")


def _contract_groups(assembly_plan: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    if not isinstance(assembly_plan, Mapping):
        raise SecondPassContractError("assembly_plan must be a mapping")
    contract = assembly_plan.get("second_pass_contract")
    if not isinstance(contract, Mapping):
        raise SecondPassContractError("assembly_plan has no second_pass_contract")
    if contract.get("version") != SECOND_PASS_CONTRACT_VERSION:
        raise SecondPassContractError("unsupported second_pass_contract version")
    groups = contract.get("physical_groups")
    if not isinstance(groups, list) or not groups or not all(isinstance(g, Mapping) for g in groups):
        raise SecondPassContractError("second_pass_contract.physical_groups must be non-empty")
    return groups


def _validate_video_groups(
    video_latents: Sequence[Any],
    assembly_plan: Mapping[str, Any],
) -> tuple[list[Mapping[str, Any]], tuple[int, int]]:
    groups = _contract_groups(assembly_plan)
    if not isinstance(video_latents, Sequence) or isinstance(video_latents, (str, bytes)):
        raise SecondPassContractError("video_latents must be a sequence")
    if len(video_latents) != len(groups):
        raise SecondPassContractError("video latent group count changed")

    target_geometry: tuple[int, int] | None = None
    for position, (latent, group) in enumerate(zip(video_latents, groups, strict=True)):
        if group.get("group_id") != position:
            raise SecondPassContractError("physical group order or group_id changed")
        samples = _latent_samples(latent, name=f"video_latents[{position}]")
        if samples.ndim != 5:
            raise SecondPassContractError("video latent must have shape [B,C,T,H,W]")
        batch, channels, temporal, height, width = (int(value) for value in samples.shape)
        if channels != 24:
            raise SecondPassContractError("MiniMax H3 video latent must have 24 channels")
        if batch != int(group.get("source_batch", -1)):
            raise SecondPassContractError("video latent batch changed")
        if temporal != int(group.get("source_latent_t", -1)):
            raise SecondPassContractError("video latent temporal length changed")
        source_h = int(group.get("source_latent_h", -1))
        source_w = int(group.get("source_latent_w", -1))
        if source_h < 1 or source_w < 1 or height < source_h or width < source_w:
            raise SecondPassContractError("video latent spatial size must be preserved or enlarged")
        _require_finite_samples(samples, name=f"video_latents[{position}]")
        if target_geometry is None:
            target_geometry = (height, width)
        elif target_geometry != (height, width):
            raise SecondPassContractError("all physical groups must use the same target H/W")

    assert target_geometry is not None
    return groups, target_geometry


def validate_second_pass_inputs(
    video_latents: Sequence[Any],
    audio_latents: Sequence[Any],
    assembly_plan: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate only structural invariants required by a future Second Pass node."""
    groups, target_geometry = _validate_video_groups(video_latents, assembly_plan)
    if not isinstance(audio_latents, Sequence) or isinstance(audio_latents, (str, bytes)):
        raise SecondPassContractError("audio_latents must be a sequence")
    if len(audio_latents) != len(groups):
        raise SecondPassContractError("audio latent group count changed")

    for position, (latent, group) in enumerate(zip(audio_latents, groups, strict=True)):
        samples = _latent_samples(latent, name=f"audio_latents[{position}]")
        expected_shape = group.get("source_audio_shape")
        if not isinstance(expected_shape, list) or tuple(expected_shape) != tuple(samples.shape):
            raise SecondPassContractError("audio latent shape or physical group order changed")
        _require_finite_samples(samples, name=f"audio_latents[{position}]")

    return {
        "physical_group_count": len(groups),
        "target_latent_h": target_geometry[0],
        "target_latent_w": target_geometry[1],
        "audio_passthrough": True,
    }


def passthrough_audio_latents(audio_latents: Sequence[Any]) -> list[Any]:
    """Return original LATENT objects; temporary refined audio is not adopted in V1."""
    return list(audio_latents)


def _normalize_selected_group_indices(
    selected_group_indices: Sequence[int] | None,
    physical_group_count: int,
) -> tuple[tuple[int, ...], bool]:
    """Validate an optional internal physical-group selection."""

    if selected_group_indices is None:
        return tuple(range(physical_group_count)), False
    if (
        not isinstance(selected_group_indices, Sequence)
        or isinstance(selected_group_indices, (str, bytes))
        or not selected_group_indices
    ):
        raise SecondPassContractError(
            "selected physical groups must be a non-empty integer sequence"
        )
    selected = tuple(selected_group_indices)
    if any(type(index) is not int for index in selected):
        raise SecondPassContractError(
            "selected physical group indices must be integers"
        )
    if len(set(selected)) != len(selected):
        raise SecondPassContractError("selected physical groups contain duplicates")
    if tuple(sorted(selected)) != selected:
        raise SecondPassContractError(
            "selected physical groups must follow physical execution order"
        )
    if selected[0] < 0 or selected[-1] >= physical_group_count:
        raise SecondPassContractError("selected physical group index is out of range")
    return selected, True


def update_second_pass_geometry(
    assembly_plan: Mapping[str, Any],
    video_latents: Sequence[Any],
) -> dict[str, Any]:
    """Return a copied plan whose output geometry follows the upscaled physical latents."""
    groups, (target_h, target_w) = _validate_video_groups(video_latents, assembly_plan)
    scale_h: int | None = None
    scale_w: int | None = None
    for group in groups:
        source_h = int(group["source_latent_h"])
        source_w = int(group["source_latent_w"])
        source_height = int(group["source_height"])
        source_width = int(group["source_width"])
        if source_height % source_h or source_width % source_w:
            raise SecondPassContractError("source pixel/latent geometry is not integral")
        group_scale_h = source_height // source_h
        group_scale_w = source_width // source_w
        if scale_h is None:
            scale_h, scale_w = group_scale_h, group_scale_w
        elif (scale_h, scale_w) != (group_scale_h, group_scale_w):
            raise SecondPassContractError("source geometry scale differs between groups")

    assert scale_h is not None and scale_w is not None
    target_height = target_h * scale_h
    target_width = target_w * scale_w
    updated = copy.deepcopy(dict(assembly_plan))
    updated["width"] = target_width
    updated["height"] = target_height
    contract = updated["second_pass_contract"]
    contract["target_width"] = target_width
    contract["target_height"] = target_height
    for group in contract["physical_groups"]:
        group["target_latent_h"] = target_h
        group["target_latent_w"] = target_w
        group["target_width"] = target_width
        group["target_height"] = target_height
    return updated


def prepare_physical_refine_groups(
    *,
    model: Any,
    clip: Any,
    video_latents: Sequence[Any],
    assembly_plan: Mapping[str, Any],
    refine_context: Any = None,
    video_vae: Any = None,
    conditioning_upscale_method: str = "bilinear",
    encode_prompt_fn=None,
    clone_model_fn=None,
    validate_refine_context_fn=None,
    adapt_group_conditioning_fn=None,
    group_consumer_fn=None,
    retain_group_outputs: bool = True,
    selected_group_indices: Sequence[int] | None = None,
) -> dict[str, Any]:
    """Prepare one MODEL and one complete CONDITIONING per physical group.

    This is the shared, sampling-independent contract used by the built-in
    Second Pass and the public Advanced Conditioning Bridge.  The returned
    ``conditioning`` value is an outer physical-group list; every item inside
    it remains one complete ComfyUI CONDITIONING object.
    """

    groups, (target_h, target_w) = _validate_video_groups(
        video_latents,
        assembly_plan,
    )
    selected_indices, selection_active = _normalize_selected_group_indices(
        selected_group_indices,
        len(groups),
    )
    selected_index_set = set(selected_indices)
    encode_prompt_fn = encode_prompt_fn or encode_prompt_conditioning
    clone_model_fn = clone_model_fn or clone_model_for_chunk
    validate_refine_context_fn = validate_refine_context_fn or validate_refine_context
    adapt_group_conditioning_fn = (
        adapt_group_conditioning_fn or adapt_group_conditioning
    )

    captured_groups: Sequence[Mapping[str, Any]] | None = None
    warnings: list[str] = []
    if refine_context is None:
        warnings.append(
            "WARNING: refine_context is not connected; using legacy prompt-only "
            "conditioning."
        )
    else:
        typed_context = (
            isinstance(refine_context, Mapping)
            and refine_context.get("magic") == REFINE_CONTEXT_MAGIC
        )
        try:
            validated_context = validate_refine_context_fn(
                refine_context,
                assembly_plan=assembly_plan,
            )
        except RefineContextError as exc:
            if typed_context:
                raise SecondPassContractError(
                    f"refine_context contract is invalid: {exc}"
                ) from exc
            warnings.append(
                "WARNING: optional refine_context was not a typed Continuum context; "
                f"using legacy prompt-only conditioning ({exc})."
            )
        else:
            if (bool(validated_context.get("complete"))
                    or validated_context.get(OUTPUT_SCOPE_KEY) is not None):
                captured_groups = validated_context["groups"]
            else:
                warnings.append(
                    "WARNING: refine_context capture is incomplete; using legacy "
                    "prompt-only conditioning."
                )
                warnings.extend(str(note) for note in validated_context.get("notes", ())
                                if str(note).startswith("Output scope unavailable:"))

    group_models: list[Any] = []
    group_conditioning: list[list[Any]] = []
    details: list[dict[str, Any]] = []
    for group_index, group in enumerate(groups):
        if group_index not in selected_index_set:
            continue
        captured_group = (
            captured_groups[group_index] if captured_groups is not None else None
        )
        model_group = captured_group if captured_group is not None else group
        adaptation_stats: Mapping[str, Any] | None = None
        context_conditioning_available = False
        if captured_group is not None:
            try:
                conditioning, adaptation_stats = adapt_group_conditioning_fn(
                    captured_group,
                    target_latent_h=target_h,
                    target_latent_w=target_w,
                    video_vae=video_vae,
                    upscale_method=str(conditioning_upscale_method),
                )
                conditioning_source = "refine_context"
                context_conditioning_available = True
            except RefineConditioningAdaptationError as exc:
                warnings.append(
                    f"WARNING: group {group_index + 1} refine_context target "
                    f"adaptation was unavailable; using legacy prompt-only "
                    f"conditioning ({exc})."
                )
            except RefineContextError as exc:
                raise SecondPassContractError(
                    f"refine_context group {group_index} is invalid: {exc}"
                ) from exc

        if not context_conditioning_available:
            prompt = str(group.get("physical_prompt", ""))
            conditioning = encode_prompt_fn(
                clip,
                prompt,
                first_image=None,
                last_image=None,
                reference_audio_assets=None,
                timeline_video_assets=None,
            )
            conditioning_source = "prompt_only_fallback"
        if not isinstance(conditioning, list):
            raise SecondPassContractError(
                f"physical group {group_index} conditioning is not a complete "
                "ComfyUI CONDITIONING object"
            )

        logical_chunks = model_group.get("logical_chunks")
        if not isinstance(logical_chunks, Sequence) or not logical_chunks:
            logical_chunks = group.get("logical_chunks")
        if not isinstance(logical_chunks, Sequence) or not logical_chunks:
            raise SecondPassContractError(
                f"physical group {group_index} has no logical chunk identity"
            )
        physical_clip_index = int(
            model_group.get("physical_clip_index", logical_chunks[0])
        )
        context_frames = int(
            model_group.get(
                "context_frames",
                group.get("trim_prefix_frames", 0),
            )
        )
        if physical_clip_index <= 0 or context_frames < 0:
            raise SecondPassContractError(
                f"physical group {group_index} MODEL context is invalid"
            )
        chunk_model = clone_model_fn(
            model,
            strict=False,
            debug=False,
            chunk_index=physical_clip_index,
            context_frames=context_frames if context_frames > 0 else None,
        )
        detail = {
            "group_index": group_index,
            "group": group,
            "conditioning_source": conditioning_source,
            "adaptation_stats": adaptation_stats,
            "physical_clip_index": physical_clip_index,
            "context_frames": context_frames,
            "reference_routing_v1": (
                captured_group.get("reference_routing_v1")
                if captured_group is not None else None
            ),
        }
        if group_consumer_fn is not None:
            group_consumer_fn(
                group_index,
                video_latents[group_index],
                group,
                chunk_model,
                conditioning,
                detail,
            )
        if retain_group_outputs:
            group_models.append(chunk_model)
            # Append, never extend: CONDITIONING's internal entries belong together.
            group_conditioning.append(conditioning)
        details.append(detail)

    physical_group_count = len(groups)
    selected_group_count = len(selected_indices)
    if retain_group_outputs and not (
        len(group_models)
        == len(group_conditioning)
        == len(details)
        == selected_group_count
    ):
        raise SecondPassContractError(
            "prepared MODEL/CONDITIONING physical group counts differ"
        )
    if not retain_group_outputs and group_consumer_fn is None:
        raise SecondPassContractError(
            "non-retained physical group preparation requires a consumer"
        )
    return {
        "group_models": group_models,
        "conditioning": group_conditioning,
        "updated_assembly_plan": update_second_pass_geometry(
            assembly_plan,
            video_latents,
        ),
        "details": details,
        "warnings": warnings,
        "physical_group_count": physical_group_count,
        "selected_group_count": selected_group_count,
        "selected_group_indices": list(selected_indices),
        "selection_active": selection_active,
        "target_latent_h": target_h,
        "target_latent_w": target_w,
    }


def run_second_pass_groups(
    *,
    model: Any,
    clip: Any,
    sampler: Any,
    sigmas: torch.Tensor,
    video_latents: Sequence[Any],
    audio_latents: Sequence[Any],
    assembly_plan: Mapping[str, Any],
    refine_seed: int,
    refine_context: Any = None,
    video_vae: Any = None,
    conditioning_upscale_method: str = "bilinear",
    enable_preview: bool = True,
    encode_prompt_fn=None,
    latent_builder=None,
    sample_fn=None,
    stream_extractor=None,
    clone_model_fn=None,
    validate_refine_context_fn=None,
    adapt_group_conditioning_fn=None,
    refine_schedule: RefineSchedule | None = None,
    selected_group_indices: Sequence[int] | None = None,
    temporal_windows_by_group: Mapping[int, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[Any], dict[str, Any], str]:
    """Refine complete physical groups while preserving first-pass audio exactly."""

    validation = validate_second_pass_inputs(video_latents, audio_latents, assembly_plan)
    try:
        resolved_schedule = resolve_refine_schedule(sigmas, refine_schedule)
    except RefineScheduleError as exc:
        raise SecondPassContractError(f"refine schedule is invalid: {exc}") from exc
    effective_sigmas = resolved_schedule.sigmas
    schedule_contract = serializable_schedule_contract(resolved_schedule)
    groups = _contract_groups(assembly_plan)
    selected_indices, selection_active = _normalize_selected_group_indices(
        selected_group_indices,
        len(groups),
    )
    latent_builder = latent_builder or latent_from_cpu
    sample_fn = sample_fn or sample_refine_chunk
    stream_extractor = stream_extractor or extract_av_streams
    refined_videos: list[dict[str, Any]] = (
        list(video_latents) if selection_active else []
    )
    group_seeds: list[int] = []
    conditioning_sources: list[str] = []
    reference_inheritance: list[dict[str, Any]] = []
    group_report_lines: list[str] = []
    routed_first_pass = isinstance(assembly_plan.get("reference_routing_v1"), Mapping)

    def sample_prepared_group(
        group_index,
        video_latent,
        group,
        chunk_model,
        conditioning,
        detail,
    ):
        audio_latent = audio_latents[group_index]
        video_samples = _latent_samples(video_latent, name=f"video_latents[{group_index}]")
        audio_samples = _latent_samples(audio_latent, name=f"audio_latents[{group_index}]")
        conditioning_source = str(detail["conditioning_source"])
        adaptation_stats = detail["adaptation_stats"]
        physical_clip_index = int(detail["physical_clip_index"])
        context_frames = int(detail["context_frames"])
        physical_seed = derive_refine_seed(int(refine_seed), group_index)
        group_seeds.append(physical_seed)
        conditioning_sources.append(conditioning_source)
        route_record = detail.get("reference_routing_v1")
        inheritance = (
            "verified" if conditioning_source == "refine_context" and route_record is not None
            else "not_inherited" if routed_first_pass
            else "not_applicable"
        )
        reference_inheritance.append({
            "physical_group": group_index + 1,
            "status": inheritance,
            "contract_sha256": route_record.get("sha256") if route_record is not None else None,
        })
        nested_latent = latent_builder(video_samples, audio_samples)
        sample_arguments = dict(
            model=chunk_model,
            conditioning=conditioning,
            latent=nested_latent,
            sampler=sampler,
            sigmas=effective_sigmas,
            seed=physical_seed,
            enable_preview=bool(enable_preview),
        )
        if temporal_windows_by_group is not None:
            temporal_window = temporal_windows_by_group.get(group_index)
            if temporal_window is None:
                raise SecondPassContractError(
                    f"selected physical group {group_index + 1} has no temporal window"
                )
            sample_arguments["temporal_window"] = temporal_window
        sampled = sample_fn(**sample_arguments)
        refined_video, _temporary_audio = stream_extractor(sampled)
        if tuple(refined_video.shape) != tuple(video_samples.shape):
            raise SecondPassContractError(
                f"refined video group {group_index} changed B/C/T/H/W geometry"
            )
        if not bool(torch.isfinite(refined_video.float()).all().item()):
            raise SecondPassContractError(
                f"refined video group {group_index} contains NaN or Inf"
            )
        output_latent = dict(video_latent)
        output_latent["samples"] = refined_video
        if selection_active:
            refined_videos[group_index] = output_latent
        else:
            refined_videos.append(output_latent)
        group_report_lines.append(
            "group "
            f"{group_index + 1}: logical_chunks={group.get('logical_chunks')}, "
            f"prompt_policy={group.get('prompt_policy', 'unknown')}, "
            f"conditioning_source={conditioning_source}, "
            f"reference_inheritance={inheritance}, "
            f"physical_clip_index={physical_clip_index}, "
            f"context_frames={context_frames}, "
            f"refine_seed={physical_seed}, shape={tuple(refined_video.shape)}, "
            "sampling_passes=1, temporary_audio_discarded=true"
        )
        if adaptation_stats is not None:
            group_report_lines.append(
                "group "
                f"{group_index + 1} target conditioning: "
                f"keyframes_resized={int(adaptation_stats.get('keyframes_resized', 0))}, "
                f"keyframes_reencoded={int(adaptation_stats.get('keyframes_reencoded', 0))}, "
                f"guide_keyframes_reencoded={int(adaptation_stats.get('guide_keyframes_reencoded', 0))}, "
                f"context_refs_resized={int(adaptation_stats.get('context_refs_resized', 0))}"
            )
            group_report_lines.extend(
                f"WARNING: {warning}"
                for warning in adaptation_stats.get("warnings", ())
            )

    prepared = prepare_physical_refine_groups(
        model=model,
        clip=clip,
        video_latents=video_latents,
        assembly_plan=assembly_plan,
        refine_context=refine_context,
        video_vae=video_vae,
        conditioning_upscale_method=conditioning_upscale_method,
        encode_prompt_fn=encode_prompt_fn,
        clone_model_fn=clone_model_fn,
        validate_refine_context_fn=validate_refine_context_fn,
        adapt_group_conditioning_fn=adapt_group_conditioning_fn,
        group_consumer_fn=sample_prepared_group,
        retain_group_outputs=False,
        selected_group_indices=(selected_indices if selection_active else None),
    )
    if len(group_seeds) != len(selected_indices):
        raise SecondPassContractError(
            "Video refine Sampling count differs from selected physical group count"
        )
    report_lines = [
        "H3 Continuum Second Pass V3.5",
        "Mode: context-aware physical-group refine when a complete First Pass "
        "refine_context is available.",
        f"Physical groups: {validation['physical_group_count']}.",
        "Sampling contract: video random noise/mask=1; audio zero noise/mask=0; "
        "the resolved RefineSchedule SIGMAS are applied directly by Core.",
        "RefineSchedule: "
        f"schema={schedule_contract['schema_version']}, "
        f"mode={schedule_contract['mode']}, "
        f"evaluations={schedule_contract['evaluation_count']}, "
        f"start_sigma={schedule_contract['start_sigma']}, "
        f"end_sigma={schedule_contract['end_sigma']}, "
        f"sigma_hash={schedule_contract['sigma_hash']}.",
        *prepared["warnings"],
        *group_report_lines,
    ]
    if selection_active:
        report_lines.insert(
            3,
            "Selected physical groups: "
            + ", ".join(str(index + 1) for index in selected_indices)
            + "; non-selected groups were exact object passthrough with no "
            "conditioning, MODEL clone, Sampling, or seed derivation.",
        )

    passthrough_audio = passthrough_audio_latents(audio_latents)
    updated_plan = prepared["updated_assembly_plan"]
    contract = updated_plan["second_pass_contract"]
    if conditioning_sources and all(
        source == "refine_context" for source in conditioning_sources
    ):
        contract["execution"] = "context_aware_physical_groups_audio_locked_v3"
    elif any(source == "refine_context" for source in conditioning_sources):
        contract["execution"] = "mixed_context_physical_groups_audio_locked_v3"
    else:
        contract["execution"] = "t2va_physical_groups_audio_locked_v2"
    contract["conditioning_sources"] = conditioning_sources
    if any(item["status"] != "not_applicable" for item in reference_inheritance):
        contract["reference_inheritance"] = reference_inheritance
    contract["refine_seed_base"] = int(refine_seed)
    contract["refine_group_seeds"] = group_seeds
    contract["audio_output"] = "bit_exact_first_pass_passthrough"
    contract["audio_sampling"] = "zero_noise_mask_locked"
    contract["refine_schedule"] = schedule_contract
    contract["refine_schedule_identity"] = schedule_contract["schedule_hash"]
    report_lines.append(
        "Audio output: first-pass physical audio LATENT objects returned bit-exact; "
        "temporary refined audio discarded."
    )
    return refined_videos, passthrough_audio, updated_plan, "\n".join(report_lines)
