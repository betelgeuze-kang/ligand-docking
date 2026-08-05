"""External immutable reservation contract for the historical one-shot A/B.

This module defines request, signed receipt, verification, and provider
interfaces. The included in-memory provider is test-only and grants no
repository execution authority. A separately reviewed external service must
implement the same contract before actual historical execution.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import threading
from typing import Mapping, Protocol, runtime_checkable

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


REQUEST_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_external_reservation_request/1.0.0"
)
RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_external_reservation_receipt/1.0.0"
)
POLICY_SHA256 = (
    "b9d2dc1c716c0f954ba5a9f30ecc08168eb29331293b8df5c08fa67ca7ae377f"
)
COHORT_SHA256 = (
    "cd2c24c9c7d937865f40352375e8a17c6b83b0b0fab8c134218d2c29537493c1"
)
MAX_CLOCK_SKEW_SECONDS = 300
MAX_RECEIPT_LIFETIME_SECONDS = 86400
FORBIDDEN_OPERATOR_PREFIXES = (
    "github-actions",
    "dependabot",
    "workflow-",
)


class ExternalReservationError(ValueError):
    """Raised when external one-shot reservation evidence fails closed."""


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
        raise ExternalReservationError(
            "reservation evidence is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _digest(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ExternalReservationError(f"{name} must be a lowercase SHA-256")
    return value


def _sha1(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 40
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ExternalReservationError(f"{name} must be a lowercase Git SHA-1")
    return value


def _operator(value: object) -> str:
    if not isinstance(value, str) or not 3 <= len(value) <= 128:
        raise ExternalReservationError("operator_id is invalid")
    normalized = value.strip()
    if normalized != value or any(
        normalized.lower().startswith(prefix)
        for prefix in FORBIDDEN_OPERATOR_PREFIXES
    ):
        raise ExternalReservationError(
            "CI, workflow, or unnormalized identities cannot reserve execution"
        )
    return value


def _timestamp(value: object, *, name: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ExternalReservationError(f"{name} must be canonical UTC")
    try:
        observed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ExternalReservationError(
            f"{name} must be canonical UTC"
        ) from exc
    if observed.tzinfo != timezone.utc or observed.microsecond:
        raise ExternalReservationError(f"{name} must be whole-second UTC")
    if observed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise ExternalReservationError(f"{name} must be canonical UTC")
    return observed


def _timestamp_text(value: datetime) -> str:
    normalized = value.astimezone(timezone.utc).replace(microsecond=0)
    return normalized.strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class ExternalReservationRequest:
    source_commit_git_sha1: str
    execution_environment_sha256: str
    operator_id: str
    nonce_sha256: str

    def __post_init__(self) -> None:
        _sha1(self.source_commit_git_sha1, name="source_commit_git_sha1")
        _digest(
            self.execution_environment_sha256,
            name="execution_environment_sha256",
        )
        _operator(self.operator_id)
        _digest(self.nonce_sha256, name="nonce_sha256")

    @property
    def reservation_key_sha256(self) -> str:
        return _sha256(
            {
                "policy_sha256": POLICY_SHA256,
                "cohort_sha256": COHORT_SHA256,
                "source_commit_git_sha1": self.source_commit_git_sha1,
                "execution_environment_sha256": (
                    self.execution_environment_sha256
                ),
            }
        )

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "schema_id": REQUEST_SCHEMA_ID,
            "policy_sha256": POLICY_SHA256,
            "cohort_sha256": COHORT_SHA256,
            "source_commit_git_sha1": self.source_commit_git_sha1,
            "execution_environment_sha256": (
                self.execution_environment_sha256
            ),
            "operator_id": self.operator_id,
            "nonce_sha256": self.nonce_sha256,
            "requested_run_ordinal": 1,
            "reservation_key_sha256": self.reservation_key_sha256,
            "historical_execution_authorized": False,
            "fresh_holdout_execution_authorized": False,
            "product_execution_authorized": False,
            "public_or_scientific_claim_authorized": False,
        }
        payload["request_sha256"] = _sha256(payload)
        return payload


def parse_request(value: Mapping[str, object]) -> ExternalReservationRequest:
    expected = {
        "cohort_sha256",
        "execution_environment_sha256",
        "fresh_holdout_execution_authorized",
        "historical_execution_authorized",
        "nonce_sha256",
        "operator_id",
        "policy_sha256",
        "product_execution_authorized",
        "public_or_scientific_claim_authorized",
        "request_sha256",
        "requested_run_ordinal",
        "reservation_key_sha256",
        "schema_id",
        "source_commit_git_sha1",
    }
    if set(value) != expected:
        raise ExternalReservationError(
            "reservation request key set is invalid"
        )
    request = ExternalReservationRequest(
        source_commit_git_sha1=_sha1(
            value.get("source_commit_git_sha1"),
            name="source_commit_git_sha1",
        ),
        execution_environment_sha256=_digest(
            value.get("execution_environment_sha256"),
            name="execution_environment_sha256",
        ),
        operator_id=_operator(value.get("operator_id")),
        nonce_sha256=_digest(value.get("nonce_sha256"), name="nonce_sha256"),
    )
    if (
        value.get("schema_id") != REQUEST_SCHEMA_ID
        or value.get("policy_sha256") != POLICY_SHA256
        or value.get("cohort_sha256") != COHORT_SHA256
        or value.get("requested_run_ordinal") != 1
        or value.get("reservation_key_sha256")
        != request.reservation_key_sha256
        or any(
            value.get(key) is not False
            for key in (
                "historical_execution_authorized",
                "fresh_holdout_execution_authorized",
                "product_execution_authorized",
                "public_or_scientific_claim_authorized",
            )
        )
        or value.get("request_sha256")
        != request.to_dict()["request_sha256"]
        or dict(value) != request.to_dict()
    ):
        raise ExternalReservationError(
            "reservation request does not independently rederive"
        )
    return request


@dataclass(frozen=True)
class VerifiedExternalReservation:
    receipt_sha256: str
    reservation_key_sha256: str
    request_sha256: str
    ledger_id: str
    ledger_sequence: int
    source_commit_git_sha1: str
    execution_environment_sha256: str
    operator_id: str
    nonce_sha256: str
    reserved_at_utc: str
    expires_at_utc: str


def _signed_projection(receipt: Mapping[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, value in receipt.items()
        if key not in {"signature_base64", "receipt_sha256"}
    }


def verify_external_reservation_receipt(
    receipt: Mapping[str, object],
    *,
    request: Mapping[str, object],
    trusted_public_key_raw: bytes,
    now_utc: datetime,
    revoked_receipt_sha256s: frozenset[str] = frozenset(),
) -> VerifiedExternalReservation:
    expected = {
        "append_only",
        "cohort_sha256",
        "execution_environment_sha256",
        "expires_at_utc",
        "fresh_holdout_execution_authorized",
        "historical_execution_authorized",
        "immutable",
        "ledger_id",
        "ledger_sequence",
        "nonce_sha256",
        "operator_id",
        "policy_sha256",
        "product_execution_authorized",
        "public_or_scientific_claim_authorized",
        "receipt_sha256",
        "request_sha256",
        "reservation_key_sha256",
        "reserved_at_utc",
        "run_ordinal",
        "schema_id",
        "signature_base64",
        "source_commit_git_sha1",
    }
    if set(receipt) != expected:
        raise ExternalReservationError(
            "external reservation receipt key set is invalid"
        )
    parsed_request = parse_request(request)
    if not isinstance(trusted_public_key_raw, bytes) or len(
        trusted_public_key_raw
    ) != 32:
        raise ExternalReservationError(
            "trusted Ed25519 public key is invalid"
        )
    projection = _signed_projection(receipt)
    receipt_sha256 = _sha256(projection)
    if receipt.get("receipt_sha256") != receipt_sha256:
        raise ExternalReservationError(
            "external reservation self-hash is invalid"
        )
    if receipt_sha256 in revoked_receipt_sha256s:
        raise ExternalReservationError(
            "external reservation receipt is revoked"
        )
    signature = receipt.get("signature_base64")
    if not isinstance(signature, str):
        raise ExternalReservationError(
            "external reservation signature is invalid"
        )
    try:
        signature_bytes = base64.b64decode(signature, validate=True)
        Ed25519PublicKey.from_public_bytes(trusted_public_key_raw).verify(
            signature_bytes,
            _canonical_bytes(projection),
        )
    except (ValueError, InvalidSignature) as exc:
        raise ExternalReservationError(
            "external reservation signature verification failed"
        ) from exc
    reserved = _timestamp(
        receipt.get("reserved_at_utc"), name="reserved_at_utc"
    )
    expires = _timestamp(
        receipt.get("expires_at_utc"), name="expires_at_utc"
    )
    now = now_utc.astimezone(timezone.utc).replace(microsecond=0)
    if expires <= reserved or int((expires - reserved).total_seconds()) > (
        MAX_RECEIPT_LIFETIME_SECONDS
    ):
        raise ExternalReservationError(
            "external reservation lifetime is invalid"
        )
    if now < reserved or now > expires:
        raise ExternalReservationError(
            "external reservation receipt is not current"
        )
    request_dict = parsed_request.to_dict()
    if (
        receipt.get("schema_id") != RECEIPT_SCHEMA_ID
        or receipt.get("policy_sha256") != POLICY_SHA256
        or receipt.get("cohort_sha256") != COHORT_SHA256
        or receipt.get("request_sha256") != request_dict["request_sha256"]
        or receipt.get("reservation_key_sha256")
        != parsed_request.reservation_key_sha256
        or receipt.get("source_commit_git_sha1")
        != parsed_request.source_commit_git_sha1
        or receipt.get("execution_environment_sha256")
        != parsed_request.execution_environment_sha256
        or receipt.get("operator_id") != parsed_request.operator_id
        or receipt.get("nonce_sha256") != parsed_request.nonce_sha256
        or receipt.get("run_ordinal") != 1
        or receipt.get("ledger_sequence") != 1
        or not isinstance(receipt.get("ledger_id"), str)
        or not receipt.get("ledger_id")
        or receipt.get("immutable") is not True
        or receipt.get("append_only") is not True
        or any(
            receipt.get(key) is not False
            for key in (
                "historical_execution_authorized",
                "fresh_holdout_execution_authorized",
                "product_execution_authorized",
                "public_or_scientific_claim_authorized",
            )
        )
    ):
        raise ExternalReservationError(
            "external reservation receipt is cross-wired or over-authorizing"
        )
    return VerifiedExternalReservation(
        receipt_sha256=receipt_sha256,
        reservation_key_sha256=parsed_request.reservation_key_sha256,
        request_sha256=str(request_dict["request_sha256"]),
        ledger_id=str(receipt["ledger_id"]),
        ledger_sequence=1,
        source_commit_git_sha1=parsed_request.source_commit_git_sha1,
        execution_environment_sha256=(
            parsed_request.execution_environment_sha256
        ),
        operator_id=parsed_request.operator_id,
        nonce_sha256=parsed_request.nonce_sha256,
        reserved_at_utc=_timestamp_text(reserved),
        expires_at_utc=_timestamp_text(expires),
    )


@runtime_checkable
class ExternalReservationProvider(Protocol):
    """Interface an independently operated append-only service must expose."""

    def reserve(
        self,
        request: Mapping[str, object],
    ) -> Mapping[str, object]:
        """Atomically create the sole receipt or fail if the key exists."""

    def lookup(
        self,
        reservation_key_sha256: str,
    ) -> Mapping[str, object] | None:
        """Return the immutable receipt for a reservation key."""


class TestOnlyInMemoryReservationProvider:
    """Deterministic single-winner provider used only by unit tests."""

    operational_for_historical_execution = False

    def __init__(self, receipt_factory) -> None:
        self._receipt_factory = receipt_factory
        self._lock = threading.Lock()
        self._receipts: dict[str, Mapping[str, object]] = {}
        self._nonces: set[str] = set()

    def reserve(
        self,
        request: Mapping[str, object],
    ) -> Mapping[str, object]:
        parsed = parse_request(request)
        with self._lock:
            if parsed.nonce_sha256 in self._nonces:
                raise ExternalReservationError(
                    "reservation nonce already consumed"
                )
            self._nonces.add(parsed.nonce_sha256)
            key = parsed.reservation_key_sha256
            if key in self._receipts:
                raise ExternalReservationError(
                    "the global run ordinal has already been reserved"
                )
            receipt = self._receipt_factory(parsed.to_dict())
            self._receipts[key] = receipt
            return receipt

    def lookup(
        self,
        reservation_key_sha256: str,
    ) -> Mapping[str, object] | None:
        _digest(
            reservation_key_sha256,
            name="reservation_key_sha256",
        )
        with self._lock:
            return self._receipts.get(reservation_key_sha256)


__all__ = [
    "COHORT_SHA256",
    "ExternalReservationError",
    "ExternalReservationProvider",
    "ExternalReservationRequest",
    "MAX_RECEIPT_LIFETIME_SECONDS",
    "POLICY_SHA256",
    "RECEIPT_SCHEMA_ID",
    "REQUEST_SCHEMA_ID",
    "TestOnlyInMemoryReservationProvider",
    "VerifiedExternalReservation",
    "parse_request",
    "verify_external_reservation_receipt",
]
