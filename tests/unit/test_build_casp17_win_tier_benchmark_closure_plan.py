from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_build_casp17_win_tier_benchmark_closure_plan_expands_missing_rows(tmp_path: Path) -> None:
    threshold = tmp_path / "threshold.json"
    workorder = tmp_path / "workorder.json"
    sidechain = tmp_path / "sidechain.json"
    historical = tmp_path / "historical.json"
    ablation = tmp_path / "ablation.json"
    calibration = tmp_path / "calibration.json"

    _write_json(
        threshold,
        {
            "summary": {
                "thresholds": {
                    "historical_monomer_rows": {"competitive": 10, "win": 25},
                    "historical_complex_rows": {"competitive": 5, "win": 15},
                }
            }
        },
    )
    _write_json(
        workorder,
        {"summary": {"workorder_count": 2, "missing_core_file_count": 4, "missing_ablation_layer_count": 20}},
    )
    _write_json(sidechain, {"summary": {"sidechain_native_benchmark_status": "blocked", "benchmark_count": 0}})
    _write_json(
        historical,
        {
            "summary": {
                "historical_benchmark_status": "blocked",
                "monomer_benchmark_count": 3,
                "complex_benchmark_count": 1,
            }
        },
    )
    _write_json(ablation, {"summary": {"refinement_ablation_status": "blocked", "ablation_group_count": 1}})
    _write_json(calibration, {"summary": {"calibration_status": "blocked", "calibration_row_count": 2}})

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_win_tier_benchmark_closure_plan.py"),
            "--threshold-json",
            str(threshold),
            "--historical-workorder-json",
            str(workorder),
            "--sidechain-native-json",
            str(sidechain),
            "--historical-benchmark-json",
            str(historical),
            "--refinement-ablation-json",
            str(ablation),
            "--model-selection-calibration-json",
            str(calibration),
            "--out-json",
            str(tmp_path / "plan.json"),
            "--out-csv",
            str(tmp_path / "plan.csv"),
            "--out-md",
            str(tmp_path / "plan.md"),
            "--out-template-csv",
            str(tmp_path / "operator_template.csv"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "plan.json").read_text(encoding="utf-8"))
    template_rows = list(csv.DictReader((tmp_path / "operator_template.csv").open("r", encoding="utf-8", newline="")))
    rows = {row["track"]: row for row in payload["rows"]}

    assert payload["summary"]["closure_plan_status"] == "ready"
    assert payload["summary"]["benchmark_evidence_status"] == "blocked_input"
    assert payload["summary"]["win_required_total_rows"] == 40
    assert payload["summary"]["missing_win_monomer_rows"] == 22
    assert payload["summary"]["missing_win_complex_rows"] == 14
    assert payload["summary"]["missing_win_total_rows"] == 36
    assert payload["summary"]["required_core_prediction_files_for_win"] == 36
    assert payload["summary"]["required_native_files_for_win"] == 36
    assert payload["summary"]["required_ablation_layer_prediction_files_for_win"] == 360
    assert payload["summary"]["required_calibration_rows_for_win"] == 36
    assert len(template_rows) == 36
    assert template_rows[0]["target_id"] == "REQUIRED_MONOMER_001"
    assert template_rows[-1]["target_id"] == "REQUIRED_COMPLEX_014"
    assert "recursive_prediction_pdb" in template_rows[0]
    assert "selected_model_rank" in template_rows[0]
    assert rows["historical_monomer_native_accuracy"]["win_missing_count"] == 22
    assert rows["refinement_ablation_native_evidence"]["extra_missing_file_count"] == 390
    assert "does not fetch native structures" in payload["summary"]["claim_boundary"]


def test_build_casp17_win_tier_benchmark_closure_plan_passes_when_counts_satisfied(tmp_path: Path) -> None:
    threshold = tmp_path / "threshold.json"
    empty = tmp_path / "empty.json"
    _write_json(
        threshold,
        {
            "summary": {
                "thresholds": {
                    "historical_monomer_rows": {"competitive": 1, "win": 1},
                    "historical_complex_rows": {"competitive": 1, "win": 1},
                }
            }
        },
    )
    _write_json(
        empty,
        {
            "summary": {
                "sidechain_native_benchmark_status": "pass",
                "historical_benchmark_status": "pass",
                "refinement_ablation_status": "pass",
                "calibration_status": "pass",
                "benchmark_count": 2,
                "monomer_benchmark_count": 1,
                "complex_benchmark_count": 1,
                "ablation_group_count": 2,
                "calibration_row_count": 2,
            }
        },
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_win_tier_benchmark_closure_plan.py"),
            "--threshold-json",
            str(threshold),
            "--historical-workorder-json",
            str(empty),
            "--sidechain-native-json",
            str(empty),
            "--historical-benchmark-json",
            str(empty),
            "--refinement-ablation-json",
            str(empty),
            "--model-selection-calibration-json",
            str(empty),
            "--out-json",
            str(tmp_path / "plan.json"),
            "--out-csv",
            str(tmp_path / "plan.csv"),
            "--out-md",
            str(tmp_path / "plan.md"),
            "--out-template-csv",
            str(tmp_path / "operator_template.csv"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "plan.json").read_text(encoding="utf-8"))
    template_rows = list(csv.DictReader((tmp_path / "operator_template.csv").open("r", encoding="utf-8", newline="")))

    assert payload["summary"]["benchmark_evidence_status"] == "pass"
    assert payload["summary"]["missing_win_total_rows"] == 0
    assert template_rows == []
    assert all(row["closure_status"] == "pass" for row in payload["rows"])
