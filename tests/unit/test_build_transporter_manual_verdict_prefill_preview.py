from __future__ import annotations

from tools.product import build_transporter_manual_verdict_prefill_preview as mod


def _contains_tokens(text: str, *tokens: str) -> None:
    lowered = text.lower()
    for token in tokens:
        assert token.lower() in lowered


def test_build_transporter_manual_verdict_prefill_preview() -> None:
    payload = mod.build_payload(
        {
            "sheet_rows": [
                {
                    "target_id": "AQP1",
                    "priority_rank": "1",
                    "packet_step": "core_binder_01",
                    "candidate_name": "bacopaside II",
                    "suggested_manual_verdict": "keep_review_only",
                    "suggested_manual_confidence_update": "medium",
                    "suggested_manual_decision_note": "note",
                    "source_anchor": "PMID 27474162",
                    "update_status": "pending_manual_verdict",
                }
            ]
        },
        {
            "sheet_rows": [
                {
                    "target_id": "GLUT1",
                    "priority_rank": "1",
                    "packet_step": "core_binder_01",
                    "candidate_name": "cytochalasin B",
                    "suggested_manual_verdict": "keep_review_only",
                    "suggested_manual_confidence_update": "strong_structural",
                    "suggested_manual_decision_note": "note",
                    "source_anchor": "PMID 27078104",
                    "update_status": "pending_manual_verdict",
                },
                {
                    "target_id": "GLUT1",
                    "priority_rank": "2",
                    "packet_step": "core_binder_02",
                    "candidate_name": "WZB117",
                    "suggested_manual_verdict": "keep_review_only",
                    "suggested_manual_confidence_update": "moderate_functional",
                    "suggested_manual_decision_note": "note2",
                    "source_anchor": "PMID 22689530",
                    "update_status": "pending_manual_verdict",
                },
                {
                    "target_id": "GLUT1",
                    "priority_rank": "3",
                    "packet_step": "core_binder_03",
                    "candidate_name": "STF-31",
                    "suggested_manual_verdict": "keep_review_only",
                    "suggested_manual_confidence_update": "moderate_functional",
                    "suggested_manual_decision_note": "note3",
                    "source_anchor": "PMID 21813754",
                    "update_status": "pending_manual_verdict",
                }
            ]
        },
    )

    summary = payload["summary"]
    assert summary["preview_row_count"] == 4
    assert summary["aqp1_preview_count"] == 1
    assert summary["glut1_preview_count"] == 3
    assert summary["requires_human_confirm_count"] == 4
    assert summary["glut1_second_wave_source_confirmation_packet_artifact"] == mod.GLUT1_SOURCE_CONFIRMATION_PACKET_MD
    assert summary["glut1_second_wave_source_confirmation_primary_focus_ligand"] == "cytochalasin B"
    assert summary["glut1_second_wave_source_confirmation_exact_target_pair_functional_ligand"] == "WZB117"
    assert summary["glut1_second_wave_source_confirmation_structured_pair_caveat_ligand"] == "STF-31"
    _contains_tokens(
        summary["next_required_step"],
        "reviewer convenience",
        "glut1_second_wave_source_confirmation_packet_current.md",
        "cytochalasin b",
        "wzb117",
        "stf-31",
    )

    assert payload["rows"][0]["requires_human_confirm"] == "yes"
    assert payload["rows"][0]["source_confirmation_packet_artifact"] == ""
    assert payload["rows"][0]["source_confirmation_handoff_lane"] == ""
    assert payload["rows"][0]["source_confirmation_review_note"] == ""

    assert payload["rows"][1]["requires_human_confirm"] == "yes"
    assert payload["rows"][1]["source_confirmation_packet_artifact"] == mod.GLUT1_SOURCE_CONFIRMATION_PACKET_MD
    assert payload["rows"][1]["source_confirmation_handoff_lane"] == "lead"
    assert "review-only" in payload["rows"][1]["source_confirmation_review_note"]
    assert payload["rows"][2]["source_confirmation_packet_artifact"] == mod.GLUT1_SOURCE_CONFIRMATION_PACKET_MD
    assert payload["rows"][2]["source_confirmation_handoff_lane"] == "exact-target-pair functional lane"
    assert "review-only" in payload["rows"][2]["source_confirmation_review_note"]
    assert payload["rows"][3]["source_confirmation_packet_artifact"] == mod.GLUT1_SOURCE_CONFIRMATION_PACKET_MD
    assert payload["rows"][3]["source_confirmation_handoff_lane"] == "structured-pair caveat"
    assert "review-only" in payload["rows"][3]["source_confirmation_review_note"]
