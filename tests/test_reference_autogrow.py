from __future__ import annotations

import inspect

import torch

from ComfyUI_H3_Continuum_Join.reference import (
    REFERENCE_SIZE_MATCH_OUTPUT,
    prepare_reference_assets,
    validate_reference_prompts,
)
from ComfyUI_H3_Continuum_Join.v3 import nodes as v3_nodes
from ComfyUI_H3_Continuum_Join.v3.nodes import H3ContinuumSamplerProduction


def test_reference_assets_accept_eight_images_in_connection_order():
    images = [
        torch.full((1, 32, 32, 3), index / 8.0)
        for index in range(8)
    ]
    assets = prepare_reference_assets(
        reference_image_1=images[0],
        reference_image_2=images[1],
        reference_image_3=images[2],
        reference_image_4=images[3],
        reference_image_5=images[4],
        reference_image_6=images[5],
        reference_image_7=images[6],
        reference_image_8=images[7],
        output_width=32,
        output_height=32,
        size_mode=REFERENCE_SIZE_MATCH_OUTPUT,
    )

    assert assets is not None
    assert assets.count == 8
    assert len(assets.image_hashes) == 8
    assert all(
        torch.equal(actual, expected)
        for actual, expected in zip(assets.images, images, strict=True)
    )
    assert validate_reference_prompts(
        [" ".join(f"<Picture {index}>" for index in range(1, 9))],
        8,
    ) == ""


def test_sparse_reference_inputs_still_compact_contiguously():
    fourth = torch.full((1, 32, 32, 3), 0.5)
    eighth = torch.ones((1, 32, 32, 3))
    assets = prepare_reference_assets(
        reference_image_1=None,
        reference_image_2=None,
        reference_image_3=None,
        reference_image_4=fourth,
        reference_image_8=eighth,
        output_width=32,
        output_height=32,
        size_mode=REFERENCE_SIZE_MATCH_OUTPUT,
    )

    assert assets is not None
    assert assets.count == 2
    assert torch.equal(assets.images[0], fourth)
    assert torch.equal(assets.images[1], eighth)


def test_production_sampler_declares_and_accepts_all_eight_reference_inputs():
    optional = H3ContinuumSamplerProduction.INPUT_TYPES()["optional"]
    for index in range(1, 9):
        name = f"reference_image_{index}"
        assert optional[name][0] == "IMAGE"

    signature = inspect.signature(H3ContinuumSamplerProduction.run)
    for index in range(1, 9):
        assert f"reference_image_{index}" in signature.parameters
    assert not any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    )


def test_reference_autogrow_does_not_restore_filename_checkpoint_classification():
    assert not hasattr(v3_nodes, "_validate_reference_checkpoint")
