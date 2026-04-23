from __future__ import annotations

import json
from pathlib import Path

from tools import run_wetlab_broad_screen_runtime_event as mod


def test_primary_runtime_event_heartbeat_loop(tmp_path: Path, monkeypatch) -> None:
    progress_md = tmp_path / "progress.md"
    log_path = tmp_path / "events.jsonl"
    monkeypatch.setattr(mod, "DEFAULT_PROGRESS_MD", str(progress_md))
    monkeypatch.setattr(mod, "DEFAULT_LOG_PATH", log_path)

    rebuild_calls: list[str] = []
    sleep_calls: list[float] = []

    def _fake_rebuild(*_: str, **__: str) -> None:
        rebuild_calls.append("rebuild")

    monkeypatch.setattr(mod, "_rebuild_support", _fake_rebuild)
    monkeypatch.setattr(mod.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    result = mod.run_event(
        target_id="CA IX",
        shard_id="08_of_20",
        event="heartbeat",
        python_bin="python3",
        loop=True,
        interval_sec=1.0,
        max_heartbeats=2,
        active_stage_label="broad_screen_primary_shard",
        log_path=log_path,
    )

    assert result["event"] == "heartbeat_loop_complete"
    assert result["pulse_count"] == 2
    assert rebuild_calls == ["rebuild", "rebuild"]
    assert sleep_calls == [1.0]
    payload = progress_md.with_suffix(".json").read_text(encoding="utf-8")
    assert "heartbeat_count" in payload


def test_complete_event_passes_append_mode_and_refresh_tier(tmp_path: Path, monkeypatch) -> None:
    progress_md = tmp_path / "progress.md"
    log_path = tmp_path / "events.jsonl"
    monkeypatch.setattr(mod, "DEFAULT_PROGRESS_MD", str(progress_md))
    monkeypatch.setattr(mod, "DEFAULT_LOG_PATH", log_path)

    rebuild_calls: list[str] = []
    append_calls: list[list[str]] = []

    monkeypatch.setattr(mod, "_rebuild_support", lambda *args, **kwargs: rebuild_calls.append("rebuild"))

    def _fake_run(cmd, cwd=None, check=None):
        append_calls.append([str(part) for part in cmd])
        return None

    monkeypatch.setattr(mod.subprocess, "run", _fake_run)

    mod.run_event(
        target_id="CA IX",
        shard_id="08_of_20",
        event="complete",
        python_bin="python3",
        rows_json="runs/rows.json",
        append_mode="enqueue",
        append_refresh_tier="minimal",
        append_batch_md="runs/batch.md",
        started_at="2026-03-30T10:00:00",
        updated_at="2026-03-30T10:05:00",
        completed_at="2026-03-30T10:05:00",
        log_path=log_path,
    )

    assert rebuild_calls == ["rebuild"]
    assert append_calls
    append_cmd = append_calls[0]
    assert any(part.endswith("tools/run_wetlab_broad_screen_actual_append.py") for part in append_cmd)
    assert "--mode" in append_cmd and "enqueue" in append_cmd
    assert "--refresh-tier" in append_cmd and "minimal" in append_cmd
    assert "--batch-md" in append_cmd and "runs/batch.md" in append_cmd

    progress_payload = json.loads(progress_md.with_suffix(".json").read_text(encoding="utf-8"))
    assert progress_payload["summary"]["status"] == "wetlab_broad_screen_progress_ready"
    assert progress_payload["summary"]["resolved_row_count"] == 1
    assert progress_payload["rows"][0]["queue_status"] == "result_ready"
    assert progress_payload["rows"][0]["last_event"] == "complete"
