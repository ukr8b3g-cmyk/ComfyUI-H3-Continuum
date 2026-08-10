import { app } from "../../../scripts/app.js";

const NODE_NAME = "H3ContinuumSamplerV2";
const PREVIEW_SETTING = "H3Continuum.ShowLatentPreview";
const PROMPT_INPUT = /^clip_(\d+)_prompt$/;
const SEQUENCE_PROMPT_INPUT = "sequence_prompt";
const CLIP_OVERRIDES_PROPERTY = "h3_show_clip_overrides";
const ADVANCED_PROPERTY = "h3_show_advanced";
const ADVANCED_INPUTS = new Set(["last_frame", "session", "initial_state", "prompt_plan"]);
const ADVANCED_OUTPUTS = new Set(["last_state", "session", "report"]);
const MAX_CHUNKS = 16;
const VISIBILITY_STYLE_ID = "h3-continuum-v215-slot-visibility";
const ADVANCED_WIDGETS = new Set([
    "control_after_generate",
    "audio_continuity",
    "exact_total_duration",
    "diagnostics",
    "reroll_from_chunk",
    "reroll_nonce",
    "strict_compatibility",
    "debug",
    "show_preview",
]);
const LEGACY_PROMPT_FORMATS = new Map([
    ["Fixed — one prompt", "Fixed"],
    ["List — split with ---", "List"],
    ["Timeline — [0-5s] sections", "Timeline"],
]);

let showLatentPreview = true;

function setWidgetCollapsed(widget, reason, collapsed) {
    if (!widget) return;
    if (!widget.__h3ContinuumCollapseState) {
        widget.__h3ContinuumCollapseState = {
            computeSize: widget.computeSize,
            hiddenOption: widget.options?.hidden,
            reasons: new Set(),
        };
    }
    const state = widget.__h3ContinuumCollapseState;
    if (collapsed) {
        state.reasons.add(reason);
    } else {
        state.reasons.delete(reason);
    }
    const hidden = state.reasons.size > 0;
    widget.options ||= {};
    if (hidden) {
        widget.options.hidden = true;
    } else if (state.hiddenOption === undefined) {
        delete widget.options.hidden;
    } else {
        widget.options.hidden = state.hiddenOption;
    }
    widget.computeSize = hidden ? () => [0, -4] : state.computeSize;
    for (const element of [widget.element, widget.inputEl, widget.el]) {
        if (element?.style) element.style.display = hidden ? "none" : "";
    }
}

function serializableWidgets(widgets) {
    return widgets.filter((widget) => widget.serialize !== false);
}

function placeTransientAfter(node, transient, anchor) {
    const original = node.widgets ?? [];
    const serializedBefore = serializableWidgets(original);
    const withoutTransient = original.filter((widget) => widget !== transient);
    const anchorIndex = withoutTransient.findIndex((widget) =>
        typeof anchor === "string" ? widget.name === anchor : widget === anchor,
    );
    if (anchorIndex < 0) return;
    const next = [
        ...withoutTransient.slice(0, anchorIndex + 1),
        transient,
        ...withoutTransient.slice(anchorIndex + 1),
    ];
    const serializedAfter = serializableWidgets(next);
    const stable = serializedBefore.length === serializedAfter.length
        && serializedBefore.every((widget, index) => widget === serializedAfter[index]);
    if (!stable) throw new Error("H3 Continuum refused to reorder serialized widgets");
    node.widgets = next;
}

function inputIsConnected(input) {
    return input?.link != null || (Array.isArray(input?.links) && input.links.length > 0);
}

function outputIsConnected(output) {
    return Array.isArray(output?.links) && output.links.length > 0;
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

function clipOverridesExpanded(node) {
    return node.properties?.[CLIP_OVERRIDES_PROPERTY] === true;
}

function ensureClipOverridesButton(node) {
    if (node.__h3ContinuumClipOverridesButton) {
        return node.__h3ContinuumClipOverridesButton;
    }
    const button = node.addWidget(
        "button",
        "Individual Clip Overrides ▸",
        null,
        () => {
            node.properties ||= {};
            node.properties[CLIP_OVERRIDES_PROPERTY] = !clipOverridesExpanded(node);
            syncNode(node);
        },
        { serialize: false },
    );
    button.serialize = false;
    button.__h3ContinuumTransient = true;
    node.__h3ContinuumClipOverridesButton = button;
    return button;
}

function syncPromptInputs(node) {
    node.properties ||= {};
    if (typeof node.properties[CLIP_OVERRIDES_PROPERTY] !== "boolean") {
        node.properties[CLIP_OVERRIDES_PROPERTY] = false;
    }
    const chunksWidget = node.widgets?.find((widget) => widget.name === "chunks");
    const chunks = Math.max(1, Math.min(MAX_CHUNKS, Number(chunksWidget?.value) || 1));
    const expanded = clipOverridesExpanded(node);
    for (const input of node.inputs ?? []) {
        const match = PROMPT_INPUT.exec(input.name);
        if (!match) continue;
        const clipIndex = Number(match[1]);
        input.label = clipIndex <= chunks
            ? "Clip " + clipIndex + " Prompt Override"
            : "Clip " + clipIndex + " Override (inactive)";
    }
    const button = ensureClipOverridesButton(node);
    placeTransientAfter(node, button, "prompt_mode");
    button.name = expanded
        ? "Individual Clip Overrides (" + chunks + ") ▾"
        : "Individual Clip Overrides (" + chunks + ") ▸";
}

function advancedExpanded(node) {
    return node.properties?.[ADVANCED_PROPERTY] === true;
}

function ensureAdvancedButton(node) {
    if (node.__h3ContinuumAdvancedButton) return node.__h3ContinuumAdvancedButton;
    const button = node.addWidget(
        "button",
        "Advanced Settings ▸",
        null,
        () => {
            node.properties ||= {};
            node.properties[ADVANCED_PROPERTY] = !advancedExpanded(node);
            syncNode(node);
        },
        { serialize: false },
    );
    button.serialize = false;
    button.__h3ContinuumTransient = true;
    node.__h3ContinuumAdvancedButton = button;
    return button;
}

function syncAdvancedWidgets(node) {
    node.properties ||= {};
    if (typeof node.properties[ADVANCED_PROPERTY] !== "boolean") {
        node.properties[ADVANCED_PROPERTY] = false;
    }
    if (
        (node.inputs ?? []).some((input) => ADVANCED_INPUTS.has(input.name) && inputIsConnected(input))
        || (node.outputs ?? []).some((output) => ADVANCED_OUTPUTS.has(output.name) && outputIsConnected(output))
    ) {
        node.properties[ADVANCED_PROPERTY] = true;
    }
    const expanded = advancedExpanded(node);
    for (const widget of node.widgets ?? []) {
        if (ADVANCED_WIDGETS.has(widget.name)) {
            setWidgetCollapsed(widget, "advanced", !expanded);
        }
    }
    const button = ensureAdvancedButton(node);
    button.name = expanded ? "Advanced Settings ▾" : "Advanced Settings ▸";
}

function syncPreviewSetting(node) {
    const widget = node.widgets?.find((candidate) => candidate.name === "show_preview");
    if (!widget) return;
    setWidgetCollapsed(widget, "preview-setting", true);
    widget.value = showLatentPreview;
}

function repairLegacySeamCorrection(node) {
    const widget = node.widgets?.find((candidate) => candidate.name === "seam_correction");
    if (widget && typeof widget.value === "boolean") widget.value = "Off";
}

function ensureSeamCorrectionProxy(node) {
    const source = node.widgets?.find((widget) => widget.name === "seam_correction");
    if (!source) return null;
    if (typeof source.value === "boolean") source.value = "Off";
    setWidgetCollapsed(source, "seam-proxy", true);

    let proxy = node.__h3ContinuumSeamProxy;
    if (!proxy) {
        proxy = node.addWidget(
            "combo",
            "Seam Correction",
            source.value,
            (value) => {
                source.value = value;
                source.callback?.call(source, value);
            },
            { values: source.options?.values ?? ["Auto", "Off", "Basic"], serialize: false },
        );
        proxy.serialize = false;
        proxy.__h3ContinuumTransient = true;
        node.__h3ContinuumSeamProxy = proxy;
    }
    proxy.value = source.value;
    placeTransientAfter(node, proxy, "base_seed");
    return proxy;
}

function cssAttributeValue(value) {
    return String(value).replaceAll("\\", "\\\\").replaceAll('"', '\\"');
}

function shouldHideInput(node, input, chunks) {
    const promptMatch = PROMPT_INPUT.exec(input.name);
    if (promptMatch) {
        const clipIndex = Number(promptMatch[1]);
        return !inputIsConnected(input)
            && (!clipOverridesExpanded(node) || clipIndex > chunks);
    }
    return ADVANCED_INPUTS.has(input.name)
        && !advancedExpanded(node)
        && !inputIsConnected(input);
}

function slotVisibilityRules(node) {
    const id = cssAttributeValue(node.id);
    const root = `.lg-node[data-node-id="${id}"]`;
    const chunksWidget = node.widgets?.find((widget) => widget.name === "chunks");
    const chunks = Math.max(1, Math.min(MAX_CHUNKS, Number(chunksWidget?.value) || 1));
    const rules = [];
    const renderedInputs = (node.inputs ?? []).filter((input) => !input.widget);
    renderedInputs.forEach((input, index) => {
        if (shouldHideInput(node, input, chunks)) {
            rules.push(`${root} .lg-slot--input:nth-child(${index + 1}) { display: none !important; }`);
        }
    });
    (node.outputs ?? []).forEach((output, index) => {
        if (
            ADVANCED_OUTPUTS.has(output.name)
            && !advancedExpanded(node)
            && !outputIsConnected(output)
        ) {
            rules.push(`${root} .lg-slot--output:nth-child(${index + 1}) { display: none !important; }`);
        }
    });
    return rules;
}

function syncSlotVisibilityStyles() {
    let style = document.getElementById(VISIBILITY_STYLE_ID);
    if (!style) {
        style = document.createElement("style");
        style.id = VISIBILITY_STYLE_ID;
        document.head.appendChild(style);
    }
    style.textContent = (app.graph?._nodes ?? [])
        .filter((node) => node.comfyClass === NODE_NAME || node.type === NODE_NAME)
        .flatMap(slotVisibilityRules)
        .join("\n");
}

function resizeNode(node) {
    node.setSize([Math.max(node.size?.[0] ?? 0, 320), 120]);
    node.setDirtyCanvas(true, true);
}

function syncNode(node) {
    setWidgetCollapsed(
        node.widgets?.find((widget) => widget.name === "prompt_script"),
        "prompt-script",
        true,
    );
    syncPromptFormat(node);
    syncSequencePrompt(node);
    repairLegacySeamCorrection(node);
    syncPromptInputs(node);
    const seamProxy = ensureSeamCorrectionProxy(node);
    syncAdvancedWidgets(node);
    if (seamProxy) {
        placeTransientAfter(node, node.__h3ContinuumAdvancedButton, seamProxy);
    }
    syncPreviewSetting(node);
    syncSlotVisibilityStyles();
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

function scheduleSync(node) {
    clearTimeout(node.__h3ContinuumSyncTimer);
    node.__h3ContinuumSyncTimer = setTimeout(() => {
        wrapChunksWidget(node);
        syncNode(node);
    }, 0);
}

function syncAllSamplerNodes() {
    for (const node of app.graph?._nodes || []) {
        if (node.comfyClass === NODE_NAME || node.type === NODE_NAME) {
            syncNode(node);
        }
    }
}

app.registerExtension({
    name: "H3Continuum.V215StableInterface",

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
            scheduleSync(this);
            return result;
        };

        const originalConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function () {
            const result = originalConfigure?.apply(this, arguments);
            scheduleSync(this);
            return result;
        };

        const originalConnectionsChange = nodeType.prototype.onConnectionsChange;
        nodeType.prototype.onConnectionsChange = function () {
            const result = originalConnectionsChange?.apply(this, arguments);
            scheduleSync(this);
            return result;
        };
    },
});
