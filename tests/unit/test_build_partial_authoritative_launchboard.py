from __future__ import annotations

from tools import build_partial_authoritative_launchboard as mod


def test_build_partial_authoritative_launchboard_payload() -> None:
    payload = mod.build_payload(
        quickstart_payload={
            "family_rows": [
                {
                    "family": "ca2",
                    "safe_scope_now": "authoritative_partial_rows_only",
                    "ready_rows": 6,
                    "blocked_rows": 6,
                    "artifact_check_command": "sed -n '1,200p' runs/ca2_packet_replacement_readiness_current.md",
                    "guardrail_check_command": "sed -n '1,200p' runs/ca2_evidence_closure_day_plan_current.md",
                    "source_artifact": "runs/ca2_reviewer_workbench_current.md",
                    "operator_note": "Keep CA2 rows review-only.",
                },
                {
                    "family": "pxr",
                    "safe_scope_now": "authoritative_partial_rows_only",
                    "ready_rows": 8,
                    "blocked_rows": 6,
                    "artifact_check_command": "sed -n '1,200p' runs/pxr_packet_fill_readiness_current.md",
                    "guardrail_check_command": "sed -n '1,200p' runs/pxr_evidence_closure_day_plan_current.md",
                    "source_artifact": "runs/pxr_reviewer_workbench_current.md",
                    "operator_note": "Keep PXR rows in partial-authoritative scope.",
                },
            ],
            "quick_rows": [
                {
                    "family": "ca2",
                    "console_rank": 1,
                    "packet_step": "core_non_binder_01",
                    "ligand": "acetaminophen",
                    "next_required_action": "manual_negative_evidence_review",
                    "recommended_resolution": "keep_review_only_until_negative_evidence_is_curated",
                    "assay_type_honesty": "no_quantitative_nonbinder_value_curated",
                    "handoff_bucket": "review_only_negative",
                },
                {
                    "family": "pxr",
                    "console_rank": 4,
                    "packet_step": "ood_eval_non_binder_02",
                    "ligand": "ibuprofen",
                    "next_required_action": "manual_negative_evidence_review",
                    "recommended_resolution": "review_only_negative_evidence",
                    "assay_type_honesty": "activity_upper_bound_only_not_quantitative_nonbinder",
                    "handoff_bucket": "review_only_negative",
                },
            ],
        },
        reviewer_console_payload={
            "family_rows": [
                {"family": "ca2", "review_focus": "today_core_review_only_negatives"},
                {"family": "pxr", "review_focus": "review_only_then_defer_triage"},
            ]
        },
        handoff_payload={
            "families": [
                {"family": "ca2", "next_gate": "review_only_negative_closure"},
                {"family": "pxr", "next_gate": "review_only_and_defer_policy_lock"},
            ]
        },
        ca2_draft_payload={"summary": {"draft_promoted_row_count": 12, "replacement_row_count": 12}},
        ca2_commit_payload={"summary": {"promoted_row_count": 6, "ready_row_count": 6}},
        pxr_draft_payload={"summary": {"draft_promoted_row_count": 14, "replacement_row_count": 14}},
        pxr_commit_payload={"summary": {"promoted_row_count": 8, "ready_row_count": 8}},
    )

    assert payload["summary"]["family_count"] == 2
    assert payload["summary"]["launchable_family_count"] == 2
    assert payload["summary"]["total_ready_rows"] == 14
    assert payload["summary"]["total_blocked_rows"] == 12
    assert payload["summary"]["total_commit_promoted_rows"] == 14
    assert payload["summary"]["total_draft_promoted_rows"] == 26
    assert payload["summary"]["launch_row_count"] == 2

    families = {row["family"]: row for row in payload["family_rows"]}
    assert families["ca2"]["next_gate"] == "review_only_negative_closure"
    assert families["pxr"]["commit_promoted_rows"] == 8
    assert families["ca2"]["draft_total_rows"] == 12

    rows = {(row["family"], row["packet_step"]): row for row in payload["launch_rows"]}
    assert rows[("ca2", "core_non_binder_01")]["handoff_bucket"] == "review_only_negative"
    assert rows[("pxr", "ood_eval_non_binder_02")]["assay_type_honesty"] == "activity_upper_bound_only_not_quantitative_nonbinder"
