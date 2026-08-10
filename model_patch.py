"""Per-MODEL ComfyUI wrapper for H3 Continuum Join."""

from __future__ import annotations

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


def _wrapper_factory(*, strict: bool, debug: bool) -> Callable[..., Any]:
    branch_baselines: dict[tuple[Any, ...], tuple[Any, ...]] = {}

    def apply_model_wrapper(executor, *args, **kwargs):
        payload = kwargs.get("minimax_payload")
        if not payload_has_continuum(payload):
            return executor(*args, **kwargs)
        try:
            ensure_native_h3_base_model(executor.class_obj)
            patched_payload = dict(payload)
            patch_layout_in_place(patched_payload, strict=True, debug=debug)
            transformer_options = kwargs.get("transformer_options")
            validate_native_continuity_layout(
                patched_payload,
                transformer_options=(
                    transformer_options if isinstance(transformer_options, dict) else {}
                ),
                branch_baselines=branch_baselines,
            )
            input_x = args[0] if args else None
            materialize_continuum_latents(patched_payload, input_x, debug=debug)
            normalize_condition_latents(patched_payload)
            kwargs["minimax_payload"] = patched_payload
        except (CompatibilityError, LayoutCompatibilityError, KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(f"H3 Continuum Join compatibility failure: {exc}") from exc
        return executor(*args, **kwargs)

    return apply_model_wrapper


def patch_model(model: Any, *, strict: bool, debug: bool):
    try:
        from comfy.patcher_extension import WrappersMP
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"ComfyUI model-wrapper API unavailable: {exc}") from exc
    required_api = ("clone", "add_wrapper_with_key", "remove_wrappers_with_key")
    missing_api = [name for name in required_api if not hasattr(model, name)]
    if missing_api:
        raise RuntimeError(
            "MODEL lacks the wrapper API required by H3 Continuum Join: " + ", ".join(missing_api)
        )
    base_model = getattr(model, "model", None)
    if base_model is None:
        raise RuntimeError("MODEL does not expose the ComfyUI BaseModel")
    ensure_native_h3_base_model(base_model)
    patched = model.clone()
    patched.remove_wrappers_with_key(WrappersMP.APPLY_MODEL, MODEL_WRAPPER_KEY)
    patched.add_wrapper_with_key(
        WrappersMP.APPLY_MODEL,
        MODEL_WRAPPER_KEY,
        _wrapper_factory(strict=bool(strict), debug=bool(debug)),
    )
    model_options = dict(getattr(patched, "model_options", None) or {})
    join_options = dict(model_options.get("h3_continuum_join") or {})
    join_options.update({"api_version": 1, "strict": bool(strict)})
    model_options["h3_continuum_join"] = join_options
    patched.model_options = model_options
    return patched


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
):
    """Create a call-local MODEL and attach an optional read-only Spectrum hint."""
    chunk_model = patch_model(model, strict=bool(strict), debug=bool(debug))
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
