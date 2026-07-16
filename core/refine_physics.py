"""CPU reference primitives for an explicitly claim-limited interaction proxy."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

REFINE_TIER_CLAIM_BOUNDARY = (
    "Internal topology-aware interaction and implicit-solvent proxy. It is not calibrated MM-GBSA, "
    "binding free energy, affinity, or OpenMM/Schrödinger parity."
)

# United-atom-ish VdW parameters (sigma in Å, epsilon in kcal/mol).
_VDW_PARAMS: dict[str, tuple[float, float]] = {
    "C": (3.50, 0.066),
    "N": (3.25, 0.170),
    "O": (3.00, 0.210),
    "S": (3.50, 0.250),
    "P": (3.74, 0.200),
    "H": (2.50, 0.030),
    "F": (2.95, 0.061),
    "CL": (3.47, 0.150),
    "BR": (3.73, 0.200),
    "I": (4.00, 0.250),
    "DEFAULT": (3.50, 0.080),
}

_DIELECTRIC_SOLVENT = 80.0
_DIELECTRIC_Solute = 1.0
_SA_GAMMA = 0.005  # kcal/mol/Å² surface tension proxy
_MIN_DISTANCE_A = 0.5
_COULOMB_PREF = 332.0636
_VDW_RADII_A = {
    "H": 1.20,
    "C": 1.70,
    "N": 1.55,
    "O": 1.52,
    "S": 1.80,
    "P": 1.80,
    "F": 1.47,
    "CL": 1.75,
    "BR": 1.85,
    "I": 1.98,
}


def normalize_element(element: str) -> str:
    raw = str(element or "").strip().upper()
    if raw[:2] in {"CL", "BR"}:
        return raw[:2]
    return raw[:1] or "DEFAULT"


def vdw_params_for_element(element: str) -> tuple[float, float]:
    key = normalize_element(element)
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
    coords: np.ndarray | None = None,
    dielectric_solvent: float = _DIELECTRIC_SOLVENT,
    dielectric_solute: float = _DIELECTRIC_Solute,
) -> float:
    """Generalized Born solvation free energy (kcal/mol)."""
    q = np.asarray(charges, dtype=np.float64).reshape(-1)
    rb = np.maximum(np.asarray(born_radii, dtype=np.float64).reshape(-1), 0.5)
    if q.size == 0:
        return 0.0
    if q.size != rb.size:
        raise ValueError("charges and born_radii must have the same length")
    dielectric_factor = 1.0 / float(dielectric_solute) - 1.0 / float(dielectric_solvent)
    if coords is None or q.size <= 1:
        return float(-0.5 * _COULOMB_PREF * dielectric_factor * np.sum(q * q / rb))
    pts = np.asarray(coords, dtype=np.float64)
    if pts.shape != (q.size, 3):
        raise ValueError("coords must have shape [charge_count, 3]")
    delta = pts[:, None, :] - pts[None, :, :]
    r2 = np.sum(delta * delta, axis=-1)
    radii_product = np.maximum(rb[:, None] * rb[None, :], 1e-8)
    f_gb = np.sqrt(r2 + radii_product * np.exp(-r2 / (4.0 * radii_product)))
    pair_sum = np.sum(np.outer(q, q) / np.maximum(f_gb, 1e-8))
    return float(-0.5 * _COULOMB_PREF * dielectric_factor * pair_sum)


def _fibonacci_sphere(point_count: int) -> np.ndarray:
    count = max(int(point_count), 12)
    indices = np.arange(count, dtype=np.float64)
    z = 1.0 - 2.0 * (indices + 0.5) / count
    radius = np.sqrt(np.maximum(1.0 - z * z, 0.0))
    phi = indices * (math.pi * (3.0 - math.sqrt(5.0)))
    return np.stack([radius * np.cos(phi), radius * np.sin(phi), z], axis=1)


def sa_surface_energy(
    coords: np.ndarray,
    *,
    elements: list[str] | None = None,
    probe_radius_a: float = 1.4,
    sphere_point_count: int = 48,
) -> float:
    """Deterministic Shrake-Rupley-like solvent-accessible surface proxy."""
    pts = np.asarray(coords, dtype=np.float64)
    if pts.size == 0:
        return 0.0
    if pts.ndim != 2 or pts.shape[1] != 3:
        raise ValueError("coords must have shape [N, 3]")
    if elements is not None and len(elements) != len(pts):
        raise ValueError("elements must match coordinate count")
    element_list = list(elements) if elements is not None else ["C"] * len(pts)
    radii = np.asarray(
        [_VDW_RADII_A.get(normalize_element(element), 1.70) + float(probe_radius_a) for element in element_list],
        dtype=np.float64,
    )
    unit_points = _fibonacci_sphere(sphere_point_count)
    area = 0.0
    for atom_index, center in enumerate(pts):
        samples = center.reshape(1, 3) + radii[atom_index] * unit_points
        delta = samples[:, None, :] - pts[None, :, :]
        distances = np.linalg.norm(delta, axis=-1)
        distances[:, atom_index] = np.inf
        occluded = np.any(distances < radii.reshape(1, -1), axis=1)
        accessible_fraction = float(np.mean(~occluded))
        area += accessible_fraction * 4.0 * math.pi * radii[atom_index] ** 2
    return float(_SA_GAMMA * area)


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
    protein_elements: list[str] | None = None,
    ligand_elements: list[str] | None = None,
    contact_cutoff_a: float = 10.0,
) -> dict[str, Any]:
    """Cross LJ interaction energy between protein and ligand beads."""
    d = pairwise_min_distances(protein_xyz, ligand_xyz)
    if d.size == 0:
        return {"e_vdw": 0.0, "contact_count": 0, "clash_count": 0, "min_distance_a": 999.0}
    mask = d < float(contact_cutoff_a)
    prot_count, lig_count = d.shape
    protein_element_list = (
        list(protein_elements)
        if protein_elements is not None and len(protein_elements) == int(prot_count)
        else [str(protein_element)] * int(prot_count)
    )
    ligand_element_list = (
        list(ligand_elements)
        if ligand_elements is not None and len(ligand_elements) == int(lig_count)
        else [str(ligand_element)] * int(lig_count)
    )
    protein_fallback = bool(protein_elements is None or len(protein_elements) != int(prot_count))
    ligand_fallback = bool(ligand_elements is None or len(ligand_elements) != int(lig_count))
    fallback_used = bool(protein_fallback or ligand_fallback)
    e_total = 0.0
    sigma_values: list[float] = []
    epsilon_values: list[float] = []
    for i in range(int(prot_count)):
        ps, pe = vdw_params_for_element(protein_element_list[i])
        for j in range(int(lig_count)):
            if not bool(mask[i, j]):
                continue
            ls, le = vdw_params_for_element(ligand_element_list[j])
            sigma, epsilon = mixing_sigma_epsilon(ps, pe, ls, le)
            e_total += float(lj_energy(np.asarray([d[i, j]], dtype=np.float64), sigma, epsilon)[0])
            sigma_values.append(float(sigma))
            epsilon_values.append(float(epsilon))
    min_d = float(np.min(d))
    clash = int(np.sum(d < 2.0))
    return {
        "e_vdw": float(e_total),
        "contact_count": int(np.sum(mask)),
        "clash_count": clash,
        "min_distance_a": min_d,
        "sigma_a": float(np.mean(sigma_values)) if sigma_values else 0.0,
        "epsilon_kcal": float(np.mean(epsilon_values)) if epsilon_values else 0.0,
        "element_model": "single_element_proxy" if fallback_used else "typed_pairwise",
        "element_fallback_used": fallback_used,
        "protein_element_count": int(prot_count),
        "ligand_element_count": int(lig_count),
        "protein_element_fallback_used": protein_fallback,
        "ligand_element_fallback_used": ligand_fallback,
    }
