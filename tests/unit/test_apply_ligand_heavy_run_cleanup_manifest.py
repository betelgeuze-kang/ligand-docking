from __future__ import annotations

import json
from pathlib import Path

from tools.accounting import apply_ligand_heavy_run_cleanup_manifest as mod


def _write(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _manifest(path: Path, rel_file: str, rel_dir: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "summary": {"status": "ligand_heavy_run_cleanup_manifest_ready"},
                "rows": [
                    {
                        "path": rel_file,
                        "path_type": "file",
                        "size_bytes": 3,
                        "cleanup_class": "raw_stage1_ligand_inventory",
                        "disposition": "delete_after_top_rank_manifest_approval",
                        "delete_recommended": True,
                    },
                    {
                        "path": rel_dir,
                        "path_type": "directory",
                        "size_bytes": 4,
                        "cleanup_class": "raw_stage2_trajectory_sidecar",
                        "disposition": "delete_after_top_rank_manifest_approval",
                        "delete_recommended": True,
                    },
                    {
                        "path": "runs/keep/ligand_stage5_ranking_topk.csv",
                        "path_type": "file",
                        "size_bytes": 5,
                        "cleanup_class": "top_ranking_evidence",
                        "disposition": "keep_top_ranking_or_compact_evidence",
                        "delete_recommended": False,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def test_apply_ligand_cleanup_manifest_dry_run_does_not_delete(tmp_path: Path) -> None:
    rel_file = "runs/old/ligand_stage1_ligands.json"
    rel_dir = "runs/old/ligand_stage2_traj_frames"
    _write(tmp_path / rel_file, "old")
    _write(tmp_path / rel_dir / "payload.txt", "payload")
    manifest = tmp_path / "runs" / "ligand_heavy_run_cleanup_manifest_current.json"
    _manifest(manifest, rel_file, rel_dir)

    payload = mod.apply_ligand_heavy_run_cleanup_manifest(root=tmp_path, manifest_json=manifest.relative_to(tmp_path))

    assert (tmp_path / rel_file).exists()
    assert (tmp_path / rel_dir).exists()
    assert payload["summary"]["delete_executed"] is False
    assert payload["summary"]["pending_count"] == 2


def test_apply_ligand_cleanup_manifest_execute_requires_token(tmp_path: Path) -> None:
    rel_file = "runs/old/ligand_stage1_ligands.json"
    rel_dir = "runs/old/ligand_stage2_traj_frames"
    _write(tmp_path / rel_file, "old")
    _write(tmp_path / rel_dir / "payload.txt", "payload")
    manifest = tmp_path / "runs" / "ligand_heavy_run_cleanup_manifest_current.json"
    _manifest(manifest, rel_file, rel_dir)

    payload = mod.apply_ligand_heavy_run_cleanup_manifest(
        root=tmp_path,
        manifest_json=manifest.relative_to(tmp_path),
        execute=True,
        approval_token=mod.APPROVAL_TOKEN,
    )

    assert not (tmp_path / rel_file).exists()
    assert not (tmp_path / rel_dir).exists()
    assert payload["summary"]["delete_executed"] is True
    assert payload["summary"]["deleted_count"] == 2
    assert payload["summary"]["external_state_mutated"] is False
