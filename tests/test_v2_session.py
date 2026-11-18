import torch
import pytest
from safetensors.torch import load_file, save_file

from ComfyUI_H3_Continuum_Join.state import make_plan
from ComfyUI_H3_Continuum_Join.v2 import session_io
from ComfyUI_H3_Continuum_Join.v2.session import (
    entry_to_state,
    make_chunk_entry,
    make_session,
    validate_session,
)


def _latent(frame_count=124):
    import sys
    from types import ModuleType

    # The session entry accepts a ComfyUI-like object exposing unbind().
    class Nested:
        def __init__(self, parts):
            self.parts = parts
        def unbind(self):
            return self.parts

    video_t = 37 if frame_count == 124 else 42
    audio_t = 207 if frame_count == 124 else 235
    return {
        "samples": Nested(
            (
                torch.randn(1, 24, video_t, 4, 6),
                torch.randn(1, 32, 2, audio_t),
            )
        )
    }


@pytest.fixture
def saved_session(tmp_path, monkeypatch):
    plan = make_plan(
        continuation=False,
        clip_index=1,
        total_frames=124,
        trim_frames=0,
        width=96,
        height=64,
        context_frames=22,
        state_capacity_frames=39,
        requested_extend_seconds=5,
        debug=False,
    )
    entry = make_chunk_entry(
        latent=_latent(),
        plan=plan,
        prompt="p",
        prompt_hash="0" * 64,
        seed=1,
        context_frames=0,
        motion_score=0.0,
        reused=False,
    )
    session = make_session(
        chunks=[entry],
        width=96,
        height=64,
        chunk_seconds=5,
        identity_hash="none",
        model_fingerprint_value="f" * 64,
        parent_session_id=None,
        reroll_from_chunk=0,
        settings={},
    )
    validate_session(session)
    state = entry_to_state(session["chunks"][0])
    assert state["capacity_frames"] == 39

    monkeypatch.setattr(session_io, "session_directory", lambda: tmp_path)
    tensor_path, json_path = session_io.save_session(session, prefix="test", slot=1)
    return session, tensor_path, json_path


def test_session_roundtrip_and_last_state(saved_session):
    session, tensor_path, json_path = saved_session
    assert tensor_path.exists() and json_path.exists()
    loaded = session_io.load_session(prefix="test", slot=1)
    assert torch.equal(loaded["chunks"][0]["video"], session["chunks"][0]["video"])
    assert loaded["session_id"] == session["session_id"]


@pytest.mark.parametrize("sidecar", ["[]", "null", '"old"', "4", "false"])
def test_non_object_mirror_does_not_block_valid_session(saved_session, caplog, sidecar):
    session, tensor_path, json_path = saved_session
    json_path.write_text(sidecar, encoding="utf-8")
    before = (tensor_path.read_bytes(), json_path.read_bytes())
    loaded = session_io.load_session(prefix="test", slot=1)
    assert loaded["session_id"] == session["session_id"]
    for key in ("video", "audio"):
        assert torch.equal(loaded["chunks"][0][key], session["chunks"][0][key])
    assert "Ignoring unreadable" in caplog.text
    assert (tensor_path.read_bytes(), json_path.read_bytes()) == before


@pytest.mark.parametrize("header", [{}, {session_io._HEADER_KEY: "{broken"}])
def test_session_rejects_invalid_authority_even_with_valid_mirror(saved_session, header):
    _, tensor_path, json_path = saved_session
    original_mirror = json_path.read_bytes()
    tensors = {k: v.clone() for k, v in load_file(str(tensor_path)).items()}
    save_file(tensors, str(tensor_path), metadata=header)
    with pytest.raises(ValueError):
        session_io.load_session(prefix="test", slot=1)
    assert json_path.read_bytes() == original_mirror


def test_model_fingerprint_can_add_continuum_wrapper_without_mutating_model():
    from types import SimpleNamespace

    from ComfyUI_H3_Continuum_Join.v2.session import model_fingerprint

    base = SimpleNamespace(diffusion_model=object())
    model = SimpleNamespace(
        model=base,
        model_options={"transformer_options": {}},
        wrappers={},
        model_dtype=lambda: "float32",
        model_size=lambda: 1,
    )
    wrapped = SimpleNamespace(
        model=base,
        model_options={"transformer_options": {}},
        wrappers={
            "apply_model": {
                "h3_continuum_join.apply_model.v1": [object()],
            }
        },
        model_dtype=model.model_dtype,
        model_size=model.model_size,
    )

    logical = model_fingerprint(
        model,
        extra_wrapper_keys=("h3_continuum_join.apply_model.v1",),
    )

    assert logical == model_fingerprint(wrapped)
    assert model.wrappers == {}
