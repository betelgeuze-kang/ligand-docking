from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import secrets
import stat


@dataclass(frozen=True)
class AttemptArtifactBinding:
    job_id: str
    results_dir: Path
    directory_fd: int


_CURRENT_ATTEMPT: ContextVar[AttemptArtifactBinding | None] = ContextVar(
    "api_current_job_attempt_artifacts",
    default=None,
)


def token_fingerprint(attempt_token: str) -> str:
    """Return the non-capability identifier safe to persist in artifacts."""

    return hashlib.sha256(attempt_token.encode("utf-8")).hexdigest()


def create_attempt_results_dir(
    *,
    storage_root: str | Path,
    job_id: str,
    worker_id: str,
    attempt_token: str,
    attempt_count: int,
) -> Path:
    """Create an exclusive directory bound to one acquired worker attempt."""

    attempt_dir, directory_fd = _create_pinned_attempt_results_dir(
        storage_root=storage_root,
        job_id=job_id,
        worker_id=worker_id,
        attempt_token=attempt_token,
        attempt_count=attempt_count,
    )
    os.close(directory_fd)
    return attempt_dir


def _create_pinned_attempt_results_dir(
    *,
    storage_root: str | Path,
    job_id: str,
    worker_id: str,
    attempt_token: str,
    attempt_count: int,
) -> tuple[Path, int]:
    """Create an attempt through no-follow parent descriptors and keep it open."""

    if not worker_id or not attempt_token or attempt_count < 1:
        raise ValueError("a live worker attempt is required for artifact staging")
    if Path(job_id).parts != (job_id,) or job_id in {"", ".", ".."}:
        raise ValueError("job_id must be one safe path component")
    worker_fingerprint = hashlib.sha256(worker_id.encode("utf-8")).hexdigest()
    attempt_fingerprint = token_fingerprint(attempt_token)
    attempt_name = (
        f"attempt-{attempt_count:06d}-{worker_fingerprint}-{attempt_fingerprint}"
    )
    storage_root_path = Path(
        os.path.abspath(str(Path(storage_root).expanduser()))
    )
    storage_root_path.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory_flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    storage_fd = os.open(storage_root_path, directory_flags)
    job_fd = -1
    attempts_fd = -1
    attempt_fd = -1
    try:
        try:
            os.mkdir(job_id, mode=0o700, dir_fd=storage_fd)
            os.fsync(storage_fd)
        except FileExistsError:
            pass
        job_fd = os.open(job_id, directory_flags, dir_fd=storage_fd)
        try:
            os.mkdir(".attempts", mode=0o700, dir_fd=job_fd)
            os.fsync(job_fd)
        except FileExistsError:
            pass
        attempts_fd = os.open(".attempts", directory_flags, dir_fd=job_fd)
        os.mkdir(attempt_name, mode=0o700, dir_fd=attempts_fd)
        os.fsync(attempts_fd)
        attempt_fd = os.open(attempt_name, directory_flags, dir_fd=attempts_fd)
        if not stat.S_ISDIR(os.fstat(attempt_fd).st_mode):
            raise OSError("created attempt artifact root is not a directory")
        attempt_dir = storage_root_path / job_id / ".attempts" / attempt_name
        return attempt_dir, attempt_fd
    except Exception:
        if attempt_fd >= 0:
            os.close(attempt_fd)
        raise
    finally:
        if attempts_fd >= 0:
            os.close(attempts_fd)
        if job_fd >= 0:
            os.close(job_fd)
        os.close(storage_fd)


def create_and_activate_attempt_results_dir(
    *,
    storage_root: str | Path,
    job_id: str,
    worker_id: str,
    attempt_token: str,
    attempt_count: int,
) -> tuple[Path, Token[AttemptArtifactBinding | None]]:
    """Create and activate an attempt without a pathname re-open race."""

    attempt_dir, directory_fd = _create_pinned_attempt_results_dir(
        storage_root=storage_root,
        job_id=job_id,
        worker_id=worker_id,
        attempt_token=attempt_token,
        attempt_count=attempt_count,
    )
    try:
        token = _CURRENT_ATTEMPT.set(
            AttemptArtifactBinding(
                job_id=job_id,
                results_dir=attempt_dir,
                directory_fd=directory_fd,
            )
        )
    except Exception:
        os.close(directory_fd)
        raise
    return attempt_dir, token


def activate_attempt_results_dir(
    job_id: str,
    results_dir: str | Path,
) -> Token[AttemptArtifactBinding | None]:
    path = Path(os.path.abspath(str(Path(results_dir).expanduser())))
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    directory_fd = os.open(path, flags)
    try:
        is_directory = stat.S_ISDIR(os.fstat(directory_fd).st_mode)
    except Exception:
        os.close(directory_fd)
        raise
    if not is_directory:
        os.close(directory_fd)
        raise OSError("attempt artifact root is not a directory")
    try:
        return _CURRENT_ATTEMPT.set(
            AttemptArtifactBinding(
                job_id=job_id,
                results_dir=path,
                directory_fd=directory_fd,
            )
        )
    except Exception:
        os.close(directory_fd)
        raise


def reset_attempt_results_dir(token: Token[AttemptArtifactBinding | None]) -> None:
    binding = _CURRENT_ATTEMPT.get()
    _CURRENT_ATTEMPT.reset(token)
    if binding is not None:
        os.close(binding.directory_fd)


def resolve_job_results_dir(job_id: str, storage_root: str | Path) -> Path:
    binding = _CURRENT_ATTEMPT.get()
    if binding is not None and binding.job_id == job_id:
        return binding.results_dir
    return Path(storage_root) / job_id


def _relative_attempt_parts(
    binding: AttemptArtifactBinding,
    path_like: str | Path,
) -> tuple[str, ...] | None:
    candidate = Path(path_like).expanduser()
    if not candidate.is_absolute():
        candidate = binding.results_dir / candidate
    normalized = Path(os.path.abspath(str(candidate)))
    try:
        relative = normalized.relative_to(binding.results_dir)
    except ValueError:
        return None
    parts = tuple(relative.parts)
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise PermissionError("attempt artifact path traversal is forbidden")
    return parts


def _open_relative_parent(
    binding: AttemptArtifactBinding,
    parts: tuple[str, ...],
) -> tuple[int, str]:
    pinned_metadata = os.fstat(binding.directory_fd)
    path_metadata = os.stat(binding.results_dir, follow_symlinks=False)
    if (
        not stat.S_ISDIR(path_metadata.st_mode)
        or path_metadata.st_dev != pinned_metadata.st_dev
        or path_metadata.st_ino != pinned_metadata.st_ino
    ):
        raise OSError("attempt artifact root pathname no longer identifies the pinned directory")
    directory_flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    current_fd = os.dup(binding.directory_fd)
    try:
        for part in parts[:-1]:
            next_fd = os.open(part, directory_flags, dir_fd=current_fd)
            if not stat.S_ISDIR(os.fstat(next_fd).st_mode):
                os.close(next_fd)
                raise OSError("attempt artifact parent is not a directory")
            os.close(current_fd)
            current_fd = next_fd
        return current_fd, parts[-1]
    except Exception:
        os.close(current_fd)
        raise


def _open_attempt_regular_file(
    binding: AttemptArtifactBinding,
    parts: tuple[str, ...],
) -> int:
    parent_fd, name = _open_relative_parent(binding, parts)
    file_fd = -1
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    try:
        file_fd = os.open(name, flags, dir_fd=parent_fd)
        metadata = os.fstat(file_fd)
        if not stat.S_ISREG(metadata.st_mode):
            raise OSError("attempt artifact is not a regular file")
        if metadata.st_nlink != 1:
            raise OSError("hard-linked attempt artifacts are forbidden")
        return file_fd
    except Exception:
        if file_fd >= 0:
            os.close(file_fd)
        raise
    finally:
        os.close(parent_fd)


def require_current_attempt_regular_file(path_like: str | Path) -> None:
    """Require a path to be a no-follow regular file in the pinned attempt root."""

    binding = _CURRENT_ATTEMPT.get()
    if binding is None:
        raise PermissionError("no attempt artifact root is active")
    parts = _relative_attempt_parts(binding, path_like)
    if parts is None:
        raise PermissionError("artifact escapes the active attempt root")
    file_fd = _open_attempt_regular_file(binding, parts)
    os.close(file_fd)


def read_current_attempt_file_bytes(
    path_like: str | Path,
    *,
    maximum_bytes: int | None = None,
) -> bytes | None:
    """Read one pinned-attempt file, or return ``None`` for an outside path.

    A returned value is read entirely from one no-follow regular-file descriptor,
    so callers never validate one pathname and subsequently read another inode.
    """

    binding = _CURRENT_ATTEMPT.get()
    if binding is None:
        return None
    parts = _relative_attempt_parts(binding, path_like)
    if parts is None:
        return None
    file_fd = _open_attempt_regular_file(binding, parts)
    try:
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(file_fd, 1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if maximum_bytes is not None and total > maximum_bytes:
                raise OSError("attempt artifact exceeds the permitted size")
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(file_fd)


def sha256_current_attempt_file(path_like: str | Path) -> str | None:
    """Stream a pinned attempt file into SHA-256 without pathname re-opening."""

    binding = _CURRENT_ATTEMPT.get()
    if binding is None:
        return None
    parts = _relative_attempt_parts(binding, path_like)
    if parts is None:
        return None
    file_fd = _open_attempt_regular_file(binding, parts)
    digest = hashlib.sha256()
    try:
        while True:
            chunk = os.read(file_fd, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
        return digest.hexdigest()
    finally:
        os.close(file_fd)


def _write_all(file_fd: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(file_fd, view)
        if written <= 0:
            raise OSError("short attempt artifact write")
        view = view[written:]


def _atomic_write_at(
    directory_fd: int,
    destination_name: str,
    payload: bytes,
    *,
    mode: int,
) -> None:
    temporary_name = f".{destination_name}.{secrets.token_hex(16)}.tmp"
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    file_fd = -1
    try:
        file_fd = os.open(temporary_name, flags, mode, dir_fd=directory_fd)
        metadata = os.fstat(file_fd)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise OSError("temporary artifact is not an exclusive regular file")
        _write_all(file_fd, payload)
        os.fsync(file_fd)
        os.close(file_fd)
        file_fd = -1
        os.replace(
            temporary_name,
            destination_name,
            src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd,
        )
        os.fsync(directory_fd)
    except Exception:
        if file_fd >= 0:
            os.close(file_fd)
        try:
            os.unlink(temporary_name, dir_fd=directory_fd)
        except OSError:
            pass
        raise


def atomic_write_file(
    path_like: str | Path,
    payload: bytes,
    *,
    mode: int = 0o600,
    allow_outside_active_attempt: bool = False,
) -> None:
    """Publish bytes without opening or truncating the destination inode."""

    binding = _CURRENT_ATTEMPT.get()
    parts = _relative_attempt_parts(binding, path_like) if binding is not None else None
    if binding is not None and parts is not None:
        parent_fd, destination_name = _open_relative_parent(binding, parts)
        try:
            _atomic_write_at(parent_fd, destination_name, payload, mode=mode)
        finally:
            os.close(parent_fd)
        return
    if binding is not None and not allow_outside_active_attempt:
        raise PermissionError("write escapes the active attempt artifact root")

    path = Path(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    directory_flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    directory_fd = os.open(path.parent, directory_flags)
    try:
        _atomic_write_at(directory_fd, path.name, payload, mode=mode)
    finally:
        os.close(directory_fd)


def atomic_write_text_file(
    path_like: str | Path,
    payload: str,
    *,
    encoding: str = "utf-8",
    mode: int = 0o600,
    allow_outside_active_attempt: bool = False,
) -> None:
    atomic_write_file(
        path_like,
        payload.encode(encoding),
        mode=mode,
        allow_outside_active_attempt=allow_outside_active_attempt,
    )
