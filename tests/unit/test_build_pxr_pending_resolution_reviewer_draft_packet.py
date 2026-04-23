from __future__ import annotations

from tools import build_pxr_pending_resolution_reviewer_draft_packet as mod


def test_build_pxr_pending_resolution_reviewer_draft_packet() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "family": "pxr",
                "target": "PXR_NR1I2_BLIND",
                "review_only_row_count": 1,
                "defer_row_count": 2,
                "binder_gap_count": 0,
                "supportive_binder_review_count": 1,
                "confirmed_binder_quantitative_gap_count": 0,
                "policy_line": "Keep ibuprofen review-only and defer the rest.",
            },
            "rows": [
                {
                    "plan_phase": "first_hour",
                    "priority_rank": 13,
                    "packet_step": "ood_eval_non_binder_02",
                    "ligand": "ibuprofen",
                    "replacement_is_binder": 0,
                    "operator_stance": "review_only_negative",
                    "assay_type_honesty": "activity_upper_bound_only_not_quantitative_nonbinder",
                    "promotion_blocker": "activity_upper_bound_only_not_quantitative_nonbinder",
                    "next_required_action": "manual_negative_evidence_review",
                },
                {
                    "plan_phase": "second_pass",
                    "priority_rank": 10,
                    "packet_step": "ood_fit_binder_01",
                    "ligand": "bexarotene",
                    "replacement_is_binder": 1,
                    "operator_stance": "deferred_supportive_binder_review",
                    "assay_type_honesty": "activity_present_manual_confirmation_required",
                    "promotion_blocker": "activity_present_manual_confirmation_required",
                    "next_required_action": "manual_curated_search_or_defer",
                },
            ],
        },
        {
            "summary": {
                "ready_for_apply_row_count": 8,
                "blocked_row_count": 6,
            }
        },
        {
            "summary": {
                "review_only_row_count": 1,
                "defer_row_count": 2,
                "binder_gap_count": 0,
            }
        },
    )

    summary = payload["summary"]
    assert summary["family"] == "pxr"
    assert summary["reviewer_draft_row_count"] == 2
    assert summary["review_only_row_count"] == 1
    assert summary["defer_row_count"] == 2
    assert summary["binder_gap_count"] == 0
    assert summary["supportive_binder_review_count"] == 1
    assert summary["confirmed_binder_quantitative_gap_count"] == 0
    assert summary["ready_for_apply_row_count"] == 8
    assert summary["blocked_row_count"] == 6

    rows = payload["rows"]
    assert rows[0]["ligand"] == "ibuprofen"
    assert rows[0]["resolution_bias"] == "review_only"
    assert "quantitative binding blank" in rows[0]["explicit_stop_condition"]
    assert rows[1]["ligand"] == "bexarotene"
    assert rows[1]["resolution_bias"] == "defer"
    assert "claim-safe binder evidence" in rows[1]["explicit_stop_condition"].lower()
    assert "pubchem" in rows[1]["draft_note"].lower()
