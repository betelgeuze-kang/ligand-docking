"""Frozen environment and result-receipt contracts for minimization validation.

The contracts bind the ordered synthetic minimization protocol to a future
CPU-only run.  They do not provide an authorization contract or receipt,
create an environment or result receipt, implement a runner, execute a case,
collect a result, authorize fitting, or promote a scientific claim.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Mapping, NoReturn

from .reference_minimization_validation_artifact_binding import (
    FROZEN_CPU_MINIMIZATION_VALIDATION_MATERIALIZATION_MANIFEST_SHA256,
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_ARTIFACT_BINDING_SHA256,
)
from .reference_minimization_validation_materializer import (
    cpu_minimization_validation_materialization_manifest_document,
)
from .reference_minimization_validation_dependency_identity import (
    REFERENCE_MINIMIZATION_VALIDATION_REQUIRED_DEPENDENCY_ARTIFACT_IDS,
)
from .reference_minimization_validation_protocol import (
    FROZEN_CPU_MINIMIZATION_VALIDATION_PROTOCOL_SHA256,
    cpu_minimization_validation_case_atom_count,
    cpu_minimization_validation_protocol_document,
)
from .reference_minimization_validation_review import (
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_REVIEW_CONTRACT_SHA256,
)


REFERENCE_MINIMIZATION_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SCHEMA_ID = "betelgeuze.engine_v2_reference_minimization_validation_execution_environment_contract/2.0.0"
REFERENCE_MINIMIZATION_VALIDATION_EXECUTION_ENVIRONMENT_RECEIPT_SCHEMA_ID = "betelgeuze.engine_v2_reference_minimization_validation_execution_environment_receipt/2.0.0"
REFERENCE_MINIMIZATION_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_ID = (
    "cpu_reference_minimization_validation_execution_environment_contract/2.0.0"
)
REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_CONTRACT_SCHEMA_ID = "betelgeuze.engine_v2_reference_minimization_validation_result_receipt_contract/2.0.0"
REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_validation_result_receipt/2.0.0"
)
REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_CONTRACT_ID = (
    "cpu_reference_minimization_validation_result_receipt_contract/2.0.0"
)
REFERENCE_MINIMIZATION_VALIDATION_RECEIPT_CONTRACT_VERSION = "2.0.0"
REFERENCE_MINIMIZATION_VALIDATION_RECEIPT_CONTRACTS_FROZEN_AT_UTC = (
    "2026-07-19T06:30:00Z"
)

# Filled only after the complete canonical projections have been reviewed.
FROZEN_REFERENCE_MINIMIZATION_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256 = (
    "a3022f345d99dfc84eb0f539d72a75f1e533c61789d770baa8a0aa9a789f51cb"
)
FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256 = (
    "d4d27679f6d658bbc22b35ae9a4d7c588f41aa3e18633eb0bff5ad4c25b38897"
)

_CURRENT_BLOCKERS = (
    "independent_scientific_review_missing",
    "signed_independent_scientific_review_attestation_missing",
    "trusted_independent_scientific_reviewer_key_not_provided",
    "implementation_author_and_independent_reviewer_separation_not_attested",
    "signed_execution_authorization_receipt_missing",
    "trusted_authorization_operator_key_not_provided",
    "authorization_nonce_not_atomically_reserved",
    "execution_environment_receipt_missing",
    "validation_execution_not_authorized",
    "minimization_validation_results_not_collected",
    "reviewed_runtime_parameter_values_not_bound",
    "scientific_parameter_applicability_not_established",
    "independent_result_review_missing",
    "parameter_fitting_not_authorized",
    "scientific_validation_missing",
    "product_integration_not_qualified",
)


class ReferenceMinimizationValidationReceiptContractError(ValueError):
    """A frozen receipt contract drifted or execution was requested."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise ReferenceMinimizationValidationReceiptContractError(
            "minimization validation receipt contract is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _closed_claim_policy() -> dict[str, bool]:
    return {
        "receipt_contracts_frozen": True,
        "validation_execution_authorized": False,
        "validation_results_collected": False,
        "minimization_validated": False,
        "parameter_fitting_proposal_authorized": False,
        "parameter_fitting_authorized": False,
        "scientifically_validated": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
    }


def _environment_contract_projection() -> dict[str, Any]:
    return {
        "schema_id": REFERENCE_MINIMIZATION_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SCHEMA_ID,
        "contract_id": REFERENCE_MINIMIZATION_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_ID,
        "contract_version": REFERENCE_MINIMIZATION_VALIDATION_RECEIPT_CONTRACT_VERSION,
        "frozen_at_utc": REFERENCE_MINIMIZATION_VALIDATION_RECEIPT_CONTRACTS_FROZEN_AT_UTC,
        "purpose": {
            "lane": "synthetic_minimization_implementation_mathematics_only",
            "contract_definition_only": True,
            "execution_environment_receipt_present": False,
            "validation_execution_authorized": False,
            "result_collection_performed": False,
        },
        "dependencies": {
            "protocol_sha256": FROZEN_CPU_MINIMIZATION_VALIDATION_PROTOCOL_SHA256,
            "artifact_binding_sha256": FROZEN_REFERENCE_MINIMIZATION_VALIDATION_ARTIFACT_BINDING_SHA256,
            "review_contract_sha256": FROZEN_REFERENCE_MINIMIZATION_VALIDATION_REVIEW_CONTRACT_SHA256,
            "materialization_manifest_sha256": FROZEN_CPU_MINIMIZATION_VALIDATION_MATERIALIZATION_MANIFEST_SHA256,
            "authorization_contract_sha256_required": True,
            "authorization_receipt_sha256_required": True,
            "authorization_nonce_sha256_required": True,
            "exact_code_commit_required": True,
            "exact_runner_source_sha256_required": True,
            "dependency_artifact_sha256_rows_required": True,
            "dependency_artifact_bytes_observed_before_engine_import": True,
            "required_dependency_artifact_ids": list(
                REFERENCE_MINIMIZATION_VALIDATION_REQUIRED_DEPENDENCY_ARTIFACT_IDS
            ),
            "distribution_record_payload_hashes_required": True,
        },
        "runtime_contract": {
            "operating_system": "linux",
            "machine_architecture": "x86_64",
            "device": "cpu",
            "cpu_only": True,
            "supported_python_minor_versions": ["3.10", "3.11", "3.12"],
            "exact_python_patch_version_required_in_receipt": True,
            "python_executable_and_stdlib_byte_manifests_required": True,
            "openssl_executable_byte_manifest_required": True,
            "torch_version": "2.6.0",
            "numpy_version": "1.26.4",
            "coordinate_dtype": "float64",
            "coordinate_unit": "angstrom",
            "energy_unit": "kcal/mol",
            "force_unit": "kcal/mol/angstrom",
            "network_access_allowed": False,
            "network_must_remain_disabled_from_materialization_through_finalize": True,
            "required_empty_environment_variables": [
                "CUDA_VISIBLE_DEVICES",
                "HIP_VISIBLE_DEVICES",
                "ROCR_VISIBLE_DEVICES",
            ],
            "required_environment_values": {
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
                "MKL_NUM_THREADS": "1",
                "OMP_NUM_THREADS": "1",
                "OPENBLAS_NUM_THREADS": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPYCACHEPREFIX": "/dev/null",
                "TZ": "UTC",
            },
            "python_hash_seed_required": True,
            "python_hash_seed_uint32_required": True,
            "python_hash_seed_applied_at_interpreter_initialization": True,
            "isolated_outer_launcher_then_seeded_controlled_inner_required": True,
            "application_seed_required": True,
            "torch_num_threads": 1,
            "torch_num_interop_threads": 1,
            "torch_deterministic_algorithms_required": True,
            "worker_seed_and_environment_receipt_binding_required": True,
            "parent_child_python_hash_probe_equality_required": True,
            "command_argv_required_as_exact_utf8_sequence": True,
            "shell_interpolation_allowed": False,
            "clean_checkout_required": True,
            "artifact_output_path_must_be_confined": True,
            "secrets_allowed_in_receipt": False,
        },
        "receipt_schema": {
            "schema_id": REFERENCE_MINIMIZATION_VALIDATION_EXECUTION_ENVIRONMENT_RECEIPT_SCHEMA_ID,
            "canonical_json_required": True,
            "duplicate_json_keys_allowed": False,
            "receipt_sha256_required": True,
            "environment_fingerprint_sha256_required": True,
            "required_fields": [
                "schema_id",
                "environment_contract_sha256",
                "protocol_sha256",
                "artifact_binding_sha256",
                "review_attestation_sha256",
                "authorization_contract_sha256",
                "authorization_receipt_sha256",
                "authorization_nonce_sha256",
                "code_commit_sha",
                "runner_source_sha256",
                "dependency_artifact_sha256_rows",
                "operating_system_release",
                "machine_architecture",
                "cpu_identity",
                "python_version",
                "torch_version",
                "numpy_version",
                "environment_variable_rows",
                "network_disabled_verification",
                "command_argv",
                "python_hash_seed",
                "application_seed",
                "thread_count_rows",
                "artifact_output_root",
                "artifact_path_confinement_verification",
                "started_at_utc",
                "environment_fingerprint_sha256",
                "receipt_sha256",
            ],
            "receipt_must_be_written_before_validation_evaluation": True,
            "receipt_must_be_reverified_at_run_start": True,
            "receipt_must_be_bound_into_result_receipt": True,
        },
        "current_state": {
            "contract_frozen": True,
            "execution_environment_receipt_present": False,
            "environment_reverified_at_run_start": False,
            "validation_execution_authorized": False,
        },
        "claim_policy": _closed_claim_policy(),
    }


def _ordered_case_contract_rows() -> list[dict[str, Any]]:
    protocol = cpu_minimization_validation_protocol_document()
    materialization = cpu_minimization_validation_materialization_manifest_document()
    protocol_cases = protocol["case_manifest"]["cases"]
    materialized_cases = materialization["cases"]
    if len(protocol_cases) != len(materialized_cases):
        raise ReferenceMinimizationValidationReceiptContractError(
            "protocol and materialization case counts diverged"
        )
    rows: list[dict[str, Any]] = []
    for ordinal, (protocol_case, materialized_case) in enumerate(
        zip(protocol_cases, materialized_cases, strict=True)
    ):
        if protocol_case["case_id"] != materialized_case["case_id"]:
            raise ReferenceMinimizationValidationReceiptContractError(
                "protocol and materialization case order diverged"
            )
        rows.append(
            {
                "ordinal": ordinal,
                "case_id": protocol_case["case_id"],
                "atom_count": cpu_minimization_validation_case_atom_count(
                    protocol_case["case_id"]
                ),
                "case_input_sha256": materialized_case["case_input_sha256"],
                "runtime_input_sha256": materialized_case["runtime_input_sha256"],
                "independent_oracle_input_sha256": materialized_case[
                    "independent_oracle_input_sha256"
                ],
                "expected_outcome": protocol_case["expected_outcome"],
                "expected_error_code": protocol_case["expected_error_code"],
                "required_metric_ids": list(protocol_case["required_metric_ids"]),
                "lane": protocol_case["lane"],
                "evaluator_scope": protocol_case["evaluator_scope"],
            }
        )
    return rows


def _result_contract_projection() -> dict[str, Any]:
    protocol = cpu_minimization_validation_protocol_document()
    materialization = cpu_minimization_validation_materialization_manifest_document()
    cases = protocol["case_manifest"]
    numerical = protocol["numerical_protocol"]
    return {
        "schema_id": REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_CONTRACT_SCHEMA_ID,
        "contract_id": REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_CONTRACT_ID,
        "contract_version": REFERENCE_MINIMIZATION_VALIDATION_RECEIPT_CONTRACT_VERSION,
        "frozen_at_utc": REFERENCE_MINIMIZATION_VALIDATION_RECEIPT_CONTRACTS_FROZEN_AT_UTC,
        "purpose": {
            "lane": "synthetic_minimization_implementation_mathematics_only",
            "contract_definition_only": True,
            "result_receipt_present": False,
            "result_values_present": False,
            "validation_execution_authorized": False,
            "scientific_acceptance_recorded": False,
        },
        "dependencies": {
            "protocol_sha256": FROZEN_CPU_MINIMIZATION_VALIDATION_PROTOCOL_SHA256,
            "artifact_binding_sha256": FROZEN_REFERENCE_MINIMIZATION_VALIDATION_ARTIFACT_BINDING_SHA256,
            "review_contract_sha256": FROZEN_REFERENCE_MINIMIZATION_VALIDATION_REVIEW_CONTRACT_SHA256,
            "execution_environment_contract_sha256": FROZEN_REFERENCE_MINIMIZATION_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256,
            "fixture_manifest_sha256": protocol["fixture_manifest"][
                "fixture_manifest_sha256"
            ],
            "case_manifest_sha256": cases["case_manifest_sha256"],
            "materialization_manifest_sha256": materialization[
                "materialization_manifest_sha256"
            ],
            "exact_review_attestation_sha256_required": True,
            "exact_authorization_contract_sha256_required": True,
            "exact_authorization_receipt_sha256_required": True,
            "exact_execution_environment_receipt_sha256_required": True,
            "exact_code_commit_and_runner_source_sha256_required": True,
        },
        "coverage_contract": {
            "case_count": cases["case_count"],
            "expected_pass_case_count": cases["expected_pass_case_count"],
            "expected_fail_closed_case_count": cases["expected_fail_closed_case_count"],
            "case_order_must_match_protocol": True,
            "all_failure_rows_must_remain_in_denominator": True,
            "skipped_cases_allowed": False,
            "partial_results_allowed": False,
            "cross_case_averaging_allowed": False,
            "ordered_cases": _ordered_case_contract_rows(),
        },
        "metric_contract": {
            "coordinate_dtype": numerical["coordinate_dtype"],
            "coordinate_unit": numerical["coordinate_unit"],
            "energy_unit": numerical["energy_unit"],
            "force_unit": numerical["force_unit"],
            "missing_metric_is_failure": True,
            "thresholds_predefined_before_results": True,
            "metrics": deepcopy(numerical["metrics"]),
        },
        "coordinate_trace_contract": {
            "trace_sources_in_order": ["operational", "independent_oracle"],
            "coordinate_dtype": "float64",
            "coordinate_unit": "angstrom",
            "coordinate_encoding": "python_float_hex",
            "coordinate_digest_algorithm": "sha256_f64le",
            "complete_raw_and_evaluated_coordinates_required_per_evaluation": True,
            "trace_length_must_equal_evaluation_count": True,
            "evaluation_indices_must_be_contiguous": True,
            "iteration_and_trial_identity_must_be_contiguous": True,
            "step_identity_must_bind_case_source_outcome_and_coordinates": True,
            "whole_trace_canonical_sha256_required": True,
            "accepted_energy_ledger_must_match_initial_and_accepted_steps": True,
            "expected_pre_evaluation_failure_uses_canonical_empty_trace": True,
            "missing_empty_or_reordered_trace_is_failure": True,
        },
        "receipt_schema": {
            "schema_id": REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_SCHEMA_ID,
            "canonical_json_required": True,
            "duplicate_json_keys_allowed": False,
            "receipt_sha256_required": True,
            "required_top_level_fields": [
                "schema_id",
                "result_contract_sha256",
                "result_writer_contract_sha256",
                "runner_contract_sha256",
                "protocol_sha256",
                "artifact_binding_sha256",
                "authorization_contract_sha256",
                "authorization_receipt_sha256",
                "authorization_nonce_sha256",
                "execution_environment_contract_sha256",
                "execution_environment_receipt_sha256",
                "environment_fingerprint_sha256",
                "runner_start_record_sha256",
                "observation_sha256",
                "code_commit_sha",
                "runner_source_sha256",
                "dependency_artifact_sha256_rows",
                "command_argv",
                "seed",
                "started_at_utc",
                "completed_at_utc",
                "case_results",
                "coverage_summary",
                "run_observation",
                "artifact_path_confinement_verification",
                "review_attestation_sha256",
                "independent_reviewer_identity_sha256",
                "reviewed_at_utc",
                "review_scope",
                "independent_result_review_state",
                "supersession_state",
                "revocation_state",
                "result_values_present",
                "result_receipt_written",
                "validation_results_collected",
                "production_validation_results_collected",
                "parameter_fitting_proposal_authorized",
                "parameter_fitting_authorized",
                "scientifically_validated",
                "benchmark_validated",
                "product_qualified",
                "customer_execution_enabled",
                "claim_safe",
                "blockers",
                "receipt_sha256",
            ],
            "required_case_fields": [
                "ordinal",
                "case_id",
                "case_input_sha256",
                "runtime_input_sha256",
                "independent_oracle_input_sha256",
                "expected_outcome",
                "observed_status",
                "expected_error_code",
                "observed_error_code",
                "operational_result_sha256",
                "independent_result_sha256",
                "accepted_iteration_count",
                "rejected_step_count",
                "energy_force_evaluation_count",
                "accepted_energy_ledger",
                "coordinate_traces",
                "metric_values",
                "case_passed",
            ],
            "required_coordinate_trace_fields": [
                "case_id",
                "trace_source",
                "trace_state",
                "coordinate_dtype",
                "coordinate_unit",
                "coordinate_encoding",
                "coordinate_digest_algorithm",
                "atom_count",
                "accepted_iteration_count",
                "rejected_step_count",
                "energy_force_evaluation_count",
                "trace_length",
                "accepted_energy_ledger",
                "steps",
                "trace_sha256",
            ],
            "required_coordinate_trace_step_fields": [
                "case_id",
                "trace_source",
                "trace_ordinal",
                "evaluation_index",
                "iteration",
                "trial",
                "outcome",
                "raw_coordinates_angstrom_hex",
                "raw_coordinates_f64le_sha256",
                "evaluated_coordinates_angstrom_hex",
                "evaluated_coordinates_f64le_sha256",
                "energy_kcal_per_mol",
                "step_identity_sha256",
            ],
            "passing_case_expected_and_observed_error_codes_must_be_null": True,
            "failing_case_observed_error_code_must_equal_expected": True,
            "zero_evaluation_failure_numeric_results_must_be_absent": True,
            "started_failure_ledger_must_be_retained": True,
            "metric_values_must_be_finite_binary64_or_exact_boolean": True,
            "failed_metrics_and_cases_must_be_retained": True,
        },
        "review_and_lifecycle": {
            "independent_result_review_required_after_receipt_creation": True,
            "implementation_author_cannot_self_accept_results": True,
            "scientific_reviewer_cannot_self_accept_results": True,
            "result_reviewer_identity_sha256_required": True,
            "reviewed_at_utc_required": True,
            "supersession_state_required": True,
            "external_revocation_state_required": True,
            "publication_authorized": False,
            "parameter_fitting_proposal_authorized": False,
            "parameter_fitting_authorized": False,
        },
        "current_state": {
            "contract_frozen": True,
            "result_receipt_present": False,
            "result_receipt_writer_implemented": True,
            "validation_runner_implemented": True,
            "complete_coordinate_trace_contract_implemented": True,
            "validation_execution_authorized": False,
            "validation_results_collected": False,
        },
        "claim_policy": _closed_claim_policy(),
    }


def reference_minimization_validation_execution_environment_contract_document() -> dict[
    str, Any
]:
    """Return the frozen environment contract; no environment receipt exists."""

    document = _environment_contract_projection()
    document["contract_sha256"] = _sha256(document)
    if document["contract_sha256"] != (
        FROZEN_REFERENCE_MINIMIZATION_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256
    ):
        raise ReferenceMinimizationValidationReceiptContractError(
            "frozen minimization execution environment contract SHA-256 drifted"
        )
    return document


def reference_minimization_validation_result_receipt_contract_document() -> dict[
    str, Any
]:
    """Return the frozen result schema; no result values are evaluated."""

    document = _result_contract_projection()
    document["contract_sha256"] = _sha256(document)
    if document["contract_sha256"] != (
        FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256
    ):
        raise ReferenceMinimizationValidationReceiptContractError(
            "frozen minimization result receipt contract SHA-256 drifted"
        )
    return document


def _require_exact_contract_document(
    payload: Mapping[str, Any],
    *,
    expected: Mapping[str, Any],
    name: str,
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ReferenceMinimizationValidationReceiptContractError(
            f"{name} must be a mapping"
        )
    try:
        observed = json.loads(_canonical_bytes(dict(payload)).decode("ascii"))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ReferenceMinimizationValidationReceiptContractError(
            f"{name} is invalid"
        ) from exc
    if observed != expected:
        raise ReferenceMinimizationValidationReceiptContractError(
            f"{name} does not match the frozen record"
        )
    return observed


def require_reference_minimization_validation_execution_environment_contract_document(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    return _require_exact_contract_document(
        payload,
        expected=reference_minimization_validation_execution_environment_contract_document(),
        name="minimization execution environment contract document",
    )


def require_reference_minimization_validation_result_receipt_contract_document(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    return _require_exact_contract_document(
        payload,
        expected=reference_minimization_validation_result_receipt_contract_document(),
        name="minimization result receipt contract document",
    )


def reference_minimization_validation_execution_readiness_decision() -> dict[str, Any]:
    """Return the current fail-closed decision without evaluating results."""

    environment = (
        reference_minimization_validation_execution_environment_contract_document()
    )
    result = reference_minimization_validation_result_receipt_contract_document()
    return {
        "review_contract_sha256": FROZEN_REFERENCE_MINIMIZATION_VALIDATION_REVIEW_CONTRACT_SHA256,
        "execution_environment_contract_sha256": environment["contract_sha256"],
        "result_receipt_contract_sha256": result["contract_sha256"],
        "receipt_contracts_frozen": True,
        "independent_review_attestation_present": False,
        "authorization_contract_frozen": True,
        "authorization_receipt_present": False,
        "trusted_reviewer_key_present": False,
        "trusted_operator_key_present": False,
        "atomic_nonce_reservation_primitive_implemented": True,
        "authorization_nonce_reserved": False,
        "run_start_environment_receipt_primitive_implemented": True,
        "execution_environment_receipt_present": False,
        "validation_runner_implemented": True,
        "result_receipt_writer_implemented": True,
        "validation_execution_authorized": False,
        "validation_results_collected": False,
        "parameter_fitting_proposal_authorized": False,
        "parameter_fitting_authorized": False,
        "blockers": list(_CURRENT_BLOCKERS),
    }


def require_reference_minimization_validation_execution_ready() -> NoReturn:
    """Always fail closed: contracts alone cannot authorize an execution."""

    decision = reference_minimization_validation_execution_readiness_decision()
    blockers = ", ".join(decision["blockers"])
    raise ReferenceMinimizationValidationReceiptContractError(
        f"CPU minimization validation execution is not authorized; blockers: {blockers}"
    )


__all__ = [
    "FROZEN_REFERENCE_MINIMIZATION_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256",
    "FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256",
    "REFERENCE_MINIMIZATION_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_ID",
    "REFERENCE_MINIMIZATION_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SCHEMA_ID",
    "REFERENCE_MINIMIZATION_VALIDATION_EXECUTION_ENVIRONMENT_RECEIPT_SCHEMA_ID",
    "REFERENCE_MINIMIZATION_VALIDATION_RECEIPT_CONTRACT_VERSION",
    "REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_CONTRACT_ID",
    "REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_CONTRACT_SCHEMA_ID",
    "REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_SCHEMA_ID",
    "ReferenceMinimizationValidationReceiptContractError",
    "reference_minimization_validation_execution_environment_contract_document",
    "reference_minimization_validation_execution_readiness_decision",
    "reference_minimization_validation_result_receipt_contract_document",
    "require_reference_minimization_validation_execution_environment_contract_document",
    "require_reference_minimization_validation_execution_ready",
    "require_reference_minimization_validation_result_receipt_contract_document",
]
