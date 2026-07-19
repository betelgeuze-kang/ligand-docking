"""Observed byte identities for the reference-validation runtime.

The helper imports only the standard library. It hashes the active Python
runtime, the standard library, trusted OpenSSL, and every RECORD-declared wheel
payload byte for cryptography, NumPy, and Torch. Callers compare the returned
rows with the exact rows signed into the one-run authorization.
"""

from __future__ import annotations

import base64
import binascii
import csv
import hashlib
from importlib import metadata, util
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import sysconfig
import time
from typing import Iterable


REFERENCE_VALIDATION_DEPENDENCY_IDENTITY_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_validation_dependency_identity/1.1.0"
)
REFERENCE_VALIDATION_DEPENDENCY_MANIFEST_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_validation_dependency_manifest/1.0.0"
)
REFERENCE_VALIDATION_REQUIRED_DEPENDENCY_ARTIFACT_IDS = (
    "cryptography-distribution",
    "numpy-distribution",
    "openssl-executable",
    "python-runtime-executable",
    "python-standard-library",
    "torch-distribution",
)
REFERENCE_VALIDATION_DEPENDENCY_MAX_FILES = 30_000
REFERENCE_VALIDATION_DEPENDENCY_MAX_BYTES = 8 * 1024**3
REFERENCE_VALIDATION_DEPENDENCY_MAX_ENTRIES = 60_000
REFERENCE_VALIDATION_DEPENDENCY_MAX_PATH_BYTES = 4_096
REFERENCE_VALIDATION_DEPENDENCY_RECORD_MAX_BYTES = 16 * 1024**2
REFERENCE_VALIDATION_DEPENDENCY_RECORD_MAX_LINE_BYTES = 8_192
REFERENCE_VALIDATION_DEPENDENCY_TOTAL_MAX_FILES = 60_000
REFERENCE_VALIDATION_DEPENDENCY_TOTAL_MAX_BYTES = 16 * 1024**3
REFERENCE_VALIDATION_DEPENDENCY_TOTAL_MAX_ENTRIES = 120_000
REFERENCE_VALIDATION_DEPENDENCY_PREFLIGHT_MAX_WALL_SECONDS = 120.0


class ReferenceValidationDependencyIdentityError(RuntimeError):
    """A dependency byte identity cannot be measured without ambiguity."""


class _ScanBudget:
    """One monotonic deadline and aggregate byte/file budget for a full scan."""

    __slots__ = ("deadline", "entries", "files", "bytes")

    def __init__(self, deadline: float) -> None:
        if (
            type(deadline) is not float
            or deadline != deadline
            or deadline in {float("inf"), float("-inf")}
        ):
            raise ReferenceValidationDependencyIdentityError(
                "dependency preflight deadline is invalid"
            )
        self.deadline = deadline
        self.entries = 0
        self.files = 0
        self.bytes = 0
        self.checkpoint()

    def checkpoint(self) -> None:
        if time.monotonic() >= self.deadline:
            raise ReferenceValidationDependencyIdentityError(
                "dependency preflight deadline expired"
            )

    def start_entry(self) -> None:
        self.checkpoint()
        self.entries += 1
        if self.entries > REFERENCE_VALIDATION_DEPENDENCY_TOTAL_MAX_ENTRIES:
            raise ReferenceValidationDependencyIdentityError(
                "dependency identity exceeds its aggregate entry bound"
            )

    def start_file(self, size: int) -> None:
        self.checkpoint()
        if (
            type(size) is not int
            or size < 0
            or size > REFERENCE_VALIDATION_DEPENDENCY_TOTAL_MAX_BYTES - self.bytes
        ):
            raise ReferenceValidationDependencyIdentityError(
                "dependency file exceeds its pre-read aggregate byte bound"
            )
        self.files += 1
        if self.files > REFERENCE_VALIDATION_DEPENDENCY_TOTAL_MAX_FILES:
            raise ReferenceValidationDependencyIdentityError(
                "dependency identity exceeds its aggregate file bound"
            )

    def add_bytes(self, count: int) -> None:
        self.checkpoint()
        self.bytes += count
        if self.bytes > REFERENCE_VALIDATION_DEPENDENCY_TOTAL_MAX_BYTES:
            raise ReferenceValidationDependencyIdentityError(
                "dependency identity exceeds its aggregate byte bound"
            )


def _require_root_owned_read_only_directory_chain(path: Path) -> Path:
    if not path.is_absolute():
        raise ReferenceValidationDependencyIdentityError(
            "dependency directory is not absolute"
        )
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise ReferenceValidationDependencyIdentityError(
            "dependency directory is unavailable"
        ) from exc
    if resolved != path:
        raise ReferenceValidationDependencyIdentityError(
            "dependency directory path is not canonical"
        )
    current = resolved
    while True:
        try:
            file_stat = current.lstat()
        except OSError as exc:
            raise ReferenceValidationDependencyIdentityError(
                "dependency directory chain is unavailable"
            ) from exc
        if (
            current.is_symlink()
            or not stat.S_ISDIR(file_stat.st_mode)
            or file_stat.st_uid != 0
            or stat.S_IMODE(file_stat.st_mode) & 0o022
        ):
            raise ReferenceValidationDependencyIdentityError(
                "dependency directory chain is not root-owned read-only storage"
            )
        parent = current.parent
        if parent == current:
            return resolved
        current = parent


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
        raise ReferenceValidationDependencyIdentityError(
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
            raise ReferenceValidationDependencyIdentityError(
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
            raise ReferenceValidationDependencyIdentityError(
                "dependency root is not root-owned read-only storage"
            )
        _require_root_owned_read_only_directory_chain(resolved)
        if resolved not in roots:
            roots.append(resolved)
    if not roots:
        raise ReferenceValidationDependencyIdentityError(
            "dependency roots are unavailable"
        )
    return tuple(roots)


def _trusted_install_scheme_roots() -> tuple[tuple[str, Path], ...]:
    configured = sysconfig.get_paths()
    roots: list[tuple[str, Path]] = []
    for scheme in ("purelib", "platlib", "scripts", "data"):
        raw_path = configured.get(scheme)
        if not isinstance(raw_path, str):
            continue
        candidate = Path(raw_path)
        try:
            resolved = candidate.resolve(strict=True)
        except OSError:
            continue
        _require_root_owned_read_only_directory_chain(resolved)
        if not any(existing == resolved for _, existing in roots):
            roots.append((scheme, resolved))
    available = {scheme for scheme, _ in roots}
    if not {"purelib", "scripts", "data"}.issubset(available) and not {
        "platlib",
        "scripts",
        "data",
    }.issubset(available):
        raise ReferenceValidationDependencyIdentityError(
            "Python install scheme roots are incomplete"
        )
    return tuple(roots)


def _normalized_record_payload_path(
    distribution_name: str,
    raw_record_path: str,
    resolved_path: Path,
    *,
    distribution_root: Path,
    install_scheme_roots: tuple[tuple[str, Path], ...],
) -> str:
    if resolved_path.is_relative_to(distribution_root):
        relative = resolved_path.relative_to(distribution_root).as_posix()
        if not relative:
            raise ReferenceValidationDependencyIdentityError(
                f"{distribution_name} RECORD payload path is invalid"
            )
        return relative
    matches = sorted(
        (
            (scheme, root)
            for scheme, root in install_scheme_roots
            if resolved_path.is_relative_to(root)
        ),
        key=lambda row: (-len(row[1].parts), row[0]),
    )
    if not matches:
        raise ReferenceValidationDependencyIdentityError(
            f"{distribution_name} RECORD payload escaped its install scheme"
        )
    scheme, root = matches[0]
    relative = resolved_path.relative_to(root).as_posix()
    if not relative or relative.startswith("../"):
        raise ReferenceValidationDependencyIdentityError(
            f"{distribution_name} RECORD payload path is invalid"
        )
    return f"{scheme}:{relative}"


def _hash_regular_file(
    path: Path,
    *,
    allowed_roots: tuple[Path, ...],
    budget: _ScanBudget,
    maximum_bytes: int = REFERENCE_VALIDATION_DEPENDENCY_MAX_BYTES,
) -> tuple[str, int]:
    if type(maximum_bytes) is not int or maximum_bytes < 0:
        raise ReferenceValidationDependencyIdentityError(
            "dependency file byte bound is invalid"
        )
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise ReferenceValidationDependencyIdentityError(
            "dependency file is unavailable"
        ) from exc
    matching_roots = tuple(
        root for root in allowed_roots if resolved.is_relative_to(root)
    )
    if not matching_roots:
        raise ReferenceValidationDependencyIdentityError(
            "dependency file escaped its trusted root"
        )
    if not path.is_absolute() or path.is_symlink() or path.absolute() != resolved:
        raise ReferenceValidationDependencyIdentityError(
            "dependency file path is not canonical"
        )
    _require_root_owned_read_only_directory_chain(resolved.parent)
    flags = os.O_RDONLY
    for flag_name in ("O_CLOEXEC", "O_NOFOLLOW"):
        if not hasattr(os, flag_name):
            raise ReferenceValidationDependencyIdentityError(
                "secure dependency file access is unavailable"
            )
        flags |= getattr(os, flag_name)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ReferenceValidationDependencyIdentityError(
            "dependency file cannot be opened securely"
        ) from exc
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != 0
            or stat.S_IMODE(before.st_mode) & 0o022
            or before.st_nlink != 1
        ):
            raise ReferenceValidationDependencyIdentityError(
                "dependency file is not a root-owned read-only single-link regular file"
            )
        if before.st_size > maximum_bytes:
            raise ReferenceValidationDependencyIdentityError(
                "dependency file exceeds its pre-read artifact byte bound"
            )
        budget.start_file(before.st_size)
        digest = hashlib.sha256()
        observed_size = 0
        while True:
            budget.checkpoint()
            chunk = os.read(
                descriptor,
                min(1024 * 1024, before.st_size + 1 - observed_size),
            )
            if not chunk:
                break
            observed_size += len(chunk)
            if observed_size > before.st_size:
                raise ReferenceValidationDependencyIdentityError(
                    "dependency file grew while being measured"
                )
            digest.update(chunk)
            budget.add_bytes(len(chunk))
        after = os.fstat(descriptor)
    except OSError as exc:
        raise ReferenceValidationDependencyIdentityError(
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
        raise ReferenceValidationDependencyIdentityError(
            "dependency file changed while being measured"
        )
    return digest.hexdigest(), observed_size


def _bounded_tree_entries(
    root: Path,
    *,
    budget: _ScanBudget,
    excluded_roots: tuple[Path, ...] = (),
) -> Iterable[tuple[Path, str, os.stat_result]]:
    """Yield a tree without allowing an API to materialize it before bounds."""

    pending: list[tuple[Path, str]] = [(root, "")]
    local_entries = 0
    while pending:
        budget.checkpoint()
        directory, relative_directory = pending.pop()
        try:
            with os.scandir(directory) as stream:
                children: list[tuple[str, Path, str]] = []
                for entry in stream:
                    budget.start_entry()
                    local_entries += 1
                    if local_entries > REFERENCE_VALIDATION_DEPENDENCY_MAX_ENTRIES:
                        raise ReferenceValidationDependencyIdentityError(
                            "dependency tree exceeds its entry bound"
                        )
                    relative = PurePosixPath(relative_directory, entry.name).as_posix()
                    try:
                        path_bytes = relative.encode("utf-8")
                    except UnicodeError as exc:
                        raise ReferenceValidationDependencyIdentityError(
                            "dependency tree path is not canonical UTF-8"
                        ) from exc
                    if (
                        not relative
                        or len(path_bytes)
                        > REFERENCE_VALIDATION_DEPENDENCY_MAX_PATH_BYTES
                    ):
                        raise ReferenceValidationDependencyIdentityError(
                            "dependency tree path exceeds its bound"
                        )
                    path = Path(entry.path)
                    children.append((entry.name, path, relative))
        except OSError as exc:
            raise ReferenceValidationDependencyIdentityError(
                "dependency tree cannot be enumerated"
            ) from exc
        child_directories: list[tuple[Path, str]] = []
        for _, path, relative in sorted(children, key=lambda row: row[0]):
            budget.checkpoint()
            if any(
                path == excluded or path.is_relative_to(excluded)
                for excluded in excluded_roots
            ):
                continue
            try:
                file_stat = path.lstat()
            except OSError as exc:
                raise ReferenceValidationDependencyIdentityError(
                    "dependency tree entry is unavailable"
                ) from exc
            yield path, relative, file_stat
            if stat.S_ISDIR(file_stat.st_mode) and not path.is_symlink():
                child_directories.append((path, relative))
        pending.extend(reversed(child_directories))


def _require_manifest_file_rows(
    rows: object,
) -> tuple[int, int]:
    if (
        not isinstance(rows, list)
        or not rows
        or len(rows) > REFERENCE_VALIDATION_DEPENDENCY_MAX_FILES
    ):
        raise ReferenceValidationDependencyIdentityError(
            "dependency manifest files are invalid"
        )
    previous_path = ""
    total_bytes = 0
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"path", "sha256", "size"}:
            raise ReferenceValidationDependencyIdentityError(
                "dependency manifest file row is invalid"
            )
        path = row.get("path")
        digest = row.get("sha256")
        size = row.get("size")
        try:
            path_bytes = path.encode("utf-8") if isinstance(path, str) else b""
        except UnicodeError as exc:
            raise ReferenceValidationDependencyIdentityError(
                "dependency manifest file row is invalid"
            ) from exc
        if (
            not isinstance(path, str)
            or not path
            or path <= previous_path
            or "\\" in path
            or any(ord(character) < 0x20 for character in path)
            or len(path_bytes) > REFERENCE_VALIDATION_DEPENDENCY_MAX_PATH_BYTES
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or type(size) is not int
            or size < 0
            or size > REFERENCE_VALIDATION_DEPENDENCY_MAX_BYTES
        ):
            raise ReferenceValidationDependencyIdentityError(
                "dependency manifest file row is invalid"
            )
        previous_path = path
        total_bytes += size
        if total_bytes > REFERENCE_VALIDATION_DEPENDENCY_MAX_BYTES:
            raise ReferenceValidationDependencyIdentityError(
                "dependency manifest files exceed their byte bound"
            )
    return len(rows), total_bytes


def _manifest_sha256(artifact_id: str, rows: list[dict[str, object]]) -> str:
    return hashlib.sha256(
        _canonical_bytes(
            {
                "schema_id": REFERENCE_VALIDATION_DEPENDENCY_IDENTITY_SCHEMA_ID,
                "artifact_id": artifact_id,
                "files": rows,
            }
        )
    ).hexdigest()


def _artifact_observation(
    artifact_id: str,
    identity_fields: dict[str, object],
) -> dict[str, object]:
    identity = {
        "schema_id": REFERENCE_VALIDATION_DEPENDENCY_IDENTITY_SCHEMA_ID,
        "artifact_id": artifact_id,
        **identity_fields,
    }
    return {
        "artifact_id": artifact_id,
        "sha256": hashlib.sha256(_canonical_bytes(identity)).hexdigest(),
        "identity": identity,
    }


def _single_file_identity(
    artifact_id: str,
    path: Path,
    *,
    allowed_roots: tuple[Path, ...],
    budget: _ScanBudget,
) -> dict[str, object]:
    digest, size = _hash_regular_file(
        path,
        allowed_roots=allowed_roots,
        budget=budget,
    )
    files = [{"path": path.name, "sha256": digest, "size": size}]
    if (
        _manifest_sha256(artifact_id, files)
        != _artifact_observation(
            artifact_id,
            {"files": files},
        )["sha256"]
    ):
        raise ReferenceValidationDependencyIdentityError(
            "single-file dependency manifest construction drifted"
        )
    return _artifact_observation(artifact_id, {"files": files})


def _standard_library_identity(
    *,
    allowed_roots: tuple[Path, ...],
    budget: _ScanBudget,
) -> dict[str, object]:
    configured = sysconfig.get_paths().get("stdlib")
    if not isinstance(configured, str):
        raise ReferenceValidationDependencyIdentityError(
            "Python standard-library root is unavailable"
        )
    root = Path(configured).resolve(strict=True)
    if not any(root.is_relative_to(allowed) for allowed in allowed_roots):
        raise ReferenceValidationDependencyIdentityError(
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
    for path, relative, file_stat in _bounded_tree_entries(
        root,
        budget=budget,
        excluded_roots=excluded_roots,
    ):
        relative_path = PurePosixPath(relative)
        if "__pycache__" in relative_path.parts or path.suffix == ".pyc":
            raise ReferenceValidationDependencyIdentityError(
                "Python standard-library identity contains bytecode cache payload"
            )
        if stat.S_ISDIR(file_stat.st_mode):
            continue
        if not stat.S_ISREG(file_stat.st_mode) or path.is_symlink():
            raise ReferenceValidationDependencyIdentityError(
                "Python standard-library entry is not a regular file"
            )
        digest, size = _hash_regular_file(
            path,
            allowed_roots=allowed_roots,
            budget=budget,
            maximum_bytes=REFERENCE_VALIDATION_DEPENDENCY_MAX_BYTES - total_bytes,
        )
        total_bytes += size
        rows.append({"path": relative, "sha256": digest, "size": size})
        if (
            len(rows) > REFERENCE_VALIDATION_DEPENDENCY_MAX_FILES
            or total_bytes > REFERENCE_VALIDATION_DEPENDENCY_MAX_BYTES
        ):
            raise ReferenceValidationDependencyIdentityError(
                "Python standard-library identity exceeds its bounds"
            )
    if not rows:
        raise ReferenceValidationDependencyIdentityError(
            "Python standard-library identity is empty"
        )
    artifact_id = "python-standard-library"
    rows.sort(key=lambda row: str(row["path"]))
    observation = _artifact_observation(artifact_id, {"files": rows})
    if observation["sha256"] != _manifest_sha256(artifact_id, rows):
        raise ReferenceValidationDependencyIdentityError(
            "standard-library dependency manifest construction drifted"
        )
    return observation


def _distribution_import_binding(
    distribution_name: str,
    import_package_name: str,
    *,
    record_paths: dict[Path, str],
) -> dict[str, str]:
    try:
        spec = util.find_spec(import_package_name)
    except (ImportError, AttributeError, ValueError) as exc:
        raise ReferenceValidationDependencyIdentityError(
            f"{distribution_name} import target is unavailable"
        ) from exc
    if (
        spec is None
        or not isinstance(spec.origin, str)
        or spec.submodule_search_locations is None
    ):
        raise ReferenceValidationDependencyIdentityError(
            f"{distribution_name} import target is not a regular package"
        )
    origin = Path(spec.origin)
    try:
        resolved_origin = origin.resolve(strict=True)
        search_locations = tuple(
            Path(location).resolve(strict=True)
            for location in spec.submodule_search_locations
        )
    except OSError as exc:
        raise ReferenceValidationDependencyIdentityError(
            f"{distribution_name} import target is unavailable"
        ) from exc
    if (
        not origin.is_absolute()
        or origin.is_symlink()
        or origin.absolute() != resolved_origin
        or search_locations != (resolved_origin.parent,)
    ):
        raise ReferenceValidationDependencyIdentityError(
            f"{distribution_name} import target is not canonical"
        )
    record_path = record_paths.get(resolved_origin)
    if record_path is None:
        raise ReferenceValidationDependencyIdentityError(
            f"{distribution_name} active import is outside its measured RECORD"
        )
    return {
        "import_package": import_package_name,
        "import_origin_record_path": record_path,
    }


def _require_closed_distribution_namespace(
    distribution_name: str,
    package_root: Path,
    *,
    record_paths: dict[Path, str],
    budget: _ScanBudget,
) -> None:
    for path, relative, file_stat in _bounded_tree_entries(
        package_root,
        budget=budget,
    ):
        relative_path = PurePosixPath(relative)
        if stat.S_ISDIR(file_stat.st_mode):
            if (
                path.name == "__pycache__"
                or file_stat.st_uid != 0
                or stat.S_IMODE(file_stat.st_mode) & 0o022
            ):
                raise ReferenceValidationDependencyIdentityError(
                    f"{distribution_name} package namespace is not closed immutable storage"
                )
            continue
        if (
            path.is_symlink()
            or not stat.S_ISREG(file_stat.st_mode)
            or path.suffix == ".pyc"
            or "__pycache__" in relative_path.parts
            or path.resolve(strict=True) not in record_paths
        ):
            raise ReferenceValidationDependencyIdentityError(
                f"{distribution_name} package namespace contains an unrecorded importable payload"
            )


def _record_owned_namespace_roots(
    distribution_name: str,
    distribution_root: Path,
    *,
    record_paths: dict[Path, str],
    active_origin: Path,
) -> tuple[Path, ...]:
    roots: set[Path] = set()
    for resolved_path in record_paths:
        if not resolved_path.is_relative_to(distribution_root):
            continue
        relative = resolved_path.relative_to(distribution_root)
        if not relative.parts:
            raise ReferenceValidationDependencyIdentityError(
                f"{distribution_name} RECORD payload path is invalid"
            )
        top_level = distribution_root / relative.parts[0]
        if top_level.is_dir():
            roots.add(top_level)
    ordered = tuple(sorted(roots, key=lambda value: value.as_posix()))
    if not ordered or not any(active_origin.is_relative_to(root) for root in ordered):
        raise ReferenceValidationDependencyIdentityError(
            f"{distribution_name} RECORD namespace roots are incomplete"
        )
    return ordered


def _read_distribution_record_rows(
    distribution_name: str,
    distribution: metadata.Distribution,
    distribution_root: Path,
    *,
    allowed_roots: tuple[Path, ...],
    budget: _ScanBudget,
) -> tuple[list[tuple[str, str | None, int | None]], str]:
    """Read RECORD incrementally, applying byte/line/row caps before storage."""

    raw_metadata_root = getattr(distribution, "_path", None)
    if not isinstance(raw_metadata_root, (str, os.PathLike)):
        raise ReferenceValidationDependencyIdentityError(
            f"{distribution_name} distribution metadata root is unavailable"
        )
    metadata_root = Path(raw_metadata_root)
    try:
        resolved_metadata_root = metadata_root.resolve(strict=True)
    except OSError as exc:
        raise ReferenceValidationDependencyIdentityError(
            f"{distribution_name} distribution metadata root is unavailable"
        ) from exc
    if (
        not metadata_root.is_absolute()
        or metadata_root.is_symlink()
        or metadata_root.absolute() != resolved_metadata_root
        or resolved_metadata_root.parent != distribution_root
        or not resolved_metadata_root.name.endswith(".dist-info")
    ):
        raise ReferenceValidationDependencyIdentityError(
            f"{distribution_name} distribution metadata root is invalid"
        )
    _require_root_owned_read_only_directory_chain(resolved_metadata_root)
    record_path = resolved_metadata_root / "RECORD"
    try:
        resolved_record_path = record_path.resolve(strict=True)
    except OSError as exc:
        raise ReferenceValidationDependencyIdentityError(
            f"{distribution_name} RECORD is unavailable"
        ) from exc
    if (
        record_path.is_symlink()
        or record_path.absolute() != resolved_record_path
        or not any(resolved_record_path.is_relative_to(root) for root in allowed_roots)
    ):
        raise ReferenceValidationDependencyIdentityError(
            f"{distribution_name} RECORD path is invalid"
        )
    flags = os.O_RDONLY
    for flag_name in ("O_CLOEXEC", "O_NOFOLLOW"):
        if not hasattr(os, flag_name):
            raise ReferenceValidationDependencyIdentityError(
                "secure dependency file access is unavailable"
            )
        flags |= getattr(os, flag_name)
    try:
        descriptor = os.open(record_path, flags)
    except OSError as exc:
        raise ReferenceValidationDependencyIdentityError(
            f"{distribution_name} RECORD cannot be opened securely"
        ) from exc
    rows: list[tuple[str, str | None, int | None]] = []

    def append_record_row(raw_line: bytes) -> None:
        if raw_line.endswith(b"\r"):
            raw_line = raw_line[:-1]
        if (
            not raw_line
            or len(raw_line) > REFERENCE_VALIDATION_DEPENDENCY_RECORD_MAX_LINE_BYTES
        ):
            raise ReferenceValidationDependencyIdentityError(
                f"{distribution_name} RECORD line exceeds its bound"
            )
        try:
            line = raw_line.decode("utf-8")
            parsed = list(csv.reader([line], strict=True))
        except (UnicodeError, csv.Error) as exc:
            raise ReferenceValidationDependencyIdentityError(
                f"{distribution_name} RECORD row is invalid"
            ) from exc
        if len(parsed) != 1 or len(parsed[0]) != 3:
            raise ReferenceValidationDependencyIdentityError(
                f"{distribution_name} RECORD row is invalid"
            )
        relative, hash_field, size_field = parsed[0]
        try:
            path_bytes = relative.encode("utf-8")
        except UnicodeError as exc:
            raise ReferenceValidationDependencyIdentityError(
                f"{distribution_name} RECORD payload path is invalid"
            ) from exc
        if (
            not relative
            or "\\" in relative
            or any(ord(character) < 0x20 for character in relative)
            or len(path_bytes) > REFERENCE_VALIDATION_DEPENDENCY_MAX_PATH_BYTES
            or PurePosixPath(relative).is_absolute()
            or PurePosixPath(relative).as_posix() != relative
        ):
            raise ReferenceValidationDependencyIdentityError(
                f"{distribution_name} RECORD payload path is invalid"
            )
        declared_hash: str | None = None
        if hash_field:
            algorithm, separator, encoded = hash_field.partition("=")
            if algorithm != "sha256" or separator != "=" or not encoded:
                raise ReferenceValidationDependencyIdentityError(
                    f"{distribution_name} RECORD has an invalid payload hash"
                )
            declared_hash = encoded
        declared_size: int | None = None
        if size_field:
            if not size_field.isascii() or not size_field.isdigit():
                raise ReferenceValidationDependencyIdentityError(
                    f"{distribution_name} RECORD has an invalid payload size"
                )
            declared_size = int(size_field)
            if str(declared_size) != size_field:
                raise ReferenceValidationDependencyIdentityError(
                    f"{distribution_name} RECORD has an invalid payload size"
                )
        budget.start_entry()
        if len(rows) >= REFERENCE_VALIDATION_DEPENDENCY_MAX_FILES:
            raise ReferenceValidationDependencyIdentityError(
                f"{distribution_name} RECORD exceeds its row bound"
            )
        rows.append((relative, declared_hash, declared_size))

    try:
        initial_stat = os.fstat(descriptor)
        if (
            not stat.S_ISREG(initial_stat.st_mode)
            or initial_stat.st_uid != 0
            or stat.S_IMODE(initial_stat.st_mode) & 0o022
            or initial_stat.st_nlink != 1
            or not 0
            < initial_stat.st_size
            <= REFERENCE_VALIDATION_DEPENDENCY_RECORD_MAX_BYTES
        ):
            raise ReferenceValidationDependencyIdentityError(
                f"{distribution_name} RECORD violates its file policy"
            )
        budget.start_file(initial_stat.st_size)
        total = 0
        pending = b""
        while True:
            budget.checkpoint()
            chunk = os.read(
                descriptor,
                min(
                    8_192,
                    initial_stat.st_size + 1 - total,
                ),
            )
            if not chunk:
                break
            total += len(chunk)
            if total > initial_stat.st_size:
                raise ReferenceValidationDependencyIdentityError(
                    f"{distribution_name} RECORD grew while being read"
                )
            budget.add_bytes(len(chunk))
            segments = (pending + chunk).split(b"\n")
            pending = segments.pop()
            if len(pending) > REFERENCE_VALIDATION_DEPENDENCY_RECORD_MAX_LINE_BYTES:
                raise ReferenceValidationDependencyIdentityError(
                    f"{distribution_name} RECORD line exceeds its bound"
                )
            for segment in segments:
                append_record_row(segment)
        if pending:
            append_record_row(pending)
        final_stat = os.fstat(descriptor)
    except OSError as exc:
        raise ReferenceValidationDependencyIdentityError(
            f"{distribution_name} RECORD cannot be read securely"
        ) from exc
    finally:
        os.close(descriptor)
    if total != initial_stat.st_size or (
        initial_stat.st_dev,
        initial_stat.st_ino,
        initial_stat.st_size,
        initial_stat.st_mtime_ns,
    ) != (
        final_stat.st_dev,
        final_stat.st_ino,
        final_stat.st_size,
        final_stat.st_mtime_ns,
    ):
        raise ReferenceValidationDependencyIdentityError(
            f"{distribution_name} RECORD changed while being read"
        )
    rows.sort(key=lambda row: row[0])
    if not rows or any(left[0] >= right[0] for left, right in zip(rows, rows[1:])):
        raise ReferenceValidationDependencyIdentityError(
            f"{distribution_name} RECORD payload order is ambiguous"
        )
    record_relative = resolved_record_path.relative_to(distribution_root).as_posix()
    return rows, record_relative


def _distribution_identity(
    distribution_name: str,
    expected_base_version: str,
    artifact_id: str,
    import_package_name: str,
    *,
    allowed_roots: tuple[Path, ...],
    install_scheme_roots: tuple[tuple[str, Path], ...],
    budget: _ScanBudget,
) -> dict[str, object]:
    budget.checkpoint()
    try:
        distribution = metadata.distribution(distribution_name)
    except metadata.PackageNotFoundError as exc:
        raise ReferenceValidationDependencyIdentityError(
            f"{distribution_name} distribution is unavailable"
        ) from exc
    observed_version = distribution.version
    if observed_version.split("+", 1)[0] != expected_base_version:
        raise ReferenceValidationDependencyIdentityError(
            f"{distribution_name} distribution version is invalid"
        )
    rows: list[dict[str, object]] = []
    record_paths: dict[Path, str] = {}
    total_bytes = 0
    record_seen = False
    try:
        distribution_root = Path(distribution.locate_file("")).resolve(strict=True)
    except OSError as exc:
        raise ReferenceValidationDependencyIdentityError(
            f"{distribution_name} distribution root is unavailable"
        ) from exc
    if not any(
        distribution_root == root and scheme in {"purelib", "platlib"}
        for scheme, root in install_scheme_roots
    ):
        raise ReferenceValidationDependencyIdentityError(
            f"{distribution_name} distribution root is not an install scheme root"
        )
    record_rows, record_relative = _read_distribution_record_rows(
        distribution_name,
        distribution,
        distribution_root,
        allowed_roots=allowed_roots,
        budget=budget,
    )
    for relative, declared_hash_value, declared_size in record_rows:
        budget.checkpoint()
        if relative.endswith(".pyc") or "/__pycache__/" in f"/{relative}":
            raise ReferenceValidationDependencyIdentityError(
                f"{distribution_name} RECORD contains bytecode cache payload"
            )
        located = Path(distribution.locate_file(relative))
        try:
            resolved_located = located.resolve(strict=True)
        except OSError as exc:
            raise ReferenceValidationDependencyIdentityError(
                f"{distribution_name} RECORD payload is unavailable"
            ) from exc
        normalized_path = _normalized_record_payload_path(
            distribution_name,
            relative,
            resolved_located,
            distribution_root=distribution_root,
            install_scheme_roots=install_scheme_roots,
        )
        digest, size = _hash_regular_file(
            resolved_located,
            allowed_roots=allowed_roots,
            budget=budget,
            maximum_bytes=REFERENCE_VALIDATION_DEPENDENCY_MAX_BYTES - total_bytes,
        )
        if resolved_located in record_paths:
            raise ReferenceValidationDependencyIdentityError(
                f"{distribution_name} RECORD resolves duplicate payload paths"
            )
        record_paths[resolved_located] = normalized_path
        if relative == record_relative:
            if declared_hash_value is not None or declared_size is not None:
                raise ReferenceValidationDependencyIdentityError(
                    f"{distribution_name} RECORD self-row must be unhashed"
                )
            record_seen = True
        elif declared_hash_value is None or declared_size is None:
            raise ReferenceValidationDependencyIdentityError(
                f"{distribution_name} RECORD has an unhashed payload row"
            )
        else:
            padding = "=" * (-len(declared_hash_value) % 4)
            try:
                expected = base64.b64decode(
                    declared_hash_value + padding,
                    altchars=b"-_",
                    validate=True,
                ).hex()
            except (binascii.Error, ValueError) as exc:
                raise ReferenceValidationDependencyIdentityError(
                    f"{distribution_name} RECORD has an invalid payload hash"
                ) from exc
            if expected != digest:
                raise ReferenceValidationDependencyIdentityError(
                    f"{distribution_name} payload does not match RECORD"
                )
        if declared_size is not None and declared_size != size:
            raise ReferenceValidationDependencyIdentityError(
                f"{distribution_name} payload size does not match RECORD"
            )
        total_bytes += size
        rows.append({"path": normalized_path, "sha256": digest, "size": size})
        if (
            len(rows) > REFERENCE_VALIDATION_DEPENDENCY_MAX_FILES
            or total_bytes > REFERENCE_VALIDATION_DEPENDENCY_MAX_BYTES
        ):
            raise ReferenceValidationDependencyIdentityError(
                f"{distribution_name} identity exceeds its bounds"
            )
    if not rows or not record_seen:
        raise ReferenceValidationDependencyIdentityError(
            f"{distribution_name} RECORD identity is incomplete"
        )
    rows.sort(key=lambda row: str(row["path"]))
    import_binding = _distribution_import_binding(
        distribution_name,
        import_package_name,
        record_paths=record_paths,
    )
    active_origin = next(
        path
        for path, relative in record_paths.items()
        if relative == import_binding["import_origin_record_path"]
    )
    namespace_roots = _record_owned_namespace_roots(
        distribution_name,
        distribution_root,
        record_paths=record_paths,
        active_origin=active_origin,
    )
    for namespace_root in namespace_roots:
        _require_closed_distribution_namespace(
            distribution_name,
            namespace_root,
            record_paths=record_paths,
            budget=budget,
        )
    return _artifact_observation(
        artifact_id,
        {
            "distribution": distribution_name,
            "version": observed_version,
            "import_binding": import_binding,
            "files": rows,
        },
    )


def _dependency_manifest_document(
    artifacts: list[dict[str, object]],
) -> dict[str, object]:
    if (
        not isinstance(artifacts, list)
        or len(artifacts) != len(REFERENCE_VALIDATION_REQUIRED_DEPENDENCY_ARTIFACT_IDS)
        or any(not isinstance(row, dict) for row in artifacts)
    ):
        raise ReferenceValidationDependencyIdentityError(
            "dependency manifest artifact rows are invalid"
        )
    artifact_ids = tuple(row.get("artifact_id") for row in artifacts)
    if artifact_ids != REFERENCE_VALIDATION_REQUIRED_DEPENDENCY_ARTIFACT_IDS:
        raise ReferenceValidationDependencyIdentityError(
            "dependency manifest artifact order drifted"
        )
    file_count = 0
    total_bytes = 0
    for artifact in artifacts:
        if not isinstance(artifact, dict) or set(artifact) != {
            "artifact_id",
            "sha256",
            "identity",
        }:
            raise ReferenceValidationDependencyIdentityError(
                "dependency manifest artifact row is invalid"
            )
        identity = artifact.get("identity")
        if (
            not isinstance(identity, dict)
            or not {"schema_id", "artifact_id", "files"}.issubset(identity)
            or not set(identity).issubset(
                {
                    "schema_id",
                    "artifact_id",
                    "distribution",
                    "version",
                    "import_binding",
                    "files",
                }
            )
            or identity.get("schema_id")
            != REFERENCE_VALIDATION_DEPENDENCY_IDENTITY_SCHEMA_ID
            or identity.get("artifact_id") != artifact.get("artifact_id")
        ):
            raise ReferenceValidationDependencyIdentityError(
                "dependency manifest artifact identity is invalid"
            )
        distribution_fields = {
            "distribution",
            "version",
            "import_binding",
        }.intersection(identity)
        if distribution_fields and distribution_fields != {
            "distribution",
            "version",
            "import_binding",
        }:
            raise ReferenceValidationDependencyIdentityError(
                "dependency manifest distribution identity is incomplete"
            )
        if distribution_fields:
            import_binding = identity.get("import_binding")
            if (
                not isinstance(identity.get("distribution"), str)
                or not identity["distribution"]
                or not isinstance(identity.get("version"), str)
                or not identity["version"]
                or not isinstance(import_binding, dict)
                or set(import_binding)
                != {"import_package", "import_origin_record_path"}
                or not all(
                    isinstance(value, str) and value
                    for value in import_binding.values()
                )
            ):
                raise ReferenceValidationDependencyIdentityError(
                    "dependency manifest distribution identity is invalid"
                )
        artifact_sha256 = artifact.get("sha256")
        if (
            not isinstance(artifact_sha256, str)
            or len(artifact_sha256) != 64
            or any(character not in "0123456789abcdef" for character in artifact_sha256)
            or artifact_sha256 != hashlib.sha256(_canonical_bytes(identity)).hexdigest()
        ):
            raise ReferenceValidationDependencyIdentityError(
                "dependency manifest artifact digest is invalid"
            )
        artifact_file_count, artifact_total_bytes = _require_manifest_file_rows(
            identity.get("files")
        )
        file_count += artifact_file_count
        total_bytes += artifact_total_bytes
        if (
            file_count > REFERENCE_VALIDATION_DEPENDENCY_TOTAL_MAX_FILES
            or total_bytes > REFERENCE_VALIDATION_DEPENDENCY_TOTAL_MAX_BYTES
        ):
            raise ReferenceValidationDependencyIdentityError(
                "dependency manifest exceeds its aggregate bounds"
            )
    projection = {
        "schema_id": REFERENCE_VALIDATION_DEPENDENCY_MANIFEST_SCHEMA_ID,
        "identity_schema_id": REFERENCE_VALIDATION_DEPENDENCY_IDENTITY_SCHEMA_ID,
        "artifacts": artifacts,
        "file_count": file_count,
        "total_bytes": total_bytes,
    }
    return {
        **projection,
        "manifest_sha256": hashlib.sha256(_canonical_bytes(projection)).hexdigest(),
    }


def require_reference_validation_dependency_manifest_document(
    value: object,
) -> dict[str, object]:
    """Require an exact canonical manifest produced by this helper."""

    if not isinstance(value, dict) or set(value) != {
        "schema_id",
        "identity_schema_id",
        "artifacts",
        "file_count",
        "total_bytes",
        "manifest_sha256",
    }:
        raise ReferenceValidationDependencyIdentityError(
            "dependency manifest fields are invalid"
        )
    artifacts = value.get("artifacts")
    if (
        value.get("schema_id") != REFERENCE_VALIDATION_DEPENDENCY_MANIFEST_SCHEMA_ID
        or value.get("identity_schema_id")
        != REFERENCE_VALIDATION_DEPENDENCY_IDENTITY_SCHEMA_ID
        or not isinstance(artifacts, list)
    ):
        raise ReferenceValidationDependencyIdentityError(
            "dependency manifest schema is invalid"
        )
    rebuilt = _dependency_manifest_document(artifacts)
    if rebuilt != value:
        raise ReferenceValidationDependencyIdentityError(
            "dependency manifest is not exact"
        )
    return dict(value)


def observed_reference_validation_dependency_manifest_document(
    dependency_roots: Iterable[str | os.PathLike[str]],
    *,
    deadline: float | None = None,
) -> dict[str, object]:
    """Measure and retain the exact active dependency per-file manifest."""

    if deadline is None:
        deadline = (
            time.monotonic()
            + REFERENCE_VALIDATION_DEPENDENCY_PREFLIGHT_MAX_WALL_SECONDS
        )
    budget = _ScanBudget(deadline)
    roots = _require_trusted_roots(dependency_roots)
    install_scheme_roots = _trusted_install_scheme_roots()
    python_executable = Path(sys.executable).resolve(strict=True)
    openssl_executable = Path("/usr/bin/openssl").resolve(strict=True)
    configured_stdlib = sysconfig.get_paths().get("stdlib")
    if not isinstance(configured_stdlib, str):
        raise ReferenceValidationDependencyIdentityError(
            "Python standard-library root is unavailable"
        )
    all_roots = _require_trusted_roots(
        (
            *roots,
            python_executable.parent,
            openssl_executable.parent,
            Path(configured_stdlib).resolve(strict=True),
            *(root for _, root in install_scheme_roots),
        )
    )
    artifacts = [
        _distribution_identity(
            "cryptography",
            "46.0.5",
            "cryptography-distribution",
            "cryptography",
            allowed_roots=all_roots,
            install_scheme_roots=install_scheme_roots,
            budget=budget,
        ),
        _distribution_identity(
            "numpy",
            "1.26.4",
            "numpy-distribution",
            "numpy",
            allowed_roots=all_roots,
            install_scheme_roots=install_scheme_roots,
            budget=budget,
        ),
        _single_file_identity(
            "openssl-executable",
            openssl_executable,
            allowed_roots=all_roots,
            budget=budget,
        ),
        _single_file_identity(
            "python-runtime-executable",
            python_executable,
            allowed_roots=all_roots,
            budget=budget,
        ),
        _standard_library_identity(
            allowed_roots=all_roots,
            budget=budget,
        ),
        _distribution_identity(
            "torch",
            "2.6.0",
            "torch-distribution",
            "torch",
            allowed_roots=all_roots,
            install_scheme_roots=install_scheme_roots,
            budget=budget,
        ),
    ]
    return _dependency_manifest_document(artifacts)


def observed_reference_validation_dependency_artifact_sha256_rows(
    dependency_roots: Iterable[str | os.PathLike[str]],
    *,
    deadline: float | None = None,
) -> dict[str, str]:
    """Measure the exact active dependency bytes without importing them."""

    manifest = observed_reference_validation_dependency_manifest_document(
        dependency_roots,
        deadline=deadline,
    )
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        raise ReferenceValidationDependencyIdentityError(
            "dependency manifest artifacts are invalid"
        )
    return {str(row["artifact_id"]): str(row["sha256"]) for row in artifacts}


__all__ = [
    "REFERENCE_VALIDATION_DEPENDENCY_IDENTITY_SCHEMA_ID",
    "REFERENCE_VALIDATION_DEPENDENCY_MANIFEST_SCHEMA_ID",
    "REFERENCE_VALIDATION_DEPENDENCY_PREFLIGHT_MAX_WALL_SECONDS",
    "REFERENCE_VALIDATION_REQUIRED_DEPENDENCY_ARTIFACT_IDS",
    "ReferenceValidationDependencyIdentityError",
    "observed_reference_validation_dependency_artifact_sha256_rows",
    "observed_reference_validation_dependency_manifest_document",
    "require_reference_validation_dependency_manifest_document",
]
