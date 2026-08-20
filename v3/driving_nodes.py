"""Public V3.4 Driving Audio sampler and assembler nodes."""

from __future__ import annotations

import torch

from ..constants import FPS, V2_CONTINUITY_OPTIONS
from ..driving_audio import prepare_driving_audio_source
from ..masked_continuation import (
    CONTINUATION_METHODS,
    CONTINUATION_NATIVE_MASKED,
    continuation_method_scope,
    validate_native_masked_request,
)
from ..reference import bundle_reference_images
from ..reference_video import (
    REFERENCE_VIDEO_SIZE_EFFICIENT,
    REFERENCE_VIDEO_SIZE_OPTIONS,
)
from ..v2.decoder import enforce_total_frames
from .assembly import H3ContinuumAssembleSeamExperimental
from .nodes import CATEGORY as CONTINUUM_CATEGORY, H3ContinuumSamplerProduction


_DRIVING_AUDIO_PLAN_KEY = "_h3_continuum_driving_audio_v1"
V34_CONTINUITY_STRONG = "Strong — 39 frames"
V34_CONTINUITY_OPTIONS = (
    V2_CONTINUITY_OPTIONS[0],
    V2_CONTINUITY_OPTIONS[1],
    V2_CONTINUITY_OPTIONS[2],
    V34_CONTINUITY_STRONG,
    V2_CONTINUITY_OPTIONS[3],
)


def _normalize_v34_continuity(value: str) -> str:
    """Map the V3.4 display value onto the inherited sequence wire contract.

    V2/V3.3 keep the historical ``Strong — 39 frames (Experimental)`` value.
    V3.4 promotes that exact 39-frame boundary, so its public widget uses the
    unsuffixed label while still accepting the old serialized value as an API
    compatibility alias.
    """

    value = str(value)
    if value == V34_CONTINUITY_STRONG:
        return V2_CONTINUITY_OPTIONS[3]
    return value


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
    """V3.4 sampler with native masked continuation and Driving Audio."""

    DEPRECATED = False
    CATEGORY = CONTINUUM_CATEGORY
    DESCRIPTION = (
        "H3 Continuum V3.4 with native masked AV continuation by default, optional "
        "Guide / Motion Context continuation, Driving Audio, and persistent Video Reference."
    )
    SEARCH_ALIASES = [
        "H3 Continuum Sampler V3.4",
        "MiniMax H3 Driving Audio",
        "MiniMax H3 masked continuation",
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
        # Keep the inherited key position stable for saved workflows while making
        # the new exact-AV default internally valid. 39 video frames map exactly
        # to 65 H3 audio-latent steps at 24 fps / 40 Hz. The final legacy value
        # remains accepted for headless/serialized V3.4 compatibility; v34_ui.js
        # presents only the canonical unsuffixed V3.4 value.
        required["continuity"] = (
            V34_CONTINUITY_OPTIONS,
            {
                "default": V34_CONTINUITY_STRONG,
                "tooltip": (
                    "Protected previous-chunk context. Native Masked generated-audio "
                    "continuation requires the exact 39-frame AV boundary; video-only "
                    "continuation and Guide / Motion Context also support 5 or 22 frames."
                ),
            },
        )
        required["video_reference_size"] = (
            REFERENCE_VIDEO_SIZE_OPTIONS,
            {
                "default": REFERENCE_VIDEO_SIZE_EFFICIENT,
                "display_name": "Video Reference Size",
                "tooltip": (
                    "Efficient limits Video Reference to about 0.4 MP; Balanced uses "
                    "about 0.6 MP; Match Output uses the output pixel area. Source "
                    "aspect ratio is preserved and smaller sources are not enlarged."
                ),
            },
        )
        # Appending this widget avoids shifting existing V3.4 serialized widget
        # positions. New nodes receive the Native default; v34_ui.js migrates
        # saved graphs without this widget to Guide / Motion Context.
        required["continuation_method"] = (
            CONTINUATION_METHODS,
            {
                "default": CONTINUATION_NATIVE_MASKED,
                "display_name": "Continuation Method",
                "tooltip": (
                    "Native Masked preserves the previous generated H3 latent directly "
                    "inside the next target and is recommended for exact same-shot continuation. "
                    "Guide / Motion Context keeps the previous clip as softer H3 guide context."
                ),
            },
        )
        optional = dict(schema.get("optional", {}))
        optional.pop("reference_audio_1", None)
        optional.pop("reference_audio_vae", None)
        for index in range(4, 9):
            optional[f"reference_image_{index}"] = ("IMAGE",)
        optional["reference_video_1"] = (
            "IMAGE",
            {
                "display_name": "Video Reference",
                "tooltip": (
                    "Optional persistent video reference. Connect an IMAGE frame batch; "
                    "frames are interpreted at 24 fps and applied to every chunk."
                ),
            },
        )
        optional["driving_audio"] = (
            "AUDIO",
            {
                "tooltip": (
                    "Optional original audio timeline. It is used as native H3 guide "
                    "conditioning and selected unchanged for final output."
                )
            },
        )
        optional["audio_vae"] = (
            "VAE",
            {
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
        continuation_method=CONTINUATION_NATIVE_MASKED,
        **kwargs,
    ):
        from ..reference_video import prepare_reference_video_source
        from ..temporal import align_frame_count_up

        # Validate the cross-modal continuation contract before any VAE/model
        # preparation. Old or manually edited workflows may still serialize a
        # 5/22-frame profile alongside Native Masked + generated Audio Continuity;
        # discovering that only when chunk 2 starts wastes a complete chunk 1.
        continuity = _normalize_v34_continuity(
            kwargs.get("continuity", V34_CONTINUITY_STRONG)
        )
        validate_native_masked_request(
            method=continuation_method,
            continuity=continuity,
            audio_continuity=bool(kwargs.get("audio_continuity", True)),
            driving_audio_active=driving_audio is not None,
            chunks=int(kwargs.get("chunks", 1)),
        )
        # The inherited V2/V3.3 sequence engine intentionally keeps its stable
        # historical wire value. Normalize only at this V3.4 facade boundary.
        kwargs["continuity"] = continuity

        active_reference = any(
            kwargs.get(f"reference_image_{index}") is not None
            for index in range(1, 9)
        )
        if active_reference:
            # V3.4 follows Core-style mode precedence: Reference mode wins over
            # connected First/Last inputs rather than rejecting the combination.
            kwargs["first_frame"] = None
            kwargs["last_frame"] = None

        extra_references = [
            kwargs.pop(f"reference_image_{index}", None)
            for index in range(4, 9)
        ]
        if any(image is not None for image in extra_references):
            kwargs["reference_image_3"] = bundle_reference_images(
                kwargs.get("reference_image_3"),
                *extra_references,
            )

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
        with continuation_method_scope(continuation_method):
            outputs = super().run(
                reference_audio_1=None,
                reference_audio_vae=None,
                driving_audio_source=source,
                driving_audio_vae=audio_vae,
                reference_video_source=reference_video_source,
                **kwargs,
            )
        selected_audio = _copy_audio(source.source_audio) if source is not None else None
        if selected_audio is not None and len(outputs) >= 3 and isinstance(outputs[2], dict):
            assembly_plan = dict(outputs[2])
            assembly_plan[_DRIVING_AUDIO_PLAN_KEY] = _copy_audio(selected_audio)
            outputs = (*outputs[:2], assembly_plan, *outputs[3:])
        return (*outputs, selected_audio)


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


NODE_CLASS_MAPPINGS = {
    "H3ContinuumSamplerV34": H3ContinuumSamplerV34,
    "H3ContinuumAssembleSeamV34": H3ContinuumAssembleSeamV34,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "H3ContinuumSamplerV34": "H3 Continuum Sampler V3.4",
    "H3ContinuumAssembleSeamV34": "H3 Continuum Assemble + Seam V3.4",
}
