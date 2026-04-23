from __future__ import annotations

from tools import build_domain_completion_status as mod


def _contains_tokens(text: str, *tokens: str) -> None:
    lowered = text.lower()
    for token in tokens:
        assert token.lower() in lowered


def test_build_domain_completion_status_summarizes_all_families() -> None:
    commercialization = {
        "summary": {"core_commercial_lane_score": 82.5, "all_category_expansion_score": 68.9},
        "rows": [
            {"family": "gpcr", "score": 82, "stage": "apply_safe_claim_lane", "status": "apply_safe_endpoint_ready_router_blocked", "claim_safe_scope": "locked-decoy equal-size shadow/apply endpoint", "primary_blocker": "router blocked", "source_artifact": "runs/gpcr_apply_safe_endpoint_current.md"},
            {"family": "ion_channel", "score": 88, "stage": "measured_family_commercial_lane", "status": "measured_noop_shadow_ready", "claim_safe_scope": "measured family", "primary_blocker": "none", "source_artifact": "runs/cross_family_locked_decoy_shadow_decision_current.md"},
            {"family": "kinase", "score": 90, "stage": "measured_family_commercial_lane", "status": "measured_noop_shadow_ready", "claim_safe_scope": "measured family", "primary_blocker": "none", "source_artifact": "runs/cross_family_locked_decoy_shadow_decision_current.md"},
            {"family": "idp", "score": 70, "stage": "subset_or_partial_authoritative_lane", "status": "literature_anchor_default_mask_ready", "claim_safe_scope": "subset only", "primary_blocker": "broader blocked", "source_artifact": "runs/idp_feature_state_subset_decision_current.md"},
            {"family": "non_kinase_enzyme_ca2", "score": 58, "stage": "manual_review_or_blocked_expansion_lane", "status": "partial_authoritative_rows_ready", "claim_safe_scope": "authoritative-ready rows 6/12", "primary_blocker": "review-only negatives", "source_artifact": "runs/ca2_packet_replacement_readiness_current.md"},
            {"family": "nuclear_receptor_pxr", "score": 62, "stage": "subset_or_partial_authoritative_lane", "status": "partial_authoritative_rows_ready", "claim_safe_scope": "authoritative-ready rows 8/14", "primary_blocker": "deferred rows", "source_artifact": "runs/pxr_packet_fill_readiness_current.md"},
            {"family": "transporter", "score": 32, "stage": "scaffold_only_lane", "status": "manual_review_only_first_wave_second_wave", "claim_safe_scope": "draft/manual-review only", "primary_blocker": "no authoritative rows", "source_artifact": "runs/transporter_manual_review_dashboard_current.md"},
        ],
    }
    payload = mod.build_payload(
        commercialization,
        {"summary": {"core_pr_delta_vs_baseline": 0.0, "chembl50_ef1_delta_vs_baseline": 1.77}},
        {"summary": {"candidate_fail_count": 0, "max_abs_delta_pr_auc": 0.0011}},
        {"summary": {"corrected_pass_folds": 7, "fold_count": 7, "default_feature_mask": "rg_sasa_only"}},
        {"summary": {"controlled_target_count": 7}},
        {"summary": {"status": "operator_packet_ready"}},
        {"summary": {"ready_row_count": 6}},
        {"summary": {"confirmed_commit_count": 3}},
        {"summary": {"ready_for_apply_row_count": 8}},
        {"summary": {"confirmed_commit_count": 4}},
        {"summary": {"manual_review_backlog_cleared": True, "top_blocker_signal": "placeholder_driven_rows=12; ready_for_apply_rows=0"}},
        {
            "summary": {
                "targets_with_placeholder_rows": 2,
                "current_phase": "blocker_closure_seed_row_promotion",
                "glut1_second_wave_source_confirmation_ready": True,
                "glut1_second_wave_source_confirmation_packet_artifact": "runs/glut1_second_wave_source_confirmation_packet_current.md",
                "glut1_second_wave_source_confirmation_primary_focus_ligand": "cytochalasin B",
                "glut1_direct_quantitative_binding_count": 1,
                "glut1_exact_target_pair_activity_count": 2,
                "glut1_structured_pair_absent_count": 1,
            }
        },
        {"summary": {"today_seed_target": "AQP1 core_binder_01", "top_blocker_signal": "placeholder_driven_rows=12; ready_for_apply_rows=0"}},
    )
    assert payload["summary"]["family_count"] == 7
    assert payload["summary"]["run_now_ready_count"] == 3
    assert payload["summary"]["subset_safe_count"] == 1
    assert payload["summary"]["partial_authoritative_count"] == 2
    assert payload["summary"]["manual_review_or_blocker_closure_count"] == 1
    rows = {row["family"]: row for row in payload["rows"]}
    _contains_tokens(rows["idp"]["completion_note"], "subset-safe", "controlled", "commercial-pretest")
    _contains_tokens(rows["idp"]["current_scope"], "controlled", "commercial-pretest", "subset", "basis")
    assert "broader_scaffold=7" in rows["idp"]["strongest_signal"]
    assert "pretest_status=operator_packet_ready" in rows["idp"]["strongest_signal"]
    assert rows["idp"]["source_artifact"] == "runs/idp_commercial_pretest_packet_current.md"
    _contains_tokens(rows["transporter"]["completion_note"], "manual-verdict", "blocker-closure", "seed-row promotion", "glut1", "cytochalasin b")
    assert "current_phase=blocker_closure_seed_row_promotion" in rows["transporter"]["strongest_signal"]
    assert "today_seed_target=AQP1 core_binder_01" in rows["transporter"]["strongest_signal"]
    assert "placeholder_driven_rows=12" in rows["transporter"]["strongest_signal"]
    assert "glut1_second_wave_source_confirmation_ready=True" in rows["transporter"]["strongest_signal"]
    assert "glut1_second_wave_primary_focus_ligand=cytochalasin B" in rows["transporter"]["strongest_signal"]
    assert "glut1_direct_quantitative_binding_count=1" in rows["transporter"]["strongest_signal"]
    assert "glut1_exact_target_pair_activity_count=2" in rows["transporter"]["strongest_signal"]
    assert "glut1_structured_pair_absent_count=1" in rows["transporter"]["strongest_signal"]
    assert rows["transporter"]["source_artifact"] == "runs/transporter_seed_row_promotion_board_current.md"
    _contains_tokens(
        payload["summary"]["next_required_step"],
        "glut1",
        "cytochalasin b",
        "glut1_second_wave_source_confirmation_packet_current.md",
        "non-authoritative",
    )


def test_build_domain_completion_status_prefers_idp_commercial_decision() -> None:
    commercialization = {
        "summary": {"core_commercial_lane_score": 82.5, "all_category_expansion_score": 68.9},
        "rows": [
            {"family": "gpcr", "score": 82, "stage": "apply_safe_claim_lane", "status": "apply_safe_endpoint_ready_router_blocked", "claim_safe_scope": "locked-decoy equal-size shadow/apply endpoint", "primary_blocker": "router blocked", "source_artifact": "runs/gpcr_apply_safe_endpoint_current.md"},
            {"family": "ion_channel", "score": 88, "stage": "measured_family_commercial_lane", "status": "measured_noop_shadow_ready", "claim_safe_scope": "measured family", "primary_blocker": "none", "source_artifact": "runs/cross_family_locked_decoy_shadow_decision_current.md"},
            {"family": "kinase", "score": 90, "stage": "measured_family_commercial_lane", "status": "measured_noop_shadow_ready", "claim_safe_scope": "measured family", "primary_blocker": "none", "source_artifact": "runs/cross_family_locked_decoy_shadow_decision_current.md"},
            {"family": "idp", "score": 70, "stage": "subset_or_partial_authoritative_lane", "status": "literature_anchor_default_mask_ready", "claim_safe_scope": "subset only", "primary_blocker": "broader blocked", "source_artifact": "runs/idp_feature_state_subset_decision_current.md"},
            {"family": "non_kinase_enzyme_ca2", "score": 58, "stage": "manual_review_or_blocked_expansion_lane", "status": "partial_authoritative_rows_ready", "claim_safe_scope": "authoritative-ready rows 6/12", "primary_blocker": "review-only negatives", "source_artifact": "runs/ca2_packet_replacement_readiness_current.md"},
            {"family": "nuclear_receptor_pxr", "score": 62, "stage": "subset_or_partial_authoritative_lane", "status": "partial_authoritative_rows_ready", "claim_safe_scope": "authoritative-ready rows 8/14", "primary_blocker": "deferred rows", "source_artifact": "runs/pxr_packet_fill_readiness_current.md"},
            {"family": "transporter", "score": 32, "stage": "scaffold_only_lane", "status": "manual_review_only_first_wave_second_wave", "claim_safe_scope": "draft/manual-review only", "primary_blocker": "no authoritative rows", "source_artifact": "runs/transporter_manual_review_dashboard_current.md"},
        ],
    }
    payload = mod.build_payload(
        commercialization,
        {"summary": {"core_pr_delta_vs_baseline": 0.0, "chembl50_ef1_delta_vs_baseline": 1.77}},
        {"summary": {"candidate_fail_count": 0, "max_abs_delta_pr_auc": 0.0011}},
        {"summary": {"corrected_pass_folds": 7, "fold_count": 7, "default_feature_mask": "rg_sasa_only"}},
        {"summary": {"controlled_target_count": 7}},
        {"summary": {"status": "operator_packet_ready"}},
        {"summary": {"ready_row_count": 6}},
        {"summary": {"confirmed_commit_count": 3}},
        {"summary": {"ready_for_apply_row_count": 8}},
        {"summary": {"confirmed_commit_count": 4}},
        {"summary": {"manual_review_backlog_cleared": True, "top_blocker_signal": "placeholder_driven_rows=12; ready_for_apply_rows=0"}},
        {"summary": {"targets_with_placeholder_rows": 2, "current_phase": "blocker_closure_seed_row_promotion"}},
        {"summary": {"today_seed_target": "AQP1 core_binder_01", "top_blocker_signal": "placeholder_driven_rows=12; ready_for_apply_rows=0"}},
        {
            "summary": {
                "status": "controlled_shadow_only_commercial_pretest_completed_shadow_safe",
                "corrected_pass_folds": 6,
                "fold_count": 7,
                "default_feature_mask": "rg_sasa_only",
                "shadow_safe_retained": True,
                "blocker_reason": "tau_k18 fragility",
                "same_scope_reproducibility_confirmed": True,
                "additional_anchor_backed_target_count": 0,
                "page4_candidate_ready_now": True,
            }
        },
    )
    rows = {row["family"]: row for row in payload["rows"]}
    assert rows["idp"]["source_artifact"] == "runs/idp_commercial_pretest_decision_current.md"
    assert "shadow_safe=True" in rows["idp"]["strongest_signal"]
    assert rows["idp"]["remaining_blocker"] == "tau_k18 fragility"
    _contains_tokens(payload["summary"]["next_required_step"], "page4", "quantitative", "anchor", "replacement")


def test_build_domain_completion_status_keeps_glut1_packet_rollup_conservative_without_dashboard_fields() -> None:
    commercialization = {
        "summary": {"core_commercial_lane_score": 82.5, "all_category_expansion_score": 68.9},
        "rows": [
            {"family": "gpcr", "score": 82, "stage": "apply_safe_claim_lane", "status": "apply_safe_endpoint_ready_router_blocked", "claim_safe_scope": "locked-decoy equal-size shadow/apply endpoint", "primary_blocker": "router blocked", "source_artifact": "runs/gpcr_apply_safe_endpoint_current.md"},
            {"family": "ion_channel", "score": 88, "stage": "measured_family_commercial_lane", "status": "measured_noop_shadow_ready", "claim_safe_scope": "measured family", "primary_blocker": "none", "source_artifact": "runs/cross_family_locked_decoy_shadow_decision_current.md"},
            {"family": "kinase", "score": 90, "stage": "measured_family_commercial_lane", "status": "measured_noop_shadow_ready", "claim_safe_scope": "measured family", "primary_blocker": "none", "source_artifact": "runs/cross_family_locked_decoy_shadow_decision_current.md"},
            {"family": "idp", "score": 70, "stage": "subset_or_partial_authoritative_lane", "status": "literature_anchor_default_mask_ready", "claim_safe_scope": "subset only", "primary_blocker": "broader blocked", "source_artifact": "runs/idp_feature_state_subset_decision_current.md"},
            {"family": "non_kinase_enzyme_ca2", "score": 58, "stage": "manual_review_or_blocked_expansion_lane", "status": "partial_authoritative_rows_ready", "claim_safe_scope": "authoritative-ready rows 6/12", "primary_blocker": "review-only negatives", "source_artifact": "runs/ca2_packet_replacement_readiness_current.md"},
            {"family": "nuclear_receptor_pxr", "score": 62, "stage": "subset_or_partial_authoritative_lane", "status": "partial_authoritative_rows_ready", "claim_safe_scope": "authoritative-ready rows 8/14", "primary_blocker": "deferred rows", "source_artifact": "runs/pxr_packet_fill_readiness_current.md"},
            {"family": "transporter", "score": 32, "stage": "scaffold_only_lane", "status": "manual_review_only_first_wave_second_wave", "claim_safe_scope": "draft/manual-review only", "primary_blocker": "no authoritative rows", "source_artifact": "runs/transporter_manual_review_dashboard_current.md"},
        ],
    }
    payload = mod.build_payload(
        commercialization,
        {"summary": {"core_pr_delta_vs_baseline": 0.0, "chembl50_ef1_delta_vs_baseline": 1.77}},
        {"summary": {"candidate_fail_count": 0, "max_abs_delta_pr_auc": 0.0011}},
        {"summary": {"corrected_pass_folds": 7, "fold_count": 7, "default_feature_mask": "rg_sasa_only"}},
        {"summary": {"controlled_target_count": 7}},
        {"summary": {"status": "operator_packet_ready"}},
        {"summary": {"ready_row_count": 6}},
        {"summary": {"confirmed_commit_count": 3}},
        {"summary": {"ready_for_apply_row_count": 8}},
        {"summary": {"confirmed_commit_count": 4}},
        {"summary": {"manual_review_backlog_cleared": True, "top_blocker_signal": "placeholder_driven_rows=12; ready_for_apply_rows=0"}},
        {"summary": {"targets_with_placeholder_rows": 2, "current_phase": "blocker_closure_seed_row_promotion"}},
        {"summary": {"today_seed_target": "AQP1 core_binder_01", "top_blocker_signal": "placeholder_driven_rows=12; ready_for_apply_rows=0"}},
    )
    transporter_row = {row["family"]: row for row in payload["rows"]}["transporter"]
    assert "source confirmation" not in transporter_row["completion_note"].lower()
    assert "cytochalasin B" not in transporter_row["strongest_signal"]
    assert "glut1_direct_quantitative_binding_count" not in transporter_row["strongest_signal"]
    assert "glut1_second_wave_source_confirmation_packet_current.md" not in payload["summary"]["next_required_step"]
