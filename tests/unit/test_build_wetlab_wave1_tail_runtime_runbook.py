from __future__ import annotations

from tools import build_wetlab_wave1_tail_runtime_runbook as mod


def test_build_wetlab_wave1_tail_runtime_runbook() -> None:
    payload = mod.build_payload(
        {"summary": {"status": "wetlab_wave1_tail_protein_run_queue_ready", "ready_now_target_count": 0, "blocked_on_previous_review_count": 2}},
        {"summary": {"status": "wetlab_wave1_tail_gate_refresh_ready", "stk17b_execution_state": "blocked_on_previous_review", "lbdhodh_review_state": "blocked_on_stk17b_result_review"}},
    )
    summary = payload["summary"]

    assert summary["status"] == "wetlab_wave1_tail_runtime_runbook_ready"
    assert summary["target_count"] == 2
    assert summary["command_row_count"] == 7
    assert "STK17B" in payload["rows"][0]["target_id"]
    assert "lbdhodh" in payload["rows"][-1]["command"]
