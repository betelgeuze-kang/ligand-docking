"""Atomic failure-inclusive result-receipt writing and verification.

The writer finalizes one bounded runner observation only after re-verifying the
raw signed review and authorization, the live execution environment, and the
durable runner-start marker.  It writes one canonical private result receipt and
never drops a failed case or metric. Receipt creation is not an
independent result review and does not authorize fitting or promote claims.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
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
from .reference_minimization_validation_nonce_reservation import (
    ReferenceMinimizationValidationNonceReservationError,
    _open_secure_root,
    _validate_record_stat,
)
from .reference_minimization_validation_protocol import (
    FROZEN_CPU_MINIMIZATION_VALIDATION_PROTOCOL_SHA256,
)
from .reference_minimization_validation_receipts import (
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256,
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256,
    REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_SCHEMA_ID,
)
from .reference_minimization_validation_review import (
    MinimizationScientificReviewerTrustAnchor,
    ReferenceMinimizationValidationReviewError,
    verify_signed_reference_minimization_validation_review_attestation,
)
from .reference_minimization_validation_run_start import (
    ReferenceMinimizationValidationExecutionEnvironmentReceipt,
    ReferenceMinimizationValidationRunStartError,
    require_reference_minimization_validation_execution_environment_receipt_for_runner,
)
from .reference_minimization_validation_runner import (
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RUNNER_CONTRACT_SHA256,
    ReferenceMinimizationValidationRunObservation,
    ReferenceMinimizationValidationRunnerError,
    read_reference_minimization_validation_runner_start_record,
    require_reference_minimization_validation_run_observation_document,
)


REFERENCE_MINIMIZATION_VALIDATION_RESULT_WRITER_CONTRACT_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_validation_result_writer_contract/1.0.0"
)
REFERENCE_MINIMIZATION_VALIDATION_RESULT_WRITER_CONTRACT_ID = (
    "cpu_reference_minimization_validation_result_receipt_writer/1.0.0"
)
REFERENCE_MINIMIZATION_VALIDATION_RESULT_WRITER_CONTRACT_VERSION = "1.0.0"
REFERENCE_MINIMIZATION_VALIDATION_RESULT_WRITER_CONTRACT_FROZEN_AT_UTC = (
    "2026-07-18T06:40:00Z"
)
REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_MAX_BYTES = 8 * 1024 * 1024

FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_WRITER_CONTRACT_SHA256 = (
    "572f40b960db70e95bd327d69a35872eefb4b542fa94c37c190feec62eadeb0d"
)

_RECEIPT_BLOCKERS = (
    "independent_result_review_missing",
    "result_receipt_external_authenticity_not_established",
    "same_uid_artifact_replacement_resistance_not_established",
    "scientific_parameter_applicability_domain_missing",
    "scientific_holdout_manifest_missing",
    "parameter_fitting_not_authorized",
    "minimization_validation_protocol_missing",
    "scientific_validation_missing",
    "product_integration_not_qualified",
)
_CURRENT_BLOCKERS = (
    "independent_scientific_review_missing",
    "trusted_independent_scientific_reviewer_key_not_provided",
    "signed_execution_authorization_receipt_missing",
    "trusted_authorization_operator_key_not_provided",
    "authorization_nonce_not_atomically_reserved",
    "production_environment_receipt_missing",
    "production_runner_start_missing",
    "production_validation_result_receipt_missing",
    "independent_result_review_missing",
    "result_receipt_external_authenticity_not_established",
    "same_uid_artifact_replacement_resistance_not_established",
    "parameter_fitting_not_authorized",
    "scientific_validation_missing",
    "product_integration_not_qualified",
)


class ReferenceMinimizationValidationResultWriterError(RuntimeError):
    """Result finalization, persistence, or verification failed closed."""


class ReferenceMinimizationValidationResultReceiptAlreadyExistsError(
    ReferenceMinimizationValidationResultWriterError
):
    """The nonce-bound result-receipt path already exists."""


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
        raise ReferenceMinimizationValidationResultWriterError(
            "result receipt is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ReferenceMinimizationValidationResultWriterError(
            f"{name} must be a lowercase SHA-256"
        )
    return value


def _format_utc(value: datetime, *, name: str) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ReferenceMinimizationValidationResultWriterError(f"{name} must be timezone-aware")
    normalized = value.astimezone(timezone.utc)
    if normalized.microsecond:
        raise ReferenceMinimizationValidationResultWriterError(
            f"{name} must use second resolution"
        )
    return normalized.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_utc(value: object, *, name: str) -> datetime:
    if not isinstance(value, str):
        raise ReferenceMinimizationValidationResultWriterError(f"{name} must be UTC text")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise ReferenceMinimizationValidationResultWriterError(
            f"{name} must use second-resolution UTC"
        ) from exc


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _closed_claim_policy() -> dict[str, bool]:
    return {
        "result_receipt_writer_implemented": True,
        "production_result_receipt_present": False,
        "independent_result_review_complete": False,
        "force_or_energy_validated": False,
        "parameter_fitting_proposal_authorized": False,
        "parameter_fitting_authorized": False,
        "scientifically_validated": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
    }


def _contract_projection() -> dict[str, Any]:
    return {
        "schema_id": REFERENCE_MINIMIZATION_VALIDATION_RESULT_WRITER_CONTRACT_SCHEMA_ID,
        "contract_id": REFERENCE_MINIMIZATION_VALIDATION_RESULT_WRITER_CONTRACT_ID,
        "contract_version": REFERENCE_MINIMIZATION_VALIDATION_RESULT_WRITER_CONTRACT_VERSION,
        "frozen_at_utc": REFERENCE_MINIMIZATION_VALIDATION_RESULT_WRITER_CONTRACT_FROZEN_AT_UTC,
        "purpose": {
            "lane": "synthetic_implementation_mathematics_only",
            "failure_inclusive_result_receipt_writer_primitive": True,
            "production_result_receipt_bundled": False,
            "independent_result_review_performed": False,
        },
        "pre_finalize_reverification": {
            "raw_signed_review_required": True,
            "raw_signed_authorization_required": True,
            "external_trust_anchors_required": True,
            "external_revocation_inputs_required": True,
            "persisted_environment_receipt_and_live_process_required": True,
            "durable_runner_start_record_required": True,
            "exact_observation_identity_required": True,
        },
        "persistence": {
            "caller_owned_private_posix_root_required": True,
            "exclusive_no_follow_creation_required": True,
            "file_mode": "0600",
            "file_and_directory_fsync_required": True,
            "duplicate_path_fails_closed": True,
            "maximum_receipt_bytes": REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_MAX_BYTES,
            "release_or_delete_api_provided": False,
        },
        "verification": {
            "canonical_json_and_receipt_sha256_required": True,
            "out_of_band_expected_receipt_sha256_required": True,
            "external_revocation_and_supersession_inputs_required": True,
            "underlying_review_and_authorization_revocation_rechecked": True,
            "receipt_signature_implemented": False,
            "private_posix_storage_is_not_external_authenticity": True,
            "same_uid_replacement_resistance_established": False,
        },
        "coverage": {
            "case_count": 14,
            "failed_cases_and_metrics_retained": True,
            "partial_or_skipped_results_allowed": False,
            "result_review_state": "pending_independent_review",
        },
        "current_state": {
            "result_receipt_writer_implemented": True,
            "production_result_receipt_present": False,
            "production_validation_results_collected": False,
            "independent_result_review_complete": False,
        },
        "claim_policy": _closed_claim_policy(),
        "blockers": list(_CURRENT_BLOCKERS),
    }


def reference_minimization_validation_result_writer_contract_document() -> dict[str, Any]:
    document = _contract_projection()
    document["contract_sha256"] = _sha256(document)
    if document["contract_sha256"] != (
        FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_WRITER_CONTRACT_SHA256
    ):
        raise ReferenceMinimizationValidationResultWriterError(
            "frozen result writer contract SHA-256 drifted"
        )
    return document


def require_reference_minimization_validation_result_writer_contract_document(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ReferenceMinimizationValidationResultWriterError(
            "result writer contract document must be a mapping"
        )
    observed = json.loads(_canonical_bytes(dict(payload)).decode("ascii"))
    expected = reference_minimization_validation_result_writer_contract_document()
    if observed != expected:
        raise ReferenceMinimizationValidationResultWriterError(
            "result writer contract document does not match the frozen record"
        )
    return observed


@dataclass(frozen=True, slots=True)
class ReferenceMinimizationValidationResultReceipt:
    receipt_sha256: str
    canonical_document_bytes: bytes

    def __post_init__(self) -> None:
        _require_sha256(self.receipt_sha256, name="result receipt")
        if (
            not isinstance(self.canonical_document_bytes, bytes)
            or not self.canonical_document_bytes
            or len(self.canonical_document_bytes)
            > REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_MAX_BYTES
        ):
            raise ReferenceMinimizationValidationResultWriterError(
                "result receipt canonical document bytes are invalid"
            )
        try:
            payload = json.loads(self.canonical_document_bytes.decode("ascii"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ReferenceMinimizationValidationResultWriterError(
                "result receipt canonical document cannot be decoded"
            ) from exc
        if (
            not isinstance(payload, dict)
            or _canonical_bytes(payload) != self.canonical_document_bytes
            or payload.get("receipt_sha256") != self.receipt_sha256
        ):
            raise ReferenceMinimizationValidationResultWriterError(
                "result receipt canonical document identity is invalid"
            )
        _validate_result_receipt_payload(payload)

    @property
    def authorization_nonce_sha256(self) -> str:
        return self.to_dict()["authorization_nonce_sha256"]

    @property
    def observation_sha256(self) -> str:
        return self.to_dict()["observation_sha256"]

    @property
    def independent_result_review_state(self) -> str:
        return self.to_dict()["independent_result_review_state"]

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self.canonical_document_bytes.decode("ascii"))


def _result_projection(
    observation: ReferenceMinimizationValidationRunObservation,
    environment: ReferenceMinimizationValidationExecutionEnvironmentReceipt,
    *,
    authorization_receipt_sha256: str,
    review_attestation_sha256: str,
    independent_reviewer_identity_sha256: str,
    reviewed_at_utc: str,
    receipt_created_at_utc: str,
) -> dict[str, Any]:
    run_document = observation.to_dict()
    return {
        "schema_id": REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_SCHEMA_ID,
        "result_contract_sha256": (
            FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256
        ),
        "result_writer_contract_sha256": (
            FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_WRITER_CONTRACT_SHA256
        ),
        "runner_contract_sha256": (
            FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RUNNER_CONTRACT_SHA256
        ),
        "protocol_sha256": FROZEN_CPU_MINIMIZATION_VALIDATION_PROTOCOL_SHA256,
        "artifact_binding_sha256": (
            FROZEN_REFERENCE_MINIMIZATION_VALIDATION_ARTIFACT_BINDING_SHA256
        ),
        "authorization_contract_sha256": (
            FROZEN_REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_CONTRACT_SHA256
        ),
        "authorization_receipt_sha256": authorization_receipt_sha256,
        "authorization_nonce_sha256": observation.authorization_nonce_sha256,
        "execution_environment_contract_sha256": (
            FROZEN_REFERENCE_MINIMIZATION_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256
        ),
        "execution_environment_receipt_sha256": (
            observation.environment_receipt_sha256
        ),
        "environment_fingerprint_sha256": (
            observation.environment_fingerprint_sha256
        ),
        "runner_start_record_sha256": observation.runner_start_record_sha256,
        "observation_sha256": _sha256(run_document),
        "code_commit_sha": observation.code_commit_sha,
        "runner_source_sha256": observation.runner_source_sha256,
        "dependency_artifact_sha256_rows": run_document[
            "dependency_artifact_sha256_rows"
        ],
        "command_argv": run_document["command_argv"],
        "seed": observation.seed,
        "started_at_utc": observation.started_at_utc,
        "completed_at_utc": observation.completed_at_utc,
        "receipt_created_at_utc": receipt_created_at_utc,
        "case_results": run_document["case_results"],
        "coverage_summary": run_document["coverage_summary"],
        "run_observation": run_document,
        "artifact_path_confinement_verification": {
            "artifact_output_root_identity_sha256": (
                environment.artifact_output_root_identity_sha256
            ),
            "caller_owned_private_posix_root_verified": True,
            "receipt_file_mode": "0600",
            "path_disclosed": False,
            "same_uid_replacement_resistance_established": False,
        },
        "review_attestation_sha256": review_attestation_sha256,
        "independent_reviewer_identity_sha256": (
            independent_reviewer_identity_sha256
        ),
        "reviewed_at_utc": reviewed_at_utc,
        "review_scope": "implementation_and_artifact_review_pre_execution",
        "independent_result_review_state": "pending_independent_review",
        "supersession_state": {
            "state": "active_initial_receipt",
            "supersedes_receipt_sha256": None,
        },
        "revocation_state": {
            "checked_at_utc": receipt_created_at_utc,
            "review_attestation_revoked": False,
            "authorization_receipt_revoked": False,
            "result_receipt_revoked": False,
            "external_recheck_required_for_later_use": True,
        },
        "result_values_present": True,
        "result_receipt_written": True,
        "validation_results_collected": True,
        "production_validation_results_collected": False,
        "parameter_fitting_proposal_authorized": False,
        "parameter_fitting_authorized": False,
        "scientifically_validated": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
        "blockers": list(_RECEIPT_BLOCKERS),
    }


def _validate_result_receipt_payload(
    source: Mapping[str, Any],
) -> ReferenceMinimizationValidationRunObservation:
    payload = dict(source)
    observed_receipt = payload.pop("receipt_sha256", None)
    receipt = _require_sha256(observed_receipt, name="result receipt")
    if not hmac.compare_digest(receipt, _sha256(payload)):
        raise ReferenceMinimizationValidationResultWriterError(
            "result receipt SHA-256 verification failed"
        )
    expected_field_names = {
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
        "receipt_created_at_utc",
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
    }
    if set(payload) != expected_field_names:
        raise ReferenceMinimizationValidationResultWriterError(
            "result receipt fields are invalid"
        )
    try:
        observation = require_reference_minimization_validation_run_observation_document(
            payload["run_observation"]
        )
    except ReferenceMinimizationValidationRunnerError as exc:
        raise ReferenceMinimizationValidationResultWriterError(
            "result receipt run observation is invalid"
        ) from exc
    constant_rows = {
        "schema_id": REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_SCHEMA_ID,
        "result_contract_sha256": (
            FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256
        ),
        "result_writer_contract_sha256": (
            FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_WRITER_CONTRACT_SHA256
        ),
        "runner_contract_sha256": (
            FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RUNNER_CONTRACT_SHA256
        ),
        "protocol_sha256": FROZEN_CPU_MINIMIZATION_VALIDATION_PROTOCOL_SHA256,
        "artifact_binding_sha256": (
            FROZEN_REFERENCE_MINIMIZATION_VALIDATION_ARTIFACT_BINDING_SHA256
        ),
        "authorization_contract_sha256": (
            FROZEN_REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_CONTRACT_SHA256
        ),
        "execution_environment_contract_sha256": (
            FROZEN_REFERENCE_MINIMIZATION_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256
        ),
        "review_scope": "implementation_and_artifact_review_pre_execution",
        "independent_result_review_state": "pending_independent_review",
        "result_values_present": True,
        "result_receipt_written": True,
        "validation_results_collected": True,
        "production_validation_results_collected": False,
        "parameter_fitting_proposal_authorized": False,
        "parameter_fitting_authorized": False,
        "scientifically_validated": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
        "blockers": list(_RECEIPT_BLOCKERS),
    }
    if any(payload.get(name) != value for name, value in constant_rows.items()):
        raise ReferenceMinimizationValidationResultWriterError(
            "result receipt constants or claim boundary drifted"
        )
    run_document = observation.to_dict()
    mirrored = {
        "authorization_receipt_sha256": payload["authorization_receipt_sha256"],
        "authorization_nonce_sha256": observation.authorization_nonce_sha256,
        "execution_environment_receipt_sha256": (
            observation.environment_receipt_sha256
        ),
        "environment_fingerprint_sha256": (
            observation.environment_fingerprint_sha256
        ),
        "runner_start_record_sha256": observation.runner_start_record_sha256,
        "observation_sha256": _sha256(run_document),
        "code_commit_sha": observation.code_commit_sha,
        "runner_source_sha256": observation.runner_source_sha256,
        "dependency_artifact_sha256_rows": run_document[
            "dependency_artifact_sha256_rows"
        ],
        "command_argv": run_document["command_argv"],
        "seed": observation.seed,
        "started_at_utc": observation.started_at_utc,
        "completed_at_utc": observation.completed_at_utc,
        "case_results": run_document["case_results"],
        "coverage_summary": run_document["coverage_summary"],
    }
    if any(payload.get(name) != value for name, value in mirrored.items()):
        raise ReferenceMinimizationValidationResultWriterError(
            "result receipt and run observation are cross-wired"
        )
    for name in (
        "review_attestation_sha256",
        "independent_reviewer_identity_sha256",
    ):
        _require_sha256(payload.get(name), name=name.replace("_", " "))
    reviewed_at = _parse_utc(payload.get("reviewed_at_utc"), name="reviewed_at")
    completed_at = _parse_utc(
        payload.get("completed_at_utc"),
        name="completed_at",
    )
    created_at = _parse_utc(
        payload.get("receipt_created_at_utc"),
        name="receipt_created_at",
    )
    if reviewed_at > completed_at or created_at < completed_at:
        raise ReferenceMinimizationValidationResultWriterError(
            "result receipt lifecycle timestamps are invalid"
        )
    expected_supersession = {
        "state": "active_initial_receipt",
        "supersedes_receipt_sha256": None,
    }
    expected_revocation = {
        "checked_at_utc": payload["receipt_created_at_utc"],
        "review_attestation_revoked": False,
        "authorization_receipt_revoked": False,
        "result_receipt_revoked": False,
        "external_recheck_required_for_later_use": True,
    }
    confinement = payload.get("artifact_path_confinement_verification")
    if (
        payload.get("supersession_state") != expected_supersession
        or payload.get("revocation_state") != expected_revocation
        or not isinstance(confinement, Mapping)
        or set(confinement)
        != {
            "artifact_output_root_identity_sha256",
            "caller_owned_private_posix_root_verified",
            "receipt_file_mode",
            "path_disclosed",
            "same_uid_replacement_resistance_established",
        }
        or confinement.get("caller_owned_private_posix_root_verified") is not True
        or confinement.get("receipt_file_mode") != "0600"
        or confinement.get("path_disclosed") is not False
        or confinement.get("same_uid_replacement_resistance_established")
        is not False
    ):
        raise ReferenceMinimizationValidationResultWriterError(
            "result receipt lifecycle or path confinement state is invalid"
        )
    _require_sha256(
        confinement["artifact_output_root_identity_sha256"],
        name="result artifact output root identity",
    )
    return observation


def _receipt_from_payload(payload: Mapping[str, Any]) -> ReferenceMinimizationValidationResultReceipt:
    document = dict(payload)
    _validate_result_receipt_payload(document)
    return ReferenceMinimizationValidationResultReceipt(
        receipt_sha256=document["receipt_sha256"],
        canonical_document_bytes=_canonical_bytes(document),
    )


def _persist_result_receipt(
    artifact_output_root: str | os.PathLike[str],
    authorization_nonce_sha256: str,
    payload: Mapping[str, Any],
) -> None:
    encoded = _canonical_bytes(dict(payload)) + b"\n"
    if len(encoded) > REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_MAX_BYTES:
        raise ReferenceMinimizationValidationResultWriterError(
            "result receipt exceeds the size limit"
        )
    try:
        root_fd = _open_secure_root(artifact_output_root)
    except ReferenceMinimizationValidationNonceReservationError as exc:
        raise ReferenceMinimizationValidationResultWriterError(
            "result artifact root does not satisfy the private POSIX policy"
        ) from exc
    descriptor: int | None = None
    try:
        try:
            descriptor = os.open(
                f"{authorization_nonce_sha256}.result.json",
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | os.O_NOFOLLOW
                | os.O_CLOEXEC,
                0o600,
                dir_fd=root_fd,
            )
        except FileExistsError as exc:
            raise ReferenceMinimizationValidationResultReceiptAlreadyExistsError(
                "result receipt already exists for this nonce"
            ) from exc
        except (OSError, ValueError) as exc:
            raise ReferenceMinimizationValidationResultWriterError(
                "result receipt cannot be created securely"
            ) from exc
        try:
            _validate_record_stat(os.fstat(descriptor))
            remaining = memoryview(encoded)
            while remaining:
                written = os.write(descriptor, remaining)
                if written <= 0:
                    raise OSError("result receipt write made no progress")
                remaining = remaining[written:]
            os.fsync(descriptor)
        except Exception as exc:
            raise ReferenceMinimizationValidationResultWriterError(
                "result receipt persistence failed; the path remains consumed"
            ) from exc
        os.close(descriptor)
        descriptor = None
        try:
            os.fsync(root_fd)
        except OSError as exc:
            raise ReferenceMinimizationValidationResultWriterError(
                "result receipt durability failed; the path remains consumed"
            ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(root_fd)


def write_reference_minimization_validation_result_receipt(
    artifact_output_root: str | os.PathLike[str],
    authorization_nonce_sha256: str,
    observation: ReferenceMinimizationValidationRunObservation,
    *,
    review_attestation: str | bytes | Mapping[str, Any],
    authorization_receipt: str | bytes | Mapping[str, Any],
    trusted_reviewer_keys: Mapping[str, MinimizationScientificReviewerTrustAnchor],
    expected_implementation_author_identity_sha256: str,
    trusted_operator_keys: Mapping[str, MinimizationAuthorizationOperatorTrustAnchor],
    revoked_authorization_receipt_sha256s: Sequence[str],
    revoked_review_attestation_sha256s: Sequence[str],
    externally_conflicting_nonce_sha256s: Sequence[str],
) -> ReferenceMinimizationValidationResultReceipt:
    """Reverify one completed bounded run and atomically write its receipt."""

    if not isinstance(observation, ReferenceMinimizationValidationRunObservation):
        raise ReferenceMinimizationValidationResultWriterError(
            "result writer requires a bounded run observation"
        )
    try:
        observation = require_reference_minimization_validation_run_observation_document(
            observation.to_dict()
        )
    except ReferenceMinimizationValidationRunnerError as exc:
        raise ReferenceMinimizationValidationResultWriterError(
            "result writer run observation verification failed"
        ) from exc
    nonce = _require_sha256(
        authorization_nonce_sha256,
        name="result authorization nonce",
    )
    checked_at = _utc_now()
    try:
        review = verify_signed_reference_minimization_validation_review_attestation(
            review_attestation,
            trusted_reviewer_keys=trusted_reviewer_keys,
            expected_implementation_author_identity_sha256=(
                expected_implementation_author_identity_sha256
            ),
            checked_at=checked_at,
        )
        authorization = verify_signed_reference_minimization_validation_authorization_receipt(
            authorization_receipt,
            review_attestation=review_attestation,
            trusted_reviewer_keys=trusted_reviewer_keys,
            expected_implementation_author_identity_sha256=(
                expected_implementation_author_identity_sha256
            ),
            trusted_operator_keys=trusted_operator_keys,
            checked_at=checked_at,
            expected_code_commit_sha=observation.code_commit_sha,
            expected_runner_source_sha256=observation.runner_source_sha256,
            expected_execution_environment_contract_sha256=(
                FROZEN_REFERENCE_MINIMIZATION_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256
            ),
            expected_result_receipt_contract_sha256=(
                FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256
            ),
            expected_dependency_artifact_sha256_rows=dict(
                observation.dependency_artifact_sha256_rows
            ),
            revoked_receipt_sha256s=(
                revoked_authorization_receipt_sha256s
            ),
            revoked_review_attestation_sha256s=(
                revoked_review_attestation_sha256s
            ),
            consumed_nonce_sha256s=externally_conflicting_nonce_sha256s,
        )
    except (ReferenceMinimizationValidationReviewError, ReferenceMinimizationValidationAuthorizationError) as exc:
        raise ReferenceMinimizationValidationResultWriterError(
            "result writer signed-chain re-verification failed"
        ) from exc
    expected_authorization_rows = {
        "receipt_sha256": authorization.receipt_sha256,
        "review_attestation_sha256": review.attestation_sha256,
        "implementation_author_identity_sha256": (
            review.implementation_author_identity_sha256
        ),
        "independent_reviewer_identity_sha256": (
            review.independent_reviewer_identity_sha256
        ),
        "authorization_nonce_sha256": nonce,
        "code_commit_sha": observation.code_commit_sha,
        "runner_source_sha256": observation.runner_source_sha256,
        "dependency_artifact_sha256_rows": (
            observation.dependency_artifact_sha256_rows
        ),
    }
    if any(
        getattr(authorization, name) != value
        for name, value in expected_authorization_rows.items()
    ):
        raise ReferenceMinimizationValidationResultWriterError(
            "result writer authorization and observation are cross-wired"
        )
    try:
        environment = (
            require_reference_minimization_validation_execution_environment_receipt_for_runner(
                artifact_output_root,
                nonce,
                expected_receipt_sha256=(
                    observation.environment_receipt_sha256
                ),
            )
        )
    except ReferenceMinimizationValidationRunStartError as exc:
        raise ReferenceMinimizationValidationResultWriterError(
            "result writer environment re-verification failed"
        ) from exc
    expected_environment_rows = {
        "receipt_sha256": observation.environment_receipt_sha256,
        "authorization_receipt_sha256": authorization.receipt_sha256,
        "review_attestation_sha256": review.attestation_sha256,
        "implementation_author_identity_sha256": (
            review.implementation_author_identity_sha256
        ),
        "independent_reviewer_identity_sha256": (
            review.independent_reviewer_identity_sha256
        ),
        "authorization_operator_identity_sha256": (
            authorization.authorization_operator_identity_sha256
        ),
        "authorization_nonce_sha256": nonce,
        "code_commit_sha": observation.code_commit_sha,
        "runner_source_sha256": observation.runner_source_sha256,
        "dependency_artifact_sha256_rows": (
            observation.dependency_artifact_sha256_rows
        ),
        "environment_fingerprint_sha256": (
            observation.environment_fingerprint_sha256
        ),
    }
    if any(
        getattr(environment, name) != value
        for name, value in expected_environment_rows.items()
    ):
        raise ReferenceMinimizationValidationResultWriterError(
            "result writer environment and observation are cross-wired"
        )
    try:
        start_record = read_reference_minimization_validation_runner_start_record(
            artifact_output_root,
            nonce,
            expected_record_sha256=observation.runner_start_record_sha256,
            expected_environment_receipt_sha256=(
                observation.environment_receipt_sha256
            ),
            expected_runner_source_sha256=observation.runner_source_sha256,
        )
    except ReferenceMinimizationValidationRunnerError as exc:
        raise ReferenceMinimizationValidationResultWriterError(
            "result writer runner-start re-verification failed"
        ) from exc
    start_crosscheck = {
        "started_at_utc": observation.started_at_utc,
        "code_commit_sha": observation.code_commit_sha,
    }
    if any(start_record.get(name) != value for name, value in start_crosscheck.items()):
        raise ReferenceMinimizationValidationResultWriterError(
            "result writer runner-start record is cross-wired"
        )
    completed_at = _parse_utc(
        observation.completed_at_utc,
        name="observation completed_at",
    )
    if checked_at < completed_at:
        raise ReferenceMinimizationValidationResultWriterError(
            "result writer clock precedes the completed observation"
        )
    created_at_utc = _format_utc(checked_at, name="result receipt created_at")
    projection = _result_projection(
        observation,
        environment,
        authorization_receipt_sha256=authorization.receipt_sha256,
        review_attestation_sha256=review.attestation_sha256,
        independent_reviewer_identity_sha256=(
            review.independent_reviewer_identity_sha256
        ),
        reviewed_at_utc=review.reviewed_at_utc,
        receipt_created_at_utc=created_at_utc,
    )
    payload = dict(projection)
    payload["receipt_sha256"] = _sha256(projection)
    result = _receipt_from_payload(payload)
    _persist_result_receipt(
        artifact_output_root,
        nonce,
        result.to_dict(),
    )
    return result


def _read_result_receipt_bytes(
    artifact_output_root: str | os.PathLike[str],
    authorization_nonce_sha256: str,
) -> bytes:
    nonce = _require_sha256(
        authorization_nonce_sha256,
        name="result receipt authorization nonce",
    )
    try:
        root_fd = _open_secure_root(artifact_output_root)
    except ReferenceMinimizationValidationNonceReservationError as exc:
        raise ReferenceMinimizationValidationResultWriterError(
            "result artifact root does not satisfy the private POSIX policy"
        ) from exc
    descriptor: int | None = None
    try:
        try:
            descriptor = os.open(
                f"{nonce}.result.json",
                os.O_RDONLY
                | os.O_NONBLOCK
                | os.O_NOFOLLOW
                | os.O_CLOEXEC,
                dir_fd=root_fd,
            )
            _validate_record_stat(os.fstat(descriptor))
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = os.read(descriptor, 65_536)
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_MAX_BYTES:
                    raise ReferenceMinimizationValidationResultWriterError(
                        "result receipt exceeds the size limit"
                    )
        except (OSError, ValueError, ReferenceMinimizationValidationNonceReservationError) as exc:
            raise ReferenceMinimizationValidationResultWriterError(
                "result receipt cannot be read securely"
            ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(root_fd)
    return b"".join(chunks)


def read_reference_minimization_validation_result_receipt(
    artifact_output_root: str | os.PathLike[str],
    authorization_nonce_sha256: str,
) -> ReferenceMinimizationValidationResultReceipt:
    """Read one canonical private result receipt without accepting it."""

    nonce = _require_sha256(
        authorization_nonce_sha256,
        name="result receipt authorization nonce",
    )
    raw = _read_result_receipt_bytes(
        artifact_output_root,
        nonce,
    )

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ReferenceMinimizationValidationResultWriterError(
                    "result receipt contains a duplicate JSON key"
                )
            result[key] = value
        return result

    try:
        if not raw.endswith(b"\n"):
            raise ReferenceMinimizationValidationResultWriterError(
                "result receipt is not canonical JSON"
            )
        payload = json.loads(
            raw[:-1].decode("ascii"),
            object_pairs_hook=reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReferenceMinimizationValidationResultWriterError(
            "result receipt is not canonical JSON"
        ) from exc
    if not isinstance(payload, dict) or _canonical_bytes(payload) + b"\n" != raw:
        raise ReferenceMinimizationValidationResultWriterError(
            "result receipt is not canonical JSON"
        )
    receipt = _receipt_from_payload(payload)
    if not hmac.compare_digest(receipt.authorization_nonce_sha256, nonce):
        raise ReferenceMinimizationValidationResultWriterError(
            "result receipt authorization nonce is cross-wired"
        )
    return receipt


def verify_reference_minimization_validation_result_receipt(
    artifact_output_root: str | os.PathLike[str],
    authorization_nonce_sha256: str,
    *,
    expected_receipt_sha256: str,
    revoked_review_attestation_sha256s: Sequence[str],
    revoked_authorization_receipt_sha256s: Sequence[str],
    revoked_result_receipt_sha256s: Sequence[str],
    superseded_result_receipt_sha256s: Sequence[str],
) -> ReferenceMinimizationValidationResultReceipt:
    """Verify exact external identity plus current revocation/supersession state."""

    expected = _require_sha256(
        expected_receipt_sha256,
        name="expected result receipt",
    )
    receipt = read_reference_minimization_validation_result_receipt(
        artifact_output_root,
        authorization_nonce_sha256,
    )
    if not hmac.compare_digest(receipt.receipt_sha256, expected):
        raise ReferenceMinimizationValidationResultWriterError(
            "result receipt identity is cross-wired"
        )
    revoked_reviews = {
        _require_sha256(value, name="revoked review attestation")
        for value in revoked_review_attestation_sha256s
    }
    revoked_authorizations = {
        _require_sha256(value, name="revoked authorization receipt")
        for value in revoked_authorization_receipt_sha256s
    }
    revoked_results = {
        _require_sha256(value, name="revoked result receipt")
        for value in revoked_result_receipt_sha256s
    }
    superseded = {
        _require_sha256(value, name="superseded result receipt")
        for value in superseded_result_receipt_sha256s
    }
    payload = receipt.to_dict()
    if payload["review_attestation_sha256"] in revoked_reviews:
        raise ReferenceMinimizationValidationResultWriterError(
            "result receipt review attestation is externally revoked"
        )
    if payload["authorization_receipt_sha256"] in revoked_authorizations:
        raise ReferenceMinimizationValidationResultWriterError(
            "result receipt authorization is externally revoked"
        )
    if receipt.receipt_sha256 in revoked_results:
        raise ReferenceMinimizationValidationResultWriterError(
            "result receipt is externally revoked"
        )
    if receipt.receipt_sha256 in superseded:
        raise ReferenceMinimizationValidationResultWriterError(
            "result receipt is externally superseded"
        )
    return receipt


def reference_minimization_validation_result_writer_contract_decision() -> dict[str, Any]:
    contract = reference_minimization_validation_result_writer_contract_document()
    return {
        "contract_sha256": contract["contract_sha256"],
        "result_receipt_writer_implemented": True,
        "production_result_receipt_present": False,
        "production_validation_results_collected": False,
        "independent_result_review_complete": False,
        "parameter_fitting_authorized": False,
        "scientifically_validated": False,
        "claim_safe": False,
        "blockers": list(_CURRENT_BLOCKERS),
    }


__all__ = [
    "FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_WRITER_CONTRACT_SHA256",
    "REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_MAX_BYTES",
    "REFERENCE_MINIMIZATION_VALIDATION_RESULT_WRITER_CONTRACT_ID",
    "REFERENCE_MINIMIZATION_VALIDATION_RESULT_WRITER_CONTRACT_SCHEMA_ID",
    "REFERENCE_MINIMIZATION_VALIDATION_RESULT_WRITER_CONTRACT_VERSION",
    "ReferenceMinimizationValidationResultReceipt",
    "ReferenceMinimizationValidationResultReceiptAlreadyExistsError",
    "ReferenceMinimizationValidationResultWriterError",
    "read_reference_minimization_validation_result_receipt",
    "reference_minimization_validation_result_writer_contract_decision",
    "reference_minimization_validation_result_writer_contract_document",
    "require_reference_minimization_validation_result_writer_contract_document",
    "verify_reference_minimization_validation_result_receipt",
    "write_reference_minimization_validation_result_receipt",
]
