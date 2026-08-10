"""ComfyUI-native chunk sampling helpers."""

from __future__ import annotations

from typing import Any

import torch

from ..state import extract_av_streams


class SamplingRuntimeError(RuntimeError):
    pass


def _make_basic_guider(model: Any, conditioning: list):
    try:
        import comfy.samplers
    except Exception as exc:  # pragma: no cover
        raise SamplingRuntimeError(f"ComfyUI sampler API unavailable: {exc}") from exc

    class _BasicGuider(comfy.samplers.CFGGuider):
        def set_positive(self, positive):
            self.inner_set_conds({"positive": positive})

    guider = _BasicGuider(model)
    guider.set_positive(conditioning)
    return guider


def _prepare_noise(latent: dict[str, Any], seed: int):
    try:
        import comfy.sample
    except Exception as exc:  # pragma: no cover
        raise SamplingRuntimeError(f"ComfyUI noise API unavailable: {exc}") from exc
    batch_inds = latent.get("batch_index")
    return comfy.sample.prepare_noise(latent["samples"], int(seed), batch_inds)


def sample_chunk(
    *,
    model: Any,
    conditioning: list,
    latent: dict[str, Any],
    sampler: Any,
    sigmas: torch.Tensor,
    seed: int,
    enable_preview: bool = True,
) -> dict[str, Any]:
    """Run one H3 chunk using the same path as SamplerCustomAdvanced."""

    try:
        import comfy.model_management
        import comfy.sample
        import comfy.utils
        import latent_preview
    except Exception as exc:  # pragma: no cover
        raise SamplingRuntimeError(f"ComfyUI sampling runtime unavailable: {exc}") from exc

    if not isinstance(latent, dict) or "samples" not in latent:
        raise SamplingRuntimeError("latent must be a ComfyUI LATENT dictionary")
    if not torch.is_tensor(sigmas) or sigmas.ndim != 1 or sigmas.numel() < 2:
        raise SamplingRuntimeError("sigmas must contain at least two values")

    working = latent.copy()
    latent_image = working["samples"]
    latent_image = comfy.sample.fix_empty_latent_channels(
        model,
        latent_image,
        working.get("downscale_ratio_spacial"),
        working.get("downscale_ratio_temporal"),
    )
    working["samples"] = latent_image
    noise_mask = working.get("noise_mask")
    guider = _make_basic_guider(model, conditioning)
    noise = _prepare_noise(working, seed)

    x0_output: dict[str, Any] = {}
    callback = None
    if enable_preview:
        callback = latent_preview.prepare_callback(model, int(sigmas.shape[-1]) - 1, x0_output)
    disable_pbar = not comfy.utils.PROGRESS_BAR_ENABLED
    samples = guider.sample(
        noise,
        latent_image,
        sampler,
        sigmas,
        denoise_mask=noise_mask,
        callback=callback,
        disable_pbar=disable_pbar,
        seed=int(seed),
    )
    samples = samples.to(comfy.model_management.intermediate_device())
    output = working.copy()
    output.pop("downscale_ratio_spacial", None)
    output.pop("downscale_ratio_temporal", None)
    output["samples"] = samples
    # Validate the nested AV shape immediately so a bad sampler output cannot be
    # committed into a session and fail much later during continuation.
    extract_av_streams(output)
    return output


def latent_to_cpu(latent: dict[str, Any]) -> tuple[torch.Tensor, torch.Tensor]:
    video, audio = extract_av_streams(latent)
    video_cpu = video.detach().to("cpu").contiguous().clone()
    audio_cpu = audio.detach().to("cpu").contiguous().clone()
    if not bool(torch.isfinite(video_cpu.float()).all().item()):
        raise SamplingRuntimeError("sampled video latent contains NaN or Inf")
    if not bool(torch.isfinite(audio_cpu.float()).all().item()):
        raise SamplingRuntimeError("sampled audio latent contains NaN or Inf")
    return video_cpu, audio_cpu


def latent_from_cpu(video: torch.Tensor, audio: torch.Tensor) -> dict[str, Any]:
    try:
        import comfy.nested_tensor
    except Exception as exc:  # pragma: no cover
        raise SamplingRuntimeError(f"ComfyUI NestedTensor API unavailable: {exc}") from exc
    return {
        "samples": comfy.nested_tensor.NestedTensor(
            (video.contiguous(), audio.contiguous())
        )
    }
