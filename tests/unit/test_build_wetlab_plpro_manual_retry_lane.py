from __future__ import annotations

from tools.wetlab import build_wetlab_plpro_manual_retry_lane as mod


def test_build_wetlab_plpro_manual_retry_lane_prefers_tuned_gate55_when_bridge_requests_gate_relaxation() -> None:
    hold_guard = {
        "summary": {"status": "wetlab_primary_hold_guard_surface_ready", "guard_limit": 3},
        "rows": [
            {
                "target_id": "SARS-CoV-2 PLpro",
                "guard_triggered_now": True,
                "recent_consecutive_auto_hold_streak": 15,
                "total_auto_hold_count": 15,
            }
        ],
    }
    retry_handoff = {
        "summary": {"status": "wetlab_retry_handoff_summary_ready"},
        "rows": [{"target_id": "SARS-CoV-2 PLpro", "decision": "pause_auto_start"}],
    }
    execution_queue = {
        "summary": {"status": "wetlab_broad_screen_execution_queue_ready"},
        "rows": [
            {
                "target_id": "SARS-CoV-2 PLpro",
                "shard_id": "16_of_20",
                "queue_status": "ready_after_previous_shard",
            }
        ],
    }
    bridge = {
        "summary": {
            "status": "wetlab_broad_screen_throughput_bridge_ready",
            "target_id": "SARS-CoV-2 PLpro",
            "shard_id": "16_of_20",
            "throughput_execute_ready": True,
            "next_required_step": "Use the tuned gate-relaxed throughput preflight command for SARS-CoV-2 PLpro 16_of_20; switch to the matching execute command after preflight passes.",
        },
        "structured": {"preferred_summary_json": "runs/example.json"},
        "rows": [
            {"command_kind": "throughput_preflight_tuned_gate55", "enabled": False, "command": "python3 tools/run_ligand_htvs_pipeline.py ... --dry-run --gate55"},
            {"command_kind": "throughput_execute_tuned_gate55", "enabled": False, "command": "python3 tools/run_ligand_htvs_pipeline.py ... --no-dry-run --gate55"},
            {"command_kind": "throughput_preflight", "enabled": True, "command": "python3 tools/run_ligand_htvs_pipeline.py ..."},
            {"command_kind": "throughput_execute", "enabled": True, "command": "python3 tools/run_ligand_htvs_pipeline.py ... --no-dry-run"},
        ],
    }

    payload = mod.build_payload(hold_guard, retry_handoff, execution_queue, bridge)
    summary = payload["summary"]
    assert summary["status"] == "wetlab_plpro_manual_retry_lane_ready"
    assert summary["target_id"] == "SARS-CoV-2 PLpro"
    assert summary["shard_id"] == "16_of_20"
    assert summary["recommended_retry_mode"] == "guarded_manual_preflight_retry"
    assert summary["selected_command_kind"] == "throughput_preflight_tuned_gate55"
    assert summary["ready_for_manual_retry"] is True
    runner_row = next(row for row in payload["rows"] if row["row_kind"] == "runner_command")
    assert "run_wetlab_plpro_manual_retry.py" in runner_row["command"]
