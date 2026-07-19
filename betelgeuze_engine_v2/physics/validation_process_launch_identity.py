"""Fail-closed Linux process launch identity evidence.

The public measurement API is deliberately fixed to the calling host's
``/proc`` tree.  It binds a numeric process id to its parent, Linux start-time
clock tick, PID namespace inode, and boot id.  The tuple is a best-effort
same-boot discriminator: clock-tick resolution cannot exclude a PID reuse
collision within one tick, and it is not external host authentication,
durable process uniqueness, or launch custody.

There is no import-time measurement and no filesystem mutation.  A private
proc-root hook exists solely so focused tests can exercise malformed and
racing proc views; documents made from any root other than ``/proc`` are
rejected by the public document validator.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import sys
from typing import Any, Mapping


PROCESS_LAUNCH_IDENTITY_SCHEMA_ID = (
    "betelgeuze.engine_v2_linux_process_launch_identity/1.0.0"
)
PROCESS_LAUNCH_IDENTITY_CONTRACT_SCHEMA_ID = (
    "betelgeuze.engine_v2_linux_process_launch_identity_contract/1.0.0"
)
PROCESS_LAUNCH_IDENTITY_CONTRACT_ID = "engine_v2_linux_process_launch_identity/1.0.0"
PROCESS_LAUNCH_IDENTITY_CONTRACT_VERSION = "1.0.0"
PROCESS_LAUNCH_IDENTITY_CONTRACT_FROZEN_AT_UTC = "2026-07-19T02:00:00Z"
FROZEN_PROCESS_LAUNCH_IDENTITY_CONTRACT_SHA256 = (
    "934b62f063e1e2133b80794df528a4227033e11679d266df8c6feee2b306f43a"
)

PROCESS_LAUNCH_PROC_ROOT = "/proc"
PROCESS_LAUNCH_BOOT_ID_RELATIVE_PATH = "sys/kernel/random/boot_id"
PROCESS_LAUNCH_MAX_BOOT_ID_BYTES = 64
PROCESS_LAUNCH_MAX_STAT_BYTES = 4_096
PROCESS_LAUNCH_MAX_NAMESPACE_TARGET_BYTES = 128
PROCESS_LAUNCH_READ_CHUNK_BYTES = 512
PROCESS_LAUNCH_MAX_PID = (1 << 31) - 1
PROCESS_LAUNCH_MAX_CLOCK_TICKS = (1 << 64) - 1
PROCESS_LAUNCH_MAX_NAMESPACE_INODE = (1 << 64) - 1

_BOOT_ID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
_PID_NAMESPACE_TARGET_PATTERN = re.compile(r"^pid:\[([1-9][0-9]*)\]$")
_LOWER_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_DOCUMENT_FIELDS = frozenset(
    {
        "schema_id",
        "contract_sha256",
        "proc_root",
        "boot_id",
        "boot_id_sha256",
        "pid",
        "parent_pid",
        "start_time_clock_ticks",
        "pid_namespace_inode",
        "process_launch_identity_sha256",
    }
)
_BLOCKERS = (
    "procfs_superblock_identity_not_authenticated",
    "external_host_identity_not_authenticated",
    "same_tick_pid_reuse_collision_not_excluded",
    "external_launch_nonce_not_bound",
    "external_worker_launch_custody_not_established",
    "external_signed_runtime_manifest_not_bound",
    "two_production_cpu_hosts_missing",
)


class ValidationProcessLaunchIdentityError(RuntimeError):
    """A process launch identity or its frozen contract is unsafe or invalid."""


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
        raise ValidationProcessLaunchIdentityError(
            "process launch identity is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_lower_sha256(value: object, *, name: str) -> str:
    if not isinstance(value, str) or _LOWER_SHA256_PATTERN.fullmatch(value) is None:
        raise ValidationProcessLaunchIdentityError(
            f"{name} must be a lowercase SHA-256"
        )
    return value


def _require_bounded_positive_integer(
    value: object,
    *,
    name: str,
    maximum: int,
) -> int:
    if type(value) is not int or value <= 0 or value > maximum:
        raise ValidationProcessLaunchIdentityError(
            f"{name} must be a positive integer no greater than {maximum}"
        )
    return value


def _require_bounded_nonnegative_integer(
    value: object,
    *,
    name: str,
    maximum: int,
) -> int:
    if type(value) is not int or value < 0 or value > maximum:
        raise ValidationProcessLaunchIdentityError(
            f"{name} must be a nonnegative integer no greater than {maximum}"
        )
    return value


def _require_canonical_decimal(
    value: bytes,
    *,
    name: str,
    maximum: int,
) -> int:
    if (
        not value
        or any(character < 48 or character > 57 for character in value)
        or (len(value) > 1 and value.startswith(b"0"))
    ):
        raise ValidationProcessLaunchIdentityError(
            f"{name} is not a canonical positive decimal integer"
        )
    observed = int(value)
    return _require_bounded_positive_integer(
        observed,
        name=name,
        maximum=maximum,
    )


def _require_canonical_nonnegative_decimal(
    value: bytes,
    *,
    name: str,
    maximum: int,
) -> int:
    if (
        not value
        or any(character < 48 or character > 57 for character in value)
        or (len(value) > 1 and value.startswith(b"0"))
    ):
        raise ValidationProcessLaunchIdentityError(
            f"{name} is not a canonical nonnegative decimal integer"
        )
    return _require_bounded_nonnegative_integer(
        int(value),
        name=name,
        maximum=maximum,
    )


def _require_boot_id(value: object) -> str:
    if not isinstance(value, str) or _BOOT_ID_PATTERN.fullmatch(value) is None:
        raise ValidationProcessLaunchIdentityError(
            "boot id must be an exact lowercase UUID"
        )
    return value


def _stable_stat_identity(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_uid,
        value.st_gid,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _secure_directory_flags() -> int:
    nofollow = getattr(os, "O_NOFOLLOW", None)
    cloexec = getattr(os, "O_CLOEXEC", None)
    directory = getattr(os, "O_DIRECTORY", None)
    if nofollow is None or cloexec is None or directory is None:
        raise ValidationProcessLaunchIdentityError(
            "required Linux O_NOFOLLOW/O_CLOEXEC directory flags are unavailable"
        )
    return os.O_RDONLY | nofollow | cloexec | directory


def _secure_file_flags() -> int:
    nofollow = getattr(os, "O_NOFOLLOW", None)
    cloexec = getattr(os, "O_CLOEXEC", None)
    if nofollow is None or cloexec is None:
        raise ValidationProcessLaunchIdentityError(
            "required Linux O_NOFOLLOW/O_CLOEXEC file flags are unavailable"
        )
    return os.O_RDONLY | nofollow | cloexec


def _require_directory_stat(value: os.stat_result, *, name: str) -> None:
    if not stat.S_ISDIR(value.st_mode) or value.st_nlink <= 0:
        raise ValidationProcessLaunchIdentityError(f"{name} is not a directory")


def _open_directory_component(parent_fd: int, name: str) -> int:
    if (
        not isinstance(name, str)
        or not name
        or name in {".", ".."}
        or "/" in name
        or "\x00" in name
    ):
        raise ValidationProcessLaunchIdentityError(
            "proc directory component is not canonical"
        )
    try:
        before = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        descriptor = os.open(name, _secure_directory_flags(), dir_fd=parent_fd)
        opened = os.fstat(descriptor)
    except OSError as exc:
        raise ValidationProcessLaunchIdentityError(
            "proc directory cannot be opened with O_NOFOLLOW/O_CLOEXEC"
        ) from exc
    if _stable_stat_identity(before) != _stable_stat_identity(opened):
        os.close(descriptor)
        raise ValidationProcessLaunchIdentityError(
            "proc directory identity changed while opened"
        )
    try:
        _require_directory_stat(opened, name="proc directory component")
    except Exception:
        os.close(descriptor)
        raise
    return descriptor


def _open_absolute_directory_no_follow(path: str) -> int:
    if (
        not isinstance(path, str)
        or not path.startswith("/")
        or path.startswith("//")
        or os.path.normpath(path) != path
    ):
        raise ValidationProcessLaunchIdentityError(
            "proc root must be a canonical absolute path"
        )
    components = [] if path == "/" else path.split("/")[1:]
    if any(not component or component in {".", ".."} for component in components):
        raise ValidationProcessLaunchIdentityError("proc root path is ambiguous")
    try:
        descriptor = os.open("/", _secure_directory_flags())
        _require_directory_stat(os.fstat(descriptor), name="filesystem root")
    except OSError as exc:
        raise ValidationProcessLaunchIdentityError(
            "filesystem root cannot be opened securely"
        ) from exc
    try:
        for component in components:
            next_descriptor = _open_directory_component(descriptor, component)
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def _read_bounded_regular_file_at(
    parent_fd: int,
    name: str,
    *,
    maximum_bytes: int,
    label: str,
) -> bytes:
    if type(maximum_bytes) is not int or maximum_bytes <= 0:
        raise ValidationProcessLaunchIdentityError(f"{label} byte bound is invalid")
    try:
        before = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        descriptor = os.open(name, _secure_file_flags(), dir_fd=parent_fd)
        opened = os.fstat(descriptor)
    except OSError as exc:
        raise ValidationProcessLaunchIdentityError(
            f"{label} cannot be opened with O_NOFOLLOW/O_CLOEXEC"
        ) from exc
    try:
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink <= 0
            or _stable_stat_identity(before) != _stable_stat_identity(opened)
        ):
            raise ValidationProcessLaunchIdentityError(
                f"{label} identity is unsafe or changed while opened"
            )
        chunks: list[bytes] = []
        observed = 0
        while True:
            try:
                chunk = os.read(
                    descriptor,
                    min(
                        PROCESS_LAUNCH_READ_CHUNK_BYTES,
                        maximum_bytes + 1 - observed,
                    ),
                )
            except OSError as exc:
                raise ValidationProcessLaunchIdentityError(
                    f"{label} cannot be read"
                ) from exc
            if not chunk:
                break
            observed += len(chunk)
            if observed > maximum_bytes:
                raise ValidationProcessLaunchIdentityError(
                    f"{label} exceeds its byte bound"
                )
            chunks.append(chunk)
        after = os.fstat(descriptor)
        if _stable_stat_identity(opened) != _stable_stat_identity(after):
            raise ValidationProcessLaunchIdentityError(
                f"{label} identity changed while read"
            )
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _read_boot_id(proc_root_fd: int) -> str:
    descriptors: list[int] = []
    current = proc_root_fd
    try:
        for component in ("sys", "kernel", "random"):
            current = _open_directory_component(current, component)
            descriptors.append(current)
        raw = _read_bounded_regular_file_at(
            current,
            "boot_id",
            maximum_bytes=PROCESS_LAUNCH_MAX_BOOT_ID_BYTES,
            label="boot id",
        )
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
    if not raw.endswith(b"\n") or raw.count(b"\n") != 1 or b"\x00" in raw:
        raise ValidationProcessLaunchIdentityError("boot id framing is invalid")
    try:
        value = raw[:-1].decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValidationProcessLaunchIdentityError("boot id is not ASCII") from exc
    return _require_boot_id(value)


def _parse_process_stat(raw: bytes, *, expected_pid: int) -> dict[str, int]:
    pid = _require_bounded_positive_integer(
        expected_pid,
        name="expected process id",
        maximum=PROCESS_LAUNCH_MAX_PID,
    )
    if (
        not isinstance(raw, bytes)
        or not raw
        or len(raw) > PROCESS_LAUNCH_MAX_STAT_BYTES
        or not raw.endswith(b"\n")
        or raw.count(b"\n") != 1
        or b"\r" in raw
        or b"\x00" in raw
    ):
        raise ValidationProcessLaunchIdentityError("process stat framing is invalid")
    body = raw[:-1]
    first_space = body.find(b" ")
    close = body.rfind(b") ")
    if (
        first_space <= 0
        or body[first_space + 1 : first_space + 2] != b"("
        or close <= first_space + 1
    ):
        raise ValidationProcessLaunchIdentityError(
            "process stat command boundary is invalid"
        )
    observed_pid = _require_canonical_decimal(
        body[:first_space],
        name="process stat pid",
        maximum=PROCESS_LAUNCH_MAX_PID,
    )
    if observed_pid != pid:
        raise ValidationProcessLaunchIdentityError(
            "process stat pid does not match the requested process"
        )
    command = body[first_space + 2 : close]
    if not command or len(command) > 255:
        raise ValidationProcessLaunchIdentityError(
            "process stat command field is invalid"
        )
    tail = body[close + 2 :].split(b" ")
    if len(tail) < 20 or any(not field for field in tail):
        raise ValidationProcessLaunchIdentityError(
            "process stat field count or spacing is invalid"
        )
    if len(tail[0]) != 1 or not (65 <= tail[0][0] <= 90 or 97 <= tail[0][0] <= 122):
        raise ValidationProcessLaunchIdentityError("process stat state is invalid")
    parent_pid = _require_canonical_nonnegative_decimal(
        tail[1],
        name="process stat parent pid",
        maximum=PROCESS_LAUNCH_MAX_PID,
    )
    start_time = _require_canonical_decimal(
        tail[19],
        name="process stat start time clock ticks",
        maximum=PROCESS_LAUNCH_MAX_CLOCK_TICKS,
    )
    return {
        "pid": observed_pid,
        "parent_pid": parent_pid,
        "start_time_clock_ticks": start_time,
    }


def _read_process_stat(pid_directory_fd: int, *, expected_pid: int) -> dict[str, int]:
    return _parse_process_stat(
        _read_bounded_regular_file_at(
            pid_directory_fd,
            "stat",
            maximum_bytes=PROCESS_LAUNCH_MAX_STAT_BYTES,
            label="process stat",
        ),
        expected_pid=expected_pid,
    )


def _read_pid_namespace_inode(pid_directory_fd: int) -> int:
    namespace_fd = _open_directory_component(pid_directory_fd, "ns")
    try:
        try:
            before = os.stat("pid", dir_fd=namespace_fd, follow_symlinks=False)
            target = os.readlink("pid", dir_fd=namespace_fd)
            after = os.stat("pid", dir_fd=namespace_fd, follow_symlinks=False)
        except OSError as exc:
            raise ValidationProcessLaunchIdentityError(
                "PID namespace link cannot be read safely"
            ) from exc
    finally:
        os.close(namespace_fd)
    if not stat.S_ISLNK(before.st_mode) or _stable_stat_identity(
        before
    ) != _stable_stat_identity(after):
        raise ValidationProcessLaunchIdentityError(
            "PID namespace link identity is unsafe or changed while read"
        )
    try:
        target_bytes = target.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValidationProcessLaunchIdentityError(
            "PID namespace link target is not ASCII"
        ) from exc
    if len(target_bytes) > PROCESS_LAUNCH_MAX_NAMESPACE_TARGET_BYTES:
        raise ValidationProcessLaunchIdentityError(
            "PID namespace link target exceeds its byte bound"
        )
    match = _PID_NAMESPACE_TARGET_PATTERN.fullmatch(target)
    if match is None:
        raise ValidationProcessLaunchIdentityError(
            "PID namespace link target is not canonical"
        )
    return _require_bounded_positive_integer(
        int(match.group(1)),
        name="PID namespace inode",
        maximum=PROCESS_LAUNCH_MAX_NAMESPACE_INODE,
    )


def _build_identity_document(
    *,
    proc_root: str,
    boot_id: str,
    process_row: Mapping[str, int],
    pid_namespace_inode: int,
) -> dict[str, Any]:
    canonical_boot_id = _require_boot_id(boot_id)
    projection: dict[str, Any] = {
        "schema_id": PROCESS_LAUNCH_IDENTITY_SCHEMA_ID,
        "contract_sha256": FROZEN_PROCESS_LAUNCH_IDENTITY_CONTRACT_SHA256,
        "proc_root": proc_root,
        "boot_id": canonical_boot_id,
        "boot_id_sha256": hashlib.sha256(canonical_boot_id.encode("ascii")).hexdigest(),
        "pid": _require_bounded_positive_integer(
            process_row.get("pid"),
            name="process id",
            maximum=PROCESS_LAUNCH_MAX_PID,
        ),
        "parent_pid": _require_bounded_nonnegative_integer(
            process_row.get("parent_pid"),
            name="parent process id",
            maximum=PROCESS_LAUNCH_MAX_PID,
        ),
        "start_time_clock_ticks": _require_bounded_positive_integer(
            process_row.get("start_time_clock_ticks"),
            name="process start time clock ticks",
            maximum=PROCESS_LAUNCH_MAX_CLOCK_TICKS,
        ),
        "pid_namespace_inode": _require_bounded_positive_integer(
            pid_namespace_inode,
            name="PID namespace inode",
            maximum=PROCESS_LAUNCH_MAX_NAMESPACE_INODE,
        ),
    }
    return {
        **projection,
        "process_launch_identity_sha256": _sha256(projection),
    }


def _measure_process_launch_identity_at_proc_root(
    pid: int,
    *,
    proc_root: str,
) -> dict[str, Any]:
    """Private test hook; public validation rejects non-``/proc`` documents."""

    checked_pid = _require_bounded_positive_integer(
        pid,
        name="process id",
        maximum=PROCESS_LAUNCH_MAX_PID,
    )
    proc_root_fd = _open_absolute_directory_no_follow(proc_root)
    try:
        proc_before = os.fstat(proc_root_fd)
        boot_before = _read_boot_id(proc_root_fd)
        pid_directory_fd = _open_directory_component(proc_root_fd, str(checked_pid))
        try:
            pid_before = os.fstat(pid_directory_fd)
            first_process = _read_process_stat(
                pid_directory_fd,
                expected_pid=checked_pid,
            )
            first_namespace = _read_pid_namespace_inode(pid_directory_fd)
            second_process = _read_process_stat(
                pid_directory_fd,
                expected_pid=checked_pid,
            )
            second_namespace = _read_pid_namespace_inode(pid_directory_fd)
            pid_after = os.fstat(pid_directory_fd)
        finally:
            os.close(pid_directory_fd)
        boot_after = _read_boot_id(proc_root_fd)
        proc_after = os.fstat(proc_root_fd)
    finally:
        os.close(proc_root_fd)
    if _stable_stat_identity(proc_before) != _stable_stat_identity(proc_after):
        raise ValidationProcessLaunchIdentityError(
            "proc root identity changed while measured"
        )
    if _stable_stat_identity(pid_before) != _stable_stat_identity(pid_after):
        raise ValidationProcessLaunchIdentityError(
            "process directory identity changed while measured"
        )
    if first_process != second_process:
        raise ValidationProcessLaunchIdentityError(
            "process pid/parent/start-time tuple changed while measured"
        )
    if first_namespace != second_namespace:
        raise ValidationProcessLaunchIdentityError(
            "PID namespace identity changed while measured"
        )
    if boot_before != boot_after:
        raise ValidationProcessLaunchIdentityError(
            "boot id changed while process identity was measured"
        )
    return _build_identity_document(
        proc_root=proc_root,
        boot_id=boot_before,
        process_row=first_process,
        pid_namespace_inode=first_namespace,
    )


def measure_process_launch_identity(pid: int | None = None) -> dict[str, Any]:
    """Measure one numeric PID from the fixed Linux ``/proc`` view."""

    if not sys.platform.startswith("linux"):
        raise ValidationProcessLaunchIdentityError(
            "process launch identity measurement is Linux-only"
        )
    if PROCESS_LAUNCH_PROC_ROOT != "/proc":
        raise ValidationProcessLaunchIdentityError(
            "public process launch identity proc root is not fixed"
        )
    checked_pid = os.getpid() if pid is None else pid
    document = _measure_process_launch_identity_at_proc_root(
        checked_pid,
        proc_root=PROCESS_LAUNCH_PROC_ROOT,
    )
    return require_process_launch_identity_document(document)


def require_process_launch_identity_document(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate a canonical identity document from the fixed public proc root."""

    if not isinstance(value, Mapping):
        raise ValidationProcessLaunchIdentityError(
            "process launch identity document must be a mapping"
        )
    document = dict(value)
    if set(document) != _DOCUMENT_FIELDS:
        raise ValidationProcessLaunchIdentityError(
            "process launch identity document fields are invalid"
        )
    if document.get("schema_id") != PROCESS_LAUNCH_IDENTITY_SCHEMA_ID:
        raise ValidationProcessLaunchIdentityError(
            "process launch identity schema is invalid"
        )
    if (
        document.get("contract_sha256")
        != FROZEN_PROCESS_LAUNCH_IDENTITY_CONTRACT_SHA256
    ):
        raise ValidationProcessLaunchIdentityError(
            "process launch identity contract hash is invalid"
        )
    if document.get("proc_root") != PROCESS_LAUNCH_PROC_ROOT:
        raise ValidationProcessLaunchIdentityError(
            "process launch identity was not measured from fixed /proc"
        )
    boot_id = _require_boot_id(document.get("boot_id"))
    boot_id_sha256 = _require_lower_sha256(
        document.get("boot_id_sha256"),
        name="boot id hash",
    )
    if boot_id_sha256 != hashlib.sha256(boot_id.encode("ascii")).hexdigest():
        raise ValidationProcessLaunchIdentityError("boot id hash is inconsistent")
    for field_name, maximum in (
        ("pid", PROCESS_LAUNCH_MAX_PID),
        ("start_time_clock_ticks", PROCESS_LAUNCH_MAX_CLOCK_TICKS),
        ("pid_namespace_inode", PROCESS_LAUNCH_MAX_NAMESPACE_INODE),
    ):
        _require_bounded_positive_integer(
            document.get(field_name),
            name=field_name.replace("_", " "),
            maximum=maximum,
        )
    _require_bounded_nonnegative_integer(
        document.get("parent_pid"),
        name="parent pid",
        maximum=PROCESS_LAUNCH_MAX_PID,
    )
    identity_sha256 = _require_lower_sha256(
        document.get("process_launch_identity_sha256"),
        name="process launch identity hash",
    )
    projection = {
        key: document[key]
        for key in sorted(document)
        if key != "process_launch_identity_sha256"
    }
    if identity_sha256 != _sha256(projection):
        raise ValidationProcessLaunchIdentityError(
            "process launch identity self hash is inconsistent"
        )
    return json.loads(_canonical_bytes(document).decode("ascii"))


def verify_process_launch_identity(
    value: Mapping[str, Any],
    *,
    expected_pid: int,
    expected_parent_pid: int,
    expected_start_time_clock_ticks: int,
    expected_pid_namespace_inode: int,
    expected_boot_id_sha256: str,
) -> dict[str, Any]:
    """Require exact caller-supplied process, namespace, and boot identities."""

    document = require_process_launch_identity_document(value)
    expected = {
        "pid": _require_bounded_positive_integer(
            expected_pid,
            name="expected process id",
            maximum=PROCESS_LAUNCH_MAX_PID,
        ),
        "parent_pid": _require_bounded_nonnegative_integer(
            expected_parent_pid,
            name="expected parent process id",
            maximum=PROCESS_LAUNCH_MAX_PID,
        ),
        "start_time_clock_ticks": _require_bounded_positive_integer(
            expected_start_time_clock_ticks,
            name="expected process start time clock ticks",
            maximum=PROCESS_LAUNCH_MAX_CLOCK_TICKS,
        ),
        "pid_namespace_inode": _require_bounded_positive_integer(
            expected_pid_namespace_inode,
            name="expected PID namespace inode",
            maximum=PROCESS_LAUNCH_MAX_NAMESPACE_INODE,
        ),
        "boot_id_sha256": _require_lower_sha256(
            expected_boot_id_sha256,
            name="expected boot id hash",
        ),
    }
    for field_name, expected_value in expected.items():
        if document[field_name] != expected_value:
            raise ValidationProcessLaunchIdentityError(
                f"process launch identity {field_name} does not match expected"
            )
    return document


def _contract_projection() -> dict[str, Any]:
    return {
        "schema_id": PROCESS_LAUNCH_IDENTITY_CONTRACT_SCHEMA_ID,
        "contract_id": PROCESS_LAUNCH_IDENTITY_CONTRACT_ID,
        "contract_version": PROCESS_LAUNCH_IDENTITY_CONTRACT_VERSION,
        "frozen_at_utc": PROCESS_LAUNCH_IDENTITY_CONTRACT_FROZEN_AT_UTC,
        "purpose": {
            "linux_process_launch_tuple_binding_only": True,
            "tuple_is_best_effort_same_boot_discriminator": True,
            "same_tick_pid_reuse_collision_excluded": False,
            "durable_process_uniqueness_established": False,
            "measurement_performed_at_contract_import": False,
            "production_execution_authorized": False,
            "external_host_authenticity_established": False,
            "external_worker_launch_custody_established": False,
        },
        "measurement_contract": {
            "public_proc_root": PROCESS_LAUNCH_PROC_ROOT,
            "public_proc_root_is_fixed": True,
            "injectable_proc_root_is_private_test_only": True,
            "non_proc_root_document_is_publicly_accepted": False,
            "boot_id_relative_path": PROCESS_LAUNCH_BOOT_ID_RELATIVE_PATH,
            "boot_id_exact_lowercase_uuid_required": True,
            "boot_id_sha256_required": True,
            "process_stat_field_22_start_time_clock_ticks_required": True,
            "process_start_time_has_clock_tick_resolution_only": True,
            "parent_pid_zero_allowed_for_pid_namespace_init": True,
            "process_stat_command_may_contain_spaces_and_closing_parentheses": True,
            "pid_namespace_inode_required": True,
            "numeric_process_directory_required": True,
            "bounded_reads_required": True,
            "regular_file_reads_use_o_nofollow_and_o_cloexec": True,
            "namespace_magic_link_uses_bounded_lstat_readlink_identity": True,
            "before_after_object_identity_required": True,
            "double_boot_process_and_namespace_observation_required": True,
            "pid_start_time_and_namespace_positive_bounded": True,
            "parent_pid_nonnegative_bounded": True,
            "canonical_document_self_hash_required": True,
        },
        "security_limits": {
            "maximum_boot_id_bytes": PROCESS_LAUNCH_MAX_BOOT_ID_BYTES,
            "maximum_process_stat_bytes": PROCESS_LAUNCH_MAX_STAT_BYTES,
            "maximum_namespace_target_bytes": (
                PROCESS_LAUNCH_MAX_NAMESPACE_TARGET_BYTES
            ),
            "maximum_pid": PROCESS_LAUNCH_MAX_PID,
            "maximum_clock_ticks": PROCESS_LAUNCH_MAX_CLOCK_TICKS,
            "maximum_namespace_inode": PROCESS_LAUNCH_MAX_NAMESPACE_INODE,
        },
        "authenticity_limits": {
            "procfs_superblock_identity_authenticated": False,
            "boot_id_is_external_host_identity": False,
            "namespace_inode_is_external_launch_custody": False,
            "same_host_process_tuple_is_external_authentication": False,
            "same_tick_pid_reuse_collision_excluded": False,
            "durable_process_uniqueness_established": False,
            "external_launch_nonce_bound": False,
            "external_signed_runtime_manifest_bound": False,
        },
        "claim_policy": {
            "production_process_authenticity_established": False,
            "production_validation_results_collected": False,
            "scientifically_validated": False,
            "benchmark_validated": False,
            "product_qualified": False,
            "parameter_fitting_authorized": False,
            "claim_safe": False,
        },
        "blockers": list(_BLOCKERS),
    }


def process_launch_identity_contract_document() -> dict[str, Any]:
    """Return the exact frozen primitive contract without measuring a process."""

    projection = _contract_projection()
    observed = _sha256(projection)
    if observed != FROZEN_PROCESS_LAUNCH_IDENTITY_CONTRACT_SHA256:
        raise ValidationProcessLaunchIdentityError(
            "process launch identity contract projection drifted"
        )
    return {**projection, "contract_sha256": observed}


def require_process_launch_identity_contract_document(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationProcessLaunchIdentityError(
            "process launch identity contract must be a mapping"
        )
    expected = process_launch_identity_contract_document()
    if dict(value) != expected:
        raise ValidationProcessLaunchIdentityError(
            "process launch identity contract does not match the frozen record"
        )
    return expected


def process_launch_identity_decision() -> dict[str, Any]:
    contract = process_launch_identity_contract_document()
    return {
        "contract_sha256": contract["contract_sha256"],
        "linux_process_launch_identity_primitive_implemented": True,
        "fixed_public_proc_root_enforced": True,
        "pid_parent_start_time_boot_and_namespace_binding_implemented": True,
        "tuple_is_best_effort_same_boot_discriminator": True,
        "same_tick_pid_reuse_collision_excluded": False,
        "durable_process_uniqueness_established": False,
        "external_launch_nonce_bound": False,
        "procfs_superblock_identity_authenticated": False,
        "external_host_authenticity_established": False,
        "external_worker_launch_custody_established": False,
        "production_process_authenticity_established": False,
        "production_validation_results_collected": False,
        "scientifically_validated": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "parameter_fitting_authorized": False,
        "claim_safe": False,
        "blockers": list(_BLOCKERS),
    }


__all__ = [
    "FROZEN_PROCESS_LAUNCH_IDENTITY_CONTRACT_SHA256",
    "PROCESS_LAUNCH_BOOT_ID_RELATIVE_PATH",
    "PROCESS_LAUNCH_IDENTITY_CONTRACT_ID",
    "PROCESS_LAUNCH_IDENTITY_CONTRACT_SCHEMA_ID",
    "PROCESS_LAUNCH_IDENTITY_CONTRACT_VERSION",
    "PROCESS_LAUNCH_IDENTITY_SCHEMA_ID",
    "PROCESS_LAUNCH_PROC_ROOT",
    "ValidationProcessLaunchIdentityError",
    "measure_process_launch_identity",
    "process_launch_identity_contract_document",
    "process_launch_identity_decision",
    "require_process_launch_identity_contract_document",
    "require_process_launch_identity_document",
    "verify_process_launch_identity",
]
