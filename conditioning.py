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
    if has_reference:
        return CONDITIONING_MODE_REFERENCE
    if has_first and has_last:
        return CONDITIONING_MODE_FL2VA
    if has_first:
        return CONDITIONING_MODE_I2VA
    if has_last:
        return CONDITIONING_MODE_LAST_ONLY
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


def conditioning_display_label(
    *,
    has_first: bool,
    has_last: bool,
    has_reference: bool,
) -> str:
    """Return a user-facing label without changing the runtime mode contract."""
    if has_reference:
        if has_first and has_last:
            return "Hybrid FL2VA + Reference + Continuation"
        if has_first:
            return "Hybrid I2VA + Reference + Continuation"
        if has_last:
            return "Hybrid L2VA + Reference + Continuation"
        return "Reference + Continuation"
    mode = conditioning_mode_from_presence(
        has_first=has_first,
        has_last=has_last,
        has_reference=False,
    )
    return conditioning_mode_label(mode)


def conditioning_mode_display_label(
    mode: str,
    *,
    has_first: bool = False,
    has_last: bool = False,
    has_reference: bool = False,
) -> str:
    """Legacy display helper retained for existing callers and tests."""
    if has_first or has_last or has_reference:
        return conditioning_display_label(
            has_first=has_first,
            has_last=has_last,
            has_reference=has_reference,
        )
    return conditioning_mode_label(mode)


def conditioning_mode_uses_video_vae(mode: str) -> bool:
    if mode not in CONDITIONING_MODES:
        raise ValueError(f"unknown conditioning mode: {mode!r}")
    return mode != CONDITIONING_MODE_T2VA
