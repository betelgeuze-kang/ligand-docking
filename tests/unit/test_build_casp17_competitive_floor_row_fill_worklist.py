from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_competitive_floor_row_fill_worklist as mod


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_pdb(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "ATOM      1  CA  ALA A   1       1.000   2.000   3.000  1.00 70.00           C  \nEND\n",
        encoding="utf-8",
    )
    return str(path)


def _batch(path: Path, folder: Path) -> Path:
    _write_json(
        path,
        {
            "summary": {"batch_status": "ready_for_fill"},
            "rows": [
                {
                    "operator_priority": 1,
                    "row_rank": 1,
                    "benchmark_id": "hist_REQUIRED_MONOMER_001",
                    "target_id": "REQUIRED_MONOMER_001",
                    "scope": "monomer",
                    "batch_folder": str(folder),
                }
            ],
        },
    )
    return path


def _placeholder_row() -> dict[str, str]:
    row = {
        "benchmark_id": "hist_REQUIRED_MONOMER_001",
        "target_id": "REQUIRED_MONOMER_001",
        "scope": "monomer",
        "split": "historical",
        "prediction_pdb": "runs/casp17_historical_benchmark_predictions_current/REQUIRED_MONOMER_001_prediction.pdb",
        "native_pdb": "runs/casp17_historical_benchmark_natives_current/REQUIRED_MONOMER_001_native.pdb",
        "leakage_clearance": "REQUIRED_NO_LEAK_CLEARANCE",
        "prediction_method": "REQUIRED_INTERNAL_METHOD",
        "prediction_created_at": "YYYY-MM-DD",
        "native_release_date": "YYYY-MM-DD",
        "prediction_generated_before_native_release": "REQUIRED_TRUE_CONFIRMATION",
        "public_template_or_native_used_for_prediction": "REQUIRED_FALSE_CONFIRMATION",
        "other_team_model_used": "REQUIRED_FALSE_CONFIRMATION",
        "post_release_information_used": "REQUIRED_FALSE_CONFIRMATION",
        "current_casp17_target": "REQUIRED_FALSE_CONFIRMATION",
        "operator_clearance": "REQUIRED_OPERATOR_CLEARANCE",
        "selected_model_rank": "REQUIRED_1_TO_5",
        "best_model_rank": "REQUIRED_1_TO_5",
        "selected_native_metric": "REQUIRED_NATIVE_METRIC",
        "best_native_metric": "REQUIRED_ORACLE_METRIC",
        "selected_score": "REQUIRED_INTERNAL_SCORE",
        "best_score": "REQUIRED_ORACLE_SCORE",
    }
    for layer in mod.ABLATION_LAYER_NAMES:
        row[f"{layer}_prediction_pdb"] = f"runs/casp17_historical_ablation_predictions_current/{layer}/REQUIRED_MONOMER_001TS.pdb"
    return row


def _ready_row(tmp_path: Path) -> dict[str, str]:
    row = {
        "benchmark_id": "hist_T9001",
        "target_id": "T9001",
        "scope": "monomer",
        "split": "historical",
        "prediction_pdb": _write_pdb(tmp_path / "predictions" / "T9001_prediction.pdb"),
        "native_pdb": _write_pdb(tmp_path / "natives" / "T9001_native.pdb"),
        "leakage_clearance": "no_leak",
        "prediction_method": "internal_physics",
        "prediction_created_at": "2025-01-01",
        "native_release_date": "2025-05-01",
        "prediction_generated_before_native_release": "true",
        "public_template_or_native_used_for_prediction": "false",
        "other_team_model_used": "false",
        "post_release_information_used": "false",
        "current_casp17_target": "false",
        "operator_clearance": "no_leak",
        "selected_model_rank": "1",
        "best_model_rank": "1",
        "selected_native_metric": "0.84",
        "best_native_metric": "0.90",
        "selected_score": "12.0",
        "best_score": "13.0",
    }
    for layer in mod.ABLATION_LAYER_NAMES:
        row[f"{layer}_prediction_pdb"] = _write_pdb(tmp_path / "layers" / layer / "T9001TS.pdb")
    return row


def test_row_fill_worklist_expands_placeholders_into_operator_actions(tmp_path: Path) -> None:
    folder = tmp_path / "batch" / "priority_001_REQUIRED_MONOMER_001"
    _write_csv(folder / "row_fill.csv", [_placeholder_row()])
    args = mod.parse_args(
        [
            "--batch-json",
            str(_batch(tmp_path / "batch.json", folder)),
            "--out-json",
            str(tmp_path / "worklist.json"),
            "--out-csv",
            str(tmp_path / "worklist.csv"),
            "--out-md",
            str(tmp_path / "WORKLIST.md"),
        ]
    )

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["worklist_status"] == "open_actions"
    assert payload["summary"]["open_action_count"] == 30
    assert payload["summary"]["target_identity_action_count"] == 2
    assert payload["summary"]["core_file_action_count"] == 2
    assert payload["summary"]["ablation_file_action_count"] == 10
    assert payload["summary"]["calibration_action_count"] == 6
    assert any(row["template_column"] == "target_id" for row in payload["rows"])
    assert (folder / "FIELD_GUIDE.md").is_file()


def test_row_fill_worklist_ready_when_all_fields_and_files_pass(tmp_path: Path) -> None:
    folder = tmp_path / "batch" / "priority_001_T9001"
    _write_csv(folder / "row_fill.csv", [_ready_row(tmp_path)])
    args = mod.parse_args(["--batch-json", str(_batch(tmp_path / "batch.json", folder))])

    payload = mod.build_payload(args)

    assert payload["summary"]["worklist_status"] == "ready"
    assert payload["summary"]["open_action_count"] == 0
    assert payload["rows"] == []
