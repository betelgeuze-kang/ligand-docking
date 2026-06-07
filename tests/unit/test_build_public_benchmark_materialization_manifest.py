from __future__ import annotations

import json
from pathlib import Path

from tools import build_public_benchmark_materialization_manifest as mod


def test_build_public_benchmark_materialization_manifest_writes_outputs(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    results = tmp_path / "results.csv"
    results.write_text("target,target_pass_rate\nT1000,0.6\n", encoding="utf-8")
    out_json = tmp_path / "manifest.json"
    out_csv = tmp_path / "manifest.csv"
    out_md = tmp_path / "manifest.md"

    mod.main(
        [
            "--suite-id",
            "casp_archive_structure_regression",
            "--dataset-artifact",
            str(dataset),
            "--result-artifact",
            str(results),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "public_benchmark_materialization_ready"
    assert payload["summary"]["operator_input_artifacts"] == str(dataset)
    assert payload["summary"]["operator_output_artifacts"] == str(results)
    assert out_csv.read_text(encoding="utf-8").startswith("check,status,observed,required")
    md_text = out_md.read_text(encoding="utf-8")
    assert "Public Benchmark Materialization Manifest" in md_text
    assert "operator_input_artifacts" in md_text
    assert "missing_input_artifacts" in md_text
