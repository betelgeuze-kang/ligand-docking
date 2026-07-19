"""Verify an external same-epoch reservation-registry transaction proof.

The sequence-five reservation companion verifies a registry/witness attestation,
but cannot by itself establish that a serializable backend performed compare and
set or consumed globally unique slots.  This module adds a verifier-only proof
boundary.  It freshly re-verifies sequence five, validates sparse-Merkle
``absent -> consumed`` transitions for the permit, authorization nonce, and
predecessor slots, verifies distinct backend and head-observer signatures, and
requires the resulting native checkpoint to equal a caller-supplied expected head.

The caller-supplied expected head is only an equality input.  This verifier does
not authenticate its provenance or prove that it is the global latest head.

The proof is deliberately same-epoch and exact-head only.  It does not prove
realm-wide non-equivocation, epoch-transition continuity, later-head
consistency, status-log compare and set, or production execution authority.
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
from betelgeuze_engine_v2.physics.validation_production_reservation_custody_extension import (
    PRODUCTION_RESERVATION_MAX_SIGNED_TRANSPORT_BYTES,
    ProductionAtomicReservationCommitVerification,
    ValidationProductionReservationCustodyExtensionError,
    verify_signed_production_atomic_reservation_commit,
)


VALIDATION_PRODUCTION_RESERVATION_REGISTRY_PROOF_CONTRACT_SCHEMA_ID = (
    "betelgeuze.engine_v2_validation_production_reservation_registry_proof_contract/1.0.0"
)
VALIDATION_PRODUCTION_RESERVATION_REGISTRY_PROOF_CONTRACT_ID = (
    "engine_v2_validation_production_reservation_registry_proof/1.0.0"
)
VALIDATION_PRODUCTION_RESERVATION_REGISTRY_PROOF_CONTRACT_VERSION = "1.0.0"
VALIDATION_PRODUCTION_RESERVATION_REGISTRY_PROOF_FROZEN_AT_UTC = (
    "2026-07-19T15:30:00Z"
)
PRODUCTION_RESERVATION_REGISTRY_TRANSACTION_PROOF_SCHEMA_ID = (
    "betelgeuze.engine_v2_external_reservation_registry_transaction_proof/1.0.0"
)
PRODUCTION_RESERVATION_NATIVE_REGISTRY_CHECKPOINT_SCHEMA_ID = (
    "betelgeuze.engine_v2_external_reservation_registry_native_checkpoint/1.0.0"
)
PRODUCTION_RESERVATION_SPARSE_MERKLE_LEAF_SCHEMA_ID = (
    "betelgeuze.engine_v2_reservation_registry_consumed_slot_leaf/1.0.0"
)
PRODUCTION_RESERVATION_SPARSE_MERKLE_DEPTH = 256
PRODUCTION_RESERVATION_REGISTRY_PROOF_MAX_BYTES = 1_048_576
PRODUCTION_RESERVATION_REGISTRY_PROOF_MAX_TRUST_ANCHORS = 16
PRODUCTION_RESERVATION_REGISTRY_PROOF_MAX_DENIAL_ROWS = 4096
PRODUCTION_RESERVATION_REGISTRY_PROOF_MAX_AGE = timedelta(minutes=15)
FROZEN_VALIDATION_PRODUCTION_RESERVATION_REGISTRY_PROOF_CONTRACT_SHA256 = (
    "a204a1d3859d382fdc248b8c11589d2a7c08560124e2dde8e82b537ce833e756"
)

_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_UTC = timezone.utc
_ZERO_SHA256 = "0" * 64
_VERIFICATION_SEAL = object()
_SLOT_KINDS = (
    "permit",
    "authorization_nonce",
    "predecessor_successor",
)
_SEQ5_REVERIFICATION_FIELDS = {
    "source",
    "raw_intent_bytes",
    "intent_raw_sequence_four_prefix",
    "current_raw_sequence_four_prefix",
    "intent_sequence_four_reverification_arguments",
    "current_sequence_four_reverification_arguments",
    "raw_reservation_record_bytes",
    "expected_run_context",
    "expected_intent_sha256",
    "expected_commit_sha256",
    "expected_raw_commit_sha256",
    "expected_external_launch_nonce_sha256",
    "expected_registry_realm_identity_sha256",
    "expected_registry_epoch",
    "expected_prior_registry_sequence",
    "expected_prior_registry_checkpoint_sha256",
    "expected_committed_registry_sequence",
    "expected_committed_registry_checkpoint_sha256",
    "trusted_registry_authority_keys",
    "trusted_checkpoint_witness_keys",
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
    "external_registry_transaction_proof_not_provisioned",
    "external_registry_backend_key_not_provisioned",
    "external_registry_head_observer_key_not_provisioned",
    "out_of_band_current_registry_head_not_provisioned",
    "status_head_compare_and_set_not_independently_verified",
    "external_registry_non_equivocation_proof_not_provisioned",
    "registry_epoch_transition_continuity_not_provisioned",
    "external_custody_successor_uniqueness_not_provisioned",
    "production_environment_and_later_custody_not_provisioned",
    "production_validation_results_not_collected",
    "two_cpu_hosts_missing",
    "independent_human_result_review_missing",
)


class ValidationProductionReservationRegistryProofError(ValueError):
    """The external registry proof, trust, state path, or expected head is invalid."""


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
        raise ValidationProductionReservationRegistryProofError(
            "reservation registry proof value is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _raw_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    if type(value) is not str or not _SHA256_RE.fullmatch(value):
        raise ValidationProductionReservationRegistryProofError(
            f"{name} must be an exact lowercase SHA-256"
        )
    return value


def _require_token(value: object, *, name: str) -> str:
    if type(value) is not str or not _TOKEN_RE.fullmatch(value):
        raise ValidationProductionReservationRegistryProofError(
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
        raise ValidationProductionReservationRegistryProofError(
            f"{name} must be an exact bounded integer"
        )
    return value


def _parse_utc(value: object, *, name: str) -> datetime:
    if type(value) is not str or not value.endswith("Z"):
        raise ValidationProductionReservationRegistryProofError(
            f"{name} must be canonical UTC"
        )
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=_UTC
        )
    except ValueError as exc:
        raise ValidationProductionReservationRegistryProofError(
            f"{name} must be canonical UTC"
        ) from exc
    return parsed


def _format_utc(value: datetime, *, name: str) -> str:
    if type(value) is not datetime or value.tzinfo is None:
        raise ValidationProductionReservationRegistryProofError(
            f"{name} must be timezone-aware"
        )
    normalized = value.astimezone(_UTC)
    if normalized.microsecond:
        raise ValidationProductionReservationRegistryProofError(
            f"{name} must have whole-second precision"
        )
    return normalized.strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_canonical_document(
    source: bytes,
    *,
    maximum_bytes: int = PRODUCTION_RESERVATION_REGISTRY_PROOF_MAX_BYTES,
    artifact_name: str = "reservation registry proof",
) -> tuple[bytes, dict[str, Any]]:
    if type(source) is not bytes or not source:
        raise ValidationProductionReservationRegistryProofError(
            f"raw {artifact_name} must be exact non-empty bytes"
        )
    if len(source) > maximum_bytes:
        raise ValidationProductionReservationRegistryProofError(
            f"raw {artifact_name} exceeds its transport bound"
        )

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValidationProductionReservationRegistryProofError(
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
        ValidationProductionReservationRegistryProofError,
    ) as exc:
        if isinstance(exc, ValidationProductionReservationRegistryProofError):
            raise
        raise ValidationProductionReservationRegistryProofError(
            f"{artifact_name} is not canonical ASCII JSON"
        ) from exc
    if type(loaded) is not dict or _canonical_bytes(loaded) != source:
        raise ValidationProductionReservationRegistryProofError(
            f"{artifact_name} is not canonical ASCII JSON"
        )
    return source, loaded


def production_reservation_sparse_merkle_node_sha256(
    left_sha256: str,
    right_sha256: str,
) -> str:
    """Hash one ordered sparse-Merkle internal node."""

    left = bytes.fromhex(_require_sha256(left_sha256, name="left node"))
    right = bytes.fromhex(_require_sha256(right_sha256, name="right node"))
    return hashlib.sha256(
        b"betelgeuze.engine_v2_reservation_registry_sparse_node/1\0"
        + left
        + right
    ).hexdigest()


PRODUCTION_RESERVATION_SPARSE_MERKLE_EMPTY_LEAF_SHA256 = hashlib.sha256(
    b"betelgeuze.engine_v2_reservation_registry_empty_leaf/1"
).hexdigest()


def production_reservation_sparse_merkle_default_sha256s() -> tuple[str, ...]:
    """Return the immutable empty-subtree hashes from leaf through root."""

    rows = [PRODUCTION_RESERVATION_SPARSE_MERKLE_EMPTY_LEAF_SHA256]
    for _ in range(PRODUCTION_RESERVATION_SPARSE_MERKLE_DEPTH):
        rows.append(production_reservation_sparse_merkle_node_sha256(rows[-1], rows[-1]))
    return tuple(rows)


def production_reservation_sparse_merkle_consumed_leaf_sha256(
    *,
    slot_sha256: str,
    registry_transaction_sha256: str,
) -> str:
    """Hash the exact consumed-slot leaf committed by the external state root."""

    return _sha256(
        {
            "schema_id": PRODUCTION_RESERVATION_SPARSE_MERKLE_LEAF_SCHEMA_ID,
            "slot_sha256": _require_sha256(slot_sha256, name="slot"),
            "state": "consumed",
            "consumed_by_registry_transaction_sha256": _require_sha256(
                registry_transaction_sha256,
                name="slot-consuming registry transaction",
            ),
        }
    )


def production_reservation_sparse_merkle_root_sha256(
    *,
    slot_sha256: str,
    leaf_sha256: str,
    sibling_sha256s: tuple[str, ...] | list[str],
) -> str:
    """Reconstruct one root from a leaf-to-root 256-sibling path."""

    slot = _require_sha256(slot_sha256, name="sparse-Merkle slot")
    node = _require_sha256(leaf_sha256, name="sparse-Merkle leaf")
    if type(sibling_sha256s) not in (tuple, list) or len(sibling_sha256s) != (
        PRODUCTION_RESERVATION_SPARSE_MERKLE_DEPTH
    ):
        raise ValidationProductionReservationRegistryProofError(
            "sparse-Merkle path must contain exactly 256 siblings"
        )
    index = int(slot, 16)
    for offset, raw_sibling in enumerate(sibling_sha256s):
        sibling = _require_sha256(
            raw_sibling,
            name=f"sparse-Merkle sibling {offset}",
        )
        if index & 1:
            node = production_reservation_sparse_merkle_node_sha256(sibling, node)
        else:
            node = production_reservation_sparse_merkle_node_sha256(node, sibling)
        index >>= 1
    return node


def _slot_sha256(
    *,
    realm_identity_sha256: str,
    kind: str,
    value: object,
) -> str:
    return _sha256(
        {
            "registry_realm_identity_sha256": realm_identity_sha256,
            "slot_kind": kind,
            "slot_value": value,
        }
    )


@dataclass(frozen=True, slots=True)
class ProductionReservationRegistryBackendTrustAnchor:
    backend_identity_sha256: str
    registry_realm_identity_sha256: str
    registry_epoch: str
    service_binary_sha256: str
    service_schema_sha256: str
    service_configuration_sha256: str
    service_deployment_sha256: str
    valid_from_utc: str
    valid_until_utc: str
    verification_key: bytes


@dataclass(frozen=True, slots=True)
class ProductionReservationRegistryHeadObserverTrustAnchor:
    observer_identity_sha256: str
    registry_realm_identity_sha256: str
    registry_epoch: str
    observer_deployment_sha256: str
    valid_from_utc: str
    valid_until_utc: str
    verification_key: bytes


def _require_key(value: object, *, name: str) -> bytes:
    if type(value) is not bytes or len(value) != 32:
        raise ValidationProductionReservationRegistryProofError(
            f"{name} must be exactly 32 public-key bytes"
        )
    return value


def _backend_trust_map(
    value: object,
) -> dict[str, ProductionReservationRegistryBackendTrustAnchor]:
    if (
        type(value) is not dict
        or not value
        or len(value) > PRODUCTION_RESERVATION_REGISTRY_PROOF_MAX_TRUST_ANCHORS
    ):
        raise ValidationProductionReservationRegistryProofError(
            "reservation registry backend trust map is invalid"
        )
    result: dict[str, ProductionReservationRegistryBackendTrustAnchor] = {}
    identities: set[str] = set()
    materials: set[bytes] = set()
    for raw_key_id, anchor in value.items():
        key_id = _require_token(raw_key_id, name="registry backend key id")
        if type(anchor) is not ProductionReservationRegistryBackendTrustAnchor:
            raise ValidationProductionReservationRegistryProofError(
                "registry backend trust map contains an invalid anchor"
            )
        identity = _require_sha256(
            anchor.backend_identity_sha256,
            name="registry backend identity",
        )
        material = _require_key(
            anchor.verification_key,
            name="registry backend verification key",
        )
        if identity in identities or material in materials:
            raise ValidationProductionReservationRegistryProofError(
                "registry backend trust map contains an alias"
            )
        for name, digest in (
            ("registry backend realm", anchor.registry_realm_identity_sha256),
            ("registry backend service binary", anchor.service_binary_sha256),
            ("registry backend service schema", anchor.service_schema_sha256),
            (
                "registry backend service configuration",
                anchor.service_configuration_sha256,
            ),
            ("registry backend service deployment", anchor.service_deployment_sha256),
        ):
            _require_sha256(digest, name=name)
        _require_token(anchor.registry_epoch, name="registry backend epoch")
        valid_from = _parse_utc(anchor.valid_from_utc, name="backend valid_from")
        valid_until = _parse_utc(anchor.valid_until_utc, name="backend valid_until")
        if valid_from >= valid_until:
            raise ValidationProductionReservationRegistryProofError(
                "registry backend trust validity window is invalid"
            )
        identities.add(identity)
        materials.add(material)
        result[key_id] = anchor
    return result


def _observer_trust_map(
    value: object,
) -> dict[str, ProductionReservationRegistryHeadObserverTrustAnchor]:
    if (
        type(value) is not dict
        or not value
        or len(value) > PRODUCTION_RESERVATION_REGISTRY_PROOF_MAX_TRUST_ANCHORS
    ):
        raise ValidationProductionReservationRegistryProofError(
            "reservation registry head-observer trust map is invalid"
        )
    result: dict[str, ProductionReservationRegistryHeadObserverTrustAnchor] = {}
    identities: set[str] = set()
    materials: set[bytes] = set()
    for raw_key_id, anchor in value.items():
        key_id = _require_token(raw_key_id, name="registry head-observer key id")
        if type(anchor) is not ProductionReservationRegistryHeadObserverTrustAnchor:
            raise ValidationProductionReservationRegistryProofError(
                "registry head-observer trust map contains an invalid anchor"
            )
        identity = _require_sha256(
            anchor.observer_identity_sha256,
            name="registry head-observer identity",
        )
        material = _require_key(
            anchor.verification_key,
            name="registry head-observer verification key",
        )
        if identity in identities or material in materials:
            raise ValidationProductionReservationRegistryProofError(
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
        valid_from = _parse_utc(anchor.valid_from_utc, name="observer valid_from")
        valid_until = _parse_utc(anchor.valid_until_utc, name="observer valid_until")
        if valid_from >= valid_until:
            raise ValidationProductionReservationRegistryProofError(
                "registry head-observer trust validity window is invalid"
            )
        identities.add(identity)
        materials.add(material)
        result[key_id] = anchor
    return result


def production_reservation_native_registry_checkpoint_sha256(
    *,
    registry_realm_identity_sha256: str,
    registry_epoch: str,
    prior_registry_sequence: int,
    committed_registry_sequence: int,
    prior_native_registry_checkpoint_sha256: str,
    seq5_prior_registry_checkpoint_sha256: str,
    seq5_committed_registry_checkpoint_sha256: str,
    registry_transaction_sha256: str,
    prior_registry_state_root_sha256: str,
    committed_registry_state_root_sha256: str,
    backend_identity_sha256: str,
    backend_service_binary_sha256: str,
    backend_service_schema_sha256: str,
    backend_service_configuration_sha256: str,
    backend_service_deployment_sha256: str,
    committed_at_utc: str,
) -> str:
    """Hash the backend-native checkpoint pinned by the external observer."""

    prior_sequence = _require_exact_int(
        prior_registry_sequence,
        name="prior registry sequence",
    )
    committed_sequence = _require_exact_int(
        committed_registry_sequence,
        name="committed registry sequence",
        minimum=1,
    )
    if committed_sequence != prior_sequence + 1:
        raise ValidationProductionReservationRegistryProofError(
            "native registry checkpoint is not an adjacent commit"
        )
    return _sha256(
        {
            "schema_id": PRODUCTION_RESERVATION_NATIVE_REGISTRY_CHECKPOINT_SCHEMA_ID,
            "registry_realm_identity_sha256": _require_sha256(
                registry_realm_identity_sha256,
                name="native checkpoint realm",
            ),
            "registry_epoch": _require_token(
                registry_epoch,
                name="native checkpoint epoch",
            ),
            "prior_registry_sequence": prior_sequence,
            "committed_registry_sequence": committed_sequence,
            "prior_native_registry_checkpoint_sha256": _require_sha256(
                prior_native_registry_checkpoint_sha256,
                name="prior native registry checkpoint",
            ),
            "seq5_prior_registry_checkpoint_sha256": _require_sha256(
                seq5_prior_registry_checkpoint_sha256,
                name="sequence-five prior registry checkpoint",
            ),
            "seq5_committed_registry_checkpoint_sha256": _require_sha256(
                seq5_committed_registry_checkpoint_sha256,
                name="sequence-five committed registry checkpoint",
            ),
            "registry_transaction_sha256": _require_sha256(
                registry_transaction_sha256,
                name="registry transaction",
            ),
            "prior_registry_state_root_sha256": _require_sha256(
                prior_registry_state_root_sha256,
                name="prior registry state root",
            ),
            "committed_registry_state_root_sha256": _require_sha256(
                committed_registry_state_root_sha256,
                name="committed registry state root",
            ),
            "backend_identity_sha256": _require_sha256(
                backend_identity_sha256,
                name="registry backend identity",
            ),
            "backend_service_binary_sha256": _require_sha256(
                backend_service_binary_sha256,
                name="registry backend binary",
            ),
            "backend_service_schema_sha256": _require_sha256(
                backend_service_schema_sha256,
                name="registry backend schema",
            ),
            "backend_service_configuration_sha256": _require_sha256(
                backend_service_configuration_sha256,
                name="registry backend configuration",
            ),
            "backend_service_deployment_sha256": _require_sha256(
                backend_service_deployment_sha256,
                name="registry backend deployment",
            ),
            "committed_at_utc": _format_utc(
                _parse_utc(committed_at_utc, name="native checkpoint committed_at"),
                name="native checkpoint committed_at",
            ),
        }
    )


def _signature(value: object, *, name: str) -> dict[str, str]:
    if type(value) is not dict or set(value) != {"algorithm", "key_id", "value"}:
        raise ValidationProductionReservationRegistryProofError(
            f"{name} signature fields are invalid"
        )
    if value["algorithm"] != "Ed25519":
        raise ValidationProductionReservationRegistryProofError(
            f"{name} signature algorithm is unsupported"
        )
    key_id = _require_token(value["key_id"], name=f"{name} key id")
    signature_value = value["value"]
    if type(signature_value) is not str:
        raise ValidationProductionReservationRegistryProofError(
            f"{name} signature value is invalid"
        )
    return {
        "algorithm": "Ed25519",
        "key_id": key_id,
        "value": signature_value,
    }


def _reverify_seq5(
    arguments: object,
    *,
    checked_at: datetime,
) -> ProductionAtomicReservationCommitVerification:
    if type(arguments) is not dict or set(arguments) != _SEQ5_REVERIFICATION_FIELDS:
        raise ValidationProductionReservationRegistryProofError(
            "sequence-five reverification arguments are omitted or aliased"
        )
    try:
        return verify_signed_production_atomic_reservation_commit(
            **arguments,  # type: ignore[arg-type]
            checked_at=checked_at,
        )
    except ValidationProductionReservationCustodyExtensionError as exc:
        raise ValidationProductionReservationRegistryProofError(
            "sequence-five reservation commit reverification failed"
        ) from exc


def _collect_seq5_trust_aliases(
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
            raise ValidationProductionReservationRegistryProofError(
                "sequence-five trust graph exceeds its traversal bound"
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
        visit(value, field_name="sequence_five_reverification_arguments")
    except RecursionError as exc:
        raise ValidationProductionReservationRegistryProofError(
            "sequence-five trust graph is too deeply nested"
        ) from exc
    return key_ids, identities, materials


def _supplied_status_lineage_tail_denials(
    arguments: dict[str, object],
    *,
    minimum_issued_at: datetime,
) -> tuple[set[str], set[str], set[str]]:
    current_prefix = arguments.get("current_raw_sequence_four_prefix")
    if type(current_prefix) is not dict:
        raise ValidationProductionReservationRegistryProofError(
            "verified current sequence-five status prefix is unavailable"
        )
    lineage = current_prefix.get("raw_status_lineage_bytes")
    if type(lineage) not in (list, tuple) or not lineage:
        raise ValidationProductionReservationRegistryProofError(
            "verified current sequence-five status lineage is unavailable"
        )
    raw_status = lineage[-1]
    if type(raw_status) is not bytes:
        raise ValidationProductionReservationRegistryProofError(
            "verified current sequence-five status bytes are unavailable"
        )
    _raw, status = _load_canonical_document(
        raw_status,
        maximum_bytes=PRODUCTION_RESERVATION_MAX_SIGNED_TRANSPORT_BYTES,
        artifact_name="supplied status lineage tail",
    )
    status_issued = _parse_utc(
        status.get("issued_at_utc"),
        name="supplied status lineage-tail issued_at",
    )
    if status_issued < minimum_issued_at:
        raise ValidationProductionReservationRegistryProofError(
            "supplied status lineage tail predates the registry proof observation"
        )
    revoked_key_rows = status.get("revoked_key_rows")
    revoked_artifact_rows = status.get("revoked_artifact_rows")
    supersession_rows = status.get("supersession_rows")
    if not all(type(rows) is list for rows in (
        revoked_key_rows,
        revoked_artifact_rows,
        supersession_rows,
    )):
        raise ValidationProductionReservationRegistryProofError(
            "supplied status lineage-tail denial rows are unavailable"
        )
    revoked_key_pairs: set[tuple[str, str]] = set()
    for row in revoked_key_rows:
        if type(row) is not dict:
            raise ValidationProductionReservationRegistryProofError(
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
            raise ValidationProductionReservationRegistryProofError(
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
            raise ValidationProductionReservationRegistryProofError(
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
        raise ValidationProductionReservationRegistryProofError(
            "supplied status lineage-tail denial rows are duplicated"
        )
    return (
        {key_id for _role, key_id in revoked_key_pairs},
        {digest for _kind, digest in revoked_artifact_pairs},
        {digest for _kind, digest in supersession_pairs},
    )


def _expected_slots(
    commit: ProductionAtomicReservationCommitVerification,
) -> dict[str, str]:
    realm = commit.registry_realm_identity_sha256
    return {
        "permit": _slot_sha256(
            realm_identity_sha256=realm,
            kind="permit",
            value=commit.permit_sha256,
        ),
        "authorization_nonce": _slot_sha256(
            realm_identity_sha256=realm,
            kind="authorization_nonce",
            value=commit.authorization_nonce_sha256,
        ),
        "predecessor_successor": _slot_sha256(
            realm_identity_sha256=realm,
            kind="predecessor_logical_and_raw",
            value={
                "logical_sha256": commit.prior_custody_event_sha256,
                "raw_sha256": commit.prior_raw_custody_event_sha256,
            },
        ),
    }


def _verify_slot_transitions(
    value: object,
    *,
    commit: ProductionAtomicReservationCommitVerification,
    prior_root_sha256: str,
    committed_root_sha256: str,
) -> tuple[dict[str, Any], ...]:
    if type(value) is not list or len(value) != len(_SLOT_KINDS):
        raise ValidationProductionReservationRegistryProofError(
            "registry proof must contain exactly three slot transitions"
        )
    expected_slots = _expected_slots(commit)
    normalized: list[dict[str, Any]] = []
    defaults = production_reservation_sparse_merkle_default_sha256s()
    current_root = prior_root_sha256
    for index, expected_kind in enumerate(_SLOT_KINDS):
        row = value[index]
        if type(row) is not dict or set(row) != {
            "slot_kind",
            "slot_sha256",
            "state_root_before_sha256",
            "state_root_after_sha256",
            "sibling_sha256s",
            "consumed_by_registry_transaction_sha256",
        }:
            raise ValidationProductionReservationRegistryProofError(
                "registry slot transition fields are omitted or aliased"
            )
        if row["slot_kind"] != expected_kind:
            raise ValidationProductionReservationRegistryProofError(
                "registry slot transitions are reordered or cross-wired"
            )
        slot = _require_sha256(row["slot_sha256"], name="registry slot")
        if slot != expected_slots[expected_kind]:
            raise ValidationProductionReservationRegistryProofError(
                "registry slot identity is cross-wired"
            )
        transaction = _require_sha256(
            row["consumed_by_registry_transaction_sha256"],
            name="slot-consuming registry transaction",
        )
        if transaction != commit.registry_transaction_sha256:
            raise ValidationProductionReservationRegistryProofError(
                "registry slot was not consumed by the sequence-five transaction"
            )
        state_root_before = _require_sha256(
            row["state_root_before_sha256"],
            name="registry slot state root before",
        )
        state_root_after = _require_sha256(
            row["state_root_after_sha256"],
            name="registry slot state root after",
        )
        if state_root_before != current_root:
            raise ValidationProductionReservationRegistryProofError(
                "registry slot transitions do not form one adjacent state chain"
            )
        path = row["sibling_sha256s"]
        prior_observed = production_reservation_sparse_merkle_root_sha256(
            slot_sha256=slot,
            leaf_sha256=defaults[0],
            sibling_sha256s=path,
        )
        committed_observed = production_reservation_sparse_merkle_root_sha256(
            slot_sha256=slot,
            leaf_sha256=(
                production_reservation_sparse_merkle_consumed_leaf_sha256(
                    slot_sha256=slot,
                    registry_transaction_sha256=transaction,
                )
            ),
            sibling_sha256s=path,
        )
        if prior_observed != state_root_before:
            raise ValidationProductionReservationRegistryProofError(
                "registry slot was not proven absent in its immediately prior state"
            )
        if committed_observed != state_root_after:
            raise ValidationProductionReservationRegistryProofError(
                "registry slot consumption does not produce its adjacent state root"
            )
        if state_root_before == state_root_after:
            raise ValidationProductionReservationRegistryProofError(
                "registry slot transition did not change the state root"
            )
        normalized.append(
            {
                "slot_kind": expected_kind,
                "slot_sha256": slot,
                "state_root_before_sha256": state_root_before,
                "state_root_after_sha256": state_root_after,
                "sibling_sha256s": list(path),
                "consumed_by_registry_transaction_sha256": transaction,
            }
        )
        current_root = state_root_after
    if current_root != committed_root_sha256:
        raise ValidationProductionReservationRegistryProofError(
            "three registry slot transitions do not produce the committed state root"
        )
    if len(set(expected_slots.values())) != len(_SLOT_KINDS):
        raise ValidationProductionReservationRegistryProofError(
            "reservation registry uniqueness slots alias"
        )
    return tuple(normalized)


def _closed_claims(payload: Mapping[str, Any]) -> None:
    if any(payload.get(name) is not expected for name, expected in _CLAIM_POLICY.items()):
        raise ValidationProductionReservationRegistryProofError(
            "reservation registry proof attempts claim promotion"
        )
    for name in (
        "external_serializable_registry_commit_verified",
        "registry_head_compare_and_set_committed",
        "permit_one_use_slot_consumed",
        "authorization_nonce_slot_consumed",
        "predecessor_successor_slot_consumed",
        "status_head_compare_and_set_committed",
        "custody_successor_uniqueness_enforced",
        "external_registry_non_equivocation_verified",
        "registry_epoch_transition_continuity_verified",
    ):
        if payload.get(name) is not False:
            raise ValidationProductionReservationRegistryProofError(
                "reservation registry proof exceeds its same-epoch exact-head scope"
            )


@dataclass(frozen=True, slots=True, init=False)
class ProductionReservationRegistryTransactionProofVerification:
    proof_sha256: str
    raw_proof_sha256: str
    raw_proof_byte_count: int
    lane: str
    commit_sha256: str
    raw_commit_sha256: str
    registry_transaction_sha256: str
    registry_realm_identity_sha256: str
    registry_epoch: str
    prior_registry_sequence: int
    committed_registry_sequence: int
    committed_native_registry_checkpoint_sha256: str
    prior_registry_state_root_sha256: str
    committed_registry_state_root_sha256: str
    backend_identity_sha256: str
    backend_key_id: str
    backend_public_key_sha256: str
    head_observer_identity_sha256: str
    head_observer_key_id: str
    head_observer_public_key_sha256: str
    proof_issued_at_utc: str
    observed_at_utc: str
    sequence_five_commit_reverified: bool = True
    backend_serializable_transaction_attestation_verified: bool = True
    exact_three_slot_state_transition_verified: bool = True
    caller_expected_native_head_match_verified: bool = True
    observer_signed_native_checkpoint_verified: bool = True
    external_serializable_registry_commit_verified: bool = False
    registry_head_compare_and_set_committed: bool = False
    permit_one_use_slot_consumed: bool = False
    authorization_nonce_slot_consumed: bool = False
    predecessor_successor_slot_consumed: bool = False
    status_head_compare_and_set_committed: bool = False
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
) -> ProductionReservationRegistryTransactionProofVerification:
    instance = object.__new__(ProductionReservationRegistryTransactionProofVerification)
    for name, value in values.items():
        object.__setattr__(instance, name, value)
    for name in (
        "sequence_five_commit_reverified",
        "backend_serializable_transaction_attestation_verified",
        "exact_three_slot_state_transition_verified",
        "caller_expected_native_head_match_verified",
        "observer_signed_native_checkpoint_verified",
    ):
        object.__setattr__(instance, name, True)
    for name in (
        "status_head_compare_and_set_committed",
        "external_serializable_registry_commit_verified",
        "registry_head_compare_and_set_committed",
        "permit_one_use_slot_consumed",
        "authorization_nonce_slot_consumed",
        "predecessor_successor_slot_consumed",
        "custody_successor_uniqueness_enforced",
        "external_registry_non_equivocation_verified",
        "registry_epoch_transition_continuity_verified",
        *_CLAIM_POLICY,
    ):
        object.__setattr__(instance, name, False)
    object.__setattr__(instance, "_verification_seal", _VERIFICATION_SEAL)
    return instance


def verify_external_production_reservation_registry_transaction_proof(
    source: bytes,
    *,
    sequence_five_reverification_arguments: dict[str, object],
    expected_proof_sha256: str,
    expected_raw_proof_sha256: str,
    expected_prior_native_registry_checkpoint_sha256: str,
    expected_caller_registry_sequence: int,
    expected_caller_native_registry_checkpoint_sha256: str,
    trusted_registry_backend_keys: dict[
        str, ProductionReservationRegistryBackendTrustAnchor
    ],
    trusted_registry_head_observer_keys: dict[
        str, ProductionReservationRegistryHeadObserverTrustAnchor
    ],
    checked_at: datetime,
) -> ProductionReservationRegistryTransactionProofVerification:
    """Verify one same-epoch backend attestation and caller-expected-head match."""

    checked = _parse_utc(
        _format_utc(checked_at, name="registry proof checked_at"),
        name="registry proof checked_at",
    )
    raw, loaded = _load_canonical_document(source)
    if _raw_sha256(raw) != _require_sha256(
        expected_raw_proof_sha256,
        name="expected raw reservation registry proof",
    ):
        raise ValidationProductionReservationRegistryProofError(
            "raw reservation registry proof identity is cross-wired"
        )
    backend_signature = _signature(
        loaded.pop("backend_signature", None),
        name="registry backend",
    )
    observer_signature = _signature(
        loaded.pop("head_observer_signature", None),
        name="registry head observer",
    )
    proof_sha256 = loaded.pop("proof_sha256", None)
    expected_proof = _require_sha256(
        expected_proof_sha256,
        name="expected reservation registry proof",
    )
    if proof_sha256 != expected_proof or proof_sha256 != _sha256(loaded):
        raise ValidationProductionReservationRegistryProofError(
            "reservation registry proof logical SHA-256 verification failed"
        )

    commit = _reverify_seq5(
        sequence_five_reverification_arguments,
        checked_at=checked,
    )
    backend_trust = _backend_trust_map(trusted_registry_backend_keys)
    observer_trust = _observer_trust_map(trusted_registry_head_observer_keys)
    backend_key_id = backend_signature["key_id"]
    observer_key_id = observer_signature["key_id"]
    backend = backend_trust.get(backend_key_id)
    observer = observer_trust.get(observer_key_id)
    if type(backend) is not ProductionReservationRegistryBackendTrustAnchor:
        raise ValidationProductionReservationRegistryProofError(
            "reservation registry backend key is not trusted"
        )
    if type(observer) is not ProductionReservationRegistryHeadObserverTrustAnchor:
        raise ValidationProductionReservationRegistryProofError(
            "reservation registry head-observer key is not trusted"
        )
    if (
        backend.registry_realm_identity_sha256
        != commit.registry_realm_identity_sha256
        or observer.registry_realm_identity_sha256
        != commit.registry_realm_identity_sha256
        or backend.registry_epoch != commit.registry_epoch
        or observer.registry_epoch != commit.registry_epoch
    ):
        raise ValidationProductionReservationRegistryProofError(
            "external registry proof trust scope is cross-wired"
        )
    backend_public_sha256 = _raw_sha256(backend.verification_key)
    observer_public_sha256 = _raw_sha256(observer.verification_key)
    external_key_ids = {*backend_trust, *observer_trust}
    external_identities = {
        *(anchor.backend_identity_sha256 for anchor in backend_trust.values()),
        *(anchor.observer_identity_sha256 for anchor in observer_trust.values()),
    }
    external_materials = {
        *(anchor.verification_key for anchor in backend_trust.values()),
        *(anchor.verification_key for anchor in observer_trust.values()),
    }
    if (
        len(external_key_ids) != len(backend_trust) + len(observer_trust)
        or len(external_identities) != len(backend_trust) + len(observer_trust)
        or len(external_materials) != len(backend_trust) + len(observer_trust)
    ):
            raise ValidationProductionReservationRegistryProofError(
                "external registry backend and observer trust roles alias"
            )
    prior_key_ids, prior_identities, prior_materials = _collect_seq5_trust_aliases(
        sequence_five_reverification_arguments
    )
    prior_key_ids.update(
        {
            commit.registry_authority_key_id,
            commit.checkpoint_witness_key_id,
            commit.continuing_custody_key_id,
        }
    )
    prior_identities.update(
        {
            commit.registry_authority_identity_sha256,
            commit.checkpoint_witness_identity_sha256,
            commit.continuing_custody_role_identity_sha256,
        }
    )
    external_public_key_sha256s = {
        _raw_sha256(material) for material in external_materials
    }
    selected_prior_public_key_sha256s = {
        commit.registry_authority_public_key_sha256,
        commit.checkpoint_witness_public_key_sha256,
        commit.continuing_custody_public_key_sha256,
    }
    if (
        external_key_ids & prior_key_ids
        or external_identities & prior_identities
        or external_materials & prior_materials
        or external_public_key_sha256s & selected_prior_public_key_sha256s
    ):
        raise ValidationProductionReservationRegistryProofError(
            "external registry backend, observer, and sequence-five trust roles alias"
        )

    committed_at = _parse_utc(commit.committed_at_utc, name="sequence-five commit time")
    proof_issued_at = _parse_utc(
        loaded.get("proof_issued_at_utc"),
        name="registry proof issued_at",
    )
    observed_at = _parse_utc(loaded.get("observed_at_utc"), name="head observed_at")
    if not committed_at <= proof_issued_at <= observed_at <= checked:
        raise ValidationProductionReservationRegistryProofError(
            "registry proof issuance or head observation has invalid causal time"
        )
    if checked - observed_at > PRODUCTION_RESERVATION_REGISTRY_PROOF_MAX_AGE:
        raise ValidationProductionReservationRegistryProofError(
            "registry head observation is stale"
        )
    backend_valid_from = _parse_utc(backend.valid_from_utc, name="backend valid_from")
    backend_valid_until = _parse_utc(backend.valid_until_utc, name="backend valid_until")
    observer_valid_from = _parse_utc(
        observer.valid_from_utc,
        name="observer valid_from",
    )
    observer_valid_until = _parse_utc(
        observer.valid_until_utc,
        name="observer valid_until",
    )
    if not (
        backend_valid_from <= committed_at < backend_valid_until
        and backend_valid_from <= proof_issued_at < backend_valid_until
        and backend_valid_from <= checked < backend_valid_until
    ):
        raise ValidationProductionReservationRegistryProofError(
            "registry backend key is not valid across commit, proof issuance, and check"
        )
    if not (
        observer_valid_from <= observed_at < observer_valid_until
        and observer_valid_from <= checked < observer_valid_until
    ):
        raise ValidationProductionReservationRegistryProofError(
            "registry head-observer key is not valid across observation and check"
        )
    revoked_keys, revoked_artifacts, superseded_artifacts = (
        _supplied_status_lineage_tail_denials(
            sequence_five_reverification_arguments,
            minimum_issued_at=observed_at,
        )
    )
    if {backend_key_id, observer_key_id} & revoked_keys:
        raise ValidationProductionReservationRegistryProofError(
            "external registry backend or head-observer key is currently revoked"
        )

    prior_native = _require_sha256(
        loaded.get("prior_native_registry_checkpoint_sha256"),
        name="prior native registry checkpoint",
    )
    if prior_native != _require_sha256(
        expected_prior_native_registry_checkpoint_sha256,
        name="expected prior native registry checkpoint",
    ):
        raise ValidationProductionReservationRegistryProofError(
            "prior native registry checkpoint differs from the caller expectation"
        )
    prior_root = _require_sha256(
        loaded.get("prior_registry_state_root_sha256"),
        name="prior registry state root",
    )
    committed_root = _require_sha256(
        loaded.get("committed_registry_state_root_sha256"),
        name="committed registry state root",
    )
    if prior_root == committed_root:
        raise ValidationProductionReservationRegistryProofError(
            "registry state root did not change after slot consumption"
        )
    transitions = _verify_slot_transitions(
        loaded.get("slot_transition_proofs"),
        commit=commit,
        prior_root_sha256=prior_root,
        committed_root_sha256=committed_root,
    )
    native_checkpoint = production_reservation_native_registry_checkpoint_sha256(
        registry_realm_identity_sha256=commit.registry_realm_identity_sha256,
        registry_epoch=commit.registry_epoch,
        prior_registry_sequence=commit.prior_registry_sequence,
        committed_registry_sequence=commit.committed_registry_sequence,
        prior_native_registry_checkpoint_sha256=prior_native,
        seq5_prior_registry_checkpoint_sha256=commit.prior_registry_checkpoint_sha256,
        seq5_committed_registry_checkpoint_sha256=(
            commit.committed_registry_checkpoint_sha256
        ),
        registry_transaction_sha256=commit.registry_transaction_sha256,
        prior_registry_state_root_sha256=prior_root,
        committed_registry_state_root_sha256=committed_root,
        backend_identity_sha256=backend.backend_identity_sha256,
        backend_service_binary_sha256=backend.service_binary_sha256,
        backend_service_schema_sha256=backend.service_schema_sha256,
        backend_service_configuration_sha256=backend.service_configuration_sha256,
        backend_service_deployment_sha256=backend.service_deployment_sha256,
        committed_at_utc=commit.committed_at_utc,
    )
    expected_sequence = _require_exact_int(
        expected_caller_registry_sequence,
        name="caller-expected registry sequence",
        minimum=1,
    )
    expected_checkpoint = _require_sha256(
        expected_caller_native_registry_checkpoint_sha256,
        name="caller-expected native registry checkpoint",
    )
    if expected_sequence != commit.committed_registry_sequence:
        raise ValidationProductionReservationRegistryProofError(
            "caller-expected registry sequence is not the exact committed sequence"
        )
    if expected_checkpoint != native_checkpoint:
        raise ValidationProductionReservationRegistryProofError(
            "committed native checkpoint differs from the caller-expected checkpoint"
        )

    external_artifact_identities = {
        proof_sha256,
        _raw_sha256(raw),
        FROZEN_VALIDATION_PRODUCTION_RESERVATION_REGISTRY_PROOF_CONTRACT_SHA256,
        commit.commit_sha256,
        commit.raw_commit_sha256,
        commit.registry_transaction_sha256,
        commit.registry_realm_identity_sha256,
        commit.prior_registry_checkpoint_sha256,
        commit.committed_registry_checkpoint_sha256,
        prior_native,
        native_checkpoint,
        prior_root,
        committed_root,
        backend.backend_identity_sha256,
        backend_public_sha256,
        backend.service_binary_sha256,
        backend.service_schema_sha256,
        backend.service_configuration_sha256,
        backend.service_deployment_sha256,
        observer.observer_identity_sha256,
        observer_public_sha256,
        observer.observer_deployment_sha256,
        *(row["slot_sha256"] for row in transitions),
    }
    if external_artifact_identities & (
        revoked_artifacts | superseded_artifacts
    ):
        raise ValidationProductionReservationRegistryProofError(
            "external registry proof identity is currently revoked or superseded"
        )

    expected_projection: dict[str, Any] = {
        "schema_id": PRODUCTION_RESERVATION_REGISTRY_TRANSACTION_PROOF_SCHEMA_ID,
        "contract_sha256": (
            FROZEN_VALIDATION_PRODUCTION_RESERVATION_REGISTRY_PROOF_CONTRACT_SHA256
        ),
        "evidence_class": "synthetic_validation_production",
        "artifact_stage": "external_same_epoch_reservation_registry_transaction_proof",
        "lane": commit.lane,
        "sequence_five_commit_sha256": commit.commit_sha256,
        "raw_sequence_five_commit_sha256": commit.raw_commit_sha256,
        "registry_transaction_sha256": commit.registry_transaction_sha256,
        "registry_realm_identity_sha256": commit.registry_realm_identity_sha256,
        "registry_epoch": commit.registry_epoch,
        "prior_registry_sequence": commit.prior_registry_sequence,
        "committed_registry_sequence": commit.committed_registry_sequence,
        "seq5_prior_registry_checkpoint_sha256": (
            commit.prior_registry_checkpoint_sha256
        ),
        "seq5_committed_registry_checkpoint_sha256": (
            commit.committed_registry_checkpoint_sha256
        ),
        "prior_native_registry_checkpoint_sha256": prior_native,
        "committed_native_registry_checkpoint_sha256": native_checkpoint,
        "prior_registry_state_root_sha256": prior_root,
        "committed_registry_state_root_sha256": committed_root,
        "slot_transition_proofs": list(transitions),
        "backend_identity_sha256": backend.backend_identity_sha256,
        "backend_key_id": backend_key_id,
        "backend_public_key_sha256": backend_public_sha256,
        "backend_service_binary_sha256": backend.service_binary_sha256,
        "backend_service_schema_sha256": backend.service_schema_sha256,
        "backend_service_configuration_sha256": (
            backend.service_configuration_sha256
        ),
        "backend_service_deployment_sha256": backend.service_deployment_sha256,
        "head_observer_identity_sha256": observer.observer_identity_sha256,
        "head_observer_key_id": observer_key_id,
        "head_observer_public_key_sha256": observer_public_sha256,
        "head_observer_deployment_sha256": observer.observer_deployment_sha256,
        "committed_at_utc": commit.committed_at_utc,
        "proof_issued_at_utc": loaded["proof_issued_at_utc"],
        "observed_at_utc": loaded["observed_at_utc"],
        "external_transaction_outcome": "backend_attested_committed",
        "external_transaction_isolation": "backend_attested_serializable",
        "backend_serializable_transaction_attestation_verified": True,
        "exact_three_slot_state_transition_verified": True,
        "caller_expected_native_head_match_verified": True,
        "observer_signed_native_checkpoint_verified": True,
        "external_serializable_registry_commit_verified": False,
        "registry_head_compare_and_set_committed": False,
        "permit_one_use_slot_consumed": False,
        "authorization_nonce_slot_consumed": False,
        "predecessor_successor_slot_consumed": False,
        "status_head_compare_and_set_committed": False,
        "custody_successor_uniqueness_enforced": False,
        "external_registry_non_equivocation_verified": False,
        "registry_epoch_transition_continuity_verified": False,
        **_CLAIM_POLICY,
        "superseded": False,
        "revoked": False,
    }
    if _canonical_bytes(loaded) != _canonical_bytes(expected_projection):
        raise ValidationProductionReservationRegistryProofError(
            "external reservation registry proof fields are omitted or transplanted"
        )
    _closed_claims(loaded)
    backend_payload = {**expected_projection, "proof_sha256": proof_sha256}
    observer_payload = {**backend_payload, "backend_signature": backend_signature}
    try:
        backend_valid = verify_ed25519(
            _canonical_bytes(backend_payload),
            backend_signature["value"],
            backend.verification_key,
        )
        observer_valid = verify_ed25519(
            _canonical_bytes(observer_payload),
            observer_signature["value"],
            observer.verification_key,
        )
    except ReferenceMinimizationValidationEd25519Error as exc:
        raise ValidationProductionReservationRegistryProofError(
            "external reservation registry Ed25519 verifier is unavailable"
        ) from exc
    if not backend_valid or not observer_valid:
        raise ValidationProductionReservationRegistryProofError(
            "external reservation registry proof signature verification failed"
        )
    return _new_verification(
        proof_sha256=proof_sha256,
        raw_proof_sha256=_raw_sha256(raw),
        raw_proof_byte_count=len(raw),
        lane=commit.lane,
        commit_sha256=commit.commit_sha256,
        raw_commit_sha256=commit.raw_commit_sha256,
        registry_transaction_sha256=commit.registry_transaction_sha256,
        registry_realm_identity_sha256=commit.registry_realm_identity_sha256,
        registry_epoch=commit.registry_epoch,
        prior_registry_sequence=commit.prior_registry_sequence,
        committed_registry_sequence=commit.committed_registry_sequence,
        committed_native_registry_checkpoint_sha256=native_checkpoint,
        prior_registry_state_root_sha256=prior_root,
        committed_registry_state_root_sha256=committed_root,
        backend_identity_sha256=backend.backend_identity_sha256,
        backend_key_id=backend_key_id,
        backend_public_key_sha256=backend_public_sha256,
        head_observer_identity_sha256=observer.observer_identity_sha256,
        head_observer_key_id=observer_key_id,
        head_observer_public_key_sha256=observer_public_sha256,
        proof_issued_at_utc=loaded["proof_issued_at_utc"],
        observed_at_utc=loaded["observed_at_utc"],
    )


def _contract_projection() -> dict[str, Any]:
    return {
        "schema_id": (
            VALIDATION_PRODUCTION_RESERVATION_REGISTRY_PROOF_CONTRACT_SCHEMA_ID
        ),
        "contract_id": VALIDATION_PRODUCTION_RESERVATION_REGISTRY_PROOF_CONTRACT_ID,
        "contract_version": (
            VALIDATION_PRODUCTION_RESERVATION_REGISTRY_PROOF_CONTRACT_VERSION
        ),
        "frozen_at_utc": (
            VALIDATION_PRODUCTION_RESERVATION_REGISTRY_PROOF_FROZEN_AT_UTC
        ),
        "purpose": {
            "verifier_only": True,
            "external_registry_backend_implemented_by_package": False,
            "sequence_five_fresh_reverification_required": True,
            "same_epoch_backend_attestation_verification_supported": True,
            "exact_three_leaf_transition_verification_supported": True,
            "caller_expected_head_match_verification_supported": True,
            "authenticated_out_of_band_head_receipt_verified": False,
            "actual_global_compare_and_set_proven": False,
            "later_head_consistency_proof_supported": False,
            "epoch_transition_continuity_supported": False,
            "verification_result_is_not_an_authorization_token": True,
            "downstream_raw_proof_reverification_required": True,
        },
        "schemas": {
            "transaction_proof": (
                PRODUCTION_RESERVATION_REGISTRY_TRANSACTION_PROOF_SCHEMA_ID
            ),
            "native_checkpoint": (
                PRODUCTION_RESERVATION_NATIVE_REGISTRY_CHECKPOINT_SCHEMA_ID
            ),
            "consumed_slot_leaf": (
                PRODUCTION_RESERVATION_SPARSE_MERKLE_LEAF_SCHEMA_ID
            ),
        },
        "transport": {
            "canonical_ascii_json_required": True,
            "duplicate_keys_rejected": True,
            "maximum_bytes": PRODUCTION_RESERVATION_REGISTRY_PROOF_MAX_BYTES,
        },
        "sparse_merkle": {
            "depth": PRODUCTION_RESERVATION_SPARSE_MERKLE_DEPTH,
            "key_encoding": "lowercase_sha256_integer_lsb_leaf_to_root",
            "path_order": "leaf_to_root",
            "empty_leaf_sha256": (
                PRODUCTION_RESERVATION_SPARSE_MERKLE_EMPTY_LEAF_SHA256
            ),
            "node_domain_separator": (
                "betelgeuze.engine_v2_reservation_registry_sparse_node/1\\0"
            ),
            "prior_leaf_state": "absent",
            "committed_leaf_state": "consumed_by_exact_registry_transaction",
            "transition_model": "fixed_order_sequential_exact_leaf_updates",
            "same_sibling_path_used_for_each_leaf_before_and_after": True,
            "adjacent_state_roots_must_chain": True,
            "unrelated_leaf_changes_per_transition_accepted": False,
        },
        "transaction": {
            "sequence_adjacency_required": True,
            "sequence_five_logical_and_raw_commit_bound": True,
            "sequence_five_registry_transaction_bound": True,
            "sequence_five_prior_and_committed_checkpoint_bound": True,
            "realm_and_epoch_bound": True,
            "backend_binary_schema_configuration_deployment_bound": True,
            "transaction_outcome_exact_value": "backend_attested_committed",
            "transaction_isolation_exact_value": "backend_attested_serializable",
            "required_slot_transition_order": list(_SLOT_KINDS),
            "caller_expected_exact_head_required": True,
            "one_expected_head_selects_at_most_one_exact_native_checkpoint": True,
            "separate_sibling_pins_do_not_prove_global_non_equivocation": True,
        },
        "trust": {
            "signature_algorithm": "Ed25519",
            "backend_and_head_observer_signatures_required": True,
            "backend_head_observer_seq5_registry_witness_custody_separation_required": (
                True
            ),
            "trust_validity_windows_required": True,
            "supplied_reverified_lineage_tail_must_not_predate_observation": True,
            "supplied_reverified_lineage_tail_denials_enforced": True,
            "global_latest_status_head_verified": False,
            "causal_time_order": "commit_le_proof_issue_le_observation_le_check",
            "selected_signing_keys_must_be_valid_at_check": True,
            "maximum_anchors_per_role": (
                PRODUCTION_RESERVATION_REGISTRY_PROOF_MAX_TRUST_ANCHORS
            ),
            "head_observation_maximum_age_seconds": int(
                PRODUCTION_RESERVATION_REGISTRY_PROOF_MAX_AGE.total_seconds()
            ),
        },
        "verified_facts_when_external_proof_is_supplied": {
            "backend_serializable_transaction_attestation_verified": True,
            "exact_three_slot_state_transition_verified": True,
            "caller_expected_native_head_match_verified": True,
            "observer_signed_native_checkpoint_verified": True,
            "external_serializable_registry_commit_verified": False,
            "registry_head_compare_and_set_committed": False,
            "permit_one_use_slot_consumed": False,
            "authorization_nonce_slot_consumed": False,
            "predecessor_successor_slot_consumed": False,
            "status_head_compare_and_set_committed": False,
            "custody_successor_uniqueness_enforced": False,
            "external_registry_non_equivocation_verified": False,
            "registry_epoch_transition_continuity_verified": False,
        },
        "current_provisioning": {
            "external_proof_present": False,
            "backend_key_present": False,
            "head_observer_key_present": False,
            "out_of_band_current_head_present": False,
            "production_execution_authorized": False,
            "production_results_collected": False,
        },
        "claim_policy": dict(_CLAIM_POLICY),
        "blockers": list(_BLOCKERS),
        "superseded": False,
        "revoked": False,
    }


def validation_production_reservation_registry_proof_contract_document() -> dict[str, Any]:
    projection = _contract_projection()
    document = {**projection, "contract_sha256": _sha256(projection)}
    if (
        document["contract_sha256"]
        != FROZEN_VALIDATION_PRODUCTION_RESERVATION_REGISTRY_PROOF_CONTRACT_SHA256
    ):
        raise ValidationProductionReservationRegistryProofError(
            "frozen reservation registry proof contract SHA-256 drifted"
        )
    return document


def require_validation_production_reservation_registry_proof_contract_document(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if type(payload) is not dict:
        raise ValidationProductionReservationRegistryProofError(
            "reservation registry proof contract must be an exact built-in dict"
        )
    observed = json.loads(_canonical_bytes(payload).decode("ascii"))
    expected = validation_production_reservation_registry_proof_contract_document()
    if _canonical_bytes(observed) != _canonical_bytes(expected):
        raise ValidationProductionReservationRegistryProofError(
            "reservation registry proof contract does not match the frozen record"
        )
    return observed


def validation_production_reservation_registry_proof_decision() -> dict[str, Any]:
    contract = validation_production_reservation_registry_proof_contract_document()
    return {
        "contract_sha256": contract["contract_sha256"],
        "verifier_implemented": True,
        "external_registry_backend_implemented_by_package": False,
        "external_registry_transaction_proof_present": False,
        "external_serializable_registry_commit_verified": False,
        "registry_head_compare_and_set_committed": False,
        "permit_one_use_slot_consumed": False,
        "authorization_nonce_slot_consumed": False,
        "predecessor_successor_slot_consumed": False,
        "status_head_compare_and_set_committed": False,
        "custody_successor_uniqueness_enforced": False,
        "external_registry_non_equivocation_verified": False,
        "registry_epoch_transition_continuity_verified": False,
        **_CLAIM_POLICY,
        "blockers": list(_BLOCKERS),
    }


__all__ = [
    "FROZEN_VALIDATION_PRODUCTION_RESERVATION_REGISTRY_PROOF_CONTRACT_SHA256",
    "PRODUCTION_RESERVATION_NATIVE_REGISTRY_CHECKPOINT_SCHEMA_ID",
    "PRODUCTION_RESERVATION_REGISTRY_PROOF_MAX_AGE",
    "PRODUCTION_RESERVATION_REGISTRY_PROOF_MAX_BYTES",
    "PRODUCTION_RESERVATION_REGISTRY_TRANSACTION_PROOF_SCHEMA_ID",
    "PRODUCTION_RESERVATION_SPARSE_MERKLE_DEPTH",
    "PRODUCTION_RESERVATION_SPARSE_MERKLE_EMPTY_LEAF_SHA256",
    "PRODUCTION_RESERVATION_SPARSE_MERKLE_LEAF_SCHEMA_ID",
    "ProductionReservationRegistryBackendTrustAnchor",
    "ProductionReservationRegistryHeadObserverTrustAnchor",
    "ProductionReservationRegistryTransactionProofVerification",
    "VALIDATION_PRODUCTION_RESERVATION_REGISTRY_PROOF_CONTRACT_ID",
    "VALIDATION_PRODUCTION_RESERVATION_REGISTRY_PROOF_CONTRACT_SCHEMA_ID",
    "VALIDATION_PRODUCTION_RESERVATION_REGISTRY_PROOF_CONTRACT_VERSION",
    "ValidationProductionReservationRegistryProofError",
    "production_reservation_native_registry_checkpoint_sha256",
    "production_reservation_sparse_merkle_consumed_leaf_sha256",
    "production_reservation_sparse_merkle_default_sha256s",
    "production_reservation_sparse_merkle_node_sha256",
    "production_reservation_sparse_merkle_root_sha256",
    "require_validation_production_reservation_registry_proof_contract_document",
    "validation_production_reservation_registry_proof_contract_document",
    "validation_production_reservation_registry_proof_decision",
    "verify_external_production_reservation_registry_transaction_proof",
]
