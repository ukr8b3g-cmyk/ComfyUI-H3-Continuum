from __future__ import annotations

from types import SimpleNamespace

import pytest
import torch

from ComfyUI_H3_Continuum_Join import nodes as root_nodes
from ComfyUI_H3_Continuum_Join.graph_contract import build_upstream_graph_contract
from ComfyUI_H3_Continuum_Join.reference import ReferenceAssets, encode_reference_prompt
from ComfyUI_H3_Continuum_Join.reference_audio import (
    H3ContinuumReferenceAudios,
    REFERENCE_AUDIOS_TYPE,
    ReferenceAudioError,
    combine_reference_audio_identity,
    encode_reference_audio_input,
    prepare_reference_audio_bundle,
    prepare_reference_audio_source,
    resolve_reference_audio_input,
    validate_reference_audio_prompts,
)
from ComfyUI_H3_Continuum_Join.v2.h3_builder import encode_prompt_conditioning
from ComfyUI_H3_Continuum_Join.v3.driving_nodes import (
    H3ContinuumSamplerV37,
    H3ContinuumSamplerV38,
)


def _audio(value: float) -> dict:
    return {
        "waveform": torch.full((1, 2, 320), value, dtype=torch.float32),
        "sample_rate": 32000,
    }


class _AudioVAE:
    audio_sample_rate = 32000

    def __init__(self):
        self.inputs = []

    def encode(self, waveform):
        self.inputs.append(waveform.clone())
        value = float(waveform.mean().item())
        return torch.full((1, 32, 2, len(self.inputs)), value, dtype=torch.float32)


class _Clip:
    def __init__(self):
        self.options = None

    def tokenize(self, prompt, **kwargs):
        self.options = kwargs
        return prompt

    def encode_from_tokens_scheduled(self, tokens):
        return [[torch.zeros((1, 1, 2)), {}]]


def test_public_helper_and_v38_socket_are_the_only_surface_additions():
    helper_id = "H3ContinuumReferenceAudios"
    helper_schema = H3ContinuumReferenceAudios.INPUT_TYPES()
    v37 = H3ContinuumSamplerV37.INPUT_TYPES()
    v38 = H3ContinuumSamplerV38.INPUT_TYPES()

    assert root_nodes.NODE_CLASS_MAPPINGS[helper_id] is H3ContinuumReferenceAudios
    assert root_nodes.NODE_DISPLAY_NAME_MAPPINGS[helper_id] == (
        "H3 Continuum Reference Audios"
    )
    assert tuple(helper_schema) == ("optional",)
    assert tuple(helper_schema["optional"]) == (
        "reference_audio_1",
        "reference_audio_2",
        "reference_audio_3",
        "reference_audio_vae",
    )
    assert H3ContinuumReferenceAudios.RETURN_TYPES == (REFERENCE_AUDIOS_TYPE,)
    assert "audio_references" not in v37["optional"]
    assert list(v38["optional"])[:-3] == list(v37["optional"])
    assert list(v38["optional"])[-3:] == [
        "audio_references",
        "image_references",
        "video_reference_mode",
    ]
    assert v38["optional"]["audio_references"][0] == REFERENCE_AUDIOS_TYPE
    mode_schema = v38["optional"]["video_reference_mode"]
    assert mode_schema[0] == ("Follow Timeline", "Repeat Reference")
    assert mode_schema[1]["default"] == "Repeat Reference"


def test_helper_preserves_order_and_requires_contiguous_core_numbering():
    vae = _AudioVAE()
    bundle = H3ContinuumReferenceAudios().pack(
        _audio(0.1), _audio(0.2), _audio(0.3), vae
    )[0]

    assert bundle.count == 3
    assert bundle.reference_audio_vae is vae
    assert [item.source_sha256 for item in bundle.sources] == [
        item["reference_audio"]["source_sha256"]
        for item in bundle.contract["items"]
    ]
    assert [item["audio_index"] for item in bundle.contract["items"]] == [1, 2, 3]

    with pytest.raises(ReferenceAudioError, match="without gaps"):
        prepare_reference_audio_bundle(_audio(0.1), None, _audio(0.3), vae)
    assert prepare_reference_audio_bundle(None, None, None, vae) is None


def test_bundle_order_changes_run_identity_and_legacy_identity_stays_v1():
    vae = _AudioVAE()
    first = prepare_reference_audio_bundle(_audio(0.1), _audio(0.2), None, vae)
    swapped = prepare_reference_audio_bundle(_audio(0.2), _audio(0.1), None, vae)
    assert first is not None and swapped is not None

    first_identity = combine_reference_audio_identity("visual", first)
    swapped_identity = combine_reference_audio_identity("visual", swapped)
    assert first_identity != swapped_identity
    assert first.contract != swapped.contract

    legacy = SimpleNamespace(combined_hash="audio")
    assert combine_reference_audio_identity("visual", legacy) == (
        "59fa60ba2a9a19525222c867aa2c2b8350dbf6af1e24ad34056317bcd40c81cb"
    )


def test_legacy_and_bundle_inputs_cannot_be_mixed():
    vae = _AudioVAE()
    bundle = prepare_reference_audio_bundle(_audio(0.1), _audio(0.2), None, vae)
    with pytest.raises(ReferenceAudioError, match="not both"):
        resolve_reference_audio_input(_audio(0.1), vae, bundle)

    resolved, resolved_vae = resolve_reference_audio_input(None, object(), bundle)
    assert resolved is bundle
    assert resolved_vae is vae


def test_each_reference_is_encoded_independently_in_order():
    vae = _AudioVAE()
    bundle = prepare_reference_audio_bundle(_audio(0.1), _audio(0.2), _audio(0.3), vae)
    assert bundle is not None

    assets = encode_reference_audio_input(vae, bundle, cache_enabled=False)

    assert isinstance(assets, tuple)
    assert len(assets) == 3
    assert len(vae.inputs) == 3
    assert [round(float(item.audio_latent.mean().item()), 3) for item in assets] == [
        0.1,
        0.2,
        0.3,
    ]


def test_three_assets_follow_core_tokenizer_and_packed_ref_order():
    latents = tuple(
        SimpleNamespace(audio_latent=torch.full((1, 32, 2, index), float(index)))
        for index in (1, 2, 3)
    )
    clip = _Clip()

    conditioning = encode_prompt_conditioning(
        clip,
        "<Audio 1> woman; <Audio 2> man; <Audio 3> ambience.",
        first_image=None,
        last_image=None,
        reference_audio_assets=latents,
    )

    assert [item["type"] for item in clip.options["minimax_ref_items"]] == [
        "audio",
        "audio",
        "audio",
    ]
    refs = conditioning[0][1]["minimax_refs"]
    assert [item["kind"] for item in refs] == ["audio", "audio", "audio"]
    assert [item["ref_audio_t"] for item in refs] == [1, 2, 3]
    assert [float(item["audio_latent"].mean().item()) for item in refs] == [1.0, 2.0, 3.0]


def test_reference_images_and_three_audio_assets_share_ordered_core_payloads():
    image = torch.full((1, 32, 32, 3), 0.5, dtype=torch.float32)
    image_assets = ReferenceAssets(
        images=(image,),
        latents=(torch.zeros((1, 24, 2, 2, 2)),),
        image_hashes=("reference-image",),
        combined_hash="reference-images",
        size_mode="Match Output",
    )
    audio_assets = tuple(
        SimpleNamespace(audio_latent=torch.full((1, 32, 2, index), float(index)))
        for index in (1, 2, 3)
    )
    clip = _Clip()

    conditioning = encode_reference_prompt(
        clip,
        "<Picture 1> with <Audio 1>, <Audio 2>, and <Audio 3>.",
        image_assets,
        reference_audio_assets=audio_assets,
    )

    assert [item["type"] for item in clip.options["minimax_ref_items"]] == [
        "image",
        "audio",
        "audio",
        "audio",
    ]
    refs = conditioning[0][1]["minimax_refs"]
    assert [item["kind"] for item in refs] == ["image", "audio", "audio", "audio"]
    assert [item["ref_audio_t"] for item in refs[1:]] == [1, 2, 3]


def test_one_item_helper_conditioning_matches_legacy_single_item():
    latent = torch.arange(64, dtype=torch.float32).reshape(1, 32, 2, 1)
    asset = SimpleNamespace(audio_latent=latent)
    legacy_clip = _Clip()
    helper_clip = _Clip()

    legacy = encode_prompt_conditioning(
        legacy_clip,
        "Use <Audio 1>.",
        first_image=None,
        last_image=None,
        reference_audio_assets=asset,
    )
    helper = encode_prompt_conditioning(
        helper_clip,
        "Use <Audio 1>.",
        first_image=None,
        last_image=None,
        reference_audio_assets=(asset,),
    )

    assert legacy_clip.options == helper_clip.options
    assert legacy[0][1].keys() == helper[0][1].keys()
    assert legacy[0][1]["minimax_refs"][0]["ref_audio_t"] == 1
    assert torch.equal(
        legacy[0][1]["minimax_refs"][0]["audio_latent"],
        helper[0][1]["minimax_refs"][0]["audio_latent"],
    )


def test_prompt_warnings_follow_connected_audio_count():
    vae = _AudioVAE()
    bundle = prepare_reference_audio_bundle(_audio(0.1), _audio(0.2), None, vae)
    assert bundle is not None

    warning = validate_reference_audio_prompts(
        ["<Audio 1> speaks while <Audio 3> answers."], bundle
    )
    assert "unavailable <Audio 3>" in warning
    assert "no <Audio 2> tag" in warning
    assert "no <Audio 1> tag" not in warning


def test_run_storage_graph_contract_fingerprints_helper_vae_and_sources():
    prompt = {
        "sampler": {
            "class_type": "H3ContinuumSamplerV38",
            "inputs": {
                "model": ["model", 0],
                "clip": ["clip", 0],
                "sampler": ["ksampler", 0],
                "audio_references": ["refs", 0],
            },
        },
        "model": {"class_type": "UNETLoader", "inputs": {"name": "model.safetensors"}},
        "clip": {"class_type": "CLIPLoader", "inputs": {"name": "text.safetensors"}},
        "ksampler": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "refs": {
            "class_type": "H3ContinuumReferenceAudios",
            "inputs": {
                "reference_audio_1": ["audio1", 0],
                "reference_audio_2": ["audio2", 0],
                "reference_audio_vae": ["vae", 0],
            },
        },
        "audio1": {"class_type": "LoadAudio", "inputs": {"audio": "one.wav"}},
        "audio2": {"class_type": "LoadAudio", "inputs": {"audio": "two.wav"}},
        "vae": {"class_type": "VAELoader", "inputs": {"vae_name": "audio.safetensors"}},
    }

    contract, safe, reasons = build_upstream_graph_contract(
        prompt,
        "sampler",
        require_video_vae=False,
        require_reference_audio_vae=True,
    )

    assert safe, reasons
    route = contract["routes"]["reference_audio_vae"]
    assert route["node"]["class_type"] == "H3ContinuumReferenceAudios"
    assert route["node"]["inputs"]["reference_audio_vae"]["node"]["class_type"] == (
        "VAELoader"
    )
    assert route["node"]["inputs"]["reference_audio_2"]["node"]["inputs"]["audio"] == (
        "two.wav"
    )


def test_v38_facade_forwards_bundle_socket_without_touching_v37(monkeypatch):
    captured = {}

    def fake_v37_run(_self, **kwargs):
        captured.update(kwargs)
        return "ok"

    monkeypatch.setattr(H3ContinuumSamplerV37, "run", fake_v37_run)
    marker = object()
    result = H3ContinuumSamplerV38().run(audio_references=marker)

    assert result == "ok"
    assert captured["audio_references"] is marker


def test_legacy_source_preparation_remains_available_unchanged():
    vae = _AudioVAE()
    source = prepare_reference_audio_source(_audio(0.25), vae)
    assert source is not None
    assert source.contract["reference_audio_contract_version"] == 1
    assert "reference_audio_bundle_contract_version" not in source.contract
