from __future__ import annotations

from tools import build_cross_family_residual_shadow_layer as mod


def test_build_payload_includes_ca2_and_pxr_blockers() -> None:
    mod._latest_cross_family_shadow_run = lambda: {"run_root": "/tmp/crossfam", "status": "running"}
    payload = mod.build_payload(
        {"decision": "no_go_for_100k_router"},
        {"summary": {"measured_failure_scopes": ["gpcr"], "measured_pass_scopes": ["ion_channel", "kinase"]}},
        {"summary": {"mean_stage2_share_pct": 86.0}},
        {"summary": {"ready_row_count": 3, "blocked_row_count": 9}},
        {"summary": {"ready_for_apply_row_count": 4, "blocked_row_count": 10}},
        {"candidate_spec_json": "/tmp/spec.json"},
        {"summary": {"decision": "keep_shadow_noop_contract_for_ion_kinase"}},
        {"summary": {"review_only_rows": 6, "defer_rows": 0}},
        {
            "summary": {"review_only_rows": 1, "defer_rows": 5},
            "rows": [
                {
                    "replacement_ligand_id": "bexarotene",
                    "promotion_blocker": "quantitative_binding_value_or_activity_proxy_missing",
                }
            ],
        },
        {"summary": {"validate_only_ok": True, "p0_open_count": 11}},
        {"summary": {"changed_row_count": 0, "provisional_anchor_row_count": 6}},
        {"summary": {"changed_row_count": 3, "would_change_gate_count": 0}},
        {"summary": {"literature_anchor_slice_count": 3, "literature_anchor_changed_slice_count": 2, "literature_anchor_would_change_state_count": 6}},
        {"decision": "prefer_rg_sasa_only"},
        {"summary": {"decision": "go_literature_anchor_default_mask_promotion", "default_feature_mask": "rg_sasa_only", "literature_anchor_default_promotion": True}},
    )
    rows = {row["family"]: row for row in payload["rows"]}
    assert rows["ion_channel"]["current_state"] == "locked_decoy_shadow_running"
    assert rows["kinase"]["readiness_signal"] == "running; decision=keep_shadow_noop_contract_for_ion_kinase"
    assert rows["idp"]["current_state"] == "literature_anchor_default_mask_ready_broader_corrected_promotion_blocked"
    assert rows["idp"]["readiness_signal"] == "subset_decision=go_literature_anchor_default_mask_promotion; default_mask=rg_sasa_only; cmp=prefer_rg_sasa_only; page4_provisional=6; tp53_gate=0"
    assert rows["non_kinase_enzyme_ca2"]["readiness_signal"] == "ready_rows=3; blocked_rows=9; review_only_rows=6; defer_rows=0"
    assert rows["nuclear_receptor_pxr"]["readiness_signal"] == "ready_rows=4; blocked_rows=10; review_only_rows=1; defer_rows=5; confirmed_quantitative_gap_rows=1"
    assert "quantitative provenance still missing" in rows["nuclear_receptor_pxr"]["next_required_step"]
    assert rows["transporter"]["readiness_signal"] == "validate_only_ok=True; p0_open_count=11"
    assert payload["summary"]["gpcr_router_decision"] == "no_go_for_100k_router"
    assert payload["summary"]["cross_family_shadow_candidate_spec_json"] == "/tmp/spec.json"


def test_enrich_payload_adds_aqp1_external_seed_signal() -> None:
    payload = {
        "summary": {},
        "rows": [
            {
                "family": "transporter",
                "current_state": "scaffold_only",
                "shadow_policy": "strongest abstention defaults",
                "routing_policy": "unsupported_shadow_family",
                "readiness_signal": "validate_only_ok=True; p0_open_count=9",
                "next_required_step": "todo",
            }
        ],
    }
    enriched = mod._enrich_payload_with_runtime_context(
        payload,
        {"summary": {"todo_count": 5, "next_priority_steps": ["aqp1_ligand_reference", "aqp1_eval_split", "aqp1_ligand_meta"]}},
        {"summary": {"review_only_negative_count": 3, "defer_binder_count": 3}},
        {"summary": {"local_target_specific_binder_evidence_curated": False, "local_quantitative_negative_evidence_curated": False, "temporary_fit_donor_target": "EGFR_KINASE", "endpoint_status": "draft_only_local_evidence_blocked"}},
        {"summary": {"candidate_count": 5, "draft_first_wave_candidate_count": 3, "endpoint_status": "external_seed_ready_direct_binding_absent"}},
        {"summary": {"keep_review_only_count": 3, "caution_only_count": 1, "defer_count": 1}},
        {"summary": {"local_target_specific_binder_evidence_curated": False, "local_quantitative_negative_evidence_curated": False, "temporary_fit_donor_target": "EGFR_KINASE"}},
        {"summary": {"candidate_count": 5, "draft_second_wave_candidate_count": 3, "endpoint_status": "external_seed_ready_second_wave_direct_binding_mixed"}},
        {"summary": {"keep_review_only_count": 3, "caution_only_count": 1, "defer_count": 1}},
        {"summary": {"pending_manual_verdict_count": 0, "completed_manual_verdict_count": 6}},
        {"summary": {"policy_status": "manual_review_only"}},
        {"summary": {"template_row_count": 6}},
        {"summary": {"preview_row_count": 6}},
        {"summary": {"target_count": 2}},
        {"summary": {"draft_prefill_count": 3, "pending_manual_verdict_count": 0}},
        {"summary": {"draft_prefilled_count": 3, "pending_reviewer_action_count": 0}},
        {"summary": {"negative_slot_count": 3}},
        {"summary": {"negative_slot_count": 3}},
        {"summary": {"current_phase": "blocker_closure_seed_row_promotion", "binder_completed_manual_verdict_count": 6, "aqp1_seed_row_fill_safe_prefill_count": 1}},
        {"summary": {"today_seed_target": "AQP1 core_binder_01", "seed_now_count": 3}},
        {"summary": {"decision_status": "scaffold_default_keep_existing_fit_donor_pool"}},
        {"summary": {"decision_status": "aqp1_first_wave_glut1_second_wave"}},
        {"summary": {"reopen_ready": False, "blocked_check_count": 3}},
        {"summary": {"pending_manual_verdict_count": 0}},
        {"summary": {"negative_slot_review_row_count": 6}},
        {"summary": {"endpoint_status": "locked_decoy_apply_safe_router_blocked"}},
        {"summary": {"status": "operator_packet_ready", "core_target_count": 4, "watchlist_target_count": 3}},
        {"summary": {"status": "controlled_shadow_only_commercial_pretest_completed_shadow_safe", "shadow_safe_retained": True, "blocking_target": "tau_k18", "next_required_step": "route follow-up through tau_k18 corrected-path stabilization"}},
        {"summary": {"true_broader_shadow_completed": True, "true_broader_shadow_passed": True, "page4_fold_pass": True, "tau_k18_fold_pass": True}},
        {"summary": {"decision": "broader_shadow_passed_promotion_review_reopen", "status": "controlled_shadow_only_commercial_pretest_broader_shadow_completed", "shadow_safe_retained": True, "blocking_target": "promotion_review", "blocking_class": "explicit_promotion_decision_required", "next_required_step": "reopen explicit promotion review using the completed broader-shadow result"}},
    )
    row = enriched["rows"][0]
    assert row["current_state"] == "manual_verdict_complete_blocker_closure_seed_row_promotion"
    assert "aqp1_external_candidate_count=5" in row["readiness_signal"]
    assert "aqp1_keep_review_only=3" in row["readiness_signal"]
    assert "glut1_external_candidate_count=5" in row["readiness_signal"]
    assert "glut1_keep_review_only=3" in row["readiness_signal"]
    assert "transporter_binder_pending=0" in row["readiness_signal"]
    assert "transporter_binder_rubric_ready=True" in row["readiness_signal"]
    assert "transporter_binder_note_templates_ready=True" in row["readiness_signal"]
    assert "transporter_binder_prefill_preview_ready=True" in row["readiness_signal"]
    assert "transporter_binder_packets_ready=True" in row["readiness_signal"]
    assert "transporter_binder_apply_drafts_ready=True" in row["readiness_signal"]
    assert "transporter_negative_packets_ready=True" in row["readiness_signal"]
    assert "transporter_reviewer_day_plan_ready=True" in row["readiness_signal"]
    assert "transporter_negative_day_plan_ready=True" in row["readiness_signal"]
    assert "transporter_current_phase=blocker_closure_seed_row_promotion" in row["readiness_signal"]
    assert "transporter_today_seed_target=AQP1 core_binder_01" in row["readiness_signal"]
    assert "transporter_donor_reopen_ready=False" in row["readiness_signal"]
    assert enriched["summary"]["aqp1_external_candidate_count"] == 5
    assert enriched["summary"]["glut1_external_candidate_count"] == 5
    assert enriched["summary"]["transporter_binder_pending_manual_verdict_count"] == 0
    assert enriched["summary"]["transporter_binder_rubric_ready"] is True
    assert enriched["summary"]["transporter_binder_note_templates_ready"] is True
    assert enriched["summary"]["transporter_binder_note_template_count"] == 6
    assert enriched["summary"]["transporter_binder_prefill_preview_ready"] is True
    assert enriched["summary"]["transporter_binder_prefill_preview_count"] == 6
    assert enriched["summary"]["transporter_binder_packets_ready"] is True
    assert enriched["summary"]["transporter_binder_packet_target_count"] == 2
    assert enriched["summary"]["transporter_binder_apply_drafts_ready"] is True
    assert enriched["summary"]["transporter_binder_apply_draft_target_count"] == 2
    assert enriched["summary"]["transporter_binder_apply_draft_prefill_count"] == 6
    assert enriched["summary"]["transporter_negative_packets_ready"] is True
    assert enriched["summary"]["transporter_negative_packet_target_count"] == 2
    assert enriched["summary"]["transporter_negative_slot_count_total"] == 6
    assert enriched["summary"]["transporter_reviewer_day_plan_ready"] is True
    assert enriched["summary"]["transporter_negative_reviewer_day_plan_ready"] is True
    assert enriched["summary"]["transporter_negative_review_row_count"] == 6
    assert enriched["summary"]["transporter_donor_reopen_ready"] is False
    assert enriched["summary"]["transporter_current_phase"] == "blocker_closure_seed_row_promotion"
    assert enriched["summary"]["transporter_today_seed_target"] == "AQP1 core_binder_01"
    assert enriched["summary"]["transporter_seed_now_count"] == 3
    assert enriched["summary"]["idp_commercial_pretest_status"] == "controlled_shadow_only_commercial_pretest_broader_shadow_completed"
    assert enriched["summary"]["idp_commercial_shadow_safe_retained"] is True
    assert enriched["summary"]["idp_commercial_blocking_target"] == "promotion_review"
    assert enriched["summary"]["idp_true_broader_shadow_completed"] is True
    assert enriched["summary"]["idp_true_broader_shadow_passed"] is True
    assert enriched["summary"]["idp_broader_shadow_decision"] == "broader_shadow_passed_promotion_review_reopen"
