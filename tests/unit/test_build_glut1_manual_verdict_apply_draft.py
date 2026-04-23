from __future__ import annotations

from tools import build_glut1_manual_verdict_apply_draft as mod


def test_build_glut1_manual_verdict_apply_draft_prefills_draft_only() -> None:
    payload = mod.build_payload(
        {
            "sheet_rows": [
                {
                    "priority_rank": "1",
                    "target_id": "GLUT1",
                    "packet_step": "core_binder_01",
                    "candidate_name": "cytochalasin B",
                    "source_anchor": "PMID 27078104",
                    "source_url": "https://pubmed.ncbi.nlm.nih.gov/27078104/",
                    "current_recommended_verdict": "keep_review_only",
                    "suggested_manual_verdict": "keep_review_only",
                    "suggested_manual_confidence_update": "strong_structural",
                    "suggested_manual_decision_note": "Suggested hold.",
                    "manual_verdict_update": "",
                    "manual_confidence_update": "",
                    "manual_decision_note": "",
                    "next_required_action": "manual_curated_search_or_defer",
                    "promotion_blocker": "no_local_glut1_binder_evidence_curated",
                }
            ]
        }
    )
    row = payload["draft_rows"][0]
    assert payload["summary"]["binder_slot_count"] == 1
    assert payload["summary"]["draft_prefilled_count"] == 1
    assert payload["summary"]["authoritative_manual_fields_touched_count"] == 0
    assert row["draft_manual_verdict_update"] == "keep_review_only"
    assert row["authoritative_manual_verdict_update"] == ""
    assert row["draft_update_status"] == "needs_manual_review"


def test_build_glut1_manual_verdict_apply_draft_preserves_authoritative_inputs() -> None:
    payload = mod.build_payload(
        {
            "sheet_rows": [
                {
                    "priority_rank": "2",
                    "packet_step": "core_binder_02",
                    "candidate_name": "WZB117",
                    "suggested_manual_verdict": "keep_review_only",
                    "suggested_manual_confidence_update": "moderate_functional",
                    "suggested_manual_decision_note": "Suggested hold.",
                    "manual_verdict_update": "keep_review_only",
                    "manual_confidence_update": "moderate_functional",
                    "manual_decision_note": "Reviewer confirmed hold.",
                }
            ]
        }
    )
    row = payload["draft_rows"][0]
    assert payload["summary"]["authoritative_manual_fields_touched_count"] == 1
    assert row["authoritative_manual_fields_touched"] == "yes"
    assert row["draft_update_status"] == "authoritative_manual_input_present"
    assert row["authoritative_manual_decision_note"] == "Reviewer confirmed hold."
