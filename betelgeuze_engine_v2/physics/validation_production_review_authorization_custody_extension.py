"""Claim-closed production review/authorization custody companion.

The frozen production evidence custody v1 contract verifies only sequence 1
(``production_permit``) and sequence 2 (``status_snapshot``).  This module is
an additive companion.  It does not modify that contract and it does not open
an execution gate.

The implemented carrier primitives are production-only Ed25519 wrappers for
the lane-specific pre-execution review and authorization.  Each wrapper
reverifies the exact raw ancestor artifacts.  Energy/force still has HMAC
upstream review and authorization artifacts; the wrappers therefore must not
be described as a fully asymmetric chain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any, Mapping, Sequence

from betelgeuze_engine_v2.physics.reference_minimization_validation_ed25519 import (
    ReferenceMinimizationValidationEd25519Error,
    ed25519_public_key_bytes,
    sign_ed25519,
    verify_ed25519,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_authorization import (
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_CONTRACT_SHA256,
    REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_RECEIPT_SCHEMA_ID,
    MinimizationAuthorizationOperatorTrustAnchor,
    ReferenceMinimizationValidationAuthorizationError,
    ReferenceMinimizationValidationAuthorizationVerification,
    verify_signed_reference_minimization_validation_authorization_receipt,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_review import (
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_REVIEW_CONTRACT_SHA256,
    REFERENCE_MINIMIZATION_VALIDATION_REVIEW_ATTESTATION_SCHEMA_ID,
    MinimizationScientificReviewerTrustAnchor,
    ReferenceMinimizationValidationReviewError,
    ReferenceMinimizationValidationReviewVerification,
    verify_signed_reference_minimization_validation_review_attestation,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_receipts import (
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256,
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256,
)
from betelgeuze_engine_v2.physics.reference_validation_review import (
    FROZEN_REFERENCE_VALIDATION_REVIEW_CONTRACT_SHA256,
    REFERENCE_VALIDATION_REVIEW_ATTESTATION_SCHEMA_ID,
    ReferenceValidationReviewError,
    ReferenceValidationReviewVerification,
    ScientificReviewerTrustAnchor,
    verify_signed_reference_validation_review_attestation,
)
from betelgeuze_engine_v2.physics.reference_validation_authorization import (
    FROZEN_REFERENCE_VALIDATION_AUTHORIZATION_CONTRACT_SHA256,
    REFERENCE_VALIDATION_AUTHORIZATION_RECEIPT_SCHEMA_ID,
    AuthorizationOperatorTrustAnchor,
    ReferenceValidationAuthorizationError,
    ReferenceValidationAuthorizationVerification,
    verify_signed_reference_validation_authorization_receipt,
)
from betelgeuze_engine_v2.physics.validation_process_launch_identity import (
    FROZEN_PROCESS_LAUNCH_IDENTITY_CONTRACT_SHA256,
)
from betelgeuze_engine_v2.physics.validation_production_evidence_custody import (
    CustodyRoleTrustAnchor,
    EvidenceAuthorityTrustAnchor,
    FROZEN_VALIDATION_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_SHA256,
    PRODUCTION_CUSTODY_EVENT_SCHEMA_ID,
    PRODUCTION_EVIDENCE_CLASS,
    PRODUCTION_EVIDENCE_PERMIT_SCHEMA_ID,
    PRODUCTION_EVIDENCE_STATUS_SNAPSHOT_SCHEMA_ID,
    ProductionCustodyEventVerification,
    ProductionEvidencePermitVerification,
    ProductionEvidenceStatusSnapshotVerification,
    ValidationProductionEvidenceCustodyError,
    verify_signed_production_custody_event,
    verify_signed_production_evidence_permit,
    verify_signed_production_evidence_status_snapshot,
)


VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SCHEMA_ID = (
    "betelgeuze.engine_v2_validation_production_review_authorization_custody_"
    "extension_contract/3.0.0"
)
VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_ID = (
    "engine_v2_synthetic_validation_production_review_authorization_custody_"
    "extension/3.0.0"
)
VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_VERSION = "3.0.0"
VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_FROZEN_AT_UTC = (
    "2026-07-22T01:17:31Z"
)
PRODUCTION_PRE_EXECUTION_REVIEW_CARRIER_SCHEMA_ID = (
    "betelgeuze.engine_v2_production_pre_execution_review_carrier/1.0.0"
)
PRODUCTION_AUTHORIZATION_CARRIER_SCHEMA_ID = (
    "betelgeuze.engine_v2_production_authorization_carrier/1.0.0"
)
PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_EVENT_SCHEMA_ID = (
    "betelgeuze.engine_v2_production_review_authorization_custody_extension_event/1.0.0"
)
PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_SIGNATURE_ALGORITHM = "ed25519"
PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_LANES = (
    "energy_force",
    "minimization",
)
PRODUCTION_PRE_EXECUTION_REVIEW_CARRIER_MAX_VALIDITY = timedelta(hours=4)
PRODUCTION_AUTHORIZATION_CARRIER_MAX_VALIDITY = timedelta(hours=4)
PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_EVENT_MAX_HANDOFF_DURATION = (
    timedelta(hours=24)
)
PRODUCTION_REVIEW_AUTHORIZATION_MAX_SIGNED_TRANSPORT_BYTES = 4 * 1024 * 1024
PRODUCTION_REVIEW_AUTHORIZATION_MAX_RAW_UPSTREAM_BYTES = 4 * 1024 * 1024
PRODUCTION_REVIEW_AUTHORIZATION_MAX_TRUST_ANCHORS = 4096
PRODUCTION_REVIEW_AUTHORIZATION_MAX_CONTRACT_ROWS = 256
PRODUCTION_REVIEW_AUTHORIZATION_MAX_ARGV_ITEMS = 64
PRODUCTION_REVIEW_AUTHORIZATION_MAX_ARGV_ITEM_BYTES = 4 * 1024
PRODUCTION_REVIEW_AUTHORIZATION_MAX_ARGV_TOTAL_BYTES = 64 * 1024
PRODUCTION_REVIEW_AUTHORIZATION_MAX_EXTERNAL_SEQUENCE_ITEMS = 4096
PRODUCTION_REVIEW_AUTHORIZATION_MAX_EXTERNAL_SEQUENCE_TOTAL_BYTES = 256 * 1024
PRODUCTION_REVIEW_AUTHORIZATION_MAX_HMAC_KEY_BYTES = 4 * 1024
PRODUCTION_REVIEW_AUTHORIZATION_MAX_HMAC_KEY_TOTAL_BYTES = 4 * 1024 * 1024
PRODUCTION_REVIEW_AUTHORIZATION_MAX_JSON_DEPTH = 128
PRODUCTION_REVIEW_AUTHORIZATION_MAX_STATUS_LINEAGE_ITEMS = 64
PRODUCTION_REVIEW_AUTHORIZATION_MAX_STATUS_LINEAGE_TOTAL_BYTES = 16 * 1024 * 1024

# Filled after the canonical projection is finalized.  Contract access fails
# closed if any later edit changes the projection.
FROZEN_VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256 = (
    "b41e48da2d11118e3e3fabae0ef83694f4b0fbebb28b6f46cb6ab39613f961c3"
)
FROZEN_LEGACY_VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256_V2 = (
    "d7c0a32d52777b3406cd7e820e36addd5d7e98af7662f9400d6f1b450ee8dda3"
)
FROZEN_LEGACY_VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256_V1 = (
    "3cb1d5c4289ac5026e5cbc8dc623239469f0fafe8bdce2ffc32bac11cfa549db"
)

_CLAIM_POLICY = {
    "production_validation_execution_authorized": False,
    "production_validation_results_collected": False,
    "force_or_energy_validated": False,
    "minimization_validated": False,
    "scientifically_validated": False,
    "parameter_fitting_proposal_authorized": False,
    "parameter_fitting_authorized": False,
    "benchmark_validated": False,
    "product_qualified": False,
    "customer_execution_enabled": False,
    "claim_safe": False,
}
_BLOCKERS = (
    "production_pre_execution_review_carrier_not_provisioned",
    "production_authorization_carrier_not_provisioned",
    "production_review_authorization_custody_events_not_provisioned",
    "energy_force_upstream_symmetric_hmac_chain",
    "trusted_production_review_key_not_provisioned",
    "trusted_production_authorization_key_not_provisioned",
    "external_custody_successor_uniqueness_not_provisioned",
    "global_one_use_permit_registry_not_provisioned",
    "reservation_and_later_custody_stages_not_implemented",
    "production_validation_result_not_collected",
    "two_production_cpu_hosts_missing",
    "independent_human_result_review_missing",
)
_RUN_CONTEXT_FIELDS = {
    "permit_sha256",
    "permit_id_sha256",
    "study_id_sha256",
    "run_id_sha256",
    "authorization_nonce_sha256",
    "contract_bundle_sha256_rows",
    "code_commit_sha",
    "source_sha256",
    "source_manifest_sha256",
    "dependency_manifest_sha256",
    "runtime_manifest_sha256",
    "seed",
    "command_argv",
    "artifact_output_root_identity_sha256",
    "custodian_identity_sha256",
    "enrolled_host_identity_sha256",
    "evidence_authority_identity_sha256",
    "evidence_authority_key_id",
    "current_status_snapshot_sha256",
    "current_status_authority_identity_sha256",
    "current_status_authority_key_id",
    "process_launch_identity_sha256",
}
_UPSTREAM_REVIEW_ARGUMENT_FIELDS = {
    "trusted_reviewer_keys",
    "expected_implementation_author_identity_sha256",
}
_UPSTREAM_AUTHORIZATION_ARGUMENT_FIELDS = {
    "trusted_reviewer_keys",
    "expected_implementation_author_identity_sha256",
    "trusted_operator_keys",
    "expected_code_commit_sha",
    "expected_runner_source_sha256",
    "expected_execution_environment_contract_sha256",
    "expected_result_receipt_contract_sha256",
    "expected_dependency_artifact_sha256_rows",
    "revoked_receipt_sha256s",
    "revoked_review_attestation_sha256s",
    "consumed_nonce_sha256s",
}
_PRE_EXECUTION_REVERIFICATION_ARGUMENT_FIELDS = {
    "expected_carrier_sha256",
    "expected_prior_custody_event_sha256",
    "upstream_review_verification_arguments",
    "trusted_production_reviewer_keys",
    "revoked_production_reviewer_key_ids",
    "revoked_upstream_reviewer_key_ids",
    "revoked_carrier_sha256s",
    "superseded_carrier_sha256s",
    "revoked_upstream_review_sha256s",
    "superseded_upstream_review_sha256s",
}
_BASE_PERMIT_REVERIFICATION_ARGUMENT_FIELDS = {
    "expected_permit_id_sha256",
    "expected_study_id_sha256",
    "expected_authorization_nonce_sha256",
    "expected_contract_bundle_sha256_rows",
    "expected_code_commit_sha",
    "expected_source_sha256",
    "expected_source_manifest_sha256",
    "expected_dependency_manifest_sha256",
    "expected_runtime_manifest_sha256",
    "expected_seed",
    "expected_command_argv",
    "expected_artifact_output_root_identity_sha256",
    "minimum_external_log_sequence",
    "expected_external_log_checkpoint_sha256",
    "revoked_authority_key_ids",
    "revoked_permit_sha256s",
    "superseded_permit_sha256s",
    "consumed_permit_sha256s",
}
_BASE_SEQUENCE_TWO_REVERIFICATION_ARGUMENT_FIELDS = {
    "trusted_authority_keys",
    "trusted_custody_keys",
    "permit_verification_arguments",
    "revoked_authority_key_ids",
    "expected_current_status_snapshot_sha256",
    "expected_current_status_checkpoint_sha256",
    "expected_sequence_one_custody_event_sha256",
    "expected_sequence_one_from_role",
    "expected_sequence_one_from_role_identity_sha256",
    "expected_sequence_one_from_key_id",
    "expected_sequence_one_to_role",
    "expected_sequence_one_to_role_identity_sha256",
    "expected_sequence_one_to_key_id",
    "expected_sequence_two_custody_event_sha256",
    "expected_sequence_two_from_role",
    "expected_sequence_two_from_role_identity_sha256",
    "expected_sequence_two_from_key_id",
    "expected_sequence_two_to_role",
    "expected_sequence_two_to_role_identity_sha256",
    "expected_sequence_two_to_key_id",
}
_EXTENSION_STAGE3_REVERIFICATION_ARGUMENT_FIELDS = {
    "expected_carrier_sha256",
    "upstream_review_verification_arguments",
    "trusted_production_reviewer_keys",
}
_EXTENSION_STAGE4_REVERIFICATION_ARGUMENT_FIELDS = {
    "expected_carrier_sha256",
    "upstream_authorization_verification_arguments",
    "trusted_production_authorization_keys",
}
_EXTENSION_SEQUENCE_THREE_EVENT_REVERIFICATION_ARGUMENT_FIELDS = {
    "expected_custody_event_sha256",
    "expected_from_role",
    "expected_from_role_identity_sha256",
    "expected_from_key_id",
    "expected_to_role",
    "expected_to_role_identity_sha256",
    "expected_to_key_id",
}
_BASE_PERMIT_INTEGER_FIELDS = {"seed", "external_log_sequence"}
_BASE_STATUS_INTEGER_FIELDS = {"status_sequence"}
_BASE_CUSTODY_EVENT_INTEGER_FIELDS = {
    "raw_artifact_byte_count",
    "custody_sequence",
}
_UPSTREAM_AUTHORIZATION_INTEGER_FIELDS = {"maximum_execution_count"}
_VERIFICATION_SEAL = object()


class ValidationProductionReviewAuthorizationCustodyExtensionError(ValueError):
    """A companion contract, carrier, context, or trust input is invalid."""


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
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production review/authorization value is not canonical JSON"
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
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            f"{name} must be a lowercase SHA-256"
        )
    return value


def _require_commit(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 40
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            f"{name} must be a lowercase Git commit SHA"
        )
    return value


def _require_token(value: object, *, name: str, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            f"{name} is invalid"
        )
    try:
        encoded = value.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            f"{name} must be ASCII"
        ) from exc
    allowed = b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:/-"
    if any(byte not in allowed for byte in encoded):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            f"{name} contains an unsupported character"
        )
    return value


def _require_lane(value: object) -> str:
    lane = _require_token(value, name="production lane")
    if lane not in PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_LANES:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production lane is unsupported"
        )
    return lane


def _format_utc(value: datetime, *, name: str) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            f"{name} must be timezone-aware"
        )
    normalized = value.astimezone(timezone.utc)
    if normalized.microsecond:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            f"{name} must have whole-second precision"
        )
    return normalized.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_utc(value: object, *, name: str) -> datetime:
    if not isinstance(value, str):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            f"{name} must be a UTC timestamp"
        )
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            f"{name} must be a canonical UTC timestamp"
        ) from exc
    return parsed


def _require_raw_bytes(value: object, *, name: str, maximum: int) -> bytes:
    if type(value) is not bytes or not value or len(value) > maximum:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            f"{name} must be non-empty bytes within the fixed bound"
        )
    return value


def _require_bounded_json_nesting(raw: bytes, *, name: str) -> None:
    """Reject excessive container depth before invoking the JSON decoder."""

    depth = 0
    in_string = False
    escaped = False
    for byte in raw:
        if in_string:
            if escaped:
                escaped = False
            elif byte == 0x5C:  # backslash
                escaped = True
            elif byte == 0x22:  # quote
                in_string = False
            continue
        if byte == 0x22:
            in_string = True
        elif byte in (0x7B, 0x5B):  # { [
            depth += 1
            if depth > PRODUCTION_REVIEW_AUTHORIZATION_MAX_JSON_DEPTH:
                raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                    f"{name} exceeds the fixed JSON nesting bound"
                )
        elif byte in (0x7D, 0x5D):  # } ]
            depth -= 1
            if depth < 0:
                break


def _load_raw_document(value: object, *, name: str, maximum: int) -> dict[str, Any]:
    raw = _require_raw_bytes(value, name=name, maximum=maximum)
    _require_bounded_json_nesting(raw, name=name)

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in pairs:
            if key in result:
                raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                    f"{name} contains a duplicate JSON key"
                )
            result[key] = item
        return result

    try:
        loaded = json.loads(raw.decode("utf-8"), object_pairs_hook=reject_duplicates)
    except ValidationProductionReviewAuthorizationCustodyExtensionError:
        raise
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            f"{name} must be UTF-8 JSON"
        ) from exc
    if type(loaded) is not dict:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            f"{name} root must be an exact JSON object"
        )
    return loaded


def _require_claims_closed(value: Mapping[str, Any]) -> None:
    if any(value.get(key) is not False for key in _CLAIM_POLICY):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production carrier cannot promote scientific or product claims"
        )


def _contract_rows(value: object) -> list[dict[str, str]]:
    if (
        type(value) is not dict
        or not value
        or len(value) > PRODUCTION_REVIEW_AUTHORIZATION_MAX_CONTRACT_ROWS
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "contract bundle must be a non-empty exact dict within its row bound"
        )
    rows: list[dict[str, str]] = []
    for contract_id, digest in value.items():
        rows.append(
            {
                "contract_id": _require_token(
                    contract_id, name="contract bundle id", maximum=512
                ),
                "sha256": _require_sha256(digest, name="contract bundle digest"),
            }
        )
    rows.sort(key=lambda row: row["contract_id"])
    if len({row["contract_id"] for row in rows}) != len(rows):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "contract bundle contains duplicate ids"
        )
    expected_extension = FROZEN_VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256
    if (
        value.get(
            VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_ID
        )
        != expected_extension
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "permit contract bundle omits or cross-wires the custody extension"
        )
    return rows


def _argv(value: object) -> list[str]:
    if (
        type(value) not in (list, tuple)
        or not value
        or len(value) > PRODUCTION_REVIEW_AUTHORIZATION_MAX_ARGV_ITEMS
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "command argv is empty or exceeds its item bound"
        )
    normalized: list[str] = []
    total = 0
    for item in value:
        if not isinstance(item, str) or not item:
            raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                "command argv contains an invalid item"
            )
        try:
            encoded = item.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                "command argv is not valid UTF-8"
            ) from exc
        if len(encoded) > PRODUCTION_REVIEW_AUTHORIZATION_MAX_ARGV_ITEM_BYTES:
            raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                "command argv item exceeds its byte bound"
            )
        total += len(encoded)
        normalized.append(item)
    if total > PRODUCTION_REVIEW_AUTHORIZATION_MAX_ARGV_TOTAL_BYTES:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "command argv exceeds its aggregate byte bound"
        )
    return normalized


def _run_context_projection(value: object) -> dict[str, Any]:
    if type(value) is not dict or set(value) != _RUN_CONTEXT_FIELDS:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "run context must be an exact built-in dict with frozen fields"
        )
    seed = value["seed"]
    if type(seed) is not int or not (0 <= seed < 2**63):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "run seed is invalid"
        )
    return {
        "permit_sha256": _require_sha256(value["permit_sha256"], name="permit"),
        "permit_id_sha256": _require_sha256(
            value["permit_id_sha256"], name="permit id"
        ),
        "study_id_sha256": _require_sha256(value["study_id_sha256"], name="study id"),
        "run_id_sha256": _require_sha256(value["run_id_sha256"], name="run id"),
        "authorization_nonce_sha256": _require_sha256(
            value["authorization_nonce_sha256"], name="authorization nonce"
        ),
        "contract_bundle_sha256_rows": _contract_rows(
            value["contract_bundle_sha256_rows"]
        ),
        "code_commit_sha": _require_commit(
            value["code_commit_sha"], name="code commit"
        ),
        "source_sha256": _require_sha256(value["source_sha256"], name="source"),
        "source_manifest_sha256": _require_sha256(
            value["source_manifest_sha256"], name="source manifest"
        ),
        "dependency_manifest_sha256": _require_sha256(
            value["dependency_manifest_sha256"], name="dependency manifest"
        ),
        "runtime_manifest_sha256": _require_sha256(
            value["runtime_manifest_sha256"], name="runtime manifest"
        ),
        "seed": seed,
        "command_argv": _argv(value["command_argv"]),
        "artifact_output_root_identity_sha256": _require_sha256(
            value["artifact_output_root_identity_sha256"],
            name="artifact output root identity",
        ),
        "custodian_identity_sha256": _require_sha256(
            value["custodian_identity_sha256"], name="custodian identity"
        ),
        "enrolled_host_identity_sha256": _require_sha256(
            value["enrolled_host_identity_sha256"], name="enrolled host identity"
        ),
        "evidence_authority_identity_sha256": _require_sha256(
            value["evidence_authority_identity_sha256"],
            name="evidence authority identity",
        ),
        "evidence_authority_key_id": _require_token(
            value["evidence_authority_key_id"], name="evidence authority key id"
        ),
        "current_status_snapshot_sha256": _require_sha256(
            value["current_status_snapshot_sha256"], name="current status snapshot"
        ),
        "current_status_authority_identity_sha256": _require_sha256(
            value["current_status_authority_identity_sha256"],
            name="current status authority identity",
        ),
        "current_status_authority_key_id": _require_token(
            value["current_status_authority_key_id"],
            name="current status authority key id",
        ),
        "process_launch_identity_sha256": _require_sha256(
            value["process_launch_identity_sha256"], name="process launch identity"
        ),
    }


def _trusted_review_keys(arguments: object, *, lane: str) -> dict[str, object]:
    if (
        type(arguments) is not dict
        or set(arguments) != _UPSTREAM_REVIEW_ARGUMENT_FIELDS
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "upstream review arguments do not match the exact frozen fields"
        )
    trust = arguments["trusted_reviewer_keys"]
    if (
        type(trust) is not dict
        or not trust
        or len(trust) > PRODUCTION_REVIEW_AUTHORIZATION_MAX_TRUST_ANCHORS
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "upstream reviewer trust map is empty or exceeds its fixed bound"
        )
    expected_type = (
        ScientificReviewerTrustAnchor
        if lane == "energy_force"
        else MinimizationScientificReviewerTrustAnchor
    )
    key_ids: set[str] = set()
    identities: set[str] = set()
    key_material: set[bytes] = set()
    total_key_bytes = 0
    for key_id, anchor in trust.items():
        normalized_key_id = _require_token(key_id, name="upstream reviewer key id")
        if type(anchor) is not expected_type:
            raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                "upstream reviewer trust map contains an invalid anchor type"
            )
        identity = _require_sha256(
            anchor.reviewer_identity_sha256, name="upstream reviewer identity"
        )
        material = anchor.verification_key
        if type(material) is not bytes or not material:
            raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                "upstream reviewer trust material is invalid"
            )
        if lane == "energy_force" and len(material) > (
            PRODUCTION_REVIEW_AUTHORIZATION_MAX_HMAC_KEY_BYTES
        ):
            raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                "upstream HMAC reviewer key exceeds its fixed byte bound"
            )
        total_key_bytes += len(material)
        if total_key_bytes > (PRODUCTION_REVIEW_AUTHORIZATION_MAX_HMAC_KEY_TOTAL_BYTES):
            raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                "upstream reviewer trust material exceeds its aggregate byte bound"
            )
        if (
            normalized_key_id in key_ids
            or identity in identities
            or material in key_material
        ):
            raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                "upstream reviewer trust map contains an alias"
            )
        key_ids.add(normalized_key_id)
        identities.add(identity)
        key_material.add(material)
    _require_sha256(
        arguments["expected_implementation_author_identity_sha256"],
        name="expected implementation author identity",
    )
    return trust


def _require_review_role_separation(
    *,
    run_context_projection: dict[str, Any],
    upstream_review: ReferenceValidationReviewVerification
    | ReferenceMinimizationValidationReviewVerification,
    upstream_trust: dict[str, object],
    production_reviewer_identity_sha256: str,
    production_reviewer_key_id: str,
    production_public_key: bytes,
    production_private_key: bytes | None = None,
    production_trust: dict[str, ProductionReviewCarrierTrustAnchor] | None = None,
) -> None:
    """Enforce all carrier-visible governance identity/key/material separation."""

    bound_context_identities = {
        run_context_projection["custodian_identity_sha256"],
        run_context_projection["enrolled_host_identity_sha256"],
        run_context_projection["evidence_authority_identity_sha256"],
        run_context_projection["current_status_authority_identity_sha256"],
    }
    if len(bound_context_identities) != 4:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "bound production context identities contain a role alias"
        )
    upstream_identities = {
        anchor.reviewer_identity_sha256
        for anchor in upstream_trust.values()  # type: ignore[attr-defined]
    }
    if (
        upstream_review.implementation_author_identity_sha256
        in bound_context_identities
        or upstream_review.implementation_author_identity_sha256 in upstream_identities
        or upstream_identities & bound_context_identities
        or production_reviewer_identity_sha256 in bound_context_identities
        or production_reviewer_identity_sha256
        in {
            upstream_review.implementation_author_identity_sha256,
            *upstream_identities,
        }
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production review governance identities contain a role alias"
        )
    bound_context_key_ids = {
        run_context_projection["evidence_authority_key_id"],
        run_context_projection["current_status_authority_key_id"],
    }
    if len(bound_context_key_ids) != 2:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "bound production context key ids contain a role alias"
        )
    upstream_key_ids = set(upstream_trust)
    if (
        upstream_key_ids & bound_context_key_ids
        or production_reviewer_key_id in bound_context_key_ids
        or production_reviewer_key_id in upstream_key_ids
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production review governance key ids contain a role alias"
        )
    upstream_material = {
        anchor.verification_key
        for anchor in upstream_trust.values()  # type: ignore[attr-defined]
    }
    candidate_material = {production_public_key}
    if production_private_key is not None:
        candidate_material.add(production_private_key)
    if candidate_material & upstream_material:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production review key material aliases upstream trust material"
        )
    if production_trust is not None:
        production_key_ids = set(production_trust)
        production_identities = {
            anchor.reviewer_identity_sha256 for anchor in production_trust.values()
        }
        production_material = {
            anchor.verification_key for anchor in production_trust.values()
        }
        if (
            production_key_ids & (upstream_key_ids | bound_context_key_ids)
            or production_identities
            & (
                upstream_identities
                | bound_context_identities
                | {upstream_review.implementation_author_identity_sha256}
            )
            or production_material & upstream_material
        ):
            raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                "production and upstream reviewer trust maps contain a global alias"
            )


def _verify_upstream_review(
    raw_review_attestation_bytes: bytes,
    *,
    lane: str,
    upstream_review_verification_arguments: dict[str, object],
    checked_at: datetime,
) -> (
    ReferenceValidationReviewVerification
    | ReferenceMinimizationValidationReviewVerification
):
    raw = _require_raw_bytes(
        raw_review_attestation_bytes,
        name="raw upstream review attestation",
        maximum=PRODUCTION_REVIEW_AUTHORIZATION_MAX_RAW_UPSTREAM_BYTES,
    )
    review_document = _load_raw_document(
        raw,
        name="raw upstream review attestation",
        maximum=PRODUCTION_REVIEW_AUTHORIZATION_MAX_RAW_UPSTREAM_BYTES,
    )
    _require_exact_json_scalar_types(
        review_document,
        name="raw upstream review attestation",
        integer_field_names=set(),
    )
    trust = _trusted_review_keys(
        upstream_review_verification_arguments,
        lane=lane,
    )
    author = upstream_review_verification_arguments[
        "expected_implementation_author_identity_sha256"
    ]
    try:
        if lane == "energy_force":
            return verify_signed_reference_validation_review_attestation(
                raw,
                trusted_reviewer_keys=trust,  # type: ignore[arg-type]
                expected_implementation_author_identity_sha256=author,  # type: ignore[arg-type]
                checked_at=checked_at,
            )
        return verify_signed_reference_minimization_validation_review_attestation(
            raw,
            trusted_reviewer_keys=trust,  # type: ignore[arg-type]
            expected_implementation_author_identity_sha256=author,  # type: ignore[arg-type]
            checked_at=checked_at,
        )
    except (
        ReferenceValidationReviewError,
        ReferenceMinimizationValidationReviewError,
    ) as exc:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "raw upstream pre-execution review re-verification failed"
        ) from exc


@dataclass(frozen=True, slots=True)
class ProductionReviewCarrierTrustAnchor:
    reviewer_identity_sha256: str
    verification_key: bytes = field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "reviewer_identity_sha256",
            _require_sha256(
                self.reviewer_identity_sha256,
                name="production review carrier signer identity",
            ),
        )
        key = self.verification_key
        if type(key) is not bytes or len(key) != 32:
            raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                "production review carrier trust key must be 32 public-key bytes"
            )


@dataclass(frozen=True, slots=True, init=False)
class ProductionPreExecutionReviewCarrierVerification:
    carrier_sha256: str
    raw_carrier_sha256: str
    raw_carrier_byte_count: int
    lane: str
    permit_sha256: str
    study_id_sha256: str
    run_id_sha256: str
    authorization_nonce_sha256: str
    prior_custody_event_sha256: str
    current_status_snapshot_sha256: str
    process_launch_identity_sha256: str
    upstream_review_attestation_sha256: str
    upstream_review_raw_sha256: str
    implementation_author_identity_sha256: str
    independent_reviewer_identity_sha256: str
    upstream_reviewer_key_id: str
    production_reviewer_identity_sha256: str
    production_reviewer_key_id: str
    signed_at_utc: str
    expires_at_utc: str
    checked_at_utc: str
    pre_execution_review_carrier_verified: bool = True
    production_validation_execution_authorized: bool = False
    scientifically_validated: bool = False
    parameter_fitting_authorized: bool = False
    product_qualified: bool = False
    claim_safe: bool = False
    _verification_seal: object = field(init=False, repr=False, compare=False)


def _new_review_verification(
    **values: object,
) -> ProductionPreExecutionReviewCarrierVerification:
    instance = object.__new__(ProductionPreExecutionReviewCarrierVerification)
    for name, value in values.items():
        object.__setattr__(instance, name, value)
    object.__setattr__(instance, "pre_execution_review_carrier_verified", True)
    object.__setattr__(instance, "production_validation_execution_authorized", False)
    object.__setattr__(instance, "scientifically_validated", False)
    object.__setattr__(instance, "parameter_fitting_authorized", False)
    object.__setattr__(instance, "product_qualified", False)
    object.__setattr__(instance, "claim_safe", False)
    object.__setattr__(instance, "_verification_seal", _VERIFICATION_SEAL)
    return instance


def _review_projection(
    *,
    lane: str,
    run_context: dict[str, object],
    prior_custody_event_sha256: str,
    raw_review_attestation_bytes: bytes,
    upstream_review: ReferenceValidationReviewVerification
    | ReferenceMinimizationValidationReviewVerification,
    raw_review_document: dict[str, Any],
    production_reviewer_identity_sha256: str,
    production_reviewer_key_id: str,
    signed_at_utc: str,
    expires_at_utc: str,
) -> dict[str, Any]:
    selected_lane = _require_lane(lane)
    context = _run_context_projection(run_context)
    expected_schema = (
        REFERENCE_VALIDATION_REVIEW_ATTESTATION_SCHEMA_ID
        if selected_lane == "energy_force"
        else REFERENCE_MINIMIZATION_VALIDATION_REVIEW_ATTESTATION_SCHEMA_ID
    )
    expected_contract = (
        FROZEN_REFERENCE_VALIDATION_REVIEW_CONTRACT_SHA256
        if selected_lane == "energy_force"
        else FROZEN_REFERENCE_MINIMIZATION_VALIDATION_REVIEW_CONTRACT_SHA256
    )
    if raw_review_document.get("schema_id") != expected_schema:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "upstream review schema is cross-wired to the production lane"
        )
    if upstream_review.contract_sha256 != expected_contract:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "upstream review contract is cross-wired to the production lane"
        )
    if raw_review_document.get("attestation_sha256") != (
        upstream_review.attestation_sha256
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "upstream review logical identity differs from its raw carrier"
        )
    production_identity = _require_sha256(
        production_reviewer_identity_sha256,
        name="production reviewer identity",
    )
    forbidden_identities = {
        upstream_review.implementation_author_identity_sha256,
        upstream_review.independent_reviewer_identity_sha256,
        context["custodian_identity_sha256"],
        context["enrolled_host_identity_sha256"],
        context["evidence_authority_identity_sha256"],
        context["current_status_authority_identity_sha256"],
    }
    if production_identity in forbidden_identities:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production reviewer identity aliases another governance role"
        )
    context_identities = {
        context["custodian_identity_sha256"],
        context["enrolled_host_identity_sha256"],
        context["evidence_authority_identity_sha256"],
        context["current_status_authority_identity_sha256"],
    }
    if {
        upstream_review.implementation_author_identity_sha256,
        upstream_review.independent_reviewer_identity_sha256,
    } & context_identities:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "upstream review identity aliases a bound production role"
        )
    production_key_id = _require_token(
        production_reviewer_key_id,
        name="production reviewer key id",
    )
    if production_key_id in {
        upstream_review.reviewer_key_id,
        context["evidence_authority_key_id"],
        context["current_status_authority_key_id"],
    }:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production reviewer key id aliases another governance role"
        )
    if upstream_review.reviewer_key_id in {
        context["evidence_authority_key_id"],
        context["current_status_authority_key_id"],
    }:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "upstream reviewer key id aliases a bound production role"
        )
    signed_at = _parse_utc(signed_at_utc, name="carrier signed_at")
    expires_at = _parse_utc(expires_at_utc, name="carrier expires_at")
    upstream_reviewed = _parse_utc(
        upstream_review.reviewed_at_utc, name="upstream review reviewed_at"
    )
    upstream_expires = _parse_utc(
        upstream_review.expires_at_utc, name="upstream review expires_at"
    )
    if signed_at < upstream_reviewed or expires_at > upstream_expires:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production review carrier is outside the upstream review lifetime"
        )
    if expires_at <= signed_at or (
        expires_at - signed_at > PRODUCTION_PRE_EXECUTION_REVIEW_CARRIER_MAX_VALIDITY
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production review carrier validity interval is invalid"
        )
    return {
        "schema_id": PRODUCTION_PRE_EXECUTION_REVIEW_CARRIER_SCHEMA_ID,
        "contract_sha256": (
            FROZEN_VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256
        ),
        "evidence_class": PRODUCTION_EVIDENCE_CLASS,
        "artifact_stage": "pre_execution_review",
        "lane": selected_lane,
        **context,
        "prior_custody_event_sha256": _require_sha256(
            prior_custody_event_sha256, name="prior custody event"
        ),
        "upstream_review_schema_id": expected_schema,
        "upstream_review_contract_sha256": expected_contract,
        "upstream_review_artifact_binding_sha256": upstream_review.artifact_binding_sha256,
        "upstream_review_attestation_sha256": upstream_review.attestation_sha256,
        "upstream_review_raw_sha256": _raw_sha256(raw_review_attestation_bytes),
        "upstream_review_raw_byte_count": len(raw_review_attestation_bytes),
        "upstream_review_nonce_sha256": _require_sha256(
            raw_review_document.get("nonce_sha256"), name="upstream review nonce"
        ),
        "implementation_author_identity_sha256": (
            upstream_review.implementation_author_identity_sha256
        ),
        "independent_reviewer_identity_sha256": (
            upstream_review.independent_reviewer_identity_sha256
        ),
        "upstream_reviewer_key_id": upstream_review.reviewer_key_id,
        "upstream_reviewed_at_utc": upstream_review.reviewed_at_utc,
        "upstream_review_expires_at_utc": upstream_review.expires_at_utc,
        "production_reviewer_identity_sha256": production_identity,
        "production_reviewer_key_id": production_key_id,
        "signed_at_utc": signed_at_utc,
        "expires_at_utc": expires_at_utc,
        "upstream_review_reverified": True,
        "full_asymmetric_chain_established": False,
        **_CLAIM_POLICY,
        "superseded": False,
        "revoked": False,
    }


def build_signed_production_pre_execution_review_carrier(
    *,
    raw_review_attestation_bytes: bytes,
    lane: str,
    run_context: dict[str, object],
    upstream_review_verification_arguments: dict[str, object],
    prior_custody_event_sha256: str,
    production_reviewer_identity_sha256: str,
    production_reviewer_key_id: str,
    signing_key: bytes,
    signed_at: datetime,
    expires_at: datetime,
) -> dict[str, Any]:
    """Wrap one exact upstream review in a production-only Ed25519 carrier."""

    selected_lane = _require_lane(lane)
    raw = _require_raw_bytes(
        raw_review_attestation_bytes,
        name="raw upstream review attestation",
        maximum=PRODUCTION_REVIEW_AUTHORIZATION_MAX_RAW_UPSTREAM_BYTES,
    )
    raw_document = _load_raw_document(
        raw,
        name="raw upstream review attestation",
        maximum=PRODUCTION_REVIEW_AUTHORIZATION_MAX_RAW_UPSTREAM_BYTES,
    )
    upstream = _verify_upstream_review(
        raw,
        lane=selected_lane,
        upstream_review_verification_arguments=(upstream_review_verification_arguments),
        checked_at=signed_at,
    )
    private_key = signing_key
    if type(private_key) is not bytes or len(private_key) != 32:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production review carrier signing key must be 32 private-key bytes"
        )
    try:
        public_key = ed25519_public_key_bytes(private_key)
    except ReferenceMinimizationValidationEd25519Error as exc:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production review carrier Ed25519 key derivation failed"
        ) from exc
    upstream_trust = _trusted_review_keys(
        upstream_review_verification_arguments,
        lane=selected_lane,
    )
    context_projection = _run_context_projection(run_context)
    _require_review_role_separation(
        run_context_projection=context_projection,
        upstream_review=upstream,
        upstream_trust=upstream_trust,
        production_reviewer_identity_sha256=_require_sha256(
            production_reviewer_identity_sha256,
            name="production reviewer identity",
        ),
        production_reviewer_key_id=_require_token(
            production_reviewer_key_id,
            name="production reviewer key id",
        ),
        production_public_key=public_key,
        production_private_key=private_key,
    )
    projection = _review_projection(
        lane=selected_lane,
        run_context=run_context,
        prior_custody_event_sha256=prior_custody_event_sha256,
        raw_review_attestation_bytes=raw,
        upstream_review=upstream,
        raw_review_document=raw_document,
        production_reviewer_identity_sha256=production_reviewer_identity_sha256,
        production_reviewer_key_id=production_reviewer_key_id,
        signed_at_utc=_format_utc(signed_at, name="carrier signed_at"),
        expires_at_utc=_format_utc(expires_at, name="carrier expires_at"),
    )
    payload = dict(projection)
    payload["carrier_sha256"] = _sha256(projection)
    try:
        signature_value = sign_ed25519(_canonical_bytes(payload), private_key)
    except ReferenceMinimizationValidationEd25519Error as exc:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production review carrier Ed25519 signing failed"
        ) from exc
    payload["signature"] = {
        "algorithm": (
            PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_SIGNATURE_ALGORITHM
        ),
        "key_id": _require_token(
            production_reviewer_key_id, name="production reviewer key id"
        ),
        "value": signature_value,
    }
    if len(_canonical_bytes(payload)) > (
        PRODUCTION_REVIEW_AUTHORIZATION_MAX_SIGNED_TRANSPORT_BYTES
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production review carrier exceeds its signed transport bound"
        )
    if not verify_ed25519(
        _canonical_bytes(
            {key: value for key, value in payload.items() if key != "signature"}
        ),
        signature_value,
        public_key,
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production review carrier self-verification failed"
        )
    return payload


def _external_sha256_set(value: object, *, name: str) -> set[str]:
    if type(value) not in (list, tuple) or len(value) > (
        PRODUCTION_REVIEW_AUTHORIZATION_MAX_EXTERNAL_SEQUENCE_ITEMS
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            f"{name} sequence exceeds its fixed bound"
        )
    if any(not isinstance(item, str) for item in value):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            f"{name} sequence contains a non-string value"
        )
    try:
        total_bytes = sum(len(item.encode("utf-8")) for item in value)
    except UnicodeEncodeError as exc:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            f"{name} sequence contains invalid Unicode"
        ) from exc
    if total_bytes > PRODUCTION_REVIEW_AUTHORIZATION_MAX_EXTERNAL_SEQUENCE_TOTAL_BYTES:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            f"{name} sequence exceeds its aggregate byte bound"
        )
    normalized = {_require_sha256(item, name=name) for item in value}
    if len(normalized) != len(value):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            f"{name} sequence contains duplicates"
        )
    return normalized


def _external_key_id_set(value: object, *, name: str) -> set[str]:
    if type(value) not in (list, tuple) or len(value) > (
        PRODUCTION_REVIEW_AUTHORIZATION_MAX_EXTERNAL_SEQUENCE_ITEMS
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            f"{name} sequence exceeds its fixed bound"
        )
    if any(not isinstance(item, str) for item in value):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            f"{name} sequence contains a non-string value"
        )
    try:
        total_bytes = sum(len(item.encode("utf-8")) for item in value)
    except UnicodeEncodeError as exc:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            f"{name} sequence contains invalid Unicode"
        ) from exc
    if total_bytes > PRODUCTION_REVIEW_AUTHORIZATION_MAX_EXTERNAL_SEQUENCE_TOTAL_BYTES:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            f"{name} sequence exceeds its aggregate byte bound"
        )
    normalized = {_require_token(item, name=name) for item in value}
    if len(normalized) != len(value):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            f"{name} sequence contains duplicates"
        )
    return normalized


def verify_signed_production_pre_execution_review_carrier(
    source: bytes,
    *,
    raw_review_attestation_bytes: bytes,
    expected_carrier_sha256: str,
    expected_lane: str,
    expected_run_context: dict[str, object],
    expected_prior_custody_event_sha256: str,
    upstream_review_verification_arguments: dict[str, object],
    trusted_production_reviewer_keys: dict[str, ProductionReviewCarrierTrustAnchor],
    checked_at: datetime,
    revoked_production_reviewer_key_ids: Sequence[str] = (),
    revoked_upstream_reviewer_key_ids: Sequence[str] = (),
    revoked_carrier_sha256s: Sequence[str] = (),
    superseded_carrier_sha256s: Sequence[str] = (),
    revoked_upstream_review_sha256s: Sequence[str] = (),
    superseded_upstream_review_sha256s: Sequence[str] = (),
) -> ProductionPreExecutionReviewCarrierVerification:
    """Reverify exact raw upstream and production carrier bytes."""

    raw_carrier = _require_raw_bytes(
        source,
        name="raw production review carrier",
        maximum=PRODUCTION_REVIEW_AUTHORIZATION_MAX_SIGNED_TRANSPORT_BYTES,
    )
    payload = _load_raw_document(
        raw_carrier,
        name="raw production review carrier",
        maximum=PRODUCTION_REVIEW_AUTHORIZATION_MAX_SIGNED_TRANSPORT_BYTES,
    )
    if raw_carrier != _canonical_bytes(payload):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production review carrier transport must be exact canonical JSON"
        )
    raw_carrier_sha256 = _raw_sha256(raw_carrier)
    if (
        type(trusted_production_reviewer_keys) is not dict
        or not trusted_production_reviewer_keys
        or len(trusted_production_reviewer_keys)
        > PRODUCTION_REVIEW_AUTHORIZATION_MAX_TRUST_ANCHORS
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production reviewer trust map is empty or exceeds its fixed bound"
        )
    identities: set[str] = set()
    materials: set[bytes] = set()
    for key_id, anchor in trusted_production_reviewer_keys.items():
        _require_token(key_id, name="trusted production reviewer key id")
        if type(anchor) is not ProductionReviewCarrierTrustAnchor:
            raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                "production reviewer trust map contains an invalid anchor"
            )
        if (
            anchor.reviewer_identity_sha256 in identities
            or anchor.verification_key in materials
        ):
            raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                "production reviewer trust map contains an alias"
            )
        identities.add(anchor.reviewer_identity_sha256)
        materials.add(anchor.verification_key)
    signature = payload.pop("signature", None)
    if type(signature) is not dict or set(signature) != {
        "algorithm",
        "key_id",
        "value",
    }:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production review carrier signature fields are invalid"
        )
    if signature["algorithm"] != (
        PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_SIGNATURE_ALGORITHM
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production review carrier signature algorithm is unsupported"
        )
    key_id = _require_token(signature["key_id"], name="production reviewer key id")
    if key_id in _external_key_id_set(
        revoked_production_reviewer_key_ids,
        name="revoked production reviewer key id",
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production reviewer key is revoked"
        )
    anchor = trusted_production_reviewer_keys.get(key_id)
    if type(anchor) is not ProductionReviewCarrierTrustAnchor:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production reviewer key is not trusted"
        )
    try:
        signature_verified = verify_ed25519(
            _canonical_bytes(payload), signature["value"], anchor.verification_key
        )
    except ReferenceMinimizationValidationEd25519Error as exc:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production review carrier Ed25519 verifier is unavailable"
        ) from exc
    if not signature_verified:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production review carrier signature verification failed"
        )
    carrier_sha256 = payload.pop("carrier_sha256", None)
    if carrier_sha256 != _sha256(payload):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production review carrier SHA-256 verification failed"
        )
    carrier_sha256 = _require_sha256(carrier_sha256, name="production review carrier")
    if carrier_sha256 != _require_sha256(
        expected_carrier_sha256, name="expected production review carrier"
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production review carrier is cross-wired to its out-of-band identity"
        )
    revoked_carriers = _external_sha256_set(
        revoked_carrier_sha256s, name="revoked production review carrier"
    )
    if {carrier_sha256, raw_carrier_sha256} & revoked_carriers:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production review carrier is revoked"
        )
    superseded_carriers = _external_sha256_set(
        superseded_carrier_sha256s, name="superseded production review carrier"
    )
    if {carrier_sha256, raw_carrier_sha256} & superseded_carriers:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production review carrier is superseded"
        )
    if payload.get("schema_id") != PRODUCTION_PRE_EXECUTION_REVIEW_CARRIER_SCHEMA_ID:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production review carrier schema is unsupported"
        )
    if payload.get("contract_sha256") != (
        FROZEN_VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production review carrier contract is cross-wired"
        )
    if payload.get("evidence_class") != PRODUCTION_EVIDENCE_CLASS:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production evidence class is missing or downgraded"
        )
    if payload.get("artifact_stage") != "pre_execution_review":
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production review carrier stage is cross-wired"
        )
    selected_lane = _require_lane(expected_lane)
    signed_at = _parse_utc(payload.get("signed_at_utc"), name="carrier signed_at")
    expires_at = _parse_utc(payload.get("expires_at_utc"), name="carrier expires_at")
    checked = _parse_utc(
        _format_utc(checked_at, name="carrier checked_at"), name="carrier checked_at"
    )
    if checked < signed_at or checked >= expires_at:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production review carrier is not currently valid"
        )
    raw_review = _require_raw_bytes(
        raw_review_attestation_bytes,
        name="raw upstream review attestation",
        maximum=PRODUCTION_REVIEW_AUTHORIZATION_MAX_RAW_UPSTREAM_BYTES,
    )
    raw_review_document = _load_raw_document(
        raw_review,
        name="raw upstream review attestation",
        maximum=PRODUCTION_REVIEW_AUTHORIZATION_MAX_RAW_UPSTREAM_BYTES,
    )
    upstream = _verify_upstream_review(
        raw_review,
        lane=selected_lane,
        upstream_review_verification_arguments=(upstream_review_verification_arguments),
        checked_at=signed_at,
    )
    if upstream.reviewer_key_id in _external_key_id_set(
        revoked_upstream_reviewer_key_ids,
        name="revoked upstream reviewer key id",
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "upstream reviewer key is revoked"
        )
    upstream_raw_sha256 = _raw_sha256(raw_review)
    revoked_upstream_reviews = _external_sha256_set(
        revoked_upstream_review_sha256s, name="revoked upstream review"
    )
    if {
        upstream.attestation_sha256,
        upstream_raw_sha256,
    } & revoked_upstream_reviews:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "upstream review is revoked"
        )
    superseded_upstream_reviews = _external_sha256_set(
        superseded_upstream_review_sha256s, name="superseded upstream review"
    )
    if {
        upstream.attestation_sha256,
        upstream_raw_sha256,
    } & superseded_upstream_reviews:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "upstream review is superseded"
        )
    upstream_trust = _trusted_review_keys(
        upstream_review_verification_arguments,
        lane=selected_lane,
    )
    context_projection = _run_context_projection(expected_run_context)
    _require_review_role_separation(
        run_context_projection=context_projection,
        upstream_review=upstream,
        upstream_trust=upstream_trust,
        production_reviewer_identity_sha256=anchor.reviewer_identity_sha256,
        production_reviewer_key_id=key_id,
        production_public_key=anchor.verification_key,
        production_trust=trusted_production_reviewer_keys,
    )
    expected_projection = _review_projection(
        lane=selected_lane,
        run_context=expected_run_context,
        prior_custody_event_sha256=expected_prior_custody_event_sha256,
        raw_review_attestation_bytes=raw_review,
        upstream_review=upstream,
        raw_review_document=raw_review_document,
        production_reviewer_identity_sha256=anchor.reviewer_identity_sha256,
        production_reviewer_key_id=key_id,
        signed_at_utc=payload["signed_at_utc"],
        expires_at_utc=payload["expires_at_utc"],
    )
    if _canonical_bytes(payload) != _canonical_bytes(expected_projection):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production review carrier fields do not match the exact expected run"
        )
    _require_claims_closed(payload)
    return _new_review_verification(
        carrier_sha256=carrier_sha256,
        raw_carrier_sha256=raw_carrier_sha256,
        raw_carrier_byte_count=len(raw_carrier),
        lane=selected_lane,
        permit_sha256=payload["permit_sha256"],
        study_id_sha256=payload["study_id_sha256"],
        run_id_sha256=payload["run_id_sha256"],
        authorization_nonce_sha256=payload["authorization_nonce_sha256"],
        prior_custody_event_sha256=payload["prior_custody_event_sha256"],
        current_status_snapshot_sha256=payload["current_status_snapshot_sha256"],
        process_launch_identity_sha256=payload["process_launch_identity_sha256"],
        upstream_review_attestation_sha256=upstream.attestation_sha256,
        upstream_review_raw_sha256=upstream_raw_sha256,
        implementation_author_identity_sha256=(
            upstream.implementation_author_identity_sha256
        ),
        independent_reviewer_identity_sha256=(
            upstream.independent_reviewer_identity_sha256
        ),
        upstream_reviewer_key_id=upstream.reviewer_key_id,
        production_reviewer_identity_sha256=anchor.reviewer_identity_sha256,
        production_reviewer_key_id=key_id,
        signed_at_utc=payload["signed_at_utc"],
        expires_at_utc=payload["expires_at_utc"],
        checked_at_utc=_format_utc(checked, name="carrier checked_at"),
    )


@dataclass(frozen=True, slots=True)
class ProductionAuthorizationCarrierTrustAnchor:
    operator_identity_sha256: str
    verification_key: bytes = field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "operator_identity_sha256",
            _require_sha256(
                self.operator_identity_sha256,
                name="production authorization carrier signer identity",
            ),
        )
        if type(self.verification_key) is not bytes or len(self.verification_key) != 32:
            raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                "production authorization carrier trust key must be 32 public-key bytes"
            )


@dataclass(frozen=True, slots=True, init=False)
class ProductionAuthorizationCarrierVerification:
    carrier_sha256: str
    raw_carrier_sha256: str
    raw_carrier_byte_count: int
    lane: str
    permit_sha256: str
    study_id_sha256: str
    run_id_sha256: str
    authorization_nonce_sha256: str
    prior_custody_event_sha256: str
    current_status_snapshot_sha256: str
    process_launch_identity_sha256: str
    pre_execution_review_carrier_sha256: str
    pre_execution_review_raw_sha256: str
    upstream_review_attestation_sha256: str
    upstream_review_raw_sha256: str
    upstream_authorization_receipt_sha256: str
    upstream_authorization_raw_sha256: str
    implementation_author_identity_sha256: str
    independent_reviewer_identity_sha256: str
    upstream_authorization_operator_identity_sha256: str
    upstream_authorization_key_id: str
    production_authorization_operator_identity_sha256: str
    production_authorization_key_id: str
    signed_at_utc: str
    expires_at_utc: str
    checked_at_utc: str
    authorization_carrier_verified: bool = True
    eligible_for_atomic_execution_reservation: bool = False
    production_validation_execution_authorized: bool = False
    scientifically_validated: bool = False
    parameter_fitting_authorized: bool = False
    product_qualified: bool = False
    claim_safe: bool = False
    _verification_seal: object = field(init=False, repr=False, compare=False)


def _new_authorization_verification(
    **values: object,
) -> ProductionAuthorizationCarrierVerification:
    instance = object.__new__(ProductionAuthorizationCarrierVerification)
    for name, value in values.items():
        object.__setattr__(instance, name, value)
    object.__setattr__(instance, "authorization_carrier_verified", True)
    object.__setattr__(instance, "eligible_for_atomic_execution_reservation", False)
    object.__setattr__(instance, "production_validation_execution_authorized", False)
    object.__setattr__(instance, "scientifically_validated", False)
    object.__setattr__(instance, "parameter_fitting_authorized", False)
    object.__setattr__(instance, "product_qualified", False)
    object.__setattr__(instance, "claim_safe", False)
    object.__setattr__(instance, "_verification_seal", _VERIFICATION_SEAL)
    return instance


def _dependency_rows(value: object) -> dict[str, str]:
    if (
        type(value) is not dict
        or not value
        or len(value) > PRODUCTION_REVIEW_AUTHORIZATION_MAX_CONTRACT_ROWS
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "authorization dependency rows must be an exact non-empty bounded dict"
        )
    normalized: dict[str, str] = {}
    for artifact_id, digest in value.items():
        normalized[_require_token(artifact_id, name="dependency artifact id")] = (
            _require_sha256(digest, name="dependency artifact digest")
        )
    return normalized


def _trusted_operator_keys(
    arguments: object,
    *,
    lane: str,
) -> dict[str, object]:
    if type(arguments) is not dict or set(arguments) != (
        _UPSTREAM_AUTHORIZATION_ARGUMENT_FIELDS
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "upstream authorization arguments do not match the exact frozen fields"
        )
    review_arguments = {
        "trusted_reviewer_keys": arguments["trusted_reviewer_keys"],
        "expected_implementation_author_identity_sha256": arguments[
            "expected_implementation_author_identity_sha256"
        ],
    }
    _trusted_review_keys(review_arguments, lane=lane)
    trust = arguments["trusted_operator_keys"]
    if (
        type(trust) is not dict
        or not trust
        or len(trust) > PRODUCTION_REVIEW_AUTHORIZATION_MAX_TRUST_ANCHORS
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "upstream operator trust map is empty or exceeds its fixed bound"
        )
    expected_type = (
        AuthorizationOperatorTrustAnchor
        if lane == "energy_force"
        else MinimizationAuthorizationOperatorTrustAnchor
    )
    key_ids: set[str] = set()
    identities: set[str] = set()
    materials: set[bytes] = set()
    total_key_bytes = 0
    for key_id, anchor in trust.items():
        normalized_key_id = _require_token(
            key_id, name="upstream authorization operator key id"
        )
        if type(anchor) is not expected_type:
            raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                "upstream operator trust map contains an invalid anchor type"
            )
        identity = _require_sha256(
            anchor.operator_identity_sha256,
            name="upstream authorization operator identity",
        )
        material = anchor.verification_key
        if type(material) is not bytes or not material:
            raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                "upstream authorization operator trust material is invalid"
            )
        if lane == "energy_force" and len(material) > (
            PRODUCTION_REVIEW_AUTHORIZATION_MAX_HMAC_KEY_BYTES
        ):
            raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                "upstream HMAC operator key exceeds its fixed byte bound"
            )
        total_key_bytes += len(material)
        if total_key_bytes > (PRODUCTION_REVIEW_AUTHORIZATION_MAX_HMAC_KEY_TOTAL_BYTES):
            raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                "upstream operator trust material exceeds its aggregate byte bound"
            )
        if (
            normalized_key_id in key_ids
            or identity in identities
            or material in materials
        ):
            raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                "upstream operator trust map contains an alias"
            )
        key_ids.add(normalized_key_id)
        identities.add(identity)
        materials.add(material)
    _require_commit(arguments["expected_code_commit_sha"], name="expected code commit")
    for name in (
        "expected_runner_source_sha256",
        "expected_execution_environment_contract_sha256",
        "expected_result_receipt_contract_sha256",
    ):
        _require_sha256(arguments[name], name=name.replace("_", " "))
    _dependency_rows(arguments["expected_dependency_artifact_sha256_rows"])
    _external_sha256_set(
        arguments["revoked_receipt_sha256s"], name="revoked authorization receipt"
    )
    _external_sha256_set(
        arguments["revoked_review_attestation_sha256s"],
        name="revoked authorization review",
    )
    _external_sha256_set(
        arguments["consumed_nonce_sha256s"], name="consumed authorization nonce"
    )
    return trust


def _verify_upstream_authorization(
    raw_authorization_receipt_bytes: bytes,
    *,
    raw_review_attestation_bytes: bytes,
    lane: str,
    upstream_authorization_verification_arguments: dict[str, object],
    checked_at: datetime,
) -> (
    ReferenceValidationAuthorizationVerification
    | ReferenceMinimizationValidationAuthorizationVerification
):
    raw_authorization = _require_raw_bytes(
        raw_authorization_receipt_bytes,
        name="raw upstream authorization receipt",
        maximum=PRODUCTION_REVIEW_AUTHORIZATION_MAX_RAW_UPSTREAM_BYTES,
    )
    authorization_document = _load_raw_document(
        raw_authorization,
        name="raw upstream authorization receipt",
        maximum=PRODUCTION_REVIEW_AUTHORIZATION_MAX_RAW_UPSTREAM_BYTES,
    )
    _require_exact_json_scalar_types(
        authorization_document,
        name="raw upstream authorization receipt",
        integer_field_names=_UPSTREAM_AUTHORIZATION_INTEGER_FIELDS,
    )
    raw_review = _require_raw_bytes(
        raw_review_attestation_bytes,
        name="raw upstream review attestation",
        maximum=PRODUCTION_REVIEW_AUTHORIZATION_MAX_RAW_UPSTREAM_BYTES,
    )
    selected_lane = _require_lane(lane)
    _trusted_operator_keys(
        upstream_authorization_verification_arguments,
        lane=selected_lane,
    )
    arguments = upstream_authorization_verification_arguments
    try:
        if selected_lane == "energy_force":
            return verify_signed_reference_validation_authorization_receipt(
                raw_authorization,
                review_attestation=raw_review,
                trusted_reviewer_keys=arguments["trusted_reviewer_keys"],  # type: ignore[arg-type]
                expected_implementation_author_identity_sha256=arguments[
                    "expected_implementation_author_identity_sha256"
                ],  # type: ignore[arg-type]
                trusted_operator_keys=arguments["trusted_operator_keys"],  # type: ignore[arg-type]
                checked_at=checked_at,
                expected_code_commit_sha=arguments["expected_code_commit_sha"],  # type: ignore[arg-type]
                expected_runner_source_sha256=arguments[
                    "expected_runner_source_sha256"
                ],  # type: ignore[arg-type]
                expected_execution_environment_contract_sha256=arguments[
                    "expected_execution_environment_contract_sha256"
                ],  # type: ignore[arg-type]
                expected_result_receipt_contract_sha256=arguments[
                    "expected_result_receipt_contract_sha256"
                ],  # type: ignore[arg-type]
                expected_dependency_artifact_sha256_rows=arguments[
                    "expected_dependency_artifact_sha256_rows"
                ],  # type: ignore[arg-type]
                revoked_receipt_sha256s=arguments["revoked_receipt_sha256s"],  # type: ignore[arg-type]
                revoked_review_attestation_sha256s=arguments[
                    "revoked_review_attestation_sha256s"
                ],  # type: ignore[arg-type]
                consumed_nonce_sha256s=arguments["consumed_nonce_sha256s"],  # type: ignore[arg-type]
            )
        if (
            arguments["expected_execution_environment_contract_sha256"]
            != FROZEN_REFERENCE_MINIMIZATION_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256
            or arguments["expected_result_receipt_contract_sha256"]
            != FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256
        ):
            raise ReferenceMinimizationValidationAuthorizationError(
                "minimization authorization environment or result contract is cross-wired"
            )
        return verify_signed_reference_minimization_validation_authorization_receipt(
            raw_authorization,
            review_attestation=raw_review,
            trusted_reviewer_keys=arguments["trusted_reviewer_keys"],  # type: ignore[arg-type]
            expected_implementation_author_identity_sha256=arguments[
                "expected_implementation_author_identity_sha256"
            ],  # type: ignore[arg-type]
            trusted_operator_keys=arguments["trusted_operator_keys"],  # type: ignore[arg-type]
            checked_at=checked_at,
            expected_code_commit_sha=arguments["expected_code_commit_sha"],  # type: ignore[arg-type]
            expected_runner_source_sha256=arguments["expected_runner_source_sha256"],  # type: ignore[arg-type]
            expected_dependency_artifact_sha256_rows=arguments[
                "expected_dependency_artifact_sha256_rows"
            ],  # type: ignore[arg-type]
            revoked_receipt_sha256s=arguments["revoked_receipt_sha256s"],  # type: ignore[arg-type]
            revoked_review_attestation_sha256s=arguments[
                "revoked_review_attestation_sha256s"
            ],  # type: ignore[arg-type]
            consumed_nonce_sha256s=arguments["consumed_nonce_sha256s"],  # type: ignore[arg-type]
        )
    except (
        ReferenceValidationAuthorizationError,
        ReferenceMinimizationValidationAuthorizationError,
    ) as exc:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "raw upstream authorization re-verification failed"
        ) from exc


def _verify_pre_execution_review_for_authorization(
    raw_pre_execution_review_carrier_bytes: bytes,
    *,
    raw_review_attestation_bytes: bytes,
    lane: str,
    run_context: dict[str, object],
    arguments: dict[str, object],
    checked_at: datetime,
) -> ProductionPreExecutionReviewCarrierVerification:
    if type(arguments) is not dict or set(arguments) != (
        _PRE_EXECUTION_REVERIFICATION_ARGUMENT_FIELDS
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "pre-execution review reverification arguments are not exact"
        )
    return verify_signed_production_pre_execution_review_carrier(
        raw_pre_execution_review_carrier_bytes,
        raw_review_attestation_bytes=raw_review_attestation_bytes,
        expected_carrier_sha256=arguments["expected_carrier_sha256"],  # type: ignore[arg-type]
        expected_lane=lane,
        expected_run_context=run_context,
        expected_prior_custody_event_sha256=arguments[
            "expected_prior_custody_event_sha256"
        ],  # type: ignore[arg-type]
        upstream_review_verification_arguments=arguments[
            "upstream_review_verification_arguments"
        ],  # type: ignore[arg-type]
        trusted_production_reviewer_keys=arguments["trusted_production_reviewer_keys"],  # type: ignore[arg-type]
        checked_at=checked_at,
        revoked_production_reviewer_key_ids=arguments[
            "revoked_production_reviewer_key_ids"
        ],  # type: ignore[arg-type]
        revoked_upstream_reviewer_key_ids=arguments[
            "revoked_upstream_reviewer_key_ids"
        ],  # type: ignore[arg-type]
        revoked_carrier_sha256s=arguments["revoked_carrier_sha256s"],  # type: ignore[arg-type]
        superseded_carrier_sha256s=arguments["superseded_carrier_sha256s"],  # type: ignore[arg-type]
        revoked_upstream_review_sha256s=arguments["revoked_upstream_review_sha256s"],  # type: ignore[arg-type]
        superseded_upstream_review_sha256s=arguments[
            "superseded_upstream_review_sha256s"
        ],  # type: ignore[arg-type]
    )


def _require_authorization_role_separation(
    *,
    run_context_projection: dict[str, Any],
    pre_execution_review: ProductionPreExecutionReviewCarrierVerification,
    upstream_authorization: ReferenceValidationAuthorizationVerification
    | ReferenceMinimizationValidationAuthorizationVerification,
    upstream_authorization_arguments: dict[str, object],
    pre_execution_review_arguments: dict[str, object],
    production_authorization_identity_sha256: str,
    production_authorization_key_id: str,
    production_authorization_public_key: bytes,
    production_authorization_private_key: bytes | None = None,
    production_authorization_trust: dict[str, ProductionAuthorizationCarrierTrustAnchor]
    | None = None,
) -> None:
    review_trust = upstream_authorization_arguments["trusted_reviewer_keys"]
    operator_trust = upstream_authorization_arguments["trusted_operator_keys"]
    stage3_upstream_arguments = pre_execution_review_arguments[
        "upstream_review_verification_arguments"
    ]
    production_review_trust = pre_execution_review_arguments[
        "trusted_production_reviewer_keys"
    ]
    if (
        type(review_trust) is not dict
        or type(operator_trust) is not dict
        or type(stage3_upstream_arguments) is not dict
        or type(production_review_trust) is not dict
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "authorization governance trust maps must be exact built-in dicts"
        )
    if (
        stage3_upstream_arguments.get("trusted_reviewer_keys") != review_trust
        or stage3_upstream_arguments.get(
            "expected_implementation_author_identity_sha256"
        )
        != upstream_authorization_arguments[
            "expected_implementation_author_identity_sha256"
        ]
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "authorization and pre-execution review trust domains differ"
        )
    context_identities = {
        run_context_projection["custodian_identity_sha256"],
        run_context_projection["enrolled_host_identity_sha256"],
        run_context_projection["evidence_authority_identity_sha256"],
        run_context_projection["current_status_authority_identity_sha256"],
    }
    identity_groups = (
        {upstream_authorization.implementation_author_identity_sha256},
        {
            anchor.reviewer_identity_sha256
            for anchor in review_trust.values()  # type: ignore[attr-defined]
        },
        {
            anchor.operator_identity_sha256
            for anchor in operator_trust.values()  # type: ignore[attr-defined]
        },
        {
            anchor.reviewer_identity_sha256
            for anchor in production_review_trust.values()  # type: ignore[attr-defined]
        },
        {production_authorization_identity_sha256},
        context_identities,
    )
    for index, group in enumerate(identity_groups):
        if any(group & other for other in identity_groups[index + 1 :]):
            raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                "authorization governance identities contain a global role alias"
            )
    context_key_ids = {
        run_context_projection["evidence_authority_key_id"],
        run_context_projection["current_status_authority_key_id"],
    }
    key_id_groups = (
        set(review_trust),
        set(operator_trust),
        set(production_review_trust),
        {production_authorization_key_id},
        context_key_ids,
    )
    for index, group in enumerate(key_id_groups):
        if any(group & other for other in key_id_groups[index + 1 :]):
            raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                "authorization governance key ids contain a global role alias"
            )
    material_groups = (
        {
            anchor.verification_key
            for anchor in review_trust.values()  # type: ignore[attr-defined]
        },
        {
            anchor.verification_key
            for anchor in operator_trust.values()  # type: ignore[attr-defined]
        },
        {
            anchor.verification_key
            for anchor in production_review_trust.values()  # type: ignore[attr-defined]
        },
        {production_authorization_public_key},
    )
    for index, group in enumerate(material_groups):
        if any(group & other for other in material_groups[index + 1 :]):
            raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                "authorization governance key material contains a global role alias"
            )
    if production_authorization_private_key is not None and any(
        production_authorization_private_key in group for group in material_groups[:-1]
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production authorization private key aliases upstream trust material"
        )
    if production_authorization_trust is not None:
        trust_key_ids = set(production_authorization_trust)
        trust_identities = {
            anchor.operator_identity_sha256
            for anchor in production_authorization_trust.values()
        }
        trust_material = {
            anchor.verification_key
            for anchor in production_authorization_trust.values()
        }
        non_authorization_key_ids = (
            key_id_groups[0] | key_id_groups[1] | key_id_groups[2] | context_key_ids
        )
        non_authorization_identities = (
            identity_groups[0]
            | identity_groups[1]
            | identity_groups[2]
            | identity_groups[3]
            | context_identities
        )
        non_authorization_material = (
            material_groups[0] | material_groups[1] | material_groups[2]
        )
        if (
            trust_key_ids & non_authorization_key_ids
            or trust_identities & non_authorization_identities
            or trust_material & non_authorization_material
        ):
            raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                "production authorization trust map contains a global alias"
            )
    if (
        upstream_authorization.review_attestation_sha256
        != pre_execution_review.upstream_review_attestation_sha256
        or upstream_authorization.implementation_author_identity_sha256
        != pre_execution_review.implementation_author_identity_sha256
        or upstream_authorization.independent_reviewer_identity_sha256
        != pre_execution_review.independent_reviewer_identity_sha256
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "authorization governance chain differs from the pre-execution review"
        )


def _authorization_projection(
    *,
    lane: str,
    run_context: dict[str, object],
    prior_custody_event_sha256: str,
    raw_pre_execution_review_carrier_bytes: bytes,
    pre_execution_review: ProductionPreExecutionReviewCarrierVerification,
    raw_review_attestation_bytes: bytes,
    raw_authorization_receipt_bytes: bytes,
    raw_authorization_document: dict[str, Any],
    upstream_authorization: ReferenceValidationAuthorizationVerification
    | ReferenceMinimizationValidationAuthorizationVerification,
    production_authorization_operator_identity_sha256: str,
    production_authorization_key_id: str,
    signed_at_utc: str,
    expires_at_utc: str,
) -> dict[str, Any]:
    selected_lane = _require_lane(lane)
    context = _run_context_projection(run_context)
    expected_schema = (
        REFERENCE_VALIDATION_AUTHORIZATION_RECEIPT_SCHEMA_ID
        if selected_lane == "energy_force"
        else REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_RECEIPT_SCHEMA_ID
    )
    expected_contract = (
        FROZEN_REFERENCE_VALIDATION_AUTHORIZATION_CONTRACT_SHA256
        if selected_lane == "energy_force"
        else FROZEN_REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_CONTRACT_SHA256
    )
    if raw_authorization_document.get("schema_id") != expected_schema:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "upstream authorization schema is cross-wired to the production lane"
        )
    if raw_authorization_document.get("contract_sha256") != expected_contract:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "upstream authorization contract is cross-wired to the production lane"
        )
    if raw_authorization_document.get("receipt_sha256") != (
        upstream_authorization.receipt_sha256
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "upstream authorization logical identity differs from its raw carrier"
        )
    if (
        upstream_authorization.authorization_nonce_sha256
        != context["authorization_nonce_sha256"]
        or upstream_authorization.code_commit_sha != context["code_commit_sha"]
        or upstream_authorization.runner_source_sha256 != context["source_sha256"]
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "upstream authorization differs from the exact permit run context"
        )
    production_identity = _require_sha256(
        production_authorization_operator_identity_sha256,
        name="production authorization operator identity",
    )
    production_key_id = _require_token(
        production_authorization_key_id,
        name="production authorization key id",
    )
    signed_at = _parse_utc(signed_at_utc, name="authorization carrier signed_at")
    expires_at = _parse_utc(expires_at_utc, name="authorization carrier expires_at")
    upstream_issued = _parse_utc(
        upstream_authorization.issued_at_utc,
        name="upstream authorization issued_at",
    )
    upstream_expires = _parse_utc(
        upstream_authorization.expires_at_utc,
        name="upstream authorization expires_at",
    )
    stage3_expires = _parse_utc(
        pre_execution_review.expires_at_utc,
        name="pre-execution review carrier expires_at",
    )
    if signed_at < upstream_issued or expires_at > min(
        upstream_expires, stage3_expires
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production authorization carrier is outside its ancestor lifetime"
        )
    if expires_at <= signed_at or (
        expires_at - signed_at > PRODUCTION_AUTHORIZATION_CARRIER_MAX_VALIDITY
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production authorization carrier validity interval is invalid"
        )
    dependency_rows = [
        {"artifact_id": artifact_id, "sha256": digest}
        for artifact_id, digest in upstream_authorization.dependency_artifact_sha256_rows
    ]
    return {
        "schema_id": PRODUCTION_AUTHORIZATION_CARRIER_SCHEMA_ID,
        "contract_sha256": (
            FROZEN_VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256
        ),
        "evidence_class": PRODUCTION_EVIDENCE_CLASS,
        "artifact_stage": "authorization",
        "lane": selected_lane,
        **context,
        "prior_custody_event_sha256": _require_sha256(
            prior_custody_event_sha256, name="prior custody event"
        ),
        "pre_execution_review_carrier_sha256": pre_execution_review.carrier_sha256,
        "pre_execution_review_raw_sha256": _raw_sha256(
            raw_pre_execution_review_carrier_bytes
        ),
        "pre_execution_review_raw_byte_count": len(
            raw_pre_execution_review_carrier_bytes
        ),
        "upstream_review_attestation_sha256": (
            pre_execution_review.upstream_review_attestation_sha256
        ),
        "upstream_review_raw_sha256": _raw_sha256(raw_review_attestation_bytes),
        "upstream_authorization_schema_id": expected_schema,
        "upstream_authorization_contract_sha256": expected_contract,
        "upstream_authorization_receipt_sha256": (
            upstream_authorization.receipt_sha256
        ),
        "upstream_authorization_raw_sha256": _raw_sha256(
            raw_authorization_receipt_bytes
        ),
        "upstream_authorization_raw_byte_count": len(raw_authorization_receipt_bytes),
        "implementation_author_identity_sha256": (
            upstream_authorization.implementation_author_identity_sha256
        ),
        "independent_reviewer_identity_sha256": (
            upstream_authorization.independent_reviewer_identity_sha256
        ),
        "upstream_authorization_operator_identity_sha256": (
            upstream_authorization.authorization_operator_identity_sha256
        ),
        "upstream_authorization_key_id": (upstream_authorization.authorization_key_id),
        "upstream_authorization_issued_at_utc": (upstream_authorization.issued_at_utc),
        "upstream_authorization_expires_at_utc": (
            upstream_authorization.expires_at_utc
        ),
        "execution_environment_contract_sha256": (
            upstream_authorization.execution_environment_contract_sha256
        ),
        "result_receipt_contract_sha256": (
            upstream_authorization.result_receipt_contract_sha256
        ),
        "dependency_artifact_sha256_rows": dependency_rows,
        "production_authorization_operator_identity_sha256": production_identity,
        "production_authorization_key_id": production_key_id,
        "signed_at_utc": signed_at_utc,
        "expires_at_utc": expires_at_utc,
        "pre_execution_review_reverified": True,
        "upstream_review_and_authorization_reverified": True,
        "eligible_for_atomic_execution_reservation": False,
        "full_asymmetric_chain_established": False,
        **_CLAIM_POLICY,
        "superseded": False,
        "revoked": False,
    }


def build_signed_production_authorization_carrier(
    *,
    raw_authorization_receipt_bytes: bytes,
    raw_review_attestation_bytes: bytes,
    raw_pre_execution_review_carrier_bytes: bytes,
    lane: str,
    run_context: dict[str, object],
    upstream_authorization_verification_arguments: dict[str, object],
    pre_execution_review_reverification_arguments: dict[str, object],
    prior_custody_event_sha256: str,
    production_authorization_operator_identity_sha256: str,
    production_authorization_key_id: str,
    signing_key: bytes,
    signed_at: datetime,
    expires_at: datetime,
) -> dict[str, Any]:
    """Wrap exact raw stage3, review, and authorization evidence in Ed25519."""

    selected_lane = _require_lane(lane)
    raw_authorization = _require_raw_bytes(
        raw_authorization_receipt_bytes,
        name="raw upstream authorization receipt",
        maximum=PRODUCTION_REVIEW_AUTHORIZATION_MAX_RAW_UPSTREAM_BYTES,
    )
    raw_authorization_document = _load_raw_document(
        raw_authorization,
        name="raw upstream authorization receipt",
        maximum=PRODUCTION_REVIEW_AUTHORIZATION_MAX_RAW_UPSTREAM_BYTES,
    )
    raw_review = _require_raw_bytes(
        raw_review_attestation_bytes,
        name="raw upstream review attestation",
        maximum=PRODUCTION_REVIEW_AUTHORIZATION_MAX_RAW_UPSTREAM_BYTES,
    )
    raw_stage3 = _require_raw_bytes(
        raw_pre_execution_review_carrier_bytes,
        name="raw pre-execution review carrier",
        maximum=PRODUCTION_REVIEW_AUTHORIZATION_MAX_SIGNED_TRANSPORT_BYTES,
    )
    pre_execution_review = _verify_pre_execution_review_for_authorization(
        raw_stage3,
        raw_review_attestation_bytes=raw_review,
        lane=selected_lane,
        run_context=run_context,
        arguments=pre_execution_review_reverification_arguments,
        checked_at=signed_at,
    )
    upstream_authorization = _verify_upstream_authorization(
        raw_authorization,
        raw_review_attestation_bytes=raw_review,
        lane=selected_lane,
        upstream_authorization_verification_arguments=(
            upstream_authorization_verification_arguments
        ),
        checked_at=signed_at,
    )
    private_key = signing_key
    if type(private_key) is not bytes or len(private_key) != 32:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production authorization signing key must be 32 private-key bytes"
        )
    try:
        public_key = ed25519_public_key_bytes(private_key)
    except ReferenceMinimizationValidationEd25519Error as exc:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production authorization Ed25519 key derivation failed"
        ) from exc
    context_projection = _run_context_projection(run_context)
    _trusted_operator_keys(
        upstream_authorization_verification_arguments,
        lane=selected_lane,
    )
    production_identity = _require_sha256(
        production_authorization_operator_identity_sha256,
        name="production authorization operator identity",
    )
    production_key_id = _require_token(
        production_authorization_key_id,
        name="production authorization key id",
    )
    _require_authorization_role_separation(
        run_context_projection=context_projection,
        pre_execution_review=pre_execution_review,
        upstream_authorization=upstream_authorization,
        upstream_authorization_arguments=(
            upstream_authorization_verification_arguments
        ),
        pre_execution_review_arguments=(pre_execution_review_reverification_arguments),
        production_authorization_identity_sha256=production_identity,
        production_authorization_key_id=production_key_id,
        production_authorization_public_key=public_key,
        production_authorization_private_key=private_key,
    )
    projection = _authorization_projection(
        lane=selected_lane,
        run_context=run_context,
        prior_custody_event_sha256=prior_custody_event_sha256,
        raw_pre_execution_review_carrier_bytes=raw_stage3,
        pre_execution_review=pre_execution_review,
        raw_review_attestation_bytes=raw_review,
        raw_authorization_receipt_bytes=raw_authorization,
        raw_authorization_document=raw_authorization_document,
        upstream_authorization=upstream_authorization,
        production_authorization_operator_identity_sha256=production_identity,
        production_authorization_key_id=production_key_id,
        signed_at_utc=_format_utc(signed_at, name="authorization carrier signed_at"),
        expires_at_utc=_format_utc(expires_at, name="authorization carrier expires_at"),
    )
    payload = dict(projection)
    payload["carrier_sha256"] = _sha256(projection)
    try:
        signature_value = sign_ed25519(_canonical_bytes(payload), private_key)
    except ReferenceMinimizationValidationEd25519Error as exc:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production authorization carrier Ed25519 signing failed"
        ) from exc
    payload["signature"] = {
        "algorithm": (
            PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_SIGNATURE_ALGORITHM
        ),
        "key_id": production_key_id,
        "value": signature_value,
    }
    if len(_canonical_bytes(payload)) > (
        PRODUCTION_REVIEW_AUTHORIZATION_MAX_SIGNED_TRANSPORT_BYTES
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production authorization carrier exceeds its signed transport bound"
        )
    if not verify_ed25519(
        _canonical_bytes(
            {key: value for key, value in payload.items() if key != "signature"}
        ),
        signature_value,
        public_key,
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production authorization carrier self-verification failed"
        )
    return payload


def verify_signed_production_authorization_carrier(
    source: bytes,
    *,
    raw_authorization_receipt_bytes: bytes,
    raw_review_attestation_bytes: bytes,
    raw_pre_execution_review_carrier_bytes: bytes,
    expected_carrier_sha256: str,
    expected_lane: str,
    expected_run_context: dict[str, object],
    expected_prior_custody_event_sha256: str,
    upstream_authorization_verification_arguments: dict[str, object],
    pre_execution_review_reverification_arguments: dict[str, object],
    trusted_production_authorization_keys: dict[
        str, ProductionAuthorizationCarrierTrustAnchor
    ],
    checked_at: datetime,
    revoked_production_authorization_key_ids: Sequence[str] = (),
    revoked_upstream_authorization_key_ids: Sequence[str] = (),
    revoked_carrier_sha256s: Sequence[str] = (),
    superseded_carrier_sha256s: Sequence[str] = (),
    revoked_upstream_authorization_sha256s: Sequence[str] = (),
    superseded_upstream_authorization_sha256s: Sequence[str] = (),
) -> ProductionAuthorizationCarrierVerification:
    """Reverify the full stage3 + upstream review/authorization raw prefix."""

    raw_carrier = _require_raw_bytes(
        source,
        name="raw production authorization carrier",
        maximum=PRODUCTION_REVIEW_AUTHORIZATION_MAX_SIGNED_TRANSPORT_BYTES,
    )
    payload = _load_raw_document(
        raw_carrier,
        name="raw production authorization carrier",
        maximum=PRODUCTION_REVIEW_AUTHORIZATION_MAX_SIGNED_TRANSPORT_BYTES,
    )
    if raw_carrier != _canonical_bytes(payload):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production authorization carrier transport must be exact canonical JSON"
        )
    raw_carrier_sha256 = _raw_sha256(raw_carrier)
    if (
        type(trusted_production_authorization_keys) is not dict
        or not trusted_production_authorization_keys
        or len(trusted_production_authorization_keys)
        > PRODUCTION_REVIEW_AUTHORIZATION_MAX_TRUST_ANCHORS
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production authorization trust map is empty or exceeds its fixed bound"
        )
    identities: set[str] = set()
    materials: set[bytes] = set()
    for key_id_value, anchor_value in trusted_production_authorization_keys.items():
        _require_token(key_id_value, name="trusted production authorization key id")
        if type(anchor_value) is not ProductionAuthorizationCarrierTrustAnchor:
            raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                "production authorization trust map contains an invalid anchor"
            )
        if (
            anchor_value.operator_identity_sha256 in identities
            or anchor_value.verification_key in materials
        ):
            raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                "production authorization trust map contains an alias"
            )
        identities.add(anchor_value.operator_identity_sha256)
        materials.add(anchor_value.verification_key)
    signature = payload.pop("signature", None)
    if type(signature) is not dict or set(signature) != {
        "algorithm",
        "key_id",
        "value",
    }:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production authorization carrier signature fields are invalid"
        )
    if signature["algorithm"] != (
        PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_SIGNATURE_ALGORITHM
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production authorization signature algorithm is unsupported"
        )
    key_id = _require_token(signature["key_id"], name="production authorization key id")
    if key_id in _external_key_id_set(
        revoked_production_authorization_key_ids,
        name="revoked production authorization key id",
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production authorization key is revoked"
        )
    anchor = trusted_production_authorization_keys.get(key_id)
    if type(anchor) is not ProductionAuthorizationCarrierTrustAnchor:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production authorization key is not trusted"
        )
    try:
        signature_verified = verify_ed25519(
            _canonical_bytes(payload), signature["value"], anchor.verification_key
        )
    except ReferenceMinimizationValidationEd25519Error as exc:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production authorization Ed25519 verifier is unavailable"
        ) from exc
    if not signature_verified:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production authorization carrier signature verification failed"
        )
    carrier_sha256 = payload.pop("carrier_sha256", None)
    if carrier_sha256 != _sha256(payload):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production authorization carrier SHA-256 verification failed"
        )
    carrier_sha256 = _require_sha256(
        carrier_sha256, name="production authorization carrier"
    )
    if carrier_sha256 != _require_sha256(
        expected_carrier_sha256,
        name="expected production authorization carrier",
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production authorization carrier is cross-wired to its identity"
        )
    revoked_carriers = _external_sha256_set(
        revoked_carrier_sha256s,
        name="revoked production authorization carrier",
    )
    if {carrier_sha256, raw_carrier_sha256} & revoked_carriers:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production authorization carrier is revoked"
        )
    superseded_carriers = _external_sha256_set(
        superseded_carrier_sha256s,
        name="superseded production authorization carrier",
    )
    if {carrier_sha256, raw_carrier_sha256} & superseded_carriers:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production authorization carrier is superseded"
        )
    if payload.get("schema_id") != PRODUCTION_AUTHORIZATION_CARRIER_SCHEMA_ID:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production authorization carrier schema is unsupported"
        )
    if payload.get("contract_sha256") != (
        FROZEN_VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production authorization carrier contract is cross-wired"
        )
    if (
        payload.get("evidence_class") != PRODUCTION_EVIDENCE_CLASS
        or payload.get("artifact_stage") != "authorization"
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production authorization evidence class or stage is cross-wired"
        )
    selected_lane = _require_lane(expected_lane)
    signed_at = _parse_utc(
        payload.get("signed_at_utc"), name="authorization carrier signed_at"
    )
    expires_at = _parse_utc(
        payload.get("expires_at_utc"), name="authorization carrier expires_at"
    )
    checked = _parse_utc(
        _format_utc(checked_at, name="authorization carrier checked_at"),
        name="authorization carrier checked_at",
    )
    if checked < signed_at or checked >= expires_at:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production authorization carrier is not currently valid"
        )
    raw_authorization = _require_raw_bytes(
        raw_authorization_receipt_bytes,
        name="raw upstream authorization receipt",
        maximum=PRODUCTION_REVIEW_AUTHORIZATION_MAX_RAW_UPSTREAM_BYTES,
    )
    raw_authorization_document = _load_raw_document(
        raw_authorization,
        name="raw upstream authorization receipt",
        maximum=PRODUCTION_REVIEW_AUTHORIZATION_MAX_RAW_UPSTREAM_BYTES,
    )
    raw_review = _require_raw_bytes(
        raw_review_attestation_bytes,
        name="raw upstream review attestation",
        maximum=PRODUCTION_REVIEW_AUTHORIZATION_MAX_RAW_UPSTREAM_BYTES,
    )
    raw_stage3 = _require_raw_bytes(
        raw_pre_execution_review_carrier_bytes,
        name="raw pre-execution review carrier",
        maximum=PRODUCTION_REVIEW_AUTHORIZATION_MAX_SIGNED_TRANSPORT_BYTES,
    )
    pre_execution_review = _verify_pre_execution_review_for_authorization(
        raw_stage3,
        raw_review_attestation_bytes=raw_review,
        lane=selected_lane,
        run_context=expected_run_context,
        arguments=pre_execution_review_reverification_arguments,
        checked_at=signed_at,
    )
    upstream_authorization = _verify_upstream_authorization(
        raw_authorization,
        raw_review_attestation_bytes=raw_review,
        lane=selected_lane,
        upstream_authorization_verification_arguments=(
            upstream_authorization_verification_arguments
        ),
        checked_at=signed_at,
    )
    if upstream_authorization.authorization_key_id in _external_key_id_set(
        revoked_upstream_authorization_key_ids,
        name="revoked upstream authorization key id",
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "upstream authorization key is revoked"
        )
    upstream_raw_sha256 = _raw_sha256(raw_authorization)
    revoked_upstream = _external_sha256_set(
        revoked_upstream_authorization_sha256s,
        name="revoked upstream authorization",
    )
    if {
        upstream_authorization.receipt_sha256,
        upstream_raw_sha256,
    } & revoked_upstream:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "upstream authorization is revoked"
        )
    superseded_upstream = _external_sha256_set(
        superseded_upstream_authorization_sha256s,
        name="superseded upstream authorization",
    )
    if {
        upstream_authorization.receipt_sha256,
        upstream_raw_sha256,
    } & superseded_upstream:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "upstream authorization is superseded"
        )
    context_projection = _run_context_projection(expected_run_context)
    _require_authorization_role_separation(
        run_context_projection=context_projection,
        pre_execution_review=pre_execution_review,
        upstream_authorization=upstream_authorization,
        upstream_authorization_arguments=(
            upstream_authorization_verification_arguments
        ),
        pre_execution_review_arguments=(pre_execution_review_reverification_arguments),
        production_authorization_identity_sha256=anchor.operator_identity_sha256,
        production_authorization_key_id=key_id,
        production_authorization_public_key=anchor.verification_key,
        production_authorization_trust=trusted_production_authorization_keys,
    )
    expected_projection = _authorization_projection(
        lane=selected_lane,
        run_context=expected_run_context,
        prior_custody_event_sha256=expected_prior_custody_event_sha256,
        raw_pre_execution_review_carrier_bytes=raw_stage3,
        pre_execution_review=pre_execution_review,
        raw_review_attestation_bytes=raw_review,
        raw_authorization_receipt_bytes=raw_authorization,
        raw_authorization_document=raw_authorization_document,
        upstream_authorization=upstream_authorization,
        production_authorization_operator_identity_sha256=(
            anchor.operator_identity_sha256
        ),
        production_authorization_key_id=key_id,
        signed_at_utc=payload["signed_at_utc"],
        expires_at_utc=payload["expires_at_utc"],
    )
    if _canonical_bytes(payload) != _canonical_bytes(expected_projection):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "production authorization carrier fields do not match the exact run"
        )
    _require_claims_closed(payload)
    return _new_authorization_verification(
        carrier_sha256=carrier_sha256,
        raw_carrier_sha256=raw_carrier_sha256,
        raw_carrier_byte_count=len(raw_carrier),
        lane=selected_lane,
        permit_sha256=payload["permit_sha256"],
        study_id_sha256=payload["study_id_sha256"],
        run_id_sha256=payload["run_id_sha256"],
        authorization_nonce_sha256=payload["authorization_nonce_sha256"],
        prior_custody_event_sha256=payload["prior_custody_event_sha256"],
        current_status_snapshot_sha256=payload["current_status_snapshot_sha256"],
        process_launch_identity_sha256=payload["process_launch_identity_sha256"],
        pre_execution_review_carrier_sha256=(pre_execution_review.carrier_sha256),
        pre_execution_review_raw_sha256=_raw_sha256(raw_stage3),
        upstream_review_attestation_sha256=(
            pre_execution_review.upstream_review_attestation_sha256
        ),
        upstream_review_raw_sha256=_raw_sha256(raw_review),
        upstream_authorization_receipt_sha256=(upstream_authorization.receipt_sha256),
        upstream_authorization_raw_sha256=upstream_raw_sha256,
        implementation_author_identity_sha256=(
            upstream_authorization.implementation_author_identity_sha256
        ),
        independent_reviewer_identity_sha256=(
            upstream_authorization.independent_reviewer_identity_sha256
        ),
        upstream_authorization_operator_identity_sha256=(
            upstream_authorization.authorization_operator_identity_sha256
        ),
        upstream_authorization_key_id=(upstream_authorization.authorization_key_id),
        production_authorization_operator_identity_sha256=(
            anchor.operator_identity_sha256
        ),
        production_authorization_key_id=key_id,
        signed_at_utc=payload["signed_at_utc"],
        expires_at_utc=payload["expires_at_utc"],
        checked_at_utc=_format_utc(checked, name="authorization carrier checked_at"),
    )


@dataclass(frozen=True, slots=True)
class _BaseSequenceTwoPrefixVerification:
    permit: ProductionEvidencePermitVerification
    current_status: ProductionEvidenceStatusSnapshotVerification
    status_lineage: tuple[ProductionEvidenceStatusSnapshotVerification, ...]
    sequence_one: ProductionCustodyEventVerification
    sequence_two: ProductionCustodyEventVerification
    raw_permit_sha256: str
    raw_status_sha256s: tuple[str, ...]
    raw_sequence_one_sha256: str
    raw_sequence_two_sha256: str


@dataclass(frozen=True, slots=True, init=False)
class ProductionReviewAuthorizationCustodyExtensionEventVerification:
    custody_event_sha256: str
    raw_event_sha256: str
    raw_event_byte_count: int
    artifact_stage: str
    custody_sequence: int
    prior_custody_event_sha256: str
    carrier_sha256: str
    raw_carrier_sha256: str
    raw_carrier_byte_count: int
    permit_sha256: str
    study_id_sha256: str
    run_id_sha256: str
    authorization_nonce_sha256: str
    lane: str
    custodian_identity_sha256: str
    enrolled_host_identity_sha256: str
    process_launch_identity_sha256: str
    from_role: str
    from_role_identity_sha256: str
    from_key_id: str
    from_public_key_sha256: str
    to_role: str
    to_role_identity_sha256: str
    to_key_id: str
    to_public_key_sha256: str
    handed_off_at_utc: str
    received_at_utc: str
    handoff_status_snapshot_sha256: str
    current_status_snapshot_sha256: str
    custody_event_lineage_sha256s: tuple[str, ...]
    raw_custody_event_lineage_sha256s: tuple[str, ...]
    carrier_lineage_sha256s: tuple[str, ...]
    raw_carrier_lineage_sha256s: tuple[str, ...]
    upstream_review_attestation_sha256: str
    upstream_review_raw_sha256: str
    upstream_authorization_receipt_sha256: str | None
    upstream_authorization_raw_sha256: str | None
    checked_at_utc: str
    dual_custody_signatures_verified: bool = True
    full_raw_prefix_reverified: bool = True
    custody_successor_uniqueness_enforced: bool = False
    eligible_for_atomic_execution_reservation: bool = False
    production_validation_execution_authorized: bool = False
    production_validation_results_collected: bool = False
    scientifically_validated: bool = False
    parameter_fitting_authorized: bool = False
    product_qualified: bool = False
    claim_safe: bool = False
    _verification_seal: object = field(init=False, repr=False, compare=False)


def _new_extension_event_verification(
    **values: object,
) -> ProductionReviewAuthorizationCustodyExtensionEventVerification:
    instance = object.__new__(
        ProductionReviewAuthorizationCustodyExtensionEventVerification
    )
    for name, value in values.items():
        object.__setattr__(instance, name, value)
    object.__setattr__(instance, "dual_custody_signatures_verified", True)
    object.__setattr__(instance, "full_raw_prefix_reverified", True)
    object.__setattr__(instance, "custody_successor_uniqueness_enforced", False)
    object.__setattr__(instance, "eligible_for_atomic_execution_reservation", False)
    object.__setattr__(instance, "production_validation_execution_authorized", False)
    object.__setattr__(instance, "production_validation_results_collected", False)
    object.__setattr__(instance, "scientifically_validated", False)
    object.__setattr__(instance, "parameter_fitting_authorized", False)
    object.__setattr__(instance, "product_qualified", False)
    object.__setattr__(instance, "claim_safe", False)
    object.__setattr__(instance, "_verification_seal", _VERIFICATION_SEAL)
    return instance


def _canonical_raw_document(
    value: object,
    *,
    name: str,
    maximum: int = PRODUCTION_REVIEW_AUTHORIZATION_MAX_SIGNED_TRANSPORT_BYTES,
) -> tuple[bytes, dict[str, Any]]:
    raw = _require_raw_bytes(value, name=name, maximum=maximum)
    document = _load_raw_document(raw, name=name, maximum=maximum)
    if raw != _canonical_bytes(document):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            f"{name} must be exact canonical JSON bytes"
        )
    return raw, document


def _require_exact_json_scalar_types(
    value: dict[str, Any],
    *,
    name: str,
    integer_field_names: set[str],
) -> None:
    """Reject Python numeric-equality aliases before frozen ancestor verifiers."""

    pending: list[object] = [value]
    while pending:
        current = pending.pop()
        if type(current) is dict:
            for field_name, item in current.items():
                if field_name in integer_field_names:
                    if type(item) is not int:
                        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                            f"{name} integer field has a non-exact JSON type"
                        )
                elif type(item) is int:
                    raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                        f"{name} contains an integer in a non-integer field"
                    )
                if type(item) is float:
                    raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                        f"{name} contains an unsupported JSON number"
                    )
                if type(item) in (dict, list):
                    pending.append(item)
        elif type(current) is list:
            for item in current:
                if type(item) in (int, float):
                    raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                        f"{name} contains an unsupported JSON number in a sequence"
                    )
                if type(item) in (dict, list):
                    pending.append(item)


def _exact_authority_trust_map(
    value: object,
) -> dict[str, EvidenceAuthorityTrustAnchor]:
    if (
        type(value) is not dict
        or not value
        or len(value) > PRODUCTION_REVIEW_AUTHORIZATION_MAX_TRUST_ANCHORS
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "base evidence authority trust map is invalid or exceeds its bound"
        )
    identities: set[str] = set()
    materials: set[bytes] = set()
    normalized: dict[str, EvidenceAuthorityTrustAnchor] = {}
    for key_id, anchor in value.items():
        normalized_key_id = _require_token(
            key_id, name="base evidence authority key id"
        )
        if type(anchor) is not EvidenceAuthorityTrustAnchor:
            raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                "base evidence authority trust map contains an invalid anchor"
            )
        if (
            anchor.authority_identity_sha256 in identities
            or anchor.verification_key in materials
        ):
            raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                "base evidence authority trust map contains an alias"
            )
        identities.add(anchor.authority_identity_sha256)
        materials.add(anchor.verification_key)
        normalized[normalized_key_id] = anchor
    return normalized


def _exact_custody_trust_map(value: object) -> dict[str, CustodyRoleTrustAnchor]:
    if (
        type(value) is not dict
        or not value
        or len(value) > PRODUCTION_REVIEW_AUTHORIZATION_MAX_TRUST_ANCHORS
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "base custody trust map is invalid or exceeds its bound"
        )
    identities: set[str] = set()
    materials: set[bytes] = set()
    normalized: dict[str, CustodyRoleTrustAnchor] = {}
    for key_id, anchor in value.items():
        normalized_key_id = _require_token(key_id, name="base custody key id")
        if type(anchor) is not CustodyRoleTrustAnchor:
            raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                "base custody trust map contains an invalid anchor"
            )
        if (
            anchor.role_identity_sha256 in identities
            or anchor.verification_key in materials
        ):
            raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                "base custody trust map contains an alias"
            )
        identities.add(anchor.role_identity_sha256)
        materials.add(anchor.verification_key)
        normalized[normalized_key_id] = anchor
    return normalized


def _exact_production_review_trust_map(
    value: object,
) -> dict[str, ProductionReviewCarrierTrustAnchor]:
    if (
        type(value) is not dict
        or not value
        or len(value) > PRODUCTION_REVIEW_AUTHORIZATION_MAX_TRUST_ANCHORS
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension production reviewer trust map is invalid"
        )
    identities: set[str] = set()
    materials: set[bytes] = set()
    normalized: dict[str, ProductionReviewCarrierTrustAnchor] = {}
    for key_id, anchor in value.items():
        normalized_key_id = _require_token(
            key_id,
            name="extension production reviewer key id",
        )
        if type(anchor) is not ProductionReviewCarrierTrustAnchor:
            raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                "extension production reviewer trust map contains an invalid anchor"
            )
        if (
            anchor.reviewer_identity_sha256 in identities
            or anchor.verification_key in materials
        ):
            raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                "extension production reviewer trust map contains an alias"
            )
        identities.add(anchor.reviewer_identity_sha256)
        materials.add(anchor.verification_key)
        normalized[normalized_key_id] = anchor
    return normalized


def _exact_production_authorization_trust_map(
    value: object,
) -> dict[str, ProductionAuthorizationCarrierTrustAnchor]:
    if (
        type(value) is not dict
        or not value
        or len(value) > PRODUCTION_REVIEW_AUTHORIZATION_MAX_TRUST_ANCHORS
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension production authorization trust map is invalid"
        )
    identities: set[str] = set()
    materials: set[bytes] = set()
    normalized: dict[str, ProductionAuthorizationCarrierTrustAnchor] = {}
    for key_id, anchor in value.items():
        normalized_key_id = _require_token(
            key_id,
            name="extension production authorization key id",
        )
        if type(anchor) is not ProductionAuthorizationCarrierTrustAnchor:
            raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                "extension production authorization trust map contains an invalid anchor"
            )
        if (
            anchor.operator_identity_sha256 in identities
            or anchor.verification_key in materials
        ):
            raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                "extension production authorization trust map contains an alias"
            )
        identities.add(anchor.operator_identity_sha256)
        materials.add(anchor.verification_key)
        normalized[normalized_key_id] = anchor
    return normalized


def _current_status_denials(
    status: ProductionEvidenceStatusSnapshotVerification,
) -> tuple[set[str], set[str], set[str]]:
    revoked_keys = {key_id for _role, key_id in status.revoked_key_rows}
    revoked_artifacts = {
        artifact_sha256
        for _artifact_kind, artifact_sha256 in status.revoked_artifact_rows
    }
    superseded_artifacts = {
        superseded_sha256
        for _artifact_kind, superseded_sha256, _replacement_sha256 in (
            status.supersession_rows
        )
    }
    return revoked_keys, revoked_artifacts, superseded_artifacts


def _require_current_status_allows_identities(
    status: ProductionEvidenceStatusSnapshotVerification,
    *,
    identities: Sequence[str],
    name: str,
) -> None:
    _revoked_keys, revoked, superseded = _current_status_denials(status)
    normalized = {
        _require_sha256(identity, name=f"{name} identity") for identity in identities
    }
    if normalized & (revoked | superseded):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            f"{name} is currently revoked or superseded"
        )


def _reverify_base_sequence_two_prefix(
    *,
    raw_permit_bytes: bytes,
    raw_status_lineage_bytes: Sequence[bytes],
    raw_sequence_one_custody_event_bytes: bytes,
    raw_sequence_two_custody_event_bytes: bytes,
    run_context: dict[str, object],
    base_reverification_arguments: dict[str, object],
    checked_at: datetime,
) -> _BaseSequenceTwoPrefixVerification:
    context = _run_context_projection(run_context)
    checked = _parse_utc(
        _format_utc(checked_at, name="base prefix checked_at"),
        name="base prefix checked_at",
    )
    if (
        type(base_reverification_arguments) is not dict
        or set(base_reverification_arguments)
        != _BASE_SEQUENCE_TWO_REVERIFICATION_ARGUMENT_FIELDS
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "base sequence-two reverification arguments are not exact"
        )
    arguments = base_reverification_arguments
    authority_trust = _exact_authority_trust_map(arguments["trusted_authority_keys"])
    custody_trust = _exact_custody_trust_map(arguments["trusted_custody_keys"])
    permit_arguments = arguments["permit_verification_arguments"]
    if type(permit_arguments) is not dict or set(permit_arguments) != (
        _BASE_PERMIT_REVERIFICATION_ARGUMENT_FIELDS
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "base permit reverification arguments are not exact"
        )
    raw_permit, permit_document = _canonical_raw_document(
        raw_permit_bytes,
        name="raw base production permit",
    )
    raw_sequence_one, sequence_one_document = _canonical_raw_document(
        raw_sequence_one_custody_event_bytes,
        name="raw base custody sequence one",
    )
    raw_sequence_two, sequence_two_document = _canonical_raw_document(
        raw_sequence_two_custody_event_bytes,
        name="raw base custody sequence two",
    )
    _require_exact_json_scalar_types(
        permit_document,
        name="raw base production permit",
        integer_field_names=_BASE_PERMIT_INTEGER_FIELDS,
    )
    _require_exact_json_scalar_types(
        sequence_one_document,
        name="raw base custody sequence one",
        integer_field_names=_BASE_CUSTODY_EVENT_INTEGER_FIELDS,
    )
    _require_exact_json_scalar_types(
        sequence_two_document,
        name="raw base custody sequence two",
        integer_field_names=_BASE_CUSTODY_EVENT_INTEGER_FIELDS,
    )
    if (
        type(raw_status_lineage_bytes) not in (list, tuple)
        or not raw_status_lineage_bytes
        or len(raw_status_lineage_bytes)
        > PRODUCTION_REVIEW_AUTHORIZATION_MAX_STATUS_LINEAGE_ITEMS
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "raw status lineage is empty or exceeds its item bound"
        )
    raw_status_rows: list[bytes] = []
    status_documents: list[dict[str, Any]] = []
    total_status_bytes = 0
    for index, source in enumerate(raw_status_lineage_bytes):
        raw_status, status_document = _canonical_raw_document(
            source,
            name=f"raw status lineage item {index}",
        )
        _require_exact_json_scalar_types(
            status_document,
            name=f"raw status lineage item {index}",
            integer_field_names=_BASE_STATUS_INTEGER_FIELDS,
        )
        total_status_bytes += len(raw_status)
        if total_status_bytes > (
            PRODUCTION_REVIEW_AUTHORIZATION_MAX_STATUS_LINEAGE_TOTAL_BYTES
        ):
            raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                "raw status lineage exceeds its aggregate byte bound"
            )
        raw_status_rows.append(raw_status)
        status_documents.append(status_document)
    raw_statuses = tuple(raw_status_rows)

    if permit_document.get("schema_id") != PRODUCTION_EVIDENCE_PERMIT_SCHEMA_ID:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "raw base permit schema is cross-wired"
        )
    if (
        sequence_one_document.get("schema_id") != PRODUCTION_CUSTODY_EVENT_SCHEMA_ID
        or sequence_two_document.get("schema_id") != PRODUCTION_CUSTODY_EVENT_SCHEMA_ID
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "raw base custody event schema is cross-wired"
        )
    expected_permit_context = {
        "expected_permit_id_sha256": context["permit_id_sha256"],
        "expected_study_id_sha256": context["study_id_sha256"],
        "expected_authorization_nonce_sha256": context["authorization_nonce_sha256"],
        "expected_code_commit_sha": context["code_commit_sha"],
        "expected_source_sha256": context["source_sha256"],
        "expected_source_manifest_sha256": context["source_manifest_sha256"],
        "expected_dependency_manifest_sha256": context["dependency_manifest_sha256"],
        "expected_runtime_manifest_sha256": context["runtime_manifest_sha256"],
        "expected_seed": context["seed"],
        "expected_artifact_output_root_identity_sha256": context[
            "artifact_output_root_identity_sha256"
        ],
    }
    if (
        any(
            permit_arguments[name] != expected
            for name, expected in expected_permit_context.items()
        )
        or _contract_rows(permit_arguments["expected_contract_bundle_sha256_rows"])
        != context["contract_bundle_sha256_rows"]
        or _argv(permit_arguments["expected_command_argv"]) != context["command_argv"]
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "base permit arguments differ from the exact carrier run context"
        )
    revoked_key_ids = _external_key_id_set(
        arguments["revoked_authority_key_ids"],
        name="base current revoked key id",
    )
    nested_revoked_key_ids = _external_key_id_set(
        permit_arguments["revoked_authority_key_ids"],
        name="base permit revoked key id",
    )
    if revoked_key_ids != nested_revoked_key_ids:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "base permit and status revocation inputs differ"
        )
    for name in (
        "revoked_permit_sha256s",
        "superseded_permit_sha256s",
        "consumed_permit_sha256s",
    ):
        _external_sha256_set(permit_arguments[name], name=f"base {name}")
    if (
        permit_document.get("permit_sha256") != context["permit_sha256"]
        or permit_document.get("run_id_sha256") != context["run_id_sha256"]
        or permit_document.get("lane") not in ("energy_force", "minimization")
        or permit_document.get("lane") != sequence_one_document.get("lane")
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "raw base permit is cross-wired to the production run"
        )
    sequence_one_handed_off = _parse_utc(
        sequence_one_document.get("handed_off_at_utc"),
        name="base sequence-one handed_off_at",
    )
    try:
        permit_call_arguments = dict(permit_arguments)
        permit_call_arguments.update(
            {
                "expected_permit_sha256": context["permit_sha256"],
                "trusted_authority_keys": authority_trust,
                "checked_at": sequence_one_handed_off,
                "expected_lane": _require_lane(permit_document.get("lane")),
                "expected_run_id_sha256": context["run_id_sha256"],
                "expected_custodian_identity_sha256": context[
                    "custodian_identity_sha256"
                ],
                "expected_enrolled_host_identity_sha256": context[
                    "enrolled_host_identity_sha256"
                ],
            }
        )
        permit = verify_signed_production_evidence_permit(
            raw_permit,
            **permit_call_arguments,  # type: ignore[arg-type]
        )
    except ValidationProductionEvidenceCustodyError as exc:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "raw base production permit re-verification failed"
        ) from exc
    if (
        permit.authority_identity_sha256
        != context["evidence_authority_identity_sha256"]
        or permit.authority_key_id != context["evidence_authority_key_id"]
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "base permit authority differs from the exact carrier run context"
        )

    status_verifications: list[ProductionEvidenceStatusSnapshotVerification] = []
    previous_status: ProductionEvidenceStatusSnapshotVerification | None = None
    try:
        for index, (raw_status, status_document) in enumerate(
            zip(raw_statuses, status_documents, strict=True)
        ):
            issued = _parse_utc(
                status_document.get("issued_at_utc"),
                name="base status issued_at",
            )
            is_current = index == len(raw_statuses) - 1
            verification = verify_signed_production_evidence_status_snapshot(
                raw_status,
                expected_snapshot_sha256=status_document.get("snapshot_sha256"),  # type: ignore[arg-type]
                expected_permit_sha256=context["permit_sha256"],
                expected_run_id_sha256=context["run_id_sha256"],
                expected_lane=_require_lane(permit_document.get("lane")),
                expected_custodian_identity_sha256=context["custodian_identity_sha256"],
                expected_enrolled_host_identity_sha256=context[
                    "enrolled_host_identity_sha256"
                ],
                trusted_authority_keys=authority_trust,
                checked_at=checked if is_current else issued,
                minimum_trusted_sequence=status_document.get("status_sequence"),  # type: ignore[arg-type]
                minimum_trusted_external_log_checkpoint_sha256=(
                    arguments["expected_current_status_checkpoint_sha256"]
                    if is_current
                    else status_document.get("external_log_checkpoint_sha256")
                ),  # type: ignore[arg-type]
                minimum_trusted_issued_at=issued,
                expected_previous_snapshot_sha256=(
                    None if previous_status is None else previous_status.snapshot_sha256
                ),
                revoked_authority_key_ids=tuple(sorted(revoked_key_ids)),
                previous_verified_snapshot=previous_status,
            )
            status_verifications.append(verification)
            previous_status = verification
    except ValidationProductionEvidenceCustodyError as exc:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "raw base status lineage re-verification failed"
        ) from exc
    permit_issued_at = _parse_utc(
        permit.issued_at_utc,
        name="base permit issued_at",
    )
    if any(
        _parse_utc(status.issued_at_utc, name="base status issued_at")
        < permit_issued_at
        for status in status_verifications
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "base status lineage predates the signed production permit"
        )
    current_status = status_verifications[-1]
    if (
        current_status.snapshot_sha256
        != arguments["expected_current_status_snapshot_sha256"]
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "base status lineage does not terminate at the expected current status"
        )
    current_revoked_key_ids, _revoked_artifacts, _superseded_artifacts = (
        _current_status_denials(current_status)
    )
    if current_revoked_key_ids != revoked_key_ids:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "base revocation input does not match the verified current status"
        )
    status_by_sha = {
        verification.snapshot_sha256: verification
        for verification in status_verifications
    }
    raw_status_by_sha = {
        verification.snapshot_sha256: raw_status
        for verification, raw_status in zip(
            status_verifications, raw_statuses, strict=True
        )
    }
    carrier_context_status = status_by_sha.get(
        context["current_status_snapshot_sha256"]
    )
    if (
        carrier_context_status is None
        or carrier_context_status.authority_identity_sha256
        != context["current_status_authority_identity_sha256"]
        or carrier_context_status.authority_key_id
        != context["current_status_authority_key_id"]
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "carrier-bound status is absent or cross-wired in the verified lineage"
        )
    sequence_one_handoff_status = status_by_sha.get(
        sequence_one_document.get("status_snapshot_sha256")
    )
    sequence_two_handoff_status = status_by_sha.get(
        sequence_two_document.get("status_snapshot_sha256")
    )
    if sequence_one_handoff_status is None or sequence_two_handoff_status is None:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "base custody event handoff status is absent from the verified lineage"
        )
    sequence_two_raw_artifact = next(
        (
            raw_status
            for raw_status in raw_statuses
            if _raw_sha256(raw_status)
            == sequence_two_document.get("raw_artifact_sha256")
        ),
        None,
    )
    if (
        sequence_two_raw_artifact is None
        or sequence_two_raw_artifact
        != (raw_status_by_sha[sequence_two_handoff_status.snapshot_sha256])
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "base sequence-two raw status artifact is absent or cross-wired"
        )
    try:
        sequence_one = verify_signed_production_custody_event(
            raw_sequence_one,
            raw_artifact_bytes=raw_permit,
            expected_custody_event_sha256=arguments[
                "expected_sequence_one_custody_event_sha256"
            ],  # type: ignore[arg-type]
            trusted_custody_keys=custody_trust,
            trusted_authority_keys=authority_trust,
            checked_at=checked,
            expected_inner_schema_id=PRODUCTION_EVIDENCE_PERMIT_SCHEMA_ID,
            expected_artifact_stage="production_permit",
            expected_prior_custody_event_sha256=None,
            expected_custody_sequence=1,
            expected_permit_sha256=context["permit_sha256"],
            expected_run_id_sha256=context["run_id_sha256"],
            expected_lane=_require_lane(permit_document.get("lane")),
            expected_custodian_identity_sha256=context["custodian_identity_sha256"],
            expected_enrolled_host_identity_sha256=context[
                "enrolled_host_identity_sha256"
            ],
            expected_from_role=arguments["expected_sequence_one_from_role"],  # type: ignore[arg-type]
            expected_from_role_identity_sha256=arguments[
                "expected_sequence_one_from_role_identity_sha256"
            ],  # type: ignore[arg-type]
            expected_from_key_id=arguments["expected_sequence_one_from_key_id"],  # type: ignore[arg-type]
            expected_to_role=arguments["expected_sequence_one_to_role"],  # type: ignore[arg-type]
            expected_to_role_identity_sha256=arguments[
                "expected_sequence_one_to_role_identity_sha256"
            ],  # type: ignore[arg-type]
            expected_to_key_id=arguments["expected_sequence_one_to_key_id"],  # type: ignore[arg-type]
            permit_source=raw_permit,
            permit_verification_arguments=permit_arguments,
            verified_permit=permit,
            status_lineage_sources=raw_statuses,
            expected_current_status_snapshot_sha256=current_status.snapshot_sha256,
            expected_current_status_checkpoint_sha256=arguments[
                "expected_current_status_checkpoint_sha256"
            ],  # type: ignore[arg-type]
            verified_handoff_status_snapshot=sequence_one_handoff_status,
            verified_current_status_snapshot=current_status,
            revoked_authority_key_ids=tuple(sorted(revoked_key_ids)),
        )
        sequence_two = verify_signed_production_custody_event(
            raw_sequence_two,
            raw_artifact_bytes=sequence_two_raw_artifact,
            expected_custody_event_sha256=arguments[
                "expected_sequence_two_custody_event_sha256"
            ],  # type: ignore[arg-type]
            trusted_custody_keys=custody_trust,
            trusted_authority_keys=authority_trust,
            checked_at=checked,
            expected_inner_schema_id=PRODUCTION_EVIDENCE_STATUS_SNAPSHOT_SCHEMA_ID,
            expected_artifact_stage="status_snapshot",
            expected_prior_custody_event_sha256=sequence_one.custody_event_sha256,
            expected_custody_sequence=2,
            expected_permit_sha256=context["permit_sha256"],
            expected_run_id_sha256=context["run_id_sha256"],
            expected_lane=_require_lane(permit_document.get("lane")),
            expected_custodian_identity_sha256=context["custodian_identity_sha256"],
            expected_enrolled_host_identity_sha256=context[
                "enrolled_host_identity_sha256"
            ],
            expected_from_role=arguments["expected_sequence_two_from_role"],  # type: ignore[arg-type]
            expected_from_role_identity_sha256=arguments[
                "expected_sequence_two_from_role_identity_sha256"
            ],  # type: ignore[arg-type]
            expected_from_key_id=arguments["expected_sequence_two_from_key_id"],  # type: ignore[arg-type]
            expected_to_role=arguments["expected_sequence_two_to_role"],  # type: ignore[arg-type]
            expected_to_role_identity_sha256=arguments[
                "expected_sequence_two_to_role_identity_sha256"
            ],  # type: ignore[arg-type]
            expected_to_key_id=arguments["expected_sequence_two_to_key_id"],  # type: ignore[arg-type]
            permit_source=raw_permit,
            permit_verification_arguments=permit_arguments,
            verified_permit=permit,
            status_lineage_sources=raw_statuses,
            expected_current_status_snapshot_sha256=current_status.snapshot_sha256,
            expected_current_status_checkpoint_sha256=arguments[
                "expected_current_status_checkpoint_sha256"
            ],  # type: ignore[arg-type]
            verified_handoff_status_snapshot=sequence_two_handoff_status,
            verified_current_status_snapshot=current_status,
            revoked_authority_key_ids=tuple(sorted(revoked_key_ids)),
            previous_event_source=raw_sequence_one,
            previous_raw_artifact_bytes=raw_permit,
            previous_verified_event=sequence_one,
        )
    except ValidationProductionEvidenceCustodyError as exc:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "raw base custody sequence-one/two re-verification failed"
        ) from exc
    _require_current_status_allows_identities(
        current_status,
        identities=(
            sequence_one.custody_event_sha256,
            _raw_sha256(raw_sequence_one),
            sequence_two.custody_event_sha256,
            _raw_sha256(raw_sequence_two),
            context["process_launch_identity_sha256"],
        ),
        name="base custody/process prefix",
    )
    return _BaseSequenceTwoPrefixVerification(
        permit=permit,
        current_status=current_status,
        status_lineage=tuple(status_verifications),
        sequence_one=sequence_one,
        sequence_two=sequence_two,
        raw_permit_sha256=_raw_sha256(raw_permit),
        raw_status_sha256s=tuple(_raw_sha256(raw) for raw in raw_statuses),
        raw_sequence_one_sha256=_raw_sha256(raw_sequence_one),
        raw_sequence_two_sha256=_raw_sha256(raw_sequence_two),
    )


def _require_global_extension_trust_separation(
    *,
    lane: str,
    current_status: ProductionEvidenceStatusSnapshotVerification,
    base_reverification_arguments: dict[str, object],
    stage3_reverification_arguments: dict[str, object],
    stage4_reverification_arguments: dict[str, object] | None = None,
) -> None:
    if (
        type(stage3_reverification_arguments) is not dict
        or set(stage3_reverification_arguments)
        != _EXTENSION_STAGE3_REVERIFICATION_ARGUMENT_FIELDS
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension stage3 reverification arguments are not exact"
        )
    authority_trust = _exact_authority_trust_map(
        base_reverification_arguments["trusted_authority_keys"]
    )
    custody_trust = _exact_custody_trust_map(
        base_reverification_arguments["trusted_custody_keys"]
    )
    upstream_review_arguments = stage3_reverification_arguments[
        "upstream_review_verification_arguments"
    ]
    if type(upstream_review_arguments) is not dict:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension upstream review arguments must be an exact dict"
        )
    selected_lane = _require_lane(lane)
    upstream_review_trust = _trusted_review_keys(
        upstream_review_arguments,
        lane=selected_lane,
    )
    production_review_trust = _exact_production_review_trust_map(
        stage3_reverification_arguments["trusted_production_reviewer_keys"]
    )

    identity_groups: list[set[str]] = [
        {
            _require_sha256(
                upstream_review_arguments[
                    "expected_implementation_author_identity_sha256"
                ],
                name="extension implementation author identity",
            )
        },
        {anchor.authority_identity_sha256 for anchor in authority_trust.values()},
        {anchor.role_identity_sha256 for anchor in custody_trust.values()},
        {
            anchor.reviewer_identity_sha256
            for anchor in upstream_review_trust.values()  # type: ignore[attr-defined]
        },
        {
            anchor.reviewer_identity_sha256
            for anchor in production_review_trust.values()
        },
    ]
    key_id_groups: list[set[str]] = [
        set(authority_trust),
        set(custody_trust),
        set(upstream_review_trust),
        set(production_review_trust),
    ]
    material_groups: list[set[bytes]] = [
        {anchor.verification_key for anchor in authority_trust.values()},
        {anchor.verification_key for anchor in custody_trust.values()},
        {
            anchor.verification_key
            for anchor in upstream_review_trust.values()  # type: ignore[attr-defined]
        },
        {anchor.verification_key for anchor in production_review_trust.values()},
    ]
    if stage4_reverification_arguments is not None:
        if (
            type(stage4_reverification_arguments) is not dict
            or set(stage4_reverification_arguments)
            != _EXTENSION_STAGE4_REVERIFICATION_ARGUMENT_FIELDS
        ):
            raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                "extension stage4 reverification arguments are not exact"
            )
        upstream_authorization_arguments = stage4_reverification_arguments[
            "upstream_authorization_verification_arguments"
        ]
        if type(upstream_authorization_arguments) is not dict:
            raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                "extension upstream authorization arguments must be an exact dict"
            )
        operator_trust = _trusted_operator_keys(
            upstream_authorization_arguments,
            lane=selected_lane,
        )
        if (
            upstream_authorization_arguments["trusted_reviewer_keys"]
            != upstream_review_trust
            or upstream_authorization_arguments[
                "expected_implementation_author_identity_sha256"
            ]
            != upstream_review_arguments[
                "expected_implementation_author_identity_sha256"
            ]
        ):
            raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                "extension stage3 and stage4 reviewer trust domains differ"
            )
        production_authorization_trust = _exact_production_authorization_trust_map(
            stage4_reverification_arguments["trusted_production_authorization_keys"]
        )
        identity_groups.extend(
            [
                {
                    anchor.operator_identity_sha256
                    for anchor in operator_trust.values()  # type: ignore[attr-defined]
                },
                {
                    anchor.operator_identity_sha256
                    for anchor in production_authorization_trust.values()
                },
            ]
        )
        key_id_groups.extend([set(operator_trust), set(production_authorization_trust)])
        material_groups.extend(
            [
                {
                    anchor.verification_key
                    for anchor in operator_trust.values()  # type: ignore[attr-defined]
                },
                {
                    anchor.verification_key
                    for anchor in production_authorization_trust.values()
                },
            ]
        )
    for groups, name in (
        (identity_groups, "identity"),
        (key_id_groups, "key id"),
        (material_groups, "key material"),
    ):
        for index, group in enumerate(groups):
            if any(group & other for other in groups[index + 1 :]):
                raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                    f"extension global trust {name} contains a cross-role alias"
                )
    revoked_key_ids, _revoked_artifacts, _superseded_artifacts = (
        _current_status_denials(current_status)
    )
    all_trusted_key_ids = set().union(*key_id_groups)
    if all_trusted_key_ids & revoked_key_ids:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension trust map retains a currently revoked key"
        )


def _extension_event_projection(
    *,
    artifact_stage: str,
    custody_sequence: int,
    prior_custody_event_sha256: str,
    raw_carrier_bytes: bytes,
    carrier: ProductionPreExecutionReviewCarrierVerification
    | ProductionAuthorizationCarrierVerification,
    run_context: dict[str, object],
    from_role: str,
    from_role_identity_sha256: str,
    from_key_id: str,
    to_role: str,
    to_role_identity_sha256: str,
    to_key_id: str,
    handed_off_at_utc: str,
    received_at_utc: str,
    status_snapshot_sha256: str,
) -> dict[str, Any]:
    expected = {
        3: (
            "pre_execution_review",
            PRODUCTION_PRE_EXECUTION_REVIEW_CARRIER_SCHEMA_ID,
            ProductionPreExecutionReviewCarrierVerification,
        ),
        4: (
            "authorization",
            PRODUCTION_AUTHORIZATION_CARRIER_SCHEMA_ID,
            ProductionAuthorizationCarrierVerification,
        ),
    }
    if type(custody_sequence) is not int or custody_sequence not in expected:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension custody sequence must be exactly three or four"
        )
    expected_stage, inner_schema_id, verification_type = expected[custody_sequence]
    stage = _require_token(artifact_stage, name="extension artifact stage")
    if stage != expected_stage or type(carrier) is not verification_type:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension custody stage, sequence, or carrier type is cross-wired"
        )
    context = _run_context_projection(run_context)
    prior = _require_sha256(
        prior_custody_event_sha256,
        name="extension prior custody event",
    )
    if (
        carrier.prior_custody_event_sha256 != prior
        or carrier.permit_sha256 != context["permit_sha256"]
        or carrier.study_id_sha256 != context["study_id_sha256"]
        or carrier.run_id_sha256 != context["run_id_sha256"]
        or carrier.authorization_nonce_sha256 != context["authorization_nonce_sha256"]
        or carrier.current_status_snapshot_sha256
        != context["current_status_snapshot_sha256"]
        or carrier.process_launch_identity_sha256
        != context["process_launch_identity_sha256"]
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension carrier differs from the exact custody run context"
        )
    if carrier.lane not in PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_LANES:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension carrier lane is unsupported"
        )
    from_role_value = _require_token(from_role, name="extension from role")
    to_role_value = _require_token(to_role, name="extension to role")
    from_identity = _require_sha256(
        from_role_identity_sha256,
        name="extension from identity",
    )
    to_identity = _require_sha256(
        to_role_identity_sha256,
        name="extension to identity",
    )
    from_key = _require_token(from_key_id, name="extension from key id")
    to_key = _require_token(to_key_id, name="extension to key id")
    if (
        from_role_value == to_role_value
        or from_identity == to_identity
        or from_key == to_key
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension custody handoff roles, identities, and keys must differ"
        )
    handed_off = _parse_utc(
        handed_off_at_utc,
        name="extension custody handed_off_at",
    )
    received = _parse_utc(received_at_utc, name="extension custody received_at")
    carrier_signed = _parse_utc(carrier.signed_at_utc, name="carrier signed_at")
    carrier_expires = _parse_utc(carrier.expires_at_utc, name="carrier expires_at")
    if (
        handed_off < carrier_signed
        or received < handed_off
        or received >= carrier_expires
        or received - handed_off
        > PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_EVENT_MAX_HANDOFF_DURATION
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension custody handoff timestamps are invalid"
        )
    status_sha256 = _require_sha256(
        status_snapshot_sha256,
        name="extension handoff status snapshot",
    )
    if status_sha256 != carrier.current_status_snapshot_sha256:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension handoff status differs from the signed carrier context"
        )
    return {
        "schema_id": (
            PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_EVENT_SCHEMA_ID
        ),
        "contract_sha256": (
            FROZEN_VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256
        ),
        "base_custody_contract_sha256": (
            FROZEN_VALIDATION_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_SHA256
        ),
        "evidence_class": PRODUCTION_EVIDENCE_CLASS,
        "inner_schema_id": inner_schema_id,
        "artifact_stage": stage,
        "custody_sequence": custody_sequence,
        "prior_custody_event_sha256": prior,
        "carrier_sha256": carrier.carrier_sha256,
        "raw_carrier_sha256": _raw_sha256(raw_carrier_bytes),
        "raw_carrier_byte_count": len(raw_carrier_bytes),
        **context,
        "lane": carrier.lane,
        "from_role": from_role_value,
        "from_role_identity_sha256": from_identity,
        "from_key_id": from_key,
        "to_role": to_role_value,
        "to_role_identity_sha256": to_identity,
        "to_key_id": to_key,
        "handed_off_at_utc": handed_off_at_utc,
        "received_at_utc": received_at_utc,
        "status_snapshot_sha256": status_sha256,
        "requires_full_raw_prefix_reverification": True,
        "custody_successor_uniqueness_enforced": False,
        "eligible_for_atomic_execution_reservation": False,
        "full_asymmetric_chain_established": False,
        **_CLAIM_POLICY,
        "superseded": False,
        "revoked": False,
    }


def _build_signed_extension_event(
    *,
    artifact_stage: str,
    custody_sequence: int,
    prior_custody_event_sha256: str,
    raw_carrier_bytes: bytes,
    carrier: ProductionPreExecutionReviewCarrierVerification
    | ProductionAuthorizationCarrierVerification,
    run_context: dict[str, object],
    from_role: str,
    from_role_identity_sha256: str,
    from_key_id: str,
    from_signing_key: bytes,
    to_role: str,
    to_role_identity_sha256: str,
    to_key_id: str,
    to_signing_key: bytes,
    handed_off_at: datetime,
    received_at: datetime,
    status_snapshot_sha256: str,
) -> dict[str, Any]:
    from_private_key = from_signing_key
    to_private_key = to_signing_key
    if (
        type(from_private_key) is not bytes
        or len(from_private_key) != 32
        or type(to_private_key) is not bytes
        or len(to_private_key) != 32
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension custody signing keys must be 32 private-key bytes"
        )
    try:
        from_public_key = ed25519_public_key_bytes(from_private_key)
        to_public_key = ed25519_public_key_bytes(to_private_key)
    except ReferenceMinimizationValidationEd25519Error as exc:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension custody public-key derivation failed"
        ) from exc
    if (
        from_private_key == to_private_key
        or from_public_key == to_public_key
        or from_private_key == to_public_key
        or to_private_key == from_public_key
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension custody signing key material must be distinct"
        )
    projection = _extension_event_projection(
        artifact_stage=artifact_stage,
        custody_sequence=custody_sequence,
        prior_custody_event_sha256=prior_custody_event_sha256,
        raw_carrier_bytes=raw_carrier_bytes,
        carrier=carrier,
        run_context=run_context,
        from_role=from_role,
        from_role_identity_sha256=from_role_identity_sha256,
        from_key_id=from_key_id,
        to_role=to_role,
        to_role_identity_sha256=to_role_identity_sha256,
        to_key_id=to_key_id,
        handed_off_at_utc=_format_utc(
            handed_off_at,
            name="extension custody handed_off_at",
        ),
        received_at_utc=_format_utc(
            received_at,
            name="extension custody received_at",
        ),
        status_snapshot_sha256=status_snapshot_sha256,
    )
    payload = dict(projection)
    payload["custody_event_sha256"] = _sha256(projection)
    message = _canonical_bytes(payload)
    try:
        from_signature = sign_ed25519(message, from_private_key)
        to_signature = sign_ed25519(message, to_private_key)
    except ReferenceMinimizationValidationEd25519Error as exc:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension custody event signing failed"
        ) from exc
    payload["signatures"] = {
        "from": {
            "algorithm": (
                PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_SIGNATURE_ALGORITHM
            ),
            "key_id": _require_token(from_key_id, name="extension from key id"),
            "value": from_signature,
        },
        "to": {
            "algorithm": (
                PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_SIGNATURE_ALGORITHM
            ),
            "key_id": _require_token(to_key_id, name="extension to key id"),
            "value": to_signature,
        },
    }
    if len(_canonical_bytes(payload)) > (
        PRODUCTION_REVIEW_AUTHORIZATION_MAX_SIGNED_TRANSPORT_BYTES
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension custody event exceeds its signed transport bound"
        )
    if not verify_ed25519(message, from_signature, from_public_key) or not (
        verify_ed25519(message, to_signature, to_public_key)
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension custody event self-verification failed"
        )
    return payload


def _verify_extension_event_signatures(
    source: bytes,
    *,
    trusted_custody_keys: dict[str, CustodyRoleTrustAnchor],
) -> tuple[
    dict[str, Any],
    str,
    str,
    CustodyRoleTrustAnchor,
    CustodyRoleTrustAnchor,
    str,
    str,
]:
    raw_event, payload = _canonical_raw_document(
        source,
        name="raw custody extension event",
    )
    custody_trust = _exact_custody_trust_map(trusted_custody_keys)
    signatures = payload.pop("signatures", None)
    if type(signatures) is not dict or set(signatures) != {"from", "to"}:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension custody event dual signatures are missing"
        )
    for slot in ("from", "to"):
        signature = signatures[slot]
        if type(signature) is not dict or set(signature) != {
            "algorithm",
            "key_id",
            "value",
        }:
            raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                "extension custody signature fields are invalid"
            )
        if signature["algorithm"] != (
            PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_SIGNATURE_ALGORITHM
        ):
            raise ValidationProductionReviewAuthorizationCustodyExtensionError(
                "extension custody signature algorithm is unsupported"
            )
    from_key_id = _require_token(
        signatures["from"]["key_id"],
        name="extension from key id",
    )
    to_key_id = _require_token(
        signatures["to"]["key_id"],
        name="extension to key id",
    )
    from_anchor = custody_trust.get(from_key_id)
    to_anchor = custody_trust.get(to_key_id)
    if (
        type(from_anchor) is not CustodyRoleTrustAnchor
        or type(to_anchor) is not CustodyRoleTrustAnchor
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension custody event key is not trusted"
        )
    message = _canonical_bytes(payload)
    try:
        verified = verify_ed25519(
            message,
            signatures["from"]["value"],
            from_anchor.verification_key,
        ) and verify_ed25519(
            message,
            signatures["to"]["value"],
            to_anchor.verification_key,
        )
    except ReferenceMinimizationValidationEd25519Error as exc:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension custody Ed25519 verifier is unavailable"
        ) from exc
    if not verified:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension custody event dual signature verification failed"
        )
    event_sha256 = payload.pop("custody_event_sha256", None)
    if event_sha256 != _sha256(payload):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension custody event SHA-256 verification failed"
        )
    event_sha256 = _require_sha256(event_sha256, name="extension custody event")
    if (
        payload.get("from_key_id") != from_key_id
        or payload.get("to_key_id") != to_key_id
        or payload.get("from_role") != from_anchor.custody_role
        or payload.get("to_role") != to_anchor.custody_role
        or payload.get("from_role_identity_sha256") != from_anchor.role_identity_sha256
        or payload.get("to_role_identity_sha256") != to_anchor.role_identity_sha256
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension custody event role, identity, or key is cross-wired"
        )
    return (
        payload,
        event_sha256,
        _raw_sha256(raw_event),
        from_anchor,
        to_anchor,
        _raw_sha256(from_anchor.verification_key),
        _raw_sha256(to_anchor.verification_key),
    )


def build_signed_production_pre_execution_review_custody_extension_event(
    *,
    raw_pre_execution_review_carrier_bytes: bytes,
    raw_review_attestation_bytes: bytes,
    lane: str,
    run_context: dict[str, object],
    upstream_review_verification_arguments: dict[str, object],
    trusted_production_reviewer_keys: dict[str, ProductionReviewCarrierTrustAnchor],
    prior_custody_event_sha256: str,
    from_role: str,
    from_role_identity_sha256: str,
    from_key_id: str,
    from_signing_key: bytes,
    to_role: str,
    to_role_identity_sha256: str,
    to_key_id: str,
    to_signing_key: bytes,
    handed_off_at: datetime,
    received_at: datetime,
    status_snapshot_sha256: str,
    revoked_production_reviewer_key_ids: Sequence[str] = (),
    revoked_upstream_reviewer_key_ids: Sequence[str] = (),
    revoked_carrier_sha256s: Sequence[str] = (),
    superseded_carrier_sha256s: Sequence[str] = (),
    revoked_upstream_review_sha256s: Sequence[str] = (),
    superseded_upstream_review_sha256s: Sequence[str] = (),
) -> dict[str, Any]:
    """Dual-sign a claim-closed candidate seq3 custody event."""

    raw_carrier, carrier_document = _canonical_raw_document(
        raw_pre_execution_review_carrier_bytes,
        name="raw pre-execution review carrier for custody",
    )
    carrier = verify_signed_production_pre_execution_review_carrier(
        raw_carrier,
        raw_review_attestation_bytes=raw_review_attestation_bytes,
        expected_carrier_sha256=carrier_document.get("carrier_sha256"),  # type: ignore[arg-type]
        expected_lane=lane,
        expected_run_context=run_context,
        expected_prior_custody_event_sha256=prior_custody_event_sha256,
        upstream_review_verification_arguments=(upstream_review_verification_arguments),
        trusted_production_reviewer_keys=trusted_production_reviewer_keys,
        checked_at=handed_off_at,
        revoked_production_reviewer_key_ids=(revoked_production_reviewer_key_ids),
        revoked_upstream_reviewer_key_ids=revoked_upstream_reviewer_key_ids,
        revoked_carrier_sha256s=revoked_carrier_sha256s,
        superseded_carrier_sha256s=superseded_carrier_sha256s,
        revoked_upstream_review_sha256s=revoked_upstream_review_sha256s,
        superseded_upstream_review_sha256s=superseded_upstream_review_sha256s,
    )
    return _build_signed_extension_event(
        artifact_stage="pre_execution_review",
        custody_sequence=3,
        prior_custody_event_sha256=prior_custody_event_sha256,
        raw_carrier_bytes=raw_carrier,
        carrier=carrier,
        run_context=run_context,
        from_role=from_role,
        from_role_identity_sha256=from_role_identity_sha256,
        from_key_id=from_key_id,
        from_signing_key=from_signing_key,
        to_role=to_role,
        to_role_identity_sha256=to_role_identity_sha256,
        to_key_id=to_key_id,
        to_signing_key=to_signing_key,
        handed_off_at=handed_off_at,
        received_at=received_at,
        status_snapshot_sha256=status_snapshot_sha256,
    )


def build_signed_production_authorization_custody_extension_event(
    *,
    raw_authorization_carrier_bytes: bytes,
    raw_authorization_receipt_bytes: bytes,
    raw_review_attestation_bytes: bytes,
    raw_pre_execution_review_carrier_bytes: bytes,
    lane: str,
    run_context: dict[str, object],
    upstream_authorization_verification_arguments: dict[str, object],
    pre_execution_review_reverification_arguments: dict[str, object],
    trusted_production_authorization_keys: dict[
        str, ProductionAuthorizationCarrierTrustAnchor
    ],
    prior_custody_event_sha256: str,
    from_role: str,
    from_role_identity_sha256: str,
    from_key_id: str,
    from_signing_key: bytes,
    to_role: str,
    to_role_identity_sha256: str,
    to_key_id: str,
    to_signing_key: bytes,
    handed_off_at: datetime,
    received_at: datetime,
    status_snapshot_sha256: str,
    revoked_production_authorization_key_ids: Sequence[str] = (),
    revoked_upstream_authorization_key_ids: Sequence[str] = (),
    revoked_carrier_sha256s: Sequence[str] = (),
    superseded_carrier_sha256s: Sequence[str] = (),
    revoked_upstream_authorization_sha256s: Sequence[str] = (),
    superseded_upstream_authorization_sha256s: Sequence[str] = (),
) -> dict[str, Any]:
    """Dual-sign a claim-closed candidate seq4 custody event."""

    raw_carrier, carrier_document = _canonical_raw_document(
        raw_authorization_carrier_bytes,
        name="raw authorization carrier for custody",
    )
    carrier = verify_signed_production_authorization_carrier(
        raw_carrier,
        raw_authorization_receipt_bytes=raw_authorization_receipt_bytes,
        raw_review_attestation_bytes=raw_review_attestation_bytes,
        raw_pre_execution_review_carrier_bytes=(raw_pre_execution_review_carrier_bytes),
        expected_carrier_sha256=carrier_document.get("carrier_sha256"),  # type: ignore[arg-type]
        expected_lane=lane,
        expected_run_context=run_context,
        expected_prior_custody_event_sha256=prior_custody_event_sha256,
        upstream_authorization_verification_arguments=(
            upstream_authorization_verification_arguments
        ),
        pre_execution_review_reverification_arguments=(
            pre_execution_review_reverification_arguments
        ),
        trusted_production_authorization_keys=(trusted_production_authorization_keys),
        checked_at=handed_off_at,
        revoked_production_authorization_key_ids=(
            revoked_production_authorization_key_ids
        ),
        revoked_upstream_authorization_key_ids=(revoked_upstream_authorization_key_ids),
        revoked_carrier_sha256s=revoked_carrier_sha256s,
        superseded_carrier_sha256s=superseded_carrier_sha256s,
        revoked_upstream_authorization_sha256s=(revoked_upstream_authorization_sha256s),
        superseded_upstream_authorization_sha256s=(
            superseded_upstream_authorization_sha256s
        ),
    )
    return _build_signed_extension_event(
        artifact_stage="authorization",
        custody_sequence=4,
        prior_custody_event_sha256=prior_custody_event_sha256,
        raw_carrier_bytes=raw_carrier,
        carrier=carrier,
        run_context=run_context,
        from_role=from_role,
        from_role_identity_sha256=from_role_identity_sha256,
        from_key_id=from_key_id,
        from_signing_key=from_signing_key,
        to_role=to_role,
        to_role_identity_sha256=to_role_identity_sha256,
        to_key_id=to_key_id,
        to_signing_key=to_signing_key,
        handed_off_at=handed_off_at,
        received_at=received_at,
        status_snapshot_sha256=status_snapshot_sha256,
    )


def verify_signed_production_pre_execution_review_custody_extension_event(
    source: bytes,
    *,
    raw_pre_execution_review_carrier_bytes: bytes,
    raw_review_attestation_bytes: bytes,
    raw_permit_bytes: bytes,
    raw_status_lineage_bytes: Sequence[bytes],
    raw_sequence_one_custody_event_bytes: bytes,
    raw_sequence_two_custody_event_bytes: bytes,
    expected_run_context: dict[str, object],
    base_reverification_arguments: dict[str, object],
    stage3_reverification_arguments: dict[str, object],
    event_reverification_arguments: dict[str, object],
    checked_at: datetime,
) -> ProductionReviewAuthorizationCustodyExtensionEventVerification:
    """Verify seq3 after internally rebuilding the exact raw v1 prefix."""

    if (
        type(event_reverification_arguments) is not dict
        or set(event_reverification_arguments)
        != _EXTENSION_SEQUENCE_THREE_EVENT_REVERIFICATION_ARGUMENT_FIELDS
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension sequence-three event arguments are not exact"
        )
    if (
        type(base_reverification_arguments) is not dict
        or set(base_reverification_arguments)
        != _BASE_SEQUENCE_TWO_REVERIFICATION_ARGUMENT_FIELDS
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "base sequence-two reverification arguments are not exact"
        )
    custody_trust = _exact_custody_trust_map(
        base_reverification_arguments["trusted_custody_keys"]
    )
    (
        payload,
        event_sha256,
        raw_event_sha256,
        from_anchor,
        to_anchor,
        from_public_key_sha256,
        to_public_key_sha256,
    ) = _verify_extension_event_signatures(
        source,
        trusted_custody_keys=custody_trust,
    )
    if event_sha256 != _require_sha256(
        event_reverification_arguments["expected_custody_event_sha256"],
        name="expected extension sequence-three event",
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension sequence-three event is cross-wired to its identity"
        )
    if (
        payload.get("schema_id")
        != PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_EVENT_SCHEMA_ID
        or payload.get("contract_sha256")
        != FROZEN_VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256
        or payload.get("base_custody_contract_sha256")
        != FROZEN_VALIDATION_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_SHA256
        or payload.get("artifact_stage") != "pre_execution_review"
        or payload.get("custody_sequence") != 3
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension sequence-three schema, contract, stage, or sequence is cross-wired"
        )
    checked = _parse_utc(
        _format_utc(checked_at, name="extension sequence-three checked_at"),
        name="extension sequence-three checked_at",
    )
    handed_off = _parse_utc(
        payload.get("handed_off_at_utc"),
        name="extension sequence-three handed_off_at",
    )
    received = _parse_utc(
        payload.get("received_at_utc"),
        name="extension sequence-three received_at",
    )
    if checked < received:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension sequence-three event is not yet valid"
        )
    base_prefix = _reverify_base_sequence_two_prefix(
        raw_permit_bytes=raw_permit_bytes,
        raw_status_lineage_bytes=raw_status_lineage_bytes,
        raw_sequence_one_custody_event_bytes=raw_sequence_one_custody_event_bytes,
        raw_sequence_two_custody_event_bytes=raw_sequence_two_custody_event_bytes,
        run_context=expected_run_context,
        base_reverification_arguments=base_reverification_arguments,
        checked_at=checked,
    )
    selected_lane = _require_lane(payload.get("lane"))
    if selected_lane != base_prefix.permit.lane:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension sequence-three lane differs from the verified permit"
        )
    _require_global_extension_trust_separation(
        lane=selected_lane,
        current_status=base_prefix.current_status,
        base_reverification_arguments=base_reverification_arguments,
        stage3_reverification_arguments=stage3_reverification_arguments,
    )
    revoked_key_ids, revoked_artifacts, superseded_artifacts = _current_status_denials(
        base_prefix.current_status
    )
    if (
        type(stage3_reverification_arguments) is not dict
        or set(stage3_reverification_arguments)
        != _EXTENSION_STAGE3_REVERIFICATION_ARGUMENT_FIELDS
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension stage3 reverification arguments are not exact"
        )
    raw_carrier, carrier_document = _canonical_raw_document(
        raw_pre_execution_review_carrier_bytes,
        name="raw sequence-three carrier",
    )
    expected_carrier_sha256 = _require_sha256(
        stage3_reverification_arguments["expected_carrier_sha256"],
        name="expected sequence-three carrier",
    )
    if (
        expected_carrier_sha256 != payload.get("carrier_sha256")
        or expected_carrier_sha256 != carrier_document.get("carrier_sha256")
        or payload.get("raw_carrier_sha256") != _raw_sha256(raw_carrier)
        or payload.get("raw_carrier_byte_count") != len(raw_carrier)
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension sequence-three carrier is substituted or cross-wired"
        )
    carrier = verify_signed_production_pre_execution_review_carrier(
        raw_carrier,
        raw_review_attestation_bytes=raw_review_attestation_bytes,
        expected_carrier_sha256=expected_carrier_sha256,
        expected_lane=selected_lane,
        expected_run_context=expected_run_context,
        expected_prior_custody_event_sha256=(
            base_prefix.sequence_two.custody_event_sha256
        ),
        upstream_review_verification_arguments=stage3_reverification_arguments[
            "upstream_review_verification_arguments"
        ],  # type: ignore[arg-type]
        trusted_production_reviewer_keys=stage3_reverification_arguments[
            "trusted_production_reviewer_keys"
        ],  # type: ignore[arg-type]
        checked_at=handed_off,
        revoked_production_reviewer_key_ids=tuple(sorted(revoked_key_ids)),
        revoked_upstream_reviewer_key_ids=tuple(sorted(revoked_key_ids)),
        revoked_carrier_sha256s=tuple(sorted(revoked_artifacts)),
        superseded_carrier_sha256s=tuple(sorted(superseded_artifacts)),
        revoked_upstream_review_sha256s=tuple(sorted(revoked_artifacts)),
        superseded_upstream_review_sha256s=tuple(sorted(superseded_artifacts)),
    )
    expected_projection = _extension_event_projection(
        artifact_stage="pre_execution_review",
        custody_sequence=3,
        prior_custody_event_sha256=base_prefix.sequence_two.custody_event_sha256,
        raw_carrier_bytes=raw_carrier,
        carrier=carrier,
        run_context=expected_run_context,
        from_role=event_reverification_arguments["expected_from_role"],  # type: ignore[arg-type]
        from_role_identity_sha256=event_reverification_arguments[
            "expected_from_role_identity_sha256"
        ],  # type: ignore[arg-type]
        from_key_id=event_reverification_arguments["expected_from_key_id"],  # type: ignore[arg-type]
        to_role=event_reverification_arguments["expected_to_role"],  # type: ignore[arg-type]
        to_role_identity_sha256=event_reverification_arguments[
            "expected_to_role_identity_sha256"
        ],  # type: ignore[arg-type]
        to_key_id=event_reverification_arguments["expected_to_key_id"],  # type: ignore[arg-type]
        handed_off_at_utc=payload.get("handed_off_at_utc"),  # type: ignore[arg-type]
        received_at_utc=payload.get("received_at_utc"),  # type: ignore[arg-type]
        status_snapshot_sha256=payload.get("status_snapshot_sha256"),  # type: ignore[arg-type]
    )
    if _canonical_bytes(payload) != _canonical_bytes(expected_projection):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension sequence-three event fields are omitted or transplanted"
        )
    _require_claims_closed(payload)
    handoff_status = next(
        (
            status
            for status in base_prefix.status_lineage
            if status.snapshot_sha256 == payload["status_snapshot_sha256"]
        ),
        None,
    )
    if handoff_status is None:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension sequence-three handoff status is not in the verified lineage"
        )
    handoff_status_issued = _parse_utc(
        handoff_status.issued_at_utc,
        name="extension sequence-three handoff status issued_at",
    )
    permit_issued = _parse_utc(
        base_prefix.permit.issued_at_utc,
        name="extension sequence-three permit issued_at",
    )
    permit_expires = _parse_utc(
        base_prefix.permit.expires_at_utc,
        name="extension sequence-three permit expires_at",
    )
    carrier_signed = _parse_utc(
        carrier.signed_at_utc,
        name="extension sequence-three carrier signed_at",
    )
    sequence_two_received = _parse_utc(
        base_prefix.sequence_two.received_at_utc,
        name="base sequence-two received_at",
    )
    if (
        not handoff_status_issued <= carrier_signed
        or handed_off - handoff_status_issued
        > PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_EVENT_MAX_HANDOFF_DURATION
        or not permit_issued
        <= carrier_signed
        <= handed_off
        <= received
        < permit_expires
        or sequence_two_received > carrier_signed
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension sequence-three prefix or handoff time is invalid"
        )
    if (
        base_prefix.sequence_two.to_role != payload["from_role"]
        or base_prefix.sequence_two.to_role_identity_sha256
        != payload["from_role_identity_sha256"]
        or base_prefix.sequence_two.to_key_id != payload["from_key_id"]
        or base_prefix.sequence_two.to_public_key_sha256 != from_public_key_sha256
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension sequence-three predecessor custody continuity failed"
        )
    _require_current_status_allows_identities(
        base_prefix.current_status,
        identities=(
            event_sha256,
            raw_event_sha256,
            carrier.carrier_sha256,
            carrier.raw_carrier_sha256,
            carrier.upstream_review_attestation_sha256,
            carrier.upstream_review_raw_sha256,
        ),
        name="extension sequence-three prefix",
    )
    return _new_extension_event_verification(
        custody_event_sha256=event_sha256,
        raw_event_sha256=raw_event_sha256,
        raw_event_byte_count=len(source),
        artifact_stage="pre_execution_review",
        custody_sequence=3,
        prior_custody_event_sha256=base_prefix.sequence_two.custody_event_sha256,
        carrier_sha256=carrier.carrier_sha256,
        raw_carrier_sha256=carrier.raw_carrier_sha256,
        raw_carrier_byte_count=carrier.raw_carrier_byte_count,
        permit_sha256=carrier.permit_sha256,
        study_id_sha256=carrier.study_id_sha256,
        run_id_sha256=carrier.run_id_sha256,
        authorization_nonce_sha256=carrier.authorization_nonce_sha256,
        lane=selected_lane,
        custodian_identity_sha256=payload["custodian_identity_sha256"],
        enrolled_host_identity_sha256=payload["enrolled_host_identity_sha256"],
        process_launch_identity_sha256=carrier.process_launch_identity_sha256,
        from_role=from_anchor.custody_role,
        from_role_identity_sha256=from_anchor.role_identity_sha256,
        from_key_id=payload["from_key_id"],
        from_public_key_sha256=from_public_key_sha256,
        to_role=to_anchor.custody_role,
        to_role_identity_sha256=to_anchor.role_identity_sha256,
        to_key_id=payload["to_key_id"],
        to_public_key_sha256=to_public_key_sha256,
        handed_off_at_utc=payload["handed_off_at_utc"],
        received_at_utc=payload["received_at_utc"],
        handoff_status_snapshot_sha256=payload["status_snapshot_sha256"],
        current_status_snapshot_sha256=base_prefix.current_status.snapshot_sha256,
        custody_event_lineage_sha256s=(
            *base_prefix.sequence_two.lineage_custody_event_sha256s,
            event_sha256,
        ),
        raw_custody_event_lineage_sha256s=(
            base_prefix.raw_sequence_one_sha256,
            base_prefix.raw_sequence_two_sha256,
            raw_event_sha256,
        ),
        carrier_lineage_sha256s=(carrier.carrier_sha256,),
        raw_carrier_lineage_sha256s=(carrier.raw_carrier_sha256,),
        upstream_review_attestation_sha256=(carrier.upstream_review_attestation_sha256),
        upstream_review_raw_sha256=carrier.upstream_review_raw_sha256,
        upstream_authorization_receipt_sha256=None,
        upstream_authorization_raw_sha256=None,
        checked_at_utc=_format_utc(
            checked,
            name="extension sequence-three checked_at",
        ),
    )


def verify_signed_production_authorization_custody_extension_event(
    source: bytes,
    *,
    raw_authorization_carrier_bytes: bytes,
    raw_authorization_receipt_bytes: bytes,
    raw_review_attestation_bytes: bytes,
    raw_pre_execution_review_carrier_bytes: bytes,
    raw_sequence_three_custody_event_bytes: bytes,
    raw_permit_bytes: bytes,
    raw_status_lineage_bytes: Sequence[bytes],
    raw_sequence_one_custody_event_bytes: bytes,
    raw_sequence_two_custody_event_bytes: bytes,
    expected_run_context: dict[str, object],
    base_reverification_arguments: dict[str, object],
    stage3_reverification_arguments: dict[str, object],
    sequence_three_event_reverification_arguments: dict[str, object],
    stage4_reverification_arguments: dict[str, object],
    event_reverification_arguments: dict[str, object],
    checked_at: datetime,
) -> ProductionReviewAuthorizationCustodyExtensionEventVerification:
    """Verify seq4 after rebuilding raw v1 and seq3 evidence from bytes."""

    if (
        type(event_reverification_arguments) is not dict
        or set(event_reverification_arguments)
        != _EXTENSION_SEQUENCE_THREE_EVENT_REVERIFICATION_ARGUMENT_FIELDS
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension sequence-four event arguments are not exact"
        )
    if (
        type(stage4_reverification_arguments) is not dict
        or set(stage4_reverification_arguments)
        != _EXTENSION_STAGE4_REVERIFICATION_ARGUMENT_FIELDS
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension stage4 reverification arguments are not exact"
        )
    if (
        type(base_reverification_arguments) is not dict
        or set(base_reverification_arguments)
        != _BASE_SEQUENCE_TWO_REVERIFICATION_ARGUMENT_FIELDS
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "base sequence-two reverification arguments are not exact"
        )
    custody_trust = _exact_custody_trust_map(
        base_reverification_arguments["trusted_custody_keys"]
    )
    (
        payload,
        event_sha256,
        raw_event_sha256,
        from_anchor,
        to_anchor,
        from_public_key_sha256,
        to_public_key_sha256,
    ) = _verify_extension_event_signatures(
        source,
        trusted_custody_keys=custody_trust,
    )
    if event_sha256 != _require_sha256(
        event_reverification_arguments["expected_custody_event_sha256"],
        name="expected extension sequence-four event",
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension sequence-four event is cross-wired to its identity"
        )
    if (
        payload.get("schema_id")
        != PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_EVENT_SCHEMA_ID
        or payload.get("contract_sha256")
        != FROZEN_VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256
        or payload.get("base_custody_contract_sha256")
        != FROZEN_VALIDATION_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_SHA256
        or payload.get("artifact_stage") != "authorization"
        or payload.get("custody_sequence") != 4
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension sequence-four schema, contract, stage, or sequence is cross-wired"
        )
    checked = _parse_utc(
        _format_utc(checked_at, name="extension sequence-four checked_at"),
        name="extension sequence-four checked_at",
    )
    handed_off = _parse_utc(
        payload.get("handed_off_at_utc"),
        name="extension sequence-four handed_off_at",
    )
    received = _parse_utc(
        payload.get("received_at_utc"),
        name="extension sequence-four received_at",
    )
    if checked < received:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension sequence-four event is not yet valid"
        )
    sequence_three = (
        verify_signed_production_pre_execution_review_custody_extension_event(
            raw_sequence_three_custody_event_bytes,
            raw_pre_execution_review_carrier_bytes=(
                raw_pre_execution_review_carrier_bytes
            ),
            raw_review_attestation_bytes=raw_review_attestation_bytes,
            raw_permit_bytes=raw_permit_bytes,
            raw_status_lineage_bytes=raw_status_lineage_bytes,
            raw_sequence_one_custody_event_bytes=(raw_sequence_one_custody_event_bytes),
            raw_sequence_two_custody_event_bytes=(raw_sequence_two_custody_event_bytes),
            expected_run_context=expected_run_context,
            base_reverification_arguments=base_reverification_arguments,
            stage3_reverification_arguments=stage3_reverification_arguments,
            event_reverification_arguments=(
                sequence_three_event_reverification_arguments
            ),
            checked_at=checked,
        )
    )
    base_prefix = _reverify_base_sequence_two_prefix(
        raw_permit_bytes=raw_permit_bytes,
        raw_status_lineage_bytes=raw_status_lineage_bytes,
        raw_sequence_one_custody_event_bytes=raw_sequence_one_custody_event_bytes,
        raw_sequence_two_custody_event_bytes=raw_sequence_two_custody_event_bytes,
        run_context=expected_run_context,
        base_reverification_arguments=base_reverification_arguments,
        checked_at=checked,
    )
    selected_lane = _require_lane(payload.get("lane"))
    if selected_lane != sequence_three.lane or selected_lane != base_prefix.permit.lane:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension sequence-four lane differs from its verified prefix"
        )
    _require_global_extension_trust_separation(
        lane=selected_lane,
        current_status=base_prefix.current_status,
        base_reverification_arguments=base_reverification_arguments,
        stage3_reverification_arguments=stage3_reverification_arguments,
        stage4_reverification_arguments=stage4_reverification_arguments,
    )
    revoked_key_ids, revoked_artifacts, superseded_artifacts = _current_status_denials(
        base_prefix.current_status
    )
    raw_carrier, carrier_document = _canonical_raw_document(
        raw_authorization_carrier_bytes,
        name="raw sequence-four carrier",
    )
    expected_carrier_sha256 = _require_sha256(
        stage4_reverification_arguments["expected_carrier_sha256"],
        name="expected sequence-four carrier",
    )
    if (
        expected_carrier_sha256 != payload.get("carrier_sha256")
        or expected_carrier_sha256 != carrier_document.get("carrier_sha256")
        or payload.get("raw_carrier_sha256") != _raw_sha256(raw_carrier)
        or payload.get("raw_carrier_byte_count") != len(raw_carrier)
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension sequence-four carrier is substituted or cross-wired"
        )
    if (
        type(stage3_reverification_arguments) is not dict
        or set(stage3_reverification_arguments)
        != _EXTENSION_STAGE3_REVERIFICATION_ARGUMENT_FIELDS
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension stage3 reverification arguments are not exact"
        )
    nested_stage3_arguments = {
        "expected_carrier_sha256": stage3_reverification_arguments[
            "expected_carrier_sha256"
        ],
        "expected_prior_custody_event_sha256": (
            base_prefix.sequence_two.custody_event_sha256
        ),
        "upstream_review_verification_arguments": stage3_reverification_arguments[
            "upstream_review_verification_arguments"
        ],
        "trusted_production_reviewer_keys": stage3_reverification_arguments[
            "trusted_production_reviewer_keys"
        ],
        "revoked_production_reviewer_key_ids": tuple(sorted(revoked_key_ids)),
        "revoked_upstream_reviewer_key_ids": tuple(sorted(revoked_key_ids)),
        "revoked_carrier_sha256s": tuple(sorted(revoked_artifacts)),
        "superseded_carrier_sha256s": tuple(sorted(superseded_artifacts)),
        "revoked_upstream_review_sha256s": tuple(sorted(revoked_artifacts)),
        "superseded_upstream_review_sha256s": tuple(sorted(superseded_artifacts)),
    }
    carrier = verify_signed_production_authorization_carrier(
        raw_carrier,
        raw_authorization_receipt_bytes=raw_authorization_receipt_bytes,
        raw_review_attestation_bytes=raw_review_attestation_bytes,
        raw_pre_execution_review_carrier_bytes=(raw_pre_execution_review_carrier_bytes),
        expected_carrier_sha256=expected_carrier_sha256,
        expected_lane=selected_lane,
        expected_run_context=expected_run_context,
        expected_prior_custody_event_sha256=sequence_three.custody_event_sha256,
        upstream_authorization_verification_arguments=stage4_reverification_arguments[
            "upstream_authorization_verification_arguments"
        ],  # type: ignore[arg-type]
        pre_execution_review_reverification_arguments=nested_stage3_arguments,
        trusted_production_authorization_keys=stage4_reverification_arguments[
            "trusted_production_authorization_keys"
        ],  # type: ignore[arg-type]
        checked_at=handed_off,
        revoked_production_authorization_key_ids=tuple(sorted(revoked_key_ids)),
        revoked_upstream_authorization_key_ids=tuple(sorted(revoked_key_ids)),
        revoked_carrier_sha256s=tuple(sorted(revoked_artifacts)),
        superseded_carrier_sha256s=tuple(sorted(superseded_artifacts)),
        revoked_upstream_authorization_sha256s=tuple(sorted(revoked_artifacts)),
        superseded_upstream_authorization_sha256s=tuple(sorted(superseded_artifacts)),
    )
    expected_projection = _extension_event_projection(
        artifact_stage="authorization",
        custody_sequence=4,
        prior_custody_event_sha256=sequence_three.custody_event_sha256,
        raw_carrier_bytes=raw_carrier,
        carrier=carrier,
        run_context=expected_run_context,
        from_role=event_reverification_arguments["expected_from_role"],  # type: ignore[arg-type]
        from_role_identity_sha256=event_reverification_arguments[
            "expected_from_role_identity_sha256"
        ],  # type: ignore[arg-type]
        from_key_id=event_reverification_arguments["expected_from_key_id"],  # type: ignore[arg-type]
        to_role=event_reverification_arguments["expected_to_role"],  # type: ignore[arg-type]
        to_role_identity_sha256=event_reverification_arguments[
            "expected_to_role_identity_sha256"
        ],  # type: ignore[arg-type]
        to_key_id=event_reverification_arguments["expected_to_key_id"],  # type: ignore[arg-type]
        handed_off_at_utc=payload.get("handed_off_at_utc"),  # type: ignore[arg-type]
        received_at_utc=payload.get("received_at_utc"),  # type: ignore[arg-type]
        status_snapshot_sha256=payload.get("status_snapshot_sha256"),  # type: ignore[arg-type]
    )
    if _canonical_bytes(payload) != _canonical_bytes(expected_projection):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension sequence-four event fields are omitted or transplanted"
        )
    _require_claims_closed(payload)
    handoff_status = next(
        (
            status
            for status in base_prefix.status_lineage
            if status.snapshot_sha256 == payload["status_snapshot_sha256"]
        ),
        None,
    )
    if handoff_status is None:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension sequence-four handoff status is not in the verified lineage"
        )
    handoff_status_issued = _parse_utc(
        handoff_status.issued_at_utc,
        name="extension sequence-four handoff status issued_at",
    )
    permit_issued = _parse_utc(
        base_prefix.permit.issued_at_utc,
        name="extension sequence-four permit issued_at",
    )
    permit_expires = _parse_utc(
        base_prefix.permit.expires_at_utc,
        name="extension sequence-four permit expires_at",
    )
    carrier_signed = _parse_utc(
        carrier.signed_at_utc,
        name="extension sequence-four carrier signed_at",
    )
    sequence_three_received = _parse_utc(
        sequence_three.received_at_utc,
        name="extension sequence-three received_at",
    )
    if (
        not handoff_status_issued <= carrier_signed
        or handed_off - handoff_status_issued
        > PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_EVENT_MAX_HANDOFF_DURATION
        or not permit_issued
        <= carrier_signed
        <= handed_off
        <= received
        < permit_expires
        or sequence_three_received > carrier_signed
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension sequence-four prefix or handoff time is invalid"
        )
    if (
        sequence_three.to_role != payload["from_role"]
        or sequence_three.to_role_identity_sha256
        != payload["from_role_identity_sha256"]
        or sequence_three.to_key_id != payload["from_key_id"]
        or sequence_three.to_public_key_sha256 != from_public_key_sha256
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "extension sequence-four predecessor custody continuity failed"
        )
    _require_current_status_allows_identities(
        base_prefix.current_status,
        identities=(
            event_sha256,
            raw_event_sha256,
            carrier.carrier_sha256,
            carrier.raw_carrier_sha256,
            carrier.upstream_authorization_receipt_sha256,
            carrier.upstream_authorization_raw_sha256,
            carrier.upstream_review_attestation_sha256,
            carrier.upstream_review_raw_sha256,
        ),
        name="extension sequence-four prefix",
    )
    return _new_extension_event_verification(
        custody_event_sha256=event_sha256,
        raw_event_sha256=raw_event_sha256,
        raw_event_byte_count=len(source),
        artifact_stage="authorization",
        custody_sequence=4,
        prior_custody_event_sha256=sequence_three.custody_event_sha256,
        carrier_sha256=carrier.carrier_sha256,
        raw_carrier_sha256=carrier.raw_carrier_sha256,
        raw_carrier_byte_count=carrier.raw_carrier_byte_count,
        permit_sha256=carrier.permit_sha256,
        study_id_sha256=carrier.study_id_sha256,
        run_id_sha256=carrier.run_id_sha256,
        authorization_nonce_sha256=carrier.authorization_nonce_sha256,
        lane=selected_lane,
        custodian_identity_sha256=payload["custodian_identity_sha256"],
        enrolled_host_identity_sha256=payload["enrolled_host_identity_sha256"],
        process_launch_identity_sha256=carrier.process_launch_identity_sha256,
        from_role=from_anchor.custody_role,
        from_role_identity_sha256=from_anchor.role_identity_sha256,
        from_key_id=payload["from_key_id"],
        from_public_key_sha256=from_public_key_sha256,
        to_role=to_anchor.custody_role,
        to_role_identity_sha256=to_anchor.role_identity_sha256,
        to_key_id=payload["to_key_id"],
        to_public_key_sha256=to_public_key_sha256,
        handed_off_at_utc=payload["handed_off_at_utc"],
        received_at_utc=payload["received_at_utc"],
        handoff_status_snapshot_sha256=payload["status_snapshot_sha256"],
        current_status_snapshot_sha256=base_prefix.current_status.snapshot_sha256,
        custody_event_lineage_sha256s=(
            *sequence_three.custody_event_lineage_sha256s,
            event_sha256,
        ),
        raw_custody_event_lineage_sha256s=(
            *sequence_three.raw_custody_event_lineage_sha256s,
            raw_event_sha256,
        ),
        carrier_lineage_sha256s=(
            *sequence_three.carrier_lineage_sha256s,
            carrier.carrier_sha256,
        ),
        raw_carrier_lineage_sha256s=(
            *sequence_three.raw_carrier_lineage_sha256s,
            carrier.raw_carrier_sha256,
        ),
        upstream_review_attestation_sha256=(carrier.upstream_review_attestation_sha256),
        upstream_review_raw_sha256=carrier.upstream_review_raw_sha256,
        upstream_authorization_receipt_sha256=(
            carrier.upstream_authorization_receipt_sha256
        ),
        upstream_authorization_raw_sha256=(carrier.upstream_authorization_raw_sha256),
        checked_at_utc=_format_utc(
            checked,
            name="extension sequence-four checked_at",
        ),
    )


def _contract_projection() -> dict[str, Any]:
    return {
        "schema_id": (
            VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SCHEMA_ID
        ),
        "contract_id": (
            VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_ID
        ),
        "contract_version": (
            VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_VERSION
        ),
        "frozen_at_utc": (
            VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_FROZEN_AT_UTC
        ),
        "superseded_contract_sha256": (
            FROZEN_LEGACY_VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256_V2
        ),
        "refreeze_reason": "binds_refrozen_minimization_projection_headroom_review_authorization_chain",
        "purpose": {
            "additive_companion_only": True,
            "base_custody_v1_modified": False,
            "pre_execution_review_carrier_implemented": True,
            "authorization_carrier_implemented": True,
            "custody_extension_event_implemented": True,
            "actual_production_artifact_present": False,
            "execution_gate_opened": False,
            "claim_promotion_allowed": False,
        },
        "bound_contracts": {
            "production_evidence_custody_v1_sha256": (
                FROZEN_VALIDATION_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_SHA256
            ),
            "linux_process_launch_identity_v1_sha256": (
                FROZEN_PROCESS_LAUNCH_IDENTITY_CONTRACT_SHA256
            ),
            "energy_force_upstream_review_sha256": (
                FROZEN_REFERENCE_VALIDATION_REVIEW_CONTRACT_SHA256
            ),
            "minimization_upstream_review_sha256": (
                FROZEN_REFERENCE_MINIMIZATION_VALIDATION_REVIEW_CONTRACT_SHA256
            ),
            "energy_force_upstream_authorization_sha256": (
                FROZEN_REFERENCE_VALIDATION_AUTHORIZATION_CONTRACT_SHA256
            ),
            "minimization_upstream_authorization_sha256": (
                FROZEN_REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_CONTRACT_SHA256
            ),
        },
        "carrier_schemas": {
            "pre_execution_review": PRODUCTION_PRE_EXECUTION_REVIEW_CARRIER_SCHEMA_ID,
            "authorization": PRODUCTION_AUTHORIZATION_CARRIER_SCHEMA_ID,
            "custody_extension_event": (
                PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_EVENT_SCHEMA_ID
            ),
        },
        "pre_execution_review": {
            "stage": "pre_execution_review",
            "future_custody_sequence": 3,
            "signature_algorithm": (
                PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_SIGNATURE_ALGORITHM
            ),
            "raw_upstream_bytes_only": True,
            "raw_upstream_internally_reverified": True,
            "upstream_exact_json_scalar_type_preflight_required": True,
            "caller_verification_dto_trusted": False,
            "exact_run_permit_status_and_predecessor_digest_binding": True,
            "supplied_process_launch_identity_digest_bound": True,
            "process_launch_identity_authenticity_established": False,
            "permit_contract_bundle_must_bind_this_extension": True,
            "carrier_visible_governance_identity_key_id_and_material_separation_required": True,
            "maximum_validity_seconds": int(
                PRODUCTION_PRE_EXECUTION_REVIEW_CARRIER_MAX_VALIDITY.total_seconds()
            ),
            "energy_force_upstream_signature_algorithm": "hmac-sha256",
            "minimization_upstream_signature_algorithm": "ed25519",
            "full_asymmetric_chain_established": False,
        },
        "authorization": {
            "stage": "authorization",
            "future_custody_sequence": 4,
            "signature_algorithm": (
                PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_SIGNATURE_ALGORITHM
            ),
            "raw_pre_execution_review_review_and_authorization_bytes_only": True,
            "raw_ancestor_artifacts_internally_reverified": True,
            "upstream_exact_json_scalar_type_preflight_required": True,
            "caller_verification_dto_trusted": False,
            "exact_run_permit_status_and_predecessor_digest_binding": True,
            "supplied_process_launch_identity_digest_bound": True,
            "process_launch_identity_authenticity_established": False,
            "upstream_environment_result_and_dependency_contracts_bound": True,
            "carrier_visible_governance_identity_key_id_and_material_separation_required": True,
            "maximum_validity_seconds": int(
                PRODUCTION_AUTHORIZATION_CARRIER_MAX_VALIDITY.total_seconds()
            ),
            "eligible_for_atomic_execution_reservation": False,
            "energy_force_upstream_signature_algorithm": "hmac-sha256",
            "minimization_upstream_signature_algorithm": "ed25519",
            "full_asymmetric_chain_established": False,
        },
        "custody_extension_event": {
            "implemented_sequences": [3, 4],
            "implemented_stages": ["pre_execution_review", "authorization"],
            "signature_algorithm": (
                PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_SIGNATURE_ALGORITHM
            ),
            "dual_custody_signatures_required": True,
            "raw_base_sequence_one_and_two_internally_reverified": True,
            "raw_sequence_three_internally_reverified_before_sequence_four": True,
            "base_and_upstream_exact_json_scalar_type_preflight_required": True,
            "base_status_lineage_not_before_permit_required": True,
            "caller_verification_dto_accepted": False,
            "canonical_bytes_only": True,
            "logical_and_raw_revocation_and_supersession_required": True,
            "current_status_descendant_allowed": True,
            "all_trust_map_anchors_globally_separated": True,
            "maximum_handoff_duration_seconds": int(
                PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_EVENT_MAX_HANDOFF_DURATION.total_seconds()
            ),
            "custody_successor_uniqueness_enforced": False,
            "external_append_only_compare_and_set_log_required": True,
            "eligible_for_atomic_execution_reservation": False,
            "full_asymmetric_chain_established": False,
        },
        "custody_scope": {
            "base_verified_stage_sequence": [
                "production_permit",
                "status_snapshot",
            ],
            "implemented_companion_carrier_stages": [
                "pre_execution_review",
                "authorization",
            ],
            "authorization_stage_implemented": True,
            "verified_custody_sequence": [
                "production_permit",
                "status_snapshot",
                "pre_execution_review",
                "authorization",
            ],
            "custody_extension_events_implemented": True,
            "custody_successor_uniqueness_enforced": False,
            "external_append_only_compare_and_set_log_required": True,
        },
        "resource_limits": {
            "signed_transport_max_bytes": (
                PRODUCTION_REVIEW_AUTHORIZATION_MAX_SIGNED_TRANSPORT_BYTES
            ),
            "raw_upstream_max_bytes": (
                PRODUCTION_REVIEW_AUTHORIZATION_MAX_RAW_UPSTREAM_BYTES
            ),
            "trust_anchor_max_items": (
                PRODUCTION_REVIEW_AUTHORIZATION_MAX_TRUST_ANCHORS
            ),
            "contract_bundle_max_rows": (
                PRODUCTION_REVIEW_AUTHORIZATION_MAX_CONTRACT_ROWS
            ),
            "argv_max_items": PRODUCTION_REVIEW_AUTHORIZATION_MAX_ARGV_ITEMS,
            "argv_item_max_bytes": (
                PRODUCTION_REVIEW_AUTHORIZATION_MAX_ARGV_ITEM_BYTES
            ),
            "argv_total_max_bytes": (
                PRODUCTION_REVIEW_AUTHORIZATION_MAX_ARGV_TOTAL_BYTES
            ),
            "external_sequence_max_items": (
                PRODUCTION_REVIEW_AUTHORIZATION_MAX_EXTERNAL_SEQUENCE_ITEMS
            ),
            "external_sequence_max_total_bytes": (
                PRODUCTION_REVIEW_AUTHORIZATION_MAX_EXTERNAL_SEQUENCE_TOTAL_BYTES
            ),
            "energy_hmac_key_max_bytes": (
                PRODUCTION_REVIEW_AUTHORIZATION_MAX_HMAC_KEY_BYTES
            ),
            "energy_hmac_key_total_max_bytes": (
                PRODUCTION_REVIEW_AUTHORIZATION_MAX_HMAC_KEY_TOTAL_BYTES
            ),
            "json_maximum_nesting_depth": (
                PRODUCTION_REVIEW_AUTHORIZATION_MAX_JSON_DEPTH
            ),
            "mapping_arguments_exact_builtin_dict_required": True,
            "raw_size_checked_before_json_materialization": True,
            "json_nesting_checked_before_json_materialization": True,
            "status_lineage_max_items": (
                PRODUCTION_REVIEW_AUTHORIZATION_MAX_STATUS_LINEAGE_ITEMS
            ),
            "status_lineage_total_max_bytes": (
                PRODUCTION_REVIEW_AUTHORIZATION_MAX_STATUS_LINEAGE_TOTAL_BYTES
            ),
            "ancestor_exact_json_integer_field_allowlists": {
                "base_permit": sorted(_BASE_PERMIT_INTEGER_FIELDS),
                "base_status": sorted(_BASE_STATUS_INTEGER_FIELDS),
                "base_custody_event": sorted(_BASE_CUSTODY_EVENT_INTEGER_FIELDS),
                "upstream_review": [],
                "upstream_authorization": sorted(
                    _UPSTREAM_AUTHORIZATION_INTEGER_FIELDS
                ),
            },
        },
        "claim_policy": dict(_CLAIM_POLICY),
        "blockers": list(_BLOCKERS),
    }


def validation_production_review_authorization_custody_extension_contract_document() -> (
    dict[str, Any]
):
    projection = _contract_projection()
    observed = _sha256(projection)
    if observed != (
        FROZEN_VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256
    ):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "frozen production review/authorization custody extension hash drifted"
        )
    return {**projection, "contract_sha256": observed}


def require_validation_production_review_authorization_custody_extension_contract_document(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    if type(value) is not dict:
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "custody extension contract must be an exact built-in dict"
        )
    expected = (
        validation_production_review_authorization_custody_extension_contract_document()
    )
    if _canonical_bytes(value) != _canonical_bytes(expected):
        raise ValidationProductionReviewAuthorizationCustodyExtensionError(
            "custody extension contract does not match the frozen record"
        )
    return expected


def validation_production_review_authorization_custody_extension_decision() -> dict[
    str, Any
]:
    contract = (
        validation_production_review_authorization_custody_extension_contract_document()
    )
    return {
        "contract_sha256": contract["contract_sha256"],
        "pre_execution_review_carrier_implemented": True,
        "authorization_carrier_implemented": True,
        "custody_extension_event_implemented": True,
        "base_custody_v1_modified": False,
        "full_asymmetric_chain_established": False,
        "energy_force_upstream_symmetric_hmac_chain": True,
        "custody_successor_uniqueness_enforced": False,
        "actual_production_artifact_present": False,
        "production_validation_execution_authorized": False,
        "production_validation_results_collected": False,
        "scientifically_validated": False,
        "parameter_fitting_authorized": False,
        "product_qualified": False,
        "claim_safe": False,
        "blockers": list(_BLOCKERS),
    }


__all__ = [
    "FROZEN_LEGACY_VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256_V2",
    "FROZEN_LEGACY_VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256_V1",
    "FROZEN_VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256",
    "PRODUCTION_AUTHORIZATION_CARRIER_SCHEMA_ID",
    "PRODUCTION_AUTHORIZATION_CARRIER_MAX_VALIDITY",
    "PRODUCTION_PRE_EXECUTION_REVIEW_CARRIER_MAX_VALIDITY",
    "PRODUCTION_PRE_EXECUTION_REVIEW_CARRIER_SCHEMA_ID",
    "PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_EVENT_SCHEMA_ID",
    "PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_EVENT_MAX_HANDOFF_DURATION",
    "PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_LANES",
    "PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_SIGNATURE_ALGORITHM",
    "ProductionAuthorizationCarrierTrustAnchor",
    "ProductionAuthorizationCarrierVerification",
    "ProductionPreExecutionReviewCarrierVerification",
    "ProductionReviewAuthorizationCustodyExtensionEventVerification",
    "ProductionReviewCarrierTrustAnchor",
    "VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_ID",
    "VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SCHEMA_ID",
    "VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_VERSION",
    "ValidationProductionReviewAuthorizationCustodyExtensionError",
    "build_signed_production_authorization_carrier",
    "build_signed_production_authorization_custody_extension_event",
    "build_signed_production_pre_execution_review_carrier",
    "build_signed_production_pre_execution_review_custody_extension_event",
    "require_validation_production_review_authorization_custody_extension_contract_document",
    "validation_production_review_authorization_custody_extension_contract_document",
    "validation_production_review_authorization_custody_extension_decision",
    "verify_signed_production_authorization_carrier",
    "verify_signed_production_authorization_custody_extension_event",
    "verify_signed_production_pre_execution_review_carrier",
    "verify_signed_production_pre_execution_review_custody_extension_event",
]
