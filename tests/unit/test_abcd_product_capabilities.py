"""Unit tests for A/B/C/D product capability modules."""

from __future__ import annotations

import numpy as np

from betelgeuze_product.structure_analysis import analyze_structure_source
from core.mm_gbsa import REFINE_LIGAND_MODEL, mm_gbsa_binding_energy, mm_gbsa_refinement_delta
from core.pocket_detection import detect_binding_pocket
from core.pose_generation import cluster_poses_by_rmsd, generate_pose_ensemble
from core.refine_physics import cross_vdw_energy, lj_energy
from core.residual_features import build_residual_feature_vector, features_from_scoring_row
from core.score_calibration import apply_calibration, fit_linear_calibration
from core.score_residual import apply_score_residual
from core.structure_metrics import (
    dockq_proxy,
    evaluate_structure_quality,
    lddt_pli_proxy,
    molprobity_clashscore_proxy,
    parse_pdb_atoms_with_coords,
    tm_score_proxy,
)
from tools.run_ligand_backmapping_scoring import _frame_mmpbsa_proxy, _score_frames


def _sample_protein() -> np.ndarray:
    return np.asarray(
        [
            [0.0, 0.0, 0.0],
            [3.8, 0.0, 0.0],
            [7.6, 0.0, 0.0],
            [0.0, 3.8, 0.0],
            [3.8, 3.8, 0.0],
        ],
        dtype=np.float32,
    )


def _sample_ligand() -> np.ndarray:
    return np.asarray([[-1.0, 1.9, 0.5], [1.0, 2.1, 0.5]], dtype=np.float32)


def test_refine_physics_lj_and_vdw():
    e = lj_energy(np.asarray([3.5, 4.0, 5.0]), 3.5, 0.08)
    assert e.shape == (3,)
    assert float(e[1]) < 0.0
    vdw = cross_vdw_energy(_sample_protein(), _sample_ligand())
    assert vdw["contact_count"] > 0
    assert vdw["min_distance_a"] < 5.0


def test_mm_gbsa_binding_energy_refine_tier():
    out = mm_gbsa_binding_energy(_sample_protein(), _sample_ligand(), props={"polar_norm": 0.5, "logp_norm": 0.3})
    assert out["refine_tier"] == "gb_sa_v1"
    assert "e_gb" in out
    assert "e_sa" in out
    assert "ligand_contact_atom_count" in out
    assert out["claim_metadata_schema_version"] == "mm_gbsa_refine_claim_metadata_v1"
    assert out["claim_safe"] is False
    assert out["blocked_reason"] == "internal_gb_sa_proxy_uncalibrated"
    assert out["claim_metadata"]["claim_safe"] is False
    assert np.isfinite(out["deltaG_mm_gbsa_kcal_mol"])


def test_mm_gbsa_binding_energy_accepts_typed_elements_without_opening_claim():
    protein = _sample_protein()
    ligand = _sample_ligand()
    carbon_only = mm_gbsa_binding_energy(
        protein,
        ligand,
        protein_elements=["C"] * int(protein.shape[0]),
        ligand_elements=["C"] * int(ligand.shape[0]),
    )
    typed = mm_gbsa_binding_energy(
        protein,
        ligand,
        protein_elements=["N", "C", "O", "S", "C"],
        ligand_elements=["N", "O"],
    )

    assert typed["element_model"] == "typed_pairwise"
    assert typed["element_fallback_used"] is False
    assert typed["protein_element_count"] == int(protein.shape[0])
    assert typed["ligand_element_count"] == int(ligand.shape[0])
    assert typed["raw_e_vdw"] != carbon_only["raw_e_vdw"]
    assert typed["claim_safe"] is False
    assert typed["blocked_reason"] == "internal_gb_sa_proxy_uncalibrated"


def test_mm_gbsa_contact_normalized_score_prefers_contact_rich_pose():
    protein = _sample_protein()
    near_ligand = _sample_ligand()
    far_ligand = near_ligand + np.asarray([30.0, 0.0, 0.0], dtype=np.float32)

    near = mm_gbsa_binding_energy(protein, near_ligand)
    far = mm_gbsa_binding_energy(protein, far_ligand)

    assert near["contact_count"] > far["contact_count"]
    assert near["deltaG_mm_gbsa_kcal_mol"] < far["deltaG_mm_gbsa_kcal_mol"]


def test_backmapping_refine_gb_sa_model():
    out = _frame_mmpbsa_proxy(
        _sample_protein(),
        _sample_ligand(),
        props={"polar_norm": 0.4},
        contact_cutoff_A=8.0,
        ligand_model=REFINE_LIGAND_MODEL,
        smiles="NCO",
        protein_elements=["N", "C", "O", "S", "C"],
    )
    assert out["ligand_model"] == REFINE_LIGAND_MODEL
    assert "deltaG_mm_gbsa_kcal_mol" in out
    assert out["deltaG_mmpbsa_proxy_kcal_mol"] == out["deltaG_mm_gbsa_kcal_mol"]
    assert out["element_model"] == "typed_pairwise"
    assert out["ligand_element_source"] == "rdkit_atom_elements_projected_to_model_coords"


def test_backmapping_refine_score_frames_records_topology_element_sources():
    protein = _sample_protein()
    ligand = _sample_ligand()

    score = _score_frames(
        frame_paths=[],
        trajectory_npz_path="",
        protein_default=protein,
        ligand_default=ligand,
        contact_cutoff_A=8.0,
        row={"ligand_smiles": "NCO", "protein_sequence": "DCKST"},
        min_frames=1,
        ligand_model=REFINE_LIGAND_MODEL,
        hbond_onsps_weight=1.0,
    )

    assert score["refine_element_model"] == "typed_pairwise"
    assert score["refine_element_fallback_used"] is False
    assert score["refine_protein_element_source"] == "sequence_residue_element_proxy"
    assert score["refine_protein_element_sequence_mapped"] is True
    assert score["refine_ligand_element_source"] == "rdkit_atom_elements_projected_to_model_coords"
    assert score["refine_ligand_element_topology_valid"] is True


def test_pocket_detection_geometric_and_ligand_guided():
    prot = _sample_protein()
    lig = _sample_ligand()
    geo = detect_binding_pocket(prot)
    guided = detect_binding_pocket(prot, lig)
    assert geo["status"] == "pocket_ready"
    assert guided["method"] == "ligand_guided"
    assert guided["contact_atom_count"] >= 0


def test_pose_generation_and_clustering():
    pocket = np.asarray([1.0, 2.0, 0.0])
    ens = generate_pose_ensemble("CCO", pocket, n_starts=3, output_mode="2bead")
    assert ens["pose_count"] == 3
    clusters = cluster_poses_by_rmsd(ens["poses"], rmsd_cutoff_a=5.0)
    assert clusters["cluster_count"] >= 1


def test_score_calibration_fit_and_apply():
    fit = fit_linear_calibration([-8.0, -7.0, -6.0, -5.0], [-9.0, -8.0, -7.0, -6.0])
    assert fit["status"] == "calibration_ready"
    calibrated = apply_calibration(-7.5, fit)
    assert calibrated < -7.0


def test_residual_features_and_score_residual_refine_inputs():
    feats = build_residual_feature_vector(refine_tier_delta=0.5, mm_gbsa_delta=0.3, refine_confidence=0.8)
    assert feats["feature_dim"] == 11
    assert feats["refine_tier_present"] is True
    row_feats = features_from_scoring_row(
        {
            "binding_energy_mmpbsa_kcal_mol_proxy": -6.0,
            "binding_energy_explicit_water_recheck_kcal_mol_proxy": -5.5,
            "contact_fraction": 0.4,
        }
    )
    assert row_feats["refine_tier_present"] is True
    base = apply_score_residual(
        -6.0,
        family="gpcr",
        prior_pressure=0.2,
        refine_tier_delta=0.4,
        mm_gbsa_delta=0.2,
        refine_confidence=0.9,
        mode="assist",
    )
    shadow_no_refine = apply_score_residual(-6.0, family="gpcr", prior_pressure=0.2, mode="assist")
    assert base["active_score"] != shadow_no_refine["active_score"] or base["refine_tier_delta"] == 0.4


def test_structure_metrics_and_product_surface():
    pdb = "\n".join(
        [
            "ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  0.00           N",
            "ATOM      2  CA  ALA A   1       1.458   0.000   0.000  1.00  0.00           C",
            "ATOM      3  C   ALA A   1       2.009   1.421   0.000  1.00  0.00           C",
            "ATOM      4  O   ALA A   1       1.251   2.390   0.000  1.00  0.00           O",
            "ATOM      5  CA  GLY A   2       3.500   1.600   0.000  1.00  0.00           C",
            "ATOM      6  CA  GLY A   3       6.000   1.600   0.000  1.00  0.00           C",
        ]
    )
    atoms = parse_pdb_atoms_with_coords(pdb)
    quality = evaluate_structure_quality(atoms)
    assert quality["molprobity_clashscore"] is not None
    coords = np.stack([a["xyz"] for a in atoms], axis=0)
    ref = coords + np.asarray([0.1, 0.0, 0.0])
    assert lddt_pli_proxy(coords, ref) is not None
    assert tm_score_proxy(coords, ref) is not None
    assert dockq_proxy(coords, ref) is not None
    assert molprobity_clashscore_proxy(coords) >= 0.0

    product = analyze_structure_source({"pdb_content": pdb})
    assert product["status"] == "structure_analysis_ready"
    assert product["molprobity_clashscore"] is not None


def test_physics_refinement_gb_sa_delta_helper():
    adj = mm_gbsa_refinement_delta(
        base_proxy_kcal=-6.0,
        mean_min_distance_a=3.0,
        contact_fraction=0.35,
        stability_score=0.2,
        protein_xyz=_sample_protein(),
        ligand_xyz=_sample_ligand(),
    )
    assert adj["backend"] == "internal_gb_sa_v1"
    assert adj["refinement_delta_kcal_mol"] >= 0.05
