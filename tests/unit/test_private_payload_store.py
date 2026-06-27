from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from betelgeuze_product.private_payload_store import (
    ERR_EXPIRED,
    ERR_JOB_ID_MISMATCH,
    ERR_MISSING,
    ERR_NO_KEYS,
    ERR_REQUEST_MISMATCH,
    ERR_TAMPERED,
    ERR_UNKNOWN_KEY,
    EncryptedPrivatePayloadStore,
    PrivatePayloadKey,
    PrivatePayloadKeyring,
    PrivatePayloadStoreError,
    canonical_request_sha256,
    open_encrypted_payload,
    seal_encrypted_payload,
)


BASE_NOW = 1_700_000_000.0
JOB_ID = "job-abc-123"
RAW_REQUEST = {
    "target_name": "ADRB2",
    "runner_profile_params": {
        "ligands": ["CCO", "CCN"],
        "protein_pdb": "ATOM      1  N   MET A   1      11.104  13.207  10.000",
        "metadata": {"ligand_smiles": "CCN", "nested": {"count": 2}},
    },
}


def _keyring(*ids: str) -> PrivatePayloadKeyring:
    keys = [PrivatePayloadKey(key_id=k, secret=(k.encode() * 32)[:32]) for k in (ids or ("k1",))]
    return PrivatePayloadKeyring(keys)


def _request_hash() -> str:
    return canonical_request_sha256(RAW_REQUEST)


# --- envelope-level round trip / tamper / expiry / binding ---


def test_round_trip_preserves_nested_payload() -> None:
    keyring = _keyring("k1")
    envelope = seal_encrypted_payload(
        RAW_REQUEST,
        keyring=keyring,
        job_id=JOB_ID,
        request_sha256=_request_hash(),
        ttl_seconds=300,
        now=BASE_NOW,
    )
    recovered = open_encrypted_payload(
        envelope,
        keyring=keyring,
        job_id=JOB_ID,
        request_sha256=_request_hash(),
        now=BASE_NOW,
    )
    assert recovered == RAW_REQUEST
    assert recovered is not RAW_REQUEST
    assert recovered["runner_profile_params"]["metadata"]["nested"]["count"] == 2


def test_ciphertext_does_not_leak_plaintext() -> None:
    keyring = _keyring("k1")
    envelope = seal_encrypted_payload(
        RAW_REQUEST,
        keyring=keyring,
        job_id=JOB_ID,
        request_sha256=_request_hash(),
        ttl_seconds=300,
        now=BASE_NOW,
    )
    serialized = json.dumps(envelope)
    assert "CCO" not in serialized
    assert "ATOM" not in serialized
    assert "ligand_smiles" not in serialized


def test_rejects_tampered_ciphertext() -> None:
    keyring = _keyring("k1")
    envelope = seal_encrypted_payload(
        RAW_REQUEST,
        keyring=keyring,
        job_id=JOB_ID,
        request_sha256=_request_hash(),
        ttl_seconds=300,
        now=BASE_NOW,
    )
    envelope["ciphertext"] = envelope["ciphertext"][:-4] + "AAAA"
    with pytest.raises(PrivatePayloadStoreError) as exc:
        open_encrypted_payload(
            envelope,
            keyring=keyring,
            job_id=JOB_ID,
            request_sha256=_request_hash(),
            now=BASE_NOW,
        )
    assert exc.value.code == ERR_TAMPERED


def test_rejects_tampered_header_field() -> None:
    keyring = _keyring("k1")
    envelope = seal_encrypted_payload(
        RAW_REQUEST,
        keyring=keyring,
        job_id=JOB_ID,
        request_sha256=_request_hash(),
        ttl_seconds=300,
        now=BASE_NOW,
    )
    # Push expiry far into the future by tampering the authenticated header.
    envelope["expires_at"] = BASE_NOW + 10_000_000
    with pytest.raises(PrivatePayloadStoreError) as exc:
        open_encrypted_payload(
            envelope,
            keyring=keyring,
            job_id=JOB_ID,
            request_sha256=_request_hash(),
            now=BASE_NOW,
        )
    assert exc.value.code == ERR_TAMPERED


def test_rejects_wrong_job_id() -> None:
    keyring = _keyring("k1")
    envelope = seal_encrypted_payload(
        RAW_REQUEST,
        keyring=keyring,
        job_id=JOB_ID,
        request_sha256=_request_hash(),
        ttl_seconds=300,
        now=BASE_NOW,
    )
    with pytest.raises(PrivatePayloadStoreError) as exc:
        open_encrypted_payload(
            envelope,
            keyring=keyring,
            job_id="someone-elses-job",
            request_sha256=_request_hash(),
            now=BASE_NOW,
        )
    assert exc.value.code == ERR_JOB_ID_MISMATCH


def test_rejects_wrong_request_hash() -> None:
    keyring = _keyring("k1")
    envelope = seal_encrypted_payload(
        RAW_REQUEST,
        keyring=keyring,
        job_id=JOB_ID,
        request_sha256=_request_hash(),
        ttl_seconds=300,
        now=BASE_NOW,
    )
    with pytest.raises(PrivatePayloadStoreError) as exc:
        open_encrypted_payload(
            envelope,
            keyring=keyring,
            job_id=JOB_ID,
            request_sha256=canonical_request_sha256({"target_name": "OTHER"}),
            now=BASE_NOW,
        )
    assert exc.value.code == ERR_REQUEST_MISMATCH


def test_rejects_expired_envelope() -> None:
    keyring = _keyring("k1")
    envelope = seal_encrypted_payload(
        RAW_REQUEST,
        keyring=keyring,
        job_id=JOB_ID,
        request_sha256=_request_hash(),
        ttl_seconds=60,
        now=BASE_NOW,
    )
    with pytest.raises(PrivatePayloadStoreError) as exc:
        open_encrypted_payload(
            envelope,
            keyring=keyring,
            job_id=JOB_ID,
            request_sha256=_request_hash(),
            now=BASE_NOW + 61,
        )
    assert exc.value.code == ERR_EXPIRED


# --- key handling / rotation ---


def test_unknown_key_is_rejected() -> None:
    sealed_keyring = _keyring("k1")
    envelope = seal_encrypted_payload(
        RAW_REQUEST,
        keyring=sealed_keyring,
        job_id=JOB_ID,
        request_sha256=_request_hash(),
        ttl_seconds=300,
        now=BASE_NOW,
    )
    other_keyring = _keyring("k2")
    with pytest.raises(PrivatePayloadStoreError) as exc:
        open_encrypted_payload(
            envelope,
            keyring=other_keyring,
            job_id=JOB_ID,
            request_sha256=_request_hash(),
            now=BASE_NOW,
        )
    assert exc.value.code == ERR_UNKNOWN_KEY


def test_key_rotation_still_opens_old_records() -> None:
    old_keyring = _keyring("k1")
    envelope = seal_encrypted_payload(
        RAW_REQUEST,
        keyring=old_keyring,
        job_id=JOB_ID,
        request_sha256=_request_hash(),
        ttl_seconds=300,
        now=BASE_NOW,
    )
    # Rotate: new primary k2, but k1 retained for decryption.
    rotated = PrivatePayloadKeyring(
        [
            PrivatePayloadKey(key_id="k2", secret=(b"k2" * 16)[:32]),
            PrivatePayloadKey(key_id="k1", secret=(b"k1" * 16)[:32]),
        ]
    )
    recovered = open_encrypted_payload(
        envelope,
        keyring=rotated,
        job_id=JOB_ID,
        request_sha256=_request_hash(),
        now=BASE_NOW,
    )
    assert recovered == RAW_REQUEST
    # New seals use the rotated primary.
    new_envelope = seal_encrypted_payload(
        RAW_REQUEST,
        keyring=rotated,
        job_id=JOB_ID,
        request_sha256=_request_hash(),
        ttl_seconds=300,
        now=BASE_NOW,
    )
    assert new_envelope["key_id"] == "k2"


def test_empty_keyring_from_config_is_rejected() -> None:
    with pytest.raises(PrivatePayloadStoreError) as exc:
        PrivatePayloadKeyring.from_config("   ")
    assert exc.value.code == ERR_NO_KEYS


def test_keyring_from_config_round_trips() -> None:
    secret_b64 = PrivatePayloadKeyring.generate_secret_b64()
    keyring = PrivatePayloadKeyring.from_config(f"primary:{secret_b64}")
    assert keyring.primary.key_id == "primary"


# --- filesystem store ---


def test_store_round_trip(tmp_path: Path) -> None:
    store = EncryptedPrivatePayloadStore(
        tmp_path / "private", keyring=_keyring("k1"), ttl_seconds=300, now=BASE_NOW
    )
    ref = store.put(JOB_ID, _request_hash(), RAW_REQUEST)
    recovered = store.get(ref, job_id=JOB_ID, request_sha256=_request_hash())
    assert recovered == RAW_REQUEST


def test_store_file_permissions_are_restrictive(tmp_path: Path) -> None:
    root = tmp_path / "private"
    store = EncryptedPrivatePayloadStore(root, keyring=_keyring("k1"), ttl_seconds=300, now=BASE_NOW)
    ref = store.put(JOB_ID, _request_hash(), RAW_REQUEST)
    payload_file = root / f"{ref}.payload.json"
    assert payload_file.exists()
    file_mode = stat.S_IMODE(os.stat(payload_file).st_mode)
    assert file_mode & 0o077 == 0, f"file is group/other accessible: {oct(file_mode)}"
    dir_mode = stat.S_IMODE(os.stat(root).st_mode)
    assert dir_mode & 0o077 == 0, f"dir is group/other accessible: {oct(dir_mode)}"


def test_store_disk_bytes_do_not_contain_plaintext(tmp_path: Path) -> None:
    root = tmp_path / "private"
    store = EncryptedPrivatePayloadStore(root, keyring=_keyring("k1"), ttl_seconds=300, now=BASE_NOW)
    ref = store.put(JOB_ID, _request_hash(), RAW_REQUEST)
    on_disk = (root / f"{ref}.payload.json").read_text(encoding="utf-8")
    assert "CCO" not in on_disk
    assert "ATOM" not in on_disk


def test_store_missing_ref_raises(tmp_path: Path) -> None:
    store = EncryptedPrivatePayloadStore(
        tmp_path / "private", keyring=_keyring("k1"), ttl_seconds=300, now=BASE_NOW
    )
    with pytest.raises(PrivatePayloadStoreError) as exc:
        store.get("does-not-exist", job_id=JOB_ID, request_sha256=_request_hash())
    assert exc.value.code == ERR_MISSING


def test_store_get_rejects_wrong_request_hash(tmp_path: Path) -> None:
    store = EncryptedPrivatePayloadStore(
        tmp_path / "private", keyring=_keyring("k1"), ttl_seconds=300, now=BASE_NOW
    )
    ref = store.put(JOB_ID, _request_hash(), RAW_REQUEST)
    with pytest.raises(PrivatePayloadStoreError) as exc:
        store.get(ref, job_id=JOB_ID, request_sha256=canonical_request_sha256({"x": 1}))
    assert exc.value.code == ERR_REQUEST_MISMATCH


def test_store_delete(tmp_path: Path) -> None:
    store = EncryptedPrivatePayloadStore(
        tmp_path / "private", keyring=_keyring("k1"), ttl_seconds=300, now=BASE_NOW
    )
    ref = store.put(JOB_ID, _request_hash(), RAW_REQUEST)
    assert store.delete(ref) is True
    assert store.delete(ref) is False
