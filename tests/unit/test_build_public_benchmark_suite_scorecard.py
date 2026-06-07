from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tools import build_public_benchmark_suite_scorecard as mod


def test_build_public_benchmark_suite_scorecard_writes_json_md_and_row(tmp_path: Path) -> None:
    evidence = tmp_path / "results.csv"
    evidence.write_text("target,pose_success_rate\n1abc,0.4\n", encoding="utf-8")
    provenance = tmp_path / "results_provenance.json"
    provenance.write_text(
        json.dumps(
            {
                "summary": {
                    "suite_id": "pdbbind_casf_pose_affinity",
                    "product_engine_result": True,
                    "source_engine": "betelgeuze_product",
                    "result_artifact": str(evidence),
                    "result_artifact_sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
                    "result_row_count": 1,
                }
            }
        ),
        encoding="utf-8",
    )
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
            "--product-provenance-json",
            str(provenance),
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
    assert payload["summary"]["operator_input_artifacts"] == f"{evidence};{provenance}"
    assert payload["summary"]["operator_output_artifacts"] == str(out_json)
    assert payload["summary"]["missing_input_artifacts"] == ""
    assert payload["summary"]["product_provenance_json"] == str(provenance)
    assert payload["summary"]["threshold"] == 0.35
    assert payload["summary"]["metric_gap_to_threshold"] > 0
    assert row_csv.read_text(encoding="utf-8").startswith("suite_id,benchmark_family,")
    md_text = out_md.read_text(encoding="utf-8")
    assert "Public Benchmark Suite Scorecard" in md_text
    assert "metric_gap_to_threshold" in md_text
    assert "operator_input_artifacts" in md_text
    assert "product_provenance_json" in md_text
