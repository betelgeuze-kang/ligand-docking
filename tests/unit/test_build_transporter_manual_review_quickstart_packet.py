from __future__ import annotations

from tools import build_transporter_manual_review_quickstart_packet as mod


def _contains_tokens(text: str, *tokens: str) -> None:
    lowered = text.lower()
    for token in tokens:
        assert token.lower() in lowered


def test_build_transporter_manual_review_quickstart_packet() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "binder_pending_manual_verdict_count": 0,
                "current_phase": "blocker_closure_seed_row_promotion",
                "placeholder_row_count_total": 12,
                "seed_row_fill_drafts_ready": True,
                "seed_row_sync_preview_ready": True,
                "aqp1_exact_human_activity_count": 1,
                "aqp1_quantitative_provenance_primary_focus_ligand": "AqB013",
                "aqp1_quantitative_provenance_signal": "exact_human_activity_present_leave_kcal_blank",
                "aqp1_negative_primary_probe_resolution_artifact": "runs/aqp1_negative_primary_probe_resolution_packet_current.md",
                "aqp1_negative_primary_probe_resolution_candidate": "sodium nitroprusside",
                "aqp1_negative_primary_probe_resolution_decision": "keep_review_only_no_authoritative_negative_promotion",
                "aqp1_negative_primary_probe_resolution_solvent_fallback_candidate": "dimethyl sulfoxide",
            },
            "target_rows": [
                {
                    "target_id": "AQP1",
                    "local_evidence_status": "draft_only_local_evidence_blocked",
                    "exact_human_activity_count": 1,
                    "quantitative_provenance_primary_focus_ligand": "AqB013",
                    "quantitative_provenance_signal": "exact_human_activity_present_leave_kcal_blank",
                    "negative_slot_count": 3,
                    "placeholder_rows": 6,
                    "aqp1_negative_primary_probe_resolution_artifact": "runs/aqp1_negative_primary_probe_resolution_packet_current.md",
                    "aqp1_negative_primary_probe_resolution_candidate": "sodium nitroprusside",
                    "aqp1_negative_primary_probe_resolution_decision": "keep_review_only_no_authoritative_negative_promotion",
                    "aqp1_negative_primary_probe_resolution_solvent_fallback_candidate": "dimethyl sulfoxide",
                    "next_required_step": "review aqp1 first Keep `runs/aqp1_negative_primary_probe_resolution_packet_current.md` ready as the AQP1 primary-probe resolution handoff: leave `sodium nitroprusside` review-only, keep `dimethyl sulfoxide` solvent-only, and preserve decision `keep_review_only_no_authoritative_negative_promotion`.",
                },
                {
                    "target_id": "GLUT1",
                    "local_evidence_status": "draft_only_local_evidence_blocked",
                    "negative_slot_count": 3,
                    "placeholder_rows": 6,
                    "next_required_step": "review glut1 second",
                },
            ],
        },
        {
            "rows": [
                {
                    "target_id": "AQP1",
                    "packet_step": "core_binder_01",
                    "candidate_name": "bacopaside II",
                    "review_bucket": "review_only_first_wave",
                    "next_required_action": "manual_curated_search_or_defer",
                    "promotion_blocker": "no_local_aqp1_binder_evidence_curated",
                },
                {
                    "target_id": "GLUT1",
                    "packet_step": "core_binder_01",
                    "candidate_name": "cytochalasin B",
                    "review_bucket": "review_only_second_wave",
                    "next_required_action": "manual_curated_search_or_defer",
                    "promotion_blocker": "no_local_glut1_binder_evidence_curated",
                },
            ]
        },
        {
            "review_rows": [
                {
                    "target_id": "AQP1",
                    "review_phase": "negative_slots_first",
                    "priority_rank": 4,
                    "packet_step": "core_non_binder_01",
                    "candidate_or_label": "aqp1_placeholder_nonbinder_01",
                    "review_bucket": "review_only_negative_evidence",
                    "next_required_action": "manual_negative_evidence_review",
                },
                {
                    "target_id": "GLUT1",
                    "review_phase": "negative_slots_first",
                    "priority_rank": 4,
                    "packet_step": "core_non_binder_01",
                    "candidate_or_label": "glut1_placeholder_nonbinder_01",
                    "review_bucket": "review_only_negative_evidence",
                    "next_required_action": "manual_negative_evidence_review",
                },
            ]
        },
        {
            "summary": {
                "decision_status": "scaffold_default_keep_existing_fit_donor_pool",
                "reopen_ready": False,
                "blocked_check_count": 3,
                "scaffold_fit_donor_target": "EGFR_KINASE",
            }
        },
        {
            "target_packets": [
                {
                    "target_id": "AQP1",
                    "row_count": 3,
                    "pending_manual_verdict_count": 3,
                },
                {
                    "target_id": "GLUT1",
                    "row_count": 3,
                    "pending_manual_verdict_count": 3,
                },
            ]
        },
        {
            "summary": {
                "row_count": 3,
                "primary_focus_ligand": "bacopaside II",
                "exact_human_reference_ligand": "AqB013",
            }
        },
        {
            "summary": {
                "row_count": 3,
                "primary_focus_ligand": "cytochalasin B",
                "primary_confirmation_target": "core_binder_01",
                "direct_quantitative_binding_count": 1,
                "exact_target_pair_activity_count": 2,
                "structured_pair_absent_count": 1,
            }
        },
    )

    summary = payload["summary"]
    assert summary["target_count"] == 2
    assert summary["first_wave_target"] == "AQP1"
    assert summary["second_wave_target"] == "GLUT1"
    assert summary["current_phase"] == "blocker_closure_seed_row_promotion"
    assert summary["binder_lane_count"] == 2
    assert summary["negative_lane_count"] == 2
    assert summary["placeholder_row_count_total"] == 12
    assert summary["aqp1_seed_fill_ready"] is True
    assert summary["aqp1_sync_preview_ready"] is True
    assert summary["aqp1_exact_human_activity_count"] == 1
    assert summary["aqp1_quantitative_provenance_focus_ligand"] == "AqB013"
    assert summary["aqp1_quantitative_provenance_signal"] == "exact_human_activity_present_leave_kcal_blank"
    assert summary["aqp1_source_confirmation_row_count"] == 3
    assert summary["aqp1_source_confirmation_primary_focus_ligand"] == "bacopaside II"
    assert summary["aqp1_source_confirmation_exact_human_reference_ligand"] == "AqB013"
    assert summary["aqp1_open_source_confirmation"] == "runs/aqp1_first_wave_source_confirmation_packet_current.md"
    assert summary["aqp1_negative_primary_probe_resolution_ready"] is True
    assert summary["aqp1_negative_primary_probe_resolution_artifact"] == "runs/aqp1_negative_primary_probe_resolution_packet_current.md"
    assert summary["aqp1_negative_primary_probe_resolution_candidate"] == "sodium nitroprusside"
    assert summary["aqp1_negative_primary_probe_resolution_decision"] == "keep_review_only_no_authoritative_negative_promotion"
    assert summary["aqp1_negative_primary_probe_resolution_solvent_fallback_candidate"] == "dimethyl sulfoxide"
    assert summary["glut1_source_confirmation_row_count"] == 3
    assert summary["glut1_source_confirmation_primary_focus_ligand"] == "cytochalasin B"
    assert summary["glut1_source_confirmation_primary_confirmation_target"] == "core_binder_01"
    assert summary["glut1_direct_quantitative_binding_count"] == 1
    assert summary["glut1_exact_target_pair_activity_count"] == 2
    assert summary["glut1_structured_pair_absent_count"] == 1
    assert summary["glut1_open_source_confirmation"] == "runs/glut1_second_wave_source_confirmation_packet_current.md"
    assert summary["donor_policy_status"] == "scaffold_default_keep_existing_fit_donor_pool"
    assert summary["donor_policy_reopen_ready"] is False
    _contains_tokens(
        summary["next_required_step"],
        "source-confirmation",
        "bacopaside",
        "aqb013",
        "cytochalasin",
        "wzb117",
        "stf-31",
        "primary-probe resolution",
        "sodium nitroprusside",
        "dimethyl sulfoxide",
    )
    _contains_tokens(summary["aqp1_operator_provenance_note"], "aqb013", "exact-human-activity", "replacement_reference_binding_kcal_mol", "blank")

    target_rows = {row["target_id"]: row for row in payload["target_rows"]}
    assert target_rows["AQP1"]["wave"] == "first-wave"
    assert target_rows["GLUT1"]["wave"] == "second-wave"
    assert target_rows["AQP1"]["exact_human_activity_count"] == 1
    assert target_rows["AQP1"]["quantitative_provenance_focus_ligand"] == "AqB013"
    assert target_rows["AQP1"]["quantitative_provenance_signal"] == "exact_human_activity_present_leave_kcal_blank"
    assert target_rows["AQP1"]["source_confirmation_row_count"] == 3
    assert target_rows["AQP1"]["source_confirmation_primary_focus_ligand"] == "bacopaside II"
    assert target_rows["AQP1"]["source_confirmation_exact_human_reference_ligand"] == "AqB013"
    assert target_rows["AQP1"]["open_source_confirmation"] == "runs/aqp1_first_wave_source_confirmation_packet_current.md"
    assert target_rows["AQP1"]["aqp1_negative_primary_probe_resolution_ready"] is True
    assert target_rows["AQP1"]["aqp1_negative_primary_probe_resolution_artifact"] == "runs/aqp1_negative_primary_probe_resolution_packet_current.md"
    assert target_rows["AQP1"]["aqp1_negative_primary_probe_resolution_candidate"] == "sodium nitroprusside"
    assert target_rows["AQP1"]["aqp1_negative_primary_probe_resolution_decision"] == "keep_review_only_no_authoritative_negative_promotion"
    assert target_rows["AQP1"]["aqp1_negative_primary_probe_resolution_solvent_fallback_candidate"] == "dimethyl sulfoxide"
    assert target_rows["GLUT1"]["source_confirmation_row_count"] == 3
    assert target_rows["GLUT1"]["source_confirmation_primary_focus_ligand"] == "cytochalasin B"
    assert target_rows["GLUT1"]["source_confirmation_primary_confirmation_target"] == "core_binder_01"
    # GLUT1 stays conservative here: the packet is propagated, but it should not
    # invent an exact-human-reference ligand for the second-wave surface.
    assert target_rows["GLUT1"]["source_confirmation_exact_human_reference_ligand"] == ""
    assert target_rows["GLUT1"]["source_confirmation_direct_quantitative_binding_count"] == 1
    assert target_rows["GLUT1"]["source_confirmation_exact_target_pair_activity_count"] == 2
    assert target_rows["GLUT1"]["source_confirmation_structured_pair_absent_count"] == 1
    assert target_rows["GLUT1"]["open_source_confirmation"] == "runs/glut1_second_wave_source_confirmation_packet_current.md"
    assert target_rows["AQP1"]["binder_pending_manual_verdict_count"] == 3
    assert target_rows["GLUT1"]["binder_pending_manual_verdict_count"] == 3

    lane_rows = payload["lane_rows"]
    assert lane_rows[0]["target_id"] == "AQP1"
    assert lane_rows[0]["lane"] == "binder"
    assert lane_rows[1]["lane"] == "negative"
