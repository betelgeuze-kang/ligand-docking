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
_SECURE_PATH_PRIMITIVES_AVAILABLE = (
    os.name == "posix"
    and all(hasattr(os, name) for name in ("O_CLOEXEC", "O_DIRECTORY", "O_NOFOLLOW"))
    and os.open in os.supports_dir_fd
    and os.stat in os.supports_dir_fd
    and os.stat in os.supports_follow_symlinks
)


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


def _require_secure_path_primitives() -> tuple[int, int]:
    required_flags = ("O_CLOEXEC", "O_DIRECTORY", "O_NOFOLLOW")
    if (
        not _SECURE_PATH_PRIMITIVES_AVAILABLE
        or any(not hasattr(os, name) for name in required_flags)
    ):
        raise ReferenceMinimizationValidationDependencyIdentityError(
            "secure dependency path traversal is unavailable"
        )
    directory_flags = (
        os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW
    )
    file_flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    return directory_flags, file_flags


def _canonical_absolute_path(
    raw_path: str | os.PathLike[str],
    *,
    name: str,
    require_normalized: bool = True,
) -> Path:
    try:
        raw = os.fspath(raw_path)
    except TypeError as exc:
        raise ReferenceMinimizationValidationDependencyIdentityError(
            f"{name} is invalid"
        ) from exc
    if (
        not isinstance(raw, str)
        or not raw
        or "\x00" in raw
        or not os.path.isabs(raw)
    ):
        raise ReferenceMinimizationValidationDependencyIdentityError(
            f"{name} must be an absolute lexical path"
        )
    normalized = os.path.normpath(raw)
    if require_normalized and normalized != raw:
        raise ReferenceMinimizationValidationDependencyIdentityError(
            f"{name} is not lexically canonical"
        )
    candidate = Path(normalized)
    if any(part in {"", ".", ".."} for part in candidate.parts[1:]):
        raise ReferenceMinimizationValidationDependencyIdentityError(
            f"{name} is not lexically canonical"
        )
    return candidate


def _lstat_at(directory_fd: int, component: str) -> os.stat_result:
    return os.stat(component, dir_fd=directory_fd, follow_symlinks=False)


def _open_trusted_child_directory(parent_fd: int, component: str) -> int:
    directory_flags, _ = _require_secure_path_primitives()
    path_before = _lstat_at(parent_fd, component)
    _require_trusted_directory_stat(path_before)
    next_fd = -1
    try:
        next_fd = os.open(component, directory_flags, dir_fd=parent_fd)
        opened = os.fstat(next_fd)
        path_after = _lstat_at(parent_fd, component)
        _require_trusted_directory_stat(opened)
        _require_trusted_directory_stat(path_after)
        if not (
            _stat_signature(path_before)
            == _stat_signature(opened)
            == _stat_signature(path_after)
        ):
            raise ReferenceMinimizationValidationDependencyIdentityError(
                "dependency directory changed while it was opened"
            )
        result = next_fd
        next_fd = -1
        return result
    finally:
        if next_fd >= 0:
            os.close(next_fd)


def _open_absolute_trusted_directory(path: Path) -> int:
    directory_flags, _ = _require_secure_path_primitives()
    lexical = _canonical_absolute_path(
        path, name="dependency directory", require_normalized=True
    )
    components = lexical.parts[1:]
    current_fd = -1
    try:
        current_fd = os.open(os.sep, directory_flags)
        root_stat = os.fstat(current_fd)
        _require_trusted_directory_stat(root_stat)
        for component in components:
            next_fd = _open_trusted_child_directory(current_fd, component)
            os.close(current_fd)
            current_fd = next_fd
        result = current_fd
        current_fd = -1
        return result
    except ReferenceMinimizationValidationDependencyIdentityError:
        raise
    except OSError as exc:
        raise ReferenceMinimizationValidationDependencyIdentityError(
            "dependency directory cannot be opened securely"
        ) from exc
    finally:
        if current_fd >= 0:
            os.close(current_fd)


def _open_absolute_trusted_regular_file(
    path: Path,
) -> tuple[int, os.stat_result]:
    _, file_flags = _require_secure_path_primitives()
    lexical = _canonical_absolute_path(
        path, name="dependency file", require_normalized=True
    )
    if lexical.parent == lexical:
        raise ReferenceMinimizationValidationDependencyIdentityError(
            "dependency file path is invalid"
        )
    parent_fd = _open_absolute_trusted_directory(lexical.parent)
    file_fd = -1
    try:
        path_before = _lstat_at(parent_fd, lexical.name)
        _require_trusted_regular_file_stat(path_before)
        file_fd = os.open(lexical.name, file_flags, dir_fd=parent_fd)
        opened = os.fstat(file_fd)
        path_after = _lstat_at(parent_fd, lexical.name)
        _require_trusted_regular_file_stat(opened)
        _require_trusted_regular_file_stat(path_after)
        if not (
            _stat_signature(path_before)
            == _stat_signature(opened)
            == _stat_signature(path_after)
        ):
            raise ReferenceMinimizationValidationDependencyIdentityError(
                "dependency path changed while it was opened"
            )
        result = file_fd
        file_fd = -1
        return result, opened
    except ReferenceMinimizationValidationDependencyIdentityError:
        raise
    except OSError as exc:
        raise ReferenceMinimizationValidationDependencyIdentityError(
            "dependency file cannot be opened securely"
        ) from exc
    finally:
        if file_fd >= 0:
            os.close(file_fd)
        os.close(parent_fd)


def _require_trusted_directory_ancestry(
    path: Path,
    *,
    minimum_root: Path | None = None,
) -> None:
    """Securely traverse a lexical directory path without following symlinks."""

    lexical = _canonical_absolute_path(
        path, name="dependency directory", require_normalized=True
    )
    if minimum_root is not None:
        root = _canonical_absolute_path(
            minimum_root, name="dependency root", require_normalized=True
        )
        if not lexical.is_relative_to(root):
            raise ReferenceMinimizationValidationDependencyIdentityError(
                "dependency path escaped its trusted directory ancestry"
            )
    descriptor = _open_absolute_trusted_directory(lexical)
    os.close(descriptor)


def _require_trusted_roots(
    raw_roots: Iterable[str | os.PathLike[str]],
) -> tuple[Path, ...]:
    roots: list[Path] = []
    for raw_root in raw_roots:
        candidate = _canonical_absolute_path(
            raw_root, name="dependency root", require_normalized=True
        )
        descriptor = _open_absolute_trusted_directory(candidate)
        os.close(descriptor)
        if candidate not in roots:
            roots.append(candidate)
    if not roots:
        raise ReferenceMinimizationValidationDependencyIdentityError(
            "dependency roots are unavailable"
        )
    return tuple(roots)


def _matching_trusted_root(path: Path, allowed_roots: tuple[Path, ...]) -> Path:
    lexical = _canonical_absolute_path(
        path, name="dependency path", require_normalized=True
    )
    matches = tuple(root for root in allowed_roots if lexical.is_relative_to(root))
    if not matches:
        raise ReferenceMinimizationValidationDependencyIdentityError(
            "dependency file escaped its trusted root"
        )
    return max(matches, key=lambda root: len(root.parts))


def _hash_regular_file(
    path: Path,
    *,
    allowed_roots: tuple[Path, ...],
    seen_file_identities: set[tuple[int, int]] | None = None,
) -> tuple[str, int]:
    lexical = _canonical_absolute_path(
        path, name="dependency file", require_normalized=True
    )
    _matching_trusted_root(lexical, allowed_roots)
    descriptor, before = _open_absolute_trusted_regular_file(lexical)
    file_identity = (int(before.st_dev), int(before.st_ino))
    if seen_file_identities is not None and file_identity in seen_file_identities:
        os.close(descriptor)
        raise ReferenceMinimizationValidationDependencyIdentityError(
            "dependency manifest aliases one inode through multiple paths"
        )
    try:
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

    verification_fd, path_after = _open_absolute_trusted_regular_file(lexical)
    os.close(verification_fd)
    if (
        observed_size != before.st_size
        or _stat_signature(before) != _stat_signature(after)
        or _stat_signature(after) != _stat_signature(path_after)
    ):
        raise ReferenceMinimizationValidationDependencyIdentityError(
            "dependency file changed while being measured"
        )
    if seen_file_identities is not None:
        seen_file_identities.add(file_identity)
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
    root = _canonical_absolute_path(
        configured,
        name="Python standard-library root",
        require_normalized=True,
    )
    trusted_root = _matching_trusted_root(root, allowed_roots)
    _require_trusted_directory_ancestry(root, minimum_root=trusted_root)
    excluded_rows: list[Path] = []
    for key in ("purelib", "platlib"):
        value = sysconfig.get_paths().get(key)
        if not isinstance(value, str):
            continue
        candidate = _canonical_absolute_path(
            value,
            name=f"Python {key} root",
            require_normalized=True,
        )
        if candidate != root and candidate.is_relative_to(root):
            excluded_rows.append(candidate)
    excluded_roots = tuple(excluded_rows)
    rows: list[dict[str, object]] = []
    total_bytes = 0
    for path in sorted(root.rglob("*")):
        lexical_path = _canonical_absolute_path(
            path,
            name="Python standard-library entry",
            require_normalized=True,
        )
        if any(lexical_path.is_relative_to(excluded) for excluded in excluded_roots):
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


def _decode_canonical_record_sha256(value: object) -> str:
    """Decode one canonical, unpadded urlsafe-base64 SHA-256 digest."""

    if not isinstance(value, str) or not value or "=" in value:
        raise ReferenceMinimizationValidationDependencyIdentityError(
            "distribution RECORD hash is malformed"
        )
    try:
        encoded = value.encode("ascii")
        decoded = base64.b64decode(
            encoded + b"=",
            altchars=b"-_",
            validate=True,
        )
    except (UnicodeEncodeError, ValueError) as exc:
        raise ReferenceMinimizationValidationDependencyIdentityError(
            "distribution RECORD hash is malformed"
        ) from exc
    if (
        len(encoded) != 43
        or len(decoded) != hashlib.sha256().digest_size
        or base64.urlsafe_b64encode(decoded).rstrip(b"=") != encoded
    ):
        raise ReferenceMinimizationValidationDependencyIdentityError(
            "distribution RECORD hash is malformed"
        )
    return decoded.hex()


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
        distribution_root = _canonical_absolute_path(
            distribution.locate_file(""),
            name=f"{distribution_name} installation root",
            require_normalized=True,
        )
    except (OSError, TypeError) as exc:
        raise ReferenceMinimizationValidationDependencyIdentityError(
            f"{distribution_name} installation root is unavailable"
        ) from exc
    trusted_root = _matching_trusted_root(distribution_root, allowed_roots)
    _require_trusted_directory_ancestry(
        distribution_root,
        minimum_root=trusted_root,
    )
    configured_scripts = sysconfig.get_paths().get("scripts")
    if not isinstance(configured_scripts, str):
        raise ReferenceMinimizationValidationDependencyIdentityError(
            "Python scripts root is unavailable"
        )
    scripts_root = _canonical_absolute_path(
        configured_scripts,
        name="Python scripts root",
        require_normalized=True,
    )
    scripts_trusted_root = _matching_trusted_root(scripts_root, allowed_roots)
    _require_trusted_directory_ancestry(
        scripts_root,
        minimum_root=scripts_trusted_root,
    )

    rows: list[dict[str, object]] = []
    total_bytes = 0
    record_seen = False
    seen_paths: set[str] = set()
    seen_file_identities: set[tuple[int, int]] = set()
    for package_path in sorted(distribution.files or (), key=str):
        relative = _normalized_distribution_relative_path(package_path)
        if relative in seen_paths:
            raise ReferenceMinimizationValidationDependencyIdentityError(
                f"{distribution_name} RECORD contains a duplicate normalized path"
            )
        seen_paths.add(relative)
        if relative.endswith(".pyc") or "/__pycache__/" in f"/{relative}":
            continue
        relative_parts = PurePosixPath(relative).parts
        leading_parent_count = 0
        for part in relative_parts:
            if part != "..":
                break
            leading_parent_count += 1
        expected_located = _canonical_absolute_path(
            os.path.normpath(
                os.path.join(distribution_root, *relative_parts)
            ),
            name=f"{distribution_name} RECORD target",
            require_normalized=True,
        )
        try:
            located = _canonical_absolute_path(
                os.path.normpath(os.fspath(distribution.locate_file(package_path))),
                name=f"{distribution_name} RECORD payload",
                require_normalized=True,
            )
        except (OSError, TypeError) as exc:
            raise ReferenceMinimizationValidationDependencyIdentityError(
                f"{distribution_name} RECORD payload is unavailable"
            ) from exc
        if located != expected_located:
            raise ReferenceMinimizationValidationDependencyIdentityError(
                f"{distribution_name} RECORD target is cross-wired"
            )
        if leading_parent_count:
            try:
                scripts_relative = located.relative_to(scripts_root)
            except ValueError as exc:
                raise ReferenceMinimizationValidationDependencyIdentityError(
                    f"{distribution_name} wheel script escaped the scripts root"
                ) from exc
            if len(scripts_relative.parts) != 1:
                raise ReferenceMinimizationValidationDependencyIdentityError(
                    f"{distribution_name} wheel script is not a direct scripts-root file"
                )
        elif not located.is_relative_to(distribution_root):
            raise ReferenceMinimizationValidationDependencyIdentityError(
                f"{distribution_name} RECORD payload escaped the installation root"
            )
        _matching_trusted_root(located, allowed_roots)
        digest, size = _hash_regular_file(
            located,
            allowed_roots=allowed_roots,
            seen_file_identities=seen_file_identities,
        )
        declared_hash = package_path.hash
        if relative.endswith(".dist-info/RECORD"):
            record_seen = True
        elif declared_hash is None or declared_hash.mode != "sha256":
            raise ReferenceMinimizationValidationDependencyIdentityError(
                f"{distribution_name} RECORD has an unhashed payload row"
            )
        else:
            expected = _decode_canonical_record_sha256(declared_hash.value)
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

    dependency_root_rows = tuple(dependency_roots)
    actual_python_executable = os.path.realpath("/proc/self/exe")
    if not os.path.isabs(actual_python_executable):
        actual_python_executable = os.path.realpath(sys.executable)
    python_executable = _canonical_absolute_path(
        actual_python_executable,
        name="Python runtime executable",
        require_normalized=True,
    )
    openssl_executable = _canonical_absolute_path(
        "/usr/bin/openssl",
        name="OpenSSL executable",
        require_normalized=True,
    )
    configured_stdlib = sysconfig.get_paths().get("stdlib")
    if not isinstance(configured_stdlib, str):
        raise ReferenceMinimizationValidationDependencyIdentityError(
            "Python standard-library root is unavailable"
        )
    configured_scripts = sysconfig.get_paths().get("scripts")
    if not isinstance(configured_scripts, str):
        raise ReferenceMinimizationValidationDependencyIdentityError(
            "Python scripts root is unavailable"
        )
    all_roots = _require_trusted_roots(
        (
            *dependency_root_rows,
            python_executable.parent,
            openssl_executable.parent,
            _canonical_absolute_path(
                configured_stdlib,
                name="Python standard-library root",
                require_normalized=True,
            ),
            _canonical_absolute_path(
                configured_scripts,
                name="Python scripts root",
                require_normalized=True,
            ),
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
