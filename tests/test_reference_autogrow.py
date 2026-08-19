from pathlib import Path

from ComfyUI_H3_Continuum_Join.v3.driving_nodes import H3ContinuumSamplerV34


ROOT = Path(__file__).resolve().parents[1]


def test_v34_sampler_declares_all_eight_reference_inputs():
    optional = H3ContinuumSamplerV34.INPUT_TYPES()["optional"]
    for index in range(1, 9):
        assert optional[f"reference_image_{index}"][0] == "IMAGE"


def test_v34_frontend_keeps_three_visible_and_grows_to_eight():
    source = (ROOT / "web" / "v34_ui.js").read_text(encoding="utf-8")
    assert "const BASE_REFERENCE_INPUTS = 3;" in source
    assert "const MAX_REFERENCE_INPUTS = 8;" in source
    assert "node.addInput?.(`reference_image_${index}`, \"IMAGE\")" in source
    assert "node.removeInput?.(slot)" in source
    assert "highestConnected + 1" in source
