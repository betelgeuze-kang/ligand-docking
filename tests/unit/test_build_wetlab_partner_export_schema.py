from __future__ import annotations

from tools import build_wetlab_partner_export_schema as mod


def test_build_wetlab_partner_export_schema() -> None:
    payload = mod.build_payload()
    summary = payload["summary"]
    rows = {row["partner_track_id"]: row for row in payload["rows"]}

    assert summary["status"] == "wetlab_partner_export_schema_ready"
    assert summary["partner_track_count"] == 5
    assert "DNDi_IPK" in rows
    assert "condition_card" in rows["oncology_condition_aware"]["required_export_artifacts"]
    assert rows["READDI_Korea"]["first_ask"].startswith("fast fluorogenic protease assay")
