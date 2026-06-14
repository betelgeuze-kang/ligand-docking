from __future__ import annotations

import json
from pathlib import Path

from tools.accounting import apply_ligand_heavy_run_cleanup_manifest as apply_mod
from tools.accounting import build_ligand_residual_force_trajectory_retention as mod
from tools.builder_table_utils import write_csv_rows


def _write(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fixture(tmp_path: Path) -> tuple[Path, Path]:
    stage2 = tmp_path / "runs" / "residual_force_trajectory_regeneration_current" / "stage2_trajectory_frames"
    npz_a = stage2 / "shard_00000" / "a.npz"
    npz_b = stage2 / "shard_00000" / "b.npz"
    _write(npz_a, "payload-a")
    _write(npz_b, "payload-b")
    write_csv_rows(
        tmp_path / "runs" / "residual_force_trajectory_regeneration_queue_current.csv",
        [
            {
                "queue_id": "q-a",
                "original_queue_id": "orig-a",
                "target": "TRPV1",
                "ligand_id": "lig-a",
                "ligand_smiles": "CCO",
                "replica_idx": "1",
                "ligand_affinity_hint": "0.9",
                "expected_regenerated_trajectory_npz": "runs/residual_force_trajectory_regeneration_current/stage2_trajectory_frames/shard_00000/a.npz",
                "source_stage3_csv": "runs/source_stage3.csv",
                "native_pdb_path": "data/native/trpv1.pdb",
            },
            {
                "queue_id": "q-b",
                "original_queue_id": "orig-b",
                "target": "TRPV1",
                "ligand_id": "lig-b",
                "ligand_smiles": "CCC",
                "replica_idx": "2",
                "ligand_affinity_hint": "0.2",
                "expected_regenerated_trajectory_npz": "runs/residual_force_trajectory_regeneration_current/stage2_trajectory_frames/shard_00000/b.npz",
                "source_stage3_csv": "runs/source_stage3.csv",
                "native_pdb_path": "data/native/trpv1.pdb",
            },
        ],
    )
    write_csv_rows(
        tmp_path / "runs" / "residual_force_trajectory_regeneration_current_manifest.csv",
        [
            {
                "queue_id": "q-a",
                "target": "TRPV1",
                "ligand_id": "lig-a",
                "frames_written": "120",
                "backend": "rust_hip",
                "affinity_hint": "0.9",
                "quality_score": "0.5",
                "stability_score": "0.1",
                "contact_fraction": "0.2",
                "contact_fraction_6A": "0.3",
                "mean_min_distance_A": "4.0",
                "binding_energy_proxy": "-1.0",
                "binding_energy_mmpbsa_kcal_mol_proxy": "-2.0",
                "generated_npz": "runs/residual_force_trajectory_regeneration_current/stage2_trajectory_frames/shard_00000/a.npz",
            },
            {
                "queue_id": "q-b",
                "target": "TRPV1",
                "ligand_id": "lig-b",
                "frames_written": "66",
                "backend": "rust_hip",
                "affinity_hint": "0.2",
                "quality_score": "0.9",
                "stability_score": "0.1",
                "contact_fraction": "0.2",
                "contact_fraction_6A": "0.3",
                "mean_min_distance_A": "3.0",
                "binding_energy_proxy": "-1.0",
                "binding_energy_mmpbsa_kcal_mol_proxy": "-2.0",
                "generated_npz": "runs/residual_force_trajectory_regeneration_current/stage2_trajectory_frames/shard_00000/b.npz",
            },
        ],
    )
    _write(tmp_path / "runs" / "source_stage3.csv", "id,score\n")
    _write(
        tmp_path / "runs" / "residual_force_trajectory_regeneration_current_summary.json",
        json.dumps({"ok_rows": 2, "failed_rows": 0, "backend_counts": {"rust_hip": 2}}),
    )
    _write(tmp_path / "runs" / "residual_force_trajectory_regeneration_current_summary.md", "# summary\n")
    write_csv_rows(
        tmp_path / "runs" / "residual_force_trajectory_regeneration_current" / "stage2_trajectory_frames_target_tail.csv",
        [{"target": "TRPV1", "jobs": "2", "fps_mean": "1.0"}],
    )
    return npz_a, npz_b


def test_residual_force_retention_marks_npz_delete_and_keeps_top_rank(tmp_path: Path) -> None:
    _fixture(tmp_path)

    retention, manifest = mod.build_ligand_residual_force_trajectory_retention(root=tmp_path, topk_per_target=1)

    assert retention["summary"]["status"] == "ligand_residual_force_trajectory_compaction_ready"
    assert retention["summary"]["current_npz_count"] == 2
    assert retention["summary"]["retained_top_rank_count"] == 1
    assert retention["retained_top_rank"][0]["ligand_id"] == "lig-a"
    assert manifest["summary"]["delete_recommended_count"] == 2
    assert {row["delete_recommended"] for row in manifest["rows"]} == {True}


def test_residual_force_retention_manifest_is_compatible_with_ligand_apply(tmp_path: Path) -> None:
    npz_a, npz_b = _fixture(tmp_path)
    _, manifest = mod.build_ligand_residual_force_trajectory_retention(root=tmp_path)
    manifest_path = tmp_path / "runs" / "delete.json"
    _write(manifest_path, json.dumps(manifest))

    execution = apply_mod.apply_ligand_heavy_run_cleanup_manifest(
        root=tmp_path,
        manifest_json="runs/delete.json",
        execute=True,
        approval_token=apply_mod.APPROVAL_TOKEN,
    )

    assert execution["summary"]["deleted_count"] == 2
    assert not npz_a.exists()
    assert not npz_b.exists()


def test_residual_force_retention_reports_complete_after_execution(tmp_path: Path) -> None:
    npz_a, npz_b = _fixture(tmp_path)
    _, manifest = mod.build_ligand_residual_force_trajectory_retention(root=tmp_path)
    _write(tmp_path / "runs" / "ligand_residual_force_trajectory_cleanup_manifest_current.json", json.dumps(manifest))
    npz_a.unlink()
    npz_b.unlink()
    _write(
        tmp_path / "runs" / "ligand_residual_force_trajectory_cleanup_execution_current.json",
        json.dumps(
            {
                "summary": {
                    "delete_executed": True,
                    "deleted_count": 2,
                    "deleted_size_bytes": 18,
                    "deleted_size_human": "18 B",
                    "failed_count": 0,
                }
            }
        ),
    )

    retention, _ = mod.build_ligand_residual_force_trajectory_retention(root=tmp_path)

    assert retention["summary"]["status"] == "ligand_residual_force_trajectory_compaction_complete"
    assert retention["summary"]["delete_recommended_count"] == 2
    assert retention["summary"]["post_delete_npz_present_count"] == 0
