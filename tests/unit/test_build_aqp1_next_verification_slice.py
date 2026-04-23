from __future__ import annotations

from tools import build_aqp1_next_verification_slice as mod


def test_build_aqp1_next_verification_slice() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {
                    "candidate_name": "bacopaside II",
                    "proposed_packet_step": "core_binder_01",
                    "recommended_review_bucket": "review_only_first_wave",
                    "source_anchor": "PMID 27474162",
                    "caution": "first wave",
                },
                {
                    "candidate_name": "AqB013",
                    "proposed_packet_step": "core_binder_02",
                    "recommended_review_bucket": "review_only_first_wave",
                    "source_anchor": "PMID 22427546",
                    "caution": "second wave",
                },
            ]
        },
        {
            "rows": [
                {
                    "packet_step": "core_binder_01",
                    "replacement_is_binder": "1",
                    "current_ligand_id": "aqp1_placeholder_binder_01",
                    "review_bucket": "defer_pending_target_specific_evidence",
                    "next_required_action": "manual_curated_search_or_defer",
                    "notes": "binder row",
                },
                {
                    "packet_step": "core_non_binder_01",
                    "replacement_is_binder": "0",
                    "current_ligand_id": "aqp1_placeholder_nonbinder_01",
                    "review_bucket": "review_only_negative_evidence",
                    "next_required_action": "manual_negative_evidence_review",
                    "notes": "negative row",
                },
            ]
        },
    )
    assert payload["summary"]["row_count"] == 3
    assert payload["summary"]["external_candidate_review_count"] == 2
    assert payload["summary"]["negative_slot_review_count"] == 1
    assert payload["rows"][0]["label"] == "bacopaside II"
    assert payload["rows"][-1]["work_item_type"] == "negative_slot_review"
