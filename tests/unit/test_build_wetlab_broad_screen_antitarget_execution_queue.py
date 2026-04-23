from __future__ import annotations

import datetime as dt

import pytest

from tools import build_wetlab_broad_screen_antitarget_execution_queue as mod


def test_antitarget_execution_queue_opens_first_gate_ready_row() -> None:
    payload = mod.build_payload(
        antitarget_queue={
            "rows": [
                {
                    "primary_target_id": "CA IX",
                    "anti_target_id": "CA II",
                    "primary_shard_id": "01_of_20",
                    "primary_gate_open": True,
                },
                {
                    "primary_target_id": "CA IX",
                    "anti_target_id": "CA II",
                    "primary_shard_id": "02_of_20",
                    "primary_gate_open": True,
                },
                {
                    "primary_target_id": "SARS-CoV-2 Mpro",
                    "anti_target_id": "host cysteine protease sanity panel",
                    "primary_shard_id": "01_of_20",
                    "primary_gate_open": False,
                },
            ]
        },
        progress_payload=None,
    )
    summary = payload["summary"]
    assert summary["status"] == "wetlab_broad_screen_antitarget_execution_queue_ready"
    assert summary["ready_now_row_count"] == 1
    assert summary["first_actionable_primary_target_id"] == "CA IX"
    assert summary["first_actionable_anti_target_id"] == "CA II"
    assert payload["rows"][0]["queue_status"] == "ready_first_counterscreen"


@pytest.mark.parametrize("resolved_status", ["result_ready", "explicit_hold"])
def test_antitarget_execution_queue_starts_next_row_after_previous_resolution(resolved_status: str) -> None:
    payload = mod.build_payload(
        antitarget_queue={
            "rows": [
                {
                    "primary_target_id": "CA IX",
                    "anti_target_id": "CA II",
                    "primary_shard_id": "01_of_20",
                    "primary_gate_open": True,
                },
                {
                    "primary_target_id": "CA IX",
                    "anti_target_id": "CA II",
                    "primary_shard_id": "02_of_20",
                    "primary_gate_open": True,
                },
            ]
        },
        progress_payload={
            "rows": [
                {
                    "primary_target_id": "CA IX",
                    "anti_target_id": "CA II",
                    "primary_shard_id": "01_of_20",
                    "queue_status": resolved_status,
                }
            ]
        },
    )
    summary = payload["summary"]
    assert summary["status"] == "wetlab_broad_screen_antitarget_execution_queue_ready"
    assert summary["resolved_row_count"] == 1
    assert summary["ready_now_row_count"] == 1
    assert summary["first_actionable_primary_target_id"] == "CA IX"
    assert summary["first_actionable_anti_target_id"] == "CA II"
    assert summary["first_actionable_shard_id"] == "02_of_20"
    assert summary["first_actionable_queue_status"] == "ready_after_previous_antitarget_resolution"
    assert summary["next_required_step"] == "Dispatch CA IX -> CA II shard 02_of_20."
    assert payload["rows"][0]["queue_status"] == resolved_status
    assert payload["rows"][0]["execution_state"] == ("explicit_hold" if resolved_status == "explicit_hold" else "result_ready")
    assert payload["rows"][1]["queue_status"] == "ready_after_previous_antitarget_resolution"
    assert payload["rows"][1]["execution_state"] == "ready_to_launch"
    assert payload["rows"][1]["launch_command"] == (
        'python3 tools/run_wetlab_broad_screen_antitarget_runner.py '
        '--primary-target-id "CA IX" '
        '--anti-target-id "CA II" '
        "--shard-id 02_of_20 --replace-heartbeat"
    )


def test_antitarget_execution_queue_marks_stale_running_for_recovery() -> None:
    payload = mod.build_payload(
        antitarget_queue={
            "rows": [
                {
                    "primary_target_id": "CA IX",
                    "anti_target_id": "CA II",
                    "primary_shard_id": "02_of_20",
                    "primary_gate_open": True,
                }
            ]
        },
        progress_payload={
            "rows": [
                {
                    "primary_target_id": "CA IX",
                    "anti_target_id": "CA II",
                    "primary_shard_id": "02_of_20",
                    "queue_status": "running",
                    "started_at": "2026-03-30T00:00:00",
                    "updated_at": "2026-03-30T00:00:00",
                }
            ]
        },
        stale_minutes=1.0,
    )
    assert payload["summary"]["stale_row_count"] == 1
    assert payload["rows"][0]["queue_status"] == "stale_running_needs_recovery"


def test_antitarget_execution_queue_labels_heartbeat_only_rows_honestly() -> None:
    now_text = dt.datetime.now().isoformat(timespec="seconds")
    payload = mod.build_payload(
        antitarget_queue={
            "rows": [
                {
                    "primary_target_id": "CA IX",
                    "anti_target_id": "CA II",
                    "primary_shard_id": "04_of_20",
                    "primary_gate_open": True,
                }
            ]
        },
        progress_payload={
            "rows": [
                {
                    "primary_target_id": "CA IX",
                    "anti_target_id": "CA II",
                    "primary_shard_id": "04_of_20",
                    "queue_status": "running",
                    "runner_kind": "heartbeat_only",
                    "updated_at": now_text,
                }
            ]
        },
        stale_minutes=100000.0,
    )
    assert payload["summary"]["running_row_count"] == 1
    assert payload["summary"]["supervision_only_running_row_count"] == 1
    assert payload["summary"]["first_actionable_queue_status"] == "running_supervision_only"
    assert payload["rows"][0]["queue_status"] == "running_supervision_only"
    assert payload["rows"][0]["execution_state"] == "watch_only"
    assert payload["rows"][0]["watcher_resolution_hint"] == "watcher_can_auto_complete_after_short_heartbeat_budget"


def test_antitarget_execution_queue_keeps_compute_attached_rows_as_running() -> None:
    now_text = dt.datetime.now().isoformat(timespec="seconds")
    payload = mod.build_payload(
        antitarget_queue={
            "rows": [
                {
                    "primary_target_id": "CA IX",
                    "anti_target_id": "CA II",
                    "primary_shard_id": "04_of_20",
                    "primary_gate_open": True,
                }
            ]
        },
        progress_payload={
            "rows": [
                {
                    "primary_target_id": "CA IX",
                    "anti_target_id": "CA II",
                    "primary_shard_id": "04_of_20",
                    "queue_status": "running",
                    "runner_kind": "compute_attached",
                    "compute_pid": 123,
                    "compute_pid_path": "/tmp/compute.pid",
                    "compute_log_path": "/tmp/compute.log",
                    "compute_summary_json": "/tmp/summary.json",
                    "updated_at": now_text,
                }
            ]
        },
        stale_minutes=100000.0,
    )
    assert payload["summary"]["running_row_count"] == 1
    assert payload["summary"]["supervision_only_running_row_count"] == 0
    assert payload["summary"]["first_actionable_queue_status"] == "running"
    assert payload["rows"][0]["queue_status"] == "running"
    assert payload["rows"][0]["execution_state"] == "running"
    assert payload["rows"][0]["concrete_compute_attached"] is True
    assert payload["rows"][0]["compute_summary_json"] == "/tmp/summary.json"
