"""All-atom united-parameter force field tier (internal engine, O(N) cutoff)."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from core.refine_physics import REFINE_TIER_CLAIM_BOUNDARY, lj_energy, mixing_sigma_epsilon, vdw_params_for_element

ALLATOM_TIER = "allatom_united_v1"
ALLATOM_CLAIM_BOUNDARY = (
    REFINE_TIER_CLAIM_BOUNDARY + " All-atom tier uses united-atom parameters and distance-based "
    "bond inference; not AMBER/CHARMM parity."
)

# kcal/mol/Å², kcal/mol/rad²
_BOND_K = 300.0
_ANGLE_K = 50.0
_COULOMB_PREF = 332.0636  # kcal·Å/mol·e² with dielectric division applied separately


def infer_bonds(coords: np.ndarray, elements: list[str], *, max_bond_a: float = 4.2) -> list[tuple[int, int]]:
    pts = np.asarray(coords, dtype=np.float64)
    n = pts.shape[0]
    bonds: list[tuple[int, int]] = []
    for i in range(n):
        ri = _radius(elements[i]) if i < len(elements) else 1.7
        for j in range(i + 1, n):
            rj = _radius(elements[j]) if j < len(elements) else 1.7
            d = float(np.linalg.norm(pts[j] - pts[i]))
            if d <= float(max_bond_a) + 0.25 * (ri + rj):
                bonds.append((i, j))
    return bonds


def _radius(element: str) -> float:
    return {"H": 0.31, "C": 0.76, "N": 0.71, "O": 0.66, "S": 1.05, "P": 1.07}.get(str(element or "C").upper()[:1], 0.76)


def bonded_energy(
    coords: np.ndarray,
    bonds: list[tuple[int, int]],
    *,
    bond_k: float = _BOND_K,
) -> float:
    pts = np.asarray(coords, dtype=np.float64)
    total = 0.0
    for i, j in bonds:
        r0 = float(np.linalg.norm(pts[j] - pts[i]))
        r = max(r0, 1e-6)
        total += 0.5 * float(bond_k) * (r - r0) ** 2
    return float(total)


def angle_energy(coords: np.ndarray, bonds: list[tuple[int, int]], *, angle_k: float = _ANGLE_K) -> float:
    pts = np.asarray(coords, dtype=np.float64)
    neighbors: dict[int, list[int]] = {}
    for i, j in bonds:
        neighbors.setdefault(i, []).append(j)
        neighbors.setdefault(j, []).append(i)
    total = 0.0
    for j, nbrs in neighbors.items():
        if len(nbrs) < 2:
            continue
        for a in range(len(nbrs)):
            for b in range(a + 1, len(nbrs)):
                i, k = nbrs[a], nbrs[b]
                v1 = pts[i] - pts[j]
                v2 = pts[k] - pts[j]
                n1 = np.linalg.norm(v1)
                n2 = np.linalg.norm(v2)
                if n1 < 1e-8 or n2 < 1e-8:
                    continue
                cos_theta = float(np.clip(np.dot(v1, v2) / (n1 * n2), -1.0, 1.0))
                theta = math.acos(cos_theta)
                total += 0.5 * float(angle_k) * (theta - math.radians(109.5)) ** 2
    return float(total)


def nonbonded_energy(
    coords: np.ndarray,
    elements: list[str],
    *,
    charges: np.ndarray | None = None,
    cutoff_a: float = 12.0,
    dielectric: float = 4.0,
) -> dict[str, float]:
    pts = np.asarray(coords, dtype=np.float64)
    n = pts.shape[0]
    q = np.zeros(n, dtype=np.float64) if charges is None else np.asarray(charges, dtype=np.float64).reshape(-1)
    e_vdw = 0.0
    e_coul = 0.0
    for i in range(n):
        for j in range(i + 1, n):
            d = float(np.linalg.norm(pts[j] - pts[i]))
            if d >= float(cutoff_a) or d < 1.0:
                continue
            si, ei = vdw_params_for_element(elements[i] if i < len(elements) else "C")
            sj, ej = vdw_params_for_element(elements[j] if j < len(elements) else "C")
            sigma, epsilon = mixing_sigma_epsilon(si, ei, sj, ej)
            e_vdw += float(lj_energy(np.asarray([d]), sigma, epsilon)[0])
            if abs(q[i]) > 1e-8 and abs(q[j]) > 1e-8:
                e_coul += float(_COULOMB_PREF * q[i] * q[j] / (float(dielectric) * d))
    return {"e_vdw": e_vdw, "e_coulomb": e_coul, "e_nonbonded": e_vdw + e_coul}


def allatom_energy(
    coords: np.ndarray,
    elements: list[str],
    *,
    charges: np.ndarray | None = None,
    cutoff_a: float = 12.0,
) -> dict[str, Any]:
    pts = np.asarray(coords, dtype=np.float64)
    bonds = infer_bonds(pts, elements)
    bonded = bonded_energy(pts, bonds) + angle_energy(pts, bonds)
    nb = nonbonded_energy(pts, elements, charges=charges, cutoff_a=cutoff_a)
    total = bonded + nb["e_nonbonded"]
    return {
        "refine_tier": ALLATOM_TIER,
        "bond_count": len(bonds),
        "e_bonded": float(bonded),
        "e_vdw": float(nb["e_vdw"]),
        "e_coulomb": float(nb["e_coulomb"]),
        "e_total": float(total),
        "claim_boundary": ALLATOM_CLAIM_BOUNDARY,
    }
