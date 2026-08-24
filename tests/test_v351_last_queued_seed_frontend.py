from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ID_JS = ROOT / "web" / "project_id.js"
SEED_REUSE_JS = ROOT / "web" / "last_queued_seed.js"


def test_v35_only_wires_last_queued_seed_reuse_into_prompt_capture():
    source = PROJECT_ID_JS.read_text(encoding="utf-8")

    assert 'const V35_NODE_CLASS = "H3ContinuumSamplerV35";' in source
    assert "if (isV35)" in source
    assert "configureLastQueuedSeedReuse(node);" in source
    assert "if (node.comfyClass === V35_NODE_CLASS)" in source
    assert "captureLastQueuedSeed(node, apiNode?.inputs?.base_seed);" in source


def test_last_queued_seed_state_is_session_only_and_uses_required_fields():
    source = SEED_REUSE_JS.read_text(encoding="utf-8")

    for field in (
        "last_queued_seed",
        "auto_updated_seed",
        "previous_control_mode",
        "auto_update_pending",
    ):
        assert field in source
    assert "localStorage" not in source
    assert "sessionStorage" not in source
    assert "widgets_values" not in source


def test_last_queued_seed_behavior_with_real_javascript_module(tmp_path):
    node = shutil.which("node")
    assert node is not None, "Node.js is required for frontend behavior validation"

    module_path = tmp_path / "last_queued_seed.mjs"
    module_path.write_text(SEED_REUSE_JS.read_text(encoding="utf-8"), encoding="utf-8")
    harness_path = tmp_path / "seed_reuse_harness.mjs"
    harness_path.write_text(
        r'''
import assert from "node:assert/strict";
import {
    captureLastQueuedSeed,
    configureLastQueuedSeedReuse,
} from "./last_queued_seed.mjs";

function makeNode({ seed = 101, mode = "randomize", nextSeeds = [], runAfter = true } = {}) {
    const remaining = [...nextSeeds];
    const seedWidget = {
        name: "base_seed",
        value: seed,
        callback(value) {
            this.value = value;
        },
    };
    const controlWidget = {
        name: "control_after_generate",
        value: mode,
        callback(value) {
            this.value = value;
        },
        afterQueued() {
            if (runAfter && this.value === "randomize" && remaining.length) {
                const next = remaining.shift();
                seedWidget.value = next;
                seedWidget.callback(next);
            }
        },
    };
    seedWidget.linkedWidgets = [controlWidget];
    const node = { widgets: [seedWidget, controlWidget] };
    assert.equal(configureLastQueuedSeedReuse(node), true);
    return { node, seedWidget, controlWidget };
}

function setSeed(seedWidget, value) {
    seedWidget.value = value;
    seedWidget.callback(value);
}

function setMode(controlWidget, value) {
    controlWidget.value = value;
    controlWidget.callback(value);
}

{
    const { node, seedWidget, controlWidget } = makeNode({ nextSeeds: [202] });
    assert.equal(captureLastQueuedSeed(node, 101), true);
    controlWidget.afterQueued();
    assert.equal(seedWidget.value, 202);
    setMode(controlWidget, "fixed");
    assert.equal(seedWidget.value, 101);
}

{
    const { node, seedWidget, controlWidget } = makeNode({ nextSeeds: [202] });
    captureLastQueuedSeed(node, 101);
    controlWidget.afterQueued();
    setSeed(seedWidget, 303);
    setMode(controlWidget, "fixed");
    assert.equal(seedWidget.value, 303);
}

{
    const { node, seedWidget, controlWidget } = makeNode({ nextSeeds: [202, 303] });
    captureLastQueuedSeed(node, 101);
    controlWidget.afterQueued();
    assert.equal(seedWidget.value, 202);
    captureLastQueuedSeed(node, 202);
    controlWidget.afterQueued();
    assert.equal(seedWidget.value, 303);
    setMode(controlWidget, "fixed");
    assert.equal(seedWidget.value, 202);
}

{
    const { node, seedWidget, controlWidget } = makeNode({ runAfter: false });
    captureLastQueuedSeed(node, 101);
    controlWidget.afterQueued();
    setMode(controlWidget, "fixed");
    assert.equal(seedWidget.value, 101);
}

{
    const { node, seedWidget, controlWidget } = makeNode({ mode: "fixed", nextSeeds: [202] });
    captureLastQueuedSeed(node, 101);
    controlWidget.afterQueued();
    assert.equal(seedWidget.value, 101);
    setSeed(seedWidget, 404);
    assert.equal(seedWidget.value, 404);
}

{
    const { node, seedWidget, controlWidget } = makeNode({ nextSeeds: [202] });
    captureLastQueuedSeed(node, 101);
    controlWidget.afterQueued();
    assert.equal(seedWidget.value, 202);
    assert.equal(captureLastQueuedSeed(node, ["12", 0]), false);
    setMode(controlWidget, "fixed");
    assert.equal(seedWidget.value, 202);
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
