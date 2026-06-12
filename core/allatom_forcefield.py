"""All-atom united-parameter force field tier (internal engine, O(N) cutoff)."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from core.refine_physics import REFINE_TIER_CLAIM_BOUNDARY, lj_energy, mixing_sigma_epsilon, vdw_params_for_element

ALLATOM_TIER = "allatom_united_v1"
ALLATOM_CLAIM_BOUNDARY = (
    REFINE_TIER_CLAIM_BOUNDARY + " All-atom tier uses united-atom parameters and distance-based "
    "bond inference plus typed internal partial charges; not AMBER/CHARMM parity."
)
PARAMETER_CALIBRATION_STATUS = "internal_proxy_uncalibrated"

# kcal/mol/Å², kcal/mol/rad²
_BOND_K = 300.0
_ANGLE_K = 50.0
_DIHEDRAL_K = 0.35
_IMPROPER_K = 25.0
_COULOMB_PREF = 332.0636  # kcal·Å/mol·e² with dielectric division applied separately

_ATOM_TYPE_PARAMS: dict[str, tuple[float, float, float]] = {
    # sigma Å, epsilon kcal/mol, partial charge e. Internal typed proxy only.
    "H_POLAR": (2.42, 0.020, 0.18),
    "H_APOLAR": (2.50, 0.015, 0.06),
    "C_SP3": (3.50, 0.066, -0.06),
    "C_SP2": (3.40, 0.070, 0.05),
    "C_SP": (3.35, 0.060, 0.03),
    "C_CARBONYL": (3.35, 0.080, 0.35),
    "N_POLAR": (3.25, 0.170, -0.30),
    "N_BASIC": (3.30, 0.160, -0.18),
    "O_CARBONYL": (3.00, 0.210, -0.45),
    "O_HYDROXYL": (3.05, 0.180, -0.35),
    "S_THIOETHER": (3.50, 0.250, -0.10),
    "P_PHOSPHATE": (3.74, 0.200, 0.70),
    "F_HALOGEN": (2.95, 0.061, -0.08),
    "CL_HALOGEN": (3.47, 0.150, -0.03),
    "BR_HALOGEN": (3.73, 0.200, -0.02),
    "I_HALOGEN": (4.00, 0.250, -0.01),
    "X_DEFAULT": (3.50, 0.080, 0.00),
}

SUPPORTED_ATOM_TYPES = tuple(sorted(atom_type for atom_type in _ATOM_TYPE_PARAMS if atom_type != "X_DEFAULT"))
SUPPORTED_ELEMENTS = ("H", "C", "N", "O", "S", "P", "F", "CL", "BR", "I")
UNSUPPORTED_METAL_OR_COFACTOR_ELEMENTS = ("NA", "MG", "CA", "FE", "ZN")


def infer_bonds(coords: np.ndarray, elements: list[str], *, max_bond_a: float = 4.2) -> list[tuple[int, int]]:
    pts = np.asarray(coords, dtype=np.float64)
    n = pts.shape[0]
    bonds: list[tuple[int, int]] = []
    for i in range(n):
        ri = _radius(elements[i]) if i < len(elements) else 1.7
        for j in range(i + 1, n):
            rj = _radius(elements[j]) if j < len(elements) else 1.7
            d = float(np.linalg.norm(pts[j] - pts[i]))
            if d <= _covalent_bond_threshold(ri, rj):
                bonds.append((i, j))
    if not bonds:
        for i in range(n - 1):
            a = str(elements[i] if i < len(elements) else "C").upper()[:1]
            b = str(elements[i + 1] if i + 1 < len(elements) else "C").upper()[:1]
            if not (a == "C" and b == "C"):
                continue
            d = float(np.linalg.norm(pts[i + 1] - pts[i]))
            if d <= float(max_bond_a):
                bonds.append((i, i + 1))
    return bonds


def _normalize_element(element: str) -> str:
    raw = str(element or "C").strip().upper()
    if not raw:
        return "C"
    two_char = raw[:2]
    if two_char in {"CL", "BR", "NA", "MG", "CA", "FE", "ZN"}:
        return two_char
    return raw[:1]


def _radius(element: str) -> float:
    return {
        "H": 0.31,
        "C": 0.76,
        "N": 0.71,
        "O": 0.66,
        "S": 1.05,
        "P": 1.07,
        "F": 0.57,
        "CL": 1.02,
        "BR": 1.20,
        "I": 1.39,
    }.get(_normalize_element(element), 0.76)


def _covalent_bond_threshold(ri: float, rj: float) -> float:
    return 1.35 * (float(ri) + float(rj)) + 0.15


def equilibrium_bond_length(element_i: str, element_j: str, observed_distance_a: float) -> float:
    ri = _radius(element_i)
    rj = _radius(element_j)
    observed = max(float(observed_distance_a), 1e-6)
    if observed <= _covalent_bond_threshold(ri, rj):
        return 1.08 * (ri + rj)
    return observed


def _element(elements: list[str], idx: int) -> str:
    return _normalize_element(elements[idx] if idx < len(elements) else "C")


def _bond_degrees(n_atoms: int, bonds: list[tuple[int, int]]) -> list[int]:
    degree = [0 for _ in range(int(n_atoms))]
    for i, j in bonds:
        if 0 <= i < n_atoms:
            degree[i] += 1
        if 0 <= j < n_atoms:
            degree[j] += 1
    return degree


def _neighbors_from_bonds(bonds: list[tuple[int, int]]) -> dict[int, list[int]]:
    neighbors: dict[int, list[int]] = {}
    for i, j in bonds:
        neighbors.setdefault(i, []).append(j)
        neighbors.setdefault(j, []).append(i)
    return {idx: sorted(set(values)) for idx, values in neighbors.items()}


def infer_atom_types(
    coords: np.ndarray,
    elements: list[str],
    *,
    bonds: list[tuple[int, int]] | None = None,
) -> list[str]:
    """Infer a small internal united-atom type set from element and local degree."""
    pts = np.asarray(coords, dtype=np.float64)
    inferred_bonds = infer_bonds(pts, elements) if bonds is None else list(bonds)
    degree = _bond_degrees(int(pts.shape[0]), inferred_bonds)
    types: list[str] = []
    for idx in range(int(pts.shape[0])):
        element = _element(elements, idx)
        deg = degree[idx]
        if element == "H":
            attached = [
                _element(elements, j if i == idx else i)
                for i, j in inferred_bonds
                if i == idx or j == idx
            ]
            types.append("H_POLAR" if any(e in {"N", "O", "S"} for e in attached) else "H_APOLAR")
        elif element == "C":
            neighbor_elements = [
                _element(elements, j if i == idx else i)
                for i, j in inferred_bonds
                if i == idx or j == idx
            ]
            if any(e == "O" for e in neighbor_elements) and deg <= 3:
                types.append("C_CARBONYL")
            elif deg <= 1:
                types.append("C_SP")
            elif deg == 2:
                types.append("C_SP2")
            else:
                types.append("C_SP3")
        elif element == "N":
            types.append("N_BASIC" if deg >= 3 else "N_POLAR")
        elif element == "O":
            types.append("O_CARBONYL" if deg <= 1 else "O_HYDROXYL")
        elif element == "S":
            types.append("S_THIOETHER")
        elif element == "P":
            types.append("P_PHOSPHATE")
        elif element == "F":
            types.append("F_HALOGEN")
        elif element == "CL":
            types.append("CL_HALOGEN")
        elif element == "BR":
            types.append("BR_HALOGEN")
        elif element == "I":
            types.append("I_HALOGEN")
        else:
            types.append("X_DEFAULT")
    return types


def atom_typing_coverage_report(
    coords: np.ndarray,
    elements: list[str],
    *,
    bonds: list[tuple[int, int]] | None = None,
) -> dict[str, Any]:
    """Report internal atom-typing coverage without upgrading the claim boundary."""
    pts = np.asarray(coords, dtype=np.float64)
    inferred_bonds = infer_bonds(pts, elements) if bonds is None else list(bonds)
    atom_types = infer_atom_types(pts, elements, bonds=inferred_bonds)
    normalized_elements = [_element(elements, idx) for idx in range(int(pts.shape[0]))]
    unsupported_elements = sorted({element for element in normalized_elements if element not in SUPPORTED_ELEMENTS})
    unsupported_metal_or_cofactor_elements = sorted(
        {element for element in unsupported_elements if element in UNSUPPORTED_METAL_OR_COFACTOR_ELEMENTS}
    )
    default_atom_count = sum(1 for atom_type in atom_types if atom_type == "X_DEFAULT")
    atom_type_counts = {atom_type: atom_types.count(atom_type) for atom_type in sorted(set(atom_types))}
    charges = partial_charges_from_atom_types(atom_types)
    atom_count = int(pts.shape[0])
    typed_atom_count = atom_count - int(default_atom_count)
    coverage_fraction = float(typed_atom_count / atom_count) if atom_count else 0.0
    coverage_ready = bool(atom_count and default_atom_count == 0 and not unsupported_elements)
    return {
        "status": "atom_typing_coverage_ready" if coverage_ready else "blocked_atom_typing_coverage",
        "atom_count": atom_count,
        "typed_atom_count": int(typed_atom_count),
        "default_atom_count": int(default_atom_count),
        "coverage_fraction": coverage_fraction,
        "supported_elements": list(SUPPORTED_ELEMENTS),
        "unsupported_elements": unsupported_elements,
        "unsupported_metal_or_cofactor_elements": unsupported_metal_or_cofactor_elements,
        "unsupported_metal_or_cofactor_count": sum(
            1 for element in normalized_elements if element in UNSUPPORTED_METAL_OR_COFACTOR_ELEMENTS
        ),
        "atom_types": atom_types,
        "atom_type_counts": atom_type_counts,
        "bond_count": len(inferred_bonds),
        "charge_neutralization_ok": bool(abs(float(np.sum(charges))) < 1e-8),
        "net_charge_e": float(np.sum(charges)) if charges.size else 0.0,
        "claim_boundary": ALLATOM_CLAIM_BOUNDARY,
    }


def parameter_calibration_report(
    *,
    public_benchmark_pair_count: int = 0,
    min_public_benchmark_pairs: int = 5,
    public_benchmark_ready: bool = False,
) -> dict[str, Any]:
    """Report calibration posture for internal all-atom proxy parameters."""
    pair_count = int(public_benchmark_pair_count)
    min_pairs = int(min_public_benchmark_pairs)
    enough_pairs = pair_count >= min_pairs
    claim_ready = bool(public_benchmark_ready and enough_pairs)
    blockers: list[str] = []
    if not enough_pairs:
        blockers.append("insufficient_public_benchmark_pairs")
    if not public_benchmark_ready:
        blockers.append("public_benchmark_gate_not_ready")
    return {
        "status": "claim_grade_parameterization_ready" if claim_ready else "blocked_parameter_calibration_claim",
        "parameter_calibration_status": PARAMETER_CALIBRATION_STATUS,
        "claim_grade_parameterization_ready": claim_ready,
        "public_benchmark_pair_count": pair_count,
        "min_public_benchmark_pairs": min_pairs,
        "public_benchmark_ready": bool(public_benchmark_ready),
        "blockers": blockers,
        "charge_parameter_source": "internal_atom_type_proxy_uncalibrated",
        "bonded_parameter_source": "covalent_radii_and_harmonic_proxy_uncalibrated",
        "torsion_parameter_source": "periodic_proxy_n3_uncalibrated",
        "improper_parameter_source": "planarity_proxy_uncalibrated",
        "solvent_parameter_source": "gb_sa_proxy_uncalibrated",
        "claim_boundary": ALLATOM_CLAIM_BOUNDARY,
    }


def vdw_params_for_atom_type(atom_type: str) -> tuple[float, float]:
    sigma, epsilon, _charge = _ATOM_TYPE_PARAMS.get(str(atom_type or "X_DEFAULT"), _ATOM_TYPE_PARAMS["X_DEFAULT"])
    return sigma, epsilon


def partial_charges_from_atom_types(
    atom_types: list[str],
    *,
    neutralize: bool = True,
) -> np.ndarray:
    charges = np.asarray(
        [_ATOM_TYPE_PARAMS.get(str(atom_type), _ATOM_TYPE_PARAMS["X_DEFAULT"])[2] for atom_type in atom_types],
        dtype=np.float64,
    )
    if neutralize and charges.size:
        charges = charges - float(np.mean(charges))
    return charges


def _dihedral_angle(p0: np.ndarray, p1: np.ndarray, p2: np.ndarray, p3: np.ndarray) -> float:
    b0 = -(p1 - p0)
    b1 = p2 - p1
    b2 = p3 - p2
    norm_b1 = np.linalg.norm(b1)
    if norm_b1 < 1e-8:
        return 0.0
    b1 = b1 / norm_b1
    v = b0 - np.dot(b0, b1) * b1
    w = b2 - np.dot(b2, b1) * b1
    nv = np.linalg.norm(v)
    nw = np.linalg.norm(w)
    if nv < 1e-8 or nw < 1e-8:
        return 0.0
    v = v / nv
    w = w / nw
    x = float(np.dot(v, w))
    y = float(np.dot(np.cross(b1, v), w))
    return float(math.atan2(y, x))


def infer_torsions(bonds: list[tuple[int, int]]) -> list[tuple[int, int, int, int]]:
    neighbors = _neighbors_from_bonds(bonds)
    torsions: set[tuple[int, int, int, int]] = set()
    for j, k in bonds:
        for i in neighbors.get(j, []):
            if i == k:
                continue
            for l in neighbors.get(k, []):
                if l == j or l == i:
                    continue
                torsion = (i, j, k, l)
                reverse = (l, k, j, i)
                torsions.add(min(torsion, reverse))
    return sorted(torsions)


def dihedral_energy(
    coords: np.ndarray,
    torsions: list[tuple[int, int, int, int]],
    *,
    dihedral_k: float = _DIHEDRAL_K,
    periodicity: int = 3,
) -> float:
    pts = np.asarray(coords, dtype=np.float64)
    total = 0.0
    for i, j, k, l in torsions:
        phi = _dihedral_angle(pts[i], pts[j], pts[k], pts[l])
        total += float(dihedral_k) * (1.0 + math.cos(int(periodicity) * phi))
    return float(total)


def infer_impropers(
    bonds: list[tuple[int, int]],
    atom_types: list[str],
) -> list[tuple[int, int, int, int]]:
    neighbors = _neighbors_from_bonds(bonds)
    impropers: list[tuple[int, int, int, int]] = []
    planar_types = {"C_SP2", "C_CARBONYL", "N_POLAR", "P_PHOSPHATE"}
    for center, nbrs in neighbors.items():
        if center >= len(atom_types) or atom_types[center] not in planar_types or len(nbrs) < 3:
            continue
        first_three = sorted(nbrs)[:3]
        impropers.append((center, first_three[0], first_three[1], first_three[2]))
    return impropers


def improper_energy(
    coords: np.ndarray,
    impropers: list[tuple[int, int, int, int]],
    *,
    improper_k: float = _IMPROPER_K,
) -> float:
    pts = np.asarray(coords, dtype=np.float64)
    total = 0.0
    for center, a, b, c in impropers:
        normal = np.cross(pts[b] - pts[a], pts[c] - pts[a])
        norm = float(np.linalg.norm(normal))
        if norm < 1e-8:
            continue
        signed_distance = float(np.dot(pts[center] - pts[a], normal / norm))
        total += 0.5 * float(improper_k) * signed_distance * signed_distance
    return float(total)


def bonded_energy(
    coords: np.ndarray,
    bonds: list[tuple[int, int]],
    *,
    elements: list[str] | None = None,
    bond_k: float = _BOND_K,
) -> float:
    pts = np.asarray(coords, dtype=np.float64)
    total = 0.0
    for i, j in bonds:
        observed = float(np.linalg.norm(pts[j] - pts[i]))
        r = max(observed, 1e-6)
        if elements is None:
            r0 = observed
        else:
            ei = elements[i] if i < len(elements) else "C"
            ej = elements[j] if j < len(elements) else "C"
            r0 = equilibrium_bond_length(ei, ej, observed)
        total += 0.5 * float(bond_k) * (r - r0) ** 2
    return float(total)


def angle_energy(coords: np.ndarray, bonds: list[tuple[int, int]], *, angle_k: float = _ANGLE_K) -> float:
    pts = np.asarray(coords, dtype=np.float64)
    neighbors = _neighbors_from_bonds(bonds)
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
    atom_types: list[str] | None = None,
    charges: np.ndarray | None = None,
    exclude_pairs: set[tuple[int, int]] | None = None,
    cutoff_a: float = 12.0,
    dielectric: float = 4.0,
) -> dict[str, float]:
    pts = np.asarray(coords, dtype=np.float64)
    n = pts.shape[0]
    inferred_types = infer_atom_types(pts, elements) if atom_types is None else list(atom_types)
    q = (
        partial_charges_from_atom_types(inferred_types)
        if charges is None
        else np.asarray(charges, dtype=np.float64).reshape(-1)
    )
    excluded = set(exclude_pairs or set())
    e_vdw = 0.0
    e_coul = 0.0
    for i in range(n):
        for j in range(i + 1, n):
            if (i, j) in excluded or (j, i) in excluded:
                continue
            d = float(np.linalg.norm(pts[j] - pts[i]))
            if d >= float(cutoff_a) or d < 1.0:
                continue
            if atom_types is None:
                si, ei = vdw_params_for_element(elements[i] if i < len(elements) else "C")
                sj, ej = vdw_params_for_element(elements[j] if j < len(elements) else "C")
            else:
                si, ei = vdw_params_for_atom_type(inferred_types[i] if i < len(inferred_types) else "X_DEFAULT")
                sj, ej = vdw_params_for_atom_type(inferred_types[j] if j < len(inferred_types) else "X_DEFAULT")
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
    atom_types = infer_atom_types(pts, elements, bonds=bonds)
    coverage = atom_typing_coverage_report(pts, elements, bonds=bonds)
    calibration = parameter_calibration_report()
    q = partial_charges_from_atom_types(atom_types) if charges is None else np.asarray(charges, dtype=np.float64).reshape(-1)
    torsions = infer_torsions(bonds)
    impropers = infer_impropers(bonds, atom_types)
    bonded = (
        bonded_energy(pts, bonds, elements=elements)
        + angle_energy(pts, bonds)
        + dihedral_energy(pts, torsions)
        + improper_energy(pts, impropers)
    )
    nb = nonbonded_energy(
        pts,
        elements,
        atom_types=atom_types,
        charges=q,
        exclude_pairs={(min(i, j), max(i, j)) for i, j in bonds},
        cutoff_a=cutoff_a,
    )
    total = bonded + nb["e_nonbonded"]
    return {
        "refine_tier": ALLATOM_TIER,
        "parameterization_level": "internal_united_atom_typed_v1",
        "bond_model": "covalent_radii_equilibrium_with_coarse_trace_fallback",
        "angle_model": "tetrahedral_harmonic_proxy",
        "dihedral_model": "periodic_torsion_proxy_n3",
        "improper_model": "planarity_proxy_for_sp2_like_centers",
        "charge_model": "typed_partial_charge_neutralized_v1" if charges is None else "caller_supplied",
        "parameter_calibration_status": calibration["parameter_calibration_status"],
        "claim_grade_parameterization_ready": calibration["claim_grade_parameterization_ready"],
        "charge_parameter_source": calibration["charge_parameter_source"],
        "bonded_parameter_source": calibration["bonded_parameter_source"],
        "torsion_parameter_source": calibration["torsion_parameter_source"],
        "improper_parameter_source": calibration["improper_parameter_source"],
        "nonbonded_exclusions": "1-2_bonded_pairs",
        "atom_types": atom_types,
        "atom_typing_coverage_status": coverage["status"],
        "atom_typing_coverage_fraction": coverage["coverage_fraction"],
        "default_atom_count": coverage["default_atom_count"],
        "unsupported_elements": coverage["unsupported_elements"],
        "unsupported_metal_or_cofactor_elements": coverage["unsupported_metal_or_cofactor_elements"],
        "unsupported_metal_or_cofactor_count": coverage["unsupported_metal_or_cofactor_count"],
        "net_charge_e": float(np.sum(q)) if q.size else 0.0,
        "bond_count": len(bonds),
        "torsion_count": len(torsions),
        "improper_count": len(impropers),
        "e_bonded": float(bonded),
        "e_vdw": float(nb["e_vdw"]),
        "e_coulomb": float(nb["e_coulomb"]),
        "e_total": float(total),
        "claim_boundary": ALLATOM_CLAIM_BOUNDARY,
    }
