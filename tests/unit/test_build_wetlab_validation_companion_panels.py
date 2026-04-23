from __future__ import annotations

from tools import build_wetlab_partner_target_portfolio as portfolio_mod
from tools import build_wetlab_validation_companion_panels as mod


def test_build_wetlab_validation_companion_panels() -> None:
    payload = mod.build_payload(portfolio_mod.build_payload())
    summary = payload["summary"]
    rows = {row["target_id"]: row for row in payload["rows"]}

    assert summary["status"] == "wetlab_validation_companion_panels_ready"
    assert summary["row_count"] == 13
    assert summary["artifact_role"] == "per_target_selectivity_and_companion_panels"
    assert rows["CA IX"]["primary_companion_panel"] == "CA II plus CA XII counterscreen"
    assert rows["SARS-CoV-2 PLpro"]["wave"] == "Wave 1"
    assert rows["Cathepsin K"]["primary_companion_panel"] == "cathepsin-family / acidic-pH specificity panel"
    assert "Acidic protease stories need class selectivity and condition specificity together." == rows["Cathepsin K"]["companion_why"]
