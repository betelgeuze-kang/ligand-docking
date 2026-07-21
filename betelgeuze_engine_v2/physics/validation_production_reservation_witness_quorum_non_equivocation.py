"""Verify one fixed-policy same-epoch witness-quorum non-equivocation certificate.

The verifier freshly re-verifies a caller-pinned later-head consistency proof,
then verifies a fixed witness membership policy and an intersecting quorum of
Ed25519 exclusive-vote statements from distinct caller-pinned declared witness,
operator, and fault-domain identifiers for the exact same-epoch sequence range
and checkpoint path.  The quorum arithmetic requires ``2Q - N > F`` so
two policy-valid quorums intersect in more witnesses than the declared maximum
fault bound.

This is a policy-scoped quorum certificate.  Its intersection arithmetic can
support an external accountable-safety argument only if no more than ``F``
independent failure domains violate the exclusive-vote rule.  This verifier does
not observe that fault bound, independently verify witness journals, or enforce
witness locking.  It therefore does not establish unconditional or realm-wide
non-equivocation, a globally latest head, epoch-transition continuity, CAS, slot
consumption, execution, or any scientific/product claim.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from typing import Any

from betelgeuze_engine_v2.physics.reference_minimization_validation_ed25519 import (
    ReferenceMinimizationValidationEd25519Error,
    verify_ed25519,
)
import betelgeuze_engine_v2.physics.validation_production_reservation_later_head_consistency as later_head
from betelgeuze_engine_v2.physics.validation_production_reservation_later_head_consistency import (
    FROZEN_VALIDATION_PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_CONTRACT_SHA256,
    ProductionReservationLaterHeadConsistencyVerification,
    ValidationProductionReservationLaterHeadConsistencyError,
    verify_external_production_reservation_later_head_consistency_proof,
)


VALIDATION_PRODUCTION_RESERVATION_WITNESS_QUORUM_CONTRACT_SCHEMA_ID = "betelgeuze.engine_v2_validation_production_reservation_witness_quorum_contract/1.0.0"
VALIDATION_PRODUCTION_RESERVATION_WITNESS_QUORUM_CONTRACT_ID = (
    "engine_v2_validation_production_reservation_witness_quorum/1.0.0"
)
VALIDATION_PRODUCTION_RESERVATION_WITNESS_QUORUM_CONTRACT_VERSION = "1.0.0"
VALIDATION_PRODUCTION_RESERVATION_WITNESS_QUORUM_FROZEN_AT_UTC = "2026-07-20T02:10:00Z"
PRODUCTION_RESERVATION_WITNESS_QUORUM_PROOF_SCHEMA_ID = (
    "betelgeuze.engine_v2_external_reservation_witness_quorum_proof/1.0.0"
)
PRODUCTION_RESERVATION_WITNESS_QUORUM_POLICY_SCHEMA_ID = (
    "betelgeuze.engine_v2_external_reservation_witness_quorum_policy/1.0.0"
)
PRODUCTION_RESERVATION_WITNESS_STATEMENT_SCHEMA_ID = (
    "betelgeuze.engine_v2_external_reservation_witness_statement/1.0.0"
)
PRODUCTION_RESERVATION_WITNESS_QUORUM_MAX_BYTES = 2 * 1024 * 1024
PRODUCTION_RESERVATION_WITNESS_QUORUM_MIN_MEMBERS = 4
PRODUCTION_RESERVATION_WITNESS_QUORUM_MAX_MEMBERS = 32
PRODUCTION_RESERVATION_WITNESS_QUORUM_MAX_JSON_INTEGER_DIGITS = 20
PRODUCTION_RESERVATION_WITNESS_QUORUM_MAX_AGE = timedelta(minutes=15)
PRODUCTION_RESERVATION_WITNESS_QUORUM_MAX_VALIDITY = timedelta(minutes=15)
PRODUCTION_RESERVATION_WITNESS_QUORUM_MAX_POLICY_VALIDITY = timedelta(hours=24)
FROZEN_VALIDATION_PRODUCTION_RESERVATION_WITNESS_QUORUM_CONTRACT_SHA256 = (
    "d7962b6a48fc25c0ff5ce83ad784800a50defa0f3d2022b2deed9ac3ce53f3f4"
)

_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_UTC = timezone.utc
_VERIFICATION_SEAL = object()
_LATER_REVERIFICATION_FIELDS = {
    "source",
    "authenticated_head_receipt_reverification_arguments",
    "expected_proof_sha256",
    "expected_raw_proof_sha256",
    "expected_later_registry_sequence",
    "expected_later_native_registry_checkpoint_sha256",
    "expected_later_registry_state_root_sha256",
    "trusted_registry_backend_keys",
    "trusted_registry_head_observer_keys",
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
    "registry_epoch_transition_continuity_verified": False,
    "declared_fault_bound_observed_in_operation": False,
    "cross_anchor_non_equivocation_verified": False,
    "exclusive_vote_enforcement_verified": False,
    "independent_witness_journal_consistency_verified": False,
    "witness_locking_enforced": False,
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
    "fixed_policy_witness_quorum_proof_not_provisioned",
    "fixed_policy_witness_keys_not_provisioned",
    "fixed_policy_witness_quorum_policy_not_provisioned",
    "post_quorum_current_status_descendant_not_provisioned",
    "independent_witness_journal_consistency_not_established",
    "witness_locking_enforcement_not_established",
    "realm_wide_external_registry_non_equivocation_not_established",
    "global_latest_registry_head_not_independently_verified",
    "global_latest_status_head_not_independently_verified",
    "registry_epoch_transition_continuity_not_provisioned",
    "external_custody_successor_uniqueness_not_provisioned",
    "production_validation_results_not_collected",
    "two_cpu_hosts_missing",
    "independent_human_result_review_missing",
)


class ValidationProductionReservationWitnessQuorumError(ValueError):
    """The supplied fixed-policy witness-quorum proof is invalid."""


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
        raise ValidationProductionReservationWitnessQuorumError(
            "witness-quorum value is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _raw_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    if type(value) is not str or not _SHA256_RE.fullmatch(value):
        raise ValidationProductionReservationWitnessQuorumError(
            f"{name} must be an exact lowercase SHA-256"
        )
    return value


def _require_token(value: object, *, name: str) -> str:
    if type(value) is not str or not _TOKEN_RE.fullmatch(value):
        raise ValidationProductionReservationWitnessQuorumError(
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
        raise ValidationProductionReservationWitnessQuorumError(
            f"{name} must be an exact bounded integer"
        )
    return value


def _parse_utc(value: object, *, name: str) -> datetime:
    if type(value) is not str or not value.endswith("Z"):
        raise ValidationProductionReservationWitnessQuorumError(
            f"{name} must be an exact UTC timestamp"
        )
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValidationProductionReservationWitnessQuorumError(
            f"{name} must be an exact UTC timestamp"
        ) from exc
    if (
        parsed.tzinfo is None
        or parsed.utcoffset() != timedelta(0)
        or parsed.microsecond
        or parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value
    ):
        raise ValidationProductionReservationWitnessQuorumError(
            f"{name} must be an exact whole-second UTC timestamp"
        )
    return parsed.astimezone(_UTC)


def _format_utc(value: datetime, *, name: str) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValidationProductionReservationWitnessQuorumError(
            f"{name} must be timezone-aware"
        )
    normalized = value.astimezone(_UTC)
    if normalized.microsecond:
        raise ValidationProductionReservationWitnessQuorumError(
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
        raise ValidationProductionReservationWitnessQuorumError(
            f"raw {artifact_name} must be exact non-empty bytes"
        )
    if len(source) > maximum_bytes:
        raise ValidationProductionReservationWitnessQuorumError(
            f"raw {artifact_name} exceeds its transport bound"
        )

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValidationProductionReservationWitnessQuorumError(
                    f"{artifact_name} contains a duplicate JSON key"
                )
            result[key] = value
        return result

    def parse_bounded_integer(value: str) -> int:
        digits = value[1:] if value.startswith("-") else value
        if len(digits) > PRODUCTION_RESERVATION_WITNESS_QUORUM_MAX_JSON_INTEGER_DIGITS:
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
        if isinstance(exc, ValidationProductionReservationWitnessQuorumError):
            raise
        raise ValidationProductionReservationWitnessQuorumError(
            f"{artifact_name} is not canonical ASCII JSON"
        ) from exc
    if type(loaded) is not dict or _canonical_bytes(loaded) != source:
        raise ValidationProductionReservationWitnessQuorumError(
            f"{artifact_name} is not canonical ASCII JSON"
        )
    return source, loaded


def _signature(value: object, *, name: str) -> dict[str, str]:
    if type(value) is not dict or set(value) != {"algorithm", "key_id", "value"}:
        raise ValidationProductionReservationWitnessQuorumError(
            f"{name} signature fields are invalid"
        )
    if value["algorithm"] != "Ed25519" or type(value["value"]) is not str:
        raise ValidationProductionReservationWitnessQuorumError(
            f"{name} signature is invalid"
        )
    return {
        "algorithm": "Ed25519",
        "key_id": _require_token(value["key_id"], name=f"{name} key id"),
        "value": value["value"],
    }


@dataclass(frozen=True, slots=True)
class ProductionReservationNonEquivocationWitnessTrustAnchor:
    witness_identity_sha256: str
    operator_identity_sha256: str
    fault_domain_identity_sha256: str
    registry_realm_identity_sha256: str
    registry_epoch: str
    service_binary_sha256: str
    service_schema_sha256: str
    service_configuration_sha256: str
    service_deployment_sha256: str
    valid_from_utc: str
    valid_until_utc: str
    verification_key: bytes


def _snapshot_later_arguments(value: object) -> dict[str, object]:
    try:
        snapshot = later_head._snapshot(
            value,
            name="later-head consistency reverification",
        )
    except ValidationProductionReservationLaterHeadConsistencyError as exc:
        raise ValidationProductionReservationWitnessQuorumError(
            "later-head consistency reverification arguments are unsafe"
        ) from exc
    if type(snapshot) is not dict or set(snapshot) != _LATER_REVERIFICATION_FIELDS:
        raise ValidationProductionReservationWitnessQuorumError(
            "later-head consistency reverification arguments are omitted or aliased"
        )
    return snapshot


def _collect_existing_role_scope(
    value: object,
) -> tuple[set[str], set[str], set[bytes], set[str]]:
    identities: set[str] = set()
    deployments: set[str] = set()
    materials: set[bytes] = set()
    key_ids: set[str] = set()
    visited: set[int] = set()

    def visit(current: object) -> None:
        if current is None or type(current) in (bool, int, float, str, bytes):
            return
        identity = id(current)
        if identity in visited:
            return
        visited.add(identity)
        if type(current) is dict:
            for key, child in current.items():
                if is_dataclass(child) and hasattr(child, "verification_key"):
                    key_ids.add(key)
                visit(child)
            return
        if type(current) in (list, tuple):
            for child in current:
                visit(child)
            return
        if is_dataclass(current):
            for descriptor in fields(current):
                child = getattr(current, descriptor.name)
                if descriptor.name.endswith("identity_sha256") and type(child) is str:
                    identities.add(child)
                elif (
                    descriptor.name.endswith("deployment_sha256") and type(child) is str
                ):
                    deployments.add(child)
                elif descriptor.name == "verification_key" and type(child) is bytes:
                    materials.add(child)
                visit(child)

    visit(value)
    return identities, deployments, materials, key_ids


def _witness_trust_map(
    value: object,
    *,
    later_arguments: dict[str, object],
) -> dict[str, ProductionReservationNonEquivocationWitnessTrustAnchor]:
    if (
        type(value) is not dict
        or not PRODUCTION_RESERVATION_WITNESS_QUORUM_MIN_MEMBERS
        <= len(value)
        <= PRODUCTION_RESERVATION_WITNESS_QUORUM_MAX_MEMBERS
    ):
        raise ValidationProductionReservationWitnessQuorumError(
            "non-equivocation witness trust map is invalid"
        )
    existing_identities, existing_deployments, existing_materials, existing_key_ids = (
        _collect_existing_role_scope(later_arguments)
    )
    if any(type(key) is not str for key in value):
        raise ValidationProductionReservationWitnessQuorumError(
            "non-equivocation witness trust map contains an invalid key id"
        )
    existing_role_digests = (
        existing_identities
        | existing_deployments
        | {_raw_sha256(material) for material in existing_materials}
    )
    witness_role_digests: set[str] = set()
    materials: set[bytes] = set()
    result: dict[str, ProductionReservationNonEquivocationWitnessTrustAnchor] = {}
    for raw_key_id, raw_anchor in sorted(value.items()):
        key_id = _require_token(raw_key_id, name="non-equivocation witness key id")
        if (
            type(raw_anchor)
            is not ProductionReservationNonEquivocationWitnessTrustAnchor
        ):
            raise ValidationProductionReservationWitnessQuorumError(
                "non-equivocation witness trust map contains an invalid anchor"
            )
        anchor = ProductionReservationNonEquivocationWitnessTrustAnchor(
            raw_anchor.witness_identity_sha256,
            raw_anchor.operator_identity_sha256,
            raw_anchor.fault_domain_identity_sha256,
            raw_anchor.registry_realm_identity_sha256,
            raw_anchor.registry_epoch,
            raw_anchor.service_binary_sha256,
            raw_anchor.service_schema_sha256,
            raw_anchor.service_configuration_sha256,
            raw_anchor.service_deployment_sha256,
            raw_anchor.valid_from_utc,
            raw_anchor.valid_until_utc,
            raw_anchor.verification_key,
        )
        witness_identity = _require_sha256(
            anchor.witness_identity_sha256,
            name="non-equivocation witness identity",
        )
        operator_identity = _require_sha256(
            anchor.operator_identity_sha256,
            name="non-equivocation witness operator identity",
        )
        fault_domain_identity = _require_sha256(
            anchor.fault_domain_identity_sha256,
            name="non-equivocation witness fault-domain identity",
        )
        realm = _require_sha256(
            anchor.registry_realm_identity_sha256,
            name="non-equivocation witness realm",
        )
        epoch = _require_token(anchor.registry_epoch, name="witness epoch")
        service_digests = (
            anchor.service_binary_sha256,
            anchor.service_schema_sha256,
            anchor.service_configuration_sha256,
            anchor.service_deployment_sha256,
        )
        for digest_name, digest in zip(
            ("binary", "schema", "configuration", "deployment"),
            service_digests,
            strict=True,
        ):
            _require_sha256(digest, name=f"witness service {digest_name}")
        if (
            type(anchor.verification_key) is not bytes
            or len(anchor.verification_key) != 32
        ):
            raise ValidationProductionReservationWitnessQuorumError(
                "non-equivocation witness public key must be exactly 32 bytes"
            )
        valid_from = _parse_utc(anchor.valid_from_utc, name="witness valid_from")
        valid_until = _parse_utc(anchor.valid_until_utc, name="witness valid_until")
        if valid_from >= valid_until:
            raise ValidationProductionReservationWitnessQuorumError(
                "non-equivocation witness validity window is invalid"
            )
        public_key_sha256 = _raw_sha256(anchor.verification_key)
        role_digests = {
            witness_identity,
            operator_identity,
            fault_domain_identity,
            anchor.service_deployment_sha256,
            public_key_sha256,
        }
        if len(role_digests) != 5:
            raise ValidationProductionReservationWitnessQuorumError(
                "witness identity, operator, fault domain, deployment, and key must be separated"
            )
        if (
            key_id in existing_key_ids
            or role_digests & existing_role_digests
            or anchor.verification_key in existing_materials
        ):
            raise ValidationProductionReservationWitnessQuorumError(
                "non-equivocation witness overlaps an upstream trust role"
            )
        if role_digests & witness_role_digests or anchor.verification_key in materials:
            raise ValidationProductionReservationWitnessQuorumError(
                "non-equivocation witness trust map contains an alias"
            )
        witness_role_digests.update(role_digests)
        materials.add(anchor.verification_key)
        result[key_id] = anchor
        del realm, epoch
    return result


def _policy_member_row(
    *,
    member_index: int,
    key_id: str,
    anchor: ProductionReservationNonEquivocationWitnessTrustAnchor,
) -> dict[str, Any]:
    return {
        "member_index": member_index,
        "witness_key_id": key_id,
        "witness_identity_sha256": anchor.witness_identity_sha256,
        "operator_identity_sha256": anchor.operator_identity_sha256,
        "fault_domain_identity_sha256": anchor.fault_domain_identity_sha256,
        "registry_realm_identity_sha256": anchor.registry_realm_identity_sha256,
        "registry_epoch": anchor.registry_epoch,
        "witness_public_key_sha256": _raw_sha256(anchor.verification_key),
        "witness_service_binary_sha256": anchor.service_binary_sha256,
        "witness_service_schema_sha256": anchor.service_schema_sha256,
        "witness_service_configuration_sha256": anchor.service_configuration_sha256,
        "witness_service_deployment_sha256": anchor.service_deployment_sha256,
        "valid_from_utc": anchor.valid_from_utc,
        "valid_until_utc": anchor.valid_until_utc,
    }


def _full_roster_artifact_identities(
    trust: dict[str, ProductionReservationNonEquivocationWitnessTrustAnchor],
) -> set[str]:
    identities: set[str] = set()
    for anchor in trust.values():
        identities.update(
            {
                anchor.witness_identity_sha256,
                anchor.operator_identity_sha256,
                anchor.fault_domain_identity_sha256,
                anchor.registry_realm_identity_sha256,
                _raw_sha256(anchor.verification_key),
                anchor.service_binary_sha256,
                anchor.service_schema_sha256,
                anchor.service_configuration_sha256,
                anchor.service_deployment_sha256,
            }
        )
    return identities


def _verify_policy(
    value: object,
    *,
    expected_policy_sha256: str,
    trust: dict[str, ProductionReservationNonEquivocationWitnessTrustAnchor],
    later: ProductionReservationLaterHeadConsistencyVerification,
) -> tuple[dict[str, Any], int, int, datetime, datetime]:
    if type(value) is not dict:
        raise ValidationProductionReservationWitnessQuorumError(
            "witness quorum policy is unavailable"
        )
    policy = dict(value)
    policy_sha256 = policy.pop("policy_sha256", None)
    expected_fields = {
        "schema_id",
        "policy_id",
        "registry_realm_identity_sha256",
        "registry_epoch",
        "member_count",
        "member_set_sha256",
        "quorum_threshold",
        "maximum_faulty_witness_count",
        "minimum_quorum_intersection_count",
        "minimum_honest_quorum_intersection_count",
        "member_rows",
        "exclusive_vote_scope",
        "exclusive_vote_protocol",
        "fault_assumption",
        "quorum_rule",
        "valid_from_utc",
        "valid_until_utc",
    }
    if set(policy) != expected_fields:
        raise ValidationProductionReservationWitnessQuorumError(
            "witness quorum policy fields are omitted or transplanted"
        )
    expected_policy = _require_sha256(
        expected_policy_sha256,
        name="caller-expected witness quorum policy",
    )
    observed_policy = _sha256(policy)
    if policy_sha256 != observed_policy or policy_sha256 != expected_policy:
        raise ValidationProductionReservationWitnessQuorumError(
            "witness quorum policy identity is cross-wired"
        )
    member_count = _require_exact_int(
        policy.get("member_count"),
        name="witness policy member count",
        minimum=PRODUCTION_RESERVATION_WITNESS_QUORUM_MIN_MEMBERS,
        maximum=PRODUCTION_RESERVATION_WITNESS_QUORUM_MAX_MEMBERS,
    )
    quorum_threshold = _require_exact_int(
        policy.get("quorum_threshold"),
        name="witness quorum threshold",
        minimum=1,
        maximum=member_count,
    )
    maximum_faulty = _require_exact_int(
        policy.get("maximum_faulty_witness_count"),
        name="maximum faulty witness count",
        minimum=1,
        maximum=member_count - 1,
    )
    quorum_intersection = 2 * quorum_threshold - member_count
    honest_quorum_intersection = quorum_intersection - maximum_faulty
    declared_quorum_intersection = _require_exact_int(
        policy.get("minimum_quorum_intersection_count"),
        name="minimum quorum intersection count",
        minimum=-member_count,
        maximum=member_count,
    )
    declared_honest_quorum_intersection = _require_exact_int(
        policy.get("minimum_honest_quorum_intersection_count"),
        name="minimum honest quorum intersection count",
        minimum=-member_count,
        maximum=member_count,
    )
    if (
        member_count != len(trust)
        or member_count < 3 * maximum_faulty + 1
        or quorum_threshold < 2 * maximum_faulty + 1
        or quorum_intersection <= maximum_faulty
        or honest_quorum_intersection < 1
        or declared_quorum_intersection != quorum_intersection
        or declared_honest_quorum_intersection != honest_quorum_intersection
    ):
        raise ValidationProductionReservationWitnessQuorumError(
            "witness quorum policy does not satisfy its fault-intersection bound"
        )
    expected_members = [
        _policy_member_row(member_index=index, key_id=key_id, anchor=anchor)
        for index, (key_id, anchor) in enumerate(trust.items())
    ]
    member_set_sha256 = _sha256(expected_members)
    policy_from = _parse_utc(policy.get("valid_from_utc"), name="policy valid_from")
    policy_until = _parse_utc(policy.get("valid_until_utc"), name="policy valid_until")
    if (
        policy_from >= policy_until
        or policy_until - policy_from
        > PRODUCTION_RESERVATION_WITNESS_QUORUM_MAX_POLICY_VALIDITY
        or policy.get("schema_id")
        != PRODUCTION_RESERVATION_WITNESS_QUORUM_POLICY_SCHEMA_ID
        or policy.get("registry_realm_identity_sha256")
        != later.registry_realm_identity_sha256
        or policy.get("registry_epoch") != later.registry_epoch
        or any(
            anchor.registry_realm_identity_sha256
            != later.registry_realm_identity_sha256
            or anchor.registry_epoch != later.registry_epoch
            for anchor in trust.values()
        )
        or _canonical_bytes(policy.get("member_rows"))
        != _canonical_bytes(expected_members)
        or policy.get("member_set_sha256") != member_set_sha256
        or any(
            _parse_utc(anchor.valid_from_utc, name="witness valid_from") > policy_from
            or policy_until
            > _parse_utc(anchor.valid_until_utc, name="witness valid_until")
            for anchor in trust.values()
        )
        or policy.get("exclusive_vote_scope") != "fixed_policy_realm_epoch_anchor"
        or policy.get("exclusive_vote_protocol")
        != "one_common_lineage_per_fixed_policy_realm_epoch_anchor"
        or policy.get("fault_assumption")
        != "at_most_f_independent_failure_domains_may_equivocate"
        or policy.get("quorum_rule") != "two_quorums_intersect_above_fault_bound"
    ):
        raise ValidationProductionReservationWitnessQuorumError(
            "witness quorum policy scope or membership is cross-wired"
        )
    _require_token(policy.get("policy_id"), name="witness quorum policy id")
    return (
        {**policy, "policy_sha256": policy_sha256},
        quorum_threshold,
        maximum_faulty,
        policy_from,
        policy_until,
    )


_LINEAGE_VECTOR_FIELDS = (
    "transition_index",
    "prior_registry_sequence",
    "committed_registry_sequence",
    "prior_native_registry_checkpoint_sha256",
    "committed_native_registry_checkpoint_sha256",
    "prior_registry_state_root_sha256",
    "committed_registry_state_root_sha256",
    "registry_transaction_sha256",
    "transition_sha256",
)


def _verified_lineage_bindings(
    *,
    later_arguments: dict[str, object],
    later: ProductionReservationLaterHeadConsistencyVerification,
    policy: dict[str, Any],
) -> dict[str, Any]:
    raw_later = later_arguments.get("source")
    _raw, later_document = _load_canonical_document(
        raw_later,
        maximum_bytes=PRODUCTION_RESERVATION_WITNESS_QUORUM_MAX_BYTES,
        artifact_name="reverified later-head consistency proof",
    )
    transition_rows = later_document.get("checkpoint_transition_rows")
    if type(transition_rows) is not list or not transition_rows:
        raise ValidationProductionReservationWitnessQuorumError(
            "reverified later-head transition vector is unavailable"
        )
    transition_vector: list[dict[str, Any]] = []
    for expected_index, row in enumerate(transition_rows):
        if type(row) is not dict:
            raise ValidationProductionReservationWitnessQuorumError(
                "reverified later-head transition vector is invalid"
            )
        vector_row = {name: row.get(name) for name in _LINEAGE_VECTOR_FIELDS}
        if (
            vector_row["transition_index"] != expected_index
            or type(vector_row["prior_registry_sequence"]) is not int
            or type(vector_row["committed_registry_sequence"]) is not int
        ):
            raise ValidationProductionReservationWitnessQuorumError(
                "reverified later-head transition vector is reordered"
            )
        for name in _LINEAGE_VECTOR_FIELDS[3:]:
            _require_sha256(vector_row[name], name=f"lineage vector {name}")
        transition_vector.append(vector_row)
    if (
        len(transition_vector) != later.checkpoint_transition_count
        or _sha256(transition_rows) != later.checkpoint_transition_path_sha256
        or later_document.get("retained_slot_set_sha256")
        != later.retained_slot_set_sha256
    ):
        raise ValidationProductionReservationWitnessQuorumError(
            "reverified later-head lineage identities are cross-wired"
        )
    head_arguments = later_arguments.get(
        "authenticated_head_receipt_reverification_arguments"
    )
    if type(head_arguments) is not dict:
        raise ValidationProductionReservationWitnessQuorumError(
            "authenticated head receipt arguments are unavailable"
        )
    challenge = _require_sha256(
        head_arguments.get("expected_request_challenge_nonce_sha256"),
        name="caller-pinned anchor request challenge",
    )
    transition_vector_sha256 = _sha256(transition_vector)
    fork_scope_projection: dict[str, Any] = {
        "schema_id": (
            "betelgeuze.engine_v2_external_reservation_witness_fork_scope/1.0.0"
        ),
        "witness_quorum_contract_sha256": (
            FROZEN_VALIDATION_PRODUCTION_RESERVATION_WITNESS_QUORUM_CONTRACT_SHA256
        ),
        "witness_quorum_policy_sha256": policy["policy_sha256"],
        "member_set_sha256": policy["member_set_sha256"],
        "lane": later.lane,
        "registry_realm_identity_sha256": later.registry_realm_identity_sha256,
        "registry_epoch": later.registry_epoch,
        "anchor_head_receipt_sha256": later.anchor_head_receipt_sha256,
        "anchor_raw_head_receipt_sha256": later.anchor_raw_head_receipt_sha256,
        "anchor_registry_proof_sha256": later.anchor_registry_proof_sha256,
        "anchor_raw_registry_proof_sha256": later.anchor_raw_registry_proof_sha256,
        "anchor_registry_sequence": later.anchor_registry_sequence,
        "anchor_native_registry_checkpoint_sha256": (
            later.anchor_native_registry_checkpoint_sha256
        ),
        "anchor_registry_state_root_sha256": later.anchor_registry_state_root_sha256,
        "caller_request_challenge_nonce_sha256": challenge,
    }
    fork_scope_sha256 = _sha256(fork_scope_projection)
    fork_scope = {
        **fork_scope_projection,
        "fork_scope_sha256": fork_scope_sha256,
    }
    common_lineage_projection: dict[str, Any] = {
        "schema_id": (
            "betelgeuze.engine_v2_external_reservation_common_lineage_statement/1.0.0"
        ),
        "fork_scope_sha256": fork_scope_sha256,
        "later_head_consistency_proof_sha256": later.proof_sha256,
        "later_raw_head_consistency_proof_sha256": later.raw_proof_sha256,
        "covered_sequence_start": later.anchor_registry_sequence + 1,
        "covered_sequence_end": later.later_registry_sequence,
        "later_native_registry_checkpoint_sha256": (
            later.later_native_registry_checkpoint_sha256
        ),
        "later_registry_state_root_sha256": later.later_registry_state_root_sha256,
        "checkpoint_transition_count": later.checkpoint_transition_count,
        "checkpoint_transition_path_sha256": (later.checkpoint_transition_path_sha256),
        "checkpoint_transition_vector_sha256": transition_vector_sha256,
        "retained_slot_set_sha256": later.retained_slot_set_sha256,
        "lineage_outcome": "exact_same_epoch_descendant_path_attested",
    }
    common_lineage_statement_sha256 = _sha256(common_lineage_projection)
    common_lineage_statement = {
        **common_lineage_projection,
        "common_lineage_statement_sha256": common_lineage_statement_sha256,
    }
    return {
        "caller_request_challenge_nonce_sha256": challenge,
        "checkpoint_transition_count": later.checkpoint_transition_count,
        "checkpoint_transition_vector": transition_vector,
        "checkpoint_transition_vector_sha256": transition_vector_sha256,
        "retained_slot_set_sha256": later.retained_slot_set_sha256,
        "fork_scope": fork_scope,
        "fork_scope_sha256": fork_scope_sha256,
        "common_lineage_statement": common_lineage_statement,
        "common_lineage_statement_sha256": common_lineage_statement_sha256,
    }


def _verify_statement_rows(
    value: object,
    *,
    policy: dict[str, Any],
    threshold: int,
    trust: dict[str, ProductionReservationNonEquivocationWitnessTrustAnchor],
    later: ProductionReservationLaterHeadConsistencyVerification,
    lineage: dict[str, Any],
    checked_at: datetime,
) -> tuple[
    list[dict[str, Any]],
    list[datetime],
    list[datetime],
    set[str],
    set[str],
]:
    if type(value) is not list or not threshold <= len(value) <= len(trust):
        raise ValidationProductionReservationWitnessQuorumError(
            "witness statement set does not satisfy the fixed quorum threshold"
        )
    member_index_by_key = {
        row["witness_key_id"]: row["member_index"] for row in policy["member_rows"]
    }
    normalized: list[dict[str, Any]] = []
    observed_times: list[datetime] = []
    expiry_times: list[datetime] = []
    signer_key_ids: set[str] = set()
    statement_ids: set[str] = set()
    log_checkpoints: set[str] = set()
    artifact_identities: set[str] = set()
    previous_member_index = -1
    later_observed = _parse_utc(
        later.later_head_observed_at_utc,
        name="later-head observer countersign completion",
    )
    for statement_index, raw_row in enumerate(value):
        if type(raw_row) is not dict:
            raise ValidationProductionReservationWitnessQuorumError(
                "witness statement row is invalid"
            )
        row = dict(raw_row)
        signature = _signature(
            row.pop("witness_signature", None),
            name="non-equivocation witness",
        )
        statement_sha256 = row.pop("statement_sha256", None)
        expected_fields = {
            "schema_id",
            "statement_index",
            "policy_member_index",
            "witness_quorum_policy_sha256",
            "member_set_sha256",
            "fork_scope_sha256",
            "common_lineage_statement_sha256",
            "caller_request_challenge_nonce_sha256",
            "lane",
            "registry_realm_identity_sha256",
            "registry_epoch",
            "anchor_head_receipt_sha256",
            "later_head_consistency_proof_sha256",
            "later_raw_head_consistency_proof_sha256",
            "anchor_registry_sequence",
            "anchor_native_registry_checkpoint_sha256",
            "anchor_registry_state_root_sha256",
            "later_registry_sequence",
            "later_native_registry_checkpoint_sha256",
            "later_registry_state_root_sha256",
            "checkpoint_transition_path_sha256",
            "checkpoint_transition_count",
            "checkpoint_transition_vector_sha256",
            "retained_slot_set_sha256",
            "covered_sequence_start",
            "covered_sequence_end",
            "witness_key_id",
            "witness_identity_sha256",
            "operator_identity_sha256",
            "fault_domain_identity_sha256",
            "witness_public_key_sha256",
            "witness_service_binary_sha256",
            "witness_service_schema_sha256",
            "witness_service_configuration_sha256",
            "witness_service_deployment_sha256",
            "witness_log_sequence",
            "witness_log_checkpoint_sha256",
            "witness_observed_at_utc",
            "expires_at_utc",
            "exclusive_vote_scope",
            "exclusive_vote_protocol",
            "complete_sequence_range_observed",
            "no_conflicting_checkpoint_attested",
            "statement_outcome",
        }
        if set(row) != expected_fields:
            raise ValidationProductionReservationWitnessQuorumError(
                "witness statement fields are omitted or transplanted"
            )
        key_id = signature["key_id"]
        anchor = trust.get(key_id)
        if type(anchor) is not ProductionReservationNonEquivocationWitnessTrustAnchor:
            raise ValidationProductionReservationWitnessQuorumError(
                "witness statement key is not trusted by the fixed policy"
            )
        member_index = _require_exact_int(
            row.get("policy_member_index"),
            name="witness policy member index",
            maximum=len(trust) - 1,
        )
        declared_statement_index = _require_exact_int(
            row.get("statement_index"),
            name="witness statement index",
            maximum=len(value) - 1,
        )
        declared_anchor_registry_sequence = _require_exact_int(
            row.get("anchor_registry_sequence"),
            name="witness anchor registry sequence",
            minimum=1,
        )
        declared_later_registry_sequence = _require_exact_int(
            row.get("later_registry_sequence"),
            name="witness later registry sequence",
            minimum=1,
        )
        declared_transition_count = _require_exact_int(
            row.get("checkpoint_transition_count"),
            name="witness checkpoint transition count",
            minimum=1,
        )
        declared_covered_sequence_start = _require_exact_int(
            row.get("covered_sequence_start"),
            name="witness covered sequence start",
            minimum=1,
        )
        declared_covered_sequence_end = _require_exact_int(
            row.get("covered_sequence_end"),
            name="witness covered sequence end",
            minimum=1,
        )
        observed = _parse_utc(
            row.get("witness_observed_at_utc"),
            name="witness observed_at",
        )
        expires = _parse_utc(
            row.get("expires_at_utc"),
            name="witness statement expires_at",
        )
        valid_from = _parse_utc(anchor.valid_from_utc, name="witness valid_from")
        valid_until = _parse_utc(anchor.valid_until_utc, name="witness valid_until")
        log_checkpoint = _require_sha256(
            row.get("witness_log_checkpoint_sha256"),
            name="witness log checkpoint",
        )
        if (
            row.get("schema_id") != PRODUCTION_RESERVATION_WITNESS_STATEMENT_SCHEMA_ID
            or declared_statement_index != statement_index
            or member_index_by_key.get(key_id) != member_index
            or member_index <= previous_member_index
            or row.get("witness_quorum_policy_sha256") != policy["policy_sha256"]
            or row.get("member_set_sha256") != policy["member_set_sha256"]
            or row.get("fork_scope_sha256") != lineage["fork_scope_sha256"]
            or row.get("common_lineage_statement_sha256")
            != lineage["common_lineage_statement_sha256"]
            or row.get("caller_request_challenge_nonce_sha256")
            != lineage["caller_request_challenge_nonce_sha256"]
            or row.get("lane") != later.lane
            or row.get("registry_realm_identity_sha256")
            != later.registry_realm_identity_sha256
            or row.get("registry_epoch") != later.registry_epoch
            or row.get("anchor_head_receipt_sha256") != later.anchor_head_receipt_sha256
            or row.get("later_head_consistency_proof_sha256") != later.proof_sha256
            or row.get("later_raw_head_consistency_proof_sha256")
            != later.raw_proof_sha256
            or declared_anchor_registry_sequence != later.anchor_registry_sequence
            or row.get("anchor_native_registry_checkpoint_sha256")
            != later.anchor_native_registry_checkpoint_sha256
            or row.get("anchor_registry_state_root_sha256")
            != later.anchor_registry_state_root_sha256
            or declared_later_registry_sequence != later.later_registry_sequence
            or row.get("later_native_registry_checkpoint_sha256")
            != later.later_native_registry_checkpoint_sha256
            or row.get("later_registry_state_root_sha256")
            != later.later_registry_state_root_sha256
            or row.get("checkpoint_transition_path_sha256")
            != later.checkpoint_transition_path_sha256
            or declared_transition_count != lineage["checkpoint_transition_count"]
            or row.get("checkpoint_transition_vector_sha256")
            != lineage["checkpoint_transition_vector_sha256"]
            or row.get("retained_slot_set_sha256")
            != lineage["retained_slot_set_sha256"]
            or declared_covered_sequence_start != later.anchor_registry_sequence + 1
            or declared_covered_sequence_end != later.later_registry_sequence
            or row.get("witness_key_id") != key_id
            or row.get("witness_identity_sha256") != anchor.witness_identity_sha256
            or row.get("operator_identity_sha256") != anchor.operator_identity_sha256
            or row.get("fault_domain_identity_sha256")
            != anchor.fault_domain_identity_sha256
            or anchor.registry_realm_identity_sha256
            != later.registry_realm_identity_sha256
            or anchor.registry_epoch != later.registry_epoch
            or row.get("witness_public_key_sha256")
            != _raw_sha256(anchor.verification_key)
            or row.get("witness_service_binary_sha256") != anchor.service_binary_sha256
            or row.get("witness_service_schema_sha256") != anchor.service_schema_sha256
            or row.get("witness_service_configuration_sha256")
            != anchor.service_configuration_sha256
            or row.get("witness_service_deployment_sha256")
            != anchor.service_deployment_sha256
            or row.get("exclusive_vote_scope") != "fixed_policy_realm_epoch_anchor"
            or row.get("exclusive_vote_protocol")
            != "one_common_lineage_per_fixed_policy_realm_epoch_anchor"
            or row.get("complete_sequence_range_observed") is not True
            or row.get("no_conflicting_checkpoint_attested") is not True
            or row.get("statement_outcome")
            != "conditional_fixed_policy_common_lineage_vote_recorded"
        ):
            raise ValidationProductionReservationWitnessQuorumError(
                "witness statement scope is reordered or cross-wired"
            )
        _require_exact_int(
            row.get("witness_log_sequence"),
            name="witness log sequence",
            minimum=1,
        )
        if (
            not later_observed < observed <= checked_at < expires
            or not valid_from <= observed < valid_until
            or not valid_from <= checked_at < valid_until
            or expires - observed > PRODUCTION_RESERVATION_WITNESS_QUORUM_MAX_VALIDITY
        ):
            raise ValidationProductionReservationWitnessQuorumError(
                "witness statement has invalid time or key validity"
            )
        expected_statement_sha256 = _sha256(row)
        if statement_sha256 != expected_statement_sha256:
            raise ValidationProductionReservationWitnessQuorumError(
                "witness statement logical SHA-256 verification failed"
            )
        payload = {**row, "statement_sha256": statement_sha256}
        try:
            valid = verify_ed25519(
                _canonical_bytes(payload),
                signature["value"],
                anchor.verification_key,
            )
        except ReferenceMinimizationValidationEd25519Error as exc:
            raise ValidationProductionReservationWitnessQuorumError(
                "witness Ed25519 verifier is unavailable"
            ) from exc
        if not valid:
            raise ValidationProductionReservationWitnessQuorumError(
                "witness statement signature verification failed"
            )
        if (
            key_id in signer_key_ids
            or statement_sha256 in statement_ids
            or log_checkpoint in log_checkpoints
        ):
            raise ValidationProductionReservationWitnessQuorumError(
                "witness statement set contains an alias or duplicate"
            )
        signer_key_ids.add(key_id)
        statement_ids.add(statement_sha256)
        log_checkpoints.add(log_checkpoint)
        artifact_identities.update(
            {
                statement_sha256,
                log_checkpoint,
                anchor.witness_identity_sha256,
                anchor.operator_identity_sha256,
                anchor.fault_domain_identity_sha256,
                _raw_sha256(anchor.verification_key),
                anchor.service_binary_sha256,
                anchor.service_schema_sha256,
                anchor.service_configuration_sha256,
                anchor.service_deployment_sha256,
            }
        )
        normalized.append(
            {
                **row,
                "statement_sha256": statement_sha256,
                "witness_signature": signature,
            }
        )
        observed_times.append(observed)
        expiry_times.append(expires)
        previous_member_index = member_index
    return (
        normalized,
        observed_times,
        expiry_times,
        signer_key_ids,
        artifact_identities,
    )


@dataclass(frozen=True, slots=True, init=False)
class ProductionReservationWitnessQuorumVerification:
    proof_sha256: str
    raw_proof_sha256: str
    raw_proof_byte_count: int
    lane: str
    later_head_consistency_proof_sha256: str
    later_raw_head_consistency_proof_sha256: str
    registry_realm_identity_sha256: str
    registry_epoch: str
    anchor_registry_sequence: int
    later_registry_sequence: int
    later_native_registry_checkpoint_sha256: str
    later_registry_state_root_sha256: str
    checkpoint_transition_path_sha256: str
    checkpoint_transition_count: int
    checkpoint_transition_vector_sha256: str
    retained_slot_set_sha256: str
    caller_request_challenge_nonce_sha256: str
    member_set_sha256: str
    fork_scope_sha256: str
    common_lineage_statement_sha256: str
    witness_quorum_policy_sha256: str
    witness_member_count: int
    quorum_threshold: int
    maximum_faulty_witness_count: int
    minimum_quorum_intersection_count: int
    minimum_honest_quorum_intersection_count: int
    quorum_signer_count: int
    quorum_statement_set_sha256: str
    proof_issued_at_utc: str
    proof_observed_at_utc: str
    current_status_tail_snapshot_sha256: str
    current_raw_status_tail_sha256: str
    current_status_tail_sequence: int
    current_status_tail_external_log_checkpoint_sha256: str
    later_head_consistency_reverified: bool = True
    fixed_policy_membership_reverified: bool = True
    quorum_threshold_satisfied: bool = True
    quorum_intersection_above_fault_bound_verified: bool = True
    exclusive_vote_statement_signatures_verified: bool = True
    fixed_policy_same_epoch_anchor_scoped_quorum_certificate_verified: bool = True
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
    declared_fault_bound_observed_in_operation: bool = False
    cross_anchor_non_equivocation_verified: bool = False
    exclusive_vote_enforcement_verified: bool = False
    independent_witness_journal_consistency_verified: bool = False
    witness_locking_enforced: bool = False
    production_validation_execution_authorized: bool = False
    production_validation_results_collected: bool = False
    scientifically_validated: bool = False
    parameter_fitting_authorized: bool = False
    product_qualified: bool = False
    claim_safe: bool = False
    _verification_seal: object = field(init=False, repr=False, compare=False)


def _new_verification(
    **values: object,
) -> ProductionReservationWitnessQuorumVerification:
    instance = object.__new__(ProductionReservationWitnessQuorumVerification)
    for name, value in values.items():
        object.__setattr__(instance, name, value)
    for name in (
        "later_head_consistency_reverified",
        "fixed_policy_membership_reverified",
        "quorum_threshold_satisfied",
        "quorum_intersection_above_fault_bound_verified",
        "exclusive_vote_statement_signatures_verified",
        "fixed_policy_same_epoch_anchor_scoped_quorum_certificate_verified",
    ):
        object.__setattr__(instance, name, True)
    for name in (*_ACTUAL_FACT_POLICY, *_CLAIM_POLICY):
        object.__setattr__(instance, name, False)
    object.__setattr__(instance, "_verification_seal", _VERIFICATION_SEAL)
    return instance


def verify_external_production_reservation_witness_quorum_proof(
    source: bytes,
    *,
    later_head_consistency_reverification_arguments: dict[str, object],
    expected_proof_sha256: str,
    expected_raw_proof_sha256: str,
    expected_witness_quorum_policy_sha256: str,
    trusted_non_equivocation_witness_keys: dict[
        str, ProductionReservationNonEquivocationWitnessTrustAnchor
    ],
    checked_at: datetime,
) -> ProductionReservationWitnessQuorumVerification:
    """Verify one caller-pinned fixed-policy quorum certificate without promotion."""

    checked = _parse_utc(
        _format_utc(checked_at, name="witness-quorum checked_at"),
        name="witness-quorum checked_at",
    )
    later_arguments = _snapshot_later_arguments(
        later_head_consistency_reverification_arguments
    )
    witness_trust = _witness_trust_map(
        trusted_non_equivocation_witness_keys,
        later_arguments=later_arguments,
    )
    raw, loaded = _load_canonical_document(
        source,
        maximum_bytes=PRODUCTION_RESERVATION_WITNESS_QUORUM_MAX_BYTES,
        artifact_name="witness-quorum proof",
    )
    if _raw_sha256(raw) != _require_sha256(
        expected_raw_proof_sha256,
        name="expected raw witness-quorum proof",
    ):
        raise ValidationProductionReservationWitnessQuorumError(
            "raw witness-quorum proof identity is cross-wired"
        )
    proof_sha256 = loaded.pop("proof_sha256", None)
    expected_proof = _require_sha256(
        expected_proof_sha256,
        name="expected witness-quorum proof",
    )
    if proof_sha256 != expected_proof or proof_sha256 != _sha256(loaded):
        raise ValidationProductionReservationWitnessQuorumError(
            "witness-quorum proof logical SHA-256 verification failed"
        )
    try:
        later = verify_external_production_reservation_later_head_consistency_proof(
            **later_arguments,  # type: ignore[arg-type]
            checked_at=checked,
        )
    except ValidationProductionReservationLaterHeadConsistencyError as exc:
        raise ValidationProductionReservationWitnessQuorumError(
            "later-head consistency proof reverification failed"
        ) from exc
    policy, threshold, maximum_faulty, policy_from, policy_until = _verify_policy(
        loaded.get("witness_quorum_policy"),
        expected_policy_sha256=expected_witness_quorum_policy_sha256,
        trust=witness_trust,
        later=later,
    )
    lineage = _verified_lineage_bindings(
        later_arguments=later_arguments,
        later=later,
        policy=policy,
    )
    proof_issued = _parse_utc(
        loaded.get("proof_issued_at_utc"),
        name="witness-quorum proof issued_at",
    )
    proof_observed = _parse_utc(
        loaded.get("proof_observed_at_utc"),
        name="witness-quorum proof observed_at",
    )
    expires = _parse_utc(
        loaded.get("expires_at_utc"),
        name="witness-quorum proof expires_at",
    )
    if not proof_issued <= proof_observed <= checked < expires:
        raise ValidationProductionReservationWitnessQuorumError(
            "witness-quorum proof has invalid causal time"
        )
    if checked - proof_observed > PRODUCTION_RESERVATION_WITNESS_QUORUM_MAX_AGE:
        raise ValidationProductionReservationWitnessQuorumError(
            "witness-quorum proof is stale"
        )
    if expires - proof_issued > PRODUCTION_RESERVATION_WITNESS_QUORUM_MAX_VALIDITY:
        raise ValidationProductionReservationWitnessQuorumError(
            "witness-quorum proof is overlong"
        )
    (
        statements,
        observed_times,
        statement_expiry_times,
        signer_key_ids,
        artifact_identities,
    ) = _verify_statement_rows(
        loaded.get("witness_statement_rows"),
        policy=policy,
        threshold=threshold,
        trust=witness_trust,
        later=later,
        lineage=lineage,
        checked_at=checked,
    )
    head_arguments = later_arguments.get(
        "authenticated_head_receipt_reverification_arguments"
    )
    if type(head_arguments) is not dict:
        raise ValidationProductionReservationWitnessQuorumError(
            "authenticated head receipt arguments are unavailable"
        )
    try:
        status, current_raw_status, revoked_keys, revoked_artifacts, superseded = (
            later_head._current_status_tail(head_arguments)
        )
    except ValidationProductionReservationLaterHeadConsistencyError as exc:
        raise ValidationProductionReservationWitnessQuorumError(
            "post-quorum status descendant is unavailable"
        ) from exc
    current_status_issued = _parse_utc(
        status.get("issued_at_utc"),
        name="post-quorum status issued_at",
    )
    if not (
        _parse_utc(
            later.later_head_observed_at_utc,
            name="later-head observer countersign completion",
        )
        < min(observed_times)
        <= max(observed_times)
        <= proof_issued
        <= proof_observed
        < current_status_issued
        <= checked
        < expires
        and policy_from <= min(observed_times)
        and expires <= min(statement_expiry_times)
        and expires <= policy_until
    ):
        raise ValidationProductionReservationWitnessQuorumError(
            "witness-quorum proof has invalid causal time"
        )
    if set(witness_trust) & revoked_keys:
        raise ValidationProductionReservationWitnessQuorumError(
            "fixed-policy non-equivocation witness key is revoked"
        )
    current_status_snapshot = _require_sha256(
        status.get("snapshot_sha256"),
        name="post-quorum status snapshot",
    )
    current_status_sequence = _require_exact_int(
        status.get("status_sequence"),
        name="post-quorum status sequence",
        minimum=1,
    )
    current_status_checkpoint = _require_sha256(
        status.get("external_log_checkpoint_sha256"),
        name="post-quorum status checkpoint",
    )
    statement_set_sha256 = _sha256(statements)
    signer_rows = [row["witness_key_id"] for row in statements]
    if set(signer_rows) != signer_key_ids:
        raise ValidationProductionReservationWitnessQuorumError(
            "witness signer set is internally inconsistent"
        )
    signer_set_sha256 = _sha256(signer_rows)
    artifact_identities.update(_full_roster_artifact_identities(witness_trust))
    artifact_identities.update(
        {
            proof_sha256,
            _raw_sha256(raw),
            FROZEN_VALIDATION_PRODUCTION_RESERVATION_WITNESS_QUORUM_CONTRACT_SHA256,
            policy["policy_sha256"],
            policy["member_set_sha256"],
            lineage["fork_scope_sha256"],
            lineage["common_lineage_statement_sha256"],
            lineage["checkpoint_transition_vector_sha256"],
            statement_set_sha256,
            signer_set_sha256,
            later.proof_sha256,
            later.raw_proof_sha256,
            later.anchor_head_receipt_sha256,
            later.later_native_registry_checkpoint_sha256,
            later.later_registry_state_root_sha256,
            later.checkpoint_transition_path_sha256,
            current_status_snapshot,
            _raw_sha256(current_raw_status),
            current_status_checkpoint,
        }
    )
    if artifact_identities & (revoked_artifacts | superseded):
        raise ValidationProductionReservationWitnessQuorumError(
            "witness-quorum proof identity is revoked or superseded"
        )
    expected_projection: dict[str, Any] = {
        "schema_id": PRODUCTION_RESERVATION_WITNESS_QUORUM_PROOF_SCHEMA_ID,
        "contract_sha256": FROZEN_VALIDATION_PRODUCTION_RESERVATION_WITNESS_QUORUM_CONTRACT_SHA256,
        "evidence_class": "synthetic_validation_production",
        "artifact_stage": "external_fixed_policy_witness_quorum_certificate",
        "lane": later.lane,
        "later_head_consistency_proof_sha256": later.proof_sha256,
        "later_raw_head_consistency_proof_sha256": later.raw_proof_sha256,
        "anchor_head_receipt_sha256": later.anchor_head_receipt_sha256,
        "registry_realm_identity_sha256": later.registry_realm_identity_sha256,
        "registry_epoch": later.registry_epoch,
        "anchor_registry_sequence": later.anchor_registry_sequence,
        "anchor_native_registry_checkpoint_sha256": (
            later.anchor_native_registry_checkpoint_sha256
        ),
        "anchor_registry_state_root_sha256": later.anchor_registry_state_root_sha256,
        "later_registry_sequence": later.later_registry_sequence,
        "later_native_registry_checkpoint_sha256": (
            later.later_native_registry_checkpoint_sha256
        ),
        "later_registry_state_root_sha256": later.later_registry_state_root_sha256,
        "checkpoint_transition_path_sha256": (later.checkpoint_transition_path_sha256),
        "checkpoint_transition_count": lineage["checkpoint_transition_count"],
        "checkpoint_transition_vector": lineage["checkpoint_transition_vector"],
        "checkpoint_transition_vector_sha256": (
            lineage["checkpoint_transition_vector_sha256"]
        ),
        "retained_slot_set_sha256": lineage["retained_slot_set_sha256"],
        "caller_request_challenge_nonce_sha256": (
            lineage["caller_request_challenge_nonce_sha256"]
        ),
        "fork_scope": lineage["fork_scope"],
        "fork_scope_sha256": lineage["fork_scope_sha256"],
        "common_lineage_statement": lineage["common_lineage_statement"],
        "common_lineage_statement_sha256": (lineage["common_lineage_statement_sha256"]),
        "witness_quorum_policy": policy,
        "witness_quorum_policy_sha256": policy["policy_sha256"],
        "member_set_sha256": policy["member_set_sha256"],
        "witness_member_count": len(witness_trust),
        "quorum_threshold": threshold,
        "maximum_faulty_witness_count": maximum_faulty,
        "minimum_quorum_intersection_count": 2 * threshold - len(witness_trust),
        "minimum_honest_quorum_intersection_count": (
            2 * threshold - len(witness_trust) - maximum_faulty
        ),
        "witness_statement_rows": statements,
        "witness_statement_set_sha256": statement_set_sha256,
        "quorum_signer_key_ids": signer_rows,
        "quorum_signer_set_sha256": signer_set_sha256,
        "proof_issued_at_utc": loaded["proof_issued_at_utc"],
        "proof_observed_at_utc": loaded["proof_observed_at_utc"],
        "expires_at_utc": loaded["expires_at_utc"],
        "certificate_outcome": (
            "conditional_fixed_policy_same_epoch_anchor_scoped_quorum_certificate_verified"
        ),
        "later_head_consistency_reverified": True,
        "fixed_policy_membership_reverified": True,
        "quorum_threshold_satisfied": True,
        "quorum_intersection_above_fault_bound_verified": True,
        "exclusive_vote_statement_signatures_verified": True,
        "fixed_policy_same_epoch_anchor_scoped_quorum_certificate_verified": True,
        **_ACTUAL_FACT_POLICY,
        **_CLAIM_POLICY,
        "superseded": False,
        "revoked": False,
    }
    if _canonical_bytes(loaded) != _canonical_bytes(expected_projection):
        raise ValidationProductionReservationWitnessQuorumError(
            "witness-quorum proof fields are omitted or transplanted"
        )
    return _new_verification(
        proof_sha256=proof_sha256,
        raw_proof_sha256=_raw_sha256(raw),
        raw_proof_byte_count=len(raw),
        lane=later.lane,
        later_head_consistency_proof_sha256=later.proof_sha256,
        later_raw_head_consistency_proof_sha256=later.raw_proof_sha256,
        registry_realm_identity_sha256=later.registry_realm_identity_sha256,
        registry_epoch=later.registry_epoch,
        anchor_registry_sequence=later.anchor_registry_sequence,
        later_registry_sequence=later.later_registry_sequence,
        later_native_registry_checkpoint_sha256=(
            later.later_native_registry_checkpoint_sha256
        ),
        later_registry_state_root_sha256=later.later_registry_state_root_sha256,
        checkpoint_transition_path_sha256=later.checkpoint_transition_path_sha256,
        checkpoint_transition_count=lineage["checkpoint_transition_count"],
        checkpoint_transition_vector_sha256=(
            lineage["checkpoint_transition_vector_sha256"]
        ),
        retained_slot_set_sha256=lineage["retained_slot_set_sha256"],
        caller_request_challenge_nonce_sha256=(
            lineage["caller_request_challenge_nonce_sha256"]
        ),
        member_set_sha256=policy["member_set_sha256"],
        fork_scope_sha256=lineage["fork_scope_sha256"],
        common_lineage_statement_sha256=(lineage["common_lineage_statement_sha256"]),
        witness_quorum_policy_sha256=policy["policy_sha256"],
        witness_member_count=len(witness_trust),
        quorum_threshold=threshold,
        maximum_faulty_witness_count=maximum_faulty,
        minimum_quorum_intersection_count=2 * threshold - len(witness_trust),
        minimum_honest_quorum_intersection_count=(
            2 * threshold - len(witness_trust) - maximum_faulty
        ),
        quorum_signer_count=len(statements),
        quorum_statement_set_sha256=statement_set_sha256,
        proof_issued_at_utc=loaded["proof_issued_at_utc"],
        proof_observed_at_utc=loaded["proof_observed_at_utc"],
        current_status_tail_snapshot_sha256=current_status_snapshot,
        current_raw_status_tail_sha256=_raw_sha256(current_raw_status),
        current_status_tail_sequence=current_status_sequence,
        current_status_tail_external_log_checkpoint_sha256=(current_status_checkpoint),
    )


def _contract_projection() -> dict[str, Any]:
    return {
        "schema_id": VALIDATION_PRODUCTION_RESERVATION_WITNESS_QUORUM_CONTRACT_SCHEMA_ID,
        "contract_id": VALIDATION_PRODUCTION_RESERVATION_WITNESS_QUORUM_CONTRACT_ID,
        "contract_version": VALIDATION_PRODUCTION_RESERVATION_WITNESS_QUORUM_CONTRACT_VERSION,
        "frozen_at_utc": VALIDATION_PRODUCTION_RESERVATION_WITNESS_QUORUM_FROZEN_AT_UTC,
        "bound_later_head_consistency_contract_sha256": (
            FROZEN_VALIDATION_PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_CONTRACT_SHA256
        ),
        "purpose": {
            "verifier_only": True,
            "fixed_policy_same_epoch_anchor_scoped_quorum_certificate_supported": True,
            "conditional_on_maximum_fault_bound": True,
            "declared_fault_bound_observed_by_verifier": False,
            "independent_witness_journals_verified": False,
            "witness_locking_enforced_by_verifier": False,
            "individual_certificate_proves_non_equivocation": False,
            "sibling_certificate_set_comparison_supported": False,
            "realm_wide_non_equivocation_supported": False,
            "global_latest_head_supported": False,
            "epoch_transition_continuity_supported": False,
            "verification_result_is_not_an_authorization_token": True,
            "downstream_raw_proof_reverification_required": True,
        },
        "schemas": {
            "quorum_proof": PRODUCTION_RESERVATION_WITNESS_QUORUM_PROOF_SCHEMA_ID,
            "quorum_policy": PRODUCTION_RESERVATION_WITNESS_QUORUM_POLICY_SCHEMA_ID,
            "witness_statement": PRODUCTION_RESERVATION_WITNESS_STATEMENT_SCHEMA_ID,
        },
        "transport": {
            "canonical_ascii_json_required": True,
            "duplicate_keys_rejected": True,
            "maximum_bytes": PRODUCTION_RESERVATION_WITNESS_QUORUM_MAX_BYTES,
            "maximum_json_integer_digits": (
                PRODUCTION_RESERVATION_WITNESS_QUORUM_MAX_JSON_INTEGER_DIGITS
            ),
        },
        "fixed_policy": {
            "minimum_members": PRODUCTION_RESERVATION_WITNESS_QUORUM_MIN_MEMBERS,
            "maximum_members": PRODUCTION_RESERVATION_WITNESS_QUORUM_MAX_MEMBERS,
            "member_operators_fault_domains_keys_and_deployments_distinct": True,
            "upstream_roles_and_key_material_disjoint": True,
            "exact_ordered_member_set_digest_required": True,
            "member_count_at_least_three_f_plus_one": True,
            "quorum_at_least_two_f_plus_one": True,
            "two_q_minus_n_strictly_greater_than_f": True,
            "minimum_quorum_intersection_formula": "2Q-N",
            "minimum_honest_quorum_intersection_formula": "2Q-N-F",
            "exclusive_vote_scope": "fixed_policy_realm_epoch_anchor",
            "exclusive_vote_protocol": (
                "one_common_lineage_per_fixed_policy_realm_epoch_anchor"
            ),
            "fault_assumption": (
                "at_most_f_independent_failure_domains_may_equivocate"
            ),
            "maximum_policy_validity_seconds": int(
                PRODUCTION_RESERVATION_WITNESS_QUORUM_MAX_POLICY_VALIDITY.total_seconds()
            ),
        },
        "trust_and_freshness": {
            "signature_algorithm": "Ed25519",
            "later_head_proof_freshly_reverified": True,
            "caller_pins_exact_policy_and_raw_quorum_proof": True,
            "stable_fork_scope_excludes_descendant_target_and_path": True,
            "common_lineage_statement_binds_exact_descendant_path": True,
            "post_quorum_status_denials_applied": True,
            "all_fixed_roster_keys_valid_for_policy_window": True,
            "all_fixed_roster_keys_and_artifacts_denial_fenced": True,
            "causal_time_order": "later_head_countersign_lt_witness_observations_le_proof_issue_le_proof_observation_lt_current_status_le_check_lt_expiry",
            "maximum_age_seconds": int(
                PRODUCTION_RESERVATION_WITNESS_QUORUM_MAX_AGE.total_seconds()
            ),
            "maximum_validity_seconds": int(
                PRODUCTION_RESERVATION_WITNESS_QUORUM_MAX_VALIDITY.total_seconds()
            ),
        },
        "verified_facts_when_external_proof_is_supplied": {
            "later_head_consistency_reverified": True,
            "fixed_policy_membership_reverified": True,
            "quorum_threshold_satisfied": True,
            "quorum_intersection_above_fault_bound_verified": True,
            "exclusive_vote_statement_signatures_verified": True,
            "fixed_policy_same_epoch_anchor_scoped_quorum_certificate_verified": True,
            **_ACTUAL_FACT_POLICY,
            **_CLAIM_POLICY,
        },
        "provisioned_state": {
            "external_witness_quorum_proof_present": False,
            "trusted_non_equivocation_witness_keys_present": False,
            "fixed_witness_quorum_policy_present": False,
            "post_quorum_status_descendant_present": False,
        },
        "blockers": list(_BLOCKERS),
        "superseded": False,
        "revoked": False,
    }


def validation_production_reservation_witness_quorum_contract_document() -> dict[
    str, Any
]:
    payload = _contract_projection()
    observed = _sha256(payload)
    if (
        observed
        != FROZEN_VALIDATION_PRODUCTION_RESERVATION_WITNESS_QUORUM_CONTRACT_SHA256
    ):
        raise ValidationProductionReservationWitnessQuorumError(
            "witness-quorum contract drifted from its frozen SHA-256"
        )
    return {
        **json.loads(_canonical_bytes(payload).decode("ascii")),
        "contract_sha256": observed,
    }


def require_validation_production_reservation_witness_quorum_contract_document(
    payload: dict[str, Any],
) -> dict[str, Any]:
    if type(payload) is not dict:
        raise ValidationProductionReservationWitnessQuorumError(
            "witness-quorum contract document is invalid"
        )
    try:
        observed = json.loads(_canonical_bytes(payload).decode("ascii"))
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValidationProductionReservationWitnessQuorumError(
            "witness-quorum contract document is invalid"
        ) from exc
    expected = validation_production_reservation_witness_quorum_contract_document()
    if _canonical_bytes(observed) != _canonical_bytes(expected):
        raise ValidationProductionReservationWitnessQuorumError(
            "witness-quorum contract does not match the frozen record"
        )
    return observed


def validation_production_reservation_witness_quorum_decision() -> dict[str, Any]:
    contract = validation_production_reservation_witness_quorum_contract_document()
    return {
        "contract_sha256": contract["contract_sha256"],
        "verifier_implemented": True,
        "external_witness_quorum_or_log_implemented_by_package": False,
        "external_witness_quorum_proof_present": False,
        "fixed_policy_same_epoch_anchor_scoped_quorum_certificate_verified": False,
        **_ACTUAL_FACT_POLICY,
        **_CLAIM_POLICY,
        "blockers": list(_BLOCKERS),
    }


__all__ = [
    "FROZEN_VALIDATION_PRODUCTION_RESERVATION_WITNESS_QUORUM_CONTRACT_SHA256",
    "PRODUCTION_RESERVATION_WITNESS_QUORUM_MAX_AGE",
    "PRODUCTION_RESERVATION_WITNESS_QUORUM_MAX_BYTES",
    "PRODUCTION_RESERVATION_WITNESS_QUORUM_MAX_MEMBERS",
    "PRODUCTION_RESERVATION_WITNESS_QUORUM_MAX_POLICY_VALIDITY",
    "PRODUCTION_RESERVATION_WITNESS_QUORUM_MAX_VALIDITY",
    "PRODUCTION_RESERVATION_WITNESS_QUORUM_MIN_MEMBERS",
    "PRODUCTION_RESERVATION_WITNESS_QUORUM_POLICY_SCHEMA_ID",
    "PRODUCTION_RESERVATION_WITNESS_QUORUM_PROOF_SCHEMA_ID",
    "PRODUCTION_RESERVATION_WITNESS_STATEMENT_SCHEMA_ID",
    "ProductionReservationNonEquivocationWitnessTrustAnchor",
    "ProductionReservationWitnessQuorumVerification",
    "VALIDATION_PRODUCTION_RESERVATION_WITNESS_QUORUM_CONTRACT_ID",
    "VALIDATION_PRODUCTION_RESERVATION_WITNESS_QUORUM_CONTRACT_SCHEMA_ID",
    "VALIDATION_PRODUCTION_RESERVATION_WITNESS_QUORUM_CONTRACT_VERSION",
    "VALIDATION_PRODUCTION_RESERVATION_WITNESS_QUORUM_FROZEN_AT_UTC",
    "ValidationProductionReservationWitnessQuorumError",
    "require_validation_production_reservation_witness_quorum_contract_document",
    "validation_production_reservation_witness_quorum_contract_document",
    "validation_production_reservation_witness_quorum_decision",
    "verify_external_production_reservation_witness_quorum_proof",
]
