"""Endpoint geometry measurements, independent of any stability predictor.

These values describe the supplied coordinate observations. They are not
experimental affinity, residence-time, MD convergence or a physical validity test.
Atom ordering must be identical before/after; periodic wrapping is not inferred.
"""
from __future__ import annotations

from typing import Any

import numpy as np


def _coords(value: np.ndarray, name: str) -> np.ndarray:
    if np.ma.isMaskedArray(value):
        raise ValueError(f"{name}: masked coordinates are unsupported")
    try:
        coords = np.asarray(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name}: invalid coordinates") from exc
    if coords.ndim != 2 or coords.shape[1] != 3 or len(coords) == 0:
        raise ValueError(f"{name}: nonempty [N, 3] coordinates required")
    if coords.dtype.kind not in "iuf":
        raise ValueError(f"{name}: real numeric coordinates required")
    with np.errstate(over="ignore", invalid="ignore"):
        coords = coords.astype(np.float64, copy=False)
    if not np.isfinite(coords).all():
        raise ValueError(f"{name}: nonfinite coordinates")
    return coords


def measure_pose_retention(
    protein_initial: np.ndarray,
    ligand_initial: np.ndarray,
    protein_final: np.ndarray,
    ligand_final: np.ndarray,
    *,
    contact_cutoff_a: float = 8.0,
) -> dict[str, Any]:
    """Measure ligand motion independently of receptor atom count.

    Fit a proper rigid transform to the receptor, then apply that *same* transform
    to the ligand. Never fit the ligand separately: that would erase escape.
    Degenerate receptor geometry and absent initial contacts yield null values.
    Pair contacts are counted in receptor blocks to bound temporary storage.
    """
    p0 = _coords(protein_initial, "protein_initial")
    l0 = _coords(ligand_initial, "ligand_initial")
    p1 = _coords(protein_final, "protein_final")
    l1 = _coords(ligand_final, "ligand_final")
    if p0.shape != p1.shape or l0.shape != l1.shape:
        raise ValueError("before/after coordinate shapes must match exactly")
    if isinstance(contact_cutoff_a, bool) or not np.isfinite(contact_cutoff_a) or contact_cutoff_a <= 0:
        raise ValueError("contact_cutoff_a must be finite and positive")

    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            ligand_direct = float(np.sqrt(np.mean(np.sum((l1 - l0) ** 2, axis=1))))
            center0, center1 = p0.mean(axis=0), p1.mean(axis=0)
            x0, x1 = p0 - center0, p1 - center1
            aligned_rmsd = centroid_shift = protein_rmsd = None
            alignment_status = "unavailable_degenerate_receptor"
            if len(p0) >= 3 and np.linalg.matrix_rank(x0) >= 2 and np.linalg.matrix_rank(x1) >= 2:
                u, _, vt = np.linalg.svd(x1.T @ x0)
                rotation = u @ vt
                if np.linalg.det(rotation) < 0.:
                    u[:, -1] *= -1.
                    rotation = u @ vt
                ligand_aligned = (l1 - center1) @ rotation + center0
                protein_aligned = x1 @ rotation + center0
                aligned_rmsd = float(np.sqrt(np.mean(np.sum((ligand_aligned - l0) ** 2, axis=1))))
                centroid_shift = float(np.linalg.norm(ligand_aligned.mean(axis=0) - l0.mean(axis=0)))
                protein_rmsd = float(np.sqrt(np.mean(np.sum((protein_aligned - p0) ** 2, axis=1))))
                alignment_status = "receptor_kabsch_proper_rotation"

            initial_contacts = final_contacts = retained_contacts = 0
            for start in range(0, len(p0), 128):
                d0 = np.linalg.norm(p0[start:start + 128, None, :] - l0[None, :, :], axis=2)
                d1 = np.linalg.norm(p1[start:start + 128, None, :] - l1[None, :, :], axis=2)
                a, b = d0 <= contact_cutoff_a, d1 <= contact_cutoff_a
                initial_contacts += int(a.sum())
                final_contacts += int(b.sum())
                retained_contacts += int((a & b).sum())
    except (FloatingPointError, np.linalg.LinAlgError) as exc:
        raise ValueError("nonfinite_or_degenerate_geometry_computation") from exc

    return {
        "measurement_scope": "endpoint_geometry_only",
        "coordinate_frame": "same_atom_order_no_periodic_unwrapping",
        "alignment_status": alignment_status,
        "protein_atom_count": int(len(p0)),
        "ligand_atom_count": int(len(l0)),
        "ligand_rmsd_direct_a": ligand_direct,
        "ligand_rmsd_receptor_frame_a": aligned_rmsd,
        "ligand_centroid_displacement_a": centroid_shift,
        "protein_alignment_rmsd_a": protein_rmsd,
        "contact_cutoff_a": float(contact_cutoff_a),
        "initial_contact_count": initial_contacts,
        "final_contact_count": final_contacts,
        "retained_contact_count": retained_contacts,
        "contact_retention_fraction": retained_contacts / initial_contacts if initial_contacts else None,
        "scientific_claim_validated": False,
    }
