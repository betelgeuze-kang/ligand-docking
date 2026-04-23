from __future__ import annotations

from tools import build_wetlab_neglected_wave1_rows as mod


def test_build_wetlab_neglected_wave1_rows() -> None:
    payload = mod.build_payload()
    summary = payload["summary"]
    rows = {row["target_id"]: row for row in payload["rows"]}

    assert summary["status"] == "wetlab_neglected_wave1_rows_ready"
    assert summary["target_count"] == 3
    assert summary["partner_track"] == "DNDi_IPK"
    assert "human PDE family mini-panel" in rows["T. cruzi PDE"]["anti_target_selectivity_panel"]
    assert "thiol-reactivity and aggregation filters" in rows["Cruzain"]["anti_target_selectivity_panel"]
    assert "host DHODH counterscreen" in rows["Leishmania braziliensis DHODH"]["anti_target_selectivity_panel"]
