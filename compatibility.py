"""ComfyUI native-H3 and accelerator compatibility checks."""

from __future__ import annotations

import inspect
from typing import Any, Iterable


class CompatibilityError(RuntimeError):
    """Raised when a MODEL is not the supported native MiniMax H3 runtime."""


def _missing_callable_parameters(
    callable_obj: Any,
    *,
    positional: Iterable[str] = (),
    keywords: Iterable[str] = (),
) -> list[str]:
    """Return parameters that a callable can no longer accept.

    Compatibility wrappers are allowed to replace a concrete signature with
    ``*args``/``**kwargs``.  Sol-Attn's MiniMax-H3 Morton integration does this
    for ``PackedLayout.__init__`` while transparently forwarding the original
    arguments.  Treating the wrapped signature as an API removal produces a
    false incompatibility even though construction remains valid.

    Explicit parameters are preferred when available.  ``*args`` satisfies
    missing positional parameters and ``**kwargs`` satisfies missing keyword
    parameters.  If ``inspect.signature`` itself is unavailable, the caller
    still receives the exception and may fail closed.
    """

    params = inspect.signature(callable_obj).parameters
    has_var_positional = any(
        parameter.kind is inspect.Parameter.VAR_POSITIONAL
        for parameter in params.values()
    )
    has_var_keyword = any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in params.values()
    )

    missing: list[str] = []
    for name in positional:
        if name not in params and not has_var_positional:
            missing.append(name)
    for name in keywords:
        if name not in params and not has_var_keyword:
            missing.append(name)
    return missing


def check_comfy_h3_runtime() -> list[str]:
    """Return human-readable incompatibilities with ComfyUI's native H3 API.

    The check deliberately validates public/runtime contracts only. It does not
    import optional accelerators and therefore cannot make their installation a
    hard dependency.
    """

    issues: list[str] = []
    try:
        import comfy.ldm.minimax.model as h3_model
    except Exception as exc:  # pragma: no cover - requires a broken Comfy install
        return [f"cannot import native MiniMax H3: {exc}"]

    layout_cls = getattr(h3_model, "PackedLayout", None)
    model_cls = getattr(h3_model, "MiniMaxH3Model", None)
    if layout_cls is None:
        issues.append("PackedLayout is missing")
    else:
        try:
            missing = _missing_callable_parameters(
                layout_cls.__init__,
                positional=(
                    "text_len",
                    "latent_t",
                    "latent_h",
                    "latent_w",
                    "audio_t",
                ),
                keywords=(
                    "keyframes",
                    "refs",
                    "frame_count",
                ),
            )
            for name in missing:
                issues.append(f"PackedLayout no longer accepts '{name}'")
        except (TypeError, ValueError) as exc:
            issues.append(f"cannot inspect PackedLayout: {exc}")

    if model_cls is None:
        issues.append("MiniMaxH3Model is missing")
    else:
        for name in (
            "forward",
            "rope_freqs",
            "_cond_video_rows",
            "_cond_audio_rows",
        ):
            if not hasattr(model_cls, name):
                issues.append(f"MiniMaxH3Model.{name} is missing")

    if tuple(getattr(h3_model, "FRAME_PER_TOKEN", ())) != (1, 4, 4, 4, 4):
        issues.append("MiniMax H3 temporal compression grid changed")

    try:
        import comfy.model_base as model_base

        base_cls = getattr(model_base, "MiniMaxH3", None)
        if base_cls is None or not hasattr(base_cls, "extra_conds"):
            issues.append("native MiniMaxH3 BaseModel.extra_conds is missing")
    except Exception as exc:
        issues.append(f"cannot inspect MiniMaxH3 BaseModel: {exc}")

    try:
        from comfy.patcher_extension import WrappersMP

        for name in ("APPLY_MODEL", "DIFFUSION_MODEL"):
            if not hasattr(WrappersMP, name):
                issues.append(f"WrappersMP.{name} is missing")
    except Exception as exc:
        issues.append(f"cannot import model wrapper API: {exc}")

    try:
        import comfy.nested_tensor

        if not hasattr(comfy.nested_tensor, "NestedTensor"):
            issues.append("comfy.nested_tensor.NestedTensor is missing")
    except Exception as exc:
        issues.append(f"cannot import NestedTensor API: {exc}")
    return issues



def run_native_layout_self_test() -> str:
    """Exercise the installed native H3 PackedLayout without loading a model.

    This catches the most dangerous class of upstream change: a layout that can
    still be constructed but no longer maps reference/target rows the way the
    Continuum adapter expects.
    """

    import torch
    import comfy.ldm.minimax.model as h3_model

    from .constants import (
        MARK_AUDIO_CONTEXT,
        MARK_AUDIO_END_FRAME,
        MARK_AUDIO_OVERHANG,
        MARK_CONTEXT_FRAMES,
        MARK_VIDEO_CONTEXT,
    )
    from .layout_adapter import normalize_condition_latents, patch_layout_in_place

    video = torch.zeros(1, 24, 2, 2, 2)  # five-frame context
    audio = torch.zeros(1, 32, 2, 8)
    ref = {
        "kind": "video_audio",
        "latent_t": 2,
        "latent_h": 2,
        "latent_w": 2,
        "ref_audio_t": 8,
        "latent": video,
        "audio_latent": audio,
        MARK_VIDEO_CONTEXT: True,
        MARK_CONTEXT_FRAMES: 5,
        MARK_AUDIO_CONTEXT: True,
        MARK_AUDIO_END_FRAME: 5.0,
        MARK_AUDIO_OVERHANG: -1.0 / 3.0,
    }
    layout = h3_model.PackedLayout(
        3, 7, 2, 2, 10, keyframes=None, refs=[ref], frame_count=22
    )
    position_id = id(layout.position_ids)
    payload = {"layout": layout, "keyframes": [], "refs": [ref]}
    normalize_condition_latents(payload)
    result = patch_layout_in_place(payload, strict=True, debug=False)
    if id(layout.position_ids) != position_id:
        raise CompatibilityError("layout self-test replaced position_ids")
    ref_video = next((a, b) for a, b, kind in layout.segments if kind == "ref_img")
    target_video = next((a, b) for a, b, kind in layout.segments if kind == "video")
    ra, rb = ref_video
    va, _vb = target_video
    if not torch.equal(layout.position_ids[ra:rb], layout.position_ids[va : va + (rb - ra)]):
        raise CompatibilityError("layout self-test could not align video context")
    return (
        f"native PackedLayout self-test passed; rows={layout.position_ids.shape[0]}, "
        f"position_ids_id={result['position_ids_id']}"
    )

def ensure_native_h3_base_model(base_model: Any) -> None:
    """Validate a ComfyUI BaseModel instance before adding our wrapper."""

    inner = getattr(base_model, "diffusion_model", None)
    if inner is None:
        raise CompatibilityError("MODEL does not expose diffusion_model")
    actual = f"{type(inner).__module__}.{type(inner).__name__}"
    if actual != "comfy.ldm.minimax.model.MiniMaxH3Model":
        raise CompatibilityError(f"native MiniMaxH3Model required; got {actual}")
    missing = [
        name
        for name in (
            "blocks",
            "final_layer",
            "patch_size",
            "latents_dim",
            "audio_latents_dim",
            "rope_freqs",
        )
        if not hasattr(inner, name)
    ]
    if missing:
        raise CompatibilityError(
            "MiniMaxH3Model contract changed; missing " + ", ".join(missing)
        )


def _wrapper_keys(model: Any) -> tuple[str, ...]:
    """Collect ModelPatcher wrapper keys without depending on enum values."""

    wrappers = getattr(model, "wrappers", {}) or {}
    found: list[str] = []
    if not isinstance(wrappers, dict):
        return ()
    for group in wrappers.values():
        if not isinstance(group, dict):
            continue
        found.extend(str(key) for key in group.keys())
    return tuple(found)


def _contains_any(values: Iterable[str], *needles: str) -> bool:
    text = " ".join(values).lower()
    return any(needle.lower() in text for needle in needles)


def accelerator_summary(model: Any) -> str:
    """Best-effort, non-authoritative summary of attached accelerators.

    Optional custom nodes expose different public markers across releases. The
    summary therefore reports only what is observable and never gates execution.
    """

    options = getattr(model, "model_options", {}) or {}
    transformer = options.get("transformer_options", {}) or {}
    wrapper_keys = _wrapper_keys(model)
    parts: list[str] = []

    if _contains_any(wrapper_keys, "spectrum"):
        parts.append("Spectrum wrapper detected")

    sol_marker = transformer.get("sol_compose") is not None or _contains_any(
        wrapper_keys, "sol_attn", "sol-attn", "solattn"
    )
    if sol_marker:
        parts.append("Sol-Attn marker detected")

    if transformer.get("optimized_attention_override") is not None:
        if sol_marker:
            parts.append("chained attention override present (Sage/other fallback possible)")
        else:
            parts.append("attention override present (Sage/other)")

    if options.get("h3_continuum_join"):
        parts.append("Continuum APPLY_MODEL wrapper installed")

    return "; ".join(parts) if parts else "accelerator markers not detected (informational only)"
