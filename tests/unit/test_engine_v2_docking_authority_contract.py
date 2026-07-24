from __future__ import annotations

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2 import (
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
)
from betelgeuze_engine_v2.docking import (
    DockingAuthorityError,
    DockingScope,
    PocketDefinition,
    build_authenticated_known_pocket_docking_problem,
    derive_authoritative_torsion_search_space,
)


def _provenance(name: str, digest: str) -> StructureProvenance:
    return StructureProvenance(
        source_format="unit",
        source_id=name,
        source_sha256=digest,
        parser_name="authority-fixture",
        parser_version="1.0.0",
    )


def _ligand(*, ring: bool = False, disconnected: bool = False) -> AllAtomSystem:
    elements = ("C", "N", "C", "O")
    atoms = tuple(
        Atom(
            index=index,
            name=f"A{index}",
            element=element,
            atomic_number={"C": 6, "N": 7, "O": 8}[element],
            residue_index=0,
        )
        for index, element in enumerate(elements)
    )
    bonds = [
        Bond(index=0, atom_i=0, atom_j=1, order=1.0),
        Bond(index=1, atom_i=1, atom_j=2, order=1.0),
    ]
    if not disconnected:
        bonds.append(Bond(index=2, atom_i=2, atom_j=3, order=1.0))
    if ring:
        bonds.append(Bond(index=len(bonds), atom_i=0, atom_j=3, order=1.0))
    return AllAtomSystem(
        system_id="authority-ligand",
        atoms=atoms,
        bonds=tuple(bonds),
        residues=(
            Residue(
                index=0,
                name="LIG",
                chain_index=0,
                sequence_number=1,
                atom_indices=(0, 1, 2, 3),
            ),
        ),
        chains=(Chain(index=0, chain_id="L", residue_indices=(0,)),),
        coordinates=torch.tensor(
            [[[0.0, 0.0, 0.0], [1.4, 0.0, 0.0], [2.8, 0.3, 0.0], [4.1, 1.0, 0.2]]],
            dtype=torch.float64,
        ),
        provenance=_provenance("ligand-source", "a" * 64),
    )


def _receptor() -> AllAtomSystem:
    atoms = tuple(
        Atom(
            index=index,
            name=f"R{index}",
            element="C",
            atomic_number=6,
            residue_index=0,
        )
        for index in range(4)
    )
    return AllAtomSystem(
        system_id="authority-receptor",
        atoms=atoms,
        bonds=(),
        residues=(
            Residue(
                index=0,
                name="REC",
                chain_index=0,
                sequence_number=1,
                atom_indices=(0, 1, 2, 3),
            ),
        ),
        chains=(Chain(index=0, chain_id="A", residue_indices=(0,)),),
        coordinates=torch.tensor(
            [[[1.0, 4.0, 0.0], [4.0, 4.0, 0.0], [7.0, 0.0, 0.0], [60.0, 60.0, 60.0]]],
            dtype=torch.float64,
        ),
        provenance=_provenance("receptor-source", "b" * 64),
    )


def _pocket() -> PocketDefinition:
    return PocketDefinition(
        scope=DockingScope.KNOWN_POCKET,
        method_id="manual-reviewed-sphere",
        method_version="1.0.0",
        coordinate_frame_id="prepared-receptor-frame-v1",
        center=torch.tensor([2.5, 0.5, 0.0], dtype=torch.float64),
        radius_angstrom=6.0,
        source_artifact_sha256="c" * 64,
        implementation_source_sha256="d" * 64,
        metadata={"reviewed": True},
    )


def test_pocket_is_cloned_and_fingerprint_guarded() -> None:
    source = torch.tensor([2.5, 0.5, 0.0], dtype=torch.float64)
    pocket = PocketDefinition(
        scope=DockingScope.REDOCKING,
        method_id="reference-sphere",
        method_version="1.0.0",
        coordinate_frame_id="receptor-frame-v1",
        center=source,
        radius_angstrom=8.0,
        source_artifact_sha256="1" * 64,
        implementation_source_sha256="2" * 64,
    )
    expected = pocket.center.clone()
    source.add_(100.0)
    assert torch.equal(pocket.center, expected)
    pocket.center.add_(1.0)
    with pytest.raises(DockingAuthorityError, match="changed after construction"):
        pocket.fingerprint_sha256


def test_torsion_derivation_is_exact_and_fail_closed() -> None:
    search_space, receipt = derive_authoritative_torsion_search_space(_ligand())
    assert search_space.torsion_count == 1
    assert receipt.root_atom_indices == (0,)
    assert receipt.rotatable_child_atom_indices == (2,)
    assert receipt.selected_model_coordinate_sha256 == receipt.zero_torsion_coordinate_sha256
    with pytest.raises(DockingAuthorityError, match="ring closure"):
        derive_authoritative_torsion_search_space(_ligand(ring=True))
    with pytest.raises(DockingAuthorityError, match="connected ligand"):
        derive_authoritative_torsion_search_space(_ligand(disconnected=True))


def test_authenticated_problem_cross_binds_every_derived_contract() -> None:
    authority = build_authenticated_known_pocket_docking_problem(
        _receptor(),
        _ligand(),
        _pocket(),
    )
    assert authority.problem.pocket_definition_sha256 == authority.pocket.fingerprint_sha256
    assert authority.search_space.fingerprint_sha256 == authority.search_space_receipt.search_space_fingerprint_sha256
    assert authority.validity_context.problem_fingerprint_sha256 == authority.problem.fingerprint_sha256
    assert authority.receptor_atom_indices == (0, 1, 2)
    assert authority.validity_context.bond_pairs == ((0, 1), (1, 2), (2, 3))
    assert len(authority.input_receipt_sha256) == 64
    assert authority.to_dict()["caller_supplied_validity_context_allowed"] is False
