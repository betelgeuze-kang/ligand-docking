from __future__ import annotations

from tools import build_transporter_binder_verdict_progress as mod


def _contains_tokens(text: str, *tokens: str) -> None:
    lowered = text.lower()
    for token in tokens:
        assert token.lower() in lowered


def test_build_transporter_binder_verdict_progress() -> None:
    payload = mod.build_payload(
        {"summary": {"binder_slot_count": 3, "suggested_prefill_count": 3, "pending_manual_verdict_count": 3, "completed_manual_verdict_count": 0}},
        {"summary": {"binder_slot_count": 3, "suggested_prefill_count": 2, "pending_manual_verdict_count": 2, "completed_manual_verdict_count": 1}},
    )

    assert payload["summary"]["family_count"] == 2
    assert payload["summary"]["binder_slot_count"] == 6
    assert payload["summary"]["suggested_prefill_count"] == 5
    assert payload["summary"]["pending_manual_verdict_count"] == 5
    assert payload["summary"]["completed_manual_verdict_count"] == 1


def test_build_transporter_binder_verdict_progress_switches_next_step_when_backlog_is_cleared() -> None:
    payload = mod.build_payload(
        {"summary": {"binder_slot_count": 3, "suggested_prefill_count": 3, "pending_manual_verdict_count": 0, "completed_manual_verdict_count": 3}},
        {"summary": {"binder_slot_count": 3, "suggested_prefill_count": 3, "pending_manual_verdict_count": 0, "completed_manual_verdict_count": 3}},
    )
    assert payload["summary"]["pending_manual_verdict_count"] == 0
    _contains_tokens(payload["summary"]["next_required_step"], "seed-row", "promotion")
