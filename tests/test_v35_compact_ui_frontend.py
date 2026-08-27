from pathlib import Path


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
