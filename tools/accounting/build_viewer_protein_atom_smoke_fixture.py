#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "runs" / "viewer_protein_atom_smoke"
PDB_NAME = "protein_atom_frames_smoke_reference_current.pdb"
NPZ_NAME = "protein_atom_frames_smoke_trajectory_current.npz"
BUNDLE_NAME = "protein_atom_frames_smoke_bundle_current.json"


def _pdb_line(
    serial: int,
    record: str,
    atom_name: str,
    residue_name: str,
    chain_id: str,
    residue_seq: int,
    x: float,
    y: float,
    z: float,
    element: str,
) -> str:
    return (
        f"{record:<6}{serial:>5} {atom_name:^4} {residue_name:>3} {chain_id:1}"
        f"{residue_seq:>4}    "
        f"{x:>8.3f}{y:>8.3f}{z:>8.3f}"
        f"{1.00:>6.2f}{15.00:>6.2f}          {element:>2}"
    )


def _write_reference_pdb(path: Path) -> dict[str, np.ndarray]:
    protein_atoms = [
        ("ATOM", "N", "ALA", "A", 10, -2.000, 0.100, 0.000, "N"),
        ("ATOM", "CA", "ALA", "A", 10, -1.000, 0.000, 0.000, "C"),
        ("ATOM", "C", "ALA", "A", 10, -0.100, 0.200, 0.200, "C"),
        ("ATOM", "O", "ALA", "A", 10, 0.700, 0.100, 0.500, "O"),
        ("ATOM", "N", "GLY", "A", 11, 1.800, 0.000, 0.100, "N"),
        ("ATOM", "CA", "GLY", "A", 11, 2.700, 0.100, 0.000, "C"),
        ("ATOM", "C", "GLY", "A", 11, 3.600, -0.100, 0.300, "C"),
        ("ATOM", "O", "GLY", "A", 11, 4.300, -0.300, 0.800, "O"),
    ]
    ligand_atoms = [
        ("HETATM", "C1", "LIG", "L", 1, 0.300, 1.700, 0.000, "C"),
        ("HETATM", "O1", "LIG", "L", 1, 0.900, 2.400, 0.200, "O"),
        ("HETATM", "N1", "LIG", "L", 1, -0.500, 2.200, -0.200, "N"),
    ]

    lines = ["REMARK Synthetic protein_atom_frames smoke fixture"]
    serial = 1
    for row in protein_atoms + ligand_atoms:
        lines.append(_pdb_line(serial, *row))
        serial += 1
    lines.extend(["TER", "END"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    protein_xyz = np.asarray([[row[5], row[6], row[7]] for row in protein_atoms], dtype=np.float32)
    ligand_xyz = np.asarray([[row[5], row[6], row[7]] for row in ligand_atoms], dtype=np.float32)
    residue_atom_index = np.asarray([0, 0, 0, 0, 1, 1, 1, 1], dtype=np.int32)
    return {
        "protein_xyz": protein_xyz,
        "ligand_xyz": ligand_xyz,
        "residue_atom_index": residue_atom_index,
    }


def _write_npz(path: Path, template: dict[str, np.ndarray]) -> None:
    frame_count = 4
    protein_template = template["protein_xyz"]
    ligand_template = template["ligand_xyz"]
    residue_atom_index = template["residue_atom_index"]

    residue_centroids = np.asarray(
        [
            [[-1.000, 0.000, 0.000], [2.700, 0.100, 0.000]],
            [[-0.850, 0.050, 0.000], [2.550, 0.050, 0.100]],
            [[-0.700, 0.120, -0.050], [2.420, 0.020, 0.120]],
            [[-0.520, 0.160, -0.080], [2.250, -0.030, 0.180]],
        ],
        dtype=np.float32,
    )
    protein_ca = residue_centroids.copy()
    first_centroids = residue_centroids[0]
    residue_shifts = residue_centroids - first_centroids[None, :, :]
    protein_atom_frames = protein_template[None, :, :] + residue_shifts[:, residue_atom_index, :]

    ligand_frames = np.asarray(
        [
            [[0.300, 1.700, 0.000], [0.900, 2.400, 0.200], [-0.500, 2.200, -0.200]],
            [[0.500, 1.500, 0.020], [1.100, 2.200, 0.240], [-0.280, 2.000, -0.180]],
            [[0.700, 1.250, 0.060], [1.320, 2.000, 0.300], [-0.050, 1.800, -0.120]],
            [[0.900, 1.050, 0.100], [1.550, 1.820, 0.340], [0.160, 1.620, -0.080]],
        ],
        dtype=np.float32,
    )

    np.savez(
        path,
        protein_ca=protein_ca,
        ligand_frames=ligand_frames,
        frame_indices=np.arange(frame_count, dtype=np.int32),
        protein_residue_centroids=residue_centroids,
        protein_residue_bfactor=np.asarray([14.0, 22.0], dtype=np.float32),
        protein_residue_schema_version=np.asarray(1, dtype=np.int32),
        protein_atom_frames=protein_atom_frames,
        protein_atom_template_index=np.arange(protein_template.shape[0], dtype=np.int32),
        protein_atom_schema_version=np.asarray(1, dtype=np.int32),
        radius_of_gyration=np.asarray([1.45, 1.42, 1.39, 1.36], dtype=np.float32),
        hbond_count=np.asarray([1.0, 2.0, 2.0, 3.0], dtype=np.float32),
        energy_std=np.asarray([0.12], dtype=np.float32),
    )


def _write_bundle(path: Path) -> None:
    rel_pdb = f"/runs/viewer_protein_atom_smoke/{PDB_NAME}"
    rel_npz = f"/runs/viewer_protein_atom_smoke/{NPZ_NAME}"
    payload = {
        "summary": {
            "status": "selected_allatom_visual_bundle_ready",
            "visual_bundle_manifest_version": "protein_atom_frames_smoke_v1",
            "target_id": "Protein Motion Smoke",
            "selected_surface_label": "protein_atom_frames_smoke",
            "surface_label": "protein_atom_frames_smoke",
            "topk_count": 1,
            "human_summary": "Synthetic smoke bundle for protein_atom_frames full-protein frame mutation diagnostics.",
            "primary_trajectory_npz": rel_npz,
            "primary_viewer_reference_pdb": rel_pdb,
            "primary_viewer_reference_pdb_ready": True,
            "primary_viewer_pose_pdb": rel_pdb,
            "primary_viewer_pose_pdb_ready": True,
            "primary_protein_reference_aligned_viewer_path": rel_pdb,
            "primary_protein_reference_structure_aligned_for_viewer": True,
            "primary_protein_reference_viewer_mode": "aligned_native_reference",
            "primary_protein_reference_alignment_mode": "synthetic_fixture_identity",
            "primary_viewer_structure_context_mode": "protein_atom_frames_smoke",
            "primary_viewer_protein_context_valid": True,
            "primary_viewer_protein_context_quality_gate_pass": True,
            "primary_viewer_protein_ca_count": 2,
            "primary_viewer_protein_ca_spread_A": 3.7,
            "primary_pocket_volume_A3": 182.0,
            "primary_pocket_volume_source": "synthetic_fixture_explicit",
        },
        "rows": [
            {
                "packet_rank": 1,
                "target_id": "Protein Motion Smoke",
                "surface_label": "protein_atom_frames_smoke",
                "ligand_id": "SMOKE_LIG",
                "compound_name": "Protein Atom Frames Smoke",
                "backmapped_pdb": rel_pdb,
                "render_structure_path": rel_pdb,
                "viewer_reference_pdb": rel_pdb,
                "viewer_reference_pdb_ready": True,
                "viewer_pose_pdb": rel_pdb,
                "viewer_pose_pdb_ready": True,
                "protein_reference_structure_path": rel_pdb,
                "protein_reference_structure_ready": True,
                "protein_reference_aligned_viewer_path": rel_pdb,
                "protein_reference_structure_aligned_for_viewer": True,
                "protein_reference_viewer_mode": "aligned_native_reference",
                "protein_reference_alignment_mode": "synthetic_fixture_identity",
                "protein_reference_structure_format": "pdb",
                "viewer_structure_context_mode": "protein_atom_frames_smoke",
                "viewer_protein_context_valid": True,
                "viewer_protein_context_quality_gate_pass": True,
                "viewer_protein_ca_count": 2,
                "viewer_protein_ca_spread_A": 3.7,
                "trajectory_npz": rel_npz,
                "mean_min_distance_A": 2.9,
                "binding_energy_proxy": -0.11,
                "contact_fraction": 0.67,
                "stability_score": 0.58,
                "trajectory_frames": 4,
                "commercial_overall_score_v2": 61.4,
                "commercial_confidence_score_v2": 74.2,
                "translation_gate_status": "smoke_ready",
                "translation_gate_reason": "Synthetic fixture for full-protein frame mutation path.",
                "shortlist_tier": "smoke",
                "recommended_next_expensive_lane": "viewer_smoke_only",
                "pocket_volume_A3": 182.0,
                "pocket_volume_source": "synthetic_fixture_explicit",
            }
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pdb_path = OUT_DIR / PDB_NAME
    npz_path = OUT_DIR / NPZ_NAME
    bundle_path = OUT_DIR / BUNDLE_NAME

    template = _write_reference_pdb(pdb_path)
    _write_npz(npz_path, template)
    _write_bundle(bundle_path)

    summary = {
        "fixture_dir": str(OUT_DIR),
        "pdb_path": str(pdb_path),
        "npz_path": str(npz_path),
        "bundle_path": str(bundle_path),
        "next_required_step": "Open the viewer and select the Protein Motion Smoke surface preset to exercise protein_atom_frames frame mutation.",
    }
    (OUT_DIR / "protein_atom_frames_smoke_summary_current.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
