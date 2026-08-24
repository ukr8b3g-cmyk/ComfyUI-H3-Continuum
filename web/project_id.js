import { app } from "../../scripts/app.js";
import {
    captureLastQueuedSeed,
    configureLastQueuedSeedReuse,
} from "./last_queued_seed.js";
import { normalizeReferenceAudioLabels } from "./reference_audio_ui.js";

const PRODUCTION_NODE_CLASS = "H3ContinuumSamplerProduction";
const TIMELINE_NODE_CLASS = "H3ContinuumSamplerTimelineVideo";
const ASSEMBLE_SEAM_NODE_CLASS = "H3ContinuumAssembleSeamExperimental";
const V34_NODE_CLASS = "H3ContinuumSamplerV34";
const V34_ASSEMBLE_SEAM_NODE_CLASS = "H3ContinuumAssembleSeamV34";
const V35_NODE_CLASS = "H3ContinuumSamplerV35";
const V35_ASSEMBLE_SEAM_NODE_CLASS = "H3ContinuumAssembleSeamV35";
const PROJECT_WIDGET = "project_id";
const LEGACY_RUN_NAME_WIDGET = "run_name";
const CHUNKS_WIDGET = "chunks";
const REGENERATE_WIDGET = "reroll_from_chunk";
const REROLL_NONCE_WIDGET = "reroll_nonce";
const RUN_STORAGE_WIDGET = "run_storage";
const REFERENCE_SIZE_WIDGET = "reference_size";
const TIMELINE_SIZE_WIDGET = "timeline_video_size";
const VIDEO_REFERENCE_SIZE_WIDGET = "video_reference_size";
const PROMPT_OVERRIDES_INPUT = "prompt_overrides";
const SETTINGS = {
    detailedReport: "H3Continuum.DetailedReport",
    developerDiagnostics: "H3Continuum.DeveloperDiagnostics",
    samplingPreview: "H3Continuum.SamplingPreview",
};

function createProjectId() {
    if (globalThis.crypto?.randomUUID) {
        return globalThis.crypto.randomUUID();
    }
    const bytes = new Uint8Array(16);
    globalThis.crypto.getRandomValues(bytes);
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = Array.from(bytes, (value) => value.toString(16).padStart(2, "0")).join("");
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

function findWidget(node, name) {
    return node.widgets?.find((widget) => widget.name === name);
}

function setWidgetVisible(widget, visible) {
    if (!widget) {
        return;
    }
    if (!widget.__h3ContinuumOriginal) {
        widget.__h3ContinuumOriginal = {
            type: widget.type,
            computeSize: widget.computeSize,
            hidden: widget.hidden,
            optionsHidden: widget.options?.hidden,
        };
    }
    widget.options ||= {};
    if (visible) {
        const original = widget.__h3ContinuumOriginal;
        widget.type = original.type;
        widget.computeSize = original.computeSize;
        widget.hidden = original.hidden;
        if (original.optionsHidden === undefined) {
            delete widget.options.hidden;
        } else {
            widget.options.hidden = original.optionsHidden;
        }
    } else {
        widget.hidden = true;
        widget.type = "converted-widget";
        widget.options.hidden = true;
        widget.computeSize = () => [0, -4];
    }
}

function hidePersistentWidget(widget) {
    setWidgetVisible(widget, false);
}

function settingValue(id, fallback) {
    try {
        return app.ui?.settings?.getSettingValue?.(id) ?? fallback;
    } catch {
        return fallback;
    }
}

function applyRuntimeSettings(node) {
    const detailed = Boolean(settingValue(SETTINGS.detailedReport, false));
    const debug = Boolean(settingValue(SETTINGS.developerDiagnostics, false));
    const preview = Boolean(settingValue(SETTINGS.samplingPreview, true));
    const diagnosticsWidget = findWidget(node, "diagnostics");
    const debugWidget = findWidget(node, "debug");
    const previewWidget = findWidget(node, "show_preview");
    const strictWidget = findWidget(node, "strict_compatibility");
    if (diagnosticsWidget) diagnosticsWidget.value = detailed ? "Detailed Report" : "Basic";
    if (debugWidget) debugWidget.value = debug;
    if (previewWidget) previewWidget.value = preview;
    if (strictWidget) strictWidget.value = false;
}

function removeUnusedInput(node, name) {
    const index = node.inputs?.findIndex((input) => input.name === name) ?? -1;
    if (index < 0) {
        return;
    }
    const input = node.inputs[index];
    if (input.link != null) {
        app.graph?.removeLink(input.link);
    }
    node.removeInput(index);
}

function regenerateOptions(chunks) {
    const count = Math.max(1, Math.min(16, Number.parseInt(chunks, 10) || 1));
    return ["Auto", ...Array.from({ length: count }, (_, index) => `Chunk ${index + 1}`)];
}

function configureRegenerateFrom(node) {
    const chunksWidget = findWidget(node, CHUNKS_WIDGET);
    const regenerateWidget = findWidget(node, REGENERATE_WIDGET);
    if (!chunksWidget || !regenerateWidget) {
        return;
    }
    const refresh = () => {
        const values = regenerateOptions(chunksWidget.value);
        regenerateWidget.options ||= {};
        regenerateWidget.options.values = values;
        const numeric = typeof regenerateWidget.value === "number"
            ? regenerateWidget.value
            : Number.parseInt(String(regenerateWidget.value).replace(/^Chunk\s+/, ""), 10);
        if (regenerateWidget.value === "Auto" || numeric === 0) {
            regenerateWidget.value = "Auto";
        } else if (Number.isInteger(numeric) && numeric >= 1 && numeric < values.length) {
            regenerateWidget.value = `Chunk ${numeric}`;
        } else {
            regenerateWidget.value = "Auto";
        }
    };
    if (!chunksWidget.__h3ContinuumRegenerateCallback) {
        const previous = chunksWidget.callback;
        chunksWidget.callback = function(value, ...args) {
            const result = previous?.call(this, value, ...args);
            refresh();
            return result;
        };
        chunksWidget.__h3ContinuumRegenerateCallback = true;
    }
    refresh();
}

function linkedInput(node, names) {
    return node.inputs?.some((input) => names.includes(input.name) && input.link != null) ?? false;
}

function attachRefresh(widget, key, refresh) {
    if (!widget || widget[key]) {
        return;
    }
    const previous = widget.callback;
    widget.callback = function(value, ...args) {
        const result = previous?.call(this, value, ...args);
        refresh();
        return result;
    };
    widget[key] = true;
}

function configureConditionalWidgets(node) {
    const storageWidget = findWidget(node, RUN_STORAGE_WIDGET);
    const regenerateWidget = findWidget(node, REGENERATE_WIDGET);
    const nonceWidget = findWidget(node, REROLL_NONCE_WIDGET);
    const runNameWidget = findWidget(node, LEGACY_RUN_NAME_WIDGET);
    const refresh = () => {
        const storageEnabled = storageWidget?.value === "Save + Auto Resume";
        const explicitRegeneration = storageEnabled
            && regenerateWidget?.value !== "Auto"
            && Number.parseInt(String(regenerateWidget?.value).replace(/^Chunk\s+/, ""), 10) > 0;
        setWidgetVisible(regenerateWidget, storageEnabled);
        setWidgetVisible(runNameWidget, storageEnabled);
        setWidgetVisible(nonceWidget, explicitRegeneration);
        setWidgetVisible(
            findWidget(node, REFERENCE_SIZE_WIDGET),
            linkedInput(node, ["reference_image_1", "reference_image_2", "reference_image_3"]),
        );
        setWidgetVisible(
            findWidget(node, TIMELINE_SIZE_WIDGET),
            linkedInput(node, ["timeline_video"]),
        );
        setWidgetVisible(
            findWidget(node, VIDEO_REFERENCE_SIZE_WIDGET),
            linkedInput(node, ["reference_video_1"]),
        );
        node.setDirtyCanvas?.(true, true);
    };
    attachRefresh(storageWidget, "__h3ContinuumStorageCallback", refresh);
    attachRefresh(regenerateWidget, "__h3ContinuumRegenerateVisibilityCallback", refresh);
    if (!node.__h3ContinuumConnectionCallback) {
        const previous = node.onConnectionsChange;
        node.onConnectionsChange = function(...args) {
            const result = previous?.apply(this, args);
            setTimeout(refresh, 0);
            return result;
        };
        node.__h3ContinuumConnectionCallback = true;
    }
    refresh();
}

function configureAssembler(node) {
    if (
        node.comfyClass !== ASSEMBLE_SEAM_NODE_CLASS
        && node.comfyClass !== V34_ASSEMBLE_SEAM_NODE_CLASS
        && node.comfyClass !== V35_ASSEMBLE_SEAM_NODE_CLASS
    ) {
        return false;
    }
    const exactDuration = findWidget(node, "exact_total_duration");
    if (exactDuration) exactDuration.value = true;
    applyRuntimeSettings(node);
    hidePersistentWidget(exactDuration);
    hidePersistentWidget(findWidget(node, "diagnostics"));
    node.setDirtyCanvas?.(true, true);
    return true;
}

function configureNode(node) {
    const isProduction = node.comfyClass === PRODUCTION_NODE_CLASS;
    const isTimeline = node.comfyClass === TIMELINE_NODE_CLASS;
    const isV34 = node.comfyClass === V34_NODE_CLASS;
    const isV35 = node.comfyClass === V35_NODE_CLASS;
    if (!isProduction && !isTimeline && !isV34 && !isV35) {
        configureAssembler(node);
        return null;
    }
    const projectWidget = findWidget(node, PROJECT_WIDGET);
    if (isProduction || isV34 || isV35) {
        if (projectWidget && !String(projectWidget.value || "").trim()) {
            projectWidget.value = createProjectId();
        }
        removeUnusedInput(node, PROMPT_OVERRIDES_INPUT);
    }
    applyRuntimeSettings(node);
    if (isV35) {
        configureLastQueuedSeedReuse(node);
        normalizeReferenceAudioLabels(node);
    }
    hidePersistentWidget(findWidget(node, "diagnostics"));
    hidePersistentWidget(findWidget(node, "strict_compatibility"));
    hidePersistentWidget(findWidget(node, "debug"));
    hidePersistentWidget(findWidget(node, "show_preview"));
    hidePersistentWidget(projectWidget);
    configureRegenerateFrom(node);
    configureConditionalWidgets(node);
    node.setDirtyCanvas?.(true, true);
    return projectWidget;
}

function configureNodeAfterSetup(node) {
    configureNode(node);
    const configureDeferred = () => configureNode(node);
    setTimeout(configureDeferred, 0);
    setTimeout(configureDeferred, 100);
}

app.registerExtension({
    name: "H3Continuum.ProjectId",

    setup() {
        const settings = app.ui?.settings;
        settings?.addSetting?.({
            id: SETTINGS.samplingPreview,
            name: "H3 Continuum: Sampling Preview",
            type: "boolean",
            defaultValue: true,
            tooltip: "Show live sampling previews. Disable only to reduce preview overhead.",
            onChange: () => refreshConfiguredNodes(),
        });
        settings?.addSetting?.({
            id: SETTINGS.developerDiagnostics,
            name: "H3 Continuum: Developer Diagnostics",
            type: "boolean",
            defaultValue: false,
            tooltip: "Enable developer-only Continuum logging and assertions.",
            onChange: () => refreshConfiguredNodes(),
        });
        settings?.addSetting?.({
            id: SETTINGS.detailedReport,
            name: "H3 Continuum: Detailed Report",
            type: "boolean",
            defaultValue: false,
            tooltip: "Include detailed diagnostics in status and assembly reports.",
            onChange: () => refreshConfiguredNodes(),
        });
    },

    nodeCreated(node) {
        configureNodeAfterSetup(node);
    },

    loadedGraphNode(node) {
        configureNodeAfterSetup(node);
    },

    afterConfigureGraph() {
        for (const node of app.graph?._nodes || []) {
            configureNodeAfterSetup(node);
        }
    },

    async beforeQueuePrompt(prompt) {
        const seen = new Set();
        for (const node of app.graph?._nodes || []) {
            const projectWidget = configureNode(node);
            const apiNode = prompt.output?.[String(node.id)];
            if (node.comfyClass === V35_NODE_CLASS) {
                captureLastQueuedSeed(node, apiNode?.inputs?.base_seed);
            }
            if (apiNode?.inputs) {
                if (
                    node.comfyClass === PRODUCTION_NODE_CLASS
                    || node.comfyClass === TIMELINE_NODE_CLASS
                    || node.comfyClass === V34_NODE_CLASS
                    || node.comfyClass === V35_NODE_CLASS
                ) {
                    apiNode.inputs.diagnostics = settingValue(SETTINGS.detailedReport, false)
                        ? "Detailed Report"
                        : "Basic";
                    apiNode.inputs.debug = Boolean(settingValue(SETTINGS.developerDiagnostics, false));
                    apiNode.inputs.show_preview = Boolean(settingValue(SETTINGS.samplingPreview, true));
                    apiNode.inputs.strict_compatibility = false;
                } else if (
                    node.comfyClass === ASSEMBLE_SEAM_NODE_CLASS
                    || node.comfyClass === V34_ASSEMBLE_SEAM_NODE_CLASS
                    || node.comfyClass === V35_ASSEMBLE_SEAM_NODE_CLASS
                ) {
                    apiNode.inputs.diagnostics = settingValue(SETTINGS.detailedReport, false)
                        ? "Detailed Report"
                        : "Basic";
                    apiNode.inputs.exact_total_duration = true;
                }
            }
            if (!projectWidget) {
                continue;
            }
            let projectId = String(projectWidget.value || "").trim();
            if (!projectId || seen.has(projectId)) {
                projectId = createProjectId();
                projectWidget.value = projectId;
            }
            seen.add(projectId);
            if (apiNode?.inputs) {
                apiNode.inputs.project_id = projectId;
            }
        }
    },
});

function refreshConfiguredNodes() {
    for (const node of app.graph?._nodes || []) {
        configureNodeAfterSetup(node);
    }
}
