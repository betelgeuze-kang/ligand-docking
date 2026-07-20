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
from pathlib import Path, PurePosixPath
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


def _stat_signature(file_stat: os.stat_result) -> tuple[int, ...]:
    """Return the metadata that must stay stable while trusted bytes are read."""

    return (
        int(file_stat.st_dev),
        int(file_stat.st_ino),
        int(file_stat.st_uid),
        int(file_stat.st_gid),
        int(file_stat.st_mode),
        int(file_stat.st_nlink),
        int(file_stat.st_size),
        int(file_stat.st_mtime_ns),
        int(file_stat.st_ctime_ns),
    )


def _require_trusted_directory_stat(file_stat: os.stat_result) -> None:
    if (
        not stat.S_ISDIR(file_stat.st_mode)
        or file_stat.st_uid != 0
        or stat.S_IMODE(file_stat.st_mode) & 0o022
    ):
        raise ReferenceMinimizationValidationDependencyIdentityError(
            "dependency directory is not root-owned read-only storage"
        )


def _require_trusted_regular_file_stat(file_stat: os.stat_result) -> None:
    if (
        not stat.S_ISREG(file_stat.st_mode)
        or file_stat.st_uid != 0
        or stat.S_IMODE(file_stat.st_mode) & 0o022
        or file_stat.st_nlink != 1
    ):
        raise ReferenceMinimizationValidationDependencyIdentityError(
            "dependency file is not a root-owned read-only single-link regular file"
        )


def _require_trusted_directory_ancestry(
    path: Path,
    *,
    minimum_root: Path | None = None,
) -> None:
    """Require every traversed directory to be canonical root-owned storage."""

    current = path
    if minimum_root is not None and not current.is_relative_to(minimum_root):
        raise ReferenceMinimizationValidationDependencyIdentityError(
            "dependency path escaped its trusted directory ancestry"
        )
    while True:
        try:
            file_stat = current.lstat()
        except OSError as exc:
            raise ReferenceMinimizationValidationDependencyIdentityError(
                "dependency directory ancestry is unavailable"
            ) from exc
        if current.is_symlink():
            raise ReferenceMinimizationValidationDependencyIdentityError(
                "dependency directory ancestry contains a symbolic link"
            )
        _require_trusted_directory_stat(file_stat)
        if minimum_root is not None and current == minimum_root:
            return
        parent = current.parent
        if parent == current:
            if minimum_root is not None:
                raise ReferenceMinimizationValidationDependencyIdentityError(
                    "dependency path did not reach its trusted root"
                )
            return
        current = parent


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
        ):
            raise ReferenceMinimizationValidationDependencyIdentityError(
                "dependency root is not canonical root-owned read-only storage"
            )
        _require_trusted_directory_stat(file_stat)
        _require_trusted_directory_ancestry(resolved)
        if resolved not in roots:
            roots.append(resolved)
    if not roots:
        raise ReferenceMinimizationValidationDependencyIdentityError(
            "dependency roots are unavailable"
        )
    return tuple(roots)


def _matching_trusted_root(path: Path, allowed_roots: tuple[Path, ...]) -> Path:
    matches = tuple(root for root in allowed_roots if path.is_relative_to(root))
    if not matches:
        raise ReferenceMinimizationValidationDependencyIdentityError(
            "dependency file escaped its trusted root"
        )
    return max(matches, key=lambda root: len(root.parts))


def _hash_regular_file(
    path: Path, *, allowed_roots: tuple[Path, ...]
) -> tuple[str, int]:
    try:
        resolved = path.resolve(strict=True)
        path_before = resolved.lstat()
    except OSError as exc:
        raise ReferenceMinimizationValidationDependencyIdentityError(
            "dependency file is unavailable"
        ) from exc
    trusted_root = _matching_trusted_root(resolved, allowed_roots)
    _require_trusted_directory_ancestry(resolved.parent, minimum_root=trusted_root)
    _require_trusted_regular_file_stat(path_before)

    flags = os.O_RDONLY
    for flag_name in ("O_CLOEXEC", "O_NOFOLLOW"):
        if not hasattr(os, flag_name):
            raise ReferenceMinimizationValidationDependencyIdentityError(
                "secure dependency file access is unavailable"
            )
        flags |= getattr(os, flag_name)
    try:
        descriptor = os.open(resolved, flags)
    except OSError as exc:
        raise ReferenceMinimizationValidationDependencyIdentityError(
            "dependency file cannot be opened securely"
        ) from exc
    try:
        before = os.fstat(descriptor)
        _require_trusted_regular_file_stat(before)
        if (before.st_dev, before.st_ino) != (path_before.st_dev, path_before.st_ino):
            raise ReferenceMinimizationValidationDependencyIdentityError(
                "dependency path changed before it was opened"
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
        _require_trusted_regular_file_stat(after)
    except OSError as exc:
        raise ReferenceMinimizationValidationDependencyIdentityError(
            "dependency file cannot be measured"
        ) from exc
    finally:
        os.close(descriptor)

    try:
        path_after = resolved.lstat()
    except OSError as exc:
        raise ReferenceMinimizationValidationDependencyIdentityError(
            "dependency file disappeared after measurement"
        ) from exc
    _require_trusted_regular_file_stat(path_after)
    if (
        observed_size != before.st_size
        or _stat_signature(path_before) != _stat_signature(before)
        or _stat_signature(before) != _stat_signature(after)
        or _stat_signature(after) != _stat_signature(path_after)
    ):
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
    trusted_root = _matching_trusted_root(root, allowed_roots)
    _require_trusted_directory_ancestry(root, minimum_root=trusted_root)
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
            _require_trusted_directory_stat(file_stat)
            continue
        _require_trusted_regular_file_stat(file_stat)
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


def _normalized_distribution_relative_path(package_path: object) -> str:
    """Accept canonical wheel paths, including a leading wheel-script parent prefix."""

    raw = str(package_path)
    if not raw or "\\" in raw:
        raise ReferenceMinimizationValidationDependencyIdentityError(
            "distribution RECORD path is not canonical POSIX text"
        )
    relative = PurePosixPath(raw)
    parts = relative.parts
    parent_prefix_finished = False
    for part in parts:
        if part == "..":
            if parent_prefix_finished:
                raise ReferenceMinimizationValidationDependencyIdentityError(
                    "distribution RECORD parent traversal is not a leading prefix"
                )
        else:
            parent_prefix_finished = True
    if (
        relative.is_absolute()
        or not parts
        or any(part in {"", "."} for part in parts)
        or all(part == ".." for part in parts)
        or relative.as_posix() != raw
    ):
        raise ReferenceMinimizationValidationDependencyIdentityError(
            "distribution RECORD path is not canonical"
        )
    return raw


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
    try:
        distribution_root = Path(distribution.locate_file("")).resolve(strict=True)
    except OSError as exc:
        raise ReferenceMinimizationValidationDependencyIdentityError(
            f"{distribution_name} installation root is unavailable"
        ) from exc
    trusted_root = _matching_trusted_root(distribution_root, allowed_roots)
    _require_trusted_directory_ancestry(
        distribution_root,
        minimum_root=trusted_root,
    )

    rows: list[dict[str, object]] = []
    total_bytes = 0
    record_seen = False
    seen_paths: set[str] = set()
    for package_path in sorted(distribution.files or (), key=str):
        relative = _normalized_distribution_relative_path(package_path)
        if relative in seen_paths:
            raise ReferenceMinimizationValidationDependencyIdentityError(
                f"{distribution_name} RECORD contains a duplicate normalized path"
            )
        seen_paths.add(relative)
        if relative.endswith(".pyc") or "/__pycache__/" in f"/{relative}":
            continue
        try:
            located = Path(distribution.locate_file(package_path)).resolve(strict=True)
        except OSError as exc:
            raise ReferenceMinimizationValidationDependencyIdentityError(
                f"{distribution_name} RECORD payload is unavailable"
            ) from exc
        _matching_trusted_root(located, allowed_roots)
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
            try:
                expected = base64.urlsafe_b64decode(
                    declared_hash.value + padding
                ).hex()
            except (ValueError, TypeError) as exc:
                raise ReferenceMinimizationValidationDependencyIdentityError(
                    f"{distribution_name} RECORD hash is malformed"
                ) from exc
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
