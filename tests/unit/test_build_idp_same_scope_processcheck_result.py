from __future__ import annotations

from tools import build_idp_same_scope_processcheck_result as mod


def test_build_idp_same_scope_processcheck_result_running_when_no_summary() -> None:
    payload = mod.build_payload({}, {}, {})
    assert payload["summary"]["status"] == "same_scope_processcheck_running_or_not_yet_summarized"
    assert payload["summary"]["summary_exists"] is False
    assert "same-scope process check" in payload["summary"]["next_required_step"]


def test_build_idp_same_scope_processcheck_result_confirms_reproducibility() -> None:
    payload = mod.build_payload(
        {"fold_count": 7, "corrected_pass_folds": 7, "combined_gate_pass": True},
        {"pass": True},
        {
            "kalman_shadow": {
                "feature_mask_name": "rg_sasa_only",
                "would_change_state_count": 0,
                "would_change_gate_count": 0,
                "would_change_llps_flag_count": 0,
                "would_change_aggregation_flag_count": 0,
            }
        },
        {"summary": {"anchor_backed_candidate_ready_now": True}},
        {"summary": {"additional_anchor_backed_target_count": 0}},
    )
    assert payload["summary"]["status"] == "same_scope_processcheck_completed_reproducibility_confirmed"
    assert payload["summary"]["shadow_safe_retained"] is True
    assert payload["summary"]["page4_candidate_ready_now"] is True
    assert payload["summary"]["next_anchor_curation_target"] == "page4_quantitative_anchor_replacement"
    assert "page4 quantitative anchor replacement" in payload["summary"]["next_required_step"]


def test_build_idp_same_scope_processcheck_result_prefers_broader_review_when_page4_replacement_completed() -> None:
    payload = mod.build_payload(
        {"fold_count": 7, "corrected_pass_folds": 7, "combined_gate_pass": True},
        {"pass": True},
        {
            "kalman_shadow": {
                "feature_mask_name": "rg_sasa_only",
                "would_change_state_count": 0,
                "would_change_gate_count": 0,
                "would_change_llps_flag_count": 0,
                "would_change_aggregation_flag_count": 0,
            }
        },
        {"summary": {"anchor_backed_candidate_ready_now": True}},
        {"summary": {"additional_anchor_backed_target_count": 1}},
    )
    assert payload["summary"]["status"] == "same_scope_processcheck_completed_reproducibility_confirmed"
    assert payload["summary"]["additional_anchor_backed_target_count"] == 1
    assert payload["summary"]["next_anchor_curation_target"] == "true_broader_rerun_review"
    assert "reopen broader shadow review" in payload["summary"]["next_required_step"]
