from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import threading

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import betelgeuze_engine_v2.benchmark.source_paired_clearance_external_reservation as reservation_module
from betelgeuze_engine_v2.benchmark.source_paired_clearance_external_reservation import (
    EXPECTED_HISTORICAL_CASE_IDS_SHA256,
    EXPECTED_ONE_SHOT_POLICY_SHA256,
    ExternalLedgerTrustAnchor,
    ExternalReservationContractError,
    ExternalReservationRequest,
    verify_signed_external_reservation_receipt,
)


class _TestOnlyInMemoryReservationProvider:
    """Deterministic test double; never carries production authority."""

    __test__ = False
    production_authority = False
    provider_id = "test-only-memory-ledger"

    def __init__(self, private_key: Ed25519PrivateKey) -> None:
        self._private_key = private_key
        self._lock = threading.Lock()
        self._receipts: dict[str, tuple[bytes, bytes]] = {}
        self._used_nonces: set[str] = set()

    def reserve(
        self,
        request: ExternalReservationRequest,
    ) -> tuple[bytes, bytes]:
        key = request.global_reservation_key_sha256
        with self._lock:
            if request.nonce_sha256 in self._used_nonces:
                raise ExternalReservationContractError(
                    "reservation nonce replayed"
                )
            if key in self._receipts:
                raise ExternalReservationContractError(
                    "global reservation already exists"
                )
            self._used_nonces.add(request.nonce_sha256)
            committed = request.issued_at_unix + 1
            payload: dict[str, object] = {
                "schema_id": reservation_module.RECEIPT_SCHEMA_ID,
                "provider_id": self.provider_id,
                "reservation_id": f"reservation-{key[:16]}",
                "global_reservation_key_sha256": key,
                "request_sha256": request.request_sha256,
                "one_shot_policy_sha256": request.one_shot_policy_sha256,
                "source_commit_git_sha1": request.source_commit_git_sha1,
                "execution_environment_sha256": (
                    request.execution_environment_sha256
                ),
                "historical_case_ids_sha256": (
                    request.historical_case_ids_sha256
                ),
                "operator_id": request.operator_id,
                "reviewer_id": request.reviewer_id,
                "nonce_sha256": request.nonce_sha256,
                "reserved_run_ordinal": 1,
                "maximum_lifetime_reservations": 1,
                "ledger_sequence": 1,
                "committed_at_unix": committed,
                "retention_until_unix": (
                    committed + reservation_module.MIN_RETENTION_SECONDS + 1
                ),
                "immutable": True,
                "append_only": True,
                "revoked": False,
                "test_only": False,
                "historical_execution_operational": False,
                "fresh_holdout_execution_authorized": False,
                "stage0_admission_authority": False,
                "profile_promotion_authority": False,
                "product_execution_authorized": False,
                "customer_pose_emission_authorized": False,
                "public_or_scientific_claim_authorized": False,
            }
            payload["receipt_sha256"] = reservation_module._sha256(payload)
            payload_bytes = reservation_module._canonical_bytes(payload)
            signed = (payload_bytes, self._private_key.sign(payload_bytes))
            self._receipts[key] = signed
            return signed

    def lookup(self, reservation_key: str) -> tuple[bytes, bytes] | None:
        with self._lock:
            return self._receipts.get(reservation_key)


def _request(*, nonce: str, environment: str = "2" * 64) -> ExternalReservationRequest:
    return ExternalReservationRequest(
        one_shot_policy_sha256=EXPECTED_ONE_SHOT_POLICY_SHA256,
        source_commit_git_sha1="1" * 40,
        execution_environment_sha256=environment,
        historical_case_ids_sha256=EXPECTED_HISTORICAL_CASE_IDS_SHA256,
        operator_id=f"operator-{nonce[:8]}",
        reviewer_id=f"reviewer-{nonce[:8]}",
        nonce_sha256=nonce,
        issued_at_unix=1_800_000_000,
        expires_at_unix=1_800_000_600,
    )


def _trust_anchor(
    private_key: Ed25519PrivateKey,
) -> ExternalLedgerTrustAnchor:
    public_raw = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return ExternalLedgerTrustAnchor(
        provider_id=_TestOnlyInMemoryReservationProvider.provider_id,
        public_key_raw=public_raw,
    )


def test_two_independent_clients_have_exactly_one_global_winner() -> None:
    private_key = Ed25519PrivateKey.generate()
    provider = _TestOnlyInMemoryReservationProvider(private_key)
    requests = (_request(nonce="3" * 64), _request(nonce="4" * 64))

    def reserve(request: ExternalReservationRequest):
        try:
            return request, provider.reserve(request), None
        except ExternalReservationContractError as error:
            return request, None, str(error)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(reserve, requests))

    winners = tuple(item for item in results if item[1] is not None)
    losers = tuple(item for item in results if item[2] is not None)
    assert len(winners) == 1
    assert len(losers) == 1
    assert losers[0][2] == "global reservation already exists"

    winning_request, signed, _error = winners[0]
    assert signed is not None
    payload, signature = signed
    verified = verify_signed_external_reservation_receipt(
        payload_bytes=payload,
        signature_bytes=signature,
        request=winning_request,
        trust_anchor=_trust_anchor(private_key),
        now_unix=1_800_000_100,
    )
    assert verified.global_reservation_key_sha256 == (
        winning_request.global_reservation_key_sha256
    )
    assert verified.authoritative_for_execution is False


def test_deleting_local_state_does_not_restore_provider_authority() -> None:
    private_key = Ed25519PrivateKey.generate()
    provider = _TestOnlyInMemoryReservationProvider(private_key)
    request = _request(nonce="5" * 64)
    signed = provider.reserve(request)
    local_state = {"reservation": signed}

    local_state.clear()

    assert provider.lookup(request.global_reservation_key_sha256) == signed
    with pytest.raises(
        ExternalReservationContractError,
        match="already exists",
    ):
        provider.reserve(_request(nonce="6" * 64))


def test_nonce_replay_is_rejected_even_for_another_global_key() -> None:
    private_key = Ed25519PrivateKey.generate()
    provider = _TestOnlyInMemoryReservationProvider(private_key)
    nonce = "7" * 64
    provider.reserve(_request(nonce=nonce))

    with pytest.raises(
        ExternalReservationContractError,
        match="nonce replayed",
    ):
        provider.reserve(_request(nonce=nonce, environment="8" * 64))


def test_unknown_global_key_lookup_is_absent() -> None:
    provider = _TestOnlyInMemoryReservationProvider(
        Ed25519PrivateKey.generate()
    )

    assert provider.lookup("9" * 64) is None
