"""Signed single-run authorization contract for minimization validation.

This module can build and verify a future operator-signed authorization receipt
against an independently verified minimization-review attestation.  It bundles
no trust key or receipt, reserves no nonce, starts no runner, collects no
result, authorizes no parameter fitting, and promotes no scientific claim.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from .reference_minimization_validation_artifact_binding import (
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_ARTIFACT_BINDING_SHA256,
)
from .reference_minimization_validation_ed25519 import (
    ReferenceMinimizationValidationEd25519Error,
    ed25519_public_key_bytes,
    sign_ed25519,
    verify_ed25519,
)
from .reference_minimization_validation_dependency_identity import (
    REFERENCE_MINIMIZATION_VALIDATION_REQUIRED_DEPENDENCY_ARTIFACT_IDS,
)
from .reference_minimization_validation_receipts import (
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256,
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256,
)
from .reference_minimization_validation_review import (
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_REVIEW_CONTRACT_SHA256,
    MinimizationScientificReviewerTrustAnchor,
    ReferenceMinimizationValidationReviewError,
    ReferenceMinimizationValidationReviewVerification,
    reference_minimization_validation_review_contract_document,
    verify_signed_reference_minimization_validation_review_attestation,
)


REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_CONTRACT_SCHEMA_ID = "betelgeuze.engine_v2_reference_minimization_validation_authorization_contract/3.0.0"
REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_validation_authorization_receipt/3.0.0"
)
REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_CONTRACT_ID = (
    "cpu_reference_minimization_validation_execution_authorization_contract/3.0.0"
)
REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_CONTRACT_VERSION = "3.0.0"
REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_CONTRACT_FROZEN_AT_UTC = (
    "2026-07-18T22:48:58Z"
)
REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_SIGNATURE_ALGORITHM = "ed25519"
REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_MAX_VALIDITY = timedelta(hours=24)

FROZEN_REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_CONTRACT_SHA256 = (
    "ccecce01b07020b97856c2dca15d5e93d2857bb2b87490874d02d69922055018"
)
FROZEN_LEGACY_REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_CONTRACT_SHA256_V2 = (
    "cd60c50e4403ece77c98975fcbc4c45d71b2f4213944e4b48b8ec48691e940a9"
)

_GIT_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
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
_POST_RECEIPT_BLOCKERS = (
    "authorization_nonce_not_atomically_reserved",
    "execution_environment_not_reverified_at_run_start",
    "validation_execution_not_authorized",
    "minimization_validation_results_not_collected",
    "independent_result_review_missing",
    "parameter_fitting_not_authorized",
    "scientific_validation_missing",
    "product_integration_not_qualified",
)


class ReferenceMinimizationValidationAuthorizationError(ValueError):
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
        raise ReferenceMinimizationValidationAuthorizationError(
            "minimization authorization artifact is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ReferenceMinimizationValidationAuthorizationError(
            f"{name} must be a lowercase SHA-256"
        )
    return value


def _require_git_commit(value: object) -> str:
    if not isinstance(value, str) or not _GIT_COMMIT_RE.fullmatch(value):
        raise ReferenceMinimizationValidationAuthorizationError(
            "authorization code commit must be a lowercase 40-character Git SHA"
        )
    return value


def _require_key_id(value: object) -> str:
    if not isinstance(value, str) or not value or len(value) > 128:
        raise ReferenceMinimizationValidationAuthorizationError(
            "authorization key id must contain 1 to 128 characters"
        )
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
    if any(character not in allowed for character in value):
        raise ReferenceMinimizationValidationAuthorizationError(
            "authorization key id contains unsupported characters"
        )
    return value


def _require_key(value: bytes | str, *, name: str) -> bytes:
    if isinstance(value, str):
        key = value.encode("utf-8")
    elif isinstance(value, bytes):
        key = value
    else:
        raise ReferenceMinimizationValidationAuthorizationError(
            f"{name} must be bytes or text"
        )
    if len(key) != 32:
        raise ReferenceMinimizationValidationAuthorizationError(
            f"{name} must contain exactly 32 bytes"
        )
    return key


def _parse_utc(value: object, *, name: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ReferenceMinimizationValidationAuthorizationError(
            f"{name} must be second-resolution UTC"
        )
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise ReferenceMinimizationValidationAuthorizationError(
            f"{name} must be second-resolution UTC"
        ) from exc


def _format_utc(value: datetime, *, name: str) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ReferenceMinimizationValidationAuthorizationError(
            f"{name} must be timezone-aware"
        )
    normalized = value.astimezone(timezone.utc)
    if normalized.microsecond:
        raise ReferenceMinimizationValidationAuthorizationError(
            f"{name} must use second resolution"
        )
    return normalized.strftime("%Y-%m-%dT%H:%M:%SZ")


def _dependency_rows(rows: Mapping[str, str]) -> list[dict[str, str]]:
    if not isinstance(rows, Mapping) or not rows:
        raise ReferenceMinimizationValidationAuthorizationError(
            "dependency artifact rows must be a non-empty mapping"
        )
    if tuple(sorted(rows)) != (
        REFERENCE_MINIMIZATION_VALIDATION_REQUIRED_DEPENDENCY_ARTIFACT_IDS
    ):
        raise ReferenceMinimizationValidationAuthorizationError(
            "dependency artifact rows do not match the required byte identities"
        )
    normalized: list[dict[str, str]] = []
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
    for artifact_id, digest in sorted(rows.items()):
        if (
            not isinstance(artifact_id, str)
            or not artifact_id
            or len(artifact_id) > 200
            or any(character not in allowed for character in artifact_id)
        ):
            raise ReferenceMinimizationValidationAuthorizationError(
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
    review = reference_minimization_validation_review_contract_document()
    return {
        "schema_id": REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_CONTRACT_SCHEMA_ID,
        "contract_id": REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_CONTRACT_ID,
        "contract_version": REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_CONTRACT_VERSION,
        "frozen_at_utc": REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_CONTRACT_FROZEN_AT_UTC,
        "purpose": {
            "scope": "future_single_run_synthetic_cpu_minimization_validation_authorization",
            "contract_definition_only": True,
            "authorization_receipt_present": False,
            "validation_execution_authorized": False,
            "parameter_fitting_proposal_authorized": False,
            "parameter_fitting_authorized": False,
        },
        "dependencies": {
            "artifact_binding_sha256": FROZEN_REFERENCE_MINIMIZATION_VALIDATION_ARTIFACT_BINDING_SHA256,
            "review_contract_sha256": FROZEN_REFERENCE_MINIMIZATION_VALIDATION_REVIEW_CONTRACT_SHA256,
            "observed_review_contract_sha256": review["contract_sha256"],
            "execution_environment_contract_sha256": FROZEN_REFERENCE_MINIMIZATION_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256,
            "result_receipt_contract_sha256": FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256,
            "verified_nonexpired_review_attestation_required": True,
            "exact_code_commit_required": True,
            "exact_runner_source_sha256_required": True,
            "dependency_artifact_sha256_rows_required": True,
            "actual_dependency_byte_measurement_required": True,
            "required_dependency_artifact_ids": list(
                REFERENCE_MINIMIZATION_VALIDATION_REQUIRED_DEPENDENCY_ARTIFACT_IDS
            ),
        },
        "identity_policy": {
            "implementation_author_identity_required": True,
            "independent_reviewer_identity_required": True,
            "authorization_operator_identity_required": True,
            "all_three_identities_must_be_pairwise_distinct": True,
            "trusted_operator_key_supplied_out_of_band": True,
            "verifier_trust_anchor_contains_public_key_only": True,
            "private_signing_key_remains_external_to_verifier": True,
            "repository_does_not_choose_or_bundle_trusted_operator_keys": True,
        },
        "receipt_schema": {
            "schema_id": REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_RECEIPT_SCHEMA_ID,
            "signature_algorithm": REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_SIGNATURE_ALGORITHM,
            "maximum_validity_seconds": int(
                REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_MAX_VALIDITY.total_seconds()
            ),
            "authorization_scope": "synthetic_minimization_implementation_mathematics_only",
            "cpu_only": True,
            "network_access_allowed": False,
            "maximum_execution_count": 1,
            "one_time_nonce_required": True,
            "external_revocation_sets_required": True,
            "atomic_nonce_reservation_required_before_execution": True,
            "builder_round_trip_verification_required": True,
            "scientific_parameterized_force_field_lane_authorized": False,
            "parameter_fitting_proposal_authorized": False,
            "parameter_fitting_authorized": False,
        },
        "current_state": {
            "authorization_receipt_present": False,
            "trusted_operator_key_present": False,
            "nonce_reservation_implemented": True,
            "execution_environment_contract_frozen": True,
            "result_receipt_contract_frozen": True,
            "validation_execution_authorized": False,
            "validation_results_collected": False,
        },
        "claim_policy": {
            "authorization_contract_implemented": True,
            "validation_execution_authorized": False,
            "validation_results_collected": False,
            "minimization_validated": False,
            "scientifically_validated": False,
            "benchmark_validated": False,
            "product_qualified": False,
            "customer_execution_enabled": False,
            "claim_safe": False,
        },
        "blockers": list(_CURRENT_BLOCKERS),
    }


def reference_minimization_validation_authorization_contract_document() -> dict[
    str, Any
]:
    document = _contract_projection()
    document["contract_sha256"] = _sha256(document)
    if document["contract_sha256"] != (
        FROZEN_REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_CONTRACT_SHA256
    ):
        raise ReferenceMinimizationValidationAuthorizationError(
            "frozen minimization authorization contract SHA-256 drifted"
        )
    return document


def require_reference_minimization_validation_authorization_contract_document(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ReferenceMinimizationValidationAuthorizationError(
            "authorization contract document must be a mapping"
        )
    observed = json.loads(_canonical_bytes(dict(payload)).decode("ascii"))
    expected = reference_minimization_validation_authorization_contract_document()
    if observed != expected:
        raise ReferenceMinimizationValidationAuthorizationError(
            "authorization contract document does not match the frozen record"
        )
    return observed


@dataclass(frozen=True, slots=True)
class MinimizationAuthorizationOperatorTrustAnchor:
    """Out-of-band operator identity and Ed25519 public key."""

    operator_identity_sha256: str
    verification_key: bytes = field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "operator_identity_sha256",
            _require_sha256(
                self.operator_identity_sha256,
                name="trusted minimization authorization operator identity",
            ),
        )
        object.__setattr__(
            self,
            "verification_key",
            _require_key(
                self.verification_key,
                name="trusted minimization authorization operator verification key",
            ),
        )


@dataclass(frozen=True, slots=True)
class ReferenceMinimizationValidationAuthorizationVerification:
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
        for name, value in (
            ("authorization receipt", self.receipt_sha256),
            ("review attestation", self.review_attestation_sha256),
            ("implementation author", self.implementation_author_identity_sha256),
            ("independent reviewer", self.independent_reviewer_identity_sha256),
            ("authorization operator", self.authorization_operator_identity_sha256),
            ("authorization nonce", self.authorization_nonce_sha256),
            ("runner source", self.runner_source_sha256),
            ("environment contract", self.execution_environment_contract_sha256),
            ("result contract", self.result_receipt_contract_sha256),
        ):
            _require_sha256(value, name=name)
        _require_key_id(self.authorization_key_id)
        _require_git_commit(self.code_commit_sha)
        if (
            len(
                {
                    self.implementation_author_identity_sha256,
                    self.independent_reviewer_identity_sha256,
                    self.authorization_operator_identity_sha256,
                }
            )
            != 3
        ):
            raise ReferenceMinimizationValidationAuthorizationError(
                "authorization verification identities must be pairwise distinct"
            )
        if not self.dependency_artifact_sha256_rows:
            raise ReferenceMinimizationValidationAuthorizationError(
                "authorization verification dependency rows must be non-empty"
            )
        normalized = _dependency_rows(dict(self.dependency_artifact_sha256_rows))
        if tuple((row["artifact_id"], row["sha256"]) for row in normalized) != (
            self.dependency_artifact_sha256_rows
        ):
            raise ReferenceMinimizationValidationAuthorizationError(
                "authorization verification dependency rows must be sorted and unique"
            )
        issued = _parse_utc(self.issued_at_utc, name="authorization issued_at_utc")
        expires = _parse_utc(self.expires_at_utc, name="authorization expires_at_utc")
        if expires <= issued:
            raise ReferenceMinimizationValidationAuthorizationError(
                "authorization verification expiry must follow issue time"
            )
        if not self.receipt_authorization_verified or not (
            self.eligible_for_atomic_execution_reservation
        ):
            raise ReferenceMinimizationValidationAuthorizationError(
                "authorization verification must retain receipt eligibility"
            )
        if (
            self.validation_execution_authorized
            or self.parameter_fitting_proposal_authorized
            or self.parameter_fitting_authorized
        ):
            raise ReferenceMinimizationValidationAuthorizationError(
                "receipt verification alone cannot open execution or fitting gates"
            )
        if not self.blockers:
            raise ReferenceMinimizationValidationAuthorizationError(
                "receipt verification must retain downstream blockers"
            )


def _verify_review(
    source: str | bytes | Mapping[str, Any],
    *,
    trusted_reviewer_keys: Mapping[str, MinimizationScientificReviewerTrustAnchor],
    expected_implementation_author_identity_sha256: str,
    checked_at: datetime,
) -> ReferenceMinimizationValidationReviewVerification:
    try:
        review = verify_signed_reference_minimization_validation_review_attestation(
            source,
            trusted_reviewer_keys=trusted_reviewer_keys,
            expected_implementation_author_identity_sha256=(
                expected_implementation_author_identity_sha256
            ),
            checked_at=checked_at,
        )
    except ReferenceMinimizationValidationReviewError as exc:
        raise ReferenceMinimizationValidationAuthorizationError(
            "authorization independent review verification failed"
        ) from exc
    if (
        not review.independent_scientific_review_verified
        or not review.implementation_author_separation_verified
        or review.contract_sha256
        != FROZEN_REFERENCE_MINIMIZATION_VALIDATION_REVIEW_CONTRACT_SHA256
        or review.artifact_binding_sha256
        != FROZEN_REFERENCE_MINIMIZATION_VALIDATION_ARTIFACT_BINDING_SHA256
    ):
        raise ReferenceMinimizationValidationAuthorizationError(
            "authorization independent review dependency drifted"
        )
    return review


def _receipt_projection(
    *,
    review: ReferenceMinimizationValidationReviewVerification,
    authorization_operator_identity_sha256: str,
    authorization_key_id: str,
    issued_at_utc: str,
    expires_at_utc: str,
    authorization_nonce_sha256: str,
    code_commit_sha: str,
    runner_source_sha256: str,
    dependency_artifact_sha256_rows: Mapping[str, str],
) -> dict[str, Any]:
    contract = reference_minimization_validation_authorization_contract_document()
    return {
        "schema_id": REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_RECEIPT_SCHEMA_ID,
        "contract_sha256": contract["contract_sha256"],
        "artifact_binding_sha256": FROZEN_REFERENCE_MINIMIZATION_VALIDATION_ARTIFACT_BINDING_SHA256,
        "review_contract_sha256": FROZEN_REFERENCE_MINIMIZATION_VALIDATION_REVIEW_CONTRACT_SHA256,
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
            authorization_nonce_sha256, name="authorization nonce"
        ),
        "code_commit_sha": _require_git_commit(code_commit_sha),
        "runner_source_sha256": _require_sha256(
            runner_source_sha256, name="validation runner source"
        ),
        "execution_environment_contract_sha256": FROZEN_REFERENCE_MINIMIZATION_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256,
        "result_receipt_contract_sha256": FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256,
        "dependency_artifact_sha256_rows": _dependency_rows(
            dependency_artifact_sha256_rows
        ),
        "authorization_scope": {
            "lane": "synthetic_minimization_implementation_mathematics_only",
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


def build_signed_reference_minimization_validation_authorization_receipt(
    *,
    review_attestation: str | bytes | Mapping[str, Any],
    trusted_reviewer_keys: Mapping[str, MinimizationScientificReviewerTrustAnchor],
    expected_implementation_author_identity_sha256: str,
    authorization_operator_identity_sha256: str,
    authorization_key_id: str,
    signing_key: bytes | str,
    issued_at: datetime,
    expires_at: datetime,
    authorization_nonce_sha256: str,
    code_commit_sha: str,
    runner_source_sha256: str,
    dependency_artifact_sha256_rows: Mapping[str, str],
) -> dict[str, Any]:
    """Build a testable signed receipt without persisting key or receipt."""

    review = _verify_review(
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
        dependency_artifact_sha256_rows=dependency_artifact_sha256_rows,
    )
    payload = dict(projection)
    payload["receipt_sha256"] = _sha256(projection)
    key = _require_key(signing_key, name="authorization signing key")
    try:
        signature_value = sign_ed25519(_canonical_bytes(payload), key)
    except ReferenceMinimizationValidationEd25519Error as exc:
        raise ReferenceMinimizationValidationAuthorizationError(
            "authorization receipt Ed25519 signing failed"
        ) from exc
    payload["signature"] = {
        "algorithm": REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_SIGNATURE_ALGORITHM,
        "key_id": _require_key_id(authorization_key_id),
        "value": signature_value,
    }
    try:
        public_key = ed25519_public_key_bytes(key)
        verify_signed_reference_minimization_validation_authorization_receipt(
            payload,
            review_attestation=review_attestation,
            trusted_reviewer_keys=trusted_reviewer_keys,
            expected_implementation_author_identity_sha256=(
                expected_implementation_author_identity_sha256
            ),
            trusted_operator_keys={
                authorization_key_id: MinimizationAuthorizationOperatorTrustAnchor(
                    authorization_operator_identity_sha256,
                    public_key,
                )
            },
            checked_at=issued_at,
            expected_code_commit_sha=code_commit_sha,
            expected_runner_source_sha256=runner_source_sha256,
            expected_dependency_artifact_sha256_rows=(dependency_artifact_sha256_rows),
        )
    except ReferenceMinimizationValidationAuthorizationError:
        raise
    except ReferenceMinimizationValidationEd25519Error as exc:
        raise ReferenceMinimizationValidationAuthorizationError(
            "authorization receipt self-verification failed"
        ) from exc
    return payload


def _load_receipt(source: str | bytes | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(source, Mapping):
        return dict(source)
    raw = source.encode("utf-8") if isinstance(source, str) else source
    if not isinstance(raw, bytes):
        raise ReferenceMinimizationValidationAuthorizationError(
            "authorization receipt must be a mapping, string, or bytes"
        )

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ReferenceMinimizationValidationAuthorizationError(
                    "authorization receipt contains a duplicate JSON key"
                )
            result[key] = value
        return result

    try:
        loaded = json.loads(
            raw.decode("utf-8"), object_pairs_hook=reject_duplicate_keys
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReferenceMinimizationValidationAuthorizationError(
            "authorization receipt must be UTF-8 JSON"
        ) from exc
    if not isinstance(loaded, dict):
        raise ReferenceMinimizationValidationAuthorizationError(
            "authorization receipt root must be an object"
        )
    return loaded


def verify_signed_reference_minimization_validation_authorization_receipt(
    source: str | bytes | Mapping[str, Any],
    *,
    review_attestation: str | bytes | Mapping[str, Any],
    trusted_reviewer_keys: Mapping[str, MinimizationScientificReviewerTrustAnchor],
    expected_implementation_author_identity_sha256: str,
    trusted_operator_keys: Mapping[str, MinimizationAuthorizationOperatorTrustAnchor],
    checked_at: datetime,
    expected_code_commit_sha: str,
    expected_runner_source_sha256: str,
    expected_dependency_artifact_sha256_rows: Mapping[str, str],
    revoked_receipt_sha256s: Sequence[str] = (),
    revoked_review_attestation_sha256s: Sequence[str] = (),
    consumed_nonce_sha256s: Sequence[str] = (),
) -> ReferenceMinimizationValidationAuthorizationVerification:
    """Verify receipt eligibility without opening or consuming the run gate."""

    checked = _parse_utc(
        _format_utc(checked_at, name="authorization checked_at"),
        name="authorization checked_at",
    )
    review = _verify_review(
        review_attestation,
        trusted_reviewer_keys=trusted_reviewer_keys,
        expected_implementation_author_identity_sha256=(
            expected_implementation_author_identity_sha256
        ),
        checked_at=checked_at,
    )
    payload = _load_receipt(source)
    signature = payload.pop("signature", None)
    if not isinstance(signature, Mapping) or set(signature) != {
        "algorithm",
        "key_id",
        "value",
    }:
        raise ReferenceMinimizationValidationAuthorizationError(
            "authorization receipt signature fields are invalid"
        )
    if (
        signature.get("algorithm")
        != REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_SIGNATURE_ALGORITHM
    ):
        raise ReferenceMinimizationValidationAuthorizationError(
            "authorization receipt signature algorithm is unsupported"
        )
    key_id = _require_key_id(signature.get("key_id"))
    if key_id not in trusted_operator_keys:
        raise ReferenceMinimizationValidationAuthorizationError(
            "authorization operator key id is not trusted"
        )
    anchor = trusted_operator_keys[key_id]
    if not isinstance(anchor, MinimizationAuthorizationOperatorTrustAnchor):
        raise ReferenceMinimizationValidationAuthorizationError(
            "trusted authorization operator entry has an invalid type"
        )
    try:
        signature_verified = verify_ed25519(
            _canonical_bytes(payload), signature.get("value"), anchor.verification_key
        )
    except ReferenceMinimizationValidationEd25519Error as exc:
        raise ReferenceMinimizationValidationAuthorizationError(
            "authorization receipt Ed25519 verifier is unavailable"
        ) from exc
    if not signature_verified:
        raise ReferenceMinimizationValidationAuthorizationError(
            "authorization receipt signature verification failed"
        )
    receipt_sha256 = payload.pop("receipt_sha256", None)
    if receipt_sha256 != _sha256(payload):
        raise ReferenceMinimizationValidationAuthorizationError(
            "authorization receipt SHA-256 verification failed"
        )
    receipt_sha256 = _require_sha256(receipt_sha256, name="authorization receipt")
    if receipt_sha256 in {
        _require_sha256(value, name="revoked authorization receipt")
        for value in revoked_receipt_sha256s
    }:
        raise ReferenceMinimizationValidationAuthorizationError(
            "authorization receipt is externally revoked"
        )
    if review.attestation_sha256 in {
        _require_sha256(value, name="revoked review attestation")
        for value in revoked_review_attestation_sha256s
    }:
        raise ReferenceMinimizationValidationAuthorizationError(
            "authorization review attestation is externally revoked"
        )
    operator = _require_sha256(
        payload.get("authorization_operator_identity_sha256"),
        name="authorization operator identity",
    )
    if operator != anchor.operator_identity_sha256:
        raise ReferenceMinimizationValidationAuthorizationError(
            "authorization operator identity does not match the trusted key"
        )
    if operator in {
        review.implementation_author_identity_sha256,
        review.independent_reviewer_identity_sha256,
    }:
        raise ReferenceMinimizationValidationAuthorizationError(
            "authorization operator must differ from author and reviewer"
        )
    if payload.get("authorization_key_id") != key_id:
        raise ReferenceMinimizationValidationAuthorizationError(
            "authorization operator key id is cross-wired"
        )
    issued = _parse_utc(
        payload.get("issued_at_utc"), name="authorization issued_at_utc"
    )
    expires = _parse_utc(
        payload.get("expires_at_utc"), name="authorization expires_at_utc"
    )
    review_start = _parse_utc(
        review.reviewed_at_utc, name="authorization review reviewed_at_utc"
    )
    review_expires = _parse_utc(
        review.expires_at_utc, name="authorization review expires_at_utc"
    )
    if expires <= issued:
        raise ReferenceMinimizationValidationAuthorizationError(
            "authorization receipt expiry must follow issue time"
        )
    if expires - issued > REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_MAX_VALIDITY:
        raise ReferenceMinimizationValidationAuthorizationError(
            "authorization receipt validity exceeds the frozen maximum"
        )
    if issued < review_start:
        raise ReferenceMinimizationValidationAuthorizationError(
            "authorization receipt predates the independent review"
        )
    if expires > review_expires:
        raise ReferenceMinimizationValidationAuthorizationError(
            "authorization receipt outlives the independent review"
        )
    if checked < issued:
        raise ReferenceMinimizationValidationAuthorizationError(
            "authorization receipt is not yet valid"
        )
    if checked >= expires:
        raise ReferenceMinimizationValidationAuthorizationError(
            "authorization receipt is expired"
        )
    nonce = _require_sha256(
        payload.get("authorization_nonce_sha256"), name="authorization nonce"
    )
    if nonce in {
        _require_sha256(value, name="consumed authorization nonce")
        for value in consumed_nonce_sha256s
    }:
        raise ReferenceMinimizationValidationAuthorizationError(
            "authorization nonce was already consumed"
        )
    expected_projection = _receipt_projection(
        review=review,
        authorization_operator_identity_sha256=operator,
        authorization_key_id=key_id,
        issued_at_utc=payload["issued_at_utc"],
        expires_at_utc=payload["expires_at_utc"],
        authorization_nonce_sha256=nonce,
        code_commit_sha=_require_git_commit(expected_code_commit_sha),
        runner_source_sha256=_require_sha256(
            expected_runner_source_sha256,
            name="expected validation runner source",
        ),
        dependency_artifact_sha256_rows=expected_dependency_artifact_sha256_rows,
    )
    if payload != expected_projection:
        raise ReferenceMinimizationValidationAuthorizationError(
            "authorization receipt fields do not match the frozen schema or expected dependencies"
        )
    return ReferenceMinimizationValidationAuthorizationVerification(
        receipt_sha256=receipt_sha256,
        review_attestation_sha256=review.attestation_sha256,
        implementation_author_identity_sha256=review.implementation_author_identity_sha256,
        independent_reviewer_identity_sha256=review.independent_reviewer_identity_sha256,
        authorization_operator_identity_sha256=operator,
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


def reference_minimization_validation_authorization_contract_decision() -> dict[
    str, Any
]:
    """Return the closed decision; no operator key or receipt is bundled."""

    contract = reference_minimization_validation_authorization_contract_document()
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
    "FROZEN_REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_CONTRACT_SHA256",
    "REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_CONTRACT_ID",
    "REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_CONTRACT_SCHEMA_ID",
    "REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_CONTRACT_VERSION",
    "REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_MAX_VALIDITY",
    "REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_RECEIPT_SCHEMA_ID",
    "REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_SIGNATURE_ALGORITHM",
    "MinimizationAuthorizationOperatorTrustAnchor",
    "ReferenceMinimizationValidationAuthorizationError",
    "ReferenceMinimizationValidationAuthorizationVerification",
    "build_signed_reference_minimization_validation_authorization_receipt",
    "reference_minimization_validation_authorization_contract_decision",
    "reference_minimization_validation_authorization_contract_document",
    "require_reference_minimization_validation_authorization_contract_document",
    "verify_signed_reference_minimization_validation_authorization_receipt",
]
