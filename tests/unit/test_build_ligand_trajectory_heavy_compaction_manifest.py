from __future__ import annotations

import json
from pathlib import Path

from tools.accounting import build_ligand_trajectory_heavy_compaction_manifest as mod


def _write(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _summary(path: Path, trajectory_npz: str) -> None:
    _write(
        path,
        json.dumps(
            {
                "active_score_col": "binding_score_composite_v7",
                "topk": [
                    {
                        "export_rank": 1,
                        "queue_id": "q1",
                        "target": "T. cruzi PDE",
                        "ligand_id": "lig1",
                        "ligand_smiles": "CCO",
                        "binding_score_composite_v7": -5.0,
                        "binding_energy_mmpbsa_kcal_mol_proxy": -0.4,
                        "trajectory_npz": trajectory_npz,
                        "trajectory_frames": 300,
                    }
                ],
            }
        ),
    )


def test_compaction_manifest_keeps_topk_and_marks_npz_delete_recommended(tmp_path: Path) -> None:
    run_root = tmp_path / "runs" / "wetlab"
    rel_npz = "runs/wetlab/stage2_traj_frames/shard_00000/a.npz"
    _write(tmp_path / rel_npz, "payload")
    _summary(run_root / "stage3_summary.json", rel_npz)

    retention, manifest = mod.build_ligand_trajectory_heavy_compaction_manifest(
        root=tmp_path,
        run_roots=("runs/wetlab",),
        delete_manifest_json="runs/delete.json",
    )

    assert retention["summary"]["status"] == "ligand_trajectory_heavy_compaction_ready"
    assert retention["summary"]["heavy_npz_count"] == 1
    assert retention["retained_topk"][0]["ligand_id"] == "lig1"
    assert manifest["rows"][0]["path"] == rel_npz
    assert manifest["rows"][0]["delete_recommended"] is True


def test_compaction_manifest_blocks_npz_without_topk_evidence(tmp_path: Path) -> None:
    _write(tmp_path / "runs" / "wetlab" / "stage2_traj_frames" / "shard_00000" / "a.npz", "payload")

    retention, manifest = mod.build_ligand_trajectory_heavy_compaction_manifest(
        root=tmp_path,
        run_roots=("runs/wetlab",),
        delete_manifest_json="runs/delete.json",
    )

    assert retention["summary"]["status"] == "blocked_ligand_trajectory_heavy_compaction"
    assert retention["summary"]["blocked_count"] == 1
    assert manifest["rows"][0]["delete_recommended"] is False


def test_compaction_manifest_finds_prefixed_stage2_traj_frame_dirs(tmp_path: Path) -> None:
    run_root = tmp_path / "runs" / "wetlab"
    rel_npz = "runs/wetlab/stage9_stage2_traj_frames/shard_00000/a.npz"
    _write(tmp_path / rel_npz, "payload")
    _summary(run_root / "stage9_stage3_summary.json", rel_npz)

    retention, manifest = mod.build_ligand_trajectory_heavy_compaction_manifest(
        root=tmp_path,
        run_roots=("runs/wetlab",),
        delete_manifest_json="runs/delete.json",
    )

    assert retention["summary"]["heavy_npz_count"] == 1
    assert manifest["rows"][0]["path"] == rel_npz
