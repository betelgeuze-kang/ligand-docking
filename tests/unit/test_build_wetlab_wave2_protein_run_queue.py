from __future__ import annotations

from tools import build_wetlab_wave2_protein_run_queue as mod


def test_build_wetlab_wave2_protein_run_queue_stays_blocked_before_final2_resolution() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {"target_id": "Cathepsin K", "wave": "Wave 2", "partner_rail": "acidic protease condition-aware rail", "total_priority_score": 9},
                {"target_id": "DprE1", "wave": "Wave 2", "partner_rail": "TB Alliance / academic TB rail", "total_priority_score": 9},
            ]
        },
        {"summary": {"status": "wetlab_validation_companion_panels_ready"}},
        {"summary": {"status": "lbdhodh_result_review_ready", "final_release_blocked": True}},
    )
    summary = payload["summary"]
    assert summary["status"] == "wetlab_wave2_protein_run_queue_ready"
    assert summary["upstream_final2_gate_open"] is False
    assert summary["blocked_on_previous_review_count"] == 2
    assert payload["rows"][0]["queue_status"] == "blocked_on_previous_review"
    assert payload["rows"][0]["companion_panel"] == "cathepsin-family / acidic-pH specificity panel"
    assert "Cathepsin K becomes the first live Wave 2 slot" in summary["next_required_step"]


def test_build_wetlab_wave2_protein_run_queue_shows_content_block_after_final2_resolution() -> None:
    payload = mod.build_payload(
        {"rows": [{"target_id": "Cathepsin K", "wave": "Wave 2", "partner_rail": "acidic protease condition-aware rail", "total_priority_score": 9}]},
        {"summary": {"status": "wetlab_validation_companion_panels_ready"}},
        {"summary": {"status": "lbdhodh_result_review_ready", "final_release_blocked": False}},
    )
    summary = payload["summary"]
    assert summary["upstream_final2_gate_open"] is True
    assert summary["blocked_on_target_content_count"] == 1
    assert payload["rows"][0]["queue_status"] == "blocked_on_target_content"


def test_build_wetlab_wave2_protein_run_queue_marks_cathepsin_k_as_real_packet() -> None:
    payload = mod.build_payload(
        {"rows": [{"target_id": "Cathepsin K", "wave": "Wave 2", "partner_rail": "acidic protease condition-aware rail", "total_priority_score": 9}]},
        {"summary": {"status": "wetlab_validation_companion_panels_ready"}},
        {"summary": {"status": "lbdhodh_result_review_ready", "final_release_blocked": False, "final_release_gate_status": "open_after_lbdhodh_result_ready"}},
        launch_payloads={"cathepsin_k": {"summary": {"status": "cathepsin_k_launch_packet_ready", "launch_readiness": "blocked_on_compound_fill"}}},
        transition_payloads={"cathepsin_k": {"summary": {"status": "cathepsin_k_result_review_ready", "queue_status_now": "blocked_on_target_content"}}},
    )
    summary = payload["summary"]

    assert summary["missing_target_specific_packet_count"] == 0
    assert summary["placeholder_target_count"] == 0
    assert payload["rows"][0]["placeholder_state"] == "live_target_specific_packet_present"
    assert "compound-fill-backed launch readiness" in summary["next_required_step"]


def test_build_wetlab_wave2_protein_run_queue_marks_tcruzi_krs1_as_real_packet_once_present() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {
                    "target_id": "T. cruzi KRS1",
                    "wave": "Wave 2",
                    "partner_rail": "DNDi Chagas backup rail",
                    "total_priority_score": 8,
                }
            ]
        },
        {"summary": {"status": "wetlab_validation_companion_panels_ready"}},
        {"summary": {"status": "lbdhodh_result_review_ready", "final_release_blocked": False, "final_release_gate_status": "open_after_lbdhodh_result_ready"}},
        launch_payloads={"tcruzi_krs1": {"summary": {"status": "tcruzi_krs1_launch_packet_ready", "launch_readiness": "blocked_on_previous_review"}}},
        transition_payloads={"tcruzi_krs1": {"summary": {"status": "tcruzi_krs1_result_review_ready", "queue_status_now": "blocked_on_previous_review"}}},
    )
    summary = payload["summary"]
    row = payload["rows"][0]

    assert summary["missing_target_specific_packet_count"] == 0
    assert summary["placeholder_target_count"] == 0
    assert row["target_id"] == "T. cruzi KRS1"
    assert row["placeholder_state"] == "live_target_specific_packet_present"
    assert row["transition_status"] == "tcruzi_krs1_result_review_ready"
    assert row["queue_status"] == "blocked_on_previous_review"
    assert row["advance_gate"] == "T. cruzi KRS1 is the active first Wave 2 slot; keep any later Wave 2 release blocked until it reaches result-ready or explicit hold"
