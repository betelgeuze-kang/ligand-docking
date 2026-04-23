from __future__ import annotations

from tools import build_pxr_evidence_closure_day_plan as mod


def test_build_pxr_evidence_closure_day_plan_assigns_phases() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "target": "PXR_NR1I2_BLIND",
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
                    "promotion_blocker": "activity_upper_bound_only_not_quantitative_nonbinder",
                    "next_required_action": "manual_negative_evidence_review",
                    "readiness_missing_fields": "replacement_reference_binding_kcal_mol",
                },
                {
                    "priority_rank": "10",
                    "packet_step": "ood_fit_binder_01",
                    "ligand": "bexarotene",
                    "replacement_is_binder": "1",
                    "disposition": "pending_binder_curation",
                    "assay_type_honesty": "literature_confirmed_target_specific_human_pxr_binder_quantitative_value_missing",
                    "promotion_blocker": "quantitative_binding_value_or_activity_proxy_missing",
                    "next_required_action": "curate_quantitative_binding_value",
                    "readiness_missing_fields": "replacement_reference_binding_kcal_mol",
                },
            ],
        },
        {
            "summary": {"ready_for_apply_row_count": 8, "blocked_row_count": 6},
            "readiness_rows": [
                {"packet_step": "ood_eval_non_binder_02", "required_missing_fields": "replacement_reference_binding_kcal_mol"},
                {"packet_step": "ood_fit_binder_01", "required_missing_fields": "replacement_reference_binding_kcal_mol"},
            ],
        },
        {
            "summary": {"contains_binder_gap": True},
            "rows": [],
        },
    )
    assert payload["summary"]["work_item_count"] == 2
    assert payload["summary"]["first_hour_count"] == 1
    assert payload["summary"]["second_pass_count"] == 1
    assert payload["summary"]["confirmed_binder_quantitative_gap_count"] == 1
    assert payload["rows"][0]["plan_phase"] == "first_hour"
    assert payload["rows"][1]["plan_phase"] == "second_pass"
    assert payload["rows"][1]["day_goal"] == "curate_quantitative_binder_provenance_or_keep_deferred"


def test_build_pxr_evidence_closure_day_plan_flags_unresolved_stops() -> None:
    payload = mod.build_payload(
        {
            "summary": {"target": "PXR_NR1I2_BLIND", "policy_line": "policy"},
            "rows": [
                {
                    "priority_rank": "5",
                    "packet_step": "core_eval_non_binder_01",
                    "ligand": "acetaminophen",
                    "replacement_is_binder": "0",
                    "disposition": "defer_pending_target_specific_evidence",
                    "assay_type_honesty": "activity_proxy_conflicts_with_non_binder",
                    "promotion_blocker": "activity_proxy_conflicts_with_non_binder",
                    "next_required_action": "manual_curated_search_or_defer",
                    "readiness_missing_fields": "replacement_reference_binding_kcal_mol",
                }
            ],
        },
        {"summary": {"ready_for_apply_row_count": 8, "blocked_row_count": 6}, "readiness_rows": []},
        {"summary": {"contains_binder_gap": True}, "rows": []},
    )
    assert payload["rows"][0]["day_goal"] == "resolve_non_binder_conflict_or_keep_deferred"
    assert payload["rows"][0]["stop_if_unresolved"] == "yes"
