"""Exact source/Git-tree identity for synthetic validation runtimes.

This module is deliberately standard-library only so a validation bootstrap can
load it by absolute path before importing the Engine v2 package.  The signed
commit is treated as the trust anchor: raw commit and tree objects are rehashed,
then every tracked package blob is compared with a securely opened source file.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import select
import stat
import subprocess
import time
from typing import Any, Mapping


VALIDATION_SOURCE_MANIFEST_SCHEMA_ID = (
    "betelgeuze.engine_v2_validation_source_manifest/1.0.0"
)
VALIDATION_SOURCE_MANIFEST_SCOPE_PATH = "betelgeuze_engine_v2"
VALIDATION_SOURCE_MANIFEST_PREFLIGHT_MAX_WALL_SECONDS = 120.0
VALIDATION_SOURCE_MANIFEST_MAX_ENTRIES = 50_000
VALIDATION_SOURCE_MANIFEST_MAX_FILES = 25_000
VALIDATION_SOURCE_MANIFEST_MAX_BYTES = 2 * 1024**3
VALIDATION_SOURCE_MANIFEST_MAX_FILE_BYTES = 256 * 1024**2
VALIDATION_SOURCE_MANIFEST_MAX_GIT_OBJECT_BYTES = 32 * 1024**2
VALIDATION_SOURCE_MANIFEST_MAX_PATH_BYTES = 4_096


class ValidationSourceIdentityError(RuntimeError):
    """The package source cannot be bound exactly to the signed Git tree."""


class _SourceBudget:
    __slots__ = ("bytes", "deadline", "entries", "files")

    def __init__(self, deadline: float) -> None:
        if (
            type(deadline) is not float
            or deadline != deadline
            or deadline in {float("inf"), float("-inf")}
        ):
            raise ValidationSourceIdentityError("source preflight deadline is invalid")
        self.deadline = deadline
        self.entries = 0
        self.files = 0
        self.bytes = 0
        self.checkpoint()

    def checkpoint(self) -> None:
        if time.monotonic() >= self.deadline:
            raise ValidationSourceIdentityError("source preflight deadline expired")

    def add_entry(self) -> None:
        self.checkpoint()
        self.entries += 1
        if self.entries > VALIDATION_SOURCE_MANIFEST_MAX_ENTRIES:
            raise ValidationSourceIdentityError(
                "source manifest exceeds its entry bound"
            )

    def start_file(self, size: int) -> None:
        self.checkpoint()
        if (
            type(size) is not int
            or size < 0
            or size > VALIDATION_SOURCE_MANIFEST_MAX_FILE_BYTES
            or size > VALIDATION_SOURCE_MANIFEST_MAX_BYTES - self.bytes
        ):
            raise ValidationSourceIdentityError(
                "source file exceeds its pre-read byte bound"
            )
        self.files += 1
        if self.files > VALIDATION_SOURCE_MANIFEST_MAX_FILES:
            raise ValidationSourceIdentityError(
                "source manifest exceeds its file bound"
            )

    def add_bytes(self, count: int) -> None:
        self.checkpoint()
        self.bytes += count
        if self.bytes > VALIDATION_SOURCE_MANIFEST_MAX_BYTES:
            raise ValidationSourceIdentityError(
                "source manifest exceeds its byte bound"
            )


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ValidationSourceIdentityError(
            "source manifest is not canonical JSON"
        ) from exc


def _require_lower_hex(value: object, *, length: int, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != length
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValidationSourceIdentityError(f"{name} is invalid")
    return value


def _require_root_owned_read_only_directory_chain(path: Path) -> Path:
    if not path.is_absolute():
        raise ValidationSourceIdentityError("source repository path is not absolute")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise ValidationSourceIdentityError(
            "source repository path is unavailable"
        ) from exc
    if resolved != path:
        raise ValidationSourceIdentityError("source repository path is not canonical")
    current = resolved
    while current != current.parent:
        try:
            file_stat = current.lstat()
        except OSError as exc:
            raise ValidationSourceIdentityError(
                "source repository directory chain is unavailable"
            ) from exc
        if current.is_symlink():
            raise ValidationSourceIdentityError(
                "source repository is not root-owned read-only storage"
            )
        _require_trusted_source_directory_stat(file_stat)
        current = current.parent
    return resolved


def _require_trusted_source_directory_stat(file_stat: os.stat_result) -> None:
    if (
        not stat.S_ISDIR(file_stat.st_mode)
        or file_stat.st_uid != 0
        or stat.S_IMODE(file_stat.st_mode) & 0o022
    ):
        raise ValidationSourceIdentityError(
            "source repository is not root-owned read-only storage"
        )


def _require_trusted_source_file_stat(
    file_stat: os.stat_result,
    *,
    expected_mode: str,
) -> None:
    executable = bool(stat.S_IMODE(file_stat.st_mode) & 0o111)
    if (
        not stat.S_ISREG(file_stat.st_mode)
        or file_stat.st_uid != 0
        or stat.S_IMODE(file_stat.st_mode) & 0o022
        or file_stat.st_nlink != 1
        or (expected_mode == "100755") != executable
    ):
        raise ValidationSourceIdentityError(
            "source file is not the expected root-owned regular file"
        )


def _trusted_git_executable() -> str:
    path = Path("/usr/bin/git")
    try:
        file_stat = path.lstat()
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise ValidationSourceIdentityError("trusted Git is unavailable") from exc
    if (
        path != resolved
        or path.is_symlink()
        or not stat.S_ISREG(file_stat.st_mode)
        or file_stat.st_uid != 0
        or stat.S_IMODE(file_stat.st_mode) & 0o022
    ):
        raise ValidationSourceIdentityError("trusted Git executable is invalid")
    _require_root_owned_read_only_directory_chain(path.parent)
    return os.fspath(path)


def _git_environment() -> dict[str, str]:
    return {
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "HOME": "/nonexistent",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": "/usr/bin:/bin",
    }


def _run_git_bounded(
    repository_root: Path,
    arguments: tuple[str, ...],
    *,
    deadline: float,
    maximum_stdout_bytes: int,
) -> bytes:
    if maximum_stdout_bytes < 0:
        raise ValidationSourceIdentityError("Git output bound is invalid")
    command = (
        _trusted_git_executable(),
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.hooksPath=/dev/null",
        *arguments,
    )
    try:
        process = subprocess.Popen(
            command,
            cwd=repository_root,
            env=_git_environment(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
    except OSError as exc:
        raise ValidationSourceIdentityError("Git source read could not start") from exc
    if process.stdout is None:
        process.kill()
        process.wait()
        raise ValidationSourceIdentityError("Git source read has no output pipe")
    descriptor = process.stdout.fileno()
    chunks: list[bytes] = []
    observed = 0
    eof = False
    try:
        os.set_blocking(descriptor, False)
        while not eof:
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                raise ValidationSourceIdentityError("source preflight deadline expired")
            readable, _, _ = select.select((descriptor,), (), (), min(remaining, 0.1))
            if not readable:
                if process.poll() is not None:
                    continue
                continue
            try:
                chunk = os.read(descriptor, 1024 * 1024)
            except BlockingIOError:
                continue
            if not chunk:
                eof = True
                continue
            observed += len(chunk)
            if observed > maximum_stdout_bytes:
                raise ValidationSourceIdentityError(
                    "Git source output exceeds its bound"
                )
            chunks.append(chunk)
        remaining = deadline - time.monotonic()
        if remaining <= 0.0:
            raise ValidationSourceIdentityError("source preflight deadline expired")
        return_code = process.wait(timeout=remaining)
        if return_code != 0:
            raise ValidationSourceIdentityError("Git source read failed")
    except (OSError, subprocess.SubprocessError):
        raise ValidationSourceIdentityError("Git source read failed") from None
    finally:
        process.stdout.close()
        if process.poll() is None:
            process.kill()
            process.wait()
    return b"".join(chunks)


def _read_verified_git_object(
    repository_root: Path,
    object_id: str,
    object_type: str,
    *,
    budget: _SourceBudget,
) -> bytes:
    _require_lower_hex(object_id, length=40, name=f"Git {object_type} object ID")
    if object_type not in {"commit", "tree"}:
        raise ValidationSourceIdentityError("Git object type is invalid")
    budget.checkpoint()
    payload = _run_git_bounded(
        repository_root,
        ("cat-file", object_type, object_id),
        deadline=budget.deadline,
        maximum_stdout_bytes=VALIDATION_SOURCE_MANIFEST_MAX_GIT_OBJECT_BYTES,
    )
    observed = hashlib.sha1(  # noqa: S324 - Git's signed object format is SHA-1.
        f"{object_type} {len(payload)}\0".encode("ascii") + payload
    ).hexdigest()
    if observed != object_id:
        raise ValidationSourceIdentityError(
            f"Git {object_type} object does not match its object ID"
        )
    return payload


def _root_tree_id_from_commit(payload: bytes) -> str:
    first_line = payload.split(b"\n", 1)[0]
    if not first_line.startswith(b"tree "):
        raise ValidationSourceIdentityError("signed Git commit has no root tree")
    try:
        tree_id = first_line[5:].decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValidationSourceIdentityError("signed Git tree ID is invalid") from exc
    return _require_lower_hex(tree_id, length=40, name="signed Git tree ID")


def _parse_tree(
    payload: bytes,
    *,
    budget: _SourceBudget | None = None,
) -> tuple[tuple[str, str, str], ...]:
    rows: list[tuple[str, str, str]] = []
    offset = 0
    names: set[str] = set()
    while offset < len(payload):
        space = payload.find(b" ", offset)
        nul = payload.find(b"\0", space + 1 if space >= 0 else offset)
        if space <= offset or nul <= space + 1 or nul + 21 > len(payload):
            raise ValidationSourceIdentityError("Git tree object is malformed")
        raw_mode = payload[offset:space]
        raw_name = payload[space + 1 : nul]
        raw_object_id = payload[nul + 1 : nul + 21]
        offset = nul + 21
        try:
            mode = raw_mode.decode("ascii")
            name = raw_name.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValidationSourceIdentityError(
                "Git tree entry is not canonical text"
            ) from exc
        if (
            mode not in {"40000", "100644", "100755"}
            or not name
            or name in {".", ".."}
            or "/" in name
            or "\x00" in name
            or len(raw_name) > VALIDATION_SOURCE_MANIFEST_MAX_PATH_BYTES
            or name in names
        ):
            raise ValidationSourceIdentityError("Git tree entry is unsafe")
        if budget is None:
            if len(rows) >= VALIDATION_SOURCE_MANIFEST_MAX_ENTRIES:
                raise ValidationSourceIdentityError(
                    "source manifest exceeds its entry bound"
                )
        else:
            budget.add_entry()
        names.add(name)
        rows.append((mode, name, raw_object_id.hex()))
    if not rows:
        raise ValidationSourceIdentityError("Git tree object is empty")
    return tuple(rows)


def _expected_package_tree(
    repository_root: Path,
    commit_sha: str,
    *,
    budget: _SourceBudget,
) -> tuple[dict[str, tuple[str, str]], set[str]]:
    commit = _read_verified_git_object(
        repository_root, commit_sha, "commit", budget=budget
    )
    root_tree_id = _root_tree_id_from_commit(commit)
    root_tree = _parse_tree(
        _read_verified_git_object(repository_root, root_tree_id, "tree", budget=budget),
        budget=budget,
    )
    package_matches = [
        row for row in root_tree if row[1] == VALIDATION_SOURCE_MANIFEST_SCOPE_PATH
    ]
    if len(package_matches) != 1 or package_matches[0][0] != "40000":
        raise ValidationSourceIdentityError(
            "signed Git tree does not contain the exact package root"
        )
    expected_files: dict[str, tuple[str, str]] = {}
    expected_directories = {VALIDATION_SOURCE_MANIFEST_SCOPE_PATH}
    pending = [(VALIDATION_SOURCE_MANIFEST_SCOPE_PATH, package_matches[0][2])]
    while pending:
        relative_directory, tree_id = pending.pop()
        entries = _parse_tree(
            _read_verified_git_object(repository_root, tree_id, "tree", budget=budget),
            budget=budget,
        )
        for mode, name, object_id in entries:
            relative = PurePosixPath(relative_directory, name).as_posix()
            if (
                len(relative.encode("utf-8"))
                > VALIDATION_SOURCE_MANIFEST_MAX_PATH_BYTES
            ):
                raise ValidationSourceIdentityError("source path exceeds its bound")
            if mode == "40000":
                if relative in expected_directories:
                    raise ValidationSourceIdentityError(
                        "Git tree directory is duplicated"
                    )
                expected_directories.add(relative)
                pending.append((relative, object_id))
            else:
                if relative in expected_files:
                    raise ValidationSourceIdentityError("Git tree file is duplicated")
                expected_files[relative] = (mode, object_id)
    if not expected_files:
        raise ValidationSourceIdentityError("signed package Git tree is empty")
    return expected_files, expected_directories


def _hash_source_file(
    path: Path,
    *,
    expected_mode: str,
    expected_blob_id: str,
    budget: _SourceBudget,
) -> tuple[str, int]:
    flags = os.O_RDONLY
    for flag_name in ("O_CLOEXEC", "O_NOFOLLOW"):
        if not hasattr(os, flag_name):
            raise ValidationSourceIdentityError("secure source access is unavailable")
        flags |= getattr(os, flag_name)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ValidationSourceIdentityError(
            "source file cannot be opened securely"
        ) from exc
    try:
        before = os.fstat(descriptor)
        _require_trusted_source_file_stat(before, expected_mode=expected_mode)
        budget.start_file(before.st_size)
        git_digest = hashlib.sha1(  # noqa: S324 - Git's blob format is SHA-1.
            f"blob {before.st_size}\0".encode("ascii")
        )
        sha256_digest = hashlib.sha256()
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
                raise ValidationSourceIdentityError(
                    "source file grew while being measured"
                )
            git_digest.update(chunk)
            sha256_digest.update(chunk)
            budget.add_bytes(len(chunk))
        after = os.fstat(descriptor)
    except OSError as exc:
        raise ValidationSourceIdentityError("source file cannot be measured") from exc
    finally:
        os.close(descriptor)
    if (
        observed_size != before.st_size
        or git_digest.hexdigest() != expected_blob_id
        or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    ):
        raise ValidationSourceIdentityError(
            "source file bytes do not match the signed Git blob"
        )
    return sha256_digest.hexdigest(), observed_size


def _actual_package_rows(
    repository_root: Path,
    expected_files: Mapping[str, tuple[str, str]],
    expected_directories: set[str],
    *,
    budget: _SourceBudget,
) -> list[dict[str, object]]:
    package_root = repository_root / VALIDATION_SOURCE_MANIFEST_SCOPE_PATH
    _require_root_owned_read_only_directory_chain(package_root)
    observed_directories = {VALIDATION_SOURCE_MANIFEST_SCOPE_PATH}
    observed_files: set[str] = set()
    rows: list[dict[str, object]] = []
    pending = [package_root]
    while pending:
        directory = pending.pop()
        try:
            with os.scandir(directory) as stream:
                entries = []
                for entry in stream:
                    budget.add_entry()
                    entries.append(entry)
        except OSError as exc:
            raise ValidationSourceIdentityError(
                "source package directory cannot be enumerated"
            ) from exc
        entries.sort(key=lambda entry: entry.name)
        child_directories: list[Path] = []
        for entry in entries:
            path = Path(entry.path)
            relative = path.relative_to(repository_root).as_posix()
            try:
                file_stat = entry.stat(follow_symlinks=False)
            except OSError as exc:
                raise ValidationSourceIdentityError(
                    "source package entry is unavailable"
                ) from exc
            if entry.is_symlink():
                raise ValidationSourceIdentityError("source package contains a symlink")
            if stat.S_ISDIR(file_stat.st_mode):
                _require_trusted_source_directory_stat(file_stat)
                if relative not in expected_directories:
                    raise ValidationSourceIdentityError(
                        "source package directory is not in the signed Git tree"
                    )
                observed_directories.add(relative)
                child_directories.append(path)
                continue
            expected = expected_files.get(relative)
            if expected is None or not stat.S_ISREG(file_stat.st_mode):
                raise ValidationSourceIdentityError(
                    "source package file is not in the signed Git tree"
                )
            digest, size = _hash_source_file(
                path,
                expected_mode=expected[0],
                expected_blob_id=expected[1],
                budget=budget,
            )
            observed_files.add(relative)
            rows.append(
                {
                    "path": relative,
                    "git_mode": expected[0],
                    "git_blob_oid": expected[1],
                    "sha256": digest,
                    "size": size,
                }
            )
        pending.extend(reversed(child_directories))
    if observed_directories != expected_directories or observed_files != set(
        expected_files
    ):
        raise ValidationSourceIdentityError(
            "source package tree is missing signed Git entries"
        )
    rows.sort(key=lambda row: str(row["path"]))
    return rows


def _manifest_document(
    code_commit_sha: str,
    files: list[dict[str, object]],
) -> dict[str, object]:
    file_count = len(files)
    total_bytes = sum(int(row["size"]) for row in files)
    projection = {
        "schema_id": VALIDATION_SOURCE_MANIFEST_SCHEMA_ID,
        "git_object_format": "sha1",
        "code_commit_sha": code_commit_sha,
        "scope_path": VALIDATION_SOURCE_MANIFEST_SCOPE_PATH,
        "files": files,
        "file_count": file_count,
        "total_bytes": total_bytes,
    }
    return {
        **projection,
        "manifest_sha256": hashlib.sha256(_canonical_bytes(projection)).hexdigest(),
    }


def require_validation_source_manifest_document(
    value: Mapping[str, Any],
) -> dict[str, object]:
    """Require the exact canonical shape and digest of a source manifest."""

    expected_fields = {
        "schema_id",
        "git_object_format",
        "code_commit_sha",
        "scope_path",
        "files",
        "file_count",
        "total_bytes",
        "manifest_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != expected_fields:
        raise ValidationSourceIdentityError("source manifest fields are invalid")
    document = dict(value)
    commit = _require_lower_hex(
        document.get("code_commit_sha"), length=40, name="source manifest commit"
    )
    files = document.get("files")
    if (
        document.get("schema_id") != VALIDATION_SOURCE_MANIFEST_SCHEMA_ID
        or document.get("git_object_format") != "sha1"
        or document.get("scope_path") != VALIDATION_SOURCE_MANIFEST_SCOPE_PATH
        or not isinstance(files, list)
        or len(files) > VALIDATION_SOURCE_MANIFEST_MAX_FILES
    ):
        raise ValidationSourceIdentityError("source manifest identity is invalid")
    previous_path = ""
    total_bytes = 0
    for row in files:
        if not isinstance(row, dict) or set(row) != {
            "path",
            "git_mode",
            "git_blob_oid",
            "sha256",
            "size",
        }:
            raise ValidationSourceIdentityError("source manifest file row is invalid")
        path = row.get("path")
        size = row.get("size")
        try:
            path_bytes = path.encode("utf-8") if isinstance(path, str) else b""
        except UnicodeError as exc:
            raise ValidationSourceIdentityError(
                "source manifest file row is invalid"
            ) from exc
        if (
            not isinstance(path, str)
            or not path.startswith(f"{VALIDATION_SOURCE_MANIFEST_SCOPE_PATH}/")
            or PurePosixPath(path).as_posix() != path
            or any(part in {"", ".", ".."} for part in PurePosixPath(path).parts)
            or len(path_bytes) > VALIDATION_SOURCE_MANIFEST_MAX_PATH_BYTES
            or path <= previous_path
            or row.get("git_mode") not in {"100644", "100755"}
            or type(size) is not int
            or size < 0
            or size > VALIDATION_SOURCE_MANIFEST_MAX_FILE_BYTES
        ):
            raise ValidationSourceIdentityError("source manifest file row is invalid")
        _require_lower_hex(
            row.get("git_blob_oid"), length=40, name="source manifest blob"
        )
        _require_lower_hex(row.get("sha256"), length=64, name="source manifest file")
        previous_path = path
        total_bytes += size
    if (
        not files
        or type(document.get("file_count")) is not int
        or document.get("file_count") != len(files)
        or type(document.get("total_bytes")) is not int
        or document.get("total_bytes") != total_bytes
        or total_bytes > VALIDATION_SOURCE_MANIFEST_MAX_BYTES
    ):
        raise ValidationSourceIdentityError("source manifest counts are invalid")
    rebuilt = _manifest_document(commit, files)
    if rebuilt != document:
        raise ValidationSourceIdentityError("source manifest is not exact")
    return rebuilt


def observed_validation_source_manifest_document(
    repository_root: str | os.PathLike[str],
    expected_code_commit_sha: str,
    *,
    deadline: float | None = None,
) -> dict[str, object]:
    """Measure the complete package source against a self-verified Git tree."""

    commit = _require_lower_hex(
        expected_code_commit_sha, length=40, name="expected source commit"
    )
    if deadline is None:
        deadline = (
            time.monotonic() + VALIDATION_SOURCE_MANIFEST_PREFLIGHT_MAX_WALL_SECONDS
        )
    budget = _SourceBudget(deadline)
    root = _require_root_owned_read_only_directory_chain(Path(repository_root))
    expected_files, expected_directories = _expected_package_tree(
        root, commit, budget=budget
    )
    rows = _actual_package_rows(
        root,
        expected_files,
        expected_directories,
        budget=budget,
    )
    return _manifest_document(commit, rows)


__all__ = [
    "VALIDATION_SOURCE_MANIFEST_PREFLIGHT_MAX_WALL_SECONDS",
    "VALIDATION_SOURCE_MANIFEST_SCHEMA_ID",
    "VALIDATION_SOURCE_MANIFEST_SCOPE_PATH",
    "ValidationSourceIdentityError",
    "observed_validation_source_manifest_document",
    "require_validation_source_manifest_document",
]
