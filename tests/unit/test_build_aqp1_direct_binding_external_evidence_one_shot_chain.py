from __future__ import annotations

from unittest.mock import patch

from tools.accounting.build_aqp1_direct_binding_external_evidence_one_shot_chain import build_packet


def test_one_shot_chain_reports_blockers_when_claim_safe_missing() -> None:
    lane_payloads = {
        "runs/aqp1_direct_binding_external_evidence_operator_staging_apply_current.json": {
            "summary": {
                "status": "aqp1_operator_staging_apply_ready_for_live_copy",
                "live_apply_allowed": True,
                "live_copy_executed": True,
            }
        },
        "runs/aqp1_direct_binding_external_evidence_intake_current.json": {
            "summary": {
                "status": "aqp1_external_direct_binding_intake_blocked",
                "claim_safe_approved_count": 0,
            }
        },
        "runs/aqp1_ready_workbook_apply_current.json": {
            "summary": {"status": "aqp1_ready_workbook_apply_refreshed"},
        },
        "runs/transporter_aqp1_external_evidence_refresh_chain_current.json": {
            "summary": {
                "status": "transporter_aqp1_external_evidence_refresh_chain_refreshed_with_blockers",
                "blockers": ["aqp1:claim_safe_approved_rows_missing"],
                "aqp1_core_p0_open_count": 1,
            }
        },
    }

    def fake_read_json(path_like: str):
        key = str(path_like).replace("/home/betelgeuze/분자동역학/", "")
        if key not in lane_payloads and "/runs/" in str(path_like):
            key = "runs/" + str(path_like).split("/runs/", 1)[-1]
        return lane_payloads.get(key, {})

    with patch(
        "tools.accounting.build_aqp1_direct_binding_external_evidence_one_shot_chain._run"
    ), patch(
        "tools.accounting.build_aqp1_direct_binding_external_evidence_one_shot_chain._read_json",
        side_effect=fake_read_json,
    ):
        payload = build_packet(generated_at_local="2026-06-07T12:00:00+09:00")

    summary = payload["summary"]
    assert summary["status"] == "aqp1_direct_binding_external_evidence_one_shot_chain_refreshed_with_blockers"
    assert summary["live_apply_allowed"] is True
    assert summary["live_copy_executed"] is True
    assert summary["claim_safe_approved_count"] == 0
    assert "aqp1_one_shot:claim_safe_approved_rows_missing" in summary["blockers"]
