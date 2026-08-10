"""Fail-closed, non-consuming host preflight for CPU performance profile v3."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import platform
import stat
import sys
from typing import Final

from betelgeuze_engine_v2.docking import performance_sidecar as v2


CPU_BOOST_SYSFS_PATH: Final = Path("/sys/devices/system/cpu/cpufreq/boost")
CPU_BOOST_MAXIMUM_ACTUAL_BYTES: Final = 32
CPU_BOOST_READER_ID: Final = "betelgeuze.linux_sysfs_boolean_reader/1.0.0"
HOST_PREFLIGHT_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_cpu_performance_host_preflight/3.0.0"
)


class CPUPerformanceHostPreflightError(ValueError):
    """A typed fail-closed host-preflight failure."""

    def __init__(self, code: str) -> None:
        if not code or not code.isascii():
            raise ValueError("host-preflight error code must be non-empty ASCII")
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class SysfsBooleanEvidenceV3:
    path: str
    reader_id: str
    raw_byte_count: int
    raw_sha256: str
    reported_size_before: int
    reported_size_descriptor_before: int
    reported_size_descriptor_after: int
    reported_size_after: int
    stable_read_count: int
    boost_enabled: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "reader_id": self.reader_id,
            "raw_byte_count": self.raw_byte_count,
            "raw_sha256": self.raw_sha256,
            "reported_size_before": self.reported_size_before,
            "reported_size_descriptor_before": (
                self.reported_size_descriptor_before
            ),
            "reported_size_descriptor_after": self.reported_size_descriptor_after,
            "reported_size_after": self.reported_size_after,
            "stable_read_count": self.stable_read_count,
            "boost_enabled": self.boost_enabled,
        }


@dataclass(frozen=True, slots=True)
class HostPreflightEvidenceV3:
    cpu_model: str
    boost_state: SysfsBooleanEvidenceV3 | None
    available_cpu_affinity: tuple[int, ...]
    platform_system: str
    platform_machine: str
    byteorder: str
    parent_pid: int
    parent_os_task_count: int
    qualified: bool
    blockers: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": HOST_PREFLIGHT_SCHEMA_ID,
            "cpu_model": self.cpu_model,
            "boost_state": (
                None if self.boost_state is None else self.boost_state.to_dict()
            ),
            "available_cpu_affinity": list(self.available_cpu_affinity),
            "platform_system": self.platform_system,
            "platform_machine": self.platform_machine,
            "byteorder": self.byteorder,
            "parent_pid": self.parent_pid,
            "parent_os_task_count": self.parent_os_task_count,
            "qualified": self.qualified,
            "blockers": list(self.blockers),
            "consumes_qualification": False,
            "launches_measurements": False,
            "molecular_execution": False,
        }


_IDENTITY_FIELDS: Final = (
    "st_dev",
    "st_ino",
    "st_mode",
    "st_uid",
    "st_gid",
    "st_nlink",
)


def _same_identity(left: os.stat_result, right: os.stat_result) -> bool:
    return all(getattr(left, field) == getattr(right, field) for field in _IDENTITY_FIELDS)


def _validate_sysfs_metadata(
    metadata: os.stat_result,
    *,
    expected_uid: int,
) -> None:
    """Validate identity and permissions while treating st_size as advisory."""

    if not stat.S_ISREG(metadata.st_mode):
        raise CPUPerformanceHostPreflightError("boost_state_not_regular")
    if metadata.st_uid != expected_uid:
        raise CPUPerformanceHostPreflightError("boost_state_owner_mismatch")
    if metadata.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise CPUPerformanceHostPreflightError("boost_state_writable_by_others")
    if metadata.st_nlink != 1:
        raise CPUPerformanceHostPreflightError("boost_state_link_count_invalid")


def _descriptor_metadata(descriptor: int) -> os.stat_result:
    try:
        return os.fstat(descriptor)
    except OSError as exc:
        raise CPUPerformanceHostPreflightError(
            "boost_state_metadata_unavailable"
        ) from exc


def _read_actual_payload(descriptor: int, *, maximum_actual_bytes: int) -> bytes:
    chunks: list[bytes] = []
    remaining = maximum_actual_bytes + 1
    while remaining:
        try:
            chunk = os.read(descriptor, remaining)
        except OSError as exc:
            raise CPUPerformanceHostPreflightError("boost_state_read_failed") from exc
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    raw = b"".join(chunks)
    if len(raw) > maximum_actual_bytes:
        raise CPUPerformanceHostPreflightError("boost_state_actual_bytes_exceeded")
    return raw


def _read_sysfs_boolean(
    path: Path,
    *,
    expected_uid: int,
    maximum_actual_bytes: int = CPU_BOOST_MAXIMUM_ACTUAL_BYTES,
) -> SysfsBooleanEvidenceV3:
    """Read one immutable sysfs boolean without trusting pseudo-file st_size."""

    if not path.is_absolute() or maximum_actual_bytes < 1:
        raise CPUPerformanceHostPreflightError("boost_state_reader_contract_invalid")
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if nofollow == 0:
        raise CPUPerformanceHostPreflightError("boost_state_safe_open_unavailable")
    try:
        before = path.lstat()
    except OSError as exc:
        raise CPUPerformanceHostPreflightError("boost_state_unavailable") from exc
    if stat.S_ISLNK(before.st_mode):
        raise CPUPerformanceHostPreflightError("boost_state_symlink_forbidden")
    _validate_sysfs_metadata(before, expected_uid=expected_uid)

    flags = os.O_RDONLY | os.O_CLOEXEC | nofollow
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise CPUPerformanceHostPreflightError("boost_state_safe_open_failed") from exc
    try:
        descriptor_before = _descriptor_metadata(descriptor)
        _validate_sysfs_metadata(descriptor_before, expected_uid=expected_uid)
        if not _same_identity(before, descriptor_before):
            raise CPUPerformanceHostPreflightError("boost_state_identity_changed")

        raw = _read_actual_payload(
            descriptor, maximum_actual_bytes=maximum_actual_bytes
        )
        try:
            if os.lseek(descriptor, 0, os.SEEK_SET) != 0:
                raise OSError("unexpected sysfs rewind offset")
        except OSError as exc:
            raise CPUPerformanceHostPreflightError("boost_state_rewind_failed") from exc
        repeated_raw = _read_actual_payload(
            descriptor, maximum_actual_bytes=maximum_actual_bytes
        )
        if repeated_raw != raw:
            raise CPUPerformanceHostPreflightError("boost_state_value_changed")

        descriptor_after = _descriptor_metadata(descriptor)
        _validate_sysfs_metadata(descriptor_after, expected_uid=expected_uid)
        if not _same_identity(descriptor_before, descriptor_after):
            raise CPUPerformanceHostPreflightError("boost_state_identity_changed")
    finally:
        os.close(descriptor)

    try:
        after = path.lstat()
    except OSError as exc:
        raise CPUPerformanceHostPreflightError("boost_state_changed_after_read") from exc
    _validate_sysfs_metadata(after, expected_uid=expected_uid)
    if not _same_identity(descriptor_after, after):
        raise CPUPerformanceHostPreflightError("boost_state_identity_changed")
    if raw not in (b"0", b"0\n", b"1", b"1\n"):
        raise CPUPerformanceHostPreflightError("boost_state_payload_invalid")

    return SysfsBooleanEvidenceV3(
        path=str(path),
        reader_id=CPU_BOOST_READER_ID,
        raw_byte_count=len(raw),
        raw_sha256=hashlib.sha256(raw).hexdigest(),
        reported_size_before=before.st_size,
        reported_size_descriptor_before=descriptor_before.st_size,
        reported_size_descriptor_after=descriptor_after.st_size,
        reported_size_after=after.st_size,
        stable_read_count=2,
        boost_enabled=raw.strip() == b"1",
    )


def read_cpu_boost_state_v3() -> SysfsBooleanEvidenceV3:
    """Read the exact production boost path; callers cannot redirect it."""

    return _read_sysfs_boolean(CPU_BOOST_SYSFS_PATH, expected_uid=0)


def derive_host_preflight_evidence_v3() -> HostPreflightEvidenceV3:
    """Inspect the host without launching a timed or molecular workload."""

    blockers: list[str] = []
    try:
        model = v2._cpu_model()
    except v2.CPUPerformanceError:
        model = ""
        blockers.append("cpu_model_unavailable")
    if model and model != v2.CPU_MODEL_EXACT:
        blockers.append("cpu_model_not_qualified")

    boost_state: SysfsBooleanEvidenceV3 | None
    try:
        boost_state = read_cpu_boost_state_v3()
    except CPUPerformanceHostPreflightError as exc:
        boost_state = None
        blockers.append(exc.code)
    else:
        if boost_state.boost_enabled:
            blockers.append("cpu_boost_not_disabled")

    try:
        affinity = tuple(sorted(os.sched_getaffinity(0)))
    except (AttributeError, OSError):
        affinity = ()
        blockers.append("process_affinity_unavailable")
    if not set(v2.AUTHORITATIVE_CPU_AFFINITY).issubset(affinity):
        blockers.append("authoritative_cpu_not_available")

    system = platform.system()
    machine = platform.machine()
    if system != "Linux":
        blockers.append("linux_host_required")
    if machine != "x86_64":
        blockers.append("x86_64_host_required")
    if sys.byteorder != "little":
        blockers.append("little_endian_host_required")
    parent_tasks = v2._os_task_count(os.getpid())
    if parent_tasks < 1:
        blockers.append("parent_os_task_count_unavailable")
    elif parent_tasks != 1:
        blockers.append("parent_os_task_count_not_one")

    unique_blockers = tuple(dict.fromkeys(blockers))
    return HostPreflightEvidenceV3(
        cpu_model=model,
        boost_state=boost_state,
        available_cpu_affinity=affinity,
        platform_system=system,
        platform_machine=machine,
        byteorder=sys.byteorder,
        parent_pid=os.getpid(),
        parent_os_task_count=parent_tasks,
        qualified=not unique_blockers,
        blockers=unique_blockers,
    )


__all__ = [
    "CPU_BOOST_MAXIMUM_ACTUAL_BYTES",
    "CPU_BOOST_READER_ID",
    "CPU_BOOST_SYSFS_PATH",
    "CPUPerformanceHostPreflightError",
    "HOST_PREFLIGHT_SCHEMA_ID",
    "HostPreflightEvidenceV3",
    "SysfsBooleanEvidenceV3",
    "derive_host_preflight_evidence_v3",
    "read_cpu_boost_state_v3",
]
