from __future__ import annotations

import json
from pathlib import Path

from tools import sync_product_public_benchmark_scorecard_intake as mod


def test_sync_product_public_benchmark_scorecard_intake_writes_partial_rows(tmp_path: Path) -> None:
    row_csv = tmp_path / "lit.csv"
    row_csv.write_text(
        "suite_id,benchmark_family,dataset_source_url,scorecard_json,status,primary_metric,primary_metric_value,primary_metric_threshold,regression_baseline_ref,run_command\n"
        "lit_pcba_virtual_screening,protein_ligand_virtual_screening,https://zenodo.org/records/4588239,runs/lit.json,fail,EF1,0.0,1.2,baseline,cmd\n",
        encoding="utf-8",
    )
    out_csv = tmp_path / "intake.csv"
    out_json = tmp_path / "sync.json"
    out_md = tmp_path / "sync.md"

    mod.main(["--row-csv", str(row_csv), "--out-csv", str(out_csv), "--out-json", str(out_json), "--out-md", str(out_md)])

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "product_public_benchmark_scorecard_intake_synced"
    assert payload["summary"]["output_row_count"] == 1
    assert payload["summary"]["missing_suite_count"] == 4
    assert out_csv.read_text(encoding="utf-8").startswith("suite_id,benchmark_family,")
    assert "Product Public Benchmark Scorecard Intake Sync" in out_md.read_text(encoding="utf-8")
