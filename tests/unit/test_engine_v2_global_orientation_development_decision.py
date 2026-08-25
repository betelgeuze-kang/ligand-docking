from __future__ import annotations

from dataclasses import replace
import hashlib

import pytest

from betelgeuze_engine_v2.benchmark import (
    source_paired_clearance_activation as activation,
)
from betelgeuze_engine_v2.benchmark.global_orientation_development_decision import (
    CASE_IDS,
    CaseComparisonObservation,
    GlobalOrientationDevelopmentDecisionError,
    evaluate_global_orientation_development,
)
from betelgeuze_engine_v2.benchmark.oracle_selection_evidence import (
    OracleSelectionEvidence,
    build_oracle_selection_evidence,
)
from betelgeuze_engine_v2.benchmark.oracle_selection_metrics import (
    CandidateObservation,
)
from betelgeuze_engine_v2.benchmark.source_paired_clearance_activation import (
    SourcePairedClearanceCaseSourceReceiptV1,
)


_INVALID_BASELINE_TOP1 = {
    "5SD5_HWI",
    "5SIS_JSM",
    "6M2B_EZO",
    "6TW5_9M2",
    "6TW7_NZB",
}


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def _source_receipt(case_id: str) -> SourcePairedClearanceCaseSourceReceiptV1:
    authority = activation._frozen_case_source_authority(case_id)
    assert authority is not None
    return SourcePairedClearanceCaseSourceReceiptV1(
        case_id=case_id,
        problem_fingerprint_sha256=_digest(f"problem:{case_id}"),
        **dict(authority),
    )


def _evidence(
    *,
    valid_oracle_rmsd: float | None,
    selected_rmsd: float | None,
    selected_valid: bool,
    candidate_count: int = 64,
) -> OracleSelectionEvidence:
    observations: list[CandidateObservation] = []
    for index in range(candidate_count):
        if index == 0:
            rmsd = selected_rmsd
            valid = selected_valid
        elif index == 1 and valid_oracle_rmsd is not None:
            rmsd = valid_oracle_rmsd
            valid = True
        else:
            rmsd = 5.0 + index / 100.0
            valid = False
        observations.append(
            CandidateObservation(
                proposal_index=index,
                score=float(index),
                rmsd_angstrom=rmsd,
                valid=valid,
            )
        )
    return build_oracle_selection_evidence(tuple(observations))


def _rows() -> tuple[CaseComparisonObservation, ...]:
    rows: list[CaseComparisonObservation] = []
    for case_id in CASE_IDS:
        if case_id == "6M73_FNR":
            rows.append(
                CaseComparisonObservation(
                    case_id=case_id,
                    case_source_receipt=None,
                    preparation_failure_receipt_sha256=_digest(
                        "preparation-failure:6M73_FNR"
                    ),
                    baseline_evidence=None,
                    experimental_evidence=None,
                )
            )
            continue
        baseline_top1_valid = case_id not in _INVALID_BASELINE_TOP1
        baseline_top1_rmsd = 1.5 if case_id == "6T88_MWQ" else 4.0
        baseline = _evidence(
            valid_oracle_rmsd=1.5 if case_id == "6T88_MWQ" else 3.0,
            selected_rmsd=baseline_top1_rmsd,
            selected_valid=baseline_top1_valid,
        )
        rows.append(
            CaseComparisonObservation(
                case_id=case_id,
                case_source_receipt=_source_receipt(case_id),
                preparation_failure_receipt_sha256=None,
                baseline_evidence=baseline,
                experimental_evidence=baseline,
            )
        )
    return tuple(rows)


def _replace_evidence(
    rows: tuple[CaseComparisonObservation, ...],
    case_id: str,
    *,
    arm: str,
    valid_oracle_rmsd: float | None,
    selected_rmsd: float,
    selected_valid: bool,
    candidate_count: int = 64,
) -> tuple[CaseComparisonObservation, ...]:
    field = f"{arm}_evidence"
    evidence = _evidence(
        valid_oracle_rmsd=valid_oracle_rmsd,
        selected_rmsd=selected_rmsd,
        selected_valid=selected_valid,
        candidate_count=candidate_count,
    )
    return tuple(
        replace(row, **{field: evidence}) if row.case_id == case_id else row
        for row in rows
    )


def _two_recoveries() -> tuple[CaseComparisonObservation, ...]:
    rows = _replace_evidence(
        _rows(),
        "5SD5_HWI",
        arm="experimental",
        valid_oracle_rmsd=1.5,
        selected_rmsd=4.0,
        selected_valid=False,
    )
    return _replace_evidence(
        rows,
        "5SIS_JSM",
        arm="experimental",
        valid_oracle_rmsd=1.8,
        selected_rmsd=4.0,
        selected_valid=False,
    )


def test_two_new_valid_proposal_recoveries_produce_bounded_go() -> None:
    decision = evaluate_global_orientation_development(_two_recoveries())

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
    rows = _replace_evidence(
        _rows(),
        "5SD5_HWI",
        arm="experimental",
        valid_oracle_rmsd=1.5,
        selected_rmsd=4.0,
        selected_valid=False,
    )
    decision = evaluate_global_orientation_development(rows)
    assert decision.verdict == "no_go"
    assert decision.hard_no_go_triggers == ()


def test_experimental_baseline_recovered_case_regression_is_hard_no_go() -> None:
    rows = _replace_evidence(
        _two_recoveries(),
        "6T88_MWQ",
        arm="experimental",
        valid_oracle_rmsd=1.5,
        selected_rmsd=2.5,
        selected_valid=True,
    )
    decision = evaluate_global_orientation_development(rows)
    assert decision.verdict == "no_go"
    assert decision.baseline_recovered_regression_case_ids == ("6T88_MWQ",)
    assert "baseline_recovered_case_regression" in decision.hard_no_go_triggers


def test_missing_evidence_fails_before_decision() -> None:
    row = next(row for row in _rows() if row.case_id == "5SD5_HWI")
    with pytest.raises(
        GlobalOrientationDevelopmentDecisionError,
        match="complete oracle-selection evidence",
    ):
        replace(row, baseline_evidence=None)


def test_invalid_selected_top1_increase_blocks_go_criterion() -> None:
    rows = _replace_evidence(
        _two_recoveries(),
        "6VTA_AKN",
        arm="experimental",
        valid_oracle_rmsd=3.0,
        selected_rmsd=4.0,
        selected_valid=False,
    )
    decision = evaluate_global_orientation_development(rows)
    assert decision.verdict == "no_go"
    assert decision.experimental_invalid_selected_top1_count == 6
    assert "no_increase_in_invalid_selected_top1_count" not in decision.go_criteria


def test_denominator_drift_fails_before_decision() -> None:
    row = next(row for row in _rows() if row.case_id == "5SD5_HWI")
    with pytest.raises(
        GlobalOrientationDevelopmentDecisionError,
        match="fixed 64-slot protocol",
    ):
        replace(
            row,
            experimental_evidence=_evidence(
                valid_oracle_rmsd=3.0,
                selected_rmsd=4.0,
                selected_valid=False,
                candidate_count=63,
            ),
        )


def test_absent_valid_oracle_rmsd_is_a_no_go_observation() -> None:
    rows = _replace_evidence(
        _rows(),
        "5SD5_HWI",
        arm="experimental",
        valid_oracle_rmsd=None,
        selected_rmsd=4.0,
        selected_valid=False,
    )
    decision = evaluate_global_orientation_development(rows)
    assert decision.verdict == "no_go"
    assert "5SD5_HWI" not in decision.new_valid_proposal_recovery_case_ids


def test_baseline_recovery_must_be_reproduced() -> None:
    rows = _replace_evidence(
        _two_recoveries(),
        "6T88_MWQ",
        arm="baseline",
        valid_oracle_rmsd=1.5,
        selected_rmsd=2.5,
        selected_valid=True,
    )
    decision = evaluate_global_orientation_development(rows)
    assert decision.verdict == "no_go"
    assert "baseline_recovered_case_not_reproduced" in decision.invariant_failures
    assert "required_invariant_failed" in decision.hard_no_go_triggers


def test_order_or_roster_drift_fails_closed() -> None:
    with pytest.raises(
        GlobalOrientationDevelopmentDecisionError,
        match="exact ordered nine-case cohort",
    ):
        evaluate_global_orientation_development(tuple(reversed(_rows())))


def test_wrong_observation_type_fails_with_protocol_error() -> None:
    rows: tuple[object, ...] = (*_rows()[:-1], {})
    with pytest.raises(
        GlobalOrientationDevelopmentDecisionError,
        match="exact comparison type",
    ):
        evaluate_global_orientation_development(rows)


def test_direct_construction_cannot_forge_go_verdict() -> None:
    decision = evaluate_global_orientation_development(_rows())
    with pytest.raises(
        GlobalOrientationDevelopmentDecisionError,
        match="verdict is inconsistent",
    ):
        replace(decision, verdict="go")


def test_decision_requires_complete_observation_receipt_roster() -> None:
    decision = evaluate_global_orientation_development(_rows())
    with pytest.raises(
        GlobalOrientationDevelopmentDecisionError,
        match="nine lowercase SHA-256",
    ):
        replace(
            decision,
            observation_receipt_sha256s=decision.observation_receipt_sha256s[:-1],
        )
