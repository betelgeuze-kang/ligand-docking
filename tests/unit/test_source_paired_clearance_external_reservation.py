from __future__ import annotations

import copy
from dataclasses import replace
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import betelgeuze_engine_v2.benchmark.source_paired_clearance_external_reservation as module
from betelgeuze_engine_v2.benchmark.source_paired_clearance_external_reservation import (
    EXPECTED_HISTORICAL_CASE_IDS_SHA256,
    EXPECTED_ONE_SHOT_POLICY_SHA256,
    ExternalLedgerTrustAnchor,
    ExternalReservationContractError,
    ExternalReservationRequest,
    build_external_reservation_binding,
    external_reservation_operational_blockers,
    request_external_reservation,
    verify_external_reservation_binding,
    verify_external_reservation_policy,
    verify_signed_external_reservation_receipt,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_POLICY_PATH = (
    _REPO_ROOT / "config/engine_v2_source_paired_clearance_external_reservation.json"
)


def _policy() -> dict[str, object]:
    return json.loads(_POLICY_PATH.read_text(encoding="utf-8"))


def _request() -> ExternalReservationRequest:
    return ExternalReservationRequest(
        one_shot_policy_sha256=EXPECTED_ONE_SHOT_POLICY_SHA256,
        source_commit_git_sha1="1" * 40,
        execution_environment_sha256="2" * 64,
        historical_case_ids_sha256=EXPECTED_HISTORICAL_CASE_IDS_SHA256,
        author_id="author-gamma",
        operator_id="operator-alpha",
        reviewer_id="reviewer-beta",
        nonce_sha256="3" * 64,
        issued_at_unix=1_800_000_000,
        expires_at_unix=1_800_000_600,
    )


def _signed_receipt(
    request: ExternalReservationRequest,
) -> tuple[
    bytes,
    bytes,
    bytes,
    bytes,
    ExternalLedgerTrustAnchor,
    Ed25519PrivateKey,
]:
    private_key = Ed25519PrivateKey.generate()
    public_raw = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    payload: dict[str, object] = {
        "schema_id": module.RECEIPT_SCHEMA_ID,
        "provider_id": "reviewed-ledger-v1",
        "reservation_id": "reservation-0001",
        "lifetime_reservation_key_sha256": (request.lifetime_reservation_key_sha256),
        "global_reservation_key_sha256": request.global_reservation_key_sha256,
        "request_sha256": request.request_sha256,
        "one_shot_policy_sha256": request.one_shot_policy_sha256,
        "source_commit_git_sha1": request.source_commit_git_sha1,
        "execution_environment_sha256": request.execution_environment_sha256,
        "historical_case_ids_sha256": request.historical_case_ids_sha256,
        "author_id": request.author_id,
        "operator_id": request.operator_id,
        "reviewer_id": request.reviewer_id,
        "nonce_sha256": request.nonce_sha256,
        "reserved_run_ordinal": 1,
        "maximum_lifetime_reservations": 1,
        "ledger_sequence": 1,
        "committed_at_unix": 1_800_000_100,
        "retention_until_unix": (1_800_000_100 + module.MIN_RETENTION_SECONDS + 1),
        "immutable": True,
        "append_only": True,
        "revoked": False,
        "test_only": False,
        "author_identity_authenticated": True,
        "operator_identity_authenticated": True,
        "reviewer_identity_authenticated": True,
        "github_actions_operator": False,
        "historical_execution_operational": False,
        "fresh_holdout_execution_authorized": False,
        "stage0_admission_authority": False,
        "profile_promotion_authority": False,
        "product_execution_authorized": False,
        "customer_pose_emission_authorized": False,
        "public_or_scientific_claim_authorized": False,
    }
    payload["receipt_sha256"] = module._sha256(payload)
    payload_bytes = module._canonical_bytes(payload)
    revocation: dict[str, object] = {
        "schema_id": module.REVOCATION_SNAPSHOT_SCHEMA_ID,
        "provider_id": "reviewed-ledger-v1",
        "ledger_sequence": 1,
        "generated_at_unix": 1_800_000_150,
        "valid_until_unix": 1_800_000_300,
        "revoked_receipt_sha256s": [],
        "append_only": True,
    }
    revocation["snapshot_sha256"] = module._sha256(revocation)
    revocation_bytes = module._canonical_bytes(revocation)
    return (
        payload_bytes,
        private_key.sign(payload_bytes),
        revocation_bytes,
        private_key.sign(revocation_bytes),
        ExternalLedgerTrustAnchor(
            provider_id="reviewed-ledger-v1",
            public_key_raw=public_raw,
        ),
        private_key,
    )


def _operational_policy(
    trust_anchor: ExternalLedgerTrustAnchor,
) -> dict[str, object]:
    policy = copy.deepcopy(_policy())
    policy["provider"] = {
        **policy["provider"],
        "provider_id": trust_anchor.provider_id,
        "endpoint": "https://reviewed.example.invalid",
        "trust_anchor_public_key_hex": trust_anchor.public_key_raw.hex(),
        "provider_operational": True,
    }
    policy["authority"]["historical_execution_operational"] = True
    return policy


def test_current_external_policy_is_explicitly_non_operational() -> None:
    observed = verify_external_reservation_policy(_policy())
    blockers = external_reservation_operational_blockers(_policy())

    assert observed == module.EXPECTED_POLICY_SHA256
    assert blockers == (
        "external_reservation_provider_not_operational",
        "external_reservation_endpoint_not_configured",
        "external_reservation_trust_anchor_not_configured",
        "historical_execution_operational_authority_false",
    )


def test_resealed_operational_or_authority_escalation_fails_closed() -> None:
    changed = _policy()
    changed["provider"]["provider_operational"] = True
    changed["provider"]["endpoint"] = "https://unreviewed.invalid"
    changed["authority"]["historical_execution_operational"] = True
    changed.pop("policy_sha256")
    changed["policy_sha256"] = module._sha256(changed)

    with pytest.raises(
        ExternalReservationContractError,
        match="provider|identity|authority",
    ):
        verify_external_reservation_policy(changed)


def test_request_identity_is_stable_and_role_separated() -> None:
    request = _request()

    assert len(request.request_sha256) == 64
    assert len(request.global_reservation_key_sha256) == 64
    assert request.to_dict()["requested_run_ordinal"] == 1

    with pytest.raises(
        ExternalReservationContractError,
        match="must differ",
    ):
        ExternalReservationRequest(
            one_shot_policy_sha256=EXPECTED_ONE_SHOT_POLICY_SHA256,
            source_commit_git_sha1="1" * 40,
            execution_environment_sha256="2" * 64,
            historical_case_ids_sha256=EXPECTED_HISTORICAL_CASE_IDS_SHA256,
            author_id="same",
            operator_id="same",
            reviewer_id="same",
            nonce_sha256="3" * 64,
            issued_at_unix=1,
            expires_at_unix=2,
        )

    with pytest.raises(
        ExternalReservationContractError,
        match="GitHub Actions",
    ):
        ExternalReservationRequest(
            one_shot_policy_sha256=EXPECTED_ONE_SHOT_POLICY_SHA256,
            source_commit_git_sha1="1" * 40,
            execution_environment_sha256="2" * 64,
            historical_case_ids_sha256=EXPECTED_HISTORICAL_CASE_IDS_SHA256,
            author_id="author",
            operator_id="github-actions[bot]",
            reviewer_id="reviewer",
            nonce_sha256="3" * 64,
            issued_at_unix=1,
            expires_at_unix=2,
        )


def test_valid_signed_receipt_is_verified_but_not_execution_authority() -> None:
    request = _request()
    (
        payload,
        signature,
        revocation_payload,
        revocation_signature,
        trust_anchor,
        _private,
    ) = _signed_receipt(request)

    verified = verify_signed_external_reservation_receipt(
        payload_bytes=payload,
        signature_bytes=signature,
        revocation_payload_bytes=revocation_payload,
        revocation_signature_bytes=revocation_signature,
        request=request,
        trust_anchor=trust_anchor,
        now_unix=1_800_000_200,
    )

    assert verified.reservation_id == "reservation-0001"
    assert verified.global_reservation_key_sha256 == (
        request.global_reservation_key_sha256
    )
    assert verified.authoritative_for_execution is False


@pytest.mark.parametrize(
    "field",
    (
        "reserved_run_ordinal",
        "maximum_lifetime_reservations",
        "ledger_sequence",
    ),
)
def test_signed_receipt_rejects_boolean_integer_counters(field: str) -> None:
    request = _request()
    (
        payload,
        _signature,
        revocation_payload,
        revocation_signature,
        trust_anchor,
        private_key,
    ) = _signed_receipt(request)
    decoded = json.loads(payload)
    decoded[field] = True
    decoded.pop("receipt_sha256")
    decoded["receipt_sha256"] = module._sha256(decoded)
    malformed = module._canonical_bytes(decoded)

    with pytest.raises(ExternalReservationContractError, match=field):
        verify_signed_external_reservation_receipt(
            payload_bytes=malformed,
            signature_bytes=private_key.sign(malformed),
            revocation_payload_bytes=revocation_payload,
            revocation_signature_bytes=revocation_signature,
            request=request,
            trust_anchor=trust_anchor,
            now_unix=1_800_000_200,
        )


def test_signed_receipt_rejects_tamper_crosswire_and_revocation() -> None:
    request = _request()
    (
        payload,
        signature,
        revocation_payload,
        revocation_signature,
        trust_anchor,
        private_key,
    ) = _signed_receipt(request)
    decoded = json.loads(payload)
    decoded["execution_environment_sha256"] = "4" * 64
    decoded.pop("receipt_sha256")
    decoded["receipt_sha256"] = module._sha256(decoded)
    tampered_bytes = module._canonical_bytes(decoded)

    with pytest.raises(ExternalReservationContractError, match="cross-wired"):
        verify_signed_external_reservation_receipt(
            payload_bytes=tampered_bytes,
            signature_bytes=private_key.sign(tampered_bytes),
            revocation_payload_bytes=revocation_payload,
            revocation_signature_bytes=revocation_signature,
            request=request,
            trust_anchor=trust_anchor,
            now_unix=1_800_000_200,
        )

    with pytest.raises(ExternalReservationContractError, match="signature"):
        verify_signed_external_reservation_receipt(
            payload_bytes=payload,
            signature_bytes=b"0" * 64,
            revocation_payload_bytes=revocation_payload,
            revocation_signature_bytes=revocation_signature,
            request=request,
            trust_anchor=trust_anchor,
            now_unix=1_800_000_200,
        )

    receipt_sha256 = json.loads(payload)["receipt_sha256"]
    decoded_revocation = json.loads(revocation_payload)
    decoded_revocation["revoked_receipt_sha256s"] = [receipt_sha256]
    decoded_revocation.pop("snapshot_sha256")
    decoded_revocation["snapshot_sha256"] = module._sha256(decoded_revocation)
    revoked_payload = module._canonical_bytes(decoded_revocation)
    with pytest.raises(ExternalReservationContractError, match="revoked"):
        verify_signed_external_reservation_receipt(
            payload_bytes=payload,
            signature_bytes=signature,
            revocation_payload_bytes=revoked_payload,
            revocation_signature_bytes=private_key.sign(revoked_payload),
            request=request,
            trust_anchor=trust_anchor,
            now_unix=1_800_000_200,
        )


def test_duplicate_json_keys_fail_closed() -> None:
    request = _request()
    (
        payload,
        signature,
        revocation_payload,
        revocation_signature,
        trust_anchor,
        private_key,
    ) = _signed_receipt(request)
    duplicate = payload[:-1] + b',"provider_id":"duplicate"}'

    with pytest.raises(ExternalReservationContractError, match="duplicate"):
        verify_signed_external_reservation_receipt(
            payload_bytes=duplicate,
            signature_bytes=private_key.sign(duplicate),
            revocation_payload_bytes=revocation_payload,
            revocation_signature_bytes=revocation_signature,
            request=request,
            trust_anchor=trust_anchor,
            now_unix=1_800_000_200,
        )


def test_noncanonical_receipt_and_stale_revocation_snapshot_fail_closed() -> None:
    request = _request()
    (
        payload,
        _signature,
        revocation_payload,
        revocation_signature,
        trust_anchor,
        private_key,
    ) = _signed_receipt(request)
    noncanonical_payload = json.dumps(
        json.loads(payload), indent=2, sort_keys=False
    ).encode("utf-8")

    with pytest.raises(ExternalReservationContractError, match="canonical"):
        verify_signed_external_reservation_receipt(
            payload_bytes=noncanonical_payload,
            signature_bytes=private_key.sign(noncanonical_payload),
            revocation_payload_bytes=revocation_payload,
            revocation_signature_bytes=private_key.sign(revocation_payload),
            request=request,
            trust_anchor=trust_anchor,
            now_unix=1_800_000_200,
        )

    stale_revocation = json.loads(revocation_payload)
    stale_revocation["valid_until_unix"] = 1_800_000_200
    stale_revocation.pop("snapshot_sha256")
    stale_revocation["snapshot_sha256"] = module._sha256(stale_revocation)
    stale_revocation_payload = module._canonical_bytes(stale_revocation)
    with pytest.raises(ExternalReservationContractError, match="lifetime"):
        verify_signed_external_reservation_receipt(
            payload_bytes=payload,
            signature_bytes=private_key.sign(payload),
            revocation_payload_bytes=stale_revocation_payload,
            revocation_signature_bytes=private_key.sign(stale_revocation_payload),
            request=request,
            trust_anchor=trust_anchor,
            now_unix=1_800_000_200,
        )


def test_stale_retention_fails_closed() -> None:
    request = _request()
    (
        payload,
        _signature,
        revocation_payload,
        revocation_signature,
        trust_anchor,
        private_key,
    ) = _signed_receipt(request)
    decoded = json.loads(payload)
    decoded["retention_until_unix"] = decoded["committed_at_unix"] + 10
    decoded.pop("receipt_sha256")
    decoded["receipt_sha256"] = module._sha256(decoded)
    stale = module._canonical_bytes(decoded)
    with pytest.raises(ExternalReservationContractError, match="retention"):
        verify_signed_external_reservation_receipt(
            payload_bytes=stale,
            signature_bytes=private_key.sign(stale),
            revocation_payload_bytes=revocation_payload,
            revocation_signature_bytes=revocation_signature,
            request=request,
            trust_anchor=trust_anchor,
            now_unix=1_800_000_200,
        )


def test_all_downstream_roles_bind_exact_external_identity() -> None:
    request = _request()
    (
        payload,
        signature,
        revocation_payload,
        revocation_signature,
        trust_anchor,
        _private,
    ) = _signed_receipt(request)
    verified = verify_signed_external_reservation_receipt(
        payload_bytes=payload,
        signature_bytes=signature,
        revocation_payload_bytes=revocation_payload,
        revocation_signature_bytes=revocation_signature,
        request=request,
        trust_anchor=trust_anchor,
        now_unix=1_800_000_200,
    )

    for role in module.DOWNSTREAM_ROLES:
        document_sha256 = module._sha256({"role": role})
        binding = build_external_reservation_binding(
            document_role=role,
            document_sha256=document_sha256,
            reservation=verified,
        )
        assert (
            verify_external_reservation_binding(
                binding,
                document_role=role,
                document_sha256=document_sha256,
                reservation=verified,
            )
            == binding["binding_sha256"]
        )
        assert binding["authoritative_for_execution"] is False
        assert binding["lifetime_reservation_key_sha256"] == (
            request.lifetime_reservation_key_sha256
        )
        assert binding["external_reservation_receipt_signature_sha256"] == (
            verified.receipt_signature_sha256
        )
        assert binding["external_revocation_snapshot_sha256"] == (
            verified.revocation_snapshot_sha256
        )


def test_downstream_binding_rejects_public_or_modified_receipt_instances() -> None:
    request = _request()
    (
        payload,
        signature,
        revocation_payload,
        revocation_signature,
        trust_anchor,
        _private,
    ) = _signed_receipt(request)
    verified = verify_signed_external_reservation_receipt(
        payload_bytes=payload,
        signature_bytes=signature,
        revocation_payload_bytes=revocation_payload,
        revocation_signature_bytes=revocation_signature,
        request=request,
        trust_anchor=trust_anchor,
        now_unix=1_800_000_200,
    )

    with pytest.raises(ExternalReservationContractError, match="verifier-constructed"):
        module.VerifiedExternalReservationReceipt(
            provider_id=verified.provider_id,
            reservation_id=verified.reservation_id,
            lifetime_reservation_key_sha256=verified.lifetime_reservation_key_sha256,
            global_reservation_key_sha256=verified.global_reservation_key_sha256,
            request_sha256=verified.request_sha256,
            receipt_sha256=verified.receipt_sha256,
            receipt_signature_sha256=verified.receipt_signature_sha256,
            revocation_snapshot_sha256=verified.revocation_snapshot_sha256,
            committed_at_unix=verified.committed_at_unix,
            retention_until_unix=verified.retention_until_unix,
            author_id=verified.author_id,
            operator_id=verified.operator_id,
            reviewer_id=verified.reviewer_id,
            source_commit_git_sha1=verified.source_commit_git_sha1,
            execution_environment_sha256=verified.execution_environment_sha256,
        )
    with pytest.raises(ExternalReservationContractError, match="verifier-constructed"):
        replace(verified, receipt_sha256="f" * 64)


def test_unconfigured_policy_blocks_before_any_client_call() -> None:
    request = _request()
    (
        payload,
        signature,
        revocation_payload,
        revocation_signature,
        trust_anchor,
        _private,
    ) = _signed_receipt(request)

    class Client:
        provider_id = trust_anchor.provider_id
        production_authority = True
        calls = 0

        def reserve(
            self, canonical_request: bytes
        ) -> tuple[bytes, bytes, bytes, bytes]:
            del canonical_request
            self.calls += 1
            return (
                payload,
                signature,
                revocation_payload,
                revocation_signature,
            )

    client = Client()
    with pytest.raises(
        ExternalReservationContractError,
        match="provider_not_operational",
    ):
        request_external_reservation(
            client=client,
            request=request,
            policy=_policy(),
            trust_anchor=trust_anchor,
        )
    assert client.calls == 0


def test_expired_request_is_rejected_before_the_ledger_call(monkeypatch) -> None:
    request = _request()
    (
        payload,
        signature,
        revocation_payload,
        revocation_signature,
        trust_anchor,
        _private,
    ) = _signed_receipt(request)

    class Client:
        provider_id = trust_anchor.provider_id
        production_authority = True
        reserve_calls = 0
        lookup_calls = 0

        def reserve(self, canonical_request: bytes):
            del canonical_request
            self.reserve_calls += 1
            return payload, signature, revocation_payload, revocation_signature

        def lookup(self, canonical_request: bytes):
            del canonical_request
            self.lookup_calls += 1
            return None

    client = Client()
    monkeypatch.setattr(module, "verify_external_reservation_policy", lambda _: "test")
    monkeypatch.setattr(module.time, "time", lambda: request.expires_at_unix)
    with pytest.raises(ExternalReservationContractError, match="active window"):
        request_external_reservation(
            client=client,
            request=request,
            policy=_operational_policy(trust_anchor),
            trust_anchor=trust_anchor,
        )
    assert client.reserve_calls == 0
    assert client.lookup_calls == 0


def test_ambiguous_commit_recovers_the_exact_signed_receipt(monkeypatch) -> None:
    request = _request()
    signed = _signed_receipt(request)
    payload, signature, revocation_payload, revocation_signature, trust_anchor, _ = signed
    expected_request = module._canonical_bytes(request.to_dict())

    class Client:
        provider_id = trust_anchor.provider_id
        production_authority = True
        reserve_calls = 0
        lookup_calls = 0

        def reserve(self, canonical_request: bytes):
            assert canonical_request == expected_request
            self.reserve_calls += 1
            raise ConnectionError("response lost after immutable commit")

        def lookup(self, canonical_request: bytes):
            assert canonical_request == expected_request
            self.lookup_calls += 1
            return payload, signature, revocation_payload, revocation_signature

    client = Client()
    monkeypatch.setattr(module, "verify_external_reservation_policy", lambda _: "test")
    monkeypatch.setattr(module.time, "time", lambda: 1_800_000_200)
    verified = request_external_reservation(
        client=client,
        request=request,
        policy=_operational_policy(trust_anchor),
        trust_anchor=trust_anchor,
    )

    assert client.reserve_calls == 1
    assert client.lookup_calls == 1
    assert verified.receipt_sha256 == json.loads(payload)["receipt_sha256"]


def test_production_client_requires_ambiguous_commit_recovery(monkeypatch) -> None:
    request = _request()
    (
        payload,
        signature,
        revocation_payload,
        revocation_signature,
        trust_anchor,
        _private,
    ) = _signed_receipt(request)

    class Client:
        provider_id = trust_anchor.provider_id
        production_authority = True
        calls = 0

        def reserve(self, canonical_request: bytes):
            del canonical_request
            self.calls += 1
            return payload, signature, revocation_payload, revocation_signature

    client = Client()
    monkeypatch.setattr(module, "verify_external_reservation_policy", lambda _: "test")
    with pytest.raises(ExternalReservationContractError, match="receipt recovery"):
        request_external_reservation(
            client=client,
            request=request,
            policy=_operational_policy(trust_anchor),
            trust_anchor=trust_anchor,
        )
    assert client.calls == 0


def test_test_double_cannot_acquire_authority_even_with_operational_shape() -> None:
    request = _request()
    (
        payload,
        signature,
        revocation_payload,
        revocation_signature,
        trust_anchor,
        _private,
    ) = _signed_receipt(request)
    policy = copy.deepcopy(_policy())
    policy["provider"] = {
        "provider_id": trust_anchor.provider_id,
        "endpoint": "https://reviewed.example.invalid",
        "trust_anchor_public_key_hex": trust_anchor.public_key_raw.hex(),
        "append_only_immutable_required": True,
        "network_round_trip_required": True,
        "mutual_tls_required": True,
        "server_timestamp_required": True,
        "receipt_signature_algorithm": "ed25519",
        "canonical_signed_payload_required": True,
        "policy_bound_trust_anchor_required": True,
        "signed_revocation_snapshot_required": True,
        "provider_operational": True,
    }
    policy["authority"]["historical_execution_operational"] = True

    class Client:
        provider_id = trust_anchor.provider_id
        production_authority = False

        def reserve(
            self, canonical_request: bytes
        ) -> tuple[bytes, bytes, bytes, bytes]:
            del canonical_request
            return (
                payload,
                signature,
                revocation_payload,
                revocation_signature,
            )

    monkey_policy_verifier = module.verify_external_reservation_policy
    try:
        module.verify_external_reservation_policy = lambda _policy: "test"
        with pytest.raises(
            ExternalReservationContractError,
            match="test doubles",
        ):
            request_external_reservation(
                client=Client(),
                request=request,
                policy=policy,
                trust_anchor=trust_anchor,
            )
    finally:
        module.verify_external_reservation_policy = monkey_policy_verifier


def test_operational_shape_rejects_policy_trust_anchor_substitution() -> None:
    request = _request()
    (
        payload,
        signature,
        revocation_payload,
        revocation_signature,
        trust_anchor,
        _private,
    ) = _signed_receipt(request)
    substituted_private_key = Ed25519PrivateKey.generate()
    substituted_anchor = ExternalLedgerTrustAnchor(
        provider_id=trust_anchor.provider_id,
        public_key_raw=substituted_private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ),
    )
    policy = copy.deepcopy(_policy())
    policy["provider"] = {
        **policy["provider"],
        "provider_id": trust_anchor.provider_id,
        "endpoint": "https://reviewed.example.invalid",
        "trust_anchor_public_key_hex": trust_anchor.public_key_raw.hex(),
        "provider_operational": True,
    }
    policy["authority"]["historical_execution_operational"] = True

    class Client:
        provider_id = trust_anchor.provider_id
        production_authority = True
        calls = 0

        def reserve(
            self, canonical_request: bytes
        ) -> tuple[bytes, bytes, bytes, bytes]:
            del canonical_request
            self.calls += 1
            return (
                payload,
                signature,
                revocation_payload,
                revocation_signature,
            )

    client = Client()
    monkey_policy_verifier = module.verify_external_reservation_policy
    try:
        module.verify_external_reservation_policy = lambda _policy: "test"
        with pytest.raises(
            ExternalReservationContractError,
            match="trust anchor",
        ):
            request_external_reservation(
                client=client,
                request=request,
                policy=policy,
                trust_anchor=substituted_anchor,
            )
    finally:
        module.verify_external_reservation_policy = monkey_policy_verifier
    assert client.calls == 0
