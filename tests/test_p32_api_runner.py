from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "tools" / "p32_api_runner.py"
SPEC = importlib.util.spec_from_file_location("h3_p32_api_runner", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def test_history_complete_accepts_completed_status():
    assert runner._history_complete(
        {"abc": {"status": {"completed": True}, "outputs": {}}}, "abc"
    )
    assert not runner._history_complete({}, "abc")


def test_history_error_extracts_execution_failure():
    history = {
        "abc": {
            "status": {
                "messages": [
                    ["execution_start", {"prompt_id": "abc"}],
                    ["execution_error", {"exception_message": "bad"}],
                ]
            }
        }
    }
    value = runner._history_error(history, "abc")
    assert value is not None
    assert "execution_error" in value
    assert runner._history_error({}, "abc") is None
