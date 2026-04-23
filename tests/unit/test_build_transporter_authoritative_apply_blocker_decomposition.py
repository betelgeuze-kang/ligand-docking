from __future__ import annotations

from tools import build_transporter_authoritative_apply_blocker_decomposition as mod


def test_build_transporter_authoritative_apply_blocker_decomposition() -> None:
    payload = mod.build_payload(
        {"summary": {"aqp1_keep_review_only_count": 3, "glut1_keep_review_only_count": 3}},
        {"summary": {"pending_manual_verdict_count": 0, "ready_for_apply_rows": 0, "placeholder_driven_rows": 12}},
        {"summary": {"reopen_ready": False, "blocked_check_count": 3, "scaffold_fit_donor_target": "EGFR_KINASE"}},
        {"summary": {"scaffold_fit_donor_target": "EGFR_KINASE"}},
        {"summary": {"p0_open_count": 9}},
        {"summary": {"manual_fields_committed_count": 3}},
        {"summary": {"manual_fields_committed_count": 3}},
        {"summary": {"ready_seed_row_count": 0}},
        {"summary": {"ready_seed_row_count": 0}},
    )

    assert payload["summary"]["blocker_count"] == 6
    assert payload["summary"]["hard_blocker_count"] == 5
    assert payload["summary"]["soft_blocker_count"] == 1
    assert payload["summary"]["manual_review_backlog_cleared"] is True
    assert payload["summary"]["authoritative_apply_ready"] is False
    assert payload["summary"]["top_blocker_id"] == "placeholder_packet_rows"
    assert payload["rows"][0]["current_signal"] == "placeholder_driven_rows=12; ready_for_apply_rows=0"
    assert payload["rows"][2]["current_signal"] == "reopen_ready=False; blocked_check_count=3; fit_donor=EGFR_KINASE"
