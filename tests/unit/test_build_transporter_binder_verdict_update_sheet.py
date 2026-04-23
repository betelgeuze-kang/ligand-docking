from __future__ import annotations

from tools import build_transporter_binder_verdict_update_sheet as mod


def test_build_transporter_binder_verdict_update_sheet() -> None:
    payload = mod.build_payload(
        "aqp1",
        {
            "rows": [
                {
                    "priority_rank": 1,
                    "packet_step": "core_binder_01",
                    "current_ligand_id": "aqp1_placeholder_binder_01",
                    "replacement_is_binder": "1",
                    "suggested_external_candidate": "bacopaside II",
                    "suggested_external_review_bucket": "review_only_first_wave",
                    "promotion_blocker": "no_local_aqp1_binder_evidence_curated",
                    "next_required_action": "manual_curated_search_or_defer",
                },
                {
                    "priority_rank": 4,
                    "packet_step": "core_non_binder_01",
                    "current_ligand_id": "aqp1_placeholder_nonbinder_01",
                    "replacement_is_binder": "0",
                },
            ]
        },
        {
            "rows": [
                {
                    "candidate_name": "bacopaside II",
                    "anchor": "PMID 27474162",
                    "source_url": "https://pubmed.ncbi.nlm.nih.gov/27474162/",
                    "mechanism_bucket": "functional_aqp1_water_channel_inhibitor",
                    "confidence": "medium",
                    "review_bucket": "review_only_first_wave",
                    "recommended_verdict": "keep_review_only",
                    "potency_or_signal": "IC50 18 uM",
                    "caution": "note",
                }
            ]
        },
        existing_sheet={},
    )

    assert payload["summary"]["binder_slot_count"] == 1
    assert payload["summary"]["suggested_prefill_count"] == 1
    assert payload["summary"]["pending_manual_verdict_count"] == 1
    row = payload["sheet_rows"][0]
    assert row["candidate_name"] == "bacopaside II"
    assert row["source_anchor"] == "PMID 27474162"
    assert row["current_recommended_verdict"] == "keep_review_only"
    assert row["suggested_manual_verdict"] == "keep_review_only"
    assert row["suggested_manual_confidence_update"] == "medium"
    assert "keep `bacopaside II` in manual-review only status" in row["suggested_manual_decision_note"]
    assert row["update_status"] == "pending_manual_verdict"
