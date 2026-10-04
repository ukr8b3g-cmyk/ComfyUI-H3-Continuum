// Runs the supplied frontend, not copied predicates. No GPU or ComfyUI server.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { webcrypto } = require('node:crypto');
const ROOT = process.env.H3_TEST_ROOT || path.resolve(__dirname,'..');
const results=[];
const sleep=()=>new Promise(r=>setImmediate(r));
function project(n=1,total=3,id='r1',run='fixture') {
  let parent=null;
  const groups=Array.from({length:n},(_,i)=>{
    const g={revision_id:`${id}-g${i+1}`,parent_revision_id:parent,lineage_sha256:'lineage',
      sampling_contract_version:6,generation_reusable:true,
      revision_order:String(i+1),take_number:1,group:{start:i+1,end:i+1,physical_group:i+1}};
    parent=g.revision_id;return g;
  });
  return {run_name:run,run_storage_schema_version:3,branch_provenance_version:1,
    canonical_storage_revision_id:id,canonical_head_revision_id:parent,
    canonical_chain:groups.map(g=>g.revision_id),
    active_revisions:Object.fromEntries(groups.map(g=>[String(g.group.physical_group),g.revision_id])),
    group_revisions:groups,revisions:[{revision_id:id,status:n===total?'complete':'review_ready',
      sampling_contract_version:6,generation_reusable:true,
      updated_utc:`2026-09-08T00:00:0${n}Z`,review_unit:{start:n,end:n,physical_group:n}}]};
}
function environment() {
  const listeners=new Map(), timers=new Set();
  let saved=null, postCount=0, fetchCount=0, nextError=null, queueHook=null, fetchHook=null;
  const submissions=[];
  const api={
    addEventListener(name,callback){const a=listeners.get(name)||[];a.push(callback);listeners.set(name,a);},
    async queuePrompt(number,data,options){
      submissions.push(structuredClone({number,data,options}));
      if(nextError){const e=nextError;nextError=null;throw e;}
      const response={prompt_id:`p${++postCount}`,number:postCount,node_errors:{}};
      if(queueHook)await queueHook(response,data);
      return response;
    },
    async fetchApi(url,opts){return fetcher(url,opts);}
  };
  async function fetcher(url,opts){
    fetchCount++;
    if(fetchHook)return fetchHook(url,opts);
    if(String(url).startsWith('/queue'))return {ok:true,status:200,json:async()=>({queue_running:[],queue_pending:[]})};
    return saved?{ok:true,status:200,json:async()=>structuredClone(saved)}:{ok:false,status:404,json:async()=>null};
  }
  const graph={_nodes:[],links:{},getNodeById(id){return this._nodes.find(n=>String(n.id)===String(id));}};
  const app={api,graph,ui:{settings:{getSettingValue:(_id,fallback)=>fallback,addSetting(){}}},registerExtension(e){this.extension=e;}};
  const sandbox={console,app,api,globalThis:null,crypto:webcrypto,fetch:fetcher,structuredClone,
    setTimeout(cb,ms){const t=setTimeout(()=>{timers.delete(t);cb();},ms);timers.add(t);return t;},
    clearTimeout(t){clearTimeout(t);timers.delete(t);}, Map, Set, WeakMap, Uint8Array};
  sandbox.globalThis=sandbox;
  const referenceSource=fs.readFileSync(path.join(ROOT,'web/reference_images_v39.js'),'utf8')
    .replace(/export function /g,'function ');
  const src=fs.readFileSync(path.join(ROOT,'web/project_id.js'),'utf8')
    .replace(/import \{ app \} from "\.\.\/\.\.\/scripts\/app.js";/,'')
    .replace(/import \{ api \} from "\.\.\/\.\.\/scripts\/api.js";/,'')
    .replace(/import \{ normalizeReferenceAudioLabels \} from "\.\/reference_audio_ui.js";/,'function normalizeReferenceAudioLabels() {}')
    .replace(/import \{ configureV39ReferenceImages, connectedV39LegacyReferenceInputs, pruneV39LegacyReferenceInputs, refreshV39ReferenceImagesForSampler \} from "\.\/reference_images_v39.js";/,'')
    .replace(/import \{ migrateReferenceImageInputs \} from "\.\/reference_image_ui.js";/,'function migrateReferenceImageInputs() {}');
  vm.runInNewContext(referenceSource+'\n'+src+`\nglobalThis.testFns={configureNode,loadTakeHistory,takeCatalog,selectTakeOffset,selectTakeAction,reviewStatus,reviewSettingsChanged,synchronizeReviewQueue};`,sandbox);
  app.extension.setup();
  const f=sandbox.testFns;
  function makeNode(id=312,run='fixture',nodeClass='H3ContinuumSamplerV38',configure=true){
    const v={prompt_mode:'Auto',chunks:3,chunk_seconds:5,aspect:'Auto from First Image',
      preset:'Draft — 0.30 MP',custom_mp:.3,continuity:'Balanced — 22 frames',base_seed:123,
      control_after_generate:'fixed',audio_continuity:true,continuation_backend:'Standard',
      run_storage:'Save + Auto Resume',reroll_from_chunk:'Auto',reroll_nonce:0,run_name:run,
      project_id:'550e8400-e29b-41d4-a716-446655440000',reference_size:'Match Output',
      video_reference_size:'Efficient - 0.4 MP',diagnostics:'Basic',strict_compatibility:false,
      debug:false,show_preview:true,generation_mode:'Full Run',review_action:'Continue / Next',
      take_group:0,take_revision_id:'',take_action:'Automatic',size_source:'Manual',width:544,height:544};
    const n={id,graph,comfyClass:nodeClass,properties:{},inputs:[],size:[500,500],
      widgets:Object.entries(v).map(([name,value])=>({name,value,type:typeof value==='number'?'number':'combo',options:{values:[]},computeSize:()=>[120,20]})),
      addWidget(type,name,value,callback,options){const w={type,name,value,callback,options:options||{},computeSize:()=>[120,20]};this.widgets.push(w);return w;},
      addCustomWidget(w){this.widgets.push(w);return w;},setDirtyCanvas(){},
      getWidgetFromSlot(slot){return this.widgets.find(w=>w.name===slot.widget?.name);},
      getSlotFromWidget(widget){return this.inputs.find(slot=>slot.widget?.name===widget?.name);},
      serialize(){return {widgets_values:this.widgets.map(w=>w.value)};},
      configure(info){info.widgets_values.forEach((v,i)=>{if(this.widgets[i])this.widgets[i].value=v;});}
    };
    graph._nodes.push(n);if(configure)f.configureNode(n);return n;
  }
  const w=(n,name)=>n.widgets.find(w=>w.name===name);
  async function inputs(n){
    for(const x of n.widgets)x.beforeQueued?.();
    const i={};for(const [index,x] of n.widgets.entries()){
      if(!x.name||x.options?.serialize===false)continue;
      i[x.name]=x.serializeValue?await x.serializeValue(n,index):x.value;
    }return i;
  }
  async function queue(n,options){const i=await inputs(n);const data={output:{[n.id]:{class_type:n.comfyClass,inputs:i}},workflow:n.serialize()};
    const result=await api.queuePrompt(0,data,options);
    for(const x of n.widgets)x.afterQueued?.({isPartialExecution:false});return result;}
  async function emit(type,detail){await Promise.all((listeners.get(type)||[]).map(cb=>cb({type,detail})));await sleep();await sleep();}
  async function finishRestore(){
    await app.extension.afterConfigureGraph();
    await Promise.all(graph._nodes.map(n=>n.__h3ContinuumHistoryRequest?.promise));
    await sleep();
  }
  return {f,api,app,w,inputs,queue,emit,makeNode,submissions,setSaved:p=>{saved=p;},
    finishRestore,
    getSaved:()=>saved,getFetchCount:()=>fetchCount,setQueueHook:h=>queueHook=h,setFetchHook:h=>fetchHook=h,
    failQueue:e=>nextError=e,visible:(n,name)=>!w(n,name)?.hidden,
    async load(n,p){saved=p;await f.loadTakeHistory(n,{force:true});n.__h3ContinuumIntuitiveUxRefresh?.();},
    close(){for(const t of timers)clearTimeout(t);}
  };
}
async function test(name,body){const e=environment();try{await body(e);results.push({name,pass:true});}catch(err){results.push({name,pass:false,error:err.stack});}finally{e.close();}}
(async()=>{
await test('no sampler executed: accepted prompt and committed readback open Review',async e=>{
 const n=e.makeNode();await e.load(n,null);e.w(n,'Run').callback('Review Each Chunk');
 const q=await e.queue(n);e.setSaved(project(1));await e.emit('execution_success',{prompt_id:q.prompt_id});
 assert(e.visible(n,'Use it and continue'),'review Continue is missing');
 const i=await e.inputs(n);assert.equal(i.reroll_from_chunk,'Auto');
});
await test('changing Full to Review preserves append intent and manual boundaries',async e=>{
 const n=e.makeNode();await e.load(n,project(3,3));e.w(n,'chunks').value=5;e.w(n,'Run').callback('Review Each Chunk');
 await e.queue(n);assert.equal(e.submissions.at(-1).data.output['312'].inputs.reroll_from_chunk,'Auto');
 e.w(n,'reroll_from_chunk').value='Chunk 3';await e.queue(n);assert.equal(e.submissions.at(-1).data.output['312'].inputs.reroll_from_chunk,'Chunk 3');
});
await test('three review queues advance without any executed events',async e=>{
 const n=e.makeNode();await e.load(n,null);e.w(n,'Run').callback('Review Each Chunk');
 for(let i=1;i<=3;i++){
   const q=await e.queue(n);assert.equal(e.submissions.at(-1).data.output['312'].inputs.reroll_from_chunk,'Auto');
   e.setSaved(project(i));await e.emit('execution_success',{prompt_id:q.prompt_id});
   assert.equal(e.visible(n,'Use it and continue'),i<3);
   assert(e.visible(n,'Try this chunk again'));
   if(i<3)e.w(n,'Use it and continue').callback();
 }
});
await test('unrelated terminal never reloads or clears another queued node',async e=>{
 const n=e.makeNode();await e.load(n,null);e.w(n,'Run').callback('Review Each Chunk');await e.queue(n);
 const before=e.getFetchCount();await e.emit('execution_error',{prompt_id:'unrelated'});
 assert.equal(e.getFetchCount(),before);assert(n.__h3ContinuumModeSetup);
});
await test('sampler saved, downstream failed: recover saved output, do not advance',async e=>{
 const n=e.makeNode();await e.load(n,null);e.w(n,'Run').callback('Review Each Chunk');const q=await e.queue(n);
 e.setSaved(project(1));await e.emit('execution_error',{prompt_id:q.prompt_id,node_id:'vae'});
 assert(e.visible(n,'Retry saved output'));assert(!e.visible(n,'Use it and continue'));
 assert.match(e.f.reviewStatus(n),/saved.*incomplete/i);
 e.w(n,'Retry saved output').callback();const retry=await e.queue(n);
 const inputs=e.submissions.at(-1).data.output['312'].inputs;
 assert.equal(inputs.take_action,'Use This Take');assert.equal(inputs.take_revision_id,'r1-g1');
 e.setSaved(project(1,3,'output-retry'));await e.emit('execution_success',{prompt_id:retry.prompt_id});
 assert(!n.__h3ContinuumOutputFailure);assert(e.visible(n,'Use it and continue'));
});
await test('interruption before commit retains intent without inventing a saved result',async e=>{
 const n=e.makeNode();await e.load(n,null);e.w(n,'Run').callback('Review Each Chunk');const q=await e.queue(n);
 await e.emit('execution_interrupted',{prompt_id:q.prompt_id});
 assert(!e.visible(n,'Use it and continue'));assert(!n.__h3ContinuumOutputFailure);
 const next=await e.inputs(n);assert.equal(next.reroll_from_chunk,'Auto');
});
await test('queue rejection preserves one-shot retry for resubmission',async e=>{
 const n=e.makeNode();e.w(n,'generation_mode').value='Review Each Chunk';await e.load(n,project(1));
 e.w(n,'Try this chunk again').callback();assert.equal(e.w(n,'review_action').value,'Regenerate Current');
 e.failQueue(new Error('validation failed'));await assert.rejects(e.queue(n),/validation failed/);
 assert.equal(e.w(n,'review_action').value,'Regenerate Current');
 await e.queue(n);assert.equal(e.submissions.at(-1).data.output['312'].inputs.review_action,'Regenerate Current');
 assert.equal(e.w(n,'review_action').value,'Continue / Next');
});
await test('history browsing never changes serialized selection, explicit apply does',async e=>{
 const n=e.makeNode();e.w(n,'generation_mode').value='Review Each Chunk';await e.load(n,project(3,3));
 const before=await e.inputs(n);e.f.selectTakeOffset(n,-1);const after=await e.inputs(n);
 for(const k of ['take_group','take_revision_id','take_action'])assert.equal(after[k],before[k]);
 e.f.selectTakeAction(n,'Use This Take');assert.equal(e.w(n,'take_group').value,2);
 assert.equal(e.w(n,'take_revision_id').value,'r1-g2');
 e.f.selectTakeOffset(n,-1);const q=await e.queue(n);
 assert.equal(e.submissions.at(-1).data.output['312'].inputs.take_revision_id,'r1-g2');
});
await test('late response for an old Run cannot replace the current history',async e=>{
 const n=e.makeNode();await e.load(n,project(1));let release;
 e.setFetchHook(()=>new Promise(r=>release=r));const pending=e.f.loadTakeHistory(n,{force:true});
 e.w(n,'run_name').value='other';release({ok:true,status:200,json:async()=>project(2)});await pending;
 assert.notEqual(n.__h3ContinuumTakeProject?.canonical_storage_revision_id,'r2');
 assert.notEqual(n.__h3ContinuumTakeProject?.revisions[0]?.review_unit?.end,2);
});
await test('clearing Run identity invalidates an in-flight history request',async e=>{
 const n=e.makeNode();await e.load(n,null);let release;
 e.setFetchHook(()=>new Promise(r=>release=r));const pending=e.f.loadTakeHistory(n,{force:true});
 e.w(n,'run_name').value='';e.w(n,'project_id').value='';await e.f.loadTakeHistory(n);
 release({ok:true,status:200,json:async()=>project(1)});await pending;assert.equal(n.__h3ContinuumTakeProject,null);
});
await test('identical concurrent history reads are coalesced',async e=>{
 const n=e.makeNode();await e.load(n,null);let release;const before=e.getFetchCount();
 e.setFetchHook(()=>new Promise(r=>release=r));const a=e.f.loadTakeHistory(n);const b=e.f.loadTakeHistory(n);
 assert.equal(e.getFetchCount(),before+1);release({ok:true,status:200,json:async()=>project(1)});await Promise.all([a,b]);
});
await test('two accepted prompts for one node retain distinct identity',async e=>{
 const n=e.makeNode();await e.load(n,null);e.w(n,'Run').callback('Review Each Chunk');
 const p1=await e.queue(n),p2=await e.queue(n);
 e.setSaved(project(2,3,'newer'));await e.emit('execution_success',{prompt_id:p2.prompt_id});
 e.setSaved(project(1,3,'older'));const reads=e.getFetchCount();await e.emit('execution_success',{prompt_id:p1.prompt_id});
 assert.equal(e.getFetchCount(),reads);assert.equal(n.__h3ContinuumTakeProject.canonical_storage_revision_id,'newer');
});
await test('a different sampler completion cannot release this node setup',async e=>{
 const a=e.makeNode(312,'first'),b=e.makeNode(313,'second');
 await e.load(a,null);await e.load(b,null);e.w(a,'Run').callback('Review Each Chunk');e.w(b,'Run').callback('Review Each Chunk');
 await e.queue(a);const q=await e.queue(b);e.setSaved(project(1,3,'second-r','second'));
 await e.emit('execution_success',{prompt_id:q.prompt_id});assert(a.__h3ContinuumModeSetup);assert(!b.__h3ContinuumModeSetup);
});
await test('partial execution excluding sampler leaves its state untouched',async e=>{
 const n=e.makeNode();await e.load(n,null);e.w(n,'Run').callback('Review Each Chunk');const reads=e.getFetchCount();
 const q=await e.queue(n,{partialExecutionTargets:['other-node']});e.setSaved(project(1));
 await e.emit('execution_success',{prompt_id:q.prompt_id});assert(n.__h3ContinuumModeSetup);assert.equal(reads,e.getFetchCount());
});
await test('early terminal before HTTP response is reconciled using the accepted ID',async e=>{
 const n=e.makeNode();await e.load(n,null);e.w(n,'Run').callback('Review Each Chunk');
 e.setQueueHook(async response=>{e.setSaved(project(1));await e.emit('execution_success',{prompt_id:response.prompt_id});});
 await e.queue(n);assert(e.visible(n,'Use it and continue'));assert(!n.__h3ContinuumModeSetup);
});
await test('the caller graph and workflow are not mutated by Queue adapter',async e=>{
 const n=e.makeNode();await e.load(n,project(1));e.w(n,'Run').callback('Review Each Chunk');
 const data={output:{'312':{class_type:n.comfyClass,inputs:await e.inputs(n)}},workflow:n.serialize()};
 const before=JSON.stringify(data);await e.api.queuePrompt(0,data);assert.equal(JSON.stringify(data),before);
});
await test('settings edited during execution remain out of date after readback',async e=>{
 const n=e.makeNode();await e.load(n,null);e.w(n,'Run').callback('Review Each Chunk');const q=await e.queue(n);
 e.w(n,'base_seed').value=999;e.setSaved(project(1));await e.emit('execution_success',{prompt_id:q.prompt_id});
 assert(e.f.reviewSettingsChanged(n));assert(!e.visible(n,'Use it and continue'));
});
await test('a later mode selection is not owned by an earlier prompt',async e=>{
 const n=e.makeNode();await e.load(n,null);e.w(n,'Run').callback('Review Each Chunk');const q=await e.queue(n);
 e.w(n,'Run').callback('Generate Full Video');e.w(n,'Run').callback('Review Each Chunk');const marker=n.__h3ContinuumModeSetup;
 e.setSaved(project(1));await e.emit('execution_success',{prompt_id:q.prompt_id});assert.equal(n.__h3ContinuumModeSetup,marker);
});
await test('missing/failed history readback does not claim success',async e=>{
 const n=e.makeNode();await e.load(n,null);e.w(n,'Run').callback('Review Each Chunk');const q=await e.queue(n);
 e.setFetchHook(async()=>{throw new Error('offline');});await e.emit('execution_success',{prompt_id:q.prompt_id});
 assert(n.__h3ContinuumModeSetup);assert(!e.visible(n,'Use it and continue'));assert.match(n.__h3ContinuumTakeError,/offline/);
});
await test('fresh browser state can open persisted Review without prior events',async e=>{
 const n=e.makeNode();e.w(n,'generation_mode').value='Review Each Chunk';await e.load(n,project(2));
 assert(e.visible(n,'Use it and continue'));assert.match(e.f.reviewStatus(n),/Chunk 2/);
});
await test('optional executed notification alone never releases setup',async e=>{
 const n=e.makeNode();await e.load(n,null);e.w(n,'Run').callback('Review Each Chunk');const q=await e.queue(n);
 e.setSaved(project(1));await e.emit('executed',{node:'312',prompt_id:q.prompt_id});assert(n.__h3ContinuumModeSetup);
 await e.emit('execution_success',{prompt_id:q.prompt_id});assert(!n.__h3ContinuumModeSetup);
});
await test('derived catalog is reused for one immutable readback',async e=>{
 const n=e.makeNode();await e.load(n,project(3,3));assert.equal(e.f.takeCatalog(n),e.f.takeCatalog(n));
});
await test('new Run identity cannot receive an older prompt result',async e=>{
 const n=e.makeNode();await e.load(n,null);e.w(n,'Run').callback('Review Each Chunk');const q=await e.queue(n);
 e.w(n,'run_name').value='new-run';e.setSaved(project(1));const reads=e.getFetchCount();
 await e.emit('execution_success',{prompt_id:q.prompt_id});assert.equal(e.getFetchCount(),reads);assert(n.__h3ContinuumModeSetup);
});


await test('cancelled queued prompt releases busy state without inventing a chunk',async e=>{
 const n=e.makeNode();await e.load(n,null);e.w(n,'Run').callback('Review Each Chunk');await e.queue(n);
 e.setFetchHook(async url=>({ok:true,status:200,json:async()=>String(url).startsWith('/queue')
  ?{queue_running:[],queue_pending:[]}:{}}));
 await e.emit('status',{exec_info:{queue_remaining:0}});
 assert.match(e.f.reviewStatus(n),/no longer pending/);assert(n.__h3ContinuumModeSetup);
});
await test('missed websocket completion is recovered from exact prompt history',async e=>{
 const n=e.makeNode();await e.load(n,null);e.w(n,'Run').callback('Review Each Chunk');const q=await e.queue(n);
 e.setFetchHook(async url=>({ok:true,status:200,json:async()=>String(url).startsWith('/queue')
  ?{queue_running:[],queue_pending:[]}:String(url).startsWith('/history/')
   ?{[q.prompt_id]:{status:{messages:[['execution_success',{prompt_id:q.prompt_id}]]}}}:project(1)}));
 await e.emit('status',{exec_info:{queue_remaining:0}});
 assert(!n.__h3ContinuumModeSetup);assert(e.visible(n,'Use it and continue'));
});
await test('reconnect discovers the exact queued node/run after browser state loss',async e=>{
 const n=e.makeNode();e.w(n,'generation_mode').value='Review Each Chunk';await e.load(n,null);
 const inputs=await e.inputs(n);const queued=[1,'survived-prompt',{'312':{class_type:n.comfyClass,inputs}}, {},['312']];
 e.setFetchHook(async url=>({ok:true,status:200,json:async()=>String(url).startsWith('/queue')
  ?{queue_running:[queued],queue_pending:[]}:project(1)}));
 await e.emit('reconnected',{});assert.match(e.f.reviewStatus(n),/Queued|progress/i);
 e.setFetchHook(null);e.setSaved(project(2));await e.emit('execution_success',{prompt_id:'survived-prompt'});
 assert(e.visible(n,'Use it and continue'));assert.match(e.f.reviewStatus(n),/Chunk 2/);
});
await test('connection error while reconciling is not treated as queue cancellation',async e=>{
 const n=e.makeNode();await e.load(n,null);e.w(n,'Run').callback('Review Each Chunk');const q=await e.queue(n);
 e.setFetchHook(async()=>{throw new Error('network unavailable');});await e.emit('status',{exec_info:{queue_remaining:0}});
 assert(!n.__h3ContinuumQueueNotice);e.setFetchHook(null);e.setSaved(project(1));
 await e.emit('execution_success',{prompt_id:q.prompt_id});assert(e.visible(n,'Use it and continue'));
});
await test('terminal readback failure can recover on reconnect without another Sampling',async e=>{
 const n=e.makeNode();await e.load(n,null);e.w(n,'Run').callback('Review Each Chunk');const q=await e.queue(n);
 e.setFetchHook(async()=>{throw new Error('readback offline');});await e.emit('execution_success',{prompt_id:q.prompt_id});
 e.setFetchHook(async url=>({ok:true,status:200,json:async()=>String(url).startsWith('/queue')
  ?{queue_running:[],queue_pending:[]}:String(url).startsWith('/history/')
   ?{[q.prompt_id]:{status:{messages:[['execution_success',{prompt_id:q.prompt_id}]]}}}:project(1)}));
 await e.emit('reconnected',{});assert(!n.__h3ContinuumModeSetup);assert(e.visible(n,'Use it and continue'));
 assert.equal(e.submissions.length,1);
});


await test('linked chunk count does not block committed review readback',async e=>{
 const n=e.makeNode();await e.load(n,null);e.w(n,'Run').callback('Review Each Chunk');
 const inputs={...await e.inputs(n),chunks:['primitive',0]};
 const q=await e.api.queuePrompt(0,{output:{'312':{class_type:n.comfyClass,inputs},primitive:{class_type:'PrimitiveInt',inputs:{value:3}}},workflow:{}});
 e.setSaved(project(1));await e.emit('execution_success',{prompt_id:q.prompt_id});
 assert(!n.__h3ContinuumModeSetup);assert(e.visible(n,'Use it and continue'));
});
await test('removing one sampler does not discard another accepted sampler',async e=>{
 const a=e.makeNode(312,'one'),b=e.makeNode(313,'two');await e.load(a,null);await e.load(b,null);
 e.w(a,'Run').callback('Review Each Chunk');e.w(b,'Run').callback('Review Each Chunk');
 const q=await e.api.queuePrompt(0,{output:{'312':{class_type:a.comfyClass,inputs:await e.inputs(a)},'313':{class_type:b.comfyClass,inputs:await e.inputs(b)}},workflow:{}});
 a.onRemoved();e.app.graph._nodes=e.app.graph._nodes.filter(n=>n!==a);
 e.setSaved(project(1,3,'two-r1','two'));await e.emit('execution_success',{prompt_id:q.prompt_id});
 assert(e.visible(b,'Use it and continue'));
});
await test('queue adapter owns setup preparation without mutating the caller payload',async e=>{
 const n=e.makeNode();await e.load(n,project(3,3));e.w(n,'chunks').value=5;e.w(n,'Run').callback('Review Each Chunk');
 const inputs=await e.inputs(n);const before=JSON.stringify(inputs);
 await e.api.queuePrompt(0,{output:{'312':{class_type:n.comfyClass,inputs}},workflow:{}});
 assert.equal(JSON.stringify(inputs),before);
 const sent=e.submissions.at(-1).data.output['312'].inputs;
 assert.equal(sent.reroll_from_chunk,'Auto');assert.equal(sent.review_action,'Continue / Next');
 assert.equal(sent.take_action,'Automatic');
});


await test('mode selection preserves progress and still exposes an explicit restart',async e=>{
 const n=e.makeNode();await e.load(n,project(3,3));e.w(n,'Run').callback('Review Each Chunk');
 assert(e.visible(n,'Start again from Chunk 1'));
 e.w(n,'Start again from Chunk 1').callback();const q=await e.queue(n);
 assert.equal(e.submissions.at(-1).data.output['312'].inputs.reroll_from_chunk,'Chunk 1');
 assert.equal(e.w(n,'reroll_from_chunk').value,'Auto');
 e.setSaved(project(1,3,'explicit-restart'));await e.emit('execution_success',{prompt_id:q.prompt_id});
 assert(e.visible(n,'Use it and continue'));
});


await test('persisted review repairs an unowned stale Chunk 1 boundary',async e=>{
 const n=e.makeNode();e.w(n,'reroll_from_chunk').value='Chunk 1';e.w(n,'generation_mode').value='Review Each Chunk';
 await e.load(n,project(1));
 assert.equal(e.w(n,'reroll_from_chunk').value,'Auto');
 assert(e.visible(n,'Use it and continue'));assert(e.visible(n,'Try this chunk again'));
});
await test('explicit advanced Regenerate From remains explicit after refresh',async e=>{
 const n=e.makeNode();e.w(n,'generation_mode').value='Review Each Chunk';await e.load(n,project(1));
 e.w(n,'reroll_from_chunk').value='Chunk 1';e.w(n,'reroll_from_chunk').callback?.('Chunk 1');
 await e.f.loadTakeHistory(n,{force:true});
 assert.equal(e.w(n,'reroll_from_chunk').value,'Chunk 1');
 assert.match(e.f.reviewStatus(n),/Regenerate from Chunk 1/);
});
await test('Progress Off cannot submit a stale Regenerate From boundary',async e=>{
 const n=e.makeNode();await e.load(n,project(1));
 e.w(n,'run_storage').value='Off';e.w(n,'reroll_from_chunk').value='Chunk 1';e.w(n,'generation_mode').value='Full Run';
 await e.queue(n);const sent=e.submissions.at(-1).data.output['312'].inputs;
 assert.equal(sent.run_storage,'Off');assert.equal(sent.reroll_from_chunk,'Auto');assert.equal(sent.reroll_nonce,0);
 assert.equal(e.w(n,'reroll_from_chunk').value,'Auto');
});
await test('successful Auto continue clears stale boundary and restores review buttons',async e=>{
 const n=e.makeNode();e.w(n,'generation_mode').value='Review Each Chunk';await e.load(n,project(1));
 e.w(n,'Use it and continue').callback();const q=await e.queue(n);
 assert.equal(e.submissions.at(-1).data.output['312'].inputs.reroll_from_chunk,'Auto');
 // Simulate stale hidden UI residue appearing after queue acceptance.
 e.w(n,'reroll_from_chunk').value='Chunk 1';
 e.setSaved(project(2));await e.emit('execution_success',{prompt_id:q.prompt_id});
 assert.equal(e.w(n,'reroll_from_chunk').value,'Auto');
 assert(e.visible(n,'Use it and continue'));assert(e.visible(n,'Try this chunk again'));
});


await test('retry consumed after acceptance without legacy preparation hook',async e=>{
 const n=e.makeNode();e.w(n,'generation_mode').value='Review Each Chunk';await e.load(n,project(1));
 e.w(n,'Try this chunk again').callback();await e.queue(n);
 assert.equal(e.w(n,'review_action').value,'Continue / Next');
 await e.queue(n);assert.equal(e.submissions.at(-1).data.output['312'].inputs.review_action,'Continue / Next');
});
await test('explicit restart consumed and Chunk 1 Continue restored',async e=>{
 const n=e.makeNode();e.w(n,'generation_mode').value='Review Each Chunk';await e.load(n,project(3,3));
 assert(e.visible(n,'Start again from Chunk 1'));e.w(n,'Start again from Chunk 1').callback();
 const q=await e.queue(n);assert.equal(e.submissions.at(-1).data.output['312'].inputs.reroll_from_chunk,'Chunk 1');
 e.setSaved(project(1,3,'restarted'));await e.emit('execution_success',{prompt_id:q.prompt_id});
 assert.equal(e.w(n,'reroll_from_chunk').value,'Auto');assert(e.visible(n,'Use it and continue'));
});
await test('850 ms terminal readback releases setup after it resolves',async e=>{
 const n=e.makeNode();await e.load(n,null);e.w(n,'Run').callback('Review Each Chunk');const q=await e.queue(n);
 e.setFetchHook(async()=>{await new Promise(r=>setTimeout(r,850));return {ok:true,status:200,json:async()=>project(1)};});
 await e.emit('execution_success',{prompt_id:q.prompt_id});
 assert.equal(n.__h3ContinuumTakeProject.canonical_storage_revision_id,'r1');
 assert(!n.__h3ContinuumModeSetup);assert(e.visible(n,'Use it and continue'));
});
await test('same completed revision reuse exits setup without new Sampling',async e=>{
 const n=e.makeNode();e.w(n,'chunks').value=2;await e.load(n,project(2,2,'done'));
 e.w(n,'Run').callback('Review Each Chunk');const q=await e.queue(n);
 e.setSaved(project(2,2,'done'));await e.emit('execution_success',{prompt_id:q.prompt_id});
 assert(!n.__h3ContinuumModeSetup);assert(e.visible(n,'Try this chunk again'));assert(e.visible(n,'Start again from Chunk 1'));
 assert(!e.visible(n,'Use it and continue'));assert.equal(e.submissions.length,1);
});
await test('Issue 20 store persistence excludes transient UI across reloads',async e=>{
 // Model the compact store serializer, which does NOT call node.serialize().
 // The flag contract is from ComfyUI_frontend 77bdc5d LGraphNode.ts.
 // Real Continuum UI creation/refresh runs through the existing environment.
 const n=e.makeNode();await e.load(n,null);
 const persistent=()=>n.widgets.filter(w=>!w.__h3ContinuumProductionTransient);
 const values=()=>persistent().map(w=>structuredClone(w.value));
 const storeSave=()=>{
  const widgets=n.widgets.filter(w=>w.serialize!==false);
  return {widgets_values:widgets.map(w=>structuredClone(w.value)),
   widgets_values_named:Object.fromEntries(widgets.map(w=>[w.name,structuredClone(w.value)]))};
 };
 // Array-only projection of Core's forceInput migration in litegraphUtil.ts.
 // A leaked history value makes 30 values look like a 31-value legacy payload.
 const migrate=(widgets,saved)=>{
  const defs=[{name:'sequence_prompt',forceInput:true},
   ...persistent().filter(w=>w.name!=='control_after_generate')
    .map(w=>({name:w.name,control_after_generate:w.name==='base_seed'}))];
  const names=new Set(widgets.map(w=>w.name));
  const skipped=new Set(widgets.filter(w=>w.serialize===false).map(w=>w.name));
  const mask=defs.filter(d=>names.has(d.name)||d.forceInput).flatMap(d=>
   skipped.has(d.name)?[]:d.control_after_generate?[!!d.forceInput,false]:[!!d.forceInput]);
  const count=widgets.filter(w=>w.serialize!==false).length;
  if(!mask.includes(true)&&saved.length===count)return saved;
  const compacted=saved.filter((_,i)=>widgets[i]?.serialize!==false);
  const aligned=compacted.length===mask.length?compacted:saved.length===mask.length?saved:undefined;
  return aligned?aligned.filter((_,i)=>!mask[i]):saved;
 };
 const verify=async()=>{
  const expected=values();assert.equal(expected.length,30);
  const saved=storeSave();
  assert.equal(saved.widgets_values.length,30,'UI-only history leaked into workflow persistence');
  assert.deepEqual(saved.widgets_values,expected);
  assert.deepEqual(n.serialize().widgets_values,expected);
  assert.deepEqual(Object.keys(saved.widgets_values_named),persistent().map(w=>w.name));
  for(const w of n.widgets.filter(w=>w.__h3ContinuumProductionTransient)){
   assert.equal(w.serialize,false,`${w.name}: workflow exclusion`);
   assert.equal(w.options?.serialize,false,`${w.name}: API exclusion`);
  }
  const apiBefore=await e.inputs(n);
  assert(!Object.hasOwn(apiBefore,'Render History / Takes'));
  for(const named of [false,true]){
   for(let i=0;i<3;i++){
    const data=JSON.parse(JSON.stringify(storeSave()));
    const canonical=persistent();
    const migrated=migrate(canonical,data.widgets_values);
    assert.deepEqual(migrated,expected);
    if(named){
     for(const w of canonical)w.value=structuredClone(data.widgets_values_named[w.name]);
    }else n.configure({widgets_values:migrated});
    e.f.configureNode(n);
    assert.deepEqual(values(),expected);
    assert.equal(e.w(n,'Prompt Format').value,e.w(n,'prompt_mode').value);
    assert.equal(e.w(n,'Height').value,e.w(n,'height').value);
   }
  }
  assert.deepEqual(await e.inputs(n),apiBefore);
 };
 // Empty history, ordinary settings, expanded controls, Review and completion.
 e.w(n,'Chunks').callback(6);e.w(n,'Seconds per Chunk').callback(2.5);
 e.w(n,'Width').callback(640);e.w(n,'Height').callback(768);
 await verify();
 e.w(n,'Advanced Settings').callback();await verify();
 e.w(n,'generation_mode').value='Review Each Chunk';await e.load(n,project(1,6));
 await verify();e.w(n,'Render History').callback();await verify();
 e.w(n,'Back to Settings').callback();await verify();
 e.w(n,'Return to Review').callback();await verify();
 await e.load(n,project(6,6,'complete'));await verify();
});
await test('mode policy and transient UI serialization remain stable',async e=>{
 const n=e.makeNode();e.w(n,'run_storage').value='Off';e.w(n,'Run').callback('Review Each Chunk');
 assert.equal(e.w(n,'run_storage').value,'Save + Auto Resume');e.w(n,'Run').callback('Generate Full Video');
 assert.equal(e.w(n,'run_storage').value,'Save + Auto Resume');
 e.w(n,'Run').callback('Review Each Chunk');await e.load(n,project(1));e.w(n,'Return to Review').callback();
 const before=JSON.stringify(n.serialize());e.w(n,'Back to Settings').callback();e.w(n,'Return to Review').callback();
 assert.equal(JSON.stringify(n.serialize()),before);
 const p=project(2,2,'full-complete');delete p.revisions[0].review_unit;await e.load(n,p);
 assert(!e.visible(n,'Try this chunk again'));assert(e.visible(n,'Render History'));
});
await test('history catalog preserves lineage eligibility and compact summary',async e=>{
 const n=e.makeNode();e.w(n,'generation_mode').value='Review Each Chunk';const p=project(3,3);
 p.group_revisions.push({revision_id:'old',lineage_sha256:'other',sampling_contract_version:6,generation_reusable:true,group:{start:1,end:1,physical_group:1}},
 {revision_id:'orphan',parent_revision_id:'missing',lineage_sha256:'lineage',sampling_contract_version:6,generation_reusable:true,group:{start:2,end:2,physical_group:2}});
 await e.load(n,p);assert.equal(e.f.takeCatalog(n).length,3);
 e.w(n,'Render History').callback();const body=e.w(n,'Render History / Takes');
 assert(body.computeSize(400)[1]<=124);const drawn=[];
 body.draw({save(){},restore(){},beginPath(){},rect(){},clip(){},fillText(s){drawn.push(s);}},n,400,0,20);
 assert(drawn.length>1);assert(drawn.some(s=>s.startsWith('Selected:')));
 e.f.selectTakeOffset(n,-1);e.f.selectTakeAction(n,'Continue From Here');
 assert.equal(e.w(n,'take_revision_id').value,'r1-g2');assert.equal(e.w(n,'take_action').value,'Continue From Here');
 assert.equal(p.canonical_head_revision_id,'r1-g3');
});

await test('duration sockets map to visible facades without changing Core names or types',async e=>{
 const n=e.makeNode();
 for(const [name,type,label] of [['chunks','INT','Chunks'],['chunk_seconds','FLOAT','Seconds per Chunk']]){
  const slot={name,type,link:null,widget:{name}};n.inputs.push(slot);
  assert.equal(n.getWidgetFromSlot(slot),e.w(n,label));
  assert.equal(n.getSlotFromWidget(e.w(n,label)),slot);
  assert.equal(n.getSlotFromWidget(e.w(n,name)),slot);
  assert.equal(slot.widget.name,name);assert.equal(slot.type,type);
  assert(!n.getWidgetFromSlot(slot).hidden);assert(e.w(n,name).hidden);
 }
 const other={name:'base_seed',widget:{name:'base_seed'}};n.inputs.push(other);
 assert.equal(n.getWidgetFromSlot(other),e.w(n,'base_seed'));
 const getter=n.getWidgetFromSlot;e.f.configureNode(n);assert.equal(n.getWidgetFromSlot,getter);
 for(const slot of n.inputs.filter(s=>['chunks','chunk_seconds'].includes(s.name))){
  assert.equal(slot._widget,n.getWidgetFromSlot(slot));
  assert(!slot._widget.hidden);
 }
 // Workflow loading replaces slot objects; configure must bind the new slots.
 n.inputs=n.inputs.map(s=>({name:s.name,type:s.type,widget:s.widget,link:null}));
 e.f.configureNode(n);
 assert.equal(n.inputs[0]._widget,e.w(n,'Chunks'));
 assert.equal(n.inputs[1]._widget,e.w(n,'Seconds per Chunk'));
 e.w(n,'generation_mode').value='Review Each Chunk';
 n.inputs[0].link=42;n.inputs[1].link=43;
 await e.load(n,project(1));
 assert(e.visible(n,'Chunks'));assert(e.visible(n,'Seconds per Chunk'));
 assert.equal(n.widgets[0].name,'Chunks');assert.equal(n.widgets[1].name,'Seconds per Chunk');
 e.w(n,'Back to Settings').callback();
 assert.equal(n.widgets[0].name,'Chunks');assert.equal(n.widgets[1].name,'Seconds per Chunk');
 e.w(n,'Return to Review').callback();
 assert.equal(n.widgets[0].name,'Chunks');assert.equal(n.widgets[1].name,'Seconds per Chunk');
 n.inputs[0].link=null;n.inputs[1].link=null;
 n.__h3ContinuumIntuitiveUxRefresh();n.__h3ContinuumProductionUxRefresh();
 assert(!e.visible(n,'Chunks'));assert(!e.visible(n,'Seconds per Chunk'));
});
await test('duration manual entry and serialized values survive connect disconnect and reload',async e=>{
 const n=e.makeNode();e.w(n,'Chunks').callback(6);e.w(n,'Seconds per Chunk').callback(2.5);
 const before=n.serialize();const input={name:'chunks',type:'INT',widget:{name:'chunks'},link:42};
 n.inputs.push(input);n.__h3ContinuumIntuitiveUxRefresh();
 assert.equal(e.w(n,'Total Length').value,'From connected inputs');
 assert.equal(JSON.stringify(n.serialize()),JSON.stringify(before));
 input.link=null;n.__h3ContinuumIntuitiveUxRefresh();
 assert.equal(e.w(n,'Total Length').value,'15 seconds');
 const restored=e.makeNode(313);restored.configure(before);
 assert.equal(e.w(restored,'chunks').value,6);assert.equal(e.w(restored,'chunk_seconds').value,2.5);
 const values=await e.inputs(restored);assert.equal(values.chunks,6);assert.equal(values.chunk_seconds,2.5);
 assert(!Object.hasOwn(values,'Chunks'));assert(!Object.hasOwn(values,'Seconds per Chunk'));
});
await test('external duration links remain links through actual review Queue adapter',async e=>{
 const n=e.makeNode();e.w(n,'chunks').value=1;
 n.inputs.push({name:'chunks',type:'INT',widget:{name:'chunks'},link:42});
 e.w(n,'Run').callback('Review Each Chunk');n.__h3ContinuumIntuitiveUxRefresh();
 assert(!e.w(n,'Chunks').tooltip.includes('Chunks is 1'));
 const data={output:{[n.id]:{class_type:n.comfyClass,inputs:{...(await e.inputs(n)),chunks:['900',0],chunk_seconds:['901',0]}}},workflow:n.serialize()};
 await e.api.queuePrompt(0,data);
 assert.deepEqual(e.submissions.at(-1).data.output[n.id].inputs.chunks,['900',0]);
 assert.deepEqual(e.submissions.at(-1).data.output[n.id].inputs.chunk_seconds,['901',0]);
});
await test('V39 helper settings invalidate transient observed Plan',async e=>{
 const n=e.makeNode(390,'v39','H3ContinuumSamplerV39');
 const helper=e.makeNode(391,'helper','H3ContinuumReferenceImagesV39');
 helper.widgets.push({name:'reference_use',value:'Per chunk',type:'combo',options:{}});
 helper.widgets.push({name:'reference_r1_chunks',value:'1,2',type:'text',options:{}});
 e.app.graph.links[900]={origin_id:391,origin_slot:0,target_id:390,target_slot:0};
 n.inputs.push({name:'reference_images',link:900});
 n.__h3ContinuumIntuitiveUxRefresh();
 const before=JSON.stringify(n.serialize());
 const observed='Reference Plan Inspector (runtime verified)\nGroup 1 [C1] generated — R1=<Picture 1>';
 n.onExecuted({h3_reference_plan:[observed]});
 assert.equal(e.w(n,'Reference Plan Inspector').value,observed);
 assert.equal(JSON.stringify(n.serialize()),before);
 assert.equal((await e.inputs(n)).reference_r1_chunks,undefined);
 e.w(helper,'reference_r1_chunks').value='2';
 n.__h3ContinuumIntuitiveUxRefresh();
 assert.match(e.w(n,'Reference Plan Inspector').value,/Configured only/);
 n.onExecuted({h3_reference_plan:[observed]});
 n.onConnectionsChange(1,0,true);
 assert.match(e.w(n,'Reference Plan Inspector').value,/Configured only/);
 e.app.extension.loadedGraphNode(n);
 assert.match(e.w(n,'Reference Plan Inspector').value,/Configured only/);
 assert.equal(e.w(helper,'reference_r1_chunks').value,'2');
});
await test('V39 loaded node removes only unused old Reference sockets',async e=>{
 const n=e.makeNode(392,'v39-stale','H3ContinuumSamplerV39');
 n.removeInput=function(index){this.inputs.splice(index,1);};
 n.inputs.push(
   {name:'reference_image_1',link:null},
   {name:'reference_image_2',link:77},
   {name:'reference_images',link:null},
 );
 e.app.extension.loadedGraphNode(n);
 assert.deepEqual(n.inputs.map(input=>input.name),['reference_image_2','reference_images']);
 assert.equal(n.inputs[0].link,77);
 assert.match(e.w(n,'Reference Plan Inspector').value,/Old Reference connection/);
 n.inputs[0].link=null;
 e.app.extension.loadedGraphNode(n);
 assert.deepEqual(n.inputs.map(input=>input.name),['reference_images']);
 assert.match(e.w(n,'Reference Plan Inspector').value,/Configured only/);
});
for(const nodeClass of ['H3ContinuumSamplerV38','H3ContinuumSamplerV39']) {
await test(`${nodeClass}: recreated tab waits for saved identity and upstream links`,async e=>{
 const saved=project(1),before=JSON.stringify(saved);e.setSaved(saved);
 e.app.extension.beforeConfigureGraph?.();
 const n=e.makeNode(312,'',nodeClass,false);e.app.extension.nodeCreated(n);
 const reads=e.getFetchCount();
 e.w(n,'run_name').value='fixture';e.w(n,'generation_mode').value='Review Each Chunk';
 e.app.extension.loadedGraphNode(n);
 assert.equal(e.getFetchCount(),reads,'restoration must not fetch a default Run');
 // Core recreates nodes, then restores upstream nodes and link objects.
 const source={id:900,comfyClass:'Text',mode:0,widgets:[{name:'text',value:'A quiet scene.'}],inputs:[]};
 e.app.graph._nodes.push(source);e.app.graph.links[42]={origin_id:900,origin_slot:0};
 n.inputs.push({name:'sequence_prompt',link:42});await e.finishRestore();
 assert.equal(n.__h3ContinuumHistoryRun,'fixture');assert(!e.f.reviewSettingsChanged(n));
 for(const name of ['Use it and continue','Try this chunk again','Use it and finish the rest','Render History'])assert(e.visible(n,name),name);
 e.w(n,'Render History').callback();assert(e.visible(n,'Use This Take'));assert(!e.w(n,'Use This Take').disabled);
 assert.equal(JSON.stringify(saved),before);assert.equal(e.submissions.length,0);
});
}
await test('ten rapid recreated tabs reject every obsolete history response',async e=>{
 const pending=[];e.setFetchHook(url=>new Promise(resolve=>pending.push({url,resolve})));
 const old=[];
 for(let i=0;i<10;i++){
  e.app.extension.beforeConfigureGraph?.();
  for(const n of e.app.graph._nodes){n.onRemoved?.();old.push(n);}e.app.graph._nodes=[];
  const n=e.makeNode(312,`run-${i}`,'H3ContinuumSamplerV39',false);
  e.w(n,'generation_mode').value='Review Each Chunk';e.app.extension.nodeCreated(n);e.app.extension.loadedGraphNode(n);
  await e.app.extension.afterConfigureGraph();
 }
 assert.equal(pending.length,10);
 const latest=e.app.graph._nodes[0];
 for(let i=9;i>=0;i--)pending[i].resolve({ok:true,status:200,json:async()=>project(1,3,`r-${i}`,`run-${i}`)});
 await Promise.all([...old,latest].map(n=>n.__h3ContinuumHistoryRequest?.promise));await sleep();
 assert.equal(latest.__h3ContinuumTakeProject.canonical_storage_revision_id,'r-9');
 assert(old.every(n=>!n.__h3ContinuumTakeProject));assert(e.visible(latest,'Use it and continue'));
 assert.equal(e.submissions.length,0);
});
await test('API graph restoration without a before hook still reloads history',async e=>{
 const n=e.makeNode();await e.load(n,null);e.setSaved(project(1));
 e.w(n,'generation_mode').value='Review Each Chunk';await e.finishRestore();
 assert(e.visible(n,'Use it and continue'));assert(!e.f.reviewSettingsChanged(n));
});
await test('manually added sampler loads history after deferred setup',async e=>{
 e.setSaved(project(1));const n=e.makeNode(312,'fixture','H3ContinuumSamplerV39',false);
 e.w(n,'generation_mode').value='Review Each Chunk';e.app.extension.nodeCreated(n);
 assert.equal(e.getFetchCount(),0);await n.__h3ContinuumConfigurePending?.promise;
 await n.__h3ContinuumHistoryRequest?.promise;await sleep();
 assert(e.visible(n,'Use it and continue'));
});
await test('real edits while restored history is pending retain the settings guard',async e=>{
 let release;e.setFetchHook(()=>new Promise(resolve=>release=resolve));
 e.app.extension.beforeConfigureGraph?.();const n=e.makeNode(312,'fixture','H3ContinuumSamplerV39',false);
 e.w(n,'generation_mode').value='Review Each Chunk';e.app.extension.nodeCreated(n);
 await e.app.extension.afterConfigureGraph();e.w(n,'base_seed').value=999;
 release({ok:true,status:200,json:async()=>project(1)});await n.__h3ContinuumHistoryRequest?.promise;
 assert(e.f.reviewSettingsChanged(n));assert(!e.visible(n,'Use it and continue'));
});
await test('same revision graph refresh cannot erase an existing real edit',async e=>{
 const n=e.makeNode();e.w(n,'generation_mode').value='Review Each Chunk';await e.load(n,project(1));
 e.w(n,'base_seed').value=999;await e.finishRestore();
 assert(e.f.reviewSettingsChanged(n));assert(!e.visible(n,'Use it and continue'));
});
await test('graph epoch rejects old results even if the same node remains attached',async e=>{
 const n=e.makeNode();await e.load(n,null);let release;
 e.setFetchHook(()=>new Promise(resolve=>release=resolve));const request=e.f.loadTakeHistory(n,{force:true});
 e.app.extension.beforeConfigureGraph?.();
 release({ok:true,status:200,json:async()=>project(1)});await request;
 assert(!n.__h3ContinuumTakeProject);
 e.setFetchHook(null);e.setSaved(project(1));e.w(n,'generation_mode').value='Review Each Chunk';
 await e.finishRestore();assert(e.visible(n,'Use it and continue'));
});
await test('removed sampler cancels deferred setup without fetching or mutating it',async e=>{
 e.setSaved(project(1));const n=e.makeNode(312,'fixture','H3ContinuumSamplerV39',false);
 e.app.extension.nodeCreated(n);const setup=n.__h3ContinuumConfigurePending?.promise;
 n.onRemoved();e.app.graph._nodes=[];await setup;
 assert.equal(e.getFetchCount(),0);assert(!n.__h3ContinuumTakeProject);
});
await test('initial restored history read preserves saved Take selection fields',async e=>{
 e.app.extension.beforeConfigureGraph?.();e.setSaved(project(1));
 const n=e.makeNode(312,'fixture','H3ContinuumSamplerV39',false);e.app.extension.nodeCreated(n);
 e.w(n,'take_group').value=1;e.w(n,'take_revision_id').value='r1-g1';
 // One-shot actions are normalized separately by the existing load hook.
 e.app.extension.loadedGraphNode(n);await e.finishRestore();
 assert.equal(e.w(n,'take_group').value,1);assert.equal(e.w(n,'take_revision_id').value,'r1-g1');
});
await test('restored missing or failed history reports accurately and can retry',async e=>{
 const n=e.makeNode();await e.load(n,null);await e.finishRestore();
 assert(!n.__h3ContinuumTakeProject);assert(!n.__h3ContinuumTakeError);
 e.setFetchHook(async()=>({ok:false,status:500}));await e.finishRestore();
 assert.match(e.w(n,'Ready to Queue').headline,/unavailable/);
 e.setFetchHook(null);e.setSaved(project(1));e.w(n,'generation_mode').value='Review Each Chunk';
 await e.finishRestore();assert(e.visible(n,'Use it and continue'));assert(!n.__h3ContinuumTakeError);
});
await test('failed graph load releases hydration gate for subsequent manual nodes',async e=>{
 e.app.extension.beforeConfigureGraph?.();e.app.extension.onGraphLoadError?.();
 e.setSaved(project(1));const n=e.makeNode(312,'fixture','H3ContinuumSamplerV39',false);
 e.w(n,'generation_mode').value='Review Each Chunk';e.app.extension.nodeCreated(n);
 await n.__h3ContinuumConfigurePending?.promise;await n.__h3ContinuumHistoryRequest?.promise;await sleep();
 assert(e.visible(n,'Use it and continue'));
});
await test('Sampling v5 history stays visible and actions remain read-only',async e=>{
 const p=project(2);for(const item of [...p.group_revisions,...p.revisions]){
   item.sampling_contract_version=5;item.generation_reusable=false;
 }
 const n=e.makeNode();await e.load(n,p);
 assert.equal(e.f.takeCatalog(n).length,2);
 assert.match(e.f.reviewStatus(n),/read-only/);
 const before=[e.w(n,'take_action').value,e.w(n,'take_revision_id').value];
 e.f.selectTakeAction(n,'Use This Take');
 assert.deepEqual([e.w(n,'take_action').value,e.w(n,'take_revision_id').value],before);
 assert(!e.visible(n,'Use it and continue'));
});
await test('archived v5 lineage remains browsable after a v6 canonical run',async e=>{
 const old=project(2,'fixture',3,'old');for(const item of old.group_revisions){
   item.sampling_contract_version=5;item.generation_reusable=false;item.lineage_sha256='old-lineage';
 }
 const current=project(1);current.group_revisions.push(...old.group_revisions);
 const n=e.makeNode();await e.load(n,current);
 assert.equal(e.f.takeCatalog(n).length,3);
});
console.log(JSON.stringify(results,null,2));if(results.some(r=>!r.pass))process.exitCode=1;
})();
