from __future__ import annotations

from tools import build_idp_broader_shadow_rerun_draft_packet as mod


def test_build_idp_broader_shadow_rerun_draft_packet() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "status": "broader_shadow_review_packet_ready_no_true_broader_roster",
                "operator_scope_now": "controlled_shadow_only_commercial_pretest",
                "broader_promotion_blocked": True,
                "shadow_safe_retained": True,
                "bounded_validation_status": "bounded_commercial_pretest_completed_activation_retained",
                "bounded_validation_pass_folds": "7/7",
                "review_item_count": 4,
            },
            "rows": [
                {"review_item": "promotion_policy", "status": "review_now", "current_signal": "shadow_safe_retained_promotion_review_required"},
                {"review_item": "target_roster", "status": "review_now", "current_signal": "controlled_target_count=7"},
                {"review_item": "guardrail_freeze", "status": "keep_frozen", "current_signal": "feature_state_smoothing_only; no_coordinate_correction; no_ranking_override; no_gate_override"},
                {"review_item": "success_criteria", "status": "review_now", "current_signal": "corrected_pass_folds=7/7; tau_k18_corrected_gate_pass=True"},
            ],
        },
        {
            "summary": {
                "operator_scope_now": "controlled_shadow_only_commercial_pretest",
                "broader_promotion_blocked": True,
                "shadow_safe_retained": True,
                "default_feature_mask": "rg_sasa_only",
            }
        },
        {
            "summary": {
                "status": "bounded_commercial_pretest_completed_activation_retained",
                "corrected_pass_folds": 7,
                "fold_count": 7,
            }
        },
        {
            "summary": {
                "additional_anchor_backed_target_count": 0,
                "provisional_only_target_count": 13,
            }
        },
    )
    s = payload["summary"]
    assert s["status"] == "broader_shadow_rerun_draft_blocked_no_true_broader_roster"
    assert s["unresolved_review_item_count"] == 3
    assert s["frozen_guardrail_count"] == 4
    assert s["command_template_ready"] is True
    assert s["true_broader_rerun_ready"] is False
    assert s["same_scope_process_check_ready"] is True
    assert "IDP_R17_TAU_PH_SPLIT_PATCH=1" in s["command_template"]
    assert "IDP_R18_TAU_PH_HELIX_RECOVERY_PATCH=1" in s["command_template"]
    assert "<broader_anchor_backed_config.json>" in s["command_template"]
    assert "idp_3bead_benchmark_v7_literature_anchor_subset.json" in s["same_scope_process_check_command"]
    rows = {row["draft_step"]: row for row in payload["rows"]}
    assert rows["guardrails"]["status"] == "frozen"
    assert rows["execution_template"]["ready_now"] is True
    assert rows["target_roster"]["status"] == "blocked_no_true_broader_roster"
    assert rows["same_scope_process_check"]["status"] == "ready_now"


def test_build_idp_broader_shadow_rerun_draft_packet_when_true_broader_roster_exists() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "status": "broader_shadow_review_packet_ready_true_broader_roster_available",
                "operator_scope_now": "controlled_shadow_only_commercial_pretest",
                "broader_promotion_blocked": True,
                "shadow_safe_retained": True,
                "bounded_validation_status": "bounded_commercial_pretest_completed_activation_retained",
                "bounded_validation_pass_folds": "7/7",
                "review_item_count": 4,
            },
            "rows": [
                {"review_item": "promotion_policy", "status": "review_now", "current_signal": "shadow_safe_retained_promotion_review_required"},
                {"review_item": "target_roster", "status": "review_now", "current_signal": "controlled_target_count=7; additional_anchor_backed_target_count=1"},
                {"review_item": "guardrail_freeze", "status": "keep_frozen", "current_signal": "feature_state_smoothing_only; no_coordinate_correction; no_ranking_override; no_gate_override"},
                {"review_item": "success_criteria", "status": "review_now", "current_signal": "corrected_pass_folds=7/7; tau_k18_corrected_gate_pass=True"},
            ],
        },
        {
            "summary": {
                "operator_scope_now": "controlled_shadow_only_commercial_pretest",
                "broader_promotion_blocked": True,
                "shadow_safe_retained": True,
                "default_feature_mask": "rg_sasa_only",
            }
        },
        {
            "summary": {
                "status": "bounded_commercial_pretest_completed_activation_retained",
                "corrected_pass_folds": 7,
                "fold_count": 7,
            }
        },
        {
            "summary": {
                "additional_anchor_backed_target_count": 1,
                "provisional_only_target_count": 12,
            }
        },
    )
    s = payload["summary"]
    assert s["status"] == "broader_shadow_rerun_draft_blocked_pending_review"
    assert s["true_broader_rerun_ready"] is True
    assert s["same_scope_process_check_ready"] is True
    assert "instantiate this draft with the first broader anchor-backed config" in s["next_required_step"]
    rows = {row["draft_step"]: row for row in payload["rows"]}
    assert rows["target_roster"]["status"] == "review_required"
    assert rows["same_scope_process_check"]["status"] == "optional_fallback"
