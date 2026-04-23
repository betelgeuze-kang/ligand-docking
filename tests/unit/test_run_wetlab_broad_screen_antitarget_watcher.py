from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

from tools import run_wetlab_broad_screen_antitarget_watcher as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_run_once_auto_holds_stale_active_row(tmp_path: Path, monkeypatch) -> None:
    execution_queue_json = tmp_path / "execution_queue.json"
    out_md = tmp_path / "watcher.md"
    pid_file = tmp_path / "loop.pid"
    log_file = tmp_path / "loop.log"
    pid_file.write_text(str(os.getpid()), encoding="utf-8")
    _write_json(
        execution_queue_json,
        {
            "summary": {"queue_row_count": 1},
            "rows": [
                {
                    "primary_target_id": "CA IX",
                    "anti_target_id": "CA II",
                    "primary_shard_id": "04_of_20",
                    "queue_status": "running",
                    "progress_updated_at": "2026-04-01T20:00:00",
                }
            ],
        },
    )

    monkeypatch.setattr(mod, "_refresh_support", lambda *args, **kwargs: None)

    recorded_events: list[str] = []

    def _fake_run_event(**kwargs):
        recorded_events.append(str(kwargs["event"]))
        _write_json(
            execution_queue_json,
            {
                "summary": {"queue_row_count": 1},
                "rows": [
                    {
                        "primary_target_id": "CA IX",
                        "anti_target_id": "CA II",
                        "primary_shard_id": "04_of_20",
                        "queue_status": "explicit_hold",
                    }
                ],
            },
        )
        return {"event": kwargs["event"]}

    monkeypatch.setattr(mod.runtime_event, "run_event", _fake_run_event)

    payload = mod.run_once(
        python_bin="python3",
        execution_queue_json=str(execution_queue_json),
        out_md=str(out_md),
        pid_file=pid_file,
        log_file=log_file,
        stale_minutes=20.0,
        auto_start_next=False,
        supervision_max_heartbeats=4,
    )

    assert recorded_events == ["hold"]
    assert payload["summary"]["last_action"] == "auto_hold"
    assert out_md.with_suffix(".json").exists()


def test_run_once_auto_completes_and_starts_next_row(tmp_path: Path, monkeypatch) -> None:
    execution_queue_json = tmp_path / "execution_queue.json"
    out_md = tmp_path / "watcher.md"
    pid_file = tmp_path / "loop.pid"
    log_file = tmp_path / "loop.log"
    pid_file.write_text("999999", encoding="utf-8")
    recent_signal = (dt.datetime.now() - dt.timedelta(minutes=1)).isoformat(timespec="seconds")
    _write_json(
        execution_queue_json,
        {
            "summary": {"queue_row_count": 2},
            "rows": [
                {
                    "primary_target_id": "CA IX",
                    "anti_target_id": "CA II",
                    "primary_shard_id": "04_of_20",
                    "queue_status": "running",
                    "progress_updated_at": recent_signal,
                },
                {
                    "primary_target_id": "CA IX",
                    "anti_target_id": "CA XII",
                    "primary_shard_id": "04_of_20",
                    "queue_status": "blocked_on_previous_antitarget_resolution",
                },
            ],
        },
    )

    monkeypatch.setattr(mod, "_refresh_support", lambda *args, **kwargs: None)

    recorded_events: list[str] = []
    launch_calls: list[str] = []

    def _fake_run_event(**kwargs):
        recorded_events.append(str(kwargs["event"]))
        if kwargs["event"] == "complete":
            _write_json(
                execution_queue_json,
                {
                    "summary": {"queue_row_count": 2},
                    "rows": [
                        {
                            "primary_target_id": "CA IX",
                            "anti_target_id": "CA II",
                            "primary_shard_id": "04_of_20",
                            "queue_status": "result_ready",
                        },
                        {
                            "primary_target_id": "CA IX",
                            "anti_target_id": "CA XII",
                            "primary_shard_id": "04_of_20",
                            "queue_status": "ready_first_counterscreen",
                            "launch_command": "launch",
                        },
                    ],
                },
            )
        return {"event": kwargs["event"]}

    def _fake_runner_run(**kwargs):
        launch_calls.append(str(kwargs["anti_target_id"]))
        assert kwargs["replace_heartbeat"] is True
        pid_file.write_text(str(os.getpid()), encoding="utf-8")
        _write_json(
            execution_queue_json,
            {
                "summary": {"queue_row_count": 2},
                "rows": [
                    {
                        "primary_target_id": "CA IX",
                        "anti_target_id": "CA II",
                        "primary_shard_id": "04_of_20",
                        "queue_status": "result_ready",
                    },
                    {
                        "primary_target_id": "CA IX",
                        "anti_target_id": "CA XII",
                        "primary_shard_id": "04_of_20",
                        "queue_status": "running",
                        "runner_kind": "compute_attached",
                        "compute_pid_path": str(tmp_path / "compute.pid"),
                        "progress_updated_at": recent_signal,
                    },
                ],
            },
        )
        return {"summary": {"status": "runner_ready"}}

    monkeypatch.setattr(mod.runtime_event, "run_event", _fake_run_event)
    monkeypatch.setattr(mod.runner_mod, "run", _fake_runner_run)

    payload = mod.run_once(
        python_bin="python3",
        execution_queue_json=str(execution_queue_json),
        out_md=str(out_md),
        pid_file=pid_file,
        log_file=log_file,
        stale_minutes=20.0,
        auto_start_next=True,
        supervision_max_heartbeats=4,
    )

    assert recorded_events == ["complete"]
    assert launch_calls == ["CA XII"]
    assert payload["summary"]["last_action"] == "auto_complete+auto_start_next"
    assert payload["summary"]["active_anti_target_id"] == "CA XII"
