from __future__ import annotations

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2.docking import (  # noqa: E402
    DOCKING_SCORE_BREAKDOWN_SCHEMA_ID,
    DockingBudget,
    DockingProblemIdentity,
    DockingScoreBreakdown,
    DockingScoreDescriptor,
    DockingScoreTerm,
    DockingScoringError,
    ScoreDirection,
    TorsionSearchSpace,
    run_bounded_docking_search,
)


def _space() -> TorsionSearchSpace:
    return TorsionSearchSpace(
        local_offsets=torch.tensor(
            [[0.0, 0.0, 0.0], [1.2, 0.0, 0.0], [0.8, 0.6, 0.0]],
            dtype=torch.float64,
        ),
        parent=torch.tensor([-1, 0, 1], dtype=torch.long),
        local_axes=torch.tensor([[0.0, 0.0, 1.0]] * 3, dtype=torch.float64),
        rotatable_mask=torch.tensor([False, False, True]),
    )


def _problem() -> DockingProblemIdentity:
    return DockingProblemIdentity.unbound()


_PROBLEM_FINGERPRINT = _problem().fingerprint_sha256


class _DecomposedScorer:
    scorer_id = "decomposed-test-scorer"
    scorer_version = "1.0.0"
    validated_for_docking_ranking = False
    problem_fingerprint_sha256 = _PROBLEM_FINGERPRINT
    implementation_source_sha256 = "f" * 64
    config_fingerprint_sha256 = "d" * 64
    score_descriptor = DockingScoreDescriptor(
        score_id="decomposed_test_score",
        direction=ScoreDirection.MINIMIZE,
        unit="kcal/mol",
        semantics="unit_test_weighted_term_sum",
        calibrated=False,
    )

    def score(self, proposal):
        coordinate_sum = float(proposal.coordinates.sum().item())
        return DockingScoreBreakdown(
            terms=(
                DockingScoreTerm(
                    term_id="coordinate_sum",
                    raw_value=coordinate_sum,
                    weight=0.5,
                    unit="kcal/mol",
                    semantics="unit_test_coordinate_sum_proxy",
                    parameter_source_sha256="e" * 64,
                ),
                DockingScoreTerm(
                    term_id="constant_offset",
                    raw_value=1.25,
                    weight=1.0,
                    unit="kcal/mol",
                    semantics="unit_test_constant_offset",
                ),
            ),
            blockers=("unit_test_score_not_calibrated",),
        )


class _IncompleteScorer(_DecomposedScorer):
    scorer_id = "incomplete-decomposed-test-scorer"

    def score(self, proposal):
        del proposal
        return DockingScoreBreakdown(
            terms=(
                DockingScoreTerm(
                    term_id="partial",
                    raw_value=1.0,
                    weight=1.0,
                    unit="kcal/mol",
                    semantics="intentionally_incomplete_unit_test_term",
                ),
            ),
            complete=False,
            blockers=("required_term_missing",),
        )


def test_term_breakdown_is_atomic_ranked_and_serialized_per_candidate() -> None:
    result = run_bounded_docking_search(
        _space(),
        DockingBudget(candidate_count=4, top_k=2, max_torsions=1, seed=19),
        _DecomposedScorer(),
        problem=_problem(),
        diversity_rmsd_angstrom=0.0,
    )

    assert result.success_count == 4
    assert "score_term_decomposition_missing" not in result.blockers
    for row in result.rows:
        assert row.score_breakdown is not None
        assert row.score == pytest.approx(row.score_breakdown.total_score)
        payload = row.to_dict()["score_breakdown"]
        assert payload["schema_id"] == DOCKING_SCORE_BREAKDOWN_SCHEMA_ID
        assert payload["total_score"] == pytest.approx(row.score)
        assert [term["term_id"] for term in payload["terms"]] == [
            "coordinate_sum",
            "constant_offset",
        ]
        assert payload["terms"][0]["contribution"] == pytest.approx(
            0.5 * payload["terms"][0]["raw_value"]
        )


def test_incomplete_breakdown_fails_each_candidate_without_dropping_rows() -> None:
    result = run_bounded_docking_search(
        _space(),
        DockingBudget(candidate_count=3, top_k=1, max_torsions=1),
        _IncompleteScorer(),
        problem=_problem(),
    )

    assert result.success_count == 0
    assert result.failure_count == 3
    assert len(result.rows) == 3
    assert all(row.score_breakdown is None for row in result.rows)
    assert all(row.error_code == "DockingSearchError" for row in result.rows)


def test_breakdown_rejects_duplicate_terms_nonfinite_values_and_bad_digests() -> None:
    term = DockingScoreTerm(
        term_id="one",
        raw_value=1.0,
        weight=1.0,
        unit=None,
        semantics="unit_test_term",
    )
    with pytest.raises(DockingScoringError, match="unique"):
        DockingScoreBreakdown(terms=(term, term))
    with pytest.raises(DockingScoringError, match="finite"):
        DockingScoreTerm(
            term_id="bad",
            raw_value=float("nan"),
            weight=1.0,
            unit=None,
            semantics="unit_test_term",
        )
    with pytest.raises(DockingScoringError, match="SHA-256"):
        DockingScoreTerm(
            term_id="bad",
            raw_value=1.0,
            weight=1.0,
            unit=None,
            semantics="unit_test_term",
            parameter_source_sha256="not-a-digest",
        )


def test_breakdown_unit_mismatch_becomes_failure_rows() -> None:
    class _WrongUnitScorer(_DecomposedScorer):
        scorer_id = "wrong-unit-test-scorer"

        def score(self, proposal):
            del proposal
            return DockingScoreBreakdown(
                terms=(
                    DockingScoreTerm(
                        term_id="wrong_unit",
                        raw_value=1.0,
                        weight=1.0,
                        unit=None,
                        semantics="unit_test_wrong_unit",
                    ),
                )
            )

    result = run_bounded_docking_search(
        _space(),
        DockingBudget(candidate_count=2, top_k=1, max_torsions=1),
        _WrongUnitScorer(),
        problem=_problem(),
    )
    assert result.failure_count == 2
    assert all(row.error_code == "DockingSearchError" for row in result.rows)
