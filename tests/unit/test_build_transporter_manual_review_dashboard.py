from __future__ import annotations

from tools import build_transporter_manual_review_dashboard as mod


def _contains_tokens(text: str, *tokens: str) -> None:
    lowered = text.lower()
    for token in tokens:
        assert token.lower() in lowered


def test_build_transporter_manual_review_dashboard() -> None:
    payload = mod.build_payload(
        aqp1_note={"summary": {"endpoint_status": "draft_only_local_evidence_blocked", "placeholder_reference_count": 6, "manual_defer_binder_count": 3, "manual_review_only_negative_count": 3, "aqp1_p0_todo_count": 5, "next_required_step": "finish aqp1"}},
        aqp1_queue={"summary": {"review_only_negative_count": 3, "defer_binder_count": 3}},
        aqp1_plan={"summary": {"todo_count": 5}},
        aqp1_external_seed={"summary": {"candidate_count": 5, "draft_first_wave_candidate_count": 3, "endpoint_status": "external_seed_ready_direct_binding_absent", "next_required_step": "review external seeds first"}},
        aqp1_verdict={"summary": {"keep_review_only_count": 3, "caution_only_count": 1, "defer_count": 1}},
        glut1_note={"summary": {"endpoint_status": "draft_only_local_evidence_blocked", "placeholder_reference_count": 6, "manual_defer_binder_count": 3, "manual_review_only_negative_count": 3, "next_required_step": "finish glut1"}},
        glut1_queue={"summary": {"review_only_negative_count": 3, "defer_binder_count": 3}},
        glut1_pending={"summary": {"defer_rows": 3, "review_only_rows": 3}},
        glut1_external_seed={"summary": {"candidate_count": 5, "draft_second_wave_candidate_count": 3, "endpoint_status": "external_seed_ready_second_wave_direct_binding_mixed", "next_required_step": "review glut1 second wave"}},
        glut1_verdict={"summary": {"keep_review_only_count": 3, "caution_only_count": 1, "defer_count": 1}},
        aqp1_binder_sheet={"summary": {"pending_manual_verdict_count": 0}},
        glut1_binder_sheet={"summary": {"pending_manual_verdict_count": 0}},
        aqp1_draft_packet={"summary": {"row_count": 3, "ready_for_reviewer_copy_count": 3}},
        glut1_draft_packet={"summary": {"binder_slot_count": 3, "suggested_prefill_count": 3}},
        aqp1_commit_packet={"summary": {"row_count": 3, "commit_ready_count": 3}},
        glut1_commit_packet={"summary": {"binder_slot_count": 3, "staged_confirmation_count": 3}},
        aqp1_confirmation_card={"summary": {"row_count": 3, "pending_manual_verdict_count": 3}},
        glut1_confirmation_card={"summary": {"row_count": 3, "pending_manual_verdict_count": 3}},
        aqp1_staging_sheet={"summary": {"row_count": 3, "ready_for_manual_fill_count": 3}},
        glut1_staging_sheet={"summary": {"row_count": 3, "ready_for_manual_fill_count": 3}},
        aqp1_apply_draft={"summary": {"draft_prefill_count": 3, "pending_manual_verdict_count": 0}},
        glut1_apply_draft={"summary": {"draft_prefilled_count": 3, "pending_reviewer_action_count": 0}},
        aqp1_quantitative_provenance={"summary": {"row_count": 3, "exact_human_aqp1_activity_count": 1, "primary_focus_ligand": "AqB013", "signal": "exact_human_activity_present_leave_kcal_blank"}},
        aqp1_negative_packet={"summary": {"negative_slot_count": 3}},
        glut1_negative_packet={"summary": {"negative_slot_count": 3}},
        binder_progress={"summary": {"pending_manual_verdict_count": 0, "completed_manual_verdict_count": 6}},
        binder_rubric={"summary": {"policy_status": "manual_review_only"}},
        binder_note_templates={"summary": {"template_row_count": 6, "aqp1_template_count": 3, "glut1_template_count": 3}},
        binder_prefill_preview={"summary": {"preview_row_count": 6, "aqp1_preview_count": 3, "glut1_preview_count": 3}},
        binder_packets={"summary": {"target_count": 2}, "target_packets": [{"target_id": "AQP1"}, {"target_id": "GLUT1"}]},
        binder_confirmation_console={"summary": {"target_count": 2, "row_count": 6}},
        operator_console={"summary": {"target_count": 2}},
        launchboard={"summary": {"today_open_now": "runs/aqp1_manual_verdict_packet_current.md"}},
        transporter_apply_status={"summary": {"pending_manual_verdict_count": 0}},
        reviewer_day_plan={"summary": {"target_count": 2}},
        reviewer_day2_console={"summary": {"stage_count": 4}},
        negative_reviewer_day_plan={"summary": {"negative_review_row_count": 6, "caution_reference_count": 4}},
        donor_policy={"summary": {"decision_status": "scaffold_default_keep_existing_fit_donor_pool", "scaffold_fit_donor_target": "EGFR_KINASE"}},
        readiness={"summary": {"p0_open_count": 9}},
        aqp1_seed_row_fill_draft={"summary": {"safe_prefill_field_count": 1}},
        aqp1_seed_row_sync_preview={"summary": {"safe_staged_field_count": 1}},
        glut1_source_confirmation={"summary": {"row_count": 3, "primary_focus_ligand": "cytochalasin B", "direct_quantitative_binding_count": 1, "exact_target_pair_activity_count": 2, "structured_pair_absent_count": 1, "next_required_step": "Keep GLUT1 second-wave and start with cytochalasin B when widened."}},
        negative_target_packets={
            "summary": {
                "aqp1_negative_primary_probe_resolution_artifact": "runs/aqp1_negative_primary_probe_resolution_packet_current.md",
                "aqp1_negative_primary_probe_resolution_candidate": "sodium nitroprusside",
                "aqp1_negative_primary_probe_resolution_decision": "keep_review_only_no_authoritative_negative_promotion",
                "aqp1_negative_primary_probe_resolution_solvent_fallback_candidate": "dimethyl sulfoxide",
            }
        },
    )
    assert payload["summary"]["target_count"] == 2
    assert payload["summary"]["family_decision_status"] == "scaffold_default_keep_existing_fit_donor_pool"
    assert payload["summary"]["current_phase"] == "blocker_closure_seed_row_promotion"
    assert payload["summary"]["aqp1_external_candidate_count"] == 5
    assert payload["summary"]["aqp1_exact_human_activity_count"] == 1
    assert payload["summary"]["aqp1_quantitative_provenance_row_count"] == 3
    assert payload["summary"]["aqp1_quantitative_provenance_primary_focus_ligand"] == "AqB013"
    assert payload["summary"]["aqp1_quantitative_provenance_signal"] == "exact_human_activity_present_leave_kcal_blank"
    assert payload["summary"]["binder_seed_row_count"] == 6
    assert payload["summary"]["binder_pending_manual_verdict_count"] == 0
    assert payload["summary"]["binder_completed_manual_verdict_count"] == 6
    assert payload["summary"]["binder_rubric_ready"] is True
    assert payload["summary"]["binder_note_template_ready"] is True
    assert payload["summary"]["binder_note_template_count"] == 6
    assert payload["summary"]["binder_prefill_preview_ready"] is True
    assert payload["summary"]["binder_prefill_preview_count"] == 6
    assert payload["summary"]["binder_draft_packets_ready"] is True
    assert payload["summary"]["binder_draft_packet_target_count"] == 2
    assert payload["summary"]["binder_draft_packet_row_count"] == 6
    assert payload["summary"]["binder_commit_packets_ready"] is True
    assert payload["summary"]["binder_commit_packet_target_count"] == 2
    assert payload["summary"]["binder_commit_packet_row_count"] == 6
    assert payload["summary"]["binder_confirmation_cards_ready"] is True
    assert payload["summary"]["binder_confirmation_card_target_count"] == 2
    assert payload["summary"]["binder_confirmation_card_row_count"] == 6
    assert payload["summary"]["binder_staging_sheets_ready"] is True
    assert payload["summary"]["binder_staging_sheet_target_count"] == 2
    assert payload["summary"]["binder_staging_sheet_row_count"] == 6
    assert payload["summary"]["binder_apply_drafts_ready"] is True
    assert payload["summary"]["binder_apply_draft_target_count"] == 2
    assert payload["summary"]["binder_apply_draft_prefill_count"] == 6
    assert payload["summary"]["binder_apply_draft_pending_count"] == 0
    assert payload["summary"]["seed_row_fill_drafts_ready"] is True
    assert payload["summary"]["seed_row_fill_draft_target_count"] == 1
    assert payload["summary"]["aqp1_seed_row_fill_safe_prefill_count"] == 1
    assert payload["summary"]["seed_row_sync_preview_ready"] is True
    assert payload["summary"]["seed_row_sync_preview_target_count"] == 1
    assert payload["summary"]["aqp1_seed_row_sync_safe_staged_field_count"] == 1
    assert payload["summary"]["placeholder_row_count_total"] == 12
    _contains_tokens(payload["summary"]["next_required_step"], "seed-row", "promotion")
    assert payload["summary"]["negative_packets_ready"] is True
    assert payload["summary"]["negative_packet_target_count"] == 2
    assert payload["summary"]["negative_slot_count_total"] == 6
    assert payload["summary"]["binder_packets_ready"] is True
    assert payload["summary"]["binder_packet_target_count"] == 2
    assert payload["summary"]["binder_confirmation_console_ready"] is True
    assert payload["summary"]["binder_confirmation_target_count"] == 2
    assert payload["summary"]["binder_confirmation_row_count"] == 6
    assert payload["summary"]["operator_console_ready"] is True
    assert payload["summary"]["operator_console_target_count"] == 2
    assert payload["summary"]["launchboard_ready"] is True
    assert payload["summary"]["launchboard_today_open_now"] == "runs/aqp1_manual_verdict_packet_current.md"
    assert payload["summary"]["reviewer_day_plan_ready"] is True
    assert payload["summary"]["reviewer_day2_console_ready"] is True
    assert payload["summary"]["reviewer_day2_stage_count"] == 4
    assert payload["summary"]["negative_reviewer_day_plan_ready"] is True
    assert payload["summary"]["negative_review_row_count"] == 6
    assert payload["summary"]["negative_caution_reference_count"] == 4
    assert payload["summary"]["aqp1_negative_primary_probe_resolution_ready"] is True
    assert payload["summary"]["aqp1_negative_primary_probe_resolution_artifact"] == "runs/aqp1_negative_primary_probe_resolution_packet_current.md"
    assert payload["summary"]["aqp1_negative_primary_probe_resolution_candidate"] == "sodium nitroprusside"
    assert payload["summary"]["aqp1_negative_primary_probe_resolution_decision"] == "keep_review_only_no_authoritative_negative_promotion"
    assert payload["summary"]["aqp1_negative_primary_probe_resolution_solvent_fallback_candidate"] == "dimethyl sulfoxide"
    assert payload["target_rows"][0]["external_candidate_count"] == 5
    assert payload["target_rows"][0]["exact_human_activity_count"] == 1
    assert payload["target_rows"][0]["quantitative_provenance_primary_focus_ligand"] == "AqB013"
    assert payload["target_rows"][0]["quantitative_provenance_signal"] == "exact_human_activity_present_leave_kcal_blank"
    assert payload["target_rows"][0]["keep_review_only_count"] == 3
    assert payload["target_rows"][0]["binder_pending_manual_verdict_count"] == 0
    assert payload["target_rows"][0]["binder_note_template_count"] == 3
    assert payload["target_rows"][0]["binder_prefill_preview_count"] == 3
    assert payload["target_rows"][0]["binder_draft_packet_ready"] is True
    assert payload["target_rows"][0]["binder_draft_packet_count"] == 3
    assert payload["target_rows"][0]["binder_commit_packet_ready"] is True
    assert payload["target_rows"][0]["binder_commit_packet_count"] == 3
    assert payload["target_rows"][0]["binder_staging_sheet_ready"] is True
    assert payload["target_rows"][0]["binder_staging_sheet_count"] == 3
    assert payload["target_rows"][0]["binder_apply_draft_ready"] is True
    assert payload["target_rows"][0]["binder_apply_draft_prefill_count"] == 3
    assert payload["target_rows"][0]["binder_apply_draft_pending_count"] == 0
    assert payload["target_rows"][0]["seed_row_fill_draft_ready"] is True
    assert payload["target_rows"][0]["seed_row_fill_safe_prefill_count"] == 1
    assert payload["target_rows"][0]["seed_row_sync_preview_ready"] is True
    assert payload["target_rows"][0]["seed_row_sync_safe_staged_field_count"] == 1
    assert payload["target_rows"][0]["negative_packet_ready"] is True
    assert payload["target_rows"][0]["negative_slot_count"] == 3
    assert payload["target_rows"][0]["binder_packet_ready"] is True
    assert payload["target_rows"][0]["aqp1_negative_primary_probe_resolution_ready"] is True
    assert payload["target_rows"][0]["aqp1_negative_primary_probe_resolution_artifact"] == "runs/aqp1_negative_primary_probe_resolution_packet_current.md"
    _contains_tokens(
        payload["target_rows"][0]["next_required_step"],
        "AqB013",
        "blank",
        "primary-probe resolution",
        "sodium nitroprusside",
        "dimethyl sulfoxide",
    )
    _contains_tokens(
        payload["summary"]["next_required_step"],
        "primary-probe resolution",
        "sodium nitroprusside",
        "dimethyl sulfoxide",
    )
    assert payload["summary"]["glut1_external_candidate_count"] == 5
    assert payload["summary"]["glut1_second_wave_source_confirmation_ready"] is True
    assert payload["summary"]["glut1_second_wave_source_confirmation_packet_artifact"] == "runs/glut1_second_wave_source_confirmation_packet_current.md"
    assert payload["summary"]["glut1_second_wave_source_confirmation_row_count"] == 3
    assert payload["summary"]["glut1_second_wave_source_confirmation_primary_focus_ligand"] == "cytochalasin B"
    assert payload["summary"]["glut1_direct_quantitative_binding_count"] == 1
    assert payload["summary"]["glut1_exact_target_pair_activity_count"] == 2
    assert payload["summary"]["glut1_structured_pair_absent_count"] == 1
    assert payload["target_rows"][1]["external_candidate_count"] == 5
    assert payload["target_rows"][1]["second_wave_source_confirmation_ready"] is True
    assert payload["target_rows"][1]["second_wave_source_confirmation_primary_focus_ligand"] == "cytochalasin B"
    assert payload["target_rows"][1]["direct_quantitative_binding_count"] == 1
    assert payload["target_rows"][1]["exact_target_pair_activity_count"] == 2
    assert payload["target_rows"][1]["structured_pair_absent_count"] == 1
    assert payload["target_rows"][1]["exact_human_activity_count"] == 0
    assert payload["target_rows"][1]["defer_count"] == 1
    assert payload["target_rows"][1]["binder_note_template_count"] == 3
    assert payload["target_rows"][1]["binder_prefill_preview_count"] == 3
    assert payload["target_rows"][1]["binder_draft_packet_ready"] is True
    assert payload["target_rows"][1]["binder_draft_packet_count"] == 3
    assert payload["target_rows"][1]["binder_commit_packet_ready"] is True
    assert payload["target_rows"][1]["binder_commit_packet_count"] == 3
    assert payload["target_rows"][1]["binder_staging_sheet_ready"] is True
    assert payload["target_rows"][1]["binder_staging_sheet_count"] == 3
    assert payload["target_rows"][1]["binder_apply_draft_ready"] is True
    assert payload["target_rows"][1]["binder_apply_draft_prefill_count"] == 3
    assert payload["target_rows"][1]["binder_apply_draft_pending_count"] == 0
    assert payload["target_rows"][1]["seed_row_fill_draft_ready"] is False
    assert payload["target_rows"][1]["seed_row_fill_safe_prefill_count"] == 0
    assert payload["target_rows"][1]["seed_row_sync_preview_ready"] is False
    assert payload["target_rows"][1]["seed_row_sync_safe_staged_field_count"] == 0
    assert payload["target_rows"][1]["negative_packet_ready"] is True
    assert payload["target_rows"][1]["negative_slot_count"] == 3
    assert payload["target_rows"][1]["binder_packet_ready"] is True
    _contains_tokens(payload["target_rows"][1]["next_required_step"], "cytochalasin b", "glut1")


def test_build_transporter_manual_review_dashboard_propagates_glut1_second_wave_source_confirmation_step() -> None:
    payload = mod.build_payload(
        aqp1_note={"summary": {"endpoint_status": "draft_only_local_evidence_blocked"}},
        aqp1_queue={"summary": {"review_only_negative_count": 3, "defer_binder_count": 3}},
        aqp1_plan={"summary": {"todo_count": 5}},
        aqp1_external_seed=None,
        aqp1_verdict=None,
        glut1_note={"summary": {"endpoint_status": "draft_only_local_evidence_blocked"}},
        glut1_queue={"summary": {"review_only_negative_count": 3, "defer_binder_count": 3}},
        glut1_pending={"summary": {"defer_rows": 3, "review_only_rows": 3}},
        glut1_external_seed={
            "summary": {
                "candidate_count": 5,
                "draft_second_wave_candidate_count": 3,
                "endpoint_status": "external_seed_ready_second_wave_direct_binding_mixed",
                "next_required_step": "Open `runs/glut1_second_wave_source_confirmation_packet_current.md` before the GLUT1 second-wave source confirmation rows.",
            }
        },
        glut1_verdict=None,
        aqp1_binder_sheet=None,
        glut1_binder_sheet=None,
        aqp1_draft_packet=None,
        glut1_draft_packet=None,
        aqp1_commit_packet=None,
        glut1_commit_packet=None,
        aqp1_confirmation_card=None,
        glut1_confirmation_card=None,
        aqp1_staging_sheet=None,
        glut1_staging_sheet=None,
        aqp1_apply_draft=None,
        glut1_apply_draft=None,
        aqp1_quantitative_provenance=None,
        aqp1_negative_packet=None,
        glut1_negative_packet=None,
        binder_progress=None,
        binder_rubric=None,
        binder_note_templates=None,
        binder_prefill_preview=None,
        binder_packets=None,
        binder_confirmation_console=None,
        operator_console=None,
        launchboard=None,
        transporter_apply_status=None,
        reviewer_day_plan=None,
        reviewer_day2_console=None,
        negative_reviewer_day_plan=None,
        donor_policy={"summary": {"decision_status": "scaffold_default_keep_existing_fit_donor_pool", "scaffold_fit_donor_target": "EGFR_KINASE"}},
        readiness={"summary": {"p0_open_count": 9}},
    )

    assert payload["target_rows"][1]["next_required_step"] == "Open `runs/glut1_second_wave_source_confirmation_packet_current.md` before the GLUT1 second-wave source confirmation rows."
