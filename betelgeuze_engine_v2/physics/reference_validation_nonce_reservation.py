"""Atomic one-time nonce reservation for signed CPU validation authorization.

The primitive re-verifies the raw signed review and authorization artifacts,
then durably consumes the authorization nonce with a POSIX ``O_EXCL`` record.
It bundles no key, attestation, receipt, or reservation root and does not create
an environment receipt, run validation, write results, authorize fitting, or
promote any scientific, product, publication, or customer claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any, Mapping, Sequence

from .reference_validation_authorization import (
    FROZEN_REFERENCE_VALIDATION_AUTHORIZATION_CONTRACT_SHA256,
    AuthorizationOperatorTrustAnchor,
    ReferenceValidationAuthorizationError,
    ReferenceValidationAuthorizationVerification,
    reference_validation_authorization_contract_document,
    verify_signed_reference_validation_authorization_receipt,
)
from .reference_validation_receipts import (
    FROZEN_REFERENCE_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256,
    FROZEN_REFERENCE_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256,
    reference_validation_execution_environment_contract_document,
    reference_validation_result_receipt_contract_document,
)
from .reference_validation_review import ScientificReviewerTrustAnchor


REFERENCE_VALIDATION_NONCE_RESERVATION_CONTRACT_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_validation_nonce_reservation_contract/5.0.0"
)
REFERENCE_VALIDATION_NONCE_RESERVATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_validation_nonce_reservation/5.0.0"
)
REFERENCE_VALIDATION_NONCE_RESERVATION_CONTRACT_ID = (
    "cpu_reference_validation_atomic_nonce_reservation/5.0.0"
)
REFERENCE_VALIDATION_NONCE_RESERVATION_CONTRACT_VERSION = "5.0.0"
REFERENCE_VALIDATION_NONCE_RESERVATION_CONTRACT_FROZEN_AT_UTC = "2026-07-24T18:30:00Z"
REFERENCE_VALIDATION_NONCE_RESERVATION_MAX_RECORD_BYTES = 65_536

FROZEN_REFERENCE_VALIDATION_NONCE_RESERVATION_CONTRACT_SHA256 = (
    "a0d080e26092bfad909fe1c74b69d1182bcbf6d58b09a7f3cbe65f49be6b1d0e"
)
FROZEN_LEGACY_REFERENCE_VALIDATION_NONCE_RESERVATION_CONTRACT_SHA256_V4 = (
    "353de1c49c6b2a4c0423b3d84c5ef5ae7114b3166295391f0e3a5bd166441bf8"
)
FROZEN_LEGACY_REFERENCE_VALIDATION_NONCE_RESERVATION_CONTRACT_SHA256_V3 = (
    "d496c1593e072b30269a742d5f94ae920a6d205dd6613dbc39f1b259cda481c6"
)
FROZEN_LEGACY_REFERENCE_VALIDATION_NONCE_RESERVATION_CONTRACT_SHA256_V2 = (
    "1e9cc7d18b78f57a34f7399da0bd6f7a755658142dfd5c91b86e952b02e94f5f"
)
FROZEN_LEGACY_REFERENCE_VALIDATION_NONCE_RESERVATION_CONTRACT_SHA256_V1 = (
    "fcaa1c9fe02b8bbab83eb8a128f9188bc299e161af1371a6c3dd2b377f6246c1"
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_ARTIFACT_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,200}$")
_CURRENT_BLOCKERS = (
    "independent_scientific_review_missing",
    "signed_independent_scientific_review_attestation_missing",
    "trusted_independent_scientific_reviewer_key_not_provided",
    "implementation_author_and_independent_reviewer_separation_not_attested",
    "signed_execution_authorization_receipt_missing",
    "trusted_authorization_operator_key_not_provided",
    "authorization_nonce_not_atomically_reserved",
    "execution_environment_receipt_missing",
    "production_runner_start_missing",
    "production_result_receipt_missing",
    "validation_execution_not_authorized",
    "validation_results_not_collected",
    "parameter_fitting_not_authorized",
    "scientific_validation_missing",
    "product_integration_not_qualified",
)
_POST_RESERVATION_BLOCKERS = (
    "execution_environment_receipt_missing",
    "execution_environment_not_reverified_at_run_start",
    "production_runner_start_missing",
    "production_result_receipt_missing",
    "validation_execution_not_authorized",
    "validation_results_not_collected",
    "parameter_fitting_not_authorized",
    "scientific_validation_missing",
    "product_integration_not_qualified",
)


class ReferenceValidationNonceReservationError(ValueError):
    """The reservation contract, trust chain, root, or durable record is invalid."""


class ReferenceValidationNonceAlreadyReservedError(
    ReferenceValidationNonceReservationError
):
    """The one-time authorization nonce already has a reservation path."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    except (TypeError, ValueError, RecursionError) as exc:
        raise ReferenceValidationNonceReservationError(
            "nonce reservation artifact is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise ReferenceValidationNonceReservationError(
            f"{name} must be a lowercase SHA-256"
        )
    return value


def _require_git_commit(value: object) -> str:
    if not isinstance(value, str) or not _GIT_COMMIT_RE.fullmatch(value):
        raise ReferenceValidationNonceReservationError(
            "nonce reservation code commit must be a lowercase 40-character Git SHA"
        )
    return value


def _format_utc(value: datetime, *, name: str) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ReferenceValidationNonceReservationError(f"{name} must be timezone-aware")
    normalized = value.astimezone(timezone.utc)
    if normalized.microsecond:
        raise ReferenceValidationNonceReservationError(
            f"{name} must use second resolution"
        )
    return normalized.strftime("%Y-%m-%dT%H:%M:%SZ")


def _require_utc(value: object, *, name: str) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ReferenceValidationNonceReservationError(
            f"{name} must be second-resolution UTC"
        )
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise ReferenceValidationNonceReservationError(
            f"{name} must be second-resolution UTC"
        ) from exc
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_dependency_rows(
    rows: Mapping[str, str] | Sequence[Mapping[str, str]],
) -> tuple[tuple[str, str], ...]:
    normalized: list[tuple[str, str]] = []
    if isinstance(rows, Mapping):
        candidates = [
            {"artifact_id": artifact_id, "sha256": digest}
            for artifact_id, digest in rows.items()
        ]
    elif isinstance(rows, Sequence) and not isinstance(rows, (str, bytes)):
        candidates = list(rows)
    else:
        raise ReferenceValidationNonceReservationError(
            "nonce reservation dependency rows must be a mapping or sequence"
        )
    if not candidates:
        raise ReferenceValidationNonceReservationError(
            "nonce reservation dependency rows must be non-empty"
        )
    for row in candidates:
        if not isinstance(row, Mapping) or set(row) != {"artifact_id", "sha256"}:
            raise ReferenceValidationNonceReservationError(
                "nonce reservation dependency row fields are invalid"
            )
        artifact_id = row.get("artifact_id")
        if not isinstance(artifact_id, str) or not _ARTIFACT_ID_RE.fullmatch(
            artifact_id
        ):
            raise ReferenceValidationNonceReservationError(
                "nonce reservation dependency artifact id is invalid"
            )
        normalized.append(
            (
                artifact_id,
                _require_sha256(
                    row.get("sha256"),
                    name=f"nonce reservation dependency {artifact_id}",
                ),
            )
        )
    normalized.sort()
    if len({artifact_id for artifact_id, _ in normalized}) != len(normalized):
        raise ReferenceValidationNonceReservationError(
            "nonce reservation dependency artifact ids must be unique"
        )
    return tuple(normalized)


def _closed_claim_policy() -> dict[str, bool]:
    return {
        "atomic_nonce_reservation_primitive_implemented": True,
        "production_authorization_nonce_reserved": False,
        "validation_execution_authorized": False,
        "validation_results_collected": False,
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
    authorization = reference_validation_authorization_contract_document()
    environment = reference_validation_execution_environment_contract_document()
    result = reference_validation_result_receipt_contract_document()
    return {
        "schema_id": REFERENCE_VALIDATION_NONCE_RESERVATION_CONTRACT_SCHEMA_ID,
        "contract_id": REFERENCE_VALIDATION_NONCE_RESERVATION_CONTRACT_ID,
        "contract_version": REFERENCE_VALIDATION_NONCE_RESERVATION_CONTRACT_VERSION,
        "frozen_at_utc": (
            REFERENCE_VALIDATION_NONCE_RESERVATION_CONTRACT_FROZEN_AT_UTC
        ),
        "superseded_contract_sha256": (
            FROZEN_LEGACY_REFERENCE_VALIDATION_NONCE_RESERVATION_CONTRACT_SHA256_V4
        ),
        "legacy_contract_chain_sha256s": [
            FROZEN_LEGACY_REFERENCE_VALIDATION_NONCE_RESERVATION_CONTRACT_SHA256_V3,
            FROZEN_LEGACY_REFERENCE_VALIDATION_NONCE_RESERVATION_CONTRACT_SHA256_V2,
            FROZEN_LEGACY_REFERENCE_VALIDATION_NONCE_RESERVATION_CONTRACT_SHA256_V1,
        ],
        "refreeze_reason": (
            "bind_authorization_and_receipt_contracts_5_0_0_without_"
            "reservation_policy_change"
        ),
        "purpose": {
            "scope": "local_single_run_authorization_nonce_consumption",
            "raw_review_and_authorization_reverification_required": True,
            "contract_definition_and_primitive_only": True,
            "trusted_keys_or_receipts_bundled": False,
            "production_nonce_reservation_present": False,
            "validation_execution_authorized": False,
            "result_collection_performed": False,
        },
        "dependencies": {
            "authorization_contract_sha256": (
                FROZEN_REFERENCE_VALIDATION_AUTHORIZATION_CONTRACT_SHA256
            ),
            "observed_authorization_contract_sha256": authorization["contract_sha256"],
            "execution_environment_contract_sha256": (
                FROZEN_REFERENCE_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256
            ),
            "observed_execution_environment_contract_sha256": environment[
                "contract_sha256"
            ],
            "result_receipt_contract_sha256": (
                FROZEN_REFERENCE_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256
            ),
            "observed_result_receipt_contract_sha256": result["contract_sha256"],
            "exact_code_commit_required": True,
            "exact_runner_source_sha256_required": True,
            "exact_dependency_artifact_sha256_rows_required": True,
        },
        "reservation_root_policy": {
            "caller_provisioned_existing_absolute_directory_required": True,
            "posix_dir_fd_and_o_nofollow_required": True,
            "owner_must_equal_effective_uid": True,
            "directory_mode_required": "0700",
            "symlink_components_allowed": False,
            "network_or_remote_filesystem_supported": False,
            "filesystem_locality_is_not_established_by_this_primitive": True,
            "repository_bundles_no_reservation_root": True,
        },
        "atomicity_and_durability": {
            "reservation_filename": "<authorization_nonce_sha256>.json",
            "create_flags": ["O_CREAT", "O_EXCL", "O_NOFOLLOW", "O_CLOEXEC"],
            "record_mode_required": "0600",
            "record_owner_must_equal_effective_uid": True,
            "record_link_count_required": 1,
            "file_fsync_required": True,
            "directory_fsync_required": True,
            "duplicate_or_preexisting_path_fails_closed": True,
            "persistence_failure_leaves_nonce_path_consumed": True,
            "release_or_delete_api_provided": False,
            "same_uid_unlink_or_replacement_resistance_established": False,
            "privileged_reservation_service_required_before_customer_execution": True,
        },
        "record_schema": {
            "schema_id": REFERENCE_VALIDATION_NONCE_RESERVATION_SCHEMA_ID,
            "canonical_json_required": True,
            "duplicate_json_keys_allowed": False,
            "maximum_record_bytes": (
                REFERENCE_VALIDATION_NONCE_RESERVATION_MAX_RECORD_BYTES
            ),
            "record_sha256_required": True,
            "authorization_receipt_and_review_attestation_sha256_required": True,
            "authorization_operator_identity_sha256_required": True,
            "authorization_validity_window_required": True,
            "reserved_at_utc_required": True,
            "execution_environment_receipt_created": False,
            "validation_execution_authorized": False,
        },
        "current_state": {
            "atomic_nonce_reservation_primitive_implemented": True,
            "production_reservation_root_present": False,
            "review_attestation_present": False,
            "authorization_receipt_present": False,
            "authorization_nonce_reserved": False,
            "execution_environment_receipt_present": False,
            "run_start_dependencies_reverified": False,
            "validation_runner_implemented": True,
            "result_receipt_writer_implemented": True,
            "validation_execution_authorized": False,
            "validation_results_collected": False,
        },
        "claim_policy": _closed_claim_policy(),
        "blockers": list(_CURRENT_BLOCKERS),
    }


def reference_validation_nonce_reservation_contract_document() -> dict[str, Any]:
    document = _contract_projection()
    document["contract_sha256"] = _sha256(document)
    if document["contract_sha256"] != (
        FROZEN_REFERENCE_VALIDATION_NONCE_RESERVATION_CONTRACT_SHA256
    ):
        raise ReferenceValidationNonceReservationError(
            "frozen nonce reservation contract SHA-256 drifted"
        )
    return document


def require_reference_validation_nonce_reservation_contract_document(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ReferenceValidationNonceReservationError(
            "nonce reservation contract document must be a mapping"
        )
    try:
        observed = json.loads(_canonical_bytes(dict(payload)).decode("ascii"))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ReferenceValidationNonceReservationError(
            "nonce reservation contract document is invalid"
        ) from exc
    expected = reference_validation_nonce_reservation_contract_document()
    if _canonical_bytes(observed) != _canonical_bytes(expected):
        raise ReferenceValidationNonceReservationError(
            "nonce reservation contract document does not match the frozen record"
        )
    return observed


@dataclass(frozen=True, slots=True)
class ReferenceValidationNonceReservation:
    reservation_record_sha256: str
    authorization_receipt_sha256: str
    review_attestation_sha256: str
    authorization_operator_identity_sha256: str
    authorization_nonce_sha256: str
    code_commit_sha: str
    runner_source_sha256: str
    execution_environment_contract_sha256: str
    result_receipt_contract_sha256: str
    dependency_artifact_sha256_rows: tuple[tuple[str, str], ...]
    authorization_issued_at_utc: str
    authorization_expires_at_utc: str
    reserved_at_utc: str
    reservation_persisted: bool
    validation_execution_authorized: bool
    validation_results_collected: bool
    parameter_fitting_authorized: bool
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_sha256(self.reservation_record_sha256, name="reservation record")
        _require_sha256(
            self.authorization_receipt_sha256,
            name="reserved authorization receipt",
        )
        _require_sha256(
            self.review_attestation_sha256,
            name="reserved review attestation",
        )
        _require_sha256(
            self.authorization_operator_identity_sha256,
            name="reserved authorization operator identity",
        )
        _require_sha256(
            self.authorization_nonce_sha256,
            name="reserved authorization nonce",
        )
        _require_git_commit(self.code_commit_sha)
        _require_sha256(self.runner_source_sha256, name="reserved runner source")
        if self.execution_environment_contract_sha256 != (
            FROZEN_REFERENCE_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256
        ):
            raise ReferenceValidationNonceReservationError(
                "reserved execution environment contract identity drifted"
            )
        if self.result_receipt_contract_sha256 != (
            FROZEN_REFERENCE_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256
        ):
            raise ReferenceValidationNonceReservationError(
                "reserved result receipt contract identity drifted"
            )
        normalized_rows = _normalize_dependency_rows(
            [
                {"artifact_id": artifact_id, "sha256": digest}
                for artifact_id, digest in self.dependency_artifact_sha256_rows
            ]
        )
        if normalized_rows != self.dependency_artifact_sha256_rows:
            raise ReferenceValidationNonceReservationError(
                "reserved dependency rows must be canonical"
            )
        issued = _require_utc(
            self.authorization_issued_at_utc,
            name="reserved authorization issued_at_utc",
        )
        expires = _require_utc(
            self.authorization_expires_at_utc,
            name="reserved authorization expires_at_utc",
        )
        reserved = _require_utc(self.reserved_at_utc, name="reserved_at_utc")
        if not (issued <= reserved < expires):
            raise ReferenceValidationNonceReservationError(
                "nonce reservation must occur inside the authorization validity window"
            )
        if not self.reservation_persisted:
            raise ReferenceValidationNonceReservationError(
                "nonce reservation result must retain durable persistence"
            )
        if (
            self.validation_execution_authorized
            or self.validation_results_collected
            or self.parameter_fitting_authorized
        ):
            raise ReferenceValidationNonceReservationError(
                "nonce reservation alone cannot authorize execution, results, or fitting"
            )
        if self.blockers != _POST_RESERVATION_BLOCKERS:
            raise ReferenceValidationNonceReservationError(
                "nonce reservation must retain exact downstream blockers"
            )

    def projection(self) -> dict[str, Any]:
        return {
            "schema_id": REFERENCE_VALIDATION_NONCE_RESERVATION_SCHEMA_ID,
            "contract_sha256": (
                FROZEN_REFERENCE_VALIDATION_NONCE_RESERVATION_CONTRACT_SHA256
            ),
            "authorization_contract_sha256": (
                FROZEN_REFERENCE_VALIDATION_AUTHORIZATION_CONTRACT_SHA256
            ),
            "authorization_receipt_sha256": self.authorization_receipt_sha256,
            "review_attestation_sha256": self.review_attestation_sha256,
            "authorization_operator_identity_sha256": (
                self.authorization_operator_identity_sha256
            ),
            "authorization_nonce_sha256": self.authorization_nonce_sha256,
            "code_commit_sha": self.code_commit_sha,
            "runner_source_sha256": self.runner_source_sha256,
            "execution_environment_contract_sha256": (
                self.execution_environment_contract_sha256
            ),
            "result_receipt_contract_sha256": self.result_receipt_contract_sha256,
            "dependency_artifact_sha256_rows": [
                {"artifact_id": artifact_id, "sha256": digest}
                for artifact_id, digest in self.dependency_artifact_sha256_rows
            ],
            "authorization_issued_at_utc": self.authorization_issued_at_utc,
            "authorization_expires_at_utc": self.authorization_expires_at_utc,
            "reserved_at_utc": self.reserved_at_utc,
            "reservation_method": "posix_o_creat_o_excl_nofollow_fsync",
            "reservation_persisted": self.reservation_persisted,
            "execution_environment_receipt_present": False,
            "run_start_dependencies_reverified": False,
            "validation_execution_authorized": self.validation_execution_authorized,
            "validation_results_collected": self.validation_results_collected,
            "parameter_fitting_proposal_authorized": False,
            "parameter_fitting_authorized": self.parameter_fitting_authorized,
            "scientifically_validated": False,
            "claim_safe": False,
            "blockers": list(self.blockers),
        }

    def to_dict(self) -> dict[str, Any]:
        payload = self.projection()
        payload["reservation_record_sha256"] = self.reservation_record_sha256
        return payload


def _reservation_from_verified_authorization(
    verification: ReferenceValidationAuthorizationVerification,
    *,
    reserved_at_utc: str,
) -> ReferenceValidationNonceReservation:
    values = {
        "authorization_receipt_sha256": verification.receipt_sha256,
        "review_attestation_sha256": verification.review_attestation_sha256,
        "authorization_operator_identity_sha256": (
            verification.authorization_operator_identity_sha256
        ),
        "authorization_nonce_sha256": verification.authorization_nonce_sha256,
        "code_commit_sha": verification.code_commit_sha,
        "runner_source_sha256": verification.runner_source_sha256,
        "execution_environment_contract_sha256": (
            verification.execution_environment_contract_sha256
        ),
        "result_receipt_contract_sha256": (verification.result_receipt_contract_sha256),
        "dependency_artifact_sha256_rows": (
            verification.dependency_artifact_sha256_rows
        ),
        "authorization_issued_at_utc": verification.issued_at_utc,
        "authorization_expires_at_utc": verification.expires_at_utc,
        "reserved_at_utc": reserved_at_utc,
        "reservation_persisted": True,
        "validation_execution_authorized": False,
        "validation_results_collected": False,
        "parameter_fitting_authorized": False,
        "blockers": _POST_RESERVATION_BLOCKERS,
    }
    provisional = ReferenceValidationNonceReservation(
        reservation_record_sha256="0" * 64,
        **values,
    )
    return ReferenceValidationNonceReservation(
        reservation_record_sha256=_sha256(provisional.projection()),
        **values,
    )


def _secure_directory_flags() -> int:
    required = ("O_NOFOLLOW", "O_DIRECTORY", "O_CLOEXEC")
    if (
        os.name != "posix"
        or any(not hasattr(os, name) for name in required)
        or not hasattr(os, "geteuid")
        or os.open not in os.supports_dir_fd
    ):
        raise ReferenceValidationNonceReservationError(
            "secure POSIX nonce reservation is unavailable"
        )
    return os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY | os.O_CLOEXEC


def _reservation_root_components(root: str | os.PathLike[str]) -> tuple[str, ...]:
    try:
        candidate = Path(root)
    except (TypeError, ValueError) as exc:
        raise ReferenceValidationNonceReservationError(
            "nonce reservation root is invalid"
        ) from exc
    if not candidate.is_absolute() or ".." in candidate.parts:
        raise ReferenceValidationNonceReservationError(
            "nonce reservation root must be an absolute path without '..'"
        )
    if candidate.anchor != os.sep:
        raise ReferenceValidationNonceReservationError(
            "nonce reservation root has an unsupported filesystem anchor"
        )
    return tuple(part for part in candidate.parts[1:] if part not in {"", "."})


def _open_secure_reservation_root(root: str | os.PathLike[str]) -> int:
    components = _reservation_root_components(root)
    flags = _secure_directory_flags()
    try:
        current_fd = os.open(os.sep, flags)
    except (OSError, ValueError) as exc:
        raise ReferenceValidationNonceReservationError(
            "filesystem root cannot be opened securely"
        ) from exc
    try:
        for component in components:
            previous_fd = current_fd
            current_fd = -1
            try:
                current_fd = os.open(component, flags, dir_fd=previous_fd)
            except (OSError, ValueError) as exc:
                raise ReferenceValidationNonceReservationError(
                    "nonce reservation root is missing, inaccessible, or traverses a symlink"
                ) from exc
            finally:
                os.close(previous_fd)
        root_stat = os.fstat(current_fd)
        if not stat.S_ISDIR(root_stat.st_mode):
            raise ReferenceValidationNonceReservationError(
                "nonce reservation root must be a directory"
            )
        if root_stat.st_uid != os.geteuid():
            raise ReferenceValidationNonceReservationError(
                "nonce reservation root owner must match the effective uid"
            )
        if stat.S_IMODE(root_stat.st_mode) != 0o700:
            raise ReferenceValidationNonceReservationError(
                "nonce reservation root mode must be 0700"
            )
        result_fd = current_fd
        current_fd = -1
        return result_fd
    finally:
        if current_fd >= 0:
            os.close(current_fd)


def _validate_reservation_file_stat(file_stat: os.stat_result) -> None:
    if not stat.S_ISREG(file_stat.st_mode):
        raise ReferenceValidationNonceReservationError(
            "nonce reservation record must be a regular file"
        )
    if file_stat.st_uid != os.geteuid():
        raise ReferenceValidationNonceReservationError(
            "nonce reservation record owner must match the effective uid"
        )
    if stat.S_IMODE(file_stat.st_mode) != 0o600:
        raise ReferenceValidationNonceReservationError(
            "nonce reservation record mode must be 0600"
        )
    if file_stat.st_nlink != 1:
        raise ReferenceValidationNonceReservationError(
            "nonce reservation record link count must equal one"
        )


def _stable_reservation_file_identity(file_stat: os.stat_result) -> tuple[int, ...]:
    return (
        file_stat.st_dev,
        file_stat.st_ino,
        file_stat.st_mode,
        file_stat.st_uid,
        file_stat.st_gid,
        file_stat.st_nlink,
        file_stat.st_size,
        file_stat.st_mtime_ns,
        file_stat.st_ctime_ns,
    )


def _write_all(descriptor: int, payload: bytes) -> None:
    remaining = memoryview(payload)
    while remaining:
        written = os.write(descriptor, remaining)
        if written <= 0:
            raise OSError("nonce reservation write made no progress")
        remaining = remaining[written:]


def _persist_reservation(
    root_fd: int, reservation: ReferenceValidationNonceReservation
) -> None:
    filename = f"{reservation.authorization_nonce_sha256}.json"
    encoded = _canonical_bytes(reservation.to_dict()) + b"\n"
    if len(encoded) > REFERENCE_VALIDATION_NONCE_RESERVATION_MAX_RECORD_BYTES:
        raise ReferenceValidationNonceReservationError(
            "nonce reservation record exceeds the size limit"
        )
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
    try:
        descriptor = os.open(filename, flags, 0o600, dir_fd=root_fd)
    except FileExistsError as exc:
        raise ReferenceValidationNonceAlreadyReservedError(
            "authorization nonce is already reserved"
        ) from exc
    except (OSError, ValueError) as exc:
        raise ReferenceValidationNonceReservationError(
            "nonce reservation record cannot be created securely"
        ) from exc
    try:
        try:
            _validate_reservation_file_stat(os.fstat(descriptor))
            _write_all(descriptor, encoded)
            os.fsync(descriptor)
        except Exception as exc:
            raise ReferenceValidationNonceReservationError(
                "nonce reservation persistence failed; the nonce path remains consumed"
            ) from exc
    finally:
        os.close(descriptor)
    try:
        os.fsync(root_fd)
    except OSError as exc:
        raise ReferenceValidationNonceReservationError(
            "nonce reservation directory fsync failed; the nonce path remains consumed"
        ) from exc


def reserve_reference_validation_authorization_nonce(
    reservation_root: str | os.PathLike[str],
    *,
    authorization_receipt: str | bytes | Mapping[str, Any],
    review_attestation: str | bytes | Mapping[str, Any],
    trusted_reviewer_keys: Mapping[str, ScientificReviewerTrustAnchor],
    expected_implementation_author_identity_sha256: str,
    trusted_operator_keys: Mapping[str, AuthorizationOperatorTrustAnchor],
    reserved_at: datetime,
    expected_code_commit_sha: str,
    expected_runner_source_sha256: str,
    expected_dependency_artifact_sha256_rows: Mapping[str, str],
    revoked_receipt_sha256s: Sequence[str] = (),
    revoked_review_attestation_sha256s: Sequence[str] = (),
    externally_consumed_nonce_sha256s: Sequence[str] = (),
) -> ReferenceValidationNonceReservation:
    """Reverify raw signed artifacts and durably consume their one-time nonce."""

    reserved_at_utc = _format_utc(reserved_at, name="reserved_at")
    try:
        verification = verify_signed_reference_validation_authorization_receipt(
            authorization_receipt,
            review_attestation=review_attestation,
            trusted_reviewer_keys=trusted_reviewer_keys,
            expected_implementation_author_identity_sha256=(
                expected_implementation_author_identity_sha256
            ),
            trusted_operator_keys=trusted_operator_keys,
            checked_at=reserved_at,
            expected_code_commit_sha=expected_code_commit_sha,
            expected_runner_source_sha256=expected_runner_source_sha256,
            expected_execution_environment_contract_sha256=(
                FROZEN_REFERENCE_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256
            ),
            expected_result_receipt_contract_sha256=(
                FROZEN_REFERENCE_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256
            ),
            expected_dependency_artifact_sha256_rows=(
                expected_dependency_artifact_sha256_rows
            ),
            revoked_receipt_sha256s=revoked_receipt_sha256s,
            revoked_review_attestation_sha256s=(revoked_review_attestation_sha256s),
            consumed_nonce_sha256s=externally_consumed_nonce_sha256s,
        )
    except ReferenceValidationAuthorizationError as exc:
        raise ReferenceValidationNonceReservationError(
            "nonce reservation authorization verification failed"
        ) from exc
    if not verification.eligible_for_atomic_execution_reservation:
        raise ReferenceValidationNonceReservationError(
            "authorization receipt is not eligible for atomic nonce reservation"
        )
    reservation = _reservation_from_verified_authorization(
        verification,
        reserved_at_utc=reserved_at_utc,
    )
    root_fd = _open_secure_reservation_root(reservation_root)
    try:
        _persist_reservation(root_fd, reservation)
    finally:
        os.close(root_fd)
    return reservation


def _load_reservation_record(raw: bytes) -> dict[str, Any]:
    if not raw or len(raw) > REFERENCE_VALIDATION_NONCE_RESERVATION_MAX_RECORD_BYTES:
        raise ReferenceValidationNonceReservationError(
            "nonce reservation record size is invalid"
        )

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ReferenceValidationNonceReservationError(
                    "nonce reservation record contains a duplicate JSON key"
                )
            result[key] = value
        return result

    try:
        loaded = json.loads(
            raw.decode("ascii"),
            object_pairs_hook=reject_duplicate_keys,
        )
    except ReferenceValidationNonceReservationError:
        raise
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise ReferenceValidationNonceReservationError(
            "nonce reservation record must be canonical ASCII JSON"
        ) from exc
    if not isinstance(loaded, dict):
        raise ReferenceValidationNonceReservationError(
            "nonce reservation record root must be an object"
        )
    if raw != _canonical_bytes(loaded) + b"\n":
        raise ReferenceValidationNonceReservationError(
            "nonce reservation record bytes are not canonical"
        )
    return loaded


def _reservation_from_record(
    payload: Mapping[str, Any],
    *,
    expected_nonce_sha256: str,
) -> ReferenceValidationNonceReservation:
    expected_fields = {
        "schema_id",
        "contract_sha256",
        "authorization_contract_sha256",
        "authorization_receipt_sha256",
        "review_attestation_sha256",
        "authorization_operator_identity_sha256",
        "authorization_nonce_sha256",
        "code_commit_sha",
        "runner_source_sha256",
        "execution_environment_contract_sha256",
        "result_receipt_contract_sha256",
        "dependency_artifact_sha256_rows",
        "authorization_issued_at_utc",
        "authorization_expires_at_utc",
        "reserved_at_utc",
        "reservation_method",
        "reservation_persisted",
        "execution_environment_receipt_present",
        "run_start_dependencies_reverified",
        "validation_execution_authorized",
        "validation_results_collected",
        "parameter_fitting_proposal_authorized",
        "parameter_fitting_authorized",
        "scientifically_validated",
        "claim_safe",
        "blockers",
        "reservation_record_sha256",
    }
    if set(payload) != expected_fields:
        raise ReferenceValidationNonceReservationError(
            "nonce reservation record fields are invalid"
        )
    fixed_expectations = {
        "schema_id": REFERENCE_VALIDATION_NONCE_RESERVATION_SCHEMA_ID,
        "contract_sha256": (
            FROZEN_REFERENCE_VALIDATION_NONCE_RESERVATION_CONTRACT_SHA256
        ),
        "authorization_contract_sha256": (
            FROZEN_REFERENCE_VALIDATION_AUTHORIZATION_CONTRACT_SHA256
        ),
        "execution_environment_contract_sha256": (
            FROZEN_REFERENCE_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256
        ),
        "result_receipt_contract_sha256": (
            FROZEN_REFERENCE_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256
        ),
        "reservation_method": "posix_o_creat_o_excl_nofollow_fsync",
        "reservation_persisted": True,
        "execution_environment_receipt_present": False,
        "run_start_dependencies_reverified": False,
        "validation_execution_authorized": False,
        "validation_results_collected": False,
        "parameter_fitting_proposal_authorized": False,
        "parameter_fitting_authorized": False,
        "scientifically_validated": False,
        "claim_safe": False,
        "blockers": list(_POST_RESERVATION_BLOCKERS),
    }
    if any(
        _canonical_bytes(payload.get(key)) != _canonical_bytes(value)
        for key, value in fixed_expectations.items()
    ):
        raise ReferenceValidationNonceReservationError(
            "nonce reservation record fixed fields drifted"
        )
    nonce = _require_sha256(
        payload.get("authorization_nonce_sha256"),
        name="record authorization nonce",
    )
    if nonce != expected_nonce_sha256:
        raise ReferenceValidationNonceReservationError(
            "nonce reservation filename and record identity are cross-wired"
        )
    projection = dict(payload)
    record_sha256 = projection.pop("reservation_record_sha256")
    if record_sha256 != _sha256(projection):
        raise ReferenceValidationNonceReservationError(
            "nonce reservation record SHA-256 verification failed"
        )
    return ReferenceValidationNonceReservation(
        reservation_record_sha256=_require_sha256(
            record_sha256,
            name="reservation record",
        ),
        authorization_receipt_sha256=_require_sha256(
            payload.get("authorization_receipt_sha256"),
            name="record authorization receipt",
        ),
        review_attestation_sha256=_require_sha256(
            payload.get("review_attestation_sha256"),
            name="record review attestation",
        ),
        authorization_operator_identity_sha256=_require_sha256(
            payload.get("authorization_operator_identity_sha256"),
            name="record authorization operator",
        ),
        authorization_nonce_sha256=nonce,
        code_commit_sha=_require_git_commit(payload.get("code_commit_sha")),
        runner_source_sha256=_require_sha256(
            payload.get("runner_source_sha256"),
            name="record runner source",
        ),
        execution_environment_contract_sha256=payload[
            "execution_environment_contract_sha256"
        ],
        result_receipt_contract_sha256=payload["result_receipt_contract_sha256"],
        dependency_artifact_sha256_rows=_normalize_dependency_rows(
            payload["dependency_artifact_sha256_rows"]
        ),
        authorization_issued_at_utc=payload["authorization_issued_at_utc"],
        authorization_expires_at_utc=payload["authorization_expires_at_utc"],
        reserved_at_utc=payload["reserved_at_utc"],
        reservation_persisted=True,
        validation_execution_authorized=False,
        validation_results_collected=False,
        parameter_fitting_authorized=False,
        blockers=_POST_RESERVATION_BLOCKERS,
    )


def verify_reference_validation_nonce_reservation_record(
    source: bytes,
    *,
    expected_authorization_nonce_sha256: str,
) -> ReferenceValidationNonceReservation:
    """Verify exact canonical raw reservation bytes without reading a path."""

    if type(source) is not bytes:
        raise ReferenceValidationNonceReservationError(
            "raw nonce reservation record must be bytes"
        )
    nonce = _require_sha256(
        expected_authorization_nonce_sha256,
        name="expected authorization nonce",
    )
    return _reservation_from_record(
        _load_reservation_record(source),
        expected_nonce_sha256=nonce,
    )


def read_reference_validation_nonce_reservation(
    reservation_root: str | os.PathLike[str],
    authorization_nonce_sha256: str,
) -> ReferenceValidationNonceReservation:
    """Read and verify one durable reservation without opening any run gate."""

    nonce = _require_sha256(
        authorization_nonce_sha256,
        name="requested authorization nonce",
    )
    root_fd = _open_secure_reservation_root(reservation_root)
    try:
        flags = (
            os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | getattr(os, "O_NONBLOCK", 0)
        )
        try:
            descriptor = os.open(f"{nonce}.json", flags, dir_fd=root_fd)
        except (OSError, ValueError) as exc:
            raise ReferenceValidationNonceReservationError(
                "nonce reservation record is missing, inaccessible, or unsafe"
            ) from exc
        try:
            file_stat = os.fstat(descriptor)
            _validate_reservation_file_stat(file_stat)
            if not (
                0
                < file_stat.st_size
                <= REFERENCE_VALIDATION_NONCE_RESERVATION_MAX_RECORD_BYTES
            ):
                raise ReferenceValidationNonceReservationError(
                    "nonce reservation record size is invalid"
                )
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = os.read(descriptor, 8192)
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > REFERENCE_VALIDATION_NONCE_RESERVATION_MAX_RECORD_BYTES:
                    raise ReferenceValidationNonceReservationError(
                        "nonce reservation record exceeds the size limit"
                    )
            if _stable_reservation_file_identity(os.fstat(descriptor)) != (
                _stable_reservation_file_identity(file_stat)
            ):
                raise ReferenceValidationNonceReservationError(
                    "nonce reservation record changed while it was read"
                )
        finally:
            os.close(descriptor)
    finally:
        os.close(root_fd)
    return verify_reference_validation_nonce_reservation_record(
        b"".join(chunks),
        expected_authorization_nonce_sha256=nonce,
    )


def reference_validation_nonce_reservation_contract_decision() -> dict[str, Any]:
    contract = reference_validation_nonce_reservation_contract_document()
    return {
        "contract_sha256": contract["contract_sha256"],
        "atomic_nonce_reservation_primitive_implemented": True,
        "review_attestation_present": False,
        "authorization_receipt_present": False,
        "trusted_keys_present": False,
        "production_reservation_root_present": False,
        "authorization_nonce_reserved": False,
        "execution_environment_receipt_present": False,
        "run_start_dependencies_reverified": False,
        "validation_execution_authorized": False,
        "validation_results_collected": False,
        "parameter_fitting_proposal_authorized": False,
        "parameter_fitting_authorized": False,
        "blockers": list(_CURRENT_BLOCKERS),
    }


__all__ = [
    "FROZEN_LEGACY_REFERENCE_VALIDATION_NONCE_RESERVATION_CONTRACT_SHA256_V2",
    "FROZEN_REFERENCE_VALIDATION_NONCE_RESERVATION_CONTRACT_SHA256",
    "REFERENCE_VALIDATION_NONCE_RESERVATION_CONTRACT_ID",
    "REFERENCE_VALIDATION_NONCE_RESERVATION_CONTRACT_SCHEMA_ID",
    "REFERENCE_VALIDATION_NONCE_RESERVATION_CONTRACT_VERSION",
    "REFERENCE_VALIDATION_NONCE_RESERVATION_MAX_RECORD_BYTES",
    "REFERENCE_VALIDATION_NONCE_RESERVATION_SCHEMA_ID",
    "ReferenceValidationNonceAlreadyReservedError",
    "ReferenceValidationNonceReservation",
    "ReferenceValidationNonceReservationError",
    "read_reference_validation_nonce_reservation",
    "reference_validation_nonce_reservation_contract_decision",
    "reference_validation_nonce_reservation_contract_document",
    "require_reference_validation_nonce_reservation_contract_document",
    "reserve_reference_validation_authorization_nonce",
    "verify_reference_validation_nonce_reservation_record",
]
