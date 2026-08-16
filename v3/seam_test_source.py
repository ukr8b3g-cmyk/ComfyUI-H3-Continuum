"""Deterministic decoded-chunk source for video seam validation."""

from __future__ import annotations

import math
from typing import Any

import torch
import torch.nn.functional as F

from ..hardening import enrich_assembly_plan
from .plan import (
    ASSEMBLY_PLAN_MAGIC,
    ASSEMBLY_PLAN_SCHEMA_VERSION,
    FPS,
    validate_assembly_plan,
)


TEST_SIZE_256 = "256 px (Fast)"
TEST_SIZE_512 = "512 px"
TEST_SIZE_INPUT = "Input Size"
TEST_SIZE_OPTIONS = (TEST_SIZE_256, TEST_SIZE_512, TEST_SIZE_INPUT)


def _prepare_image(image: Any, size_mode: str) -> torch.Tensor:
    if not torch.is_tensor(image) or image.ndim != 4 or int(image.shape[-1]) < 3:
        raise ValueError("image must be an IMAGE tensor [B,H,W,C]")
    if int(image.shape[0]) != 1:
        raise ValueError("Seam Test Source requires exactly one input image")

    frame = image[0, ..., :3].detach().to(device="cpu", dtype=torch.float32)
    if not bool(torch.isfinite(frame).all().item()):
        raise ValueError("input image contains NaN or Inf")
    frame = frame.clamp(0.0, 1.0)
    if size_mode == TEST_SIZE_INPUT:
        return frame.contiguous()

    limits = {TEST_SIZE_256: 256, TEST_SIZE_512: 512}
    if size_mode not in limits:
        raise ValueError(f"unknown Test Resolution: {size_mode!r}")
    height, width = int(frame.shape[0]), int(frame.shape[1])
    scale = min(1.0, float(limits[size_mode]) / float(max(height, width)))
    target_height = max(1, int(round(height * scale)))
    target_width = max(1, int(round(width * scale)))
    if (target_height, target_width) == (height, width):
        return frame.contiguous()
    resized = F.interpolate(
        frame.permute(2, 0, 1).unsqueeze(0),
        size=(target_height, target_width),
        mode="bilinear",
        align_corners=False,
    )
    return resized[0].permute(1, 2, 0).contiguous()


def _repeat_frame(frame: torch.Tensor, count: int) -> torch.Tensor:
    return frame.unsqueeze(0).expand(int(count), -1, -1, -1).clone()


def _ramp_chunk(
    previous_anchor: torch.Tensor,
    *,
    context_frames: int,
    net_frames: int,
    exposure_change: float,
) -> tuple[torch.Tensor, torch.Tensor]:
    context = _repeat_frame(previous_anchor, context_frames)
    ramp_count = 5
    ramp_factors = torch.linspace(
        1.0 - exposure_change,
        1.0 - exposure_change * 2.0,
        steps=ramp_count,
        dtype=torch.float32,
    )
    ramp = (
        previous_anchor.unsqueeze(0)
        * ramp_factors.reshape(-1, 1, 1, 1)
    ).clamp(0.0, 1.0)
    next_anchor = ramp[-1].contiguous()
    tail = _repeat_frame(next_anchor, net_frames - ramp_count)
    return torch.cat((context, ramp, tail), dim=0).contiguous(), next_anchor


def _silent_audio(total_frames: int, sample_rate: int) -> dict[str, Any]:
    samples = int(math.ceil(total_frames / FPS * sample_rate)) + 8
    return {
        "waveform": torch.zeros((1, 2, samples), dtype=torch.float32),
        "sample_rate": int(sample_rate),
    }


def _assembly_plan(width: int, height: int) -> dict[str, Any]:
    chunks = [
        {
            "sequence_index": 1,
            "chunk_index": 1,
            "total_frames": 124,
            "trim_frames": 0,
            "net_frames": 124,
            "context_frames": 0,
            "expected_video_latent_t": 32,
            "expected_audio_latent_t": 207,
        },
        {
            "sequence_index": 2,
            "chunk_index": 2,
            "total_frames": 141,
            "trim_frames": 22,
            "net_frames": 119,
            "context_frames": 22,
            "expected_video_latent_t": 36,
            "expected_audio_latent_t": 235,
        },
        {
            "sequence_index": 3,
            "chunk_index": 3,
            "total_frames": 141,
            "trim_frames": 22,
            "net_frames": 119,
            "context_frames": 22,
            "expected_video_latent_t": 36,
            "expected_audio_latent_t": 235,
        },
    ]
    plan = {
        "magic": ASSEMBLY_PLAN_MAGIC,
        "schema_version": ASSEMBLY_PLAN_SCHEMA_VERSION,
        "fps": FPS,
        "width": int(width),
        "height": int(height),
        "chunk_seconds": 5.0,
        "target_frames": 360,
        "preserve_final_frame": True,
        "chunks": chunks,
    }
    enrich_assembly_plan(plan)
    return validate_assembly_plan(plan)


class H3ContinuumSeamTestSource:
    DESCRIPTION = (
        "Create deterministic decoded chunks for testing Video Seam modes. "
        "Chunk 2 and Chunk 3 each begin with a controlled exposure ramp. "
        "This node performs no H3 sampling."
    )
    SEARCH_ALIASES = ["H3 seam test", "H3 exposure ramp test"]

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "exposure_change": (
                    "FLOAT",
                    {
                        "default": 0.08,
                        "min": 0.01,
                        "max": 0.20,
                        "step": 0.01,
                        "display_name": "Exposure Change",
                        "tooltip": (
                            "8% is the controlled default. Each new chunk ramps "
                            "from one step darker to two steps darker."
                        ),
                    },
                ),
                "test_resolution": (
                    TEST_SIZE_OPTIONS,
                    {
                        "default": TEST_SIZE_256,
                        "display_name": "Test Resolution",
                        "tooltip": (
                            "256 px is recommended for fast seam testing. "
                            "Input Size can require several GiB of RAM."
                        ),
                    },
                ),
            }
        }

    RETURN_TYPES = (
        "IMAGE",
        "AUDIO",
        "H3_CONTINUUM_ASSEMBLY_PLAN",
        "STRING",
    )
    RETURN_NAMES = ("images", "audio", "assembly_plan", "instructions")
    OUTPUT_IS_LIST = (True, True, False, False)
    FUNCTION = "create"
    CATEGORY = "MiniMax H3/Continuum/Testing"
    EXPERIMENTAL = True

    def create(
        self,
        image,
        exposure_change=0.08,
        test_resolution=TEST_SIZE_256,
    ):
        change = float(exposure_change)
        if not math.isfinite(change) or not 0.01 <= change <= 0.20:
            raise ValueError("Exposure Change must be between 0.01 and 0.20")
        base = _prepare_image(image, str(test_resolution))
        chunk_1 = _repeat_frame(base, 124)
        chunk_2, anchor_2 = _ramp_chunk(
            base,
            context_frames=22,
            net_frames=119,
            exposure_change=change,
        )
        chunk_3, _anchor_3 = _ramp_chunk(
            anchor_2,
            context_frames=22,
            net_frames=119,
            exposure_change=change,
        )
        images = [chunk_1, chunk_2, chunk_3]
        audio = [
            _silent_audio(124, 32000),
            _silent_audio(141, 32000),
            _silent_audio(141, 32000),
        ]
        plan = _assembly_plan(int(base.shape[1]), int(base.shape[0]))
        instructions = (
            "H3 Continuum Seam Test Source\n"
            "1. Connect images, audio, and assembly_plan to the matching inputs "
            "of H3 Continuum Assemble + Seam.\n"
            "2. Set Audio Seam=Off and exact_total_duration=true.\n"
            "3. Run Video Seam=Analyze Only, then Auto, then Auto 2.\n"
            "4. Analyze Only should report class=exposure_ramp at both boundaries.\n"
            "5. Auto should keep both native boundaries. Auto 2 should report "
            "normalized exposure/color on 4 exposure ramp boundary frame(s).\n"
            f"Source: 3 x 5 sec, 24 fps, {base.shape[1]}x{base.shape[0]}, "
            f"exposure change={change:.0%}."
        )
        return images, audio, plan, instructions
