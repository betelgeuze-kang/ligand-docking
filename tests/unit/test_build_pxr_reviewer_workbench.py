from __future__ import annotations

from tools import build_pxr_reviewer_workbench as mod


def test_build_pxr_reviewer_workbench_merges_pending_and_day_plan() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "family": "pxr",
                "target": "PXR_NR1I2_BLIND",
                "review_only_row_count": 1,
                "defer_row_count": 2,
                "binder_gap_count": 1,
                "supportive_binder_review_count": 0,
                "confirmed_binder_quantitative_gap_count": 1,
                "policy_line": "Keep ibuprofen review-only and defer the rest.",
            },
            "rows": [
                {
                    "priority_rank": "13",
                    "packet_step": "ood_eval_non_binder_02",
                    "ligand": "ibuprofen",
                    "replacement_is_binder": "0",
                    "disposition": "review_only_negative_evidence",
                    "assay_type_honesty": "activity_upper_bound_only_not_quantitative_nonbinder",
                    "verification_status": "pending_binding_provenance_review",
                    "promotion_blocker": "activity_upper_bound_only_not_quantitative_nonbinder",
                    "readiness_missing_fields": "replacement_reference_binding_kcal_mol",
                    "ready_for_authoritative_apply": "no",
                    "next_required_action": "manual_negative_evidence_review",
                },
                {
                    "priority_rank": "10",
                    "packet_step": "ood_fit_binder_01",
                    "ligand": "bexarotene",
                    "replacement_is_binder": "1",
                    "disposition": "pending_binder_curation",
                    "assay_type_honesty": "literature_confirmed_target_specific_human_pxr_binder_quantitative_value_missing",
                    "verification_status": "pending_binding_provenance_review",
                    "promotion_blocker": "quantitative_binding_value_or_activity_proxy_missing",
                    "readiness_missing_fields": "replacement_reference_binding_kcal_mol",
                    "ready_for_authoritative_apply": "no",
                    "next_required_action": "curate_quantitative_binding_value",
                },
            ],
        },
        {
            "summary": {"next_required_step": "Start with ibuprofen, then leave bexarotene deferred unless evidence appears."},
            "rows": [
                {
                    "priority_rank": "13",
                    "packet_step": "ood_eval_non_binder_02",
                    "plan_phase": "first_hour",
                    "day_goal": "confirm_review_only_negative_and_leave_quantitative_binding_blank",
                    "next_required_action": "manual_negative_evidence_review",
                    "stop_if_unresolved": "no",
                },
                {
                    "priority_rank": "10",
                    "packet_step": "ood_fit_binder_01",
                    "plan_phase": "second_pass",
                    "day_goal": "curate_quantitative_binder_provenance_or_keep_deferred",
                    "next_required_action": "curate_quantitative_binding_value",
                    "stop_if_unresolved": "yes",
                },
            ],
        },
    )
    assert payload["summary"]["workbench_row_count"] == 2
    assert payload["summary"]["first_hour_count"] == 1
    assert payload["summary"]["second_pass_count"] == 1
    assert payload["summary"]["supportive_binder_review_count"] == 0
    assert payload["summary"]["confirmed_binder_quantitative_gap_count"] == 1
    assert payload["rows"][0]["operator_stance"] == "review_only_negative"
    assert payload["rows"][1]["operator_stance"] == "deferred_confirmed_binder_quantitative_gap"


def test_build_pxr_reviewer_workbench_handles_deferred_non_binder() -> None:
    payload = mod.build_payload(
        {
            "summary": {"family": "pxr", "target": "PXR_NR1I2_BLIND", "review_only_row_count": 0, "defer_row_count": 1, "binder_gap_count": 0, "policy_line": "policy"},
            "rows": [
                {
                    "priority_rank": "5",
                    "packet_step": "core_eval_non_binder_01",
                    "ligand": "acetaminophen",
                    "replacement_is_binder": "0",
                    "disposition": "defer_pending_target_specific_evidence",
                    "assay_type_honesty": "activity_proxy_conflicts_with_non_binder",
                    "verification_status": "pending_binding_provenance_review",
                    "promotion_blocker": "activity_proxy_conflicts_with_non_binder",
                    "readiness_missing_fields": "replacement_reference_binding_kcal_mol",
                    "ready_for_authoritative_apply": "no",
                    "next_required_action": "manual_curated_search_or_defer",
                }
            ],
        },
        {
            "summary": {"next_required_step": "step"},
            "rows": [
                {
                    "priority_rank": "5",
                    "packet_step": "core_eval_non_binder_01",
                    "plan_phase": "same_day_followup",
                    "day_goal": "resolve_non_binder_conflict_or_keep_deferred",
                    "next_required_action": "manual_curated_search_or_defer",
                    "stop_if_unresolved": "yes",
                }
            ],
        },
    )
    assert payload["rows"][0]["operator_stance"] == "deferred_non_binder_conflict"
    assert payload["rows"][0]["plan_phase"] == "same_day_followup"
