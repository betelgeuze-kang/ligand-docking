from __future__ import annotations

from tools import build_wetlab_priority3_execution_console as mod


def test_build_wetlab_priority3_execution_console() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "status": "wetlab_priority3_protein_run_queue_ready",
                "queue_target_count": 3,
                "ready_now_target_count": 1,
                "blocked_on_previous_review_count": 2,
                "running_target_count": 0,
                "resolved_target_count": 0,
            },
            "rows": [
                {
                    "queue_order": 1,
                    "target_id": "SARS-CoV-2 Mpro",
                    "launch_packet_artifact": "runs/sarscov2_mpro_launch_packet_current.md",
                    "transition_artifact": "runs/sarscov2_mpro_run_status_current.md",
                    "partner_track_id": "READDI_Korea",
                    "transition_status": "sarscov2_mpro_run_status_ready",
                    "queue_status": "ready_first",
                    "advance_gate": "Mpro result opens CA IX",
                    "parallel_lane_artifact": "runs/wetlab_prep_artifact_lane_current.md",
                }
            ],
        },
        {
            "summary": {
                "status": "wetlab_priority3_gate_refresh_ready",
                "mpro_execution_state": "ready_to_launch",
                "caix_review_state": "blocked_on_mpro_result_review",
                "tcruzi_execution_state": "blocked_on_previous_review",
            }
        },
        {"summary": {"status": "wetlab_priority3_runtime_event_applied"}},
        {"summary": {"status": "wetlab_priority3_runtime_runbook_ready"}},
        [
            {
                "target_id": "SARS-CoV-2 Mpro",
                "event": "reset",
                "event_timestamp": "2026-03-29T20:00:00",
                "queue_status_now": "ready_first",
                "gate_status": "sarscov2_mpro_run_status_ready",
            }
        ],
    )
    summary = payload["summary"]

    assert summary["status"] == "wetlab_priority3_execution_console_ready"
    assert summary["queue_target_count"] == 3
    assert summary["ready_now_target_count"] == 1
    assert summary["recent_runtime_event_count"] == 1
    assert summary["last_runtime_target"] == "SARS-CoV-2 Mpro"
    assert payload["rows"][0]["console_role"] == "serialized_queue_status"
    assert payload["rows"][-1]["console_role"] == "recent_runtime_event"

