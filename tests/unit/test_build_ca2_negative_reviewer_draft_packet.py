from __future__ import annotations

from tools import build_ca2_negative_reviewer_draft_packet as mod


def test_build_ca2_negative_reviewer_draft_packet() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {
                    "packet_step": "core_non_binder_01",
                    "review_phase": "today_focus",
                    "ligand": "acetaminophen",
                    "operator_review_bucket": "conflict_review",
                    "assay_type_honesty": "review_only_negative_conflict_with_weak_activity",
                    "promotion_blocker": "no_quantitative_nonbinder_value_curated",
                    "recommended_resolution": "keep_review_only_until_negative_evidence_is_curated",
                    "next_required_action": "manual_negative_evidence_review",
                    "operator_note_template": "Check weak-activity conflict first.",
                },
                {
                    "packet_step": "core_non_binder_02",
                    "review_phase": "today_focus",
                    "ligand": "metformin",
                    "operator_review_bucket": "standard_review",
                    "assay_type_honesty": "no_quantitative_nonbinder_value_curated",
                    "promotion_blocker": "no_quantitative_nonbinder_value_curated",
                    "recommended_resolution": "keep_review_only_until_negative_evidence_is_curated",
                    "next_required_action": "manual_negative_evidence_review",
                    "operator_note_template": "Review negative evidence.",
                },
            ]
        },
        {
            "today_focus_rows": [
                {
                    "packet_step": "core_non_binder_01",
                    "ligand": "acetaminophen",
                    "day_queue_rank": 1,
                    "recommended_resolution": "keep_review_only_until_negative_evidence_is_curated",
                },
                {
                    "packet_step": "core_non_binder_02",
                    "ligand": "metformin",
                    "day_queue_rank": 2,
                    "recommended_resolution": "keep_review_only_until_negative_evidence_is_curated",
                },
            ]
        },
        {
            "rows": [
                {
                    "packet_step": "core_non_binder_01",
                    "notes": "Queue note 1",
                },
                {
                    "packet_step": "core_non_binder_02",
                    "notes": "Queue note 2",
                },
            ]
        },
    )
    assert payload["summary"]["family"] == "ca2"
    assert payload["summary"]["draft_row_count"] == 2
    assert payload["summary"]["auto_promote_allowed_count"] == 0
    assert payload["rows"][0]["auto_promote_allowed"] == "no"
    assert payload["rows"][0]["authoritative_apply_allowed_now"] == "no"
    assert "Queue note 1" in payload["rows"][0]["draft_manual_decision_note"]
    assert payload["rows"][1]["ligand"] == "metformin"
