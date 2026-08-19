from types import SimpleNamespace

import pytest
import torch

from ComfyUI_H3_Continuum_Join.constants import (
    DIAGNOSTICS_BASIC,
    PROMPT_MODE_FIXED,
    V2_CONTINUITY_OPTIONS,
)
from ComfyUI_H3_Continuum_Join.temporal import audio_latent_t, video_latent_t
from ComfyUI_H3_Continuum_Join.v2 import sequence
from ComfyUI_H3_Continuum_Join.v2.h3_builder import IdentityAssets
from ComfyUI_H3_Continuum_Join.v2.prompts import make_prompt_plan
from ComfyUI_H3_Continuum_Join.v3.plan import (
    ASSEMBLY_PLAN_MAGIC,
    AssemblyPlanError,
    validate_assembly_plan,
)


class Nested:
    def __init__(self, parts):
        self.parts = list(parts)

    def unbind(self):
        return self.parts


def _latent(width, height, frames):
    return {
        "samples": Nested(
            (
                torch.zeros(
                    1,
                    24,
                    video_latent_t(frames),
                    height // 16,
                    width // 16,
                ),
                torch.zeros(1, 32, 2, audio_latent_t(frames)),
            )
        )
    }


class FakeClip:
    def tokenize(self, prompt, images):
        return prompt

    def encode_from_tokens_scheduled(self, tokens):
        return [[torch.zeros(1, 1, 2), {}]]


def _fake_model():
    return SimpleNamespace(
        model=SimpleNamespace(diffusion_model=SimpleNamespace()),
        model_options={},
        wrappers={},
        model_dtype=lambda: torch.bfloat16,
        model_size=lambda: 0,
    )


def test_final_chunk_rounds_up_without_changing_intermediate_nearest_grid(monkeypatch):
    width, height = 96, 64
    assets = IdentityAssets(None, None, None, None, "none")
    model = _fake_model()

    monkeypatch.setattr(sequence, "check_comfy_h3_runtime", lambda: [])
    monkeypatch.setattr(sequence, "prepare_identity_assets", lambda *a, **k: assets)
    monkeypatch.setattr(sequence, "encode_identity_latents", lambda *a, **k: assets)
    monkeypatch.setattr(sequence, "empty_h3_latent", _latent)
    monkeypatch.setattr(sequence, "accelerator_summary", lambda _model: "accelerators")
    monkeypatch.setattr(
        sequence,
        "clone_model_for_chunk",
        lambda model, **kwargs: model,
    )
    monkeypatch.setattr(
        sequence,
        "sample_chunk",
        lambda **kwargs: kwargs["latent"],
    )

    prompt_plan = make_prompt_plan(
        mode=PROMPT_MODE_FIXED,
        script="continuous motion",
        chunks=3,
        chunk_seconds=7.0,
    )
    entries, _last_state, _session, _report = sequence.run_sequence(
        model=model,
        clip=FakeClip(),
        video_vae=object(),
        audio_vae=None,
        sampler=object(),
        sigmas=torch.tensor([1.0, 0.0]),
        first_frame=None,
        last_frame=None,
        prompt_plan=prompt_plan,
        width=width,
        height=height,
        continuity=V2_CONTINUITY_OPTIONS[1],
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

    plans = [entry["plan"] for entry in entries]
    assert [plan["total_frames"] for plan in plans] == [175, 175, 209]
    assert [plan["net_frames"] for plan in plans] == [175, 153, 187]
    assert sum(plan["net_frames"] for plan in plans) == 515
    assert sum(plan["net_frames"] for plan in plans) >= 3 * 7 * 24


def test_short_cached_final_chunk_is_not_reused(monkeypatch):
    monkeypatch.setattr(sequence, "validate_session", lambda session: session)
    monkeypatch.setattr(sequence, "validate_chunk_entry", lambda entry: entry)

    session = {
        "width": 96,
        "height": 64,
        "chunk_seconds": 7.0,
        "identity_hash": "none",
        "chunks": [
            {"prompt_hash": "p1", "plan": {"net_frames": 175}},
            {"prompt_hash": "p2", "plan": {"net_frames": 153}},
        ],
    }

    preserved, notes = sequence._preserved_prefix(
        session=session,
        prompt_hashes=["p1", "p2"],
        chunks=2,
        reroll_from_chunk=0,
        width=96,
        height=64,
        chunk_seconds=7.0,
        identity_hash="none",
    )

    assert len(preserved) == 1
    assert any("retained 328 frames for 336-frame target" in note for note in notes)


def test_cached_final_chunk_at_or_above_target_remains_reusable(monkeypatch):
    monkeypatch.setattr(sequence, "validate_session", lambda session: session)
    monkeypatch.setattr(sequence, "validate_chunk_entry", lambda entry: entry)

    session = {
        "width": 96,
        "height": 64,
        "chunk_seconds": 7.0,
        "identity_hash": "none",
        "chunks": [
            {"prompt_hash": "p1", "plan": {"net_frames": 175}},
            {"prompt_hash": "p2", "plan": {"net_frames": 170}},
        ],
    }

    preserved, _notes = sequence._preserved_prefix(
        session=session,
        prompt_hashes=["p1", "p2"],
        chunks=2,
        reroll_from_chunk=0,
        width=96,
        height=64,
        chunk_seconds=7.0,
        identity_hash="none",
    )

    assert len(preserved) == 2


def test_v3_assembly_plan_rejects_legacy_under_length_sequence():
    plan = {
        "magic": ASSEMBLY_PLAN_MAGIC,
        "schema_version": 1,
        "fps": 24,
        "width": 96,
        "height": 64,
        "chunk_seconds": 7.0,
        "target_frames": 336,
        "preserve_final_frame": False,
        "chunks": [
            {
                "sequence_index": 1,
                "chunk_index": 1,
                "total_frames": 175,
                "trim_frames": 0,
                "net_frames": 175,
                "context_frames": 5,
                "expected_video_latent_t": 52,
                "expected_audio_latent_t": 292,
            },
            {
                "sequence_index": 2,
                "chunk_index": 2,
                "total_frames": 175,
                "trim_frames": 22,
                "net_frames": 153,
                "context_frames": 22,
                "expected_video_latent_t": 52,
                "expected_audio_latent_t": 292,
            },
        ],
    }

    with pytest.raises(
        AssemblyPlanError,
        match="retains 328 frames for a 336-frame target",
    ):
        validate_assembly_plan(plan)
