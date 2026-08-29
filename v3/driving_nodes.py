"""Public V3.4 Driving Audio sampler and assembler nodes."""

from __future__ import annotations

import torch

from ..constants import CONTINUITY_OPTIONS, FPS
from ..driving_audio import prepare_driving_audio_source
from ..guide_timeline import (
    GUIDE_TYPE,
    make_still_image_guide,
    prepare_still_image_guide_source,
)
from ..hardening import diagnostics_is_full
from ..reference_video import (
    REFERENCE_VIDEO_SIZE_EFFICIENT,
    REFERENCE_VIDEO_SIZE_OPTIONS,
)
from ..v2.decoder import enforce_total_frames
from .assembly import (
    H3ContinuumAssembleSeamExperimental,
    _chunk_list,
    _singleton,
)
from .assembly_v35 import (
    BUFFER_BACKEND_AUTO,
    BUFFER_BACKEND_OPTIONS,
    assemble_decoded_chunks_v35,
)
from .memory_attribution import (
    format_assembly_projection,
    project_assembly_buffers,
)
from .nodes import CATEGORY as CONTINUUM_CATEGORY, H3ContinuumSamplerProduction


_DRIVING_AUDIO_PLAN_KEY = "_h3_continuum_driving_audio_v1"


def _unwrap_single_audio_value(value):
    while isinstance(value, list):
        if len(value) != 1:
            return None
        value = value[0]
    return value


def _copy_audio(value):
    value = _unwrap_single_audio_value(value)
    if not isinstance(value, dict):
        return None
    waveform = value.get("waveform")
    sample_rate = value.get("sample_rate")
    if not isinstance(waveform, torch.Tensor) or sample_rate is None:
        return None
    return {
        "waveform": waveform.detach().to("cpu").contiguous().clone(),
        "sample_rate": int(sample_rate),
    }


def _driving_audio_from_plan(args, kwargs):
    value = kwargs.get("assembly_plan")
    if value is None and len(args) >= 3:
        value = args[2]
    value = _unwrap_single_audio_value(value)
    if not isinstance(value, dict):
        return None
    return _copy_audio(value.get(_DRIVING_AUDIO_PLAN_KEY))


class H3ContinuumSamplerV34(H3ContinuumSamplerProduction):
    """V3.4 sampler with globally encoded, absolute-time Driving Audio."""

    DEPRECATED = False
    CATEGORY = CONTINUUM_CATEGORY
    DESCRIPTION = (
        "H3 Continuum V3.4 with optional Driving Audio and persistent Video Reference. "
        "Video Reference uses an IMAGE frame batch and one-chunk reference prefix."
    )
    SEARCH_ALIASES = [
        "H3 Continuum Sampler V3.4",
        "MiniMax H3 Driving Audio",
    ]
    RETURN_TYPES = (
        "LATENT",
        "LATENT",
        "H3_CONTINUUM_ASSEMBLY_PLAN",
        "STRING",
        "AUDIO",
    )
    RETURN_NAMES = (
        "video_latents",
        "audio_latents",
        "assembly_plan",
        "status",
        "driving_audio",
    )
    OUTPUT_IS_LIST = (True, True, False, False, False)

    @classmethod
    def INPUT_TYPES(cls):
        schema = super().INPUT_TYPES()
        required = dict(schema.get("required", {}))
        required["video_reference_size"] = (
            REFERENCE_VIDEO_SIZE_OPTIONS,
            {
                "default": REFERENCE_VIDEO_SIZE_EFFICIENT,
                "display_name": "Video Guide Size",
                "tooltip": (
                    "Efficient limits Video Guide Frames to about 0.4 MP; Balanced uses "
                    "about 0.6 MP; Match Output uses the output pixel area. Source "
                    "aspect ratio is preserved and smaller sources are not enlarged."
                ),
            },
        )
        optional = dict(schema.get("optional", {}))
        optional.pop("reference_audio_1", None)
        optional.pop("reference_audio_vae", None)
        optional["reference_video_1"] = (
            "IMAGE",
            {
                "display_name": "Video Guide Frames",
                "tooltip": (
                    "Optional video guide. Connect the IMAGE frame batch from a video loader; "
                    "source-video audio is not included. Frames are interpreted at 24 fps "
                    "and applied to every chunk. Non-native frame counts are padded by "
                    "repeating the final frame to the next H3 17k+5 count, up to the "
                    "one-chunk limit."
                ),
            },
        )
        optional["driving_audio"] = (
            "AUDIO",
            {
                "display_name": "Driving Audio",
                "tooltip": (
                    "Optional original audio timeline. It is used as native H3 guide "
                    "conditioning and selected unchanged for final output."
                )
            },
        )
        optional["audio_vae"] = (
            "VAE",
            {
                "display_name": "Driving Audio VAE",
                "tooltip": (
                    "Required only when Driving Audio is connected. Uses the same "
                    "Audio VAE encode path as ComfyUI Core MiniMax H3 Add Guide."
                )
            },
        )
        schema["required"] = required
        schema["optional"] = optional
        return schema

    def run(
        self,
        driving_audio=None,
        audio_vae=None,
        reference_video_1=None,
        video_reference_size=REFERENCE_VIDEO_SIZE_EFFICIENT,
        capture_refine_context=False,
        reference_audio_1=None,
        reference_audio_vae=None,
        **kwargs,
    ):
        from ..reference_video import prepare_reference_video_source
        from ..temporal import align_frame_count_up

        target_frames = round(
            int(kwargs["chunks"]) * float(kwargs["chunk_seconds"]) * FPS
        )
        source = prepare_driving_audio_source(
            driving_audio,
            audio_vae,
            target_frames=target_frames,
            fps=FPS,
        )
        reference_video_source = prepare_reference_video_source(
            reference_video_1,
            target_frames=align_frame_count_up(
                int(round(float(kwargs["chunk_seconds"]) * FPS))
            ),
            output_width=int(kwargs["width"]),
            output_height=int(kwargs["height"]),
            size_mode=str(video_reference_size),
        )
        outputs = super().run(
            reference_audio_1=reference_audio_1,
            reference_audio_vae=reference_audio_vae,
            driving_audio_source=source,
            driving_audio_vae=audio_vae,
            reference_video_source=reference_video_source,
            capture_refine_context=bool(capture_refine_context),
            **kwargs,
        )
        selected_audio = _copy_audio(source.source_audio) if source is not None else None
        if selected_audio is not None and len(outputs) >= 3 and isinstance(outputs[2], dict):
            assembly_plan = dict(outputs[2])
            assembly_plan[_DRIVING_AUDIO_PLAN_KEY] = _copy_audio(selected_audio)
            outputs = (*outputs[:2], assembly_plan, *outputs[3:])
        if bool(capture_refine_context):
            return (*outputs[:4], selected_audio, outputs[4])
        return (*outputs, selected_audio)


class H3ContinuumSamplerV35(H3ContinuumSamplerV34):
    """V3.5 sampler with a physical-group First Pass refine context output."""

    DEPRECATED = False
    CATEGORY = CONTINUUM_CATEGORY
    DESCRIPTION = (
        "H3 Continuum V3.5 sampler. It preserves the V3.4 outputs and adds one "
        "physical-group refine context for context-aware Hi-Res Fix or an "
        "external latent Second Pass."
    )
    SEARCH_ALIASES = [
        "H3 Continuum Sampler V3.5",
        "MiniMax H3 context-aware Hi-Res Fix",
    ]
    RETURN_TYPES = (
        *H3ContinuumSamplerV34.RETURN_TYPES,
        "H3_CONTINUUM_REFINE_CONTEXT",
    )
    RETURN_NAMES = (
        *H3ContinuumSamplerV34.RETURN_NAMES,
        "refine_context",
    )
    OUTPUT_IS_LIST = (*H3ContinuumSamplerV34.OUTPUT_IS_LIST, False)

    @classmethod
    def INPUT_TYPES(cls):
        schema = super().INPUT_TYPES()
        optional = dict(schema.get("optional", {}))
        optional["reference_audio_1"] = (
            "AUDIO",
            {
                "display_name": "Reference Audio (Optional)",
                "tooltip": (
                    "Optional standalone audio reference for H3 conditioning. "
                    "It is not the audio track of Video Guide Frames. Unlike Driving "
                    "Audio, it does not replace the generated final audio."
                ),
            },
        )
        optional["reference_audio_vae"] = (
            "VAE",
            {
                "display_name": "Reference Audio VAE (Optional)",
                "tooltip": (
                    "Required only when Reference Audio is connected. It encodes the "
                    "reference for H3 conditioning; generated audio remains the output."
                ),
            },
        )
        schema["optional"] = optional
        return schema

    def run(self, *args, **kwargs):
        kwargs.pop("capture_refine_context", None)
        kwargs.pop("memory_attribution", None)
        kwargs.pop("prompt_conditioning_cache", None)
        return super().run(
            *args,
            capture_refine_context=True,
            memory_attribution=True,
            prompt_conditioning_cache=True,
            **kwargs,
        )


CONTINUATION_BACKEND_STANDARD = "Standard"
CONTINUATION_BACKEND_COMPATIBILITY = "Compatibility"
CONTINUATION_BACKEND_OPTIONS = (
    CONTINUATION_BACKEND_STANDARD,
    CONTINUATION_BACKEND_COMPATIBILITY,
)

_V36_BALANCED_CONTINUITY = CONTINUITY_OPTIONS[0]
_V36_NON_BALANCED_AUDIO_FALLBACK_REASON = (
    "Masked AV Standard currently requires Balanced 22 when Audio Continuity "
    "is enabled."
)


def _resolve_v36_continuation_transport(
    *,
    continuation_backend,
    audio_continuity,
    continuity,
):
    from ..v2.sequence import (
        MASKED_AV_PREFIX_22_V1,
        MASKED_VIDEO_PREFIX_V1,
        REFERENCE_CONTEXT_V1,
    )

    backend = str(continuation_backend)
    if backend == CONTINUATION_BACKEND_COMPATIBILITY:
        return REFERENCE_CONTEXT_V1, None
    if not bool(audio_continuity):
        return MASKED_VIDEO_PREFIX_V1, None
    if str(continuity) == _V36_BALANCED_CONTINUITY:
        return MASKED_AV_PREFIX_22_V1, None
    return REFERENCE_CONTEXT_V1, _V36_NON_BALANCED_AUDIO_FALLBACK_REASON


def _prepend_v36_transport_report(outputs, fallback_reason):
    if fallback_reason is None:
        return outputs
    status = (
        "Continuation Backend: Standard\n"
        "Resolved transport: Reference Context\n"
        f"Reason: {fallback_reason}\n"
        f"{str(outputs[3])}"
    )
    return (*outputs[:3], status, *outputs[4:])


class H3ContinuumSamplerV36(H3ContinuumSamplerV35):
    """V3.6 sampler with Masked continuation and a legacy fallback."""

    DEPRECATED = False
    CATEGORY = CONTINUUM_CATEGORY
    DESCRIPTION = (
        "H3 Continuum V3.6 sampler. Standard continuation preserves prior Video/Audio "
        "inside the next H3 target with native noise masks; Compatibility retains the "
        "V3.5 Reference Context transport. With Audio Continuity enabled, Standard "
        "uses Masked AV for Balanced 22 and safely falls back to Reference Context "
        "for Fast 5, Strong 39, and Auto."
    )
    SEARCH_ALIASES = [
        "H3 Continuum Sampler V3.6",
        "MiniMax H3 masked continuation",
    ]

    @classmethod
    def INPUT_TYPES(cls):
        schema = super().INPUT_TYPES()
        required = dict(schema.get("required", {}))
        required["continuation_backend"] = (
            CONTINUATION_BACKEND_OPTIONS,
            {
                "default": CONTINUATION_BACKEND_STANDARD,
                "display_name": "Continuation Backend",
                "advanced": True,
                "tooltip": (
                    "Standard uses the V3.6 target-preserving continuation path. "
                    "With Audio Continuity enabled, Masked AV currently uses Balanced "
                    "22; Fast 5, Strong 39, and Auto safely use Reference Context. "
                    "Compatibility restores the V3.5 Reference Context path for "
                    "older workflows or comparison. Run Storage identity follows "
                    "the resolved transport before execution begins."
                ),
            },
        )
        schema["required"] = required
        return schema

    def run(
        self,
        *args,
        continuation_backend=CONTINUATION_BACKEND_STANDARD,
        **kwargs,
    ):
        audio_continuity = kwargs.get("audio_continuity")
        if audio_continuity is None:
            audio_continuity = True
        continuity = kwargs.get("continuity", _V36_BALANCED_CONTINUITY)
        transport, fallback_reason = _resolve_v36_continuation_transport(
            continuation_backend=continuation_backend,
            audio_continuity=audio_continuity,
            continuity=continuity,
        )
        kwargs["continuation_transport"] = transport
        outputs = super().run(*args, **kwargs)
        return _prepend_v36_transport_report(outputs, fallback_reason)


class H3ContinuumStillImageGuideV37:
    """One frame-based image anchor for the V3.7 sampler."""

    DEPRECATED = False
    CATEGORY = CONTINUUM_CATEGORY
    DESCRIPTION = (
        "Prepare one Still Image Guide at an absolute 24 fps output frame. "
        "The V3.7 sampler resolves it to the owning physical group and Core frame_idx."
    )
    SEARCH_ALIASES = [
        "H3 Continuum Still Image Guide",
        "MiniMax H3 Add Guide timeline",
    ]

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "absolute_frame": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 0x7FFFFFFF,
                        "step": 1,
                        "display_name": "Absolute Frame (24 fps)",
                        "tooltip": (
                            "Zero-based frame on the final visible Continuum timeline."
                        ),
                    },
                ),
            }
        }

    RETURN_TYPES = (GUIDE_TYPE,)
    RETURN_NAMES = ("guide",)
    FUNCTION = "pack"
    CATEGORY = CONTINUUM_CATEGORY

    def pack(self, image, absolute_frame):
        return (make_still_image_guide(image, absolute_frame),)


class H3ContinuumSamplerV37(H3ContinuumSamplerV36):
    """V3.6-compatible sampler with one physical-group Still Image Guide."""

    DEPRECATED = False
    CATEGORY = CONTINUUM_CATEGORY
    DESCRIPTION = (
        "H3 Continuum V3.7 Stage 2 sampler. It preserves V3.6 behavior and can "
        "inject one Still Image Guide into only its resolved physical sampling group."
    )
    SEARCH_ALIASES = [
        "H3 Continuum Sampler V3.7",
        "MiniMax H3 absolute frame guide",
    ]

    @classmethod
    def INPUT_TYPES(cls):
        schema = super().INPUT_TYPES()
        optional = dict(schema.get("optional", {}))
        optional["guide"] = (
            GUIDE_TYPE,
            {
                "display_name": "Still Image Guide (Optional)",
                "tooltip": (
                    "Optional V3.7 Still Image Guide. Only the owning physical "
                    "sampling group receives the Core minimax_keyframes entry."
                ),
            },
        )
        schema["optional"] = optional
        return schema

    def run(self, guide=None, **kwargs):
        guide_source = prepare_still_image_guide_source(
            guide,
            output_width=int(kwargs["width"]),
            output_height=int(kwargs["height"]),
        )
        return super().run(guide_source=guide_source, **kwargs)


class H3ContinuumAssembleSeamV34(H3ContinuumAssembleSeamExperimental):
    """Assemble decoded chunks and select original Driving Audio when connected."""

    DEPRECATED = False
    CATEGORY = CONTINUUM_CATEGORY
    DESCRIPTION = (
        "V3.4 decoded-chunk assembler. Driving Audio bypasses generated audio "
        "and Audio Seam while video seam correction remains available."
    )

    @classmethod
    def INPUT_TYPES(cls):
        schema = super().INPUT_TYPES()
        optional = dict(schema.get("optional", {}))
        optional["driving_audio"] = (
            "AUDIO",
            {
                "tooltip": (
                    "Connect the sampler Driving Audio output. When present, generated "
                    "audio and Audio Seam are bypassed."
                )
            },
        )
        schema["optional"] = optional
        return schema

    def assemble(self, *args, driving_audio=None, **kwargs):
        preserved_audio = _driving_audio_from_plan(args, kwargs)
        images, audio, report = super().assemble(*args, **kwargs)
        selected = preserved_audio or _copy_audio(driving_audio)
        if selected is None:
            return images, audio, report

        plan_value = kwargs.get("assembly_plan")
        if plan_value is None and len(args) >= 3:
            plan_value = args[2]
        while isinstance(plan_value, list):
            if len(plan_value) != 1:
                raise ValueError("assembly_plan must contain exactly one value")
            plan_value = plan_value[0]
        exact = kwargs.get("exact_total_duration")
        if exact is None and len(args) >= 4:
            exact = args[3]
        while isinstance(exact, list):
            if len(exact) != 1:
                raise ValueError("exact_total_duration must contain exactly one value")
            exact = exact[0]
        if bool(exact):
            _, selected, _ = enforce_total_frames(
                images,
                selected,
                target_frames=int(plan_value["target_frames"]),
                preserve_final_frame=bool(plan_value.get("preserve_final_frame", False)),
            )
        source = "assembly plan" if preserved_audio is not None else "direct input"
        samples = int(selected["waveform"].shape[-1])
        report = str(report) + (
            f"\nDriving Audio: preserved source selected from {source}; "
            f"sample_rate={selected['sample_rate']}, samples={samples}; "
            "generated audio and Audio Seam bypassed."
        )
        return images, selected, report


def _assembly_argument(args, kwargs, name, index):
    if name in kwargs:
        return kwargs[name]
    if len(args) > index:
        return args[index]
    return None


def _insert_projection_report(report, line):
    lines = str(report).splitlines()
    for index, value in enumerate(lines):
        if value.startswith("Memory [assemble preflight]"):
            lines.insert(index + 1, line)
            return "\n".join(lines)
    lines.append(line)
    return "\n".join(lines)


class H3ContinuumAssembleSeamV35(H3ContinuumAssembleSeamV34):
    """Independent V3.5 direct-write assembly with selectable IMAGE storage."""

    DEPRECATED = False
    CATEGORY = CONTINUUM_CATEGORY
    DESCRIPTION = (
        "V3.5 decoded-chunk assembler with Auto, RAM, or Disk-backed IMAGE "
        "storage, direct Exact Duration writes, and small-patch Video Seam."
    )

    @classmethod
    def INPUT_TYPES(cls):
        schema = super().INPUT_TYPES()
        required = dict(schema["required"])
        diagnostics = required.pop("diagnostics")
        required["buffer_backend"] = (
            BUFFER_BACKEND_OPTIONS,
            {
                "default": BUFFER_BACKEND_AUTO,
                "display_name": "Buffer Backend",
                "tooltip": (
                    "Auto keeps outputs up to 4 GiB in RAM only when physical "
                    "memory has a safety reserve; otherwise it maps the final "
                    "IMAGE to disk. Manual RAM and Disk-backed remain available."
                ),
            },
        )
        required["diagnostics"] = diagnostics
        schema["required"] = required
        return schema

    def assemble(
        self,
        images,
        audio,
        assembly_plan,
        exact_total_duration,
        audio_seam,
        video_seam,
        buffer_backend,
        diagnostics,
        driving_audio=None,
    ):
        image_chunks = _chunk_list(images)
        audio_chunks = _chunk_list(audio)
        plan = _singleton(assembly_plan, "assembly_plan")
        exact = bool(_singleton(exact_total_duration, "exact_total_duration"))
        audio_seam_mode = str(_singleton(audio_seam, "audio_seam"))
        video_seam_mode = str(_singleton(video_seam, "video_seam"))
        backend = str(_singleton(buffer_backend, "buffer_backend"))
        diagnostics_mode = str(_singleton(diagnostics, "diagnostics"))
        preserved_audio = _copy_audio(plan.get(_DRIVING_AUDIO_PLAN_KEY))
        selected_audio = preserved_audio or _copy_audio(driving_audio)
        selected_audio_source = None
        if selected_audio is not None:
            selected_audio_source = (
                "assembly plan" if preserved_audio is not None else "direct input"
            )
        projection_line = None
        if diagnostics_is_full(diagnostics_mode):
            try:
                projection = project_assembly_buffers(
                    images=image_chunks,
                    audio=audio_chunks,
                    assembly_plan=plan,
                    exact_total_duration=exact,
                )
                projection_line = format_assembly_projection(projection) + (
                    "; V3.5 Exact Duration IMAGE write=direct; "
                    "additional final IMAGE copy=no"
                )
            except Exception as exc:
                projection_line = (
                    "Projected assembly buffers [V3.5]: unavailable "
                    f"({type(exc).__name__}: {exc})"
                )

        result_images, result_audio, report = assemble_decoded_chunks_v35(
            images=image_chunks,
            audio=audio_chunks,
            assembly_plan=plan,
            exact_total_duration=exact,
            audio_seam=audio_seam_mode,
            video_seam=video_seam_mode,
            diagnostics=diagnostics_mode,
            buffer_backend=backend,
            final_audio_override=selected_audio,
            final_audio_source=selected_audio_source,
        )
        if projection_line is not None:
            report = _insert_projection_report(report, projection_line)
        return result_images, result_audio, report


NODE_CLASS_MAPPINGS = {
    "H3ContinuumSamplerV34": H3ContinuumSamplerV34,
    "H3ContinuumSamplerV35": H3ContinuumSamplerV35,
    "H3ContinuumSamplerV36": H3ContinuumSamplerV36,
    "H3ContinuumStillImageGuideV37": H3ContinuumStillImageGuideV37,
    "H3ContinuumSamplerV37": H3ContinuumSamplerV37,
    "H3ContinuumAssembleSeamV34": H3ContinuumAssembleSeamV34,
    "H3ContinuumAssembleSeamV35": H3ContinuumAssembleSeamV35,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "H3ContinuumSamplerV34": "H3 Continuum Sampler V3.4",
    "H3ContinuumSamplerV35": "H3 Continuum Sampler V3.5",
    "H3ContinuumSamplerV36": "H3 Continuum Sampler V3.6",
    "H3ContinuumStillImageGuideV37": "H3 Continuum Still Image Guide V3.7",
    "H3ContinuumSamplerV37": "H3 Continuum Sampler V3.7",
    "H3ContinuumAssembleSeamV34": "H3 Continuum Assemble + Seam V3.4",
    "H3ContinuumAssembleSeamV35": "H3 Continuum Assemble + Seam V3.5",
}
