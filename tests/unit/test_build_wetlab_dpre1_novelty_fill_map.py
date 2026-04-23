from __future__ import annotations

from tools import build_wetlab_dpre1_novelty_fill_map as mod
from tools import build_wetlab_dpre1_repurposing_fill_map as rep_mod


def test_build_wetlab_dpre1_novelty_fill_map() -> None:
    rep_payload = rep_mod.build_payload()
    payload = mod.build_payload(rep_payload)
    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["status"] == "wetlab_dpre1_novelty_fill_map_ready"
    assert summary["row_count"] == 3
    assert [row["novelty_compound_name"] for row in rows] == [
        "OPC-167832",
        "PBTZ169",
        "TBA-7371",
    ]
    assert rows[0]["first_contact_use_mode"] == "proceed_now"
    assert rows[0]["source_repurposing_fill_bound"] is True
    assert rows[2]["first_contact_packet_artifact"] == "runs/dpre1_tb_alliance_export_current.md"
