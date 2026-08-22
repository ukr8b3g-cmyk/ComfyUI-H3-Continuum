from __future__ import annotations

import pytest

from ComfyUI_H3_Continuum_Join.conditioning import (
    conditioning_display_label,
    conditioning_mode_from_presence,
)


@pytest.mark.parametrize(
    ("has_first", "has_last", "has_reference", "expected"),
    [
        (False, False, False, "T2VA + Continuation"),
        (True, False, False, "I2VA + Continuation"),
        (False, True, False, "Last Frame + Continuation"),
        (True, True, False, "FL2VA + Continuation"),
        (False, False, True, "Reference + Continuation"),
        (True, False, True, "Hybrid I2VA + Reference + Continuation"),
        (False, True, True, "Hybrid L2VA + Reference + Continuation"),
        (True, True, True, "Hybrid FL2VA + Reference + Continuation"),
    ],
)
def test_conditioning_display_label_matrix(
    has_first: bool,
    has_last: bool,
    has_reference: bool,
    expected: str,
) -> None:
    assert (
        conditioning_display_label(
            has_first=has_first,
            has_last=has_last,
            has_reference=has_reference,
        )
        == expected
    )


@pytest.mark.parametrize(
    ("has_first", "has_last"),
    [
        (True, False),
        (False, True),
        (True, True),
    ],
)
def test_hybrid_display_does_not_change_internal_reference_mode(
    has_first: bool,
    has_last: bool,
) -> None:
    assert (
        conditioning_mode_from_presence(
            has_first=has_first,
            has_last=has_last,
            has_reference=True,
        )
        == "reference"
    )