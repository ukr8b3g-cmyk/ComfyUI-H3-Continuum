"""ComfyUI nodes for H3 Continuum Join."""

from __future__ import annotations

import logging
import torch

from .compatibility import accelerator_summary, check_comfy_h3_runtime
from .constants import (
    CONTINUITY_FRAMES,
    CONTINUITY_OPTIONS,
)
from .continuation import (
    POLICY_ERROR,
    POLICY_KEEP,
    POLICY_REPLACE,
    conditioning_diagnostics as _conditioning_diagnostics,
    new_h3_latent as _new_h3_latent,
    prepare_conditioning as _prepare_conditioning,
)
from .media import assemble_segments, trim_audio as _trim_audio
from .model_patch import patch_model
from .state import (
    StateValidationError,
    capture_state,
    extract_av_streams,
    make_plan,
    select_context,
    validate_plan,
    validate_state,
)
from .state_io import load_state, save_state, state_mtime, state_paths
from .temporal import (
    is_valid_frame_count,
    largest_context_capacity,
    make_extension_shape,
    pixel_frames_for_latent_t,
)
from .version import PACKAGE_VERSION

LOG = logging.getLogger("h3_continuum_join")
CATEGORY = "MiniMax H3/Continuum"


class H3ContinuumJoin:
    DESCRIPTION = (
        "Prepare a native MiniMax H3 continuation clip from a previous AV latent state. "
        "Uses one timeline-positioned video/audio context reference, per-MODEL wrappers only, "
        "and composes with external SageAttention, Sol-Attn, and Spectrum."
    )
    SEARCH_ALIASES = ["H3 extend", "MiniMax H3 continuation", "H3 long video"]

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
                "conditioning": ("CONDITIONING",),
                "latent": ("LATENT",),
                "continuity": (CONTINUITY_OPTIONS, {"default": CONTINUITY_OPTIONS[0]}),
                "extend_seconds": (
                    "FLOAT",
                    {
                        "default": 5.0,
                        "min": 0.5,
                        "max": 15.0,
                        "step": 0.1,
                        "tooltip": "Requested NEW duration. H3 snaps to the nearest 17k+5 frame count.",
                    },
                ),
                "audio_continuity": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "Carry the previous native audio latent and place it on the new clip timeline.",
                    },
                ),
                "first_frame_policy": (
                    [POLICY_REPLACE, POLICY_ERROR, POLICY_KEEP],
                    {
                        "default": POLICY_REPLACE,
                        "tooltip": (
                            "Recommended: replace only the old spatial keyframe. If the prompt was encoded "
                            "with an input image, its Qwen visual tokens remain as an identity cue."
                        ),
                    },
                ),
                "preserve_last_frame": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "Move an existing FL2VA last-frame anchor to the end of the continuation clip.",
                    },
                ),
                "strict_compatibility": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": (
                            "Run proactive native-H3 API checks. Marked Continuum payload failures always stop; "
                            "they are never silently bypassed."
                        ),
                    },
                ),
                "debug": ("BOOLEAN", {"default": False}),
            },
            "optional": {"previous_state": ("H3_CONTINUUM_STATE",)},
        }

    RETURN_TYPES = ("MODEL", "CONDITIONING", "LATENT", "H3_CONTINUUM_PLAN", "STRING")
    RETURN_NAMES = ("model", "conditioning", "latent", "plan", "report")
    FUNCTION = "join"
    CATEGORY = CATEGORY

    def join(
        self,
        model,
        conditioning,
        latent,
        continuity,
        extend_seconds,
        audio_continuity,
        first_frame_policy,
        preserve_last_frame,
        strict_compatibility,
        debug,
        previous_state=None,
    ):
        issues = check_comfy_h3_runtime()
        if issues and strict_compatibility:
            raise RuntimeError("H3 runtime is incompatible: " + "; ".join(issues))
        patched_model = patch_model(model, strict=strict_compatibility, debug=debug)
        video, _audio = extract_av_streams(latent)
        current_frames = pixel_frames_for_latent_t(int(video.shape[2]))
        if not is_valid_frame_count(current_frames):
            raise StateValidationError(
                f"input latent represents {current_frames} frames, not a native H3 17k+5 length"
            )
        width, height = int(video.shape[-1]) * 16, int(video.shape[-2]) * 16
        context_frames = CONTINUITY_FRAMES[continuity]

        if previous_state is None:
            plan = make_plan(
                continuation=False,
                clip_index=1,
                total_frames=current_frames,
                trim_frames=0,
                width=width,
                height=height,
                context_frames=context_frames,
                state_capacity_frames=largest_context_capacity(current_frames),
                requested_extend_seconds=current_frames / 24.0,
                debug=debug,
            )
            report = (
                f"H3 Continuum Join {PACKAGE_VERSION}: initial clip; {current_frames} frames "
                f"({current_frames/24.0:.3f}s). {accelerator_summary(patched_model)}"
            )
            return patched_model, conditioning, latent, plan, report

        state = validate_state(previous_state)
        if int(state["width"]) != width or int(state["height"]) != height:
            raise StateValidationError(
                f"state is {state['width']}x{state['height']} but latent is {width}x{height}; "
                "automatic state resizing is disabled"
            )
        diagnostics = _conditioning_diagnostics(conditioning)
        video_context, audio_context, grid_offset = select_context(
            state, context_frames, include_audio=bool(audio_continuity)
        )
        shape = make_extension_shape(context_frames, float(extend_seconds))
        new_latent = _new_h3_latent(
            latent, video_t=shape.video_latent_t, audio_t=shape.audio_latent_t
        )
        new_conditioning = _prepare_conditioning(
            conditioning,
            video_context=video_context,
            audio_context=audio_context,
            audio_grid_offset=grid_offset,
            context_frames=context_frames,
            new_frame_count=shape.total_frames,
            first_frame_policy=first_frame_policy,
            preserve_last_frame=bool(preserve_last_frame),
            source_frame_count=current_frames,
        )
        clip_index = int(state.get("clip_index", 0)) + 1
        plan = make_plan(
            continuation=True,
            clip_index=clip_index,
            total_frames=shape.total_frames,
            trim_frames=context_frames,
            width=width,
            height=height,
            context_frames=context_frames,
            state_capacity_frames=largest_context_capacity(shape.net_new_frames),
            requested_extend_seconds=float(extend_seconds),
            debug=debug,
        )
        plan["visual_identity_tokens"] = diagnostics["visual_tokens"]
        report_parts = [
            f"Continuation clip {clip_index}: generate {shape.total_frames}, trim {context_frames}, "
            f"append {shape.net_new_frames} frames ({shape.actual_extend_seconds:.3f}s).",
            f"Audio context {'ON' if audio_context is not None else 'OFF'}.",
            f"Next-state capacity {plan['state_capacity_frames']} frames.",
        ]
        if diagnostics["visual_tokens"]:
            report_parts.append(
                f"Qwen visual identity tokens retained: {diagnostics['visual_tokens']}."
            )
        report_parts.append(accelerator_summary(patched_model))
        return patched_model, new_conditioning, new_latent, plan, " ".join(report_parts)


class H3ContinuumFinish:
    DESCRIPTION = (
        "Trim the overlap, sample-align audio, and capture a CPU AV latent state for the next Join."
    )
    SEARCH_ALIASES = ["H3 trim", "H3 continuation state"]

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "samples": ("LATENT",),
                "images": ("IMAGE",),
                "audio": ("AUDIO",),
                "plan": ("H3_CONTINUUM_PLAN",),
            }
        }

    RETURN_TYPES = ("IMAGE", "AUDIO", "H3_CONTINUUM_STATE", "STRING")
    RETURN_NAMES = ("images", "audio", "state", "report")
    FUNCTION = "finish"
    CATEGORY = CATEGORY

    def finish(self, samples, images, audio, plan):
        plan = validate_plan(plan)
        total_frames = int(plan["total_frames"])
        trim_frames = int(plan["trim_frames"])
        if not torch.is_tensor(images) or images.ndim != 4:
            raise ValueError("IMAGE input must be [frames,H,W,C]")
        if images.shape[0] < total_frames:
            raise ValueError(
                f"decoded batch has {images.shape[0]} frames; expected at least {total_frames}"
            )
        trimmed_images = images[:total_frames][trim_frames:].contiguous()
        trimmed_audio = _trim_audio(
            audio, trim_frames=trim_frames, output_frames=int(trimmed_images.shape[0])
        )
        state = capture_state(
            samples,
            source_frame_count=total_frames,
            clip_index=int(plan["clip_index"]),
            capacity_frames=int(plan["state_capacity_frames"]),
        )
        report = (
            f"Clip {plan['clip_index']} finished: {trimmed_images.shape[0]} retained frames "
            f"({trimmed_images.shape[0]/24.0:.3f}s); next-state capacity "
            f"{plan['state_capacity_frames']} frames; "
            f"audio samples {trimmed_audio['waveform'].shape[-1]}."
        )
        return trimmed_images, trimmed_audio, state, report


class H3ContinuumAssemble:
    DESCRIPTION = (
        "Append two already-trimmed Continuum segments while preserving exact audio sample order."
    )
    SEARCH_ALIASES = ["H3 concatenate", "H3 join clips", "H3 append"]

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "previous_images": ("IMAGE",),
                "previous_audio": ("AUDIO",),
                "next_images": ("IMAGE",),
                "next_audio": ("AUDIO",),
            }
        }

    RETURN_TYPES = ("IMAGE", "AUDIO", "STRING")
    RETURN_NAMES = ("images", "audio", "report")
    FUNCTION = "assemble"
    CATEGORY = CATEGORY

    def assemble(self, previous_images, previous_audio, next_images, next_audio):
        return assemble_segments(previous_images, previous_audio, next_images, next_audio)


class H3ContinuumSaveState:
    DESCRIPTION = "Atomically save a Continuum state as safetensors + JSON."
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "state": ("H3_CONTINUUM_STATE",),
                "prefix": ("STRING", {"default": "h3_continuum"}),
                "slot": ("INT", {"default": 1, "min": 1, "max": 9999, "step": 1}),
            }
        }

    RETURN_TYPES = ("H3_CONTINUUM_STATE", "STRING")
    RETURN_NAMES = ("state", "path")
    FUNCTION = "save"
    CATEGORY = CATEGORY

    def save(self, state, prefix, slot):
        tensor_path, _ = save_state(state, prefix=prefix, slot=slot)
        return state, str(tensor_path)


class H3ContinuumLoadState:
    DESCRIPTION = "Load an explicitly numbered Continuum state slot."

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prefix": ("STRING", {"default": "h3_continuum"}),
                "slot": ("INT", {"default": 1, "min": 1, "max": 9999, "step": 1}),
            }
        }

    RETURN_TYPES = ("H3_CONTINUUM_STATE", "STRING")
    RETURN_NAMES = ("state", "path")
    FUNCTION = "load"
    CATEGORY = CATEGORY

    @classmethod
    def IS_CHANGED(cls, prefix, slot):
        return state_mtime(prefix=prefix, slot=slot)

    def load(self, prefix, slot):
        state = load_state(prefix=prefix, slot=slot)
        tensor_path, _ = state_paths(prefix, slot)
        return state, str(tensor_path)


NODE_CLASS_MAPPINGS = {
    "H3ContinuumJoin": H3ContinuumJoin,
    "H3ContinuumFinish": H3ContinuumFinish,
    "H3ContinuumAssemble": H3ContinuumAssemble,
    "H3ContinuumSaveState": H3ContinuumSaveState,
    "H3ContinuumLoadState": H3ContinuumLoadState,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "H3ContinuumJoin": "H3 Continuum Join",
    "H3ContinuumFinish": "H3 Continuum Finish",
    "H3ContinuumAssemble": "H3 Continuum Assemble",
    "H3ContinuumSaveState": "H3 Continuum Save State",
    "H3ContinuumLoadState": "H3 Continuum Load State",
}

# V2 is an orchestration layer over the same V1 continuation core. Keeping the
# mapping merge here preserves every V1 workflow and node identifier.
from .v2.nodes import (
    NODE_CLASS_MAPPINGS as V2_NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS as V2_NODE_DISPLAY_NAME_MAPPINGS,
)

NODE_CLASS_MAPPINGS.update(V2_NODE_CLASS_MAPPINGS)
NODE_DISPLAY_NAME_MAPPINGS.update(V2_NODE_DISPLAY_NAME_MAPPINGS)

# V3 keeps the V1/V2 sampling and state contracts but exposes raw AV chunks so
# ComfyUI Core owns video/audio VAE decoding.
from .v3.nodes import (
    NODE_CLASS_MAPPINGS as V3_NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS as V3_NODE_DISPLAY_NAME_MAPPINGS,
)

NODE_CLASS_MAPPINGS.update(V3_NODE_CLASS_MAPPINGS)
NODE_DISPLAY_NAME_MAPPINGS.update(V3_NODE_DISPLAY_NAME_MAPPINGS)

from .v3.driving_nodes import (
    NODE_CLASS_MAPPINGS as V34_NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS as V34_NODE_DISPLAY_NAME_MAPPINGS,
)

NODE_CLASS_MAPPINGS.update(V34_NODE_CLASS_MAPPINGS)
NODE_DISPLAY_NAME_MAPPINGS.update(V34_NODE_DISPLAY_NAME_MAPPINGS)

# The stable facade and its pack helpers are the public workflow surface. Keep
# every older identifier registered so saved workflows still load, while
# ComfyUI's native deprecated-node filter hides legacy building blocks.
_primary_node_ids = {
    "H3ContinuumSamplerV34",
    "H3ContinuumAssembleSeamV34",
    "H3ContinuumClipOverrides",
    "H3ContinuumResult",
}
for _node_id, _node_class in NODE_CLASS_MAPPINGS.items():
    if _node_id in _primary_node_ids:
        continue
    _node_class.DEPRECATED = True
    _node_class.CATEGORY = f"{CATEGORY}/Legacy"
    _display_name = NODE_DISPLAY_NAME_MAPPINGS.get(_node_id, _node_id)
    if not _display_name.startswith("[Legacy]"):
        NODE_DISPLAY_NAME_MAPPINGS[_node_id] = f"[Legacy] {_display_name}"
