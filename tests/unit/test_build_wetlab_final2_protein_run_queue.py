from __future__ import annotations

from tools import build_wetlab_final2_protein_run_queue as mod


def test_build_wetlab_final2_protein_run_queue_counts_blocked_states() -> None:
    payload = mod.build_payload(
        {"summary": {"partner_track_id": "SGC_dark_kinase"}},
        {"summary": {"partner_track_id": "DNDi_IPK"}},
        {"summary": {"status": "wetlab_prep_artifact_lane_ready", "serialized_execution_slot_count": 1}},
        {"summary": {"status": "stk17b_run_status_ready", "queue_status_now": "blocked_on_previous_review"}},
        {"summary": {"status": "lbdhodh_result_review_ready", "queue_status_now": "blocked_on_target_content"}},
    )
    summary = payload["summary"]

    assert summary["status"] == "wetlab_final2_protein_run_queue_ready"
    assert summary["queue_target_count"] == 2
    assert summary["blocked_on_previous_review_count"] == 1
    assert summary["blocked_on_target_content_count"] == 1
