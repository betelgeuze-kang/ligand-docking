from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_build_gpcr_frozen_pose_support_gap_packet_blocks_missing_positive_support(tmp_path: Path) -> None:
    scores_csv = tmp_path / "scores.csv"
    labels_csv = tmp_path / "labels.csv"
    out_json = tmp_path / "gap.json"
    out_csv = tmp_path / "gap.csv"
    out_md = tmp_path / "gap.md"
    score_rows = [
        {
            "target": "T1",
            "ligand_id": "P1",
            "base_score": -5.0,
            "binding_score_composite_v7_residual_shadow": -7.0,
            "label_free_support_pressure": 0.60,
            "weak_base_rescue_support_pressure": 0.30,
            "pose_preservation_support": 1.0,
            "coarse_centroid_preservation_rmsd_A_mean": 0.8,
            "basic_amine_count": 2,
            "multipolar_basic_pressure": 0.0,
            "gpcr_synthetic_anchor_saturation_pressure_v12": 0.0,
            "gpcr_moderate_multi_basic_weakbase_support_v12": 0.2,
        },
        {
            "target": "T1",
            "ligand_id": "D1",
            "base_score": -4.0,
            "binding_score_composite_v7_residual_shadow": -4.0,
            "label_free_support_pressure": 0.0,
            "weak_base_rescue_support_pressure": 0.0,
            "pose_preservation_support": 0.0,
            "coarse_centroid_preservation_rmsd_A_mean": 7.0,
            "basic_amine_count": 1,
            "multipolar_basic_pressure": 0.0,
            "gpcr_synthetic_anchor_saturation_pressure_v12": 0.0,
            "gpcr_moderate_multi_basic_weakbase_support_v12": 0.0,
        },
        {
            "target": "T2",
            "ligand_id": "D2",
            "base_score": -9.0,
            "binding_score_composite_v7_residual_shadow": -8.0,
            "label_free_support_pressure": 0.40,
            "weak_base_rescue_support_pressure": 0.0,
            "pose_preservation_support": 0.8,
            "coarse_centroid_preservation_rmsd_A_mean": 1.1,
            "basic_amine_count": 2,
            "multipolar_basic_pressure": 0.50,
            "gpcr_synthetic_anchor_saturation_pressure_v12": 0.0,
            "gpcr_moderate_multi_basic_weakbase_support_v12": 0.0,
        },
        {
            "target": "T2",
            "ligand_id": "P2",
            "base_score": -4.0,
            "binding_score_composite_v7_residual_shadow": -4.0,
            "label_free_support_pressure": 0.0,
            "weak_base_rescue_support_pressure": 0.0,
            "pose_preservation_support": 0.0,
            "coarse_centroid_preservation_rmsd_A_mean": 34.0,
            "basic_amine_count": 2,
            "multipolar_basic_pressure": 0.0,
            "gpcr_synthetic_anchor_saturation_pressure_v12": 0.0,
            "gpcr_moderate_multi_basic_weakbase_support_v12": 0.0,
        },
    ]
    _write_csv(scores_csv, score_rows)
    _write_csv(
        labels_csv,
        [
            {"target": "T1", "ligand_id": "P1", "is_binder": "true"},
            {"target": "T1", "ligand_id": "D1", "is_binder": "false"},
            {"target": "T2", "ligand_id": "P2", "is_binder": "true"},
            {"target": "T2", "ligand_id": "D2", "is_binder": "false"},
        ],
    )

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/gpcr_replay/build_gpcr_frozen_pose_support_gap_packet.py"),
            "--input-scores-csv",
            str(scores_csv),
            "--label-csv",
            str(labels_csv),
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
    summary = payload["summary"]
    t2 = next(row for row in payload["target_summaries"] if row["target"] == "T2")

    assert summary["status"] == "blocked_pose_support_gap_claim_locked"
    assert summary["claim_promotion_allowed"] is False
    assert summary["scorer_apply_allowed"] is False
    assert summary["labels_used_for_scoring"] is False
    assert summary["blocker_counts"]["positive_anchor_support_missing"] == 1
    assert summary["blocker_counts"]["positive_pose_backmapping_collapse"] == 1
    assert t2["decoys_above_positive"] == 1
    assert "base_score_decoy_intrusion" in t2["blockers"]
    assert out_csv.exists()
    assert "GPCR Frozen Pose Support Gap Packet" in out_md.read_text(encoding="utf-8")
