"""Temporary runner: update the approved workflow fingerprint, then validate."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

BASE = 'f8eb40d8b44e54386bcf3c5197c48f0f71daf6df'
ROOT = Path.cwd()
ALLOWED = {
    'tests/test_v38x2_decode_cache_integration.py',
    'WORKLOG.md', 'PROJECT_STATE.md', 'docs/LOADER_PERSISTENCE_REPAIR.md',
    'MANIFEST.sha256', 'REGISTRY_MANIFEST.sha256',
}

def git(*args):
    return subprocess.check_output(['git', *args], text=True).strip()

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def refresh_manifests():
    # Registry first, because the source declaration may include its digest.
    for name in ('REGISTRY_MANIFEST.sha256', 'MANIFEST.sha256'):
        path = ROOT / name
        entries = [line.split(None, 1)[1].strip()
                   for line in path.read_text().splitlines() if line.strip()]
        path.write_bytes(''.join(f'{sha(ROOT / entry)}  {entry}\n'
                                 for entry in entries).encode())
    for name in ('REGISTRY_MANIFEST.sha256', 'MANIFEST.sha256'):
        for line in (ROOT / name).read_text().splitlines():
            digest, entry = line.split(None, 1)
            assert sha(ROOT / entry.strip()) == digest, (name, entry)

assert git('rev-parse', 'HEAD') == BASE
assert not git('status', '--porcelain'), 'Follow-up checkout must be clean'
before = {p: sha(ROOT / p) for p in git('ls-files').splitlines()
          if (ROOT / p).is_file()}
workflow = ROOT / 'examples/workflows/MiniMax_H3_Continuum_V38X2.json'
expected = '1B2212B7511FAC0B63DFA6E9F006CD8644C72D08C6945AB0E4ED0E722C97A730'
assert sha(workflow).upper() == expected
path = ROOT / 'tests/test_v38x2_decode_cache_integration.py'
old = b'6C445D62979632BC1A801B1C28DBD639C23B51CC156EBAE18837BAAA757E592B'
source = path.read_bytes()
assert source.count(old) == 1
# Preserve every semantic assertion; only the authorized graph fingerprint changes.
path.write_bytes(source.replace(old, expected.encode('ascii')))
refresh_manifests()
subprocess.run(['git', 'diff', '--check'], check=True)
report = Path(os.environ['RUNNER_TEMP']) / 'loader-followup-full.xml'
subprocess.run([sys.executable, '-m', 'pytest', '-q', '-ra', '-p', 'no:cacheprovider',
                f'--junitxml={report}'], check=True)
root = ET.parse(report).getroot()
stats = {k: sum(int(s.get(k, '0')) for s in root.iter('testsuite'))
         for k in ('tests', 'failures', 'errors', 'skipped')}
assert stats['tests'] > 0 and stats['failures'] == stats['errors'] == 0
stats['passed'] = stats['tests'] - stats['skipped']
print('FULL_SUITE_RESULT', json.dumps(stats), flush=True)
note = (f'\n## Loader repair full-suite follow-up (2026-09-21)\n\n'
        f'- Main repair `{BASE}` passed the 46 focused tests. Its first full CI '
        f'returned 1376 passed, 3 skipped, and one stale pre-migration workflow '
        f'fingerprint failure in `test_v38x2_decode_cache_integration.py`.\n'
        f'- Updated only that expected fingerprint to the user-approved migrated '
        f'workflow ({expected}); all Decode Cache route and output assertions remain. '
        f'No runtime or workflow bytes changed in this follow-up.\n'
        f'- Full isolated CPU/Node suite: {stats["passed"]} passed, '
        f'{stats["skipped"]} skipped, zero failures/errors. '
        f'Actions run {os.environ["GITHUB_RUN_ID"]}. Source was snapshotted with '
        f'`tools/snapshot.ps1` before edits; source/Registry manifest hashes verified.\n'
        f'- Windows deployment, live-browser checks and GPU generation were not '
        f'performed; fixed H3情報チェック handoff remains pending. '
        f'No Release/tag/Registry publication.\n')
for name in ('WORKLOG.md', 'docs/LOADER_PERSISTENCE_REPAIR.md'):
    path = ROOT / name
    path.write_bytes(path.read_bytes() + note.encode('utf-8'))
path = ROOT / 'PROJECT_STATE.md'
source = path.read_bytes()
cut = source.index(b'\n') + 1
path.write_bytes(source[:cut] + note.encode('utf-8') + b'\n' + source[cut:])
refresh_manifests()
for name, digest in before.items():
    if name not in ALLOWED:
        assert sha(ROOT / name) == digest, f'Unexpected change: {name}'
changed = set(git('diff', '--name-only').splitlines())
assert changed <= ALLOWED, changed - ALLOWED
assert not git('ls-files', '--others', '--exclude-standard')
subprocess.run(['git', 'diff', '--check'], check=True)
subprocess.run(['git', 'add', '--', *sorted(changed)], check=True)
subprocess.run(['git', 'diff', '--cached', '--stat'], check=True)
