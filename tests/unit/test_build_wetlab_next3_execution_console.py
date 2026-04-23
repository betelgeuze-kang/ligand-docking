from __future__ import annotations

from tools import build_wetlab_next3_execution_console as mod


def test_build_wetlab_next3_execution_console() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "status": "wetlab_next3_protein_run_queue_ready",
                "queue_target_count": 3,
                "ready_now_target_count": 0,
                "blocked_on_previous_review_count": 3,
                "running_target_count": 0,
                "resolved_target_count": 0,
            },
            "rows": [
                {
                    "queue_order": 1,
                    "target_id": "Cruzain",
                    "launch_packet_artifact": "runs/cruzain_launch_packet_current.md",
                    "transition_artifact": "runs/cruzain_run_status_current.md",
                    "partner_track_id": "DNDi_IPK",
                    "transition_status": "cruzain_run_status_ready",
                    "queue_status": "blocked_on_previous_review",
                    "advance_gate": "Cruzain result opens PLpro",
                    "parallel_lane_artifact": "runs/wetlab_prep_artifact_lane_current.md",
                }
            ],
        },
        {
            "summary": {
                "status": "wetlab_next3_gate_refresh_ready",
                "cruzain_execution_state": "blocked_on_previous_review",
                "plpro_review_state": "blocked_on_cruzain_result_review",
                "alk2_execution_state": "blocked_on_previous_review",
            }
        },
        {"summary": {"status": "wetlab_next3_runtime_event_applied"}},
        {"summary": {"status": "wetlab_next3_runtime_runbook_ready"}},
        [
            {
                "target_id": "Cruzain",
                "event": "reset",
                "event_timestamp": "2026-03-29T20:00:00",
                "queue_status_now": "blocked_on_previous_review",
                "gate_status": "cruzain_run_status_ready",
            }
        ],
    )
    summary = payload["summary"]

    assert summary["status"] == "wetlab_next3_execution_console_ready"
    assert summary["queue_target_count"] == 3
    assert summary["recent_runtime_event_count"] == 1
    assert summary["last_runtime_target"] == "Cruzain"
    assert payload["rows"][0]["console_role"] == "serialized_queue_status"
    assert payload["rows"][-1]["console_role"] == "recent_runtime_event"
