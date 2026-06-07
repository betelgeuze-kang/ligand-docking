from __future__ import annotations

from tools.wetlab import build_wetlab_wave1_tail_chain_stack as mod


def test_build_wetlab_wave1_tail_chain_stack_reports_readiness() -> None:
    payload = mod.build_payload(
        {"summary": {"status": "stk17b_render_suite_ready"}},
        {"summary": {"status": "lbdhodh_render_suite_ready"}},
        {"summary": {"status": "stk17b_launch_packet_ready"}},
        {"summary": {"status": "lbdhodh_launch_packet_ready"}},
        {"summary": {"status": "stk17b_run_record_ready", "artifact_kind": "run_record", "target_id": "STK17B (DRAK2)"}},
        {"summary": {"status": "lbdhodh_run_record_ready", "artifact_kind": "run_record", "target_id": "Leishmania braziliensis DHODH"}},
        {"summary": {"status": "stk17b_run_status_ready", "queue_status_now": "blocked_on_previous_review"}},
        {"summary": {"status": "lbdhodh_result_review_ready", "queue_status_now": "blocked_on_previous_review"}},
        {"summary": {"status": "wetlab_wave1_tail_protein_run_queue_ready", "blocked_on_previous_review_count": 2}},
        {"summary": {"status": "alk2_result_review_ready", "next_queue_release_blocked": True, "next_queue_release_gate_status": "next_queue_release_blocked"}},
    )
    summary = payload["summary"]

    assert summary["status"] == "wetlab_wave1_tail_chain_stack_ready"
    assert summary["target_count"] == 2
    assert summary["next3_final_review_ready"] is True
    assert summary["wave1_tail_queue_ready"] is True
    assert summary["stk17b_run_record_ready"] is True
    assert summary["lbdhodh_run_record_ready"] is True


def test_build_wetlab_wave1_tail_chain_stack_propagates_upstream_open() -> None:
    payload = mod.build_payload(
        {},
        {},
        {},
        {},
        {"summary": {"artifact_kind": "run_record", "target_id": "STK17B (DRAK2)"}},
        {"summary": {"artifact_kind": "run_record", "target_id": "Leishmania braziliensis DHODH"}},
        {"summary": {"queue_status_now": "ready_after_previous_review"}},
        {"summary": {"queue_status_now": "blocked_on_previous_review"}},
        {"summary": {"status": "wetlab_wave1_tail_protein_run_queue_ready", "ready_now_target_count": 1}},
        {"summary": {"status": "alk2_result_review_ready", "next_queue_release_blocked": False, "next_queue_release_gate_status": "open_after_alk2_result_ready"}},
    )
    assert payload["summary"]["next3_final_gate_open"] is True
    assert payload["summary"]["ready_now_target_count"] == 1
