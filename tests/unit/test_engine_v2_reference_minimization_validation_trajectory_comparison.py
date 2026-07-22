from __future__ import annotations

from copy import deepcopy

import pytest

from betelgeuze_engine_v2.physics import (
    reference_minimization_validation_runner as runner,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_trajectory_comparison import (
    CHECKPOINT_RESTART_EXPECTED_FAIL_CLOSED,
    CHECKPOINT_RESTART_NOT_APPLICABLE,
    CHECKPOINT_RESTART_UNEXPECTED_FAILURE,
    CHECKPOINT_RESTART_VERIFIED,
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COMPARISON_CONTRACT_SHA256,
    REFERENCE_MINIMIZATION_VALIDATION_CHECKPOINT_CASE_PAUSES,
    REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COORDINATE_THRESHOLD_ANGSTROM,
    REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_ENERGY_THRESHOLD_KCAL_PER_MOL,
    SUPERSEDED_REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COMPARISON_CONTRACT_SHA256,
    TRAJECTORY_COMPARISON_ACCEPTED,
    TRAJECTORY_COMPARISON_EXPECTED_FAIL_CLOSED,
    TRAJECTORY_COMPARISON_REJECTED_ALIGNMENT,
    TRAJECTORY_COMPARISON_REJECTED_THRESHOLD,
    TRAJECTORY_COMPARISON_UNEXPECTED_FAILURE,
    ReferenceMinimizationValidationTrajectoryComparisonError,
    build_reference_minimization_validation_trajectory_comparison,
    reference_minimization_validation_trajectory_comparison_contract_document,
    require_reference_minimization_validation_trajectory_comparison,
    require_reference_minimization_validation_trajectory_comparison_contract_document,
)


@pytest.fixture(scope="module")
def matrix():
    return runner._run_case_matrix_in_process()


def _row(matrix, case_id: str):
    return next(row for row in matrix if row.case_id == case_id)


def test_comparison_contract_is_frozen_before_production_observation() -> None:
    contract = reference_minimization_validation_trajectory_comparison_contract_document()

    assert contract["contract_sha256"] == (
        FROZEN_REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COMPARISON_CONTRACT_SHA256
    )
    assert contract["superseded_contract_sha256"] == (
        SUPERSEDED_REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COMPARISON_CONTRACT_SHA256
    )
    assert contract["purpose"]["comparison_before_production_observation"] is True
    assert contract["purpose"]["production_result_bundled"] is False
    assert contract["numerical_contract"]["coordinate_max_and_rms_threshold"] == pytest.approx(1.0e-8)
    assert contract["numerical_contract"]["energy_max_and_rms_threshold"] == pytest.approx(1.0e-10)
    assert contract["checkpoint_restart_contract"]["checkpoint_case_count"] == 3
    assert contract["current_state"]["s0_accepted"] is False
    assert contract["current_state"]["s1_admission"] is False
    assert require_reference_minimization_validation_trajectory_comparison_contract_document(contract) == contract


def test_all_cases_retain_ordered_comparison_and_explicit_noncomparability(
    matrix,
) -> None:
    assert len(matrix) == 14
    assert sum(row.trajectory_comparison["comparison_passed"] for row in matrix) == 14

    for row in matrix:
        comparison = row.trajectory_comparison
        assert comparison["case_id"] == row.case_id
        assert comparison["expected_outcome"] == row.expected_outcome
        assert comparison["operational_trace_sha256"] == (row.coordinate_traces[0].trace_sha256)
        assert comparison["independent_trace_sha256"] == (row.coordinate_traces[1].trace_sha256)
        assert (
            require_reference_minimization_validation_trajectory_comparison(
                comparison,
                expected_case_id=row.case_id,
                expected_outcome=row.expected_outcome,
                operational_trace=row.coordinate_traces[0].to_dict(),
                independent_trace=row.coordinate_traces[1].to_dict(),
            )
            == comparison
        )
        if row.expected_outcome == "fail_closed":
            assert comparison["trajectory_comparison_disposition"] == (TRAJECTORY_COMPARISON_EXPECTED_FAIL_CLOSED)
            assert comparison["step_comparisons"] == []
            assert comparison["comparison_passed"] is True
            assert (
                comparison["checkpoint_restart_evidence"]["checkpoint_restart_disposition"]
                == CHECKPOINT_RESTART_EXPECTED_FAIL_CLOSED
            )


def test_three_checkpoint_cases_bind_uninterrupted_paused_and_resumed_digests(
    matrix,
) -> None:
    pause_by_case = dict(REFERENCE_MINIMIZATION_VALIDATION_CHECKPOINT_CASE_PAUSES)
    for case_id, pause in pause_by_case.items():
        row = _row(matrix, case_id)
        checkpoint = row.trajectory_comparison["checkpoint_restart_evidence"]
        assert checkpoint["pause_after_accepted_iterations"] == pause
        assert checkpoint["checkpoint_restart_disposition"] == (CHECKPOINT_RESTART_VERIFIED)
        assert checkpoint["checkpoint_restart_passed"] is True
        assert checkpoint["result_digest_equality"] is True
        assert checkpoint["checkpoint_digest_equality"] is True
        assert checkpoint["trajectory_digest_equality"] is True
        assert checkpoint["uninterrupted_resumed_count_equality"] is True
        assert checkpoint["paused"]["accepted_iteration_count"] == pause
        assert checkpoint["paused"]["status"] == "checkpointed"
        assert checkpoint["uninterrupted"]["result_sha256"] == (row.operational_result_sha256)
        assert checkpoint["uninterrupted"]["trajectory_sha256"] == (row.coordinate_traces[0].trace_sha256)
        assert checkpoint["uninterrupted"] == checkpoint["resumed"]

    noncheckpoint = _row(matrix, "v1_bonded_energy_decrease")
    assert (
        noncheckpoint.trajectory_comparison["checkpoint_restart_evidence"]["checkpoint_restart_disposition"]
        == CHECKPOINT_RESTART_NOT_APPLICABLE
    )


def test_fixed_born_traces_pass_predefined_thresholds_with_projection_headroom(matrix) -> None:
    for case_id in (
        "v2_fixed_born_constrained_energy_decrease",
        "v2_fixed_born_checkpoint_restart_exact",
    ):
        comparison = _row(matrix, case_id).trajectory_comparison
        assert comparison["trajectory_comparison_disposition"] == (TRAJECTORY_COMPARISON_ACCEPTED)
        assert comparison["comparison_passed"] is True
        assert comparison["energy_max_abs_error_kcal_per_mol"] <= (
            REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_ENERGY_THRESHOLD_KCAL_PER_MOL
        )
        assert comparison["raw_coordinate_max_abs_error_angstrom"] <= (
            REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COORDINATE_THRESHOLD_ANGSTROM
        )
        assert comparison["evaluated_coordinate_max_abs_error_angstrom"] <= (
            REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COORDINATE_THRESHOLD_ANGSTROM
        )
        assert all(
            row["step_comparison_disposition"] == TRAJECTORY_COMPARISON_ACCEPTED
            for row in comparison["step_comparisons"]
        )


@pytest.mark.parametrize(
    "mutation",
    (
        "missing_step",
        "reordered_steps",
        "crosswired_case",
        "nonfinite_aggregate",
        "step_digest",
        "checkpoint_digest",
        "comparison_digest",
    ),
)
def test_comparison_verifier_rejects_omission_reorder_crosswire_and_tamper(
    matrix,
    mutation: str,
) -> None:
    row = _row(matrix, "v1_checkpoint_restart_exact")
    source = deepcopy(row.trajectory_comparison)
    if mutation == "missing_step":
        source["step_comparisons"].pop()
    elif mutation == "reordered_steps":
        source["step_comparisons"].reverse()
    elif mutation == "crosswired_case":
        source["case_id"] = "v1_mixed_term_energy_decrease"
    elif mutation == "nonfinite_aggregate":
        source["energy_rms_error_kcal_per_mol"] = float("nan")
    elif mutation == "step_digest":
        source["step_comparisons"][0]["step_comparison_sha256"] = "0" * 64
    elif mutation == "checkpoint_digest":
        source["checkpoint_restart_evidence"]["resumed"]["trajectory_sha256"] = "0" * 64
    elif mutation == "comparison_digest":
        source["comparison_sha256"] = "0" * 64
    else:  # pragma: no cover
        raise AssertionError(mutation)

    with pytest.raises(ReferenceMinimizationValidationTrajectoryComparisonError):
        require_reference_minimization_validation_trajectory_comparison(
            source,
            expected_case_id=row.case_id,
            expected_outcome=row.expected_outcome,
            operational_trace=row.coordinate_traces[0].to_dict(),
            independent_trace=row.coordinate_traces[1].to_dict(),
        )


def test_alignment_mismatch_and_unexpected_failure_have_rejected_dispositions(
    matrix,
) -> None:
    row = _row(matrix, "v1_bonded_energy_decrease")
    independent = deepcopy(row.coordinate_traces[1].to_dict())
    independent["steps"][1]["trial"] += 1
    rejected = build_reference_minimization_validation_trajectory_comparison(
        case_id=row.case_id,
        expected_outcome=row.expected_outcome,
        operational_trace=row.coordinate_traces[0].to_dict(),
        independent_trace=independent,
        checkpoint_restart_evidence=row.trajectory_comparison["checkpoint_restart_evidence"],
    )
    assert rejected["trajectory_comparison_disposition"] == (TRAJECTORY_COMPARISON_REJECTED_ALIGNMENT)
    assert rejected["comparison_passed"] is False

    failure = runner._failure_complete_matrix("synthetic_supervisor_failure")[0]
    assert failure.trajectory_comparison["trajectory_comparison_disposition"] == (
        TRAJECTORY_COMPARISON_UNEXPECTED_FAILURE
    )
    assert failure.trajectory_comparison["checkpoint_restart_evidence"]["checkpoint_restart_disposition"] in {
        CHECKPOINT_RESTART_NOT_APPLICABLE,
        CHECKPOINT_RESTART_UNEXPECTED_FAILURE,
    }
    assert failure.trajectory_comparison["comparison_passed"] is False


def test_aligned_trace_above_predefined_coordinate_threshold_is_rejected(matrix) -> None:
    row = _row(matrix, "v1_bonded_energy_decrease")
    independent = deepcopy(row.coordinate_traces[1].to_dict())
    encoded = independent["steps"][0]["raw_coordinates_angstrom_hex"][0][0]
    independent["steps"][0]["raw_coordinates_angstrom_hex"][0][0] = (float.fromhex(encoded) + 1.0e-6).hex()

    rejected = build_reference_minimization_validation_trajectory_comparison(
        case_id=row.case_id,
        expected_outcome=row.expected_outcome,
        operational_trace=row.coordinate_traces[0].to_dict(),
        independent_trace=independent,
        checkpoint_restart_evidence=row.trajectory_comparison["checkpoint_restart_evidence"],
    )

    assert rejected["trajectory_comparison_disposition"] == (TRAJECTORY_COMPARISON_REJECTED_THRESHOLD)
    assert rejected["step_comparisons"][0]["step_comparison_disposition"] == (TRAJECTORY_COMPARISON_REJECTED_THRESHOLD)
    assert rejected["comparison_passed"] is False


def test_aligned_non_born_case_retains_every_step_and_aggregate(matrix) -> None:
    comparison = _row(matrix, "v1_mixed_term_energy_decrease").trajectory_comparison
    assert comparison["trajectory_comparison_disposition"] == (TRAJECTORY_COMPARISON_ACCEPTED)
    assert comparison["aligned_step_count"] == comparison["operational_trace_length"]
    assert comparison["aligned_step_count"] == comparison["independent_trace_length"]
    assert comparison["raw_coordinate_scalar_count"] > 0
    assert comparison["evaluated_coordinate_scalar_count"] > 0
    assert comparison["energy_value_count"] == comparison["aligned_step_count"]
    assert all(
        row["comparison_ordinal"] == ordinal and row["evaluation_index"] == ordinal
        for ordinal, row in enumerate(comparison["step_comparisons"], start=1)
    )
