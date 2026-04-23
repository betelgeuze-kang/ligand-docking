from __future__ import annotations

from tools import build_wetlab_partner_target_portfolio as mod


def test_build_wetlab_partner_target_portfolio() -> None:
    payload = mod.build_payload()
    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["status"] == "wetlab_partner_target_portfolio_ready"
    assert summary["total_target_count"] == 14
    assert summary["wave1_count"] == 8
    assert summary["wave2_count"] == 5
    assert summary["validation_companion_count"] == 1
    assert "CA XII" in summary["next_required_step"]

    rows_by_target = {row["target_id"]: row for row in rows}
    assert rows_by_target["T. cruzi PDE"]["wave"] == "Wave 1"
    assert rows_by_target["T. cruzi PDE"]["total_priority_score"] == 13
    assert rows_by_target["SARS-CoV-2 Mpro"]["wave"] == "Wave 1"
    assert rows_by_target["CA XII"]["wave"] == "Validation Companion"
    assert rows_by_target["CA XII"]["repurposing_fit_score"] == 5
    assert rows_by_target["LRRK2"]["wave"] == "Wave 2"
