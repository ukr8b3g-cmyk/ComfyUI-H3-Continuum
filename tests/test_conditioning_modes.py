import pytest

from ComfyUI_H3_Continuum_Join.conditioning import (
    conditioning_mode_from_presence,
)


@pytest.mark.parametrize(
    ("has_first", "has_last", "has_reference", "expected"),
    [
        (False, False, False, "t2va"),
        (True, False, False, "i2va"),
        (False, True, False, "last_only"),
        (True, True, False, "fl2va"),
        (False, False, True, "reference"),
        (True, False, True, "i2va"),
        (False, True, True, "last_only"),
        (True, True, True, "fl2va"),
    ],
)
def test_conditioning_mode_matrix(
    has_first, has_last, has_reference, expected
):
    assert conditioning_mode_from_presence(
        has_first=has_first,
        has_last=has_last,
        has_reference=has_reference,
    ) == expected


def test_references_augment_keyframe_mode_instead_of_overriding_it():
    assert conditioning_mode_from_presence(
        has_first=True,
        has_last=False,
        has_reference=True,
    ) == "i2va"
    assert conditioning_mode_from_presence(
        has_first=False,
        has_last=True,
        has_reference=True,
    ) == "last_only"
    assert conditioning_mode_from_presence(
        has_first=True,
        has_last=True,
        has_reference=True,
    ) == "fl2va"
