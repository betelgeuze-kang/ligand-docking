from __future__ import annotations

import datetime as dt
import errno
import hashlib
import hmac
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


RECEIPT_PATH_ENV = "API_VALIDATED_RUNNER_NAMESPACE_RECEIPT_PATH"
RECEIPT_SHA256_ENV = "API_VALIDATED_RUNNER_NAMESPACE_RECEIPT_SHA256"
RECEIPT_SCHEMA_VERSION = "validated_runner_namespace_runtime_receipt_v1"
MAX_RECEIPT_BYTES = 32 * 1024
MAX_RECEIPT_VALIDITY = dt.timedelta(hours=24)
MAX_CLOCK_SKEW = dt.timedelta(minutes=5)

_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
_TOP_LEVEL_FIELDS = {
    "schema_version",
    "qualification",
    "containment",
    "issued_at_utc",
    "expires_at_utc",
}
_QUALIFICATION = {
    "validated_runner_namespace_runtime_qualified": True,
    "runtime_class": "namespace_capable_host_v1",
}
_CONTAINMENT = {
    "private_user_namespace": True,
    "private_pid_namespace": True,
    "private_mount_namespace": True,
    "namespace_init_pidfd_pinned_before_runner_start": True,
    "runner_start_gate_enforced": True,
    "supervisor_no_new_privs": True,
    "supervisor_effective_capabilities_zero": True,
    "supervisor_non_dumpable": True,
}


@dataclass(frozen=True)
class NamespaceRuntimeQualification:
    qualified: bool
    reason: str
    schema_version: str = ""
    receipt_sha256: str = ""
    issued_at_utc: str = ""
    expires_at_utc: str = ""


class _DuplicateJsonKey(ValueError):
    pass


def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in pairs:
        if key in payload:
            raise _DuplicateJsonKey(key)
        payload[key] = value
    return payload


def _failure(
    reason: str,
    *,
    schema_version: str = "",
    receipt_sha256: str = "",
    issued_at_utc: str = "",
    expires_at_utc: str = "",
) -> NamespaceRuntimeQualification:
    return NamespaceRuntimeQualification(
        qualified=False,
        reason=reason,
        schema_version=schema_version,
        receipt_sha256=receipt_sha256,
        issued_at_utc=issued_at_utc,
        expires_at_utc=expires_at_utc,
    )


def _open_receipt_without_symlinks(path: Path) -> tuple[int, str]:
    directory_flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    file_flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NONBLOCK", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    parts = path.parts
    if not path.is_absolute() or len(parts) < 2 or any(
        part in {"", ".", ".."} for part in parts[1:]
    ):
        return -1, "receipt_path_invalid"

    current_fd = -1
    file_fd = -1
    try:
        current_fd = os.open(path.anchor, directory_flags)
        for part in parts[1:-1]:
            next_fd = os.open(part, directory_flags, dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
        file_fd = os.open(parts[-1], file_flags, dir_fd=current_fd)
        return file_fd, ""
    except OSError as exc:
        if file_fd >= 0:
            os.close(file_fd)
        if exc.errno == errno.ELOOP:
            return -1, "receipt_symlink_rejected"
        if exc.errno == errno.ENOTDIR:
            return -1, "receipt_path_component_rejected"
        return -1, "receipt_open_failed"
    finally:
        if current_fd >= 0:
            os.close(current_fd)


def _read_regular_receipt(path: Path) -> tuple[bytes | None, str]:
    fd, open_error = _open_receipt_without_symlinks(path)
    if fd < 0:
        return None, open_error

    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode):
            return None, "receipt_not_regular_file"
        if metadata.st_nlink != 1:
            return None, "receipt_hardlink_rejected"
        if metadata.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            return None, "receipt_permissions_unsafe"
        if metadata.st_size <= 0:
            return None, "receipt_empty"
        if metadata.st_size > MAX_RECEIPT_BYTES:
            return None, "receipt_too_large"

        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(fd, min(8192, MAX_RECEIPT_BYTES + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > MAX_RECEIPT_BYTES:
                return None, "receipt_too_large"
        payload = b"".join(chunks)
        if not payload:
            return None, "receipt_empty"
        return payload, ""
    except OSError:
        return None, "receipt_read_failed"
    finally:
        os.close(fd)


def _parse_utc_timestamp(value: Any) -> dt.datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = dt.datetime.strptime(value, _TIMESTAMP_FORMAT)
    except ValueError:
        return None
    return parsed.replace(tzinfo=dt.timezone.utc)


def _matches_exact_mapping(
    value: Any,
    expected: Mapping[str, Any],
) -> bool:
    if not isinstance(value, dict) or set(value) != set(expected):
        return False
    return all(
        type(value[key]) is type(expected_value) and value[key] == expected_value
        for key, expected_value in expected.items()
    )


def verify_validated_runner_namespace_runtime(
    *,
    receipt_path: str | os.PathLike[str] | None = None,
    expected_sha256: str | None = None,
    now: dt.datetime | None = None,
    environ: Mapping[str, str] | None = None,
) -> NamespaceRuntimeQualification:
    environment = os.environ if environ is None else environ
    configured_path = str(
        receipt_path
        if receipt_path is not None
        else environment.get(RECEIPT_PATH_ENV, "")
    ).strip()
    configured_sha256 = str(
        expected_sha256
        if expected_sha256 is not None
        else environment.get(RECEIPT_SHA256_ENV, "")
    ).strip()

    if not configured_path:
        return _failure("receipt_path_missing")
    path = Path(configured_path)
    if not path.is_absolute():
        return _failure("receipt_path_not_absolute")
    if _SHA256_RE.fullmatch(configured_sha256) is None:
        return _failure("receipt_sha256_pin_invalid")

    raw, read_error = _read_regular_receipt(path)
    if raw is None:
        return _failure(read_error)
    actual_sha256 = hashlib.sha256(raw).hexdigest()
    if not hmac.compare_digest(actual_sha256, configured_sha256):
        return _failure(
            "receipt_sha256_mismatch",
            receipt_sha256=actual_sha256,
        )

    try:
        payload = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_object_without_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, _DuplicateJsonKey):
        return _failure(
            "receipt_json_invalid",
            receipt_sha256=actual_sha256,
        )
    if not isinstance(payload, dict) or set(payload) != _TOP_LEVEL_FIELDS:
        return _failure(
            "receipt_top_level_fields_invalid",
            receipt_sha256=actual_sha256,
        )

    schema_version = payload.get("schema_version")
    if schema_version != RECEIPT_SCHEMA_VERSION:
        return _failure(
            "receipt_schema_version_invalid",
            schema_version=str(schema_version or ""),
            receipt_sha256=actual_sha256,
        )
    if not _matches_exact_mapping(payload.get("qualification"), _QUALIFICATION):
        return _failure(
            "receipt_qualification_invalid",
            schema_version=RECEIPT_SCHEMA_VERSION,
            receipt_sha256=actual_sha256,
        )
    if not _matches_exact_mapping(payload.get("containment"), _CONTAINMENT):
        return _failure(
            "receipt_containment_invalid",
            schema_version=RECEIPT_SCHEMA_VERSION,
            receipt_sha256=actual_sha256,
        )

    issued_at_text = payload.get("issued_at_utc")
    expires_at_text = payload.get("expires_at_utc")
    issued_at = _parse_utc_timestamp(issued_at_text)
    expires_at = _parse_utc_timestamp(expires_at_text)
    if issued_at is None or expires_at is None:
        return _failure(
            "receipt_timestamp_invalid",
            schema_version=RECEIPT_SCHEMA_VERSION,
            receipt_sha256=actual_sha256,
        )
    if expires_at <= issued_at or expires_at - issued_at > MAX_RECEIPT_VALIDITY:
        return _failure(
            "receipt_validity_window_invalid",
            schema_version=RECEIPT_SCHEMA_VERSION,
            receipt_sha256=actual_sha256,
            issued_at_utc=str(issued_at_text),
            expires_at_utc=str(expires_at_text),
        )

    checked_at = now or dt.datetime.now(dt.timezone.utc)
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=dt.timezone.utc)
    else:
        checked_at = checked_at.astimezone(dt.timezone.utc)
    if issued_at > checked_at + MAX_CLOCK_SKEW:
        return _failure(
            "receipt_not_yet_valid",
            schema_version=RECEIPT_SCHEMA_VERSION,
            receipt_sha256=actual_sha256,
            issued_at_utc=str(issued_at_text),
            expires_at_utc=str(expires_at_text),
        )
    if checked_at >= expires_at:
        return _failure(
            "receipt_expired",
            schema_version=RECEIPT_SCHEMA_VERSION,
            receipt_sha256=actual_sha256,
            issued_at_utc=str(issued_at_text),
            expires_at_utc=str(expires_at_text),
        )

    return NamespaceRuntimeQualification(
        qualified=True,
        reason="qualified",
        schema_version=RECEIPT_SCHEMA_VERSION,
        receipt_sha256=actual_sha256,
        issued_at_utc=str(issued_at_text),
        expires_at_utc=str(expires_at_text),
    )


def require_validated_runner_namespace_runtime() -> NamespaceRuntimeQualification:
    verification = verify_validated_runner_namespace_runtime()
    if not verification.qualified:
        raise PermissionError(
            "validated_runner_namespace_runtime_unqualified:"
            f"{verification.reason}"
        )
    return verification


def validated_runner_namespace_runtime_receipt_template(
    *,
    issued_at: dt.datetime,
    expires_at: dt.datetime,
) -> dict[str, Any]:
    def _format(value: dt.datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=dt.timezone.utc)
        return value.astimezone(dt.timezone.utc).strftime(_TIMESTAMP_FORMAT)

    return {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "qualification": dict(_QUALIFICATION),
        "containment": dict(_CONTAINMENT),
        "issued_at_utc": _format(issued_at),
        "expires_at_utc": _format(expires_at),
    }
