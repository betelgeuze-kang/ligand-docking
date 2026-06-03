from __future__ import annotations

import json
from pathlib import Path

from tools import build_cameo_official_results_intake_gate as mod


def test_build_cameo_official_results_intake_gate_tool_writes_outputs_and_template(tmp_path: Path) -> None:
    results = tmp_path / "results.csv"
    results.write_text(
        "target_id,candidate_id,cameo_model_rank,result_source_kind,result_source_url,result_record_id,retrieved_at_utc,assessment_date,lddt,tm_score,qs_score,rmsd_A\n"
        "CAMEO100,model1,1,official_cameo,https://cameo3d.org/modeling/CAMEO100,CAMEO100:model1,2026-06-03T00:00:00Z,2026-06-03,0.72,,,,\n",
        encoding="utf-8",
    )
    out_json = tmp_path / "gate.json"
    out_csv = tmp_path / "gate.csv"
    out_md = tmp_path / "gate.md"
    template = tmp_path / "template.csv"

    mod.main(["--results-csv", str(results), "--template-csv", str(template), "--out-json", str(out_json), "--out-csv", str(out_csv), "--out-md", str(out_md)])

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "cameo_official_results_intake_ready"
    assert "required_columns" in json.loads(out_json.read_text(encoding="utf-8"))["summary"]
    summary = json.loads(out_json.read_text(encoding="utf-8"))["summary"]
    assert summary["operator_template_csv"] == str(template)
    assert summary["operator_intake_csv"] == str(results)
    assert summary["missing_required_columns"] == []
    assert summary["blocker_codes"] == []
    assert summary["rejected_official_result_count"] == 0
    assert out_csv.read_text(encoding="utf-8").startswith("row_number,target_id,")
    assert "CAMEO Official Results Intake Gate" in out_md.read_text(encoding="utf-8")
    assert "operator_intake_csv" in out_md.read_text(encoding="utf-8")
    assert "disallowed_local_accuracy_columns" in out_md.read_text(encoding="utf-8")
    assert template.read_text(encoding="utf-8").startswith("target_id,candidate_id,")
