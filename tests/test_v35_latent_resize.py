from __future__ import annotations

import torch
import torch.nn.functional as F

from ComfyUI_H3_Continuum_Join.nodes import NODE_CLASS_MAPPINGS
from ComfyUI_H3_Continuum_Join.v3.latent_resize_nodes import (
    H3ContinuumLatentResizeV35,
    UPSCALE_METHODS,
    resize_video_latents,
    resize_video_latents_to_size,
)


def _latent(shape: tuple[int, ...], *, marker: str) -> dict:
    return {
        "samples": torch.arange(torch.tensor(shape).prod().item(), dtype=torch.float32).reshape(shape),
        "marker": marker,
    }


def _test_upscale(samples, width, height, upscale_method, crop):
    assert crop == "disabled"
    original = samples.shape
    flattened = samples.movedim(2, 1).reshape(
        -1,
        original[1],
        original[-2],
        original[-1],
    )
    mode = "bilinear" if upscale_method == "bislerp" else upscale_method
    output = F.interpolate(flattened, size=(height, width), mode=mode)
    return output.reshape((original[0], -1, original[1], height, width)).movedim(
        2,
        1,
    )


def test_resize_preserves_physical_groups_bct_order_and_metadata() -> None:
    inputs = [
        _latent((1, 24, 37, 4, 5), marker="group-1"),
        _latent((1, 24, 77, 4, 5), marker="group-2"),
    ]

    outputs = resize_video_latents(
        inputs,
        upscale_method="bilinear",
        scale_by=2.0,
        upscale_fn=_test_upscale,
    )

    assert [item["samples"].shape for item in outputs] == [
        (1, 24, 37, 8, 10),
        (1, 24, 77, 8, 10),
    ]
    assert [item["marker"] for item in outputs] == ["group-1", "group-2"]
    assert all(after is not before for before, after in zip(inputs, outputs, strict=True))
    assert [item["samples"].shape for item in inputs] == [
        (1, 24, 37, 4, 5),
        (1, 24, 77, 4, 5),
    ]


def test_resize_delegates_dimensions_method_and_crop_to_core_boundary() -> None:
    latent = _latent((1, 24, 3, 4, 5), marker="core")
    calls = []

    def capture(samples, width, height, upscale_method, crop):
        calls.append((samples, width, height, upscale_method, crop))
        return _test_upscale(samples, width, height, upscale_method, crop)

    output = resize_video_latents(
        [latent],
        upscale_method="bicubic",
        scale_by=1.5,
        upscale_fn=capture,
    )[0]

    assert calls == [(latent["samples"], 8, 6, "bicubic", "disabled")]
    assert output["samples"].shape == (1, 24, 3, 6, 8)


def test_resize_to_exact_latent_geometry_preserves_groups_and_metadata() -> None:
    inputs = [
        _latent((1, 24, 37, 4, 5), marker="group-1"),
        _latent((1, 24, 77, 4, 5), marker="group-2"),
    ]

    outputs = resize_video_latents_to_size(
        inputs,
        upscale_method="bilinear",
        target_width=9,
        target_height=7,
        upscale_fn=_test_upscale,
    )

    assert [item["samples"].shape for item in outputs] == [
        (1, 24, 37, 7, 9),
        (1, 24, 77, 7, 9),
    ]
    assert [item["marker"] for item in outputs] == ["group-1", "group-2"]


def test_bislerp_preserves_dtype_and_returns_finite_video_latent() -> None:
    latent = {"samples": torch.randn((1, 24, 2, 3, 3), dtype=torch.float32)}
    output = resize_video_latents(
        [latent],
        upscale_method="bislerp",
        scale_by=2.0,
        upscale_fn=_test_upscale,
    )[0]["samples"]

    assert output.shape == (1, 24, 2, 6, 6)
    assert output.dtype == latent["samples"].dtype
    assert torch.isfinite(output).all()


def test_latent_resize_node_is_registered_and_core_compatible() -> None:
    node_class = NODE_CLASS_MAPPINGS["H3ContinuumLatentResizeV35"]
    assert node_class is H3ContinuumLatentResizeV35
    assert node_class.DEPRECATED is False
    assert node_class.INPUT_IS_LIST is True
    assert node_class.OUTPUT_IS_LIST == (True,)
    assert list(UPSCALE_METHODS) == [
        "nearest-exact",
        "bilinear",
        "area",
        "bicubic",
        "bislerp",
    ]


def test_node_unwraps_widget_lists_but_preserves_physical_latent_list(monkeypatch) -> None:
    monkeypatch.setitem(
        H3ContinuumLatentResizeV35.resize.__globals__,
        "resize_video_latents",
        lambda video_latents, **kwargs: resize_video_latents(
            video_latents,
            upscale_fn=_test_upscale,
            **kwargs,
        ),
    )
    inputs = [_latent((1, 24, 2, 2, 2), marker="one")]
    (outputs,) = H3ContinuumLatentResizeV35().resize(
        inputs,
        ["nearest-exact"],
        [2.0],
    )

    assert len(outputs) == 1
    assert outputs[0]["samples"].shape == (1, 24, 2, 4, 4)
    assert outputs[0]["marker"] == "one"
