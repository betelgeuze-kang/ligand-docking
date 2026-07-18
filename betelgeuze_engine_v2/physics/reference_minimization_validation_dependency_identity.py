"""Observed byte identities for the minimization-validation runtime.

The helper imports only the standard library. It hashes the active Python
runtime, the standard library, trusted OpenSSL, and every RECORD-declared wheel
payload byte for cryptography, NumPy, and Torch. Callers compare the returned
rows with the exact rows signed into the one-run authorization.
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
import sysconfig
from typing import Iterable


REFERENCE_MINIMIZATION_VALIDATION_DEPENDENCY_IDENTITY_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_validation_dependency_identity/1.0.0"
)
REFERENCE_MINIMIZATION_VALIDATION_REQUIRED_DEPENDENCY_ARTIFACT_IDS = (
    "cryptography-distribution",
    "numpy-distribution",
    "openssl-executable",
    "python-runtime-executable",
    "python-standard-library",
    "torch-distribution",
)
REFERENCE_MINIMIZATION_VALIDATION_DEPENDENCY_MAX_FILES = 30_000
REFERENCE_MINIMIZATION_VALIDATION_DEPENDENCY_MAX_BYTES = 8 * 1024**3


class ReferenceMinimizationValidationDependencyIdentityError(RuntimeError):
    """A dependency byte identity cannot be measured without ambiguity."""


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
        raise ReferenceMinimizationValidationDependencyIdentityError(
            "dependency identity is not canonical JSON"
        ) from exc


def _require_trusted_roots(
    raw_roots: Iterable[str | os.PathLike[str]],
) -> tuple[Path, ...]:
    roots: list[Path] = []
    for raw_root in raw_roots:
        candidate = Path(raw_root)
        try:
            file_stat = candidate.lstat()
            resolved = candidate.resolve(strict=True)
        except OSError as exc:
            raise ReferenceMinimizationValidationDependencyIdentityError(
                "dependency root is unavailable"
            ) from exc
        if (
            not candidate.is_absolute()
            or candidate.is_symlink()
            or candidate != resolved
            or not stat.S_ISDIR(file_stat.st_mode)
            or file_stat.st_uid != 0
            or stat.S_IMODE(file_stat.st_mode) & 0o022
        ):
            raise ReferenceMinimizationValidationDependencyIdentityError(
                "dependency root is not root-owned read-only storage"
            )
        if resolved not in roots:
            roots.append(resolved)
    if not roots:
        raise ReferenceMinimizationValidationDependencyIdentityError(
            "dependency roots are unavailable"
        )
    return tuple(roots)


def _hash_regular_file(
    path: Path, *, allowed_roots: tuple[Path, ...]
) -> tuple[str, int]:
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise ReferenceMinimizationValidationDependencyIdentityError(
            "dependency file is unavailable"
        ) from exc
    if not any(resolved.is_relative_to(root) for root in allowed_roots):
        raise ReferenceMinimizationValidationDependencyIdentityError(
            "dependency file escaped its trusted root"
        )
    flags = os.O_RDONLY
    for flag_name in ("O_CLOEXEC", "O_NOFOLLOW"):
        if not hasattr(os, flag_name):
            raise ReferenceMinimizationValidationDependencyIdentityError(
                "secure dependency file access is unavailable"
            )
        flags |= getattr(os, flag_name)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ReferenceMinimizationValidationDependencyIdentityError(
            "dependency file cannot be opened securely"
        ) from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise ReferenceMinimizationValidationDependencyIdentityError(
                "dependency file is not a single-link regular file"
            )
        digest = hashlib.sha256()
        observed_size = 0
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            observed_size += len(chunk)
        after = os.fstat(descriptor)
    except OSError as exc:
        raise ReferenceMinimizationValidationDependencyIdentityError(
            "dependency file cannot be measured"
        ) from exc
    finally:
        os.close(descriptor)
    if observed_size != before.st_size or (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    ) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise ReferenceMinimizationValidationDependencyIdentityError(
            "dependency file changed while being measured"
        )
    return digest.hexdigest(), observed_size


def _manifest_sha256(artifact_id: str, rows: list[dict[str, object]]) -> str:
    return hashlib.sha256(
        _canonical_bytes(
            {
                "schema_id": REFERENCE_MINIMIZATION_VALIDATION_DEPENDENCY_IDENTITY_SCHEMA_ID,
                "artifact_id": artifact_id,
                "files": rows,
            }
        )
    ).hexdigest()


def _single_file_identity(
    artifact_id: str,
    path: Path,
    *,
    allowed_roots: tuple[Path, ...],
) -> str:
    digest, size = _hash_regular_file(path, allowed_roots=allowed_roots)
    return _manifest_sha256(
        artifact_id,
        [{"path": path.name, "sha256": digest, "size": size}],
    )


def _standard_library_identity(*, allowed_roots: tuple[Path, ...]) -> str:
    configured = sysconfig.get_paths().get("stdlib")
    if not isinstance(configured, str):
        raise ReferenceMinimizationValidationDependencyIdentityError(
            "Python standard-library root is unavailable"
        )
    root = Path(configured).resolve(strict=True)
    if not any(root.is_relative_to(allowed) for allowed in allowed_roots):
        raise ReferenceMinimizationValidationDependencyIdentityError(
            "Python standard library escaped trusted storage"
        )
    excluded_roots: tuple[Path, ...] = tuple(
        Path(value).resolve(strict=True)
        for key in ("purelib", "platlib")
        if isinstance((value := sysconfig.get_paths().get(key)), str)
        and Path(value).resolve(strict=True) != root
        and Path(value).resolve(strict=True).is_relative_to(root)
    )
    rows: list[dict[str, object]] = []
    total_bytes = 0
    for path in sorted(root.rglob("*")):
        resolved_path = path.resolve(strict=False)
        if any(resolved_path.is_relative_to(excluded) for excluded in excluded_roots):
            continue
        relative = path.relative_to(root)
        if "__pycache__" in relative.parts or path.suffix == ".pyc":
            continue
        try:
            file_stat = path.lstat()
        except OSError as exc:
            raise ReferenceMinimizationValidationDependencyIdentityError(
                "Python standard-library entry is unavailable"
            ) from exc
        if stat.S_ISDIR(file_stat.st_mode):
            continue
        if not stat.S_ISREG(file_stat.st_mode) or path.is_symlink():
            raise ReferenceMinimizationValidationDependencyIdentityError(
                "Python standard-library entry is not a regular file"
            )
        digest, size = _hash_regular_file(path, allowed_roots=allowed_roots)
        total_bytes += size
        rows.append({"path": relative.as_posix(), "sha256": digest, "size": size})
        if (
            len(rows) > REFERENCE_MINIMIZATION_VALIDATION_DEPENDENCY_MAX_FILES
            or total_bytes > REFERENCE_MINIMIZATION_VALIDATION_DEPENDENCY_MAX_BYTES
        ):
            raise ReferenceMinimizationValidationDependencyIdentityError(
                "Python standard-library identity exceeds its bounds"
            )
    if not rows:
        raise ReferenceMinimizationValidationDependencyIdentityError(
            "Python standard-library identity is empty"
        )
    return _manifest_sha256("python-standard-library", rows)


def _distribution_identity(
    distribution_name: str,
    expected_base_version: str,
    artifact_id: str,
    *,
    allowed_roots: tuple[Path, ...],
) -> str:
    try:
        distribution = metadata.distribution(distribution_name)
    except metadata.PackageNotFoundError as exc:
        raise ReferenceMinimizationValidationDependencyIdentityError(
            f"{distribution_name} distribution is unavailable"
        ) from exc
    observed_version = distribution.version
    if observed_version.split("+", 1)[0] != expected_base_version:
        raise ReferenceMinimizationValidationDependencyIdentityError(
            f"{distribution_name} distribution version is invalid"
        )
    rows: list[dict[str, object]] = []
    total_bytes = 0
    record_seen = False
    for package_path in sorted(distribution.files or (), key=str):
        relative = str(package_path).replace(os.sep, "/")
        if relative.endswith(".pyc") or "/__pycache__/" in f"/{relative}":
            continue
        located = Path(distribution.locate_file(package_path))
        digest, size = _hash_regular_file(located, allowed_roots=allowed_roots)
        declared_hash = package_path.hash
        if relative.endswith(".dist-info/RECORD"):
            record_seen = True
        elif declared_hash is None or declared_hash.mode != "sha256":
            raise ReferenceMinimizationValidationDependencyIdentityError(
                f"{distribution_name} RECORD has an unhashed payload row"
            )
        else:
            padding = "=" * (-len(declared_hash.value) % 4)
            expected = base64.urlsafe_b64decode(declared_hash.value + padding).hex()
            if expected != digest:
                raise ReferenceMinimizationValidationDependencyIdentityError(
                    f"{distribution_name} payload does not match RECORD"
                )
        if package_path.size is not None and package_path.size != size:
            raise ReferenceMinimizationValidationDependencyIdentityError(
                f"{distribution_name} payload size does not match RECORD"
            )
        total_bytes += size
        rows.append({"path": relative, "sha256": digest, "size": size})
        if (
            len(rows) > REFERENCE_MINIMIZATION_VALIDATION_DEPENDENCY_MAX_FILES
            or total_bytes > REFERENCE_MINIMIZATION_VALIDATION_DEPENDENCY_MAX_BYTES
        ):
            raise ReferenceMinimizationValidationDependencyIdentityError(
                f"{distribution_name} identity exceeds its bounds"
            )
    if not rows or not record_seen:
        raise ReferenceMinimizationValidationDependencyIdentityError(
            f"{distribution_name} RECORD identity is incomplete"
        )
    return hashlib.sha256(
        _canonical_bytes(
            {
                "schema_id": REFERENCE_MINIMIZATION_VALIDATION_DEPENDENCY_IDENTITY_SCHEMA_ID,
                "artifact_id": artifact_id,
                "distribution": distribution_name,
                "version": observed_version,
                "files": rows,
            }
        )
    ).hexdigest()


def observed_reference_minimization_validation_dependency_artifact_sha256_rows(
    dependency_roots: Iterable[str | os.PathLike[str]],
) -> dict[str, str]:
    """Measure the exact active dependency bytes without importing them."""

    roots = _require_trusted_roots(dependency_roots)
    python_executable = Path(sys.executable).resolve(strict=True)
    openssl_executable = Path("/usr/bin/openssl").resolve(strict=True)
    configured_stdlib = sysconfig.get_paths().get("stdlib")
    if not isinstance(configured_stdlib, str):
        raise ReferenceMinimizationValidationDependencyIdentityError(
            "Python standard-library root is unavailable"
        )
    all_roots = _require_trusted_roots(
        (
            *roots,
            python_executable.parent,
            openssl_executable.parent,
            Path(configured_stdlib).resolve(strict=True),
        )
    )
    rows = {
        "cryptography-distribution": _distribution_identity(
            "cryptography",
            "46.0.5",
            "cryptography-distribution",
            allowed_roots=all_roots,
        ),
        "numpy-distribution": _distribution_identity(
            "numpy", "1.26.4", "numpy-distribution", allowed_roots=all_roots
        ),
        "openssl-executable": _single_file_identity(
            "openssl-executable", openssl_executable, allowed_roots=all_roots
        ),
        "python-runtime-executable": _single_file_identity(
            "python-runtime-executable", python_executable, allowed_roots=all_roots
        ),
        "python-standard-library": _standard_library_identity(allowed_roots=all_roots),
        "torch-distribution": _distribution_identity(
            "torch", "2.6.0", "torch-distribution", allowed_roots=all_roots
        ),
    }
    if tuple(sorted(rows)) != (
        REFERENCE_MINIMIZATION_VALIDATION_REQUIRED_DEPENDENCY_ARTIFACT_IDS
    ):
        raise ReferenceMinimizationValidationDependencyIdentityError(
            "dependency artifact row schema drifted"
        )
    return rows


__all__ = [
    "REFERENCE_MINIMIZATION_VALIDATION_DEPENDENCY_IDENTITY_SCHEMA_ID",
    "REFERENCE_MINIMIZATION_VALIDATION_REQUIRED_DEPENDENCY_ARTIFACT_IDS",
    "ReferenceMinimizationValidationDependencyIdentityError",
    "observed_reference_minimization_validation_dependency_artifact_sha256_rows",
]
