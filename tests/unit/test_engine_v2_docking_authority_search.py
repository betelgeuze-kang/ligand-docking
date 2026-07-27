from __future__ import annotations

# Torch is optional for collection, so imports depending on it intentionally follow
# the importorskip guard below.
# ruff: noqa: E402

from dataclasses import replace

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
    DockingBudget,
    DockingScoreDescriptor,
    DockingScope,
    PocketDefinition,
    ScoreDirection,
    build_authenticated_known_pocket_docking_problem,
    run_authenticated_bounded_docking_search,
)


def _system(*, receptor: bool) -> AllAtomSystem:
    if receptor:
        elements = ("C", "C", "C")
        coordinates = [[[1.0, 4.0, 0.0], [4.0, 4.0, 0.0], [7.0, 0.0, 0.0]]]
        bonds = ()
        digest = "a" * 64
        name = "REC"
    else:
        elements = ("C", "N", "C", "O")
        coordinates = [[[0.0, 0.0, 0.0], [1.4, 0.0, 0.0], [2.8, 0.3, 0.0], [4.1, 1.0, 0.2]]]
        bonds = (
            Bond(index=0, atom_i=0, atom_j=1, order=1.0),
            Bond(index=1, atom_i=1, atom_j=2, order=1.0),
            Bond(index=2, atom_i=2, atom_j=3, order=1.0),
        )
        digest = "b" * 64
        name = "LIG"
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
    return AllAtomSystem(
        system_id=f"authority-{name.lower()}",
        atoms=atoms,
        bonds=bonds,
        residues=(
            Residue(
                index=0,
                name=name,
                chain_index=0,
                sequence_number=1,
                atom_indices=tuple(range(len(atoms))),
            ),
        ),
        chains=(Chain(index=0, chain_id="A", residue_indices=(0,)),),
        coordinates=torch.tensor(coordinates, dtype=torch.float64),
        provenance=StructureProvenance(
            source_format="unit",
            source_id=f"authority-{name.lower()}-source",
            source_sha256=digest,
            parser_name="authority-fixture",
            parser_version="1.0.0",
        ),
    )


def _authority():
    return build_authenticated_known_pocket_docking_problem(
        _system(receptor=True),
        _system(receptor=False),
        PocketDefinition(
            scope=DockingScope.KNOWN_POCKET,
            method_id="manual-reviewed-sphere",
            method_version="1.0.0",
            coordinate_frame_id="prepared-receptor-frame-v1",
            center=torch.tensor([2.5, 0.5, 0.0], dtype=torch.float64),
            radius_angstrom=6.0,
            source_artifact_sha256="c" * 64,
            implementation_source_sha256="d" * 64,
        ),
    )


class _Scorer:
    scorer_id = "authority-test-scorer"
    scorer_version = "1.0.0"
    validated_for_docking_ranking = False
    implementation_source_sha256 = "e" * 64
    config_fingerprint_sha256 = "f" * 64
    score_descriptor = DockingScoreDescriptor(
        score_id="authority-test-score",
        direction=ScoreDirection.MINIMIZE,
        unit=None,
        semantics="unit_test_only",
        calibrated=False,
    )

    def __init__(self, problem_fingerprint: str) -> None:
        self.problem_fingerprint_sha256 = problem_fingerprint

    def score(self, proposal):
        return proposal.coordinates.square().sum()


def test_authenticated_search_retains_input_authority() -> None:
    authority = _authority()
    result = run_authenticated_bounded_docking_search(
        authority,
        DockingBudget(
            candidate_count=3,
            top_k=2,
            max_torsions=1,
            translation_radius_angstrom=0.0,
            seed=43,
        ),
        _Scorer(authority.problem.fingerprint_sha256),
        diversity_rmsd_angstrom=0.0,
        diversity_metric="symmetry_aware_direct_rmsd",
        symmetry_permutations=((0, 1, 2, 3),),
    )
    assert result.authenticated_input_receipt_sha256 == authority.input_receipt_sha256
    assert result.search_result.problem_fingerprint_sha256 == authority.problem.fingerprint_sha256
    assert result.search_result.search_space_fingerprint_sha256 == authority.search_space.fingerprint_sha256
    assert result.search_result.validity_context_fingerprint_sha256 == authority.validity_context.fingerprint_sha256
    assert result.search_result.diversity_metric == "symmetry_aware_direct_rmsd"
    assert len(result.receipt_sha256) == 64
    assert result.to_dict()["claim_safe"] is False


def test_authenticated_problem_rejects_identity_cross_wiring() -> None:
    authority = _authority()
    with pytest.raises(DockingAuthorityError, match="ligand identity"):
        replace(authority, ligand_system_sha256="9" * 64)
