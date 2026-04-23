from __future__ import annotations

from tools import build_wetlab_engineering_progress as mod


def test_build_wetlab_engineering_progress_summarizes_workstreams() -> None:
    payload = mod.build_payload(
        precision_monitor={"summary": {"completion_pct": 2.7, "resolved_shards": 7, "running_shards": 1}},
        rerank_payload={"summary": {"full_bulk_ready_target_count": 1}},
        source_payload={"summary": {"actual_row_count": 3}},
    )
    summary = payload["summary"]
    assert summary["status"] == "wetlab_engineering_progress_ready"
    assert summary["full_bulk_ready_target_count"] == 1
    assert summary["actual_row_count"] == 3
    rows = {row["workstream"]: row for row in payload["rows"]}
    assert rows["auto_append_pipeline"]["status"] == "partially_implemented"
    assert rows["broad_screen_runtime_monitoring"]["status"] == "implemented"
