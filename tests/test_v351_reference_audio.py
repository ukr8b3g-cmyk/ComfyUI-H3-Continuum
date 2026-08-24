from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest
import torch

from ComfyUI_H3_Continuum_Join.reference_audio import (
    ReferenceAudioError,
    prepare_reference_audio_source,
)
from ComfyUI_H3_Continuum_Join.run_storage import automatic_project_key
from ComfyUI_H3_Continuum_Join.v3 import driving_nodes
from ComfyUI_H3_Continuum_Join.v3.driving_nodes import (
    H3ContinuumSamplerV34,
    H3ContinuumSamplerV35,
)
from ComfyUI_H3_Continuum_Join.v3.nodes import H3ContinuumSamplerProduction


ROOT = Path(__file__).resolve().parents[1]


def test_v35_appends_reference_audio_sockets_without_changing_v34_schema():
    v34_optional = H3ContinuumSamplerV34.INPUT_TYPES()["optional"]
    v35_optional = H3ContinuumSamplerV35.INPUT_TYPES()["optional"]

    assert "reference_audio_1" not in v34_optional
    assert "reference_audio_vae" not in v34_optional
    assert list(v35_optional)[:-2] == list(v34_optional)
    assert list(v35_optional)[-2:] == ["reference_audio_1", "reference_audio_vae"]
    assert v35_optional["reference_audio_1"][0] == "AUDIO"
    assert v35_optional["reference_audio_1"][1]["display_name"] == (
        "Reference Audio (Optional)"
    )
    assert v35_optional["reference_audio_vae"][0] == "VAE"
    assert v35_optional["reference_audio_vae"][1]["display_name"] == (
        "Reference Audio VAE (Optional)"
    )
    assert "Driving Audio" in v35_optional["reference_audio_1"][1]["tooltip"]


def test_v34_internal_reference_audio_parameters_are_appended_and_forwarded(
    monkeypatch,
):
    parameters = list(inspect.signature(H3ContinuumSamplerV34.run).parameters)
    assert parameters[-4:] == [
        "capture_refine_context",
        "reference_audio_1",
        "reference_audio_vae",
        "kwargs",
    ]

    captured = {}
    reference_audio = object()
    reference_audio_vae = object()

    monkeypatch.setattr(
        driving_nodes,
        "prepare_driving_audio_source",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "ComfyUI_H3_Continuum_Join.reference_video.prepare_reference_video_source",
        lambda *_args, **_kwargs: None,
    )

    def production_run(_self, **kwargs):
        captured.update(kwargs)
        return [], [], {}, "status"

    monkeypatch.setattr(H3ContinuumSamplerProduction, "run", production_run)
    outputs = H3ContinuumSamplerV34().run(
        reference_audio_1=reference_audio,
        reference_audio_vae=reference_audio_vae,
        chunks=1,
        chunk_seconds=5.0,
        width=640,
        height=640,
    )

    assert captured["reference_audio_1"] is reference_audio
    assert captured["reference_audio_vae"] is reference_audio_vae
    assert outputs[-1] is None


def test_v35_run_forwards_reference_audio_without_duplicate_preparation(monkeypatch):
    captured = {}
    reference_audio = object()
    reference_audio_vae = object()

    def v34_run(_self, *args, **kwargs):
        captured.update(kwargs)
        return [], [], {}, "status", None, {"groups": ()}

    monkeypatch.setattr(H3ContinuumSamplerV34, "run", v34_run)
    H3ContinuumSamplerV35().run(
        reference_audio_1=reference_audio,
        reference_audio_vae=reference_audio_vae,
    )

    assert captured["reference_audio_1"] is reference_audio
    assert captured["reference_audio_vae"] is reference_audio_vae
    assert captured["capture_refine_context"] is True
    assert captured["memory_attribution"] is True


def test_reference_audio_vae_is_ignored_without_audio_and_required_with_audio():
    vae = object()
    assert prepare_reference_audio_source(None, vae) is None
    audio = {
        "waveform": torch.zeros((1, 2, 32000), dtype=torch.float32),
        "sample_rate": 32000,
    }
    with pytest.raises(ReferenceAudioError, match="reference_audio_vae is required"):
        prepare_reference_audio_source(audio, None)


def test_unused_reference_audio_vae_does_not_change_automatic_project_key():
    base = {
        "1": {"class_type": "H3ContinuumSamplerV35", "inputs": {}},
        "2": {"class_type": "VAELoader", "inputs": {}},
    }
    vae_only = {
        **base,
        "1": {
            "class_type": "H3ContinuumSamplerV35",
            "inputs": {"reference_audio_vae": ["2", 0]},
        },
    }
    assert automatic_project_key(base, "1") == automatic_project_key(vae_only, "1")


def test_published_v35_template_keeps_existing_sampler_socket_routes():
    template = ROOT / "examples/workflows/MiniMax_H3_Continuum_V35.json"
    if not template.exists():
        pytest.skip("published workflow template is not installed in this runtime copy")
    workflow = json.loads(
        template.read_text(encoding="utf-8")
    )
    sampler = next(
        node for node in workflow["nodes"] if node["type"] == "H3ContinuumSamplerV35"
    )
    routes = {item["name"]: item.get("link") for item in sampler["inputs"]}
    assert routes["reference_image_1"] == 321
    assert routes["reference_image_2"] == 320
    assert routes["reference_image_3"] == 318
    assert routes["reference_video_1"] == 322
    assert routes["driving_audio"] == 294
    assert routes["audio_vae"] == 295
    assert "reference_audio_1" not in routes
    assert "reference_audio_vae" not in routes
