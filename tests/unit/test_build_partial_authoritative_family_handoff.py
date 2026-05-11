from __future__ import annotations

from tools import build_partial_authoritative_family_handoff as mod


def test_build_partial_authoritative_family_handoff_payload() -> None:
    payload = mod.build_payload(
        ca2_readiness_payload={
            "summary": {"ready_row_count": 6, "blocked_row_count": 6},
        },
        ca2_policy_payload={
            "summary": {
                "review_only_rows": 6,
                "defer_rows": 0,
                "next_required_step": "Keep CA2 negative-like rows review-only.",
            }
        },
        ca2_next_slice_payload={
            "summary": {"row_count": 3},
            "rows": [
                {
                    "priority_rank": "4",
                    "packet_step": "core_non_binder_01",
                    "replacement_ligand_id": "acetaminophen",
                    "replacement_is_binder": "0",
                    "assay_type_honesty": "review_only_negative_conflict_with_weak_activity",
                    "next_required_action": "manual_negative_evidence_review",
                    "ready_for_authoritative_apply": "no",
                }
            ],
        },
        ca2_packet_payload={
            "summary": {"workbook_row_count": 12}
        },
        ca2_commit_payload={
            "summary": {
                "conflict_review_row_count": 5,
                "no_direct_negative_source_row_count": 1,
                "authoritative_apply_allowed_count": 0,
            }
        },
        pxr_readiness_payload={
            "summary": {"ready_for_apply_row_count": 8, "blocked_row_count": 6},
        },
        pxr_policy_payload={
            "summary": {
                "review_only_rows": ["nicotinamide", "ibuprofen", "aspirin"],
                "defer_rows": ["acetaminophen", "caffeine", "bexarotene"],
                "policy_line": "Keep ibuprofen review-only and defer the rest.",
            }
        },
        pxr_next_slice_payload={
            "summary": {"row_count": 4},
            "rows": [
                {
                    "priority_rank": "13",
                    "packet_step": "ood_eval_non_binder_02",
                    "replacement_ligand_id": "ibuprofen",
                    "replacement_is_binder": "0",
                    "assay_type_honesty": "activity_upper_bound_only_not_quantitative_nonbinder",
                    "next_required_action": "manual_negative_evidence_review",
                    "ready_for_authoritative_apply": "no",
                },
                {
                    "priority_rank": "10",
                    "packet_step": "ood_fit_binder_01",
                    "replacement_ligand_id": "bexarotene",
                    "replacement_is_binder": "1",
                    "assay_type_honesty": "no_local_target_activity_curated",
                    "next_required_action": "manual_curated_search_or_defer",
                    "ready_for_authoritative_apply": "no",
                },
            ],
        },
        pxr_packet_payload={"summary": {"workbook_row_count": 14, "target": "PXR_NR1I2_BLIND"}},
    )

    assert payload["summary"]["family_count"] == 2
    assert payload["summary"]["ready_row_total"] == 14
    assert payload["summary"]["blocked_row_total"] == 12
    assert payload["summary"]["review_only_row_total"] == 9
    assert payload["summary"]["defer_row_total"] == 3
    assert payload["summary"]["handoff_row_count"] == 3

    families = {row["family"]: row for row in payload["families"]}
    assert families["ca2"]["target"] == "CARBONIC_ANHYDRASE_2_ZN_BLIND"
    assert families["ca2"]["partial_mode"] == "authoritative_partial_rows_only"
    assert families["ca2"]["next_gate"] == "review_only_negative_closure"
    assert families["pxr"]["target"] == "PXR_NR1I2_BLIND"
    assert families["pxr"]["next_gate"] == "review_only_and_defer_policy_lock"

    handoff = {(row["family"], row["packet_step"]): row for row in payload["handoff_rows"]}
    assert handoff[("ca2", "core_non_binder_01")]["handoff_bucket"] == "review_only_negative"
    assert handoff[("pxr", "ood_fit_binder_01")]["handoff_bucket"] == "defer_or_gap"
