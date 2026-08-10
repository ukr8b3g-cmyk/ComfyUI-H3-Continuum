import { app } from "../../../scripts/app.js";

const NODE_NAME = "H3ContinuumSamplerV2";
const PREVIEW_SETTING = "H3Continuum.ShowLatentPreview";
const PROMPT_INPUT = /^clip_(\d+)_prompt$/;
const SEQUENCE_PROMPT_INPUT = "sequence_prompt";
const OVERRIDE_PROPERTY = "h3_show_clip_overrides";
const MAX_CHUNKS = 16;
const LEGACY_PROMPT_FORMATS = new Map([
    ["Fixed — one prompt", "Fixed"],
    ["List — split with ---", "List"],
    ["Timeline — [0-5s] sections", "Timeline"],
]);

let showLatentPreview = true;

function hideWidget(widget) {
    if (!widget) return;
    if (!widget.__h3ContinuumHidden) {
        widget.__h3ContinuumHidden = true;
        widget.type = "converted-widget";
        widget.computeSize = () => [0, -4];
    }
    widget.hidden = true;
    for (const element of [widget.element, widget.inputEl, widget.el]) {
        if (element?.style) element.style.display = "none";
    }
}

function promptInputName(index) {
    return `clip_${index}_prompt`;
}

function inputIsConnected(input) {
    return input?.link != null || (Array.isArray(input?.links) && input.links.length > 0);
}

function overridesExpanded(node) {
    return node.properties?.[OVERRIDE_PROPERTY] === true;
}

function syncPromptFormat(node) {
    const widget = node.widgets?.find((candidate) => candidate.name === "prompt_mode");
    if (!widget) return;
    if (LEGACY_PROMPT_FORMATS.has(widget.value)) {
        widget.value = LEGACY_PROMPT_FORMATS.get(widget.value);
    }
    widget.label = "Prompt Format";
}

function syncSequencePrompt(node) {
    const input = node.inputs?.find((candidate) => candidate.name === SEQUENCE_PROMPT_INPUT);
    if (input) input.label = "Sequence Prompt";
}

function syncPromptInputs(node) {
    const chunksWidget = node.widgets?.find((widget) => widget.name === "chunks");
    const chunks = Math.max(1, Math.min(MAX_CHUNKS, Number(chunksWidget?.value) || 1));
    const expanded = overridesExpanded(node);

    for (let index = node.inputs.length - 1; index >= 0; index -= 1) {
        const input = node.inputs[index];
        const match = PROMPT_INPUT.exec(input.name);
        if (!match) continue;
        const clipIndex = Number(match[1]);
        const active = clipIndex <= chunks;
        if ((!expanded || !active) && !inputIsConnected(input)) {
            node.removeInput(index);
        } else {
            input.label = active
                ? "Clip " + clipIndex + " Prompt Override"
                : "Clip " + clipIndex + " Override (inactive)";
        }
    }

    if (!expanded) return;
    for (let index = 1; index <= chunks; index += 1) {
        const name = promptInputName(index);
        if (!node.inputs.some((input) => input.name === name)) {
            node.addInput(name, "STRING");
        }
        const input = node.inputs.find((candidate) => candidate.name === name);
        if (input) input.label = "Clip " + index + " Prompt Override";
    }
}

function ensureOverrideToggle(node) {
    node.properties ||= {};
    if (typeof node.properties[OVERRIDE_PROPERTY] !== "boolean") {
        node.properties[OVERRIDE_PROPERTY] = false;
    }
    let widget = node.widgets?.find((candidate) => candidate.__h3OverrideToggle);
    if (!widget) {
        widget = node.addWidget(
            "button",
            "Individual Clip Overrides ▸",
            null,
            () => {
                node.properties[OVERRIDE_PROPERTY] = !overridesExpanded(node);
                syncNode(node);
            },
            { serialize: false },
        );
        widget.__h3OverrideToggle = true;
        widget.serialize = false;
        const widgets = node.widgets || [];
        const currentIndex = widgets.indexOf(widget);
        const formatIndex = widgets.findIndex((candidate) => candidate.name === "prompt_mode");
        if (currentIndex >= 0 && formatIndex >= 0) {
            widgets.splice(currentIndex, 1);
            widgets.splice(formatIndex + 1, 0, widget);
        }
    }
    widget.name = overridesExpanded(node)
        ? "Individual Clip Overrides ▾"
        : "Individual Clip Overrides ▸";
}

function syncPreviewSetting(node) {
    const widget = node.widgets?.find((candidate) => candidate.name === "show_preview");
    if (!widget) return;
    hideWidget(widget);
    widget.value = showLatentPreview;
}

function repairLegacySeamCorrection(node) {
    const widget = node.widgets?.find((candidate) => candidate.name === "seam_correction");
    if (widget && typeof widget.value === "boolean") widget.value = "Off";
}

function resizeNode(node) {
    const size = node.computeSize();
    node.setSize([Math.max(node.size[0], size[0]), size[1]]);
    node.setDirtyCanvas(true, true);
}

function syncNode(node) {
    hideWidget(node.widgets?.find((widget) => widget.name === "prompt_script"));
    syncPromptFormat(node);
    syncSequencePrompt(node);
    ensureOverrideToggle(node);
    repairLegacySeamCorrection(node);
    syncPromptInputs(node);
    syncPreviewSetting(node);
    resizeNode(node);
}

function wrapChunksWidget(node) {
    const widget = node.widgets?.find((candidate) => candidate.name === "chunks");
    if (!widget || widget.__h3ContinuumWrapped) return;
    widget.__h3ContinuumWrapped = true;
    const originalCallback = widget.callback;
    widget.callback = function (...args) {
        const result = originalCallback?.apply(this, args);
        queueMicrotask(() => syncNode(node));
        return result;
    };
}

function syncAllSamplerNodes() {
    for (const node of app.graph?._nodes || []) {
        if (node.comfyClass === NODE_NAME || node.type === NODE_NAME) {
            syncPreviewSetting(node);
            node.setDirtyCanvas(true, true);
        }
    }
}

app.registerExtension({
    name: "H3Continuum.V2Interface",

    async setup() {
        showLatentPreview = app.ui.settings.getSettingValue(PREVIEW_SETTING) ?? true;
        app.ui.settings.addSetting({
            id: PREVIEW_SETTING,
            name: "Show latent preview",
            category: ["H3 Continuum", "Preview", "Show latent preview"],
            tooltip: "Show the in-progress latent thumbnail inside H3 Continuum Sampler V2 nodes.",
            type: "boolean",
            defaultValue: true,
            onChange(value) {
                showLatentPreview = value !== false;
                syncAllSamplerNodes();
            },
        });
    },

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_NAME) return;

        const originalCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = originalCreated?.apply(this, arguments);
            setTimeout(() => {
                wrapChunksWidget(this);
                syncNode(this);
            }, 0);
            return result;
        };

        const originalConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function () {
            const result = originalConfigure?.apply(this, arguments);
            setTimeout(() => {
                wrapChunksWidget(this);
                syncNode(this);
            }, 0);
            return result;
        };
    },
});
