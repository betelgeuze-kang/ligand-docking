from __future__ import annotations

import pytest

from tools import build_cathepsin_k_run_record as mod


LAUNCH = {
    "summary": {
        "status": "cathepsin_k_launch_packet_ready",
        "serialized_queue_rank": 1,
        "serialized_run_order": "1_of_5_in_wave2",
        "partner_track_id": "acidic_protease_wave2",
    }
}
GO_NO_GO = {"summary": {"status": "cathepsin_k_go_no_go_card_ready"}}
DENGUE = {"summary": {"target_id": "Dengue NS2B-NS3 protease"}}


def test_build_cathepsin_k_run_record_defaults_to_blocked_when_final2_gate_is_closed() -> None:
    payload = mod.build_payload(
        LAUNCH,
        {"summary": {"status": "cathepsin_k_result_review_ready", "cathepsin_k_gate_open": False}},
        DENGUE,
        GO_NO_GO,
    )
    summary = payload["summary"]

    assert summary["status"] == "cathepsin_k_run_record_ready"
    assert summary["execution_state"] == "blocked_on_previous_review"
    assert summary["queue_status_now"] == "blocked_on_previous_review"
    assert summary["successor_gate_open"] is False
    assert summary["successor_gate_state"] == "blocked_until_cathepsin_k_result_ready_or_explicit_hold"


def test_build_cathepsin_k_run_record_opens_dengue_after_result_ready() -> None:
    payload = mod.build_payload(
        LAUNCH,
        {
            "summary": {
                "status": "cathepsin_k_result_review_ready",
                "cathepsin_k_gate_open": True,
                "cathepsin_k_review_state": "ready_to_capture_cathepsin_k_result_review",
            }
        },
        DENGUE,
        GO_NO_GO,
        result_summary={"summary": {"status": "completed", "result_review_ready": True}},
    )
    summary = payload["summary"]

    assert summary["result_summary_detected"] is True
    assert summary["execution_state"] == "result_ready"
    assert summary["queue_status_now"] == "result_ready_for_review"
    assert summary["successor_gate_open"] is True
    assert summary["successor_gate_state"] == "open_for_dengue_execution"
    assert summary["successor_next_queue_state"] == "ready_after_previous_review"


def test_build_cathepsin_k_run_record_rejects_advanced_state_when_gate_is_closed() -> None:
    with pytest.raises(ValueError):
        mod.build_payload(
            LAUNCH,
            {"summary": {"status": "cathepsin_k_result_review_ready", "cathepsin_k_gate_open": False}},
            DENGUE,
            GO_NO_GO,
            run_state="running",
        )


def test_build_cathepsin_k_run_record_accepts_execution_gate_open_fallback() -> None:
    payload = mod.build_payload(
        LAUNCH,
        {
            "summary": {
                "status": "cathepsin_k_result_review_ready",
                "execution_gate_open": True,
                "cathepsin_k_review_state": "ready_to_capture_cathepsin_k_result_review",
            }
        },
        DENGUE,
        GO_NO_GO,
        live_progress={"summary": {"status": "running", "active_stage_label": "acidic_protease_primary_assay", "started_at": "2026-03-30T00:21:00"}},
    )
    summary = payload["summary"]

    assert summary["upstream_gate_open"] is True
    assert summary["execution_state"] == "running"
    assert summary["queue_status_now"] == "running_active_slot"
