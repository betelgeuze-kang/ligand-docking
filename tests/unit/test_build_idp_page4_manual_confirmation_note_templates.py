from __future__ import annotations

from tools import build_idp_page4_manual_confirmation_note_templates as mod


def test_build_idp_page4_manual_confirmation_note_templates() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {
                    "confirmation_item": "ph_low_freeze_confirmation",
                    "source_anchor": "PMID 26242913",
                    "suggested_manual_confirmation_decision": "accept_with_guardrails",
                    "guardrail_focus": "keep construct match explicit",
                    "reopen_effect_if_accepted": "supports low-state candidate review",
                },
                {
                    "confirmation_item": "ph_high_freeze_confirmation",
                    "source_anchor": "PMID 28289210",
                    "suggested_manual_confirmation_decision": "accept_with_guardrails",
                    "guardrail_focus": "avoid aggregation overcall",
                    "reopen_effect_if_accepted": "supports high-state candidate review",
                },
            ]
        }
    )
    s = payload["summary"]
    assert s["status"] == "page4_manual_confirmation_note_templates_ready"
    assert s["template_row_count"] == 2
    assert s["template_ready_count"] == 2
    assert "accept_with_guardrails" in payload["rows"][0]["manual_confirmation_note_template"]

