from pathlib import Path
import json
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ID_JS = ROOT / "web" / "project_id.js"


def _function_source(source: str, name: str, next_name: str) -> str:
    start = source.index(f"function {name}")
    end = source.index(f"function {next_name}", start)
    return source[start:end]


def test_v35_sampler_uses_existing_compact_runtime_settings_path():
    source = PROJECT_ID_JS.read_text(encoding="utf-8")
    configure = _function_source(source, "configureNode", "configureNodeAfterSetup")
    before_queue = source[source.index("async beforeQueuePrompt") :]

    assert 'const V35_NODE_CLASS = "H3ContinuumSamplerV35";' in source
    assert "const isV35 = node.comfyClass === V35_NODE_CLASS;" in configure
    assert "!isProduction && !isTimeline && !isV34 && !isV35" in configure
    assert "isProduction || isV34 || isV35" in configure
    assert "node.comfyClass === V35_NODE_CLASS" in before_queue

    for widget_name in (
        '"diagnostics"',
        '"strict_compatibility"',
        '"debug"',
        '"show_preview"',
    ):
        assert f"hidePersistentWidget(findWidget(node, {widget_name}))" in configure


def test_v36_sampler_uses_compact_settings_without_hiding_backend_choice():
    source = PROJECT_ID_JS.read_text(encoding="utf-8")
    configure = _function_source(source, "configureNode", "configureNodeAfterSetup")
    before_queue = source[source.index("async beforeQueuePrompt") :]

    assert 'const V36_NODE_CLASS = "H3ContinuumSamplerV36";' in source
    assert "const isV36 = node.comfyClass === V36_NODE_CLASS;" in configure
    assert "!isProduction && !isTimeline && !isV34 && !isV35 && !isV36" in configure
    assert "isProduction || isV34 || isV35 || isV36" in configure
    assert "isV35 || isV36" in configure
    assert "node.comfyClass === V36_NODE_CLASS" in before_queue
    assert 'hidePersistentWidget(findWidget(node, "continuation_backend"))' not in configure


def test_v37_sampler_inherits_v36_compact_frontend_and_queue_normalization():
    source = PROJECT_ID_JS.read_text(encoding="utf-8")
    configure = _function_source(source, "configureNode", "configureNodeAfterSetup")
    before_queue = source[source.index("async beforeQueuePrompt") :]

    assert 'const V37_NODE_CLASS = "H3ContinuumSamplerV37";' in source
    assert "const isV37 = node.comfyClass === V37_NODE_CLASS;" in configure
    assert (
        "!isProduction && !isTimeline && !isV34 && !isV35 && !isV36 && !isV37"
        in configure
    )
    assert "isProduction || isV34 || isV35 || isV36 || isV37" in configure
    assert "isV35 || isV36 || isV37" in configure
    assert "node.comfyClass === V37_NODE_CLASS" in before_queue
    assert 'hidePersistentWidget(findWidget(node, "continuation_backend"))' not in configure


def test_v35_assembler_uses_existing_compact_runtime_settings_path():
    source = PROJECT_ID_JS.read_text(encoding="utf-8")
    configure = _function_source(source, "configureAssembler", "configureNode")
    before_queue = source[source.index("async beforeQueuePrompt") :]

    assert (
        'const V35_ASSEMBLE_SEAM_NODE_CLASS = "H3ContinuumAssembleSeamV35";'
        in source
    )
    assert "node.comfyClass !== V35_ASSEMBLE_SEAM_NODE_CLASS" in configure
    assert "node.comfyClass === V35_ASSEMBLE_SEAM_NODE_CLASS" in before_queue
    assert 'hidePersistentWidget(findWidget(node, "diagnostics"))' in configure


def test_run_storage_off_normalizes_widgets_reload_and_queued_inputs(tmp_path):
    node_executable = shutil.which("node")
    if node_executable is None:
        pytest.skip("Node.js is required for the frontend behavior regression")

    source = PROJECT_ID_JS.read_text(encoding="utf-8")
    functions = "\n".join(
        [
            _function_source(source, "findWidget", "setWidgetVisible"),
            _function_source(source, "setWidgetVisible", "hidePersistentWidget"),
            _function_source(source, "linkedInput", "attachRefresh"),
            _function_source(source, "attachRefresh", "normalizeRunStorageState"),
            _function_source(source, "normalizeRunStorageState", "configureConditionalWidgets"),
            _function_source(source, "configureConditionalWidgets", "configureAssembler"),
        ]
    )
    script = f"""
const RUN_STORAGE_WIDGET = "run_storage";
const REGENERATE_WIDGET = "reroll_from_chunk";
const REROLL_NONCE_WIDGET = "reroll_nonce";
const LEGACY_RUN_NAME_WIDGET = "run_name";
const REFERENCE_SIZE_WIDGET = "reference_size";
const TIMELINE_SIZE_WIDGET = "timeline_video_size";
const VIDEO_REFERENCE_SIZE_WIDGET = "video_reference_size";
{functions}

function widget(name, value) {{
    return {{ name, value, type: "combo", options: {{}}, computeSize: () => [120, 20] }};
}}
function makeNode(storage, regenerate, nonce) {{
    return {{
        widgets: [
            widget(RUN_STORAGE_WIDGET, storage),
            widget(REGENERATE_WIDGET, regenerate),
            widget(REROLL_NONCE_WIDGET, nonce),
            widget(LEGACY_RUN_NAME_WIDGET, "phase1-test"),
            widget(REFERENCE_SIZE_WIDGET, "Match Output"),
            widget(TIMELINE_SIZE_WIDGET, "Efficient"),
            widget(VIDEO_REFERENCE_SIZE_WIDGET, "Efficient"),
        ],
        inputs: [],
        setDirtyCanvas() {{}},
    }};
}}

const live = makeNode("Save + Auto Resume", "Auto", 0);
configureConditionalWidgets(live);
const liveStorage = findWidget(live, RUN_STORAGE_WIDGET);
const liveRegenerate = findWidget(live, REGENERATE_WIDGET);
const liveNonce = findWidget(live, REROLL_NONCE_WIDGET);
liveRegenerate.value = "Chunk 2";
liveRegenerate.callback("Chunk 2");
liveNonce.value = 5;
liveStorage.value = "Off";
liveStorage.callback("Off");

const queued = {{ reroll_from_chunk: "Chunk 2", reroll_nonce: 5 }};
normalizeRunStorageState(live, queued);

const reloaded = makeNode("Off", "Chunk 3", 9);
configureConditionalWidgets(reloaded);
const reloadRegenerate = findWidget(reloaded, REGENERATE_WIDGET);
const reloadNonce = findWidget(reloaded, REROLL_NONCE_WIDGET);

console.log(JSON.stringify({{
    live: {{ regenerate: liveRegenerate.value, nonce: liveNonce.value }},
    queued,
    reloaded: {{
        regenerate: reloadRegenerate.value,
        nonce: reloadNonce.value,
        regenerateHidden: reloadRegenerate.hidden,
        nonceHidden: reloadNonce.hidden,
    }},
}}));
"""
    script_path = tmp_path / "run-storage-frontend-regression.js"
    script_path.write_text(script, encoding="utf-8")

    result = subprocess.run(
        [node_executable, str(script_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    observed = json.loads(result.stdout)

    assert observed["live"] == {"regenerate": "Auto", "nonce": 0}
    assert observed["queued"] == {"reroll_from_chunk": "Auto", "reroll_nonce": 0}
    assert observed["reloaded"] == {
        "regenerate": "Auto",
        "nonce": 0,
        "regenerateHidden": True,
        "nonceHidden": True,
    }
