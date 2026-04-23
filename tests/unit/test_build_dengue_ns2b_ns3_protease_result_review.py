from __future__ import annotations

from tools import build_dengue_ns2b_ns3_protease_result_review as mod


LAUNCH = {
    "summary": {
        "status": "dengue_ns2b_ns3_protease_launch_packet_ready",
        "serialized_queue_rank": 2,
        "serialized_run_order": "2_of_5_in_wave2",
        "partner_track_id": "IPK_dengue",
        "execution_goal": "Open Wave 2 with a Dengue NS2B-NS3 packet.",
        "blocking_rule": "Do not start DprE1 until Dengue resolves.",
        "launch_readiness": "ready_for_serialized_execution",
    }
}
DPRE1 = {"summary": {"target_id": "DprE1"}}


def test_build_dengue_ns2b_ns3_protease_result_review_blocks_without_cathepsin_resolution() -> None:
    payload = mod.build_payload({}, LAUNCH, DPRE1)
    summary = payload["summary"]

    assert summary["status"] == "dengue_ns2b_ns3_protease_result_review_ready"
    assert summary["upstream_gate_open"] is False
    assert summary["content_ready"] is True
    assert summary["dengue_review_state"] == "blocked_on_cathepsin_k_result_review"
    assert summary["queue_status_now"] == "blocked_on_previous_review"
    assert summary["successor_gate_open"] is False


def test_build_dengue_ns2b_ns3_protease_result_review_opens_dpre1_when_run_record_is_result_ready() -> None:
    payload = mod.build_payload(
        {"summary": {"status": "cathepsin_k_result_review_ready", "successor_gate_open": True, "successor_gate_state": "open_for_dengue_execution"}},
        LAUNCH,
        DPRE1,
        {"summary": {"execution_state": "result_ready", "run_started": True, "result_review_ready": True}},
    )
    summary = payload["summary"]

    assert summary["upstream_gate_open"] is True
    assert summary["content_ready"] is True
    assert summary["dengue_review_state"] == "dengue_result_review_resolved"
    assert summary["queue_status_now"] == "result_ready_for_successor"
    assert summary["successor_gate_open"] is True
    assert summary["successor_gate_state"] == "open_for_dpre1_execution"
    assert summary["dpre1_next_queue_state"] == "ready_after_previous_review"
