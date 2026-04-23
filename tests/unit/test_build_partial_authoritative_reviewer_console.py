from __future__ import annotations

from tools import build_partial_authoritative_reviewer_console as mod


def test_build_partial_authoritative_reviewer_console() -> None:
    payload = mod.build_payload(
        {
            "family_rows": [
                {
                    "family": "ca2",
                    "safe_scope_now": "authoritative_partial_rows_only",
                    "ready_rows": 6,
                    "blocked_rows": 6,
                    "artifact_check_command": "sed -n '1,200p' runs/ca2_packet_replacement_readiness_current.md",
                    "guardrail_check_command": "sed -n '1,220p' runs/ca2_evidence_closure_day_plan_current.md",
                    "operator_note": "Keep CA2 rows review-only.",
                },
                {
                    "family": "pxr",
                    "safe_scope_now": "authoritative_partial_rows_only",
                    "ready_rows": 8,
                    "blocked_rows": 6,
                    "artifact_check_command": "sed -n '1,220p' runs/pxr_packet_fill_readiness_current.md",
                    "guardrail_check_command": "sed -n '1,220p' runs/pxr_evidence_closure_day_plan_current.md",
                    "operator_note": "Keep PXR deferred rows locked.",
                },
            ]
        },
        {
            "summary": {"review_only_row_count": 6},
            "rows": [
                {
                    "day_queue_rank": 1,
                    "review_phase": "today_focus",
                    "packet_step": "core_non_binder_01",
                    "ligand": "acetaminophen",
                    "operator_review_bucket": "conflict_review",
                    "next_required_action": "manual_negative_evidence_review",
                    "recommended_resolution": "keep_review_only_until_negative_evidence_is_curated",
                    "promotion_blocker": "no_quantitative_nonbinder_value_curated",
                    "authoritative_apply_allowed_now": "no",
                    "operator_note_template": "Keep review-only.",
                }
            ],
        },
        {
            "summary": {"review_only_row_count": 1, "defer_row_count": 3},
            "rows": [
                {
                    "priority_rank": "13",
                    "plan_phase": "first_hour",
                    "packet_step": "ood_eval_non_binder_02",
                    "ligand": "ibuprofen",
                    "operator_stance": "review_only_negative",
                    "next_required_action": "manual_negative_evidence_review",
                    "disposition": "review_only_negative_evidence",
                    "promotion_blocker": "activity_upper_bound_only_not_quantitative_nonbinder",
                    "ready_for_authoritative_apply": "no",
                    "day_goal": "confirm_review_only_negative_and_leave_quantitative_binding_blank",
                }
            ],
        },
        {"summary": {"today_focus_count": 3}},
        {"summary": {"first_hour_count": 1}},
        {
            "summary": {"row_count": 6},
            "rows": [
                {
                    "packet_step": "core_non_binder_01",
                    "notes": "CA2 pending note",
                }
            ],
        },
        {
            "summary": {"pending_resolution_row_count": 4},
            "rows": [
                {
                    "packet_step": "ood_eval_non_binder_02",
                    "review_reason": "PXR pending note",
                    "disposition": "review_only_negative_evidence",
                }
            ],
        },
        {
            "summary": {
                "today_open_now": "runs/ca2_evidence_closure_commit_packet_current.md",
            }
        },
    )
    assert payload["summary"]["family_count"] == 2
    assert payload["summary"]["reviewer_row_count"] == 2
    assert payload["summary"]["ca2_today_focus_count"] == 3
    assert payload["summary"]["pxr_first_hour_count"] == 1
    assert payload["summary"]["after_review_artifact"] == "runs/partial_authoritative_commit_launchboard_current.md"
    assert payload["summary"]["after_review_open_now"] == "runs/ca2_evidence_closure_commit_packet_current.md"
    assert payload["family_rows"][0]["family"] == "ca2"
    assert payload["family_rows"][1]["family"] == "pxr"
    assert payload["reviewer_rows"][0]["family"] == "ca2"
    assert payload["reviewer_rows"][0]["review_reason"] == "CA2 pending note"
    assert payload["reviewer_rows"][1]["family"] == "pxr"
    assert payload["reviewer_rows"][1]["recommended_resolution"] == "review_only_negative_evidence"
