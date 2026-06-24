from __future__ import annotations

import copy

import pytest

from betelgeuze_product.payload_privacy import open_private_payload, seal_private_payload


SIGNING_KEY = "test-private-payload-key"
BASE_NOW = 1_700_000_000.0


def test_private_payload_round_trip_preserves_nested_content() -> None:
    payload = {
        "target_name": "ADRB2",
        "runner_profile_params": {
            "ligands": ["CCO", "CCN"],
            "metadata": {"ligand_smiles": "CCN", "nested": {"count": 2}},
        },
    }

    envelope = seal_private_payload(
        payload,
        signing_key=SIGNING_KEY,
        ttl_seconds=300,
        now=BASE_NOW,
    )
    recovered = open_private_payload(envelope, signing_key=SIGNING_KEY, now=BASE_NOW)

    assert recovered == payload
    assert recovered is not payload
    assert recovered["runner_profile_params"]["metadata"]["nested"]["count"] == 2


def test_private_payload_rejects_tampered_payload() -> None:
    envelope = seal_private_payload(
        {"secret": "value"},
        signing_key=SIGNING_KEY,
        ttl_seconds=300,
        now=BASE_NOW,
    )
    tampered = copy.deepcopy(envelope)
    tampered["payload"]["secret"] = "changed"

    with pytest.raises(ValueError, match="private_payload_tampered"):
        open_private_payload(tampered, signing_key=SIGNING_KEY, now=BASE_NOW)


def test_private_payload_rejects_tampered_signature() -> None:
    envelope = seal_private_payload(
        {"secret": "value"},
        signing_key=SIGNING_KEY,
        ttl_seconds=300,
        now=BASE_NOW,
    )
    tampered = copy.deepcopy(envelope)
    tampered["signature"] = "0" * 64

    with pytest.raises(ValueError, match="private_payload_tampered"):
        open_private_payload(tampered, signing_key=SIGNING_KEY, now=BASE_NOW)


def test_private_payload_rejects_wrong_signing_key() -> None:
    envelope = seal_private_payload(
        {"secret": "value"},
        signing_key=SIGNING_KEY,
        ttl_seconds=300,
        now=BASE_NOW,
    )

    with pytest.raises(ValueError, match="private_payload_tampered"):
        open_private_payload(envelope, signing_key="other-key", now=BASE_NOW)


def test_private_payload_rejects_expired_envelope() -> None:
    envelope = seal_private_payload(
        {"secret": "value"},
        signing_key=SIGNING_KEY,
        ttl_seconds=60,
        now=BASE_NOW,
    )

    with pytest.raises(ValueError, match="private_payload_expired"):
        open_private_payload(envelope, signing_key=SIGNING_KEY, now=BASE_NOW + 61)
