from __future__ import annotations

from tools import build_family_packet_catalog as mod


def _build_payload(**overrides):
    base = dict(
        execution={"summary": {"run_now_count": 4, "prepare_next_count": 2, "manual_review_only_count": 1}},
        operator_console={"summary": {}},
        platform_index={"summary": {"run_now_count": 4, "prepare_next_count": 2, "manual_review_count": 1}},
        platform_quickstart={"summary": {"blocked_lane_count": 1}},
        pretest_sequence={"summary": {}},
        pretest_checklist={"summary": {}},
        run_now_packet={"summary": {"run_now_packet_count": 2, "measured_noop_packet_count": 2}},
        run_now_safe_command={"summary": {"run_now_family_count": 2}},
        idp_pretest_scope={"summary": {"subset_safe": True}},
        idp_commercial_pretest={"summary": {"row_count": 7, "watchlist_target_count": 3}},
        idp_broader_result={"summary": {"true_broader_shadow_completed": True, "true_broader_shadow_passed": True, "page4_fold_pass": True, "tau_k18_fold_pass": True}},
        idp_broader_decision={"summary": {"decision": "broader_shadow_passed_promotion_review_reopen", "blocking_class": "explicit_promotion_decision_required", "broader_promotion_blocked": True}},
        idp_broader_review_packet={"summary": {"status": "broader_shadow_review_packet_ready_true_broader_roster_available", "review_item_count": 4}},
        idp_broader_review_resolution={"summary": {"status": "broader_shadow_review_resolved_true_broader_roster_available", "true_broader_rerun_ready": True}},
        idp_broader_launch_packet={"summary": {"status": "launch_ready_shadow_stress_not_promotion", "true_broader_rerun_ready": True}},
        idp_page4_curation_packet={"summary": {"status": "page4_anchor_curation_packet_ready", "target_name": "page4"}},
        idp_page4_evidence_seed={"summary": {"status": "page4_anchor_evidence_seed_ready", "first_open_source_anchor": "PMC3077599 (2011)"}},
        idp_page4_provenance_fill={"summary": {"status": "page4_anchor_provenance_fill_draft_ready"}},
        idp_page4_citation_confirmed={"summary": {"status": "page4_anchor_citation_confirmed_packet_ready"}},
        idp_page4_phospho_followup={"summary": {"status": "page4_phosphorylation_followup_packet_ready"}},
        idp_page4_phospho_fill_draft={"summary": {"status": "page4_phosphorylation_fill_draft_ready"}},
        idp_page4_readiness={"summary": {"status": "page4_anchor_backed_candidate_review_ready"}},
        idp_page4_ph_low_fill={"summary": {"status": "page4_ph_low_fill_value_packet_ready"}},
        idp_page4_ph_high_fill={"summary": {"status": "page4_ph_high_fill_value_packet_ready"}},
        idp_page4_review={"summary": {"status": "page4_anchor_backed_candidate_review_packet_ready", "review_item_count": 3}},
        idp_page4_decision={"summary": {"status": "page4_anchor_backed_candidate_decision_pending_manual_confirmation", "manual_confirmation_required_count": 2}},
        idp_page4_confirmation={"summary": {"status": "page4_anchor_backed_candidate_confirmation_sheet_resolved", "pending_manual_confirmation_count": 0, "confirmed_accept_with_guardrails_count": 2}},
        idp_page4_confirmation_recommendation={"summary": {"status": "page4_anchor_backed_confirmation_recommendation_ready", "recommended_accept_with_guardrails_count": 2}},
        idp_page4_promotion_review={"summary": {"status": "page4_anchor_backed_promotion_review_ready_for_candidate_promotion", "promotion_review_ready": True, "anchor_backed_candidate_ready_now": True}},
        idp_page4_confirmation_launch={"summary": {"status": "page4_manual_confirmation_launch_packet_resolved", "pending_manual_confirmation_count": 0, "confirmed_accept_with_guardrails_count": 2, "anchor_backed_candidate_ready_now": True}},
        idp_page4_confirmation_console={"summary": {"status": "page4_manual_confirmation_console_resolved", "pending_manual_confirmation_count": 0, "confirmed_accept_with_guardrails_count": 2, "anchor_backed_candidate_ready_now": True}},
        idp_page4_confirmation_workbench={"summary": {"status": "page4_manual_confirmation_workbench_resolved", "review_row_count": 2, "pending_manual_confirmation_count": 0, "confirmed_accept_with_guardrails_count": 2, "anchor_backed_candidate_ready_now": True}},
        idp_page4_confirmation_note_templates={"summary": {"status": "page4_manual_confirmation_note_templates_ready", "template_row_count": 2}},
        idp_page4_quantitative_replacement={"summary": {"status": "page4_quantitative_anchor_replacement_packet_ready", "candidate_ready_now": True, "quantitative_replacement_row_count": 5}},
        heatmap={"summary": {"run_now_count": 4}, "rows": [{"family": "non_kinase_enzyme_ca2", "heat_bucket": "prep"}, {"family": "nuclear_receptor_pxr", "heat_bucket": "prep"}]},
        commercialization_gap={"summary": {"highest_gap_family": "transporter"}},
        commercial_core={"summary": {}},
        partial_console={"summary": {}},
        partial_operator_console={"summary": {}},
        partial_quickstart={"summary": {"ca2_ready_rows": 6, "pxr_ready_rows": 8}},
        partial_reviewer_console={"summary": {"reviewer_row_count": 10}},
        ca2_day_plan={"summary": {}},
        pxr_day_plan={"summary": {"first_hour_count": 1}},
        ca2_workbench={"summary": {"today_focus_count": 3}},
        ca2_draft_packet={"summary": {"draft_row_count": 3}},
        ca2_commit_packet={"summary": {"commit_row_count": 3}},
        pxr_workbench={"summary": {"first_hour_count": 1}},
        pxr_draft_packet={"summary": {"reviewer_draft_row_count": 4}},
        pxr_commit_packet={"summary": {"commit_row_count": 4, "confirm_now_count": 1, "must_remain_deferred_count": 3, "review_only_row_count": 1, "defer_row_count": 3, "binder_gap_count": 1}},
        pxr_capture_sheet={"summary": {"row_count": 4, "source_linked_count": 4, "supportive_target_specific_human_count": 2, "review_only_candidate_count": 1, "deferred_candidate_count": 3, "pending_capture_count": 0}},
        pxr_capture_intake={"summary": {"source_linked_count": 4, "supportive_target_specific_human_count": 2, "captured_conflict_or_gap_count": 4, "pending_capture_count": 0}},
        pxr_exact_source_confirmation={"summary": {"row_count": 2, "supportive_binder_confirmation_count": 1, "conflict_confirmation_count": 1, "title_direct_nonhuman_count": 1, "primary_focus_ligand": "bexarotene"}},
        pxr_conflict_resolver={"summary": {"row_count": 2, "pubchem_conflict_count": 1, "title_direct_nonhuman_conflict_count": 1, "exact_human_dual_mode_conflict_count": 1, "direct_human_qhts_conflict_count": 1, "nonhuman_boundary_context_count": 1, "primary_focus_ligand": "acetaminophen"}},
        pxr_quantitative_provenance={"summary": {"row_count": 1, "quantitative_value_found_count": 0, "chembl_zero_activity_count": 1, "bindingdb_exact_gap_count": 1, "primary_focus_ligand": "bexarotene"}},
        transporter_dashboard={"summary": {"current_phase": "blocker_closure_seed_row_promotion", "binder_pending_manual_verdict_count": 0, "binder_seed_row_count": 6, "placeholder_row_count_total": 12}},
        transporter_apply_status={"summary": {"placeholder_driven_rows": 12, "staged_non_authoritative_rows": 0}},
        transporter_quickstart={"summary": {"donor_policy_reopen_ready": False}},
        transporter_operator_console={"summary": {"target_count": 2}},
        transporter_launchboard={"summary": {"today_open_now_label": "bacopaside II", "first_wave_target": "AQP1"}},
        transporter_day_plan={"summary": {}},
        transporter_neg_day_plan={"summary": {"negative_slot_review_row_count": 6}},
        transporter_donor_blocker={"summary": {}},
        transporter_capture_sheet={"summary": {"row_count": 12, "source_linked_count": 0, "supportive_target_specific_packet_evidence_count": 0, "pending_capture_count": 0}},
        transporter_capture_intake={"summary": {"pending_capture_count": 0}},
        aqp1_workbench={"summary": {"pending_manual_verdict_count": 0}},
        aqp1_first_seed_row_packet={"summary": {"candidate_name": "bacopaside II", "evidence_mode": "functional_potency_staged_review_only", "quantitative_binding_status": "quantitative_binding_absent_claim_safe_kcal_missing", "remaining_unresolved_fields": "replacement_reference_binding_kcal_mol"}},
        aqp1_source_confirmation={"summary": {"row_count": 3, "primary_focus_ligand": "bacopaside II", "exact_human_reference_ligand": "AqB013", "exact_pair_absent_count": 2, "exact_human_activity_reference_count": 1}},
        aqp1_negative_source_exclusion={"summary": {"row_count": 2, "primary_focus_ligand": "tetraethylammonium", "exact_target_pair_absent_count": 2, "query_error_count": 0}},
        aqp1_negative_slot_closure={"summary": {"packet_artifact": "runs/aqp1_negative_slot_closure_packet_current.md", "row_count": 3, "top_packet_step": "core_non_binder_01", "primary_focus_ligand": "aqp1_placeholder_nonbinder_01", "shared_blocker_signal_count": 3, "exclusion_reference_row_count": 2, "exclusion_exact_target_pair_absent_count": 2}},
        aqp1_negative_acquisition={"summary": {"packet_artifact": "runs/aqp1_negative_evidence_acquisition_packet_current.md", "row_count": 3, "primary_query_label": "pressure_induced_hemolysis_reinvestigation", "primary_anchor_pmid": "23123479", "exclusion_primary_focus_ligand": "tetraethylammonium"}},
        aqp1_negative_confirmation={"summary": {"packet_artifact": "runs/aqp1_negative_evidence_confirmation_packet_current.md", "row_count": 3, "top_packet_step": "core_non_binder_01", "primary_anchor_pmid": "23123479", "boundary_positive_pmid": "40359885", "confirmation_decision": "keep_review_only_no_authoritative_negative_promotion"}},
        aqp1_negative_slot_resolution={"summary": {"packet_artifact": "runs/aqp1_negative_slot_resolution_packet_current.md", "row_count": 3, "top_packet_step": "core_non_binder_01", "primary_anchor_pmid": "23123479", "acetazolamide_boundary_pmid": "40359885", "tetraethylammonium_exact_target_pair_absent_count": 1, "confirmation_decision": "keep_review_only_no_authoritative_negative_promotion"}},
        aqp1_negative_candidate_frontier={"summary": {"packet_artifact": "runs/aqp1_negative_candidate_frontier_packet_current.md", "row_count": 4, "exact_source_tested_row_count": 4, "exact_target_pair_absent_count": 4, "frontier_candidate_count": 2, "primary_frontier_candidate": "sodium nitroprusside"}},
        aqp1_negative_frontier_resolution={"summary": {"packet_artifact": "runs/aqp1_negative_frontier_resolution_packet_current.md", "row_count": 2, "primary_frontier_candidate": "sodium nitroprusside", "solvent_fallback_candidate": "dimethyl sulfoxide", "indirect_context_row_count": 1, "exact_target_pair_absent_count": 2}},
        aqp1_negative_primary_probe={"summary": {"packet_artifact": "runs/aqp1_negative_primary_probe_packet_current.md", "row_count": 1, "primary_probe_candidate": "sodium nitroprusside", "source_anchor_pmid": "23123479", "indirect_context_pmid": "27261598"}},
        aqp1_negative_exact_source_outcome={"summary": {"packet_artifact": "runs/aqp1_negative_exact_source_outcome_packet_current.md", "row_count": 4, "primary_negative_probe_candidate": "sodium nitroprusside", "small_inhibitor_signal_candidate": "dimethyl sulfoxide", "source_pmid": "23123479"}},
        aqp1_negative_primary_probe_resolution={"summary": {"packet_artifact": "runs/aqp1_negative_primary_probe_resolution_packet_current.md", "row_count": 1, "primary_probe_candidate": "sodium nitroprusside", "source_anchor_pmid": "23123479", "solvent_fallback_candidate": "dimethyl sulfoxide", "resolution_decision": "keep_review_only_no_authoritative_negative_promotion"}},
        aqp1_follow_on_packet={
            "summary": {
                "row_count": 2,
                "follow_on_targets": "core_binder_02, core_binder_03",
                "primary_follow_on_target": "core_binder_02",
                "primary_focus_ligand": "AqB013",
                "exact_human_guardrail_ligand": "AqB013",
                "review_only_follow_on_count": 2,
                "blocking_signal": "follow_on_targets=core_binder_02, core_binder_03; exact_human_guardrail=AqB013; authoritative_apply_allowed=False",
                "next_required_step": "After core_binder_01, use core_binder_02 as the first AQP1 follow-on lane, keep replacement_reference_binding_kcal_mol blank, then continue core_binder_03 before widening to GLUT1.",
            }
        },
        aqp1_follow_on_blocker_decomposition={
            "summary": {
                "blocker_row_count": 2,
                "follow_on_targets": "core_binder_02, core_binder_03",
                "primary_focus_ligand": "AqB013",
                "exact_human_guardrail_ligand": "AqB013",
                "exact_human_nonbinding_count": 1,
                "exact_target_pair_absent_count": 1,
                "high_or_medium_potential_count": 1,
                "claim_safe_kcal_ready_count": 0,
                "source_confirmation_primary_focus_ligand": "bacopaside II",
                "blocking_signal": "follow_on_targets=core_binder_02, core_binder_03; exact_human_guardrail=AqB013; exact_human_nonbinding=1; exact_target_pair_absent=1; authoritative_apply_allowed=False",
                "next_required_step": "Keep core_binder_02 (AqB013) as the exact-human-activity follow-on guardrail with replacement_reference_binding_kcal_mol blank, keep core_binder_03 (AqB011) deferred until exact target-pair evidence is curated, and do not widen to GLUT1 until both follow-on blockers are explicitly parked.",
                "blocker_decomposition_artifact": "runs/aqp1_follow_on_blocker_decomposition_current.json",
            }
        },
        transporter_seed_row_execution_packet={"summary": {"packet_step": "core_binder_01", "safe_staged_field_count": 1}},
        aqp1_seed_row_fill_draft={"summary": {"safe_prefill_field_count": 1, "blocked_field_count": 4}},
        aqp1_draft_packet={"summary": {"ready_for_reviewer_copy_count": 3}},
        aqp1_commit_packet={"summary": {"commit_ready_count": 3}},
        aqp1_quantitative_provenance={"summary": {"row_count": 1, "exact_human_aqp1_activity_count": 1, "claim_safe_kcal_ready_count": 0, "primary_focus_ligand": "AqB013", "signal": "exact_human_activity_present_leave_kcal_blank"}},
        glut1_workbench={"summary": {"pending_manual_verdict_count": 0}},
        glut1_draft_packet={"summary": {"suggested_prefill_count": 3}},
        glut1_commit_packet={"summary": {"staged_confirmation_count": 3}},
        transporter_seed_row_board={"summary": {"seed_now_count": 3}},
        transporter_negative_target_packets={
            "summary": {
                "target_count": 2,
                "top_target_id": "AQP1",
                "top_queue_rank_start": 1,
                "top_queue_rank_end": 3,
                "aqp1_negative_slot_count": 3,
                "glut1_negative_slot_count": 3,
                "glut1_source_context_primary_focus_ligand": "cytochalasin B",
                "aqp1_slot_closure_artifact": "runs/aqp1_negative_slot_closure_packet_current.md",
                "aqp1_slot_closure_row_count": 3,
                "aqp1_slot_closure_top_packet_step": "core_non_binder_01",
                "aqp1_negative_acquisition_artifact": "runs/aqp1_negative_evidence_acquisition_packet_current.md",
                "aqp1_negative_acquisition_row_count": 3,
                "aqp1_negative_acquisition_primary_query_label": "pressure_induced_hemolysis_reinvestigation",
                "aqp1_negative_acquisition_primary_anchor_pmid": "23123479",
                "aqp1_negative_confirmation_artifact": "runs/aqp1_negative_evidence_confirmation_packet_current.md",
                "aqp1_negative_confirmation_row_count": 3,
                "aqp1_negative_confirmation_primary_anchor_pmid": "23123479",
                "aqp1_negative_confirmation_boundary_positive_pmid": "40359885",
                "aqp1_negative_confirmation_decision": "keep_review_only_no_authoritative_negative_promotion",
                "aqp1_negative_frontier_resolution_artifact": "runs/aqp1_negative_frontier_resolution_packet_current.md",
                "aqp1_negative_frontier_resolution_row_count": 2,
                "aqp1_negative_frontier_resolution_primary_frontier_candidate": "sodium nitroprusside",
                "aqp1_negative_frontier_resolution_solvent_fallback_candidate": "dimethyl sulfoxide",
                "aqp1_negative_primary_probe_artifact": "runs/aqp1_negative_primary_probe_packet_current.md",
                "aqp1_negative_primary_probe_row_count": 1,
                "aqp1_negative_primary_probe_candidate": "sodium nitroprusside",
                "aqp1_negative_primary_probe_source_anchor_pmid": "23123479",
                "aqp1_negative_exact_source_outcome_artifact": "runs/aqp1_negative_exact_source_outcome_packet_current.md",
                "aqp1_negative_exact_source_outcome_row_count": 4,
                "aqp1_negative_exact_source_primary_probe_candidate": "sodium nitroprusside",
                "aqp1_negative_exact_source_small_inhibitor_signal_candidate": "dimethyl sulfoxide",
                "aqp1_negative_exact_source_source_pmid": "23123479",
                "aqp1_negative_primary_probe_resolution_artifact": "runs/aqp1_negative_primary_probe_resolution_packet_current.md",
                "aqp1_negative_primary_probe_resolution_row_count": 1,
                "aqp1_negative_primary_probe_resolution_candidate": "sodium nitroprusside",
                "aqp1_negative_primary_probe_resolution_solvent_fallback_candidate": "dimethyl sulfoxide",
                "aqp1_negative_primary_probe_resolution_decision": "keep_review_only_no_authoritative_negative_promotion",
            }
        },
        idp_broader_promotion_review=None,
        idp_broader_promotion_resolution=None,
        idp_one_wider_repeatability_packet=None,
        idp_one_wider_repeatability_result=None,
    )
    base.update(overrides)
    return mod.build_payload(**base)


def test_build_family_packet_catalog() -> None:
    payload = _build_payload()
    assert payload["summary"]["catalog_row_count"] == 29
    assert payload["summary"]["top_level_packet_count"] == 3
    assert payload["summary"]["family_packet_count"] == 26
    assert payload["summary"]["pxr_unresolved_row_count"] == 4
    assert payload["summary"]["pxr_source_linked_count"] == 4
    assert payload["summary"]["pxr_supportive_target_specific_human_count"] == 2
    assert payload["summary"]["pxr_review_only_candidate_count"] == 1
    assert payload["summary"]["pxr_captured_conflict_or_gap_count"] == 4
    assert payload["summary"]["pxr_confirm_now_count"] == 1
    assert payload["summary"]["pxr_must_defer_count"] == 3
    assert payload["summary"]["pxr_binder_gap_count"] == 1
    assert payload["summary"]["pxr_confirmation_focus_count"] == 2
    assert payload["summary"]["pxr_confirmation_supportive_binder_count"] == 1
    assert payload["summary"]["pxr_confirmation_conflict_count"] == 1
    assert payload["summary"]["pxr_conflict_resolver_focus_count"] == 2
    assert payload["summary"]["pxr_conflict_resolver_pubchem_conflict_count"] == 1
    assert payload["summary"]["pxr_conflict_resolver_title_direct_nonhuman_conflict_count"] == 1
    assert payload["summary"]["pxr_conflict_resolver_exact_human_dual_mode_conflict_count"] == 1
    assert payload["summary"]["pxr_conflict_resolver_direct_human_qhts_conflict_count"] == 1
    assert payload["summary"]["pxr_conflict_resolver_nonhuman_boundary_context_count"] == 1
    assert payload["summary"]["pxr_quantitative_provenance_focus_count"] == 1
    assert payload["summary"]["pxr_quantitative_provenance_value_found_count"] == 0
    assert payload["summary"]["pxr_quantitative_provenance_chembl_zero_count"] == 1
    assert payload["summary"]["pxr_quantitative_provenance_bindingdb_exact_gap_count"] == 1
    assert payload["summary"]["aqp1_quantitative_provenance_focus_count"] == 1
    assert payload["summary"]["aqp1_quantitative_provenance_exact_human_activity_count"] == 1
    assert payload["summary"]["aqp1_source_confirmation_focus_count"] == 3
    assert payload["summary"]["aqp1_source_confirmation_exact_pair_absent_count"] == 2
    assert payload["summary"]["aqp1_source_confirmation_primary_focus_ligand"] == "bacopaside II"
    assert payload["summary"]["aqp1_negative_source_exclusion_ready"] is True
    assert payload["summary"]["aqp1_negative_source_exclusion_row_count"] == 2
    assert payload["summary"]["aqp1_negative_source_exclusion_primary_focus_ligand"] == "tetraethylammonium"
    assert payload["summary"]["aqp1_negative_source_exclusion_exact_target_pair_absent_count"] == 2
    assert payload["summary"]["aqp1_negative_slot_closure_ready"] is True
    assert payload["summary"]["aqp1_negative_slot_closure_row_count"] == 3
    assert payload["summary"]["aqp1_negative_slot_closure_top_packet_step"] == "core_non_binder_01"
    assert payload["summary"]["aqp1_negative_slot_closure_primary_focus_ligand"] == "aqp1_placeholder_nonbinder_01"
    assert payload["summary"]["aqp1_negative_acquisition_ready"] is True
    assert payload["summary"]["aqp1_negative_acquisition_row_count"] == 3
    assert payload["summary"]["aqp1_negative_acquisition_primary_query_label"] == "pressure_induced_hemolysis_reinvestigation"
    assert payload["summary"]["aqp1_negative_acquisition_primary_anchor_pmid"] == "23123479"
    assert payload["summary"]["aqp1_negative_confirmation_ready"] is True
    assert payload["summary"]["aqp1_negative_confirmation_row_count"] == 3
    assert payload["summary"]["aqp1_negative_confirmation_top_packet_step"] == "core_non_binder_01"
    assert payload["summary"]["aqp1_negative_confirmation_primary_anchor_pmid"] == "23123479"
    assert payload["summary"]["aqp1_negative_confirmation_boundary_positive_pmid"] == "40359885"
    assert payload["summary"]["aqp1_negative_confirmation_decision"] == "keep_review_only_no_authoritative_negative_promotion"
    assert payload["summary"]["aqp1_negative_slot_resolution_ready"] is True
    assert payload["summary"]["aqp1_negative_slot_resolution_row_count"] == 3
    assert payload["summary"]["aqp1_negative_slot_resolution_top_packet_step"] == "core_non_binder_01"
    assert payload["summary"]["aqp1_negative_slot_resolution_primary_anchor_pmid"] == "23123479"
    assert payload["summary"]["aqp1_negative_slot_resolution_acetazolamide_boundary_pmid"] == "40359885"
    assert payload["summary"]["aqp1_negative_slot_resolution_tetraethylammonium_exact_target_pair_absent_count"] == 1
    assert payload["summary"]["aqp1_negative_candidate_frontier_ready"] is True
    assert payload["summary"]["aqp1_negative_candidate_frontier_row_count"] == 4
    assert payload["summary"]["aqp1_negative_candidate_frontier_exact_source_tested_row_count"] == 4
    assert payload["summary"]["aqp1_negative_candidate_frontier_exact_target_pair_absent_count"] == 4
    assert payload["summary"]["aqp1_negative_candidate_frontier_frontier_candidate_count"] == 2
    assert payload["summary"]["aqp1_negative_candidate_frontier_primary_frontier_candidate"] == "sodium nitroprusside"
    assert payload["summary"]["aqp1_negative_frontier_resolution_ready"] is True
    assert payload["summary"]["aqp1_negative_frontier_resolution_row_count"] == 2
    assert payload["summary"]["aqp1_negative_frontier_resolution_primary_frontier_candidate"] == "sodium nitroprusside"
    assert payload["summary"]["aqp1_negative_frontier_resolution_solvent_fallback_candidate"] == "dimethyl sulfoxide"
    assert payload["summary"]["aqp1_negative_frontier_resolution_indirect_context_row_count"] == 1
    assert payload["summary"]["aqp1_negative_primary_probe_ready"] is True
    assert payload["summary"]["aqp1_negative_primary_probe_row_count"] == 1
    assert payload["summary"]["aqp1_negative_primary_probe_candidate"] == "sodium nitroprusside"
    assert payload["summary"]["aqp1_negative_primary_probe_source_anchor_pmid"] == "23123479"
    assert payload["summary"]["aqp1_negative_primary_probe_indirect_context_pmid"] == "27261598"
    assert payload["summary"]["aqp1_negative_exact_source_outcome_ready"] is True
    assert payload["summary"]["aqp1_negative_exact_source_outcome_row_count"] == 4
    assert payload["summary"]["aqp1_negative_exact_source_primary_probe_candidate"] == "sodium nitroprusside"
    assert payload["summary"]["aqp1_negative_exact_source_small_inhibitor_signal_candidate"] == "dimethyl sulfoxide"
    assert payload["summary"]["aqp1_negative_exact_source_source_pmid"] == "23123479"
    assert payload["summary"]["aqp1_negative_primary_probe_resolution_ready"] is True
    assert payload["summary"]["aqp1_negative_primary_probe_resolution_row_count"] == 1
    assert payload["summary"]["aqp1_negative_primary_probe_resolution_candidate"] == "sodium nitroprusside"
    assert payload["summary"]["aqp1_negative_primary_probe_resolution_source_anchor_pmid"] == "23123479"
    assert payload["summary"]["aqp1_negative_primary_probe_resolution_solvent_fallback_candidate"] == "dimethyl sulfoxide"
    assert payload["summary"]["aqp1_negative_primary_probe_resolution_decision"] == "keep_review_only_no_authoritative_negative_promotion"
    assert payload["summary"]["aqp1_follow_on_row_count"] == 2
    assert payload["summary"]["aqp1_follow_on_targets"] == "core_binder_02, core_binder_03"
    assert payload["summary"]["aqp1_follow_on_primary_follow_on_target"] == "core_binder_02"
    assert payload["summary"]["aqp1_follow_on_primary_focus_ligand"] == "AqB013"
    assert payload["summary"]["aqp1_follow_on_exact_human_guardrail_ligand"] == "AqB013"
    assert payload["summary"]["aqp1_follow_on_review_only_follow_on_count"] == 2
    assert "follow_on_targets=core_binder_02, core_binder_03" in payload["summary"]["aqp1_follow_on_blocking_signal"]
    assert payload["summary"]["aqp1_follow_on_next_required_step"].startswith("Keep core_binder_02 (AqB013) as the exact-human-activity follow-on guardrail")
    assert payload["summary"]["aqp1_follow_on_blocker_decomposition_ready"] is True
    assert payload["summary"]["aqp1_follow_on_blocker_count"] == 2
    assert payload["summary"]["aqp1_follow_on_exact_human_nonbinding_count"] == 1
    assert payload["summary"]["aqp1_follow_on_exact_target_pair_absent_count"] == 1
    assert payload["summary"]["aqp1_follow_on_high_or_medium_potential_count"] == 1
    assert payload["summary"]["aqp1_follow_on_claim_safe_kcal_ready_count"] == 0
    assert payload["summary"]["aqp1_follow_on_source_confirmation_primary_focus_ligand"] == "bacopaside II"
    assert payload["summary"]["aqp1_follow_on_exact_human_guardrail_ligand"] == "AqB013"
    assert payload["summary"]["aqp1_follow_on_blocking_signal"] == "follow_on_targets=core_binder_02, core_binder_03; exact_human_guardrail=AqB013; exact_human_nonbinding=1; exact_target_pair_absent=1; authoritative_apply_allowed=False"
    assert payload["summary"]["aqp1_follow_on_next_required_step"].startswith("Keep core_binder_02 (AqB013) as the exact-human-activity follow-on guardrail")
    assert payload["summary"]["aqp1_follow_on_blocker_decomposition_artifact"] == "runs/aqp1_follow_on_blocker_decomposition_current.json"
    assert payload["summary"]["aqp1_quantitative_provenance_claim_safe_kcal_ready_count"] == 0
    assert payload["summary"]["aqp1_quantitative_provenance_primary_focus_ligand"] == "AqB013"
    assert payload["summary"]["aqp1_quantitative_provenance_signal"] == "exact_human_activity_present_leave_kcal_blank"
    assert payload["summary"]["transporter_negative_target_packets_ready"] is True
    assert payload["summary"]["transporter_negative_target_packets_target_count"] == 2
    assert payload["summary"]["transporter_negative_target_packets_top_target_id"] == "AQP1"
    assert payload["summary"]["transporter_negative_target_packets_top_queue_rank_start"] == 1
    assert payload["summary"]["transporter_negative_target_packets_top_queue_rank_end"] == 3
    assert payload["summary"]["transporter_negative_target_packets_aqp1_negative_slot_count"] == 3
    assert payload["summary"]["transporter_negative_target_packets_glut1_negative_slot_count"] == 3
    assert payload["summary"]["pxr_signal"] == "review_only_1_deferred_3_keep_human_support_explicit"
    assert payload["rows"][0]["family"] == "platform"
    assert payload["rows"][0]["primary_artifact"] == "runs/platform_packet_index_current.md"
    assert "blocked=1" in payload["rows"][0]["status_signal"]
    assert payload["rows"][1]["status_signal"] == "highest_gap_family=transporter"
    assert payload["rows"][2]["primary_artifact"] == "runs/run_now_safe_command_packet_current.md"
    assert payload["rows"][3]["family"] == "idp"
    assert payload["rows"][3]["primary_artifact"] == "runs/idp_broader_shadow_decision_current.md"
    assert payload["rows"][3]["secondary_artifact"] == "runs/idp_broader_shadow_result_current.md"
    assert "controlled_targets=7" in payload["rows"][3]["status_signal"]
    assert "promotion_blocked=True" in payload["rows"][3]["status_signal"]
    assert "broader_shadow_completed=True" in payload["rows"][3]["status_signal"]
    assert payload["rows"][4]["primary_artifact"] == "runs/ca2_reviewer_workbench_current.md"
    assert payload["rows"][5]["primary_artifact"] == "runs/pxr_reviewer_workbench_current.md"
    assert "review_only=1" in payload["rows"][5]["status_signal"]
    assert "defer=3" in payload["rows"][5]["status_signal"]
    assert "binder_gap=1" in payload["rows"][5]["status_signal"]
    assert "capture_sources=4" in payload["rows"][5]["status_signal"]
    assert "supportive_human=2" in payload["rows"][5]["status_signal"]
    assert "captured_conflict_or_gap=4" in payload["rows"][5]["status_signal"]
    assert "conflict_resolver_focus=2" in payload["rows"][5]["status_signal"]
    assert "exact_dual_mode_conflicts=1" in payload["rows"][5]["status_signal"]
    assert "qhts_conflicts=1" in payload["rows"][5]["status_signal"]
    assert "nonhuman_boundary_contexts=1" in payload["rows"][5]["status_signal"]
    assert "signal=review_only_1_deferred_3_keep_human_support_explicit" in payload["rows"][5]["status_signal"]
    assert payload["rows"][6]["primary_artifact"] == "runs/pxr_exact_source_confirmation_packet_current.md"
    assert "confirmation_rows=2" in payload["rows"][6]["status_signal"]
    assert "supportive_binder=1" in payload["rows"][6]["status_signal"]
    assert "conflict_rows=1" in payload["rows"][6]["status_signal"]
    assert "title_direct_nonhuman=1" in payload["rows"][6]["status_signal"]
    assert "primary_focus=bexarotene" in payload["rows"][6]["status_signal"]
    assert payload["rows"][7]["primary_artifact"] == "runs/pxr_conflict_resolver_packet_current.md"
    assert "resolver_rows=2" in payload["rows"][7]["status_signal"]
    assert "pubchem_conflicts=1" in payload["rows"][7]["status_signal"]
    assert "title_direct_nonhuman_conflicts=1" in payload["rows"][7]["status_signal"]
    assert "exact_dual_mode_conflicts=1" in payload["rows"][7]["status_signal"]
    assert "qhts_conflicts=1" in payload["rows"][7]["status_signal"]
    assert "nonhuman_boundary_contexts=1" in payload["rows"][7]["status_signal"]
    assert "primary_focus=acetaminophen" in payload["rows"][7]["status_signal"]
    assert payload["rows"][8]["primary_artifact"] == "runs/pxr_quantitative_provenance_packet_current.md"
    assert "trace_rows=1" in payload["rows"][8]["status_signal"]
    assert "value_found=0" in payload["rows"][8]["status_signal"]
    assert "chembl_zero=1" in payload["rows"][8]["status_signal"]
    assert "bindingdb_exact_gap=1" in payload["rows"][8]["status_signal"]
    assert "primary_focus=bexarotene" in payload["rows"][8]["status_signal"]
    assert payload["rows"][9]["primary_artifact"] == "runs/pxr_unresolved_evidence_capture_sheet_current.md"
    assert "rows=4" in payload["rows"][9]["status_signal"]
    assert "source_linked=4" in payload["rows"][9]["status_signal"]
    assert "supportive_human=2" in payload["rows"][9]["status_signal"]
    assert "review_only_candidates=1" in payload["rows"][9]["status_signal"]
    assert "deferred_candidates=3" in payload["rows"][9]["status_signal"]
    assert "captured_conflict_or_gap=4" in payload["rows"][9]["status_signal"]
    assert payload["rows"][10]["primary_artifact"] == "runs/transporter_operator_console_current.md"
    assert "aqp1_exact_human_activity=1" in payload["rows"][10]["status_signal"]
    assert "aqp1_provenance_focus=AqB013" in payload["rows"][10]["status_signal"]
    assert "aqp1_provenance_signal=exact_human_activity_present_leave_kcal_blank" in payload["rows"][10]["status_signal"]
    assert payload["rows"][11]["primary_artifact"] == "runs/transporter_blocker_capture_sheet_current.md"
    assert payload["rows"][12]["primary_artifact"] == "runs/aqp1_first_seed_row_packet_current.md"
    assert "exact_human_activity=1" in payload["rows"][12]["status_signal"]
    assert "provenance_focus=AqB013" in payload["rows"][12]["status_signal"]
    assert payload["rows"][13]["primary_artifact"] == "runs/aqp1_quantitative_provenance_packet_current.md"
    assert "exact_human_activity=1" in payload["rows"][13]["status_signal"]
    assert "signal=exact_human_activity_present_leave_kcal_blank" in payload["rows"][13]["status_signal"]
    assert payload["rows"][14]["primary_artifact"] == "runs/aqp1_first_wave_source_confirmation_packet_current.md"
    assert "rows=3" in payload["rows"][14]["status_signal"]
    assert "primary_focus=bacopaside II" in payload["rows"][14]["status_signal"]
    assert "exact_human_reference=AqB013" in payload["rows"][14]["status_signal"]
    assert "exact_pair_absent=2" in payload["rows"][14]["status_signal"]
    assert payload["rows"][15]["primary_artifact"] == "runs/aqp1_negative_source_exclusion_packet_current.md"
    assert payload["rows"][15]["secondary_artifact"] == "runs/aqp1_negative_review_handoff_packet_current.md"
    assert "rows=2" in payload["rows"][15]["status_signal"]
    assert "primary_focus=tetraethylammonium" in payload["rows"][15]["status_signal"]
    assert "exact_target_pair_absent=2" in payload["rows"][15]["status_signal"]
    assert payload["rows"][16]["primary_artifact"] == "runs/aqp1_first_wave_follow_on_packet_current.md"
    assert payload["rows"][16]["secondary_artifact"] == "runs/aqp1_first_wave_source_confirmation_packet_current.md"
    assert "follow_on_targets=core_binder_02, core_binder_03" in payload["rows"][16]["status_signal"]
    assert "primary_follow_on_target=core_binder_02" in payload["rows"][16]["status_signal"]
    assert "primary_focus=AqB013" in payload["rows"][16]["status_signal"]
    assert "exact_human_guardrail=AqB013" in payload["rows"][16]["status_signal"]
    assert "review_only_follow_on=2" in payload["rows"][16]["status_signal"]
    assert payload["rows"][17]["family"] == "aqp1"
    assert payload["rows"][17]["primary_artifact"] == "runs/aqp1_follow_on_blocker_decomposition_current.md"
    assert payload["rows"][17]["secondary_artifact"] == "runs/aqp1_first_wave_follow_on_packet_current.md"
    assert "ready=True" in payload["rows"][17]["status_signal"]
    assert "blocker_row_count=2" in payload["rows"][17]["status_signal"]
    assert "follow_on_targets=core_binder_02, core_binder_03" in payload["rows"][17]["status_signal"]
    assert "primary_focus_ligand=AqB013" in payload["rows"][17]["status_signal"]
    assert "exact_human_guardrail_ligand=AqB013" in payload["rows"][17]["status_signal"]
    assert "exact_human_nonbinding_count=1" in payload["rows"][17]["status_signal"]
    assert "exact_target_pair_absent_count=1" in payload["rows"][17]["status_signal"]
    assert "high_or_medium_potential_count=1" in payload["rows"][17]["status_signal"]
    assert "claim_safe_kcal_ready_count=0" in payload["rows"][17]["status_signal"]
    assert "source_confirmation_primary_focus_ligand=bacopaside II" in payload["rows"][17]["status_signal"]
    assert "blocking_signal=follow_on_targets=core_binder_02, core_binder_03; exact_human_guardrail=AqB013; exact_human_nonbinding=1; exact_target_pair_absent=1; authoritative_apply_allowed=False" in payload["rows"][17]["status_signal"]
    assert "next_required_step=Keep core_binder_02 (AqB013) as the exact-human-activity follow-on guardrail" in payload["rows"][17]["status_signal"]
    assert "artifact=runs/aqp1_follow_on_blocker_decomposition_current.json" in payload["rows"][17]["status_signal"]
    assert payload["rows"][18]["family"] == "glut1"
    assert payload["rows"][19]["family"] == "transporter"
    assert payload["rows"][19]["primary_artifact"] == "runs/transporter_negative_evidence_target_packets_current.md"
    assert "target_count=2" in payload["rows"][19]["status_signal"]
    assert "top_target=AQP1" in payload["rows"][19]["status_signal"]
    assert "top_queue_range=1-3" in payload["rows"][19]["status_signal"]
    assert "aqp1_negative_slots=3" in payload["rows"][19]["status_signal"]
    assert "glut1_negative_slots=3" in payload["rows"][19]["status_signal"]
    assert payload["rows"][19]["family"] == "transporter"
    assert payload["rows"][20]["family"] == "aqp1"
    assert payload["rows"][20]["primary_artifact"] == "runs/aqp1_negative_slot_closure_packet_current.md"
    assert payload["rows"][20]["secondary_artifact"] == "runs/aqp1_negative_source_exclusion_packet_current.md"
    assert "rows=3" in payload["rows"][20]["status_signal"]
    assert "top_packet_step=core_non_binder_01" in payload["rows"][20]["status_signal"]
    assert "primary_focus=aqp1_placeholder_nonbinder_01" in payload["rows"][20]["status_signal"]
    assert payload["rows"][21]["family"] == "aqp1"
    assert payload["rows"][21]["primary_artifact"] == "runs/aqp1_negative_evidence_acquisition_packet_current.md"
    assert payload["rows"][21]["secondary_artifact"] == "runs/aqp1_negative_slot_closure_packet_current.md"
    assert "primary_query=pressure_induced_hemolysis_reinvestigation" in payload["rows"][21]["status_signal"]
    assert "primary_anchor_pmid=23123479" in payload["rows"][21]["status_signal"]
    assert payload["rows"][22]["family"] == "aqp1"
    assert payload["rows"][22]["primary_artifact"] == "runs/aqp1_negative_evidence_confirmation_packet_current.md"
    assert payload["rows"][22]["secondary_artifact"] == "runs/aqp1_negative_evidence_acquisition_packet_current.md"
    assert "top_packet_step=core_non_binder_01" in payload["rows"][22]["status_signal"]
    assert "primary_anchor_pmid=23123479" in payload["rows"][22]["status_signal"]
    assert "boundary_positive_pmid=40359885" in payload["rows"][22]["status_signal"]
    assert "decision=keep_review_only_no_authoritative_negative_promotion" in payload["rows"][22]["status_signal"]
    assert payload["rows"][23]["family"] == "aqp1"
    assert payload["rows"][23]["primary_artifact"] == "runs/aqp1_negative_slot_resolution_packet_current.md"
    assert payload["rows"][23]["secondary_artifact"] == "runs/aqp1_negative_evidence_confirmation_packet_current.md"
    assert "top_packet_step=core_non_binder_01" in payload["rows"][23]["status_signal"]
    assert "primary_anchor_pmid=23123479" in payload["rows"][23]["status_signal"]
    assert "acetazolamide_boundary_pmid=40359885" in payload["rows"][23]["status_signal"]
    assert "tetraethylammonium_exact_target_pair_absent_count=1" in payload["rows"][23]["status_signal"]
    assert payload["rows"][24]["family"] == "aqp1"
    assert payload["rows"][24]["primary_artifact"] == "runs/aqp1_negative_candidate_frontier_packet_current.md"
    assert payload["rows"][24]["secondary_artifact"] == "runs/aqp1_negative_slot_resolution_packet_current.md"
    assert "rows=4" in payload["rows"][24]["status_signal"]
    assert "exact_source_tested=4" in payload["rows"][24]["status_signal"]
    assert "exact_target_pair_absent=4" in payload["rows"][24]["status_signal"]
    assert "frontier_candidate_count=2" in payload["rows"][24]["status_signal"]
    assert "primary_frontier_candidate=sodium nitroprusside" in payload["rows"][24]["status_signal"]
    assert payload["rows"][25]["family"] == "aqp1"
    assert payload["rows"][25]["primary_artifact"] == "runs/aqp1_negative_frontier_resolution_packet_current.md"
    assert payload["rows"][25]["secondary_artifact"] == "runs/aqp1_negative_candidate_frontier_packet_current.md"
    assert "rows=2" in payload["rows"][25]["status_signal"]
    assert "primary_frontier_candidate=sodium nitroprusside" in payload["rows"][25]["status_signal"]
    assert "solvent_fallback_candidate=dimethyl sulfoxide" in payload["rows"][25]["status_signal"]
    assert "indirect_context_rows=1" in payload["rows"][25]["status_signal"]
    assert "exact_target_pair_absent=2" in payload["rows"][25]["status_signal"]
    assert payload["rows"][26]["family"] == "aqp1"
    assert payload["rows"][26]["primary_artifact"] == "runs/aqp1_negative_primary_probe_packet_current.md"
    assert payload["rows"][26]["secondary_artifact"] == "runs/aqp1_negative_frontier_resolution_packet_current.md"
    assert "rows=1" in payload["rows"][26]["status_signal"]
    assert "primary_probe_candidate=sodium nitroprusside" in payload["rows"][26]["status_signal"]
    assert "source_anchor_pmid=23123479" in payload["rows"][26]["status_signal"]
    assert "indirect_context_pmid=27261598" in payload["rows"][26]["status_signal"]
    assert payload["rows"][27]["family"] == "aqp1"
    assert payload["rows"][27]["primary_artifact"] == "runs/aqp1_negative_exact_source_outcome_packet_current.md"
    assert payload["rows"][27]["secondary_artifact"] == "runs/aqp1_negative_primary_probe_packet_current.md"
    assert "primary_negative_probe_candidate=sodium nitroprusside" in payload["rows"][27]["status_signal"]
    assert "small_inhibitor_signal_candidate=dimethyl sulfoxide" in payload["rows"][27]["status_signal"]
    assert "source_pmid=23123479" in payload["rows"][27]["status_signal"]
    assert payload["rows"][28]["family"] == "aqp1"
    assert payload["rows"][28]["primary_artifact"] == "runs/aqp1_negative_primary_probe_resolution_packet_current.md"
    assert payload["rows"][28]["secondary_artifact"] == "runs/aqp1_negative_primary_probe_packet_current.md"
    assert "primary_probe_candidate=sodium nitroprusside" in payload["rows"][28]["status_signal"]
    assert "source_anchor_pmid=23123479" in payload["rows"][28]["status_signal"]
    assert "solvent_fallback_candidate=dimethyl sulfoxide" in payload["rows"][28]["status_signal"]


def test_build_family_packet_catalog_prefers_idp_broader_promotion_resolution() -> None:
    payload = _build_payload(
        idp_broader_promotion_review={"summary": {"status": "broader_promotion_review_packet_ready_wider_lane_candidate", "review_item_count": 4}},
        idp_broader_promotion_resolution={"summary": {"decision": "one_wider_shadow_safe_lane_admitted", "wider_shadow_safe_lane_admitted": True}},
    )
    idp_row = payload["rows"][3]
    assert idp_row["primary_artifact"] == "runs/idp_broader_promotion_resolution_current.md"
    assert idp_row["secondary_artifact"] == "runs/idp_broader_shadow_result_current.md"
    assert "promotion_review_ready=True" in idp_row["status_signal"]
    assert "promotion_review_resolved=True" in idp_row["status_signal"]
    assert "wider_lane_admitted=True" in idp_row["status_signal"]


def test_build_family_packet_catalog_prefers_repeatability_artifact_after_resolution() -> None:
    payload = _build_payload(
        idp_broader_promotion_review={"summary": {"status": "broader_promotion_review_packet_ready_wider_lane_candidate", "review_item_count": 4}},
        idp_broader_promotion_resolution={"summary": {"decision": "one_wider_shadow_safe_lane_admitted", "wider_shadow_safe_lane_admitted": True}},
        idp_one_wider_repeatability_packet={"summary": {"status": "one_wider_shadow_repeatability_packet_ready"}},
    )
    idp_row = payload["rows"][3]
    assert idp_row["secondary_artifact"] == "runs/idp_one_wider_shadow_repeatability_packet_current.md"
    assert "repeatability_packet_ready=True" in idp_row["status_signal"]
