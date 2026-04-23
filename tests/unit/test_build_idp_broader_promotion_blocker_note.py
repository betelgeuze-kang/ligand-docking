from __future__ import annotations

from tools import build_idp_broader_promotion_blocker_note as mod


def _contains_tokens(text: str, *tokens: str) -> None:
    lowered = text.lower()
    for token in tokens:
        assert token.lower() in lowered


def test_build_idp_broader_promotion_blocker_note() -> None:
    payload = mod.build_payload(
        {"summary": {"broader_full_idp_promotion": False, "blocking_reason": "corrected-path fragility remains"}}
    )
    assert payload["summary"]["broader_promotion_blocked"] is True
    assert payload["summary"]["subset_safe_scope"] == "literature_anchor_subset_rg_sasa_only"
    assert payload["summary"]["operator_scope_now"] == "controlled_shadow_only_commercial_pretest"
    assert "corrected-path fragility remains" in payload["summary"]["blocker_reason"]


def test_build_idp_broader_promotion_blocker_note_prefers_commercial_decision() -> None:
    payload = mod.build_payload(
        {"summary": {"broader_full_idp_promotion": False, "blocking_reason": "legacy blocker"}},
        {
            "summary": {
                "broader_promotion_blocked": True,
                "operator_scope_now": "controlled_shadow_only_commercial_pretest",
                "shadow_safe_retained": True,
                "blocker_reason": "tau_k18 corrected-path fragility remains the blocker",
                "next_required_step": "Keep broader_full_idp_promotion blocked.",
            }
        },
        {"summary": {"blocker_reason": "failure-packet wording wins"}},
    )
    assert payload["summary"]["shadow_safe_retained"] is True
    assert payload["summary"]["blocker_reason"] == "failure-packet wording wins"
    _contains_tokens(payload["summary"]["next_required_step"], "broader_full_idp_promotion", "blocked")


def test_build_idp_broader_promotion_blocker_note_prefers_broader_shadow_decision() -> None:
    payload = mod.build_payload(
        {"summary": {"broader_full_idp_promotion": False, "blocking_reason": "legacy blocker"}},
        {"summary": {"broader_promotion_blocked": True, "operator_scope_now": "controlled_shadow_only_commercial_pretest", "shadow_safe_retained": True}},
        broader_shadow_result={"summary": {"true_broader_shadow_completed": True, "true_broader_shadow_passed": True, "page4_fold_pass": True, "tau_k18_fold_pass": True}},
        broader_shadow_decision={
            "summary": {
                "broader_promotion_blocked": True,
                "operator_scope_now": "controlled_shadow_only_commercial_pretest",
                "shadow_safe_retained": True,
                "blocker_reason": "broader shadow passed cleanly and now needs explicit promotion review",
                "next_required_step": "reopen explicit promotion review using the completed broader-shadow result",
            }
        },
    )
    assert payload["summary"]["broader_shadow_completed"] is True
    assert payload["summary"]["broader_shadow_passed"] is True
    assert payload["summary"]["page4_fold_pass"] is True
    assert payload["summary"]["tau_k18_fold_pass"] is True
    assert "explicit promotion review" in payload["summary"]["next_required_step"]


def test_build_idp_broader_promotion_blocker_note_surfaces_latest_diagnostic_observation() -> None:
    payload = mod.build_payload(
        {"summary": {"broader_full_idp_promotion": False, "blocking_reason": "legacy blocker"}},
        {"summary": {"broader_promotion_blocked": True, "operator_scope_now": "controlled_shadow_only_commercial_pretest", "shadow_safe_retained": True}},
        {"summary": {"blocker_reason": "tau_k18 corrected-path fragility remains the blocker"}},
        None,
        None,
        None,
        None,
        None,
        {"summary": {"diagnostic_rule_name": "short_tau_base_phlow_gate_trace_v1"}},
        {
            "summary": {
                "status": "single_slice_diagnostic_completed_blocker_persists",
                "diagnostic_rule_name": "short_tau_base_phlow_gate_trace_v1",
                "primary_observation": "short_tau_diagnostic_path_inactive_on_current_corrected_slice",
                "debug_columns_present_count": 2,
                "inactive_short_tau_diag_count": 2,
                "next_required_step": "Inspect why the short-tau diagnostic path stayed inactive on base/ph_low before choosing another corrected-path calibration rule.",
            }
        },
    )
    assert payload["summary"]["current_diagnostic_rule"] == "short_tau_base_phlow_gate_trace_v1"
    assert payload["summary"]["current_diagnostic_observation"] == "short_tau_diagnostic_path_inactive_on_current_corrected_slice"
    assert payload["summary"]["inactive_short_tau_diag_count"] == 2
    _contains_tokens(payload["summary"]["next_required_step"], "short-tau", "inactive", "calibration")


def test_build_idp_broader_promotion_blocker_note_surfaces_activation_follow_up() -> None:
    payload = mod.build_payload(
        {"summary": {"broader_full_idp_promotion": False, "blocking_reason": "legacy blocker"}},
        {"summary": {"broader_promotion_blocked": True, "operator_scope_now": "controlled_shadow_only_commercial_pretest", "shadow_safe_retained": True}},
        {"summary": {"blocker_reason": "tau_k18 corrected-path fragility remains the blocker"}},
        None,
        None,
        None,
        None,
        None,
        {"summary": {"diagnostic_rule_name": "short_tau_base_phlow_gate_trace_v1"}},
        {"summary": {"diagnostic_rule_name": "short_tau_base_phlow_gate_trace_v1", "primary_observation": "short_tau_diagnostic_path_inactive_on_current_corrected_slice"}},
        {"summary": {"activation_rule_name": "short_tau_diag_r16_activation_v1"}},
        {
            "summary": {
                "status": "activation_slice_completed_path_active",
                "activation_rule_name": "short_tau_diag_r16_activation_v1",
                "primary_observation": "short_tau_diagnostic_path_activated_on_focus_rows",
                "focus_condition_count": 2,
                "focus_condition_active_count": 2,
                "next_required_step": "Validate the same now-active short-tau path on a bounded commercial-pretest rerun before any broader rerun.",
            }
        },
    )
    assert payload["summary"]["current_activation_rule"] == "short_tau_diag_r16_activation_v1"
    assert payload["summary"]["current_activation_observation"] == "short_tau_diagnostic_path_activated_on_focus_rows"
    assert payload["summary"]["activation_focus_condition_active_count"] == 2
    _contains_tokens(payload["summary"]["next_required_step"], "bounded", "commercial-pretest", "rerun")


def test_build_idp_broader_promotion_blocker_note_prefers_validation_follow_up() -> None:
    payload = mod.build_payload(
        {"summary": {"broader_full_idp_promotion": False, "blocking_reason": "legacy blocker"}},
        {"summary": {"broader_promotion_blocked": True, "operator_scope_now": "controlled_shadow_only_commercial_pretest", "shadow_safe_retained": True}},
        {"summary": {"blocker_reason": "tau_k18 corrected-path fragility remains the blocker"}},
        None,
        None,
        None,
        None,
        None,
        {"summary": {"diagnostic_rule_name": "short_tau_base_phlow_gate_trace_v1"}},
        {"summary": {"diagnostic_rule_name": "short_tau_base_phlow_gate_trace_v1", "primary_observation": "short_tau_diagnostic_path_inactive_on_current_corrected_slice"}},
        {"summary": {"activation_rule_name": "short_tau_diag_r16_activation_v1"}},
        {"summary": {"status": "activation_slice_completed_path_active", "activation_rule_name": "short_tau_diag_r16_activation_v1", "primary_observation": "short_tau_diagnostic_path_activated_on_focus_rows", "focus_condition_count": 2, "focus_condition_active_count": 2}},
        {"summary": {"status": "bounded_commercial_pretest_completed_blocker_persists_activation_retained", "tau_k18_corrected_gate_pass": False, "corrected_pass_folds": 6, "fold_count": 7, "next_required_step": "Use the tau_k18 full-fold corrected failure slice to choose exactly one next corrected-path interpretation or calibration rule."}},
    )
    assert payload["summary"]["validation_status"] == "bounded_commercial_pretest_completed_blocker_persists_activation_retained"
    _contains_tokens(payload["summary"]["next_required_step"], "full-fold", "corrected", "failure", "slice")
