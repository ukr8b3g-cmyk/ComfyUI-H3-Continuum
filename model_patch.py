"""Per-MODEL ComfyUI wrapper for H3 Continuum Join."""

from __future__ import annotations


import logging
import time
from typing import Any, Callable

from .compatibility import CompatibilityError, ensure_native_h3_base_model
from .constants import (
    CONTINUUM_ACTUAL_PREFIX_STEPS,
    CONTINUUM_INTEROP_API,
    CONTINUUM_INTEROP_KEY,
    MODEL_WRAPPER_KEY,
)
from .layout_adapter import (
    LayoutCompatibilityError,
    materialize_continuum_latents,
    normalize_condition_latents,
    patch_layout_in_place,
    payload_has_continuum,
    validate_native_continuity_layout,
)


class LayoutValidationProfiler:
    """Detailed-only wall-time accounting for the current full validator."""

    def __init__(self, *, route_markers: str):
        self.route_markers = str(route_markers)
        self.validation_calls = 0
        self.full_validation_count = 0
        self.cumulative_wall_seconds = 0.0
        self.status_counts: dict[str, int] = {}
        self.failed_validation_count = 0
        self.sampled_physical_groups = 0
        self.sampling_steps_total = 0
        self.validated_sampling_steps = 0
        self._groups: list[dict[str, Any]] = []

    def record_validation(
        self,
        result: dict[str, Any] | None,
        wall_seconds: float,
        *,
        full_validation: bool,
        failed: bool = False,
    ) -> None:
        self.validation_calls += 1
        self.full_validation_count += int(bool(full_validation))
        self.cumulative_wall_seconds += max(0.0, float(wall_seconds))
        if failed:
            self.failed_validation_count += 1
            return
        status = str((result or {}).get("status", "unknown"))
        self.status_counts[status] = self.status_counts.get(status, 0) + 1

    def begin_sampling_group(
        self,
        *,
        physical_group: int,
        logical_chunks: tuple[int, ...],
        sampling_steps: int,
    ) -> dict[str, Any]:
        return {
            "physical_group": int(physical_group),
            "logical_chunks": tuple(int(value) for value in logical_chunks),
            "sampling_steps": max(0, int(sampling_steps)),
            "validation_calls": self.validation_calls,
            "full_validation_count": self.full_validation_count,
            "cumulative_wall_seconds": self.cumulative_wall_seconds,
        }

    def finish_sampling_group(self, token: dict[str, Any]) -> None:
        sampling_steps = int(token["sampling_steps"])
        validation_calls = self.validation_calls - int(token["validation_calls"])
        full_validations = self.full_validation_count - int(
            token["full_validation_count"]
        )
        wall_seconds = self.cumulative_wall_seconds - float(
            token["cumulative_wall_seconds"]
        )
        self.sampled_physical_groups += 1
        self.sampling_steps_total += sampling_steps
        if validation_calls:
            self.validated_sampling_steps += sampling_steps
        self._groups.append(
            {
                "physical_group": int(token["physical_group"]),
                "logical_chunks": tuple(token["logical_chunks"]),
                "sampling_steps": sampling_steps,
                "validation_calls": validation_calls,
                "full_validation_count": full_validations,
                "wall_seconds": max(0.0, wall_seconds),
            }
        )

    def report_lines(self) -> list[str]:
        validated_steps = self.validated_sampling_steps
        calls_per_step = (
            self.validation_calls / validated_steps if validated_steps else 0.0
        )
        wall_ms_per_step = (
            self.cumulative_wall_seconds * 1000.0 / validated_steps
            if validated_steps
            else 0.0
        )
        mean_ms_per_call = (
            self.cumulative_wall_seconds * 1000.0 / self.validation_calls
            if self.validation_calls
            else 0.0
        )
        status_text = ",".join(
            f"{name}={count}" for name, count in sorted(self.status_counts.items())
        ) or "none"
        route_markers = self.route_markers.replace(";", " |")
        lines = [
            "Layout validation profile [V3.6]: "
            f"route_markers={route_markers}; "
            f"validation_calls={self.validation_calls}; "
            f"full_validation_count={self.full_validation_count}; "
            f"failed_validation_count={self.failed_validation_count}; "
            f"statuses={status_text}; "
            "cumulative_wall_including_existing_device_to_host_sync="
            f"{self.cumulative_wall_seconds:.6f}s; "
            f"sampled_physical_groups={self.sampled_physical_groups}; "
            f"sampling_steps_total={self.sampling_steps_total}; "
            f"validated_sampling_steps={validated_steps}; "
            f"calls_per_validated_step={calls_per_step:.3f}; "
            f"wall_per_validated_step={wall_ms_per_step:.3f}ms; "
            f"mean_wall_per_call={mean_ms_per_call:.3f}ms; "
            "explicit_cuda_synchronize=not_used."
        ]
        for group in self._groups:
            group_steps = int(group["sampling_steps"])
            group_calls = int(group["validation_calls"])
            group_wall = float(group["wall_seconds"])
            group_calls_per_step = group_calls / group_steps if group_steps else 0.0
            group_wall_per_step = (
                group_wall * 1000.0 / group_steps if group_steps else 0.0
            )
            lines.append(
                "Layout validation group [V3.6]: "
                f"physical_group={group['physical_group']}; "
                f"logical_chunks={list(group['logical_chunks'])}; "
                f"sampling_steps={group_steps}; "
                f"validation_calls={group_calls}; "
                f"full_validation_count={group['full_validation_count']}; "
                f"cumulative_wall={group_wall:.6f}s; "
                f"calls_per_step={group_calls_per_step:.3f}; "
                f"wall_per_step={group_wall_per_step:.3f}ms."
            )
        return lines


def _wrapper_factory(
    *,
    strict: bool,
    debug: bool,
    validation_profiler: LayoutValidationProfiler | None = None,
) -> Callable[..., Any]:
    branch_baselines: dict[tuple[Any, ...], tuple[Any, ...]] = {}

    def apply_model_wrapper(executor, *args, **kwargs):
        payload = kwargs.get("minimax_payload")
        has_continuum = payload_has_continuum(payload)
        has_mixed_keyframe_refs = (
            isinstance(payload, dict)
            and bool(payload.get("keyframes"))
            and payload.get("refs") is not None
        )
        if not has_continuum and not has_mixed_keyframe_refs:
            return executor(*args, **kwargs)
        try:
            try:
                ensure_native_h3_base_model(executor.class_obj)
            except CompatibilityError as exc:
                logging.getLogger(__name__).warning(
                    "H3 Continuum could not pre-classify this model; continuing with "
                    "ComfyUI runtime validation: %s",
                    exc,
                )
            patched_payload = dict(payload)
            if has_continuum:
                patch_layout_in_place(patched_payload, strict=True, debug=debug)
                transformer_options = kwargs.get("transformer_options")
                validation_started = (
                    time.perf_counter() if validation_profiler is not None else None
                )
                try:
                    validation_result = validate_native_continuity_layout(
                        patched_payload,
                        transformer_options=(
                            transformer_options
                            if isinstance(transformer_options, dict)
                            else {}
                        ),
                        branch_baselines=branch_baselines,
                    )
                except Exception:
                    if validation_profiler is not None and validation_started is not None:
                        validation_profiler.record_validation(
                            None,
                            time.perf_counter() - validation_started,
                            full_validation=True,
                            failed=True,
                        )
                    raise
                if validation_profiler is not None and validation_started is not None:
                    validation_profiler.record_validation(
                        validation_result,
                        time.perf_counter() - validation_started,
                        full_validation=True,
                    )
                input_x = args[0] if args else None
                materialize_continuum_latents(patched_payload, input_x, debug=debug)
            # ComfyUI Core 0.33.1 replaces keyframe condition latents with
            # reference latents when both contracts are present. Rebuild the
            # combined list for First/Last Frame + standalone Reference Audio.
            normalize_condition_latents(patched_payload)
            kwargs["minimax_payload"] = patched_payload
        except (CompatibilityError, LayoutCompatibilityError, KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(f"H3 Continuum Join compatibility failure: {exc}") from exc
        return executor(*args, **kwargs)

    return apply_model_wrapper


def configure_continuum_model(
    model: Any,
    *,
    strict: bool,
    debug: bool,
    validation_profiler: LayoutValidationProfiler | None = None,
):
    try:
        from comfy.patcher_extension import WrappersMP
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"ComfyUI model-wrapper API unavailable: {exc}") from exc
    required_api = ("add_wrapper_with_key", "remove_wrappers_with_key")
    missing_api = [name for name in required_api if not hasattr(model, name)]
    if missing_api:
        raise RuntimeError(
            "MODEL lacks the wrapper API required by H3 Continuum Join: " + ", ".join(missing_api)
        )
    base_model = getattr(model, "model", None)
    if base_model is None:
        raise RuntimeError("MODEL does not expose the ComfyUI BaseModel")
    try:
        ensure_native_h3_base_model(base_model)
    except CompatibilityError as exc:
        logging.getLogger(__name__).warning(
            "H3 Continuum could not pre-classify this model; installing the wrapper "
            "and deferring compatibility to ComfyUI runtime validation: %s",
            exc,
        )
    patched = model
    patched.remove_wrappers_with_key(WrappersMP.APPLY_MODEL, MODEL_WRAPPER_KEY)
    patched.add_wrapper_with_key(
        WrappersMP.APPLY_MODEL,
        MODEL_WRAPPER_KEY,
        _wrapper_factory(
            strict=bool(strict),
            debug=bool(debug),
            validation_profiler=validation_profiler,
        ),
    )
    model_options = dict(getattr(patched, "model_options", None) or {})
    join_options = dict(model_options.get("h3_continuum_join") or {})
    join_options.update({"api_version": 1, "strict": bool(strict)})
    model_options["h3_continuum_join"] = join_options
    patched.model_options = model_options
    return patched

def patch_model(
    model: Any,
    *,
    strict: bool,
    debug: bool,
    validation_profiler: LayoutValidationProfiler | None = None,
):
    """Clone once, then install the Continuum wrapper on that clone."""
    if not hasattr(model, "clone"):
        raise RuntimeError(
            "MODEL lacks the wrapper API required by H3 Continuum Join: clone"
        )
    return configure_continuum_model(
        model.clone(),
        strict=strict,
        debug=debug,
        validation_profiler=validation_profiler,
    )

def continuum_interop_request(*, chunk_index: int, context_frames: int) -> dict[str, Any]:
    return {
        "api": CONTINUUM_INTEROP_API,
        "active": True,
        "min_actual_prefix_steps": CONTINUUM_ACTUAL_PREFIX_STEPS,
        "chunk_index": int(chunk_index),
        "context_frames": int(context_frames),
    }


def clone_model_for_chunk(
    model: Any,
    *,
    strict: bool,
    debug: bool,
    chunk_index: int,
    context_frames: int | None,
    validation_profiler: LayoutValidationProfiler | None = None,
):
    """Create a call-local MODEL and attach an optional read-only Spectrum hint."""
    if not hasattr(model, "clone"):
        raise RuntimeError(
            "MODEL lacks the wrapper API required by H3 Continuum Join: clone"
        )
    chunk_model = model.clone()
    configure_continuum_model(
        chunk_model,
        strict=bool(strict),
        debug=bool(debug),
        validation_profiler=validation_profiler,
    )
    if debug:
        parent = getattr(chunk_model, "parent", None)
        logging.getLogger(__name__).info(
            "Continuum model lifetime: input=%s chunk=%s parent=%s base=%s",
            id(model),
            id(chunk_model),
            id(parent) if parent is not None else None,
            id(getattr(chunk_model, "model", None)),
        )
    model_options = dict(getattr(chunk_model, "model_options", None) or {})
    transformer_options = dict(model_options.get("transformer_options") or {})
    if context_frames is None:
        transformer_options.pop(CONTINUUM_INTEROP_KEY, None)
    else:
        transformer_options[CONTINUUM_INTEROP_KEY] = continuum_interop_request(
            chunk_index=int(chunk_index), context_frames=int(context_frames)
        )
    model_options["transformer_options"] = transformer_options
    chunk_model.model_options = model_options
    return chunk_model
