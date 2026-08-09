"""External immutable reservation contract for the historical one-shot A/B.

The repository deliberately ships no production ledger endpoint, credential,
private key, network client, or execution-authorizing configuration.  This
module defines and verifies request, signed receipt, and downstream-binding
semantics so a separately reviewed external service can be integrated without
letting a local clone, deleted state directory, GitHub Actions, or a test double
create global run authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import hmac
import json
import secrets
import time
from typing import Any, Mapping, Protocol

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


POLICY_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_external_reservation_policy/1.1.0"
)
REQUEST_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_external_reservation_request/1.1.0"
)
RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_external_reservation_receipt/1.1.0"
)
BINDING_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_external_reservation_binding/1.1.0"
)
REVOCATION_SNAPSHOT_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_"
    "external_reservation_revocation_snapshot/1.0.0"
)
EXPECTED_POLICY_SHA256 = (
    "e018b149a010b337ddc3705c0cb904466a6cd870db82836b3b5c580c3cb650c4"
)
EXPECTED_ONE_SHOT_POLICY_SHA256 = (
    "b9d2dc1c716c0f954ba5a9f30ecc08168eb29331293b8df5c08fa67ca7ae377f"
)
EXPECTED_HISTORICAL_CASE_IDS_SHA256 = (
    "cd2c24c9c7d937865f40352375e8a17c6b83b0b0fab8c134218d2c29537493c1"
)
MAX_REQUEST_LIFETIME_SECONDS = 15 * 60
MIN_RETENTION_SECONDS = 10 * 365 * 24 * 60 * 60
MAX_REVOCATION_SNAPSHOT_LIFETIME_SECONDS = 5 * 60
DOWNSTREAM_ROLES = (
    "local_reservation",
    "run_start",
    "candidate_evidence",
    "result",
)
_FALSE_AUTHORITY_KEYS = (
    "historical_execution_operational",
    "fresh_holdout_execution_authorized",
    "stage0_admission_authority",
    "profile_promotion_authority",
    "product_execution_authorized",
    "customer_pose_emission_authorized",
    "public_or_scientific_claim_authorized",
)


class ExternalReservationContractError(ValueError):
    """Raised when the external reservation chain fails closed."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise ExternalReservationContractError(
            "external reservation value is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _is_git_sha1(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 40
        and all(character in "0123456789abcdef" for character in value)
    )


def _identity(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value.strip() != value
        or len(value) > 256
    ):
        raise ExternalReservationContractError(f"{name} is invalid")
    return value


def _operator_identity(value: object) -> str:
    operator = _identity(value, name="operator_id")
    normalized = operator.casefold().replace("_", "-").replace(" ", "-")
    if (
        "github-actions" in normalized
        or normalized.endswith("[bot]")
        or normalized in {"actions", "github"}
    ):
        raise ExternalReservationContractError(
            "GitHub Actions and bot identities cannot operate the reservation"
        )
    return operator


def _integer(value: object, *, name: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ExternalReservationContractError(f"{name} is invalid")
    return value


def _mapping(value: object, *, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ExternalReservationContractError(f"{name} must be an object")
    return json.loads(_canonical_bytes(value).decode("ascii"))


def _exact_keys(value: Mapping[str, Any], expected: set[str], *, name: str) -> None:
    if set(value) != expected:
        raise ExternalReservationContractError(f"{name} key set is invalid")


def _strict_json_object(raw: bytes, *, name: str) -> dict[str, Any]:
    if not isinstance(raw, bytes) or not raw or len(raw) > 4 * 1024 * 1024:
        raise ExternalReservationContractError(f"{name} byte envelope is invalid")

    def pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ExternalReservationContractError(
                    f"{name} contains duplicate JSON keys"
                )
            result[key] = value
        return result

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs_hook)
    except ExternalReservationContractError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ExternalReservationContractError(f"{name} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise ExternalReservationContractError(f"{name} must be a JSON object")
    return value


def _verify_self_hash(
    value: Mapping[str, Any],
    *,
    hash_field: str,
    name: str,
) -> str:
    observed = value.get(hash_field)
    if not _is_sha256(observed):
        raise ExternalReservationContractError(f"{name} hash is invalid")
    projection = dict(value)
    projection.pop(hash_field, None)
    expected = _sha256(projection)
    if observed != expected:
        raise ExternalReservationContractError(f"{name} self-hash is invalid")
    return str(observed)


def verify_external_reservation_policy(policy: Mapping[str, Any]) -> str:
    """Verify the repository policy and preserve its non-operational boundary."""

    expected_keys = {
        "authority",
        "downstream_binding",
        "incident_recovery",
        "policy_role",
        "policy_sha256",
        "provider",
        "reservation_key",
        "retention",
        "roles",
        "schema_id",
        "status",
    }
    _exact_keys(policy, expected_keys, name="external reservation policy")
    if policy.get("schema_id") != POLICY_SCHEMA_ID:
        raise ExternalReservationContractError("external policy schema is invalid")
    if policy.get("policy_role") != "cross_clone_immutable_reservation_contract":
        raise ExternalReservationContractError("external policy role is invalid")
    policy_sha256 = _verify_self_hash(
        policy,
        hash_field="policy_sha256",
        name="external reservation policy",
    )
    if policy_sha256 != EXPECTED_POLICY_SHA256:
        raise ExternalReservationContractError("external policy identity drifted")
    if policy.get("status") != "contract_implemented_external_service_not_operational":
        raise ExternalReservationContractError("external policy status drifted")

    key = _mapping(policy.get("reservation_key"), name="reservation_key")
    if key != {
        "fields": [
            "one_shot_policy_sha256",
            "source_commit_git_sha1",
            "execution_environment_sha256",
            "historical_case_ids_sha256",
        ],
        "lifetime_uniqueness_fields": [
            "one_shot_policy_sha256",
            "historical_case_ids_sha256",
        ],
        "exact_execution_binding_fields": [
            "source_commit_git_sha1",
            "execution_environment_sha256",
        ],
        "maximum_lifetime_reservations": 1,
        "reserved_run_ordinal": 1,
        "atomic_create_if_absent_required": True,
        "deleted_local_store_does_not_restore_authority": True,
        "alternate_source_or_environment_cannot_allocate_new_ordinal": True,
    }:
        raise ExternalReservationContractError(
            "global reservation key contract drifted"
        )

    provider = _mapping(policy.get("provider"), name="provider")
    if provider != {
        "provider_id": "unconfigured",
        "endpoint": "",
        "trust_anchor_public_key_hex": "",
        "append_only_immutable_required": True,
        "network_round_trip_required": True,
        "mutual_tls_required": True,
        "server_timestamp_required": True,
        "receipt_signature_algorithm": "ed25519",
        "canonical_signed_payload_required": True,
        "policy_bound_trust_anchor_required": True,
        "signed_revocation_snapshot_required": True,
        "provider_operational": False,
    }:
        raise ExternalReservationContractError(
            "provider must remain explicitly unconfigured and non-operational"
        )

    roles = _mapping(policy.get("roles"), name="roles")
    if roles != {
        "author_identity_required": True,
        "author_reviewer_operator_distinct_required": True,
        "operator_identity_required": True,
        "reviewer_identity_required": True,
        "github_actions_operator_forbidden": True,
        "test_double_authority_forbidden": True,
        "signed_role_attestations_required": True,
    }:
        raise ExternalReservationContractError("role-separation policy drifted")

    retention = _mapping(policy.get("retention"), name="retention")
    if retention != {
        "minimum_years": 10,
        "primary_and_offsite_backup_required": True,
        "append_only_audit_log_required": True,
        "deletion_prohibited": True,
    }:
        raise ExternalReservationContractError("retention policy drifted")

    incident = _mapping(policy.get("incident_recovery"), name="incident_recovery")
    if incident != {
        "reservation_rollback_forbidden": True,
        "revocation_is_append_only": True,
        "replacement_reservation_after_incident_forbidden_without_new_policy": True,
        "recovery_requires_independent_review": True,
    }:
        raise ExternalReservationContractError("incident policy drifted")

    downstream = _mapping(policy.get("downstream_binding"), name="downstream_binding")
    if downstream != {
        "local_reservation_required": True,
        "run_start_required": True,
        "candidate_evidence_required": True,
        "result_required": True,
        "external_receipt_sha256_required": True,
        "global_reservation_key_sha256_required": True,
        "lifetime_reservation_key_sha256_required": True,
        "receipt_signature_sha256_required": True,
        "revocation_snapshot_sha256_required": True,
    }:
        raise ExternalReservationContractError("downstream binding policy drifted")

    authority = _mapping(policy.get("authority"), name="authority")
    if set(authority) != set(_FALSE_AUTHORITY_KEYS) or any(
        authority.get(key) is not False for key in _FALSE_AUTHORITY_KEYS
    ):
        raise ExternalReservationContractError(
            "external ledger contract must not claim execution or downstream authority"
        )
    return policy_sha256


@dataclass(frozen=True, slots=True)
class ExternalReservationRequest:
    one_shot_policy_sha256: str
    source_commit_git_sha1: str
    execution_environment_sha256: str
    historical_case_ids_sha256: str
    author_id: str
    operator_id: str
    reviewer_id: str
    nonce_sha256: str
    issued_at_unix: int
    expires_at_unix: int
    schema_id: str = REQUEST_SCHEMA_ID
    _request_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != REQUEST_SCHEMA_ID:
            raise ExternalReservationContractError("request schema is invalid")
        if self.one_shot_policy_sha256 != EXPECTED_ONE_SHOT_POLICY_SHA256:
            raise ExternalReservationContractError("one-shot policy identity drifted")
        if not _is_git_sha1(self.source_commit_git_sha1):
            raise ExternalReservationContractError("source commit is invalid")
        if not _is_sha256(self.execution_environment_sha256):
            raise ExternalReservationContractError("execution environment is invalid")
        if self.historical_case_ids_sha256 != EXPECTED_HISTORICAL_CASE_IDS_SHA256:
            raise ExternalReservationContractError("historical cohort identity drifted")
        author = _identity(self.author_id, name="author_id")
        operator = _operator_identity(self.operator_id)
        reviewer = _identity(self.reviewer_id, name="reviewer_id")
        if len({author, operator, reviewer}) != 3:
            raise ExternalReservationContractError(
                "author, operator, and reviewer identities must differ"
            )
        if not _is_sha256(self.nonce_sha256):
            raise ExternalReservationContractError("reservation nonce is invalid")
        issued = _integer(self.issued_at_unix, name="issued_at_unix")
        expires = _integer(self.expires_at_unix, name="expires_at_unix")
        if expires <= issued or expires - issued > MAX_REQUEST_LIFETIME_SECONDS:
            raise ExternalReservationContractError("request lifetime is invalid")
        object.__setattr__(self, "_request_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "one_shot_policy_sha256": self.one_shot_policy_sha256,
            "source_commit_git_sha1": self.source_commit_git_sha1,
            "execution_environment_sha256": self.execution_environment_sha256,
            "historical_case_ids_sha256": self.historical_case_ids_sha256,
            "author_id": self.author_id,
            "operator_id": self.operator_id,
            "reviewer_id": self.reviewer_id,
            "nonce_sha256": self.nonce_sha256,
            "issued_at_unix": self.issued_at_unix,
            "expires_at_unix": self.expires_at_unix,
            "requested_run_ordinal": 1,
            "maximum_lifetime_reservations": 1,
        }

    @property
    def lifetime_reservation_key_sha256(self) -> str:
        return _sha256(
            {
                "one_shot_policy_sha256": self.one_shot_policy_sha256,
                "historical_case_ids_sha256": self.historical_case_ids_sha256,
            }
        )

    @property
    def global_reservation_key_sha256(self) -> str:
        return _sha256(
            {
                "lifetime_reservation_key_sha256": (
                    self.lifetime_reservation_key_sha256
                ),
                "source_commit_git_sha1": self.source_commit_git_sha1,
                "execution_environment_sha256": self.execution_environment_sha256,
            }
        )

    @property
    def request_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._request_sha256:
            raise ExternalReservationContractError("request changed after construction")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {
            **self._projection(),
            "lifetime_reservation_key_sha256": (self.lifetime_reservation_key_sha256),
            "global_reservation_key_sha256": self.global_reservation_key_sha256,
            "request_sha256": self.request_sha256,
        }


@dataclass(frozen=True, slots=True)
class ExternalLedgerTrustAnchor:
    provider_id: str
    public_key_raw: bytes = field(repr=False)

    def __post_init__(self) -> None:
        _identity(self.provider_id, name="provider_id")
        if not isinstance(self.public_key_raw, bytes) or len(self.public_key_raw) != 32:
            raise ExternalReservationContractError(
                "Ed25519 trust anchor must contain exactly 32 raw bytes"
            )


_VERIFIED_RECEIPT_PROOF_SECRET = secrets.token_bytes(32)


@dataclass(frozen=True, slots=True)
class VerifiedExternalReservationReceipt:
    provider_id: str
    reservation_id: str
    lifetime_reservation_key_sha256: str
    global_reservation_key_sha256: str
    request_sha256: str
    receipt_sha256: str
    receipt_signature_sha256: str
    revocation_snapshot_sha256: str
    committed_at_unix: int
    retention_until_unix: int
    author_id: str
    operator_id: str
    reviewer_id: str
    source_commit_git_sha1: str
    execution_environment_sha256: str
    authoritative_for_execution: bool = False
    _verification_proof_sha256: str = field(
        default="",
        repr=False,
        compare=False,
    )

    def _proof_projection(self) -> dict[str, object]:
        return {
            "provider_id": self.provider_id,
            "reservation_id": self.reservation_id,
            "lifetime_reservation_key_sha256": self.lifetime_reservation_key_sha256,
            "global_reservation_key_sha256": self.global_reservation_key_sha256,
            "request_sha256": self.request_sha256,
            "receipt_sha256": self.receipt_sha256,
            "receipt_signature_sha256": self.receipt_signature_sha256,
            "revocation_snapshot_sha256": self.revocation_snapshot_sha256,
            "committed_at_unix": self.committed_at_unix,
            "retention_until_unix": self.retention_until_unix,
            "author_id": self.author_id,
            "operator_id": self.operator_id,
            "reviewer_id": self.reviewer_id,
            "source_commit_git_sha1": self.source_commit_git_sha1,
            "execution_environment_sha256": self.execution_environment_sha256,
            "authoritative_for_execution": self.authoritative_for_execution,
        }

    def _require_verifier_proof(self) -> None:
        expected = hmac.new(
            _VERIFIED_RECEIPT_PROOF_SECRET,
            _canonical_bytes(self._proof_projection()),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(self._verification_proof_sha256, expected):
            raise ExternalReservationContractError(
                "verified external receipts are verifier-constructed only"
            )

    def __post_init__(self) -> None:
        self._require_verifier_proof()
        _identity(self.provider_id, name="verified provider_id")
        _identity(self.reservation_id, name="verified reservation_id")
        for name, value in (
            ("lifetime_reservation_key_sha256", self.lifetime_reservation_key_sha256),
            ("global_reservation_key_sha256", self.global_reservation_key_sha256),
            ("request_sha256", self.request_sha256),
            ("receipt_sha256", self.receipt_sha256),
            ("receipt_signature_sha256", self.receipt_signature_sha256),
            ("revocation_snapshot_sha256", self.revocation_snapshot_sha256),
            ("execution_environment_sha256", self.execution_environment_sha256),
        ):
            if not _is_sha256(value):
                raise ExternalReservationContractError(f"verified {name} is invalid")
        _integer(self.committed_at_unix, name="verified committed_at_unix")
        _integer(self.retention_until_unix, name="verified retention_until_unix")
        _identity(self.author_id, name="verified author_id")
        _operator_identity(self.operator_id)
        _identity(self.reviewer_id, name="verified reviewer_id")
        if not _is_git_sha1(self.source_commit_git_sha1):
            raise ExternalReservationContractError(
                "verified source_commit_git_sha1 is invalid"
            )
        if self.authoritative_for_execution is not False:
            raise ExternalReservationContractError(
                "verified receipt cannot grant execution authority"
            )


@dataclass(frozen=True, slots=True)
class VerifiedExternalRevocationSnapshot:
    provider_id: str
    snapshot_sha256: str
    ledger_sequence: int
    generated_at_unix: int
    valid_until_unix: int
    revoked_receipt_sha256s: tuple[str, ...]


class ExternalReservationLedgerClient(Protocol):
    """Network boundary implemented only by separately reviewed operator code."""

    provider_id: str
    production_authority: bool

    def reserve(self, canonical_request: bytes) -> tuple[bytes, bytes, bytes, bytes]:
        """Return signed receipt and signed revocation-snapshot envelopes."""

    def lookup(self, canonical_request: bytes) -> tuple[bytes, bytes, bytes, bytes] | None:
        """Recover the signed envelopes after an ambiguous reserve response."""


def _verify_canonical_signature(
    *,
    payload_bytes: bytes,
    signature_bytes: bytes,
    payload: Mapping[str, Any],
    trust_anchor: ExternalLedgerTrustAnchor,
    name: str,
) -> str:
    if payload_bytes != _canonical_bytes(payload):
        raise ExternalReservationContractError(f"{name} is not canonical JSON")
    if not isinstance(signature_bytes, bytes) or len(signature_bytes) != 64:
        raise ExternalReservationContractError(f"{name} Ed25519 signature is invalid")
    try:
        Ed25519PublicKey.from_public_bytes(trust_anchor.public_key_raw).verify(
            signature_bytes,
            payload_bytes,
        )
    except (InvalidSignature, ValueError) as exc:
        raise ExternalReservationContractError(
            f"{name} signature verification failed"
        ) from exc
    return hashlib.sha256(signature_bytes).hexdigest()


def verify_signed_external_revocation_snapshot(
    *,
    payload_bytes: bytes,
    signature_bytes: bytes,
    trust_anchor: ExternalLedgerTrustAnchor,
    now_unix: int,
) -> VerifiedExternalRevocationSnapshot:
    """Verify a short-lived, provider-signed append-only revocation snapshot."""

    now = _integer(now_unix, name="now_unix")
    payload = _strict_json_object(payload_bytes, name="external revocation snapshot")
    _exact_keys(
        payload,
        {
            "schema_id",
            "provider_id",
            "ledger_sequence",
            "generated_at_unix",
            "valid_until_unix",
            "revoked_receipt_sha256s",
            "append_only",
            "snapshot_sha256",
        },
        name="external revocation snapshot",
    )
    if payload.get("schema_id") != REVOCATION_SNAPSHOT_SCHEMA_ID:
        raise ExternalReservationContractError("revocation snapshot schema is invalid")
    _verify_canonical_signature(
        payload_bytes=payload_bytes,
        signature_bytes=signature_bytes,
        payload=payload,
        trust_anchor=trust_anchor,
        name="external revocation snapshot",
    )
    snapshot_sha256 = _verify_self_hash(
        payload,
        hash_field="snapshot_sha256",
        name="external revocation snapshot",
    )
    if payload.get("provider_id") != trust_anchor.provider_id:
        raise ExternalReservationContractError(
            "revocation snapshot trust anchor is cross-wired"
        )
    sequence = _integer(
        payload.get("ledger_sequence"),
        name="revocation ledger_sequence",
        minimum=1,
    )
    generated = _integer(
        payload.get("generated_at_unix"),
        name="revocation generated_at_unix",
    )
    valid_until = _integer(
        payload.get("valid_until_unix"),
        name="revocation valid_until_unix",
    )
    if (
        valid_until <= generated
        or valid_until - generated > MAX_REVOCATION_SNAPSHOT_LIFETIME_SECONDS
        or not generated <= now < valid_until
    ):
        raise ExternalReservationContractError(
            "revocation snapshot lifetime is invalid"
        )
    raw_revoked = payload.get("revoked_receipt_sha256s")
    if not isinstance(raw_revoked, list) or any(
        not _is_sha256(item) for item in raw_revoked
    ):
        raise ExternalReservationContractError("revocation snapshot set is invalid")
    revoked = tuple(str(item) for item in raw_revoked)
    if tuple(sorted(set(revoked))) != revoked:
        raise ExternalReservationContractError(
            "revocation snapshot set must be sorted and unique"
        )
    if payload.get("append_only") is not True:
        raise ExternalReservationContractError("revocation snapshot is not append-only")
    return VerifiedExternalRevocationSnapshot(
        provider_id=trust_anchor.provider_id,
        snapshot_sha256=snapshot_sha256,
        ledger_sequence=sequence,
        generated_at_unix=generated,
        valid_until_unix=valid_until,
        revoked_receipt_sha256s=revoked,
    )


def verify_signed_external_reservation_receipt(
    *,
    payload_bytes: bytes,
    signature_bytes: bytes,
    request: ExternalReservationRequest,
    trust_anchor: ExternalLedgerTrustAnchor,
    now_unix: int,
    revocation_payload_bytes: bytes,
    revocation_signature_bytes: bytes,
) -> VerifiedExternalReservationReceipt:
    """Verify one immutable receipt without granting repository execution authority."""

    now = _integer(now_unix, name="now_unix")
    payload = _strict_json_object(payload_bytes, name="external reservation receipt")
    expected_keys = {
        "schema_id",
        "provider_id",
        "reservation_id",
        "lifetime_reservation_key_sha256",
        "global_reservation_key_sha256",
        "request_sha256",
        "one_shot_policy_sha256",
        "source_commit_git_sha1",
        "execution_environment_sha256",
        "historical_case_ids_sha256",
        "author_id",
        "operator_id",
        "reviewer_id",
        "nonce_sha256",
        "reserved_run_ordinal",
        "maximum_lifetime_reservations",
        "ledger_sequence",
        "committed_at_unix",
        "retention_until_unix",
        "immutable",
        "append_only",
        "revoked",
        "test_only",
        "author_identity_authenticated",
        "operator_identity_authenticated",
        "reviewer_identity_authenticated",
        "github_actions_operator",
        *_FALSE_AUTHORITY_KEYS,
        "receipt_sha256",
    }
    _exact_keys(payload, expected_keys, name="external reservation receipt")
    if payload.get("schema_id") != RECEIPT_SCHEMA_ID:
        raise ExternalReservationContractError("external receipt schema is invalid")
    receipt_signature_sha256 = _verify_canonical_signature(
        payload_bytes=payload_bytes,
        signature_bytes=signature_bytes,
        payload=payload,
        trust_anchor=trust_anchor,
        name="external reservation receipt",
    )
    receipt_sha256 = _verify_self_hash(
        payload,
        hash_field="receipt_sha256",
        name="external reservation receipt",
    )
    revocation = verify_signed_external_revocation_snapshot(
        payload_bytes=revocation_payload_bytes,
        signature_bytes=revocation_signature_bytes,
        trust_anchor=trust_anchor,
        now_unix=now,
    )
    if (
        receipt_sha256 in revocation.revoked_receipt_sha256s
        or payload.get("revoked") is not False
    ):
        raise ExternalReservationContractError("external reservation is revoked")
    if payload.get("provider_id") != trust_anchor.provider_id:
        raise ExternalReservationContractError("provider trust anchor is cross-wired")
    reservation_id = _identity(payload.get("reservation_id"), name="reservation_id")
    expected = request.to_dict()
    for binding_field in (
        "global_reservation_key_sha256",
        "lifetime_reservation_key_sha256",
        "request_sha256",
        "one_shot_policy_sha256",
        "source_commit_git_sha1",
        "execution_environment_sha256",
        "historical_case_ids_sha256",
        "author_id",
        "operator_id",
        "reviewer_id",
        "nonce_sha256",
    ):
        if payload.get(binding_field) != expected.get(binding_field):
            raise ExternalReservationContractError(
                f"external reservation {binding_field} is cross-wired"
            )
    reserved_run_ordinal = _integer(
        payload.get("reserved_run_ordinal"),
        name="reserved_run_ordinal",
        minimum=1,
    )
    maximum_lifetime_reservations = _integer(
        payload.get("maximum_lifetime_reservations"),
        name="maximum_lifetime_reservations",
        minimum=1,
    )
    ledger_sequence = _integer(
        payload.get("ledger_sequence"),
        name="receipt ledger_sequence",
        minimum=1,
    )
    if (
        reserved_run_ordinal != 1
        or maximum_lifetime_reservations != 1
        or ledger_sequence != 1
        or payload.get("immutable") is not True
        or payload.get("append_only") is not True
        or payload.get("test_only") is not False
        or payload.get("author_identity_authenticated") is not True
        or payload.get("operator_identity_authenticated") is not True
        or payload.get("reviewer_identity_authenticated") is not True
        or payload.get("github_actions_operator") is not False
    ):
        raise ExternalReservationContractError(
            "external reservation is not the sole immutable production receipt"
        )
    committed = _integer(
        payload.get("committed_at_unix"),
        name="committed_at_unix",
    )
    retention = _integer(
        payload.get("retention_until_unix"),
        name="retention_until_unix",
    )
    if not request.issued_at_unix <= committed <= request.expires_at_unix:
        raise ExternalReservationContractError(
            "external reservation was committed outside the request window"
        )
    if now < committed:
        raise ExternalReservationContractError("external receipt is from the future")
    if revocation.generated_at_unix < committed:
        raise ExternalReservationContractError(
            "revocation snapshot predates the committed reservation"
        )
    if retention - committed < MIN_RETENTION_SECONDS or now >= retention:
        raise ExternalReservationContractError("external receipt retention is invalid")
    if any(payload.get(key) is not False for key in _FALSE_AUTHORITY_KEYS):
        raise ExternalReservationContractError(
            "external reservation receipt exceeds its authority boundary"
        )
    verified_fields: dict[str, object] = {
        "provider_id": trust_anchor.provider_id,
        "reservation_id": reservation_id,
        "lifetime_reservation_key_sha256": request.lifetime_reservation_key_sha256,
        "global_reservation_key_sha256": request.global_reservation_key_sha256,
        "request_sha256": request.request_sha256,
        "receipt_sha256": receipt_sha256,
        "receipt_signature_sha256": receipt_signature_sha256,
        "revocation_snapshot_sha256": revocation.snapshot_sha256,
        "committed_at_unix": committed,
        "retention_until_unix": retention,
        "author_id": request.author_id,
        "operator_id": request.operator_id,
        "reviewer_id": request.reviewer_id,
        "source_commit_git_sha1": request.source_commit_git_sha1,
        "execution_environment_sha256": request.execution_environment_sha256,
        "authoritative_for_execution": False,
    }
    verification_proof = hmac.new(
        _VERIFIED_RECEIPT_PROOF_SECRET,
        _canonical_bytes(verified_fields),
        hashlib.sha256,
    ).hexdigest()
    return VerifiedExternalReservationReceipt(
        **verified_fields,
        _verification_proof_sha256=verification_proof,
    )


def external_reservation_operational_blockers(
    policy: Mapping[str, Any],
) -> tuple[str, ...]:
    """Return explicit blockers; the committed repository must remain blocked."""

    verify_external_reservation_policy(policy)
    provider = _mapping(policy.get("provider"), name="provider")
    blockers: list[str] = []
    if provider.get("provider_operational") is not True:
        blockers.append("external_reservation_provider_not_operational")
    if not provider.get("endpoint"):
        blockers.append("external_reservation_endpoint_not_configured")
    if not provider.get("trust_anchor_public_key_hex"):
        blockers.append("external_reservation_trust_anchor_not_configured")
    authority = _mapping(policy.get("authority"), name="authority")
    if authority.get("historical_execution_operational") is not True:
        blockers.append("historical_execution_operational_authority_false")
    return tuple(blockers)


def request_external_reservation(
    *,
    client: ExternalReservationLedgerClient,
    request: ExternalReservationRequest,
    policy: Mapping[str, Any],
    trust_anchor: ExternalLedgerTrustAnchor,
) -> VerifiedExternalReservationReceipt:
    """Fail before network unless a separately reviewed policy becomes operational."""

    blockers = external_reservation_operational_blockers(policy)
    if blockers:
        raise ExternalReservationContractError(";".join(blockers))
    provider = _mapping(policy.get("provider"), name="provider")
    if (
        provider.get("provider_id") != trust_anchor.provider_id
        or provider.get("trust_anchor_public_key_hex")
        != trust_anchor.public_key_raw.hex()
    ):
        raise ExternalReservationContractError(
            "ledger trust anchor is not bound to the reviewed provider policy"
        )
    if client.provider_id != trust_anchor.provider_id:
        raise ExternalReservationContractError("ledger client/provider cross-wire")
    if client.production_authority is not True:
        raise ExternalReservationContractError(
            "test doubles and nonproduction clients cannot reserve authority"
        )
    lookup = getattr(client, "lookup", None)
    if not callable(lookup):
        raise ExternalReservationContractError(
            "production ledger client lacks ambiguous-commit receipt recovery"
        )
    now = _integer(int(time.time()), name="current_unix_time")
    if not request.issued_at_unix <= now < request.expires_at_unix:
        raise ExternalReservationContractError(
            "external reservation request is outside its active window"
        )
    canonical_request = _canonical_bytes(request.to_dict())
    try:
        signed_envelopes = client.reserve(canonical_request)
    except Exception as reserve_error:
        try:
            recovered = lookup(canonical_request)
        except Exception as lookup_error:
            raise ExternalReservationContractError(
                "external reservation commit is ambiguous and recovery failed"
            ) from lookup_error
        if recovered is None:
            raise ExternalReservationContractError(
                "external reservation commit is ambiguous and no receipt was recovered"
            ) from reserve_error
        signed_envelopes = recovered
    try:
        payload, signature, revocation_payload, revocation_signature = signed_envelopes
    except (TypeError, ValueError) as exc:
        raise ExternalReservationContractError(
            "external reservation provider returned an invalid envelope set"
        ) from exc
    return verify_signed_external_reservation_receipt(
        payload_bytes=payload,
        signature_bytes=signature,
        request=request,
        trust_anchor=trust_anchor,
        now_unix=now,
        revocation_payload_bytes=revocation_payload,
        revocation_signature_bytes=revocation_signature,
    )


def build_external_reservation_binding(
    *,
    document_role: str,
    document_sha256: str,
    reservation: VerifiedExternalReservationReceipt,
) -> dict[str, Any]:
    """Bind a local/downstream receipt to the externally committed identity."""

    if document_role not in DOWNSTREAM_ROLES:
        raise ExternalReservationContractError("downstream document role is invalid")
    if not _is_sha256(document_sha256):
        raise ExternalReservationContractError("downstream document hash is invalid")
    if (
        type(reservation) is not VerifiedExternalReservationReceipt
        or reservation.authoritative_for_execution is not False
    ):
        raise ExternalReservationContractError(
            "downstream reservation must be an exact non-authorizing verified receipt"
        )
    reservation._require_verifier_proof()
    binding: dict[str, Any] = {
        "schema_id": BINDING_SCHEMA_ID,
        "document_role": document_role,
        "document_sha256": document_sha256,
        "provider_id": reservation.provider_id,
        "external_reservation_id": reservation.reservation_id,
        "external_reservation_receipt_sha256": reservation.receipt_sha256,
        "external_reservation_receipt_signature_sha256": (
            reservation.receipt_signature_sha256
        ),
        "external_revocation_snapshot_sha256": (reservation.revocation_snapshot_sha256),
        "lifetime_reservation_key_sha256": (
            reservation.lifetime_reservation_key_sha256
        ),
        "global_reservation_key_sha256": (reservation.global_reservation_key_sha256),
        "request_sha256": reservation.request_sha256,
        "author_id": reservation.author_id,
        "source_commit_git_sha1": reservation.source_commit_git_sha1,
        "execution_environment_sha256": (reservation.execution_environment_sha256),
        "authoritative_for_execution": False,
        **{key: False for key in _FALSE_AUTHORITY_KEYS},
    }
    binding["binding_sha256"] = _sha256(binding)
    return binding


def verify_external_reservation_binding(
    binding: Mapping[str, Any],
    *,
    document_role: str,
    document_sha256: str,
    reservation: VerifiedExternalReservationReceipt,
) -> str:
    expected = build_external_reservation_binding(
        document_role=document_role,
        document_sha256=document_sha256,
        reservation=reservation,
    )
    observed = _mapping(binding, name="external reservation binding")
    if observed != expected:
        raise ExternalReservationContractError(
            "external reservation binding is missing, stale, or cross-wired"
        )
    return str(observed["binding_sha256"])


__all__ = [
    "BINDING_SCHEMA_ID",
    "DOWNSTREAM_ROLES",
    "EXPECTED_HISTORICAL_CASE_IDS_SHA256",
    "EXPECTED_ONE_SHOT_POLICY_SHA256",
    "EXPECTED_POLICY_SHA256",
    "ExternalLedgerTrustAnchor",
    "ExternalReservationContractError",
    "ExternalReservationLedgerClient",
    "ExternalReservationRequest",
    "POLICY_SCHEMA_ID",
    "RECEIPT_SCHEMA_ID",
    "REQUEST_SCHEMA_ID",
    "REVOCATION_SNAPSHOT_SCHEMA_ID",
    "VerifiedExternalRevocationSnapshot",
    "build_external_reservation_binding",
    "external_reservation_operational_blockers",
    "request_external_reservation",
    "verify_external_reservation_binding",
    "verify_external_reservation_policy",
    "verify_signed_external_revocation_snapshot",
    "verify_signed_external_reservation_receipt",
]
