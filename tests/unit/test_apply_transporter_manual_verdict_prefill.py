from __future__ import annotations

from tools.product import apply_transporter_manual_verdict_prefill as mod


def test_apply_prefill_copies_suggested_values() -> None:
    rows = [
        {
            "packet_step": "core_binder_01",
            "suggested_manual_verdict": "keep_review_only",
            "suggested_manual_confidence_update": "medium",
            "suggested_manual_decision_note": "note",
            "manual_verdict_update": "",
            "manual_confidence_update": "",
            "manual_decision_note": "",
            "update_status": "pending_manual_verdict",
        }
    ]

    updated_rows, updated = mod.apply_prefill(rows)

    assert updated == 1
    assert updated_rows[0]["manual_verdict_update"] == "keep_review_only"
    assert updated_rows[0]["manual_confidence_update"] == "medium"
    assert updated_rows[0]["manual_decision_note"] == "note"
    assert updated_rows[0]["update_status"] == "completed_manual_verdict"
