from __future__ import annotations

from tools.product import build_transporter_donor_policy_reopen_checklist as mod


def test_build_transporter_donor_policy_reopen_checklist() -> None:
    payload = mod.build_payload(
        {"summary": {"decision_status": "scaffold_default_keep_existing_fit_donor_pool", "scaffold_fit_donor_target": "EGFR_KINASE"}},
        {"summary": {"defer_binder_count": 3}},
        {"summary": {"keep_review_only_count": 3}},
        {"summary": {"defer_binder_count": 3}},
        {"summary": {"keep_review_only_count": 3}},
        {"summary": {"p0_open_count": 9}},
        {"summary": {"placeholder_driven_rows": 0, "staged_non_authoritative_rows": 6, "ready_for_apply_rows": 6}},
        {"summary": {"binder_promotion_ready": False, "primary_blocker_signal": "claim_safe_kcal_ready_count=0;workbook_ready_binder_row_count=0;authoritative_binder_apply_allowed_count=0"}},
    )

    assert payload["summary"]["reopen_ready"] is False
    assert payload["summary"]["blocked_check_count"] == 2
    assert payload["rows"][0]["status"] == "ready"
    assert payload["rows"][0]["current_value"] == "placeholder_driven_rows=0; staged_non_authoritative_rows=6; ready_for_apply_rows=6"
    assert payload["rows"][1]["current_value"] == 9
    assert payload["rows"][2]["current_value"] == "claim_safe_kcal_ready_count=0;workbook_ready_binder_row_count=0;authoritative_binder_apply_allowed_count=0"
