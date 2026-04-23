from __future__ import annotations

from tools import build_lbdhodh_result_review as mod


def test_build_lbdhodh_result_review_stays_blocked_without_stk17b_resolution() -> None:
    payload = mod.build_payload({}, {"summary": {"status": "lbdhodh_launch_packet_ready", "launch_readiness": "ready_for_serialized_execution"}})
    summary = payload["summary"]

    assert summary["status"] == "lbdhodh_result_review_ready"
    assert summary["queue_status_now"] == "blocked_on_previous_review"
    assert summary["final_release_blocked"] is True


def test_build_lbdhodh_result_review_blocks_on_compound_fill_even_after_upstream_resolution() -> None:
    payload = mod.build_payload(
        {"summary": {"execution_state": "result_ready"}},
        {"summary": {"status": "lbdhodh_launch_packet_ready", "launch_readiness": "blocked_on_compound_fill"}},
    )
    summary = payload["summary"]

    assert summary["upstream_gate_open"] is True
    assert summary["lbdhodh_gate_open"] is False
    assert summary["content_ready"] is False
    assert summary["queue_status_now"] == "blocked_on_target_content"
    assert summary["lbdhodh_review_state"] == "blocked_on_compound_fill"
