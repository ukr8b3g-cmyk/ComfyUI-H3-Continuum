from __future__ import annotations

import pytest
import torch

from ComfyUI_H3_Continuum_Join.reference import (
    REFERENCE_SIZE_MATCH_OUTPUT,
    ReferenceAssets,
    ReferenceConditioningError,
    prepare_reference_assets,
    validate_reference_prompts,
)
from ComfyUI_H3_Continuum_Join.v3.nodes import _validate_reference_checkpoint


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


def test_reference_socket_rejects_image_batches():
    with pytest.raises(ReferenceConditioningError, match="batch size B=1"):
        prepare_reference_assets(
            reference_image_1=torch.zeros((2, 32, 32, 3)),
            reference_image_2=None,
            output_width=32,
            output_height=32,
            size_mode=REFERENCE_SIZE_MATCH_OUTPUT,
        )


def _reference_prompt(checkpoint_name: str) -> dict:
    return {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": checkpoint_name},
        },
        "2": {
            "class_type": "H3ContinuumSamplerProduction",
            "inputs": {"model": ["1", 0]},
        },
    }


def test_strict_reference_requires_ref2va_checkpoint():
    assert _validate_reference_checkpoint(
        _reference_prompt("minimax_h3_ref2va_pruned_int8.safetensors"),
        "2",
        strict_compatibility=True,
    ) == "ref2va"
    with pytest.raises(ValueError, match="FL2VA checkpoint"):
        _validate_reference_checkpoint(
            _reference_prompt("minimax_h3_fl2va_pruned_int8.safetensors"),
            "2",
            strict_compatibility=True,
        )
    assert _validate_reference_checkpoint(
        _reference_prompt("minimax_h3_fl2va_pruned_int8.safetensors"),
        "2",
        strict_compatibility=False,
    ) == "fl2va"
