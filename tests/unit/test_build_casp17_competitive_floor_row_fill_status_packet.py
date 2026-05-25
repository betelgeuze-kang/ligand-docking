from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_competitive_floor_row_fill_status_packet as mod


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


def test_row_fill_status_reports_awaiting_unfilled_template(tmp_path: Path) -> None:
    folder = tmp_path / "batch" / "priority_001_REQUIRED_MONOMER_001"
    _write_csv(folder / "row_fill_template.csv", [{"benchmark_id": "hist_REQUIRED_MONOMER_001"}])
    args = mod.parse_args(["--batch-json", str(_batch(tmp_path / "batch.json", folder))])

    payload = mod.build_payload(args)

    assert payload["summary"]["row_fill_status"] == "awaiting_fill"
    assert payload["summary"]["row_fill_template_count"] == 1
    assert payload["summary"]["row_fill_filled_count"] == 0
    assert payload["summary"]["ready_for_operator_template_count"] == 0
    assert payload["rows"][0]["row_fill_status"] == "awaiting_row_fill"
    assert "row_fill_csv_not_filled" in payload["rows"][0]["blockers"]


def test_row_fill_status_accepts_ready_filled_row(tmp_path: Path) -> None:
    folder = tmp_path / "batch" / "priority_001_T9001"
    target_id = "T9001"
    row = {
        "benchmark_id": "hist_T9001",
        "target_id": target_id,
        "scope": "monomer",
        "split": "historical",
        "prediction_pdb": _write_pdb(tmp_path / "predictions" / f"{target_id}_prediction.pdb"),
        "native_pdb": _write_pdb(tmp_path / "natives" / f"{target_id}_native.pdb"),
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
    _write_csv(folder / "row_fill_template.csv", [row])
    _write_csv(folder / "row_fill.csv", [row])
    args = mod.parse_args(["--batch-json", str(_batch(tmp_path / "batch.json", folder))])

    payload = mod.build_payload(args)

    assert payload["summary"]["row_fill_status"] == "ready_for_operator_template"
    assert payload["summary"]["row_fill_filled_count"] == 1
    assert payload["summary"]["ready_for_operator_template_count"] == 1
    assert payload["summary"]["missing_local_file_count"] == 0
    assert payload["rows"][0]["row_fill_status"] == "ready_for_operator_template"
