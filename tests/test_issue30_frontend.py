"""Issue #30 overhead and Reference Inspector reconfiguration regressions."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def run_frontend(filename):
    node = shutil.which("node")
    assert node, "Node.js is required for frontend regression tests"
    return subprocess.run(
        [node, str(ROOT / "tests" / filename)],
        env={**os.environ, "H3_TEST_ROOT": str(ROOT)},
        capture_output=True, text=True, encoding="utf-8", timeout=45,
    )


def test_reference_selection_notifications_and_layout():
    result = run_frontend("frontend_reference_images_v39.cjs")
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.fixture(scope="module")
def issue30_results():
    result = run_frontend("frontend_issue30_ui.cjs")
    assert result.returncode == 0, result.stdout + result.stderr
    records = json.loads(result.stdout)
    assert len(records) == 16
    return {record["name"]: record for record in records}


@pytest.mark.parametrize("name", [
    "no Review baseline: draw does not traverse upstream settings",
    "Review baseline: every draw still detects upstream edits",
    *[f"{node_class}: {change} edit keeps immediate Take and draw guards"
      for node_class in ("H3ContinuumSamplerV38", "H3ContinuumSamplerV39")
      for change in ("widget", "link")],
    "Reference Inspector stays current after 1 configure passes",
    "Reference Inspector stays current after 2 configure passes",
    "Reference Inspector stays current after 100 configure passes",
    "Reference Inspector rejects a late result after an assignment edit",
    "Reference Inspector isolates prompt order, sampler and graph identity",
    "Reference Inspector handles execution before the Queue HTTP response",
    "Reference Inspector resolves a nested execution ID without changing its inputs",
    "removing one queued Sampler keeps only the other Sampler eligible",
    "H3ContinuumSamplerV38 Review checks the effective seed input",
    "H3ContinuumSamplerV39 Review checks the effective seed input",
])
def test_issue30_frontend_paths(issue30_results, name):
    record = issue30_results[name]
    assert record["pass"], record.get("error", name)
