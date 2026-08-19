from __future__ import annotations

import torch

from ComfyUI_H3_Continuum_Join.constants import (
    CONTINUUM_INTEROP_API,
    CONTINUUM_REFERENCE_AUDIO_ROLE_AUDIO_CONTEXT,
    CONTINUUM_REFERENCE_METADATA_KEY,
    CONTINUUM_REFERENCE_PRESERVE_ROPE_KEY,
    CONTINUUM_REFERENCE_ROLE_VIDEO_CONTEXT,
)
from ComfyUI_H3_Continuum_Join.continuation import POLICY_REPLACE, prepare_conditioning


def test_continuation_reference_publishes_stable_external_patch_metadata():
    conditioning = [
        [
            torch.zeros((1, 4, 8)),
            {
                "minimax_refs": [
                    {
                        "kind": "image",
                        "latent_h": 4,
                        "latent_w": 4,
                    }
                ]
            },
        ]
    ]
    video_context = torch.zeros((1, 24, 2, 4, 4))
    audio_context = torch.zeros((1, 32, 2, 8))

    prepared = prepare_conditioning(
        conditioning,
        video_context=video_context,
        audio_context=audio_context,
        audio_grid_offset=0.0,
        context_frames=5,
        new_frame_count=121,
        first_frame_policy=POLICY_REPLACE,
        preserve_last_frame=False,
    )

    refs = prepared[0][1]["minimax_refs"]
    assert len(refs) == 2
    assert refs[0]["kind"] == "image"

    continuation_ref = refs[1]
    assert continuation_ref["kind"] == "video_audio"
    metadata = continuation_ref[CONTINUUM_REFERENCE_METADATA_KEY]
    assert metadata == {
        "api": CONTINUUM_INTEROP_API,
        "role": CONTINUUM_REFERENCE_ROLE_VIDEO_CONTEXT,
        "audio_role": CONTINUUM_REFERENCE_AUDIO_ROLE_AUDIO_CONTEXT,
        CONTINUUM_REFERENCE_PRESERVE_ROPE_KEY: True,
    }


def test_video_only_continuation_still_marks_rope_preservation():
    prepared = prepare_conditioning(
        [[torch.zeros((1, 2, 4)), {}]],
        video_context=torch.zeros((1, 24, 1, 4, 4)),
        audio_context=None,
        audio_grid_offset=0.0,
        context_frames=1,
        new_frame_count=25,
        first_frame_policy=POLICY_REPLACE,
        preserve_last_frame=False,
    )

    ref = prepared[0][1]["minimax_refs"][0]
    metadata = ref[CONTINUUM_REFERENCE_METADATA_KEY]
    assert ref["kind"] == "video"
    assert metadata["api"] == CONTINUUM_INTEROP_API
    assert metadata["role"] == CONTINUUM_REFERENCE_ROLE_VIDEO_CONTEXT
    assert metadata["audio_role"] is None
    assert metadata[CONTINUUM_REFERENCE_PRESERVE_ROPE_KEY] is True


def test_reference_kinds_remain_distinct_for_downstream_minimax_payload():
    """Continuum must not collapse image/video/video_audio into one visual label."""
    conditioning = [
        [
            torch.zeros((1, 4, 8)),
            {
                "minimax_refs": [
                    {"kind": "image", "latent_h": 4, "latent_w": 4},
                    {
                        "kind": "video",
                        "latent_t": 1,
                        "latent_h": 4,
                        "latent_w": 4,
                        "latent": torch.zeros((1, 24, 1, 4, 4)),
                    },
                ]
            },
        ]
    ]

    prepared = prepare_conditioning(
        conditioning,
        video_context=torch.zeros((1, 24, 2, 4, 4)),
        audio_context=torch.zeros((1, 32, 2, 8)),
        audio_grid_offset=0.0,
        context_frames=5,
        new_frame_count=121,
        first_frame_policy=POLICY_REPLACE,
        preserve_last_frame=False,
    )

    refs = prepared[0][1]["minimax_refs"]
    assert [ref["kind"] for ref in refs] == ["image", "video", "video_audio"]
    assert refs[0] is not conditioning[0][1]["minimax_refs"][0]
    assert refs[1] is not conditioning[0][1]["minimax_refs"][1]
    assert refs[2][CONTINUUM_REFERENCE_METADATA_KEY][CONTINUUM_REFERENCE_PRESERVE_ROPE_KEY] is True
