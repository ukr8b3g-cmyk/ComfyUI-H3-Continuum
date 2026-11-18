// Exercise the complete production scripts through the existing Queue fixture.
// DOM, graph and server responses are fixtures; no ComfyUI service or GPU is used.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ROOT = process.env.H3_TEST_ROOT || path.resolve(__dirname, '..');
const harness = fs.readFileSync(path.join(ROOT, 'tests/frontend_review_queue.cjs'), 'utf8');
const marker = harness.indexOf('\n(async()=>{');
assert(marker > 0);
function dom(tag) {
    return { tag, children: [], style: {}, textContent: '',
        append(...items) { this.children.push(...items); },
        replaceChildren(...items) { this.children = items; },
        addEventListener() {}, setAttribute(name, value) { this[name] = value; } };
}
const scope = { require, process, console, __dirname: path.join(ROOT, 'tests'),
    setTimeout, clearTimeout, setImmediate, structuredClone,
    document: { createElement: dom } };
const prefix = harness.slice(0, marker)
    .replace('globalThis:null,', 'globalThis:null,document,')
    .replace('reviewSettingsChanged,synchronizeReviewQueue};',
        'reviewSettingsChanged,reviewSettingsSnapshot,synchronizeReviewQueue};');
vm.runInNewContext(prefix + '\nglobalThis.fixtures={environment,project};', scope);
const { environment, project } = scope.fixtures;
const results = [];
async function test(name, body) {
    const e = environment();
    try { await body(e); results.push({ name, pass: true }); }
    catch (error) { results.push({ name, pass: false, error: error.stack }); }
    finally { e.close(); }
}
function upstream(e, n, count = 20) {
    let previous = n;
    for (let i = 0; i < count; i++) {
        const source = { id: 900 + i, comfyClass: 'FixtureSource', mode: 0,
            widgets: [{ name: 'text', value: `source-${i}`, options: {} }], inputs: [] };
        e.app.graph._nodes.push(source);
        previous.inputs.push({ name: 'source', link: 70 + i });
        e.app.graph.links[70 + i] = { origin_id: source.id, origin_slot: 0 };
        previous = source;
    }
    return previous;
}
function helper(e, n) {
    const h = e.makeNode(391, 'helper', 'H3ContinuumReferenceImagesV39', false);
    h.widgets = [{ name: 'reference_use', value: 'Per chunk', options: {} },
        ...Array.from({ length: 9 }, (_, i) => ({ name: `reference_r${i + 1}_chunks`, value: 'off', options: {} }))];
    h.inputs = [{ name: 'reference_image_1', link: 600 }];
    h.outputs = [{ name: 'reference_images', links: [900] }];
    h.addDOMWidget = function(_name, _type, host, options) {
        this.panel = host.children[0]; this.display = { options }; return this.display;
    };
    h.computeSize = function() { return [this.size[0], 310 + this.display.computeSize(this.size[0])[1]]; };
    h.setSize = function(size) { this.size = size; };
    e.app.graph.links[900] = { origin_id: h.id, target_id: n.id, origin_slot: 0 };
    n.inputs.push({ name: 'reference_images', link: 900 });
    e.f.configureNode(h);
    return h;
}
async function queueWithHelper(e, n, h) {
    return e.api.queuePrompt(0, { workflow: n.serialize(), output: {
        [n.id]: { class_type: n.comfyClass, inputs: { ...(await e.inputs(n)), reference_images: [String(h.id), 0] } },
        [h.id]: { class_type: h.comfyClass, inputs: await e.inputs(h) },
    } });
}
async function publishPlan(e, n, promptId, text) {
    const output = { h3_reference_plan: [text] };
    const result = n.onExecuted?.(output);
    await e.emit('executed', { prompt_id: promptId, node: String(n.id), output });
    return result;
}
(async () => {
    await test('no Review baseline: draw does not traverse upstream settings', async e => {
        const n = e.makeNode(); upstream(e, n);
        let lookups = 0, refreshes = 0;
        const get = e.app.graph.getNodeById;
        e.app.graph.getNodeById = function(...args) { lookups++; return get.apply(this, args); };
        n.__h3ContinuumIntuitiveUxRefresh = n.__h3ContinuumProductionUxRefresh = () => { refreshes++; };
        for (const baseline of [undefined, null]) {
            n.__h3ContinuumReviewedSettings = baseline;
            n.__h3ContinuumReviewDrawChanged = false;
            for (let i = 0; i < 600; i++) n.onDrawForeground();
            assert.equal(e.f.reviewSettingsChanged(n), false);
        }
        assert.equal(lookups, 0); assert.equal(refreshes, 0);
        n.__h3ContinuumReviewedSettings = '';
        assert.equal(e.f.reviewSettingsChanged(n), true, 'an existing empty baseline still requires comparison');
        assert.equal(lookups, 20);
    });
    await test('Review baseline: every draw still detects upstream edits', async e => {
        const n = e.makeNode(), last = upstream(e, n);
        n.__h3ContinuumReviewedSettings = e.f.reviewSettingsSnapshot(n);
        n.__h3ContinuumReviewDrawChanged = false;
        let lookups = 0, refreshes = 0;
        const get = e.app.graph.getNodeById;
        e.app.graph.getNodeById = function(...args) { lookups++; return get.apply(this, args); };
        n.__h3ContinuumIntuitiveUxRefresh = n.__h3ContinuumProductionUxRefresh = () => { refreshes++; };
        for (let i = 0; i < 600; i++) n.onDrawForeground();
        assert.equal(lookups, 12000); assert.equal(refreshes, 0);
        last.widgets[0].value = 'edited';
        n.onDrawForeground();
        assert.equal(n.__h3ContinuumReviewDrawChanged, true);
        assert.equal(refreshes, 2);
    });
    for (const nodeClass of ['H3ContinuumSamplerV38', 'H3ContinuumSamplerV39']) {
        for (const change of ['widget', 'link']) {
            await test(`${nodeClass}: ${change} edit keeps immediate Take and draw guards`, async e => {
                const n = e.makeNode(312, 'fixture', nodeClass), source = upstream(e, n, 1);
                e.w(n, 'generation_mode').value = 'Review Each Chunk';
                await e.load(n, project(1));
                delete n.__h3ContinuumModeSetup;
                n.__h3ContinuumReviewedSettings = e.f.reviewSettingsSnapshot(n);
                n.__h3ContinuumProductionUxRefresh(); n.onDrawForeground();
                assert(e.visible(n, 'Use it and continue'));
                if (change === 'widget') source.widgets[0].value = 'edited';
                else e.app.graph.links[70].origin_slot = 1;
                assert(e.visible(n, 'Use it and continue'), 'no draw has occurred yet');
                e.f.selectTakeAction(n, 'Use This Take');
                assert.equal(e.w(n, 'take_action').value, 'Automatic');
                assert.equal(e.w(n, 'take_revision_id').value, '');
                n.onDrawForeground();
                assert(!e.visible(n, 'Use it and continue'));
                assert.match(e.w(n, 'Review Ready').headline, /Settings changed/);
                assert.equal(e.submissions.length, 0);
            });
        }
    }
    for (const passes of [1, 2, 100]) {
        await test(`Reference Inspector stays current after ${passes} configure passes`, async e => {
            const n = e.makeNode(312, 'fixture', 'H3ContinuumSamplerV39', false), h = helper(e, n);
            let executions = 0, connections = 0;
            n.onExecuted = () => { executions++; return 'executed'; };
            n.onConnectionsChange = () => { connections++; return 'connected'; };
            const saved = n.serialize();
            for (let i = 0; i < passes; i++) e.f.configureNode(n);
            assert.deepEqual(n.serialize(), saved, 'configure preserves persistent widget values');
            assert.equal(n.widgets.filter(w => w.name === 'Reference Plan Inspector').length, 1);
            const first = await queueWithHelper(e, n, h);
            assert.equal(await publishPlan(e, n, first.prompt_id, 'fixture verified plan'), 'executed');
            const plan = e.w(n, 'Reference Plan Inspector');
            assert.equal(plan.value, 'fixture verified plan');
            h.widgets[1].value = '1'; h.widgets[1].callback('1');
            assert.equal(n.__h3ContinuumReferencePlan, null);
            assert.notEqual(plan.value, 'fixture verified plan', 'an invalidated plan must not keep its verified display');
            const unverified = plan.value;
            const next = await queueWithHelper(e, n, h);
            await publishPlan(e, n, next.prompt_id, 'new verified plan');
            assert.equal(plan.value, 'new verified plan', 'the next execution publishes its new plan');
            assert.equal(executions, 2, 'configure must not multiply execution callbacks');
            let value = plan.value, writes = 0;
            Object.defineProperty(plan, 'value', { configurable: true,
                get() { return value; }, set(next) { writes++; value = next; } });
            n.__h3ContinuumIntuitiveUxRefresh();
            assert.equal(writes, 1, 'one UI refresh updates the Inspector once after any number of configure passes');
            assert.equal(plan.value, 'new verified plan', 'unchanged settings keep the verified plan');
            assert.equal(n.onConnectionsChange(), 'connected');
            assert.equal(connections, 1, 'configure must not multiply connection callbacks');
            assert.equal(plan.value, unverified, 'connection changes invalidate the displayed plan');
            assert.deepEqual(n.serialize(), saved, 'Inspector updates do not enter saved widget values');
            assert.equal(e.submissions.length, 2);
        });
    }
    await test('Reference Inspector rejects a late result after an assignment edit', async e => {
        const n = e.makeNode(312, 'fixture', 'H3ContinuumSamplerV39'), h = helper(e, n);
        const assign = value => { h.widgets[1].value = value; h.widgets[1].callback(value); };
        assign('1');
        const first = await queueWithHelper(e, n, h);
        assign('2');
        const plan = e.w(n, 'Reference Plan Inspector');
        await publishPlan(e, n, first.prompt_id, 'verified R1 for Chunk 1');
        await e.emit('execution_success', { prompt_id: first.prompt_id });
        assert.match(plan.value, /Configured only/);
        const next = await queueWithHelper(e, n, h);
        await publishPlan(e, n, next.prompt_id, 'verified R1 for Chunk 2');
        assert.equal(plan.value, 'verified R1 for Chunk 2');
        assert.deepEqual(Array.from(e.submissions, s => s.data.output[h.id].inputs.reference_r1_chunks), ['1', '2']);
    });
    await test('Reference Inspector isolates prompt order, sampler and graph identity', async e => {
        const n = e.makeNode(312, 'fixture', 'H3ContinuumSamplerV39');
        const other = e.makeNode(313, 'other', 'H3ContinuumSamplerV39');
        const a = await e.queue(n), b = await e.queue(n);
        await publishPlan(e, n, b.prompt_id, 'newest');
        await publishPlan(e, n, a.prompt_id, 'older');
        await publishPlan(e, n, 'someone-else', 'foreign');
        await publishPlan(e, other, b.prompt_id, 'wrong node');
        assert.equal(e.w(n, 'Reference Plan Inspector').value, 'newest');
        assert.match(e.w(other, 'Reference Plan Inspector').value, /Configured only/);
        e.w(n, 'run_name').value = 'another run'; n.__h3ContinuumV39ReferenceUxRefresh();
        await publishPlan(e, n, b.prompt_id, 'old run');
        assert.match(e.w(n, 'Reference Plan Inspector').value, /Configured only/);
        e.w(n, 'run_name').value = 'fixture';
        e.app.extension.beforeConfigureGraph();
        await publishPlan(e, n, b.prompt_id, 'old graph');
        assert.notEqual(e.w(n, 'Reference Plan Inspector').value, 'old graph');
    });
    await test('Reference Inspector handles execution before the Queue HTTP response', async e => {
        const n = e.makeNode(312, 'fixture', 'H3ContinuumSamplerV39');
        e.setQueueHook(async q => {
            await publishPlan(e, n, q.prompt_id, 'fast result');
            await publishPlan(e, n, 'unrelated', 'foreign');
            await e.emit('execution_success', { prompt_id: q.prompt_id });
            assert.match(e.w(n, 'Reference Plan Inspector').value, /Configured only/);
        });
        await e.queue(n);
        assert.equal(e.w(n, 'Reference Plan Inspector').value, 'fast result');
    });
    await test('Reference Inspector resolves a nested execution ID without changing its inputs', async e => {
        const n = e.makeNode(312, 'fixture', 'H3ContinuumSamplerV39');
        const root = { getNodeById: id => String(id) === '91' ? { subgraph: e.app.graph } : null };
        e.app.rootGraph = root;
        const item = { class_type: n.comfyClass, inputs: await e.inputs(n) };
        const { prompt_id } = await e.api.queuePrompt(0, { output: { '91:312': item } });
        const output = { h3_reference_plan: ['nested plan'] };
        n.onExecuted?.(output);
        await e.emit('executed', { prompt_id, node: '91:312', output });
        assert.equal(e.w(n, 'Reference Plan Inspector').value, 'nested plan');
        assert.deepEqual(e.submissions.at(-1).data.output['91:312'], structuredClone(item));
    });
    await test('removing one queued Sampler keeps only the other Sampler eligible', async e => {
        const n = e.makeNode(312, 'first', 'H3ContinuumSamplerV39');
        const other = e.makeNode(313, 'second', 'H3ContinuumSamplerV39');
        const { prompt_id } = await e.api.queuePrompt(0, { output: {
            [n.id]: { class_type: n.comfyClass, inputs: await e.inputs(n) },
            [other.id]: { class_type: other.comfyClass, inputs: await e.inputs(other) },
        } });
        other.onRemoved(); e.app.graph._nodes.splice(e.app.graph._nodes.indexOf(other), 1);
        const replacement = e.makeNode(313, 'second', 'H3ContinuumSamplerV39');
        await publishPlan(e, replacement, prompt_id, 'old instance');
        assert.match(e.w(replacement, 'Reference Plan Inspector').value, /Configured only/);
        await publishPlan(e, n, prompt_id, 'still attached');
        assert.equal(e.w(n, 'Reference Plan Inspector').value, 'still attached');
    });
    for (const nodeClass of ['H3ContinuumSamplerV38','H3ContinuumSamplerV39']) {
        await test(`${nodeClass} Review checks the effective seed input`, async e => {
            const n = e.makeNode(312, 'fixture', nodeClass);
            e.w(n, 'generation_mode').value = 'Review Each Chunk';
            e.w(n, 'control_after_generate').value = 'randomize';
            const submit = async (seed, extra = {}) => e.api.queuePrompt(0, { output: {
                ...extra, [n.id]: { class_type: n.comfyClass, inputs: { ...(await e.inputs(n)), base_seed: seed } }
            } });
            await assert.rejects(submit(777), /requires.*fixed/);
            await assert.rejects(submit(['901', 0]), /requires.*fixed/);
            assert.equal(e.submissions.length, 0);
            const source = { id: 901, comfyClass: 'PrimitiveInt', mode: 0, inputs: [],
                widgets: [{ name: 'value', value: 777, options: {} }] };
            e.app.graph._nodes.push(source);
            n.inputs.push({ name: 'base_seed', link: 95 });
            e.app.graph.links[95] = { origin_id: 901, origin_slot: 0 };
            const upstream = { '901': { class_type: 'PrimitiveInt', inputs: { value: 777 } } };
            const q = await submit(['901', 0], upstream);
            await e.emit('execution_success', { prompt_id: q.prompt_id });
            assert.equal(JSON.stringify(e.submissions[0].data.output[n.id].inputs.base_seed), '["901",0]');
            n.widgets = n.widgets.filter(w => w.name !== 'control_after_generate');
            await submit(['901', 0], upstream);
            await submit(777);
            assert.equal(e.submissions.length, 3);
            assert.equal(e.submissions[2].data.output[n.id].inputs.base_seed, 777);
            delete e.app.graph.links[95];
            await assert.rejects(submit(777), /requires.*fixed/);
            assert.equal(e.submissions.length, 3);
        });
    }
    console.log(JSON.stringify(results));
    if (results.some(item => !item.pass)) process.exitCode = 1;
})();
