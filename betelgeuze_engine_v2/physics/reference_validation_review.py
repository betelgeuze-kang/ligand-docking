"""Independent-review attestation contract for CPU validation artifacts.

The module freezes the shape and verification rules for a future independent
scientific review.  It does not ship a review attestation, choose a trusted
reviewer, authorize validation execution, collect results, or promote any
scientific, fitting, benchmark, product, or customer claim.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from typing import Any, Mapping, Sequence

from .reference_validation_artifact_binding import (
    FROZEN_INDEPENDENT_ANALYTIC_ORACLE_SOURCE_SHA256,
    FROZEN_REFERENCE_FORCEFIELD_SOURCE_SHA256,
    FROZEN_REFERENCE_VALIDATION_ARTIFACT_BINDING_SHA256,
    FROZEN_REFERENCE_VALIDATION_MATERIALIZER_SOURCE_SHA256,
    reference_validation_artifact_binding_document,
)


REFERENCE_VALIDATION_REVIEW_CONTRACT_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_validation_review_contract/1.0.0"
)
REFERENCE_VALIDATION_REVIEW_ATTESTATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_validation_review_attestation/1.0.0"
)
REFERENCE_VALIDATION_REVIEW_CONTRACT_ID = (
    "cpu_reference_validation_independent_review_contract/1.0.0"
)
REFERENCE_VALIDATION_REVIEW_CONTRACT_VERSION = "1.0.0"
REFERENCE_VALIDATION_REVIEW_CONTRACT_FROZEN_AT_UTC = "2026-07-17T04:31:00Z"
REFERENCE_VALIDATION_REVIEW_SIGNATURE_ALGORITHM = "hmac-sha256"
REFERENCE_VALIDATION_REVIEW_MAX_VALIDITY = timedelta(days=30)

FROZEN_REFERENCE_VALIDATION_REVIEW_CONTRACT_SHA256 = (
    "37ca9f550486febc73e36dc36a113e00042d87de79b14bf8033fbbfc1dcbf104"
)

_REQUIRED_REVIEW_CHECK_IDS = (
    "fixture_materialization_identity_and_case_coverage_reviewed",
    "oracle_scalar_equations_match_declared_h5_equations",
    "oracle_force_derivatives_reviewed_independently",
    "oracle_import_and_implementation_separation_reviewed",
    "failure_and_singularity_semantics_reviewed",
    "thresholds_and_invariance_scope_reviewed",
    "nonpromotion_and_synthetic_parameter_limitations_acknowledged",
)
_REQUIRED_LIMITATION_IDS = (
    "synthetic_fixture_values_are_not_reviewed_runtime_parameter_values",
    "contract_review_is_not_scientific_force_field_validation",
    "contract_review_does_not_establish_chemical_applicability",
    "contract_review_does_not_authorize_validation_execution",
    "contract_review_does_not_authorize_parameter_fitting",
)
_CLOSED_GATE_BLOCKERS = (
    "signed_independent_scientific_review_attestation_missing",
    "trusted_independent_scientific_reviewer_key_not_provided",
    "implementation_author_and_independent_reviewer_separation_not_attested",
    "signed_execution_authorization_receipt_schema_not_frozen",
    "signed_execution_authorization_receipt_missing",
    "validation_execution_not_authorized",
    "validation_results_not_collected",
    "parameter_fitting_not_authorized",
    "scientific_validation_missing",
    "product_integration_not_qualified",
)
_POST_REVIEW_BLOCKERS = (
    "signed_execution_authorization_receipt_schema_not_frozen",
    "signed_execution_authorization_receipt_missing",
    "validation_execution_not_authorized",
    "validation_results_not_collected",
    "parameter_fitting_not_authorized",
    "scientific_validation_missing",
    "product_integration_not_qualified",
)


class ReferenceValidationReviewError(ValueError):
    """The review contract, attestation, trust anchor, or signature is invalid."""


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
        raise ReferenceValidationReviewError("review artifact is not canonical JSON") from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ReferenceValidationReviewError(f"{name} must be a lowercase SHA-256")
    if any(character not in "0123456789abcdef" for character in value):
        raise ReferenceValidationReviewError(f"{name} must be a lowercase SHA-256")
    return value


def _parse_utc(value: object, *, name: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ReferenceValidationReviewError(f"{name} must be second-resolution UTC")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ReferenceValidationReviewError(f"{name} must be second-resolution UTC") from exc
    return parsed


def _format_utc(value: datetime, *, name: str) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ReferenceValidationReviewError(f"{name} must be timezone-aware")
    normalized = value.astimezone(timezone.utc)
    if normalized.microsecond:
        raise ReferenceValidationReviewError(f"{name} must use second resolution")
    return normalized.strftime("%Y-%m-%dT%H:%M:%SZ")


def _require_key(value: bytes | str, *, name: str) -> bytes:
    if isinstance(value, str):
        key = value.encode("utf-8")
    elif isinstance(value, bytes):
        key = value
    else:
        raise ReferenceValidationReviewError(f"{name} must be bytes or text")
    if len(key) < 32:
        raise ReferenceValidationReviewError(f"{name} must contain at least 32 bytes")
    return key


def _require_key_id(value: object) -> str:
    if not isinstance(value, str) or not value or len(value) > 128:
        raise ReferenceValidationReviewError("reviewer key id must contain 1 to 128 characters")
    if any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for character in value):
        raise ReferenceValidationReviewError("reviewer key id contains unsupported characters")
    return value


def _contract_projection() -> dict[str, Any]:
    binding = reference_validation_artifact_binding_document()
    return {
        "schema_id": REFERENCE_VALIDATION_REVIEW_CONTRACT_SCHEMA_ID,
        "contract_id": REFERENCE_VALIDATION_REVIEW_CONTRACT_ID,
        "contract_version": REFERENCE_VALIDATION_REVIEW_CONTRACT_VERSION,
        "frozen_at_utc": REFERENCE_VALIDATION_REVIEW_CONTRACT_FROZEN_AT_UTC,
        "purpose": {
            "scope": "future_independent_review_of_cpu_validation_implementation_artifacts",
            "contract_definition_only": True,
            "review_attestation_present": False,
            "authorizes_validation_execution": False,
            "authorizes_parameter_fitting_proposal": False,
            "authorizes_parameter_fitting": False,
        },
        "dependencies": {
            "artifact_binding_sha256": FROZEN_REFERENCE_VALIDATION_ARTIFACT_BINDING_SHA256,
            "protocol_sha256": binding["dependencies"]["protocol_sha256"],
            "h5_applicability_record_sha256": binding["dependencies"]["h5_applicability_record_sha256"],
            "materialization_manifest_sha256": binding["materializer"]["materialization_manifest_sha256"],
            "reference_evaluator_source_sha256": FROZEN_REFERENCE_FORCEFIELD_SOURCE_SHA256,
            "materializer_source_sha256": FROZEN_REFERENCE_VALIDATION_MATERIALIZER_SOURCE_SHA256,
            "oracle_source_sha256": FROZEN_INDEPENDENT_ANALYTIC_ORACLE_SOURCE_SHA256,
            "exact_dependency_match_required": True,
            "dependency_claim_status_inherited": False,
        },
        "identity_policy": {
            "implementation_author_identity_sha256_required": True,
            "independent_reviewer_identity_sha256_required": True,
            "implementation_author_and_reviewer_must_differ": True,
            "reviewer_key_id_required": True,
            "trusted_reviewer_key_supplied_out_of_band": True,
            "repository_does_not_choose_or_bundle_trusted_reviewer_keys": True,
            "organizational_independence_requires_external_governance_review": True,
        },
        "attestation_schema": {
            "schema_id": REFERENCE_VALIDATION_REVIEW_ATTESTATION_SCHEMA_ID,
            "signature_algorithm": REFERENCE_VALIDATION_REVIEW_SIGNATURE_ALGORITHM,
            "maximum_validity_seconds": int(REFERENCE_VALIDATION_REVIEW_MAX_VALIDITY.total_seconds()),
            "required_review_check_ids": list(_REQUIRED_REVIEW_CHECK_IDS),
            "required_limitation_ids": list(_REQUIRED_LIMITATION_IDS),
            "all_required_checks_must_be_accepted": True,
            "all_limitations_must_be_acknowledged": True,
            "review_recommendation": "eligible_for_separate_signed_synthetic_validation_authorization",
            "scientific_parameterized_force_field_recommendation_allowed": False,
            "parameter_fitting_recommendation_allowed": False,
            "superseded_or_revoked_attestation_allowed": False,
        },
        "authorization_gate": {
            "status": "closed",
            "independent_scientific_review_completed": False,
            "implementation_author_separation_attested": False,
            "validation_execution_authorized": False,
            "parameter_fitting_proposal_authorized": False,
            "parameter_fitting_authorized": False,
            "current_blockers": list(_CLOSED_GATE_BLOCKERS),
        },
        "claim_policy": {
            "review_contract_implemented": True,
            "independent_scientific_review_completed": False,
            "force_or_energy_validated": False,
            "scientific_applicability_established": False,
            "scientifically_validated": False,
            "benchmark_validated": False,
            "product_qualified": False,
            "customer_execution_enabled": False,
            "claim_safe": False,
        },
        "blockers": list(_CLOSED_GATE_BLOCKERS),
    }


def reference_validation_review_contract_document() -> dict[str, Any]:
    document = _contract_projection()
    document["contract_sha256"] = _sha256(document)
    if document["contract_sha256"] != FROZEN_REFERENCE_VALIDATION_REVIEW_CONTRACT_SHA256:
        raise ReferenceValidationReviewError("frozen validation review contract SHA-256 drifted")
    return document


def require_reference_validation_review_contract_document(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ReferenceValidationReviewError("review contract document must be a mapping")
    try:
        observed = json.loads(_canonical_bytes(dict(payload)).decode("ascii"))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ReferenceValidationReviewError("review contract document is invalid") from exc
    expected = reference_validation_review_contract_document()
    if observed != expected:
        raise ReferenceValidationReviewError("review contract document does not match the frozen record")
    return observed


@dataclass(frozen=True, slots=True)
class ScientificReviewerTrustAnchor:
    """Out-of-band reviewer identity and HMAC verification key."""

    reviewer_identity_sha256: str
    verification_key: bytes = field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "reviewer_identity_sha256",
            _require_sha256(self.reviewer_identity_sha256, name="trusted reviewer identity"),
        )
        object.__setattr__(
            self,
            "verification_key",
            _require_key(self.verification_key, name="trusted reviewer verification key"),
        )


@dataclass(frozen=True, slots=True)
class ReferenceValidationReviewVerification:
    contract_sha256: str
    artifact_binding_sha256: str
    attestation_sha256: str
    implementation_author_identity_sha256: str
    independent_reviewer_identity_sha256: str
    reviewer_key_id: str
    reviewed_at_utc: str
    expires_at_utc: str
    independent_scientific_review_verified: bool
    implementation_author_separation_verified: bool
    validation_execution_authorized: bool
    parameter_fitting_proposal_authorized: bool
    parameter_fitting_authorized: bool
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_sha256(self.contract_sha256, name="review contract")
        _require_sha256(self.artifact_binding_sha256, name="review artifact binding")
        _require_sha256(self.attestation_sha256, name="review attestation")
        author = _require_sha256(
            self.implementation_author_identity_sha256,
            name="review implementation author identity",
        )
        reviewer = _require_sha256(
            self.independent_reviewer_identity_sha256,
            name="review independent reviewer identity",
        )
        if author == reviewer:
            raise ReferenceValidationReviewError(
                "review verification author and reviewer identities must differ"
            )
        _require_key_id(self.reviewer_key_id)
        reviewed_at = _parse_utc(self.reviewed_at_utc, name="review verification reviewed_at_utc")
        expires_at = _parse_utc(self.expires_at_utc, name="review verification expires_at_utc")
        if expires_at <= reviewed_at:
            raise ReferenceValidationReviewError(
                "review verification expiry must follow review time"
            )
        if not self.independent_scientific_review_verified:
            raise ReferenceValidationReviewError("verified review decision must retain review verification")
        if not self.implementation_author_separation_verified:
            raise ReferenceValidationReviewError("verified review decision must retain author separation")
        if (
            self.validation_execution_authorized
            or self.parameter_fitting_proposal_authorized
            or self.parameter_fitting_authorized
        ):
            raise ReferenceValidationReviewError("review attestation alone cannot authorize execution or fitting")
        if not self.blockers:
            raise ReferenceValidationReviewError("review verification must retain downstream blockers")

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_sha256": self.contract_sha256,
            "artifact_binding_sha256": self.artifact_binding_sha256,
            "attestation_sha256": self.attestation_sha256,
            "implementation_author_identity_sha256": self.implementation_author_identity_sha256,
            "independent_reviewer_identity_sha256": self.independent_reviewer_identity_sha256,
            "reviewer_key_id": self.reviewer_key_id,
            "reviewed_at_utc": self.reviewed_at_utc,
            "expires_at_utc": self.expires_at_utc,
            "independent_scientific_review_verified": self.independent_scientific_review_verified,
            "implementation_author_separation_verified": self.implementation_author_separation_verified,
            "validation_execution_authorized": self.validation_execution_authorized,
            "parameter_fitting_proposal_authorized": self.parameter_fitting_proposal_authorized,
            "parameter_fitting_authorized": self.parameter_fitting_authorized,
            "blockers": list(self.blockers),
        }


def _attestation_projection(
    *,
    implementation_author_identity_sha256: str,
    independent_reviewer_identity_sha256: str,
    reviewer_key_id: str,
    reviewed_at_utc: str,
    expires_at_utc: str,
    nonce_sha256: str,
    accepted_check_ids: Sequence[str],
    acknowledged_limitation_ids: Sequence[str],
) -> dict[str, Any]:
    contract = reference_validation_review_contract_document()
    return {
        "schema_id": REFERENCE_VALIDATION_REVIEW_ATTESTATION_SCHEMA_ID,
        "contract_sha256": contract["contract_sha256"],
        "artifact_binding_sha256": FROZEN_REFERENCE_VALIDATION_ARTIFACT_BINDING_SHA256,
        "implementation_author_identity_sha256": _require_sha256(
            implementation_author_identity_sha256,
            name="implementation author identity",
        ),
        "independent_reviewer_identity_sha256": _require_sha256(
            independent_reviewer_identity_sha256,
            name="independent reviewer identity",
        ),
        "reviewer_key_id": _require_key_id(reviewer_key_id),
        "reviewed_at_utc": reviewed_at_utc,
        "expires_at_utc": expires_at_utc,
        "nonce_sha256": _require_sha256(nonce_sha256, name="review nonce"),
        "accepted_check_ids": list(accepted_check_ids),
        "acknowledged_limitation_ids": list(acknowledged_limitation_ids),
        "review_recommendation": "eligible_for_separate_signed_synthetic_validation_authorization",
        "scientific_parameterized_force_field_validation_recommended": False,
        "parameter_fitting_proposal_recommended": False,
        "parameter_fitting_recommended": False,
        "validation_execution_authorized": False,
        "scientifically_validated": False,
        "claim_safe": False,
        "superseded": False,
        "revoked": False,
    }


def build_signed_reference_validation_review_attestation(
    *,
    implementation_author_identity_sha256: str,
    independent_reviewer_identity_sha256: str,
    reviewer_key_id: str,
    signing_key: bytes | str,
    reviewed_at: datetime,
    expires_at: datetime,
    nonce_sha256: str,
    accepted_check_ids: Sequence[str] = _REQUIRED_REVIEW_CHECK_IDS,
    acknowledged_limitation_ids: Sequence[str] = _REQUIRED_LIMITATION_IDS,
) -> dict[str, Any]:
    """Build a signed external-review artifact without storing the secret key."""

    projection = _attestation_projection(
        implementation_author_identity_sha256=implementation_author_identity_sha256,
        independent_reviewer_identity_sha256=independent_reviewer_identity_sha256,
        reviewer_key_id=reviewer_key_id,
        reviewed_at_utc=_format_utc(reviewed_at, name="reviewed_at"),
        expires_at_utc=_format_utc(expires_at, name="expires_at"),
        nonce_sha256=nonce_sha256,
        accepted_check_ids=accepted_check_ids,
        acknowledged_limitation_ids=acknowledged_limitation_ids,
    )
    payload = dict(projection)
    payload["attestation_sha256"] = _sha256(projection)
    key = _require_key(signing_key, name="review signing key")
    payload["signature"] = {
        "algorithm": REFERENCE_VALIDATION_REVIEW_SIGNATURE_ALGORITHM,
        "key_id": _require_key_id(reviewer_key_id),
        "value": hmac.new(key, _canonical_bytes(payload), hashlib.sha256).hexdigest(),
    }
    return payload


def _load_attestation(source: str | bytes | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(source, Mapping):
        return dict(source)
    raw = source.encode("utf-8") if isinstance(source, str) else source
    if not isinstance(raw, bytes):
        raise ReferenceValidationReviewError("review attestation must be a mapping, string, or bytes")
    try:
        def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in pairs:
                if key in result:
                    raise ReferenceValidationReviewError(
                        "review attestation contains a duplicate JSON key"
                    )
                result[key] = value
            return result

        loaded = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReferenceValidationReviewError("review attestation must be UTF-8 JSON") from exc
    if not isinstance(loaded, dict):
        raise ReferenceValidationReviewError("review attestation root must be an object")
    return loaded


def verify_signed_reference_validation_review_attestation(
    source: str | bytes | Mapping[str, Any],
    *,
    trusted_reviewer_keys: Mapping[str, ScientificReviewerTrustAnchor],
    expected_implementation_author_identity_sha256: str,
    checked_at: datetime,
) -> ReferenceValidationReviewVerification:
    """Verify identity separation, exact dependencies, signature, and freshness.

    A successful review verification still cannot authorize execution.  A
    separately signed, non-expired authorization receipt remains mandatory.
    """

    expected_author = _require_sha256(
        expected_implementation_author_identity_sha256,
        name="expected implementation author identity",
    )
    checked_at_utc = _parse_utc(_format_utc(checked_at, name="checked_at"), name="checked_at")
    payload = _load_attestation(source)
    signature = payload.pop("signature", None)
    if not isinstance(signature, Mapping):
        raise ReferenceValidationReviewError("review attestation signature is missing")
    if set(signature) != {"algorithm", "key_id", "value"}:
        raise ReferenceValidationReviewError("review attestation signature fields are invalid")
    if signature.get("algorithm") != REFERENCE_VALIDATION_REVIEW_SIGNATURE_ALGORITHM:
        raise ReferenceValidationReviewError("review attestation signature algorithm is unsupported")
    key_id = _require_key_id(signature.get("key_id"))
    if key_id not in trusted_reviewer_keys:
        raise ReferenceValidationReviewError("reviewer key id is not trusted")
    anchor = trusted_reviewer_keys[key_id]
    if not isinstance(anchor, ScientificReviewerTrustAnchor):
        raise ReferenceValidationReviewError("trusted reviewer entry has an invalid type")
    expected_signature = hmac.new(
        anchor.verification_key,
        _canonical_bytes(payload),
        hashlib.sha256,
    ).hexdigest()
    signature_value = signature.get("value")
    if not isinstance(signature_value, str) or not hmac.compare_digest(signature_value, expected_signature):
        raise ReferenceValidationReviewError("review attestation signature verification failed")

    attestation_sha256 = payload.pop("attestation_sha256", None)
    if attestation_sha256 != _sha256(payload):
        raise ReferenceValidationReviewError("review attestation SHA-256 verification failed")
    if payload.get("schema_id") != REFERENCE_VALIDATION_REVIEW_ATTESTATION_SCHEMA_ID:
        raise ReferenceValidationReviewError("review attestation schema is unsupported")
    contract = reference_validation_review_contract_document()
    if payload.get("contract_sha256") != contract["contract_sha256"]:
        raise ReferenceValidationReviewError("review attestation contract identity drifted")
    if payload.get("artifact_binding_sha256") != FROZEN_REFERENCE_VALIDATION_ARTIFACT_BINDING_SHA256:
        raise ReferenceValidationReviewError("review attestation artifact binding drifted")
    if payload.get("implementation_author_identity_sha256") != expected_author:
        raise ReferenceValidationReviewError("review attestation implementation author identity drifted")
    reviewer_identity = _require_sha256(
        payload.get("independent_reviewer_identity_sha256"),
        name="independent reviewer identity",
    )
    if reviewer_identity != anchor.reviewer_identity_sha256:
        raise ReferenceValidationReviewError("reviewer identity does not match the trusted key")
    if reviewer_identity == expected_author:
        raise ReferenceValidationReviewError("implementation author and independent reviewer must differ")
    if payload.get("reviewer_key_id") != key_id:
        raise ReferenceValidationReviewError("reviewer key id is cross-wired")

    reviewed_at = _parse_utc(payload.get("reviewed_at_utc"), name="reviewed_at_utc")
    expires_at = _parse_utc(payload.get("expires_at_utc"), name="expires_at_utc")
    if expires_at <= reviewed_at:
        raise ReferenceValidationReviewError("review attestation expiry must follow review time")
    if expires_at - reviewed_at > REFERENCE_VALIDATION_REVIEW_MAX_VALIDITY:
        raise ReferenceValidationReviewError("review attestation validity exceeds the frozen maximum")
    if checked_at_utc < reviewed_at:
        raise ReferenceValidationReviewError("review attestation is not yet valid")
    if checked_at_utc >= expires_at:
        raise ReferenceValidationReviewError("review attestation is expired")

    expected_checks = list(_REQUIRED_REVIEW_CHECK_IDS)
    expected_limitations = list(_REQUIRED_LIMITATION_IDS)
    if payload.get("accepted_check_ids") != expected_checks:
        raise ReferenceValidationReviewError("review attestation check coverage is incomplete or reordered")
    if payload.get("acknowledged_limitation_ids") != expected_limitations:
        raise ReferenceValidationReviewError("review attestation limitations are incomplete or reordered")
    expected_projection = _attestation_projection(
        implementation_author_identity_sha256=expected_author,
        independent_reviewer_identity_sha256=reviewer_identity,
        reviewer_key_id=key_id,
        reviewed_at_utc=payload["reviewed_at_utc"],
        expires_at_utc=payload["expires_at_utc"],
        nonce_sha256=payload.get("nonce_sha256"),
        accepted_check_ids=expected_checks,
        acknowledged_limitation_ids=expected_limitations,
    )
    if payload != expected_projection:
        raise ReferenceValidationReviewError("review attestation fields do not match the frozen schema")
    return ReferenceValidationReviewVerification(
        contract_sha256=contract["contract_sha256"],
        artifact_binding_sha256=FROZEN_REFERENCE_VALIDATION_ARTIFACT_BINDING_SHA256,
        attestation_sha256=_require_sha256(attestation_sha256, name="review attestation"),
        implementation_author_identity_sha256=expected_author,
        independent_reviewer_identity_sha256=reviewer_identity,
        reviewer_key_id=key_id,
        reviewed_at_utc=payload["reviewed_at_utc"],
        expires_at_utc=payload["expires_at_utc"],
        independent_scientific_review_verified=True,
        implementation_author_separation_verified=True,
        validation_execution_authorized=False,
        parameter_fitting_proposal_authorized=False,
        parameter_fitting_authorized=False,
        blockers=_POST_REVIEW_BLOCKERS,
    )


def reference_validation_review_contract_authorization_decision() -> dict[str, Any]:
    """Return the current closed decision; no review attestation is bundled."""

    contract = reference_validation_review_contract_document()
    return {
        "contract_sha256": contract["contract_sha256"],
        "review_attestation_present": False,
        "independent_scientific_review_verified": False,
        "implementation_author_separation_verified": False,
        "validation_execution_authorized": False,
        "parameter_fitting_proposal_authorized": False,
        "parameter_fitting_authorized": False,
        "blockers": list(_CLOSED_GATE_BLOCKERS),
    }


__all__ = [
    "FROZEN_REFERENCE_VALIDATION_REVIEW_CONTRACT_SHA256",
    "REFERENCE_VALIDATION_REVIEW_ATTESTATION_SCHEMA_ID",
    "REFERENCE_VALIDATION_REVIEW_CONTRACT_ID",
    "REFERENCE_VALIDATION_REVIEW_CONTRACT_SCHEMA_ID",
    "REFERENCE_VALIDATION_REVIEW_CONTRACT_VERSION",
    "REFERENCE_VALIDATION_REVIEW_MAX_VALIDITY",
    "REFERENCE_VALIDATION_REVIEW_SIGNATURE_ALGORITHM",
    "ReferenceValidationReviewError",
    "ReferenceValidationReviewVerification",
    "ScientificReviewerTrustAnchor",
    "build_signed_reference_validation_review_attestation",
    "reference_validation_review_contract_authorization_decision",
    "reference_validation_review_contract_document",
    "require_reference_validation_review_contract_document",
    "verify_signed_reference_validation_review_attestation",
]
