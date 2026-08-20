from __future__ import annotations

from typing import Any


CONDITIONING_MODE_T2VA = "t2va"
CONDITIONING_MODE_I2VA = "i2va"
CONDITIONING_MODE_LAST_ONLY = "last_only"
CONDITIONING_MODE_FL2VA = "fl2va"
CONDITIONING_MODE_REFERENCE = "reference"

CONDITIONING_MODES = frozenset(
    {
        CONDITIONING_MODE_T2VA,
        CONDITIONING_MODE_I2VA,
        CONDITIONING_MODE_LAST_ONLY,
        CONDITIONING_MODE_FL2VA,
        CONDITIONING_MODE_REFERENCE,
    }
)

_MODE_LABELS = {
    CONDITIONING_MODE_T2VA: "T2VA + Continuation",
    CONDITIONING_MODE_I2VA: "I2VA + Continuation",
    CONDITIONING_MODE_LAST_ONLY: "Last Frame + Continuation",
    CONDITIONING_MODE_FL2VA: "FL2VA + Continuation",
    CONDITIONING_MODE_REFERENCE: "Reference + Continuation",
}


def conditioning_mode_from_presence(
    *, has_first: bool, has_last: bool, has_reference: bool
) -> str:
    """Classify the temporal keyframe task while allowing reference augmentation.

    MiniMax H3 reference blocks and first/last keyframes are orthogonal pieces of
    conditioning. Core can start from Reference-to-Video conditioning and layer
    keyframe guides on top, so a connected reference must not erase First/Last
    semantics. Keeping the temporal keyframe mode when keyframes are present also
    makes Run Storage fingerprint those keyframes while the separate reference
    contract fingerprints the reference assets.
    """

    if has_first and has_last:
        return CONDITIONING_MODE_FL2VA
    if has_first:
        return CONDITIONING_MODE_I2VA
    if has_last:
        return CONDITIONING_MODE_LAST_ONLY
    if has_reference:
        return CONDITIONING_MODE_REFERENCE
    return CONDITIONING_MODE_T2VA


def detect_conditioning_mode(
    *, first_frame: Any, last_frame: Any, reference_assets: Any
) -> str:
    return conditioning_mode_from_presence(
        has_first=first_frame is not None,
        has_last=last_frame is not None,
        has_reference=reference_assets is not None,
    )


def conditioning_mode_label(mode: str) -> str:
    try:
        return _MODE_LABELS[str(mode)]
    except KeyError as exc:
        raise ValueError(f"unknown conditioning mode: {mode!r}") from exc


def conditioning_mode_uses_video_vae(mode: str) -> bool:
    if mode not in CONDITIONING_MODES:
        raise ValueError(f"unknown conditioning mode: {mode!r}")
    return mode != CONDITIONING_MODE_T2VA
