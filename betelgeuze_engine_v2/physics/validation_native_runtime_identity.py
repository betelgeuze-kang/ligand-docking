"""Fail-closed native executable mapping and worker lifecycle evidence.

The measurement path is Linux-only and deliberately standard-library only.  It
reads ``/proc/self/maps`` twice around a bounded hash of every file backing an
executable VMA.  File descriptors are opened component-by-component with
``O_NOFOLLOW`` so the resulting manifest is evidence about the objects named by
the kernel mapping table rather than about a later pathname replacement.

This module has no import-time measurement or filesystem side effect.  A
caller must explicitly request a snapshot or build lifecycle evidence.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import re
import selectors
import signal
import stat
import subprocess
import time
from typing import Any, Mapping, Sequence


NATIVE_RUNTIME_SNAPSHOT_SCHEMA_ID = "betelgeuze.engine_v2_native_runtime_snapshot/1.0.0"
WORKER_RUNTIME_PRE_EVIDENCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_worker_runtime_pre_evidence/1.0.0"
)
WORKER_RUNTIME_PAYLOAD_EVIDENCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_worker_runtime_payload_evidence/1.0.0"
)
WORKER_RUNTIME_POST_EVIDENCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_worker_runtime_post_evidence/1.0.0"
)
WORKER_RUNTIME_LIFECYCLE_EVIDENCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_worker_runtime_lifecycle_evidence/1.0.0"
)

WORKER_RUNTIME_LANE_ENERGY_FORCE = "27-case-59-variant-energy-force"
WORKER_RUNTIME_LANE_ENERGY_FORCE_MANIFEST = "27-case-59-variant-energy-force-manifest"
WORKER_RUNTIME_LANE_MINIMIZATION = "14-case-minimization"
WORKER_RUNTIME_LANES = (
    WORKER_RUNTIME_LANE_ENERGY_FORCE,
    WORKER_RUNTIME_LANE_ENERGY_FORCE_MANIFEST,
    WORKER_RUNTIME_LANE_MINIMIZATION,
)

NATIVE_RUNTIME_MAPS_PATH = "/proc/self/maps"
NATIVE_RUNTIME_MAX_WALL_SECONDS = 180.0
NATIVE_RUNTIME_MAX_MAPS_BYTES = 16 * 1024**2
NATIVE_RUNTIME_MAX_MAP_ROWS = 16_384
NATIVE_RUNTIME_MAX_PATH_BYTES = 4_096
NATIVE_RUNTIME_MAX_FILES = 4_096
NATIVE_RUNTIME_MAX_FILE_BYTES = 1024**3
NATIVE_RUNTIME_MAX_TOTAL_FILE_BYTES = 8 * 1024**3
NATIVE_RUNTIME_READ_CHUNK_BYTES = 1024 * 1024
WORKER_RUNTIME_MAX_PAYLOAD_ROW_BYTES = 32 * 1024**2
WORKER_RUNTIME_MAX_PAYLOAD_BYTES = 256 * 1024**2
WORKER_RUNTIME_MAX_ROW_ID_BYTES = 512
WORKER_RUNTIME_PIPE_READ_CHUNK_BYTES = 64 * 1024
WORKER_RUNTIME_REAP_MAX_WALL_SECONDS = 5.0

_MAPS_ROW_PATTERN = re.compile(
    rb"([0-9a-f]+)-([0-9a-f]+) "
    rb"([r-][w-][x-][ps]) "
    rb"([0-9a-f]+) "
    rb"([0-9a-f]+):([0-9a-f]+) "
    rb"([0-9]+)(?: +((?:/|\[).*))? *"
)
_SPECIAL_EXECUTABLE_MAPPINGS = frozenset({"[vdso]", "[vsyscall]"})
_SNAPSHOT_FIELDS = frozenset(
    {
        "schema_id",
        "process_id",
        "mapping_count",
        "file_count",
        "hashed_file_bytes",
        "mapping_rows",
        "file_rows",
        "snapshot_sha256",
    }
)
_MAPPING_ROW_FIELDS = frozenset(
    {
        "ordinal",
        "address_start_hex",
        "address_end_hex",
        "permissions",
        "file_offset_hex",
        "device_major_hex",
        "device_minor_hex",
        "inode",
        "path",
        "backing_kind",
        "backing_file_identity_sha256",
    }
)
_FILE_ROW_FIELDS = frozenset(
    {
        "ordinal",
        "path",
        "device_major_hex",
        "device_minor_hex",
        "inode",
        "mode_octal",
        "uid",
        "gid",
        "link_count",
        "size_bytes",
        "mtime_ns",
        "ctime_ns",
        "sha256",
        "file_identity_sha256",
    }
)
_MATERIALIZATION_MANIFEST_FIELDS = frozenset(
    {
        "schema_id",
        "materializer_id",
        "materializer_version",
        "materializer_source_sha256",
        "protocol_sha256",
        "fixture_manifest_sha256",
        "materialization_policy",
        "coverage",
        "cases",
        "result_collection_performed",
        "energy_or_force_values_present",
        "metric_values_present",
        "validation_execution_authorized",
        "scientifically_validated",
        "claim_safe",
        "materialization_manifest_sha256",
    }
)
_MATERIALIZATION_CASE_FIELDS = frozenset(
    {
        "case_id",
        "case_input_sha256",
        "fixture_profile_id",
        "fixture_profile_sha256",
        "mutation_contract_id",
        "mutation_contract_sha256",
        "expected_outcome",
        "expected_error_code",
        "variant_count",
        "variants",
        "result_fields_present",
        "materialization_sha256",
    }
)


class ValidationNativeRuntimeIdentityError(RuntimeError):
    """Native mapping or worker lifecycle evidence is unsafe or malformed."""


def _close_pipe(pipe: object | None) -> None:
    if pipe is None:
        return
    try:
        pipe.close()  # type: ignore[attr-defined]
    except (OSError, ValueError):
        pass


def _terminate_worker_process_group(process: Any) -> None:
    pid = getattr(process, "pid", None)
    group_killed = False
    if type(pid) is int and pid > 0:
        try:
            process_group_id = os.getpgid(pid)
        except ProcessLookupError:
            process_group_id = pid
        except OSError:
            process_group_id = None
        if process_group_id == pid:
            try:
                os.killpg(pid, signal.SIGKILL)
                group_killed = True
            except ProcessLookupError:
                group_killed = True
            except OSError:
                pass
    if not group_killed:
        try:
            process.kill()
        except (OSError, ProcessLookupError):
            pass


def _reap_worker_process(process: Any) -> None:
    try:
        process.wait(timeout=WORKER_RUNTIME_REAP_MAX_WALL_SECONDS)
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        raise ValidationNativeRuntimeIdentityError(
            "worker process could not be reaped after termination"
        ) from exc


def communicate_bounded_worker_process(
    process: Any,
    request_bytes: bytes,
    *,
    deadline: float,
    max_output_bytes: int,
) -> tuple[bytes, bool, bool]:
    """Exchange one request with a worker without ever buffering past the cap."""

    if (
        not isinstance(request_bytes, bytes)
        or not request_bytes
        or type(deadline) is not float
        or not math.isfinite(deadline)
        or type(max_output_bytes) is not int
        or max_output_bytes <= 0
    ):
        raise ValidationNativeRuntimeIdentityError(
            "bounded worker communication arguments are invalid"
        )
    stdin = getattr(process, "stdin", None)
    stdout = getattr(process, "stdout", None)
    if stdin is None or stdout is None:
        raise ValidationNativeRuntimeIdentityError(
            "bounded worker communication requires stdin and stdout pipes"
        )
    try:
        stdin_fd = stdin.fileno()
        stdout_fd = stdout.fileno()
        os.set_blocking(stdin_fd, False)
        os.set_blocking(stdout_fd, False)
    except (AttributeError, OSError, ValueError) as exc:
        raise ValidationNativeRuntimeIdentityError(
            "bounded worker pipes are invalid"
        ) from exc

    selector = selectors.DefaultSelector()
    output = bytearray()
    request_offset = 0
    timed_out = False
    communication_failed = False
    output_exceeded = False
    process_terminated = False
    stdin_open = True
    stdout_open = True
    try:
        selector.register(stdin_fd, selectors.EVENT_WRITE, "stdin")
        selector.register(stdout_fd, selectors.EVENT_READ, "stdout")
        while stdin_open or stdout_open:
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                timed_out = True
                _terminate_worker_process_group(process)
                process_terminated = True
                break
            events = selector.select(remaining)
            if not events:
                timed_out = True
                _terminate_worker_process_group(process)
                process_terminated = True
                break
            for key, _mask in events:
                if key.data == "stdin":
                    try:
                        written = os.write(stdin_fd, request_bytes[request_offset:])
                    except BlockingIOError:
                        continue
                    except (BrokenPipeError, OSError):
                        communication_failed = True
                        written = 0
                    request_offset += written
                    if communication_failed or request_offset == len(request_bytes):
                        selector.unregister(stdin_fd)
                        _close_pipe(stdin)
                        stdin_open = False
                else:
                    remaining_capacity = max_output_bytes - len(output) + 1
                    try:
                        chunk = os.read(
                            stdout_fd,
                            min(
                                WORKER_RUNTIME_PIPE_READ_CHUNK_BYTES,
                                remaining_capacity,
                            ),
                        )
                    except BlockingIOError:
                        continue
                    except OSError:
                        communication_failed = True
                        chunk = b""
                    if chunk:
                        output.extend(chunk)
                        if len(output) > max_output_bytes:
                            output_exceeded = True
                            _terminate_worker_process_group(process)
                            process_terminated = True
                            break
                    else:
                        selector.unregister(stdout_fd)
                        _close_pipe(stdout)
                        stdout_open = False
            if output_exceeded:
                break
        if not process_terminated:
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                timed_out = True
                _terminate_worker_process_group(process)
                process_terminated = True
            else:
                try:
                    process.wait(timeout=remaining)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    _terminate_worker_process_group(process)
                    process_terminated = True
    finally:
        selector.close()
        if stdin_open:
            _close_pipe(stdin)
        if stdout_open:
            _close_pipe(stdout)
    if process_terminated:
        _reap_worker_process(process)
    return (
        b"" if output_exceeded or communication_failed else bytes(output),
        timed_out,
        not timed_out
        and not communication_failed
        and not output_exceeded
        and getattr(process, "returncode", None) == 0,
    )


def require_complete_worker_runtime_process_id(
    lifecycle: Mapping[str, Any],
    *,
    expected_process_id: int,
) -> None:
    """Bind both accepted endpoint snapshots to the supervisor's child PID."""

    if type(expected_process_id) is not int or expected_process_id <= 0:
        raise ValidationNativeRuntimeIdentityError(
            "expected worker process id is invalid"
        )
    if not isinstance(lifecycle, Mapping) or lifecycle.get("completion_state") != (
        "complete"
    ):
        raise ValidationNativeRuntimeIdentityError(
            "worker process identity requires a complete lifecycle"
        )
    try:
        pre_process_id = lifecycle["pre"]["snapshot"]["process_id"]
        post_process_id = lifecycle["post"]["snapshot"]["process_id"]
    except (KeyError, TypeError) as exc:
        raise ValidationNativeRuntimeIdentityError(
            "worker lifecycle process identity is absent"
        ) from exc
    if pre_process_id != expected_process_id or post_process_id != expected_process_id:
        raise ValidationNativeRuntimeIdentityError(
            "worker lifecycle process identity mismatches the supervised child"
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
        raise ValidationNativeRuntimeIdentityError(
            "native runtime evidence is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _plain_copy(value: object) -> Any:
    try:
        return json.loads(_canonical_bytes(value).decode("ascii"))
    except json.JSONDecodeError as exc:  # pragma: no cover - canonical encoder output
        raise ValidationNativeRuntimeIdentityError(
            "native runtime evidence cannot be copied"
        ) from exc


def _require_exact_document(
    observed: Mapping[str, Any], expected: Mapping[str, Any], *, name: str
) -> None:
    if not hmac.compare_digest(
        _canonical_bytes(dict(observed)), _canonical_bytes(dict(expected))
    ):
        raise ValidationNativeRuntimeIdentityError(
            f"{name} is not the exact canonical schema"
        )


def _require_sha256(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValidationNativeRuntimeIdentityError(f"{name} is not a lowercase SHA-256")
    return value


def _require_nonnegative_int(value: object, *, name: str) -> int:
    if type(value) is not int or value < 0:
        raise ValidationNativeRuntimeIdentityError(
            f"{name} is not a nonnegative integer"
        )
    return value


def _require_positive_int(value: object, *, name: str) -> int:
    if type(value) is not int or value <= 0:
        raise ValidationNativeRuntimeIdentityError(f"{name} is not a positive integer")
    return value


def _require_canonical_hex(
    value: object, *, name: str, allow_zero: bool = True
) -> tuple[str, int]:
    if (
        not isinstance(value, str)
        or not value
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValidationNativeRuntimeIdentityError(
            f"{name} is not lowercase hexadecimal"
        )
    try:
        number = int(value, 16)
    except ValueError as exc:  # pragma: no cover - guarded above
        raise ValidationNativeRuntimeIdentityError(f"{name} is invalid") from exc
    if (
        number > 2**64 - 1
        or format(number, "x") != value
        or (not allow_zero and number == 0)
    ):
        raise ValidationNativeRuntimeIdentityError(
            f"{name} is not canonical hexadecimal"
        )
    return value, number


def _require_lane(value: object) -> str:
    if value not in WORKER_RUNTIME_LANES:
        raise ValidationNativeRuntimeIdentityError("worker runtime lane is invalid")
    return str(value)


def _require_row_id(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValidationNativeRuntimeIdentityError(
            "worker payload row identity is invalid"
        )
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValidationNativeRuntimeIdentityError(
            "worker payload row identity is invalid"
        ) from exc
    if (
        len(encoded) > WORKER_RUNTIME_MAX_ROW_ID_BYTES
        or "\x00" in value
        or any(ord(character) < 0x20 or ord(character) == 0x7F for character in value)
    ):
        raise ValidationNativeRuntimeIdentityError(
            "worker payload row identity is invalid"
        )
    return value


def _deadline_or_default(deadline: float | None) -> float:
    if deadline is None:
        return time.monotonic() + NATIVE_RUNTIME_MAX_WALL_SECONDS
    if (
        type(deadline) is not float
        or not math.isfinite(deadline)
        or deadline <= time.monotonic()
    ):
        raise ValidationNativeRuntimeIdentityError(
            "native runtime measurement deadline is invalid or expired"
        )
    return deadline


def _checkpoint(deadline: float) -> None:
    if time.monotonic() >= deadline:
        raise ValidationNativeRuntimeIdentityError(
            "native runtime measurement deadline expired"
        )


def _stable_stat_identity(file_stat: os.stat_result) -> tuple[int, ...]:
    return (
        file_stat.st_dev,
        file_stat.st_ino,
        file_stat.st_mode,
        file_stat.st_uid,
        file_stat.st_gid,
        file_stat.st_nlink,
        file_stat.st_size,
        file_stat.st_mtime_ns,
        file_stat.st_ctime_ns,
    )


def _require_trusted_directory_stat(file_stat: os.stat_result) -> None:
    if (
        not stat.S_ISDIR(file_stat.st_mode)
        or file_stat.st_uid != 0
        or stat.S_IMODE(file_stat.st_mode) & 0o022
    ):
        raise ValidationNativeRuntimeIdentityError(
            "native mapping directory is not root-owned and group/world read-only"
        )


def _require_trusted_file_stat(file_stat: os.stat_result) -> None:
    if (
        not stat.S_ISREG(file_stat.st_mode)
        or file_stat.st_uid != 0
        or stat.S_IMODE(file_stat.st_mode) & 0o022
        or file_stat.st_nlink <= 0
    ):
        raise ValidationNativeRuntimeIdentityError(
            "native mapping is not a root-owned, non-group/world-writable regular file"
        )


def _open_trusted_absolute_file(
    path: str, *, deadline: float
) -> tuple[int, os.stat_result]:
    _checkpoint(deadline)
    if (
        not path.startswith("/")
        or path == "/"
        or os.path.normpath(path) != path
        or path.startswith("//")
    ):
        raise ValidationNativeRuntimeIdentityError(
            "native executable mapping path is not canonical absolute"
        )
    components = path.split("/")[1:]
    if not components or any(
        not component or component in {".", ".."} for component in components
    ):
        raise ValidationNativeRuntimeIdentityError(
            "native executable mapping path is ambiguous"
        )
    nofollow = getattr(os, "O_NOFOLLOW", None)
    directory_flag = getattr(os, "O_DIRECTORY", None)
    cloexec = getattr(os, "O_CLOEXEC", None)
    if nofollow is None or directory_flag is None or cloexec is None:
        raise ValidationNativeRuntimeIdentityError(
            "required Linux no-follow open flags are unavailable"
        )
    directory_flags = os.O_RDONLY | directory_flag | cloexec | nofollow
    file_flags = os.O_RDONLY | cloexec | nofollow
    try:
        directory_fd = os.open("/", directory_flags)
    except OSError as exc:
        raise ValidationNativeRuntimeIdentityError(
            "native mapping root directory cannot be opened safely"
        ) from exc
    try:
        _require_trusted_directory_stat(os.fstat(directory_fd))
        for component in components[:-1]:
            _checkpoint(deadline)
            try:
                before = os.stat(component, dir_fd=directory_fd, follow_symlinks=False)
                next_fd = os.open(component, directory_flags, dir_fd=directory_fd)
                after = os.fstat(next_fd)
            except OSError as exc:
                raise ValidationNativeRuntimeIdentityError(
                    "native mapping directory chain cannot be opened without symlinks"
                ) from exc
            if _stable_stat_identity(before) != _stable_stat_identity(after):
                os.close(next_fd)
                raise ValidationNativeRuntimeIdentityError(
                    "native mapping directory changed while measured"
                )
            try:
                _require_trusted_directory_stat(after)
            except Exception:
                os.close(next_fd)
                raise
            os.close(directory_fd)
            directory_fd = next_fd
        _checkpoint(deadline)
        basename = components[-1]
        try:
            before = os.stat(basename, dir_fd=directory_fd, follow_symlinks=False)
            file_fd = os.open(basename, file_flags, dir_fd=directory_fd)
            after = os.fstat(file_fd)
        except OSError as exc:
            raise ValidationNativeRuntimeIdentityError(
                "native mapping file cannot be opened with O_NOFOLLOW"
            ) from exc
        if _stable_stat_identity(before) != _stable_stat_identity(after):
            os.close(file_fd)
            raise ValidationNativeRuntimeIdentityError(
                "native mapping file changed while opened"
            )
        try:
            _require_trusted_file_stat(after)
        except Exception:
            os.close(file_fd)
            raise
        return file_fd, after
    finally:
        os.close(directory_fd)


def _read_maps_bounded(*, deadline: float) -> bytes:
    _checkpoint(deadline)
    descriptor = _open_proc_self_maps_descriptor()
    chunks: list[bytes] = []
    observed = 0
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ValidationNativeRuntimeIdentityError(
                "/proc/self/maps is not a regular procfs view"
            )
        while True:
            _checkpoint(deadline)
            try:
                chunk = os.read(descriptor, NATIVE_RUNTIME_READ_CHUNK_BYTES)
            except OSError as exc:
                raise ValidationNativeRuntimeIdentityError(
                    "/proc/self/maps cannot be read"
                ) from exc
            if not chunk:
                break
            observed += len(chunk)
            if observed > NATIVE_RUNTIME_MAX_MAPS_BYTES:
                raise ValidationNativeRuntimeIdentityError(
                    "/proc/self/maps exceeds its byte bound"
                )
            chunks.append(chunk)
        after = os.fstat(descriptor)
        if _stable_stat_identity(before) != _stable_stat_identity(after):
            raise ValidationNativeRuntimeIdentityError(
                "/proc/self/maps identity changed while read"
            )
    finally:
        os.close(descriptor)
    raw = b"".join(chunks)
    if not raw or not raw.endswith(b"\n") or b"\x00" in raw:
        raise ValidationNativeRuntimeIdentityError("/proc/self/maps framing is invalid")
    return raw


def _open_proc_self_maps_descriptor() -> int:
    """Open the calling process's real procfs maps view, not a substitute file."""

    nofollow = getattr(os, "O_NOFOLLOW", None)
    cloexec = getattr(os, "O_CLOEXEC", None)
    if nofollow is None or cloexec is None:
        raise ValidationNativeRuntimeIdentityError(
            "required Linux no-follow open flags are unavailable"
        )
    if NATIVE_RUNTIME_MAPS_PATH != "/proc/self/maps":
        raise ValidationNativeRuntimeIdentityError(
            "/proc/self/maps path identity is not fixed"
        )
    try:
        proc_stat = os.stat("/proc", follow_symlinks=False)
        pid_maps_stat = os.stat(
            f"/proc/{os.getpid()}/maps",
            follow_symlinks=False,
        )
        descriptor = os.open(
            "/proc/self/maps",
            os.O_RDONLY | cloexec | nofollow,
        )
    except OSError as exc:
        raise ValidationNativeRuntimeIdentityError(
            "/proc/self/maps cannot be opened safely"
        ) from exc
    try:
        descriptor_stat = os.fstat(descriptor)
        if (
            not stat.S_ISDIR(proc_stat.st_mode)
            or proc_stat.st_uid != 0
            or stat.S_IMODE(proc_stat.st_mode) & 0o022
            or not stat.S_ISREG(pid_maps_stat.st_mode)
            or descriptor_stat.st_dev != proc_stat.st_dev
            or (
                descriptor_stat.st_dev,
                descriptor_stat.st_ino,
                descriptor_stat.st_mode,
                descriptor_stat.st_uid,
                descriptor_stat.st_gid,
            )
            != (
                pid_maps_stat.st_dev,
                pid_maps_stat.st_ino,
                pid_maps_stat.st_mode,
                pid_maps_stat.st_uid,
                pid_maps_stat.st_gid,
            )
        ):
            raise ValidationNativeRuntimeIdentityError(
                "/proc/self/maps is not bound to the calling process procfs view"
            )
    except Exception:
        os.close(descriptor)
        raise
    return descriptor


def _parse_maps(raw: bytes, *, deadline: float) -> list[dict[str, Any]]:
    lines = raw.splitlines()
    if not lines or len(lines) > NATIVE_RUNTIME_MAX_MAP_ROWS:
        raise ValidationNativeRuntimeIdentityError(
            "/proc/self/maps row count is invalid or exceeds its bound"
        )
    parsed: list[dict[str, Any]] = []
    previous_end = 0
    for row_index, line in enumerate(lines):
        _checkpoint(deadline)
        if not line or len(line) > NATIVE_RUNTIME_MAX_PATH_BYTES + 256:
            raise ValidationNativeRuntimeIdentityError(
                "/proc/self/maps contains an invalid row length"
            )
        match = _MAPS_ROW_PATTERN.fullmatch(line)
        if match is None:
            raise ValidationNativeRuntimeIdentityError(
                "/proc/self/maps contains an ambiguous row"
            )
        (
            raw_start,
            raw_end,
            raw_permissions,
            raw_offset,
            raw_major,
            raw_minor,
            raw_inode,
            raw_path,
        ) = match.groups()
        start = int(raw_start, 16)
        end = int(raw_end, 16)
        offset = int(raw_offset, 16)
        major = int(raw_major, 16)
        minor = int(raw_minor, 16)
        inode = int(raw_inode, 10)
        if (
            start < previous_end
            or end <= start
            or end > 2**64
            or offset > 2**64 - 1
            or major > 2**32 - 1
            or minor > 2**32 - 1
            or inode > 2**64 - 1
        ):
            raise ValidationNativeRuntimeIdentityError(
                "/proc/self/maps address or identity range is invalid"
            )
        previous_end = end
        permissions = raw_permissions.decode("ascii")
        if permissions[1:3] == "wx":
            raise ValidationNativeRuntimeIdentityError(
                "writable executable native mapping is forbidden"
            )
        path: str | None = None
        if raw_path is not None:
            if len(raw_path) > NATIVE_RUNTIME_MAX_PATH_BYTES or b"\\" in raw_path:
                raise ValidationNativeRuntimeIdentityError(
                    "native mapping pathname is oversized or ambiguous"
                )
            try:
                path = raw_path.decode("utf-8", errors="strict")
            except UnicodeDecodeError as exc:
                raise ValidationNativeRuntimeIdentityError(
                    "native mapping pathname is not unambiguous UTF-8"
                ) from exc
            if any(
                ord(character) < 0x20 or ord(character) == 0x7F for character in path
            ):
                raise ValidationNativeRuntimeIdentityError(
                    "native mapping pathname contains a control character"
                )
        parsed.append(
            {
                "row_index": row_index,
                "start": start,
                "end": end,
                "permissions": permissions,
                "offset": offset,
                "major": major,
                "minor": minor,
                "raw_major": raw_major,
                "raw_minor": raw_minor,
                "inode": inode,
                "path": path,
            }
        )
    return parsed


def _executable_maps_projection(
    parsed_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "address_start_hex": format(row["start"], "x"),
            "address_end_hex": format(row["end"], "x"),
            "permissions": row["permissions"],
            "file_offset_hex": format(row["offset"], "x"),
            "device_major_hex": format(row["major"], "x"),
            "device_minor_hex": format(row["minor"], "x"),
            "inode": row["inode"],
            "path": row["path"],
        }
        for row in parsed_rows
        if row["permissions"][2] == "x"
    ]


def _hash_open_file(
    descriptor: int,
    before: os.stat_result,
    *,
    already_hashed_bytes: int,
    deadline: float,
) -> tuple[str, os.stat_result]:
    size = before.st_size
    if (
        size < 0
        or size > NATIVE_RUNTIME_MAX_FILE_BYTES
        or size > NATIVE_RUNTIME_MAX_TOTAL_FILE_BYTES - already_hashed_bytes
    ):
        raise ValidationNativeRuntimeIdentityError(
            "native mapping file exceeds its pre-read byte bound"
        )
    digest = hashlib.sha256()
    observed = 0
    while True:
        _checkpoint(deadline)
        try:
            chunk = os.read(
                descriptor, min(NATIVE_RUNTIME_READ_CHUNK_BYTES, size - observed + 1)
            )
        except OSError as exc:
            raise ValidationNativeRuntimeIdentityError(
                "native mapping file cannot be hashed"
            ) from exc
        if not chunk:
            break
        observed += len(chunk)
        if observed > size or observed > NATIVE_RUNTIME_MAX_FILE_BYTES:
            raise ValidationNativeRuntimeIdentityError(
                "native mapping file grew while measured"
            )
        digest.update(chunk)
    after = os.fstat(descriptor)
    if observed != size or _stable_stat_identity(before) != _stable_stat_identity(
        after
    ):
        raise ValidationNativeRuntimeIdentityError(
            "native mapping file changed while measured"
        )
    return digest.hexdigest(), after


def _file_identity_projection(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "path": row["path"],
        "device_major_hex": row["device_major_hex"],
        "device_minor_hex": row["device_minor_hex"],
        "inode": row["inode"],
        "mode_octal": row["mode_octal"],
        "uid": row["uid"],
        "gid": row["gid"],
        "link_count": row["link_count"],
        "size_bytes": row["size_bytes"],
        "mtime_ns": row["mtime_ns"],
        "ctime_ns": row["ctime_ns"],
        "sha256": row["sha256"],
    }


def _measure_file_row(
    parsed: Mapping[str, Any],
    *,
    already_hashed_bytes: int,
    deadline: float,
) -> dict[str, Any]:
    path = parsed["path"]
    if not isinstance(path, str):  # pragma: no cover - guarded by caller
        raise ValidationNativeRuntimeIdentityError("native mapping path is absent")
    descriptor, before = _open_trusted_absolute_file(path, deadline=deadline)
    try:
        observed_major = os.major(before.st_dev)
        observed_minor = os.minor(before.st_dev)
        if (
            observed_major != parsed["major"]
            or observed_minor != parsed["minor"]
            or before.st_ino != parsed["inode"]
        ):
            raise ValidationNativeRuntimeIdentityError(
                "native mapping maps-vs-fd device or inode identity mismatches"
            )
        if parsed["offset"] >= before.st_size:
            raise ValidationNativeRuntimeIdentityError(
                "native executable mapping offset is outside its file"
            )
        digest, after = _hash_open_file(
            descriptor,
            before,
            already_hashed_bytes=already_hashed_bytes,
            deadline=deadline,
        )
    finally:
        os.close(descriptor)
    row: dict[str, Any] = {
        "path": path,
        "device_major_hex": format(observed_major, "x"),
        "device_minor_hex": format(observed_minor, "x"),
        "inode": after.st_ino,
        "mode_octal": format(stat.S_IMODE(after.st_mode), "04o"),
        "uid": after.st_uid,
        "gid": after.st_gid,
        "link_count": after.st_nlink,
        "size_bytes": after.st_size,
        "mtime_ns": after.st_mtime_ns,
        "ctime_ns": after.st_ctime_ns,
        "sha256": digest,
    }
    row["file_identity_sha256"] = _sha256(_file_identity_projection(row))
    return row


def measure_native_runtime_snapshot(*, deadline: float | None = None) -> dict[str, Any]:
    """Measure every resident executable VMA in the calling Linux process."""

    measurement_deadline = _deadline_or_default(deadline)
    raw_maps = _read_maps_bounded(deadline=measurement_deadline)
    parsed_rows = _parse_maps(raw_maps, deadline=measurement_deadline)
    executable_rows = [row for row in parsed_rows if row["permissions"][2] == "x"]
    if not executable_rows:
        raise ValidationNativeRuntimeIdentityError(
            "process has no executable native mappings"
        )

    file_by_kernel_identity: dict[tuple[int, int], dict[str, Any]] = {}
    mapping_sources: list[tuple[dict[str, Any], str, str | None]] = []
    observed_special_mappings: set[str] = set()
    hashed_file_bytes = 0
    for parsed in executable_rows:
        _checkpoint(measurement_deadline)
        path = parsed["path"]
        if path in _SPECIAL_EXECUTABLE_MAPPINGS:
            if path in observed_special_mappings:
                raise ValidationNativeRuntimeIdentityError(
                    "kernel executable mapping exception is duplicated"
                )
            if (
                parsed["raw_major"] != b"00"
                or parsed["raw_minor"] != b"00"
                or parsed["inode"] != 0
                or parsed["offset"] != 0
                or parsed["permissions"][1] == "w"
                or parsed["permissions"][3] != "p"
            ):
                raise ValidationNativeRuntimeIdentityError(
                    "kernel executable mapping exception is not narrow"
                )
            observed_special_mappings.add(path)
            mapping_sources.append((parsed, "kernel", None))
            continue
        if path is None:
            raise ValidationNativeRuntimeIdentityError(
                "anonymous executable native mapping is forbidden"
            )
        lowered_path = path.lower()
        if (
            path.startswith("[")
            or "memfd:" in lowered_path
            or path.endswith(" (deleted)")
            or not path.startswith("/")
        ):
            raise ValidationNativeRuntimeIdentityError(
                "deleted, memfd, special, or non-absolute executable mapping is forbidden"
            )
        identity = (parsed["major"], parsed["minor"], parsed["inode"])
        existing = file_by_kernel_identity.get(identity)
        if existing is None:
            if len(file_by_kernel_identity) >= NATIVE_RUNTIME_MAX_FILES:
                raise ValidationNativeRuntimeIdentityError(
                    "native mapping file count exceeds its bound"
                )
            measured = _measure_file_row(
                parsed,
                already_hashed_bytes=hashed_file_bytes,
                deadline=measurement_deadline,
            )
            file_by_kernel_identity[identity] = measured
            hashed_file_bytes += measured["size_bytes"]
            existing = measured
        elif existing["path"] != path:
            raise ValidationNativeRuntimeIdentityError(
                "one executable native object is exposed through multiple pathnames"
            )
        mapping_sources.append((parsed, "file", existing["file_identity_sha256"]))

    second_raw_maps = _read_maps_bounded(deadline=measurement_deadline)
    second_parsed_rows = _parse_maps(
        second_raw_maps,
        deadline=measurement_deadline,
    )
    first_executable_projection = _executable_maps_projection(parsed_rows)
    second_executable_projection = _executable_maps_projection(second_parsed_rows)
    if not hmac.compare_digest(
        _canonical_bytes(first_executable_projection),
        _canonical_bytes(second_executable_projection),
    ):
        raise ValidationNativeRuntimeIdentityError(
            "executable native mapping set changed while measured"
        )

    file_rows_without_ordinal = sorted(
        file_by_kernel_identity.values(),
        key=lambda row: (
            row["path"],
            int(row["device_major_hex"], 16),
            int(row["device_minor_hex"], 16),
            row["inode"],
        ),
    )
    file_rows = [
        {"ordinal": ordinal, **row}
        for ordinal, row in enumerate(file_rows_without_ordinal)
    ]
    mapping_rows: list[dict[str, Any]] = []
    for ordinal, (parsed, backing_kind, file_identity_sha256) in enumerate(
        mapping_sources
    ):
        mapping_rows.append(
            {
                "ordinal": ordinal,
                "address_start_hex": format(parsed["start"], "x"),
                "address_end_hex": format(parsed["end"], "x"),
                "permissions": parsed["permissions"],
                "file_offset_hex": format(parsed["offset"], "x"),
                "device_major_hex": format(parsed["major"], "x"),
                "device_minor_hex": format(parsed["minor"], "x"),
                "inode": parsed["inode"],
                "path": parsed["path"],
                "backing_kind": backing_kind,
                "backing_file_identity_sha256": file_identity_sha256,
            }
        )
    projection = {
        "schema_id": NATIVE_RUNTIME_SNAPSHOT_SCHEMA_ID,
        "process_id": os.getpid(),
        "mapping_count": len(mapping_rows),
        "file_count": len(file_rows),
        "hashed_file_bytes": hashed_file_bytes,
        "mapping_rows": mapping_rows,
        "file_rows": file_rows,
    }
    document = {**projection, "snapshot_sha256": _sha256(projection)}
    return require_native_runtime_snapshot(document)


def _require_file_row(value: object, *, ordinal: int) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _FILE_ROW_FIELDS:
        raise ValidationNativeRuntimeIdentityError(
            "native snapshot file row schema is invalid"
        )
    row = dict(value)
    if row["ordinal"] != ordinal or type(row["ordinal"]) is not int:
        raise ValidationNativeRuntimeIdentityError(
            "native snapshot file row order is invalid"
        )
    path = row["path"]
    if (
        not isinstance(path, str)
        or not path.startswith("/")
        or path == "/"
        or path.startswith("//")
        or os.path.normpath(path) != path
    ):
        raise ValidationNativeRuntimeIdentityError(
            "native snapshot file path is invalid"
        )
    try:
        path_bytes = path.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValidationNativeRuntimeIdentityError(
            "native snapshot file path is invalid"
        ) from exc
    if (
        not path_bytes
        or len(path_bytes) > NATIVE_RUNTIME_MAX_PATH_BYTES
        or b"\\" in path_bytes
        or b"\x00" in path_bytes
        or any(byte < 0x20 or byte == 0x7F for byte in path_bytes)
        or any(
            not component or component in {".", ".."}
            for component in path.split("/")[1:]
        )
    ):
        raise ValidationNativeRuntimeIdentityError(
            "native snapshot file path is invalid"
        )
    _, major = _require_canonical_hex(
        row["device_major_hex"], name="native file device major"
    )
    _, minor = _require_canonical_hex(
        row["device_minor_hex"], name="native file device minor"
    )
    inode = _require_positive_int(row["inode"], name="native file inode")
    if major > 2**32 - 1 or minor > 2**32 - 1 or inode > 2**64 - 1:
        raise ValidationNativeRuntimeIdentityError(
            "native snapshot file identity is out of range"
        )
    mode = row["mode_octal"]
    if (
        not isinstance(mode, str)
        or not re.fullmatch(r"[0-7]{4}", mode)
        or int(mode, 8) & 0o022
    ):
        raise ValidationNativeRuntimeIdentityError(
            "native snapshot file mode is invalid"
        )
    if row["uid"] != 0 or type(row["uid"]) is not int:
        raise ValidationNativeRuntimeIdentityError(
            "native snapshot file is not root-owned"
        )
    _require_nonnegative_int(row["gid"], name="native file gid")
    _require_positive_int(row["link_count"], name="native file link count")
    size = _require_nonnegative_int(row["size_bytes"], name="native file size")
    if size > NATIVE_RUNTIME_MAX_FILE_BYTES:
        raise ValidationNativeRuntimeIdentityError(
            "native snapshot file exceeds its byte bound"
        )
    _require_nonnegative_int(row["mtime_ns"], name="native file mtime")
    _require_nonnegative_int(row["ctime_ns"], name="native file ctime")
    _require_sha256(row["sha256"], name="native file content")
    identity_sha256 = _require_sha256(
        row["file_identity_sha256"], name="native file identity"
    )
    if not hmac.compare_digest(
        identity_sha256, _sha256(_file_identity_projection(row))
    ):
        raise ValidationNativeRuntimeIdentityError(
            "native snapshot file identity digest mismatches"
        )
    return row


def _require_mapping_row(
    value: object,
    *,
    ordinal: int,
    file_identities: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _MAPPING_ROW_FIELDS:
        raise ValidationNativeRuntimeIdentityError(
            "native snapshot mapping row schema is invalid"
        )
    row = dict(value)
    if row["ordinal"] != ordinal or type(row["ordinal"]) is not int:
        raise ValidationNativeRuntimeIdentityError(
            "native snapshot mapping row order is invalid"
        )
    _, start = _require_canonical_hex(
        row["address_start_hex"], name="native mapping start"
    )
    _, end = _require_canonical_hex(
        row["address_end_hex"], name="native mapping end", allow_zero=False
    )
    _, offset = _require_canonical_hex(
        row["file_offset_hex"], name="native mapping offset"
    )
    _, major = _require_canonical_hex(
        row["device_major_hex"], name="native mapping device major"
    )
    _, minor = _require_canonical_hex(
        row["device_minor_hex"], name="native mapping device minor"
    )
    inode = _require_nonnegative_int(row["inode"], name="native mapping inode")
    if end <= start or major > 2**32 - 1 or minor > 2**32 - 1 or inode > 2**64 - 1:
        raise ValidationNativeRuntimeIdentityError(
            "native snapshot mapping range is invalid"
        )
    permissions = row["permissions"]
    if (
        not isinstance(permissions, str)
        or re.fullmatch(r"[r-][w-]x[ps]", permissions) is None
        or permissions[1] == "w"
    ):
        raise ValidationNativeRuntimeIdentityError(
            "native snapshot contains an unsafe executable permission"
        )
    path = row["path"]
    backing_kind = row["backing_kind"]
    identity_sha256 = row["backing_file_identity_sha256"]
    if backing_kind == "kernel":
        if (
            path not in _SPECIAL_EXECUTABLE_MAPPINGS
            or major != 0
            or minor != 0
            or inode != 0
            or offset != 0
            or permissions[3] != "p"
            or identity_sha256 is not None
        ):
            raise ValidationNativeRuntimeIdentityError(
                "native snapshot kernel mapping exception is invalid"
            )
    elif backing_kind == "file":
        if not isinstance(path, str) or not path.startswith("/"):
            raise ValidationNativeRuntimeIdentityError(
                "native snapshot file mapping path is invalid"
            )
        identity_sha256 = _require_sha256(
            identity_sha256, name="native mapping backing file"
        )
        file_row = file_identities.get(identity_sha256)
        if (
            file_row is None
            or file_row["path"] != path
            or int(file_row["device_major_hex"], 16) != major
            or int(file_row["device_minor_hex"], 16) != minor
            or file_row["inode"] != inode
            or offset >= file_row["size_bytes"]
        ):
            raise ValidationNativeRuntimeIdentityError(
                "native mapping does not match its backing file evidence"
            )
    else:
        raise ValidationNativeRuntimeIdentityError(
            "native snapshot backing kind is invalid"
        )
    return row


def require_native_runtime_snapshot(value: Mapping[str, Any]) -> dict[str, Any]:
    """Require an exact, self-hashed native runtime snapshot document."""

    if not isinstance(value, Mapping) or set(value) != _SNAPSHOT_FIELDS:
        raise ValidationNativeRuntimeIdentityError(
            "native runtime snapshot schema is invalid"
        )
    observed = dict(value)
    if observed["schema_id"] != NATIVE_RUNTIME_SNAPSHOT_SCHEMA_ID:
        raise ValidationNativeRuntimeIdentityError(
            "native runtime snapshot schema identity is invalid"
        )
    _require_positive_int(observed["process_id"], name="native snapshot process id")
    mapping_count = _require_positive_int(
        observed["mapping_count"], name="native mapping count"
    )
    file_count = _require_positive_int(observed["file_count"], name="native file count")
    hashed_file_bytes = _require_nonnegative_int(
        observed["hashed_file_bytes"], name="native hashed file bytes"
    )
    if (
        mapping_count > NATIVE_RUNTIME_MAX_MAP_ROWS
        or file_count > NATIVE_RUNTIME_MAX_FILES
        or hashed_file_bytes > NATIVE_RUNTIME_MAX_TOTAL_FILE_BYTES
    ):
        raise ValidationNativeRuntimeIdentityError(
            "native snapshot count or byte bound is exceeded"
        )
    raw_file_rows = observed["file_rows"]
    raw_mapping_rows = observed["mapping_rows"]
    if (
        not isinstance(raw_file_rows, list)
        or not isinstance(raw_mapping_rows, list)
        or len(raw_file_rows) != file_count
        or len(raw_mapping_rows) != mapping_count
    ):
        raise ValidationNativeRuntimeIdentityError(
            "native snapshot row counts are inconsistent"
        )
    file_rows = [
        _require_file_row(row, ordinal=index) for index, row in enumerate(raw_file_rows)
    ]
    if file_rows != sorted(
        file_rows,
        key=lambda row: (
            row["path"],
            int(row["device_major_hex"], 16),
            int(row["device_minor_hex"], 16),
            row["inode"],
        ),
    ):
        raise ValidationNativeRuntimeIdentityError(
            "native snapshot file rows are not canonically ordered"
        )
    file_identities = {row["file_identity_sha256"]: row for row in file_rows}
    kernel_identities = {
        (
            int(row["device_major_hex"], 16),
            int(row["device_minor_hex"], 16),
            row["inode"],
        )
        for row in file_rows
    }
    if len(file_identities) != len(file_rows) or len(kernel_identities) != len(
        file_rows
    ):
        raise ValidationNativeRuntimeIdentityError(
            "native snapshot file identities are not unique"
        )
    if sum(row["size_bytes"] for row in file_rows) != hashed_file_bytes:
        raise ValidationNativeRuntimeIdentityError(
            "native snapshot hashed byte total is inconsistent"
        )
    mapping_rows = [
        _require_mapping_row(row, ordinal=index, file_identities=file_identities)
        for index, row in enumerate(raw_mapping_rows)
    ]
    previous_end = 0
    referenced_file_identities: set[str] = set()
    observed_special_mappings: set[str] = set()
    for row in mapping_rows:
        start = int(row["address_start_hex"], 16)
        if start < previous_end:
            raise ValidationNativeRuntimeIdentityError(
                "native snapshot mappings are not canonically ordered"
            )
        previous_end = int(row["address_end_hex"], 16)
        identity = row["backing_file_identity_sha256"]
        if isinstance(identity, str):
            referenced_file_identities.add(identity)
        elif row["backing_kind"] == "kernel":
            path = row["path"]
            if path in observed_special_mappings:
                raise ValidationNativeRuntimeIdentityError(
                    "native snapshot kernel mapping exception is duplicated"
                )
            observed_special_mappings.add(path)
    if referenced_file_identities != set(file_identities):
        raise ValidationNativeRuntimeIdentityError(
            "native snapshot contains unreferenced backing file evidence"
        )
    projection = {key: observed[key] for key in observed if key != "snapshot_sha256"}
    snapshot_sha256 = _require_sha256(
        observed["snapshot_sha256"], name="native snapshot"
    )
    if not hmac.compare_digest(snapshot_sha256, _sha256(projection)):
        raise ValidationNativeRuntimeIdentityError(
            "native runtime snapshot digest mismatches"
        )
    expected = {**projection, "snapshot_sha256": snapshot_sha256}
    _require_exact_document(observed, expected, name="native runtime snapshot")
    return _plain_copy(expected)


def _evidence_document(
    projection: Mapping[str, Any], *, hash_field: str
) -> dict[str, Any]:
    plain_projection = _plain_copy(dict(projection))
    return {**plain_projection, hash_field: _sha256(plain_projection)}


def build_worker_runtime_pre_evidence(
    *,
    lane: str,
    worker_request_sha256: str,
    snapshot: Mapping[str, Any] | None = None,
    deadline: float | None = None,
) -> dict[str, Any]:
    """Build the worker's pre-payload native-runtime phase evidence."""

    checked_lane = _require_lane(lane)
    checked_request = _require_sha256(worker_request_sha256, name="worker request")
    checked_snapshot = (
        measure_native_runtime_snapshot(deadline=deadline)
        if snapshot is None
        else require_native_runtime_snapshot(snapshot)
    )
    return _evidence_document(
        {
            "schema_id": WORKER_RUNTIME_PRE_EVIDENCE_SCHEMA_ID,
            "phase": "pre",
            "lane": checked_lane,
            "worker_request_sha256": checked_request,
            "snapshot": checked_snapshot,
        },
        hash_field="evidence_sha256",
    )


def require_worker_runtime_pre_evidence(
    value: Mapping[str, Any],
    *,
    expected_lane: str | None = None,
    expected_worker_request_sha256: str | None = None,
) -> dict[str, Any]:
    """Validate the exact pre phase and its embedded native snapshot."""

    fields = {
        "schema_id",
        "phase",
        "lane",
        "worker_request_sha256",
        "snapshot",
        "evidence_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != fields:
        raise ValidationNativeRuntimeIdentityError(
            "worker runtime pre evidence schema is invalid"
        )
    observed = dict(value)
    lane = _require_lane(observed["lane"])
    request_sha256 = _require_sha256(
        observed["worker_request_sha256"], name="worker request"
    )
    if (
        observed["schema_id"] != WORKER_RUNTIME_PRE_EVIDENCE_SCHEMA_ID
        or observed["phase"] != "pre"
        or (expected_lane is not None and lane != _require_lane(expected_lane))
        or (
            expected_worker_request_sha256 is not None
            and request_sha256
            != _require_sha256(
                expected_worker_request_sha256, name="expected worker request"
            )
        )
    ):
        raise ValidationNativeRuntimeIdentityError(
            "worker runtime pre evidence binding is invalid"
        )
    snapshot = require_native_runtime_snapshot(observed["snapshot"])
    projection = {
        "schema_id": WORKER_RUNTIME_PRE_EVIDENCE_SCHEMA_ID,
        "phase": "pre",
        "lane": lane,
        "worker_request_sha256": request_sha256,
        "snapshot": snapshot,
    }
    expected = _evidence_document(projection, hash_field="evidence_sha256")
    _require_sha256(observed["evidence_sha256"], name="worker runtime pre evidence")
    _require_exact_document(observed, expected, name="worker runtime pre evidence")
    return expected


def _require_materialization_manifest_wrapper(
    row: Mapping[str, Any],
) -> tuple[int, int]:
    if set(row) != {"ordinal", "case_id", "materialization_manifest"}:
        raise ValidationNativeRuntimeIdentityError(
            "materialization-manifest payload wrapper is not exact"
        )
    if row["ordinal"] != 0 or type(row["ordinal"]) is not int:
        raise ValidationNativeRuntimeIdentityError(
            "materialization-manifest payload wrapper ordinal is invalid"
        )
    if row["case_id"] != "materialization_manifest":
        raise ValidationNativeRuntimeIdentityError(
            "materialization-manifest payload wrapper identity is invalid"
        )
    raw_manifest = row["materialization_manifest"]
    if (
        not isinstance(raw_manifest, Mapping)
        or set(raw_manifest) != _MATERIALIZATION_MANIFEST_FIELDS
    ):
        raise ValidationNativeRuntimeIdentityError(
            "materialization manifest is not the exact canonical schema"
        )
    manifest = dict(raw_manifest)
    if (
        manifest["schema_id"]
        != "betelgeuze.engine_v2_reference_validation_materializer/1.0.0"
    ):
        raise ValidationNativeRuntimeIdentityError(
            "materialization manifest schema identity is invalid"
        )
    manifest_sha256 = _require_sha256(
        manifest["materialization_manifest_sha256"],
        name="materialization manifest",
    )
    manifest_projection = {
        key: manifest[key]
        for key in manifest
        if key != "materialization_manifest_sha256"
    }
    if not hmac.compare_digest(manifest_sha256, _sha256(manifest_projection)):
        raise ValidationNativeRuntimeIdentityError(
            "materialization manifest canonical digest mismatches"
        )
    coverage = manifest["coverage"]
    if (
        not isinstance(coverage, Mapping)
        or set(coverage)
        != {
            "fixture_count",
            "mutation_count",
            "case_count",
            "variant_count",
            "expected_pass_case_count",
            "expected_fail_closed_case_count",
        }
        or coverage.get("case_count") != 27
        or coverage.get("variant_count") != 59
    ):
        raise ValidationNativeRuntimeIdentityError(
            "materialization manifest coverage is not 27 cases and 59 variants"
        )
    raw_cases = manifest["cases"]
    if not isinstance(raw_cases, list) or len(raw_cases) != 27:
        raise ValidationNativeRuntimeIdentityError(
            "materialization manifest does not retain exactly 27 cases"
        )
    observed_case_ids: set[str] = set()
    nested_variant_count = 0
    for raw_case in raw_cases:
        if (
            not isinstance(raw_case, Mapping)
            or set(raw_case) != _MATERIALIZATION_CASE_FIELDS
        ):
            raise ValidationNativeRuntimeIdentityError(
                "materialization manifest case is not the exact schema"
            )
        case = dict(raw_case)
        case_id = _require_row_id(case["case_id"])
        if case_id in observed_case_ids:
            raise ValidationNativeRuntimeIdentityError(
                "materialization manifest case identities are not unique"
            )
        observed_case_ids.add(case_id)
        raw_variants = case["variants"]
        variant_count = case["variant_count"]
        if (
            type(variant_count) is not int
            or variant_count <= 0
            or not isinstance(raw_variants, list)
            or len(raw_variants) != variant_count
        ):
            raise ValidationNativeRuntimeIdentityError(
                "materialization manifest case variant coverage is invalid"
            )
        observed_variant_ids: set[str] = set()
        for raw_variant in raw_variants:
            if not isinstance(raw_variant, Mapping):
                raise ValidationNativeRuntimeIdentityError(
                    "materialization manifest variant is invalid"
                )
            variant_id = _require_row_id(raw_variant.get("variant_id"))
            if variant_id in observed_variant_ids:
                raise ValidationNativeRuntimeIdentityError(
                    "materialization manifest variant identities are not unique"
                )
            observed_variant_ids.add(variant_id)
        case_sha256 = _require_sha256(
            case["materialization_sha256"],
            name="materialization manifest case",
        )
        case_projection = {
            key: case[key] for key in case if key != "materialization_sha256"
        }
        if not hmac.compare_digest(case_sha256, _sha256(case_projection)):
            raise ValidationNativeRuntimeIdentityError(
                "materialization manifest case canonical digest mismatches"
            )
        nested_variant_count += variant_count
    if nested_variant_count != 59:
        raise ValidationNativeRuntimeIdentityError(
            "materialization manifest does not retain exactly 59 variants"
        )
    return len(raw_cases), nested_variant_count


def _payload_row_metadata(
    payload_rows: Sequence[Mapping[str, Any]],
    *,
    lane: str,
) -> list[dict[str, Any]]:
    if not isinstance(payload_rows, (list, tuple)):
        raise ValidationNativeRuntimeIdentityError(
            "worker payload rows must be a concrete ordered sequence"
        )
    if lane == WORKER_RUNTIME_LANE_ENERGY_FORCE:
        expected_count = 27
    elif lane == WORKER_RUNTIME_LANE_ENERGY_FORCE_MANIFEST:
        expected_count = 1
    else:
        expected_count = 14
    if len(payload_rows) != expected_count:
        raise ValidationNativeRuntimeIdentityError(
            "worker payload row count is not lane-complete"
        )
    metadata: list[dict[str, Any]] = []
    observed_ids: set[str] = set()
    total_bytes = 0
    total_variants = 0
    for position, raw_row in enumerate(payload_rows):
        if not isinstance(raw_row, Mapping):
            raise ValidationNativeRuntimeIdentityError(
                "worker payload row is not a mapping"
            )
        row = dict(raw_row)
        encoded = _canonical_bytes(row)
        total_bytes += len(encoded)
        if (
            len(encoded) > WORKER_RUNTIME_MAX_PAYLOAD_ROW_BYTES
            or total_bytes > WORKER_RUNTIME_MAX_PAYLOAD_BYTES
        ):
            raise ValidationNativeRuntimeIdentityError(
                "worker payload rows exceed their byte bound"
            )
        row_id = _require_row_id(row.get("case_id"))
        if row_id in observed_ids:
            raise ValidationNativeRuntimeIdentityError(
                "worker payload row identities are not unique"
            )
        observed_ids.add(row_id)
        expected_ordinal = (
            position
            if lane
            in {
                WORKER_RUNTIME_LANE_ENERGY_FORCE,
                WORKER_RUNTIME_LANE_ENERGY_FORCE_MANIFEST,
            }
            else position + 1
        )
        if type(row.get("ordinal")) is not int or row["ordinal"] != expected_ordinal:
            raise ValidationNativeRuntimeIdentityError(
                "worker payload row ordinal or order is invalid"
            )
        nested_case_count: int | None
        nested_variant_count: int | None
        if lane == WORKER_RUNTIME_LANE_ENERGY_FORCE:
            variants = row.get("variant_results")
            if not isinstance(variants, list) or not variants:
                raise ValidationNativeRuntimeIdentityError(
                    "energy-force payload row lacks nested variants"
                )
            nested_variant_count = len(variants)
            total_variants += nested_variant_count
            nested_case_count = None
        elif lane == WORKER_RUNTIME_LANE_ENERGY_FORCE_MANIFEST:
            nested_case_count, nested_variant_count = (
                _require_materialization_manifest_wrapper(row)
            )
            total_variants += nested_variant_count
        else:
            if "variant_results" in row:
                raise ValidationNativeRuntimeIdentityError(
                    "minimization payload row unexpectedly has variants"
                )
            nested_variant_count = None
            nested_case_count = None
        metadata.append(
            {
                "position": position,
                "row_ordinal": expected_ordinal,
                "row_id": row_id,
                "row_sha256": hashlib.sha256(encoded).hexdigest(),
                "nested_case_count": nested_case_count,
                "nested_variant_count": nested_variant_count,
            }
        )
    if (
        lane
        in {
            WORKER_RUNTIME_LANE_ENERGY_FORCE,
            WORKER_RUNTIME_LANE_ENERGY_FORCE_MANIFEST,
        }
        and total_variants != 59
    ):
        raise ValidationNativeRuntimeIdentityError(
            "energy-force payload does not retain exactly 59 variants"
        )
    return metadata


def build_worker_runtime_payload_evidence(
    *,
    lane: str,
    worker_request_sha256: str,
    pre_evidence: Mapping[str, Any],
    payload_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Bind exact ordered worker payload row identities and canonical digests."""

    checked_lane = _require_lane(lane)
    checked_request = _require_sha256(worker_request_sha256, name="worker request")
    checked_pre = require_worker_runtime_pre_evidence(
        pre_evidence,
        expected_lane=checked_lane,
        expected_worker_request_sha256=checked_request,
    )
    row_metadata = _payload_row_metadata(payload_rows, lane=checked_lane)
    aggregate_projection = {
        "lane": checked_lane,
        "worker_request_sha256": checked_request,
        "pre_evidence_sha256": checked_pre["evidence_sha256"],
        "payload_rows": row_metadata,
    }
    projection = {
        "schema_id": WORKER_RUNTIME_PAYLOAD_EVIDENCE_SCHEMA_ID,
        "lane": checked_lane,
        "worker_request_sha256": checked_request,
        "pre_evidence_sha256": checked_pre["evidence_sha256"],
        "payload_row_count": len(row_metadata),
        "payload_rows": row_metadata,
        "payload_aggregate_sha256": _sha256(aggregate_projection),
    }
    return _evidence_document(projection, hash_field="evidence_sha256")


def require_worker_runtime_payload_evidence(
    value: Mapping[str, Any],
    *,
    expected_lane: str,
    expected_worker_request_sha256: str,
    expected_pre_evidence_sha256: str,
    expected_payload_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Validate payload evidence against the supervisor-retained exact rows."""

    fields = {
        "schema_id",
        "lane",
        "worker_request_sha256",
        "pre_evidence_sha256",
        "payload_row_count",
        "payload_rows",
        "payload_aggregate_sha256",
        "evidence_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != fields:
        raise ValidationNativeRuntimeIdentityError(
            "worker runtime payload evidence schema is invalid"
        )
    observed = dict(value)
    lane = _require_lane(expected_lane)
    request_sha256 = _require_sha256(
        expected_worker_request_sha256, name="expected worker request"
    )
    pre_sha256 = _require_sha256(
        expected_pre_evidence_sha256, name="expected worker pre evidence"
    )
    expected_rows = _payload_row_metadata(expected_payload_rows, lane=lane)
    aggregate_projection = {
        "lane": lane,
        "worker_request_sha256": request_sha256,
        "pre_evidence_sha256": pre_sha256,
        "payload_rows": expected_rows,
    }
    projection = {
        "schema_id": WORKER_RUNTIME_PAYLOAD_EVIDENCE_SCHEMA_ID,
        "lane": lane,
        "worker_request_sha256": request_sha256,
        "pre_evidence_sha256": pre_sha256,
        "payload_row_count": len(expected_rows),
        "payload_rows": expected_rows,
        "payload_aggregate_sha256": _sha256(aggregate_projection),
    }
    expected = _evidence_document(projection, hash_field="evidence_sha256")
    _require_sha256(
        observed["payload_aggregate_sha256"], name="worker payload aggregate"
    )
    _require_sha256(observed["evidence_sha256"], name="worker payload evidence")
    _require_exact_document(observed, expected, name="worker runtime payload evidence")
    return expected


def build_worker_runtime_post_evidence(
    *,
    lane: str,
    worker_request_sha256: str,
    pre_evidence: Mapping[str, Any],
    payload_evidence: Mapping[str, Any],
    payload_rows: Sequence[Mapping[str, Any]],
    snapshot: Mapping[str, Any] | None = None,
    deadline: float | None = None,
) -> dict[str, Any]:
    """Build the post phase and require pre/post executable-set equality."""

    checked_lane = _require_lane(lane)
    checked_request = _require_sha256(worker_request_sha256, name="worker request")
    checked_pre = require_worker_runtime_pre_evidence(
        pre_evidence,
        expected_lane=checked_lane,
        expected_worker_request_sha256=checked_request,
    )
    checked_payload = require_worker_runtime_payload_evidence(
        payload_evidence,
        expected_lane=checked_lane,
        expected_worker_request_sha256=checked_request,
        expected_pre_evidence_sha256=checked_pre["evidence_sha256"],
        expected_payload_rows=payload_rows,
    )
    checked_snapshot = (
        measure_native_runtime_snapshot(deadline=deadline)
        if snapshot is None
        else require_native_runtime_snapshot(snapshot)
    )
    if checked_snapshot != checked_pre["snapshot"]:
        raise ValidationNativeRuntimeIdentityError(
            "worker pre/post executable mapping sets differ"
        )
    return _evidence_document(
        {
            "schema_id": WORKER_RUNTIME_POST_EVIDENCE_SCHEMA_ID,
            "phase": "post",
            "lane": checked_lane,
            "worker_request_sha256": checked_request,
            "pre_evidence_sha256": checked_pre["evidence_sha256"],
            "payload_evidence_sha256": checked_payload["evidence_sha256"],
            "payload_aggregate_sha256": checked_payload["payload_aggregate_sha256"],
            "snapshot": checked_snapshot,
        },
        hash_field="evidence_sha256",
    )


def require_worker_runtime_post_evidence(
    value: Mapping[str, Any],
    *,
    expected_lane: str,
    expected_worker_request_sha256: str,
    expected_pre_evidence: Mapping[str, Any],
    expected_payload_evidence: Mapping[str, Any],
    expected_payload_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Validate the exact post phase and pre/payload/native closure links."""

    fields = {
        "schema_id",
        "phase",
        "lane",
        "worker_request_sha256",
        "pre_evidence_sha256",
        "payload_evidence_sha256",
        "payload_aggregate_sha256",
        "snapshot",
        "evidence_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != fields:
        raise ValidationNativeRuntimeIdentityError(
            "worker runtime post evidence schema is invalid"
        )
    observed = dict(value)
    lane = _require_lane(expected_lane)
    request_sha256 = _require_sha256(
        expected_worker_request_sha256, name="expected worker request"
    )
    pre = require_worker_runtime_pre_evidence(
        expected_pre_evidence,
        expected_lane=lane,
        expected_worker_request_sha256=request_sha256,
    )
    payload = require_worker_runtime_payload_evidence(
        expected_payload_evidence,
        expected_lane=lane,
        expected_worker_request_sha256=request_sha256,
        expected_pre_evidence_sha256=pre["evidence_sha256"],
        expected_payload_rows=expected_payload_rows,
    )
    snapshot = require_native_runtime_snapshot(observed["snapshot"])
    if snapshot != pre["snapshot"]:
        raise ValidationNativeRuntimeIdentityError(
            "worker pre/post executable mapping sets differ"
        )
    projection = {
        "schema_id": WORKER_RUNTIME_POST_EVIDENCE_SCHEMA_ID,
        "phase": "post",
        "lane": lane,
        "worker_request_sha256": request_sha256,
        "pre_evidence_sha256": pre["evidence_sha256"],
        "payload_evidence_sha256": payload["evidence_sha256"],
        "payload_aggregate_sha256": payload["payload_aggregate_sha256"],
        "snapshot": snapshot,
    }
    expected = _evidence_document(projection, hash_field="evidence_sha256")
    _require_sha256(observed["evidence_sha256"], name="worker runtime post evidence")
    _require_exact_document(observed, expected, name="worker runtime post evidence")
    return expected


def build_complete_worker_runtime_lifecycle_evidence(
    *,
    lane: str,
    worker_request_sha256: str,
    pre_evidence: Mapping[str, Any],
    payload_rows: Sequence[Mapping[str, Any]],
    post_snapshot: Mapping[str, Any] | None = None,
    deadline: float | None = None,
) -> dict[str, Any]:
    """Build a complete pre -> payload -> post lifecycle document."""

    checked_lane = _require_lane(lane)
    checked_request = _require_sha256(worker_request_sha256, name="worker request")
    checked_pre = require_worker_runtime_pre_evidence(
        pre_evidence,
        expected_lane=checked_lane,
        expected_worker_request_sha256=checked_request,
    )
    payload = build_worker_runtime_payload_evidence(
        lane=checked_lane,
        worker_request_sha256=checked_request,
        pre_evidence=checked_pre,
        payload_rows=payload_rows,
    )
    post = build_worker_runtime_post_evidence(
        lane=checked_lane,
        worker_request_sha256=checked_request,
        pre_evidence=checked_pre,
        payload_evidence=payload,
        payload_rows=payload_rows,
        snapshot=post_snapshot,
        deadline=deadline,
    )
    return _evidence_document(
        {
            "schema_id": WORKER_RUNTIME_LIFECYCLE_EVIDENCE_SCHEMA_ID,
            "completion_state": "complete",
            "failure_code": None,
            "lane": checked_lane,
            "worker_request_sha256": checked_request,
            "pre": checked_pre,
            "payload": payload,
            "post": post,
            "payload_aggregate_sha256": payload["payload_aggregate_sha256"],
        },
        hash_field="lifecycle_sha256",
    )


def build_incomplete_worker_runtime_lifecycle_evidence(
    *,
    lane: str,
    worker_request_sha256: str,
    failure_code: str,
    pre_evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build fail-closed evidence with no accepted payload or post phase."""

    checked_lane = _require_lane(lane)
    checked_request = _require_sha256(worker_request_sha256, name="worker request")
    if (
        not isinstance(failure_code, str)
        or not failure_code
        or len(failure_code) > 256
        or re.fullmatch(r"[a-z0-9_]+", failure_code) is None
    ):
        raise ValidationNativeRuntimeIdentityError(
            "worker lifecycle failure code is invalid"
        )
    checked_pre = (
        None
        if pre_evidence is None
        else require_worker_runtime_pre_evidence(
            pre_evidence,
            expected_lane=checked_lane,
            expected_worker_request_sha256=checked_request,
        )
    )
    return _evidence_document(
        {
            "schema_id": WORKER_RUNTIME_LIFECYCLE_EVIDENCE_SCHEMA_ID,
            "completion_state": "incomplete",
            "failure_code": failure_code,
            "lane": checked_lane,
            "worker_request_sha256": checked_request,
            "pre": checked_pre,
            "payload": None,
            "post": None,
            "payload_aggregate_sha256": None,
        },
        hash_field="lifecycle_sha256",
    )


def require_worker_runtime_lifecycle_evidence(
    value: Mapping[str, Any],
    *,
    expected_lane: str,
    expected_worker_request_sha256: str,
    expected_payload_rows: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    """Validate complete or fail-closed lifecycle evidence exactly.

    Complete evidence always requires the supervisor-retained payload rows.  A
    self-consistent worker claim is never accepted as proof of row identity.
    """

    fields = {
        "schema_id",
        "completion_state",
        "failure_code",
        "lane",
        "worker_request_sha256",
        "pre",
        "payload",
        "post",
        "payload_aggregate_sha256",
        "lifecycle_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != fields:
        raise ValidationNativeRuntimeIdentityError(
            "worker runtime lifecycle evidence schema is invalid"
        )
    observed = dict(value)
    lane = _require_lane(expected_lane)
    request_sha256 = _require_sha256(
        expected_worker_request_sha256, name="expected worker request"
    )
    if (
        observed["schema_id"] != WORKER_RUNTIME_LIFECYCLE_EVIDENCE_SCHEMA_ID
        or observed["lane"] != lane
        or observed["worker_request_sha256"] != request_sha256
    ):
        raise ValidationNativeRuntimeIdentityError(
            "worker runtime lifecycle binding is invalid"
        )
    state = observed["completion_state"]
    if state == "incomplete":
        if (
            expected_payload_rows is not None
            or observed["payload"] is not None
            or observed["post"] is not None
            or observed["payload_aggregate_sha256"] is not None
            or not isinstance(observed["failure_code"], str)
        ):
            raise ValidationNativeRuntimeIdentityError(
                "incomplete worker lifecycle retained payload or post evidence"
            )
        expected = build_incomplete_worker_runtime_lifecycle_evidence(
            lane=lane,
            worker_request_sha256=request_sha256,
            failure_code=observed["failure_code"],
            pre_evidence=observed["pre"],
        )
    elif state == "complete":
        if expected_payload_rows is None or observed["failure_code"] is not None:
            raise ValidationNativeRuntimeIdentityError(
                "complete worker lifecycle lacks supervisor-retained payload rows"
            )
        pre = require_worker_runtime_pre_evidence(
            observed["pre"],
            expected_lane=lane,
            expected_worker_request_sha256=request_sha256,
        )
        payload = require_worker_runtime_payload_evidence(
            observed["payload"],
            expected_lane=lane,
            expected_worker_request_sha256=request_sha256,
            expected_pre_evidence_sha256=pre["evidence_sha256"],
            expected_payload_rows=expected_payload_rows,
        )
        post = require_worker_runtime_post_evidence(
            observed["post"],
            expected_lane=lane,
            expected_worker_request_sha256=request_sha256,
            expected_pre_evidence=pre,
            expected_payload_evidence=payload,
            expected_payload_rows=expected_payload_rows,
        )
        projection = {
            "schema_id": WORKER_RUNTIME_LIFECYCLE_EVIDENCE_SCHEMA_ID,
            "completion_state": "complete",
            "failure_code": None,
            "lane": lane,
            "worker_request_sha256": request_sha256,
            "pre": pre,
            "payload": payload,
            "post": post,
            "payload_aggregate_sha256": payload["payload_aggregate_sha256"],
        }
        expected = _evidence_document(projection, hash_field="lifecycle_sha256")
    else:
        raise ValidationNativeRuntimeIdentityError(
            "worker runtime lifecycle completion state is invalid"
        )
    _require_sha256(observed["lifecycle_sha256"], name="worker lifecycle")
    _require_exact_document(
        observed, expected, name="worker runtime lifecycle evidence"
    )
    return expected


__all__ = [
    "NATIVE_RUNTIME_MAX_FILE_BYTES",
    "NATIVE_RUNTIME_MAX_FILES",
    "NATIVE_RUNTIME_MAX_MAPS_BYTES",
    "NATIVE_RUNTIME_MAX_MAP_ROWS",
    "NATIVE_RUNTIME_MAX_PATH_BYTES",
    "NATIVE_RUNTIME_MAX_TOTAL_FILE_BYTES",
    "NATIVE_RUNTIME_MAX_WALL_SECONDS",
    "NATIVE_RUNTIME_SNAPSHOT_SCHEMA_ID",
    "ValidationNativeRuntimeIdentityError",
    "WORKER_RUNTIME_LANE_ENERGY_FORCE",
    "WORKER_RUNTIME_LANE_ENERGY_FORCE_MANIFEST",
    "WORKER_RUNTIME_LANE_MINIMIZATION",
    "WORKER_RUNTIME_LANES",
    "WORKER_RUNTIME_LIFECYCLE_EVIDENCE_SCHEMA_ID",
    "WORKER_RUNTIME_PAYLOAD_EVIDENCE_SCHEMA_ID",
    "WORKER_RUNTIME_POST_EVIDENCE_SCHEMA_ID",
    "WORKER_RUNTIME_PRE_EVIDENCE_SCHEMA_ID",
    "build_complete_worker_runtime_lifecycle_evidence",
    "build_incomplete_worker_runtime_lifecycle_evidence",
    "build_worker_runtime_payload_evidence",
    "build_worker_runtime_post_evidence",
    "build_worker_runtime_pre_evidence",
    "communicate_bounded_worker_process",
    "measure_native_runtime_snapshot",
    "require_complete_worker_runtime_process_id",
    "require_native_runtime_snapshot",
    "require_worker_runtime_lifecycle_evidence",
    "require_worker_runtime_payload_evidence",
    "require_worker_runtime_post_evidence",
    "require_worker_runtime_pre_evidence",
]
