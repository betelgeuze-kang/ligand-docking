from __future__ import annotations

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2.docking import (  # noqa: E402
    DockingBudget,
    DockingProblemIdentity,
    PoseValidityConfig,
    PoseValidityContext,
    TorsionSearchSpace,
    generate_bounded_docking_proposals,
    run_bounded_docking_search,
)
from betelgeuze_engine_v2.docking.proposals import (  # noqa: E402
    DockingProposalError,
)


def _problem(marker: str = "a", *, metadata=None) -> DockingProblemIdentity:
    return DockingProblemIdentity(
        receptor_system_sha256=marker * 64,
        ligand_system_sha256=("b" if marker == "a" else "d") * 64,
        pocket_definition_sha256="c" * 64,
        metadata={} if metadata is None else metadata,
    )


def _space() -> TorsionSearchSpace:
    return TorsionSearchSpace(
        local_offsets=torch.tensor(
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 0.4, 0.0]],
            dtype=torch.float64,
        ),
        parent=torch.tensor([-1, 0, 1], dtype=torch.long),
        local_axes=torch.tensor([[0.0, 0.0, 1.0]] * 3, dtype=torch.float64),
        rotatable_mask=torch.tensor([False, False, True]),
    )


def _validity_context(problem: DockingProblemIdentity) -> PoseValidityContext:
    reference = generate_bounded_docking_proposals(
        _space(),
        DockingBudget(candidate_count=1, top_k=1, max_torsions=1),
        problem=problem,
    )[0].coordinates
    return PoseValidityContext(
        problem_fingerprint_sha256=problem.fingerprint_sha256,
        reference_coordinates=reference,
        bond_pairs=((0, 1), (1, 2)),
        excluded_nonbonded_pairs=((0, 1), (1, 2)),
        receptor_coordinates=torch.tensor(
            [[100.0, 100.0, 100.0]], dtype=torch.float64
        ),
        pocket_center=reference.mean(dim=0),
        chirality_centers=(),
        config=PoseValidityConfig(pocket_radius_angstrom=20.0),
    )


class _BoundScorer:
    scorer_id = "bound-integrity-scorer"
    scorer_version = "1.0.0"
    validated_for_docking_ranking = False
    implementation_source_sha256 = "e" * 64
    config_fingerprint_sha256 = "f" * 64

    def __init__(self, problem: DockingProblemIdentity) -> None:
        self.problem_fingerprint_sha256 = problem.fingerprint_sha256
        self.call_count = 0

    def score(self, proposal):
        self.call_count += 1
        return proposal.coordinates.square().sum()


class _MutatingScorer(_BoundScorer):
    scorer_id = "mutating-integrity-scorer"

    def score(self, proposal):
        self.call_count += 1
        proposal.coordinates.add_(1.0)
        return 0.0


class _MutatingRefiner:
    refiner_id = "mutating-integrity-refiner"
    refiner_version = "1.0.0"
    implementation_source_sha256 = "1" * 64
    config_fingerprint_sha256 = "2" * 64

    def __init__(self, problem: DockingProblemIdentity) -> None:
        self.problem_fingerprint_sha256 = problem.fingerprint_sha256

    def refine(self, proposal, *, max_steps):
        del max_steps
        proposal.coordinates.mul_(2.0)
        return proposal


def test_problem_metadata_is_recursively_frozen_and_copied() -> None:
    source = {"nested": {"values": [1, 2]}, "label": "fixture"}
    problem = _problem(metadata=source)
    fingerprint = problem.fingerprint_sha256

    source["nested"]["values"].append(3)
    source["label"] = "changed"

    assert problem.fingerprint_sha256 == fingerprint
    assert problem.to_dict()["metadata"] == {
        "label": "fixture",
        "nested": {"values": [1, 2]},
    }
    with pytest.raises(TypeError):
        problem.metadata["label"] = "forbidden"


def test_search_space_clones_callers_tensors_and_detects_internal_mutation() -> None:
    local_offsets = torch.tensor(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]], dtype=torch.float64
    )
    space = TorsionSearchSpace(
        local_offsets=local_offsets,
        parent=torch.tensor([-1, 0], dtype=torch.long),
        local_axes=torch.tensor([[0.0, 0.0, 1.0]] * 2, dtype=torch.float64),
        rotatable_mask=torch.tensor([False, False]),
    )
    fingerprint = space.fingerprint_sha256

    local_offsets[1, 0] = 9.0
    assert space.fingerprint_sha256 == fingerprint

    space.local_offsets[1, 0] = 8.0
    with pytest.raises(
        DockingProposalError,
        match="search-space tensors changed",
    ):
        space.assert_integrity()


def test_proposal_clones_generated_tensors_and_detects_internal_mutation() -> None:
    proposal = generate_bounded_docking_proposals(
        _space(),
        DockingBudget(candidate_count=1, top_k=1, max_torsions=1),
        problem=_problem(),
    )[0]
    proposal.assert_integrity()

    proposal.coordinates[0, 0] += 0.5
    with pytest.raises(
        DockingProposalError,
        match="coordinates changed after construction",
    ):
        proposal.assert_integrity()


def test_bound_problem_rejects_cross_wired_scorer_before_any_candidate() -> None:
    active = _problem("a")
    scorer = _BoundScorer(_problem("d"))

    with pytest.raises(ValueError, match="active docking problem"):
        run_bounded_docking_search(
            _space(),
            DockingBudget(candidate_count=2, top_k=1, max_torsions=1),
            scorer,
            validity_context=_validity_context(active),
            problem=active,
        )

    assert scorer.call_count == 0


def test_scorer_in_place_mutation_becomes_failure_rows_not_success() -> None:
    problem = _problem()
    scorer = _MutatingScorer(problem)
    result = run_bounded_docking_search(
        _space(),
        DockingBudget(candidate_count=2, top_k=1, max_torsions=1),
        scorer,
        validity_context=_validity_context(problem),
        problem=problem,
    )

    assert result.success_count == 0
    assert result.failure_count == 2
    assert all(row.error_code == "DockingProposalError" for row in result.rows)
    assert result.top_rows == ()


def test_refiner_in_place_mutation_becomes_failure_rows_not_success() -> None:
    problem = _problem()
    result = run_bounded_docking_search(
        _space(),
        DockingBudget(
            candidate_count=2,
            top_k=1,
            max_torsions=1,
            max_refinement_steps=1,
        ),
        _BoundScorer(problem),
        refiner=_MutatingRefiner(problem),
        validity_context=_validity_context(problem),
        problem=problem,
    )

    assert result.success_count == 0
    assert result.failure_count == 2
    assert all(row.error_code == "DockingProposalError" for row in result.rows)


def test_component_source_identity_changes_the_search_fingerprint() -> None:
    problem = _problem()
    context = _validity_context(problem)
    first_scorer = _BoundScorer(problem)
    second_scorer = _BoundScorer(problem)
    second_scorer.implementation_source_sha256 = "9" * 64
    budget = DockingBudget(candidate_count=2, top_k=1, max_torsions=1)

    first = run_bounded_docking_search(
        _space(),
        budget,
        first_scorer,
        validity_context=context,
        problem=problem,
    )
    second = run_bounded_docking_search(
        _space(),
        budget,
        second_scorer,
        validity_context=context,
        problem=problem,
    )

    assert (
        first.scorer_contract_fingerprint_sha256
        != second.scorer_contract_fingerprint_sha256
    )
    assert first.search_fingerprint_sha256 != second.search_fingerprint_sha256
