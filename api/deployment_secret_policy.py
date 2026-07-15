"""Stdlib-only rejection policy for committed deployment placeholders."""

from __future__ import annotations

import base64
import binascii
import re
from typing import Any


INSECURE_PRODUCT_API_TOKENS = frozenset(
    {
        "replace-with-operator-managed-admin-token",
        "replace-with-operator-managed-token",
    }
)
INSECURE_RESULT_MANIFEST_SIGNING_KEYS = frozenset(
    {
        "local-dev-result-manifest-signing-key-change-me",
        "tier-alpha-local-smoke-signing-key",
        "replace-with-operator-managed-secret",
        "replace-with-operator-managed-signing-key",
    }
)
INSECURE_RESULT_MANIFEST_KEY_IDS = frozenset(
    {
        "",
        "dev",
        "default",
        "local",
        "local-dev",
        "product-k8s-local",
        "product-local",
        "product-local-tier-alpha",
        "site-local-v1",
        "tier-alpha-local",
    }
)
INSECURE_PRIVATE_PAYLOAD_KEY_IDS = frozenset(
    {
        "default",
        "dev",
        "local",
        "local-dev",
        "product-local",
        "replace-with-operator-managed-key-id",
        "site-local-v1",
        "test",
    }
)
INSECURE_PRIVATE_PAYLOAD_SECRETS = frozenset(
    {
        b"replace-with-operator-managed-private-payload-key",
        b"replace-with-operator-managed-secret",
        b"unit-test-private-payload-key",
    }
)

_KEY_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


def product_api_token_is_operator_managed(value: Any) -> bool:
    return bool(
        type(value) is str
        and len(value.encode("utf-8")) >= 32
        and value not in INSECURE_PRODUCT_API_TOKENS
    )


def result_manifest_signing_key_is_operator_managed(value: Any) -> bool:
    return bool(
        type(value) is str
        and len(value.encode("utf-8")) >= 32
        and value not in INSECURE_RESULT_MANIFEST_SIGNING_KEYS
    )


def result_manifest_key_id_is_operator_managed(value: Any) -> bool:
    return bool(
        type(value) is str
        and _KEY_ID_RE.fullmatch(value) is not None
        and value not in INSECURE_RESULT_MANIFEST_KEY_IDS
    )


def docking_private_payload_keys_are_operator_managed(value: Any) -> bool:
    """Validate the complete rotation keyring used for customer payloads.

    The runtime parser accepts 16-byte secrets for backwards-compatible local
    stores. Product API startup applies the stricter deployment boundary here:
    every configured key must have a non-placeholder identifier and at least
    32 bytes of base64-decoded key material.
    """

    if type(value) is not str:
        return False

    seen_key_ids: set[str] = set()
    entries = [entry.strip() for entry in value.split(",") if entry.strip()]
    if not entries:
        return False

    for entry in entries:
        if ":" not in entry:
            return False
        key_id, _, encoded_secret = entry.partition(":")
        key_id = key_id.strip()
        encoded_secret = encoded_secret.strip()
        if (
            _KEY_ID_RE.fullmatch(key_id) is None
            or key_id in INSECURE_PRIVATE_PAYLOAD_KEY_IDS
            or key_id in seen_key_ids
        ):
            return False
        try:
            secret = base64.b64decode(encoded_secret.encode("ascii"), validate=True)
        except (UnicodeEncodeError, binascii.Error, ValueError):
            return False
        if len(secret) < 32 or secret in INSECURE_PRIVATE_PAYLOAD_SECRETS:
            return False
        seen_key_ids.add(key_id)

    return True
