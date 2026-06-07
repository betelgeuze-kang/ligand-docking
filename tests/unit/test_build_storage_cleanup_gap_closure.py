from __future__ import annotations

from tools import build_storage_cleanup_gap_closure as mod


def test_storage_cleanup_gap_closure_complete() -> None:
    payload = mod.build_storage_cleanup_gap_closure(
        residual_packet={"summary": {"status": "storage_residual_cleanup_status_ready", "operator_action_candidate_count": 0}},
        completion_gate_packet={"summary": {"status": "cleanup_completion_gate_ready", "cleanup_complete": True, "postcheck_contract_ready": True}},
    )
    summary = payload["summary"]
    assert summary["status"] == "storage_cleanup_gap_closure_complete"
    assert summary["all_gaps_closed"] is True
    assert summary["delete_executed"] is False
