"""Signed independent review of exact Engine/OpenMM reference receipts.

This module is an offline evidence boundary.  It re-verifies both Engine
result-review chains, validates the complete OpenMM receipts, proves that the
OpenMM observations are tied to the retained Engine outputs/traces, and signs
one host-scoped projection with Ed25519.  The resulting attestation is an input
to a future two-host S0 bundle; by itself it cannot promote a production,
scientific, fitting, benchmark, or product claim.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import re
from typing import Any, Mapping, Sequence

from betelgeuze_engine_v2.physics import (
    reference_minimization_validation_result_review as _minimization_review,
)
from betelgeuze_engine_v2.physics import (
    reference_validation_result_review as _energy_review,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_ed25519 import (
    ReferenceMinimizationValidationEd25519Error,
    sign_ed25519,
    verify_ed25519,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_result_review import (
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_CONTRACT_SHA256,
    ReferenceMinimizationValidationResultReviewVerification,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_result_writer import (
    REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_MAX_BYTES,
    ReferenceMinimizationValidationResultReceipt,
    ReferenceMinimizationValidationResultWriterError,
)
from betelgeuze_engine_v2.physics.reference_validation_result_review import (
    FROZEN_REFERENCE_VALIDATION_RESULT_REVIEW_CONTRACT_SHA256,
    ReferenceValidationResultReviewVerification,
)
from betelgeuze_engine_v2.physics.reference_validation_result_writer import (
    REFERENCE_VALIDATION_RESULT_RECEIPT_MAX_BYTES,
    ReferenceValidationResultReceipt,
    ReferenceValidationResultWriterError,
)
from .openmm_reference_oracle import (
    FROZEN_OPENMM_REFERENCE_MAPPING_CONTRACT_SHA256,
    OPENMM_REFERENCE_OFFLINE_ORACLE_ID,
)
from .openmm_reference_materialization import (
    OPENMM_REFERENCE_MATERIALIZATION_SCHEMA_ID,
    OpenMMReferenceMaterializationError,
    require_openmm_reference_materialization,
)
from .openmm_reference_native_minimization import (
    FROZEN_OPENMM_REFERENCE_NATIVE_MINIMIZATION_CONFIGURATION_SHA256,
    OPENMM_REFERENCE_NATIVE_MINIMIZATION_RECEIPT_SCHEMA_ID,
    OpenMMReferenceNativeMinimizationError,
    require_openmm_reference_native_minimization_receipt,
)
from .openmm_reference_fixed_born_disposition import (
    FROZEN_OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_CONFIGURATION_SHA256,
    OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_RECEIPT_SCHEMA_ID,
    OpenMMReferenceFixedBornDispositionError,
    require_openmm_reference_fixed_born_disposition_receipt,
)
from .openmm_reference_receipts import (
    OPENMM_REFERENCE_ENERGY_FORCE_RECEIPT_SCHEMA_ID,
    OPENMM_REFERENCE_MINIMIZATION_TRACE_RECEIPT_SCHEMA_ID,
    OpenMMReferenceReceiptError,
    require_openmm_reference_energy_force_receipt,
    require_openmm_reference_minimization_trace_receipt,
)


OPENMM_REFERENCE_RESULT_REVIEW_CONTRACT_SCHEMA_ID = (
    "betelgeuze.engine_v2_openmm_reference_result_review_contract/4.0.0"
)
OPENMM_REFERENCE_RESULT_REVIEW_ATTESTATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_openmm_reference_result_review_attestation/4.0.0"
)
OPENMM_REFERENCE_RESULT_REVIEW_CONTRACT_ID = (
    "engine_v2_openmm_reference_independent_result_review/4.0.0"
)
OPENMM_REFERENCE_RESULT_REVIEW_CONTRACT_VERSION = "4.0.0"
OPENMM_REFERENCE_RESULT_REVIEW_CONTRACT_FROZEN_AT_UTC = "2026-07-24T15:00:00Z"
OPENMM_REFERENCE_RESULT_REVIEW_SIGNATURE_ALGORITHM = "ed25519"
OPENMM_REFERENCE_RESULT_REVIEW_MAX_VALIDITY = timedelta(days=30)
OPENMM_REFERENCE_RESULT_REVIEW_MAX_TRANSPORT_BYTES = 32 * 1024 * 1024

# The reviewed hash binds both nested result-review contracts, the pinned
# OpenMM mapping, exact output/trace cross-checks, role policy, and claim gate.
FROZEN_OPENMM_REFERENCE_RESULT_REVIEW_CONTRACT_SHA256 = (
    "6e543d32b320b562fa0b3ad31c1ac26cc7b274fcbb4f79025f53ce1035ea5970"
)
FROZEN_LEGACY_OPENMM_REFERENCE_RESULT_REVIEW_CONTRACT_SHA256_V3 = (
    "ff41e9ad4daba651b0d68b2a6a69f890e7549d0bef5b8418aa09c8d821b9e656"
)
FROZEN_LEGACY_OPENMM_REFERENCE_RESULT_REVIEW_CONTRACT_SHA256_V2 = (
    "8481d89bd4d3593fd220d0fc42cd3c3a09462a50cb7f65321ef7c5a1b6aa9b47"
)
FROZEN_LEGACY_OPENMM_REFERENCE_RESULT_REVIEW_CONTRACT_SHA256_V1 = (
    "cb0f55af71b8a80f184d1ac8cb0e857b81e591a7c785e5dd5c9a49dd99d5f4d0"
)

OPENMM_REFERENCE_RESULT_REVIEW_OUTCOME_ACCEPTED = "accepted"
OPENMM_REFERENCE_RESULT_REVIEW_OUTCOME_REJECTED = "rejected"

_KEY_ID_RE = re.compile(r"\A[a-zA-Z0-9][a-zA-Z0-9._:/-]{0,127}\Z")
_UTC_RE = re.compile(r"\A\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")

_REQUIRED_CHECK_IDS = (
    "energy_force_result_receipt_and_signed_result_review_reverified",
    "minimization_result_receipt_and_signed_result_review_reverified",
    "engine_commit_dependency_seed_and_role_chain_crosschecked",
    "openmm_mapping_runtime_source_and_receipt_self_hashes_reverified",
    "all_twenty_seven_cases_and_fifty_nine_variants_crosschecked",
    "all_fourteen_minimization_traces_and_failure_rows_crosschecked",
    "energy_component_total_force_units_and_atom_order_crosschecked",
    "fixed_born_self_pair_and_trace_step_outputs_reverified",
    "openmm_materialization_and_native_minimization_receipt_reverified",
    "all_fourteen_native_endpoint_rows_and_failure_dispositions_reverified",
    "native_endpoint_health_outcome_and_failed_case_ids_propagated",
    "rejected_native_fixed_born_failure_disposition_receipt_reverified",
    "failure_disposition_completeness_separated_from_endpoint_acceptance",
    "host_cpu_session_custody_nonce_and_freshness_bound",
    "revocation_supersession_role_separation_and_nonpromotion_reviewed",
)
_REQUIRED_LIMITATION_IDS = (
    "offline_openmm_receipts_are_claim_closed_development_observations",
    "external_review_does_not_authenticate_external_custody_by_itself",
    "external_review_does_not_establish_two_host_reproducibility",
    "openmm_trace_re_evaluation_is_not_native_lbfgs_trajectory_equivalence",
    "native_endpoint_rejection_blocks_external_comparison_and_s0_admission",
    "failure_disposition_completion_does_not_resolve_native_endpoint_health",
    "failure_disposition_sensitivity_does_not_prove_causal_root_cause",
    "openmm_review_does_not_establish_chemical_applicability",
    "external_review_does_not_authorize_s0_s1_fitting_or_product_promotion",
)
_CLOSED_GATE_BLOCKERS = (
    "signed_openmm_reference_result_review_attestation_missing",
    "trusted_openmm_reference_result_reviewer_key_not_provided",
    "openmm_reference_materialization_not_provided",
    "openmm_native_minimization_receipt_not_provided",
    "openmm_fixed_born_failure_disposition_receipt_not_provided",
    "openmm_native_minimization_endpoint_health_not_accepted",
    "two_distinct_cpu_host_attestations_missing",
    "host_to_host_exact_physics_projection_equality_missing",
    "externally_authenticated_production_custody_missing",
    "final_independent_human_s0_approval_missing",
    "scientific_parameter_applicability_not_established",
    "s1_admission_not_authorized",
    "product_integration_not_qualified",
)
_POST_ATTESTATION_BLOCKERS = (
    "single_host_external_review_is_not_two_host_reproducibility",
    "offline_openmm_receipts_remain_nonproduction_claim_closed_observations",
    "externally_authenticated_production_custody_missing",
    "final_independent_human_s0_approval_missing",
    "scientific_parameter_applicability_not_established",
    "s1_admission_not_authorized",
    "product_integration_not_qualified",
)
_REJECTED_NATIVE_ENDPOINT_BLOCKERS = (
    "openmm_native_minimization_endpoint_health_failed",
    "fixed_born_constraint_projection_tradeoff_does_not_resolve_endpoint_health",
    "fixed_born_failure_causal_root_cause_not_proven",
    "external_oracle_comparison_not_accepted",
    "s0_admission_blocked_by_native_endpoint_failure",
    *_POST_ATTESTATION_BLOCKERS,
)


class OpenMMReferenceResultReviewError(ValueError):
    """An external receipt, nested review, signature, or binding is invalid."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise OpenMMReferenceResultReviewError(
            "OpenMM result-review value is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _raw_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise OpenMMReferenceResultReviewError(
            f"{name} must be a lowercase SHA-256 digest"
        )
    return value


def _require_commit_sha(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 40
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise OpenMMReferenceResultReviewError(
            f"{name} must be a lowercase Git commit SHA"
        )
    return value


def _require_key_id(value: object) -> str:
    if not isinstance(value, str) or _KEY_ID_RE.fullmatch(value) is None:
        raise OpenMMReferenceResultReviewError("reviewer key id is invalid")
    return value


def _require_key(value: bytes | str, *, name: str) -> bytes:
    if isinstance(value, bytes):
        raw = value
    elif isinstance(value, str):
        try:
            raw = bytes.fromhex(value)
        except ValueError as exc:
            raise OpenMMReferenceResultReviewError(
                f"{name} is not hexadecimal"
            ) from exc
    else:
        raise OpenMMReferenceResultReviewError(f"{name} must be bytes or hex")
    if len(raw) != 32:
        raise OpenMMReferenceResultReviewError(f"{name} must be 32 bytes")
    return raw


def _format_utc(value: datetime, *, name: str) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise OpenMMReferenceResultReviewError(f"{name} must be timezone-aware")
    normalized = value.astimezone(timezone.utc)
    if normalized.microsecond:
        raise OpenMMReferenceResultReviewError(f"{name} must use second resolution")
    return normalized.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_utc(value: object, *, name: str) -> datetime:
    if not isinstance(value, str) or _UTC_RE.fullmatch(value) is None:
        raise OpenMMReferenceResultReviewError(f"{name} must be second-resolution UTC")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise OpenMMReferenceResultReviewError(
            f"{name} must be second-resolution UTC"
        ) from exc


def _external_sha256_set(values: Sequence[str], *, name: str) -> set[str]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise OpenMMReferenceResultReviewError(f"{name} list is invalid")
    normalized = [_require_sha256(value, name=name) for value in values]
    if len(normalized) != len(set(normalized)):
        raise OpenMMReferenceResultReviewError(f"{name} list contains duplicates")
    return set(normalized)


def _load_attestation(source: str | bytes | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(source, Mapping):
        return dict(source)
    raw = source.encode("utf-8") if isinstance(source, str) else source
    if (
        not isinstance(raw, bytes)
        or not raw
        or len(raw) > OPENMM_REFERENCE_RESULT_REVIEW_MAX_TRANSPORT_BYTES
    ):
        raise OpenMMReferenceResultReviewError(
            "OpenMM result-review transport is invalid or oversized"
        )

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise OpenMMReferenceResultReviewError(
                    "OpenMM result-review transport contains a duplicate key"
                )
            result[key] = value
        return result

    try:
        loaded = json.loads(
            raw.decode("utf-8"), object_pairs_hook=reject_duplicate_keys
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OpenMMReferenceResultReviewError(
            "OpenMM result-review transport must be UTF-8 JSON"
        ) from exc
    if not isinstance(loaded, dict) or _canonical_bytes(loaded) != raw:
        raise OpenMMReferenceResultReviewError(
            "OpenMM result-review transport is not canonical JSON"
        )
    return loaded


def _validated_energy_result_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise OpenMMReferenceResultReviewError(
            "energy-force result receipt must be a mapping"
        )
    document = dict(value)
    raw = _canonical_bytes(document)
    if len(raw) > REFERENCE_VALIDATION_RESULT_RECEIPT_MAX_BYTES:
        raise OpenMMReferenceResultReviewError(
            "energy-force result receipt exceeds its byte bound"
        )
    try:
        return ReferenceValidationResultReceipt(
            receipt_sha256=_require_sha256(
                document.get("receipt_sha256"), name="energy-force result receipt"
            ),
            canonical_document_bytes=raw,
        ).to_dict()
    except ReferenceValidationResultWriterError as exc:
        raise OpenMMReferenceResultReviewError(
            "energy-force result receipt validation failed"
        ) from exc


def _validated_minimization_result_receipt(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise OpenMMReferenceResultReviewError(
            "minimization result receipt must be a mapping"
        )
    document = dict(value)
    raw = _canonical_bytes(document)
    if len(raw) > REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_MAX_BYTES:
        raise OpenMMReferenceResultReviewError(
            "minimization result receipt exceeds its byte bound"
        )
    try:
        return ReferenceMinimizationValidationResultReceipt(
            receipt_sha256=_require_sha256(
                document.get("receipt_sha256"), name="minimization result receipt"
            ),
            canonical_document_bytes=raw,
        ).to_dict()
    except ReferenceMinimizationValidationResultWriterError as exc:
        raise OpenMMReferenceResultReviewError(
            "minimization result receipt validation failed"
        ) from exc


@dataclass(frozen=True, slots=True)
class EnergyForceResultReviewEvidence:
    """Raw inputs needed to freshly verify one energy-force result review."""

    result_receipt: Mapping[str, Any]
    result_review_attestation: str | bytes | Mapping[str, Any]
    pre_execution_review_attestation: str | bytes | Mapping[str, Any]
    authorization_receipt: str | bytes | Mapping[str, Any]
    trusted_scientific_reviewer_keys: Mapping[str, Any]
    trusted_authorization_operator_keys: Mapping[str, Any]
    trusted_result_reviewer_keys: Mapping[str, Any]
    expected_implementation_author_identity_sha256: str
    expected_independent_scientific_reviewer_identity_sha256: str
    expected_authorization_operator_identity_sha256: str
    revoked_pre_execution_review_attestation_sha256s: Sequence[str] = ()
    revoked_authorization_receipt_sha256s: Sequence[str] = ()
    revoked_execution_environment_receipt_sha256s: Sequence[str] = ()
    revoked_result_receipt_sha256s: Sequence[str] = ()
    superseded_result_receipt_sha256s: Sequence[str] = ()
    revoked_result_review_attestation_sha256s: Sequence[str] = ()
    superseded_result_review_attestation_sha256s: Sequence[str] = ()

    def verify(
        self, *, checked_at: datetime
    ) -> ReferenceValidationResultReviewVerification:
        try:
            return _energy_review.verify_signed_reference_validation_result_review_attestation(
                self.result_review_attestation,
                result_receipt=self.result_receipt,
                pre_execution_review_attestation=(
                    self.pre_execution_review_attestation
                ),
                authorization_receipt=self.authorization_receipt,
                trusted_scientific_reviewer_keys=(
                    self.trusted_scientific_reviewer_keys
                ),
                trusted_authorization_operator_keys=(
                    self.trusted_authorization_operator_keys
                ),
                expected_result_receipt_sha256=_require_sha256(
                    self.result_receipt.get("receipt_sha256"),
                    name="expected energy-force result receipt",
                ),
                trusted_result_reviewer_keys=self.trusted_result_reviewer_keys,
                expected_implementation_author_identity_sha256=(
                    self.expected_implementation_author_identity_sha256
                ),
                expected_independent_scientific_reviewer_identity_sha256=(
                    self.expected_independent_scientific_reviewer_identity_sha256
                ),
                expected_authorization_operator_identity_sha256=(
                    self.expected_authorization_operator_identity_sha256
                ),
                checked_at=checked_at,
                revoked_pre_execution_review_attestation_sha256s=(
                    self.revoked_pre_execution_review_attestation_sha256s
                ),
                revoked_authorization_receipt_sha256s=(
                    self.revoked_authorization_receipt_sha256s
                ),
                revoked_execution_environment_receipt_sha256s=(
                    self.revoked_execution_environment_receipt_sha256s
                ),
                revoked_result_receipt_sha256s=(self.revoked_result_receipt_sha256s),
                superseded_result_receipt_sha256s=(
                    self.superseded_result_receipt_sha256s
                ),
                revoked_result_review_attestation_sha256s=(
                    self.revoked_result_review_attestation_sha256s
                ),
                superseded_result_review_attestation_sha256s=(
                    self.superseded_result_review_attestation_sha256s
                ),
            )
        except _energy_review.ReferenceValidationResultReviewError as exc:
            raise OpenMMReferenceResultReviewError(
                "energy-force result review verification failed"
            ) from exc


@dataclass(frozen=True, slots=True)
class MinimizationResultReviewEvidence:
    """Raw inputs needed to freshly verify one minimization result review."""

    result_receipt: Mapping[str, Any]
    result_review_attestation: str | bytes | Mapping[str, Any]
    pre_execution_review_attestation: str | bytes | Mapping[str, Any]
    authorization_receipt: str | bytes | Mapping[str, Any]
    trusted_scientific_reviewer_keys: Mapping[str, Any]
    trusted_authorization_operator_keys: Mapping[str, Any]
    trusted_result_reviewer_keys: Mapping[str, Any]
    expected_implementation_author_identity_sha256: str
    expected_independent_scientific_reviewer_identity_sha256: str
    expected_authorization_operator_identity_sha256: str
    revoked_pre_execution_review_attestation_sha256s: Sequence[str] = ()
    revoked_authorization_receipt_sha256s: Sequence[str] = ()
    revoked_execution_environment_receipt_sha256s: Sequence[str] = ()
    revoked_result_receipt_sha256s: Sequence[str] = ()
    superseded_result_receipt_sha256s: Sequence[str] = ()
    revoked_result_review_attestation_sha256s: Sequence[str] = ()
    superseded_result_review_attestation_sha256s: Sequence[str] = ()

    def verify(
        self, *, checked_at: datetime
    ) -> ReferenceMinimizationValidationResultReviewVerification:
        try:
            return _minimization_review.verify_signed_reference_minimization_validation_result_review_attestation(
                self.result_review_attestation,
                result_receipt=self.result_receipt,
                pre_execution_review_attestation=(
                    self.pre_execution_review_attestation
                ),
                authorization_receipt=self.authorization_receipt,
                trusted_scientific_reviewer_keys=(
                    self.trusted_scientific_reviewer_keys
                ),
                trusted_authorization_operator_keys=(
                    self.trusted_authorization_operator_keys
                ),
                expected_result_receipt_sha256=_require_sha256(
                    self.result_receipt.get("receipt_sha256"),
                    name="expected minimization result receipt",
                ),
                trusted_result_reviewer_keys=self.trusted_result_reviewer_keys,
                expected_implementation_author_identity_sha256=(
                    self.expected_implementation_author_identity_sha256
                ),
                expected_independent_scientific_reviewer_identity_sha256=(
                    self.expected_independent_scientific_reviewer_identity_sha256
                ),
                expected_authorization_operator_identity_sha256=(
                    self.expected_authorization_operator_identity_sha256
                ),
                checked_at=checked_at,
                revoked_pre_execution_review_attestation_sha256s=(
                    self.revoked_pre_execution_review_attestation_sha256s
                ),
                revoked_authorization_receipt_sha256s=(
                    self.revoked_authorization_receipt_sha256s
                ),
                revoked_execution_environment_receipt_sha256s=(
                    self.revoked_execution_environment_receipt_sha256s
                ),
                revoked_result_receipt_sha256s=(self.revoked_result_receipt_sha256s),
                superseded_result_receipt_sha256s=(
                    self.superseded_result_receipt_sha256s
                ),
                revoked_result_review_attestation_sha256s=(
                    self.revoked_result_review_attestation_sha256s
                ),
                superseded_result_review_attestation_sha256s=(
                    self.superseded_result_review_attestation_sha256s
                ),
            )
        except (
            _minimization_review.ReferenceMinimizationValidationResultReviewError
        ) as exc:
            raise OpenMMReferenceResultReviewError(
                "minimization result review verification failed"
            ) from exc


@dataclass(frozen=True, slots=True)
class OpenMMReferenceResultReviewerTrustAnchor:
    """Out-of-band external result-reviewer identity and public key."""

    reviewer_identity_sha256: str
    verification_key: bytes = field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "reviewer_identity_sha256",
            _require_sha256(
                self.reviewer_identity_sha256,
                name="trusted OpenMM result reviewer identity",
            ),
        )
        object.__setattr__(
            self,
            "verification_key",
            _require_key(
                self.verification_key,
                name="trusted OpenMM result reviewer verification key",
            ),
        )


@dataclass(frozen=True, slots=True)
class OpenMMReferenceResultReviewVerification:
    contract_sha256: str
    attestation_sha256: str
    enrolled_host_identity_sha256: str
    cpu_identity_sha256: str
    production_evidence_session_sha256: str
    custody_terminal_sha256: str
    energy_force_result_receipt_sha256: str
    energy_force_result_review_attestation_sha256: str
    minimization_result_receipt_sha256: str
    minimization_result_review_attestation_sha256: str
    openmm_energy_force_receipt_sha256: str
    openmm_minimization_trace_receipt_sha256: str
    openmm_reference_materialization_sha256: str
    openmm_native_minimization_receipt_sha256: str
    openmm_fixed_born_disposition_receipt_sha256: str | None
    energy_force_physics_projection_sha256: str
    minimization_physics_projection_sha256: str
    native_minimization_physics_projection_sha256: str
    fixed_born_disposition_physics_projection_sha256: str | None
    energy_force_source_manifest_sha256: str
    minimization_source_manifest_sha256: str
    energy_force_execution_environment_receipt_sha256: str
    minimization_execution_environment_receipt_sha256: str
    openmm_runtime_identity_sha256: str
    openmm_source_identity_sha256: str
    native_minimization_configuration_sha256: str
    fixed_born_disposition_configuration_sha256: str | None
    code_commit_sha: str
    dependency_rows_sha256: str
    seed: int
    energy_force_authorization_nonce_sha256: str
    minimization_authorization_nonce_sha256: str
    nonce_sha256: str
    implementation_author_identity_sha256: str
    independent_scientific_reviewer_identity_sha256: str
    authorization_operator_identity_sha256: str
    energy_force_result_reviewer_identity_sha256: str
    minimization_result_reviewer_identity_sha256: str
    external_result_reviewer_identity_sha256: str
    external_result_reviewer_key_id: str
    reviewed_at_utc: str
    expires_at_utc: str
    failure_inclusive_native_minimization_evidence_verified: bool
    native_minimization_status: str
    native_endpoint_health_passed_case_count: int
    native_endpoint_health_failed_case_ids: tuple[str, ...]
    fixed_born_failure_disposition_required: bool
    fixed_born_failure_disposition_verified: bool
    fixed_born_failure_disposition_complete: bool
    fixed_born_failure_disposition_status: str
    fixed_born_failure_disposition_classification: str | None
    external_oracle_comparison_verified: bool
    result_review_outcome: str
    production_validation_evidence: bool
    scientifically_validated: bool
    s0_admission_authorized: bool
    s1_admission_authorized: bool
    claim_safe: bool
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        for name, value in (
            ("contract", self.contract_sha256),
            ("attestation", self.attestation_sha256),
            ("host", self.enrolled_host_identity_sha256),
            ("CPU", self.cpu_identity_sha256),
            ("production evidence session", self.production_evidence_session_sha256),
            ("custody terminal", self.custody_terminal_sha256),
            ("energy-force result receipt", self.energy_force_result_receipt_sha256),
            (
                "energy-force result review",
                self.energy_force_result_review_attestation_sha256,
            ),
            ("minimization result receipt", self.minimization_result_receipt_sha256),
            (
                "minimization result review",
                self.minimization_result_review_attestation_sha256,
            ),
            ("OpenMM energy-force receipt", self.openmm_energy_force_receipt_sha256),
            (
                "OpenMM minimization receipt",
                self.openmm_minimization_trace_receipt_sha256,
            ),
            (
                "OpenMM reference materialization",
                self.openmm_reference_materialization_sha256,
            ),
            (
                "OpenMM native minimization receipt",
                self.openmm_native_minimization_receipt_sha256,
            ),
            (
                "energy-force physics projection",
                self.energy_force_physics_projection_sha256,
            ),
            (
                "minimization physics projection",
                self.minimization_physics_projection_sha256,
            ),
            (
                "native minimization physics projection",
                self.native_minimization_physics_projection_sha256,
            ),
            ("energy-force source manifest", self.energy_force_source_manifest_sha256),
            ("minimization source manifest", self.minimization_source_manifest_sha256),
            (
                "energy-force execution environment receipt",
                self.energy_force_execution_environment_receipt_sha256,
            ),
            (
                "minimization execution environment receipt",
                self.minimization_execution_environment_receipt_sha256,
            ),
            ("OpenMM runtime identity", self.openmm_runtime_identity_sha256),
            ("OpenMM source identity", self.openmm_source_identity_sha256),
            (
                "native minimization configuration",
                self.native_minimization_configuration_sha256,
            ),
            ("dependency rows", self.dependency_rows_sha256),
            (
                "energy-force authorization nonce",
                self.energy_force_authorization_nonce_sha256,
            ),
            (
                "minimization authorization nonce",
                self.minimization_authorization_nonce_sha256,
            ),
            ("external result-review nonce", self.nonce_sha256),
            ("implementation author", self.implementation_author_identity_sha256),
            (
                "independent scientific reviewer",
                self.independent_scientific_reviewer_identity_sha256,
            ),
            ("authorization operator", self.authorization_operator_identity_sha256),
            (
                "energy-force result reviewer",
                self.energy_force_result_reviewer_identity_sha256,
            ),
            (
                "minimization result reviewer",
                self.minimization_result_reviewer_identity_sha256,
            ),
            ("external result reviewer", self.external_result_reviewer_identity_sha256),
        ):
            _require_sha256(value, name=name)
        for name, value in (
            (
                "OpenMM fixed-Born disposition receipt",
                self.openmm_fixed_born_disposition_receipt_sha256,
            ),
            (
                "fixed-Born disposition physics projection",
                self.fixed_born_disposition_physics_projection_sha256,
            ),
            (
                "fixed-Born disposition configuration",
                self.fixed_born_disposition_configuration_sha256,
            ),
        ):
            if value is not None:
                _require_sha256(value, name=name)
        _require_commit_sha(self.code_commit_sha, name="code commit")
        _require_key_id(self.external_result_reviewer_key_id)
        if type(self.seed) is not int or self.seed < 0:
            raise OpenMMReferenceResultReviewError("verified seed is invalid")
        reviewed = _parse_utc(self.reviewed_at_utc, name="reviewed_at")
        expires = _parse_utc(self.expires_at_utc, name="expires_at")
        if expires <= reviewed:
            raise OpenMMReferenceResultReviewError(
                "verified OpenMM review expiry must follow review time"
            )
        if not self.failure_inclusive_native_minimization_evidence_verified:
            raise OpenMMReferenceResultReviewError(
                "verification must retain the failure-inclusive native comparison"
            )
        if (
            type(self.native_endpoint_health_passed_case_count) is not int
            or not 0 <= self.native_endpoint_health_passed_case_count <= 8
            or not isinstance(self.native_endpoint_health_failed_case_ids, tuple)
            or any(
                not isinstance(case_id, str) or not case_id
                for case_id in self.native_endpoint_health_failed_case_ids
            )
            or len(set(self.native_endpoint_health_failed_case_ids))
            != len(self.native_endpoint_health_failed_case_ids)
            or self.native_endpoint_health_passed_case_count
            + len(self.native_endpoint_health_failed_case_ids)
            != 8
        ):
            raise OpenMMReferenceResultReviewError(
                "native endpoint-health disposition is invalid"
            )
        if self.native_minimization_status == (
            "accepted_offline_native_endpoint_comparison"
        ):
            if (
                not self.external_oracle_comparison_verified
                or self.result_review_outcome
                != OPENMM_REFERENCE_RESULT_REVIEW_OUTCOME_ACCEPTED
                or self.native_endpoint_health_passed_case_count != 8
                or self.native_endpoint_health_failed_case_ids
                or self.openmm_fixed_born_disposition_receipt_sha256 is not None
                or self.fixed_born_disposition_physics_projection_sha256 is not None
                or self.fixed_born_disposition_configuration_sha256 is not None
                or self.fixed_born_failure_disposition_required
                or self.fixed_born_failure_disposition_verified
                or self.fixed_born_failure_disposition_complete
                or self.fixed_born_failure_disposition_status
                != "not_applicable_native_endpoint_accepted"
                or self.fixed_born_failure_disposition_classification is not None
            ):
                raise OpenMMReferenceResultReviewError(
                    "accepted native endpoint disposition is inconsistent"
                )
        elif self.native_minimization_status == (
            "rejected_offline_native_endpoint_comparison"
        ):
            if (
                self.external_oracle_comparison_verified
                or self.result_review_outcome
                != OPENMM_REFERENCE_RESULT_REVIEW_OUTCOME_REJECTED
                or self.native_endpoint_health_passed_case_count >= 8
                or not self.native_endpoint_health_failed_case_ids
                or self.openmm_fixed_born_disposition_receipt_sha256 is None
                or self.fixed_born_disposition_physics_projection_sha256 is None
                or self.fixed_born_disposition_configuration_sha256
                != FROZEN_OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_CONFIGURATION_SHA256
                or not self.fixed_born_failure_disposition_required
                or not self.fixed_born_failure_disposition_verified
                or not self.fixed_born_failure_disposition_complete
                or self.fixed_born_failure_disposition_status
                != "accepted_failure_disposition_evidence"
                or self.fixed_born_failure_disposition_classification
                != "final_constraint_projection_tradeoff_observed"
            ):
                raise OpenMMReferenceResultReviewError(
                    "rejected native endpoint disposition is inconsistent"
                )
        else:
            raise OpenMMReferenceResultReviewError(
                "native minimization status is invalid"
            )
        if any(
            (
                self.production_validation_evidence,
                self.scientifically_validated,
                self.s0_admission_authorized,
                self.s1_admission_authorized,
                self.claim_safe,
            )
        ):
            raise OpenMMReferenceResultReviewError(
                "single-host OpenMM review cannot promote a downstream claim"
            )
        if not self.blockers:
            raise OpenMMReferenceResultReviewError(
                "OpenMM result-review verification must retain blockers"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_sha256": self.contract_sha256,
            "attestation_sha256": self.attestation_sha256,
            "enrolled_host_identity_sha256": self.enrolled_host_identity_sha256,
            "cpu_identity_sha256": self.cpu_identity_sha256,
            "production_evidence_session_sha256": (
                self.production_evidence_session_sha256
            ),
            "custody_terminal_sha256": self.custody_terminal_sha256,
            "energy_force_result_receipt_sha256": (
                self.energy_force_result_receipt_sha256
            ),
            "energy_force_result_review_attestation_sha256": (
                self.energy_force_result_review_attestation_sha256
            ),
            "minimization_result_receipt_sha256": (
                self.minimization_result_receipt_sha256
            ),
            "minimization_result_review_attestation_sha256": (
                self.minimization_result_review_attestation_sha256
            ),
            "openmm_energy_force_receipt_sha256": (
                self.openmm_energy_force_receipt_sha256
            ),
            "openmm_minimization_trace_receipt_sha256": (
                self.openmm_minimization_trace_receipt_sha256
            ),
            "openmm_reference_materialization_sha256": (
                self.openmm_reference_materialization_sha256
            ),
            "openmm_native_minimization_receipt_sha256": (
                self.openmm_native_minimization_receipt_sha256
            ),
            "openmm_fixed_born_disposition_receipt_sha256": (
                self.openmm_fixed_born_disposition_receipt_sha256
            ),
            "energy_force_physics_projection_sha256": (
                self.energy_force_physics_projection_sha256
            ),
            "minimization_physics_projection_sha256": (
                self.minimization_physics_projection_sha256
            ),
            "native_minimization_physics_projection_sha256": (
                self.native_minimization_physics_projection_sha256
            ),
            "fixed_born_disposition_physics_projection_sha256": (
                self.fixed_born_disposition_physics_projection_sha256
            ),
            "energy_force_source_manifest_sha256": (
                self.energy_force_source_manifest_sha256
            ),
            "minimization_source_manifest_sha256": (
                self.minimization_source_manifest_sha256
            ),
            "energy_force_execution_environment_receipt_sha256": (
                self.energy_force_execution_environment_receipt_sha256
            ),
            "minimization_execution_environment_receipt_sha256": (
                self.minimization_execution_environment_receipt_sha256
            ),
            "openmm_runtime_identity_sha256": self.openmm_runtime_identity_sha256,
            "openmm_source_identity_sha256": self.openmm_source_identity_sha256,
            "native_minimization_configuration_sha256": (
                self.native_minimization_configuration_sha256
            ),
            "fixed_born_disposition_configuration_sha256": (
                self.fixed_born_disposition_configuration_sha256
            ),
            "code_commit_sha": self.code_commit_sha,
            "dependency_rows_sha256": self.dependency_rows_sha256,
            "seed": self.seed,
            "energy_force_authorization_nonce_sha256": (
                self.energy_force_authorization_nonce_sha256
            ),
            "minimization_authorization_nonce_sha256": (
                self.minimization_authorization_nonce_sha256
            ),
            "nonce_sha256": self.nonce_sha256,
            "implementation_author_identity_sha256": (
                self.implementation_author_identity_sha256
            ),
            "independent_scientific_reviewer_identity_sha256": (
                self.independent_scientific_reviewer_identity_sha256
            ),
            "authorization_operator_identity_sha256": (
                self.authorization_operator_identity_sha256
            ),
            "energy_force_result_reviewer_identity_sha256": (
                self.energy_force_result_reviewer_identity_sha256
            ),
            "minimization_result_reviewer_identity_sha256": (
                self.minimization_result_reviewer_identity_sha256
            ),
            "external_result_reviewer_identity_sha256": (
                self.external_result_reviewer_identity_sha256
            ),
            "external_result_reviewer_key_id": self.external_result_reviewer_key_id,
            "reviewed_at_utc": self.reviewed_at_utc,
            "expires_at_utc": self.expires_at_utc,
            "failure_inclusive_native_minimization_evidence_verified": (
                self.failure_inclusive_native_minimization_evidence_verified
            ),
            "native_minimization_status": self.native_minimization_status,
            "native_endpoint_health_passed_case_count": (
                self.native_endpoint_health_passed_case_count
            ),
            "native_endpoint_health_failed_case_ids": list(
                self.native_endpoint_health_failed_case_ids
            ),
            "fixed_born_failure_disposition_required": (
                self.fixed_born_failure_disposition_required
            ),
            "fixed_born_failure_disposition_verified": (
                self.fixed_born_failure_disposition_verified
            ),
            "fixed_born_failure_disposition_complete": (
                self.fixed_born_failure_disposition_complete
            ),
            "fixed_born_failure_disposition_status": (
                self.fixed_born_failure_disposition_status
            ),
            "fixed_born_failure_disposition_classification": (
                self.fixed_born_failure_disposition_classification
            ),
            "external_oracle_comparison_verified": (
                self.external_oracle_comparison_verified
            ),
            "result_review_outcome": self.result_review_outcome,
            "production_validation_evidence": self.production_validation_evidence,
            "scientifically_validated": self.scientifically_validated,
            "s0_admission_authorized": self.s0_admission_authorized,
            "s1_admission_authorized": self.s1_admission_authorized,
            "claim_safe": self.claim_safe,
            "blockers": list(self.blockers),
        }


def _result_receipt_dependency_rows(receipt: Mapping[str, Any]) -> list[dict[str, str]]:
    value = receipt.get("dependency_artifact_sha256_rows")
    if not isinstance(value, list) or not value:
        raise OpenMMReferenceResultReviewError(
            "result receipt dependency rows are missing"
        )
    rows: list[dict[str, str]] = []
    for item in value:
        if (
            not isinstance(item, Mapping)
            or set(item) != {"artifact_id", "sha256"}
            or not isinstance(item.get("artifact_id"), str)
            or not item["artifact_id"]
        ):
            raise OpenMMReferenceResultReviewError(
                "result receipt dependency row is invalid"
            )
        rows.append(
            {
                "artifact_id": item["artifact_id"],
                "sha256": _require_sha256(
                    item.get("sha256"), name="dependency artifact"
                ),
            }
        )
    if rows != sorted(rows, key=lambda row: row["artifact_id"]) or len(
        {row["artifact_id"] for row in rows}
    ) != len(rows):
        raise OpenMMReferenceResultReviewError(
            "result receipt dependency rows are not canonical"
        )
    return rows


def _require_exact_number(left: object, right: object, *, name: str) -> None:
    if (
        isinstance(left, bool)
        or isinstance(right, bool)
        or not isinstance(left, (int, float))
        or not isinstance(right, (int, float))
        or not math.isfinite(float(left))
        or not math.isfinite(float(right))
        or float(left).hex() != float(right).hex()
    ):
        raise OpenMMReferenceResultReviewError(f"{name} is cross-wired")


def _component_map(value: object, *, name: str) -> dict[str, float]:
    if not isinstance(value, list) or not value:
        raise OpenMMReferenceResultReviewError(f"{name} components are invalid")
    rows: dict[str, float] = {}
    for row in value:
        if (
            not isinstance(row, Mapping)
            or set(row) != {"name", "value", "unit"}
            or not isinstance(row.get("name"), str)
            or row.get("unit") != "kcal/mol"
            or row["name"] in rows
        ):
            raise OpenMMReferenceResultReviewError(f"{name} component row is invalid")
        number = row.get("value")
        if (
            isinstance(number, bool)
            or not isinstance(number, (int, float))
            or not math.isfinite(float(number))
        ):
            raise OpenMMReferenceResultReviewError(f"{name} component value is invalid")
        rows[row["name"]] = float(number)
    return rows


def _require_exact_components(left: object, right: object, *, name: str) -> None:
    left_rows = _component_map(left, name=f"{name} left")
    right_rows = _component_map(right, name=f"{name} right")
    if set(left_rows) != set(right_rows):
        raise OpenMMReferenceResultReviewError(
            f"{name} component coverage is cross-wired"
        )
    for component in sorted(left_rows):
        _require_exact_number(
            left_rows[component],
            right_rows[component],
            name=f"{name} {component}",
        )


def _require_exact_array(left: object, right: object, *, name: str) -> None:
    if (
        not isinstance(left, list)
        or not isinstance(right, list)
        or len(left) != len(right)
    ):
        raise OpenMMReferenceResultReviewError(f"{name} shape is cross-wired")
    for row_index, (left_row, right_row) in enumerate(zip(left, right, strict=True)):
        if (
            not isinstance(left_row, list)
            or not isinstance(right_row, list)
            or len(left_row) != 3
            or len(right_row) != 3
        ):
            raise OpenMMReferenceResultReviewError(f"{name} shape is invalid")
        for axis, (left_value, right_value) in enumerate(
            zip(left_row, right_row, strict=True)
        ):
            _require_exact_number(
                left_value,
                right_value,
                name=f"{name} row {row_index} axis {axis}",
            )


def _crosscheck_energy_force_outputs(
    engine_receipt: Mapping[str, Any],
    openmm_receipt: Mapping[str, Any],
) -> str:
    engine_cases = engine_receipt.get("case_results")
    openmm_cases = openmm_receipt.get("cases")
    if (
        not isinstance(engine_cases, list)
        or not isinstance(openmm_cases, list)
        or len(engine_cases) != 27
        or len(openmm_cases) != 27
    ):
        raise OpenMMReferenceResultReviewError(
            "energy-force receipt case coverage is incomplete"
        )
    variant_count = 0
    for engine_case, openmm_case in zip(engine_cases, openmm_cases, strict=True):
        if not isinstance(engine_case, Mapping) or not isinstance(openmm_case, Mapping):
            raise OpenMMReferenceResultReviewError(
                "energy-force receipt case row is invalid"
            )
        if any(
            (
                engine_case.get("case_id") != openmm_case.get("case_id"),
                engine_case.get("case_input_sha256")
                != openmm_case.get("case_input_sha256"),
                engine_case.get("expected_outcome")
                != openmm_case.get("expected_outcome"),
                engine_case.get("expected_error_code")
                != openmm_case.get("expected_error_code"),
            )
        ):
            raise OpenMMReferenceResultReviewError(
                "energy-force case identity is cross-wired"
            )
        engine_variants = engine_case.get("variant_results")
        openmm_variants = openmm_case.get("variants")
        if (
            not isinstance(engine_variants, list)
            or not isinstance(openmm_variants, list)
            or len(engine_variants) != len(openmm_variants)
        ):
            raise OpenMMReferenceResultReviewError(
                "energy-force variant coverage is cross-wired"
            )
        variant_count += len(engine_variants)
        for engine_variant, openmm_variant in zip(
            engine_variants, openmm_variants, strict=True
        ):
            if not isinstance(engine_variant, Mapping) or not isinstance(
                openmm_variant, Mapping
            ):
                raise OpenMMReferenceResultReviewError(
                    "energy-force variant row is invalid"
                )
            if any(
                (
                    engine_variant.get("variant_id")
                    != openmm_variant.get("variant_id"),
                    engine_variant.get("runtime_input_sha256")
                    != openmm_variant.get("runtime_input_sha256"),
                )
            ):
                raise OpenMMReferenceResultReviewError(
                    "energy-force variant identity is cross-wired"
                )
            if engine_variant.get("observed_status") == "success":
                if (
                    openmm_variant.get("disposition") != "evaluated_openmm_reference"
                    or openmm_variant.get("openmm_evaluation_performed") is not True
                    or openmm_variant.get("comparison_performed") is not True
                ):
                    raise OpenMMReferenceResultReviewError(
                        "successful Engine variant is not evaluated by OpenMM"
                    )
                if _sha256(openmm_variant.get("exact_input")) != engine_variant.get(
                    "oracle_input_sha256"
                ):
                    raise OpenMMReferenceResultReviewError(
                        "energy-force exact input is cross-wired"
                    )
                engine_output = openmm_variant.get("engine_evaluation")
                analytic_output = openmm_variant.get("independent_analytic_evaluation")
                if not isinstance(engine_output, Mapping) or not isinstance(
                    analytic_output, Mapping
                ):
                    raise OpenMMReferenceResultReviewError(
                        "OpenMM comparison omitted an Engine or analytic output"
                    )
                _require_exact_components(
                    engine_variant.get("component_energy_values_and_units"),
                    engine_output.get("component_energies"),
                    name="Engine component energy",
                )
                engine_total = engine_output.get("total_energy")
                engine_forces = engine_output.get("forces")
                if (
                    not isinstance(engine_total, Mapping)
                    or engine_total.get("unit") != "kcal/mol"
                    or not isinstance(engine_forces, Mapping)
                    or engine_forces.get("unit") != "kcal/mol/angstrom"
                ):
                    raise OpenMMReferenceResultReviewError(
                        "energy-force output units are cross-wired"
                    )
                _require_exact_number(
                    engine_variant.get("total_energy_value"),
                    engine_total.get("value"),
                    name="Engine total energy",
                )
                _require_exact_array(
                    engine_variant.get("force_array_values"),
                    engine_forces.get("values"),
                    name="Engine force array",
                )
            elif engine_variant.get("observed_status") == "fail_closed":
                if (
                    openmm_variant.get("disposition")
                    != "not_applicable_engine_contract"
                    or openmm_variant.get("expected_error_code")
                    != engine_variant.get("observed_error_code")
                    or openmm_variant.get("openmm_evaluation_performed") is not False
                    or openmm_variant.get("comparison_performed") is not False
                ):
                    raise OpenMMReferenceResultReviewError(
                        "energy-force failure disposition is cross-wired"
                    )
            else:
                raise OpenMMReferenceResultReviewError(
                    "accepted Engine review contains a nonterminal variant"
                )
    if variant_count != 59:
        raise OpenMMReferenceResultReviewError(
            "energy-force receipt does not contain exactly 59 variants"
        )
    return _sha256(
        {
            "mapping_contract_sha256": openmm_receipt["mapping_contract_sha256"],
            "energy_force_protocol_sha256": openmm_receipt[
                "energy_force_protocol_sha256"
            ],
            "predefined_thresholds": openmm_receipt["predefined_thresholds"],
            "cases": openmm_cases,
            "summary": openmm_receipt["summary"],
            "status": openmm_receipt["status"],
        }
    )


def _crosscheck_minimization_traces(
    engine_receipt: Mapping[str, Any],
    openmm_receipt: Mapping[str, Any],
) -> str:
    engine_cases = engine_receipt.get("case_results")
    source_traces = openmm_receipt.get("source_operational_traces")
    openmm_cases = openmm_receipt.get("cases")
    if (
        not isinstance(engine_cases, list)
        or not isinstance(source_traces, list)
        or not isinstance(openmm_cases, list)
        or len(engine_cases) != 14
        or len(source_traces) != 14
        or len(openmm_cases) != 14
    ):
        raise OpenMMReferenceResultReviewError(
            "minimization receipt trace coverage is incomplete"
        )
    for engine_case, source_trace, openmm_case in zip(
        engine_cases, source_traces, openmm_cases, strict=True
    ):
        if (
            not isinstance(engine_case, Mapping)
            or not isinstance(source_trace, Mapping)
            or not isinstance(openmm_case, Mapping)
        ):
            raise OpenMMReferenceResultReviewError(
                "minimization receipt case or trace row is invalid"
            )
        traces = engine_case.get("coordinate_traces")
        if not isinstance(traces, list) or len(traces) != 2:
            raise OpenMMReferenceResultReviewError(
                "minimization Engine receipt omitted coordinate traces"
            )
        operational = traces[0]
        if not isinstance(operational, Mapping) or dict(operational) != dict(
            source_trace
        ):
            raise OpenMMReferenceResultReviewError(
                "OpenMM source trace is not the retained Engine operational trace"
            )
        # The runner intentionally hashes ``materialized.to_dict()`` (which
        # includes the materializer's own runtime digest), while the OpenMM
        # mapping stores that inner materializer digest.  Each nested verifier
        # checks its respective identity; the exact retained trace is the
        # cross-lane bridge, so the two differently scoped digests are bound
        # but must not be compared as equal.
        identity_mismatches = [
            name
            for name, left, right in (
                (
                    "case_id",
                    engine_case.get("case_id"),
                    openmm_case.get("case_id"),
                ),
                (
                    "case_input_sha256",
                    engine_case.get("case_input_sha256"),
                    openmm_case.get("case_input_sha256"),
                ),
                (
                    "source_trace_sha256",
                    source_trace.get("trace_sha256"),
                    openmm_case.get("source_trace_sha256"),
                ),
            )
            if left != right
        ]
        if identity_mismatches:
            raise OpenMMReferenceResultReviewError(
                "minimization case or trace identity is cross-wired: "
                + ",".join(identity_mismatches)
            )
        if engine_case.get("expected_outcome") == "pass":
            if (
                openmm_case.get("disposition")
                != "evaluated_openmm_reference_trace_coordinates"
                or openmm_case.get("openmm_evaluation_performed") is not True
                or openmm_case.get("trace_step_count")
                != source_trace.get("trace_length")
            ):
                raise OpenMMReferenceResultReviewError(
                    "passing minimization trace is not fully evaluated by OpenMM"
                )
        elif engine_case.get("expected_outcome") == "fail_closed":
            if (
                openmm_case.get("disposition") != "not_applicable_engine_contract"
                or openmm_case.get("expected_error_code")
                != engine_case.get("expected_error_code")
                or openmm_case.get("openmm_evaluation_performed") is not False
                or openmm_case.get("trace_step_count") != 0
                or openmm_case.get("steps") != []
            ):
                raise OpenMMReferenceResultReviewError(
                    "minimization failure disposition is cross-wired"
                )
        else:
            raise OpenMMReferenceResultReviewError(
                "minimization expected outcome is invalid"
            )
    return _sha256(
        {
            "mapping_contract_sha256": openmm_receipt["mapping_contract_sha256"],
            "minimization_protocol_sha256": openmm_receipt[
                "minimization_protocol_sha256"
            ],
            "predefined_thresholds": openmm_receipt["predefined_thresholds"],
            "source_operational_traces": source_traces,
            "cases": openmm_cases,
            "summary": openmm_receipt["summary"],
            "status": openmm_receipt["status"],
        }
    )


def _native_minimization_physics_projection(
    native_receipt: Mapping[str, Any],
) -> tuple[str, tuple[str, ...]]:
    cases = native_receipt.get("cases")
    summary = native_receipt.get("summary")
    if (
        not isinstance(cases, list)
        or len(cases) != 14
        or not isinstance(summary, Mapping)
        or summary.get("evaluated_case_count") != 8
        or summary.get("not_applicable_engine_contract_case_count") != 6
        or summary.get("complete_failure_inclusive_comparison") is not True
        or summary.get("all_failure_rows_retained") is not True
    ):
        raise OpenMMReferenceResultReviewError(
            "native minimization coverage or failure denominator is incomplete"
        )
    failed_case_ids = tuple(
        row["case_id"]
        for row in cases
        if isinstance(row, Mapping)
        and row.get("native_endpoint_executed") is True
        and row.get("case_passed_predefined_endpoint_health") is False
    )
    passed_count = summary.get("endpoint_health_passed_case_count")
    if (
        type(passed_count) is not int
        or passed_count + len(failed_case_ids) != 8
        or summary.get("same_coordinate_mapping_passed_case_count") != 8
        or summary.get("energy_nonincreasing_case_count") != 8
    ):
        raise OpenMMReferenceResultReviewError(
            "native minimization endpoint-health disposition is inconsistent"
        )
    status = native_receipt.get("status")
    all_health_passed = summary.get("all_predefined_endpoint_health_metrics_passed")
    if (
        status == "accepted_offline_native_endpoint_comparison"
        and (all_health_passed is not True or failed_case_ids)
    ) or (
        status == "rejected_offline_native_endpoint_comparison"
        and (all_health_passed is not False or not failed_case_ids)
    ):
        raise OpenMMReferenceResultReviewError(
            "native minimization status does not match endpoint health"
        )
    return (
        _sha256(
            {
                "configuration_sha256": native_receipt["configuration_sha256"],
                "mapping_contract_sha256": native_receipt["mapping_contract_sha256"],
                "minimization_protocol_sha256": native_receipt[
                    "minimization_protocol_sha256"
                ],
                "cases": cases,
                "summary": dict(summary),
                "status": status,
            }
        ),
        failed_case_ids,
    )


def _fixed_born_disposition_physics_projection(
    disposition_receipt: Mapping[str, Any],
    *,
    native_failed_case_ids: tuple[str, ...],
) -> tuple[str, str]:
    cases = disposition_receipt.get("cases")
    summary = disposition_receipt.get("summary")
    if (
        not isinstance(cases, list)
        or len(cases) != 2
        or not isinstance(summary, Mapping)
        or tuple(row.get("case_id") for row in cases) != native_failed_case_ids
        or summary.get("exact_failed_case_scope_retained") is not True
        or summary.get("failure_disposition_complete") is not True
        or summary.get("frozen_native_endpoint_health_failure_resolved") is not False
        or summary.get("causal_root_cause_proven") is not False
        or summary.get("cross_alias_physics_projection_exactly_equal") is not True
        or summary.get("cross_alias_classification_exactly_equal") is not True
        or disposition_receipt.get("status") != "accepted_failure_disposition_evidence"
    ):
        raise OpenMMReferenceResultReviewError(
            "fixed-Born failure disposition coverage or claim boundary is invalid"
        )
    classification = summary.get("classification")
    if classification != "final_constraint_projection_tradeoff_observed":
        raise OpenMMReferenceResultReviewError(
            "fixed-Born failure disposition classification drifted"
        )
    return (
        _sha256(
            {
                "configuration_sha256": disposition_receipt["configuration_sha256"],
                "source_materialization_sha256": disposition_receipt[
                    "source_materialization_sha256"
                ],
                "source_native_receipt_sha256": disposition_receipt[
                    "source_native_receipt_sha256"
                ],
                "case_physics_projection_sha256s": [
                    row["case_physics_projection_sha256"] for row in cases
                ],
                "summary": dict(summary),
                "status": disposition_receipt["status"],
            }
        ),
        classification,
    )


def _contract_projection() -> dict[str, Any]:
    return {
        "schema_id": OPENMM_REFERENCE_RESULT_REVIEW_CONTRACT_SCHEMA_ID,
        "contract_id": OPENMM_REFERENCE_RESULT_REVIEW_CONTRACT_ID,
        "contract_version": OPENMM_REFERENCE_RESULT_REVIEW_CONTRACT_VERSION,
        "frozen_at_utc": OPENMM_REFERENCE_RESULT_REVIEW_CONTRACT_FROZEN_AT_UTC,
        "superseded_contract_sha256": (
            FROZEN_LEGACY_OPENMM_REFERENCE_RESULT_REVIEW_CONTRACT_SHA256_V3
        ),
        "legacy_contract_chain_sha256s": [
            FROZEN_LEGACY_OPENMM_REFERENCE_RESULT_REVIEW_CONTRACT_SHA256_V2,
            FROZEN_LEGACY_OPENMM_REFERENCE_RESULT_REVIEW_CONTRACT_SHA256_V1,
        ],
        "refreeze_reason": (
            "conditionally_binds_fixed_born_failure_disposition_without_"
            "promoting_rejected_native_endpoint_health"
        ),
        "oracle_id": OPENMM_REFERENCE_OFFLINE_ORACLE_ID,
        "bound_contracts": {
            "openmm_mapping_contract_sha256": (
                FROZEN_OPENMM_REFERENCE_MAPPING_CONTRACT_SHA256
            ),
            "energy_force_result_review_contract_sha256": (
                FROZEN_REFERENCE_VALIDATION_RESULT_REVIEW_CONTRACT_SHA256
            ),
            "minimization_result_review_contract_sha256": (
                FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_CONTRACT_SHA256
            ),
            "openmm_energy_force_receipt_schema_id": (
                OPENMM_REFERENCE_ENERGY_FORCE_RECEIPT_SCHEMA_ID
            ),
            "openmm_minimization_trace_receipt_schema_id": (
                OPENMM_REFERENCE_MINIMIZATION_TRACE_RECEIPT_SCHEMA_ID
            ),
            "openmm_reference_materialization_schema_id": (
                OPENMM_REFERENCE_MATERIALIZATION_SCHEMA_ID
            ),
            "openmm_native_minimization_receipt_schema_id": (
                OPENMM_REFERENCE_NATIVE_MINIMIZATION_RECEIPT_SCHEMA_ID
            ),
            "openmm_native_minimization_configuration_sha256": (
                FROZEN_OPENMM_REFERENCE_NATIVE_MINIMIZATION_CONFIGURATION_SHA256
            ),
            "openmm_fixed_born_disposition_receipt_schema_id": (
                OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_RECEIPT_SCHEMA_ID
            ),
            "openmm_fixed_born_disposition_configuration_sha256": (
                FROZEN_OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_CONFIGURATION_SHA256
            ),
            "energy_force_upstream_signature_algorithm": "ed25519",
            "energy_force_upstream_trust_anchors_contain_public_keys_only": True,
            "private_or_symmetric_verification_keys_allowed": False,
        },
        "required_nested_outcomes": {
            "energy_force_result_review_accepted": True,
            "minimization_result_review_accepted": True,
            "openmm_energy_force_status": "accepted_offline_reference_agreement",
            "openmm_minimization_status": (
                "accepted_offline_reference_trace_agreement"
            ),
            "openmm_reference_materialization_status": (
                "accepted_offline_reference_materialization"
            ),
            "native_endpoint_status_derived_from_predefined_metrics": True,
            "accepted_review_requires_native_endpoint_status": (
                "accepted_offline_native_endpoint_comparison"
            ),
            "rejected_native_endpoint_requires_disposition_status": (
                "accepted_failure_disposition_evidence"
            ),
            "accepted_native_endpoint_requires_failure_disposition": False,
            "failure_disposition_complete_does_not_imply_endpoint_accepted": True,
            "energy_force_case_count": 27,
            "energy_force_variant_count": 59,
            "minimization_case_count": 14,
            "native_endpoint_evaluated_case_count": 8,
            "native_endpoint_not_applicable_case_count": 6,
            "all_failure_rows_retained": True,
        },
        "cross_binding_policy": {
            "same_code_commit_dependency_rows_and_seed_across_lanes": True,
            "distinct_lane_authorization_environment_result_and_review_ids": True,
            "same_author_scientific_reviewer_and_operator_across_lanes": True,
            "exact_energy_component_total_and_force_match": True,
            "analytic_openmm_comparison_retained_and_receipt_verified": True,
            "exact_minimization_operational_trace_match": True,
            "native_receipt_source_materialization_exactly_bound": True,
            "native_endpoint_failed_case_ids_retained": True,
            "native_physics_projection_host_comparable": True,
            "rejected_native_disposition_receipt_and_physics_exactly_bound": True,
            "accepted_native_endpoint_rejects_failure_specific_disposition_input": (
                True
            ),
            "runtime_mapping_source_host_cpu_session_and_custody_bound": True,
        },
        "signature_policy": {
            "algorithm": OPENMM_REFERENCE_RESULT_REVIEW_SIGNATURE_ALGORITHM,
            "maximum_validity_seconds": int(
                OPENMM_REFERENCE_RESULT_REVIEW_MAX_VALIDITY.total_seconds()
            ),
            "external_reviewer_distinct_from_all_nested_roles": True,
            "trusted_keys_are_out_of_band": True,
            "canonical_json_required": True,
            "revocation_and_supersession_inputs_required": True,
        },
        "required_check_ids": list(_REQUIRED_CHECK_IDS),
        "required_limitation_ids": list(_REQUIRED_LIMITATION_IDS),
        "claim_policy": {
            "single_host_external_oracle_comparison_may_be_verified_only_when_native_endpoint_health_is_accepted": True,
            "signed_rejected_review_retains_failed_native_case_ids": True,
            "signed_rejected_review_may_verify_failure_disposition_separately": True,
            "failure_disposition_completion_cannot_open_external_comparison_or_s0": (
                True
            ),
            "production_validation_evidence": False,
            "scientifically_validated": False,
            "s0_admission_authorized": False,
            "s1_admission_authorized": False,
            "parameter_fitting_authorized": False,
            "benchmark_validated": False,
            "product_qualified": False,
            "claim_safe": False,
        },
    }


def openmm_reference_result_review_contract_document() -> dict[str, Any]:
    projection = _contract_projection()
    document = {**projection, "contract_sha256": _sha256(projection)}
    if (
        FROZEN_OPENMM_REFERENCE_RESULT_REVIEW_CONTRACT_SHA256
        and document["contract_sha256"]
        != FROZEN_OPENMM_REFERENCE_RESULT_REVIEW_CONTRACT_SHA256
    ):
        raise OpenMMReferenceResultReviewError(
            "frozen OpenMM result-review contract SHA-256 drifted"
        )
    return document


def require_openmm_reference_result_review_contract_document(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise OpenMMReferenceResultReviewError(
            "OpenMM result-review contract must be a mapping"
        )
    observed = dict(value)
    expected = openmm_reference_result_review_contract_document()
    if observed != expected:
        raise OpenMMReferenceResultReviewError(
            "OpenMM result-review contract does not match the frozen record"
        )
    return observed


def _verified_nested_evidence(
    *,
    energy_force_evidence: EnergyForceResultReviewEvidence,
    minimization_evidence: MinimizationResultReviewEvidence,
    openmm_energy_force_receipt: Mapping[str, Any],
    openmm_minimization_trace_receipt: Mapping[str, Any],
    openmm_reference_materialization: Mapping[str, Any],
    openmm_native_minimization_receipt: Mapping[str, Any],
    openmm_fixed_born_disposition_receipt: Mapping[str, Any] | None,
    expected_openmm_reference_materialization_sha256: str,
    expected_openmm_fixed_born_disposition_receipt_sha256: str | None,
    checked_at: datetime,
) -> dict[str, Any]:
    energy_receipt = _validated_energy_result_receipt(
        energy_force_evidence.result_receipt
    )
    minimization_receipt = _validated_minimization_result_receipt(
        minimization_evidence.result_receipt
    )
    energy_verification = energy_force_evidence.verify(checked_at=checked_at)
    minimization_verification = minimization_evidence.verify(checked_at=checked_at)
    if (
        not energy_verification.result_receipt_accepted
        or not minimization_verification.result_receipt_accepted
        or energy_verification.result_receipt_sha256 != energy_receipt["receipt_sha256"]
        or minimization_verification.result_receipt_sha256
        != minimization_receipt["receipt_sha256"]
    ):
        raise OpenMMReferenceResultReviewError(
            "nested Engine result review was not accepted or is cross-wired"
        )
    try:
        openmm_energy = require_openmm_reference_energy_force_receipt(
            openmm_energy_force_receipt
        )
        openmm_minimization = require_openmm_reference_minimization_trace_receipt(
            openmm_minimization_trace_receipt
        )
    except OpenMMReferenceReceiptError as exc:
        raise OpenMMReferenceResultReviewError(
            "OpenMM receipt verification failed"
        ) from exc
    if (
        openmm_energy["status"] != "accepted_offline_reference_agreement"
        or openmm_minimization["status"] != "accepted_offline_reference_trace_agreement"
        or openmm_energy["mapping_contract_sha256"]
        != openmm_minimization["mapping_contract_sha256"]
        or openmm_energy["runtime_identity"] != openmm_minimization["runtime_identity"]
        or openmm_energy["source_identity"] != openmm_minimization["source_identity"]
    ):
        raise OpenMMReferenceResultReviewError(
            "OpenMM receipts disagree on accepted status, mapping, runtime, or source"
        )
    expected_materialization_sha256 = _require_sha256(
        expected_openmm_reference_materialization_sha256,
        name="expected OpenMM reference materialization",
    )
    try:
        materialization = require_openmm_reference_materialization(
            openmm_reference_materialization
        )
        native_minimization = require_openmm_reference_native_minimization_receipt(
            openmm_native_minimization_receipt,
            source_materialization=materialization,
            expected_source_materialization_sha256=(expected_materialization_sha256),
        )
    except (
        OpenMMReferenceMaterializationError,
        OpenMMReferenceNativeMinimizationError,
    ) as exc:
        raise OpenMMReferenceResultReviewError(
            "OpenMM materialization or native minimization verification failed"
        ) from exc
    if (
        materialization["materialization_sha256"] != expected_materialization_sha256
        or materialization["status"] != "accepted_offline_reference_materialization"
        or materialization["energy_force_receipt"] != openmm_energy
        or materialization["minimization_trace_receipt"] != openmm_minimization
        or native_minimization["source_materialization_sha256"]
        != materialization["materialization_sha256"]
        or native_minimization["source_minimization_trace_receipt_sha256"]
        != openmm_minimization["receipt_sha256"]
        or native_minimization["runtime_identity_sha256"]
        != openmm_energy["runtime_identity"]["runtime_identity_sha256"]
        or native_minimization["mapping_contract_sha256"]
        != openmm_energy["mapping_contract_sha256"]
        or native_minimization["configuration_sha256"]
        != FROZEN_OPENMM_REFERENCE_NATIVE_MINIMIZATION_CONFIGURATION_SHA256
    ):
        raise OpenMMReferenceResultReviewError(
            "OpenMM materialization or native minimization ancestry is cross-wired"
        )
    energy_dependency_rows = _result_receipt_dependency_rows(energy_receipt)
    minimization_dependency_rows = _result_receipt_dependency_rows(minimization_receipt)
    if energy_dependency_rows != minimization_dependency_rows:
        raise OpenMMReferenceResultReviewError(
            "Engine dependency rows differ across validation lanes"
        )
    code_commit_sha = _require_commit_sha(
        energy_receipt.get("code_commit_sha"), name="energy-force code commit"
    )
    seed = energy_receipt.get("seed")
    if (
        minimization_receipt.get("code_commit_sha") != code_commit_sha
        or minimization_receipt.get("seed") != seed
        or type(seed) is not int
        or seed < 0
    ):
        raise OpenMMReferenceResultReviewError(
            "Engine commit or seed differs across validation lanes"
        )
    distinct_lane_values = (
        (
            energy_receipt.get("authorization_nonce_sha256"),
            minimization_receipt.get("authorization_nonce_sha256"),
            "authorization nonce",
        ),
        (
            energy_receipt.get("execution_environment_receipt_sha256"),
            minimization_receipt.get("execution_environment_receipt_sha256"),
            "environment receipt",
        ),
        (
            energy_receipt.get("receipt_sha256"),
            minimization_receipt.get("receipt_sha256"),
            "result receipt",
        ),
        (
            energy_verification.attestation_sha256,
            minimization_verification.attestation_sha256,
            "result-review attestation",
        ),
    )
    for left, right, name in distinct_lane_values:
        _require_sha256(left, name=f"energy-force {name}")
        _require_sha256(right, name=f"minimization {name}")
        if left == right:
            raise OpenMMReferenceResultReviewError(
                f"validation lane {name} identities must be distinct"
            )
    shared_roles = (
        (
            energy_verification.implementation_author_identity_sha256,
            minimization_verification.implementation_author_identity_sha256,
            "implementation author",
        ),
        (
            energy_verification.independent_scientific_reviewer_identity_sha256,
            minimization_verification.independent_scientific_reviewer_identity_sha256,
            "scientific reviewer",
        ),
        (
            energy_verification.authorization_operator_identity_sha256,
            minimization_verification.authorization_operator_identity_sha256,
            "authorization operator",
        ),
    )
    for left, right, name in shared_roles:
        if left != right:
            raise OpenMMReferenceResultReviewError(
                f"{name} identity differs across validation lanes"
            )
    energy_physics = _crosscheck_energy_force_outputs(energy_receipt, openmm_energy)
    minimization_physics = _crosscheck_minimization_traces(
        minimization_receipt, openmm_minimization
    )
    native_physics, native_failed_case_ids = _native_minimization_physics_projection(
        native_minimization
    )
    disposition: dict[str, Any] | None = None
    disposition_physics: str | None = None
    disposition_classification: str | None = None
    if native_minimization["status"] == ("rejected_offline_native_endpoint_comparison"):
        if (
            not isinstance(openmm_fixed_born_disposition_receipt, Mapping)
            or expected_openmm_fixed_born_disposition_receipt_sha256 is None
        ):
            raise OpenMMReferenceResultReviewError(
                "rejected native minimization requires fixed-Born disposition evidence"
            )
        expected_disposition_sha256 = _require_sha256(
            expected_openmm_fixed_born_disposition_receipt_sha256,
            name="expected fixed-Born disposition receipt",
        )
        try:
            disposition = require_openmm_reference_fixed_born_disposition_receipt(
                openmm_fixed_born_disposition_receipt,
                source_materialization=materialization,
                source_native_receipt=native_minimization,
                expected_source_materialization_sha256=(
                    expected_materialization_sha256
                ),
                expected_source_native_receipt_sha256=(
                    native_minimization["receipt_sha256"]
                ),
            )
        except OpenMMReferenceFixedBornDispositionError as exc:
            raise OpenMMReferenceResultReviewError(
                "fixed-Born disposition receipt verification failed"
            ) from exc
        if (
            disposition["receipt_sha256"] != expected_disposition_sha256
            or disposition["configuration_sha256"]
            != FROZEN_OPENMM_REFERENCE_FIXED_BORN_DISPOSITION_CONFIGURATION_SHA256
            or disposition["source_materialization_sha256"]
            != materialization["materialization_sha256"]
            or disposition["source_native_receipt_sha256"]
            != native_minimization["receipt_sha256"]
            or disposition["runtime_identity_sha256"]
            != native_minimization["runtime_identity_sha256"]
        ):
            raise OpenMMReferenceResultReviewError(
                "fixed-Born disposition receipt ancestry is cross-wired"
            )
        disposition_physics, disposition_classification = (
            _fixed_born_disposition_physics_projection(
                disposition,
                native_failed_case_ids=native_failed_case_ids,
            )
        )
    elif (
        openmm_fixed_born_disposition_receipt is not None
        or expected_openmm_fixed_born_disposition_receipt_sha256 is not None
    ):
        raise OpenMMReferenceResultReviewError(
            "accepted native minimization forbids failure-specific disposition input"
        )
    runtime_identity = openmm_energy["runtime_identity"]
    source_identity = openmm_energy["source_identity"]
    return {
        "energy_receipt": energy_receipt,
        "minimization_receipt": minimization_receipt,
        "energy_verification": energy_verification,
        "minimization_verification": minimization_verification,
        "openmm_energy": openmm_energy,
        "openmm_minimization": openmm_minimization,
        "openmm_materialization": materialization,
        "openmm_native_minimization": native_minimization,
        "openmm_fixed_born_disposition": disposition,
        "code_commit_sha": code_commit_sha,
        "seed": seed,
        "dependency_rows": energy_dependency_rows,
        "energy_force_physics_projection_sha256": energy_physics,
        "minimization_physics_projection_sha256": minimization_physics,
        "native_minimization_physics_projection_sha256": native_physics,
        "fixed_born_disposition_physics_projection_sha256": (disposition_physics),
        "fixed_born_failure_disposition_classification": (disposition_classification),
        "native_endpoint_health_failed_case_ids": native_failed_case_ids,
        "runtime_identity_sha256": _require_sha256(
            runtime_identity.get("runtime_identity_sha256"),
            name="OpenMM runtime identity",
        ),
        "source_identity_sha256": _require_sha256(
            source_identity.get("source_identity_sha256"),
            name="OpenMM source identity",
        ),
    }


def _attestation_projection(
    *,
    nested: Mapping[str, Any],
    enrolled_host_identity_sha256: str,
    cpu_identity_sha256: str,
    production_evidence_session_sha256: str,
    custody_terminal_sha256: str,
    external_result_reviewer_identity_sha256: str,
    external_result_reviewer_key_id: str,
    reviewed_at_utc: str,
    expires_at_utc: str,
    nonce_sha256: str,
) -> dict[str, Any]:
    energy_receipt = nested["energy_receipt"]
    minimization_receipt = nested["minimization_receipt"]
    energy_verification = nested["energy_verification"]
    minimization_verification = nested["minimization_verification"]
    openmm_energy = nested["openmm_energy"]
    openmm_minimization = nested["openmm_minimization"]
    openmm_materialization = nested["openmm_materialization"]
    openmm_native_minimization = nested["openmm_native_minimization"]
    openmm_fixed_born_disposition = nested["openmm_fixed_born_disposition"]
    native_summary = openmm_native_minimization["summary"]
    native_status = openmm_native_minimization["status"]
    native_accepted = (
        native_status == "accepted_offline_native_endpoint_comparison"
        and native_summary["all_predefined_endpoint_health_metrics_passed"] is True
        and not nested["native_endpoint_health_failed_case_ids"]
    )
    reviewer = _require_sha256(
        external_result_reviewer_identity_sha256,
        name="external result reviewer identity",
    )
    nested_roles = {
        energy_verification.implementation_author_identity_sha256,
        energy_verification.independent_scientific_reviewer_identity_sha256,
        energy_verification.authorization_operator_identity_sha256,
        energy_verification.independent_result_reviewer_identity_sha256,
        minimization_verification.independent_result_reviewer_identity_sha256,
    }
    if reviewer in nested_roles:
        raise OpenMMReferenceResultReviewError(
            "external result reviewer must be distinct from every nested role"
        )
    reviewed = _parse_utc(reviewed_at_utc, name="reviewed_at")
    nested_times = [
        _parse_utc(openmm_energy["observed_at_utc"], name="OpenMM observed_at"),
        _parse_utc(openmm_minimization["observed_at_utc"], name="OpenMM observed_at"),
        _parse_utc(
            openmm_materialization["observed_at_utc"],
            name="OpenMM materialization observed_at",
        ),
        _parse_utc(
            openmm_native_minimization["observed_at_utc"],
            name="OpenMM native minimization observed_at",
        ),
        _parse_utc(
            energy_verification.reviewed_at_utc,
            name="energy-force review reviewed_at",
        ),
        _parse_utc(
            minimization_verification.reviewed_at_utc,
            name="minimization review reviewed_at",
        ),
    ]
    if openmm_fixed_born_disposition is not None:
        nested_times.append(
            _parse_utc(
                openmm_fixed_born_disposition["observed_at_utc"],
                name="fixed-Born disposition observed_at",
            )
        )
    latest_nested_time = max(nested_times)
    if reviewed < latest_nested_time:
        raise OpenMMReferenceResultReviewError(
            "external result review predates nested evidence"
        )
    expires = _parse_utc(expires_at_utc, name="expires_at")
    nested_expiry = min(
        _parse_utc(
            energy_verification.expires_at_utc,
            name="energy-force review expires_at",
        ),
        _parse_utc(
            minimization_verification.expires_at_utc,
            name="minimization review expires_at",
        ),
    )
    if expires > nested_expiry:
        raise OpenMMReferenceResultReviewError(
            "external result review outlives a nested result review"
        )
    return {
        "schema_id": OPENMM_REFERENCE_RESULT_REVIEW_ATTESTATION_SCHEMA_ID,
        "contract_sha256": openmm_reference_result_review_contract_document()[
            "contract_sha256"
        ],
        "oracle_id": OPENMM_REFERENCE_OFFLINE_ORACLE_ID,
        "mapping_contract_sha256": FROZEN_OPENMM_REFERENCE_MAPPING_CONTRACT_SHA256,
        "host_binding": {
            "enrolled_host_identity_sha256": _require_sha256(
                enrolled_host_identity_sha256, name="enrolled host identity"
            ),
            "cpu_identity_sha256": _require_sha256(
                cpu_identity_sha256, name="CPU identity"
            ),
            "production_evidence_session_sha256": _require_sha256(
                production_evidence_session_sha256,
                name="production evidence session",
            ),
            "custody_terminal_sha256": _require_sha256(
                custody_terminal_sha256, name="custody terminal"
            ),
        },
        "engine_evidence": {
            "code_commit_sha": nested["code_commit_sha"],
            "dependency_rows": nested["dependency_rows"],
            "dependency_rows_sha256": _sha256(nested["dependency_rows"]),
            "seed": nested["seed"],
            "energy_force": {
                "result_receipt_sha256": energy_receipt["receipt_sha256"],
                "result_review_attestation_sha256": (
                    energy_verification.attestation_sha256
                ),
                "protocol_sha256": energy_receipt["protocol_sha256"],
                "authorization_nonce_sha256": energy_receipt[
                    "authorization_nonce_sha256"
                ],
                "execution_environment_receipt_sha256": energy_receipt[
                    "execution_environment_receipt_sha256"
                ],
                "source_manifest_sha256": energy_receipt["source_manifest_sha256"],
                "physics_projection_sha256": nested[
                    "energy_force_physics_projection_sha256"
                ],
            },
            "minimization": {
                "result_receipt_sha256": minimization_receipt["receipt_sha256"],
                "result_review_attestation_sha256": (
                    minimization_verification.attestation_sha256
                ),
                "protocol_sha256": minimization_receipt["protocol_sha256"],
                "authorization_nonce_sha256": minimization_receipt[
                    "authorization_nonce_sha256"
                ],
                "execution_environment_receipt_sha256": minimization_receipt[
                    "execution_environment_receipt_sha256"
                ],
                "source_manifest_sha256": minimization_receipt[
                    "source_manifest_sha256"
                ],
                "physics_projection_sha256": nested[
                    "minimization_physics_projection_sha256"
                ],
            },
        },
        "openmm_evidence": {
            "runtime_identity_sha256": nested["runtime_identity_sha256"],
            "source_identity_sha256": nested["source_identity_sha256"],
            "energy_force_receipt_sha256": openmm_energy["receipt_sha256"],
            "minimization_trace_receipt_sha256": openmm_minimization["receipt_sha256"],
            "reference_materialization_sha256": openmm_materialization[
                "materialization_sha256"
            ],
            "native_minimization_receipt_sha256": openmm_native_minimization[
                "receipt_sha256"
            ],
            "fixed_born_disposition_receipt_sha256": (
                None
                if openmm_fixed_born_disposition is None
                else openmm_fixed_born_disposition["receipt_sha256"]
            ),
            "native_minimization_configuration_sha256": (
                openmm_native_minimization["configuration_sha256"]
            ),
            "fixed_born_disposition_configuration_sha256": (
                None
                if openmm_fixed_born_disposition is None
                else openmm_fixed_born_disposition["configuration_sha256"]
            ),
            "native_minimization_physics_projection_sha256": nested[
                "native_minimization_physics_projection_sha256"
            ],
            "fixed_born_disposition_physics_projection_sha256": nested[
                "fixed_born_disposition_physics_projection_sha256"
            ],
            "energy_force_status": openmm_energy["status"],
            "minimization_status": openmm_minimization["status"],
            "reference_materialization_status": openmm_materialization["status"],
            "native_minimization_status": native_status,
            "native_minimization_summary_sha256": _sha256(native_summary),
            "native_endpoint_health_passed_case_count": native_summary[
                "endpoint_health_passed_case_count"
            ],
            "native_endpoint_health_failed_case_ids": list(
                nested["native_endpoint_health_failed_case_ids"]
            ),
            "fixed_born_failure_disposition_required": (
                openmm_fixed_born_disposition is not None
            ),
            "fixed_born_failure_disposition_verified": (
                openmm_fixed_born_disposition is not None
            ),
            "fixed_born_failure_disposition_complete": (
                False
                if openmm_fixed_born_disposition is None
                else openmm_fixed_born_disposition["summary"][
                    "failure_disposition_complete"
                ]
            ),
            "fixed_born_failure_disposition_status": (
                "not_applicable_native_endpoint_accepted"
                if openmm_fixed_born_disposition is None
                else openmm_fixed_born_disposition["status"]
            ),
            "fixed_born_failure_disposition_classification": nested[
                "fixed_born_failure_disposition_classification"
            ],
        },
        "role_binding": {
            "implementation_author_identity_sha256": (
                energy_verification.implementation_author_identity_sha256
            ),
            "independent_scientific_reviewer_identity_sha256": (
                energy_verification.independent_scientific_reviewer_identity_sha256
            ),
            "authorization_operator_identity_sha256": (
                energy_verification.authorization_operator_identity_sha256
            ),
            "energy_force_result_reviewer_identity_sha256": (
                energy_verification.independent_result_reviewer_identity_sha256
            ),
            "minimization_result_reviewer_identity_sha256": (
                minimization_verification.independent_result_reviewer_identity_sha256
            ),
            "external_result_reviewer_identity_sha256": reviewer,
            "external_result_reviewer_key_id": _require_key_id(
                external_result_reviewer_key_id
            ),
            "all_required_role_separation_verified": True,
        },
        "reviewed_at_utc": reviewed_at_utc,
        "expires_at_utc": expires_at_utc,
        "nonce_sha256": _require_sha256(
            nonce_sha256, name="OpenMM result-review nonce"
        ),
        "accepted_check_ids": list(_REQUIRED_CHECK_IDS),
        "acknowledged_limitation_ids": list(_REQUIRED_LIMITATION_IDS),
        "failure_inclusive_native_minimization_evidence_verified": True,
        "failure_disposition_requirement_satisfied": (
            native_accepted or openmm_fixed_born_disposition is not None
        ),
        "external_oracle_comparison_verified": native_accepted,
        "result_review_outcome": (
            OPENMM_REFERENCE_RESULT_REVIEW_OUTCOME_ACCEPTED
            if native_accepted
            else OPENMM_REFERENCE_RESULT_REVIEW_OUTCOME_REJECTED
        ),
        "production_evidence_session_binding_attested": True,
        "external_custody_authenticity_proven_by_this_attestation": False,
        "two_host_reproducibility_verified": False,
        "production_validation_evidence": False,
        "scientifically_validated": False,
        "s0_admission_authorized": False,
        "s1_admission_authorized": False,
        "parameter_fitting_authorized": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "claim_safe": False,
        "superseded": False,
        "revoked": False,
    }


def build_signed_openmm_reference_result_review_attestation(
    *,
    energy_force_evidence: EnergyForceResultReviewEvidence,
    minimization_evidence: MinimizationResultReviewEvidence,
    openmm_energy_force_receipt: Mapping[str, Any],
    openmm_minimization_trace_receipt: Mapping[str, Any],
    openmm_reference_materialization: Mapping[str, Any],
    openmm_native_minimization_receipt: Mapping[str, Any],
    openmm_fixed_born_disposition_receipt: Mapping[str, Any] | None,
    expected_openmm_reference_materialization_sha256: str,
    expected_openmm_fixed_born_disposition_receipt_sha256: str | None,
    enrolled_host_identity_sha256: str,
    cpu_identity_sha256: str,
    production_evidence_session_sha256: str,
    custody_terminal_sha256: str,
    external_result_reviewer_identity_sha256: str,
    external_result_reviewer_key_id: str,
    signing_key: bytes | str,
    reviewed_at: datetime,
    expires_at: datetime,
    nonce_sha256: str,
) -> dict[str, Any]:
    """Freshly verify all nested inputs and sign one exact host projection."""

    reviewed_at_utc = _format_utc(reviewed_at, name="reviewed_at")
    expires_at_utc = _format_utc(expires_at, name="expires_at")
    reviewed = _parse_utc(reviewed_at_utc, name="reviewed_at")
    expires = _parse_utc(expires_at_utc, name="expires_at")
    if expires <= reviewed:
        raise OpenMMReferenceResultReviewError(
            "OpenMM result-review expiry must follow review time"
        )
    if expires - reviewed > OPENMM_REFERENCE_RESULT_REVIEW_MAX_VALIDITY:
        raise OpenMMReferenceResultReviewError(
            "OpenMM result-review validity exceeds the frozen maximum"
        )
    nested = _verified_nested_evidence(
        energy_force_evidence=energy_force_evidence,
        minimization_evidence=minimization_evidence,
        openmm_energy_force_receipt=openmm_energy_force_receipt,
        openmm_minimization_trace_receipt=openmm_minimization_trace_receipt,
        openmm_reference_materialization=openmm_reference_materialization,
        openmm_native_minimization_receipt=openmm_native_minimization_receipt,
        openmm_fixed_born_disposition_receipt=(openmm_fixed_born_disposition_receipt),
        expected_openmm_reference_materialization_sha256=(
            expected_openmm_reference_materialization_sha256
        ),
        expected_openmm_fixed_born_disposition_receipt_sha256=(
            expected_openmm_fixed_born_disposition_receipt_sha256
        ),
        checked_at=reviewed,
    )
    projection = _attestation_projection(
        nested=nested,
        enrolled_host_identity_sha256=enrolled_host_identity_sha256,
        cpu_identity_sha256=cpu_identity_sha256,
        production_evidence_session_sha256=production_evidence_session_sha256,
        custody_terminal_sha256=custody_terminal_sha256,
        external_result_reviewer_identity_sha256=(
            external_result_reviewer_identity_sha256
        ),
        external_result_reviewer_key_id=external_result_reviewer_key_id,
        reviewed_at_utc=reviewed_at_utc,
        expires_at_utc=expires_at_utc,
        nonce_sha256=nonce_sha256,
    )
    payload = {**projection, "attestation_sha256": _sha256(projection)}
    try:
        signature = sign_ed25519(
            _canonical_bytes(payload),
            _require_key(signing_key, name="OpenMM result-review signing key"),
        )
    except ReferenceMinimizationValidationEd25519Error as exc:
        raise OpenMMReferenceResultReviewError(
            "OpenMM result-review signing failed"
        ) from exc
    payload["signature"] = {
        "algorithm": OPENMM_REFERENCE_RESULT_REVIEW_SIGNATURE_ALGORITHM,
        "key_id": _require_key_id(external_result_reviewer_key_id),
        "value": signature,
    }
    return payload


def verify_signed_openmm_reference_result_review_attestation(
    source: str | bytes | Mapping[str, Any],
    *,
    energy_force_evidence: EnergyForceResultReviewEvidence,
    minimization_evidence: MinimizationResultReviewEvidence,
    openmm_energy_force_receipt: Mapping[str, Any],
    openmm_minimization_trace_receipt: Mapping[str, Any],
    openmm_reference_materialization: Mapping[str, Any],
    openmm_native_minimization_receipt: Mapping[str, Any],
    openmm_fixed_born_disposition_receipt: Mapping[str, Any] | None,
    expected_openmm_reference_materialization_sha256: str,
    expected_openmm_fixed_born_disposition_receipt_sha256: str | None,
    expected_enrolled_host_identity_sha256: str,
    expected_cpu_identity_sha256: str,
    expected_production_evidence_session_sha256: str,
    expected_custody_terminal_sha256: str,
    trusted_external_result_reviewer_keys: Mapping[
        str, OpenMMReferenceResultReviewerTrustAnchor
    ],
    checked_at: datetime,
    revoked_openmm_energy_force_receipt_sha256s: Sequence[str],
    superseded_openmm_energy_force_receipt_sha256s: Sequence[str],
    revoked_openmm_minimization_trace_receipt_sha256s: Sequence[str],
    superseded_openmm_minimization_trace_receipt_sha256s: Sequence[str],
    revoked_openmm_reference_materialization_sha256s: Sequence[str],
    superseded_openmm_reference_materialization_sha256s: Sequence[str],
    revoked_openmm_native_minimization_receipt_sha256s: Sequence[str],
    superseded_openmm_native_minimization_receipt_sha256s: Sequence[str],
    revoked_openmm_fixed_born_disposition_receipt_sha256s: Sequence[str],
    superseded_openmm_fixed_born_disposition_receipt_sha256s: Sequence[str],
    revoked_result_review_attestation_sha256s: Sequence[str],
    superseded_result_review_attestation_sha256s: Sequence[str],
) -> OpenMMReferenceResultReviewVerification:
    """Verify nested evidence, canonical projection, Ed25519, and current state."""

    checked_at_utc = _parse_utc(
        _format_utc(checked_at, name="checked_at"), name="checked_at"
    )
    loaded = _load_attestation(source)
    signature = loaded.pop("signature", None)
    attestation_sha256 = loaded.pop("attestation_sha256", None)
    if (
        not isinstance(signature, Mapping)
        or set(signature) != {"algorithm", "key_id", "value"}
        or signature.get("algorithm")
        != OPENMM_REFERENCE_RESULT_REVIEW_SIGNATURE_ALGORITHM
    ):
        raise OpenMMReferenceResultReviewError(
            "OpenMM result-review signature envelope is invalid"
        )
    observed_attestation = _require_sha256(
        attestation_sha256, name="OpenMM result-review attestation"
    )
    if observed_attestation != _sha256(loaded):
        raise OpenMMReferenceResultReviewError(
            "OpenMM result-review attestation digest mismatch"
        )
    revoked_reviews = _external_sha256_set(
        revoked_result_review_attestation_sha256s,
        name="revoked OpenMM result-review attestation",
    )
    superseded_reviews = _external_sha256_set(
        superseded_result_review_attestation_sha256s,
        name="superseded OpenMM result-review attestation",
    )
    if observed_attestation in revoked_reviews:
        raise OpenMMReferenceResultReviewError(
            "OpenMM result-review attestation is externally revoked"
        )
    if observed_attestation in superseded_reviews:
        raise OpenMMReferenceResultReviewError(
            "OpenMM result-review attestation is externally superseded"
        )
    key_id = _require_key_id(signature.get("key_id"))
    anchor = trusted_external_result_reviewer_keys.get(key_id)
    if anchor is None or not isinstance(
        anchor, OpenMMReferenceResultReviewerTrustAnchor
    ):
        raise OpenMMReferenceResultReviewError(
            "OpenMM result-review key is not trusted"
        )
    role_binding = loaded.get("role_binding")
    if (
        not isinstance(role_binding, Mapping)
        or role_binding.get("external_result_reviewer_identity_sha256")
        != anchor.reviewer_identity_sha256
        or role_binding.get("external_result_reviewer_key_id") != key_id
    ):
        raise OpenMMReferenceResultReviewError(
            "OpenMM result-review signer identity is cross-wired"
        )
    signed_payload = {**loaded, "attestation_sha256": observed_attestation}
    try:
        verified = verify_ed25519(
            _canonical_bytes(signed_payload),
            signature.get("value"),
            anchor.verification_key,
        )
    except ReferenceMinimizationValidationEd25519Error as exc:
        raise OpenMMReferenceResultReviewError(
            "OpenMM result-review signature verifier is unavailable"
        ) from exc
    if not verified:
        raise OpenMMReferenceResultReviewError(
            "OpenMM result-review signature verification failed"
        )
    reviewed_at = _parse_utc(loaded.get("reviewed_at_utc"), name="reviewed_at")
    expires_at = _parse_utc(loaded.get("expires_at_utc"), name="expires_at")
    if (
        expires_at <= reviewed_at
        or expires_at - reviewed_at > OPENMM_REFERENCE_RESULT_REVIEW_MAX_VALIDITY
        or checked_at_utc < reviewed_at
        or checked_at_utc > expires_at
    ):
        raise OpenMMReferenceResultReviewError(
            "OpenMM result-review attestation is not currently valid"
        )
    nested = _verified_nested_evidence(
        energy_force_evidence=energy_force_evidence,
        minimization_evidence=minimization_evidence,
        openmm_energy_force_receipt=openmm_energy_force_receipt,
        openmm_minimization_trace_receipt=openmm_minimization_trace_receipt,
        openmm_reference_materialization=openmm_reference_materialization,
        openmm_native_minimization_receipt=openmm_native_minimization_receipt,
        openmm_fixed_born_disposition_receipt=(openmm_fixed_born_disposition_receipt),
        expected_openmm_reference_materialization_sha256=(
            expected_openmm_reference_materialization_sha256
        ),
        expected_openmm_fixed_born_disposition_receipt_sha256=(
            expected_openmm_fixed_born_disposition_receipt_sha256
        ),
        checked_at=checked_at_utc,
    )
    openmm_energy_hash = nested["openmm_energy"]["receipt_sha256"]
    openmm_minimization_hash = nested["openmm_minimization"]["receipt_sha256"]
    openmm_materialization_hash = nested["openmm_materialization"][
        "materialization_sha256"
    ]
    openmm_native_minimization_hash = nested["openmm_native_minimization"][
        "receipt_sha256"
    ]
    revocation_rows: list[tuple[str, Sequence[str], Sequence[str], str]] = [
        (
            openmm_energy_hash,
            revoked_openmm_energy_force_receipt_sha256s,
            superseded_openmm_energy_force_receipt_sha256s,
            "OpenMM energy-force receipt",
        ),
        (
            openmm_minimization_hash,
            revoked_openmm_minimization_trace_receipt_sha256s,
            superseded_openmm_minimization_trace_receipt_sha256s,
            "OpenMM minimization trace receipt",
        ),
        (
            openmm_materialization_hash,
            revoked_openmm_reference_materialization_sha256s,
            superseded_openmm_reference_materialization_sha256s,
            "OpenMM reference materialization",
        ),
        (
            openmm_native_minimization_hash,
            revoked_openmm_native_minimization_receipt_sha256s,
            superseded_openmm_native_minimization_receipt_sha256s,
            "OpenMM native minimization receipt",
        ),
    ]
    disposition = nested["openmm_fixed_born_disposition"]
    if disposition is not None:
        revocation_rows.append(
            (
                disposition["receipt_sha256"],
                revoked_openmm_fixed_born_disposition_receipt_sha256s,
                superseded_openmm_fixed_born_disposition_receipt_sha256s,
                "OpenMM fixed-Born disposition receipt",
            )
        )
    elif (
        revoked_openmm_fixed_born_disposition_receipt_sha256s
        or superseded_openmm_fixed_born_disposition_receipt_sha256s
    ):
        _external_sha256_set(
            revoked_openmm_fixed_born_disposition_receipt_sha256s,
            name="revoked OpenMM fixed-Born disposition receipt",
        )
        _external_sha256_set(
            superseded_openmm_fixed_born_disposition_receipt_sha256s,
            name="superseded OpenMM fixed-Born disposition receipt",
        )
    for digest, revoked, superseded, name in revocation_rows:
        if digest in _external_sha256_set(revoked, name=f"revoked {name}"):
            raise OpenMMReferenceResultReviewError(f"{name} is externally revoked")
        if digest in _external_sha256_set(superseded, name=f"superseded {name}"):
            raise OpenMMReferenceResultReviewError(f"{name} is externally superseded")
    expected_projection = _attestation_projection(
        nested=nested,
        enrolled_host_identity_sha256=_require_sha256(
            expected_enrolled_host_identity_sha256,
            name="expected enrolled host identity",
        ),
        cpu_identity_sha256=_require_sha256(
            expected_cpu_identity_sha256, name="expected CPU identity"
        ),
        production_evidence_session_sha256=_require_sha256(
            expected_production_evidence_session_sha256,
            name="expected production evidence session",
        ),
        custody_terminal_sha256=_require_sha256(
            expected_custody_terminal_sha256,
            name="expected custody terminal",
        ),
        external_result_reviewer_identity_sha256=(anchor.reviewer_identity_sha256),
        external_result_reviewer_key_id=key_id,
        reviewed_at_utc=loaded["reviewed_at_utc"],
        expires_at_utc=loaded["expires_at_utc"],
        nonce_sha256=loaded.get("nonce_sha256"),
    )
    if loaded != expected_projection:
        raise OpenMMReferenceResultReviewError(
            "OpenMM result-review fields do not match the derived projection"
        )
    host = expected_projection["host_binding"]
    engine = expected_projection["engine_evidence"]
    openmm = expected_projection["openmm_evidence"]
    return OpenMMReferenceResultReviewVerification(
        contract_sha256=expected_projection["contract_sha256"],
        attestation_sha256=observed_attestation,
        enrolled_host_identity_sha256=host["enrolled_host_identity_sha256"],
        cpu_identity_sha256=host["cpu_identity_sha256"],
        production_evidence_session_sha256=host["production_evidence_session_sha256"],
        custody_terminal_sha256=host["custody_terminal_sha256"],
        energy_force_result_receipt_sha256=engine["energy_force"][
            "result_receipt_sha256"
        ],
        energy_force_result_review_attestation_sha256=engine["energy_force"][
            "result_review_attestation_sha256"
        ],
        minimization_result_receipt_sha256=engine["minimization"][
            "result_receipt_sha256"
        ],
        minimization_result_review_attestation_sha256=engine["minimization"][
            "result_review_attestation_sha256"
        ],
        openmm_energy_force_receipt_sha256=openmm["energy_force_receipt_sha256"],
        openmm_minimization_trace_receipt_sha256=openmm[
            "minimization_trace_receipt_sha256"
        ],
        openmm_reference_materialization_sha256=openmm[
            "reference_materialization_sha256"
        ],
        openmm_native_minimization_receipt_sha256=openmm[
            "native_minimization_receipt_sha256"
        ],
        openmm_fixed_born_disposition_receipt_sha256=openmm[
            "fixed_born_disposition_receipt_sha256"
        ],
        energy_force_physics_projection_sha256=engine["energy_force"][
            "physics_projection_sha256"
        ],
        minimization_physics_projection_sha256=engine["minimization"][
            "physics_projection_sha256"
        ],
        native_minimization_physics_projection_sha256=openmm[
            "native_minimization_physics_projection_sha256"
        ],
        fixed_born_disposition_physics_projection_sha256=openmm[
            "fixed_born_disposition_physics_projection_sha256"
        ],
        energy_force_source_manifest_sha256=engine["energy_force"][
            "source_manifest_sha256"
        ],
        minimization_source_manifest_sha256=engine["minimization"][
            "source_manifest_sha256"
        ],
        energy_force_execution_environment_receipt_sha256=engine["energy_force"][
            "execution_environment_receipt_sha256"
        ],
        minimization_execution_environment_receipt_sha256=engine["minimization"][
            "execution_environment_receipt_sha256"
        ],
        openmm_runtime_identity_sha256=openmm["runtime_identity_sha256"],
        openmm_source_identity_sha256=openmm["source_identity_sha256"],
        native_minimization_configuration_sha256=openmm[
            "native_minimization_configuration_sha256"
        ],
        fixed_born_disposition_configuration_sha256=openmm[
            "fixed_born_disposition_configuration_sha256"
        ],
        code_commit_sha=engine["code_commit_sha"],
        dependency_rows_sha256=engine["dependency_rows_sha256"],
        seed=engine["seed"],
        energy_force_authorization_nonce_sha256=engine["energy_force"][
            "authorization_nonce_sha256"
        ],
        minimization_authorization_nonce_sha256=engine["minimization"][
            "authorization_nonce_sha256"
        ],
        nonce_sha256=expected_projection["nonce_sha256"],
        implementation_author_identity_sha256=expected_projection["role_binding"][
            "implementation_author_identity_sha256"
        ],
        independent_scientific_reviewer_identity_sha256=expected_projection[
            "role_binding"
        ]["independent_scientific_reviewer_identity_sha256"],
        authorization_operator_identity_sha256=expected_projection["role_binding"][
            "authorization_operator_identity_sha256"
        ],
        energy_force_result_reviewer_identity_sha256=expected_projection[
            "role_binding"
        ]["energy_force_result_reviewer_identity_sha256"],
        minimization_result_reviewer_identity_sha256=expected_projection[
            "role_binding"
        ]["minimization_result_reviewer_identity_sha256"],
        external_result_reviewer_identity_sha256=(anchor.reviewer_identity_sha256),
        external_result_reviewer_key_id=key_id,
        reviewed_at_utc=expected_projection["reviewed_at_utc"],
        expires_at_utc=expected_projection["expires_at_utc"],
        failure_inclusive_native_minimization_evidence_verified=(
            expected_projection[
                "failure_inclusive_native_minimization_evidence_verified"
            ]
        ),
        native_minimization_status=openmm["native_minimization_status"],
        native_endpoint_health_passed_case_count=openmm[
            "native_endpoint_health_passed_case_count"
        ],
        native_endpoint_health_failed_case_ids=tuple(
            openmm["native_endpoint_health_failed_case_ids"]
        ),
        fixed_born_failure_disposition_required=openmm[
            "fixed_born_failure_disposition_required"
        ],
        fixed_born_failure_disposition_verified=openmm[
            "fixed_born_failure_disposition_verified"
        ],
        fixed_born_failure_disposition_complete=openmm[
            "fixed_born_failure_disposition_complete"
        ],
        fixed_born_failure_disposition_status=openmm[
            "fixed_born_failure_disposition_status"
        ],
        fixed_born_failure_disposition_classification=openmm[
            "fixed_born_failure_disposition_classification"
        ],
        external_oracle_comparison_verified=expected_projection[
            "external_oracle_comparison_verified"
        ],
        result_review_outcome=expected_projection["result_review_outcome"],
        production_validation_evidence=False,
        scientifically_validated=False,
        s0_admission_authorized=False,
        s1_admission_authorized=False,
        claim_safe=False,
        blockers=(
            _POST_ATTESTATION_BLOCKERS
            if expected_projection["result_review_outcome"]
            == OPENMM_REFERENCE_RESULT_REVIEW_OUTCOME_ACCEPTED
            else _REJECTED_NATIVE_ENDPOINT_BLOCKERS
        ),
    )


def openmm_reference_result_review_contract_decision() -> dict[str, Any]:
    contract = openmm_reference_result_review_contract_document()
    return {
        "contract_sha256": contract["contract_sha256"],
        "result_review_contract_implemented": True,
        "signed_result_review_attestation_present": False,
        "external_oracle_comparison_verified": False,
        "production_validation_evidence": False,
        "scientifically_validated": False,
        "s0_admission_authorized": False,
        "s1_admission_authorized": False,
        "parameter_fitting_authorized": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "claim_safe": False,
        "blockers": list(_CLOSED_GATE_BLOCKERS),
    }


__all__ = [
    "FROZEN_LEGACY_OPENMM_REFERENCE_RESULT_REVIEW_CONTRACT_SHA256_V1",
    "FROZEN_LEGACY_OPENMM_REFERENCE_RESULT_REVIEW_CONTRACT_SHA256_V2",
    "FROZEN_LEGACY_OPENMM_REFERENCE_RESULT_REVIEW_CONTRACT_SHA256_V3",
    "FROZEN_OPENMM_REFERENCE_RESULT_REVIEW_CONTRACT_SHA256",
    "OPENMM_REFERENCE_RESULT_REVIEW_ATTESTATION_SCHEMA_ID",
    "OPENMM_REFERENCE_RESULT_REVIEW_CONTRACT_ID",
    "OPENMM_REFERENCE_RESULT_REVIEW_CONTRACT_SCHEMA_ID",
    "OPENMM_REFERENCE_RESULT_REVIEW_CONTRACT_VERSION",
    "OPENMM_REFERENCE_RESULT_REVIEW_MAX_VALIDITY",
    "OPENMM_REFERENCE_RESULT_REVIEW_OUTCOME_ACCEPTED",
    "OPENMM_REFERENCE_RESULT_REVIEW_OUTCOME_REJECTED",
    "OPENMM_REFERENCE_RESULT_REVIEW_SIGNATURE_ALGORITHM",
    "EnergyForceResultReviewEvidence",
    "MinimizationResultReviewEvidence",
    "OpenMMReferenceResultReviewError",
    "OpenMMReferenceResultReviewVerification",
    "OpenMMReferenceResultReviewerTrustAnchor",
    "build_signed_openmm_reference_result_review_attestation",
    "openmm_reference_result_review_contract_decision",
    "openmm_reference_result_review_contract_document",
    "require_openmm_reference_result_review_contract_document",
    "verify_signed_openmm_reference_result_review_attestation",
]
