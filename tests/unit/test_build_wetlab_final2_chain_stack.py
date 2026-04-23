from __future__ import annotations

from tools import build_wetlab_final2_chain_stack as mod


def test_build_wetlab_final2_chain_stack_reports_readiness() -> None:
    payload = mod.build_payload(
        {"summary": {"status": "stk17b_render_suite_ready"}},
        {"summary": {"status": "lbdhodh_render_suite_ready"}},
        {"summary": {"status": "stk17b_launch_packet_ready"}},
        {"summary": {"status": "lbdhodh_launch_packet_ready", "launch_readiness": "blocked_on_compound_fill"}},
        {"summary": {"artifact_kind": "run_record", "target_id": "STK17B (DRAK2)", "execution_state": "blocked_on_previous_review"}},
        {"summary": {"artifact_kind": "run_record", "target_id": "Leishmania braziliensis DHODH", "execution_state": "blocked_on_target_content"}},
        {"summary": {"status": "stk17b_run_status_ready", "queue_status_now": "blocked_on_previous_review"}},
        {"summary": {"status": "lbdhodh_result_review_ready", "queue_status_now": "blocked_on_target_content"}},
        {"summary": {"status": "wetlab_final2_protein_run_queue_ready", "blocked_on_previous_review_count": 1}},
        {"summary": {"status": "alk2_result_review_ready", "next_queue_release_blocked": True}},
    )
    summary = payload["summary"]

    assert summary["status"] == "wetlab_final2_chain_stack_ready"
    assert summary["next3_final_review_ready"] is True
    assert summary["stk17b_run_record_ready"] is True
    assert summary["lbdhodh_run_record_ready"] is True
    assert summary["final2_queue_ready"] is True
    assert summary["lbdhodh_content_ready"] is False
    assert summary["stk17b_queue_status"] == "blocked_on_previous_review"
    assert summary["lbdhodh_queue_status"] == "blocked_on_target_content"
    assert summary["stack_gate_states"]["stk17b"]["queue_status"] == "blocked_on_previous_review"
    assert summary["stack_gate_states"]["lbdhodh"]["execution_state"] == "blocked_on_target_content"
    assert summary["lbdhodh_blockers"] == {"upstream_stk17b_result_review": "blocked", "compound_fill": "blocked"}
