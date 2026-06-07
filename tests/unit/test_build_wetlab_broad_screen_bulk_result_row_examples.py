from __future__ import annotations

from tools.wetlab import build_wetlab_broad_screen_bulk_result_row_examples as mod


def test_build_wetlab_broad_screen_bulk_result_row_examples_has_two_caix_rows() -> None:
    payload = mod.build_payload()
    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["status"] == "wetlab_broad_screen_bulk_result_row_examples_ready"
    assert summary["example_row_count"] == 2
    assert summary["target_id"] == "CA IX"
    assert rows[0]["target_id"] == "CA IX"
    assert rows[0]["compound_name"] == "Acetazolamide"
    assert rows[0]["bulk_rank"] == 1
    assert rows[1]["compound_name"] == "Methazolamide"
    assert rows[1]["bulk_rank"] == 2
