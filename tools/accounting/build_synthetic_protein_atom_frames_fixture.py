#!/usr/bin/env python3

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

import numpy as np


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _to_pdb_line(
    serial: int,
    atom_name: str,
    res_name: str,
    chain_id: str,
    res_seq: int,
    xyz: np.ndarray,
    element: str,
    *,
    hetatm: bool = False,
) -> str:
    rec = "HETATM" if hetatm else "ATOM  "
    x, y, z = [float(v) for v in np.asarray(xyz, dtype=np.float32).reshape(3)]
    return (
        f"{rec}{serial:5d} {atom_name:<4s} {res_name:>3s} {chain_id:1s}{res_seq:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{1.00:6.2f}{20.00:6.2f}          {element:>2s}"
    )


def _write_pdb(path: str, protein_atoms: List[Dict[str, Any]], ligand_atoms: List[Dict[str, Any]]) -> None:
    lines: List[str] = ["REMARK SYNTHETIC PROTEIN_ATOM_FRAMES FIXTURE"]
    serial = 1
    for atom in protein_atoms:
        lines.append(
            _to_pdb_line(
                serial,
                atom_name=str(atom["atom_name"]),
                res_name=str(atom["res_name"]),
                chain_id=str(atom["chain_id"]),
                res_seq=int(atom["res_seq"]),
                xyz=np.asarray(atom["xyz"], dtype=np.float32),
                element=str(atom["element"]),
                hetatm=False,
            )
        )
        serial += 1
    lines.append("TER")
    for atom in ligand_atoms:
        lines.append(
            _to_pdb_line(
                serial,
                atom_name=str(atom["atom_name"]),
                res_name="LIG",
                chain_id="L",
                res_seq=1,
                xyz=np.asarray(atom["xyz"], dtype=np.float32),
                element=str(atom["element"]),
                hetatm=True,
            )
        )
        serial += 1
    lines.append("END")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _web_path(abs_path: str, repo_root: str) -> str:
    rel = os.path.relpath(abs_path, repo_root).replace(os.sep, "/")
    return f"/{rel}"


def main() -> None:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    out_dir = os.path.join(repo_root, "runs", "synthetic_protein_atom_frames_fixture_current")
    _ensure_dir(out_dir)

    structure_pdb = os.path.join(out_dir, "synthetic_protein_atom_fixture_structure.pdb")
    trajectory_npz = os.path.join(out_dir, "synthetic_protein_atom_fixture_trajectory.npz")
    bundle_json = os.path.join(out_dir, "synthetic_protein_atom_fixture_bundle.json")

    protein_atoms = [
        {"atom_name": "N", "res_name": "GLY", "chain_id": "A", "res_seq": 1, "xyz": [0.000, 0.000, 0.000], "element": "N"},
        {"atom_name": "CA", "res_name": "GLY", "chain_id": "A", "res_seq": 1, "xyz": [1.450, 0.000, 0.000], "element": "C"},
        {"atom_name": "C", "res_name": "GLY", "chain_id": "A", "res_seq": 1, "xyz": [2.050, 1.240, 0.000], "element": "C"},
    ]
    ligand_atoms = [
        {"atom_name": "C1", "xyz": [3.500, 0.200, 0.000], "element": "C"},
        {"atom_name": "C2", "xyz": [4.200, 0.950, 0.000], "element": "C"},
    ]
    _write_pdb(structure_pdb, protein_atoms, ligand_atoms)

    protein_ca = np.asarray([[1.450, 0.000, 0.000]], dtype=np.float32)
    ligand_frames = np.asarray(
        [
            [[3.500, 0.200, 0.000], [4.200, 0.950, 0.000]],
            [[3.300, 0.150, 0.000], [4.000, 0.900, 0.000]],
            [[3.100, 0.100, 0.000], [3.800, 0.850, 0.000]],
        ],
        dtype=np.float32,
    )
    frame_indices = np.asarray([0, 1, 2], dtype=np.int32)

    protein_atom_frame_0 = np.asarray([atom["xyz"] for atom in protein_atoms], dtype=np.float32)
    protein_atom_frame_1 = protein_atom_frame_0 + np.asarray([[0.000, 0.000, 0.000], [0.040, 0.020, 0.000], [0.040, 0.020, 0.000]], dtype=np.float32)
    protein_atom_frame_2 = protein_atom_frame_0 + np.asarray([[0.000, 0.000, 0.000], [0.080, 0.040, 0.000], [0.080, 0.040, 0.000]], dtype=np.float32)
    protein_atom_frames = np.stack([protein_atom_frame_0, protein_atom_frame_1, protein_atom_frame_2], axis=0).astype(np.float32, copy=False)
    protein_atom_template_index = np.asarray([0, 1, 2], dtype=np.int32)
    protein_residue_centroids = np.asarray(
        [
            [[1.167, 0.413, 0.000]],
            [[1.193, 0.427, 0.000]],
            [[1.220, 0.440, 0.000]],
        ],
        dtype=np.float32,
    )
    protein_residue_bfactor_equivalent = np.asarray([14.0], dtype=np.float32)

    np.savez(
        trajectory_npz,
        protein_ca=protein_ca,
        ligand_frames=ligand_frames,
        frame_indices=frame_indices,
        protein_atom_frames=protein_atom_frames,
        protein_atom_template_index=protein_atom_template_index,
        protein_atom_schema_version=np.asarray(1, dtype=np.int32),
        protein_residue_centroids=protein_residue_centroids,
        protein_residue_bfactor_equivalent=protein_residue_bfactor_equivalent,
        protein_residue_schema_version=np.asarray(1, dtype=np.int32),
    )

    structure_web = _web_path(structure_pdb, repo_root)
    trajectory_web = _web_path(trajectory_npz, repo_root)
    bundle = {
        "summary": {
            "status": "selected_allatom_visual_bundle_ready",
            "target_id": "Synthetic Protein Atom Frames",
            "selected_surface_label": "synthetic.protein_atom_frames.fixture",
            "surface_label": "synthetic.protein_atom_frames.fixture",
            "topk_count": 1,
            "primary_trajectory_npz": trajectory_web,
            "primary_protein_reference_aligned_viewer_path": structure_web,
            "primary_protein_reference_structure_aligned_for_viewer": True,
            "primary_protein_reference_structure_format": "pdb",
            "primary_viewer_reference_pdb": structure_web,
            "primary_viewer_reference_pdb_ready": True,
        },
        "rows": [
            {
                "packet_rank": 1,
                "compound_name": "synthetic_fixture_rank1",
                "ligand_id": "synthetic_fixture_ligand",
                "target_id": "Synthetic Protein Atom Frames",
                "surface_label": "synthetic.protein_atom_frames.fixture",
                "backmapped_pdb": structure_web,
                "protein_reference_structure_path": structure_web,
                "protein_reference_structure_ready": True,
                "protein_reference_aligned_viewer_path": structure_web,
                "protein_reference_structure_aligned_for_viewer": True,
                "protein_reference_structure_format": "pdb",
                "protein_reference_viewer_mode": "aligned_reference",
                "protein_reference_alignment_mode": "synthetic_identity",
                "viewer_reference_pdb": structure_web,
                "viewer_reference_pdb_ready": True,
                "viewer_pose_pdb": structure_web,
                "viewer_pose_pdb_ready": True,
                "viewer_structure_context_mode": "protein_atom_frames_fixture",
                "viewer_protein_context_valid": True,
                "viewer_protein_context_quality_gate_pass": True,
                "viewer_protein_ca_count": 1,
                "viewer_protein_ca_spread_A": 0.0,
                "trajectory_npz": trajectory_web,
                "trajectory_frames": 3,
                "mean_min_distance_A": 1.85,
                "binding_energy_proxy": -0.11,
                "contact_fraction": 0.67,
                "stability_score": 0.81,
                "commercial_overall_score_v2": 72.0,
                "translation_gate_status": "fixture_ready",
                "shortlist_tier": "synthetic",
                "recommended_next_expensive_lane": "none",
            }
        ],
    }
    with open(bundle_json, "w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=2, ensure_ascii=False)

    print(json.dumps(
        {
            "structure_pdb": structure_pdb,
            "trajectory_npz": trajectory_npz,
            "bundle_json": bundle_json,
            "viewer_bundle_url": _web_path(bundle_json, repo_root),
        },
        indent=2,
        ensure_ascii=False,
    ))


if __name__ == "__main__":
    main()
