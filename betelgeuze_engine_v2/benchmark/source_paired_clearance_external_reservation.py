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
import json
from typing import Any, Mapping, Protocol, Sequence

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


POLICY_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_"
    "external_reservation_policy/1.0.0"
)
REQUEST_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_"
    "external_reservation_request/1.0.0"
)
RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_"
    "external_reservation_receipt/1.0.0"
)
BINDING_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_"
    "external_reservation_binding/1.0.0"
)
EXPECTED_POLICY_SHA256 = (
    "5e6417cb27f243effa698e860f43569751a0ea735858468151e8c9b75efecf4b"
)
EXPECTED_ONE_SHOT_POLICY_SHA256 = (
    "b9d2dc1c716c0f954ba5a9f30ecc08168eb29331293b8df5c08fa67ca7ae377f"
)
EXPECTED_HISTORICAL_CASE_IDS_SHA256 = (
    "cd2c24c9c7d937865f40352375e8a17c6b83b0b0fab8c134218d2c29537493c1"
)
MAX_REQUEST_LIFETIME_SECONDS = 15 * 60
MIN_RETENTION_SECONDS = 10 * 365 * 24 * 60 * 60
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
        "maximum_lifetime_reservations": 1,
        "reserved_run_ordinal": 1,
        "atomic_create_if_absent_required": True,
        "deleted_local_store_does_not_restore_authority": True,
    }:
        raise ExternalReservationContractError("global reservation key contract drifted")

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
        "provider_operational": False,
    }:
        raise ExternalReservationContractError(
            "provider must remain explicitly unconfigured and non-operational"
        )

    roles = _mapping(policy.get("roles"), name="roles")
    if roles != {
        "author_reviewer_operator_distinct_required": True,
        "operator_identity_required": True,
        "reviewer_identity_required": True,
        "github_actions_operator_forbidden": True,
        "test_double_authority_forbidden": True,
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
        operator = _identity(self.operator_id, name="operator_id")
        reviewer = _identity(self.reviewer_id, name="reviewer_id")
        if operator == reviewer:
            raise ExternalReservationContractError(
                "operator and reviewer identities must differ"
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
            "operator_id": self.operator_id,
            "reviewer_id": self.reviewer_id,
            "nonce_sha256": self.nonce_sha256,
            "issued_at_unix": self.issued_at_unix,
            "expires_at_unix": self.expires_at_unix,
            "requested_run_ordinal": 1,
            "maximum_lifetime_reservations": 1,
        }

    @property
    def global_reservation_key_sha256(self) -> str:
        return _sha256(
            {
                "one_shot_policy_sha256": self.one_shot_policy_sha256,
                "source_commit_git_sha1": self.source_commit_git_sha1,
                "execution_environment_sha256": self.execution_environment_sha256,
                "historical_case_ids_sha256": self.historical_case_ids_sha256,
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


@dataclass(frozen=True, slots=True)
class VerifiedExternalReservationReceipt:
    provider_id: str
    reservation_id: str
    global_reservation_key_sha256: str
    request_sha256: str
    receipt_sha256: str
    committed_at_unix: int
    retention_until_unix: int
    operator_id: str
    reviewer_id: str
    source_commit_git_sha1: str
    execution_environment_sha256: str
    authoritative_for_execution: bool = False


class ExternalReservationLedgerClient(Protocol):
    """Network boundary implemented only by separately reviewed operator code."""

    provider_id: str
    production_authority: bool

    def reserve(self, canonical_request: bytes) -> tuple[bytes, bytes]:
        """Return signed payload bytes and raw Ed25519 signature bytes."""


def verify_signed_external_reservation_receipt(
    *,
    payload_bytes: bytes,
    signature_bytes: bytes,
    request: ExternalReservationRequest,
    trust_anchor: ExternalLedgerTrustAnchor,
    now_unix: int,
    revoked_receipt_sha256s: Sequence[str] = (),
) -> VerifiedExternalReservationReceipt:
    """Verify one immutable receipt without granting repository execution authority."""

    now = _integer(now_unix, name="now_unix")
    if not isinstance(signature_bytes, bytes) or len(signature_bytes) != 64:
        raise ExternalReservationContractError("Ed25519 signature is invalid")
    payload = _strict_json_object(payload_bytes, name="external reservation receipt")
    expected_keys = {
        "schema_id",
        "provider_id",
        "reservation_id",
        "global_reservation_key_sha256",
        "request_sha256",
        "one_shot_policy_sha256",
        "source_commit_git_sha1",
        "execution_environment_sha256",
        "historical_case_ids_sha256",
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
        *_FALSE_AUTHORITY_KEYS,
        "receipt_sha256",
    }
    _exact_keys(payload, expected_keys, name="external reservation receipt")
    if payload.get("schema_id") != RECEIPT_SCHEMA_ID:
        raise ExternalReservationContractError("external receipt schema is invalid")
    try:
        Ed25519PublicKey.from_public_bytes(trust_anchor.public_key_raw).verify(
            signature_bytes,
            payload_bytes,
        )
    except (InvalidSignature, ValueError) as exc:
        raise ExternalReservationContractError(
            "external reservation signature verification failed"
        ) from exc
    receipt_sha256 = _verify_self_hash(
        payload,
        hash_field="receipt_sha256",
        name="external reservation receipt",
    )
    revoked = set(revoked_receipt_sha256s)
    if any(not _is_sha256(item) for item in revoked):
        raise ExternalReservationContractError("revocation set is invalid")
    if receipt_sha256 in revoked or payload.get("revoked") is not False:
        raise ExternalReservationContractError("external reservation is revoked")
    if payload.get("provider_id") != trust_anchor.provider_id:
        raise ExternalReservationContractError("provider trust anchor is cross-wired")
    reservation_id = _identity(payload.get("reservation_id"), name="reservation_id")
    expected = request.to_dict()
    for binding_field in (
        "global_reservation_key_sha256",
        "request_sha256",
        "one_shot_policy_sha256",
        "source_commit_git_sha1",
        "execution_environment_sha256",
        "historical_case_ids_sha256",
        "operator_id",
        "reviewer_id",
        "nonce_sha256",
    ):
        if payload.get(binding_field) != expected.get(binding_field):
            raise ExternalReservationContractError(
                f"external reservation {binding_field} is cross-wired"
            )
    if (
        payload.get("reserved_run_ordinal") != 1
        or payload.get("maximum_lifetime_reservations") != 1
        or payload.get("ledger_sequence") != 1
        or payload.get("immutable") is not True
        or payload.get("append_only") is not True
        or payload.get("test_only") is not False
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
    if retention - committed < MIN_RETENTION_SECONDS or now >= retention:
        raise ExternalReservationContractError("external receipt retention is invalid")
    if any(payload.get(key) is not False for key in _FALSE_AUTHORITY_KEYS):
        raise ExternalReservationContractError(
            "external reservation receipt exceeds its authority boundary"
        )
    return VerifiedExternalReservationReceipt(
        provider_id=trust_anchor.provider_id,
        reservation_id=reservation_id,
        global_reservation_key_sha256=request.global_reservation_key_sha256,
        request_sha256=request.request_sha256,
        receipt_sha256=receipt_sha256,
        committed_at_unix=committed,
        retention_until_unix=retention,
        operator_id=request.operator_id,
        reviewer_id=request.reviewer_id,
        source_commit_git_sha1=request.source_commit_git_sha1,
        execution_environment_sha256=request.execution_environment_sha256,
        authoritative_for_execution=False,
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
    now_unix: int,
    revoked_receipt_sha256s: Sequence[str] = (),
) -> VerifiedExternalReservationReceipt:
    """Fail before network unless a separately reviewed policy becomes operational."""

    blockers = external_reservation_operational_blockers(policy)
    if blockers:
        raise ExternalReservationContractError(";".join(blockers))
    if client.provider_id != trust_anchor.provider_id:
        raise ExternalReservationContractError("ledger client/provider cross-wire")
    if client.production_authority is not True:
        raise ExternalReservationContractError(
            "test doubles and nonproduction clients cannot reserve authority"
        )
    try:
        payload, signature = client.reserve(_canonical_bytes(request.to_dict()))
    except Exception as exc:
        raise ExternalReservationContractError(
            "external reservation provider is unavailable"
        ) from exc
    return verify_signed_external_reservation_receipt(
        payload_bytes=payload,
        signature_bytes=signature,
        request=request,
        trust_anchor=trust_anchor,
        now_unix=now_unix,
        revoked_receipt_sha256s=revoked_receipt_sha256s,
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
    binding: dict[str, Any] = {
        "schema_id": BINDING_SCHEMA_ID,
        "document_role": document_role,
        "document_sha256": document_sha256,
        "provider_id": reservation.provider_id,
        "external_reservation_id": reservation.reservation_id,
        "external_reservation_receipt_sha256": reservation.receipt_sha256,
        "global_reservation_key_sha256": (
            reservation.global_reservation_key_sha256
        ),
        "request_sha256": reservation.request_sha256,
        "source_commit_git_sha1": reservation.source_commit_git_sha1,
        "execution_environment_sha256": (
            reservation.execution_environment_sha256
        ),
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
    "VerifiedExternalReservationReceipt",
    "build_external_reservation_binding",
    "external_reservation_operational_blockers",
    "request_external_reservation",
    "verify_external_reservation_binding",
    "verify_external_reservation_policy",
    "verify_signed_external_reservation_receipt",
]
