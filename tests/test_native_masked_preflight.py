import pytest

from ComfyUI_H3_Continuum_Join.constants import V2_CONTINUITY_AUTO, V2_CONTINUITY_OPTIONS
from ComfyUI_H3_Continuum_Join.masked_continuation import (
    CONTINUATION_GUIDE,
    CONTINUATION_NATIVE_MASKED,
    NativeMaskedContinuationError,
    validate_native_masked_request,
)


@pytest.mark.parametrize("continuity", [V2_CONTINUITY_OPTIONS[1], V2_CONTINUITY_OPTIONS[2]])
def test_native_generated_audio_rejects_non_shared_av_profiles(continuity):
    with pytest.raises(NativeMaskedContinuationError, match="do not land on an exact H3"):
        validate_native_masked_request(
            method=CONTINUATION_NATIVE_MASKED,
            continuity=continuity,
            audio_continuity=True,
            driving_audio_active=False,
            chunks=2,
        )


@pytest.mark.parametrize(
    "method,continuity,audio_continuity,driving_audio_active,chunks",
    [
        (CONTINUATION_NATIVE_MASKED, V2_CONTINUITY_OPTIONS[3], True, False, 2),
        (CONTINUATION_NATIVE_MASKED, V2_CONTINUITY_AUTO, True, False, 2),
        (CONTINUATION_NATIVE_MASKED, V2_CONTINUITY_OPTIONS[1], False, False, 2),
        (CONTINUATION_NATIVE_MASKED, V2_CONTINUITY_OPTIONS[1], True, True, 2),
        (CONTINUATION_NATIVE_MASKED, V2_CONTINUITY_OPTIONS[1], True, False, 1),
        (CONTINUATION_GUIDE, V2_CONTINUITY_OPTIONS[1], True, False, 2),
    ],
)
def test_native_av_preflight_preserves_valid_nonconflicting_modes(
    method,
    continuity,
    audio_continuity,
    driving_audio_active,
    chunks,
):
    validate_native_masked_request(
        method=method,
        continuity=continuity,
        audio_continuity=audio_continuity,
        driving_audio_active=driving_audio_active,
        chunks=chunks,
    )
