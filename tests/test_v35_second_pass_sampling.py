from __future__ import annotations

import torch
import pytest

import ComfyUI_H3_Continuum_Join.v3.second_pass as second_pass_module
from ComfyUI_H3_Continuum_Join.nodes import NODE_CLASS_MAPPINGS
from ComfyUI_H3_Continuum_Join.v3.second_pass import (
    SecondPassContractError,
    derive_refine_seed,
    run_second_pass_groups,
)
from ComfyUI_H3_Continuum_Join.v3.refine_context import (
    MAGIC as REFINE_CONTEXT_MAGIC,
    RefineConditioningAdaptationError,
)
from ComfyUI_H3_Continuum_Join.v3.second_pass_nodes import (
    H3ContinuumSecondPassV35,
)


def _latent(samples: torch.Tensor) -> dict[str, torch.Tensor]:
    return {"samples": samples}


def _plan(groups: list[dict]) -> dict:
    return {
        "width": 640,
        "height": 640,
        "second_pass_contract": {
            "version": 1,
            "physical_groups": groups,
        },
    }


def _group(group_id: int, *, temporal: int, prompt: str, terminal: bool = False) -> dict:
    return {
        "group_id": group_id,
        "logical_chunks": [group_id + 1] if not terminal else [2, 3],
        "physical_prompt": prompt,
        "prompt_policy": "single" if not terminal else "paired_timeline_v1",
        "physical_frames": 124 if not terminal else 260,
        "trim_prefix_frames": 0 if not terminal else 22,
        "terminal_merged": terminal,
        "source_width": 640,
        "source_height": 640,
        "source_batch": 1,
        "latent_channels": 24,
        "source_latent_t": temporal,
        "source_latent_h": 40,
        "source_latent_w": 40,
        "source_audio_shape": [1, 8, temporal * 4],
    }


def _run_fixture(groups: list[dict]):
    videos = [
        _latent(torch.zeros((1, 24, group["source_latent_t"], 48, 48)))
        for group in groups
    ]
    audios = [
        _latent(torch.full(tuple(group["source_audio_shape"]), float(index + 1)))
        for index, group in enumerate(groups)
    ]
    calls: list[dict] = []

    def encode_prompt(_clip, prompt, **kwargs):
        assert kwargs["first_image"] is None
        assert kwargs["last_image"] is None
        calls.append({"prompt": prompt})
        return [prompt]

    def build_latent(video, audio):
        return {"video": video, "audio": audio}

    def clone_model(model, **kwargs):
        calls[-1]["clone"] = kwargs
        return model

    def sample(**kwargs):
        calls[-1]["seed"] = kwargs["seed"]
        calls[-1]["conditioning"] = kwargs["conditioning"]
        nested = kwargs["latent"]
        return {
            "video": nested["video"] + 1,
            "audio": nested["audio"] + 99,
        }

    def extract(sampled):
        return sampled["video"], sampled["audio"]

    result = run_second_pass_groups(
        model=object(),
        clip=object(),
        sampler=object(),
        sigmas=torch.tensor([0.3, 0.0]),
        video_latents=videos,
        audio_latents=audios,
        assembly_plan=_plan(groups),
        refine_seed=42,
        encode_prompt_fn=encode_prompt,
        latent_builder=build_latent,
        sample_fn=sample,
        stream_extractor=extract,
        clone_model_fn=clone_model,
    )
    return videos, audios, calls, result


def test_second_pass_uses_plan_prompts_one_seed_per_physical_group_and_audio_passthrough():
    groups = [
        _group(0, temporal=31, prompt="first physical prompt"),
        _group(1, temporal=65, prompt="terminal physical prompt", terminal=True),
    ]
    videos, audios, calls, (refined, output_audio, updated, report) = _run_fixture(groups)

    assert [call["prompt"] for call in calls] == [
        "first physical prompt",
        "terminal physical prompt",
    ]
    assert [call["seed"] for call in calls] == [
        derive_refine_seed(42, 0),
        derive_refine_seed(42, 1),
    ]
    assert [call["clone"] for call in calls] == [
        {
            "strict": False,
            "debug": False,
            "chunk_index": 1,
            "context_frames": None,
        },
        {
            "strict": False,
            "debug": False,
            "chunk_index": 2,
            "context_frames": 22,
        },
    ]
    assert all(after is before for before, after in zip(audios, output_audio, strict=True))
    assert all(torch.equal(item["samples"], torch.ones_like(item["samples"])) for item in refined)
    assert [item["samples"].shape[2] for item in refined] == [31, 65]
    assert updated["width"] == 768
    assert updated["height"] == 768
    assert updated["second_pass_contract"]["audio_output"] == (
        "bit_exact_first_pass_passthrough"
    )
    assert updated["second_pass_contract"]["execution"] == (
        "t2va_physical_groups_audio_locked_v2"
    )
    assert updated["second_pass_contract"]["audio_sampling"] == (
        "zero_noise_mask_locked"
    )
    assert "temporary_audio_discarded=true" in report
    assert "audio zero noise/mask=0" in report
    assert "refine_seed=" in report
    assert videos[1]["samples"].shape[2] == 65


def test_second_pass_defaults_to_audio_locked_refine_sampler(monkeypatch):
    group = _group(0, temporal=31, prompt="physical prompt")
    video = _latent(torch.zeros((1, 24, 31, 48, 48)))
    audio = _latent(torch.ones(tuple(group["source_audio_shape"])))
    captured = {}

    def fake_refine_sample(**kwargs):
        captured.update(kwargs)
        return kwargs["latent"]

    monkeypatch.setattr(
        second_pass_module,
        "sample_refine_chunk",
        fake_refine_sample,
    )
    run_second_pass_groups(
        model=object(),
        clip=object(),
        sampler=object(),
        sigmas=torch.tensor([0.3, 0.0]),
        video_latents=[video],
        audio_latents=[audio],
        assembly_plan=_plan([group]),
        refine_seed=17,
        encode_prompt_fn=lambda *_args, **_kwargs: ["conditioning"],
        latent_builder=lambda video_samples, audio_samples: {
            "video": video_samples,
            "audio": audio_samples,
        },
        stream_extractor=lambda sampled: (sampled["video"], sampled["audio"]),
        clone_model_fn=lambda source, **_kwargs: source,
    )

    assert captured["latent"]["video"] is video["samples"]
    assert captured["latent"]["audio"] is audio["samples"]
    assert captured["seed"] == derive_refine_seed(17, 0)


def test_complete_refine_context_skips_prompt_encode_and_clones_each_group_model():
    groups = [
        _group(0, temporal=31, prompt="unused first prompt"),
        _group(1, temporal=65, prompt="unused terminal prompt", terminal=True),
    ]
    videos = [
        _latent(torch.zeros((1, 24, group["source_latent_t"], 48, 48)))
        for group in groups
    ]
    audios = [
        _latent(torch.ones(tuple(group["source_audio_shape"]))) for group in groups
    ]
    context_groups = (
        {
            "group_id": 0,
            "logical_chunks": (1,),
            "physical_clip_index": 4,
            "context_frames": 0,
        },
        {
            "group_id": 1,
            "logical_chunks": (2, 3),
            "physical_clip_index": 5,
            "context_frames": 22,
        },
    )
    refine_context = {
        "magic": REFINE_CONTEXT_MAGIC,
        "complete": True,
        "groups": context_groups,
    }
    adapted_calls = []
    clone_calls = []
    sample_calls = []
    video_vae = object()

    def unexpected_prompt_encode(*_args, **_kwargs):
        raise AssertionError("complete refine_context must bypass prompt encoding")

    def validate_context(value, *, assembly_plan):
        assert value is refine_context
        assert assembly_plan is plan
        return value

    def adapt(group, **kwargs):
        adapted_calls.append((group, kwargs))
        return [f"captured-{group['group_id']}"], {
            "keyframes_resized": group["group_id"],
            "keyframes_reencoded": 0,
            "context_refs_resized": 0,
            "warnings": (),
        }

    def clone(source, **kwargs):
        clone_calls.append((source, kwargs))
        return f"group-model-{kwargs['chunk_index']}"

    def sample(**kwargs):
        sample_calls.append(kwargs)
        return kwargs["latent"]

    plan = _plan(groups)
    refined, output_audio, updated, report = run_second_pass_groups(
        model="source-model",
        clip=object(),
        sampler=object(),
        sigmas=torch.tensor([0.3, 0.0]),
        video_latents=videos,
        audio_latents=audios,
        assembly_plan=plan,
        refine_seed=42,
        refine_context=refine_context,
        video_vae=video_vae,
        encode_prompt_fn=unexpected_prompt_encode,
        latent_builder=lambda video, audio: {"video": video, "audio": audio},
        sample_fn=sample,
        stream_extractor=lambda value: (value["video"], value["audio"]),
        clone_model_fn=clone,
        validate_refine_context_fn=validate_context,
        adapt_group_conditioning_fn=adapt,
    )

    assert [call[0] for call in adapted_calls] == list(context_groups)
    assert all(call[1] == {
        "target_latent_h": 48,
        "target_latent_w": 48,
        "video_vae": video_vae,
        "upscale_method": "bilinear",
    } for call in adapted_calls)
    assert [call[1] for call in clone_calls] == [
        {
            "strict": False,
            "debug": False,
            "chunk_index": 4,
            "context_frames": None,
        },
        {
            "strict": False,
            "debug": False,
            "chunk_index": 5,
            "context_frames": 22,
        },
    ]
    assert [call["model"] for call in sample_calls] == [
        "group-model-4",
        "group-model-5",
    ]
    assert [call["conditioning"] for call in sample_calls] == [
        ["captured-0"],
        ["captured-1"],
    ]
    assert all(before is after for before, after in zip(audios, output_audio, strict=True))
    assert all(
        item["samples"] is before["samples"]
        for item, before in zip(refined, videos, strict=True)
    )
    assert updated["second_pass_contract"]["execution"] == (
        "context_aware_physical_groups_audio_locked_v3"
    )
    assert "conditioning_source=refine_context" in report


def test_unadaptable_complete_context_warns_and_uses_prompt_only_fallback():
    group = _group(0, temporal=31, prompt="fallback prompt")
    video = _latent(torch.zeros((1, 24, 31, 48, 48)))
    audio = _latent(torch.ones(tuple(group["source_audio_shape"])))
    refine_context = {
        "magic": REFINE_CONTEXT_MAGIC,
        "complete": True,
        "groups": ({"group_id": 0, "logical_chunks": (1,)},),
    }
    prompts = []

    def unavailable(*_args, **_kwargs):
        raise RefineConditioningAdaptationError("target conversion unavailable")

    _refined, output_audio, updated, report = run_second_pass_groups(
        model=object(),
        clip=object(),
        sampler=object(),
        sigmas=torch.tensor([0.3, 0.0]),
        video_latents=[video],
        audio_latents=[audio],
        assembly_plan=_plan([group]),
        refine_seed=5,
        refine_context=refine_context,
        encode_prompt_fn=lambda _clip, prompt, **_kwargs: prompts.append(prompt) or [prompt],
        latent_builder=lambda video_samples, audio_samples: {
            "video": video_samples,
            "audio": audio_samples,
        },
        sample_fn=lambda **kwargs: kwargs["latent"],
        stream_extractor=lambda value: (value["video"], value["audio"]),
        clone_model_fn=lambda source, **_kwargs: source,
        validate_refine_context_fn=lambda value, **_kwargs: value,
        adapt_group_conditioning_fn=unavailable,
    )

    assert prompts == ["fallback prompt"]
    assert output_audio[0] is audio
    assert updated["second_pass_contract"]["execution"] == (
        "t2va_physical_groups_audio_locked_v2"
    )
    assert "target adaptation was unavailable" in report
    assert "conditioning_source=prompt_only_fallback" in report


def test_incomplete_refine_context_warns_and_preserves_legacy_prompt_path():
    group = _group(0, temporal=31, prompt="legacy prompt")
    video = _latent(torch.zeros((1, 24, 31, 48, 48)))
    audio = _latent(torch.ones(tuple(group["source_audio_shape"])))
    incomplete_context = {
        "magic": REFINE_CONTEXT_MAGIC,
        "complete": False,
        "groups": (),
    }
    prompts = []

    def unexpected_adaptation(*_args, **_kwargs):
        raise AssertionError("incomplete context must not be adapted")

    _refined, output_audio, updated, report = run_second_pass_groups(
        model=object(),
        clip=object(),
        sampler=object(),
        sigmas=torch.tensor([0.3, 0.0]),
        video_latents=[video],
        audio_latents=[audio],
        assembly_plan=_plan([group]),
        refine_seed=5,
        refine_context=incomplete_context,
        encode_prompt_fn=lambda _clip, prompt, **_kwargs: prompts.append(prompt) or [prompt],
        latent_builder=lambda video_samples, audio_samples: {
            "video": video_samples,
            "audio": audio_samples,
        },
        sample_fn=lambda **kwargs: kwargs["latent"],
        stream_extractor=lambda value: (value["video"], value["audio"]),
        clone_model_fn=lambda source, **_kwargs: source,
        validate_refine_context_fn=lambda value, **_kwargs: value,
        adapt_group_conditioning_fn=unexpected_adaptation,
    )

    assert prompts == ["legacy prompt"]
    assert output_audio[0] is audio
    assert updated["second_pass_contract"]["execution"] == (
        "t2va_physical_groups_audio_locked_v2"
    )
    assert "capture is incomplete" in report


def test_corrupt_typed_refine_context_is_a_contract_error():
    group = _group(0, temporal=31, prompt="prompt")
    with pytest.raises(SecondPassContractError, match="refine_context contract"):
        run_second_pass_groups(
            model=object(),
            clip=object(),
            sampler=object(),
            sigmas=torch.tensor([0.3, 0.0]),
            video_latents=[_latent(torch.zeros((1, 24, 31, 48, 48)))],
            audio_latents=[_latent(torch.ones(tuple(group["source_audio_shape"])))],
            assembly_plan=_plan([group]),
            refine_seed=5,
            refine_context={"magic": REFINE_CONTEXT_MAGIC, "version": 999},
        )


def test_experimental_node_unwraps_single_inputs_but_preserves_physical_lists(monkeypatch):
    captured = {}
    sentinel = (["video"], ["audio"], {"plan": True}, "status")

    def fake_run(**kwargs):
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(
        "ComfyUI_H3_Continuum_Join.v3.second_pass_nodes.run_second_pass_groups",
        fake_run,
    )
    node = H3ContinuumSecondPassV35()
    videos = [{"samples": torch.zeros((1, 24, 31, 40, 40))}]
    audios = [{"samples": torch.zeros((1, 8, 124))}]
    result = node.refine(
        ["model"],
        ["clip"],
        ["sampler"],
        [torch.tensor([0.3, 0.0])],
        videos,
        audios,
        [{"second_pass_contract": {}}],
        [7],
    )
    assert result == sentinel
    assert captured["video_latents"] is videos
    assert captured["audio_latents"] is audios
    assert captured["refine_seed"] == 7
    assert captured["refine_context"] is None
    assert captured["video_vae"] is None


def test_second_pass_node_forwards_optional_refine_context_and_video_vae(monkeypatch):
    captured = {}
    sentinel = ([], [], {"plan": True}, "status")

    def fake_run(**kwargs):
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(
        "ComfyUI_H3_Continuum_Join.v3.second_pass_nodes.run_second_pass_groups",
        fake_run,
    )
    context = {"context": True}
    video_vae = object()
    result = H3ContinuumSecondPassV35().refine(
        ["model"],
        ["clip"],
        ["sampler"],
        [torch.tensor([0.3, 0.0])],
        [{"samples": torch.zeros((1, 24, 31, 40, 40))}],
        [{"samples": torch.zeros((1, 8, 124))}],
        [{"second_pass_contract": {}}],
        [7],
        [context],
        [video_vae],
    )

    assert result == sentinel
    assert captured["refine_context"] is context
    assert captured["video_vae"] is video_vae


def test_second_pass_node_is_registered_and_not_deprecated():
    node_class = NODE_CLASS_MAPPINGS["H3ContinuumSecondPassV35"]
    assert node_class is H3ContinuumSecondPassV35
    assert node_class.DEPRECATED is False
    assert node_class.INPUT_IS_LIST is True
    assert node_class.OUTPUT_IS_LIST == (True, True, False, False)
    assert node_class.INPUT_TYPES()["optional"] == {
        "refine_context": ("H3_CONTINUUM_REFINE_CONTEXT",),
        "video_vae": ("VAE",),
    }
