from __future__ import annotations

from tools import run_wetlab_stk17b_exploratory_followup_retry as mod


def test_run_wetlab_stk17b_exploratory_followup_retry_launches_primary_runner(monkeypatch) -> None:
    monkeypatch.setattr(mod, "stop_pid_file", lambda path: 0)
    monkeypatch.setattr(mod, "_archive_existing_followup_artifacts", lambda shard_id: [])
    monkeypatch.setattr(
        mod,
        "load_json",
        lambda path: {
            "summary": {
                "status": "wetlab_stk17b_exploratory_followup_lane_ready",
                "target_id": "STK17B (DRAK2)",
                "shard_id": "18_of_20",
                "followup_shard_ids": "18_of_20;19_of_20;20_of_20",
                "selected_command_kind": "throughput_preflight_tuned_gate45",
                "ready_for_manual_retry": True,
            }
        },
    )
    monkeypatch.setattr(
        mod,
        "maybe_load_json",
        lambda path: {
            "summary": {
                "shard_id": "19_of_20",
                "next_required_step": "Run the STK17B (DRAK2) exploratory gate4.5 follow-up runner for 19_of_20.",
            }
        }
        if path == "runs/wetlab_stk17b_exploratory_followup_lane_current.json"
        else {},
    )
    runner_calls = []
    monkeypatch.setattr(
        mod.primary_runner_mod,
        "run",
        lambda **kwargs: runner_calls.append(kwargs) or {"summary": {"compute_pid": 111, "heartbeat_pid": 222}},
    )
    monkeypatch.setattr(
        mod,
        "_settle_followup_run",
        lambda **kwargs: {
            "settled": True,
            "queue_status": "result_ready",
            "summary_path": "runs/stk17b/18_of_20/throughput_run_gate45_summary.json",
            "summary_payload": {"service_result": {"status": "ok", "error_code": "HTVS_OK"}},
            "watch_action": {"action_taken": "completed_from_summary"},
        },
    )
    monkeypatch.setattr(mod, "write_artifact", lambda *args, **kwargs: None)

    payload = mod.run(
        lane_json="runs/wetlab_stk17b_exploratory_followup_lane_current.json",
        python_bin="python3",
        shard_id="",
        command_kind="",
        execution_queue_json="runs/wetlab_broad_screen_execution_queue_current.json",
        compound_universe_json="runs/wetlab_broad_screen_compound_universe_current.json",
        portfolio_json="runs/wetlab_partner_target_portfolio_current.json",
        target_native_csv="config/real_drug_targets_native_v1.csv",
        interval_sec=30.0,
        replace_heartbeat=True,
        settle_timeout_sec=30.0,
        settle_poll_sec=1.0,
    )

    assert runner_calls
    assert runner_calls[0]["target_id"] == "STK17B (DRAK2)"
    assert runner_calls[0]["shard_id"] == "18_of_20"
    assert runner_calls[0]["command_kind"] == "throughput_preflight_tuned_gate45"
    assert runner_calls[0]["launch_watcher"] is False
    assert payload["summary"]["status"] == "wetlab_stk17b_exploratory_followup_retry_runner_ready"
    assert payload["summary"]["shard_id"] == "18_of_20"
    assert payload["summary"]["settle_action"] == "completed_from_summary"
    assert payload["summary"]["settled_queue_status"] == "result_ready"
    assert payload["summary"]["throughput_status"] == "ok"
    assert payload["summary"]["next_followup_shard_id"] == "19_of_20"
    assert payload["summary"]["canonical_summary_path"].endswith("throughput_run_gate45_summary.json")


def test_run_wetlab_stk17b_exploratory_followup_retry_allows_explicit_followup_shard_when_lane_blocked(monkeypatch) -> None:
    monkeypatch.setattr(mod, "stop_pid_file", lambda path: 0)
    monkeypatch.setattr(mod, "_archive_existing_followup_artifacts", lambda shard_id: [])
    monkeypatch.setattr(
        mod,
        "load_json",
        lambda path: {
            "summary": {
                "status": "wetlab_stk17b_exploratory_followup_lane_blocked",
                "target_id": "STK17B (DRAK2)",
                "shard_id": "",
                "followup_shard_ids": "18_of_20;19_of_20;20_of_20",
                "selected_command_kind": "throughput_preflight_tuned_gate45",
                "ready_for_manual_retry": False,
            }
        },
    )
    monkeypatch.setattr(
        mod,
        "maybe_load_json",
        lambda path: {
            "summary": {
                "shard_id": "20_of_20",
                "next_required_step": "Run the STK17B (DRAK2) exploratory gate4.5 follow-up runner for 20_of_20.",
            }
        }
        if path == "runs/wetlab_stk17b_exploratory_followup_lane_current.json"
        else {},
    )
    runner_calls = []
    monkeypatch.setattr(
        mod.primary_runner_mod,
        "run",
        lambda **kwargs: runner_calls.append(kwargs) or {"summary": {"compute_pid": 333, "heartbeat_pid": 444}},
    )
    monkeypatch.setattr(
        mod,
        "_settle_followup_run",
        lambda **kwargs: {
            "settled": True,
            "queue_status": "explicit_hold",
            "summary_path": "runs/stk17b/19_of_20/throughput_run_gate45_summary.json",
            "summary_payload": {"service_result": {"status": "error", "error_code": "HTVS_GATE_FAILED", "failed_stage": "stage6_operational_gate"}},
            "watch_action": {"action_taken": "held_from_watcher"},
        },
    )
    monkeypatch.setattr(mod, "write_artifact", lambda *args, **kwargs: None)

    payload = mod.run(
        lane_json="runs/wetlab_stk17b_exploratory_followup_lane_current.json",
        python_bin="python3",
        shard_id="19_of_20",
        command_kind="",
        execution_queue_json="runs/wetlab_broad_screen_execution_queue_current.json",
        compound_universe_json="runs/wetlab_broad_screen_compound_universe_current.json",
        portfolio_json="runs/wetlab_partner_target_portfolio_current.json",
        target_native_csv="config/real_drug_targets_native_v1.csv",
        interval_sec=30.0,
        replace_heartbeat=True,
        settle_timeout_sec=30.0,
        settle_poll_sec=1.0,
    )

    assert runner_calls[0]["shard_id"] == "19_of_20"
    assert runner_calls[0]["command_kind"] == "throughput_preflight_tuned_gate45"
    assert runner_calls[0]["launch_watcher"] is False
    assert payload["summary"]["shard_id"] == "19_of_20"
    assert payload["summary"]["settle_action"] == "held_from_watcher"
    assert payload["summary"]["throughput_failed_stage"] == "stage6_operational_gate"
    assert payload["summary"]["next_followup_shard_id"] == "20_of_20"
    assert payload["summary"]["canonical_summary_path"].endswith("throughput_run_gate45_summary.json")
