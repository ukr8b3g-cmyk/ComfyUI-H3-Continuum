// Issue #20 candidate gate: real extension + modeled frontend lifecycle.
// This is not a browser, GPU test, or proof of the reporter's full reset bug.
const assert = require('node:assert/strict');
const { environment, project } = require('./frontend_review_queue.cjs');
const results = [];
const transient = w => !!w.__h3ContinuumProductionTransient;
const persistent = n => n.widgets.filter(w => !transient(w));
const values = n => persistent(n).map(w => structuredClone(w.value));
const canonical = x => JSON.parse(JSON.stringify(x));
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function test(name, body) {
  const e = environment();
  try { await body(e); results.push({ name, pass: true }); }
  catch (error) { results.push({ name, pass: false, error: error.stack }); }
  finally { e.close(); }
}
function observeArray(n) {
  let writes = 0;
  n.widgets = new Proxy(n.widgets, {
    set(target, key, value) { writes++; return Reflect.set(target, key, value); },
    deleteProperty(target, key) { writes++; return Reflect.deleteProperty(target, key); }
  });
  return () => writes;
}
(async () => {
  await test('serialize is a read: no live widget-array writes', async e => {
    const n = e.makeNode(); await e.load(n, null);
    e.w(n, 'Width').callback(640); e.w(n, 'Height').callback(864);
    const expected = values(n), before = [...n.widgets], writes = observeArray(n), widgets = n.widgets;
    for (let i = 0; i < 10; i++) assert.deepEqual(canonical(n.serialize().widgets_values), expected);
    assert.equal(n.widgets, widgets); assert.deepEqual([...n.widgets], before);
    assert.equal(writes(), 0, 'saving spliced the live widget array');
  });
  for (const format of ['indexed', 'compact']) {
    await test(`${format} serializer round trip preserves values and named metadata`, async e => {
      const n = e.makeNode(312, 'fixture', node => {
        node.serialize = function () {
          const selected = this.widgets.filter(w => w.serialize !== false);
          const data = format === 'compact' ? selected.map(w => w.value) : [];
          if (format === 'indexed') this.widgets.forEach((w, i) => { if (w.serialize !== false) data[i] = w.value; });
          return { widgets_values: data, widgets_values_named: Object.fromEntries(selected.map(w => [w.name, w.value])), properties: { keep: 'original' } };
        };
      });
      await e.load(n, null);
      e.w(n, 'Prompt Format').callback('List'); e.w(n, 'Chunks').callback(6);
      e.w(n, 'Width').callback(640); e.w(n, 'Height').callback(864);
      const expected = values(n), apiBefore = canonical(await e.inputs(n));
      for (const status of ['settings', 'review', 'complete']) {
        if (status === 'review') { e.w(n, 'generation_mode').value = 'Review Each Chunk'; await e.load(n, project(1, 6)); }
        if (status === 'complete') await e.load(n, project(6, 6, 'complete'));
        const current = values(n), writes = observeArray(n), saved = canonical(n.serialize());
        assert.deepEqual(saved.widgets_values, current); assert.equal(writes(), 0);
        assert.deepEqual(Object.keys(saved.widgets_values_named), persistent(n).map(w => w.name));
        assert.deepEqual(saved.properties, { keep: 'original' });
        const restored = e.makeNode(313); restored.configure(saved); e.f.configureNode(restored);
        assert.equal(e.w(restored, 'prompt_mode').value, 'List');
        assert.equal(e.w(restored, 'chunks').value, 6);
        assert.equal(e.w(restored, 'width').value, 640); assert.equal(e.w(restored, 'height').value, 864);
      }
      assert.equal(expected.length, 30); assert.equal(apiBefore.width, 640);
    });
  }
  await test('serialize exception leaves widgets untouched', async e => {
    const n = e.makeNode(312, 'fixture', node => { node.serialize = () => { throw Error('serializer failure'); }; });
    await e.load(n, null);
    const before = [...n.widgets], writes = observeArray(n);
    assert.throws(() => n.serialize(), /serializer failure/);
    assert.deepEqual([...n.widgets], before); assert.equal(writes(), 0);
  });
  await test('repeated facade and review ordering is idempotent', async e => {
    const n = e.makeNode(); await e.load(n, null);
    const names = n.__h3ContinuumFacadeOrder;
    e.f.moveFacadeWidgetsToFront(n, names);
    let writes = observeArray(n);
    for (let i = 0; i < 5; i++) e.f.moveFacadeWidgetsToFront(n, names);
    assert.equal(writes(), 0, 'unchanged facade order was rewritten');
    e.f.moveNamedWidgetsToFront(n, ['Use it and continue', 'Try this chunk again']);
    writes = observeArray(n);
    for (let i = 0; i < 5; i++) e.f.moveNamedWidgetsToFront(n, ['Use it and continue', 'Try this chunk again']);
    assert.equal(writes(), 0, 'unchanged review order was rewritten');
  });
  await test('old deferred setup cannot touch detached nodes with reused IDs', async e => {
    const n = e.makeNode(); await e.load(n, null);
    e.f.configureNodeAfterSetup(n);
    const graph = n.graph;
    graph._nodes = graph._nodes.filter(x => x !== n);
    const other = e.makeNode(312, 'other'); await e.load(other, null);
    e.w(other, 'Width').callback(480); e.w(other, 'Height').callback(864);
    const before = values(other); let oldRefreshes = 0;
    n.setDirtyCanvas = () => { oldRefreshes++; };
    await sleep(150);
    assert.equal(oldRefreshes, 0, 'detached node was configured after tab replacement');
    assert.deepEqual(values(other), before);
  });
  await test('First Image resolution uses its owner graph, not a different active tab', async e => {
    const n = e.makeNode(); await e.load(n, null);
    const owner = n.graph;
    const image = { id: 90, mode: 0, imgs: [{ naturalWidth: 1200, naturalHeight: 600 }] };
    owner._nodes.push(image); owner.links[42] = { origin_id: 90 };
    n.inputs.push({ name: 'first_frame', link: 42 }); e.w(n, 'size_source').value = 'First Image';
    const wrongImage = { id: 90, mode: 0, imgs: [{ naturalWidth: 600, naturalHeight: 1200 }] };
    e.app.graph = { _nodes: [wrongImage], links: { 42: { origin_id: 90 } }, getNodeById() { return wrongImage; } };
    n.__h3ContinuumResolutionUxRefresh();
    assert(e.w(n, 'width').value > e.w(n, 'height').value, 'dimensions came from the other tab');
    assert.equal(wrongImage.imgs[0].naturalWidth, 600);
  });
  await test('live deferred setup still runs and new nodes remain usable', async e => {
    const n = e.makeNode(); await e.load(n, null);
    let refreshes = 0; n.setDirtyCanvas = () => { refreshes++; };
    e.f.configureNodeAfterSetup(n); const immediate = refreshes;
    await sleep(150); assert(refreshes > immediate);
    e.w(n, 'Chunks').callback(4); const input = await e.inputs(n);
    assert.equal(input.chunks, 4); assert.equal(input.width, 544);
  });
  await test('repeated save/restore leaves sibling Model VAE and LoRA selections unchanged', async e => {
    const n = e.makeNode(); await e.load(n, null);
    const loaders = ['model', 'video_vae', 'audio_vae', 'lora'].map((name, i) => ({ id: 900 + i, widgets: [{ name, value: `${name}-selected.safetensors` }] }));
    n.graph._nodes.push(...loaders); const expected = canonical(loaders);
    e.w(n, 'Prompt Format').callback('List'); e.w(n, 'Width').callback(480); e.w(n, 'Height').callback(864);
    for (let i = 0; i < 10; i++) {
      const saved = canonical(n.serialize()); n.configure(saved); e.f.configureNode(n);
      assert.deepEqual(canonical(loaders), expected);
      assert.equal(e.w(n, 'prompt_mode').value, 'List'); assert.equal(e.w(n, 'height').value, 864);
    }
    const input = await e.inputs(n); assert.equal(input.width, 480); assert.equal(input.height, 864);
    assert(!Object.hasOwn(input, 'Render History / Takes'));
  });
  console.log(JSON.stringify(results, null, 2));
  if (results.some(item => !item.pass)) process.exitCode = 1;
})();
