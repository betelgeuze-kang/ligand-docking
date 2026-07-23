"""Failure-inclusive same-input GNINA and Smina execution receipts.

The runner consumes the exact strict PoseBusters preparation receipt and its
private PDBQT artifact tree.  It accepts only pinned official GNINA or Smina
executables, freezes the common search inputs and every engine-specific option,
retains every generated pose score and every blocked or failed case, and writes
private no-overwrite artifacts.  It does not evaluate pose validity or RMSD and
does not promote the 18-case prepared subset to a public docking benchmark.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import platform
import re
import resource
import stat
import subprocess
import tempfile
from typing import Any, Protocol, Sequence

from .public_posebusters_corpus_audit import (
    _canonical_bytes,
    _canonical_sha256,
    _positive_int,
    _source_file_sha256,
    _token,
)
from .public_posebusters_external_preparation import (
    PoseBustersExternalPreparationError,
    _verify_artifact_tree,
    _write_artifact_tree,
)
from .public_posebusters_intake import _read_exact_regular_file
from .public_posebusters_vina_execution import (
    PoseBustersVinaExecutionError,
    _PreparedCaseView,
    _case_id,
    _digest,
    _identifier,
    _load_preparation_receipt,
    _normalize_error,
    _validate_hex,
)


POSEBUSTERS_EXTERNAL_BINARY_DEPENDENCY_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_external_binary_dependency/1.0.0"
)
POSEBUSTERS_EXTERNAL_BINARY_RUNTIME_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_external_binary_runtime/1.0.0"
)
POSEBUSTERS_EXTERNAL_BINARY_SCORE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_external_binary_score/1.0.0"
)
POSEBUSTERS_EXTERNAL_BINARY_ARTIFACT_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_external_binary_artifact/1.0.0"
)
POSEBUSTERS_EXTERNAL_BINARY_CASE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_external_binary_case/1.0.0"
)
POSEBUSTERS_EXTERNAL_BINARY_METRIC_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_external_binary_metric/1.0.0"
)
POSEBUSTERS_EXTERNAL_BINARY_EXECUTION_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_external_binary_execution/1.0.0"
)

POSEBUSTERS_EXTERNAL_BINARY_ENGINES = ("gnina", "smina")
POSEBUSTERS_EXTERNAL_BINARY_MAX_EXECUTABLE_BYTES = 3 * 1024 * 1024 * 1024
POSEBUSTERS_EXTERNAL_BINARY_MAX_LIBRARY_BYTES = 2 * 1024 * 1024 * 1024
POSEBUSTERS_EXTERNAL_BINARY_MAX_POSE_ARTIFACT_BYTES = 32 * 1024 * 1024
POSEBUSTERS_EXTERNAL_BINARY_MAX_DIAGNOSTIC_BYTES = 4 * 1024 * 1024
POSEBUSTERS_EXTERNAL_BINARY_MAX_RECEIPT_BYTES = 32 * 1024 * 1024
POSEBUSTERS_EXTERNAL_BINARY_TIMEOUT_SECONDS = 30 * 60
POSEBUSTERS_EXTERNAL_BINARY_CPU_LIMIT_SECONDS = 30 * 60
POSEBUSTERS_EXTERNAL_BINARY_CONFIDENCE_LEVEL = 0.95
POSEBUSTERS_EXTERNAL_BINARY_Z = 1.959963984540054

_ENGINE_SPECS: dict[str, dict[str, Any]] = {
    "gnina": {
        "version": "1.3.3",
        "version_output": "gnina v1.3.3 master:6fe1ce2 Built Jun 30 2026.",
        "executable_sha256": (
            "3340c1f49cd3c7c84d8699182a1c6af13c7fa2a22448d1204640446106f72172"
        ),
        "executable_size_bytes": 2_056_131_000,
        "source_url": (
            "https://github.com/gnina/gnina/releases/download/"
            "v1.3.3/gnina.cuda12.8.static"
        ),
        "source_release_date": "2026-06-29",
        "score_components": (
            "minimized_affinity_kcal_per_mol",
            "cnn_pose_score",
            "cnn_affinity",
        ),
        "dynamic": True,
    },
    "smina": {
        "version": "2019-10-15",
        "version_output": ("Smina Oct 15 2019. Based on AutoDock Vina 1.1.2."),
        "executable_sha256": (
            "ffe5e1e78c947f76b0df8805e2c54383d0bbaf2e827a633b643a708cf682a958"
        ),
        "executable_size_bytes": 9_853_920,
        "source_url": (
            "https://sourceforge.net/projects/smina/files/smina.static/download"
        ),
        "source_release_date": "2019-10-15",
        "score_components": ("minimized_affinity_kcal_per_mol",),
        "dynamic": False,
    },
}

_GNINA_REQUIRED_LIBRARIES = (
    "ld-linux-x86-64.so.2",
    "libc.so.6",
    "libcublas.so.12",
    "libcublasLt.so.12",
    "libcudart.so.12",
    "libcudnn.so.9",
    "libcufft.so.11",
    "libcusolver.so.11",
    "libcusparse.so.12",
    "libdl.so.2",
    "libgcc_s.so.1",
    "libm.so.6",
    "libnvJitLink.so.12",
    "libpthread.so.0",
    "librt.so.1",
    "libstdc++.so.6",
)

POSEBUSTERS_EXTERNAL_BINARY_COMMON_CONFIGURATION = {
    "box_size_angstrom": [22.5, 22.5, 22.5],
    "cpu_count": 1,
    "diagnostic_absolute_path_normalization": True,
    "exhaustiveness": 32,
    "explicit_empirical_scoring": "vina",
    "failure_taxonomy_version": "external_binary_failure_taxonomy/1.0.0",
    "maximum_output_modes": 20,
    "minimum_mode_rmsd_angstrom": 1.0,
    "native_reference_use": "pocket_center_only_from_preparation_receipt",
    "prepared_ligand_hydrogen_addition": False,
    "random_seed": 20260723,
}
POSEBUSTERS_EXTERNAL_BINARY_CONFIGURATIONS = {
    "gnina": {
        **POSEBUSTERS_EXTERNAL_BINARY_COMMON_CONFIGURATION,
        "cnn_scoring": "rescore",
        "diagnostic_timing_normalization": [],
        "energy_range_kcal_per_mol": None,
        "energy_range_option_supported": False,
        "gpu_enabled": False,
        "pose_sort_order": "CNNscore",
        "score_component_order": list(_ENGINE_SPECS["gnina"]["score_components"]),
    },
    "smina": {
        **POSEBUSTERS_EXTERNAL_BINARY_COMMON_CONFIGURATION,
        "cnn_scoring": None,
        "diagnostic_timing_normalization": ["Refine time", "Loop time"],
        "energy_range_kcal_per_mol": 20.0,
        "energy_range_option_supported": True,
        "gpu_enabled": False,
        "pose_sort_order": "minimized_affinity",
        "score_component_order": list(_ENGINE_SPECS["smina"]["score_components"]),
    },
}
POSEBUSTERS_EXTERNAL_BINARY_CONFIGURATION_SHA256 = {
    "gnina": "91f33547f6e3dc5a58a00a89134d79f2538b5ba28fec8dd8b1d24eba80b77965",
    "smina": "925b343a60b607e033ad9129b16f45b192f0d36123e797e4b1fa9ccfbb323f3c",
}

POSEBUSTERS_EXTERNAL_BINARY_BLOCKERS = (
    "only_strictly_prepared_chemistry_subset_executed",
    "prepared_ad4_types_and_gasteiger_charges_not_independently_validated",
    "gnina_energy_range_option_not_supported",
    "generated_pose_validity_and_rmsd_not_yet_evaluated",
    "target_family_and_leakage_receipts_missing",
    "independent_external_host_rerun_missing",
    "independent_scientific_review_missing",
    "public_docking_benchmark_claim_not_authorized",
)

_PREPARATION_STATUSES = {
    "prepared",
    "preparation_failure",
    "upstream_failure",
    "abstain_chemistry_scope",
}
_CASE_STATUSES = {
    "success",
    "engine_failure",
    "blocked_preparation_failure",
    "blocked_upstream_failure",
    "abstain_chemistry_scope",
}
_SHA256_CHARACTERS = frozenset("0123456789abcdef")
_MODEL_LINE = re.compile(r"^MODEL ([1-9][0-9]*)$")
_SCORE_LINE = re.compile(
    r"^REMARK (minimizedAffinity|CNNscore|CNNaffinity) "
    r"([+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[Ee][+-]?[0-9]+)?)$"
)
_SMINA_TIMING_LINE = re.compile(rb"(?m)^(Refine time|Loop time) [0-9]+(?:\.[0-9]+)?$")
_UNSUPPORTED_AUTODOCK_ATOM_TYPE = re.compile(
    rb'Parse error on line [1-9][0-9]* in file "[^"]+": ATOM syntax '
    rb'incorrect: "([A-Za-z0-9]{1,16})" is not a valid AutoDock type\.'
)
_LDD_ARROW_LINE = re.compile(r"^\s*(\S+)\s+=>\s+(\S+)\s+\(0x[0-9a-fA-F]+\)\s*$")
_LDD_LOADER_LINE = re.compile(r"^\s*(/\S+)\s+\(0x[0-9a-fA-F]+\)\s*$")


class PoseBustersExternalBinaryExecutionError(ValueError):
    """External binary identity, input, execution, or receipt is invalid."""


class PoseBustersExternalBinaryCaseError(RuntimeError):
    """One prepared case failed during bounded external execution."""

    def __init__(
        self,
        *,
        stage: str,
        error_code: str,
        error_type: str,
        error_message_sha256: str,
        diagnostic_sha256: str,
        diagnostic_size_bytes: int,
    ) -> None:
        super().__init__(error_code)
        self.stage = _token(stage, name="external binary failure stage")
        self.error_code = _token(error_code, name="external binary error code")
        self.error_type = _identifier(
            error_type,
            name="external binary error type",
        )
        self.error_message_sha256 = _digest(
            error_message_sha256,
            name="external binary error message",
        )
        self.diagnostic_sha256 = _digest(
            diagnostic_sha256,
            name="external binary diagnostic",
        )
        self.diagnostic_size_bytes = _positive_int(
            diagnostic_size_bytes,
            name="external binary diagnostic size",
            allow_zero=True,
        )


def _hash_bytes(source: bytes) -> str:
    return hashlib.sha256(source).hexdigest()


def _classified_execution_failure(
    engine_id: str,
    returncode: int,
    diagnostic: bytes,
) -> PoseBustersExternalBinaryCaseError:
    engine = _engine_id(engine_id)
    unsupported_type = _UNSUPPORTED_AUTODOCK_ATOM_TYPE.search(diagnostic)
    if unsupported_type is not None:
        atom_type = unsupported_type.group(1)
        return PoseBustersExternalBinaryCaseError(
            stage="engine_input_validation",
            error_code=f"{engine}_unsupported_prepared_autodock_atom_type",
            error_type="UnsupportedPreparedAutoDockAtomType",
            error_message_sha256=_hash_bytes(
                f"returncode:{returncode};atom_type:".encode("ascii") + atom_type
            ),
            diagnostic_sha256=_hash_bytes(diagnostic),
            diagnostic_size_bytes=len(diagnostic),
        )
    return PoseBustersExternalBinaryCaseError(
        stage="engine_execution",
        error_code=f"{engine}_execution_failed",
        error_type="CalledProcessError",
        error_message_sha256=_hash_bytes(f"returncode:{returncode}".encode("ascii")),
        diagnostic_sha256=_hash_bytes(diagnostic),
        diagnostic_size_bytes=len(diagnostic),
    )


def _bounded_text(value: object, *, name: str) -> str:
    if not isinstance(value, str):
        raise PoseBustersExternalBinaryExecutionError(f"{name} must be text")
    result = " ".join(value.split())
    if not result or len(result.encode("utf-8")) > 4096 or "\x00" in result:
        raise PoseBustersExternalBinaryExecutionError(
            f"{name} must be bounded non-empty text"
        )
    return result


def _engine_id(value: object) -> str:
    engine = _token(value, name="external binary engine")
    if engine not in POSEBUSTERS_EXTERNAL_BINARY_ENGINES:
        raise PoseBustersExternalBinaryExecutionError(
            "external binary engine must be gnina or smina"
        )
    return engine


def _hash_regular_file(
    path: Path,
    *,
    maximum_bytes: int,
    require_executable: bool = False,
) -> tuple[str, int]:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise PoseBustersExternalBinaryExecutionError(
            "external binary payload is unavailable"
        ) from exc
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or metadata.st_size < 1
        or metadata.st_size > maximum_bytes
        or (require_executable and not metadata.st_mode & 0o111)
    ):
        raise PoseBustersExternalBinaryExecutionError(
            "external binary payload is not a bounded executable regular file"
        )
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    descriptor = os.open(path, flags)
    digest = hashlib.sha256()
    observed = 0
    try:
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            observed += len(chunk)
            if observed > maximum_bytes:
                raise PoseBustersExternalBinaryExecutionError(
                    "external binary payload exceeds its byte bound"
                )
            digest.update(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if (
        observed != metadata.st_size
        or after.st_dev != metadata.st_dev
        or after.st_ino != metadata.st_ino
        or after.st_size != metadata.st_size
    ):
        raise PoseBustersExternalBinaryExecutionError(
            "external binary payload changed while hashing"
        )
    return digest.hexdigest(), observed


def _read_bounded_regular_file(path: Path, *, maximum_bytes: int) -> bytes:
    try:
        source = _read_exact_regular_file(path, maximum_bytes=maximum_bytes)
    except Exception as exc:
        raise PoseBustersExternalBinaryExecutionError(
            "external binary output is missing, unsafe, or oversized"
        ) from exc
    if not source or b"\x00" in source:
        raise PoseBustersExternalBinaryExecutionError(
            "external binary output must be non-empty text bytes"
        )
    return source


def _private_scratch_root(path: Path) -> Path:
    try:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        metadata = path.lstat()
    except OSError as exc:
        raise PoseBustersExternalBinaryExecutionError(
            "external binary scratch root is unavailable"
        ) from exc
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o700
    ):
        raise PoseBustersExternalBinaryExecutionError(
            "external binary scratch root must be a private real directory"
        )
    return path


def _write_private_file(path: Path, source: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    try:
        observed = 0
        while observed < len(source):
            written = os.write(descriptor, source[observed:])
            if written < 1:
                raise OSError("external binary staging write made no progress")
            observed += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _private_child_limits() -> None:
    os.umask(0o077)
    resource.setrlimit(
        resource.RLIMIT_CPU,
        (
            POSEBUSTERS_EXTERNAL_BINARY_CPU_LIMIT_SECONDS,
            POSEBUSTERS_EXTERNAL_BINARY_CPU_LIMIT_SECONDS,
        ),
    )
    resource.setrlimit(
        resource.RLIMIT_FSIZE,
        (
            POSEBUSTERS_EXTERNAL_BINARY_MAX_POSE_ARTIFACT_BYTES,
            POSEBUSTERS_EXTERNAL_BINARY_MAX_POSE_ARTIFACT_BYTES,
        ),
    )
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def _base_environment(library_dirs: Sequence[Path]) -> dict[str, str]:
    environment = {
        "CUDA_VISIBLE_DEVICES": "",
        "HIP_VISIBLE_DEVICES": "",
        "ROCR_VISIBLE_DEVICES": "",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "MKL_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "PYTHONHASHSEED": "0",
        "TZ": "UTC",
    }
    if library_dirs:
        environment["LD_LIBRARY_PATH"] = ":".join(str(path) for path in library_dirs)
    return environment


def _validated_library_dirs(
    paths: Sequence[str | os.PathLike[str]],
) -> tuple[Path, ...]:
    directories: list[Path] = []
    for raw in paths:
        try:
            path = Path(raw).resolve(strict=True)
            metadata = path.lstat()
        except OSError as exc:
            raise PoseBustersExternalBinaryExecutionError(
                "dynamic library directory is unavailable"
            ) from exc
        if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
            raise PoseBustersExternalBinaryExecutionError(
                "dynamic library directory must be a real directory"
            )
        if path in directories:
            raise PoseBustersExternalBinaryExecutionError(
                "dynamic library directory is duplicated"
            )
        directories.append(path)
    return tuple(directories)


@dataclass(frozen=True, slots=True)
class PoseBustersExternalBinaryDependency:
    requested_name: str
    payload_name: str
    sha256: str
    size_bytes: int
    schema_id: str = POSEBUSTERS_EXTERNAL_BINARY_DEPENDENCY_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_EXTERNAL_BINARY_DEPENDENCY_SCHEMA_ID:
            raise PoseBustersExternalBinaryExecutionError(
                "unsupported external binary dependency schema"
            )
        for name in ("requested_name", "payload_name"):
            value = _bounded_text(getattr(self, name), name=name)
            if "/" in value or "\\" in value:
                raise PoseBustersExternalBinaryExecutionError(
                    "external binary dependency name must be a basename"
                )
            object.__setattr__(self, name, value)
        object.__setattr__(self, "sha256", _digest(self.sha256, name="dependency"))
        size = _positive_int(self.size_bytes, name="dependency size")
        if size > POSEBUSTERS_EXTERNAL_BINARY_MAX_LIBRARY_BYTES:
            raise PoseBustersExternalBinaryExecutionError(
                "external binary dependency exceeds its byte bound"
            )
        object.__setattr__(self, "size_bytes", size)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "requested_name": self.requested_name,
            "payload_name": self.payload_name,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True, slots=True)
class PoseBustersExternalBinaryRuntimeIdentity:
    engine_id: str
    engine_version: str
    version_output: str
    executable_sha256: str
    executable_size_bytes: int
    source_url: str
    source_release_date: str
    dynamic_dependencies: tuple[PoseBustersExternalBinaryDependency, ...]
    platform_system: str
    platform_machine: str
    libc_name: str
    libc_version: str
    schema_id: str = POSEBUSTERS_EXTERNAL_BINARY_RUNTIME_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_EXTERNAL_BINARY_RUNTIME_SCHEMA_ID:
            raise PoseBustersExternalBinaryExecutionError(
                "unsupported external binary runtime schema"
            )
        engine = _engine_id(self.engine_id)
        spec = _ENGINE_SPECS[engine]
        version = _bounded_text(self.engine_version, name="engine version")
        version_output = _bounded_text(
            self.version_output,
            name="engine version output",
        )
        source_url = _bounded_text(self.source_url, name="engine source URL")
        release_date = _bounded_text(
            self.source_release_date,
            name="engine source release date",
        )
        executable_sha = _digest(
            self.executable_sha256,
            name="engine executable",
        )
        executable_size = _positive_int(
            self.executable_size_bytes,
            name="engine executable size",
        )
        dependencies = tuple(self.dynamic_dependencies)
        if (
            version != spec["version"]
            or version_output != spec["version_output"]
            or executable_sha != spec["executable_sha256"]
            or executable_size != spec["executable_size_bytes"]
            or source_url != spec["source_url"]
            or release_date != spec["source_release_date"]
        ):
            raise PoseBustersExternalBinaryExecutionError(
                "external engine executable identity changed"
            )
        names = tuple(row.requested_name for row in dependencies)
        expected_names = _GNINA_REQUIRED_LIBRARIES if engine == "gnina" else ()
        if (
            names != tuple(sorted(names))
            or len(set(names)) != len(names)
            or names != expected_names
        ):
            raise PoseBustersExternalBinaryExecutionError(
                "external engine dynamic dependency closure changed"
            )
        for name in (
            "platform_system",
            "platform_machine",
            "libc_name",
            "libc_version",
        ):
            object.__setattr__(
                self,
                name,
                _bounded_text(getattr(self, name), name=name),
            )
        object.__setattr__(self, "engine_id", engine)
        object.__setattr__(self, "engine_version", version)
        object.__setattr__(self, "version_output", version_output)
        object.__setattr__(self, "executable_sha256", executable_sha)
        object.__setattr__(self, "executable_size_bytes", executable_size)
        object.__setattr__(self, "source_url", source_url)
        object.__setattr__(self, "source_release_date", release_date)
        object.__setattr__(self, "dynamic_dependencies", dependencies)

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "engine_id": self.engine_id,
            "engine_version": self.engine_version,
            "version_output": self.version_output,
            "executable_sha256": self.executable_sha256,
            "executable_size_bytes": self.executable_size_bytes,
            "source_url": self.source_url,
            "source_release_date": self.source_release_date,
            "dynamic_dependencies": [
                row.to_dict() for row in self.dynamic_dependencies
            ],
            "platform_system": self.platform_system,
            "platform_machine": self.platform_machine,
            "libc_name": self.libc_name,
            "libc_version": self.libc_version,
        }


def _dynamic_dependencies(
    executable: Path,
    library_dirs: Sequence[Path],
) -> tuple[PoseBustersExternalBinaryDependency, ...]:
    try:
        result = subprocess.run(
            ["/usr/bin/ldd", str(executable)],
            check=False,
            capture_output=True,
            timeout=30,
            env=_base_environment(library_dirs),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise PoseBustersExternalBinaryExecutionError(
            "external engine dependency inspection failed"
        ) from exc
    if result.returncode != 0:
        raise PoseBustersExternalBinaryExecutionError(
            "dynamic external engine did not expose a complete dependency closure"
        )
    try:
        text = result.stdout.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PoseBustersExternalBinaryExecutionError(
            "external engine dependency inspection was not UTF-8"
        ) from exc
    paths: dict[str, Path] = {}
    for line in text.splitlines():
        if "linux-vdso" in line:
            continue
        arrow = _LDD_ARROW_LINE.fullmatch(line)
        loader = _LDD_LOADER_LINE.fullmatch(line)
        if arrow is not None:
            requested, raw_path = arrow.groups()
        elif loader is not None:
            raw_path = loader.group(1)
            requested = Path(raw_path).name
        elif "not found" in line:
            raise PoseBustersExternalBinaryExecutionError(
                "external engine dynamic dependency is missing"
            )
        elif line.strip():
            raise PoseBustersExternalBinaryExecutionError(
                "external engine dependency inspection format changed"
            )
        else:
            continue
        try:
            path = Path(raw_path).resolve(strict=True)
        except OSError as exc:
            raise PoseBustersExternalBinaryExecutionError(
                "external engine dependency path is unavailable"
            ) from exc
        if requested in paths:
            raise PoseBustersExternalBinaryExecutionError(
                "external engine dependency name is duplicated"
            )
        paths[requested] = path
    if tuple(sorted(paths)) != _GNINA_REQUIRED_LIBRARIES:
        raise PoseBustersExternalBinaryExecutionError(
            "GNINA dynamic dependency names differ from the frozen closure"
        )
    dependencies = []
    for requested, path in sorted(paths.items()):
        sha256, size = _hash_regular_file(
            path,
            maximum_bytes=POSEBUSTERS_EXTERNAL_BINARY_MAX_LIBRARY_BYTES,
        )
        dependencies.append(
            PoseBustersExternalBinaryDependency(
                requested_name=requested,
                payload_name=path.name,
                sha256=sha256,
                size_bytes=size,
            )
        )
    return tuple(dependencies)


def _load_runtime_identity(
    engine_id: str,
    executable_path: Path,
    library_dirs: Sequence[Path],
) -> PoseBustersExternalBinaryRuntimeIdentity:
    engine = _engine_id(engine_id)
    spec = _ENGINE_SPECS[engine]
    sha256, size = _hash_regular_file(
        executable_path,
        maximum_bytes=POSEBUSTERS_EXTERNAL_BINARY_MAX_EXECUTABLE_BYTES,
        require_executable=True,
    )
    if sha256 != spec["executable_sha256"] or size != spec["executable_size_bytes"]:
        raise PoseBustersExternalBinaryExecutionError(
            "external engine executable differs from the frozen official asset"
        )
    if bool(library_dirs) != bool(spec["dynamic"]):
        raise PoseBustersExternalBinaryExecutionError(
            "external engine dynamic-library inputs are inconsistent"
        )
    try:
        version_result = subprocess.run(
            [str(executable_path), "--version"],
            check=False,
            capture_output=True,
            timeout=30,
            env=_base_environment(library_dirs),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise PoseBustersExternalBinaryExecutionError(
            "external engine version command failed"
        ) from exc
    version_bytes = version_result.stdout + version_result.stderr
    if (
        version_result.returncode != 0
        or len(version_bytes) > POSEBUSTERS_EXTERNAL_BINARY_MAX_DIAGNOSTIC_BYTES
    ):
        raise PoseBustersExternalBinaryExecutionError(
            "external engine version command was not successful and bounded"
        )
    try:
        version_output = _bounded_text(
            version_bytes.decode("utf-8"),
            name="external engine version output",
        )
    except UnicodeDecodeError as exc:
        raise PoseBustersExternalBinaryExecutionError(
            "external engine version output was not UTF-8"
        ) from exc
    dependencies = (
        _dynamic_dependencies(executable_path, library_dirs)
        if engine == "gnina"
        else ()
    )
    libc_name, libc_version = platform.libc_ver()
    return PoseBustersExternalBinaryRuntimeIdentity(
        engine_id=engine,
        engine_version=spec["version"],
        version_output=version_output,
        executable_sha256=sha256,
        executable_size_bytes=size,
        source_url=spec["source_url"],
        source_release_date=spec["source_release_date"],
        dynamic_dependencies=dependencies,
        platform_system=platform.system(),
        platform_machine=platform.machine(),
        libc_name=libc_name,
        libc_version=libc_version,
    )


@dataclass(frozen=True, slots=True)
class PoseBustersExternalBinaryPoseScore:
    pose_rank: int
    components_binary64_hex: tuple[str, ...]
    schema_id: str = POSEBUSTERS_EXTERNAL_BINARY_SCORE_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_EXTERNAL_BINARY_SCORE_SCHEMA_ID:
            raise PoseBustersExternalBinaryExecutionError(
                "unsupported external binary score schema"
            )
        rank = _positive_int(self.pose_rank, name="external binary pose rank")
        components = tuple(
            _validate_hex(value, name="external binary score")
            for value in self.components_binary64_hex
        )
        if not components:
            raise PoseBustersExternalBinaryExecutionError(
                "external binary score must contain components"
            )
        object.__setattr__(self, "pose_rank", rank)
        object.__setattr__(self, "components_binary64_hex", components)

    def to_dict(self, component_order: Sequence[str]) -> dict[str, Any]:
        if len(component_order) != len(self.components_binary64_hex):
            raise PoseBustersExternalBinaryExecutionError(
                "external binary score component order is inconsistent"
            )
        return {
            "schema_id": self.schema_id,
            "pose_rank": self.pose_rank,
            "score_component_order": list(component_order),
            "components_binary64_hex": list(self.components_binary64_hex),
            "components": {
                name: value
                for name, value in zip(
                    component_order,
                    self.components_binary64_hex,
                )
            },
        }


def _score_hex(value: str) -> str:
    try:
        number = float(value)
    except ValueError as exc:
        raise PoseBustersExternalBinaryExecutionError(
            "external binary score is not numeric"
        ) from exc
    if not math.isfinite(number):
        raise PoseBustersExternalBinaryExecutionError(
            "external binary score must be finite"
        )
    return number.hex()


def _parse_pose_output(
    engine_id: str,
    source: bytes,
) -> tuple[PoseBustersExternalBinaryPoseScore, ...]:
    engine = _engine_id(engine_id)
    if len(source) > POSEBUSTERS_EXTERNAL_BINARY_MAX_POSE_ARTIFACT_BYTES:
        raise PoseBustersExternalBinaryExecutionError(
            "external binary pose output exceeds its byte bound"
        )
    try:
        text = source.decode("ascii")
    except UnicodeDecodeError as exc:
        raise PoseBustersExternalBinaryExecutionError(
            "external binary PDBQT output must be ASCII"
        ) from exc
    lines = text.splitlines()
    blocks: list[list[str]] = []
    current: list[str] | None = None
    expected_rank = 1
    for line in lines:
        model = _MODEL_LINE.fullmatch(line)
        if model is not None:
            if current is not None or int(model.group(1)) != expected_rank:
                raise PoseBustersExternalBinaryExecutionError(
                    "external binary PDBQT MODEL order is invalid"
                )
            current = []
            continue
        if line == "ENDMDL":
            if current is None:
                raise PoseBustersExternalBinaryExecutionError(
                    "external binary PDBQT ENDMDL is unmatched"
                )
            blocks.append(current)
            current = None
            expected_rank += 1
            continue
        if current is None:
            if line.strip():
                raise PoseBustersExternalBinaryExecutionError(
                    "external binary PDBQT has text outside MODEL blocks"
                )
        else:
            current.append(line)
    if current is not None or not blocks or len(blocks) > 20:
        raise PoseBustersExternalBinaryExecutionError(
            "external binary PDBQT model count is invalid"
        )
    required_labels = (
        ("minimizedAffinity", "CNNscore", "CNNaffinity")
        if engine == "gnina"
        else ("minimizedAffinity",)
    )
    rows: list[PoseBustersExternalBinaryPoseScore] = []
    for rank, block in enumerate(blocks, start=1):
        scores: dict[str, str] = {}
        atom_count = 0
        for line in block:
            match = _SCORE_LINE.fullmatch(line)
            if match is not None:
                label, value = match.groups()
                if label in scores:
                    raise PoseBustersExternalBinaryExecutionError(
                        "external binary PDBQT score label is duplicated"
                    )
                scores[label] = _score_hex(value)
            if line.startswith(("ATOM  ", "HETATM")):
                atom_count += 1
        if (
            tuple(label for label in required_labels if label in scores)
            != required_labels
            or any(label not in required_labels for label in scores)
            or atom_count < 1
            or "ROOT" not in block
            or "ENDROOT" not in block
        ):
            raise PoseBustersExternalBinaryExecutionError(
                "external binary PDBQT model content is invalid"
            )
        rows.append(
            PoseBustersExternalBinaryPoseScore(
                pose_rank=rank,
                components_binary64_hex=tuple(
                    scores[label] for label in required_labels
                ),
            )
        )
    if engine == "smina" and any(
        float.fromhex(rows[index].components_binary64_hex[0])
        > float.fromhex(rows[index + 1].components_binary64_hex[0])
        for index in range(len(rows) - 1)
    ):
        raise PoseBustersExternalBinaryExecutionError(
            "Smina pose affinity order is invalid"
        )
    if engine == "gnina" and any(
        float.fromhex(rows[index].components_binary64_hex[1])
        < float.fromhex(rows[index + 1].components_binary64_hex[1])
        for index in range(len(rows) - 1)
    ):
        raise PoseBustersExternalBinaryExecutionError(
            "GNINA CNN pose-score order is invalid"
        )
    return tuple(rows)


@dataclass(frozen=True, slots=True)
class _ExternalExecutionBytes:
    poses_pdbqt: bytes
    pose_scores: tuple[PoseBustersExternalBinaryPoseScore, ...]
    diagnostic_sha256: str
    diagnostic_size_bytes: int


class _ExternalRuntimeProtocol(Protocol):
    identity: PoseBustersExternalBinaryRuntimeIdentity

    def execute(
        self,
        receptor_pdbqt: bytes,
        ligand_pdbqt: bytes,
        pocket_center_binary64_hex: tuple[str, ...],
    ) -> _ExternalExecutionBytes: ...


class _ExternalBinaryRuntime:
    def __init__(
        self,
        *,
        engine_id: str,
        executable_path: Path,
        library_dirs: Sequence[Path],
        identity: PoseBustersExternalBinaryRuntimeIdentity,
        scratch_root: Path,
    ) -> None:
        self.engine_id = _engine_id(engine_id)
        self.executable_path = executable_path
        self.library_dirs = tuple(library_dirs)
        self.identity = identity
        self.scratch_root = _private_scratch_root(scratch_root)

    def _arguments(
        self,
        receptor_path: Path,
        ligand_path: Path,
        output_path: Path,
        center: tuple[str, ...],
    ) -> list[str]:
        coordinates = tuple(format(float.fromhex(value), ".17g") for value in center)
        arguments = [
            str(self.executable_path),
            "--receptor",
            str(receptor_path),
            "--ligand",
            str(ligand_path),
            "--center_x",
            coordinates[0],
            "--center_y",
            coordinates[1],
            "--center_z",
            coordinates[2],
            "--size_x",
            "22.5",
            "--size_y",
            "22.5",
            "--size_z",
            "22.5",
            "--cpu",
            "1",
            "--seed",
            "20260723",
            "--exhaustiveness",
            "32",
            "--num_modes",
            "20",
            "--min_rmsd_filter",
            "1.0",
            "--scoring",
            "vina",
            "--addH",
            "0",
        ]
        if self.engine_id == "gnina":
            arguments.extend(
                [
                    "--cnn_scoring",
                    "rescore",
                    "--pose_sort_order",
                    "CNNscore",
                    "--no_gpu",
                ]
            )
        else:
            arguments.extend(["--energy_range", "20"])
        arguments.extend(["--out", str(output_path)])
        return arguments

    def _diagnostic(
        self,
        source: bytes,
        replacements: Sequence[tuple[bytes, bytes]],
    ) -> bytes:
        normalized = source
        for original, replacement in replacements:
            normalized = normalized.replace(original, replacement)
        if self.engine_id == "smina":
            normalized = _SMINA_TIMING_LINE.sub(
                rb"\1 <SECONDS>",
                normalized,
            )
        if len(normalized) > POSEBUSTERS_EXTERNAL_BINARY_MAX_DIAGNOSTIC_BYTES:
            raise PoseBustersExternalBinaryExecutionError(
                "external binary diagnostic exceeds its byte bound"
            )
        return normalized

    def execute(
        self,
        receptor_pdbqt: bytes,
        ligand_pdbqt: bytes,
        pocket_center_binary64_hex: tuple[str, ...],
    ) -> _ExternalExecutionBytes:
        if len(pocket_center_binary64_hex) != 3:
            raise PoseBustersExternalBinaryCaseError(
                stage="input",
                error_code="invalid_pocket_center",
                error_type="ValueError",
                error_message_sha256=_hash_bytes(b"invalid pocket center"),
                diagnostic_sha256=_hash_bytes(b""),
                diagnostic_size_bytes=0,
            )
        try:
            with tempfile.TemporaryDirectory(
                prefix=f"{self.engine_id}-case-",
                dir=self.scratch_root,
            ) as temporary:
                root = Path(temporary)
                receptor_path = root / "receptor.pdbqt"
                ligand_path = root / "ligand.pdbqt"
                output_path = root / "poses.pdbqt"
                diagnostic_path = root / "diagnostic.txt"
                _write_private_file(receptor_path, receptor_pdbqt)
                _write_private_file(ligand_path, ligand_pdbqt)
                arguments = self._arguments(
                    receptor_path,
                    ligand_path,
                    output_path,
                    pocket_center_binary64_hex,
                )
                descriptor = os.open(
                    diagnostic_path,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
                    0o600,
                )
                try:
                    with os.fdopen(descriptor, "wb", closefd=False) as diagnostic:
                        result = subprocess.run(
                            arguments,
                            check=False,
                            cwd=root,
                            env={
                                **_base_environment(self.library_dirs),
                                "TMPDIR": str(root),
                            },
                            stdout=diagnostic,
                            stderr=subprocess.STDOUT,
                            timeout=POSEBUSTERS_EXTERNAL_BINARY_TIMEOUT_SECONDS,
                            preexec_fn=_private_child_limits,
                        )
                        diagnostic.flush()
                        os.fsync(diagnostic.fileno())
                finally:
                    os.close(descriptor)
                raw_diagnostic = _read_bounded_regular_file(
                    diagnostic_path,
                    maximum_bytes=POSEBUSTERS_EXTERNAL_BINARY_MAX_DIAGNOSTIC_BYTES,
                )
                diagnostic = self._diagnostic(
                    raw_diagnostic,
                    (
                        (str(self.executable_path).encode(), b"<ENGINE>"),
                        (str(receptor_path).encode(), b"<RECEPTOR>"),
                        (str(ligand_path).encode(), b"<LIGAND>"),
                        (str(output_path).encode(), b"<OUTPUT>"),
                        (str(root).encode(), b"<SCRATCH>"),
                    ),
                )
                if result.returncode != 0:
                    raise _classified_execution_failure(
                        self.engine_id,
                        result.returncode,
                        diagnostic,
                    )
                poses = _read_bounded_regular_file(
                    output_path,
                    maximum_bytes=(POSEBUSTERS_EXTERNAL_BINARY_MAX_POSE_ARTIFACT_BYTES),
                )
                scores = _parse_pose_output(self.engine_id, poses)
                return _ExternalExecutionBytes(
                    poses_pdbqt=poses,
                    pose_scores=scores,
                    diagnostic_sha256=_hash_bytes(diagnostic),
                    diagnostic_size_bytes=len(diagnostic),
                )
        except PoseBustersExternalBinaryCaseError:
            raise
        except subprocess.TimeoutExpired as exc:
            raise PoseBustersExternalBinaryCaseError(
                stage="engine_execution",
                error_code=f"{self.engine_id}_execution_timeout",
                error_type=type(exc).__name__,
                error_message_sha256=_hash_bytes(_normalize_error(exc)),
                diagnostic_sha256=_hash_bytes(b""),
                diagnostic_size_bytes=0,
            ) from exc
        except Exception as exc:
            raise PoseBustersExternalBinaryCaseError(
                stage="engine_execution",
                error_code=f"{self.engine_id}_execution_failed",
                error_type=type(exc).__name__,
                error_message_sha256=_hash_bytes(_normalize_error(exc)),
                diagnostic_sha256=_hash_bytes(b""),
                diagnostic_size_bytes=0,
            ) from exc


def _load_runtime(
    engine_id: str,
    executable_path: str | os.PathLike[str],
    library_dirs: Sequence[str | os.PathLike[str]],
    scratch_root: Path,
) -> _ExternalRuntimeProtocol:
    engine = _engine_id(engine_id)
    try:
        executable = Path(executable_path).resolve(strict=True)
    except OSError as exc:
        raise PoseBustersExternalBinaryExecutionError(
            "external engine executable path is unavailable"
        ) from exc
    directories = _validated_library_dirs(library_dirs)
    identity = _load_runtime_identity(engine, executable, directories)
    return _ExternalBinaryRuntime(
        engine_id=engine,
        executable_path=executable,
        library_dirs=directories,
        identity=identity,
        scratch_root=scratch_root,
    )


@dataclass(frozen=True, slots=True)
class PoseBustersExternalBinaryPoseArtifact:
    engine_id: str
    relative_path: str
    sha256: str
    size_bytes: int
    prepared_receptor_sha256: str
    prepared_ligand_sha256: str
    schema_id: str = POSEBUSTERS_EXTERNAL_BINARY_ARTIFACT_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_EXTERNAL_BINARY_ARTIFACT_SCHEMA_ID:
            raise PoseBustersExternalBinaryExecutionError(
                "unsupported external binary artifact schema"
            )
        engine = _engine_id(self.engine_id)
        if not isinstance(self.relative_path, str):
            raise PoseBustersExternalBinaryExecutionError(
                "external binary artifact path must be text"
            )
        relative = PurePosixPath(self.relative_path)
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or len(relative.parts) != 2
            or relative.parts[1] != "poses.pdbqt"
        ):
            raise PoseBustersExternalBinaryExecutionError(
                "external binary artifact path is unsafe"
            )
        for name in (
            "sha256",
            "prepared_receptor_sha256",
            "prepared_ligand_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _digest(getattr(self, name), name=name),
            )
        size = _positive_int(self.size_bytes, name="external binary artifact size")
        if size > POSEBUSTERS_EXTERNAL_BINARY_MAX_POSE_ARTIFACT_BYTES:
            raise PoseBustersExternalBinaryExecutionError(
                "external binary artifact exceeds its byte bound"
            )
        object.__setattr__(self, "engine_id", engine)
        object.__setattr__(self, "relative_path", relative.as_posix())
        object.__setattr__(self, "size_bytes", size)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "role": f"{self.engine_id}_generated_poses_pdbqt",
            "engine_id": self.engine_id,
            "relative_path": self.relative_path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "media_type": "chemical/x-pdbqt",
            "prepared_receptor_sha256": self.prepared_receptor_sha256,
            "prepared_ligand_sha256": self.prepared_ligand_sha256,
        }


@dataclass(frozen=True, slots=True)
class PoseBustersExternalBinaryExecutionCase:
    engine_id: str
    case_id: str
    status: str
    disposition_code: str
    preparation_status: str
    preparation_disposition_code: str
    pocket_center_binary64_hex: tuple[str, ...] = ()
    engine_attempted: bool = False
    pose_scores: tuple[PoseBustersExternalBinaryPoseScore, ...] = ()
    pose_artifact: PoseBustersExternalBinaryPoseArtifact | None = None
    error_stage: str = ""
    error_code: str = ""
    error_type: str = ""
    error_message_sha256: str = ""
    diagnostic_sha256: str = ""
    diagnostic_size_bytes: int = 0
    schema_id: str = POSEBUSTERS_EXTERNAL_BINARY_CASE_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_EXTERNAL_BINARY_CASE_SCHEMA_ID:
            raise PoseBustersExternalBinaryExecutionError(
                "unsupported external binary case schema"
            )
        engine = _engine_id(self.engine_id)
        case = _case_id(self.case_id)
        if self.status not in _CASE_STATUSES:
            raise PoseBustersExternalBinaryExecutionError(
                "external binary case status is invalid"
            )
        if self.preparation_status not in _PREPARATION_STATUSES:
            raise PoseBustersExternalBinaryExecutionError(
                "external binary preparation status is invalid"
            )
        disposition = _token(
            self.disposition_code,
            name="external binary disposition",
        )
        preparation_disposition = _token(
            self.preparation_disposition_code,
            name="external binary preparation disposition",
        )
        center = tuple(
            _validate_hex(value, name="external binary pocket center")
            for value in self.pocket_center_binary64_hex
        )
        scores = tuple(self.pose_scores)
        expected_components = len(_ENGINE_SPECS[engine]["score_components"])
        diagnostics = _positive_int(
            self.diagnostic_size_bytes,
            name="external binary diagnostic size",
            allow_zero=True,
        )
        if self.status == "success":
            valid = (
                self.preparation_status == "prepared"
                and self.engine_attempted
                and len(center) == 3
                and 0 < len(scores) <= 20
                and tuple(row.pose_rank for row in scores)
                == tuple(range(1, len(scores) + 1))
                and all(
                    len(row.components_binary64_hex) == expected_components
                    for row in scores
                )
                and isinstance(
                    self.pose_artifact,
                    PoseBustersExternalBinaryPoseArtifact,
                )
                and self.pose_artifact.engine_id == engine
                and not any(
                    (
                        self.error_stage,
                        self.error_code,
                        self.error_type,
                        self.error_message_sha256,
                    )
                )
                and bool(self.diagnostic_sha256)
            )
        elif self.status == "engine_failure":
            valid = (
                self.preparation_status == "prepared"
                and self.engine_attempted
                and len(center) == 3
                and not scores
                and self.pose_artifact is None
                and all(
                    (
                        self.error_stage,
                        self.error_code,
                        self.error_type,
                        self.error_message_sha256,
                        self.diagnostic_sha256,
                    )
                )
            )
        else:
            expected_preparation = {
                "blocked_preparation_failure": "preparation_failure",
                "blocked_upstream_failure": "upstream_failure",
                "abstain_chemistry_scope": "abstain_chemistry_scope",
            }[self.status]
            valid = (
                self.preparation_status == expected_preparation
                and not self.engine_attempted
                and not center
                and not scores
                and self.pose_artifact is None
                and not any(
                    (
                        self.error_stage,
                        self.error_type,
                        self.error_message_sha256,
                        self.diagnostic_sha256,
                        diagnostics,
                    )
                )
            )
        if not valid:
            raise PoseBustersExternalBinaryExecutionError(
                "external binary case disposition is inconsistent"
            )
        for name, helper in (
            ("error_stage", _token),
            ("error_code", _token),
            ("error_type", _identifier),
        ):
            value = getattr(self, name)
            if value:
                object.__setattr__(
                    self,
                    name,
                    helper(value, name=f"external binary {name}"),
                )
        if self.error_message_sha256:
            object.__setattr__(
                self,
                "error_message_sha256",
                _digest(self.error_message_sha256, name="external binary error"),
            )
        if self.diagnostic_sha256:
            object.__setattr__(
                self,
                "diagnostic_sha256",
                _digest(self.diagnostic_sha256, name="external binary diagnostic"),
            )
        object.__setattr__(self, "engine_id", engine)
        object.__setattr__(self, "case_id", case)
        object.__setattr__(self, "disposition_code", disposition)
        object.__setattr__(
            self,
            "preparation_disposition_code",
            preparation_disposition,
        )
        object.__setattr__(self, "pocket_center_binary64_hex", center)
        object.__setattr__(self, "pose_scores", scores)
        object.__setattr__(self, "diagnostic_size_bytes", diagnostics)

    @property
    def pose_count(self) -> int:
        return len(self.pose_scores)

    def to_dict(self) -> dict[str, Any]:
        component_order = _ENGINE_SPECS[self.engine_id]["score_components"]
        return {
            "schema_id": self.schema_id,
            "engine_id": self.engine_id,
            "case_id": self.case_id,
            "status": self.status,
            "disposition_code": self.disposition_code,
            "preparation_status": self.preparation_status,
            "preparation_disposition_code": self.preparation_disposition_code,
            "pocket_center_binary64_hex": list(self.pocket_center_binary64_hex),
            "engine_attempted": self.engine_attempted,
            "pose_count": self.pose_count,
            "score_component_order": list(component_order),
            "pose_scores": [row.to_dict(component_order) for row in self.pose_scores],
            "pose_artifact": (
                self.pose_artifact.to_dict() if self.pose_artifact is not None else None
            ),
            "generated_pose_present": self.status == "success",
            "pose_validity_evaluated": False,
            "symmetry_aware_rmsd_evaluated": False,
            "error_stage": self.error_stage,
            "error_code": self.error_code,
            "error_type": self.error_type,
            "error_message_sha256": self.error_message_sha256,
            "diagnostic_sha256": self.diagnostic_sha256,
            "diagnostic_size_bytes": self.diagnostic_size_bytes,
        }


@dataclass(frozen=True, slots=True)
class PoseBustersExternalBinaryExecutionMetric:
    metric_id: str
    numerator: int
    denominator: int
    estimate: float
    confidence_interval_low: float
    confidence_interval_high: float
    schema_id: str = POSEBUSTERS_EXTERNAL_BINARY_METRIC_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_EXTERNAL_BINARY_METRIC_SCHEMA_ID:
            raise PoseBustersExternalBinaryExecutionError(
                "unsupported external binary metric schema"
            )
        metric = _token(self.metric_id, name="external binary metric")
        numerator = _positive_int(
            self.numerator, name="metric numerator", allow_zero=True
        )
        denominator = _positive_int(self.denominator, name="metric denominator")
        values = (
            float(self.estimate),
            float(self.confidence_interval_low),
            float(self.confidence_interval_high),
        )
        if (
            numerator > denominator
            or any(
                not math.isfinite(value) or not 0.0 <= value <= 1.0 for value in values
            )
            or not values[1] <= values[0] <= values[2]
            or not math.isclose(values[0], numerator / denominator, abs_tol=1.0e-15)
        ):
            raise PoseBustersExternalBinaryExecutionError(
                "external binary metric is inconsistent"
            )
        object.__setattr__(self, "metric_id", metric)
        object.__setattr__(self, "numerator", numerator)
        object.__setattr__(self, "denominator", denominator)
        object.__setattr__(self, "estimate", values[0])
        object.__setattr__(self, "confidence_interval_low", values[1])
        object.__setattr__(self, "confidence_interval_high", values[2])

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "metric_id": self.metric_id,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "estimate": self.estimate,
            "confidence_level": POSEBUSTERS_EXTERNAL_BINARY_CONFIDENCE_LEVEL,
            "confidence_interval_method": "wilson_score_binomial",
            "confidence_interval_low": self.confidence_interval_low,
            "confidence_interval_high": self.confidence_interval_high,
        }


def _metric(
    metric_id: str,
    numerator: int,
    denominator: int,
) -> PoseBustersExternalBinaryExecutionMetric:
    proportion = numerator / denominator
    z2 = POSEBUSTERS_EXTERNAL_BINARY_Z**2
    scale = 1.0 + z2 / denominator
    center = (proportion + z2 / (2.0 * denominator)) / scale
    radius = (
        POSEBUSTERS_EXTERNAL_BINARY_Z
        * math.sqrt(
            proportion * (1.0 - proportion) / denominator + z2 / (4.0 * denominator**2)
        )
        / scale
    )
    return PoseBustersExternalBinaryExecutionMetric(
        metric_id=metric_id,
        numerator=numerator,
        denominator=denominator,
        estimate=proportion,
        confidence_interval_low=min(proportion, max(0.0, center - radius)),
        confidence_interval_high=max(proportion, min(1.0, center + radius)),
    )


def _summary_metrics(
    engine_id: str,
    rows: Sequence[PoseBustersExternalBinaryExecutionCase],
) -> tuple[PoseBustersExternalBinaryExecutionMetric, ...]:
    engine = _engine_id(engine_id)
    predicates: tuple[
        tuple[str, Callable[[PoseBustersExternalBinaryExecutionCase], bool]],
        ...,
    ] = (
        (
            "strict_prepared_input_pair_rate",
            lambda row: row.preparation_status == "prepared",
        ),
        (f"{engine}_engine_attempt_rate", lambda row: row.engine_attempted),
        (f"{engine}_engine_success_rate", lambda row: row.status == "success"),
        (f"{engine}_engine_failure_rate", lambda row: row.status == "engine_failure"),
        ("generated_pose_artifact_rate", lambda row: row.status == "success"),
        (
            "preparation_failure_blocked_rate",
            lambda row: row.status == "blocked_preparation_failure",
        ),
        (
            "upstream_failure_blocked_rate",
            lambda row: row.status == "blocked_upstream_failure",
        ),
        (
            "chemistry_scope_abstention_rate",
            lambda row: row.status == "abstain_chemistry_scope",
        ),
        ("generated_pose_validity_evaluation_rate", lambda _row: False),
        ("symmetry_aware_rmsd_evaluation_rate", lambda _row: False),
    )
    denominator = len(rows)
    return tuple(
        _metric(name, sum(bool(predicate(row)) for row in rows), denominator)
        for name, predicate in predicates
    )


def _artifact_set_sha256(
    rows: Sequence[PoseBustersExternalBinaryExecutionCase],
) -> str:
    return _canonical_sha256(
        {
            row.case_id: row.pose_artifact.to_dict()
            for row in rows
            if row.pose_artifact is not None
        }
    )


@dataclass(frozen=True, slots=True)
class PoseBustersExternalBinaryExecutionReceipt:
    engine_id: str
    preparation_receipt_sha256: str
    preparation_receipt_file_sha256: str
    preparation_artifact_set_sha256: str
    preparation_runtime_identity_sha256: str
    implementation_source_sha256: str
    implementation_source_members: tuple[tuple[str, str], ...]
    runtime_identity: PoseBustersExternalBinaryRuntimeIdentity
    configuration_sha256: str
    case_rows: tuple[PoseBustersExternalBinaryExecutionCase, ...]
    metrics: tuple[PoseBustersExternalBinaryExecutionMetric, ...]
    artifact_set_sha256: str
    schema_id: str = POSEBUSTERS_EXTERNAL_BINARY_EXECUTION_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_EXTERNAL_BINARY_EXECUTION_SCHEMA_ID:
            raise PoseBustersExternalBinaryExecutionError(
                "unsupported external binary receipt schema"
            )
        engine = _engine_id(self.engine_id)
        for name in (
            "preparation_receipt_sha256",
            "preparation_receipt_file_sha256",
            "preparation_artifact_set_sha256",
            "preparation_runtime_identity_sha256",
            "implementation_source_sha256",
            "configuration_sha256",
            "artifact_set_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _digest(getattr(self, name), name=name),
            )
        if (
            self.configuration_sha256
            != (POSEBUSTERS_EXTERNAL_BINARY_CONFIGURATION_SHA256[engine])
        ):
            raise PoseBustersExternalBinaryExecutionError(
                "external binary configuration identity changed"
            )
        members = tuple(
            (
                _token(role, name="external binary source role"),
                _digest(digest, name="external binary implementation source"),
            )
            for role, digest in self.implementation_source_members
        )
        if (
            not members
            or tuple(sorted(members)) != members
            or len({role for role, _digest_value in members}) != len(members)
            or self.implementation_source_sha256 != _canonical_sha256(dict(members))
        ):
            raise PoseBustersExternalBinaryExecutionError(
                "external binary implementation-source identity is invalid"
            )
        if (
            not isinstance(
                self.runtime_identity,
                PoseBustersExternalBinaryRuntimeIdentity,
            )
            or self.runtime_identity.engine_id != engine
        ):
            raise PoseBustersExternalBinaryExecutionError(
                "external binary runtime identity is invalid"
            )
        rows = tuple(self.case_rows)
        if (
            not rows
            or tuple(row.case_id for row in rows)
            != tuple(sorted(row.case_id for row in rows))
            or len({row.case_id for row in rows}) != len(rows)
            or any(row.engine_id != engine for row in rows)
        ):
            raise PoseBustersExternalBinaryExecutionError(
                "external binary rows must be canonical unique cases"
            )
        metrics = _summary_metrics(engine, rows)
        if tuple(row.to_dict() for row in self.metrics) != tuple(
            row.to_dict() for row in metrics
        ):
            raise PoseBustersExternalBinaryExecutionError(
                "external binary metrics do not match case rows"
            )
        if self.artifact_set_sha256 != _artifact_set_sha256(rows):
            raise PoseBustersExternalBinaryExecutionError(
                "external binary artifact-set identity is invalid"
            )
        object.__setattr__(self, "engine_id", engine)
        object.__setattr__(self, "implementation_source_members", members)
        object.__setattr__(self, "case_rows", rows)
        object.__setattr__(self, "metrics", metrics)

    @property
    def attempted_case_count(self) -> int:
        return sum(row.engine_attempted for row in self.case_rows)

    @property
    def success_case_count(self) -> int:
        return sum(row.status == "success" for row in self.case_rows)

    @property
    def engine_failure_case_count(self) -> int:
        return sum(row.status == "engine_failure" for row in self.case_rows)

    @property
    def generated_pose_count(self) -> int:
        return sum(row.pose_count for row in self.case_rows)

    def _payload(self) -> dict[str, Any]:
        engine_flags = {
            f"{engine}_same_input_execution_performed": (
                engine == self.engine_id and self.attempted_case_count > 0
            )
            for engine in ("vina", "gnina", "smina")
        }
        blockers = list(POSEBUSTERS_EXTERNAL_BINARY_BLOCKERS)
        if self.engine_id == "smina":
            blockers.remove("gnina_energy_range_option_not_supported")
        return {
            "schema_id": self.schema_id,
            "engine_id": self.engine_id,
            "preparation_receipt_sha256": self.preparation_receipt_sha256,
            "preparation_receipt_file_sha256": self.preparation_receipt_file_sha256,
            "preparation_artifact_set_sha256": self.preparation_artifact_set_sha256,
            "preparation_runtime_identity_sha256": (
                self.preparation_runtime_identity_sha256
            ),
            "implementation_source_sha256": self.implementation_source_sha256,
            "implementation_source_members": dict(self.implementation_source_members),
            "runtime_identity": self.runtime_identity.to_dict(),
            "runtime_identity_sha256": self.runtime_identity.fingerprint_sha256,
            "configuration": POSEBUSTERS_EXTERNAL_BINARY_CONFIGURATIONS[self.engine_id],
            "configuration_sha256": self.configuration_sha256,
            "all_case_denominator": len(self.case_rows),
            "attempted_case_count": self.attempted_case_count,
            "success_case_count": self.success_case_count,
            "engine_failure_case_count": self.engine_failure_case_count,
            "generated_pose_count": self.generated_pose_count,
            "case_rows": [row.to_dict() for row in self.case_rows],
            "metrics": [row.to_dict() for row in self.metrics],
            "artifact_set_sha256": self.artifact_set_sha256,
            "external_engine_executed": self.attempted_case_count > 0,
            **engine_flags,
            "generated_pose_validity_evaluated": False,
            "symmetry_aware_rmsd_evaluated": False,
            "target_family_metrics_present": False,
            "leakage_receipt_present": False,
            "independent_external_rerun_present": False,
            "benchmark_executed": False,
            "scientific_blockers": blockers,
            "scientifically_validated": False,
            "claim_safe": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self._payload())

    def to_dict(self) -> dict[str, Any]:
        return {**self._payload(), "receipt_sha256": self.fingerprint_sha256}

    def write_json(self, output_path: str | os.PathLike[str]) -> Path:
        output = Path(output_path)
        output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        payload = _canonical_bytes(self.to_dict()) + b"\n"
        if len(payload) > POSEBUSTERS_EXTERNAL_BINARY_MAX_RECEIPT_BYTES:
            raise PoseBustersExternalBinaryExecutionError(
                "external binary receipt exceeds its byte bound"
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
                raise PoseBustersExternalBinaryExecutionError(
                    "external binary execution output already exists"
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


def _implementation_source_members() -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted(
            {
                "external_binary_execution": _source_file_sha256(__file__),
                "external_preparation_contract": _source_file_sha256(
                    Path(__file__).with_name(
                        "public_posebusters_external_preparation.py"
                    )
                ),
                "preparation_receipt_loader": _source_file_sha256(
                    Path(__file__).with_name("public_posebusters_vina_execution.py")
                ),
            }.items()
        )
    )


def _blocked_row(
    engine_id: str,
    prepared: _PreparedCaseView,
) -> PoseBustersExternalBinaryExecutionCase:
    status = {
        "preparation_failure": "blocked_preparation_failure",
        "upstream_failure": "blocked_upstream_failure",
        "abstain_chemistry_scope": "abstain_chemistry_scope",
    }[prepared.status]
    disposition = {
        "preparation_failure": "blocked_by_strict_preparation_failure",
        "upstream_failure": "blocked_by_upstream_preparation_input_failure",
        "abstain_chemistry_scope": "chemistry_scope_abstention",
    }[prepared.status]
    return PoseBustersExternalBinaryExecutionCase(
        engine_id=engine_id,
        case_id=prepared.case_id,
        status=status,
        disposition_code=disposition,
        preparation_status=prepared.status,
        preparation_disposition_code=prepared.disposition_code,
        error_code=prepared.error_code,
    )


def _execute_case(
    engine_id: str,
    prepared: _PreparedCaseView,
    prepared_payloads: dict[str, bytes],
    runtime: _ExternalRuntimeProtocol,
) -> tuple[PoseBustersExternalBinaryExecutionCase, dict[str, bytes]]:
    engine = _engine_id(engine_id)
    if prepared.status != "prepared":
        return _blocked_row(engine, prepared), {}
    artifacts = {row.role: row for row in prepared.artifacts}
    receptor = artifacts["prepared_receptor_pdbqt"]
    ligand = artifacts["prepared_ligand_pdbqt"]
    try:
        execution = runtime.execute(
            prepared_payloads[receptor.relative_path],
            prepared_payloads[ligand.relative_path],
            prepared.pocket_center_binary64_hex,
        )
    except PoseBustersExternalBinaryCaseError as exc:
        return PoseBustersExternalBinaryExecutionCase(
            engine_id=engine,
            case_id=prepared.case_id,
            status="engine_failure",
            disposition_code=exc.error_code,
            preparation_status=prepared.status,
            preparation_disposition_code=prepared.disposition_code,
            pocket_center_binary64_hex=prepared.pocket_center_binary64_hex,
            engine_attempted=True,
            error_stage=exc.stage,
            error_code=exc.error_code,
            error_type=exc.error_type,
            error_message_sha256=exc.error_message_sha256,
            diagnostic_sha256=exc.diagnostic_sha256,
            diagnostic_size_bytes=exc.diagnostic_size_bytes,
        ), {}
    except Exception as exc:
        return PoseBustersExternalBinaryExecutionCase(
            engine_id=engine,
            case_id=prepared.case_id,
            status="engine_failure",
            disposition_code=f"unclassified_{engine}_runtime_failure",
            preparation_status=prepared.status,
            preparation_disposition_code=prepared.disposition_code,
            pocket_center_binary64_hex=prepared.pocket_center_binary64_hex,
            engine_attempted=True,
            error_stage="runtime",
            error_code=f"unclassified_{engine}_runtime_failure",
            error_type=type(exc).__name__,
            error_message_sha256=_hash_bytes(_normalize_error(exc)),
            diagnostic_sha256=_hash_bytes(b""),
            diagnostic_size_bytes=0,
        ), {}
    relative = f"{prepared.case_id}/poses.pdbqt"
    artifact = PoseBustersExternalBinaryPoseArtifact(
        engine_id=engine,
        relative_path=relative,
        sha256=_hash_bytes(execution.poses_pdbqt),
        size_bytes=len(execution.poses_pdbqt),
        prepared_receptor_sha256=receptor.sha256,
        prepared_ligand_sha256=ligand.sha256,
    )
    return PoseBustersExternalBinaryExecutionCase(
        engine_id=engine,
        case_id=prepared.case_id,
        status="success",
        disposition_code=f"{engine}_generated_pose_artifact",
        preparation_status=prepared.status,
        preparation_disposition_code=prepared.disposition_code,
        pocket_center_binary64_hex=prepared.pocket_center_binary64_hex,
        engine_attempted=True,
        pose_scores=execution.pose_scores,
        pose_artifact=artifact,
        diagnostic_sha256=execution.diagnostic_sha256,
        diagnostic_size_bytes=execution.diagnostic_size_bytes,
    ), {relative: execution.poses_pdbqt}


def _roots_are_disjoint(paths: Sequence[Path]) -> bool:
    return all(
        first != second and first not in second.parents and second not in first.parents
        for index, first in enumerate(paths)
        for second in paths[index + 1 :]
    )


def _build_execution(
    engine_id: str,
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    output_artifact_root: str | os.PathLike[str],
    scratch_root: str | os.PathLike[str],
    executable_path: str | os.PathLike[str],
    dynamic_library_dirs: Sequence[str | os.PathLike[str]],
    *,
    expected_preparation_receipt_sha256: str,
) -> tuple[PoseBustersExternalBinaryExecutionReceipt, dict[str, bytes]]:
    engine = _engine_id(engine_id)
    preparation_root = Path(preparation_artifact_root).resolve(strict=False)
    output_root = Path(output_artifact_root).resolve(strict=False)
    scratch = Path(scratch_root).resolve(strict=False)
    executable = Path(executable_path).resolve(strict=False)
    if not _roots_are_disjoint((preparation_root, output_root, scratch)):
        raise PoseBustersExternalBinaryExecutionError(
            "preparation, output, and scratch roots must be disjoint"
        )
    if (
        executable == output_root
        or output_root in executable.parents
        or executable == scratch
        or scratch in executable.parents
    ):
        raise PoseBustersExternalBinaryExecutionError(
            "external executable must not be below output or scratch root"
        )
    try:
        preparation, prepared_payloads = _load_preparation_receipt(
            preparation_receipt_path,
            preparation_artifact_root,
            expected_receipt_sha256=expected_preparation_receipt_sha256,
        )
    except (PoseBustersVinaExecutionError, PoseBustersExternalPreparationError) as exc:
        raise PoseBustersExternalBinaryExecutionError(
            "strict preparation receipt or artifact tree did not verify"
        ) from exc
    configuration = POSEBUSTERS_EXTERNAL_BINARY_CONFIGURATIONS[engine]
    if (
        _canonical_sha256(configuration)
        != (POSEBUSTERS_EXTERNAL_BINARY_CONFIGURATION_SHA256[engine])
    ):
        raise PoseBustersExternalBinaryExecutionError(
            "external binary frozen configuration was mutated"
        )
    runtime = _load_runtime(
        engine,
        executable_path,
        dynamic_library_dirs,
        Path(scratch_root),
    )
    rows: list[PoseBustersExternalBinaryExecutionCase] = []
    payloads: dict[str, bytes] = {}
    for prepared in preparation.case_rows:
        row, case_payloads = _execute_case(
            engine,
            prepared,
            prepared_payloads,
            runtime,
        )
        rows.append(row)
        for relative, source in case_payloads.items():
            if relative in payloads:
                raise PoseBustersExternalBinaryExecutionError(
                    "external binary artifact path is duplicated"
                )
            payloads[relative] = source
    rows_tuple = tuple(rows)
    members = _implementation_source_members()
    return (
        PoseBustersExternalBinaryExecutionReceipt(
            engine_id=engine,
            preparation_receipt_sha256=preparation.receipt_sha256,
            preparation_receipt_file_sha256=preparation.receipt_file_sha256,
            preparation_artifact_set_sha256=preparation.artifact_set_sha256,
            preparation_runtime_identity_sha256=(preparation.runtime_identity_sha256),
            implementation_source_sha256=_canonical_sha256(dict(members)),
            implementation_source_members=members,
            runtime_identity=runtime.identity,
            configuration_sha256=(
                POSEBUSTERS_EXTERNAL_BINARY_CONFIGURATION_SHA256[engine]
            ),
            case_rows=rows_tuple,
            metrics=_summary_metrics(engine, rows_tuple),
            artifact_set_sha256=_artifact_set_sha256(rows_tuple),
        ),
        payloads,
    )


def materialize_posebusters_external_binary_execution(
    engine_id: str,
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    output_artifact_root: str | os.PathLike[str],
    scratch_root: str | os.PathLike[str],
    executable_path: str | os.PathLike[str],
    dynamic_library_dirs: Sequence[str | os.PathLike[str]] = (),
    *,
    expected_preparation_receipt_sha256: str,
) -> PoseBustersExternalBinaryExecutionReceipt:
    """Run a pinned GNINA or Smina executable and materialize exact artifacts."""

    receipt, payloads = _build_execution(
        engine_id,
        preparation_receipt_path,
        preparation_artifact_root,
        output_artifact_root,
        scratch_root,
        executable_path,
        dynamic_library_dirs,
        expected_preparation_receipt_sha256=(expected_preparation_receipt_sha256),
    )
    try:
        _write_artifact_tree(Path(output_artifact_root), payloads)
    except PoseBustersExternalPreparationError as exc:
        raise PoseBustersExternalBinaryExecutionError(
            "external binary artifact tree could not be materialized"
        ) from exc
    return receipt


def verify_posebusters_external_binary_execution_receipt(
    execution_receipt_path: str | os.PathLike[str],
    engine_id: str,
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    output_artifact_root: str | os.PathLike[str],
    scratch_root: str | os.PathLike[str],
    executable_path: str | os.PathLike[str],
    dynamic_library_dirs: Sequence[str | os.PathLike[str]] = (),
    *,
    expected_preparation_receipt_sha256: str,
) -> PoseBustersExternalBinaryExecutionReceipt:
    """Require exact engine reexecution, artifact equality, and receipt bytes."""

    source = _read_exact_regular_file(
        execution_receipt_path,
        maximum_bytes=POSEBUSTERS_EXTERNAL_BINARY_MAX_RECEIPT_BYTES,
    )
    expected, payloads = _build_execution(
        engine_id,
        preparation_receipt_path,
        preparation_artifact_root,
        output_artifact_root,
        scratch_root,
        executable_path,
        dynamic_library_dirs,
        expected_preparation_receipt_sha256=(expected_preparation_receipt_sha256),
    )
    if source != _canonical_bytes(expected.to_dict()) + b"\n":
        raise PoseBustersExternalBinaryExecutionError(
            "external binary receipt does not match exact reexecution"
        )
    try:
        _verify_artifact_tree(Path(output_artifact_root), payloads)
    except PoseBustersExternalPreparationError as exc:
        raise PoseBustersExternalBinaryExecutionError(
            "external binary artifact tree does not match exact reexecution"
        ) from exc
    return expected


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2-posebusters-external-execute",
        description="Execute pinned GNINA or Smina with all-case rows.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("materialize", "verify"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument(
            "--engine", choices=POSEBUSTERS_EXTERNAL_BINARY_ENGINES, required=True
        )
        subparser.add_argument("--preparation-receipt", required=True)
        subparser.add_argument("--preparation-artifact-root", required=True)
        subparser.add_argument("--expected-preparation-receipt-sha256", required=True)
        subparser.add_argument("--output-artifact-root", required=True)
        subparser.add_argument("--scratch-root", required=True)
        subparser.add_argument("--executable", required=True)
        subparser.add_argument(
            "--dynamic-library-dir",
            action="append",
            default=[],
        )
    subparsers.choices["materialize"].add_argument("--output", required=True)
    subparsers.choices["verify"].add_argument(
        "--execution-receipt",
        required=True,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    common = {
        "engine_id": args.engine,
        "preparation_receipt_path": args.preparation_receipt,
        "preparation_artifact_root": args.preparation_artifact_root,
        "output_artifact_root": args.output_artifact_root,
        "scratch_root": args.scratch_root,
        "executable_path": args.executable,
        "dynamic_library_dirs": tuple(args.dynamic_library_dir),
        "expected_preparation_receipt_sha256": (
            args.expected_preparation_receipt_sha256
        ),
    }
    if args.command == "materialize":
        if Path(args.output).exists():
            raise PoseBustersExternalBinaryExecutionError(
                "external binary execution output already exists"
            )
        receipt = materialize_posebusters_external_binary_execution(**common)
        receipt.write_json(args.output)
    else:
        receipt = verify_posebusters_external_binary_execution_receipt(
            execution_receipt_path=args.execution_receipt,
            **common,
        )
    print(
        json.dumps(
            {
                "engine_id": receipt.engine_id,
                "receipt_sha256": receipt.fingerprint_sha256,
                "all_case_denominator": len(receipt.case_rows),
                "attempted_case_count": receipt.attempted_case_count,
                "success_case_count": receipt.success_case_count,
                "engine_failure_case_count": receipt.engine_failure_case_count,
                "generated_pose_count": receipt.generated_pose_count,
                "benchmark_executed": False,
                "claim_safe": False,
            },
            sort_keys=True,
        )
    )
    return 0


__all__ = [
    "POSEBUSTERS_EXTERNAL_BINARY_CONFIGURATIONS",
    "POSEBUSTERS_EXTERNAL_BINARY_CONFIGURATION_SHA256",
    "POSEBUSTERS_EXTERNAL_BINARY_ENGINES",
    "POSEBUSTERS_EXTERNAL_BINARY_EXECUTION_SCHEMA_ID",
    "PoseBustersExternalBinaryDependency",
    "PoseBustersExternalBinaryExecutionCase",
    "PoseBustersExternalBinaryExecutionError",
    "PoseBustersExternalBinaryExecutionMetric",
    "PoseBustersExternalBinaryExecutionReceipt",
    "PoseBustersExternalBinaryPoseArtifact",
    "PoseBustersExternalBinaryPoseScore",
    "PoseBustersExternalBinaryRuntimeIdentity",
    "main",
    "materialize_posebusters_external_binary_execution",
    "verify_posebusters_external_binary_execution_receipt",
]


if __name__ == "__main__":
    raise SystemExit(main())
