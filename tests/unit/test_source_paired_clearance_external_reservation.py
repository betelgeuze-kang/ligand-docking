from __future__ import annotations

import base64
import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import threading

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import betelgeuze_engine_v2.benchmark.source_paired_clearance_external_reservation as mod
from betelgeuze_engine_v2.benchmark.source_paired_clearance_external_reservation import (
    ExternalReservationError,
    ExternalReservationRequest,
    TestOnlyInMemoryReservationProvider,
    parse_request,
    verify_external_reservation_receipt,
)


_NOW = datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc)


def _request(
    *,
    nonce: str = "4" * 64,
    operator: str = "operator-alpha",
) -> dict[str, object]:
    return ExternalReservationRequest(
        source_commit_git_sha1="1" * 40,
        execution_environment_sha256="2" * 64,
        operator_id=operator,
        nonce_sha256=nonce,
    ).to_dict()


@pytest.fixture()
def signing():
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )

    def factory(request):
        projection = {
            "schema_id": mod.RECEIPT_SCHEMA_ID,
            "policy_sha256": mod.POLICY_SHA256,
            "cohort_sha256": mod.COHORT_SHA256,
            "request_sha256": request["request_sha256"],
            "reservation_key_sha256": request[
                "reservation_key_sha256"
            ],
            "source_commit_git_sha1": request["source_commit_git_sha1"],
            "execution_environment_sha256": request[
                "execution_environment_sha256"
            ],
            "operator_id": request["operator_id"],
            "nonce_sha256": request["nonce_sha256"],
            "run_ordinal": 1,
            "ledger_id": "external-ledger-test-v1",
            "ledger_sequence": 1,
            "reserved_at_utc": "2026-08-05T12:00:00Z",
            "expires_at_utc": "2026-08-05T13:00:00Z",
            "immutable": True,
            "append_only": True,
            "historical_execution_authorized": False,
            "fresh_holdout_execution_authorized": False,
            "product_execution_authorized": False,
            "public_or_scientific_claim_authorized": False,
        }
        receipt = dict(projection)
        receipt["signature_base64"] = base64.b64encode(
            private.sign(mod._canonical_bytes(projection))
        ).decode("ascii")
        receipt["receipt_sha256"] = mod._sha256(projection)
        return receipt

    return private, public, factory


def test_request_round_trips_and_ci_identity_is_rejected() -> None:
    request = _request()

    assert parse_request(request).to_dict() == request
    assert request["requested_run_ordinal"] == 1
    assert request["historical_execution_authorized"] is False

    with pytest.raises(ExternalReservationError, match="CI|workflow"):
        _request(operator="github-actions-pr-245")


def test_signed_external_receipt_verifies_exact_request(signing) -> None:
    _, public, factory = signing
    request = _request()
    receipt = factory(request)

    verified = verify_external_reservation_receipt(
        receipt,
        request=request,
        trusted_public_key_raw=public,
        now_utc=_NOW,
    )

    assert verified.ledger_sequence == 1
    assert verified.reservation_key_sha256 == request[
        "reservation_key_sha256"
    ]
    assert verified.source_commit_git_sha1 == "1" * 40
    assert verified.execution_environment_sha256 == "2" * 64


def test_two_clone_clients_have_exactly_one_winner(signing) -> None:
    _, _, factory = signing
    provider = TestOnlyInMemoryReservationProvider(factory)
    requests = [
        _request(nonce="a" * 64),
        _request(nonce="b" * 64),
    ]
    winners = []
    failures = []

    def reserve(request):
        try:
            winners.append(provider.reserve(request))
        except ExternalReservationError as exc:
            failures.append(str(exc))

    threads = [
        threading.Thread(target=reserve, args=(row,))
        for row in requests
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(winners) == 1
    assert len(failures) == 1
    assert "already been reserved" in failures[0]
    key = requests[0]["reservation_key_sha256"]
    assert provider.lookup(key) == winners[0]
    assert provider.operational_for_historical_execution is False


def test_deleted_local_state_does_not_restore_provider_authority(
    signing,
) -> None:
    _, _, factory = signing
    provider = TestOnlyInMemoryReservationProvider(factory)
    first = _request(nonce="c" * 64)
    provider.reserve(first)

    local_state = {"reservation": "present"}
    local_state.clear()

    with pytest.raises(
        ExternalReservationError,
        match="already been reserved",
    ):
        provider.reserve(_request(nonce="d" * 64))


def test_nonce_replay_fails_even_for_same_request(signing) -> None:
    _, _, factory = signing
    provider = TestOnlyInMemoryReservationProvider(factory)
    request = _request(nonce="e" * 64)
    provider.reserve(request)

    with pytest.raises(ExternalReservationError, match="nonce"):
        provider.reserve(request)


def test_signature_source_environment_and_authority_tamper_fail(
    signing,
) -> None:
    private, public, factory = signing
    request = _request()
    receipt = factory(request)

    signature_tamper = copy.deepcopy(receipt)
    signature_tamper["ledger_id"] = "another-ledger"
    signature_tamper["receipt_sha256"] = mod._sha256(
        mod._signed_projection(signature_tamper)
    )
    with pytest.raises(ExternalReservationError, match="signature"):
        verify_external_reservation_receipt(
            signature_tamper,
            request=request,
            trusted_public_key_raw=public,
            now_utc=_NOW,
        )

    crosswired_request = _request(nonce="f" * 64)
    crosswired_request["source_commit_git_sha1"] = "9" * 40
    crosswired_request["reservation_key_sha256"] = mod._sha256(
        {
            "policy_sha256": mod.POLICY_SHA256,
            "cohort_sha256": mod.COHORT_SHA256,
            "source_commit_git_sha1": "9" * 40,
            "execution_environment_sha256": "2" * 64,
        }
    )
    crosswired_request["request_sha256"] = mod._sha256(
        {
            key: value
            for key, value in crosswired_request.items()
            if key != "request_sha256"
        }
    )
    with pytest.raises(ExternalReservationError, match="cross-wired"):
        verify_external_reservation_receipt(
            receipt,
            request=crosswired_request,
            trusted_public_key_raw=public,
            now_utc=_NOW,
        )

    authority_tamper = copy.deepcopy(receipt)
    authority_tamper["product_execution_authorized"] = True
    projection = mod._signed_projection(authority_tamper)
    authority_tamper["signature_base64"] = base64.b64encode(
        private.sign(mod._canonical_bytes(projection))
    ).decode("ascii")
    authority_tamper["receipt_sha256"] = mod._sha256(projection)
    with pytest.raises(
        ExternalReservationError,
        match="over-authorizing",
    ):
        verify_external_reservation_receipt(
            authority_tamper,
            request=request,
            trusted_public_key_raw=public,
            now_utc=_NOW,
        )


def test_expired_and_revoked_receipts_fail_closed(signing) -> None:
    _, public, factory = signing
    request = _request()
    receipt = factory(request)

    with pytest.raises(ExternalReservationError, match="not current"):
        verify_external_reservation_receipt(
            receipt,
            request=request,
            trusted_public_key_raw=public,
            now_utc=_NOW + timedelta(hours=2),
        )

    with pytest.raises(ExternalReservationError, match="revoked"):
        verify_external_reservation_receipt(
            receipt,
            request=request,
            trusted_public_key_raw=public,
            now_utc=_NOW,
            revoked_receipt_sha256s=frozenset(
                {receipt["receipt_sha256"]}
            ),
        )


def test_provider_interface_does_not_grant_repository_authority(
    signing,
) -> None:
    _, _, factory = signing
    provider = TestOnlyInMemoryReservationProvider(factory)

    assert provider.operational_for_historical_execution is False
    assert not hasattr(provider, "run")
    assert not hasattr(provider, "delete")
    assert not hasattr(provider, "release")
