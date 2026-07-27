from __future__ import annotations

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
    SPARSE_BASE_RECEPTOR_CLASH_ALGORITHM_ID,
    SPARSE_BASE_VALIDITY_SHA256,
    DockingBudget,
    DockingScope,
    ElementAwareValidityError,
    PocketDefinition,
    VdwContactPolicy,
    build_element_aware_authenticated_known_pocket_docking_problem,
    generate_bounded_docking_proposals,
)


def _provenance(name: str, digest: str) -> StructureProvenance:
    return StructureProvenance(
        source_format="unit",
        source_id=name,
        source_sha256=digest,
        parser_name="sparse-base-validity-fixture",
        parser_version="1.0.0",
    )


def _ligand() -> AllAtomSystem:
    elements = ("C", "N", "C", "O")
    return AllAtomSystem(
        system_id="sparse-base-ligand",
        atoms=tuple(
            Atom(
                index=index,
                name=f"L{index}",
                element=element,
                atomic_number={"C": 6, "N": 7, "O": 8}[element],
                residue_index=0,
            )
            for index, element in enumerate(elements)
        ),
        bonds=(
            Bond(index=0, atom_i=0, atom_j=1, order=1.0),
            Bond(index=1, atom_i=1, atom_j=2, order=1.0),
            Bond(index=2, atom_i=2, atom_j=3, order=1.0),
        ),
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
        provenance=_provenance("sparse-base-ligand-source", "a" * 64),
    )


def _receptor(*, overlapping: bool = False) -> AllAtomSystem:
    coordinates = [
        [float(x), float(y), float(z)]
        for x in range(-12, 13, 4)
        for y in range(-12, 13, 4)
        for z in (-8, -4, 0, 4, 8)
        if (x, y, z) != (0, 0, 0)
    ]
    if overlapping:
        coordinates.insert(0, [0.0, 0.0, 0.0])
    atoms = tuple(
        Atom(
            index=index,
            name=f"R{index}",
            element="C",
            atomic_number=6,
            residue_index=0,
        )
        for index in range(len(coordinates))
    )
    return AllAtomSystem(
        system_id="sparse-base-receptor",
        atoms=atoms,
        bonds=(),
        residues=(
            Residue(
                index=0,
                name="REC",
                chain_index=0,
                sequence_number=1,
                atom_indices=tuple(range(len(atoms))),
            ),
        ),
        chains=(Chain(index=0, chain_id="A", residue_indices=(0,)),),
        coordinates=torch.tensor([coordinates], dtype=torch.float64),
        provenance=_provenance("sparse-base-receptor-source", "b" * 64),
    )


def _pocket() -> PocketDefinition:
    return PocketDefinition(
        scope=DockingScope.KNOWN_POCKET,
        method_id="sparse-base-test-sphere",
        method_version="1.0.0",
        coordinate_frame_id="prepared-receptor-frame-v1",
        center=torch.tensor([0.0, 0.0, 0.0], dtype=torch.float64),
        radius_angstrom=25.0,
        source_artifact_sha256="c" * 64,
        implementation_source_sha256="d" * 64,
    )


def _authority(*, overlapping: bool = False, policy=None):
    return build_element_aware_authenticated_known_pocket_docking_problem(
        _receptor(overlapping=overlapping),
        _ligand(),
        _pocket(),
        receptor_margin_angstrom=0.0,
        contact_policy=policy,
    )


def _proposal(authority):
    return generate_bounded_docking_proposals(
        authority.search_space,
        DockingBudget(
            candidate_count=1,
            top_k=1,
            max_torsions=1,
            translation_radius_angstrom=0.0,
            seed=157,
        ),
        problem=authority.problem,
    )[0]


def test_sparse_base_algorithm_is_bound_to_context_identity() -> None:
    assert len(SPARSE_BASE_VALIDITY_SHA256) == 64
    authority = _authority()
    document = authority.validity_context.to_dict()
    assert document["base_receptor_clash_algorithm_id"] == (
        SPARSE_BASE_RECEPTOR_CLASH_ALGORITHM_ID
    )
    assert document["dense_receptor_cartesian_traversal_performed"] is False
    assert len(authority.validity_context.fingerprint_sha256) == 64


def test_base_and_vdw_receptor_checks_share_sparse_candidates() -> None:
    authority = _authority()
    result = authority.validity_context.evaluate(_proposal(authority))
    assert result.evaluated_checks["receptor_ligand_clash_free"] is True
    assert "receptor_ligand_clash_free" not in result.not_evaluated_reasons
    sparse_count = result.measurements[
        "evaluated_receptor_ligand_pair_count"
    ]
    full_count = result.measurements[
        "full_cartesian_receptor_ligand_pair_count"
    ]
    assert sparse_count == result.measurements[
        "element_vdw_receptor_candidate_pair_count"
    ]
    assert 0 <= sparse_count < full_count
    assert result.measurements["sparse_receptor_cell_count"] > 1
    assert result.complete is True


def test_sparse_base_clash_preserves_legacy_check_and_blocker() -> None:
    authority = _authority(overlapping=True)
    result = authority.validity_context.evaluate(_proposal(authority))
    assert result.checks["receptor_ligand_clash_free"] is False
    assert "receptor_ligand_clash_detected" in result.blockers
    assert result.measurements[
        "minimum_receptor_ligand_distance_angstrom"
    ] == pytest.approx(0.0, abs=1.0e-12)
    assert result.checks["element_vdw_receptor_overlap_free"] is False
    assert result.valid is False


def test_sparse_candidate_capacity_remains_fail_closed() -> None:
    authority = _authority(
        policy=VdwContactPolicy(max_receptor_candidate_pairs=0),
    )
    with pytest.raises(
        ElementAwareValidityError,
        match="candidate-pair capacity",
    ):
        authority.validity_context.evaluate(_proposal(authority))
