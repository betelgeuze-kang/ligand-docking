from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_build_global_residual_correction_target_list(tmp_path: Path) -> None:
    gpcr_failure_json = tmp_path / "gpcr_failure.json"
    kpi_json = tmp_path / "kpi.json"
    audit_json = tmp_path / "audit.json"
    ranking_csv = tmp_path / "ranking.csv"
    stage3_csv = tmp_path / "stage3.csv"
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"

    gpcr_failure_json.write_text(
        json.dumps(
            {
                "summary": {
                    "scaleup_positive_ranks": [1, 2, 15, 78],
                }
            }
        ),
        encoding="utf-8",
    )
    kpi_json.write_text(
        json.dumps(
            {
                "summary": {"mean_stage2_share_pct": 86.0},
                "rows": [
                    {"task_id": "gpcr_core_full", "stage2_share_pct": 83.4, "max_required_speedup_to_target": 1.55},
                    {"task_id": "ion_trpv1_chembl20_full", "stage2_share_pct": 90.2, "max_required_speedup_to_target": 1.94},
                    {"task_id": "kinase_core_full", "stage2_share_pct": 89.3, "max_required_speedup_to_target": 3.01},
                ],
            }
        ),
        encoding="utf-8",
    )
    audit_json.write_text(
        json.dumps({"summary": {"valid_completed_test_run": True}}),
        encoding="utf-8",
    )
    with ranking_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["ligand_id", "is_binder", "role"])
        writer.writeheader()
        writer.writerows(
            [
                {"ligand_id": "b1", "is_binder": "1", "role": "eval"},
                {"ligand_id": "b2", "is_binder": "1", "role": "eval"},
                {"ligand_id": "d1", "is_binder": "0", "role": "eval"},
                {"ligand_id": "d2", "is_binder": "0", "role": "eval"},
            ]
        )
    with stage3_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "ligand_id",
                "binding_energy_proxy",
                "contact_fraction",
                "mean_min_distance_A",
                "ligand_affinity_hint",
            ],
        )
        writer.writeheader()
        writer.writerows(
            [
                {
                    "ligand_id": "b1",
                    "binding_energy_proxy": "-0.3",
                    "contact_fraction": "0.005",
                    "mean_min_distance_A": "4.0",
                    "ligand_affinity_hint": "0.6",
                },
                {
                    "ligand_id": "b2",
                    "binding_energy_proxy": "-0.2",
                    "contact_fraction": "0.004",
                    "mean_min_distance_A": "4.1",
                    "ligand_affinity_hint": "0.5",
                },
                {
                    "ligand_id": "d1",
                    "binding_energy_proxy": "0.02",
                    "contact_fraction": "0.002",
                    "mean_min_distance_A": "4.8",
                    "ligand_affinity_hint": "0.4",
                },
                {
                    "ligand_id": "d2",
                    "binding_energy_proxy": "-0.1",
                    "contact_fraction": "0.003",
                    "mean_min_distance_A": "4.6",
                    "ligand_affinity_hint": "0.45",
                },
            ]
        )

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_global_residual_correction_target_list.py"),
            "--gpcr-failure-json",
            str(gpcr_failure_json),
            "--kpi-json",
            str(kpi_json),
            "--scaleup-audit-json",
            str(audit_json),
            "--gpcr-ranking-csv",
            str(ranking_csv),
            "--gpcr-stage3-csv",
            str(stage3_csv),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["valid_completed_100k_test_run"] is True
    scopes = [row["scope"] for row in payload["rows"]]
    assert "global" in scopes
    assert "gpcr" in scopes
    assert "idp" in scopes
    gpcr_row = next(row for row in payload["rows"] if row["scope"] == "gpcr")
    assert "energy/contact" in gpcr_row["correction_goal"]
    assert "decoy_mean_energy" in gpcr_row["supporting_metrics"]

