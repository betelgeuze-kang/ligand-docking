from __future__ import annotations

from tools.product import build_aqp1_binder_review_brief as mod


def test_build_aqp1_binder_review_brief() -> None:
    payload = mod.build_payload(
        {
            "sheet_rows": [
                {
                    "priority_rank": "1",
                    "packet_step": "core_binder_01",
                    "candidate_name": "bacopaside II",
                    "source_anchor": "PMID 27474162",
                    "source_url": "https://pubmed.ncbi.nlm.nih.gov/27474162/",
                    "suggested_manual_verdict": "keep_review_only",
                    "suggested_manual_confidence_update": "medium",
                    "suggested_manual_decision_note": "Suggested hold: keep `bacopaside II` in manual-review only status.",
                    "caution": "not direct binding",
                    "update_status": "pending_manual_verdict",
                }
            ]
        },
        {
            "rows": [
                {
                    "candidate_name": "bacopaside II",
                    "mechanism_bucket": "functional_aqp1_water_channel_inhibitor",
                    "assay_surface": "Xenopus assay",
                }
            ]
        },
    )
    assert payload["summary"]["binder_slot_count"] == 1
    assert payload["summary"]["pending_manual_verdict_count"] == 1
    row = payload["rows"][0]
    assert row["candidate_name"] == "bacopaside II"
    assert row["mechanism_bucket"] == "functional_aqp1_water_channel_inhibitor"
    assert row["confirm_fields"] == "manual_verdict_update, manual_confidence_update, manual_decision_note"
    assert "keep `bacopaside II`" in row["reviewer_copy_note"]


def test_build_aqp1_binder_review_brief_marks_exact_human_provenance() -> None:
    payload = mod.build_payload(
        {
            "sheet_rows": [
                {
                    "priority_rank": "2",
                    "packet_step": "core_binder_02",
                    "candidate_name": "AqB013",
                    "source_anchor": "PMID 22427546",
                    "source_url": "https://pubmed.ncbi.nlm.nih.gov/22427546/",
                    "suggested_manual_verdict": "keep_review_only",
                    "suggested_manual_confidence_update": "medium",
                    "suggested_manual_decision_note": "Suggested hold: keep `AqB013` in manual-review only status.",
                    "caution": "activity is nonbinding",
                    "update_status": "pending_manual_verdict",
                }
            ]
        },
        {
            "rows": [
                {
                    "candidate_name": "AqB013",
                    "mechanism_bucket": "functional_aqp1_antagonist_tool",
                    "assay_surface": "Xenopus oocyte swelling assay",
                }
            ]
        },
        {
            "rows": [
                {
                    "candidate_name": "AqB013",
                    "public_provenance_status": "exact_human_aqp1_quantitative_activity_present_nonbinding",
                    "public_provenance_signal": "exact_human_activity_present_leave_kcal_blank",
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
    assert "exact human AQP1 target-activity provenance" in row["review_focus"]
