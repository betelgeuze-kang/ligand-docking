from __future__ import annotations

from tools import build_wetlab_stk17b_manual_retry_lane as mod


def test_build_wetlab_stk17b_manual_retry_lane_prefers_tuned_gate55() -> None:
    hold_guard = {
        "summary": {"status": "wetlab_primary_hold_guard_surface_ready", "guard_limit": 3},
        "rows": [
            {
                "target_id": "STK17B (DRAK2)",
                "guard_triggered_now": True,
                "recent_consecutive_auto_hold_streak": 11,
                "total_auto_hold_count": 11,
            }
        ],
    }
    retry_handoff = {
        "summary": {"status": "wetlab_retry_handoff_summary_ready"},
        "rows": [{"target_id": "STK17B (DRAK2)", "decision": "do_not_autoadvance"}],
    }
    execution_queue = {
        "summary": {"status": "wetlab_broad_screen_execution_queue_ready"},
        "rows": [
            {
                "target_id": "STK17B (DRAK2)",
                "shard_id": "12_of_20",
                "queue_status": "ready_after_previous_shard",
            }
        ],
    }
    bridge = {
        "summary": {
            "status": "wetlab_broad_screen_throughput_bridge_ready",
            "target_id": "STK17B (DRAK2)",
            "shard_id": "12_of_20",
            "throughput_execute_ready": True,
            "next_required_step": "Use the standard throughput preflight command for STK17B (DRAK2) 12_of_20; switch to the matching execute command after preflight passes.",
        },
        "structured": {"preferred_summary_json": "runs/example.json"},
        "rows": [
            {"command_kind": "throughput_preflight_tuned_gate55", "enabled": False, "command": "python3 tools/run_ligand_htvs_pipeline.py ... --dry-run --gate55"},
            {"command_kind": "throughput_execute_tuned_gate55", "enabled": False, "command": "python3 tools/run_ligand_htvs_pipeline.py ... --no-dry-run --gate55"},
            {"command_kind": "throughput_preflight", "enabled": True, "command": "python3 tools/run_ligand_htvs_pipeline.py ..."},
        ],
    }

    payload = mod.build_payload(hold_guard, retry_handoff, execution_queue, bridge)
    summary = payload["summary"]
    assert summary["status"] == "wetlab_stk17b_manual_retry_lane_ready"
    assert summary["target_id"] == "STK17B (DRAK2)"
    assert summary["shard_id"] == "12_of_20"
    assert summary["campaign_start_shard_id"] == "12_of_20"
    assert summary["recommended_retry_mode"] == "guarded_tuned_gate55_manual_retry"
    assert summary["selected_command_kind"] == "throughput_preflight_tuned_gate55"
    assert summary["ready_for_manual_retry"] is True
    runner_row = next(row for row in payload["rows"] if row["row_kind"] == "runner_command")
    assert "run_wetlab_stk17b_manual_retry.py" in runner_row["command"]


def test_build_wetlab_stk17b_manual_retry_lane_preserves_campaign_start_shard() -> None:
    hold_guard = {
        "summary": {"status": "wetlab_primary_hold_guard_surface_ready", "guard_limit": 3},
        "rows": [
            {
                "target_id": "STK17B (DRAK2)",
                "guard_triggered_now": True,
                "recent_consecutive_auto_hold_streak": 12,
                "total_auto_hold_count": 12,
            }
        ],
    }
    retry_handoff = {"summary": {"status": "wetlab_retry_handoff_summary_ready"}, "rows": []}
    execution_queue = {
        "summary": {"status": "wetlab_broad_screen_execution_queue_ready"},
        "rows": [
            {
                "target_id": "STK17B (DRAK2)",
                "shard_id": "13_of_20",
                "queue_status": "ready_after_previous_shard",
            }
        ],
    }
    bridge = {
        "summary": {"status": "wetlab_broad_screen_throughput_bridge_ready", "throughput_execute_ready": True},
        "rows": [
            {"command_kind": "throughput_preflight_tuned_gate55", "enabled": False, "command": "python3 tools/run_ligand_htvs_pipeline.py ... --dry-run --gate55"},
        ],
    }
    previous_lane = {
        "summary": {
            "status": "wetlab_stk17b_manual_retry_lane_ready",
            "target_id": "STK17B (DRAK2)",
            "shard_id": "12_of_20",
            "campaign_start_shard_id": "12_of_20",
        }
    }

    payload = mod.build_payload(hold_guard, retry_handoff, execution_queue, bridge, previous_lane)
    summary = payload["summary"]
    assert summary["shard_id"] == "13_of_20"
    assert summary["campaign_start_shard_id"] == "12_of_20"


def test_build_wetlab_stk17b_manual_retry_lane_infers_campaign_start_from_previous_resolved_shard() -> None:
    hold_guard = {
        "summary": {"status": "wetlab_primary_hold_guard_surface_ready", "guard_limit": 3},
        "rows": [
            {
                "target_id": "STK17B (DRAK2)",
                "guard_triggered_now": True,
                "recent_consecutive_auto_hold_streak": 13,
                "total_auto_hold_count": 13,
            }
        ],
    }
    retry_handoff = {"summary": {"status": "wetlab_retry_handoff_summary_ready"}, "rows": []}
    execution_queue = {
        "summary": {"status": "wetlab_broad_screen_execution_queue_ready"},
        "rows": [
            {"target_id": "STK17B (DRAK2)", "shard_id": "13_of_20", "queue_status": "explicit_hold"},
            {"target_id": "STK17B (DRAK2)", "shard_id": "14_of_20", "queue_status": "ready_after_previous_shard"},
        ],
    }
    bridge = {
        "summary": {"status": "wetlab_broad_screen_throughput_bridge_ready", "throughput_execute_ready": True},
        "rows": [
            {"command_kind": "throughput_preflight_tuned_gate55", "enabled": False, "command": "python3 tools/run_ligand_htvs_pipeline.py ... --dry-run --gate55"},
        ],
    }

    payload = mod.build_payload(hold_guard, retry_handoff, execution_queue, bridge)
    summary = payload["summary"]
    assert summary["shard_id"] == "14_of_20"
    assert summary["campaign_start_shard_id"] == "13_of_20"
