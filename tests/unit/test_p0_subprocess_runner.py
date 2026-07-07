from __future__ import annotations

import sys
from pathlib import Path

from tools.product.subprocess_runner import run_cmd


def test_p0_subprocess_runner_times_out_fail_closed(monkeypatch) -> None:
    monkeypatch.setenv("BETELGEUZE_SUBPROCESS_TIMEOUT_SEC", "0.01")

    payload = run_cmd([sys.executable, "-c", "import time; time.sleep(1)"])

    assert payload["ok"] is False
    assert payload["timed_out"] is True
    assert payload["returncode"] == 124
    assert payload["failure_class"] == "timeout"
    assert "timed out" in payload["stderr_tail"]


def test_p0_subprocess_runner_writes_requested_artifacts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BETELGEUZE_SUBPROCESS_LOG_DIR", str(tmp_path))

    payload = run_cmd([sys.executable, "-c", "print('runner ok')"])

    assert payload["ok"] is True
    assert payload["failure_class"] == ""
    assert Path(payload["stdout_path"]).exists()
    assert Path(payload["stderr_path"]).exists()
    assert "runner ok" in Path(payload["stdout_path"]).read_text(encoding="utf-8")
