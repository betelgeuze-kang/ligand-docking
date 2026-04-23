from __future__ import annotations

import json
from pathlib import Path

from tools import watch_wetlab_broad_screen_primary as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _watcher_paths(tmp_path: Path) -> dict[str, Path]:
    return {
        "queue": tmp_path / "runs/wetlab_broad_screen_execution_queue_current.json",
        "progress": tmp_path / "runs/wetlab_broad_screen_progress_current.json",
        "bridge": tmp_path / "runs/wetlab_broad_screen_throughput_bridge_current.json",
        "state": tmp_path / "runs/wetlab_broad_screen_primary_watcher_state_current.json",
        "artifact": tmp_path / "runs/wetlab_broad_screen_primary_watcher_current.md",
        "runtime_dir": tmp_path / "runs/wetlab_broad_screen_primary_watcher_runtime",
        "throughput_dir": tmp_path / "runs/wetlab_broad_screen_throughput/ca_ix/11_of_20",
    }


def test_watcher_detects_summary_completion_and_auto_completes(monkeypatch, tmp_path: Path) -> None:
    paths = _watcher_paths(tmp_path)
    _write_json(
        paths["queue"],
        {
            "summary": {
                "first_actionable_target_id": "CA IX",
                "first_actionable_shard_id": "11_of_20",
                "first_actionable_queue_status": "running",
            },
            "rows": [
                {"target_id": "CA IX", "shard_id": "11_of_20", "queue_status": "running"},
                {"target_id": "CA IX", "shard_id": "12_of_20", "queue_status": "blocked_on_previous_shard"},
            ],
        },
    )
    _write_json(
        paths["progress"],
        {
            "rows": [
                {
                    "target_id": "CA IX",
                    "shard_id": "11_of_20",
                    "queue_status": "running",
                    "active_stage_label": "broad_screen_primary_shard_tuned_gate55",
                }
            ]
        },
    )
    _write_json(
        paths["bridge"],
        {
            "summary": {"target_id": "CA IX", "shard_id": "11_of_20"},
            "structured": {"out_prefix": str(paths["throughput_dir"] / "throughput_run_gate55")},
            "rows": [
                {
                    "command_kind": "throughput_preflight_tuned_gate55",
                    "enabled": True,
                    "command": "python3 tools/run_ligand_htvs_pipeline.py --dry-run",
                }
            ],
        },
    )
    _write_json(
        paths["state"],
        {
            "managed_run": {
                "target_id": "CA IX",
                "shard_id": "11_of_20",
                "compute_pid": 43210,
                "compute_command_kind": "throughput_preflight_tuned_gate55",
            }
        },
    )
    _write_json(
        paths["throughput_dir"] / "throughput_run_gate55_summary.json",
        {"pass": True, "generated_at_local": "2026-04-01T21:31:14"},
    )

    calls: list[dict[str, str]] = []

    def _fake_run_primary_event(**kwargs):
        calls.append({"event": kwargs["event"], "target_id": kwargs["target_id"], "shard_id": kwargs["shard_id"], "notes": kwargs["notes"]})
        return {"event": kwargs["event"]}

    monkeypatch.setattr(mod, "_run_primary_event", _fake_run_primary_event)

    payload = mod.run_once(
        queue_json=paths["queue"],
        progress_json=paths["progress"],
        throughput_bridge_json=paths["bridge"],
        watcher_state_json=paths["state"],
        out_md=paths["artifact"],
        auto_complete_active=True,
        auto_start_next=False,
        runtime_dir=paths["runtime_dir"],
    )

    assert payload["summary"]["compute_state"] == "summary_complete"
    assert payload["summary"]["compute_summary_present"] is True
    assert len(calls) == 1
    assert calls[0]["event"] == "complete"
    assert calls[0]["target_id"] == "CA IX"
    assert calls[0]["shard_id"] == "11_of_20"
    assert "watcher_auto_complete_from_compute_summary" in calls[0]["notes"]
    assert "throughput_run_gate55_summary.json" in calls[0]["notes"]
    assert "pass=true" in calls[0]["notes"]
    state_payload = json.loads(paths["state"].read_text(encoding="utf-8"))
    assert state_payload["managed_run"] == {}


def test_watcher_detects_pid_exit_without_summary(monkeypatch, tmp_path: Path) -> None:
    paths = _watcher_paths(tmp_path)
    _write_json(
        paths["queue"],
        {
            "summary": {
                "first_actionable_target_id": "CA IX",
                "first_actionable_shard_id": "11_of_20",
                "first_actionable_queue_status": "running",
            },
            "rows": [{"target_id": "CA IX", "shard_id": "11_of_20", "queue_status": "running"}],
        },
    )
    _write_json(
        paths["progress"],
        {
            "rows": [
                {
                    "target_id": "CA IX",
                    "shard_id": "11_of_20",
                    "queue_status": "running",
                    "active_stage_label": "broad_screen_primary_shard_tuned_gate55",
                }
            ]
        },
    )
    _write_json(
        paths["bridge"],
        {
            "summary": {"target_id": "CA IX", "shard_id": "11_of_20"},
            "structured": {"out_prefix": str(paths["throughput_dir"] / "throughput_run_gate55")},
            "rows": [],
        },
    )
    _write_json(
        paths["state"],
        {
            "managed_run": {
                "target_id": "CA IX",
                "shard_id": "11_of_20",
                "compute_pid": 99887,
                "compute_command_kind": "throughput_preflight_tuned_gate55",
                "compute_log_path": str(paths["runtime_dir"] / "ca_ix/11_of_20/throughput_preflight_tuned_gate55.log"),
            }
        },
    )

    monkeypatch.setattr(mod, "_pid_is_running", lambda pid: False)

    payload = mod.run_once(
        queue_json=paths["queue"],
        progress_json=paths["progress"],
        throughput_bridge_json=paths["bridge"],
        watcher_state_json=paths["state"],
        out_md=paths["artifact"],
        runtime_dir=paths["runtime_dir"],
    )

    assert payload["summary"]["compute_state"] == "pid_exited_no_summary"
    assert payload["summary"]["compute_summary_present"] is False
    assert "Compute PID exited for CA IX shard 11_of_20" in payload["summary"]["next_required_step"]


def test_watcher_auto_starts_next_ready_row_with_heartbeat_and_preflight(monkeypatch, tmp_path: Path) -> None:
    paths = _watcher_paths(tmp_path)
    ready_dir = tmp_path / "runs/wetlab_broad_screen_throughput/ca_ix/12_of_20"
    _write_json(
        paths["queue"],
        {
            "summary": {
                "first_actionable_target_id": "CA IX",
                "first_actionable_shard_id": "12_of_20",
                "first_actionable_queue_status": "ready_after_previous_shard",
            },
            "rows": [
                {"target_id": "CA IX", "shard_id": "11_of_20", "queue_status": "result_ready"},
                {"target_id": "CA IX", "shard_id": "12_of_20", "queue_status": "ready_after_previous_shard"},
            ],
        },
    )
    _write_json(paths["progress"], {"rows": [{"target_id": "CA IX", "shard_id": "11_of_20", "queue_status": "result_ready"}]})
    _write_json(
        paths["bridge"],
        {
            "summary": {"target_id": "CA IX", "shard_id": "12_of_20"},
            "structured": {"out_prefix": str(ready_dir / "throughput_run_gate55")},
            "rows": [
                {
                    "command_kind": "throughput_preflight_tuned_gate55",
                    "enabled": True,
                    "command": "python3 tools/run_ligand_htvs_pipeline.py --run-scope full --dry-run",
                },
                {
                    "command_kind": "throughput_preflight",
                    "enabled": True,
                    "command": "python3 tools/run_ligand_htvs_pipeline.py --dry-run",
                },
            ],
        },
    )
    _write_json(paths["state"], {"managed_run": {}})

    start_calls: list[dict[str, str]] = []

    def _fake_run_primary_event(**kwargs):
        start_calls.append({"event": kwargs["event"], "target_id": kwargs["target_id"], "shard_id": kwargs["shard_id"], "active_stage_label": kwargs["active_stage_label"]})
        return {"event": kwargs["event"]}

    monkeypatch.setattr(mod, "_run_primary_event", _fake_run_primary_event)
    monkeypatch.setattr(
        mod,
        "_launch_heartbeat_loop",
        lambda **kwargs: {
            "pid": 32100,
            "pid_file": str(paths["runtime_dir"] / "heartbeat_loop.pid"),
            "log_file": str(paths["runtime_dir"] / "heartbeat_loop.log"),
            "command": "heartbeat",
        },
    )
    monkeypatch.setattr(
        mod,
        "_launch_compute_command",
        lambda **kwargs: {
            "pid": 65400,
            "log_file": str(paths["runtime_dir"] / "ca_ix/12_of_20/throughput_preflight_tuned_gate55.log"),
            "command": kwargs["command"],
        },
    )
    monkeypatch.setattr(mod, "_pid_is_running", lambda pid: pid in {32100, 65400})

    payload = mod.run_once(
        queue_json=paths["queue"],
        progress_json=paths["progress"],
        throughput_bridge_json=paths["bridge"],
        watcher_state_json=paths["state"],
        out_md=paths["artifact"],
        auto_start_next=True,
        runtime_dir=paths["runtime_dir"],
    )

    assert start_calls == [
        {
            "event": "start",
            "target_id": "CA IX",
            "shard_id": "12_of_20",
            "active_stage_label": "broad_screen_primary_shard_tuned_gate55",
        }
    ]
    state_payload = json.loads(paths["state"].read_text(encoding="utf-8"))
    assert state_payload["managed_run"]["target_id"] == "CA IX"
    assert state_payload["managed_run"]["shard_id"] == "12_of_20"
    assert state_payload["managed_run"]["compute_pid"] == 65400
    assert state_payload["managed_run"]["heartbeat_pid"] == 32100
    assert payload["summary"]["managed_compute_command_kind"] == "throughput_preflight_tuned_gate55"
    assert payload["summary"]["actions_taken_count"] == 3
