"""Two-host S0 production-evidence bundle and final human approval.

The bundle composes exactly two freshly verified OpenMM/Engine host reviews,
requires distinct execution identities and exact host-to-host physics equality,
and binds a final role-separated Ed25519 human approval.  No evidence, key, or
trust anchor is bundled by the repository; the static decision remains closed.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
from typing import Any, Mapping, Sequence

from betelgeuze_engine_v2.physics.reference_minimization_validation_ed25519 import (
    ReferenceMinimizationValidationEd25519Error,
    ed25519_public_key_bytes,
    sign_ed25519,
    verify_ed25519,
)
from .openmm_reference_result_review import (
    FROZEN_OPENMM_REFERENCE_RESULT_REVIEW_CONTRACT_SHA256,
    EnergyForceResultReviewEvidence,
    MinimizationResultReviewEvidence,
    OpenMMReferenceResultReviewError,
    OpenMMReferenceResultReviewerTrustAnchor,
    OpenMMReferenceResultReviewVerification,
    verify_signed_openmm_reference_result_review_attestation,
)


S0_PRODUCTION_EVIDENCE_BUNDLE_CONTRACT_SCHEMA_ID = (
    "betelgeuze.engine_v2_s0_production_evidence_bundle_contract/2.0.0"
)
S0_PRODUCTION_EVIDENCE_BUNDLE_APPROVAL_SCHEMA_ID = (
    "betelgeuze.engine_v2_s0_production_evidence_bundle_approval/2.0.0"
)
S0_PRODUCTION_EVIDENCE_BUNDLE_SIGNING_REQUEST_SCHEMA_ID = (
    "betelgeuze.engine_v2_s0_production_evidence_bundle_signing_request/2.0.0"
)
S0_PRODUCTION_EVIDENCE_BUNDLE_CONTRACT_ID = (
    "engine_v2_s0_two_host_reference_physics_evidence_bundle/2.0.0"
)
S0_PRODUCTION_EVIDENCE_BUNDLE_CONTRACT_VERSION = "2.0.0"
S0_PRODUCTION_EVIDENCE_BUNDLE_CONTRACT_FROZEN_AT_UTC = "2026-07-22T12:00:00Z"
S0_PRODUCTION_EVIDENCE_BUNDLE_SIGNATURE_ALGORITHM = "ed25519"
S0_PRODUCTION_EVIDENCE_BUNDLE_MAX_VALIDITY = timedelta(days=30)
S0_PRODUCTION_EVIDENCE_BUNDLE_MAX_TRANSPORT_BYTES = 4 * 1024 * 1024
S0_PRODUCTION_EVIDENCE_BUNDLE_HOST_COUNT = 2

FROZEN_S0_PRODUCTION_EVIDENCE_BUNDLE_CONTRACT_SHA256 = (
    "f39ed6d45da770174d3a7668c28274d56c57d414e5d138df767e633cbd79ba02"
)
FROZEN_LEGACY_S0_PRODUCTION_EVIDENCE_BUNDLE_CONTRACT_SHA256_V1 = (
    "8bd620d40ef373cb7584fe3e75e43fd7cee8495ab15418f84c4615efe127fd30"
)

S0_FINAL_REVIEW_OUTCOME_ACCEPTED = "accepted"
S0_FINAL_REVIEW_OUTCOME_REJECTED = "rejected"

_KEY_ID_RE = re.compile(r"\A[a-zA-Z0-9][a-zA-Z0-9._:/-]{0,127}\Z")

_REQUIRED_FINAL_CHECK_IDS = (
    "exactly_two_host_review_attestations_freshly_reverified",
    "host_cpu_session_custody_receipt_review_and_nonce_identities_distinct",
    "code_commit_source_dependency_runtime_and_seed_identities_equal",
    "energy_force_physics_projection_bitwise_equal_across_hosts",
    "minimization_coordinate_energy_force_trace_projection_bitwise_equal",
    "all_twenty_seven_cases_fifty_nine_variants_and_failure_rows_reviewed",
    "all_fourteen_minimization_cases_counts_traces_failures_and_restarts_reviewed",
    "openmm_mapping_units_atom_order_terms_fixed_born_and_outputs_reviewed",
    "external_custody_and_production_session_evidence_independently_reviewed",
    "final_reviewer_role_freshness_revocation_and_supersession_reviewed",
)
_REQUIRED_FINAL_LIMITATION_IDS = (
    "s0_acceptance_is_limited_to_frozen_synthetic_reference_protocols",
    "s0_acceptance_does_not_establish_real_chemistry_applicability",
    "s1_entry_does_not_authorize_a_validated_refinement_claim",
    "parameter_fitting_benchmark_product_and_customer_promotion_remain_closed",
    "openmm_is_an_offline_reference_and_not_a_customer_runtime_dependency",
)
_CLOSED_GATE_BLOCKERS = (
    "two_distinct_cpu_host_result_sets_not_provisioned",
    "signed_host_external_result_reviews_not_provisioned",
    "trusted_host_external_result_reviewer_keys_not_provisioned",
    "authenticated_external_production_custody_not_provisioned",
    "final_independent_human_s0_approval_not_provisioned",
    "trusted_final_s0_reviewer_key_not_provisioned",
    "s0_reference_physics_evidence_not_accepted",
    "s1_admission_not_authorized",
    "scientific_parameter_applicability_not_established",
    "product_integration_not_qualified",
)
_POST_ACCEPTANCE_BLOCKERS = (
    "s1_real_molecule_chemistry_validation_required",
    "supported_chemical_domain_not_established",
    "parameter_provenance_and_applicability_not_validated",
    "ood_recall_and_abstention_not_validated",
    "docking_benchmark_and_calibration_not_validated",
    "parameter_fitting_not_authorized",
    "product_integration_not_qualified",
)


class S0ProductionEvidenceBundleError(ValueError):
    """The S0 bundle, host evidence, trust input, or signature is invalid."""


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
        raise S0ProductionEvidenceBundleError(
            "S0 evidence value is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise S0ProductionEvidenceBundleError(
            f"{name} must be a lowercase SHA-256 digest"
        )
    return value


def _require_commit_sha(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 40
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise S0ProductionEvidenceBundleError(
            f"{name} must be a lowercase Git commit SHA"
        )
    return value


def _require_key_id(value: object) -> str:
    if not isinstance(value, str) or _KEY_ID_RE.fullmatch(value) is None:
        raise S0ProductionEvidenceBundleError("S0 reviewer key id is invalid")
    return value


def _require_key(value: bytes | str, *, name: str) -> bytes:
    if isinstance(value, bytes):
        raw = value
    elif isinstance(value, str):
        try:
            raw = bytes.fromhex(value)
        except ValueError as exc:
            raise S0ProductionEvidenceBundleError(f"{name} is not hexadecimal") from exc
    else:
        raise S0ProductionEvidenceBundleError(f"{name} must be bytes or hex")
    if len(raw) != 32:
        raise S0ProductionEvidenceBundleError(f"{name} must be 32 bytes")
    return raw


def _format_utc(value: datetime, *, name: str) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise S0ProductionEvidenceBundleError(f"{name} must be timezone-aware")
    normalized = value.astimezone(timezone.utc)
    if normalized.microsecond:
        raise S0ProductionEvidenceBundleError(f"{name} must use second resolution")
    return normalized.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_utc(value: object, *, name: str) -> datetime:
    if not isinstance(value, str):
        raise S0ProductionEvidenceBundleError(f"{name} must be second-resolution UTC")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise S0ProductionEvidenceBundleError(
            f"{name} must be second-resolution UTC"
        ) from exc


def _external_sha256_set(values: Sequence[str], *, name: str) -> set[str]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise S0ProductionEvidenceBundleError(f"{name} list is invalid")
    result = [_require_sha256(value, name=name) for value in values]
    if len(result) != len(set(result)):
        raise S0ProductionEvidenceBundleError(f"{name} list contains duplicates")
    return set(result)


def _external_key_id_set(values: Sequence[str], *, name: str) -> set[str]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise S0ProductionEvidenceBundleError(f"{name} list is invalid")
    result = [_require_key_id(value) for value in values]
    if len(result) != len(set(result)):
        raise S0ProductionEvidenceBundleError(f"{name} list contains duplicates")
    return set(result)


def _load_approval(source: str | bytes | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(source, Mapping):
        return dict(source)
    raw = source.encode("utf-8") if isinstance(source, str) else source
    if (
        not isinstance(raw, bytes)
        or not raw
        or len(raw) > S0_PRODUCTION_EVIDENCE_BUNDLE_MAX_TRANSPORT_BYTES
    ):
        raise S0ProductionEvidenceBundleError(
            "S0 approval transport is invalid or oversized"
        )

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise S0ProductionEvidenceBundleError(
                    "S0 approval transport contains a duplicate key"
                )
            result[key] = value
        return result

    try:
        loaded = json.loads(
            raw.decode("utf-8"), object_pairs_hook=reject_duplicate_keys
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise S0ProductionEvidenceBundleError(
            "S0 approval transport must be UTF-8 JSON"
        ) from exc
    if not isinstance(loaded, dict) or _canonical_bytes(loaded) != raw:
        raise S0ProductionEvidenceBundleError(
            "S0 approval transport is not canonical JSON"
        )
    return loaded


@dataclass(frozen=True, slots=True)
class S0HostEvidence:
    """Raw material and out-of-band trust used to verify one host review."""

    result_review_attestation: str | bytes | Mapping[str, Any]
    energy_force_evidence: EnergyForceResultReviewEvidence
    minimization_evidence: MinimizationResultReviewEvidence
    openmm_energy_force_receipt: Mapping[str, Any]
    openmm_minimization_trace_receipt: Mapping[str, Any]
    expected_enrolled_host_identity_sha256: str
    expected_cpu_identity_sha256: str
    expected_production_evidence_session_sha256: str
    expected_custody_terminal_sha256: str
    trusted_external_result_reviewer_keys: Mapping[
        str, OpenMMReferenceResultReviewerTrustAnchor
    ]
    revoked_openmm_energy_force_receipt_sha256s: Sequence[str] = ()
    superseded_openmm_energy_force_receipt_sha256s: Sequence[str] = ()
    revoked_openmm_minimization_trace_receipt_sha256s: Sequence[str] = ()
    superseded_openmm_minimization_trace_receipt_sha256s: Sequence[str] = ()
    revoked_result_review_attestation_sha256s: Sequence[str] = ()
    superseded_result_review_attestation_sha256s: Sequence[str] = ()

    def verify(
        self, *, checked_at: datetime
    ) -> OpenMMReferenceResultReviewVerification:
        return _verify_host_evidence(self, checked_at=checked_at)


def _verify_host_evidence(
    evidence: S0HostEvidence, *, checked_at: datetime
) -> OpenMMReferenceResultReviewVerification:
    """Invoke the frozen nested verifier without polymorphic dispatch."""

    if not isinstance(evidence, S0HostEvidence):
        raise S0ProductionEvidenceBundleError("S0 host evidence input is invalid")
    try:
        return verify_signed_openmm_reference_result_review_attestation(
            evidence.result_review_attestation,
            energy_force_evidence=evidence.energy_force_evidence,
            minimization_evidence=evidence.minimization_evidence,
            openmm_energy_force_receipt=evidence.openmm_energy_force_receipt,
            openmm_minimization_trace_receipt=(
                evidence.openmm_minimization_trace_receipt
            ),
            expected_enrolled_host_identity_sha256=(
                evidence.expected_enrolled_host_identity_sha256
            ),
            expected_cpu_identity_sha256=evidence.expected_cpu_identity_sha256,
            expected_production_evidence_session_sha256=(
                evidence.expected_production_evidence_session_sha256
            ),
            expected_custody_terminal_sha256=(
                evidence.expected_custody_terminal_sha256
            ),
            trusted_external_result_reviewer_keys=(
                evidence.trusted_external_result_reviewer_keys
            ),
            checked_at=checked_at,
            revoked_openmm_energy_force_receipt_sha256s=(
                evidence.revoked_openmm_energy_force_receipt_sha256s
            ),
            superseded_openmm_energy_force_receipt_sha256s=(
                evidence.superseded_openmm_energy_force_receipt_sha256s
            ),
            revoked_openmm_minimization_trace_receipt_sha256s=(
                evidence.revoked_openmm_minimization_trace_receipt_sha256s
            ),
            superseded_openmm_minimization_trace_receipt_sha256s=(
                evidence.superseded_openmm_minimization_trace_receipt_sha256s
            ),
            revoked_result_review_attestation_sha256s=(
                evidence.revoked_result_review_attestation_sha256s
            ),
            superseded_result_review_attestation_sha256s=(
                evidence.superseded_result_review_attestation_sha256s
            ),
        )
    except OpenMMReferenceResultReviewError as exc:
        raise S0ProductionEvidenceBundleError(
            "S0 host result review verification failed"
        ) from exc


@dataclass(frozen=True, slots=True)
class S0FinalReviewerTrustAnchor:
    """Out-of-band final human reviewer identity and raw Ed25519 public key."""

    reviewer_identity_sha256: str
    verification_key: bytes = field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "reviewer_identity_sha256",
            _require_sha256(
                self.reviewer_identity_sha256, name="trusted final S0 reviewer"
            ),
        )
        object.__setattr__(
            self,
            "verification_key",
            _require_key(
                self.verification_key,
                name="trusted final S0 reviewer verification key",
            ),
        )


@dataclass(frozen=True, slots=True)
class S0ProductionEvidenceBundleVerification:
    contract_sha256: str
    approval_sha256: str
    bundle_sha256: str
    host_review_attestation_sha256s: tuple[str, str]
    enrolled_host_identity_sha256s: tuple[str, str]
    cpu_identity_sha256s: tuple[str, str]
    code_commit_sha: str
    energy_force_source_manifest_sha256: str
    minimization_source_manifest_sha256: str
    dependency_rows_sha256: str
    openmm_runtime_identity_sha256: str
    openmm_source_identity_sha256: str
    energy_force_physics_projection_sha256: str
    minimization_physics_projection_sha256: str
    final_reviewer_identity_sha256: str
    final_reviewer_key_id: str
    reviewed_at_utc: str
    expires_at_utc: str
    two_cpu_host_reproducibility_verified: bool
    independent_external_implementation_comparison_verified: bool
    production_validation_evidence: bool
    reference_energy_force_protocol_validated: bool
    reference_minimization_protocol_validated: bool
    s0_accepted: bool
    s1_admission_authorized: bool
    scientifically_validated: bool
    chemical_applicability_validated: bool
    validated_refinement_claim_authorized: bool
    parameter_fitting_authorized: bool
    benchmark_validated: bool
    product_qualified: bool
    customer_execution_enabled: bool
    claim_safe: bool
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        for name, value in (
            ("contract", self.contract_sha256),
            ("approval", self.approval_sha256),
            ("bundle", self.bundle_sha256),
            ("code commit", self.code_commit_sha),
            ("energy-force source manifest", self.energy_force_source_manifest_sha256),
            ("minimization source manifest", self.minimization_source_manifest_sha256),
            ("dependency rows", self.dependency_rows_sha256),
            ("OpenMM runtime", self.openmm_runtime_identity_sha256),
            ("OpenMM source", self.openmm_source_identity_sha256),
            ("energy-force physics", self.energy_force_physics_projection_sha256),
            ("minimization physics", self.minimization_physics_projection_sha256),
            ("final reviewer", self.final_reviewer_identity_sha256),
        ):
            if name == "code commit":
                _require_commit_sha(value, name=name)
            else:
                _require_sha256(value, name=name)
        for name, values in (
            ("host review", self.host_review_attestation_sha256s),
            ("enrolled host", self.enrolled_host_identity_sha256s),
            ("CPU", self.cpu_identity_sha256s),
        ):
            if len(values) != 2 or len(set(values)) != 2:
                raise S0ProductionEvidenceBundleError(
                    f"verified {name} identities must contain two distinct values"
                )
            for value in values:
                _require_sha256(value, name=f"verified {name} identity")
        _require_key_id(self.final_reviewer_key_id)
        reviewed = _parse_utc(self.reviewed_at_utc, name="reviewed_at")
        expires = _parse_utc(self.expires_at_utc, name="expires_at")
        if expires <= reviewed:
            raise S0ProductionEvidenceBundleError(
                "verified S0 approval expiry must follow review time"
            )
        if not all(
            (
                self.two_cpu_host_reproducibility_verified,
                self.independent_external_implementation_comparison_verified,
                self.production_validation_evidence,
                self.reference_energy_force_protocol_validated,
                self.reference_minimization_protocol_validated,
                self.s0_accepted,
                self.s1_admission_authorized,
            )
        ):
            raise S0ProductionEvidenceBundleError(
                "accepted S0 verification lost a required narrow fact"
            )
        if any(
            (
                self.scientifically_validated,
                self.chemical_applicability_validated,
                self.validated_refinement_claim_authorized,
                self.parameter_fitting_authorized,
                self.benchmark_validated,
                self.product_qualified,
                self.customer_execution_enabled,
                self.claim_safe,
            )
        ):
            raise S0ProductionEvidenceBundleError(
                "S0 verification cannot promote chemistry, fitting, benchmark, or product claims"
            )
        if not self.blockers:
            raise S0ProductionEvidenceBundleError(
                "S0 verification must retain post-S0 blockers"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_sha256": self.contract_sha256,
            "approval_sha256": self.approval_sha256,
            "bundle_sha256": self.bundle_sha256,
            "host_review_attestation_sha256s": list(
                self.host_review_attestation_sha256s
            ),
            "enrolled_host_identity_sha256s": list(self.enrolled_host_identity_sha256s),
            "cpu_identity_sha256s": list(self.cpu_identity_sha256s),
            "code_commit_sha": self.code_commit_sha,
            "energy_force_source_manifest_sha256": (
                self.energy_force_source_manifest_sha256
            ),
            "minimization_source_manifest_sha256": (
                self.minimization_source_manifest_sha256
            ),
            "dependency_rows_sha256": self.dependency_rows_sha256,
            "openmm_runtime_identity_sha256": self.openmm_runtime_identity_sha256,
            "openmm_source_identity_sha256": self.openmm_source_identity_sha256,
            "energy_force_physics_projection_sha256": (
                self.energy_force_physics_projection_sha256
            ),
            "minimization_physics_projection_sha256": (
                self.minimization_physics_projection_sha256
            ),
            "final_reviewer_identity_sha256": self.final_reviewer_identity_sha256,
            "final_reviewer_key_id": self.final_reviewer_key_id,
            "reviewed_at_utc": self.reviewed_at_utc,
            "expires_at_utc": self.expires_at_utc,
            "two_cpu_host_reproducibility_verified": (
                self.two_cpu_host_reproducibility_verified
            ),
            "independent_external_implementation_comparison_verified": (
                self.independent_external_implementation_comparison_verified
            ),
            "production_validation_evidence": self.production_validation_evidence,
            "reference_energy_force_protocol_validated": (
                self.reference_energy_force_protocol_validated
            ),
            "reference_minimization_protocol_validated": (
                self.reference_minimization_protocol_validated
            ),
            "s0_accepted": self.s0_accepted,
            "s1_admission_authorized": self.s1_admission_authorized,
            "scientifically_validated": self.scientifically_validated,
            "chemical_applicability_validated": self.chemical_applicability_validated,
            "validated_refinement_claim_authorized": (
                self.validated_refinement_claim_authorized
            ),
            "parameter_fitting_authorized": self.parameter_fitting_authorized,
            "benchmark_validated": self.benchmark_validated,
            "product_qualified": self.product_qualified,
            "customer_execution_enabled": self.customer_execution_enabled,
            "claim_safe": self.claim_safe,
            "blockers": list(self.blockers),
        }


def _contract_projection() -> dict[str, Any]:
    return {
        "schema_id": S0_PRODUCTION_EVIDENCE_BUNDLE_CONTRACT_SCHEMA_ID,
        "contract_id": S0_PRODUCTION_EVIDENCE_BUNDLE_CONTRACT_ID,
        "contract_version": S0_PRODUCTION_EVIDENCE_BUNDLE_CONTRACT_VERSION,
        "frozen_at_utc": S0_PRODUCTION_EVIDENCE_BUNDLE_CONTRACT_FROZEN_AT_UTC,
        "superseded_contract_sha256": (
            FROZEN_LEGACY_S0_PRODUCTION_EVIDENCE_BUNDLE_CONTRACT_SHA256_V1
        ),
        "refreeze_reason": "binds_complete_energy_force_ed25519_signature_chain",
        "bound_contracts": {
            "openmm_reference_result_review_contract_sha256": (
                FROZEN_OPENMM_REFERENCE_RESULT_REVIEW_CONTRACT_SHA256
            ),
        },
        "host_policy": {
            "required_host_count": S0_PRODUCTION_EVIDENCE_BUNDLE_HOST_COUNT,
            "host_cpu_session_custody_receipt_review_and_nonce_distinct": True,
            "code_commit_source_dependency_runtime_and_seed_equal": True,
            "energy_force_physics_projection_exactly_equal": True,
            "minimization_physics_projection_exactly_equal": True,
            "host_rows_sorted_by_enrolled_host_identity": True,
            "all_failure_rows_remain_in_denominator": True,
            "energy_force_review_authorization_and_result_chain_uses_ed25519": True,
            "nested_verifier_trust_anchors_contain_public_keys_only": True,
            "private_or_symmetric_verification_keys_allowed": False,
        },
        "final_review_policy": {
            "algorithm": S0_PRODUCTION_EVIDENCE_BUNDLE_SIGNATURE_ALGORITHM,
            "maximum_validity_seconds": int(
                S0_PRODUCTION_EVIDENCE_BUNDLE_MAX_VALIDITY.total_seconds()
            ),
            "final_human_reviewer_distinct_from_all_nested_roles": True,
            "canonical_json_required": True,
            "trusted_keys_are_out_of_band": True,
            "revocation_and_supersession_inputs_required": True,
            "approval_cannot_outlive_nested_host_reviews": True,
            "secret_free_detached_signing_request_supported": True,
            "external_or_hardware_signer_may_sign_exact_canonical_payload": True,
            "private_key_forbidden_in_signing_request_and_cli": True,
            "signature_attachment_does_not_replace_full_evidence_reverification": True,
        },
        "required_final_check_ids": list(_REQUIRED_FINAL_CHECK_IDS),
        "required_final_limitation_ids": list(_REQUIRED_FINAL_LIMITATION_IDS),
        "accepted_bundle_policy": {
            "two_cpu_host_reproducibility_verified": True,
            "independent_external_implementation_comparison_verified": True,
            "production_validation_evidence": True,
            "reference_energy_force_protocol_validated": True,
            "reference_minimization_protocol_validated": True,
            "s0_accepted": True,
            "s1_admission_authorized": True,
            "scientifically_validated": False,
            "chemical_applicability_validated": False,
            "validated_refinement_claim_authorized": False,
            "parameter_fitting_authorized": False,
            "benchmark_validated": False,
            "product_qualified": False,
            "customer_execution_enabled": False,
            "claim_safe": False,
        },
    }


def s0_production_evidence_bundle_contract_document() -> dict[str, Any]:
    projection = _contract_projection()
    document = {**projection, "contract_sha256": _sha256(projection)}
    if (
        FROZEN_S0_PRODUCTION_EVIDENCE_BUNDLE_CONTRACT_SHA256
        and document["contract_sha256"]
        != FROZEN_S0_PRODUCTION_EVIDENCE_BUNDLE_CONTRACT_SHA256
    ):
        raise S0ProductionEvidenceBundleError(
            "frozen S0 evidence-bundle contract SHA-256 drifted"
        )
    return document


def require_s0_production_evidence_bundle_contract_document(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise S0ProductionEvidenceBundleError(
            "S0 evidence-bundle contract must be a mapping"
        )
    observed = dict(value)
    expected = s0_production_evidence_bundle_contract_document()
    if observed != expected:
        raise S0ProductionEvidenceBundleError(
            "S0 evidence-bundle contract does not match the frozen record"
        )
    return observed


def _verified_host_rows(
    host_evidence: Sequence[S0HostEvidence],
    *,
    checked_at: datetime,
    revoked_host_review_attestation_sha256s: Sequence[str],
    superseded_host_review_attestation_sha256s: Sequence[str],
) -> tuple[list[dict[str, Any]], tuple[OpenMMReferenceResultReviewVerification, ...]]:
    if (
        isinstance(host_evidence, (str, bytes))
        or not isinstance(host_evidence, Sequence)
        or len(host_evidence) != S0_PRODUCTION_EVIDENCE_BUNDLE_HOST_COUNT
        or any(not isinstance(item, S0HostEvidence) for item in host_evidence)
    ):
        raise S0ProductionEvidenceBundleError(
            "S0 bundle requires exactly two typed host evidence inputs"
        )
    verifications = tuple(
        _verify_host_evidence(item, checked_at=checked_at) for item in host_evidence
    )
    revoked = _external_sha256_set(
        revoked_host_review_attestation_sha256s,
        name="revoked host result-review attestation",
    )
    superseded = _external_sha256_set(
        superseded_host_review_attestation_sha256s,
        name="superseded host result-review attestation",
    )
    for verification in verifications:
        if verification.attestation_sha256 in revoked:
            raise S0ProductionEvidenceBundleError(
                "host result-review attestation is externally revoked"
            )
        if verification.attestation_sha256 in superseded:
            raise S0ProductionEvidenceBundleError(
                "host result-review attestation is externally superseded"
            )
    ordered = tuple(
        sorted(verifications, key=lambda row: row.enrolled_host_identity_sha256)
    )
    shared_fields = (
        "code_commit_sha",
        "energy_force_source_manifest_sha256",
        "minimization_source_manifest_sha256",
        "dependency_rows_sha256",
        "seed",
        "openmm_runtime_identity_sha256",
        "openmm_source_identity_sha256",
        "energy_force_physics_projection_sha256",
        "minimization_physics_projection_sha256",
    )
    for field_name in shared_fields:
        if getattr(ordered[0], field_name) != getattr(ordered[1], field_name):
            raise S0ProductionEvidenceBundleError(
                f"host-to-host {field_name} equality failed"
            )
    distinct_fields = (
        "attestation_sha256",
        "enrolled_host_identity_sha256",
        "cpu_identity_sha256",
        "production_evidence_session_sha256",
        "custody_terminal_sha256",
        "energy_force_result_receipt_sha256",
        "energy_force_result_review_attestation_sha256",
        "minimization_result_receipt_sha256",
        "minimization_result_review_attestation_sha256",
        "openmm_energy_force_receipt_sha256",
        "openmm_minimization_trace_receipt_sha256",
        "energy_force_execution_environment_receipt_sha256",
        "minimization_execution_environment_receipt_sha256",
        "energy_force_authorization_nonce_sha256",
        "minimization_authorization_nonce_sha256",
        "nonce_sha256",
    )
    for field_name in distinct_fields:
        if getattr(ordered[0], field_name) == getattr(ordered[1], field_name):
            raise S0ProductionEvidenceBundleError(
                f"host-to-host {field_name} identities must be distinct"
            )
    rows = []
    for ordinal, verification in enumerate(ordered, start=1):
        rows.append(
            {
                "ordinal": ordinal,
                "enrolled_host_identity_sha256": (
                    verification.enrolled_host_identity_sha256
                ),
                "cpu_identity_sha256": verification.cpu_identity_sha256,
                "production_evidence_session_sha256": (
                    verification.production_evidence_session_sha256
                ),
                "custody_terminal_sha256": verification.custody_terminal_sha256,
                "host_result_review_attestation_sha256": (
                    verification.attestation_sha256
                ),
                "energy_force_result_receipt_sha256": (
                    verification.energy_force_result_receipt_sha256
                ),
                "energy_force_result_review_attestation_sha256": (
                    verification.energy_force_result_review_attestation_sha256
                ),
                "minimization_result_receipt_sha256": (
                    verification.minimization_result_receipt_sha256
                ),
                "minimization_result_review_attestation_sha256": (
                    verification.minimization_result_review_attestation_sha256
                ),
                "openmm_energy_force_receipt_sha256": (
                    verification.openmm_energy_force_receipt_sha256
                ),
                "openmm_minimization_trace_receipt_sha256": (
                    verification.openmm_minimization_trace_receipt_sha256
                ),
                "energy_force_execution_environment_receipt_sha256": (
                    verification.energy_force_execution_environment_receipt_sha256
                ),
                "minimization_execution_environment_receipt_sha256": (
                    verification.minimization_execution_environment_receipt_sha256
                ),
                "energy_force_authorization_nonce_sha256": (
                    verification.energy_force_authorization_nonce_sha256
                ),
                "minimization_authorization_nonce_sha256": (
                    verification.minimization_authorization_nonce_sha256
                ),
                "host_result_review_nonce_sha256": verification.nonce_sha256,
                "external_result_reviewer_identity_sha256": (
                    verification.external_result_reviewer_identity_sha256
                ),
                "implementation_author_identity_sha256": (
                    verification.implementation_author_identity_sha256
                ),
                "independent_scientific_reviewer_identity_sha256": (
                    verification.independent_scientific_reviewer_identity_sha256
                ),
                "authorization_operator_identity_sha256": (
                    verification.authorization_operator_identity_sha256
                ),
                "energy_force_result_reviewer_identity_sha256": (
                    verification.energy_force_result_reviewer_identity_sha256
                ),
                "minimization_result_reviewer_identity_sha256": (
                    verification.minimization_result_reviewer_identity_sha256
                ),
                "reviewed_at_utc": verification.reviewed_at_utc,
                "expires_at_utc": verification.expires_at_utc,
                "external_oracle_comparison_verified": True,
            }
        )
    return rows, ordered


def _approval_projection(
    *,
    host_rows: Sequence[Mapping[str, Any]],
    host_verifications: Sequence[OpenMMReferenceResultReviewVerification],
    final_reviewer_identity_sha256: str,
    final_reviewer_key_id: str,
    reviewed_at_utc: str,
    expires_at_utc: str,
    nonce_sha256: str,
) -> dict[str, Any]:
    if len(host_rows) != 2 or len(host_verifications) != 2:
        raise S0ProductionEvidenceBundleError(
            "S0 approval requires exactly two verified host rows"
        )
    final_reviewer = _require_sha256(
        final_reviewer_identity_sha256, name="final S0 reviewer identity"
    )
    nested_roles = {
        identity
        for verification in host_verifications
        for identity in (
            verification.implementation_author_identity_sha256,
            verification.independent_scientific_reviewer_identity_sha256,
            verification.authorization_operator_identity_sha256,
            verification.energy_force_result_reviewer_identity_sha256,
            verification.minimization_result_reviewer_identity_sha256,
            verification.external_result_reviewer_identity_sha256,
        )
    }
    if final_reviewer in nested_roles:
        raise S0ProductionEvidenceBundleError(
            "final S0 reviewer must be distinct from every nested role"
        )
    reviewed = _parse_utc(reviewed_at_utc, name="reviewed_at")
    expires = _parse_utc(expires_at_utc, name="expires_at")
    latest_host_review = max(
        _parse_utc(row.reviewed_at_utc, name="host reviewed_at")
        for row in host_verifications
    )
    earliest_host_expiry = min(
        _parse_utc(row.expires_at_utc, name="host expires_at")
        for row in host_verifications
    )
    if reviewed < latest_host_review:
        raise S0ProductionEvidenceBundleError(
            "final S0 review predates a host result review"
        )
    if expires > earliest_host_expiry:
        raise S0ProductionEvidenceBundleError(
            "final S0 approval outlives a host result review"
        )
    host_nonces = {row.nonce_sha256 for row in host_verifications}
    final_nonce = _require_sha256(nonce_sha256, name="final S0 review nonce")
    if final_nonce in host_nonces:
        raise S0ProductionEvidenceBundleError(
            "final S0 review nonce reuses a host review nonce"
        )
    first = host_verifications[0]
    bundle_projection = {
        "host_rows": [dict(row) for row in host_rows],
        "shared_identity": {
            "code_commit_sha": first.code_commit_sha,
            "energy_force_source_manifest_sha256": (
                first.energy_force_source_manifest_sha256
            ),
            "minimization_source_manifest_sha256": (
                first.minimization_source_manifest_sha256
            ),
            "dependency_rows_sha256": first.dependency_rows_sha256,
            "seed": first.seed,
            "openmm_runtime_identity_sha256": (first.openmm_runtime_identity_sha256),
            "openmm_source_identity_sha256": first.openmm_source_identity_sha256,
            "energy_force_physics_projection_sha256": (
                first.energy_force_physics_projection_sha256
            ),
            "minimization_physics_projection_sha256": (
                first.minimization_physics_projection_sha256
            ),
        },
        "host_to_host_disposition": {
            "distinct_host_cpu_session_custody_and_artifact_identities": True,
            "source_binary_environment_dependency_identity_frozen": True,
            "energy_force_physics_projection_exactly_equal": True,
            "minimization_physics_projection_exactly_equal": True,
            "all_failure_rows_retained": True,
            "outcome": "accepted",
        },
    }
    return {
        "schema_id": S0_PRODUCTION_EVIDENCE_BUNDLE_APPROVAL_SCHEMA_ID,
        "contract_sha256": s0_production_evidence_bundle_contract_document()[
            "contract_sha256"
        ],
        "bundle": bundle_projection,
        "bundle_sha256": _sha256(bundle_projection),
        "final_review": {
            "final_reviewer_identity_sha256": final_reviewer,
            "final_reviewer_key_id": _require_key_id(final_reviewer_key_id),
            "reviewed_at_utc": reviewed_at_utc,
            "expires_at_utc": expires_at_utc,
            "nonce_sha256": final_nonce,
            "accepted_check_ids": list(_REQUIRED_FINAL_CHECK_IDS),
            "acknowledged_limitation_ids": list(_REQUIRED_FINAL_LIMITATION_IDS),
            "external_custody_and_production_session_evidence_reviewed": True,
            "review_outcome": S0_FINAL_REVIEW_OUTCOME_ACCEPTED,
        },
        "two_cpu_host_reproducibility_verified": True,
        "independent_external_implementation_comparison_verified": True,
        "production_validation_evidence": True,
        "reference_energy_force_protocol_validated": True,
        "reference_minimization_protocol_validated": True,
        "s0_accepted": True,
        "s1_admission_authorized": True,
        "scientifically_validated": False,
        "chemical_applicability_validated": False,
        "validated_refinement_claim_authorized": False,
        "parameter_fitting_authorized": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
        "superseded": False,
        "revoked": False,
    }


def build_signed_s0_production_evidence_bundle_approval(
    *,
    host_evidence: Sequence[S0HostEvidence],
    final_reviewer_identity_sha256: str,
    final_reviewer_key_id: str,
    signing_key: bytes | str,
    reviewed_at: datetime,
    expires_at: datetime,
    nonce_sha256: str,
    revoked_host_review_attestation_sha256s: Sequence[str],
    superseded_host_review_attestation_sha256s: Sequence[str],
) -> dict[str, Any]:
    """Convenience builder using the same detached-signing payload contract."""

    request = build_s0_production_evidence_bundle_approval_signing_request(
        host_evidence=host_evidence,
        final_reviewer_identity_sha256=final_reviewer_identity_sha256,
        final_reviewer_key_id=final_reviewer_key_id,
        reviewed_at=reviewed_at,
        expires_at=expires_at,
        nonce_sha256=nonce_sha256,
        revoked_host_review_attestation_sha256s=(
            revoked_host_review_attestation_sha256s
        ),
        superseded_host_review_attestation_sha256s=(
            superseded_host_review_attestation_sha256s
        ),
    )
    private_key = _require_key(signing_key, name="final S0 reviewer signing key")
    try:
        signature = sign_ed25519(
            s0_production_evidence_bundle_approval_signing_bytes(request),
            private_key,
        )
        public_key = ed25519_public_key_bytes(private_key)
    except ReferenceMinimizationValidationEd25519Error as exc:
        raise S0ProductionEvidenceBundleError("final S0 signing failed") from exc
    return attach_s0_production_evidence_bundle_approval_signature(
        request,
        signature_hex=signature,
        verification_key=public_key,
    )


def build_s0_production_evidence_bundle_approval_signing_request(
    *,
    host_evidence: Sequence[S0HostEvidence],
    final_reviewer_identity_sha256: str,
    final_reviewer_key_id: str,
    reviewed_at: datetime,
    expires_at: datetime,
    nonce_sha256: str,
    revoked_host_review_attestation_sha256s: Sequence[str],
    superseded_host_review_attestation_sha256s: Sequence[str],
) -> dict[str, Any]:
    """Freshly verify two hosts and return a secret-free detached signing request."""

    reviewed_at_utc = _format_utc(reviewed_at, name="reviewed_at")
    expires_at_utc = _format_utc(expires_at, name="expires_at")
    reviewed = _parse_utc(reviewed_at_utc, name="reviewed_at")
    expires = _parse_utc(expires_at_utc, name="expires_at")
    if expires <= reviewed:
        raise S0ProductionEvidenceBundleError(
            "S0 approval expiry must follow review time"
        )
    if expires - reviewed > S0_PRODUCTION_EVIDENCE_BUNDLE_MAX_VALIDITY:
        raise S0ProductionEvidenceBundleError(
            "S0 approval validity exceeds the frozen maximum"
        )
    rows, verifications = _verified_host_rows(
        host_evidence,
        checked_at=reviewed,
        revoked_host_review_attestation_sha256s=(
            revoked_host_review_attestation_sha256s
        ),
        superseded_host_review_attestation_sha256s=(
            superseded_host_review_attestation_sha256s
        ),
    )
    projection = _approval_projection(
        host_rows=rows,
        host_verifications=verifications,
        final_reviewer_identity_sha256=final_reviewer_identity_sha256,
        final_reviewer_key_id=final_reviewer_key_id,
        reviewed_at_utc=reviewed_at_utc,
        expires_at_utc=expires_at_utc,
        nonce_sha256=nonce_sha256,
    )
    payload = {**projection, "approval_sha256": _sha256(projection)}
    request_projection = {
        "schema_id": S0_PRODUCTION_EVIDENCE_BUNDLE_SIGNING_REQUEST_SCHEMA_ID,
        "contract_sha256": s0_production_evidence_bundle_contract_document()[
            "contract_sha256"
        ],
        "signature_algorithm": S0_PRODUCTION_EVIDENCE_BUNDLE_SIGNATURE_ALGORITHM,
        "final_reviewer_identity_sha256": _require_sha256(
            final_reviewer_identity_sha256, name="final S0 reviewer identity"
        ),
        "final_reviewer_key_id": _require_key_id(final_reviewer_key_id),
        "approval_payload": payload,
        "signing_bytes_sha256": hashlib.sha256(_canonical_bytes(payload)).hexdigest(),
    }
    request = {
        **request_projection,
        "request_sha256": _sha256(request_projection),
    }
    return require_s0_production_evidence_bundle_approval_signing_request(request)


def _load_signing_request(
    source: str | bytes | Mapping[str, Any],
) -> dict[str, Any]:
    if isinstance(source, Mapping):
        return dict(source)
    raw = source.encode("utf-8") if isinstance(source, str) else source
    if (
        not isinstance(raw, bytes)
        or not raw
        or len(raw) > S0_PRODUCTION_EVIDENCE_BUNDLE_MAX_TRANSPORT_BYTES
    ):
        raise S0ProductionEvidenceBundleError(
            "S0 signing-request transport is invalid or oversized"
        )

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise S0ProductionEvidenceBundleError(
                    "S0 signing-request transport contains a duplicate key"
                )
            result[key] = value
        return result

    try:
        loaded = json.loads(
            raw.decode("utf-8"), object_pairs_hook=reject_duplicate_keys
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise S0ProductionEvidenceBundleError(
            "S0 signing-request transport must be UTF-8 JSON"
        ) from exc
    if not isinstance(loaded, dict) or _canonical_bytes(loaded) != raw:
        raise S0ProductionEvidenceBundleError(
            "S0 signing-request transport is not canonical JSON"
        )
    return loaded


def _reject_private_signing_material(value: object) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise S0ProductionEvidenceBundleError(
                    "S0 signing request contains a non-string field"
                )
            lowered = key.lower()
            if (
                "private_key" in lowered
                or "signing_key" in lowered
                or lowered in {"secret", "secret_hex"}
            ):
                raise S0ProductionEvidenceBundleError(
                    "S0 signing request must not contain private signing material"
                )
            _reject_private_signing_material(child)
    elif isinstance(value, list):
        for child in value:
            _reject_private_signing_material(child)


def _require_unsigned_approval_payload(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise S0ProductionEvidenceBundleError(
            "S0 signing request approval payload is invalid"
        )
    payload = dict(value)
    _reject_private_signing_material(payload)
    if "signature" in payload:
        raise S0ProductionEvidenceBundleError(
            "S0 signing request must contain an unsigned approval payload"
        )
    approval_sha256 = payload.pop("approval_sha256", None)
    if _require_sha256(approval_sha256, name="unsigned S0 approval") != _sha256(
        payload
    ):
        raise S0ProductionEvidenceBundleError("unsigned S0 approval digest mismatch")
    if (
        payload.get("schema_id") != S0_PRODUCTION_EVIDENCE_BUNDLE_APPROVAL_SCHEMA_ID
        or payload.get("contract_sha256")
        != s0_production_evidence_bundle_contract_document()["contract_sha256"]
    ):
        raise S0ProductionEvidenceBundleError(
            "unsigned S0 approval contract identity is invalid"
        )
    bundle = payload.get("bundle")
    if (
        not isinstance(bundle, Mapping)
        or set(bundle) != {"host_rows", "shared_identity", "host_to_host_disposition"}
        or not isinstance(bundle.get("host_rows"), list)
        or len(bundle["host_rows"]) != S0_PRODUCTION_EVIDENCE_BUNDLE_HOST_COUNT
        or payload.get("bundle_sha256") != _sha256(bundle)
    ):
        raise S0ProductionEvidenceBundleError(
            "unsigned S0 approval bundle projection is invalid"
        )
    host_row_fields = {
        "ordinal",
        "enrolled_host_identity_sha256",
        "cpu_identity_sha256",
        "production_evidence_session_sha256",
        "custody_terminal_sha256",
        "host_result_review_attestation_sha256",
        "energy_force_result_receipt_sha256",
        "energy_force_result_review_attestation_sha256",
        "minimization_result_receipt_sha256",
        "minimization_result_review_attestation_sha256",
        "openmm_energy_force_receipt_sha256",
        "openmm_minimization_trace_receipt_sha256",
        "energy_force_execution_environment_receipt_sha256",
        "minimization_execution_environment_receipt_sha256",
        "energy_force_authorization_nonce_sha256",
        "minimization_authorization_nonce_sha256",
        "host_result_review_nonce_sha256",
        "external_result_reviewer_identity_sha256",
        "implementation_author_identity_sha256",
        "independent_scientific_reviewer_identity_sha256",
        "authorization_operator_identity_sha256",
        "energy_force_result_reviewer_identity_sha256",
        "minimization_result_reviewer_identity_sha256",
        "reviewed_at_utc",
        "expires_at_utc",
        "external_oracle_comparison_verified",
    }
    host_rows = bundle["host_rows"]
    for ordinal, row in enumerate(host_rows, start=1):
        if (
            not isinstance(row, Mapping)
            or set(row) != host_row_fields
            or row.get("ordinal") != ordinal
            or row.get("external_oracle_comparison_verified") is not True
        ):
            raise S0ProductionEvidenceBundleError(
                "unsigned S0 approval host row is invalid"
            )
        for field_name in host_row_fields - {
            "ordinal",
            "reviewed_at_utc",
            "expires_at_utc",
            "external_oracle_comparison_verified",
        }:
            _require_sha256(row.get(field_name), name=f"unsigned host {field_name}")
        row_reviewed = _parse_utc(row.get("reviewed_at_utc"), name="host reviewed_at")
        row_expires = _parse_utc(row.get("expires_at_utc"), name="host expires_at")
        if row_expires <= row_reviewed:
            raise S0ProductionEvidenceBundleError(
                "unsigned S0 approval host review validity is invalid"
            )
    if [row["enrolled_host_identity_sha256"] for row in host_rows] != sorted(
        row["enrolled_host_identity_sha256"] for row in host_rows
    ):
        raise S0ProductionEvidenceBundleError(
            "unsigned S0 approval host rows are not canonical"
        )
    for field_name in (
        "enrolled_host_identity_sha256",
        "cpu_identity_sha256",
        "production_evidence_session_sha256",
        "custody_terminal_sha256",
        "host_result_review_attestation_sha256",
        "energy_force_result_receipt_sha256",
        "energy_force_result_review_attestation_sha256",
        "minimization_result_receipt_sha256",
        "minimization_result_review_attestation_sha256",
        "openmm_energy_force_receipt_sha256",
        "openmm_minimization_trace_receipt_sha256",
        "energy_force_execution_environment_receipt_sha256",
        "minimization_execution_environment_receipt_sha256",
        "energy_force_authorization_nonce_sha256",
        "minimization_authorization_nonce_sha256",
        "host_result_review_nonce_sha256",
    ):
        if host_rows[0][field_name] == host_rows[1][field_name]:
            raise S0ProductionEvidenceBundleError(
                f"unsigned S0 approval host {field_name} must be distinct"
            )
    shared = bundle["shared_identity"]
    shared_fields = {
        "code_commit_sha",
        "energy_force_source_manifest_sha256",
        "minimization_source_manifest_sha256",
        "dependency_rows_sha256",
        "seed",
        "openmm_runtime_identity_sha256",
        "openmm_source_identity_sha256",
        "energy_force_physics_projection_sha256",
        "minimization_physics_projection_sha256",
    }
    if not isinstance(shared, Mapping) or set(shared) != shared_fields:
        raise S0ProductionEvidenceBundleError(
            "unsigned S0 approval shared identity is invalid"
        )
    _require_commit_sha(shared.get("code_commit_sha"), name="unsigned code commit")
    if type(shared.get("seed")) is not int or shared["seed"] < 0:
        raise S0ProductionEvidenceBundleError("unsigned S0 approval seed is invalid")
    for field_name in shared_fields - {"code_commit_sha", "seed"}:
        _require_sha256(shared.get(field_name), name=f"unsigned shared {field_name}")
    if bundle["host_to_host_disposition"] != {
        "distinct_host_cpu_session_custody_and_artifact_identities": True,
        "source_binary_environment_dependency_identity_frozen": True,
        "energy_force_physics_projection_exactly_equal": True,
        "minimization_physics_projection_exactly_equal": True,
        "all_failure_rows_retained": True,
        "outcome": "accepted",
    }:
        raise S0ProductionEvidenceBundleError(
            "unsigned S0 approval host disposition is invalid"
        )
    final_review = payload.get("final_review")
    if (
        not isinstance(final_review, Mapping)
        or set(final_review)
        != {
            "final_reviewer_identity_sha256",
            "final_reviewer_key_id",
            "reviewed_at_utc",
            "expires_at_utc",
            "nonce_sha256",
            "accepted_check_ids",
            "acknowledged_limitation_ids",
            "external_custody_and_production_session_evidence_reviewed",
            "review_outcome",
        }
        or final_review.get("accepted_check_ids") != list(_REQUIRED_FINAL_CHECK_IDS)
        or final_review.get("acknowledged_limitation_ids")
        != list(_REQUIRED_FINAL_LIMITATION_IDS)
        or final_review.get("external_custody_and_production_session_evidence_reviewed")
        is not True
        or final_review.get("review_outcome") != S0_FINAL_REVIEW_OUTCOME_ACCEPTED
    ):
        raise S0ProductionEvidenceBundleError(
            "unsigned S0 approval final-review projection is invalid"
        )
    _require_sha256(
        final_review.get("final_reviewer_identity_sha256"),
        name="unsigned final S0 reviewer identity",
    )
    _require_key_id(final_review.get("final_reviewer_key_id"))
    reviewed = _parse_utc(final_review.get("reviewed_at_utc"), name="reviewed_at")
    expires = _parse_utc(final_review.get("expires_at_utc"), name="expires_at")
    if (
        expires <= reviewed
        or expires - reviewed > S0_PRODUCTION_EVIDENCE_BUNDLE_MAX_VALIDITY
    ):
        raise S0ProductionEvidenceBundleError(
            "unsigned S0 approval validity is invalid"
        )
    final_nonce = _require_sha256(
        final_review.get("nonce_sha256"), name="final S0 review nonce"
    )
    host_reviewed = [
        _parse_utc(row["reviewed_at_utc"], name="host reviewed_at") for row in host_rows
    ]
    host_expires = [
        _parse_utc(row["expires_at_utc"], name="host expires_at") for row in host_rows
    ]
    if reviewed < max(host_reviewed) or expires > min(host_expires):
        raise S0ProductionEvidenceBundleError(
            "unsigned S0 approval is outside the nested host-review window"
        )
    if final_nonce in {row["host_result_review_nonce_sha256"] for row in host_rows}:
        raise S0ProductionEvidenceBundleError(
            "unsigned final S0 review nonce reuses a host nonce"
        )
    nested_role_fields = (
        "external_result_reviewer_identity_sha256",
        "implementation_author_identity_sha256",
        "independent_scientific_reviewer_identity_sha256",
        "authorization_operator_identity_sha256",
        "energy_force_result_reviewer_identity_sha256",
        "minimization_result_reviewer_identity_sha256",
    )
    final_reviewer = final_review["final_reviewer_identity_sha256"]
    if final_reviewer in {
        row[field_name] for row in host_rows for field_name in nested_role_fields
    }:
        raise S0ProductionEvidenceBundleError(
            "unsigned final S0 reviewer reuses a nested role"
        )
    expected_facts = {
        "two_cpu_host_reproducibility_verified": True,
        "independent_external_implementation_comparison_verified": True,
        "production_validation_evidence": True,
        "reference_energy_force_protocol_validated": True,
        "reference_minimization_protocol_validated": True,
        "s0_accepted": True,
        "s1_admission_authorized": True,
        "scientifically_validated": False,
        "chemical_applicability_validated": False,
        "validated_refinement_claim_authorized": False,
        "parameter_fitting_authorized": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
        "superseded": False,
        "revoked": False,
    }
    if any(
        payload.get(name) is not expected for name, expected in expected_facts.items()
    ):
        raise S0ProductionEvidenceBundleError(
            "unsigned S0 approval claim projection is invalid"
        )
    expected_keys = {
        "schema_id",
        "contract_sha256",
        "bundle",
        "bundle_sha256",
        "final_review",
        *expected_facts,
    }
    if set(payload) != expected_keys:
        raise S0ProductionEvidenceBundleError(
            "unsigned S0 approval fields are not the frozen schema"
        )
    result = {**payload, "approval_sha256": approval_sha256}
    return result


def require_s0_production_evidence_bundle_approval_signing_request(
    source: str | bytes | Mapping[str, Any],
) -> dict[str, Any]:
    """Validate one canonical, secret-free detached signing request."""

    loaded = _load_signing_request(source)
    if set(loaded) != {
        "schema_id",
        "contract_sha256",
        "signature_algorithm",
        "final_reviewer_identity_sha256",
        "final_reviewer_key_id",
        "approval_payload",
        "signing_bytes_sha256",
        "request_sha256",
    }:
        raise S0ProductionEvidenceBundleError(
            "S0 signing request fields are not the frozen schema"
        )
    request_sha256 = loaded.pop("request_sha256")
    if _require_sha256(request_sha256, name="S0 signing request") != _sha256(loaded):
        raise S0ProductionEvidenceBundleError("S0 signing request digest mismatch")
    if (
        loaded.get("schema_id")
        != S0_PRODUCTION_EVIDENCE_BUNDLE_SIGNING_REQUEST_SCHEMA_ID
        or loaded.get("contract_sha256")
        != s0_production_evidence_bundle_contract_document()["contract_sha256"]
        or loaded.get("signature_algorithm")
        != S0_PRODUCTION_EVIDENCE_BUNDLE_SIGNATURE_ALGORITHM
    ):
        raise S0ProductionEvidenceBundleError(
            "S0 signing request contract identity is invalid"
        )
    payload = _require_unsigned_approval_payload(loaded.get("approval_payload"))
    final_review = payload["final_review"]
    reviewer = _require_sha256(
        loaded.get("final_reviewer_identity_sha256"),
        name="signing-request final reviewer identity",
    )
    key_id = _require_key_id(loaded.get("final_reviewer_key_id"))
    if (
        reviewer != final_review["final_reviewer_identity_sha256"]
        or key_id != final_review["final_reviewer_key_id"]
    ):
        raise S0ProductionEvidenceBundleError(
            "S0 signing request reviewer identity is cross-wired"
        )
    signing_digest = hashlib.sha256(_canonical_bytes(payload)).hexdigest()
    if (
        _require_sha256(loaded.get("signing_bytes_sha256"), name="S0 signing bytes")
        != signing_digest
    ):
        raise S0ProductionEvidenceBundleError(
            "S0 signing request bytes digest mismatch"
        )
    result = {
        **loaded,
        "approval_payload": payload,
        "request_sha256": request_sha256,
    }
    _reject_private_signing_material(result)
    return result


def s0_production_evidence_bundle_approval_signing_bytes(
    source: str | bytes | Mapping[str, Any],
) -> bytes:
    """Return the exact canonical bytes an external Ed25519 signer must sign."""

    request = require_s0_production_evidence_bundle_approval_signing_request(source)
    return _canonical_bytes(request["approval_payload"])


def attach_s0_production_evidence_bundle_approval_signature(
    source: str | bytes | Mapping[str, Any],
    *,
    signature_hex: str,
    verification_key: bytes | str,
) -> dict[str, Any]:
    """Verify and attach an externally produced signature without private keys."""

    request = require_s0_production_evidence_bundle_approval_signing_request(source)
    public_key = _require_key(
        verification_key, name="detached final S0 reviewer verification key"
    )
    try:
        verified = verify_ed25519(
            _canonical_bytes(request["approval_payload"]),
            signature_hex,
            public_key,
        )
    except ReferenceMinimizationValidationEd25519Error as exc:
        raise S0ProductionEvidenceBundleError(
            "detached final S0 signature verifier is unavailable"
        ) from exc
    if not verified:
        raise S0ProductionEvidenceBundleError(
            "detached final S0 signature verification failed"
        )
    payload = dict(request["approval_payload"])
    payload["signature"] = {
        "algorithm": S0_PRODUCTION_EVIDENCE_BUNDLE_SIGNATURE_ALGORITHM,
        "key_id": request["final_reviewer_key_id"],
        "value": signature_hex,
    }
    return payload


def verify_signed_s0_production_evidence_bundle_approval(
    source: str | bytes | Mapping[str, Any],
    *,
    host_evidence: Sequence[S0HostEvidence],
    trusted_final_reviewer_keys: Mapping[str, S0FinalReviewerTrustAnchor],
    checked_at: datetime,
    revoked_final_reviewer_key_ids: Sequence[str],
    revoked_host_review_attestation_sha256s: Sequence[str],
    superseded_host_review_attestation_sha256s: Sequence[str],
    revoked_approval_sha256s: Sequence[str],
    superseded_approval_sha256s: Sequence[str],
) -> S0ProductionEvidenceBundleVerification:
    """Freshly verify both hosts, final signature, freshness, and current state."""

    checked = _parse_utc(_format_utc(checked_at, name="checked_at"), name="checked_at")
    loaded = _load_approval(source)
    signature = loaded.pop("signature", None)
    approval_sha256 = loaded.pop("approval_sha256", None)
    if (
        not isinstance(signature, Mapping)
        or set(signature) != {"algorithm", "key_id", "value"}
        or signature.get("algorithm")
        != S0_PRODUCTION_EVIDENCE_BUNDLE_SIGNATURE_ALGORITHM
    ):
        raise S0ProductionEvidenceBundleError("final S0 signature envelope is invalid")
    approval_digest = _require_sha256(approval_sha256, name="final S0 approval")
    if approval_digest != _sha256(loaded):
        raise S0ProductionEvidenceBundleError("final S0 approval digest mismatch")
    if approval_digest in _external_sha256_set(
        revoked_approval_sha256s, name="revoked final S0 approval"
    ):
        raise S0ProductionEvidenceBundleError("final S0 approval is revoked")
    if approval_digest in _external_sha256_set(
        superseded_approval_sha256s, name="superseded final S0 approval"
    ):
        raise S0ProductionEvidenceBundleError("final S0 approval is superseded")
    key_id = _require_key_id(signature.get("key_id"))
    if key_id in _external_key_id_set(
        revoked_final_reviewer_key_ids, name="revoked final reviewer key"
    ):
        raise S0ProductionEvidenceBundleError("final S0 reviewer key is revoked")
    anchor = trusted_final_reviewer_keys.get(key_id)
    if anchor is None or not isinstance(anchor, S0FinalReviewerTrustAnchor):
        raise S0ProductionEvidenceBundleError("final S0 reviewer key is not trusted")
    final_review = loaded.get("final_review")
    if (
        not isinstance(final_review, Mapping)
        or final_review.get("final_reviewer_identity_sha256")
        != anchor.reviewer_identity_sha256
        or final_review.get("final_reviewer_key_id") != key_id
    ):
        raise S0ProductionEvidenceBundleError(
            "final S0 reviewer identity is cross-wired"
        )
    signed_payload = {**loaded, "approval_sha256": approval_digest}
    try:
        verified = verify_ed25519(
            _canonical_bytes(signed_payload),
            signature.get("value"),
            anchor.verification_key,
        )
    except ReferenceMinimizationValidationEd25519Error as exc:
        raise S0ProductionEvidenceBundleError(
            "final S0 signature verifier is unavailable"
        ) from exc
    if not verified:
        raise S0ProductionEvidenceBundleError("final S0 signature verification failed")
    reviewed = _parse_utc(final_review.get("reviewed_at_utc"), name="reviewed_at")
    expires = _parse_utc(final_review.get("expires_at_utc"), name="expires_at")
    if (
        expires <= reviewed
        or expires - reviewed > S0_PRODUCTION_EVIDENCE_BUNDLE_MAX_VALIDITY
        or checked < reviewed
        or checked > expires
    ):
        raise S0ProductionEvidenceBundleError(
            "final S0 approval is not currently valid"
        )
    rows, verifications = _verified_host_rows(
        host_evidence,
        checked_at=checked,
        revoked_host_review_attestation_sha256s=(
            revoked_host_review_attestation_sha256s
        ),
        superseded_host_review_attestation_sha256s=(
            superseded_host_review_attestation_sha256s
        ),
    )
    expected = _approval_projection(
        host_rows=rows,
        host_verifications=verifications,
        final_reviewer_identity_sha256=anchor.reviewer_identity_sha256,
        final_reviewer_key_id=key_id,
        reviewed_at_utc=final_review["reviewed_at_utc"],
        expires_at_utc=final_review["expires_at_utc"],
        nonce_sha256=final_review.get("nonce_sha256"),
    )
    if loaded != expected:
        raise S0ProductionEvidenceBundleError(
            "final S0 approval fields do not match the derived bundle"
        )
    shared = expected["bundle"]["shared_identity"]
    host_rows = expected["bundle"]["host_rows"]
    return S0ProductionEvidenceBundleVerification(
        contract_sha256=expected["contract_sha256"],
        approval_sha256=approval_digest,
        bundle_sha256=expected["bundle_sha256"],
        host_review_attestation_sha256s=tuple(
            row["host_result_review_attestation_sha256"] for row in host_rows
        ),
        enrolled_host_identity_sha256s=tuple(
            row["enrolled_host_identity_sha256"] for row in host_rows
        ),
        cpu_identity_sha256s=tuple(row["cpu_identity_sha256"] for row in host_rows),
        code_commit_sha=shared["code_commit_sha"],
        energy_force_source_manifest_sha256=shared[
            "energy_force_source_manifest_sha256"
        ],
        minimization_source_manifest_sha256=shared[
            "minimization_source_manifest_sha256"
        ],
        dependency_rows_sha256=shared["dependency_rows_sha256"],
        openmm_runtime_identity_sha256=shared["openmm_runtime_identity_sha256"],
        openmm_source_identity_sha256=shared["openmm_source_identity_sha256"],
        energy_force_physics_projection_sha256=shared[
            "energy_force_physics_projection_sha256"
        ],
        minimization_physics_projection_sha256=shared[
            "minimization_physics_projection_sha256"
        ],
        final_reviewer_identity_sha256=anchor.reviewer_identity_sha256,
        final_reviewer_key_id=key_id,
        reviewed_at_utc=final_review["reviewed_at_utc"],
        expires_at_utc=final_review["expires_at_utc"],
        two_cpu_host_reproducibility_verified=True,
        independent_external_implementation_comparison_verified=True,
        production_validation_evidence=True,
        reference_energy_force_protocol_validated=True,
        reference_minimization_protocol_validated=True,
        s0_accepted=True,
        s1_admission_authorized=True,
        scientifically_validated=False,
        chemical_applicability_validated=False,
        validated_refinement_claim_authorized=False,
        parameter_fitting_authorized=False,
        benchmark_validated=False,
        product_qualified=False,
        customer_execution_enabled=False,
        claim_safe=False,
        blockers=_POST_ACCEPTANCE_BLOCKERS,
    )


def s0_production_evidence_bundle_contract_decision() -> dict[str, Any]:
    contract = s0_production_evidence_bundle_contract_document()
    return {
        "contract_sha256": contract["contract_sha256"],
        "bundle_contract_implemented": True,
        "two_host_evidence_present": False,
        "final_human_approval_present": False,
        "two_cpu_host_reproducibility_verified": False,
        "independent_external_implementation_comparison_verified": False,
        "production_validation_evidence": False,
        "reference_energy_force_protocol_validated": False,
        "reference_minimization_protocol_validated": False,
        "s0_accepted": False,
        "s1_admission_authorized": False,
        "scientifically_validated": False,
        "chemical_applicability_validated": False,
        "validated_refinement_claim_authorized": False,
        "parameter_fitting_authorized": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
        "blockers": list(_CLOSED_GATE_BLOCKERS),
    }


def _read_cli_input(path: Path) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_size <= 0
            or before.st_size > S0_PRODUCTION_EVIDENCE_BUNDLE_MAX_TRANSPORT_BYTES
        ):
            raise S0ProductionEvidenceBundleError(
                "S0 CLI input is not a bounded regular file"
            )
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(descriptor, min(remaining, 1024 * 1024))
            if not chunk:
                raise S0ProductionEvidenceBundleError(
                    "S0 CLI input ended before its measured size"
                )
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            raise S0ProductionEvidenceBundleError("S0 CLI input grew while it was read")
        after = os.fstat(descriptor)
        if (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ):
            raise S0ProductionEvidenceBundleError(
                "S0 CLI input changed while it was read"
            )
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _write_cli_output(path: str, payload: bytes) -> None:
    if path == "-":
        sys.stdout.buffer.write(payload)
        sys.stdout.buffer.flush()
        return
    destination = Path(path)
    parent = destination.parent if destination.parent != Path("") else Path(".")
    parent_flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    parent_descriptor = os.open(parent, parent_flags)
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    descriptor: int | None = None
    created = False
    completed = False
    try:
        descriptor = os.open(
            destination.name,
            flags,
            0o600,
            dir_fd=parent_descriptor,
        )
        created = True
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("S0 CLI output write made no progress")
            view = view[written:]
        os.fsync(descriptor)
        completed = True
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if created and not completed:
            try:
                os.unlink(destination.name, dir_fd=parent_descriptor)
            except FileNotFoundError:
                pass
        else:
            os.fsync(parent_descriptor)
        os.close(parent_descriptor)


def _cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2-s0-review",
        description=(
            "Inspect the S0 contract or process secret-free detached final-review "
            "signing material. This CLI never accepts a private key."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    contract = subparsers.add_parser("contract", help="emit the frozen S0 contract")
    contract.add_argument("--output", default="-")
    signing_bytes = subparsers.add_parser(
        "signing-bytes",
        help="validate a signing request and emit the exact bytes to sign",
    )
    signing_bytes.add_argument("--request", required=True)
    signing_bytes.add_argument("--output", default="-")
    attach = subparsers.add_parser(
        "attach-signature",
        help="verify and attach an externally generated Ed25519 signature",
    )
    attach.add_argument("--request", required=True)
    attach.add_argument("--signature-hex", required=True)
    attach.add_argument("--verification-key-hex", required=True)
    attach.add_argument("--output", default="-")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the secret-free detached final-review helper."""

    args = _cli_parser().parse_args(argv)
    try:
        if args.command == "contract":
            output = _canonical_bytes(s0_production_evidence_bundle_contract_document())
        elif args.command == "signing-bytes":
            request = _read_cli_input(Path(args.request))
            output = s0_production_evidence_bundle_approval_signing_bytes(request)
        else:
            request = _read_cli_input(Path(args.request))
            approval = attach_s0_production_evidence_bundle_approval_signature(
                request,
                signature_hex=args.signature_hex,
                verification_key=args.verification_key_hex,
            )
            output = _canonical_bytes(approval)
        _write_cli_output(args.output, output)
    except (OSError, S0ProductionEvidenceBundleError) as exc:
        print(f"S0 review operation failed: {exc}", file=sys.stderr)
        return 2
    return 0


__all__ = [
    "FROZEN_LEGACY_S0_PRODUCTION_EVIDENCE_BUNDLE_CONTRACT_SHA256_V1",
    "FROZEN_S0_PRODUCTION_EVIDENCE_BUNDLE_CONTRACT_SHA256",
    "S0_FINAL_REVIEW_OUTCOME_ACCEPTED",
    "S0_FINAL_REVIEW_OUTCOME_REJECTED",
    "S0_PRODUCTION_EVIDENCE_BUNDLE_APPROVAL_SCHEMA_ID",
    "S0_PRODUCTION_EVIDENCE_BUNDLE_CONTRACT_ID",
    "S0_PRODUCTION_EVIDENCE_BUNDLE_CONTRACT_SCHEMA_ID",
    "S0_PRODUCTION_EVIDENCE_BUNDLE_SIGNING_REQUEST_SCHEMA_ID",
    "S0_PRODUCTION_EVIDENCE_BUNDLE_CONTRACT_VERSION",
    "S0_PRODUCTION_EVIDENCE_BUNDLE_HOST_COUNT",
    "S0_PRODUCTION_EVIDENCE_BUNDLE_MAX_VALIDITY",
    "S0_PRODUCTION_EVIDENCE_BUNDLE_SIGNATURE_ALGORITHM",
    "S0FinalReviewerTrustAnchor",
    "S0HostEvidence",
    "S0ProductionEvidenceBundleError",
    "S0ProductionEvidenceBundleVerification",
    "attach_s0_production_evidence_bundle_approval_signature",
    "build_s0_production_evidence_bundle_approval_signing_request",
    "build_signed_s0_production_evidence_bundle_approval",
    "main",
    "require_s0_production_evidence_bundle_contract_document",
    "require_s0_production_evidence_bundle_approval_signing_request",
    "s0_production_evidence_bundle_approval_signing_bytes",
    "s0_production_evidence_bundle_contract_decision",
    "s0_production_evidence_bundle_contract_document",
    "verify_signed_s0_production_evidence_bundle_approval",
]


if __name__ == "__main__":
    raise SystemExit(main())
