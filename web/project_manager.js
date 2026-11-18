import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

// Optional metadata UI. No graph hooks, Queue wrapper, background fetch or timer.
const ENABLED = "H3Continuum.ProjectManager.Enabled";
const BASE = "/h3-continuum/project-manager/projects";
const words = {
    en: {
        title: "Project / Take", experimental: "Experimental · V1.2", enable: "Enable Project / Take Manager (experimental)",
        open: "Open Project / Take", close: "Close", refresh: "Refresh", project: "Project", attempt: "Trial / Run",
        savepoint: "Named savepoints", target: "Target Sampler", noTarget: "No available V3.9 Sampler", select: "Select…",
        create: "Create Project", newAttempt: "New trial", attach: "Add current Run", save: "Name selected Take",
        rename: "Rename", archive: "Archive", restore: "Restore", archived: "Show archived items", name: "Name",
        prepare: "Prepare from savepoint", prepareAttempt: "Prepare new trial", loading: "Loading…", retry: "Retry pending update",
        note: "Savepoints reference existing Takes; they are not backups. Prompts, models and workflow settings are not restored.",
        queue: "Preparation opens the existing Review controls. Generate with the normal Queue button.",
        saved: "Management information saved. Your workflow has not been changed.", prepared: "Prepared. Check the Sampler and use the normal Queue button.",
        fresh: "A separate trial was created. Use Prepare new trial to switch the target Sampler to it.",
        disabled: "Enable Project / Take Manager in Settings → H3Continuum → Project Manager first.",
        changed: "The graph or target Sampler changed. Select it again and retry preparation.",
        missing: "Select a Project, trial or savepoint first.", requiredName: "Enter a name first.",
        wrongRun: "The selected Take must belong to the selected trial. Add the current Run or select its trial first.",
        noTake: "Select a saved Take in Render History first.", unavailable: "Project Manager is unavailable. Existing generation is unaffected.",
        secureIds: "This browser cannot generate secure operation IDs. Use HTTPS, localhost, or a supported browser.",
        conflict: "This Project changed in another tab. Refresh and review it before trying a new update.",
        uncertain: "The update result is unknown. Retry pending update uses the same operation ID; do not create a second update.",
        enableLabel: "Experimental Project / Take Manager", empty: "No items yet", chunk: "Through Chunk", viewError: "Some Projects could not be read",
    },
    ja: {
        title: "Project / Take", experimental: "試験機能 · V1.2", enable: "Project / Take Managerを有効にする（試験機能）",
        open: "Project / Takeを開く", close: "閉じる", refresh: "更新", project: "Project", attempt: "試行 / Run",
        savepoint: "名前付き保存点", target: "対象Sampler", noTarget: "利用できるV3.9 Samplerがありません", select: "選択…",
        create: "Projectを作成", newAttempt: "新しい試行", attach: "現在のRunを追加", save: "選択Takeに名前を付ける",
        rename: "名前を変更", archive: "アーカイブ", restore: "戻す", archived: "アーカイブも表示", name: "名前",
        prepare: "保存点から再開準備", prepareAttempt: "新しい試行へ切替準備", loading: "読み込み中…", retry: "未確認の更新を再確認",
        note: "保存点は既存Takeへの参照です。バックアップではなく、プロンプト・モデル・ワークフロー設定の復元も行いません。",
        queue: "再開準備後は既存Reviewで確認し、通常のQueueから生成します。",
        saved: "管理情報を保存しました。ワークフローは変更していません。", prepared: "準備できました。Samplerを確認し、通常のQueueから生成してください。",
        fresh: "独立した試行を作成しました。「新しい試行へ切替準備」で対象Samplerへ反映できます。",
        disabled: "設定 → H3Continuum → Project Managerで、先に試験機能を有効にしてください。",
        changed: "グラフまたは対象Samplerが変わりました。選び直して再開準備をやり直してください。",
        missing: "Project・試行・保存点を選択してください。", requiredName: "名前を入力してください。",
        wrongRun: "選択Takeと試行のRunが異なります。現在のRunを追加するか、対応する試行を選んでください。",
        noTake: "先にRender Historyで保存済みTakeを選択してください。", unavailable: "Project Managerを利用できません。従来の生成はそのまま利用できます。",
        secureIds: "このブラウザーでは安全な操作IDを生成できません。HTTPS・localhost、または対応ブラウザーをご利用ください。",
        conflict: "別のタブでProjectが更新されました。更新して内容を確認してから操作してください。",
        uncertain: "更新結果を確認できません。同じ操作IDで再確認できます。新しい更新を重ねないでください。",
        enableLabel: "試験機能 Project / Take Manager", empty: "まだありません", chunk: "Chunk", viewError: "読み込めないProjectがあります",
    },
};

function text() {
    const locale = app.ui?.settings?.getSettingValue?.("Comfy.Locale") || globalThis.navigator?.language || "en";
    return String(locale).startsWith("ja") ? words.ja : words.en;
}
function enabled() { return app.ui?.settings?.getSettingValue?.(ENABLED, false) === true; }
function el(tag, label, parent) {
    const node = document.createElement(tag);
    if (label != null) node.textContent = label;
    parent?.append(node);
    return node;
}
function button(label, parent, action) {
    const node = el("button", label, parent); node.type = "button";
    Object.assign(node.style, { padding: "7px 9px", cursor: "pointer", borderRadius: "5px" });
    node.addEventListener("click", action);
    return node;
}
function uuid() {
    const crypto = globalThis.crypto;
    if (typeof crypto?.randomUUID === "function") return crypto.randomUUID();
    if (typeof crypto?.getRandomValues !== "function") throw new Error(text().secureIds);
    // getRandomValues also works where randomUUID requires a secure context.
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = Array.from(bytes, b => b.toString(16).padStart(2, "0"));
    return `${hex.slice(0, 4).join("")}-${hex.slice(4, 6).join("")}-${hex.slice(6, 8).join("")}-${hex.slice(8, 10).join("")}-${hex.slice(10).join("")}`;
}
async function request(url, body) {
    let response;
    try {
        response = await api.fetchApi(url, body === undefined ? { cache: "no-store" } : {
            method: "POST", cache: "no-store", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
        });
    } catch { throw Object.assign(new Error(text().unavailable), { uncertain: body !== undefined }); }
    let value;
    try { value = await response.json(); } catch {
        throw Object.assign(new Error(`${text().unavailable} (HTTP ${response.status})`), { uncertain: body !== undefined && (response.ok || response.status >= 500) });
    }
    if (!response.ok) {
        const conflict = response.status === 409 && value?.code === "project_revision_conflict";
        throw Object.assign(new Error(conflict ? text().conflict : (value?.error || `HTTP ${response.status}`)), {
            status: response.status, revisionConflict: conflict, uncertain: body !== undefined && response.status >= 500,
        });
    }
    if (!value || typeof value !== "object" || Array.isArray(value)) {
        throw Object.assign(new Error(text().unavailable), { uncertain: body !== undefined });
    }
    return value;
}
function projectValue(value) {
    if (typeof value?.id !== "string" || !Number.isInteger(value.revision) || !Array.isArray(value.attempts) || !Array.isArray(value.savepoints)) {
        throw Object.assign(new Error(text().unavailable), { uncertain: true });
    }
    return value;
}

let opened = null;
// Retain an unresolved write across panel close/reopen. Never auto-replay it.
let pendingWrite = null;

export function openProjectManager(event) {
    if (!enabled()) { globalThis.alert?.(text().disabled); return; }
    if (opened?.panel.isConnected) { opened.panel.focus(); return; }
    // Host dialogs can detach body children without invoking our Close button.
    // Invalidate their async work before creating a replacement panel.
    opened?.close();
    const t = text();
    const parent = event?.currentTarget?.closest?.('[role="dialog"], dialog') || document.body;
    const panel = el("aside", null, parent);
    panel.setAttribute("role", "dialog"); panel.setAttribute("aria-label", t.title); panel.tabIndex = -1;
    Object.assign(panel.style, {
        position: "fixed", right: "12px", top: "64px", bottom: "12px", width: "420px", maxWidth: "calc(100vw - 24px)",
        zIndex: "1001", background: "var(--comfy-menu-bg, #24282e)", color: "var(--fg-color, #eee)",
        border: "1px solid var(--border-color, #59616d)", borderRadius: "10px", boxShadow: "0 8px 32px #0008",
        padding: "16px", boxSizing: "border-box", overflow: "auto", font: "13px/1.5 system-ui, sans-serif",
    });
    const header = el("div", null, panel); Object.assign(header.style, { display: "flex", alignItems: "center", gap: "8px" });
    const title = el("strong", t.title, header); title.style.fontSize = "18px"; title.style.flex = "1";
    const close = button(t.close, header, () => closePanel());
    el("small", t.experimental, panel).style.color = "#eab96c";
    const status = el("p", "", panel); status.setAttribute("role", "status"); status.setAttribute("aria-live", "polite");
    const toolbar = el("div", null, panel);
    const refresh = button(t.refresh, toolbar, () => perform(refreshAll));
    const retry = button(t.retry, toolbar, () => perform(retryWrite));
    const archivedLabel = el("label", null, panel); archivedLabel.style.display = "block";
    const showArchived = el("input", null, archivedLabel); showArchived.type = "checkbox";
    el("span", ` ${t.archived}`, archivedLabel);
    const targetLabel = el("label", t.target, panel); targetLabel.style.display = "block";
    const target = el("select", null, targetLabel); target.setAttribute("aria-label", t.target); target.style.width = "100%";
    let projects = [], project = null, selectedAttempt = "", selectedSavepoint = "", busy = false, closed = false, epoch = 0;
    let targets = [];
    const controls = [];
    const sections = {};
    for (const [key, label] of [["project", t.project], ["attempt", t.attempt], ["savepoint", t.savepoint]]) {
        const section = el("section", null, panel); Object.assign(section.style, { marginTop: "14px", paddingTop: "10px", borderTop: "1px solid #58606a" });
        el("strong", label, section);
        const list = el("select", null, section); list.setAttribute("aria-label", label); list.size = key === "project" ? 1 : 4;
        Object.assign(list.style, { width: "100%", display: "block", margin: "6px 0", padding: "4px" });
        const name = el("input", null, section); name.type = "text"; name.maxLength = 120; name.placeholder = `${label} — ${t.name}`;
        name.setAttribute("aria-label", `${label} ${t.name}`); Object.assign(name.style, { width: "100%", boxSizing: "border-box", marginBottom: "6px", padding: "6px" });
        const row = el("div", null, section); Object.assign(row.style, { display: "flex", flexWrap: "wrap", gap: "5px" });
        sections[key] = { section, list, name, row }; controls.push(list, name);
    }
    const p = sections.project, a = sections.attempt, s = sections.savepoint;
    const addProject = button(t.create, p.row, () => perform(async () => {
        const name = requiredName(p.name); const id = uuid();
        await write({ url: BASE, body: { name, project_id: id, operation_id: uuid() } });
    }));
    const renameProject = button(t.rename, p.row, () => perform(() => mutate("rename_project", { name: requiredName(p.name) })));
    const archiveProject = button(t.archive, p.row, () => perform(() => mutate("archive_project", { archived: !project?.archived })));
    const addAttempt = button(t.newAttempt, a.row, () => perform(async () => {
        await mutate("new_attempt", { name: requiredName(a.name) }); status.textContent = t.fresh;
    }));
    const attachAttempt = button(t.attach, a.row, () => perform(async () => {
        const identity = targetContext().description;
        if (!identity.run_name) throw new Error(t.noTake);
        await mutate("attach_attempt", { name: requiredName(a.name), run_name: identity.run_name });
    }));
    const renameAttempt = button(t.rename, a.row, () => perform(() => mutate("rename_attempt", { attempt_id: attempt().id, name: requiredName(a.name) })));
    const archiveAttempt = button(t.archive, a.row, () => perform(() => mutate("archive_attempt", { attempt_id: attempt().id, archived: !attempt().archived })));
    const prepareAttempt = button(t.prepareAttempt, a.section, () => perform(async () => {
        const item = attempt(), context = targetContext(), id = project.id;
        if (item.run_name || !item.project_id) throw new Error(t.noTake);
        await context.bridge.prepareRun({ run_name: "", project_id: item.project_id,
            isCurrent: contextGuard(context, () => project?.id === id && selectedAttempt === item.id) });
        assertContext(context, false); status.textContent = t.prepared;
    }));
    const addSavepoint = button(t.save, s.row, () => perform(async () => {
        const item = attempt(), context = targetContext(), identity = context.description;
        if (!identity.revision_id) throw new Error(t.noTake);
        if (identity.run_name !== (item.storage_name || item.run_name)) throw new Error(t.wrongRun);
        await mutate("savepoint", { attempt_id: item.id, name: requiredName(s.name), revision_id: identity.revision_id });
    }));
    const renameSavepoint = button(t.rename, s.row, () => perform(() => mutate("rename_savepoint", { savepoint_id: savepoint().id, name: requiredName(s.name) })));
    const archiveSavepoint = button(t.archive, s.row, () => perform(() => mutate("archive_savepoint", { savepoint_id: savepoint().id, archived: !savepoint().archived })));
    const prepare = button(t.prepare, s.section, () => perform(async () => {
        const item = savepoint(), context = targetContext(), id = project.id;
        const prepared = await request(`${BASE}/${encodeURIComponent(id)}/prepare`, { savepoint_id: item.id });
        assertContext(context);
        if (project?.id !== id || selectedSavepoint !== item.id) throw new Error(t.changed);
        await context.bridge.prepareRun({ ...prepared,
            isCurrent: contextGuard(context, () => project?.id === id && selectedSavepoint === item.id) });
        assertContext(context, false); status.textContent = t.prepared;
    }));
    Object.assign(prepare.style, { width: "100%", marginTop: "9px", background: "#2466a3", color: "white", border: "1px solid #4486c3" });
    el("p", t.queue, panel); el("small", t.note, panel).style.opacity = ".8";
    controls.push(addProject, renameProject, archiveProject, addAttempt, attachAttempt, renameAttempt, archiveAttempt,
        prepareAttempt, addSavepoint, renameSavepoint, archiveSavepoint, prepare, target, showArchived);
    function closePanel() { closed = true; epoch++; panel.remove(); if (opened?.panel === panel) opened = null; }
    opened = { panel, close: closePanel, writeSettled(value, error) {
        if (closed) return;
        if (value) acceptProject(value);
        else {
            if (error?.revisionConflict) project = null;
            status.textContent = String(error?.message || t.unavailable);
        }
        updateControls();
    } };
    function requiredName(input) { const value = input.value.trim(); if (!value) throw new Error(t.requiredName); return value; }
    function attempt() { const item = project?.attempts.find(x => x.id === selectedAttempt); if (!item) throw new Error(t.missing); return item; }
    function savepoint() { const item = project?.savepoints.find(x => x.id === selectedSavepoint); if (!item) throw new Error(t.missing); return item; }
    function targetContext() {
        const node = targets.find(n => String(n.id) === target.value);
        const bridge = node?.__h3ContinuumManagerBridge;
        if (!bridge || !app.graph?._nodes?.includes(node)) throw new Error(t.noTarget);
        return { node, bridge, graph: app.graph, target: target.value, description: bridge.describe() };
    }
    function assertContext(context, identity = true) {
        if (closed || app.graph !== context.graph || !app.graph?._nodes?.includes(context.node) || target.value !== context.target
            || context.node.__h3ContinuumManagerBridge !== context.bridge) throw new Error(t.changed);
        if (identity) {
            const current = context.bridge.describe();
            for (const key of ["run_name", "project_id", "revision_id"]) if (current[key] !== context.description[key]) throw new Error(t.changed);
        }
    }
    function contextGuard(context, selection) {
        return () => {
            if (!enabled() || !selection()) return false;
            try { assertContext(context); return true; } catch { return false; }
        };
    }
    function fill(select, values, value, label) {
        select.replaceChildren();
        const blank = el("option", values.length ? t.select : t.empty, select); blank.value = "";
        for (const item of values) { const option = el("option", label(item), select); option.value = String(item.id); }
        select.value = values.some(x => String(x.id) === value) ? value : "";
        return select.value;
    }
    function visible(items) { return items.filter(x => showArchived.checked || !x.archived); }
    function renderTargets() {
        targets = (app.graph?._nodes || []).filter(n => n.__h3ContinuumManagerBridge);
        const old = target.value;
        fill(target, targets, old, n => `${n.title || "H3 Continuum V3.9"} #${n.id}`);
        if (!old && targets.length === 1) target.value = String(targets[0].id);
    }
    function render() {
        fill(p.list, visible(projects), project?.id || "", x => `${x.name}${x.archived ? " · archive" : ""}`);
        selectedAttempt = fill(a.list, visible(project?.attempts || []), selectedAttempt, x => x.name);
        const points = visible(project?.savepoints || []).filter(x => x.attempt_id === selectedAttempt);
        selectedSavepoint = fill(s.list, points, selectedSavepoint, x => `${x.name}${x.group?.end ? ` · ${t.chunk} ${x.group.end}` : ""}`);
        updateControls();
    }
    function updateControls() {
        const blocked = busy || !!pendingWrite;
        for (const item of controls) item.disabled = blocked;
        refresh.disabled = busy || !!pendingWrite; retry.disabled = busy || !pendingWrite;
        retry.hidden = !pendingWrite;
        const hasProject = !!project, hasAttempt = project?.attempts.some(x => x.id === selectedAttempt), hasPoint = project?.savepoints.some(x => x.id === selectedSavepoint);
        for (const item of [renameProject, archiveProject, addAttempt, attachAttempt]) item.disabled ||= !hasProject;
        for (const item of [renameAttempt, archiveAttempt, prepareAttempt, addSavepoint]) item.disabled ||= !hasAttempt;
        for (const item of [renameSavepoint, archiveSavepoint, prepare]) item.disabled ||= !hasPoint;
        for (const item of [prepareAttempt, addSavepoint, attachAttempt, prepare]) item.disabled ||= !target.value;
        for (const item of [addAttempt, attachAttempt, addSavepoint, prepareAttempt, prepare]) item.disabled ||= !!project?.archived;
        archiveProject.textContent = project?.archived ? t.restore : t.archive;
        archiveAttempt.textContent = hasAttempt && attempt().archived ? t.restore : t.archive;
        archiveSavepoint.textContent = hasPoint && savepoint().archived ? t.restore : t.archive;
        if (hasAttempt) { prepareAttempt.disabled ||= !!attempt().run_name || !attempt().project_id || !!attempt().archived; addSavepoint.disabled ||= !!attempt().archived; }
        if (hasPoint) prepare.disabled ||= !!savepoint().archived;
        if (target.value) {
            try { const d = targetContext().description; for (const item of [prepareAttempt, prepare]) item.disabled ||= !!d.busy; }
            catch { prepareAttempt.disabled = prepare.disabled = true; }
        }
    }
    async function refreshAll() {
        const token = ++epoch, id = project?.id;
        const value = await request(BASE);
        if (closed || token !== epoch) return;
        if (!Array.isArray(value.projects)) throw new Error(t.unavailable);
        projects = value.projects;
        if (id && projects.some(x => x.id === id)) {
            const current = projectValue(await request(`${BASE}/${encodeURIComponent(id)}`));
            if (closed || token !== epoch) return; project = current;
        } else { project = null; selectedAttempt = selectedSavepoint = ""; }
        renderTargets(); render(); status.textContent = value.errors?.length ? `${t.viewError}: ${value.errors.length}` : "";
    }
    async function write(operation) {
        pendingWrite = operation;
        try {
            const value = projectValue(await request(operation.url, operation.body));
            if (pendingWrite === operation) pendingWrite = null;
            if (closed) { opened?.writeSettled(value); return; }
            acceptProject(value);
        } catch (error) {
            if (!error.uncertain && pendingWrite === operation) pendingWrite = null;
            if (error.revisionConflict) project = null;
            if (error.uncertain) error.message += ` ${t.uncertain}`;
            if (closed) opened?.writeSettled(null, error);
            throw error;
        }
    }
    function acceptProject(value) {
        project = value;
        const index = projects.findIndex(x => x.id === value.id);
        if (index < 0) projects.push(value); else projects[index] = value;
        selectedAttempt = value.last_result?.attempt_id || selectedAttempt;
        selectedSavepoint = value.last_result?.savepoint_id || selectedSavepoint;
        render(); status.textContent = t.saved;
    }
    async function retryWrite() { if (pendingWrite) await write(pendingWrite); }
    async function mutate(action, payload) {
        if (!project) throw new Error(t.missing);
        await write({ url: `${BASE}/${encodeURIComponent(project.id)}/operations`, body: { revision: project.revision, operation_id: uuid(), action, ...payload } });
    }
    async function perform(action) {
        if (closed || busy) return;
        busy = true; updateControls(); status.textContent = t.loading;
        try { await action(); }
        catch (error) { if (!closed) status.textContent = String(error?.message || error); }
        finally { busy = false; if (!closed) updateControls(); }
    }
    p.list.addEventListener("change", () => perform(async () => {
        const id = p.list.value, token = ++epoch;
        project = null; selectedAttempt = selectedSavepoint = "";
        if (id) {
            const value = projectValue(await request(`${BASE}/${encodeURIComponent(id)}`));
            if (closed || token !== epoch) return; project = value; p.name.value = value.name;
        }
        render(); status.textContent = "";
    }));
    a.list.addEventListener("change", () => { selectedAttempt = a.list.value; selectedSavepoint = ""; if (selectedAttempt) a.name.value = attempt().name; render(); });
    s.list.addEventListener("change", () => { selectedSavepoint = s.list.value; if (selectedSavepoint) s.name.value = savepoint().name; updateControls(); });
    target.addEventListener("change", updateControls);
    showArchived.addEventListener("change", render);
    panel.addEventListener("keydown", event => {
        event.stopPropagation();
        if (event.key === "Escape") { event.preventDefault(); closePanel(); }
    });
    panel.focus(); renderTargets(); render();
    if (pendingWrite) status.textContent = t.uncertain;
    else perform(refreshAll);
}

app.registerExtension({
    name: "H3Continuum.ProjectTakeManager",
    commands: [{ id: "H3Continuum.ProjectManager.Open", label: "Project / Take", function: openProjectManager }],
    menuCommands: [{ path: ["H3 Continuum"], commands: ["H3Continuum.ProjectManager.Open"] }],
    setup() {
        app.ui?.settings?.addSetting?.({
            id: ENABLED, name: text().enable, category: ["H3Continuum", "Project Manager", "Enabled"], type: "boolean", defaultValue: false,
            onChange(value) { if (!value) opened?.close(); },
        });
        app.ui?.settings?.addSetting?.({
            id: "H3Continuum.ProjectManager.Open", name: "Project / Take", category: ["H3Continuum", "Project Manager", "Open"], defaultValue: null,
            type() {
                const row = el("tr"), cell = el("td", null, row); cell.colSpan = 2;
                button(text().open, cell, openProjectManager); return row;
            },
        });
    },
});
