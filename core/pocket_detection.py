"""Geometric binding-pocket detection (independent engine)."""

from __future__ import annotations

from typing import Any

import numpy as np

POCKET_CLAIM_BOUNDARY = (
    "Geometry-based pocket detection from supplied coordinates only. "
    "Not a druggability or cryptic-site prediction claim."
)


def _grid_centers(
    bounds_min: np.ndarray,
    bounds_max: np.ndarray,
    spacing: float,
    *,
    max_grid_points: int = 20_000,
) -> tuple[np.ndarray, float]:
    span = np.maximum(bounds_max - bounds_min, spacing)
    effective_spacing = max(float(spacing), 0.1)

    def grid_shape(value: float) -> tuple[int, int, int]:
        return tuple(max(int(np.ceil(axis / value)) + 1, 2) for axis in span)  # type: ignore[return-value]

    nx, ny, nz = grid_shape(effective_spacing)
    limit = max(int(max_grid_points), 8)
    while nx * ny * nz > limit:
        scale = max((nx * ny * nz / limit) ** (1.0 / 3.0), 1.01)
        effective_spacing *= scale * 1.01
        nx, ny, nz = grid_shape(effective_spacing)
    xs = np.linspace(bounds_min[0], bounds_max[0], nx)
    ys = np.linspace(bounds_min[1], bounds_max[1], ny)
    zs = np.linspace(bounds_min[2], bounds_max[2], nz)
    grid = np.stack(np.meshgrid(xs, ys, zs, indexing="ij"), axis=-1).reshape(-1, 3)
    return grid.astype(np.float64), effective_spacing


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
    if prot.ndim != 2 or prot.shape[1] != 3 or not np.isfinite(prot).all():
        return {"status": "blocked_invalid_protein_coordinates", "pocket_center": [0.0, 0.0, 0.0], "pocket_radius_a": 0.0}
    if lig.size and (lig.ndim != 2 or lig.shape[1] != 3 or not np.isfinite(lig).all()):
        return {"status": "blocked_invalid_ligand_coordinates", "pocket_center": [0.0, 0.0, 0.0], "pocket_radius_a": 0.0}
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
    max_grid_points: int = 20_000,
    distance_batch_size: int = 128,
) -> dict[str, Any]:
    """Grid cavity search: prefer points with nearby protein shell but low core density."""
    prot = np.asarray(protein_xyz, dtype=np.float64)
    if prot.size == 0:
        return {"status": "blocked_empty_protein", "pocket_center": [0.0, 0.0, 0.0], "pocket_radius_a": 0.0}
    if prot.ndim != 2 or prot.shape[1] != 3 or not np.isfinite(prot).all():
        return {"status": "blocked_invalid_protein_coordinates", "pocket_center": [0.0, 0.0, 0.0], "pocket_radius_a": 0.0}

    pad = 4.0
    bounds_min = prot.min(axis=0) - pad
    bounds_max = prot.max(axis=0) + pad
    grid, effective_spacing = _grid_centers(
        bounds_min,
        bounds_max,
        float(grid_spacing_a),
        max_grid_points=max_grid_points,
    )

    core = np.zeros(grid.shape[0], dtype=np.int32)
    shell = np.zeros(grid.shape[0], dtype=np.int32)
    batch_size = max(1, int(distance_batch_size))
    for start in range(0, int(grid.shape[0]), batch_size):
        stop = min(start + batch_size, int(grid.shape[0]))
        delta = grid[start:stop, None, :] - prot[None, :, :]
        distance_sq = np.sum(delta * delta, axis=-1)
        core[start:stop] = np.sum(distance_sq < 3.5**2, axis=1)
        shell[start:stop] = np.sum(
            (distance_sq >= 3.5**2) & (distance_sq <= 7.0**2),
            axis=1,
        )
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
            "grid_point_count": int(grid.shape[0]),
            "requested_grid_spacing_a": float(grid_spacing_a),
            "effective_grid_spacing_a": float(effective_spacing),
            "distance_batch_size": batch_size,
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
        "grid_point_count": int(grid.shape[0]),
        "requested_grid_spacing_a": float(grid_spacing_a),
        "effective_grid_spacing_a": float(effective_spacing),
        "distance_batch_size": batch_size,
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
