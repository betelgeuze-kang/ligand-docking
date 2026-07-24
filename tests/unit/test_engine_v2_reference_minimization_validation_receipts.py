from __future__ import annotations

from copy import deepcopy

import pytest

from betelgeuze_engine_v2.physics.reference_minimization_validation_artifact_binding import (
    FROZEN_CPU_MINIMIZATION_VALIDATION_MATERIALIZATION_MANIFEST_SHA256,
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_ARTIFACT_BINDING_SHA256,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_protocol import (
    FROZEN_CPU_MINIMIZATION_VALIDATION_PROTOCOL_SHA256,
    cpu_minimization_validation_protocol_document,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_receipts import (
    FROZEN_LEGACY_REFERENCE_MINIMIZATION_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256_V4,
    FROZEN_LEGACY_REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256_V5,
    FROZEN_LEGACY_REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256_V3,
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256,
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256,
    REFERENCE_MINIMIZATION_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SCHEMA_ID,
    REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_CONTRACT_SCHEMA_ID,
    ReferenceMinimizationValidationReceiptContractError,
    reference_minimization_validation_execution_environment_contract_document,
    reference_minimization_validation_execution_readiness_decision,
    reference_minimization_validation_result_receipt_contract_document,
    require_reference_minimization_validation_execution_environment_contract_document,
    require_reference_minimization_validation_execution_ready,
    require_reference_minimization_validation_result_receipt_contract_document,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_review import (
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_REVIEW_CONTRACT_SHA256,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_trajectory_comparison import (
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COMPARISON_CONTRACT_SHA256,
    REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COORDINATE_THRESHOLD_ANGSTROM,
    REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_ENERGY_THRESHOLD_KCAL_PER_MOL,
)


def test_environment_contract_is_frozen_dependency_bound_and_receipt_free() -> None:
    first = reference_minimization_validation_execution_environment_contract_document()
    second = reference_minimization_validation_execution_environment_contract_document()

    assert first == second
    assert first["schema_id"] == REFERENCE_MINIMIZATION_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SCHEMA_ID
    assert first["contract_sha256"] == FROZEN_REFERENCE_MINIMIZATION_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256
    assert first["superseded_contract_sha256"] == (
        FROZEN_LEGACY_REFERENCE_MINIMIZATION_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256_V4
    )
    assert first["dependencies"]["protocol_sha256"] == FROZEN_CPU_MINIMIZATION_VALIDATION_PROTOCOL_SHA256
    assert (
        first["dependencies"]["artifact_binding_sha256"]
        == FROZEN_REFERENCE_MINIMIZATION_VALIDATION_ARTIFACT_BINDING_SHA256
    )
    assert (
        first["dependencies"]["review_contract_sha256"]
        == FROZEN_REFERENCE_MINIMIZATION_VALIDATION_REVIEW_CONTRACT_SHA256
    )
    assert (
        first["dependencies"]["materialization_manifest_sha256"]
        == FROZEN_CPU_MINIMIZATION_VALIDATION_MATERIALIZATION_MANIFEST_SHA256
    )
    assert first["dependencies"]["authorization_contract_sha256_required"] is True
    assert first["runtime_contract"]["device"] == "cpu"
    assert first["runtime_contract"]["coordinate_dtype"] == "float64"
    assert first["runtime_contract"]["network_access_allowed"] is False
    assert first["runtime_contract"]["secrets_allowed_in_receipt"] is False
    assert first["purpose"]["execution_environment_receipt_present"] is False
    assert first["claim_policy"]["scientifically_validated"] is False
    assert first["claim_policy"]["claim_safe"] is False
    assert require_reference_minimization_validation_execution_environment_contract_document(first) == first


def test_result_contract_is_exact_failure_inclusive_and_result_free() -> None:
    contract = reference_minimization_validation_result_receipt_contract_document()
    protocol = cpu_minimization_validation_protocol_document()

    assert contract["schema_id"] == REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_CONTRACT_SCHEMA_ID
    assert contract["contract_sha256"] == FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256
    assert contract["superseded_contract_sha256"] == (
        FROZEN_LEGACY_REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256_V5
    )
    assert (
        FROZEN_LEGACY_REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256_V3
        == "814ea0ec6464acb77cdf41ccba8070c03ed79cc6e605805a55719c54c55b6745"
    )
    assert (
        contract["dependencies"]["trajectory_comparison_contract_sha256"]
        == FROZEN_REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COMPARISON_CONTRACT_SHA256
    )
    coverage = contract["coverage_contract"]
    assert coverage["case_count"] == 14
    assert coverage["expected_pass_case_count"] == 8
    assert coverage["expected_fail_closed_case_count"] == 6
    assert coverage["all_failure_rows_must_remain_in_denominator"] is True
    assert coverage["skipped_cases_allowed"] is False
    assert coverage["partial_results_allowed"] is False
    assert [row["case_id"] for row in coverage["ordered_cases"]] == [
        row["case_id"] for row in protocol["case_manifest"]["cases"]
    ]
    assert [row["ordinal"] for row in coverage["ordered_cases"]] == list(range(14))
    assert len(contract["metric_contract"]["metrics"]) == 10
    assert contract["metric_contract"]["metrics"] == protocol["numerical_protocol"]["metrics"]
    assert contract["purpose"]["result_receipt_present"] is False
    assert contract["purpose"]["result_values_present"] is False
    assert contract["current_state"]["validation_runner_implemented"] is True
    assert contract["current_state"]["result_receipt_writer_implemented"] is True
    assert contract["current_state"]["complete_coordinate_trace_contract_implemented"] is True
    trace_contract = contract["coordinate_trace_contract"]
    assert trace_contract["trace_sources_in_order"] == [
        "operational",
        "independent_oracle",
    ]
    assert trace_contract["complete_raw_and_evaluated_coordinates_required_per_evaluation"] is True
    assert trace_contract["whole_trace_canonical_sha256_required"] is True
    assert trace_contract["missing_empty_or_reordered_trace_is_failure"] is True
    assert "coordinate_traces" in contract["receipt_schema"]["required_case_fields"]
    assert "trajectory_comparison" in contract["receipt_schema"]["required_case_fields"]
    assert "step_identity_sha256" in contract["receipt_schema"]["required_coordinate_trace_step_fields"]
    comparison = contract["trajectory_comparison_contract"]
    assert comparison["comparison_required_for_every_case"] is True
    assert comparison["coordinate_threshold_angstrom"] == (
        REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COORDINATE_THRESHOLD_ANGSTROM
    )
    assert comparison["energy_threshold_kcal_per_mol"] == (
        REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_ENERGY_THRESHOLD_KCAL_PER_MOL
    )
    assert [row["case_id"] for row in comparison["checkpoint_cases"]] == [
        "v1_checkpoint_restart_exact",
        "v2_constrained_checkpoint_restart_exact",
        "v2_fixed_born_checkpoint_restart_exact",
    ]
    assert contract["current_state"]["trajectory_comparison_contract_implemented"] is True
    assert contract["claim_policy"]["minimization_validated"] is False
    assert require_reference_minimization_validation_result_receipt_contract_document(contract) == contract


def test_case_contract_binds_both_implementations_and_failure_semantics() -> None:
    rows = reference_minimization_validation_result_receipt_contract_document()["coverage_contract"]["ordered_cases"]

    assert all(len(row["runtime_input_sha256"]) == 64 for row in rows)
    assert all(len(row["independent_oracle_input_sha256"]) == 64 for row in rows)
    assert all(row["runtime_input_sha256"] != row["independent_oracle_input_sha256"] for row in rows)
    failures = [row for row in rows if row["expected_outcome"] == "fail_closed"]
    assert len(failures) == 6
    assert all(row["expected_error_code"] for row in failures)
    assert all(row["required_metric_ids"] == [] for row in failures)


@pytest.mark.parametrize("kind", ("environment", "result"))
def test_frozen_contracts_reject_tamper(kind: str) -> None:
    if kind == "environment":
        contract = reference_minimization_validation_execution_environment_contract_document()
        require = require_reference_minimization_validation_execution_environment_contract_document
    else:
        contract = reference_minimization_validation_result_receipt_contract_document()
        require = require_reference_minimization_validation_result_receipt_contract_document
    tampered = deepcopy(contract)
    tampered["claim_policy"]["claim_safe"] = True
    with pytest.raises(
        ReferenceMinimizationValidationReceiptContractError,
        match="does not match the frozen record",
    ):
        require(tampered)


def test_readiness_remains_closed_and_execution_raises() -> None:
    decision = reference_minimization_validation_execution_readiness_decision()

    assert decision["receipt_contracts_frozen"] is True
    assert decision["authorization_contract_frozen"] is True
    assert decision["independent_review_attestation_present"] is False
    assert decision["authorization_receipt_present"] is False
    assert decision["run_start_environment_receipt_primitive_implemented"] is True
    assert decision["execution_environment_receipt_present"] is False
    assert decision["validation_runner_implemented"] is True
    assert decision["result_receipt_writer_implemented"] is True
    assert decision["validation_execution_authorized"] is False
    assert decision["validation_results_collected"] is False
    assert "signed_execution_authorization_receipt_schema_not_frozen" not in decision["blockers"]
    assert "independent_result_review_missing" in decision["blockers"]
    with pytest.raises(
        ReferenceMinimizationValidationReceiptContractError,
        match="execution is not authorized",
    ):
        require_reference_minimization_validation_execution_ready()
