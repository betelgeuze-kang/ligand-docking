from __future__ import annotations

from pathlib import Path

from tools.gpcr_replay.build_gpcr_frozen_trajectory_storage_gap_packet import build_packet


def test_gpcr_trajectory_gap_detects_stage2_missing_and_missing_npz(tmp_path: Path) -> None:
    mount_root = tmp_path / "ligand_heavy_runs"
    run_root = (
        mount_root
        / "external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full_p0_n100000_r1"
    )
    (run_root / "stage3_delivery").mkdir(parents=True)
    npz_path = run_root / "stage2_trajectory_frames" / "shard_00031" / "positive.npz"
    repair_rows = [{"trajectory_npz": str(npz_path), "ligand_id": "CHEMBL301265"}]
    payload = build_packet(
        repair_packet={
            "positive_row": {
                "ligand_id": "CHEMBL301265",
                "trajectory_npz": str(npz_path),
            }
        },
        repair_rows=repair_rows,
        backmapping_packet={"summary": {"input_row_count": 1, "failed_row_count": 1, "repaired_row_count": 0}, "rows": []},
        readiness_packet={"summary": {"launch_eligible": True, "claim_review_eligible": False}},
        mount_root=str(mount_root),
        generated_at_local="2026-06-07T00:00:00+09:00",
    )
    summary = payload["summary"]
    assert summary["status"] == "blocked_frozen_trajectory_storage_gap"
    assert summary["stage2_missing_run_count"] == 1
    assert summary["repair_slice_npz_missing_count"] == 1
    assert summary["drd2_repair_blocked"] is True
    assert "stage2_trajectory_frames_missing" in summary["blockers"]
    assert "repair_slice_source_npz_missing" in summary["blockers"]


def test_gpcr_trajectory_gap_ready_when_stage2_and_npz_exist(tmp_path: Path) -> None:
    mount_root = tmp_path / "ligand_heavy_runs"
    run_root = mount_root / "gpcr_run_r1"
    npz_path = run_root / "stage2_trajectory_frames" / "shard_00001" / "positive.npz"
    npz_path.parent.mkdir(parents=True)
    npz_path.write_bytes(b"npz")
    repair_rows = [{"trajectory_npz": str(npz_path), "ligand_id": "CHEMBL301265"}]
    payload = build_packet(
        repair_packet={"positive_row": {"ligand_id": "CHEMBL301265", "trajectory_npz": str(npz_path)}},
        repair_rows=repair_rows,
        backmapping_packet={"summary": {"input_row_count": 1, "failed_row_count": 0, "repaired_row_count": 1}, "rows": []},
        readiness_packet={"summary": {"launch_eligible": True, "claim_review_eligible": True}},
        mount_root=str(mount_root),
        generated_at_local="2026-06-07T00:00:00+09:00",
    )
    summary = payload["summary"]
    assert summary["repair_slice_npz_missing_count"] == 0
    assert summary["positive_trajectory_npz_exists"] is True
    assert summary["drd2_repair_blocked"] is False
    assert "stage2_trajectory_frames_missing" not in summary["blockers"]
    assert "repair_slice_source_npz_missing" not in summary["blockers"]
