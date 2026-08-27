from __future__ import annotations

import json
from pathlib import Path

from ComfyUI_H3_Continuum_Join import nodes as root_nodes
from ComfyUI_H3_Continuum_Join.v2.sequence import (
    MASKED_AV_PREFIX_22_V1,
    MASKED_VIDEO_PREFIX_V1,
    REFERENCE_CONTEXT_V1,
)
from ComfyUI_H3_Continuum_Join.v3.driving_nodes import (
    CONTINUATION_BACKEND_COMPATIBILITY,
    CONTINUATION_BACKEND_OPTIONS,
    CONTINUATION_BACKEND_STANDARD,
    H3ContinuumSamplerV35,
    H3ContinuumSamplerV36,
    NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS,
)
from ComfyUI_H3_Continuum_Join.v3.nodes import H3ContinuumSamplerProduction


ROOT = Path(__file__).resolve().parents[1]


def test_v36_is_registered_without_replacing_v35():
    assert NODE_CLASS_MAPPINGS["H3ContinuumSamplerV36"] is H3ContinuumSamplerV36
    assert NODE_DISPLAY_NAME_MAPPINGS["H3ContinuumSamplerV36"] == (
        "H3 Continuum Sampler V3.6"
    )
    assert root_nodes.NODE_CLASS_MAPPINGS["H3ContinuumSamplerV36"] is (
        H3ContinuumSamplerV36
    )
    assert root_nodes.NODE_CLASS_MAPPINGS["H3ContinuumSamplerV35"] is (
        H3ContinuumSamplerV35
    )
    assert H3ContinuumSamplerV36.RETURN_TYPES == H3ContinuumSamplerV35.RETURN_TYPES
    assert H3ContinuumSamplerV36.RETURN_NAMES == H3ContinuumSamplerV35.RETURN_NAMES


def test_v36_schema_exposes_only_friendly_backend_names_at_the_end():
    required = H3ContinuumSamplerV36.INPUT_TYPES()["required"]
    assert tuple(required)[-1] == "continuation_backend"
    choices, metadata = required["continuation_backend"]
    assert choices == CONTINUATION_BACKEND_OPTIONS
    assert choices == (
        CONTINUATION_BACKEND_STANDARD,
        CONTINUATION_BACKEND_COMPATIBILITY,
    )
    assert metadata["default"] == CONTINUATION_BACKEND_STANDARD
    rendered = repr(required["continuation_backend"])
    assert "masked_av_prefix" not in rendered
    assert "reference_context_v1" not in rendered
    assert "continuation_transport" not in required
    assert "continuation_backend" not in H3ContinuumSamplerV35.INPUT_TYPES()["required"]


def test_v36_maps_public_backend_and_audio_policy_to_internal_transport(monkeypatch):
    captured = []

    def fake_production_run(_self, **kwargs):
        captured.append(kwargs.get("continuation_transport", REFERENCE_CONTEXT_V1))
        return "video", "audio", {"plan": True}, "status", "context"

    monkeypatch.setattr(H3ContinuumSamplerProduction, "run", fake_production_run)
    common = {"chunks": 1, "chunk_seconds": 5.0, "width": 96, "height": 64}

    H3ContinuumSamplerV35().run(**common, audio_continuity=True)
    H3ContinuumSamplerV36().run(
        **common,
        audio_continuity=True,
        continuation_backend=CONTINUATION_BACKEND_STANDARD,
    )
    H3ContinuumSamplerV36().run(
        **common,
        audio_continuity=False,
        continuation_backend=CONTINUATION_BACKEND_STANDARD,
    )
    H3ContinuumSamplerV36().run(
        **common,
        audio_continuity=True,
        continuation_backend=CONTINUATION_BACKEND_COMPATIBILITY,
    )

    assert captured == [
        REFERENCE_CONTEXT_V1,
        MASKED_AV_PREFIX_22_V1,
        MASKED_VIDEO_PREFIX_V1,
        REFERENCE_CONTEXT_V1,
    ]


def test_v36_template_uses_standard_backend_and_v35_template_is_unchanged():
    v36 = json.loads(
        (ROOT / "examples/workflows/MiniMax_H3_Continuum_V36.json").read_text(
            encoding="utf-8"
        )
    )
    v35 = json.loads(
        (ROOT / "examples/workflows/MiniMax_H3_Continuum_V35.json").read_text(
            encoding="utf-8"
        )
    )
    v36_sampler = next(node for node in v36["nodes"] if node["id"] == 305)
    v35_sampler = next(node for node in v35["nodes"] if node["id"] == 305)

    assert v36_sampler["type"] == "H3ContinuumSamplerV36"
    assert v36_sampler["properties"]["Node name for S&R"] == (
        "H3ContinuumSamplerV36"
    )
    assert v36_sampler["widgets_values"][-1] == CONTINUATION_BACKEND_STANDARD
    assert v36_sampler["widgets_values_named"]["continuation_backend"] == (
        CONTINUATION_BACKEND_STANDARD
    )
    assert v35_sampler["type"] == "H3ContinuumSamplerV35"
    assert "continuation_backend" not in v35_sampler["widgets_values_named"]
