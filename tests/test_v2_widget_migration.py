import json
from pathlib import Path

from ComfyUI_H3_Continuum_Join.constants import DIAGNOSTICS_BASIC
from ComfyUI_H3_Continuum_Join.v2.nodes import _repair_v200_example_widget_shift


def test_malformed_v200_example_widget_shift_is_repaired():
    values = _repair_v200_example_widget_shift(
        audio_continuity=True,
        exact_total_duration=DIAGNOSTICS_BASIC,
        diagnostics=0,
        reroll_from_chunk=0,
        reroll_nonce=True,
        strict_compatibility=False,
        debug=False,
    )
    assert values == (True, True, DIAGNOSTICS_BASIC, 0, 0, True, False)


def test_valid_v2_widget_values_are_unchanged():
    values = _repair_v200_example_widget_shift(
        audio_continuity=False,
        exact_total_duration=False,
        diagnostics=DIAGNOSTICS_BASIC,
        reroll_from_chunk=2,
        reroll_nonce=7,
        strict_compatibility=True,
        debug=True,
    )
    assert values == (False, False, DIAGNOSTICS_BASIC, 2, 7, True, True)


def test_bundled_v2_example_serializes_control_after_generate_slot():
    root = Path(__file__).resolve().parents[1]
    data = json.loads((root / "examples" / "H3_Continuum_V2_3x5s.json").read_text(encoding="utf-8"))
    node = next(n for n in data["nodes"] if n["type"] == "H3ContinuumSamplerV2")
    values = node["widgets_values"]
    assert len(values) == 16
    assert values[8] in {"fixed", "increment", "decrement", "randomize"}
    assert values[11] in {"Basic", "Full", "Off"}
