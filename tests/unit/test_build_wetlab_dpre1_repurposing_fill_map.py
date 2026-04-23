from __future__ import annotations

from tools import build_wetlab_dpre1_repurposing_fill_map as mod


def test_build_wetlab_dpre1_repurposing_fill_map() -> None:
    payload = mod.build_payload()
    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["status"] == "wetlab_dpre1_repurposing_fill_map_ready"
    assert summary["row_count"] == 3
    assert [row["compound_name"] for row in rows] == [
        "Delamanid",
        "Pretomanid",
        "Bedaquiline",
    ]
    assert rows[0]["first_contact_use_mode"] == "benchmark_control"
    assert rows[1]["first_contact_use_mode"] == "comparator_only"
    assert rows[2]["target_brief_artifact"] == "runs/dpre1_render_suite_current.md"
    assert summary["bulk_override_applied"] is False


def test_build_wetlab_dpre1_repurposing_fill_map_uses_bulk_override() -> None:
    bulk_autofill = {
        "rows": [
            {"target_id": "DprE1", "compound_name": "BulkDprE1A", "bulk_rank": 1, "bulk_score": 9.5},
            {"target_id": "DprE1", "compound_name": "BulkDprE1B", "bulk_rank": 2, "bulk_score": 8.2},
            {"target_id": "DprE1", "compound_name": "BulkDprE1C", "bulk_rank": 3, "bulk_score": 7.9},
        ]
    }

    payload = mod.build_payload(bulk_autofill)
    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["bulk_override_applied"] is True
    assert [row["compound_name"] for row in rows] == ["BulkDprE1A", "BulkDprE1B", "BulkDprE1C"]
    assert all(row["row_status"] == "bulk_override_ready" for row in rows)
