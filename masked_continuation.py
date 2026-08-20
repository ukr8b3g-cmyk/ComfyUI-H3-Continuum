"""Native MiniMax H3 target-latent continuation.

Exact continuation uses ComfyUI Core's native per-token denoise-mask contract
introduced by ComfyUI PR #15375. The previous generated AV latent is copied
into the beginning of the next *target* latent; it is never represented as an
ordinary H3 reference and therefore needs no Continuum RoPE/position-id rewrite.
"""

from __future__ import annotations

from contextlib import contextmanager
import contextvars
import hashlib
from typing import Any

import torch

from .constants import AUDIO_LATENT_FPS, CONTINUITY_FRAMES, FPS, V2_CONTINUITY_AUTO
from .continuation import clone_conditioning
from .state import extract_av_streams, validate_state
from .temporal import context_slots
from .v2.motion import choose_context_frames, latent_motion_score


CONTINUATION_NATIVE_MASKED = "Native Masked — exact continuation (Recommended)"
CONTINUATION_GUIDE = "Guide / Motion Context"
CONTINUATION_METHODS = (CONTINUATION_NATIVE_MASKED, CONTINUATION_GUIDE)
NATIVE_MASK_CONTRACT_VERSION = 1
NATIVE_MASK_CORE_MERGE_COMMIT = "ff6c8a8af144fc9e9e7bc436b1b202f9316848d8"

_CURRENT_METHOD: contextvars.ContextVar[str] = contextvars.ContextVar(
    "h3_continuum_method", default=CONTINUATION_GUIDE
)


class NativeMaskedContinuationError(RuntimeError):
    pass


def validate_continuation_method(value: str) -> str:
    value = str(value)
    if value not in CONTINUATION_METHODS:
        raise NativeMaskedContinuationError(
            f"unknown continuation method: {value!r}; expected one of {CONTINUATION_METHODS!r}"
        )
    return value


@contextmanager
def continuation_method_scope(value: str):
    """Set the invocation-local V3.4 continuation method.

    ContextVar keeps concurrent/re-entrant prompt executions isolated while the
    legacy V2/V3.3 public signatures remain byte-for-byte compatible.
    """

    method = validate_continuation_method(value)
    token = _CURRENT_METHOD.set(method)
    try:
        yield method
    finally:
        _CURRENT_METHOD.reset(token)


def current_continuation_method() -> str:
    return validate_continuation_method(_CURRENT_METHOD.get())


def native_mask_support_issues() -> list[str]:
    """Return missing Core capabilities required by PR #15375."""

    issues: list[str] = []
    try:
        import comfy.model_base as model_base
    except Exception as exc:  # pragma: no cover - broken Comfy install
        return [f"cannot import comfy.model_base: {exc}"]

    base_cls = getattr(model_base, "MiniMaxH3", None)
    if base_cls is None:
        issues.append("comfy.model_base.MiniMaxH3 is missing")
    else:
        for name in (
            "_denoise_mask_conds",
            "_denoise_mask_values",
            "_token_grid_masks",
            "scale_latent_inpaint",
        ):
            if not callable(getattr(base_cls, name, None)):
                issues.append(f"MiniMaxH3.{name} is missing")

    try:
        import comfy.nested_tensor

        if not hasattr(comfy.nested_tensor, "NestedTensor"):
            issues.append("comfy.nested_tensor.NestedTensor is missing")
    except Exception as exc:  # pragma: no cover - broken Comfy install
        issues.append(f"cannot import comfy.nested_tensor: {exc}")
    return issues


def require_native_mask_support() -> None:
    issues = native_mask_support_issues()
    if issues:
        detail = "; ".join(issues)
        raise NativeMaskedContinuationError(
            "Native Masked continuation requires ComfyUI MiniMax-H3 per-token "
            "denoise-mask support from ComfyUI PR #15375 "
            f"(merge commit {NATIVE_MASK_CORE_MERGE_COMMIT}) or newer. "
            f"Update ComfyUI, or select {CONTINUATION_GUIDE!r}. Missing capability: {detail}"
        )


def exact_audio_prefix_steps(context_frames: int) -> int:
    """Map an exact 24-fps video prefix to the 40-Hz H3 audio grid."""

    frames = int(context_frames)
    numerator = frames * int(AUDIO_LATENT_FPS)
    denominator = int(FPS)
    if numerator % denominator:
        raise NativeMaskedContinuationError(
            f"{frames} video frames at {int(FPS)} fps do not land on an exact H3 "
            f"audio-latent boundary at {int(AUDIO_LATENT_FPS)} Hz. Native generated-"
            "audio continuation cannot silently round that boundary. Use 39-frame "
            "continuity, disable generated Audio Continuity, or select Guide / Motion Context."
        )
    return numerator // denominator


def validate_native_masked_request(
    *,
    method: str,
    continuity: str,
    audio_continuity: bool,
    driving_audio_active: bool,
    chunks: int,
) -> None:
    """Reject an impossible exact AV contract before any chunk is sampled.

    Native video-only continuation can use every H3 video context profile. When
    generated audio is also protected, the preserved prefix must end on both the
    24-fps video grid and the 40-Hz audio grid. Auto resolves that requirement to
    39 frames later from the accepted state; explicit 5/22-frame requests are
    invalid and must never be discovered only after chunk 1 has finished.
    """

    method = validate_continuation_method(method)
    if (
        method != CONTINUATION_NATIVE_MASKED
        or int(chunks) <= 1
        or not bool(audio_continuity)
        or bool(driving_audio_active)
        or str(continuity) == V2_CONTINUITY_AUTO
    ):
        return
    frames = CONTINUITY_FRAMES.get(str(continuity))
    if frames is None:
        raise NativeMaskedContinuationError(f"unknown continuity mode: {continuity!r}")
    exact_audio_prefix_steps(int(frames))


def choose_continuation_context_frames(
    *,
    method: str,
    continuity: str,
    state: dict[str, Any],
    audio_continuity: bool,
    driving_audio_active: bool,
) -> tuple[int, float, str]:
    """Resolve context without changing explicit user timing silently."""

    method = validate_continuation_method(method)
    state = validate_state(state)
    if method == CONTINUATION_GUIDE:
        return choose_context_frames(continuity, state)

    carry_generated_audio = bool(audio_continuity) and not bool(driving_audio_active)
    if carry_generated_audio and continuity == V2_CONTINUITY_AUTO:
        capacity = int(state["capacity_frames"])
        if capacity < 39:
            raise NativeMaskedContinuationError(
                "Native Masked generated-audio continuation needs the 39-frame exact "
                f"AV boundary, but this state retains only {capacity} frames. Regenerate "
                "the preceding chunk with normal 39-frame state capacity, disable Audio "
                "Continuity, or select Guide / Motion Context."
            )
        score = latent_motion_score(state)
        return 39, score, "native exact AV boundary (39 video frames = 65 audio steps)"

    context_frames, score, reason = choose_context_frames(continuity, state)
    if carry_generated_audio:
        audio_steps = exact_audio_prefix_steps(context_frames)
        reason = f"{reason}; exact AV boundary ({audio_steps} audio steps)"
    return context_frames, score, reason


def _validate_video_context(video_context: torch.Tensor, context_frames: int) -> int:
    if not torch.is_tensor(video_context) or video_context.ndim != 5:
        raise NativeMaskedContinuationError("video continuation context must be [1,24,T,H,W]")
    if tuple(video_context.shape[:2]) != (1, 24):
        raise NativeMaskedContinuationError("video continuation context must be [1,24,T,H,W]")
    expected = context_slots(int(context_frames))
    if int(video_context.shape[2]) != expected:
        raise NativeMaskedContinuationError(
            f"video context has latent T={int(video_context.shape[2])}; "
            f"{int(context_frames)} frames require T={expected}"
        )
    return expected


def _validate_audio_context(audio_context: torch.Tensor, context_frames: int) -> int:
    if not torch.is_tensor(audio_context) or audio_context.ndim != 4:
        raise NativeMaskedContinuationError("audio continuation context must be [1,32,2,T]")
    if tuple(audio_context.shape[:3]) != (1, 32, 2):
        raise NativeMaskedContinuationError("audio continuation context must be [1,32,2,T]")
    expected = exact_audio_prefix_steps(int(context_frames))
    if int(audio_context.shape[-1]) != expected:
        raise NativeMaskedContinuationError(
            f"audio context has latent T={int(audio_context.shape[-1])}; "
            f"the exact {int(context_frames)}-frame AV boundary requires T={expected}"
        )
    return expected


def apply_native_masked_continuation(
    latent: dict[str, Any],
    *,
    video_context: torch.Tensor,
    audio_context: torch.Tensor | None,
    context_frames: int,
) -> dict[str, Any]:
    """Populate a fresh H3 target prefix and attach Core-native denoise masks.

    The target tensors are intentionally modified in place: ``empty_h3_latent``
    creates them uniquely for this chunk, so cloning the full target would only
    double peak VRAM. Source context tensors are read-only and copied into the
    target; no alias is retained.
    """

    require_native_mask_support()
    if not isinstance(latent, dict) or "samples" not in latent:
        raise NativeMaskedContinuationError("target latent must contain 'samples'")
    video, audio = extract_av_streams(latent)
    video_steps = _validate_video_context(video_context, context_frames)
    if int(video.shape[2]) <= video_steps:
        raise NativeMaskedContinuationError(
            "target video latent contains no generatable region after the preserved prefix"
        )
    if tuple(video.shape[-2:]) != tuple(video_context.shape[-2:]):
        raise NativeMaskedContinuationError(
            "continuation video geometry does not match the new target latent"
        )

    # copy_ performs the required device/dtype conversion without allocating a
    # full second target latent. It does not alias or mutate the CPU source state.
    video[:, :, :video_steps].copy_(video_context)

    # Core's generic MASK contract is float32. Keep it independent of the H3
    # latent precision while retaining the target device and exact 0/1 values.
    video_mask = torch.ones(
        (1, 1, int(video.shape[2]), int(video.shape[3]), int(video.shape[4])),
        device=video.device,
        dtype=torch.float32,
    )
    video_mask[:, :, :video_steps] = 0
    audio_mask = torch.ones(
        (1, 1, int(audio.shape[2]), int(audio.shape[3])),
        device=audio.device,
        dtype=torch.float32,
    )

    if audio_context is not None:
        audio_steps = _validate_audio_context(audio_context, context_frames)
        if int(audio.shape[-1]) <= audio_steps:
            raise NativeMaskedContinuationError(
                "target audio latent contains no generatable region after the preserved prefix"
            )
        audio[..., :audio_steps].copy_(audio_context)
        audio_mask[..., :audio_steps] = 0

    try:
        import comfy.nested_tensor
    except Exception as exc:  # pragma: no cover
        raise NativeMaskedContinuationError(
            f"ComfyUI NestedTensor API unavailable: {exc}"
        ) from exc

    output = dict(latent)
    output["noise_mask"] = comfy.nested_tensor.NestedTensor((video_mask, audio_mask))
    return output


def prepare_masked_conditioning(
    conditioning,
    *,
    context_frames: int,
    new_frame_count: int,
):
    """Remove target keyframes that compete with the protected prefix.

    Ordinary Ref2VA image/video/audio references are preserved. A final-frame
    keyframe remains valid because it lies outside the protected prefix. Driving
    Audio is attached after this function and therefore remains the audio
    authority when that mode is active.
    """

    output = clone_conditioning(conditioning)
    for _, metadata in output:
        kept = []
        for raw in metadata.get("minimax_keyframes") or ():
            keyframe = dict(raw)
            frame_index = int(keyframe.get("resolved_frame_index", 0))
            if 0 <= frame_index < int(context_frames):
                continue
            kept.append(keyframe)
        if kept:
            metadata["minimax_keyframes"] = kept
        else:
            metadata.pop("minimax_keyframes", None)
        metadata["minimax_frame_count"] = int(new_frame_count)
    return output


def continuation_storage_plan(prompt_plan: dict[str, Any], method: str) -> dict[str, Any]:
    """Salt only continuation-chunk fingerprints with backend semantics.

    Chunk 1 has no continuation prefix, so its hash remains reusable across
    Guide/Native method changes. Chunks 2+ carry a self-describing hash salt;
    Run Storage can therefore reuse an unaffected first chunk from an older
    revision while never accepting a Guide chunk as Native Masked (or a future
    mask-contract version as v1).
    """

    method = validate_continuation_method(method)
    if method == CONTINUATION_GUIDE:
        return prompt_plan
    result = dict(prompt_plan)
    hashes = list(prompt_plan["hashes"])
    for index in range(1, len(hashes)):
        payload = (
            f"{hashes[index]}\0continuation={method}\0"
            f"native_mask_contract={NATIVE_MASK_CONTRACT_VERSION}"
        ).encode("utf-8")
        hashes[index] = (
            f"h3c-native-mask-v{NATIVE_MASK_CONTRACT_VERSION}:"
            + hashlib.sha256(payload).hexdigest()
        )
    result["hashes"] = hashes
    return result


def plan_continuation_contract(plan: dict[str, Any], method: str) -> dict[str, Any]:
    result = dict(plan)
    method = validate_continuation_method(method)
    result["continuation_method"] = method
    if method == CONTINUATION_NATIVE_MASKED:
        result["native_mask_contract_version"] = NATIVE_MASK_CONTRACT_VERSION
    return result


def stored_plan_matches_method(plan: dict[str, Any], method: str, *, chunk_number: int) -> bool:
    """Compatibility predicate for explicit Session reuse."""

    method = validate_continuation_method(method)
    if int(chunk_number) <= 1:
        return True
    stored = plan.get("continuation_method")
    if method == CONTINUATION_GUIDE:
        # Pre-feature sessions are the legacy Guide architecture.
        return stored in (None, CONTINUATION_GUIDE)
    return (
        stored == CONTINUATION_NATIVE_MASKED
        and int(plan.get("native_mask_contract_version", -1))
        == NATIVE_MASK_CONTRACT_VERSION
    )