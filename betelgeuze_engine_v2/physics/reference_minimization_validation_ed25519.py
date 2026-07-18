"""Deferred Ed25519 signing and public-key verification helpers.

The module keeps the optional cryptography import inside the operations so the
stdlib-only validation bootstrap can verify its first trust boundary before the
Engine v2 package is imported. Private keys are raw 32-byte Ed25519 seeds;
verifiers receive only raw 32-byte public keys.
"""

from __future__ import annotations

ED25519_PRIVATE_KEY_BYTES = 32
ED25519_PUBLIC_KEY_BYTES = 32
ED25519_SIGNATURE_BYTES = 64


class ReferenceMinimizationValidationEd25519Error(ValueError):
    """An Ed25519 key, signature, or backend is invalid."""


def _require_bytes(value: object, *, length: int, name: str) -> bytes:
    if not isinstance(value, bytes) or len(value) != length:
        raise ReferenceMinimizationValidationEd25519Error(
            f"{name} must contain exactly {length} bytes"
        )
    return value


def _backend() -> tuple[object, object, type[Exception]]:
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
            Ed25519PublicKey,
        )
    except ImportError as exc:
        raise ReferenceMinimizationValidationEd25519Error(
            "the pinned cryptography Ed25519 backend is unavailable"
        ) from exc
    return Ed25519PrivateKey, Ed25519PublicKey, InvalidSignature


def ed25519_public_key_bytes(private_key: bytes) -> bytes:
    """Derive the raw public key for provisioning a verifier trust store."""

    private = _require_bytes(
        private_key, length=ED25519_PRIVATE_KEY_BYTES, name="Ed25519 private key"
    )
    private_type, _, _ = _backend()
    try:
        key = private_type.from_private_bytes(private)  # type: ignore[attr-defined]
        return key.public_key().public_bytes_raw()
    except (TypeError, ValueError) as exc:
        raise ReferenceMinimizationValidationEd25519Error(
            "Ed25519 private key is invalid"
        ) from exc


def sign_ed25519(message: bytes, private_key: bytes) -> str:
    """Return a lowercase hexadecimal Ed25519 signature."""

    if not isinstance(message, bytes):
        raise ReferenceMinimizationValidationEd25519Error(
            "Ed25519 message must be bytes"
        )
    private = _require_bytes(
        private_key, length=ED25519_PRIVATE_KEY_BYTES, name="Ed25519 private key"
    )
    private_type, _, _ = _backend()
    try:
        signature = private_type.from_private_bytes(private).sign(message)  # type: ignore[attr-defined]
    except (TypeError, ValueError) as exc:
        raise ReferenceMinimizationValidationEd25519Error(
            "Ed25519 signing failed"
        ) from exc
    return _require_bytes(
        signature, length=ED25519_SIGNATURE_BYTES, name="Ed25519 signature"
    ).hex()


def verify_ed25519(message: bytes, signature_hex: object, public_key: bytes) -> bool:
    """Verify one signature with a public key; never accepts signing material."""

    if not isinstance(message, bytes):
        raise ReferenceMinimizationValidationEd25519Error(
            "Ed25519 message must be bytes"
        )
    public = _require_bytes(
        public_key, length=ED25519_PUBLIC_KEY_BYTES, name="Ed25519 public key"
    )
    if (
        not isinstance(signature_hex, str)
        or len(signature_hex) != ED25519_SIGNATURE_BYTES * 2
        or any(character not in "0123456789abcdef" for character in signature_hex)
    ):
        return False
    _, public_type, invalid_signature = _backend()
    try:
        public_type.from_public_bytes(public).verify(  # type: ignore[attr-defined]
            bytes.fromhex(signature_hex), message
        )
    except (invalid_signature, TypeError, ValueError):
        return False
    return True


__all__ = [
    "ED25519_PRIVATE_KEY_BYTES",
    "ED25519_PUBLIC_KEY_BYTES",
    "ED25519_SIGNATURE_BYTES",
    "ReferenceMinimizationValidationEd25519Error",
    "ed25519_public_key_bytes",
    "sign_ed25519",
    "verify_ed25519",
]
