"""Wiring helpers for the encrypted private payload store in the docking flow.

This is the bridge between the raw customer docking request and the encrypted
at-rest store (`betelgeuze_product.private_payload_store`). It deliberately has
**no FastAPI/pandas dependency** so the store/recover logic can be unit tested
in isolation; the API endpoint and the queue materializer only *call* it.

End-to-end intent:

1. At submit time the original request (with raw SMILES/PDB/...) is encrypted
   and stored, keyed by ``job_id`` and bound to the ledger ``request_sha256``.
   The public ledger keeps only the redacted form.
2. At materialization time, when the ledger/queue carry only redacted ligand
   sources, the original ligands are recovered from the store with the same
   ``job_id`` + ``request_sha256`` binding.

Every entry point is **fail-closed**: if the store is unconfigured, the payload
is missing, the binding mismatches, the record is tampered, or the TTL expired,
these helpers return ``None`` (or no-op) and the caller keeps its existing
fail-closed behavior. Raw inputs are never logged here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from betelgeuze_product.private_payload_store import (
    EncryptedPrivatePayloadStore,
    PrivatePayloadKeyring,
    PrivatePayloadStoreError,
)

# Default at-rest retention for a stored request (7 days).
DEFAULT_TTL_SECONDS = 7 * 24 * 3600
DEFAULT_STORE_DIR = "./results/private_payloads"


def build_store(
    *,
    keys_config: str,
    root_dir: str | Path,
    ttl_seconds: float = DEFAULT_TTL_SECONDS,
    now: float | None = None,
) -> EncryptedPrivatePayloadStore | None:
    """Build a store from a key-config string, or ``None`` when no keys exist.

    ``keys_config`` is the ordered ``"key_id:base64secret,..."`` format parsed by
    ``PrivatePayloadKeyring.from_config``. An empty/whitespace value disables the
    store (returns ``None``) so the pipeline degrades to redaction-only.
    """

    keys_config = (keys_config or "").strip()
    if not keys_config:
        return None
    keyring = PrivatePayloadKeyring.from_config(keys_config)
    return EncryptedPrivatePayloadStore(
        root_dir,
        keyring=keyring,
        ttl_seconds=ttl_seconds,
        now=now,
    )


def configured_store() -> EncryptedPrivatePayloadStore | None:
    """Build the store from application settings, or ``None`` if not configured.

    Reads settings lazily so importing this module never requires the API
    settings stack. Any configuration error fails closed to ``None``.
    """

    try:
        from api.config import settings
    except Exception:
        return None
    try:
        return build_store(
            keys_config=getattr(settings, "docking_private_payload_keys", "") or "",
            root_dir=getattr(settings, "docking_private_payload_dir", DEFAULT_STORE_DIR) or DEFAULT_STORE_DIR,
            ttl_seconds=int(
                getattr(settings, "docking_private_payload_ttl_seconds", DEFAULT_TTL_SECONDS) or DEFAULT_TTL_SECONDS
            ),
        )
    except (PrivatePayloadStoreError, ValueError, TypeError):
        return None


def store_docking_request(
    store: EncryptedPrivatePayloadStore | None,
    *,
    job_id: str,
    request_sha256: str,
    request: dict[str, Any],
) -> str | None:
    """Encrypt and persist the original request. No-op (``None``) if unusable.

    Bound to ``job_id`` and ``request_sha256`` so a record can only be recovered
    under the same identity. Never raises into the caller (submit must not fail
    because the optional store is misconfigured).
    """

    if store is None or not job_id or not request_sha256 or not isinstance(request, dict):
        return None
    try:
        return store.put(job_id, request_sha256, request)
    except PrivatePayloadStoreError:
        return None


def recover_docking_request(
    store: EncryptedPrivatePayloadStore | None,
    *,
    job_id: str,
    request_sha256: str,
) -> dict[str, Any] | None:
    """Recover the original request, or ``None`` if unavailable/invalid.

    Fail-closed: a missing payload, binding mismatch, tampered record, expired
    TTL, or unknown key all yield ``None``.
    """

    if store is None or not job_id or not request_sha256:
        return None
    try:
        ref = store.ref_for_job(job_id)
        recovered = store.get(ref, job_id=job_id, request_sha256=request_sha256)
    except PrivatePayloadStoreError:
        return None
    return recovered if isinstance(recovered, dict) else None


def recover_request_ligands(
    store: EncryptedPrivatePayloadStore | None,
    *,
    job_id: str,
    request_sha256: str,
) -> list[dict[str, Any]] | None:
    """Return the original ligand rows from the stored request, or ``None``.

    Used by the queue materializer to recover un-redacted ligand sources.
    """

    request = recover_docking_request(store, job_id=job_id, request_sha256=request_sha256)
    if not isinstance(request, dict):
        return None
    ligands = request.get("ligands")
    if isinstance(ligands, list) and ligands:
        rows = [row for row in ligands if isinstance(row, dict)]
        return rows or None
    return None


__all__ = [
    "DEFAULT_TTL_SECONDS",
    "DEFAULT_STORE_DIR",
    "build_store",
    "configured_store",
    "store_docking_request",
    "recover_docking_request",
    "recover_request_ligands",
]
