from __future__ import annotations

from tools import build_cathepsin_k_result_review as mod


LAUNCH = {
    "summary": {
        "status": "cathepsin_k_launch_packet_ready",
        "serialized_queue_rank": 1,
        "serialized_run_order": "1_of_5_after_final2",
        "partner_track_id": "acidic_protease_wave2",
        "execution_goal": "Open Wave 2 with a Cathepsin K packet.",
        "blocking_rule": "Do not start Dengue until Cathepsin K resolves.",
        "launch_readiness": "ready_for_serialized_execution",
    }
}
DENGUE = {"summary": {"target_id": "Dengue NS2B-NS3 protease"}}


def test_build_cathepsin_k_result_review_blocks_without_final2_release() -> None:
    payload = mod.build_payload({}, LAUNCH, DENGUE)
    summary = payload["summary"]

    assert summary["status"] == "cathepsin_k_result_review_ready"
    assert summary["upstream_gate_open"] is False
    assert summary["content_ready"] is True
    assert summary["cathepsin_k_review_state"] == "blocked_on_final2_final_review"
    assert summary["queue_status_now"] == "blocked_on_previous_review"
    assert summary["successor_gate_open"] is False


def test_build_cathepsin_k_result_review_opens_dengue_when_run_record_is_result_ready() -> None:
    payload = mod.build_payload(
        {"summary": {"status": "lbdhodh_result_review_ready", "final_release_blocked": False}},
        LAUNCH,
        DENGUE,
        {"summary": {"execution_state": "result_ready", "run_started": True, "result_review_ready": True}},
    )
    summary = payload["summary"]

    assert summary["upstream_gate_open"] is True
    assert summary["content_ready"] is True
    assert summary["cathepsin_k_review_state"] == "cathepsin_k_result_review_resolved"
    assert summary["queue_status_now"] == "result_ready_for_successor"
    assert summary["successor_gate_open"] is True
    assert summary["successor_gate_state"] == "open_for_dengue_execution"
    assert summary["dengue_next_queue_state"] == "ready_after_previous_review"
