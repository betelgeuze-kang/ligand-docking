from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

from tools import wetlab_broad_screen_antitarget_watcher_state as mod


class _FixedDateTime(dt.datetime):
    frozen_now = dt.datetime(2026, 4, 1, 22, 0, 0)

    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return cls.frozen_now
        return cls.frozen_now.replace(tzinfo=tz)


def test_inspect_state_marks_dead_recent_pid_for_complete(tmp_path: Path, monkeypatch) -> None:
    pid_file = tmp_path / "loop.pid"
    pid_file.write_text("999999", encoding="utf-8")
    monkeypatch.setattr(mod.dt, "datetime", _FixedDateTime)

    inspection = mod.inspect_state(
        {
            "rows": [
                {
                    "primary_target_id": "CA IX",
                    "anti_target_id": "CA II",
                    "primary_shard_id": "04_of_20",
                    "queue_status": "running",
                    "progress_updated_at": "2026-04-01T21:55:00",
                }
            ]
        },
        pid_file=pid_file,
        stale_minutes=20.0,
    )

    assert inspection["decision"] == "auto_complete"
    assert inspection["recommended_event"] == "complete"
    assert inspection["decision_reason"] == "heartbeat_loop_exited_after_recent_signal"


def test_inspect_state_marks_stale_live_pid_for_hold(tmp_path: Path, monkeypatch) -> None:
    pid_file = tmp_path / "loop.pid"
    pid_file.write_text(str(os.getpid()), encoding="utf-8")
    monkeypatch.setattr(mod.dt, "datetime", _FixedDateTime)

    inspection = mod.inspect_state(
        {
            "rows": [
                {
                    "primary_target_id": "CA IX",
                    "anti_target_id": "CA II",
                    "primary_shard_id": "04_of_20",
                    "queue_status": "running",
                    "progress_updated_at": "2026-04-01T21:20:00",
                }
            ]
        },
        pid_file=pid_file,
        stale_minutes=20.0,
    )

    assert inspection["decision"] == "auto_hold"
    assert inspection["recommended_event"] == "hold"
    assert inspection["decision_reason"] == "heartbeat_loop_alive_but_signal_stale"


def test_inspect_state_auto_completes_supervision_only_row_after_heartbeat_budget(tmp_path: Path, monkeypatch) -> None:
    pid_file = tmp_path / "loop.pid"
    pid_file.write_text(str(os.getpid()), encoding="utf-8")
    monkeypatch.setattr(mod.dt, "datetime", _FixedDateTime)

    inspection = mod.inspect_state(
        {
            "rows": [
                {
                    "primary_target_id": "CA IX",
                    "anti_target_id": "CA II",
                    "primary_shard_id": "04_of_20",
                    "queue_status": "running_supervision_only",
                    "progress_updated_at": "2026-04-01T21:59:00",
                    "runner_kind": "heartbeat_only",
                    "heartbeat_count": 8,
                }
            ]
        },
        pid_file=pid_file,
        stale_minutes=20.0,
        supervision_max_heartbeats=4,
    )

    assert inspection["decision"] == "auto_complete"
    assert inspection["recommended_event"] == "complete"
    assert inspection["decision_reason"] == "supervision_only_heartbeat_budget_consumed"


def test_build_payload_surfaces_active_and_next_ready_rows(tmp_path: Path) -> None:
    inspection = {
        "active_row": {
            "primary_target_id": "CA IX",
            "anti_target_id": "CA II",
            "primary_shard_id": "04_of_20",
            "queue_status": "running",
            "complete_command": "complete-cmd",
            "hold_command": "hold-cmd",
            "reset_command": "reset-cmd",
        },
        "next_ready_row": {
            "primary_target_id": "CA IX",
            "anti_target_id": "CA XII",
            "primary_shard_id": "04_of_20",
            "queue_status": "ready_after_previous_antitarget_resolution",
            "launch_command": "launch-cmd",
        },
        "signal_age_minutes": 4.0,
        "recommended_event": "complete",
        "decision": "auto_complete",
        "decision_reason": "heartbeat_loop_exited_after_recent_signal",
        "pid_status": {"pid_file": str(tmp_path / "loop.pid"), "pid_state": "dead", "pid": 999999},
        "inspected_at": "2026-04-01T22:00:00",
    }

    payload = mod.build_payload(
        {"summary": {"queue_row_count": 2}, "rows": [inspection["active_row"], inspection["next_ready_row"]]},
        inspection,
        log_file=tmp_path / "loop.log",
        last_action="auto_complete",
        auto_start_next=True,
    )

    assert payload["summary"]["status"] == "wetlab_broad_screen_antitarget_watcher_state_ready"
    assert payload["summary"]["last_action"] == "auto_complete"
    assert payload["summary"]["active_primary_target_id"] == "CA IX"
    assert payload["rows"][0]["row_kind"] == "active"
    assert payload["rows"][1]["row_kind"] == "next_ready"


def test_inspect_state_auto_completes_compute_attached_row_from_summary(tmp_path: Path, monkeypatch) -> None:
    summary_json = tmp_path / "throughput_summary.json"
    summary_json.write_text(
        '{"service_result": {"status": "ok", "failed_stage": null}, "failed_stage": null}',
        encoding="utf-8",
    )
    compute_pid = tmp_path / "compute.pid"
    compute_pid.write_text(str(os.getpid()), encoding="utf-8")
    heartbeat_pid = tmp_path / "loop.pid"
    heartbeat_pid.write_text(str(os.getpid()), encoding="utf-8")
    monkeypatch.setattr(mod.dt, "datetime", _FixedDateTime)

    inspection = mod.inspect_state(
        {
            "rows": [
                {
                    "primary_target_id": "CA IX",
                    "anti_target_id": "CA II",
                    "primary_shard_id": "06_of_20",
                    "queue_status": "running",
                    "progress_updated_at": "2026-04-01T21:59:00",
                    "runner_kind": "compute_attached",
                    "compute_pid_path": str(compute_pid),
                    "compute_summary_json": str(summary_json),
                }
            ]
        },
        pid_file=heartbeat_pid,
        stale_minutes=20.0,
    )

    assert inspection["decision"] == "auto_complete_candidate_summary_ok"
    assert inspection["recommended_event"] == "complete"
    assert inspection["throughput_summary_detected"] is True
    assert inspection["throughput_ok"] is True
    assert inspection["compute_pid_alive"] is True


def test_inspect_state_auto_completes_compute_attached_row_when_pid_exited_but_summary_ok(tmp_path: Path, monkeypatch) -> None:
    summary_json = tmp_path / "throughput_summary.json"
    summary_json.write_text(
        '{"service_result": {"status": "ok", "failed_stage": null}, "failed_stage": null}',
        encoding="utf-8",
    )
    compute_pid = tmp_path / "compute.pid"
    compute_pid.write_text("999999", encoding="utf-8")
    heartbeat_pid = tmp_path / "loop.pid"
    heartbeat_pid.write_text(str(os.getpid()), encoding="utf-8")
    monkeypatch.setattr(mod.dt, "datetime", _FixedDateTime)

    inspection = mod.inspect_state(
        {
            "rows": [
                {
                    "primary_target_id": "CA IX",
                    "anti_target_id": "CA II",
                    "primary_shard_id": "06_of_20",
                    "queue_status": "running",
                    "progress_updated_at": "2026-04-01T21:59:00",
                    "runner_kind": "compute_attached",
                    "compute_pid_path": str(compute_pid),
                    "compute_summary_json": str(summary_json),
                }
            ]
        },
        pid_file=heartbeat_pid,
        stale_minutes=20.0,
    )

    assert inspection["decision"] == "auto_complete_candidate_summary_ok"
    assert inspection["recommended_event"] == "complete"
    assert inspection["decision_reason"] == "compute_pid_exited_summary_ok"
    assert inspection["throughput_summary_detected"] is True
    assert inspection["throughput_ok"] is True
    assert inspection["compute_pid_alive"] is False


def test_inspect_state_auto_holds_compute_attached_row_when_pid_exited_and_summary_failed(tmp_path: Path, monkeypatch) -> None:
    summary_json = tmp_path / "throughput_summary.json"
    summary_json.write_text(
        '{"service_result": {"status": "error", "error_code": "HTVS_GATE_FAILED", "failed_stage": "stage6_operational_gate"}, "failed_stage": "stage6_operational_gate"}',
        encoding="utf-8",
    )
    compute_pid = tmp_path / "compute.pid"
    compute_pid.write_text("999999", encoding="utf-8")
    heartbeat_pid = tmp_path / "loop.pid"
    heartbeat_pid.write_text(str(os.getpid()), encoding="utf-8")
    monkeypatch.setattr(mod.dt, "datetime", _FixedDateTime)

    inspection = mod.inspect_state(
        {
            "rows": [
                {
                    "primary_target_id": "CA IX",
                    "anti_target_id": "CA II",
                    "primary_shard_id": "06_of_20",
                    "queue_status": "running",
                    "progress_updated_at": "2026-04-01T21:59:00",
                    "runner_kind": "compute_attached",
                    "compute_pid_path": str(compute_pid),
                    "compute_summary_json": str(summary_json),
                }
            ]
        },
        pid_file=heartbeat_pid,
        stale_minutes=20.0,
    )

    assert inspection["decision"] == "auto_hold_candidate_summary_failed"
    assert inspection["recommended_event"] == "hold"
    assert inspection["decision_reason"] == "compute_pid_exited_summary_failed"
    assert inspection["throughput_summary_detected"] is True
    assert inspection["throughput_failed"] is True
    assert inspection["compute_pid_alive"] is False
