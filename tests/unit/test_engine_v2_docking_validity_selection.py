from __future__ import annotations

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2.docking import (  # noqa: E402
    DockingBudget,
    DockingProblemIdentity,
    DockingScoreDescriptor,
    PoseValidityConfig,
    PoseValidityContext,
    ScoreDirection,
    TorsionSearchSpace,
    generate_bounded_docking_proposals,
    run_bounded_docking_search,
)


def _problem(marker: str = "a") -> DockingProblemIdentity:
    return DockingProblemIdentity(
        receptor_system_sha256=marker * 64,
        ligand_system_sha256=("b" if marker == "a" else "d") * 64,
        pocket_definition_sha256="c" * 64,
    )


def _space() -> TorsionSearchSpace:
    return TorsionSearchSpace(
        local_offsets=torch.tensor(
            [
                [0.0, 0.0, 0.0],
                [1.2, 0.0, 0.0],
                [1.0, 0.5, 0.0],
                [0.8, 0.5, 0.4],
            ],
            dtype=torch.float64,
        ),
        parent=torch.tensor([-1, 0, 1, 2], dtype=torch.long),
        local_axes=torch.tensor([[0.0, 0.0, 1.0]] * 4, dtype=torch.float64),
        rotatable_mask=torch.tensor([False, False, True, True]),
    )


def _reference(problem: DockingProblemIdentity | None = None) -> torch.Tensor:
    return generate_bounded_docking_proposals(
        _space(),
        DockingBudget(candidate_count=1, top_k=1, max_torsions=2),
        problem=problem or _problem(),
    )[0].coordinates


def _context(
    *,
    problem: DockingProblemIdentity | None = None,
    receptor_coordinates: torch.Tensor | None = None,
    pocket_center: torch.Tensor | None = None,
    pocket_radius: float = 20.0,
    chirality_centers: tuple[tuple[int, int, int, int], ...] = (),
    excluded_nonbonded_pairs: tuple[tuple[int, int], ...] = (
        (0, 1),
        (1, 2),
        (2, 3),
    ),
) -> PoseValidityContext:
    active_problem = problem or _problem()
    reference = _reference(active_problem)
    return PoseValidityContext(
        problem_fingerprint_sha256=active_problem.fingerprint_sha256,
        reference_coordinates=reference,
        bond_pairs=((0, 1), (1, 2), (2, 3)),
        excluded_nonbonded_pairs=excluded_nonbonded_pairs,
        receptor_coordinates=(
            torch.tensor([[100.0, 100.0, 100.0]], dtype=torch.float64)
            if receptor_coordinates is None
            else receptor_coordinates
        ),
        pocket_center=(
            reference.mean(dim=0) if pocket_center is None else pocket_center
        ),
        chirality_centers=chirality_centers,
        config=PoseValidityConfig(pocket_radius_angstrom=pocket_radius),
    )


class _IndexScorer:
    scorer_id = "validity-index-scorer"
    scorer_version = "1.0.0"
    validated_for_docking_ranking = False
    implementation_source_sha256 = "e" * 64
    config_fingerprint_sha256 = "f" * 64
    score_descriptor = DockingScoreDescriptor(
        score_id="proposal_index",
        direction=ScoreDirection.MINIMIZE,
        unit=None,
        semantics="unit_test_proposal_index",
        calibrated=False,
    )

    def __init__(self, problem: DockingProblemIdentity) -> None:
        self.problem_fingerprint_sha256 = problem.fingerprint_sha256

    def score(self, proposal):
        return float(proposal.proposal_index)


class _MirrorFirstRefiner:
    refiner_id = "mirror-first-refiner"
    refiner_version = "1.0.0"
    implementation_source_sha256 = "1" * 64
    config_fingerprint_sha256 = "2" * 64

    def __init__(self, problem: DockingProblemIdentity) -> None:
        self.problem_fingerprint_sha256 = problem.fingerprint_sha256

    def refine(self, proposal, *, max_steps):
        del max_steps
        coordinates = proposal.coordinates.clone()
        if proposal.proposal_index == 0:
            coordinates[:, 2] *= -1.0
        return proposal.with_refined_coordinates(
            coordinates,
            refiner_id=self.refiner_id,
            refiner_version=self.refiner_version,
        )


class _ClashFirstRefiner(_MirrorFirstRefiner):
    refiner_id = "clash-first-refiner"

    def refine(self, proposal, *, max_steps):
        del max_steps
        coordinates = proposal.coordinates.clone()
        if proposal.proposal_index == 0:
            coordinates[:] = torch.tensor(
                [0.0, 0.0, 0.0], dtype=coordinates.dtype
            )
        return proposal.with_refined_coordinates(
            coordinates,
            refiner_id=self.refiner_id,
            refiner_version=self.refiner_version,
        )


class _OutsideFirstRefiner(_MirrorFirstRefiner):
    refiner_id = "outside-first-refiner"

    def refine(self, proposal, *, max_steps):
        del max_steps
        coordinates = proposal.coordinates.clone()
        if proposal.proposal_index == 0:
            coordinates += 100.0
        return proposal.with_refined_coordinates(
            coordinates,
            refiner_id=self.refiner_id,
            refiner_version=self.refiner_version,
        )


def _run_with_refiner(refiner_type, *, context: PoseValidityContext):
    problem = _problem()
    return run_bounded_docking_search(
        _space(),
        DockingBudget(
            candidate_count=3,
            top_k=1,
            max_torsions=2,
            max_refinement_steps=1,
            seed=17,
        ),
        _IndexScorer(problem),
        refiner=refiner_type(problem),
        validity_context=context,
        problem=problem,
        diversity_rmsd_angstrom=0.0,
    )


def test_bound_problem_requires_validity_context_before_scoring() -> None:
    problem = _problem()
    scorer = _IndexScorer(problem)

    with pytest.raises(
        RuntimeError,
        match="require a complete pose validity context",
    ):
        run_bounded_docking_search(
            _space(),
            DockingBudget(candidate_count=2, top_k=1, max_torsions=2),
            scorer,
            problem=problem,
        )


def test_cross_wired_validity_context_fails_before_scoring() -> None:
    active_problem = _problem("a")
    other_problem = _problem("d")

    with pytest.raises(RuntimeError, match="does not match"):
        run_bounded_docking_search(
            _space(),
            DockingBudget(candidate_count=2, top_k=1, max_torsions=2),
            _IndexScorer(active_problem),
            validity_context=_context(problem=other_problem),
            problem=active_problem,
        )


def test_highest_ranked_mirrored_pose_is_retained_but_not_selected() -> None:
    result = _run_with_refiner(
        _MirrorFirstRefiner,
        context=_context(chirality_centers=((1, 0, 2, 3),)),
    )

    first = result.rows[0]
    assert first.succeeded
    assert first.pose_validity is not None
    assert not first.pose_validity.valid
    assert "declared_chirality_not_preserved" in first.pose_validity.blockers
    assert first.selection_eligible is False
    assert result.top_rows[0].proposal_index != 0
    assert "invalid_pose_candidates_present" in result.blockers


def test_highest_ranked_clashing_pose_is_retained_but_not_selected() -> None:
    result = _run_with_refiner(
        _ClashFirstRefiner,
        context=_context(),
    )

    first = result.rows[0]
    assert first.pose_validity is not None
    assert not first.pose_validity.valid
    assert first.selection_eligible is False
    assert result.top_rows[0].proposal_index != 0


def test_highest_ranked_out_of_pocket_pose_is_retained_but_not_selected() -> None:
    result = _run_with_refiner(
        _OutsideFirstRefiner,
        context=_context(pocket_radius=10.0),
    )

    first = result.rows[0]
    assert first.pose_validity is not None
    assert "pose_outside_declared_pocket" in first.pose_validity.blockers
    assert first.selection_eligible is False
    assert result.top_rows[0].proposal_index != 0


def test_explicit_nonbonded_exclusions_prevent_false_self_clash() -> None:
    problem = _problem()
    reference = _reference(problem)
    context = PoseValidityContext(
        problem_fingerprint_sha256=problem.fingerprint_sha256,
        reference_coordinates=reference,
        bond_pairs=((0, 1), (1, 2), (2, 3)),
        excluded_nonbonded_pairs=(
            (0, 1),
            (1, 2),
            (2, 3),
            (0, 2),
            (1, 3),
        ),
        receptor_coordinates=torch.tensor(
            [[100.0, 100.0, 100.0]], dtype=torch.float64
        ),
        pocket_center=reference.mean(dim=0),
        chirality_centers=(),
        config=PoseValidityConfig(
            pocket_radius_angstrom=20.0,
            ligand_self_clash_angstrom=2.5,
        ),
    )
    result = run_bounded_docking_search(
        _space(),
        DockingBudget(candidate_count=1, top_k=1, max_torsions=2),
        _IndexScorer(problem),
        validity_context=context,
        problem=problem,
    )

    assert result.rows[0].pose_validity is not None
    assert result.rows[0].pose_validity.checks["ligand_self_clash_free"]
    assert result.rows[0].selection_eligible


def test_validity_context_changes_search_identity() -> None:
    problem = _problem()
    budget = DockingBudget(candidate_count=2, top_k=1, max_torsions=2)
    first = run_bounded_docking_search(
        _space(),
        budget,
        _IndexScorer(problem),
        validity_context=_context(problem=problem, pocket_radius=20.0),
        problem=problem,
    )
    second = run_bounded_docking_search(
        _space(),
        budget,
        _IndexScorer(problem),
        validity_context=_context(problem=problem, pocket_radius=21.0),
        problem=problem,
    )

    assert (
        first.validity_context_fingerprint_sha256
        != second.validity_context_fingerprint_sha256
    )
    assert first.search_fingerprint_sha256 != second.search_fingerprint_sha256
