from __future__ import annotations

from tools.product import build_aqp1_manual_verdict_apply_draft as mod


def test_build_aqp1_manual_verdict_apply_draft() -> None:
    payload = mod.build_payload(
        {
            "sheet_rows": [
                {
                    "priority_rank": "1",
                    "packet_step": "core_binder_01",
                    "candidate_name": "bacopaside II",
                    "source_anchor": "PMID 27474162",
                    "source_url": "https://pubmed.ncbi.nlm.nih.gov/27474162/",
                    "evidence_class": "functional_aqp1_water_channel_inhibitor",
                    "evidence_strength": "medium",
                    "potency_or_signal": "AQP1 water-channel IC50 18 uM in Xenopus oocyte assay",
                    "current_review_bucket": "review_only_first_wave",
                    "promotion_blocker": "no_local_aqp1_binder_evidence_curated",
                    "suggested_manual_verdict": "keep_review_only",
                    "suggested_manual_confidence_update": "medium",
                    "suggested_manual_decision_note": "Suggested hold note",
                    "manual_verdict_update": "",
                    "manual_confidence_update": "",
                    "manual_decision_note": "",
                    "update_status": "pending_manual_verdict",
                    "caution": "Functional only.",
                }
            ]
        },
        {
            "rows": [
                {
                    "candidate_name": "bacopaside II",
                    "mechanism_bucket": "functional_aqp1_water_channel_inhibitor",
                    "assay_surface": "Xenopus oocyte swelling assay",
                    "confidence": "medium",
                    "review_bucket": "review_only_first_wave",
                }
            ]
        },
    )

    assert payload["summary"]["target_id"] == "AQP1"
    assert payload["summary"]["row_count"] == 1
    assert payload["summary"]["draft_prefill_count"] == 1
    assert payload["summary"]["pending_manual_verdict_count"] == 1
    assert payload["summary"]["authoritative_apply_allowed"] is False
    assert payload["rows"][0]["mechanism_bucket"] == "functional_aqp1_water_channel_inhibitor"
    assert payload["rows"][0]["draft_manual_verdict_update"] == "keep_review_only"
    assert payload["rows"][0]["authoritative_apply_allowed"] == "no"


def test_build_aqp1_manual_verdict_apply_draft_appends_exact_human_provenance_note() -> None:
    payload = mod.build_payload(
        {
            "sheet_rows": [
                {
                    "priority_rank": "2",
                    "packet_step": "core_binder_02",
                    "candidate_name": "AqB013",
                    "source_anchor": "PMID 22427546",
                    "source_url": "https://pubmed.ncbi.nlm.nih.gov/22427546/",
                    "evidence_class": "functional_aqp1_antagonist_tool",
                    "evidence_strength": "medium",
                    "potency_or_signal": "20 uM AqB013 blocked cGMP-stimulated AQP1-dependent fluid flux",
                    "current_review_bucket": "review_only_first_wave",
                    "promotion_blocker": "no_local_aqp1_binder_evidence_curated",
                    "suggested_manual_verdict": "keep_review_only",
                    "suggested_manual_confidence_update": "medium",
                    "suggested_manual_decision_note": "Suggested hold note",
                    "manual_verdict_update": "",
                    "manual_confidence_update": "",
                    "manual_decision_note": "",
                    "update_status": "pending_manual_verdict",
                    "caution": "Functional only.",
                }
            ]
        },
        {
            "rows": [
                {
                    "candidate_name": "AqB013",
                    "mechanism_bucket": "functional_aqp1_antagonist_tool",
                    "assay_surface": "Xenopus oocyte swelling assay",
                    "confidence": "medium",
                    "review_bucket": "review_only_first_wave",
                }
            ]
        },
        {
            "rows": [
                {
                    "candidate_name": "AqB013",
                    "public_provenance_status": "exact_human_aqp1_quantitative_activity_present_nonbinding",
                    "public_provenance_signal": "exact_human_activity_present_leave_kcal_blank",
                    "state_change_potential": "medium",
                    "chembl_best_activity_type": "IC50",
                    "chembl_best_activity_value": "20000.0",
                    "chembl_best_activity_units": "nM",
                }
            ]
        },
    )

    assert payload["summary"]["exact_human_provenance_count"] == 1
    row = payload["rows"][0]
    assert row["public_provenance_status"] == "exact_human_aqp1_quantitative_activity_present_nonbinding"
    assert row["reviewer_checklist"] == "confirm_anchor_scope;confirm_exact_human_activity_nonbinding;keep_kcal_blank;record_manual_note"
    assert "20000.0 nM" in row["draft_manual_decision_note"]
