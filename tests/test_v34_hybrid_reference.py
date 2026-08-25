from __future__ import annotations

from types import SimpleNamespace

import torch

from ComfyUI_H3_Continuum_Join.reference import (
    build_hybrid_presentation_items,
    combine_hybrid_visual_identity,
    validate_reference_prompts,
)
from ComfyUI_H3_Continuum_Join.v2.sequence import _conditioning_cache_key


def _image(value: float) -> torch.Tensor:
    return torch.full((1, 2, 2, 3), value, dtype=torch.float32)


def test_hybrid_picture_order_first_last_then_references() -> None:
    first = _image(1.0)
    last = _image(2.0)
    ref1 = _image(3.0)
    ref2 = _image(4.0)
    items = build_hybrid_presentation_items(
        [{"type": "image", "data": ref1}, {"type": "image", "data": ref2}],
        first_image=first,
        last_image=last,
    )
    assert [id(item["data"]) for item in items] == [id(first), id(last), id(ref1), id(ref2)]


def test_hybrid_picture_order_supports_first_only() -> None:
    first = _image(1.0)
    ref = _image(2.0)
    items = build_hybrid_presentation_items(
        [{"type": "image", "data": ref}],
        first_image=first,
    )
    assert [id(item["data"]) for item in items] == [id(first), id(ref)]


def test_hybrid_picture_order_supports_last_only() -> None:
    last = _image(1.0)
    ref = _image(2.0)
    items = build_hybrid_presentation_items(
        [{"type": "image", "data": ref}],
        last_image=last,
    )
    assert [id(item["data"]) for item in items] == [id(last), id(ref)]


def test_hybrid_prompt_validation_offsets_reference_numbers() -> None:
    assert validate_reference_prompts(
        ["<Picture 1> starts the shot and <Picture 3> defines identity."],
        1,
        picture_offset=2,
    ) == ""


def test_hybrid_prompt_validation_keeps_public_picture_numbers_in_warnings() -> None:
    warning = validate_reference_prompts(
        ["<Picture 1> starts the shot and <Picture 4> is unavailable."],
        1,
        picture_offset=2,
    )
    assert "unavailable <Picture 4>" in warning
    assert "connected reference <Picture 3>" in warning
    assert "unavailable <Picture 2>" not in warning


def test_hybrid_prompt_validation_reports_the_missing_reference_number() -> None:
    warning = validate_reference_prompts(
        ["<Picture 1> starts the shot."],
        1,
        picture_offset=2,
    )
    assert "connected reference <Picture 3>" in warning
    assert "the prompt contains no <Picture N> tag" not in warning


def test_pure_fl_identity_is_unchanged() -> None:
    assert combine_hybrid_visual_identity(
        keyframe_identity_hash="fl-identity",
        reference_assets=None,
        has_first=True,
        has_last=True,
    ) == "fl-identity"


def test_pure_reference_identity_is_unchanged() -> None:
    references = SimpleNamespace(combined_hash="reference-identity")
    assert combine_hybrid_visual_identity(
        keyframe_identity_hash="unused",
        reference_assets=references,
        has_first=False,
        has_last=False,
    ) == "reference-identity"


def test_hybrid_identity_uses_keyframes_and_references() -> None:
    references = SimpleNamespace(combined_hash="reference-identity")
    first = combine_hybrid_visual_identity(
        keyframe_identity_hash="keyframe-a",
        reference_assets=references,
        has_first=True,
        has_last=False,
    )
    second = combine_hybrid_visual_identity(
        keyframe_identity_hash="keyframe-b",
        reference_assets=references,
        has_first=True,
        has_last=False,
    )
    assert first != "keyframe-a"
    assert first != "reference-identity"
    assert first != second


def test_hybrid_conditioning_cache_key_reuses_encoded_reference_prompt() -> None:
    references = SimpleNamespace(count=1)
    assert _conditioning_cache_key(
        "final prompt",
        include_last=True,
        reference_assets=references,
    ) == ("final prompt", False)


def test_pure_fl_conditioning_cache_key_keeps_final_frame_variant() -> None:
    assert _conditioning_cache_key(
        "final prompt",
        include_last=True,
        reference_assets=None,
    ) == ("final prompt", True)


def test_pure_reference_conditioning_cache_key_stays_without_last_frame() -> None:
    references = SimpleNamespace(count=1)
    assert _conditioning_cache_key(
        "reference prompt",
        include_last=False,
        reference_assets=references,
    ) == ("reference prompt", False)
