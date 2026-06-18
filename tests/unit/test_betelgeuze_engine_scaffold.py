from __future__ import annotations

import numpy as np
import pytest
import torch

from betelgeuze_engine.contracts import EngineState, TermResult
from betelgeuze_engine.interactions.hbond_evidence import evaluate_hbond_evidence
from betelgeuze_engine.backmapping.onsps import (
    ONSPS_BACKMAP_SCHEMA_VERSION,
    backmap_4bead_onsps,
    evaluate_onsps_backmap_evidence,
)
from betelgeuze_engine.physics.terms import (
    DirectionalHBondTerm,
    HydrophobicContactTerm,
    LegacyLJTerm,
    ScreenedElectrostaticsTerm,
)
from betelgeuze_engine.physics import ProductForceField, default_force_term_registry, guarded_force_term_registry
from betelgeuze_engine.topology import (
    ComplexTopology,
    ProteinTopology,
    TopologyFactoryFacade,
    ligand_topology_from_smiles,
    protein_topology_from_sequence,
    topology_claim_metadata,
)
from betelgeuze_engine.validation import finite_difference_force_error, rotation_equivariance_error


def test_engine_terms_return_energy_forces_and_diagnostics() -> None:
    coords = torch.tensor([[[0.0, 0.0, 0.0], [3.0, 0.0, 0.0], [5.0, 0.0, 0.0]]])
    state = EngineState(
        coords=coords,
        atom_types=torch.tensor([0, 1, 2]),
        metadata={
            "hbond_roles": ["donor", "acceptor", "none"],
            "hydrophobic_mask": torch.tensor([False, True, True]),
            "topology_fidelity": "sequence_mapped",
            "ligand_topology_valid": True,
            "hbond_evidence_status": "pass",
            "claim_safe": True,
            "blocked_reason": "",
        },
    )

    for term in (LegacyLJTerm(sigma=1.0), DirectionalHBondTerm(), HydrophobicContactTerm()):
        result = term.energy_forces(state)
        assert isinstance(result, TermResult)
        assert result.energy.shape == (1,)
        assert result.forces.shape == coords.shape
        assert result.diagnostics["term"] == term.name
        assert result.diagnostics["status"] == "pass"
        assert result.claim_metadata["claim_safe"] is True
        assert result.claim_metadata["blocked_reason"] == ""
        assert result.claim_metadata["force_term_name"] == term.name
        assert result.claim_metadata["force_term_status"] == "pass"
        assert result.claim_metadata["topology_fidelity"] == "sequence_mapped"
        assert result.claim_metadata["ligand_topology_valid"] is True
        assert result.claim_metadata["hbond_evidence_status"] == "pass"
        if term.name == "directional_hbond":
            assert result.claim_metadata["hbond_evidence_schema_version"] == "hbond_evidence_v1"
            assert result.claim_metadata["hbond_evidence_schema_ready"] is True
        assert result.claim_metadata["force_residual_applied"] is False
        assert torch.isfinite(result.energy).all()
        assert torch.isfinite(result.forces).all()


def test_force_terms_fail_closed_with_scoped_claim_metadata_for_missing_inputs() -> None:
    state = EngineState(
        coords=torch.zeros(1, 2, 3),
        atom_types=torch.tensor([0, 1]),
        metadata={
            "topology_fidelity": "sequence_mapped",
            "ligand_topology_valid": True,
            "claim_safe": True,
            "blocked_reason": "",
        },
    )

    hbond = DirectionalHBondTerm().energy_forces(state)
    hydrophobic = HydrophobicContactTerm().energy_forces(state)

    assert hbond.claim_metadata["claim_safe"] is False
    assert hbond.claim_metadata["force_term_name"] == "directional_hbond"
    assert hbond.claim_metadata["force_term_status"] == "roles_missing"
    assert hbond.claim_metadata["blocked_reason"] == "hbond_roles_missing"
    assert hbond.claim_metadata["hbond_evidence_status"] == "roles_missing"
    assert hydrophobic.claim_metadata["claim_safe"] is False
    assert hydrophobic.claim_metadata["force_term_name"] == "hydrophobic_contact"
    assert hydrophobic.claim_metadata["force_term_status"] == "mask_missing"
    assert hydrophobic.claim_metadata["blocked_reason"] == "hydrophobic_mask_missing"


def test_legacy_lj_force_matches_finite_difference() -> None:
    term = LegacyLJTerm(sigma=1.0, epsilon=0.5)
    base = torch.tensor([[[0.0, 0.0, 0.0], [4.0, 0.0, 0.0]]], dtype=torch.float64)
    state = EngineState(coords=base, atom_types=torch.tensor([0, 0]))
    observed = term.energy_forces(state).forces[0, 0, 0].item()
    eps = 1e-4
    plus = base.clone()
    minus = base.clone()
    plus[0, 0, 0] += eps
    minus[0, 0, 0] -= eps
    e_plus = term.energy_forces(EngineState(coords=plus, atom_types=torch.tensor([0, 0]))).energy.item()
    e_minus = term.energy_forces(EngineState(coords=minus, atom_types=torch.tensor([0, 0]))).energy.item()
    finite_difference_force = -((e_plus - e_minus) / (2.0 * eps))

    assert observed == pytest.approx(finite_difference_force, rel=1e-3, abs=1e-6)


def test_legacy_lj_translation_invariance() -> None:
    term = LegacyLJTerm(sigma=1.0, epsilon=0.5)
    coords = torch.tensor([[[0.0, 0.0, 0.0], [4.0, 0.0, 0.0], [0.0, 4.0, 0.0]]])
    shift = torch.tensor([[[10.0, -3.0, 2.0]]])
    atom_types = torch.tensor([0, 0, 0])

    a = term.energy_forces(EngineState(coords=coords, atom_types=atom_types))
    b = term.energy_forces(EngineState(coords=coords + shift, atom_types=atom_types))

    assert a.energy == pytest.approx(b.energy)
    assert torch.allclose(a.forces, b.forces, atol=1e-6)


def test_legacy_lj_rotation_equivariance() -> None:
    term = LegacyLJTerm(sigma=1.0, epsilon=0.5)
    state = EngineState(
        coords=torch.tensor([[[0.0, 0.0, 0.0], [4.0, 0.0, 0.0], [0.0, 4.0, 0.0]]], dtype=torch.float64),
        atom_types=torch.tensor([0, 0, 0]),
    )
    rotation = torch.tensor(
        [
            [0.0, -1.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=torch.float64,
    )

    assert rotation_equivariance_error(term, state, rotation) < 1e-9


def test_product_forcefield_plugin_registry_aggregates_terms_and_claim_metadata() -> None:
    registry = default_force_term_registry()
    assert registry.names() == ["directional_hbond", "hydrophobic_contact", "legacy_lj"]
    forcefield = ProductForceField.from_registry(
        registry,
        names=["legacy_lj", "directional_hbond", "hydrophobic_contact"],
    )
    coords = torch.tensor([[[0.0, 0.0, 0.0], [3.0, 0.0, 0.0], [5.0, 0.0, 0.0]]])
    state = EngineState(
        coords=coords,
        atom_types=torch.tensor([0, 1, 2]),
        metadata={
            "hbond_roles": ["donor", "acceptor", "none"],
            "hydrophobic_mask": torch.tensor([False, True, True]),
        },
    )

    result = forcefield.energy_forces(
        state,
        claim_metadata={
            "topology_fidelity": "sequence_mapped",
            "ligand_topology_valid": True,
            "claim_safe": True,
            "blocked_reason": "",
        },
    )

    assert result.energy.shape == (1,)
    assert result.forces.shape == coords.shape
    assert set(result.terms) == {"legacy_lj", "directional_hbond", "hydrophobic_contact"}
    assert result.diagnostics["term_count"] == 3
    assert result.claim_metadata["claim_safe"] is True
    assert result.claim_metadata["topology_fidelity"] == "sequence_mapped"
    assert result.claim_metadata["ligand_topology_valid"] is True
    assert result.claim_metadata["hbond_evidence_status"] == "pass"
    assert result.claim_metadata["hbond_evidence_schema_version"] == "hbond_evidence_v1"
    assert result.claim_metadata["hbond_evidence_schema_ready"] is True
    assert result.claim_metadata["force_term_plugin_count"] == 3
    assert result.claim_metadata["force_term_claim_metadata_ready"] is True
    assert result.claim_metadata["force_term_claim_metadata_schema_version"] == "force_term_claim_metadata_v1"
    assert result.claim_metadata["force_term_claim_safe_count"] == 3
    assert result.claim_metadata["force_term_blocked_count"] == 0
    assert {
        row["force_term_name"]
        for row in result.claim_metadata["force_term_claim_rows"]
    } == {"legacy_lj", "directional_hbond", "hydrophobic_contact"}
    assert all(row["claim_safe"] is True for row in result.claim_metadata["force_term_claim_rows"])
    assert all(row["blocked_reason"] == "" for row in result.claim_metadata["force_term_claim_rows"])
    assert any(
        row["force_term_name"] == "directional_hbond"
        and row["hbond_evidence_schema_version"] == "hbond_evidence_v1"
        and row["hbond_evidence_schema_ready"] is True
        for row in result.claim_metadata["force_term_claim_rows"]
    )
    for term_name, diagnostics in result.diagnostics["term_diagnostics"].items():
        term_metadata = diagnostics["claim_metadata"]
        assert term_metadata["claim_safe"] is True
        assert term_metadata["blocked_reason"] == ""
        assert term_metadata["force_term_name"] == term_name
        assert term_metadata["force_term_status"] == "pass"
        assert term_metadata["topology_fidelity"] == "sequence_mapped"
        assert term_metadata["ligand_topology_valid"] is True


def test_guarded_force_term_registry_exposes_screened_electrostatics_opt_in() -> None:
    default_registry = default_force_term_registry()
    guarded_registry = guarded_force_term_registry()

    assert default_registry.names() == ["directional_hbond", "hydrophobic_contact", "legacy_lj"]
    assert guarded_registry.names() == [
        "directional_hbond",
        "hydrophobic_contact",
        "legacy_lj",
        "screened_electrostatics",
    ]
    assert isinstance(guarded_registry.create(["screened_electrostatics"])[0], ScreenedElectrostaticsTerm)


def test_screened_electrostatics_term_is_guarded_and_claim_scoped() -> None:
    term = ScreenedElectrostaticsTerm(scale=2.0, debye_kappa=0.15)
    coords = torch.tensor([[[0.0, 0.0, 0.0], [4.0, 0.0, 0.0], [0.0, 5.0, 0.0]]], dtype=torch.float64)
    state = EngineState(
        coords=coords,
        atom_types=torch.tensor([0, 1, 2]),
        metadata={
            "partial_charges": torch.tensor([1.0, -1.0, 0.5], dtype=torch.float64),
            "charge_source": "unit_test_validated_proxy",
            "charge_model_valid": True,
            "topology_fidelity": "sequence_mapped",
            "ligand_topology_valid": True,
            "hbond_evidence_status": "pass",
            "claim_safe": True,
            "blocked_reason": "",
        },
    )

    result = term.energy_forces(state)

    assert isinstance(result, TermResult)
    assert result.energy.shape == (1,)
    assert result.forces.shape == coords.shape
    assert torch.isfinite(result.energy).all()
    assert torch.isfinite(result.forces).all()
    assert result.diagnostics["term"] == "screened_electrostatics"
    assert result.diagnostics["status"] == "pass"
    assert result.diagnostics["active_pair_count"] == 3
    assert result.claim_metadata["claim_safe"] is True
    assert result.claim_metadata["blocked_reason"] == ""
    assert result.claim_metadata["force_term_name"] == "screened_electrostatics"
    assert result.claim_metadata["force_term_status"] == "pass"
    assert result.claim_metadata["force_term_charge_model_valid"] is True
    assert finite_difference_force_error(term, state, atom_index=0, coord_index=0) < 1e-5

    missing = term.energy_forces(
        EngineState(
            coords=coords,
            atom_types=torch.tensor([0, 1, 2]),
            metadata={"claim_safe": True, "blocked_reason": ""},
        )
    )
    assert missing.claim_metadata["claim_safe"] is False
    assert missing.claim_metadata["force_term_status"] == "charges_missing"
    assert missing.claim_metadata["blocked_reason"] == "screened_electrostatics_charges_missing"
    assert torch.allclose(missing.energy, torch.zeros_like(missing.energy))
    assert torch.allclose(missing.forces, torch.zeros_like(missing.forces))

    unvalidated = term.energy_forces(
        EngineState(
            coords=coords,
            atom_types=torch.tensor([0, 1, 2]),
            metadata={
                "partial_charges": torch.tensor([1.0, -1.0, 0.5], dtype=torch.float64),
                "claim_safe": True,
                "blocked_reason": "",
            },
        )
    )
    assert unvalidated.claim_metadata["claim_safe"] is False
    assert unvalidated.claim_metadata["force_term_status"] == "charge_model_unvalidated"
    assert unvalidated.claim_metadata["blocked_reason"] == "screened_electrostatics_charge_model_unvalidated"


def test_product_forcefield_can_execute_guarded_screened_electrostatics_plugin() -> None:
    forcefield = ProductForceField.from_registry(
        guarded_force_term_registry(),
        names=["screened_electrostatics"],
    )
    coords = torch.tensor([[[0.0, 0.0, 0.0], [4.0, 0.0, 0.0]]], dtype=torch.float64)
    state = EngineState(
        coords=coords,
        atom_types=torch.tensor([0, 1]),
        metadata={
            "partial_charges": torch.tensor([1.0, -1.0], dtype=torch.float64),
            "charge_source": "unit_test_validated_proxy",
            "charge_model_valid": True,
        },
    )

    result = forcefield.energy_forces(
        state,
        claim_metadata={
            "topology_fidelity": "sequence_mapped",
            "ligand_topology_valid": True,
            "hbond_evidence_status": "pass",
            "claim_safe": True,
            "blocked_reason": "",
        },
    )

    assert result.energy.shape == (1,)
    assert result.forces.shape == coords.shape
    assert result.claim_metadata["claim_safe"] is True
    assert result.claim_metadata["force_term_plugins"] == ["screened_electrostatics"]
    assert result.claim_metadata["force_term_claim_metadata_ready"] is True
    assert result.diagnostics["term_diagnostics"]["screened_electrostatics"]["status"] == "pass"


def test_product_forcefield_plugin_registry_blocks_missing_metadata_or_bad_term_status() -> None:
    forcefield = ProductForceField.from_registry(names=["directional_hbond"])
    state = EngineState(
        coords=torch.zeros(1, 2, 3),
        atom_types=torch.tensor([0, 1]),
        metadata={},
    )

    result = forcefield.energy_forces(
        state,
        claim_metadata={
            "topology_fidelity": "sequence_mapped",
            "ligand_topology_valid": True,
            "claim_safe": True,
            "blocked_reason": "",
        },
    )

    assert result.claim_metadata["claim_safe"] is False
    assert result.claim_metadata["force_term_claim_metadata_ready"] is True
    assert "directional_hbond:roles_missing" in result.claim_metadata["blocked_reason"]
    assert "hbond_roles_missing" in result.claim_metadata["blocked_reason"]
    term_metadata = result.diagnostics["term_diagnostics"]["directional_hbond"]["claim_metadata"]
    assert term_metadata["force_term_status"] == "roles_missing"
    assert term_metadata["blocked_reason"] == "hbond_roles_missing"
    assert term_metadata["hbond_evidence_schema_version"] == "hbond_evidence_v1"
    assert term_metadata["hbond_evidence_schema_ready"] is False


def test_hbond_evidence_uses_onsps_roles_distance_and_angle() -> None:
    two_bead = np.asarray([[0.0, 0.0, 0.0], [1.6, 0.0, 0.0]], dtype=np.float32)
    mapped, meta = backmap_4bead_onsps(two_bead, "CCO")
    if meta.get("mapping_source") != "rdkit_etkdg":
        pytest.skip("RDKit ONSPS evidence is required for claim-safe 2-bead H-bond geometry")
    protein = mapped + np.asarray([[0.0, 0.0, 3.0]], dtype=np.float32)
    pocket_center = mapped.mean(axis=0) + np.asarray([0.0, 0.0, 6.0], dtype=np.float32)

    evidence = evaluate_hbond_evidence(
        smiles="CCO",
        protein_xyz=protein,
        ligand_xyz=two_bead,
        pocket_center=pocket_center,
    )

    assert evidence.site_count >= 1
    assert evidence.donor_site_count + evidence.acceptor_site_count == evidence.site_count
    assert evidence.distance_pass_count >= 1
    assert evidence.angle_pass_count >= 1
    assert evidence.distance_pass_fraction > 0.0
    assert evidence.angle_pass_fraction > 0.0
    assert evidence.geometry_evaluated is True
    assert evidence.geometry_complete is True
    assert evidence.donor_acceptor_pairs[0]["role"] in {"donor", "acceptor"}
    assert evidence.hbond_confidence > 0.0
    assert evidence.schema_version == "hbond_evidence_v1"
    assert evidence.claim_safe is True
    assert evidence.abstention_reason == ""
    assert evidence.blocked_reason == ""
    assert evidence.thresholds["claim_safe_confidence_min"] == 0.5
    assert evidence.onsps_backmap_metadata["schema_version"] == ONSPS_BACKMAP_SCHEMA_VERSION
    assert evidence.onsps_backmap_metadata["backmap_status"] == "ok"
    assert evidence.onsps_backmap_metadata["mapping_source"] == "rdkit_etkdg"
    assert evidence.onsps_backmap_metadata["claim_safe"] is True
    assert (
        evidence.onsps_backmap_metadata["role_counts"]["donor"]
        + evidence.onsps_backmap_metadata["role_counts"]["acceptor"]
    ) >= 1


def test_onsps_backmap_evidence_schema_and_fail_closed_geometry() -> None:
    from betelgeuze_engine.backmapping import ONSPS_BACKMAP_SCHEMA_VERSION as exported_schema

    assert exported_schema == ONSPS_BACKMAP_SCHEMA_VERSION
    two_bead = np.asarray([[0.0, 0.0, 0.0], [1.6, 0.0, 0.0]], dtype=np.float32)
    evidence = evaluate_onsps_backmap_evidence(two_bead, "CCO")

    assert evidence.schema_version == ONSPS_BACKMAP_SCHEMA_VERSION
    assert evidence.backmap_status == "ok"
    assert evidence.site_count >= 1
    assert evidence.mapped_site_count == evidence.site_count
    assert evidence.input_bead_count == 2
    assert evidence.output_shape[1] == 3
    assert evidence.role_counts["donor"] + evidence.role_counts["acceptor"] >= 1
    if evidence.mapping_source == "rdkit_etkdg":
        assert evidence.claim_safe is True
        assert evidence.blocked_reason == ""
    else:
        assert evidence.claim_safe is False
        assert evidence.blocked_reason == "onsps_fallback_not_claim_safe"

    invalid = evaluate_onsps_backmap_evidence(np.asarray([[0.0, 0.0, 0.0]], dtype=np.float32), "CCO")
    assert invalid.schema_version == ONSPS_BACKMAP_SCHEMA_VERSION
    assert invalid.claim_safe is False
    assert invalid.backmap_status == "empty_input"
    assert invalid.blocked_reason == "invalid_two_bead_geometry"
    assert invalid.abstention_reason == "invalid_two_bead_geometry"

    no_sites = evaluate_onsps_backmap_evidence(two_bead, "CCCC")
    assert no_sites.schema_version == ONSPS_BACKMAP_SCHEMA_VERSION
    assert no_sites.claim_safe is False
    assert no_sites.backmap_status == "no_onsps_sites"
    assert no_sites.blocked_reason == "no_onsps_sites"
    assert no_sites.site_count == 0


def test_hbond_evidence_fail_closed_schema_for_invalid_or_missing_anchor() -> None:
    invalid = evaluate_hbond_evidence(smiles="C1(")
    assert invalid.claim_safe is False
    assert invalid.status == "invalid_smiles"
    assert invalid.abstention_reason == "invalid_smiles"
    assert invalid.blocked_reason == "invalid_smiles"
    assert invalid.schema_version == "hbond_evidence_v1"
    assert invalid.donor_site_count == 0
    assert invalid.acceptor_site_count == 0
    assert invalid.distance_pass_count == 0
    assert invalid.angle_pass_count == 0
    assert invalid.geometry_evaluated is False
    assert invalid.geometry_complete is False
    assert invalid.onsps_backmap_metadata["schema_version"] == ONSPS_BACKMAP_SCHEMA_VERSION
    assert invalid.onsps_backmap_metadata["backmap_status"] == "invalid_smiles"
    assert invalid.onsps_backmap_metadata["claim_safe"] is False
    assert invalid.onsps_backmap_metadata["blocked_reason"] == "invalid_smiles"

    missing = evaluate_hbond_evidence(
        smiles="CCO",
        protein_xyz=np.asarray([[0.0, 0.0, 0.0]], dtype=np.float32),
        ligand_xyz=np.asarray([[8.0, 0.0, 0.0], [9.0, 0.0, 0.0]], dtype=np.float32),
    )
    assert missing.claim_safe is False
    assert missing.abstention_reason == "missing_expected_anchor"
    assert missing.geometry_evaluated is True
    assert missing.geometry_complete is True
    assert missing.distance_pass_count == 0

    no_pose_geometry = evaluate_hbond_evidence(smiles="CCO")
    assert no_pose_geometry.claim_safe is False
    assert no_pose_geometry.abstention_reason == "pose_geometry_missing"
    assert no_pose_geometry.geometry_evaluated is False
    assert no_pose_geometry.geometry_complete is False
    assert no_pose_geometry.onsps_backmap_metadata["schema_version"] == ONSPS_BACKMAP_SCHEMA_VERSION
    assert no_pose_geometry.onsps_backmap_metadata["backmap_status"] == "not_evaluated"
    assert no_pose_geometry.onsps_backmap_metadata["claim_safe"] is False
    assert no_pose_geometry.onsps_backmap_metadata["blocked_reason"] == "ligand_geometry_missing"


def test_hbond_evidence_rejects_overanchored_decoy_contact() -> None:
    two_bead = np.asarray([[0.0, 0.0, 0.0], [1.6, 0.0, 0.0]], dtype=np.float32)
    mapped, meta = backmap_4bead_onsps(two_bead, "CC(=O)N")
    if meta.get("mapping_source") != "rdkit_etkdg":
        pytest.skip("RDKit ONSPS evidence is required for overanchored decoy fixture")

    evidence = evaluate_hbond_evidence(
        smiles="CC(=O)N",
        protein_xyz=mapped,
        ligand_xyz=two_bead,
    )

    assert evidence.claim_safe is False
    assert evidence.overanchoring_flag is True
    assert evidence.blocked_reason == "overanchored_decoy"
    assert evidence.abstention_reason == "overanchored_decoy"
    assert evidence.geometry_evaluated is True
    assert evidence.geometry_complete is True
    assert evidence.thresholds["overanchor_distance"] == 2.1
    assert evidence.onsps_backmap_metadata["schema_version"] == ONSPS_BACKMAP_SCHEMA_VERSION
    assert evidence.onsps_backmap_metadata["claim_safe"] is True


def test_topology_claim_metadata_blocks_placeholder_and_invalid_ligand() -> None:
    protein = protein_topology_from_sequence("", n_res=3)
    ligand = ligand_topology_from_smiles("")
    complex_topology = ComplexTopology(
        protein=protein,
        ligand=ligand,
        pocket_residue_indices=[],
        claim_scope="unit-test",
    )

    metadata = topology_claim_metadata(complex_topology)

    assert metadata["topology_fidelity"] == "placeholder_alanine"
    assert metadata["ligand_topology_valid"] is False
    assert metadata["claim_safe"] is False
    assert metadata["blocked_reason"] in {"empty_smiles", "ligand_topology_invalid"}


def test_topology_claim_metadata_carries_ligand_product_validity_status() -> None:
    protein = protein_topology_from_sequence("ACD", n_res=3)
    ligand = ligand_topology_from_smiles("C[C@H](O)C(=O)O")
    complex_topology = ComplexTopology(
        protein=protein,
        ligand=ligand,
        pocket_residue_indices=[1, 2],
        claim_scope="unit-test",
    )

    metadata = topology_claim_metadata(complex_topology)

    if ligand.validity.get("source") != "rdkit":
        pytest.skip("RDKit topology validity is required for claim-safe ligand metadata")
    assert metadata["claim_safe"] is True
    assert metadata["blocked_reason"] == ""
    assert metadata["topology_fidelity"] == "sequence_mapped"
    assert metadata["ligand_topology_valid"] is True
    assert metadata["ligand_topology_claim_safe"] is True
    assert metadata["ligand_topology_schema_version"] == "ligand_topology_validity_v1"
    assert metadata["ligand_topology_source"] == "rdkit"
    assert metadata["ligand_atom_count"] == 6
    assert metadata["ligand_hbond_site_count"] >= 1
    assert metadata["ligand_chiral_center_count"] == 1
    assert metadata["ligand_specified_chiral_center_count"] == 1
    assert metadata["ligand_unassigned_chiral_center_count"] == 0
    assert metadata["ligand_chirality_status"] == "specified"
    assert metadata["ligand_chirality_valid"] is True
    assert metadata["ligand_ring_status"] == "not_applicable"
    assert metadata["ligand_ring_valid"] is True
    assert metadata["ligand_protonation_status"] == "neutral_state_parsed"
    assert metadata["ligand_protonation_valid"] is True
    assert metadata["ligand_tautomer_status"] == "connectivity_parsed_tautomer_not_canonicalized"
    assert metadata["ligand_tautomer_valid"] is True
    assert metadata["ligand_validity_blockers"] == []


def test_topology_claim_metadata_blocks_unassigned_ligand_chirality() -> None:
    protein = protein_topology_from_sequence("ACD", n_res=3)
    ligand = ligand_topology_from_smiles("CC(O)C(=O)O")
    complex_topology = ComplexTopology(
        protein=protein,
        ligand=ligand,
        pocket_residue_indices=[1, 2],
        claim_scope="unit-test",
    )

    metadata = topology_claim_metadata(complex_topology)

    if ligand.validity.get("source") != "rdkit":
        pytest.skip("RDKit topology validity is required for chirality blocker metadata")
    assert ligand.validity["valid"] is True
    assert ligand.validity["claim_safe"] is False
    assert metadata["claim_safe"] is False
    assert metadata["ligand_topology_valid"] is True
    assert metadata["ligand_topology_claim_safe"] is False
    assert metadata["ligand_topology_schema_version"] == "ligand_topology_validity_v1"
    assert metadata["ligand_unassigned_chiral_center_count"] == 1
    assert metadata["ligand_chirality_status"] == "unassigned_chiral_centers"
    assert metadata["ligand_chirality_valid"] is False
    assert "unassigned_ligand_chirality" in metadata["blocked_reason"]
    assert "unassigned_ligand_chirality" in metadata["ligand_validity_blockers"]


def test_engine_topology_factory_facade_builds_claim_metadata() -> None:
    factory = TopologyFactoryFacade(device="cpu", default_claim_scope="unit_test")
    result = factory.from_sequence_and_smiles(
        sequence="ACD",
        smiles="C[C@H](O)C(=O)O",
        pocket_residue_indices=[1, 2],
    )

    assert isinstance(result.complex_topology, ComplexTopology)
    assert result.complex_topology.protein.fidelity == "sequence_mapped"
    assert result.complex_topology.claim_scope == "unit_test"
    assert result.complex_topology.pocket_residue_indices == [1, 2]
    if result.claim_metadata.get("ligand_topology_source") != "rdkit":
        pytest.skip("RDKit topology validity is required for claim-safe ligand metadata")
    assert result.claim_metadata["topology_fidelity"] == "sequence_mapped"
    assert result.claim_metadata["ligand_topology_valid"] is True
    assert result.claim_metadata["ligand_topology_claim_safe"] is True
    assert result.claim_metadata["ligand_topology_schema_version"] == "ligand_topology_validity_v1"
    assert result.claim_metadata["claim_safe"] is True
    assert result.claim_metadata["blocked_reason"] == ""


def test_engine_topology_factory_facade_blocks_placeholder_or_ligand_invalidity() -> None:
    factory = TopologyFactoryFacade(device="cpu")
    placeholder = factory.from_sequence_and_smiles(
        sequence="",
        smiles="C[C@H](O)C(=O)O",
        n_res=3,
    )
    if placeholder.claim_metadata.get("ligand_topology_source") != "rdkit":
        pytest.skip("RDKit topology validity is required for topology factory blocker metadata")
    assert placeholder.claim_metadata["topology_fidelity"] == "placeholder_alanine"
    assert placeholder.claim_metadata["ligand_topology_valid"] is True
    assert placeholder.claim_metadata["claim_safe"] is False
    assert placeholder.claim_metadata["blocked_reason"] == "placeholder_alanine_topology"

    invalid_ligand = factory.from_sequence_and_smiles(
        sequence="ACD",
        smiles="C1(",
    )
    assert invalid_ligand.claim_metadata["topology_fidelity"] == "sequence_mapped"
    assert invalid_ligand.claim_metadata["ligand_topology_valid"] is False
    assert invalid_ligand.claim_metadata["claim_safe"] is False
    assert invalid_ligand.claim_metadata["blocked_reason"] == "invalid_smiles"


def test_core_topology_factory_facades_engine_protein_topology() -> None:
    from core.definitions import StrategyType
    from core.topology import TopologyFactory

    topo = TopologyFactory(
        n_res=3,
        t_type=1,
        box_size=[10.0, 10.0, 10.0],
        device="cpu",
        strategy_type=StrategyType.CA_ONLY,
    )

    assert isinstance(topo.protein_topology, ProteinTopology)
    assert topo.protein_topology.fidelity == "placeholder_alanine"
    topo.set_residue_types_from_sequence(torch.tensor([9, 3, 5], dtype=torch.long))
    assert topo.protein_topology.fidelity == "sequence_mapped"
    assert topo.hbond_roles() == topo.protein_topology.hbond_roles
    coords = torch.zeros(1, 3, 3)
    assert torch.allclose(topo.compute_virtual_hbond_bead_coords(coords), topo.protein_topology.virtual_site_offsets.unsqueeze(0))
