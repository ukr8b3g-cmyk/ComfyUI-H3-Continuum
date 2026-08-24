from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ID_JS = ROOT / "web" / "project_id.js"
REFERENCE_AUDIO_UI_JS = ROOT / "web" / "reference_audio_ui.js"
BRIDGE_WORKFLOW = (
    ROOT
    / "examples"
    / "workflows"
    / "MiniMax_H3_Continuum_V351_LBH_Conditioning_Bridge.json"
)


def test_v35_keeps_reference_audio_inputs_permanent_after_node_setup():
    project_source = PROJECT_ID_JS.read_text(encoding="utf-8")
    reference_source = REFERENCE_AUDIO_UI_JS.read_text(encoding="utf-8")

    assert 'import { normalizeReferenceAudioLabels } from "./reference_audio_ui.js";' in project_source
    assert "normalizeReferenceAudioLabels(node);" in project_source
    assert "configureReferenceAudioInputs" not in project_source
    assert "Reference Audio Inputs" not in reference_source
    assert "addInput" not in reference_source
    assert "removeInput" not in reference_source
    assert "addWidget" not in reference_source
    assert "onSerialize" not in reference_source


def test_reference_audio_labels_do_not_change_inputs_or_widgets(tmp_path):
    node = shutil.which("node")
    assert node is not None, "Node.js is required for frontend behavior validation"

    module_path = tmp_path / "reference_audio_ui.mjs"
    module_path.write_text(REFERENCE_AUDIO_UI_JS.read_text(encoding="utf-8"), encoding="utf-8")
    harness_path = tmp_path / "reference_audio_ui_harness.mjs"
    harness_path.write_text(
        r'''
import assert from "node:assert/strict";
import { normalizeReferenceAudioLabels } from "./reference_audio_ui.mjs";

const inputs = [
    { name: "reference_video_1", type: "IMAGE", label: "Video Reference", link: null },
    { name: "driving_audio", type: "AUDIO", label: "driving_audio", link: null },
    { name: "audio_vae", type: "VAE", label: "audio_vae", link: null },
    { name: "reference_audio_1", type: "AUDIO", label: "Reference Audio", link: null },
    { name: "reference_audio_vae", type: "VAE", label: "Reference Audio VAE", link: null },
    { name: "prompt_mode", type: "COMBO", link: null },
];
const widgets = [{ name: "prompt_mode", value: "Auto" }];
const node = { inputs, widgets };
const originalInputs = [...inputs];
const originalWidgets = [...widgets];

assert.equal(normalizeReferenceAudioLabels(node), true);
assert.deepEqual(node.inputs, originalInputs);
assert.deepEqual(node.widgets, originalWidgets);
assert.deepEqual(
    node.inputs.slice(0, 5).map((input) => input.label),
    [
        "Video Guide Frames",
        "Driving Audio",
        "Driving Audio VAE",
        "Reference Audio (Optional)",
        "Reference Audio VAE (Optional)",
    ],
);
assert.equal(node.inputs[3].name, "reference_audio_1");
assert.equal(node.inputs[4].name, "reference_audio_vae");
''',
        encoding="utf-8",
    )

    result = subprocess.run(
        [node, str(harness_path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_workflow_save_reload_preserves_v35_widget_value_alignment(tmp_path):
    node = shutil.which("node")
    assert node is not None, "Node.js is required for frontend behavior validation"

    module_path = tmp_path / "reference_audio_ui.mjs"
    module_path.write_text(REFERENCE_AUDIO_UI_JS.read_text(encoding="utf-8"), encoding="utf-8")
    harness_path = tmp_path / "workflow_reload_harness.mjs"
    harness_path.write_text(
        r'''
import assert from "node:assert/strict";
import { normalizeReferenceAudioLabels } from "./reference_audio_ui.mjs";

const widgetValues = {
    prompt_mode: "Auto",
    chunks: 3,
    chunk_seconds: 5.0,
    width: 1344,
    height: 768,
    continuity: "Balanced — 22 frames",
    base_seed: 123456789,
    control_after_generate: "randomize",
    audio_continuity: true,
    diagnostics: "Detailed Report",
    reroll_from_chunk: "Auto",
    reroll_nonce: 7,
    strict_compatibility: false,
    debug: false,
    show_preview: true,
    run_storage: "Off",
    run_name: "alignment-test",
    reference_size: "Match Output",
    project_id: "workflow-save-reload",
    video_reference_size: "Efficient - 0.4 MP",
};

function makeNode(values) {
    return {
        inputs: [
            { name: "reference_video_1", type: "IMAGE", link: null },
            { name: "driving_audio", type: "AUDIO", link: null },
            { name: "audio_vae", type: "VAE", link: null },
            { name: "reference_audio_1", type: "AUDIO", link: null },
            { name: "reference_audio_vae", type: "VAE", link: null },
        ],
        widgets: Object.entries(values).map(([name, value]) => ({ name, value })),
    };
}

const original = makeNode(widgetValues);
normalizeReferenceAudioLabels(original);
const saved = JSON.parse(JSON.stringify({
    inputs: original.inputs.map(({ name, type, link }) => ({ name, type, link })),
    widgets_values: original.widgets
        .filter((widget) => widget.serialize !== false)
        .map((widget) => widget.value),
}));

assert.equal(saved.inputs[3].name, "reference_audio_1");
assert.equal(saved.inputs[4].name, "reference_audio_vae");
assert.equal(saved.widgets_values.length, Object.keys(widgetValues).length);

const reloaded = makeNode(Object.fromEntries(Object.keys(widgetValues).map((name) => [name, null])));
saved.widgets_values.forEach((value, index) => {
    reloaded.widgets[index].value = value;
});
normalizeReferenceAudioLabels(reloaded);

assert.deepEqual(
    Object.fromEntries(reloaded.widgets.map(({ name, value }) => [name, value])),
    widgetValues,
);
assert.equal(reloaded.widgets.some((widget) => widget.name === "Reference Audio Inputs"), false);
assert.deepEqual(
    reloaded.inputs.map((input) => input.name),
    original.inputs.map((input) => input.name),
);
''',
        encoding="utf-8",
    )

    result = subprocess.run(
        [node, str(harness_path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_bundled_bridge_workflow_has_permanent_sockets_and_aligned_widgets():
    workflow = json.loads(BRIDGE_WORKFLOW.read_text(encoding="utf-8"))
    sampler = next(
        node for node in workflow["nodes"] if node["type"] == "H3ContinuumSamplerV35"
    )
    expected = {
        "prompt_mode": "Auto",
        "chunks": 1,
        "chunk_seconds": 5,
        "width": 1344,
        "height": 768,
        "continuity": "Fast — 5 frames",
        "base_seed": 783839598838387,
        "control_after_generate": "randomize",
        "audio_continuity": True,
        "diagnostics": "Detailed Report",
        "reroll_from_chunk": "Auto",
        "reroll_nonce": 0,
        "strict_compatibility": False,
        "debug": False,
        "show_preview": True,
        "run_storage": "Off",
        "run_name": "",
        "reference_size": "Match Output",
        "project_id": "d1c61168-c72e-44d1-9b78-1c9adb4eba0e",
        "video_reference_size": "Efficient - 0.4 MP",
    }

    assert sampler["widgets_values"] == list(expected.values())
    assert sampler["widgets_values_named"] == expected
    input_names = [input_["name"] for input_ in sampler["inputs"]]
    assert input_names[input_names.index("audio_vae") + 1 : input_names.index("width")] == [
        "reference_audio_1",
        "reference_audio_vae",
    ]
