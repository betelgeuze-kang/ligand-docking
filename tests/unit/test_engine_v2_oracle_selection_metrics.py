from __future__ import annotations

import pytest

from betelgeuze_engine_v2.benchmark.oracle_selection_metrics import (
    CandidateObservation,
    OracleSelectionError,
    evaluate_oracle_selection,
)


def _row(
    index: int,
    *,
    score: float,
    rmsd: float | None,
    valid: bool,
) -> CandidateObservation:
    return CandidateObservation(
        proposal_index=index,
        score=score,
        rmsd_angstrom=rmsd,
        valid=valid,
    )


def test_success_separates_generation_and_selection_metrics() -> None:
    report = evaluate_oracle_selection(
        (
            _row(0, score=-5.0, rmsd=1.2, valid=True),
            _row(1, score=-4.0, rmsd=0.8, valid=True),
            _row(2, score=-3.0, rmsd=5.0, valid=True),
        ),
        top_ks=(1, 2, 3),
    )

    assert report.failure_class == "success"
    assert report.proposal_oracle_index == 1
    assert report.proposal_oracle_rmsd_angstrom == pytest.approx(0.8)
    assert report.selected_top1_index == 0
    assert report.selected_top1_success is True
    assert report.selection_regret_angstrom == pytest.approx(0.4)
    assert report.ranked_oracles[0].valid_near_native_present is True


def test_proposal_failure_means_no_near_native_candidate_was_generated() -> None:
    report = evaluate_oracle_selection(
        (
            _row(0, score=-5.0, rmsd=4.0, valid=True),
            _row(1, score=-4.0, rmsd=3.0, valid=True),
        )
    )

    assert report.failure_class == "proposal_failure"
    assert report.proposal_oracle_success is False
    assert report.valid_proposal_oracle_success is False


def test_validity_failure_is_distinct_from_proposal_failure() -> None:
    report = evaluate_oracle_selection(
        (
            _row(0, score=-5.0, rmsd=1.0, valid=False),
            _row(1, score=-4.0, rmsd=4.0, valid=True),
        )
    )

    assert report.proposal_oracle_success is True
    assert report.valid_proposal_oracle_success is False
    assert report.failure_class == "validity_failure"


def test_ranking_failure_preserves_successful_proposal_oracle() -> None:
    report = evaluate_oracle_selection(
        (
            _row(0, score=-10.0, rmsd=6.0, valid=True),
            _row(1, score=-2.0, rmsd=1.0, valid=True),
            _row(2, score=-1.0, rmsd=5.0, valid=True),
        ),
        top_ks=(1, 2),
    )

    assert report.proposal_oracle_success is True
    assert report.valid_proposal_oracle_success is True
    assert report.selected_top1_success is False
    assert report.failure_class == "ranking_failure"
    assert report.ranked_oracles[0].valid_near_native_present is False
    assert report.ranked_oracles[1].valid_near_native_present is True
    assert report.selection_regret_angstrom == pytest.approx(5.0)


def test_score_ties_break_by_proposal_index() -> None:
    report = evaluate_oracle_selection(
        (
            _row(0, score=-5.0, rmsd=4.0, valid=True),
            _row(1, score=-5.0, rmsd=1.0, valid=True),
        )
    )

    assert report.selected_top1_index == 0
    assert report.failure_class == "ranking_failure"


def test_missing_rmsd_remains_in_denominator() -> None:
    report = evaluate_oracle_selection(
        (
            _row(0, score=-5.0, rmsd=None, valid=False),
            _row(1, score=-4.0, rmsd=1.0, valid=True),
        )
    )

    assert report.candidate_count == 2
    assert report.evaluated_rmsd_count == 1
    assert report.failure_class == "ranking_failure"


def test_noncontiguous_proposal_indices_fail_closed() -> None:
    with pytest.raises(OracleSelectionError, match="contiguous"):
        evaluate_oracle_selection(
            (
                _row(0, score=-5.0, rmsd=1.0, valid=True),
                _row(2, score=-4.0, rmsd=2.0, valid=True),
            )
        )
