from __future__ import annotations

from tools.wetlab import build_wetlab_wave1_target_packets as mod


def test_build_wetlab_wave1_target_packets() -> None:
    payload = mod.build_payload()
    summary = payload["summary"]
    rows = {row["target_id"]: row for row in payload["rows"]}

    assert summary["status"] == "wetlab_wave1_target_packets_ready"
    assert summary["row_count"] == 8
    assert rows["CA IX"]["partner_track"] == "oncology_condition_aware"
    assert "human PDE" in rows["T. cruzi PDE"]["anti_target_selectivity_panel"]
    assert "crowded" in rows["SARS-CoV-2 Mpro"]["main_external_lab_objection"]
