"""Fail-closed OpenMM Reference adapter for one canonical smoke system.

The provenance-bearing API never evaluates OpenMM in the caller process.  It
pins the installed distribution and Python executable, journals every relevant
path component, and invokes a standalone worker in a clean isolated child.
"""

from __future__ import annotations

from contextlib import contextmanager
import ctypes
from dataclasses import dataclass
import hashlib
from importlib import metadata
import json
import math
import os
from pathlib import Path, PurePosixPath
import stat
import struct
import tempfile
from typing import Any, Iterator, Mapping

from ..contract import (
    CANONICAL_UNITS,
    OracleRequest,
    OracleResult,
    canonical_json_bytes,
    canonical_sha256,
    require_sha256,
)
from ..errors import (
    OracleContractError,
    OracleExecutionError,
    OracleUnavailableError,
)
from ..execution import run_argv, sanitized_environment
from . import OpenMMModules, load_openmm


ORACLE_TASK = "energy_force"
REFERENCE_PLATFORM = "Reference"
PREPARED_SYSTEM_ROLE = "prepared_system"
PREPARED_SYSTEM_SCHEMA_ID = "betelgeuze.openmm_harmonic_bond_prepared_system/1.0.0"
RUNTIME_DIGEST_SCHEMA_ID = "betelgeuze.openmm_runtime_dependency_distributions/3.0.0"
RAW_STATE_SCHEMA_ID = "betelgeuze.openmm_reference_state/3.0.0"
_WORKER_REQUEST_SCHEMA_ID = "betelgeuze.openmm_reference_worker_request/4.0.0"
_RUNTIME_DISTRIBUTION_NAMES = ("OpenMM", "numpy")
_INSTALL_GENERATED_METADATA_NAMES = frozenset(
    {"INSTALLER", "RECORD", "REQUESTED", "direct_url.json"}
)
_MAX_CHILD_OUTPUT_BYTES = 64 * 1024
_MAX_WORKER_SOURCE_BYTES = 256 * 1024
_PARAMETER_NAMES = frozenset(
    {
        "distance_angstrom",
        "equilibrium_angstrom",
        "force_constant_kcal_per_mol_angstrom2",
    }
)
_IDENTITY_FIELDS = (
    "st_dev",
    "st_ino",
    "st_mode",
    "st_size",
    "st_mtime_ns",
    "st_ctime_ns",
)
_IN_MODIFY = 0x0000_0002
_IN_ATTRIB = 0x0000_0004
_IN_CLOSE_WRITE = 0x0000_0008
_IN_MOVED_FROM = 0x0000_0040
_IN_MOVED_TO = 0x0000_0080
_IN_CREATE = 0x0000_0100
_IN_DELETE = 0x0000_0200
_IN_DELETE_SELF = 0x0000_0400
_IN_MOVE_SELF = 0x0000_0800
_IN_Q_OVERFLOW = 0x0000_4000
_IN_IGNORED = 0x0000_8000
_IN_MUTATION = (
    _IN_MODIFY
    | _IN_ATTRIB
    | _IN_CLOSE_WRITE
    | _IN_MOVED_FROM
    | _IN_MOVED_TO
    | _IN_CREATE
    | _IN_DELETE
    | _IN_DELETE_SELF
    | _IN_MOVE_SELF
)
_IN_SELF_MUTATION = _IN_ATTRIB | _IN_DELETE_SELF | _IN_MOVE_SELF | _IN_IGNORED
_INOTIFY_EVENT = struct.Struct("iIII")


def _f64_bits(value: float) -> str:
    return f"{struct.unpack('>Q', struct.pack('>d', value))[0]:016x}"


@dataclass(frozen=True)
class HarmonicBondResult:
    """Canonical energy and forces returned by the Reference platform."""

    energy_kcal_per_mol: float
    force_x_kcal_per_mol_angstrom: tuple[float, float]
    openmm_version: str
    platform: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "canonical_units": dict(CANONICAL_UNITS),
            "energy_kcal_per_mol": self.energy_kcal_per_mol,
            "force_x_kcal_per_mol_angstrom": list(self.force_x_kcal_per_mol_angstrom),
            "energy_f64_bits": _f64_bits(self.energy_kcal_per_mol),
            "force_x_f64_bits": [
                _f64_bits(value) for value in self.force_x_kcal_per_mol_angstrom
            ],
            "engine_version": self.openmm_version,
            "platform": self.platform,
            "benchmark_oracle_only": True,
            "claim_safe": False,
        }


@dataclass(frozen=True)
class OpenMMReferenceIdentity:
    """Installed-distribution and process identity for one Reference run."""

    openmm_distribution_version: str
    numpy_distribution_version: str
    openmm_version: str
    platform: str
    runtime_sha256: str
    python_executable_sha256: str
    openmm_artifact_count: int
    numpy_artifact_count: int

    @property
    def artifact_count(self) -> int:
        return self.openmm_artifact_count + self.numpy_artifact_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "runtime_dependency_manifest_schema_id": RUNTIME_DIGEST_SCHEMA_ID,
            "runtime_dependency_distributions": [
                {
                    "distribution": "OpenMM",
                    "version": self.openmm_distribution_version,
                    "artifact_count": self.openmm_artifact_count,
                },
                {
                    "distribution": "numpy",
                    "version": self.numpy_distribution_version,
                    "artifact_count": self.numpy_artifact_count,
                },
            ],
            "openmm_version": self.openmm_version,
            "platform": self.platform,
            "runtime_sha256": self.runtime_sha256,
            "python_executable_sha256": self.python_executable_sha256,
            "runtime_dependency_artifact_count": self.artifact_count,
            "isolated_child": True,
            "benchmark_oracle_only": True,
            "claim_safe": False,
        }


@dataclass(frozen=True)
class HarmonicBondRun:
    """A Reference observation plus its claim-locked common provenance."""

    identity: OpenMMReferenceIdentity
    result: HarmonicBondResult
    raw_state: bytes
    provenance: OracleResult


@dataclass(frozen=True)
class _DistributionInventory:
    name: str
    version: str
    search_root: Path
    entries: tuple[tuple[str, Path], ...]


@dataclass(frozen=True)
class _RuntimeInventory:
    distributions: tuple[_DistributionInventory, ...]

    @property
    def entries(self) -> tuple[tuple[str, str, Path], ...]:
        return tuple(
            (distribution.name, relative_path, path)
            for distribution in self.distributions
            for relative_path, path in distribution.entries
        )


@dataclass(frozen=True)
class _PinnedArtifact:
    distribution_name: str
    relative_path: str
    path: Path
    descriptor: int
    identity: os.stat_result
    sha256: str


@dataclass(frozen=True)
class _RuntimeSnapshot:
    inventory: _RuntimeInventory
    artifacts: tuple[_PinnedArtifact, ...]
    sha256: str

    def close(self) -> None:
        for artifact in self.artifacts:
            _close_descriptor(artifact.descriptor)


@dataclass(frozen=True)
class _PinnedDirectory:
    path: Path
    descriptor: int
    identity: os.stat_result
    strict_identity: bool


@dataclass
class _MutationJournal:
    descriptor: int
    watch_rules: dict[int, frozenset[bytes] | None]
    directories: tuple[_PinnedDirectory, ...]

    @classmethod
    def open(
        cls,
        protected_paths: tuple[Path, ...],
        *,
        wildcard_directories: tuple[Path, ...] = (),
    ) -> _MutationJournal:
        requested: dict[Path, set[bytes] | None] = {}
        for path in protected_paths:
            _add_path_component_watches(requested, path)
        for directory in wildcard_directories:
            _add_path_component_watches(requested, directory)
            requested[directory] = None
        libc = ctypes.CDLL(None, use_errno=True)
        init = getattr(libc, "inotify_init1", None)
        add_watch = getattr(libc, "inotify_add_watch", None)
        if init is None or add_watch is None:
            raise OracleExecutionError("descriptor_paths_unavailable")
        init.argtypes = [ctypes.c_int]
        init.restype = ctypes.c_int
        descriptor = int(init(os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0)))
        if descriptor < 0:
            raise OracleExecutionError("descriptor_paths_unavailable")
        add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
        add_watch.restype = ctypes.c_int
        directories: list[_PinnedDirectory] = []
        rules: dict[int, frozenset[bytes] | None] = {}
        try:
            for directory in sorted(
                requested, key=lambda value: (len(value.parts), os.fspath(value))
            ):
                pinned = _open_pinned_directory(
                    directory,
                    strict_identity=requested[directory] is None,
                )
                directories.append(pinned)
                watch = int(
                    add_watch(
                        descriptor,
                        os.fsencode(directory),
                        ctypes.c_uint32(_IN_MUTATION),
                    )
                )
                if watch < 0:
                    raise OracleExecutionError("descriptor_paths_unavailable")
                requested_names = requested[directory]
                previous = rules.get(watch, frozenset())
                if previous is None or requested_names is None:
                    rules[watch] = None
                else:
                    rules[watch] = frozenset(previous | requested_names)
        except BaseException:
            for pinned in directories:
                _close_descriptor(pinned.descriptor)
            _close_descriptor(descriptor)
            raise
        return cls(descriptor, rules, tuple(directories))

    def verify_unchanged(self) -> None:
        if self._relevant_event_pending():
            raise OracleExecutionError("runtime_hash_drift")
        for directory in self.directories:
            try:
                descriptor_status = os.fstat(directory.descriptor)
                path_status = directory.path.lstat()
            except OSError as exc:
                raise OracleExecutionError("runtime_hash_drift") from exc
            if (
                stat.S_ISLNK(path_status.st_mode)
                or not stat.S_ISDIR(path_status.st_mode)
                or not _same_directory_identity(
                    directory.identity,
                    descriptor_status,
                    strict=directory.strict_identity,
                )
                or not _same_directory_identity(
                    directory.identity,
                    path_status,
                    strict=directory.strict_identity,
                )
            ):
                raise OracleExecutionError("runtime_hash_drift")
        if self._relevant_event_pending():
            raise OracleExecutionError("runtime_hash_drift")

    def _relevant_event_pending(self) -> bool:
        relevant = False
        while True:
            try:
                chunk = os.read(self.descriptor, 64 * 1024)
            except BlockingIOError:
                return relevant
            except OSError as exc:
                raise OracleExecutionError("runtime_hash_drift") from exc
            if not chunk:
                return relevant
            offset = 0
            while offset < len(chunk):
                if len(chunk) - offset < _INOTIFY_EVENT.size:
                    raise OracleExecutionError("runtime_hash_drift")
                watch, mask, _cookie, name_length = _INOTIFY_EVENT.unpack_from(
                    chunk, offset
                )
                offset += _INOTIFY_EVENT.size
                end = offset + name_length
                if end > len(chunk):
                    raise OracleExecutionError("runtime_hash_drift")
                name = chunk[offset:end].split(b"\0", 1)[0]
                offset = end
                if mask & _IN_Q_OVERFLOW:
                    relevant = True
                    continue
                rule = self.watch_rules.get(watch)
                if watch not in self.watch_rules:
                    relevant = True
                elif not name and mask & _IN_SELF_MUTATION:
                    relevant = True
                elif name and (rule is None or name in rule):
                    relevant = True

    def close(self) -> None:
        for directory in self.directories:
            _close_descriptor(directory.descriptor)
        _close_descriptor(self.descriptor)


@dataclass(frozen=True)
class _PinnedEvaluationRuntime:
    snapshot: _RuntimeSnapshot
    python: _PinnedArtifact
    worker: _PinnedArtifact
    journal: _MutationJournal
    pycache_prefix: Path

    def verify_unchanged(self) -> None:
        self.journal.verify_unchanged()
        if _verify_runtime_snapshot(self.snapshot) != self.snapshot.sha256:
            raise OracleExecutionError("runtime_hash_drift")
        _verify_pinned_artifact(self.python, drift_code="binary_hash_drift")
        _verify_pinned_artifact(self.worker, drift_code="runtime_hash_drift")
        self.journal.verify_unchanged()

    def close(self) -> None:
        self.snapshot.close()
        _close_descriptor(self.python.descriptor)
        _close_descriptor(self.worker.descriptor)
        self.journal.close()


def _close_descriptor(descriptor: int) -> None:
    try:
        os.close(descriptor)
    except OSError:
        pass


def _same_identity(left: os.stat_result, right: os.stat_result) -> bool:
    return all(
        getattr(left, field) == getattr(right, field) for field in _IDENTITY_FIELDS
    )


def _same_directory_identity(
    left: os.stat_result, right: os.stat_result, *, strict: bool
) -> bool:
    fields = _IDENTITY_FIELDS if strict else ("st_dev", "st_ino", "st_mode")
    return all(getattr(left, field) == getattr(right, field) for field in fields)


def _add_path_component_watches(
    requested: dict[Path, set[bytes] | None], path: Path
) -> None:
    candidate = Path(os.path.abspath(path))
    child_name = os.fsencode(candidate.name)
    parent = candidate.parent
    while True:
        existing = requested.setdefault(parent, set())
        if existing is not None:
            existing.add(child_name)
        if parent == parent.parent:
            break
        child_name = os.fsencode(parent.name)
        parent = parent.parent


def _open_pinned_directory(path: Path, *, strict_identity: bool) -> _PinnedDirectory:
    descriptor = -1
    try:
        before_path = path.lstat()
        if stat.S_ISLNK(before_path.st_mode) or not stat.S_ISDIR(before_path.st_mode):
            raise OracleExecutionError("descriptor_paths_unavailable")
        flags = (
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_DIRECTORY", 0)
        )
        descriptor = os.open(path, flags)
        descriptor_status = os.fstat(descriptor)
        after_path = path.lstat()
        if (
            not stat.S_ISDIR(descriptor_status.st_mode)
            or not _same_directory_identity(
                before_path,
                descriptor_status,
                strict=strict_identity,
            )
            or not _same_directory_identity(
                before_path,
                after_path,
                strict=strict_identity,
            )
        ):
            raise OracleExecutionError("descriptor_paths_unavailable")
        return _PinnedDirectory(
            path,
            descriptor,
            descriptor_status,
            strict_identity,
        )
    except OracleExecutionError:
        if descriptor >= 0:
            _close_descriptor(descriptor)
        raise
    except OSError as exc:
        if descriptor >= 0:
            _close_descriptor(descriptor)
        raise OracleExecutionError("descriptor_paths_unavailable") from exc


def _descriptor_sha256(descriptor: int) -> str:
    digest = hashlib.sha256()
    offset = 0
    try:
        while chunk := os.pread(descriptor, 1024 * 1024, offset):
            digest.update(chunk)
            offset += len(chunk)
    except OSError as exc:
        raise OracleExecutionError("runtime_artifact_unreadable") from exc
    return digest.hexdigest()


def _pinned_worker_source(artifact: _PinnedArtifact) -> str:
    """Read the verified worker into an immutable argv value.

    Passing its regular-file descriptor into an untrusted child would let an
    anonymous file be reopened through ``/proc/self/fd`` with stronger access.
    The bounded source bytes are instead copied into the already pinned
    command line, while the parent keeps hashing and journaling the source path.
    """

    _verify_pinned_artifact(artifact, drift_code="runtime_hash_drift")
    if not 1 <= artifact.identity.st_size <= _MAX_WORKER_SOURCE_BYTES:
        raise OracleExecutionError("runtime_artifact_invalid")
    try:
        raw = os.pread(
            artifact.descriptor,
            _MAX_WORKER_SOURCE_BYTES + 1,
            0,
        )
        source = raw.decode("utf-8", errors="strict")
    except (OSError, UnicodeError) as exc:
        raise OracleExecutionError("runtime_artifact_unreadable") from exc
    if (
        len(raw) != artifact.identity.st_size
        or hashlib.sha256(raw).hexdigest() != artifact.sha256
        or "\0" in source
    ):
        raise OracleExecutionError("runtime_hash_drift")
    _verify_pinned_artifact(artifact, drift_code="runtime_hash_drift")
    return source


def _normalized_artifact_name(value: object) -> str:
    rendered = str(value).replace("\\", "/")
    candidate = PurePosixPath(rendered)
    normalized = candidate.as_posix()
    parts = candidate.parts
    if (
        not rendered
        or "\x00" in rendered
        or candidate.is_absolute()
        or rendered != normalized
        or not parts
        or parts[-1] == ".."
        or any(
            part == ".." and any(previous != ".." for previous in parts[:index])
            for index, part in enumerate(parts)
        )
    ):
        raise OracleExecutionError("runtime_artifact_invalid")
    return normalized


def _runtime_artifact_relative_path(
    search_root: Path,
    located: Path,
) -> str | None:
    """Return the canonical import-closure path or exclude install output."""

    try:
        relative = located.relative_to(search_root)
    except ValueError:
        return None
    parts = relative.parts
    if not parts:
        raise OracleExecutionError("runtime_metadata_invalid")
    if "__pycache__" in parts and parts[-1].endswith(".pyc"):
        return None
    if parts[-1] in _INSTALL_GENERATED_METADATA_NAMES and any(
        part.endswith(".dist-info") for part in parts[:-1]
    ):
        return None
    return PurePosixPath(*parts).as_posix()


def _one_distribution_inventory(distribution_name: str) -> _DistributionInventory:
    try:
        distribution = metadata.distribution(distribution_name)
    except metadata.PackageNotFoundError as exc:
        raise OracleUnavailableError(distribution_name.lower()) from exc
    except Exception as exc:
        raise OracleExecutionError("runtime_metadata_invalid") from exc
    files = distribution.files
    version = " ".join(str(distribution.version or "").split())
    if not files or not version:
        raise OracleExecutionError("runtime_metadata_invalid")
    try:
        search_root = Path(os.path.abspath(distribution.locate_file("")))
    except Exception as exc:
        raise OracleExecutionError("runtime_metadata_invalid") from exc
    if not search_root.is_absolute():
        raise OracleExecutionError("runtime_metadata_invalid")
    entries: list[tuple[str, Path]] = []
    names: set[str] = set()
    for entry in files:
        relative_path = _normalized_artifact_name(entry)
        try:
            located = Path(distribution.locate_file(entry))
        except Exception as exc:
            raise OracleExecutionError("runtime_metadata_invalid") from exc
        located = Path(os.path.abspath(located))
        expected = Path(os.path.abspath(search_root / relative_path))
        if located != expected:
            raise OracleExecutionError("runtime_metadata_invalid")
        canonical_path = _runtime_artifact_relative_path(search_root, located)
        if canonical_path is None:
            continue
        if canonical_path in names:
            continue
        names.add(canonical_path)
        entries.append((canonical_path, located))
    if sum(path.endswith(".dist-info/METADATA") for path in names) != 1:
        raise OracleExecutionError("runtime_metadata_invalid")
    entries.sort(key=lambda item: item[0])
    return _DistributionInventory(
        distribution_name,
        version,
        search_root,
        tuple(entries),
    )


def _distribution_inventory() -> _RuntimeInventory:
    distributions = tuple(
        _one_distribution_inventory(name) for name in _RUNTIME_DISTRIBUTION_NAMES
    )
    paths = [
        path for distribution in distributions for _name, path in distribution.entries
    ]
    if len(paths) != len(set(paths)):
        raise OracleExecutionError("runtime_metadata_invalid")
    return _RuntimeInventory(distributions)


def _open_pinned_artifact(
    name: str,
    path: Path,
    *,
    distribution_name: str = "",
    missing_code: str = "runtime_artifact_missing",
    invalid_code: str = "runtime_artifact_invalid",
    unreadable_code: str = "runtime_artifact_unreadable",
) -> _PinnedArtifact:
    descriptor = -1
    try:
        before_path = path.lstat()
        if stat.S_ISLNK(before_path.st_mode) or not stat.S_ISREG(before_path.st_mode):
            raise OracleExecutionError(invalid_code)
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        before_descriptor = os.fstat(descriptor)
        if not stat.S_ISREG(before_descriptor.st_mode) or not _same_identity(
            before_path, before_descriptor
        ):
            raise OracleExecutionError(invalid_code)
        digest = _descriptor_sha256(descriptor)
        after_descriptor = os.fstat(descriptor)
        after_path = path.lstat()
        if (
            stat.S_ISLNK(after_path.st_mode)
            or not _same_identity(before_descriptor, after_descriptor)
            or not _same_identity(before_descriptor, after_path)
        ):
            raise OracleExecutionError("runtime_hash_drift")
        return _PinnedArtifact(
            distribution_name,
            name,
            path,
            descriptor,
            before_descriptor,
            digest,
        )
    except OracleExecutionError:
        if descriptor >= 0:
            _close_descriptor(descriptor)
        raise
    except FileNotFoundError as exc:
        if descriptor >= 0:
            _close_descriptor(descriptor)
        raise OracleExecutionError(missing_code) from exc
    except OSError as exc:
        if descriptor >= 0:
            _close_descriptor(descriptor)
        raise OracleExecutionError(unreadable_code) from exc


def _verify_pinned_artifact(artifact: _PinnedArtifact, *, drift_code: str) -> None:
    try:
        before_descriptor = os.fstat(artifact.descriptor)
        before_path = artifact.path.lstat()
        digest = _descriptor_sha256(artifact.descriptor)
        after_descriptor = os.fstat(artifact.descriptor)
        after_path = artifact.path.lstat()
    except OracleExecutionError as exc:
        raise OracleExecutionError(drift_code) from exc
    except OSError as exc:
        raise OracleExecutionError(drift_code) from exc
    if (
        stat.S_ISLNK(before_path.st_mode)
        or stat.S_ISLNK(after_path.st_mode)
        or not _same_identity(artifact.identity, before_descriptor)
        or not _same_identity(artifact.identity, before_path)
        or not _same_identity(artifact.identity, after_descriptor)
        or not _same_identity(artifact.identity, after_path)
        or digest != artifact.sha256
    ):
        raise OracleExecutionError(drift_code)


def _runtime_manifest_sha256(
    inventory: _RuntimeInventory,
    artifacts: tuple[_PinnedArtifact, ...],
) -> str:
    return canonical_sha256(
        {
            "schema_id": RUNTIME_DIGEST_SCHEMA_ID,
            "runtime_dependency_distributions": [
                {
                    "distribution": distribution.name,
                    "version": distribution.version,
                    "artifacts": [
                        {
                            "path": artifact.relative_path,
                            "size": artifact.identity.st_size,
                            "sha256": artifact.sha256,
                        }
                        for artifact in artifacts
                        if artifact.distribution_name == distribution.name
                    ],
                }
                for distribution in inventory.distributions
            ],
        }
    )


def _capture_runtime_snapshot(inventory: _RuntimeInventory) -> _RuntimeSnapshot:
    artifacts: list[_PinnedArtifact] = []
    try:
        for distribution_name, name, path in inventory.entries:
            artifacts.append(
                _open_pinned_artifact(
                    name,
                    path,
                    distribution_name=distribution_name,
                )
            )
    except BaseException:
        for artifact in artifacts:
            _close_descriptor(artifact.descriptor)
        raise
    frozen = tuple(artifacts)
    return _RuntimeSnapshot(
        inventory=inventory,
        artifacts=frozen,
        sha256=_runtime_manifest_sha256(inventory, frozen),
    )


def _verify_runtime_snapshot(snapshot: _RuntimeSnapshot) -> str:
    try:
        current_inventory = _distribution_inventory()
    except OracleUnavailableError as exc:
        raise OracleExecutionError("runtime_hash_drift") from exc
    if current_inventory != snapshot.inventory:
        raise OracleExecutionError("runtime_hash_drift")
    for artifact in snapshot.artifacts:
        _verify_pinned_artifact(artifact, drift_code="runtime_hash_drift")
    observed = _runtime_manifest_sha256(snapshot.inventory, snapshot.artifacts)
    if observed != snapshot.sha256:
        raise OracleExecutionError("runtime_hash_drift")
    return observed


def _resolved_python_executable() -> Path:
    try:
        candidate = Path("/proc/self/exe").resolve(strict=True)
    except OSError as exc:
        raise OracleExecutionError("binary_missing") from exc
    if not candidate.is_absolute():
        raise OracleExecutionError("binary_missing")
    return candidate


def _worker_path() -> Path:
    return Path(__file__).with_name("_reference_worker.py")


def _runtime_watch_configuration(
    inventory: _RuntimeInventory,
    *,
    python_path: Path,
    worker_path: Path,
    pycache_prefix: Path,
) -> tuple[tuple[Path, ...], tuple[Path, ...]]:
    artifact_paths = tuple(path for _distribution, _name, path in inventory.entries)
    protected = artifact_paths + (python_path, worker_path, pycache_prefix)
    wildcard = tuple(
        sorted(
            {path.parent for path in artifact_paths}
            | {distribution.search_root for distribution in inventory.distributions}
            | {pycache_prefix},
            key=os.fspath,
        )
    )
    return protected, wildcard


@contextmanager
def _pinned_runtime(
    expected_runtime_sha256: str,
) -> Iterator[_PinnedEvaluationRuntime]:
    try:
        expected = require_sha256(
            expected_runtime_sha256, field="expected_runtime_sha256"
        )
    except OracleContractError as exc:
        raise OracleExecutionError("runtime_hash_missing") from exc
    inventory = _distribution_inventory()
    python_path = _resolved_python_executable()
    worker_path = _worker_path()
    pycache = tempfile.TemporaryDirectory(prefix="betelgeuze-openmm-pycache-")
    pycache_prefix = Path(pycache.name)
    protected, wildcard = _runtime_watch_configuration(
        inventory,
        python_path=python_path,
        worker_path=worker_path,
        pycache_prefix=pycache_prefix,
    )
    journal: _MutationJournal | None = None
    snapshot: _RuntimeSnapshot | None = None
    python_artifact: _PinnedArtifact | None = None
    worker_artifact: _PinnedArtifact | None = None
    runtime: _PinnedEvaluationRuntime | None = None
    try:
        journal = _MutationJournal.open(protected, wildcard_directories=wildcard)
        python_artifact = _open_pinned_artifact(
            "python_executable",
            python_path,
            missing_code="binary_missing",
            invalid_code="binary_invalid",
            unreadable_code="binary_unreadable",
        )
        worker_artifact = _open_pinned_artifact("reference_worker", worker_path)
        snapshot = _capture_runtime_snapshot(inventory)
        if snapshot.sha256 != expected:
            raise OracleExecutionError("runtime_hash_mismatch")
        runtime = _PinnedEvaluationRuntime(
            snapshot,
            python_artifact,
            worker_artifact,
            journal,
            pycache_prefix,
        )
        runtime.verify_unchanged()
        yield runtime
    finally:
        try:
            if runtime is not None:
                runtime.verify_unchanged()
        finally:
            if runtime is not None:
                runtime.close()
            else:
                if snapshot is not None:
                    snapshot.close()
                if python_artifact is not None:
                    _close_descriptor(python_artifact.descriptor)
                if worker_artifact is not None:
                    _close_descriptor(worker_artifact.descriptor)
                if journal is not None:
                    journal.close()
            pycache.cleanup()


def openmm_runtime_dependency_distributions_sha256() -> str:
    """Hash OpenMM and NumPy distribution bytes under path journals."""

    inventory = _distribution_inventory()
    artifact_paths = tuple(path for _distribution, _name, path in inventory.entries)
    journal = _MutationJournal.open(
        artifact_paths,
        wildcard_directories=tuple(
            sorted(
                {path.parent for path in artifact_paths}
                | {
                    distribution.search_root for distribution in inventory.distributions
                },
                key=os.fspath,
            )
        ),
    )
    snapshot: _RuntimeSnapshot | None = None
    try:
        snapshot = _capture_runtime_snapshot(inventory)
        journal.verify_unchanged()
        observed = _verify_runtime_snapshot(snapshot)
        journal.verify_unchanged()
        return observed
    finally:
        if snapshot is not None:
            snapshot.close()
        journal.close()


def openmm_reference_runtime_sha256() -> str:
    """Compatibility alias for the composite runtime dependency digest."""

    return openmm_runtime_dependency_distributions_sha256()


def _finite_parameter(value: object, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OracleContractError(f"OpenMM harmonic-bond {name} is not a number")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise OracleContractError("OpenMM harmonic-bond inputs must be finite")
    return normalized


def _harmonic_bond_parameters(
    *,
    distance_angstrom: object,
    equilibrium_angstrom: object,
    force_constant_kcal_per_mol_angstrom2: object,
) -> dict[str, float]:
    distance = _finite_parameter(distance_angstrom, name="distance")
    equilibrium = _finite_parameter(equilibrium_angstrom, name="equilibrium")
    force_constant = _finite_parameter(
        force_constant_kcal_per_mol_angstrom2, name="force constant"
    )
    if distance <= 0.0 or equilibrium <= 0.0:
        raise OracleContractError("OpenMM harmonic-bond distances must be positive")
    if force_constant < 0.0:
        raise OracleContractError("OpenMM harmonic-bond force constant is negative")
    return {
        "distance_angstrom": distance,
        "equilibrium_angstrom": equilibrium,
        "force_constant_kcal_per_mol_angstrom2": force_constant,
    }


def harmonic_bond_prepared_system_sha256(
    *,
    distance_angstrom: object,
    equilibrium_angstrom: object,
    force_constant_kcal_per_mol_angstrom2: object,
) -> str:
    """Digest the complete fixed two-particle system implied by parameters."""

    parameters = _harmonic_bond_parameters(
        distance_angstrom=distance_angstrom,
        equilibrium_angstrom=equilibrium_angstrom,
        force_constant_kcal_per_mol_angstrom2=(force_constant_kcal_per_mol_angstrom2),
    )
    return canonical_sha256(
        {
            "schema_id": PREPARED_SYSTEM_SCHEMA_ID,
            "platform": REFERENCE_PLATFORM,
            "particles": (
                {"mass_dalton": 1.0},
                {"mass_dalton": 1.0},
            ),
            "bond": {
                "particle_indices": (0, 1),
                "equilibrium_angstrom": parameters["equilibrium_angstrom"],
                "force_constant_kcal_per_mol_angstrom2": parameters[
                    "force_constant_kcal_per_mol_angstrom2"
                ],
            },
            "positions_angstrom": (
                (0.0, 0.0, 0.0),
                (parameters["distance_angstrom"], 0.0, 0.0),
            ),
            "integrator": {"kind": "verlet", "step_femtosecond": 1.0},
        }
    )


def _validated_request(request: OracleRequest) -> dict[str, float]:
    if not isinstance(request, OracleRequest):
        raise OracleExecutionError("request_invalid")
    if request.engine_id != "openmm" or request.task != ORACLE_TASK:
        raise OracleExecutionError("request_mismatch")
    if request.seed != 0 or request.thread_count != 1:
        raise OracleExecutionError("request_mismatch")
    if set(request.parameters) != _PARAMETER_NAMES:
        raise OracleExecutionError("request_mismatch")
    try:
        parameters = _harmonic_bond_parameters(**dict(request.parameters))
    except (OracleContractError, TypeError) as exc:
        raise OracleExecutionError("request_mismatch") from exc
    if set(request.input_sha256) != {PREPARED_SYSTEM_ROLE}:
        raise OracleExecutionError("input_roles_mismatch")
    prepared_sha256 = harmonic_bond_prepared_system_sha256(**parameters)
    if request.input_sha256[PREPARED_SYSTEM_ROLE] != prepared_sha256:
        raise OracleExecutionError("input_hash_mismatch")
    return parameters


def _evaluate_harmonic_bond_smoke(
    parameters: Mapping[str, float], modules: OpenMMModules
) -> HarmonicBondResult:
    mm, unit = modules.mm, modules.unit
    try:
        platform = mm.Platform.getPlatformByName(REFERENCE_PLATFORM)
    except Exception as exc:
        raise OracleExecutionError("reference_platform_unavailable") from exc
    if str(platform.getName()) != REFERENCE_PLATFORM:
        raise OracleExecutionError("reference_platform_identity_mismatch")
    system = mm.System()
    system.addParticle(1.0 * unit.dalton)
    system.addParticle(1.0 * unit.dalton)
    force = mm.HarmonicBondForce()
    force.addBond(
        0,
        1,
        parameters["equilibrium_angstrom"] * unit.angstrom,
        parameters["force_constant_kcal_per_mol_angstrom2"]
        * unit.kilocalorie_per_mole
        / (unit.angstrom**2),
    )
    system.addForce(force)
    integrator = mm.VerletIntegrator(1.0 * unit.femtosecond)
    try:
        context = mm.Context(system, integrator, platform)
        context.setPositions(
            [
                (0.0, 0.0, 0.0),
                (parameters["distance_angstrom"], 0.0, 0.0),
            ]
            * unit.angstrom
        )
        state = context.getState(getEnergy=True, getForces=True)
        energy = float(
            state.getPotentialEnergy().value_in_unit(unit.kilocalorie_per_mole)
        )
        forces = state.getForces(asNumpy=True).value_in_unit(
            unit.kilocalorie_per_mole / unit.angstrom
        )
        force_x = (float(forces[0][0]), float(forces[1][0]))
    except Exception as exc:
        raise OracleExecutionError("openmm_evaluation_failed") from exc
    finally:
        if "context" in locals():
            del context
        del integrator
    if not math.isfinite(energy) or any(not math.isfinite(value) for value in force_x):
        raise OracleExecutionError("nonfinite_output")
    version = " ".join(str(getattr(mm.version, "version", "")).split())
    if not version:
        raise OracleExecutionError("runtime_version_invalid")
    return HarmonicBondResult(energy, force_x, version, REFERENCE_PLATFORM)


def evaluate_harmonic_bond_smoke(
    *,
    distance_angstrom: object,
    equilibrium_angstrom: object,
    force_constant_kcal_per_mol_angstrom2: object,
) -> HarmonicBondResult:
    """Evaluate scalar inputs in-process without provenance; smoke use only."""

    parameters = _harmonic_bond_parameters(
        distance_angstrom=distance_angstrom,
        equilibrium_angstrom=equilibrium_angstrom,
        force_constant_kcal_per_mol_angstrom2=(force_constant_kcal_per_mol_angstrom2),
    )
    return _evaluate_harmonic_bond_smoke(parameters, load_openmm())


def _worker_payload(
    runtime: _PinnedEvaluationRuntime,
    parameters: Mapping[str, float],
    prepared_sha256: str,
) -> bytes:
    payload = canonical_json_bytes(
        {
            "schema_id": _WORKER_REQUEST_SCHEMA_ID,
            "expected_runtime_sha256": runtime.snapshot.sha256,
            "python_executable_sha256": runtime.python.sha256,
            "worker_sha256": runtime.worker.sha256,
            "runtime_dependency_distributions": [
                {
                    "distribution": distribution.name,
                    "version": distribution.version,
                    "search_root": os.fspath(distribution.search_root),
                }
                for distribution in runtime.snapshot.inventory.distributions
            ],
            "pycache_prefix": os.fspath(runtime.pycache_prefix),
            "prepared_system_sha256": prepared_sha256,
            "parameters": dict(parameters),
        }
    )
    if len(payload) > 64 * 1024:
        raise OracleExecutionError("runtime_metadata_invalid")
    return payload


def _finite_worker_number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OracleExecutionError("openmm_child_output_invalid")
    result = float(value)
    if not math.isfinite(result):
        raise OracleExecutionError("openmm_child_output_invalid")
    return result


def _parse_worker_result(
    raw_state: bytes,
    runtime: _PinnedEvaluationRuntime,
    prepared_sha256: str,
) -> HarmonicBondResult:
    try:
        payload = json.loads(raw_state.decode("utf-8", errors="strict"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise OracleExecutionError("openmm_child_output_invalid") from exc
    if not isinstance(payload, dict) or canonical_json_bytes(payload) != raw_state:
        raise OracleExecutionError("openmm_child_output_invalid")
    expected_fields = {
        "schema_id",
        "runtime_sha256",
        "runtime_dependency_manifest_schema_id",
        "runtime_dependency_distributions",
        "openmm_version",
        "platform",
        "prepared_system_sha256",
        "energy_kcal_per_mol",
        "force_x_kcal_per_mol_angstrom",
        "energy_f64_bits",
        "force_x_f64_bits",
    }
    if set(payload) != expected_fields or payload["schema_id"] != RAW_STATE_SCHEMA_ID:
        raise OracleExecutionError("openmm_child_output_invalid")
    expected_dependencies = _runtime_dependency_summary(runtime.snapshot)
    if (
        payload["runtime_sha256"] != runtime.snapshot.sha256
        or payload["runtime_dependency_manifest_schema_id"] != RUNTIME_DIGEST_SCHEMA_ID
        or payload["runtime_dependency_distributions"] != expected_dependencies
        or payload["prepared_system_sha256"] != prepared_sha256
        or payload["platform"] != REFERENCE_PLATFORM
    ):
        raise OracleExecutionError("openmm_child_output_invalid")
    version = payload["openmm_version"]
    if not isinstance(version, str) or not version or "\x00" in version:
        raise OracleExecutionError("openmm_child_output_invalid")
    energy = _finite_worker_number(payload["energy_kcal_per_mol"])
    raw_force = payload["force_x_kcal_per_mol_angstrom"]
    if not isinstance(raw_force, list) or len(raw_force) != 2:
        raise OracleExecutionError("openmm_child_output_invalid")
    force_x = tuple(_finite_worker_number(value) for value in raw_force)
    if payload["energy_f64_bits"] != _f64_bits(energy) or payload[
        "force_x_f64_bits"
    ] != [_f64_bits(value) for value in force_x]:
        raise OracleExecutionError("openmm_child_output_invalid")
    return HarmonicBondResult(
        energy,
        (force_x[0], force_x[1]),
        " ".join(version.split()),
        REFERENCE_PLATFORM,
    )


def _runtime_dependency_summary(snapshot: _RuntimeSnapshot) -> list[dict[str, Any]]:
    return [
        {
            "distribution": distribution.name,
            "version": distribution.version,
            "artifact_count": sum(
                artifact.distribution_name == distribution.name
                for artifact in snapshot.artifacts
            ),
        }
        for distribution in snapshot.inventory.distributions
    ]


def evaluate_harmonic_bond_reference(
    request: OracleRequest,
    *,
    expected_runtime_sha256: str,
    timeout_seconds: float = 60.0,
) -> HarmonicBondRun:
    """Evaluate a SHA-bound request in a byte-pinned isolated child."""

    parameters = _validated_request(request)
    prepared_sha256 = harmonic_bond_prepared_system_sha256(**parameters)
    with _pinned_runtime(expected_runtime_sha256) as runtime:
        worker_source = _pinned_worker_source(runtime.worker)
        output = run_argv(
            (
                os.fspath(runtime.python.path),
                "-I",
                "-S",
                "-B",
                "-X",
                f"pycache_prefix={runtime.pycache_prefix}",
                "-c",
                worker_source,
                runtime.worker.sha256,
            ),
            timeout_seconds=timeout_seconds,
            max_output_bytes=_MAX_CHILD_OUTPUT_BYTES,
            expected_executable_sha256=runtime.python.sha256,
            env=sanitized_environment(thread_count=request.thread_count),
            input_bytes=_worker_payload(runtime, parameters, prepared_sha256),
            integrity_check=runtime.verify_unchanged,
        )
        if output.stderr:
            raise OracleExecutionError("openmm_child_output_invalid")
        result = _parse_worker_result(output.stdout, runtime, prepared_sha256)
        dependencies = {
            distribution.name: distribution
            for distribution in runtime.snapshot.inventory.distributions
        }
        artifact_counts = {
            name: sum(
                artifact.distribution_name == name
                for artifact in runtime.snapshot.artifacts
            )
            for name in _RUNTIME_DISTRIBUTION_NAMES
        }
        identity = OpenMMReferenceIdentity(
            openmm_distribution_version=dependencies["OpenMM"].version,
            numpy_distribution_version=dependencies["numpy"].version,
            openmm_version=result.openmm_version,
            platform=result.platform,
            runtime_sha256=runtime.snapshot.sha256,
            python_executable_sha256=runtime.python.sha256,
            openmm_artifact_count=artifact_counts["OpenMM"],
            numpy_artifact_count=artifact_counts["numpy"],
        )
        raw_state = output.stdout
        stderr_sha256 = output.stderr_sha256
    provenance = OracleResult(
        request_sha256=request.sha256,
        engine_id="openmm",
        engine_version=identity.openmm_version,
        executable_sha256=identity.runtime_sha256,
        status="success",
        values={
            "platform": identity.platform,
            "runtime_dependency_manifest_schema_id": RUNTIME_DIGEST_SCHEMA_ID,
            "runtime_dependency_distributions": identity.to_dict()[
                "runtime_dependency_distributions"
            ],
            "python_executable_sha256": identity.python_executable_sha256,
            "isolated_child": True,
            "runtime_dependency_artifact_count": identity.artifact_count,
            "prepared_system_sha256": prepared_sha256,
            "energy_kcal_per_mol": result.energy_kcal_per_mol,
            "force_x_kcal_per_mol_angstrom": (result.force_x_kcal_per_mol_angstrom),
        },
        raw_output_sha256={
            "state_record": hashlib.sha256(raw_state).hexdigest(),
            "child_stderr": stderr_sha256,
        },
    )
    return HarmonicBondRun(identity, result, raw_state, provenance)


__all__ = [
    "HarmonicBondResult",
    "HarmonicBondRun",
    "OpenMMReferenceIdentity",
    "ORACLE_TASK",
    "PREPARED_SYSTEM_ROLE",
    "REFERENCE_PLATFORM",
    "evaluate_harmonic_bond_reference",
    "evaluate_harmonic_bond_smoke",
    "harmonic_bond_prepared_system_sha256",
    "openmm_runtime_dependency_distributions_sha256",
    "openmm_reference_runtime_sha256",
]
