from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable

import pytest

from api.validated_runner_runtime_qualification import (
    MAX_RECEIPT_BYTES,
    RECEIPT_PATH_ENV,
    RECEIPT_SHA256_ENV,
    validated_runner_namespace_runtime_receipt_template,
    verify_validated_runner_namespace_runtime,
)


NOW = dt.datetime(2026, 7, 16, 0, 0, tzinfo=dt.timezone.utc)


def _write_receipt(
    path: Path,
    *,
    issued_at: dt.datetime | None = None,
    expires_at: dt.datetime | None = None,
    mutate: Callable[[dict[str, Any]], None] | None = None,
) -> str:
    payload = validated_runner_namespace_runtime_receipt_template(
        issued_at=issued_at or NOW - dt.timedelta(minutes=1),
        expires_at=expires_at or NOW + dt.timedelta(hours=1),
    )
    if mutate is not None:
        mutate(payload)
    raw = (json.dumps(payload, sort_keys=True) + "\n").encode()
    path.write_bytes(raw)
    path.chmod(0o600)
    return hashlib.sha256(raw).hexdigest()


def test_namespace_runtime_receipt_requires_independently_pinned_hash(
    tmp_path: Path,
) -> None:
    receipt = tmp_path / "namespace-runtime.json"
    actual_sha256 = _write_receipt(receipt)

    qualified = verify_validated_runner_namespace_runtime(
        receipt_path=receipt,
        expected_sha256=actual_sha256,
        now=NOW,
    )
    forged_pin = verify_validated_runner_namespace_runtime(
        receipt_path=receipt,
        expected_sha256="0" * 64,
        now=NOW,
    )

    assert qualified.qualified is True
    assert qualified.reason == "qualified"
    assert forged_pin.qualified is False
    assert forged_pin.reason == "receipt_sha256_mismatch"


@pytest.mark.parametrize(
    ("issued_at", "expires_at", "reason"),
    [
        (
            NOW - dt.timedelta(hours=2),
            NOW - dt.timedelta(seconds=1),
            "receipt_expired",
        ),
        (
            NOW - dt.timedelta(hours=25),
            NOW + dt.timedelta(minutes=1),
            "receipt_validity_window_invalid",
        ),
        (
            NOW + dt.timedelta(minutes=6),
            NOW + dt.timedelta(hours=1),
            "receipt_not_yet_valid",
        ),
    ],
)
def test_namespace_runtime_receipt_enforces_freshness(
    tmp_path: Path,
    issued_at: dt.datetime,
    expires_at: dt.datetime,
    reason: str,
) -> None:
    receipt = tmp_path / "namespace-runtime.json"
    sha256 = _write_receipt(
        receipt,
        issued_at=issued_at,
        expires_at=expires_at,
    )

    result = verify_validated_runner_namespace_runtime(
        receipt_path=receipt,
        expected_sha256=sha256,
        now=NOW,
    )

    assert result.qualified is False
    assert result.reason == reason


def test_namespace_runtime_receipt_requires_exact_containment_contract(
    tmp_path: Path,
) -> None:
    receipt = tmp_path / "namespace-runtime.json"
    sha256 = _write_receipt(
        receipt,
        mutate=lambda payload: payload["containment"].update(
            {"supervisor_no_new_privs": False}
        ),
    )

    result = verify_validated_runner_namespace_runtime(
        receipt_path=receipt,
        expected_sha256=sha256,
        now=NOW,
    )

    assert result.qualified is False
    assert result.reason == "receipt_containment_invalid"


def test_namespace_runtime_receipt_rejects_integer_boolean_aliases(
    tmp_path: Path,
) -> None:
    receipt = tmp_path / "namespace-runtime.json"
    sha256 = _write_receipt(
        receipt,
        mutate=lambda payload: payload["containment"].update(
            {"supervisor_no_new_privs": 1}
        ),
    )

    result = verify_validated_runner_namespace_runtime(
        receipt_path=receipt,
        expected_sha256=sha256,
        now=NOW,
    )

    assert result.qualified is False
    assert result.reason == "receipt_containment_invalid"


def test_namespace_runtime_receipt_rejects_symlink_and_nonregular_files(
    tmp_path: Path,
) -> None:
    receipt = tmp_path / "namespace-runtime.json"
    sha256 = _write_receipt(receipt)
    symlink = tmp_path / "namespace-runtime-link.json"
    symlink.symlink_to(receipt)
    hardlink = tmp_path / "namespace-runtime-hardlink.json"
    os.link(receipt, hardlink)
    fifo = tmp_path / "namespace-runtime.fifo"
    os.mkfifo(fifo)

    symlink_result = verify_validated_runner_namespace_runtime(
        receipt_path=symlink,
        expected_sha256=sha256,
        now=NOW,
    )
    fifo_result = verify_validated_runner_namespace_runtime(
        receipt_path=fifo,
        expected_sha256=sha256,
        now=NOW,
    )
    hardlink_result = verify_validated_runner_namespace_runtime(
        receipt_path=hardlink,
        expected_sha256=sha256,
        now=NOW,
    )

    assert symlink_result.qualified is False
    assert symlink_result.reason == "receipt_symlink_rejected"
    assert fifo_result.qualified is False
    assert fifo_result.reason == "receipt_not_regular_file"
    assert hardlink_result.qualified is False
    assert hardlink_result.reason == "receipt_hardlink_rejected"


def test_namespace_runtime_receipt_rejects_symlinked_parent_and_unsafe_mode(
    tmp_path: Path,
) -> None:
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    receipt = real_dir / "namespace-runtime.json"
    sha256 = _write_receipt(receipt)
    linked_dir = tmp_path / "linked"
    linked_dir.symlink_to(real_dir, target_is_directory=True)

    linked_parent_result = verify_validated_runner_namespace_runtime(
        receipt_path=linked_dir / receipt.name,
        expected_sha256=sha256,
        now=NOW,
    )
    assert linked_parent_result.qualified is False
    assert linked_parent_result.reason == "receipt_path_component_rejected"

    receipt.chmod(0o666)
    unsafe_mode_result = verify_validated_runner_namespace_runtime(
        receipt_path=receipt,
        expected_sha256=sha256,
        now=NOW,
    )
    assert unsafe_mode_result.qualified is False
    assert unsafe_mode_result.reason == "receipt_permissions_unsafe"


@pytest.mark.parametrize("mutation", ["duplicate", "extra"])
def test_namespace_runtime_receipt_rejects_ambiguous_schema(
    tmp_path: Path,
    mutation: str,
) -> None:
    receipt = tmp_path / "namespace-runtime.json"
    payload = validated_runner_namespace_runtime_receipt_template(
        issued_at=NOW - dt.timedelta(minutes=1),
        expires_at=NOW + dt.timedelta(hours=1),
    )
    if mutation == "duplicate":
        raw = json.dumps(payload, sort_keys=True)[:-1]
        raw += ', "schema_version": "validated_runner_namespace_runtime_receipt_v1"}'
        expected_reason = "receipt_json_invalid"
    else:
        payload["unexpected"] = True
        raw = json.dumps(payload, sort_keys=True)
        expected_reason = "receipt_top_level_fields_invalid"
    encoded = (raw + "\n").encode()
    receipt.write_bytes(encoded)
    receipt.chmod(0o600)

    result = verify_validated_runner_namespace_runtime(
        receipt_path=receipt,
        expected_sha256=hashlib.sha256(encoded).hexdigest(),
        now=NOW,
    )

    assert result.qualified is False
    assert result.reason == expected_reason


def test_namespace_runtime_receipt_reader_is_bounded(tmp_path: Path) -> None:
    receipt = tmp_path / "namespace-runtime.json"
    receipt.write_bytes(b"x" * (MAX_RECEIPT_BYTES + 1))
    receipt.chmod(0o600)

    result = verify_validated_runner_namespace_runtime(
        receipt_path=receipt,
        expected_sha256=hashlib.sha256(receipt.read_bytes()).hexdigest(),
        now=NOW,
    )

    assert result.qualified is False
    assert result.reason == "receipt_too_large"


def test_enabled_runner_fails_closed_without_namespace_runtime_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from api import validated_runner

    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_enabled", True)
    monkeypatch.delenv(RECEIPT_PATH_ENV, raising=False)
    monkeypatch.delenv(RECEIPT_SHA256_ENV, raising=False)

    with pytest.raises(
        PermissionError,
        match="validated_runner_namespace_runtime_unqualified:receipt_path_missing",
    ):
        asyncio.run(
            validated_runner.execute_validated_runner_profile(
                "job-no-runtime-receipt",
                {},
            )
        )
