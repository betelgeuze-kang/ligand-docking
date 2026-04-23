from __future__ import annotations

from tools import build_idp_page4_manual_confirmation_workbench as mod


def test_build_idp_page4_manual_confirmation_workbench() -> None:
    payload = mod.build_payload(
        {
            "summary": {"status": "page4_anchor_backed_confirmation_recommendation_ready"},
            "rows": [
                {
                    "confirmation_item": "ph_low_freeze_confirmation",
                    "source_anchor": "PMID 26242913",
                    "suggested_manual_confirmation_decision": "accept_with_guardrails",
                    "guardrail_focus": "keep low state separate",
                    "supporting_guardrails": "g1 ; g2",
                },
                {
                    "confirmation_item": "ph_high_freeze_confirmation",
                    "source_anchor": "PMID 28289210",
                    "suggested_manual_confirmation_decision": "accept_with_guardrails",
                    "guardrail_focus": "keep high state separate",
                    "supporting_guardrails": "g3 ; g4",
                },
            ],
        },
        {
            "summary": {"pending_manual_confirmation_count": 2},
            "rows": [
                {"confirmation_item": "ph_low_freeze_confirmation", "staged_confirmation_note": "low note", "confirmation_status": "ready_for_manual_confirmation"},
                {"confirmation_item": "ph_high_freeze_confirmation", "staged_confirmation_note": "high note", "confirmation_status": "ready_for_manual_confirmation"},
            ],
        },
        {
            "summary": {"promotion_review_ready": True},
            "rows": [
                {"promotion_item": "ph_low_confirmation", "promotion_effect_if_accepted": "low effect"},
                {"promotion_item": "ph_high_confirmation", "promotion_effect_if_accepted": "high effect"},
            ],
        },
    )
    s = payload["summary"]
    assert s["status"] == "page4_manual_confirmation_workbench_ready"
    assert s["review_row_count"] == 2
    assert s["pending_manual_confirmation_count"] == 2
    assert payload["rows"][0]["confirmation_item"] == "ph_low_freeze_confirmation"


def test_build_idp_page4_manual_confirmation_workbench_resolved() -> None:
    payload = mod.build_payload(
        {
            "summary": {"status": "page4_anchor_backed_confirmation_recommendation_ready"},
            "rows": [
                {"confirmation_item": "ph_low_freeze_confirmation", "source_anchor": "PMID 26242913", "suggested_manual_confirmation_decision": "accept_with_guardrails"},
                {"confirmation_item": "ph_high_freeze_confirmation", "source_anchor": "PMID 28289210", "suggested_manual_confirmation_decision": "accept_with_guardrails"},
            ],
        },
        {
            "summary": {
                "pending_manual_confirmation_count": 0,
                "confirmed_accept_with_guardrails_count": 2,
            },
            "rows": [
                {
                    "confirmation_item": "ph_low_freeze_confirmation",
                    "staged_confirmation_note": "low note",
                    "manual_confirmation_decision": "accept_with_guardrails",
                    "confirmation_status": "assistant_confirmed_with_guardrails",
                },
                {
                    "confirmation_item": "ph_high_freeze_confirmation",
                    "staged_confirmation_note": "high note",
                    "manual_confirmation_decision": "accept_with_guardrails",
                    "confirmation_status": "assistant_confirmed_with_guardrails",
                },
            ],
        },
        {"summary": {"promotion_review_ready": True, "anchor_backed_candidate_ready_now": True}, "rows": []},
    )
    s = payload["summary"]
    assert s["status"] == "page4_manual_confirmation_workbench_resolved"
    assert s["pending_manual_confirmation_count"] == 0
    assert s["confirmed_accept_with_guardrails_count"] == 2
    assert s["anchor_backed_candidate_ready_now"] is True
