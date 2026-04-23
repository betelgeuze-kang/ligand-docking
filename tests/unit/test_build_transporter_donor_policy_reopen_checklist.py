from __future__ import annotations

from tools import build_transporter_donor_policy_reopen_checklist as mod


def test_build_transporter_donor_policy_reopen_checklist() -> None:
    payload = mod.build_payload(
        {"summary": {"decision_status": "scaffold_default_keep_existing_fit_donor_pool", "scaffold_fit_donor_target": "EGFR_KINASE"}},
        {"summary": {"defer_binder_count": 3}},
        {"summary": {"keep_review_only_count": 3}},
        {"summary": {"defer_binder_count": 3}},
        {"summary": {"keep_review_only_count": 3}},
        {"summary": {"p0_open_count": 9}},
    )

    assert payload["summary"]["reopen_ready"] is False
    assert payload["summary"]["blocked_check_count"] == 3
    assert payload["rows"][0]["status"] == "blocked"
    assert payload["rows"][1]["current_value"] == 9
