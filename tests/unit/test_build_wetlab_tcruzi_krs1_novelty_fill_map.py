from __future__ import annotations

from tools import build_wetlab_tcruzi_krs1_novelty_fill_map as mod
from tools import build_wetlab_tcruzi_krs1_repurposing_fill_map as rep_mod


def test_build_wetlab_tcruzi_krs1_novelty_fill_map() -> None:
    rep_payload = rep_mod.build_payload()
    payload = mod.build_payload(rep_payload)
    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["status"] == "wetlab_tcruzi_krs1_novelty_fill_map_ready"
    assert summary["novelty_slot_count"] == 3
    assert rows[0]["target_id"] == "T. cruzi KRS1"
    assert rows[0]["novelty_compound_name"] == "DMU759"
    assert rows[0]["source_repurposing_fill_bound"] is True
    assert rows[2]["first_contact_packet_artifact"] == "runs/tcruzi_krs1_dndi_backup_export_current.md"
