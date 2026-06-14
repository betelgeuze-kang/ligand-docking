from __future__ import annotations

import json
from pathlib import Path

from tools.accounting import build_npz_dynamics_cleanup_manifest as mod


def _write(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_npz_dynamics_cleanup_manifest_protects_current_references(tmp_path: Path) -> None:
    old_npz = tmp_path / "runs" / "old_run_stage2_traj_frames" / "shard_00000" / "old.npz"
    ref_npz = tmp_path / "runs" / "wetlab_stage2_traj_frames" / "shard_00000" / "selected.npz"
    current_npz = tmp_path / "runs" / "residual_force_trajectory_regeneration_current" / "stage2_trajectory_frames" / "shard_00000" / "current.npz"
    non_dyn_npz = tmp_path / "data" / "feature_cache.npz"
    _write(old_npz, "old")
    _write(ref_npz, "ref")
    _write(current_npz, "current")
    _write(non_dyn_npz, "cache")
    _write(
        tmp_path / "runs" / "wetlab_current.json",
        json.dumps({"rows": [{"trajectory_npz": str(ref_npz.relative_to(tmp_path))}]}),
    )
    _write(
        tmp_path / "runs" / "product_release_source_of_truth_gate_current.json",
        json.dumps({"rows": [{"artifact_path": "runs/wetlab_current.json"}]}),
    )

    payload = mod.build_npz_dynamics_cleanup_manifest(root=tmp_path)
    rows = {row["path"]: row for row in payload["rows"]}
    summary = payload["summary"]

    assert summary["status"] == "npz_dynamics_cleanup_manifest_ready"
    assert summary["candidate_count"] == 4
    assert rows[str(old_npz.relative_to(tmp_path))]["delete_recommended"] is True
    assert rows[str(ref_npz.relative_to(tmp_path))]["disposition"] == "keep_referenced_current_evidence"
    assert rows[str(current_npz.relative_to(tmp_path))]["disposition"] == "review_current_regenerable_dynamics_payload"
    assert rows[str(non_dyn_npz.relative_to(tmp_path))]["disposition"] == "review_non_dynamics_npz_payload"
    assert summary["cleanup_allowed_count"] == 0
    assert summary["delete_executed"] is False


def test_npz_dynamics_cleanup_manifest_missing_runs_stays_read_only(tmp_path: Path) -> None:
    _write(tmp_path / "data" / "cache.npz", "cache")

    payload = mod.build_npz_dynamics_cleanup_manifest(root=tmp_path, runs_dir="missing_runs")
    summary = payload["summary"]

    assert summary["current_json_source_count"] == 0
    assert summary["candidate_count"] == 1
    assert summary["delete_recommended_count"] == 0
    assert summary["external_state_mutated"] is False
