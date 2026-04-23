from __future__ import annotations

from tools import build_family_manual_review_priority_queue as mod


def test_build_family_manual_review_priority_queue() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {"family": "ca2", "ready_count": 6, "review_only_count": 6, "defer_count": 0, "pending_manual_count": 6, "current_stage": "ca2_stage"},
                {"family": "pxr", "ready_count": 8, "review_only_count": 1, "defer_count": 5, "pending_manual_count": 6, "current_stage": "pxr_stage"},
                {"family": "aqp1", "ready_count": 0, "review_only_count": 3, "defer_count": 1, "pending_manual_count": 3, "current_stage": "aqp1_stage"},
                {"family": "glut1", "ready_count": 0, "review_only_count": 3, "defer_count": 1, "pending_manual_count": 3, "current_stage": "glut1_stage"},
            ]
        },
        {
            "rows": [
                {
                    "priority_rank": "4",
                    "packet_step": "core_non_binder_01",
                    "replacement_ligand_id": "acetaminophen",
                    "next_required_action": "manual_negative_evidence_review",
                    "assay_type_honesty": "review_only_negative_conflict_with_weak_activity",
                    "notes": "keep review-only",
                }
            ]
        },
        {
            "rows": [
                {
                    "priority_rank": "13",
                    "packet_step": "ood_eval_non_binder_02",
                    "replacement_ligand_id": "ibuprofen",
                    "next_required_action": "manual_negative_evidence_review",
                    "assay_type_honesty": "activity_upper_bound_only_not_quantitative_nonbinder",
                    "review_reason": "upper bound only",
                },
                {
                    "priority_rank": "10",
                    "packet_step": "ood_fit_binder_01",
                    "replacement_ligand_id": "bexarotene",
                    "next_required_action": "manual_curated_search_or_defer",
                    "assay_type_honesty": "no_local_target_activity_curated",
                    "review_reason": "defer",
                },
            ]
        },
        {
            "target_packets": [
                {
                    "target_id": "AQP1",
                    "rows": [
                        {
                            "priority_rank": "1",
                            "packet_step": "core_binder_01",
                            "candidate_name": "bacopaside II",
                            "suggested_manual_verdict": "keep_review_only",
                            "promotion_blocker": "no_local_aqp1_binder_evidence_curated",
                            "manual_decision_note_template": "aqp1 note",
                        }
                    ],
                },
                {
                    "target_id": "GLUT1",
                    "rows": [
                        {
                            "priority_rank": "1",
                            "packet_step": "core_binder_01",
                            "candidate_name": "cytochalasin B",
                            "suggested_manual_verdict": "keep_review_only",
                            "promotion_blocker": "no_local_glut1_binder_evidence_curated",
                            "manual_decision_note_template": "glut1 note",
                        }
                    ],
                },
            ]
        },
    )

    assert payload["summary"]["queue_row_count"] == 5
    assert payload["summary"]["family_band_order"] == ["ca2", "pxr", "aqp1", "glut1"]
    assert payload["rows"][0]["family"] == "ca2"
    assert payload["rows"][1]["family"] == "pxr"
    assert payload["rows"][1]["policy_bucket"] == "review_only"
    assert payload["rows"][2]["policy_bucket"] == "defer"
    assert payload["rows"][3]["family"] == "aqp1"
    assert payload["rows"][4]["family"] == "glut1"
