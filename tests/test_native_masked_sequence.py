from __future__ import annotations

from types import SimpleNamespace

import torch

from ComfyUI_H3_Continuum_Join.constants import (
    CONTINUUM_INTEROP_KEY,
    DIAGNOSTICS_BASIC,
    PROMPT_MODE_FIXED,
    V2_CONTINUITY_AUTO,
    V2_CONTINUITY_OPTIONS,
)
from ComfyUI_H3_Continuum_Join.masked_continuation import (
    CONTINUATION_GUIDE,
    CONTINUATION_NATIVE_MASKED,
    continuation_method_scope,
)
from ComfyUI_H3_Continuum_Join.temporal import audio_latent_t, video_latent_t
from ComfyUI_H3_Continuum_Join.v2.h3_builder import IdentityAssets
from ComfyUI_H3_Continuum_Join.v2.prompts import make_prompt_plan
from ComfyUI_H3_Continuum_Join.v2 import sequence


class Nested:
    def __init__(self, parts):
        self.parts = list(parts)

    def unbind(self):
        return self.parts


def _latent(width, height, frames):
    return {
        "samples": Nested(
            (
                torch.zeros(1, 24, video_latent_t(frames), height // 16, width // 16),
                torch.zeros(1, 32, 2, audio_latent_t(frames)),
            )
        )
    }


class FakeClip:
    def tokenize(self, prompt, images):
        return prompt

    def encode_from_tokens_scheduled(self, tokens):
        return [[torch.zeros(1, 1, 2), {}]]


def _install_common_runtime(monkeypatch, events):
    width, height = 96, 64
    model = SimpleNamespace(
        model=SimpleNamespace(diffusion_model=SimpleNamespace()),
        model_options={},
        wrappers={},
        model_dtype=lambda: torch.bfloat16,
        model_size=lambda: 0,
    )
    assets = IdentityAssets(None, None, None, None, "none")
    monkeypatch.setattr(sequence, "check_comfy_h3_runtime", lambda: [])
    monkeypatch.setattr(sequence, "require_native_mask_support", lambda: None)
    monkeypatch.setattr(sequence, "prepare_identity_assets", lambda *a, **k: assets)
    monkeypatch.setattr(sequence, "encode_identity_latents", lambda *a, **k: assets)
    monkeypatch.setattr(sequence, "empty_h3_latent", _latent)
    monkeypatch.setattr(sequence, "accelerator_summary", lambda model: "accelerators")

    def clone_model_for_chunk(model, *, strict, debug, chunk_index, context_frames):
        options = dict(model.model_options)
        transformer = dict(options.get("transformer_options") or {})
        if context_frames is not None:
            transformer[CONTINUUM_INTEROP_KEY] = {
                "api": 1,
                "active": True,
                "min_actual_prefix_steps": 2,
            }
        options["transformer_options"] = transformer
        events.append(("clone", chunk_index, context_frames, transformer.get(CONTINUUM_INTEROP_KEY)))
        return SimpleNamespace(
            model=model.model,
            model_options=options,
            wrappers=model.wrappers,
            model_dtype=model.model_dtype,
            model_size=model.model_size,
        )

    monkeypatch.setattr(sequence, "clone_model_for_chunk", clone_model_for_chunk)

    sample_number = 0

    def sample_chunk(**kwargs):
        nonlocal sample_number
        sample_number += 1
        video, audio = kwargs["latent"]["samples"].unbind()
        events.append(
            (
                "sample",
                sample_number,
                "noise_mask" in kwargs["latent"],
                kwargs["model"].model_options["transformer_options"].get(CONTINUUM_INTEROP_KEY),
            )
        )
        # Make the accepted chunk latent distinguishable so chunk N+1 can prove
        # it selected the immediately preceding accepted latent, including after
        # CPU session/state conversion.
        video.fill_(float(sample_number))
        audio.fill_(float(sample_number * 10))
        return kwargs["latent"]

    monkeypatch.setattr(sequence, "sample_chunk", sample_chunk)
    plan = make_prompt_plan(
        mode=PROMPT_MODE_FIXED,
        script="continuous shot",
        chunks=2,
        chunk_seconds=5.0,
    )
    kwargs = dict(
        model=model,
        clip=FakeClip(),
        video_vae=object(),
        audio_vae=object(),
        sampler=object(),
        sigmas=torch.tensor([1.0, 0.0]),
        first_frame=None,
        last_frame=None,
        prompt_plan=plan,
        width=width,
        height=height,
        continuity=V2_CONTINUITY_AUTO,
        base_seed=42,
        audio_continuity=True,
        exact_total_duration=False,
        diagnostics_mode=DIAGNOSTICS_BASIC,
        reroll_from_chunk=0,
        reroll_nonce=0,
        strict_compatibility=True,
        debug=False,
        latent_only=True,
    )
    return kwargs


def _enable_driving_audio(monkeypatch, kwargs):
    source = SimpleNamespace(contract={"test": "driving-audio"})
    kwargs["driving_audio_source"] = source
    kwargs["driving_audio_vae"] = object()
    monkeypatch.setattr(
        sequence,
        "combine_driving_audio_identity",
        lambda identity, source: f"{identity}:driving",
    )
    monkeypatch.setattr(sequence, "encode_driving_audio", lambda source, vae: object())
    monkeypatch.setattr(
        sequence,
        "slice_driving_audio_latent",
        lambda *args, **kwargs: torch.zeros(1, 32, 2, 1),
    )
    monkeypatch.setattr(sequence, "attach_driving_audio", lambda conditioning, latent: conditioning)
    return source


def test_native_sequence_has_no_chunk1_prefix_uses_previous_accepted_latent_and_skips_legacy_rope_path(monkeypatch):
    events = []
    kwargs = _install_common_runtime(monkeypatch, events)
    masked_calls = []

    def masked(latent, *, video_context, audio_context, context_frames):
        masked_calls.append(
            (
                context_frames,
                video_context.detach().clone(),
                audio_context.detach().clone() if audio_context is not None else None,
            )
        )
        latent = dict(latent)
        latent["noise_mask"] = "native-mask"
        return latent

    monkeypatch.setattr(sequence, "apply_native_masked_continuation", masked)
    monkeypatch.setattr(
        sequence,
        "prepare_conditioning",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("native continuation must not enter legacy reference/RoPE preparation")
        ),
    )

    with continuation_method_scope(CONTINUATION_NATIVE_MASKED):
        entries, last_state, session, report = sequence.run_sequence(**kwargs)

    assert [event[2] for event in events if event[0] == "sample"] == [False, True]
    assert len(masked_calls) == 1
    context_frames, video_context, audio_context = masked_calls[0]
    assert context_frames == 39
    assert torch.all(video_context == 1.0)
    assert torch.all(audio_context == 10.0)
    clone_events = [event for event in events if event[0] == "clone"]
    assert clone_events[0][2] is None
    assert clone_events[1][2] == 39
    assert clone_events[1][3]["min_actual_prefix_steps"] == 2
    assert entries[0]["plan"].get("continuation_method") is None
    assert entries[1]["plan"]["continuation_method"] == CONTINUATION_NATIVE_MASKED
    assert entries[1]["plan"]["trim_frames"] == 39
    assert entries[1]["plan"]["net_frames"] == entries[1]["plan"]["total_frames"] - 39
    assert last_state["clip_index"] == 2
    assert session["settings"]["continuation_method"] == CONTINUATION_NATIVE_MASKED
    assert "Continuation method: Native Masked" in report


def test_native_three_chunk_run_uses_immediately_previous_accepted_state_without_stale_context(monkeypatch):
    events = []
    kwargs = _install_common_runtime(monkeypatch, events)
    kwargs["prompt_plan"] = make_prompt_plan(
        mode=PROMPT_MODE_FIXED,
        script="continuous shot",
        chunks=3,
        chunk_seconds=5.0,
    )
    captured = []

    def masked(latent, *, video_context, audio_context, context_frames):
        captured.append((
            float(video_context.mean()),
            float(audio_context.mean()),
            context_frames,
        ))
        latent = dict(latent)
        latent["noise_mask"] = "native-mask"
        return latent

    monkeypatch.setattr(sequence, "apply_native_masked_continuation", masked)

    with continuation_method_scope(CONTINUATION_NATIVE_MASKED):
        entries, last_state, _session, _report = sequence.run_sequence(**kwargs)

    assert captured == [(1.0, 10.0, 39), (2.0, 20.0, 39)]
    assert len(entries) == 3
    assert last_state["clip_index"] == 3
    assert [event[2] for event in events if event[0] == "sample"] == [False, True, True]


def test_guide_sequence_still_uses_legacy_conditioning_path_and_never_native_mask(monkeypatch):
    events = []
    kwargs = _install_common_runtime(monkeypatch, events)
    guide_calls = []

    def guide(conditioning, **kwargs):
        guide_calls.append(kwargs)
        return conditioning

    monkeypatch.setattr(sequence, "prepare_conditioning", guide)
    monkeypatch.setattr(
        sequence,
        "apply_native_masked_continuation",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("Guide mode must not use the native masked target path")
        ),
    )

    with continuation_method_scope(CONTINUATION_GUIDE):
        entries, _last_state, session, report = sequence.run_sequence(**kwargs)

    assert len(guide_calls) == 1
    assert guide_calls[0]["context_frames"] in (5, 22, 39)
    assert [event[2] for event in events if event[0] == "sample"] == [False, False]
    assert entries[1]["plan"].get("continuation_method") is None
    assert session["settings"]["continuation_method"] == CONTINUATION_GUIDE
    assert "Continuation method: Guide / Motion Context" in report


def test_driving_audio_disables_generated_audio_continuity_for_native_mask(monkeypatch):
    events = []
    kwargs = _install_common_runtime(monkeypatch, events)
    _enable_driving_audio(monkeypatch, kwargs)
    kwargs["continuity"] = V2_CONTINUITY_OPTIONS[1]  # 22 frames is video-valid, AV-inexact.
    masked_audio_contexts = []

    def masked(latent, *, video_context, audio_context, context_frames):
        masked_audio_contexts.append(audio_context)
        latent = dict(latent)
        latent["noise_mask"] = "native-mask"
        return latent

    monkeypatch.setattr(sequence, "apply_native_masked_continuation", masked)

    with continuation_method_scope(CONTINUATION_NATIVE_MASKED):
        entries, _last_state, session, report = sequence.run_sequence(**kwargs)

    assert masked_audio_contexts == [None]
    assert entries[1]["plan"]["trim_frames"] == 22
    assert session["settings"]["driving_audio_contract"] == {"test": "driving-audio"}
    assert "generated-audio continuation is disabled" in report


def test_driving_audio_also_prevents_legacy_guide_from_reusing_generated_audio(monkeypatch):
    events = []
    kwargs = _install_common_runtime(monkeypatch, events)
    _enable_driving_audio(monkeypatch, kwargs)
    guide_audio_contexts = []

    def guide(conditioning, **kwargs):
        guide_audio_contexts.append(kwargs["audio_context"])
        return conditioning

    monkeypatch.setattr(sequence, "prepare_conditioning", guide)

    with continuation_method_scope(CONTINUATION_GUIDE):
        sequence.run_sequence(**kwargs)

    assert guide_audio_contexts == [None]
