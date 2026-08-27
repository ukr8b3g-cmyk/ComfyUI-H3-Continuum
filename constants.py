"""Constants shared by H3 Continuum Join."""

from __future__ import annotations

FPS = 24.0
AUDIO_SAMPLE_RATE = 32_000
AUDIO_LATENT_FPS = 40.0
FRAME_RESCALE = AUDIO_LATENT_FPS / FPS
FRAME_PER_TOKEN = (1, 4, 4, 4, 4)

CHUNK_SECONDS_DEFAULT = 5.0
CHUNK_SECONDS_MIN = 4.0
CHUNK_SECONDS_MAX = 30.0
CHUNK_SECONDS_STEP = 0.1
CHUNK_SECONDS_TOOLTIP = (
    "Target duration shared by every chunk. 5–15 seconds is the recommended "
    "and validated range. Values above 15 seconds are supported, but VRAM "
    "use and processing time can increase substantially, especially at high "
    "resolution."
)

STATE_MAGIC = "H3_CONTINUUM_STATE"
PLAN_MAGIC = "H3_CONTINUUM_PLAN"
SESSION_MAGIC = "H3_CONTINUUM_SESSION"
PROMPT_PLAN_MAGIC = "H3_CONTINUUM_PROMPT_PLAN"

MARK_SCHEMA = "_h3cj_schema"
MARK_VIDEO_SLOT = "_h3cj_video_slot"  # legacy/internal-slot compatibility
MARK_PIXEL_START = "_h3cj_pixel_start"
MARK_VIDEO_CONTEXT = "_h3cj_video_context"
MARK_CONTEXT_FRAMES = "_h3cj_context_frames"
MARK_AUDIO_CONTEXT = "_h3cj_audio_context"
MARK_AUDIO_END_FRAME = "_h3cj_audio_end_frame"
MARK_AUDIO_OVERHANG = "_h3cj_audio_overhang"
CONTINUUM_REFERENCE_METADATA_KEY = "_h3_continuum"
CONTINUUM_INTEROP_KEY = "h3_continuum"
CONTINUUM_INTEROP_API = 1
CONTINUUM_ACTUAL_PREFIX_STEPS = 2

MODEL_WRAPPER_KEY = "h3_continuum_join.apply_model.v1"
V2_RUNTIME_KEY = "h3_continuum_v2"
LAYOUT_ORIGINAL_TIME_ATTR = "_h3cj_original_time_v1"
LAYOUT_SIGNATURE_ATTR = "_h3cj_patch_signature_v1"
LAYOUT_DEVICE_CACHE_ATTR = "_h3cj_device_cache_v1"

CONTINUITY_OPTIONS = (
    "Balanced — 22 frames",
    "Fast — 5 frames",
    "Strong — 39 frames (Experimental)",
)
CONTINUITY_FRAMES = {
    CONTINUITY_OPTIONS[0]: 22,
    CONTINUITY_OPTIONS[1]: 5,
    CONTINUITY_OPTIONS[2]: 39,
}
DEFAULT_STATE_CAPACITY_FRAMES = 39

V2_CONTINUITY_AUTO = "Auto — conservative"
V2_CONTINUITY_OPTIONS = (V2_CONTINUITY_AUTO,) + CONTINUITY_OPTIONS

PROMPT_MODE_FIXED = "Fixed — one prompt"
PROMPT_MODE_LIST = "List — split with ---"
PROMPT_MODE_TIMELINE = "Timeline — [0-5s] sections"
PROMPT_MODE_OPTIONS = (PROMPT_MODE_FIXED, PROMPT_MODE_LIST, PROMPT_MODE_TIMELINE)

PROMPT_FORMAT_AUTO = "Auto"
PROMPT_FORMAT_FIXED = "Fixed"
PROMPT_FORMAT_LIST = "List"
PROMPT_FORMAT_TIMELINE = "Timeline"
PROMPT_FORMAT_OPTIONS = (
    PROMPT_FORMAT_AUTO,
    PROMPT_FORMAT_FIXED,
    PROMPT_FORMAT_LIST,
    PROMPT_FORMAT_TIMELINE,
)

DIAGNOSTICS_OFF = "Off"
DIAGNOSTICS_BASIC = "Basic"
DIAGNOSTICS_FULL = "Detailed Report"
DIAGNOSTICS_LEGACY_FULL = "Full"
DIAGNOSTICS_OPTIONS = (DIAGNOSTICS_BASIC, DIAGNOSTICS_FULL, DIAGNOSTICS_OFF)
DIAGNOSTICS_ACCEPTED_OPTIONS = DIAGNOSTICS_OPTIONS + (DIAGNOSTICS_LEGACY_FULL,)


def normalize_diagnostics_mode(value: str) -> str:
    return DIAGNOSTICS_FULL if value == DIAGNOSTICS_LEGACY_FULL else value

SEAM_CORRECTION_AUTO = "Auto"
SEAM_CORRECTION_OFF = "Off"
SEAM_CORRECTION_BASIC = "Basic"
SEAM_CORRECTION_OPTIONS = (
    SEAM_CORRECTION_AUTO,
    SEAM_CORRECTION_OFF,
    SEAM_CORRECTION_BASIC,
)
