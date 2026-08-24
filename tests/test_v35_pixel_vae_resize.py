from __future__ import annotations

import pytest
import torch
import torch.nn.functional as F

from ComfyUI_H3_Continuum_Join.v3.pixel_vae_resize import (
    PIXEL_UPSCALE_METHODS,
    PixelVaeResizeError,
    resolve_pixel_latent_scale,
    resize_video_latents_via_vae,
)


def _plan(
    *,
    temporals=(3, 5),
    batch=1,
    scale_width=6,
    scale_height=4,
) -> dict:
    latent_width = 3
    latent_height = 2
    width = latent_width * scale_width
    height = latent_height * scale_height
    return {
        "width": width,
        "height": height,
        "second_pass_contract": {
            "version": 1,
            "physical_groups": [
                {
                    "group_id": position,
                    "source_width": width,
                    "source_height": height,
                    "source_batch": batch,
                    "latent_channels": 24,
                    "source_latent_t": temporal,
                    "source_latent_h": latent_height,
                    "source_latent_w": latent_width,
                }
                for position, temporal in enumerate(temporals)
            ],
        },
    }


def _latents(temporals=(3, 5), *, batch=1) -> list[dict]:
    return [
        {
            "samples": torch.full(
                (batch, 24, temporal, 2, 3),
                float(position + 1),
            ),
            "marker": f"group-{position}",
        }
        for position, temporal in enumerate(temporals)
    ]


class _RoundTripVae:
    def __init__(self, log, *, scale_width=6, scale_height=4):
        self.log = log
        self.scale_width = scale_width
        self.scale_height = scale_height
        self.pending_temporal = None
        self.pending_batches = 0

    def decode(self, samples):
        temporal = int(samples.shape[2])
        assert self.pending_temporal is None
        assert self.pending_batches == 0
        self.pending_temporal = temporal
        self.pending_batches = int(samples.shape[0])
        self.log.append(("decode", temporal, tuple(samples.shape)))
        frames = temporal * 2 + 1
        return torch.full(
            (int(samples.shape[0]), frames, 8, 18, 3),
            float(temporal),
        )

    def encode(self, pixels):
        temporal = self.pending_temporal
        assert temporal is not None
        assert pixels.ndim == 4
        assert self.pending_batches > 0
        self.log.append(("encode", temporal, tuple(pixels.shape)))
        self.pending_batches -= 1
        if self.pending_batches == 0:
            self.pending_temporal = None
        return torch.full(
            (
                1,
                24,
                temporal,
                int(pixels.shape[1]) // self.scale_height,
                int(pixels.shape[2]) // self.scale_width,
            ),
            float(temporal),
        )


def test_plan_derives_non_hardcoded_pixel_latent_scale() -> None:
    assert resolve_pixel_latent_scale(
        _plan(scale_width=6, scale_height=4)
    ) == (6, 4)


def test_sequential_roundtrip_preserves_groups_bct_metadata_and_input() -> None:
    log = []
    vae = _RoundTripVae(log)
    inputs = _latents()
    original_samples = [item["samples"] for item in inputs]

    def upscale(samples, width, height, method, crop):
        log.append(("upscale", tuple(samples.shape), width, height, method, crop))
        assert samples.ndim == 4
        return F.interpolate(samples, size=(height, width), mode="bilinear")

    outputs = resize_video_latents_via_vae(
        inputs,
        _plan(),
        video_vae=vae,
        target_width=36,
        target_height=16,
        upscale_method="lanczos",
        upscale_fn=upscale,
    )

    assert [tuple(item["samples"].shape) for item in outputs] == [
        (1, 24, 3, 4, 6),
        (1, 24, 5, 4, 6),
    ]
    assert [item["marker"] for item in outputs] == ["group-0", "group-1"]
    assert all(
        output is not source
        for output, source in zip(outputs, inputs, strict=True)
    )
    assert all(
        item["samples"] is original
        for item, original in zip(inputs, original_samples, strict=True)
    )
    assert all(output["samples"].device.type == "cpu" for output in outputs)
    assert all(torch.isfinite(output["samples"]).all() for output in outputs)
    assert log == [
        ("decode", 3, (1, 24, 3, 2, 3)),
        ("upscale", (7, 3, 8, 18), 36, 16, "lanczos", "disabled"),
        ("encode", 3, (7, 16, 36, 3)),
        ("decode", 5, (1, 24, 5, 2, 3)),
        ("upscale", (8, 3, 8, 18), 36, 16, "lanczos", "disabled"),
        ("upscale", (3, 3, 8, 18), 36, 16, "lanczos", "disabled"),
        ("encode", 5, (11, 16, 36, 3)),
    ]


def test_core_4d_encode_boundary_preserves_continuum_batch() -> None:
    log = []
    vae = _RoundTripVae(log)

    outputs = resize_video_latents_via_vae(
        _latents((3,), batch=2),
        _plan(temporals=(3,), batch=2),
        video_vae=vae,
        target_width=36,
        target_height=16,
        upscale_method="lanczos",
        upscale_fn=lambda samples, width, height, *_args: F.interpolate(
            samples, size=(height, width), mode="bilinear"
        ),
    )

    assert tuple(outputs[0]["samples"].shape) == (2, 24, 3, 4, 6)
    assert [entry for entry in log if entry[0] == "encode"] == [
        ("encode", 3, (7, 16, 36, 3)),
        ("encode", 3, (7, 16, 36, 3)),
    ]


def test_each_core_encode_batch_is_validated_before_concat() -> None:
    class BadSecondBatchVae(_RoundTripVae):
        def __init__(self):
            super().__init__([])
            self.encode_calls = 0

        def encode(self, pixels):
            encoded = super().encode(pixels)
            self.encode_calls += 1
            if self.encode_calls == 2:
                return torch.zeros((1, 24, 4, 4, 6))
            return encoded

    with pytest.raises(PixelVaeResizeError, match="for batch 1"):
        resize_video_latents_via_vae(
            _latents((3,), batch=2),
            _plan(temporals=(3,), batch=2),
            video_vae=BadSecondBatchVae(),
            target_width=36,
            target_height=16,
            upscale_fn=lambda samples, width, height, *_args: F.interpolate(
                samples, size=(height, width), mode="bilinear"
            ),
        )


def test_lanczos_is_a_supported_pixel_method() -> None:
    assert PIXEL_UPSCALE_METHODS == (
        "nearest-exact",
        "bilinear",
        "area",
        "bicubic",
        "bislerp",
        "lanczos",
    )


def test_decode_requires_core_video_image_layout() -> None:
    class BadDecode:
        def decode(self, _samples):
            return torch.zeros((1, 8, 18, 3))

        def encode(self, _pixels):
            raise AssertionError("encode must not run")

    with pytest.raises(PixelVaeResizeError, match=r"\[B,F,H,W,C\]"):
        resize_video_latents_via_vae(
            _latents((3,)),
            _plan(temporals=(3,)),
            video_vae=BadDecode(),
            target_width=36,
            target_height=16,
            upscale_fn=lambda *args: args[0],
        )


def test_encode_rejects_changed_bct_or_target_geometry() -> None:
    class BadEncode(_RoundTripVae):
        def encode(self, pixels):
            temporal = self.pending_temporal
            assert temporal is not None
            return torch.zeros((1, 24, temporal + 1, 4, 6))

    with pytest.raises(PixelVaeResizeError, match="changed B/C/T"):
        resize_video_latents_via_vae(
            _latents((3,)),
            _plan(temporals=(3,)),
            video_vae=BadEncode([]),
            target_width=36,
            target_height=16,
            upscale_fn=lambda samples, width, height, *_args: F.interpolate(
                samples, size=(height, width), mode="bilinear"
            ),
        )


def test_target_geometry_uses_plan_ratio_and_must_be_aligned() -> None:
    class MustNotRun:
        def decode(self, _samples):
            raise AssertionError("decode must not run")

        def encode(self, _pixels):
            raise AssertionError("encode must not run")

    with pytest.raises(PixelVaeResizeError, match="plan-derived latent scale"):
        resize_video_latents_via_vae(
            _latents((3,)),
            _plan(temporals=(3,)),
            video_vae=MustNotRun(),
            target_width=35,
            target_height=16,
            upscale_fn=lambda *args: args[0],
        )


def test_manual_target_is_not_independently_restricted_to_upscale_only() -> None:
    outputs = resize_video_latents_via_vae(
        _latents((3,)),
        _plan(temporals=(3,)),
        video_vae=_RoundTripVae([]),
        target_width=12,
        target_height=4,
        upscale_method="bilinear",
        upscale_fn=lambda samples, width, height, *_args: F.interpolate(
            samples, size=(height, width), mode="bilinear"
        ),
    )

    assert tuple(outputs[0]["samples"].shape) == (1, 24, 3, 1, 2)


def test_vae_failure_propagates_without_latent_fallback() -> None:
    sentinel = RuntimeError("VAE encode sentinel")

    class FailingVae(_RoundTripVae):
        def encode(self, _pixels):
            raise sentinel

    with pytest.raises(RuntimeError) as captured:
        resize_video_latents_via_vae(
            _latents((3,)),
            _plan(temporals=(3,)),
            video_vae=FailingVae([]),
            target_width=36,
            target_height=16,
            upscale_fn=lambda samples, width, height, *_args: F.interpolate(
                samples, size=(height, width), mode="bilinear"
            ),
        )

    assert captured.value is sentinel


@pytest.mark.parametrize("stage", ["decode", "resize", "encode"])
def test_nonfinite_values_are_rejected_at_each_stage(stage) -> None:
    class NonFiniteVae(_RoundTripVae):
        def decode(self, samples):
            pixels = super().decode(samples)
            if stage == "decode":
                pixels[0, 0, 0, 0, 0] = torch.nan
            return pixels

        def encode(self, pixels):
            encoded = super().encode(pixels)
            if stage == "encode":
                encoded[0, 0, 0, 0, 0] = torch.inf
            return encoded

    def upscale(samples, width, height, *_args):
        output = F.interpolate(samples, size=(height, width), mode="bilinear")
        if stage == "resize":
            output[0, 0, 0, 0] = torch.nan
        return output

    with pytest.raises(PixelVaeResizeError, match="NaN or Inf"):
        resize_video_latents_via_vae(
            _latents((3,)),
            _plan(temporals=(3,)),
            video_vae=NonFiniteVae([]),
            target_width=36,
            target_height=16,
            upscale_fn=upscale,
        )
