from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from ComfyUI_H3_Continuum_Join import nodes as root_nodes
from ComfyUI_H3_Continuum_Join.v3 import driving_nodes
from ComfyUI_H3_Continuum_Join.v3 import easy_nodes
from ComfyUI_H3_Continuum_Join.v3 import second_pass_nodes


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DISPLAY_NAMES = {
    "H3ContinuumSamplerV38": "H3 Continuum Sampler V3.8",
    "H3ContinuumSamplerV39": "H3 Continuum Sampler V3.9",
    "H3ContinuumReferenceAudios": "H3 Continuum Reference Audios",
    "H3ContinuumAssembleSeamV35": "H3 Continuum Finalize",
    "H3EasyLoadImage": "H3 Continuum Load Image",
    "H3EasyLoadAudio": "H3 Continuum Load Audio",
    "H3ContinuumLoadVideo": "H3 Continuum Load Video",
    "H3ContinuumVideoAdapter": "H3 Continuum Video Adapter",
    "H3ContinuumSecondPassV35": "H3 Continuum Second Pass",
    "H3ContinuumReferenceImages": "H3 Continuum Reference Images",
    "H3ContinuumReferenceImagesV39": "H3 Continuum Reference Images V3.9",
    "H3DecodeCacheHelper": "Decode Cache Helper",
}


def test_public_export_keeps_legacy_loaders_and_adds_video_adapter():
    assert set(root_nodes.NODE_CLASS_MAPPINGS) == set(PUBLIC_DISPLAY_NAMES)
    assert root_nodes.NODE_DISPLAY_NAME_MAPPINGS == PUBLIC_DISPLAY_NAMES


def test_labs_and_unreleased_easy_implementations_remain_internal():
    assert "H3ContinuumMemoryActionPolicyExperimental" in (
        driving_nodes.NODE_CLASS_MAPPINGS
    )
    assert "H3ContinuumSamplerV38MemoryPolicyExperimental" in (
        driving_nodes.NODE_CLASS_MAPPINGS
    )
    assert "H3ContinuumSelectiveSecondPassExperimental" in (
        second_pass_nodes.NODE_CLASS_MAPPINGS
    )
    assert "H3ContinuumEasyReferences" in easy_nodes.NODE_CLASS_MAPPINGS
    assert "H3ContinuumEasyV38" in easy_nodes.NODE_CLASS_MAPPINGS
    assert not set(
        (
            "H3ContinuumMemoryActionPolicyExperimental",
            "H3ContinuumSamplerV38MemoryPolicyExperimental",
            "H3ContinuumSelectiveSecondPassExperimental",
            "H3ContinuumEasyReferences",
            "H3ContinuumEasyV38",
        )
    ) & set(root_nodes.NODE_CLASS_MAPPINGS)


def test_v38_schema_and_serialized_widget_order_are_unchanged():
    schema = driving_nodes.H3ContinuumSamplerV38.INPUT_TYPES()
    assert list(schema["required"]) == [
        "model",
        "clip",
        "video_vae",
        "sampler",
        "sigmas",
        "sequence_prompt",
        "prompt_mode",
        "chunks",
        "chunk_seconds",
        "aspect",
        "preset",
        "custom_mp",
        "continuity",
        "base_seed",
        "audio_continuity",
        "diagnostics",
        "reroll_from_chunk",
        "reroll_nonce",
        "strict_compatibility",
        "debug",
        "show_preview",
        "run_storage",
        "run_name",
        "reference_size",
        "project_id",
        "video_reference_size",
        "continuation_backend",
            "generation_mode",
            "review_action",
            "take_group",
            "take_revision_id",
            "take_action",
            "size_source",
            "width",
            "height",
        ]
    assert list(schema["optional"]) == [
        "first_frame",
        "last_frame",
        "reference_image_1",
        "reference_image_2",
        "reference_image_3",
        "reference_video_1",
        "driving_audio",
        "audio_vae",
        "reference_audio_1",
        "reference_audio_vae",
        "guide",
        "audio_references",
        "image_references",
        "video_reference_mode",
    ]


def test_registry_package_keeps_official_v38x2_workflows_and_excludes_development_assets():
    rules = (ROOT / ".comfyignore").read_text(encoding="utf-8").splitlines()
    assert "tests/" in rules
    assert "tools/*" in rules
    assert "!tools/__init__.py" in rules
    assert "!tools/p20_file_backed_tensor_poc.py" in rules
    assert "tools/" not in rules
    assert "AGENTS.md" in rules
    assert "PROJECT_STATE.md" in rules
    assert "WORKLOG.md" in rules
    assert "MANIFEST.sha256" in rules
    assert "examples/*" in rules
    assert "!examples/workflows/" in rules
    assert "examples/workflows/*" in rules
    assert "!examples/workflows/MiniMax_H3_Continuum_V38X2.json" in rules
    assert "!examples/workflows/MiniMax_H3_Continuum_V38X2.zip" in rules
    assert "!examples/workflows/MiniMax_H3_Continuum_V38X2+Decode_Cache_Helper.json" in rules
    assert "!examples/workflows/MiniMax_H3_Continuum_V38X2+Decode_Cache_Helper.zip" in rules
    assert "!examples/workflows/MiniMax_H3_Continuum_V39_Reference_Inline.json" in rules
    assert "!examples/workflows/MiniMax_H3_Continuum_V39_Reference_Inline.zip" in rules
    assert "!examples/workflows/MiniMax_H3_Continuum_V39.json" in rules
    assert "!examples/workflows/MiniMax_H3_Continuum_V39.zip" in rules
    assert "!examples/MiniMax_H3_Continuum_V39.json" in rules
    assert "!examples/MiniMax_H3_Continuum_V38X2.json" in rules
    assert "*.zip" in rules

    workflow = json.loads(
        (ROOT / "examples/workflows/MiniMax_H3_Continuum_V38X2.json").read_text(
            encoding="utf-8"
        )
    )
    custom_types = {
        node["type"] for node in workflow["nodes"] if node["type"].startswith("H3")
    }
    assert custom_types <= set(PUBLIC_DISPLAY_NAMES)
    sampler = next(
        node for node in workflow["nodes"] if node["type"] == "H3ContinuumSamplerV38"
    )
    assert sampler["properties"]["H3 Continuum View"] == "Basic"
    # The user-approved Spectrum distribution preserves its saved Core titles.
    # Exact bytes, dependencies and graph topology are tested in the workflow suite.
    assert any(node["type"] == "SpectrumApplyMiniMaxH3" for node in workflow["nodes"])


def test_registry_manifest_matches_every_declared_source_file():
    manifest = ROOT / "REGISTRY_MANIFEST.sha256"
    entries = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        digest, relative_path = line.split("  ", 1)
        entries[relative_path] = digest

    assert "REGISTRY_MANIFEST.sha256" not in entries
    assert "MANIFEST.sha256" not in entries
    assert "AGENTS.md" not in entries
    assert "PROJECT_STATE.md" not in entries
    assert "WORKLOG.md" not in entries
    assert "tools/__init__.py" in entries
    assert "tools/p20_file_backed_tensor_poc.py" in entries
    assert "tools/verify_runtime.py" in entries
    assert not {
        path for path in entries if path.startswith("tools/")
    } - {
        "tools/__init__.py",
        "tools/p20_file_backed_tensor_poc.py",
        "tools/verify_runtime.py",
    }
    assert {
        path for path in entries if path.startswith("examples/")
    } == {
        "examples/workflows/MiniMax_H3_Continuum_V38X2.json",
        "examples/workflows/MiniMax_H3_Continuum_V38X2.zip",
        "examples/workflows/MiniMax_H3_Continuum_V38X2+Decode_Cache_Helper.json",
        "examples/workflows/MiniMax_H3_Continuum_V38X2+Decode_Cache_Helper.zip",
        "examples/workflows/MiniMax_H3_Continuum_V39_Reference_Inline.json",
        "examples/workflows/MiniMax_H3_Continuum_V39_Reference_Inline.zip",
        "examples/workflows/MiniMax_H3_Continuum_V39.json",
        "examples/workflows/MiniMax_H3_Continuum_V39.zip",
        "examples/MiniMax_H3_Continuum_V39.json",
        "examples/MiniMax_H3_Continuum_V38X2.json",
    }

    for relative_path, expected_digest in entries.items():
        payload = (ROOT / relative_path).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == expected_digest


def test_intuitive_facade_is_discoverable_and_presentation_only(tmp_path):
    node_executable = shutil.which("node")
    if node_executable is None:
        pytest.skip("Node.js is required for the frontend behavior regression")

    source = (ROOT / "web/project_id.js").read_text(encoding="utf-8")
    source = source.replace(
        'import { app } from "../../scripts/app.js";',
        "const app = globalThis.__app;",
    ).replace(
        'import { normalizeReferenceAudioLabels } from "./reference_audio_ui.js";',
        "function normalizeReferenceAudioLabels() {}",
    ).replace(
        'import { configureV39ReferenceImages, connectedV39LegacyReferenceInputs, pruneV39LegacyReferenceInputs, refreshV39ReferenceImagesForSampler } from "./reference_images_v39.js";',
        "function configureV39ReferenceImages() {} function connectedV39LegacyReferenceInputs() { return []; } function pruneV39LegacyReferenceInputs() { return 0; } function refreshV39ReferenceImagesForSampler() {}",
    ).replace(
        'import { migrateReferenceImageInputs } from "./reference_image_ui.js";',
        "function migrateReferenceImageInputs() {}",
    ).replace(
        'import { api } from "../../scripts/api.js";',
        "const api = { fetchApi: (...args) => globalThis.fetch(...args), "
        "addEventListener(name, callback) { "
        "const listeners = terminalListeners.get(name) || []; "
        "listeners.push(callback); terminalListeners.set(name, listeners); }, "
        "queuePrompt: async () => ({prompt_id: 'facade-queue'}) };",
    )
    script = f"""
globalThis.__extension = null;
const terminalListeners = new Map();
let savedProject = null;
const sourceNodes = {{
  101: {{ id: 101, mode: 0, widgets: [{{ name: "Enable Image", value: true }}] }},
  102: {{ id: 102, mode: 0, widgets: [{{ name: "Enable Video", value: true }}] }},
  103: {{ id: 103, mode: 4, widgets: [{{ name: "Enable Audio", value: true }}] }},
  104: {{ id: 104, mode: 0, widgets: [{{ name: "Enable Audio", value: true }}] }},
}};
globalThis.__app = {{
  graph: {{
    _nodes: [],
    links: {{
      2: {{ origin_id: 102 }}, 3: {{ origin_id: 101 }},
      4: {{ origin_id: 103 }}, 5: {{ origin_id: 104 }},
    }},
    getNodeById(id) {{ return sourceNodes[id] || null; }},
  }},
  ui: {{ settings: {{ getSettingValue: (_id, fallback) => fallback, addSetting() {{}} }} }},
  registerExtension(extension) {{ globalThis.__extension = extension; }},
}};
globalThis.fetch = async () => savedProject
  ? {{status: 200, ok: true, json: async () => structuredClone(savedProject)}}
  : {{status: 404, ok: false}};
{source}
function widget(name, value) {{
  return {{
    name, value, type: "combo",
    options: {{ values: [] }},
    computeSize: () => [120, 20],
  }};
}}
const node = {{
  id: 312,
  comfyClass: "H3ContinuumSamplerV38",
  properties: {{ "H3 Continuum View": "Basic" }},
  widgets: [
    widget("prompt_mode", "Auto"),
    widget("chunks", 3), widget("chunk_seconds", 5),
    widget("aspect", "Auto from First Image"),
    widget("preset", "Draft — 0.30 MP"), widget("custom_mp", 0.3),
    widget("continuity", "Balanced — 22 frames"),
    widget("base_seed", 0), widget("control_after_generate", "randomize"),
    widget("audio_continuity", true),
    widget("continuation_backend", "Standard"),
    widget("run_storage", "Save + Auto Resume"),
    widget("reroll_from_chunk", "Chunk 2"), widget("reroll_nonce", 7),
    widget("run_name", "keep-me"), widget("reference_size", "Match Output"),
    widget("video_reference_size", "Efficient - 0.4 MP"),
    widget("diagnostics", "Detailed Report"), widget("strict_compatibility", false),
    widget("debug", true), widget("show_preview", false),
    widget("project_id", "stable-project"),
    widget("generation_mode", "Full Run"), widget("review_action", "Continue / Next"),
    widget("take_group", 0), widget("take_revision_id", ""),
    widget("take_action", "Automatic"),
    widget("size_source", "First Image"), widget("width", 480), widget("height", 640),
  ],
  inputs: [
    {{ name: "model", link: 10 }},
    {{ name: "clip", link: 11 }},
    {{ name: "video_vae", link: 12 }},
    {{ name: "sampler", link: 13 }},
    {{ name: "sigmas", link: 14 }},
    {{ name: "prompt_overrides", link: null }},
    {{ name: "first_frame", link: 3 }},
    {{ name: "last_frame", link: null }},
    {{ name: "reference_image_1", link: 1 }},
    {{ name: "reference_video_1", link: 2 }},
    {{ name: "driving_audio", link: null }},
    {{ name: "audio_references", link: null }},
    {{ name: "guide", link: null }},
  ],
  addWidget(type, name, value, callback, options) {{
    const item = {{ name, value, callback, type, options: options || {{}}, computeSize: () => [120, 20] }};
    this.widgets.push(item);
    return item;
  }},
  addCustomWidget(item) {{
    this.widgets.push(item);
    return item;
  }},
  removeInput(index) {{ this.inputs.splice(index, 1); }},
  serialize() {{ return {{ widgets_values: this.widgets.map((item) => item.value) }}; }},
  configure(info) {{
    info.widgets_values.forEach((value, index) => {{ this.widgets[index].value = value; }});
  }},
  setDirtyCanvas() {{}},
}};
globalThis.__app.graph._nodes.push(node);
globalThis.__extension.nodeCreated(node);
globalThis.__extension.setup();
setTimeout(async () => {{
  const savedBefore = node.serialize().widgets_values;
  const facade = Object.fromEntries([
    "Prompt Format", "Continuity", "Base Seed", "Control After Generate", "Audio Continuity",
    "Chunks", "Seconds per Chunk", "Total Length",
    "Size Source", "Resolution", "Custom MP", "Width", "Height",
    "Run", "Progress", "Ready to Queue", "Advanced Settings",
    "Reference Image Size", "Video Guide Size",
  ].map((name) => [name, node.widgets.find((item) => item.name === name)]));
  const normalVisibleBeforeReview = [
    "Prompt Format", "Continuity", "Base Seed", "Control After Generate", "Audio Continuity",
    "Chunks", "Seconds per Chunk", "Total Length", "Size Source", "Resolution",
    "Run", "Progress", "Ready to Queue", "Advanced Settings",
  ].every((name) => facade[name] && !facade[name].hidden);
  const coreMainOrder = node.widgets.slice(0, 5).map((item) => item.name);
  const corePersistentHidden = [
    "prompt_mode", "continuity", "base_seed", "control_after_generate", "audio_continuity",
  ].every((name) => node.widgets.find((item) => item.name === name).hidden);
  const dimensionsInitiallyHidden = facade.Width.hidden && facade.Height.hidden;
  const drawMetrics = (widget) => {{
    let rect = null;
    const textYs = [];
    const ctx = {{
      save() {{}}, restore() {{}}, beginPath() {{}}, closePath() {{}},
      fill() {{}}, stroke() {{}}, moveTo() {{}}, lineTo() {{}}, quadraticCurveTo() {{}},
      roundRect(x, y, width, height, radius) {{ rect = {{ x, y, width, height, radius }}; }},
      fillText(_text, _x, y) {{ textYs.push(y); }},
    }};
    widget.draw(ctx, node, 400, 100, 20);
    return {{ rectHeight: rect.height, firstTextY: textYs[0], secondTextY: textYs[1] }};
  }};
  const readyCardMetrics = drawMetrics(facade["Ready to Queue"]);
  const reviewActionHidden = node.widgets.find((item) => item.name === "review_action").hidden;
  const advancedSource = node.widgets.find((item) => item.name === "continuation_backend");
  const advancedInitiallyHidden = advancedSource.hidden;
  const advancedClosedLabel = facade["Advanced Settings"].label;
  facade["Advanced Settings"].callback();
  const advancedVisible = !advancedSource.hidden;
  const conditionalSizesVisibleInAdvanced = (
    !facade["Reference Image Size"].hidden && !facade["Video Guide Size"].hidden
  );
  const advancedOpenLabel = facade["Advanced Settings"].label;
  facade["Advanced Settings"].callback();
  facade["Seconds per Chunk"].value = 10;
  facade["Seconds per Chunk"].callback(10);
  const chunksAfterSecondsChange = node.widgets.find((item) => item.name === "chunks").value;
  const secondsAfterSecondsChange = node.widgets.find((item) => item.name === "chunk_seconds").value;
  const totalAfterSecondsChange = facade["Total Length"].value;
  facade.Chunks.value = 2;
  facade.Chunks.callback(2);
  const secondsAfterChunksChange = node.widgets.find((item) => item.name === "chunk_seconds").value;
  const totalAfterChunksChange = facade["Total Length"].value;
  facade["Size Source"].value = "Manual";
  facade["Size Source"].callback("Manual");
  const manualSizeSource = node.widgets.find((item) => item.name === "size_source").value;
  const manualResolutionHidden = facade.Resolution.hidden;
  const manualDimensionsVisible = !facade.Width.hidden && !facade.Height.hidden;
  facade["Size Source"].value = "First Image";
  facade["Size Source"].callback("First Image");
  sourceNodes[101].mode = 4;
  node.__h3ContinuumIntuitiveUxRefresh();
  const bypassedSizeSource = facade["Size Source"].value;
  const bypassedReady = facade["Ready to Queue"].value;
  const bypassedResolutionVisible = !facade.Resolution.hidden;
  const bypassedDimensionsHidden = facade.Width.hidden && facade.Height.hidden;
  sourceNodes[101].mode = 0;
  node.__h3ContinuumIntuitiveUxRefresh();
  facade.Run.value = "Review Each Chunk";
  facade.Run.callback("Review Each Chunk");
  const reviewMapped = node.widgets.find((item) => item.name === "generation_mode").value;
  const saveMapped = node.widgets.find((item) => item.name === "run_storage").value;
  facade.Chunks.value = 1;
  facade.Chunks.callback(1);
  const singleChunkReviewGuidance = facade["Ready to Queue"].value;
  const singleChunkReviewHelp = facade.Chunks.tooltip;
  facade.Chunks.value = 2;
  facade.Chunks.callback(2);
  const autoFixedReviewGuidance = facade["Ready to Queue"].value;
  facade["Control After Generate"].value = "fixed";
  facade["Control After Generate"].callback("fixed");
  const fixedReviewReady = facade["Ready to Queue"].value;
  const reviewButtonsHiddenBeforeReady = [
    "Use it and continue", "Try this chunk again", "Use it and finish the rest",
  ].every((name) => node.widgets.find((item) => item.name === name).hidden);
  const historyHiddenBeforeTake = node.widgets.find(
    (item) => item.name === "Render History",
  ).hidden;
  // Queue ordinary continuation through the supported lifecycle. Do not call
  // the removed setup helper or fabricate completion directly on the node.
  node.widgets.find((item) => item.name === "reroll_from_chunk").value = "Auto";
  for (const widget of node.widgets) widget.beforeQueued?.({{isPartialExecution:false}});
  const submitted = {{}};
  for (const [index, widget] of node.widgets.entries()) {{
    if (widget.options?.serialize === false) continue;
    submitted[widget.name] = widget.serializeValue
      ? await widget.serializeValue(node, index) : widget.value;
  }}
  await api.queuePrompt(0, {{output: {{312: {{class_type:node.comfyClass, inputs:submitted}}}}}});
  for (const widget of node.widgets) widget.afterQueued?.({{isPartialExecution:false}});
  savedProject = {{
    branch_provenance_version: 1,
    canonical_storage_revision_id: "storage-ready",
    revisions: [{{
      revision_id: "storage-ready", status: "review_ready",
      sampling_contract_version: 6, generation_reusable: true,
      review_unit: {{ start: 1, end: 1, physical_group: 1 }},
    }}],
    canonical_head_revision_id: "take-1",
    active_revisions: {{ "1": "take-1" }},
    group_revisions: [{{
      revision_id: "take-1", revision_order: "1",
      sampling_contract_version: 6, generation_reusable: true,
      group: {{ start: 1, end: 1, physical_group: 1 }},
    }}],
  }};
  for (const listener of terminalListeners.get("execution_success") || []) {{
    await listener({{type:"execution_success",detail:{{prompt_id:"facade-queue"}}}});
  }}
  const reviewButtonsVisibleWhenReady = [
    "Use it and continue", "Try this chunk again", "Use it and finish the rest",
  ].every((name) => !node.widgets.find((item) => item.name === name).hidden);
  const setupHiddenWhenReady = [
    "Prompt Format", "Continuity", "Base Seed", "Control After Generate", "Audio Continuity",
    "Chunks", "Seconds per Chunk", "Total Length", "Size Source", "Resolution",
    "Run", "Progress", "Ready to Queue",
  ].every((name) => node.widgets.find((item) => item.name === name).hidden);
  const reviewStatus = node.widgets.find((item) => item.name === "Review Ready");
  const reviewCardMetrics = drawMetrics(reviewStatus);
  const reviewStatusBeforeSelection = reviewStatus.value;
  const backToSettings = node.widgets.find((item) => item.name === "Back to Settings");
  const returnToReview = node.widgets.find((item) => item.name === "Return to Review");
  const backToSettingsVisibleWhenReady = !backToSettings.hidden;
  const returnToReviewHiddenWhenReady = returnToReview.hidden;
  backToSettings.callback();
  const setupVisibleAfterBack = [
    "Prompt Format", "Continuity", "Base Seed", "Control After Generate", "Audio Continuity",
    "Chunks", "Seconds per Chunk", "Total Length", "Size Source", "Resolution",
    "Run", "Progress", "Ready to Queue",
  ].every((name) => !node.widgets.find((item) => item.name === name).hidden);
  const reviewButtonsHiddenAfterBack = [
    "Use it and continue", "Try this chunk again", "Use it and finish the rest",
  ].every((name) => node.widgets.find((item) => item.name === name).hidden);
  const returnToReviewVisibleAfterBack = !returnToReview.hidden;
  const backToSettingsHiddenAfterBack = backToSettings.hidden;
  const settingsReviewCard = node.widgets.find((item) => item.name === "Ready to Queue");
  const settingsReviewStatusAfterBack = settingsReviewCard.value;
  const settingsReviewVariantAfterBack = settingsReviewCard.__h3ContinuumInfoVariant;
  returnToReview.callback();
  const setupHiddenAfterReturn = [
    "Prompt Format", "Continuity", "Base Seed", "Control After Generate", "Audio Continuity",
    "Chunks", "Seconds per Chunk", "Total Length", "Size Source", "Resolution",
    "Run", "Progress", "Ready to Queue",
  ].every((name) => node.widgets.find((item) => item.name === name).hidden);
  const reviewButtonsVisibleAfterReturn = [
    "Use it and continue", "Try this chunk again", "Use it and finish the rest",
  ].every((name) => !node.widgets.find((item) => item.name === name).hidden);
  const continueButton = node.widgets.find((item) => item.name === "Use it and continue");
  continueButton.callback();
  const selectedContinueLabel = continueButton.label;
  const reviewStatusAfterSelection = reviewStatus.value;
  const historyVisibleWithTake = !node.widgets.find(
    (item) => item.name === "Render History",
  ).hidden;
  const savedAfter = node.serialize().widgets_values;
  console.log(JSON.stringify({{
    facadeNames: Object.keys(facade),
    normalVisible: normalVisibleBeforeReview,
    coreMainOrder,
    corePersistentHidden,
    promptFormat: facade["Prompt Format"].value,
    continuity: facade.Continuity.value,
    baseSeed: facade["Base Seed"].value,
    controlAfter: facade["Control After Generate"].value,
    audioContinuity: facade["Audio Continuity"].value,
    readyCardMetrics,
    reviewCardMetrics,
    dimensionsInitiallyHidden,
    chunks: facade.Chunks.value,
    secondsPerChunk: facade["Seconds per Chunk"].value,
    totalLength: facade["Total Length"].value,
    sizeSource: facade["Size Source"].value,
    resolution: facade.Resolution.value,
    progress: facade.Progress.value,
    ready: facade["Ready to Queue"].value,
    reviewActionHidden,
    advancedInitiallyHidden,
    advancedVisible,
    conditionalSizesVisibleInAdvanced,
    advancedClosedLabel,
    advancedOpenLabel,
    legacyPropertyRemoved: !("H3 Continuum View" in node.properties),
    reviewMapped,
    saveMapped,
    singleChunkReviewGuidance,
    singleChunkReviewHelp,
    autoFixedReviewGuidance,
    fixedReviewReady,
    chunksAfterSecondsChange,
    secondsAfterSecondsChange,
    totalAfterSecondsChange,
    secondsAfterChunksChange,
    totalAfterChunksChange,
    manualSizeSource,
    manualResolutionHidden,
    manualDimensionsVisible,
    bypassedSizeSource,
    bypassedReady,
    bypassedResolutionVisible,
    bypassedDimensionsHidden,
    reviewButtonsHiddenBeforeReady,
    reviewButtonsVisibleWhenReady,
    setupHiddenWhenReady,
    backToSettingsVisibleWhenReady,
    returnToReviewHiddenWhenReady,
    setupVisibleAfterBack,
    reviewButtonsHiddenAfterBack,
    returnToReviewVisibleAfterBack,
    backToSettingsHiddenAfterBack,
    settingsReviewStatusAfterBack,
    settingsReviewVariantAfterBack,
    setupHiddenAfterReturn,
    reviewButtonsVisibleAfterReturn,
    reviewStatusBeforeSelection,
    selectedContinueLabel,
    reviewStatusAfterSelection,
    historyHiddenBeforeTake,
    historyVisibleWithTake,
    serializedCountStable: savedBefore.length === savedAfter.length,
    inputs: node.inputs.map((item) => item.name),
  }}));
}}, 150);
"""
    script_path = tmp_path / "v38-public-surface-ui.js"
    script_path.write_text(script, encoding="utf-8")
    result = subprocess.run(
        [node_executable, str(script_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    observed = json.loads(result.stdout)
    assert observed == {
        "facadeNames": [
            "Prompt Format",
            "Continuity",
            "Base Seed",
            "Control After Generate",
            "Audio Continuity",
            "Chunks",
            "Seconds per Chunk",
            "Total Length",
            "Size Source",
            "Resolution",
            "Custom MP",
            "Width",
            "Height",
            "Run",
            "Progress",
            "Ready to Queue",
            "Advanced Settings",
            "Reference Image Size",
            "Video Guide Size",
        ],
        "normalVisible": True,
        "coreMainOrder": [
            "Prompt Format",
            "Continuity",
            "Base Seed",
            "Control After Generate",
            "Audio Continuity",
        ],
        "corePersistentHidden": True,
        "promptFormat": "Auto",
        "continuity": "Balanced — 22 frames",
        "baseSeed": 0,
        "controlAfter": "fixed",
        "audioContinuity": True,
        "readyCardMetrics": {
            "rectHeight": 56,
            "firstTextY": 122,
            "secondTextY": 145,
        },
        "reviewCardMetrics": {
            "rectHeight": 62,
            "firstTextY": 122,
            "secondTextY": 145,
        },
        "dimensionsInitiallyHidden": True,
        "chunks": 2,
        "secondsPerChunk": 10,
        "totalLength": "20 seconds",
        "sizeSource": "First Image",
        "resolution": "Draft — 0.30 MP",
        "progress": "On — Resume and Takes available",
        "ready": "Ready to Queue\n2 × 10s = 20 seconds • First Image • Review each chunk",
        "reviewActionHidden": True,
        "advancedInitiallyHidden": True,
        "advancedVisible": True,
        "conditionalSizesVisibleInAdvanced": True,
        "advancedClosedLabel": "Show Advanced Settings",
        "advancedOpenLabel": "Hide Advanced Settings",
        "legacyPropertyRemoved": True,
        "reviewMapped": "Review Each Chunk",
        "saveMapped": "Save + Auto Resume",
        "singleChunkReviewGuidance": (
            "Set Chunks to 2 or more\nChunks is 1, so the first 10s chunk is also the last. "
            "Set Chunks to 2 or more before Queue to use Review and Continue."
        ),
        "singleChunkReviewHelp": (
            "Chunks is 1, so there is no next chunk to continue. Set Chunks to 2 or more "
            "before Queue when using Review Each Chunk."
        ),
        "autoFixedReviewGuidance": (
            "Ready to Queue\n2 × 10s = 20 seconds • First Image • Review each chunk"
        ),
        "fixedReviewReady": (
            "Ready to Queue\n2 × 10s = 20 seconds • First Image • Review each chunk"
        ),
        "chunksAfterSecondsChange": 3,
        "secondsAfterSecondsChange": 10,
        "totalAfterSecondsChange": "30 seconds",
        "secondsAfterChunksChange": 10,
        "totalAfterChunksChange": "20 seconds",
        "manualSizeSource": "Manual",
        "manualResolutionHidden": True,
        "manualDimensionsVisible": True,
        "bypassedSizeSource": "First Image",
        "bypassedReady": (
            "Check First Image\nSize Source is First Image, but no active image is "
            "connected. Queue fallback: 480 × 640."
        ),
        "bypassedResolutionVisible": True,
        "bypassedDimensionsHidden": True,
        "reviewButtonsHiddenBeforeReady": True,
        "reviewButtonsVisibleWhenReady": True,
        "setupHiddenWhenReady": True,
        "backToSettingsVisibleWhenReady": True,
        "returnToReviewHiddenWhenReady": True,
        "setupVisibleAfterBack": True,
        "reviewButtonsHiddenAfterBack": True,
        "returnToReviewVisibleAfterBack": True,
        "backToSettingsHiddenAfterBack": True,
        "settingsReviewStatusAfterBack": (
            "Chunk 1 is ready for review\nChoose what happens next, then press Queue."
        ),
        "settingsReviewVariantAfterBack": "review",
        "setupHiddenAfterReturn": True,
        "reviewButtonsVisibleAfterReturn": True,
        "reviewStatusBeforeSelection": (
            "Chunk 1 is ready for review\nChoose what happens next, then press Queue."
        ),
        "selectedContinueLabel": "✓ Use it and continue",
        "reviewStatusAfterSelection": (
            "Chunk 1 is ready for review\nSelected: Use it and continue. Press Queue to run this action."
        ),
        "historyHiddenBeforeTake": True,
        "historyVisibleWithTake": True,
        "serializedCountStable": True,
        "inputs": [
            "model",
            "clip",
            "video_vae",
            "sampler",
            "sigmas",
            "prompt_overrides",
            "first_frame",
            "last_frame",
            "reference_image_1",
            "reference_video_1",
                "driving_audio",
                "audio_references",
            ],
    }
