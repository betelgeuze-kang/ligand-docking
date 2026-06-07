from __future__ import annotations

from tools.product import build_transporter_manual_verdict_packets as mod


def _contains_tokens(text: str, *tokens: str) -> None:
    lowered = text.lower()
    for token in tokens:
        assert token.lower() in lowered


def test_build_transporter_manual_verdict_packets() -> None:
    payload = mod.build_payload(
        {
            "sheet_rows": [
                {
                    "priority_rank": "1",
                    "packet_step": "core_binder_01",
                    "candidate_name": "bacopaside II",
                    "source_anchor": "PMID 27474162",
                    "suggested_manual_verdict": "keep_review_only",
                    "suggested_manual_confidence_update": "medium",
                    "promotion_blocker": "no_local_aqp1_binder_evidence_curated",
                    "suggested_manual_decision_note": "fallback",
                    "update_status": "pending_manual_verdict",
                    "next_required_action": "manual_curated_search_or_defer",
                }
            ]
        },
        {
            "sheet_rows": [
                {
                    "priority_rank": "1",
                    "packet_step": "core_binder_01",
                    "candidate_name": "cytochalasin B",
                    "source_anchor": "PMID 27078104",
                    "suggested_manual_verdict": "keep_review_only",
                    "suggested_manual_confidence_update": "strong_structural",
                    "promotion_blocker": "no_local_glut1_binder_evidence_curated",
                    "suggested_manual_decision_note": "fallback2",
                    "update_status": "pending_manual_verdict",
                    "next_required_action": "manual_curated_search_or_defer",
                },
                {
                    "priority_rank": "2",
                    "packet_step": "core_binder_02",
                    "candidate_name": "WZB117",
                    "source_anchor": "PMID 22689530",
                    "suggested_manual_verdict": "keep_review_only",
                    "suggested_manual_confidence_update": "moderate_functional",
                    "promotion_blocker": "no_local_glut1_binder_evidence_curated",
                    "suggested_manual_decision_note": "fallback3",
                    "update_status": "pending_manual_verdict",
                    "next_required_action": "manual_curated_search_or_defer",
                },
                {
                    "priority_rank": "3",
                    "packet_step": "core_binder_03",
                    "candidate_name": "STF-31",
                    "source_anchor": "PMID 21813754",
                    "suggested_manual_verdict": "keep_review_only",
                    "suggested_manual_confidence_update": "moderate_functional",
                    "promotion_blocker": "no_local_glut1_binder_evidence_curated",
                    "suggested_manual_decision_note": "fallback4",
                    "update_status": "pending_manual_verdict",
                    "next_required_action": "manual_curated_search_or_defer",
                }
            ]
        },
        {
            "rows": [
                {
                    "target_id": "AQP1",
                    "packet_step": "core_binder_01",
                    "manual_decision_note_template": "AQP1 note",
                },
                {
                    "target_id": "GLUT1",
                    "packet_step": "core_binder_01",
                    "manual_decision_note_template": "GLUT1 note",
                },
                {
                    "target_id": "GLUT1",
                    "packet_step": "core_binder_02",
                    "manual_decision_note_template": "GLUT1 note 2",
                },
                {
                    "target_id": "GLUT1",
                    "packet_step": "core_binder_03",
                    "manual_decision_note_template": "GLUT1 note 3",
                },
            ]
        },
    )

    summary = payload["summary"]
    assert summary["target_count"] == 2
    assert summary["total_binder_slots"] == 4
    assert summary["pending_manual_verdict_count"] == 4
    assert summary["glut1_second_wave_source_confirmation_packet_artifact"] == mod.GLUT1_SOURCE_CONFIRMATION_PACKET_MD
    assert summary["glut1_second_wave_source_confirmation_primary_focus_ligand"] == "cytochalasin B"
    assert summary["glut1_second_wave_source_confirmation_exact_target_pair_functional_ligand"] == "WZB117"
    assert summary["glut1_second_wave_source_confirmation_structured_pair_caveat_ligand"] == "STF-31"
    _contains_tokens(
        summary["next_required_step"],
        "review-only",
        "glut1_second_wave_source_confirmation_packet_current.md",
        "cytochalasin b",
        "wzb117",
        "stf-31",
    )

    aqp1 = payload["target_packets"][0]
    glut1 = payload["target_packets"][1]
    assert aqp1["rows"][0]["manual_decision_note_template"] == "AQP1 note"
    assert aqp1["rows"][0]["source_confirmation_packet_artifact"] == ""
    assert aqp1["rows"][0]["source_confirmation_handoff_lane"] == ""

    assert glut1["source_confirmation_packet_artifact"] == mod.GLUT1_SOURCE_CONFIRMATION_PACKET_MD
    assert glut1["source_confirmation_primary_focus_ligand"] == "cytochalasin B"
    assert glut1["source_confirmation_exact_target_pair_functional_ligand"] == "WZB117"
    assert glut1["source_confirmation_structured_pair_caveat_ligand"] == "STF-31"
    _contains_tokens(
        glut1["next_required_step"],
        "review-only",
        "glut1_second_wave_source_confirmation_packet_current.md",
        "cytochalasin b",
        "wzb117",
        "stf-31",
    )
    assert glut1["rows"][0]["manual_decision_note_template"] == "GLUT1 note"
    assert glut1["rows"][0]["source_confirmation_packet_artifact"] == mod.GLUT1_SOURCE_CONFIRMATION_PACKET_MD
    assert glut1["rows"][0]["source_confirmation_handoff_lane"] == "lead"
    assert "review-only" in glut1["rows"][0]["source_confirmation_review_note"]
    assert glut1["rows"][1]["manual_decision_note_template"] == "GLUT1 note 2"
    assert glut1["rows"][1]["source_confirmation_handoff_lane"] == "exact-target-pair functional lane"
    assert "review-only" in glut1["rows"][1]["source_confirmation_review_note"]
    assert glut1["rows"][2]["manual_decision_note_template"] == "GLUT1 note 3"
    assert glut1["rows"][2]["source_confirmation_handoff_lane"] == "structured-pair caveat"
    assert "review-only" in glut1["rows"][2]["source_confirmation_review_note"]
