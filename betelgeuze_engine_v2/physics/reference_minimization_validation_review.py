"""Independent-review attestation contract for CPU minimization artifacts.

The module freezes the shape and verification rules for a future independent
scientific review.  It does not ship a review attestation, choose a trusted
reviewer, authorize validation execution, collect results, or promote any
scientific, fitting, benchmark, product, or customer claim.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any, Mapping, Sequence

from .reference_minimization_validation_ed25519 import (
    ReferenceMinimizationValidationEd25519Error,
    sign_ed25519,
    verify_ed25519,
)

from .reference_minimization_validation_artifact_binding import (
    FROZEN_CPU_MINIMIZATION_VALIDATION_MATERIALIZATION_MANIFEST_SHA256,
    FROZEN_CPU_MINIMIZATION_VALIDATION_MATERIALIZER_SOURCE_SHA256,
    FROZEN_INDEPENDENT_ANALYTIC_ORACLE_SOURCE_SHA256,
    FROZEN_INDEPENDENT_MINIMIZATION_ORACLE_SOURCE_SHA256,
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_ARTIFACT_BINDING_SHA256,
    reference_minimization_validation_artifact_binding_document,
)


REFERENCE_MINIMIZATION_VALIDATION_REVIEW_CONTRACT_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_validation_review_contract/5.0.0"
)
REFERENCE_MINIMIZATION_VALIDATION_REVIEW_ATTESTATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_validation_review_attestation/5.0.0"
)
REFERENCE_MINIMIZATION_VALIDATION_REVIEW_CONTRACT_ID = (
    "cpu_reference_minimization_validation_independent_review_contract/5.0.0"
)
REFERENCE_MINIMIZATION_VALIDATION_REVIEW_CONTRACT_VERSION = "5.0.0"
REFERENCE_MINIMIZATION_VALIDATION_REVIEW_CONTRACT_FROZEN_AT_UTC = "2026-07-24T00:00:00Z"
REFERENCE_MINIMIZATION_VALIDATION_REVIEW_SIGNATURE_ALGORITHM = "ed25519"
REFERENCE_MINIMIZATION_VALIDATION_REVIEW_MAX_VALIDITY = timedelta(days=30)

FROZEN_REFERENCE_MINIMIZATION_VALIDATION_REVIEW_CONTRACT_SHA256 = (
    "1ee6e03aa0918e77b8afd105103f480b6342f16a40850422e3d2d4b83eb0a35e"
)
FROZEN_LEGACY_REFERENCE_MINIMIZATION_VALIDATION_REVIEW_CONTRACT_SHA256_V4 = (
    "2d5d04c46a10e29ba4918a1cea584891da84060a5b86d3b526c5cf6bde790dcd"
)
FROZEN_LEGACY_REFERENCE_MINIMIZATION_VALIDATION_REVIEW_CONTRACT_SHA256_V3 = (
    "9aee9223b5842f1ddbc2509079fd417958edb24b11262398b74853c9fe44d8a7"
)
FROZEN_LEGACY_REFERENCE_MINIMIZATION_VALIDATION_REVIEW_CONTRACT_SHA256_V2 = (
    "324b9feebe12ba0f4056686a36fb9c62104604fb0be7c0e508a630105d8f448a"
)

_REQUIRED_REVIEW_CHECK_IDS = (
    "fixture_materialization_identity_and_case_coverage_reviewed",
    "independent_reference_algorithm_and_equations_reviewed",
    "constraint_position_projection_reviewed",
    "constraint_tangent_force_projection_reviewed",
    "fixed_born_energy_and_force_equations_reviewed",
    "bounded_backtracking_and_failure_ledger_reviewed",
    "complete_coordinate_trace_retention_and_identity_reviewed",
    "checkpoint_restart_identity_and_reproducibility_reviewed",
    "negative_case_error_mapping_reviewed",
    "oracle_import_and_operational_implementation_separation_reviewed",
    "predeclared_metric_thresholds_and_case_denominator_reviewed",
    "nonpromotion_and_synthetic_parameter_limitations_acknowledged",
)
_REQUIRED_LIMITATION_IDS = (
    "synthetic_fixture_values_are_not_reviewed_runtime_parameter_values",
    "contract_review_is_not_scientific_minimization_validation",
    "test_only_endpoint_comparisons_are_not_validation_results",
    "contract_review_does_not_establish_chemical_applicability",
    "contract_review_does_not_authorize_validation_execution",
    "contract_review_does_not_authorize_parameter_fitting",
)
_CLOSED_GATE_BLOCKERS = (
    "signed_independent_scientific_review_attestation_missing",
    "trusted_independent_scientific_reviewer_key_not_provided",
    "implementation_author_and_independent_reviewer_separation_not_attested",
    "signed_execution_authorization_receipt_missing",
    "validation_execution_not_authorized",
    "validation_results_not_collected",
    "parameter_fitting_not_authorized",
    "scientific_validation_missing",
    "product_integration_not_qualified",
)
_POST_REVIEW_BLOCKERS = (
    "signed_execution_authorization_receipt_missing",
    "validation_execution_not_authorized",
    "validation_results_not_collected",
    "parameter_fitting_not_authorized",
    "scientific_validation_missing",
    "product_integration_not_qualified",
)


class ReferenceMinimizationValidationReviewError(ValueError):
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
        raise ReferenceMinimizationValidationReviewError(
            "review artifact is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ReferenceMinimizationValidationReviewError(
            f"{name} must be a lowercase SHA-256"
        )
    if any(character not in "0123456789abcdef" for character in value):
        raise ReferenceMinimizationValidationReviewError(
            f"{name} must be a lowercase SHA-256"
        )
    return value


def _parse_utc(value: object, *, name: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ReferenceMinimizationValidationReviewError(
            f"{name} must be second-resolution UTC"
        )
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise ReferenceMinimizationValidationReviewError(
            f"{name} must be second-resolution UTC"
        ) from exc
    return parsed


def _format_utc(value: datetime, *, name: str) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ReferenceMinimizationValidationReviewError(
            f"{name} must be timezone-aware"
        )
    normalized = value.astimezone(timezone.utc)
    if normalized.microsecond:
        raise ReferenceMinimizationValidationReviewError(
            f"{name} must use second resolution"
        )
    return normalized.strftime("%Y-%m-%dT%H:%M:%SZ")


def _require_key(value: bytes | str, *, name: str) -> bytes:
    if isinstance(value, str):
        key = value.encode("utf-8")
    elif isinstance(value, bytes):
        key = value
    else:
        raise ReferenceMinimizationValidationReviewError(
            f"{name} must be bytes or text"
        )
    if len(key) != 32:
        raise ReferenceMinimizationValidationReviewError(
            f"{name} must contain exactly 32 bytes"
        )
    return key


def _require_key_id(value: object) -> str:
    if not isinstance(value, str) or not value or len(value) > 128:
        raise ReferenceMinimizationValidationReviewError(
            "reviewer key id must contain 1 to 128 characters"
        )
    if any(
        character
        not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
        for character in value
    ):
        raise ReferenceMinimizationValidationReviewError(
            "reviewer key id contains unsupported characters"
        )
    return value


def _contract_projection() -> dict[str, Any]:
    binding = reference_minimization_validation_artifact_binding_document()
    return {
        "schema_id": REFERENCE_MINIMIZATION_VALIDATION_REVIEW_CONTRACT_SCHEMA_ID,
        "contract_id": REFERENCE_MINIMIZATION_VALIDATION_REVIEW_CONTRACT_ID,
        "contract_version": REFERENCE_MINIMIZATION_VALIDATION_REVIEW_CONTRACT_VERSION,
        "frozen_at_utc": REFERENCE_MINIMIZATION_VALIDATION_REVIEW_CONTRACT_FROZEN_AT_UTC,
        "superseded_contract_sha256": (
            FROZEN_LEGACY_REFERENCE_MINIMIZATION_VALIDATION_REVIEW_CONTRACT_SHA256_V4
        ),
        "refreeze_reason": (
            "binds_compact_default_capacity_protocol_and_refrozen_artifact_binding"
        ),
        "purpose": {
            "scope": "future_independent_review_of_cpu_minimization_validation_implementation_artifacts",
            "contract_definition_only": True,
            "review_attestation_present": False,
            "authorizes_validation_execution": False,
            "authorizes_parameter_fitting_proposal": False,
            "authorizes_parameter_fitting": False,
        },
        "dependencies": {
            "artifact_binding_sha256": FROZEN_REFERENCE_MINIMIZATION_VALIDATION_ARTIFACT_BINDING_SHA256,
            "protocol_sha256": binding["dependencies"]["protocol_sha256"],
            "fixture_manifest_sha256": binding["dependencies"][
                "fixture_manifest_sha256"
            ],
            "case_manifest_sha256": binding["dependencies"]["case_manifest_sha256"],
            "materialization_manifest_sha256": FROZEN_CPU_MINIMIZATION_VALIDATION_MATERIALIZATION_MANIFEST_SHA256,
            "materializer_source_sha256": FROZEN_CPU_MINIMIZATION_VALIDATION_MATERIALIZER_SOURCE_SHA256,
            "analytic_oracle_source_sha256": FROZEN_INDEPENDENT_ANALYTIC_ORACLE_SOURCE_SHA256,
            "minimization_oracle_source_sha256": FROZEN_INDEPENDENT_MINIMIZATION_ORACLE_SOURCE_SHA256,
            "exact_dependency_match_required": True,
            "dependency_claim_status_inherited": False,
        },
        "identity_policy": {
            "implementation_author_identity_sha256_required": True,
            "independent_reviewer_identity_sha256_required": True,
            "implementation_author_and_reviewer_must_differ": True,
            "reviewer_key_id_required": True,
            "trusted_reviewer_key_supplied_out_of_band": True,
            "verifier_trust_anchor_contains_public_key_only": True,
            "private_signing_key_remains_external_to_verifier": True,
            "repository_does_not_choose_or_bundle_trusted_reviewer_keys": True,
            "organizational_independence_requires_external_governance_review": True,
        },
        "attestation_schema": {
            "schema_id": REFERENCE_MINIMIZATION_VALIDATION_REVIEW_ATTESTATION_SCHEMA_ID,
            "signature_algorithm": REFERENCE_MINIMIZATION_VALIDATION_REVIEW_SIGNATURE_ALGORITHM,
            "maximum_validity_seconds": int(
                REFERENCE_MINIMIZATION_VALIDATION_REVIEW_MAX_VALIDITY.total_seconds()
            ),
            "required_review_check_ids": list(_REQUIRED_REVIEW_CHECK_IDS),
            "required_limitation_ids": list(_REQUIRED_LIMITATION_IDS),
            "all_required_checks_must_be_accepted": True,
            "all_limitations_must_be_acknowledged": True,
            "review_recommendation": "eligible_for_separate_signed_synthetic_minimization_validation_authorization",
            "scientific_minimization_validation_recommendation_allowed": False,
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


def reference_minimization_validation_review_contract_document() -> dict[str, Any]:
    document = _contract_projection()
    document["contract_sha256"] = _sha256(document)
    if (
        document["contract_sha256"]
        != FROZEN_REFERENCE_MINIMIZATION_VALIDATION_REVIEW_CONTRACT_SHA256
    ):
        raise ReferenceMinimizationValidationReviewError(
            "frozen validation review contract SHA-256 drifted"
        )
    return document


def require_reference_minimization_validation_review_contract_document(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ReferenceMinimizationValidationReviewError(
            "review contract document must be a mapping"
        )
    try:
        observed = json.loads(_canonical_bytes(dict(payload)).decode("ascii"))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ReferenceMinimizationValidationReviewError(
            "review contract document is invalid"
        ) from exc
    expected = reference_minimization_validation_review_contract_document()
    if observed != expected:
        raise ReferenceMinimizationValidationReviewError(
            "review contract document does not match the frozen record"
        )
    return observed


@dataclass(frozen=True, slots=True)
class MinimizationScientificReviewerTrustAnchor:
    """Out-of-band reviewer identity and Ed25519 public key."""

    reviewer_identity_sha256: str
    verification_key: bytes = field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "reviewer_identity_sha256",
            _require_sha256(
                self.reviewer_identity_sha256, name="trusted reviewer identity"
            ),
        )
        object.__setattr__(
            self,
            "verification_key",
            _require_key(
                self.verification_key, name="trusted reviewer verification key"
            ),
        )


@dataclass(frozen=True, slots=True)
class ReferenceMinimizationValidationReviewVerification:
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
            raise ReferenceMinimizationValidationReviewError(
                "review verification author and reviewer identities must differ"
            )
        _require_key_id(self.reviewer_key_id)
        reviewed_at = _parse_utc(
            self.reviewed_at_utc, name="review verification reviewed_at_utc"
        )
        expires_at = _parse_utc(
            self.expires_at_utc, name="review verification expires_at_utc"
        )
        if expires_at <= reviewed_at:
            raise ReferenceMinimizationValidationReviewError(
                "review verification expiry must follow review time"
            )
        if not self.independent_scientific_review_verified:
            raise ReferenceMinimizationValidationReviewError(
                "verified review decision must retain review verification"
            )
        if not self.implementation_author_separation_verified:
            raise ReferenceMinimizationValidationReviewError(
                "verified review decision must retain author separation"
            )
        if (
            self.validation_execution_authorized
            or self.parameter_fitting_proposal_authorized
            or self.parameter_fitting_authorized
        ):
            raise ReferenceMinimizationValidationReviewError(
                "review attestation alone cannot authorize execution or fitting"
            )
        if not self.blockers:
            raise ReferenceMinimizationValidationReviewError(
                "review verification must retain downstream blockers"
            )

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
    contract = reference_minimization_validation_review_contract_document()
    return {
        "schema_id": REFERENCE_MINIMIZATION_VALIDATION_REVIEW_ATTESTATION_SCHEMA_ID,
        "contract_sha256": contract["contract_sha256"],
        "artifact_binding_sha256": FROZEN_REFERENCE_MINIMIZATION_VALIDATION_ARTIFACT_BINDING_SHA256,
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
        "review_recommendation": "eligible_for_separate_signed_synthetic_minimization_validation_authorization",
        "scientific_minimization_validation_recommended": False,
        "parameter_fitting_proposal_recommended": False,
        "parameter_fitting_recommended": False,
        "validation_execution_authorized": False,
        "scientifically_validated": False,
        "claim_safe": False,
        "superseded": False,
        "revoked": False,
    }


def build_signed_reference_minimization_validation_review_attestation(
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
    try:
        signature = sign_ed25519(_canonical_bytes(payload), key)
    except ReferenceMinimizationValidationEd25519Error as exc:
        raise ReferenceMinimizationValidationReviewError(
            "review attestation Ed25519 signing failed"
        ) from exc
    payload["signature"] = {
        "algorithm": REFERENCE_MINIMIZATION_VALIDATION_REVIEW_SIGNATURE_ALGORITHM,
        "key_id": _require_key_id(reviewer_key_id),
        "value": signature,
    }
    return payload


def _load_attestation(source: str | bytes | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(source, Mapping):
        return dict(source)
    raw = source.encode("utf-8") if isinstance(source, str) else source
    if not isinstance(raw, bytes):
        raise ReferenceMinimizationValidationReviewError(
            "review attestation must be a mapping, string, or bytes"
        )
    try:

        def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in pairs:
                if key in result:
                    raise ReferenceMinimizationValidationReviewError(
                        "review attestation contains a duplicate JSON key"
                    )
                result[key] = value
            return result

        loaded = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReferenceMinimizationValidationReviewError(
            "review attestation must be UTF-8 JSON"
        ) from exc
    if not isinstance(loaded, dict):
        raise ReferenceMinimizationValidationReviewError(
            "review attestation root must be an object"
        )
    return loaded


def verify_signed_reference_minimization_validation_review_attestation(
    source: str | bytes | Mapping[str, Any],
    *,
    trusted_reviewer_keys: Mapping[str, MinimizationScientificReviewerTrustAnchor],
    expected_implementation_author_identity_sha256: str,
    checked_at: datetime,
) -> ReferenceMinimizationValidationReviewVerification:
    """Verify identity separation, exact dependencies, signature, and freshness.

    A successful review verification still cannot authorize execution.  A
    separately signed, non-expired authorization receipt remains mandatory.
    """

    expected_author = _require_sha256(
        expected_implementation_author_identity_sha256,
        name="expected implementation author identity",
    )
    checked_at_utc = _parse_utc(
        _format_utc(checked_at, name="checked_at"), name="checked_at"
    )
    payload = _load_attestation(source)
    signature = payload.pop("signature", None)
    if not isinstance(signature, Mapping):
        raise ReferenceMinimizationValidationReviewError(
            "review attestation signature is missing"
        )
    if set(signature) != {"algorithm", "key_id", "value"}:
        raise ReferenceMinimizationValidationReviewError(
            "review attestation signature fields are invalid"
        )
    if (
        signature.get("algorithm")
        != REFERENCE_MINIMIZATION_VALIDATION_REVIEW_SIGNATURE_ALGORITHM
    ):
        raise ReferenceMinimizationValidationReviewError(
            "review attestation signature algorithm is unsupported"
        )
    key_id = _require_key_id(signature.get("key_id"))
    if key_id not in trusted_reviewer_keys:
        raise ReferenceMinimizationValidationReviewError(
            "reviewer key id is not trusted"
        )
    anchor = trusted_reviewer_keys[key_id]
    if not isinstance(anchor, MinimizationScientificReviewerTrustAnchor):
        raise ReferenceMinimizationValidationReviewError(
            "trusted reviewer entry has an invalid type"
        )
    signature_value = signature.get("value")
    try:
        verified = verify_ed25519(
            _canonical_bytes(payload), signature_value, anchor.verification_key
        )
    except ReferenceMinimizationValidationEd25519Error as exc:
        raise ReferenceMinimizationValidationReviewError(
            "review attestation Ed25519 verifier is unavailable"
        ) from exc
    if not verified:
        raise ReferenceMinimizationValidationReviewError(
            "review attestation signature verification failed"
        )

    attestation_sha256 = payload.pop("attestation_sha256", None)
    if attestation_sha256 != _sha256(payload):
        raise ReferenceMinimizationValidationReviewError(
            "review attestation SHA-256 verification failed"
        )
    if (
        payload.get("schema_id")
        != REFERENCE_MINIMIZATION_VALIDATION_REVIEW_ATTESTATION_SCHEMA_ID
    ):
        raise ReferenceMinimizationValidationReviewError(
            "review attestation schema is unsupported"
        )
    contract = reference_minimization_validation_review_contract_document()
    if payload.get("contract_sha256") != contract["contract_sha256"]:
        raise ReferenceMinimizationValidationReviewError(
            "review attestation contract identity drifted"
        )
    if (
        payload.get("artifact_binding_sha256")
        != FROZEN_REFERENCE_MINIMIZATION_VALIDATION_ARTIFACT_BINDING_SHA256
    ):
        raise ReferenceMinimizationValidationReviewError(
            "review attestation artifact binding drifted"
        )
    if payload.get("implementation_author_identity_sha256") != expected_author:
        raise ReferenceMinimizationValidationReviewError(
            "review attestation implementation author identity drifted"
        )
    reviewer_identity = _require_sha256(
        payload.get("independent_reviewer_identity_sha256"),
        name="independent reviewer identity",
    )
    if reviewer_identity != anchor.reviewer_identity_sha256:
        raise ReferenceMinimizationValidationReviewError(
            "reviewer identity does not match the trusted key"
        )
    if reviewer_identity == expected_author:
        raise ReferenceMinimizationValidationReviewError(
            "implementation author and independent reviewer must differ"
        )
    if payload.get("reviewer_key_id") != key_id:
        raise ReferenceMinimizationValidationReviewError(
            "reviewer key id is cross-wired"
        )

    reviewed_at = _parse_utc(payload.get("reviewed_at_utc"), name="reviewed_at_utc")
    expires_at = _parse_utc(payload.get("expires_at_utc"), name="expires_at_utc")
    if expires_at <= reviewed_at:
        raise ReferenceMinimizationValidationReviewError(
            "review attestation expiry must follow review time"
        )
    if expires_at - reviewed_at > REFERENCE_MINIMIZATION_VALIDATION_REVIEW_MAX_VALIDITY:
        raise ReferenceMinimizationValidationReviewError(
            "review attestation validity exceeds the frozen maximum"
        )
    if checked_at_utc < reviewed_at:
        raise ReferenceMinimizationValidationReviewError(
            "review attestation is not yet valid"
        )
    if checked_at_utc >= expires_at:
        raise ReferenceMinimizationValidationReviewError(
            "review attestation is expired"
        )

    expected_checks = list(_REQUIRED_REVIEW_CHECK_IDS)
    expected_limitations = list(_REQUIRED_LIMITATION_IDS)
    if payload.get("accepted_check_ids") != expected_checks:
        raise ReferenceMinimizationValidationReviewError(
            "review attestation check coverage is incomplete or reordered"
        )
    if payload.get("acknowledged_limitation_ids") != expected_limitations:
        raise ReferenceMinimizationValidationReviewError(
            "review attestation limitations are incomplete or reordered"
        )
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
        raise ReferenceMinimizationValidationReviewError(
            "review attestation fields do not match the frozen schema"
        )
    return ReferenceMinimizationValidationReviewVerification(
        contract_sha256=contract["contract_sha256"],
        artifact_binding_sha256=FROZEN_REFERENCE_MINIMIZATION_VALIDATION_ARTIFACT_BINDING_SHA256,
        attestation_sha256=_require_sha256(
            attestation_sha256, name="review attestation"
        ),
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


def reference_minimization_validation_review_contract_authorization_decision() -> dict[
    str, Any
]:
    """Return the current closed decision; no review attestation is bundled."""

    contract = reference_minimization_validation_review_contract_document()
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
    "FROZEN_REFERENCE_MINIMIZATION_VALIDATION_REVIEW_CONTRACT_SHA256",
    "REFERENCE_MINIMIZATION_VALIDATION_REVIEW_ATTESTATION_SCHEMA_ID",
    "REFERENCE_MINIMIZATION_VALIDATION_REVIEW_CONTRACT_ID",
    "REFERENCE_MINIMIZATION_VALIDATION_REVIEW_CONTRACT_SCHEMA_ID",
    "REFERENCE_MINIMIZATION_VALIDATION_REVIEW_CONTRACT_VERSION",
    "REFERENCE_MINIMIZATION_VALIDATION_REVIEW_MAX_VALIDITY",
    "REFERENCE_MINIMIZATION_VALIDATION_REVIEW_SIGNATURE_ALGORITHM",
    "ReferenceMinimizationValidationReviewError",
    "ReferenceMinimizationValidationReviewVerification",
    "MinimizationScientificReviewerTrustAnchor",
    "build_signed_reference_minimization_validation_review_attestation",
    "reference_minimization_validation_review_contract_authorization_decision",
    "reference_minimization_validation_review_contract_document",
    "require_reference_minimization_validation_review_contract_document",
    "verify_signed_reference_minimization_validation_review_attestation",
]
