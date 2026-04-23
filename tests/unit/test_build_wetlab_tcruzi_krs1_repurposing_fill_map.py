from __future__ import annotations

from tools import build_wetlab_tcruzi_krs1_repurposing_fill_map as mod


def test_build_wetlab_tcruzi_krs1_repurposing_fill_map() -> None:
    payload = mod.build_payload()
    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["status"] == "wetlab_tcruzi_krs1_repurposing_fill_map_ready"
    assert summary["row_count"] == 3
    assert rows[0]["target_id"] == "T. cruzi KRS1"
    assert rows[0]["compound_name"] == "Benznidazole"
    assert rows[0]["first_contact_packet_artifact"] == "runs/tcruzi_krs1_launch_packet_current.md"
    assert rows[2]["compound_name"] == "Posaconazole"
    assert rows[2]["track_label"] == "DNDi Chagas backup rail"
