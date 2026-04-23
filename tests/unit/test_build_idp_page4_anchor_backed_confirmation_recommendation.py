from __future__ import annotations

from tools import build_idp_page4_anchor_backed_confirmation_recommendation as mod


def test_build_idp_page4_anchor_backed_confirmation_recommendation() -> None:
    payload = mod.build_payload(
        {"summary": {"status": "page4_anchor_backed_candidate_decision_pending_manual_confirmation"}},
        {
            "summary": {"pending_manual_confirmation_count": 2},
            "rows": [
                {"confirmation_item": "ph_low_freeze_confirmation", "staged_confirmation_decision": "accept_with_guardrails"},
                {"confirmation_item": "ph_high_freeze_confirmation", "staged_confirmation_decision": "accept_with_guardrails"},
            ],
        },
        {
            "summary": {"source_anchor": "PMID 26242913"},
            "rows": [
                {"fill_field": "ph_low_candidate_state_note", "freeze_guardrail": "do_not_import_into_base_or_hyperphosphorylated_state"},
                {"fill_field": "ph_low_candidate_compactness_note", "freeze_guardrail": "full_length_construct_and_state_explicit_only"},
            ],
        },
        {
            "summary": {"source_anchor": "PMID 28289210"},
            "rows": [
                {"fill_field": "ph_high_candidate_state_note", "freeze_guardrail": "do_not_mix_with_base_or_low_phosphorylation_state"},
                {"fill_field": "ph_high_candidate_aggregation_note", "freeze_guardrail": "do_not_convert_expanded_signal_into_true_aggregation_positive"},
            ],
        },
    )
    s = payload["summary"]
    assert s["status"] == "page4_anchor_backed_confirmation_recommendation_ready"
    assert s["recommendation_row_count"] == 2
    assert s["recommended_accept_with_guardrails_count"] == 2
    assert payload["rows"][0]["recommendation_status"] == "ready_for_manual_confirmation_review"

