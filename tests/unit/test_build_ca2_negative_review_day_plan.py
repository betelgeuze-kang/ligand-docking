from __future__ import annotations

from tools import build_ca2_negative_review_day_plan as mod


def test_build_ca2_negative_review_day_plan() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "review_only_row_count": 2,
                "core_review_only_count": 1,
                "ood_review_only_count": 1,
                "high_conflict_row_count": 1,
            },
            "rows": [
                {
                    "priority_rank": 4,
                    "packet": "core",
                    "packet_step": "core_non_binder_01",
                    "replacement_ligand_id": "acetaminophen",
                    "operator_review_bucket": "conflict_review",
                    "assay_type_honesty": "review_only_negative_conflict_with_weak_activity",
                    "promotion_blocker": "no_quantitative_nonbinder_value_curated",
                    "next_required_action": "manual_negative_evidence_review",
                    "operator_goal": "keep_review_only_without_quantitative_fill",
                    "operator_note_template": "conflict note",
                },
                {
                    "priority_rank": 10,
                    "packet": "ood",
                    "packet_step": "ood_non_binder_01",
                    "replacement_ligand_id": "aspirin",
                    "operator_review_bucket": "standard_review",
                    "assay_type_honesty": "",
                    "promotion_blocker": "no_quantitative_nonbinder_value_curated",
                    "next_required_action": "manual_negative_evidence_review",
                    "operator_goal": "keep_review_only_without_quantitative_fill",
                    "operator_note_template": "standard note",
                },
            ],
        },
        {
            "summary": {"blocked_row_count": 2},
            "workbook_rows": [
                {"packet": "core", "row_ready_for_apply": "no"},
                {"packet": "ood", "row_ready_for_apply": "no"},
            ],
        },
        {
            "rows": [
                {"packet_step": "core_non_binder_01", "next_action": "manual_negative_evidence_review"},
                {"packet_step": "ood_non_binder_01", "next_action": "manual_negative_evidence_review"},
            ]
        },
        {
            "rows": [
                {
                    "family": "ca2",
                    "review_only_negative_count": 6,
                    "defer_count": 0,
                }
            ]
        },
    )

    assert payload["summary"]["family"] == "ca2"
    assert payload["summary"]["authoritative_apply_allowed"] is False
    assert payload["summary"]["blocked_core_count"] == 1
    assert payload["summary"]["blocked_ood_count"] == 1
    assert payload["summary"]["policy_review_only_negative_count"] == 6
    assert payload["rows"][0]["day_block"] == "first_conflict_check"
    assert payload["rows"][1]["day_block"] == "afternoon_ood_review"
    assert len(payload["checklist"]) == 3
    assert len(payload["phase_notes"]) == 3
