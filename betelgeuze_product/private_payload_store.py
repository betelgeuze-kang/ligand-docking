from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from betelgeuze_product.atomic_io import atomic_write_bytes

PRIVATE_PAYLOAD_SCHEMA_VERSION = "docking_private_payload_v1"
_REFERENCE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{20,128}$")


class PrivatePayloadError(RuntimeError):
    pass


class PrivatePayloadConfigurationError(PrivatePayloadError):
    pass


class PrivatePayloadNotFoundError(PrivatePayloadError):
    pass


class PrivatePayloadIntegrityError(PrivatePayloadError):
    pass


class PrivatePayloadExpiredError(PrivatePayloadError):
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _format_utc(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def _parse_utc(value: Any) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise PrivatePayloadIntegrityError("private payload timestamp is missing")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PrivatePayloadIntegrityError("private payload timestamp is invalid") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def payload_sha256(payload: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def _configured_keys(value: str) -> list[str]:
    return [
        item.strip()
        for item in str(value or "").replace(";", ",").split(",")
        if item.strip()
    ]


class PrivatePayloadStore:
    """Encrypted, content-verified store for customer docking input payloads.

    Public job ledgers carry only the opaque reference and cryptographic hashes.
    The original structure and ligand sources are encrypted with Fernet and are
    materialized only inside the validated runner boundary.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        fernet_keys: list[str],
        key_id: str,
        ttl_seconds: int,
    ) -> None:
        if not fernet_keys:
            raise PrivatePayloadConfigurationError(
                "DOCKING_PRIVATE_PAYLOAD_FERNET_KEYS must contain at least one key"
            )
        if int(ttl_seconds) <= 0:
            raise PrivatePayloadConfigurationError("private payload TTL must be positive")
        try:
            from cryptography.fernet import Fernet, MultiFernet

            fernets = [Fernet(key.encode("ascii")) for key in fernet_keys]
        except ImportError as exc:
            raise PrivatePayloadConfigurationError(
                "cryptography is required for the encrypted private payload store"
            ) from exc
        except (TypeError, ValueError) as exc:
            raise PrivatePayloadConfigurationError(
                "DOCKING_PRIVATE_PAYLOAD_FERNET_KEYS contains an invalid Fernet key"
            ) from exc

        self.root = Path(root).expanduser()
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            self.root.chmod(0o700)
        except OSError:
            pass
        self.key_id = str(key_id or "private-payload-key").strip()
        self.ttl_seconds = int(ttl_seconds)
        self._fernet = MultiFernet(fernets)

    @classmethod
    def from_settings(cls, settings: Any) -> "PrivatePayloadStore":
        return cls(
            getattr(settings, "docking_private_payload_store_path"),
            fernet_keys=_configured_keys(
                getattr(settings, "docking_private_payload_fernet_keys", "")
            ),
            key_id=str(
                getattr(settings, "docking_private_payload_key_id", "")
                or "private-payload-key"
            ),
            ttl_seconds=int(
                getattr(settings, "docking_private_payload_ttl_seconds", 604800)
            ),
        )

    def _path_for_reference(self, reference: str) -> Path:
        ref = str(reference or "").strip()
        if not _REFERENCE_PATTERN.fullmatch(ref):
            raise PrivatePayloadIntegrityError("private payload reference is invalid")
        return self.root / ref[:2] / f"{ref}.fernet"

    def put(
        self,
        *,
        job_id: str,
        payload: dict[str, Any],
        expected_request_sha256: str = "",
    ) -> dict[str, Any]:
        resolved_job_id = str(job_id or "").strip()
        if not resolved_job_id:
            raise PrivatePayloadIntegrityError("private payload job_id is required")
        if not isinstance(payload, dict):
            raise PrivatePayloadIntegrityError("private payload must be a JSON object")

        digest = payload_sha256(payload)
        expected = str(expected_request_sha256 or "").strip()
        if expected and not hmac.compare_digest(digest, expected):
            raise PrivatePayloadIntegrityError(
                "private payload request SHA256 does not match the public job record"
            )

        created_at = _utc_now()
        expires_at = created_at + timedelta(seconds=self.ttl_seconds)
        envelope = {
            "schema_version": PRIVATE_PAYLOAD_SCHEMA_VERSION,
            "job_id": resolved_job_id,
            "request_sha256": digest,
            "created_at_utc": _format_utc(created_at),
            "expires_at_utc": _format_utc(expires_at),
            "key_id": self.key_id,
            "payload": payload,
        }
        ciphertext = self._fernet.encrypt(_canonical_json_bytes(envelope))
        reference = secrets.token_urlsafe(32).rstrip("=")
        path = self._path_for_reference(reference)
        atomic_write_bytes(path, ciphertext + b"\n", mode=0o600)
        return {
            "private_payload_schema_version": PRIVATE_PAYLOAD_SCHEMA_VERSION,
            "private_payload_ref": reference,
            "private_payload_request_sha256": digest,
            "private_payload_ciphertext_sha256": hashlib.sha256(ciphertext).hexdigest(),
            "private_payload_key_id": self.key_id,
            "private_payload_created_at_utc": _format_utc(created_at),
            "private_payload_expires_at_utc": _format_utc(expires_at),
            "private_payload_store_ready": True,
        }

    def get(
        self,
        reference: str,
        *,
        expected_job_id: str = "",
        expected_request_sha256: str = "",
        allow_expired: bool = False,
    ) -> dict[str, Any]:
        path = self._path_for_reference(reference)
        if not path.is_file():
            raise PrivatePayloadNotFoundError("private payload reference was not found")
        try:
            ciphertext = path.read_bytes().strip()
        except OSError as exc:
            raise PrivatePayloadNotFoundError("private payload could not be read") from exc

        try:
            from cryptography.fernet import InvalidToken

            plaintext = self._fernet.decrypt(ciphertext)
        except InvalidToken as exc:
            raise PrivatePayloadIntegrityError(
                "private payload authentication or decryption failed"
            ) from exc
        try:
            envelope = json.loads(plaintext.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PrivatePayloadIntegrityError("private payload envelope is invalid") from exc
        if not isinstance(envelope, dict):
            raise PrivatePayloadIntegrityError("private payload envelope must be an object")
        if envelope.get("schema_version") != PRIVATE_PAYLOAD_SCHEMA_VERSION:
            raise PrivatePayloadIntegrityError("private payload schema version is unsupported")

        job_id = str(envelope.get("job_id") or "").strip()
        expected_job = str(expected_job_id or "").strip()
        if expected_job and not hmac.compare_digest(job_id, expected_job):
            raise PrivatePayloadIntegrityError("private payload job_id does not match")

        payload = envelope.get("payload")
        if not isinstance(payload, dict):
            raise PrivatePayloadIntegrityError("private payload body must be an object")
        observed_digest = payload_sha256(payload)
        envelope_digest = str(envelope.get("request_sha256") or "").strip()
        if not envelope_digest or not hmac.compare_digest(observed_digest, envelope_digest):
            raise PrivatePayloadIntegrityError("private payload content hash is invalid")
        expected_digest = str(expected_request_sha256 or "").strip()
        if expected_digest and not hmac.compare_digest(observed_digest, expected_digest):
            raise PrivatePayloadIntegrityError("private payload request SHA256 does not match")

        expires_at = _parse_utc(envelope.get("expires_at_utc"))
        if not allow_expired and _utc_now() > expires_at:
            raise PrivatePayloadExpiredError("private payload has expired")
        return payload

    def inspect(
        self,
        reference: str,
        *,
        expected_job_id: str = "",
        expected_request_sha256: str = "",
    ) -> dict[str, Any]:
        payload = self.get(
            reference,
            expected_job_id=expected_job_id,
            expected_request_sha256=expected_request_sha256,
        )
        return {
            "private_payload_ref": str(reference),
            "private_payload_request_sha256": payload_sha256(payload),
            "private_payload_ligand_count": len(payload.get("ligands") or []),
            "private_payload_store_ready": True,
        }

    def delete(self, reference: str) -> bool:
        path = self._path_for_reference(reference)
        if not path.exists():
            return False
        try:
            path.unlink()
        except OSError as exc:
            raise PrivatePayloadError("private payload could not be deleted") from exc
        return True
