"""Stable non-UI API shared by V1 and the integrated V2 sampler.

External orchestration code should call these functions instead of importing node classes. The
schema/version constants allow saved workflows and state files to evolve
without binding a sampler implementation to the UI layer.
"""

from __future__ import annotations

from .continuation import (
    FIRST_FRAME_POLICIES,
    POLICY_ERROR,
    POLICY_KEEP,
    POLICY_REPLACE,
    conditioning_diagnostics,
    new_h3_latent,
    prepare_conditioning,
)
from .layout_adapter import normalize_condition_latents, patch_layout_in_place
from .media import assemble_segments, trim_audio
from .state import capture_state, select_context, validate_plan, validate_state
from .temporal import make_extension_shape
from .version import PUBLIC_API_VERSION
from .v2.motion import choose_context_frames, latent_motion_score
from .v2.prompts import make_prompt_plan, validate_prompt_plan
from .v2.seeds import derive_chunk_seed
from .v2.session import entry_to_state, make_session, validate_session

__all__ = [
    "PUBLIC_API_VERSION",
    "FIRST_FRAME_POLICIES",
    "POLICY_REPLACE",
    "POLICY_ERROR",
    "POLICY_KEEP",
    "make_extension_shape",
    "conditioning_diagnostics",
    "prepare_conditioning",
    "new_h3_latent",
    "capture_state",
    "select_context",
    "validate_state",
    "validate_plan",
    "normalize_condition_latents",
    "patch_layout_in_place",
    "trim_audio",
    "assemble_segments",
    "make_prompt_plan",
    "validate_prompt_plan",
    "derive_chunk_seed",
    "latent_motion_score",
    "choose_context_frames",
    "make_session",
    "validate_session",
    "entry_to_state",
]
