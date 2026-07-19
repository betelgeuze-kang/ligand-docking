"""Verify an authenticated external registry-head and status-tail receipt.

The reservation-registry proof verifier deliberately treats its caller-supplied
expected head as an equality input.  This companion freshly re-verifies that raw
proof, then verifies a distinct external receipt-authority signature binding the
exact registry checkpoint, the supplied and reverified status-lineage tail, and
a caller challenge.  Verification also requires a separately snapshotted,
reverified strict status descendant issued strictly after the receipt, so
post-receipt revocation and supersession rows are applied.  It authenticates
that bounded receipt only; it does not
prove a globally latest head, compare-and-set, one-use consumption,
non-equivocation, later-head consistency, or epoch-transition continuity.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from typing import Any, Mapping

from betelgeuze_engine_v2.physics.reference_minimization_validation_ed25519 import (
    ReferenceMinimizationValidationEd25519Error,
    verify_ed25519,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_authorization import (
    MinimizationAuthorizationOperatorTrustAnchor,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_review import (
    MinimizationScientificReviewerTrustAnchor,
)
from betelgeuze_engine_v2.physics.reference_validation_authorization import (
    AuthorizationOperatorTrustAnchor,
)
from betelgeuze_engine_v2.physics.reference_validation_review import (
    ScientificReviewerTrustAnchor,
)
from betelgeuze_engine_v2.physics.validation_production_evidence_custody import (
    CustodyRoleTrustAnchor,
    EvidenceAuthorityTrustAnchor,
)
from betelgeuze_engine_v2.physics.validation_production_reservation_custody_extension import (
    PRODUCTION_RESERVATION_MAX_SIGNED_TRANSPORT_BYTES,
    ProductionReservationRegistryTrustAnchor,
    ProductionReservationWitnessTrustAnchor,
)
from betelgeuze_engine_v2.physics.validation_production_reservation_registry_proof import (
    ProductionReservationRegistryTransactionProofVerification,
    ProductionReservationRegistryBackendTrustAnchor,
    ProductionReservationRegistryHeadObserverTrustAnchor,
    ValidationProductionReservationRegistryProofError,
    verify_external_production_reservation_registry_transaction_proof,
)
from betelgeuze_engine_v2.physics.validation_production_review_authorization_custody_extension import (
    ProductionAuthorizationCarrierTrustAnchor,
    ProductionReviewCarrierTrustAnchor,
)


VALIDATION_PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_CONTRACT_SCHEMA_ID = (
    "betelgeuze.engine_v2_validation_production_reservation_authenticated_head_receipt_contract/1.0.0"
)
VALIDATION_PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_CONTRACT_ID = (
    "engine_v2_validation_production_reservation_authenticated_head_receipt/1.0.0"
)
VALIDATION_PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_CONTRACT_VERSION = (
    "1.0.0"
)
VALIDATION_PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_FROZEN_AT_UTC = (
    "2026-07-19T18:20:00Z"
)
PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_external_reservation_authenticated_head_receipt/1.0.0"
)
PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_MAX_BYTES = 1024 * 1024
PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_MAX_TRUST_ANCHORS = 16
PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_MAX_SNAPSHOT_NODES = 100_000
PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_MAX_SNAPSHOT_DEPTH = 64
PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_MAX_AGE = timedelta(minutes=15)
PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_MAX_VALIDITY = timedelta(
    minutes=15
)
FROZEN_VALIDATION_PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_CONTRACT_SHA256 = (
    "0e9ddbab2978ad679eb040faebaa49524d08a59a939d22e7f38029d2fc4b1639"
)

_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_UTC = timezone.utc
_VERIFICATION_SEAL = object()
_ALLOWED_REVERIFICATION_DATACLASS_TYPES = (
    AuthorizationOperatorTrustAnchor,
    CustodyRoleTrustAnchor,
    EvidenceAuthorityTrustAnchor,
    MinimizationAuthorizationOperatorTrustAnchor,
    MinimizationScientificReviewerTrustAnchor,
    ProductionAuthorizationCarrierTrustAnchor,
    ProductionReservationRegistryBackendTrustAnchor,
    ProductionReservationRegistryHeadObserverTrustAnchor,
    ProductionReservationRegistryTrustAnchor,
    ProductionReservationWitnessTrustAnchor,
    ProductionReviewCarrierTrustAnchor,
    ScientificReviewerTrustAnchor,
)
_REGISTRY_PROOF_REVERIFICATION_FIELDS = {
    "source",
    "sequence_five_reverification_arguments",
    "expected_proof_sha256",
    "expected_raw_proof_sha256",
    "expected_prior_native_registry_checkpoint_sha256",
    "expected_caller_registry_sequence",
    "expected_caller_native_registry_checkpoint_sha256",
    "trusted_registry_backend_keys",
    "trusted_registry_head_observer_keys",
}
_CLAIM_POLICY = {
    "production_validation_execution_authorized": False,
    "production_validation_results_collected": False,
    "scientifically_validated": False,
    "parameter_fitting_authorized": False,
    "product_qualified": False,
    "claim_safe": False,
}
_ACTUAL_FACT_POLICY = {
    "caller_challenge_freshness_verified": False,
    "caller_challenge_one_use_verified": False,
    "global_latest_registry_head_verified": False,
    "global_latest_status_head_verified": False,
    "external_serializable_registry_commit_verified": False,
    "registry_head_compare_and_set_committed": False,
    "status_head_compare_and_set_committed": False,
    "permit_one_use_slot_consumed": False,
    "authorization_nonce_slot_consumed": False,
    "predecessor_successor_slot_consumed": False,
    "custody_successor_uniqueness_enforced": False,
    "external_registry_non_equivocation_verified": False,
    "later_head_consistency_verified": False,
    "registry_epoch_transition_continuity_verified": False,
}
_BLOCKERS = (
    "authenticated_external_head_status_receipt_not_provisioned",
    "trusted_external_head_receipt_authority_key_not_provisioned",
    "caller_head_receipt_challenge_not_provisioned",
    "caller_challenge_freshness_and_one_use_not_independently_verified",
    "post_receipt_current_status_descendant_not_provisioned",
    "global_latest_registry_head_not_independently_verified",
    "global_latest_status_head_not_independently_verified",
    "status_head_compare_and_set_not_independently_verified",
    "external_registry_non_equivocation_proof_not_provisioned",
    "later_head_consistency_proof_not_provisioned",
    "registry_epoch_transition_continuity_not_provisioned",
    "external_custody_successor_uniqueness_not_provisioned",
    "production_environment_and_later_custody_not_provisioned",
    "production_validation_results_not_collected",
    "two_cpu_hosts_missing",
    "independent_human_result_review_missing",
)


class ValidationProductionReservationAuthenticatedHeadReceiptError(ValueError):
    """The external authenticated head/status receipt is invalid."""


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
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            "authenticated head receipt value is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _raw_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    if type(value) is not str or not _SHA256_RE.fullmatch(value):
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            f"{name} must be an exact lowercase SHA-256"
        )
    return value


def _require_token(value: object, *, name: str) -> str:
    if type(value) is not str or not _TOKEN_RE.fullmatch(value):
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            f"{name} must be an exact bounded token"
        )
    return value


def _require_exact_int(
    value: object,
    *,
    name: str,
    minimum: int = 0,
    maximum: int = 2**63 - 1,
) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            f"{name} must be an exact bounded integer"
        )
    return value


def _parse_utc(value: object, *, name: str) -> datetime:
    if type(value) is not str or not value.endswith("Z"):
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            f"{name} must be canonical UTC"
        )
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_UTC)
    except ValueError as exc:
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            f"{name} must be canonical UTC"
        ) from exc


def _format_utc(value: datetime, *, name: str) -> str:
    if type(value) is not datetime or value.tzinfo is None:
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            f"{name} must be timezone-aware"
        )
    normalized = value.astimezone(_UTC)
    if normalized.microsecond:
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            f"{name} must have whole-second precision"
        )
    return normalized.strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_canonical_document(
    source: bytes,
    *,
    maximum_bytes: int,
    artifact_name: str,
) -> tuple[bytes, dict[str, Any]]:
    if type(source) is not bytes or not source:
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            f"raw {artifact_name} must be exact non-empty bytes"
        )
    if len(source) > maximum_bytes:
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            f"raw {artifact_name} exceeds its transport bound"
        )

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValidationProductionReservationAuthenticatedHeadReceiptError(
                    f"{artifact_name} contains a duplicate JSON key"
                )
            result[key] = value
        return result

    try:
        loaded = json.loads(source.decode("ascii"), object_pairs_hook=reject_duplicates)
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        RecursionError,
        ValidationProductionReservationAuthenticatedHeadReceiptError,
    ) as exc:
        if isinstance(
            exc, ValidationProductionReservationAuthenticatedHeadReceiptError
        ):
            raise
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            f"{artifact_name} is not canonical ASCII JSON"
        ) from exc
    if type(loaded) is not dict or _canonical_bytes(loaded) != source:
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            f"{artifact_name} is not canonical ASCII JSON"
        )
    return source, loaded


def _signature(value: object) -> dict[str, str]:
    if type(value) is not dict or set(value) != {"algorithm", "key_id", "value"}:
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            "head receipt authority signature fields are invalid"
        )
    if value["algorithm"] != "Ed25519" or type(value["value"]) is not str:
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            "head receipt authority signature is invalid"
        )
    return {
        "algorithm": "Ed25519",
        "key_id": _require_token(value["key_id"], name="head receipt authority key id"),
        "value": value["value"],
    }


@dataclass(frozen=True, slots=True)
class ProductionReservationHeadReceiptAuthorityTrustAnchor:
    authority_identity_sha256: str
    registry_realm_identity_sha256: str
    registry_epoch: str
    service_binary_sha256: str
    service_schema_sha256: str
    service_configuration_sha256: str
    service_deployment_sha256: str
    valid_from_utc: str
    valid_until_utc: str
    verification_key: bytes


def _require_key(value: object) -> bytes:
    if type(value) is not bytes or len(value) != 32:
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            "head receipt authority public key must be exactly 32 bytes"
        )
    return value


def _trust_map(
    value: object,
) -> dict[str, ProductionReservationHeadReceiptAuthorityTrustAnchor]:
    if (
        type(value) is not dict
        or not value
        or len(value)
        > PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_MAX_TRUST_ANCHORS
    ):
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            "head receipt authority trust map is invalid"
        )
    result: dict[str, ProductionReservationHeadReceiptAuthorityTrustAnchor] = {}
    identities: set[str] = set()
    materials: set[bytes] = set()
    for raw_key_id, anchor in value.items():
        key_id = _require_token(raw_key_id, name="head receipt authority key id")
        if type(anchor) is not ProductionReservationHeadReceiptAuthorityTrustAnchor:
            raise ValidationProductionReservationAuthenticatedHeadReceiptError(
                "head receipt authority trust map contains an invalid anchor"
            )
        identity = _require_sha256(
            anchor.authority_identity_sha256,
            name="head receipt authority identity",
        )
        material = _require_key(anchor.verification_key)
        if identity in identities or material in materials:
            raise ValidationProductionReservationAuthenticatedHeadReceiptError(
                "head receipt authority trust map contains an alias"
            )
        for name, digest in (
            ("head receipt realm", anchor.registry_realm_identity_sha256),
            ("head receipt service binary", anchor.service_binary_sha256),
            ("head receipt service schema", anchor.service_schema_sha256),
            ("head receipt service configuration", anchor.service_configuration_sha256),
            ("head receipt service deployment", anchor.service_deployment_sha256),
        ):
            _require_sha256(digest, name=name)
        _require_token(anchor.registry_epoch, name="head receipt epoch")
        valid_from = _parse_utc(anchor.valid_from_utc, name="authority valid_from")
        valid_until = _parse_utc(anchor.valid_until_utc, name="authority valid_until")
        if valid_from >= valid_until:
            raise ValidationProductionReservationAuthenticatedHeadReceiptError(
                "head receipt authority trust validity window is invalid"
            )
        identities.add(identity)
        materials.add(material)
        result[key_id] = anchor
    return result


def _collect_prior_trust_aliases(
    value: object,
) -> tuple[set[str], set[str], set[bytes]]:
    key_ids: set[str] = set()
    identities: set[str] = set()
    materials: set[bytes] = set()
    seen: set[int] = set()
    visited = 0

    def visit(current: object, *, field_name: str = "") -> None:
        nonlocal visited
        visited += 1
        if visited > 100_000:
            raise ValidationProductionReservationAuthenticatedHeadReceiptError(
                "registry proof trust graph exceeds its traversal bound"
            )
        if type(current) is bytes:
            if len(current) == 32:
                materials.add(current)
            return
        if type(current) is str:
            denial_field = any(
                marker in field_name
                for marker in ("revoked", "superseded", "denial")
            )
            if (
                not denial_field
                and "identity_sha256" in field_name
                and _SHA256_RE.fullmatch(current)
            ):
                identities.add(current)
            if (
                not denial_field
                and "key_id" in field_name
                and _TOKEN_RE.fullmatch(current)
            ):
                key_ids.add(current)
            return
        if current is None or type(current) in (bool, int, float):
            return
        identity = id(current)
        if identity in seen:
            return
        seen.add(identity)
        if type(current) is dict:
            trusted_key_map = "trusted" in field_name and "key" in field_name
            for key, child in current.items():
                if trusted_key_map and type(key) is str and _TOKEN_RE.fullmatch(key):
                    key_ids.add(key)
                visit(child, field_name=key if type(key) is str else "")
            return
        if type(current) in (list, tuple):
            for child in current:
                visit(child, field_name=field_name)
            return
        if is_dataclass(current):
            for descriptor in fields(current):
                visit(getattr(current, descriptor.name), field_name=descriptor.name)

    try:
        visit(value, field_name="registry_proof_reverification_arguments")
    except RecursionError as exc:
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            "registry proof trust graph is too deeply nested"
        ) from exc
    return key_ids, identities, materials


def _reverify_registry_proof(
    arguments: object,
    *,
    checked_at: datetime,
) -> ProductionReservationRegistryTransactionProofVerification:
    if (
        type(arguments) is not dict
        or set(arguments) != _REGISTRY_PROOF_REVERIFICATION_FIELDS
    ):
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            "registry proof reverification arguments are omitted or aliased"
        )
    try:
        return verify_external_production_reservation_registry_transaction_proof(
            **arguments,  # type: ignore[arg-type]
            checked_at=checked_at,
        )
    except ValidationProductionReservationRegistryProofError as exc:
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            "reservation registry transaction proof reverification failed"
        ) from exc


def _snapshot_registry_proof_reverification_arguments(
    arguments: object,
) -> dict[str, object]:
    if (
        type(arguments) is not dict
        or set(arguments) != _REGISTRY_PROOF_REVERIFICATION_FIELDS
    ):
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            "registry proof reverification arguments are omitted or aliased"
        )
    memo: dict[int, object] = {}
    active: set[int] = set()
    visited = 0

    def clone(current: object, *, depth: int) -> object:
        nonlocal visited
        visited += 1
        if (
            visited
            > PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_MAX_SNAPSHOT_NODES
            or depth
            > PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_MAX_SNAPSHOT_DEPTH
        ):
            raise ValidationProductionReservationAuthenticatedHeadReceiptError(
                "registry proof reverification argument graph exceeds its snapshot bound"
            )
        if current is None or type(current) in (bool, int, float, str, bytes):
            return current
        identity = id(current)
        if identity in active:
            raise ValidationProductionReservationAuthenticatedHeadReceiptError(
                "registry proof reverification argument graph is cyclic"
            )
        if identity in memo:
            return memo[identity]
        current_type = type(current)
        active.add(identity)
        try:
            if current_type is dict:
                if len(current) > (
                    PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_MAX_SNAPSHOT_NODES
                ):
                    raise ValidationProductionReservationAuthenticatedHeadReceiptError(
                        "registry proof reverification mapping exceeds its snapshot bound"
                    )
                result: dict[str, object] = {}
                memo[identity] = result
                for key, child in tuple(current.items()):
                    if type(key) is not str:
                        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
                            "registry proof reverification mapping key is invalid"
                        )
                    result[key] = clone(child, depth=depth + 1)
                return result
            if current_type is list:
                if len(current) > (
                    PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_MAX_SNAPSHOT_NODES
                ):
                    raise ValidationProductionReservationAuthenticatedHeadReceiptError(
                        "registry proof reverification list exceeds its snapshot bound"
                    )
                list_result: list[object] = []
                memo[identity] = list_result
                list_result.extend(
                    clone(child, depth=depth + 1) for child in tuple(current)
                )
                return list_result
            if current_type is tuple:
                if len(current) > (
                    PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_MAX_SNAPSHOT_NODES
                ):
                    raise ValidationProductionReservationAuthenticatedHeadReceiptError(
                        "registry proof reverification tuple exceeds its snapshot bound"
                    )
                tuple_result = tuple(
                    clone(child, depth=depth + 1) for child in current
                )
                memo[identity] = tuple_result
                return tuple_result
            if current_type in _ALLOWED_REVERIFICATION_DATACLASS_TYPES and is_dataclass(
                current
            ):
                descriptors = fields(current)
                if any(not descriptor.init for descriptor in descriptors):
                    raise ValidationProductionReservationAuthenticatedHeadReceiptError(
                        "registry proof reverification trust anchor is not snapshot-safe"
                    )
                values = {
                    descriptor.name: clone(
                        getattr(current, descriptor.name),
                        depth=depth + 1,
                    )
                    for descriptor in descriptors
                }
                dataclass_result = current_type(**values)
                memo[identity] = dataclass_result
                return dataclass_result
            raise ValidationProductionReservationAuthenticatedHeadReceiptError(
                "registry proof reverification graph contains an unsupported value"
            )
        finally:
            active.discard(identity)

    try:
        snapshot = clone(arguments, depth=0)
    except ValidationProductionReservationAuthenticatedHeadReceiptError:
        raise
    except (IndexError, KeyError, TypeError, ValueError, RuntimeError, RecursionError) as exc:
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            "registry proof reverification arguments cannot be snapshotted"
        ) from exc
    if (
        type(snapshot) is not dict
        or set(snapshot) != _REGISTRY_PROOF_REVERIFICATION_FIELDS
    ):
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            "registry proof reverification argument snapshot is invalid"
        )
    return snapshot


def _status_lineage(
    registry_proof_reverification_arguments: dict[str, object],
) -> tuple[bytes, ...]:
    seq5 = registry_proof_reverification_arguments.get(
        "sequence_five_reverification_arguments"
    )
    if type(seq5) is not dict:
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            "sequence-five reverification arguments are unavailable"
        )
    prefix = seq5.get("current_raw_sequence_four_prefix")
    if type(prefix) is not dict:
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            "supplied status lineage is unavailable"
        )
    lineage = prefix.get("raw_status_lineage_bytes")
    if (
        type(lineage) not in (list, tuple)
        or not lineage
        or any(type(item) is not bytes or not item for item in lineage)
    ):
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            "supplied status lineage tail is unavailable"
        )
    return tuple(lineage)


def _require_same_sequence_four_trust_domain(
    bound_seq5: dict[str, object],
    current_seq5: dict[str, object],
) -> None:
    bound_arguments = bound_seq5.get(
        "current_sequence_four_reverification_arguments"
    )
    current_arguments = current_seq5.get(
        "current_sequence_four_reverification_arguments"
    )
    if (
        type(bound_arguments) is not dict
        or type(current_arguments) is not dict
        or set(bound_arguments) != set(current_arguments)
        or any(
            bound_arguments[name] != current_arguments[name]
            for name in bound_arguments
            if name != "base_reverification_arguments"
        )
    ):
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            "current sequence-four reverification trust domain differs"
        )
    bound_base = bound_arguments.get("base_reverification_arguments")
    current_base = current_arguments.get("base_reverification_arguments")
    status_derived_fields = {
        "expected_current_status_checkpoint_sha256",
        "expected_current_status_snapshot_sha256",
        "permit_verification_arguments",
        "revoked_authority_key_ids",
    }
    if (
        type(bound_base) is not dict
        or type(current_base) is not dict
        or set(bound_base) != set(current_base)
        or any(
            bound_base[name] != current_base[name]
            for name in bound_base
            if name not in status_derived_fields
        )
    ):
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            "current sequence-four reverification trust domain differs"
        )
    bound_permit = bound_base.get("permit_verification_arguments")
    current_permit = current_base.get("permit_verification_arguments")
    if (
        type(bound_permit) is not dict
        or type(current_permit) is not dict
        or set(bound_permit) != set(current_permit)
        or any(
            bound_permit[name] != current_permit[name]
            for name in bound_permit
            if name != "revoked_authority_key_ids"
        )
        or bound_permit.get("revoked_authority_key_ids")
        != bound_base.get("revoked_authority_key_ids")
        or current_permit.get("revoked_authority_key_ids")
        != current_base.get("revoked_authority_key_ids")
    ):
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            "current sequence-four reverification trust domain differs"
        )


def _require_post_receipt_status_descendant(
    bound_arguments: dict[str, object],
    current_arguments: dict[str, object],
) -> None:
    if any(
        bound_arguments[name] != current_arguments[name]
        for name in _REGISTRY_PROOF_REVERIFICATION_FIELDS
        if name != "sequence_five_reverification_arguments"
    ):
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            "current registry proof inputs differ outside status reverification"
        )
    bound_seq5 = bound_arguments["sequence_five_reverification_arguments"]
    current_seq5 = current_arguments["sequence_five_reverification_arguments"]
    if type(bound_seq5) is not dict or type(current_seq5) is not dict:
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            "sequence-five status reverification inputs are unavailable"
        )
    if set(bound_seq5) != set(current_seq5) or any(
        bound_seq5[name] != current_seq5[name]
        for name in bound_seq5
        if name
        not in {
            "current_raw_sequence_four_prefix",
            "current_sequence_four_reverification_arguments",
        }
    ):
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            "current sequence-five inputs differ outside status reverification"
        )
    _require_same_sequence_four_trust_domain(bound_seq5, current_seq5)
    bound_prefix = bound_seq5.get("current_raw_sequence_four_prefix")
    current_prefix = current_seq5.get("current_raw_sequence_four_prefix")
    if (
        type(bound_prefix) is not dict
        or type(current_prefix) is not dict
        or set(bound_prefix) != set(current_prefix)
        or any(
            bound_prefix[name] != current_prefix[name]
            for name in bound_prefix
            if name != "raw_status_lineage_bytes"
        )
    ):
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            "current sequence-four prefix differs outside status lineage"
        )
    bound_lineage = _status_lineage(bound_arguments)
    current_lineage = _status_lineage(current_arguments)
    if (
        len(current_lineage) <= len(bound_lineage)
        or current_lineage[: len(bound_lineage)] != bound_lineage
    ):
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            "current status lineage is not a strict descendant of the receipt-bound tail"
        )


def _status_tail(
    registry_proof_reverification_arguments: dict[str, object],
) -> tuple[dict[str, Any], bytes, set[str], set[str], set[str]]:
    raw = _status_lineage(registry_proof_reverification_arguments)[-1]
    _raw, status = _load_canonical_document(
        raw,
        maximum_bytes=PRODUCTION_RESERVATION_MAX_SIGNED_TRANSPORT_BYTES,
        artifact_name="supplied status lineage tail",
    )
    revoked_key_rows = status.get("revoked_key_rows")
    revoked_artifact_rows = status.get("revoked_artifact_rows")
    supersession_rows = status.get("supersession_rows")
    if not all(
        type(rows) is list
        for rows in (
            revoked_key_rows,
            revoked_artifact_rows,
            supersession_rows,
        )
    ):
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            "supplied status lineage-tail denial rows are unavailable"
        )
    revoked_key_pairs: set[tuple[str, str]] = set()
    for row in revoked_key_rows:
        if type(row) is not dict:
            raise ValidationProductionReservationAuthenticatedHeadReceiptError(
                "supplied status lineage-tail denial rows are invalid"
            )
        revoked_key_pairs.add(
            (
                _require_token(row.get("role"), name="revoked key role"),
                _require_token(row.get("key_id"), name="revoked key id"),
            )
        )
    revoked_artifact_pairs: set[tuple[str, str]] = set()
    for row in revoked_artifact_rows:
        if type(row) is not dict:
            raise ValidationProductionReservationAuthenticatedHeadReceiptError(
                "supplied status lineage-tail denial rows are invalid"
            )
        revoked_artifact_pairs.add(
            (
                _require_token(
                    row.get("artifact_kind"),
                    name="revoked artifact kind",
                ),
                _require_sha256(
                    row.get("artifact_sha256"),
                    name="revoked artifact",
                ),
            )
        )
    supersession_pairs: set[tuple[str, str]] = set()
    for row in supersession_rows:
        if type(row) is not dict:
            raise ValidationProductionReservationAuthenticatedHeadReceiptError(
                "supplied status lineage-tail denial rows are invalid"
            )
        supersession_pairs.add(
            (
                _require_token(
                    row.get("artifact_kind"),
                    name="superseded artifact kind",
                ),
                _require_sha256(
                    row.get("superseded_sha256"),
                    name="superseded artifact",
                ),
            )
        )
    if (
        len(revoked_key_pairs) != len(revoked_key_rows)
        or len(revoked_artifact_pairs) != len(revoked_artifact_rows)
        or len(supersession_pairs) != len(supersession_rows)
    ):
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            "supplied status lineage-tail denial rows are duplicated"
        )
    return (
        status,
        raw,
        {key_id for _role, key_id in revoked_key_pairs},
        {digest for _kind, digest in revoked_artifact_pairs},
        {digest for _kind, digest in supersession_pairs},
    )


@dataclass(frozen=True, slots=True, init=False)
class ProductionReservationAuthenticatedHeadReceiptVerification:
    head_receipt_sha256: str
    raw_head_receipt_sha256: str
    raw_head_receipt_byte_count: int
    lane: str
    registry_proof_sha256: str
    raw_registry_proof_sha256: str
    sequence_five_commit_sha256: str
    raw_sequence_five_commit_sha256: str
    registry_transaction_sha256: str
    registry_realm_identity_sha256: str
    registry_epoch: str
    registry_sequence: int
    native_registry_checkpoint_sha256: str
    registry_state_root_sha256: str
    status_tail_snapshot_sha256: str
    raw_status_tail_sha256: str
    status_tail_sequence: int
    status_tail_external_log_checkpoint_sha256: str
    current_status_tail_snapshot_sha256: str
    current_raw_status_tail_sha256: str
    current_status_tail_sequence: int
    current_status_tail_external_log_checkpoint_sha256: str
    current_status_tail_issued_at_utc: str
    authority_identity_sha256: str
    authority_key_id: str
    authority_public_key_sha256: str
    request_challenge_nonce_sha256: str
    requested_at_utc: str
    head_observed_at_utc: str
    receipt_issued_at_utc: str
    expires_at_utc: str
    registry_transaction_proof_reverified: bool = True
    receipt_authority_signature_verified: bool = True
    caller_challenge_match_verified: bool = True
    exact_registry_head_and_status_tail_bound: bool = True
    post_receipt_current_status_descendant_reverified: bool = True
    authenticated_external_head_status_receipt_verified: bool = True
    caller_challenge_freshness_verified: bool = False
    caller_challenge_one_use_verified: bool = False
    global_latest_registry_head_verified: bool = False
    global_latest_status_head_verified: bool = False
    external_serializable_registry_commit_verified: bool = False
    registry_head_compare_and_set_committed: bool = False
    status_head_compare_and_set_committed: bool = False
    permit_one_use_slot_consumed: bool = False
    authorization_nonce_slot_consumed: bool = False
    predecessor_successor_slot_consumed: bool = False
    custody_successor_uniqueness_enforced: bool = False
    external_registry_non_equivocation_verified: bool = False
    later_head_consistency_verified: bool = False
    registry_epoch_transition_continuity_verified: bool = False
    production_validation_execution_authorized: bool = False
    production_validation_results_collected: bool = False
    scientifically_validated: bool = False
    parameter_fitting_authorized: bool = False
    product_qualified: bool = False
    claim_safe: bool = False
    _verification_seal: object = field(init=False, repr=False, compare=False)


def _new_verification(
    **values: object,
) -> ProductionReservationAuthenticatedHeadReceiptVerification:
    instance = object.__new__(ProductionReservationAuthenticatedHeadReceiptVerification)
    for name, value in values.items():
        object.__setattr__(instance, name, value)
    for name in (
        "registry_transaction_proof_reverified",
        "receipt_authority_signature_verified",
        "caller_challenge_match_verified",
        "exact_registry_head_and_status_tail_bound",
        "post_receipt_current_status_descendant_reverified",
        "authenticated_external_head_status_receipt_verified",
    ):
        object.__setattr__(instance, name, True)
    for name in (*_ACTUAL_FACT_POLICY, *_CLAIM_POLICY):
        object.__setattr__(instance, name, False)
    object.__setattr__(instance, "_verification_seal", _VERIFICATION_SEAL)
    return instance


def verify_external_production_reservation_authenticated_head_receipt(
    source: bytes,
    *,
    registry_proof_reverification_arguments: dict[str, object],
    current_registry_proof_reverification_arguments: dict[str, object],
    expected_head_receipt_sha256: str,
    expected_raw_head_receipt_sha256: str,
    expected_request_challenge_nonce_sha256: str,
    trusted_head_receipt_authority_keys: dict[
        str, ProductionReservationHeadReceiptAuthorityTrustAnchor
    ],
    checked_at: datetime,
) -> ProductionReservationAuthenticatedHeadReceiptVerification:
    """Verify one authenticated exact-head/status receipt without claim promotion."""

    checked = _parse_utc(
        _format_utc(checked_at, name="head receipt checked_at"),
        name="head receipt checked_at",
    )
    raw, loaded = _load_canonical_document(
        source,
        maximum_bytes=PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_MAX_BYTES,
        artifact_name="authenticated head receipt",
    )
    if _raw_sha256(raw) != _require_sha256(
        expected_raw_head_receipt_sha256,
        name="expected raw authenticated head receipt",
    ):
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            "raw authenticated head receipt identity is cross-wired"
        )
    signature = _signature(loaded.pop("head_receipt_authority_signature", None))
    head_receipt_sha256 = loaded.pop("head_receipt_sha256", None)
    expected_receipt = _require_sha256(
        expected_head_receipt_sha256,
        name="expected authenticated head receipt",
    )
    if (
        head_receipt_sha256 != expected_receipt
        or head_receipt_sha256 != _sha256(loaded)
    ):
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            "authenticated head receipt logical SHA-256 verification failed"
        )

    bound_registry_arguments = _snapshot_registry_proof_reverification_arguments(
        registry_proof_reverification_arguments
    )
    current_registry_arguments = _snapshot_registry_proof_reverification_arguments(
        current_registry_proof_reverification_arguments
    )
    proof = _reverify_registry_proof(
        bound_registry_arguments,
        checked_at=checked,
    )
    current_proof = _reverify_registry_proof(
        current_registry_arguments,
        checked_at=checked,
    )
    if current_proof != proof:
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            "current status reverification does not reproduce the receipt-bound registry proof"
        )
    _require_post_receipt_status_descendant(
        bound_registry_arguments,
        current_registry_arguments,
    )
    status, raw_status, _bound_keys, _bound_artifacts, _bound_superseded = (
        _status_tail(bound_registry_arguments)
    )
    (
        current_status,
        current_raw_status,
        revoked_keys,
        revoked_artifacts,
        superseded_artifacts,
    ) = _status_tail(current_registry_arguments)
    trust = _trust_map(trusted_head_receipt_authority_keys)
    authority_key_id = signature["key_id"]
    authority = trust.get(authority_key_id)
    if type(authority) is not ProductionReservationHeadReceiptAuthorityTrustAnchor:
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            "head receipt authority key is not trusted"
        )
    if (
        authority.registry_realm_identity_sha256
        != proof.registry_realm_identity_sha256
        or authority.registry_epoch != proof.registry_epoch
    ):
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            "head receipt authority trust scope is cross-wired"
        )
    bound_key_ids, bound_identities, bound_materials = _collect_prior_trust_aliases(
        bound_registry_arguments
    )
    current_key_ids, current_identities, current_materials = (
        _collect_prior_trust_aliases(current_registry_arguments)
    )
    prior_key_ids = bound_key_ids | current_key_ids
    prior_identities = bound_identities | current_identities
    prior_materials = bound_materials | current_materials
    authority_identities = {
        anchor.authority_identity_sha256 for anchor in trust.values()
    }
    authority_materials = {anchor.verification_key for anchor in trust.values()}
    if (
        set(trust) & prior_key_ids
        or authority_identities & prior_identities
        or authority_materials & prior_materials
    ):
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            "head receipt authority and prior trust roles alias"
        )
    authority_public_sha256 = _raw_sha256(authority.verification_key)

    challenge = _require_sha256(
        loaded.get("request_challenge_nonce_sha256"),
        name="head receipt request challenge",
    )
    if challenge != _require_sha256(
        expected_request_challenge_nonce_sha256,
        name="expected head receipt request challenge",
    ):
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            "head receipt request challenge is cross-wired"
        )
    proof_observed = _parse_utc(proof.observed_at_utc, name="proof observed_at")
    status_issued = _parse_utc(
        status.get("issued_at_utc"),
        name="status tail issued_at",
    )
    requested = _parse_utc(loaded.get("requested_at_utc"), name="receipt requested_at")
    head_observed = _parse_utc(
        loaded.get("head_observed_at_utc"),
        name="receipt head_observed_at",
    )
    receipt_issued = _parse_utc(
        loaded.get("receipt_issued_at_utc"),
        name="receipt issued_at",
    )
    expires = _parse_utc(loaded.get("expires_at_utc"), name="receipt expires_at")
    current_status_issued = _parse_utc(
        current_status.get("issued_at_utc"),
        name="current status tail issued_at",
    )
    if not (
        proof_observed
        <= status_issued
        <= requested
        <= head_observed
        <= receipt_issued
        < current_status_issued
        <= checked
        < expires
    ):
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            "authenticated head receipt has invalid causal time"
        )
    if (
        checked - requested
        > PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_MAX_AGE
        or receipt_issued - requested
        > PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_MAX_AGE
        or expires - receipt_issued
        > PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_MAX_VALIDITY
    ):
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            "authenticated head receipt is stale or overlong"
        )
    valid_from = _parse_utc(authority.valid_from_utc, name="authority valid_from")
    valid_until = _parse_utc(authority.valid_until_utc, name="authority valid_until")
    if not (
        valid_from <= head_observed < valid_until
        and valid_from <= receipt_issued < valid_until
        and valid_from <= checked < valid_until
    ):
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            "head receipt authority key is not valid across observation, issue, and check"
        )
    if authority_key_id in revoked_keys:
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            "head receipt authority key is revoked in the supplied status tail"
        )

    status_snapshot = _require_sha256(
        status.get("snapshot_sha256"),
        name="status tail snapshot",
    )
    raw_status_sha256 = _raw_sha256(raw_status)
    status_sequence = _require_exact_int(
        status.get("status_sequence"),
        name="status tail sequence",
        minimum=1,
    )
    status_checkpoint = _require_sha256(
        status.get("external_log_checkpoint_sha256"),
        name="status tail external log checkpoint",
    )
    current_status_snapshot = _require_sha256(
        current_status.get("snapshot_sha256"),
        name="current status tail snapshot",
    )
    current_raw_status_sha256 = _raw_sha256(current_raw_status)
    current_status_sequence = _require_exact_int(
        current_status.get("status_sequence"),
        name="current status tail sequence",
        minimum=1,
    )
    current_status_checkpoint = _require_sha256(
        current_status.get("external_log_checkpoint_sha256"),
        name="current status tail external log checkpoint",
    )
    if current_status_sequence <= status_sequence:
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            "current status tail sequence does not advance the receipt-bound tail"
        )
    external_artifact_identities = {
        head_receipt_sha256,
        _raw_sha256(raw),
        FROZEN_VALIDATION_PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_CONTRACT_SHA256,
        proof.proof_sha256,
        proof.raw_proof_sha256,
        proof.commit_sha256,
        proof.raw_commit_sha256,
        proof.registry_transaction_sha256,
        proof.registry_realm_identity_sha256,
        proof.committed_native_registry_checkpoint_sha256,
        proof.committed_registry_state_root_sha256,
        status_snapshot,
        raw_status_sha256,
        status_checkpoint,
        current_status_snapshot,
        current_raw_status_sha256,
        current_status_checkpoint,
        authority.authority_identity_sha256,
        authority_public_sha256,
        authority.service_binary_sha256,
        authority.service_schema_sha256,
        authority.service_configuration_sha256,
        authority.service_deployment_sha256,
        challenge,
    }
    if external_artifact_identities & (revoked_artifacts | superseded_artifacts):
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            "authenticated head receipt identity is revoked or superseded in the supplied status tail"
        )

    expected_projection: dict[str, Any] = {
        "schema_id": PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_SCHEMA_ID,
        "contract_sha256": FROZEN_VALIDATION_PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_CONTRACT_SHA256,
        "evidence_class": "synthetic_validation_production",
        "artifact_stage": "external_authenticated_reservation_head_status_receipt",
        "lane": proof.lane,
        "registry_proof_sha256": proof.proof_sha256,
        "raw_registry_proof_sha256": proof.raw_proof_sha256,
        "sequence_five_commit_sha256": proof.commit_sha256,
        "raw_sequence_five_commit_sha256": proof.raw_commit_sha256,
        "registry_transaction_sha256": proof.registry_transaction_sha256,
        "registry_realm_identity_sha256": proof.registry_realm_identity_sha256,
        "registry_epoch": proof.registry_epoch,
        "registry_sequence": proof.committed_registry_sequence,
        "native_registry_checkpoint_sha256": proof.committed_native_registry_checkpoint_sha256,
        "registry_state_root_sha256": proof.committed_registry_state_root_sha256,
        "status_tail_snapshot_sha256": status_snapshot,
        "raw_status_tail_sha256": raw_status_sha256,
        "status_tail_sequence": status_sequence,
        "status_tail_external_log_checkpoint_sha256": status_checkpoint,
        "status_tail_issued_at_utc": status["issued_at_utc"],
        "head_receipt_authority_identity_sha256": authority.authority_identity_sha256,
        "head_receipt_authority_key_id": authority_key_id,
        "head_receipt_authority_public_key_sha256": authority_public_sha256,
        "head_receipt_service_binary_sha256": authority.service_binary_sha256,
        "head_receipt_service_schema_sha256": authority.service_schema_sha256,
        "head_receipt_service_configuration_sha256": authority.service_configuration_sha256,
        "head_receipt_service_deployment_sha256": authority.service_deployment_sha256,
        "request_challenge_nonce_sha256": challenge,
        "proof_observed_at_utc": proof.observed_at_utc,
        "requested_at_utc": loaded["requested_at_utc"],
        "head_observed_at_utc": loaded["head_observed_at_utc"],
        "receipt_issued_at_utc": loaded["receipt_issued_at_utc"],
        "expires_at_utc": loaded["expires_at_utc"],
        "head_attestation_outcome": "authority_attested_exact_head_and_status_tail",
        "registry_transaction_proof_reverified": True,
        "receipt_authority_signature_verified": True,
        "caller_challenge_match_verified": True,
        "exact_registry_head_and_status_tail_bound": True,
        "authenticated_external_head_status_receipt_verified": True,
        **_ACTUAL_FACT_POLICY,
        **_CLAIM_POLICY,
        "superseded": False,
        "revoked": False,
    }
    if _canonical_bytes(loaded) != _canonical_bytes(expected_projection):
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            "authenticated head receipt fields are omitted or transplanted"
        )
    payload = {**expected_projection, "head_receipt_sha256": head_receipt_sha256}
    try:
        signature_valid = verify_ed25519(
            _canonical_bytes(payload),
            signature["value"],
            authority.verification_key,
        )
    except ReferenceMinimizationValidationEd25519Error as exc:
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            "authenticated head receipt Ed25519 verifier is unavailable"
        ) from exc
    if not signature_valid:
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            "authenticated head receipt signature verification failed"
        )
    return _new_verification(
        head_receipt_sha256=head_receipt_sha256,
        raw_head_receipt_sha256=_raw_sha256(raw),
        raw_head_receipt_byte_count=len(raw),
        lane=proof.lane,
        registry_proof_sha256=proof.proof_sha256,
        raw_registry_proof_sha256=proof.raw_proof_sha256,
        sequence_five_commit_sha256=proof.commit_sha256,
        raw_sequence_five_commit_sha256=proof.raw_commit_sha256,
        registry_transaction_sha256=proof.registry_transaction_sha256,
        registry_realm_identity_sha256=proof.registry_realm_identity_sha256,
        registry_epoch=proof.registry_epoch,
        registry_sequence=proof.committed_registry_sequence,
        native_registry_checkpoint_sha256=proof.committed_native_registry_checkpoint_sha256,
        registry_state_root_sha256=proof.committed_registry_state_root_sha256,
        status_tail_snapshot_sha256=status_snapshot,
        raw_status_tail_sha256=raw_status_sha256,
        status_tail_sequence=status_sequence,
        status_tail_external_log_checkpoint_sha256=status_checkpoint,
        current_status_tail_snapshot_sha256=current_status_snapshot,
        current_raw_status_tail_sha256=current_raw_status_sha256,
        current_status_tail_sequence=current_status_sequence,
        current_status_tail_external_log_checkpoint_sha256=(
            current_status_checkpoint
        ),
        current_status_tail_issued_at_utc=current_status["issued_at_utc"],
        authority_identity_sha256=authority.authority_identity_sha256,
        authority_key_id=authority_key_id,
        authority_public_key_sha256=authority_public_sha256,
        request_challenge_nonce_sha256=challenge,
        requested_at_utc=loaded["requested_at_utc"],
        head_observed_at_utc=loaded["head_observed_at_utc"],
        receipt_issued_at_utc=loaded["receipt_issued_at_utc"],
        expires_at_utc=loaded["expires_at_utc"],
    )


def _contract_projection() -> dict[str, Any]:
    return {
        "schema_id": VALIDATION_PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_CONTRACT_SCHEMA_ID,
        "contract_id": VALIDATION_PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_CONTRACT_ID,
        "contract_version": VALIDATION_PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_CONTRACT_VERSION,
        "frozen_at_utc": VALIDATION_PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_FROZEN_AT_UTC,
        "purpose": {
            "verifier_only": True,
            "external_receipt_service_implemented_by_package": False,
            "registry_transaction_proof_fresh_reverification_required": True,
            "reverification_inputs_snapshotted_before_use": True,
            "strict_post_receipt_status_descendant_reverification_required": True,
            "exact_registry_head_status_tail_and_challenge_binding_supported": True,
            "authenticated_receipt_signature_verification_supported": True,
            "global_latest_head_verification_supported": False,
            "later_head_consistency_supported": False,
            "non_equivocation_supported": False,
            "epoch_transition_continuity_supported": False,
            "verification_result_is_not_an_authorization_token": True,
            "downstream_raw_receipt_reverification_required": True,
        },
        "schemas": {
            "authenticated_head_receipt": PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_SCHEMA_ID,
        },
        "transport": {
            "canonical_ascii_json_required": True,
            "duplicate_keys_rejected": True,
            "maximum_bytes": PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_MAX_BYTES,
        },
        "binding": {
            "registry_proof_logical_and_raw_identity_bound": True,
            "sequence_five_logical_and_raw_commit_bound": True,
            "realm_epoch_sequence_native_checkpoint_and_state_root_bound": True,
            "status_tail_logical_raw_sequence_checkpoint_and_issue_time_bound": True,
            "post_receipt_current_status_logical_raw_sequence_checkpoint_recorded": True,
            "caller_challenge_required": True,
            "caller_challenge_equality_only": True,
            "caller_challenge_freshness_or_one_use_supported": False,
            "receipt_service_binary_schema_configuration_deployment_bound": True,
            "head_attestation_outcome_exact_value": "authority_attested_exact_head_and_status_tail",
        },
        "trust_and_freshness": {
            "signature_algorithm": "Ed25519",
            "receipt_authority_separated_from_all_prior_roles": True,
            "supplied_reverified_status_tail_denials_applied": True,
            "post_receipt_current_status_denials_applied": True,
            "selected_authority_key_valid_at_observation_issue_and_check": True,
            "causal_time_order": "proof_observation_le_receipt_bound_status_tail_le_request_le_head_observation_le_receipt_issue_lt_current_status_tail_le_check_lt_expiry",
            "maximum_age_seconds": int(
                PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_MAX_AGE.total_seconds()
            ),
            "maximum_validity_seconds": int(
                PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_MAX_VALIDITY.total_seconds()
            ),
            "maximum_anchors": PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_MAX_TRUST_ANCHORS,
            "reverification_snapshot_maximum_nodes": PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_MAX_SNAPSHOT_NODES,
            "reverification_snapshot_maximum_depth": PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_MAX_SNAPSHOT_DEPTH,
        },
        "verified_facts_when_external_receipt_is_supplied": {
            "registry_transaction_proof_reverified": True,
            "receipt_authority_signature_verified": True,
            "caller_challenge_match_verified": True,
            "exact_registry_head_and_status_tail_bound": True,
            "post_receipt_current_status_descendant_reverified": True,
            "authenticated_external_head_status_receipt_verified": True,
            **_ACTUAL_FACT_POLICY,
        },
        "current_provisioning": {
            "external_authenticated_receipt_present": False,
            "trusted_receipt_authority_key_present": False,
            "caller_challenge_present": False,
            "post_receipt_current_status_descendant_present": False,
            "production_execution_authorized": False,
            "production_results_collected": False,
        },
        "claim_policy": dict(_CLAIM_POLICY),
        "blockers": list(_BLOCKERS),
        "superseded": False,
        "revoked": False,
    }


def validation_production_reservation_authenticated_head_receipt_contract_document() -> dict[str, Any]:
    projection = _contract_projection()
    document = {**projection, "contract_sha256": _sha256(projection)}
    if document["contract_sha256"] != (
        FROZEN_VALIDATION_PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_CONTRACT_SHA256
    ):
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            "frozen authenticated head receipt contract SHA-256 drifted"
        )
    return document


def require_validation_production_reservation_authenticated_head_receipt_contract_document(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if type(payload) is not dict:
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            "authenticated head receipt contract must be an exact built-in dict"
        )
    observed = json.loads(_canonical_bytes(payload).decode("ascii"))
    expected = (
        validation_production_reservation_authenticated_head_receipt_contract_document()
    )
    if _canonical_bytes(observed) != _canonical_bytes(expected):
        raise ValidationProductionReservationAuthenticatedHeadReceiptError(
            "authenticated head receipt contract does not match the frozen record"
        )
    return observed


def validation_production_reservation_authenticated_head_receipt_decision() -> dict[
    str, Any
]:
    contract = (
        validation_production_reservation_authenticated_head_receipt_contract_document()
    )
    return {
        "contract_sha256": contract["contract_sha256"],
        "verifier_implemented": True,
        "external_receipt_service_implemented_by_package": False,
        "external_authenticated_receipt_present": False,
        "post_receipt_current_status_descendant_present": False,
        "authenticated_external_head_status_receipt_verified": False,
        **_ACTUAL_FACT_POLICY,
        **_CLAIM_POLICY,
        "blockers": list(_BLOCKERS),
    }


__all__ = [
    "FROZEN_VALIDATION_PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_CONTRACT_SHA256",
    "PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_MAX_AGE",
    "PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_MAX_BYTES",
    "PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_MAX_SNAPSHOT_DEPTH",
    "PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_MAX_SNAPSHOT_NODES",
    "PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_MAX_VALIDITY",
    "PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_SCHEMA_ID",
    "ProductionReservationAuthenticatedHeadReceiptVerification",
    "ProductionReservationHeadReceiptAuthorityTrustAnchor",
    "VALIDATION_PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_CONTRACT_ID",
    "VALIDATION_PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_CONTRACT_SCHEMA_ID",
    "VALIDATION_PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_CONTRACT_VERSION",
    "ValidationProductionReservationAuthenticatedHeadReceiptError",
    "require_validation_production_reservation_authenticated_head_receipt_contract_document",
    "validation_production_reservation_authenticated_head_receipt_contract_document",
    "validation_production_reservation_authenticated_head_receipt_decision",
    "verify_external_production_reservation_authenticated_head_receipt",
]
