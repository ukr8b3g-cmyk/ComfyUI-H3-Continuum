import { app } from "../../scripts/app.js";

const SAMPLER_NODE = "H3ContinuumSamplerV2";
const ADVANCED_PROPERTY = "h3_show_advanced";

const ADVANCED_INPUTS = [
    ["last_frame", "IMAGE"],
    ["session", "H3_CONTINUUM_SESSION"],
    ["initial_state", "H3_CONTINUUM_STATE"],
    ["prompt_plan", "H3_CONTINUUM_PROMPT_PLAN"],
];

const ADVANCED_OUTPUTS = [
    ["last_state", "H3_CONTINUUM_STATE"],
    ["session", "H3_CONTINUUM_SESSION"],
    ["report", "STRING"],
];

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

function inputByName(node, name) {
    return node.inputs?.find((input) => input.name === name);
}

function outputByName(node, name) {
    return node.outputs?.find((output) => output.name === name);
}

function hasAdvancedConnection(node) {
    const inputLinked = ADVANCED_INPUTS.some(([name]) => inputByName(node, name)?.link != null);
    const outputLinked = ADVANCED_OUTPUTS.some(([name]) => {
        const links = outputByName(node, name)?.links;
        return Array.isArray(links) && links.length > 0;
    });
    return inputLinked || outputLinked;
}

function ensureAdvancedSlots(node) {
    for (const [name, type] of ADVANCED_INPUTS) {
        if (!inputByName(node, name)) {
            node.addInput(name, type, { shape: 7 });
        }
    }
    for (const [name, type] of ADVANCED_OUTPUTS) {
        if (!outputByName(node, name)) {
            node.addOutput(name, type);
        }
    }
}

function removeUnlinkedAdvancedSlots(node) {
    if (hasAdvancedConnection(node)) {
        return;
    }
    for (let index = (node.inputs?.length ?? 0) - 1; index >= 0; index -= 1) {
        if (ADVANCED_INPUTS.some(([name]) => node.inputs[index].name === name)) {
            node.removeInput(index);
        }
    }
    for (let index = (node.outputs?.length ?? 0) - 1; index >= 0; index -= 1) {
        if (ADVANCED_OUTPUTS.some(([name]) => node.outputs[index].name === name)) {
            node.removeOutput(index);
        }
    }
}

function setWidgetVisible(widget, visible) {
    if (!widget.__h3V214Original) {
        widget.__h3V214Original = {
            type: widget.type,
            computeSize: widget.computeSize,
            hidden: widget.hidden,
        };
    }
    if (visible) {
        widget.type = widget.__h3V214Original.type;
        widget.computeSize = widget.__h3V214Original.computeSize;
        widget.hidden = widget.__h3V214Original.hidden;
        return;
    }
    widget.type = "hidden";
    widget.computeSize = () => [0, -4];
    widget.hidden = true;
}

function ensureAdvancedButton(node) {
    if (node.__h3V214AdvancedButton) {
        return node.__h3V214AdvancedButton;
    }
    const button = node.addWidget(
        "button",
        "Advanced Settings ▸",
        null,
        () => {
            node.properties ||= {};
            node.properties[ADVANCED_PROPERTY] = !node.properties[ADVANCED_PROPERTY];
            syncAdvancedUi(node);
        },
        { serialize: false },
    );
    button.serialize = false;
    node.__h3V214AdvancedButton = button;
    return button;
}

function placeAdvancedButton(node, button, expanded) {
    const widgets = node.widgets ?? [];
    const currentIndex = widgets.indexOf(button);
    if (currentIndex >= 0) {
        widgets.splice(currentIndex, 1);
    }
    if (!expanded) {
        widgets.push(button);
        return;
    }
    const firstAdvancedIndex = widgets.findIndex((widget) => ADVANCED_WIDGETS.has(widget.name));
    widgets.splice(firstAdvancedIndex >= 0 ? firstAdvancedIndex : widgets.length, 0, button);
}

function resizeNode(node) {
    const computed = node.computeSize();
    const width = Math.max(node.size?.[0] ?? 0, computed[0], 320);
    node.setSize([width, computed[1]]);
    node.setDirtyCanvas(true, true);
}

function syncAdvancedUi(node) {
    node.properties ||= {};
    if (typeof node.properties[ADVANCED_PROPERTY] !== "boolean") {
        node.properties[ADVANCED_PROPERTY] = false;
    }
    if (hasAdvancedConnection(node)) {
        node.properties[ADVANCED_PROPERTY] = true;
    }

    const expanded = node.properties[ADVANCED_PROPERTY];
    if (expanded) {
        ensureAdvancedSlots(node);
    } else {
        removeUnlinkedAdvancedSlots(node);
    }

    for (const widget of node.widgets ?? []) {
        if (ADVANCED_WIDGETS.has(widget.name)) {
            setWidgetVisible(widget, expanded);
        }
    }
    const button = ensureAdvancedButton(node);
    button.name = expanded ? "Advanced Settings ▾" : "Advanced Settings ▸";
    placeAdvancedButton(node, button, expanded);
    resizeNode(node);
}

function scheduleSync(node) {
    clearTimeout(node.__h3V214SyncTimer);
    node.__h3V214SyncTimer = setTimeout(() => syncAdvancedUi(node), 0);
}

app.registerExtension({
    name: "H3Continuum.V214SimplifiedUi",
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== SAMPLER_NODE) {
            return;
        }

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = onNodeCreated?.apply(this, arguments);
            this.properties ||= {};
            if (typeof this.properties[ADVANCED_PROPERTY] !== "boolean") {
                this.properties[ADVANCED_PROPERTY] = false;
            }
            ensureAdvancedButton(this);
            scheduleSync(this);
            return result;
        };

        const onConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function () {
            ensureAdvancedSlots(this);
            const result = onConfigure?.apply(this, arguments);
            ensureAdvancedButton(this);
            scheduleSync(this);
            return result;
        };

        const onConnectionsChange = nodeType.prototype.onConnectionsChange;
        nodeType.prototype.onConnectionsChange = function () {
            const result = onConnectionsChange?.apply(this, arguments);
            scheduleSync(this);
            return result;
        };
    },
});
