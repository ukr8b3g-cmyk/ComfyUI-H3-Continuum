from __future__ import annotations

import builtins
from types import SimpleNamespace

import pytest
import torch

from ComfyUI_H3_Continuum_Join import audio_compat, reference, reference_audio, driving_audio
from ComfyUI_H3_Continuum_Join.v3.ref_encode_cache import clear_ref_encode_cache
from . import test_v38_ref_encode_cache as cache_cases


def test_equal_rate_returns_original_without_importing_a_resampler(monkeypatch):
    monkeypatch.setattr(audio_compat.importlib, "import_module", lambda *args: pytest.fail("unneeded import"))
    waveform = torch.arange(200, dtype=torch.float32)
    assert audio_compat.resample_audio(waveform, 32000, 32000) is waveform


@pytest.mark.parametrize("rate", [16000, 22050, 32000, 44100, 48000, 96000])
@pytest.mark.parametrize("channels", [1, 2])
def test_resample_is_exactly_core(rate, channels, require_comfy_core):
    from comfy.audio import resample
    waveform = torch.sin(torch.arange(rate // 10, dtype=torch.float32) * 0.0123).view(1, 1, -1).repeat(1, channels, 1)
    frozen = waveform.clone()
    expected = resample(waveform, rate, 32000)
    actual = audio_compat.resample_audio(waveform, rate, 32000)
    assert actual.shape == expected.shape
    assert actual.dtype == expected.dtype
    assert torch.equal(actual, expected)
    assert torch.equal(waveform, frozen)


@pytest.mark.parametrize("absence", ["module", "api"])
def test_older_core_uses_the_legacy_adapter_only_if_api_absent(monkeypatch, absence):
    calls = []
    def legacy(waveform, source_rate, target_rate):
        calls.append((source_rate, target_rate))
        return waveform + 1
    def modules(name):
        if name == "comfy.audio":
            if absence == "module":
                raise ModuleNotFoundError("old Core", name="comfy.audio")
            return SimpleNamespace()
        assert name == "torchaudio"
        return SimpleNamespace(functional=SimpleNamespace(resample=legacy))
    monkeypatch.setattr(audio_compat.importlib, "import_module", modules)
    waveform = torch.zeros(1, 1, 20)
    assert torch.equal(audio_compat.resample_audio(waveform, 44100, 32000), waveform + 1)
    assert calls == [(44100, 32000)]


@pytest.mark.parametrize("failure", ["internal_dependency", "core_computation", "both_absent"])
def test_errors_never_switch_silently_to_a_different_resampler(monkeypatch, failure):
    calls = []
    def core(*args):
        raise ValueError("Core computation failed")
    def modules(name):
        calls.append(name)
        if name == "comfy.audio":
            if failure == "internal_dependency":
                raise ModuleNotFoundError("broken scipy", name="scipy.signal")
            if failure == "core_computation":
                return SimpleNamespace(resample=core)
            raise ModuleNotFoundError("old Core", name="comfy.audio")
        raise ModuleNotFoundError("no legacy module", name="torchaudio")
    monkeypatch.setattr(audio_compat.importlib, "import_module", modules)
    with pytest.raises((ModuleNotFoundError, ValueError, RuntimeError), match={
        "internal_dependency": "broken scipy", "core_computation": "Core computation failed",
        "both_absent": "requires comfy.audio.resample",
    }[failure]):
        audio_compat.resample_audio(torch.zeros(1, 1, 20), 44100, 32000)
    if failure != "both_absent":
        assert calls == ["comfy.audio"]


@pytest.mark.parametrize("rate", [32000, 44100, 48000])
def test_reference_bundle_and_driving_do_not_require_torchaudio(rate, monkeypatch, require_comfy_core):
    original_import = builtins.__import__
    def no_torchaudio(name, *args, **kwargs):
        if name == "torchaudio" or name.startswith("torchaudio."):
            raise ModuleNotFoundError("Torchaudio deliberately absent", name="torchaudio")
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", no_torchaudio)
    from comfy.audio import resample
    waveform = torch.sin(torch.arange(rate, dtype=torch.float32) / 10).view(1, 1, -1)
    source = {"waveform": waveform, "sample_rate": rate}
    vae = cache_cases.AudioVAE()
    reference_source = reference_audio.prepare_reference_audio_source(source, vae)
    bundle = reference_audio.H3ContinuumReferenceAudios().pack(source, None, None, vae)[0]
    assert bundle is not None
    assert reference_source.source_sample_rate == rate
    assert torch.equal(reference_source.waveform, resample(waveform, rate, 32000))
    driving = driving_audio.prepare_driving_audio_source(source, vae, target_frames=12, fps=24)
    effective = waveform[..., :round(rate / 2)]
    assert torch.equal(driving.source_audio["waveform"], effective)
    assert driving.source_audio["sample_rate"] == rate
    assert torch.equal(driving.resampled_waveform, resample(effective, rate, 32000))
    assert driving.contract["preprocess_version"] == 1
    same = reference_audio.prepare_reference_audio_source(source, vae)
    assert same.combined_hash == reference_source.combined_hash
    assert torch.equal(source["waveform"], waveform)


@pytest.mark.parametrize("kind", ["image", "audio"])
def test_direct_same_vae_weight_mutation_requires_clear_or_reload(kind):
    clear_ref_encode_cache()
    class WeightedImage(cache_cases.ImageVAE):
        def __init__(self):
            super().__init__()
            self.weight = torch.tensor(1.)
        def encode(self, image):
            return super().encode(image) + self.weight
    class WeightedAudio(cache_cases.AudioVAE):
        def __init__(self):
            super().__init__()
            self.weight = torch.tensor(1.)
        def encode(self, waveform):
            return super().encode(waveform) + self.weight
    vae = WeightedImage() if kind == "image" else WeightedAudio()
    source = cache_cases._image_assets("stability-r5-image") if kind == "image" else cache_cases._audio_source("stability-r5-audio")
    def encode(current):
        if kind == "image":
            return reference.encode_reference_latents_cached(current, source).latents[0]
        return reference_audio.encode_reference_audio_cached(current, source).audio_latent
    cold = encode(vae)
    same = encode(vae)
    assert vae.calls == 1 and torch.equal(cold, same)
    vae.weight.add_(1)
    stale = encode(vae)
    assert vae.calls == 1 and torch.equal(cold, stale)
    clear_ref_encode_cache()
    refreshed = encode(vae)
    assert vae.calls == 2 and torch.equal(refreshed, cold + 1)
    reloaded = type(vae)()
    reloaded.weight.fill_(3)
    assert torch.equal(encode(reloaded), cold + 2)
    assert reloaded.calls == 1
    clear_ref_encode_cache()
