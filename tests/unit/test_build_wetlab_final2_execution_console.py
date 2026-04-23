from __future__ import annotations

from tools import build_wetlab_final2_execution_console as mod


def test_build_wetlab_final2_execution_console() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "status": "wetlab_final2_protein_run_queue_ready",
                "queue_target_count": 2,
                "ready_now_target_count": 0,
                "blocked_on_previous_review_count": 1,
                "blocked_on_target_content_count": 1,
                "running_target_count": 0,
                "resolved_target_count": 0,
            },
            "rows": [
                {
                    "queue_order": 1,
                    "target_id": "STK17B (DRAK2)",
                    "launch_packet_artifact": "runs/stk17b_launch_packet_current.md",
                    "transition_artifact": "runs/stk17b_run_status_current.md",
                    "partner_track_id": "SGC_dark_kinase",
                    "transition_status": "stk17b_run_status_ready",
                    "queue_status": "blocked_on_previous_review",
                    "advance_gate": "STK17B result opens LbDHODH review",
                    "parallel_lane_artifact": "runs/wetlab_prep_artifact_lane_current.md",
                }
            ],
        },
        {"summary": {"status": "wetlab_final2_gate_refresh_ready", "step_count": 7}},
        {"summary": {"status": "wetlab_final2_runtime_event_applied", "target_id": "STK17B (DRAK2)", "event": "reset", "queue_status_now": "blocked_on_previous_review"}},
        {"summary": {"status": "wetlab_final2_runtime_runbook_ready", "command_row_count": 7}},
        [
            {
                "target_id": "STK17B (DRAK2)",
                "event": "reset",
                "event_timestamp": "2026-03-29T20:00:00",
                "queue_status_now": "blocked_on_previous_review",
                "gate_status": "stk17b_run_status_ready",
            }
        ],
    )
    summary = payload["summary"]

    assert summary["status"] == "wetlab_final2_execution_console_ready"
    assert summary["queue_target_count"] == 2
    assert summary["recent_runtime_event_count"] == 1
    assert summary["last_runtime_target"] == "STK17B (DRAK2)"
    assert payload["rows"][0]["console_role"] == "serialized_queue_status"
    assert payload["rows"][-1]["console_role"] == "recent_runtime_event"
