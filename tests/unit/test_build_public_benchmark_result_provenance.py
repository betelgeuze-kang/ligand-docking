from __future__ import annotations

import json
from pathlib import Path

from tools import build_public_benchmark_result_provenance as mod


def test_build_public_benchmark_result_provenance_tool_writes_outputs(tmp_path: Path) -> None:
    result = tmp_path / "results.csv"
    result.write_text("suite_id,target_id,candidate_id,primary_metric_value\ns,T1,L1,0.7\n", encoding="utf-8")
    out_json = tmp_path / "provenance.json"
    out_csv = tmp_path / "provenance.csv"
    out_md = tmp_path / "provenance.md"

    mod.main(
        [
            "--suite-id",
            "dude_z_decoy_smoke",
            "--result-artifact",
            str(result),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "public_benchmark_result_provenance_ready"
    assert payload["summary"]["result_artifact"] == str(result)
    assert payload["summary"]["result_row_count"] == 1
    assert out_csv.read_text(encoding="utf-8").startswith("check,status,")
    assert "Public Benchmark Result Provenance" in out_md.read_text(encoding="utf-8")
