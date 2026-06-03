from __future__ import annotations

import json
from pathlib import Path

from tools import build_lit_pcba_scorecard as mod


def test_build_lit_pcba_scorecard_tool_writes_blocked_outputs(tmp_path: Path) -> None:
    out_json = tmp_path / "scorecard.json"
    out_md = tmp_path / "scorecard.md"
    row_csv = tmp_path / "row.csv"

    mod.main(
        [
            "--scores-csv",
            str(tmp_path / "missing_scores.csv"),
            "--labels-csv",
            str(tmp_path / "missing_labels.csv"),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--row-csv",
            str(row_csv),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "blocked_lit_pcba_scorecard"
    assert payload["scorecard_row"]["suite_id"] == "lit_pcba_virtual_screening"
    assert row_csv.read_text(encoding="utf-8").startswith("suite_id,benchmark_family,")
    assert "LIT-PCBA Scorecard" in out_md.read_text(encoding="utf-8")
