from __future__ import annotations

from tools.product import build_ca2_reviewer_workbench as mod


def test_build_ca2_reviewer_workbench_payload() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "family": "ca2",
                "review_only_row_count": 6,
                "high_conflict_row_count": 1,
                "most_common_missing_field": "replacement_reference_binding_kcal_mol",
            },
            "rows": [
                {
                    "packet_step": "core_non_binder_01",
                    "operator_review_bucket": "conflict_review",
                    "assay_type_honesty": "review_only_negative_conflict_with_weak_activity",
                    "promotion_blocker": "no_quantitative_nonbinder_value_curated",
                    "next_required_action": "manual_negative_evidence_review",
                    "current_missing_fields": "replacement_reference_binding_kcal_mol",
                    "authoritative_apply_allowed_now": "no",
                    "operator_note_template": "Check weak-activity ambiguity first.",
                },
                {
                    "packet_step": "ood_non_binder_01",
                    "operator_review_bucket": "standard_review",
                    "assay_type_honesty": "",
                    "promotion_blocker": "no_quantitative_nonbinder_value_curated",
                    "next_required_action": "manual_negative_evidence_review",
                    "current_missing_fields": "replacement_reference_binding_kcal_mol",
                    "authoritative_apply_allowed_now": "no",
                    "operator_note_template": "Standard review note.",
                },
            ],
        },
        {
            "summary": {
                "family": "ca2",
                "today_focus_count": 1,
                "later_queue_count": 1,
                "ship_blocker": "replacement_reference_binding_kcal_mol",
                "selected_after_verified_top3": True,
                "contains_only_core_rows": True,
                "day_goal": "Close the core negatives first.",
            },
            "rows": [
                {
                    "day_queue_rank": 1,
                    "packet_step": "core_non_binder_01",
                    "ligand": "acetaminophen",
                    "packet": "core",
                    "assay_type_honesty": "no_quantitative_nonbinder_value_curated",
                    "recommended_resolution": "keep_review_only_until_negative_evidence_is_curated",
                    "today_focus": True,
                },
                {
                    "day_queue_rank": 4,
                    "packet_step": "ood_non_binder_01",
                    "ligand": "aspirin",
                    "packet": "ood",
                    "assay_type_honesty": "no_quantitative_nonbinder_value_curated",
                    "recommended_resolution": "keep_review_only_until_negative_evidence_is_curated",
                    "today_focus": False,
                },
            ],
        },
    )

    assert payload["summary"]["family"] == "ca2"
    assert payload["summary"]["today_focus_count"] == 1
    assert payload["summary"]["later_queue_count"] == 1
    assert payload["summary"]["high_conflict_row_count"] == 1
    assert payload["summary"]["workbench_ready"] is True

    rows = payload["rows"]
    assert rows[0]["review_phase"] == "today_focus"
    assert rows[0]["packet_step"] == "core_non_binder_01"
    assert rows[0]["operator_review_bucket"] == "conflict_review"
    assert rows[0]["authoritative_apply_allowed_now"] == "no"
    assert rows[1]["review_phase"] == "later_queue"
    assert rows[1]["packet_step"] == "ood_non_binder_01"
