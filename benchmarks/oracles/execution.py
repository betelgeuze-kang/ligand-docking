"""Fail-closed argv execution used only by external benchmark adapters."""

from __future__ import annotations

from contextlib import contextmanager, ExitStack
import ctypes
from dataclasses import dataclass
import fcntl
import hashlib
import os
from pathlib import Path
import selectors
import signal
import stat
import subprocess
import sys
import tempfile
import time
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence

from .contract import OracleRequest, require_sha256
from .errors import OracleContractError, OracleExecutionError


DEFAULT_MAX_CAPTURE_BYTES = 1_048_576
DEFAULT_MAX_ARTIFACT_BYTES = 64 * 1024 * 1024
DEFAULT_MAX_BINARY_ARTIFACT_BYTES = 1024 * 1024 * 1024
_DEFAULT_RUNNER = subprocess.run
_FILE_IDENTITY = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
_IN_SNAPSHOT_MUTATION = (
    0x0000_0002  # IN_MODIFY
    | 0x0000_0004  # IN_ATTRIB
    | 0x0000_0008  # IN_CLOSE_WRITE
    | 0x0000_0040  # IN_MOVED_FROM
    | 0x0000_0080  # IN_MOVED_TO
    | 0x0000_0100  # IN_CREATE
    | 0x0000_0200  # IN_DELETE
    | 0x0000_0400  # IN_DELETE_SELF
    | 0x0000_0800  # IN_MOVE_SELF
)


@dataclass(frozen=True)
class ExecutionOutput:
    argv: tuple[str, ...]
    returncode: int
    stdout: bytes
    stderr: bytes

    @property
    def stdout_sha256(self) -> str:
        return hashlib.sha256(self.stdout).hexdigest()

    @property
    def stderr_sha256(self) -> str:
        return hashlib.sha256(self.stderr).hexdigest()


@dataclass(frozen=True)
class VerifiedArtifact:
    """Bounded bytes and digest from one stable regular non-symlink file."""

    data: bytes
    sha256: str


@dataclass(frozen=True)
class _PinnedFile:
    path: Path
    descriptor: int
    identity: os.stat_result
    sha256: str
    drift_code: str


@dataclass(frozen=True)
class PinnedOracleWorkspace:
    """Descriptor-anchored immutable copies consumed by an external solver."""

    executable: str
    inputs: Mapping[str, str]
    directory_fd: int
    output_directory_fd: int
    executable_sha256: str
    input_sha256: Mapping[str, str]
    _pinned_files: tuple[_PinnedFile, ...]
    _watch_fd: int

    @property
    def pass_fds(self) -> tuple[int, ...]:
        return (self.directory_fd, self.output_directory_fd)

    @property
    def writable_directory_fds(self) -> tuple[int, ...]:
        return (self.output_directory_fd,)

    def output_path(self, filename: str) -> str:
        if (
            not isinstance(filename, str)
            or not filename
            or filename in {".", ".."}
            or "/" in filename
            or "\0" in filename
        ):
            raise OracleContractError("workspace output name is invalid")
        return f"/proc/self/fd/{self.output_directory_fd}/{filename}"

    def verify_unchanged(self) -> None:
        """Reject any mutation of a snapshot, including write-and-restore.

        Snapshot descriptors stay open for the workspace lifetime.  Ordinary
        users cannot restore an inode's ctime after chmod, truncate, write, or
        replacement, so checking descriptor/path identity around a fresh hash
        makes every solver result fail closed if a same-UID process touched a
        prepared input or the executable while it was running.
        """

        if _snapshot_watch_changed(self._watch_fd):
            raise OracleExecutionError("input_hash_drift")
        for pinned in self._pinned_files:
            _verify_pinned_file(pinned)
        # A mutation can race the descriptor/path rehash after the initial
        # journal drain and restore every endpoint before its own row is
        # inspected.  Drain again so any event queued during verification
        # invalidates the complete snapshot observation.
        if _snapshot_watch_changed(self._watch_fd):
            raise OracleExecutionError("input_hash_drift")


def _same_file_identity(left: os.stat_result, right: os.stat_result) -> bool:
    return all(
        getattr(left, field) == getattr(right, field) for field in _FILE_IDENTITY
    )


def _open_regular_nofollow(
    path: str | Path,
    *,
    missing_code: str,
    invalid_code: str,
    unreadable_code: str,
) -> tuple[int, os.stat_result]:
    candidate = Path(path)
    try:
        path_status = candidate.lstat()
    except FileNotFoundError as exc:
        raise OracleExecutionError(missing_code) from exc
    except OSError as exc:
        raise OracleExecutionError(unreadable_code) from exc
    if stat.S_ISLNK(path_status.st_mode) or not stat.S_ISREG(path_status.st_mode):
        raise OracleExecutionError(invalid_code)
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = -1
    try:
        descriptor = os.open(candidate, flags)
        descriptor_status = os.fstat(descriptor)
    except OSError as exc:
        if descriptor >= 0:
            os.close(descriptor)
        raise OracleExecutionError(unreadable_code) from exc
    if not stat.S_ISREG(descriptor_status.st_mode) or not _same_file_identity(
        path_status, descriptor_status
    ):
        os.close(descriptor)
        raise OracleExecutionError(invalid_code)
    return descriptor, descriptor_status


def _sha256_descriptor(descriptor: int) -> str:
    digest = hashlib.sha256()
    offset = 0
    while chunk := os.pread(descriptor, 1024 * 1024, offset):
        digest.update(chunk)
        offset += len(chunk)
    return digest.hexdigest()


def _verify_pinned_file(pinned: _PinnedFile) -> None:
    try:
        before = os.fstat(pinned.descriptor)
        before_path = pinned.path.lstat()
        digest = _sha256_descriptor(pinned.descriptor)
        after = os.fstat(pinned.descriptor)
        after_path = pinned.path.lstat()
    except OSError as exc:
        raise OracleExecutionError(pinned.drift_code) from exc
    if (
        not stat.S_ISREG(before.st_mode)
        or stat.S_ISLNK(before_path.st_mode)
        or stat.S_ISLNK(after_path.st_mode)
        or not _same_file_identity(pinned.identity, before)
        or not _same_file_identity(pinned.identity, before_path)
        or not _same_file_identity(pinned.identity, after)
        or not _same_file_identity(pinned.identity, after_path)
        or digest != pinned.sha256
    ):
        raise OracleExecutionError(pinned.drift_code)


def _watch_snapshot_directory(path: Path) -> int:
    """Open a fail-closed Linux change journal for the prepared-input tree."""

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
    watch = int(
        add_watch(
            descriptor,
            os.fsencode(path),
            ctypes.c_uint32(_IN_SNAPSHOT_MUTATION),
        )
    )
    if watch < 0:
        os.close(descriptor)
        raise OracleExecutionError("descriptor_paths_unavailable")
    return descriptor


def _snapshot_watch_changed(descriptor: int) -> bool:
    changed = False
    while True:
        try:
            chunk = os.read(descriptor, 64 * 1024)
        except BlockingIOError:
            return changed
        except OSError as exc:
            raise OracleExecutionError("input_hash_drift") from exc
        if not chunk:
            return changed
        changed = True


def _sha256_regular(
    path: str | Path,
    *,
    missing_code: str,
    invalid_code: str,
    unreadable_code: str,
    drift_code: str,
    max_bytes: int | None = None,
) -> str:
    descriptor, before = _open_regular_nofollow(
        path,
        missing_code=missing_code,
        invalid_code=invalid_code,
        unreadable_code=unreadable_code,
    )
    if max_bytes is not None and before.st_size > max_bytes:
        os.close(descriptor)
        raise OracleExecutionError("output_too_large")
    digest = hashlib.sha256()
    total = 0
    try:
        with ExitStack() as stack:
            stream = stack.enter_context(os.fdopen(descriptor, "rb", closefd=True))
            descriptor = -1
            while chunk := stream.read(1024 * 1024):
                total += len(chunk)
                if max_bytes is not None and total > max_bytes:
                    raise OracleExecutionError("output_too_large")
                digest.update(chunk)
            after_descriptor = os.fstat(stream.fileno())
        after_path = Path(path).lstat()
    except OracleExecutionError:
        raise
    except OSError as exc:
        raise OracleExecutionError(unreadable_code) from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if (
        not _same_file_identity(before, after_descriptor)
        or not _same_file_identity(before, after_path)
        or stat.S_ISLNK(after_path.st_mode)
    ):
        raise OracleExecutionError(drift_code)
    return digest.hexdigest()


def sha256_regular_file(path: str | Path) -> str:
    return _sha256_regular(
        path,
        missing_code="binary_missing",
        invalid_code="binary_invalid",
        unreadable_code="binary_unreadable",
        drift_code="binary_hash_drift",
    )


def sha256_input_file(path: str | Path) -> str:
    """Hash one stable prepared input without following a symlink."""

    return _sha256_regular(
        path,
        missing_code="input_missing",
        invalid_code="input_invalid",
        unreadable_code="input_unreadable",
        drift_code="input_hash_drift",
    )


def require_pinned_executable(
    path: str | Path,
    expected_sha256: str,
) -> tuple[Path, str]:
    """Require an explicit absolute regular executable with its frozen digest."""

    try:
        expected = require_sha256(expected_sha256, field="executable_sha256")
    except OracleContractError as exc:
        raise OracleExecutionError("binary_hash_missing") from exc
    candidate = Path(path)
    if not candidate.is_absolute():
        raise OracleExecutionError("binary_missing")
    if sha256_regular_file(candidate) != expected:
        raise OracleExecutionError("binary_hash_mismatch")
    if not os.access(candidate, os.X_OK):
        raise OracleExecutionError("binary_invalid")
    return candidate, expected


def verify_request_inputs(
    request: OracleRequest,
    input_paths: Mapping[str, str | Path],
    *,
    engine_id: str,
    task: str,
) -> dict[str, str]:
    """Verify exact role names and prepared-input digests for an adapter call."""

    if not isinstance(request, OracleRequest):
        raise OracleExecutionError("request_invalid")
    if request.engine_id != engine_id or request.task != task:
        raise OracleExecutionError("request_mismatch")
    if not isinstance(input_paths, Mapping) or any(
        not isinstance(role, str) or not role for role in input_paths
    ):
        raise OracleExecutionError("input_roles_mismatch")
    if set(request.input_sha256) != set(input_paths):
        raise OracleExecutionError("input_roles_mismatch")
    observed: dict[str, str] = {}
    for role in sorted(input_paths):
        digest = sha256_input_file(input_paths[role])
        if digest != request.input_sha256[role]:
            raise OracleExecutionError("input_hash_mismatch")
        observed[role] = digest
    return observed


def _suffix_for_snapshot(path: str | Path) -> str:
    suffix = "".join(Path(path).suffixes)
    if len(suffix) > 64 or any(
        character
        not in ".-_abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        for character in suffix
    ):
        raise OracleExecutionError("input_invalid")
    return suffix


def _copy_verified_file(
    source: str | Path,
    destination: Path,
    *,
    expected_sha256: str,
    kind: str,
    mode: int,
) -> str:
    if kind == "binary":
        codes = (
            "binary_missing",
            "binary_invalid",
            "binary_unreadable",
            "binary_hash_drift",
            "binary_hash_mismatch",
        )
    else:
        codes = (
            "input_missing",
            "input_invalid",
            "input_unreadable",
            "input_hash_drift",
            "input_hash_mismatch",
        )
    descriptor, before = _open_regular_nofollow(
        source,
        missing_code=codes[0],
        invalid_code=codes[1],
        unreadable_code=codes[2],
    )
    if kind == "binary" and before.st_mode & 0o111 == 0:
        os.close(descriptor)
        raise OracleExecutionError(codes[1])
    destination_descriptor = -1
    digest = hashlib.sha256()
    try:
        destination_descriptor = os.open(
            destination,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        with ExitStack() as stack:
            source_stream = stack.enter_context(
                os.fdopen(descriptor, "rb", closefd=True)
            )
            descriptor = -1
            destination_stream = stack.enter_context(
                os.fdopen(destination_descriptor, "wb", closefd=True)
            )
            destination_descriptor = -1
            while chunk := source_stream.read(1024 * 1024):
                digest.update(chunk)
                destination_stream.write(chunk)
            destination_stream.flush()
            os.fsync(destination_stream.fileno())
            after_descriptor = os.fstat(source_stream.fileno())
        after_path = Path(source).lstat()
        os.chmod(destination, mode, follow_symlinks=False)
    except OSError as exc:
        raise OracleExecutionError(codes[2]) from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if destination_descriptor >= 0:
            os.close(destination_descriptor)
    if (
        not _same_file_identity(before, after_descriptor)
        or not _same_file_identity(before, after_path)
        or stat.S_ISLNK(after_path.st_mode)
    ):
        raise OracleExecutionError(codes[3])
    observed = digest.hexdigest()
    if observed != expected_sha256:
        raise OracleExecutionError(codes[4])
    return observed


@contextmanager
def pinned_oracle_workspace(
    executable: str | Path,
    expected_executable_sha256: str,
    request: OracleRequest,
    input_paths: Mapping[str, str | Path],
    *,
    engine_id: str,
    task: str,
):
    """Yield descriptor paths for immutable request-bound private copies.

    The original paths are never passed to the child.  Snapshot bytes are read
    from the same ``O_NOFOLLOW`` descriptors that are hashed, defeating
    swap-and-restore races against the public input and executable paths.
    """

    try:
        expected_executable = require_sha256(
            expected_executable_sha256, field="executable_sha256"
        )
    except OracleContractError as exc:
        raise OracleExecutionError("binary_hash_missing") from exc
    executable_path = Path(executable)
    if not executable_path.is_absolute():
        raise OracleExecutionError("binary_missing")
    if not isinstance(request, OracleRequest):
        raise OracleExecutionError("request_invalid")
    if request.engine_id != engine_id or request.task != task:
        raise OracleExecutionError("request_mismatch")
    if not isinstance(input_paths, Mapping) or set(input_paths) != set(
        request.input_sha256
    ):
        raise OracleExecutionError("input_roles_mismatch")
    if not Path("/proc/self/fd").is_dir():
        raise OracleExecutionError("descriptor_paths_unavailable")

    with tempfile.TemporaryDirectory(prefix="betelgeuze-oracle-") as directory:
        root = Path(directory)
        os.chmod(root, 0o700)
        prepared_root = root / "prepared"
        output_root = root / "outputs"
        prepared_root.mkdir(mode=0o700)
        output_root.mkdir(mode=0o700)
        executable_snapshot = prepared_root / "00_oracle_executable"
        executable_digest = _copy_verified_file(
            executable_path,
            executable_snapshot,
            expected_sha256=expected_executable,
            kind="binary",
            mode=0o500,
        )
        snapshots: dict[str, Path] = {}
        observed_inputs: dict[str, str] = {}
        for index, role in enumerate(sorted(input_paths), start=1):
            snapshot = (
                prepared_root
                / f"{index:02d}_{role}{_suffix_for_snapshot(input_paths[role])}"
            )
            observed_inputs[role] = _copy_verified_file(
                input_paths[role],
                snapshot,
                expected_sha256=request.input_sha256[role],
                kind="input",
                mode=0o400,
            )
            snapshots[role] = snapshot
        os.chmod(prepared_root, 0o500)
        with ExitStack() as descriptors:
            pinned_files: list[_PinnedFile] = []
            snapshot_specs = [
                (
                    executable_snapshot,
                    executable_digest,
                    "binary_hash_drift",
                    "binary_missing",
                    "binary_invalid",
                    "binary_unreadable",
                ),
                *[
                    (
                        snapshots[role],
                        observed_inputs[role],
                        "input_hash_drift",
                        "input_missing",
                        "input_invalid",
                        "input_unreadable",
                    )
                    for role in sorted(snapshots)
                ],
            ]
            for (
                snapshot_path,
                snapshot_digest,
                drift_code,
                missing_code,
                invalid_code,
                unreadable_code,
            ) in snapshot_specs:
                descriptor, identity = _open_regular_nofollow(
                    snapshot_path,
                    missing_code=missing_code,
                    invalid_code=invalid_code,
                    unreadable_code=unreadable_code,
                )
                descriptors.callback(os.close, descriptor)
                pinned_files.append(
                    _PinnedFile(
                        path=snapshot_path,
                        descriptor=descriptor,
                        identity=identity,
                        sha256=snapshot_digest,
                        drift_code=drift_code,
                    )
                )
            watch_fd = _watch_snapshot_directory(prepared_root)
            descriptors.callback(os.close, watch_fd)
            directory_fd = os.open(
                root,
                os.O_RDONLY
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_CLOEXEC", 0),
            )
            descriptors.callback(os.close, directory_fd)
            output_directory_fd = os.open(
                output_root,
                os.O_RDONLY
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_CLOEXEC", 0),
            )
            descriptors.callback(os.close, output_directory_fd)
            proc_root = f"/proc/self/fd/{directory_fd}/prepared"
            workspace = PinnedOracleWorkspace(
                executable=f"{proc_root}/{executable_snapshot.name}",
                inputs=MappingProxyType(
                    {
                        role: f"{proc_root}/{path.name}"
                        for role, path in snapshots.items()
                    }
                ),
                directory_fd=directory_fd,
                output_directory_fd=output_directory_fd,
                executable_sha256=executable_digest,
                input_sha256=MappingProxyType(dict(sorted(observed_inputs.items()))),
                _pinned_files=tuple(pinned_files),
                _watch_fd=watch_fd,
            )
            workspace.verify_unchanged()
            yield workspace
            workspace.verify_unchanged()


def read_fresh_output(
    path: str | Path,
    *,
    max_bytes: int = DEFAULT_MAX_ARTIFACT_BYTES,
) -> VerifiedArtifact:
    """Read a new regular non-symlink artifact under a strict memory bound."""

    if isinstance(max_bytes, bool) or not 1 <= max_bytes <= 1024 * 1024 * 1024:
        raise OracleContractError("max artifact bytes is outside the benchmark bound")
    descriptor, before = _open_regular_nofollow(
        path,
        missing_code="output_missing",
        invalid_code="output_invalid",
        unreadable_code="output_unreadable",
    )
    digest = hashlib.sha256()
    chunks: list[bytes] = []
    total = 0
    try:
        with ExitStack() as stack:
            stream = stack.enter_context(os.fdopen(descriptor, "rb", closefd=True))
            descriptor = -1
            while chunk := stream.read(min(1024 * 1024, max_bytes + 1 - total)):
                total += len(chunk)
                if total > max_bytes:
                    raise OracleExecutionError("output_too_large")
                chunks.append(chunk)
                digest.update(chunk)
            after_descriptor = os.fstat(stream.fileno())
        after_path = Path(path).lstat()
    except OracleExecutionError:
        raise
    except OSError as exc:
        raise OracleExecutionError("output_unreadable") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if (
        not _same_file_identity(before, after_descriptor)
        or not _same_file_identity(before, after_path)
        or stat.S_ISLNK(after_path.st_mode)
    ):
        raise OracleExecutionError("output_hash_drift")
    return VerifiedArtifact(data=b"".join(chunks), sha256=digest.hexdigest())


def sha256_output_file(path: str | Path, *, max_bytes: int | None = None) -> str:
    """Hash a stable regular non-symlink output without loading it in memory."""

    if max_bytes is not None and (
        isinstance(max_bytes, bool) or not 1 <= max_bytes <= 16 * 1024 * 1024 * 1024
    ):
        raise OracleContractError("max artifact bytes is outside the benchmark bound")
    return _sha256_regular(
        path,
        missing_code="output_missing",
        invalid_code="output_invalid",
        unreadable_code="output_unreadable",
        drift_code="output_hash_drift",
        max_bytes=max_bytes,
    )


def validate_argv(argv: Sequence[str]) -> tuple[str, ...]:
    normalized = tuple(str(value) for value in argv)
    if not normalized or any(not value or "\0" in value for value in normalized):
        raise OracleContractError("external command argv is invalid")
    return normalized


def _validated_inherited_fds(
    pass_fds: Sequence[int],
    writable_directory_fds: Sequence[int],
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Allow only read-only directories across the trust boundary.

    A read-only regular descriptor is not an immutable capability on Linux:
    anonymous files (and some path-backed files) can be reopened through
    ``/proc/self/fd`` with write access.  Oracle adapters need only anchored
    input/output directories, so rejecting regular files closes that upgrade
    path instead of trying to infer filesystem-specific reopen semantics.
    """

    def normalized(values: Sequence[int], *, field: str) -> tuple[int, ...]:
        result: list[int] = []
        for value in values:
            if isinstance(value, bool) or not isinstance(value, int) or value <= 2:
                raise OracleContractError(f"{field} contains an invalid descriptor")
            if value not in result:
                result.append(value)
        if len(result) > 64:
            raise OracleContractError(f"{field} contains too many descriptors")
        return tuple(result)

    inherited = normalized(pass_fds, field="pass_fds")
    writable = normalized(
        writable_directory_fds,
        field="writable_directory_fds",
    )
    if not set(writable).issubset(inherited):
        raise OracleContractError("writable_directory_fds must be a subset of pass_fds")
    for descriptor in inherited:
        try:
            flags = int(fcntl.fcntl(descriptor, fcntl.F_GETFL))
            status = os.fstat(descriptor)
        except OSError as exc:
            raise OracleContractError("pass_fds contains a closed descriptor") from exc
        if flags & os.O_ACCMODE != os.O_RDONLY or not stat.S_ISDIR(status.st_mode):
            raise OracleContractError("pass_fds may contain only read-only directories")
    return inherited, writable


def invoke_argv(
    argv: Sequence[str],
    *,
    runner: Callable[..., Any] = subprocess.run,
    **kwargs: Any,
) -> Any:
    """Own the low-level process boundary while preserving caller policy.

    Compatibility benchmark runners use this primitive when they need custom
    descriptor, stdout, or timeout handling.  Exceptions and return values are
    deliberately left untouched for those callers, but a shell is never
    permitted.
    """

    command = validate_argv(argv)
    if kwargs.pop("shell", False) is not False:
        raise OracleContractError("external oracle commands cannot use a shell")
    return runner(command, shell=False, **kwargs)


def _kill_process_group(process: subprocess.Popen[bytes]) -> None:
    """Ask the subreaper to clean its tree, then enforce a hard fallback."""

    if process.poll() is not None:
        process.wait()
        return
    try:
        process.terminate()
    except ProcessLookupError:
        process.wait()
        return
    try:
        # The util-linux launcher and namespace PID 1 intentionally remain in
        # this private host process group.  Kill that group before reaping its
        # leader: terminating namespace PID 1 makes the kernel synchronously
        # kill even setsid/double-fork descendants in the PID namespace.
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except OSError:
        if process.poll() is None:
            process.kill()
    process.wait()


def _pinned_supervisor() -> _PinnedFile:
    path = Path(__file__).with_name("_process_supervisor.py")
    descriptor, identity = _open_regular_nofollow(
        path,
        missing_code="binary_missing",
        invalid_code="binary_invalid",
        unreadable_code="binary_unreadable",
    )
    try:
        return _PinnedFile(
            path=path,
            descriptor=descriptor,
            identity=identity,
            sha256=_sha256_descriptor(descriptor),
            drift_code="binary_hash_drift",
        )
    except BaseException:
        os.close(descriptor)
        raise


def _pinned_python() -> _PinnedFile:
    """Pin the interpreter used inside the private PID namespace."""

    try:
        path = Path(sys.executable).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise OracleExecutionError("isolation_unavailable") from exc
    descriptor, identity = _open_regular_nofollow(
        path,
        missing_code="isolation_unavailable",
        invalid_code="isolation_unavailable",
        unreadable_code="isolation_unavailable",
    )
    try:
        if identity.st_mode & 0o111 == 0:
            raise OracleExecutionError("isolation_unavailable")
        return _PinnedFile(
            path=path,
            descriptor=descriptor,
            identity=identity,
            sha256=_sha256_descriptor(descriptor),
            drift_code="binary_hash_drift",
        )
    except BaseException:
        os.close(descriptor)
        raise


def _pinned_unshare() -> _PinnedFile:
    """Pin a root-owned util-linux namespace launcher or fail closed."""

    observed: set[Path] = set()
    for candidate in (Path("/usr/bin/unshare"), Path("/bin/unshare")):
        try:
            path = candidate.resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        if path in observed:
            continue
        observed.add(path)
        try:
            descriptor, identity = _open_regular_nofollow(
                path,
                missing_code="isolation_unavailable",
                invalid_code="isolation_unavailable",
                unreadable_code="isolation_unavailable",
            )
        except OracleExecutionError:
            continue
        try:
            if (
                identity.st_uid != 0
                or identity.st_mode & 0o111 == 0
                or identity.st_mode & 0o022 != 0
            ):
                raise OracleExecutionError("isolation_unavailable")
            return _PinnedFile(
                path=path,
                descriptor=descriptor,
                identity=identity,
                sha256=_sha256_descriptor(descriptor),
                drift_code="binary_hash_drift",
            )
        except OracleExecutionError:
            os.close(descriptor)
            continue
        except BaseException:
            os.close(descriptor)
            raise
    raise OracleExecutionError("isolation_unavailable")


def _run_streaming_subprocess(
    command: tuple[str, ...],
    *,
    timeout_seconds: float,
    max_output_bytes: int,
    env: Mapping[str, str] | None,
    pass_fds: tuple[int, ...],
    writable_directory_fds: tuple[int, ...],
    input_bytes: bytes,
) -> tuple[int, bytes, bytes]:
    """Drain both pipes concurrently and kill as soon as their cap is crossed."""

    pass_fds, writable_directory_fds = _validated_inherited_fds(
        pass_fds,
        writable_directory_fds,
    )
    with (
        tempfile.TemporaryFile(mode="w+b") as stdin_file,
        tempfile.TemporaryDirectory(prefix="betelgeuze-oracle-sandbox-") as sandbox,
    ):
        stdin_file.write(input_bytes)
        stdin_file.seek(0)
        pinned_stack = ExitStack()
        try:
            sandbox_fd = os.open(
                sandbox,
                os.O_RDONLY
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_CLOEXEC", 0),
            )
            pinned_stack.callback(os.close, sandbox_fd)
            supervisor = _pinned_supervisor()
            pinned_stack.callback(os.close, supervisor.descriptor)
            python = _pinned_python()
            pinned_stack.callback(os.close, python.descriptor)
            unshare = _pinned_unshare()
            pinned_stack.callback(os.close, unshare.descriptor)
        except BaseException:
            pinned_stack.close()
            raise
        pinned_files = (supervisor, python, unshare)
        write_fds = tuple(dict.fromkeys((sandbox_fd, *writable_directory_fds)))
        cpu_seconds = min(
            86_400,
            max(60, int(timeout_seconds * 64.0) + 1),
        )
        supervisor_arguments = (
            "--cpu-seconds",
            str(cpu_seconds),
            *(
                value
                for descriptor in write_fds
                for value in ("--write-fd", str(descriptor))
            ),
        )
        namespace_command = (
            f"/proc/self/fd/{unshare.descriptor}",
            "--user",
            "--map-current-user",
            "--ipc",
            "--net",
            "--pid",
            "--uts",
            "--fork",
            "--kill-child=SIGKILL",
            "--mount-proc",
            f"/proc/self/fd/{python.descriptor}",
            "-I",
            "-S",
            "-B",
            f"/proc/self/fd/{supervisor.descriptor}",
            *supervisor_arguments,
            "--",
            *command,
        )
        launch_command = (
            f"/proc/self/fd/{python.descriptor}",
            "-I",
            "-S",
            "-B",
            f"/proc/self/fd/{supervisor.descriptor}",
            "--parent-guard",
            str(os.getpid()),
            "--",
            *namespace_command,
        )
        launch_env = dict(os.environ if env is None else env)
        for unsafe_name in (
            "BASH_ENV",
            "CDPATH",
            "ENV",
            "GCONV_PATH",
            "LD_LIBRARY_PATH",
            "LD_PRELOAD",
            "PYTHONHOME",
            "PYTHONPATH",
        ):
            launch_env.pop(unsafe_name, None)
        launch_env.update(
            {
                "HOME": sandbox,
                "TMPDIR": sandbox,
                "TMP": sandbox,
                "TEMP": sandbox,
                "XDG_CACHE_HOME": sandbox,
                "XDG_CONFIG_HOME": sandbox,
                "XDG_DATA_HOME": sandbox,
                "XDG_STATE_HOME": sandbox,
            }
        )
        try:
            process = subprocess.Popen(
                launch_command,
                shell=False,
                stdin=stdin_file,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=launch_env,
                cwd=sandbox,
                pass_fds=tuple(
                    dict.fromkeys(
                        (
                            *pass_fds,
                            *write_fds,
                            *(pinned.descriptor for pinned in pinned_files),
                        )
                    )
                ),
                start_new_session=True,
            )
        except BaseException:
            pinned_stack.close()
            raise
        try:
            _validated_inherited_fds(pass_fds, writable_directory_fds)
        except BaseException:
            _kill_process_group(process)
            pinned_stack.close()
            raise
        if process.stdout is None or process.stderr is None:
            _kill_process_group(process)
            pinned_stack.close()
            raise OracleExecutionError("launch_failed", argv=command)
        streams = {"stdout": process.stdout, "stderr": process.stderr}
        buffers = {"stdout": bytearray(), "stderr": bytearray()}
        selector = selectors.DefaultSelector()
        deadline = time.monotonic() + timeout_seconds
        try:
            for name, stream in streams.items():
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, data=name)
            while selector.get_map():
                remaining_time = deadline - time.monotonic()
                if remaining_time <= 0.0:
                    raise OracleExecutionError(
                        "timeout",
                        argv=command,
                        stdout=bytes(buffers["stdout"]),
                        stderr=bytes(buffers["stderr"]),
                        returncode=process.returncode,
                        capture_complete=False,
                    )
                events = selector.select(timeout=min(remaining_time, 0.05))
                for key, _mask in events:
                    name = str(key.data)
                    aggregate = len(buffers["stdout"]) + len(buffers["stderr"])
                    remaining_bytes = max_output_bytes - aggregate
                    try:
                        chunk = os.read(
                            key.fileobj.fileno(), min(65_536, remaining_bytes + 1)
                        )
                    except BlockingIOError:
                        continue
                    if not chunk:
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                        continue
                    buffers[name].extend(chunk[:remaining_bytes])
                    if len(chunk) > remaining_bytes:
                        raise OracleExecutionError(
                            "output_too_large",
                            argv=command,
                            stdout=bytes(buffers["stdout"]),
                            stderr=bytes(buffers["stderr"]),
                            returncode=process.returncode,
                            capture_complete=False,
                        )
            returncode = process.wait(timeout=max(0.0, deadline - time.monotonic()))
            return returncode, bytes(buffers["stdout"]), bytes(buffers["stderr"])
        except subprocess.TimeoutExpired as exc:
            _kill_process_group(process)
            raise OracleExecutionError(
                "timeout",
                argv=command,
                stdout=bytes(buffers["stdout"]),
                stderr=bytes(buffers["stderr"]),
                returncode=process.returncode,
                capture_complete=False,
            ) from exc
        except BaseException:
            _kill_process_group(process)
            raise
        finally:
            selector.close()
            for stream in streams.values():
                if not stream.closed:
                    stream.close()
            # A solver may daemonize a child, close the inherited pipes, and
            # let its direct parent exit successfully.  Always reap the whole
            # private process group so no descendant can outlive the bounded
            # oracle call or mutate benchmark state later.
            _kill_process_group(process)
            try:
                for pinned in pinned_files:
                    _verify_pinned_file(pinned)
            finally:
                pinned_stack.close()


def run_argv(
    argv: Sequence[str],
    *,
    timeout_seconds: float,
    max_output_bytes: int = DEFAULT_MAX_CAPTURE_BYTES,
    expected_executable_sha256: str = "",
    env: Mapping[str, str] | None = None,
    pass_fds: Sequence[int] = (),
    writable_directory_fds: Sequence[int] = (),
    runner: Callable[..., subprocess.CompletedProcess[bytes]] = _DEFAULT_RUNNER,
    input_bytes: bytes = b"",
    integrity_check: Callable[[], None] | None = None,
) -> ExecutionOutput:
    """Run argv without a shell and strictly bound in-memory captured output.

    The real subprocess path drains two nonblocking pipes concurrently and
    kills a noisy solver as soon as their aggregate prefix reaches the bound.
    Injected runners remain available for deterministic tests and are
    validated after returning.
    """

    command = validate_argv(argv)
    inherited_fds, write_fds = _validated_inherited_fds(
        pass_fds,
        writable_directory_fds,
    )
    if not 0.0 < float(timeout_seconds) <= 86_400.0:
        raise OracleContractError("timeout_seconds is outside the benchmark bound")
    if (
        isinstance(max_output_bytes, bool)
        or not 1 <= max_output_bytes <= 64 * 1024 * 1024
    ):
        raise OracleContractError("max_output_bytes is outside the benchmark bound")
    if not isinstance(input_bytes, bytes) or len(input_bytes) > 64 * 1024:
        raise OracleContractError("input_bytes is outside the benchmark bound")
    executable = Path(command[0])
    expected = ""
    if expected_executable_sha256:
        executable, expected = require_pinned_executable(
            executable, expected_executable_sha256
        )
    child_env = (
        None if env is None else {str(key): str(value) for key, value in env.items()}
    )
    if integrity_check is not None:
        integrity_check()
    try:
        if runner is _DEFAULT_RUNNER:
            returncode, stdout, stderr = _run_streaming_subprocess(
                command,
                timeout_seconds=float(timeout_seconds),
                max_output_bytes=max_output_bytes,
                env=child_env,
                pass_fds=inherited_fds,
                writable_directory_fds=write_fds,
                input_bytes=input_bytes,
            )
        else:
            completed = invoke_argv(
                command,
                runner=runner,
                check=False,
                capture_output=True,
                timeout=float(timeout_seconds),
                env=child_env,
                pass_fds=inherited_fds,
                input=input_bytes,
            )
            returncode = int(completed.returncode)
            raw_stdout = completed.stdout or b""
            raw_stderr = completed.stderr or b""
            stdout = (
                raw_stdout.encode("utf-8")
                if isinstance(raw_stdout, str)
                else bytes(raw_stdout)
            )
            stderr = (
                raw_stderr.encode("utf-8")
                if isinstance(raw_stderr, str)
                else bytes(raw_stderr)
            )
    except OracleExecutionError as exc:
        if expected and sha256_regular_file(executable) != expected:
            raise OracleExecutionError(
                "binary_hash_drift",
                argv=command,
                stdout=exc.stdout,
                stderr=exc.stderr,
                returncode=exc.returncode,
                capture_complete=exc.capture_complete,
            ) from exc
        raise
    except subprocess.TimeoutExpired as exc:
        raw_stdout = exc.stdout or b""
        raw_stderr = exc.stderr or b""
        stdout = raw_stdout if isinstance(raw_stdout, bytes) else raw_stdout.encode()
        remaining = max(0, max_output_bytes - min(len(stdout), max_output_bytes))
        stderr = raw_stderr if isinstance(raw_stderr, bytes) else raw_stderr.encode()
        raise OracleExecutionError(
            "timeout",
            argv=command,
            stdout=stdout[:max_output_bytes],
            stderr=stderr[:remaining],
            capture_complete=False,
        ) from exc
    except (OSError, subprocess.SubprocessError) as exc:
        if expected and sha256_regular_file(executable) != expected:
            raise OracleExecutionError("binary_hash_drift") from exc
        raise OracleExecutionError("launch_failed", argv=command) from exc
    finally:
        if integrity_check is not None:
            integrity_check()
    if len(stdout) + len(stderr) > max_output_bytes:
        stdout_prefix = stdout[:max_output_bytes]
        remaining = max_output_bytes - len(stdout_prefix)
        raise OracleExecutionError(
            "output_too_large",
            argv=command,
            stdout=stdout_prefix,
            stderr=stderr[:remaining],
            returncode=returncode,
            capture_complete=False,
        )
    if expected:
        if sha256_regular_file(executable) != expected:
            raise OracleExecutionError("binary_hash_drift")
    if returncode != 0:
        raise OracleExecutionError(
            "nonzero_exit",
            argv=command,
            stdout=stdout,
            stderr=stderr,
            returncode=returncode,
            capture_complete=True,
        )
    return ExecutionOutput(command, returncode, stdout, stderr)


def sanitized_environment(*, thread_count: int) -> dict[str, str]:
    if isinstance(thread_count, bool) or thread_count <= 0:
        raise OracleContractError("thread_count must be positive")
    path = os.environ.get("PATH", "")
    return {
        "PATH": path,
        "LC_ALL": "C",
        "LANG": "C",
        "OMP_NUM_THREADS": str(thread_count),
        "OPENBLAS_NUM_THREADS": str(thread_count),
        "GMX_DISABLE_GPU_DETECTION": "1",
        "CUDA_VISIBLE_DEVICES": "",
        "HIP_VISIBLE_DEVICES": "",
        "ROCR_VISIBLE_DEVICES": "",
    }
