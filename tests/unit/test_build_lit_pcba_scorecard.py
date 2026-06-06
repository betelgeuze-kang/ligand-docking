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
    assert str(tmp_path / "missing_scores.csv") in payload["summary"]["operator_input_artifacts"]
    assert str(tmp_path / "missing_labels.csv") in payload["summary"]["missing_input_artifacts"]
    assert payload["summary"]["operator_output_artifacts"] == str(out_json)
    assert payload["summary"]["threshold"] == payload["summary"]["primary_metric_threshold"]
    assert payload["summary"]["metric_gap_to_threshold"] < 0
    assert "scores_csv_missing" in payload["summary"]["blocker"]
    assert "product_provenance_json_not_declared" in payload["summary"]["blocker"]
    assert payload["scorecard_row"]["suite_id"] == "lit_pcba_virtual_screening"
    assert row_csv.read_text(encoding="utf-8").startswith("suite_id,benchmark_family,")
    md_text = out_md.read_text(encoding="utf-8")
    assert "LIT-PCBA Scorecard" in md_text
    assert "operator_input_artifacts" in md_text
    assert "metric_gap_to_threshold" in md_text
    assert "product_provenance_json" in md_text
