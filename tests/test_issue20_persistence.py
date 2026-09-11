"""CPU-only regression gate for the Issue #20 frontend candidate."""
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
