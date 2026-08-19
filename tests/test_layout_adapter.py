from types import SimpleNamespace

import torch

from ComfyUI_H3_Continuum_Join.constants import (
    MARK_AUDIO_CONTEXT,
    MARK_AUDIO_END_FRAME,
    MARK_AUDIO_OVERHANG,
    MARK_CONTEXT_FRAMES,
    MARK_VIDEO_CONTEXT,
)
from ComfyUI_H3_Continuum_Join.layout_adapter import (
    normalize_condition_latents,
    patch_layout_in_place,
)


def _video_times(origin: float):
    offsets = (0, 1, 5, 9, 13, 17, 18)
    return [origin + value * 5.0 / 3.0 for value in offsets]


def _fake_layout(*, with_last_keyframe=False):
    # text=3, optional one stock keyframe, a 22-frame video/audio context ref,
    # target audio=10 steps, target video=7 slots x 2 rows.
    row = 0
    segments = [(row, row + 3, "text")]
    row += 3
    if with_last_keyframe:
        segments.append((row, row + 2, "cond"))
        row += 2
    audio_ref = (row, row + 74)
    segments.append((*audio_ref, "ref_audio"))
    row += 74
    video_ref = (row, row + 14)
    segments.append((*video_ref, "ref_img"))
    row += 14
    target_audio = (row, row + 20)
    segments.append((*target_audio, "audio"))
    row += 20
    target_video = (row, row + 14)
    segments.append((*target_video, "video"))
    row += 14

    pos = torch.zeros(row, 3, dtype=torch.float64)
    pos[:3, 0] = torch.arange(3, dtype=torch.float64)
    if with_last_keyframe:
        # Stock last keyframe is text-relative before refs shift the target.
        pos[3:5, 0] = 3.0 + 35.0
    # Stock context ref lives in its own pre-target coordinate span.
    a0, a1 = audio_ref
    pos[a0 : a0 + 37, 0] = torch.arange(37, dtype=torch.float64) + 3.0
    pos[a0 + 37 : a1, 0] = torch.arange(37, dtype=torch.float64) + 3.0
    v0, _v1 = video_ref
    for slot, value in enumerate(_video_times(3.0)):
        pos[v0 + slot * 2 : v0 + (slot + 1) * 2, 0] = value
    # Target origin = text 3 + max(audio 37, video span 36 2/3) = 40.
    ta0, ta1 = target_audio
    pos[ta0 : ta0 + 10, 0] = torch.arange(10, dtype=torch.float64) + 40.0
    pos[ta0 + 10 : ta1, 0] = torch.arange(10, dtype=torch.float64) + 40.0
    tv0, _tv1 = target_video
    for slot, value in enumerate(_video_times(40.0)):
        pos[tv0 + slot * 2 : tv0 + (slot + 1) * 2, 0] = value
    # Give every target video row distinct h/w values so the full-coordinate
    # copy (not only time) is tested.
    pos[tv0 : tv0 + 14, 1] = torch.arange(14, dtype=torch.float64)
    pos[tv0 : tv0 + 14, 2] = torch.arange(14, dtype=torch.float64) + 100

    return SimpleNamespace(
        segments=segments,
        position_ids=pos,
        signature=(3, 7, 2, 2, 10),
    ), video_ref, target_video


def _context_ref(video, audio):
    return {
        "kind": "video_audio",
        "latent_t": 7,
        "latent_h": 2,
        "latent_w": 2,
        "ref_audio_t": 37,
        "latent": video,
        "audio_latent": audio,
        MARK_VIDEO_CONTEXT: True,
        MARK_CONTEXT_FRAMES: 22,
        MARK_AUDIO_CONTEXT: True,
        MARK_AUDIO_END_FRAME: 22.0,
        MARK_AUDIO_OVERHANG: 1.0 / 3.0,
    }


def test_layout_patches_video_audio_ref_in_place_and_is_idempotent():
    layout, video_ref_span, target_video_span = _fake_layout()
    tensor_id = id(layout.position_ids)
    video = torch.zeros(1, 24, 7, 2, 2)
    audio = torch.zeros(1, 32, 2, 37)
    payload = {"layout": layout, "keyframes": [], "refs": [_context_ref(video, audio)]}
    normalize_condition_latents(payload)
    result = patch_layout_in_place(payload)
    assert result["video_refs"] == 1
    assert result["audio_windows"] == 1
    assert id(layout.position_ids) == tensor_id

    rv0, rv1 = video_ref_span
    tv0, tv1 = target_video_span
    assert torch.equal(layout.position_ids[rv0:rv1], layout.position_ids[tv0:tv1])
    # 22 frames (36 2/3 audio steps) plus source overhang 1/3 = 37,
    # so the audio context begins exactly at target origin 40.
    audio_start = next(a for a, _b, kind in layout.segments if kind == "ref_audio")
    assert torch.isclose(
        layout.position_ids[audio_start, 0], torch.tensor(40.0, dtype=torch.float64)
    )

    before = layout.position_ids.clone()
    second = patch_layout_in_place(payload)
    assert second["status"] == "already_patched"
    assert torch.equal(before, layout.position_ids)
    assert payload["cond_video_latents"] == [video]
    assert payload["cond_audio_latents"] == [audio]


def test_existing_last_keyframe_is_shifted_with_context_ref():
    layout, _video_ref_span, target_video_span = _fake_layout(with_last_keyframe=True)
    target_origin = float(layout.position_ids[target_video_span[0], 0])
    image = torch.zeros(1, 24, 1, 2, 2)
    video = torch.zeros(1, 24, 7, 2, 2)
    audio = torch.zeros(1, 32, 2, 37)
    payload = {
        "layout": layout,
        "keyframes": [{"resolved_frame_index": 140, "latent": image}],
        "refs": [_context_ref(video, audio)],
    }
    normalize_condition_latents(payload)
    patch_layout_in_place(payload)
    cond_start = next(a for a, _b, kind in layout.segments if kind == "cond")
    expected = target_origin + 140.0 * 5.0 / 3.0
    assert torch.allclose(
        layout.position_ids[cond_start : cond_start + 2, 0],
        torch.full((2,), expected, dtype=torch.float64),
    )
    assert payload["cond_video_latents"] == [image, video]


def test_negative_audio_grid_offset_places_context_before_target_origin():
    layout, _video_ref_span, _target_video_span = _fake_layout()
    video = torch.zeros(1, 24, 7, 2, 2)
    audio = torch.zeros(1, 32, 2, 37)
    ref = _context_ref(video, audio)
    ref[MARK_AUDIO_OVERHANG] = -1.0 / 3.0
    payload = {"layout": layout, "keyframes": [], "refs": [ref]}
    normalize_condition_latents(payload)
    patch_layout_in_place(payload)
    audio_start = next(a for a, _b, kind in layout.segments if kind == "ref_audio")
    # target origin is 40; 22 frames = 36 2/3 audio steps, signed offset -1/3,
    # and the retained window is 37 steps, so it starts 2/3 step before origin.
    assert torch.isclose(
        layout.position_ids[audio_start, 0],
        torch.tensor(40.0 - 2.0 / 3.0, dtype=torch.float64),
    )
