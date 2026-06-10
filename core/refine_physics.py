"""Refine-tier physics primitives: united-atom LJ + implicit GB/SA (independent engine)."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

REFINE_TIER_CLAIM_BOUNDARY = (
    "Refine-tier implicit-solvent MM-GBSA proxy using internal united-atom parameters. "
    "Not an OpenMM/Schrödinger-grade all-atom free-energy claim."
)

# United-atom-ish VdW parameters (sigma in Å, epsilon in kcal/mol).
_VDW_PARAMS: dict[str, tuple[float, float]] = {
    "C": (3.50, 0.066),
    "N": (3.25, 0.170),
    "O": (3.00, 0.210),
    "S": (3.50, 0.250),
    "P": (3.74, 0.200),
    "H": (2.50, 0.030),
    "DEFAULT": (3.50, 0.080),
}

_DIELECTRIC_SOLVENT = 80.0
_DIELECTRIC_Solute = 1.0
_SA_GAMMA = 0.005  # kcal/mol/Å² surface tension proxy
_MIN_DISTANCE_A = 1.5


def vdw_params_for_element(element: str) -> tuple[float, float]:
    key = str(element or "").strip().upper()[:1]
    return _VDW_PARAMS.get(key, _VDW_PARAMS["DEFAULT"])


def lj_energy(dist_a: np.ndarray, sigma_a: float, epsilon_kcal: float) -> np.ndarray:
    """12-6 Lennard-Jones potential (kcal/mol)."""
    r = np.maximum(np.asarray(dist_a, dtype=np.float64), _MIN_DISTANCE_A)
    sr6 = (float(sigma_a) / r) ** 6
    sr12 = sr6 * sr6
    return 4.0 * float(epsilon_kcal) * (sr12 - sr6)


def lj_force_magnitude(dist_a: np.ndarray, sigma_a: float, epsilon_kcal: float) -> np.ndarray:
    r = np.maximum(np.asarray(dist_a, dtype=np.float64), _MIN_DISTANCE_A)
    sr6 = (float(sigma_a) / r) ** 6
    sr12 = sr6 * sr6
    return 4.0 * float(epsilon_kcal) * (12.0 * sr12 - 6.0 * sr6) / r


def mixing_sigma_epsilon(sigma_a: float, eps_a: float, sigma_b: float, eps_b: float) -> tuple[float, float]:
    sigma = math.sqrt(float(sigma_a) * float(sigma_b))
    epsilon = math.sqrt(float(eps_a) * float(eps_b))
    return sigma, epsilon


def gb_born_radius_estimate(coords: np.ndarray, neighbor_cutoff_a: float = 6.0) -> np.ndarray:
    """Crude analytical Born radii from local atomic density (Still-like)."""
    pts = np.asarray(coords, dtype=np.float64)
    if pts.size == 0:
        return np.zeros((0,), dtype=np.float64)
    n = pts.shape[0]
    if n == 1:
        return np.asarray([1.2], dtype=np.float64)
    diff = pts[:, None, :] - pts[None, :, :]
    dist = np.linalg.norm(diff, axis=-1)
    np.fill_diagonal(dist, np.inf)
    local = np.sum(dist < float(neighbor_cutoff_a), axis=1).astype(np.float64)
    density = local / max(float(neighbor_cutoff_a) ** 3, 1.0)
    born = 0.85 + 0.35 / (1.0 + 0.15 * density)
    return np.clip(born, 0.6, 2.5)


def gb_solvation_energy(
    charges: np.ndarray,
    born_radii: np.ndarray,
    *,
    dielectric_solvent: float = _DIELECTRIC_SOLVENT,
    dielectric_solute: float = _DIELECTRIC_Solute,
) -> float:
    """Generalized Born solvation free energy (kcal/mol)."""
    q = np.asarray(charges, dtype=np.float64).reshape(-1)
    rb = np.maximum(np.asarray(born_radii, dtype=np.float64).reshape(-1), 0.5)
    if q.size == 0:
        return 0.0
    pref = -0.5 * (1.0 / float(dielectric_solute) - 1.0 / float(dielectric_solvent))
    self_term = pref * np.sum(q * q / rb)
    if q.size <= 1:
        return float(self_term)
    diff = 1.0 / rb[:, None] + 1.0 / rb[None, :] - 1.0 / np.maximum(rb[:, None] + rb[None, :], 1e-6)
    pair = pref * np.outer(q, q) * diff
    np.fill_diagonal(pair, 0.0)
    return float(self_term + np.sum(pair))


def sa_surface_energy(coords: np.ndarray, *, probe_radius_a: float = 1.4) -> float:
    """Surface-area proxy from solvent-accessible count (kcal/mol)."""
    pts = np.asarray(coords, dtype=np.float64)
    if pts.size == 0:
        return 0.0
    diff = pts[:, None, :] - pts[None, :, :]
    dist = np.linalg.norm(diff, axis=-1)
    np.fill_diagonal(dist, np.inf)
    exposed = np.sum(np.min(dist, axis=1) > float(probe_radius_a) + 1.8)
    area_proxy = float(exposed) * 4.0 * math.pi * (float(probe_radius_a) + 1.5) ** 2
    return float(_SA_GAMMA * area_proxy)


def pairwise_min_distances(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    aa = np.asarray(a, dtype=np.float64)
    bb = np.asarray(b, dtype=np.float64)
    if aa.size == 0 or bb.size == 0:
        return np.zeros((0, 0), dtype=np.float64)
    return np.linalg.norm(aa[:, None, :] - bb[None, :, :], axis=-1)


def cross_vdw_energy(
    protein_xyz: np.ndarray,
    ligand_xyz: np.ndarray,
    *,
    protein_element: str = "C",
    ligand_element: str = "C",
    contact_cutoff_a: float = 10.0,
) -> dict[str, Any]:
    """Cross LJ interaction energy between protein and ligand beads."""
    d = pairwise_min_distances(protein_xyz, ligand_xyz)
    if d.size == 0:
        return {"e_vdw": 0.0, "contact_count": 0, "clash_count": 0, "min_distance_a": 999.0}
    ps, pe = vdw_params_for_element(protein_element)
    ls, le = vdw_params_for_element(ligand_element)
    sigma, epsilon = mixing_sigma_epsilon(ps, pe, ls, le)
    mask = d < float(contact_cutoff_a)
    e = lj_energy(d[mask], sigma, epsilon)
    min_d = float(np.min(d))
    clash = int(np.sum(d < 2.0))
    return {
        "e_vdw": float(np.sum(e)) if e.size else 0.0,
        "contact_count": int(np.sum(mask)),
        "clash_count": clash,
        "min_distance_a": min_d,
        "sigma_a": sigma,
        "epsilon_kcal": epsilon,
    }
