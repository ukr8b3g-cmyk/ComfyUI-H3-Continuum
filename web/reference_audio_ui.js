const REFERENCE_AUDIO_WIDGET = "Reference Audio Inputs";
const REFERENCE_AUDIO_HIDDEN = "Hidden";
const REFERENCE_AUDIO_SHOW = "Show";

const INPUT_DEFINITIONS = [
    {
        name: "reference_audio_1",
        type: "AUDIO",
        label: "Reference Audio (Optional)",
        shape: 7,
    },
    {
        name: "reference_audio_vae",
        type: "VAE",
        label: "Reference Audio VAE (Optional)",
        shape: 7,
    },
];

const NORMALIZED_INPUT_LABELS = {
    reference_video_1: "Video Guide Frames",
    driving_audio: "Driving Audio",
    audio_vae: "Driving Audio VAE",
    reference_audio_1: "Reference Audio (Optional)",
    reference_audio_vae: "Reference Audio VAE (Optional)",
};

function findInput(node, name) {
    return node.inputs?.find((input) => input.name === name);
}

function findWidget(node) {
    return node.widgets?.find((widget) => widget.name === REFERENCE_AUDIO_WIDGET);
}

function normalizeInputLabels(node) {
    for (const input of node.inputs || []) {
        const label = NORMALIZED_INPUT_LABELS[input.name];
        if (label) {
            input.label = label;
        }
    }
}

function inputHasLink(input) {
    return input?.link != null && input.link !== -1;
}

function hasReferenceAudioLink(node) {
    return INPUT_DEFINITIONS.some(({ name }) => inputHasLink(findInput(node, name)));
}

function rememberInputDefinitions(node) {
    node.__h3ContinuumReferenceAudioDefinitions ||= {};
    for (const definition of INPUT_DEFINITIONS) {
        const input = findInput(node, definition.name);
        if (!input || node.__h3ContinuumReferenceAudioDefinitions[definition.name]) {
            continue;
        }
        node.__h3ContinuumReferenceAudioDefinitions[definition.name] = {
            name: definition.name,
            type: input.type || definition.type,
            label: definition.label,
            shape: input.shape ?? definition.shape,
            index: node.inputs.indexOf(input),
        };
    }
}

function inputDefinition(node, name) {
    const remembered = node.__h3ContinuumReferenceAudioDefinitions?.[name];
    return remembered || INPUT_DEFINITIONS.find((definition) => definition.name === name);
}

function resizeNode(node) {
    const computed = node.computeSize?.();
    if (computed && node.setSize) {
        const width = Math.max(Number(node.size?.[0]) || 0, Number(computed[0]) || 0);
        node.setSize([width, computed[1]]);
    }
    node.setDirtyCanvas?.(true, true);
}

function showReferenceAudioInputs(node) {
    for (const expected of INPUT_DEFINITIONS) {
        if (findInput(node, expected.name)) {
            continue;
        }
        const definition = inputDefinition(node, expected.name);
        const input = node.addInput?.(definition.name, definition.type, {
            label: definition.label,
            shape: definition.shape,
        });
        const addedIndex = node.inputs?.indexOf(input) ?? -1;
        const rememberedIndex = Number(definition.index);
        const firstWidgetInput = node.inputs?.findIndex(
            (candidate) => candidate.name === "prompt_mode",
        ) ?? -1;
        const requestedIndex = Number.isInteger(rememberedIndex)
            ? rememberedIndex
            : (firstWidgetInput >= 0 ? firstWidgetInput : node.inputs.length - 1);
        const targetIndex = Math.min(
            Math.max(0, requestedIndex),
            Math.max(0, node.inputs.length - 1),
        );
        if (addedIndex >= 0 && addedIndex !== targetIndex) {
            node.inputs.splice(addedIndex, 1);
            node.inputs.splice(targetIndex, 0, input);
        }
    }
    normalizeInputLabels(node);
    return INPUT_DEFINITIONS.every(({ name }) => Boolean(findInput(node, name)));
}

function hideReferenceAudioInputs(node) {
    if (hasReferenceAudioLink(node)) {
        return false;
    }
    const indices = INPUT_DEFINITIONS.map(({ name }) =>
        node.inputs?.findIndex((input) => input.name === name) ?? -1
    );
    for (const index of indices.filter((index) => index >= 0).sort((left, right) => right - left)) {
        node.removeInput?.(index);
    }
    return INPUT_DEFINITIONS.every(({ name }) => !findInput(node, name));
}

function setReferenceAudioVisibility(node, widget, show) {
    rememberInputDefinitions(node);
    const applied = show
        ? showReferenceAudioInputs(node)
        : hideReferenceAudioInputs(node);
    if (!applied) {
        showReferenceAudioInputs(node);
        widget.value = REFERENCE_AUDIO_SHOW;
    }
    resizeNode(node);
    return applied;
}

function ensureVisibilityWidget(node) {
    let widget = findWidget(node);
    if (widget) {
        return widget;
    }
    if (!node.addWidget) {
        return null;
    }
    const initialValue = hasReferenceAudioLink(node)
        ? REFERENCE_AUDIO_SHOW
        : REFERENCE_AUDIO_HIDDEN;
    widget = node.addWidget(
        "combo",
        REFERENCE_AUDIO_WIDGET,
        initialValue,
        (value) => {
            setReferenceAudioVisibility(
                node,
                widget,
                value === REFERENCE_AUDIO_SHOW,
            );
        },
        { values: [REFERENCE_AUDIO_HIDDEN, REFERENCE_AUDIO_SHOW] },
    );
    widget.options ||= {};
    widget.options.serialize = false;
    widget.serializeValue = () => undefined;
    return widget;
}

function attachWorkflowSerializationGuard(node, widget) {
    if (node.__h3ContinuumReferenceAudioSerializationGuard) {
        return;
    }
    const previous = node.onSerialize;
    node.onSerialize = function(info, ...args) {
        const result = previous?.call(this, info, ...args);
        const widgetIndex = node.widgets?.indexOf(widget) ?? -1;
        if (
            widgetIndex >= 0
            && Array.isArray(info?.widgets_values)
            && widgetIndex === node.widgets.length - 1
            && info.widgets_values.length === node.widgets.length
        ) {
            info.widgets_values.pop();
        }
        return result;
    };
    node.__h3ContinuumReferenceAudioSerializationGuard = true;
}

function attachConnectionRefresh(node, widget) {
    if (node.__h3ContinuumReferenceAudioConnectionCallback) {
        return;
    }
    const previous = node.onConnectionsChange;
    node.onConnectionsChange = function(...args) {
        const result = previous?.apply(this, args);
        setTimeout(() => {
            normalizeInputLabels(node);
            if (hasReferenceAudioLink(node)) {
                widget.value = REFERENCE_AUDIO_SHOW;
                setReferenceAudioVisibility(node, widget, true);
            }
        }, 0);
        return result;
    };
    node.__h3ContinuumReferenceAudioConnectionCallback = true;
}

export function configureReferenceAudioInputs(node) {
    if (!node) {
        return false;
    }
    normalizeInputLabels(node);
    rememberInputDefinitions(node);
    const widget = ensureVisibilityWidget(node);
    if (!widget) {
        return false;
    }
    attachWorkflowSerializationGuard(node, widget);
    if (hasReferenceAudioLink(node)) {
        widget.value = REFERENCE_AUDIO_SHOW;
    }
    setReferenceAudioVisibility(
        node,
        widget,
        widget.value === REFERENCE_AUDIO_SHOW,
    );
    attachConnectionRefresh(node, widget);
    return true;
}
