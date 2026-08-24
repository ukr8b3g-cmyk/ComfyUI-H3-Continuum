from __future__ import annotations

from types import SimpleNamespace

import torch

from ComfyUI_H3_Continuum_Join.v3 import refine_sampling


class _Nested:
    is_nested = True

    def __init__(self, tensors):
        self.tensors = list(tensors)

    def unbind(self):
        return self.tensors

    def to(self, *_args, **_kwargs):
        return self


def test_refine_noise_is_random_for_video_zero_for_audio_with_minimal_masks():
    video = torch.zeros((1, 24, 3, 4, 5), dtype=torch.float16)
    audio = torch.ones((1, 32, 2, 12), dtype=torch.float16)
    calls = []

    def prepare_noise(samples, seed, batch_inds):
        calls.append((samples, seed, batch_inds))
        return torch.full_like(samples, 0.75, device="cpu")

    noise, mask = refine_sampling._prepare_refine_noise_and_mask(
        video,
        audio,
        seed=123,
        batch_inds=[0],
        prepare_noise_fn=prepare_noise,
        nested_builder=_Nested,
    )

    video_noise, audio_noise = noise.unbind()
    video_mask, audio_mask = mask.unbind()
    assert calls == [(video, 123, [0])]
    assert torch.equal(video_noise, torch.full_like(video_noise, 0.75))
    assert torch.count_nonzero(audio_noise) == 0
    assert audio_noise.dtype == audio.dtype
    assert tuple(video_mask.shape) == (1, 1, 1, 1, 1)
    assert tuple(audio_mask.shape) == (1, 1, 1, 1)
    assert torch.all(video_mask == 1)
    assert torch.all(audio_mask == 0)


def test_refine_sampler_passes_original_av_latent_and_workflow_sigmas_to_core(monkeypatch):
    video = torch.randn((1, 24, 3, 4, 4))
    audio = torch.randn((1, 32, 2, 12))
    latent_samples = _Nested((video, audio))
    latent = {"samples": latent_samples}
    sigmas = torch.tensor([0.35, 0.2, 0.0])
    captured = {}

    class _Guider:
        def sample(self, noise, latent_image, sampler, supplied_sigmas, **kwargs):
            captured.update(
                noise=noise,
                latent_image=latent_image,
                sampler=sampler,
                sigmas=supplied_sigmas,
                **kwargs,
            )
            return latent_image

    def prepare_noise(samples, seed, batch_inds):
        captured["prepare_noise"] = (samples, seed, batch_inds)
        return torch.full_like(samples, 0.5, device="cpu")

    fake_sample = SimpleNamespace(
        fix_empty_latent_channels=lambda _model, samples, _spatial, _temporal: samples,
        prepare_noise=prepare_noise,
    )
    fake_runtime = (
        SimpleNamespace(intermediate_device=lambda: torch.device("cpu")),
        SimpleNamespace(NestedTensor=_Nested),
        fake_sample,
        SimpleNamespace(PROGRESS_BAR_ENABLED=False),
        SimpleNamespace(prepare_callback=lambda *_args: None),
    )
    monkeypatch.setattr(refine_sampling, "_load_runtime_modules", lambda: fake_runtime)
    monkeypatch.setattr(refine_sampling, "_make_basic_guider", lambda *_args: _Guider())

    sampler = object()
    output = refine_sampling.sample_refine_chunk(
        model=object(),
        conditioning=["conditioning"],
        latent=latent,
        sampler=sampler,
        sigmas=sigmas,
        seed=987,
        enable_preview=False,
    )

    assert captured["prepare_noise"] == (video, 987, None)
    assert captured["latent_image"] is latent_samples
    assert captured["latent_image"].unbind()[1] is audio
    assert captured["sigmas"] is sigmas
    assert captured["sampler"] is sampler
    video_noise, audio_noise = captured["noise"].unbind()
    video_mask, audio_mask = captured["denoise_mask"].unbind()
    assert torch.equal(video_noise, torch.full_like(video_noise, 0.5))
    assert torch.count_nonzero(audio_noise) == 0
    assert torch.all(video_mask == 1)
    assert torch.all(audio_mask == 0)
    assert output["samples"] is latent_samples
