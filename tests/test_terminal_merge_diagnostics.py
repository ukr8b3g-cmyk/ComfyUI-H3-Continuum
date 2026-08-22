from __future__ import annotations

from types import SimpleNamespace

import torch

from ComfyUI_H3_Continuum_Join.v2.sequence import (
    _split_terminal_merged_latents,
    _terminal_pair_contract,
)
from ComfyUI_H3_Continuum_Join.tests.terminal_merge_diagnostics import (
    DiagnosticCapture,
    first_divergent_stage,
    tensor_difference,
    tensor_fingerprint,
)


def _capture_all_stages(*, sampled_offset: float = 0.0) -> DiagnosticCapture:
    capture = DiagnosticCapture()
    capture.capture_pre_sampler(
        physical_frames=243,
        seed=42,
        conditioning=[[torch.tensor([1.0]), {"minimax_frame_count": 243}]],
        latent={"video": torch.zeros(1, 24, 72, 2, 2)},
        noise=torch.arange(8, dtype=torch.float32),
        keyframes=(0, 242),
        qwen_images=("first", "last"),
        minimax_refs=None,
    )
    layout = SimpleNamespace(
        signature=(1, 2, 3),
        segments=(("target_video", 0, 72),),
        position_ids=torch.arange(12, dtype=torch.float32).reshape(6, 2),
    )
    capture.capture_first_model_call(
        minimax_payload={
            "layout": layout,
            "cond_video_latents": torch.ones(1, 24, 2, 2, 2),
            "target_video_shape": (1, 24, 72, 2, 2),
            "target_audio_shape": (1, 32, 2, 405),
        },
        transformer_options={"patches": {}},
    )
    video = torch.full((1, 24, 72, 2, 2), sampled_offset)
    audio = torch.zeros(1, 32, 2, 405)
    capture.capture_sampled_physical_av(video=video, audio=audio)
    capture.capture_split_recombine(
        physical_video=video,
        physical_audio=audio,
        recombined_video=video.clone(),
        recombined_audio=audio.clone(),
    )
    decoded = torch.zeros(243, 2, 2, 3)
    capture.capture_decode_assembly(
        physical_decoded=decoded,
        assembled_decoded=decoded.clone(),
    )
    return capture


def test_tensor_fingerprint_is_deterministic_and_dtype_sensitive():
    value = torch.arange(12, dtype=torch.float32).reshape(3, 4)
    first = tensor_fingerprint(value)
    second = tensor_fingerprint(value.clone())

    assert first == second
    assert first.shape == (3, 4)
    assert first.dtype == "torch.float32"
    assert first.sha256 != tensor_fingerprint(value.to(torch.float64)).sha256


def test_tensor_difference_keeps_hash_mismatch_distinct_from_allclose():
    core = torch.tensor([1.0], dtype=torch.float32)
    continuum = torch.tensor([1.0 + 1.0e-7], dtype=torch.float32)

    difference = tensor_difference(core, continuum)

    assert difference.bit_exact is False
    assert difference.allclose is True
    assert difference.max_abs_diff is not None
    assert difference.max_abs_diff > 0.0
    assert difference.mean_abs_diff == difference.max_abs_diff


def test_pre_sampler_capture_includes_initial_noise():
    core = _capture_all_stages()
    continuum = _capture_all_stages()
    assert first_divergent_stage(core, continuum) is None

    changed = DiagnosticCapture()
    changed.capture_pre_sampler(
        physical_frames=243,
        seed=42,
        conditioning=[[torch.tensor([1.0]), {"minimax_frame_count": 243}]],
        latent={"video": torch.zeros(1, 24, 72, 2, 2)},
        noise=torch.arange(8, dtype=torch.float32) + 1.0,
        keyframes=(0, 242),
        qwen_images=("first", "last"),
        minimax_refs=None,
    )

    assert first_divergent_stage(core, changed) == "A_pre_sampler"


def test_first_model_call_capture_detects_packed_layout_difference():
    core = DiagnosticCapture()
    continuum = DiagnosticCapture()
    shared = dict(
        physical_frames=243,
        seed=42,
        conditioning=[torch.zeros(1)],
        latent=torch.zeros(1),
        noise=torch.zeros(1),
    )
    core.capture_pre_sampler(**shared)
    continuum.capture_pre_sampler(**shared)

    core_layout = SimpleNamespace(
        signature=(1, 2),
        segments=(("target_video", 0, 72),),
        position_ids=torch.zeros(4, 2),
    )
    continuum_layout = SimpleNamespace(
        signature=(1, 2),
        segments=(("target_video", 0, 72),),
        position_ids=torch.ones(4, 2),
    )
    core.capture_first_model_call(
        minimax_payload={"layout": core_layout},
        transformer_options={},
    )
    continuum.capture_first_model_call(
        minimax_payload={"layout": continuum_layout},
        transformer_options={},
    )

    assert first_divergent_stage(core, continuum) == "B_first_model_call"


def test_first_divergent_stage_uses_pipeline_order():
    core = _capture_all_stages(sampled_offset=0.0)
    continuum = _capture_all_stages(sampled_offset=1.0)

    assert first_divergent_stage(core, continuum) == "C_sampled_physical_av"


def test_terminal_split_recombine_is_bit_exact():
    contract = _terminal_pair_contract(initial_pair=True, chunk_seconds=5.0)
    video = torch.arange(
        1 * 24 * contract["video_slices"][-1][1] * 2 * 2,
        dtype=torch.float32,
    ).reshape(1, 24, contract["video_slices"][-1][1], 2, 2)
    audio = torch.arange(
        1 * 32 * 2 * contract["audio_slices"][-1][1],
        dtype=torch.float32,
    ).reshape(1, 32, 2, contract["audio_slices"][-1][1])

    (video_1, audio_1), (video_2, audio_2) = _split_terminal_merged_latents(
        video,
        audio,
        contract,
    )
    video_overlap = contract["video_slices"][0][1] - contract["video_slices"][1][0]
    audio_overlap = contract["audio_slices"][0][1] - contract["audio_slices"][1][0]
    recombined_video = torch.cat((video_1, video_2[:, :, video_overlap:]), dim=2)
    recombined_audio = torch.cat((audio_1, audio_2[..., audio_overlap:]), dim=-1)

    assert contract["physical_frames"] == 243
    assert contract["logical_frames"] == (124, 141)
    assert torch.equal(recombined_video, video)
    assert torch.equal(recombined_audio, audio)
    assert tensor_difference(video, recombined_video).bit_exact is True
    assert tensor_difference(audio, recombined_audio).bit_exact is True

    capture = DiagnosticCapture()
    stage = capture.capture_split_recombine(
        physical_video=video,
        physical_audio=audio,
        recombined_video=recombined_video,
        recombined_audio=recombined_audio,
    )
    assert stage.name == "D_split_recombine"
