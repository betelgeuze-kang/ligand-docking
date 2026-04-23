from __future__ import annotations

from tools import build_wetlab_broad_screen_compound_universe as mod


def test_build_wetlab_broad_screen_compound_universe_dedupes_local_sources() -> None:
    payload = mod.build_payload()
    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["status"] == "wetlab_broad_screen_compound_universe_ready"
    assert summary["target_library_size"] == 100000
    assert summary["source_file_count"] >= 1
    assert summary["deduped_compound_count"] == len(rows)
    assert summary["duplicate_row_count"] >= 1
    assert summary["coverage_status"] in {"partial_local_coverage", "full_target_coverage"}
    assert rows[0]["compound_index"] == 1
    assert rows[0]["dedupe_key"]
