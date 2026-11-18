const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = process.env.H3_TEST_ROOT || path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'web/reference_images_v39.js'), 'utf8')
    .replace('export function configureV39ReferenceImages', 'function configureV39ReferenceImages')
    .replace('export function refreshV39ReferenceImagesForSampler', 'function refreshV39ReferenceImagesForSampler')
    .replace('export function connectedV39LegacyReferenceInputs', 'function connectedV39LegacyReferenceInputs')
    .replace('export function pruneV39LegacyReferenceInputs', 'function pruneV39LegacyReferenceInputs');
function dom(tag) {
    return {
        tag, children: [], style: {}, textContent: '',
        append(...items) { this.children.push(...items); },
        replaceChildren(...items) { this.children = items; },
        addEventListener() {}, setAttribute(name, value) { this[name] = value; },
    };
}
const graph = { links: {}, nodes: new Map(), getNodeById(id) { return this.nodes.get(id); } };
const sandbox = { document: { createElement: dom }, app: { graph }, Set, Array, Number, JSON };
vm.runInNewContext(source + '\nglobalThis.v39={configureV39ReferenceImages,refreshV39ReferenceImagesForSampler,connectedV39LegacyReferenceInputs,pruneV39LegacyReferenceInputs};', sandbox);
const {
    configureV39ReferenceImages, refreshV39ReferenceImagesForSampler,
    connectedV39LegacyReferenceInputs, pruneV39LegacyReferenceInputs,
} = sandbox.v39;
const nativeCalls = [];
let resizeCalls = 0;
const selectors = Array.from({ length: 9 }, (_, i) => ({
    name: `reference_r${i + 1}_chunks`, value: 'off', type: 'text', options: {},
    callback(...args) { nativeCalls.push({ receiver: this, args }); return 'native-result'; },
}));
const mode = { name: 'reference_use', value: 'All chunks', type: 'combo', options: {} };
const helper = {
    id: 1, graph, comfyClass: 'H3ContinuumReferenceImagesV39',
    size: [440, 500],
    widgets: [mode, ...selectors],
    inputs: Array.from({ length: 9 }, (_, i) => ({ name: `reference_image_${i + 1}`, link: i === 0 || i === 3 || i === 8 ? i + 100 : null })),
    outputs: [{ name: 'reference_images', links: [10] }],
    addDOMWidget(_name, _type, host, options) { this.host = host; this.panel = host.children[0]; this.domOptions = options; this.display = { options: {} }; return this.display; },
    computeSize() { return [this.size[0], 310 + this.display.computeSize(this.size[0])[1]]; },
    setSize(size) { resizeCalls++; this.size = size; },
    setDirtyCanvas() {},
};
const chunks = { name: 'chunks', value: 6 };
const sampler = {
    id: 2, graph, comfyClass: 'H3ContinuumSamplerV39',
    widgets: [chunks], inputs: [{ name: 'reference_images', link: 10 }],
    refreshes: 0,
    __h3ContinuumIntuitiveUxRefresh() { this.refreshes++; },
    __h3ContinuumReferencePlan: 'verified', setDirtyCanvas() {},
};
graph.nodes.set(1, helper); graph.nodes.set(2, sampler);
graph.links[10] = { origin_id: 1, target_id: 2 };
configureV39ReferenceImages(helper);
assert.equal(helper.domOptions.serialize, false);
assert.equal(selectors[0].options.serialize, undefined);
assert.equal(selectors[0].type, 'hidden');
assert.equal(selectors[0].hidden, true);
assert.equal(selectors[0].computeSize()[1], 0);
assert.equal(typeof selectors[0].draw, 'function');
assert.match(helper.host.style.cssText, /padding-top:8px/);
assert.match(helper.panel.children[0].textContent, /all chunks/i);
mode.value = 'Per chunk'; mode.callback('Per chunk');
assert.equal(helper.display.computeSize(440)[1], 193);
assert.equal(helper.panel.style.height, '185px');
assert.equal(helper.size[1], 503, 'three-row assignment panel must size the node');
const visit = (item, predicate) => {
    if (predicate(item)) return item;
    for (const child of item.children || []) {
        const found = visit(child, predicate);
        if (found) return found;
    }
    return null;
};
function click(slot, chunk) {
    const box = visit(helper.panel, (item) => item.tag === 'input'
        && item['aria-label'] === `Image ${slot}, Chunk ${chunk}`);
    assert(box, `missing Image ${slot} / Chunk ${chunk}`);
    const before = { notifications: sampler.refreshes, native: nativeCalls.length, sizes: resizeCalls, width: helper.size[0] };
    box.checked = !box.checked; box.onchange();
    assert.equal(sampler.refreshes, before.notifications + 1, 'one synchronous Sampler notification per checkbox');
    assert.equal(nativeCalls.length, before.native + 1, 'preserve the native callback exactly once');
    assert.equal(nativeCalls.at(-1).receiver, selectors[slot - 1]);
    assert.equal(nativeCalls.at(-1).args[0], selectors[slot - 1].value);
    assert.equal(resizeCalls, before.sizes, 'selection changes must not resize an unchanged layout');
    assert.equal(helper.size[0], before.width, 'keep the manually chosen width');
}
for (const chunk of [1, 3, 6]) click(1, chunk);
assert.equal(selectors[0].value, '1,3,6');
assert.equal(sampler.__h3ContinuumReferencePlan, null);
chunks.value = 3; refreshV39ReferenceImagesForSampler(sampler);
assert.match(helper.panel.children.find((item) => item.textContent.startsWith('Image 1 →')).textContent, /saved beyond range: 6/);
assert.equal(selectors[0].value, '1,3,6');
function action(label) {
    const row = visit(helper.panel, (item) => item.tag === 'tr'
        && item.children[0]?.textContent === 'Image 1 · @R1');
    const button = visit(row, (item) => item.tag === 'button' && item.textContent === label);
    assert(button && !button.disabled);
    const before = { notifications: sampler.refreshes, native: nativeCalls.length, sizes: resizeCalls };
    button.onclick();
    assert.equal(sampler.refreshes, before.notifications + 1, 'one notification per All / Off');
    assert.equal(nativeCalls.length, before.native + 1);
    assert.equal(resizeCalls, before.sizes);
}
action('All');
assert.equal(selectors[0].value, '1,2,3,6', 'All preserves saved chunks beyond the current range');
action('Off');
assert.equal(selectors[0].value, '6', 'Off preserves saved chunks beyond the current range');
selectors[0].value = '1,3,6';
const nativeBefore = nativeCalls.length;
const refreshBefore = sampler.refreshes;
assert.equal(selectors[0].callback('1,3,6', 'native-edit'), 'native-result');
assert.equal(nativeCalls.length, nativeBefore + 1);
assert.equal(nativeCalls.at(-1).args[1], 'native-edit');
assert.equal(sampler.refreshes, refreshBefore + 1);
chunks.value = 6; refreshV39ReferenceImagesForSampler(sampler);
assert.equal(selectors[0].value, '1,3,6');
mode.value = 'All chunks'; mode.callback('All chunks');
assert.equal(helper.display.computeSize(440)[1], 62);
assert.equal(helper.size[1], 372, 'switching to All chunks must remove unused panel space');
mode.value = 'Per chunk'; mode.callback('Per chunk');
assert.equal(selectors[0].value, '1,3,6');
helper.inputs.forEach((input, index) => { input.link = index + 100; });
chunks.value = 16;
helper.__h3ReferenceImagesRefresh();
assert.equal(helper.display.computeSize(440)[1], 368);
assert.equal(helper.panel.style.height, '360px');
const stableSizes = resizeCalls;
const wrappedCallback = selectors[0].callback;
for (let i = 0; i < 100; i++) configureV39ReferenceImages(helper);
assert.equal(selectors[0].callback, wrappedCallback, 'helper reconfiguration must not stack callbacks');
assert.equal(resizeCalls, stableSizes);
helper.size[0] = 620;
click(1, 2);
assert.equal(helper.size[0], 620);
// Check another connected Sampler independently of the manually chosen width.
helper.size[0] = 440;
const secondSampler = { ...sampler, id: 3, refreshes: 0, widgets: [{ name: 'chunks', value: 16 }] };
graph.nodes.set(3, secondSampler);
graph.links[11] = { origin_id: 1, target_id: 3 };
helper.outputs[0].links.push(11);
click(1, 3);
assert.equal(secondSampler.refreshes, 1, 'each connected Sampler receives the selection');
assert.equal(secondSampler.__h3ContinuumReferencePlan, null);
const separateSampler = { ...sampler, id: 5, refreshes: 0, widgets: [{ name: 'chunks', value: 16 }],
    __h3ContinuumReferencePlan: 'verified' };
const separateHelper = {
    id: 4, graph, comfyClass: helper.comfyClass, size: [440, 500],
    widgets: [{ name: 'reference_use', value: 'Per chunk', options: {} },
        ...Array.from({ length: 9 }, (_, i) => ({ name: `reference_r${i + 1}_chunks`, value: 'off', options: {} }))],
    inputs: helper.inputs.map((input) => ({ ...input })),
    outputs: [{ name: 'reference_images', links: [12] }],
    addDOMWidget: helper.addDOMWidget, computeSize: helper.computeSize,
    setSize: helper.setSize, setDirtyCanvas() {},
};
graph.nodes.set(4, separateHelper); graph.nodes.set(5, separateSampler);
graph.links[12] = { origin_id: 4, target_id: 5 };
configureV39ReferenceImages(separateHelper);
const firstBefore = sampler.refreshes;
click(1, 4);
const separateBox = visit(separateHelper.panel, (item) => item.tag === 'input'
    && item['aria-label'] === 'Image 1, Chunk 5');
separateBox.checked = true; separateBox.onchange();
assert.equal(sampler.refreshes, firstBefore + 1);
assert.equal(separateSampler.refreshes, 1, 'independent helpers must not cancel each other');
assert.equal(separateHelper.widgets[1].value, '5');
assert.equal(separateSampler.__h3ContinuumReferencePlan, null);
delete graph.links[12]; separateHelper.outputs[0].links = [];
separateHelper.onConnectionsChange();
const detachedRefreshes = separateSampler.refreshes;
separateHelper.widgets[1].value = '6'; separateHelper.widgets[1].callback('6');
assert.equal(separateSampler.refreshes, detachedRefreshes, 'disconnected Samplers are not notified');
const oldSampler = {
    comfyClass: 'H3ContinuumSamplerV39',
    __h3ContinuumReferencePlan: 'old plan',
    inputs: [
        { name: 'reference_image_1', link: null },
        { name: 'reference_image_2', link: 22 },
        { name: 'image_references', link: null },
        { name: 'reference_images', link: 10 },
    ],
    removeInput(index) { this.inputs.splice(index, 1); },
    setDirtyCanvas() { this.dirty = true; },
};
assert.equal(pruneV39LegacyReferenceInputs(oldSampler), 2);
assert.deepEqual(oldSampler.inputs.map((input) => input.name), ['reference_image_2', 'reference_images']);
assert.equal(oldSampler.__h3ContinuumReferencePlan, null);
assert.equal(oldSampler.dirty, true);
assert.equal(connectedV39LegacyReferenceInputs(oldSampler).join(','), 'reference_image_2');
assert.equal(pruneV39LegacyReferenceInputs(oldSampler), 0);
oldSampler.inputs[0].link = null;
assert.equal(pruneV39LegacyReferenceInputs(oldSampler), 1);
assert.deepEqual(oldSampler.inputs.map((input) => input.name), ['reference_images']);
assert.equal(pruneV39LegacyReferenceInputs({ ...oldSampler, comfyClass: 'H3ContinuumSamplerV38' }), 0);
// External INT values are not frontend widget values. Exercise the production
// helper in fresh graphs without resolving or guessing any upstream value.
function assignmentFixture({ value = 3, external = false, link = 90, saved = 'off', missing = false, other = null } = {}) {
    const graph = { links: {}, nodes: new Map(), getNodeById(id) { return this.nodes.get(id); } };
    const calls = { native: 0, notify: 0, size: 0 };
    const controls = Array.from({ length: 9 }, (_, i) => ({ name: `reference_r${i + 1}_chunks`,
        value: i === 0 ? saved : 'off', options: {}, callback() { calls.native++; } }));
    const helper = { id: 1, graph, comfyClass: 'H3ContinuumReferenceImagesV39', size: [440, 500],
        widgets: [{ name: 'reference_use', value: 'Per chunk' }, ...controls],
        inputs: [{ name: 'reference_image_1', link: 100 }], outputs: [{ name: 'reference_images', links: [10] }],
        addDOMWidget(_name, _type, host) { this.panel = host.children[0]; this.display = { options: {} }; return this.display; },
        computeSize() { return [440, 310 + this.display.computeSize(440)[1]]; },
        setSize(value) { calls.size++; this.size = value; }, setDirtyCanvas() {},
    };
    const sampler = { id: 2, graph, comfyClass: 'H3ContinuumSamplerV39',
        widgets: missing ? [] : [{ name: 'chunks', value }],
        inputs: [{ name: 'reference_images', link: 10 }, { name: 'chunks', link: external ? link : null }],
        __h3ContinuumIntuitiveUxRefresh() { calls.notify++; }, setDirtyCanvas() {},
    };
    graph.nodes.set(1, helper); graph.nodes.set(2, sampler); graph.links[10] = { origin_id: 1, target_id: 2 };
    if (other !== null) {
        const second = { ...sampler, id: 3, widgets: [{ name: 'chunks', value: other }],
            inputs: [{ name: 'reference_images', link: 11 }, { name: 'chunks', link: null }] };
        graph.nodes.set(3, second); graph.links[11] = { origin_id: 1, target_id: 3 }; helper.outputs[0].links.push(11);
    }
    configureV39ReferenceImages(helper);
    return { graph, helper, sampler, calls, control: controls[0],
        text() { const values = []; const collect = (node) => { values.push(node.textContent || ''); (node.children || []).forEach(collect); }; collect(helper.panel); return values.join('\n'); },
        checkbox(n) { return visit(helper.panel, (item) => item['aria-label'] === `Image 1, Chunk ${n}`); },
        action(label) { const button = visit(helper.panel, (item) => item.tag === 'button' && item.textContent === label); assert(button && !button.disabled, label); button.onclick(); },
        refresh() { refreshV39ReferenceImagesForSampler(sampler); },
    };
}
const externalCases = [];
function externalCase(name, run) {
    try { run(); externalCases.push({ name, pass: true }); }
    catch (error) { externalCases.push({ name, pass: false, error: error.message }); }
}
function unknown(f, reason) {
    assert.match(f.text(), /range 1–16/);
    assert.match(f.text(), reason);
    assert(f.checkbox(3));
    assert(!f.text().includes('saved beyond range'));
}
externalCase('J01 direct three keeps native range', () => {
    const f = assignmentFixture(); assert.match(f.text(), /3 chunks/); assert(f.checkbox(3)); assert(!f.checkbox(4));
    f.action('All'); assert.equal(f.control.value, '1,2,3'); f.action('Off'); assert.equal(f.control.value, 'off');
});
externalCase('J02 external three and widget two allow C3', () => unknown(assignmentFixture({ value: 2, external: true }), /connected node/));
externalCase('J03 external with matching widget remains unresolved', () => unknown(assignmentFixture({ external: true }), /connected node/));
externalCase('J04 link zero is external', () => unknown(assignmentFixture({ external: true, link: 0 }), /connected node/));
externalCase('J05 unrestored link stays external', () => unknown(assignmentFixture({ external: true, link: 99999 }), /connected node/));
externalCase('J06 disconnected or absent socket uses direct value', () => {
    const f = assignmentFixture(); f.sampler.inputs.pop(); f.refresh(); assert.match(f.text(), /3 chunks/);
});
externalCase('J07 unavailable or invalid widget preserves selection', () => {
    for (const options of [{ missing: true }, { value: 0 }, { value: 17 }, { value: 2.5 }, { value: 'bad' }]) {
        const f = assignmentFixture({ ...options, saved: '1,2,3' }); unknown(f, /not available/); assert.equal(f.control.value, '1,2,3');
    }
});
externalCase('J08 multiple direct three targets agree', () => assert.match(assignmentFixture({ other: 3 }).text(), /3 chunks/));
externalCase('J09 multiple different direct counts stay unresolved', () => unknown(assignmentFixture({ other: 2 }), /different chunk counts/));
externalCase('J10 any externally connected target makes range unresolved', () => unknown(assignmentFixture({ external: true, other: 3 }), /connected node/));
externalCase('J11 unknown reason refreshes even when range is unchanged', () => {
    const f = assignmentFixture({ external: true }); unknown(f, /connected node/);
    f.helper.outputs[0].links = []; f.helper.onConnectionsChange(); unknown(f, /Connect this helper to a Sampler/);
    assert(!f.text().includes('connected node'));
});
externalCase('J12 upstream value changes do not rewrite or rebuild', () => {
    const f = assignmentFixture({ external: true, saved: '1,2' }); const first = f.helper.panel.children[0];
    const counts = { ...f.calls }; f.graph.nodes.set(90, { value: 4 }); f.refresh();
    assert.equal(f.helper.panel.children[0], first); assert.equal(f.control.value, '1,2'); assert.deepEqual(f.calls, counts);
});
externalCase('J13 saved C3 remains visible and is not called outside range', () => {
    const f = assignmentFixture({ value: 2, external: true, saved: '1,2,3' }); f.refresh();
    assert.equal(f.control.value, '1,2,3'); assert(f.checkbox(3).checked); assert.match(f.text(), /Saved assignments: 1, 2, 3/);
});
externalCase('J14 old one-two is never automatically expanded', () => {
    const f = assignmentFixture({ value: 2, external: true, saved: '1,2' }); configureV39ReferenceImages(f.helper); f.refresh();
    assert.equal(f.control.value, '1,2'); assert(!f.checkbox(3).checked);
});
externalCase('J15 unknown All operates over all pages', () => {
    const f = assignmentFixture({ external: true }); f.action('▶'); f.action('▶'); f.action('All 1–16');
    assert.equal(f.control.value, Array.from({ length: 16 }, (_, i) => i + 1).join(','));
});
externalCase('J16 unknown Off clears future saved assignments', () => {
    const f = assignmentFixture({ external: true, saved: '1,2,3,16' }); f.action('Off 1–16'); assert.equal(f.control.value, 'off');
});
externalCase('J17 direct All and Off preserve saved future six', () => {
    const f = assignmentFixture({ saved: '6' }); f.action('All'); assert.equal(f.control.value, '1,2,3,6'); f.action('Off'); assert.equal(f.control.value, '6');
});
externalCase('J18 C3 updates native value and notifies once', () => {
    const f = assignmentFixture({ value: 2, external: true }); const counts = { ...f.calls }; const box = f.checkbox(3);
    assert(box); box.checked = true; box.onchange(); assert.equal(f.control.value, '3');
    assert.equal(f.calls.native, counts.native + 1); assert.equal(f.calls.notify, counts.notify + 1); assert.equal(f.calls.size, counts.size);
});
externalCase('J19 independent helpers and multiple targets stay independent', () => {
    const f = assignmentFixture({ external: true, other: 3 }), g = assignmentFixture({ external: true });
    f.action('All 1–16'); assert.equal(f.calls.notify, 2); assert.equal(g.control.value, 'off'); assert.equal(g.calls.notify, 0);
});
externalCase('J20 repeated configure keeps callbacks layout and width', () => {
    const f = assignmentFixture({ external: true }); const callback = f.control.callback, sizes = f.calls.size;
    for (let i = 0; i < 100; i++) configureV39ReferenceImages(f.helper);
    assert.equal(f.control.callback, callback); assert.equal(f.calls.size, sizes); assert.equal(f.helper.size[0], 440);
});
externalCase('J21 malformed saved selector remains disabled and unchanged', () => {
    const f = assignmentFixture({ external: true, saved: 'invalid' }); assert.equal(f.control.value, 'invalid');
    assert(f.checkbox(3).disabled); assert(visit(f.helper.panel, (item) => item.textContent === 'All 1–16').disabled);
});
for (const [saved, chunk] of [['1,1', 1], ['1-3,3', 3], ['2-4,1-3', 2]]) {
    externalCase(`overlapping saved selector ${saved} requires an explicit edit`, () => {
        const f = assignmentFixture({ saved });
        f.helper.widgets[2].value = '8';
        configureV39ReferenceImages(f.helper); f.refresh();
        assert(f.text().includes(`Image 1: invalid saved selection. Chunk ${chunk} appears more than once.`));
        assert(!f.text().includes('No references assigned'));
        assert(f.checkbox(1).disabled); assert(!f.checkbox(1).checked);
        assert.equal(f.control.value, saved); assert.equal(f.calls.native, 0);
        f.action('Reset to Off');
        assert.equal(f.control.value, 'off'); assert.equal(f.helper.widgets[2].value, '8');
        assert.equal(f.calls.native, 1); assert(!f.checkbox(1).disabled);
        const box = f.checkbox(2); box.checked = true; box.onchange();
        assert.equal(f.control.value, '2');
    });
}
externalCase('adjacent non-overlapping ranges stay valid without rewriting their saved text', () => {
    const f = assignmentFixture({ saved: '1-2,3' });
    assert.match(f.text(), /Chunks 1, 2, 3/); assert(!f.checkbox(3).disabled);
    assert.equal(f.control.value, '1-2,3'); assert.equal(f.calls.native, 0);
});
console.log(JSON.stringify(externalCases));
assert.equal(externalCases.filter((item) => !item.pass).length, 0, 'external Chunk assignment contracts failed');
console.log('V3.9 Reference Images UI contract PASS');
