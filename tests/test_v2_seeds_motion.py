import torch

from ComfyUI_H3_Continuum_Join.constants import (
    STATE_MAGIC,
    V2_CONTINUITY_AUTO,
)
from ComfyUI_H3_Continuum_Join.v2.motion import choose_context_frames, latent_motion_score
from ComfyUI_H3_Continuum_Join.v2.seeds import derive_chunk_seed


def _state(video):
    return {
        "magic": STATE_MAGIC,
        "schema_version": 1,
        "clip_index": 1,
        "source_frame_count": 124,
        "capacity_frames": 39,
        "width": 96,
        "height": 64,
        "video_tail": video,
        "audio_tail": torch.zeros(1, 32, 2, 65),
        "audio_overhang": 1.0 / 3.0,
        "source_mode": "latent_direct",
    }


def test_chunk_seeds_are_stable_and_independent():
    values = [derive_chunk_seed(123, i, 0) for i in range(4)]
    assert values == [derive_chunk_seed(123, i, 0) for i in range(4)]
    assert len(set(values)) == 4
    rerolled = [derive_chunk_seed(123, i, 1) for i in range(4)]
    assert values != rerolled


def test_auto_context_selects_static_and_dynamic_profiles():
    static_state = _state(torch.ones(1, 24, 12, 4, 6))
    assert latent_motion_score(static_state) == 0.0
    frames, _score, _reason = choose_context_frames(V2_CONTINUITY_AUTO, static_state)
    assert frames == 5

    dynamic = torch.zeros(1, 24, 12, 4, 6)
    dynamic[:, :, 1::2] = 10
    dynamic_state = _state(dynamic)
    frames, score, _reason = choose_context_frames(V2_CONTINUITY_AUTO, dynamic_state)
    assert score > 0.12
    assert frames == 39
