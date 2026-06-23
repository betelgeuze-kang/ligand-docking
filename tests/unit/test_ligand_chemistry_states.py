from __future__ import annotations

import numpy as np
import pytest

from betelgeuze_engine.backmapping.onsps import backmap_4bead_onsps
from betelgeuze_engine.chemistry.ligand_states import (
    enumerate_ligand_states_from_smiles,
    ligand_chemistry_state_from_smiles,
)
from betelgeuze_engine.biodiscovery.ligand_prep import validate_ligand
from betelgeuze_engine.topology.ligand import ligand_topology_from_smiles


pytest.importorskip("rdkit")


def _roles(smiles: str) -> list[tuple[str, str]]:
    return [(site.element, site.role) for site in ligand_chemistry_state_from_smiles(smiles).feature_sites]


def test_rdkit_chemical_features_drive_donor_acceptor_roles() -> None:
    amide = ligand_chemistry_state_from_smiles("CC(=O)N")
    pyridine = ligand_chemistry_state_from_smiles("c1ccncc1")
    protonated_amine = ligand_chemistry_state_from_smiles("C[NH3+]")

    assert ("O", "acceptor") in _roles("CC(=O)N")
    assert ("N", "donor") in _roles("CC(=O)N")
    assert amide.feature_source == "rdkit_chemical_features_base_fdef"
    assert pyridine.donor_site_count == 0
    assert pyridine.acceptor_site_count == 1
    assert protonated_amine.protonation_status == "charged_state_parsed"
    assert protonated_amine.donor_site_count == 1
    assert protonated_amine.acceptor_site_count == 0


def test_tautomer_salt_charge_and_chirality_state_are_recorded() -> None:
    keto = ligand_chemistry_state_from_smiles("CC(=O)CC(=O)C")
    salt = ligand_chemistry_state_from_smiles("CC(=O)[O-].[Na+]")
    unspecified_chiral = ligand_chemistry_state_from_smiles("CC(O)C(=O)O")

    assert keto.tautomer_status == "canonical_tautomer_enumerated"
    assert keto.tautomer_count >= 2
    assert keto.canonical_tautomer_smiles
    assert salt.salt_stripped is True
    assert salt.fragment_count == 2
    assert salt.salt_parent_smiles == "CC(=O)[O-]"
    assert salt.formal_charge_sum == 0
    assert salt.charged_atom_count == 2
    assert salt.protonation_status == "charged_state_parsed"
    assert unspecified_chiral.chirality_status == "unassigned_stereochemistry"
    assert "unassigned_ligand_chirality" in unspecified_chiral.claim_safe_blockers
    assert "unassigned_ligand_stereochemistry" in unspecified_chiral.claim_safe_blockers


def test_unspecified_double_bond_stereo_is_fail_closed() -> None:
    unspecified = ligand_chemistry_state_from_smiles("CC=CC")
    specified = ligand_chemistry_state_from_smiles("C/C=C/C")

    assert unspecified.chirality_status == "unassigned_stereochemistry"
    assert unspecified.unassigned_stereo_bond_count == 1
    assert "unassigned_ligand_double_bond_stereochemistry" in unspecified.claim_safe_blockers
    assert specified.chirality_status == "specified"
    assert specified.unassigned_stereo_count == 0
    assert specified.claim_safe_blockers == ()

    blocked = validate_ligand("CC=CC")
    allowed = validate_ligand("C/C=C/C")
    assert blocked["blocked"] is True
    assert "unassigned_ligand_double_bond_stereochemistry" in blocked["blockers"]
    assert allowed["blocked"] is False


def test_restricted_ligand_state_ensemble_records_salt_parent_without_pka_claim() -> None:
    states = enumerate_ligand_states_from_smiles("CC(=O)[O-].[Na+]", max_states=4)

    assert [state.state_kind for state in states][:2] == ["input_canonical", "salt_parent"]
    assert any(state.state_kind.startswith("tautomer_") for state in states)
    assert states[0].smiles == "CC(=O)[O-].[Na+]"
    assert states[0].salt_stripped is True
    assert states[0].protonation_source.endswith("no_pka_enumeration")
    assert states[1].smiles == "CC(=O)[O-]"
    assert states[1].source == "rdkit_molstandardize_fragment_parent"
    assert states[1].atom_count == 4
    assert "salt_parent_projection_not_product_safe" in states[1].claim_safe_blockers


def test_restricted_tautomer_states_are_bounded_and_claim_blocked() -> None:
    states = enumerate_ligand_states_from_smiles("CC(=O)CC(=O)C", max_states=4)

    assert states[0].state_kind == "input_canonical"
    tautomer_states = [state for state in states if state.state_kind.startswith("tautomer_")]
    assert 1 <= len(tautomer_states) <= 3
    assert all("tautomer_projection_not_product_safe" in state.claim_safe_blockers for state in tautomer_states)
    assert all("tautomer_enumeration_limited" in state.claim_safe_blockers for state in tautomer_states)
    assert states[0].protonation_policy == "restricted_formal_charge_input_state_ph_7_4_no_pka"
    assert states[0].protonation_ph_values == (7.4,)
    assert "no pKa model" in states[0].protonation_claim_boundary


def test_ligand_topology_uses_chemistry_state_metadata() -> None:
    ligand = ligand_topology_from_smiles("CC(=O)[O-].[Na+]")

    assert ligand.validity["valid"] is True
    assert ligand.validity["feature_source"] == "rdkit_chemical_features_base_fdef"
    assert ligand.validity["protonation_status"] == "charged_state_parsed"
    assert ligand.validity["protonation_policy"] == "restricted_formal_charge_input_state_ph_7_4_no_pka"
    assert ligand.validity["protonation_ph_values"] == [7.4]
    assert ligand.validity["charged_atom_count"] == 2
    assert ligand.validity["salt_stripped"] is True
    assert ligand.validity["salt_parent_smiles"] == "CC(=O)[O-]"
    assert ligand.validity["tautomer_status"] == "canonical_tautomer_enumerated"
    assert ligand.validity["canonical_tautomer_smiles"]


def test_ligand_topology_preserves_dual_donor_acceptor_feature_roles() -> None:
    methanol = ligand_topology_from_smiles("CO")

    assert methanol.atom_elements == ["C", "O"]
    assert methanol.donor_acceptor_roles == ["none", "donor_acceptor"]
    assert methanol.validity["feature_source"] == "rdkit_chemical_features_base_fdef"
    assert methanol.validity["donor_site_count"] == 1
    assert methanol.validity["acceptor_site_count"] == 1
    assert methanol.validity["hbond_site_count"] == 2
    oxygen_sites = [site for site in methanol.validity["feature_sites"] if site["atom_idx"] == 1]
    assert {site["role"] for site in oxygen_sites} == {"donor", "acceptor"}


def test_validate_ligand_preserves_rdkit_protonation_and_tautomer_sources() -> None:
    ligand = validate_ligand("CC(=O)CC(=O)C")

    assert ligand["protonation_source"] == "rdkit_formal_charge_state_from_input_ph_7_4_no_pka_enumeration"
    assert ligand["protonation_policy"] == "restricted_formal_charge_input_state_ph_7_4_no_pka"
    assert ligand["protonation_ph_values"] == [7.4]
    assert ligand["tautomer_source"] == "rdkit_molstandardize_tautomer_enumerator"
    assert ligand["tautomer_status"] == "canonical_tautomer_enumerated"


def test_onsps_backmap_uses_rdkit_feature_roles() -> None:
    two_bead = np.asarray([[0.0, 0.0, 0.0], [1.6, 0.0, 0.0]], dtype=np.float32)
    _mapped, meta = backmap_4bead_onsps(two_bead, "c1ccncc1")

    assert meta["schema_version"] == "onsps_backmap_evidence_v1"
    assert meta["backmap_status"] == "ok"
    assert meta["mapping_source"] == "rdkit_etkdg"
    assert meta["elements"] == ["N"]
    assert meta["roles"] == ["acceptor"]
    assert meta["role_counts"]["donor"] == 0
    assert meta["role_counts"]["acceptor"] == 1
