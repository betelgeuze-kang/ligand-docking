from __future__ import annotations

from tools.product import build_ca2_pending_burndown_console as mod


def test_build_ca2_pending_burndown_console() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "ready_row_count": 6,
                "blocked_row_count": 6,
                "most_common_missing_field": "replacement_reference_binding_kcal_mol",
            }
        },
        {
            "summary": {"draft_row_count": 3},
            "rows": [
                {
                    "day_queue_rank": 1,
                    "packet_step": "core_non_binder_01",
                    "ligand": "acetaminophen",
                    "next_required_action": "manual_negative_evidence_review",
                    "authoritative_apply_allowed_now": "no",
                    "promotion_blocker": "no_quantitative_nonbinder_value_curated",
                    "draft_manual_decision_note": "keep review-only",
                }
            ],
        },
        {
            "summary": {"confirm_now_row_count": 3},
            "rows": [
                {
                    "packet_step": "core_non_binder_01",
                    "ligand": "acetaminophen",
                    "next_required_action": "manual_negative_evidence_review",
                    "authoritative_apply_allowed_now": False,
                    "must_remain_blank_fields": "replacement_reference_binding_kcal_mol",
                    "draft_manual_decision_note": "confirm closure note",
                }
            ],
        },
    )

    summary = payload["summary"]
    assert summary["family"] == "ca2"
    assert summary["ready_row_count"] == 6
    assert summary["blocked_row_count"] == 6
    assert summary["confirm_now_row_count"] == 3
    assert summary["review_only_row_count"] == 3
    assert summary["most_common_missing_field"] == "replacement_reference_binding_kcal_mol"

    rows = payload["rows"]
    assert rows[0]["lane"] == "confirm_now"
    assert rows[0]["allowed_now"] == "no"
    assert rows[0]["must_keep_blank"] == "replacement_reference_binding_kcal_mol"
    assert rows[1]["lane"] == "review_only"
    assert rows[1]["allowed_now"] == "no"
