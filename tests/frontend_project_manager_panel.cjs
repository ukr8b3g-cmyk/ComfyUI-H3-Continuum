// Actual optional panel code in a small DOM, with no running ComfyUI or GPU.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { webcrypto } = require('node:crypto');
const ROOT = process.env.H3_TEST_ROOT || path.resolve(__dirname, '..');
const results = [];
const settle = async () => { for (let i = 0; i < 6; i++) await new Promise(r => setImmediate(r)); };
const projectId = '11111111-1111-4111-8111-111111111111';
function record() {
    return { id: projectId, name: 'Basketball', revision: 3, archived: false,
        attempts: [{ id: 'a1', name: 'Trial A', run_name: 'fixture', project_id: '', storage_name: 'fixture', archived: false },
            { id: 'a2', name: 'Trial B', run_name: '', project_id: '22222222-2222-4222-8222-222222222222', storage_name: 'run_22222222222242228222222222222222', archived: false }],
        savepoints: [{ id: 's1', name: 'Keep beginning', attempt_id: 'a1', run_name: 'fixture', revision_id: 'revision1', group: { end: 1 }, archived: false }] };
}
function environment(locale = 'en', crypto = webcrypto) {
    const elements = [], requests = [], settings = new Map(), calls = [], alerts = [];
    let extension, enabled = false, state = record(), hook = null, fail = null;
    class Element extends EventTarget {
        constructor(tag) { super(); this.tag = tag; this.children = []; this.style = {}; this.attributes = {}; this.disabled = false; this.hidden = false; this.value = ''; this.textContent = ''; this.checked = false; }
        append(child) { this.children.push(child); child.parentElement = this; }
        replaceChildren() { for (const c of this.children) c.parentElement = null; this.children = []; }
        setAttribute(k, v) { this.attributes[k] = v; }
        get isConnected() { return this === document.body || !!this.parentElement?.isConnected; }
        remove() { if (!this.parentElement) return; this.parentElement.children = this.parentElement.children.filter(x => x !== this); this.parentElement = null; }
        closest() { let n = this; while (n) { if (n.tag === 'dialog' || n.attributes.role === 'dialog') return n; n = n.parentElement; } return null; }
        focus() {}
        click() { if (!this.disabled) this.dispatchEvent(new Event('click')); }
        change(value) { if (value !== undefined) this.value = value; this.dispatchEvent(new Event('change')); }
    }
    const document = { body: new Element('body'), createElement(tag) { const e = new Element(tag); elements.push(e); return e; } };
    const identity = { run_name: 'fixture', project_id: 'p0', revision_id: 'revision1', busy: false, edited: false };
    const node = { id: 123, title: 'H3 Continuum V3.9', widgets: [{name:'run_name',value:'fixture'}],
        __h3ContinuumManagerBridge: { describe: () => ({...identity}), async prepareRun(data) { assert(data.isCurrent());const {isCurrent,...payload}=data;calls.push(structuredClone(payload)); } } };
    const app = { graph: { _nodes: [node] }, ui: { settings: {
        getSettingValue(id, fallback) { return id === 'Comfy.Locale' ? locale : id.endsWith('.Enabled') ? enabled : fallback; },
        addSetting(value) { settings.set(value.id, value); },
    } }, registerExtension(value) { extension = value; } };
    const api = { queuePrompt() { throw new Error('Manager must not submit Queue'); }, async fetchApi(url, options) {
        const body = options.body ? JSON.parse(options.body) : undefined;
        requests.push({url, body, options});
        if (hook) return hook(url, body);
        if (fail) { if (fail === 'network') throw new Error('offline'); return new Response('', { status: fail }); }
        if (url.endsWith('/prepare')) return Response.json({run_name:'fixture', project_id:'', revision_id:'revision1', group:{end:1}, generation_reusable:true});
        if (body) {
            if (url.endsWith('/projects')) { state = {id:body.project_id,name:body.name,revision:1,attempts:[],savepoints:[]}; }
            else {
                if (body.revision !== state.revision) return Response.json({error:'conflict',code:'project_revision_conflict'}, {status:409});
                state = structuredClone(state); state.revision++;
                if (body.action === 'rename_project') state.name = body.name;
                if (body.action === 'new_attempt') { const item={id:'new-attempt',name:body.name,run_name:'',project_id:'33333333-3333-4333-8333-333333333333',storage_name:'run_33333333333343338333333333333333'}; state.attempts.push(item); state.last_result={attempt_id:item.id}; }
                if (body.action === 'savepoint') { const item={id:'new-point',name:body.name,attempt_id:body.attempt_id,revision_id:body.revision_id,group:{end:1}}; state.savepoints.push(item); state.last_result={savepoint_id:item.id}; }
            }
            return Response.json(state);
        }
        return Response.json(url.endsWith('/projects') ? {projects:[state],errors:[]} : state);
    } };
    const sandbox = {app,api,document,navigator:{language:locale},crypto,alert:m=>alerts.push(m),console};
    const source = fs.readFileSync(path.join(ROOT, 'web/project_manager.js'), 'utf8')
        .replace(/^import .*;\r?\n/gm, '').replace('export function openProjectManager', 'function openProjectManager');
    vm.runInNewContext(source, sandbox);
    extension.setup();
    const find = (tag,label) => elements.find(x=>x.isConnected && x.tag===tag && (x.attributes['aria-label']===label || x.textContent===label));
    const section = label => find('select',label)?.parentElement;
    const control = (label, sectionLabel) => {
        const container = sectionLabel ? section(sectionLabel) : null;
        return elements.find(x => x.isConnected && x.tag === 'button' && x.textContent === label && (!container || x.parentElement===container || x.parentElement?.parentElement===container));
    };
    return {app,api,node,identity,requests,calls,alerts,settings,elements,find,control,extension,
        setEnabled(v=true) { enabled=v;settings.get('H3Continuum.ProjectManager.Enabled').onChange(v); },
        async open() { extension.commands[0].function(); await settle(); },
        async chooseProject() { find('select','Project').change(projectId); await settle(); },
        selectAttempt(id='a1') { find('select',locale==='ja'?'試行 / Run':'Trial / Run').change(id); },
        selectPoint(id='s1') { find('select',locale==='ja'?'名前付き保存点':'Named savepoints').change(id); },
        setFail(v) { fail=v; }, setHook(h) {hook=h;}, getState:()=>state,
        async action(label,sectionLabel) { assert(control(label,sectionLabel),label);control(label,sectionLabel).click();await settle(); },
        async ready() { this.setEnabled();await this.open();await this.chooseProject();this.selectAttempt();this.selectPoint(); },
        status() { return elements.find(x=>x.isConnected && x.attributes.role==='status')?.textContent; },
        close() { control(locale==='ja'?'閉じる':'Close')?.click(); },
    };
}
async function test(name, body) { try { await body();results.push({name,pass:true}); } catch(error) { results.push({name,pass:false,error:error.stack}); } }
(async()=>{
await test('host-removed panel can reopen and obsolete responses stay cancelled',async()=>{
    const e=environment();e.setEnabled();await e.open();
    e.elements.find(x=>x.tag==='aside'&&x.isConnected).remove();
    await e.open();assert.equal(e.elements.filter(x=>x.tag==='aside'&&x.isConnected).length,1);
    assert.equal(e.requests.length,2);e.close();
});
await test('disabled and closed Manager do not read data or change graph/Queue', async()=>{
    const e=environment(), before=JSON.stringify(e.app.graph), queue=e.api.queuePrompt;
    assert.equal(e.settings.get('H3Continuum.ProjectManager.Enabled').defaultValue,false);
    assert.equal(e.requests.length,0);await e.open();assert.equal(e.requests.length,0);assert.equal(e.alerts.length,1);
    e.setEnabled();assert.equal(e.requests.length,0);assert.equal(JSON.stringify(e.app.graph),before);assert.equal(e.api.queuePrompt,queue);
});
await test('supported menu entry and one right panel per explicit open',async()=>{
    const e=environment();assert.deepEqual(Array.from(e.extension.menuCommands[0].path),['H3 Continuum']);e.setEnabled();await e.open();await e.open();
    assert.equal(e.elements.filter(x=>x.tag==='aside'&&x.isConnected).length,1);assert.equal(e.requests.length,1);
    assert.equal(e.elements.find(x=>x.tag==='aside').style.right,'12px');e.close();
});
await test('locale follows Comfy Locale for English and Japanese labels',async()=>{
    const e=environment('ja');e.setEnabled();await e.open();assert(e.control('閉じる'));assert(e.control('保存点から再開準備'));assert(e.find('select','対象Sampler'));e.close();
});
await test('closing and disabling leave no requests or callback timers',async()=>{
    const e=environment();e.setEnabled();for(let n=0;n<30;n++){await e.open();e.close();}assert.equal(e.requests.length,30);
    await e.open();e.setEnabled(false);assert.equal(e.elements.filter(x=>x.tag==='aside'&&x.isConnected).length,0);await settle();assert.equal(e.requests.length,31);
});
await test('create Project is metadata-only and uses caller UUID and operation ID',async()=>{
    const e=environment();e.setEnabled();await e.open();e.find('input','Project Name').value='My project';await e.action('Create Project');
    const r=e.requests.at(-1);assert.match(r.body.project_id,/^[a-f0-9-]{36}$/);assert.notEqual(r.body.project_id,r.body.operation_id);assert.equal(e.calls.length,0);assert.match(e.status(),/not been changed/);e.close();
});
await test('new trial requires explicit separate preparation',async()=>{
    const e=environment();await e.ready();e.find('input','Trial / Run Name').value='New take';await e.action('New trial');assert.equal(e.calls.length,0);
    assert.equal(e.find('select','Trial / Run').value,'new-attempt');await e.action('Prepare new trial');assert.equal(e.calls.length,1);
    assert.equal(e.calls[0].run_name,'');assert.equal(e.calls[0].project_id,'33333333-3333-4333-8333-333333333333');e.close();
});
await test('attach current Run never switches graph',async()=>{
    const e=environment();await e.ready();e.find('input','Trial / Run Name').value='Current';await e.action('Add current Run');assert.equal(e.requests.at(-1).body.run_name,'fixture');assert.equal(e.calls.length,0);e.close();
});
await test('savepoint pins selected revision not an implicit moving latest',async()=>{
    const e=environment();await e.ready();e.find('input','Named savepoints Name').value='Good start';await e.action('Name selected Take');
    const body=e.requests.at(-1).body;assert.equal(body.action,'savepoint');assert.equal(body.revision_id,'revision1');assert.equal(body.attempt_id,'a1');assert.equal(e.calls.length,0);e.close();
});
await test('wrong Run cannot create a savepoint in another trial',async()=>{
    const e=environment();await e.ready();e.identity.run_name='different';e.find('input','Named savepoints Name').value='Wrong';const n=e.requests.length;
    await e.action('Name selected Take');assert.equal(e.requests.length,n);assert.match(e.status(),/must belong/);e.close();
});
await test('resume validates with backend then delegates only to existing bridge',async()=>{
    const e=environment();await e.ready();await e.action('Prepare from savepoint');assert.equal(e.calls.length,1);assert.equal(e.calls[0].revision_id,'revision1');
    assert.equal(e.requests.at(-1).body.savepoint_id,'s1');assert.match(e.status(),/normal Queue/);e.close();
});
await test('graph switch while prepare is pending prevents bridge action',async()=>{
    const e=environment();await e.ready();let resolve;e.setHook(()=>new Promise(r=>{resolve=r;}));e.control('Prepare from savepoint').click();await settle();
    e.app.graph={_nodes:[e.node]};resolve(Response.json({run_name:'fixture',revision_id:'revision1'}));await settle();assert.equal(e.calls.length,0);assert.match(e.status(),/changed/);e.close();
});
await test('Take selection changed during pending prepare is rejected',async()=>{
    const e=environment();await e.ready();let resolve;e.setHook(()=>new Promise(r=>{resolve=r;}));e.control('Prepare from savepoint').click();await settle();
    e.identity.revision_id='another';resolve(Response.json({run_name:'fixture',revision_id:'revision1'}));await settle();assert.equal(e.calls.length,0);assert.match(e.status(),/changed/);e.close();
});
await test('closing during pending prepare prevents graph mutation',async()=>{
    const e=environment();await e.ready();let resolve;e.setHook(()=>new Promise(r=>{resolve=r;}));e.control('Prepare from savepoint').click();await settle();e.close();
    resolve(Response.json({run_name:'fixture',revision_id:'revision1'}));await settle();assert.equal(e.calls.length,0);
});
await test('closing during bridge awaits cancels immediately before graph mutation',async()=>{
    const e=environment();await e.ready();let release;e.node.__h3ContinuumManagerBridge.prepareRun=async data=>{
        await new Promise(r=>{release=r;});if(!data.isCurrent())throw new Error('Preparation cancelled');e.calls.push(data);
    };
    e.control('Prepare from savepoint').click();await settle();assert(release);e.close();release();await settle();assert.equal(e.calls.length,0);
});
await test('disabling during fresh-trial bridge awaits cancels mutation',async()=>{
    const e=environment();await e.ready();e.selectAttempt('a2');let release;e.node.__h3ContinuumManagerBridge.prepareRun=async data=>{
        await new Promise(r=>{release=r;});if(!data.isCurrent())throw new Error('Preparation cancelled');e.calls.push(data);
    };
    e.control('Prepare new trial').click();await settle();assert(release);e.setEnabled(false);release();await settle();assert.equal(e.calls.length,0);
});
await test('busy Sampler preparation is disabled but metadata remains available',async()=>{
    const e=environment();e.identity.busy=true;await e.ready();assert(e.control('Prepare from savepoint').disabled);assert(!e.control('Rename','Project').disabled);e.close();
});
await test('unknown write outcome is not replayed and explicit retry retains ID',async()=>{
    const e=environment();await e.ready();e.find('input','Project Name').value='Rename';e.setFail('network');await e.action('Rename','Project');
    const failed=e.requests.at(-1);assert.match(e.status(),/unknown/);assert(e.control('Create Project').disabled);const n=e.requests.length;await settle();assert.equal(e.requests.length,n);
    e.setFail(null);await e.action('Retry pending update');assert.deepEqual(e.requests.at(-1).body,failed.body);assert.equal(e.getState().name,'Rename');e.close();
});
await test('unresolved operation survives close/reopen without automatic replay',async()=>{
    const e=environment();await e.ready();e.find('input','Project Name').value='Rename';e.setFail(500);await e.action('Rename','Project');const failed=e.requests.at(-1);e.close();const n=e.requests.length;
    await e.open();assert.equal(e.requests.length,n);e.setFail(null);await e.action('Retry pending update');assert.deepEqual(e.requests.at(-1).body,failed.body);e.close();
});
await test('original write settling after reopen unlocks and updates the new panel',async()=>{
    const e=environment();await e.ready();e.find('input','Project Name').value='Renamed';let release;e.setHook(()=>new Promise(r=>{release=r;}));
    e.control('Rename','Project').click();await settle();e.close();await e.open();assert(e.control('Refresh').disabled);
    release(Response.json({...record(),name:'Renamed',revision:4}));await settle();assert(!e.control('Refresh').disabled);
    assert(e.control('Retry pending update').hidden);assert.equal(e.find('select','Project').children[1].textContent,'Renamed');assert.match(e.status(),/saved/);e.close();
});
await test('revision conflict requires explicit refresh not silent overwrite',async()=>{
    const e=environment();await e.ready();e.find('input','Project Name').value='Rename';e.setHook(()=>Promise.resolve(Response.json({error:'conflict',code:'project_revision_conflict'},{status:409})));
    await e.action('Rename','Project');assert.match(e.status(),/another tab/);assert(e.control('Rename','Project').disabled);assert(!e.control('Refresh').disabled);assert.equal(e.calls.length,0);e.close();
});
for (const locale of ['en','ja']) {
    await test(`${locale}: refusing a duplicate Run preserves the selected Project, trial and savepoint`,async()=>{
        const e=environment(locale);await e.ready();
        const ja=locale==='ja', trial=ja?'試行 / Run':'Trial / Run', point=ja?'名前付き保存点':'Named savepoints';
        e.find('input',trial+' '+(ja?'名前':'Name')).value='Same Run';
        const before=structuredClone(e.getState()), count=e.requests.length;
        const reason='This Run is already attached to the Project';
        e.setHook(()=>Promise.resolve(Response.json({error:reason},{status:409})));
        await e.action(ja?'現在のRunを追加':'Add current Run');
        assert.equal(e.status(),reason);
        assert.equal(e.requests.length,count+1);assert.equal(e.requests.at(-1).body.action,'attach_attempt');
        assert(!e.control(ja?'名前を変更':'Rename','Project').disabled);
        e.setHook(null);await e.action(ja?'更新':'Refresh');
        assert.equal(e.find('select','Project').value,projectId);
        assert.equal(e.find('select',trial).value,'a1');assert.equal(e.find('select',point).value,'s1');
        assert.deepEqual(e.getState(),before);assert.equal(e.calls.length,0);e.close();
    });
    const reasons = [
        ['read-only', {error:'This saved Take is read-only for Sampling v6; use a new attempt'}, true],
        ['raw integrity', {error:'Saved raw data failed its size/SHA-256 check'}, true],
        ['busy Run', {error:'This Run is queued or running; wait before preparing Review'}, true],
        ['journal limit', {error:'Project operation journal is full; create another Project'}, false],
        ['revision conflict', {error:'Project changed in another tab; refresh before saving',code:'project_revision_conflict'}, false],
        ['unknown error code', {error:'Future refusal reason',code:'future_reason'}, false],
        ['missing reason', {}, false],
    ];
    for (const [name, body, preparing] of reasons) {
        await test(`${locale}: 409 ${name} displays the right reason without Queue or automatic retry`,async()=>{
            const e=environment(locale);await e.ready();
            const state=JSON.stringify(e.getState()), widgets=JSON.stringify(e.node.widgets), requests=e.requests.length;
            e.setHook(()=>Promise.resolve(Response.json(body,{status:409})));
            if (preparing) await e.action(locale==='ja'?'保存点から再開準備':'Prepare from savepoint');
            else await e.action(locale==='ja'?'名前を変更':'Rename','Project');
            const expected=body.code==='project_revision_conflict'
                ? (locale==='ja'?'別のタブでProjectが更新されました。更新して内容を確認してから操作してください。':'This Project changed in another tab. Refresh and review it before trying a new update.')
                : (body.error || 'HTTP 409');
            assert.equal(e.status(),expected);
            assert.equal(e.control(locale==='ja'?'名前を変更':'Rename','Project').disabled,
                body.code==='project_revision_conflict');
            assert.equal(e.requests.length,requests+1);assert.equal(e.calls.length,0);
            assert.equal(JSON.stringify(e.getState()),state);assert.equal(JSON.stringify(e.node.widgets),widgets);
            assert(e.control(locale==='ja'?'未確認の更新を再確認':'Retry pending update').hidden);
            e.close();
        });
    }
}
await test('missing backend leaves generator available and manual refresh recovers',async()=>{
    const e=environment();e.setEnabled();e.setFail(404);await e.open();assert.match(e.status(),/HTTP 404/);assert(!e.control('Refresh').disabled);
    e.setFail(null);await e.action('Refresh');await e.chooseProject();assert.equal(e.find('select','Trial / Run').children.length,3);assert.equal(e.calls.length,0);e.close();
});
await test('late list result after close cannot reopen or update graph',async()=>{
    const e=environment();e.setEnabled();let resolve;e.setHook(()=>new Promise(r=>{resolve=r;}));e.extension.commands[0].function();await settle();e.close();
    resolve(Response.json({projects:[record()],errors:[]}));await settle();assert.equal(e.elements.filter(x=>x.tag==='aside'&&x.isConnected).length,0);assert.equal(e.calls.length,0);
});
await test('names render as text instead of HTML',async()=>{
    const e=environment();await e.ready();e.find('input','Project Name').value='<img src=x onerror=alert(1)>';await e.action('Rename','Project');
    assert.equal(e.find('select','Project').children[1].textContent,'<img src=x onerror=alert(1)>');assert.equal(e.alerts.length,0);e.close();
});
for(const locale of ['en','ja']) {
    for(const kind of ['native','getRandomValues-only','none']) {
        await test(`${locale}: secure operation IDs with ${kind}`,async()=>{
            const crypto=kind==='native'?webcrypto:kind==='none'?null:
                {getRandomValues:webcrypto.getRandomValues.bind(webcrypto)};
            const e=environment(locale,crypto);e.setEnabled();await e.open();
            e.find('input',locale==='ja'?'Project 名前':'Project Name').value='Synthetic';
            const before=e.requests.length;
            await e.action(locale==='ja'?'Projectを作成':'Create Project');
            if(kind==='none') {
                assert.equal(e.requests.length,before);
                assert.match(e.status(),locale==='ja'?/安全な操作ID/:/secure operation IDs/);
            } else {
                const body=e.requests.at(-1).body;
                const pattern=/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
                assert.equal(e.requests.length,before+1);
                assert.match(body.project_id,pattern);assert.match(body.operation_id,pattern);
                assert.notEqual(body.project_id,body.operation_id);
            }
            e.close();
        });
    }
    await test(`${locale}: fallback UUID retry preserves operation identity`,async()=>{
        const e=environment(locale,{getRandomValues:webcrypto.getRandomValues.bind(webcrypto)});
        await e.ready();e.find('input',locale==='ja'?'Project 名前':'Project Name').value='Rename';
        e.setFail('network');await e.action(locale==='ja'?'名前を変更':'Rename','Project');
        const failed=e.requests.at(-1);assert(failed.body.operation_id);
        e.setFail(null);await e.action(locale==='ja'?'未確認の更新を再確認':'Retry pending update');
        assert.deepEqual(e.requests.at(-1).body,failed.body);e.close();
    });
}
console.log(JSON.stringify(results,null,2));if(results.some(x=>!x.pass))process.exitCode=1;
})();
