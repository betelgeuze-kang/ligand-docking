from __future__ import annotations

from tools import build_idp_page4_manual_confirmation_console as mod


def test_build_idp_page4_manual_confirmation_console() -> None:
    payload = mod.build_payload(
        {"summary": {"status": "page4_manual_confirmation_launch_packet_ready", "pending_manual_confirmation_count": 2}},
        {"summary": {"status": "page4_manual_confirmation_workbench_ready"}},
        {"summary": {"status": "page4_anchor_backed_confirmation_recommendation_ready"}},
        {"summary": {"status": "page4_manual_confirmation_note_templates_ready"}},
        {"summary": {"status": "page4_anchor_backed_candidate_confirmation_sheet_ready", "pending_manual_confirmation_count": 2}},
        {"summary": {"status": "page4_anchor_backed_promotion_review_pending_manual_confirmation"}},
    )
    s = payload["summary"]
    assert s["status"] == "page4_manual_confirmation_console_ready"
    assert s["launch_packet_ready"] is True
    assert s["workbench_ready"] is True
    assert s["recommendation_ready"] is True
    assert s["note_templates_ready"] is True
    assert s["confirmation_sheet_ready"] is True
    assert s["promotion_review_ready"] is True
    assert s["pending_manual_confirmation_count"] == 2
    assert payload["rows"][0]["step_id"] == "open_workbench"


def test_build_idp_page4_manual_confirmation_console_resolved() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "status": "page4_manual_confirmation_launch_packet_resolved",
                "pending_manual_confirmation_count": 0,
                "confirmed_accept_with_guardrails_count": 2,
            }
        },
        {"summary": {"status": "page4_manual_confirmation_workbench_resolved"}},
        {"summary": {"status": "page4_anchor_backed_confirmation_recommendation_ready"}},
        {"summary": {"status": "page4_manual_confirmation_note_templates_ready"}},
        {"summary": {"status": "page4_anchor_backed_candidate_confirmation_sheet_resolved", "pending_manual_confirmation_count": 0, "confirmed_accept_with_guardrails_count": 2}},
        {"summary": {"status": "page4_anchor_backed_promotion_review_ready_for_candidate_promotion", "anchor_backed_candidate_ready_now": True}},
    )
    s = payload["summary"]
    assert s["status"] == "page4_manual_confirmation_console_resolved"
    assert s["pending_manual_confirmation_count"] == 0
    assert s["confirmed_accept_with_guardrails_count"] == 2
    assert s["anchor_backed_candidate_ready_now"] is True
