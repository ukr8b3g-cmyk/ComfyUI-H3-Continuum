import torch

from ComfyUI_H3_Continuum_Join.constants import PLAN_MAGIC
from ComfyUI_H3_Continuum_Join.state import (
    capture_state,
    select_context,
    validate_plan,
    validate_state,
)


class FakeNested:
    def __init__(self, parts):
        self.parts = parts

    def unbind(self):
        return tuple(self.parts)


def _latent():
    return {
        "samples": FakeNested(
            (
                torch.randn(1, 24, 37, 4, 6),
                torch.randn(1, 32, 2, 207),
            )
        )
    }


def test_capture_and_select():
    state = capture_state(_latent(), source_frame_count=124, clip_index=1)
    validate_state(state)
    assert state["video_tail"].shape == (1, 24, 12, 4, 6)
    assert state["audio_tail"].shape == (1, 32, 2, 65)
    video, audio, grid_offset = select_context(state, 22, include_audio=True)
    assert video.shape[2] == 7
    assert audio.shape[-1] == 37
    assert abs(grid_offset - 1.0 / 3.0) < 1e-6


def test_plan_validation():
    plan = {
        "magic": PLAN_MAGIC,
        "schema_version": 1,
        "total_frames": 141,
        "trim_frames": 22,
        "net_frames": 119,
        "width": 1344,
        "height": 768,
        "clip_index": 2,
        "continuation": True,
        "state_capacity_frames": 39,
    }
    assert validate_plan(plan) is plan


def test_signed_audio_grid_offset_is_preserved_for_round_down_lengths():
    latent = {
        "samples": FakeNested(
            (
                torch.randn(1, 24, 47, 4, 6),  # 158 frames
                torch.randn(1, 32, 2, 263),
            )
        )
    }
    state = capture_state(latent, source_frame_count=158, clip_index=2)
    assert abs(state["audio_overhang"] + 1.0 / 3.0) < 1e-6
    validate_state(state)
