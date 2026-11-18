const CLASS = "H3ContinuumReferenceImagesV39";
const SAMPLER = "H3ContinuumSamplerV39";
const MAX = 16;
const LEGACY_SAMPLER_INPUTS = new Set([
    ...Array.from({ length: 5 }, (_, index) => `reference_image_${index + 1}`),
    "image_references",
]);
const getWidget = (node, name) => node.widgets?.find((item) => item.name === name);
const element = (tag, value = "") => {
    const item = document.createElement(tag);
    item.textContent = value;
    return item;
};

function savedChunks(value) {
    const text = String(value ?? "off").trim().toLowerCase();
    if (text === "off") return { chunks: new Set() };
    if (text === "all") return { chunks: new Set(Array.from({ length: MAX }, (_, i) => i + 1)) };
    const result = new Set();
    for (const token of text.split(",")) {
        const match = token.trim().match(/^(\d+)(?:\s*-\s*(\d+))?$/);
        if (!match) return { error: "invalid saved selection." };
        const first = Number(match[1]);
        const last = Number(match[2] || match[1]);
        if (first < 1 || last > MAX || first > last) return { error: "invalid saved selection." };
        for (let n = first; n <= last; n += 1) {
            if (result.has(n)) return { error: `invalid saved selection. Chunk ${n} appears more than once.` };
            result.add(n);
        }
    }
    return { chunks: result };
}

function linkedSamplers(node) {
    const output = node.outputs?.find((item) => item.name === "reference_images");
    return (output?.links || []).map((id) => {
        const link = node.graph?.links?.[id];
        return node.graph?.getNodeById?.(link?.target_id);
    }).filter((target) => target?.comfyClass === SAMPLER);
}

function destination(node) {
    const targets = linkedSamplers(node);
    const unknown = (reason) => ({ count: MAX, known: false, reason });
    if (!targets.length) return unknown("no_sampler");
    if (targets.some((target) => target.inputs?.some((input) => input.name === "chunks" && input.link != null))) {
        return unknown("external_chunks");
    }
    const counts = targets.map((target) => Number(getWidget(target, "chunks")?.value));
    if (!counts.every((n) => Number.isInteger(n) && n >= 1 && n <= MAX)) return unknown("unavailable_count");
    if (!counts.every((n) => n === counts[0])) return unknown("different_counts");
    return { count: counts[0], known: true, reason: "direct_count" };
}

function invalidate(node) {
    for (const target of linkedSamplers(node)) {
        target.__h3ContinuumReferencePlan = null;
        target.__h3ContinuumIntuitiveUxRefresh?.();
        target.setDirtyCanvas?.(true, true);
    }
}

export function connectedV39LegacyReferenceInputs(node) {
    if (node?.comfyClass !== SAMPLER) return [];
    return (node.inputs || []).filter((input) =>
        LEGACY_SAMPLER_INPUTS.has(input.name) && input.link != null
    ).map((input) => input.name);
}

export function pruneV39LegacyReferenceInputs(node) {
    if (node?.comfyClass !== SAMPLER || typeof node.removeInput !== "function") return 0;
    let removed = 0;
    for (let index = (node.inputs?.length || 0) - 1; index >= 0; index -= 1) {
        const input = node.inputs[index];
        if (!LEGACY_SAMPLER_INPUTS.has(input.name) || input.link != null) continue;
        node.removeInput(index);
        removed += 1;
    }
    if (removed) {
        node.__h3ContinuumReferencePlan = null;
        node.setDirtyCanvas?.(true, true);
    }
    return removed;
}

export function configureV39ReferenceImages(node) {
    if (node?.comfyClass !== CLASS || typeof document === "undefined") return;
    const mode = getWidget(node, "reference_use");
    const selectors = Array.from({ length: 9 }, (_, i) => getWidget(node, `reference_r${i + 1}_chunks`));
    if (!mode || selectors.some((item) => !item)) return;
    if (node.__h3ReferenceImagesRefresh) return node.__h3ReferenceImagesRefresh();
    if (typeof node.addDOMWidget !== "function") return;
    // The standard STRING widgets remain serializable; only their presentation is hidden.
    for (const item of selectors) {
        item.type = "hidden";
        item.hidden = true;
        item.options ||= {};
        item.options.hidden = true;
        item.computeSize = () => [0, 0];
        item.draw = () => {};
    }
    const panel = element("div");
    panel.style.cssText = "box-sizing:border-box;min-width:340px;max-height:360px;overflow:auto;padding:7px;color:#e7f4e9;background:#203827;font:12px Arial;pointer-events:auto";
    const host = element("div");
    host.style.cssText = "box-sizing:border-box;padding-top:8px;pointer-events:auto";
    host.append(panel);
    for (const name of ["pointerdown", "mousedown", "mouseup", "dblclick"]) {
        host.addEventListener(name, (event) => event.stopPropagation());
    }
    const display = node.addDOMWidget("reference_assignment", "h3_reference_assignment", host, { serialize: false });
    display.options ||= {};
    display.options.serialize = false;
    let panelHeight = 54;
    display.computeSize = (width) => [Math.max(340, Number(width) || Number(node.size?.[0]) || 340), panelHeight + 8];
    const reservePanelSpace = (height) => {
        panelHeight = height;
        panel.style.height = `${height}px`;
        const computedHeight = Number(node.computeSize?.()[1]);
        const width = Number(node.size?.[0]) || 340;
        if (Number.isFinite(computedHeight) && typeof node.setSize === "function"
            && (Number(node.size?.[0]) !== width || Number(node.size?.[1]) !== computedHeight)) {
            node.setSize([width, computedHeight]);
        }
    };
    let page = 0;
    let previousKey = null;
    const setSelection = (slot, selection) => {
        const target = selectors[slot - 1];
        target.value = [...selection].sort((a, b) => a - b).join(",") || "off";
        // The wrapped native callback owns invalidation and the immediate refresh.
        target.callback?.(target.value);
    };
    const refresh = () => {
        const { count, known, reason } = destination(node);
        const rows = Array.from({ length: 9 }, (_, i) => i + 1).filter((slot) =>
            node.inputs?.some((input) => input.name === `reference_image_${slot}` && input.link != null));
        const key = JSON.stringify([mode.value, count, known, reason, rows, selectors.map((item) => item.value), page]);
        if (key === previousKey) return;
        previousKey = key;
        panel.replaceChildren();
        if (mode.value !== "Per chunk") {
            panel.append(element("div", "Connected images are used in all chunks."));
            reservePanelSpace(54);
            return;
        }
        panel.append(element("div", known ? `Per-chunk assignments · ${count} chunks` : "Per-chunk assignments · range 1–16"));
        if (!known) {
            const explanation = {
                no_sampler: "Connect this helper to a Sampler to determine its chunk count.",
                external_chunks: "Chunk count is supplied by a connected node.",
                unavailable_count: "The Sampler chunk count is not available.",
                different_counts: "Connected Samplers have different chunk counts.",
            };
            panel.append(element("div", explanation[reason]));
            panel.append(element("div", "Assignments apply only to chunks generated by the Sampler."));
        }
        if (!rows.length) {
            panel.append(element("div", "Connect Reference Images to assign them."));
            reservePanelSpace(known ? 64 : 104);
            return;
        }
        page = Math.min(page, Math.ceil(count / 6) - 1);
        const first = page * 6 + 1;
        const last = Math.min(first + 5, count);
        if (count > 6) {
            const nav = element("div");
            for (const [label, targetPage] of [["◀", page - 1], [`${first}–${last} / ${count}`, page], ["▶", page + 1]]) {
                const button = element("button", label);
                button.type = "button";
                button.disabled = targetPage < 0 || targetPage >= Math.ceil(count / 6) || targetPage === page;
                button.onclick = () => { page = targetPage; previousKey = null; refresh(); };
                nav.append(button);
            }
            panel.append(nav);
        }
        const table = element("table");
        table.style.cssText = "width:100%;border-collapse:collapse;text-align:center;color:#e7f4e9";
        const header = element("tr");
        header.append(element("th", "Image"));
        for (let n = first; n <= last; n += 1) header.append(element("th", String(n)));
        header.append(element("th", "All / Off"));
        table.append(header);
        const selections = new Map(rows.map(slot => [slot, savedChunks(selectors[slot - 1].value)]));
        for (const slot of rows) {
            const selected = selections.get(slot).chunks;
            const row = element("tr");
            row.append(element("td", `Image ${slot} · @R${slot}`));
            for (let n = first; n <= last; n += 1) {
                const cell = element("td");
                const checkbox = element("input");
                checkbox.type = "checkbox";
                checkbox.checked = selected?.has(n) || false;
                checkbox.disabled = !selected;
                checkbox.setAttribute("aria-label", `Image ${slot}, Chunk ${n}`);
                checkbox.onchange = () => {
                    const updated = new Set(selected);
                    if (checkbox.checked) updated.add(n); else updated.delete(n);
                    setSelection(slot, updated);
                };
                cell.append(checkbox);
                row.append(cell);
            }
            const actions = element("td");
            for (const [label, on] of [["All", true], ["Off", false]]) {
                const reset = !selected && !on;
                const button = element("button", reset ? "Reset to Off" : known ? label : `${label} 1–16`);
                button.type = "button";
                button.disabled = !selected && !reset;
                button.onclick = () => {
                    if (reset) { setSelection(slot, new Set()); return; }
                    const updated = new Set(selected);
                    for (let n = 1; n <= count; n += 1) {
                        if (on) updated.add(n); else updated.delete(n);
                    }
                    setSelection(slot, updated);
                };
                actions.append(button);
            }
            row.append(actions);
            table.append(row);
        }
        panel.append(table);
        for (const slot of rows) {
            const { chunks: selected, error } = selections.get(slot);
            if (error) {
                panel.append(element("div", `Image ${slot}: ${error}`));
                continue;
            }
            if (!known) {
                const saved = [...selected].sort((a, b) => a - b);
                panel.append(element("div", `Image ${slot} → Saved assignments: ${saved.join(", ") || "none"}`));
                continue;
            }
            const active = [...selected].filter((n) => n <= count).sort((a, b) => a - b);
            const future = [...selected].filter((n) => n > count).sort((a, b) => a - b);
            panel.append(element("div", `Image ${slot} → Chunks ${active.join(", ") || "none"}${future.length ? ` · saved beyond range: ${future.join(", ")}` : ""}`));
        }
        if (rows.every(slot => {
            const selected = selections.get(slot).chunks;
            return selected && ![...selected].some(n => n <= count);
        })) {
            panel.append(element("div", known ? "No references assigned. Check the chunks to use." : "No saved assignments. Check the chunks to use."));
        }
        reservePanelSpace(Math.min(360, 77 + rows.length * 36 + (count > 6 ? 32 : 0) + (known ? 0 : 40)));
        node.setDirtyCanvas?.(true, true);
    };
    node.__h3ReferenceImagesRefresh = refresh;
    const oldConnections = node.onConnectionsChange;
    node.onConnectionsChange = function(...args) {
        const result = oldConnections?.apply(this, args);
        invalidate(this);
        refresh();
        return result;
    };
    for (const control of [mode, ...selectors]) {
        const previous = control.callback;
        control.callback = function(...args) {
            const result = previous?.apply(this, args);
            invalidate(node);
            refresh();
            return result;
        };
    }
    refresh();
}

export function refreshV39ReferenceImagesForSampler(node) {
    if (node?.comfyClass !== SAMPLER) return;
    const input = node.inputs?.find((item) => item.name === "reference_images");
    const link = node.graph?.links?.[input?.link];
    const source = node.graph?.getNodeById?.(link?.origin_id);
    if (source?.comfyClass === CLASS) configureV39ReferenceImages(source);
}
