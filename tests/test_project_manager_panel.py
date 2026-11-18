"""Optional Manager panel uses production JavaScript, without browser/GPU claims."""
import json
import os
from pathlib import Path
import shutil
import subprocess


def test_project_manager_panel_cpu_javascript():
    node = shutil.which("node")
    assert node, "Node.js is required for frontend regression checks"
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [node, str(root / "tests/frontend_project_manager_panel.cjs")],
        env={**os.environ, "H3_TEST_ROOT": str(root)},
        capture_output=True, text=True, encoding="utf-8", timeout=40,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    records = json.loads(result.stdout)
    assert len(records) == 48
    assert all(item["pass"] for item in records), records
