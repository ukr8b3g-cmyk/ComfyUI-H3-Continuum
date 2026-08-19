import pytest

from ComfyUI_H3_Continuum_Join.temporal import (
    align_frame_count_nearest,
    align_frame_count_up,
    audio_grid_offset,
    audio_latent_t,
    context_slots,
    latent_slot_offsets,
    largest_context_capacity,
    make_av_context_window,
    make_extension_shape,
    make_extension_shape_at_least,
    pixel_frames_for_latent_t,
    video_latent_t,
)


def test_context_presets():
    assert context_slots(5) == 2
    assert context_slots(22) == 7
    assert context_slots(39) == 12
    assert latent_slot_offsets(7) == (0, 1, 5, 9, 13, 17, 18)


def test_valid_h3_counts():
    assert video_latent_t(124) == 37
    assert pixel_frames_for_latent_t(37) == 124
    assert audio_latent_t(124) == 207


def test_balanced_five_second_extension():
    shape = make_extension_shape(22, 5.0)
    assert shape.total_frames == 141
    assert shape.net_new_frames == 119
    assert shape.video_latent_t == 42
    assert shape.audio_latent_t == 235


def test_nearest_grid_choice():
    assert align_frame_count_nearest(13) == 5
    assert align_frame_count_nearest(14) == 22


def test_minimum_extension_rounds_up_instead_of_undershooting():
    shape = make_extension_shape_at_least(22, 161)
    assert shape.total_frames == 192
    assert shape.net_new_frames == 170
    assert shape.net_new_frames >= shape.requested_new_frames
    assert shape.net_new_frames - shape.requested_new_frames < 17


def test_minimum_extension_never_undershoots_across_ui_range():
    for context in (5, 22, 39):
        for requested_new_frames in range(1, 15 * 24 + 1):
            shape = make_extension_shape_at_least(context, requested_new_frames)
            assert shape.total_frames % 17 == 5
            assert shape.net_new_frames >= requested_new_frames
            assert shape.net_new_frames - requested_new_frames < 17
            assert pixel_frames_for_latent_t(shape.video_latent_t) == shape.total_frames


def test_two_seven_second_chunks_generate_surplus_instead_of_frozen_tail_padding():
    target_per_chunk = round(7.0 * 24)
    target_total = 2 * target_per_chunk
    first_frames = align_frame_count_up(target_per_chunk)
    requested_second = target_total - first_frames
    second = make_extension_shape_at_least(22, requested_second)
    natural_frames = first_frames + second.net_new_frames

    assert first_frames == 175
    assert requested_second == 161
    assert second.total_frames == 192
    assert second.net_new_frames == 170
    assert natural_frames == 345
    assert natural_frames >= target_total


def test_audio_grid_offset_is_signed_and_bounded_on_valid_h3_lengths():
    offsets = []
    for k in range(0, 32):
        frames = 5 + 17 * k
        offsets.append(audio_grid_offset(frames, audio_latent_t(frames)))
    assert all(-0.500001 <= value <= 0.500001 for value in offsets)
    assert any(value < 0 for value in offsets)
    assert any(value > 0 for value in offsets)


def test_native_context_window_uses_source_av_grid_and_cycle_phase():
    balanced = make_av_context_window(141, audio_latent_t(141), 22)
    assert (balanced.video_start_slot, balanced.video_stop_slot) == (35, 42)
    assert (balanced.audio_start_tick, balanced.audio_stop_tick) == (198, 235)
    assert balanced.audio_steps == 37

    shifted = make_av_context_window(158, audio_latent_t(158), 22)
    assert (shifted.video_start_slot, shifted.video_stop_slot) == (40, 47)
    assert (shifted.audio_start_tick, shifted.audio_stop_tick) == (226, 263)
    assert shifted.audio_grid_offset < 0


def test_native_context_window_rejects_unknown_audio_grid_phase():
    with pytest.raises(ValueError, match="audio-grid offset"):
        make_av_context_window(141, audio_latent_t(141) + 2, 22)


def test_dynamic_state_capacity_for_short_extensions():
    assert largest_context_capacity(119) == 39
    assert largest_context_capacity(34) == 22
    assert largest_context_capacity(17) == 5


def test_extension_shapes_remain_valid_across_ui_range():
    for context in (5, 22, 39):
        for tenths in range(5, 151):
            shape = make_extension_shape(context, tenths / 10.0)
            assert shape.total_frames % 17 == 5
            assert shape.net_new_frames >= 5
            assert pixel_frames_for_latent_t(shape.video_latent_t) == shape.total_frames
