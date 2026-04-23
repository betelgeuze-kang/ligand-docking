from __future__ import annotations

from tools import build_ca2_evidence_closure_day_plan as mod


def test_build_ca2_evidence_closure_day_plan() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "ready_row_count": 6,
                "blocked_row_count": 6,
                "most_common_missing_field": "replacement_reference_binding_kcal_mol",
            }
        },
        {
            "summary": {
                "policy_fixed_pending_count": 6,
            },
            "rows": [
                {
                    "priority_rank": 4,
                    "packet": "core",
                    "packet_step": "core_non_binder_01",
                    "replacement_ligand_id": "acetaminophen",
                    "assay_type_honesty": "review_only_negative_conflict_with_weak_activity",
                    "recommended_resolution": "keep_review_only",
                },
                {
                    "priority_rank": 5,
                    "packet": "core",
                    "packet_step": "core_non_binder_02",
                    "replacement_ligand_id": "metformin",
                    "assay_type_honesty": "no_quantitative_nonbinder_value_curated",
                    "recommended_resolution": "keep_review_only",
                },
                {
                    "priority_rank": 10,
                    "packet": "ood",
                    "packet_step": "ood_non_binder_01",
                    "replacement_ligand_id": "aspirin",
                    "assay_type_honesty": "no_quantitative_nonbinder_value_curated",
                    "recommended_resolution": "keep_review_only",
                },
            ],
        },
        {
            "summary": {
                "selected_after_verified_top3": True,
                "contains_only_core_rows": True,
            },
            "rows": [
                {
                    "priority_rank": 4,
                    "packet_step": "core_non_binder_01",
                },
                {
                    "priority_rank": 5,
                    "packet_step": "core_non_binder_02",
                },
            ],
        },
    )

    summary = payload["summary"]
    assert summary["family"] == "ca2"
    assert summary["ready_row_count"] == 6
    assert summary["blocked_row_count"] == 6
    assert summary["policy_fixed_pending_count"] == 6
    assert summary["today_focus_count"] == 2
    assert summary["later_queue_count"] == 1
    assert summary["ship_blocker"] == "replacement_reference_binding_kcal_mol"

    today = payload["today_focus_rows"]
    later = payload["later_queue_rows"]
    assert [row["packet_step"] for row in today] == ["core_non_binder_01", "core_non_binder_02"]
    assert later[0]["packet_step"] == "ood_non_binder_01"
    assert today[0]["today_focus"] == "yes"
    assert later[0]["today_focus"] == "no"
