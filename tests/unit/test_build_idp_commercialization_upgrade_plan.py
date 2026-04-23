from __future__ import annotations

from tools import build_idp_commercialization_upgrade_plan as mod


def _contains_tokens(text: str, *tokens: str) -> None:
    lowered = text.lower()
    for token in tokens:
        assert token.lower() in lowered


def test_build_idp_commercialization_upgrade_plan() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "default_feature_mask": "rg_sasa_only",
                "fold_count": 7,
                "corrected_pass_folds": 7,
                "broader_full_idp_promotion": False,
            }
        },
        {"summary": {"allowed_now": "literature_anchor_subset_only", "blocked_now": "broader_full_idp_promotion"}},
        {"summary": {"blocker_reason": "tau_k18 corrected-path fragility"}},
        {"summary": {"default_feature_mask": "rg_sasa_only"}},
        {
            "rows": [
                {
                    "family": "idp",
                    "score": 70,
                    "stage": "subset_or_partial_authoritative_lane",
                    "status": "controlled_shadow_only_commercial_pretest_ready_broader_blocked",
                    "claim_safe_scope": "controlled shadow-only commercial-pretest lane built on a literature-anchor subset basis",
                }
            ]
        },
        {
            "summary": {
                "controlled_target_count": 7,
                "commercial_pretest_core_count": 4,
                "commercial_pretest_watchlist_count": 3,
            }
        },
        {"summary": {"row_count": 7}},
    )
    assert payload["summary"]["current_score"] == 70
    assert payload["summary"]["default_feature_mask"] == "rg_sasa_only"
    assert payload["summary"]["done_count"] == 1
    assert payload["summary"]["blocked_count"] == 3
    assert payload["summary"]["broader_anchor_scaffold_ready"] is True
    assert payload["summary"]["broader_anchor_scaffold_target_count"] == 7
    assert payload["summary"]["commercial_pretest_packet_ready"] is True
    assert payload["summary"]["commercial_pretest_packet_target_count"] == 7
    _contains_tokens(payload["summary"]["current_safe_scope"], "controlled", "commercial-pretest", "subset", "basis")
    _contains_tokens(payload["summary"]["next_required_step"], "validated", "subset", "controlled", "commercial-pretest")
    _contains_tokens(payload["rows"][1]["current_signal"], "legacy_note_scope", "operator_scope", "controlled_shadow_only_commercial_pretest")
    assert payload["rows"][2]["milestone_id"] == "complete_broader_shadow_review"


def test_build_idp_commercialization_upgrade_plan_prefers_commercial_decision() -> None:
    payload = mod.build_payload(
        {"summary": {"default_feature_mask": "rg_sasa_only", "fold_count": 7, "corrected_pass_folds": 7, "broader_full_idp_promotion": False}},
        {"summary": {"allowed_now": "literature_anchor_subset_only", "blocked_now": "broader_full_idp_promotion"}},
        {"summary": {"blocker_reason": "tau_k18 corrected-path fragility"}},
        {"summary": {"default_feature_mask": "rg_sasa_only"}},
        {"rows": [{"family": "idp", "score": 70, "stage": "subset_or_partial_authoritative_lane", "status": "controlled_shadow_only_commercial_pretest_ready_broader_blocked", "claim_safe_scope": "controlled shadow-only commercial-pretest lane built on a literature-anchor subset basis"}]},
        {"summary": {"controlled_target_count": 7, "commercial_pretest_core_count": 4, "commercial_pretest_watchlist_count": 3}},
        {"summary": {"row_count": 7}},
        {"summary": {"decision": "shadow_safe_retained_broader_promotion_blocked", "blocking_target": "tau_k18", "blocker_reason": "tau_k18 corrected-path fragility", "next_required_step": "move the next improvement to page4 quantitative anchor replacement before any true broader rerun", "same_scope_reproducibility_confirmed": True, "page4_candidate_ready_now": True}},
        {"summary": {"failure_anchor_target": "tau_k18"}},
    )
    assert payload["summary"]["commercial_pretest_decision_ready"] is True
    assert "commercial_decision=shadow_safe_retained_broader_promotion_blocked" in payload["rows"][3]["current_signal"]
    _contains_tokens(payload["summary"]["next_required_step"], "page4", "quantitative", "anchor", "replacement")
    _contains_tokens(payload["rows"][3]["next_evidence_needed"], "page4", "quantitative", "anchor", "replacement")


def test_build_idp_commercialization_upgrade_plan_surfaces_diagnostic_inactive_path() -> None:
    payload = mod.build_payload(
        {"summary": {"default_feature_mask": "rg_sasa_only", "fold_count": 7, "corrected_pass_folds": 6, "broader_full_idp_promotion": False}},
        {"summary": {"allowed_now": "literature_anchor_subset_only", "blocked_now": "broader_full_idp_promotion"}},
        {
            "summary": {
                "blocker_reason": "tau_k18 corrected-path fragility remains the blocker",
                "current_diagnostic_rule": "short_tau_base_phlow_gate_trace_v1",
                "current_diagnostic_status": "single_slice_diagnostic_completed_blocker_persists",
                "current_diagnostic_observation": "short_tau_diagnostic_path_inactive_on_current_corrected_slice",
                "inactive_short_tau_diag_count": 2,
                "debug_columns_present_count": 2,
                "next_required_step": "Inspect why the short-tau diagnostic path stayed inactive on base/ph_low before choosing another corrected-path calibration rule.",
            }
        },
        {"summary": {"default_feature_mask": "rg_sasa_only"}},
        {"rows": [{"family": "idp", "score": 70, "stage": "subset_or_partial_authoritative_lane", "status": "controlled_shadow_only_commercial_pretest_completed_shadow_safe", "claim_safe_scope": "controlled shadow-only commercial-pretest lane built on a literature-anchor subset basis"}]},
        {"summary": {"controlled_target_count": 7, "commercial_pretest_core_count": 4, "commercial_pretest_watchlist_count": 3}},
        {"summary": {"row_count": 7}},
        {"summary": {"decision": "shadow_safe_retained_broader_promotion_blocked", "blocking_target": "tau_k18", "blocker_reason": "tau_k18 corrected-path fragility"}},
    )
    signal = payload["rows"][2]["current_signal"]
    assert "diagnostic_rule=short_tau_base_phlow_gate_trace_v1" in signal
    assert "diagnostic_observation=short_tau_diagnostic_path_inactive_on_current_corrected_slice" in signal
    assert "diagnostic_inactive_count=2" in signal
    _contains_tokens(payload["rows"][2]["next_evidence_needed"], "promotion", "roster", "guardrails", "review")


def test_build_idp_commercialization_upgrade_plan_surfaces_activation_follow_up() -> None:
    payload = mod.build_payload(
        {"summary": {"default_feature_mask": "rg_sasa_only", "fold_count": 7, "corrected_pass_folds": 6, "broader_full_idp_promotion": False}},
        {"summary": {"allowed_now": "literature_anchor_subset_only", "blocked_now": "broader_full_idp_promotion"}},
        {
            "summary": {
                "blocker_reason": "tau_k18 corrected-path fragility remains the blocker",
                "current_diagnostic_rule": "short_tau_base_phlow_gate_trace_v1",
                "current_diagnostic_status": "single_slice_diagnostic_completed_blocker_persists",
                "current_diagnostic_observation": "short_tau_diagnostic_path_inactive_on_current_corrected_slice",
                "inactive_short_tau_diag_count": 2,
                "debug_columns_present_count": 2,
                "current_activation_rule": "short_tau_diag_r16_activation_v1",
                "current_activation_status": "activation_slice_completed_path_active",
                "current_activation_observation": "short_tau_diagnostic_path_activated_on_focus_rows",
                "activation_focus_condition_active_count": 2,
                "next_required_step": "Use the broader-shadow review packet to lock policy, roster, and guardrails before any broader rerun.",
            }
        },
        {"summary": {"default_feature_mask": "rg_sasa_only"}},
        {"rows": [{"family": "idp", "score": 70, "stage": "subset_or_partial_authoritative_lane", "status": "controlled_shadow_only_commercial_pretest_completed_shadow_safe", "claim_safe_scope": "controlled shadow-only commercial-pretest lane built on a literature-anchor subset basis"}]},
        {"summary": {"controlled_target_count": 7, "commercial_pretest_core_count": 4, "commercial_pretest_watchlist_count": 3}},
        {"summary": {"row_count": 7}},
        {"summary": {"decision": "shadow_safe_retained_broader_promotion_blocked", "blocking_target": "tau_k18", "blocker_reason": "tau_k18 corrected-path fragility"}},
        {"summary": {"status": "bounded_commercial_pretest_completed_blocker_persists_activation_retained", "tau_k18_corrected_gate_pass": False}},
        {"summary": {"failure_anchor_target": "tau_k18"}},
        None,
        None,
        None,
        {"summary": {"activation_rule_name": "short_tau_diag_r16_activation_v1"}},
        {"summary": {"status": "activation_slice_completed_path_active"}},
    )
    signal = payload["rows"][2]["current_signal"]
    assert "activation_rule=short_tau_diag_r16_activation_v1" in signal
    assert "activation_status=activation_slice_completed_path_active" in signal
    assert "activation_active_count=2" in signal
    assert "validation_status=bounded_commercial_pretest_completed_blocker_persists_activation_retained" in signal
    assert payload["summary"]["activation_packet_ready"] is True
    assert payload["summary"]["activation_result_ready"] is True
    assert payload["summary"]["validation_result_ready"] is True
    _contains_tokens(payload["summary"]["next_required_step"], "broader-shadow", "review", "broader", "rerun")


def test_build_idp_commercialization_upgrade_plan_surfaces_completed_broader_shadow() -> None:
    payload = mod.build_payload(
        {"summary": {"default_feature_mask": "rg_sasa_only", "fold_count": 7, "corrected_pass_folds": 7, "broader_full_idp_promotion": False}},
        {"summary": {"allowed_now": "literature_anchor_subset_only", "blocked_now": "broader_full_idp_promotion"}},
        {"summary": {"blocker_reason": "broader shadow passed and now needs explicit promotion review"}},
        {"summary": {"default_feature_mask": "rg_sasa_only"}},
        {"rows": [{"family": "idp", "score": 70, "stage": "subset_or_partial_authoritative_lane", "status": "controlled_shadow_only_commercial_pretest_broader_shadow_completed", "claim_safe_scope": "controlled shadow-only commercial-pretest lane built on a literature-anchor subset basis"}]},
        {"summary": {"controlled_target_count": 8, "commercial_pretest_core_count": 4, "commercial_pretest_watchlist_count": 4}},
        {"summary": {"row_count": 8}},
        {"summary": {"decision": "shadow_safe_retained_promotion_review_required", "next_required_step": "legacy next step"}},
        broader_shadow_result={"summary": {"true_broader_shadow_passed": True}},
        broader_shadow_decision={"summary": {"decision": "broader_shadow_passed_promotion_review_reopen", "next_required_step": "reopen explicit promotion review using the completed broader-shadow result"}},
    )
    assert payload["summary"]["broader_shadow_result_ready"] is True
    assert payload["summary"]["broader_shadow_decision_ready"] is True
    assert payload["rows"][2]["status"] == "done"
    assert payload["rows"][3]["status"] == "review_now"
    _contains_tokens(payload["rows"][3]["current_signal"], "broader_shadow_passed=True")
    _contains_tokens(payload["rows"][3]["next_evidence_needed"], "explicit", "promotion", "review")
