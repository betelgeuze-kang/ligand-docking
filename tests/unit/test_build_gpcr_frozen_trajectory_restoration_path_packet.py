from __future__ import annotations

from pathlib import Path

from tools.gpcr_replay.build_gpcr_frozen_trajectory_restoration_path_packet import (
    build_local_reuse_repair_rows,
    build_overlay_rows,
    build_packet,
)


def test_restoration_path_maps_local_pseudo_npz_for_repair_rows(tmp_path: Path) -> None:
    local_root = tmp_path / "pseudo"
    local_root.mkdir()
    repair_rows = [
        {"target": "CHEMBL217_DRD2_HUMAN", "ligand_id": "CHEMBL301265", "trajectory_npz": "/missing/mount.npz"},
        {"target": "CHEMBL217_DRD2_HUMAN", "ligand_id": "decoy_001", "trajectory_npz": ""},
    ]
    for row in repair_rows:
        npz_path = local_root / f"{row['target']}__{row['ligand_id']}.npz"
        npz_path.write_bytes(b"placeholder")

    overlay_rows = build_overlay_rows(repair_rows, local_root)
    assert len(overlay_rows) == 2
    assert overlay_rows[0]["restoration_path"] == "interim_local_pseudo_allatom"
    assert overlay_rows[0]["restoration_source_exists"] == "True"
    assert str(local_root) in overlay_rows[0]["trajectory_npz"]

    payload = build_packet(
        repair_rows=repair_rows,
        gap_packet={"summary": {"drd2_repair_blocked": True}},
        mount_root=str(tmp_path / "mount"),
        local_pseudo_root=str(local_root),
        frozen_run_id="frozen_run",
        generated_at_local="2026-06-07T00:00:00+09:00",
    )
    summary = payload["summary"]
    assert summary["local_pseudo_mapped_row_count"] == 2
    assert summary["recommended_interim_path_id"] == "interim_local_pseudo_allatom_overlay"
    assert summary["claim_promotion_allowed"] is False


def test_restoration_path_builds_local_reuse_rows_for_readable_npz(tmp_path: Path) -> None:
    local_root = tmp_path / "pseudo"
    local_root.mkdir()
    native_pdb = tmp_path / "drd2.pdb"
    native_pdb.write_text(
        "ATOM      1  OD1 ASP A 114       0.000   0.000   0.000  1.00 20.00           O\n"
        "ATOM      2  OD2 ASP A 114       0.600   0.000   0.000  1.00 20.00           O\n"
        "END\n",
        encoding="utf-8",
    )
    import numpy as np

    npz_path = local_root / "CHEMBL217_DRD2_HUMAN__CHEMBL301265.npz"
    np.savez(
        npz_path,
        ligand_frames=np.asarray([[[0.3, 0.0, 3.0], [0.3, 0.0, 4.2]]], dtype=np.float32),
    )
    overlay_rows = [
        {
            "target": "CHEMBL217_DRD2_HUMAN",
            "ligand_id": "CHEMBL301265",
            "trajectory_npz": str(npz_path),
            "original_trajectory_npz": "/missing/mount.npz",
            "protein_structure_source_path": str(native_pdb),
        }
    ]
    reuse_rows = build_local_reuse_repair_rows(overlay_rows, default_drd2_native_pdb=str(native_pdb))
    assert reuse_rows[0]["allatom_backmapping_status"] == "ok"
    assert reuse_rows[0]["allatom_backmapping_reason"] == "local_pseudo_allatom_reused"


def test_restoration_path_reports_mount_stage2_absence(tmp_path: Path) -> None:
    mount_root = tmp_path / "mount"
    run_root = mount_root / "frozen_run"
    (run_root / "stage3_delivery").mkdir(parents=True)
    payload = build_packet(
        repair_rows=[],
        gap_packet={"summary": {"drd2_repair_blocked": True}},
        mount_root=str(mount_root),
        local_pseudo_root=str(tmp_path / "pseudo"),
        frozen_run_id="frozen_run",
        generated_at_local="2026-06-07T00:00:00+09:00",
    )
    assert payload["summary"]["mount_stage2_present_run_count"] == 0
    assert "mount_stage2_absent_for_all_gpcr_100k_runs" in payload["summary"]["blockers"]
