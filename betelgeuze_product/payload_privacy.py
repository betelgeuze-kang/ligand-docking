from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any

PRIVATE_PAYLOAD_ENVELOPE_VERSION = "private_payload_integrity_v1"
PRIVATE_PAYLOAD_INTEGRITY_ALGORITHM = "hmac-sha256"

SENSITIVE_SCALAR_KEYS = {
    "canonical_smiles",
    "inline_pdb",
    "isomeric_smiles",
    "ligand_smiles",
    "mol2_content",
    "pdb_content",
    "pdb_text",
    "pdbqt_content",
    "protein_pdb",
    "sdf_content",
    "smiles",
    "source_value",
    "structure_content",
    "target_pdb",
}
SENSITIVE_COLLECTION_KEYS = {"compound", "compounds", "ligand", "ligands"}
SENSITIVE_KEY_SUFFIXES = ("_pdb_content", "_pdb_text", "_smiles")


def _canonical_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _redaction_record(value: Any) -> dict[str, Any]:
    raw = _canonical_text(value)
    return {
        "redacted": True,
        "redaction": "sha256",
        "sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest() if raw else "",
        "byte_length": len(raw.encode("utf-8")),
    }


def _is_sensitive_key(key: str) -> bool:
    return key in SENSITIVE_SCALAR_KEYS or key.endswith(SENSITIVE_KEY_SUFFIXES)


def sanitize_request_for_ledger(value: Any, *, parent_key: str = "") -> Any:
    key = parent_key.lower()
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            child_key = str(raw_key)
            child_key_l = child_key.lower()
            if child_key_l.endswith("_sha256") or child_key_l == "request_sha256":
                sanitized[child_key] = raw_value
            elif _is_sensitive_key(child_key_l):
                sanitized[child_key] = _redaction_record(raw_value)
            else:
                sanitized[child_key] = sanitize_request_for_ledger(raw_value, parent_key=child_key)
        return sanitized
    if isinstance(value, list):
        return [sanitize_request_for_ledger(item, parent_key=parent_key) for item in value]
    if key in SENSITIVE_COLLECTION_KEYS and isinstance(value, str):
        return _redaction_record(value)
    return value


def _private_payload_now(now: float | None) -> float:
    return float(time.time() if now is None else now)


def _private_payload_signing_body(
    *,
    issued_at: float,
    expires_at: float,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "envelope_version": PRIVATE_PAYLOAD_ENVELOPE_VERSION,
        "integrity_algorithm": PRIVATE_PAYLOAD_INTEGRITY_ALGORITHM,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "payload": payload,
    }


def _private_payload_signature(signing_body: dict[str, Any], *, signing_key: str) -> str:
    canonical = json.dumps(signing_body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )
    return hmac.new(signing_key.encode("utf-8"), canonical, hashlib.sha256).hexdigest()


def seal_private_payload(
    payload: dict[str, Any],
    *,
    signing_key: str,
    ttl_seconds: float,
    now: float | None = None,
) -> dict[str, Any]:
    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be positive")
    issued_at = _private_payload_now(now)
    expires_at = issued_at + float(ttl_seconds)
    signing_body = _private_payload_signing_body(
        issued_at=issued_at,
        expires_at=expires_at,
        payload=dict(payload),
    )
    envelope = dict(signing_body)
    envelope["signature"] = _private_payload_signature(signing_body, signing_key=signing_key)
    return envelope


def open_private_payload(
    envelope: dict[str, Any],
    *,
    signing_key: str,
    now: float | None = None,
) -> dict[str, Any]:
    observed_signature = str(envelope.get("signature") or "")
    signing_body = {
        key: envelope[key]
        for key in (
            "envelope_version",
            "integrity_algorithm",
            "issued_at",
            "expires_at",
            "payload",
        )
        if key in envelope
    }
    expected_signature = _private_payload_signature(signing_body, signing_key=signing_key)
    if not observed_signature or not hmac.compare_digest(observed_signature, expected_signature):
        raise ValueError("private_payload_tampered")
    current_time = _private_payload_now(now)
    expires_at = float(envelope.get("expires_at") or 0)
    if current_time > expires_at:
        raise ValueError("private_payload_expired")
    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("private_payload_tampered")
    return dict(payload)
