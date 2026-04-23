from __future__ import annotations

from tools import build_wetlab_broad_screen_bulk_result_source_schema as mod


def test_build_wetlab_broad_screen_bulk_result_source_schema_lists_required_fields() -> None:
    payload = mod.build_payload()
    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["status"] == "wetlab_broad_screen_bulk_result_source_schema_ready"
    assert summary["required_field_count"] == 4
    assert rows[0]["field_name"] == "target_id"
    assert rows[1]["field_name"] == "compound_name"
    assert rows[2]["field_name"] == "bulk_rank"
    assert rows[3]["field_name"] == "bulk_score"
