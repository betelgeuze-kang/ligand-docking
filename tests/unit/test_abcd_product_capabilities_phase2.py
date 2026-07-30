"""Phase-2 tests: all-atom, explicit, FEP, cross-docking, refine training, external metrics."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import torch

from betelgeuze_product.structure_analysis import analyze_structure_source
from core.allatom_forcefield import (
    allatom_energy,
    atom_typing_coverage_report,
    bonded_energy,
    dihedral_energy,
    equilibrium_bond_length,
    formal_charge_proxy_report,
    improper_energy,
    infer_atom_types,
    infer_bonds,
    infer_impropers,
    infer_torsions,
    ionizable_atom_typing_report,
    metal_cofactor_coordination_report,
    nonbonded_energy,
    parameter_calibration_report,
    partial_charges_from_atom_types,
)
from core.explicit_solvent import explicit_solvation_energy
from core.fep import estimate_binding_fep
from core.mm_gbsa import compute_full_refine_stack, refine_stack_calibration_report
from core.pose_generation import generate_cross_docking_poses, induced_fit_relax, sample_sidechain_rotamers
from core.structure_metrics import structure_quality_claim_guard_report
from core.structure_metrics_external import try_molprobity_clashscore
from tools import train_residual_production_score_model as train_mod
from tools.product.build_refine_tier_residual_training_dataset import enrich_refine_tier_labels


def _prot() -> np.ndarray:
    return np.asarray([[0, 0, 0], [3.8, 0, 0], [7.6, 0, 0], [0, 3.8, 0]], dtype=np.float32)


def _lig() -> np.ndarray:
    return np.asarray([[-1, 2, 0], [1, 2, 0]], dtype=np.float32)


def test_allatom_explicit_fep_stack():
    aa = allatom_energy(_prot(), ["C"] * 4)
    assert aa["bond_count"] >= 1
    assert aa["bond_model"] == "covalent_radii_equilibrium_with_coarse_trace_fallback"
    assert aa["parameterization_level"] == "internal_united_atom_typed_v1"
    assert aa["charge_model"] == "typed_partial_charge_neutralized_v1"
    assert aa["parameter_calibration_status"] == "internal_proxy_uncalibrated"
    assert aa["claim_grade_parameterization_ready"] is False
    assert aa["charge_parameter_source"] == "internal_atom_type_proxy_uncalibrated"
    assert aa["dihedral_model"] == "periodic_torsion_proxy_n3"
    assert aa["improper_model"] == "planarity_proxy_for_sp2_like_centers"
    ex = explicit_solvation_energy(_prot(), ["C"] * 4)
    assert ex["water_count"] >= 0
    fep = estimate_binding_fep(_prot(), _lig(), n_windows=5, n_bootstrap=2)
    assert fep["status"] == "fep_estimate_ready"
    stack = compute_full_refine_stack(_prot(), _lig(), include_explicit=True, include_fep=True)
    assert "gb_sa" in stack and "allatom" in stack and "fep" in stack
    calibration = refine_stack_calibration_report(
        stack,
        public_solvent_pair_count=4,
        public_fep_pair_count=4,
        min_public_solvent_pairs=5,
        min_public_fep_pairs=5,
    )
    assert calibration["status"] == "blocked_solvent_fep_calibration_claim"
    assert calibration["solvent_fep_surface_ready"] is True
    assert calibration["claim_grade_solvent_fep_calibration_ready"] is False
    assert "insufficient_public_solvent_pairs" in calibration["blockers"]
    assert "insufficient_public_fep_pairs" in calibration["blockers"]
    assert "explicit_solvent_md_sampling_not_validated" in calibration["blockers"]
    assert "fep_holdout_calibration_not_validated" in calibration["blockers"]


def test_refine_stack_and_fep_use_typed_elements_when_provided():
    protein = _prot()
    ligand = _lig()
    protein_elements = ["N", "C", "O", "S"]
    ligand_elements = ["N", "O"]

    fep = estimate_binding_fep(
        protein,
        ligand,
        n_windows=5,
        n_bootstrap=2,
        protein_elements=protein_elements,
        ligand_elements=ligand_elements,
    )
    carbon_fep = estimate_binding_fep(
        protein,
        ligand,
        n_windows=5,
        n_bootstrap=2,
        protein_elements=["C"] * int(protein.shape[0]),
        ligand_elements=["C"] * int(ligand.shape[0]),
    )
    assert fep["status"] == "fep_estimate_ready"
    assert fep["element_model"] == "typed_pairwise"
    assert fep["element_fallback_used"] is False
    assert fep["windows"][0]["e_cross"] != carbon_fep["windows"][0]["e_cross"]

    stack = compute_full_refine_stack(
        protein,
        ligand,
        include_explicit=True,
        include_fep=True,
        protein_elements=protein_elements,
        ligand_elements=ligand_elements,
    )
    assert stack["element_model"] == "typed_pairwise"
    assert stack["element_fallback_used"] is False
    assert stack["gb_sa"]["element_model"] == "typed_pairwise"
    assert stack["fep"]["element_model"] == "typed_pairwise"
    assert stack["allatom"]["atom_types"][0].startswith("N_")
    assert stack["allatom"]["atom_types"][-1].startswith("O_")
    assert stack["claim_safe"] is False
    assert stack["calibration_status"] == "internal_solvent_fep_proxy_uncalibrated"


def test_structure_quality_interface_proxy_is_reported_but_claim_blocked():
    atoms = [
        {"record": "ATOM", "atom_name": "CA", "resname": "ALA", "chain_id": "A", "residue_id": "1", "element": "C", "xyz": np.asarray([0.0, 0.0, 0.0])},
        {"record": "ATOM", "atom_name": "CA", "resname": "GLY", "chain_id": "A", "residue_id": "2", "element": "C", "xyz": np.asarray([3.8, 0.0, 0.0])},
        {"record": "ATOM", "atom_name": "CA", "resname": "SER", "chain_id": "A", "residue_id": "3", "element": "C", "xyz": np.asarray([7.6, 0.2, 0.0])},
        {"record": "ATOM", "atom_name": "CA", "resname": "THR", "chain_id": "A", "residue_id": "4", "element": "C", "xyz": np.asarray([11.4, 0.1, 0.0])},
        {"record": "HETATM", "atom_name": "C1", "resname": "LIG", "chain_id": "L", "residue_id": "1", "element": "C", "xyz": np.asarray([3.8, 3.2, 0.0])},
        {"record": "HETATM", "atom_name": "O1", "resname": "LIG", "chain_id": "L", "residue_id": "1", "element": "O", "xyz": np.asarray([5.0, 3.2, 0.0])},
    ]
    reference = [
        {**atom, "xyz": np.asarray(atom["xyz"], dtype=np.float64) + np.asarray([0.05, -0.02, 0.01])}
        for atom in atoms
    ]
    report = structure_quality_claim_guard_report(
        atoms,
        receptor_coords=np.asarray([atom["xyz"] for atom in atoms[:4]], dtype=np.float64),
        ligand_coords=np.asarray([atom["xyz"] for atom in atoms[4:]], dtype=np.float64),
        reference_atoms=reference,
        max_clashscore_proxy=200.0,
    )
    assert report["status"] == "blocked_structure_quality_claim"
    assert report["structure_quality_proxy_surface_ready"] is True
    assert report["claim_grade_structure_quality_ready"] is False
    assert report["clashscore_proxy_ready"] is True
    assert report["reference_metric_surface_ready"] is True
    assert report["interface"]["contact_count"] >= 1
    assert "external_molprobity_not_available" in report["blockers"]
    assert "external_openstructure_not_available" in report["blockers"]
    assert "native_complex_benchmark_not_ready" in report["blockers"]
    assert "structure_quality_proxy_not_external_parity" in report["blockers"]


def test_allatom_bonded_energy_uses_element_equilibrium_lengths():
    near_equilibrium = np.asarray([[0.0, 0.0, 0.0], [1.53, 0.0, 0.0]], dtype=np.float32)
    stretched = np.asarray([[0.0, 0.0, 0.0], [1.85, 0.0, 0.0]], dtype=np.float32)
    elements = ["C", "O"]
    assert infer_bonds(stretched, elements) == [(0, 1)]
    assert 1.40 <= equilibrium_bond_length("C", "O", 1.85) <= 1.65
    assert bonded_energy(stretched, [(0, 1)], elements=elements) > 10.0
    assert bonded_energy(near_equilibrium, [(0, 1)], elements=elements) < bonded_energy(
        stretched,
        [(0, 1)],
        elements=elements,
    )


def test_allatom_atom_types_charges_and_bonded_nonbonded_exclusions():
    coords = np.asarray(
        [
            [0.0, 0.0, 0.0],
            [1.25, 0.0, 0.0],
            [2.45, 0.0, 0.0],
            [3.75, 0.0, 0.0],
        ],
        dtype=np.float32,
    )
    elements = ["C", "O", "N", "H"]
    bonds = infer_bonds(coords, elements)
    atom_types = infer_atom_types(coords, elements, bonds=bonds)
    assert atom_types[0] == "C_CARBONYL"
    assert "O_" in atom_types[1]
    charges = partial_charges_from_atom_types(atom_types)
    assert abs(float(np.sum(charges))) < 1e-8
    assert float(charges[1]) < 0.0
    included = nonbonded_energy(coords, elements, atom_types=atom_types, charges=charges)
    excluded = nonbonded_energy(
        coords,
        elements,
        atom_types=atom_types,
        charges=charges,
        exclude_pairs={(min(i, j), max(i, j)) for i, j in bonds},
    )
    assert included["e_nonbonded"] != excluded["e_nonbonded"]
    aa = allatom_energy(coords, elements)
    assert aa["nonbonded_exclusions"] == "1-2_bonded_pairs"
    assert aa["atom_types"] == atom_types
    assert abs(float(aa["net_charge_e"])) < 1e-8


def test_allatom_atom_typing_coverage_reports_halogen_and_unknown_boundaries():
    coords = np.asarray(
        [[float(idx) * 1.5, 0.0, 0.0] for idx in range(10)],
        dtype=np.float32,
    )
    elements = ["H", "C", "N", "O", "S", "P", "F", "Cl", "Br", "I"]
    report = atom_typing_coverage_report(coords, elements, bonds=[])
    assert report["status"] == "atom_typing_coverage_ready"
    assert report["default_atom_count"] == 0
    assert report["coverage_fraction"] == 1.0
    assert report["atom_type_counts"]["CL_HALOGEN"] == 1
    assert report["atom_type_counts"]["BR_HALOGEN"] == 1
    assert report["charge_neutralization_ok"] is True

    blocked = atom_typing_coverage_report(coords[:2], ["C", "Zn"], bonds=[])
    assert blocked["status"] == "blocked_atom_typing_coverage"
    assert blocked["default_atom_count"] == 1
    assert blocked["unsupported_elements"] == ["ZN"]
    assert blocked["unsupported_metal_or_cofactor_elements"] == ["ZN"]
    assert blocked["unsupported_metal_or_cofactor_count"] == 1

    aa_blocked = allatom_energy(coords[:2], ["C", "Zn"])
    assert aa_blocked["atom_typing_coverage_status"] == "blocked_atom_typing_coverage"
    assert aa_blocked["default_atom_count"] == 1
    assert aa_blocked["unsupported_metal_or_cofactor_elements"] == ["ZN"]


def test_allatom_metal_cofactor_coordination_is_reported_but_claim_blocked():
    coords = np.asarray(
        [
            [0.0, 0.0, 0.0],
            [2.0, 0.0, 0.0],
            [0.0, 2.1, 0.0],
            [0.0, 0.0, 2.2],
            [4.5, 0.0, 0.0],
        ],
        dtype=np.float32,
    )
    elements = ["Zn", "N", "O", "S", "C"]

    report = metal_cofactor_coordination_report(coords, elements)
    assert report["status"] == "blocked_metal_cofactor_parameterization"
    assert report["metal_cofactor_coordination_surface_ready"] is True
    assert report["claim_grade_metal_cofactor_parameterization_ready"] is False
    assert report["metal_count"] == 1
    assert report["metal_elements"] == ["ZN"]
    assert report["coordination_site_count"] == 1
    assert report["coordination_donor_count"] == 3
    assert report["coordination_rows"][0]["donor_count"] == 3
    assert "metal_cofactor_parameter_source_missing" in report["blockers"]
    assert "metal_cofactor_parameterization_not_supported" in report["blockers"]

    aa = allatom_energy(coords, elements)
    assert aa["atom_typing_coverage_status"] == "blocked_atom_typing_coverage"
    assert aa["metal_cofactor_coordination_status"] == "blocked_metal_cofactor_parameterization"
    assert aa["metal_cofactor_coordination_surface_ready"] is True
    assert aa["metal_cofactor_coordination_site_count"] == 1
    assert aa["metal_cofactor_coordination_donor_count"] == 3
    assert aa["claim_grade_metal_cofactor_parameterization_ready"] is False


def test_allatom_ionizable_charged_residue_typing_is_reported_but_claim_blocked():
    coords = np.asarray([[float(idx) * 1.4, 0.0, 0.0] for idx in range(12)], dtype=np.float32)
    elements = ["C", "O", "O", "C", "N", "H", "H", "H", "P", "O", "O", "S"]
    bonds = [
        (0, 1),
        (0, 2),
        (0, 3),
        (3, 4),
        (4, 5),
        (4, 6),
        (4, 7),
        (8, 9),
        (8, 10),
        (3, 11),
    ]

    atom_types = infer_atom_types(coords, elements, bonds=bonds)
    assert atom_types[0] == "C_CARBOXYLATE"
    assert atom_types[1:3] == ["O_CARBOXYLATE", "O_CARBOXYLATE"]
    assert atom_types[4] == "N_CATIONIC"
    assert atom_types[9:11] == ["O_PHOSPHATE", "O_PHOSPHATE"]
    assert atom_types[11] == "S_THIOLATE"

    report = ionizable_atom_typing_report(coords, elements, bonds=bonds)
    assert report["status"] == "ionizable_atom_typing_surface_ready"
    assert report["ionizable_atom_typing_surface_ready"] is True
    assert report["claim_grade_charged_parameterization_ready"] is False
    assert report["ionizable_atom_count"] == 7
    assert report["ionizable_atom_type_counts"]["C_CARBOXYLATE"] == 1
    assert report["ionizable_atom_type_counts"]["O_CARBOXYLATE"] == 2
    assert report["ionizable_atom_type_counts"]["N_CATIONIC"] == 1
    assert report["ionizable_atom_type_counts"]["O_PHOSPHATE"] == 2
    assert report["ionizable_atom_type_counts"]["S_THIOLATE"] == 1
    assert "charged_residue_parameter_calibration_not_ready" in report["blockers"]

    formal = formal_charge_proxy_report(coords, elements, bonds=bonds)
    assert formal["status"] == "blocked_formal_charge_proxy"
    assert formal["formal_charge_proxy_ready"] is True
    assert formal["claim_grade_formal_charge_ready"] is False
    assert formal["formal_charge_proxy_atom_count"] == 7
    assert formal["formal_charge_proxy_net_e"] == -2.0
    assert "protonation_source_missing" in formal["blockers"]
    assert "formal_charge_proxy_not_calibrated" in formal["blockers"]

    aa = allatom_energy(coords, elements, bonds=bonds, charges=partial_charges_from_atom_types(atom_types), cutoff_a=6.0)
    assert aa["ionizable_atom_typing_status"] == "ionizable_atom_typing_surface_ready"
    assert aa["ionizable_atom_count"] == 7
    assert aa["claim_grade_charged_parameterization_ready"] is False
    assert aa["formal_charge_proxy_status"] == "blocked_formal_charge_proxy"
    assert aa["formal_charge_proxy_net_e"] == -2.0
    assert aa["claim_grade_formal_charge_ready"] is False


def test_allatom_parameter_calibration_claim_guard_is_fail_closed():
    blocked = parameter_calibration_report(public_benchmark_pair_count=4, min_public_benchmark_pairs=5)
    assert blocked["status"] == "blocked_parameter_calibration_claim"
    assert blocked["claim_grade_parameterization_ready"] is False
    assert blocked["parameter_calibration_status"] == "internal_proxy_uncalibrated"
    assert "insufficient_public_benchmark_pairs" in blocked["blockers"]
    assert "public_benchmark_gate_not_ready" in blocked["blockers"]

    ready = parameter_calibration_report(
        public_benchmark_pair_count=5,
        min_public_benchmark_pairs=5,
        public_benchmark_ready=True,
    )
    assert ready["status"] == "claim_grade_parameterization_ready"
    assert ready["claim_grade_parameterization_ready"] is True


def test_allatom_dihedral_and_improper_terms_are_active():
    planar_chain = np.asarray(
        [[0.0, 0.0, 0.0], [1.54, 0.0, 0.0], [2.54, 1.0, 0.0], [3.54, 1.0, 0.0]],
        dtype=np.float32,
    )
    twisted_chain = np.asarray(
        [[0.0, 0.0, 0.0], [1.54, 0.0, 0.0], [2.54, 1.0, 0.0], [3.54, 1.0, 0.8]],
        dtype=np.float32,
    )
    chain_bonds = infer_bonds(planar_chain, ["C", "C", "C", "C"])
    torsions = infer_torsions(chain_bonds)
    assert torsions == [(0, 1, 2, 3)]
    assert dihedral_energy(planar_chain, torsions) != dihedral_energy(twisted_chain, torsions)

    planar_center = np.asarray(
        [[0.0, 0.0, 0.0], [1.25, 0.0, 0.0], [0.0, 1.25, 0.0], [-1.0, -1.0, 0.0]],
        dtype=np.float32,
    )
    out_of_plane_center = planar_center.copy()
    out_of_plane_center[0, 2] = 0.4
    elements = ["C", "O", "N", "H"]
    improper_bonds = infer_bonds(planar_center, elements)
    atom_types = infer_atom_types(planar_center, elements, bonds=improper_bonds)
    impropers = infer_impropers(improper_bonds, atom_types)
    assert impropers == [(0, 1, 2, 3)]
    assert improper_energy(out_of_plane_center, impropers) > improper_energy(planar_center, impropers)
    aa = allatom_energy(out_of_plane_center, elements)
    assert aa["torsion_count"] >= 0
    assert aa["improper_count"] == 1


def test_cross_docking_and_induced_fit():
    cross = generate_cross_docking_poses("CCO", _prot(), n_starts=2, induced_fit=True)
    assert cross["mode"] == "cross_docking"
    assert cross["pose_count"] == 2
    fit = induced_fit_relax(_prot(), _lig())
    assert fit["status"] == "induced_fit_relaxed"
    atoms = [
        {"chain_id": "A", "resname": "SER", "residue_id": "10", "xyz": np.asarray([0, 0, 0])},
        {"chain_id": "A", "resname": "ASP", "residue_id": "11", "xyz": np.asarray([3.8, 0, 0])},
    ]
    rot = sample_sidechain_rotamers(atoms)
    assert len(rot) >= 2


def test_refine_tier_training_enrichment_and_model_features(tmp_path: Path):
    dataset = tmp_path / "dataset.csv"
    stage3 = tmp_path / "stage3.csv"
    enriched = tmp_path / "enriched.csv"
    dataset.write_text(
        "target,family,ligand_id,is_binder,role,reference_binding_kcal_mol,raw_score,score_col,delta_score,corrected_score,mean_min_distance_A,source_csv,label_source\n"
        "ADRB2,gpcr,lig1,1,fit,-9.0,-8.0,binding_score_composite_v7,-1.0,-9.0,3.0,fixture,fixture\n"
        "ADRB2,gpcr,lig2,0,fit,-2.0,-1.0,binding_score_composite_v7,-1.0,-2.0,3.5,fixture,fixture\n",
        encoding="utf-8",
    )
    stage3.write_text(
        "target,ligand_id,binding_energy_mmpbsa_kcal_mol_proxy,deltaG_mm_gbsa_kcal_mol,physics_refinement_confidence\n"
        "ADRB2,lig1,-6.0,-5.2,0.85\n"
        "ADRB2,lig2,-1.0,-0.5,0.55\n",
        encoding="utf-8",
    )
    summary = enrich_refine_tier_labels(input_csv=dataset, stage3_csv=stage3, out_csv=enriched)
    assert summary["refine_tier_label_rows"] == 2

    # pad dataset for training minimum rows
    rows = enriched.read_text(encoding="utf-8").strip().splitlines()
    header = rows[0]
    body = rows[1:]
    padded = tmp_path / "padded.csv"
    padded.write_text(header + "\n" + "\n".join(body * 20) + "\n", encoding="utf-8")
    checkpoint = tmp_path / "model.pt"
    train_summary = train_mod.train_residual_production_score_model(
        input_csv=str(padded),
        out_checkpoint=str(checkpoint),
        epochs=1,
        hidden_dim=16,
        batch_size=8,
        device_name="cpu",
    )
    assert "refine_confidence" in train_summary["feature_names"] or "mm_gbsa_delta" in train_summary["feature_names"]
    assert checkpoint.exists()


def test_refine_tier_enrichment_merges_multiple_stage3_sources(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.csv"
    stage3_a = tmp_path / "a_refine.csv"
    stage3_b = tmp_path / "b_refine.csv"
    enriched = tmp_path / "enriched.csv"
    dataset.write_text(
        "target,family,ligand_id,is_binder,role,reference_binding_kcal_mol,raw_score,score_col,delta_score,corrected_score,mean_min_distance_A,source_csv,label_source\n"
        "T1,gpcr,lig1,1,fit,-9.0,-8.0,binding_score_composite_v7,-1.0,-9.0,3.0,fixture,fixture\n"
        "T2,gpcr,lig2,0,fit,-2.0,-1.0,binding_score_composite_v7,-1.0,-2.0,3.5,fixture,fixture\n",
        encoding="utf-8",
    )
    stage3_a.write_text(
        "target,ligand_id,binding_energy_mmpbsa_kcal_mol_proxy,deltaG_mm_gbsa_kcal_mol,physics_refinement_confidence\n"
        "T1,lig1,-6.0,-5.0,0.8\n",
        encoding="utf-8",
    )
    stage3_b.write_text(
        "target,ligand_id,binding_energy_mmpbsa_kcal_mol_proxy,deltaG_mm_gbsa_kcal_mol,physics_refinement_confidence\n"
        "T2,lig2,-1.0,-0.4,0.6\n",
        encoding="utf-8",
    )
    summary = enrich_refine_tier_labels(
        input_csv=dataset,
        stage3_glob=str(tmp_path / "*_refine.csv"),
        out_csv=enriched,
    )
    assert summary["stage3_source_count"] == 2
    assert summary["refine_tier_label_rows"] == 2


def test_refine_tier_enrichment_normalizes_product_gate_decoy_ids(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.csv"
    stage3 = tmp_path / "refine.csv"
    enriched = tmp_path / "enriched.csv"
    dataset.write_text(
        "target,family,ligand_id,is_binder,role,reference_binding_kcal_mol,raw_score,score_col,delta_score,corrected_score,mean_min_distance_A,source_csv,label_source\n"
        "ADRB2_GPCR_BLIND,gpcr,decoy_ADRB2_GPCR_BLIND_0144,0,fit,-2.0,-1.0,binding_score_composite_v7,-1.0,-2.0,3.5,fixture,fixture\n",
        encoding="utf-8",
    )
    stage3.write_text(
        "target,ligand_id,binding_energy_mmpbsa_kcal_mol_proxy,deltaG_mm_gbsa_kcal_mol,physics_refinement_confidence\n"
        "ADRB2_GPCR_BLIND,product_gate_decoy_0144,-1.0,-0.4,0.6\n",
        encoding="utf-8",
    )
    summary = enrich_refine_tier_labels(
        input_csv=dataset,
        stage3_csv=stage3,
        out_csv=enriched,
    )
    assert summary["refine_tier_label_rows"] == 1
    rows = list(csv.DictReader(enriched.open(encoding="utf-8")))
    assert rows[0]["refine_tier_join_method"] == "target_ligand_id_normalized"


def test_refine_tier_enrichment_joins_by_queue_id(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.csv"
    stage3 = tmp_path / "refine.csv"
    enriched = tmp_path / "enriched.csv"
    dataset.write_text(
        "target,family,ligand_id,queue_id,is_binder,role,reference_binding_kcal_mol,raw_score,score_col,delta_score,corrected_score,mean_min_distance_A,source_csv,label_source\n"
        "HIV1_PROTEASE,protease,legacy_alias,HIV1_PROTEASE__rep0022__imatinib,1,fit,-9.0,-8.0,binding_score_composite_v7,-1.0,-9.0,3.0,fixture,fixture\n",
        encoding="utf-8",
    )
    stage3.write_text(
        "target,ligand_id,queue_id,binding_energy_mmpbsa_kcal_mol_proxy,deltaG_mm_gbsa_kcal_mol,physics_refinement_confidence\n"
        "HIV1_PROTEASE,imatinib,HIV1_PROTEASE__rep0022__imatinib,-6.0,-5.0,0.8\n",
        encoding="utf-8",
    )
    summary = enrich_refine_tier_labels(
        input_csv=dataset,
        stage3_csv=stage3,
        out_csv=enriched,
    )
    assert summary["refine_tier_label_rows"] == 1
    assert summary["refine_tier_join_methods"]["queue_id"] == 1


def test_external_metric_adapter_falls_back_to_proxy():
    pdb = "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00  0.00           C\n"
    clash = try_molprobity_clashscore(pdb)
    assert clash["source"] == "internal_proxy"
    assert clash["value"] is not None
    product = analyze_structure_source({"pdb_content": pdb})
    assert product["molprobity_clashscore_source"] == "internal_proxy"


def test_physics_refinement_full_stack_backend(tmp_path: Path):
    from betelgeuze_engine.product.selection_score_authority import SelectionScoreAuthority
    from tools.run_ligand_physics_refinement import build_parser, run_refinement

    scores = tmp_path / "stage3.csv"
    scores.write_text(
        "target,family,ligand_id,binding_energy_mmpbsa_kcal_mol_proxy,binding_score_composite_v7,mean_min_distance_A,contact_fraction,stability_score\n"
        + "\n".join(
            f"ADRB2,gpcr,lig{i},{-6.0 + 0.01 * i},{-7.0 + 0.01 * i},{3.0 + 0.02 * i},0.3,0.2"
            for i in range(20)
        )
        + "\n",
        encoding="utf-8",
    )
    authority_summary = tmp_path / "stage3_summary.json"
    authority_summary.write_text(
        json.dumps(
            {
                "selection_score_authority": SelectionScoreAuthority.create(
                    score_column="binding_score_composite_v7",
                    score_direction="ascending",
                ).to_dict()
            }
        ),
        encoding="utf-8",
    )
    out_csv = tmp_path / "out.csv"
    args = build_parser().parse_args(
        [
            "--scores-csv",
            str(scores),
            "--selection-authority-summary-json",
            str(authority_summary),
            "--score-col",
            "binding_score_composite_v7",
            "--backend",
            "internal_full_stack_v1",
            "--topk-global",
            "8",
            "--admission-rank-threshold-pct",
            "1.0",
            "--out-csv",
            str(out_csv),
        ]
    )
    summary = run_refinement(args)
    assert summary["pass"] is True
    assert summary["selected_count"] == 8
    assert out_csv.exists()


def test_cross_docking_pose_seed_rotation_diversifies_initial_pose():
    from tools.generate_ligand_trajectory_engine import _compose_ligand_xyz

    row = {
        "pocket_x": 5.0,
        "pocket_y": 0.0,
        "pocket_z": 0.0,
        "ligand_bead0_x": -0.8,
        "ligand_bead0_y": 0.0,
        "ligand_bead0_z": 0.0,
        "ligand_bead1_x": 0.8,
        "ligand_bead1_y": 0.0,
        "ligand_bead1_z": 0.0,
    }
    base = _compose_ligand_xyz(row, cross_docking_angle_rad=0.0)
    rotated = _compose_ligand_xyz(row, cross_docking_angle_rad=float(np.pi) / 2.0)
    # default angle preserves legacy behavior
    assert np.allclose(base, np.asarray([[4.2, 0.0, 0.0], [5.8, 0.0, 0.0]], dtype=np.float32))
    # rotation moves beads off the x-axis but keeps pocket center
    assert not np.allclose(base, rotated)
    assert np.allclose(rotated.mean(axis=0), base.mean(axis=0), atol=1e-5)


def test_docking_request_pose_generation_contract_surface():
    from betelgeuze_product.docking_request import build_docking_job_record

    pdb_lines = []
    for i in range(12):
        x = (i % 4) * 3.8
        y = (i // 4) * 3.8
        pdb_lines.append(
            f"ATOM  {i + 1:5d}  CA  ALA A{i + 1:4d}    {x:8.3f}{y:8.3f}{0.0:8.3f}  1.00  0.00           C"
        )
    pdb = "\n".join(pdb_lines) + "\n"
    record = build_docking_job_record(
        {
            "request_type": "structure_analysis_ligand_docking",
            "family": "gpcr",
            "target_id": "ADRB2",
            "pdb_content": pdb,
            "ligands": [{"ligand_id": "lig_1", "smiles": "CCO"}],
        },
        job_id="job_pose",
    )
    assert "pose_generation_contract" in record
    assert record["pose_generation_contract"]["execution_enabled"] is False
    assert record["execution_enabled"] is False
    node = next(n for n in record["ai_decision_graph_trace"] if n["node_id"] == "pose_generation_contract")
    assert "pose_generation_modes" in node["evidence"]
