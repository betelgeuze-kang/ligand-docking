from __future__ import annotations

from dataclasses import replace
import math

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2 import (  # noqa: E402
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
)
from betelgeuze_engine_v2.docking import (  # noqa: E402
    AUTHENTICATED_DOCKING_MACROCYCLE_MIN_RING_ATOMS,
    DockingAuthorityError,
    DockingBudget,
    DockingProblemIdentity,
    derive_authoritative_torsion_search_space,
    generate_bounded_docking_proposals,
)


def _provenance() -> StructureProvenance:
    return StructureProvenance(
        source_format="unit",
        source_id="ring-ligand-stage1",
        source_sha256="a" * 64,
        parser_name="ring-ligand-stage1-fixture",
        parser_version="1.0.0",
    )


def _system(
    coordinates: list[list[float]],
    bond_pairs: list[tuple[int, int]],
) -> AllAtomSystem:
    atom_count = len(coordinates)
    return AllAtomSystem(
        system_id="ring-ligand-stage1",
        atoms=tuple(
            Atom(
                index=index,
                name=f"C{index}",
                element="C",
                atomic_number=6,
                residue_index=0,
            )
            for index in range(atom_count)
        ),
        bonds=tuple(
            Bond(
                index=index,
                atom_i=min(first, second),
                atom_j=max(first, second),
                order=1.0,
            )
            for index, (first, second) in enumerate(bond_pairs)
        ),
        residues=(
            Residue(
                index=0,
                name="LIG",
                chain_index=0,
                sequence_number=1,
                atom_indices=tuple(range(atom_count)),
            ),
        ),
        chains=(Chain(index=0, chain_id="L", residue_indices=(0,)),),
        coordinates=torch.tensor([coordinates], dtype=torch.float64),
        provenance=_provenance(),
    )


def _substituted_cyclohexane() -> AllAtomSystem:
    ring = [
        [1.4, 0.0, 0.2],
        [0.7, 1.212, -0.2],
        [-0.7, 1.212, 0.2],
        [-1.4, 0.0, -0.2],
        [-0.7, -1.212, 0.2],
        [0.7, -1.212, -0.2],
    ]
    substituents = [
        [2.8, 0.0, 0.2],
        [4.2, 0.3, 0.6],
        [-2.8, 0.0, -0.2],
        [-4.2, -0.3, -0.6],
    ]
    return _system(
        ring + substituents,
        [
            (0, 1),
            (1, 2),
            (2, 3),
            (3, 4),
            (4, 5),
            (5, 0),
            (0, 6),
            (6, 7),
            (3, 8),
            (8, 9),
        ],
    )


def _simple_ring(size: int) -> AllAtomSystem:
    radius = 2.0
    coordinates = [
        [
            radius * math.cos(2.0 * math.pi * index / size),
            radius * math.sin(2.0 * math.pi * index / size),
            0.1 * (index % 2),
        ]
        for index in range(size)
    ]
    bonds = [(index, (index + 1) % size) for index in range(size)]
    return _system(coordinates, bonds)


def _chorded_ring(size: int) -> AllAtomSystem:
    system = _simple_ring(size)
    return _system(
        system.coordinates[0].tolist(),
        [
            (index, (index + 1) % size)
            for index in range(size)
        ]
        + [(0, size // 2)],
    )


def test_ring_system_is_rigid_and_only_external_bonds_are_rotatable() -> None:
    ligand = _substituted_cyclohexane()
    search_space, receipt = derive_authoritative_torsion_search_space(ligand)

    assert receipt.rigid_ring_system_atom_indices == ((0, 1, 2, 3, 4, 5),)
    assert receipt.ring_bond_pairs == (
        (0, 1),
        (0, 5),
        (1, 2),
        (2, 3),
        (3, 4),
        (4, 5),
    )
    assert receipt.maximum_ring_system_atom_count == 6
    assert receipt.maximum_ring_cycle_size == 6
    assert receipt.rotatable_child_atom_indices == (6, 8)
    assert search_space.torsion_count == 2
    assert not any(
        bool(search_space.rotatable_mask[index])
        for index in receipt.rigid_ring_system_atom_indices[0]
    )


def test_generated_proposals_preserve_all_ring_pair_distances() -> None:
    ligand = _substituted_cyclohexane()
    search_space, receipt = derive_authoritative_torsion_search_space(ligand)
    problem = DockingProblemIdentity(
        receptor_system_sha256="b" * 64,
        ligand_system_sha256="c" * 64,
        pocket_definition_sha256="d" * 64,
    )
    proposals = generate_bounded_docking_proposals(
        search_space,
        DockingBudget(
            candidate_count=5,
            top_k=3,
            max_torsions=2,
            seed=211,
        ),
        problem=problem,
    )
    ring_atoms = list(receipt.rigid_ring_system_atom_indices[0])
    reference = torch.cdist(
        ligand.coordinates[0, ring_atoms],
        ligand.coordinates[0, ring_atoms],
    )
    for proposal in proposals:
        observed = torch.cdist(
            proposal.coordinates[ring_atoms],
            proposal.coordinates[ring_atoms],
        )
        assert torch.allclose(observed, reference, atol=1.0e-10, rtol=0.0)


def test_macrocycle_lane_is_explicitly_unsupported() -> None:
    assert AUTHENTICATED_DOCKING_MACROCYCLE_MIN_RING_ATOMS == 12
    with pytest.raises(DockingAuthorityError, match="conservatively rejects"):
        derive_authoritative_torsion_search_space(
            _simple_ring(AUTHENTICATED_DOCKING_MACROCYCLE_MIN_RING_ATOMS)
        )


def test_chord_cannot_hide_an_unsupported_large_ring_system() -> None:
    with pytest.raises(DockingAuthorityError, match="conservatively rejects"):
        derive_authoritative_torsion_search_space(
            _chorded_ring(AUTHENTICATED_DOCKING_MACROCYCLE_MIN_RING_ATOMS)
        )


def test_small_ring_is_supported_without_internal_rotors() -> None:
    search_space, receipt = derive_authoritative_torsion_search_space(
        _simple_ring(7)
    )
    assert search_space.torsion_count == 0
    assert receipt.maximum_ring_system_atom_count == 7
    assert receipt.maximum_ring_cycle_size == 7
    assert receipt.rigid_ring_system_atom_indices == ((0, 1, 2, 3, 4, 5, 6),)
    document = receipt.to_dict()
    assert document["ring_systems_retained_as_rigid_components"] is True
    assert document["ring_closure_supported"] is True
    assert document["ring_closure_sampling_supported"] is False
    assert document["macrocycle_supported"] is False
    assert document["macrocycle_min_ring_atoms"] == 12


def test_ring_receipt_rejects_overlapping_or_cross_wired_systems() -> None:
    _, receipt = derive_authoritative_torsion_search_space(
        _substituted_cyclohexane()
    )
    with pytest.raises(DockingAuthorityError, match="atom-disjoint"):
        replace(
            receipt,
            rigid_ring_system_atom_indices=((0, 1, 2, 3), (3, 4, 5)),
        )
    with pytest.raises(DockingAuthorityError, match="cannot cross"):
        replace(
            receipt,
            rigid_ring_system_atom_indices=((0, 1, 5), (2, 3, 4)),
        )
