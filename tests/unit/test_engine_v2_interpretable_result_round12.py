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
    DockingBudget,
    DockingScope,
    InterpretablePoseScorerV0,
    InterpretableSearchResultError,
    InterpretableSearchTermRow,
    PocketDefinition,
    build_element_aware_authenticated_known_pocket_docking_problem,
    run_authenticated_interpretable_pocket_search,
)


def _provenance(name: str, digest: str) -> StructureProvenance:
    return StructureProvenance(
        source_format="unit",
        source_id=name,
        source_sha256=digest,
        parser_name="interpretable-result-fixture",
        parser_version="1.0.0",
    )


def _ligand() -> AllAtomSystem:
    elements = ("C", "N", "C", "O")
    return AllAtomSystem(
        system_id="term-result-ligand",
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
            [
                [
                    [0.0, 0.0, 0.0],
                    [1.4, 0.0, 0.0],
                    [2.8, 0.3, 0.0],
                    [4.1, 1.0, 0.2],
                ]
            ],
            dtype=torch.float64,
        ),
        provenance=_provenance("term-result-ligand-source", "a" * 64),
    )


def _receptor() -> AllAtomSystem:
    coordinates = (
        [0.0, 0.0, 0.0],
        [5.0, 0.0, 0.0],
        [8.0, 7.0, 4.0],
        [-8.0, -7.0, -4.0],
    )
    return AllAtomSystem(
        system_id="term-result-receptor",
        atoms=tuple(
            Atom(
                index=index,
                name=f"R{index}",
                element="C",
                atomic_number=6,
                residue_index=0,
            )
            for index in range(len(coordinates))
        ),
        bonds=(),
        residues=(
            Residue(
                index=0,
                name="REC",
                chain_index=0,
                sequence_number=1,
                atom_indices=tuple(range(len(coordinates))),
            ),
        ),
        chains=(Chain(index=0, chain_id="A", residue_indices=(0,)),),
        coordinates=torch.tensor([coordinates], dtype=torch.float64),
        provenance=_provenance("term-result-receptor-source", "b" * 64),
    )


def _authority(
    center: tuple[float, float, float] = (2.5, 2.0, 0.0),
):
    pocket = PocketDefinition(
        scope=DockingScope.KNOWN_POCKET,
        method_id="term-result-test-sphere",
        method_version="1.0.0",
        coordinate_frame_id="prepared-receptor-frame-v1",
        center=torch.tensor(center, dtype=torch.float64),
        radius_angstrom=12.0,
        source_artifact_sha256="c" * 64,
        implementation_source_sha256="d" * 64,
    )
    return build_element_aware_authenticated_known_pocket_docking_problem(
        _receptor(),
        _ligand(),
        pocket,
        receptor_margin_angstrom=4.0,
    )


def _budget() -> DockingBudget:
    return DockingBudget(
        candidate_count=6,
        top_k=3,
        max_torsions=1,
        translation_radius_angstrom=2.0,
        seed=127,
    )


def _scorer(authority):
    return InterpretablePoseScorerV0(
        authority,
        implementation_source_sha256="e" * 64,
    )


def test_successful_rows_retain_bit_exact_term_decomposition() -> None:
    authority = _authority()
    scorer = _scorer(authority)
    result = run_authenticated_interpretable_pocket_search(
        authority,
        _budget(),
        scorer,
        diversity_rmsd_angstrom=0.0,
        diversity_metric="symmetry_aware_direct_rmsd",
        symmetry_permutations=((0, 1, 2, 3),),
    )
    search_rows = (
        result.placement_search_result.authenticated_search_result.search_result.rows
    )
    assert len(result.rows) == len(search_rows) == _budget().candidate_count
    assert result.success_count == sum(row.succeeded for row in search_rows)
    assert result.failure_count == len(result.rows) - result.success_count
    for retained, source in zip(result.rows, search_rows, strict=True):
        assert retained.candidate_id == source.candidate_id
        assert retained.proposal_index == source.proposal_index
        assert retained.search_status == source.status
        if source.succeeded:
            assert retained.terms is not None
            assert retained.score is not None
            assert retained.score.hex() == retained.terms.total_score.hex()
            assert retained.terms.proposal_fingerprint_sha256 == (
                source.proposal.fingerprint_sha256
            )
        else:
            assert retained.terms is None
            assert retained.score is None
    document = result.to_dict()
    assert document["failure_rows_retained"] is True
    assert document["calibrated"] is False
    assert document["validated_for_docking_ranking"] is False
    assert document["claim_safe"] is False
    assert len(result.receipt_sha256) == 64


class _FailingScorer(InterpretablePoseScorerV0):
    def score(self, proposal):
        if proposal.proposal_index == 1:
            raise RuntimeError("intentional candidate failure")
        return super().score(proposal)


def test_failed_candidate_remains_without_fabricated_terms() -> None:
    authority = _authority()
    scorer = _FailingScorer(
        authority,
        implementation_source_sha256="f" * 64,
    )
    result = run_authenticated_interpretable_pocket_search(
        authority,
        _budget(),
        scorer,
        diversity_rmsd_angstrom=0.0,
    )
    failed = [row for row in result.rows if row.proposal_index == 1]
    assert len(failed) == 1
    row = failed[0]
    assert row.search_status == "failure"
    assert row.score is None
    assert row.terms is None
    assert row.selection_eligible is False
    assert row.error_code
    assert result.failure_count >= 1


def test_scorer_authority_cross_wiring_is_rejected_before_search() -> None:
    authority = _authority()
    other = _authority(center=(3.5, 2.0, 0.0))
    scorer = _scorer(other)
    with pytest.raises(
        InterpretableSearchResultError,
        match="cross-wired",
    ):
        run_authenticated_interpretable_pocket_search(
            authority,
            _budget(),
            scorer,
        )


def test_term_row_rejects_a_scalar_that_disagrees_with_terms() -> None:
    authority = _authority()
    scorer = _scorer(authority)
    result = run_authenticated_interpretable_pocket_search(
        authority,
        _budget(),
        scorer,
        diversity_rmsd_angstrom=0.0,
    )
    successful = next(row for row in result.rows if row.succeeded)
    assert successful.terms is not None
    assert successful.score is not None
    with pytest.raises(
        InterpretableSearchResultError,
        match="bit-exactly",
    ):
        InterpretableSearchTermRow(
            candidate_id=successful.candidate_id,
            proposal_index=successful.proposal_index,
            search_status="success",
            search_row_sha256=successful.search_row_sha256,
            score=successful.score + 1.0,
            selection_eligible=successful.selection_eligible,
            terms=successful.terms,
        )
