from __future__ import annotations

from tools import build_dpre1_result_review as mod


LAUNCH = {
    "summary": {
        "status": "dpre1_launch_packet_ready",
        "serialized_queue_rank": 3,
        "serialized_run_order": "3_of_5_in_wave2",
        "partner_track_id": "TB_Alliance",
        "blocking_rule": "Do not start DprE1 until Dengue resolves.",
        "launch_readiness": "ready_for_serialized_execution",
    }
}
SUCCESSOR = {"summary": {"target_id": "T. cruzi KRS1"}}


def test_build_dpre1_result_review_blocks_without_dengue_resolution() -> None:
    payload = mod.build_payload({}, LAUNCH, SUCCESSOR)
    summary = payload["summary"]

    assert summary["status"] == "dpre1_result_review_ready"
    assert summary["upstream_gate_open"] is False
    assert summary["content_ready"] is True
    assert summary["dpre1_gate_open"] is False
    assert summary["dpre1_review_state"] == "blocked_on_dengue_result_review"
    assert summary["queue_status_now"] == "blocked_on_previous_review"
    assert summary["successor_gate_open"] is False


def test_build_dpre1_result_review_opens_tcruzi_krs1_when_run_record_is_result_ready() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "status": "dengue_ns2b_ns3_protease_result_review_ready",
                "successor_gate_open": True,
                "successor_gate_state": "open_for_dpre1_execution",
            }
        },
        LAUNCH,
        SUCCESSOR,
        {"summary": {"execution_state": "result_ready", "run_started": True, "result_review_ready": True}},
    )
    summary = payload["summary"]

    assert summary["upstream_gate_open"] is True
    assert summary["content_ready"] is True
    assert summary["dpre1_gate_open"] is True
    assert summary["dpre1_review_state"] == "dpre1_result_review_resolved"
    assert summary["queue_status_now"] == "result_ready_for_successor"
    assert summary["successor_gate_open"] is True
    assert summary["successor_gate_state"] == "open_for_tcruzi_krs1_execution"
    assert summary["tcruzi_krs1_next_queue_state"] == "ready_after_previous_review"
