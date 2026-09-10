import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { normalizeReferenceAudioLabels } from "./reference_audio_ui.js";

const PRODUCTION_NODE_CLASS = "H3ContinuumSamplerProduction";
const TIMELINE_NODE_CLASS = "H3ContinuumSamplerTimelineVideo";
const ASSEMBLE_SEAM_NODE_CLASS = "H3ContinuumAssembleSeamExperimental";
const V34_NODE_CLASS = "H3ContinuumSamplerV34";
const V34_ASSEMBLE_SEAM_NODE_CLASS = "H3ContinuumAssembleSeamV34";
const V35_NODE_CLASS = "H3ContinuumSamplerV35";
const V36_NODE_CLASS = "H3ContinuumSamplerV36";
const V37_NODE_CLASS = "H3ContinuumSamplerV37";
const V38_NODE_CLASS = "H3ContinuumSamplerV38";
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
const RESOLUTION_PRESET_WIDGET = "preset";
const CUSTOM_MP_WIDGET = "custom_mp";
const CUSTOM_RESOLUTION_PRESET = "Custom";
const LEGACY_ASPECT_WIDGET = "aspect";
const SIZE_SOURCE_WIDGET = "size_source";
const WIDTH_WIDGET = "width";
const HEIGHT_WIDGET = "height";
const SIZE_SOURCE_FIRST_IMAGE = "First Image";
const SIZE_SOURCE_MANUAL = "Manual";
const SIZE_SOURCE_LEGACY = "Legacy Aspect";
const RESOLUTION_PRESET_DRAFT = "Draft — 0.30 MP";
const RESOLUTION_PRESET_BALANCED = "Balanced — 0.60 MP";
const RESOLUTION_PRESET_NATIVE = "Native 768";
const CANVAS_MULTIPLE = 32;
const NATIVE_SHORT_EDGE = 768;
const NATIVE_LONG_EDGE_CAP = 1344;
const GENERATION_MODE_WIDGET = "generation_mode";
const REVIEW_ACTION_WIDGET = "review_action";
const GENERATION_MODE_FULL_RUN = "Full Run";
const GENERATION_MODE_REVIEW = "Review Each Chunk";
const REVIEW_ACTION_CONTINUE = "Continue / Next";
const REVIEW_ACTION_REGENERATE = "Regenerate Current";
const REVIEW_ACTION_FINISH = "Finish Remaining";
const TAKE_GROUP_WIDGET = "take_group";
const TAKE_REVISION_WIDGET = "take_revision_id";
const TAKE_ACTION_WIDGET = "take_action";
const TAKE_ACTION_AUTOMATIC = "Automatic";
const TAKE_ACTION_USE = "Use This Take";
const TAKE_ACTION_CONTINUE = "Continue From Here";
const REVIEW_PENDING_ACTION = "__h3ContinuumPendingReviewAction";
const REVIEW_UI_SELECTION = "__h3ContinuumReviewUiSelection";
const TAKE_PENDING_ACTION = "__h3ContinuumPendingTakeAction";
const PRODUCTION_STATUS_WIDGET = "Review Ready";
const PRODUCTION_CONTINUE_WIDGET = "Use it and continue";
const PRODUCTION_REGENERATE_WIDGET = "Try this chunk again";
const PRODUCTION_FINISH_WIDGET = "Use it and finish the rest";
const PRODUCTION_BACK_TO_SETTINGS_WIDGET = "Back to Settings";
const PRODUCTION_RETURN_TO_REVIEW_WIDGET = "Return to Review";
const PRODUCTION_RESTART_WIDGET = "Start again from Chunk 1";
const PRODUCTION_OUTPUT_RETRY_WIDGET = "Retry saved output";
const TAKE_STATUS_WIDGET = "Render History / Takes";
const TAKE_TOGGLE_WIDGET = "Render History";
const TAKE_PREVIOUS_WIDGET = "Previous Take";
const TAKE_NEXT_WIDGET = "Next Take";
const TAKE_USE_WIDGET = "Use This Take";
const TAKE_CONTINUE_WIDGET = "Continue From Here";
const PRODUCTION_TRANSIENT_WIDGET = "__h3ContinuumProductionTransient";
const FACADE_TRANSIENT_WIDGET = "__h3ContinuumFacadeTransient";
const FACADE_PROMPT_FORMAT_WIDGET = "Prompt Format";
const FACADE_CONTINUITY_WIDGET = "Continuity";
const FACADE_BASE_SEED_WIDGET = "Base Seed";
const FACADE_CONTROL_AFTER_WIDGET = "Control After Generate";
const FACADE_AUDIO_CONTINUITY_WIDGET = "Audio Continuity";
const FACADE_CHUNKS_WIDGET = "Chunks";
const FACADE_SECONDS_WIDGET = "Seconds per Chunk";
const FACADE_TOTAL_LENGTH_WIDGET = "Total Length";
const FACADE_SIZE_SOURCE_WIDGET = "Size Source";
const FACADE_RESOLUTION_WIDGET = "Resolution";
const FACADE_CUSTOM_MP_WIDGET = "Custom MP";
const FACADE_WIDTH_WIDGET = "Width";
const FACADE_HEIGHT_WIDGET = "Height";
const FACADE_GENERATE_WIDGET = "Run";
const FACADE_SAVE_WIDGET = "Progress";
const FACADE_READY_WIDGET = "Ready to Queue";
const FACADE_REFERENCE_SIZE_WIDGET = "Reference Image Size";
const FACADE_VIDEO_SIZE_WIDGET = "Video Guide Size";
const FACADE_ADVANCED_WIDGET = "Advanced Settings";
const FACADE_GENERATE_ALL = "Generate Full Video";
const FACADE_GENERATE_REVIEW = "Review Each Chunk";
const FACADE_SAVE_OFF = "Off — No resume or Take history";
const FACADE_SAVE_ON = "On — Resume and Takes available";
const FACADE_HELP = Object.freeze({
    [FACADE_PROMPT_FORMAT_WIDGET]: (
        "Prompt interpretation mode. Auto accepts Fixed text, Timeline/List syntax, or JSON and "
        + "uses the first valid format it detects."
    ),
    [FACADE_CONTINUITY_WIDGET]: (
        "Video continuation overlap between chunks. Balanced — 22 frames is the normal Production default."
    ),
    [FACADE_BASE_SEED_WIDGET]: (
        "Base seed used for deterministic chunk seed derivation. Keep it fixed to reproduce the same run."
    ),
    [FACADE_CONTROL_AFTER_WIDGET]: (
        "What ComfyUI does to Base Seed after Queue. randomize chooses a new seed for the next Queue; "
        + "fixed keeps it unchanged."
    ),
    [FACADE_AUDIO_CONTINUITY_WIDGET]: (
        "Preserves audio continuation across chunk boundaries. Keep this On for normal audiovisual generation."
    ),
    [FACADE_CHUNKS_WIDGET]: (
        "Number of Continuum chunks to generate. This is an explicit setting and is never "
        + "recalculated from Total Length."
    ),
    [FACADE_SECONDS_WIDGET]: (
        "Duration of each chunk in seconds. Set this directly, for example 3 chunks × 10 seconds."
    ),
    [FACADE_TOTAL_LENGTH_WIDGET]: (
        "Read-only total duration calculated from Chunks × Seconds per Chunk. It never changes either setting."
    ),
    [FACADE_GENERATE_WIDGET]: (
        "Generate Full Video creates all remaining chunks in one Queue. Review Each Chunk pauses "
        + "after each physical group so you can keep it, try it again, or finish the rest."
    ),
    [FACADE_SIZE_SOURCE_WIDGET]: (
        "First Image preserves the selected First Image aspect ratio. Manual uses the exact Width "
        + "and Height below. This choice is explicit and is not changed automatically."
    ),
    [FACADE_RESOLUTION_WIDGET]: (
        "Resolution preset used with First Image sizing. Draft uses least memory, Balanced adds detail, "
        + "Native 768 uses the H3 native short edge, and Custom uses Custom MP."
    ),
    [FACADE_CUSTOM_MP_WIDGET]: (
        "Custom target megapixels while preserving the First Image aspect ratio. The final "
        + "Width and Height are aligned to the H3 canvas requirements."
    ),
    [FACADE_WIDTH_WIDGET]: (
        "Exact output width used in Manual mode. Use a multiple of 32. Manual Width and Height "
        + "are suitable for T2VA or any workflow without a First Image."
    ),
    [FACADE_HEIGHT_WIDGET]: (
        "Exact output height used in Manual mode. Use a multiple of 32. Manual Width and Height "
        + "are suitable for T2VA or any workflow without a First Image."
    ),
    [FACADE_SAVE_WIDGET]: (
        "On saves chunk progress atomically for safe resume and Take history. Review Each Chunk "
        + "turns this on automatically."
    ),
    [FACADE_READY_WIDGET]: (
        "Plain-language summary of what the next normal Queue will do. It uses current graph links "
        + "and widget values and does not change the backend contract."
    ),
    [FACADE_REFERENCE_SIZE_WIDGET]: (
        "Controls only connected Reference Images. Match Output is the practical default. "
        + "Max Identity preserves more reference detail but can use more memory."
    ),
    [FACADE_VIDEO_SIZE_WIDGET]: (
        "Controls only connected Video Guide Frames. Efficient uses about 0.4 MP, Balanced "
        + "about 0.6 MP, and Match Output uses the output pixel area."
    ),
    [FACADE_ADVANCED_WIDGET]: (
        "Show or hide technical controls such as prompt parsing, continuity strength, seed, "
        + "audio continuity, continuation backend, and explicit regeneration."
    ),
});
const ADVANCED_WIDGET_HELP = Object.freeze({
    prompt_mode: (
        "How Sequence Prompt is interpreted. Auto detects Fixed, list-separated, and "
        + "[time] timeline formats."
    ),
    continuity: (
        "Amount of prior video context retained at each chunk boundary. Balanced - 22 frames "
        + "is the Production default; Strong - 39 frames is experimental."
    ),
    base_seed: (
        "Base seed used to derive deterministic per-chunk seeds. Keep it fixed when comparing "
        + "settings or Takes."
    ),
    control_after_generate: (
        "Controls how Base Seed changes after Queue. Use fixed/keep for repeatable comparisons; "
        + "randomize creates a new base seed for the next Queue."
    ),
    audio_continuity: (
        "On carries previous generated-audio context across chunk boundaries. Turn it off only "
        + "when isolating or replacing generated audio."
    ),
    continuation_backend: (
        "Standard uses the current V3.8 continuation path. Compatibility restores the older "
        + "Reference Context path for comparison or older workflows."
    ),
    reroll_from_chunk: (
        "Auto resumes the longest compatible saved prefix. Selecting a chunk reuses everything "
        + "before it and regenerates that chunk and all following chunks."
    ),
    run_name: (
        "Optional stable name for Resume and Render History. Leave blank to use the sampler's "
        + "automatic project identity."
    ),
    reroll_nonce: (
        "Variation number for an explicit regeneration. Change it to create another Take while "
        + "keeping the same prompt, seed, and other settings."
    ),
});
const V38_VIEW_PROPERTY = "H3 Continuum View";
const V38_VIEW_BASIC = "Basic";
const V38_VIEW_PRODUCTION = "Production";
const V38_VIEW_OPTIONS = [V38_VIEW_BASIC, V38_VIEW_PRODUCTION];
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

function activeLinkedInput(node, names) {
    const inputs = node.inputs?.filter(
        (item) => names.includes(item.name) && item.link != null,
    ) || [];
    return inputs.some((input) => {
        const link = app.graph?.links?.[input.link];
        if (!link) return true;
        const source = app.graph?.getNodeById?.(link.origin_id);
        if (!source) return true;
        if ([2, 4].includes(Number(source.mode))) return false;
        const enableWidget = source.widgets?.find((widget) => (
            [
                "Enable Image",
                "Enable Video",
                "Enable Audio",
                "enable_image",
                "enable_video",
                "enable_audio",
            ].includes(widget.name)
        ));
        if (!enableWidget) return true;
        const value = enableWidget.value;
        if (typeof value === "boolean") return value;
        return !["off", "false", "disabled", "0", ""].includes(
            String(value).trim().toLowerCase(),
        );
    });
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

function transientProductionWidgets(node) {
    return node.widgets?.filter((widget) => widget[PRODUCTION_TRANSIENT_WIDGET]) || [];
}

function installProductionSerializationGuard(node) {
    if (node.__h3ContinuumProductionSerializationGuard) return;
    const withoutTransientWidgets = (callback, owner, args) => {
        const widgets = owner.widgets;
        if (!Array.isArray(widgets)) return callback.apply(owner, args);
        const removed = [];
        for (let index = widgets.length - 1; index >= 0; index -= 1) {
            if (widgets[index]?.[PRODUCTION_TRANSIENT_WIDGET]) {
                removed.push({ index, widget: widgets[index] });
                widgets.splice(index, 1);
            }
        }
        try {
            return callback.apply(owner, args);
        } finally {
            removed.sort((left, right) => left.index - right.index);
            for (const item of removed) {
                widgets.splice(Math.min(item.index, widgets.length), 0, item.widget);
            }
        }
    };
    const originalSerialize = node.serialize;
    if (typeof originalSerialize === "function") {
        node.serialize = function(...args) {
            return withoutTransientWidgets(originalSerialize, this, args);
        };
    }
    const originalConfigure = node.configure;
    if (typeof originalConfigure === "function") {
        node.configure = function(...args) {
            return withoutTransientWidgets(originalConfigure, this, args);
        };
    }
    node.__h3ContinuumProductionSerializationGuard = true;
}

function addTransientProductionWidget(node, type, name, value, callback, options = {}) {
    if (typeof node.addWidget !== "function") return null;
    const widget = node.addWidget(
        type,
        name,
        value,
        callback,
        { ...options, serialize: false },
    );
    if (!widget) return null;
    widget[PRODUCTION_TRANSIENT_WIDGET] = true;
    widget.serialize = false;
    widget.options ||= {};
    widget.options.serialize = false;
    return widget;
}

function setExistingWidgetValue(widget, value) {
    if (!widget || widget.value === value) return;
    widget.value = value;
    widget.callback?.(value);
}

function setRegenerateProgrammatically(node, value) {
    const widget = findWidget(node, REGENERATE_WIDGET);
    if (!widget) return;
    node.__h3ContinuumProgrammaticRegenerate = true;
    try {
        setExistingWidgetValue(widget, value);
    } finally {
        delete node.__h3ContinuumProgrammaticRegenerate;
    }
    if (value === "Auto" || value === 0 || value == null) {
        delete node.__h3ContinuumManualRegenerateIntent;
    }
}

function repairStaleReviewRegenerate(node, project) {
    const revision = canonicalStorageRevision(project);
    if (
        !revision
        || !["review_ready", "complete"].includes(revision.status)
        || activeReviewPrompt(node)
        || node.__h3ContinuumManualRegenerateIntent
        || node.__h3ContinuumRestartSelected
    ) {
        return false;
    }
    const widget = findWidget(node, REGENERATE_WIDGET);
    if (!widget || widget.value === "Auto" || widget.value === 0) return false;
    setRegenerateProgrammatically(node, "Auto");
    setExistingWidgetValue(findWidget(node, REROLL_NONCE_WIDGET), 0);
    return true;
}

function facadeProductionWidgets(node) {
    return node.widgets?.filter((widget) => widget[FACADE_TRANSIENT_WIDGET]) || [];
}

function addFacadeWidget(node, type, name, value, callback, options = {}) {
    let widget = facadeProductionWidgets(node).find((item) => item.name === name);
    if (widget) return widget;
    widget = addTransientProductionWidget(node, type, name, value, callback, options);
    if (!widget) return null;
    widget[FACADE_TRANSIENT_WIDGET] = true;
    return widget;
}

function drawRoundedRect(ctx, x, y, width, height, radius) {
    const safeRadius = Math.max(0, Math.min(radius, width / 2, height / 2));
    ctx.beginPath();
    if (typeof ctx.roundRect === "function") {
        ctx.roundRect(x, y, width, height, safeRadius);
    } else {
        ctx.moveTo(x + safeRadius, y);
        ctx.lineTo(x + width - safeRadius, y);
        ctx.quadraticCurveTo(x + width, y, x + width, y + safeRadius);
        ctx.lineTo(x + width, y + height - safeRadius);
        ctx.quadraticCurveTo(x + width, y + height, x + width - safeRadius, y + height);
        ctx.lineTo(x + safeRadius, y + height);
        ctx.quadraticCurveTo(x, y + height, x, y + height - safeRadius);
        ctx.lineTo(x, y + safeRadius);
        ctx.quadraticCurveTo(x, y, x + safeRadius, y);
    }
    ctx.closePath();
}

function drawFacadeInfoWidget(widget, ctx, width, y, height) {
    const left = 15;
    const top = y + 3;
    const innerWidth = Math.max(80, width - 30);
    const innerHeight = Math.max(18, height - 6);
    const variant = widget.__h3ContinuumInfoVariant || "row";
    ctx.save();
    ctx.textBaseline = "middle";
    if (variant === "badges") {
        const badges = Array.isArray(widget.badges) ? widget.badges : [];
        const gap = 6;
        const chipWidth = Math.max(70, (innerWidth - gap * 3) / 4);
        const chipHeight = Math.min(26, innerHeight);
        for (let index = 0; index < badges.length; index += 1) {
            const badge = badges[index];
            const chipX = left + index * (chipWidth + gap);
            drawRoundedRect(ctx, chipX, top, chipWidth, chipHeight, 7);
            ctx.fillStyle = badge.connected ? "rgba(31, 86, 38, 0.96)" : "rgba(31, 31, 31, 0.96)";
            ctx.fill();
            ctx.strokeStyle = badge.connected ? "#63d36d" : "#666";
            ctx.lineWidth = 1;
            ctx.stroke();
            ctx.fillStyle = badge.connected ? "#e7ffe9" : "#bdbdbd";
            ctx.font = "12px Arial";
            ctx.textAlign = "center";
            ctx.fillText(
                `${badge.label} ${badge.connected ? "✓" : "—"}`,
                chipX + chipWidth / 2,
                top + chipHeight / 2,
                chipWidth - 10,
            );
        }
        ctx.restore();
        return;
    }

    const palette = variant === "ready"
        ? {
            background: "rgba(17, 55, 24, 0.96)",
            border: "#58c963",
            headline: "#8ee987",
            detail: "#e8f5e9",
        }
        : variant === "review"
            ? {
                background: "rgba(55, 42, 15, 0.97)",
                border: "#b98b2d",
                headline: "#ffc85a",
                detail: "#f4ead2",
            }
            : {
                background: "rgba(28, 28, 28, 0.96)",
                border: "#666",
                headline: "#bdbdbd",
                detail: "#f0f0f0",
            };
    drawRoundedRect(ctx, left, top, innerWidth, innerHeight, 8);
    ctx.fillStyle = palette.background;
    ctx.fill();
    ctx.strokeStyle = palette.border;
    ctx.lineWidth = 1;
    ctx.stroke();

    if (variant === "row") {
        ctx.font = "13px Arial";
        ctx.fillStyle = palette.headline;
        ctx.textAlign = "left";
        ctx.fillText(widget.name, left + 12, top + innerHeight / 2, innerWidth * 0.43);
        ctx.font = "13px Arial";
        ctx.fillStyle = palette.detail;
        ctx.textAlign = "right";
        ctx.fillText(String(widget.value || ""), left + innerWidth - 12, top + innerHeight / 2, innerWidth * 0.57);
    } else if (variant === "details") {
        ctx.font = "12px Arial";
        ctx.fillStyle = palette.detail;
        ctx.textAlign = "center";
        ctx.fillText(String(widget.value || ""), left + innerWidth / 2, top + innerHeight / 2, innerWidth - 20);
    } else {
        ctx.textAlign = "left";
        ctx.font = "bold 14px Arial";
        ctx.fillStyle = palette.headline;
        ctx.fillText(String(widget.headline || widget.name), left + 14, top + 19, innerWidth - 28);
        ctx.font = "12px Arial";
        ctx.fillStyle = palette.detail;
        ctx.fillText(String(widget.detail || ""), left + 14, top + 42, innerWidth - 28);
    }
    ctx.restore();
}

function addFacadeInfoWidget(node, name, variant, height, facade = true) {
    let widget = transientProductionWidgets(node).find((item) => item.name === name);
    if (widget) return widget;
    if (typeof node.addCustomWidget === "function") {
        widget = {
            name,
            type: "custom",
            value: "",
            options: { serialize: false },
            serialize: false,
            __h3ContinuumInfoVariant: variant,
            computeSize(width) {
                return [width, height];
            },
            draw(ctx, _node, width, y, _widgetHeight) {
                drawFacadeInfoWidget(this, ctx, width, y, height);
            },
        };
        widget[PRODUCTION_TRANSIENT_WIDGET] = true;
        if (facade) widget[FACADE_TRANSIENT_WIDGET] = true;
        node.addCustomWidget(widget);
    } else {
        widget = facade
            ? addFacadeWidget(
                node,
                "text",
                name,
                "",
                null,
                { multiline: variant === "ready" || variant === "review" },
            )
            : addTransientProductionWidget(
                node,
                "text",
                name,
                "",
                null,
                { multiline: variant === "ready" || variant === "review" },
            );
        if (widget) {
            widget.disabled = true;
            widget.__h3ContinuumInfoVariant = variant;
            widget.computeSize = () => [Math.max(300, Number(node.size?.[0] || 0)), height];
        }
    }
    return widget;
}

function compactValue(value, maximumFractionDigits = 1) {
    const number = Number(value);
    if (!Number.isFinite(number)) return String(value ?? "");
    if (Number.isInteger(number)) return String(number);
    return number.toFixed(maximumFractionDigits).replace(/\.?0+$/, "");
}

function durationLabel(node, chunks = null) {
    if (linkedInput(node, [CHUNKS_WIDGET, "chunk_seconds"])) {
        return "From connected inputs";
    }
    const chunkCount = Number(chunks ?? findWidget(node, CHUNKS_WIDGET)?.value ?? 1);
    const seconds = Number(findWidget(node, "chunk_seconds")?.value || 5);
    return `${compactValue(chunkCount * seconds)} seconds`;
}

function frameSizeLabel(width, height) {
    return `${Math.round(Number(width) || 0)} × ${Math.round(Number(height) || 0)}`;
}

function requiredConnectionNames(node) {
    const labels = {
        model: "Model",
        clip: "CLIP",
        video_vae: "Video VAE",
        sampler: "Sampler",
        sigmas: "Sigmas",
    };
    return Object.entries(labels)
        .filter(([name]) => !linkedInput(node, [name]))
        .map(([, label]) => label);
}

function baseSeedControlWidget(node) {
    const seedWidget = findWidget(node, "base_seed");
    const linkedControl = seedWidget?.linkedWidgets?.find(
        (widget) => widget?.name === "control_after_generate",
    );
    return linkedControl || findWidget(node, "control_after_generate");
}

function setReviewSeedControlFixed(node) {
    const control = baseSeedControlWidget(node);
    if (!control) return false;
    setExistingWidgetValue(control, "fixed");
    return String(control.value || "").toLowerCase() === "fixed";
}

function requireFixedSeedForReview(node) {
    if (node.comfyClass !== V38_NODE_CLASS) return;
    if (findWidget(node, GENERATION_MODE_WIDGET)?.value !== GENERATION_MODE_REVIEW) return;
    const control = String(baseSeedControlWidget(node)?.value || "").toLowerCase();
    if (control === "fixed") return;
    throw new Error(
        "H3 Continuum V3.8: Run = Review Each Chunk requires "
        + "Control After Generate = fixed. This keeps Base Seed unchanged so the "
        + "next Queue can reuse the accepted Chunk.",
    );
}

function readySummary(node) {
    if (activeReviewPrompt(node)) return {headline:"Queued / generating", detail:"Waiting for this Run's saved result."};
    if (node.__h3ContinuumOutputFailure?.runName === takeRunName(node)) return {
        headline:"Chunk saved — output incomplete", detail:node.__h3ContinuumOutputFailure.message,
    };
    if (node.__h3ContinuumQueueNotice) return {headline:"Check saved progress", detail:node.__h3ContinuumQueueNotice};
    const missing = requiredConnectionNames(node);
    if (missing.length) {
        return {
            headline: "Connect required inputs",
            detail: `Missing: ${missing.join(", ")}`,
        };
    }
    const sizeSource = findWidget(node, SIZE_SOURCE_WIDGET)?.value;
    const width = findWidget(node, WIDTH_WIDGET)?.value;
    const height = findWidget(node, HEIGHT_WIDGET)?.value;
    if (
        sizeSource === SIZE_SOURCE_FIRST_IMAGE
        && !activeLinkedInput(node, ["first_frame"])
    ) {
        return {
            headline: "Check First Image",
            detail: `Size Source is First Image, but no active image is connected. Queue fallback: ${frameSizeLabel(width, height)}.`,
        };
    }
    const chunks = Math.max(1, Number(findWidget(node, CHUNKS_WIDGET)?.value || 1));
    const seconds = Number(findWidget(node, "chunk_seconds")?.value || 5);
    const reviewing = findWidget(node, GENERATION_MODE_WIDGET)?.value === GENERATION_MODE_REVIEW;
    if (reviewing && chunks < 2 && !linkedInput(node, [CHUNKS_WIDGET])) {
        return {
            headline: "Set Chunks to 2 or more",
            detail: (
                `Chunks is 1, so the first ${compactValue(seconds)}s chunk is also the last. `
                + "Set Chunks to 2 or more before Queue to use Review and Continue."
            ),
        };
    }
    const controlAfterGenerate = String(
        baseSeedControlWidget(node)?.value || "",
    ).toLowerCase();
    if (reviewing && controlAfterGenerate !== "fixed") {
        return {
            headline: "Set Control After Generate to fixed",
            detail: "Review Each Chunk must keep Base Seed unchanged between Queue runs.",
        };
    }
    const duration = linkedInput(node, [CHUNKS_WIDGET, "chunk_seconds"])
        ? "Duration from connected inputs"
        : `${compactValue(chunks)} × ${compactValue(seconds)}s = ${durationLabel(node)}`;
    const output = sizeSource === SIZE_SOURCE_FIRST_IMAGE
        ? "First Image"
        : `Manual ${frameSizeLabel(width, height)}`;
    return {
        headline: "Ready to Queue",
        detail: `${duration} • ${output}${reviewing ? " • Review each chunk" : ""}`,
    };
}

function setWidgetTooltip(widget, tooltip) {
    if (!widget || !tooltip) return;
    widget.tooltip = tooltip;
    widget.options ||= {};
    widget.options.tooltip = tooltip;
}

function facadeWidgetTooltip(node, name) {
    if (name === FACADE_CHUNKS_WIDGET) {
        const reviewing = findWidget(node, GENERATION_MODE_WIDGET)?.value === GENERATION_MODE_REVIEW;
        const chunks = Math.max(1, Number(findWidget(node, CHUNKS_WIDGET)?.value || 1));
        if (reviewing && chunks < 2 && !linkedInput(node, [CHUNKS_WIDGET])) {
            return (
                "Chunks is 1, so there is no next chunk to continue. Set Chunks to 2 or more "
                + "before Queue when using Review Each Chunk."
            );
        }
    }
    if (name === FACADE_GENERATE_WIDGET) {
        const reviewing = findWidget(node, GENERATION_MODE_WIDGET)?.value === GENERATION_MODE_REVIEW;
        return reviewing
            ? (
                "Review Each Chunk: the next normal Queue generates at most one new physical group. "
                + "Set Chunks to 2 or more; when the first chunk is ready, choose one of the "
                + "three review actions, then press Queue."
            )
            : (
                "Generate Full Video: one normal Queue generates all remaining chunks without pausing for review. "
                + "Use Review Each Chunk when you want to approve or retry each result."
            );
    }
    if (name === FACADE_CONTROL_AFTER_WIDGET) {
        const reviewing = findWidget(node, GENERATION_MODE_WIDGET)?.value === GENERATION_MODE_REVIEW;
        if (reviewing) {
            return (
                "Review Each Chunk requires fixed. Changing Base Seed between Queue runs "
                + "starts a different stored revision instead of continuing the accepted Chunk."
            );
        }
    }
    if (name === FACADE_SIZE_SOURCE_WIDGET) {
        const firstImage = findWidget(node, SIZE_SOURCE_WIDGET)?.value === SIZE_SOURCE_FIRST_IMAGE;
        return firstImage
            ? (
                "First Image: uses the aspect ratio of the image connected to First Image, then "
                + "Resolution chooses the pixel area. Use this for I2VA or FL2VA. If the image is unavailable, "
                + "the displayed Manual Width and Height are used as a safe fallback."
            )
            : (
                "Manual: enter exact Width and Height. Use this for T2VA, workflows without a First Image, "
                + "or whenever the output canvas must be specified directly."
            );
    }
    if (name === FACADE_RESOLUTION_WIDGET) {
        const preset = String(findWidget(node, RESOLUTION_PRESET_WIDGET)?.value || "");
        if (preset === RESOLUTION_PRESET_DRAFT) {
            return "Draft - 0.30 MP: fastest First Image sizing option and the lowest VRAM starting point.";
        }
        if (preset === RESOLUTION_PRESET_BALANCED) {
            return "Balanced - 0.60 MP: higher-detail First Image sizing with greater VRAM and processing cost.";
        }
        if (preset === RESOLUTION_PRESET_NATIVE) {
            return "Native 768: preserves the First Image aspect with an H3-native 768 px short edge and a 1344 px long-edge cap.";
        }
        return "Custom: preserves the First Image aspect and uses the Custom MP target shown below.";
    }
    if (name === FACADE_SAVE_WIDGET) {
        const enabled = findWidget(node, RUN_STORAGE_WIDGET)?.value === "Save + Auto Resume";
        return enabled
            ? (
                "On: saves raw chunk progress and immutable Take history for safe resume, regeneration, "
                + "Use This Take, and Continue From Here."
            )
            : (
                "Off: does not keep resumable chunk history. Turn this On for Review Each Chunk, "
                + "Render History, or partial regeneration."
            );
    }
    if (name === FACADE_REFERENCE_SIZE_WIDGET) {
        const mode = String(findWidget(node, REFERENCE_SIZE_WIDGET)?.value || "Match Output");
        return mode === "Max Identity"
            ? "Max Identity: retains more Reference Image detail for identity guidance, with a higher memory cost."
            : "Match Output: resizes connected Reference Images to the output canvas. This is the practical default.";
    }
    if (name === FACADE_VIDEO_SIZE_WIDGET) {
        const mode = String(findWidget(node, VIDEO_REFERENCE_SIZE_WIDGET)?.value || "Efficient - 0.4 MP");
        if (mode === "Balanced - 0.6 MP") {
            return "Balanced - 0.6 MP: keeps more Video Guide detail than Efficient and uses more memory.";
        }
        if (mode === "Match Output") {
            return "Match Output: processes Video Guide Frames at the output pixel area. This can be substantially heavier.";
        }
        return "Efficient - 0.4 MP: reduces Video Guide conditioning cost while preserving its source aspect ratio.";
    }
    return FACADE_HELP[name] || "";
}

function applyV38WidgetHelp(node) {
    for (const widget of facadeProductionWidgets(node)) {
        setWidgetTooltip(widget, facadeWidgetTooltip(node, widget.name));
    }
    for (const [name, tooltip] of Object.entries(ADVANCED_WIDGET_HELP)) {
        setWidgetTooltip(findWidget(node, name), tooltip);
    }
}

function installCompactNumberDisplay(widget, maximumFractionDigits) {
    if (!widget || widget.type !== "number") return;
    widget.options ||= {};
    delete widget.options.precision;
    Object.defineProperty(widget, "_displayValue", {
        configurable: true,
        get() {
            const value = Number(this.value);
            if (!Number.isFinite(value)) return String(this.value ?? "");
            if (maximumFractionDigits <= 0 || Number.isInteger(value)) {
                return String(Math.round(value));
            }
            return value.toFixed(maximumFractionDigits).replace(/\.?0+$/, "");
        },
    });
}

function addFacadeProxyWidget(
    node,
    {
        type,
        name,
        sourceName,
        sourceWidget = null,
        options = {},
        fromSource = (value) => value,
        onSet = null,
        compactDecimals = null,
    },
) {
    const source = sourceWidget || findWidget(node, sourceName);
    if (!source) return null;
    let widget = facadeProductionWidgets(node).find((item) => item.name === name);
    if (!widget) {
        widget = addFacadeWidget(
            node,
            type,
            name,
            fromSource(source.value),
            (value) => {
                if (onSet) {
                    onSet(value, source);
                } else {
                    setExistingWidgetValue(source, value);
                }
                node.__h3ContinuumIntuitiveUxRefresh?.();
            },
            options,
        );
        if (widget) {
            setWidgetTooltip(widget, source.tooltip || source.options?.tooltip);
        }
    }
    if (!widget) return null;
    if (Number.isInteger(compactDecimals) && compactDecimals >= 0) {
        installCompactNumberDisplay(widget, compactDecimals);
    }
    widget.value = fromSource(source.value);
    const refreshKey = `__h3ContinuumFacadeRefresh_${name.replaceAll(" ", "_")}`;
    attachRefresh(source, refreshKey, () => {
        widget.value = fromSource(source.value);
        node.__h3ContinuumIntuitiveUxRefresh?.();
    });
    return widget;
}

function moveFacadeWidgetsToFront(node, orderedNames) {
    if (!Array.isArray(node.widgets)) return;
    const byName = new Map(
        facadeProductionWidgets(node).map((widget) => [widget.name, widget]),
    );
    const ordered = orderedNames.map((name) => byName.get(name)).filter(Boolean);
    const remainder = node.widgets.filter((widget) => !widget[FACADE_TRANSIENT_WIDGET]);
    node.widgets.splice(0, node.widgets.length, ...ordered, ...remainder);
}

function configureDurationInputSlots(node) {
    // Core lays out widget sockets using the direct widget binding, not the
    // getWidgetFromSlot override used for drawing and disabled-state lookup.
    for (const [source, facade] of [[CHUNKS_WIDGET, FACADE_CHUNKS_WIDGET], ["chunk_seconds", FACADE_SECONDS_WIDGET]]) {
        const slot = node.inputs?.find((input) => input.widget?.name === source);
        if (slot) slot._widget = findWidget(node, facade);
    }
    node._widgetSlotsDirty = true;
    if (node.__h3ContinuumDurationSlots || typeof node.getWidgetFromSlot !== "function"
        || typeof node.getSlotFromWidget !== "function") return;
    const names = new Map([
        [CHUNKS_WIDGET, FACADE_CHUNKS_WIDGET],
        ["chunk_seconds", FACADE_SECONDS_WIDGET],
    ]);
    const getWidget = node.getWidgetFromSlot;
    const getSlot = node.getSlotFromWidget;
    // Keep Core input names/configuration intact; only map their visible controls.
    node.getWidgetFromSlot = function(slot) {
        const facade = names.get(slot.widget?.name);
        return facade ? findWidget(this, facade) : getWidget.call(this, slot);
    };
    node.getSlotFromWidget = function(widget) {
        for (const [source, facade] of names) {
            if (widget?.name === facade) return getSlot.call(this, findWidget(this, source));
        }
        return getSlot.call(this, widget);
    };
    node.__h3ContinuumDurationSlots = true;
}

function moveNamedWidgetsToFront(node, orderedNames) {
    if (!Array.isArray(node.widgets)) return;
    const byName = new Map(node.widgets.map((widget) => [widget.name, widget]));
    const ordered = orderedNames.map((name) => byName.get(name)).filter(Boolean);
    const selected = new Set(ordered);
    const remainder = node.widgets.filter((widget) => !selected.has(widget));
    node.widgets.splice(0, node.widgets.length, ...ordered, ...remainder);
}

function configureIntuitiveV38Ux(node) {
    if (node.comfyClass !== V38_NODE_CLASS || typeof node.addWidget !== "function") return;
    const sourceOptions = (name) => {
        const widget = name === "control_after_generate"
            ? baseSeedControlWidget(node)
            : findWidget(node, name);
        const values = widget?.options?.values;
        return Array.isArray(values) ? [...values] : values;
    };

    const promptFormatFacade = addFacadeProxyWidget(node, {
        type: "combo",
        name: FACADE_PROMPT_FORMAT_WIDGET,
        sourceName: "prompt_mode",
        options: { values: sourceOptions("prompt_mode") },
    });
    const continuityFacade = addFacadeProxyWidget(node, {
        type: "combo",
        name: FACADE_CONTINUITY_WIDGET,
        sourceName: "continuity",
        options: { values: sourceOptions("continuity") },
    });
    const baseSeedSource = findWidget(node, "base_seed");
    const baseSeedFacade = addFacadeProxyWidget(node, {
        type: "number",
        name: FACADE_BASE_SEED_WIDGET,
        sourceName: "base_seed",
        compactDecimals: 0,
        options: {
            min: baseSeedSource?.options?.min,
            max: baseSeedSource?.options?.max,
            step: baseSeedSource?.options?.step,
        },
    });
    const controlAfterFacade = addFacadeProxyWidget(node, {
        type: "combo",
        name: FACADE_CONTROL_AFTER_WIDGET,
        sourceName: "control_after_generate",
        sourceWidget: baseSeedControlWidget(node),
        options: { values: sourceOptions("control_after_generate") },
    });
    const audioContinuityFacade = addFacadeProxyWidget(node, {
        type: "toggle",
        name: FACADE_AUDIO_CONTINUITY_WIDGET,
        sourceName: "audio_continuity",
    });
    const chunksFacade = addFacadeProxyWidget(node, {
        type: "number",
        name: FACADE_CHUNKS_WIDGET,
        sourceName: CHUNKS_WIDGET,
        compactDecimals: 0,
        options: {
            min: findWidget(node, CHUNKS_WIDGET)?.options?.min,
            max: findWidget(node, CHUNKS_WIDGET)?.options?.max,
            step: findWidget(node, CHUNKS_WIDGET)?.options?.step,
        },
    });
    const secondsFacade = addFacadeProxyWidget(node, {
        type: "number",
        name: FACADE_SECONDS_WIDGET,
        sourceName: "chunk_seconds",
        compactDecimals: 1,
        options: {
            min: findWidget(node, "chunk_seconds")?.options?.min,
            max: findWidget(node, "chunk_seconds")?.options?.max,
            step: findWidget(node, "chunk_seconds")?.options?.step,
        },
    });
    const totalLengthWidget = addFacadeInfoWidget(
        node,
        FACADE_TOTAL_LENGTH_WIDGET,
        "row",
        34,
    );
    const readyWidget = addFacadeInfoWidget(node, FACADE_READY_WIDGET, "ready", 62);
    configureDurationInputSlots(node);

    const outputFacade = addFacadeProxyWidget(node, {
        type: "combo",
        name: FACADE_SIZE_SOURCE_WIDGET,
        sourceName: SIZE_SOURCE_WIDGET,
        options: { values: [SIZE_SOURCE_FIRST_IMAGE, SIZE_SOURCE_MANUAL] },
    });

    const qualityFacade = addFacadeProxyWidget(node, {
        type: "combo",
        name: FACADE_RESOLUTION_WIDGET,
        sourceName: RESOLUTION_PRESET_WIDGET,
        options: { values: sourceOptions(RESOLUTION_PRESET_WIDGET) },
    });

    for (const [type, name, sourceName] of (
        [
            ["number", FACADE_CUSTOM_MP_WIDGET, CUSTOM_MP_WIDGET],
            ["number", FACADE_WIDTH_WIDGET, WIDTH_WIDGET],
            ["number", FACADE_HEIGHT_WIDGET, HEIGHT_WIDGET],
            ["combo", FACADE_REFERENCE_SIZE_WIDGET, REFERENCE_SIZE_WIDGET],
            ["combo", FACADE_VIDEO_SIZE_WIDGET, VIDEO_REFERENCE_SIZE_WIDGET],
        ]
    )) {
        const source = findWidget(node, sourceName);
        addFacadeProxyWidget(node, {
            type,
            name,
            sourceName,
            compactDecimals: type === "number"
                ? (name === FACADE_CUSTOM_MP_WIDGET ? 2 : 0)
                : null,
            options: type === "combo"
                ? { values: sourceOptions(sourceName) }
                : {
                    min: source?.options?.min,
                    max: source?.options?.max,
                    step: source?.options?.step,
                },
        });
    }

    const generationFacade = addFacadeProxyWidget(node, {
        type: "combo",
        name: FACADE_GENERATE_WIDGET,
        sourceName: GENERATION_MODE_WIDGET,
        options: { values: [FACADE_GENERATE_ALL, FACADE_GENERATE_REVIEW] },
        fromSource: (value) => (
            value === GENERATION_MODE_REVIEW ? FACADE_GENERATE_REVIEW : FACADE_GENERATE_ALL
        ),
        onSet: (value, source) => {
            const reviewing = value === FACADE_GENERATE_REVIEW;
            if (reviewing && source.value !== GENERATION_MODE_REVIEW) {
                // Selecting a mode is setup, not selecting a saved review.
                node.__h3ContinuumModeSetup = {};
            } else if (!reviewing) {
                delete node.__h3ContinuumModeSetup;
            }
            setExistingWidgetValue(
                source,
                reviewing ? GENERATION_MODE_REVIEW : GENERATION_MODE_FULL_RUN,
            );
            if (reviewing) {
                setExistingWidgetValue(
                    findWidget(node, RUN_STORAGE_WIDGET),
                    "Save + Auto Resume",
                );
            }
        },
    });
    if (generationFacade) {
        setWidgetTooltip(generationFacade, (
            "Generate Full Video generates every chunk in one Queue. Review Each Chunk pauses "
            + "after each completed chunk so you can keep it, try it again, or finish the rest."
        ));
    }

    const storageFacade = addFacadeProxyWidget(node, {
        type: "combo",
        name: FACADE_SAVE_WIDGET,
        sourceName: RUN_STORAGE_WIDGET,
        options: { values: [FACADE_SAVE_OFF, FACADE_SAVE_ON] },
        fromSource: (value) => (
            value === "Save + Auto Resume" ? FACADE_SAVE_ON : FACADE_SAVE_OFF
        ),
        onSet: (value, source) => {
            const enabled = value === FACADE_SAVE_ON;
            setExistingWidgetValue(source, enabled ? "Save + Auto Resume" : "Off");
            if (!enabled) {
                setExistingWidgetValue(
                    findWidget(node, GENERATION_MODE_WIDGET),
                    GENERATION_MODE_FULL_RUN,
                );
            }
        },
    });
    if (storageFacade) {
        setWidgetTooltip(storageFacade, (
            "Keep progress for safe resume and Render History. Review Each Chunk turns this on automatically."
        ));
    }
    let advancedWidget = facadeProductionWidgets(node).find(
        (widget) => widget.name === FACADE_ADVANCED_WIDGET,
    );
    if (!advancedWidget) {
        advancedWidget = addFacadeWidget(
            node,
            "button",
            FACADE_ADVANCED_WIDGET,
            null,
            () => {
                node.__h3ContinuumAdvancedOpen = !node.__h3ContinuumAdvancedOpen;
                node.__h3ContinuumIntuitiveUxRefresh?.();
            },
        );
        if (advancedWidget) {
            setWidgetTooltip(advancedWidget, "Show technical controls only when you need them.");
        }
    }
    const orderedNames = [
        FACADE_PROMPT_FORMAT_WIDGET,
        FACADE_CONTINUITY_WIDGET,
        FACADE_BASE_SEED_WIDGET,
        FACADE_CONTROL_AFTER_WIDGET,
        FACADE_AUDIO_CONTINUITY_WIDGET,
        FACADE_CHUNKS_WIDGET,
        FACADE_SECONDS_WIDGET,
        FACADE_TOTAL_LENGTH_WIDGET,
        FACADE_SIZE_SOURCE_WIDGET,
        FACADE_RESOLUTION_WIDGET,
        FACADE_CUSTOM_MP_WIDGET,
        FACADE_WIDTH_WIDGET,
        FACADE_HEIGHT_WIDGET,
        FACADE_GENERATE_WIDGET,
        FACADE_SAVE_WIDGET,
        FACADE_READY_WIDGET,
        FACADE_ADVANCED_WIDGET,
        FACADE_REFERENCE_SIZE_WIDGET,
        FACADE_VIDEO_SIZE_WIDGET,
    ];
    node.__h3ContinuumFacadeOrder = orderedNames;
    moveFacadeWidgetsToFront(node, orderedNames);
    installProductionSerializationGuard(node);

    const refresh = () => {
        const firstImage = findWidget(node, SIZE_SOURCE_WIDGET)?.value === SIZE_SOURCE_FIRST_IMAGE;
        const customResolution = (
            firstImage
            && findWidget(node, RESOLUTION_PRESET_WIDGET)?.value === CUSTOM_RESOLUTION_PRESET
        );
        const referenceConnected = activeLinkedInput(
            node,
            ["reference_image_1", "reference_image_2", "reference_image_3"],
        );
        const videoConnected = activeLinkedInput(node, ["reference_video_1"]);
        const storageEnabled = findWidget(node, RUN_STORAGE_WIDGET)?.value === "Save + Auto Resume";
        const regenerateWidget = findWidget(node, REGENERATE_WIDGET);
        const explicitRegeneration = storageEnabled
            && regenerateWidget?.value !== "Auto"
            && Number.parseInt(String(regenerateWidget?.value).replace(/^Chunk\s+/, ""), 10) > 0;
        const advanced = Boolean(node.__h3ContinuumAdvancedOpen);
        node.__h3ContinuumAdvancedOpen = advanced;

        if (promptFormatFacade) promptFormatFacade.value = findWidget(node, "prompt_mode")?.value;
        if (continuityFacade) continuityFacade.value = findWidget(node, "continuity")?.value;
        if (baseSeedFacade) baseSeedFacade.value = findWidget(node, "base_seed")?.value;
        if (controlAfterFacade) {
            controlAfterFacade.value = baseSeedControlWidget(node)?.value;
        }
        if (audioContinuityFacade) {
            audioContinuityFacade.value = findWidget(node, "audio_continuity")?.value;
        }
        if (chunksFacade) chunksFacade.value = findWidget(node, CHUNKS_WIDGET)?.value;
        if (secondsFacade) secondsFacade.value = findWidget(node, "chunk_seconds")?.value;
        if (totalLengthWidget) totalLengthWidget.value = durationLabel(node);
        if (outputFacade) {
            outputFacade.value = findWidget(node, SIZE_SOURCE_WIDGET)?.value;
        }
        if (qualityFacade) qualityFacade.value = findWidget(node, RESOLUTION_PRESET_WIDGET)?.value;
        if (readyWidget) {
            const summary = readySummary(node);
            readyWidget.headline = summary.headline;
            readyWidget.detail = summary.detail;
            readyWidget.value = `${summary.headline}\n${summary.detail}`;
            readyWidget.__h3ContinuumInfoVariant = summary.headline === "Ready to Queue"
                ? "ready"
                : "review";
        }
        if (advancedWidget) {
            advancedWidget.label = advanced
                ? "Hide Advanced Settings"
                : "Show Advanced Settings";
        }

        for (const name of orderedNames) {
            setWidgetVisible(
                facadeProductionWidgets(node).find((widget) => widget.name === name),
                true,
            );
        }
        setWidgetVisible(
            facadeProductionWidgets(node).find(
                (widget) => widget.name === FACADE_RESOLUTION_WIDGET,
            ),
            firstImage,
        );
        setWidgetVisible(
            facadeProductionWidgets(node).find(
                (widget) => widget.name === FACADE_CUSTOM_MP_WIDGET,
            ),
            customResolution,
        );
        for (const name of [FACADE_WIDTH_WIDGET, FACADE_HEIGHT_WIDGET]) {
            setWidgetVisible(
                facadeProductionWidgets(node).find((widget) => widget.name === name),
                !firstImage,
            );
        }
        setWidgetVisible(
            facadeProductionWidgets(node).find(
                (widget) => widget.name === FACADE_REFERENCE_SIZE_WIDGET,
            ),
            advanced && referenceConnected,
        );
        setWidgetVisible(
            facadeProductionWidgets(node).find(
                (widget) => widget.name === FACADE_VIDEO_SIZE_WIDGET,
            ),
            advanced && videoConnected,
        );

        for (const name of (
            [
                SIZE_SOURCE_WIDGET,
                RESOLUTION_PRESET_WIDGET,
                CUSTOM_MP_WIDGET,
                WIDTH_WIDGET,
                HEIGHT_WIDGET,
                "prompt_mode",
                "continuity",
                "base_seed",
                "control_after_generate",
                "audio_continuity",
                CHUNKS_WIDGET,
                "chunk_seconds",
                RUN_STORAGE_WIDGET,
                REFERENCE_SIZE_WIDGET,
                VIDEO_REFERENCE_SIZE_WIDGET,
                GENERATION_MODE_WIDGET,
                REVIEW_ACTION_WIDGET,
            ]
        )) {
            hidePersistentWidget(findWidget(node, name));
        }
        for (const name of (
            [
                "continuation_backend",
            ]
        )) {
            setWidgetVisible(findWidget(node, name), advanced);
        }
        setWidgetVisible(findWidget(node, REGENERATE_WIDGET), advanced && storageEnabled);
        setWidgetVisible(findWidget(node, LEGACY_RUN_NAME_WIDGET), advanced && storageEnabled);
        setWidgetVisible(findWidget(node, REROLL_NONCE_WIDGET), advanced && explicitRegeneration);
        applyV38WidgetHelp(node);
        moveFacadeWidgetsToFront(node, orderedNames);
        node.__h3ContinuumProductionUxRefresh?.();
        node.setDirtyCanvas?.(true, true);
    };
    node.__h3ContinuumIntuitiveUxRefresh = refresh;
    for (const [name, key] of (
        [
            ["prompt_mode", "__h3ContinuumFacadePromptMode"],
            ["continuity", "__h3ContinuumFacadeContinuity"],
            ["base_seed", "__h3ContinuumFacadeBaseSeed"],
            ["audio_continuity", "__h3ContinuumFacadeAudioContinuity"],
            [CHUNKS_WIDGET, "__h3ContinuumFacadeChunks"],
            ["chunk_seconds", "__h3ContinuumFacadeSeconds"],
            [SIZE_SOURCE_WIDGET, "__h3ContinuumFacadeSizeSource"],
            [RESOLUTION_PRESET_WIDGET, "__h3ContinuumFacadePreset"],
            [CUSTOM_MP_WIDGET, "__h3ContinuumFacadeCustomMp"],
            [WIDTH_WIDGET, "__h3ContinuumFacadeWidth"],
            [HEIGHT_WIDGET, "__h3ContinuumFacadeHeight"],
            [RUN_STORAGE_WIDGET, "__h3ContinuumFacadeStorage"],
            [REGENERATE_WIDGET, "__h3ContinuumFacadeRegenerate"],
            [GENERATION_MODE_WIDGET, "__h3ContinuumFacadeGenerate"],
        ]
    )) {
        attachRefresh(findWidget(node, name), key, refresh);
    }
    attachRefresh(
        baseSeedControlWidget(node),
        "__h3ContinuumFacadeControlAfter",
        refresh,
    );
    if (!node.__h3ContinuumFacadeConnectionCallback) {
        const previous = node.onConnectionsChange;
        node.onConnectionsChange = function(...args) {
            const result = previous?.apply(this, args);
            setTimeout(refresh, 0);
            return result;
        };
        node.__h3ContinuumFacadeConnectionCallback = true;
    }
    refresh();
}

function productionQueueSummary(node) {
    const generation = findWidget(node, GENERATION_MODE_WIDGET)?.value;
    const action = findWidget(node, REVIEW_ACTION_WIDGET)?.value;
    if (generation !== GENERATION_MODE_REVIEW) {
        return "Full Run";
    }
    if (action === REVIEW_ACTION_REGENERATE) {
        return "Regenerate current physical group (atomic)";
    }
    if (action === REVIEW_ACTION_FINISH) {
        return "Reuse accepted prefix + finish remaining";
    }
    return "Accept current + continue one physical group";
}

function productionRunPlan(node) {
    const storage = findWidget(node, RUN_STORAGE_WIDGET)?.value || "Off";
    const regenerateFrom = findWidget(node, REGENERATE_WIDGET)?.value ?? "Auto";
    const nonce = findWidget(node, REROLL_NONCE_WIDGET)?.value ?? 0;
    return (
        `Next Queue: ${productionQueueSummary(node)} | `
        + `Storage: ${storage} | From: ${regenerateFrom} | Nonce: ${nonce}`
    );
}

function canonicalStorageRevision(project) {
    const revisionId = String(project?.canonical_storage_revision_id || "");
    const revisions = Array.isArray(project?.revisions) ? project.revisions : [];
    return revisions.find((item) => String(item?.revision_id || "") === revisionId) || null;
}

// Browser edit detection is advisory: it can withdraw stale actions, never
// approve a saved prefix. Run Storage still owns all compatibility/reuse checks.
function reviewSettingsSnapshot(node) {
    const ignored = new Set([
        PROJECT_WIDGET, LEGACY_RUN_NAME_WIDGET, RUN_STORAGE_WIDGET,
        GENERATION_MODE_WIDGET, REVIEW_ACTION_WIDGET, REGENERATE_WIDGET,
        REROLL_NONCE_WIDGET, TAKE_GROUP_WIDGET, TAKE_REVISION_WIDGET,
        TAKE_ACTION_WIDGET, "control_after_generate", "diagnostics", "debug",
        "strict_compatibility", "show_preview",
    ]);
    const seen = new Set();
    const visit = (current) => {
        if (!current || seen.has(current)) return null;
        seen.add(current);
        const widgets = (current.widgets || []).filter((widget) => (
            !widget[PRODUCTION_TRANSIENT_WIDGET] && !widget[FACADE_TRANSIENT_WIDGET]
            && widget.options?.serialize !== false && widget.type !== "button"
            && !(current === node && ignored.has(widget.name))
        )).map((widget) => [widget.name, widget.value])
            .sort((a, b) => String(a[0]).localeCompare(String(b[0])));
        const graph = node.graph || (typeof app === "undefined" ? null : app.graph);
        const inputs = (current.inputs || []).map((input) => {
            const link = graph?.links?.[input.link];
            return [input.name, input.link, link?.origin_slot,
                visit(graph?.getNodeById?.(link?.origin_id))];
        });
        return [current.id, current.comfyClass || current.type, current.mode, widgets, inputs];
    };
    try { return JSON.stringify(visit(node)); } catch { return null; }
}

function reviewSettingsChanged(node) {
    const baseline = node.__h3ContinuumReviewedSettings;
    const current = reviewSettingsSnapshot(node);
    return baseline != null && current != null && current !== baseline;
}

function rememberReviewSettings(node, requestedSettings) {
    const revision = canonicalStorageRevision(node.__h3ContinuumTakeProject);
    if (!revision || !["review_ready", "complete"].includes(revision.status)) return;
    const key = JSON.stringify([takeRunName(node), revision.revision_id,
        revision.status, revision.review_unit, revision.updated_utc]);
    if (key === node.__h3ContinuumReviewedSettingsKey) return;
    node.__h3ContinuumReviewedSettingsKey = key;
    node.__h3ContinuumReviewedSettings = requestedSettings ?? reviewSettingsSnapshot(node);
}

function selectProductionRestart(node) {
    clearTakeSelection(node);
    setExistingWidgetValue(findWidget(node, REVIEW_ACTION_WIDGET), REVIEW_ACTION_CONTINUE);
    setExistingWidgetValue(findWidget(node, REROLL_NONCE_WIDGET), 0);
    node.__h3ContinuumRestartSelected = true;
    setRegenerateProgrammatically(node, "Chunk 1");
    delete node[REVIEW_UI_SELECTION];
    node.__h3ContinuumProductionUxRefresh?.();
}

function reviewReady(node) {
    const revision = canonicalStorageRevision(node.__h3ContinuumTakeProject);
    // Completion ends continuation, not the user's ability to inspect/retry a Take.
    // Keep the backend status authoritative; never rewrite complete to review_ready.
    if (revision?.status === "complete") return true;
    return revision?.status === "review_ready" && reviewHasUnit(node);
}

function reviewHasUnit(node) {
    const revision = canonicalStorageRevision(node.__h3ContinuumTakeProject);
    const unit = revision?.review_unit;
    return [unit?.physical_group, unit?.start, unit?.end].every(
        (value) => Number.isInteger(Number(value)) && Number(value) > 0,
    ) && Number(unit.end) >= Number(unit.start)
        && Number(unit.physical_group) === Number(unit.start);
}

function reviewStatus(node) {
    const pending = activeReviewPrompt(node);
    if (pending) return "Queued / generating\nWaiting for this Run's saved result.";
    if (node.__h3ContinuumOutputFailure?.runName === takeRunName(node)) {
        return "Chunk saved — output incomplete\n" + node.__h3ContinuumOutputFailure.message;
    }
    if (node.__h3ContinuumQueueNotice) return "Check saved progress\n" + node.__h3ContinuumQueueNotice;
    if (node.__h3ContinuumTakeError) {
        return `Review status unavailable: ${node.__h3ContinuumTakeError}`;
    }
    const from = findWidget(node, REGENERATE_WIDGET)?.value;
    if (from && from !== "Auto" && from !== 0) {
        return `Regenerate from ${from}\nPress Queue directly. Saved Takes are kept.`;
    }
    if (reviewSettingsChanged(node)) {
        return "Settings changed — previous review is out of date\nQueue current settings, or start again from Chunk 1. Saved Takes are kept.";
    }
    const project = node.__h3ContinuumTakeProject;
    if (!project) return "Queue the workflow to create the first chunk.";
    const revision = canonicalStorageRevision(project);
    if (!revision) return "Queue the workflow to create the first chunk.";
    if (revision.status === "complete") {
        const unit = revision.review_unit;
        const label = reviewHasUnit(node)
            ? (Number(unit.end) > Number(unit.start)
                ? `Chunks ${unit.start}-${unit.end}` : `Chunk ${unit.start}`)
            : "";
        if (label && node[REVIEW_UI_SELECTION] === REVIEW_ACTION_REGENERATE) {
            return `Saved sequence is complete\nSelected: retry ${label}. Press Run to generate a new Take.`;
        }
        return "Saved sequence is complete\n" + (label
            ? `Retry ${label}, or open history/settings below.`
            : "Open history/settings below to extend or regenerate.");
    }
    if (reviewReady(node)) {
        const group = revision.review_unit;
        const label = Number(group.end) > Number(group.start)
            ? `Chunks ${group.start}-${group.end}`
            : `Chunk ${group.physical_group}`;
        const selected = node[REVIEW_UI_SELECTION];
        const selectedLabel = selected === REVIEW_ACTION_CONTINUE
            ? PRODUCTION_CONTINUE_WIDGET
            : selected === REVIEW_ACTION_REGENERATE
                ? PRODUCTION_REGENERATE_WIDGET
                : selected === REVIEW_ACTION_FINISH
                    ? PRODUCTION_FINISH_WIDGET
                    : null;
        if (selectedLabel) {
            return `${label} is ready for review\nSelected: ${selectedLabel}. Press Queue to run this action.`;
        }
        return `${label} is ready for review\nChoose what happens next, then press Queue.`;
    }
    if (revision.status === "interrupted") {
        return "The last run was interrupted. Queue to resume safely.";
    }
    return "Generation is in progress. Review actions will appear when the chunk is ready.";
}

function selectProductionReviewAction(node, action) {
    if (activeReviewPrompt(node) || node.__h3ContinuumOutputFailure) return;
    const from = findWidget(node, REGENERATE_WIDGET)?.value;
    if (reviewSettingsChanged(node) || (from && from !== "Auto" && from !== 0)) {
        node.__h3ContinuumProductionUxRefresh?.();
        return;
    }
    setExistingWidgetValue(findWidget(node, RUN_STORAGE_WIDGET), "Save + Auto Resume");
    setExistingWidgetValue(findWidget(node, GENERATION_MODE_WIDGET), GENERATION_MODE_REVIEW);
    setReviewSeedControlFixed(node);
    setExistingWidgetValue(findWidget(node, REVIEW_ACTION_WIDGET), action);
    node[REVIEW_UI_SELECTION] = action;
    node.__h3ContinuumProductionUxRefresh?.();
    node.setDirtyCanvas?.(true, true);
}

function takeRunName(node) {
    const explicit = String(findWidget(node, LEGACY_RUN_NAME_WIDGET)?.value || "").trim();
    if (explicit) return explicit;
    const projectId = String(findWidget(node, PROJECT_WIDGET)?.value || "").trim().toLowerCase();
    if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(projectId)) {
        return "";
    }
    return `run_${projectId.replaceAll("-", "")}`;
}

function takeGroup(item) {
    const physicalGroup = Number(item?.group?.physical_group || 0);
    const start = Number(item?.group?.start || physicalGroup);
    const end = Number(item?.group?.end || start);
    if (!Number.isInteger(physicalGroup) || physicalGroup < 1) return null;
    if (!Number.isInteger(start) || !Number.isInteger(end) || start < 1 || end < start) {
        return null;
    }
    return { physical_group: physicalGroup, start, end };
}

const takeCatalogCache = new WeakMap();

function takeCatalog(node) {
    const project = node.__h3ContinuumTakeProject;
    if (project && takeCatalogCache.has(project)) return takeCatalogCache.get(project);
    const revisions = project?.group_revisions;
    if (!Array.isArray(revisions)) return [];
    const normalized = revisions
        .map((item) => ({ item, group: takeGroup(item) }))
        .filter(({ item, group }) => group && String(item?.revision_id || ""));
    if (!normalized.length) return [];

    // project.json is an archive for every sampling lineage that has used this
    // Run Name.  Take actions, however, are deliberately validated by the
    // backend against the current canonical lineage only.  Never present old
    // lineages (or orphaned ancestry) as actionable history.
    const normalizedById = new Map(normalized.map(
        (entry) => [String(entry.item.revision_id), entry],
    ));
    const activeIds = Object.values(project?.active_revisions || {}).map(String);
    const anchor = normalizedById.get(String(project?.canonical_head_revision_id || ""))
        || activeIds.map((revisionId) => normalizedById.get(revisionId)).find(Boolean)
        || null;
    const canonicalLineage = String(anchor?.item?.lineage_sha256 || "");
    const lineageAware = normalized.some(
        ({ item }) => Boolean(String(item?.lineage_sha256 || "")),
    );
    if (lineageAware && !canonicalLineage) return [];
    const scoped = canonicalLineage
        ? normalized.filter(
            ({ item }) => String(item?.lineage_sha256 || "") === canonicalLineage,
        )
        : normalized;
    const scopedById = new Map(scoped.map(
        (entry) => [String(entry.item.revision_id), entry],
    ));
    const resolvable = ({ item }) => {
        const reverse = [];
        const seen = new Set();
        let revisionId = String(item.revision_id || "");
        while (revisionId) {
            if (seen.has(revisionId)) return false;
            seen.add(revisionId);
            const entry = scopedById.get(revisionId);
            if (!entry) return false;
            reverse.push(entry);
            revisionId = String(entry.item.parent_revision_id || "");
        }
        let expectedStart = 1;
        for (const entry of reverse.reverse()) {
            if (entry.group.start !== expectedStart) return false;
            expectedStart = entry.group.end + 1;
        }
        return true;
    };
    const sorted = scoped
        .filter(resolvable)
        .sort((left, right) => (
            left.group.physical_group - right.group.physical_group
            || String(left.item.revision_order || left.item.revision_id).localeCompare(
                String(right.item.revision_order || right.item.revision_id),
            )
        ));
    const totals = new Map();
    for (const { group } of sorted) {
        totals.set(group.physical_group, (totals.get(group.physical_group) || 0) + 1);
    }
    const positions = new Map();
    const result = sorted.map(({ item, group }) => {
        const takeNumber = (positions.get(group.physical_group) || 0) + 1;
        positions.set(group.physical_group, takeNumber);
        return {
            ...item,
            group,
            take_number: takeNumber,
            take_count: totals.get(group.physical_group),
        };
    });
    takeCatalogCache.set(project, result);
    return result;
}

function takeCandidates(node) {
    const catalog = takeCatalog(node);
    const requestedGroup = Number(findWidget(node, TAKE_GROUP_WIDGET)?.value || 0);
    const active = node.__h3ContinuumTakeProject?.active_revisions || {};
    const activeGroups = Object.keys(active).map(Number).filter(Number.isInteger);
    const group = requestedGroup > 0
        ? requestedGroup
        : (activeGroups.length ? Math.max(...activeGroups) : 0);
    return catalog.filter((item) => item.group.physical_group === group);
}

function selectedTake(node) {
    const project = node.__h3ContinuumTakeProject;
    const catalog = takeCatalog(node);
    if (!project || !catalog.length) return null;
    const selectedId = String(node.__h3ContinuumBrowseRevision
        || findWidget(node, TAKE_REVISION_WIDGET)?.value || "");
    const explicit = catalog.find((item) => item.revision_id === selectedId);
    if (explicit) return explicit;
    const requestedGroup = Number(findWidget(node, TAKE_GROUP_WIDGET)?.value || 0);
    const activeId = requestedGroup > 0
        ? project.active_revisions?.[String(requestedGroup)]
        : project.canonical_head_revision_id;
    return (
        catalog.find((item) => item.revision_id === activeId)
        || catalog.find((item) => item.revision_id === project.canonical_head_revision_id)
        || catalog.at(-1)
        || null
    );
}

function shortRevision(value) {
    const text = String(value || "");
    return text ? text.slice(0, 12) : "root";
}

function physicalGroupLabel(group) {
    return group.end > group.start
        ? `${group.start}-${group.end} (atomic)`
        : String(group.physical_group);
}

function takeLabel(item) {
    return `Group ${physicalGroupLabel(item.group)} / Take ${item.take_number}`;
}

function groupSetLabel(groups) {
    if (!groups.length) return "no groups";
    const ordered = [...groups].sort((left, right) => left.start - right.start);
    const allSingle = ordered.every((group) => group.start === group.end);
    const contiguous = ordered.every((group, index) => (
        index === 0 || group.start === ordered[index - 1].end + 1
    ));
    if (allSingle && contiguous && ordered.length > 1) {
        return `Groups ${ordered[0].start}-${ordered.at(-1).end}`;
    }
    if (ordered.length === 1) return `Group ${physicalGroupLabel(ordered[0])}`;
    return `Groups ${ordered.map(physicalGroupLabel).join(", ")}`;
}

function takeAncestry(project, selected, catalog) {
    const byId = new Map(catalog.map((item) => [item.revision_id, item]));
    const reverse = [];
    const seen = new Set();
    let revisionId = selected?.revision_id || null;
    while (revisionId) {
        if (seen.has(revisionId) || !byId.has(revisionId)) return [];
        seen.add(revisionId);
        const item = byId.get(revisionId);
        reverse.push(item);
        revisionId = item.parent_revision_id || null;
    }
    const chain = reverse.reverse();
    let expectedStart = 1;
    for (const item of chain) {
        if (item.group.start !== expectedStart) return [];
        expectedStart = item.group.end + 1;
    }
    return chain;
}

function continueFromTakeSummary(project, selected, catalog) {
    const chain = takeAncestry(project, selected, catalog);
    if (!chain.length) {
        return "Continue From Here: unavailable until provenance is validated";
    }
    const knownGroups = new Map();
    for (const item of catalog) {
        knownGroups.set(item.group.physical_group, item.group);
    }
    const later = [...knownGroups.values()].filter(
        (group) => group.start > selected.group.end,
    );
    const regenerate = later.length
        ? groupSetLabel(later)
        : `groups after ${physicalGroupLabel(selected.group)} (backend-determined)`;
    return (
        `Continue From Here: Reuse ${groupSetLabel(chain.map((item) => item.group))}`
        + ` | Regenerate ${regenerate}`
    );
}

function takeStatus(node) {
    const project = node.__h3ContinuumTakeProject;
    if (!project) return "No Render History yet";
    if (
        Number(project.run_storage_schema_version) === 2
        && Number(project.branch_provenance_version) !== 1
    ) {
        return (
            "Legacy Run Storage v2 detected\n"
            + "History is read-only until the next normal Queue reconstructs "
            + "Branch Provenance non-destructively."
        );
    }
    const catalog = takeCatalog(node);
    const selected = selectedTake(node);
    if (!selected) return "No completed Takes in this Run Storage";
    const activeId = project.active_revisions?.[String(selected.group.physical_group)];
    const canonical = catalog.find((item) => item.revision_id === activeId) || null;
    const canonicalHead = catalog.find(
        (item) => item.revision_id === project.canonical_head_revision_id,
    ) || null;
    const action = findWidget(node, TAKE_ACTION_WIDGET)?.value || TAKE_ACTION_AUTOMATIC;
    const rawCount = Array.isArray(project.group_revisions)
        ? project.group_revisions.length
        : 0;
    const hiddenCount = Math.max(0, rawCount - catalog.length);
    const lines = [
        `Selected: ${takeLabel(selected)} | ${shortRevision(selected.revision_id)}`,
        canonical
            ? `Canonical: ${takeLabel(canonical)} | ${shortRevision(canonical.revision_id)}`
            : "Canonical: unavailable",
        canonicalHead
            ? `Canonical head: ${takeLabel(canonicalHead)} | ${shortRevision(canonicalHead.revision_id)}`
            : "Canonical head: unavailable",
        `Compatible history: ${catalog.length} Take${catalog.length === 1 ? "" : "s"}`,
        continueFromTakeSummary(project, selected, catalog),
    ];
    if (hiddenCount) {
        lines.push(
            `${hiddenCount} incompatible or incomplete Take${hiddenCount === 1 ? "" : "s"} hidden`,
        );
    }
    if (findWidget(node, RUN_STORAGE_WIDGET)?.value === "Off") {
        lines.push("Run Storage: Off (history view only; a Take action enables storage)");
    }
    if (action !== TAKE_ACTION_AUTOMATIC) {
        const targetId = String(findWidget(node, TAKE_REVISION_WIDGET)?.value || "");
        const target = catalog.find(item => item.revision_id === targetId);
        lines.push(`Next Queue: ${action} — ${target ? takeLabel(target) : "selection unavailable"}`);
        lines.push("Browsing does not change the queued selection. Press an action to apply a different Take.");
    }
    return lines.join("\n");
}

function selectTakeOffset(node, offset) {
    const catalog = takeCatalog(node);
    if (!catalog.length) return;
    const current = selectedTake(node);
    const currentIndex = Math.max(0, catalog.findIndex(item => item.revision_id === current?.revision_id));
    const index = (currentIndex + offset + catalog.length) % catalog.length;
    node.__h3ContinuumBrowseRevision = catalog[index].revision_id;
    node.__h3ContinuumProductionUxRefresh?.();
    node.setDirtyCanvas?.(true, true);
}

function selectTakeAction(node, action) {
    const selected = selectedTake(node);
    if (!selected || reviewSettingsChanged(node) || activeReviewPrompt(node)) return;
    delete node.__h3ContinuumModeSetup;
    setExistingWidgetValue(
        findWidget(node, TAKE_GROUP_WIDGET),
        Number(selected.group.physical_group),
    );
    setExistingWidgetValue(
        findWidget(node, TAKE_REVISION_WIDGET),
        String(selected.revision_id),
    );
    setRegenerateProgrammatically(node, "Auto");
    setExistingWidgetValue(findWidget(node, RUN_STORAGE_WIDGET), "Save + Auto Resume");
    setExistingWidgetValue(findWidget(node, GENERATION_MODE_WIDGET), GENERATION_MODE_REVIEW);
    setReviewSeedControlFixed(node);
    setExistingWidgetValue(findWidget(node, REVIEW_ACTION_WIDGET), REVIEW_ACTION_CONTINUE);
    setExistingWidgetValue(findWidget(node, TAKE_ACTION_WIDGET), action);
    node.__h3ContinuumProductionUxRefresh?.();
    node.setDirtyCanvas?.(true, true);
}

function clearTakeSelection(node) {
    setExistingWidgetValue(findWidget(node, TAKE_GROUP_WIDGET), 0);
    setExistingWidgetValue(findWidget(node, TAKE_REVISION_WIDGET), "");
    setExistingWidgetValue(findWidget(node, TAKE_ACTION_WIDGET), TAKE_ACTION_AUTOMATIC);
}

async function loadTakeHistory(node, options = {}) {
    const runName = takeRunName(node);
    const requestedSettings = options.reviewedSettings ?? node.__h3ContinuumReadReviewSettings?.();
    const identityChanged = node.__h3ContinuumHistoryRun !== runName;
    if (identityChanged) {
        node.__h3ContinuumHistoryRun = runName;
        node.__h3ContinuumTakeProject = null;
        delete node.__h3ContinuumBrowseRevision;
        delete node.__h3ContinuumOutputFailure;
        delete node.__h3ContinuumQueueNotice;
        delete node.__h3ContinuumReviewedSettings;
        delete node.__h3ContinuumReviewedSettingsKey;
        clearTakeSelection(node);
    }
    if (!options.force && node.__h3ContinuumHistoryRequest?.runName === runName) {
        return node.__h3ContinuumHistoryRequest.promise;
    }
    const token = Number(node.__h3ContinuumTakeLoadToken || 0) + 1;
    node.__h3ContinuumTakeLoadToken = token;
    const current = () => node.__h3ContinuumTakeLoadToken === token && takeRunName(node) === runName;
    if (!runName) {
        node.__h3ContinuumTakeProject = null;
        delete node.__h3ContinuumTakeError;
        node.__h3ContinuumProductionUxRefresh?.();
        return false;
    }
    const promise = (async () => {
        try {
            const subfolder = `h3_continuum/runs/${runName}`;
            const response = await api.fetchApi(
                `/view?filename=project.json&type=output&subfolder=${encodeURIComponent(subfolder)}`,
                { cache: "no-store" },
            );
            if (!current()) return false;
            if (response.status === 404) {
                node.__h3ContinuumTakeProject = null;
                delete node.__h3ContinuumTakeError;
                return true;
            }
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const project = await response.json();
            if (!current()) return false;
            if (project?.run_name && project.run_name !== runName) {
                throw new Error("Run Storage identity does not match this request");
            }
            const legacy = Number(project?.run_storage_schema_version) === 2
                && Number(project?.branch_provenance_version) !== 1;
            if (!legacy && Number(project?.branch_provenance_version) !== 1) {
                throw new Error("Branch Provenance v1 is unavailable");
            }
            node.__h3ContinuumTakeProject = project;
            node.__h3ContinuumRememberReviewSettings?.(requestedSettings);
            repairStaleReviewRegenerate(node, project);
            delete node.__h3ContinuumTakeError;
            return true;
        } catch (error) {
            if (!current()) return false;
            node.__h3ContinuumTakeProject = null;
            node.__h3ContinuumTakeError = String(error?.message || error);
            return false;
        } finally {
            if (current()) node.__h3ContinuumProductionUxRefresh?.();
        }
    })();
    node.__h3ContinuumHistoryRequest = { runName, token, promise };
    try { return await promise; }
    finally {
        if (node.__h3ContinuumHistoryRequest?.token === token) delete node.__h3ContinuumHistoryRequest;
    }
}

// One immutable record per accepted prompt/node/run. Never correlate via
// Sampler `executed`: that event exists only for nodes returning UI output.
const reviewPrompts = new Map();
const reviewEarlyTerminals = new Map();
let reviewSubmissionCount = 0;
let reviewQueueSequence = 0;

function reviewRevisionKey(project) {
    const r = canonicalStorageRevision(project);
    return r ? JSON.stringify([r.revision_id, r.status, r.review_unit, r.updated_utc]) : "";
}

function reviewPromptRunName(inputs) {
    const explicit = String(inputs?.run_name || "").trim();
    if (explicit) return explicit;
    const id = String(inputs?.project_id || "").trim().toLowerCase();
    return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(id)
        ? `run_${id.replaceAll("-", "")}` : "";
}

function reviewPromptIncludes(output, nodeId, options) {
    const targets = options?.partialExecutionTargets;
    if (!Array.isArray(targets) || !targets.length) return true;
    const seen = new Set();
    const visit = (id) => {
        id = String(id);
        if (seen.has(id)) return;
        seen.add(id);
        for (const value of Object.values(output[id]?.inputs || {})) {
            if (Array.isArray(value) && value.length === 2 && output[String(value[0])]) visit(value[0]);
        }
    };
    targets.forEach(visit);
    return seen.has(String(nodeId));
}

function activeReviewPrompt(node) {
    for (const records of reviewPrompts.values()) {
        const item = !records.terminalEvent && records.find(r => r.node === node && r.runName === takeRunName(node));
        if (item) return item;
    }
    return null;
}

async function refreshV38TakeHistoryAfterExecution(event) {
    const promptId = String(event?.detail?.prompt_id || "");
    if (!promptId) return;
    const records = reviewPrompts.get(promptId);
    if (!records) {
        // A very fast execution may finish before the HTTP response. Buffer only
        // while a submission is in flight; unrelated prompts never affect nodes.
        if (reviewSubmissionCount && reviewEarlyTerminals.size < 64) {
            reviewEarlyTerminals.set(promptId, event);
        }
        return;
    }
    records.terminalEvent = event;
    if (records.processing) return records.processing;
    records.processing = (async () => {
    const pending = [];
    for (const record of records) {
        const node = record.node;
        if (takeRunName(node) !== record.runName || String(node.id) !== record.nodeId
                || !(app.graph?._nodes || []).includes(node)
                || record.sequence < Number(node.__h3ContinuumAppliedPromptSequence || 0)) continue;
        const ok = await loadTakeHistory(node, {force: true, reviewedSettings: record.settings});
        if (!ok) {
            if (takeRunName(node) === record.runName) pending.push(record);
            continue;
        }
        if (takeRunName(node) !== record.runName
                || record.sequence < Number(node.__h3ContinuumAppliedPromptSequence || 0)) continue;
        const project = node.__h3ContinuumTakeProject;
        const revision = canonicalStorageRevision(project);
        // Converted input widgets can submit a graph link rather than a literal
        // count. In that case the backend, not the browser, resolves its value.
        const requestedCount = !Array.isArray(record.intent.chunks)
            ? Number(record.intent.chunks) : NaN;
        const literalCount = Number.isInteger(requestedCount) && requestedCount > 0;
        const saved = revision && ["complete", "review_ready"].includes(revision.status)
            && (revision.status === "complete" || reviewHasUnit(node))
            && (!revision.review_unit || (reviewHasUnit(node)
                && (!literalCount || Number(revision.review_unit.end) <= requestedCount)));
        const changed = reviewRevisionKey(project) !== record.baseline;
        const success = event.type === "execution_success";
        const unchangedReview = success && !changed && revision?.status === "review_ready"
            && record.intent[GENERATION_MODE_WIDGET] === GENERATION_MODE_REVIEW
            && record.intent[TAKE_ACTION_WIDGET] !== TAKE_ACTION_USE;
        if (unchangedReview) {
            node.__h3ContinuumQueueNotice = "No new saved chunk was found for this Queue. Reload progress before continuing.";
        } else if (saved && (success || changed)) {
            delete node.__h3ContinuumQueueNotice;
            if (record.intent[REGENERATE_WIDGET] === "Auto" || record.intent[REGENERATE_WIDGET] === 0) {
                setRegenerateProgrammatically(node, "Auto");
                setExistingWidgetValue(findWidget(node, REROLL_NONCE_WIDGET), 0);
            }
            // Only this setup selection can be released. A later mode selection
            // or an edit to another Run is not owned by this execution.
            if (record.setup === node.__h3ContinuumModeSetup) delete node.__h3ContinuumModeSetup;
            node.__h3ContinuumReviewedSettings = record.settings;
            node.__h3ContinuumAppliedPromptSequence = record.sequence;
            if (success) delete node.__h3ContinuumOutputFailure;
            else node.__h3ContinuumOutputFailure = {
                promptId, runName: record.runName,
                revisionId: revision.revision_id,
                message: "Chunk saved; preview/output did not finish. Retry saved output without sampling a new Take.",
            };
        }
        node.__h3ContinuumIntuitiveUxRefresh?.();
        node.__h3ContinuumProductionUxRefresh?.();
    }
    if (reviewPrompts.get(promptId) === records) {
        if (pending.length) {
            pending.terminalEvent = event;
            reviewPrompts.set(promptId, pending);
        } else reviewPrompts.delete(promptId);
    }
    })();
    try { return await records.processing; } finally { delete records.processing; }
}

function installReviewQueueAdapter() {
    if (api.__h3ContinuumReviewQueueAdapter || typeof api.queuePrompt !== "function") return;
    const previous = api.queuePrompt;
    api.queuePrompt = async function(number, data, options, ...rest) {
        const output = { ...(data?.output || {}) };
        const records = [];
        for (const [nodeId, item] of Object.entries(output)) {
            if (item?.class_type !== V38_NODE_CLASS || !reviewPromptIncludes(output, nodeId, options)) continue;
            const node = app.graph?.getNodeById?.(nodeId)
                || app.graph?._nodes?.find(n => String(n.id) === nodeId);
            if (!node || node.comfyClass !== V38_NODE_CLASS) continue;
            requireFixedSeedForReview(node);
            const normalizedInputs = { ...(item.inputs || {}) };
            normalizeRunStorageState(node, normalizedInputs);
            const inputs = buildReviewQueueInputs(node, normalizedInputs);
            output[nodeId] = { ...item, inputs };
            records.push({ node, nodeId, runName: reviewPromptRunName(inputs),
                settings: reviewSettingsSnapshot(node), setup: node.__h3ContinuumModeSetup,
                baseline: reviewRevisionKey(node.__h3ContinuumTakeProject),
                intent: Object.freeze({ ...inputs }), sequence: ++reviewQueueSequence });
        }
        if (!records.length) return previous.call(this, number, data, options, ...rest);
        reviewSubmissionCount++;
        try {
            const response = await previous.call(this, number, {...data, output}, options, ...rest);
            const promptId = String(response?.prompt_id || "");
            if (!promptId) return response;
            reviewPrompts.set(promptId, records);
            for (const r of records) {
                delete r.node.__h3ContinuumQueueNotice;
                // Capture is per-prompt, never one mutable "last queue" slot.
                r.node[REVIEW_PENDING_ACTION] = r.intent[REVIEW_ACTION_WIDGET];
                r.node[TAKE_PENDING_ACTION] = r.intent[TAKE_ACTION_WIDGET];
                if (r.node.__h3ContinuumRestartSelected && r.intent[REGENERATE_WIDGET] === "Chunk 1") {
                    r.node.__h3ContinuumRestartQueued = true;
                }
                r.node.__h3ContinuumProductionUxRefresh?.();
            }
            const early = reviewEarlyTerminals.get(promptId);
            reviewEarlyTerminals.delete(promptId);
            if (early) await refreshV38TakeHistoryAfterExecution(early);
            return response;
        } finally {
            reviewSubmissionCount--;
            if (!reviewSubmissionCount) reviewEarlyTerminals.clear();
        }
    };
    api.__h3ContinuumReviewQueueAdapter = true;
}

let reviewSyncPromise = null;

async function synchronizeReviewQueue({discover = false} = {}) {
    if (reviewSyncPromise) return reviewSyncPromise;
    reviewSyncPromise = (async () => {
        let queue;
        try {
            const response = await api.fetchApi("/queue", {cache: "no-store"});
            if (!response.ok) return;
            queue = await response.json();
        } catch { return; } // A connection error is not cancellation or completion.
        const queued = [...(queue.queue_running || []), ...(queue.queue_pending || [])];
        const present = new Set(queued.map(item => String(item[1])));
        if (discover) {
            for (const item of queued) {
                const promptId = String(item[1] || "");
                const output = item[2] || {};
                if (!promptId || reviewPrompts.has(promptId)) continue;
                const records = [];
                for (const node of app.graph?._nodes || []) {
                    const nodeId = String(node.id);
                    const submitted = output[nodeId];
                    if (node.comfyClass !== V38_NODE_CLASS || submitted?.class_type !== V38_NODE_CLASS
                            || !reviewPromptIncludes(output, nodeId, {partialExecutionTargets: item[4]})
                            || reviewPromptRunName(submitted.inputs) !== takeRunName(node)) continue;
                    records.push({node, nodeId, runName: takeRunName(node),
                        settings: reviewSettingsSnapshot(node), setup: node.__h3ContinuumModeSetup,
                        baseline: reviewRevisionKey(node.__h3ContinuumTakeProject),
                        intent: Object.freeze({...submitted.inputs}), sequence: ++reviewQueueSequence});
                }
                if (records.length) reviewPrompts.set(promptId, records);
            }
        }
        for (const [promptId, records] of [...reviewPrompts]) {
            if (records.terminalEvent) {
                await refreshV38TakeHistoryAfterExecution(records.terminalEvent);
                continue;
            }
            if (present.has(promptId)) continue;
            try {
                const response = await api.fetchApi(`/history/${encodeURIComponent(promptId)}`, {cache:"no-store"});
                if (!response.ok) continue;
                const history = (await response.json())?.[promptId];
                if (history) {
                    const messages = history.status?.messages || [];
                    const terminal = [...messages].reverse().find(item => [
                        "execution_success", "execution_error", "execution_interrupted",
                    ].includes(item[0]));
                    if (terminal) await refreshV38TakeHistoryAfterExecution({type:terminal[0], detail:{prompt_id:promptId}});
                } else if (!reviewSubmissionCount) {
                    // No running/pending entry and no history: cancelled before
                    // execution. No invented commit and no automatic resampling.
                    reviewPrompts.delete(promptId);
                    for (const record of records) {
                        if (takeRunName(record.node) !== record.runName) continue;
                        record.node.__h3ContinuumQueueNotice = "Queued prompt is no longer pending. Refresh saved progress before continuing.";
                        record.node.__h3ContinuumIntuitiveUxRefresh?.();
                        record.node.__h3ContinuumProductionUxRefresh?.();
                    }
                }
            } catch { /* Keep ownership until the server can be read again. */ }
        }
    })();
    try { return await reviewSyncPromise; } finally { reviewSyncPromise = null; }
}

async function reloadReviewHistory() {
    for (const node of app.graph?._nodes || []) {
        if (node.comfyClass === V38_NODE_CLASS) await loadTakeHistory(node, {force: true});
    }
    await synchronizeReviewQueue({discover: true});
}

function reconcileReviewQueueStatus(event) {
    const remaining = event?.detail?.exec_info?.queue_remaining;
    if (remaining === 0 && reviewPrompts.size && !reviewSubmissionCount) {
        // Read the server queue/history rather than inferring completion from
        // a zero queue count. This also handles dropped terminal messages.
        return synchronizeReviewQueue();
    }
}

function retrySavedReviewOutput(node) {
    const project = node.__h3ContinuumTakeProject;
    const head = takeCatalog(node).find(r => r.revision_id === project?.canonical_head_revision_id);
    if (!head || reviewSettingsChanged(node) || activeReviewPrompt(node)) return;
    node.__h3ContinuumBrowseRevision = head.revision_id;
    selectTakeAction(node, TAKE_ACTION_USE);
}

function attachTakeHistoryReload(node) {
    for (const [name, key] of (
        [
            [RUN_STORAGE_WIDGET, "__h3ContinuumTakeStorageReload"],
            [LEGACY_RUN_NAME_WIDGET, "__h3ContinuumTakeRunNameReload"],
            [PROJECT_WIDGET, "__h3ContinuumTakeProjectReload"],
        ]
    )) {
        const widget = findWidget(node, name);
        if (!widget || widget[key]) continue;
        const previous = widget.callback;
        widget.callback = function(value, ...args) {
            const result = previous?.call(this, value, ...args);
            void loadTakeHistory(node);
            return result;
        };
        widget[key] = true;
    }
}

function configureProductionReviewUx(node) {
    if (node.comfyClass !== V38_NODE_CLASS || typeof node.addWidget !== "function") return;
    let statusWidget = transientProductionWidgets(node).find(
        (widget) => widget.name === PRODUCTION_STATUS_WIDGET,
    );
    if (!statusWidget) {
        statusWidget = addFacadeInfoWidget(
            node,
            PRODUCTION_STATUS_WIDGET,
            "review",
            68,
            false,
        );
        if (statusWidget) {
            statusWidget.disabled = true;
            setWidgetTooltip(statusWidget, (
                "Review and completion come from the saved backend revision. "
                + "After completion, retry the last reviewed unit or open Render History. "
                + "To extend, use Back to Settings, increase Chunks, then press Run. "
                + "The backend checks whether saved chunks can be reused."
            ));
        }
        const buttons = (
            [
                [PRODUCTION_CONTINUE_WIDGET, REVIEW_ACTION_CONTINUE],
                [PRODUCTION_REGENERATE_WIDGET, REVIEW_ACTION_REGENERATE],
                [PRODUCTION_FINISH_WIDGET, REVIEW_ACTION_FINISH],
            ]
        );
        for (const [name, action] of buttons) {
            const widget = addTransientProductionWidget(
                node,
                "button",
                name,
                null,
                () => selectProductionReviewAction(node, action),
            );
            if (widget) {
                setWidgetTooltip(widget, (
                    name === PRODUCTION_CONTINUE_WIDGET
                        ? "Keep the reviewed chunk and generate the next chunk after normal Queue."
                        : name === PRODUCTION_REGENERATE_WIDGET
                            ? "Create another Take for the reviewed chunk after normal Queue."
                            : "Keep the reviewed chunk and finish all remaining chunks after normal Queue."
                ));
            }
        }
        const retryOutput = addTransientProductionWidget(node, "button", PRODUCTION_OUTPUT_RETRY_WIDGET,
            null, () => retrySavedReviewOutput(node));
        setWidgetTooltip(retryOutput, "Reuse the saved canonical Take and retry decoding/saving. No new Sampling. Then press Queue.");
        const backToSettings = addTransientProductionWidget(
            node,
            "button",
            PRODUCTION_BACK_TO_SETTINGS_WIDGET,
            null,
            () => {
                node.__h3ContinuumReviewSettingsOpen = true;
                node.__h3ContinuumIntuitiveUxRefresh?.();
                node.__h3ContinuumProductionUxRefresh?.();
            },
        );
        if (backToSettings) {
            setWidgetTooltip(backToSettings, (
                "Show the normal Continuum settings without changing the pending review, "
                + "selected action, Take, or canonical branch."
            ));
        }
        const returnToReview = addTransientProductionWidget(
            node,
            "button",
            PRODUCTION_RETURN_TO_REVIEW_WIDGET,
            null,
            () => {
                delete node.__h3ContinuumModeSetup;
                node.__h3ContinuumReviewSettingsOpen = false;
                node.__h3ContinuumIntuitiveUxRefresh?.();
                node.__h3ContinuumProductionUxRefresh?.();
            },
        );
        if (returnToReview) {
            setWidgetTooltip(returnToReview, (
                "Return to the pending chunk review without changing any settings or Take state."
            ));
        }
        const restart = addTransientProductionWidget(
            node, "button", PRODUCTION_RESTART_WIDGET, null,
            () => selectProductionRestart(node),
        );
        if (restart) setWidgetTooltip(restart, (
            "Select a new branch from Chunk 1 using the current settings and automatic "
            + "Take variation. Press Queue afterward. Saved Takes are not deleted; "
            + "the restart selection is consumed once after Queue."
        ));
        const historyToggle = addTransientProductionWidget(
            node,
            "button",
            TAKE_TOGGLE_WIDGET,
            null,
            () => {
                node.__h3ContinuumHistoryOpen = !node.__h3ContinuumHistoryOpen;
                node.__h3ContinuumProductionUxRefresh?.();
            },
        );
        if (historyToggle) {
            setWidgetTooltip(historyToggle, "Open the stored Take list only when you need it.");
        }
        const takeStatusWidget = typeof node.addCustomWidget === "function"
            ? node.addCustomWidget({
                type: "h3_continuum_take_history",
                name: TAKE_STATUS_WIDGET,
                value: "No Render History yet",
                serialize: false,
                options: { serialize: false },
                [PRODUCTION_TRANSIENT_WIDGET]: true,
                draw(ctx, _node, width, y, height) {
                    const renderHeight = Math.max(
                        28,
                        Number(this.computeSize?.(width)?.[1] || height || 28),
                    );
                    ctx.save();
                    ctx.beginPath();
                    ctx.rect(15, y + 4, Math.max(1, width - 30), renderHeight - 8);
                    ctx.clip();
                    ctx.fillStyle = "#eeeeee";
                    ctx.font = "12px Arial";
                    ctx.textAlign = "left";
                    ctx.textBaseline = "top";
                    const lines = String(this.value || "").split("\n");
                    const count = Math.max(1, Math.floor((renderHeight - 12) / 16));
                    for (let i = 0; i < Math.min(lines.length, count); i++) {
                        ctx.fillText(lines[i], 18, y + 6 + i * 16, Math.max(1, width - 36));
                    }
                    ctx.restore();
                },
            })
            : addTransientProductionWidget(
            node,
            "text",
            TAKE_STATUS_WIDGET,
            "No Render History yet",
            null,
            { multiline: true },
        );
        if (takeStatusWidget) {
            takeStatusWidget.disabled = true;
            takeStatusWidget.computeSize = () => {
                const lines = String(takeStatusWidget.value || "").split("\n").length;
                return [
                    Math.max(300, Number(node.size?.[0] || 0)),
                    Math.min(124, Math.max(44, 12 + lines * 16)),
                ];
            };
            setWidgetTooltip(takeStatusWidget, (
                "Read-only Branch Provenance from Run Storage. Selecting a Take does not "
                + "change the canonical branch until Use This Take is queued normally."
            ));
        }
        for (const [name, callback] of (
            [
                [TAKE_PREVIOUS_WIDGET, () => selectTakeOffset(node, -1)],
                [TAKE_NEXT_WIDGET, () => selectTakeOffset(node, 1)],
                [TAKE_USE_WIDGET, () => selectTakeAction(node, TAKE_ACTION_USE)],
                [TAKE_CONTINUE_WIDGET, () => selectTakeAction(node, TAKE_ACTION_CONTINUE)],
            ]
        )) {
            const widget = addTransientProductionWidget(node, "button", name, null, callback);
            if (widget) {
                setWidgetTooltip(
                    widget,
                    name === TAKE_PREVIOUS_WIDGET || name === TAKE_NEXT_WIDGET
                        ? "Walk through stored physical-group Takes without changing the canonical branch."
                        : "Uses immutable physical-group revision provenance; Queue normally after selecting an action.",
                );
            }
        }
        installProductionSerializationGuard(node);

    }
    const refresh = () => {
        const reviewing = (
            findWidget(node, GENERATION_MODE_WIDGET)?.value === GENERATION_MODE_REVIEW
        );
        const storageEnabled = (
            findWidget(node, RUN_STORAGE_WIDGET)?.value === "Save + Auto Resume"
        );
        const historyOpen = storageEnabled && Boolean(node.__h3ContinuumHistoryOpen);
        const ready = reviewing && storageEnabled && reviewReady(node);
        const complete = canonicalStorageRevision(node.__h3ContinuumTakeProject)?.status === "complete";
        const readyRevisionId = ready
            ? String(canonicalStorageRevision(node.__h3ContinuumTakeProject)?.revision_id || "")
            : "";
        if (readyRevisionId && readyRevisionId !== node.__h3ContinuumReviewSettingsRevision) {
            node.__h3ContinuumReviewSettingsRevision = readyRevisionId;
            node.__h3ContinuumReviewSettingsOpen = false;
        } else if (!ready) {
            node.__h3ContinuumReviewSettingsOpen = false;
        }
        const modeSetup = Boolean(node.__h3ContinuumModeSetup);
        const settingsOpen = ready && !modeSetup && Boolean(node.__h3ContinuumReviewSettingsOpen);
        const reviewOpen = ready && !modeSetup && !settingsOpen;
        const from = findWidget(node, REGENERATE_WIDGET)?.value;
        const edited = reviewSettingsChanged(node);
        const outputFailure = node.__h3ContinuumOutputFailure?.runName === takeRunName(node);
        const busy = Boolean(activeReviewPrompt(node));
        const canReview = !edited && !busy && !outputFailure && (!from || from === "Auto" || from === 0);
        const takeCount = takeCatalog(node).length;
        const actionNames = new Set([
            PRODUCTION_STATUS_WIDGET,
            PRODUCTION_CONTINUE_WIDGET,
            PRODUCTION_REGENERATE_WIDGET,
            PRODUCTION_FINISH_WIDGET,
        ]);
        const historyNames = new Set([
            TAKE_STATUS_WIDGET,
            TAKE_PREVIOUS_WIDGET,
            TAKE_NEXT_WIDGET,
            TAKE_USE_WIDGET,
            TAKE_CONTINUE_WIDGET,
        ]);
        for (const widget of transientProductionWidgets(node)) {
            if (widget[FACADE_TRANSIENT_WIDGET]) continue;
            if (widget.name === PRODUCTION_STATUS_WIDGET) {
                setWidgetVisible(widget, reviewOpen);
            } else if (widget.name === PRODUCTION_OUTPUT_RETRY_WIDGET) {
                setWidgetVisible(widget, reviewOpen && outputFailure);
                widget.disabled = edited || busy;
            } else if (widget.name === PRODUCTION_REGENERATE_WIDGET) {
                setWidgetVisible(widget, reviewOpen && canReview && reviewHasUnit(node));
            } else if (
                widget.name === PRODUCTION_CONTINUE_WIDGET
                || widget.name === PRODUCTION_FINISH_WIDGET
            ) {
                setWidgetVisible(widget, reviewOpen && canReview && !complete);
            } else if (actionNames.has(widget.name)) {
                setWidgetVisible(widget, reviewOpen);
            } else if (widget.name === PRODUCTION_BACK_TO_SETTINGS_WIDGET) {
                setWidgetVisible(widget, reviewOpen);
            } else if (widget.name === PRODUCTION_RETURN_TO_REVIEW_WIDGET) {
                setWidgetVisible(widget, settingsOpen || (ready && modeSetup));
            } else if (widget.name === PRODUCTION_RESTART_WIDGET) {
                setWidgetVisible(widget, ready && !busy);
            } else if (widget.name === TAKE_TOGGLE_WIDGET) {
                setWidgetVisible(widget, reviewOpen && takeCount > 0);
            } else if (historyNames.has(widget.name)) {
                setWidgetVisible(widget, reviewOpen && historyOpen && takeCount > 0);
            }
        }
        if (statusWidget) {
            const [headline, detail = ""] = reviewStatus(node).split("\n", 2);
            statusWidget.headline = headline;
            statusWidget.detail = detail;
            statusWidget.value = detail ? `${headline}\n${detail}` : headline;
            statusWidget.__h3ContinuumInfoVariant = "review";
        }
        const takeStatusWidget = transientProductionWidgets(node).find(
            (widget) => widget.name === TAKE_STATUS_WIDGET,
        );
        if (takeStatusWidget) {
            takeStatusWidget.value = node.__h3ContinuumTakeError
                ? `Render History unavailable: ${node.__h3ContinuumTakeError}`
                : takeStatus(node);
        }
        const catalog = takeCatalog(node);
        const hasSelection = Boolean(selectedTake(node));
        const takeActionAvailable = hasSelection && !edited && !busy;
        const historyToggle = transientProductionWidgets(node).find(
            (widget) => widget.name === TAKE_TOGGLE_WIDGET,
        );
        if (historyToggle) {
            const count = catalog.length;
            historyToggle.label = historyOpen
                ? "Close Render History"
                : `Render History — ${count} Take${count === 1 ? "" : "s"}`;
        }
        const selectedAction = node[REVIEW_UI_SELECTION];
        for (const [name, action] of (
            [
                [PRODUCTION_CONTINUE_WIDGET, REVIEW_ACTION_CONTINUE],
                [PRODUCTION_REGENERATE_WIDGET, REVIEW_ACTION_REGENERATE],
                [PRODUCTION_FINISH_WIDGET, REVIEW_ACTION_FINISH],
            ]
        )) {
            const widget = transientProductionWidgets(node).find((item) => item.name === name);
            if (widget) widget.label = selectedAction === action ? `✓ ${name}` : name;
        }
        for (const name of [TAKE_PREVIOUS_WIDGET, TAKE_NEXT_WIDGET]) {
            const widget = transientProductionWidgets(node).find((item) => item.name === name);
            if (widget) widget.disabled = catalog.length < 2;
        }
        for (const name of [TAKE_USE_WIDGET, TAKE_CONTINUE_WIDGET]) {
            const widget = transientProductionWidgets(node).find((item) => item.name === name);
            if (widget) widget.disabled = !takeActionAvailable;
        }
        if (reviewOpen) {
            for (const widget of facadeProductionWidgets(node)) {
                if (
                    widget.name !== FACADE_ADVANCED_WIDGET
                    && widget.name !== FACADE_REFERENCE_SIZE_WIDGET
                    && widget.name !== FACADE_VIDEO_SIZE_WIDGET
                ) {
                    setWidgetVisible(widget, false);
                }
            }
            moveNamedWidgetsToFront(
                node,
                [
                    PRODUCTION_STATUS_WIDGET,
                    PRODUCTION_OUTPUT_RETRY_WIDGET,
                    PRODUCTION_CONTINUE_WIDGET,
                    PRODUCTION_REGENERATE_WIDGET,
                    PRODUCTION_FINISH_WIDGET,
                    PRODUCTION_BACK_TO_SETTINGS_WIDGET,
                    PRODUCTION_RESTART_WIDGET,
                    TAKE_TOGGLE_WIDGET,
                    TAKE_STATUS_WIDGET,
                    TAKE_PREVIOUS_WIDGET,
                    TAKE_NEXT_WIDGET,
                    TAKE_USE_WIDGET,
                    TAKE_CONTINUE_WIDGET,
                    FACADE_ADVANCED_WIDGET,
                    FACADE_REFERENCE_SIZE_WIDGET,
                    FACADE_VIDEO_SIZE_WIDGET,
                ],
            );
        } else if (settingsOpen && Array.isArray(node.__h3ContinuumFacadeOrder)) {
            const readyFacade = facadeProductionWidgets(node).find(
                (widget) => widget.name === FACADE_READY_WIDGET,
            );
            if (readyFacade) {
                const [headline, detail = ""] = reviewStatus(node).split("\n", 2);
                readyFacade.headline = headline;
                readyFacade.detail = detail;
                readyFacade.value = detail ? `${headline}\n${detail}` : headline;
                readyFacade.__h3ContinuumInfoVariant = "review";
            }
            const settingsOrder = [...node.__h3ContinuumFacadeOrder];
            const readyIndex = settingsOrder.indexOf(FACADE_READY_WIDGET);
            settingsOrder.splice(
                readyIndex >= 0 ? readyIndex + 1 : settingsOrder.length,
                0,
                PRODUCTION_RETURN_TO_REVIEW_WIDGET,
                PRODUCTION_RESTART_WIDGET,
            );
            moveNamedWidgetsToFront(node, settingsOrder);
        } else if (Array.isArray(node.__h3ContinuumFacadeOrder)) {
            if (ready && modeSetup) {
                const order = [...node.__h3ContinuumFacadeOrder];
                const at = order.indexOf(FACADE_READY_WIDGET);
                order.splice(at < 0 ? order.length : at + 1, 0,
                    PRODUCTION_RETURN_TO_REVIEW_WIDGET, PRODUCTION_RESTART_WIDGET);
                moveNamedWidgetsToFront(node, order);
            } else moveFacadeWidgetsToFront(node, node.__h3ContinuumFacadeOrder);
        }
        // Connected duration controls stay directly below the normal inputs,
        // including while the settings facade is replaced by Review/History.
        const connectedDuration = [];
        for (const [source, facade] of [[CHUNKS_WIDGET, FACADE_CHUNKS_WIDGET], ["chunk_seconds", FACADE_SECONDS_WIDGET]]) {
            if (!linkedInput(node, [source])) continue;
            setWidgetVisible(findWidget(node, facade), true);
            connectedDuration.push(facade);
        }
        if (connectedDuration.length) moveNamedWidgetsToFront(node, connectedDuration);
        node._widgetSlotsDirty = true;
        node.setDirtyCanvas?.(true, true);
    };
    node.__h3ContinuumProductionUxRefresh = refresh;
    if (!node.__h3ContinuumReviewRemovalGuard) {
        const previous = node.onRemoved;
        node.onRemoved = function(...args) {
            this.__h3ContinuumTakeLoadToken = Number(this.__h3ContinuumTakeLoadToken || 0) + 1;
            for (const [id, records] of reviewPrompts) {
                const remaining = records.filter(record => record.node !== this);
                if (remaining.length) reviewPrompts.set(id, remaining);
                else reviewPrompts.delete(id);
            }
            return previous?.apply(this, args);
        };
        node.__h3ContinuumReviewRemovalGuard = true;
    }
    node.__h3ContinuumReviewSettingsChanged = () => reviewSettingsChanged(node);
    node.__h3ContinuumRememberReviewSettings = (requested) => rememberReviewSettings(node, requested);
    node.__h3ContinuumReadReviewSettings = () => reviewSettingsSnapshot(node);
    // Upstream prompt/media edits also invalidate review, not just local widgets.
    if (!node.__h3ContinuumReviewDrawWatch) {
        const previous = node.onDrawForeground;
        node.onDrawForeground = function(...args) {
            const result = previous?.apply(this, args);
            const changed = reviewSettingsChanged(this);
            if (changed !== this.__h3ContinuumReviewDrawChanged) {
                this.__h3ContinuumReviewDrawChanged = changed;
                this.__h3ContinuumIntuitiveUxRefresh?.();
                this.__h3ContinuumProductionUxRefresh?.();
            }
            return result;
        };
        node.__h3ContinuumReviewDrawWatch = true;
    }
    for (const [name, key] of (
        [
            [RUN_STORAGE_WIDGET, "__h3ContinuumProductionStorageRefresh"],
            [REGENERATE_WIDGET, "__h3ContinuumProductionRegenerateRefresh"],
            [REROLL_NONCE_WIDGET, "__h3ContinuumProductionNonceRefresh"],
            [GENERATION_MODE_WIDGET, "__h3ContinuumProductionModeRefresh"],
            [REVIEW_ACTION_WIDGET, "__h3ContinuumProductionActionRefresh"],
            [TAKE_GROUP_WIDGET, "__h3ContinuumTakeGroupRefresh"],
            [TAKE_REVISION_WIDGET, "__h3ContinuumTakeRevisionRefresh"],
            [TAKE_ACTION_WIDGET, "__h3ContinuumTakeActionRefresh"],
        ]
    )) {
        attachRefresh(findWidget(node, name), key, refresh);
    }
    attachTakeHistoryReload(node);
    for (const widget of node.widgets || []) {
        if (!widget[PRODUCTION_TRANSIENT_WIDGET] && !widget[FACADE_TRANSIENT_WIDGET]) {
            attachRefresh(widget, "__h3ContinuumReviewEditRefresh", refresh);
        }
    }
    refresh();
}

function normalizedV38View(node) {
    return node.__h3ContinuumAdvancedOpen ? V38_VIEW_PRODUCTION : V38_VIEW_BASIC;
}

function applyV38View(node) {
    if (node.comfyClass !== V38_NODE_CLASS) return;
    node.__h3ContinuumIntuitiveUxRefresh?.();
    node.__h3ContinuumProductionUxRefresh?.();
    if (!node.__h3ContinuumTakeInitialLoad) {
        node.__h3ContinuumTakeInitialLoad = true;
        void loadTakeHistory(node);
    }
    node.setDirtyCanvas?.(true, true);
}

function configureV38ViewProperty(node) {
    if (node.comfyClass !== V38_NODE_CLASS) return V38_VIEW_BASIC;
    node.properties ||= {};
    if (!node.__h3ContinuumLegacyViewMigrated) {
        node.__h3ContinuumAdvancedOpen = (
            node.properties[V38_VIEW_PROPERTY] === V38_VIEW_PRODUCTION
        );
        delete node.properties[V38_VIEW_PROPERTY];
        node.__h3ContinuumLegacyViewMigrated = true;
    }
    return normalizedV38View(node);
}

function normalizeRunStorageState(node, apiInputs = null) {
    const storageWidget = findWidget(node, RUN_STORAGE_WIDGET);
    const storageEnabled = storageWidget?.value === "Save + Auto Resume";
    if (storageEnabled) {
        return true;
    }
    const nonceWidget = findWidget(node, REROLL_NONCE_WIDGET);
    setRegenerateProgrammatically(node, "Auto");
    if (nonceWidget) nonceWidget.value = 0;
    if (apiInputs) {
        apiInputs[REGENERATE_WIDGET] = "Auto";
        apiInputs[REROLL_NONCE_WIDGET] = 0;
    }
    return false;
}

function configureConditionalWidgets(node) {
    const storageWidget = findWidget(node, RUN_STORAGE_WIDGET);
    const regenerateWidget = findWidget(node, REGENERATE_WIDGET);
    const nonceWidget = findWidget(node, REROLL_NONCE_WIDGET);
    const runNameWidget = findWidget(node, LEGACY_RUN_NAME_WIDGET);
    if (regenerateWidget && !regenerateWidget.__h3ContinuumManualIntentCallback) {
        const previous = regenerateWidget.callback;
        regenerateWidget.callback = function(value, ...args) {
            const result = previous?.call(this, value, ...args);
            if (!node.__h3ContinuumProgrammaticRegenerate) {
                if (value === "Auto" || value === 0 || value == null) {
                    delete node.__h3ContinuumManualRegenerateIntent;
                } else {
                    node.__h3ContinuumManualRegenerateIntent = true;
                }
            }
            return result;
        };
        regenerateWidget.__h3ContinuumManualIntentCallback = true;
    }
    const refresh = () => {
        const productionView = true;
        const storageEnabled = node.comfyClass === V38_NODE_CLASS
            ? storageWidget?.value === "Save + Auto Resume"
            : normalizeRunStorageState(node);
        const explicitRegeneration = storageEnabled
            && regenerateWidget?.value !== "Auto"
            && Number.parseInt(String(regenerateWidget?.value).replace(/^Chunk\s+/, ""), 10) > 0;
        setWidgetVisible(regenerateWidget, storageEnabled && productionView);
        setWidgetVisible(runNameWidget, storageEnabled && productionView);
        setWidgetVisible(nonceWidget, explicitRegeneration && productionView);
        setWidgetVisible(
            findWidget(node, REFERENCE_SIZE_WIDGET),
            productionView
                && linkedInput(node, ["reference_image_1", "reference_image_2", "reference_image_3"]),
        );
        setWidgetVisible(
            findWidget(node, TIMELINE_SIZE_WIDGET),
            linkedInput(node, ["timeline_video"]),
        );
        setWidgetVisible(
            findWidget(node, VIDEO_REFERENCE_SIZE_WIDGET),
            productionView && linkedInput(node, ["reference_video_1"]),
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

function configureResolutionPresetWidgets(node) {
    if (node.comfyClass !== V38_NODE_CLASS) {
        return;
    }
    const aspectWidget = findWidget(node, LEGACY_ASPECT_WIDGET);
    const sizeSourceWidget = findWidget(node, SIZE_SOURCE_WIDGET);
    const widthWidget = findWidget(node, WIDTH_WIDGET);
    const heightWidget = findWidget(node, HEIGHT_WIDGET);
    const presetWidget = findWidget(node, RESOLUTION_PRESET_WIDGET);
    const customMpWidget = findWidget(node, CUSTOM_MP_WIDGET);
    if (!sizeSourceWidget || !widthWidget || !heightWidget) return;

    const roundCanvas = (value) => Math.max(
        CANVAS_MULTIPLE,
        Math.floor(Number(value) / CANVAS_MULTIPLE + 0.5) * CANVAS_MULTIPLE,
    );
    const presetSize = (aspectRatio) => {
        const preset = presetWidget?.value;
        if (preset === RESOLUTION_PRESET_NATIVE) {
            const landscape = aspectRatio >= 1;
            const majorRatio = landscape ? aspectRatio : 1 / aspectRatio;
            let shortEdge = NATIVE_SHORT_EDGE;
            let longEdge = shortEdge * majorRatio;
            if (longEdge > NATIVE_LONG_EDGE_CAP) {
                longEdge = NATIVE_LONG_EDGE_CAP;
                shortEdge = longEdge / majorRatio;
            }
            const longPx = Math.min(NATIVE_LONG_EDGE_CAP, roundCanvas(longEdge));
            const shortPx = Math.min(NATIVE_SHORT_EDGE, roundCanvas(shortEdge));
            return landscape ? [longPx, shortPx] : [shortPx, longPx];
        }
        const megapixels = preset === RESOLUTION_PRESET_DRAFT
            ? 0.30
            : preset === RESOLUTION_PRESET_BALANCED
                ? 0.60
                : Number(customMpWidget?.value || 0.30);
        const targetPixels = megapixels * 1_000_000;
        return [
            roundCanvas(Math.sqrt(targetPixels * aspectRatio)),
            roundCanvas(Math.sqrt(targetPixels / aspectRatio)),
        ];
    };
    const firstImageGeometry = () => {
        const input = node.inputs?.find((item) => item.name === "first_frame");
        if (input?.link == null) return null;
        const link = app.graph?.links?.[input.link];
        const source = app.graph?.getNodeById?.(link?.origin_id);
        if (!source || Number(source.mode) === 4) return null;
        const image = source.imgs?.[0];
        const width = Number(image?.naturalWidth || image?.width || 0);
        const height = Number(image?.naturalHeight || image?.height || 0);
        return width > 0 && height > 0 ? { width, height } : null;
    };
    const migrateLegacyAspect = () => {
        if (sizeSourceWidget.value !== SIZE_SOURCE_LEGACY) return;
        const legacy = String(aspectWidget?.value || "Auto from First Image");
        if (legacy === "Auto from First Image") {
            sizeSourceWidget.value = SIZE_SOURCE_FIRST_IMAGE;
            return;
        }
        const ratio = legacy === "Portrait 9:16"
            ? 9 / 16
            : legacy === "Square 1:1"
                ? 1
                : 16 / 9;
        const [width, height] = presetSize(ratio);
        widthWidget.value = width;
        heightWidget.value = height;
        sizeSourceWidget.value = SIZE_SOURCE_MANUAL;
    };
    migrateLegacyAspect();
    sizeSourceWidget.options ||= {};
    sizeSourceWidget.options.values = [SIZE_SOURCE_FIRST_IMAGE, SIZE_SOURCE_MANUAL];
    hidePersistentWidget(aspectWidget);

    const refresh = () => {
        migrateLegacyAspect();
        const firstImage = sizeSourceWidget.value === SIZE_SOURCE_FIRST_IMAGE;
        const geometry = firstImage ? firstImageGeometry() : null;
        if (geometry) {
            [widthWidget.value, heightWidget.value] = presetSize(
                geometry.width / geometry.height,
            );
        }
        widthWidget.disabled = firstImage;
        heightWidget.disabled = firstImage;
        presetWidget.disabled = !firstImage;
        widthWidget.tooltip = firstImage
            ? "Resolved from First Image at Queue time. The displayed value updates when exact frontend image geometry is available."
            : "Manual output width. Must be aligned to 32 pixels.";
        heightWidget.tooltip = firstImage
            ? "Resolved from First Image at Queue time. The displayed value updates when exact frontend image geometry is available."
            : "Manual output height. Must be aligned to 32 pixels.";
        setWidgetVisible(
            customMpWidget,
            firstImage && presetWidget?.value === CUSTOM_RESOLUTION_PRESET,
        );
        node.setDirtyCanvas?.(true, true);
    };
    attachRefresh(sizeSourceWidget, "__h3ContinuumSizeSourceCallback", refresh);
    attachRefresh(presetWidget, "__h3ContinuumResolutionPresetCallback", refresh);
    attachRefresh(customMpWidget, "__h3ContinuumCustomMpCallback", refresh);
    attachRefresh(widthWidget, "__h3ContinuumWidthCallback", refresh);
    attachRefresh(heightWidget, "__h3ContinuumHeightCallback", refresh);
    if (!node.__h3ContinuumResolutionConnectionCallback) {
        const previous = node.onConnectionsChange;
        node.onConnectionsChange = function(...args) {
            const result = previous?.apply(this, args);
            setTimeout(refresh, 0);
            return result;
        };
        node.__h3ContinuumResolutionConnectionCallback = true;
    }
    if (!node.__h3ContinuumResolutionConfigureGuard) {
        const originalConfigure = node.configure;
        const sizeSourceIndex = node.widgets?.indexOf(sizeSourceWidget) ?? -1;
        if (typeof originalConfigure === "function" && sizeSourceIndex >= 0) {
            node.configure = function(info, ...args) {
                const values = Array.isArray(info?.widgets_values)
                    ? info.widgets_values
                    : [];
                const hasExplicitSizeSource = values.length > sizeSourceIndex;
                const result = originalConfigure.call(this, info, ...args);
                if (!hasExplicitSizeSource) {
                    sizeSourceWidget.value = SIZE_SOURCE_LEGACY;
                    migrateLegacyAspect();
                }
                refresh();
                return result;
            };
        }
        node.__h3ContinuumResolutionConfigureGuard = true;
    }
    node.__h3ContinuumResolutionUxRefresh = refresh;
    refresh();
}

function isOneShotReviewAction(value) {
    return value === REVIEW_ACTION_REGENERATE || value === REVIEW_ACTION_FINISH;
}

function normalizeReviewActionOnLoad(node) {
    if (node.comfyClass !== V38_NODE_CLASS) {
        return false;
    }
    delete node[REVIEW_PENDING_ACTION];
    delete node[REVIEW_UI_SELECTION];
    let changed = false;
    const actionWidget = findWidget(node, REVIEW_ACTION_WIDGET);
    if (actionWidget && isOneShotReviewAction(actionWidget.value)) {
        actionWidget.value = REVIEW_ACTION_CONTINUE;
        changed = true;
    }
    const takeActionWidget = findWidget(node, TAKE_ACTION_WIDGET);
    if (takeActionWidget && takeActionWidget.value !== TAKE_ACTION_AUTOMATIC) {
        takeActionWidget.value = TAKE_ACTION_AUTOMATIC;
        changed = true;
    }
    return changed;
}

function resetReviewActionAfterQueued(node) {
    const pendingAction = node[REVIEW_PENDING_ACTION];
    delete node[REVIEW_PENDING_ACTION];
    delete node[REVIEW_UI_SELECTION];
    if (!isOneShotReviewAction(pendingAction)) {
        return false;
    }
    const actionWidget = findWidget(node, REVIEW_ACTION_WIDGET);
    if (!actionWidget || actionWidget.value !== pendingAction) {
        return false;
    }
    actionWidget.value = REVIEW_ACTION_CONTINUE;
    actionWidget.callback?.(REVIEW_ACTION_CONTINUE);
    node.setDirtyCanvas?.(true, true);
    return true;
}

function resetTakeActionAfterQueued(node) {
    const pendingAction = node[TAKE_PENDING_ACTION];
    delete node[TAKE_PENDING_ACTION];
    if (pendingAction !== TAKE_ACTION_USE && pendingAction !== TAKE_ACTION_CONTINUE) {
        return false;
    }
    const actionWidget = findWidget(node, TAKE_ACTION_WIDGET);
    if (!actionWidget || actionWidget.value !== pendingAction) return false;
    actionWidget.value = TAKE_ACTION_AUTOMATIC;
    actionWidget.callback?.(TAKE_ACTION_AUTOMATIC);
    node.setDirtyCanvas?.(true, true);
    return true;
}

function buildReviewQueueInputs(node, apiInputs) {
    const result = { ...apiInputs };
    const value = (name, fallback) => result[name] ?? findWidget(node, name)?.value ?? fallback;
    const mode = value(GENERATION_MODE_WIDGET, GENERATION_MODE_FULL_RUN);
    const storage = value(RUN_STORAGE_WIDGET, "Off");
    const setup = Boolean(node.__h3ContinuumModeSetup);
    const stale = reviewSettingsChanged(node);
    let from = value(REGENERATE_WIDGET, "Auto");
    let nonce = value(REROLL_NONCE_WIDGET, 0);

    // A Run mode change is never a hidden restart. Repair only an unowned
    // stale Chunk 1 boundary; explicit Advanced regeneration stays explicit.
    if (
        setup
        && from === "Chunk 1"
        && !node.__h3ContinuumManualRegenerateIntent
        && !node.__h3ContinuumRestartSelected
    ) {
        from = "Auto";
        nonce = 0;
    }
    // Backend rejects regeneration without Run Storage. Normalize the impossible
    // combination before submission and keep the visible controls consistent.
    if (storage !== "Save + Auto Resume") {
        from = "Auto";
        nonce = 0;
        setRegenerateProgrammatically(node, "Auto");
        setExistingWidgetValue(findWidget(node, REROLL_NONCE_WIDGET), 0);
    }
    result[REGENERATE_WIDGET] = from;
    result[REROLL_NONCE_WIDGET] = nonce;
    const manual = from && from !== "Auto" && from !== 0;
    result[GENERATION_MODE_WIDGET] = mode;
    result[REVIEW_ACTION_WIDGET] = mode === GENERATION_MODE_FULL_RUN || manual || setup || stale
        ? REVIEW_ACTION_CONTINUE : value(REVIEW_ACTION_WIDGET, REVIEW_ACTION_CONTINUE);
    for (const [name, fallback] of [[TAKE_GROUP_WIDGET, 0], [TAKE_REVISION_WIDGET, ""],
        [TAKE_ACTION_WIDGET, TAKE_ACTION_AUTOMATIC]]) {
        result[name] = setup || stale ? fallback : value(name, fallback);
    }
    return result;
}

function prepareReviewQueueIntent(node, apiInputs) {
    if (node.comfyClass !== V38_NODE_CLASS || !apiInputs) return false;
    Object.assign(apiInputs, buildReviewQueueInputs(node, apiInputs));
    return true;
}

function configureReviewControls(node) {
    if (node.comfyClass !== V38_NODE_CLASS) {
        return;
    }
    const generationWidget = findWidget(node, GENERATION_MODE_WIDGET);
    const actionWidget = findWidget(node, REVIEW_ACTION_WIDGET);
    const storageWidget = findWidget(node, RUN_STORAGE_WIDGET);
    const takeActionWidget = findWidget(node, TAKE_ACTION_WIDGET);
    if (!generationWidget || !actionWidget) {
        return;
    }
    const refresh = () => {
        setWidgetVisible(
            actionWidget,
            generationWidget.value === GENERATION_MODE_REVIEW,
        );
        node.setDirtyCanvas?.(true, true);
    };
    if (!generationWidget.__h3ContinuumReviewModeCallback) {
        const previous = generationWidget.callback;
        generationWidget.callback = function(value, ...args) {
            const result = previous?.call(this, value, ...args);
            if (
                value === GENERATION_MODE_REVIEW
                && storageWidget?.value === "Off"
            ) {
                storageWidget.value = "Save + Auto Resume";
                storageWidget.callback?.("Save + Auto Resume");
            }
            if (value === GENERATION_MODE_REVIEW) {
                setReviewSeedControlFixed(node);
            }
            refresh();
            return result;
        };
        generationWidget.__h3ContinuumReviewModeCallback = true;
    }
    if (generationWidget.value === GENERATION_MODE_REVIEW) {
        setReviewSeedControlFixed(node);
    }
    if (!actionWidget.__h3ContinuumReviewAfterQueued) {
        const previous = actionWidget.afterQueued;
        actionWidget.afterQueued = function(...args) {
            const result = previous?.apply(this, args);
            resetReviewActionAfterQueued(node);
            resetTakeActionAfterQueued(node);
            if (node.__h3ContinuumRestartQueued) {
                delete node.__h3ContinuumRestartQueued;
                delete node.__h3ContinuumRestartSelected;
                const from = findWidget(node, REGENERATE_WIDGET);
                if (from?.value === "Chunk 1") {
                    setRegenerateProgrammatically(node, "Auto");
                }
            }
            return result;
        };
        actionWidget.__h3ContinuumReviewAfterQueued = true;
    }
    if (takeActionWidget && !takeActionWidget.__h3ContinuumTakeAfterQueued) {
        const previous = takeActionWidget.afterQueued;
        takeActionWidget.afterQueued = function(...args) {
            const result = previous?.apply(this, args);
            resetTakeActionAfterQueued(node);
            return result;
        };
        takeActionWidget.__h3ContinuumTakeAfterQueued = true;
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
    const isV36 = node.comfyClass === V36_NODE_CLASS;
    const isV37 = node.comfyClass === V37_NODE_CLASS;
    const isV38 = node.comfyClass === V38_NODE_CLASS;
    if (!isProduction && !isTimeline && !isV34 && !isV35 && !isV36 && !isV37 && !isV38) {
        configureAssembler(node);
        return null;
    }
    const projectWidget = findWidget(node, PROJECT_WIDGET);
    if (isProduction || isV34 || isV35 || isV36 || isV37 || isV38) {
        if (projectWidget && !String(projectWidget.value || "").trim()) {
            projectWidget.value = createProjectId();
        }
        if (!isV38) removeUnusedInput(node, PROMPT_OVERRIDES_INPUT);
    }
    applyRuntimeSettings(node);
    if (isV35 || isV36 || isV37 || isV38) {
        normalizeReferenceAudioLabels(node);
    }
    hidePersistentWidget(findWidget(node, "diagnostics"));
    hidePersistentWidget(findWidget(node, "strict_compatibility"));
    hidePersistentWidget(findWidget(node, "debug"));
    hidePersistentWidget(findWidget(node, "show_preview"));
    hidePersistentWidget(projectWidget);
    hidePersistentWidget(findWidget(node, TAKE_GROUP_WIDGET));
    hidePersistentWidget(findWidget(node, TAKE_REVISION_WIDGET));
    hidePersistentWidget(findWidget(node, TAKE_ACTION_WIDGET));
    configureV38ViewProperty(node);
    configureRegenerateFrom(node);
    configureConditionalWidgets(node);
    configureResolutionPresetWidgets(node);
    configureReviewControls(node);
    configureIntuitiveV38Ux(node);
    configureProductionReviewUx(node);
    applyV38View(node);
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
        installReviewQueueAdapter();
        api.addEventListener("reconnected", reloadReviewHistory);
        api.addEventListener("status", reconcileReviewQueueStatus);
        for (const eventName of [
            "execution_success",
            "execution_error",
            "execution_interrupted",
        ]) {
            api.addEventListener(
                eventName,
                refreshV38TakeHistoryAfterExecution,
            );
        }
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
        normalizeReviewActionOnLoad(node);
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
            if (apiNode?.inputs) {
                if (
                    node.comfyClass === PRODUCTION_NODE_CLASS
                    || node.comfyClass === TIMELINE_NODE_CLASS
                    || node.comfyClass === V34_NODE_CLASS
                    || node.comfyClass === V35_NODE_CLASS
                    || node.comfyClass === V36_NODE_CLASS
                    || node.comfyClass === V37_NODE_CLASS
                    || node.comfyClass === V38_NODE_CLASS
                ) {
                    node.__h3ContinuumResolutionUxRefresh?.();
                    requireFixedSeedForReview(node);
                    normalizeRunStorageState(node, apiNode.inputs);
                    prepareReviewQueueIntent(node, apiNode.inputs);
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
