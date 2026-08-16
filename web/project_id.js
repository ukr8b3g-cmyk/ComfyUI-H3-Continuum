import { app } from "../../scripts/app.js";

const PRODUCTION_NODE_CLASS = "H3ContinuumSamplerProduction";
const TIMELINE_NODE_CLASS = "H3ContinuumSamplerTimelineVideo";
const PROJECT_WIDGET = "project_id";
const LEGACY_RUN_NAME_WIDGET = "run_name";
const CHUNKS_WIDGET = "chunks";
const REGENERATE_WIDGET = "reroll_from_chunk";
const PROMPT_OVERRIDES_INPUT = "prompt_overrides";

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

function hidePersistentWidget(widget) {
    if (!widget || widget.__h3ContinuumHidden) {
        return;
    }
    widget.__h3ContinuumHidden = true;
    widget.hidden = true;
    widget.type = "converted-widget";
    widget.options ||= {};
    widget.options.hidden = true;
    widget.computeSize = () => [0, -4];
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

function configureNode(node) {
    const isProduction = node.comfyClass === PRODUCTION_NODE_CLASS;
    const isTimeline = node.comfyClass === TIMELINE_NODE_CLASS;
    if (!isProduction && !isTimeline) {
        return null;
    }
    const projectWidget = findWidget(node, PROJECT_WIDGET);
    if (isProduction) {
        if (projectWidget && !String(projectWidget.value || "").trim()) {
            projectWidget.value = createProjectId();
        }
        hidePersistentWidget(findWidget(node, LEGACY_RUN_NAME_WIDGET));
        removeUnusedInput(node, PROMPT_OVERRIDES_INPUT);
    }
    hidePersistentWidget(projectWidget);
    configureRegenerateFrom(node);
    node.setDirtyCanvas?.(true, true);
    return isProduction ? projectWidget : null;
}

function configureNodeAfterSetup(node) {
    configureNode(node);
    setTimeout(() => configureNode(node), 0);
    setTimeout(() => configureNode(node), 100);
}

app.registerExtension({
    name: "H3Continuum.ProjectId",

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
            if (!projectWidget) {
                continue;
            }
            let projectId = String(projectWidget.value || "").trim();
            if (!projectId || seen.has(projectId)) {
                projectId = createProjectId();
                projectWidget.value = projectId;
            }
            seen.add(projectId);
            const apiNode = prompt.output?.[String(node.id)];
            if (apiNode?.inputs) {
                apiNode.inputs.project_id = projectId;
            }
        }
    },
});
