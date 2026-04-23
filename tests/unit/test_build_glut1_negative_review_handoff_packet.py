from __future__ import annotations

from tools import build_glut1_negative_review_handoff_packet as mod


def test_build_glut1_negative_review_handoff_packet_collects_negative_and_caution_rows() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {
                    "priority_rank": 4,
                    "packet_step": "core_non_binder_01",
                    "current_ligand_id": "glut1_placeholder_nonbinder_01",
                    "replacement_is_binder": "0",
                    "required_missing_fields": "replacement_ligand_id",
                    "review_bucket": "review_only_negative_evidence",
                    "promotion_blocker": "no_quantitative_transporter_negative_evidence_curated",
                    "next_required_action": "manual_negative_evidence_review",
                },
                {
                    "priority_rank": 1,
                    "packet_step": "core_binder_01",
                    "current_ligand_id": "glut1_placeholder_binder_01",
                    "replacement_is_binder": "1",
                },
            ]
        },
        {
            "rows": [
                {
                    "packet_step": "core_non_binder_01",
                    "disposition": "review_only_negative_evidence",
                    "promotion_blocker": "no_quantitative_transporter_negative_evidence_curated",
                    "next_required_action": "manual_negative_evidence_review",
                }
            ]
        },
        {
            "summary": {
                "endpoint_status": "draft_only_local_evidence_blocked",
                "local_quantitative_negative_evidence_curated": False,
            }
        },
        {
            "rows": [
                {
                    "candidate_name": "forskolin",
                    "proposed_packet_step": "caution_only",
                    "review_bucket": "review_only_tool_reference",
                    "recommended_verdict": "caution_only",
                    "source_anchor": "PMID 21384913",
                    "caution": "Tool only.",
                },
                {
                    "candidate_name": "cytochalasin B",
                    "proposed_packet_step": "core_binder_01",
                    "review_bucket": "review_only_second_wave",
                    "recommended_verdict": "keep_review_only",
                },
            ]
        },
        {
            "rows": [
                {
                    "packet_step": "core_non_binder_01",
                    "next_action": "manual_negative_evidence_review",
                },
                {
                    "packet_step": "caution_only",
                    "next_action": "review_primary_source_and_decide_keep_review_only_or_defer",
                },
            ]
        },
        {
            "summary": {
                "family_decision_status": "scaffold_default_keep_existing_fit_donor_pool",
                "scaffold_fit_donor_target": "EGFR_KINASE",
            },
            "target_rows": [
                {
                    "target_id": "GLUT1",
                    "local_evidence_status": "draft_only_local_evidence_blocked",
                    "placeholder_rows": 6,
                    "negative_review_only_rows": 3,
                }
            ],
        },
    )
    assert payload["summary"]["negative_slot_count"] == 1
    assert payload["summary"]["caution_signal_count"] == 1
    assert payload["summary"]["negative_review_only_rows"] == 3
    assert payload["negative_rows"][0]["verification_queue_action"] == "manual_negative_evidence_review"
    assert payload["caution_signal_rows"][0]["candidate_name"] == "forskolin"


def test_glut1_negative_review_handoff_target_row_lookup() -> None:
    row = mod._glut1_target_row(
        {
            "target_rows": [
                {"target_id": "AQP1"},
                {"target_id": "GLUT1", "placeholder_rows": 6},
            ]
        }
    )
    assert row["target_id"] == "GLUT1"
    assert row["placeholder_rows"] == 6
