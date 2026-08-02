"""Ring rigid-component and chemistry-aware rotor perception tests (P1-2, P1-3)."""

from __future__ import annotations

import pytest

from betelgeuze_engine.chemistry.rotor_perception import (
    MACROCYCLE_MIN_RING_SIZE,
    ROTOR_CLASS_AMIDE,
    ROTOR_CLASS_CARBAMATE,
    ROTOR_CLASS_CONJUGATED,
    ROTOR_CLASS_EXOCYCLIC_RING,
    ROTOR_CLASS_RING_RING,
    ROTOR_CLASS_SP3_SP3,
    ROTOR_CLASS_SULFONAMIDE,
    ROTOR_CLASS_UREA,
    ROTOR_PERCEPTION_SCHEMA_VERSION,
    STATUS_SUPPORTED,
    STATUS_UNSUPPORTED_INVALID,
    STATUS_UNSUPPORTED_MACROCYCLE,
    perceive_ligand_rotors,
)
from betelgeuze_engine.topology import ligand_topology_from_smiles

pytest.importorskip("rdkit")


def _classes(smiles: str) -> list[str]:
    return [rotor.rotor_class for rotor in perceive_ligand_rotors(smiles).rotors]


def test_ring_bonds_never_become_rotors() -> None:
    perception = perceive_ligand_rotors("c1ccccc1")

    assert perception.status == STATUS_SUPPORTED
    assert perception.rotor_count == 0
    assert perception.rigid_components[0].ring_sizes == (6,)
    assert perception.rigid_components[0].aromatic is True


def test_fused_rings_collapse_into_one_rigid_component() -> None:
    perception = perceive_ligand_rotors("c1ccc2ccccc2c1")

    assert len(perception.rigid_components) == 1
    component = perception.rigid_components[0]
    assert component.ring_count == 2
    assert component.ring_sizes == (6, 6)
    assert len(component.atom_indices) == 10
    assert perception.rotor_count == 0


def test_separate_rings_stay_separate_rigid_components() -> None:
    perception = perceive_ligand_rotors("c1ccccc1-c1ccccc1")

    assert len(perception.rigid_components) == 2
    assert perception.rotor_count == 1


@pytest.mark.parametrize(
    ("smiles", "expected_class"),
    [
        ("CC(=O)NC", ROTOR_CLASS_AMIDE),
        ("CNC(=O)NC", ROTOR_CLASS_UREA),
        ("CCOC(=O)NC", ROTOR_CLASS_CARBAMATE),
        ("CS(=O)(=O)NC", ROTOR_CLASS_SULFONAMIDE),
    ],
)
def test_restrained_linkages_are_classified(smiles: str, expected_class: str) -> None:
    assert expected_class in _classes(smiles)


def test_urea_is_not_downgraded_to_amide() -> None:
    classes = _classes("CNC(=O)NC")

    assert set(classes) == {ROTOR_CLASS_UREA}
    assert ROTOR_CLASS_AMIDE not in classes


def test_restrained_rotors_are_flagged_and_have_few_states() -> None:
    perception = perceive_ligand_rotors("CC(=O)NC")
    rotor = perception.rotors[0]

    assert rotor.restrained is True
    assert rotor.preferred_state_count == 2
    assert rotor.periodicity == 2
    assert perception.restrained_rotor_count == 1


def test_conjugated_single_bond_is_hindered_not_free() -> None:
    perception = perceive_ligand_rotors("c1ccccc1-c1ccccc1")
    rotor = perception.rotors[0]

    assert rotor.rotor_class == ROTOR_CLASS_CONJUGATED
    assert rotor.conjugated is True
    assert rotor.preferred_state_count == 2


def test_exocyclic_ring_bond_is_distinct_from_ring_ring_bond() -> None:
    exocyclic = perceive_ligand_rotors("C1CCCCC1CC").rotors[0]
    ring_ring = perceive_ligand_rotors("C1CCCCC1C2CCCCC2").rotors[0]

    assert exocyclic.rotor_class == ROTOR_CLASS_EXOCYCLIC_RING
    assert exocyclic.exocyclic_ring_bond is True
    assert exocyclic.ring_ring_bond is False

    assert ring_ring.rotor_class == ROTOR_CLASS_RING_RING
    assert ring_ring.ring_ring_bond is True
    assert ring_ring.exocyclic_ring_bond is False


def test_plain_alkane_chain_rotors_are_sp3() -> None:
    assert _classes("CCCCCC") == [ROTOR_CLASS_SP3_SP3] * 3


def test_terminal_bonds_are_not_torsions() -> None:
    # Ethane has one single bond but no heavy torsion partners on either side.
    assert perceive_ligand_rotors("CC").rotor_count == 0


def test_double_bond_is_stereo_locked_not_a_rotor() -> None:
    perception = perceive_ligand_rotors("CC=CC")

    assert perception.rotor_count == 0
    assert perception.stereo_locked_bond_count == 1


def test_macrocycle_routes_to_unsupported_lane() -> None:
    perception = perceive_ligand_rotors("C1CCCCCCCCCCCC1")

    assert perception.status == STATUS_UNSUPPORTED_MACROCYCLE
    assert perception.supported is False
    assert perception.rotor_count == 0
    assert perception.macrocycle_ring_sizes == (13,)
    assert perception.unsupported_reason == "macrocycle_requires_ring_closure_sampling"
    # The ring system is still reported so the caller can see why it was routed out.
    assert perception.rigid_components[0].macrocyclic is True


def test_ring_at_macrocycle_threshold_is_unsupported() -> None:
    ring = "C1" + "C" * (MACROCYCLE_MIN_RING_SIZE - 2) + "C1"
    perception = perceive_ligand_rotors(ring)

    assert perception.status == STATUS_UNSUPPORTED_MACROCYCLE


def test_ring_below_macrocycle_threshold_stays_supported() -> None:
    ring = "C1" + "C" * (MACROCYCLE_MIN_RING_SIZE - 3) + "C1"
    perception = perceive_ligand_rotors(ring)

    assert perception.status == STATUS_SUPPORTED
    assert perception.macrocycle_ring_sizes == ()


def test_invalid_and_empty_smiles_fail_closed() -> None:
    assert perceive_ligand_rotors("").status == STATUS_UNSUPPORTED_INVALID
    assert perceive_ligand_rotors("not_a_molecule[").status == STATUS_UNSUPPORTED_INVALID


def test_effective_torsion_state_count_is_product_of_rotor_states() -> None:
    perception = perceive_ligand_rotors("CCCCCC")

    assert perception.effective_torsion_state_count == 3 * 3 * 3


def test_restraint_shrinks_the_search_space_versus_free_rotors() -> None:
    restrained = perceive_ligand_rotors("CCC(=O)NCC")
    assert restrained.restrained_rotor_count >= 1
    # An amide-containing chain must not be searched as if every bond were free.
    free_equivalent = 6 ** restrained.rotor_count
    assert restrained.effective_torsion_state_count < free_equivalent


def test_payload_exposes_schema_and_claim_boundary() -> None:
    payload = perceive_ligand_rotors("CC(=O)NC").to_dict()

    assert payload["schema_version"] == ROTOR_PERCEPTION_SCHEMA_VERSION
    assert "not ring-closure sampling" in payload["claim_boundary"]


def test_ligand_topology_reports_flexibility_lane_and_rotor_counts() -> None:
    topology = ligand_topology_from_smiles("c1ccccc1C(=O)NCC2CCCCC2")
    validity = topology.validity

    assert validity["ligand_flexibility_lane"] == "rigid_component_plus_rotor"
    assert validity["rotor_perception_supported"] is True
    assert validity["restrained_rotor_count"] == 1
    assert validity["rigid_component_count"] == 2
    assert validity["macrocycle_present"] is False
    assert validity["claim_safe"] is True
    assert topology.rotor_perception is not None


def test_ligand_topology_blocks_claim_safe_for_macrocycle() -> None:
    validity = ligand_topology_from_smiles("C1CCCCCCCCCCCC1").validity

    assert validity["ligand_flexibility_lane"] == "macrocycle_unsupported"
    assert validity["rotor_perception_supported"] is False
    assert validity["claim_safe"] is False
    assert "macrocycle_ligand_unsupported_lane" in validity["claim_safe_blockers"]


def test_pose_diagnostics_expose_chemistry_aware_rotor_summary() -> None:
    from betelgeuze_engine.biodiscovery.pose import chemistry_aware_rotor_summary

    summary = chemistry_aware_rotor_summary("c1ccccc1C(=O)NCC2CCCCC2")

    assert summary["supported"] is True
    assert summary["flexibility_lane"] == "rigid_component_plus_rotor"
    assert summary["restrained_rotor_count"] == 1
    assert summary["rigid_component_count"] == 2
    assert summary["effective_torsion_state_count"] > 1


def test_pose_diagnostics_route_macrocycle_out() -> None:
    from betelgeuze_engine.biodiscovery.pose import chemistry_aware_rotor_summary

    summary = chemistry_aware_rotor_summary("C1CCCCCCCCCCCC1")

    assert summary["flexibility_lane"] == "macrocycle_unsupported"
    assert summary["macrocycle_present"] is True
