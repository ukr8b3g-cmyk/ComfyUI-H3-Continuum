import torch

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


def test_session_roundtrip_and_last_state(tmp_path, monkeypatch):
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
    assert tensor_path.exists() and json_path.exists()
    loaded = session_io.load_session(prefix="test", slot=1)
    assert torch.equal(loaded["chunks"][0]["video"], session["chunks"][0]["video"])
    assert loaded["session_id"] == session["session_id"]
