"""Stdlib-only bootstrap for the bounded reference-validation process.

This file is executed directly, before importing the Engine v2 package.  An
isolated outer launcher verifies the executable and command, then re-executes
the same interpreter with a minimal environment so ``PYTHONHASHSEED`` is
applied during interpreter initialization.  Automatic ``site`` loading stays
disabled throughout the bootstrap.
"""

from __future__ import annotations

import hashlib
import importlib.abc
import importlib.machinery
import importlib.util
import json
import os
import select
import stat
import subprocess
import sys
import sysconfig
import time
import types


REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_RELATIVE_PATH = (
    "betelgeuze_engine_v2/physics/reference_minimization_validation_bootstrap.py"
)
REFERENCE_MINIMIZATION_VALIDATION_DEPENDENCY_IDENTITY_RELATIVE_PATH = "betelgeuze_engine_v2/physics/reference_minimization_validation_dependency_identity.py"
REFERENCE_MINIMIZATION_VALIDATION_SOURCE_IDENTITY_RELATIVE_PATH = (
    "betelgeuze_engine_v2/physics/validation_source_identity.py"
)
REFERENCE_MINIMIZATION_VALIDATION_NATIVE_RUNTIME_IDENTITY_RELATIVE_PATH = (
    "betelgeuze_engine_v2/physics/validation_native_runtime_identity.py"
)
REFERENCE_MINIMIZATION_VALIDATION_TRUSTED_OUTER_LAUNCHER_ARGV = (
    "python",
    "-I",
    "-S",
    "-B",
    "-X",
    "pycache_prefix=/dev/null",
    REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_RELATIVE_PATH,
)
REFERENCE_MINIMIZATION_VALIDATION_FIXED_RUNPY_LOADER = (
    'import runpy,sys;p=sys.argv.pop();runpy.run_path(p,run_name="__main__")'
)
REFERENCE_MINIMIZATION_VALIDATION_LOGICAL_RUNNER_ARGV = (
    "python",
    "-S",
    "-B",
    "-X",
    "pycache_prefix=/dev/null",
    "-c",
    REFERENCE_MINIMIZATION_VALIDATION_FIXED_RUNPY_LOADER,
    REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_RELATIVE_PATH,
)
REFERENCE_MINIMIZATION_VALIDATION_CONTROLLED_INNER_STATE = "seeded-controlled-inner/3"
REFERENCE_MINIMIZATION_VALIDATION_CONTROLLED_INNER_STAGE_ENV = (
    "BETELGEUZE_REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_STAGE"
)
REFERENCE_MINIMIZATION_VALIDATION_CONTROLLED_INNER_PREFLIGHT_DEADLINE_ENV = (
    "BETELGEUZE_REFERENCE_MINIMIZATION_VALIDATION_PREFLIGHT_DEADLINE"
)
REFERENCE_MINIMIZATION_VALIDATION_APPLICATION_SEED_ENV = (
    "BETELGEUZE_REFERENCE_MINIMIZATION_VALIDATION_SEED"
)
REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_STATE_ATTRIBUTE = (
    "_betelgeuze_reference_minimization_validation_bootstrap_state"
)
REFERENCE_MINIMIZATION_VALIDATION_SOURCE_FINDER_ATTRIBUTE = (
    "_betelgeuze_reference_minimization_validation_source_finder"
)
REFERENCE_MINIMIZATION_VALIDATION_SOURCE_MANIFEST_ATTRIBUTE = (
    "_betelgeuze_reference_minimization_validation_source_manifest_sha256"
)
REFERENCE_MINIMIZATION_VALIDATION_SOURCE_MANIFEST_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_validation_execution_sources/2.0.0"
)
REFERENCE_MINIMIZATION_VALIDATION_SOURCE_MAX_FILES = 4_096
REFERENCE_MINIMIZATION_VALIDATION_SOURCE_MAX_FILE_BYTES = 8 * 1_048_576
REFERENCE_MINIMIZATION_VALIDATION_SOURCE_MAX_TOTAL_BYTES = 64 * 1_048_576
_SOURCE_PATH_PRIMITIVES_AVAILABLE = (
    os.name == "posix"
    and all(
        hasattr(os, name)
        for name in ("O_CLOEXEC", "O_DIRECTORY", "O_NOFOLLOW")
    )
    and os.open in os.supports_dir_fd
    and os.stat in os.supports_dir_fd
    and os.stat in os.supports_follow_symlinks
    and os.listdir in os.supports_fd
)
REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_MAX_REQUEST_BYTES = 1_048_576
REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_TRUST_STORE_MAX_BYTES = 65_536
REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_PREFLIGHT_MAX_WALL_SECONDS = 180.0
REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_SOURCE_TREE_MAX_ENTRIES = 50_000
REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_SOURCE_TREE_MAX_PATH_BYTES = 4_096
REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_EXECUTION_SOURCE_MAX_BYTES = 16 * 1024**2
REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_EXECUTION_SOURCE_MAX_WALL_SECONDS = 10.0
REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_PROCESS_ARGV_MAX_BYTES = 65_536
REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_TRUST_STORE_PATH = (
    "/etc/betelgeuze/engine-v2/reference-minimization-validation-trust-anchors.json"
)
REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_TRUST_STORE_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_validation_trust_store/2.0.0"
)
REFERENCE_MINIMIZATION_VALIDATION_RUNNER_RESPONSE_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_validation_runner_response/2.0.0"
)
_REFERENCE_MINIMIZATION_VALIDATION_TRUST_STORE_SCHEMA_ID = (
    REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_TRUST_STORE_SCHEMA_ID
)
_REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_validation_authorization_receipt/6.0.0"
)
_REFERENCE_MINIMIZATION_VALIDATION_REVIEW_ATTESTATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_validation_review_attestation/5.0.0"
)
_REFERENCE_MINIMIZATION_VALIDATION_NETWORK_ATTESTATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_validation_network_isolation_attestation/6.0.0"
)
_REFERENCE_MINIMIZATION_VALIDATION_TRUST_STORE_FIELDS = frozenset(
    {
        "schema_id",
        "reviewer_keys",
        "operator_keys",
        "revoked_authorization_receipt_sha256s",
        "revoked_review_attestation_sha256s",
        "externally_conflicting_nonce_sha256s",
        "revoked_network_attestation_sha256s",
        "superseded_operator_key_ids",
        "superseded_reviewer_key_ids",
        "minimum_authorization_receipt_schema_id",
        "minimum_review_attestation_schema_id",
    }
)
_REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_SIGNATURE_ALGORITHM = "ed25519"
_REFERENCE_MINIMIZATION_VALIDATION_REQUIRED_DEPENDENCY_ARTIFACT_IDS = (
    "cryptography-distribution",
    "numpy-distribution",
    "openssl-executable",
    "python-runtime-executable",
    "python-standard-library",
    "torch-distribution",
)
_REFERENCE_MINIMIZATION_VALIDATION_OPENSSL_EXECUTABLE = "/usr/bin/openssl"
_ED25519_SUBJECT_PUBLIC_KEY_INFO_PREFIX = bytes.fromhex("302a300506032b6570032100")
REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_RUNNER_REQUEST_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_validation_runner_request/2.0.0"
)
_REFERENCE_MINIMIZATION_VALIDATION_RUNNER_REQUEST_SCHEMA_ID = (
    REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_RUNNER_REQUEST_SCHEMA_ID
)
_BOOTSTRAP_REQUEST_FIELDS = {
    "schema_id",
    "reservation_root",
    "artifact_output_root",
    "authorization_nonce_sha256",
    "authorization_receipt",
    "review_attestation",
    "expected_implementation_author_identity_sha256",
    "network_isolation_attestation",
    "expected_code_commit_sha",
    "expected_runner_source_sha256",
    "expected_dependency_artifact_sha256_rows",
    "revoked_authorization_receipt_sha256s",
    "revoked_review_attestation_sha256s",
    "externally_conflicting_nonce_sha256s",
    "revoked_network_attestation_sha256s",
}
_SAFE_KEY_ID_CHARACTERS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
)


class _ReferenceMinimizationValidationBootstrapError(RuntimeError):
    """The interpreter did not establish the frozen import boundary."""


_CONTROLLED_INNER_FIXED_ENVIRONMENT = {
    "CUDA_VISIBLE_DEVICES": "",
    "HIP_VISIBLE_DEVICES": "",
    "HOME": "/nonexistent",
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "MKL_NUM_THREADS": "1",
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "PATH": "/usr/bin:/bin",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONNOUSERSITE": "1",
    "PYTHONPYCACHEPREFIX": "/dev/null",
    "ROCR_VISIBLE_DEVICES": "",
    "TZ": "UTC",
}


def reference_minimization_validation_bootstrap_path() -> str:
    """Return the canonical checked-out bootstrap path."""

    return os.path.realpath(__file__)


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
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap request is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _source_stat_signature(file_stat: os.stat_result) -> tuple[int, ...]:
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


def _require_source_directory_stat(file_stat: os.stat_result) -> None:
    if not stat.S_ISDIR(file_stat.st_mode):
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation source ancestry contains a non-directory"
        )


def _require_source_regular_file_stat(file_stat: os.stat_result) -> None:
    if (
        not stat.S_ISREG(file_stat.st_mode)
        or file_stat.st_nlink != 1
        or not 0
        <= file_stat.st_size
        <= REFERENCE_MINIMIZATION_VALIDATION_SOURCE_MAX_FILE_BYTES
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation source is not a bounded single-link regular file"
        )


def _canonical_source_absolute_path(raw_path: object, *, name: str) -> str:
    try:
        raw = os.fspath(raw_path)
    except TypeError as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
            f"{name} is invalid"
        ) from exc
    if (
        not isinstance(raw, str)
        or not raw
        or "\x00" in raw
        or not os.path.isabs(raw)
        or os.path.normpath(raw) != raw
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            f"{name} is not a canonical absolute path"
        )
    return raw


def _source_lstat_at(directory_fd: int, component: str) -> os.stat_result:
    return os.stat(component, dir_fd=directory_fd, follow_symlinks=False)


def _open_source_child_directory(parent_fd: int, component: str) -> int:
    if (
        not isinstance(component, str)
        or not component
        or component in {".", ".."}
        or os.sep in component
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation source directory component is invalid"
        )
    directory_flags = os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW
    path_before = _source_lstat_at(parent_fd, component)
    _require_source_directory_stat(path_before)
    next_fd = -1
    try:
        next_fd = os.open(component, directory_flags, dir_fd=parent_fd)
        opened = os.fstat(next_fd)
        path_after = _source_lstat_at(parent_fd, component)
        _require_source_directory_stat(opened)
        _require_source_directory_stat(path_after)
        if not (
            _source_stat_signature(path_before)
            == _source_stat_signature(opened)
            == _source_stat_signature(path_after)
        ):
            raise _ReferenceMinimizationValidationBootstrapError(
                "validation source directory changed while it was opened"
            )
        result = next_fd
        next_fd = -1
        return result
    except _ReferenceMinimizationValidationBootstrapError:
        raise
    except OSError as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation source directory cannot be opened securely"
        ) from exc
    finally:
        if next_fd >= 0:
            os.close(next_fd)


def _open_source_absolute_directory(raw_path: object) -> int:
    if not _SOURCE_PATH_PRIMITIVES_AVAILABLE:
        raise _ReferenceMinimizationValidationBootstrapError(
            "secure validation source traversal is unavailable"
        )
    path = _canonical_source_absolute_path(
        raw_path,
        name="validation source directory",
    )
    components = tuple(part for part in path.split(os.sep) if part)
    directory_flags = os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW
    current_fd = -1
    try:
        current_fd = os.open(os.sep, directory_flags)
        _require_source_directory_stat(os.fstat(current_fd))
        for component in components:
            next_fd = _open_source_child_directory(current_fd, component)
            os.close(current_fd)
            current_fd = next_fd
        result = current_fd
        current_fd = -1
        return result
    except _ReferenceMinimizationValidationBootstrapError:
        raise
    except OSError as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation source directory cannot be opened securely"
        ) from exc
    finally:
        if current_fd >= 0:
            os.close(current_fd)


def _read_source_file_at(directory_fd: int, name: str) -> bytes:
    if (
        not isinstance(name, str)
        or not name
        or name in {".", ".."}
        or os.sep in name
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation source file name is invalid"
        )
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    path_before = _source_lstat_at(directory_fd, name)
    _require_source_regular_file_stat(path_before)
    descriptor = -1
    try:
        descriptor = os.open(name, flags, dir_fd=directory_fd)
        before = os.fstat(descriptor)
        path_opened = _source_lstat_at(directory_fd, name)
        _require_source_regular_file_stat(before)
        _require_source_regular_file_stat(path_opened)
        if not (
            _source_stat_signature(path_before)
            == _source_stat_signature(before)
            == _source_stat_signature(path_opened)
        ):
            raise _ReferenceMinimizationValidationBootstrapError(
                "validation source changed before it was read"
            )
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, 1_048_576)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > REFERENCE_MINIMIZATION_VALIDATION_SOURCE_MAX_FILE_BYTES:
                raise _ReferenceMinimizationValidationBootstrapError(
                    "validation source file exceeds its byte bound"
                )
        after = os.fstat(descriptor)
        path_after = _source_lstat_at(directory_fd, name)
        _require_source_regular_file_stat(after)
        _require_source_regular_file_stat(path_after)
        if (
            total != before.st_size
            or _source_stat_signature(before) != _source_stat_signature(after)
            or _source_stat_signature(after) != _source_stat_signature(path_after)
        ):
            raise _ReferenceMinimizationValidationBootstrapError(
                "validation source changed while it was read"
            )
        return b"".join(chunks)
    except _ReferenceMinimizationValidationBootstrapError:
        raise
    except OSError as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation source cannot be read securely"
        ) from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _snapshot_source_directory(
    directory_fd: int,
    relative_parts: tuple[str, ...],
    source_by_relative_path: dict[str, bytes],
    counters: list[int],
) -> None:
    before = os.fstat(directory_fd)
    _require_source_directory_stat(before)
    try:
        names_before = tuple(sorted(os.listdir(directory_fd)))
    except OSError as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation source directory cannot be enumerated"
        ) from exc
    for name in names_before:
        if not isinstance(name, str) or name in {"", ".", ".."} or os.sep in name:
            raise _ReferenceMinimizationValidationBootstrapError(
                "validation source directory entry is invalid"
            )
        entry_stat = _source_lstat_at(directory_fd, name)
        if stat.S_ISDIR(entry_stat.st_mode):
            if name == "__pycache__":
                continue
            child_fd = _open_source_child_directory(directory_fd, name)
            try:
                _snapshot_source_directory(
                    child_fd,
                    (*relative_parts, name),
                    source_by_relative_path,
                    counters,
                )
            finally:
                os.close(child_fd)
            continue
        if not stat.S_ISREG(entry_stat.st_mode):
            raise _ReferenceMinimizationValidationBootstrapError(
                "validation source tree contains a symlink or special file"
            )
        if not name.endswith(".py"):
            continue
        payload = _read_source_file_at(directory_fd, name)
        relative_path = "/".join((*relative_parts, name))
        if relative_path in source_by_relative_path:
            raise _ReferenceMinimizationValidationBootstrapError(
                "validation source path is duplicated"
            )
        source_by_relative_path[relative_path] = payload
        counters[0] += 1
        counters[1] += len(payload)
        if (
            counters[0] > REFERENCE_MINIMIZATION_VALIDATION_SOURCE_MAX_FILES
            or counters[1] > REFERENCE_MINIMIZATION_VALIDATION_SOURCE_MAX_TOTAL_BYTES
        ):
            raise _ReferenceMinimizationValidationBootstrapError(
                "validation source snapshot exceeds its bounds"
            )
    try:
        names_after = tuple(sorted(os.listdir(directory_fd)))
        after = os.fstat(directory_fd)
    except OSError as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation source directory cannot be rechecked"
        ) from exc
    _require_source_directory_stat(after)
    if names_before != names_after or _source_stat_signature(
        before
    ) != _source_stat_signature(after):
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation source directory changed during snapshot"
        )


def _snapshot_reference_minimization_validation_sources(
    repository_root: str,
) -> tuple[str, types.MappingProxyType, tuple[int, ...]]:
    repository = _canonical_source_absolute_path(
        repository_root,
        name="validation repository root",
    )
    repository_fd = _open_source_absolute_directory(repository)
    package_fd = -1
    try:
        repository_identity = _source_stat_signature(os.fstat(repository_fd))
        package_fd = _open_source_child_directory(
            repository_fd,
            "betelgeuze_engine_v2",
        )
        sources: dict[str, bytes] = {}
        counters = [0, 0]
        _snapshot_source_directory(
            package_fd,
            ("betelgeuze_engine_v2",),
            sources,
            counters,
        )
    finally:
        if package_fd >= 0:
            os.close(package_fd)
        os.close(repository_fd)
    required_paths = {
        REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_RELATIVE_PATH,
        REFERENCE_MINIMIZATION_VALIDATION_DEPENDENCY_IDENTITY_RELATIVE_PATH,
        "betelgeuze_engine_v2/physics/reference_minimization_validation_runner.py",
    }
    if not required_paths.issubset(sources):
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation source snapshot is missing required execution sources"
        )
    rows = [
        {
            "path": relative_path,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "size": len(payload),
        }
        for relative_path, payload in sorted(sources.items())
    ]
    manifest_sha256 = _sha256(
        {
            "schema_id": REFERENCE_MINIMIZATION_VALIDATION_SOURCE_MANIFEST_SCHEMA_ID,
            "source_count": len(rows),
            "total_source_bytes": sum(int(row["size"]) for row in rows),
            "sources": rows,
        }
    )
    verification_fd = _open_source_absolute_directory(repository)
    try:
        if _source_stat_signature(os.fstat(verification_fd)) != repository_identity:
            raise _ReferenceMinimizationValidationBootstrapError(
                "validation repository root changed during source snapshot"
            )
    finally:
        os.close(verification_fd)
    return manifest_sha256, types.MappingProxyType(sources), repository_identity


def _module_record_from_relative_path(
    repository_root: str,
    relative_path: str,
    payload: bytes,
) -> tuple[str, str, bytes, bool]:
    parts = relative_path.split("/")
    if (
        not parts
        or parts[0] != "betelgeuze_engine_v2"
        or not parts[-1].endswith(".py")
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation source module path is invalid"
        )
    is_package = parts[-1] == "__init__.py"
    module_parts = parts[:-1] if is_package else (*parts[:-1], parts[-1][:-3])
    module_name = ".".join(module_parts)
    if not module_name:
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation source module name is invalid"
        )
    filename = os.path.join(repository_root, *parts)
    return module_name, filename, payload, is_package


class _VerifiedSourceLoader(importlib.abc.Loader):
    __slots__ = ("_filename", "_fullname", "_is_package", "_payload")

    def __init__(
        self,
        fullname: str,
        filename: str,
        payload: bytes,
        is_package: bool,
    ) -> None:
        self._fullname = fullname
        self._filename = filename
        self._payload = payload
        self._is_package = is_package

    def create_module(self, spec: object) -> None:
        del spec
        return None

    def exec_module(self, module: object) -> None:
        module.__file__ = self._filename
        module.__cached__ = None
        code = compile(
            self._payload,
            self._filename,
            "exec",
            dont_inherit=True,
            optimize=sys.flags.optimize,
        )
        exec(code, module.__dict__)

    def get_filename(self, fullname: str) -> str:
        if fullname != self._fullname:
            raise ImportError("verified source loader name mismatch")
        return self._filename

    def get_source(self, fullname: str) -> str:
        if fullname != self._fullname:
            raise ImportError("verified source loader name mismatch")
        return self._payload.decode("utf-8")

    def is_package(self, fullname: str) -> bool:
        if fullname != self._fullname:
            raise ImportError("verified source loader name mismatch")
        return self._is_package


class _VerifiedSourceFinder(importlib.abc.MetaPathFinder):
    __slots__ = (
        "_records",
        "_repository_identity",
        "_repository_root",
        "_sources",
        "finder_identity_sha256",
        "source_manifest_sha256",
    )

    def __init__(
        self,
        repository_root: str,
        source_manifest_sha256: str,
        sources: types.MappingProxyType,
        repository_identity: tuple[int, ...],
    ) -> None:
        records: dict[str, tuple[str, bytes, bool]] = {}
        for relative_path, payload in sources.items():
            module_name, filename, source, is_package = (
                _module_record_from_relative_path(
                    repository_root,
                    relative_path,
                    payload,
                )
            )
            if module_name in records:
                raise _ReferenceMinimizationValidationBootstrapError(
                    "validation source module name is duplicated"
                )
            records[module_name] = (filename, source, is_package)
        self._repository_root = repository_root
        self._repository_identity = repository_identity
        self._sources = sources
        self._records = types.MappingProxyType(records)
        self.source_manifest_sha256 = source_manifest_sha256
        self.finder_identity_sha256 = _sha256(
            {
                "schema_id": (
                    "betelgeuze.engine_v2_reference_minimization_validation_source_finder/"
                    "1.0.0"
                ),
                "source_manifest_sha256": source_manifest_sha256,
                "module_count": len(records),
            }
        )

    @property
    def repository_root(self) -> str:
        return self._repository_root

    def source_bytes_for_relative_path(self, relative_path: str) -> bytes:
        try:
            return self._sources[relative_path]
        except KeyError as exc:
            raise _ReferenceMinimizationValidationBootstrapError(
                "verified source path is unavailable"
            ) from exc

    def verify_repository_binding(self) -> None:
        descriptor = _open_source_absolute_directory(self._repository_root)
        try:
            observed = _source_stat_signature(os.fstat(descriptor))
        finally:
            os.close(descriptor)
        if observed != self._repository_identity:
            raise _ReferenceMinimizationValidationBootstrapError(
                "validation repository root changed after source snapshot"
            )

    def find_spec(
        self,
        fullname: str,
        path: object = None,
        target: object = None,
    ) -> object:
        del path, target
        record = self._records.get(fullname)
        if record is None:
            if fullname == "betelgeuze_engine_v2" or fullname.startswith(
                "betelgeuze_engine_v2."
            ):
                raise ModuleNotFoundError(
                    f"{fullname} is absent from the verified source snapshot"
                )
            return None
        filename, payload, is_package = record
        loader = _VerifiedSourceLoader(fullname, filename, payload, is_package)
        spec = importlib.machinery.ModuleSpec(
            fullname,
            loader,
            origin=filename,
            is_package=is_package,
        )
        if is_package:
            spec.submodule_search_locations = [
                f"<verified-source:{self.source_manifest_sha256}>/"
                f"{fullname.replace('.', '/')}"
            ]
        return spec


def _install_verified_source_finder(
    repository_root: str,
    source_manifest_sha256: str,
    sources: types.MappingProxyType,
    repository_identity: tuple[int, ...],
) -> _VerifiedSourceFinder:
    if any(
        name == "betelgeuze_engine_v2" or name.startswith("betelgeuze_engine_v2.")
        for name in sys.modules
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "Engine v2 was imported before source verification"
        )
    if hasattr(sys, REFERENCE_MINIMIZATION_VALIDATION_SOURCE_FINDER_ATTRIBUTE):
        raise _ReferenceMinimizationValidationBootstrapError(
            "verified source finder is already installed"
        )
    finder = _VerifiedSourceFinder(
        repository_root,
        source_manifest_sha256,
        sources,
        repository_identity,
    )
    sys.meta_path.insert(0, finder)
    setattr(
        sys,
        REFERENCE_MINIMIZATION_VALIDATION_SOURCE_FINDER_ATTRIBUTE,
        finder,
    )
    setattr(
        sys,
        REFERENCE_MINIMIZATION_VALIDATION_SOURCE_MANIFEST_ATTRIBUTE,
        source_manifest_sha256,
    )
    return finder


def _require_verified_source_finder() -> _VerifiedSourceFinder:
    finder = getattr(
        sys,
        REFERENCE_MINIMIZATION_VALIDATION_SOURCE_FINDER_ATTRIBUTE,
        None,
    )
    manifest = getattr(
        sys,
        REFERENCE_MINIMIZATION_VALIDATION_SOURCE_MANIFEST_ATTRIBUTE,
        None,
    )
    if (
        not isinstance(finder, _VerifiedSourceFinder)
        or finder not in sys.meta_path
        or manifest != finder.source_manifest_sha256
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "verified source finder is unavailable"
        )
    return finder


def _bounded_execution_source_sha256(source: str, *, deadline: float) -> str:
    """Hash one execution source after enforcing its cap before any read."""

    try:
        path_stat = os.lstat(source)
    except OSError as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation execution source is unavailable"
        ) from exc
    flags = os.O_RDONLY
    for flag_name in ("O_CLOEXEC", "O_NOFOLLOW"):
        if not hasattr(os, flag_name):
            raise _ReferenceMinimizationValidationBootstrapError(
                "secure validation execution source access is unavailable"
            )
        flags |= getattr(os, flag_name)
    try:
        descriptor = os.open(source, flags)
    except OSError as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation execution source cannot be opened securely"
        ) from exc
    try:
        before = os.fstat(descriptor)
        if (
            os.path.islink(source)
            or not stat.S_ISREG(path_stat.st_mode)
            or path_stat.st_nlink != 1
            or (path_stat.st_dev, path_stat.st_ino, path_stat.st_size)
            != (before.st_dev, before.st_ino, before.st_size)
            or before.st_size < 0
            or before.st_size
            > REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_EXECUTION_SOURCE_MAX_BYTES
        ):
            raise _ReferenceMinimizationValidationBootstrapError(
                "validation execution source violates its pre-read file policy"
            )
        digest = hashlib.sha256()
        observed = 0
        while True:
            if time.monotonic() >= deadline:
                raise _ReferenceMinimizationValidationBootstrapError(
                    "validation execution source deadline expired"
                )
            chunk = os.read(
                descriptor,
                min(
                    1024 * 1024,
                    before.st_size + 1 - observed,
                ),
            )
            if not chunk:
                break
            observed += len(chunk)
            if observed > before.st_size:
                raise _ReferenceMinimizationValidationBootstrapError(
                    "validation execution source grew while being measured"
                )
            digest.update(chunk)
        after = os.fstat(descriptor)
    except OSError as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation execution source cannot be measured"
        ) from exc
    finally:
        os.close(descriptor)
    if observed != before.st_size or (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    ) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation execution source changed while being measured"
        )
    return digest.hexdigest()


def reference_minimization_validation_execution_source_sha256() -> str:
    """Bind the stdlib bootstrap and runner into one authorization identity."""

    physics_root = os.path.dirname(reference_minimization_validation_bootstrap_path())
    source_rows: list[dict[str, str]] = []
    deadline = (
        time.monotonic()
        + REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_EXECUTION_SOURCE_MAX_WALL_SECONDS
    )
    finder = getattr(
        sys,
        REFERENCE_MINIMIZATION_VALIDATION_SOURCE_FINDER_ATTRIBUTE,
        None,
    )
    for relative_path in (
        REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_RELATIVE_PATH,
        REFERENCE_MINIMIZATION_VALIDATION_DEPENDENCY_IDENTITY_RELATIVE_PATH,
        REFERENCE_MINIMIZATION_VALIDATION_SOURCE_IDENTITY_RELATIVE_PATH,
        REFERENCE_MINIMIZATION_VALIDATION_NATIVE_RUNTIME_IDENTITY_RELATIVE_PATH,
        "betelgeuze_engine_v2/physics/reference_minimization_validation_runner.py",
    ):
        source = os.path.join(physics_root, os.path.basename(relative_path))
        if isinstance(finder, _VerifiedSourceFinder):
            source_sha256 = hashlib.sha256(
                finder.source_bytes_for_relative_path(relative_path)
            ).hexdigest()
        else:
            source_sha256 = _bounded_execution_source_sha256(
                source,
                deadline=deadline,
            )
        source_rows.append(
            {
                "path": relative_path,
                "sha256": source_sha256,
            }
        )
    return hashlib.sha256(
        _canonical_bytes(
            {
                "schema_id": (
                    "betelgeuze.engine_v2_reference_minimization_validation_execution_sources/4.0.0"
                ),
                "sources": source_rows,
            }
        )
    ).hexdigest()


def _require_observed_dependency_artifact_rows_before_import(
    repository_root: str,
    dependency_roots: tuple[str, ...],
    request: dict[str, object],
    *,
    deadline: float | None = None,
    signed_expected: dict[str, str] | None = None,
) -> None:
    if deadline is not None:
        _require_preflight_time(deadline)
    request_expected = _require_dependency_artifact_row_mapping(
        request.get("expected_dependency_artifact_sha256_rows"),
        name="bootstrap request",
    )
    if signed_expected is None:
        signed_expected = request_expected
    else:
        signed_expected = _require_dependency_artifact_row_mapping(
            signed_expected,
            name="signed authorization",
        )
        if request_expected != signed_expected:
            raise _ReferenceMinimizationValidationBootstrapError(
                "bootstrap request dependency rows do not match the signed authorization"
            )
    helper_path = os.path.join(
        repository_root,
        REFERENCE_MINIMIZATION_VALIDATION_DEPENDENCY_IDENTITY_RELATIVE_PATH,
    )
    try:
        finder = getattr(
            sys,
            REFERENCE_MINIMIZATION_VALIDATION_SOURCE_FINDER_ATTRIBUTE,
            None,
        )
        if finder is None:
            try:
                finder = _require_verified_source_finder()
            except _ReferenceMinimizationValidationBootstrapError:
                finder = None
        helper_name = (
            "_betelgeuze_reference_minimization_validation_dependency_identity"
        )
        if finder is not None:
            if finder.repository_root != repository_root:
                raise _ReferenceMinimizationValidationBootstrapError(
                    "verified dependency helper repository is cross-wired"
                )
            helper_source = finder.source_bytes_for_relative_path(
                REFERENCE_MINIMIZATION_VALIDATION_DEPENDENCY_IDENTITY_RELATIVE_PATH
            )
            loader = _VerifiedSourceLoader(
                helper_name,
                helper_path,
                helper_source,
                False,
            )
            spec = importlib.util.spec_from_loader(
                helper_name,
                loader,
                origin=helper_path,
            )
        else:
            spec = importlib.util.spec_from_file_location(
                helper_name,
                helper_path,
            )
        if spec is None or spec.loader is None:
            raise ImportError("dependency identity loader is unavailable")
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        observer = (
            helper.observed_reference_minimization_validation_dependency_artifact_sha256_rows
        )
        if deadline is None:
            observed = observer(dependency_roots)
        else:
            observed = observer(dependency_roots, deadline=deadline)
    except Exception as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap dependency bytes cannot be measured"
        ) from exc
    if observed != signed_expected:
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap dependency bytes do not match the signed authorization"
        )


def _require_source_manifest_before_import(
    repository_root: str,
    expected_code_commit_sha: str,
    *,
    deadline: float,
) -> dict[str, object]:
    """Bind every package file to the self-verified signed Git tree."""

    _require_preflight_time(deadline)
    helper_path = os.path.join(
        repository_root,
        REFERENCE_MINIMIZATION_VALIDATION_SOURCE_IDENTITY_RELATIVE_PATH,
    )
    try:
        finder = _require_verified_source_finder()
        if finder.repository_root != repository_root:
            raise _ReferenceMinimizationValidationBootstrapError(
                "verified source identity helper repository is cross-wired"
            )
        helper_name = "_betelgeuze_minimization_validation_source_identity"
        loader = _VerifiedSourceLoader(
            helper_name,
            helper_path,
            finder.source_bytes_for_relative_path(
                REFERENCE_MINIMIZATION_VALIDATION_SOURCE_IDENTITY_RELATIVE_PATH
            ),
            False,
        )
        spec = importlib.util.spec_from_loader(
            helper_name,
            loader,
            origin=helper_path,
        )
        if spec is None or spec.loader is None:
            raise ImportError("source identity loader is unavailable")
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        document = helper.observed_validation_source_manifest_document(
            repository_root,
            expected_code_commit_sha,
            deadline=deadline,
        )
        return helper.require_validation_source_manifest_document(document)
    except Exception as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap source bytes do not match the signed Git tree"
        ) from exc


def _require_root_owned_read_only_directory(raw_path: str) -> str:
    if not raw_path or not os.path.isabs(raw_path) or os.pathsep in raw_path:
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap path is invalid"
        )
    resolved = os.path.realpath(raw_path)
    if resolved != os.path.abspath(raw_path):
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap path is not canonical"
        )
    current = resolved
    while current != os.path.dirname(current):
        try:
            file_stat = os.lstat(current)
        except OSError as exc:
            raise _ReferenceMinimizationValidationBootstrapError(
                "bootstrap path is unavailable"
            ) from exc
        if (
            not stat.S_ISDIR(file_stat.st_mode)
            or file_stat.st_uid != 0
            or stat.S_IMODE(file_stat.st_mode) & 0o022
        ):
            raise _ReferenceMinimizationValidationBootstrapError(
                "bootstrap path is not root-owned read-only storage"
            )
        current = os.path.dirname(current)
    return resolved


def _require_preflight_time(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0.0:
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap preflight deadline expired"
        )
    return remaining


def _require_canonical_preflight_deadline(value: object) -> float:
    if not isinstance(value, str) or not value or len(value) > 64:
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap preflight deadline is invalid"
        )
    try:
        deadline = float.fromhex(value)
    except ValueError as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap preflight deadline is invalid"
        ) from exc
    if (
        deadline != deadline
        or deadline in {float("inf"), float("-inf")}
        or deadline.hex() != value
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap preflight deadline is not canonical"
        )
    remaining = _require_preflight_time(deadline)
    if (
        remaining
        > REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_PREFLIGHT_MAX_WALL_SECONDS
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap preflight deadline exceeds its frozen bound"
        )
    return deadline


def _require_immutable_source_snapshot(
    repository_root: str,
    *,
    deadline: float,
) -> str:
    """Reject any package tree the executing uid could replace or rewrite."""

    _require_preflight_time(deadline)
    if os.geteuid() == 0:
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation source snapshot must execute under a non-root uid"
        )
    resolved_root = _require_root_owned_read_only_directory(repository_root)
    package_root = os.path.join(resolved_root, "betelgeuze_engine_v2")
    _require_root_owned_read_only_directory(package_root)
    entry_count = 0
    pending = [package_root]
    while pending:
        _require_preflight_time(deadline)
        directory = pending.pop()
        try:
            with os.scandir(directory) as stream:
                names: list[str] = []
                for entry in stream:
                    _require_preflight_time(deadline)
                    entry_count += 1
                    if (
                        entry_count
                        > REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_SOURCE_TREE_MAX_ENTRIES
                    ):
                        raise _ReferenceMinimizationValidationBootstrapError(
                            "validation source snapshot exceeds its entry bound"
                        )
                    name = entry.name
                    path = os.path.join(directory, name)
                    try:
                        relative = os.path.relpath(path, package_root).encode("utf-8")
                    except UnicodeError as exc:
                        raise _ReferenceMinimizationValidationBootstrapError(
                            "validation source snapshot path is not canonical UTF-8"
                        ) from exc
                    if (
                        len(relative)
                        > REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_SOURCE_TREE_MAX_PATH_BYTES
                    ):
                        raise _ReferenceMinimizationValidationBootstrapError(
                            "validation source snapshot path exceeds its bound"
                        )
                    names.append(name)
        except OSError as exc:
            raise _ReferenceMinimizationValidationBootstrapError(
                "validation source snapshot cannot be enumerated"
            ) from exc
        child_directories: list[str] = []
        for name in sorted(names):
            path = os.path.join(directory, name)
            try:
                file_stat = os.lstat(path)
            except OSError as exc:
                raise _ReferenceMinimizationValidationBootstrapError(
                    "validation source snapshot entry is unavailable"
                ) from exc
            if (
                os.path.islink(path)
                or file_stat.st_uid != 0
                or stat.S_IMODE(file_stat.st_mode) & 0o022
            ):
                raise _ReferenceMinimizationValidationBootstrapError(
                    "validation source snapshot is not root-owned read-only storage"
                )
            if name == "__pycache__" or name.endswith(".pyc"):
                raise _ReferenceMinimizationValidationBootstrapError(
                    "validation source snapshot contains bytecode cache payload"
                )
            if stat.S_ISDIR(file_stat.st_mode):
                child_directories.append(path)
                continue
            if not stat.S_ISREG(file_stat.st_mode) or file_stat.st_nlink != 1:
                raise _ReferenceMinimizationValidationBootstrapError(
                    "validation source snapshot contains an unsafe entry"
                )
        pending.extend(reversed(child_directories))
    if entry_count == 0:
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation source snapshot is empty"
        )
    return resolved_root


def _parse_canonical_seed(
    value: object,
    *,
    name: str,
    maximum: int,
) -> int:
    if not isinstance(value, str) or not value.isascii() or not value.isdigit():
        raise _ReferenceMinimizationValidationBootstrapError(
            f"validation bootstrap {name} must be a canonical ASCII integer"
        )
    parsed = int(value)
    if not 0 <= parsed <= maximum or str(parsed) != value:
        raise _ReferenceMinimizationValidationBootstrapError(
            f"validation bootstrap {name} is outside the frozen range"
        )
    return parsed


def reference_minimization_validation_controlled_inner_environment(
    *,
    preflight_deadline: float | None = None,
) -> dict[str, str]:
    """Return the exact secret-free environment for the seeded inner process."""

    python_hash_seed = _parse_canonical_seed(
        os.environ.get("PYTHONHASHSEED"),
        name="PYTHONHASHSEED",
        maximum=2**32 - 1,
    )
    application_seed = _parse_canonical_seed(
        os.environ.get(REFERENCE_MINIMIZATION_VALIDATION_APPLICATION_SEED_ENV),
        name=REFERENCE_MINIMIZATION_VALIDATION_APPLICATION_SEED_ENV,
        maximum=2**63 - 1,
    )
    if preflight_deadline is None:
        raw_deadline = os.environ.get(
            REFERENCE_MINIMIZATION_VALIDATION_CONTROLLED_INNER_PREFLIGHT_DEADLINE_ENV
        )
        preflight_deadline = (
            _require_canonical_preflight_deadline(raw_deadline)
            if raw_deadline is not None
            else time.monotonic()
            + REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_PREFLIGHT_MAX_WALL_SECONDS
        )
    _require_preflight_time(preflight_deadline)
    return {
        **_CONTROLLED_INNER_FIXED_ENVIRONMENT,
        "PYTHONHASHSEED": str(python_hash_seed),
        REFERENCE_MINIMIZATION_VALIDATION_APPLICATION_SEED_ENV: str(application_seed),
        REFERENCE_MINIMIZATION_VALIDATION_CONTROLLED_INNER_STAGE_ENV: (
            REFERENCE_MINIMIZATION_VALIDATION_CONTROLLED_INNER_STATE
        ),
        REFERENCE_MINIMIZATION_VALIDATION_CONTROLLED_INNER_PREFLIGHT_DEADLINE_ENV: (
            preflight_deadline.hex()
        ),
    }


def _require_trusted_root_working_directory() -> str:
    try:
        root_stat = os.lstat("/")
    except OSError as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap trusted working directory is unavailable"
        ) from exc
    if (
        not stat.S_ISDIR(root_stat.st_mode)
        or root_stat.st_uid != 0
        or stat.S_IMODE(root_stat.st_mode) & 0o022
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap trusted working directory is invalid"
        )
    return "/"


def _require_trusted_running_interpreter() -> str:
    raw_executable = sys.executable
    if not raw_executable or not os.path.isabs(raw_executable):
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap Python executable is invalid"
        )
    executable = os.path.realpath(raw_executable)
    if executable != os.path.abspath(executable):
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap Python executable is not canonical"
        )
    try:
        executable_stat = os.lstat(executable)
        running_stat = os.stat("/proc/self/exe")
    except OSError as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap Python executable is unavailable"
        ) from exc
    if (
        not stat.S_ISREG(executable_stat.st_mode)
        or executable_stat.st_uid != 0
        or stat.S_IMODE(executable_stat.st_mode) & 0o022
        or executable_stat.st_nlink != 1
        or (executable_stat.st_dev, executable_stat.st_ino)
        != (running_stat.st_dev, running_stat.st_ino)
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap Python executable is not trusted"
        )
    _require_root_owned_read_only_directory(os.path.dirname(executable))
    _require_trusted_root_working_directory()
    return executable


def _read_process_argv() -> tuple[str, ...]:
    try:
        with open("/proc/self/cmdline", "rb") as stream:
            raw = stream.read(
                REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_PROCESS_ARGV_MAX_BYTES + 1
            )
        tokens = raw.rstrip(b"\0").split(b"\0")
        decoded = tuple(token.decode("utf-8") for token in tokens)
    except (OSError, UnicodeDecodeError) as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap process argv is unavailable"
        ) from exc
    if (
        len(raw) > REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_PROCESS_ARGV_MAX_BYTES
        or not raw.endswith(b"\0")
        or not decoded
        or any(not token for token in decoded)
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap process argv is invalid"
        )
    return decoded


def _trusted_standard_library_roots() -> tuple[str, ...]:
    roots: list[str] = []
    for raw_path in sys.path:
        if not raw_path or not os.path.isdir(raw_path):
            continue
        resolved = _require_root_owned_read_only_directory(raw_path)
        if resolved not in roots:
            roots.append(resolved)
    if not roots:
        raise _ReferenceMinimizationValidationBootstrapError(
            "trusted standard-library roots are unavailable"
        )
    return tuple(roots)


def _trusted_dependency_roots() -> tuple[str, ...]:
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    configured = sysconfig.get_paths()
    candidates = (
        configured.get("purelib"),
        configured.get("platlib"),
        f"/usr/local/lib/{version}/site-packages",
        f"/usr/local/lib/{version}/dist-packages",
        f"/usr/lib/{version}/site-packages",
        f"/usr/lib/{version}/dist-packages",
        "/usr/lib/python3/dist-packages",
    )
    roots: list[str] = []
    for raw_path in candidates:
        if not isinstance(raw_path, str) or not os.path.isdir(raw_path):
            continue
        try:
            resolved = _require_root_owned_read_only_directory(raw_path)
        except _ReferenceMinimizationValidationBootstrapError:
            continue
        if resolved not in roots:
            roots.append(resolved)
    if not roots:
        raise _ReferenceMinimizationValidationBootstrapError(
            "trusted dependency roots are unavailable"
        )
    return tuple(roots)


def _read_bootstrap_request() -> tuple[bytes, dict[str, object]]:
    input_stream = getattr(sys.stdin, "buffer", sys.stdin)
    deadline = _require_canonical_preflight_deadline(
        os.environ.get(
            REFERENCE_MINIMIZATION_VALIDATION_CONTROLLED_INNER_PREFLIGHT_DEADLINE_ENV
        )
    )
    try:
        descriptor = input_stream.fileno()
        poller = select.poll()
        poller.register(
            descriptor,
            select.POLLIN | select.POLLHUP | select.POLLERR | select.POLLNVAL,
        )
    except (AttributeError, OSError, ValueError) as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap request cannot be read"
        ) from exc
    raw_buffer = bytearray()
    while (
        len(raw_buffer) <= REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_MAX_REQUEST_BYTES
    ):
        remaining = _require_preflight_time(deadline)
        timeout_ms = max(1, int(remaining * 1000.0))
        try:
            events = poller.poll(timeout_ms)
        except OSError as exc:
            raise _ReferenceMinimizationValidationBootstrapError(
                "validation bootstrap request cannot be polled"
            ) from exc
        if not events:
            continue
        if any(mask & select.POLLNVAL for _, mask in events):
            raise _ReferenceMinimizationValidationBootstrapError(
                "validation bootstrap request descriptor is invalid"
            )
        try:
            chunk = os.read(
                descriptor,
                min(
                    65_536,
                    REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_MAX_REQUEST_BYTES
                    + 1
                    - len(raw_buffer),
                ),
            )
        except OSError as exc:
            raise _ReferenceMinimizationValidationBootstrapError(
                "validation bootstrap request cannot be read"
            ) from exc
        if not chunk:
            break
        raw_buffer.extend(chunk)
        newline = raw_buffer.find(b"\n")
        if newline >= 0:
            if newline != len(raw_buffer) - 1:
                raise _ReferenceMinimizationValidationBootstrapError(
                    "validation bootstrap request framing is invalid"
                )
            break
    raw = bytes(raw_buffer)
    if (
        not raw
        or len(raw) > REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_MAX_REQUEST_BYTES
        or not raw.endswith(b"\n")
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap request framing is invalid"
        )

    def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise _ReferenceMinimizationValidationBootstrapError(
                    "validation bootstrap request contains duplicate fields"
                )
            result[key] = value
        return result

    try:
        request = json.loads(
            raw[:-1].decode("ascii"),
            object_pairs_hook=reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap request is not ASCII JSON"
        ) from exc
    if (
        not isinstance(request, dict)
        or _canonical_bytes(request) + b"\n" != raw
        or set(request) != _BOOTSTRAP_REQUEST_FIELDS
        or request.get("schema_id")
        != REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_RUNNER_REQUEST_SCHEMA_ID
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap request is not the exact canonical schema"
        )
    return raw, request


def _require_lower_hex(value: object, *, length: int, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != length
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise _ReferenceMinimizationValidationBootstrapError(f"{name} is invalid")
    return value


def _require_key_id(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 128
        or any(character not in _SAFE_KEY_ID_CHARACTERS for character in value)
    ):
        raise _ReferenceMinimizationValidationBootstrapError(f"{name} is invalid")
    return value


def _require_string_sequence(value: object, *, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise _ReferenceMinimizationValidationBootstrapError(
            f"{name} must be a JSON string array"
        )
    return tuple(value)


def _require_sorted_unique_digest_sequence(
    value: object,
    *,
    name: str,
) -> tuple[str, ...]:
    rows = _require_string_sequence(value, name=name)
    normalized = tuple(
        _require_lower_hex(item, length=64, name=name) for item in rows
    )
    if normalized != tuple(sorted(set(normalized))):
        raise _ReferenceMinimizationValidationBootstrapError(
            f"{name} must be uniquely sorted"
        )
    return normalized


def _require_sorted_unique_key_id_sequence(
    value: object,
    *,
    name: str,
) -> tuple[str, ...]:
    rows = _require_string_sequence(value, name=name)
    normalized = tuple(_require_key_id(item, name=name) for item in rows)
    if normalized != tuple(sorted(set(normalized))):
        raise _ReferenceMinimizationValidationBootstrapError(
            f"{name} must be uniquely sorted"
        )
    return normalized


def _require_embedded_receipt_sha256(
    value: object,
    *,
    field_name: str,
    name: str,
) -> str:
    if not isinstance(value, dict):
        raise _ReferenceMinimizationValidationBootstrapError(f"{name} is invalid")
    return _require_lower_hex(
        value.get(field_name),
        length=64,
        name=f"{name} {field_name}",
    )


def _require_trusted_revocation_state(
    request: dict[str, object],
    trust_payload: dict[str, object],
) -> dict[str, tuple[str, ...]]:
    state = {
        "revoked_authorization_receipt_sha256s": (
            _require_sorted_unique_digest_sequence(
                trust_payload.get("revoked_authorization_receipt_sha256s"),
                name="trusted revoked authorization receipts",
            )
        ),
        "revoked_review_attestation_sha256s": (
            _require_sorted_unique_digest_sequence(
                trust_payload.get("revoked_review_attestation_sha256s"),
                name="trusted revoked review attestations",
            )
        ),
        "externally_conflicting_nonce_sha256s": (
            _require_sorted_unique_digest_sequence(
                trust_payload.get("externally_conflicting_nonce_sha256s"),
                name="trusted externally conflicting nonces",
            )
        ),
        "revoked_network_attestation_sha256s": (
            _require_sorted_unique_digest_sequence(
                trust_payload.get("revoked_network_attestation_sha256s"),
                name="trusted revoked network attestations",
            )
        ),
        "superseded_operator_key_ids": _require_sorted_unique_key_id_sequence(
            trust_payload.get("superseded_operator_key_ids"),
            name="trusted superseded operator keys",
        ),
        "superseded_reviewer_key_ids": _require_sorted_unique_key_id_sequence(
            trust_payload.get("superseded_reviewer_key_ids"),
            name="trusted superseded reviewer keys",
        ),
    }
    for request_field in (
        "revoked_authorization_receipt_sha256s",
        "revoked_review_attestation_sha256s",
        "externally_conflicting_nonce_sha256s",
        "revoked_network_attestation_sha256s",
    ):
        request_rows = _require_sorted_unique_digest_sequence(
            request.get(request_field),
            name=f"bootstrap request {request_field}",
        )
        if request_rows != state[request_field]:
            raise _ReferenceMinimizationValidationBootstrapError(
                "bootstrap request revocation state does not match the trusted store"
            )
    nonce = _require_lower_hex(
        request.get("authorization_nonce_sha256"),
        length=64,
        name="bootstrap request authorization nonce",
    )
    if nonce in state["externally_conflicting_nonce_sha256s"]:
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap authorization nonce is externally conflicting"
        )
    review = request.get("review_attestation")
    review_sha256 = _require_embedded_receipt_sha256(
        review,
        field_name="attestation_sha256",
        name="bootstrap review attestation",
    )
    if (
        not isinstance(review, dict)
        or review.get("schema_id")
        != trust_payload.get("minimum_review_attestation_schema_id")
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap review attestation schema is below the trusted minimum"
        )
    if review_sha256 in state["revoked_review_attestation_sha256s"]:
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap review attestation is externally revoked"
        )
    network = request.get("network_isolation_attestation")
    network_sha256 = _require_embedded_receipt_sha256(
        network,
        field_name="attestation_sha256",
        name="bootstrap network attestation",
    )
    if (
        not isinstance(network, dict)
        or network.get("schema_id")
        != _REFERENCE_MINIMIZATION_VALIDATION_NETWORK_ATTESTATION_SCHEMA_ID
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap network attestation schema is unsupported"
        )
    if network_sha256 in state["revoked_network_attestation_sha256s"]:
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap network attestation is externally revoked"
        )
    return state


def _require_dependency_artifact_row_mapping(
    value: object,
    *,
    name: str,
) -> dict[str, str]:
    if not isinstance(value, dict):
        raise _ReferenceMinimizationValidationBootstrapError(
            f"{name} dependency artifact rows are invalid"
        )
    rows: dict[str, str] = {}
    for artifact_id, digest in value.items():
        if not isinstance(artifact_id, str) or artifact_id in rows:
            raise _ReferenceMinimizationValidationBootstrapError(
                f"{name} dependency artifact rows are invalid"
            )
        rows[artifact_id] = _require_lower_hex(
            digest,
            length=64,
            name=f"{name} dependency {artifact_id}",
        )
    if tuple(sorted(rows)) != (
        _REFERENCE_MINIMIZATION_VALIDATION_REQUIRED_DEPENDENCY_ARTIFACT_IDS
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            f"{name} dependency artifact row schema is invalid"
        )
    return rows


def _require_signed_dependency_artifact_rows(value: object) -> dict[str, str]:
    if not isinstance(value, list):
        raise _ReferenceMinimizationValidationBootstrapError(
            "signed authorization dependency artifact rows are invalid"
        )
    rows: dict[str, str] = {}
    for row in value:
        if (
            not isinstance(row, dict)
            or set(row) != {"artifact_id", "sha256"}
            or not isinstance(row.get("artifact_id"), str)
        ):
            raise _ReferenceMinimizationValidationBootstrapError(
                "signed authorization dependency artifact rows are invalid"
            )
        artifact_id = row["artifact_id"]
        if artifact_id in rows:
            raise _ReferenceMinimizationValidationBootstrapError(
                "signed authorization dependency artifact rows are duplicated"
            )
        rows[artifact_id] = _require_lower_hex(
            row.get("sha256"),
            length=64,
            name=f"signed authorization dependency {artifact_id}",
        )
    return _require_dependency_artifact_row_mapping(
        rows,
        name="signed authorization",
    )


def _require_external_private_root(
    value: object,
    *,
    repository_root: str,
    name: str,
) -> str:
    if not isinstance(value, str) or not value or not os.path.isabs(value):
        raise _ReferenceMinimizationValidationBootstrapError(f"{name} is not absolute")
    candidate = os.path.abspath(value)
    resolved = os.path.realpath(value)
    try:
        file_stat = os.lstat(value)
        common = os.path.commonpath((resolved, repository_root))
    except (OSError, ValueError) as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
            f"{name} is unavailable"
        ) from exc
    if (
        candidate != resolved
        or not stat.S_ISDIR(file_stat.st_mode)
        or file_stat.st_uid != os.geteuid()
        or stat.S_IMODE(file_stat.st_mode) != 0o700
        or common in {resolved, repository_root}
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            f"{name} must be private and outside the checkout"
        )
    return resolved


def _open_bootstrap_trust_store() -> int:
    required_flags = ("O_NOFOLLOW", "O_CLOEXEC", "O_DIRECTORY", "O_NONBLOCK")
    if (
        os.name != "posix"
        or any(not hasattr(os, name) for name in required_flags)
        or os.open not in os.supports_dir_fd
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "secure bootstrap trust-store access is unavailable"
        )
    path = REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_TRUST_STORE_PATH
    if not os.path.isabs(path) or os.path.normpath(path) != path:
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap trust-store path is invalid"
        )
    components = tuple(part for part in path.split(os.sep) if part)
    if len(components) < 2:
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap trust-store path is invalid"
        )
    directory_flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_DIRECTORY
    current_fd = -1
    file_fd = -1
    try:
        current_fd = os.open(os.sep, directory_flags)
        for component in components[:-1]:
            directory_stat = os.fstat(current_fd)
            if (
                not stat.S_ISDIR(directory_stat.st_mode)
                or directory_stat.st_uid != 0
                or stat.S_IMODE(directory_stat.st_mode) & 0o022
            ):
                raise _ReferenceMinimizationValidationBootstrapError(
                    "bootstrap trust-store directory policy failed"
                )
            next_fd = os.open(component, directory_flags, dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
        directory_stat = os.fstat(current_fd)
        if (
            not stat.S_ISDIR(directory_stat.st_mode)
            or directory_stat.st_uid != 0
            or stat.S_IMODE(directory_stat.st_mode) & 0o022
        ):
            raise _ReferenceMinimizationValidationBootstrapError(
                "bootstrap trust-store directory policy failed"
            )
        file_fd = os.open(
            components[-1],
            os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=current_fd,
        )
        file_stat = os.fstat(file_fd)
        if (
            not stat.S_ISREG(file_stat.st_mode)
            or file_stat.st_uid != 0
            or stat.S_IMODE(file_stat.st_mode) != 0o600
            or file_stat.st_nlink != 1
            or not (
                0
                < file_stat.st_size
                <= REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_TRUST_STORE_MAX_BYTES
            )
        ):
            raise _ReferenceMinimizationValidationBootstrapError(
                "bootstrap trust-store file policy failed"
            )
        result = file_fd
        file_fd = -1
        return result
    except _ReferenceMinimizationValidationBootstrapError:
        raise
    except (OSError, ValueError) as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap trust store cannot be opened securely"
        ) from exc
    finally:
        if file_fd >= 0:
            os.close(file_fd)
        if current_fd >= 0:
            os.close(current_fd)


def _load_bootstrap_trust_store_payload() -> dict[str, object]:
    descriptor = _open_bootstrap_trust_store()
    try:
        before = os.fstat(descriptor)
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, 8192)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_TRUST_STORE_MAX_BYTES:
                raise _ReferenceMinimizationValidationBootstrapError(
                    "bootstrap trust store exceeds the size limit"
                )
        after = os.fstat(descriptor)
    except _ReferenceMinimizationValidationBootstrapError:
        raise
    except OSError as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap trust store cannot be read securely"
        ) from exc
    finally:
        os.close(descriptor)
    raw = b"".join(chunks)
    if (
        not stat.S_ISREG(before.st_mode)
        or before.st_uid != 0
        or stat.S_IMODE(before.st_mode) != 0o600
        or before.st_nlink != 1
        or (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        or len(raw) != before.st_size
        or not raw.endswith(b"\n")
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap trust store changed or violates the file policy"
        )

    def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise _ReferenceMinimizationValidationBootstrapError(
                    "bootstrap trust store contains duplicate fields"
                )
            result[key] = value
        return result

    try:
        payload = json.loads(
            raw[:-1].decode("ascii"),
            object_pairs_hook=reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap trust store is not ASCII JSON"
        ) from exc
    if (
        not isinstance(payload, dict)
        or set(payload) != _REFERENCE_MINIMIZATION_VALIDATION_TRUST_STORE_FIELDS
        or payload.get("schema_id")
        != _REFERENCE_MINIMIZATION_VALIDATION_TRUST_STORE_SCHEMA_ID
        or not isinstance(payload.get("reviewer_keys"), list)
        or not isinstance(payload.get("operator_keys"), list)
        or payload.get("minimum_authorization_receipt_schema_id")
        != _REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_RECEIPT_SCHEMA_ID
        or payload.get("minimum_review_attestation_schema_id")
        != _REFERENCE_MINIMIZATION_VALIDATION_REVIEW_ATTESTATION_SCHEMA_ID
        or _canonical_bytes(payload) + b"\n" != raw
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap trust store is not the exact canonical schema"
        )
    reviewer_ids = tuple(
        row.get("key_id")
        for row in payload["reviewer_keys"]
        if isinstance(row, dict)
    )
    operator_ids = tuple(
        row.get("key_id")
        for row in payload["operator_keys"]
        if isinstance(row, dict)
    )
    if reviewer_ids != tuple(sorted(set(reviewer_ids))) or operator_ids != tuple(
        sorted(set(operator_ids))
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap trust-store active key ids must be uniquely sorted"
        )
    superseded_reviewers = _require_sorted_unique_key_id_sequence(
        payload.get("superseded_reviewer_key_ids"),
        name="trusted superseded reviewer keys",
    )
    superseded_operators = _require_sorted_unique_key_id_sequence(
        payload.get("superseded_operator_key_ids"),
        name="trusted superseded operator keys",
    )
    if set(reviewer_ids).intersection(superseded_reviewers) or set(
        operator_ids
    ).intersection(superseded_operators):
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap trust store contains active superseded keys"
        )
    return payload


def _load_bootstrap_operator_keys(
    payload: dict[str, object] | None = None,
) -> dict[str, tuple[str, bytes]]:
    if payload is None:
        payload = _load_bootstrap_trust_store_payload()
    raw_rows = payload.get("operator_keys")
    if not isinstance(raw_rows, list):
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap operator keys are invalid"
        )
    result: dict[str, tuple[str, bytes]] = {}
    for row in raw_rows:
        if not isinstance(row, dict) or set(row) != {
            "key_id",
            "operator_identity_sha256",
            "verification_key_hex",
        }:
            raise _ReferenceMinimizationValidationBootstrapError(
                "bootstrap operator key fields are invalid"
            )
        key_id = _require_key_id(
            row.get("key_id"),
            name="bootstrap operator key id",
        )
        identity = _require_lower_hex(
            row.get("operator_identity_sha256"),
            length=64,
            name="bootstrap operator identity",
        )
        key_hex = _require_lower_hex(
            row.get("verification_key_hex"),
            length=64,
            name="bootstrap operator verification key",
        )
        if key_id in result:
            raise _ReferenceMinimizationValidationBootstrapError(
                "bootstrap operator key ids are duplicated"
            )
        result[key_id] = (identity, bytes.fromhex(key_hex))
    if not result:
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap operator keys are unavailable"
        )
    return result


def _require_trusted_root_executable(path: str, *, name: str) -> str:
    try:
        file_stat = os.lstat(path)
    except OSError as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
            f"validation bootstrap {name} is unavailable"
        ) from exc
    if (
        os.path.islink(path)
        or not stat.S_ISREG(file_stat.st_mode)
        or file_stat.st_uid != 0
        or stat.S_IMODE(file_stat.st_mode) & 0o022
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            f"validation bootstrap {name} is not trusted"
        )
    return path


def _write_all(descriptor: int, payload: bytes) -> None:
    remaining = memoryview(payload)
    while remaining:
        written = os.write(descriptor, remaining)
        if written <= 0:
            raise OSError("secure bootstrap memory file write failed")
        remaining = remaining[written:]


def _verify_ed25519_with_trusted_openssl(
    message: bytes,
    signature_hex: object,
    public_key: bytes,
) -> bool:
    if (
        not isinstance(signature_hex, str)
        or len(signature_hex) != 128
        or any(character not in "0123456789abcdef" for character in signature_hex)
        or not isinstance(public_key, bytes)
        or len(public_key) != 32
        or not hasattr(os, "memfd_create")
    ):
        return False
    executable = _require_trusted_root_executable(
        _REFERENCE_MINIMIZATION_VALIDATION_OPENSSL_EXECUTABLE,
        name="OpenSSL",
    )
    message_descriptor = -1
    key_descriptor = -1
    signature_descriptor = -1
    try:
        message_descriptor = os.memfd_create("ed25519-message", flags=0)
        key_descriptor = os.memfd_create("ed25519-public-key", flags=0)
        signature_descriptor = os.memfd_create("ed25519-signature", flags=0)
        _write_all(message_descriptor, message)
        _write_all(
            key_descriptor,
            _ED25519_SUBJECT_PUBLIC_KEY_INFO_PREFIX + public_key,
        )
        _write_all(signature_descriptor, bytes.fromhex(signature_hex))
        os.lseek(message_descriptor, 0, os.SEEK_SET)
        os.lseek(key_descriptor, 0, os.SEEK_SET)
        os.lseek(signature_descriptor, 0, os.SEEK_SET)
        completed = subprocess.run(
            [
                executable,
                "pkeyutl",
                "-verify",
                "-pubin",
                "-keyform",
                "DER",
                "-inkey",
                f"/proc/self/fd/{key_descriptor}",
                "-rawin",
                "-in",
                f"/proc/self/fd/{message_descriptor}",
                "-sigfile",
                f"/proc/self/fd/{signature_descriptor}",
            ],
            env={
                "HOME": "/nonexistent",
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
                "PATH": "/usr/bin:/bin",
            },
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            pass_fds=(
                message_descriptor,
                key_descriptor,
                signature_descriptor,
            ),
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError, ValueError):
        return False
    finally:
        if signature_descriptor >= 0:
            os.close(signature_descriptor)
        if key_descriptor >= 0:
            os.close(key_descriptor)
        if message_descriptor >= 0:
            os.close(message_descriptor)
    return completed.returncode == 0


def _require_bootstrap_authorization_signature(
    request: dict[str, object],
    *,
    expected_commit: str,
    expected_source: str,
    trust_payload: dict[str, object] | None = None,
    trusted_revocation_state: dict[str, tuple[str, ...]] | None = None,
) -> dict[str, str]:
    raw_receipt = request.get("authorization_receipt")
    if not isinstance(raw_receipt, dict):
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap authorization receipt is invalid"
        )
    payload = dict(raw_receipt)
    signature = payload.pop("signature", None)
    if (
        not isinstance(signature, dict)
        or set(signature) != {"algorithm", "key_id", "value"}
        or signature.get("algorithm")
        != _REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_SIGNATURE_ALGORITHM
        or not isinstance(signature.get("value"), str)
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap authorization signature is invalid"
        )
    key_id = _require_key_id(
        signature.get("key_id"),
        name="bootstrap authorization key id",
    )
    if trusted_revocation_state is not None and key_id in trusted_revocation_state[
        "superseded_operator_key_ids"
    ]:
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap authorization key is superseded"
        )
    operator_keys = (
        _load_bootstrap_operator_keys()
        if trust_payload is None
        else _load_bootstrap_operator_keys(trust_payload)
    )
    if key_id not in operator_keys:
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap authorization key is not trusted"
        )
    operator_identity, verification_key = operator_keys[key_id]
    if not _verify_ed25519_with_trusted_openssl(
        _canonical_bytes(payload), signature["value"], verification_key
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap authorization signature verification failed"
        )
    receipt_sha256 = payload.pop("receipt_sha256", None)
    request_nonce = _require_lower_hex(
        request.get("authorization_nonce_sha256"),
        length=64,
        name="bootstrap request authorization nonce",
    )
    if (
        trusted_revocation_state is not None
        and receipt_sha256
        in trusted_revocation_state["revoked_authorization_receipt_sha256s"]
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap authorization receipt is externally revoked"
        )
    expected_schema = (
        _REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_RECEIPT_SCHEMA_ID
        if trust_payload is None
        else trust_payload.get("minimum_authorization_receipt_schema_id")
    )
    if (
        receipt_sha256 != _sha256(payload)
        or payload.get("schema_id") != expected_schema
        or payload.get("schema_id")
        != _REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_RECEIPT_SCHEMA_ID
        or payload.get("authorization_key_id") != key_id
        or payload.get("authorization_operator_identity_sha256") != operator_identity
        or payload.get("authorization_nonce_sha256") != request_nonce
        or payload.get("code_commit_sha") != expected_commit
        or payload.get("runner_source_sha256") != expected_source
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "bootstrap authorization source binding is invalid"
        )
    if "expected_implementation_author_identity_sha256" in request:
        expected_author = _require_lower_hex(
            request.get("expected_implementation_author_identity_sha256"),
            length=64,
            name="bootstrap implementation author",
        )
        if payload.get("implementation_author_identity_sha256") != expected_author:
            raise _ReferenceMinimizationValidationBootstrapError(
                "bootstrap authorization source binding is invalid"
            )
    signed_dependencies = _require_signed_dependency_artifact_rows(
        payload.get("dependency_artifact_sha256_rows")
    )
    if "expected_dependency_artifact_sha256_rows" in request:
        request_dependencies = _require_dependency_artifact_row_mapping(
            request.get("expected_dependency_artifact_sha256_rows"),
            name="bootstrap request",
        )
        if request_dependencies != signed_dependencies:
            raise _ReferenceMinimizationValidationBootstrapError(
                "bootstrap authorization source binding is invalid"
            )
    return signed_dependencies


def _require_signed_clean_checkout_before_import(
    repository_root: str,
    request: dict[str, object],
    *,
    deadline: float,
) -> tuple[dict[str, object], dict[str, str], str]:
    _require_preflight_time(deadline)
    _require_root_owned_read_only_directory(repository_root)
    finder = _require_verified_source_finder()
    if finder.repository_root != repository_root:
        raise _ReferenceMinimizationValidationBootstrapError(
            "verified source finder repository is cross-wired"
        )
    finder.verify_repository_binding()
    _require_external_private_root(
        request.get("reservation_root"),
        repository_root=repository_root,
        name="reservation root",
    )
    _require_external_private_root(
        request.get("artifact_output_root"),
        repository_root=repository_root,
        name="artifact output root",
    )
    expected_commit = _require_lower_hex(
        request.get("expected_code_commit_sha"),
        length=40,
        name="expected checkout commit",
    )
    expected_source = _require_lower_hex(
        request.get("expected_runner_source_sha256"),
        length=64,
        name="expected validation source",
    )
    trust_payload = _load_bootstrap_trust_store_payload()
    trusted_revocation_state = _require_trusted_revocation_state(
        request,
        trust_payload,
    )
    signed_dependency_rows = _require_bootstrap_authorization_signature(
        request,
        expected_commit=expected_commit,
        expected_source=expected_source,
        trust_payload=trust_payload,
        trusted_revocation_state=trusted_revocation_state,
    )
    git_executable = _require_trusted_root_executable("/usr/bin/git", name="Git")
    environment = {
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "HOME": "/nonexistent",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": "/usr/bin:/bin",
    }
    common_command = [
        git_executable,
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.hooksPath=/dev/null",
    ]
    try:
        observed_head = subprocess.run(
            [*common_command, "rev-parse", "--verify", "HEAD"],
            cwd=repository_root,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=min(10.0, _require_preflight_time(deadline)),
        )
        observed_status = subprocess.run(
            [
                *common_command,
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
            ],
            cwd=repository_root,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=min(10.0, _require_preflight_time(deadline)),
        )
        observed_replacements = subprocess.run(
            [*common_command, "replace", "--list"],
            cwd=repository_root,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=min(10.0, _require_preflight_time(deadline)),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap checkout cannot be verified"
        ) from exc
    if (
        observed_head.returncode != 0
        or observed_head.stdout != expected_commit.encode("ascii") + b"\n"
        or observed_status.returncode != 0
        or observed_status.stdout
        or observed_replacements.returncode != 0
        or observed_replacements.stdout
        or reference_minimization_validation_execution_source_sha256()
        != expected_source
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap checkout is not the signed clean source"
        )
    finder.verify_repository_binding()
    return (
        _require_source_manifest_before_import(
            repository_root,
            expected_commit,
            deadline=deadline,
        ),
        signed_dependency_rows,
        _sha256(trust_payload),
    )


def _require_canonical_bootstrap_source() -> str:
    expected_bootstrap = reference_minimization_validation_bootstrap_path()
    try:
        bootstrap_stat = os.lstat(__file__)
    except OSError as exc:
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap source is unavailable"
        ) from exc
    if (
        os.path.abspath(__file__) != expected_bootstrap
        or not stat.S_ISREG(bootstrap_stat.st_mode)
        or bootstrap_stat.st_nlink != 1
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap source is not a canonical regular file"
        )
    return expected_bootstrap


def _prepare_isolated_outer_launcher(*, deadline: float) -> tuple[str, str]:
    expected_bootstrap = _require_canonical_bootstrap_source()
    repository_root = os.path.dirname(
        os.path.dirname(os.path.dirname(expected_bootstrap))
    )
    _require_immutable_source_snapshot(repository_root, deadline=deadline)
    expected_tail = (
        *REFERENCE_MINIMIZATION_VALIDATION_TRUSTED_OUTER_LAUNCHER_ARGV[1:-1],
        expected_bootstrap,
    )
    observed_argv = tuple(getattr(sys, "orig_argv", ()))
    process_argv = _read_process_argv()
    interpreter = _require_trusted_running_interpreter()
    if (
        len(observed_argv)
        != len(REFERENCE_MINIMIZATION_VALIDATION_TRUSTED_OUTER_LAUNCHER_ARGV)
        or observed_argv[1:] != expected_tail
        or process_argv != observed_argv
        or not os.path.isabs(observed_argv[0])
        or os.path.realpath(observed_argv[0]) != interpreter
        or sys.argv != [expected_bootstrap]
        or sys.flags.isolated != 1
        or sys.flags.ignore_environment != 1
        or sys.flags.no_site != 1
        or sys.flags.no_user_site != 1
        or sys.flags.dont_write_bytecode != 1
        or sys.dont_write_bytecode is not True
        or sys.pycache_prefix != "/dev/null"
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap requires the frozen isolated Python command"
        )
    if hasattr(sys, REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_STATE_ATTRIBUTE):
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap state exists before the controlled inner process"
        )
    return interpreter, expected_bootstrap


def _reexec_seeded_controlled_inner(
    interpreter: str,
    expected_bootstrap: str,
    *,
    deadline: float,
) -> None:
    environment = reference_minimization_validation_controlled_inner_environment(
        preflight_deadline=deadline
    )
    command = (
        interpreter,
        *REFERENCE_MINIMIZATION_VALIDATION_LOGICAL_RUNNER_ARGV[1:-1],
        expected_bootstrap,
    )
    os.chdir(_require_trusted_root_working_directory())
    os.execve(interpreter, command, environment)
    raise _ReferenceMinimizationValidationBootstrapError(
        "validation bootstrap controlled inner exec unexpectedly returned"
    )


def _prepare_seeded_controlled_import_boundary(
    *,
    deadline: float,
) -> tuple[object, ...]:
    expected_bootstrap = _require_canonical_bootstrap_source()
    interpreter = _require_trusted_running_interpreter()
    expected_argv = (
        interpreter,
        *REFERENCE_MINIMIZATION_VALIDATION_LOGICAL_RUNNER_ARGV[1:-1],
        expected_bootstrap,
    )
    observed_argv = tuple(getattr(sys, "orig_argv", ()))
    process_argv = _read_process_argv()
    expected_environment = (
        reference_minimization_validation_controlled_inner_environment(
            preflight_deadline=deadline
        )
    )
    python_hash_seed = int(expected_environment["PYTHONHASHSEED"])
    if (
        observed_argv != expected_argv
        or process_argv != expected_argv
        or sys.argv != [expected_bootstrap]
        or os.getcwd() != "/"
        or dict(os.environ) != expected_environment
        or sys.flags.isolated != 0
        or sys.flags.ignore_environment != 0
        or sys.flags.no_site != 1
        or sys.flags.no_user_site != 1
        or sys.flags.dont_write_bytecode != 1
        or sys.flags.hash_randomization != (0 if python_hash_seed == 0 else 1)
        or sys.dont_write_bytecode is not True
        or sys.pycache_prefix != "/dev/null"
    ):
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap requires the frozen seeded inner command"
        )
    if hasattr(sys, REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_STATE_ATTRIBUTE):
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation bootstrap state exists before trust verification"
        )

    repository_root = os.path.dirname(
        os.path.dirname(os.path.dirname(expected_bootstrap))
    )
    _require_immutable_source_snapshot(repository_root, deadline=deadline)
    source_snapshot_sha256, sources, repository_identity = (
        _snapshot_reference_minimization_validation_sources(repository_root)
    )
    finder = _install_verified_source_finder(
        repository_root,
        source_snapshot_sha256,
        sources,
        repository_identity,
    )
    standard_library_roots = _trusted_standard_library_roots()
    dependency_roots = _trusted_dependency_roots()
    sanitized_path = (
        *standard_library_roots,
        *dependency_roots,
    )
    sys.path[:] = list(dict.fromkeys(sanitized_path))
    if repository_root in sys.path:
        raise _ReferenceMinimizationValidationBootstrapError(
            "validation repository remained importable from the live checkout"
        )
    return (
        REFERENCE_MINIMIZATION_VALIDATION_CONTROLLED_INNER_STATE,
        expected_bootstrap,
        repository_root,
        dependency_roots,
        tuple(sys.path),
        source_snapshot_sha256,
        finder.finder_identity_sha256,
    )


def main() -> int:
    """Establish the import boundary and delegate canonical stdin handling."""

    try:
        stage = os.environ.get(
            REFERENCE_MINIMIZATION_VALIDATION_CONTROLLED_INNER_STAGE_ENV
        )
        if stage is None:
            preflight_deadline = (
                time.monotonic()
                + REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_PREFLIGHT_MAX_WALL_SECONDS
            )
            interpreter, expected_bootstrap = _prepare_isolated_outer_launcher(
                deadline=preflight_deadline
            )
            _reexec_seeded_controlled_inner(
                interpreter,
                expected_bootstrap,
                deadline=preflight_deadline,
            )
            raise _ReferenceMinimizationValidationBootstrapError(
                "validation bootstrap controlled inner process did not start"
            )
        if stage != REFERENCE_MINIMIZATION_VALIDATION_CONTROLLED_INNER_STATE:
            raise _ReferenceMinimizationValidationBootstrapError(
                "validation bootstrap stage marker is invalid"
            )
        preflight_deadline = _require_canonical_preflight_deadline(
            os.environ.get(
                REFERENCE_MINIMIZATION_VALIDATION_CONTROLLED_INNER_PREFLIGHT_DEADLINE_ENV
            )
        )
        state = _prepare_seeded_controlled_import_boundary(deadline=preflight_deadline)
        raw_request, request = _read_bootstrap_request()
        (
            source_manifest,
            signed_dependency_rows,
            _trust_store_sha256,
        ) = _require_signed_clean_checkout_before_import(
            state[2],
            request,
            deadline=preflight_deadline,
        )
        _require_observed_dependency_artifact_rows_before_import(
            state[2],
            state[3],
            request,
            deadline=preflight_deadline,
            signed_expected=signed_dependency_rows,
        )
        _require_verified_source_finder().verify_repository_binding()
        setattr(
            sys,
            REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_STATE_ATTRIBUTE,
            (
                *state[:5],
                _canonical_bytes(source_manifest),
                *state[5:],
            ),
        )
        from betelgeuze_engine_v2.physics import (
            reference_minimization_validation_runner,
        )

        return reference_minimization_validation_runner._main_from_canonical_request(
            raw_request
        )
    except Exception:
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
