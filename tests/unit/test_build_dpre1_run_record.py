from __future__ import annotations

import pytest

from tools import build_dpre1_run_record as mod


LAUNCH = {
    "summary": {
        "status": "dpre1_launch_packet_ready",
        "serialized_queue_rank": 3,
        "serialized_run_order": "3_of_5_in_wave2",
        "partner_track_id": "TB_Alliance",
    }
}
GO_NO_GO = {"summary": {"status": "dpre1_go_no_go_card_ready"}}
SUCCESSOR = {"summary": {"target_id": "T. cruzi KRS1"}}


def test_build_dpre1_run_record_defaults_to_blocked_when_dengue_gate_is_closed() -> None:
    payload = mod.build_payload(
        LAUNCH,
        {"summary": {"status": "dpre1_result_review_ready", "dpre1_gate_open": False}},
        SUCCESSOR,
        GO_NO_GO,
    )
    summary = payload["summary"]

    assert summary["status"] == "dpre1_run_record_ready"
    assert summary["execution_state"] == "blocked_on_previous_review"
    assert summary["queue_status_now"] == "blocked_on_previous_review"
    assert summary["successor_gate_open"] is False
    assert summary["successor_gate_state"] == "blocked_until_dpre1_result_ready_or_explicit_hold"


def test_build_dpre1_run_record_opens_tcruzi_krs1_after_result_ready() -> None:
    payload = mod.build_payload(
        LAUNCH,
        {
            "summary": {
                "status": "dpre1_result_review_ready",
                "dpre1_gate_open": True,
                "dpre1_review_state": "ready_to_capture_dpre1_result_review",
            }
        },
        SUCCESSOR,
        GO_NO_GO,
        result_summary={"summary": {"status": "completed", "result_review_ready": True}},
    )
    summary = payload["summary"]

    assert summary["result_summary_detected"] is True
    assert summary["execution_state"] == "result_ready"
    assert summary["queue_status_now"] == "result_ready_for_review"
    assert summary["successor_gate_open"] is True
    assert summary["successor_gate_state"] == "open_for_tcruzi_krs1_execution"
    assert summary["successor_next_queue_state"] == "ready_after_previous_review"


def test_build_dpre1_run_record_rejects_advanced_state_when_gate_is_closed() -> None:
    with pytest.raises(ValueError):
        mod.build_payload(
            LAUNCH,
            {"summary": {"status": "dpre1_result_review_ready", "dpre1_gate_open": False}},
            SUCCESSOR,
            GO_NO_GO,
            run_state="running",
        )
