from __future__ import annotations

from tools import build_idp_broader_shadow_review_packet as mod


def _contains_tokens(text: str, *tokens: str) -> None:
    lowered = text.lower()
    for token in tokens:
        assert token.lower() in lowered


def test_build_idp_broader_shadow_review_packet_prefers_page4_quantitative_anchor_replacement() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "decision": "shadow_safe_retained_promotion_review_required",
                "operator_scope_now": "controlled_shadow_only_commercial_pretest",
                "broader_promotion_blocked": True,
                "shadow_safe_retained": True,
                "same_scope_reproducibility_confirmed": True,
                "page4_candidate_ready_now": True,
            }
        },
        {"summary": {"status": "bounded_commercial_pretest_completed_activation_retained", "corrected_pass_folds": 7, "fold_count": 7, "tau_k18_corrected_gate_pass": True}},
        {"summary": {"controlled_target_count": 7}},
        {"summary": {"additional_anchor_backed_target_count": 0, "provisional_only_target_count": 13}},
    )

    summary = payload["summary"]
    assert summary["status"] == "broader_shadow_review_packet_ready_no_true_broader_roster"
    assert summary["page4_candidate_ready_now"] is True
    assert summary["next_anchor_curation_target"] == "page4_quantitative_anchor_replacement"
    _contains_tokens(summary["next_required_step"], "page4", "quantitative", "anchor", "replacement")


def test_build_idp_broader_shadow_review_packet_keeps_same_scope_or_new_anchor_when_page4_not_ready() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "decision": "shadow_safe_retained_promotion_review_required",
                "operator_scope_now": "controlled_shadow_only_commercial_pretest",
                "broader_promotion_blocked": True,
                "shadow_safe_retained": True,
                "same_scope_reproducibility_confirmed": False,
                "page4_candidate_ready_now": False,
            }
        },
        {"summary": {"status": "bounded_commercial_pretest_completed_activation_retained", "corrected_pass_folds": 7, "fold_count": 7, "tau_k18_corrected_gate_pass": True}},
        {"summary": {"controlled_target_count": 7}},
        {"summary": {"additional_anchor_backed_target_count": 0, "provisional_only_target_count": 13}},
    )

    summary = payload["summary"]
    assert summary["next_anchor_curation_target"] == "same_scope_process_check_or_new_anchor"
    _contains_tokens(summary["next_required_step"], "same-scope", "process", "check")
