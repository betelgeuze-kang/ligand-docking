from __future__ import annotations

from tools import build_wetlab_broad_screen_bulk_results_source_merge as mod


def test_build_updated_source_payload_replaces_bootstrap_rows_with_actual_rows() -> None:
    source_payload = {
        "summary": {"status": "wetlab_broad_screen_bulk_results_source_ready"},
        "structured": {"source_artifacts": "bootstrap"},
        "rows": [
            {"target_id": "CA IX", "compound_name": "Acetazolamide", "bulk_rank": 1, "bulk_score": 80.0, "seed_status": "bootstrap_from_manual_fill_map"},
            {"target_id": "CA IX", "compound_name": "Methazolamide", "bulk_rank": 2, "bulk_score": 79.0, "seed_status": "bootstrap_from_manual_fill_map"},
            {"target_id": "CA IX", "compound_name": "Dichlorphenamide", "bulk_rank": 3, "bulk_score": 78.0, "seed_status": "bootstrap_from_manual_fill_map"},
        ],
    }
    incoming_payload = {
        "rows": [
            {"target_id": "CA IX", "compound_name": "Acetazolamide", "bulk_rank": 1, "bulk_score": 92.4, "seed_status": "broad_screen_actual_result_example"},
            {"target_id": "CA IX", "compound_name": "Methazolamide", "bulk_rank": 2, "bulk_score": 89.1, "seed_status": "broad_screen_actual_result_example"},
        ]
    }

    updated, report = mod.build_updated_source_payload(source_payload, incoming_payload, source_rows_artifact="rows.md")

    assert updated["summary"]["row_count"] == 3
    assert updated["summary"]["actual_row_count"] == 2
    assert updated["summary"]["bootstrap_row_count"] == 1
    rows = updated["rows"]
    assert rows[0]["compound_name"] == "Acetazolamide"
    assert rows[0]["bulk_score"] == 92.4
    assert rows[1]["compound_name"] == "Methazolamide"
    assert report["summary"]["overwritten_row_count"] == 2
