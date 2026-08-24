from __future__ import annotations

import pytest
import torch

from ComfyUI_H3_Continuum_Join.nodes import (
    NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS,
)
from ComfyUI_H3_Continuum_Join.v3.hires_fix_nodes import (
    H3ContinuumHiResFixV35,
    resolve_h3_native_latent_target,
)
from ComfyUI_H3_Continuum_Join.v3.second_pass import SecondPassContractError


def _video(marker: str, *, height: int = 4, width: int = 4) -> dict:
    return {
        "samples": torch.zeros((1, 24, 3, height, width)),
        "marker": marker,
    }


def _audio(marker: str) -> dict:
    return {
        "samples": torch.zeros((1, 8, 12)),
        "marker": marker,
    }


def _plan(
    *,
    width: int = 64,
    height: int = 64,
    latent_width: int = 4,
    latent_height: int = 4,
) -> dict:
    return {
        "width": width,
        "height": height,
        "second_pass_contract": {
            "version": 1,
            "physical_groups": [
                {
                    "group_id": 0,
                    "source_width": width,
                    "source_height": height,
                    "source_batch": 1,
                    "latent_channels": 24,
                    "source_latent_t": 3,
                    "source_latent_w": latent_width,
                    "source_latent_h": latent_height,
                }
            ]
        },
    }


def test_disabled_returns_first_pass_objects_without_resize_or_sampling(monkeypatch):
    def unexpected_call(*_args, **_kwargs):
        raise AssertionError("disabled Hi-res fix must not resize or sample")

    monkeypatch.setattr(
        "ComfyUI_H3_Continuum_Join.v3.hires_fix_nodes.resize_video_latents_via_vae",
        unexpected_call,
    )
    monkeypatch.setattr(
        "ComfyUI_H3_Continuum_Join.v3.hires_fix_nodes.run_second_pass_groups",
        unexpected_call,
    )
    videos = [_video("video")]
    audios = [_audio("audio")]
    plan = {"width": 640, "height": 640}

    output_video, output_audio, output_plan, status = H3ContinuumHiResFixV35().apply(
        None,
        None,
        None,
        None,
        videos,
        audios,
        [plan],
        [False],
        ["bislerp"],
        [2.0],
        [7],
        ["must", "not be unwrapped"],
        ["must", "not be unwrapped"],
    )

    assert output_video is videos
    assert output_audio is audios
    assert output_plan is plan
    assert "disabled" in status


def test_enabled_pixel_vae_roundtrip_then_reuses_second_pass_contract(monkeypatch):
    videos = [_video("first-pass", height=40, width=40)]
    resized = [_video("reencoded", height=80, width=80)]
    audios = [_audio("first-pass")]
    plan = _plan(width=640, height=640, latent_width=40, latent_height=40)
    sentinel = (
        [_video("refined")],
        audios,
        {"width": 1280, "height": 1280},
        "sampled",
    )
    calls = []

    def fake_roundtrip(video_latents, assembly_plan, **kwargs):
        calls.append(("roundtrip", video_latents, assembly_plan, kwargs))
        return resized

    def fake_second_pass(**kwargs):
        calls.append(("second_pass", kwargs))
        return sentinel

    monkeypatch.setattr(
        "ComfyUI_H3_Continuum_Join.v3.hires_fix_nodes.resize_video_latents_via_vae",
        fake_roundtrip,
    )
    monkeypatch.setattr(
        "ComfyUI_H3_Continuum_Join.v3.hires_fix_nodes.run_second_pass_groups",
        fake_second_pass,
    )
    monkeypatch.setattr(
        "ComfyUI_H3_Continuum_Join.v3.hires_fix_nodes.h3_core_native_canvas",
        lambda *_args, **_kwargs: (768, 768),
    )

    result = H3ContinuumHiResFixV35().apply(
        ["model"],
        ["clip"],
        ["sampler"],
        [torch.tensor([0.3, 0.0])],
        videos,
        audios,
        [plan],
        [True],
        ["lanczos"],
        [2.0],
        [17],
        [{"context": True}],
        ["video-vae"],
    )

    assert result[:3] == sentinel[:3]
    assert "mode=manual_scale_by" in result[3]
    assert "backend=sequential_pixel_vae_roundtrip" in result[3]
    assert "target=1280x1280" in result[3]
    assert "INFO" in result[3]
    assert calls[0] == (
        "roundtrip",
        videos,
        plan,
        {
            "video_vae": "video-vae",
            "target_width": 1280,
            "target_height": 1280,
            "upscale_method": "lanczos",
        },
    )
    second_pass = calls[1][1]
    assert second_pass["model"] == "model"
    assert second_pass["clip"] == "clip"
    assert second_pass["sampler"] == "sampler"
    assert second_pass["video_latents"] is resized
    assert second_pass["audio_latents"] is audios
    assert second_pass["assembly_plan"] is plan
    assert second_pass["refine_seed"] == 17
    assert second_pass["refine_context"] == {"context": True}
    assert second_pass["video_vae"] == "video-vae"
    assert second_pass["conditioning_upscale_method"] == "bilinear"


def test_native_auto_resizes_to_exact_core_target_then_samples(monkeypatch):
    videos = [_video("first-pass")]
    resized = [_video("native", height=6, width=6)]
    audios = [_audio("first-pass")]
    plan = _plan()
    calls = []

    def fake_roundtrip(video_latents, assembly_plan, **kwargs):
        calls.append(("roundtrip", video_latents, assembly_plan, kwargs))
        return resized

    def fake_second_pass(**kwargs):
        calls.append(("second_pass", kwargs))
        return (
            [_video("refined", height=6, width=6)],
            audios,
            {"width": 96, "height": 96},
            "sampled",
        )

    monkeypatch.setattr(
        "ComfyUI_H3_Continuum_Join.v3.hires_fix_nodes.h3_core_native_canvas",
        lambda *_args, **_kwargs: (96, 96),
    )
    monkeypatch.setattr(
        "ComfyUI_H3_Continuum_Join.v3.hires_fix_nodes.resize_video_latents_via_vae",
        fake_roundtrip,
    )
    monkeypatch.setattr(
        "ComfyUI_H3_Continuum_Join.v3.hires_fix_nodes.run_second_pass_groups",
        fake_second_pass,
    )

    result = H3ContinuumHiResFixV35().apply(
        ["model"],
        ["clip"],
        ["sampler"],
        [torch.tensor([0.3, 0.0])],
        videos,
        audios,
        [plan],
        [True],
        ["bilinear"],
        [0.0],
        [17],
        None,
        ["video-vae"],
    )

    assert calls[0] == (
        "roundtrip",
        videos,
        plan,
        {
            "video_vae": "video-vae",
            "upscale_method": "bilinear",
            "target_width": 96,
            "target_height": 96,
        },
    )
    assert calls[1][1]["video_latents"] is resized
    assert calls[1][1]["conditioning_upscale_method"] == "bilinear"
    assert result[2]["width"] == 96
    assert "mode=h3_native_canvas_auto" in result[3]
    assert "source=64x64" in result[3]
    assert "target=96x96" in result[3]
    assert "WARNING" not in result[3]


def test_native_target_uses_core_canvas_and_never_shrinks_existing_latent():
    source = [_video("source", height=36, width=36)]
    plan = _plan(width=576, height=576, latent_width=36, latent_height=36)

    native = resolve_h3_native_latent_target(
        source,
        plan,
        adapt_canvas_fn=lambda _width, _height: (768, 768),
    )

    assert native["target_latent_width"] == 48
    assert native["target_latent_height"] == 48
    assert native["target_width"] == 768
    assert native["target_height"] == 768
    assert native["preserved_current"] is False

    oversized = [_video("oversized", height=64, width=64)]
    preserved = resolve_h3_native_latent_target(
        oversized,
        plan,
        adapt_canvas_fn=lambda _width, _height: (768, 768),
    )

    assert preserved["target_latent_width"] == 64
    assert preserved["target_latent_height"] == 64
    assert preserved["target_width"] == 1024
    assert preserved["target_height"] == 1024
    assert preserved["preserved_current"] is True


def test_native_target_uses_exact_core_landscape_geometry():
    source = [_video("landscape", height=36, width=64)]
    plan = _plan(width=1024, height=576, latent_width=64, latent_height=36)

    native = resolve_h3_native_latent_target(
        source,
        plan,
        adapt_canvas_fn=lambda _width, _height: (1344, 768),
    )

    assert native["target_latent_width"] == 84
    assert native["target_latent_height"] == 48
    assert native["target_width"] == 1344
    assert native["target_height"] == 768


def test_enabled_requires_video_vae_without_legacy_latent_fallback(monkeypatch):
    def unexpected_call(*_args, **_kwargs):
        raise AssertionError("missing VAE must fail before resize or sampling")

    monkeypatch.setattr(
        "ComfyUI_H3_Continuum_Join.v3.hires_fix_nodes.resize_video_latents_via_vae",
        unexpected_call,
    )
    monkeypatch.setattr(
        "ComfyUI_H3_Continuum_Join.v3.hires_fix_nodes.run_second_pass_groups",
        unexpected_call,
    )

    with pytest.raises(SecondPassContractError, match="requires video_vae"):
        H3ContinuumHiResFixV35().apply(
            ["model"],
            ["clip"],
            ["sampler"],
            [torch.tensor([0.3, 0.0])],
            [_video("first-pass")],
            [_audio("first-pass")],
            [_plan()],
            [True],
            ["lanczos"],
            [2.0],
            [17],
        )


def test_manual_scale_below_one_rejects_before_vae_or_sampling(monkeypatch):
    def unexpected_call(*_args, **_kwargs):
        raise AssertionError("invalid manual scale must fail before expensive work")

    monkeypatch.setattr(
        "ComfyUI_H3_Continuum_Join.v3.hires_fix_nodes.resize_video_latents_via_vae",
        unexpected_call,
    )
    monkeypatch.setattr(
        "ComfyUI_H3_Continuum_Join.v3.hires_fix_nodes.run_second_pass_groups",
        unexpected_call,
    )

    with pytest.raises(SecondPassContractError, match="at least 1.0"):
        H3ContinuumHiResFixV35().apply(
            ["model"],
            ["clip"],
            ["sampler"],
            [torch.tensor([0.3, 0.0])],
            [_video("first-pass")],
            [_audio("first-pass")],
            [_plan()],
            [True],
            ["lanczos"],
            [0.5],
            [17],
            None,
            ["video-vae"],
        )


def test_lazy_inputs_are_requested_only_when_enabled():
    node = H3ContinuumHiResFixV35()

    assert node.check_lazy_status([False]) == []
    assert node.check_lazy_status(
        [False],
        refine_context=[None],
        video_vae=[None],
    ) == []
    assert node.check_lazy_status([True]) == [
        "model",
        "clip",
        "sampler",
        "sigmas",
    ]
    assert node.check_lazy_status(
        [True],
        model=(None,),
        clip=(None,),
        sampler=(None,),
        sigmas=(None,),
    ) == ["model", "clip", "sampler", "sigmas"]
    assert node.check_lazy_status(
        [True],
        model=["model"],
        clip=["clip"],
        sampler=["sampler"],
        sigmas=["sigmas"],
    ) == []
    assert node.check_lazy_status(
        [True],
        model=["model"],
        clip=["clip"],
        sampler=["sampler"],
        sigmas=["sigmas"],
        refine_context=[None],
        video_vae=[None],
    ) == ["refine_context", "video_vae"]


def test_three_v35_nodes_are_registered_with_final_display_names():
    assert NODE_CLASS_MAPPINGS["H3ContinuumHiResFixV35"] is H3ContinuumHiResFixV35
    assert NODE_DISPLAY_NAME_MAPPINGS["H3ContinuumHiResFixV35"] == (
        "H3 Continuum Hi-Res Fix V3.5"
    )
    assert NODE_DISPLAY_NAME_MAPPINGS["H3ContinuumSecondPassV35"] == (
        "H3 Continuum Second Pass V3.5"
    )
    assert NODE_DISPLAY_NAME_MAPPINGS["H3ContinuumLatentResizeV35"] == (
        "H3 Continuum Latent Resize V3.5"
    )
    assert H3ContinuumHiResFixV35.INPUT_IS_LIST is True
    assert H3ContinuumHiResFixV35.OUTPUT_IS_LIST == (True, True, False, False)


def test_hires_fix_schema_exposes_one_node_controls_and_lazy_sampling_inputs():
    schema = H3ContinuumHiResFixV35.INPUT_TYPES()
    required = schema["required"]

    assert required["enabled"][1]["default"] is True
    assert required["upscale_method"][0][0] == "lanczos"
    assert required["upscale_method"][1]["default"] == "lanczos"
    assert required["scale_by"][1] == {
        "default": 2.0,
        "min": 0.0,
        "max": 4.0,
        "step": 0.01,
        "tooltip": (
            "2.0 = validated 2x Pixel/VAE Hi-res Fix. 0 uses the "
            "ComfyUI Core H3 native canvas automatically. Manual "
            "values follow the existing Second Pass contract and must "
            "be 1.0 or greater."
        ),
    }
    assert all(required[name][1]["lazy"] is True for name in (
        "model",
        "clip",
        "sampler",
        "sigmas",
    ))
    assert schema["optional"] == {
        "refine_context": ("H3_CONTINUUM_REFINE_CONTEXT", {"lazy": True}),
        "video_vae": (
            "VAE",
            {
                "lazy": True,
                "tooltip": (
                    "Required while enabled for the safe Pixel/VAE roundtrip; "
                    "not evaluated while disabled."
                ),
            },
        ),
    }
