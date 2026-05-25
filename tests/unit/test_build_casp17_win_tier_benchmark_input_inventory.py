from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
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


def _write_ca_pdb(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 80.00           C\n",
        "ATOM      2  CA  GLY A   2       3.800   0.000   0.000  1.00 80.00           C\n",
        "TER\n",
        "END\n",
    ]
    path.write_text("".join(lines), encoding="utf-8")


def test_build_casp17_win_tier_benchmark_input_inventory_detects_ready_and_blocked_rows(tmp_path: Path) -> None:
    ready_dir = tmp_path / "row_ready"
    blocked_dir = tmp_path / "row_blocked"
    ready_prediction = tmp_path / "prediction.pdb"
    ready_native = tmp_path / "native.pdb"
    ready_ablation = tmp_path / "ablation.pdb"
    _write_ca_pdb(ready_prediction)
    _write_ca_pdb(ready_native)
    _write_ca_pdb(ready_ablation)
    _write_csv(
        ready_dir / "required_files.csv",
        [
            {"file_role": "prediction_pdb", "template_column": "prediction_pdb", "expected_path": str(ready_prediction)},
            {"file_role": "native_pdb", "template_column": "native_pdb", "expected_path": str(ready_native)},
            {
                "file_role": "ablation_recursive_prediction_pdb",
                "template_column": "recursive_prediction_pdb",
                "expected_path": str(ready_ablation),
            },
        ],
    )
    _write_csv(
        ready_dir / "provenance_template.csv",
        [
            {
                "leakage_clearance": "no_leak",
                "prediction_method": "internal_physics_demo",
                "prediction_created_at": "2024-01-01",
                "native_release_date": "2024-02-01",
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
        ready_dir / "calibration_template.csv",
        [
            {
                "selected_model_rank": "1",
                "best_model_rank": "1",
                "selected_native_metric": "0.91",
                "best_native_metric": "0.93",
                "selected_score": "42.0",
                "best_score": "43.0",
            }
        ],
    )
    _write_csv(
        blocked_dir / "required_files.csv",
        [
            {
                "file_role": "prediction_pdb",
                "template_column": "prediction_pdb",
                "expected_path": str(tmp_path / "missing_prediction.pdb"),
            },
            {
                "file_role": "native_pdb",
                "template_column": "native_pdb",
                "expected_path": str(tmp_path / "missing_native.pdb"),
            },
        ],
    )
    _write_csv(
        blocked_dir / "provenance_template.csv",
        [{"leakage_clearance": "REQUIRED_NO_LEAK_CLEARANCE", "prediction_method": "REQUIRED_INTERNAL_METHOD"}],
    )
    _write_csv(blocked_dir / "calibration_template.csv", [{"selected_model_rank": "REQUIRED_1_TO_5"}])
    scaffold = tmp_path / "scaffold.json"
    scaffold.write_text(
        json.dumps(
            {
                "summary": {"scaffold_status": "ready"},
                "rows": [
                    {
                        "row_rank": 1,
                        "benchmark_id": "hist_DEMO_READY",
                        "target_id": "DEMO_READY",
                        "scope": "monomer",
                        "metric_profile": "TM,GDT_TS,CA_lDDT",
                        "required_file_count": 3,
                        "required_files_csv": str(ready_dir / "required_files.csv"),
                        "provenance_template_csv": str(ready_dir / "provenance_template.csv"),
                        "calibration_template_csv": str(ready_dir / "calibration_template.csv"),
                        "row_dir": str(ready_dir),
                    },
                    {
                        "row_rank": 2,
                        "benchmark_id": "hist_REQUIRED_MONOMER_001",
                        "target_id": "REQUIRED_MONOMER_001",
                        "scope": "monomer",
                        "metric_profile": "TM,GDT_TS,CA_lDDT",
                        "required_file_count": 2,
                        "required_files_csv": str(blocked_dir / "required_files.csv"),
                        "provenance_template_csv": str(blocked_dir / "provenance_template.csv"),
                        "calibration_template_csv": str(blocked_dir / "calibration_template.csv"),
                        "row_dir": str(blocked_dir),
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_win_tier_benchmark_input_inventory.py"),
            "--input-scaffold-json",
            str(scaffold),
            "--out-json",
            str(tmp_path / "inventory.json"),
            "--out-csv",
            str(tmp_path / "inventory.csv"),
            "--out-files-csv",
            str(tmp_path / "files.csv"),
            "--out-md",
            str(tmp_path / "inventory.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "inventory.json").read_text(encoding="utf-8"))
    summary = payload["summary"]
    rows = payload["rows"]
    files = list(csv.DictReader((tmp_path / "files.csv").open(encoding="utf-8")))

    assert summary["inventory_status"] == "blocked"
    assert summary["row_count"] == 2
    assert summary["ready_row_count"] == 1
    assert summary["blocked_row_count"] == 1
    assert summary["present_file_count"] == 3
    assert summary["missing_file_count"] == 2
    assert summary["provenance_ready_row_count"] == 1
    assert summary["calibration_ready_row_count"] == 1
    assert rows[0]["inventory_status"] == "ready"
    assert rows[0]["present_file_count"] == 3
    assert rows[1]["inventory_status"] == "blocked"
    assert "placeholder_target_id" in rows[1]["blockers"]
    assert any(row["pdb_ca_count"] == "2" for row in files)
    assert "Local input inventory only" in summary["claim_boundary"]
