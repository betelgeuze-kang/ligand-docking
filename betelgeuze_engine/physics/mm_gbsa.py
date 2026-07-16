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
REFINE_STACK_CALIBRATION_STATUS = "blocked_interaction_proxy_stack_uncalibrated_v2"
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


def _element_metadata(
    protein_elements: list[str],
    ligand_elements: list[str],
    protein_fallback: bool,
    ligand_fallback: bool,
) -> dict[str, Any]:
    fallback_used = bool(protein_fallback or ligand_fallback)
    return {
        "element_model": "single_element_proxy" if fallback_used else "typed_pairwise",
        "element_fallback_used": fallback_used,
        "protein_element_fallback_used": bool(protein_fallback),
        "ligand_element_fallback_used": bool(ligand_fallback),
        "protein_element_count": int(len(protein_elements)),
        "ligand_element_count": int(len(ligand_elements)),
    }


def mm_gbsa_binding_energy(
    protein_xyz: np.ndarray,
    ligand_xyz: np.ndarray,
    *,
    contact_cutoff_a: float = 8.0,
    props: dict[str, float] | None = None,
    ligand_charge_scale: float = 0.0,
    protein_elements: list[str] | None = None,
    ligand_elements: list[str] | None = None,
    protein_charges: np.ndarray | None = None,
    ligand_charges: np.ndarray | None = None,
) -> dict[str, Any]:
    """Compute a claim-blocked GB/SA interaction score, not binding free energy."""
    props = dict(props or {})
    prot = np.asarray(protein_xyz, dtype=np.float32)
    lig = np.asarray(ligand_xyz, dtype=np.float32)
    protein_element_list, protein_fallback = _normalized_elements(protein_elements, int(prot.shape[0]))
    ligand_element_list, ligand_fallback = _normalized_elements(ligand_elements, int(lig.shape[0]))
    element_meta = _element_metadata(protein_element_list, ligand_element_list, protein_fallback, ligand_fallback)
    claim_metadata = _refine_claim_metadata()
    if prot.size == 0 or lig.size == 0:
        return {
            "min_distance_a": 999.0,
            "contact_fraction": 0.0,
            "contact_count": 0.0,
            "close_contact_count": 0.0,
            "clash_count": 0.0,
            "interaction_score_proxy": 0.0,
            "deltaG_mm_gbsa_kcal_mol": 0.0,
            "deltaG_mmpbsa_proxy_kcal_mol": 0.0,
            "e_vdw": 0.0,
            "e_polar": 0.0,
            "e_nonpolar": 0.0,
            "e_gb": 0.0,
            "e_sa": 0.0,
            "e_solvation": 0.0,
            "score_unit": "internal_proxy_unit",
            "is_free_energy": False,
            "legacy_energy_field_deprecated": True,
            "ligand_model": REFINE_LIGAND_MODEL,
            "refine_tier": "interaction_gb_sa_proxy_v2",
            **element_meta,
            **claim_metadata,
            "claim_metadata": claim_metadata,
        }

    vdw = cross_vdw_energy(
        prot,
        lig,
        protein_elements=protein_element_list,
        ligand_elements=ligand_element_list,
        contact_cutoff_a=float(contact_cutoff_a),
    )
    d = np.linalg.norm(prot[:, None, :] - lig[None, :, :], axis=2)
    min_d = float(vdw["min_distance_a"])
    contacts = float(vdw["contact_count"])
    close_contacts = float(np.sum(d < 4.5))
    ligand_atom_count = float(max(int(lig.shape[0]), 1))
    ligand_contact_atom_count = float(np.sum(np.any(d < float(contact_cutoff_a), axis=0)))
    contact_fraction = ligand_contact_atom_count / ligand_atom_count
    clashes = float(vdw["clash_count"])

    complex_coords = np.vstack([prot, lig])
    n_prot = prot.shape[0]
    q_prot = (
        np.asarray(protein_charges, dtype=np.float64).reshape(-1)
        if protein_charges is not None
        else np.zeros(n_prot, dtype=np.float64)
    )
    q_lig = (
        np.asarray(ligand_charges, dtype=np.float64).reshape(-1)
        if ligand_charges is not None
        else np.full(lig.shape[0], float(ligand_charge_scale), dtype=np.float64)
    )
    if q_prot.size != n_prot or q_lig.size != lig.shape[0]:
        raise ValueError("protein_charges and ligand_charges must match coordinate counts")
    q_complex = np.concatenate([q_prot, q_lig])
    born_complex = gb_born_radius_estimate(complex_coords)
    born_prot = gb_born_radius_estimate(prot)
    born_lig = gb_born_radius_estimate(lig)
    e_gb_complex = gb_solvation_energy(q_complex, born_complex, coords=complex_coords)
    e_gb_prot = gb_solvation_energy(q_prot, born_prot, coords=prot)
    e_gb_lig = gb_solvation_energy(q_lig, born_lig, coords=lig)
    e_gb_cross = e_gb_complex - e_gb_prot - e_gb_lig

    e_sa_complex = sa_surface_energy(
        complex_coords,
        elements=protein_element_list + ligand_element_list,
    )
    e_sa_prot = sa_surface_energy(prot, elements=protein_element_list)
    e_sa_lig = sa_surface_energy(lig, elements=ligand_element_list)
    e_sa_cross = e_sa_complex - e_sa_prot - e_sa_lig

    raw_vdw = float(vdw["e_vdw"])
    e_vdw = raw_vdw
    e_gb = float(e_gb_cross)
    e_sa = float(e_sa_cross)
    e_solv = e_gb + e_sa
    interaction_score = float(e_vdw + e_solv)
    electrostatics_available = bool(
        protein_charges is not None and ligand_charges is not None
    )

    return {
        "min_distance_a": min_d,
        "contact_fraction": float(contact_fraction),
        "contact_count": contacts,
        "ligand_contact_atom_count": ligand_contact_atom_count,
        "close_contact_count": close_contacts,
        "clash_count": clashes,
        "interaction_score_proxy": interaction_score,
        # Compatibility aliases for existing internal datasets. They are
        # explicitly non-claim fields and must not be presented as ΔG.
        "deltaG_mm_gbsa_kcal_mol": interaction_score,
        "deltaG_mmpbsa_proxy_kcal_mol": interaction_score,
        "e_vdw": float(e_vdw),
        "raw_e_vdw": raw_vdw,
        "e_polar": 0.0,
        "e_nonpolar": float(e_sa),
        "e_gb": float(e_gb),
        "e_sa": float(e_sa),
        "e_solvation": float(e_solv),
        "electrostatics_available": electrostatics_available,
        "score_unit": "internal_proxy_unit",
        "is_free_energy": False,
        "legacy_energy_field_deprecated": True,
        "method": "topology_limited_gb_sa_interaction_proxy_v2",
        "ligand_model": REFINE_LIGAND_MODEL,
        "refine_tier": "interaction_gb_sa_proxy_v2",
        **element_meta,
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
    protein_elements: list[str] | None = None,
    ligand_elements: list[str] | None = None,
) -> dict[str, Any]:
    """Refinement adjustment when coords are available or proxy features only."""
    claim_metadata = _refine_claim_metadata()
    if protein_xyz is not None and ligand_xyz is not None:
        refined = mm_gbsa_binding_energy(
            protein_xyz,
            ligand_xyz,
            props=props or {},
            protein_elements=protein_elements,
            ligand_elements=ligand_elements,
        )
        delta = float(refined["deltaG_mm_gbsa_kcal_mol"] - float(base_proxy_kcal))
        confidence = float(np.clip(1.0 / (1.0 + 0.25 * abs(delta) + 0.1 * refined["clash_count"]), 0.05, 0.99))
        return {
            "refined_energy_kcal_mol": float(refined["deltaG_mm_gbsa_kcal_mol"]),
            "refinement_delta_kcal_mol": float(delta),
            "confidence": confidence,
            "backend": "interaction_gb_sa_proxy_v2",
            "is_free_energy": False,
            "element_model": refined.get("element_model", "single_element_proxy"),
            "element_fallback_used": bool(refined.get("element_fallback_used", True)),
            "protein_element_fallback_used": bool(refined.get("protein_element_fallback_used", True)),
            "ligand_element_fallback_used": bool(refined.get("ligand_element_fallback_used", True)),
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
        "backend": "feature_penalty_proxy_v1",
        "is_free_energy": False,
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
    protein_elements: list[str] | None = None,
    ligand_elements: list[str] | None = None,
) -> dict[str, Any]:
    """Run GB/SA -> all-atom -> explicit shell -> FEP stack when coords available."""
    from core.allatom_forcefield import allatom_energy
    from core.explicit_solvent import fixed_oxygen_shell_interaction_score
    from core.fep import estimate_binding_fep

    claim_metadata = _refine_claim_metadata()
    prot = np.asarray(protein_xyz, dtype=np.float32)
    lig = np.asarray(ligand_xyz, dtype=np.float32)
    protein_element_list, protein_fallback = _normalized_elements(protein_elements, int(prot.shape[0]))
    ligand_element_list, ligand_fallback = _normalized_elements(ligand_elements, int(lig.shape[0]))
    element_meta = _element_metadata(protein_element_list, ligand_element_list, protein_fallback, ligand_fallback)
    gb = mm_gbsa_binding_energy(
        protein_xyz,
        ligand_xyz,
        props=props or {},
        protein_elements=protein_element_list,
        ligand_elements=ligand_element_list,
    )
    complex_coords = np.vstack([prot, lig])
    elements = protein_element_list + ligand_element_list
    fragment_ids = [0] * int(prot.shape[0]) + [1] * int(lig.shape[0])
    aa_complex = allatom_energy(complex_coords, elements, fragment_ids=fragment_ids)
    aa_protein = allatom_energy(prot, protein_element_list, fragment_ids=[0] * int(prot.shape[0]))
    aa_ligand = allatom_energy(lig, ligand_element_list, fragment_ids=[1] * int(lig.shape[0]))
    aa = {
        "method": "fragment_separated_energy_difference_v2",
        "is_binding_free_energy": False,
        "complex": aa_complex,
        "protein": aa_protein,
        "ligand": aa_ligand,
        "interaction_energy_proxy": float(
            aa_complex["e_total"] - aa_protein["e_total"] - aa_ligand["e_total"]
        ),
        "cross_fragment_bond_count": 0,
        "atom_types": list(aa_complex.get("atom_types", [])),
        "net_charge_e": float(aa_complex.get("net_charge_e", 0.0)),
        "e_total": float(aa_complex.get("e_total", 0.0)),
    }
    out: dict[str, Any] = {
        "refine_stack": ["interaction_gb_sa_proxy", "fragment_separated_allatom_proxy"],
        "gb_sa": gb,
        "allatom": aa,
        **element_meta,
        **claim_metadata,
        "claim_metadata": claim_metadata,
    }
    if include_explicit:
        explicit_complex = fixed_oxygen_shell_interaction_score(complex_coords, elements)
        explicit_protein = fixed_oxygen_shell_interaction_score(prot, protein_element_list)
        explicit_ligand = fixed_oxygen_shell_interaction_score(lig, ligand_element_list)
        explicit = {
            "status": "fixed_oxygen_shell_interaction_proxy_ready",
            "is_explicit_solvent_md": False,
            "complex": explicit_complex,
            "protein": explicit_protein,
            "ligand": explicit_ligand,
            "interaction_solvation_score_proxy": float(
                explicit_complex["solvation_score_proxy"]
                - explicit_protein["solvation_score_proxy"]
                - explicit_ligand["solvation_score_proxy"]
            ),
        }
        out["explicit"] = explicit
        out["refine_stack"].append("fixed_oxygen_shell_proxy")
    if include_fep:
        fep = estimate_binding_fep(
            protein_xyz,
            ligand_xyz,
            n_windows=7,
            n_bootstrap=4,
            protein_elements=protein_element_list,
            ligand_elements=ligand_element_list,
        )
        out["fep"] = fep
        out["refine_stack"].append("blocked_static_alchemical_endpoint_proxy")
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
    def _finite_number(mapping: dict[str, Any], key: str) -> bool:
        try:
            return bool(np.isfinite(float(mapping.get(key))))
        except (TypeError, ValueError):
            return False

    gb_ready = bool(gb.get("is_free_energy") is False and _finite_number(gb, "interaction_score_proxy"))
    explicit_ready = bool(
        explicit.get("status") == "fixed_oxygen_shell_interaction_proxy_ready"
        and _finite_number(explicit, "interaction_solvation_score_proxy")
    )
    fep_ready = False
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
