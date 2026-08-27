from __future__ import annotations

import hashlib
import sys
from types import ModuleType, SimpleNamespace

import pytest
import torch

from ComfyUI_H3_Continuum_Join.constants import (
    CONTINUITY_OPTIONS,
    CONTINUUM_INTEROP_KEY,
    DIAGNOSTICS_BASIC,
    PROMPT_MODE_FIXED,
    PROMPT_MODE_LIST,
    V2_CONTINUITY_OPTIONS,
)
from ComfyUI_H3_Continuum_Join.temporal import (
    audio_grid_offset,
    audio_latent_t,
    context_slots,
    make_extension_shape,
    video_latent_t,
)
from ComfyUI_H3_Continuum_Join.v2.h3_builder import IdentityAssets
from ComfyUI_H3_Continuum_Join.v2.prompts import make_prompt_plan
from ComfyUI_H3_Continuum_Join.v2 import sequence
from ComfyUI_H3_Continuum_Join.v2.seeds import derive_chunk_seed
from ComfyUI_H3_Continuum_Join.v3.plan import prepare_physical_decode_entries
from ComfyUI_H3_Continuum_Join.v3.masked_continuation import (
    MASKED_AV_PREFIX_22_V1,
    MASKED_AV_PREFIX_39_V1,
    MASKED_VIDEO_PREFIX_V1,
    build_masked_av_prefix_latent,
    build_masked_video_prefix_latent,
    restore_masked_av_prefix,
)


class Nested:
    def __init__(self, parts):
        self.parts = list(parts)

    def unbind(self):
        return self.parts


class FakeClip:
    def tokenize(self, prompt, images):
        return prompt

    def encode_from_tokens_scheduled(self, tokens):
        return [[torch.zeros(1, 1, 2), {}]]


def _install_nested_tensor(monkeypatch):
    nested_module = ModuleType("comfy.nested_tensor")
    nested_module.NestedTensor = Nested
    comfy_module = sys.modules.get("comfy") or ModuleType("comfy")
    comfy_module.nested_tensor = nested_module
    monkeypatch.setitem(sys.modules, "comfy", comfy_module)
    monkeypatch.setitem(sys.modules, "comfy.nested_tensor", nested_module)


def _latent(width, height, frames, *, fill=0.0):
    return {
        "samples": Nested(
            (
                torch.full(
                    (1, 24, video_latent_t(frames), height // 16, width // 16),
                    float(fill),
                ),
                torch.full((1, 32, 2, audio_latent_t(frames)), float(fill)),
            )
        )
    }


def _sha256(tensor):
    value = tensor.detach().to("cpu").contiguous()
    return hashlib.sha256(value.view(torch.uint8).numpy().tobytes()).hexdigest()


def test_nondefault_transport_scopes_session_and_run_storage_identity():
    base_hash = "a" * 64

    assert sequence._continuation_transport_identity(
        base_hash, sequence.REFERENCE_CONTEXT_V1
    ) == base_hash
    masked_hash = sequence._continuation_transport_identity(
        base_hash, MASKED_AV_PREFIX_22_V1
    )
    assert masked_hash != base_hash
    assert masked_hash == sequence._continuation_transport_identity(
        base_hash, MASKED_AV_PREFIX_22_V1
    )
    assert masked_hash != sequence._continuation_transport_identity(
        base_hash, MASKED_AV_PREFIX_39_V1
    )

    assert sequence._terminal_execution_semantics(
        merge_enabled=False,
        continuation_transport=sequence.REFERENCE_CONTEXT_V1,
    ) is None
    assert sequence._terminal_execution_semantics(
        merge_enabled=False,
        continuation_transport=MASKED_AV_PREFIX_22_V1,
    ) == {"continuation_transport": MASKED_AV_PREFIX_22_V1}
    assert sequence._terminal_execution_semantics(
        merge_enabled=True,
        prompt_policy=sequence.TERMINAL_PROMPT_POLICY_TIMELINE,
        continuation_transport=MASKED_AV_PREFIX_22_V1,
    ) == {
        "flf_execution": sequence.FLF_STRATEGY,
        "terminal_seed_policy": sequence.TERMINAL_SEED_POLICY,
        "terminal_prompt_policy": sequence.TERMINAL_PROMPT_POLICY_TIMELINE,
        "continuation_transport": MASKED_AV_PREFIX_22_V1,
    }


def test_masked_av_39f_temporal_contract_is_exact_duration_with_known_grid_phase():
    shape = make_extension_shape(39, 5.0)

    assert context_slots(39) == 12
    assert audio_latent_t(39) == 65
    assert shape.total_frames == 158
    assert shape.net_new_frames == 119
    assert shape.video_latent_t == 47
    assert shape.audio_latent_t == 263
    assert audio_grid_offset(124, 207) == pytest.approx(1.0 / 3.0)
    assert audio_grid_offset(158, 263) == pytest.approx(-1.0 / 3.0)


def test_masked_av_22f_temporal_contract_preserves_balanced_asymmetry():
    shape = make_extension_shape(22, 5.0)

    assert context_slots(22) == 7
    assert audio_latent_t(22) == 37
    assert shape.total_frames == 141
    assert shape.net_new_frames == 119
    assert shape.video_latent_t == 42
    assert shape.audio_latent_t == 235
    video_seconds = 22 / 24
    audio_seconds = 37 / 40
    assert audio_seconds - video_seconds == pytest.approx(1.0 / 120.0)


def test_build_masked_video_prefix_latent_preserves_normalized_prefix(monkeypatch):
    _install_nested_tensor(monkeypatch)
    target = _latent(96, 64, 141)
    target_video, target_audio = target["samples"].unbind()
    context = torch.arange(
        1 * 24 * 7 * 4 * 6,
        dtype=torch.float64,
    ).reshape(1, 24, 7, 4, 6)
    source_before = context.clone()
    target_video_before = target_video.clone()
    target_audio_before = target_audio.clone()

    result = build_masked_video_prefix_latent(target, context, 22)
    video, audio = result["samples"].unbind()
    video_mask, audio_mask = result["noise_mask"].unbind()
    normalized = context.to(dtype=video.dtype)

    assert torch.equal(video[:, :, :7], normalized)
    assert _sha256(video[:, :, :7]) == _sha256(normalized)
    assert torch.count_nonzero(video[:, :, 7:]) == 0
    assert torch.equal(audio, target_audio_before)
    assert tuple(video_mask.shape) == (1, 1, 42, 4, 6)
    assert torch.count_nonzero(video_mask[:, :, :7]) == 0
    assert torch.all(video_mask[:, :, 7:] == 1)
    assert tuple(audio_mask.shape) == (1, 1, 2, 235)
    assert torch.all(audio_mask == 1)
    assert torch.equal(context, source_before)
    assert torch.equal(target_video, target_video_before)
    assert torch.equal(target_audio, target_audio_before)
    assert "noise_mask" not in target


def test_build_masked_av_prefix_latent_preserves_exact_39f_65t_prefixes(
    monkeypatch,
):
    _install_nested_tensor(monkeypatch)
    target = _latent(96, 64, 158)
    target_video, target_audio = target["samples"].unbind()
    video_context = torch.arange(
        1 * 24 * 12 * 4 * 6,
        dtype=torch.float64,
    ).reshape(1, 24, 12, 4, 6)
    audio_context = torch.arange(
        1 * 32 * 2 * 65,
        dtype=torch.float64,
    ).reshape(1, 32, 2, 65)
    source_video = video_context.clone()
    source_audio = audio_context.clone()
    target_video_before = target_video.clone()
    target_audio_before = target_audio.clone()

    result = build_masked_av_prefix_latent(
        target,
        video_context,
        audio_context,
        39,
    )
    video, audio = result["samples"].unbind()
    video_mask, audio_mask = result["noise_mask"].unbind()
    normalized_video = video_context.to(video)
    normalized_audio = audio_context.to(audio)

    assert tuple(video.shape) == (1, 24, 47, 4, 6)
    assert tuple(audio.shape) == (1, 32, 2, 263)
    assert torch.equal(video[:, :, :12], normalized_video)
    assert torch.equal(audio[..., :65], normalized_audio)
    assert _sha256(video[:, :, :12]) == _sha256(normalized_video)
    assert _sha256(audio[..., :65]) == _sha256(normalized_audio)
    assert torch.count_nonzero(video[:, :, 12:]) == 0
    assert torch.count_nonzero(audio[..., 65:]) == 0
    assert tuple(video_mask.shape) == (1, 1, 47, 4, 6)
    assert tuple(audio_mask.shape) == (1, 1, 2, 263)
    assert torch.count_nonzero(video_mask[:, :, :12]) == 0
    assert torch.all(video_mask[:, :, 12:] == 1)
    assert torch.count_nonzero(audio_mask[..., :65]) == 0
    assert torch.all(audio_mask[..., 65:] == 1)
    assert torch.equal(video_context, source_video)
    assert torch.equal(audio_context, source_audio)
    assert torch.equal(target_video, target_video_before)
    assert torch.equal(target_audio, target_audio_before)
    assert "noise_mask" not in target


def test_build_masked_av_prefix_latent_preserves_balanced_22f_37t_prefixes(
    monkeypatch,
):
    _install_nested_tensor(monkeypatch)
    target = _latent(96, 64, 141)
    video_context = torch.arange(
        1 * 24 * 7 * 4 * 6,
        dtype=torch.float64,
    ).reshape(1, 24, 7, 4, 6)
    audio_context = torch.arange(
        1 * 32 * 2 * 37,
        dtype=torch.float64,
    ).reshape(1, 32, 2, 37)

    result = build_masked_av_prefix_latent(
        target,
        video_context,
        audio_context,
        22,
    )
    video, audio = result["samples"].unbind()
    video_mask, audio_mask = result["noise_mask"].unbind()

    assert tuple(video.shape) == (1, 24, 42, 4, 6)
    assert tuple(audio.shape) == (1, 32, 2, 235)
    assert torch.equal(video[:, :, :7], video_context.to(video))
    assert torch.equal(audio[..., :37], audio_context.to(audio))
    assert torch.count_nonzero(video_mask[:, :, :7]) == 0
    assert torch.all(video_mask[:, :, 7:] == 1)
    assert torch.count_nonzero(audio_mask[..., :37]) == 0
    assert torch.all(audio_mask[..., 37:] == 1)


def test_restore_masked_av_prefix_does_not_restore_generated_regions(monkeypatch):
    _install_nested_tensor(monkeypatch)
    target = _latent(96, 64, 158)
    video_context = torch.arange(
        1 * 24 * 12 * 4 * 6,
        dtype=torch.float32,
    ).reshape(1, 24, 12, 4, 6)
    audio_context = torch.arange(
        1 * 32 * 2 * 65,
        dtype=torch.float32,
    ).reshape(1, 32, 2, 65)
    masked = build_masked_av_prefix_latent(
        target,
        video_context,
        audio_context,
        39,
    )
    masked_video, masked_audio = masked["samples"].unbind()
    sampled_video = masked_video.clone()
    sampled_audio = masked_audio.clone()
    sampled_video[:, :, :12] = torch.nextafter(
        sampled_video[:, :, :12],
        torch.full_like(sampled_video[:, :, :12], float("inf")),
    )
    sampled_audio[..., :65] = torch.nextafter(
        sampled_audio[..., :65],
        torch.full_like(sampled_audio[..., :65], float("inf")),
    )
    sampled_video[:, :, 12:] = 7.0
    sampled_audio[..., 65:] = 11.0
    sampled = {"samples": Nested((sampled_video, sampled_audio))}

    restored = restore_masked_av_prefix(sampled, masked, 39)
    restored_video, restored_audio = restored["samples"].unbind()

    assert torch.equal(restored_video[:, :, :12], masked_video[:, :, :12])
    assert torch.equal(restored_audio[..., :65], masked_audio[..., :65])
    assert torch.all(restored_video[:, :, 12:] == 7.0)
    assert torch.all(restored_audio[..., 65:] == 11.0)
    assert torch.all(sampled_video[:, :, 12:] == 7.0)
    assert torch.all(sampled_audio[..., 65:] == 11.0)


@pytest.mark.parametrize(
    "context",
    (
        torch.zeros(1, 24, 6, 4, 6),
        torch.zeros(1, 24, 7, 5, 6),
        torch.zeros(1, 23, 7, 4, 6),
    ),
)
def test_build_masked_video_prefix_latent_rejects_invalid_context(
    monkeypatch, context
):
    _install_nested_tensor(monkeypatch)
    with pytest.raises(ValueError):
        build_masked_video_prefix_latent(_latent(96, 64, 141), context, 22)


@pytest.mark.parametrize(
    "audio_context",
    (
        torch.zeros(1, 32, 2, 64),
        torch.zeros(1, 31, 2, 65),
        torch.full((1, 32, 2, 65), float("nan")),
    ),
)
def test_build_masked_av_prefix_latent_rejects_invalid_audio_context(
    monkeypatch, audio_context
):
    _install_nested_tensor(monkeypatch)
    video_context = torch.zeros(1, 24, 12, 4, 6)
    with pytest.raises(ValueError):
        build_masked_av_prefix_latent(
            _latent(96, 64, 158),
            video_context,
            audio_context,
            39,
        )


@pytest.mark.parametrize(
    (
        "transport",
        "continuity",
        "context_frames",
        "video_slots",
        "audio_steps",
        "total_frames",
    ),
    (
        (
            MASKED_VIDEO_PREFIX_V1,
            V2_CONTINUITY_OPTIONS[1],
            22,
            7,
            0,
            141,
        ),
        (
            MASKED_AV_PREFIX_22_V1,
            V2_CONTINUITY_OPTIONS[1],
            22,
            7,
            37,
            141,
        ),
        (
            MASKED_AV_PREFIX_39_V1,
            CONTINUITY_OPTIONS[2],
            39,
            12,
            65,
            158,
        ),
    ),
)
def test_sequence_masked_transport_uses_target_mask_without_reference_interop(
    monkeypatch,
    transport,
    continuity,
    context_frames,
    video_slots,
    audio_steps,
    total_frames,
):
    _install_nested_tensor(monkeypatch)
    width, height = 96, 64
    events = []
    sample_inputs = []
    fake_model = SimpleNamespace(
        model=SimpleNamespace(diffusion_model=SimpleNamespace()),
        model_options={},
        wrappers={},
        model_dtype=lambda: torch.bfloat16,
        model_size=lambda: 0,
    )
    first_latent = torch.full((1, 24, 1, height // 16, width // 16), 0.25)
    assets = IdentityAssets(
        torch.zeros(1, height, width, 3),
        first_latent,
        None,
        None,
        "i2va-first-image",
    )

    monkeypatch.setattr(sequence, "check_comfy_h3_runtime", lambda: [])
    monkeypatch.setattr(sequence, "prepare_identity_assets", lambda *a, **k: assets)
    monkeypatch.setattr(sequence, "encode_identity_latents", lambda *a, **k: assets)
    monkeypatch.setattr(sequence, "empty_h3_latent", _latent)
    monkeypatch.setattr(sequence, "accelerator_summary", lambda model: "accelerators")

    def clone_model_for_chunk(model, *, strict, debug, chunk_index, context_frames):
        options = dict(model.model_options)
        transformer_options = dict(options.get("transformer_options") or {})
        if context_frames is not None:
            transformer_options[CONTINUUM_INTEROP_KEY] = {"active": True}
        options["transformer_options"] = transformer_options
        events.append(("clone", chunk_index, context_frames))
        return SimpleNamespace(
            model=model.model,
            model_options=options,
            wrappers=model.wrappers,
            model_dtype=model.model_dtype,
            model_size=model.model_size,
        )

    call_index = 0

    def sample_chunk(**kwargs):
        nonlocal call_index
        call_index += 1
        latent = kwargs["latent"]
        video, audio = latent["samples"].unbind()
        conditioning = kwargs["conditioning"]
        metadata = conditioning[0][1]
        sample_inputs.append((video.clone(), audio.clone(), latent.get("noise_mask")))
        events.append(
            (
                "sample",
                call_index,
                metadata.get("minimax_refs"),
                kwargs["model"].model_options["transformer_options"].get(
                    CONTINUUM_INTEROP_KEY
                ),
                metadata.get("minimax_frame_count"),
                metadata.get("minimax_keyframes"),
            )
        )
        if call_index == 1:
            video = torch.arange(video.numel(), dtype=video.dtype).reshape_as(video)
            audio = torch.arange(audio.numel(), dtype=audio.dtype).reshape_as(audio)
            return {"samples": Nested((video, audio))}
        before_prefix = video[:, :, :video_slots].clone()
        before_audio_prefix = (
            audio[..., :audio_steps].clone() if audio_steps else None
        )
        sampled_video = video.clone()
        sampled_audio = audio.clone()
        # Core restores at each model call, but sampler integration may leave a
        # final float32 rounding delta. The private sequence path reapplies only
        # the preserved prefix after sampling.
        sampled_video[:, :, :video_slots] = torch.nextafter(
            sampled_video[:, :, :video_slots],
            torch.full_like(
                sampled_video[:, :, :video_slots],
                float("inf"),
            ),
        )
        sampled_video[:, :, video_slots:] += 1
        assert not torch.equal(
            before_prefix,
            sampled_video[:, :, :video_slots],
        )
        if audio_steps:
            sampled_audio[..., :audio_steps] = torch.nextafter(
                sampled_audio[..., :audio_steps],
                torch.full_like(
                    sampled_audio[..., :audio_steps],
                    float("inf"),
                ),
            )
            sampled_audio[..., audio_steps:] += 2
            assert not torch.equal(
                before_audio_prefix,
                sampled_audio[..., :audio_steps],
            )
        return {"samples": Nested((sampled_video, sampled_audio))}

    monkeypatch.setattr(sequence, "clone_model_for_chunk", clone_model_for_chunk)
    monkeypatch.setattr(sequence, "sample_chunk", sample_chunk)

    plan = make_prompt_plan(
        mode=PROMPT_MODE_FIXED,
        script="continuous shot",
        chunks=2,
        chunk_seconds=5.0,
    )
    entries, last_state, session, report = sequence.run_sequence(
        model=fake_model,
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
        continuity=continuity,
        base_seed=42,
        audio_continuity=False,
        exact_total_duration=False,
        diagnostics_mode=DIAGNOSTICS_BASIC,
        reroll_from_chunk=0,
        reroll_nonce=0,
        strict_compatibility=False,
        debug=False,
        latent_only=True,
        continuation_transport=transport,
    )

    first_video = entries[0]["video"]
    second_video, second_audio, masks = sample_inputs[1]
    video_mask, audio_mask = masks.unbind()
    expected_prefix = first_video[:, :, -video_slots:].to(second_video)
    assert torch.equal(second_video[:, :, :video_slots], expected_prefix)
    assert _sha256(second_video[:, :, :video_slots]) == _sha256(expected_prefix)
    assert tuple(second_video.shape) == (
        1,
        24,
        video_latent_t(total_frames),
        4,
        6,
    )
    assert tuple(second_audio.shape) == (
        1,
        32,
        2,
        audio_latent_t(total_frames),
    )
    assert torch.count_nonzero(video_mask[:, :, :video_slots]) == 0
    assert torch.all(video_mask[:, :, video_slots:] == 1)
    if audio_steps:
        first_audio = entries[0]["audio"]
        expected_audio_prefix = first_audio[..., -audio_steps:].to(second_audio)
        assert torch.equal(
            second_audio[..., :audio_steps],
            expected_audio_prefix,
        )
        assert torch.count_nonzero(audio_mask[..., :audio_steps]) == 0
        assert torch.all(audio_mask[..., audio_steps:] == 1)
    else:
        assert torch.all(audio_mask == 1)
    second_sample = next(
        event for event in events if event[0] == "sample" and event[1] == 2
    )
    assert second_sample[2] is None
    assert second_sample[3] is None
    assert second_sample[4] == total_frames
    first_sample = next(
        event for event in events if event[0] == "sample" and event[1] == 1
    )
    assert len(first_sample[5]) == 1
    assert first_sample[5][0]["resolved_frame_index"] == 0
    assert first_sample[5][0]["latent"] is first_latent
    assert second_sample[5] is None
    assert [event[2] for event in events if event[0] == "clone"] == [None, None]
    assert entries[1]["plan"]["total_frames"] == total_frames
    assert entries[1]["plan"]["trim_frames"] == context_frames
    assert entries[1]["plan"]["net_frames"] == 119
    assert torch.equal(
        entries[1]["video"][:, :, :video_slots],
        expected_prefix,
    )
    if audio_steps:
        assert torch.equal(
            entries[1]["audio"][..., :audio_steps],
            expected_audio_prefix,
        )
        assert torch.all(entries[1]["audio"][..., audio_steps:] == 2)
        assert f"masked AV target prefix {context_frames}f/{audio_steps}T" in report
        assert "source_audio_grid_offset=0.333333" in report
    else:
        assert "masked video target prefix" in report
    assert last_state["clip_index"] == 2
    assert len(session["chunks"]) == 2
    assert "interop=not_emitted" in report


@pytest.mark.parametrize(
    ("transport", "audio_steps"),
    (
        (MASKED_VIDEO_PREFIX_V1, 0),
        (MASKED_AV_PREFIX_22_V1, 37),
    ),
)
def test_fl2va_terminal_merge_uses_masked_prefix_without_reference_rows(
    monkeypatch,
    transport,
    audio_steps,
):
    _install_nested_tensor(monkeypatch)
    width, height = 96, 64
    first_latent = torch.full((1, 24, 1, 4, 6), 0.25)
    last_latent = torch.full((1, 24, 1, 4, 6), 0.75)
    assets = IdentityAssets(
        torch.zeros(1, height, width, 3),
        first_latent,
        torch.ones(1, height, width, 3),
        last_latent,
        "fl2va-identity",
    )
    model = SimpleNamespace(
        model=SimpleNamespace(diffusion_model=SimpleNamespace()),
        model_options={},
        wrappers={},
        model_dtype=lambda: torch.bfloat16,
        model_size=lambda: 0,
    )
    samples = []
    clones = []
    finalized_physical = []

    monkeypatch.setattr(sequence, "check_comfy_h3_runtime", lambda: [])
    monkeypatch.setattr(sequence, "prepare_identity_assets", lambda *a, **k: assets)
    monkeypatch.setattr(sequence, "encode_identity_latents", lambda *a, **k: assets)
    monkeypatch.setattr(sequence, "empty_h3_latent", _latent)
    monkeypatch.setattr(sequence, "accelerator_summary", lambda _model: "accelerators")
    monkeypatch.setattr(
        sequence,
        "latent_from_cpu",
        lambda video, audio: {"samples": Nested((video, audio))},
    )

    def latent_to_cpu(latent):
        video, audio = latent["samples"].unbind()
        finalized_physical.append((video.clone(), audio.clone()))
        return video, audio

    monkeypatch.setattr(sequence, "latent_to_cpu", latent_to_cpu)

    def clone_model_for_chunk(model, *, context_frames, **_kwargs):
        clones.append(context_frames)
        return model

    monkeypatch.setattr(sequence, "clone_model_for_chunk", clone_model_for_chunk)

    def sample_chunk(**kwargs):
        latent = kwargs["latent"]
        video, audio = latent["samples"].unbind()
        masks = latent.get("noise_mask")
        metadata = kwargs["conditioning"][0][1]
        samples.append(
            {
                "video": video.clone(),
                "audio": audio.clone(),
                "masks": masks,
                "metadata": metadata,
                "seed": kwargs["seed"],
            }
        )
        if len(samples) == 1:
            return {
                "samples": Nested(
                    (
                        torch.arange(video.numel(), dtype=video.dtype).reshape_as(video),
                        torch.arange(audio.numel(), dtype=audio.dtype).reshape_as(audio),
                    )
                )
            }
        sampled_video = video.clone()
        sampled_audio = audio.clone()
        sampled_video[:, :, :7] = torch.nextafter(
            sampled_video[:, :, :7],
            torch.full_like(sampled_video[:, :, :7], float("inf")),
        )
        sampled_video[:, :, 7:] = 7.0
        if audio_steps:
            sampled_audio[..., :audio_steps] = torch.nextafter(
                sampled_audio[..., :audio_steps],
                torch.full_like(sampled_audio[..., :audio_steps], float("inf")),
            )
            sampled_audio[..., audio_steps:] = 11.0
        else:
            sampled_audio.fill_(11.0)
        return {"samples": Nested((sampled_video, sampled_audio))}

    monkeypatch.setattr(sequence, "sample_chunk", sample_chunk)

    plan = make_prompt_plan(
        mode=PROMPT_MODE_LIST,
        script="first\n---\nmiddle\n---\nlast",
        chunks=3,
        chunk_seconds=5.0,
    )
    entries, _last_state, _session, report = sequence.run_sequence(
        model=model,
        clip=FakeClip(),
        video_vae=object(),
        audio_vae=object(),
        sampler=object(),
        sigmas=torch.tensor([1.0, 0.0]),
        first_frame=assets.first_image,
        last_frame=assets.last_image,
        prompt_plan=plan,
        width=width,
        height=height,
        continuity=V2_CONTINUITY_OPTIONS[1],
        base_seed=42,
        audio_continuity=bool(audio_steps),
        exact_total_duration=False,
        diagnostics_mode=DIAGNOSTICS_BASIC,
        reroll_from_chunk=0,
        reroll_nonce=0,
        strict_compatibility=False,
        debug=False,
        latent_only=True,
        continuation_transport=transport,
    )

    assert len(samples) == 2
    assert len(entries) == 3
    assert clones == [None, None]
    first_sample, terminal_sample = samples
    assert first_sample["masks"] is None
    assert first_sample["metadata"]["minimax_keyframes"] == [
        {"resolved_frame_index": 0, "latent": first_latent}
    ]
    assert tuple(terminal_sample["video"].shape) == (1, 24, 77, 4, 6)
    assert tuple(terminal_sample["audio"].shape) == (1, 32, 2, 433)
    assert terminal_sample["metadata"].get("minimax_refs") is None
    terminal_keyframes = terminal_sample["metadata"]["minimax_keyframes"]
    assert terminal_keyframes == [
        {"resolved_frame_index": 259, "latent": last_latent}
    ]
    video_mask, audio_mask = terminal_sample["masks"].unbind()
    assert torch.count_nonzero(video_mask[:, :, :7]) == 0
    assert torch.all(video_mask[:, :, 7:] == 1)
    expected_video_prefix = entries[0]["video"][:, :, -7:].to(
        terminal_sample["video"]
    )
    assert torch.equal(terminal_sample["video"][:, :, :7], expected_video_prefix)
    if audio_steps:
        assert torch.count_nonzero(audio_mask[..., :audio_steps]) == 0
        assert torch.all(audio_mask[..., audio_steps:] == 1)
        expected_audio_prefix = entries[0]["audio"][..., -audio_steps:].to(
            terminal_sample["audio"]
        )
        assert torch.equal(
            terminal_sample["audio"][..., :audio_steps],
            expected_audio_prefix,
        )
    else:
        assert torch.all(audio_mask == 1)

    final_video, final_audio = finalized_physical[0]
    assert torch.equal(final_video[:, :, :7], expected_video_prefix)
    assert torch.all(final_video[:, :, 7:] == 7.0)
    if audio_steps:
        assert torch.equal(final_audio[..., :audio_steps], expected_audio_prefix)
        assert torch.all(final_audio[..., audio_steps:] == 11.0)
    else:
        assert torch.all(final_audio == 11.0)

    expected_seed = derive_chunk_seed(42, 1, 0)
    assert terminal_sample["seed"] == expected_seed
    assert entries[1]["seed"] == expected_seed
    assert entries[2]["seed"] == expected_seed
    decode_entries, assembly_plan = prepare_physical_decode_entries(
        entries,
        chunk_seconds=5.0,
        preserve_final_frame=True,
        terminal_merged=True,
    )
    assert len(decode_entries) == 2
    assert assembly_plan["logical_chunk_count"] == 3
    assert assembly_plan["physical_decode_group_count"] == 2
    terminal_group = assembly_plan["decode_groups"][1]
    assert terminal_group["logical_chunk_indices"] == [2, 3]
    assert terminal_group["terminal_merged"] is True
    assert terminal_group["total_frames"] == 260
    assert terminal_group["trim_frames"] == 22
    assert terminal_group["expected_video_latent_t"] == 77
    assert terminal_group["expected_audio_latent_t"] == 433
    recombined_video = decode_entries[1]["video"]
    recombined_audio = decode_entries[1]["audio"]
    assert torch.equal(recombined_video, final_video)
    assert torch.equal(recombined_audio, final_audio)
    assert "paired_timeline_v1" in report
    assert "physical_frames=260" in report
