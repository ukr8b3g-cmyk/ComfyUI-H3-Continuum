"""One-shot publisher support. Runs only in the isolated Issue20 worktree."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

BASE = 'bd12073c4322a88ce666fe062b7bb265f5de131a'
ROOT = Path.cwd()
HELPERS = Path(__file__).resolve().parent
EVIDENCE = Path(os.environ['RUNNER_TEMP']) / 'issue20-evidence'
EVIDENCE.mkdir(exist_ok=True)
EXPECTED = {
 'web/project_id.js': 'dcef8db261339ff08568512dcb4ccb80834ef5e4af073ab45909fc82ebcb2a0a',
 'tests/frontend_review_queue.cjs': 'eece5f447c05f9835571899910451e6b0de285b961e3c0491e3f9134adf3b05f',
 'tests/frontend_issue20_persistence.cjs': '572de38536d896e20b2efb4e97c3bf87e38bb995489cef77e540b884638fa843',
 'tests/test_issue20_persistence.py': 'd294cece75592e1a2bf18f32f75bbef01d6490a051cd816795e4cc516c55c108',
}

def replace(rel, old, new, count=1):
    p = ROOT / rel
    raw = p.read_bytes()
    assert raw.count(old.encode()) == count, (rel, old[:80])
    p.write_bytes(raw.replace(old.encode(), new.encode()))

def apply():
    assert subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip() == BASE
    assert not subprocess.check_output(['git','status','--porcelain'], text=True).strip()
    replace('web/project_id.js', '''        node.serialize = function(...args) {
            return withoutTransientWidgets(originalSerialize, this, args);
        };''', '''        node.serialize = function(...args) {
            // Serialize is also used by tab-state/change tracking. Never splice
            // the live (possibly reactive) widget array during that read path.
            const widgets = this.widgets;
            const result = originalSerialize.apply(this, args);
            if (!Array.isArray(widgets) || !Array.isArray(result?.widgets_values)) return result;
            const persistent = widgets.map((widget, index) => ({ widget, index }))
                .filter(({ widget }) => !widget?.[PRODUCTION_TRANSIENT_WIDGET]);
            const values = result.widgets_values;
            // Core's indexed serializer leaves slots for excluded widgets;
            // other frontend paths already return a compact positional array.
            if (persistent.length === widgets.length || values.length <= persistent.length) return result;
            return { ...result, widgets_values: persistent.map(({ index }) => values[index]) };
        };''')
    replace('web/project_id.js', '    node.widgets.splice(0, node.widgets.length, ...ordered, ...remainder);', '''    const next = [...ordered, ...remainder];
    if (next.length !== node.widgets.length
        || next.some((widget, index) => widget !== node.widgets[index])) {
        node.widgets.splice(0, node.widgets.length, ...next);
    }''', 2)
    replace('web/project_id.js', '''        const link = app.graph?.links?.[input.link];
        const source = app.graph?.getNodeById?.(link?.origin_id);''', '''        // A deferred refresh may outlive the active workflow tab.
        const graph = node.graph || app.graph;
        const link = graph?.links?.[input.link];
        const source = graph?.getNodeById?.(link?.origin_id);''')
    replace('web/project_id.js', 'function configureNodeAfterSetup(node) {', 'const deferredNodeSetups = new WeakMap();\n\nfunction configureNodeAfterSetup(node) {')
    replace('web/project_id.js', '    const configureDeferred = () => configureNode(node);\r\n', '''    const graph = node.graph || app.graph;
    const token = {};
    deferredNodeSetups.set(node, token);
    const configureDeferred = () => {
        // Old nodes can share IDs with a newly restored workflow. Do not let
        // their pending setup mutate the restored graph or detached widgets.
        if (deferredNodeSetups.get(node) !== token || node.graph !== graph) return;
        if (graph?.getNodeById?.(node.id) !== node) return;
        configureNode(node);
    };
''')
    replace('tests/frontend_review_queue.cjs', 'testFns={configureNode,loadTakeHistory,', 'testFns={configureNode,configureNodeAfterSetup,moveFacadeWidgetsToFront,moveNamedWidgetsToFront,loadTakeHistory,')
    replace('tests/frontend_review_queue.cjs', "function makeNode(id=312,run='fixture'){", "function makeNode(id=312,run='fixture',beforeConfigure=null){")
    replace('tests/frontend_review_queue.cjs', 'graph._nodes.push(n);f.configureNode(n);return n;', 'graph._nodes.push(n);beforeConfigure?.(n);f.configureNode(n);return n;')
    replace('tests/frontend_review_queue.cjs', '(async()=>{\nawait test(', 'if (require.main !== module) {\n module.exports = { environment, project };\n} else (async()=>{\nawait test(')
    shutil.copyfile(HELPERS / 'issue20_tests.cjs', ROOT / 'tests/frontend_issue20_persistence.cjs')
    (ROOT / 'tests/test_issue20_persistence.py').write_text('''"""CPU-only regression gate for the Issue #20 frontend candidate."""
import json
import os
from pathlib import Path
import shutil
import subprocess


def test_issue20_persistence_frontend():
    root = Path(__file__).resolve().parents[1]
    node = shutil.which("node")
    assert node, "Node.js is required for the Issue #20 frontend gate"
    result = subprocess.run(
        [node, str(root / "tests" / "frontend_issue20_persistence.cjs")],
        env={**os.environ, "H3_TEST_ROOT": str(root)},
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    records = json.loads(result.stdout)
    assert len(records) == 9, "All Issue #20 persistence scenarios must finish"
    assert result.returncode == 0 and all(item["pass"] for item in records), (
        result.stdout + result.stderr
    )
''', encoding='utf-8')
    for rel, expected in EXPECTED.items():
        actual = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
        assert actual == expected, (rel, actual, expected)
    refresh_manifests()
    print('Candidate bytes match the locally validated patch (4 source/test files).')


def refresh_manifests():
    for name, paths in [('MANIFEST.sha256', ['web/project_id.js','tests/frontend_review_queue.cjs']), ('REGISTRY_MANIFEST.sha256',['web/project_id.js'])]:
        p = ROOT / name
        raw = p.read_bytes()
        for rel in paths:
            matches = [line for line in raw.splitlines(keepends=True) if line.decode().rstrip().endswith('  '+rel)]
            assert len(matches) == 1, (name,rel)
            old = matches[0]
            raw = raw.replace(old, hashlib.sha256((ROOT / rel).read_bytes()).hexdigest().encode() + old[64:])
        p.write_bytes(raw)


def suite(name):
    root = ET.parse(EVIDENCE / f'{name}.xml').getroot()
    tests = list(root.iter('testcase'))
    failed = sorted(x.get('classname','')+'::'+x.get('name','') for x in tests if x.find('failure') is not None or x.find('error') is not None)
    skipped = sum(x.find('skipped') is not None for x in tests)
    return {'total':len(tests),'passed':len(tests)-len(failed)-skipped,'failed':failed,'skipped':skipped}


def finalize():
    base, candidate = suite('base'), suite('candidate')
    assert candidate['failed'] == base['failed'], 'New or changed CPU failures; do not publish'
    assert candidate['passed'] == base['passed'] + 1, (base,candidate)
    assert candidate['skipped'] == base['skipped']
    red = json.loads((EVIDENCE/'issue20-red.json').read_text())
    green = json.loads((EVIDENCE/'issue20-green.json').read_text())
    original = json.loads((EVIDENCE/'existing-frontend.json').read_text())
    assert len(red) == len(green) == 9
    assert sum(not x['pass'] for x in red) == 7, red
    assert all(x['pass'] for x in green)
    assert len(original) == 46 and all(x['pass'] for x in original)
    report = {'base':base, 'candidate':candidate, 'frontend_existing':46, 'frontend_issue20':9, 'baseline_regression_failures':7, 'gpu_tested':False,'reporter_browser_reproduced':False}
    (EVIDENCE/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    summary = f'''\n## Issue #20 persistence candidate (2026-09-11; test branch only)\n\n- User authorized `test/issue-20-workflow-persistence`, based on `{BASE}`. The maintainer still cannot reproduce the reporter's complete Model/VAE/LoRA reset; this is a candidate, not a confirmed resolution. Main, tags/releases, installed Windows runtimes and saved Takes are untouched.\n- Runtime scope is only `web/project_id.js`: serialize without removing/reinserting live widgets, skip unchanged widget reorder operations, discard obsolete/detached deferred setup, and resolve First Image geometry using the owning graph. Backend schema/order, Sampling, Review Queue, Run Storage, Audio and public workflow bytes are unchanged. Canvas repaint is retained; `setDirtyCanvas` alone is not treated as evidence of a persistence defect.\n- Existing Node fixture 46/46 PASS. Additional candidate scenarios 9/9 PASS; 7 fail against unmodified base runtime. Tests are modeled lifecycle/serializer tests, not real-browser reproduction. Full CPU comparison: baseline {base['passed']} passed / {len(base['failed'])} failed / {base['skipped']} skipped; candidate {candidate['passed']} passed / {len(candidate['failed'])} failed / {candidate['skipped']} skipped. Failure identities are unchanged (existing missing workflow assets); no new CPU failures.\n- Before source edits, `tools/snapshot.ps1` created a count/hash-verified pinned-source snapshot in the isolated runner. Fixed H3情報チェック task was unavailable from this session; its review and reporter browser verification remain pending. Do not promote to main on these modeled tests alone. See `docs/ISSUE20_TEST_BRANCH.md` and the validation run artifacts.\n'''
    p=ROOT/'PROJECT_STATE.md'
    data=p.read_bytes(); marker=b'# Project State\n'
    assert data.startswith(marker)
    p.write_bytes(marker+summary.encode()+data[len(marker):])
    p=ROOT/'WORKLOG.md'
    p.write_bytes(p.read_bytes()+summary.encode())
    shutil.copyfile(HELPERS/'issue20_readme.md',ROOT/'docs/ISSUE20_TEST_BRANCH.md')
    print(json.dumps(report,indent=2))

if __name__ == '__main__':
    {'apply':apply,'finalize':finalize}[sys.argv[1]]()
