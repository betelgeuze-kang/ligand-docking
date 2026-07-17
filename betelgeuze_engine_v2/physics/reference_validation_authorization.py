"""Signed execution-authorization receipt contract for CPU validation.

This module verifies a future operator-signed authorization receipt against an
already verified independent-review attestation.  It does not bundle trust
keys or receipts, reserve one-time nonces, run validation, write results,
authorize parameter fitting, or promote scientific/product claims.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import re
from typing import Any, Mapping, Sequence

from .reference_validation_artifact_binding import (
    FROZEN_REFERENCE_VALIDATION_ARTIFACT_BINDING_SHA256,
)
from .reference_validation_review import (
    FROZEN_REFERENCE_VALIDATION_REVIEW_CONTRACT_SHA256,
    ReferenceValidationReviewError,
    ReferenceValidationReviewVerification,
    ScientificReviewerTrustAnchor,
    reference_validation_review_contract_document,
    verify_signed_reference_validation_review_attestation,
)


REFERENCE_VALIDATION_AUTHORIZATION_CONTRACT_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_validation_authorization_contract/1.0.0"
)
REFERENCE_VALIDATION_AUTHORIZATION_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_validation_authorization_receipt/1.0.0"
)
REFERENCE_VALIDATION_AUTHORIZATION_CONTRACT_ID = (
    "cpu_reference_validation_execution_authorization_contract/1.0.0"
)
REFERENCE_VALIDATION_AUTHORIZATION_CONTRACT_VERSION = "1.0.0"
REFERENCE_VALIDATION_AUTHORIZATION_CONTRACT_FROZEN_AT_UTC = "2026-07-17T05:00:00Z"
REFERENCE_VALIDATION_AUTHORIZATION_SIGNATURE_ALGORITHM = "hmac-sha256"
REFERENCE_VALIDATION_AUTHORIZATION_MAX_VALIDITY = timedelta(hours=24)

FROZEN_REFERENCE_VALIDATION_AUTHORIZATION_CONTRACT_SHA256 = (
    "8c10d264c4228bead4a8d53b337a689d1ae1814c893190bb975f438cb9b3c018"
)

_GIT_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_CURRENT_BLOCKERS = (
    "signed_execution_authorization_receipt_missing",
    "trusted_authorization_operator_key_not_provided",
    "authorization_nonce_not_atomically_reserved",
    "execution_environment_contract_not_frozen",
    "result_receipt_contract_not_frozen",
    "validation_execution_not_authorized",
    "validation_results_not_collected",
    "parameter_fitting_not_authorized",
    "scientific_validation_missing",
    "product_integration_not_qualified",
)
_POST_RECEIPT_BLOCKERS = (
    "authorization_nonce_not_atomically_reserved",
    "execution_environment_not_reverified_at_run_start",
    "result_receipt_writer_not_implemented",
    "validation_execution_not_authorized",
    "validation_results_not_collected",
    "parameter_fitting_not_authorized",
    "scientific_validation_missing",
    "product_integration_not_qualified",
)


class ReferenceValidationAuthorizationError(ValueError):
    """The authorization contract, receipt, trust, or dependency is invalid."""


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
        raise ReferenceValidationAuthorizationError(
            "authorization artifact is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ReferenceValidationAuthorizationError(
            f"{name} must be a lowercase SHA-256"
        )
    if any(character not in "0123456789abcdef" for character in value):
        raise ReferenceValidationAuthorizationError(
            f"{name} must be a lowercase SHA-256"
        )
    return value


def _require_git_commit(value: object) -> str:
    if not isinstance(value, str) or not _GIT_COMMIT_RE.fullmatch(value):
        raise ReferenceValidationAuthorizationError(
            "authorization code commit must be a lowercase 40-character Git SHA"
        )
    return value


def _require_key_id(value: object) -> str:
    if not isinstance(value, str) or not value or len(value) > 128:
        raise ReferenceValidationAuthorizationError(
            "authorization key id must contain 1 to 128 characters"
        )
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
    if any(character not in allowed for character in value):
        raise ReferenceValidationAuthorizationError(
            "authorization key id contains unsupported characters"
        )
    return value


def _require_key(value: bytes | str, *, name: str) -> bytes:
    if isinstance(value, str):
        key = value.encode("utf-8")
    elif isinstance(value, bytes):
        key = value
    else:
        raise ReferenceValidationAuthorizationError(f"{name} must be bytes or text")
    if len(key) < 32:
        raise ReferenceValidationAuthorizationError(
            f"{name} must contain at least 32 bytes"
        )
    return key


def _parse_utc(value: object, *, name: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ReferenceValidationAuthorizationError(
            f"{name} must be second-resolution UTC"
        )
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise ReferenceValidationAuthorizationError(
            f"{name} must be second-resolution UTC"
        ) from exc


def _format_utc(value: datetime, *, name: str) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ReferenceValidationAuthorizationError(
            f"{name} must be timezone-aware"
        )
    normalized = value.astimezone(timezone.utc)
    if normalized.microsecond:
        raise ReferenceValidationAuthorizationError(
            f"{name} must use second resolution"
        )
    return normalized.strftime("%Y-%m-%dT%H:%M:%SZ")


def _dependency_rows(rows: Mapping[str, str]) -> list[dict[str, str]]:
    if not isinstance(rows, Mapping) or not rows:
        raise ReferenceValidationAuthorizationError(
            "dependency artifact rows must be a non-empty mapping"
        )
    normalized: list[dict[str, str]] = []
    for artifact_id, digest in sorted(rows.items()):
        if not isinstance(artifact_id, str) or not artifact_id or len(artifact_id) > 200:
            raise ReferenceValidationAuthorizationError(
                "dependency artifact id must contain 1 to 200 characters"
            )
        if any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for character in artifact_id):
            raise ReferenceValidationAuthorizationError(
                "dependency artifact id contains unsupported characters"
            )
        normalized.append(
            {
                "artifact_id": artifact_id,
                "sha256": _require_sha256(digest, name=f"dependency {artifact_id}"),
            }
        )
    return normalized


def _contract_projection() -> dict[str, Any]:
    review_contract = reference_validation_review_contract_document()
    return {
        "schema_id": REFERENCE_VALIDATION_AUTHORIZATION_CONTRACT_SCHEMA_ID,
        "contract_id": REFERENCE_VALIDATION_AUTHORIZATION_CONTRACT_ID,
        "contract_version": REFERENCE_VALIDATION_AUTHORIZATION_CONTRACT_VERSION,
        "frozen_at_utc": REFERENCE_VALIDATION_AUTHORIZATION_CONTRACT_FROZEN_AT_UTC,
        "purpose": {
            "scope": "future_single_run_synthetic_cpu_validation_authorization",
            "contract_definition_only": True,
            "authorization_receipt_present": False,
            "validation_execution_authorized": False,
            "parameter_fitting_proposal_authorized": False,
            "parameter_fitting_authorized": False,
        },
        "dependencies": {
            "artifact_binding_sha256": FROZEN_REFERENCE_VALIDATION_ARTIFACT_BINDING_SHA256,
            "review_contract_sha256": FROZEN_REFERENCE_VALIDATION_REVIEW_CONTRACT_SHA256,
            "observed_review_contract_sha256": review_contract["contract_sha256"],
            "verified_nonexpired_review_attestation_required": True,
            "exact_code_commit_required": True,
            "exact_runner_source_sha256_required": True,
            "exact_execution_environment_contract_sha256_required": True,
            "exact_result_receipt_contract_sha256_required": True,
            "dependency_artifact_sha256_rows_required": True,
        },
        "identity_policy": {
            "implementation_author_identity_required": True,
            "independent_reviewer_identity_required": True,
            "authorization_operator_identity_required": True,
            "all_three_identities_must_be_pairwise_distinct": True,
            "trusted_operator_key_supplied_out_of_band": True,
            "repository_does_not_choose_or_bundle_trusted_operator_keys": True,
        },
        "receipt_schema": {
            "schema_id": REFERENCE_VALIDATION_AUTHORIZATION_RECEIPT_SCHEMA_ID,
            "signature_algorithm": REFERENCE_VALIDATION_AUTHORIZATION_SIGNATURE_ALGORITHM,
            "maximum_validity_seconds": int(
                REFERENCE_VALIDATION_AUTHORIZATION_MAX_VALIDITY.total_seconds()
            ),
            "authorization_scope": "synthetic_implementation_mathematics_only",
            "cpu_only": True,
            "network_access_allowed": False,
            "maximum_execution_count": 1,
            "one_time_nonce_required": True,
            "external_revocation_sets_required": True,
            "atomic_nonce_reservation_required_before_execution": True,
            "scientific_parameterized_force_field_lane_authorized": False,
            "parameter_fitting_proposal_authorized": False,
            "parameter_fitting_authorized": False,
        },
        "current_state": {
            "authorization_receipt_present": False,
            "trusted_operator_key_present": False,
            "nonce_reservation_implemented": False,
            "execution_environment_contract_frozen": False,
            "result_receipt_contract_frozen": False,
            "validation_execution_authorized": False,
            "validation_results_collected": False,
        },
        "claim_policy": {
            "authorization_contract_implemented": True,
            "validation_execution_authorized": False,
            "validation_results_collected": False,
            "force_or_energy_validated": False,
            "scientifically_validated": False,
            "benchmark_validated": False,
            "product_qualified": False,
            "customer_execution_enabled": False,
            "claim_safe": False,
        },
        "blockers": list(_CURRENT_BLOCKERS),
    }


def reference_validation_authorization_contract_document() -> dict[str, Any]:
    document = _contract_projection()
    document["contract_sha256"] = _sha256(document)
    if (
        document["contract_sha256"]
        != FROZEN_REFERENCE_VALIDATION_AUTHORIZATION_CONTRACT_SHA256
    ):
        raise ReferenceValidationAuthorizationError(
            "frozen validation authorization contract SHA-256 drifted"
        )
    return document


def require_reference_validation_authorization_contract_document(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ReferenceValidationAuthorizationError(
            "authorization contract document must be a mapping"
        )
    try:
        observed = json.loads(_canonical_bytes(dict(payload)).decode("ascii"))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ReferenceValidationAuthorizationError(
            "authorization contract document is invalid"
        ) from exc
    expected = reference_validation_authorization_contract_document()
    if observed != expected:
        raise ReferenceValidationAuthorizationError(
            "authorization contract document does not match the frozen record"
        )
    return observed


@dataclass(frozen=True, slots=True)
class AuthorizationOperatorTrustAnchor:
    """Out-of-band operator identity and HMAC verification key."""

    operator_identity_sha256: str
    verification_key: bytes = field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "operator_identity_sha256",
            _require_sha256(
                self.operator_identity_sha256,
                name="trusted authorization operator identity",
            ),
        )
        object.__setattr__(
            self,
            "verification_key",
            _require_key(
                self.verification_key,
                name="trusted authorization operator verification key",
            ),
        )


@dataclass(frozen=True, slots=True)
class ReferenceValidationAuthorizationVerification:
    receipt_sha256: str
    review_attestation_sha256: str
    implementation_author_identity_sha256: str
    independent_reviewer_identity_sha256: str
    authorization_operator_identity_sha256: str
    authorization_key_id: str
    authorization_nonce_sha256: str
    code_commit_sha: str
    runner_source_sha256: str
    execution_environment_contract_sha256: str
    result_receipt_contract_sha256: str
    dependency_artifact_sha256_rows: tuple[tuple[str, str], ...]
    issued_at_utc: str
    expires_at_utc: str
    receipt_authorization_verified: bool
    eligible_for_atomic_execution_reservation: bool
    validation_execution_authorized: bool
    parameter_fitting_proposal_authorized: bool
    parameter_fitting_authorized: bool
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_sha256(self.receipt_sha256, name="authorization receipt")
        _require_sha256(self.review_attestation_sha256, name="authorization review attestation")
        _require_sha256(
            self.implementation_author_identity_sha256,
            name="authorization implementation author identity",
        )
        _require_sha256(
            self.independent_reviewer_identity_sha256,
            name="authorization independent reviewer identity",
        )
        _require_sha256(
            self.authorization_operator_identity_sha256,
            name="authorization operator identity",
        )
        _require_key_id(self.authorization_key_id)
        if len(
            {
                self.implementation_author_identity_sha256,
                self.independent_reviewer_identity_sha256,
                self.authorization_operator_identity_sha256,
            }
        ) != 3:
            raise ReferenceValidationAuthorizationError(
                "authorization verification identities must be pairwise distinct"
            )
        _require_sha256(self.authorization_nonce_sha256, name="authorization nonce")
        _require_git_commit(self.code_commit_sha)
        _require_sha256(self.runner_source_sha256, name="authorization runner source")
        _require_sha256(
            self.execution_environment_contract_sha256,
            name="authorization execution environment contract",
        )
        _require_sha256(
            self.result_receipt_contract_sha256,
            name="authorization result receipt contract",
        )
        if not self.dependency_artifact_sha256_rows:
            raise ReferenceValidationAuthorizationError(
                "authorization verification dependency rows must be non-empty"
            )
        dependency_ids: list[str] = []
        for artifact_id, digest in self.dependency_artifact_sha256_rows:
            normalized = _dependency_rows({artifact_id: digest})[0]
            dependency_ids.append(normalized["artifact_id"])
        if dependency_ids != sorted(set(dependency_ids)):
            raise ReferenceValidationAuthorizationError(
                "authorization verification dependency rows must be sorted and unique"
            )
        issued_at = _parse_utc(self.issued_at_utc, name="authorization issued_at_utc")
        expires_at = _parse_utc(self.expires_at_utc, name="authorization expires_at_utc")
        if expires_at <= issued_at:
            raise ReferenceValidationAuthorizationError(
                "authorization verification expiry must follow issue time"
            )
        if not self.receipt_authorization_verified:
            raise ReferenceValidationAuthorizationError(
                "authorization verification must retain receipt verification"
            )
        if not self.eligible_for_atomic_execution_reservation:
            raise ReferenceValidationAuthorizationError(
                "verified receipt must remain eligible for atomic reservation"
            )
        if (
            self.validation_execution_authorized
            or self.parameter_fitting_proposal_authorized
            or self.parameter_fitting_authorized
        ):
            raise ReferenceValidationAuthorizationError(
                "receipt verification alone cannot open execution or fitting gates"
            )
        if not self.blockers:
            raise ReferenceValidationAuthorizationError(
                "receipt verification must retain downstream blockers"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_sha256": self.receipt_sha256,
            "review_attestation_sha256": self.review_attestation_sha256,
            "implementation_author_identity_sha256": (
                self.implementation_author_identity_sha256
            ),
            "independent_reviewer_identity_sha256": (
                self.independent_reviewer_identity_sha256
            ),
            "authorization_operator_identity_sha256": self.authorization_operator_identity_sha256,
            "authorization_key_id": self.authorization_key_id,
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
            "issued_at_utc": self.issued_at_utc,
            "expires_at_utc": self.expires_at_utc,
            "receipt_authorization_verified": self.receipt_authorization_verified,
            "eligible_for_atomic_execution_reservation": (
                self.eligible_for_atomic_execution_reservation
            ),
            "validation_execution_authorized": self.validation_execution_authorized,
            "parameter_fitting_proposal_authorized": self.parameter_fitting_proposal_authorized,
            "parameter_fitting_authorized": self.parameter_fitting_authorized,
            "blockers": list(self.blockers),
        }


def _require_review_verification(
    review: ReferenceValidationReviewVerification,
) -> ReferenceValidationReviewVerification:
    if not isinstance(review, ReferenceValidationReviewVerification):
        raise ReferenceValidationAuthorizationError(
            "authorization requires a verified independent-review decision"
        )
    if not review.independent_scientific_review_verified:
        raise ReferenceValidationAuthorizationError(
            "authorization review is not independently verified"
        )
    if not review.implementation_author_separation_verified:
        raise ReferenceValidationAuthorizationError(
            "authorization review lacks implementation-author separation"
        )
    if review.contract_sha256 != FROZEN_REFERENCE_VALIDATION_REVIEW_CONTRACT_SHA256:
        raise ReferenceValidationAuthorizationError(
            "authorization review contract identity drifted"
        )
    if review.artifact_binding_sha256 != FROZEN_REFERENCE_VALIDATION_ARTIFACT_BINDING_SHA256:
        raise ReferenceValidationAuthorizationError(
            "authorization review artifact binding drifted"
        )
    return review


def _verify_review_attestation(
    source: str | bytes | Mapping[str, Any],
    *,
    trusted_reviewer_keys: Mapping[str, ScientificReviewerTrustAnchor],
    expected_implementation_author_identity_sha256: str,
    checked_at: datetime,
) -> ReferenceValidationReviewVerification:
    try:
        verified = verify_signed_reference_validation_review_attestation(
            source,
            trusted_reviewer_keys=trusted_reviewer_keys,
            expected_implementation_author_identity_sha256=(
                expected_implementation_author_identity_sha256
            ),
            checked_at=checked_at,
        )
    except ReferenceValidationReviewError as exc:
        raise ReferenceValidationAuthorizationError(
            "authorization independent review verification failed"
        ) from exc
    return _require_review_verification(verified)


def _receipt_projection(
    *,
    review: ReferenceValidationReviewVerification,
    authorization_operator_identity_sha256: str,
    authorization_key_id: str,
    issued_at_utc: str,
    expires_at_utc: str,
    authorization_nonce_sha256: str,
    code_commit_sha: str,
    runner_source_sha256: str,
    execution_environment_contract_sha256: str,
    result_receipt_contract_sha256: str,
    dependency_artifact_sha256_rows: Mapping[str, str],
) -> dict[str, Any]:
    contract = reference_validation_authorization_contract_document()
    return {
        "schema_id": REFERENCE_VALIDATION_AUTHORIZATION_RECEIPT_SCHEMA_ID,
        "contract_sha256": contract["contract_sha256"],
        "artifact_binding_sha256": FROZEN_REFERENCE_VALIDATION_ARTIFACT_BINDING_SHA256,
        "review_contract_sha256": FROZEN_REFERENCE_VALIDATION_REVIEW_CONTRACT_SHA256,
        "review_attestation_sha256": review.attestation_sha256,
        "implementation_author_identity_sha256": review.implementation_author_identity_sha256,
        "independent_reviewer_identity_sha256": review.independent_reviewer_identity_sha256,
        "authorization_operator_identity_sha256": _require_sha256(
            authorization_operator_identity_sha256,
            name="authorization operator identity",
        ),
        "authorization_key_id": _require_key_id(authorization_key_id),
        "issued_at_utc": issued_at_utc,
        "expires_at_utc": expires_at_utc,
        "authorization_nonce_sha256": _require_sha256(
            authorization_nonce_sha256,
            name="authorization nonce",
        ),
        "code_commit_sha": _require_git_commit(code_commit_sha),
        "runner_source_sha256": _require_sha256(
            runner_source_sha256,
            name="validation runner source",
        ),
        "execution_environment_contract_sha256": _require_sha256(
            execution_environment_contract_sha256,
            name="execution environment contract",
        ),
        "result_receipt_contract_sha256": _require_sha256(
            result_receipt_contract_sha256,
            name="result receipt contract",
        ),
        "dependency_artifact_sha256_rows": _dependency_rows(
            dependency_artifact_sha256_rows
        ),
        "authorization_scope": {
            "lane": "synthetic_implementation_mathematics_only",
            "cpu_only": True,
            "network_access_allowed": False,
            "maximum_execution_count": 1,
            "one_time_nonce_required": True,
            "scientific_parameterized_force_field_lane_authorized": False,
            "parameter_fitting_proposal_authorized": False,
            "parameter_fitting_authorized": False,
            "benchmark_publication_authorized": False,
            "customer_execution_authorized": False,
        },
        "superseded": False,
        "revoked": False,
        "scientifically_validated": False,
        "claim_safe": False,
    }


def build_signed_reference_validation_authorization_receipt(
    *,
    review_attestation: str | bytes | Mapping[str, Any],
    trusted_reviewer_keys: Mapping[str, ScientificReviewerTrustAnchor],
    expected_implementation_author_identity_sha256: str,
    authorization_operator_identity_sha256: str,
    authorization_key_id: str,
    signing_key: bytes | str,
    issued_at: datetime,
    expires_at: datetime,
    authorization_nonce_sha256: str,
    code_commit_sha: str,
    runner_source_sha256: str,
    execution_environment_contract_sha256: str,
    result_receipt_contract_sha256: str,
    dependency_artifact_sha256_rows: Mapping[str, str],
) -> dict[str, Any]:
    """Build an operator-signed receipt; no key or receipt is persisted."""

    review = _verify_review_attestation(
        review_attestation,
        trusted_reviewer_keys=trusted_reviewer_keys,
        expected_implementation_author_identity_sha256=(
            expected_implementation_author_identity_sha256
        ),
        checked_at=issued_at,
    )
    projection = _receipt_projection(
        review=review,
        authorization_operator_identity_sha256=authorization_operator_identity_sha256,
        authorization_key_id=authorization_key_id,
        issued_at_utc=_format_utc(issued_at, name="authorization issued_at"),
        expires_at_utc=_format_utc(expires_at, name="authorization expires_at"),
        authorization_nonce_sha256=authorization_nonce_sha256,
        code_commit_sha=code_commit_sha,
        runner_source_sha256=runner_source_sha256,
        execution_environment_contract_sha256=execution_environment_contract_sha256,
        result_receipt_contract_sha256=result_receipt_contract_sha256,
        dependency_artifact_sha256_rows=dependency_artifact_sha256_rows,
    )
    payload = dict(projection)
    payload["receipt_sha256"] = _sha256(projection)
    key = _require_key(signing_key, name="authorization signing key")
    payload["signature"] = {
        "algorithm": REFERENCE_VALIDATION_AUTHORIZATION_SIGNATURE_ALGORITHM,
        "key_id": _require_key_id(authorization_key_id),
        "value": hmac.new(key, _canonical_bytes(payload), hashlib.sha256).hexdigest(),
    }
    return payload


def _load_receipt(source: str | bytes | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(source, Mapping):
        return dict(source)
    raw = source.encode("utf-8") if isinstance(source, str) else source
    if not isinstance(raw, bytes):
        raise ReferenceValidationAuthorizationError(
            "authorization receipt must be a mapping, string, or bytes"
        )

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ReferenceValidationAuthorizationError(
                    "authorization receipt contains a duplicate JSON key"
                )
            result[key] = value
        return result

    try:
        loaded = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReferenceValidationAuthorizationError(
            "authorization receipt must be UTF-8 JSON"
        ) from exc
    if not isinstance(loaded, dict):
        raise ReferenceValidationAuthorizationError(
            "authorization receipt root must be an object"
        )
    return loaded


def verify_signed_reference_validation_authorization_receipt(
    source: str | bytes | Mapping[str, Any],
    *,
    review_attestation: str | bytes | Mapping[str, Any],
    trusted_reviewer_keys: Mapping[str, ScientificReviewerTrustAnchor],
    expected_implementation_author_identity_sha256: str,
    trusted_operator_keys: Mapping[str, AuthorizationOperatorTrustAnchor],
    checked_at: datetime,
    expected_code_commit_sha: str,
    expected_runner_source_sha256: str,
    expected_execution_environment_contract_sha256: str,
    expected_result_receipt_contract_sha256: str,
    expected_dependency_artifact_sha256_rows: Mapping[str, str],
    revoked_receipt_sha256s: Sequence[str] = (),
    revoked_review_attestation_sha256s: Sequence[str] = (),
    consumed_nonce_sha256s: Sequence[str] = (),
) -> ReferenceValidationAuthorizationVerification:
    """Verify a receipt without opening the execution gate or consuming nonce."""

    checked_at_utc = _parse_utc(
        _format_utc(checked_at, name="authorization checked_at"),
        name="authorization checked_at",
    )
    review = _verify_review_attestation(
        review_attestation,
        trusted_reviewer_keys=trusted_reviewer_keys,
        expected_implementation_author_identity_sha256=(
            expected_implementation_author_identity_sha256
        ),
        checked_at=checked_at,
    )
    payload = _load_receipt(source)
    signature = payload.pop("signature", None)
    if not isinstance(signature, Mapping):
        raise ReferenceValidationAuthorizationError(
            "authorization receipt signature is missing"
        )
    if set(signature) != {"algorithm", "key_id", "value"}:
        raise ReferenceValidationAuthorizationError(
            "authorization receipt signature fields are invalid"
        )
    if signature.get("algorithm") != REFERENCE_VALIDATION_AUTHORIZATION_SIGNATURE_ALGORITHM:
        raise ReferenceValidationAuthorizationError(
            "authorization receipt signature algorithm is unsupported"
        )
    key_id = _require_key_id(signature.get("key_id"))
    if key_id not in trusted_operator_keys:
        raise ReferenceValidationAuthorizationError(
            "authorization operator key id is not trusted"
        )
    anchor = trusted_operator_keys[key_id]
    if not isinstance(anchor, AuthorizationOperatorTrustAnchor):
        raise ReferenceValidationAuthorizationError(
            "trusted authorization operator entry has an invalid type"
        )
    expected_signature = hmac.new(
        anchor.verification_key,
        _canonical_bytes(payload),
        hashlib.sha256,
    ).hexdigest()
    signature_value = signature.get("value")
    if not isinstance(signature_value, str) or not hmac.compare_digest(
        signature_value,
        expected_signature,
    ):
        raise ReferenceValidationAuthorizationError(
            "authorization receipt signature verification failed"
        )

    receipt_sha256 = payload.pop("receipt_sha256", None)
    if receipt_sha256 != _sha256(payload):
        raise ReferenceValidationAuthorizationError(
            "authorization receipt SHA-256 verification failed"
        )
    receipt_sha256 = _require_sha256(
        receipt_sha256,
        name="authorization receipt",
    )
    revoked_receipts = {
        _require_sha256(value, name="revoked authorization receipt")
        for value in revoked_receipt_sha256s
    }
    if receipt_sha256 in revoked_receipts:
        raise ReferenceValidationAuthorizationError(
            "authorization receipt is externally revoked"
        )
    revoked_reviews = {
        _require_sha256(value, name="revoked review attestation")
        for value in revoked_review_attestation_sha256s
    }
    if review.attestation_sha256 in revoked_reviews:
        raise ReferenceValidationAuthorizationError(
            "authorization review attestation is externally revoked"
        )

    operator_identity = _require_sha256(
        payload.get("authorization_operator_identity_sha256"),
        name="authorization operator identity",
    )
    if operator_identity != anchor.operator_identity_sha256:
        raise ReferenceValidationAuthorizationError(
            "authorization operator identity does not match the trusted key"
        )
    if operator_identity in {
        review.implementation_author_identity_sha256,
        review.independent_reviewer_identity_sha256,
    }:
        raise ReferenceValidationAuthorizationError(
            "authorization operator must differ from author and reviewer"
        )
    if payload.get("authorization_key_id") != key_id:
        raise ReferenceValidationAuthorizationError(
            "authorization operator key id is cross-wired"
        )

    issued_at = _parse_utc(payload.get("issued_at_utc"), name="authorization issued_at_utc")
    expires_at = _parse_utc(payload.get("expires_at_utc"), name="authorization expires_at_utc")
    review_expires_at = _parse_utc(
        review.expires_at_utc,
        name="authorization review expires_at_utc",
    )
    if expires_at <= issued_at:
        raise ReferenceValidationAuthorizationError(
            "authorization receipt expiry must follow issue time"
        )
    if expires_at - issued_at > REFERENCE_VALIDATION_AUTHORIZATION_MAX_VALIDITY:
        raise ReferenceValidationAuthorizationError(
            "authorization receipt validity exceeds the frozen maximum"
        )
    if issued_at < _parse_utc(review.reviewed_at_utc, name="authorization review reviewed_at_utc"):
        raise ReferenceValidationAuthorizationError(
            "authorization receipt predates the independent review"
        )
    if expires_at > review_expires_at:
        raise ReferenceValidationAuthorizationError(
            "authorization receipt outlives the independent review"
        )
    if checked_at_utc < issued_at:
        raise ReferenceValidationAuthorizationError(
            "authorization receipt is not yet valid"
        )
    if checked_at_utc >= expires_at:
        raise ReferenceValidationAuthorizationError(
            "authorization receipt is expired"
        )
    if checked_at_utc >= review_expires_at:
        raise ReferenceValidationAuthorizationError(
            "authorization review attestation is expired"
        )

    nonce = _require_sha256(
        payload.get("authorization_nonce_sha256"),
        name="authorization nonce",
    )
    consumed_nonces = {
        _require_sha256(value, name="consumed authorization nonce")
        for value in consumed_nonce_sha256s
    }
    if nonce in consumed_nonces:
        raise ReferenceValidationAuthorizationError(
            "authorization nonce was already consumed"
        )

    expected_projection = _receipt_projection(
        review=review,
        authorization_operator_identity_sha256=operator_identity,
        authorization_key_id=key_id,
        issued_at_utc=payload["issued_at_utc"],
        expires_at_utc=payload["expires_at_utc"],
        authorization_nonce_sha256=nonce,
        code_commit_sha=_require_git_commit(expected_code_commit_sha),
        runner_source_sha256=_require_sha256(
            expected_runner_source_sha256,
            name="expected validation runner source",
        ),
        execution_environment_contract_sha256=_require_sha256(
            expected_execution_environment_contract_sha256,
            name="expected execution environment contract",
        ),
        result_receipt_contract_sha256=_require_sha256(
            expected_result_receipt_contract_sha256,
            name="expected result receipt contract",
        ),
        dependency_artifact_sha256_rows=expected_dependency_artifact_sha256_rows,
    )
    if payload != expected_projection:
        raise ReferenceValidationAuthorizationError(
            "authorization receipt fields do not match the frozen schema or expected dependencies"
        )
    return ReferenceValidationAuthorizationVerification(
        receipt_sha256=receipt_sha256,
        review_attestation_sha256=review.attestation_sha256,
        implementation_author_identity_sha256=(
            review.implementation_author_identity_sha256
        ),
        independent_reviewer_identity_sha256=(
            review.independent_reviewer_identity_sha256
        ),
        authorization_operator_identity_sha256=operator_identity,
        authorization_key_id=key_id,
        authorization_nonce_sha256=nonce,
        code_commit_sha=expected_projection["code_commit_sha"],
        runner_source_sha256=expected_projection["runner_source_sha256"],
        execution_environment_contract_sha256=expected_projection[
            "execution_environment_contract_sha256"
        ],
        result_receipt_contract_sha256=expected_projection[
            "result_receipt_contract_sha256"
        ],
        dependency_artifact_sha256_rows=tuple(
            (row["artifact_id"], row["sha256"])
            for row in expected_projection["dependency_artifact_sha256_rows"]
        ),
        issued_at_utc=payload["issued_at_utc"],
        expires_at_utc=payload["expires_at_utc"],
        receipt_authorization_verified=True,
        eligible_for_atomic_execution_reservation=True,
        validation_execution_authorized=False,
        parameter_fitting_proposal_authorized=False,
        parameter_fitting_authorized=False,
        blockers=_POST_RECEIPT_BLOCKERS,
    )


def reference_validation_authorization_contract_decision() -> dict[str, Any]:
    """Return the current closed decision; no authorization receipt is bundled."""

    contract = reference_validation_authorization_contract_document()
    return {
        "contract_sha256": contract["contract_sha256"],
        "authorization_receipt_present": False,
        "trusted_operator_key_present": False,
        "receipt_authorization_verified": False,
        "authorization_nonce_reserved": False,
        "validation_execution_authorized": False,
        "parameter_fitting_proposal_authorized": False,
        "parameter_fitting_authorized": False,
        "blockers": list(_CURRENT_BLOCKERS),
    }


__all__ = [
    "FROZEN_REFERENCE_VALIDATION_AUTHORIZATION_CONTRACT_SHA256",
    "REFERENCE_VALIDATION_AUTHORIZATION_CONTRACT_ID",
    "REFERENCE_VALIDATION_AUTHORIZATION_CONTRACT_SCHEMA_ID",
    "REFERENCE_VALIDATION_AUTHORIZATION_CONTRACT_VERSION",
    "REFERENCE_VALIDATION_AUTHORIZATION_MAX_VALIDITY",
    "REFERENCE_VALIDATION_AUTHORIZATION_RECEIPT_SCHEMA_ID",
    "REFERENCE_VALIDATION_AUTHORIZATION_SIGNATURE_ALGORITHM",
    "AuthorizationOperatorTrustAnchor",
    "ReferenceValidationAuthorizationError",
    "ReferenceValidationAuthorizationVerification",
    "build_signed_reference_validation_authorization_receipt",
    "reference_validation_authorization_contract_decision",
    "reference_validation_authorization_contract_document",
    "require_reference_validation_authorization_contract_document",
    "verify_signed_reference_validation_authorization_receipt",
]
