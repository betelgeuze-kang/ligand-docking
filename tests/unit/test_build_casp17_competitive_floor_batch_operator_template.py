from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_competitive_floor_batch_operator_template as mod


LAYERS = [
    "recursive",
    "scored",
    "sidechain_scaffold",
    "sidechain_repacked",
    "sidechain_completed",
    "steric_relaxed",
    "rotamer_minimized",
    "polar_refined",
    "forcefield_minimized",
    "statistical_rotamer",
]


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
        "MODEL 1\nATOM      1 CA   ALA A   1       1.000   2.000   3.000  1.00 70.00           C  \nEND\n",
        encoding="utf-8",
    )
    return str(path)


def _batch_json(path: Path, batch_folder: Path, scaffold: Path, target_id: str = "REQUIRED_MONOMER_001") -> Path:
    _write_json(
        path,
        {
            "summary": {"batch_status": "ready_for_fill"},
            "rows": [
                {
                    "operator_priority": 1,
                    "row_rank": 1,
                    "benchmark_id": f"hist_{target_id}",
                    "target_id": target_id,
                    "scope": "monomer",
                    "batch_folder": str(batch_folder),
                    "copied_row_scaffold": str(scaffold),
                }
            ],
        },
    )
    return path


def test_competitive_floor_batch_operator_template_blocks_unfilled_placeholders(tmp_path: Path) -> None:
    batch_folder = tmp_path / "batch" / "priority_001_REQUIRED_MONOMER_001"
    scaffold = batch_folder / "row_scaffold"
    _write_csv(
        batch_folder / "row_metadata_template.csv",
        [{"benchmark_id": "hist_REQUIRED_MONOMER_001", "target_id": "REQUIRED_MONOMER_001", "scope": "monomer", "split": "historical"}],
    )
    _write_csv(
        scaffold / "required_files.csv",
        [
            {
                "file_role": "prediction_pdb",
                "template_column": "prediction_pdb",
                "expected_path": "runs/casp17_historical_benchmark_predictions_current/REQUIRED_MONOMER_001_prediction.pdb",
            }
        ],
    )
    _write_csv(
        scaffold / "provenance_template.csv",
        [
            {
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
            }
        ],
    )
    _write_csv(
        scaffold / "calibration_template.csv",
        [
            {
                "selected_model_rank": "REQUIRED_1_TO_5",
                "best_model_rank": "REQUIRED_1_TO_5",
                "selected_native_metric": "REQUIRED_NATIVE_METRIC",
                "best_native_metric": "REQUIRED_ORACLE_METRIC",
                "selected_score": "REQUIRED_INTERNAL_SCORE",
                "best_score": "REQUIRED_ORACLE_SCORE",
            }
        ],
    )
    batch_json = _batch_json(tmp_path / "batch.json", batch_folder, scaffold)

    args = mod.parse_args(
        [
            "--batch-json",
            str(batch_json),
            "--out-template-csv",
            str(tmp_path / "operator.csv"),
            "--out-json",
            str(tmp_path / "operator.json"),
            "--out-csv",
            str(tmp_path / "audit.csv"),
            "--out-md",
            str(tmp_path / "operator.md"),
        ]
    )
    payload = mod.build_payload(args)

    assert payload["summary"]["template_status"] == "blocked"
    assert payload["summary"]["row_count"] == 1
    assert payload["summary"]["blocked_count"] == 1
    assert payload["rows"][0]["template_row_status"] == "blocked"
    assert "placeholder_target_id" in payload["rows"][0]["blockers"]
    assert payload["summary"]["placeholder_file_path_count"] >= 1


def test_competitive_floor_batch_operator_template_builds_ready_candidate(tmp_path: Path) -> None:
    target_id = "T9001"
    batch_folder = tmp_path / "batch" / "priority_001_T9001"
    scaffold = batch_folder / "row_scaffold"
    prediction = _write_pdb(tmp_path / "predictions" / f"{target_id}_prediction.pdb")
    native = _write_pdb(tmp_path / "natives" / f"{target_id}_native.pdb")
    required_rows = [
        {"file_role": "prediction_pdb", "template_column": "prediction_pdb", "expected_path": prediction},
        {"file_role": "native_pdb", "template_column": "native_pdb", "expected_path": native},
    ]
    for layer in LAYERS:
        required_rows.append(
            {
                "file_role": f"ablation_{layer}_prediction_pdb",
                "template_column": f"{layer}_prediction_pdb",
                "expected_path": _write_pdb(tmp_path / "layers" / layer / f"{target_id}TS.pdb"),
            }
        )
    _write_csv(
        batch_folder / "row_metadata.csv",
        [{"benchmark_id": "hist_T9001", "target_id": target_id, "scope": "monomer", "split": "historical"}],
    )
    _write_csv(scaffold / "required_files.csv", required_rows)
    _write_csv(
        scaffold / "provenance_template.csv",
        [
            {
                "leakage_clearance": "no_leak",
                "prediction_method": "internal_physics",
                "prediction_created_at": "2025-01-01",
                "native_release_date": "2025-06-01",
                "prediction_generated_before_native_release": "true",
                "public_template_or_native_used_for_prediction": "false",
                "other_team_model_used": "false",
                "post_release_information_used": "false",
                "current_casp17_target": "false",
                "operator_clearance": "no_leak",
            }
        ],
    )
    _write_csv(
        scaffold / "calibration_template.csv",
        [
            {
                "selected_model_rank": "1",
                "best_model_rank": "1",
                "selected_native_metric": "0.91",
                "best_native_metric": "0.92",
                "selected_score": "42.0",
                "best_score": "43.0",
            }
        ],
    )
    batch_json = _batch_json(tmp_path / "batch.json", batch_folder, scaffold, target_id)

    args = mod.parse_args(
        [
            "--batch-json",
            str(batch_json),
            "--out-template-csv",
            str(tmp_path / "operator.csv"),
            "--out-json",
            str(tmp_path / "operator.json"),
            "--out-csv",
            str(tmp_path / "audit.csv"),
            "--out-md",
            str(tmp_path / "operator.md"),
        ]
    )
    payload = mod.build_payload(args)
    mod._write_csv(args.out_template_csv, payload["operator_rows"], fieldnames=mod.OUTPUT_COLUMNS)
    rows = list(csv.DictReader((tmp_path / "operator.csv").open("r", encoding="utf-8", newline="")))

    assert payload["summary"]["template_status"] == "ready_for_preflight"
    assert payload["summary"]["ready_for_preflight_count"] == 1
    assert payload["summary"]["missing_file_count"] == 0
    assert payload["summary"]["provenance_blocker_count"] == 0
    assert payload["summary"]["calibration_blocker_count"] == 0
    assert rows[0]["target_id"] == target_id
    assert rows[0]["recursive_prediction_pdb"].endswith("T9001TS.pdb")
    assert rows[0]["best_native_metric"] == "0.92"


def test_competitive_floor_batch_operator_template_prefers_single_row_fill_csv(tmp_path: Path) -> None:
    target_id = "T9003"
    batch_folder = tmp_path / "batch" / "priority_001_T9003"
    scaffold = batch_folder / "row_scaffold"
    prediction = _write_pdb(tmp_path / "predictions" / f"{target_id}_prediction.pdb")
    native = _write_pdb(tmp_path / "natives" / f"{target_id}_native.pdb")
    row = {
        "benchmark_id": "hist_T9003",
        "target_id": target_id,
        "scope": "monomer",
        "split": "historical",
        "prediction_pdb": prediction,
        "native_pdb": native,
        "leakage_clearance": "no_leak",
        "prediction_method": "internal_physics",
        "prediction_created_at": "2025-01-01",
        "native_release_date": "2025-06-01",
        "prediction_generated_before_native_release": "true",
        "public_template_or_native_used_for_prediction": "false",
        "other_team_model_used": "false",
        "post_release_information_used": "false",
        "current_casp17_target": "false",
        "operator_clearance": "no_leak",
        "selected_model_rank": "1",
        "best_model_rank": "1",
        "selected_native_metric": "0.88",
        "best_native_metric": "0.91",
        "selected_score": "12.5",
        "best_score": "14.0",
    }
    for layer in LAYERS:
        row[f"{layer}_prediction_pdb"] = _write_pdb(tmp_path / "layers" / layer / f"{target_id}TS.pdb")
    _write_csv(batch_folder / "row_fill.csv", [row])
    batch_json = _batch_json(tmp_path / "batch.json", batch_folder, scaffold, target_id)

    args = mod.parse_args(
        [
            "--batch-json",
            str(batch_json),
            "--out-template-csv",
            str(tmp_path / "operator.csv"),
            "--out-json",
            str(tmp_path / "operator.json"),
            "--out-csv",
            str(tmp_path / "audit.csv"),
            "--out-md",
            str(tmp_path / "operator.md"),
        ]
    )
    payload = mod.build_payload(args)

    assert payload["summary"]["template_status"] == "ready_for_preflight"
    assert payload["summary"]["row_fill_candidate_count"] == 1
    assert payload["rows"][0]["candidate_source_type"] == "row_fill_csv"
    assert payload["rows"][0]["template_row_status"] == "ready_for_preflight"
    assert payload["operator_rows"][0]["target_id"] == target_id
