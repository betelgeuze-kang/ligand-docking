"""Encrypted at-rest store for raw customer docking inputs.

This module keeps the *original* customer request (raw SMILES, PDB, SDF, etc.)
out of the public job ledger and SQLite queue by persisting it as an encrypted,
authenticated envelope on disk. It complements
``betelgeuze_product.payload_privacy``:

- ``payload_privacy.sanitize_request_for_ledger`` redacts sensitive fields from
  anything that is written to the *public* ledger / API responses.
- ``payload_privacy.seal_private_payload`` provides an HMAC *integrity* envelope
  (it signs, it does not encrypt).
- ``EncryptedPrivatePayloadStore`` (this module) provides *confidentiality at
  rest*: the customer payload is encrypted before it touches the filesystem and
  is bound to the originating ``job_id`` and canonical request hash.

Cipher construction (``PRIVATE_PAYLOAD_CIPHER``)
------------------------------------------------
The deployment target for the web-safe lane has no third-party crypto library
available (``cryptography`` / Fernet are not installed and cannot be fetched in
the restricted network mode), and the rest of this package is deliberately
stdlib-only. We therefore use a standard, auditable construction built entirely
on ``hashlib`` / ``hmac``:

1. Per-record 16-byte random ``nonce``.
2. HKDF-SHA256 (RFC 5869) derives independent ``enc``/``mac`` subkeys from the
   configured key secret and the nonce.
3. A CTR-mode keystream is produced by HMAC-SHA256 used as a PRF and XOR'd with
   the plaintext.
4. Encrypt-then-MAC: an HMAC-SHA256 tag authenticates the canonical header
   (version, cipher, key id, nonce, issued/expires, ``job_id``,
   ``request_sha256``) together with the ciphertext.

The ``version``/``cipher`` fields are persisted in every envelope so an AEAD
backend (e.g. AES-GCM / Fernet) can be added later without breaking stored
records. Do **not** weaken the "encrypt-then-MAC + unique nonce" invariants.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

PRIVATE_PAYLOAD_STORE_VERSION = "private_payload_store_v1"
PRIVATE_PAYLOAD_CIPHER = "hmac-sha256-ctr-encrypt-then-mac"

_NONCE_BYTES = 16
_HKDF_ENC_INFO = b"betelgeuze-private-payload-enc-v1"
_HKDF_MAC_INFO = b"betelgeuze-private-payload-mac-v1"
_MAC_DOMAIN_SEPARATOR = b"\x00betelgeuze-private-payload-aead\x00"

_FILE_MODE = 0o600
_DIR_MODE = 0o700

# Error codes are stable strings so callers/tests can match on category without
# depending on prose wording.
ERR_NO_KEYS = "private_payload_store_no_keys"
ERR_UNKNOWN_KEY = "private_payload_store_unknown_key"
ERR_TAMPERED = "private_payload_store_tampered"
ERR_EXPIRED = "private_payload_store_expired"
ERR_JOB_ID_MISMATCH = "private_payload_store_job_id_mismatch"
ERR_REQUEST_MISMATCH = "private_payload_store_request_mismatch"
ERR_MISSING = "private_payload_store_missing"
ERR_MALFORMED = "private_payload_store_malformed"


class PrivatePayloadStoreError(ValueError):
    """Base error for the encrypted private payload store.

    Carries a stable ``code`` (one of the ``ERR_*`` constants) in addition to a
    human readable message so callers can branch on category.
    """

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(message or code)


def canonical_request_sha256(request: Any) -> str:
    """Return the canonical SHA-256 of a request object.

    Uses sorted-key, separator-stable JSON so the same logical request always
    hashes identically regardless of dict ordering.
    """

    canonical = json.dumps(request, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _hkdf_sha256(secret: bytes, salt: bytes, info: bytes, length: int) -> bytes:
    prk = hmac.new(salt, secret, hashlib.sha256).digest()
    okm = b""
    block = b""
    counter = 1
    while len(okm) < length:
        block = hmac.new(prk, block + info + bytes([counter]), hashlib.sha256).digest()
        okm += block
        counter += 1
    return okm[:length]


def _keystream(enc_key: bytes, nonce: bytes, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        out += hmac.new(enc_key, nonce + counter.to_bytes(8, "big"), hashlib.sha256).digest()
        counter += 1
    return bytes(out[:length])


def _xor(data: bytes, keystream: bytes) -> bytes:
    return bytes(b ^ k for b, k in zip(data, keystream))


def _b64encode(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _b64decode(value: str) -> bytes:
    try:
        return base64.b64decode(value.encode("ascii"), validate=True)
    except (ValueError, TypeError) as exc:  # pragma: no cover - defensive
        raise PrivatePayloadStoreError(ERR_MALFORMED, "invalid base64 field") from exc


@dataclass(frozen=True)
class PrivatePayloadKey:
    """A single named key secret."""

    key_id: str
    secret: bytes

    def __post_init__(self) -> None:
        if not self.key_id:
            raise PrivatePayloadStoreError(ERR_MALFORMED, "key_id must be non-empty")
        if len(self.secret) < 16:
            raise PrivatePayloadStoreError(ERR_MALFORMED, "key secret must be >= 16 bytes")


class PrivatePayloadKeyring:
    """Ordered set of keys supporting rotation.

    The first key is the *primary* used for new encryptions. All keys are
    available for decryption, so rotating in a new primary key still allows
    reading records sealed under older keys.
    """

    def __init__(self, keys: Iterable[PrivatePayloadKey]):
        ordered = list(keys)
        self._by_id: dict[str, PrivatePayloadKey] = {}
        for key in ordered:
            if key.key_id in self._by_id:
                raise PrivatePayloadStoreError(ERR_MALFORMED, f"duplicate key_id: {key.key_id}")
            self._by_id[key.key_id] = key
        self._ordered = ordered

    def __len__(self) -> int:
        return len(self._ordered)

    @property
    def primary(self) -> PrivatePayloadKey:
        if not self._ordered:
            raise PrivatePayloadStoreError(ERR_NO_KEYS, "keyring has no keys")
        return self._ordered[0]

    def get(self, key_id: str) -> PrivatePayloadKey:
        key = self._by_id.get(key_id)
        if key is None:
            raise PrivatePayloadStoreError(ERR_UNKNOWN_KEY, f"unknown key_id: {key_id}")
        return key

    @classmethod
    def from_config(cls, value: str) -> "PrivatePayloadKeyring":
        """Parse ``"key_id:base64secret,key_id2:base64secret2"``.

        Whitespace around entries is ignored. The first entry is the primary.
        """

        keys: list[PrivatePayloadKey] = []
        for raw_entry in (value or "").split(","):
            entry = raw_entry.strip()
            if not entry:
                continue
            if ":" not in entry:
                raise PrivatePayloadStoreError(ERR_MALFORMED, "key entry must be 'key_id:base64secret'")
            key_id, _, b64secret = entry.partition(":")
            keys.append(
                PrivatePayloadKey(key_id=key_id.strip(), secret=_b64decode(b64secret.strip()))
            )
        if not keys:
            raise PrivatePayloadStoreError(ERR_NO_KEYS, "no keys configured")
        return cls(keys)

    @staticmethod
    def generate_secret_b64(num_bytes: int = 32) -> str:
        """Helper for operators/tests to mint a fresh base64 key secret."""

        return _b64encode(secrets.token_bytes(num_bytes))


def _now(now: float | None) -> float:
    return float(time.time() if now is None else now)


def _header(
    *,
    key_id: str,
    nonce_b64: str,
    issued_at: float,
    expires_at: float,
    job_id: str,
    request_sha256: str,
) -> dict[str, Any]:
    return {
        "version": PRIVATE_PAYLOAD_STORE_VERSION,
        "cipher": PRIVATE_PAYLOAD_CIPHER,
        "key_id": key_id,
        "nonce": nonce_b64,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "job_id": job_id,
        "request_sha256": request_sha256,
    }


def _aad(header: dict[str, Any]) -> bytes:
    return json.dumps(header, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _compute_tag(mac_key: bytes, header: dict[str, Any], ciphertext: bytes) -> bytes:
    mac = hmac.new(mac_key, _MAC_DOMAIN_SEPARATOR, hashlib.sha256)
    mac.update(_aad(header))
    mac.update(b".")
    mac.update(ciphertext)
    return mac.digest()


def seal_encrypted_payload(
    payload: dict[str, Any],
    *,
    keyring: PrivatePayloadKeyring,
    job_id: str,
    request_sha256: str,
    ttl_seconds: float,
    now: float | None = None,
) -> dict[str, Any]:
    """Encrypt ``payload`` into a self-describing envelope dict.

    The envelope is bound to ``job_id`` and ``request_sha256`` (both
    authenticated) and expires after ``ttl_seconds``.
    """

    if ttl_seconds <= 0:
        raise PrivatePayloadStoreError(ERR_MALFORMED, "ttl_seconds must be positive")
    key = keyring.primary
    nonce = secrets.token_bytes(_NONCE_BYTES)
    nonce_b64 = _b64encode(nonce)
    issued_at = _now(now)
    expires_at = issued_at + float(ttl_seconds)
    header = _header(
        key_id=key.key_id,
        nonce_b64=nonce_b64,
        issued_at=issued_at,
        expires_at=expires_at,
        job_id=job_id,
        request_sha256=request_sha256,
    )
    enc_key = _hkdf_sha256(key.secret, nonce, _HKDF_ENC_INFO, 32)
    mac_key = _hkdf_sha256(key.secret, nonce, _HKDF_MAC_INFO, 32)
    plaintext = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )
    ciphertext = _xor(plaintext, _keystream(enc_key, nonce, len(plaintext)))
    tag = _compute_tag(mac_key, header, ciphertext)
    envelope = dict(header)
    envelope["ciphertext"] = _b64encode(ciphertext)
    envelope["tag"] = _b64encode(tag)
    return envelope


def open_encrypted_payload(
    envelope: dict[str, Any],
    *,
    keyring: PrivatePayloadKeyring,
    job_id: str,
    request_sha256: str,
    now: float | None = None,
) -> dict[str, Any]:
    """Authenticate, decrypt, and verify binding of an envelope.

    Raises :class:`PrivatePayloadStoreError` (with a stable ``code``) on any
    integrity, expiry, key, or binding failure.
    """

    if not isinstance(envelope, dict):
        raise PrivatePayloadStoreError(ERR_MALFORMED, "envelope must be a dict")
    try:
        header = _header(
            key_id=str(envelope["key_id"]),
            nonce_b64=str(envelope["nonce"]),
            issued_at=float(envelope["issued_at"]),
            expires_at=float(envelope["expires_at"]),
            job_id=str(envelope["job_id"]),
            request_sha256=str(envelope["request_sha256"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise PrivatePayloadStoreError(ERR_MALFORMED, "envelope missing required fields") from exc

    if envelope.get("version") != PRIVATE_PAYLOAD_STORE_VERSION:
        raise PrivatePayloadStoreError(ERR_MALFORMED, "unsupported envelope version")
    if envelope.get("cipher") != PRIVATE_PAYLOAD_CIPHER:
        raise PrivatePayloadStoreError(ERR_MALFORMED, "unsupported cipher")

    key = keyring.get(header["key_id"])
    nonce = _b64decode(header["nonce"])
    ciphertext = _b64decode(str(envelope.get("ciphertext", "")))
    observed_tag = _b64decode(str(envelope.get("tag", "")))

    mac_key = _hkdf_sha256(key.secret, nonce, _HKDF_MAC_INFO, 32)
    expected_tag = _compute_tag(mac_key, header, ciphertext)
    if not hmac.compare_digest(observed_tag, expected_tag):
        raise PrivatePayloadStoreError(ERR_TAMPERED, "authentication tag mismatch")

    # Binding + expiry checks only after authentication succeeds.
    if header["job_id"] != job_id:
        raise PrivatePayloadStoreError(ERR_JOB_ID_MISMATCH, "job_id does not match envelope")
    if header["request_sha256"] != request_sha256:
        raise PrivatePayloadStoreError(ERR_REQUEST_MISMATCH, "request hash does not match envelope")
    if _now(now) > header["expires_at"]:
        raise PrivatePayloadStoreError(ERR_EXPIRED, "payload envelope expired")

    enc_key = _hkdf_sha256(key.secret, nonce, _HKDF_ENC_INFO, 32)
    plaintext = _xor(ciphertext, _keystream(enc_key, nonce, len(ciphertext)))
    try:
        recovered = json.loads(plaintext.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:  # pragma: no cover - defensive
        raise PrivatePayloadStoreError(ERR_MALFORMED, "decrypted payload is not valid JSON") from exc
    if not isinstance(recovered, dict):
        raise PrivatePayloadStoreError(ERR_MALFORMED, "decrypted payload is not an object")
    return recovered


def _ref_for_job(job_id: str) -> str:
    """Stable, path-safe storage reference for a job id."""

    return hashlib.sha256(job_id.encode("utf-8")).hexdigest()


class EncryptedPrivatePayloadStore:
    """Filesystem-backed encrypted store for raw customer payloads."""

    def __init__(
        self,
        root_dir: str | Path,
        *,
        keyring: PrivatePayloadKeyring,
        ttl_seconds: float,
        now: float | None = None,
    ):
        if len(keyring) == 0:
            raise PrivatePayloadStoreError(ERR_NO_KEYS, "store requires at least one key")
        if ttl_seconds <= 0:
            raise PrivatePayloadStoreError(ERR_MALFORMED, "ttl_seconds must be positive")
        self.root_dir = Path(root_dir)
        self.keyring = keyring
        self.ttl_seconds = float(ttl_seconds)
        self._fixed_now = now
        self.root_dir.mkdir(parents=True, exist_ok=True)
        # Tighten directory permissions even if it already existed.
        try:
            os.chmod(self.root_dir, _DIR_MODE)
        except OSError:  # pragma: no cover - platform dependent
            pass

    def _path_for_ref(self, ref: str) -> Path:
        return self.root_dir / f"{ref}.payload.json"

    def put(self, job_id: str, request_sha256: str, payload: dict[str, Any]) -> str:
        """Encrypt and persist ``payload``; returns the storage reference."""

        if not job_id:
            raise PrivatePayloadStoreError(ERR_MALFORMED, "job_id must be non-empty")
        envelope = seal_encrypted_payload(
            payload,
            keyring=self.keyring,
            job_id=job_id,
            request_sha256=request_sha256,
            ttl_seconds=self.ttl_seconds,
            now=self._fixed_now,
        )
        ref = _ref_for_job(job_id)
        target = self._path_for_ref(ref)
        serialized = json.dumps(envelope, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        self._atomic_write(target, serialized)
        return ref

    def _atomic_write(self, target: Path, serialized: str) -> None:
        tmp = target.with_suffix(target.suffix + f".tmp-{secrets.token_hex(8)}")
        # Open with restrictive permissions from the start.
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, _FILE_MODE)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(serialized)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(tmp, _FILE_MODE)
            os.replace(tmp, target)
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:  # pragma: no cover - defensive
                    pass

    def get(self, ref: str, *, job_id: str, request_sha256: str) -> dict[str, Any]:
        """Load, authenticate, decrypt, and verify a stored payload."""

        target = self._path_for_ref(ref)
        if not target.exists():
            raise PrivatePayloadStoreError(ERR_MISSING, f"no stored payload for ref: {ref}")
        try:
            envelope = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PrivatePayloadStoreError(ERR_MALFORMED, "stored envelope is unreadable") from exc
        return open_encrypted_payload(
            envelope,
            keyring=self.keyring,
            job_id=job_id,
            request_sha256=request_sha256,
            now=self._fixed_now,
        )

    def ref_for_job(self, job_id: str) -> str:
        return _ref_for_job(job_id)

    def delete(self, ref: str) -> bool:
        target = self._path_for_ref(ref)
        try:
            target.unlink()
            return True
        except FileNotFoundError:
            return False


__all__ = [
    "PRIVATE_PAYLOAD_STORE_VERSION",
    "PRIVATE_PAYLOAD_CIPHER",
    "PrivatePayloadStoreError",
    "PrivatePayloadKey",
    "PrivatePayloadKeyring",
    "EncryptedPrivatePayloadStore",
    "canonical_request_sha256",
    "seal_encrypted_payload",
    "open_encrypted_payload",
    "ERR_NO_KEYS",
    "ERR_UNKNOWN_KEY",
    "ERR_TAMPERED",
    "ERR_EXPIRED",
    "ERR_JOB_ID_MISMATCH",
    "ERR_REQUEST_MISMATCH",
    "ERR_MISSING",
    "ERR_MALFORMED",
]
