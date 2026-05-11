from __future__ import annotations

from tools import run_viewer_smoke_refresh as mod


def test_run_with_retries_marks_transient_recovery(monkeypatch) -> None:
    results = [
        {"cmd": ["demo"], "returncode": 1, "elapsed_sec": 0.1, "stdout": "", "stderr": "viewer_not_ready", "ok": False},
        {"cmd": ["demo"], "returncode": 0, "elapsed_sec": 0.2, "stdout": "{}", "stderr": "", "ok": True},
    ]

    def fake_run(cmd: list[str]) -> dict:
        return dict(results.pop(0))

    monkeypatch.setattr(mod, "_run", fake_run)
    monkeypatch.setattr(mod.time, "sleep", lambda _seconds: None)

    result = mod._run_with_retries(["demo"], max_attempts=2, retry_delay_sec=0)

    assert result["ok"] is True
    assert result["attempt_count"] == 2
    assert result["retry_recovered"] is True
    assert [attempt["ok"] for attempt in result["attempts"]] == [False, True]
