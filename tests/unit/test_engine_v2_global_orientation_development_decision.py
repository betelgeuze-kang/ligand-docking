from __future__ import annotations

from dataclasses import replace

import pytest

from betelgeuze_engine_v2.benchmark.global_orientation_development_decision import (
    CASE_IDS,
    CaseComparisonObservation,
    GlobalOrientationDevelopmentDecisionError,
    evaluate_global_orientation_development,
)


_INVALID_BASELINE_TOP1 = {
    "5SD5_HWI",
    "5SIS_JSM",
    "6M2B_EZO",
    "6TW5_9M2",
    "6TW7_NZB",
}


def _rows() -> tuple[CaseComparisonObservation, ...]:
    rows: list[CaseComparisonObservation] = []
    for case_id in CASE_IDS:
        if case_id == "6M73_FNR":
            rows.append(
                CaseComparisonObservation(
                    case_id=case_id,
                    baseline_preparation_succeeded=False,
                    experimental_preparation_succeeded=False,
                    baseline_candidate_count=0,
                    experimental_candidate_count=0,
                    baseline_valid_proposal_oracle_rmsd=None,
                    experimental_valid_proposal_oracle_rmsd=None,
                    baseline_selected_top1_rmsd=None,
                    experimental_selected_top1_rmsd=None,
                    baseline_selected_top1_valid=None,
                    experimental_selected_top1_valid=None,
                    source_geometry_evidence_complete=True,
                    observation_evidence_complete=True,
                )
            )
            continue
        baseline_top1_valid = case_id not in _INVALID_BASELINE_TOP1
        baseline_top1_rmsd = 1.5 if case_id == "6T88_MWQ" else 4.0
        rows.append(
            CaseComparisonObservation(
                case_id=case_id,
                baseline_preparation_succeeded=True,
                experimental_preparation_succeeded=True,
                baseline_candidate_count=64,
                experimental_candidate_count=64,
                baseline_valid_proposal_oracle_rmsd=(
                    1.5 if case_id == "6T88_MWQ" else 3.0
                ),
                experimental_valid_proposal_oracle_rmsd=(
                    1.5 if case_id == "6T88_MWQ" else 3.0
                ),
                baseline_selected_top1_rmsd=baseline_top1_rmsd,
                experimental_selected_top1_rmsd=baseline_top1_rmsd,
                baseline_selected_top1_valid=baseline_top1_valid,
                experimental_selected_top1_valid=baseline_top1_valid,
                source_geometry_evidence_complete=True,
                observation_evidence_complete=True,
            )
        )
    return tuple(rows)


def _replace_case(
    rows: tuple[CaseComparisonObservation, ...],
    case_id: str,
    **changes: object,
) -> tuple[CaseComparisonObservation, ...]:
    return tuple(
        replace(row, **changes) if row.case_id == case_id else row
        for row in rows
    )


def test_two_new_valid_proposal_recoveries_produce_bounded_go() -> None:
    rows = _replace_case(
        _rows(),
        "5SD5_HWI",
        experimental_valid_proposal_oracle_rmsd=1.5,
    )
    rows = _replace_case(
        rows,
        "5SIS_JSM",
        experimental_valid_proposal_oracle_rmsd=1.8,
    )

    decision = evaluate_global_orientation_development(rows)

    assert decision.verdict == "go"
    assert decision.new_valid_proposal_recovery_case_ids == (
        "5SD5_HWI",
        "5SIS_JSM",
    )
    assert decision.hard_no_go_triggers == ()
    assert decision.to_dict()["fresh_holdout_execution_authorized"] is False
    assert decision.to_dict()["product_execution_authorized"] is False
    assert decision.to_dict()["public_or_scientific_claim_authorized"] is False
    assert len(decision.receipt_sha256) == 64


def test_zero_new_recoveries_is_hard_no_go() -> None:
    decision = evaluate_global_orientation_development(_rows())

    assert decision.verdict == "no_go"
    assert (
        "zero_new_previously_uncovered_valid_proposal_recoveries"
        in decision.hard_no_go_triggers
    )


def test_one_new_recovery_does_not_meet_breadth_criterion() -> None:
    rows = _replace_case(
        _rows(),
        "5SD5_HWI",
        experimental_valid_proposal_oracle_rmsd=1.5,
    )

    decision = evaluate_global_orientation_development(rows)

    assert decision.verdict == "no_go"
    assert decision.hard_no_go_triggers == ()
    assert (
        "valid_proposal_oracle_recovery_in_at_least_2_of_7_"
        "previously_uncovered_cases"
        not in decision.go_criteria
    )


def test_baseline_recovered_case_regression_is_hard_no_go() -> None:
    rows = _replace_case(
        _rows(),
        "5SD5_HWI",
        experimental_valid_proposal_oracle_rmsd=1.5,
    )
    rows = _replace_case(
        rows,
        "5SIS_JSM",
        experimental_valid_proposal_oracle_rmsd=1.8,
    )
    rows = _replace_case(
        rows,
        "6T88_MWQ",
        experimental_selected_top1_rmsd=2.5,
    )

    decision = evaluate_global_orientation_development(rows)

    assert decision.verdict == "no_go"
    assert decision.baseline_recovered_regression_case_ids == ("6T88_MWQ",)
    assert "baseline_recovered_case_regression" in decision.hard_no_go_triggers


def test_incomplete_evidence_fails_an_invariant() -> None:
    rows = _replace_case(
        _rows(),
        "5SD5_HWI",
        experimental_valid_proposal_oracle_rmsd=1.5,
        source_geometry_evidence_complete=False,
    )
    rows = _replace_case(
        rows,
        "5SIS_JSM",
        experimental_valid_proposal_oracle_rmsd=1.8,
    )

    decision = evaluate_global_orientation_development(rows)

    assert decision.verdict == "no_go"
    assert "required_invariant_failed" in decision.hard_no_go_triggers
    assert (
        "complete_source_and_observation_rederivation"
        in decision.invariant_failures
    )


def test_invalid_selected_top1_increase_blocks_go_criterion() -> None:
    rows = _replace_case(
        _rows(),
        "5SD5_HWI",
        experimental_valid_proposal_oracle_rmsd=1.5,
    )
    rows = _replace_case(
        rows,
        "5SIS_JSM",
        experimental_valid_proposal_oracle_rmsd=1.8,
    )
    rows = _replace_case(
        rows,
        "6VTA_AKN",
        experimental_selected_top1_valid=False,
    )

    decision = evaluate_global_orientation_development(rows)

    assert decision.verdict == "no_go"
    assert decision.experimental_invalid_selected_top1_count == 6
    assert "no_increase_in_invalid_selected_top1_count" not in decision.go_criteria


def test_denominator_drift_fails_before_decision() -> None:
    row = next(row for row in _rows() if row.case_id == "5SD5_HWI")

    with pytest.raises(
        GlobalOrientationDevelopmentDecisionError,
        match="64-slot denominators",
    ):
        replace(row, experimental_candidate_count=63)


def test_order_or_roster_drift_fails_closed() -> None:
    rows = tuple(reversed(_rows()))

    with pytest.raises(
        GlobalOrientationDevelopmentDecisionError,
        match="exact ordered nine-case cohort",
    ):
        evaluate_global_orientation_development(rows)
