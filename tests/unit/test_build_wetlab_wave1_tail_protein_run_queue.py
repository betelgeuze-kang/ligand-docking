from __future__ import annotations

from tools.wetlab import build_wetlab_wave1_tail_protein_run_queue as mod


def test_build_wetlab_wave1_tail_protein_run_queue_defaults_to_all_blocked() -> None:
    payload = mod.build_payload(
        {"summary": {"status": "stk17b_launch_packet_ready", "partner_track_id": "SGC_dark_kinase"}},
        {"summary": {"status": "lbdhodh_launch_packet_ready", "partner_track_id": "DNDi_IPK"}},
        {"summary": {"status": "wetlab_prep_artifact_lane_ready", "serialized_execution_slot_count": 1}},
        {"summary": {"status": "stk17b_run_status_ready", "queue_status_now": "blocked_on_previous_review"}},
        {"summary": {"status": "lbdhodh_result_review_ready", "queue_status_now": "blocked_on_previous_review"}},
    )
    summary = payload["summary"]

    assert summary["status"] == "wetlab_wave1_tail_protein_run_queue_ready"
    assert summary["queue_target_count"] == 2
    assert summary["blocked_on_previous_review_count"] == 2
    assert summary["ready_now_target_count"] == 0
    assert payload["rows"][0]["target_id"] == "STK17B (DRAK2)"
    assert payload["rows"][1]["target_id"] == "Leishmania braziliensis DHODH"


def test_build_wetlab_wave1_tail_protein_run_queue_propagates_later_opening() -> None:
    payload = mod.build_payload(
        {"summary": {"status": "stk17b_launch_packet_ready", "partner_track_id": "SGC_dark_kinase"}},
        {"summary": {"status": "lbdhodh_launch_packet_ready", "partner_track_id": "DNDi_IPK"}},
        {"summary": {"status": "wetlab_prep_artifact_lane_ready", "serialized_execution_slot_count": 1}},
        {"summary": {"status": "stk17b_run_status_ready", "queue_status_now": "ready_after_previous_review"}},
        {"summary": {"status": "lbdhodh_result_review_ready", "queue_status_now": "blocked_on_previous_review"}},
    )
    summary = payload["summary"]

    assert summary["ready_now_target_count"] == 1
    assert summary["stk17b_queue_status"] == "ready_after_previous_review"
