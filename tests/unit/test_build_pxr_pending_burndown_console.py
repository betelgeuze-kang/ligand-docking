from __future__ import annotations

from tools import build_pxr_pending_burndown_console as mod


def test_build_pxr_pending_burndown_console() -> None:
    payload = mod.build_payload(
        {
            "target": "PXR_NR1I2_BLIND",
            "summary": {
                "ready_for_apply_row_count": 8,
                "blocked_row_count": 6,
            },
        },
        {
            "summary": {
                "family": "pxr",
                "target": "PXR_NR1I2_BLIND",
                "review_only_row_count": 1,
                "defer_row_count": 2,
                "binder_gap_count": 1,
                "confirmed_binder_quantitative_gap_count": 1,
                "policy_line": "Keep ibuprofen review-only and defer the rest.",
            },
            "rows": [
                {
                    "plan_phase": "first_hour",
                    "priority_rank": 13,
                    "packet_step": "ood_eval_non_binder_02",
                    "ligand": "ibuprofen",
                    "promotion_blocker": "activity_upper_bound_only_not_quantitative_nonbinder",
                    "next_required_action": "manual_negative_evidence_review",
                    "draft_note": "Confirm weak upper-bound signal only.",
                },
                {
                    "plan_phase": "same_day_followup",
                    "priority_rank": 5,
                    "packet_step": "core_eval_non_binder_01",
                    "ligand": "acetaminophen",
                    "promotion_blocker": "activity_proxy_conflicts_with_non_binder",
                    "next_required_action": "manual_curated_search_or_defer",
                    "draft_note": "Keep deferred unless local human PXR evidence appears.",
                },
                {
                    "plan_phase": "second_pass",
                    "priority_rank": 10,
                    "packet_step": "ood_fit_binder_01",
                    "ligand": "bexarotene",
                    "promotion_blocker": "quantitative_binding_value_or_activity_proxy_missing",
                    "next_required_action": "curate_quantitative_binding_value",
                    "draft_note": "Keep deferred until quantitative binder provenance is curated.",
                },
            ],
        },
        {
            "summary": {
                "family": "pxr",
                "target": "PXR_NR1I2_BLIND",
                "review_only_row_count": 1,
                "defer_row_count": 2,
                "binder_gap_count": 1,
                "confirmed_binder_quantitative_gap_count": 1,
                "policy_line": "Keep ibuprofen review-only and defer the rest.",
            },
            "rows": [
                {
                    "commit_rank": 1,
                    "plan_phase": "first_hour",
                    "priority_rank": 13,
                    "packet_step": "ood_eval_non_binder_02",
                    "ligand": "ibuprofen",
                    "binder": 0,
                    "resolution_bias": "review_only",
                    "commit_class": "confirm_now",
                    "commit_note": "Confirm as review-only negative-like row.",
                    "stop_condition": "Keep quantitative binding blank.",
                },
                {
                    "commit_rank": 2,
                    "plan_phase": "same_day_followup",
                    "priority_rank": 5,
                    "packet_step": "core_eval_non_binder_01",
                    "ligand": "acetaminophen",
                    "binder": 0,
                    "resolution_bias": "defer",
                    "commit_class": "must_remain_deferred",
                    "commit_note": "Keep deferred unless local human PXR evidence resolves the conflict.",
                    "stop_condition": "Do not relabel as non-binder on proxy-only evidence.",
                },
                {
                    "commit_rank": 3,
                    "plan_phase": "second_pass",
                    "priority_rank": 10,
                    "packet_step": "ood_fit_binder_01",
                    "ligand": "bexarotene",
                    "binder": 1,
                    "resolution_bias": "defer",
                    "commit_class": "must_remain_deferred",
                    "commit_note": "Keep deferred until binder evidence closes the gap.",
                    "stop_condition": "Do not fill binder fields without local human PXR evidence.",
                },
            ],
        },
    )

    summary = payload["summary"]
    assert summary["family"] == "pxr"
    assert summary["target"] == "PXR_NR1I2_BLIND"
    assert summary["row_count"] == 3
    assert summary["confirm_now_count"] == 1
    assert summary["must_defer_count"] == 2
    assert summary["confirmed_binder_quantitative_gap_count"] == 1
    assert summary["ready_for_apply_row_count"] == 8
    assert summary["blocked_row_count"] == 6
    assert summary["today_open_now"] == "ibuprofen"

    confirm_rows = payload["confirm_now_rows"]
    assert len(confirm_rows) == 1
    assert confirm_rows[0]["ligand"] == "ibuprofen"
    assert confirm_rows[0]["lane"] == "confirm_now"
    assert confirm_rows[0]["next_required_action"] == "manual_negative_evidence_review"

    must_defer_rows = payload["must_defer_rows"]
    assert [row["ligand"] for row in must_defer_rows] == ["acetaminophen", "bexarotene"]
    assert all(row["lane"] == "must_defer" for row in must_defer_rows)
    assert must_defer_rows[0]["promotion_blocker"] == "activity_proxy_conflicts_with_non_binder"
    assert must_defer_rows[1]["promotion_blocker"] == "quantitative_binding_value_or_activity_proxy_missing"
