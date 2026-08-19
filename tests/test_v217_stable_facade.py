from pathlib import Path

import pytest

from ComfyUI_H3_Continuum_Join.constants import PROMPT_FORMAT_OPTIONS
from ComfyUI_H3_Continuum_Join.v2.nodes import (
    H3ContinuumAdvanced,
    H3ContinuumClipOverrides,
    H3ContinuumResult,
    H3ContinuumSampler,
    H3ContinuumSamplerV2,
    NODE_CLASS_MAPPINGS,
)
from ComfyUI_H3_Continuum_Join.v2.prompts import PromptPlanError


ROOT = Path(__file__).resolve().parents[1]


def test_v217_registers_static_facade_and_preserves_legacy_sampler():
    assert NODE_CLASS_MAPPINGS["H3ContinuumSampler"] is H3ContinuumSampler
    assert NODE_CLASS_MAPPINGS["H3ContinuumSamplerV2"] is H3ContinuumSamplerV2
    assert NODE_CLASS_MAPPINGS["H3ContinuumClipOverrides"] is H3ContinuumClipOverrides
    assert NODE_CLASS_MAPPINGS["H3ContinuumAdvanced"] is H3ContinuumAdvanced
    assert NODE_CLASS_MAPPINGS["H3ContinuumResult"] is H3ContinuumResult


def test_v217_facade_schema_is_static_and_compact():
    schema = H3ContinuumSampler.INPUT_TYPES()
    required = schema["required"]
    optional = schema["optional"]

    assert "sequence_prompt" in required
    assert required["sequence_prompt"][1]["forceInput"] is True
    assert "prompt_script" not in required
    assert "prompt_overrides" in optional
    assert "advanced" in optional
    assert not any(name.startswith("clip_") for name in required | optional)
    assert set(H3ContinuumSampler.RETURN_NAMES) == {"images", "audio", "result"}


def test_v217_pack_nodes_have_no_dynamic_clip_sockets():
    clip_schema = H3ContinuumClipOverrides.INPUT_TYPES()["required"]
    assert set(clip_schema) == {"prompt_mode", "override_script"}
    assert clip_schema["override_script"][1]["forceInput"] is True

    advanced = H3ContinuumAdvanced.INPUT_TYPES()
    assert set(advanced["optional"]) == {
        "last_frame",
        "session",
        "initial_state",
        "prompt_plan",
    }


def test_v217_facade_delegates_to_legacy_core(monkeypatch):
    captured = {}

    def fake_run(_self, **kwargs):
        captured.update(kwargs)
        return "images", "audio", "state", "session", "report"

    monkeypatch.setattr(H3ContinuumSamplerV2, "run", fake_run)
    facade = H3ContinuumSampler()
    result = facade.run(
        model="model",
        clip="clip",
        video_vae="video_vae",
        audio_vae="audio_vae",
        sampler="sampler",
        sigmas="sigmas",
        sequence_prompt="base prompt",
        prompt_mode=PROMPT_FORMAT_OPTIONS[0],
        chunks=3,
        chunk_seconds=5.0,
        width=1344,
        height=768,
        continuity="Balanced - 22 frames",
        base_seed=123,
        seam_correction="Auto",
    )

    assert result == (
        "images",
        "audio",
        {"last_state": "state", "session": "session", "report": "report"},
    )
    assert captured["prompt_script"] == "base prompt"
    assert captured["sequence_prompt"] == "base prompt"
    assert captured["audio_continuity"] is True
    assert captured["show_preview"] is True


def test_v217_facade_passes_only_sparse_override_clips(monkeypatch):
    captured = {}

    def fake_run(_self, **kwargs):
        captured.update(kwargs)
        return "images", "audio", "state", "session", "report"

    monkeypatch.setattr(H3ContinuumSamplerV2, "run", fake_run)
    pack = H3ContinuumClipOverrides().build(
        PROMPT_FORMAT_OPTIONS[0],
        "[Clip 2]\nclose-up\n\n[Clip 5]\nfinish naturally",
    )[0]
    H3ContinuumSampler().run(
        model="model", clip="clip", video_vae="video_vae", audio_vae="audio_vae",
        sampler="sampler", sigmas="sigmas", sequence_prompt="base",
        prompt_mode=PROMPT_FORMAT_OPTIONS[0], chunks=5, chunk_seconds=5.0,
        width=1344, height=768, continuity="Balanced - 22 frames", base_seed=123,
        seam_correction="Auto", prompt_overrides=pack,
    )
    assert captured["clip_2_prompt"] == "close-up"
    assert captured["clip_5_prompt"] == "finish naturally"
    assert not any(f"clip_{index}_prompt" in captured for index in (1, 3, 4))


def test_v217_facade_ignores_sparse_override_outside_chunks(monkeypatch):
    captured = {}

    def fake_run(_self, **kwargs):
        captured.update(kwargs)
        return "images", "audio", "state", "session", "report"

    monkeypatch.setattr(H3ContinuumSamplerV2, "run", fake_run)
    pack = H3ContinuumClipOverrides().build(
        PROMPT_FORMAT_OPTIONS[0], "[Clip 6]\noutside"
    )[0]
    H3ContinuumSampler().run(
        model="model", clip="clip", video_vae="video_vae", audio_vae="audio_vae",
        sampler="sampler", sigmas="sigmas", sequence_prompt="base",
        prompt_mode=PROMPT_FORMAT_OPTIONS[0], chunks=5, chunk_seconds=5.0,
        width=1344, height=768, continuity="Balanced - 22 frames", base_seed=123,
        seam_correction="Auto", prompt_overrides=pack,
    )
    assert not any(key.startswith("clip_") and key.endswith("_prompt") for key in captured)


def test_v217_result_pack_expands_legacy_outputs():
    assert H3ContinuumResult().unpack(
        {"last_state": "state", "session": "session", "report": "report"}
    ) == ("state", "session", "report")


def test_v217_has_no_frontend_display_controller():
    assert not (ROOT / "web" / "h3_continuum_v2.js").exists()
    version_source = (ROOT / "version.py").read_text(encoding="utf-8")
    assert 'PACKAGE_VERSION = "3.4.0"' in version_source
