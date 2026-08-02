"""Inline proxy scoring for stage2-skipped HTVS rows."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from betelgeuze_engine.physics.mm_gbsa import gb_sa_proxy_energy
from tools.run_ligand_backmapping_scoring import _frame_mmpbsa_proxy, _ligand_props, _load_native_target_coords


def _compose_ligand_xyz_from_row(row: dict[str, Any]) -> np.ndarray:
    b0 = [
        float(row.get("ligand_bead0_x", row.get("bead0_x", -0.8)) or -0.8),
        float(row.get("ligand_bead0_y", row.get("bead0_y", 0.0)) or 0.0),
        float(row.get("ligand_bead0_z", row.get("bead0_z", 0.0)) or 0.0),
    ]
    b1 = [
        float(row.get("ligand_bead1_x", row.get("bead1_x", 0.8)) or 0.8),
        float(row.get("ligand_bead1_y", row.get("bead1_y", 0.0)) or 0.0),
        float(row.get("ligand_bead1_z", row.get("bead1_z", 0.0)) or 0.0),
    ]
    return np.asarray([b0, b1], dtype=np.float32)


def score_skipped_row_inline(row: dict[str, Any], *, contact_cutoff_A: float = 6.0) -> dict[str, Any]:
    target = str(row.get("target", "unknown"))
    native_info = _load_native_target_coords(target, native_path=str(row.get("native_pdb_path", "")))
    protein = np.asarray(native_info.get("coords"), dtype=np.float32)
    ligand = _compose_ligand_xyz_from_row(row)
    props = _ligand_props(row)
    smiles = str(row.get("ligand_smiles", row.get("smiles", "")) or "")
    ff = _frame_mmpbsa_proxy(
        protein_xyz=protein,
        ligand_xyz=ligand,
        props=props,
        contact_cutoff_A=float(contact_cutoff_A),
        ligand_model="2bead",
        smiles=smiles,
    )
    return {
        "queue_id": str(row.get("queue_id", "")),
        "target": target,
        "ligand_id": str(row.get("ligand_id", "")),
        "inline_aux_available": True,
        "stage2_route_decision": str(row.get("stage2_route_decision", "skip_stage2_inline_score")),
        "stage2_skip_applied": True,
        "trajectory_frame_count": 0,
        "trajectory_frames": 0,
        "binding_energy_proxy": float(gb_sa_proxy_energy(ff, 0.0)),
        "binding_energy_mmpbsa_kcal_mol_proxy": float(gb_sa_proxy_energy(ff, 0.0)),
        "binding_energy_mmpbsa_std": 0.0,
        "stability_score": float(ff["contact_fraction"] / (1.0 + ff["min_distance_A"])),
        "contact_fraction": float(ff["contact_fraction"]),
        "mean_min_distance_A": float(ff["min_distance_A"]),
        "mean_e_vdw": float(ff["e_vdw"]),
        "mean_e_polar": float(ff["e_polar"]),
        "mean_e_nonpolar": float(ff["e_nonpolar"]),
        "mean_e_solvation": float(ff["e_solvation"]),
        "affinity_hint": float(props.get("affinity_hint", 0.0)),
        "onsps_norm": float(props.get("onsps_norm", 0.0)),
        "ligand_onsps_norm": float(props.get("onsps_norm", 0.0)),
    }


def build_skip_inline_manifest(
    skipped_rows: list[dict[str, Any]],
    *,
    out_csv: str,
    contact_cutoff_A: float = 6.0,
) -> dict[str, Any]:
    manifest_rows = [score_skipped_row_inline(row, contact_cutoff_A=contact_cutoff_A) for row in skipped_rows]
    df = pd.DataFrame(manifest_rows)
    out_path = str(out_csv)
    import os

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    df.to_csv(out_path, index=False)
    return {
        "skip_manifest_csv": out_path,
        "skip_row_count": int(len(manifest_rows)),
        "inline_aux_available": True,
    }
