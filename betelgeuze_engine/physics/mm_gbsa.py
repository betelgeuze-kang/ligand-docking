"""MM-GBSA refine-tier binding energy proxy with claim-safe metadata."""

from __future__ import annotations

from typing import Any

import numpy as np

from core.refine_physics import (
    REFINE_TIER_CLAIM_BOUNDARY,
    cross_vdw_energy,
    gb_born_radius_estimate,
    gb_solvation_energy,
    sa_surface_energy,
)

REFINE_LIGAND_MODEL = "refine_gb_sa"
REFINE_STACK_CALIBRATION_STATUS = "internal_solvent_fep_proxy_uncalibrated"
REFINE_PROXY_BLOCKED_REASON = "internal_gb_sa_proxy_uncalibrated"
MM_GBSA_CLAIM_METADATA_SCHEMA_VERSION = "mm_gbsa_refine_claim_metadata_v1"


def _refine_claim_metadata() -> dict[str, Any]:
    return {
        "claim_metadata_schema_version": MM_GBSA_CLAIM_METADATA_SCHEMA_VERSION,
        "claim_safe": False,
        "blocked_reason": REFINE_PROXY_BLOCKED_REASON,
        "accuracy_claim_grade": "restricted_internal_proxy",
        "claim_boundary": REFINE_TIER_CLAIM_BOUNDARY,
        "calibration_status": REFINE_STACK_CALIBRATION_STATUS,
        "ligand_model": REFINE_LIGAND_MODEL,
    }


def mm_gbsa_binding_energy(
    protein_xyz: np.ndarray,
    ligand_xyz: np.ndarray,
    *,
    contact_cutoff_a: float = 8.0,
    props: dict[str, float] | None = None,
    ligand_charge_scale: float = 0.0,
) -> dict[str, Any]:
    """Compute refine-tier MM-GBSA proxy binding free energy (kcal/mol).

    Positive values indicate weaker binding (less favorable). This is an
    internal proxy and deliberately returns claim-safe blocking metadata.
    """
    props = dict(props or {})
    prot = np.asarray(protein_xyz, dtype=np.float32)
    lig = np.asarray(ligand_xyz, dtype=np.float32)
    claim_metadata = _refine_claim_metadata()
    if prot.size == 0 or lig.size == 0:
        return {
            "min_distance_a": 999.0,
            "contact_fraction": 0.0,
            "contact_count": 0.0,
            "close_contact_count": 0.0,
            "clash_count": 0.0,
            "deltaG_mm_gbsa_kcal_mol": 5.0,
            "deltaG_mmpbsa_proxy_kcal_mol": 5.0,
            "e_vdw": 0.0,
            "e_polar": 0.0,
            "e_nonpolar": 0.0,
            "e_gb": 0.0,
            "e_sa": 0.0,
            "e_solvation": 5.0,
            "ligand_model": REFINE_LIGAND_MODEL,
            "refine_tier": "gb_sa_v1",
            **claim_metadata,
            "claim_metadata": claim_metadata,
        }

    vdw = cross_vdw_energy(prot, lig, contact_cutoff_a=float(contact_cutoff_a))
    d = np.linalg.norm(prot[:, None, :] - lig[None, :, :], axis=2)
    min_d = float(vdw["min_distance_a"])
    denom = float(max(int(d.size), 1))
    contacts = float(vdw["contact_count"])
    close_contacts = float(np.sum(d < 4.5))
    ligand_atom_count = float(max(int(lig.shape[0]), 1))
    ligand_contact_atom_count = float(np.sum(np.any(d < float(contact_cutoff_a), axis=0)))
    contact_fraction = contacts / denom
    clashes = float(vdw["clash_count"])

    polar_n = float(props.get("polar_norm", 0.0))
    logp_n = float(props.get("logp_norm", 0.0))
    hb_contacts = float(np.sum(d < 3.5)) * (0.5 + 0.5 * polar_n)

    complex_coords = np.vstack([prot, lig])
    born = gb_born_radius_estimate(complex_coords)
    n_prot = prot.shape[0]
    q_prot = np.zeros(n_prot, dtype=np.float64)
    q_lig = np.full(lig.shape[0], float(ligand_charge_scale) * (0.1 + 0.2 * polar_n), dtype=np.float64)
    q_complex = np.concatenate([q_prot, q_lig])
    e_gb_complex = gb_solvation_energy(q_complex, born)
    e_gb_prot = gb_solvation_energy(q_prot, born[:n_prot])
    e_gb_lig = gb_solvation_energy(q_lig, born[n_prot:])
    e_gb_cross = e_gb_complex - e_gb_prot - e_gb_lig

    e_sa_complex = sa_surface_energy(complex_coords)
    e_sa_prot = sa_surface_energy(prot)
    e_sa_lig = sa_surface_energy(lig)
    e_sa_cross = e_sa_complex - e_sa_prot - e_sa_lig

    raw_vdw = float(vdw["e_vdw"])
    e_vdw = float(np.clip(0.02 * raw_vdw, -2.0, 2.0)) + 0.18 * clashes
    e_polar = -(0.04 + 0.08 * polar_n) * hb_contacts
    e_nonpolar = (
        -0.0020 * contacts
        -0.10 * ligand_atom_count
        -0.05 * max(0.0, logp_n) * ligand_contact_atom_count
    )
    e_gb = 0.05 * float(e_gb_cross)
    e_sa = 0.05 * float(e_sa_cross)
    e_solv = e_gb + e_sa + 0.12 * max(0.0, min_d - 4.0) + 0.35 * max(0.0, 0.20 - contact_fraction)
    delta_g = float(1.50 + e_vdw + e_polar + e_nonpolar + e_solv)

    return {
        "min_distance_a": min_d,
        "contact_fraction": float(contact_fraction),
        "contact_count": contacts,
        "ligand_contact_atom_count": ligand_contact_atom_count,
        "close_contact_count": close_contacts,
        "clash_count": clashes,
        "deltaG_mm_gbsa_kcal_mol": delta_g,
        "deltaG_mmpbsa_proxy_kcal_mol": delta_g,
        "e_vdw": float(e_vdw),
        "raw_e_vdw": raw_vdw,
        "e_polar": float(e_polar),
        "e_nonpolar": float(e_nonpolar),
        "e_gb": float(e_gb),
        "e_sa": float(e_sa),
        "e_solvation": float(e_solv),
        "ligand_model": REFINE_LIGAND_MODEL,
        "refine_tier": "gb_sa_v1",
        **claim_metadata,
        "claim_metadata": claim_metadata,
    }


def mm_gbsa_refinement_delta(
    *,
    base_proxy_kcal: float,
    mean_min_distance_a: float,
    contact_fraction: float,
    stability_score: float,
    protein_xyz: np.ndarray | None = None,
    ligand_xyz: np.ndarray | None = None,
    props: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Refinement adjustment when coords are available or proxy features only."""
    claim_metadata = _refine_claim_metadata()
    if protein_xyz is not None and ligand_xyz is not None:
        refined = mm_gbsa_binding_energy(protein_xyz, ligand_xyz, props=props or {})
        delta = float(refined["deltaG_mm_gbsa_kcal_mol"] - float(base_proxy_kcal))
        confidence = float(np.clip(1.0 / (1.0 + 0.25 * abs(delta) + 0.1 * refined["clash_count"]), 0.05, 0.99))
        return {
            "refined_energy_kcal_mol": float(refined["deltaG_mm_gbsa_kcal_mol"]),
            "refinement_delta_kcal_mol": float(max(delta, 0.05)),
            "confidence": confidence,
            "backend": "internal_gb_sa_v1",
            **claim_metadata,
            "claim_metadata": claim_metadata,
        }

    distance_penalty = max(0.0, float(mean_min_distance_a) - 2.60) * 0.90
    contact_penalty = max(0.0, 0.32 - float(contact_fraction)) * 8.00
    stability_penalty = max(0.0, 0.24 - float(stability_score)) * 5.50
    delta = float(np.clip(0.25 + distance_penalty + contact_penalty + stability_penalty, 0.05, 8.0))
    confidence = float(np.clip(1.0 / (1.0 + 0.40 * delta + 0.15 * contact_penalty), 0.05, 0.99))
    return {
        "refined_energy_kcal_mol": float(base_proxy_kcal) + delta,
        "refinement_delta_kcal_mol": delta,
        "confidence": confidence,
        "backend": "internal_gb_sa_v1_proxy",
        **claim_metadata,
        "claim_metadata": claim_metadata,
    }


def compute_full_refine_stack(
    protein_xyz: np.ndarray,
    ligand_xyz: np.ndarray,
    *,
    props: dict[str, float] | None = None,
    include_explicit: bool = True,
    include_fep: bool = True,
) -> dict[str, Any]:
    """Run GB/SA -> all-atom -> explicit shell -> FEP stack when coords available."""
    from core.allatom_forcefield import allatom_energy
    from core.explicit_solvent import explicit_solvation_energy
    from core.fep import estimate_binding_fep

    claim_metadata = _refine_claim_metadata()
    gb = mm_gbsa_binding_energy(protein_xyz, ligand_xyz, props=props or {})
    complex_coords = np.vstack([np.asarray(protein_xyz, dtype=np.float32), np.asarray(ligand_xyz, dtype=np.float32)])
    n_prot = int(np.asarray(protein_xyz).shape[0])
    elements = ["C"] * n_prot + ["C"] * int(np.asarray(ligand_xyz).shape[0])
    aa = allatom_energy(complex_coords, elements)
    out: dict[str, Any] = {
        "refine_stack": ["gb_sa", "allatom"],
        "gb_sa": gb,
        "allatom": aa,
        **claim_metadata,
        "claim_metadata": claim_metadata,
    }
    if include_explicit:
        explicit = explicit_solvation_energy(complex_coords, elements)
        out["explicit"] = explicit
        out["refine_stack"].append("explicit_tip3p_shell")
    if include_fep:
        fep = estimate_binding_fep(protein_xyz, ligand_xyz, n_windows=7, n_bootstrap=4)
        out["fep"] = fep
        out["refine_stack"].append("fep")
    return out


def refine_stack_calibration_report(
    refine_stack: dict[str, Any],
    *,
    public_solvent_pair_count: int = 0,
    public_fep_pair_count: int = 0,
    min_public_solvent_pairs: int = 5,
    min_public_fep_pairs: int = 5,
    public_benchmark_ready: bool = False,
) -> dict[str, Any]:
    """Report solvent/FEP calibration posture without opening an accuracy claim."""
    gb = refine_stack.get("gb_sa") if isinstance(refine_stack.get("gb_sa"), dict) else {}
    explicit = refine_stack.get("explicit") if isinstance(refine_stack.get("explicit"), dict) else {}
    fep = refine_stack.get("fep") if isinstance(refine_stack.get("fep"), dict) else {}

    def _finite_number(mapping: dict[str, Any], key: str) -> bool:
        try:
            return bool(np.isfinite(float(mapping.get(key))))
        except (TypeError, ValueError):
            return False

    gb_ready = _finite_number(gb, "deltaG_mm_gbsa_kcal_mol")
    explicit_ready = bool(explicit.get("refine_tier") == "explicit_tip3p_shell_v1" and _finite_number(explicit, "delta_e_total_kcal_mol"))
    fep_ready = bool(fep.get("status") == "fep_estimate_ready" and _finite_number(fep, "delta_g_fep_kcal_mol"))
    solvent_pairs = int(public_solvent_pair_count)
    fep_pairs = int(public_fep_pair_count)
    enough_solvent_pairs = solvent_pairs >= int(min_public_solvent_pairs)
    enough_fep_pairs = fep_pairs >= int(min_public_fep_pairs)
    claim_ready = False
    blockers: list[str] = []
    if not gb_ready:
        blockers.append("gb_sa_surface_not_ready")
    if not explicit_ready:
        blockers.append("explicit_solvent_surface_not_ready")
    if not fep_ready:
        blockers.append("fep_surface_not_ready")
    if not enough_solvent_pairs:
        blockers.append("insufficient_public_solvent_pairs")
    if not enough_fep_pairs:
        blockers.append("insufficient_public_fep_pairs")
    if not public_benchmark_ready:
        blockers.append("public_benchmark_gate_not_ready")
    blockers.append("explicit_solvent_md_sampling_not_validated")
    blockers.append("fep_holdout_calibration_not_validated")
    claim_metadata = _refine_claim_metadata()
    return {
        "status": "claim_grade_solvent_fep_calibration_ready" if claim_ready else "blocked_solvent_fep_calibration_claim",
        "calibration_status": REFINE_STACK_CALIBRATION_STATUS,
        "solvent_fep_surface_ready": bool(gb_ready and explicit_ready and fep_ready),
        "gb_sa_surface_ready": gb_ready,
        "explicit_solvent_surface_ready": explicit_ready,
        "fep_surface_ready": fep_ready,
        "claim_grade_solvent_fep_calibration_ready": claim_ready,
        "public_solvent_pair_count": solvent_pairs,
        "public_fep_pair_count": fep_pairs,
        "min_public_solvent_pairs": int(min_public_solvent_pairs),
        "min_public_fep_pairs": int(min_public_fep_pairs),
        "public_benchmark_ready": bool(public_benchmark_ready),
        "blockers": blockers,
        **claim_metadata,
        "claim_metadata": claim_metadata,
    }
