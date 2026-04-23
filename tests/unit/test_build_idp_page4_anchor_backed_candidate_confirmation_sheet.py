from __future__ import annotations

from tools import build_idp_page4_anchor_backed_candidate_confirmation_sheet as mod


def test_build_idp_page4_anchor_backed_candidate_confirmation_sheet() -> None:
    payload = mod.build_payload(
        {"summary": {"status": "page4_anchor_backed_candidate_decision_pending_manual_confirmation"}},
        {"summary": {"source_anchor": "PMID 26242913"}},
        {"summary": {"source_anchor": "PMID 28289210"}},
        {},
    )
    s = payload["summary"]
    assert s["status"] == "page4_anchor_backed_candidate_confirmation_sheet_ready"
    assert s["confirmation_row_count"] == 2
    assert s["pending_manual_confirmation_count"] == 2
    assert payload["rows"][0]["confirmation_status"] == "ready_for_manual_confirmation"


def test_build_idp_page4_anchor_backed_candidate_confirmation_sheet_applies_resolution() -> None:
    payload = mod.build_payload(
        {"summary": {"status": "page4_anchor_backed_candidate_decision_pending_manual_confirmation"}},
        {"summary": {"source_anchor": "PMID 26242913"}},
        {"summary": {"source_anchor": "PMID 28289210"}},
        {
            "summary": {"status": "page4_manual_confirmation_resolution_ready"},
            "rows": [
                {
                    "confirmation_item": "ph_low_freeze_confirmation",
                    "manual_confirmation_decision": "accept_with_guardrails",
                    "manual_confirmation_note": "low accepted",
                    "manual_confirmation_actor": "assistant_curated_from_literature",
                },
                {
                    "confirmation_item": "ph_high_freeze_confirmation",
                    "manual_confirmation_decision": "accept_with_guardrails",
                    "manual_confirmation_note": "high accepted",
                    "manual_confirmation_actor": "assistant_curated_from_literature",
                },
            ],
        },
    )
    s = payload["summary"]
    assert s["status"] == "page4_anchor_backed_candidate_confirmation_sheet_resolved"
    assert s["pending_manual_confirmation_count"] == 0
    assert s["confirmed_accept_with_guardrails_count"] == 2
    assert s["anchor_backed_candidate_ready_now"] is True
    assert payload["rows"][0]["confirmation_status"] == "assistant_confirmed_with_guardrails"
