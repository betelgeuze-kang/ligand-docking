from __future__ import annotations

from tools import build_wetlab_next3_protein_run_queue as mod


def test_build_wetlab_next3_protein_run_queue_defaults_to_all_blocked() -> None:
    payload = mod.build_payload(
        {"summary": {"partner_track_id": "DNDi_IPK"}},
        {"summary": {"partner_track_id": "READDI_Korea"}},
        {"summary": {"partner_track_id": "M4K_open_science"}},
        {"summary": {"status": "wetlab_prep_artifact_lane_ready", "serialized_execution_slot_count": 1}},
        {"summary": {"status": "cruzain_run_status_ready", "queue_status_now": "blocked_on_previous_review"}},
        {"summary": {"status": "sarscov2_plpro_result_review_ready", "queue_status_now": "blocked_on_previous_review"}},
        {"summary": {"status": "alk2_result_review_ready", "queue_status_now": "blocked_on_previous_review"}},
    )
    summary = payload["summary"]

    assert summary["status"] == "wetlab_next3_protein_run_queue_ready"
    assert summary["queue_target_count"] == 3
    assert summary["ready_now_target_count"] == 0
    assert summary["blocked_on_previous_review_count"] == 3
    assert payload["rows"][0]["target_id"] == "Cruzain"


def test_build_wetlab_next3_protein_run_queue_propagates_later_opening() -> None:
    payload = mod.build_payload(
        {"summary": {"partner_track_id": "DNDi_IPK"}},
        {"summary": {"partner_track_id": "READDI_Korea"}},
        {"summary": {"partner_track_id": "M4K_open_science"}},
        {"summary": {"status": "wetlab_prep_artifact_lane_ready", "serialized_execution_slot_count": 1}},
        {"summary": {"status": "cruzain_run_status_ready", "queue_status_now": "result_ready_for_review"}},
        {"summary": {"status": "sarscov2_plpro_result_review_ready", "queue_status_now": "ready_after_previous_review"}},
        {"summary": {"status": "alk2_result_review_ready", "queue_status_now": "blocked_on_previous_review"}},
    )
    summary = payload["summary"]

    assert summary["ready_now_target_count"] == 1
    assert summary["resolved_target_count"] == 1
    assert summary["plpro_queue_status"] == "ready_after_previous_review"
