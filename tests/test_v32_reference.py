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
from ComfyUI_H3_Continuum_Join.reference_audio import validate_reference_audio_prompts
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


@pytest.mark.parametrize("count", (1, 2))
def test_v322_reference_contract_json_is_golden_compatible(count):
    hashes = [str(index) * 64 for index in range(1, count + 1)]
    assert _assets(count).contract == {
        "reference_contract_version": 1,
        "count": count,
        "size_mode": REFERENCE_SIZE_MATCH_OUTPUT,
        "image_hashes": hashes,
        "combined_hash": "a" * 64,
    }


def test_v323_third_reference_adds_only_the_image_3_extension():
    contract = _assets(3).contract
    assert set(contract) == {
        "reference_contract_version",
        "count",
        "size_mode",
        "image_hashes",
        "combined_hash",
        "reference_image_3",
    }
    assert contract["reference_image_3"] == {
        "reference_position": 3,
        "shape": [1, 32, 32, 3],
        "dtype": "torch.float32",
        "sha256": "3" * 64,
        "preprocess_version": 1,
    }


def test_unavailable_picture_tags_warn_without_stopping_like_core():
    assert validate_reference_prompts(["Use <Picture 1> and <Picture 2>."], 2) == ""
    message = validate_reference_prompts(["Use <Picture 2>."], 1)
    assert "H3C-P102" in message
    assert "only 1 active reference image(s) reached the Sampler" in message
    assert "generation will continue" in message
    assert "ignored or hallucinated" in message
    message = validate_reference_prompts(["Use <Picture 3>."], 2)
    assert "unavailable <Picture 3>" in message
    assert "generation will continue" in message


def test_missing_picture_tag_is_a_warning_not_an_error():
    warning = validate_reference_prompts(["The same person walks forward."], 1)
    assert "H3C-P103" in warning
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


def test_reference_image_3_rejects_image_batches():
    with pytest.raises(ReferenceConditioningError, match="batch size B=1"):
        prepare_reference_assets(
            reference_image_1=torch.zeros((1, 32, 32, 3)),
            reference_image_2=torch.zeros((1, 32, 32, 3)),
            reference_image_3=torch.zeros((2, 32, 32, 3)),
            output_width=32,
            output_height=32,
            size_mode=REFERENCE_SIZE_MATCH_OUTPUT,
        )


def test_three_reference_images_are_ordered_and_contiguous():
    assets = prepare_reference_assets(
        reference_image_1=torch.zeros((1, 32, 32, 3)),
        reference_image_2=torch.ones((1, 32, 32, 3)),
        reference_image_3=torch.full((1, 32, 32, 3), 0.5),
        output_width=32,
        output_height=32,
        size_mode=REFERENCE_SIZE_MATCH_OUTPUT,
    )
    assert assets is not None
    assert assets.count == 3
    assert validate_reference_prompts(["Use <Picture 1>, <Picture 2>, and <Picture 3>."], 3) == ""


def test_reference_image_gaps_are_compacted_like_core():
    first = torch.zeros((1, 32, 32, 3))
    third = torch.ones((1, 32, 32, 3))
    assets = prepare_reference_assets(
        reference_image_1=first,
        reference_image_2=None,
        reference_image_3=third,
        output_width=32,
        output_height=32,
        size_mode=REFERENCE_SIZE_MATCH_OUTPUT,
    )
    assert assets is not None
    assert len(assets.images) == 2
    assert torch.equal(assets.images[0], first)
    assert torch.equal(assets.images[1], third)


def test_reference_image_2_alone_becomes_picture_1_like_core():
    second = torch.ones((1, 32, 32, 3))
    assets = prepare_reference_assets(
        reference_image_1=None,
        reference_image_2=second,
        reference_image_3=None,
        output_width=32,
        output_height=32,
        size_mode=REFERENCE_SIZE_MATCH_OUTPUT,
    )
    assert assets is not None
    assert len(assets.images) == 1
    assert torch.equal(assets.images[0], second)


def test_unavailable_audio_tags_warn_without_stopping_like_core():
    message = validate_reference_audio_prompts(
        ["Perform <Audio 1> and <Audio 2>."], None
    )
    assert "unavailable <Audio 1>" in message
    assert "H3C-P102" in message
    assert "unavailable <Audio 2>" in message
    assert "generation will continue" in message


def test_connected_audio_keeps_unavailable_extra_tag_as_warning():
    message = validate_reference_audio_prompts(
        ["Perform <Audio 2>."], object()
    )
    assert "unavailable <Audio 2>" in message
    assert "no <Audio 1> tag" in message
    assert "H3C-P103" in message


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


def test_reference_checkpoint_classification_is_diagnostic_only():
    assert _validate_reference_checkpoint(
        _reference_prompt("minimax_h3_ref2va_pruned_int8.safetensors"),
        "2",
        strict_compatibility=True,
    ) == "ref2va"
    assert _validate_reference_checkpoint(
        _reference_prompt("minimax_h3_fl2va_pruned_int8.safetensors"),
        "2",
        strict_compatibility=True,
    ) == "fl2va"
    assert _validate_reference_checkpoint(
        _reference_prompt("minimax_h3_unknown.safetensors"),
        "2",
        strict_compatibility=True,
    ) == "unknown"
