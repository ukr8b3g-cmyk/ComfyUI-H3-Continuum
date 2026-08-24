const CONFIGURATION = Symbol("h3ContinuumLastQueuedSeedConfiguration");

function normalizeControlMode(value) {
    if (value === true) return "randomize";
    if (value === false) return "fixed";
    return String(value ?? "").trim().toLowerCase();
}

function sameSeed(left, right) {
    if (left == null || right == null) return false;
    return String(left) === String(right);
}

function clearAutomaticUpdate(state) {
    state.auto_updated_seed = undefined;
    state.auto_update_pending = false;
}

function findSeedWidgets(node) {
    const seedWidget = node.widgets?.find((widget) => widget.name === "base_seed");
    const controlWidget = seedWidget?.linkedWidgets?.find(
        (widget) => widget.name === "control_after_generate",
    ) ?? node.widgets?.find((widget) => widget.name === "control_after_generate");
    return { seedWidget, controlWidget };
}

export function configureLastQueuedSeedReuse(node) {
    const { seedWidget, controlWidget } = findSeedWidgets(node);
    if (!seedWidget || !controlWidget) {
        return false;
    }

    const existing = node[CONFIGURATION];
    if (existing?.seedWidget === seedWidget && existing?.controlWidget === controlWidget) {
        return true;
    }

    const state = {
        last_queued_seed: undefined,
        auto_updated_seed: undefined,
        previous_control_mode: normalizeControlMode(controlWidget.value),
        auto_update_pending: false,
    };
    let applyingAutomaticUpdate = false;
    let restoringQueuedSeed = false;

    const previousSeedCallback = seedWidget.callback;
    seedWidget.callback = function(value, ...args) {
        const result = previousSeedCallback?.call(this, value, ...args);
        if (
            !applyingAutomaticUpdate
            && !restoringQueuedSeed
            && state.auto_update_pending
            && !sameSeed(value, state.auto_updated_seed)
        ) {
            clearAutomaticUpdate(state);
        }
        return result;
    };

    const previousControlCallback = controlWidget.callback;
    controlWidget.callback = function(value, ...args) {
        const priorMode = state.previous_control_mode;
        const result = previousControlCallback?.call(this, value, ...args);
        const nextMode = normalizeControlMode(value ?? controlWidget.value);

        if (priorMode === "randomize" && nextMode === "fixed") {
            if (
                state.auto_update_pending
                && sameSeed(seedWidget.value, state.auto_updated_seed)
                && state.last_queued_seed != null
            ) {
                restoringQueuedSeed = true;
                try {
                    seedWidget.value = state.last_queued_seed;
                    seedWidget.callback?.(state.last_queued_seed);
                } finally {
                    restoringQueuedSeed = false;
                }
            }
            clearAutomaticUpdate(state);
        } else if (nextMode !== "randomize") {
            clearAutomaticUpdate(state);
        }

        state.previous_control_mode = nextMode;
        return result;
    };

    const previousAfterQueued = controlWidget.afterQueued;
    controlWidget.afterQueued = function(...args) {
        const before = seedWidget.value;
        applyingAutomaticUpdate = true;
        let result;
        try {
            result = previousAfterQueued?.apply(this, args);
        } finally {
            applyingAutomaticUpdate = false;
        }
        const after = seedWidget.value;
        const mode = normalizeControlMode(controlWidget.value);
        state.previous_control_mode = mode;

        if (
            mode === "randomize"
            && state.last_queued_seed != null
            && sameSeed(before, state.last_queued_seed)
            && !sameSeed(after, before)
        ) {
            state.auto_updated_seed = after;
            state.auto_update_pending = true;
        }
        return result;
    };

    node[CONFIGURATION] = { seedWidget, controlWidget, state };
    return true;
}

export function captureLastQueuedSeed(node, queuedSeed) {
    if (!configureLastQueuedSeedReuse(node)) {
        return false;
    }

    const configuration = node[CONFIGURATION];
    const { controlWidget, state } = configuration;
    if (queuedSeed == null || Array.isArray(queuedSeed)) {
        state.last_queued_seed = undefined;
        state.previous_control_mode = normalizeControlMode(controlWidget.value);
        clearAutomaticUpdate(state);
        return false;
    }
    state.last_queued_seed = queuedSeed;
    state.previous_control_mode = normalizeControlMode(controlWidget.value);
    clearAutomaticUpdate(state);
    return true;
}
