from __future__ import annotations

from tools import build_partial_authoritative_quickstart_packet as mod


def _contains_tokens(text: str, *tokens: str) -> None:
    lowered = text.lower()
    for token in tokens:
        assert token.lower() in lowered


def test_build_partial_authoritative_quickstart_packet() -> None:
    payload = mod.build_payload(
        {
            "console_rows": [
                {
                    "console_rank": 1,
                    "family": "ca2",
                    "packet_step": "core_non_binder_01",
                    "ligand": "acetaminophen",
                    "next_required_action": "manual_negative_evidence_review",
                    "recommended_resolution": "keep_review_only_until_negative_evidence_is_curated",
                    "assay_type_honesty": "review_only_negative_conflict_with_weak_activity",
                },
                {
                    "console_rank": 4,
                    "family": "pxr",
                    "packet_step": "core_eval_non_binder_01",
                    "ligand": "acetaminophen",
                    "next_required_action": "manual_curated_search_or_defer",
                    "recommended_resolution": "defer_or_manual_curated_search",
                    "assay_type_honesty": "activity_proxy_conflicts_with_non_binder",
                },
            ]
        },
        {
            "families": [
                {
                    "family": "ca2",
                    "partial_mode": "authoritative_partial_rows_only",
                    "ready_rows": 6,
                    "blocked_rows": 6,
                    "policy_line": "Keep remaining CA2 rows review-only.",
                    "next_gate": "review_only_negative_closure",
                },
                {
                    "family": "pxr",
                    "partial_mode": "authoritative_partial_rows_only",
                    "ready_rows": 8,
                    "blocked_rows": 6,
                    "policy_line": "Keep ibuprofen review-only and defer the rest.",
                    "next_gate": "review_only_and_defer_policy_lock",
                },
            ]
        },
        {"summary": {"next_required_step": "Use CA2 workbench.", "review_only_row_count": 6}},
        {"summary": {"next_required_step": "Use PXR workbench.", "review_only_row_count": 1}},
        {"summary": {"today_focus_count": 3}, "today_focus_rows": [{"packet_step": "core_non_binder_01", "ligand": "acetaminophen", "next_required_action": "manual_negative_evidence_review"}]},
        {"summary": {"first_hour_count": 1}, "rows": [{"packet_step": "ood_eval_non_binder_02", "ligand": "ibuprofen", "next_required_action": "manual_negative_evidence_review"}]},
        {"rows": [{"packet_step": "core_non_binder_01", "replacement_ligand_id": "acetaminophen", "next_required_action": "manual_negative_evidence_review"}]},
        {"rows": [{"packet_step": "ood_eval_non_binder_02", "replacement_ligand_id": "ibuprofen", "next_required_action": "manual_negative_evidence_review"}]},
        {"summary": {"ready_row_count": 6, "blocked_row_count": 6}},
        {"summary": {"ready_for_apply_row_count": 8, "blocked_row_count": 6}},
        {"summary": {"row_count": 2, "supportive_binder_confirmation_count": 1}},
        {"summary": {"row_count": 1, "primary_focus_ligand": "bexarotene"}},
        {"summary": {"row_count": 2, "primary_focus_ligand": "acetaminophen"}},
    )
    assert payload["summary"]["family_count"] == 2
    assert payload["summary"]["ca2_ready_rows"] == 6
    assert payload["summary"]["pxr_ready_rows"] == 8
    assert payload["summary"]["pxr_confirmation_focus_count"] == 2
    assert payload["summary"]["pxr_supportive_binder_confirmation_count"] == 1
    assert payload["summary"]["pxr_conflict_resolver_focus_count"] == 2
    assert payload["summary"]["pxr_quantitative_provenance_focus_count"] == 1
    assert payload["family_rows"][0]["family"] == "ca2"
    assert "ca2_reviewer_workbench_current.md" in payload["family_rows"][0]["artifact_check_command"]
    assert payload["family_rows"][1]["family"] == "pxr"
    assert "pxr_exact_source_confirmation_packet_current.md" in payload["family_rows"][1]["artifact_check_command"]
    assert "pxr_conflict_resolver_packet_current.md" in payload["family_rows"][1]["artifact_check_command"]
    assert "pxr_quantitative_provenance_packet_current.md" in payload["family_rows"][1]["artifact_check_command"]
    _contains_tokens(payload["family_rows"][1]["no_go_rule"], "do", "not", "auto-promote")
    assert len(payload["quick_rows"]) == 2
    assert payload["quick_rows"][0]["family"] == "ca2"
    assert payload["quick_rows"][1]["family"] == "pxr"
