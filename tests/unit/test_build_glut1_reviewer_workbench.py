from __future__ import annotations

from tools import build_glut1_reviewer_workbench as mod


def test_build_glut1_reviewer_workbench() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "target_id": "GLUT1",
                "wave": "second_wave",
                "local_evidence_status": "draft_only_local_evidence_blocked",
                "binder_pending_manual_verdict_count": 1,
            },
            "binder_rows": [
                {
                    "priority_rank": "1",
                    "packet_step": "core_binder_01",
                    "candidate_name": "cytochalasin B",
                    "recommended_verdict": "keep_review_only",
                    "draft_manual_verdict_update": "keep_review_only",
                    "draft_manual_confidence_update": "strong_structural",
                    "source_anchor": "PMID 27078104",
                    "evidence_strength": "strong_structural",
                    "next_required_action": "manual_curated_search_or_defer",
                    "promotion_blocker": "no_local_glut1_binder_evidence_curated",
                }
            ],
        },
        {
            "summary": {
                "negative_slot_count": 1,
                "caution_signal_count": 1,
            },
            "negative_rows": [
                {
                    "priority_rank": "4",
                    "packet_step": "core_non_binder_01",
                    "current_ligand_id": "glut1_placeholder_nonbinder_01",
                    "next_required_action": "manual_negative_evidence_review",
                    "promotion_blocker": "no_quantitative_transporter_negative_evidence_curated",
                }
            ],
            "caution_signal_rows": [
                {
                    "priority_rank": "1",
                    "proposed_packet_step": "caution_only",
                    "candidate_name": "forskolin",
                    "recommended_verdict": "caution_only",
                    "verification_queue_action": "review_primary_source_and_decide_keep_review_only_or_defer",
                }
            ],
        },
        {
            "summary": {
                "draft_prefilled_count": 1,
            },
            "draft_rows": [
                {
                    "packet_step": "core_binder_01",
                    "draft_manual_verdict_update": "keep_review_only",
                    "draft_manual_confidence_update": "strong_structural",
                }
            ],
        },
        {
            "summary": {
                "candidate_count": 5,
            },
            "rows": [
                {
                    "proposed_packet_step": "caution_only",
                    "recommended_verdict": "caution_only",
                    "promotion_policy": "caution_only_not_for_authoritative_apply",
                }
            ],
        },
        {
            "summary": {
                "local_target_specific_binder_evidence_curated": False,
                "local_quantitative_negative_evidence_curated": False,
                "next_required_step": "Keep blocked until donor policy and provenance mature.",
            },
            "rows": [
                {"check_id": "binder_evidence"},
                {"check_id": "negative_evidence"},
                {"check_id": "fit_donor_policy"},
            ],
        },
    )

    assert payload["summary"]["target_id"] == "GLUT1"
    assert payload["summary"]["wave"] == "second_wave"
    assert payload["summary"]["authoritative_apply_allowed"] is False
    assert payload["summary"]["binder_second_wave_count"] == 1
    assert payload["summary"]["negative_slot_count"] == 1
    assert payload["summary"]["caution_or_defer_reference_count"] == 1
    assert payload["summary"]["draft_prefill_count"] == 1
    assert payload["summary"]["ready_for_reviewer_fill_count"] == 1
    assert payload["summary"]["local_binder_curated"] is False
    assert payload["summary"]["local_negative_curated"] is False
    assert payload["summary"]["local_blocker_signal_count"] == 3
    assert payload["rows"][0]["workbench_section"] == "binder_second_wave"
    assert payload["rows"][1]["workbench_section"] == "negative_slot_policy"
    assert payload["rows"][2]["workbench_section"] == "caution_or_defer_signal"
    assert len(payload["checklist"]) == 4
