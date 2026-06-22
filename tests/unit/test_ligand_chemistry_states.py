from __future__ import annotations

import numpy as np
import pytest

from betelgeuze_engine.backmapping.onsps import backmap_4bead_onsps
from betelgeuze_engine.chemistry.ligand_states import ligand_chemistry_state_from_smiles
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
    assert unspecified_chiral.chirality_status == "unassigned_chiral_centers"
    assert "unassigned_ligand_chirality" in unspecified_chiral.claim_safe_blockers


def test_ligand_topology_uses_chemistry_state_metadata() -> None:
    ligand = ligand_topology_from_smiles("CC(=O)[O-].[Na+]")

    assert ligand.validity["valid"] is True
    assert ligand.validity["feature_source"] == "rdkit_chemical_features_base_fdef"
    assert ligand.validity["protonation_status"] == "charged_state_parsed"
    assert ligand.validity["charged_atom_count"] == 2
    assert ligand.validity["salt_stripped"] is True
    assert ligand.validity["salt_parent_smiles"] == "CC(=O)[O-]"
    assert ligand.validity["tautomer_status"] == "canonical_tautomer_enumerated"
    assert ligand.validity["canonical_tautomer_smiles"]


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
