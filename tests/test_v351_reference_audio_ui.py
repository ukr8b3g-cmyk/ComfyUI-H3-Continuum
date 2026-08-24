from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ID_JS = ROOT / "web" / "project_id.js"
REFERENCE_AUDIO_UI_JS = ROOT / "web" / "reference_audio_ui.js"


def test_v35_wires_reference_audio_visibility_after_node_setup():
    source = PROJECT_ID_JS.read_text(encoding="utf-8")

    assert 'from "./reference_audio_ui.js";' in source
    assert "if (node.comfyClass === V35_NODE_CLASS)" in source
    assert "configureReferenceAudioInputs(node);" in source
    assert "setTimeout(configureDeferred, 0);" in source
    assert "node.__h3ContinuumLoadedGraphNode = true;" in source
    assert "node.__h3ContinuumAfterConfigureGraph = true;" in source


def test_reference_audio_visibility_with_real_javascript_module(tmp_path):
    node = shutil.which("node")
    assert node is not None, "Node.js is required for frontend behavior validation"

    module_path = tmp_path / "reference_audio_ui.mjs"
    module_path.write_text(REFERENCE_AUDIO_UI_JS.read_text(encoding="utf-8"), encoding="utf-8")
    harness_path = tmp_path / "reference_audio_ui_harness.mjs"
    harness_path.write_text(
        r'''
import assert from "node:assert/strict";
import { configureReferenceAudioInputs } from "./reference_audio_ui.mjs";

function makeNode({ referenceLink = null, vaeLink = null, includeReferenceInputs = true } = {}) {
    const widgets = [];
    const inputs = [
        { name: "reference_video_1", type: "IMAGE", label: "Video Reference", link: null },
        { name: "driving_audio", type: "AUDIO", link: null },
        { name: "audio_vae", type: "VAE", link: null },
    ];
    if (includeReferenceInputs) {
        inputs.push(
            { name: "reference_audio_1", type: "AUDIO", label: "Reference Audio", shape: 7, link: referenceLink },
            { name: "reference_audio_vae", type: "VAE", label: "Reference Audio VAE", shape: 7, link: vaeLink },
        );
    }
    inputs.push(
        { name: "prompt_mode", type: "COMBO", link: null },
        { name: "chunks", type: "INT", link: null },
    );
    let previousConnectionCalls = 0;
    const node = {
        inputs,
        widgets,
        size: [320, 600],
        addWidget(type, name, value, callback, options) {
            const widget = { type, name, value, callback, options };
            this.widgets.push(widget);
            return widget;
        },
        addInput(name, type, options = {}) {
            const input = { name, type, link: null, ...options };
            this.inputs.push(input);
            return input;
        },
        removeInput(index) {
            assert.ok(this.inputs[index].link === null || this.inputs[index].link === -1);
            this.inputs.splice(index, 1);
        },
        computeSize() {
            return [320, 400 + this.inputs.length * 10];
        },
        setSize(size) {
            this.size = size;
        },
        setDirtyCanvas() {},
        onConnectionsChange() {
            previousConnectionCalls += 1;
        },
    };
    return { node, previousConnectionCalls: () => previousConnectionCalls };
}

function widget(node) {
    return node.widgets.find((item) => item.name === "Reference Audio Inputs");
}

function input(node, name) {
    return node.inputs.find((item) => item.name === name);
}

{
    const { node } = makeNode();
    assert.equal(configureReferenceAudioInputs(node), true);
    assert.equal(widget(node).value, "Hidden");
    assert.equal(widget(node).options.serialize, false);
    assert.equal(widget(node).serializeValue(), undefined);
    assert.equal(input(node, "reference_audio_1"), undefined);
    assert.equal(input(node, "reference_audio_vae"), undefined);
    assert.equal(input(node, "reference_video_1").label, "Video Guide Frames");
    assert.equal(input(node, "audio_vae").label, "Driving Audio VAE");
    const serialized = { widgets_values: node.widgets.map((item) => item.value) };
    node.onSerialize(serialized);
    assert.deepEqual(serialized.widgets_values, []);

    widget(node).value = "Show";
    widget(node).callback("Show");
    assert.deepEqual(
        node.inputs.slice(3, 5).map((item) => [item.name, item.label]),
        [
            ["reference_audio_1", "Reference Audio (Optional)"],
            ["reference_audio_vae", "Reference Audio VAE (Optional)"],
        ],
    );

    input(node, "reference_audio_1").link = 42;
    widget(node).value = "Hidden";
    widget(node).callback("Hidden");
    assert.equal(widget(node).value, "Show");
    assert.equal(input(node, "reference_audio_1").link, 42);
}

{
    const { node, previousConnectionCalls } = makeNode({ referenceLink: 7, vaeLink: 8 });
    assert.equal(configureReferenceAudioInputs(node), true);
    assert.equal(widget(node).value, "Show");
    assert.equal(input(node, "reference_audio_1").link, 7);
    assert.equal(input(node, "reference_audio_vae").link, 8);
    node.onConnectionsChange();
    await new Promise((resolve) => setTimeout(resolve, 1));
    assert.equal(previousConnectionCalls(), 1);
    assert.equal(widget(node).value, "Show");
}

{
    const { node } = makeNode({ referenceLink: -1, vaeLink: -1 });
    assert.equal(configureReferenceAudioInputs(node), true);
    assert.equal(widget(node).value, "Hidden");
    assert.equal(input(node, "reference_audio_1"), undefined);
    assert.equal(input(node, "reference_audio_vae"), undefined);
}

{
    const { node } = makeNode({ includeReferenceInputs: false });
    assert.equal(configureReferenceAudioInputs(node), true);
    assert.equal(widget(node).value, "Hidden");
    widget(node).value = "Show";
    widget(node).callback("Show");
    assert.equal(input(node, "reference_audio_1").type, "AUDIO");
    assert.equal(input(node, "reference_audio_vae").type, "VAE");
}
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
