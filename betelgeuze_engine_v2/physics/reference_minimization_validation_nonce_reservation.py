"""Atomic one-time nonce reservation for minimization validation.

The primitive re-verifies raw signed review and authorization artifacts before
durably consuming one authorization nonce in a caller-provisioned private POSIX
directory.  It bundles no key, signed artifact, reservation root, environment
receipt, runner, result, fitting authority, or scientific/product claim.
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

from .reference_minimization_validation_authorization import (
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_CONTRACT_SHA256,
    MinimizationAuthorizationOperatorTrustAnchor,
    ReferenceMinimizationValidationAuthorizationError,
    ReferenceMinimizationValidationAuthorizationVerification,
    reference_minimization_validation_authorization_contract_document,
    verify_signed_reference_minimization_validation_authorization_receipt,
)
from .reference_minimization_validation_receipts import (
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256,
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256,
    reference_minimization_validation_execution_environment_contract_document,
    reference_minimization_validation_result_receipt_contract_document,
)
from .reference_minimization_validation_review import (
    MinimizationScientificReviewerTrustAnchor,
)


REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_CONTRACT_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_validation_nonce_reservation_contract/1.0.0"
)
REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_validation_nonce_reservation/1.0.0"
)
REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_CONTRACT_ID = (
    "cpu_reference_minimization_validation_atomic_nonce_reservation/1.0.0"
)
REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_CONTRACT_VERSION = "1.0.0"
REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_CONTRACT_FROZEN_AT_UTC = "2026-07-18T04:05:00Z"
REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_MAX_RECORD_BYTES = 65_536

FROZEN_REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_CONTRACT_SHA256 = (
    "f652946b1743dc23710a968388ec713d9083cd9ced4170cf91d472a3fd411831"
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
    "run_start_dependency_reverification_not_implemented",
    "validation_runner_not_implemented",
    "result_receipt_writer_not_implemented",
    "validation_execution_not_authorized",
    "minimization_validation_results_not_collected",
    "independent_result_review_missing",
    "parameter_fitting_not_authorized",
    "scientific_validation_missing",
    "product_integration_not_qualified",
)
_POST_RESERVATION_BLOCKERS = (
    "execution_environment_receipt_missing",
    "execution_environment_not_reverified_at_run_start",
    "run_start_dependency_reverification_not_implemented",
    "validation_runner_not_implemented",
    "result_receipt_writer_not_implemented",
    "validation_execution_not_authorized",
    "minimization_validation_results_not_collected",
    "independent_result_review_missing",
    "parameter_fitting_not_authorized",
    "scientific_validation_missing",
    "product_integration_not_qualified",
)


class ReferenceMinimizationValidationNonceReservationError(ValueError):
    """The reservation contract, trust chain, root, or record is invalid."""


class ReferenceMinimizationValidationNonceAlreadyReservedError(ReferenceMinimizationValidationNonceReservationError):
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
    except (TypeError, ValueError) as exc:
        raise ReferenceMinimizationValidationNonceReservationError(
            "minimization nonce reservation artifact is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise ReferenceMinimizationValidationNonceReservationError(f"{name} must be a lowercase SHA-256")
    return value


def _require_git_commit(value: object) -> str:
    if not isinstance(value, str) or not _GIT_COMMIT_RE.fullmatch(value):
        raise ReferenceMinimizationValidationNonceReservationError(
            "nonce reservation code commit must be a lowercase 40-character Git SHA"
        )
    return value


def _format_utc(value: datetime, *, name: str) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ReferenceMinimizationValidationNonceReservationError(f"{name} must be timezone-aware")
    normalized = value.astimezone(timezone.utc)
    if normalized.microsecond:
        raise ReferenceMinimizationValidationNonceReservationError(f"{name} must use second resolution")
    return normalized.strftime("%Y-%m-%dT%H:%M:%SZ")


def _require_utc(value: object, *, name: str) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ReferenceMinimizationValidationNonceReservationError(f"{name} must be second-resolution UTC")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ReferenceMinimizationValidationNonceReservationError(f"{name} must be second-resolution UTC") from exc
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_dependency_rows(
    rows: Mapping[str, str] | Sequence[Mapping[str, str]],
) -> tuple[tuple[str, str], ...]:
    if isinstance(rows, Mapping):
        candidates = [{"artifact_id": artifact_id, "sha256": digest} for artifact_id, digest in rows.items()]
    elif isinstance(rows, Sequence) and not isinstance(rows, (str, bytes)):
        candidates = list(rows)
    else:
        raise ReferenceMinimizationValidationNonceReservationError(
            "nonce reservation dependency rows must be a mapping or sequence"
        )
    if not candidates:
        raise ReferenceMinimizationValidationNonceReservationError(
            "nonce reservation dependency rows must not be empty"
        )
    normalized: list[tuple[str, str]] = []
    for row in candidates:
        if not isinstance(row, Mapping) or set(row) != {"artifact_id", "sha256"}:
            raise ReferenceMinimizationValidationNonceReservationError(
                "nonce reservation dependency row fields are invalid"
            )
        artifact_id = row.get("artifact_id")
        if not isinstance(artifact_id, str) or not _ARTIFACT_ID_RE.fullmatch(artifact_id):
            raise ReferenceMinimizationValidationNonceReservationError(
                "nonce reservation dependency artifact id is invalid"
            )
        normalized.append(
            (
                artifact_id,
                _require_sha256(row.get("sha256"), name=f"dependency {artifact_id}"),
            )
        )
    ordered = tuple(sorted(normalized))
    if len({artifact_id for artifact_id, _ in ordered}) != len(ordered):
        raise ReferenceMinimizationValidationNonceReservationError(
            "nonce reservation dependency artifact ids must be unique"
        )
    return ordered


def _contract_projection() -> dict[str, Any]:
    authorization = reference_minimization_validation_authorization_contract_document()
    environment = reference_minimization_validation_execution_environment_contract_document()
    result = reference_minimization_validation_result_receipt_contract_document()
    return {
        "schema_id": REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_CONTRACT_SCHEMA_ID,
        "contract_id": REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_CONTRACT_ID,
        "contract_version": REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_CONTRACT_VERSION,
        "frozen_at_utc": REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_CONTRACT_FROZEN_AT_UTC,
        "purpose": {
            "scope": "local_atomic_one_time_minimization_validation_authorization_nonce_reservation",
            "primitive_definition_only": True,
            "reservation_root_bundled": False,
            "authorization_nonce_reserved": False,
            "validation_execution_authorized": False,
        },
        "dependencies": {
            "authorization_contract_sha256": FROZEN_REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_CONTRACT_SHA256,
            "observed_authorization_contract_sha256": authorization["contract_sha256"],
            "execution_environment_contract_sha256": FROZEN_REFERENCE_MINIMIZATION_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256,
            "observed_execution_environment_contract_sha256": environment["contract_sha256"],
            "result_receipt_contract_sha256": FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256,
            "observed_result_receipt_contract_sha256": result["contract_sha256"],
            "raw_signed_review_reverification_required": True,
            "raw_signed_authorization_reverification_required": True,
            "external_revocation_and_consumed_nonce_inputs_required": True,
        },
        "storage_contract": {
            "platform": "posix_local_filesystem",
            "caller_provisioned_absolute_root_required": True,
            "root_owner_must_match_effective_uid": True,
            "root_mode": "0700",
            "symlink_traversal_allowed": False,
            "record_filename": "<authorization_nonce_sha256>.json",
            "record_mode": "0600",
            "record_link_count": 1,
            "record_creation_flags": [
                "O_CREAT",
                "O_EXCL",
                "O_NOFOLLOW",
                "O_CLOEXEC",
            ],
            "maximum_record_bytes": REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_MAX_RECORD_BYTES,
            "canonical_ascii_json_with_single_trailing_lf": True,
            "file_fsync_required": True,
            "directory_fsync_required": True,
            "duplicate_nonce_fails_closed": True,
            "release_or_delete_api_present": False,
        },
        "record_contract": {
            "schema_id": REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_SCHEMA_ID,
            "authorization_and_review_receipt_sha256_required": True,
            "operator_and_nonce_identity_required": True,
            "code_runner_environment_result_dependency_identities_required": True,
            "authorization_validity_window_required": True,
            "reservation_timestamp_must_be_inside_validity_window": True,
            "record_sha256_required": True,
            "environment_receipt_present": False,
            "run_start_dependencies_reverified": False,
            "validation_execution_authorized": False,
        },
        "current_state": {
            "atomic_nonce_reservation_primitive_implemented": True,
            "production_reservation_root_present": False,
            "production_nonce_reserved": False,
            "validation_execution_authorized": False,
            "validation_results_collected": False,
        },
        "claim_policy": {
            "authorization_nonce_reservation_implemented": True,
            "validation_execution_authorized": False,
            "validation_results_collected": False,
            "minimization_validated": False,
            "parameter_fitting_authorized": False,
            "scientifically_validated": False,
            "benchmark_validated": False,
            "product_qualified": False,
            "customer_execution_enabled": False,
            "claim_safe": False,
        },
        "blockers": list(_CURRENT_BLOCKERS),
    }


def reference_minimization_validation_nonce_reservation_contract_document() -> dict[str, Any]:
    """Return the frozen contract; no root or reservation is bundled."""

    document = _contract_projection()
    document["contract_sha256"] = _sha256(document)
    if document["contract_sha256"] != (FROZEN_REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_CONTRACT_SHA256):
        raise ReferenceMinimizationValidationNonceReservationError(
            "frozen minimization nonce reservation contract SHA-256 drifted"
        )
    return document


def require_reference_minimization_validation_nonce_reservation_contract_document(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ReferenceMinimizationValidationNonceReservationError(
            "nonce reservation contract document must be a mapping"
        )
    observed = json.loads(_canonical_bytes(dict(payload)).decode("ascii"))
    expected = reference_minimization_validation_nonce_reservation_contract_document()
    if observed != expected:
        raise ReferenceMinimizationValidationNonceReservationError(
            "nonce reservation contract does not match the frozen record"
        )
    return observed


@dataclass(frozen=True, slots=True)
class ReferenceMinimizationValidationNonceReservation:
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
        for name, value in (
            ("reservation record", self.reservation_record_sha256),
            ("authorization receipt", self.authorization_receipt_sha256),
            ("review attestation", self.review_attestation_sha256),
            ("authorization operator", self.authorization_operator_identity_sha256),
            ("authorization nonce", self.authorization_nonce_sha256),
            ("runner source", self.runner_source_sha256),
            ("environment contract", self.execution_environment_contract_sha256),
            ("result contract", self.result_receipt_contract_sha256),
        ):
            _require_sha256(value, name=name)
        _require_git_commit(self.code_commit_sha)
        if self.execution_environment_contract_sha256 != (
            FROZEN_REFERENCE_MINIMIZATION_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256
        ) or self.result_receipt_contract_sha256 != (
            FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256
        ):
            raise ReferenceMinimizationValidationNonceReservationError("reserved receipt contract identities drifted")
        normalized_rows = _normalize_dependency_rows(
            [
                {"artifact_id": artifact_id, "sha256": digest}
                for artifact_id, digest in self.dependency_artifact_sha256_rows
            ]
        )
        if normalized_rows != self.dependency_artifact_sha256_rows:
            raise ReferenceMinimizationValidationNonceReservationError("reserved dependency rows must be canonical")
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
            raise ReferenceMinimizationValidationNonceReservationError(
                "nonce reservation must occur inside the authorization validity window"
            )
        if not self.reservation_persisted:
            raise ReferenceMinimizationValidationNonceReservationError(
                "nonce reservation result must retain durable persistence"
            )
        if (
            self.validation_execution_authorized
            or self.validation_results_collected
            or self.parameter_fitting_authorized
        ):
            raise ReferenceMinimizationValidationNonceReservationError(
                "nonce reservation alone cannot authorize execution, results, or fitting"
            )
        if self.blockers != _POST_RESERVATION_BLOCKERS:
            raise ReferenceMinimizationValidationNonceReservationError(
                "nonce reservation must retain exact downstream blockers"
            )

    def projection(self) -> dict[str, Any]:
        return {
            "schema_id": REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_SCHEMA_ID,
            "contract_sha256": FROZEN_REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_CONTRACT_SHA256,
            "authorization_contract_sha256": FROZEN_REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_CONTRACT_SHA256,
            "authorization_receipt_sha256": self.authorization_receipt_sha256,
            "review_attestation_sha256": self.review_attestation_sha256,
            "authorization_operator_identity_sha256": self.authorization_operator_identity_sha256,
            "authorization_nonce_sha256": self.authorization_nonce_sha256,
            "code_commit_sha": self.code_commit_sha,
            "runner_source_sha256": self.runner_source_sha256,
            "execution_environment_contract_sha256": self.execution_environment_contract_sha256,
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


def _reservation_from_verification(
    verification: ReferenceMinimizationValidationAuthorizationVerification,
    *,
    reserved_at_utc: str,
) -> ReferenceMinimizationValidationNonceReservation:
    values = {
        "authorization_receipt_sha256": verification.receipt_sha256,
        "review_attestation_sha256": verification.review_attestation_sha256,
        "authorization_operator_identity_sha256": verification.authorization_operator_identity_sha256,
        "authorization_nonce_sha256": verification.authorization_nonce_sha256,
        "code_commit_sha": verification.code_commit_sha,
        "runner_source_sha256": verification.runner_source_sha256,
        "execution_environment_contract_sha256": verification.execution_environment_contract_sha256,
        "result_receipt_contract_sha256": verification.result_receipt_contract_sha256,
        "dependency_artifact_sha256_rows": verification.dependency_artifact_sha256_rows,
        "authorization_issued_at_utc": verification.issued_at_utc,
        "authorization_expires_at_utc": verification.expires_at_utc,
        "reserved_at_utc": reserved_at_utc,
        "reservation_persisted": True,
        "validation_execution_authorized": False,
        "validation_results_collected": False,
        "parameter_fitting_authorized": False,
        "blockers": _POST_RESERVATION_BLOCKERS,
    }
    provisional = ReferenceMinimizationValidationNonceReservation(reservation_record_sha256="0" * 64, **values)
    return ReferenceMinimizationValidationNonceReservation(
        reservation_record_sha256=_sha256(provisional.projection()), **values
    )


def _secure_directory_flags() -> int:
    required = ("O_NOFOLLOW", "O_DIRECTORY", "O_CLOEXEC")
    if (
        os.name != "posix"
        or any(not hasattr(os, name) for name in required)
        or not hasattr(os, "geteuid")
        or os.open not in os.supports_dir_fd
    ):
        raise ReferenceMinimizationValidationNonceReservationError(
            "secure POSIX minimization nonce reservation is unavailable"
        )
    return os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY | os.O_CLOEXEC


def _root_components(root: str | os.PathLike[str]) -> tuple[str, ...]:
    try:
        candidate = Path(root)
    except (TypeError, ValueError) as exc:
        raise ReferenceMinimizationValidationNonceReservationError("nonce reservation root is invalid") from exc
    if not candidate.is_absolute() or ".." in candidate.parts or candidate.anchor != os.sep:
        raise ReferenceMinimizationValidationNonceReservationError(
            "nonce reservation root must be an absolute POSIX path without '..'"
        )
    return tuple(part for part in candidate.parts[1:] if part not in {"", "."})


def _open_secure_root(root: str | os.PathLike[str]) -> int:
    flags = _secure_directory_flags()
    try:
        current_fd = os.open(os.sep, flags)
    except (OSError, ValueError) as exc:
        raise ReferenceMinimizationValidationNonceReservationError("filesystem root cannot be opened securely") from exc
    try:
        for component in _root_components(root):
            previous_fd = current_fd
            current_fd = -1
            try:
                current_fd = os.open(component, flags, dir_fd=previous_fd)
            except (OSError, ValueError) as exc:
                raise ReferenceMinimizationValidationNonceReservationError(
                    "nonce reservation root is missing, inaccessible, or traverses a symlink"
                ) from exc
            finally:
                os.close(previous_fd)
        root_stat = os.fstat(current_fd)
        if (
            not stat.S_ISDIR(root_stat.st_mode)
            or root_stat.st_uid != os.geteuid()
            or stat.S_IMODE(root_stat.st_mode) != 0o700
        ):
            raise ReferenceMinimizationValidationNonceReservationError(
                "nonce reservation root must be an effective-uid-owned mode-0700 directory"
            )
        result = current_fd
        current_fd = -1
        return result
    finally:
        if current_fd >= 0:
            os.close(current_fd)


def _validate_record_stat(file_stat: os.stat_result) -> None:
    if (
        not stat.S_ISREG(file_stat.st_mode)
        or file_stat.st_uid != os.geteuid()
        or stat.S_IMODE(file_stat.st_mode) != 0o600
        or file_stat.st_nlink != 1
    ):
        raise ReferenceMinimizationValidationNonceReservationError(
            "nonce reservation record must be an effective-uid-owned mode-0600 single-link regular file"
        )


def _stable_record_identity(file_stat: os.stat_result) -> tuple[int, ...]:
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


def _persist(root_fd: int, reservation: ReferenceMinimizationValidationNonceReservation) -> None:
    filename = f"{reservation.authorization_nonce_sha256}.json"
    encoded = _canonical_bytes(reservation.to_dict()) + b"\n"
    if len(encoded) > REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_MAX_RECORD_BYTES:
        raise ReferenceMinimizationValidationNonceReservationError("nonce reservation record exceeds the size limit")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
    try:
        descriptor = os.open(filename, flags, 0o600, dir_fd=root_fd)
    except FileExistsError as exc:
        raise ReferenceMinimizationValidationNonceAlreadyReservedError(
            "authorization nonce is already reserved"
        ) from exc
    except (OSError, ValueError) as exc:
        raise ReferenceMinimizationValidationNonceReservationError(
            "nonce reservation record cannot be created securely"
        ) from exc
    try:
        try:
            _validate_record_stat(os.fstat(descriptor))
            _write_all(descriptor, encoded)
            os.fsync(descriptor)
        except Exception as exc:
            raise ReferenceMinimizationValidationNonceReservationError(
                "nonce reservation persistence failed; the nonce path remains consumed"
            ) from exc
    finally:
        os.close(descriptor)
    try:
        os.fsync(root_fd)
    except OSError as exc:
        raise ReferenceMinimizationValidationNonceReservationError(
            "nonce reservation directory fsync failed; the nonce path remains consumed"
        ) from exc


def reserve_reference_minimization_validation_authorization_nonce(
    reservation_root: str | os.PathLike[str],
    *,
    authorization_receipt: str | bytes | Mapping[str, Any],
    review_attestation: str | bytes | Mapping[str, Any],
    trusted_reviewer_keys: Mapping[str, MinimizationScientificReviewerTrustAnchor],
    expected_implementation_author_identity_sha256: str,
    trusted_operator_keys: Mapping[str, MinimizationAuthorizationOperatorTrustAnchor],
    reserved_at: datetime,
    expected_code_commit_sha: str,
    expected_runner_source_sha256: str,
    expected_dependency_artifact_sha256_rows: Mapping[str, str],
    revoked_receipt_sha256s: Sequence[str] = (),
    revoked_review_attestation_sha256s: Sequence[str] = (),
    externally_consumed_nonce_sha256s: Sequence[str] = (),
) -> ReferenceMinimizationValidationNonceReservation:
    """Reverify raw signed artifacts and durably consume their nonce."""

    reserved_at_utc = _format_utc(reserved_at, name="reserved_at")
    try:
        verification = verify_signed_reference_minimization_validation_authorization_receipt(
            authorization_receipt,
            review_attestation=review_attestation,
            trusted_reviewer_keys=trusted_reviewer_keys,
            expected_implementation_author_identity_sha256=(expected_implementation_author_identity_sha256),
            trusted_operator_keys=trusted_operator_keys,
            checked_at=reserved_at,
            expected_code_commit_sha=expected_code_commit_sha,
            expected_runner_source_sha256=expected_runner_source_sha256,
            expected_dependency_artifact_sha256_rows=(expected_dependency_artifact_sha256_rows),
            revoked_receipt_sha256s=revoked_receipt_sha256s,
            revoked_review_attestation_sha256s=(revoked_review_attestation_sha256s),
            consumed_nonce_sha256s=externally_consumed_nonce_sha256s,
        )
    except ReferenceMinimizationValidationAuthorizationError as exc:
        raise ReferenceMinimizationValidationNonceReservationError(
            "nonce reservation authorization verification failed"
        ) from exc
    if not verification.eligible_for_atomic_execution_reservation:
        raise ReferenceMinimizationValidationNonceReservationError(
            "authorization receipt is not eligible for atomic nonce reservation"
        )
    reservation = _reservation_from_verification(verification, reserved_at_utc=reserved_at_utc)
    root_fd = _open_secure_root(reservation_root)
    try:
        _persist(root_fd, reservation)
    finally:
        os.close(root_fd)
    return reservation


def _load_record(raw: bytes) -> dict[str, Any]:
    if not raw or len(raw) > (REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_MAX_RECORD_BYTES):
        raise ReferenceMinimizationValidationNonceReservationError("nonce reservation record size is invalid")

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ReferenceMinimizationValidationNonceReservationError(
                    "nonce reservation record contains a duplicate JSON key"
                )
            result[key] = value
        return result

    try:
        loaded = json.loads(raw.decode("ascii"), object_pairs_hook=reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReferenceMinimizationValidationNonceReservationError(
            "nonce reservation record must be canonical ASCII JSON"
        ) from exc
    if not isinstance(loaded, dict) or raw != _canonical_bytes(loaded) + b"\n":
        raise ReferenceMinimizationValidationNonceReservationError("nonce reservation record bytes are not canonical")
    return loaded


def _reservation_from_record(
    payload: Mapping[str, Any], *, expected_nonce_sha256: str
) -> ReferenceMinimizationValidationNonceReservation:
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
        raise ReferenceMinimizationValidationNonceReservationError("nonce reservation record fields are invalid")
    fixed = {
        "schema_id": REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_SCHEMA_ID,
        "contract_sha256": FROZEN_REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_CONTRACT_SHA256,
        "authorization_contract_sha256": FROZEN_REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_CONTRACT_SHA256,
        "execution_environment_contract_sha256": FROZEN_REFERENCE_MINIMIZATION_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256,
        "result_receipt_contract_sha256": FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256,
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
    if any(payload.get(key) != value for key, value in fixed.items()):
        raise ReferenceMinimizationValidationNonceReservationError("nonce reservation record fixed fields drifted")
    nonce = _require_sha256(payload.get("authorization_nonce_sha256"), name="record authorization nonce")
    if nonce != expected_nonce_sha256:
        raise ReferenceMinimizationValidationNonceReservationError(
            "nonce reservation filename and record identity are cross-wired"
        )
    projection = dict(payload)
    record_sha256 = projection.pop("reservation_record_sha256")
    if record_sha256 != _sha256(projection):
        raise ReferenceMinimizationValidationNonceReservationError(
            "nonce reservation record SHA-256 verification failed"
        )
    return ReferenceMinimizationValidationNonceReservation(
        reservation_record_sha256=_require_sha256(record_sha256, name="reservation record"),
        authorization_receipt_sha256=_require_sha256(
            payload.get("authorization_receipt_sha256"),
            name="record authorization receipt",
        ),
        review_attestation_sha256=_require_sha256(
            payload.get("review_attestation_sha256"), name="record review attestation"
        ),
        authorization_operator_identity_sha256=_require_sha256(
            payload.get("authorization_operator_identity_sha256"),
            name="record authorization operator",
        ),
        authorization_nonce_sha256=nonce,
        code_commit_sha=_require_git_commit(payload.get("code_commit_sha")),
        runner_source_sha256=_require_sha256(payload.get("runner_source_sha256"), name="record runner source"),
        execution_environment_contract_sha256=payload["execution_environment_contract_sha256"],
        result_receipt_contract_sha256=payload["result_receipt_contract_sha256"],
        dependency_artifact_sha256_rows=_normalize_dependency_rows(payload["dependency_artifact_sha256_rows"]),
        authorization_issued_at_utc=_require_utc(
            payload.get("authorization_issued_at_utc"),
            name="record authorization issued_at_utc",
        ),
        authorization_expires_at_utc=_require_utc(
            payload.get("authorization_expires_at_utc"),
            name="record authorization expires_at_utc",
        ),
        reserved_at_utc=_require_utc(payload.get("reserved_at_utc"), name="record reserved_at_utc"),
        reservation_persisted=True,
        validation_execution_authorized=False,
        validation_results_collected=False,
        parameter_fitting_authorized=False,
        blockers=_POST_RESERVATION_BLOCKERS,
    )


def read_reference_minimization_validation_nonce_reservation(
    reservation_root: str | os.PathLike[str], *, authorization_nonce_sha256: str
) -> ReferenceMinimizationValidationNonceReservation:
    """Read and verify one durable reservation without changing it."""

    nonce = _require_sha256(authorization_nonce_sha256, name="authorization nonce")
    root_fd = _open_secure_root(reservation_root)
    filename = f"{nonce}.json"
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
    try:
        try:
            descriptor = os.open(filename, flags, dir_fd=root_fd)
        except (OSError, ValueError) as exc:
            raise ReferenceMinimizationValidationNonceReservationError(
                "nonce reservation record is missing or cannot be opened securely"
            ) from exc
        try:
            file_stat = os.fstat(descriptor)
            _validate_record_stat(file_stat)
            if file_stat.st_size <= 0 or file_stat.st_size > (
                REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_MAX_RECORD_BYTES
            ):
                raise ReferenceMinimizationValidationNonceReservationError("nonce reservation record size is invalid")
            raw = b""
            while len(raw) <= (REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_MAX_RECORD_BYTES):
                chunk = os.read(descriptor, 65_536)
                if not chunk:
                    break
                raw += chunk
            if _stable_record_identity(os.fstat(descriptor)) != (_stable_record_identity(file_stat)):
                raise ReferenceMinimizationValidationNonceReservationError(
                    "nonce reservation record changed while it was read"
                )
        finally:
            os.close(descriptor)
    finally:
        os.close(root_fd)
    return _reservation_from_record(_load_record(raw), expected_nonce_sha256=nonce)


def reference_minimization_validation_nonce_reservation_contract_decision() -> dict[str, Any]:
    """Return the closed current decision without reserving a nonce."""

    contract = reference_minimization_validation_nonce_reservation_contract_document()
    return {
        "contract_sha256": contract["contract_sha256"],
        "atomic_nonce_reservation_primitive_implemented": True,
        "production_reservation_root_present": False,
        "authorization_nonce_reserved": False,
        "execution_environment_receipt_present": False,
        "validation_execution_authorized": False,
        "validation_results_collected": False,
        "parameter_fitting_authorized": False,
        "blockers": list(_CURRENT_BLOCKERS),
    }


__all__ = [
    "FROZEN_REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_CONTRACT_SHA256",
    "REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_CONTRACT_ID",
    "REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_CONTRACT_SCHEMA_ID",
    "REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_CONTRACT_VERSION",
    "REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_MAX_RECORD_BYTES",
    "REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_SCHEMA_ID",
    "ReferenceMinimizationValidationNonceAlreadyReservedError",
    "ReferenceMinimizationValidationNonceReservation",
    "ReferenceMinimizationValidationNonceReservationError",
    "read_reference_minimization_validation_nonce_reservation",
    "reference_minimization_validation_nonce_reservation_contract_decision",
    "reference_minimization_validation_nonce_reservation_contract_document",
    "require_reference_minimization_validation_nonce_reservation_contract_document",
    "reserve_reference_minimization_validation_authorization_nonce",
]
