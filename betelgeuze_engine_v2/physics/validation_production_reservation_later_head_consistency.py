"""Verify one bounded same-epoch later registry-head consistency proof.

The verifier starts from a freshly reverified authenticated head receipt.  It
then verifies an adjacent, backend-signed checkpoint path to one caller-pinned
later head, an observer signature over the complete path, and sparse-Merkle
inclusion of the original three consumed reservation slots in the later state
root.  A status descendant issued after the consistency proof supplies the
revocation and supersession fence.  ``later_head_observed_at_utc`` is the
observer countersign completion time, not merely the backend commit time.

This is deliberately a one-fork verifier.  Separately pinned sibling paths can
both verify, so it does not prove global latest-head status, realm-wide
non-equivocation, or epoch-transition continuity.  It never authorizes a run or
promotes scientific or product claims.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from typing import Any, Mapping

from betelgeuze_engine_v2.physics.reference_minimization_validation_authorization import (
    MinimizationAuthorizationOperatorTrustAnchor,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_ed25519 import (
    ReferenceMinimizationValidationEd25519Error,
    verify_ed25519,
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
from betelgeuze_engine_v2.physics.validation_production_reservation_authenticated_head_receipt import (
    ProductionReservationAuthenticatedHeadReceiptVerification,
    ProductionReservationHeadReceiptAuthorityTrustAnchor,
    ValidationProductionReservationAuthenticatedHeadReceiptError,
    verify_external_production_reservation_authenticated_head_receipt,
)
from betelgeuze_engine_v2.physics.validation_production_reservation_custody_extension import (
    PRODUCTION_RESERVATION_MAX_SIGNED_TRANSPORT_BYTES,
    ProductionReservationRegistryTrustAnchor,
    ProductionReservationWitnessTrustAnchor,
)
from betelgeuze_engine_v2.physics.validation_production_reservation_registry_proof import (
    PRODUCTION_RESERVATION_REGISTRY_PROOF_MAX_BYTES,
    ProductionReservationRegistryBackendTrustAnchor,
    ProductionReservationRegistryHeadObserverTrustAnchor,
    ValidationProductionReservationRegistryProofError,
    production_reservation_sparse_merkle_consumed_leaf_sha256,
    production_reservation_sparse_merkle_root_sha256,
)
from betelgeuze_engine_v2.physics.validation_production_review_authorization_custody_extension import (
    ProductionAuthorizationCarrierTrustAnchor,
    ProductionReviewCarrierTrustAnchor,
)


VALIDATION_PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_CONTRACT_SCHEMA_ID = (
    "betelgeuze.engine_v2_validation_production_reservation_later_head_consistency_contract/2.0.0"
)
VALIDATION_PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_CONTRACT_ID = (
    "engine_v2_validation_production_reservation_later_head_consistency/2.0.0"
)
VALIDATION_PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_CONTRACT_VERSION = (
    "2.0.0"
)
VALIDATION_PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_FROZEN_AT_UTC = (
    "2026-07-22T00:00:00Z"
)
PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_PROOF_SCHEMA_ID = (
    "betelgeuze.engine_v2_external_reservation_later_head_consistency_proof/1.0.0"
)
PRODUCTION_RESERVATION_LATER_HEAD_TRANSITION_SCHEMA_ID = (
    "betelgeuze.engine_v2_external_reservation_later_head_transition/1.0.0"
)
PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_MAX_BYTES = 2 * 1024 * 1024
PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_MAX_TRANSITIONS = 256
PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_MAX_TRUST_ANCHORS = 16
PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_MAX_SNAPSHOT_NODES = 100_000
PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_MAX_SNAPSHOT_DEPTH = 64
PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_MAX_JSON_INTEGER_DIGITS = 20
PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_MAX_AGE = timedelta(minutes=15)
PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_MAX_VALIDITY = timedelta(minutes=15)
FROZEN_VALIDATION_PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_CONTRACT_SHA256 = (
    "2a714e5f7be70378467a58a187fedd09ccc9ef21082bdfde3080adf3fe55bd46"
)
FROZEN_LEGACY_VALIDATION_PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_CONTRACT_SHA256_V1 = (
    "ee4e5d624e5f565e2fd591ddae899cea5f12b5a07c2a694b23cdb777bfb1d834"
)

_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_UTC = timezone.utc
_VERIFICATION_SEAL = object()
_SLOT_KINDS = ("permit", "authorization_nonce", "predecessor_successor")
_HEAD_RECEIPT_REVERIFICATION_FIELDS = {
    "source",
    "registry_proof_reverification_arguments",
    "current_registry_proof_reverification_arguments",
    "expected_head_receipt_sha256",
    "expected_raw_head_receipt_sha256",
    "expected_request_challenge_nonce_sha256",
    "trusted_head_receipt_authority_keys",
}
_ALLOWED_SNAPSHOT_DATACLASS_TYPES = (
    AuthorizationOperatorTrustAnchor,
    CustodyRoleTrustAnchor,
    EvidenceAuthorityTrustAnchor,
    MinimizationAuthorizationOperatorTrustAnchor,
    MinimizationScientificReviewerTrustAnchor,
    ProductionAuthorizationCarrierTrustAnchor,
    ProductionReservationHeadReceiptAuthorityTrustAnchor,
    ProductionReservationRegistryBackendTrustAnchor,
    ProductionReservationRegistryHeadObserverTrustAnchor,
    ProductionReservationRegistryTrustAnchor,
    ProductionReservationWitnessTrustAnchor,
    ProductionReviewCarrierTrustAnchor,
    ScientificReviewerTrustAnchor,
)
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
    "registry_epoch_transition_continuity_verified": False,
}
_CLAIM_POLICY = {
    "production_validation_execution_authorized": False,
    "production_validation_results_collected": False,
    "scientifically_validated": False,
    "parameter_fitting_authorized": False,
    "product_qualified": False,
    "claim_safe": False,
}
_BLOCKERS = (
    "later_head_consistency_proof_not_provisioned",
    "authenticated_external_head_status_receipt_not_provisioned",
    "trusted_external_head_receipt_authority_key_not_provisioned",
    "caller_head_receipt_challenge_not_provisioned",
    "trusted_external_registry_backend_key_not_provisioned",
    "external_registry_head_observer_key_not_provisioned",
    "post_consistency_current_status_descendant_not_provisioned",
    "caller_challenge_freshness_and_one_use_not_independently_verified",
    "global_latest_registry_head_not_independently_verified",
    "global_latest_status_head_not_independently_verified",
    "external_registry_non_equivocation_proof_not_provisioned",
    "registry_epoch_transition_continuity_not_provisioned",
    "external_custody_successor_uniqueness_not_provisioned",
    "production_validation_results_not_collected",
    "two_cpu_hosts_missing",
    "independent_human_result_review_missing",
)


class ValidationProductionReservationLaterHeadConsistencyError(ValueError):
    """The supplied later-head consistency proof is invalid."""


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
        raise ValidationProductionReservationLaterHeadConsistencyError(
            "later-head consistency value is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _raw_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    if type(value) is not str or not _SHA256_RE.fullmatch(value):
        raise ValidationProductionReservationLaterHeadConsistencyError(
            f"{name} must be an exact lowercase SHA-256"
        )
    return value


def _require_token(value: object, *, name: str) -> str:
    if type(value) is not str or not _TOKEN_RE.fullmatch(value):
        raise ValidationProductionReservationLaterHeadConsistencyError(
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
        raise ValidationProductionReservationLaterHeadConsistencyError(
            f"{name} must be an exact bounded integer"
        )
    return value


def _parse_utc(value: object, *, name: str) -> datetime:
    if type(value) is not str or not value.endswith("Z"):
        raise ValidationProductionReservationLaterHeadConsistencyError(
            f"{name} must be an exact UTC timestamp"
        )
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValidationProductionReservationLaterHeadConsistencyError(
            f"{name} must be an exact UTC timestamp"
        ) from exc
    if (
        parsed.tzinfo is None
        or parsed.utcoffset() != timedelta(0)
        or parsed.microsecond
        or parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value
    ):
        raise ValidationProductionReservationLaterHeadConsistencyError(
            f"{name} must be an exact whole-second UTC timestamp"
        )
    return parsed.astimezone(_UTC)


def _format_utc(value: datetime, *, name: str) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValidationProductionReservationLaterHeadConsistencyError(
            f"{name} must be timezone-aware"
        )
    normalized = value.astimezone(_UTC)
    if normalized.microsecond:
        raise ValidationProductionReservationLaterHeadConsistencyError(
            f"{name} must use whole seconds"
        )
    return normalized.strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_canonical_document(
    source: object,
    *,
    maximum_bytes: int,
    artifact_name: str,
) -> tuple[bytes, dict[str, Any]]:
    if type(source) is not bytes or not source:
        raise ValidationProductionReservationLaterHeadConsistencyError(
            f"raw {artifact_name} must be exact non-empty bytes"
        )
    if len(source) > maximum_bytes:
        raise ValidationProductionReservationLaterHeadConsistencyError(
            f"raw {artifact_name} exceeds its transport bound"
        )

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValidationProductionReservationLaterHeadConsistencyError(
                    f"{artifact_name} contains a duplicate JSON key"
                )
            result[key] = value
        return result

    def parse_bounded_integer(value: str) -> int:
        digits = value[1:] if value.startswith("-") else value
        if len(digits) > (
            PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_MAX_JSON_INTEGER_DIGITS
        ):
            raise ValueError("JSON integer exceeds its digit bound")
        return int(value)

    try:
        loaded = json.loads(
            source.decode("ascii"),
            object_pairs_hook=reject_duplicates,
            parse_int=parse_bounded_integer,
        )
    except (
        UnicodeDecodeError,
        RecursionError,
        OverflowError,
        TypeError,
        ValueError,
    ) as exc:
        if isinstance(
            exc, ValidationProductionReservationLaterHeadConsistencyError
        ):
            raise
        raise ValidationProductionReservationLaterHeadConsistencyError(
            f"{artifact_name} is not canonical ASCII JSON"
        ) from exc
    if type(loaded) is not dict or _canonical_bytes(loaded) != source:
        raise ValidationProductionReservationLaterHeadConsistencyError(
            f"{artifact_name} is not canonical ASCII JSON"
        )
    return source, loaded


def _signature(value: object, *, name: str) -> dict[str, str]:
    if type(value) is not dict or set(value) != {"algorithm", "key_id", "value"}:
        raise ValidationProductionReservationLaterHeadConsistencyError(
            f"{name} signature fields are invalid"
        )
    if value["algorithm"] != "Ed25519" or type(value["value"]) is not str:
        raise ValidationProductionReservationLaterHeadConsistencyError(
            f"{name} signature is invalid"
        )
    return {
        "algorithm": "Ed25519",
        "key_id": _require_token(value["key_id"], name=f"{name} key id"),
        "value": value["value"],
    }


def _snapshot(value: object, *, name: str) -> object:
    memo: dict[int, object] = {}
    active: set[int] = set()
    visited = 0

    def clone(current: object, *, depth: int) -> object:
        nonlocal visited
        visited += 1
        if (
            visited > PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_MAX_SNAPSHOT_NODES
            or depth > PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_MAX_SNAPSHOT_DEPTH
        ):
            raise ValidationProductionReservationLaterHeadConsistencyError(
                f"{name} graph exceeds its snapshot bound"
            )
        if current is None or type(current) in (bool, int, float, str, bytes):
            return current
        identity = id(current)
        if identity in active:
            raise ValidationProductionReservationLaterHeadConsistencyError(
                f"{name} graph is cyclic"
            )
        if identity in memo:
            return memo[identity]
        current_type = type(current)
        active.add(identity)
        try:
            if current_type is dict:
                if len(current) > (
                    PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_MAX_SNAPSHOT_NODES
                ):
                    raise ValidationProductionReservationLaterHeadConsistencyError(
                        f"{name} mapping exceeds its snapshot bound"
                    )
                result: dict[str, object] = {}
                memo[identity] = result
                for key, child in tuple(current.items()):
                    if type(key) is not str:
                        raise ValidationProductionReservationLaterHeadConsistencyError(
                            f"{name} mapping key is invalid"
                        )
                    result[key] = clone(child, depth=depth + 1)
                return result
            if current_type is list:
                if len(current) > (
                    PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_MAX_SNAPSHOT_NODES
                ):
                    raise ValidationProductionReservationLaterHeadConsistencyError(
                        f"{name} list exceeds its snapshot bound"
                    )
                result_list: list[object] = []
                memo[identity] = result_list
                result_list.extend(
                    clone(child, depth=depth + 1) for child in tuple(current)
                )
                return result_list
            if current_type is tuple:
                if len(current) > (
                    PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_MAX_SNAPSHOT_NODES
                ):
                    raise ValidationProductionReservationLaterHeadConsistencyError(
                        f"{name} tuple exceeds its snapshot bound"
                    )
                result_tuple = tuple(
                    clone(child, depth=depth + 1) for child in current
                )
                memo[identity] = result_tuple
                return result_tuple
            if current_type in _ALLOWED_SNAPSHOT_DATACLASS_TYPES and is_dataclass(
                current
            ):
                descriptors = fields(current)
                if any(not descriptor.init for descriptor in descriptors):
                    raise ValidationProductionReservationLaterHeadConsistencyError(
                        f"{name} trust anchor is not snapshot-safe"
                    )
                values = {
                    descriptor.name: clone(
                        getattr(current, descriptor.name), depth=depth + 1
                    )
                    for descriptor in descriptors
                }
                result_dataclass = current_type(**values)
                memo[identity] = result_dataclass
                return result_dataclass
            raise ValidationProductionReservationLaterHeadConsistencyError(
                f"{name} graph contains an unsupported value"
            )
        finally:
            active.discard(identity)

    try:
        return clone(value, depth=0)
    except ValidationProductionReservationLaterHeadConsistencyError:
        raise
    except (IndexError, KeyError, TypeError, ValueError, RuntimeError, RecursionError) as exc:
        raise ValidationProductionReservationLaterHeadConsistencyError(
            f"{name} cannot be snapshotted"
        ) from exc


def _snapshot_head_arguments(value: object) -> dict[str, object]:
    snapshot = _snapshot(value, name="authenticated head receipt reverification")
    if type(snapshot) is not dict or set(snapshot) != _HEAD_RECEIPT_REVERIFICATION_FIELDS:
        raise ValidationProductionReservationLaterHeadConsistencyError(
            "authenticated head receipt reverification arguments are omitted or aliased"
        )
    return snapshot


def _reverify_head_receipt(
    arguments: dict[str, object],
    *,
    checked_at: datetime,
) -> ProductionReservationAuthenticatedHeadReceiptVerification:
    try:
        return verify_external_production_reservation_authenticated_head_receipt(
            **arguments,  # type: ignore[arg-type]
            checked_at=checked_at,
        )
    except ValidationProductionReservationAuthenticatedHeadReceiptError as exc:
        raise ValidationProductionReservationLaterHeadConsistencyError(
            "authenticated head receipt reverification failed"
        ) from exc


def _backend_trust_map(
    value: object,
) -> dict[str, ProductionReservationRegistryBackendTrustAnchor]:
    if (
        type(value) is not dict
        or not value
        or len(value) > PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_MAX_TRUST_ANCHORS
    ):
        raise ValidationProductionReservationLaterHeadConsistencyError(
            "registry backend trust map is invalid"
        )
    result: dict[str, ProductionReservationRegistryBackendTrustAnchor] = {}
    identities: set[str] = set()
    materials: set[bytes] = set()
    for raw_key_id, anchor in value.items():
        key_id = _require_token(raw_key_id, name="registry backend key id")
        if type(anchor) is not ProductionReservationRegistryBackendTrustAnchor:
            raise ValidationProductionReservationLaterHeadConsistencyError(
                "registry backend trust map contains an invalid anchor"
            )
        identity = _require_sha256(
            anchor.backend_identity_sha256, name="registry backend identity"
        )
        if type(anchor.verification_key) is not bytes or len(anchor.verification_key) != 32:
            raise ValidationProductionReservationLaterHeadConsistencyError(
                "registry backend public key must be exactly 32 bytes"
            )
        if identity in identities or anchor.verification_key in materials:
            raise ValidationProductionReservationLaterHeadConsistencyError(
                "registry backend trust map contains an alias"
            )
        for field_name, digest in (
            ("registry backend realm", anchor.registry_realm_identity_sha256),
            ("registry backend service binary", anchor.service_binary_sha256),
            ("registry backend service schema", anchor.service_schema_sha256),
            ("registry backend service configuration", anchor.service_configuration_sha256),
            ("registry backend service deployment", anchor.service_deployment_sha256),
        ):
            _require_sha256(digest, name=field_name)
        _require_token(anchor.registry_epoch, name="registry backend epoch")
        if _parse_utc(anchor.valid_from_utc, name="backend valid_from") >= _parse_utc(
            anchor.valid_until_utc, name="backend valid_until"
        ):
            raise ValidationProductionReservationLaterHeadConsistencyError(
                "registry backend trust validity window is invalid"
            )
        identities.add(identity)
        materials.add(anchor.verification_key)
        result[key_id] = anchor
    return result


def _observer_trust_map(
    value: object,
) -> dict[str, ProductionReservationRegistryHeadObserverTrustAnchor]:
    if (
        type(value) is not dict
        or not value
        or len(value) > PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_MAX_TRUST_ANCHORS
    ):
        raise ValidationProductionReservationLaterHeadConsistencyError(
            "registry head-observer trust map is invalid"
        )
    result: dict[str, ProductionReservationRegistryHeadObserverTrustAnchor] = {}
    identities: set[str] = set()
    materials: set[bytes] = set()
    for raw_key_id, anchor in value.items():
        key_id = _require_token(raw_key_id, name="registry head-observer key id")
        if type(anchor) is not ProductionReservationRegistryHeadObserverTrustAnchor:
            raise ValidationProductionReservationLaterHeadConsistencyError(
                "registry head-observer trust map contains an invalid anchor"
            )
        identity = _require_sha256(
            anchor.observer_identity_sha256, name="registry head-observer identity"
        )
        if type(anchor.verification_key) is not bytes or len(anchor.verification_key) != 32:
            raise ValidationProductionReservationLaterHeadConsistencyError(
                "registry head-observer public key must be exactly 32 bytes"
            )
        if identity in identities or anchor.verification_key in materials:
            raise ValidationProductionReservationLaterHeadConsistencyError(
                "registry head-observer trust map contains an alias"
            )
        _require_sha256(
            anchor.registry_realm_identity_sha256,
            name="registry head-observer realm",
        )
        _require_token(anchor.registry_epoch, name="registry head-observer epoch")
        _require_sha256(
            anchor.observer_deployment_sha256,
            name="registry head-observer deployment",
        )
        if _parse_utc(anchor.valid_from_utc, name="observer valid_from") >= _parse_utc(
            anchor.valid_until_utc, name="observer valid_until"
        ):
            raise ValidationProductionReservationLaterHeadConsistencyError(
                "registry head-observer trust validity window is invalid"
            )
        identities.add(identity)
        materials.add(anchor.verification_key)
        result[key_id] = anchor
    return result


def _registry_arguments(
    head_arguments: dict[str, object],
    *,
    name: str,
) -> dict[str, object]:
    value = head_arguments.get(name)
    if type(value) is not dict:
        raise ValidationProductionReservationLaterHeadConsistencyError(
            f"{name} is unavailable"
        )
    return value


def _require_same_external_trust_domain(
    head_arguments: dict[str, object],
    backend_trust: dict[str, ProductionReservationRegistryBackendTrustAnchor],
    observer_trust: dict[str, ProductionReservationRegistryHeadObserverTrustAnchor],
) -> None:
    for registry_name in (
        "registry_proof_reverification_arguments",
        "current_registry_proof_reverification_arguments",
    ):
        registry = _registry_arguments(head_arguments, name=registry_name)
        if (
            registry.get("trusted_registry_backend_keys") != backend_trust
            or registry.get("trusted_registry_head_observer_keys") != observer_trust
        ):
            raise ValidationProductionReservationLaterHeadConsistencyError(
                "later-head proof external trust domain differs from the anchor receipt"
            )


def _current_status_tail(
    head_arguments: dict[str, object],
) -> tuple[dict[str, Any], bytes, set[str], set[str], set[str]]:
    registry = _registry_arguments(
        head_arguments,
        name="current_registry_proof_reverification_arguments",
    )
    seq5 = registry.get("sequence_five_reverification_arguments")
    if type(seq5) is not dict:
        raise ValidationProductionReservationLaterHeadConsistencyError(
            "current sequence-five reverification arguments are unavailable"
        )
    prefix = seq5.get("current_raw_sequence_four_prefix")
    if type(prefix) is not dict:
        raise ValidationProductionReservationLaterHeadConsistencyError(
            "current status lineage is unavailable"
        )
    lineage = prefix.get("raw_status_lineage_bytes")
    if (
        type(lineage) not in (list, tuple)
        or not lineage
        or any(type(item) is not bytes or not item for item in lineage)
    ):
        raise ValidationProductionReservationLaterHeadConsistencyError(
            "current status lineage is unavailable"
        )
    raw, status = _load_canonical_document(
        lineage[-1],
        maximum_bytes=PRODUCTION_RESERVATION_MAX_SIGNED_TRANSPORT_BYTES,
        artifact_name="post-consistency status tail",
    )
    revoked_keys: set[str] = set()
    revoked_artifacts: set[str] = set()
    superseded_artifacts: set[str] = set()
    rows = status.get("revoked_key_rows")
    if type(rows) is not list:
        raise ValidationProductionReservationLaterHeadConsistencyError(
            "post-consistency revoked key rows are unavailable"
        )
    seen_keys: set[tuple[str, str]] = set()
    for row in rows:
        if type(row) is not dict:
            raise ValidationProductionReservationLaterHeadConsistencyError(
                "post-consistency revoked key row is invalid"
            )
        pair = (
            _require_token(row.get("role"), name="revoked key role"),
            _require_token(row.get("key_id"), name="revoked key id"),
        )
        if pair in seen_keys:
            raise ValidationProductionReservationLaterHeadConsistencyError(
                "post-consistency revoked key rows are duplicated"
            )
        seen_keys.add(pair)
        revoked_keys.add(pair[1])
    rows = status.get("revoked_artifact_rows")
    if type(rows) is not list:
        raise ValidationProductionReservationLaterHeadConsistencyError(
            "post-consistency revoked artifact rows are unavailable"
        )
    seen_artifacts: set[tuple[str, str]] = set()
    for row in rows:
        if type(row) is not dict:
            raise ValidationProductionReservationLaterHeadConsistencyError(
                "post-consistency revoked artifact row is invalid"
            )
        pair = (
            _require_token(row.get("artifact_kind"), name="revoked artifact kind"),
            _require_sha256(row.get("artifact_sha256"), name="revoked artifact"),
        )
        if pair in seen_artifacts:
            raise ValidationProductionReservationLaterHeadConsistencyError(
                "post-consistency revoked artifact rows are duplicated"
            )
        seen_artifacts.add(pair)
        revoked_artifacts.add(pair[1])
    rows = status.get("supersession_rows")
    if type(rows) is not list:
        raise ValidationProductionReservationLaterHeadConsistencyError(
            "post-consistency supersession rows are unavailable"
        )
    seen_superseded: set[tuple[str, str]] = set()
    for row in rows:
        if type(row) is not dict:
            raise ValidationProductionReservationLaterHeadConsistencyError(
                "post-consistency supersession row is invalid"
            )
        pair = (
            _require_token(row.get("artifact_kind"), name="superseded artifact kind"),
            _require_sha256(
                row.get("superseded_sha256"), name="superseded artifact"
            ),
        )
        if pair in seen_superseded:
            raise ValidationProductionReservationLaterHeadConsistencyError(
                "post-consistency supersession rows are duplicated"
            )
        seen_superseded.add(pair)
        superseded_artifacts.add(pair[1])
    return status, raw, revoked_keys, revoked_artifacts, superseded_artifacts


def _anchor_slot_rows(
    head_arguments: dict[str, object],
    *,
    transaction_sha256: str,
) -> tuple[tuple[str, str, str], ...]:
    registry = _registry_arguments(
        head_arguments,
        name="registry_proof_reverification_arguments",
    )
    raw = registry.get("source")
    _raw, document = _load_canonical_document(
        raw,
        maximum_bytes=PRODUCTION_RESERVATION_REGISTRY_PROOF_MAX_BYTES,
        artifact_name="anchor registry proof",
    )
    rows = document.get("slot_transition_proofs")
    if type(rows) is not list or len(rows) != len(_SLOT_KINDS):
        raise ValidationProductionReservationLaterHeadConsistencyError(
            "anchor registry proof slot transitions are unavailable"
        )
    result: list[tuple[str, str, str]] = []
    for expected_kind, row in zip(_SLOT_KINDS, rows, strict=True):
        if type(row) is not dict or row.get("slot_kind") != expected_kind:
            raise ValidationProductionReservationLaterHeadConsistencyError(
                "anchor registry proof slot transitions are reordered or invalid"
            )
        slot = _require_sha256(row.get("slot_sha256"), name="anchor slot")
        transaction = _require_sha256(
            row.get("consumed_by_registry_transaction_sha256"),
            name="anchor slot transaction",
        )
        if transaction != transaction_sha256:
            raise ValidationProductionReservationLaterHeadConsistencyError(
                "anchor slot is not consumed by the verified registry transaction"
            )
        result.append((expected_kind, slot, transaction))
    if len({row[1] for row in result}) != len(result):
        raise ValidationProductionReservationLaterHeadConsistencyError(
            "anchor registry proof slots alias"
        )
    return tuple(result)


def _anchor_link_sha256(
    anchor: ProductionReservationAuthenticatedHeadReceiptVerification,
) -> str:
    return _sha256(
        {
            "schema_id": "betelgeuze.engine_v2_external_reservation_head_anchor_link/1.0.0",
            "head_receipt_sha256": anchor.head_receipt_sha256,
            "raw_head_receipt_sha256": anchor.raw_head_receipt_sha256,
            "registry_proof_sha256": anchor.registry_proof_sha256,
            "raw_registry_proof_sha256": anchor.raw_registry_proof_sha256,
            "registry_realm_identity_sha256": anchor.registry_realm_identity_sha256,
            "registry_epoch": anchor.registry_epoch,
            "registry_sequence": anchor.registry_sequence,
            "native_registry_checkpoint_sha256": (
                anchor.native_registry_checkpoint_sha256
            ),
            "registry_state_root_sha256": anchor.registry_state_root_sha256,
        }
    )


def _verify_transition_rows(
    value: object,
    *,
    anchor: ProductionReservationAuthenticatedHeadReceiptVerification,
    backend_trust: dict[str, ProductionReservationRegistryBackendTrustAnchor],
    checked_at: datetime,
) -> tuple[list[dict[str, Any]], datetime, datetime, set[str], set[str]]:
    if (
        type(value) is not list
        or not value
        or len(value) > PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_MAX_TRANSITIONS
    ):
        raise ValidationProductionReservationLaterHeadConsistencyError(
            "checkpoint transition path is empty or exceeds its bound"
        )
    previous_sequence = anchor.registry_sequence
    previous_checkpoint = anchor.native_registry_checkpoint_sha256
    previous_root = anchor.registry_state_root_sha256
    previous_link = _anchor_link_sha256(anchor)
    previous_time = _parse_utc(
        anchor.head_observed_at_utc, name="anchor head observed_at"
    )
    normalized: list[dict[str, Any]] = []
    selected_key_ids: set[str] = set()
    artifact_identities: set[str] = set()
    transaction_ids: set[str] = set()
    transition_ids: set[str] = set()
    for index, raw_row in enumerate(value):
        if type(raw_row) is not dict:
            raise ValidationProductionReservationLaterHeadConsistencyError(
                "checkpoint transition row is invalid"
            )
        row = dict(raw_row)
        signature = _signature(
            row.pop("backend_signature", None), name="later-head backend"
        )
        transition_sha256 = row.pop("transition_sha256", None)
        expected_fields = {
            "schema_id",
            "transition_index",
            "registry_realm_identity_sha256",
            "registry_epoch",
            "prior_registry_sequence",
            "committed_registry_sequence",
            "prior_native_registry_checkpoint_sha256",
            "committed_native_registry_checkpoint_sha256",
            "prior_registry_state_root_sha256",
            "committed_registry_state_root_sha256",
            "registry_transaction_sha256",
            "committed_at_utc",
            "previous_transition_sha256",
            "backend_identity_sha256",
            "backend_key_id",
            "backend_public_key_sha256",
            "backend_service_binary_sha256",
            "backend_service_schema_sha256",
            "backend_service_configuration_sha256",
            "backend_service_deployment_sha256",
        }
        if set(row) != expected_fields:
            raise ValidationProductionReservationLaterHeadConsistencyError(
                "checkpoint transition fields are omitted or transplanted"
            )
        key_id = signature["key_id"]
        backend = backend_trust.get(key_id)
        if type(backend) is not ProductionReservationRegistryBackendTrustAnchor:
            raise ValidationProductionReservationLaterHeadConsistencyError(
                "checkpoint transition backend key is not trusted"
            )
        transition_index = _require_exact_int(
            row.get("transition_index"), name="transition index"
        )
        prior_sequence = _require_exact_int(
            row.get("prior_registry_sequence"), name="transition prior sequence"
        )
        committed_sequence = _require_exact_int(
            row.get("committed_registry_sequence"),
            name="transition committed sequence",
            minimum=1,
        )
        prior_checkpoint = _require_sha256(
            row.get("prior_native_registry_checkpoint_sha256"),
            name="transition prior checkpoint",
        )
        committed_checkpoint = _require_sha256(
            row.get("committed_native_registry_checkpoint_sha256"),
            name="transition committed checkpoint",
        )
        prior_root = _require_sha256(
            row.get("prior_registry_state_root_sha256"),
            name="transition prior state root",
        )
        committed_root = _require_sha256(
            row.get("committed_registry_state_root_sha256"),
            name="transition committed state root",
        )
        transaction = _require_sha256(
            row.get("registry_transaction_sha256"),
            name="transition registry transaction",
        )
        committed_at = _parse_utc(
            row.get("committed_at_utc"), name="transition committed_at"
        )
        if (
            row.get("schema_id")
            != PRODUCTION_RESERVATION_LATER_HEAD_TRANSITION_SCHEMA_ID
            or transition_index != index
            or row.get("registry_realm_identity_sha256")
            != anchor.registry_realm_identity_sha256
            or row.get("registry_epoch") != anchor.registry_epoch
            or prior_sequence != previous_sequence
            or committed_sequence != previous_sequence + 1
            or prior_checkpoint != previous_checkpoint
            or prior_root != previous_root
            or row.get("previous_transition_sha256") != previous_link
        ):
            raise ValidationProductionReservationLaterHeadConsistencyError(
                "checkpoint transition path is reordered, gapped, or cross-wired"
            )
        if (
            committed_checkpoint == prior_checkpoint
            or committed_root == prior_root
            or committed_at <= previous_time
        ):
            raise ValidationProductionReservationLaterHeadConsistencyError(
                "checkpoint transition does not strictly advance state and time"
            )
        if (
            backend.registry_realm_identity_sha256
            != anchor.registry_realm_identity_sha256
            or backend.registry_epoch != anchor.registry_epoch
            or row.get("backend_identity_sha256")
            != backend.backend_identity_sha256
            or row.get("backend_key_id") != key_id
            or row.get("backend_public_key_sha256")
            != _raw_sha256(backend.verification_key)
            or row.get("backend_service_binary_sha256")
            != backend.service_binary_sha256
            or row.get("backend_service_schema_sha256")
            != backend.service_schema_sha256
            or row.get("backend_service_configuration_sha256")
            != backend.service_configuration_sha256
            or row.get("backend_service_deployment_sha256")
            != backend.service_deployment_sha256
        ):
            raise ValidationProductionReservationLaterHeadConsistencyError(
                "checkpoint transition backend trust scope is cross-wired"
            )
        valid_from = _parse_utc(backend.valid_from_utc, name="backend valid_from")
        valid_until = _parse_utc(backend.valid_until_utc, name="backend valid_until")
        if not valid_from <= committed_at < valid_until or not valid_from <= checked_at < valid_until:
            raise ValidationProductionReservationLaterHeadConsistencyError(
                "checkpoint transition backend key is outside its validity window"
            )
        expected_transition = _sha256(row)
        if transition_sha256 != expected_transition:
            raise ValidationProductionReservationLaterHeadConsistencyError(
                "checkpoint transition logical SHA-256 verification failed"
            )
        payload = {**row, "transition_sha256": transition_sha256}
        try:
            valid = verify_ed25519(
                _canonical_bytes(payload), signature["value"], backend.verification_key
            )
        except ReferenceMinimizationValidationEd25519Error as exc:
            raise ValidationProductionReservationLaterHeadConsistencyError(
                "checkpoint transition Ed25519 verifier is unavailable"
            ) from exc
        if not valid:
            raise ValidationProductionReservationLaterHeadConsistencyError(
                "checkpoint transition backend signature verification failed"
            )
        if transaction in transaction_ids or transition_sha256 in transition_ids:
            raise ValidationProductionReservationLaterHeadConsistencyError(
                "checkpoint transition path contains a duplicate transaction or link"
            )
        transaction_ids.add(transaction)
        transition_ids.add(transition_sha256)
        selected_key_ids.add(key_id)
        artifact_identities.update(
            {
                transition_sha256,
                transaction,
                committed_checkpoint,
                committed_root,
                backend.backend_identity_sha256,
                _raw_sha256(backend.verification_key),
                backend.service_binary_sha256,
                backend.service_schema_sha256,
                backend.service_configuration_sha256,
                backend.service_deployment_sha256,
            }
        )
        normalized.append(
            {**row, "transition_sha256": transition_sha256, "backend_signature": signature}
        )
        previous_sequence = committed_sequence
        previous_checkpoint = committed_checkpoint
        previous_root = committed_root
        previous_link = transition_sha256
        previous_time = committed_at
    return normalized, _parse_utc(
        normalized[0]["committed_at_utc"], name="first transition committed_at"
    ), previous_time, selected_key_ids, artifact_identities


def _verify_slot_retention(
    value: object,
    *,
    anchor_slots: tuple[tuple[str, str, str], ...],
    later_root_sha256: str,
) -> list[dict[str, Any]]:
    if type(value) is not list or len(value) != len(_SLOT_KINDS):
        raise ValidationProductionReservationLaterHeadConsistencyError(
            "later-head slot-retention proofs must contain exactly three rows"
        )
    normalized: list[dict[str, Any]] = []
    for (expected_kind, expected_slot, expected_transaction), raw_row in zip(
        anchor_slots, value, strict=True
    ):
        if type(raw_row) is not dict or set(raw_row) != {
            "slot_kind",
            "slot_sha256",
            "consumed_by_registry_transaction_sha256",
            "sibling_sha256s",
        }:
            raise ValidationProductionReservationLaterHeadConsistencyError(
                "later-head slot-retention proof fields are invalid"
            )
        if (
            raw_row.get("slot_kind") != expected_kind
            or raw_row.get("slot_sha256") != expected_slot
            or raw_row.get("consumed_by_registry_transaction_sha256")
            != expected_transaction
        ):
            raise ValidationProductionReservationLaterHeadConsistencyError(
                "later-head slot-retention proof is reordered or cross-wired"
            )
        siblings = raw_row.get("sibling_sha256s")
        if type(siblings) is not list:
            raise ValidationProductionReservationLaterHeadConsistencyError(
                "later-head slot-retention sibling path is invalid"
            )
        leaf = production_reservation_sparse_merkle_consumed_leaf_sha256(
            slot_sha256=expected_slot,
            registry_transaction_sha256=expected_transaction,
        )
        try:
            observed_root = production_reservation_sparse_merkle_root_sha256(
                slot_sha256=expected_slot,
                leaf_sha256=leaf,
                sibling_sha256s=siblings,
            )
        except ValidationProductionReservationRegistryProofError as exc:
            raise ValidationProductionReservationLaterHeadConsistencyError(
                "later-head slot-retention sparse-Merkle proof is invalid"
            ) from exc
        if observed_root != later_root_sha256:
            raise ValidationProductionReservationLaterHeadConsistencyError(
                "original consumed reservation slot is not retained in the later state root"
            )
        normalized.append(
            {
                "slot_kind": expected_kind,
                "slot_sha256": expected_slot,
                "consumed_by_registry_transaction_sha256": expected_transaction,
                "sibling_sha256s": [
                    _require_sha256(item, name="slot-retention sibling")
                    for item in siblings
                ],
            }
        )
    return normalized


@dataclass(frozen=True, slots=True, init=False)
class ProductionReservationLaterHeadConsistencyVerification:
    proof_sha256: str
    raw_proof_sha256: str
    raw_proof_byte_count: int
    lane: str
    anchor_head_receipt_sha256: str
    anchor_raw_head_receipt_sha256: str
    anchor_registry_proof_sha256: str
    anchor_raw_registry_proof_sha256: str
    registry_realm_identity_sha256: str
    registry_epoch: str
    anchor_registry_sequence: int
    anchor_native_registry_checkpoint_sha256: str
    anchor_registry_state_root_sha256: str
    later_registry_sequence: int
    later_native_registry_checkpoint_sha256: str
    later_registry_state_root_sha256: str
    checkpoint_transition_count: int
    checkpoint_transition_path_sha256: str
    retained_slot_set_sha256: str
    head_observer_identity_sha256: str
    head_observer_key_id: str
    head_observer_public_key_sha256: str
    proof_issued_at_utc: str
    later_head_observed_at_utc: str
    current_status_tail_snapshot_sha256: str
    current_raw_status_tail_sha256: str
    current_status_tail_sequence: int
    current_status_tail_external_log_checkpoint_sha256: str
    authenticated_head_receipt_reverified: bool = True
    adjacent_checkpoint_lineage_verified: bool = True
    original_consumed_slots_retained_verified: bool = True
    observer_signed_later_head_verified: bool = True
    caller_expected_later_head_match_verified: bool = True
    post_consistency_status_descendant_reverified: bool = True
    later_head_consistency_verified: bool = True
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
) -> ProductionReservationLaterHeadConsistencyVerification:
    instance = object.__new__(ProductionReservationLaterHeadConsistencyVerification)
    for name, value in values.items():
        object.__setattr__(instance, name, value)
    for name in (
        "authenticated_head_receipt_reverified",
        "adjacent_checkpoint_lineage_verified",
        "original_consumed_slots_retained_verified",
        "observer_signed_later_head_verified",
        "caller_expected_later_head_match_verified",
        "post_consistency_status_descendant_reverified",
        "later_head_consistency_verified",
    ):
        object.__setattr__(instance, name, True)
    for name in (*_ACTUAL_FACT_POLICY, *_CLAIM_POLICY):
        object.__setattr__(instance, name, False)
    object.__setattr__(instance, "_verification_seal", _VERIFICATION_SEAL)
    return instance


def verify_external_production_reservation_later_head_consistency_proof(
    source: bytes,
    *,
    authenticated_head_receipt_reverification_arguments: dict[str, object],
    expected_proof_sha256: str,
    expected_raw_proof_sha256: str,
    expected_later_registry_sequence: int,
    expected_later_native_registry_checkpoint_sha256: str,
    expected_later_registry_state_root_sha256: str,
    trusted_registry_backend_keys: dict[
        str, ProductionReservationRegistryBackendTrustAnchor
    ],
    trusted_registry_head_observer_keys: dict[
        str, ProductionReservationRegistryHeadObserverTrustAnchor
    ],
    checked_at: datetime,
) -> ProductionReservationLaterHeadConsistencyVerification:
    """Verify one caller-pinned same-epoch later-head path without promotion."""

    checked = _parse_utc(
        _format_utc(checked_at, name="later-head checked_at"),
        name="later-head checked_at",
    )
    head_arguments = _snapshot_head_arguments(
        authenticated_head_receipt_reverification_arguments
    )
    backend_snapshot = _snapshot(
        trusted_registry_backend_keys, name="registry backend trust"
    )
    observer_snapshot = _snapshot(
        trusted_registry_head_observer_keys, name="registry head-observer trust"
    )
    backend_trust = _backend_trust_map(backend_snapshot)
    observer_trust = _observer_trust_map(observer_snapshot)
    _require_same_external_trust_domain(
        head_arguments, backend_trust, observer_trust
    )
    raw, loaded = _load_canonical_document(
        source,
        maximum_bytes=PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_MAX_BYTES,
        artifact_name="later-head consistency proof",
    )
    if _raw_sha256(raw) != _require_sha256(
        expected_raw_proof_sha256, name="expected raw later-head consistency proof"
    ):
        raise ValidationProductionReservationLaterHeadConsistencyError(
            "raw later-head consistency proof identity is cross-wired"
        )
    observer_signature = _signature(
        loaded.pop("head_observer_signature", None), name="later-head observer"
    )
    proof_sha256 = loaded.pop("proof_sha256", None)
    expected_proof = _require_sha256(
        expected_proof_sha256, name="expected later-head consistency proof"
    )
    if proof_sha256 != expected_proof or proof_sha256 != _sha256(loaded):
        raise ValidationProductionReservationLaterHeadConsistencyError(
            "later-head consistency proof logical SHA-256 verification failed"
        )

    anchor = _reverify_head_receipt(head_arguments, checked_at=checked)
    transitions, first_commit, last_commit, backend_key_ids, artifact_identities = (
        _verify_transition_rows(
            loaded.get("checkpoint_transition_rows"),
            anchor=anchor,
            backend_trust=backend_trust,
            checked_at=checked,
        )
    )
    last = transitions[-1]
    later_sequence = _require_exact_int(
        loaded.get("later_registry_sequence"),
        name="later registry sequence",
        minimum=1,
    )
    later_checkpoint = _require_sha256(
        loaded.get("later_native_registry_checkpoint_sha256"),
        name="later native registry checkpoint",
    )
    later_root = _require_sha256(
        loaded.get("later_registry_state_root_sha256"),
        name="later registry state root",
    )
    expected_sequence = _require_exact_int(
        expected_later_registry_sequence,
        name="caller-expected later registry sequence",
        minimum=1,
    )
    expected_checkpoint = _require_sha256(
        expected_later_native_registry_checkpoint_sha256,
        name="caller-expected later native registry checkpoint",
    )
    expected_root = _require_sha256(
        expected_later_registry_state_root_sha256,
        name="caller-expected later registry state root",
    )
    if (
        later_sequence != expected_sequence
        or later_checkpoint != expected_checkpoint
        or later_root != expected_root
        or later_sequence != last["committed_registry_sequence"]
        or later_checkpoint != last["committed_native_registry_checkpoint_sha256"]
        or later_root != last["committed_registry_state_root_sha256"]
    ):
        raise ValidationProductionReservationLaterHeadConsistencyError(
            "later registry head differs from the path or caller expectation"
        )
    if later_sequence <= anchor.registry_sequence:
        raise ValidationProductionReservationLaterHeadConsistencyError(
            "later registry head does not advance the anchor"
        )
    anchor_slots = _anchor_slot_rows(
        head_arguments, transaction_sha256=anchor.registry_transaction_sha256
    )
    retention = _verify_slot_retention(
        loaded.get("retained_slot_inclusion_proofs"),
        anchor_slots=anchor_slots,
        later_root_sha256=later_root,
    )
    path_sha256 = _sha256(transitions)
    retention_sha256 = _sha256(retention)

    observer_key_id = observer_signature["key_id"]
    observer = observer_trust.get(observer_key_id)
    if type(observer) is not ProductionReservationRegistryHeadObserverTrustAnchor:
        raise ValidationProductionReservationLaterHeadConsistencyError(
            "later-head observer key is not trusted"
        )
    if (
        observer.registry_realm_identity_sha256
        != anchor.registry_realm_identity_sha256
        or observer.registry_epoch != anchor.registry_epoch
    ):
        raise ValidationProductionReservationLaterHeadConsistencyError(
            "later-head observer trust scope is cross-wired"
        )
    observer_public_sha256 = _raw_sha256(observer.verification_key)
    proof_issued = _parse_utc(
        loaded.get("proof_issued_at_utc"), name="later-head proof issued_at"
    )
    observed = _parse_utc(
        loaded.get("later_head_observed_at_utc"), name="later head observed_at"
    )
    expires = _parse_utc(
        loaded.get("expires_at_utc"), name="later-head proof expires_at"
    )
    status, current_raw_status, revoked_keys, revoked_artifacts, superseded = (
        _current_status_tail(head_arguments)
    )
    current_status_issued = _parse_utc(
        status.get("issued_at_utc"), name="post-consistency status issued_at"
    )
    if not (
        _parse_utc(anchor.head_observed_at_utc, name="anchor head observed_at")
        < first_commit
        <= last_commit
        <= proof_issued
        and _parse_utc(
            anchor.receipt_issued_at_utc, name="anchor receipt issued_at"
        )
        <= proof_issued
        <= observed
        < current_status_issued
        <= checked
        < expires
    ):
        raise ValidationProductionReservationLaterHeadConsistencyError(
            "later-head consistency proof has invalid causal time"
        )
    if (
        checked - observed > PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_MAX_AGE
        or expires - proof_issued
        > PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_MAX_VALIDITY
    ):
        raise ValidationProductionReservationLaterHeadConsistencyError(
            "later-head consistency proof is stale or overlong"
        )
    observer_valid_from = _parse_utc(
        observer.valid_from_utc, name="observer valid_from"
    )
    observer_valid_until = _parse_utc(
        observer.valid_until_utc, name="observer valid_until"
    )
    if not (
        observer_valid_from <= proof_issued < observer_valid_until
        and observer_valid_from <= observed < observer_valid_until
        and observer_valid_from <= checked < observer_valid_until
    ):
        raise ValidationProductionReservationLaterHeadConsistencyError(
            "later-head observer key is outside its validity window"
        )
    if (backend_key_ids | {observer_key_id}) & revoked_keys:
        raise ValidationProductionReservationLaterHeadConsistencyError(
            "later-head backend or observer key is revoked"
        )
    current_status_snapshot = _require_sha256(
        status.get("snapshot_sha256"), name="post-consistency status snapshot"
    )
    current_status_sequence = _require_exact_int(
        status.get("status_sequence"),
        name="post-consistency status sequence",
        minimum=1,
    )
    current_status_checkpoint = _require_sha256(
        status.get("external_log_checkpoint_sha256"),
        name="post-consistency status checkpoint",
    )
    artifact_identities.update(
        {
            proof_sha256,
            _raw_sha256(raw),
            FROZEN_VALIDATION_PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_CONTRACT_SHA256,
            anchor.head_receipt_sha256,
            anchor.raw_head_receipt_sha256,
            anchor.registry_proof_sha256,
            anchor.raw_registry_proof_sha256,
            anchor.native_registry_checkpoint_sha256,
            anchor.registry_state_root_sha256,
            _anchor_link_sha256(anchor),
            later_checkpoint,
            later_root,
            path_sha256,
            retention_sha256,
            observer.observer_identity_sha256,
            observer_public_sha256,
            observer.observer_deployment_sha256,
            current_status_snapshot,
            _raw_sha256(current_raw_status),
            current_status_checkpoint,
        }
    )
    if artifact_identities & (revoked_artifacts | superseded):
        raise ValidationProductionReservationLaterHeadConsistencyError(
            "later-head consistency proof identity is revoked or superseded"
        )

    expected_projection: dict[str, Any] = {
        "schema_id": PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_PROOF_SCHEMA_ID,
        "contract_sha256": FROZEN_VALIDATION_PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_CONTRACT_SHA256,
        "evidence_class": "synthetic_validation_production",
        "artifact_stage": "external_same_epoch_later_head_consistency_proof",
        "lane": anchor.lane,
        "anchor_head_receipt_sha256": anchor.head_receipt_sha256,
        "anchor_raw_head_receipt_sha256": anchor.raw_head_receipt_sha256,
        "anchor_registry_proof_sha256": anchor.registry_proof_sha256,
        "anchor_raw_registry_proof_sha256": anchor.raw_registry_proof_sha256,
        "anchor_sequence_five_commit_sha256": anchor.sequence_five_commit_sha256,
        "anchor_raw_sequence_five_commit_sha256": (
            anchor.raw_sequence_five_commit_sha256
        ),
        "anchor_registry_transaction_sha256": anchor.registry_transaction_sha256,
        "registry_realm_identity_sha256": anchor.registry_realm_identity_sha256,
        "registry_epoch": anchor.registry_epoch,
        "anchor_registry_sequence": anchor.registry_sequence,
        "anchor_native_registry_checkpoint_sha256": (
            anchor.native_registry_checkpoint_sha256
        ),
        "anchor_registry_state_root_sha256": anchor.registry_state_root_sha256,
        "anchor_status_tail_snapshot_sha256": anchor.status_tail_snapshot_sha256,
        "anchor_raw_status_tail_sha256": anchor.raw_status_tail_sha256,
        "anchor_status_tail_sequence": anchor.status_tail_sequence,
        "anchor_status_tail_external_log_checkpoint_sha256": (
            anchor.status_tail_external_log_checkpoint_sha256
        ),
        "later_registry_sequence": later_sequence,
        "later_native_registry_checkpoint_sha256": later_checkpoint,
        "later_registry_state_root_sha256": later_root,
        "checkpoint_transition_rows": transitions,
        "checkpoint_transition_path_sha256": path_sha256,
        "retained_slot_inclusion_proofs": retention,
        "retained_slot_set_sha256": retention_sha256,
        "head_observer_identity_sha256": observer.observer_identity_sha256,
        "head_observer_key_id": observer_key_id,
        "head_observer_public_key_sha256": observer_public_sha256,
        "head_observer_deployment_sha256": observer.observer_deployment_sha256,
        "proof_issued_at_utc": loaded["proof_issued_at_utc"],
        "later_head_observed_at_utc": loaded["later_head_observed_at_utc"],
        "expires_at_utc": loaded["expires_at_utc"],
        "consistency_outcome": "observer_attested_exact_adjacent_same_epoch_path",
        "authenticated_head_receipt_reverified": True,
        "adjacent_checkpoint_lineage_verified": True,
        "original_consumed_slots_retained_verified": True,
        "observer_signed_later_head_verified": True,
        "caller_expected_later_head_match_verified": True,
        "later_head_consistency_verified": True,
        **_ACTUAL_FACT_POLICY,
        **_CLAIM_POLICY,
        "superseded": False,
        "revoked": False,
    }
    if _canonical_bytes(loaded) != _canonical_bytes(expected_projection):
        raise ValidationProductionReservationLaterHeadConsistencyError(
            "later-head consistency proof fields are omitted or transplanted"
        )
    observer_payload = {**expected_projection, "proof_sha256": proof_sha256}
    try:
        observer_valid = verify_ed25519(
            _canonical_bytes(observer_payload),
            observer_signature["value"],
            observer.verification_key,
        )
    except ReferenceMinimizationValidationEd25519Error as exc:
        raise ValidationProductionReservationLaterHeadConsistencyError(
            "later-head observer Ed25519 verifier is unavailable"
        ) from exc
    if not observer_valid:
        raise ValidationProductionReservationLaterHeadConsistencyError(
            "later-head observer signature verification failed"
        )
    return _new_verification(
        proof_sha256=proof_sha256,
        raw_proof_sha256=_raw_sha256(raw),
        raw_proof_byte_count=len(raw),
        lane=anchor.lane,
        anchor_head_receipt_sha256=anchor.head_receipt_sha256,
        anchor_raw_head_receipt_sha256=anchor.raw_head_receipt_sha256,
        anchor_registry_proof_sha256=anchor.registry_proof_sha256,
        anchor_raw_registry_proof_sha256=anchor.raw_registry_proof_sha256,
        registry_realm_identity_sha256=anchor.registry_realm_identity_sha256,
        registry_epoch=anchor.registry_epoch,
        anchor_registry_sequence=anchor.registry_sequence,
        anchor_native_registry_checkpoint_sha256=(
            anchor.native_registry_checkpoint_sha256
        ),
        anchor_registry_state_root_sha256=anchor.registry_state_root_sha256,
        later_registry_sequence=later_sequence,
        later_native_registry_checkpoint_sha256=later_checkpoint,
        later_registry_state_root_sha256=later_root,
        checkpoint_transition_count=len(transitions),
        checkpoint_transition_path_sha256=path_sha256,
        retained_slot_set_sha256=retention_sha256,
        head_observer_identity_sha256=observer.observer_identity_sha256,
        head_observer_key_id=observer_key_id,
        head_observer_public_key_sha256=observer_public_sha256,
        proof_issued_at_utc=loaded["proof_issued_at_utc"],
        later_head_observed_at_utc=loaded["later_head_observed_at_utc"],
        current_status_tail_snapshot_sha256=current_status_snapshot,
        current_raw_status_tail_sha256=_raw_sha256(current_raw_status),
        current_status_tail_sequence=current_status_sequence,
        current_status_tail_external_log_checkpoint_sha256=(
            current_status_checkpoint
        ),
    )


def _contract_projection() -> dict[str, Any]:
    return {
        "schema_id": VALIDATION_PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_CONTRACT_SCHEMA_ID,
        "contract_id": VALIDATION_PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_CONTRACT_ID,
        "contract_version": VALIDATION_PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_CONTRACT_VERSION,
        "frozen_at_utc": VALIDATION_PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_FROZEN_AT_UTC,
        "purpose": {
            "verifier_only": True,
            "external_registry_or_observer_implemented_by_package": False,
            "authenticated_head_receipt_fresh_reverification_required": True,
            "reverification_inputs_snapshotted_before_use": True,
            "same_epoch_adjacent_checkpoint_path_supported": True,
            "original_consumed_slot_retention_supported": True,
            "caller_expected_later_head_match_supported": True,
            "post_consistency_status_denial_fence_required": True,
            "global_latest_head_verification_supported": False,
            "global_non_equivocation_supported": False,
            "epoch_transition_continuity_supported": False,
            "verification_result_is_not_an_authorization_token": True,
            "downstream_raw_proof_reverification_required": True,
        },
        "schemas": {
            "consistency_proof": PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_PROOF_SCHEMA_ID,
            "checkpoint_transition": PRODUCTION_RESERVATION_LATER_HEAD_TRANSITION_SCHEMA_ID,
        },
        "transport": {
            "canonical_ascii_json_required": True,
            "duplicate_keys_rejected": True,
            "maximum_bytes": PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_MAX_BYTES,
            "maximum_transition_count": PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_MAX_TRANSITIONS,
            "maximum_json_integer_digits": PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_MAX_JSON_INTEGER_DIGITS,
        },
        "consistency_path": {
            "realm_and_epoch_fixed_to_anchor": True,
            "strict_sequence_adjacency_required": True,
            "prior_checkpoint_and_state_root_linkage_required": True,
            "strict_commit_time_order_required": True,
            "each_transition_backend_signature_required": True,
            "complete_path_observer_signature_required": True,
            "anchor_three_consumed_slots_must_be_included_in_later_root": True,
            "retained_slot_fact_scope": "anchor_attested_consumed_leaf_encodings_in_selected_later_root_only",
            "actual_slot_consumption_inferred": False,
            "path_selects_one_caller_pinned_fork_only": True,
            "separately_pinned_sibling_paths_can_each_verify": True,
        },
        "trust_and_freshness": {
            "signature_algorithm": "Ed25519",
            "backend_and_observer_trust_exactly_equal_anchor_receipt_domain": True,
            "selected_keys_valid_at_signing_observation_and_check": True,
            "post_consistency_status_denials_applied": True,
            "later_head_observed_at_is_observer_countersign_completion_time": True,
            "causal_time_order": "anchor_head_observation_lt_path_commits_le_proof_issue_and_anchor_receipt_issue_le_proof_issue_le_head_observation_lt_current_status_le_check_lt_expiry",
            "maximum_age_seconds": int(
                PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_MAX_AGE.total_seconds()
            ),
            "maximum_validity_seconds": int(
                PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_MAX_VALIDITY.total_seconds()
            ),
            "maximum_anchors_per_role": PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_MAX_TRUST_ANCHORS,
            "reverification_snapshot_maximum_nodes": PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_MAX_SNAPSHOT_NODES,
            "reverification_snapshot_maximum_depth": PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_MAX_SNAPSHOT_DEPTH,
        },
        "verified_facts_when_external_proof_is_supplied": {
            "authenticated_head_receipt_reverified": True,
            "adjacent_checkpoint_lineage_verified": True,
            "original_consumed_slots_retained_verified": True,
            "observer_signed_later_head_verified": True,
            "caller_expected_later_head_match_verified": True,
            "post_consistency_status_descendant_reverified": True,
            "later_head_consistency_verified": True,
            **_ACTUAL_FACT_POLICY,
        },
        "current_provisioning": {
            "external_consistency_proof_present": False,
            "authenticated_anchor_receipt_present": False,
            "trusted_backend_key_present": False,
            "trusted_observer_key_present": False,
            "post_consistency_status_descendant_present": False,
            "production_execution_authorized": False,
            "production_results_collected": False,
        },
        "claim_policy": dict(_CLAIM_POLICY),
        "blockers": list(_BLOCKERS),
        "superseded": False,
        "revoked": False,
    }


def validation_production_reservation_later_head_consistency_contract_document() -> dict[
    str, Any
]:
    projection = _contract_projection()
    document = {**projection, "contract_sha256": _sha256(projection)}
    if document["contract_sha256"] != (
        FROZEN_VALIDATION_PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_CONTRACT_SHA256
    ):
        raise ValidationProductionReservationLaterHeadConsistencyError(
            "frozen later-head consistency contract SHA-256 drifted"
        )
    return document


def require_validation_production_reservation_later_head_consistency_contract_document(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if type(payload) is not dict:
        raise ValidationProductionReservationLaterHeadConsistencyError(
            "later-head consistency contract must be an exact built-in dict"
        )
    observed = json.loads(_canonical_bytes(payload).decode("ascii"))
    expected = validation_production_reservation_later_head_consistency_contract_document()
    if _canonical_bytes(observed) != _canonical_bytes(expected):
        raise ValidationProductionReservationLaterHeadConsistencyError(
            "later-head consistency contract does not match the frozen record"
        )
    return observed


def validation_production_reservation_later_head_consistency_decision() -> dict[
    str, Any
]:
    contract = validation_production_reservation_later_head_consistency_contract_document()
    return {
        "contract_sha256": contract["contract_sha256"],
        "verifier_implemented": True,
        "external_registry_or_observer_implemented_by_package": False,
        "external_consistency_proof_present": False,
        "authenticated_anchor_receipt_present": False,
        "post_consistency_status_descendant_present": False,
        "later_head_consistency_verified": False,
        **_ACTUAL_FACT_POLICY,
        **_CLAIM_POLICY,
        "blockers": list(_BLOCKERS),
    }


__all__ = [
    "FROZEN_LEGACY_VALIDATION_PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_CONTRACT_SHA256_V1",
    "FROZEN_VALIDATION_PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_CONTRACT_SHA256",
    "PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_MAX_AGE",
    "PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_MAX_BYTES",
    "PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_MAX_SNAPSHOT_DEPTH",
    "PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_MAX_SNAPSHOT_NODES",
    "PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_MAX_TRANSITIONS",
    "PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_MAX_VALIDITY",
    "PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_PROOF_SCHEMA_ID",
    "PRODUCTION_RESERVATION_LATER_HEAD_TRANSITION_SCHEMA_ID",
    "ProductionReservationLaterHeadConsistencyVerification",
    "VALIDATION_PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_CONTRACT_ID",
    "VALIDATION_PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_CONTRACT_SCHEMA_ID",
    "VALIDATION_PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_CONTRACT_VERSION",
    "ValidationProductionReservationLaterHeadConsistencyError",
    "require_validation_production_reservation_later_head_consistency_contract_document",
    "validation_production_reservation_later_head_consistency_contract_document",
    "validation_production_reservation_later_head_consistency_decision",
    "verify_external_production_reservation_later_head_consistency_proof",
]
