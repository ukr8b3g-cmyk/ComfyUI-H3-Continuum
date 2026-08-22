"""Standalone ComfyUI node for Core-vs-Continuum GPU diagnostics."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import gc
import importlib
import json
from pathlib import Path, PurePosixPath
import random
import sys
import traceback
from types import SimpleNamespace
from typing import Any

import numpy as np
import torch

from .capture import (
    DiagnosticCapture,
    STAGE_ORDER,
    compare_stage,
    compare_tensors,
    format_comparison,
    recombine_terminal_streams,
)


def _resolve_loaded_module(path: Path):
    target = path.resolve()
    for module in tuple(sys.modules.values()):
        source = getattr(module, "__file__", None)
        if source and Path(source).resolve() == target:
            return module
    return None


def _resolve_continuum_modules() -> SimpleNamespace:
    import nodes as comfy_nodes

    sampler_class = comfy_nodes.NODE_CLASS_MAPPINGS.get("H3ContinuumSamplerV34")
    if sampler_class is None:
        raise RuntimeError("H3ContinuumSamplerV34 is not loaded; install and enable H3 Continuum V3.4 first")
    owner = sys.modules.get(sampler_class.__module__)
    source = getattr(owner, "__file__", None)
    if source is None:
        raise RuntimeError("cannot resolve the active H3 Continuum package")
    root = Path(source).resolve().parent.parent
    module_name = sampler_class.__module__
    base_name = module_name.split(".v3.", 1)[0] if ".v3." in module_name else module_name.rsplit(".", 2)[0]

    def load(relative: str, suffix: str):
        target = root / relative
        loaded = _resolve_loaded_module(target)
        if loaded is not None:
            return loaded
        return importlib.import_module(f"{base_name}.{suffix}")

    return SimpleNamespace(
        root=root,
        constants=load("constants.py", "constants"),
        state=load("state.py", "state"),
        sequence=load("v2/sequence.py", "v2.sequence"),
        sampling=load("v2/sampling.py", "v2.sampling"),
        prompts=load("v2/prompts.py", "v2.prompts"),
        decoder=load("v2/decoder.py", "v2.decoder"),
    )


def _reset_rng(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed & 0xFFFFFFFF)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _release_cuda() -> None:
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def _safe_output_directory(subdir: str) -> Path:
    import folder_paths

    clean = str(subdir).replace("\\", "/").strip("/") or "h3_continuum/diagnostics"
    parts = PurePosixPath(clean).parts
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError("output_subdir must stay below the ComfyUI output directory")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return Path(folder_paths.get_output_directory()).joinpath(*parts, stamp)


def _capture_av_value(capture: DiagnosticCapture, stage: str, prefix: str, value: Any) -> None:
    candidate = value.get("samples") if isinstance(value, dict) and "samples" in value else value
    if hasattr(candidate, "unbind") and candidate.__class__.__name__ == "NestedTensor":
        parts = list(candidate.unbind())
        capture.add_value(stage, f"{prefix}.components", len(parts))
        for index, part in enumerate(parts):
            label = ("video", "audio")[index] if index < 2 else f"component_{index}"
            capture.add_tensor(stage, f"{prefix}.{label}", part)
        return
    if torch.is_tensor(candidate) and getattr(candidate, "is_nested", False):
        parts = list(candidate.unbind())
        capture.add_value(stage, f"{prefix}.components", len(parts))
        for index, part in enumerate(parts):
            label = ("video", "audio")[index] if index < 2 else f"component_{index}"
            capture.add_tensor(stage, f"{prefix}.{label}", part)
        return
    capture.capture_value(stage, prefix, candidate)


def _capture_pre_sampler(
    capture: DiagnosticCapture,
    modules: SimpleNamespace,
    *,
    conditioning: Any,
    latent: dict[str, Any],
    sigmas: torch.Tensor,
    seed: int,
) -> None:
    stage = "A_pre_sampler"
    capture.add_value(stage, "seed", int(seed))
    capture.add_value(stage, "presentation_order", ["First Frame", "Last Frame"])
    capture.add_tensor(stage, "sigmas", sigmas)
    video, audio = modules.state.extract_av_streams(latent)
    capture.add_tensor(stage, "target.video", video)
    capture.add_tensor(stage, "target.audio", audio)
    capture.add_value(stage, "target.video_shape", list(video.shape))
    capture.add_value(stage, "target.audio_shape", list(audio.shape))

    if not conditioning:
        capture.add_value(stage, "conditioning.empty", True)
        return
    first = conditioning[0]
    cond_tensor = first[0]
    metadata = first[1] if len(first) > 1 and isinstance(first[1], dict) else {}
    capture.capture_value(stage, "conditioning.positive", cond_tensor)
    capture.add_value(stage, "conditioning.metadata_keys", sorted(str(key) for key in metadata))
    capture.add_value(stage, "physical_frames", int(metadata.get("minimax_frame_count", 243)))
    for key in ("minimax_token_tags", "minimax_keyframes", "minimax_refs", "minimax_frame_count"):
        if key in metadata:
            capture.capture_value(stage, f"conditioning.{key}", metadata[key])


def _capture_physical_sample(
    capture: DiagnosticCapture,
    modules: SimpleNamespace,
    result: dict[str, Any],
) -> tuple[torch.Tensor, torch.Tensor]:
    video, audio = modules.state.extract_av_streams(result)
    video_cpu = video.detach().to("cpu").contiguous()
    audio_cpu = audio.detach().to("cpu").contiguous()
    capture.add_tensor("C_physical_sample", "video", video_cpu)
    capture.add_tensor("C_physical_sample", "audio", audio_cpu)
    capture.runtime["physical_streams"] = (video_cpu, audio_cpu)
    return video_cpu, audio_cpu


@contextmanager
def _runtime_capture(capture: DiagnosticCapture):
    import comfy.model_base
    import comfy.sample

    original_noise = comfy.sample.prepare_noise
    original_apply = comfy.model_base.BaseModel._apply_model
    noise_seen = False
    model_seen = False

    def prepare_noise(*args, **kwargs):
        nonlocal noise_seen
        result = original_noise(*args, **kwargs)
        if not noise_seen:
            noise_seen = True
            _capture_av_value(capture, "A_pre_sampler", "actual_noise", result)
        return result

    def apply_model(
        self,
        x,
        t,
        c_concat=None,
        c_crossattn=None,
        control=None,
        transformer_options={},
        **kwargs,
    ):
        nonlocal model_seen
        if not model_seen and self.__class__.__name__ == "MiniMaxH3":
            model_seen = True
            capture.capture_value("B_first_model_call", "input_x", x)
            capture.capture_value("B_first_model_call", "timestep", t)
            capture.capture_value(
                "B_first_model_call",
                "transformer_options",
                transformer_options,
                persist_tensors=False,
            )
            capture.capture_value("B_first_model_call", "minimax_payload", kwargs.get("minimax_payload"))
            capture.capture_value("B_first_model_call", "latent_shapes", kwargs.get("latent_shapes"))
        return original_apply(
            self,
            x,
            t,
            c_concat,
            c_crossattn,
            control,
            transformer_options,
            **kwargs,
        )

    comfy.sample.prepare_noise = prepare_noise
    comfy.model_base.BaseModel._apply_model = apply_model
    try:
        yield
    finally:
        comfy.sample.prepare_noise = original_noise
        comfy.model_base.BaseModel._apply_model = original_apply
        restored = (
            comfy.sample.prepare_noise is original_noise
            and comfy.model_base.BaseModel._apply_model is original_apply
        )
        capture.add_value("B_first_model_call", "patches_restored", restored)
        capture.add_value("A_pre_sampler", "noise_captured", noise_seen)
        capture.add_value("B_first_model_call", "model_call_captured", model_seen)


def _run_core(
    capture: DiagnosticCapture,
    modules: SimpleNamespace,
    *,
    model: Any,
    clip: Any,
    video_vae: Any,
    sampler: Any,
    sigmas: torch.Tensor,
    first_frame: torch.Tensor,
    last_frame: torch.Tensor,
    prompt: str,
    width: int,
    height: int,
    seed: int,
) -> None:
    from comfy_extras.nodes_minimax_h3 import MiniMaxH3ImageToVideo

    core_model = model.clone()
    output = MiniMaxH3ImageToVideo().execute(
        clip,
        video_vae,
        prompt,
        int(width),
        int(height),
        243,
        first_frame=first_frame,
        last_frame=last_frame,
    )
    conditioning, latent = output[0], output[1]
    _capture_pre_sampler(
        capture,
        modules,
        conditioning=conditioning,
        latent=latent,
        sigmas=sigmas,
        seed=seed,
    )
    with _runtime_capture(capture):
        result = modules.sampling.sample_chunk(
            model=core_model,
            conditioning=conditioning,
            latent=latent,
            sampler=sampler,
            sigmas=sigmas,
            seed=int(seed),
            enable_preview=False,
        )
    _capture_physical_sample(capture, modules, result)
    capture.add_value("C_physical_sample", "sampling_passes", 1)
    capture.add_value("C_physical_sample", "physical_seed", int(seed))
    del result, latent, conditioning, core_model


def _capture_terminal_split(
    capture: DiagnosticCapture,
    video: torch.Tensor,
    audio: torch.Tensor,
    contract: dict[str, Any],
    result: Any,
) -> None:
    (video_1, audio_1), (video_2, audio_2) = result
    video_ranges = contract["video_slices"]
    audio_ranges = contract["audio_slices"]
    video_recombined = recombine_terminal_streams(
        video_1,
        video_2,
        first_range=video_ranges[0],
        second_range=video_ranges[1],
        dim=2,
    )
    audio_recombined = recombine_terminal_streams(
        audio_1,
        audio_2,
        first_range=audio_ranges[0],
        second_range=audio_ranges[1],
        dim=-1,
    )
    video_diff = compare_tensors(video.detach().to("cpu"), video_recombined.detach().to("cpu"))
    audio_diff = compare_tensors(audio.detach().to("cpu"), audio_recombined.detach().to("cpu"))
    stage = "D_split_recombine"
    capture.add_value(stage, "contract", contract)
    capture.add_tensor(stage, "video.physical", video)
    capture.add_tensor(stage, "video.chunk_1", video_1)
    capture.add_tensor(stage, "video.chunk_2", video_2)
    capture.add_tensor(stage, "video.recombined", video_recombined)
    capture.add_tensor(stage, "audio.physical", audio)
    capture.add_tensor(stage, "audio.chunk_1", audio_1)
    capture.add_tensor(stage, "audio.chunk_2", audio_2)
    capture.add_tensor(stage, "audio.recombined", audio_recombined)
    capture.add_value(stage, "video_difference", video_diff.to_dict())
    capture.add_value(stage, "audio_difference", audio_diff.to_dict())
    capture.runtime["logical_streams"] = (
        (video_1.detach().to("cpu").contiguous(), audio_1.detach().to("cpu").contiguous()),
        (video_2.detach().to("cpu").contiguous(), audio_2.detach().to("cpu").contiguous()),
    )
    capture.runtime["terminal_contract"] = contract


def _run_continuum(
    capture: DiagnosticCapture,
    modules: SimpleNamespace,
    *,
    model: Any,
    clip: Any,
    video_vae: Any,
    audio_vae: Any,
    sampler: Any,
    sigmas: torch.Tensor,
    first_frame: torch.Tensor,
    last_frame: torch.Tensor,
    prompt: str,
    width: int,
    height: int,
    seed: int,
) -> None:
    sequence = modules.sequence
    original_sample = sequence.sample_chunk
    original_split = sequence._split_terminal_merged_latents
    sample_calls = 0
    split_calls = 0

    def sample_chunk(**kwargs):
        nonlocal sample_calls
        sample_calls += 1
        if sample_calls == 1:
            _capture_pre_sampler(
                capture,
                modules,
                conditioning=kwargs["conditioning"],
                latent=kwargs["latent"],
                sigmas=kwargs["sigmas"],
                seed=int(kwargs["seed"]),
            )
        result = original_sample(**kwargs)
        if sample_calls == 1:
            _capture_physical_sample(capture, modules, result)
            capture.add_value("C_physical_sample", "physical_seed", int(kwargs["seed"]))
        return result

    def split_terminal(video, audio, contract):
        nonlocal split_calls
        split_calls += 1
        result = original_split(video, audio, contract)
        if split_calls == 1:
            _capture_terminal_split(capture, video, audio, contract, result)
        return result

    sequence.sample_chunk = sample_chunk
    sequence._split_terminal_merged_latents = split_terminal
    try:
        prompt_plan = modules.prompts.make_prompt_plan(
            mode=modules.constants.PROMPT_MODE_FIXED,
            script=prompt,
            chunks=2,
            chunk_seconds=5.0,
        )
        continuum_model = model.clone()
        with _runtime_capture(capture):
            sequence.run_sequence(
                model=continuum_model,
                clip=clip,
                video_vae=video_vae,
                audio_vae=audio_vae,
                sampler=sampler,
                sigmas=sigmas,
                first_frame=first_frame,
                last_frame=last_frame,
                prompt_plan=prompt_plan,
                width=int(width),
                height=int(height),
                continuity=modules.constants.CONTINUITY_OPTIONS[0],
                base_seed=int(seed),
                audio_continuity=True,
                exact_total_duration=True,
                diagnostics_mode=modules.constants.DIAGNOSTICS_BASIC,
                reroll_from_chunk=0,
                reroll_nonce=0,
                strict_compatibility=False,
                debug=False,
                seam_correction=modules.constants.SEAM_CORRECTION_OFF,
                enable_preview=False,
                session=None,
                initial_state=None,
                latent_only=True,
                reference_assets=None,
                reference_audio_source=None,
                reference_audio_vae=None,
                driving_audio_source=None,
                driving_audio_vae=None,
                reference_video_source=None,
                timeline_video_source=None,
            )
        capture.add_value("C_physical_sample", "sampling_passes", sample_calls)
        capture.add_value("D_split_recombine", "split_calls", split_calls)
        del continuum_model
    finally:
        sequence.sample_chunk = original_sample
        sequence._split_terminal_merged_latents = original_split
        capture.add_value(
            "D_split_recombine",
            "sequence_patches_restored",
            sequence.sample_chunk is original_sample
            and sequence._split_terminal_merged_latents is original_split,
        )


def _make_av_latent(video: torch.Tensor, audio: torch.Tensor) -> dict[str, Any]:
    from comfy.nested_tensor import NestedTensor

    return {"samples": NestedTensor([video, audio])}


def _copy_audio(audio: dict[str, Any]) -> dict[str, Any]:
    return {
        "waveform": audio["waveform"].clone(),
        "sample_rate": int(audio["sample_rate"]),
    }


def _run_decode_diagnostics(capture: DiagnosticCapture, modules: SimpleNamespace, video_vae: Any, audio_vae: Any) -> dict[str, Any]:
    physical = capture.runtime.get("physical_streams")
    logical = capture.runtime.get("logical_streams")
    contract = capture.runtime.get("terminal_contract")
    if physical is None or logical is None or contract is None:
        return {
            "E1_decode_243": {"status": "NOT_RUN", "first_field": "missing terminal capture"},
            "E2_final_240": {"status": "NOT_RUN", "first_field": "missing terminal capture"},
        }

    decoder = modules.decoder
    physical_video, physical_audio = physical
    direct_latent = _make_av_latent(physical_video, physical_audio)
    direct_images = decoder.decode_video(video_vae, direct_latent)
    direct_audio = decoder.decode_audio(audio_vae, direct_latent)

    decoded_images = []
    decoded_audio = []
    for video, audio in logical:
        latent = _make_av_latent(video, audio)
        decoded_images.append(decoder.decode_video(video_vae, latent))
        decoded_audio.append(decoder.decode_audio(audio_vae, latent))

    trim_frames = 22
    reconstructed_images = torch.cat(
        (decoded_images[0][:124], decoded_images[1][:141][trim_frames:]),
        dim=0,
    ).contiguous()
    sample_rate = int(decoded_audio[0]["sample_rate"])
    if int(decoded_audio[1]["sample_rate"]) != sample_rate:
        raise ValueError("chunk audio sample rates differ during decode diagnostics")
    total_samples = int(round(243 / 24.0 * sample_rate))
    reconstructed_waveform = torch.empty(
        (*decoded_audio[0]["waveform"].shape[:-1], total_samples),
        dtype=decoded_audio[0]["waveform"].dtype,
        device="cpu",
    )
    segment_1 = decoder._slice_audio_for_timeline(
        decoded_audio[0], trim_frames=0, frame_start=0, frame_stop=124
    )
    segment_2 = decoder._slice_audio_for_timeline(
        decoded_audio[1], trim_frames=trim_frames, frame_start=124, frame_stop=243
    )
    split_sample = int(round(124 / 24.0 * sample_rate))
    reconstructed_waveform[..., :split_sample].copy_(segment_1)
    reconstructed_waveform[..., split_sample:].copy_(segment_2)
    reconstructed_audio = {"waveform": reconstructed_waveform, "sample_rate": sample_rate}

    direct_images, direct_audio, _ = decoder.enforce_total_frames(
        direct_images,
        direct_audio,
        target_frames=243,
        preserve_final_frame=False,
    )
    reconstructed_images, reconstructed_audio, _ = decoder.enforce_total_frames(
        reconstructed_images,
        reconstructed_audio,
        target_frames=243,
        preserve_final_frame=False,
    )

    image_e1 = compare_tensors(direct_images, reconstructed_images)
    audio_e1 = compare_tensors(direct_audio["waveform"], reconstructed_audio["waveform"])
    stage = "E1_decode_243"
    capture.add_tensor(stage, "direct.images", direct_images, persist=False)
    capture.add_tensor(stage, "split.images", reconstructed_images, persist=False)
    capture.add_tensor(stage, "direct.audio", direct_audio["waveform"], persist=False)
    capture.add_tensor(stage, "split.audio", reconstructed_audio["waveform"], persist=False)
    capture.add_value(stage, "images_difference", image_e1.to_dict())
    capture.add_value(stage, "audio_difference", audio_e1.to_dict())
    boundary = slice(112, 129)
    capture.add_tensor(stage, "direct.boundary_images", direct_images[boundary])
    capture.add_tensor(stage, "split.boundary_images", reconstructed_images[boundary])
    boundary_diff = compare_tensors(direct_images[boundary], reconstructed_images[boundary])
    capture.add_value(stage, "boundary_images_difference", boundary_diff.to_dict())

    direct_240_images, direct_240_audio, _ = decoder.enforce_total_frames(
        direct_images,
        _copy_audio(direct_audio),
        target_frames=240,
        preserve_final_frame=True,
    )
    split_240_images, split_240_audio, _ = decoder.enforce_total_frames(
        reconstructed_images,
        _copy_audio(reconstructed_audio),
        target_frames=240,
        preserve_final_frame=True,
    )
    image_e2 = compare_tensors(direct_240_images, split_240_images)
    audio_e2 = compare_tensors(direct_240_audio["waveform"], split_240_audio["waveform"])
    stage = "E2_final_240"
    capture.add_tensor(stage, "direct.images", direct_240_images, persist=False)
    capture.add_tensor(stage, "split.images", split_240_images, persist=False)
    capture.add_tensor(stage, "direct.audio", direct_240_audio["waveform"], persist=False)
    capture.add_tensor(stage, "split.audio", split_240_audio["waveform"], persist=False)
    capture.add_value(stage, "images_difference", image_e2.to_dict())
    capture.add_value(stage, "audio_difference", audio_e2.to_dict())
    capture.add_tensor(stage, "direct.boundary_images", direct_240_images[boundary])
    capture.add_tensor(stage, "split.boundary_images", split_240_images[boundary])

    return {
        "E1_decode_243": {
            "status": "MATCH" if image_e1.matches and audio_e1.matches else "DIFFER",
            "first_field": None if image_e1.matches and audio_e1.matches else ("images" if not image_e1.matches else "audio"),
            "images": image_e1.to_dict(),
            "audio": audio_e1.to_dict(),
            "boundary_images": boundary_diff.to_dict(),
        },
        "E2_final_240": {
            "status": "MATCH" if image_e2.matches and audio_e2.matches else "DIFFER",
            "first_field": None if image_e2.matches and audio_e2.matches else ("images" if not image_e2.matches else "audio"),
            "images": image_e2.to_dict(),
            "audio": audio_e2.to_dict(),
        },
    }


class H3CoreContinuumGpuDiagnostic:
    """Run an isolated Core 243f and Continuum 2x5s comparison in one queue."""

    OUTPUT_NODE = True
    CATEGORY = "H3-Continuum/Diagnostics"
    FUNCTION = "run"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("diagnostic_report",)

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
                "clip": ("CLIP",),
                "video_vae": ("VAE",),
                "audio_vae": ("VAE",),
                "sampler": ("SAMPLER",),
                "sigmas": ("SIGMAS",),
                "first_frame": ("IMAGE",),
                "last_frame": ("IMAGE",),
                "prompt": ("STRING", {"multiline": True, "default": "The subject moves continuously from the First Frame to the Last Frame."}),
                "width": ("INT", {"default": 640, "min": 64, "max": 4096, "step": 16}),
                "height": ("INT", {"default": 640, "min": 64, "max": 4096, "step": 16}),
                "seed": ("INT", {"default": 42, "min": 0, "max": 0xFFFFFFFFFFFFFFFF}),
                "output_subdir": ("STRING", {"default": "h3_continuum/diagnostics"}),
            }
        }

    def run(
        self,
        model,
        clip,
        video_vae,
        audio_vae,
        sampler,
        sigmas,
        first_frame,
        last_frame,
        prompt,
        width,
        height,
        seed,
        output_subdir,
    ):
        output_directory = _safe_output_directory(output_subdir)
        core = DiagnosticCapture("core")
        continuum = DiagnosticCapture("continuum")
        comparison: dict[str, Any] = {}
        modules = _resolve_continuum_modules()
        common = {
            "seed": int(seed),
            "width": int(width),
            "height": int(height),
            "physical_frames": 243,
            "spectrum": "must be OFF at the model input",
            "run_storage": "Off",
            "session": None,
            "continuum_root": str(modules.root),
        }
        core.manifest["conditions"] = common
        continuum.manifest["conditions"] = common

        try:
            _reset_rng(int(seed))
            _run_core(
                core,
                modules,
                model=model,
                clip=clip,
                video_vae=video_vae,
                sampler=sampler,
                sigmas=sigmas,
                first_frame=first_frame,
                last_frame=last_frame,
                prompt=prompt,
                width=width,
                height=height,
                seed=seed,
            )
            _release_cuda()
            _reset_rng(int(seed))
            _run_continuum(
                continuum,
                modules,
                model=model,
                clip=clip,
                video_vae=video_vae,
                audio_vae=audio_vae,
                sampler=sampler,
                sigmas=sigmas,
                first_frame=first_frame,
                last_frame=last_frame,
                prompt=prompt,
                width=width,
                height=height,
                seed=seed,
            )

            for stage in ("A_pre_sampler", "B_first_model_call", "C_physical_sample"):
                comparison[stage] = compare_stage(core, continuum, stage)

            d_values = continuum.manifest["stages"].get("D_split_recombine", {}).get("values", {})
            d_video = d_values.get("video_difference", {})
            d_audio = d_values.get("audio_difference", {})
            d_match = bool(d_video.get("matches") and d_audio.get("matches"))
            comparison["D_split_recombine"] = {
                "status": "MATCH" if d_match else "DIFFER",
                "first_field": None if d_match else ("video" if not d_video.get("matches") else "audio"),
                "video": d_video,
                "audio": d_audio,
            }
            comparison.update(_run_decode_diagnostics(continuum, modules, video_vae, audio_vae))
        except Exception as exc:
            comparison["error"] = {
                "type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
            }
        finally:
            output_directory.mkdir(parents=True, exist_ok=True)
            core.save(output_directory / "core")
            continuum.save(output_directory / "continuum")
            for stage in STAGE_ORDER:
                comparison.setdefault(stage, {"status": "NOT_RUN", "first_field": None})
            summary = format_comparison(comparison, output_directory)
            (output_directory / "comparison.json").write_text(
                json.dumps(comparison, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            (output_directory / "comparison.txt").write_text(summary + "\n", encoding="utf-8")
            _release_cuda()

        if "error" in comparison:
            error = comparison["error"]
            raise RuntimeError(
                f"GPU diagnostic failed; partial results were saved to {output_directory}: "
                f"{error['type']}: {error['message']}"
            )
        return (summary,)


NODE_CLASS_MAPPINGS = {
    "H3CoreContinuumGpuDiagnostic": H3CoreContinuumGpuDiagnostic,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "H3CoreContinuumGpuDiagnostic": "H3 Core vs Continuum GPU Diagnostic",
}
