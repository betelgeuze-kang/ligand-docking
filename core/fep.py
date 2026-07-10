"""Static alchemical endpoint diagnostic plus a standalone BAR estimator."""

from __future__ import annotations

from typing import Any

import numpy as np

from core.allatom_forcefield import allatom_energy
from core.refine_physics import lj_energy, mixing_sigma_epsilon, vdw_params_for_element

FEP_CLAIM_BOUNDARY = (
    "Fixed-coordinate alchemical endpoint diagnostic only. No ensemble sampling, solvent leg, restraints, "
    "or convergence evidence is present, so this output is not FEP or binding free energy."
)


def lambda_schedule(n_windows: int = 11) -> np.ndarray:
    n = max(int(n_windows), 2)
    return np.linspace(0.0, 1.0, n, dtype=np.float64)


def softcore_lj_at_lambda(
    dist_a: np.ndarray,
    sigma_a: float,
    epsilon_kcal: float,
    *,
    lam: float,
    alpha: float = 0.5,
) -> np.ndarray:
    """Linear alchemical annihilation: scale epsilon by (1-lambda) with soft core."""
    r = np.maximum(np.asarray(dist_a, dtype=np.float64), 0.5 + float(alpha) * (1.0 - float(lam)))
    scaled_eps = float(epsilon_kcal) * (1.0 - float(lam))
    return lj_energy(r, float(sigma_a), scaled_eps)


def _normalized_elements(
    elements: list[str] | None,
    atom_count: int,
    *,
    default: str = "C",
) -> tuple[list[str], bool]:
    count = int(atom_count)
    if elements is None or len(elements) != count:
        return [str(default)] * count, True
    return [str(element or default) for element in elements], False


def _ligand_protein_cross_energy(
    protein_xyz: np.ndarray,
    ligand_xyz: np.ndarray,
    *,
    lam: float,
    protein_element: str = "C",
    ligand_element: str = "C",
    protein_elements: list[str] | None = None,
    ligand_elements: list[str] | None = None,
) -> float:
    prot = np.asarray(protein_xyz, dtype=np.float64)
    lig = np.asarray(ligand_xyz, dtype=np.float64)
    if prot.size == 0 or lig.size == 0:
        return 0.0
    d = np.linalg.norm(prot[:, None, :] - lig[None, :, :], axis=-1)
    prot_elements, _ = _normalized_elements(protein_elements, int(prot.shape[0]), default=protein_element)
    lig_elements, _ = _normalized_elements(ligand_elements, int(lig.shape[0]), default=ligand_element)
    total = 0.0
    for i, prot_element in enumerate(prot_elements):
        ps, pe = vdw_params_for_element(prot_element)
        for j, lig_element in enumerate(lig_elements):
            ls, le = vdw_params_for_element(lig_element)
            sigma, epsilon = mixing_sigma_epsilon(ps, pe, ls, le)
            total += float(softcore_lj_at_lambda(np.asarray([d[i, j]], dtype=np.float64), sigma, epsilon, lam=float(lam))[0])
    return float(total)


def _element_metadata(
    protein_element_fallback_used: bool,
    ligand_element_fallback_used: bool,
    protein_element_count: int,
    ligand_element_count: int,
) -> dict[str, Any]:
    fallback_used = bool(protein_element_fallback_used or ligand_element_fallback_used)
    return {
        "element_model": "single_element_proxy" if fallback_used else "typed_pairwise",
        "element_fallback_used": fallback_used,
        "protein_element_fallback_used": bool(protein_element_fallback_used),
        "ligand_element_fallback_used": bool(ligand_element_fallback_used),
        "protein_element_count": int(protein_element_count),
        "ligand_element_count": int(ligand_element_count),
    }


def fep_lambda_energies(
    protein_xyz: np.ndarray,
    ligand_xyz: np.ndarray,
    *,
    n_windows: int = 11,
    protein_elements: list[str] | None = None,
    ligand_elements: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Energy at each lambda for protein–ligand annihilation path."""
    protein_atom_count = int(np.asarray(protein_xyz).shape[0])
    ligand_atom_count = int(np.asarray(ligand_xyz).shape[0])
    protein_element_list, protein_fallback = _normalized_elements(protein_elements, protein_atom_count)
    ligand_element_list, ligand_fallback = _normalized_elements(ligand_elements, ligand_atom_count)
    element_meta = _element_metadata(protein_fallback, ligand_fallback, protein_atom_count, ligand_atom_count)
    schedule = lambda_schedule(n_windows)
    lig_internal = allatom_energy(ligand_xyz, ligand_element_list)
    rows: list[dict[str, Any]] = []
    for lam in schedule:
        cross = _ligand_protein_cross_energy(
            protein_xyz,
            ligand_xyz,
            lam=float(lam),
            protein_elements=protein_element_list,
            ligand_elements=ligand_element_list,
        )
        total = float(lig_internal["e_total"]) + cross
        rows.append({"lambda": float(lam), "e_cross": cross, "e_total": total, **element_meta})
    return rows


def bar_free_energy(
    forward_work: np.ndarray | list[float],
    reverse_work: np.ndarray | list[float] | None = None,
    *,
    temperature_k: float = 298.15,
    tolerance_kcal_mol: float = 1e-10,
    max_iterations: int = 256,
) -> float:
    """Solve the equal-sample Bennett acceptance-ratio equation.

    ``forward_work`` is A→B work and ``reverse_work`` is B→A work using the
    usual sign convention. Static lambda energies are intentionally rejected:
    BAR requires forward and reverse ensemble samples.
    """

    if reverse_work is None:
        raise ValueError("BAR requires separate forward and reverse work samples")
    forward = np.asarray(forward_work, dtype=np.float64).reshape(-1)
    reverse = np.asarray(reverse_work, dtype=np.float64).reshape(-1)
    forward = forward[np.isfinite(forward)]
    reverse = reverse[np.isfinite(reverse)]
    if forward.size < 2 or reverse.size < 2:
        raise ValueError("BAR requires at least two finite samples in each direction")
    if forward.size != reverse.size:
        raise ValueError("this reference BAR implementation requires equal sample counts")
    kbt = 0.00198720425864083 * float(temperature_k)
    if not np.isfinite(kbt) or kbt <= 0.0:
        raise ValueError("temperature_k must be positive and finite")
    beta = 1.0 / kbt

    def _fermi(value: np.ndarray) -> np.ndarray:
        clipped = np.clip(value, -700.0, 700.0)
        return 1.0 / (1.0 + np.exp(clipped))

    def equation(delta_f: float) -> float:
        lhs = np.sum(_fermi(beta * (forward - delta_f)))
        rhs = np.sum(_fermi(beta * (reverse + delta_f)))
        return float(lhs - rhs)

    span = max(float(np.ptp(forward)), float(np.ptp(reverse)), kbt)
    lower = min(float(np.min(forward)), float(np.min(-reverse))) - 100.0 * span
    upper = max(float(np.max(forward)), float(np.max(-reverse))) + 100.0 * span
    if equation(lower) > 0.0 or equation(upper) < 0.0:
        raise RuntimeError("BAR root could not be bracketed")
    for _ in range(max(int(max_iterations), 1)):
        midpoint = 0.5 * (lower + upper)
        value = equation(midpoint)
        if abs(value) <= 1e-12 or upper - lower <= float(tolerance_kcal_mol):
            return float(midpoint)
        if value > 0.0:
            upper = midpoint
        else:
            lower = midpoint
    return float(0.5 * (lower + upper))


def static_alchemical_endpoint_proxy(
    protein_xyz: np.ndarray,
    ligand_xyz: np.ndarray,
    *,
    n_windows: int = 11,
    protein_elements: list[str] | None = None,
    ligand_elements: list[str] | None = None,
) -> dict[str, Any]:
    windows = fep_lambda_energies(
        protein_xyz,
        ligand_xyz,
        n_windows=n_windows,
        protein_elements=protein_elements,
        ligand_elements=ligand_elements,
    )
    endpoint_difference = (
        float(windows[-1]["e_total"] - windows[0]["e_total"])
        if len(windows) >= 2
        else 0.0
    )
    first = windows[0] if windows else {}
    return {
        "status": "blocked_static_alchemical_endpoint_proxy",
        "method": "fixed_coordinate_softcore_lj_endpoint_difference_v2",
        "n_windows": len(windows),
        "static_endpoint_score_proxy": endpoint_difference,
        "score_unit": "internal_proxy_unit",
        "is_fep": False,
        "is_binding_free_energy": False,
        "ensemble_sample_count": 0,
        "uncertainty_available": False,
        "claim_safe": False,
        "blocked_reason": "ensemble_sampling_and_thermodynamic_cycle_missing",
        "windows": windows,
        "element_model": str(first.get("element_model", "single_element_proxy")),
        "element_fallback_used": bool(first.get("element_fallback_used", True)),
        "protein_element_fallback_used": bool(first.get("protein_element_fallback_used", True)),
        "ligand_element_fallback_used": bool(first.get("ligand_element_fallback_used", True)),
        "protein_element_count": int(first.get("protein_element_count", 0)),
        "ligand_element_count": int(first.get("ligand_element_count", 0)),
        "claim_boundary": FEP_CLAIM_BOUNDARY,
    }


def estimate_binding_fep(
    protein_xyz: np.ndarray,
    ligand_xyz: np.ndarray,
    *,
    n_windows: int = 11,
    n_bootstrap: int = 8,
    protein_elements: list[str] | None = None,
    ligand_elements: list[str] | None = None,
) -> dict[str, Any]:
    """Deprecated compatibility API returning a blocked static endpoint proxy."""
    result = static_alchemical_endpoint_proxy(
        protein_xyz,
        ligand_xyz,
        n_windows=n_windows,
        protein_elements=protein_elements,
        ligand_elements=ligand_elements,
    )
    result["deprecated_api_alias"] = "estimate_binding_fep"
    result["requested_bootstrap_count_ignored"] = int(n_bootstrap)
    result["delta_g_fep_kcal_mol"] = None
    result["delta_g_fep_std_kcal_mol"] = None
    return result
