from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import run_wetlab_broad_screen_antitarget_runtime_event as mod


def test_antitarget_runtime_event_start_and_reset(tmp_path: Path, monkeypatch) -> None:
    progress_md = tmp_path / "progress.md"
    log_path = tmp_path / "events.jsonl"
    monkeypatch.setattr(mod, "DEFAULT_PROGRESS_MD", str(progress_md))
    monkeypatch.setattr(mod, "DEFAULT_LOG_PATH", log_path)

    rebuild_calls: list[str] = []

    def _fake_rebuild(*_: object, **__: object) -> None:
        rebuild_calls.append("rebuild")

    monkeypatch.setattr(mod, "_rebuild_support", _fake_rebuild)

    row = mod.apply_event(
        primary_target_id="CA IX",
        anti_target_id="CA II",
        shard_id="01_of_20",
        event="start",
        python_bin="python3",
        active_stage_label="antitarget_counterscreen_primary_shard",
        started_at="2026-03-30T02:20:00",
        updated_at="2026-03-30T02:20:00",
        notes="runtime_validation_only",
        compute_summary_json="runs/summary.json",
        compute_summary_md="runs/summary.md",
        log_path=log_path,
    )

    assert row["event"] == "start"
    assert rebuild_calls == ["rebuild"]
    assert progress_md.with_suffix(".json").exists()
    payload = json.loads(progress_md.with_suffix(".json").read_text(encoding="utf-8"))
    current = payload["rows"][0]
    assert current["queue_status"] == "running_supervision_only"
    assert current["runner_kind"] == "heartbeat_only"
    assert current["concrete_compute_attached"] is False
    assert current["compute_summary_json"] == "runs/summary.json"
    assert current["compute_summary_md"] == "runs/summary.md"


def _seed_running_progress(progress_md: Path) -> Path:
    progress_json = progress_md.with_suffix(".json")
    progress_json.parent.mkdir(parents=True, exist_ok=True)
    progress_json.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "wetlab_broad_screen_antitarget_progress_ready",
                    "row_count": 1,
                    "running_row_count": 1,
                    "resolved_row_count": 0,
                },
                "rows": [
                    {
                        "primary_target_id": "CA IX",
                        "anti_target_id": "CA II",
                        "primary_shard_id": "01_of_20",
                        "queue_status": "running",
                        "active_stage_label": "antitarget_counterscreen_primary_shard",
                        "started_at": "2026-03-30T02:20:00",
                        "updated_at": "2026-03-30T02:20:00",
                        "completed_at": "",
                        "notes": "seed_running",
                        "heartbeat_count": 3,
                        "event_count": 4,
                        "run_attempt": 1,
                        "last_event": "heartbeat",
                        "last_event_at": "2026-03-30T02:20:00",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return progress_json


@pytest.mark.parametrize(
    ("event", "expected_queue_status", "expected_completed_at"),
    [
        ("complete", "result_ready", "2026-03-30T02:34:00"),
        ("hold", "explicit_hold", ""),
    ],
)
def test_antitarget_runtime_event_complete_and_hold_update_state(
    tmp_path: Path,
    monkeypatch,
    event: str,
    expected_queue_status: str,
    expected_completed_at: str,
) -> None:
    progress_md = tmp_path / "progress.md"
    log_path = tmp_path / "events.jsonl"
    monkeypatch.setattr(mod, "DEFAULT_PROGRESS_MD", str(progress_md))
    monkeypatch.setattr(mod, "DEFAULT_LOG_PATH", log_path)

    rebuild_calls: list[str] = []

    def _fake_rebuild(*_: object, **__: object) -> None:
        rebuild_calls.append("rebuild")

    monkeypatch.setattr(mod, "_rebuild_support", _fake_rebuild)
    progress_json = _seed_running_progress(progress_md)

    row = mod.apply_event(
        primary_target_id="CA IX",
        anti_target_id="CA II",
        shard_id="01_of_20",
        event=event,
        python_bin="python3",
        active_stage_label="antitarget_counterscreen_primary_shard",
        started_at="2026-03-30T02:20:00",
        updated_at="2026-03-30T02:34:00",
        completed_at="2026-03-30T02:34:00" if event == "complete" else "",
        notes=f"{event}_manual_review",
        log_path=log_path,
    )

    assert row["event"] == event
    assert row["event_timestamp"] == "2026-03-30T02:34:00"
    assert rebuild_calls == ["rebuild"]
    payload = json.loads(progress_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "wetlab_broad_screen_antitarget_progress_ready"
    assert payload["summary"]["row_count"] == 1
    assert payload["summary"]["running_row_count"] == 0
    assert payload["summary"]["resolved_row_count"] == 1
    current = payload["rows"][0]
    assert current["queue_status"] == expected_queue_status
    assert current["event_count"] == 5
    assert current["run_attempt"] == 1
    assert current["heartbeat_count"] == 3
    assert current["last_event"] == event
    assert current["last_event_at"] == "2026-03-30T02:34:00"
    assert current["notes"] == f"{event}_manual_review"
    assert current["started_at"] == "2026-03-30T02:20:00"
    assert current["updated_at"] == "2026-03-30T02:34:00"
    assert current["completed_at"] == expected_completed_at


def test_antitarget_runtime_event_heartbeat_loop(tmp_path: Path, monkeypatch) -> None:
    progress_md = tmp_path / "progress.md"
    log_path = tmp_path / "events.jsonl"
    monkeypatch.setattr(mod, "DEFAULT_PROGRESS_MD", str(progress_md))
    monkeypatch.setattr(mod, "DEFAULT_LOG_PATH", log_path)

    rebuild_calls: list[str] = []
    sleep_calls: list[float] = []

    def _fake_rebuild(*_: object, **__: object) -> None:
        rebuild_calls.append("rebuild")

    monkeypatch.setattr(mod, "_rebuild_support", _fake_rebuild)
    monkeypatch.setattr(mod.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    result = mod.run_event(
        primary_target_id="CA IX",
        anti_target_id="CA II",
        shard_id="02_of_20",
        event="heartbeat",
        python_bin="python3",
        loop=True,
        interval_sec=1.0,
        max_heartbeats=2,
        active_stage_label="antitarget_counterscreen_primary_shard",
        log_path=log_path,
    )

    assert result["event"] == "heartbeat_loop_complete"
    assert result["pulse_count"] == 2
    assert rebuild_calls == ["rebuild", "rebuild"]
    assert sleep_calls == [1.0]
    payload = progress_md.with_suffix(".json").read_text(encoding="utf-8")
    assert "heartbeat_count" in payload
