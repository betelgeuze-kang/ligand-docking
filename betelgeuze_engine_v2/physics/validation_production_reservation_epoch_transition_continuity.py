"""Verify one adjacent registry-epoch terminal-to-genesis transition.

The verifier freshly re-verifies a caller-pinned same-epoch witness-quorum
certificate, requires an exactly adjacent caller-pinned epoch ordinal, carries
the previous terminal state root unchanged into sequence-zero genesis, derives
the genesis checkpoint from the complete transition context, and verifies
independent Ed25519 quorums from both the previous and next fixed witness
rosters over that exact transition statement.

This proves continuity only for the supplied, caller-pinned adjacent transition.
It does not observe witness locking, compare independent witness journals,
exclude a separately quorum-signed sibling successor, establish a globally
latest head, commit a registry CAS, authorize execution, or open any scientific
or product claim.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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
    ValidationProductionReservationLaterHeadConsistencyError,
)
import betelgeuze_engine_v2.physics.validation_production_reservation_witness_quorum_non_equivocation as witness_quorum
from betelgeuze_engine_v2.physics.validation_production_reservation_witness_quorum_non_equivocation import (
    FROZEN_VALIDATION_PRODUCTION_RESERVATION_WITNESS_QUORUM_CONTRACT_SHA256,
    PRODUCTION_RESERVATION_WITNESS_QUORUM_MAX_MEMBERS,
    PRODUCTION_RESERVATION_WITNESS_QUORUM_MIN_MEMBERS,
    ProductionReservationNonEquivocationWitnessTrustAnchor,
    ProductionReservationWitnessQuorumVerification,
    ValidationProductionReservationWitnessQuorumError,
    verify_external_production_reservation_witness_quorum_proof,
)


VALIDATION_PRODUCTION_RESERVATION_EPOCH_TRANSITION_CONTRACT_SCHEMA_ID = (
    "betelgeuze.engine_v2_validation_production_reservation_epoch_transition_contract/1.0.0"
)
VALIDATION_PRODUCTION_RESERVATION_EPOCH_TRANSITION_CONTRACT_ID = (
    "engine_v2_validation_production_reservation_epoch_transition/1.0.0"
)
VALIDATION_PRODUCTION_RESERVATION_EPOCH_TRANSITION_CONTRACT_VERSION = "1.0.0"
VALIDATION_PRODUCTION_RESERVATION_EPOCH_TRANSITION_FROZEN_AT_UTC = (
    "2026-07-22T03:00:00Z"
)
PRODUCTION_RESERVATION_EPOCH_TRANSITION_PROOF_SCHEMA_ID = (
    "betelgeuze.engine_v2_external_reservation_epoch_transition_proof/1.0.0"
)
PRODUCTION_RESERVATION_EPOCH_TRANSITION_STATEMENT_SCHEMA_ID = (
    "betelgeuze.engine_v2_external_reservation_epoch_transition_statement/1.0.0"
)
PRODUCTION_RESERVATION_EPOCH_TRANSITION_GENESIS_SCHEMA_ID = (
    "betelgeuze.engine_v2_external_reservation_epoch_genesis_checkpoint/1.0.0"
)
PRODUCTION_RESERVATION_EPOCH_TRANSITION_POLICY_SCHEMA_ID = (
    "betelgeuze.engine_v2_external_reservation_epoch_transition_policy/1.0.0"
)
PRODUCTION_RESERVATION_EPOCH_TRANSITION_VOTE_SCHEMA_ID = (
    "betelgeuze.engine_v2_external_reservation_epoch_transition_vote/1.0.0"
)
PRODUCTION_RESERVATION_EPOCH_TRANSITION_MAX_BYTES = 2 * 1024 * 1024
PRODUCTION_RESERVATION_EPOCH_TRANSITION_MAX_JSON_INTEGER_DIGITS = 20
PRODUCTION_RESERVATION_EPOCH_TRANSITION_MAX_AGE = timedelta(minutes=15)
PRODUCTION_RESERVATION_EPOCH_TRANSITION_MAX_VALIDITY = timedelta(minutes=15)
PRODUCTION_RESERVATION_EPOCH_TRANSITION_MAX_POLICY_VALIDITY = timedelta(hours=24)
PRODUCTION_RESERVATION_EPOCH_TRANSITION_GENESIS_SEQUENCE = 0
FROZEN_VALIDATION_PRODUCTION_RESERVATION_EPOCH_TRANSITION_CONTRACT_SHA256 = (
    "7d05c2d1438eec4963ce84014860e2f4415ef3094d4ab6503608d5c3ffcae26f"
)

_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_UTC = timezone.utc
_VERIFICATION_SEAL = object()
_PREVIOUS_REVERIFICATION_FIELDS = {
    "source",
    "later_head_consistency_reverification_arguments",
    "expected_proof_sha256",
    "expected_raw_proof_sha256",
    "expected_witness_quorum_policy_sha256",
    "trusted_non_equivocation_witness_keys",
}
_TRUE_FACT_FIELDS = (
    "previous_epoch_witness_quorum_reverified",
    "same_registry_realm_verified",
    "adjacent_epoch_ordinal_verified",
    "terminal_state_root_carried_to_genesis_verified",
    "derived_genesis_checkpoint_verified",
    "previous_epoch_transition_quorum_verified",
    "next_epoch_transition_quorum_verified",
    "joint_dual_epoch_transition_quorum_verified",
    "pre_transition_status_denials_applied",
    "registry_epoch_transition_continuity_verified",
)
_FALSE_FACT_POLICY = {
    "post_transition_status_denials_applied": False,
    "transition_successor_uniqueness_enforced": False,
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
    "adjacent_epoch_transition_proof_not_provisioned",
    "previous_epoch_transition_quorum_not_provisioned",
    "next_epoch_transition_quorum_not_provisioned",
    "next_epoch_transition_policy_not_provisioned",
    "post_transition_current_status_descendant_not_provisioned",
    "transition_successor_uniqueness_not_externally_enforced",
    "independent_witness_journal_consistency_not_established",
    "witness_locking_enforcement_not_established",
    "realm_wide_external_registry_non_equivocation_not_established",
    "global_latest_registry_head_not_independently_verified",
    "global_latest_status_head_not_independently_verified",
    "external_registry_transition_commit_not_provisioned",
    "production_validation_results_not_collected",
    "two_cpu_hosts_missing",
    "independent_human_result_review_missing",
)


class ValidationProductionReservationEpochTransitionError(ValueError):
    """The supplied adjacent epoch-transition proof is invalid."""


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
        raise ValidationProductionReservationEpochTransitionError(
            "epoch-transition value is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _raw_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    if type(value) is not str or not _SHA256_RE.fullmatch(value):
        raise ValidationProductionReservationEpochTransitionError(
            f"{name} must be an exact lowercase SHA-256"
        )
    return value


def _require_token(value: object, *, name: str) -> str:
    if type(value) is not str or not _TOKEN_RE.fullmatch(value):
        raise ValidationProductionReservationEpochTransitionError(
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
        raise ValidationProductionReservationEpochTransitionError(
            f"{name} must be an exact bounded integer"
        )
    return value


def _parse_utc(value: object, *, name: str) -> datetime:
    if type(value) is not str or not value.endswith("Z"):
        raise ValidationProductionReservationEpochTransitionError(
            f"{name} must be an exact UTC timestamp"
        )
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValidationProductionReservationEpochTransitionError(
            f"{name} must be an exact UTC timestamp"
        ) from exc
    if (
        parsed.tzinfo is None
        or parsed.utcoffset() != timedelta(0)
        or parsed.microsecond
        or parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value
    ):
        raise ValidationProductionReservationEpochTransitionError(
            f"{name} must be an exact whole-second UTC timestamp"
        )
    return parsed.astimezone(_UTC)


def _format_utc(value: datetime, *, name: str) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValidationProductionReservationEpochTransitionError(
            f"{name} must be timezone-aware"
        )
    normalized = value.astimezone(_UTC)
    if normalized.microsecond:
        raise ValidationProductionReservationEpochTransitionError(
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
        raise ValidationProductionReservationEpochTransitionError(
            f"raw {artifact_name} must be exact non-empty bytes"
        )
    if len(source) > maximum_bytes:
        raise ValidationProductionReservationEpochTransitionError(
            f"raw {artifact_name} exceeds its transport bound"
        )

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValidationProductionReservationEpochTransitionError(
                    f"{artifact_name} contains a duplicate JSON key"
                )
            result[key] = value
        return result

    def parse_bounded_integer(value: str) -> int:
        digits = value[1:] if value.startswith("-") else value
        if len(digits) > PRODUCTION_RESERVATION_EPOCH_TRANSITION_MAX_JSON_INTEGER_DIGITS:
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
        if isinstance(exc, ValidationProductionReservationEpochTransitionError):
            raise
        raise ValidationProductionReservationEpochTransitionError(
            f"{artifact_name} is not canonical ASCII JSON"
        ) from exc
    if type(loaded) is not dict or _canonical_bytes(loaded) != source:
        raise ValidationProductionReservationEpochTransitionError(
            f"{artifact_name} is not canonical ASCII JSON"
        )
    return source, loaded


def _signature(value: object, *, name: str) -> dict[str, str]:
    if type(value) is not dict or set(value) != {"algorithm", "key_id", "value"}:
        raise ValidationProductionReservationEpochTransitionError(
            f"{name} signature fields are invalid"
        )
    if value["algorithm"] != "Ed25519" or type(value["value"]) is not str:
        raise ValidationProductionReservationEpochTransitionError(
            f"{name} signature is invalid"
        )
    return {
        "algorithm": "Ed25519",
        "key_id": _require_token(value["key_id"], name=f"{name} key id"),
        "value": value["value"],
    }


def _snapshot_previous_arguments(value: object) -> dict[str, object]:
    if type(value) is not dict or set(value) != _PREVIOUS_REVERIFICATION_FIELDS:
        raise ValidationProductionReservationEpochTransitionError(
            "previous witness-quorum reverification arguments are omitted or aliased"
        )
    try:
        later_arguments = witness_quorum._snapshot_later_arguments(
            value["later_head_consistency_reverification_arguments"]
        )
        trust = witness_quorum._witness_trust_map(
            value["trusted_non_equivocation_witness_keys"],
            later_arguments=later_arguments,
        )
    except ValidationProductionReservationWitnessQuorumError as exc:
        raise ValidationProductionReservationEpochTransitionError(
            "previous witness-quorum reverification arguments are unsafe"
        ) from exc
    source = value["source"]
    if type(source) is not bytes:
        raise ValidationProductionReservationEpochTransitionError(
            "previous witness-quorum source must be exact bytes"
        )
    return {
        "source": bytes(source),
        "later_head_consistency_reverification_arguments": later_arguments,
        "expected_proof_sha256": _require_sha256(
            value["expected_proof_sha256"],
            name="previous expected witness-quorum proof",
        ),
        "expected_raw_proof_sha256": _require_sha256(
            value["expected_raw_proof_sha256"],
            name="previous expected raw witness-quorum proof",
        ),
        "expected_witness_quorum_policy_sha256": _require_sha256(
            value["expected_witness_quorum_policy_sha256"],
            name="previous expected witness policy",
        ),
        "trusted_non_equivocation_witness_keys": trust,
    }


def _next_witness_trust_map(
    value: object,
    *,
    previous_arguments: dict[str, object],
    expected_realm: str,
    expected_epoch: str,
) -> dict[str, ProductionReservationNonEquivocationWitnessTrustAnchor]:
    try:
        trust = witness_quorum._witness_trust_map(
            value,
            later_arguments=previous_arguments,
        )
    except ValidationProductionReservationWitnessQuorumError as exc:
        raise ValidationProductionReservationEpochTransitionError(
            "next-epoch witness trust map is invalid or overlaps an upstream role"
        ) from exc
    if any(
        anchor.registry_realm_identity_sha256 != expected_realm
        or anchor.registry_epoch != expected_epoch
        for anchor in trust.values()
    ):
        raise ValidationProductionReservationEpochTransitionError(
            "next-epoch witness trust scope is cross-wired"
        )
    return trust


def _transition_policy_member_row(
    *,
    member_index: int,
    key_id: str,
    anchor: ProductionReservationNonEquivocationWitnessTrustAnchor,
    registry_epoch_ordinal: int,
) -> dict[str, Any]:
    return {
        **witness_quorum._policy_member_row(
            member_index=member_index,
            key_id=key_id,
            anchor=anchor,
        ),
        "registry_epoch_ordinal": registry_epoch_ordinal,
    }


def _verify_next_policy(
    value: object,
    *,
    expected_policy_sha256: str,
    trust: dict[str, ProductionReservationNonEquivocationWitnessTrustAnchor],
    realm: str,
    epoch: str,
    epoch_ordinal: int,
) -> tuple[dict[str, Any], int, int, datetime, datetime]:
    if type(value) is not dict:
        raise ValidationProductionReservationEpochTransitionError(
            "next-epoch transition policy is unavailable"
        )
    policy = dict(value)
    policy_sha256 = policy.pop("policy_sha256", None)
    expected_fields = {
        "schema_id",
        "policy_id",
        "registry_realm_identity_sha256",
        "registry_epoch",
        "registry_epoch_ordinal",
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
        raise ValidationProductionReservationEpochTransitionError(
            "next-epoch transition policy fields are omitted or transplanted"
        )
    expected_policy = _require_sha256(
        expected_policy_sha256,
        name="caller-expected next-epoch transition policy",
    )
    observed_policy = _sha256(policy)
    if policy_sha256 != observed_policy or policy_sha256 != expected_policy:
        raise ValidationProductionReservationEpochTransitionError(
            "next-epoch transition policy identity is cross-wired"
        )
    member_count = _require_exact_int(
        policy.get("member_count"),
        name="next-epoch policy member count",
        minimum=PRODUCTION_RESERVATION_WITNESS_QUORUM_MIN_MEMBERS,
        maximum=PRODUCTION_RESERVATION_WITNESS_QUORUM_MAX_MEMBERS,
    )
    threshold = _require_exact_int(
        policy.get("quorum_threshold"),
        name="next-epoch quorum threshold",
        minimum=1,
        maximum=member_count,
    )
    maximum_faulty = _require_exact_int(
        policy.get("maximum_faulty_witness_count"),
        name="next-epoch maximum faulty witness count",
        minimum=1,
        maximum=member_count - 1,
    )
    declared_epoch_ordinal = _require_exact_int(
        policy.get("registry_epoch_ordinal"),
        name="next-epoch policy epoch ordinal",
        minimum=1,
    )
    intersection = 2 * threshold - member_count
    honest_intersection = intersection - maximum_faulty
    declared_intersection = _require_exact_int(
        policy.get("minimum_quorum_intersection_count"),
        name="next-epoch minimum quorum intersection count",
        minimum=-member_count,
        maximum=member_count,
    )
    declared_honest_intersection = _require_exact_int(
        policy.get("minimum_honest_quorum_intersection_count"),
        name="next-epoch minimum honest quorum intersection count",
        minimum=-member_count,
        maximum=member_count,
    )
    if (
        member_count != len(trust)
        or member_count < 3 * maximum_faulty + 1
        or threshold < 2 * maximum_faulty + 1
        or intersection <= maximum_faulty
        or honest_intersection < 1
        or declared_intersection != intersection
        or declared_honest_intersection != honest_intersection
    ):
        raise ValidationProductionReservationEpochTransitionError(
            "next-epoch transition policy violates its fault-intersection bound"
        )
    member_rows = [
        _transition_policy_member_row(
            member_index=index,
            key_id=key_id,
            anchor=anchor,
            registry_epoch_ordinal=epoch_ordinal,
        )
        for index, (key_id, anchor) in enumerate(trust.items())
    ]
    member_set_sha256 = _sha256(member_rows)
    policy_from = _parse_utc(
        policy.get("valid_from_utc"),
        name="next-epoch policy valid_from",
    )
    policy_until = _parse_utc(
        policy.get("valid_until_utc"),
        name="next-epoch policy valid_until",
    )
    if (
        policy_from >= policy_until
        or policy_until - policy_from
        > PRODUCTION_RESERVATION_EPOCH_TRANSITION_MAX_POLICY_VALIDITY
        or policy.get("schema_id")
        != PRODUCTION_RESERVATION_EPOCH_TRANSITION_POLICY_SCHEMA_ID
        or policy.get("registry_realm_identity_sha256") != realm
        or policy.get("registry_epoch") != epoch
        or declared_epoch_ordinal != epoch_ordinal
        or _canonical_bytes(policy.get("member_rows"))
        != _canonical_bytes(member_rows)
        or policy.get("member_set_sha256") != member_set_sha256
        or any(
            _parse_utc(anchor.valid_from_utc, name="next witness valid_from")
            > policy_from
            or policy_until
            > _parse_utc(anchor.valid_until_utc, name="next witness valid_until")
            for anchor in trust.values()
        )
        or policy.get("exclusive_vote_scope")
        != "registry_realm_adjacent_epoch_transition"
        or policy.get("exclusive_vote_protocol")
        != "one_successor_epoch_per_terminal_epoch_head"
        or policy.get("fault_assumption")
        != "at_most_f_independent_failure_domains_may_equivocate"
        or policy.get("quorum_rule")
        != "two_quorums_intersect_above_fault_bound"
    ):
        raise ValidationProductionReservationEpochTransitionError(
            "next-epoch transition policy scope or membership is cross-wired"
        )
    _require_token(policy.get("policy_id"), name="next-epoch transition policy id")
    return (
        {**policy, "policy_sha256": policy_sha256},
        threshold,
        maximum_faulty,
        policy_from,
        policy_until,
    )


def _genesis_projection(
    *,
    previous: ProductionReservationWitnessQuorumVerification,
    previous_epoch_ordinal: int,
    next_epoch: str,
    next_epoch_ordinal: int,
    transition_nonce_sha256: str,
    previous_policy_sha256: str,
    previous_member_set_sha256: str,
    next_policy_sha256: str,
    next_member_set_sha256: str,
) -> dict[str, Any]:
    return {
        "schema_id": PRODUCTION_RESERVATION_EPOCH_TRANSITION_GENESIS_SCHEMA_ID,
        "epoch_transition_contract_sha256": (
            FROZEN_VALIDATION_PRODUCTION_RESERVATION_EPOCH_TRANSITION_CONTRACT_SHA256
        ),
        "lane": previous.lane,
        "registry_realm_identity_sha256": previous.registry_realm_identity_sha256,
        "previous_registry_epoch": previous.registry_epoch,
        "previous_registry_epoch_ordinal": previous_epoch_ordinal,
        "previous_terminal_registry_sequence": previous.later_registry_sequence,
        "previous_terminal_native_registry_checkpoint_sha256": (
            previous.later_native_registry_checkpoint_sha256
        ),
        "previous_terminal_registry_state_root_sha256": (
            previous.later_registry_state_root_sha256
        ),
        "next_registry_epoch": next_epoch,
        "next_registry_epoch_ordinal": next_epoch_ordinal,
        "next_genesis_registry_sequence": (
            PRODUCTION_RESERVATION_EPOCH_TRANSITION_GENESIS_SEQUENCE
        ),
        "next_genesis_registry_state_root_sha256": (
            previous.later_registry_state_root_sha256
        ),
        "transition_nonce_sha256": transition_nonce_sha256,
        "previous_witness_quorum_policy_sha256": previous_policy_sha256,
        "previous_member_set_sha256": previous_member_set_sha256,
        "next_witness_transition_policy_sha256": next_policy_sha256,
        "next_member_set_sha256": next_member_set_sha256,
        "state_root_carried_forward_unchanged": True,
        "epoch_ordinal_delta": 1,
    }


def _transition_statement(
    *,
    previous: ProductionReservationWitnessQuorumVerification,
    previous_epoch_ordinal: int,
    next_epoch: str,
    next_epoch_ordinal: int,
    transition_nonce_sha256: str,
    previous_policy_sha256: str,
    previous_member_set_sha256: str,
    next_policy_sha256: str,
    next_member_set_sha256: str,
    next_genesis_checkpoint_sha256: str,
) -> dict[str, Any]:
    projection: dict[str, Any] = {
        "schema_id": PRODUCTION_RESERVATION_EPOCH_TRANSITION_STATEMENT_SCHEMA_ID,
        "epoch_transition_contract_sha256": (
            FROZEN_VALIDATION_PRODUCTION_RESERVATION_EPOCH_TRANSITION_CONTRACT_SHA256
        ),
        "previous_witness_quorum_contract_sha256": (
            FROZEN_VALIDATION_PRODUCTION_RESERVATION_WITNESS_QUORUM_CONTRACT_SHA256
        ),
        "lane": previous.lane,
        "registry_realm_identity_sha256": previous.registry_realm_identity_sha256,
        "previous_witness_quorum_proof_sha256": previous.proof_sha256,
        "previous_raw_witness_quorum_proof_sha256": previous.raw_proof_sha256,
        "previous_witness_quorum_policy_sha256": previous_policy_sha256,
        "previous_member_set_sha256": previous_member_set_sha256,
        "previous_registry_epoch": previous.registry_epoch,
        "previous_registry_epoch_ordinal": previous_epoch_ordinal,
        "previous_terminal_registry_sequence": previous.later_registry_sequence,
        "previous_terminal_native_registry_checkpoint_sha256": (
            previous.later_native_registry_checkpoint_sha256
        ),
        "previous_terminal_registry_state_root_sha256": (
            previous.later_registry_state_root_sha256
        ),
        "next_witness_transition_policy_sha256": next_policy_sha256,
        "next_member_set_sha256": next_member_set_sha256,
        "next_registry_epoch": next_epoch,
        "next_registry_epoch_ordinal": next_epoch_ordinal,
        "next_genesis_registry_sequence": (
            PRODUCTION_RESERVATION_EPOCH_TRANSITION_GENESIS_SEQUENCE
        ),
        "next_genesis_native_registry_checkpoint_sha256": (
            next_genesis_checkpoint_sha256
        ),
        "next_genesis_registry_state_root_sha256": (
            previous.later_registry_state_root_sha256
        ),
        "transition_nonce_sha256": transition_nonce_sha256,
        "state_root_carried_forward_unchanged": True,
        "epoch_ordinal_delta": 1,
        "transition_scope": "one_adjacent_epoch_terminal_to_genesis",
        "transition_outcome": "exact_terminal_state_carried_to_derived_genesis",
    }
    statement_sha256 = _sha256(projection)
    return {**projection, "transition_statement_sha256": statement_sha256}


def _verify_vote_rows(
    value: object,
    *,
    vote_side: str,
    threshold: int,
    trust: dict[str, ProductionReservationNonEquivocationWitnessTrustAnchor],
    policy_sha256: str,
    member_set_sha256: str,
    member_index_by_key: dict[str, int],
    statement: dict[str, Any],
    previous: ProductionReservationWitnessQuorumVerification,
    previous_epoch_ordinal: int,
    next_epoch: str,
    next_epoch_ordinal: int,
    checked_at: datetime,
) -> tuple[list[dict[str, Any]], list[datetime], list[datetime], set[str]]:
    if type(value) is not list or not threshold <= len(value) <= len(trust):
        raise ValidationProductionReservationEpochTransitionError(
            f"{vote_side} vote set does not satisfy its fixed quorum threshold"
        )
    normalized: list[dict[str, Any]] = []
    observed_times: list[datetime] = []
    expiry_times: list[datetime] = []
    signer_ids: set[str] = set()
    statement_ids: set[str] = set()
    log_checkpoints: set[str] = set()
    artifact_identities: set[str] = set()
    previous_member_index = -1
    for vote_index, raw_row in enumerate(value):
        if type(raw_row) is not dict:
            raise ValidationProductionReservationEpochTransitionError(
                f"{vote_side} vote row is invalid"
            )
        row = dict(raw_row)
        signature = _signature(
            row.pop("witness_signature", None),
            name=f"{vote_side} transition vote",
        )
        vote_sha256 = row.pop("vote_sha256", None)
        expected_fields = {
            "schema_id",
            "vote_side",
            "vote_index",
            "policy_member_index",
            "signing_witness_policy_sha256",
            "signing_member_set_sha256",
            "transition_statement_sha256",
            "transition_nonce_sha256",
            "lane",
            "registry_realm_identity_sha256",
            "previous_registry_epoch",
            "previous_registry_epoch_ordinal",
            "previous_terminal_registry_sequence",
            "previous_terminal_native_registry_checkpoint_sha256",
            "previous_terminal_registry_state_root_sha256",
            "next_registry_epoch",
            "next_registry_epoch_ordinal",
            "next_genesis_registry_sequence",
            "next_genesis_native_registry_checkpoint_sha256",
            "next_genesis_registry_state_root_sha256",
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
            "terminal_and_genesis_observed",
            "no_conflicting_successor_attested",
            "vote_outcome",
        }
        if set(row) != expected_fields:
            raise ValidationProductionReservationEpochTransitionError(
                f"{vote_side} vote fields are omitted or transplanted"
            )
        key_id = signature["key_id"]
        anchor = trust.get(key_id)
        if type(anchor) is not ProductionReservationNonEquivocationWitnessTrustAnchor:
            raise ValidationProductionReservationEpochTransitionError(
                f"{vote_side} vote key is not trusted"
            )
        member_index = _require_exact_int(
            row.get("policy_member_index"),
            name=f"{vote_side} policy member index",
            maximum=len(trust) - 1,
        )
        declared_vote_index = _require_exact_int(
            row.get("vote_index"),
            name=f"{vote_side} vote index",
            maximum=len(value) - 1,
        )
        declared_previous_epoch_ordinal = _require_exact_int(
            row.get("previous_registry_epoch_ordinal"),
            name=f"{vote_side} previous epoch ordinal",
        )
        declared_previous_terminal_sequence = _require_exact_int(
            row.get("previous_terminal_registry_sequence"),
            name=f"{vote_side} previous terminal sequence",
            minimum=1,
        )
        declared_next_epoch_ordinal = _require_exact_int(
            row.get("next_registry_epoch_ordinal"),
            name=f"{vote_side} next epoch ordinal",
            minimum=1,
        )
        declared_next_genesis_sequence = _require_exact_int(
            row.get("next_genesis_registry_sequence"),
            name=f"{vote_side} next genesis sequence",
        )
        observed = _parse_utc(
            row.get("witness_observed_at_utc"),
            name=f"{vote_side} vote observed_at",
        )
        expires = _parse_utc(
            row.get("expires_at_utc"),
            name=f"{vote_side} vote expires_at",
        )
        valid_from = _parse_utc(
            anchor.valid_from_utc,
            name=f"{vote_side} witness valid_from",
        )
        valid_until = _parse_utc(
            anchor.valid_until_utc,
            name=f"{vote_side} witness valid_until",
        )
        log_checkpoint = _require_sha256(
            row.get("witness_log_checkpoint_sha256"),
            name=f"{vote_side} witness log checkpoint",
        )
        if (
            row.get("schema_id")
            != PRODUCTION_RESERVATION_EPOCH_TRANSITION_VOTE_SCHEMA_ID
            or row.get("vote_side") != vote_side
            or declared_vote_index != vote_index
            or member_index_by_key.get(key_id) != member_index
            or member_index <= previous_member_index
            or row.get("signing_witness_policy_sha256") != policy_sha256
            or row.get("signing_member_set_sha256") != member_set_sha256
            or row.get("transition_statement_sha256")
            != statement["transition_statement_sha256"]
            or row.get("transition_nonce_sha256")
            != statement["transition_nonce_sha256"]
            or row.get("lane") != previous.lane
            or row.get("registry_realm_identity_sha256")
            != previous.registry_realm_identity_sha256
            or row.get("previous_registry_epoch") != previous.registry_epoch
            or declared_previous_epoch_ordinal != previous_epoch_ordinal
            or declared_previous_terminal_sequence != previous.later_registry_sequence
            or row.get("previous_terminal_native_registry_checkpoint_sha256")
            != previous.later_native_registry_checkpoint_sha256
            or row.get("previous_terminal_registry_state_root_sha256")
            != previous.later_registry_state_root_sha256
            or row.get("next_registry_epoch") != next_epoch
            or declared_next_epoch_ordinal != next_epoch_ordinal
            or declared_next_genesis_sequence
            != PRODUCTION_RESERVATION_EPOCH_TRANSITION_GENESIS_SEQUENCE
            or row.get("next_genesis_native_registry_checkpoint_sha256")
            != statement["next_genesis_native_registry_checkpoint_sha256"]
            or row.get("next_genesis_registry_state_root_sha256")
            != previous.later_registry_state_root_sha256
            or row.get("witness_key_id") != key_id
            or row.get("witness_identity_sha256") != anchor.witness_identity_sha256
            or row.get("operator_identity_sha256")
            != anchor.operator_identity_sha256
            or row.get("fault_domain_identity_sha256")
            != anchor.fault_domain_identity_sha256
            or row.get("witness_public_key_sha256")
            != _raw_sha256(anchor.verification_key)
            or row.get("witness_service_binary_sha256")
            != anchor.service_binary_sha256
            or row.get("witness_service_schema_sha256")
            != anchor.service_schema_sha256
            or row.get("witness_service_configuration_sha256")
            != anchor.service_configuration_sha256
            or row.get("witness_service_deployment_sha256")
            != anchor.service_deployment_sha256
            or row.get("exclusive_vote_scope")
            != "registry_realm_adjacent_epoch_transition"
            or row.get("exclusive_vote_protocol")
            != "one_successor_epoch_per_terminal_epoch_head"
            or row.get("terminal_and_genesis_observed") is not True
            or row.get("no_conflicting_successor_attested") is not True
            or row.get("vote_outcome")
            != "conditional_exact_adjacent_epoch_transition_vote_recorded"
        ):
            raise ValidationProductionReservationEpochTransitionError(
                f"{vote_side} vote scope is reordered or cross-wired"
            )
        _require_exact_int(
            row.get("witness_log_sequence"),
            name=f"{vote_side} witness log sequence",
            minimum=1,
        )
        if (
            not observed <= checked_at < expires
            or not valid_from <= observed < valid_until
            or not valid_from <= checked_at < valid_until
            or expires > valid_until
            or expires - observed
            > PRODUCTION_RESERVATION_EPOCH_TRANSITION_MAX_VALIDITY
        ):
            raise ValidationProductionReservationEpochTransitionError(
                f"{vote_side} vote has invalid time or key validity"
            )
        expected_vote_sha256 = _sha256(row)
        if vote_sha256 != expected_vote_sha256:
            raise ValidationProductionReservationEpochTransitionError(
                f"{vote_side} vote logical SHA-256 verification failed"
            )
        payload = {**row, "vote_sha256": vote_sha256}
        try:
            valid = verify_ed25519(
                _canonical_bytes(payload),
                signature["value"],
                anchor.verification_key,
            )
        except ReferenceMinimizationValidationEd25519Error as exc:
            raise ValidationProductionReservationEpochTransitionError(
                "epoch-transition Ed25519 verifier is unavailable"
            ) from exc
        if not valid:
            raise ValidationProductionReservationEpochTransitionError(
                f"{vote_side} vote signature verification failed"
            )
        if (
            key_id in signer_ids
            or vote_sha256 in statement_ids
            or log_checkpoint in log_checkpoints
        ):
            raise ValidationProductionReservationEpochTransitionError(
                f"{vote_side} vote set contains an alias or duplicate"
            )
        signer_ids.add(key_id)
        statement_ids.add(vote_sha256)
        log_checkpoints.add(log_checkpoint)
        artifact_identities.update(
            {
                vote_sha256,
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
                "vote_sha256": vote_sha256,
                "witness_signature": signature,
            }
        )
        observed_times.append(observed)
        expiry_times.append(expires)
        previous_member_index = member_index
    return normalized, observed_times, expiry_times, artifact_identities


@dataclass(frozen=True, slots=True, init=False)
class ProductionReservationEpochTransitionVerification:
    proof_sha256: str
    raw_proof_sha256: str
    raw_proof_byte_count: int
    lane: str
    registry_realm_identity_sha256: str
    previous_registry_epoch: str
    previous_registry_epoch_ordinal: int
    next_registry_epoch: str
    next_registry_epoch_ordinal: int
    previous_terminal_registry_sequence: int
    previous_terminal_native_registry_checkpoint_sha256: str
    previous_terminal_registry_state_root_sha256: str
    next_genesis_registry_sequence: int
    next_genesis_native_registry_checkpoint_sha256: str
    next_genesis_registry_state_root_sha256: str
    transition_nonce_sha256: str
    transition_statement_sha256: str
    previous_witness_quorum_proof_sha256: str
    previous_raw_witness_quorum_proof_sha256: str
    previous_witness_quorum_policy_sha256: str
    previous_member_set_sha256: str
    previous_member_count: int
    previous_quorum_threshold: int
    previous_maximum_faulty_witness_count: int
    previous_quorum_signer_count: int
    previous_vote_set_sha256: str
    next_witness_transition_policy_sha256: str
    next_member_set_sha256: str
    next_member_count: int
    next_quorum_threshold: int
    next_maximum_faulty_witness_count: int
    next_quorum_signer_count: int
    next_vote_set_sha256: str
    proof_issued_at_utc: str
    proof_observed_at_utc: str
    pre_transition_status_tail_snapshot_sha256: str
    pre_transition_raw_status_tail_sha256: str
    pre_transition_status_tail_sequence: int
    pre_transition_status_tail_external_log_checkpoint_sha256: str
    previous_epoch_witness_quorum_reverified: bool = True
    same_registry_realm_verified: bool = True
    adjacent_epoch_ordinal_verified: bool = True
    terminal_state_root_carried_to_genesis_verified: bool = True
    derived_genesis_checkpoint_verified: bool = True
    previous_epoch_transition_quorum_verified: bool = True
    next_epoch_transition_quorum_verified: bool = True
    joint_dual_epoch_transition_quorum_verified: bool = True
    pre_transition_status_denials_applied: bool = True
    registry_epoch_transition_continuity_verified: bool = True
    post_transition_status_denials_applied: bool = False
    transition_successor_uniqueness_enforced: bool = False
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
) -> ProductionReservationEpochTransitionVerification:
    instance = object.__new__(ProductionReservationEpochTransitionVerification)
    for name, value in values.items():
        object.__setattr__(instance, name, value)
    for name in _TRUE_FACT_FIELDS:
        object.__setattr__(instance, name, True)
    for name in (*_FALSE_FACT_POLICY, *_CLAIM_POLICY):
        object.__setattr__(instance, name, False)
    object.__setattr__(instance, "_verification_seal", _VERIFICATION_SEAL)
    return instance


def verify_external_production_reservation_epoch_transition_proof(
    source: bytes,
    *,
    previous_epoch_witness_quorum_reverification_arguments: dict[str, object],
    expected_proof_sha256: str,
    expected_raw_proof_sha256: str,
    expected_registry_realm_identity_sha256: str,
    expected_previous_epoch_ordinal: int,
    expected_next_registry_epoch: str,
    expected_next_epoch_ordinal: int,
    expected_transition_nonce_sha256: str,
    expected_transition_statement_sha256: str,
    expected_next_genesis_native_registry_checkpoint_sha256: str,
    expected_next_genesis_registry_state_root_sha256: str,
    expected_next_epoch_transition_policy_sha256: str,
    trusted_next_epoch_witness_keys: dict[
        str, ProductionReservationNonEquivocationWitnessTrustAnchor
    ],
    checked_at: datetime,
) -> ProductionReservationEpochTransitionVerification:
    """Verify one caller-pinned adjacent transition without claim promotion."""

    checked = _parse_utc(
        _format_utc(checked_at, name="epoch-transition checked_at"),
        name="epoch-transition checked_at",
    )
    previous_arguments = _snapshot_previous_arguments(
        previous_epoch_witness_quorum_reverification_arguments
    )
    try:
        previous = verify_external_production_reservation_witness_quorum_proof(
            **previous_arguments,  # type: ignore[arg-type]
            checked_at=checked,
        )
    except ValidationProductionReservationWitnessQuorumError as exc:
        raise ValidationProductionReservationEpochTransitionError(
            "previous epoch witness-quorum proof reverification failed"
        ) from exc
    raw, loaded = _load_canonical_document(
        source,
        maximum_bytes=PRODUCTION_RESERVATION_EPOCH_TRANSITION_MAX_BYTES,
        artifact_name="epoch-transition proof",
    )
    if _raw_sha256(raw) != _require_sha256(
        expected_raw_proof_sha256,
        name="expected raw epoch-transition proof",
    ):
        raise ValidationProductionReservationEpochTransitionError(
            "raw epoch-transition proof identity is cross-wired"
        )
    proof_sha256 = loaded.pop("proof_sha256", None)
    expected_proof = _require_sha256(
        expected_proof_sha256,
        name="expected epoch-transition proof",
    )
    if proof_sha256 != expected_proof or proof_sha256 != _sha256(loaded):
        raise ValidationProductionReservationEpochTransitionError(
            "epoch-transition proof logical SHA-256 verification failed"
        )
    realm = _require_sha256(
        expected_registry_realm_identity_sha256,
        name="caller-expected registry realm",
    )
    previous_ordinal = _require_exact_int(
        expected_previous_epoch_ordinal,
        name="caller-expected previous epoch ordinal",
        maximum=2**63 - 2,
    )
    next_epoch = _require_token(
        expected_next_registry_epoch,
        name="caller-expected next registry epoch",
    )
    next_ordinal = _require_exact_int(
        expected_next_epoch_ordinal,
        name="caller-expected next epoch ordinal",
        minimum=1,
    )
    if realm != previous.registry_realm_identity_sha256:
        raise ValidationProductionReservationEpochTransitionError(
            "registry realm is cross-wired from the previous terminal"
        )
    if next_epoch == previous.registry_epoch:
        raise ValidationProductionReservationEpochTransitionError(
            "next registry epoch reuses the previous epoch identity"
        )
    if next_ordinal != previous_ordinal + 1:
        raise ValidationProductionReservationEpochTransitionError(
            "registry epoch ordinals are not exactly adjacent"
        )
    transition_nonce = _require_sha256(
        expected_transition_nonce_sha256,
        name="caller-expected transition nonce",
    )
    next_trust = _next_witness_trust_map(
        trusted_next_epoch_witness_keys,
        previous_arguments=previous_arguments,
        expected_realm=realm,
        expected_epoch=next_epoch,
    )
    next_policy, next_threshold, next_maximum_faulty, next_policy_from, next_policy_until = (
        _verify_next_policy(
            loaded.get("next_epoch_transition_policy"),
            expected_policy_sha256=expected_next_epoch_transition_policy_sha256,
            trust=next_trust,
            realm=realm,
            epoch=next_epoch,
            epoch_ordinal=next_ordinal,
        )
    )
    previous_trust = previous_arguments["trusted_non_equivocation_witness_keys"]
    if type(previous_trust) is not dict:
        raise ValidationProductionReservationEpochTransitionError(
            "previous witness trust map is unavailable"
        )
    previous_member_rows = [
        witness_quorum._policy_member_row(
            member_index=index,
            key_id=key_id,
            anchor=anchor,
        )
        for index, (key_id, anchor) in enumerate(previous_trust.items())
    ]
    previous_member_set_sha256 = _sha256(previous_member_rows)
    if previous_member_set_sha256 != previous.member_set_sha256:
        raise ValidationProductionReservationEpochTransitionError(
            "previous witness member set is cross-wired"
        )
    genesis_projection = _genesis_projection(
        previous=previous,
        previous_epoch_ordinal=previous_ordinal,
        next_epoch=next_epoch,
        next_epoch_ordinal=next_ordinal,
        transition_nonce_sha256=transition_nonce,
        previous_policy_sha256=previous.witness_quorum_policy_sha256,
        previous_member_set_sha256=previous_member_set_sha256,
        next_policy_sha256=next_policy["policy_sha256"],
        next_member_set_sha256=next_policy["member_set_sha256"],
    )
    derived_genesis_checkpoint = _sha256(genesis_projection)
    expected_genesis_checkpoint = _require_sha256(
        expected_next_genesis_native_registry_checkpoint_sha256,
        name="caller-expected next genesis checkpoint",
    )
    expected_genesis_state_root = _require_sha256(
        expected_next_genesis_registry_state_root_sha256,
        name="caller-expected next genesis state root",
    )
    if expected_genesis_state_root != previous.later_registry_state_root_sha256:
        raise ValidationProductionReservationEpochTransitionError(
            "next genesis resets or rewrites the previous terminal state root"
        )
    if expected_genesis_checkpoint != derived_genesis_checkpoint:
        raise ValidationProductionReservationEpochTransitionError(
            "next genesis checkpoint is not derived from the previous terminal"
        )
    statement = _transition_statement(
        previous=previous,
        previous_epoch_ordinal=previous_ordinal,
        next_epoch=next_epoch,
        next_epoch_ordinal=next_ordinal,
        transition_nonce_sha256=transition_nonce,
        previous_policy_sha256=previous.witness_quorum_policy_sha256,
        previous_member_set_sha256=previous_member_set_sha256,
        next_policy_sha256=next_policy["policy_sha256"],
        next_member_set_sha256=next_policy["member_set_sha256"],
        next_genesis_checkpoint_sha256=derived_genesis_checkpoint,
    )
    expected_statement_sha256 = _require_sha256(
        expected_transition_statement_sha256,
        name="caller-expected transition statement",
    )
    if statement["transition_statement_sha256"] != expected_statement_sha256:
        raise ValidationProductionReservationEpochTransitionError(
            "transition statement identity is cross-wired"
        )
    if _canonical_bytes(loaded.get("transition_statement")) != _canonical_bytes(
        statement
    ):
        raise ValidationProductionReservationEpochTransitionError(
            "transition statement fields are omitted or transplanted"
        )
    previous_member_index = {
        row["witness_key_id"]: row["member_index"] for row in previous_member_rows
    }
    next_member_index = {
        row["witness_key_id"]: row["member_index"]
        for row in next_policy["member_rows"]
    }
    previous_votes, previous_observed, previous_expiry, previous_artifacts = (
        _verify_vote_rows(
            loaded.get("previous_epoch_vote_rows"),
            vote_side="previous_epoch_terminal",
            threshold=previous.quorum_threshold,
            trust=previous_trust,
            policy_sha256=previous.witness_quorum_policy_sha256,
            member_set_sha256=previous_member_set_sha256,
            member_index_by_key=previous_member_index,
            statement=statement,
            previous=previous,
            previous_epoch_ordinal=previous_ordinal,
            next_epoch=next_epoch,
            next_epoch_ordinal=next_ordinal,
            checked_at=checked,
        )
    )
    next_votes, next_observed, next_expiry, next_artifacts = _verify_vote_rows(
        loaded.get("next_epoch_vote_rows"),
        vote_side="next_epoch_genesis",
        threshold=next_threshold,
        trust=next_trust,
        policy_sha256=next_policy["policy_sha256"],
        member_set_sha256=next_policy["member_set_sha256"],
        member_index_by_key=next_member_index,
        statement=statement,
        previous=previous,
        previous_epoch_ordinal=previous_ordinal,
        next_epoch=next_epoch,
        next_epoch_ordinal=next_ordinal,
        checked_at=checked,
    )
    if previous_artifacts & next_artifacts:
        raise ValidationProductionReservationEpochTransitionError(
            "previous and next epoch vote artifacts are aliased"
        )
    proof_issued = _parse_utc(
        loaded.get("proof_issued_at_utc"),
        name="epoch-transition proof issued_at",
    )
    proof_observed = _parse_utc(
        loaded.get("proof_observed_at_utc"),
        name="epoch-transition proof observed_at",
    )
    expires = _parse_utc(
        loaded.get("expires_at_utc"),
        name="epoch-transition proof expires_at",
    )
    if not proof_issued <= proof_observed <= checked < expires:
        raise ValidationProductionReservationEpochTransitionError(
            "epoch-transition proof has invalid causal time"
        )
    if checked - proof_observed > PRODUCTION_RESERVATION_EPOCH_TRANSITION_MAX_AGE:
        raise ValidationProductionReservationEpochTransitionError(
            "epoch-transition proof is stale"
        )
    if expires - proof_issued > PRODUCTION_RESERVATION_EPOCH_TRANSITION_MAX_VALIDITY:
        raise ValidationProductionReservationEpochTransitionError(
            "epoch-transition proof is overlong"
        )
    _, previous_document = _load_canonical_document(
        previous_arguments["source"],
        maximum_bytes=PRODUCTION_RESERVATION_EPOCH_TRANSITION_MAX_BYTES,
        artifact_name="reverified previous witness-quorum proof",
    )
    previous_policy_document = previous_document.get("witness_quorum_policy")
    if type(previous_policy_document) is not dict:
        raise ValidationProductionReservationEpochTransitionError(
            "previous witness policy is unavailable"
        )
    previous_policy_from = _parse_utc(
        previous_policy_document.get("valid_from_utc"),
        name="previous witness policy valid_from",
    )
    previous_policy_until = _parse_utc(
        previous_policy_document.get("valid_until_utc"),
        name="previous witness policy valid_until",
    )
    previous_proof_expires = _parse_utc(
        previous_document.get("expires_at_utc"),
        name="previous witness proof expires_at",
    )
    later_arguments = previous_arguments[
        "later_head_consistency_reverification_arguments"
    ]
    if type(later_arguments) is not dict:
        raise ValidationProductionReservationEpochTransitionError(
            "previous later-head arguments are unavailable"
        )
    head_arguments = later_arguments.get(
        "authenticated_head_receipt_reverification_arguments"
    )
    if type(head_arguments) is not dict:
        raise ValidationProductionReservationEpochTransitionError(
            "previous authenticated head arguments are unavailable"
        )
    try:
        status, current_raw_status, revoked_keys, revoked_artifacts, superseded = (
            later_head._current_status_tail(head_arguments)
        )
    except ValidationProductionReservationLaterHeadConsistencyError as exc:
        raise ValidationProductionReservationEpochTransitionError(
            "pre-transition status descendant is unavailable"
        ) from exc
    status_issued = _parse_utc(
        status.get("issued_at_utc"),
        name="pre-transition status issued_at",
    )
    status_snapshot = _require_sha256(
        status.get("snapshot_sha256"),
        name="pre-transition status snapshot",
    )
    status_sequence = _require_exact_int(
        status.get("status_sequence"),
        name="pre-transition status sequence",
        minimum=1,
    )
    status_checkpoint = _require_sha256(
        status.get("external_log_checkpoint_sha256"),
        name="pre-transition status checkpoint",
    )
    if (
        status_snapshot != previous.current_status_tail_snapshot_sha256
        or _raw_sha256(current_raw_status)
        != previous.current_raw_status_tail_sha256
        or status_sequence != previous.current_status_tail_sequence
        or status_checkpoint
        != previous.current_status_tail_external_log_checkpoint_sha256
    ):
        raise ValidationProductionReservationEpochTransitionError(
            "pre-transition status tail is cross-wired"
        )
    all_observed = [*previous_observed, *next_observed]
    all_vote_expiry = [*previous_expiry, *next_expiry]
    if not (
        _parse_utc(
            previous.proof_observed_at_utc,
            name="previous witness proof observed_at",
        )
        < status_issued
        < min(all_observed)
        <= max(all_observed)
        <= proof_issued
        <= proof_observed
        <= checked
        < expires
        <= min(all_vote_expiry)
        and previous_policy_from <= min(previous_observed)
        and expires <= previous_policy_until
        and next_policy_from <= min(next_observed)
        and expires <= next_policy_until
        and expires <= previous_proof_expires
    ):
        raise ValidationProductionReservationEpochTransitionError(
            "epoch-transition proof has invalid causal time"
        )
    previous_vote_set_sha256 = _sha256(previous_votes)
    next_vote_set_sha256 = _sha256(next_votes)
    previous_signer_rows = [row["witness_key_id"] for row in previous_votes]
    next_signer_rows = [row["witness_key_id"] for row in next_votes]
    artifact_identities = previous_artifacts | next_artifacts
    artifact_identities.update(
        witness_quorum._full_roster_artifact_identities(next_trust)
    )
    artifact_identities.update(
        {
            proof_sha256,
            _raw_sha256(raw),
            FROZEN_VALIDATION_PRODUCTION_RESERVATION_EPOCH_TRANSITION_CONTRACT_SHA256,
            statement["transition_statement_sha256"],
            derived_genesis_checkpoint,
            next_policy["policy_sha256"],
            next_policy["member_set_sha256"],
            previous_vote_set_sha256,
            next_vote_set_sha256,
            _sha256(previous_signer_rows),
            _sha256(next_signer_rows),
        }
    )
    if set(next_trust) & revoked_keys or artifact_identities & (
        revoked_artifacts | superseded
    ):
        raise ValidationProductionReservationEpochTransitionError(
            "epoch-transition key or artifact is denied by the pre-transition status"
        )
    expected_projection: dict[str, Any] = {
        "schema_id": PRODUCTION_RESERVATION_EPOCH_TRANSITION_PROOF_SCHEMA_ID,
        "contract_sha256": (
            FROZEN_VALIDATION_PRODUCTION_RESERVATION_EPOCH_TRANSITION_CONTRACT_SHA256
        ),
        "evidence_class": "synthetic_validation_production",
        "artifact_stage": "external_adjacent_registry_epoch_transition_certificate",
        "lane": previous.lane,
        "registry_realm_identity_sha256": realm,
        "previous_witness_quorum_proof_sha256": previous.proof_sha256,
        "previous_raw_witness_quorum_proof_sha256": previous.raw_proof_sha256,
        "previous_witness_quorum_policy_sha256": (
            previous.witness_quorum_policy_sha256
        ),
        "previous_member_set_sha256": previous_member_set_sha256,
        "previous_member_count": previous.witness_member_count,
        "previous_quorum_threshold": previous.quorum_threshold,
        "previous_maximum_faulty_witness_count": (
            previous.maximum_faulty_witness_count
        ),
        "previous_registry_epoch": previous.registry_epoch,
        "previous_registry_epoch_ordinal": previous_ordinal,
        "previous_terminal_registry_sequence": previous.later_registry_sequence,
        "previous_terminal_native_registry_checkpoint_sha256": (
            previous.later_native_registry_checkpoint_sha256
        ),
        "previous_terminal_registry_state_root_sha256": (
            previous.later_registry_state_root_sha256
        ),
        "next_epoch_transition_policy": next_policy,
        "next_epoch_transition_policy_sha256": next_policy["policy_sha256"],
        "next_member_set_sha256": next_policy["member_set_sha256"],
        "next_member_count": len(next_trust),
        "next_quorum_threshold": next_threshold,
        "next_maximum_faulty_witness_count": next_maximum_faulty,
        "next_minimum_quorum_intersection_count": (
            2 * next_threshold - len(next_trust)
        ),
        "next_minimum_honest_quorum_intersection_count": (
            2 * next_threshold - len(next_trust) - next_maximum_faulty
        ),
        "next_registry_epoch": next_epoch,
        "next_registry_epoch_ordinal": next_ordinal,
        "next_genesis_registry_sequence": (
            PRODUCTION_RESERVATION_EPOCH_TRANSITION_GENESIS_SEQUENCE
        ),
        "next_genesis_native_registry_checkpoint_sha256": (
            derived_genesis_checkpoint
        ),
        "next_genesis_registry_state_root_sha256": (
            previous.later_registry_state_root_sha256
        ),
        "transition_nonce_sha256": transition_nonce,
        "transition_statement": statement,
        "transition_statement_sha256": statement["transition_statement_sha256"],
        "previous_epoch_vote_rows": previous_votes,
        "previous_epoch_vote_set_sha256": previous_vote_set_sha256,
        "previous_epoch_signer_key_ids": previous_signer_rows,
        "previous_epoch_signer_set_sha256": _sha256(previous_signer_rows),
        "next_epoch_vote_rows": next_votes,
        "next_epoch_vote_set_sha256": next_vote_set_sha256,
        "next_epoch_signer_key_ids": next_signer_rows,
        "next_epoch_signer_set_sha256": _sha256(next_signer_rows),
        "proof_issued_at_utc": loaded["proof_issued_at_utc"],
        "proof_observed_at_utc": loaded["proof_observed_at_utc"],
        "expires_at_utc": loaded["expires_at_utc"],
        "certificate_outcome": (
            "conditional_exact_adjacent_epoch_terminal_to_genesis_continuity_verified"
        ),
        **{name: True for name in _TRUE_FACT_FIELDS},
        **_FALSE_FACT_POLICY,
        **_CLAIM_POLICY,
        "superseded": False,
        "revoked": False,
    }
    if _canonical_bytes(loaded) != _canonical_bytes(expected_projection):
        raise ValidationProductionReservationEpochTransitionError(
            "epoch-transition proof fields are omitted or transplanted"
        )
    return _new_verification(
        proof_sha256=proof_sha256,
        raw_proof_sha256=_raw_sha256(raw),
        raw_proof_byte_count=len(raw),
        lane=previous.lane,
        registry_realm_identity_sha256=realm,
        previous_registry_epoch=previous.registry_epoch,
        previous_registry_epoch_ordinal=previous_ordinal,
        next_registry_epoch=next_epoch,
        next_registry_epoch_ordinal=next_ordinal,
        previous_terminal_registry_sequence=previous.later_registry_sequence,
        previous_terminal_native_registry_checkpoint_sha256=(
            previous.later_native_registry_checkpoint_sha256
        ),
        previous_terminal_registry_state_root_sha256=(
            previous.later_registry_state_root_sha256
        ),
        next_genesis_registry_sequence=(
            PRODUCTION_RESERVATION_EPOCH_TRANSITION_GENESIS_SEQUENCE
        ),
        next_genesis_native_registry_checkpoint_sha256=derived_genesis_checkpoint,
        next_genesis_registry_state_root_sha256=(
            previous.later_registry_state_root_sha256
        ),
        transition_nonce_sha256=transition_nonce,
        transition_statement_sha256=statement["transition_statement_sha256"],
        previous_witness_quorum_proof_sha256=previous.proof_sha256,
        previous_raw_witness_quorum_proof_sha256=previous.raw_proof_sha256,
        previous_witness_quorum_policy_sha256=(
            previous.witness_quorum_policy_sha256
        ),
        previous_member_set_sha256=previous_member_set_sha256,
        previous_member_count=previous.witness_member_count,
        previous_quorum_threshold=previous.quorum_threshold,
        previous_maximum_faulty_witness_count=(
            previous.maximum_faulty_witness_count
        ),
        previous_quorum_signer_count=len(previous_votes),
        previous_vote_set_sha256=previous_vote_set_sha256,
        next_witness_transition_policy_sha256=next_policy["policy_sha256"],
        next_member_set_sha256=next_policy["member_set_sha256"],
        next_member_count=len(next_trust),
        next_quorum_threshold=next_threshold,
        next_maximum_faulty_witness_count=next_maximum_faulty,
        next_quorum_signer_count=len(next_votes),
        next_vote_set_sha256=next_vote_set_sha256,
        proof_issued_at_utc=loaded["proof_issued_at_utc"],
        proof_observed_at_utc=loaded["proof_observed_at_utc"],
        pre_transition_status_tail_snapshot_sha256=status_snapshot,
        pre_transition_raw_status_tail_sha256=_raw_sha256(current_raw_status),
        pre_transition_status_tail_sequence=status_sequence,
        pre_transition_status_tail_external_log_checkpoint_sha256=(
            status_checkpoint
        ),
    )


def _contract_projection() -> dict[str, Any]:
    return {
        "schema_id": VALIDATION_PRODUCTION_RESERVATION_EPOCH_TRANSITION_CONTRACT_SCHEMA_ID,
        "contract_id": VALIDATION_PRODUCTION_RESERVATION_EPOCH_TRANSITION_CONTRACT_ID,
        "contract_version": VALIDATION_PRODUCTION_RESERVATION_EPOCH_TRANSITION_CONTRACT_VERSION,
        "frozen_at_utc": VALIDATION_PRODUCTION_RESERVATION_EPOCH_TRANSITION_FROZEN_AT_UTC,
        "bound_previous_witness_quorum_contract_sha256": (
            FROZEN_VALIDATION_PRODUCTION_RESERVATION_WITNESS_QUORUM_CONTRACT_SHA256
        ),
        "purpose": {
            "verifier_only": True,
            "caller_pinned_adjacent_epoch_transition_supported": True,
            "previous_terminal_to_next_genesis_continuity_supported": True,
            "joint_previous_and_next_witness_quorum_required": True,
            "state_root_carried_forward_unchanged": True,
            "genesis_checkpoint_derived_from_complete_transition_context": True,
            "post_transition_status_denials_verified": False,
            "transition_successor_uniqueness_supported": False,
            "independent_witness_journals_verified": False,
            "witness_locking_enforced_by_verifier": False,
            "realm_wide_non_equivocation_supported": False,
            "global_latest_head_supported": False,
            "verification_result_is_not_an_authorization_token": True,
            "downstream_raw_proof_reverification_required": True,
        },
        "schemas": {
            "transition_proof": PRODUCTION_RESERVATION_EPOCH_TRANSITION_PROOF_SCHEMA_ID,
            "transition_statement": (
                PRODUCTION_RESERVATION_EPOCH_TRANSITION_STATEMENT_SCHEMA_ID
            ),
            "genesis_checkpoint": (
                PRODUCTION_RESERVATION_EPOCH_TRANSITION_GENESIS_SCHEMA_ID
            ),
            "next_epoch_policy": (
                PRODUCTION_RESERVATION_EPOCH_TRANSITION_POLICY_SCHEMA_ID
            ),
            "transition_vote": PRODUCTION_RESERVATION_EPOCH_TRANSITION_VOTE_SCHEMA_ID,
        },
        "transport": {
            "canonical_ascii_json_required": True,
            "duplicate_keys_rejected": True,
            "maximum_bytes": PRODUCTION_RESERVATION_EPOCH_TRANSITION_MAX_BYTES,
            "maximum_json_integer_digits": (
                PRODUCTION_RESERVATION_EPOCH_TRANSITION_MAX_JSON_INTEGER_DIGITS
            ),
        },
        "continuity": {
            "registry_realm_must_match_previous_terminal": True,
            "next_epoch_identity_must_differ": True,
            "caller_pinned_integer_ordinals_required": True,
            "next_ordinal_must_equal_previous_plus_one": True,
            "next_genesis_sequence": (
                PRODUCTION_RESERVATION_EPOCH_TRANSITION_GENESIS_SEQUENCE
            ),
            "next_genesis_state_root_must_equal_previous_terminal_state_root": True,
            "genesis_checkpoint_binds_terminal_checkpoint_root_epochs_ordinals_nonce_and_policies": True,
            "caller_pins_exact_genesis_checkpoint_state_root_statement_and_raw_proof": True,
        },
        "joint_quorum": {
            "signature_algorithm": "Ed25519",
            "previous_fixed_roster_reused_from_reverified_certificate": True,
            "next_fixed_roster_caller_pinned": True,
            "previous_and_next_roles_keys_and_deployments_disjoint": True,
            "minimum_members": PRODUCTION_RESERVATION_WITNESS_QUORUM_MIN_MEMBERS,
            "maximum_members": PRODUCTION_RESERVATION_WITNESS_QUORUM_MAX_MEMBERS,
            "member_count_at_least_three_f_plus_one": True,
            "quorum_at_least_two_f_plus_one": True,
            "two_q_minus_n_strictly_greater_than_f": True,
            "both_quorums_sign_exact_same_transition_statement": True,
            "exclusive_vote_scope": "registry_realm_adjacent_epoch_transition",
            "exclusive_vote_protocol": (
                "one_successor_epoch_per_terminal_epoch_head"
            ),
            "declared_exclusive_vote_is_not_external_lock_enforcement": True,
        },
        "trust_and_freshness": {
            "previous_witness_quorum_proof_freshly_reverified": True,
            "pre_transition_status_denials_applied": True,
            "post_transition_status_descendant_required_for_later_claims": True,
            "all_roster_keys_valid_through_proof_expiry": True,
            "transition_expiry_not_after_previous_certificate_or_policy": True,
            "causal_time_order": "previous_quorum_observation_lt_pre_transition_status_lt_transition_votes_le_proof_issue_le_proof_observation_le_check_lt_expiry",
            "maximum_age_seconds": int(
                PRODUCTION_RESERVATION_EPOCH_TRANSITION_MAX_AGE.total_seconds()
            ),
            "maximum_validity_seconds": int(
                PRODUCTION_RESERVATION_EPOCH_TRANSITION_MAX_VALIDITY.total_seconds()
            ),
            "maximum_policy_validity_seconds": int(
                PRODUCTION_RESERVATION_EPOCH_TRANSITION_MAX_POLICY_VALIDITY.total_seconds()
            ),
        },
        "verified_facts_when_external_proof_is_supplied": {
            **{name: True for name in _TRUE_FACT_FIELDS},
            **_FALSE_FACT_POLICY,
            **_CLAIM_POLICY,
        },
        "provisioned_state": {
            "external_epoch_transition_proof_present": False,
            "previous_epoch_transition_votes_present": False,
            "next_epoch_transition_votes_present": False,
            "next_epoch_witness_policy_present": False,
            "post_transition_status_descendant_present": False,
        },
        "blockers": list(_BLOCKERS),
        "superseded": False,
        "revoked": False,
    }


def validation_production_reservation_epoch_transition_contract_document() -> dict[
    str, Any
]:
    payload = _contract_projection()
    observed = _sha256(payload)
    if (
        observed
        != FROZEN_VALIDATION_PRODUCTION_RESERVATION_EPOCH_TRANSITION_CONTRACT_SHA256
    ):
        raise ValidationProductionReservationEpochTransitionError(
            "epoch-transition contract drifted from its frozen SHA-256"
        )
    return {
        **json.loads(_canonical_bytes(payload).decode("ascii")),
        "contract_sha256": observed,
    }


def require_validation_production_reservation_epoch_transition_contract_document(
    payload: dict[str, Any],
) -> dict[str, Any]:
    if type(payload) is not dict:
        raise ValidationProductionReservationEpochTransitionError(
            "epoch-transition contract document is invalid"
        )
    try:
        observed = json.loads(_canonical_bytes(payload).decode("ascii"))
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValidationProductionReservationEpochTransitionError(
            "epoch-transition contract document is invalid"
        ) from exc
    expected = validation_production_reservation_epoch_transition_contract_document()
    if _canonical_bytes(observed) != _canonical_bytes(expected):
        raise ValidationProductionReservationEpochTransitionError(
            "epoch-transition contract does not match the frozen record"
        )
    return observed


def validation_production_reservation_epoch_transition_decision() -> dict[str, Any]:
    contract = validation_production_reservation_epoch_transition_contract_document()
    return {
        "contract_sha256": contract["contract_sha256"],
        "verifier_implemented": True,
        "external_epoch_transition_service_implemented_by_package": False,
        "external_epoch_transition_proof_present": False,
        **{name: False for name in _TRUE_FACT_FIELDS},
        **_FALSE_FACT_POLICY,
        **_CLAIM_POLICY,
        "blockers": list(_BLOCKERS),
    }


__all__ = [
    "FROZEN_VALIDATION_PRODUCTION_RESERVATION_EPOCH_TRANSITION_CONTRACT_SHA256",
    "PRODUCTION_RESERVATION_EPOCH_TRANSITION_GENESIS_SCHEMA_ID",
    "PRODUCTION_RESERVATION_EPOCH_TRANSITION_GENESIS_SEQUENCE",
    "PRODUCTION_RESERVATION_EPOCH_TRANSITION_MAX_AGE",
    "PRODUCTION_RESERVATION_EPOCH_TRANSITION_MAX_BYTES",
    "PRODUCTION_RESERVATION_EPOCH_TRANSITION_MAX_POLICY_VALIDITY",
    "PRODUCTION_RESERVATION_EPOCH_TRANSITION_MAX_VALIDITY",
    "PRODUCTION_RESERVATION_EPOCH_TRANSITION_POLICY_SCHEMA_ID",
    "PRODUCTION_RESERVATION_EPOCH_TRANSITION_PROOF_SCHEMA_ID",
    "PRODUCTION_RESERVATION_EPOCH_TRANSITION_STATEMENT_SCHEMA_ID",
    "PRODUCTION_RESERVATION_EPOCH_TRANSITION_VOTE_SCHEMA_ID",
    "ProductionReservationEpochTransitionVerification",
    "VALIDATION_PRODUCTION_RESERVATION_EPOCH_TRANSITION_CONTRACT_ID",
    "VALIDATION_PRODUCTION_RESERVATION_EPOCH_TRANSITION_CONTRACT_SCHEMA_ID",
    "VALIDATION_PRODUCTION_RESERVATION_EPOCH_TRANSITION_CONTRACT_VERSION",
    "VALIDATION_PRODUCTION_RESERVATION_EPOCH_TRANSITION_FROZEN_AT_UTC",
    "ValidationProductionReservationEpochTransitionError",
    "require_validation_production_reservation_epoch_transition_contract_document",
    "validation_production_reservation_epoch_transition_contract_document",
    "validation_production_reservation_epoch_transition_decision",
    "verify_external_production_reservation_epoch_transition_proof",
]
