"""Fixed oxygen-shell diagnostic; deliberately not an explicit-solvent model."""

from __future__ import annotations

from typing import Any

import numpy as np

from core.refine_physics import cross_vdw_energy

TIP3P_CLAIM_BOUNDARY = (
    "Fixed, unoriented oxygen points provide a geometric shell diagnostic only. This is not TIP3P, "
    "explicit solvent, molecular dynamics, or a solvation free-energy calculation."
)


def _water_grid(
    center: np.ndarray,
    radius_a: float,
    spacing_a: float = 2.8,
) -> np.ndarray:
    c = np.asarray(center, dtype=np.float64).reshape(3)
    r = float(radius_a)
    xs = np.arange(c[0] - r, c[0] + r + spacing_a, spacing_a)
    ys = np.arange(c[1] - r, c[1] + r + spacing_a, spacing_a)
    zs = np.arange(c[2] - r, c[2] + r + spacing_a, spacing_a)
    grid = np.stack(
        np.meshgrid(xs, ys, zs, indexing="ij"),
        axis=-1,
    ).reshape(-1, 3)
    dist = np.linalg.norm(grid - c.reshape(1, 3), axis=1)
    shell = (dist >= r * 0.55) & (dist <= r * 1.05)
    return grid[shell]


def place_fixed_oxygen_shell(
    solute_coords: np.ndarray,
    *,
    shell_radius_a: float = 8.0,
    spacing_a: float = 2.8,
    max_waters: int = 256,
) -> dict[str, Any]:
    """Place unoriented oxygen proxy points around a solute centroid."""
    solute = np.asarray(solute_coords, dtype=np.float64)
    if solute.size == 0:
        return {
            "status": "blocked_empty_solute",
            "water_count": 0,
            "water_coords": np.zeros((0, 3)),
            "claim_boundary": TIP3P_CLAIM_BOUNDARY,
        }
    if solute.ndim != 2 or solute.shape[1] != 3:
        raise ValueError("solute_coords must have shape [N, 3]")
    if not np.isfinite(solute).all():
        raise ValueError("solute_coords must contain only finite values")
    if not np.isfinite(float(shell_radius_a)) or float(shell_radius_a) <= 0.0:
        raise ValueError("shell_radius_a must be positive and finite")
    if not np.isfinite(float(spacing_a)) or float(spacing_a) <= 0.0:
        raise ValueError("spacing_a must be positive and finite")
    if int(max_waters) < 0:
        raise ValueError("max_waters must be non-negative")

    center = solute.mean(axis=0)
    candidates = _water_grid(
        center,
        float(shell_radius_a),
        spacing_a=float(spacing_a),
    )
    if candidates.size == 0:
        return {
            "status": "blocked_no_shell",
            "water_count": 0,
            "water_coords": np.zeros((0, 3)),
            "claim_boundary": TIP3P_CLAIM_BOUNDARY,
        }

    kept: list[np.ndarray] = []
    min_solute_dist = 2.4
    min_water_dist = 2.2
    for point in candidates:
        if len(kept) >= int(max_waters):
            break
        if (
            float(
                np.min(
                    np.linalg.norm(
                        solute - point.reshape(1, 3),
                        axis=1,
                    )
                )
            )
            < min_solute_dist
        ):
            continue
        if kept and float(
            min(np.linalg.norm(np.stack(kept) - point, axis=1))
        ) < min_water_dist:
            continue
        kept.append(point)
    waters = (
        np.stack(kept, axis=0)
        if kept
        else np.zeros((0, 3), dtype=np.float64)
    )
    return {
        "status": "fixed_oxygen_shell_ready",
        "water_count": int(waters.shape[0]),
        "oxygen_proxy_count": int(waters.shape[0]),
        "water_coords": waters.astype(np.float32),
        "shell_radius_a": float(shell_radius_a),
        "is_tip3p": False,
        "is_explicit_solvent_md": False,
        "claim_boundary": TIP3P_CLAIM_BOUNDARY,
    }


def place_tip3p_shell(
    solute_coords: np.ndarray,
    *,
    shell_radius_a: float = 8.0,
    spacing_a: float = 2.8,
    max_waters: int = 256,
) -> dict[str, Any]:
    """Deprecated compatibility alias for :func:`place_fixed_oxygen_shell`."""
    result = place_fixed_oxygen_shell(
        solute_coords,
        shell_radius_a=shell_radius_a,
        spacing_a=spacing_a,
        max_waters=max_waters,
    )
    result["deprecated_api_alias"] = "place_tip3p_shell"
    return result


def fixed_oxygen_shell_interaction_score(
    solute_coords: np.ndarray,
    solute_elements: list[str],
    *,
    shell_radius_a: float = 8.0,
) -> dict[str, Any]:
    """Return a fixed oxygen-shell interaction diagnostic in proxy units."""
    shell = place_fixed_oxygen_shell(
        solute_coords,
        shell_radius_a=float(shell_radius_a),
    )
    waters = np.asarray(shell["water_coords"], dtype=np.float64)
    solute = np.asarray(solute_coords, dtype=np.float64)
    if len(solute_elements) != int(solute.shape[0]):
        raise ValueError("solute_elements must match coordinate count")
    interaction = (
        cross_vdw_energy(
            solute,
            waters,
            protein_elements=list(solute_elements),
            ligand_elements=["O"] * int(waters.shape[0]),
            contact_cutoff_a=10.0,
        )
        if waters.size
        else {
            "e_vdw": 0.0,
            "contact_count": 0,
            "clash_count": 0,
            "min_distance_a": 999.0,
        }
    )
    score = float(interaction["e_vdw"])
    return {
        "status": "fixed_oxygen_shell_proxy_ready",
        "refine_tier": "fixed_oxygen_shell_proxy_v2",
        "water_count": int(shell["water_count"]),
        "oxygen_proxy_count": int(shell["water_count"]),
        "solvation_score_proxy": score,
        "cross_vdw_score_proxy": score,
        "contact_count": int(interaction["contact_count"]),
        "clash_count": int(interaction["clash_count"]),
        "min_distance_a": float(interaction["min_distance_a"]),
        "is_tip3p": False,
        "is_explicit_solvent_md": False,
        "score_unit": "internal_proxy_unit",
        "legacy_energy_field_deprecated": True,
        "delta_e_explicit_kcal_mol": None,
        "delta_e_total_kcal_mol": None,
        "claim_safe": False,
        "blocked_reason": "oriented_water_model_and_ensemble_sampling_missing",
        "claim_boundary": TIP3P_CLAIM_BOUNDARY,
    }


def explicit_solvation_energy(
    solute_coords: np.ndarray,
    solute_elements: list[str],
    *,
    shell_radius_a: float = 8.0,
) -> dict[str, Any]:
    """Deprecated compatibility alias for the fixed oxygen-shell score."""
    result = fixed_oxygen_shell_interaction_score(
        solute_coords,
        solute_elements,
        shell_radius_a=shell_radius_a,
    )
    result["deprecated_api_alias"] = "explicit_solvation_energy"
    return result
