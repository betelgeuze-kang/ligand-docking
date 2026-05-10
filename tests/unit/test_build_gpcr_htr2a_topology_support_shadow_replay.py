from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from tools import build_gpcr_htr2a_topology_support_shadow_replay as mod

ROOT = Path(__file__).resolve().parents[2]


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _fixture_inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    input_scores = tmp_path / "scores.csv"
    stage3 = tmp_path / "stage3.csv"
    pose_gap = tmp_path / "pose_gap.json"
    life_science = tmp_path / "life_science.json"
    _write_csv(
        input_scores,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                mod.DEFAULT_SCORE_COL: 1.0,
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "drd2_decoy_1",
                mod.DEFAULT_SCORE_COL: 0.5,
            },
            {
                "target": "CHEMBL224_HTR2A_HUMAN",
                "ligand_id": "CHEMBL83894",
                mod.DEFAULT_SCORE_COL: 0.6,
            },
            {
                "target": "CHEMBL224_HTR2A_HUMAN",
                "ligand_id": "htr2a_decoy_1",
                mod.DEFAULT_SCORE_COL: 0.25,
            },
            {
                "target": "CHEMBL233_OPRM1_HUMAN",
                "ligand_id": "CHEMBL331883",
                mod.DEFAULT_SCORE_COL: 2.0,
            },
            {
                "target": "CHEMBL233_OPRM1_HUMAN",
                "ligand_id": "oprm1_decoy_1",
                mod.DEFAULT_SCORE_COL: 1.0,
            },
        ],
    )
    _write_csv(
        stage3,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "ligand_smiles": "CN1CCCCC1",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "drd2_decoy_1",
                "ligand_smiles": "c1ccccc1",
            },
            {
                "target": "CHEMBL224_HTR2A_HUMAN",
                "ligand_id": "CHEMBL83894",
                "ligand_smiles": "O=S1(=O)c2cccc3cccc(c23)N1CCCN1CCN(c2ccc(F)cc2)CC1",
            },
            {
                "target": "CHEMBL224_HTR2A_HUMAN",
                "ligand_id": "htr2a_decoy_1",
                "ligand_smiles": "c1ccccc1",
            },
            {
                "target": "CHEMBL233_OPRM1_HUMAN",
                "ligand_id": "CHEMBL331883",
                "ligand_smiles": "CN1CCCCC1",
            },
            {
                "target": "CHEMBL233_OPRM1_HUMAN",
                "ligand_id": "oprm1_decoy_1",
                "ligand_smiles": "c1ccccc1",
            },
        ],
    )
    _write_json(
        pose_gap,
        {
            "target_summaries": [
                {"target": "CHEMBL217_DRD2_HUMAN", "ligand_id": "CHEMBL301265"},
                {"target": "CHEMBL224_HTR2A_HUMAN", "ligand_id": "CHEMBL83894"},
                {"target": "CHEMBL233_OPRM1_HUMAN", "ligand_id": "CHEMBL331883"},
            ]
        },
    )
    _write_json(
        life_science,
        {
            "summary": {
                "status": "life_science_evidence_supports_claim_locked_htr2a_topology_probe"
            }
        },
    )
    return input_scores, stage3, pose_gap, life_science


def test_build_replay_selects_minimal_green_weight_without_non_htr2a_regression(tmp_path: Path) -> None:
    input_scores, stage3, pose_gap, life_science = _fixture_inputs(tmp_path)

    payload, grid_rows, score_rows = mod.build_replay(
        input_scores_csv=input_scores,
        stage3_scores_csv=stage3,
        pose_gap_json=pose_gap,
        life_science_evidence_json=life_science,
        grid="0,0.25,0.5,1",
        generated_at_local="2026-05-09T01:00:00+09:00",
    )

    summary = payload["summary"]
    grid_by_weight = {row["support_weight"]: row for row in grid_rows}
    positive_row = next(
        row
        for row in score_rows
        if row["target"] == "CHEMBL224_HTR2A_HUMAN" and row["ligand_id"] == "CHEMBL83894"
    )
    assert summary["status"] == "htr2a_topology_support_shadow_replay_selected_slice_green_claim_locked"
    assert summary["claim_promotion_allowed"] is False
    assert summary["scorer_apply_allowed"] is False
    assert summary["guarded_100k_rerun_allowed"] is False
    assert summary["active_score_locked_to_base"] is True
    assert summary["topology_support_row_count"] == 1
    assert summary["selected_support_weight"] == 0.5
    assert summary["selected_htr2a_target_rank"] == 1
    assert summary["selected_htr2a_decoys_above_positive"] == 0
    assert summary["selected_non_htr2a_regression_count"] == 0
    assert grid_by_weight[0.0]["htr2a_target_rank"] == 2
    assert grid_by_weight[0.25]["htr2a_target_rank"] == 2
    assert grid_by_weight[0.5]["selected_slice_green"] is True
    assert grid_by_weight[0.5]["regression_count"] == 0
    assert positive_row["htr2a_atom_typed_topology_support_probe"] == 1.0
    assert abs(float(positive_row[mod.DEFAULT_SHADOW_SCORE_COL]) - 0.1) < 1.0e-9
    assert payload["claim_boundary"]["target_identity_feature_allowed"] is False


def test_replay_cli_writes_summary_grid_and_scores(tmp_path: Path) -> None:
    input_scores, stage3, pose_gap, life_science = _fixture_inputs(tmp_path)
    out_json = tmp_path / "summary.json"
    out_grid = tmp_path / "grid.csv"
    out_scores = tmp_path / "scores.csv"
    out_md = tmp_path / "summary.md"

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_htr2a_topology_support_shadow_replay.py"),
            "--input-scores-csv",
            str(input_scores),
            "--stage3-scores-csv",
            str(stage3),
            "--pose-gap-json",
            str(pose_gap),
            "--life-science-evidence-json",
            str(life_science),
            "--grid",
            "0,0.5",
            "--out-json",
            str(out_json),
            "--out-grid-csv",
            str(out_grid),
            "--out-scores-csv",
            str(out_scores),
            "--out-md",
            str(out_md),
        ],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert result.returncode == 0
    assert payload["summary"]["selected_support_weight"] == 0.5
    assert "support_weight" in out_grid.read_text(encoding="utf-8")
    assert mod.DEFAULT_SHADOW_SCORE_COL in out_scores.read_text(encoding="utf-8")
    assert "GPCR HTR2A Topology-Support Shadow Replay" in out_md.read_text(encoding="utf-8")
