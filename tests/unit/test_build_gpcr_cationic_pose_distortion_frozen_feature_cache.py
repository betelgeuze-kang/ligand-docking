from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def _pdb_line(record: str, serial: int, name: str, resn: str, chain: str, resi: int, xyz: tuple[float, float, float]) -> str:
    element = name.strip()[0]
    return (
        f"{record:<6}{serial:5d} {name:>4s} {resn:>3s} {chain:1s}{resi:4d}    "
        f"{xyz[0]:8.3f}{xyz[1]:8.3f}{xyz[2]:8.3f}  1.00 20.00           {element:>2s}\n"
    )


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_build_gpcr_cationic_pose_distortion_frozen_feature_cache_claim_locked(tmp_path: Path) -> None:
    pdb = tmp_path / "native.pdb"
    pdb.write_text(
        "".join(
            [
                _pdb_line("ATOM", 1, "OD1", "ASP", "A", 114, (0.0, 0.0, 0.0)),
                _pdb_line("ATOM", 2, "OD2", "ASP", "A", 114, (0.0, 1.0, 0.0)),
                _pdb_line("HETATM", 3, "C1", "LIG", "A", 1, (3.0, 0.0, 0.0)),
                _pdb_line("HETATM", 4, "C2", "LIG", "A", 1, (3.1, 0.2, 0.0)),
                _pdb_line("HETATM", 5, "C3", "LIG", "A", 1, (3.2, 0.3, 0.0)),
                _pdb_line("HETATM", 6, "C4", "LIG", "A", 1, (3.3, 0.4, 0.0)),
                _pdb_line("HETATM", 7, "C5", "LIG", "A", 1, (3.4, 0.5, 0.0)),
            ]
        ),
        encoding="utf-8",
    )
    traj = tmp_path / "traj.npz"
    ligand_frames = np.asarray(
        [
            [[3.0, 0.1, 0.0], [4.0, 0.1, 0.0]],
            [[3.1, 0.2, 0.0], [4.1, 0.2, 0.0]],
        ],
        dtype=np.float32,
    )
    protein_atom_frames = np.asarray(
        [
            [[0.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            [[0.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        ],
        dtype=np.float32,
    )
    np.savez_compressed(traj, ligand_frames=ligand_frames, protein_atom_frames=protein_atom_frames)
    input_csv = tmp_path / "stage3.csv"
    out_csv = tmp_path / "cache.csv"
    out_json = tmp_path / "cache.json"
    out_md = tmp_path / "cache.md"
    _write_csv(
        input_csv,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "ligand_smiles": "CCN",
                "trajectory_npz": str(traj),
                "protein_structure_source_path": str(pdb),
                "binding_score_composite_v7": -0.75,
                "binding_score_composite_v7_residual_active": -1.5,
                "ligand_h_donors": 1,
                "ligand_h_acceptors": 1,
                "ligand_rot_bonds": 1,
                "ligand_logp": 1.2,
            }
        ],
    )

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_cationic_pose_distortion_frozen_feature_cache.py"),
            "--input-csv",
            str(input_csv),
            "--row-limit",
            "1",
            "--out-csv",
            str(out_csv),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    summary = payload["summary"]
    rows = list(csv.DictReader(out_csv.open("r", encoding="utf-8", newline="")))

    assert summary["status"] == "feature_cache_ready_for_shadow_replay_claim_locked"
    assert summary["feature_row_count"] == 1
    assert summary["claim_promotion_allowed"] is False
    assert payload["claim_boundary"]["selected_slice_green_is_not_claim_evidence"] is True
    assert rows[0]["feature_cache_status"] == "ok"
    assert rows[0]["effective_label_free_anchor_mode"] == "none"
    assert float(rows[0]["base_score"]) == -0.75
    assert float(rows[0]["label_free_support_pressure"]) >= 0.0
    assert float(rows[0]["weak_base_rescue_gate"]) > 0.0
    assert float(rows[0]["weak_base_rescue_support_pressure"]) >= 0.0
    assert float(rows[0]["v12_synthetic_anchor_saturation_pressure"]) >= 0.0
    assert float(rows[0]["v12_moderate_multi_basic_weakbase_support_pressure"]) >= 0.0
    assert float(rows[0]["v12_plausible_anchor_window_support"]) >= 0.0
    assert float(rows[0]["v14_cationic_anchor_occupancy_support"]) >= 0.0
    assert float(rows[0]["v14_cationic_anchor_window_gate"]) >= 0.0
    assert float(rows[0]["v14_cationic_overclose_artifact_pressure"]) >= 0.0
    assert "claim_promotion_allowed: `false`" in out_md.read_text(encoding="utf-8")


def test_build_gpcr_cationic_pose_distortion_frozen_feature_cache_adaptive_rejects_pose_collapse(
    tmp_path: Path,
) -> None:
    pdb = tmp_path / "native.pdb"
    pdb.write_text(
        "".join(
            [
                _pdb_line("ATOM", 1, "OD1", "ASP", "A", 114, (0.0, 0.0, 0.0)),
                _pdb_line("ATOM", 2, "OD2", "ASP", "A", 114, (0.0, 1.0, 0.0)),
                _pdb_line("HETATM", 3, "C1", "LIG", "A", 1, (35.0, 0.0, 0.0)),
                _pdb_line("HETATM", 4, "C2", "LIG", "A", 1, (36.0, 0.0, 0.0)),
                _pdb_line("HETATM", 5, "C3", "LIG", "A", 1, (37.0, 0.0, 0.0)),
                _pdb_line("HETATM", 6, "C4", "LIG", "A", 1, (38.0, 0.0, 0.0)),
                _pdb_line("HETATM", 7, "C5", "LIG", "A", 1, (39.0, 0.0, 0.0)),
            ]
        ),
        encoding="utf-8",
    )
    traj = tmp_path / "traj.npz"
    ligand_frames = np.asarray(
        [
            [[35.0, 0.0, 0.0], [36.0, 0.0, 0.0]],
            [[35.2, 0.0, 0.0], [36.2, 0.0, 0.0]],
        ],
        dtype=np.float32,
    )
    protein_atom_frames = np.asarray(
        [
            [[0.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            [[0.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        ],
        dtype=np.float32,
    )
    np.savez_compressed(traj, ligand_frames=ligand_frames, protein_atom_frames=protein_atom_frames)
    input_csv = tmp_path / "stage3.csv"
    out_csv = tmp_path / "cache.csv"
    out_json = tmp_path / "cache.json"
    out_md = tmp_path / "cache.md"
    _write_csv(
        input_csv,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL331883",
                "ligand_smiles": "CCN",
                "trajectory_npz": str(traj),
                "protein_structure_source_path": str(pdb),
                "binding_score_composite_v7": -4.5,
                "ligand_h_donors": 1,
                "ligand_h_acceptors": 1,
                "ligand_rot_bonds": 1,
                "ligand_logp": 1.2,
            }
        ],
    )

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_cationic_pose_distortion_frozen_feature_cache.py"),
            "--input-csv",
            str(input_csv),
            "--anchor-mode",
            "adaptive_pose_preserving",
            "--out-csv",
            str(out_csv),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )
    rows = list(csv.DictReader(out_csv.open("r", encoding="utf-8", newline="")))

    assert rows[0]["feature_cache_status"] == "ok"
    assert rows[0]["requested_label_free_anchor_mode"] == "adaptive_pose_preserving"
    assert rows[0]["effective_label_free_anchor_mode"] == "none"
    assert rows[0]["label_free_anchor_mode"] == "none"
    assert rows[0]["adaptive_selection_reason"] == "all_basic_pose_collapse_rejected"
    assert float(rows[0]["adaptive_all_basic_pose_rmsd_A"]) > float(rows[0]["adaptive_none_pose_rmsd_A"]) + 6.0


def test_build_gpcr_cationic_pose_distortion_frozen_feature_cache_uses_static_anchor_for_prod_light_npz(
    tmp_path: Path,
) -> None:
    pdb = tmp_path / "native.pdb"
    pdb.write_text(
        "".join(
            [
                _pdb_line("ATOM", 1, "OD1", "ASP", "A", 114, (0.0, 0.0, 0.0)),
                _pdb_line("ATOM", 2, "OD2", "ASP", "A", 114, (0.0, 1.0, 0.0)),
                _pdb_line("HETATM", 3, "C1", "LIG", "A", 1, (3.0, 0.0, 0.0)),
                _pdb_line("HETATM", 4, "C2", "LIG", "A", 1, (3.1, 0.2, 0.0)),
                _pdb_line("HETATM", 5, "C3", "LIG", "A", 1, (3.2, 0.3, 0.0)),
                _pdb_line("HETATM", 6, "C4", "LIG", "A", 1, (3.3, 0.4, 0.0)),
                _pdb_line("HETATM", 7, "C5", "LIG", "A", 1, (3.4, 0.5, 0.0)),
            ]
        ),
        encoding="utf-8",
    )
    traj = tmp_path / "prod_light_traj.npz"
    np.savez_compressed(
        traj,
        ligand_frames=np.asarray(
            [
                [[3.0, 0.1, 0.0], [4.0, 0.1, 0.0]],
                [[3.1, 0.2, 0.0], [4.1, 0.2, 0.0]],
            ],
            dtype=np.float32,
        ),
    )
    input_csv = tmp_path / "stage3.csv"
    out_csv = tmp_path / "cache.csv"
    out_json = tmp_path / "cache.json"
    out_md = tmp_path / "cache.md"
    _write_csv(
        input_csv,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "ligand_smiles": "CCN",
                "trajectory_npz": str(traj),
                "protein_structure_source_path": str(pdb),
                "binding_score_composite_v7": -0.75,
                "ligand_h_donors": 1,
                "ligand_h_acceptors": 1,
                "ligand_rot_bonds": 1,
                "ligand_logp": 1.2,
            }
        ],
    )

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_cationic_pose_distortion_frozen_feature_cache.py"),
            "--input-csv",
            str(input_csv),
            "--anchor-mode",
            "all_basic",
            "--out-csv",
            str(out_csv),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )
    rows = list(csv.DictReader(out_csv.open("r", encoding="utf-8", newline="")))

    assert rows[0]["feature_cache_status"] == "ok"
    assert rows[0]["effective_label_free_anchor_mode"] == "all_basic"
    assert int(rows[0]["atom_anchor_available"]) == 1
    assert int(rows[0]["cationic_center_available"]) == 1


def test_build_gpcr_cationic_pose_distortion_frozen_feature_cache_blocks_missing_native(tmp_path: Path) -> None:
    input_csv = tmp_path / "stage3.csv"
    out_csv = tmp_path / "cache.csv"
    out_json = tmp_path / "cache.json"
    out_md = tmp_path / "cache.md"
    _write_csv(
        input_csv,
        [
            {
                "target": "UNKNOWN_GPCR",
                "ligand_id": "L1",
                "ligand_smiles": "CCN",
                "trajectory_npz": "",
                "protein_structure_source_path": "",
                "binding_score_composite_v7": 1.0,
            }
        ],
    )

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_cationic_pose_distortion_frozen_feature_cache.py"),
            "--input-csv",
            str(input_csv),
            "--out-csv",
            str(out_csv),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))

    assert payload["summary"]["status"] == "blocked_no_feature_rows"
    assert payload["summary"]["failure_reason_counts"] == {"native_pdb_missing": 1}


def test_build_gpcr_cationic_pose_distortion_frozen_feature_cache_resumes_existing_rows(tmp_path: Path) -> None:
    pdb = tmp_path / "native.pdb"
    pdb.write_text(
        "".join(
            [
                _pdb_line("ATOM", 1, "OD1", "ASP", "A", 114, (0.0, 0.0, 0.0)),
                _pdb_line("ATOM", 2, "OD2", "ASP", "A", 114, (0.0, 1.0, 0.0)),
                _pdb_line("HETATM", 3, "C1", "LIG", "A", 1, (3.0, 0.0, 0.0)),
                _pdb_line("HETATM", 4, "C2", "LIG", "A", 1, (3.1, 0.2, 0.0)),
                _pdb_line("HETATM", 5, "C3", "LIG", "A", 1, (3.2, 0.3, 0.0)),
                _pdb_line("HETATM", 6, "C4", "LIG", "A", 1, (3.3, 0.4, 0.0)),
                _pdb_line("HETATM", 7, "C5", "LIG", "A", 1, (3.4, 0.5, 0.0)),
            ]
        ),
        encoding="utf-8",
    )
    traj = tmp_path / "traj.npz"
    ligand_frames = np.asarray([[[3.0, 0.1, 0.0], [4.0, 0.1, 0.0]]], dtype=np.float32)
    protein_atom_frames = np.asarray([[[0.0, 0.0, 0.0], [0.0, 1.0, 0.0]]], dtype=np.float32)
    np.savez_compressed(traj, ligand_frames=ligand_frames, protein_atom_frames=protein_atom_frames)
    input_csv = tmp_path / "stage3.csv"
    out_csv = tmp_path / "cache.csv"
    out_json = tmp_path / "cache.json"
    out_md = tmp_path / "cache.md"
    rows = [
        {
            "target": "CHEMBL217_DRD2_HUMAN",
            "ligand_id": ligand_id,
            "ligand_smiles": "CCN",
            "trajectory_npz": str(traj),
            "protein_structure_source_path": str(pdb),
            "binding_score_composite_v7": -0.5,
            "binding_score_composite_v7_residual_active": -1.0,
            "ligand_h_donors": 1,
            "ligand_h_acceptors": 1,
            "ligand_rot_bonds": 1,
            "ligand_logp": 1.2,
        }
        for ligand_id in ["L1", "L2"]
    ]
    _write_csv(input_csv, rows)

    common_cmd = [
        sys.executable,
        str(ROOT / "tools/build_gpcr_cationic_pose_distortion_frozen_feature_cache.py"),
        "--input-csv",
        str(input_csv),
        "--row-limit",
        "1",
        "--resume-existing",
        "--out-csv",
        str(out_csv),
        "--out-json",
        str(out_json),
        "--out-md",
        str(out_md),
    ]
    subprocess.run(common_cmd, check=True, cwd=ROOT)
    subprocess.run([*common_cmd, "--row-offset", "1"], check=True, cwd=ROOT)
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    cached = list(csv.DictReader(out_csv.open("r", encoding="utf-8", newline="")))

    assert payload["summary"]["existing_row_count"] == 1
    assert payload["summary"]["total_output_row_count"] == 2
    assert {row["ligand_id"] for row in cached} == {"L1", "L2"}
