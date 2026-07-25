"""Stdlib-only pre-import launcher for the Engine v2 console command.

The generated console script imports this top-level module rather than the
``betelgeuze_engine_v2`` package. It validates every installed Engine v2 Python
source file and ``py.typed`` marker against the wheel ``RECORD`` hashes before
importing any Engine v2 package module. Only after the receipt is complete does
it import and dispatch the ordinary CLI.

Wheel ``RECORD`` hashes provide installation-integrity evidence, not a publisher
signature. The receipt therefore keeps signature, scientific, benchmark,
product, customer, and claim statuses closed.
"""

from __future__ import annotations

import base64
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import stat
import sys
from typing import Sequence


PREFLIGHT_RECORD_SCHEMA_ID = (
    "betelgeuze.engine_v2_preimport_distribution_record/1.0.0"
)
PREFLIGHT_FAILURE_SCHEMA_ID = (
    "betelgeuze.engine_v2_preimport_distribution_failure/1.0.0"
)
PREFLIGHT_COMMAND_ID = "betelgeuze-engine-v2/preimport-record/1.0.0"
DISTRIBUTION_NAME = "betelgeuze-engine-v2"
_PACKAGE_PREFIX = "betelgeuze_engine_v2/"
_PREFLIGHT_MODULE = "betelgeuze_engine_v2_preflight.py"
_PY_TYPED = "betelgeuze_engine_v2/py.typed"
_READ_CHUNK_BYTES = 1024 * 1024
MAX_PREFLIGHT_SOURCE_BYTES = 32 * 1024 * 1024
_CRITICAL_SOURCE_PATHS = frozenset(
    {
        _PREFLIGHT_MODULE,
        "betelgeuze_engine_v2/__init__.py",
        "betelgeuze_engine_v2/cli.py",
        "betelgeuze_engine_v2/cli_dispatch.py",
        "betelgeuze_engine_v2/input_bound_verifier.py",
        "betelgeuze_engine_v2/execution_parameter_attestation.py",
        "betelgeuze_engine_v2/scorer_source_observation.py",
        "betelgeuze_engine_v2/reference_pocket.py",
        "betelgeuze_engine_v2/result_verifier.py",
        "betelgeuze_engine_v2/result_verifier_strict.py",
        "betelgeuze_engine_v2/docking/interpretable_scorer.py",
        "betelgeuze_engine_v2/docking/search_fingerprint_material.py",
    }
)

_ACTIVE_PREFLIGHT_RECEIPT: dict[str, object] | None = None


class PreflightRecordError(RuntimeError):
    """The installed distribution cannot satisfy pre-import RECORD integrity."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise PreflightRecordError(
            "preflight receipt is not canonical JSON"
        ) from exc


def _sha256_document(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _engine_modules_loaded() -> tuple[str, ...]:
    return tuple(
        sorted(
            name
            for name in sys.modules
            if name == "betelgeuze_engine_v2"
            or name.startswith("betelgeuze_engine_v2.")
        )
    )


def _read_regular_no_follow(path: Path, *, maximum: int) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = -1
    try:
        descriptor = os.open(path, flags)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise PreflightRecordError(
                f"distribution source is not a regular file: {path.name}"
            )
        if not 0 <= before.st_size <= maximum:
            raise PreflightRecordError(
                f"distribution source exceeds its byte bound: {path.name}"
            )
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, _READ_CHUNK_BYTES)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > maximum:
                raise PreflightRecordError(
                    f"distribution source exceeds its byte bound: {path.name}"
                )
        after = os.fstat(descriptor)
        before_identity = (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        after_identity = (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        if before_identity != after_identity or total != after.st_size:
            raise PreflightRecordError(
                f"distribution source changed while reading: {path.name}"
            )
        return b"".join(chunks)
    except PreflightRecordError:
        raise
    except OSError as exc:
        raise PreflightRecordError(
            f"distribution source could not be read: {path.name}"
        ) from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _record_digest_matches(payload: bytes, *, mode: str, value: str) -> bool:
    if mode != "sha256":
        raise PreflightRecordError(
            f"unsupported RECORD digest algorithm: {mode!r}"
        )
    observed = base64.urlsafe_b64encode(
        hashlib.sha256(payload).digest()
    ).decode("ascii").rstrip("=")
    return observed == value


def _is_verified_source_path(relative_path: str) -> bool:
    return (
        relative_path == _PREFLIGHT_MODULE
        or relative_path == _PY_TYPED
        or (
            relative_path.startswith(_PACKAGE_PREFIX)
            and relative_path.endswith(".py")
        )
    )


def verify_installed_distribution_record() -> dict[str, object]:
    """Verify installed source bytes before importing Engine v2 package code."""

    loaded_before = _engine_modules_loaded()
    if loaded_before:
        raise PreflightRecordError(
            "Engine v2 package modules were imported before preflight"
        )
    try:
        distribution = metadata.distribution(DISTRIBUTION_NAME)
    except metadata.PackageNotFoundError as exc:
        raise PreflightRecordError(
            "Engine v2 distribution metadata is unavailable"
        ) from exc
    files = distribution.files
    if files is None:
        raise PreflightRecordError(
            "Engine v2 distribution RECORD is unavailable"
        )

    verified_files: list[dict[str, object]] = []
    observed_paths: set[str] = set()
    for package_path in sorted(files, key=lambda value: str(value)):
        relative_path = str(package_path).replace("\\", "/")
        if not _is_verified_source_path(relative_path):
            continue
        if relative_path.startswith("/") or ".." in Path(relative_path).parts:
            raise PreflightRecordError(
                "distribution RECORD contains an unsafe source path"
            )
        file_hash = package_path.hash
        if file_hash is None:
            raise PreflightRecordError(
                f"distribution source lacks a RECORD hash: {relative_path}"
            )
        payload = _read_regular_no_follow(
            Path(package_path.locate()),
            maximum=MAX_PREFLIGHT_SOURCE_BYTES,
        )
        if package_path.size is not None and len(payload) != package_path.size:
            raise PreflightRecordError(
                f"distribution source size differs from RECORD: {relative_path}"
            )
        if not _record_digest_matches(
            payload,
            mode=file_hash.mode,
            value=file_hash.value,
        ):
            raise PreflightRecordError(
                f"distribution source hash differs from RECORD: {relative_path}"
            )
        observed_paths.add(relative_path)
        verified_files.append(
            {
                "path": relative_path,
                "byte_count": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "record_digest_algorithm": file_hash.mode,
                "record_digest_value": file_hash.value,
            }
        )

    missing = sorted(_CRITICAL_SOURCE_PATHS - observed_paths)
    if missing:
        raise PreflightRecordError(
            "critical Engine v2 sources are missing from RECORD verification: "
            + ", ".join(missing)
        )
    if _PY_TYPED not in observed_paths:
        raise PreflightRecordError(
            "Engine v2 py.typed marker was not RECORD verified"
        )
    if _engine_modules_loaded():
        raise PreflightRecordError(
            "Engine v2 package was imported during preflight verification"
        )

    projection: dict[str, object] = {
        "schema_id": PREFLIGHT_RECORD_SCHEMA_ID,
        "command_id": PREFLIGHT_COMMAND_ID,
        "distribution_name": DISTRIBUTION_NAME,
        "distribution_version": distribution.version,
        "record_source": "installed_distribution_RECORD",
        "verified_file_count": len(verified_files),
        "verified_files": verified_files,
        "critical_source_paths": sorted(_CRITICAL_SOURCE_PATHS),
        "engine_package_modules_loaded_before_verification": [],
        "engine_package_imported_before_verification": False,
        "engine_package_imported_during_verification": False,
        "record_hashes_verified": True,
        "record_signature_verified": False,
        "wheel_signature_verified": False,
        "network_fetch_performed": False,
        "scientifically_validated": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
    }
    projection["receipt_sha256"] = _sha256_document(projection)
    return projection


def _failure_document(exc: BaseException) -> dict[str, object]:
    private = (
        f"{exc.__class__.__module__}.{exc.__class__.__qualname__}: {exc}"
    ).encode("utf-8", errors="replace")
    return {
        "schema_id": PREFLIGHT_FAILURE_SCHEMA_ID,
        "status": "failure",
        "error_code": "engine_v2_preflight_failed",
        "public_message": "Engine v2 package preflight verification failed",
        "private_error_sha256": hashlib.sha256(private).hexdigest(),
        "private_error_byte_length": len(private),
        "claim_safe": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    global _ACTIVE_PREFLIGHT_RECEIPT
    try:
        _ACTIVE_PREFLIGHT_RECEIPT = verify_installed_distribution_record()
        from betelgeuze_engine_v2.cli_dispatch import main as dispatch_main

        return dispatch_main(argv)
    except SystemExit:
        raise
    except Exception as exc:
        failure = _failure_document(exc)
        sys.stderr.buffer.write(_canonical_bytes(failure) + b"\n")
        sys.stderr.buffer.flush()
        return 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DISTRIBUTION_NAME",
    "MAX_PREFLIGHT_SOURCE_BYTES",
    "PREFLIGHT_COMMAND_ID",
    "PREFLIGHT_FAILURE_SCHEMA_ID",
    "PREFLIGHT_RECORD_SCHEMA_ID",
    "PreflightRecordError",
    "main",
    "verify_installed_distribution_record",
]
