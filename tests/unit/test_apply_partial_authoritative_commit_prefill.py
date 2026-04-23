from __future__ import annotations

from tools import apply_partial_authoritative_commit_prefill as mod


def test_apply_ca2_prefill_confirms_review_only() -> None:
    rows = [
        {
            "packet_step": "core_non_binder_01",
            "staged_review_bucket": "conflict_review",
            "staged_assay_type_honesty": "review_only_negative_conflict_with_weak_activity",
            "staged_promotion_blocker": "no_quantitative_nonbinder_value_curated",
            "staged_next_required_action": "manual_negative_evidence_review",
            "staged_recommended_resolution": "keep_review_only_until_negative_evidence_is_curated",
            "staged_manual_decision_note": "draft note",
            "manual_decision_note": "",
            "commit_status": "pending_manual_commit",
        }
    ]

    updated_rows, updated = mod.apply_ca2_prefill(rows)

    assert updated == 1
    assert updated_rows[0]["manual_review_bucket"] == "conflict_review"
    assert updated_rows[0]["manual_decision_note"] == "draft note"
    assert updated_rows[0]["commit_status"] == "confirmed_review_only"


def test_apply_pxr_prefill_marks_review_only_and_defer() -> None:
    rows = [
        {
            "packet_step": "ood_eval_non_binder_02",
            "staged_commit_class": "confirm_now",
            "staged_resolution_bias": "review_only",
            "staged_assay_type_honesty": "activity_upper_bound_only_not_quantitative_nonbinder",
            "staged_promotion_blocker": "activity_upper_bound_only_not_quantitative_nonbinder",
            "staged_next_required_action": "manual_negative_evidence_review",
            "staged_commit_note": "review only note",
            "manual_commit_note": "",
        },
        {
            "packet_step": "ood_fit_binder_01",
            "staged_commit_class": "must_remain_deferred",
            "staged_resolution_bias": "defer",
            "staged_assay_type_honesty": "no_local_target_activity_curated",
            "staged_promotion_blocker": "no_local_target_activity_curated",
            "staged_next_required_action": "manual_curated_search_or_defer",
            "staged_commit_note": "defer note",
            "manual_commit_note": "",
        },
    ]

    updated_rows, updated = mod.apply_pxr_prefill(rows)

    assert updated == 2
    assert updated_rows[0]["commit_status"] == "confirmed_review_only"
    assert updated_rows[0]["manual_commit_note"] == "review only note"
    assert updated_rows[1]["commit_status"] == "confirmed_defer"
    assert updated_rows[1]["manual_commit_note"] == "defer note"
