"""Measured runtime/RSS companion for the internal PoseBusters oracle.

The deterministic oracle receipt remains byte-reexecutable.  This module
observes a separate exact reexecution with ``perf_counter_ns`` and bounded
Linux ``/proc/self/statm`` sampling, then binds the non-deterministic
measurements to the unchanged oracle receipt, implementation sources, engine
wheel, runtime environment, and every all-case row.

The companion is an unsigned local observation.  Sampled RSS is not a
kernel-enforced per-case maximum, instrumentation overhead is not subtracted,
and no benchmark or product claim is opened.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from email.parser import BytesParser
from email.policy import default as email_policy
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import stat
import sys
import tempfile
import threading
import time
from typing import Callable, Mapping, Sequence
import zipfile

from betelgeuze_engine_v2.contracts import DISTRIBUTION_VERSION

from .public_posebusters_corpus_audit import (
    _canonical_bytes,
    _canonical_sha256,
    _source_file_sha256,
)
from .public_posebusters_generated_pose_evaluation import (
    _case_id,
    _digest,
    _hash_bytes,
    _positive_int,
    _token,
)
from .public_posebusters_intake import (
    OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT,
    PoseBustersArchiveContract,
    _hash_descriptor,
    _read_exact_regular_file,
    _regular_file_descriptor,
)
from .public_posebusters_internal_execution import (
    PoseBustersInternalExecutionConfig,
)
from .public_posebusters_internal_oracle_evaluation import (
    POSEBUSTERS_INTERNAL_ORACLE_BLOCKERS,
    POSEBUSTERS_INTERNAL_ORACLE_MAX_RECEIPT_BYTES,
    PoseBustersInternalOracleCase,
    PoseBustersInternalOracleEvaluationError,
    PoseBustersInternalOracleEvaluationReceipt,
    _verify_posebusters_internal_oracle_evaluation_receipt,
    verify_posebusters_internal_oracle_evaluation_receipt,
)
from .public_posebusters_internal_preparation import (
    PoseBustersInternalPreparationConfig,
)
from .public_posebusters_internal_rmsd_evaluation import (
    PoseBustersInternalRMSDConfig,
)


POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_WHEEL_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_oracle_runtime_wheel/1.0.0"
)
POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_ENVIRONMENT_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_oracle_runtime_environment/1.0.0"
)
POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_CASE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_oracle_runtime_case/1.0.0"
)
POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_OBSERVATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_oracle_runtime_observation/1.0.0"
)
POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_MAX_RECEIPT_BYTES = 32 * 1024 * 1024
POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_MAX_ENGINE_WHEEL_BYTES = 64 * 1024 * 1024
POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_MAX_SOURCE_BYTES = 2 * 1024 * 1024
POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_SAMPLE_INTERVAL_NS = 5_000_000

POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_CONFIGURATION = {
    "schema_id": (
        "betelgeuze.engine_v2_posebusters_internal_oracle_runtime_configuration/1.0.0"
    ),
    "wall_clock_source": "time.perf_counter_ns",
    "rss_source": "linux_proc_self_statm_resident_pages_times_sysconf_page_size",
    "sample_interval_ns": POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_SAMPLE_INTERVAL_NS,
    "synchronous_case_boundary_samples": True,
    "background_rss_sampling": True,
    "batch_measurement_scope": (
        "full_exact_internal_oracle_receipt_reexecution_including_upstream_chain"
    ),
    "case_measurement_scope": (
        "downstream_posebusters_oracle_case_loop_only"
    ),
    "measurement_values_are_not_exactly_reexecutable": True,
    "oracle_payload_is_observer_independent": True,
}
POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_CONFIGURATION_SHA256 = (
    "ff8d8995bd52fc8cfa67f6bd2b085a15a16c177658d946058d529951aed06192"
)

POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_BLOCKERS = tuple(
    dict.fromkeys(
        (
            *(
                blocker
                for blocker in POSEBUSTERS_INTERNAL_ORACLE_BLOCKERS
                if blocker != "wall_clock_and_peak_memory_measurement_missing"
            ),
            "runtime_observation_is_unsigned_operator_local_measurement",
            "rss_peak_is_sampled_not_kernel_enforced_case_peak",
            "sampling_and_observer_overhead_not_subtracted",
            "case_processes_not_isolated_for_memory_measurement",
            "per_case_full_redocking_pipeline_runtime_breakdown_missing",
            "physical_host_identity_not_proven",
            "independent_second_host_runtime_observation_missing",
        )
    )
)

_ENGINE_SOURCE_MEMBERS = {
    "internal_oracle_runtime_observation": (
        "betelgeuze_engine_v2/benchmark/"
        "public_posebusters_internal_oracle_runtime_observation.py"
    ),
    "internal_oracle_evaluation": (
        "betelgeuze_engine_v2/benchmark/"
        "public_posebusters_internal_oracle_evaluation.py"
    ),
    "posebusters_generated_pose_runtime": (
        "betelgeuze_engine_v2/benchmark/"
        "public_posebusters_generated_pose_evaluation.py"
    ),
}
_SAFE_ENVIRONMENT_NAMES = (
    "CUDA_VISIBLE_DEVICES",
    "HIP_VISIBLE_DEVICES",
    "MKL_NUM_THREADS",
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "PYTHONHASHSEED",
    "ROCR_VISIBLE_DEVICES",
)
_DISTRIBUTIONS = (
    "betelgeuze-engine-v2",
    "meeko",
    "numpy",
    "pandas",
    "posebusters",
    "rdkit",
    "torch",
)


class PoseBustersInternalOracleRuntimeObservationError(
    PoseBustersInternalOracleEvaluationError
):
    """Runtime-observation input, execution, or receipt is invalid."""


def _text(
    value: object,
    *,
    name: str,
    maximum: int = 512,
    allow_empty: bool = False,
) -> str:
    if (
        not isinstance(value, str)
        or (not value and not allow_empty)
        or len(value) > maximum
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise PoseBustersInternalOracleRuntimeObservationError(
            f"{name} must be bounded printable text"
        )
    return value


def _mapping(value: object, *, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(
        not isinstance(key, str) for key in value
    ):
        raise PoseBustersInternalOracleRuntimeObservationError(
            f"{name} must be an object"
        )
    return value


def _list(value: object, *, name: str) -> list[object]:
    if not isinstance(value, list):
        raise PoseBustersInternalOracleRuntimeObservationError(
            f"{name} must be a list"
        )
    return value


def _nonnegative_int(value: object, *, name: str) -> int:
    return _positive_int(value, name=name, allow_zero=True)


def _current_source_members() -> tuple[tuple[str, str], ...]:
    root = Path(__file__).resolve().parents[2]
    rows = tuple(
        sorted(
            (
                role,
                _source_file_sha256(root / relative_path),
            )
            for role, relative_path in _ENGINE_SOURCE_MEMBERS.items()
        )
    )
    return rows


@dataclass(frozen=True, slots=True)
class PoseBustersInternalOracleRuntimeWheelBinding:
    filename: str
    sha256: str
    size_bytes: int
    distribution_name: str
    distribution_version: str
    source_members: tuple[tuple[str, str], ...]
    schema_id: str = POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_WHEEL_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_WHEEL_SCHEMA_ID:
            raise PoseBustersInternalOracleRuntimeObservationError(
                "unsupported runtime wheel-binding schema"
            )
        filename = _text(self.filename, name="engine wheel filename", maximum=255)
        if Path(filename).name != filename or not filename.endswith(".whl"):
            raise PoseBustersInternalOracleRuntimeObservationError(
                "engine wheel filename is invalid"
            )
        digest = _digest(self.sha256, name="engine wheel")
        size = _positive_int(self.size_bytes, name="engine wheel size")
        distribution = _text(
            self.distribution_name,
            name="engine wheel distribution",
        )
        version = _text(
            self.distribution_version,
            name="engine wheel version",
        )
        if distribution != "betelgeuze-engine-v2" or version != DISTRIBUTION_VERSION:
            raise PoseBustersInternalOracleRuntimeObservationError(
                "engine wheel distribution identity is wrong"
            )
        members = tuple(
            (
                _token(role, name="engine source role"),
                _digest(member_digest, name=f"{role} wheel source"),
            )
            for role, member_digest in self.source_members
        )
        if (
            tuple(sorted(members)) != members
            or tuple(role for role, _digest_value in members)
            != tuple(sorted(_ENGINE_SOURCE_MEMBERS))
        ):
            raise PoseBustersInternalOracleRuntimeObservationError(
                "engine wheel source-member projection is invalid"
            )
        object.__setattr__(self, "filename", filename)
        object.__setattr__(self, "sha256", digest)
        object.__setattr__(self, "size_bytes", size)
        object.__setattr__(self, "distribution_name", distribution)
        object.__setattr__(self, "distribution_version", version)
        object.__setattr__(self, "source_members", members)

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "filename": self.filename,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "distribution_name": self.distribution_name,
            "distribution_version": self.distribution_version,
            "source_members": dict(self.source_members),
        }

    @classmethod
    def from_dict(
        cls,
        raw: Mapping[str, object],
    ) -> "PoseBustersInternalOracleRuntimeWheelBinding":
        source_members = _mapping(
            raw.get("source_members"),
            name="wheel source members",
        )
        return cls(
            filename=raw.get("filename"),  # type: ignore[arg-type]
            sha256=raw.get("sha256"),  # type: ignore[arg-type]
            size_bytes=raw.get("size_bytes"),  # type: ignore[arg-type]
            distribution_name=raw.get("distribution_name"),  # type: ignore[arg-type]
            distribution_version=raw.get("distribution_version"),  # type: ignore[arg-type]
            source_members=tuple(source_members.items()),  # type: ignore[arg-type]
            schema_id=raw.get("schema_id"),  # type: ignore[arg-type]
        )


def _engine_wheel_binding(
    wheel_path: str | os.PathLike[str],
    *,
    expected_sha256: str,
) -> PoseBustersInternalOracleRuntimeWheelBinding:
    expected = _digest(expected_sha256, name="expected engine wheel")
    descriptor, size = _regular_file_descriptor(
        wheel_path,
        maximum_bytes=POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_MAX_ENGINE_WHEEL_BYTES,
    )
    try:
        observed_sha = _hash_descriptor(descriptor, size)
        if observed_sha != expected:
            raise PoseBustersInternalOracleRuntimeObservationError(
                "engine wheel differs from its expected identity"
            )
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            try:
                with zipfile.ZipFile(handle, "r") as archive:
                    infos = archive.infolist()
                    names = tuple(info.filename for info in infos)
                    if len(set(names)) != len(names):
                        raise PoseBustersInternalOracleRuntimeObservationError(
                            "engine wheel contains duplicate members"
                        )
                    source_rows: list[tuple[str, str]] = []
                    for role, member_path in sorted(_ENGINE_SOURCE_MEMBERS.items()):
                        try:
                            info = archive.getinfo(member_path)
                        except KeyError as exc:
                            raise PoseBustersInternalOracleRuntimeObservationError(
                                "engine wheel omits a measured implementation source"
                            ) from exc
                        mode = info.external_attr >> 16
                        if (
                            info.is_dir()
                            or not stat.S_ISREG(mode)
                            or info.file_size < 1
                            or info.file_size
                            > POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_MAX_SOURCE_BYTES
                        ):
                            raise PoseBustersInternalOracleRuntimeObservationError(
                                "engine wheel implementation source is not bounded regular data"
                            )
                        source_rows.append(
                            (role, hashlib.sha256(archive.read(info)).hexdigest())
                        )
                    metadata_infos = tuple(
                        info
                        for info in infos
                        if info.filename.endswith(".dist-info/METADATA")
                    )
                    if len(metadata_infos) != 1:
                        raise PoseBustersInternalOracleRuntimeObservationError(
                            "engine wheel metadata member is ambiguous"
                        )
                    metadata_info = metadata_infos[0]
                    if not 1 <= metadata_info.file_size <= 256 * 1024:
                        raise PoseBustersInternalOracleRuntimeObservationError(
                            "engine wheel metadata is outside its byte bound"
                        )
                    metadata = BytesParser(policy=email_policy).parsebytes(
                        archive.read(metadata_info)
                    )
            except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
                raise PoseBustersInternalOracleRuntimeObservationError(
                    "engine wheel failed bounded ZIP inspection"
                ) from exc
    finally:
        os.close(descriptor)
    current_members = _current_source_members()
    observed_members = tuple(source_rows)
    if observed_members != current_members:
        raise PoseBustersInternalOracleRuntimeObservationError(
            "engine wheel sources differ from the executing implementation"
        )
    distribution = str(metadata.get("Name", ""))
    version = str(metadata.get("Version", ""))
    return PoseBustersInternalOracleRuntimeWheelBinding(
        filename=Path(wheel_path).name,
        sha256=observed_sha,
        size_bytes=size,
        distribution_name=distribution,
        distribution_version=version,
        source_members=observed_members,
    )


@dataclass(frozen=True, slots=True)
class PoseBustersInternalOracleRuntimeEnvironment:
    platform_system: str
    platform_release: str
    platform_machine: str
    processor: str
    python_implementation: str
    python_version: str
    python_executable_sha256: str
    python_executable_size_bytes: int
    page_size_bytes: int
    distribution_versions: tuple[tuple[str, str | None], ...]
    safe_environment: tuple[tuple[str, str], ...]
    cpu_projection_sha256: str
    physical_host_identity_proven: bool = False
    schema_id: str = POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_ENVIRONMENT_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_ENVIRONMENT_SCHEMA_ID:
            raise PoseBustersInternalOracleRuntimeObservationError(
                "unsupported runtime-environment schema"
            )
        system = _text(self.platform_system, name="runtime platform system")
        release = _text(self.platform_release, name="runtime platform release")
        machine = _text(self.platform_machine, name="runtime platform machine")
        processor = _text(self.processor, name="runtime processor")
        implementation = _text(
            self.python_implementation,
            name="runtime Python implementation",
        )
        version = _text(self.python_version, name="runtime Python version")
        executable_sha = _digest(
            self.python_executable_sha256,
            name="runtime Python executable",
        )
        executable_size = _positive_int(
            self.python_executable_size_bytes,
            name="runtime Python executable size",
        )
        page_size = _positive_int(self.page_size_bytes, name="runtime page size")
        distributions = tuple(
            (
                _token(name, name="runtime distribution name"),
                (
                    None
                    if value is None
                    else _text(value, name=f"{name} runtime version")
                ),
            )
            for name, value in self.distribution_versions
        )
        environment = tuple(
            (
                _text(
                    name,
                    name="safe environment name",
                    maximum=64,
                ),
                _text(
                    value,
                    name=f"{name} safe environment value",
                    maximum=1024,
                    allow_empty=True,
                ),
            )
            for name, value in self.safe_environment
        )
        cpu_projection = {
            "platform_system": system,
            "platform_release": release,
            "platform_machine": machine,
            "processor": processor,
        }
        if (
            system != "Linux"
            or tuple(name for name, _value in distributions) != _DISTRIBUTIONS
            or tuple(name for name, _value in environment)
            != _SAFE_ENVIRONMENT_NAMES
            or tuple(sorted(distributions)) != distributions
            or tuple(sorted(environment)) != environment
            or self.cpu_projection_sha256 != _canonical_sha256(cpu_projection)
            or self.physical_host_identity_proven is not False
        ):
            raise PoseBustersInternalOracleRuntimeObservationError(
                "runtime environment projection is invalid"
            )
        object.__setattr__(self, "platform_system", system)
        object.__setattr__(self, "platform_release", release)
        object.__setattr__(self, "platform_machine", machine)
        object.__setattr__(self, "processor", processor)
        object.__setattr__(self, "python_implementation", implementation)
        object.__setattr__(self, "python_version", version)
        object.__setattr__(self, "python_executable_sha256", executable_sha)
        object.__setattr__(self, "python_executable_size_bytes", executable_size)
        object.__setattr__(self, "page_size_bytes", page_size)
        object.__setattr__(self, "distribution_versions", distributions)
        object.__setattr__(self, "safe_environment", environment)

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "platform_system": self.platform_system,
            "platform_release": self.platform_release,
            "platform_machine": self.platform_machine,
            "processor": self.processor,
            "python_implementation": self.python_implementation,
            "python_version": self.python_version,
            "python_executable_sha256": self.python_executable_sha256,
            "python_executable_size_bytes": self.python_executable_size_bytes,
            "page_size_bytes": self.page_size_bytes,
            "distribution_versions": dict(self.distribution_versions),
            "safe_environment": dict(self.safe_environment),
            "cpu_projection_sha256": self.cpu_projection_sha256,
            "physical_host_identity_proven": self.physical_host_identity_proven,
        }

    @classmethod
    def from_dict(
        cls,
        raw: Mapping[str, object],
    ) -> "PoseBustersInternalOracleRuntimeEnvironment":
        distributions = _mapping(
            raw.get("distribution_versions"),
            name="runtime distribution versions",
        )
        environment = _mapping(
            raw.get("safe_environment"),
            name="safe runtime environment",
        )
        return cls(
            platform_system=raw.get("platform_system"),  # type: ignore[arg-type]
            platform_release=raw.get("platform_release"),  # type: ignore[arg-type]
            platform_machine=raw.get("platform_machine"),  # type: ignore[arg-type]
            processor=raw.get("processor"),  # type: ignore[arg-type]
            python_implementation=raw.get("python_implementation"),  # type: ignore[arg-type]
            python_version=raw.get("python_version"),  # type: ignore[arg-type]
            python_executable_sha256=raw.get("python_executable_sha256"),  # type: ignore[arg-type]
            python_executable_size_bytes=raw.get("python_executable_size_bytes"),  # type: ignore[arg-type]
            page_size_bytes=raw.get("page_size_bytes"),  # type: ignore[arg-type]
            distribution_versions=tuple(distributions.items()),  # type: ignore[arg-type]
            safe_environment=tuple(environment.items()),  # type: ignore[arg-type]
            cpu_projection_sha256=raw.get("cpu_projection_sha256"),  # type: ignore[arg-type]
            physical_host_identity_proven=raw.get("physical_host_identity_proven"),  # type: ignore[arg-type]
            schema_id=raw.get("schema_id"),  # type: ignore[arg-type]
        )


def _distribution_versions() -> tuple[tuple[str, str | None], ...]:
    rows: list[tuple[str, str | None]] = []
    for distribution in _DISTRIBUTIONS:
        try:
            version: str | None = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            version = None
        rows.append((distribution, version))
    return tuple(rows)


def _observe_runtime_environment() -> PoseBustersInternalOracleRuntimeEnvironment:
    executable = Path(sys.executable).resolve(strict=True)
    descriptor, size = _regular_file_descriptor(
        executable,
        maximum_bytes=128 * 1024 * 1024,
    )
    try:
        executable_sha = _hash_descriptor(descriptor, size)
    finally:
        os.close(descriptor)
    processor = platform.processor() or platform.machine()
    cpu_projection = {
        "platform_system": platform.system(),
        "platform_release": platform.release(),
        "platform_machine": platform.machine().lower(),
        "processor": processor,
    }
    page_size = os.sysconf("SC_PAGE_SIZE")
    if not isinstance(page_size, int):
        raise PoseBustersInternalOracleRuntimeObservationError(
            "runtime page size is unavailable"
        )
    return PoseBustersInternalOracleRuntimeEnvironment(
        platform_system=cpu_projection["platform_system"],
        platform_release=cpu_projection["platform_release"],
        platform_machine=cpu_projection["platform_machine"],
        processor=cpu_projection["processor"],
        python_implementation=platform.python_implementation(),
        python_version=platform.python_version(),
        python_executable_sha256=executable_sha,
        python_executable_size_bytes=size,
        page_size_bytes=page_size,
        distribution_versions=_distribution_versions(),
        safe_environment=tuple(
            (name, os.environ.get(name, "<unset>"))
            for name in _SAFE_ENVIRONMENT_NAMES
        ),
        cpu_projection_sha256=_canonical_sha256(cpu_projection),
    )


def _read_current_rss_bytes() -> int:
    if platform.system() != "Linux":
        raise PoseBustersInternalOracleRuntimeObservationError(
            "sampled RSS observation requires Linux"
        )
    descriptor = os.open(
        "/proc/self/statm",
        os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    try:
        source = os.read(descriptor, 4097)
    finally:
        os.close(descriptor)
    if not source or len(source) > 4096 or b"\x00" in source:
        raise PoseBustersInternalOracleRuntimeObservationError(
            "Linux statm observation is outside its byte bound"
        )
    fields = source.split()
    try:
        resident_pages = int(fields[1], 10)
        page_size = os.sysconf("SC_PAGE_SIZE")
    except (IndexError, TypeError, ValueError) as exc:
        raise PoseBustersInternalOracleRuntimeObservationError(
            "Linux statm resident pages are invalid"
        ) from exc
    if (
        resident_pages < 1
        or not isinstance(page_size, int)
        or page_size < 1
    ):
        raise PoseBustersInternalOracleRuntimeObservationError(
            "Linux RSS observation is non-positive"
        )
    return resident_pages * page_size


@dataclass(frozen=True, slots=True)
class _RawCaseMeasurement:
    case_id: str
    wall_duration_ns: int
    rss_start_bytes: int
    rss_end_bytes: int
    sampled_peak_rss_bytes: int
    rss_sample_count: int


@dataclass(frozen=True, slots=True)
class _ExecutionMeasurement:
    batch_wall_duration_ns: int
    batch_rss_start_bytes: int
    batch_rss_end_bytes: int
    batch_sampled_peak_rss_bytes: int
    batch_rss_sample_count: int
    case_rows: tuple[_RawCaseMeasurement, ...]


@dataclass(slots=True)
class _ActiveCase:
    case_id: str
    started_ns: int
    rss_start_bytes: int
    sampled_peak_rss_bytes: int
    rss_sample_count: int


class _RuntimeMeasurementSession:
    def __init__(
        self,
        *,
        clock: Callable[[], int] | None = None,
        rss_reader: Callable[[], int] | None = None,
        sample_interval_ns: int = (
            POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_SAMPLE_INTERVAL_NS
        ),
    ) -> None:
        self._clock = time.perf_counter_ns if clock is None else clock
        self._rss_reader = (
            _read_current_rss_bytes if rss_reader is None else rss_reader
        )
        self._sample_interval_ns = _positive_int(
            sample_interval_ns,
            name="RSS sample interval",
        )
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._started_ns: int | None = None
        self._rss_start_bytes: int | None = None
        self._rss_end_bytes: int | None = None
        self._sampled_peak_rss_bytes = 0
        self._rss_sample_count = 0
        self._active_case: _ActiveCase | None = None
        self._case_rows: list[_RawCaseMeasurement] = []
        self._sampling_error: BaseException | None = None

    def _sample_locked(self) -> int:
        rss = _positive_int(self._rss_reader(), name="sampled process RSS")
        self._sampled_peak_rss_bytes = max(self._sampled_peak_rss_bytes, rss)
        self._rss_sample_count += 1
        if self._active_case is not None:
            self._active_case.sampled_peak_rss_bytes = max(
                self._active_case.sampled_peak_rss_bytes,
                rss,
            )
            self._active_case.rss_sample_count += 1
        return rss

    def _sample_loop(self) -> None:
        interval = self._sample_interval_ns / 1_000_000_000
        while not self._stop.wait(interval):
            try:
                with self._lock:
                    self._sample_locked()
            except BaseException as exc:
                with self._lock:
                    self._sampling_error = exc
                self._stop.set()
                return

    def _require_sampling_ok_locked(self) -> None:
        if self._sampling_error is not None:
            raise PoseBustersInternalOracleRuntimeObservationError(
                "background RSS sampling failed"
            ) from self._sampling_error

    def start(self) -> None:
        with self._lock:
            if self._started_ns is not None:
                raise PoseBustersInternalOracleRuntimeObservationError(
                    "runtime measurement session was already started"
                )
            self._started_ns = _nonnegative_int(
                self._clock(),
                name="batch start clock",
            )
            self._rss_start_bytes = self._sample_locked()
        self._thread = threading.Thread(
            target=self._sample_loop,
            name="posebusters-internal-oracle-rss-sampler",
            daemon=True,
        )
        self._thread.start()

    def case_started(self, case_id: str) -> None:
        case = _case_id(case_id)
        with self._lock:
            self._require_sampling_ok_locked()
            if self._started_ns is None or self._active_case is not None:
                raise PoseBustersInternalOracleRuntimeObservationError(
                    "runtime case observer start order is invalid"
                )
            started = _nonnegative_int(self._clock(), name="case start clock")
            rss = self._sample_locked()
            self._active_case = _ActiveCase(
                case_id=case,
                started_ns=started,
                rss_start_bytes=rss,
                sampled_peak_rss_bytes=rss,
                rss_sample_count=1,
            )

    def _finish_case_locked(self, case_id: str) -> None:
        case = _case_id(case_id)
        self._require_sampling_ok_locked()
        active = self._active_case
        if active is None or active.case_id != case:
            raise PoseBustersInternalOracleRuntimeObservationError(
                "runtime case observer finish order is invalid"
            )
        finished = _nonnegative_int(self._clock(), name="case finish clock")
        rss = self._sample_locked()
        if finished < active.started_ns:
            raise PoseBustersInternalOracleRuntimeObservationError(
                "case wall clock moved backwards"
            )
        self._case_rows.append(
            _RawCaseMeasurement(
                case_id=case,
                wall_duration_ns=finished - active.started_ns,
                rss_start_bytes=active.rss_start_bytes,
                rss_end_bytes=rss,
                sampled_peak_rss_bytes=max(active.sampled_peak_rss_bytes, rss),
                rss_sample_count=active.rss_sample_count,
            )
        )
        self._active_case = None

    def case_finished(self, row: PoseBustersInternalOracleCase) -> None:
        if not isinstance(row, PoseBustersInternalOracleCase):
            raise PoseBustersInternalOracleRuntimeObservationError(
                "runtime observer received an invalid oracle case"
            )
        with self._lock:
            self._finish_case_locked(row.case_id)

    def case_aborted(self, case_id: str) -> None:
        with self._lock:
            self._finish_case_locked(case_id)

    def _stop_thread(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=5.0)
            if thread.is_alive():
                raise PoseBustersInternalOracleRuntimeObservationError(
                    "RSS sampling thread did not stop"
                )

    def finish(self) -> _ExecutionMeasurement:
        self._stop_thread()
        with self._lock:
            self._require_sampling_ok_locked()
            if self._started_ns is None or self._active_case is not None:
                raise PoseBustersInternalOracleRuntimeObservationError(
                    "runtime measurement session is incomplete"
                )
            finished = _nonnegative_int(self._clock(), name="batch finish clock")
            self._rss_end_bytes = self._sample_locked()
            if finished < self._started_ns:
                raise PoseBustersInternalOracleRuntimeObservationError(
                    "batch wall clock moved backwards"
                )
            return _ExecutionMeasurement(
                batch_wall_duration_ns=finished - self._started_ns,
                batch_rss_start_bytes=self._rss_start_bytes or 0,
                batch_rss_end_bytes=self._rss_end_bytes,
                batch_sampled_peak_rss_bytes=self._sampled_peak_rss_bytes,
                batch_rss_sample_count=self._rss_sample_count,
                case_rows=tuple(self._case_rows),
            )

    def abort(self) -> None:
        self._stop_thread()
        with self._lock:
            self._active_case = None


@dataclass(frozen=True, slots=True)
class PoseBustersInternalOracleRuntimeCase:
    case_id: str
    oracle_status: str
    selected_pose_count: int
    oracle_attempted: bool
    wall_duration_ns: int
    rss_start_bytes: int
    rss_end_bytes: int
    sampled_peak_rss_bytes: int
    rss_sample_count: int
    schema_id: str = POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_CASE_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_CASE_SCHEMA_ID:
            raise PoseBustersInternalOracleRuntimeObservationError(
                "unsupported runtime case schema"
            )
        case = _case_id(self.case_id)
        status = _token(self.oracle_status, name="runtime oracle status")
        selected = _nonnegative_int(
            self.selected_pose_count,
            name="runtime selected pose count",
        )
        if not isinstance(self.oracle_attempted, bool):
            raise PoseBustersInternalOracleRuntimeObservationError(
                "runtime oracle-attempt flag must be boolean"
            )
        duration = _nonnegative_int(
            self.wall_duration_ns,
            name="case wall duration",
        )
        rss_start = _positive_int(self.rss_start_bytes, name="case start RSS")
        rss_end = _positive_int(self.rss_end_bytes, name="case end RSS")
        peak = _positive_int(
            self.sampled_peak_rss_bytes,
            name="case sampled peak RSS",
        )
        samples = _positive_int(self.rss_sample_count, name="case RSS sample count")
        if peak < max(rss_start, rss_end) or samples < 2:
            raise PoseBustersInternalOracleRuntimeObservationError(
                "case sampled RSS summary is inconsistent"
            )
        object.__setattr__(self, "case_id", case)
        object.__setattr__(self, "oracle_status", status)
        object.__setattr__(self, "selected_pose_count", selected)
        object.__setattr__(self, "wall_duration_ns", duration)
        object.__setattr__(self, "rss_start_bytes", rss_start)
        object.__setattr__(self, "rss_end_bytes", rss_end)
        object.__setattr__(self, "sampled_peak_rss_bytes", peak)
        object.__setattr__(self, "rss_sample_count", samples)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "case_id": self.case_id,
            "oracle_status": self.oracle_status,
            "selected_pose_count": self.selected_pose_count,
            "oracle_attempted": self.oracle_attempted,
            "wall_duration_ns": self.wall_duration_ns,
            "rss_start_bytes": self.rss_start_bytes,
            "rss_end_bytes": self.rss_end_bytes,
            "sampled_peak_rss_bytes": self.sampled_peak_rss_bytes,
            "rss_sample_count": self.rss_sample_count,
            "wall_clock_measured": True,
            "sampled_peak_rss_measured": True,
        }

    @classmethod
    def from_dict(
        cls,
        raw: Mapping[str, object],
    ) -> "PoseBustersInternalOracleRuntimeCase":
        return cls(
            case_id=raw.get("case_id"),  # type: ignore[arg-type]
            oracle_status=raw.get("oracle_status"),  # type: ignore[arg-type]
            selected_pose_count=raw.get("selected_pose_count"),  # type: ignore[arg-type]
            oracle_attempted=raw.get("oracle_attempted"),  # type: ignore[arg-type]
            wall_duration_ns=raw.get("wall_duration_ns"),  # type: ignore[arg-type]
            rss_start_bytes=raw.get("rss_start_bytes"),  # type: ignore[arg-type]
            rss_end_bytes=raw.get("rss_end_bytes"),  # type: ignore[arg-type]
            sampled_peak_rss_bytes=raw.get("sampled_peak_rss_bytes"),  # type: ignore[arg-type]
            rss_sample_count=raw.get("rss_sample_count"),  # type: ignore[arg-type]
            schema_id=raw.get("schema_id"),  # type: ignore[arg-type]
        )


@dataclass(frozen=True, slots=True)
class PoseBustersInternalOracleRuntimeObservationReceipt:
    oracle_receipt_sha256: str
    oracle_receipt_file_sha256: str
    oracle_runtime_identity_sha256: str
    oracle_case_projection_sha256: str
    engine_wheel_binding: PoseBustersInternalOracleRuntimeWheelBinding
    runtime_environment: PoseBustersInternalOracleRuntimeEnvironment
    implementation_source_sha256: str
    implementation_source_members: tuple[tuple[str, str], ...]
    configuration_sha256: str
    batch_wall_duration_ns: int
    batch_rss_start_bytes: int
    batch_rss_end_bytes: int
    batch_sampled_peak_rss_bytes: int
    batch_rss_sample_count: int
    case_rows: tuple[PoseBustersInternalOracleRuntimeCase, ...]
    schema_id: str = POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_OBSERVATION_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != (
            POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_OBSERVATION_SCHEMA_ID
        ):
            raise PoseBustersInternalOracleRuntimeObservationError(
                "unsupported runtime-observation schema"
            )
        for name in (
            "oracle_receipt_sha256",
            "oracle_receipt_file_sha256",
            "oracle_runtime_identity_sha256",
            "oracle_case_projection_sha256",
            "implementation_source_sha256",
            "configuration_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _digest(getattr(self, name), name=name),
            )
        if self.configuration_sha256 != (
            POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_CONFIGURATION_SHA256
        ):
            raise PoseBustersInternalOracleRuntimeObservationError(
                "runtime-observation configuration identity changed"
            )
        if not isinstance(
            self.engine_wheel_binding,
            PoseBustersInternalOracleRuntimeWheelBinding,
        ) or not isinstance(
            self.runtime_environment,
            PoseBustersInternalOracleRuntimeEnvironment,
        ):
            raise PoseBustersInternalOracleRuntimeObservationError(
                "runtime observation lacks wheel or environment identity"
            )
        members = tuple(
            (
                _token(role, name="runtime implementation role"),
                _digest(digest, name=f"{role} runtime source"),
            )
            for role, digest in self.implementation_source_members
        )
        if (
            tuple(sorted(members)) != members
            or members != self.engine_wheel_binding.source_members
            or self.implementation_source_sha256
            != _canonical_sha256(dict(members))
        ):
            raise PoseBustersInternalOracleRuntimeObservationError(
                "runtime implementation-source identity is invalid"
            )
        rows = tuple(self.case_rows)
        if (
            not rows
            or any(
                not isinstance(row, PoseBustersInternalOracleRuntimeCase)
                for row in rows
            )
            or tuple(row.case_id for row in rows)
            != tuple(sorted(row.case_id for row in rows))
            or len({row.case_id for row in rows}) != len(rows)
            or self.oracle_case_projection_sha256
            != _canonical_sha256([row.case_id for row in rows])
        ):
            raise PoseBustersInternalOracleRuntimeObservationError(
                "runtime case projection is invalid"
            )
        duration = _nonnegative_int(
            self.batch_wall_duration_ns,
            name="batch wall duration",
        )
        rss_start = _positive_int(self.batch_rss_start_bytes, name="batch start RSS")
        rss_end = _positive_int(self.batch_rss_end_bytes, name="batch end RSS")
        peak = _positive_int(
            self.batch_sampled_peak_rss_bytes,
            name="batch sampled peak RSS",
        )
        samples = _positive_int(
            self.batch_rss_sample_count,
            name="batch RSS sample count",
        )
        if (
            peak < max(rss_start, rss_end, *(row.sampled_peak_rss_bytes for row in rows))
            or samples < sum(row.rss_sample_count for row in rows)
            or duration < sum(row.wall_duration_ns for row in rows)
        ):
            raise PoseBustersInternalOracleRuntimeObservationError(
                "batch runtime/RSS summary is inconsistent"
            )
        object.__setattr__(self, "implementation_source_members", members)
        object.__setattr__(self, "case_rows", rows)
        object.__setattr__(self, "batch_wall_duration_ns", duration)
        object.__setattr__(self, "batch_rss_start_bytes", rss_start)
        object.__setattr__(self, "batch_rss_end_bytes", rss_end)
        object.__setattr__(self, "batch_sampled_peak_rss_bytes", peak)
        object.__setattr__(self, "batch_rss_sample_count", samples)

    def _payload(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "oracle_receipt_sha256": self.oracle_receipt_sha256,
            "oracle_receipt_file_sha256": self.oracle_receipt_file_sha256,
            "oracle_runtime_identity_sha256": (
                self.oracle_runtime_identity_sha256
            ),
            "oracle_case_projection_sha256": (
                self.oracle_case_projection_sha256
            ),
            "engine_wheel_binding": self.engine_wheel_binding.to_dict(),
            "engine_wheel_binding_sha256": (
                self.engine_wheel_binding.fingerprint_sha256
            ),
            "runtime_environment": self.runtime_environment.to_dict(),
            "runtime_environment_sha256": (
                self.runtime_environment.fingerprint_sha256
            ),
            "implementation_source_sha256": self.implementation_source_sha256,
            "implementation_source_members": dict(
                self.implementation_source_members
            ),
            "configuration": dict(
                POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_CONFIGURATION
            ),
            "configuration_sha256": self.configuration_sha256,
            "all_case_denominator": len(self.case_rows),
            "batch_wall_duration_ns": self.batch_wall_duration_ns,
            "batch_rss_start_bytes": self.batch_rss_start_bytes,
            "batch_rss_end_bytes": self.batch_rss_end_bytes,
            "batch_sampled_peak_rss_bytes": (
                self.batch_sampled_peak_rss_bytes
            ),
            "batch_rss_sample_count": self.batch_rss_sample_count,
            "case_wall_duration_total_ns": sum(
                row.wall_duration_ns for row in self.case_rows
            ),
            "case_wall_duration_min_ns": min(
                row.wall_duration_ns for row in self.case_rows
            ),
            "case_wall_duration_max_ns": max(
                row.wall_duration_ns for row in self.case_rows
            ),
            "case_sampled_peak_rss_max_bytes": max(
                row.sampled_peak_rss_bytes for row in self.case_rows
            ),
            "case_rows": [row.to_dict() for row in self.case_rows],
            "exact_oracle_reexecution_matched": True,
            "all_failure_rows_measured": True,
            "wall_clock_runtime_measurements_present": True,
            "sampled_peak_rss_measurements_present": True,
            "batch_full_chain_runtime_memory_measured": True,
            "per_case_posebusters_oracle_loop_runtime_memory_measured": True,
            "per_case_full_redocking_pipeline_runtime_memory_measured": False,
            "kernel_exact_case_peak_memory_measurements_present": False,
            "measurement_values_exactly_reexecutable": False,
            "operator_signature_present": False,
            "physical_host_identity_proven": False,
            "independent_second_host_observation_present": False,
            "benchmark_executed": False,
            "scientific_blockers": list(
                POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_BLOCKERS
            ),
            "scientifically_validated": False,
            "claim_safe": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self._payload())

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "receipt_sha256": self.fingerprint_sha256}

    def write_json(self, output_path: str | os.PathLike[str]) -> Path:
        output = Path(output_path)
        output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        payload = _canonical_bytes(self.to_dict()) + b"\n"
        if len(payload) > POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_MAX_RECEIPT_BYTES:
            raise PoseBustersInternalOracleRuntimeObservationError(
                "runtime-observation receipt exceeds its byte bound"
            )
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{output.name}.",
            suffix=".tmp",
            dir=str(output.parent),
        )
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary_name, output, follow_symlinks=False)
            except FileExistsError as exc:
                raise PoseBustersInternalOracleRuntimeObservationError(
                    "runtime-observation receipt output already exists"
                ) from exc
        finally:
            try:
                os.close(descriptor)
            except OSError:
                pass
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
        return output


def _runtime_case(
    oracle: PoseBustersInternalOracleCase,
    measured: _RawCaseMeasurement,
) -> PoseBustersInternalOracleRuntimeCase:
    if oracle.case_id != measured.case_id:
        raise PoseBustersInternalOracleRuntimeObservationError(
            "runtime measurement is cross-wired to another oracle case"
        )
    return PoseBustersInternalOracleRuntimeCase(
        case_id=oracle.case_id,
        oracle_status=oracle.status,
        selected_pose_count=oracle.selected_pose_count,
        oracle_attempted=oracle.oracle_attempted,
        wall_duration_ns=measured.wall_duration_ns,
        rss_start_bytes=measured.rss_start_bytes,
        rss_end_bytes=measured.rss_end_bytes,
        sampled_peak_rss_bytes=measured.sampled_peak_rss_bytes,
        rss_sample_count=measured.rss_sample_count,
    )


def _require_oracle_binding(
    receipt: PoseBustersInternalOracleRuntimeObservationReceipt,
    oracle: PoseBustersInternalOracleEvaluationReceipt,
    oracle_source: bytes,
) -> None:
    if (
        receipt.oracle_receipt_sha256 != oracle.fingerprint_sha256
        or receipt.oracle_receipt_file_sha256 != _hash_bytes(oracle_source)
        or receipt.oracle_runtime_identity_sha256
        != oracle.runtime_identity.fingerprint_sha256
        or receipt.oracle_case_projection_sha256
        != _canonical_sha256([row.case_id for row in oracle.case_rows])
        or tuple(
            (
                row.case_id,
                row.oracle_status,
                row.selected_pose_count,
                row.oracle_attempted,
            )
            for row in receipt.case_rows
        )
        != tuple(
            (
                row.case_id,
                row.status,
                row.selected_pose_count,
                row.oracle_attempted,
            )
            for row in oracle.case_rows
        )
    ):
        raise PoseBustersInternalOracleRuntimeObservationError(
            "runtime observation is cross-wired to another oracle receipt"
        )


def _implementation_source_sha256(
    members: tuple[tuple[str, str], ...],
) -> str:
    return _canonical_sha256(dict(members))


def materialize_posebusters_internal_oracle_runtime_observation(
    oracle_receipt_path: str | os.PathLike[str],
    internal_rmsd_receipt_path: str | os.PathLike[str],
    execution_receipt_path: str | os.PathLike[str],
    execution_artifact_root: str | os.PathLike[str],
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    archive_path: str | os.PathLike[str],
    selection_path: str | os.PathLike[str],
    intake_receipt_path: str | os.PathLike[str],
    corpus_audit_receipt_path: str | os.PathLike[str],
    posebusters_wheel_path: str | os.PathLike[str],
    engine_wheel_path: str | os.PathLike[str],
    scratch_root: str | os.PathLike[str],
    *,
    expected_oracle_receipt_sha256: str,
    expected_internal_rmsd_receipt_sha256: str,
    expected_engine_wheel_sha256: str,
    contract: PoseBustersArchiveContract = OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT,
    preparation_configuration: PoseBustersInternalPreparationConfig | None = None,
    execution_configuration: PoseBustersInternalExecutionConfig | None = None,
    rmsd_configuration: PoseBustersInternalRMSDConfig | None = None,
) -> PoseBustersInternalOracleRuntimeObservationReceipt:
    """Measure one exact internal-oracle reexecution without changing it."""

    expected_oracle_sha = _digest(
        expected_oracle_receipt_sha256,
        name="expected internal-oracle receipt",
    )
    if (
        _canonical_sha256(POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_CONFIGURATION)
        != POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_CONFIGURATION_SHA256
    ):
        raise PoseBustersInternalOracleRuntimeObservationError(
            "runtime-observation frozen configuration was mutated"
        )
    wheel = _engine_wheel_binding(
        engine_wheel_path,
        expected_sha256=expected_engine_wheel_sha256,
    )
    environment = _observe_runtime_environment()
    session = _RuntimeMeasurementSession()
    session.start()
    try:
        oracle = _verify_posebusters_internal_oracle_evaluation_receipt(
            oracle_receipt_path,
            internal_rmsd_receipt_path,
            execution_receipt_path,
            execution_artifact_root,
            preparation_receipt_path,
            preparation_artifact_root,
            archive_path,
            selection_path,
            intake_receipt_path,
            corpus_audit_receipt_path,
            posebusters_wheel_path,
            scratch_root,
            expected_internal_rmsd_receipt_sha256=(
                expected_internal_rmsd_receipt_sha256
            ),
            contract=contract,
            preparation_configuration=preparation_configuration,
            execution_configuration=execution_configuration,
            rmsd_configuration=rmsd_configuration,
            case_observer=session,
        )
    except BaseException:
        try:
            session.abort()
        except BaseException:
            pass
        raise
    measured = session.finish()
    if oracle.fingerprint_sha256 != expected_oracle_sha:
        raise PoseBustersInternalOracleRuntimeObservationError(
            "observed oracle receipt differs from the expected input"
        )
    oracle_source = _read_exact_regular_file(
        oracle_receipt_path,
        maximum_bytes=POSEBUSTERS_INTERNAL_ORACLE_MAX_RECEIPT_BYTES,
    )
    if oracle_source != _canonical_bytes(oracle.to_dict()) + b"\n":
        raise PoseBustersInternalOracleRuntimeObservationError(
            "oracle receipt changed after measured exact reexecution"
        )
    if len(measured.case_rows) != len(oracle.case_rows):
        raise PoseBustersInternalOracleRuntimeObservationError(
            "runtime observer omitted an all-case row"
        )
    case_rows = tuple(
        _runtime_case(oracle_row, measured_row)
        for oracle_row, measured_row in zip(
            oracle.case_rows,
            measured.case_rows,
            strict=True,
        )
    )
    members = _current_source_members()
    receipt = PoseBustersInternalOracleRuntimeObservationReceipt(
        oracle_receipt_sha256=oracle.fingerprint_sha256,
        oracle_receipt_file_sha256=_hash_bytes(oracle_source),
        oracle_runtime_identity_sha256=(
            oracle.runtime_identity.fingerprint_sha256
        ),
        oracle_case_projection_sha256=_canonical_sha256(
            [row.case_id for row in oracle.case_rows]
        ),
        engine_wheel_binding=wheel,
        runtime_environment=environment,
        implementation_source_sha256=_implementation_source_sha256(members),
        implementation_source_members=members,
        configuration_sha256=(
            POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_CONFIGURATION_SHA256
        ),
        batch_wall_duration_ns=measured.batch_wall_duration_ns,
        batch_rss_start_bytes=measured.batch_rss_start_bytes,
        batch_rss_end_bytes=measured.batch_rss_end_bytes,
        batch_sampled_peak_rss_bytes=measured.batch_sampled_peak_rss_bytes,
        batch_rss_sample_count=measured.batch_rss_sample_count,
        case_rows=case_rows,
    )
    _require_oracle_binding(receipt, oracle, oracle_source)
    return receipt


def _json_object_pairs(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise PoseBustersInternalOracleRuntimeObservationError(
                "runtime-observation receipt contains a duplicate JSON key"
            )
        result[key] = value
    return result


def _reject_json_constant(value: str) -> object:
    raise PoseBustersInternalOracleRuntimeObservationError(
        f"runtime-observation receipt contains forbidden JSON constant {value}"
    )


def _load_runtime_observation_receipt(
    receipt_path: str | os.PathLike[str],
) -> PoseBustersInternalOracleRuntimeObservationReceipt:
    try:
        metadata = Path(receipt_path).stat(follow_symlinks=False)
    except OSError as exc:
        raise PoseBustersInternalOracleRuntimeObservationError(
            "runtime-observation receipt metadata is unavailable"
        ) from exc
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise PoseBustersInternalOracleRuntimeObservationError(
            "runtime-observation receipt must remain mode 0600"
        )
    source = _read_exact_regular_file(
        receipt_path,
        maximum_bytes=POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_MAX_RECEIPT_BYTES,
    )
    try:
        raw = json.loads(
            source.decode("ascii"),
            object_pairs_hook=_json_object_pairs,
            parse_constant=_reject_json_constant,
        )
    except PoseBustersInternalOracleRuntimeObservationError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PoseBustersInternalOracleRuntimeObservationError(
            "runtime-observation receipt must be ASCII JSON"
        ) from exc
    document = _mapping(raw, name="runtime-observation receipt")
    rows = tuple(
        PoseBustersInternalOracleRuntimeCase.from_dict(
            _mapping(item, name="runtime-observation case")
        )
        for item in _list(document.get("case_rows"), name="runtime case rows")
    )
    members = _mapping(
        document.get("implementation_source_members"),
        name="runtime implementation members",
    )
    receipt = PoseBustersInternalOracleRuntimeObservationReceipt(
        oracle_receipt_sha256=document.get("oracle_receipt_sha256"),  # type: ignore[arg-type]
        oracle_receipt_file_sha256=document.get("oracle_receipt_file_sha256"),  # type: ignore[arg-type]
        oracle_runtime_identity_sha256=document.get("oracle_runtime_identity_sha256"),  # type: ignore[arg-type]
        oracle_case_projection_sha256=document.get("oracle_case_projection_sha256"),  # type: ignore[arg-type]
        engine_wheel_binding=(
            PoseBustersInternalOracleRuntimeWheelBinding.from_dict(
                _mapping(
                    document.get("engine_wheel_binding"),
                    name="runtime engine wheel binding",
                )
            )
        ),
        runtime_environment=(
            PoseBustersInternalOracleRuntimeEnvironment.from_dict(
                _mapping(
                    document.get("runtime_environment"),
                    name="runtime environment",
                )
            )
        ),
        implementation_source_sha256=document.get("implementation_source_sha256"),  # type: ignore[arg-type]
        implementation_source_members=tuple(members.items()),  # type: ignore[arg-type]
        configuration_sha256=document.get("configuration_sha256"),  # type: ignore[arg-type]
        batch_wall_duration_ns=document.get("batch_wall_duration_ns"),  # type: ignore[arg-type]
        batch_rss_start_bytes=document.get("batch_rss_start_bytes"),  # type: ignore[arg-type]
        batch_rss_end_bytes=document.get("batch_rss_end_bytes"),  # type: ignore[arg-type]
        batch_sampled_peak_rss_bytes=document.get("batch_sampled_peak_rss_bytes"),  # type: ignore[arg-type]
        batch_rss_sample_count=document.get("batch_rss_sample_count"),  # type: ignore[arg-type]
        case_rows=rows,
        schema_id=document.get("schema_id"),  # type: ignore[arg-type]
    )
    if source != _canonical_bytes(receipt.to_dict()) + b"\n":
        raise PoseBustersInternalOracleRuntimeObservationError(
            "runtime-observation receipt is not canonical or self-authenticating"
        )
    return receipt


def verify_posebusters_internal_oracle_runtime_observation_receipt(
    runtime_observation_receipt_path: str | os.PathLike[str],
    oracle_receipt_path: str | os.PathLike[str],
    internal_rmsd_receipt_path: str | os.PathLike[str],
    execution_receipt_path: str | os.PathLike[str],
    execution_artifact_root: str | os.PathLike[str],
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    archive_path: str | os.PathLike[str],
    selection_path: str | os.PathLike[str],
    intake_receipt_path: str | os.PathLike[str],
    corpus_audit_receipt_path: str | os.PathLike[str],
    posebusters_wheel_path: str | os.PathLike[str],
    engine_wheel_path: str | os.PathLike[str],
    scratch_root: str | os.PathLike[str],
    *,
    expected_runtime_observation_receipt_sha256: str,
    expected_oracle_receipt_sha256: str,
    expected_internal_rmsd_receipt_sha256: str,
    expected_engine_wheel_sha256: str,
    contract: PoseBustersArchiveContract = OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT,
    preparation_configuration: PoseBustersInternalPreparationConfig | None = None,
    execution_configuration: PoseBustersInternalExecutionConfig | None = None,
    rmsd_configuration: PoseBustersInternalRMSDConfig | None = None,
) -> PoseBustersInternalOracleRuntimeObservationReceipt:
    """Verify the measured companion and reexecute its deterministic oracle."""

    expected_observation_sha = _digest(
        expected_runtime_observation_receipt_sha256,
        name="expected runtime-observation receipt",
    )
    expected_oracle_sha = _digest(
        expected_oracle_receipt_sha256,
        name="expected internal-oracle receipt",
    )
    receipt = _load_runtime_observation_receipt(
        runtime_observation_receipt_path
    )
    if receipt.fingerprint_sha256 != expected_observation_sha:
        raise PoseBustersInternalOracleRuntimeObservationError(
            "runtime-observation receipt differs from its expected identity"
        )
    wheel = _engine_wheel_binding(
        engine_wheel_path,
        expected_sha256=expected_engine_wheel_sha256,
    )
    if wheel.to_dict() != receipt.engine_wheel_binding.to_dict():
        raise PoseBustersInternalOracleRuntimeObservationError(
            "runtime-observation engine wheel binding changed"
        )
    members = _current_source_members()
    if (
        members != receipt.implementation_source_members
        or _implementation_source_sha256(members)
        != receipt.implementation_source_sha256
    ):
        raise PoseBustersInternalOracleRuntimeObservationError(
            "runtime-observation implementation source changed"
        )
    oracle = verify_posebusters_internal_oracle_evaluation_receipt(
        oracle_receipt_path,
        internal_rmsd_receipt_path,
        execution_receipt_path,
        execution_artifact_root,
        preparation_receipt_path,
        preparation_artifact_root,
        archive_path,
        selection_path,
        intake_receipt_path,
        corpus_audit_receipt_path,
        posebusters_wheel_path,
        scratch_root,
        expected_internal_rmsd_receipt_sha256=(
            expected_internal_rmsd_receipt_sha256
        ),
        contract=contract,
        preparation_configuration=preparation_configuration,
        execution_configuration=execution_configuration,
        rmsd_configuration=rmsd_configuration,
    )
    if oracle.fingerprint_sha256 != expected_oracle_sha:
        raise PoseBustersInternalOracleRuntimeObservationError(
            "verified oracle receipt differs from the expected input"
        )
    oracle_source = _read_exact_regular_file(
        oracle_receipt_path,
        maximum_bytes=POSEBUSTERS_INTERNAL_ORACLE_MAX_RECEIPT_BYTES,
    )
    if oracle_source != _canonical_bytes(oracle.to_dict()) + b"\n":
        raise PoseBustersInternalOracleRuntimeObservationError(
            "oracle receipt changed after exact verification"
        )
    _require_oracle_binding(receipt, oracle, oracle_source)
    return receipt


def _add_common_arguments(command: argparse.ArgumentParser) -> None:
    command.add_argument("--oracle-receipt", required=True)
    command.add_argument("--internal-rmsd-receipt", required=True)
    command.add_argument("--execution-receipt", required=True)
    command.add_argument("--execution-artifact-root", required=True)
    command.add_argument("--preparation-receipt", required=True)
    command.add_argument("--preparation-artifact-root", required=True)
    command.add_argument("--archive", required=True)
    command.add_argument("--selection", required=True)
    command.add_argument("--intake-receipt", required=True)
    command.add_argument("--corpus-audit-receipt", required=True)
    command.add_argument("--posebusters-wheel", required=True)
    command.add_argument("--engine-wheel", required=True)
    command.add_argument("--scratch-root", required=True)
    command.add_argument("--expected-oracle-receipt-sha256", required=True)
    command.add_argument(
        "--expected-internal-rmsd-receipt-sha256",
        required=True,
    )
    command.add_argument("--expected-engine-wheel-sha256", required=True)
    command.add_argument("--candidate-count", type=int, default=64)
    command.add_argument("--search-top-k", type=int, default=10)
    command.add_argument("--max-torsions", type=int, default=32)
    command.add_argument("--translation-radius", type=float, default=4.0)
    command.add_argument("--diversity-rmsd", type=float, default=0.5)
    command.add_argument("--max-refinement-steps", type=int, default=6)
    command.add_argument("--base-seed", type=int, default=7_301)
    command.add_argument("--rmsd-threshold", type=float, default=2.0)
    command.add_argument("--evaluation-top-k", type=int, default=5)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2-posebusters-internal-oracle-runtime",
        description=(
            "Measure all-case wall time and sampled RSS for an exact internal "
            "PoseBusters-oracle reexecution."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    materialize = subparsers.add_parser("materialize")
    verify = subparsers.add_parser("verify")
    _add_common_arguments(materialize)
    _add_common_arguments(verify)
    materialize.add_argument("--receipt", required=True)
    verify.add_argument("--receipt", required=True)
    verify.add_argument(
        "--expected-runtime-observation-receipt-sha256",
        required=True,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    execution_configuration = PoseBustersInternalExecutionConfig(
        candidate_count=args.candidate_count,
        top_k=args.search_top_k,
        max_torsions=args.max_torsions,
        translation_radius_angstrom=args.translation_radius,
        diversity_rmsd_angstrom=args.diversity_rmsd,
        max_refinement_steps=args.max_refinement_steps,
        base_seed=args.base_seed,
    )
    rmsd_configuration = PoseBustersInternalRMSDConfig(
        rmsd_threshold_angstrom=args.rmsd_threshold,
        top_k=args.evaluation_top_k,
    )
    common = {
        "oracle_receipt_path": args.oracle_receipt,
        "internal_rmsd_receipt_path": args.internal_rmsd_receipt,
        "execution_receipt_path": args.execution_receipt,
        "execution_artifact_root": args.execution_artifact_root,
        "preparation_receipt_path": args.preparation_receipt,
        "preparation_artifact_root": args.preparation_artifact_root,
        "archive_path": args.archive,
        "selection_path": args.selection,
        "intake_receipt_path": args.intake_receipt,
        "corpus_audit_receipt_path": args.corpus_audit_receipt,
        "posebusters_wheel_path": args.posebusters_wheel,
        "engine_wheel_path": args.engine_wheel,
        "scratch_root": args.scratch_root,
        "expected_oracle_receipt_sha256": (
            args.expected_oracle_receipt_sha256
        ),
        "expected_internal_rmsd_receipt_sha256": (
            args.expected_internal_rmsd_receipt_sha256
        ),
        "expected_engine_wheel_sha256": args.expected_engine_wheel_sha256,
        "execution_configuration": execution_configuration,
        "rmsd_configuration": rmsd_configuration,
    }
    if args.command == "materialize":
        if Path(args.receipt).exists():
            raise PoseBustersInternalOracleRuntimeObservationError(
                "runtime-observation receipt output already exists"
            )
        receipt = materialize_posebusters_internal_oracle_runtime_observation(
            **common
        )
        receipt.write_json(args.receipt)
    else:
        receipt = (
            verify_posebusters_internal_oracle_runtime_observation_receipt(
                runtime_observation_receipt_path=args.receipt,
                expected_runtime_observation_receipt_sha256=(
                    args.expected_runtime_observation_receipt_sha256
                ),
                **common,
            )
        )
    print(
        json.dumps(
            {
                "receipt_sha256": receipt.fingerprint_sha256,
                "all_case_denominator": len(receipt.case_rows),
                "batch_wall_duration_ns": receipt.batch_wall_duration_ns,
                "batch_sampled_peak_rss_bytes": (
                    receipt.batch_sampled_peak_rss_bytes
                ),
                "benchmark_executed": False,
                "claim_safe": False,
            },
            sort_keys=True,
        )
    )
    return 0


__all__ = [
    "POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_BLOCKERS",
    "POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_CASE_SCHEMA_ID",
    "POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_CONFIGURATION",
    "POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_CONFIGURATION_SHA256",
    "POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_ENVIRONMENT_SCHEMA_ID",
    "POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_MAX_RECEIPT_BYTES",
    "POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_OBSERVATION_SCHEMA_ID",
    "POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_SAMPLE_INTERVAL_NS",
    "POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_WHEEL_SCHEMA_ID",
    "PoseBustersInternalOracleRuntimeCase",
    "PoseBustersInternalOracleRuntimeEnvironment",
    "PoseBustersInternalOracleRuntimeObservationError",
    "PoseBustersInternalOracleRuntimeObservationReceipt",
    "PoseBustersInternalOracleRuntimeWheelBinding",
    "main",
    "materialize_posebusters_internal_oracle_runtime_observation",
    "verify_posebusters_internal_oracle_runtime_observation_receipt",
]


if __name__ == "__main__":
    raise SystemExit(main())
