"""Geometric binding-pocket detection (independent engine)."""

from __future__ import annotations

from typing import Any

import numpy as np

POCKET_CLAIM_BOUNDARY = (
    "Geometry-based pocket detection from supplied coordinates only. "
    "Not a druggability or cryptic-site prediction claim."
)


def _grid_centers(bounds_min: np.ndarray, bounds_max: np.ndarray, spacing: float) -> np.ndarray:
    span = np.maximum(bounds_max - bounds_min, spacing)
    nx = max(int(np.ceil(span[0] / spacing)) + 1, 2)
    ny = max(int(np.ceil(span[1] / spacing)) + 1, 2)
    nz = max(int(np.ceil(span[2] / spacing)) + 1, 2)
    xs = np.linspace(bounds_min[0], bounds_max[0], nx)
    ys = np.linspace(bounds_min[1], bounds_max[1], ny)
    zs = np.linspace(bounds_min[2], bounds_max[2], nz)
    grid = np.stack(np.meshgrid(xs, ys, zs, indexing="ij"), axis=-1).reshape(-1, 3)
    return grid.astype(np.float64)


def detect_pocket_from_ligand(
    protein_xyz: np.ndarray,
    ligand_xyz: np.ndarray,
    *,
    shell_inner_a: float = 4.0,
    shell_outer_a: float = 8.0,
) -> dict[str, Any]:
    """Ligand-guided pocket: center on ligand, shell = protein atoms near ligand."""
    prot = np.asarray(protein_xyz, dtype=np.float64)
    lig = np.asarray(ligand_xyz, dtype=np.float64)
    if prot.size == 0:
        return {"status": "blocked_empty_protein", "pocket_center": [0.0, 0.0, 0.0], "pocket_radius_a": 0.0}
    if lig.size == 0:
        return detect_pocket_geometric(prot)

    center = lig.mean(axis=0)
    dist = np.linalg.norm(prot - center.reshape(1, 3), axis=1)
    shell = (dist >= float(shell_inner_a)) & (dist <= float(shell_outer_a))
    contact = dist <= float(shell_inner_a)
    radius = float(max(np.max(np.linalg.norm(lig - center, axis=1)) + 2.0, shell_inner_a))
    return {
        "status": "pocket_ready",
        "method": "ligand_guided",
        "pocket_center": center.tolist(),
        "pocket_radius_a": radius,
        "shell_atom_count": int(np.sum(shell)),
        "contact_atom_count": int(np.sum(contact)),
        "contact_atom_indices": np.where(contact)[0].astype(int).tolist(),
        "claim_boundary": POCKET_CLAIM_BOUNDARY,
    }


def detect_pocket_geometric(
    protein_xyz: np.ndarray,
    *,
    grid_spacing_a: float = 2.5,
    min_shell_atoms: int = 8,
) -> dict[str, Any]:
    """Grid cavity search: prefer points with nearby protein shell but low core density."""
    prot = np.asarray(protein_xyz, dtype=np.float64)
    if prot.size == 0:
        return {"status": "blocked_empty_protein", "pocket_center": [0.0, 0.0, 0.0], "pocket_radius_a": 0.0}

    pad = 4.0
    bounds_min = prot.min(axis=0) - pad
    bounds_max = prot.max(axis=0) + pad
    grid = _grid_centers(bounds_min, bounds_max, float(grid_spacing_a))

    dist = np.linalg.norm(grid[:, None, :] - prot[None, :, :], axis=-1)
    core = np.sum(dist < 3.5, axis=1)
    shell = np.sum((dist >= 3.5) & (dist <= 7.0), axis=1)
    score = shell.astype(np.float64) - 2.0 * core.astype(np.float64)
    score[core > 2] = -np.inf
    if not np.any(np.isfinite(score)):
        center = prot.mean(axis=0)
        radius = float(np.max(np.linalg.norm(prot - center, axis=1)) * 0.35 + 4.0)
        return {
            "status": "pocket_ready",
            "method": "protein_centroid_fallback",
            "pocket_center": center.tolist(),
            "pocket_radius_a": radius,
            "shell_atom_count": int(prot.shape[0]),
            "contact_atom_count": 0,
            "contact_atom_indices": [],
            "claim_boundary": POCKET_CLAIM_BOUNDARY,
        }

    best_idx = int(np.argmax(score))
    center = grid[best_idx]
    shell_mask = (np.linalg.norm(prot - center, axis=1) >= 3.5) & (np.linalg.norm(prot - center, axis=1) <= 7.0)
    contact_mask = np.linalg.norm(prot - center, axis=1) <= 4.0
    radius = 5.0 + 0.15 * float(np.sum(shell_mask))
    if int(np.sum(shell_mask)) < int(min_shell_atoms):
        center = prot.mean(axis=0)
        radius = float(np.max(np.linalg.norm(prot - center, axis=1)) * 0.35 + 4.0)
        method = "protein_centroid_fallback"
    else:
        method = "grid_cavity"
    return {
        "status": "pocket_ready",
        "method": method,
        "pocket_center": center.tolist(),
        "pocket_radius_a": float(radius),
        "shell_atom_count": int(np.sum(shell_mask)),
        "contact_atom_count": int(np.sum(contact_mask)),
        "contact_atom_indices": np.where(contact_mask)[0].astype(int).tolist(),
        "cavity_score": float(score[best_idx]) if method == "grid_cavity" else 0.0,
        "claim_boundary": POCKET_CLAIM_BOUNDARY,
    }


def detect_binding_pocket(
    protein_xyz: np.ndarray,
    ligand_xyz: np.ndarray | None = None,
    *,
    grid_spacing_a: float = 2.5,
) -> dict[str, Any]:
    """Unified pocket API: ligand-guided when ligand present, else geometric."""
    lig = np.asarray(ligand_xyz, dtype=np.float64) if ligand_xyz is not None else np.zeros((0, 3))
    if lig.size > 0:
        return detect_pocket_from_ligand(protein_xyz, lig)
    return detect_pocket_geometric(protein_xyz, grid_spacing_a=float(grid_spacing_a))
