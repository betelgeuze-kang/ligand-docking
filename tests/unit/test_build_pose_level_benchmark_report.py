from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from tools.product.build_pose_level_benchmark_report import build_pose_level_benchmark_report


def test_pose_level_benchmark_report_summarizes_thresholds(tmp_path: Path) -> None:
    scores_csv = tmp_path / "scores.csv"
    pd.DataFrame(
        [
            {
                "target": "T1",
                "ligand_id": "L1",
                "pose_rmsd_A": 1.2,
                "clash_count": 0,
                "ligand_strain_kcal_mol": 4.0,
                "hbond_geometry_score": 0.6,
                "contact_recovery": 0.5,
            },
            {
                "target": "T1",
                "ligand_id": "L2",
                "pose_rmsd_A": 3.4,
                "clash_count": 2,
                "ligand_strain_kcal_mol": 12.0,
                "hbond_geometry_score": 0.2,
                "contact_recovery": 0.1,
            },
        ]
    ).to_csv(scores_csv, index=False)
    out_json = tmp_path / "report.json"
    out_md = tmp_path / "report.md"

    payload = build_pose_level_benchmark_report(str(scores_csv), out_json=str(out_json), out_md=str(out_md))

    assert payload["summary"]["status"] == "pose_level_benchmark_threshold_review"
    assert payload["summary"]["row_count"] == 2
    assert payload["summary"]["missing_required_metrics"] == []
    assert payload["summary"]["blocked_metric_row_count"] == 1
    assert payload["metric_summaries"]["pose_rmsd_A"]["pass_rate"] == 0.5
    assert payload["blocked_rows"][0]["row_id"] == "T1::L2"
    assert out_json.exists()
    assert out_md.exists()
    on_disk = json.loads(out_json.read_text(encoding="utf-8"))
    assert on_disk["summary"]["claim_boundary"].startswith("Pose-level benchmark")


def test_pose_level_benchmark_report_marks_missing_required_metrics(tmp_path: Path) -> None:
    scores_csv = tmp_path / "scores_minimal.csv"
    pd.DataFrame([{"target": "T1", "ligand_id": "L1", "pose_rmsd_A": 1.0}]).to_csv(scores_csv, index=False)

    payload = build_pose_level_benchmark_report(str(scores_csv), out_json=str(tmp_path / "report.json"))

    assert payload["summary"]["status"] == "pose_level_benchmark_incomplete"
    assert "clash_count" in payload["summary"]["missing_required_metrics"]
    assert "contact_recovery" in payload["summary"]["missing_required_metrics"]
