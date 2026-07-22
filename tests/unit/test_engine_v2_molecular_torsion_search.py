from __future__ import annotations

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2.docking import (  # noqa: E402
    DockingBudget,
    DockingProblemIdentity,
    MolecularTorsionSearchConfig,
    MolecularTorsionSearchError,
    build_molecular_torsion_search_space,
    generate_bounded_docking_proposals,
)
from betelgeuze_engine_v2.molecular import (  # noqa: E402
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
)


def _system(
    coordinates: tuple[tuple[float, float, float], ...],
    bonds: tuple[tuple[int, int, float, bool], ...],
    *,
    elements: tuple[str, ...] | None = None,
) -> AllAtomSystem:
    names = elements or tuple("C" for _ in coordinates)
    atomic_numbers = {"C": 6, "N": 7, "O": 8, "S": 16, "P": 15}
    atoms = tuple(
        Atom(
            index=index,
            name=f"{element}{index + 1}",
            element=element,
            atomic_number=atomic_numbers[element],
            residue_index=0,
        )
        for index, element in enumerate(names)
    )
    bond_rows = tuple(
        Bond(
            index=index,
            atom_i=min(first, second),
            atom_j=max(first, second),
            order=order,
            aromatic=aromatic,
        )
        for index, (first, second, order, aromatic) in enumerate(bonds)
    )
    return AllAtomSystem(
        system_id="torsion-unit-system",
        atoms=atoms,
        bonds=bond_rows,
        residues=(
            Residue(
                index=0,
                name="LIG",
                chain_index=0,
                sequence_number=1,
                atom_indices=tuple(range(len(atoms))),
                entity_type="non-polymer",
                hetero=True,
            ),
        ),
        chains=(Chain(index=0, chain_id="L", residue_indices=(0,)),),
        coordinates=torch.tensor((coordinates,), dtype=torch.float64),
        provenance=StructureProvenance(source_format="unit-test"),
    )


def _chain() -> AllAtomSystem:
    return _system(
        (
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 0.0),
            (1.4, 0.0, 0.0),
            (1.8, 1.1, 0.7),
        ),
        (
            (0, 1, 1.0, False),
            (1, 2, 1.0, False),
            (2, 3, 1.0, False),
        ),
    )


def test_bridge_only_tree_selects_one_internal_bond_and_reconstructs_input() -> None:
    system = _chain()

    space, receipt = build_molecular_torsion_search_space(system)
    second_space, second_receipt = build_molecular_torsion_search_space(system)

    assert space.torsion_count == 1
    assert space.rotatable_mask.tolist() == [False, False, True, False]
    assert receipt.rotatable_bond_count == 1
    assert receipt.excluded_bond_count == 2
    assert receipt.bond_rows[1].status == "selected"
    assert receipt.bond_rows[1].reason == (
        "selected_bridge_single_heavy_nonterminal"
    )
    assert receipt.bond_rows[1].side_heavy_atom_counts == (2, 2)
    assert receipt.reconstruction_max_abs_error_angstrom <= 1.0e-12
    assert space.fingerprint_sha256 == second_space.fingerprint_sha256
    assert receipt.to_dict() == second_receipt.to_dict()
    assert receipt.to_dict()["scientifically_validated"] is False
    assert receipt.to_dict()["claim_safe"] is False


def test_generated_torsion_proposals_preserve_every_covalent_bond_length() -> None:
    system = _chain()
    space, _receipt = build_molecular_torsion_search_space(system)
    problem = DockingProblemIdentity(
        receptor_system_sha256="a" * 64,
        ligand_system_sha256="b" * 64,
        pocket_definition_sha256="c" * 64,
    )
    proposals = generate_bounded_docking_proposals(
        space,
        DockingBudget(
            candidate_count=8,
            top_k=3,
            max_torsions=1,
            translation_radius_angstrom=2.0,
            seed=101,
        ),
        problem=problem,
    )
    reference = system.coordinates[0]
    reference_bonds = torch.tensor(
        [
            torch.linalg.vector_norm(reference[bond.atom_i] - reference[bond.atom_j])
            for bond in system.bonds
        ],
        dtype=torch.float64,
    )
    for proposal in proposals:
        observed = torch.tensor(
            [
                torch.linalg.vector_norm(
                    proposal.coordinates[bond.atom_i]
                    - proposal.coordinates[bond.atom_j]
                )
                for bond in system.bonds
            ],
            dtype=torch.float64,
        )
        assert torch.allclose(observed, reference_bonds, atol=1.0e-12, rtol=0.0)
    reference_end_distance = torch.linalg.vector_norm(reference[0] - reference[3])
    assert any(
        not torch.isclose(
            torch.linalg.vector_norm(proposal.coordinates[0] - proposal.coordinates[3]),
            reference_end_distance,
            atol=1.0e-8,
            rtol=0.0,
        )
        for proposal in proposals[1:]
    )


def test_ring_bonds_and_terminal_bridges_are_explicitly_excluded() -> None:
    ring = _system(
        (
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
        ),
        (
            (0, 1, 1.0, False),
            (1, 2, 1.0, False),
            (2, 3, 1.0, False),
            (0, 3, 1.0, False),
        ),
    )

    space, receipt = build_molecular_torsion_search_space(ring)

    assert space.torsion_count == 0
    assert receipt.rotatable_bond_count == 0
    assert {row.reason for row in receipt.bond_rows} == {
        "ring_or_redundant_cycle_bond"
    }


def test_narrow_amide_pattern_is_not_admitted_as_a_free_torsion() -> None:
    amide = _system(
        (
            (0.0, 1.2, 0.0),
            (0.0, 0.0, 0.0),
            (1.4, 0.0, 0.0),
            (2.2, 0.9, 0.0),
            (-0.9, -0.8, 0.0),
            (2.2, -0.9, 0.0),
        ),
        (
            (0, 1, 2.0, False),
            (1, 2, 1.0, False),
            (2, 3, 1.0, False),
            (1, 4, 1.0, False),
            (2, 5, 1.0, False),
        ),
        elements=("O", "C", "N", "C", "C", "C"),
    )

    space, receipt = build_molecular_torsion_search_space(amide)

    assert space.torsion_count == 0
    assert receipt.bond_rows[1].reason == "amide_like_c_n_partial_double_bond"


def test_disconnected_components_and_capacity_overflow_fail_closed() -> None:
    disconnected = _system(
        ((0.0, 0.0, 0.0), (2.0, 0.0, 0.0)),
        (),
    )
    with pytest.raises(MolecularTorsionSearchError, match="connected"):
        build_molecular_torsion_search_space(disconnected)

    with pytest.raises(MolecularTorsionSearchError, match="rotatable-bond count"):
        build_molecular_torsion_search_space(
            _chain(),
            config=MolecularTorsionSearchConfig(max_rotatable_bonds=0),
        )


def test_molecular_torsion_symbols_are_reexported() -> None:
    from betelgeuze_engine_v2 import docking
    from betelgeuze_engine_v2.docking.molecular_torsion import (
        __all__ as torsion_exports,
    )

    assert set(torsion_exports) <= set(docking.__all__)
