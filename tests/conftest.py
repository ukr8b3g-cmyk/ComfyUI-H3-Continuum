from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "ComfyUI_H3_Continuum_Join"
if PACKAGE_NAME not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        PACKAGE_NAME,
        ROOT / "__init__.py",
        submodule_search_locations=[str(ROOT)],
    )
    module = importlib.util.module_from_spec(spec)
    module.__path__ = [str(ROOT)]
    sys.modules[PACKAGE_NAME] = module


# Run real production JS through ComfyUI's supported queue lifecycle once.
# No unsupported beforeQueuePrompt helper injection or copied UI predicates.
import json
import os
import shutil
import subprocess

import pytest


@pytest.fixture(scope="session")
def review_queue_results():
    node = shutil.which("node")
    assert node, "Node.js is required for the frontend regression gate"
    result = subprocess.run(
        [node, str(ROOT / "tests" / "frontend_review_queue.cjs")],
        env={**os.environ, "H3_TEST_ROOT": str(ROOT)},
        capture_output=True, text=True, encoding="utf-8", timeout=45,
    )
    records = json.loads(result.stdout)
    assert len(records) == 46, "The complete queue fixture must finish, including duration-input and Issue 20 persistence cases"
    failures = [item for item in records if not item["pass"]]
    assert result.returncode == 0 and not failures, result.stdout + result.stderr
    return {item["name"]: item for item in records}
