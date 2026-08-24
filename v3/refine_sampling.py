"""V3.5 Second Pass sampling with the first-pass audio stream locked."""

from __future__ import annotations

from typing import Any, Callable

import torch

from ..state import extract_av_streams


class RefineSamplingRuntimeError(RuntimeError):
    """Raised when the ComfyUI sampling runtime cannot satisfy the refine contract."""


def _make_basic_guider(model: Any, conditioning: list):
    try:
        import comfy.samplers
    except Exception as exc:  # pragma: no cover
        raise RefineSamplingRuntimeError(f"ComfyUI sampler API unavailable: {exc}") from exc

    class _BasicGuider(comfy.samplers.CFGGuider):
        def set_positive(self, positive):
            self.inner_set_conds({"positive": positive})

    guider = _BasicGuider(model)
    guider.set_positive(conditioning)
    return guider


def _load_runtime_modules():
    try:
        import comfy.model_management
        import comfy.nested_tensor
        import comfy.sample
        import comfy.utils
        import latent_preview
    except Exception as exc:  # pragma: no cover
        raise RefineSamplingRuntimeError(
            f"ComfyUI refine sampling runtime unavailable: {exc}"
        ) from exc
    return (
        comfy.model_management,
        comfy.nested_tensor,
        comfy.sample,
        comfy.utils,
        latent_preview,
    )


def _prepare_refine_noise_and_mask(
    video: torch.Tensor,
    audio: torch.Tensor,
    *,
    seed: int,
    batch_inds: Any = None,
    prepare_noise_fn: Callable[[torch.Tensor, int, Any], torch.Tensor],
    nested_builder: Callable[[tuple[torch.Tensor, torch.Tensor]], Any],
) -> tuple[Any, Any]:
    """Build random video noise and a Core-expandable audio-lock mask."""

    if video.ndim != 5 or audio.ndim != 4:
        raise RefineSamplingRuntimeError(
            "refine latent must contain video [B,C,T,H,W] and audio [B,C,2,T]"
        )
    if int(video.shape[0]) != int(audio.shape[0]):
        raise RefineSamplingRuntimeError("refine video/audio batch sizes differ")

    video_noise = prepare_noise_fn(video, int(seed), batch_inds)
    if not torch.is_tensor(video_noise) or tuple(video_noise.shape) != tuple(video.shape):
        raise RefineSamplingRuntimeError("ComfyUI returned invalid video noise geometry")

    # Core prepare_noise creates CPU noise. Keep both streams on that same handoff
    # device so NestedTensor packing remains valid before Core moves it to the model.
    audio_noise = torch.zeros_like(audio, device="cpu")

    # These masks deliberately use the smallest shapes accepted by Core reshape_mask.
    # Core expands them to the full stream geometry on the sampling device.
    video_mask = torch.ones(
        (int(video.shape[0]), 1, 1, 1, 1),
        dtype=torch.float32,
        device="cpu",
    )
    audio_mask = torch.zeros(
        (int(audio.shape[0]), 1, 1, 1),
        dtype=torch.float32,
        device="cpu",
    )
    noise = nested_builder((video_noise, audio_noise))
    noise_mask = nested_builder((video_mask, audio_mask))
    return noise, noise_mask


def sample_refine_chunk(
    *,
    model: Any,
    conditioning: list,
    latent: dict[str, Any],
    sampler: Any,
    sigmas: torch.Tensor,
    seed: int,
    enable_preview: bool = True,
) -> dict[str, Any]:
    """Refine video while Core carries the first-pass audio as a locked AV stream."""

    if not isinstance(latent, dict) or "samples" not in latent:
        raise RefineSamplingRuntimeError("latent must be a ComfyUI LATENT dictionary")
    if not torch.is_tensor(sigmas) or sigmas.ndim != 1 or sigmas.numel() < 2:
        raise RefineSamplingRuntimeError("sigmas must contain at least two values")

    model_management, nested_tensor, comfy_sample, comfy_utils, preview = (
        _load_runtime_modules()
    )
    working = latent.copy()
    latent_image = comfy_sample.fix_empty_latent_channels(
        model,
        working["samples"],
        working.get("downscale_ratio_spacial"),
        working.get("downscale_ratio_temporal"),
    )
    working["samples"] = latent_image
    video, audio = extract_av_streams(working)
    noise, noise_mask = _prepare_refine_noise_and_mask(
        video,
        audio,
        seed=int(seed),
        batch_inds=working.get("batch_index"),
        prepare_noise_fn=comfy_sample.prepare_noise,
        nested_builder=nested_tensor.NestedTensor,
    )
    guider = _make_basic_guider(model, conditioning)

    x0_output: dict[str, Any] = {}
    callback = None
    if enable_preview:
        callback = preview.prepare_callback(
            model,
            int(sigmas.shape[-1]) - 1,
            x0_output,
        )
    disable_pbar = not comfy_utils.PROGRESS_BAR_ENABLED
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
    samples = samples.to(model_management.intermediate_device())
    output = working.copy()
    output.pop("downscale_ratio_spacial", None)
    output.pop("downscale_ratio_temporal", None)
    output["samples"] = samples
    extract_av_streams(output)
    return output
