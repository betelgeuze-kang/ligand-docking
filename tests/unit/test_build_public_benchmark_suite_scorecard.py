from __future__ import annotations

import json
from pathlib import Path

from tools import build_public_benchmark_suite_scorecard as mod


def test_build_public_benchmark_suite_scorecard_writes_json_md_and_row(tmp_path: Path) -> None:
    evidence = tmp_path / "results.csv"
    evidence.write_text("target,pose_success_rate\n1abc,0.4\n", encoding="utf-8")
    out_json = tmp_path / "scorecard.json"
    out_md = tmp_path / "scorecard.md"
    row_csv = tmp_path / "row.csv"

    mod.main(
        [
            "--suite-id",
            "pdbbind_casf_pose_affinity",
            "--primary-metric-value",
            "0.4",
            "--evidence-artifact",
            str(evidence),
            "--evidence-row-count",
            "1",
            "--regression-baseline-ref",
            "pdbbind:baseline",
            "--run-command",
            "python3 tools/build_public_benchmark_suite_scorecard.py --suite-id pdbbind_casf_pose_affinity",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--row-csv",
            str(row_csv),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "public_benchmark_suite_scorecard_pass"
    assert payload["summary"]["operator_input_artifacts"] == str(evidence)
    assert payload["summary"]["operator_output_artifacts"] == str(out_json)
    assert payload["summary"]["missing_input_artifacts"] == ""
    assert payload["summary"]["threshold"] == 0.35
    assert payload["summary"]["metric_gap_to_threshold"] > 0
    assert row_csv.read_text(encoding="utf-8").startswith("suite_id,benchmark_family,")
    md_text = out_md.read_text(encoding="utf-8")
    assert "Public Benchmark Suite Scorecard" in md_text
    assert "metric_gap_to_threshold" in md_text
    assert "operator_input_artifacts" in md_text
