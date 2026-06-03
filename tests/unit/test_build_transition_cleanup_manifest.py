from __future__ import annotations

from pathlib import Path

from tools import build_transition_cleanup_manifest as mod


def _touch(path: Path, size: int = 16) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)


def test_transition_cleanup_manifest_classifies_heavy_paths(tmp_path: Path) -> None:
    _touch(tmp_path / "casp17/massivefold_external_pool_intake/pool_a/model.cif")
    _touch(tmp_path / "runs/archive/old_run.json")
    _touch(tmp_path / "runs/legacy/stage2_traj_frames/frame_001.pdb")
    _touch(tmp_path / "rust_engine/target/debug/libkernel.a")
    _touch(tmp_path / ".venv/bin/python")

    payload = mod.build_payload(str(tmp_path))
    summary = payload["summary"]
    rows = {row["path"]: row for row in payload["rows"]}

    assert summary["status"] == "transition_cleanup_manifest_dry_run_ready"
    assert summary["delete_executed"] is False
    assert summary["external_state_mutated"] is False
    assert summary["operator_approval_required_count"] >= 4
    assert summary["approval_gated_reclaim_size_bytes"] > 0
    assert rows["casp17/massivefold_external_pool_intake"]["recommended_action"] == "externalize"
    assert rows["casp17/massivefold_external_pool_intake"]["approval_token"] == "APPROVE_EXTERNALIZE_HEAVY_ARTIFACTS"
    assert rows["runs/archive"]["recommended_action"] == "archive"
    assert rows["runs/archive"]["execution_phase"] == "P1_archive_after_snapshot"
    assert rows["runs/legacy/stage2_traj_frames"]["recommended_action"] == "review_for_stage2_traj_frames"
    assert rows["runs/legacy/stage2_traj_frames"]["approval_token"] == ""
    assert rows["rust_engine/target"]["recommended_action"] == "delete_candidate"
    assert rows["rust_engine/target"]["postcheck"]
    assert rows[".venv"]["operator_approval_required"] is True


def test_transition_cleanup_manifest_discovers_ligand_heavy_roots_from_configs(tmp_path: Path) -> None:
    heavy_root = tmp_path / "external" / "ligand_heavy_runs"
    _touch(heavy_root / "ligand_old_run" / "stage2_trajectory_frames" / "traj.xtc")
    config = tmp_path / "config" / "ligand_htvs_smoke.json"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(
        '{"heavy_artifacts_root": "' + str(heavy_root).replace("\\", "\\\\") + '"}\n',
        encoding="utf-8",
    )

    payload = mod.build_payload(str(tmp_path))
    rows = {row["path"]: row for row in payload["rows"]}
    row = rows["external/ligand_heavy_runs"]

    assert row["recommended_action"] == "review_for_ligand_heavy_payload_cleanup"
    assert row["lane"] == "ligand_heavy_runs_config_root"
    assert row["operator_approval_required"] is False
    assert row["hash_strategy"] == "du_size_only_external_root"
    assert row["config_reference_count"] == 1
    assert "config/ligand_htvs_smoke.json" in row["config_references"]
    assert "cleanup_ligand_heavy_runs.py" in row["postcheck"]
