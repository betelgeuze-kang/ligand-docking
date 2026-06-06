from __future__ import annotations

from tools.product import build_pxr_pending_resolution_commit_packet as mod


def _contains_tokens(text: str, *tokens: str) -> None:
    lowered = text.lower()
    for token in tokens:
        assert token.lower() in lowered


def test_build_pxr_pending_resolution_commit_packet() -> None:
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
            }
        },
        {
            "summary": {
                "review_only_row_count": 1,
                "defer_row_count": 2,
                "binder_gap_count": 1,
                "supportive_binder_review_count": 0,
                "confirmed_binder_quantitative_gap_count": 1,
            }
        },
        {
            "summary": {
                "family": "pxr",
                "target": "PXR_NR1I2_BLIND",
            },
            "rows": [
                {
                    "plan_phase": "first_hour",
                    "priority_rank": 13,
                    "packet_step": "ood_eval_non_binder_02",
                    "ligand": "ibuprofen",
                    "binder": 0,
                    "resolution_bias": "review_only",
                    "explicit_stop_condition": "keep review-only and leave quantitative binding blank",
                },
                {
                    "plan_phase": "same_day_followup",
                    "priority_rank": 5,
                    "packet_step": "core_eval_non_binder_01",
                    "ligand": "acetaminophen",
                    "binder": 0,
                    "resolution_bias": "defer",
                    "explicit_stop_condition": "keep deferred and do not relabel as a non-binder",
                },
                {
                    "plan_phase": "second_pass",
                    "priority_rank": 10,
                    "packet_step": "ood_fit_binder_01",
                    "ligand": "bexarotene",
                    "binder": 1,
                    "resolution_bias": "defer",
                    "explicit_stop_condition": "keep deferred and do not fill binder fields",
                },
            ],
        },
        {
            "summary": {
                "ready_for_apply_row_count": 8,
                "blocked_row_count": 6,
            }
        },
        existing_sheet={
            "ood_fit_binder_01": {
                "manual_assay_type_honesty": "literature_confirmed_target_specific_human_pxr_binder_quantitative_value_missing",
                "manual_promotion_blocker": "quantitative_binding_value_or_activity_proxy_missing",
                "commit_status": "confirmed_defer",
            }
        },
    )

    summary = payload["summary"]
    assert summary["family"] == "pxr"
    assert summary["commit_row_count"] == 3
    assert summary["confirm_now_count"] == 1
    assert summary["must_remain_deferred_count"] == 2
    assert summary["binder_gap_count"] == 1
    assert summary["supportive_binder_review_count"] == 0
    assert summary["confirmed_binder_quantitative_gap_count"] == 1
    assert summary["ready_for_apply_row_count"] == 8
    assert summary["blocked_row_count"] == 6

    rows = payload["rows"]
    assert rows[0]["ligand"] == "ibuprofen"
    assert rows[0]["commit_class"] == "confirm_now"
    _contains_tokens(rows[0]["commit_note"], "review-only", "negative-like", "row")
    assert rows[1]["ligand"] == "acetaminophen"
    assert rows[1]["commit_class"] == "must_remain_deferred"
    assert rows[2]["ligand"] == "bexarotene"
    _contains_tokens(rows[2]["commit_note"], "quantitative", "provenance", "missing")


def test_build_pxr_pending_resolution_commit_packet_prefers_capture_sheet_manual_commit_fields() -> None:
    payload = mod.build_payload(
        {"summary": {"family": "pxr", "target": "PXR_NR1I2_BLIND"}},
        {"summary": {"review_only_row_count": 0, "defer_row_count": 1, "binder_gap_count": 0}},
        {
            "summary": {"family": "pxr", "target": "PXR_NR1I2_BLIND"},
            "rows": [
                {
                    "plan_phase": "same_day_followup",
                    "priority_rank": 6,
                    "packet_step": "core_eval_non_binder_02",
                    "ligand": "caffeine",
                    "binder": 0,
                    "resolution_bias": "defer",
                    "explicit_stop_condition": "keep deferred unless stronger source appears",
                }
            ],
        },
        {"summary": {"ready_for_apply_row_count": 8, "blocked_row_count": 6}},
        existing_sheet={
            "core_eval_non_binder_02": {
                "capture_status": "captured_supportive",
                "manual_commit_class": "confirm_now",
                "manual_commit_class_override": "Confirm as review-only based on an exact human PXR upper-bound source and keep quantitative binding blank.",
                "commit_status": "confirmed_review_only",
            }
        },
    )
    row = payload["rows"][0]
    assert row["ligand"] == "caffeine"
    assert row["commit_class"] == "confirm_now"
    _contains_tokens(row["commit_note"], "review-only", "upper-bound", "quantitative", "blank")
