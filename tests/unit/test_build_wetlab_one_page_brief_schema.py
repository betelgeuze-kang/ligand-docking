from __future__ import annotations

from tools import build_wetlab_one_page_brief_schema as mod


def test_build_wetlab_one_page_brief_schema() -> None:
    payload = mod.build_payload()
    summary = payload["summary"]
    assert summary["status"] == "wetlab_one_page_brief_schema_ready"
    assert summary["summary_field_count"] == 11
    assert summary["row_field_count"] == 5
    assert summary["suggested_artifact_pattern"].endswith("_current.md")
