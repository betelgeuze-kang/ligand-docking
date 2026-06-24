from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from betelgeuze_product import private_payload_store as payload_store_mod
from betelgeuze_product.private_payload_store import (
    PrivatePayloadExpiredError,
    PrivatePayloadIntegrityError,
    PrivatePayloadStore,
    payload_sha256,
)


def _test_key() -> str:
    return base64.urlsafe_b64encode(b"test-private-payload-key-0000000"[:32]).decode("ascii")


def _store(tmp_path: Path, *, ttl_seconds: int = 60) -> PrivatePayloadStore:
    return PrivatePayloadStore(
        tmp_path / "private",
        fernet_keys=[_test_key()],
        key_id="test-key-v1",
        ttl_seconds=ttl_seconds,
    )


def _payload() -> dict:
    return {
        "request_type": "structure_analysis_ligand_docking",
        "family": "gpcr",
        "target_id": "ADRB2",
        "pdb_content": "ATOM      1  CA  GLY A   1      12.104  13.207  14.321\n",
        "ligands": [{"ligand_id": "lig-1", "smiles": "CCO"}],
    }


def test_private_payload_round_trip_is_authenticated_and_not_plaintext(tmp_path: Path) -> None:
    store = _store(tmp_path)
    payload = _payload()
    digest = payload_sha256(payload)
    metadata = store.put(
        job_id="job-private-1",
        payload=payload,
        expected_request_sha256=digest,
    )

    restored = store.get(
        metadata["private_payload_ref"],
        expected_job_id="job-private-1",
        expected_request_sha256=digest,
    )
    inspection = store.inspect(
        metadata["private_payload_ref"],
        expected_job_id="job-private-1",
        expected_request_sha256=digest,
    )

    assert restored == payload
    assert inspection["private_payload_ligand_count"] == 1
    assert inspection["private_payload_request_sha256"] == digest
    encrypted_path = store._path_for_reference(metadata["private_payload_ref"])
    encrypted_bytes = encrypted_path.read_bytes()
    assert b"CCO" not in encrypted_bytes
    assert b"ATOM" not in encrypted_bytes
    assert encrypted_path.stat().st_mode & 0o077 == 0


def test_private_payload_corruption_is_rejected(tmp_path: Path) -> None:
    store = _store(tmp_path)
    metadata = store.put(job_id="job-private-2", payload=_payload())
    path = store._path_for_reference(metadata["private_payload_ref"])
    encrypted = path.read_bytes().strip()
    path.write_bytes(encrypted[:-8] + b"corrupt!\n")

    with pytest.raises(
        PrivatePayloadIntegrityError,
        match="authentication or decryption failed",
    ):
        store.get(
            metadata["private_payload_ref"],
            expected_job_id="job-private-2",
        )


def test_private_payload_expiry_is_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_time = datetime(2026, 6, 24, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(payload_store_mod, "_utc_now", lambda: base_time)
    store = _store(tmp_path, ttl_seconds=5)
    metadata = store.put(job_id="job-private-3", payload=_payload())

    monkeypatch.setattr(
        payload_store_mod,
        "_utc_now",
        lambda: base_time + timedelta(seconds=6),
    )
    with pytest.raises(PrivatePayloadExpiredError, match="has expired"):
        store.get(
            metadata["private_payload_ref"],
            expected_job_id="job-private-3",
        )


def test_private_payload_hash_and_job_mismatch_are_rejected(tmp_path: Path) -> None:
    store = _store(tmp_path)
    metadata = store.put(job_id="job-private-4", payload=_payload())

    with pytest.raises(PrivatePayloadIntegrityError, match="job_id does not match"):
        store.get(
            metadata["private_payload_ref"],
            expected_job_id="another-job",
        )
    with pytest.raises(PrivatePayloadIntegrityError, match="request SHA256 does not match"):
        store.get(
            metadata["private_payload_ref"],
            expected_job_id="job-private-4",
            expected_request_sha256="0" * 64,
        )
