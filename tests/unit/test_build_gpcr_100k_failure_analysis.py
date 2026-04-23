from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "target",
                "ligand_id",
                "is_binder",
                "reference_binding_kcal_mol",
                "binding_score_composite_v7",
                "mean_min_distance_A",
                "role",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def test_build_gpcr_100k_failure_analysis(tmp_path: Path) -> None:
    baseline = tmp_path / "runs" / "baseline.csv"
    scaleup = tmp_path / "runs" / "scaleup.csv"
    _write_rows(
        baseline,
        [
            {"target": "ADRB2", "ligand_id": "b1", "is_binder": "1", "reference_binding_kcal_mol": "-9", "binding_score_composite_v7": "-9.0", "mean_min_distance_A": "4.0", "role": "far_ood_eval"},
            {"target": "ADRB2", "ligand_id": "b2", "is_binder": "1", "reference_binding_kcal_mol": "-8", "binding_score_composite_v7": "-8.0", "mean_min_distance_A": "4.1", "role": "far_ood_eval"},
            {"target": "ADRB2", "ligand_id": "d1", "is_binder": "0", "reference_binding_kcal_mol": "-3", "binding_score_composite_v7": "-7.0", "mean_min_distance_A": "4.2", "role": "far_ood_eval"},
        ],
    )
    _write_rows(
        scaleup,
        [
            {"target": "ADRB2", "ligand_id": "b1", "is_binder": "1", "reference_binding_kcal_mol": "-9", "binding_score_composite_v7": "-9.0", "mean_min_distance_A": "4.0", "role": "far_ood_eval"},
            {"target": "ADRB2", "ligand_id": "d1", "is_binder": "0", "reference_binding_kcal_mol": "-3", "binding_score_composite_v7": "-8.5", "mean_min_distance_A": "4.2", "role": "far_ood_eval"},
            {"target": "ADRB2", "ligand_id": "d2", "is_binder": "0", "reference_binding_kcal_mol": "-3", "binding_score_composite_v7": "-8.4", "mean_min_distance_A": "4.3", "role": "far_ood_eval"},
            {"target": "ADRB2", "ligand_id": "b2", "is_binder": "1", "reference_binding_kcal_mol": "-8", "binding_score_composite_v7": "-8.0", "mean_min_distance_A": "4.1", "role": "far_ood_eval"},
        ],
    )
    out_json = tmp_path / "runs" / "analysis.json"
    out_csv = tmp_path / "runs" / "analysis.csv"
    out_md = tmp_path / "runs" / "analysis.md"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_100k_failure_analysis.py"),
            "--baseline-csv",
            str(baseline),
            "--scaleup-csv",
            str(scaleup),
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
    assert payload["summary"]["baseline_positive_ranks"] == [1, 2]
    assert payload["summary"]["scaleup_positive_ranks"] == [1, 4]
    assert payload["summary"]["scaleup_top20_binder_count"] == 2

