from __future__ import annotations

from tools import build_partial_authoritative_operator_console as mod


def test_build_partial_authoritative_operator_console() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "ready_row_count": 6,
                "blocked_row_count": 6,
                "today_focus_count": 3,
                "ship_blocker": "replacement_reference_binding_kcal_mol",
                "next_required_step": "close core negatives",
            },
            "today_focus_rows": [
                {
                    "priority_rank": 4,
                    "packet_step": "core_non_binder_01",
                    "ligand": "acetaminophen",
                    "assay_type_honesty": "review_only_negative_conflict_with_weak_activity",
                    "recommended_resolution": "keep_review_only",
                }
            ],
        },
        {
            "summary": {
                "ready_row_count": 6,
                "blocked_row_count": 6,
                "most_common_missing_field": "replacement_reference_binding_kcal_mol",
            }
        },
        {
            "summary": {
                "ready_for_apply_row_count": 8,
                "blocked_row_count": 6,
                "most_common_missing_field": "replacement_reference_binding_kcal_mol",
            }
        },
        {
            "summary": {
                "row_count": 2,
                "next_required_step": "defer unresolved rows",
            },
            "rows": [
                {
                    "priority_rank": 13,
                    "packet_step": "ood_eval_non_binder_02",
                    "replacement_ligand_id": "ibuprofen",
                    "replacement_is_binder": 0,
                    "assay_type_honesty": "activity_upper_bound_only_not_quantitative_nonbinder",
                    "next_required_action": "manual_negative_evidence_review",
                },
                {
                    "priority_rank": 10,
                    "packet_step": "ood_fit_binder_01",
                    "replacement_ligand_id": "bexarotene",
                    "replacement_is_binder": 1,
                    "assay_type_honesty": "no_local_target_activity_curated",
                    "next_required_action": "manual_curated_search_or_defer",
                },
            ],
        },
        {
            "summary": {
                "policy_line": "Keep ibuprofen review-only and defer unresolved rows.",
            }
        },
    )

    summary = payload["summary"]
    assert summary["family_count"] == 2
    assert summary["partial_authoritative_family_count"] == 2
    assert summary["ready_row_count_total"] == 14
    assert summary["blocked_row_count_total"] == 12
    assert summary["handoff_row_count_total"] == 5

    families = {row["family"]: row for row in payload["family_rows"]}
    assert families["ca2"]["day_scope"] == "today_core_negative_closure"
    assert families["pxr"]["day_scope"] == "pending_policy_triage"

    rows = payload["console_rows"]
    assert rows[0]["family"] == "ca2"
    assert rows[0]["ligand"] == "acetaminophen"
    assert rows[1]["family"] == "pxr"
    assert rows[1]["recommended_resolution"] == "defer_or_manual_curated_search"
