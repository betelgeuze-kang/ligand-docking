from __future__ import annotations

from copy import deepcopy
import inspect
import json

import pytest

from betelgeuze_engine_v2.physics.reference_validation_authorization import (
    FROZEN_REFERENCE_VALIDATION_AUTHORIZATION_CONTRACT_SHA256,
)
from betelgeuze_engine_v2.physics.reference_validation_materializer import (
    reference_validation_materialization_manifest_document,
)
from betelgeuze_engine_v2.physics.reference_validation_protocol import (
    FROZEN_CPU_REFERENCE_VALIDATION_PROTOCOL_SHA256,
    cpu_reference_validation_protocol_document,
)
from betelgeuze_engine_v2.physics.reference_validation_receipts import (
    FROZEN_REFERENCE_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256,
    FROZEN_REFERENCE_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256,
    REFERENCE_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SCHEMA_ID,
    REFERENCE_VALIDATION_EXECUTION_ENVIRONMENT_RECEIPT_SCHEMA_ID,
    REFERENCE_VALIDATION_RESULT_RECEIPT_CONTRACT_SCHEMA_ID,
    REFERENCE_VALIDATION_RESULT_RECEIPT_SCHEMA_ID,
    ReferenceValidationReceiptContractError,
    reference_validation_execution_environment_contract_document,
    reference_validation_execution_readiness_decision,
    reference_validation_result_receipt_contract_document,
    require_reference_validation_execution_environment_contract_document,
    require_reference_validation_execution_ready,
    require_reference_validation_result_receipt_contract_document,
)
import betelgeuze_engine_v2.physics.reference_validation_receipts as receipts_module


def test_environment_contract_is_frozen_cpu_only_and_pre_execution() -> None:
    first = reference_validation_execution_environment_contract_document()
    second = reference_validation_execution_environment_contract_document()

    assert first == second
    assert first["schema_id"] == (
        REFERENCE_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SCHEMA_ID
    )
    assert first["contract_sha256"] == (
        FROZEN_REFERENCE_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256
    )
    assert first["purpose"]["execution_environment_receipt_present"] is False
    assert first["purpose"]["validation_execution_authorized"] is False
    runtime = first["runtime_contract"]
    assert runtime["device"] == "cpu"
    assert runtime["supported_python_minor_versions"] == ["3.10", "3.11", "3.12"]
    assert runtime["torch_version"] == "2.6.0"
    assert runtime["numpy_version"] == "1.26.4"
    assert runtime["network_access_allowed"] is False
    assert runtime["required_empty_environment_variables"] == [
        "CUDA_VISIBLE_DEVICES",
        "HIP_VISIBLE_DEVICES",
        "ROCR_VISIBLE_DEVICES",
    ]
    assert runtime["shell_interpolation_allowed"] is False
    assert runtime["secrets_allowed_in_receipt"] is False
    assert first["receipt_schema"]["schema_id"] == (
        REFERENCE_VALIDATION_EXECUTION_ENVIRONMENT_RECEIPT_SCHEMA_ID
    )
    assert first["receipt_schema"][
        "receipt_must_be_written_before_validation_evaluation"
    ]
    assert (
        require_reference_validation_execution_environment_contract_document(first)
        == first
    )


def test_environment_contract_rejects_tamper() -> None:
    tampered = deepcopy(reference_validation_execution_environment_contract_document())
    tampered["runtime_contract"]["network_access_allowed"] = True
    with pytest.raises(
        ReferenceValidationReceiptContractError,
        match="does not match the frozen record",
    ):
        require_reference_validation_execution_environment_contract_document(tampered)


def test_result_contract_is_frozen_without_results() -> None:
    first = reference_validation_result_receipt_contract_document()
    second = reference_validation_result_receipt_contract_document()

    assert first == second
    assert first["schema_id"] == REFERENCE_VALIDATION_RESULT_RECEIPT_CONTRACT_SCHEMA_ID
    assert first["contract_sha256"] == (
        FROZEN_REFERENCE_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256
    )
    assert first["receipt_schema"]["schema_id"] == (
        REFERENCE_VALIDATION_RESULT_RECEIPT_SCHEMA_ID
    )
    assert first["purpose"]["result_receipt_present"] is False
    assert first["purpose"]["result_values_present"] is False
    assert first["current_state"]["result_receipt_writer_implemented"] is True
    assert first["current_state"]["validation_runner_implemented"] is True
    assert first["current_state"]["validation_results_collected"] is False
    assert first["claim_policy"]["force_or_energy_validated"] is False
    assert first["claim_policy"]["claim_safe"] is False
    assert require_reference_validation_result_receipt_contract_document(first) == first


def test_result_contract_binds_exact_protocol_cases_variants_and_metrics() -> None:
    result = reference_validation_result_receipt_contract_document()
    protocol = cpu_reference_validation_protocol_document()
    materialization = reference_validation_materialization_manifest_document()
    coverage = result["coverage_contract"]

    assert result["dependencies"]["protocol_sha256"] == (
        FROZEN_CPU_REFERENCE_VALIDATION_PROTOCOL_SHA256
    )
    assert result["dependencies"]["authorization_contract_sha256"] == (
        FROZEN_REFERENCE_VALIDATION_AUTHORIZATION_CONTRACT_SHA256
    )
    assert result["dependencies"]["execution_environment_contract_sha256"] == (
        FROZEN_REFERENCE_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256
    )
    assert coverage["case_count"] == 27
    assert coverage["variant_count"] == 59
    assert coverage["expected_pass_case_count"] == 15
    assert coverage["expected_fail_closed_case_count"] == 12
    assert coverage["skipped_cases_allowed"] is False
    assert coverage["partial_results_allowed"] is False
    assert len(coverage["ordered_cases"]) == 27
    assert sum(row["variant_count"] for row in coverage["ordered_cases"]) == 59
    assert [row["case_id"] for row in coverage["ordered_cases"]] == [
        row["case_id"] for row in protocol["fixture_manifest"]["cases"]
    ]
    assert [row["case_input_sha256"] for row in coverage["ordered_cases"]] == [
        row["case_input_sha256"] for row in materialization["cases"]
    ]
    assert (
        result["metric_contract"]["metrics"]
        == protocol["numerical_protocol"]["metrics"]
    )
    assert len(result["metric_contract"]["metrics"]) == 19


def test_contract_rows_contain_identities_but_no_observed_values() -> None:
    result = reference_validation_result_receipt_contract_document()
    encoded = json.dumps(result, allow_nan=False, sort_keys=True)

    for case in result["coverage_contract"]["ordered_cases"]:
        assert "observed_status" not in case
        assert "metric_values" not in case
        assert "case_passed" not in case
        for variant in case["ordered_variants"]:
            assert "total_energy_value" not in variant
            assert "component_energy_values" not in variant
            assert "force_array_sha256" not in variant
    assert '"result_receipt_present": false' in encoded
    assert '"result_values_present": false' in encoded


def test_result_contract_rejects_tamper() -> None:
    tampered = deepcopy(reference_validation_result_receipt_contract_document())
    tampered["coverage_contract"]["skipped_cases_allowed"] = True
    with pytest.raises(
        ReferenceValidationReceiptContractError,
        match="does not match the frozen record",
    ):
        require_reference_validation_result_receipt_contract_document(tampered)


def test_execution_readiness_remains_closed_after_contract_freeze() -> None:
    decision = reference_validation_execution_readiness_decision()

    assert decision["receipt_contracts_frozen"] is True
    assert decision["independent_review_attestation_present"] is False
    assert decision["authorization_receipt_present"] is False
    assert decision["authorization_nonce_reserved"] is False
    assert decision["execution_environment_receipt_present"] is False
    assert decision["validation_runner_implemented"] is True
    assert decision["result_receipt_writer_implemented"] is True
    assert decision["validation_execution_authorized"] is False
    assert decision["validation_results_collected"] is False
    assert decision["parameter_fitting_proposal_authorized"] is False
    assert decision["parameter_fitting_authorized"] is False
    for blocker in (
        "execution_environment_receipt_missing",
        "authorization_nonce_not_atomically_reserved",
        "validation_execution_not_authorized",
        "validation_results_not_collected",
    ):
        assert blocker in decision["blockers"]


def test_execution_requirement_always_fails_closed() -> None:
    with pytest.raises(
        ReferenceValidationReceiptContractError,
        match="execution is not authorized",
    ):
        require_reference_validation_execution_ready()


def test_receipt_contract_module_exposes_no_runner_writer_or_receipt_builder() -> None:
    public = set(receipts_module.__all__)
    assert not any(name.startswith("build_") for name in public)
    assert not any(name.startswith("write_") for name in public)
    assert not any(name.startswith("run_") for name in public)

    source = inspect.getsource(receipts_module)
    assert "reference_forcefield" not in source
    assert "evaluate_reference_force_field" not in source
    assert "evaluate_independent_analytic_oracle" not in source
