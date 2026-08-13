from __future__ import annotations

import pytest
import torch

from ComfyUI_H3_Continuum_Join.reference import (
    REFERENCE_SIZE_MATCH_OUTPUT,
    ReferenceAssets,
    ReferenceConditioningError,
    validate_reference_prompts,
)


def test_reference_size_is_appended_after_v31_widgets():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "v3" / "nodes.py").read_text(
        encoding="utf-8"
    )
    production = source.split("class H3ContinuumSamplerProduction", 1)[1]
    required = production.split('"optional": {', 1)[0]
    assert required.index('"run_name"') < required.index('"reference_size"')


def _assets(count: int = 2) -> ReferenceAssets:
    images = tuple(torch.zeros((1, 32, 32, 3)) for _ in range(count))
    hashes = tuple(str(index) * 64 for index in range(1, count + 1))
    return ReferenceAssets(
        images=images,
        latents=tuple(None for _ in range(count)),
        image_hashes=hashes,
        combined_hash="a" * 64,
        size_mode=REFERENCE_SIZE_MATCH_OUTPUT,
    )


def test_reference_contract_contains_metadata_only():
    contract = _assets().contract
    assert contract["count"] == 2
    assert contract["size_mode"] == REFERENCE_SIZE_MATCH_OUTPUT
    assert contract["image_hashes"] == ["1" * 64, "2" * 64]
    assert not any(torch.is_tensor(value) for value in contract.values())


def test_picture_tags_must_match_connected_references():
    assert validate_reference_prompts(["Use <Picture 1> and <Picture 2>."], 2) == ""
    with pytest.raises(ReferenceConditioningError, match="Picture 2"):
        validate_reference_prompts(["Use <Picture 2>."], 1)


def test_missing_picture_tag_is_a_warning_not_an_error():
    warning = validate_reference_prompts(["The same person walks forward."], 1)
    assert "no <Picture N> tag" in warning
