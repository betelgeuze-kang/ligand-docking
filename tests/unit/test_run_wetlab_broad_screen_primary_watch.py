from __future__ import annotations

from tools import run_wetlab_broad_screen_primary_watch as mod


def test_post_action_scripts_refresh_kinase_retry_policy_templates() -> None:
    assert "tools/build_wetlab_kinase_retry_policy_templates.py" in mod.POST_ACTION_SCRIPTS


def test_run_once_completes_and_autostarts_next(monkeypatch) -> None:
    queue_payload = {
        "rows": [
            {"target_id": "CA IX", "shard_id": "11_of_20", "queue_status": "running", "active_stage_label": "broad_screen_primary_shard_tuned_gate55"},
            {"target_id": "CA IX", "shard_id": "12_of_20", "queue_status": "ready_after_previous_shard"},
        ]
    }
    refreshed_queue = {
        "rows": [
            {"target_id": "CA IX", "shard_id": "11_of_20", "queue_status": "result_ready"},
            {"target_id": "CA IX", "shard_id": "12_of_20", "queue_status": "ready_after_previous_shard"},
        ]
    }
    loads = [queue_payload, {}, {}, refreshed_queue]

    monkeypatch.setattr(mod, "load_json", lambda path: loads.pop(0))
    monkeypatch.setattr(mod, "maybe_load_json", lambda path: None)
    monkeypatch.setattr(mod.state_mod, "build_payload", lambda *args, **kwargs: {
        "summary": {
            "active_target_id": "CA IX",
            "active_shard_id": "11_of_20",
            "watcher_decision": "auto_complete_candidate_summary_ok",
            "compute_pid_path": "runs/compute.pid",
        }
    })
    complete_calls = []
    runner_calls = []
    refresh_calls = []
    written = []

    monkeypatch.setattr(mod, "_complete_running_row", lambda **kwargs: complete_calls.append(kwargs))
    monkeypatch.setattr(mod, "_hold_running_row", lambda **kwargs: None)
    monkeypatch.setattr(mod, "_post_refresh", lambda python_bin: refresh_calls.append(python_bin))
    monkeypatch.setattr(mod.runner_mod, "run", lambda **kwargs: runner_calls.append(kwargs))
    monkeypatch.setattr(mod, "write_artifact", lambda *args, **kwargs: written.append(args[0]))
    monkeypatch.setattr(mod.subprocess, "run", lambda *args, **kwargs: None)

    payload = mod.run_once(
        python_bin="python3",
        execution_queue_json="runs/q.json",
        compound_universe_json="runs/u.json",
        portfolio_json="runs/p.json",
        target_native_csv="config/t.csv",
        auto_start_next=True,
    )

    assert complete_calls and complete_calls[0]["compute_pid_path"] == "runs/compute.pid"
    assert runner_calls and runner_calls[0]["target_id"] == "CA IX" and runner_calls[0]["shard_id"] == "12_of_20"
    assert payload["summary"]["action_taken"] == "completed_from_summary+autostart_next"


def test_run_once_holds_on_pid_exit_without_autostart_when_no_ready_row(monkeypatch) -> None:
    queue_payload = {
        "rows": [
            {"target_id": "CA IX", "shard_id": "11_of_20", "queue_status": "running", "active_stage_label": "broad_screen_primary_shard"},
        ]
    }
    refreshed_queue = {
        "rows": [
            {"target_id": "CA IX", "shard_id": "11_of_20", "queue_status": "explicit_hold"},
        ]
    }
    loads = [queue_payload, {}, {}, refreshed_queue]

    monkeypatch.setattr(mod, "load_json", lambda path: loads.pop(0))
    monkeypatch.setattr(mod, "maybe_load_json", lambda path: None)
    monkeypatch.setattr(mod.state_mod, "build_payload", lambda *args, **kwargs: {
        "summary": {
            "active_target_id": "CA IX",
            "active_shard_id": "11_of_20",
            "watcher_decision": "auto_hold_candidate_pid_exited_no_summary",
            "compute_pid_path": "runs/compute.pid",
        }
    })
    hold_calls = []
    monkeypatch.setattr(mod, "_complete_running_row", lambda **kwargs: None)
    monkeypatch.setattr(mod, "_hold_running_row", lambda **kwargs: hold_calls.append(kwargs))
    monkeypatch.setattr(mod, "_post_refresh", lambda python_bin: None)
    monkeypatch.setattr(mod.runner_mod, "run", lambda **kwargs: (_ for _ in ()).throw(AssertionError("runner should not start")))
    monkeypatch.setattr(mod, "write_artifact", lambda *args, **kwargs: None)
    monkeypatch.setattr(mod.subprocess, "run", lambda *args, **kwargs: None)

    payload = mod.run_once(
        python_bin="python3",
        execution_queue_json="runs/q.json",
        compound_universe_json="runs/u.json",
        portfolio_json="runs/p.json",
        target_native_csv="config/t.csv",
        auto_start_next=True,
    )

    assert hold_calls and hold_calls[0]["compute_pid_path"] == "runs/compute.pid"
    assert payload["summary"]["action_taken"] == "held_from_watcher"


def test_run_once_blocks_autostart_after_consecutive_auto_holds(monkeypatch) -> None:
    queue_payload = {
        "rows": [
            {"queue_rank": 1, "target_id": "SARS-CoV-2 Mpro", "shard_id": "01_of_20", "queue_status": "explicit_hold", "notes": "auto_hold_from_primary_watcher_runtime_validation_only"},
            {"queue_rank": 2, "target_id": "SARS-CoV-2 Mpro", "shard_id": "02_of_20", "queue_status": "explicit_hold", "notes": "auto_hold_from_primary_watcher_runtime_validation_only"},
            {"queue_rank": 3, "target_id": "SARS-CoV-2 Mpro", "shard_id": "03_of_20", "queue_status": "running", "active_stage_label": "broad_screen_primary_shard"},
            {"queue_rank": 4, "target_id": "SARS-CoV-2 Mpro", "shard_id": "04_of_20", "queue_status": "ready_after_previous_shard"},
        ]
    }
    refreshed_queue = {
        "rows": [
            {"queue_rank": 1, "target_id": "SARS-CoV-2 Mpro", "shard_id": "01_of_20", "queue_status": "explicit_hold", "notes": "auto_hold_from_primary_watcher_runtime_validation_only"},
            {"queue_rank": 2, "target_id": "SARS-CoV-2 Mpro", "shard_id": "02_of_20", "queue_status": "explicit_hold", "notes": "auto_hold_from_primary_watcher_runtime_validation_only"},
            {"queue_rank": 3, "target_id": "SARS-CoV-2 Mpro", "shard_id": "03_of_20", "queue_status": "explicit_hold", "notes": "auto_hold_from_primary_watcher_runtime_validation_only"},
            {"queue_rank": 4, "target_id": "SARS-CoV-2 Mpro", "shard_id": "04_of_20", "queue_status": "ready_after_previous_shard"},
        ]
    }
    loads = [queue_payload, {}, {}, refreshed_queue]

    monkeypatch.setattr(mod, "load_json", lambda path: loads.pop(0))
    monkeypatch.setattr(mod, "maybe_load_json", lambda path: None)
    monkeypatch.setattr(mod.state_mod, "build_payload", lambda *args, **kwargs: {
        "summary": {
            "active_target_id": "SARS-CoV-2 Mpro",
            "active_shard_id": "03_of_20",
            "watcher_decision": "auto_hold_candidate_summary_failed",
            "compute_pid_path": "runs/compute.pid",
        }
    })
    hold_calls = []
    runner_calls = []
    monkeypatch.setattr(mod, "_complete_running_row", lambda **kwargs: None)
    monkeypatch.setattr(mod, "_hold_running_row", lambda **kwargs: hold_calls.append(kwargs))
    monkeypatch.setattr(mod, "_post_refresh", lambda python_bin: None)
    monkeypatch.setattr(mod.runner_mod, "run", lambda **kwargs: runner_calls.append(kwargs))
    monkeypatch.setattr(mod, "write_artifact", lambda *args, **kwargs: None)
    monkeypatch.setattr(mod.subprocess, "run", lambda *args, **kwargs: None)

    payload = mod.run_once(
        python_bin="python3",
        execution_queue_json="runs/q.json",
        compound_universe_json="runs/u.json",
        portfolio_json="runs/p.json",
        target_native_csv="config/t.csv",
        auto_start_next=True,
        max_consecutive_auto_holds=3,
    )

    assert hold_calls
    assert not runner_calls
    assert payload["summary"]["action_taken"] == "held_from_watcher+guard_stop_target_after_holds"
    assert payload["summary"]["guard_blocked_target_id"] == "SARS-CoV-2 Mpro"
    assert payload["summary"]["guard_hold_streak"] == 3


def test_run_once_hard_freezes_default_autostart_after_stk17b_exploratory_success(monkeypatch) -> None:
    queue_payload = {
        "rows": [
            {"queue_rank": 1, "target_id": "STK17B (DRAK2)", "shard_id": "17_of_20", "queue_status": "running", "active_stage_label": "broad_screen_primary_shard_tuned_gate45", "notes": "throughput_preflight_tuned_gate45"},
            {"queue_rank": 2, "target_id": "STK17B (DRAK2)", "shard_id": "18_of_20", "queue_status": "ready_after_previous_shard"},
        ]
    }
    refreshed_queue = {
        "rows": [
            {"queue_rank": 1, "target_id": "STK17B (DRAK2)", "shard_id": "17_of_20", "queue_status": "result_ready"},
            {"queue_rank": 2, "target_id": "STK17B (DRAK2)", "shard_id": "18_of_20", "queue_status": "ready_after_previous_shard"},
        ]
    }
    loads = [queue_payload, {}, {}, refreshed_queue]

    monkeypatch.setattr(mod, "load_json", lambda path: loads.pop(0))
    monkeypatch.setattr(mod, "maybe_load_json", lambda path: None)
    monkeypatch.setattr(mod.state_mod, "build_payload", lambda *args, **kwargs: {
        "summary": {
            "active_target_id": "STK17B (DRAK2)",
            "active_shard_id": "17_of_20",
            "watcher_decision": "auto_complete_candidate_summary_ok",
            "compute_pid_path": "runs/compute.pid",
        }
    })
    monkeypatch.setattr(
        mod.state_mod,
        "detect_exploratory_hard_freeze",
        lambda payload: {
            "target_id": "STK17B (DRAK2)",
            "success_shard_id": "17_of_20",
            "blocked_shard_id": "18_of_20",
            "reason": "Default auto-start is frozen for STK17B follow-up shard 18_of_20.",
        },
    )
    complete_calls = []
    runner_calls = []
    monkeypatch.setattr(mod, "_complete_running_row", lambda **kwargs: complete_calls.append(kwargs))
    monkeypatch.setattr(mod, "_hold_running_row", lambda **kwargs: None)
    monkeypatch.setattr(mod, "_post_refresh", lambda python_bin: None)
    monkeypatch.setattr(mod.runner_mod, "run", lambda **kwargs: runner_calls.append(kwargs))
    monkeypatch.setattr(mod, "write_artifact", lambda *args, **kwargs: None)
    monkeypatch.setattr(mod.subprocess, "run", lambda *args, **kwargs: None)

    payload = mod.run_once(
        python_bin="python3",
        execution_queue_json="runs/q.json",
        compound_universe_json="runs/u.json",
        portfolio_json="runs/p.json",
        target_native_csv="config/t.csv",
        auto_start_next=True,
    )

    assert complete_calls
    assert not runner_calls
    assert payload["summary"]["action_taken"] == "completed_from_summary+freeze_after_exploratory_success+hard_freeze_default_autostart"
    assert payload["summary"]["exploratory_hard_freeze_blocked_shard_id"] == "18_of_20"
    assert "Default auto-start is frozen" in payload["summary"]["next_required_step"]


def test_run_once_blocks_default_autostart_on_preset_mismatch_hard_guard(monkeypatch) -> None:
    queue_payload = {
        "rows": [
            {"queue_rank": 1, "target_id": "Cathepsin K", "shard_id": "04_of_20", "queue_status": "running", "active_stage_label": "broad_screen_primary_shard"},
            {"queue_rank": 2, "target_id": "Cathepsin K", "shard_id": "05_of_20", "queue_status": "ready_after_previous_shard"},
        ]
    }
    refreshed_queue = {
        "rows": [
            {"queue_rank": 1, "target_id": "Cathepsin K", "shard_id": "04_of_20", "queue_status": "explicit_hold"},
            {"queue_rank": 2, "target_id": "Cathepsin K", "shard_id": "05_of_20", "queue_status": "ready_after_previous_shard"},
        ]
    }
    loads = [queue_payload, {}, {}, refreshed_queue]

    monkeypatch.setattr(mod, "load_json", lambda path: loads.pop(0))
    monkeypatch.setattr(mod, "maybe_load_json", lambda path: None)
    monkeypatch.setattr(mod.state_mod, "build_payload", lambda *args, **kwargs: {
        "summary": {
            "active_target_id": "Cathepsin K",
            "active_shard_id": "04_of_20",
            "watcher_decision": "auto_hold_candidate_summary_failed",
            "compute_pid_path": "runs/compute.pid",
            "preset_mismatch_hard_guard_active": True,
            "stage2_requested_preset": "kinase_protease",
            "stage2_hinted_families": "default",
            "preset_mismatch_hard_guard_reason": "Requested preset kinase_protease does not match detected target-family hints ['default']; block default-lane auto-start and require a target-specific rescue decision.",
        }
    })
    hold_calls = []
    runner_calls = []
    monkeypatch.setattr(mod, "_complete_running_row", lambda **kwargs: None)
    monkeypatch.setattr(mod, "_hold_running_row", lambda **kwargs: hold_calls.append(kwargs))
    monkeypatch.setattr(mod, "_post_refresh", lambda python_bin: None)
    monkeypatch.setattr(mod.runner_mod, "run", lambda **kwargs: runner_calls.append(kwargs))
    monkeypatch.setattr(mod, "write_artifact", lambda *args, **kwargs: None)
    monkeypatch.setattr(mod.subprocess, "run", lambda *args, **kwargs: None)

    payload = mod.run_once(
        python_bin="python3",
        execution_queue_json="runs/q.json",
        compound_universe_json="runs/u.json",
        portfolio_json="runs/p.json",
        target_native_csv="config/t.csv",
        auto_start_next=True,
    )

    assert hold_calls
    assert not runner_calls
    assert payload["summary"]["action_taken"] == "held_from_watcher+preset_mismatch_hard_guard_block"
    assert payload["summary"]["preset_mismatch_guard_blocked_target_id"] == "Cathepsin K"
    assert payload["summary"]["preset_mismatch_guard_requested_preset"] == "kinase_protease"
    assert payload["summary"]["preset_mismatch_guard_hinted_families"] == "default"
