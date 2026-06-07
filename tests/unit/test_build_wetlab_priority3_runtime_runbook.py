from __future__ import annotations

from tools import build_wetlab_priority3_runtime_runbook as mod


def test_build_wetlab_priority3_runtime_runbook() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "status": "wetlab_priority3_protein_run_queue_ready",
                "ready_now_target_count": 1,
                "blocked_on_previous_review_count": 2,
            }
        },
        {
            "summary": {
                "status": "wetlab_priority3_gate_refresh_ready",
                "mpro_execution_state": "ready_to_launch",
                "caix_review_state": "blocked_on_mpro_result_review",
                "tcruzi_execution_state": "blocked_on_previous_review",
            }
        },
    )
    summary = payload["summary"]

    assert summary["status"] == "wetlab_priority3_runtime_runbook_ready"
    assert summary["target_count"] == 3
    assert summary["command_row_count"] == 10
    assert summary["ready_now_target_count"] == 1
    assert summary["blocked_on_previous_review_count"] == 2
    assert payload["rows"][0]["target_id"] == "SARS-CoV-2 Mpro"
    assert "--decision-case" not in payload["rows"][1]["command"]
    assert "--action" not in payload["rows"][1]["command"]
    assert "result_ready_pending_classification" in payload["rows"][1]["expected_effect"]
    assert payload["rows"][4]["target_id"] == "CA IX"
    assert payload["rows"][7]["target_id"] == "T. cruzi PDE"
    assert payload["rows"][-1]["event"] == "reset"


def test_build_wetlab_priority3_runtime_runbook_reports_resolved_handoff() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "status": "wetlab_priority3_protein_run_queue_ready",
                "ready_now_target_count": 0,
                "blocked_on_previous_review_count": 0,
                "running_target_count": 0,
                "resolved_target_count": 3,
            }
        },
        {
            "summary": {
                "status": "wetlab_priority3_gate_refresh_ready",
                "mpro_execution_state": "result_ready",
                "caix_review_state": "caix_result_review_resolved",
                "tcruzi_execution_state": "result_ready",
            }
        },
    )

    assert "partner send-round artifact" in payload["summary"]["next_required_step"]
    assert "explicit R4 confirmation" in payload["summary"]["next_required_step"]
