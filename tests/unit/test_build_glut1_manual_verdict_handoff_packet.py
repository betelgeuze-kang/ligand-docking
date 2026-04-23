from __future__ import annotations

from tools import build_glut1_manual_verdict_handoff_packet as mod


def test_build_glut1_manual_verdict_handoff_packet_merges_binder_and_negative_rows() -> None:
    payload = mod.build_payload(
        {"summary": {"endpoint_status": "draft_only_local_evidence_blocked"}},
        {
            "summary": {"candidate_count": 2, "draft_second_wave_candidate_count": 1},
            "rows": [
                {
                    "proposed_packet_step": "core_binder_01",
                    "candidate_name": "cytochalasin B",
                    "caution": "Hold as manual review only.",
                }
            ],
        },
        {
            "rows": [
                {
                    "priority_rank": 1,
                    "packet_step": "core_binder_01",
                    "current_ligand_id": "glut1_placeholder_binder_01",
                    "replacement_is_binder": "1",
                    "suggested_external_review_bucket": "review_only_second_wave",
                    "promotion_blocker": "no_local_glut1_binder_evidence_curated",
                    "next_required_action": "manual_curated_search_or_defer",
                },
                {
                    "priority_rank": 2,
                    "packet_step": "core_non_binder_01",
                    "current_ligand_id": "glut1_placeholder_nonbinder_01",
                    "replacement_is_binder": "0",
                    "required_missing_fields": "replacement_ligand_id",
                    "review_bucket": "review_only_negative_evidence",
                    "promotion_blocker": "no_quantitative_transporter_negative_evidence_curated",
                    "next_required_action": "manual_negative_evidence_review",
                },
            ]
        },
        {
            "rows": [
                {
                    "proposed_packet_step": "core_binder_01",
                    "review_bucket": "review_only_second_wave",
                    "recommended_verdict": "keep_review_only",
                }
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
            "summary": {"pending_manual_verdict_count": 1},
            "sheet_rows": [
                {
                    "priority_rank": "1",
                    "packet_step": "core_binder_01",
                    "candidate_name": "cytochalasin B",
                    "source_anchor": "PMID 27078104",
                    "source_url": "https://pubmed.ncbi.nlm.nih.gov/27078104/",
                    "evidence_strength": "strong_structural",
                    "current_recommended_verdict": "keep_review_only",
                    "promotion_blocker": "no_local_glut1_binder_evidence_curated",
                    "next_required_action": "manual_curated_search_or_defer",
                }
            ],
        },
        {
            "summary": {"authoritative_manual_fields_touched_count": 0},
            "draft_rows": [
                {
                    "packet_step": "core_binder_01",
                    "draft_manual_verdict_update": "keep_review_only",
                    "draft_manual_confidence_update": "strong_structural",
                    "draft_update_status": "needs_manual_review",
                }
            ],
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
                    "next_required_step": "Keep GLUT1 authoritative apply blocked.",
                }
            ],
        },
    )
    assert payload["summary"]["binder_slot_count"] == 1
    assert payload["summary"]["negative_slot_count"] == 1
    assert payload["summary"]["external_candidate_count"] == 2
    assert payload["summary"]["family_decision_status"] == "scaffold_default_keep_existing_fit_donor_pool"
    assert payload["binder_rows"][0]["draft_manual_verdict_update"] == "keep_review_only"
    assert payload["negative_rows"][0]["review_bucket"] == "review_only_negative_evidence"


def test_glut1_target_row_uses_dashboard_target_rows() -> None:
    row = mod._glut1_target_row(
        {
            "target_rows": [
                {"target_id": "AQP1", "local_evidence_status": "blocked"},
                {"target_id": "GLUT1", "local_evidence_status": "draft_only_local_evidence_blocked"},
            ]
        }
    )
    assert row["target_id"] == "GLUT1"
    assert row["local_evidence_status"] == "draft_only_local_evidence_blocked"
