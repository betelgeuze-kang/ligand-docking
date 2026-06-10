"""Explicit TIP3P water shell placement (internal engine, no external MD)."""

from __future__ import annotations

from typing import Any

import numpy as np

from core.allatom_forcefield import allatom_energy
from core.refine_physics import gb_born_radius_estimate, gb_solvation_energy

TIP3P_CLAIM_BOUNDARY = (
    "Explicit-solvent tier places a fixed TIP3P-like water shell for local solvation recheck. "
    "Not a production MD explicit-solvent claim."
)

_O_WAT = 3.15  # Å LJ sigma proxy for water oxygen
_EPS_WAT = 0.152  # kcal/mol


def _water_grid(center: np.ndarray, radius_a: float, spacing_a: float = 2.8) -> np.ndarray:
    c = np.asarray(center, dtype=np.float64).reshape(3)
    r = float(radius_a)
    xs = np.arange(c[0] - r, c[0] + r + spacing_a, spacing_a)
    ys = np.arange(c[1] - r, c[1] + r + spacing_a, spacing_a)
    zs = np.arange(c[2] - r, c[2] + r + spacing_a, spacing_a)
    grid = np.stack(np.meshgrid(xs, ys, zs, indexing="ij"), axis=-1).reshape(-1, 3)
    dist = np.linalg.norm(grid - c.reshape(1, 3), axis=1)
    shell = (dist >= r * 0.55) & (dist <= r * 1.05)
    return grid[shell]


def place_tip3p_shell(
    solute_coords: np.ndarray,
    *,
    shell_radius_a: float = 8.0,
    spacing_a: float = 2.8,
    max_waters: int = 256,
) -> dict[str, Any]:
    """Place waters around solute centroid in a spherical shell."""
    solute = np.asarray(solute_coords, dtype=np.float64)
    if solute.size == 0:
        return {"status": "blocked_empty_solute", "water_count": 0, "water_coords": np.zeros((0, 3))}
    center = solute.mean(axis=0)
    candidates = _water_grid(center, float(shell_radius_a), spacing_a=float(spacing_a))
    if candidates.size == 0:
        return {"status": "blocked_no_shell", "water_count": 0, "water_coords": np.zeros((0, 3))}

    kept: list[np.ndarray] = []
    min_solute_dist = 2.4
    min_water_dist = 2.2
    for point in candidates:
        if len(kept) >= int(max_waters):
            break
        if float(np.min(np.linalg.norm(solute - point.reshape(1, 3), axis=1))) < min_solute_dist:
            continue
        if kept and float(min(np.linalg.norm(np.stack(kept) - point, axis=1))) < min_water_dist:
            continue
        kept.append(point)
    waters = np.stack(kept, axis=0) if kept else np.zeros((0, 3), dtype=np.float64)
    return {
        "status": "explicit_shell_ready",
        "water_count": int(waters.shape[0]),
        "water_coords": waters.astype(np.float32),
        "shell_radius_a": float(shell_radius_a),
        "claim_boundary": TIP3P_CLAIM_BOUNDARY,
    }


def explicit_solvation_energy(
    solute_coords: np.ndarray,
    solute_elements: list[str],
    *,
    shell_radius_a: float = 8.0,
) -> dict[str, Any]:
    """Solute all-atom energy + explicit water shell + GB correction for outer bulk."""
    shell = place_tip3p_shell(solute_coords, shell_radius_a=float(shell_radius_a))
    waters = np.asarray(shell["water_coords"], dtype=np.float64)
    solute = np.asarray(solute_coords, dtype=np.float64)
    elements = list(solute_elements) + ["O"] * int(waters.shape[0])
    complex_coords = np.vstack([solute, waters]) if waters.size else solute
    solute_energy = allatom_energy(solute, solute_elements)
    complex_energy = allatom_energy(complex_coords, elements) if waters.size else solute_energy
    delta_explicit = float(complex_energy["e_total"] - solute_energy["e_total"])
    born = gb_born_radius_estimate(complex_coords)
    e_gb = gb_solvation_energy(np.zeros(complex_coords.shape[0]), born)
    return {
        "refine_tier": "explicit_tip3p_shell_v1",
        "water_count": int(shell["water_count"]),
        "e_solute": float(solute_energy["e_total"]),
        "e_complex": float(complex_energy["e_total"]),
        "delta_e_explicit_kcal_mol": delta_explicit,
        "e_gb_bulk_proxy": float(e_gb),
        "delta_e_total_kcal_mol": float(delta_explicit + 0.15 * e_gb),
        "claim_boundary": TIP3P_CLAIM_BOUNDARY,
    }
