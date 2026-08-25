from __future__ import annotations

import hashlib

import pytest
import torch

from ComfyUI_H3_Continuum_Join import reference_video


def _legacy_v3_hash(value: torch.Tensor) -> str:
    normalized = value[:, :, :, :3].detach().to(
        device="cpu", dtype=torch.float32
    ).contiguous()
    digest = hashlib.sha256()
    digest.update(str(tuple(int(item) for item in normalized.shape)).encode("ascii"))
    digest.update(str(normalized.dtype).encode("ascii"))
    digest.update(normalized.numpy().tobytes(order="C"))
    return digest.hexdigest()


def _source(value: torch.Tensor, *, target_frames: int = 22):
    return reference_video.prepare_reference_video_source(
        value,
        target_frames=target_frames,
        output_width=32,
        output_height=32,
    )


def test_chunked_source_hash_is_exactly_legacy_v3_for_full_normalized_input():
    torch.manual_seed(4601)
    value = torch.rand((43, 32, 48, 4), dtype=torch.float64)

    source = _source(value)

    assert source.source_sha256 == _legacy_v3_hash(value)
    assert source.source_shape == (43, 32, 48, 3)
    assert source.source_dtype == "torch.float32"
    assert source.contract["preprocess_version"] == 3


def test_only_used_prefix_storage_is_retained_but_full_tail_remains_in_identity():
    torch.manual_seed(4602)
    value = torch.rand((80, 32, 32, 3), dtype=torch.float32)
    changed_tail = value.clone()
    changed_tail[-1, 0, 0, 0] += 0.25

    original = _source(value)
    changed = _source(changed_tail)

    assert original.frame_count == 22
    assert original.frames.shape == (22, 32, 32, 3)
    assert original.frames.untyped_storage().nbytes() == original.frames.numel() * 4
    assert torch.equal(original.frames, value[:22])
    assert torch.equal(original.frames, changed.frames)
    assert original.source_sha256 != changed.source_sha256
    assert original.combined_hash != changed.combined_hash
    assert reference_video.combine_reference_video_identity("visual", original) != (
        reference_video.combine_reference_video_identity("visual", changed)
    )


def test_nonfinite_value_in_unused_tail_is_still_rejected():
    value = torch.zeros((80, 32, 32, 3), dtype=torch.float32)
    value[-1, 0, 0, 0] = torch.nan

    with pytest.raises(reference_video.ReferenceVideoError, match="NaN or infinity"):
        _source(value)


def test_short_source_keeps_v3_alignment_and_final_frame_padding_contract():
    value = torch.arange(6 * 32 * 32 * 3, dtype=torch.float32).reshape(
        6, 32, 32, 3
    )
    source = _source(value, target_frames=124)
    captured = {}

    class VideoVAE:
        def encode(self, frames):
            captured["frames"] = frames.clone()
            return torch.zeros((1, 24, 7, 2, 2), dtype=torch.float32)

    assets = reference_video.encode_reference_video(VideoVAE(), source)

    assert source.frame_count == 22
    assert source.frames.shape[0] == 6
    assert captured["frames"].shape == (22, 32, 32, 3)
    assert torch.equal(captured["frames"][:6], value)
    assert torch.equal(
        captured["frames"][6:], value[-1:].expand(16, -1, -1, -1)
    )
    assert assets.block["latent_t"] == 7


def test_chunked_tensor_hash_matches_legacy_byte_order():
    torch.manual_seed(4603)
    value = torch.rand((19, 7, 9, 3), dtype=torch.float32)

    assert reference_video._tensor_hash(value) == _legacy_v3_hash(value)
