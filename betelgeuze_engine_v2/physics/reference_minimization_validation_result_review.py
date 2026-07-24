"""Independent result-review attestation contract for minimization validation.

The module freezes the shape and verification rules for a future independent
review of one exact minimization validation result receipt.  It does not ship a
result review attestation, choose a trusted result reviewer, collect results,
or promote any scientific, fitting, benchmark, product, or customer claim.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import struct
from typing import Any, Mapping, Sequence

from .reference_minimization_validation_artifact_binding import (
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_ARTIFACT_BINDING_SHA256,
)
from .reference_minimization_validation_authorization import (
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_CONTRACT_SHA256,
    MinimizationAuthorizationOperatorTrustAnchor,
    ReferenceMinimizationValidationAuthorizationError,
    verify_signed_reference_minimization_validation_authorization_receipt,
)
from .reference_minimization_validation_ed25519 import (
    ReferenceMinimizationValidationEd25519Error,
    sign_ed25519,
    verify_ed25519,
)
from .reference_minimization_validation_materializer import (
    cpu_minimization_validation_materialization_manifest_document,
)
from .reference_minimization_validation_protocol import (
    FROZEN_CPU_MINIMIZATION_VALIDATION_PROTOCOL_SHA256,
    cpu_minimization_validation_case_atom_count,
    cpu_minimization_validation_protocol_document,
)
from .reference_minimization_validation_receipts import (
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256,
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256,
    REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_SCHEMA_ID,
)
from .reference_minimization_validation_result_writer import (
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_WRITER_CONTRACT_SHA256,
    ReferenceMinimizationValidationResultReceipt,
    ReferenceMinimizationValidationResultWriterError,
)
from .reference_minimization_validation_review import (
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_REVIEW_CONTRACT_SHA256,
    MinimizationScientificReviewerTrustAnchor,
)
from .reference_minimization_validation_runner import (
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RUNNER_CONTRACT_SHA256,
    REFERENCE_MINIMIZATION_VALIDATION_MATRIX_WORKER_FRAME_SCHEMA_ID,
    REFERENCE_MINIMIZATION_VALIDATION_MATRIX_WORKER_REQUEST_SCHEMA_ID,
)
from .reference_minimization_validation_trajectory_comparison import (
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COMPARISON_CONTRACT_SHA256,
    TRAJECTORY_COMPARISON_ACCEPTED,
    TRAJECTORY_COMPARISON_EXPECTED_FAIL_CLOSED,
    ReferenceMinimizationValidationTrajectoryComparisonError,
    require_reference_minimization_validation_trajectory_comparison,
)


REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_CONTRACT_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_validation_result_review_contract/8.0.0"
)
REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_ATTESTATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_validation_result_review_attestation/8.0.0"
)
REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_CONTRACT_ID = (
    "cpu_reference_minimization_validation_independent_result_review_contract/8.0.0"
)
REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_CONTRACT_VERSION = "8.0.0"
REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_CONTRACT_FROZEN_AT_UTC = "2026-07-24T00:00:00Z"
REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_SIGNATURE_ALGORITHM = "ed25519"
REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_MAX_VALIDITY = timedelta(days=30)
RESULT_REVIEW_OUTCOME_ACCEPTED = "accepted"
RESULT_REVIEW_OUTCOME_REJECTED = "rejected"
RETAINED_METRIC_VALUE_ACCEPTED = "retained_metric_value_accepted"
RETAINED_METRIC_VALUE_REJECTED = "retained_metric_value_rejected"
REQUIRED_METRIC_VALUE_MISSING_REJECTED = "required_metric_value_missing_rejected"
UNEXPECTED_METRIC_VALUE_REJECTED = "unexpected_metric_value_rejected"
EXPECTED_FAIL_CLOSED_OUTCOME_ACCEPTED = "expected_fail_closed_outcome_accepted"
EXPECTED_FAIL_CLOSED_OUTCOME_REJECTED = "expected_fail_closed_outcome_rejected"
PASS_CASE_OUTCOME_REJECTED = "pass_case_outcome_rejected"
REQUIRED_RESULT_EVIDENCE_ACCEPTED = "required_result_evidence_accepted"
REQUIRED_RESULT_EVIDENCE_REJECTED = "required_result_evidence_rejected"
COORDINATE_TRACE_ACCEPTED = "coordinate_trace_accepted"
EXPECTED_EMPTY_COORDINATE_TRACE_ACCEPTED = "expected_empty_coordinate_trace_accepted"
COORDINATE_TRACE_REJECTED = "coordinate_trace_rejected"
COORDINATE_TRACE_STEP_ACCEPTED = "coordinate_trace_step_accepted"
WORKER_EXECUTION_EVIDENCE_ACCEPTED = "worker_execution_evidence_accepted"
WORKER_EXECUTION_EVIDENCE_REJECTED = "worker_execution_evidence_rejected"
TRAJECTORY_COMPARISON_EVIDENCE_ACCEPTED = "trajectory_comparison_evidence_accepted"
EXPECTED_FAIL_CLOSED_TRAJECTORY_COMPARISON_ACCEPTED = "expected_fail_closed_trajectory_comparison_accepted"
TRAJECTORY_COMPARISON_EVIDENCE_REJECTED = "trajectory_comparison_evidence_rejected"

FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_CONTRACT_SHA256 = (
    "8793f138185f19d5e7c1465cc8850c7f466d1df99274d831ac5d91f324cdaea0"
)
FROZEN_LEGACY_REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_CONTRACT_SHA256_V7 = (
    "85be6ec706b0220b5a10e80c10d158601ce438016903e0695a8ea22f3ed1bca5"
)
FROZEN_LEGACY_REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_CONTRACT_SHA256_V6 = (
    "b62a476bac963b63ee48c3a763d2423103676db0ec568380dc28104d246c4fe2"
)
FROZEN_LEGACY_REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_CONTRACT_SHA256_V5 = (
    "fef2198e4cc18b07f3607cc4036555f737eb423f51264179738b261dee3ea420"
)
FROZEN_LEGACY_REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_CONTRACT_SHA256_V4 = (
    "bb53f31227d7be92743b0fc49164237ec81948836ec82441c2854a65e0cb5e0a"
)
FROZEN_LEGACY_REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_CONTRACT_SHA256_V3 = (
    "b1b981940ea3d5a68f3aa936e4569e6756a8a9b88b0e86137c10d8ec4deebcfa"
)
FROZEN_LEGACY_REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_CONTRACT_SHA256_V2 = (
    "2ad7c25661e4192eb988237a0c351a0e30fdde9c16854f825134b4148744eb82"
)

_REQUIRED_RESULT_REVIEW_CHECK_IDS = (
    "result_receipt_identity_and_exact_dependency_chain_reviewed",
    "protocol_runner_and_writer_contract_identities_reviewed",
    "complete_worker_lifecycle_and_retained_case_aggregate_reviewed",
    "ordered_fourteen_case_coverage_and_failure_inclusion_reviewed",
    "retained_metric_dispositions_complete_and_ordered_reviewed",
    "iteration_rejection_evaluation_and_energy_trace_reviewed",
    "complete_ordered_coordinate_traces_and_step_identities_reviewed",
    "trajectory_alignment_threshold_and_checkpoint_restart_evidence_reviewed",
    "cryptographic_pre_execution_review_authorization_and_role_chain_reviewed",
    "supersession_and_external_revocation_state_reviewed",
    "source_dependency_and_environment_identity_rows_reviewed",
    "nonpromotion_and_synthetic_parameter_limitations_acknowledged",
)
_REQUIRED_LIMITATION_IDS = (
    "synthetic_fixture_values_are_not_reviewed_runtime_parameter_values",
    "contract_result_review_is_not_scientific_minimization_validation",
    "test_only_endpoint_comparisons_are_not_validation_results",
    "result_review_does_not_establish_two_host_reproducibility",
    "result_review_does_not_establish_external_implementation_comparison",
    "result_review_does_not_establish_chemical_applicability",
    "result_review_does_not_authorize_parameter_fitting",
    "test_only_result_review_attestation_is_not_production_evidence",
    "contract_result_review_does_not_authorize_production_claim_promotion",
)
_CLOSED_GATE_BLOCKERS = (
    "signed_independent_result_review_attestation_missing",
    "trusted_independent_result_reviewer_key_not_provided",
    "implementation_author_and_independent_result_reviewer_separation_not_attested",
    "production_result_receipt_missing",
    "independent_result_review_missing",
    "result_receipt_external_authenticity_not_established",
    "same_uid_artifact_replacement_resistance_not_established",
    "independent_result_review_dependency_manifest_reverification_missing",
    "worker_process_starttime_and_boot_id_binding_missing",
    "incomplete_raw_partial_transcript_not_independently_replayable",
    "two_cpu_host_reproducibility_missing",
    "independent_external_implementation_comparison_missing",
    "reviewed_runtime_parameter_values_not_bound",
    "scientific_parameter_applicability_not_established",
    "parameter_fitting_not_authorized",
    "scientific_validation_missing",
    "product_integration_not_qualified",
)
_POST_ATTESTATION_BLOCKERS = (
    "production_result_receipt_missing",
    "test_only_result_review_attestation_is_not_production_evidence",
    "independent_result_review_missing",
    "result_receipt_external_authenticity_not_established",
    "same_uid_artifact_replacement_resistance_not_established",
    "independent_result_review_dependency_manifest_reverification_missing",
    "worker_process_starttime_and_boot_id_binding_missing",
    "incomplete_raw_partial_transcript_not_independently_replayable",
    "two_cpu_host_reproducibility_missing",
    "independent_external_implementation_comparison_missing",
    "reviewed_runtime_parameter_values_not_bound",
    "scientific_parameter_applicability_not_established",
    "parameter_fitting_not_authorized",
    "scientific_validation_missing",
    "product_integration_not_qualified",
)
_REJECTED_RESULT_BLOCKERS = (
    "result_receipt_review_rejected",
    *_POST_ATTESTATION_BLOCKERS,
)


class ReferenceMinimizationValidationResultReviewError(ValueError):
    """The result-review contract, attestation, trust anchor, or signature is invalid."""


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
        raise ReferenceMinimizationValidationResultReviewError("result review artifact is not canonical JSON") from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ReferenceMinimizationValidationResultReviewError(f"{name} must be a lowercase SHA-256")
    if any(character not in "0123456789abcdef" for character in value):
        raise ReferenceMinimizationValidationResultReviewError(f"{name} must be a lowercase SHA-256")
    return value


def _parse_utc(value: object, *, name: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ReferenceMinimizationValidationResultReviewError(f"{name} must be second-resolution UTC")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ReferenceMinimizationValidationResultReviewError(f"{name} must be second-resolution UTC") from exc
    return parsed


def _format_utc(value: datetime, *, name: str) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ReferenceMinimizationValidationResultReviewError(f"{name} must be timezone-aware")
    normalized = value.astimezone(timezone.utc)
    if normalized.microsecond:
        raise ReferenceMinimizationValidationResultReviewError(f"{name} must use second resolution")
    return normalized.strftime("%Y-%m-%dT%H:%M:%SZ")


def _require_key(value: bytes | str, *, name: str) -> bytes:
    if isinstance(value, str):
        key = value.encode("utf-8")
    elif isinstance(value, bytes):
        key = value
    else:
        raise ReferenceMinimizationValidationResultReviewError(f"{name} must be bytes or text")
    if len(key) != 32:
        raise ReferenceMinimizationValidationResultReviewError(f"{name} must contain exactly 32 bytes")
    return key


def _require_key_id(value: object) -> str:
    if not isinstance(value, str) or not value or len(value) > 128:
        raise ReferenceMinimizationValidationResultReviewError(
            "result reviewer key id must contain 1 to 128 characters"
        )
    if any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for character in value):
        raise ReferenceMinimizationValidationResultReviewError("result reviewer key id contains unsupported characters")
    return value


def _validated_result_receipt_document(
    result_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Normalize and fully revalidate one result-writer receipt."""

    if not isinstance(result_receipt, Mapping):
        raise ReferenceMinimizationValidationResultReviewError("result receipt must be a mapping")
    document = json.loads(_canonical_bytes(dict(result_receipt)).decode("ascii"))
    receipt_sha256 = _require_sha256(document.get("receipt_sha256"), name="result receipt")
    try:
        validated = ReferenceMinimizationValidationResultReceipt(
            receipt_sha256=receipt_sha256,
            canonical_document_bytes=_canonical_bytes(document),
        )
    except ReferenceMinimizationValidationResultWriterError as exc:
        raise ReferenceMinimizationValidationResultReviewError(
            "result receipt failed full result-writer contract validation"
        ) from exc
    return validated.to_dict()


def _metric_contract_rows() -> dict[str, dict[str, Any]]:
    protocol = cpu_minimization_validation_protocol_document()
    return {row["metric_id"]: dict(row) for row in protocol["numerical_protocol"]["metrics"]}


def _threshold_pass(operator: str, value: float, threshold: float) -> bool:
    if operator == "equal":
        return value == threshold
    if operator == "less_than_or_equal":
        return value <= threshold
    if operator == "greater_than_or_equal":
        return value >= threshold
    raise ReferenceMinimizationValidationResultReviewError("result review metric threshold operator is unsupported")


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _is_nonzero_sha256(value: object) -> bool:
    return _is_sha256(value) and value != "0" * 64


def _is_exact_nonnegative_int(value: object) -> bool:
    return type(value) is int and value >= 0


def _is_finite_number(value: object) -> bool:
    return type(value) in {int, float} and not isinstance(value, bool) and math.isfinite(float(value))


def _allowed_pass_status_error_pairs(*, lane: str, evaluator_scope: str) -> frozenset[tuple[str, str | None]]:
    if lane == "unconstrained_v1" and evaluator_scope == "reference_forcefield_v1":
        line_search_error = "bounded_backtracking_exhausted"
    elif lane in {"constrained_v2", "fixed_born_constrained_v2"} and (
        evaluator_scope in {"reference_forcefield_v2", "reference_forcefield_v2_with_fixed_born"}
    ):
        line_search_error = "bounded_projected_backtracking_exhausted"
    else:
        raise ReferenceMinimizationValidationResultReviewError(
            "passing minimization case lane or evaluator scope is unsupported"
        )
    return frozenset(
        {
            ("converged", None),
            ("max_iterations_reached", "maximum_iteration_budget_exhausted"),
            ("line_search_failed", line_search_error),
        }
    )


def _ordered_protocol_case_rows() -> list[dict[str, Any]]:
    protocol = cpu_minimization_validation_protocol_document()
    materialization = cpu_minimization_validation_materialization_manifest_document()
    protocol_cases = protocol["case_manifest"]["cases"]
    materialized_cases = materialization["cases"]
    if len(protocol_cases) != 14 or len(materialized_cases) != 14:
        raise ReferenceMinimizationValidationResultReviewError("protocol and materialization case counts diverged")
    rows: list[dict[str, Any]] = []
    for ordinal, (protocol_case, materialized_case) in enumerate(
        zip(protocol_cases, materialized_cases, strict=True),
        start=1,
    ):
        if protocol_case["case_id"] != materialized_case["case_id"]:
            raise ReferenceMinimizationValidationResultReviewError("protocol and materialization case order diverged")
        rows.append(
            {
                "ordinal": ordinal,
                "case_id": protocol_case["case_id"],
                "lane": protocol_case["lane"],
                "evaluator_scope": protocol_case["evaluator_scope"],
                "case_input_sha256": materialized_case["case_input_sha256"],
                "materialization_runtime_input_sha256": materialized_case["runtime_input_sha256"],
                "runtime_input_sha256": _sha256(materialized_case),
                "independent_oracle_input_sha256": materialized_case["independent_oracle_input_sha256"],
                "maximum_iterations": protocol_case["canonical_input"]["maximum_iterations"],
                "maximum_backtracks": protocol_case["canonical_input"]["maximum_backtracks"],
                "atom_count": cpu_minimization_validation_case_atom_count(protocol_case["case_id"]),
                "expected_outcome": protocol_case["expected_outcome"],
                "expected_error_code": protocol_case["expected_error_code"],
                "required_metric_ids": list(protocol_case["required_metric_ids"]),
            }
        )
    return rows


def _coordinate_payload_f64le_sha256(
    value: object,
    *,
    atom_count: int,
) -> str | None:
    if not isinstance(value, list) or len(value) != atom_count:
        return None
    raw = bytearray()
    for row in value:
        if not isinstance(row, list) or len(row) != 3:
            return None
        for item in row:
            if not isinstance(item, str):
                return None
            try:
                number = float.fromhex(item)
            except ValueError:
                return None
            if not math.isfinite(number) or number.hex() != item:
                return None
            raw.extend(struct.pack("<d", number))
    return hashlib.sha256(raw).hexdigest()


def _coordinate_trace_review_dispositions(
    case_row: Mapping[str, Any],
    template: Mapping[str, Any],
) -> list[dict[str, Any]]:
    traces = case_row.get("coordinate_traces")
    if not isinstance(traces, list) or len(traces) != 2:
        raise ReferenceMinimizationValidationResultReviewError("result receipt coordinate traces are incomplete")
    expected_sources = ("operational", "independent_oracle")
    dispositions: list[dict[str, Any]] = []
    for source_ordinal, (trace, expected_source) in enumerate(zip(traces, expected_sources, strict=True), start=1):
        if not isinstance(trace, Mapping):
            raise ReferenceMinimizationValidationResultReviewError("result receipt coordinate trace must be a mapping")
        steps = trace.get("steps")
        if not isinstance(steps, list):
            raise ReferenceMinimizationValidationResultReviewError(
                "result receipt coordinate trace steps must be a list"
            )
        trace_reasons: list[str] = []
        if trace.get("case_id") != template["case_id"]:
            trace_reasons.append("coordinate_trace_case_identity_mismatch")
        if trace.get("trace_source") != expected_source:
            trace_reasons.append("coordinate_trace_source_reordered_or_crosswired")
        if trace.get("trace_length") != len(steps):
            trace_reasons.append("coordinate_trace_length_mismatch")
        if trace.get("energy_force_evaluation_count") != len(steps):
            trace_reasons.append("coordinate_trace_evaluation_count_mismatch")
        trace_projection = {key: value for key, value in trace.items() if key != "trace_sha256"}
        if not _is_sha256(trace.get("trace_sha256")) or _sha256(trace_projection) != trace.get("trace_sha256"):
            trace_reasons.append("coordinate_trace_canonical_digest_mismatch")
        step_dispositions: list[dict[str, Any]] = []
        for step_ordinal, step in enumerate(steps, start=1):
            if not isinstance(step, Mapping):
                raise ReferenceMinimizationValidationResultReviewError(
                    "result receipt coordinate trace step must be a mapping"
                )
            step_reasons: list[str] = []
            if step.get("case_id") != template["case_id"] or step.get("trace_source") != expected_source:
                step_reasons.append("coordinate_trace_step_identity_crosswire")
            if step.get("trace_ordinal") != step_ordinal or step.get("evaluation_index") != step_ordinal:
                step_reasons.append("coordinate_trace_step_order_mismatch")
            raw_sha256 = _coordinate_payload_f64le_sha256(
                step.get("raw_coordinates_angstrom_hex"),
                atom_count=template["atom_count"],
            )
            evaluated_sha256 = _coordinate_payload_f64le_sha256(
                step.get("evaluated_coordinates_angstrom_hex"),
                atom_count=template["atom_count"],
            )
            if raw_sha256 is None or raw_sha256 != step.get("raw_coordinates_f64le_sha256"):
                step_reasons.append("coordinate_trace_raw_coordinate_digest_mismatch")
            if evaluated_sha256 is None or evaluated_sha256 != step.get("evaluated_coordinates_f64le_sha256"):
                step_reasons.append("coordinate_trace_evaluated_coordinate_digest_mismatch")
            step_projection = {key: value for key, value in step.items() if key != "step_identity_sha256"}
            if not _is_sha256(step.get("step_identity_sha256")) or _sha256(step_projection) != step.get(
                "step_identity_sha256"
            ):
                step_reasons.append("coordinate_trace_step_digest_mismatch")
            step_disposition = COORDINATE_TRACE_STEP_ACCEPTED if not step_reasons else COORDINATE_TRACE_REJECTED
            if step_reasons:
                trace_reasons.append(f"coordinate_trace_step_{step_ordinal}_rejected")
            step_dispositions.append(
                {
                    "trace_ordinal": step_ordinal,
                    "evaluation_index": step.get("evaluation_index"),
                    "iteration": step.get("iteration"),
                    "trial": step.get("trial"),
                    "outcome": step.get("outcome"),
                    "step_identity_sha256": step.get("step_identity_sha256"),
                    "raw_coordinates_f64le_sha256": step.get("raw_coordinates_f64le_sha256"),
                    "evaluated_coordinates_f64le_sha256": step.get("evaluated_coordinates_f64le_sha256"),
                    "disposition": step_disposition,
                    "rejection_reasons": step_reasons,
                }
            )
        trace_state = trace.get("trace_state")
        expected_empty = template["expected_outcome"] == "fail_closed" and (
            expected_source == "operational" or trace.get("energy_force_evaluation_count") == 0
        )
        if steps:
            if trace_state != "evaluated":
                trace_reasons.append("coordinate_trace_nonempty_state_invalid")
            disposition = COORDINATE_TRACE_ACCEPTED if not trace_reasons else COORDINATE_TRACE_REJECTED
        else:
            if not expected_empty or trace_state != ("not_evaluated_expected_fail_closed"):
                trace_reasons.append("coordinate_trace_unexpected_empty")
            disposition = EXPECTED_EMPTY_COORDINATE_TRACE_ACCEPTED if not trace_reasons else COORDINATE_TRACE_REJECTED
        dispositions.append(
            {
                "source_ordinal": source_ordinal,
                "trace_source": expected_source,
                "trace_state": trace_state,
                "trace_length": len(steps),
                "trace_sha256": trace.get("trace_sha256"),
                "accepted_iteration_count": trace.get("accepted_iteration_count"),
                "rejected_step_count": trace.get("rejected_step_count"),
                "energy_force_evaluation_count": trace.get("energy_force_evaluation_count"),
                "disposition": disposition,
                "rejection_reasons": trace_reasons,
                "step_dispositions": step_dispositions,
            }
        )
    return dispositions


def _trajectory_comparison_review_disposition(
    case_row: Mapping[str, Any],
    template: Mapping[str, Any],
) -> dict[str, Any]:
    traces = case_row.get("coordinate_traces")
    if not isinstance(traces, list) or len(traces) != 2 or not all(isinstance(trace, Mapping) for trace in traces):
        raise ReferenceMinimizationValidationResultReviewError(
            "trajectory comparison review requires both coordinate traces"
        )
    try:
        comparison = require_reference_minimization_validation_trajectory_comparison(
            case_row.get("trajectory_comparison"),
            expected_case_id=template["case_id"],
            expected_outcome=template["expected_outcome"],
            operational_trace=traces[0],
            independent_trace=traces[1],
        )
    except ReferenceMinimizationValidationTrajectoryComparisonError as exc:
        raise ReferenceMinimizationValidationResultReviewError(
            "trajectory comparison failed independent result-review verification"
        ) from exc
    checkpoint = comparison["checkpoint_restart_evidence"]
    reasons: list[str] = []
    if comparison["trajectory_comparison_passed"] is not True:
        reasons.append("trajectory_comparison_rejected")
    if checkpoint["checkpoint_restart_passed"] is not True:
        reasons.append("checkpoint_restart_comparison_rejected")
    if comparison["comparison_passed"] is not True:
        reasons.append("case_comparison_rejected")
    if reasons:
        disposition = TRAJECTORY_COMPARISON_EVIDENCE_REJECTED
    elif comparison["trajectory_comparison_disposition"] == TRAJECTORY_COMPARISON_EXPECTED_FAIL_CLOSED:
        disposition = EXPECTED_FAIL_CLOSED_TRAJECTORY_COMPARISON_ACCEPTED
    else:
        disposition = TRAJECTORY_COMPARISON_EVIDENCE_ACCEPTED
    return {
        "comparison_sha256": comparison["comparison_sha256"],
        "operational_trace_sha256": comparison["operational_trace_sha256"],
        "independent_trace_sha256": comparison["independent_trace_sha256"],
        "operational_trace_length": comparison["operational_trace_length"],
        "independent_trace_length": comparison["independent_trace_length"],
        "aligned_step_count": comparison["aligned_step_count"],
        "trace_length_disposition": comparison["trace_length_disposition"],
        "step_identity_alignment_disposition": comparison["step_identity_alignment_disposition"],
        "branch_sequence_disposition": comparison["branch_sequence_disposition"],
        "rejection_sequence_disposition": comparison["rejection_sequence_disposition"],
        "accepted_iteration_count_disposition": comparison["accepted_iteration_count_disposition"],
        "rejected_step_count_disposition": comparison["rejected_step_count_disposition"],
        "energy_force_evaluation_count_disposition": comparison["energy_force_evaluation_count_disposition"],
        "raw_coordinate_max_abs_error_angstrom": comparison["raw_coordinate_max_abs_error_angstrom"],
        "raw_coordinate_rms_error_angstrom": comparison["raw_coordinate_rms_error_angstrom"],
        "evaluated_coordinate_max_abs_error_angstrom": comparison["evaluated_coordinate_max_abs_error_angstrom"],
        "evaluated_coordinate_rms_error_angstrom": comparison["evaluated_coordinate_rms_error_angstrom"],
        "energy_max_abs_error_kcal_per_mol": comparison["energy_max_abs_error_kcal_per_mol"],
        "energy_rms_error_kcal_per_mol": comparison["energy_rms_error_kcal_per_mol"],
        "trajectory_comparison_disposition": comparison["trajectory_comparison_disposition"],
        "checkpoint_restart_disposition": checkpoint["checkpoint_restart_disposition"],
        "checkpoint_restart_evidence_sha256": checkpoint["checkpoint_restart_evidence_sha256"],
        "step_dispositions": [
            {
                "comparison_ordinal": row["comparison_ordinal"],
                "evaluation_index": row["evaluation_index"],
                "iteration": row["iteration"],
                "trial": row["trial"],
                "outcome": row["outcome"],
                "step_comparison_sha256": row["step_comparison_sha256"],
                "disposition": row["step_comparison_disposition"],
            }
            for row in comparison["step_comparisons"]
        ],
        "disposition": disposition,
        "rejection_reasons": reasons,
    }


def _case_review_row_from_result_case(case_row: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(case_row, Mapping):
        raise ReferenceMinimizationValidationResultReviewError("result receipt case row must be a mapping")
    ordinal = case_row.get("ordinal")
    case_id = case_row.get("case_id")
    if not isinstance(ordinal, int) or ordinal < 1 or ordinal > 14:
        raise ReferenceMinimizationValidationResultReviewError("result receipt case ordinal is invalid")
    if not isinstance(case_id, str) or not case_id:
        raise ReferenceMinimizationValidationResultReviewError("result receipt case id is invalid")
    template = next(
        (row for row in _ordered_protocol_case_rows() if row["ordinal"] == ordinal),
        None,
    )
    if template is None or template["case_id"] != case_id:
        raise ReferenceMinimizationValidationResultReviewError("result receipt case order or identity drifted")
    case_input_sha256 = _require_sha256(case_row.get("case_input_sha256"), name="result receipt case input")
    if case_input_sha256 != template["case_input_sha256"]:
        raise ReferenceMinimizationValidationResultReviewError("result receipt case input identity drifted")
    metric_values = case_row.get("metric_values")
    if not isinstance(metric_values, list):
        raise ReferenceMinimizationValidationResultReviewError("result receipt metric values are invalid")
    required_metric_ids = list(template["required_metric_ids"])
    metric_contract = _metric_contract_rows()
    seen_required: set[str] = set()
    metric_dispositions: list[dict[str, Any]] = []
    for retained in metric_values:
        if not isinstance(retained, Mapping):
            raise ReferenceMinimizationValidationResultReviewError("result receipt retained metric row is invalid")
        metric_id = retained.get("metric_id")
        value = retained.get("value")
        contract_row = metric_contract.get(metric_id) if isinstance(metric_id, str) else None
        expected_once = (
            isinstance(metric_id, str)
            and metric_id in required_metric_ids
            and metric_id not in seen_required
            and contract_row is not None
        )
        if expected_once:
            seen_required.add(metric_id)
            threshold_operator = str(contract_row["threshold_operator"])
            threshold_value = float(contract_row["threshold_value"])
            accepted = _is_finite_number(value) and _threshold_pass(threshold_operator, float(value), threshold_value)
            disposition = RETAINED_METRIC_VALUE_ACCEPTED if accepted else RETAINED_METRIC_VALUE_REJECTED
        else:
            threshold_operator = None
            threshold_value = None
            disposition = UNEXPECTED_METRIC_VALUE_REJECTED
        metric_dispositions.append(
            {
                "metric_id": metric_id,
                "value": value,
                "threshold_operator": threshold_operator,
                "threshold_value": threshold_value,
                "disposition": disposition,
            }
        )
    missing_metric_dispositions = [
        {
            "metric_id": metric_id,
            "disposition": REQUIRED_METRIC_VALUE_MISSING_REJECTED,
        }
        for metric_id in required_metric_ids
        if metric_id not in seen_required
    ]
    retained_metric_values = {
        row["metric_id"]: row["value"] for row in metric_dispositions if row["threshold_operator"] is not None
    }
    case_passed = case_row.get("case_passed") is True
    if template["expected_outcome"] == "fail_closed":
        failure_disposition = (
            EXPECTED_FAIL_CLOSED_OUTCOME_ACCEPTED if case_passed else EXPECTED_FAIL_CLOSED_OUTCOME_REJECTED
        )
    else:
        failure_disposition = None if case_passed else PASS_CASE_OUTCOME_REJECTED

    runtime_input_sha256 = case_row.get("runtime_input_sha256")
    independent_oracle_input_sha256 = case_row.get("independent_oracle_input_sha256")
    operational_result_sha256 = case_row.get("operational_result_sha256")
    independent_result_sha256 = case_row.get("independent_result_sha256")
    observed_status = case_row.get("observed_status")
    observed_error_code = case_row.get("observed_error_code")
    accepted_iteration_count = case_row.get("accepted_iteration_count")
    rejected_step_count = case_row.get("rejected_step_count")
    energy_force_evaluation_count = case_row.get("energy_force_evaluation_count")
    accepted_energy_ledger = case_row.get("accepted_energy_ledger")
    evidence_rejection_reasons: list[str] = []
    if runtime_input_sha256 != template["runtime_input_sha256"]:
        evidence_rejection_reasons.append("runtime_input_identity_mismatch")
    if independent_oracle_input_sha256 != template["independent_oracle_input_sha256"]:
        evidence_rejection_reasons.append("independent_oracle_input_identity_mismatch")
    for field_name, value in (
        ("accepted_iteration_count", accepted_iteration_count),
        ("rejected_step_count", rejected_step_count),
        ("energy_force_evaluation_count", energy_force_evaluation_count),
    ):
        if not _is_exact_nonnegative_int(value):
            evidence_rejection_reasons.append(f"{field_name}_invalid")
    if not isinstance(accepted_energy_ledger, list) or not all(
        _is_finite_number(value) for value in accepted_energy_ledger
    ):
        evidence_rejection_reasons.append("accepted_energy_ledger_invalid")
        ledger_for_digest: list[object] = []
    else:
        ledger_for_digest = list(accepted_energy_ledger)
    counts_valid = all(
        _is_exact_nonnegative_int(value)
        for value in (
            accepted_iteration_count,
            rejected_step_count,
            energy_force_evaluation_count,
        )
    )
    ledger_valid = "accepted_energy_ledger_invalid" not in evidence_rejection_reasons
    if ledger_valid and any(next_value > value for value, next_value in zip(ledger_for_digest, ledger_for_digest[1:])):
        evidence_rejection_reasons.append("accepted_energy_ledger_not_monotonic")
    maximum_iterations = template["maximum_iterations"]
    maximum_backtracks = template["maximum_backtracks"]
    if counts_valid:
        if accepted_iteration_count > maximum_iterations:
            evidence_rejection_reasons.append("accepted_iteration_count_exceeds_case_budget")
    if template["expected_outcome"] == "pass":
        if (observed_status, observed_error_code) not in (
            _allowed_pass_status_error_pairs(
                lane=template["lane"],
                evaluator_scope=template["evaluator_scope"],
            )
        ):
            evidence_rejection_reasons.append("pass_status_or_error_code_invalid")
        if not _is_nonzero_sha256(operational_result_sha256):
            evidence_rejection_reasons.append("operational_result_identity_missing")
        if not _is_nonzero_sha256(independent_result_sha256):
            evidence_rejection_reasons.append("independent_result_identity_missing")
        if counts_valid and ledger_valid:
            if observed_status == "max_iterations_reached" and accepted_iteration_count != maximum_iterations:
                evidence_rejection_reasons.append("maximum_iteration_status_count_mismatch")
            if observed_status == "line_search_failed":
                minimum_rejections = maximum_backtracks + 1
                maximum_rejections = accepted_iteration_count * maximum_backtracks + minimum_rejections
                if (
                    accepted_iteration_count >= maximum_iterations
                    or not minimum_rejections <= rejected_step_count <= maximum_rejections
                ):
                    evidence_rejection_reasons.append("line_search_failure_status_count_mismatch")
            elif rejected_step_count > (accepted_iteration_count * maximum_backtracks):
                evidence_rejection_reasons.append("accepted_path_rejection_count_exceeds_case_progress")
            if energy_force_evaluation_count == 0:
                evidence_rejection_reasons.append("pass_energy_force_evaluation_count_empty")
            if len(ledger_for_digest) != accepted_iteration_count + 1:
                evidence_rejection_reasons.append("pass_energy_ledger_iteration_count_mismatch")
            if energy_force_evaluation_count != (accepted_iteration_count + rejected_step_count + 1):
                evidence_rejection_reasons.append("pass_evaluation_count_mismatch")
            if ledger_for_digest:
                if retained_metric_values.get("final_energy_change") != (ledger_for_digest[-1] - ledger_for_digest[0]):
                    evidence_rejection_reasons.append("final_energy_change_metric_ledger_mismatch")
                if "minimum_required_energy_decrease" in retained_metric_values and (
                    retained_metric_values["minimum_required_energy_decrease"]
                    != ledger_for_digest[0] - ledger_for_digest[-1]
                ):
                    evidence_rejection_reasons.append("minimum_energy_decrease_metric_ledger_mismatch")
    else:
        if observed_status != "fail_closed":
            evidence_rejection_reasons.append("fail_closed_status_invalid")
        if observed_error_code != template["expected_error_code"]:
            evidence_rejection_reasons.append("fail_closed_error_code_mismatch")
        if operational_result_sha256 is not None:
            evidence_rejection_reasons.append("fail_closed_operational_result_must_be_absent")
        if not _is_nonzero_sha256(independent_result_sha256):
            evidence_rejection_reasons.append("independent_result_identity_missing")
        if counts_valid and ledger_valid:
            if template["expected_error_code"] == "line_search_exhausted":
                minimum_rejections = maximum_backtracks + 1
                maximum_rejections = accepted_iteration_count * maximum_backtracks + minimum_rejections
                if (
                    accepted_iteration_count >= maximum_iterations
                    or not minimum_rejections <= rejected_step_count <= maximum_rejections
                ):
                    evidence_rejection_reasons.append("fail_closed_line_search_count_mismatch")
            elif (
                any(
                    value != 0
                    for value in (
                        accepted_iteration_count,
                        rejected_step_count,
                        energy_force_evaluation_count,
                    )
                )
                or ledger_for_digest
            ):
                evidence_rejection_reasons.append("pre_evaluation_fail_closed_case_retained_progress")
            if energy_force_evaluation_count == 0:
                if accepted_iteration_count != 0 or rejected_step_count != 0 or ledger_for_digest:
                    evidence_rejection_reasons.append("zero_evaluation_failure_evidence_mismatch")
            else:
                if len(ledger_for_digest) != accepted_iteration_count + 1:
                    evidence_rejection_reasons.append("fail_closed_energy_ledger_iteration_count_mismatch")
                if energy_force_evaluation_count != (accepted_iteration_count + rejected_step_count + 1):
                    evidence_rejection_reasons.append("fail_closed_evaluation_count_mismatch")
    coordinate_trace_dispositions = _coordinate_trace_review_dispositions(case_row, template)
    if any(
        row["disposition"]
        not in {
            COORDINATE_TRACE_ACCEPTED,
            EXPECTED_EMPTY_COORDINATE_TRACE_ACCEPTED,
        }
        for row in coordinate_trace_dispositions
    ):
        evidence_rejection_reasons.append("coordinate_trace_disposition_rejected")
    trajectory_comparison_disposition = _trajectory_comparison_review_disposition(case_row, template)
    if trajectory_comparison_disposition["disposition"] not in {
        TRAJECTORY_COMPARISON_EVIDENCE_ACCEPTED,
        EXPECTED_FAIL_CLOSED_TRAJECTORY_COMPARISON_ACCEPTED,
    }:
        evidence_rejection_reasons.append("trajectory_comparison_disposition_rejected")
    if type(case_row.get("case_passed")) is not bool:
        evidence_rejection_reasons.append("case_passed_flag_invalid")
    evidence_disposition = (
        REQUIRED_RESULT_EVIDENCE_ACCEPTED if not evidence_rejection_reasons else REQUIRED_RESULT_EVIDENCE_REJECTED
    )
    return {
        "ordinal": ordinal,
        "case_id": case_id,
        "case_input_sha256": case_input_sha256,
        "runtime_input_sha256": runtime_input_sha256,
        "independent_oracle_input_sha256": independent_oracle_input_sha256,
        "operational_result_sha256": operational_result_sha256,
        "independent_result_sha256": independent_result_sha256,
        "expected_outcome": template["expected_outcome"],
        "observed_status": observed_status,
        "expected_error_code": template["expected_error_code"],
        "observed_error_code": observed_error_code,
        "accepted_iteration_count": accepted_iteration_count,
        "rejected_step_count": rejected_step_count,
        "energy_force_evaluation_count": energy_force_evaluation_count,
        "accepted_energy_ledger_length": len(ledger_for_digest),
        "accepted_energy_ledger_sha256": _sha256(ledger_for_digest),
        "coordinate_trace_dispositions": coordinate_trace_dispositions,
        "trajectory_comparison_disposition": trajectory_comparison_disposition,
        "result_evidence_disposition": evidence_disposition,
        "result_evidence_rejection_reasons": evidence_rejection_reasons,
        "case_passed": case_passed,
        "metric_dispositions": metric_dispositions,
        "missing_metric_dispositions": missing_metric_dispositions,
        "failure_disposition": failure_disposition,
    }


def _case_review_rows_from_result_receipt(
    result_receipt: Mapping[str, Any],
) -> list[dict[str, Any]]:
    case_results = result_receipt.get("case_results")
    if not isinstance(case_results, list) or len(case_results) != 14:
        raise ReferenceMinimizationValidationResultReviewError("result receipt case coverage is incomplete")
    rows = [_case_review_row_from_result_case(row) for row in case_results]
    if tuple(row["ordinal"] for row in rows) != tuple(range(1, 15)):
        raise ReferenceMinimizationValidationResultReviewError("result receipt case rows are reordered")
    return rows


def _result_review_outcome(
    case_review_rows: Sequence[Mapping[str, Any]],
    worker_execution_review: Mapping[str, Any],
) -> str:
    accepted = (
        worker_execution_review.get("disposition") == WORKER_EXECUTION_EVIDENCE_ACCEPTED
        and worker_execution_review.get("completion_state") == "complete"
        and worker_execution_review.get("runtime_lifecycle_completion_state") == "complete"
        and worker_execution_review.get("payload_frame_count") == 14
        and worker_execution_review.get("discarded_partial_payload_count") == 0
        and worker_execution_review.get("native_pre_post_snapshot_equality_verified") is True
        and worker_execution_review.get("native_mapping_lifetime_closure_claimed") is False
        and not worker_execution_review.get("rejection_reasons")
        and all(
            row.get("case_passed") is True
            and row.get("result_evidence_disposition") == REQUIRED_RESULT_EVIDENCE_ACCEPTED
            and not row.get("result_evidence_rejection_reasons")
            and not row.get("missing_metric_dispositions")
            and len(row.get("coordinate_trace_dispositions", ())) == 2
            and all(
                trace.get("disposition")
                in {
                    COORDINATE_TRACE_ACCEPTED,
                    EXPECTED_EMPTY_COORDINATE_TRACE_ACCEPTED,
                }
                and not trace.get("rejection_reasons")
                and all(
                    step.get("disposition") == COORDINATE_TRACE_STEP_ACCEPTED and not step.get("rejection_reasons")
                    for step in trace.get("step_dispositions", ())
                    if isinstance(step, Mapping)
                )
                for trace in row.get("coordinate_trace_dispositions", ())
                if isinstance(trace, Mapping)
            )
            and isinstance(row.get("trajectory_comparison_disposition"), Mapping)
            and row["trajectory_comparison_disposition"].get("disposition")
            in {
                TRAJECTORY_COMPARISON_EVIDENCE_ACCEPTED,
                EXPECTED_FAIL_CLOSED_TRAJECTORY_COMPARISON_ACCEPTED,
            }
            and not row["trajectory_comparison_disposition"].get("rejection_reasons")
            and all(
                step.get("disposition") == TRAJECTORY_COMPARISON_ACCEPTED
                for step in row["trajectory_comparison_disposition"].get("step_dispositions", ())
                if isinstance(step, Mapping)
            )
            and all(
                metric.get("disposition") == RETAINED_METRIC_VALUE_ACCEPTED
                for metric in row.get("metric_dispositions", ())
                if isinstance(metric, Mapping)
            )
            and row.get("failure_disposition") in {None, EXPECTED_FAIL_CLOSED_OUTCOME_ACCEPTED}
            for row in case_review_rows
        )
    )
    return RESULT_REVIEW_OUTCOME_ACCEPTED if accepted else RESULT_REVIEW_OUTCOME_REJECTED


def _dependency_rows(rows: object) -> list[dict[str, str]]:
    if not isinstance(rows, list) or not rows:
        raise ReferenceMinimizationValidationResultReviewError(
            "result receipt dependency rows must be a non-empty list"
        )
    normalized: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise ReferenceMinimizationValidationResultReviewError("result receipt dependency row is invalid")
        artifact_id = row.get("artifact_id")
        digest = row.get("sha256")
        if not isinstance(artifact_id, str) or not artifact_id:
            raise ReferenceMinimizationValidationResultReviewError("result receipt dependency artifact id is invalid")
        normalized.append(
            {
                "artifact_id": artifact_id,
                "sha256": _require_sha256(digest, name="result receipt dependency"),
            }
        )
    if tuple(row["artifact_id"] for row in normalized) != tuple(sorted(row["artifact_id"] for row in normalized)):
        raise ReferenceMinimizationValidationResultReviewError("result receipt dependency rows are not sorted")
    return normalized


def _reconstruct_complete_worker_transcript_for_review(
    *,
    worker_request_sha256: str,
    case_results: Sequence[Mapping[str, Any]],
    lifecycle: Mapping[str, Any],
) -> tuple[bytes, list[dict[str, Any]]]:
    def finalize(projection: Mapping[str, Any]) -> dict[str, Any]:
        row = dict(projection)
        row["frame_sha256"] = _sha256(row)
        return row

    if len(case_results) != 14:
        raise ReferenceMinimizationValidationResultReviewError(
            "worker transcript reconstruction requires fourteen cases"
        )
    try:
        pre = lifecycle["pre"]
        payload = lifecycle["payload"]
        post = lifecycle["post"]
        payload_aggregate = lifecycle["payload_aggregate_sha256"]
        lifecycle_sha256 = lifecycle["lifecycle_sha256"]
    except (KeyError, TypeError) as exc:
        raise ReferenceMinimizationValidationResultReviewError("complete worker lifecycle phases are absent") from exc
    first = finalize(
        {
            "schema_id": REFERENCE_MINIMIZATION_VALIDATION_MATRIX_WORKER_FRAME_SCHEMA_ID,
            "frame_type": "preflight_complete",
            "frame_ordinal": 0,
            "worker_request_sha256": worker_request_sha256,
            "previous_frame_sha256": None,
            "runtime_pre_evidence": pre,
        }
    )
    frames = [first]
    previous = first["frame_sha256"]
    for ordinal, raw_case in enumerate(case_results, start=1):
        case = dict(raw_case)
        frame = finalize(
            {
                "schema_id": REFERENCE_MINIMIZATION_VALIDATION_MATRIX_WORKER_FRAME_SCHEMA_ID,
                "frame_type": "case_payload",
                "frame_ordinal": ordinal,
                "worker_request_sha256": worker_request_sha256,
                "previous_frame_sha256": previous,
                "case_id": case["case_id"],
                "case_observation_sha256": _sha256(case),
                "case_observation": case,
            }
        )
        frames.append(frame)
        previous = frame["frame_sha256"]
    frames.append(
        finalize(
            {
                "schema_id": REFERENCE_MINIMIZATION_VALIDATION_MATRIX_WORKER_FRAME_SCHEMA_ID,
                "frame_type": "completion",
                "frame_ordinal": 15,
                "worker_request_sha256": worker_request_sha256,
                "previous_frame_sha256": previous,
                "case_count": 14,
                "retained_case_aggregate_sha256": _sha256([dict(row) for row in case_results]),
                "runtime_payload_evidence": payload,
                "runtime_post_evidence": post,
                "runtime_payload_aggregate_sha256": payload_aggregate,
                "runtime_lifecycle_sha256": lifecycle_sha256,
                "native_mapping_lifetime_closure_claimed": False,
            }
        )
    )
    return (
        b"".join(_canonical_bytes(frame) + b"\n" for frame in frames),
        frames,
    )


def _worker_execution_review_from_result_receipt(
    result_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Project exact validated worker evidence into the signed review decision."""

    run_observation = result_receipt["run_observation"]
    case_results = run_observation["case_results"]
    evidence = run_observation["worker_execution_evidence"]
    lifecycle = evidence["runtime_lifecycle_evidence"]
    case_frame_rows = [dict(row) for row in evidence["case_frame_sha256_rows"]]
    request_document = evidence["worker_request_document"]
    request_bytes_base64 = evidence["worker_request_canonical_bytes_base64"]
    request_bytes_verified = False
    if isinstance(request_document, Mapping) and isinstance(request_bytes_base64, str):
        try:
            request_bytes = base64.b64decode(request_bytes_base64.encode("ascii"), validate=True)
        except (UnicodeEncodeError, binascii.Error, ValueError):
            request_bytes = b""
        request_bytes_verified = (
            base64.b64encode(request_bytes).decode("ascii") == request_bytes_base64
            and request_bytes == _canonical_bytes(dict(request_document)) + b"\n"
            and len(request_bytes) == evidence["worker_request_byte_count"]
            and _sha256(dict(request_document)) == evidence["worker_request_sha256"]
            and request_document.get("schema_id") == REFERENCE_MINIMIZATION_VALIDATION_MATRIX_WORKER_REQUEST_SCHEMA_ID
        )
    materialization_sha256 = cpu_minimization_validation_materialization_manifest_document()[
        "materialization_manifest_sha256"
    ]
    expected_request_provenance = {
        "expected_authorization_nonce_sha256": run_observation["authorization_nonce_sha256"],
        "expected_runner_start_record_sha256": run_observation["runner_start_record_sha256"],
        "expected_code_commit_sha": run_observation["code_commit_sha"],
        "expected_runner_source_sha256": run_observation["runner_source_sha256"],
        "expected_source_manifest_sha256": run_observation["source_manifest_sha256"],
        "expected_materialization_manifest_sha256": materialization_sha256,
        "expected_dependency_artifact_sha256_rows": {
            row["artifact_id"]: row["sha256"] for row in run_observation["dependency_artifact_sha256_rows"]
        },
        "expected_environment_receipt_sha256": run_observation["environment_receipt_sha256"],
        "expected_environment_fingerprint_sha256": run_observation["environment_fingerprint_sha256"],
        "expected_python_hash_seed": run_observation["python_hash_seed"],
        "expected_application_seed": run_observation["seed"],
    }
    request_provenance_verified = isinstance(request_document, Mapping) and all(
        request_document.get(name) == expected for name, expected in expected_request_provenance.items()
    )

    retained_case_aggregate_sha256 = _require_sha256(
        evidence["retained_case_aggregate_sha256"],
        name="retained worker case aggregate",
    )
    recomputed_retained_case_aggregate_sha256 = _sha256(case_results)
    lifecycle_sha256 = _require_sha256(
        lifecycle["lifecycle_sha256"],
        name="worker runtime lifecycle",
    )
    completion_state = evidence["completion_state"]
    lifecycle_completion_state = lifecycle["completion_state"]
    discarded_partial_payload_count = evidence["discarded_child_payload_frame_count"]

    expected_case_frame_rows = [
        {
            "ordinal": row["ordinal"],
            "case_id": row["case_id"],
            "case_observation_sha256": _sha256(row),
        }
        for row in case_results
    ]
    observed_case_frame_projection = [
        {
            "ordinal": row["ordinal"],
            "case_id": row["case_id"],
            "case_observation_sha256": row["case_observation_sha256"],
        }
        for row in case_frame_rows
    ]
    case_frame_rows_match_retained_cases = observed_case_frame_projection == expected_case_frame_rows

    pre = lifecycle["pre"]
    post = lifecycle["post"]
    pre_snapshot_sha256 = (
        None
        if pre is None
        else _require_sha256(
            pre["snapshot"]["snapshot_sha256"],
            name="worker native pre snapshot",
        )
    )
    post_snapshot_sha256 = (
        None
        if post is None
        else _require_sha256(
            post["snapshot"]["snapshot_sha256"],
            name="worker native post snapshot",
        )
    )
    supervisor_child_process_id = evidence["supervisor_child_process_id"]
    pre_process_id = None if pre is None else pre["snapshot"]["process_id"]
    post_process_id = None if post is None else post["snapshot"]["process_id"]
    child_process_identity_verified = (
        type(supervisor_child_process_id) is int
        and supervisor_child_process_id > 0
        and pre_process_id == supervisor_child_process_id
        and post_process_id == supervisor_child_process_id
    )
    native_pre_post_snapshot_equality_verified = (
        evidence["native_pre_post_snapshot_equality_verified"] is True
        and pre_snapshot_sha256 is not None
        and pre_snapshot_sha256 == post_snapshot_sha256
        and child_process_identity_verified
    )

    frame_sha256s = [
        evidence["pre_frame_sha256"],
        *(row["frame_sha256"] for row in case_frame_rows),
        evidence["completion_frame_sha256"],
    ]
    complete_frame_set_verified = (
        len(frame_sha256s) == 16 and all(_is_sha256(value) for value in frame_sha256s) and len(set(frame_sha256s)) == 16
    )
    reconstructed_transcript_sha256: str | None = None
    reconstructed_transcript_byte_count: int | None = None
    canonical_transcript_verified = False
    if completion_state == "complete":
        try:
            reconstructed_raw, reconstructed_frames = _reconstruct_complete_worker_transcript_for_review(
                worker_request_sha256=evidence["worker_request_sha256"],
                case_results=case_results,
                lifecycle=lifecycle,
            )
        except ReferenceMinimizationValidationResultReviewError:
            reconstructed_raw = b""
            reconstructed_frames = []
        reconstructed_transcript_sha256 = hashlib.sha256(reconstructed_raw).hexdigest()
        reconstructed_transcript_byte_count = len(reconstructed_raw)
        canonical_transcript_verified = (
            len(reconstructed_frames) == 16
            and [row["frame_sha256"] for row in reconstructed_frames] == frame_sha256s
            and evidence["transcript_sha256"] == reconstructed_transcript_sha256
            and evidence["transcript_byte_count"] == reconstructed_transcript_byte_count
            and evidence["transcript_frame_count"] == 16
            and evidence["canonical_transcript_reconstructed"] is True
            and evidence["partial_prefix_frame_rows"] == []
            and evidence["raw_partial_not_independently_replayable"] is False
        )

    rejection_reasons: list[str] = []
    if completion_state != "complete":
        rejection_reasons.append("worker_execution_incomplete")
    if lifecycle_completion_state != "complete":
        rejection_reasons.append("worker_runtime_lifecycle_incomplete")
    if lifecycle["worker_request_sha256"] != evidence["worker_request_sha256"]:
        rejection_reasons.append("worker_request_lifecycle_mismatch")
    if not request_bytes_verified:
        rejection_reasons.append("worker_request_canonical_bytes_mismatch")
    if not request_provenance_verified:
        rejection_reasons.append("worker_request_observation_provenance_mismatch")
    if evidence["failure_code"] is not None or lifecycle["failure_code"] is not None:
        rejection_reasons.append("worker_failure_code_present")
    if (
        evidence["failure_stage"] is not None
        or evidence["worker_exit_code"] != 0
        or evidence["worker_timed_out"] is not False
        or evidence["worker_output_overflow_detected"] is not False
        or evidence["worker_communication_failed"] is not False
        or evidence["worker_request_fully_written"] is not True
        or evidence["accepted_child_payload_frame_count"] != 14
    ):
        rejection_reasons.append("worker_supervision_outcome_not_clean")
    if len(case_results) != 14:
        rejection_reasons.append("retained_case_count_mismatch")
    if len(case_frame_rows) != 14:
        rejection_reasons.append("worker_payload_frame_count_mismatch")
    if not case_frame_rows_match_retained_cases:
        rejection_reasons.append("worker_case_frame_rows_mismatch")
    if retained_case_aggregate_sha256 != recomputed_retained_case_aggregate_sha256:
        rejection_reasons.append("retained_case_aggregate_mismatch")
    if lifecycle["payload_aggregate_sha256"] is None:
        rejection_reasons.append("runtime_payload_aggregate_missing")
    if not complete_frame_set_verified:
        rejection_reasons.append("complete_worker_frame_set_missing")
    if evidence["transcript_sha256"] is None:
        rejection_reasons.append("worker_transcript_identity_missing")
    if not canonical_transcript_verified:
        rejection_reasons.append("canonical_worker_transcript_not_reconstructed")
    if discarded_partial_payload_count != 0:
        rejection_reasons.append("zero_discarded_partial_payloads_not_established")
    if not native_pre_post_snapshot_equality_verified:
        rejection_reasons.append("native_pre_post_snapshot_equality_not_verified")
    if not child_process_identity_verified:
        rejection_reasons.append("supervisor_child_process_identity_not_verified")
    if evidence["native_mapping_lifetime_closure_claimed"] is not False:
        rejection_reasons.append("native_mapping_lifetime_closure_overclaimed")

    return {
        "worker_request_sha256": _require_sha256(
            evidence["worker_request_sha256"],
            name="worker request",
        ),
        "worker_request_document": (None if request_document is None else dict(request_document)),
        "worker_request_canonical_bytes_base64": request_bytes_base64,
        "worker_request_byte_count": evidence["worker_request_byte_count"],
        "worker_request_canonical_bytes_verified": request_bytes_verified,
        "worker_request_observation_provenance_verified": (request_provenance_verified),
        "supervisor_child_process_id": supervisor_child_process_id,
        "completion_state": completion_state,
        "failure_code": evidence["failure_code"],
        "runtime_lifecycle_completion_state": lifecycle_completion_state,
        "runtime_lifecycle_sha256": lifecycle_sha256,
        "runtime_payload_aggregate_sha256": lifecycle["payload_aggregate_sha256"],
        "retained_case_count": len(case_results),
        "retained_case_aggregate_sha256": retained_case_aggregate_sha256,
        "recomputed_retained_case_aggregate_sha256": (recomputed_retained_case_aggregate_sha256),
        "payload_frame_count": len(case_frame_rows),
        "case_frame_sha256_rows": case_frame_rows,
        "case_frame_rows_match_retained_cases": (case_frame_rows_match_retained_cases),
        "pre_frame_sha256": evidence["pre_frame_sha256"],
        "completion_frame_sha256": evidence["completion_frame_sha256"],
        "transcript_sha256": evidence["transcript_sha256"],
        "transcript_byte_count": evidence["transcript_byte_count"],
        "transcript_frame_count": evidence["transcript_frame_count"],
        "reconstructed_transcript_sha256": reconstructed_transcript_sha256,
        "reconstructed_transcript_byte_count": (reconstructed_transcript_byte_count),
        "canonical_transcript_verified": canonical_transcript_verified,
        "partial_prefix_frame_rows": evidence["partial_prefix_frame_rows"],
        "partial_prefix_byte_count": evidence["partial_prefix_byte_count"],
        "partial_prefix_sha256": evidence["partial_prefix_sha256"],
        "partial_unparsed_suffix_byte_count": evidence["partial_unparsed_suffix_byte_count"],
        "partial_unparsed_suffix_sha256": evidence["partial_unparsed_suffix_sha256"],
        "raw_partial_not_independently_replayable": evidence["raw_partial_not_independently_replayable"],
        "failure_stage": evidence["failure_stage"],
        "worker_exit_code": evidence["worker_exit_code"],
        "worker_timed_out": evidence["worker_timed_out"],
        "worker_output_overflow_detected": evidence["worker_output_overflow_detected"],
        "worker_communication_failed": evidence["worker_communication_failed"],
        "worker_request_fully_written": evidence["worker_request_fully_written"],
        "complete_frame_set_verified": complete_frame_set_verified,
        "discarded_partial_payload_count": discarded_partial_payload_count,
        "native_pre_snapshot_sha256": pre_snapshot_sha256,
        "native_post_snapshot_sha256": post_snapshot_sha256,
        "native_pre_process_id": pre_process_id,
        "native_post_process_id": post_process_id,
        "supervisor_child_process_identity_verified": (child_process_identity_verified),
        "native_pre_post_snapshot_equality_verified": (native_pre_post_snapshot_equality_verified),
        "native_mapping_lifetime_closure_claimed": evidence["native_mapping_lifetime_closure_claimed"],
        "disposition": (
            WORKER_EXECUTION_EVIDENCE_ACCEPTED if not rejection_reasons else WORKER_EXECUTION_EVIDENCE_REJECTED
        ),
        "rejection_reasons": rejection_reasons,
    }


def _result_receipt_binding(result_receipt: Mapping[str, Any]) -> dict[str, Any]:
    result_receipt = _validated_result_receipt_document(result_receipt)
    if result_receipt.get("schema_id") != REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_SCHEMA_ID:
        raise ReferenceMinimizationValidationResultReviewError("result receipt schema is unsupported")
    receipt_sha256 = _require_sha256(result_receipt.get("receipt_sha256"), name="result receipt")
    return {
        "result_receipt_sha256": receipt_sha256,
        "protocol_sha256": _require_sha256(result_receipt.get("protocol_sha256"), name="result receipt protocol"),
        "result_contract_sha256": _require_sha256(
            result_receipt.get("result_contract_sha256"),
            name="result receipt result contract",
        ),
        "result_writer_contract_sha256": _require_sha256(
            result_receipt.get("result_writer_contract_sha256"),
            name="result receipt result writer contract",
        ),
        "runner_contract_sha256": _require_sha256(
            result_receipt.get("runner_contract_sha256"),
            name="result receipt runner contract",
        ),
        "artifact_binding_sha256": _require_sha256(
            result_receipt.get("artifact_binding_sha256"),
            name="result receipt artifact binding",
        ),
        "authorization_contract_sha256": _require_sha256(
            result_receipt.get("authorization_contract_sha256"),
            name="result receipt authorization contract",
        ),
        "authorization_receipt_sha256": _require_sha256(
            result_receipt.get("authorization_receipt_sha256"),
            name="result receipt authorization receipt",
        ),
        "authorization_nonce_sha256": _require_sha256(
            result_receipt.get("authorization_nonce_sha256"),
            name="result receipt authorization nonce",
        ),
        "execution_environment_contract_sha256": _require_sha256(
            result_receipt.get("execution_environment_contract_sha256"),
            name="result receipt environment contract",
        ),
        "execution_environment_receipt_sha256": _require_sha256(
            result_receipt.get("execution_environment_receipt_sha256"),
            name="result receipt environment receipt",
        ),
        "environment_fingerprint_sha256": _require_sha256(
            result_receipt.get("environment_fingerprint_sha256"),
            name="result receipt environment fingerprint",
        ),
        "observation_sha256": _require_sha256(
            result_receipt.get("observation_sha256"),
            name="result receipt observation",
        ),
        "result_receipt_created_at_utc": _format_utc(
            _parse_utc(
                result_receipt.get("receipt_created_at_utc"),
                name="result receipt created_at_utc",
            ),
            name="result receipt created_at_utc",
        ),
        "code_commit_sha": result_receipt.get("code_commit_sha"),
        "runner_source_sha256": _require_sha256(
            result_receipt.get("runner_source_sha256"),
            name="result receipt runner source",
        ),
        "source_manifest_sha256": _require_sha256(
            result_receipt.get("source_manifest_sha256"),
            name="result receipt source manifest",
        ),
        "dependency_artifact_sha256_rows": _dependency_rows(result_receipt.get("dependency_artifact_sha256_rows")),
        "review_attestation_sha256": _require_sha256(
            result_receipt.get("review_attestation_sha256"),
            name="result receipt pre-execution review attestation",
        ),
        "independent_scientific_reviewer_identity_sha256": _require_sha256(
            result_receipt.get("independent_reviewer_identity_sha256"),
            name="result receipt independent scientific reviewer identity",
        ),
        "worker_execution_review": _worker_execution_review_from_result_receipt(result_receipt),
    }


def _external_sha256_set(values: Sequence[str], *, name: str) -> set[str]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise ReferenceMinimizationValidationResultReviewError(f"{name} must be an explicit sequence of SHA-256 values")
    return {_require_sha256(value, name=name) for value in values}


def _verify_upstream_role_chain(
    *,
    result_receipt: Mapping[str, Any],
    pre_execution_review_attestation: str | bytes | Mapping[str, Any],
    authorization_receipt: str | bytes | Mapping[str, Any],
    trusted_scientific_reviewer_keys: Mapping[str, MinimizationScientificReviewerTrustAnchor],
    trusted_authorization_operator_keys: Mapping[str, MinimizationAuthorizationOperatorTrustAnchor],
    expected_implementation_author_identity_sha256: str,
    expected_independent_scientific_reviewer_identity_sha256: str,
    expected_authorization_operator_identity_sha256: str,
    revoked_pre_execution_review_attestation_sha256s: Sequence[str],
    revoked_authorization_receipt_sha256s: Sequence[str],
) -> None:
    """Cryptographically reverify the signed upstream role chain at receipt time."""

    binding = _result_receipt_binding(result_receipt)
    expected_author = _require_sha256(
        expected_implementation_author_identity_sha256,
        name="expected implementation author identity",
    )
    expected_scientific_reviewer = _require_sha256(
        expected_independent_scientific_reviewer_identity_sha256,
        name="expected independent scientific reviewer identity",
    )
    expected_operator = _require_sha256(
        expected_authorization_operator_identity_sha256,
        name="expected authorization operator identity",
    )
    revoked_reviews = _external_sha256_set(
        revoked_pre_execution_review_attestation_sha256s,
        name="revoked pre-execution review attestation",
    )
    revoked_authorizations = _external_sha256_set(
        revoked_authorization_receipt_sha256s,
        name="revoked authorization receipt",
    )
    receipt_created_at = _parse_utc(
        binding["result_receipt_created_at_utc"],
        name="result receipt created_at_utc",
    )
    try:
        authorization = verify_signed_reference_minimization_validation_authorization_receipt(
            authorization_receipt,
            review_attestation=pre_execution_review_attestation,
            trusted_reviewer_keys=trusted_scientific_reviewer_keys,
            expected_implementation_author_identity_sha256=expected_author,
            trusted_operator_keys=trusted_authorization_operator_keys,
            checked_at=receipt_created_at,
            expected_code_commit_sha=binding["code_commit_sha"],
            expected_runner_source_sha256=binding["runner_source_sha256"],
            expected_dependency_artifact_sha256_rows={
                row["artifact_id"]: row["sha256"] for row in binding["dependency_artifact_sha256_rows"]
            },
            revoked_receipt_sha256s=tuple(sorted(revoked_authorizations)),
            revoked_review_attestation_sha256s=tuple(sorted(revoked_reviews)),
            consumed_nonce_sha256s=(),
        )
    except ReferenceMinimizationValidationAuthorizationError as exc:
        raise ReferenceMinimizationValidationResultReviewError(
            "result review upstream signed-chain verification failed"
        ) from exc
    expected_rows = {
        "receipt_sha256": binding["authorization_receipt_sha256"],
        "review_attestation_sha256": binding["review_attestation_sha256"],
        "implementation_author_identity_sha256": expected_author,
        "independent_reviewer_identity_sha256": expected_scientific_reviewer,
        "authorization_operator_identity_sha256": expected_operator,
        "authorization_nonce_sha256": binding["authorization_nonce_sha256"],
        "code_commit_sha": binding["code_commit_sha"],
        "runner_source_sha256": binding["runner_source_sha256"],
        "execution_environment_contract_sha256": binding["execution_environment_contract_sha256"],
        "result_receipt_contract_sha256": binding["result_contract_sha256"],
        "dependency_artifact_sha256_rows": tuple(
            (row["artifact_id"], row["sha256"]) for row in binding["dependency_artifact_sha256_rows"]
        ),
    }
    if any(
        getattr(authorization, field_name) != expected_value for field_name, expected_value in expected_rows.items()
    ):
        raise ReferenceMinimizationValidationResultReviewError(
            "result review upstream signed-chain roles or identities are cross-wired"
        )


def _contract_projection() -> dict[str, Any]:
    protocol = cpu_minimization_validation_protocol_document()
    materialization = cpu_minimization_validation_materialization_manifest_document()
    return {
        "schema_id": REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_CONTRACT_SCHEMA_ID,
        "contract_id": REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_CONTRACT_ID,
        "contract_version": REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_CONTRACT_VERSION,
        "frozen_at_utc": REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_CONTRACT_FROZEN_AT_UTC,
        "superseded_contract_sha256": (
            FROZEN_LEGACY_REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_CONTRACT_SHA256_V7
        ),
        "refreeze_reason": "binds_refrozen_minimization_protocol_and_authenticated_execution_chain",
        "purpose": {
            "scope": "future_independent_review_of_one_exact_minimization_validation_result_receipt",
            "contract_definition_only": True,
            "result_review_attestation_present": False,
            "authorizes_scientific_validation": False,
            "authorizes_parameter_fitting_proposal": False,
            "authorizes_parameter_fitting": False,
            "authorizes_product_claim": False,
        },
        "dependencies": {
            "protocol_sha256": FROZEN_CPU_MINIMIZATION_VALIDATION_PROTOCOL_SHA256,
            "artifact_binding_sha256": FROZEN_REFERENCE_MINIMIZATION_VALIDATION_ARTIFACT_BINDING_SHA256,
            "review_contract_sha256": FROZEN_REFERENCE_MINIMIZATION_VALIDATION_REVIEW_CONTRACT_SHA256,
            "authorization_contract_sha256": FROZEN_REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_CONTRACT_SHA256,
            "execution_environment_contract_sha256": FROZEN_REFERENCE_MINIMIZATION_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256,
            "result_receipt_contract_sha256": FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256,
            "result_writer_contract_sha256": FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_WRITER_CONTRACT_SHA256,
            "runner_contract_sha256": FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RUNNER_CONTRACT_SHA256,
            "trajectory_comparison_contract_sha256": FROZEN_REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COMPARISON_CONTRACT_SHA256,
            "fixture_manifest_sha256": protocol["fixture_manifest"]["fixture_manifest_sha256"],
            "case_manifest_sha256": protocol["case_manifest"]["case_manifest_sha256"],
            "materialization_manifest_sha256": materialization["materialization_manifest_sha256"],
            "exact_result_receipt_sha256_required": True,
            "full_result_writer_receipt_validation_required": True,
            "raw_signed_pre_execution_review_and_authorization_required": True,
            "upstream_ed25519_signatures_reverified_at_result_receipt_time": True,
            "exact_case_and_metric_dispositions_required": True,
            "exact_runtime_oracle_and_result_identities_required": True,
            "exact_nonnegative_counts_and_finite_energy_ledger_required": True,
            "case_iteration_and_backtrack_budgets_bound_accepted_counts": True,
            "rejected_counts_are_bound_to_accepted_case_progress": True,
            "line_search_failure_code_is_lane_and_evaluator_specific": True,
            "line_search_failure_requires_complete_final_backtrack_budget": True,
            "energy_ledger_and_retained_energy_metrics_must_be_consistent": True,
            "complete_operational_and_independent_coordinate_traces_required": True,
            "canonical_empty_trace_required_for_pre_evaluation_failure": True,
            "coordinate_trace_step_and_whole_trace_digests_recomputed": True,
            "coordinate_trace_counts_and_energy_ledger_must_be_consistent": True,
            "trajectory_comparison_recomputed_from_both_coordinate_traces": True,
            "trajectory_alignment_branch_rejection_and_counts_reverified": True,
            "trajectory_raw_evaluated_coordinate_and_energy_errors_reverified": True,
            "trajectory_predefined_threshold_dispositions_reverified": True,
            "checkpoint_uninterrupted_paused_and_resumed_digests_reverified": True,
            "worker_execution_evidence_extracted_from_validated_run_observation": True,
            "exact_worker_request_document_and_transport_bytes_reverified": True,
            "worker_request_nonce_start_code_source_dependency_environment_seed_and_materialization_crosschecked": True,
            "worker_completion_state_and_runtime_lifecycle_sha256_bound": True,
            "worker_retained_case_aggregate_recomputed_and_bound": True,
            "ordered_worker_case_frame_rows_and_case_digests_bound": True,
            "canonical_sixteen_frame_transcript_independently_reconstructed_and_rehashed": True,
            "canonical_transcript_length_count_and_frame_chain_bound": True,
            "supervisor_child_process_id_matches_native_lifecycle_endpoints": True,
            "independent_live_dependency_manifest_reverification_performed": False,
            "worker_process_starttime_and_boot_id_binding_established": False,
            "incomplete_partial_hash_length_prefix_suffix_and_discard_metadata_bound": True,
            "incomplete_raw_partial_independently_replayable": False,
            "native_pre_post_snapshot_equality_evidence_bound": True,
            "native_mapping_lifetime_closure_claim_remains_false": True,
            "dependency_claim_status_inherited": False,
        },
        "identity_policy": {
            "implementation_author_identity_sha256_required": True,
            "independent_scientific_reviewer_identity_sha256_required": True,
            "authorization_operator_identity_sha256_required": True,
            "independent_result_reviewer_identity_sha256_required": True,
            "all_four_identities_must_be_pairwise_distinct": True,
            "author_reviewer_and_operator_identities_derived_from_signed_upstream_chain": True,
            "result_reviewer_key_id_required": True,
            "trusted_result_reviewer_key_supplied_out_of_band": True,
            "verifier_trust_anchor_contains_public_key_only": True,
            "private_signing_key_remains_external_to_verifier": True,
            "repository_does_not_choose_or_bundle_trusted_result_reviewer_keys": True,
            "organizational_independence_requires_external_governance_review": True,
        },
        "attestation_schema": {
            "schema_id": REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_ATTESTATION_SCHEMA_ID,
            "signature_algorithm": REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_SIGNATURE_ALGORITHM,
            "maximum_validity_seconds": int(
                REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_MAX_VALIDITY.total_seconds()
            ),
            "result_review_must_not_predate_result_receipt": True,
            "required_review_check_ids": list(_REQUIRED_RESULT_REVIEW_CHECK_IDS),
            "required_limitation_ids": list(_REQUIRED_LIMITATION_IDS),
            "ordered_case_review_rows_required": 14,
            "all_required_checks_must_be_accepted": True,
            "all_limitations_must_be_acknowledged": True,
            "retained_metric_dispositions_required_for_all_cases": True,
            "missing_required_metric_dispositions_required": True,
            "retained_failure_dispositions_required_for_all_rejected_cases": True,
            "ordered_coordinate_trace_dispositions_required_for_all_cases": True,
            "ordered_coordinate_trace_step_dispositions_required": True,
            "expected_empty_coordinate_trace_disposition_is_explicit": True,
            "trajectory_comparison_disposition_required_for_all_cases": True,
            "trajectory_step_dispositions_required_for_all_aligned_steps": True,
            "checkpoint_restart_disposition_required_for_all_cases": True,
            "review_outcomes": [
                RESULT_REVIEW_OUTCOME_ACCEPTED,
                RESULT_REVIEW_OUTCOME_REJECTED,
            ],
            "review_outcome_derived_from_frozen_case_semantics": True,
            "accepted_outcome_requires_complete_result_evidence_disposition": True,
            "accepted_outcome_requires_all_trace_and_step_dispositions": True,
            "accepted_outcome_requires_trajectory_and_checkpoint_comparison_acceptance": True,
            "accepted_outcome_requires_complete_worker_lifecycle": True,
            "accepted_outcome_requires_exact_request_provenance_binding": True,
            "accepted_outcome_requires_reconstructed_canonical_transcript": True,
            "accepted_outcome_requires_supervisor_child_pid_match": True,
            "accepted_outcome_requires_fourteen_ordered_worker_payload_frames": True,
            "accepted_outcome_requires_zero_discarded_partial_payloads": True,
            "accepted_outcome_requires_matching_retained_case_aggregate": True,
            "accepted_outcome_requires_native_pre_post_snapshot_equality": True,
            "incomplete_worker_lifecycle_is_preservable_and_signable": True,
            "incomplete_worker_lifecycle_can_only_be_rejected": True,
            "verified_review_does_not_imply_result_acceptance": True,
            "external_revocation_rechecks_required_for_entire_receipt_chain": True,
            "all_external_lifecycle_inputs_are_required_verifier_arguments": True,
            "result_review_attestation_supersession_recheck_required": True,
            "canonical_json_bytes_required_for_text_or_byte_transport": True,
            "scientific_minimization_validation_recommendation_allowed": False,
            "parameter_fitting_recommendation_allowed": False,
            "superseded_or_revoked_attestation_allowed": False,
        },
        "case_review_template": _ordered_protocol_case_rows(),
        "authorization_gate": {
            "status": "closed",
            "independent_result_review_completed": False,
            "implementation_author_separation_attested": False,
            "scientifically_validated": False,
            "parameter_fitting_proposal_authorized": False,
            "parameter_fitting_authorized": False,
            "current_blockers": list(_CLOSED_GATE_BLOCKERS),
        },
        "claim_policy": {
            "result_review_contract_implemented": True,
            "trajectory_comparison_review_implemented": True,
            "independent_result_review_completed": False,
            "minimization_validated": False,
            "scientific_applicability_established": False,
            "scientifically_validated": False,
            "benchmark_validated": False,
            "product_qualified": False,
            "customer_execution_enabled": False,
            "claim_safe": False,
        },
        "blockers": list(_CLOSED_GATE_BLOCKERS),
    }


def reference_minimization_validation_result_review_contract_document() -> dict[str, Any]:
    document = _contract_projection()
    document["contract_sha256"] = _sha256(document)
    if (
        FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_CONTRACT_SHA256
        and document["contract_sha256"] != FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_CONTRACT_SHA256
    ):
        raise ReferenceMinimizationValidationResultReviewError(
            "frozen validation result review contract SHA-256 drifted"
        )
    return document


def require_reference_minimization_validation_result_review_contract_document(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ReferenceMinimizationValidationResultReviewError("result review contract document must be a mapping")
    try:
        observed = json.loads(_canonical_bytes(dict(payload)).decode("ascii"))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ReferenceMinimizationValidationResultReviewError("result review contract document is invalid") from exc
    expected = reference_minimization_validation_result_review_contract_document()
    if observed != expected:
        raise ReferenceMinimizationValidationResultReviewError(
            "result review contract document does not match the frozen record"
        )
    return observed


@dataclass(frozen=True, slots=True)
class MinimizationResultReviewerTrustAnchor:
    """Out-of-band result-reviewer identity and Ed25519 public key."""

    result_reviewer_identity_sha256: str
    verification_key: bytes = field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "result_reviewer_identity_sha256",
            _require_sha256(
                self.result_reviewer_identity_sha256,
                name="trusted result reviewer identity",
            ),
        )
        object.__setattr__(
            self,
            "verification_key",
            _require_key(
                self.verification_key,
                name="trusted result reviewer verification key",
            ),
        )


@dataclass(frozen=True, slots=True)
class ReferenceMinimizationValidationResultReviewVerification:
    contract_sha256: str
    result_receipt_sha256: str
    source_manifest_sha256: str
    attestation_sha256: str
    implementation_author_identity_sha256: str
    independent_scientific_reviewer_identity_sha256: str
    authorization_operator_identity_sha256: str
    independent_result_reviewer_identity_sha256: str
    result_reviewer_key_id: str
    reviewed_at_utc: str
    expires_at_utc: str
    independent_result_review_verified: bool
    implementation_author_separation_verified: bool
    result_receipt_review_outcome: str
    result_receipt_accepted: bool
    scientifically_validated: bool
    parameter_fitting_proposal_authorized: bool
    parameter_fitting_authorized: bool
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        for name, value in (
            ("result review contract", self.contract_sha256),
            ("result receipt", self.result_receipt_sha256),
            ("source manifest", self.source_manifest_sha256),
            ("result review attestation", self.attestation_sha256),
            ("implementation author", self.implementation_author_identity_sha256),
            (
                "independent scientific reviewer",
                self.independent_scientific_reviewer_identity_sha256,
            ),
            ("authorization operator", self.authorization_operator_identity_sha256),
            (
                "independent result reviewer",
                self.independent_result_reviewer_identity_sha256,
            ),
        ):
            _require_sha256(value, name=name)
        identities = {
            self.implementation_author_identity_sha256,
            self.independent_scientific_reviewer_identity_sha256,
            self.authorization_operator_identity_sha256,
            self.independent_result_reviewer_identity_sha256,
        }
        if len(identities) != 4:
            raise ReferenceMinimizationValidationResultReviewError(
                "result review verification identities must be pairwise distinct"
            )
        _require_key_id(self.result_reviewer_key_id)
        reviewed_at = _parse_utc(self.reviewed_at_utc, name="result review verification reviewed_at_utc")
        expires_at = _parse_utc(self.expires_at_utc, name="result review verification expires_at_utc")
        if expires_at <= reviewed_at:
            raise ReferenceMinimizationValidationResultReviewError(
                "result review verification expiry must follow review time"
            )
        if not self.independent_result_review_verified:
            raise ReferenceMinimizationValidationResultReviewError(
                "verified result review decision must retain review verification"
            )
        if not self.implementation_author_separation_verified:
            raise ReferenceMinimizationValidationResultReviewError(
                "verified result review decision must retain author separation"
            )
        if self.result_receipt_review_outcome not in {
            RESULT_REVIEW_OUTCOME_ACCEPTED,
            RESULT_REVIEW_OUTCOME_REJECTED,
        }:
            raise ReferenceMinimizationValidationResultReviewError("result review verification outcome is invalid")
        if self.result_receipt_accepted is not (self.result_receipt_review_outcome == RESULT_REVIEW_OUTCOME_ACCEPTED):
            raise ReferenceMinimizationValidationResultReviewError(
                "result review verification acceptance contradicts its outcome"
            )
        if (
            self.scientifically_validated
            or self.parameter_fitting_proposal_authorized
            or self.parameter_fitting_authorized
        ):
            raise ReferenceMinimizationValidationResultReviewError(
                "result review attestation alone cannot authorize validation or fitting"
            )
        if not self.blockers:
            raise ReferenceMinimizationValidationResultReviewError(
                "result review verification must retain downstream blockers"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_sha256": self.contract_sha256,
            "result_receipt_sha256": self.result_receipt_sha256,
            "source_manifest_sha256": self.source_manifest_sha256,
            "attestation_sha256": self.attestation_sha256,
            "implementation_author_identity_sha256": self.implementation_author_identity_sha256,
            "independent_scientific_reviewer_identity_sha256": self.independent_scientific_reviewer_identity_sha256,
            "authorization_operator_identity_sha256": self.authorization_operator_identity_sha256,
            "independent_result_reviewer_identity_sha256": self.independent_result_reviewer_identity_sha256,
            "result_reviewer_key_id": self.result_reviewer_key_id,
            "reviewed_at_utc": self.reviewed_at_utc,
            "expires_at_utc": self.expires_at_utc,
            "independent_result_review_verified": self.independent_result_review_verified,
            "implementation_author_separation_verified": self.implementation_author_separation_verified,
            "result_receipt_review_outcome": self.result_receipt_review_outcome,
            "result_receipt_accepted": self.result_receipt_accepted,
            "scientifically_validated": self.scientifically_validated,
            "parameter_fitting_proposal_authorized": self.parameter_fitting_proposal_authorized,
            "parameter_fitting_authorized": self.parameter_fitting_authorized,
            "blockers": list(self.blockers),
        }


def _attestation_projection(
    *,
    result_receipt: Mapping[str, Any],
    implementation_author_identity_sha256: str,
    independent_scientific_reviewer_identity_sha256: str,
    authorization_operator_identity_sha256: str,
    independent_result_reviewer_identity_sha256: str,
    result_reviewer_key_id: str,
    reviewed_at_utc: str,
    expires_at_utc: str,
    nonce_sha256: str,
    accepted_check_ids: Sequence[str],
    acknowledged_limitation_ids: Sequence[str],
    case_review_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    contract = reference_minimization_validation_result_review_contract_document()
    binding = _result_receipt_binding(result_receipt)
    author_identity = _require_sha256(
        implementation_author_identity_sha256,
        name="implementation author identity",
    )
    scientific_reviewer_identity = _require_sha256(
        independent_scientific_reviewer_identity_sha256,
        name="independent scientific reviewer identity",
    )
    if scientific_reviewer_identity != binding["independent_scientific_reviewer_identity_sha256"]:
        raise ReferenceMinimizationValidationResultReviewError(
            "independent scientific reviewer identity is cross-wired"
        )
    operator_identity = _require_sha256(
        authorization_operator_identity_sha256,
        name="authorization operator identity",
    )
    result_reviewer_identity = _require_sha256(
        independent_result_reviewer_identity_sha256,
        name="independent result reviewer identity",
    )
    if (
        len(
            {
                author_identity,
                scientific_reviewer_identity,
                operator_identity,
                result_reviewer_identity,
            }
        )
        != 4
    ):
        raise ReferenceMinimizationValidationResultReviewError("result review roles must be pairwise distinct")
    if list(accepted_check_ids) != list(_REQUIRED_RESULT_REVIEW_CHECK_IDS):
        raise ReferenceMinimizationValidationResultReviewError(
            "result review check coverage is incomplete or reordered"
        )
    if list(acknowledged_limitation_ids) != list(_REQUIRED_LIMITATION_IDS):
        raise ReferenceMinimizationValidationResultReviewError("result review limitations are incomplete or reordered")
    rows = [dict(row) for row in case_review_rows]
    review_outcome = _result_review_outcome(
        rows,
        binding["worker_execution_review"],
    )
    return {
        "schema_id": REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_ATTESTATION_SCHEMA_ID,
        "contract_sha256": contract["contract_sha256"],
        "result_receipt_sha256": binding["result_receipt_sha256"],
        "protocol_sha256": binding["protocol_sha256"],
        "result_contract_sha256": binding["result_contract_sha256"],
        "result_writer_contract_sha256": binding["result_writer_contract_sha256"],
        "runner_contract_sha256": binding["runner_contract_sha256"],
        "artifact_binding_sha256": binding["artifact_binding_sha256"],
        "authorization_contract_sha256": binding["authorization_contract_sha256"],
        "authorization_receipt_sha256": binding["authorization_receipt_sha256"],
        "authorization_nonce_sha256": binding["authorization_nonce_sha256"],
        "execution_environment_contract_sha256": binding["execution_environment_contract_sha256"],
        "execution_environment_receipt_sha256": binding["execution_environment_receipt_sha256"],
        "environment_fingerprint_sha256": binding["environment_fingerprint_sha256"],
        "observation_sha256": binding["observation_sha256"],
        "result_receipt_created_at_utc": binding["result_receipt_created_at_utc"],
        "code_commit_sha": binding["code_commit_sha"],
        "runner_source_sha256": binding["runner_source_sha256"],
        "source_manifest_sha256": binding["source_manifest_sha256"],
        "dependency_artifact_sha256_rows": binding["dependency_artifact_sha256_rows"],
        "review_attestation_sha256": binding["review_attestation_sha256"],
        "worker_execution_review": binding["worker_execution_review"],
        "implementation_author_identity_sha256": author_identity,
        "independent_scientific_reviewer_identity_sha256": scientific_reviewer_identity,
        "authorization_operator_identity_sha256": operator_identity,
        "independent_result_reviewer_identity_sha256": result_reviewer_identity,
        "result_reviewer_key_id": _require_key_id(result_reviewer_key_id),
        "reviewed_at_utc": reviewed_at_utc,
        "expires_at_utc": expires_at_utc,
        "nonce_sha256": _require_sha256(nonce_sha256, name="result review nonce"),
        "accepted_check_ids": list(accepted_check_ids),
        "acknowledged_limitation_ids": list(acknowledged_limitation_ids),
        "case_review_rows": rows,
        "result_receipt_review_outcome": review_outcome,
        "result_receipt_accepted": review_outcome == RESULT_REVIEW_OUTCOME_ACCEPTED,
        "scientific_minimization_validation_recommended": False,
        "parameter_fitting_proposal_recommended": False,
        "parameter_fitting_recommended": False,
        "scientifically_validated": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "claim_safe": False,
        "superseded": False,
        "revoked": False,
    }


def build_signed_reference_minimization_validation_result_review_attestation(
    *,
    result_receipt: Mapping[str, Any],
    pre_execution_review_attestation: str | bytes | Mapping[str, Any],
    authorization_receipt: str | bytes | Mapping[str, Any],
    trusted_scientific_reviewer_keys: Mapping[str, MinimizationScientificReviewerTrustAnchor],
    trusted_authorization_operator_keys: Mapping[str, MinimizationAuthorizationOperatorTrustAnchor],
    implementation_author_identity_sha256: str,
    independent_scientific_reviewer_identity_sha256: str,
    authorization_operator_identity_sha256: str,
    independent_result_reviewer_identity_sha256: str,
    result_reviewer_key_id: str,
    signing_key: bytes | str,
    reviewed_at: datetime,
    expires_at: datetime,
    nonce_sha256: str,
    revoked_pre_execution_review_attestation_sha256s: Sequence[str],
    revoked_authorization_receipt_sha256s: Sequence[str],
    revoked_execution_environment_receipt_sha256s: Sequence[str],
    revoked_result_receipt_sha256s: Sequence[str],
    superseded_result_receipt_sha256s: Sequence[str],
    accepted_check_ids: Sequence[str] = _REQUIRED_RESULT_REVIEW_CHECK_IDS,
    acknowledged_limitation_ids: Sequence[str] = _REQUIRED_LIMITATION_IDS,
    case_review_rows: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a signed external result-review artifact without storing the secret key."""

    validated_receipt = _validated_result_receipt_document(result_receipt)
    binding = _result_receipt_binding(validated_receipt)
    _verify_upstream_role_chain(
        result_receipt=validated_receipt,
        pre_execution_review_attestation=pre_execution_review_attestation,
        authorization_receipt=authorization_receipt,
        trusted_scientific_reviewer_keys=trusted_scientific_reviewer_keys,
        trusted_authorization_operator_keys=trusted_authorization_operator_keys,
        expected_implementation_author_identity_sha256=(implementation_author_identity_sha256),
        expected_independent_scientific_reviewer_identity_sha256=(independent_scientific_reviewer_identity_sha256),
        expected_authorization_operator_identity_sha256=(authorization_operator_identity_sha256),
        revoked_pre_execution_review_attestation_sha256s=(revoked_pre_execution_review_attestation_sha256s),
        revoked_authorization_receipt_sha256s=(revoked_authorization_receipt_sha256s),
    )
    revoked_environments = _external_sha256_set(
        revoked_execution_environment_receipt_sha256s,
        name="revoked execution environment receipt",
    )
    revoked_results = _external_sha256_set(
        revoked_result_receipt_sha256s,
        name="revoked result receipt",
    )
    superseded_results = _external_sha256_set(
        superseded_result_receipt_sha256s,
        name="superseded result receipt",
    )
    if binding["execution_environment_receipt_sha256"] in revoked_environments:
        raise ReferenceMinimizationValidationResultReviewError("execution environment receipt is externally revoked")
    if binding["result_receipt_sha256"] in revoked_results:
        raise ReferenceMinimizationValidationResultReviewError("result receipt is externally revoked")
    if binding["result_receipt_sha256"] in superseded_results:
        raise ReferenceMinimizationValidationResultReviewError("result receipt is externally superseded")
    expected_rows = _case_review_rows_from_result_receipt(validated_receipt)
    if case_review_rows is not None and [dict(row) for row in case_review_rows] != expected_rows:
        raise ReferenceMinimizationValidationResultReviewError(
            "caller-supplied case review dispositions contradict the result receipt"
        )
    reviewed_at_utc = _format_utc(reviewed_at, name="reviewed_at")
    expires_at_utc = _format_utc(expires_at, name="expires_at")
    reviewed_time = _parse_utc(reviewed_at_utc, name="reviewed_at")
    expires_time = _parse_utc(expires_at_utc, name="expires_at")
    if expires_time <= reviewed_time:
        raise ReferenceMinimizationValidationResultReviewError(
            "result review attestation expiry must follow review time"
        )
    if expires_time - reviewed_time > REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_MAX_VALIDITY:
        raise ReferenceMinimizationValidationResultReviewError(
            "result review attestation validity exceeds the frozen maximum"
        )
    receipt_created_at = _parse_utc(
        validated_receipt["receipt_created_at_utc"],
        name="result receipt created_at_utc",
    )
    if reviewed_time < receipt_created_at:
        raise ReferenceMinimizationValidationResultReviewError("result review attestation predates the result receipt")
    projection = _attestation_projection(
        result_receipt=validated_receipt,
        implementation_author_identity_sha256=implementation_author_identity_sha256,
        independent_scientific_reviewer_identity_sha256=(independent_scientific_reviewer_identity_sha256),
        authorization_operator_identity_sha256=authorization_operator_identity_sha256,
        independent_result_reviewer_identity_sha256=(independent_result_reviewer_identity_sha256),
        result_reviewer_key_id=result_reviewer_key_id,
        reviewed_at_utc=reviewed_at_utc,
        expires_at_utc=expires_at_utc,
        nonce_sha256=nonce_sha256,
        accepted_check_ids=accepted_check_ids,
        acknowledged_limitation_ids=acknowledged_limitation_ids,
        case_review_rows=expected_rows,
    )
    payload = dict(projection)
    payload["attestation_sha256"] = _sha256(projection)
    key = _require_key(signing_key, name="result review signing key")
    try:
        signature = sign_ed25519(_canonical_bytes(payload), key)
    except ReferenceMinimizationValidationEd25519Error as exc:
        raise ReferenceMinimizationValidationResultReviewError(
            "result review attestation Ed25519 signing failed"
        ) from exc
    payload["signature"] = {
        "algorithm": REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_SIGNATURE_ALGORITHM,
        "key_id": _require_key_id(result_reviewer_key_id),
        "value": signature,
    }
    return payload


def _load_attestation(source: str | bytes | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(source, Mapping):
        return dict(source)
    raw = source.encode("utf-8") if isinstance(source, str) else source
    if not isinstance(raw, bytes):
        raise ReferenceMinimizationValidationResultReviewError(
            "result review attestation must be a mapping, string, or bytes"
        )
    try:

        def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in pairs:
                if key in result:
                    raise ReferenceMinimizationValidationResultReviewError(
                        "result review attestation contains a duplicate JSON key"
                    )
                result[key] = value
            return result

        loaded = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReferenceMinimizationValidationResultReviewError("result review attestation must be UTF-8 JSON") from exc
    if not isinstance(loaded, dict):
        raise ReferenceMinimizationValidationResultReviewError("result review attestation root must be an object")
    if _canonical_bytes(loaded) != raw:
        raise ReferenceMinimizationValidationResultReviewError(
            "result review attestation transport is not canonical JSON"
        )
    return loaded


def verify_signed_reference_minimization_validation_result_review_attestation(
    source: str | bytes | Mapping[str, Any],
    *,
    result_receipt: Mapping[str, Any],
    pre_execution_review_attestation: str | bytes | Mapping[str, Any],
    authorization_receipt: str | bytes | Mapping[str, Any],
    trusted_scientific_reviewer_keys: Mapping[str, MinimizationScientificReviewerTrustAnchor],
    trusted_authorization_operator_keys: Mapping[str, MinimizationAuthorizationOperatorTrustAnchor],
    expected_result_receipt_sha256: str,
    trusted_result_reviewer_keys: Mapping[str, MinimizationResultReviewerTrustAnchor],
    expected_implementation_author_identity_sha256: str,
    expected_independent_scientific_reviewer_identity_sha256: str,
    expected_authorization_operator_identity_sha256: str,
    checked_at: datetime,
    revoked_pre_execution_review_attestation_sha256s: Sequence[str],
    revoked_authorization_receipt_sha256s: Sequence[str],
    revoked_execution_environment_receipt_sha256s: Sequence[str],
    revoked_result_receipt_sha256s: Sequence[str],
    superseded_result_receipt_sha256s: Sequence[str],
    revoked_result_review_attestation_sha256s: Sequence[str],
    superseded_result_review_attestation_sha256s: Sequence[str],
) -> ReferenceMinimizationValidationResultReviewVerification:
    """Verify exact receipt identity, role separation, signature, and freshness.

    A successful result-review verification still cannot authorize scientific
    validation, fitting, or a product claim.  A production result receipt and
    externally governed production review remain mandatory.
    """

    expected_receipt = _require_sha256(
        expected_result_receipt_sha256,
        name="expected result receipt",
    )
    expected_author = _require_sha256(
        expected_implementation_author_identity_sha256,
        name="expected implementation author identity",
    )
    expected_scientific_reviewer = _require_sha256(
        expected_independent_scientific_reviewer_identity_sha256,
        name="expected independent scientific reviewer identity",
    )
    expected_operator = _require_sha256(
        expected_authorization_operator_identity_sha256,
        name="expected authorization operator identity",
    )
    checked_at_utc = _parse_utc(_format_utc(checked_at, name="checked_at"), name="checked_at")
    validated_receipt = _validated_result_receipt_document(result_receipt)
    receipt_binding = _result_receipt_binding(validated_receipt)
    revoked_pre_execution_reviews = _external_sha256_set(
        revoked_pre_execution_review_attestation_sha256s,
        name="revoked pre-execution review attestation",
    )
    revoked_authorizations = _external_sha256_set(
        revoked_authorization_receipt_sha256s,
        name="revoked authorization receipt",
    )
    revoked_environments = _external_sha256_set(
        revoked_execution_environment_receipt_sha256s,
        name="revoked execution environment receipt",
    )
    revoked_results = _external_sha256_set(
        revoked_result_receipt_sha256s,
        name="revoked result receipt",
    )
    superseded_results = _external_sha256_set(
        superseded_result_receipt_sha256s,
        name="superseded result receipt",
    )
    revoked_result_reviews = _external_sha256_set(
        revoked_result_review_attestation_sha256s,
        name="revoked result review attestation",
    )
    superseded_result_reviews = _external_sha256_set(
        superseded_result_review_attestation_sha256s,
        name="superseded result review attestation",
    )
    if receipt_binding["result_receipt_sha256"] != expected_receipt:
        raise ReferenceMinimizationValidationResultReviewError("result receipt identity is cross-wired")
    if receipt_binding["protocol_sha256"] != FROZEN_CPU_MINIMIZATION_VALIDATION_PROTOCOL_SHA256:
        raise ReferenceMinimizationValidationResultReviewError("result receipt protocol identity drifted")
    if receipt_binding["artifact_binding_sha256"] != FROZEN_REFERENCE_MINIMIZATION_VALIDATION_ARTIFACT_BINDING_SHA256:
        raise ReferenceMinimizationValidationResultReviewError("result receipt artifact binding drifted")
    if (
        receipt_binding["authorization_contract_sha256"]
        != FROZEN_REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_CONTRACT_SHA256
    ):
        raise ReferenceMinimizationValidationResultReviewError("result receipt authorization contract drifted")
    if (
        receipt_binding["execution_environment_contract_sha256"]
        != FROZEN_REFERENCE_MINIMIZATION_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256
    ):
        raise ReferenceMinimizationValidationResultReviewError("result receipt environment contract drifted")
    if (
        receipt_binding["result_contract_sha256"]
        != FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256
    ):
        raise ReferenceMinimizationValidationResultReviewError("result receipt result contract drifted")
    if (
        receipt_binding["result_writer_contract_sha256"]
        != FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_WRITER_CONTRACT_SHA256
    ):
        raise ReferenceMinimizationValidationResultReviewError("result receipt result writer contract drifted")
    if receipt_binding["runner_contract_sha256"] != FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RUNNER_CONTRACT_SHA256:
        raise ReferenceMinimizationValidationResultReviewError("result receipt runner contract drifted")
    if receipt_binding["independent_scientific_reviewer_identity_sha256"] != expected_scientific_reviewer:
        raise ReferenceMinimizationValidationResultReviewError(
            "result receipt scientific reviewer identity is cross-wired"
        )
    if receipt_binding["review_attestation_sha256"] in revoked_pre_execution_reviews:
        raise ReferenceMinimizationValidationResultReviewError("pre-execution review attestation is externally revoked")
    if receipt_binding["authorization_receipt_sha256"] in revoked_authorizations:
        raise ReferenceMinimizationValidationResultReviewError("authorization receipt is externally revoked")
    if receipt_binding["execution_environment_receipt_sha256"] in revoked_environments:
        raise ReferenceMinimizationValidationResultReviewError("execution environment receipt is externally revoked")
    if expected_receipt in revoked_results:
        raise ReferenceMinimizationValidationResultReviewError("result receipt is externally revoked")
    if expected_receipt in superseded_results:
        raise ReferenceMinimizationValidationResultReviewError("result receipt is externally superseded")
    _verify_upstream_role_chain(
        result_receipt=validated_receipt,
        pre_execution_review_attestation=pre_execution_review_attestation,
        authorization_receipt=authorization_receipt,
        trusted_scientific_reviewer_keys=trusted_scientific_reviewer_keys,
        trusted_authorization_operator_keys=trusted_authorization_operator_keys,
        expected_implementation_author_identity_sha256=expected_author,
        expected_independent_scientific_reviewer_identity_sha256=(expected_scientific_reviewer),
        expected_authorization_operator_identity_sha256=expected_operator,
        revoked_pre_execution_review_attestation_sha256s=tuple(sorted(revoked_pre_execution_reviews)),
        revoked_authorization_receipt_sha256s=tuple(sorted(revoked_authorizations)),
    )
    expected_case_rows = _case_review_rows_from_result_receipt(validated_receipt)

    payload = _load_attestation(source)
    signature = payload.pop("signature", None)
    if not isinstance(signature, Mapping):
        raise ReferenceMinimizationValidationResultReviewError("result review attestation signature is missing")
    if set(signature) != {"algorithm", "key_id", "value"}:
        raise ReferenceMinimizationValidationResultReviewError("result review attestation signature fields are invalid")
    if signature.get("algorithm") != REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_SIGNATURE_ALGORITHM:
        raise ReferenceMinimizationValidationResultReviewError(
            "result review attestation signature algorithm is unsupported"
        )
    key_id = _require_key_id(signature.get("key_id"))
    if key_id not in trusted_result_reviewer_keys:
        raise ReferenceMinimizationValidationResultReviewError("result reviewer key id is not trusted")
    anchor = trusted_result_reviewer_keys[key_id]
    if not isinstance(anchor, MinimizationResultReviewerTrustAnchor):
        raise ReferenceMinimizationValidationResultReviewError("trusted result reviewer entry has an invalid type")
    signature_value = signature.get("value")
    try:
        verified = verify_ed25519(_canonical_bytes(payload), signature_value, anchor.verification_key)
    except ReferenceMinimizationValidationEd25519Error as exc:
        raise ReferenceMinimizationValidationResultReviewError(
            "result review attestation Ed25519 verifier is unavailable"
        ) from exc
    if not verified:
        raise ReferenceMinimizationValidationResultReviewError(
            "result review attestation signature verification failed"
        )

    attestation_sha256 = payload.pop("attestation_sha256", None)
    if attestation_sha256 != _sha256(payload):
        raise ReferenceMinimizationValidationResultReviewError("result review attestation SHA-256 verification failed")
    if attestation_sha256 in revoked_result_reviews:
        raise ReferenceMinimizationValidationResultReviewError("result review attestation is externally revoked")
    if attestation_sha256 in superseded_result_reviews:
        raise ReferenceMinimizationValidationResultReviewError("result review attestation is externally superseded")
    if payload.get("schema_id") != REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_ATTESTATION_SCHEMA_ID:
        raise ReferenceMinimizationValidationResultReviewError("result review attestation schema is unsupported")
    contract = reference_minimization_validation_result_review_contract_document()
    if payload.get("contract_sha256") != contract["contract_sha256"]:
        raise ReferenceMinimizationValidationResultReviewError("result review attestation contract identity drifted")
    if payload.get("result_receipt_sha256") != expected_receipt:
        raise ReferenceMinimizationValidationResultReviewError(
            "result review attestation result receipt identity drifted"
        )
    for field_name, expected_value in receipt_binding.items():
        if payload.get(field_name) != expected_value:
            raise ReferenceMinimizationValidationResultReviewError(
                "result review attestation result receipt binding drifted"
            )
    if payload.get("implementation_author_identity_sha256") != expected_author:
        raise ReferenceMinimizationValidationResultReviewError(
            "result review attestation implementation author identity drifted"
        )
    if payload.get("independent_scientific_reviewer_identity_sha256") != expected_scientific_reviewer:
        raise ReferenceMinimizationValidationResultReviewError(
            "result review attestation scientific reviewer identity drifted"
        )
    if payload.get("authorization_operator_identity_sha256") != expected_operator:
        raise ReferenceMinimizationValidationResultReviewError(
            "result review attestation authorization operator identity drifted"
        )
    result_reviewer = _require_sha256(
        payload.get("independent_result_reviewer_identity_sha256"),
        name="independent result reviewer identity",
    )
    if result_reviewer != anchor.result_reviewer_identity_sha256:
        raise ReferenceMinimizationValidationResultReviewError(
            "result reviewer identity does not match the trusted key"
        )
    identities = {
        expected_author,
        expected_scientific_reviewer,
        expected_operator,
        result_reviewer,
    }
    if len(identities) != 4:
        raise ReferenceMinimizationValidationResultReviewError("result review roles must be pairwise distinct")
    if payload.get("result_reviewer_key_id") != key_id:
        raise ReferenceMinimizationValidationResultReviewError("result reviewer key id is cross-wired")

    reviewed_at = _parse_utc(payload.get("reviewed_at_utc"), name="reviewed_at_utc")
    expires_at = _parse_utc(payload.get("expires_at_utc"), name="expires_at_utc")
    receipt_created_at = _parse_utc(
        receipt_binding["result_receipt_created_at_utc"],
        name="result receipt created_at_utc",
    )
    if reviewed_at < receipt_created_at:
        raise ReferenceMinimizationValidationResultReviewError("result review attestation predates the result receipt")
    if expires_at <= reviewed_at:
        raise ReferenceMinimizationValidationResultReviewError(
            "result review attestation expiry must follow review time"
        )
    if expires_at - reviewed_at > REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_MAX_VALIDITY:
        raise ReferenceMinimizationValidationResultReviewError(
            "result review attestation validity exceeds the frozen maximum"
        )
    if checked_at_utc < reviewed_at:
        raise ReferenceMinimizationValidationResultReviewError("result review attestation is not yet valid")
    if checked_at_utc >= expires_at:
        raise ReferenceMinimizationValidationResultReviewError("result review attestation is expired")

    expected_checks = list(_REQUIRED_RESULT_REVIEW_CHECK_IDS)
    expected_limitations = list(_REQUIRED_LIMITATION_IDS)
    if payload.get("accepted_check_ids") != expected_checks:
        raise ReferenceMinimizationValidationResultReviewError(
            "result review attestation check coverage is incomplete or reordered"
        )
    if payload.get("acknowledged_limitation_ids") != expected_limitations:
        raise ReferenceMinimizationValidationResultReviewError(
            "result review attestation limitations are incomplete or reordered"
        )
    if payload.get("case_review_rows") != expected_case_rows:
        raise ReferenceMinimizationValidationResultReviewError(
            "result review attestation case dispositions are incomplete, reordered, or contradictory"
        )
    expected_projection = _attestation_projection(
        result_receipt=validated_receipt,
        implementation_author_identity_sha256=expected_author,
        independent_scientific_reviewer_identity_sha256=expected_scientific_reviewer,
        authorization_operator_identity_sha256=expected_operator,
        independent_result_reviewer_identity_sha256=result_reviewer,
        result_reviewer_key_id=key_id,
        reviewed_at_utc=payload["reviewed_at_utc"],
        expires_at_utc=payload["expires_at_utc"],
        nonce_sha256=payload.get("nonce_sha256"),
        accepted_check_ids=expected_checks,
        acknowledged_limitation_ids=expected_limitations,
        case_review_rows=expected_case_rows,
    )
    if payload != expected_projection:
        raise ReferenceMinimizationValidationResultReviewError(
            "result review attestation fields do not match the frozen schema"
        )
    result_review_outcome = _result_review_outcome(
        expected_case_rows,
        receipt_binding["worker_execution_review"],
    )
    return ReferenceMinimizationValidationResultReviewVerification(
        contract_sha256=contract["contract_sha256"],
        result_receipt_sha256=expected_receipt,
        source_manifest_sha256=receipt_binding["source_manifest_sha256"],
        attestation_sha256=_require_sha256(attestation_sha256, name="result review attestation"),
        implementation_author_identity_sha256=expected_author,
        independent_scientific_reviewer_identity_sha256=expected_scientific_reviewer,
        authorization_operator_identity_sha256=expected_operator,
        independent_result_reviewer_identity_sha256=result_reviewer,
        result_reviewer_key_id=key_id,
        reviewed_at_utc=payload["reviewed_at_utc"],
        expires_at_utc=payload["expires_at_utc"],
        independent_result_review_verified=True,
        implementation_author_separation_verified=True,
        result_receipt_review_outcome=result_review_outcome,
        result_receipt_accepted=(result_review_outcome == RESULT_REVIEW_OUTCOME_ACCEPTED),
        scientifically_validated=False,
        parameter_fitting_proposal_authorized=False,
        parameter_fitting_authorized=False,
        blockers=(
            _POST_ATTESTATION_BLOCKERS
            if result_review_outcome == RESULT_REVIEW_OUTCOME_ACCEPTED
            else _REJECTED_RESULT_BLOCKERS
        ),
    )


def reference_minimization_validation_result_review_contract_decision() -> dict[str, Any]:
    """Return the current closed decision; no result review attestation is bundled."""

    contract = reference_minimization_validation_result_review_contract_document()
    return {
        "contract_sha256": contract["contract_sha256"],
        "result_review_attestation_present": False,
        "independent_result_review_verified": False,
        "implementation_author_separation_verified": False,
        "result_receipt_review_outcome": None,
        "result_receipt_accepted": False,
        "scientifically_validated": False,
        "parameter_fitting_proposal_authorized": False,
        "parameter_fitting_authorized": False,
        "blockers": list(_CLOSED_GATE_BLOCKERS),
    }


__all__ = [
    "COORDINATE_TRACE_ACCEPTED",
    "COORDINATE_TRACE_REJECTED",
    "COORDINATE_TRACE_STEP_ACCEPTED",
    "EXPECTED_EMPTY_COORDINATE_TRACE_ACCEPTED",
    "FROZEN_LEGACY_REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_CONTRACT_SHA256_V7",
    "FROZEN_LEGACY_REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_CONTRACT_SHA256_V6",
    "FROZEN_LEGACY_REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_CONTRACT_SHA256_V5",
    "FROZEN_LEGACY_REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_CONTRACT_SHA256_V4",
    "FROZEN_LEGACY_REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_CONTRACT_SHA256_V3",
    "FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_CONTRACT_SHA256",
    "REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_ATTESTATION_SCHEMA_ID",
    "REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_CONTRACT_ID",
    "REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_CONTRACT_SCHEMA_ID",
    "REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_CONTRACT_VERSION",
    "REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_MAX_VALIDITY",
    "REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_SIGNATURE_ALGORITHM",
    "EXPECTED_FAIL_CLOSED_OUTCOME_ACCEPTED",
    "EXPECTED_FAIL_CLOSED_OUTCOME_REJECTED",
    "PASS_CASE_OUTCOME_REJECTED",
    "REQUIRED_METRIC_VALUE_MISSING_REJECTED",
    "REQUIRED_RESULT_EVIDENCE_ACCEPTED",
    "REQUIRED_RESULT_EVIDENCE_REJECTED",
    "RETAINED_METRIC_VALUE_ACCEPTED",
    "RETAINED_METRIC_VALUE_REJECTED",
    "RESULT_REVIEW_OUTCOME_ACCEPTED",
    "RESULT_REVIEW_OUTCOME_REJECTED",
    "UNEXPECTED_METRIC_VALUE_REJECTED",
    "WORKER_EXECUTION_EVIDENCE_ACCEPTED",
    "WORKER_EXECUTION_EVIDENCE_REJECTED",
    "MinimizationResultReviewerTrustAnchor",
    "ReferenceMinimizationValidationResultReviewError",
    "ReferenceMinimizationValidationResultReviewVerification",
    "build_signed_reference_minimization_validation_result_review_attestation",
    "reference_minimization_validation_result_review_contract_decision",
    "reference_minimization_validation_result_review_contract_document",
    "require_reference_minimization_validation_result_review_contract_document",
    "verify_signed_reference_minimization_validation_result_review_attestation",
]
