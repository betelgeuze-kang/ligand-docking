from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.cameo import build_cameo_operator_input_validation as mod


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_build_cameo_operator_input_validation_tool_writes_outputs(tmp_path: Path) -> None:
    model_path = tmp_path / "model1.pdb"
    model_path.write_text(
        "ATOM      1  CA  GLY A   1      12.104  13.207   9.111  1.00 20.00           C\nEND\n",
        encoding="utf-8",
    )
    candidates_csv = tmp_path / "candidates.csv"
    models_csv = tmp_path / "models.csv"
    results_csv = tmp_path / "results.csv"
    _write_csv(
        candidates_csv,
        [
            {
                "target_id": "CAMEO100",
                "candidate_id": "cand1",
                "source_kind": "internal_prediction",
                "validation_status": "pass",
                "model_path": str(model_path),
                "confidence_mean": "0.91",
                "continuity_fraction": "1.0",
            }
        ],
    )
    _write_csv(
        models_csv,
        [
            {
                "target_id": "CAMEO100",
                "candidate_id": "cand1",
                "cameo_model_rank": "1",
                "model_path": str(model_path),
            }
        ],
    )
    _write_csv(
        results_csv,
        [
            {
                "target_id": "CAMEO100",
                "candidate_id": "cand1",
                "cameo_model_rank": "1",
                "result_source_kind": "official_cameo",
                "lddt": "0.8",
            }
        ],
    )
    out_json = tmp_path / "validation.json"
    out_csv = tmp_path / "validation.csv"
    out_md = tmp_path / "validation.md"

    mod.main(
        [
            "--candidates-csv",
            str(candidates_csv),
            "--models-csv",
            str(models_csv),
            "--official-results-csv",
            str(results_csv),
            "--base-dir",
            str(tmp_path),
            "--require-official-results",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "cameo_operator_inputs_ready_with_official_results"
    assert out_csv.read_text(encoding="utf-8").startswith("input_name,row_number,")
    assert "CAMEO Operator Input Validation" in out_md.read_text(encoding="utf-8")
