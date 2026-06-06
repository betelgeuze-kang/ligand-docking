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


def test_build_casp17_win_tier_benchmark_input_scaffold_writes_row_workbooks(tmp_path: Path) -> None:
    template = tmp_path / "template.csv"
    dashboard = tmp_path / "dashboard.json"
    fill = tmp_path / "fill.csv"
    base_row = {
        "benchmark_id": "hist_DEMO_MONOMER_001",
        "target_id": "DEMO_MONOMER_001",
        "scope": "monomer",
        "split": "historical",
        "prediction_pdb": "runs/predictions/DEMO_MONOMER_001_prediction.pdb",
        "native_pdb": "runs/natives/DEMO_MONOMER_001_native.pdb",
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
        "recursive_prediction_pdb": "runs/ablation/recursive/DEMO_MONOMER_001TS.pdb",
        "scored_prediction_pdb": "runs/ablation/scored/DEMO_MONOMER_001TS.pdb",
        "sidechain_scaffold_prediction_pdb": "runs/ablation/sidechain_scaffold/DEMO_MONOMER_001TS.pdb",
        "sidechain_repacked_prediction_pdb": "runs/ablation/sidechain_repacked/DEMO_MONOMER_001TS.pdb",
        "sidechain_completed_prediction_pdb": "runs/ablation/sidechain_completed/DEMO_MONOMER_001TS.pdb",
        "steric_relaxed_prediction_pdb": "runs/ablation/steric_relaxed/DEMO_MONOMER_001TS.pdb",
        "rotamer_minimized_prediction_pdb": "runs/ablation/rotamer_minimized/DEMO_MONOMER_001TS.pdb",
        "polar_refined_prediction_pdb": "runs/ablation/polar_refined/DEMO_MONOMER_001TS.pdb",
        "forcefield_minimized_prediction_pdb": "runs/ablation/forcefield_minimized/DEMO_MONOMER_001TS.pdb",
        "statistical_rotamer_prediction_pdb": "runs/ablation/statistical_rotamer/DEMO_MONOMER_001TS.pdb",
        "selected_model_rank": "REQUIRED_1_TO_5",
        "best_model_rank": "REQUIRED_1_TO_5",
        "selected_native_metric": "REQUIRED_NATIVE_METRIC",
        "best_native_metric": "REQUIRED_ORACLE_METRIC",
        "selected_score": "REQUIRED_INTERNAL_SCORE",
        "best_score": "REQUIRED_ORACLE_SCORE",
    }
    complex_row = dict(base_row)
    complex_row.update(
        {
            "benchmark_id": "hist_DEMO_COMPLEX_001",
            "target_id": "DEMO_COMPLEX_001",
            "scope": "complex",
            "prediction_pdb": "runs/predictions/DEMO_COMPLEX_001_prediction.pdb",
            "native_pdb": "runs/natives/DEMO_COMPLEX_001_native.pdb",
        }
    )
    _write_csv(template, [base_row, complex_row])
    dashboard.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "row_rank": 1,
                        "benchmark_id": "hist_DEMO_MONOMER_001",
                        "target_id": "DEMO_MONOMER_001",
                        "scope": "monomer",
                        "metric_profile": "TM,GDT_TS,CA_lDDT",
                        "operator_row_status": "blocked",
                        "needs_target_replacement": False,
                        "needs_core_files": True,
                        "needs_ablation_layers": True,
                        "needs_calibration": True,
                        "needs_provenance": True,
                        "next_action": "Fill row",
                        "blockers": "prediction_pdb_not_found",
                    },
                    {
                        "row_rank": 2,
                        "benchmark_id": "hist_DEMO_COMPLEX_001",
                        "target_id": "DEMO_COMPLEX_001",
                        "scope": "complex",
                        "metric_profile": "TM,interface_F1,DockQ,QSbest,IPS",
                        "operator_row_status": "blocked",
                        "needs_target_replacement": False,
                        "needs_core_files": True,
                        "needs_ablation_layers": True,
                        "needs_calibration": True,
                        "needs_provenance": True,
                        "next_action": "Fill row",
                        "blockers": "native_pdb_not_found",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    _write_csv(
        fill,
        [
            {
                "row_rank": 1,
                "benchmark_id": "hist_DEMO_MONOMER_001",
                "target_id": "DEMO_MONOMER_001",
                "evidence_class": "native_metric_gate",
                "completion_status": "missing",
            },
            {
                "row_rank": 2,
                "benchmark_id": "hist_DEMO_COMPLEX_001",
                "target_id": "DEMO_COMPLEX_001",
                "evidence_class": "native_metric_gate",
                "completion_status": "missing",
            },
        ],
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/casp17/build_casp17_win_tier_benchmark_input_scaffold.py"),
            "--operator-template-csv",
            str(template),
            "--operator-dashboard-json",
            str(dashboard),
            "--evidence-fill-kit-csv",
            str(fill),
            "--out-dir",
            str(tmp_path / "scaffold"),
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "packet.csv"),
            "--out-md",
            str(tmp_path / "packet.md"),
            "--out-manifest-draft-csv",
            str(tmp_path / "manifest_draft.csv"),
            "--out-calibration-draft-csv",
            str(tmp_path / "calibration_draft.csv"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "packet.json").read_text(encoding="utf-8"))
    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["scaffold_status"] == "ready"
    assert summary["row_count"] == 2
    assert summary["monomer_row_count"] == 1
    assert summary["complex_row_count"] == 1
    assert summary["required_prediction_file_count"] == 2
    assert summary["required_native_file_count"] == 2
    assert summary["required_ablation_file_count"] == 20
    assert summary["native_metric_gate_count"] == 2
    assert rows[1]["metric_profile"] == "TM,interface_F1,DockQ,QSbest,IPS"
    assert Path(rows[0]["row_readme"]).exists()
    assert Path(rows[0]["required_files_csv"]).exists()
    assert Path(rows[0]["provenance_template_csv"]).exists()
    assert Path(rows[0]["calibration_template_csv"]).exists()
    assert (tmp_path / "manifest_draft.csv").exists()
    assert (tmp_path / "calibration_draft.csv").exists()
    readme = Path(rows[0]["row_readme"]).read_text(encoding="utf-8")
    assert "Do not use a current CASP17 target native structure" in readme
    assert "Local input scaffold only" in summary["claim_boundary"]
