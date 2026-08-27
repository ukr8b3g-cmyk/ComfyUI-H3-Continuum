from __future__ import annotations

import sys
from types import ModuleType
from types import SimpleNamespace

import torch

from ComfyUI_H3_Continuum_Join.constants import (
    DIAGNOSTICS_BASIC,
    DIAGNOSTICS_FULL,
    PROMPT_MODE_FIXED,
    PROMPT_MODE_LIST,
    V2_CONTINUITY_OPTIONS,
)
from ComfyUI_H3_Continuum_Join.temporal import audio_latent_t, video_latent_t
from ComfyUI_H3_Continuum_Join.reference import (
    REFERENCE_SIZE_MATCH_OUTPUT,
    ReferenceAssets,
)
from ComfyUI_H3_Continuum_Join.v2 import sequence
from ComfyUI_H3_Continuum_Join.v2.h3_builder import IdentityAssets
from ComfyUI_H3_Continuum_Join.v2.prompts import make_prompt_plan
from ComfyUI_H3_Continuum_Join.v3.driving_nodes import (
    H3ContinuumSamplerV34,
    H3ContinuumSamplerV35,
    NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS,
)
from ComfyUI_H3_Continuum_Join.v3.nodes import H3ContinuumSamplerProduction
from ComfyUI_H3_Continuum_Join.v3.plan import prepare_physical_decode_entries
from ComfyUI_H3_Continuum_Join.v3.refine_context import validate_refine_context


class _Nested:
    def __init__(self, parts):
        self.parts = list(parts)

    def unbind(self):
        return self.parts


def _install_nested_tensor(monkeypatch):
    nested_module = ModuleType("comfy.nested_tensor")
    nested_module.NestedTensor = _Nested
    comfy_module = sys.modules.get("comfy") or ModuleType("comfy")
    comfy_module.nested_tensor = nested_module
    monkeypatch.setitem(sys.modules, "comfy", comfy_module)
    monkeypatch.setitem(sys.modules, "comfy.nested_tensor", nested_module)


class _Clip:
    def __init__(self):
        self.encode_calls = 0
        self.layer_idx = None
        self.use_clip_schedule = False
        self.tokenizer_options = {}
        self.apply_hooks_to_conds = None
        self.patcher = SimpleNamespace(
            patches_uuid="test-patch-a",
            forced_hooks=None,
            current_hooks=None,
            hook_patches={},
        )

    def tokenize(self, prompt, **_kwargs):
        return prompt

    def encode_from_tokens_scheduled(self, _tokens):
        self.encode_calls += 1
        return [[torch.zeros((1, 1, 2)), {}]]


def _latent(width: int, height: int, frames: int):
    return {
        "samples": _Nested(
            (
                torch.zeros(
                    (1, 24, video_latent_t(frames), height // 16, width // 16)
                ),
                torch.zeros((1, 32, 2, audio_latent_t(frames))),
            )
        )
    }


def _model():
    return SimpleNamespace(
        model=SimpleNamespace(diffusion_model=SimpleNamespace()),
        model_options={},
        wrappers={},
        model_dtype=lambda: torch.bfloat16,
        model_size=lambda: 0,
    )


def _capture_sequence(
    monkeypatch,
    *,
    terminal: bool,
    reference_image: bool = False,
    reference_audio: bool = False,
    continuation_transport=sequence.REFERENCE_CONTEXT_V1,
    session=None,
    diagnostics=DIAGNOSTICS_BASIC,
    memory_attribution=False,
    prompt_conditioning_cache=False,
    clip=None,
):
    _install_nested_tensor(monkeypatch)
    width, height = 96, 64
    first_image = torch.zeros((1, height, width, 3)) if terminal else None
    last_image = torch.ones((1, height, width, 3)) if terminal else None
    first_latent = torch.zeros((1, 24, 1, height // 16, width // 16)) if terminal else None
    last_latent = torch.ones((1, 24, 1, height // 16, width // 16)) if terminal else None
    assets = IdentityAssets(
        first_image,
        first_latent,
        last_image,
        last_latent,
        "identity" if terminal else "none",
    )
    monkeypatch.setattr(sequence, "check_comfy_h3_runtime", lambda: [])
    monkeypatch.setattr(sequence, "prepare_identity_assets", lambda *a, **k: assets)
    monkeypatch.setattr(sequence, "encode_identity_latents", lambda *a, **k: assets)
    monkeypatch.setattr(sequence, "empty_h3_latent", _latent)
    monkeypatch.setattr(
        sequence,
        "latent_from_cpu",
        lambda video, audio: {"samples": _Nested((video, audio))},
    )
    monkeypatch.setattr(sequence, "accelerator_summary", lambda _model: "accelerators")
    monkeypatch.setattr(sequence, "sample_chunk", lambda **kwargs: kwargs["latent"])
    monkeypatch.setattr(
        sequence,
        "clone_model_for_chunk",
        lambda model, **_kwargs: model,
    )
    reference_assets = None
    if reference_image:
        reference_assets = ReferenceAssets(
            images=(torch.full((1, height, width, 3), 0.5),),
            latents=(torch.full((1, 24, 1, height // 16, width // 16), 0.5),),
            image_hashes=("b" * 64,),
            combined_hash="c" * 64,
            size_mode=REFERENCE_SIZE_MATCH_OUTPUT,
        )
    reference_audio_source = None
    reference_audio_vae = None
    if reference_audio:
        from ComfyUI_H3_Continuum_Join import reference_audio as reference_audio_module

        reference_audio_source = SimpleNamespace(
            combined_hash="reference-audio-hash",
            contract={
                "reference_audio_contract_version": 1,
                "source_sha256": "a" * 64,
            },
        )
        reference_audio_vae = object()
        reference_audio_assets = SimpleNamespace(
            audio_latent=torch.arange(64, dtype=torch.float32).reshape(1, 32, 2, 1)
        )
        monkeypatch.setattr(
            reference_audio_module,
            "encode_reference_audio",
            lambda _vae, _source: reference_audio_assets,
        )
    chunks = 3 if terminal else 2
    mode = PROMPT_MODE_LIST if terminal else PROMPT_MODE_FIXED
    script = "first\n---\nmiddle\n---\nlast" if terminal else "same prompt"
    plan = make_prompt_plan(
        mode=mode,
        script=script,
        chunks=chunks,
        chunk_seconds=5.0,
    )
    return sequence.run_sequence(
        model=_model(),
        clip=clip or _Clip(),
        video_vae=object(),
        audio_vae=None,
        sampler=object(),
        sigmas=torch.tensor([1.0, 0.0]),
        first_frame=first_image,
        last_frame=last_image,
        prompt_plan=plan,
        width=width,
        height=height,
        continuity=V2_CONTINUITY_OPTIONS[1],
        base_seed=42,
        audio_continuity=True,
        exact_total_duration=False,
        diagnostics_mode=diagnostics,
        reroll_from_chunk=0,
        reroll_nonce=0,
        strict_compatibility=False,
        debug=False,
        session=session,
        latent_only=True,
        reference_assets=reference_assets,
        reference_audio_source=reference_audio_source,
        reference_audio_vae=reference_audio_vae,
        capture_refine_context=True,
        memory_attribution=memory_attribution,
        prompt_conditioning_cache=prompt_conditioning_cache,
        continuation_transport=continuation_transport,
    )


def test_v34_public_output_schema_is_unchanged():
    assert H3ContinuumSamplerV34.RETURN_TYPES == (
        "LATENT",
        "LATENT",
        "H3_CONTINUUM_ASSEMBLY_PLAN",
        "STRING",
        "AUDIO",
    )
    assert H3ContinuumSamplerV34.RETURN_NAMES == (
        "video_latents",
        "audio_latents",
        "assembly_plan",
        "status",
        "driving_audio",
    )
    assert H3ContinuumSamplerV34.OUTPUT_IS_LIST == (True, True, False, False, False)


def test_v35_is_registered_with_v34_outputs_then_refine_context():
    from ComfyUI_H3_Continuum_Join import nodes as root_nodes

    assert NODE_CLASS_MAPPINGS["H3ContinuumSamplerV35"] is H3ContinuumSamplerV35
    assert NODE_DISPLAY_NAME_MAPPINGS["H3ContinuumSamplerV35"] == (
        "H3 Continuum Sampler V3.5"
    )
    assert root_nodes.NODE_CLASS_MAPPINGS["H3ContinuumSamplerV35"] is (
        H3ContinuumSamplerV35
    )
    assert H3ContinuumSamplerV35.RETURN_TYPES[:5] == H3ContinuumSamplerV34.RETURN_TYPES
    assert H3ContinuumSamplerV35.RETURN_NAMES[:5] == H3ContinuumSamplerV34.RETURN_NAMES
    assert H3ContinuumSamplerV35.RETURN_TYPES[5] == "H3_CONTINUUM_REFINE_CONTEXT"
    assert H3ContinuumSamplerV35.RETURN_NAMES[5] == "refine_context"
    assert H3ContinuumSamplerV35.OUTPUT_IS_LIST == (
        True,
        True,
        False,
        False,
        False,
        False,
    )


def test_v35_runtime_keeps_driving_audio_fifth_and_context_sixth(monkeypatch):
    captured = {}

    def fake_production_run(_self, **kwargs):
        captured["capture"] = kwargs["capture_refine_context"]
        captured["memory"] = kwargs.get("memory_attribution", False)
        captured["prompt_cache"] = kwargs.get("prompt_conditioning_cache", False)
        base = ("video", "audio", {"plan": True}, "status")
        return (*base, "context") if kwargs["capture_refine_context"] else base

    monkeypatch.setattr(H3ContinuumSamplerProduction, "run", fake_production_run)
    v34_outputs = H3ContinuumSamplerV34().run(
        chunks=1,
        chunk_seconds=5.0,
        width=96,
        height=64,
    )
    assert captured["capture"] is False
    assert captured["memory"] is False
    assert captured["prompt_cache"] is False
    assert v34_outputs == (
        "video",
        "audio",
        {"plan": True},
        "status",
        None,
    )
    outputs = H3ContinuumSamplerV35().run(
        chunks=1,
        chunk_seconds=5.0,
        width=96,
        height=64,
    )
    assert captured["capture"] is True
    assert captured["memory"] is True
    assert captured["prompt_cache"] is True
    assert outputs == (
        "video",
        "audio",
        {"plan": True},
        "status",
        None,
        "context",
    )


def test_capture_records_normal_physical_groups_in_sampling_order(monkeypatch):
    outputs = _capture_sequence(monkeypatch, terminal=False)
    assert len(outputs) == 5
    context = outputs[4]
    assert context["complete"] is True
    assert context["conditioning_mode"] == "t2va"
    groups = context["groups"]
    assert [group["logical_chunks"] for group in groups] == [(1,), (2,)]
    assert [group["physical_clip_index"] for group in groups] == [1, 2]
    assert [group["context_frames"] for group in groups] == [0, 22]
    assert [group["prompt_policy"] for group in groups] == ["single", "single"]
    assert [group["source_video_shape"] for group in groups] == [
        (1, 24, 37, 4, 6),
        (1, 24, 42, 4, 6),
    ]
    _, assembly_plan = prepare_physical_decode_entries(
        outputs[0],
        chunk_seconds=5.0,
        preserve_final_frame=False,
        terminal_merged=False,
    )
    assert validate_refine_context(context, assembly_plan) is context


def test_capture_records_terminal_pair_as_one_physical_group(monkeypatch):
    outputs = _capture_sequence(monkeypatch, terminal=True)
    context = outputs[4]
    assert context["complete"] is True
    assert context["conditioning_mode"] == "fl2va"
    groups = context["groups"]
    assert len(groups) == 2
    assert groups[0]["logical_chunks"] == (1,)
    assert groups[1]["logical_chunks"] == (2, 3)
    assert groups[1]["physical_frames"] == 260
    assert groups[1]["physical_clip_index"] == 2
    assert groups[1]["context_frames"] == 22
    assert groups[1]["prompt_policy"] == "paired_timeline_v1"
    assert groups[1]["physical_prompt"] == (
        "[0-5s]\nmiddle\n\n[5-10s]\nlast"
    )
    assert groups[1]["source_video_shape"] == (1, 24, 77, 4, 6)
    assert torch.equal(groups[1]["first_image"], torch.zeros((1, 64, 96, 3)))
    assert torch.equal(groups[1]["last_image"], torch.ones((1, 64, 96, 3)))
    _, assembly_plan = prepare_physical_decode_entries(
        outputs[0],
        chunk_seconds=5.0,
        preserve_final_frame=True,
        terminal_merged=True,
    )
    assert validate_refine_context(context, assembly_plan) is context


def test_reference_audio_is_captured_in_every_normal_physical_group(monkeypatch):
    outputs = _capture_sequence(
        monkeypatch,
        terminal=False,
        reference_audio=True,
    )
    groups = outputs[4]["groups"]
    assert [group["logical_chunks"] for group in groups] == [(1,), (2,)]
    for group in groups:
        refs = group["conditioning"][0][1]["minimax_refs"]
        assert [ref["kind"] for ref in refs].count("audio") == 1


def test_reference_audio_is_captured_in_terminal_physical_group(monkeypatch):
    outputs = _capture_sequence(
        monkeypatch,
        terminal=True,
        reference_audio=True,
    )
    groups = outputs[4]["groups"]
    assert [group["logical_chunks"] for group in groups] == [(1,), (2, 3)]
    assert groups[1]["prompt_policy"] == "paired_timeline_v1"
    for group in groups:
        refs = group["conditioning"][0][1]["minimax_refs"]
        assert [ref["kind"] for ref in refs].count("audio") == 1


def test_masked_av_preserves_image_and_audio_refs_in_every_normal_group(monkeypatch):
    outputs = _capture_sequence(
        monkeypatch,
        terminal=False,
        reference_image=True,
        reference_audio=True,
        continuation_transport=sequence.MASKED_AV_PREFIX_22_V1,
    )
    groups = outputs[4]["groups"]
    assert [group["logical_chunks"] for group in groups] == [(1,), (2,)]
    for group in groups:
        refs = group["conditioning"][0][1]["minimax_refs"]
        assert [ref["kind"] for ref in refs] == ["image", "audio"]


def test_masked_av_preserves_image_and_audio_refs_in_terminal_groups(monkeypatch):
    outputs = _capture_sequence(
        monkeypatch,
        terminal=True,
        reference_image=True,
        reference_audio=True,
        continuation_transport=sequence.MASKED_AV_PREFIX_22_V1,
    )
    groups = outputs[4]["groups"]
    assert [group["logical_chunks"] for group in groups] == [(1,), (2, 3)]
    assert groups[1]["prompt_policy"] == "paired_timeline_v1"
    for group in groups:
        refs = group["conditioning"][0][1]["minimax_refs"]
        assert [ref["kind"] for ref in refs] == ["image", "audio"]


def test_reused_session_returns_incomplete_context_without_stopping(monkeypatch):
    first_outputs = _capture_sequence(monkeypatch, terminal=False)
    reused_outputs = _capture_sequence(
        monkeypatch,
        terminal=False,
        session=first_outputs[2],
    )
    context = reused_outputs[4]
    assert context["complete"] is False
    assert context["groups"] == ()
    assert len(reused_outputs[0]) == 2
    assert any("Run Storage" in note for note in context["notes"])


def test_v35_full_memory_events_follow_physical_terminal_group_order(monkeypatch):
    outputs = _capture_sequence(
        monkeypatch,
        terminal=True,
        diagnostics=DIAGNOSTICS_FULL,
        memory_attribution=True,
    )
    memory_lines = [
        line for line in outputs[3].splitlines() if line.startswith("Memory [V3.5")
    ]
    labels = [line.split("]: RSS", 1)[0] + "]" for line in memory_lines]
    assert labels == [
        "Memory [V3.5 sequence start]",
        "Memory [V3.5 physical group 1 logical=[1] before sampling]",
        "Memory [V3.5 physical group 1 logical=[1] after sampling]",
        "Memory [V3.5 physical group 1 logical=[1] after CPU commit]",
        "Memory [V3.5 physical group 2 logical=[2,3] before sampling]",
        "Memory [V3.5 physical group 2 logical=[2,3] after sampling]",
        "Memory [V3.5 physical group 2 logical=[2,3] after CPU commit]",
        "Memory [V3.5 sequence complete]",
    ]
    performance_lines = [
        line
        for line in outputs[3].splitlines()
        if line.startswith("Performance [V3.5")
    ]
    assert len(performance_lines) == 3
    assert performance_lines[0].startswith(
        "Performance [V3.5 physical group 1 logical=[1]]"
    )
    assert performance_lines[1].startswith(
        "Performance [V3.5 physical group 2 logical=[2,3]]"
    )
    assert performance_lines[2].startswith("Performance [V3.5 summary]")
    assert "sampling=2" in performance_lines[2]
    assert "conditioning_identity_video_vae=1" in performance_lines[2]
    assert "conditioning_prompt_clip=1" in performance_lines[2]
    assert "conditioning_reference_audio_vae=0" in performance_lines[2]
    assert "CUDA_synchronize=not_used" in performance_lines[2]


def test_v35_reference_audio_conditioning_attribution_is_reported(monkeypatch):
    outputs = _capture_sequence(
        monkeypatch,
        terminal=False,
        reference_audio=True,
        diagnostics=DIAGNOSTICS_FULL,
        memory_attribution=True,
    )
    summary = next(
        line
        for line in outputs[3].splitlines()
        if line.startswith("Performance [V3.5 summary]")
    )
    assert "conditioning_reference_audio_vae=" in summary
    assert "conditioning_reference_audio_vae=1" in summary


def test_memory_attribution_is_absent_when_private_flag_is_off(monkeypatch):
    outputs = _capture_sequence(
        monkeypatch,
        terminal=False,
        diagnostics=DIAGNOSTICS_FULL,
        memory_attribution=False,
    )
    assert "Memory [V3.5" not in outputs[3]
    assert "Memory [sequence start]" in outputs[3]
    assert "Memory [sequence complete]" in outputs[3]


def test_v35_prompt_cache_reports_real_encode_elision_across_runs(monkeypatch):
    clip = _Clip()
    first = _capture_sequence(
        monkeypatch,
        terminal=False,
        diagnostics=DIAGNOSTICS_FULL,
        prompt_conditioning_cache=True,
        clip=clip,
    )
    assert clip.encode_calls == 1
    assert "Prompt/CLIP cache [V3.5]: hits=0, misses=1, bypasses=0, encode_calls=1." in first[3]

    second = _capture_sequence(
        monkeypatch,
        terminal=False,
        diagnostics=DIAGNOSTICS_FULL,
        prompt_conditioning_cache=True,
        clip=clip,
    )
    assert clip.encode_calls == 1
    assert "Prompt/CLIP cache [V3.5]: hits=1, misses=0, bypasses=0, encode_calls=0." in second[3]


def test_v35_terminal_prompt_cache_preserves_physical_prompt_set(monkeypatch):
    clip = _Clip()
    _capture_sequence(
        monkeypatch,
        terminal=True,
        diagnostics=DIAGNOSTICS_FULL,
        prompt_conditioning_cache=True,
        clip=clip,
    )
    assert clip.encode_calls == 4

    second = _capture_sequence(
        monkeypatch,
        terminal=True,
        diagnostics=DIAGNOSTICS_FULL,
        prompt_conditioning_cache=True,
        clip=clip,
    )
    assert clip.encode_calls == 4
    assert "Prompt/CLIP cache [V3.5]: hits=4, misses=0, bypasses=0, encode_calls=0." in second[3]
