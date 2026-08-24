from __future__ import annotations

from collections.abc import Mapping

import pytest
import torch

from ComfyUI_H3_Continuum_Join.constants import MARK_VIDEO_CONTEXT
from ComfyUI_H3_Continuum_Join.v3 import refine_context as rc


def _upscale(samples, width, height, method, crop):
    del method, crop
    return torch.nn.functional.interpolate(
        samples, size=(height, width), mode="nearest"
    )


def _conditioning():
    text = torch.arange(6, dtype=torch.float32, device="cpu").reshape(1, 2, 3)
    first = torch.full((1, 24, 1, 2, 3), 1.0)
    last = torch.full((1, 24, 1, 2, 3), 2.0)
    ordinary_video = torch.full((1, 24, 2, 4, 5), 3.0)
    ordinary_audio = torch.full((1, 32, 2, 7), 4.0)
    context_video = torch.arange(1 * 24 * 2 * 2 * 3, dtype=torch.float32).reshape(
        1, 24, 2, 2, 3
    )
    context_audio = torch.full((1, 32, 2, 9), 5.0)
    return [
        [
            text,
            {
                "minimax_token_tags": torch.tensor([1, 0]),
                "minimax_frame_count": 124,
                "minimax_keyframes": [
                    {"resolved_frame_index": 0, "latent": first},
                    {"resolved_frame_index": 123, "latent": last},
                ],
                "minimax_refs": [
                    {
                        "kind": "video_audio",
                        "latent_t": 2,
                        "latent_h": 4,
                        "latent_w": 5,
                        "latent": ordinary_video,
                        "ref_audio_t": 7,
                        "audio_latent": ordinary_audio,
                    },
                    {
                        "kind": "video_audio",
                        "latent_t": 2,
                        "latent_h": 2,
                        "latent_w": 3,
                        "latent": context_video,
                        "ref_audio_t": 9,
                        "audio_latent": context_audio,
                        MARK_VIDEO_CONTEXT: True,
                    },
                ],
            },
        ]
    ]


def _group(**overrides):
    values = {
        "conditioning": _conditioning(),
        "group_id": 0,
        "logical_chunks": [1],
        "physical_frames": 124,
        "prompt_policy": "single",
        "physical_prompt": "prompt",
        "source_video_shape": (1, 24, 37, 2, 3),
        "physical_clip_index": 1,
        "context_frames": 0,
        "first_image": torch.ones((1, 32, 48, 3)),
        "last_image": torch.zeros((1, 32, 48, 3)),
    }
    values.update(overrides)
    return rc.make_refine_group(**values)


def test_freeze_conditioning_owns_cpu_tensors_and_immutable_containers():
    source = _conditioning()
    frozen = rc.freeze_conditioning(source)
    assert isinstance(frozen, tuple)
    assert isinstance(frozen[0], tuple)
    assert isinstance(frozen[0][1], Mapping)
    assert isinstance(frozen[0][1]["minimax_refs"], tuple)
    assert frozen[0][0].device.type == "cpu"
    assert frozen[0][0] is not source[0][0]
    assert frozen[0][0].data_ptr() != source[0][0].data_ptr()
    source[0][0].fill_(99)
    source[0][1]["minimax_refs"][0]["audio_latent"].fill_(99)
    assert not bool((frozen[0][0] == 99).any())
    assert not bool(
        (frozen[0][1]["minimax_refs"][0]["audio_latent"] == 99).any()
    )
    with pytest.raises(TypeError):
        frozen[0][1]["new"] = True


def test_adapt_resizes_keyframes_and_only_marked_video_context(monkeypatch):
    monkeypatch.setattr(rc, "_common_upscale", _upscale)
    group = _group(first_image=None, last_image=None)
    frozen_meta = group["conditioning"][0][1]
    ordinary_ref = frozen_meta["minimax_refs"][0]
    context_ref = frozen_meta["minimax_refs"][1]
    ordinary_video = ordinary_ref["latent"]
    ordinary_audio = ordinary_ref["audio_latent"]
    context_audio = context_ref["audio_latent"]

    adapted, stats = rc.adapt_group_conditioning(group, 4, 6)
    metadata = adapted[0][1]
    assert adapted[0][0] is group["conditioning"][0][0]
    assert [tuple(item["latent"].shape[-2:]) for item in metadata["minimax_keyframes"]] == [
        (4, 6),
        (4, 6),
    ]
    assert metadata["minimax_refs"][0] is ordinary_ref
    assert metadata["minimax_refs"][0]["latent"] is ordinary_video
    assert metadata["minimax_refs"][0]["audio_latent"] is ordinary_audio
    assert tuple(metadata["minimax_refs"][1]["latent"].shape[-2:]) == (4, 6)
    expected_context = torch.nn.functional.interpolate(
        context_ref["latent"].permute(0, 2, 1, 3, 4).reshape(2, 24, 2, 3),
        size=(4, 6),
        mode="nearest",
    ).reshape(1, 2, 24, 4, 6).permute(0, 2, 1, 3, 4)
    assert torch.equal(metadata["minimax_refs"][1]["latent"], expected_context)
    assert metadata["minimax_refs"][1]["latent_h"] == 4
    assert metadata["minimax_refs"][1]["latent_w"] == 6
    assert metadata["minimax_refs"][1]["audio_latent"] is context_audio
    assert context_ref["latent_h"] == 2
    assert context_ref["latent_w"] == 3
    assert tuple(context_ref["latent"].shape[-2:]) == (2, 3)
    assert stats["keyframes_latent_fallback"] == 2
    assert stats["context_refs_resized"] == 1
    assert len(stats["warnings"]) == 2


class _FakeVAE:
    def __init__(self):
        self.inputs = []

    def encode(self, image):
        self.inputs.append(image.clone())
        batch, height, width, _ = image.shape
        return torch.full((batch, 24, 1, height // 16, width // 16), len(self.inputs))


def test_keyframes_reencode_images_with_core_first_last_crop_rules(monkeypatch):
    calls = []

    def upscale(samples, width, height, method, crop):
        calls.append((width, height, method, crop))
        return torch.nn.functional.interpolate(samples, size=(height, width), mode="nearest")

    monkeypatch.setattr(rc, "_common_upscale", upscale)
    vae = _FakeVAE()
    adapted, stats = rc.adapt_group_conditioning(_group(), 4, 6, video_vae=vae)
    keyframes = adapted[0][1]["minimax_keyframes"]
    assert torch.all(keyframes[0]["latent"] == 1)
    assert torch.all(keyframes[1]["latent"] == 2)
    assert calls[:2] == [
        (96, 64, "lanczos", "disabled"),
        (96, 64, "lanczos", "center"),
    ]
    assert stats["keyframes_reencoded"] == 2
    assert stats["keyframes_latent_fallback"] == 0
    assert stats["warnings"] == ()


def test_context_validation_matches_physical_group_assembly_contract():
    group = _group()
    context = rc.make_refine_context(
        [group],
        source_width=48,
        source_height=32,
        conditioning_mode="fl2va",
    )
    plan = {
        "width": 48,
        "height": 32,
        "second_pass_contract": {
            "physical_groups": [
                {
                    "group_id": 0,
                    "logical_chunks": [1],
                    "physical_frames": 124,
                    "prompt_policy": "single",
                    "physical_prompt": "prompt",
                    "trim_prefix_frames": 0,
                    "source_batch": 1,
                    "latent_channels": 24,
                    "source_latent_t": 37,
                    "source_latent_h": 2,
                    "source_latent_w": 3,
                }
            ]
        },
    }
    assert rc.validate_refine_context(context, plan) is context
    assert context["groups"] == (group,)
    assert context["complete"] is True
    bad = {**plan, "width": 64}
    with pytest.raises(rc.RefineContextError, match="dimensions differ"):
        rc.validate_refine_context(context, bad)


def test_incomplete_context_may_be_empty_but_complete_context_may_not():
    context = rc.make_refine_context(
        [],
        source_width=48,
        source_height=32,
        conditioning_mode="t2va",
        complete=False,
        notes=("Run Storage reused groups were not recaptured",),
    )
    assert context["groups"] == ()
    assert context["notes"]
    partial = rc.make_refine_context(
        [
            _group(
                logical_chunks=[3],
                physical_clip_index=3,
            )
        ],
        source_width=48,
        source_height=32,
        conditioning_mode="t2va",
        complete=False,
    )
    # Partial ids are capture-local.  They must not be paired by index with a
    # plan group, because an earlier Run Storage group may be absent.
    plan = {
        "width": 48,
        "height": 32,
        "second_pass_contract": {"physical_groups": [{"logical_chunks": [1]}]},
    }
    assert rc.validate_refine_context(partial, plan) is partial
    with pytest.raises(rc.RefineContextError, match="no physical groups"):
        rc.make_refine_context(
            [],
            source_width=48,
            source_height=32,
            conditioning_mode="t2va",
            complete=True,
        )
