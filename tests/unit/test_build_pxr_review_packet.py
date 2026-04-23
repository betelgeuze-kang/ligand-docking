from __future__ import annotations

from tools import build_pxr_review_packet as mod


def test_build_pxr_review_packet() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "review_only_rows": ["ibuprofen"],
                "defer_rows": ["acetaminophen", "bexarotene"],
                "policy_line": "Keep ibuprofen review-only; keep others deferred.",
            }
        },
        {
            "rows": [
                {
                    "priority_rank": "13",
                    "packet_step": "ood_eval_non_binder_02",
                    "replacement_ligand_id": "ibuprofen",
                    "replacement_is_binder": "0",
                    "review_bucket": "review_only_negative",
                    "assay_type_honesty": "activity_upper_bound_only_not_quantitative_nonbinder",
                    "next_required_action": "manual_negative_evidence_review",
                },
                {
                    "priority_rank": "10",
                    "packet_step": "ood_fit_binder_01",
                    "replacement_ligand_id": "bexarotene",
                    "replacement_is_binder": "1",
                    "review_bucket": "defer_pending_target_specific_evidence",
                    "assay_type_honesty": "literature_confirmed_target_specific_human_pxr_binder_quantitative_value_missing",
                    "next_required_action": "curate_quantitative_binding_value",
                },
            ]
        },
        {"summary": {"ready_for_apply_row_count": 8, "blocked_row_count": 6}},
    )

    assert payload["summary"]["row_count"] == 2
    assert payload["summary"]["review_only_row_count"] == 1
    assert payload["summary"]["defer_row_count"] == 2
    assert payload["summary"]["ready_for_apply_row_count"] == 8
    assert payload["rows"][0]["ligand"] == "ibuprofen"
    assert "review-only negative-like evidence only" in payload["rows"][0]["reviewer_note_template"]
    assert "keep `bexarotene` deferred" in payload["rows"][1]["reviewer_note_template"]
    assert "qualitative literature alone" in payload["rows"][1]["reviewer_note_template"]
