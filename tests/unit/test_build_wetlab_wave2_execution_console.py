from __future__ import annotations

from tools import build_wetlab_wave2_execution_console as mod


def test_build_wetlab_wave2_execution_console_reports_blocked_state() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "queue_target_count": 5,
                "ready_now_target_count": 0,
                "blocked_on_previous_review_count": 5,
                "blocked_on_target_content_count": 0,
                "running_target_count": 0,
                "resolved_target_count": 0,
                "next_required_step": "Keep Wave 2 behind the LbDHODH final-release gate. Once that gate opens, Cathepsin K becomes the first live Wave 2 slot.",
            },
            "rows": [{"target_id": "Cathepsin K", "queue_status": "blocked_on_previous_review", "transition_status": "missing_transition_surface"}],
        },
        {"summary": {"final2_final_gate_open": False}},
        {"summary": {"target_id": "none", "event": "reset"}},
        {"summary": {"status": "wetlab_wave2_runtime_runbook_ready"}},
        [],
    )
    summary = payload["summary"]
    assert summary["status"] == "wetlab_wave2_execution_console_ready"
    assert summary["final2_final_gate_open"] is False
    assert summary["ready_now_target_count"] == 0
    assert "Cathepsin K becomes the first live Wave 2 slot" in summary["next_required_step"]
