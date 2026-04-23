from __future__ import annotations

from tools import build_wetlab_wave1_tail_execution_console as mod


def test_build_wetlab_wave1_tail_execution_console() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "status": "wetlab_wave1_tail_protein_run_queue_ready",
                "queue_target_count": 2,
                "ready_now_target_count": 0,
                "blocked_on_previous_review_count": 2,
                "running_target_count": 0,
                "resolved_target_count": 0,
            },
            "rows": [
                {"queue_order": 1, "target_id": "STK17B (DRAK2)", "launch_packet_artifact": "runs/stk17b_launch_packet_current.md", "transition_artifact": "runs/stk17b_run_status_current.md", "partner_track_id": "SGC_dark_kinase", "transition_status": "stk17b_run_status_ready", "queue_status": "blocked_on_previous_review", "advance_gate": "upstream", "parallel_lane_artifact": "runs/wetlab_prep_artifact_lane_current.md"},
                {"queue_order": 2, "target_id": "Leishmania braziliensis DHODH", "launch_packet_artifact": "runs/lbdhodh_launch_packet_current.md", "transition_artifact": "runs/lbdhodh_result_review_current.md", "partner_track_id": "DNDi_IPK", "transition_status": "lbdhodh_result_review_ready", "queue_status": "blocked_on_previous_review", "advance_gate": "upstream", "parallel_lane_artifact": "runs/wetlab_prep_artifact_lane_current.md"},
            ],
        },
        {"summary": {"status": "wetlab_wave1_tail_gate_refresh_ready", "stk17b_execution_state": "blocked_on_previous_review", "lbdhodh_review_state": "blocked_on_stk17b_result_review"}},
        {"summary": {"status": "wetlab_wave1_tail_runtime_event_applied"}},
        {"summary": {"status": "wetlab_wave1_tail_runtime_runbook_ready"}},
        [
            {"target_id": "STK17B (DRAK2)", "event": "reset", "queue_status_now": "blocked_on_previous_review", "gate_status": "stk17b_run_status_ready", "event_timestamp": "2026-03-29T22:00:00"},
        ],
    )
    summary = payload["summary"]

    assert summary["status"] == "wetlab_wave1_tail_execution_console_ready"
    assert summary["queue_target_count"] == 2
    assert summary["recent_runtime_event_count"] == 1
    assert summary["last_runtime_target"] == "STK17B (DRAK2)"
