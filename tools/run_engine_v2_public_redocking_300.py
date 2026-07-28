#!/usr/bin/env python3
"""Run the frozen 300-case Engine V2/Vina/GNINA redocking comparison."""

from __future__ import annotations

import argparse
from contextlib import contextmanager, ExitStack
import ctypes
from dataclasses import replace
from functools import lru_cache
import hashlib
from io import BytesIO
from importlib import metadata
import json
import math
import os
from pathlib import Path
import platform
import shutil
import stat
import subprocess
import sys
import time
from typing import Iterator, Mapping, Sequence
import uuid

import torch

import betelgeuze_engine_v2.benchmark.public_redocking_benchmark as benchmark_contract
from betelgeuze_engine_v2.benchmark import (
    FROZEN_PUBLIC_REDOCKING_CASE_IDS,
    PUBLIC_REDOCKING_ALLOWED_TORCH_VERSIONS,
    PUBLIC_REDOCKING_CASE_SEED_BASE,
    PUBLIC_REDOCKING_ENGINEERING_SMOKE_CASE_IDS,
    PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_COUNT,
    PUBLIC_REDOCKING_PRIMARY_BLIND_HOLDOUT_CASE_IDS,
    PUBLIC_REDOCKING_PRIMARY_ENGINES,
    PUBLIC_REDOCKING_RUNNER_ID,
    PublicRedockingCaseProfile,
    PublicRedockingCaseResult,
    PublicRedockingEngineV2CandidateDiagnostic,
    PublicRedockingEngineV2Diagnostics,
    PublicRedockingEngineIdentity,
    PublicRedockingEvaluationPolicy,
    VerifiedCaseMaterialization,
    VerifiedPublicRedockingCaseExecution,
    VerifiedPublicRedockingArchive,
    build_public_redocking_benchmark_report,
    frozen_public_redocking_case_seed,
    frozen_public_redocking_profiles,
    verify_public_redocking_source_identifiers,
)
from betelgeuze_engine_v2.docking import (
    ChemistryPoseScorerV1,
    DockingBudget,
    DockingAuthorityError,
    DockingSearchError,
    DockingScope,
    ElementAwareValidityError,
    PocketDefinition,
    ScorerV1Error,
    build_element_aware_authenticated_known_pocket_docking_problem,
    build_guided_placement_context,
    run_authenticated_scorer_v1_guided_search,
)
from betelgeuze_engine_v2.io import (
    PDBParseError,
    SDFParseError,
    parse_pdb,
    parse_sdf_v2000,
)
from betelgeuze_engine_v2.molecular import AllAtomSystem


RUNNER_ID = PUBLIC_REDOCKING_RUNNER_ID
DEFAULT_SEED = PUBLIC_REDOCKING_CASE_SEED_BASE
POSEBUSTERS_VERSION = "0.3.1"
RDKit_VERSION = "2022.09.5"
EVALUATOR_DISTRIBUTION_VERSIONS = {
    "numpy": "1.26.4",
    "pandas": "2.3.3",
    "PyYAML": "6.0.3",
    "rdkit-pypi": "2022.9.5",
    "posebusters": POSEBUSTERS_VERSION,
}
_RUNTIME_ENVIRONMENT_KEYS = (
    "CUDA_VISIBLE_DEVICES",
    "HIP_VISIBLE_DEVICES",
    "LANG",
    "LC_ALL",
    "LD_LIBRARY_PATH",
    "LD_PRELOAD",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "ROCR_VISIBLE_DEVICES",
    "VECLIB_MAXIMUM_THREADS",
)
RECEPTOR_CHARGE_METHOD_ID = (
    "betelgeuze.public_redocking_standard_residue_formal_charge_proxy/1.0.0"
)
LIGAND_CHARGE_METHOD_ID = "rdkit_gasteiger_12_iter_conserved/2022.09.5"
ENGINE_V2_CANDIDATE_COUNT = PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_COUNT
ENGINE_V2_CPU_POLICY = {
    "cpu_count": 1,
    "torch_intraop_threads": 1,
    "torch_interop_threads": 1,
    "torch_version": str(torch.__version__),
}
_CASE_FILE_SUFFIXES = (
    "protein.pdb",
    "ligands.sdf",
    "ligand.sdf",
    "ligand_start_conf.sdf",
)
_EXTERNAL_INPUT_ALIAS_NAMES = {
    "receptor": "receptor.pdb",
    "reference": "reference.sdf",
    "native": "native.sdf",
    "seed": "seed.sdf",
}
_INOTIFY_DIRECTORY_MUTATION_MASK = (
    0x00000004  # IN_ATTRIB
    | 0x00000040  # IN_MOVED_FROM
    | 0x00000080  # IN_MOVED_TO
    | 0x00000100  # IN_CREATE
    | 0x00000200  # IN_DELETE
    | 0x00000400  # IN_DELETE_SELF
    | 0x00000800  # IN_MOVE_SELF
)
_INOTIFY_FILE_MUTATION_MASK = (
    0x00000002  # IN_MODIFY
    | 0x00000004  # IN_ATTRIB
    | 0x00000008  # IN_CLOSE_WRITE
)
CHEMICAL_COLUMNS = (
    "sanitization",
    "inchi_convertible",
    "all_atoms_connected",
    "molecular_formula",
    "molecular_bonds",
    "double_bond_stereochemistry",
    "tetrahedral_chirality",
    "bond_lengths",
    "bond_angles",
    "internal_steric_clash",
    "aromatic_ring_flatness",
    "double_bond_flatness",
    "internal_energy",
)
GEOMETRIC_COLUMNS = (
    "protein-ligand_maximum_distance",
    "minimum_distance_to_protein",
    "minimum_distance_to_organic_cofactors",
    "minimum_distance_to_inorganic_cofactors",
    "minimum_distance_to_waters",
    "volume_overlap_with_protein",
    "volume_overlap_with_organic_cofactors",
    "volume_overlap_with_inorganic_cofactors",
    "volume_overlap_with_waters",
)


class PublicRedockingRunnerError(RuntimeError):
    """The local operator run cannot preserve its frozen evidence contract."""


class EngineV2CaseFailure(PublicRedockingRunnerError):
    """One source case is outside the bounded Engine V2 execution lane."""

    failure_code = "engine_v2_case_failed"


class IncompleteRankedPoseSet(EngineV2CaseFailure):
    """Engine V2 did not produce exactly five serializable ranked poses."""

    failure_code = "engine_v2_pose_count_incomplete"


class InvalidRankedPoseSet(EngineV2CaseFailure):
    """Engine V2 produced ranked coordinates that cannot represent the ligand."""


class EngineV2PreparationFailure(EngineV2CaseFailure):
    """Engine V2 could not complete its case-local preparation stage."""

    def __init__(
        self,
        preparation_failure_code: str,
        message: str,
        *,
        failure_code: str = "engine_v2_case_failed",
    ) -> None:
        super().__init__(message)
        self.preparation_failure_code = preparation_failure_code
        self.failure_code = failure_code


class EngineV2SearchCaseFailure(EngineV2CaseFailure):
    """Engine V2 failed after preparation and retains its fixed denominator."""

    def __init__(
        self,
        message: str,
        *,
        diagnostics: PublicRedockingEngineV2Diagnostics,
        failure_code: str = "engine_v2_case_failed",
        diagnostic_evaluation_seconds: float = 0.0,
    ) -> None:
        super().__init__(message)
        self.diagnostics = diagnostics
        self.failure_code = failure_code
        self.diagnostic_evaluation_seconds = diagnostic_evaluation_seconds


class EngineV2PoseSearchOutcome:
    __slots__ = (
        "diagnostic_evaluation_seconds",
        "diagnostics",
        "ranked_coordinates",
    )

    def __init__(
        self,
        *,
        ranked_coordinates: tuple[torch.Tensor, ...],
        diagnostics: PublicRedockingEngineV2Diagnostics,
        diagnostic_evaluation_seconds: float = 0.0,
    ) -> None:
        self.ranked_coordinates = tuple(ranked_coordinates)
        self.diagnostics = diagnostics
        self.diagnostic_evaluation_seconds = float(
            diagnostic_evaluation_seconds
        )


class ExecutionEnvironmentIdentity:
    __slots__ = (
        "boot_session_id_available",
        "sha256",
        "timed_cache_reusable",
    )

    def __init__(
        self,
        *,
        sha256: str,
        boot_session_id_available: bool,
        timed_cache_reusable: bool,
    ) -> None:
        self.sha256 = sha256
        self.boot_session_id_available = boot_session_id_available
        self.timed_cache_reusable = timed_cache_reusable


class PinnedExternalBinary:
    __slots__ = ("_closed", "descriptor", "path", "sha256")

    def __init__(self, path: Path, sha256: str) -> None:
        self.path = Path(os.path.abspath(path))
        self.sha256 = sha256
        self.descriptor = -1
        self._closed = True
        flags = os.O_RDONLY
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            self.descriptor = os.open(self.path, flags)
        except OSError as exc:
            raise PublicRedockingRunnerError(
                "staged GNINA binary cannot be pinned by file descriptor"
            ) from exc
        self._closed = False

    @property
    def execution_path(self) -> str:
        if self._closed:
            raise PublicRedockingRunnerError("staged GNINA descriptor is closed")
        descriptor_root = Path("/proc/self/fd")
        if platform.system() != "Linux" or not descriptor_root.is_dir():
            raise PublicRedockingRunnerError(
                "GNINA benchmark requires Linux descriptor-based execution"
            )
        return str(descriptor_root / str(self.descriptor))

    def close(self) -> None:
        if not self._closed:
            os.close(self.descriptor)
            self._closed = True

    def __enter__(self) -> "PinnedExternalBinary":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except (AttributeError, OSError):
            pass


class PinnedCaseInputs:
    __slots__ = (
        "_closed",
        "_descriptors",
        "_expected_sha256s",
        "_external_alias_descriptor",
        "_external_alias_directory",
        "_external_alias_identity",
        "_input_monitor_compromised",
        "_input_monitor_descriptor",
        "_logical_paths",
    )

    def __init__(
        self,
        logical_paths: Mapping[str, Path],
        expected_sha256s: Mapping[str, str],
    ) -> None:
        self._logical_paths = dict(logical_paths)
        self._expected_sha256s = dict(expected_sha256s)
        self._descriptors: dict[str, int] = {}
        self._external_alias_descriptor = -1
        self._external_alias_directory = self._logical_paths["directory"].parent / (
            f".{self._logical_paths['directory'].name}.pinned-{uuid.uuid4().hex}"
        )
        self._external_alias_identity: tuple[int, int, int, int, int, int] | None = None
        self._input_monitor_compromised = False
        self._input_monitor_descriptor = -1
        self._closed = True
        _require_case_input_identity(
            self._logical_paths,
            self._expected_sha256s,
        )
        flags = os.O_RDONLY
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            for role in ("receptor", "reference", "native", "seed"):
                path = self._logical_paths[role]
                descriptor = os.open(path, flags)
                self._descriptors[role] = descriptor
                path_status = path.lstat()
                descriptor_status = os.fstat(descriptor)
                if (
                    not stat.S_ISREG(descriptor_status.st_mode)
                    or (path_status.st_dev, path_status.st_ino)
                    != (descriptor_status.st_dev, descriptor_status.st_ino)
                    or _sha256_descriptor(descriptor) != self._expected_sha256s[role]
                ):
                    raise PublicRedockingRunnerError(
                        f"materialized {role} input could not be pinned"
                    )
            self._create_external_aliases()
            self._closed = False
            self.verify()
        except BaseException:
            self._close_input_monitor()
            try:
                self._remove_external_aliases(require_verified=False)
            except (OSError, PublicRedockingRunnerError):
                pass
            for descriptor in self._descriptors.values():
                os.close(descriptor)
            self._descriptors.clear()
            raise

    def _create_external_aliases(self) -> None:
        parent_descriptor = _owned_directory_descriptor(
            self._external_alias_directory.parent,
            create=False,
        )
        directory_flags = os.O_RDONLY
        if hasattr(os, "O_DIRECTORY"):
            directory_flags |= os.O_DIRECTORY
        if hasattr(os, "O_CLOEXEC"):
            directory_flags |= os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            directory_flags |= os.O_NOFOLLOW
        try:
            os.mkdir(
                self._external_alias_directory.name,
                0o700,
                dir_fd=parent_descriptor,
            )
            self._external_alias_descriptor = os.open(
                self._external_alias_directory.name,
                directory_flags,
                dir_fd=parent_descriptor,
            )
            for role, alias_name in _EXTERNAL_INPUT_ALIAS_NAMES.items():
                os.link(
                    self._logical_paths[role],
                    alias_name,
                    dst_dir_fd=self._external_alias_descriptor,
                    follow_symlinks=False,
                )
            self._verify_external_aliases(require_monitor=False)
            os.fchmod(self._external_alias_descriptor, 0o500)
            if stat.S_IMODE(os.fstat(self._external_alias_descriptor).st_mode) != 0o500:
                raise PublicRedockingRunnerError(
                    "external input alias directory permissions are invalid"
                )
            self._external_alias_identity = self._external_alias_status_identity(
                os.fstat(self._external_alias_descriptor)
            )
            self._start_input_monitor()
        except OSError as exc:
            raise PublicRedockingRunnerError(
                "external input aliases could not be pinned"
            ) from exc
        finally:
            os.close(parent_descriptor)

    @staticmethod
    def _external_alias_status_identity(
        status: os.stat_result,
    ) -> tuple[int, int, int, int, int, int]:
        return (
            status.st_dev,
            status.st_ino,
            status.st_uid,
            stat.S_IMODE(status.st_mode),
            status.st_ctime_ns,
            status.st_mtime_ns,
        )

    def _start_input_monitor(self) -> None:
        try:
            libc = ctypes.CDLL(None, use_errno=True)
            inotify_init1 = libc.inotify_init1
            inotify_add_watch = libc.inotify_add_watch
        except (AttributeError, OSError) as exc:
            raise PublicRedockingRunnerError(
                "Linux input mutation monitoring is unavailable"
            ) from exc
        inotify_init1.argtypes = (ctypes.c_int,)
        inotify_init1.restype = ctypes.c_int
        inotify_add_watch.argtypes = (
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint32,
        )
        inotify_add_watch.restype = ctypes.c_int
        descriptor = inotify_init1(
            getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NONBLOCK", 0)
        )
        if descriptor < 0:
            error_number = ctypes.get_errno()
            raise PublicRedockingRunnerError(
                "Linux input mutation monitor could not be opened"
            ) from OSError(error_number, os.strerror(error_number))
        targets = (
            (
                Path("/proc/self/fd") / str(self._external_alias_descriptor),
                _INOTIFY_DIRECTORY_MUTATION_MASK,
            ),
            *(
                (
                    Path("/proc/self/fd") / str(self._descriptors[role]),
                    _INOTIFY_FILE_MUTATION_MASK,
                )
                for role in ("receptor", "reference", "native", "seed")
            ),
        )
        try:
            for path, mask in targets:
                watch_descriptor = inotify_add_watch(
                    descriptor,
                    os.fsencode(path),
                    mask,
                )
                if watch_descriptor < 0:
                    error_number = ctypes.get_errno()
                    raise OSError(error_number, os.strerror(error_number))
        except OSError as exc:
            os.close(descriptor)
            raise PublicRedockingRunnerError(
                "pinned inputs could not be monitored for mutation"
            ) from exc
        self._input_monitor_descriptor = descriptor
        self._input_monitor_compromised = False
        self._require_quiet_input_monitor()

    def _require_quiet_input_monitor(self) -> None:
        if self._input_monitor_compromised:
            raise PublicRedockingRunnerError(
                "pinned input mutation monitor observed a change"
            )
        if self._input_monitor_descriptor < 0:
            raise PublicRedockingRunnerError(
                "pinned input mutation monitor is not active"
            )
        try:
            events = os.read(self._input_monitor_descriptor, 64 * 1024)
        except BlockingIOError:
            return
        except OSError as exc:
            raise PublicRedockingRunnerError(
                "pinned input mutation monitor failed"
            ) from exc
        if events:
            self._input_monitor_compromised = True
            raise PublicRedockingRunnerError(
                "pinned input mutation monitor observed a change"
            )

    def _close_input_monitor(self) -> None:
        if self._input_monitor_descriptor >= 0:
            os.close(self._input_monitor_descriptor)
            self._input_monitor_descriptor = -1

    def _verify_external_aliases(self, *, require_monitor: bool = True) -> None:
        if self._external_alias_descriptor < 0:
            raise PublicRedockingRunnerError(
                "external input alias directory is not open"
            )
        if require_monitor:
            self._require_quiet_input_monitor()
        directory_status = os.fstat(self._external_alias_descriptor)
        if (
            not stat.S_ISDIR(directory_status.st_mode)
            or (hasattr(os, "geteuid") and directory_status.st_uid != os.geteuid())
            or set(os.listdir(self._external_alias_descriptor))
            != set(_EXTERNAL_INPUT_ALIAS_NAMES.values())
            or (
                self._external_alias_identity is not None
                and self._external_alias_status_identity(directory_status)
                != self._external_alias_identity
            )
        ):
            raise PublicRedockingRunnerError("external input alias directory changed")
        for role, alias_name in _EXTERNAL_INPUT_ALIAS_NAMES.items():
            alias_status = os.stat(
                alias_name,
                dir_fd=self._external_alias_descriptor,
                follow_symlinks=False,
            )
            descriptor_status = os.fstat(self._descriptors[role])
            if (
                not stat.S_ISREG(alias_status.st_mode)
                or (alias_status.st_dev, alias_status.st_ino)
                != (descriptor_status.st_dev, descriptor_status.st_ino)
                or _sha256_descriptor(self._descriptors[role])
                != self._expected_sha256s[role]
            ):
                raise PublicRedockingRunnerError(f"external {role} input alias changed")

    def _remove_external_aliases(self, *, require_verified: bool) -> None:
        if self._external_alias_descriptor < 0:
            return
        directory_descriptor = self._external_alias_descriptor
        directory_status = os.fstat(directory_descriptor)
        expected_names = set(_EXTERNAL_INPUT_ALIAS_NAMES.values())
        if require_verified:
            self._verify_external_aliases()
        self._close_input_monitor()
        observed_names = set(os.listdir(directory_descriptor))
        if not require_verified and not observed_names.issubset(expected_names):
            raise PublicRedockingRunnerError(
                "external input alias cleanup found unexpected entries"
            )
        try:
            os.fchmod(directory_descriptor, 0o700)
            for alias_name in observed_names:
                os.unlink(alias_name, dir_fd=directory_descriptor)
            os.fsync(directory_descriptor)
            os.close(directory_descriptor)
            self._external_alias_descriptor = -1
            self._external_alias_identity = None
            parent_descriptor = _owned_directory_descriptor(
                self._external_alias_directory.parent,
                create=False,
            )
            try:
                current_status = os.stat(
                    self._external_alias_directory.name,
                    dir_fd=parent_descriptor,
                    follow_symlinks=False,
                )
                if (current_status.st_dev, current_status.st_ino) != (
                    directory_status.st_dev,
                    directory_status.st_ino,
                ):
                    raise PublicRedockingRunnerError(
                        "external input alias directory changed before cleanup"
                    )
                os.rmdir(
                    self._external_alias_directory.name,
                    dir_fd=parent_descriptor,
                )
                os.fsync(parent_descriptor)
            finally:
                os.close(parent_descriptor)
        except OSError as exc:
            raise PublicRedockingRunnerError(
                "external input aliases could not be removed safely"
            ) from exc

    @property
    def descriptors(self) -> tuple[int, ...]:
        if self._closed:
            raise PublicRedockingRunnerError("case input descriptors are closed")
        return (
            *(self._descriptors[role] for role in sorted(self._descriptors)),
            self._external_alias_descriptor,
        )

    @property
    def execution_paths(self) -> dict[str, Path]:
        if self._closed:
            raise PublicRedockingRunnerError("case input descriptors are closed")
        return {
            "directory": self._logical_paths["directory"],
            **{
                role: Path("/proc/self/fd") / str(self._descriptors[role])
                for role in ("receptor", "reference", "native", "seed")
            },
        }

    @property
    def external_execution_paths(self) -> dict[str, Path]:
        if self._closed or self._external_alias_descriptor < 0:
            raise PublicRedockingRunnerError("case input descriptors are closed")
        directory = Path("/proc/self/fd") / str(self._external_alias_descriptor)
        return {
            "directory": directory,
            **{
                role: directory / alias_name
                for role, alias_name in _EXTERNAL_INPUT_ALIAS_NAMES.items()
            },
        }

    def verify(self) -> None:
        if self._closed:
            raise PublicRedockingRunnerError("case input descriptors are closed")
        _require_case_input_identity(
            self._logical_paths,
            self._expected_sha256s,
        )
        for role, descriptor in self._descriptors.items():
            path_status = self._logical_paths[role].lstat()
            descriptor_status = os.fstat(descriptor)
            if (
                not stat.S_ISREG(descriptor_status.st_mode)
                or (path_status.st_dev, path_status.st_ino)
                != (descriptor_status.st_dev, descriptor_status.st_ino)
                or _sha256_descriptor(descriptor) != self._expected_sha256s[role]
            ):
                raise PublicRedockingRunnerError(
                    f"pinned {role} input changed during the benchmark"
                )
        self._verify_external_aliases()

    @contextmanager
    def verified_window(self) -> Iterator[None]:
        self.verify()
        try:
            yield
        finally:
            self.verify()

    def close(self) -> None:
        if not self._closed:
            try:
                self.verify()
                self._remove_external_aliases(require_verified=True)
            finally:
                self._close_input_monitor()
                if self._external_alias_descriptor >= 0:
                    os.close(self._external_alias_descriptor)
                    self._external_alias_descriptor = -1
                    self._external_alias_identity = None
                for descriptor in self._descriptors.values():
                    os.close(descriptor)
                self._descriptors.clear()
                self._closed = True

    def __enter__(self) -> "PinnedCaseInputs":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except (AttributeError, OSError):
            pass


_ENGINE_V2_CASE_EXCEPTIONS = (
    DockingAuthorityError,
    DockingSearchError,
    ElementAwareValidityError,
    EngineV2CaseFailure,
    PDBParseError,
    ScorerV1Error,
    SDFParseError,
    UnicodeDecodeError,
)


def _configure_engine_v2_cpu() -> None:
    if (
        ENGINE_V2_CPU_POLICY["torch_version"]
        not in PUBLIC_REDOCKING_ALLOWED_TORCH_VERSIONS
    ):
        raise PublicRedockingRunnerError(
            "Engine V2 Torch build is outside the frozen runtime set"
        )
    torch.set_num_threads(ENGINE_V2_CPU_POLICY["torch_intraop_threads"])
    if torch.get_num_interop_threads() != ENGINE_V2_CPU_POLICY["torch_interop_threads"]:
        torch.set_num_interop_threads(ENGINE_V2_CPU_POLICY["torch_interop_threads"])
    if (
        torch.get_num_threads() != ENGINE_V2_CPU_POLICY["torch_intraop_threads"]
        or torch.get_num_interop_threads()
        != ENGINE_V2_CPU_POLICY["torch_interop_threads"]
    ):
        raise PublicRedockingRunnerError(
            "Engine V2 could not enforce the frozen one-CPU Torch policy"
        )


def _external_execution_policy(timeout_seconds: int) -> dict[str, object]:
    return {
        "cpu_count": 1,
        "timeout_seconds": timeout_seconds,
    }


def _execution_policy_tokens(policy: dict[str, object]) -> tuple[str, ...]:
    if not policy:
        raise PublicRedockingRunnerError("execution policy cannot be empty")
    return tuple(
        f"{key}={json.dumps(value, allow_nan=False, separators=(',', ':'))}"
        for key, value in sorted(policy.items())
    )


def _evaluator_environment_versions() -> dict[str, str]:
    observed: dict[str, str] = {}
    for distribution, expected in EVALUATOR_DISTRIBUTION_VERSIONS.items():
        try:
            version = metadata.version(distribution)
        except metadata.PackageNotFoundError as exc:
            raise PublicRedockingRunnerError(
                f"evaluator dependency is missing: {distribution}"
            ) from exc
        if version != expected:
            raise PublicRedockingRunnerError(
                f"evaluator dependency {distribution} must equal {expected}"
            )
        observed[distribution] = version
    return observed


@lru_cache(maxsize=1)
def _evaluator_distribution_payload_sha256s() -> dict[str, str]:
    payload_sha256s: dict[str, str] = {}
    for distribution_name in EVALUATOR_DISTRIBUTION_VERSIONS:
        try:
            distribution = metadata.distribution(distribution_name)
        except metadata.PackageNotFoundError as exc:
            raise PublicRedockingRunnerError(
                f"evaluator dependency is missing: {distribution_name}"
            ) from exc
        files = tuple(distribution.files or ())
        if not files:
            raise PublicRedockingRunnerError(
                f"evaluator dependency has no installed-file record: {distribution_name}"
            )
        rows: list[tuple[object, ...]] = []
        for relative_path in sorted(files, key=str):
            path = Path(distribution.locate_file(relative_path))
            try:
                status = path.lstat()
            except FileNotFoundError:
                rows.append((str(relative_path), "missing"))
                continue
            except OSError as exc:
                raise PublicRedockingRunnerError(
                    f"evaluator dependency file cannot be identified: {distribution_name}"
                ) from exc
            if stat.S_ISLNK(status.st_mode):
                rows.append(
                    (
                        str(relative_path),
                        "symlink",
                        os.readlink(path),
                    )
                )
            elif stat.S_ISREG(status.st_mode):
                rows.append(
                    (
                        str(relative_path),
                        "regular",
                        status.st_size,
                        _sha256_path(path),
                    )
                )
            else:
                rows.append(
                    (
                        str(relative_path),
                        "other",
                        stat.S_IFMT(status.st_mode),
                    )
                )
        payload_sha256s[distribution_name] = _sha256_bytes(_canonical_bytes(rows))
    return dict(sorted(payload_sha256s.items()))


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_descriptor(descriptor: int) -> str:
    digest = hashlib.sha256()
    offset = 0
    while True:
        chunk = os.pread(descriptor, 1024 * 1024, offset)
        if not chunk:
            break
        digest.update(chunk)
        offset += len(chunk)
    return digest.hexdigest()


def _bytes_from_descriptor(descriptor: int) -> bytes:
    chunks: list[bytes] = []
    offset = 0
    while True:
        chunk = os.pread(descriptor, 1024 * 1024, offset)
        if not chunk:
            break
        chunks.append(chunk)
        offset += len(chunk)
    return b"".join(chunks)


@lru_cache(maxsize=1)
def _static_runtime_environment_projection() -> dict[str, object]:
    try:
        affinity = (
            sorted(os.sched_getaffinity(0))
            if hasattr(os, "sched_getaffinity")
            else None
        )
    except OSError:
        affinity = None
    cpu_fields: dict[str, set[str]] = {}
    try:
        for line in (
            Path("/proc/cpuinfo")
            .read_text(
                encoding="ascii",
                errors="replace",
            )
            .splitlines()
        ):
            if ":" not in line:
                continue
            key, value = (part.strip() for part in line.split(":", 1))
            if key in {
                "cpu family",
                "flags",
                "microcode",
                "model",
                "model name",
                "stepping",
                "vendor_id",
            }:
                cpu_fields.setdefault(key, set()).add(value)
    except OSError:
        cpu_fields = {}
    loaded_paths: set[str] = set()
    try:
        for line in (
            Path("/proc/self/maps")
            .read_text(
                encoding="utf-8",
                errors="replace",
            )
            .splitlines()
        ):
            fields = line.split(None, 5)
            if len(fields) == 6 and fields[5].startswith("/"):
                loaded_paths.add(fields[5].removesuffix(" (deleted)"))
    except OSError:
        loaded_paths = set()
    loaded_rows: list[tuple[object, ...]] = []
    for value in sorted(loaded_paths):
        path = Path(value)
        try:
            status = path.lstat()
            if stat.S_ISREG(status.st_mode):
                loaded_rows.append((value, status.st_size, _sha256_path(path)))
            else:
                loaded_rows.append((value, "non_regular"))
        except OSError:
            loaded_rows.append((value, "unavailable"))
    executable = Path(sys.executable)
    return {
        "cpu_affinity": affinity,
        "cpu_identity": {
            key: sorted(values) for key, values in sorted(cpu_fields.items())
        },
        "environment_value_sha256s": {
            key: (
                None
                if key not in os.environ
                else _sha256_bytes(os.environ[key].encode("utf-8"))
            )
            for key in _RUNTIME_ENVIRONMENT_KEYS
        },
        "loaded_file_identities_sha256": _sha256_bytes(_canonical_bytes(loaded_rows)),
        "python_executable_sha256": _sha256_path(executable),
    }


def _execution_environment_identity(
    *,
    boot_id_path: Path | None = None,
) -> ExecutionEnvironmentIdentity:
    active_boot_id_path = (
        Path("/proc/sys/kernel/random/boot_id")
        if boot_id_path is None
        else boot_id_path
    )
    try:
        raw_boot_session = active_boot_id_path.read_text(encoding="ascii").strip()
        boot_session = str(uuid.UUID(raw_boot_session))
        if raw_boot_session.lower() != boot_session:
            boot_session = ""
    except (OSError, UnicodeError, ValueError):
        boot_session = ""
    boot_session_id_available = bool(boot_session)
    projection = {
        **_static_runtime_environment_projection(),
        "boot_session": boot_session if boot_session_id_available else None,
        "boot_session_id_available": boot_session_id_available,
        "cache_read_allowed": False,
        "logical_cpu_count": os.cpu_count(),
        "machine": platform.machine(),
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "system": platform.system(),
        "system_release": platform.release(),
        "torch_version": str(torch.__version__),
    }
    return ExecutionEnvironmentIdentity(
        sha256=_sha256_bytes(_canonical_bytes(projection)),
        boot_session_id_available=boot_session_id_available,
        timed_cache_reusable=False,
    )


def _execution_environment_sha256() -> str:
    return _execution_environment_identity().sha256


def _open_directory_descriptor(path: Path, *, create: bool) -> int:
    if not path.is_absolute() or any(part in {".", ".."} for part in path.parts):
        raise PublicRedockingRunnerError(
            "managed artifact directory must be an absolute canonical path"
        )
    directory_flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        directory_flags |= os.O_DIRECTORY
    if hasattr(os, "O_CLOEXEC"):
        directory_flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        directory_flags |= os.O_NOFOLLOW
    descriptor = -1
    try:
        descriptor = os.open("/", directory_flags)
        for component in path.parts[1:]:
            try:
                next_descriptor = os.open(
                    component,
                    directory_flags,
                    dir_fd=descriptor,
                )
            except FileNotFoundError:
                if not create:
                    raise
                try:
                    os.mkdir(component, 0o700, dir_fd=descriptor)
                except FileExistsError:
                    pass
                next_descriptor = os.open(
                    component,
                    directory_flags,
                    dir_fd=descriptor,
                )
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor
    except OSError as exc:
        if descriptor >= 0:
            os.close(descriptor)
        raise PublicRedockingRunnerError(
            "managed artifact directory contains an unavailable or symlink component"
        ) from exc


def _owned_directory_descriptor(
    path: Path,
    *,
    create: bool,
    exact_mode: int | None = None,
) -> int:
    descriptor = _open_directory_descriptor(path, create=create)
    try:
        status = os.fstat(descriptor)
        if not stat.S_ISDIR(status.st_mode) or (
            hasattr(os, "geteuid") and status.st_uid != os.geteuid()
        ):
            raise PublicRedockingRunnerError(
                "managed artifact directory is not an owned directory"
            )
        if exact_mode is not None:
            os.fchmod(descriptor, exact_mode)
            if stat.S_IMODE(os.fstat(descriptor).st_mode) != exact_mode:
                raise PublicRedockingRunnerError(
                    "managed artifact directory permissions are invalid"
                )
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _atomic_json(path: Path, payload: object) -> None:
    encoded = _canonical_bytes(payload) + b"\n"
    _atomic_bytes(path, encoded)


def _atomic_bytes(path: Path, payload: bytes) -> None:
    if not isinstance(payload, bytes):
        raise TypeError("atomic payload must be bytes")
    descriptor = -1
    directory_descriptor = -1
    temporary_name = f".{path.name}.{uuid.uuid4().hex}.tmp"
    try:
        directory_descriptor = _owned_directory_descriptor(
            path.parent,
            create=True,
        )
        write_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_CLOEXEC"):
            write_flags |= os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            write_flags |= os.O_NOFOLLOW
        descriptor = os.open(
            temporary_name,
            write_flags,
            0o600,
            dir_fd=directory_descriptor,
        )
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(
            temporary_name,
            path.name,
            src_dir_fd=directory_descriptor,
            dst_dir_fd=directory_descriptor,
        )
        os.fsync(directory_descriptor)
    except OSError as exc:
        raise PublicRedockingRunnerError("atomic artifact write failed") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if directory_descriptor >= 0:
            try:
                os.unlink(temporary_name, dir_fd=directory_descriptor)
            except OSError:
                pass
            finally:
                os.close(directory_descriptor)


def _quarantine_managed_regular_file(
    path: Path,
    *,
    label: str,
    required_mode: int | None = None,
) -> Path | None:
    directory_descriptor = _owned_directory_descriptor(
        path.parent,
        create=True,
    )
    stale_name = f"{path.name}.stale-{time.time_ns()}-{uuid.uuid4().hex}"
    try:
        try:
            source_status = os.stat(
                path.name,
                dir_fd=directory_descriptor,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            return None
        if (
            not stat.S_ISREG(source_status.st_mode)
            or (
                hasattr(os, "geteuid")
                and source_status.st_uid != os.geteuid()
            )
            or (
                required_mode is not None
                and stat.S_IMODE(source_status.st_mode) != required_mode
            )
        ):
            raise PublicRedockingRunnerError(
                f"{label} is not an owned regular file with expected permissions"
            )
        os.rename(
            path.name,
            stale_name,
            src_dir_fd=directory_descriptor,
            dst_dir_fd=directory_descriptor,
        )
        stale_status = os.stat(
            stale_name,
            dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
        if (
            stale_status.st_dev,
            stale_status.st_ino,
            stale_status.st_size,
            stat.S_IMODE(stale_status.st_mode),
            stale_status.st_uid,
        ) != (
            source_status.st_dev,
            source_status.st_ino,
            source_status.st_size,
            stat.S_IMODE(source_status.st_mode),
            source_status.st_uid,
        ):
            raise PublicRedockingRunnerError(
                f"{label} changed while it was quarantined"
            )
        os.fsync(directory_descriptor)
        return path.parent / stale_name
    except OSError as exc:
        raise PublicRedockingRunnerError(
            f"{label} could not be quarantined safely"
        ) from exc
    finally:
        os.close(directory_descriptor)


def _split_sdf_records(source: bytes) -> tuple[bytes, ...]:
    if not source or b"\r" in source:
        raise PublicRedockingRunnerError("SDF output is empty or uses CRLF")
    records: list[bytes] = []
    current = bytearray()
    for line in source.splitlines(keepends=True):
        current.extend(line)
        if line == b"$$$$\n":
            records.append(bytes(current))
            current.clear()
    if current or not records or b"".join(records) != source:
        raise PublicRedockingRunnerError("SDF output records are incomplete")
    return tuple(records)


def _materialize_case_inputs(
    archive: VerifiedPublicRedockingArchive,
    case_id: str,
    root: Path,
) -> tuple[dict[str, Path], VerifiedCaseMaterialization]:
    receipt, payloads = archive.verified_case(case_id)
    directory = root / case_id
    directory_descriptor = _owned_directory_descriptor(
        directory,
        create=True,
        exact_mode=0o700,
    )
    os.close(directory_descriptor)
    roles = ("receptor", "reference", "native", "seed")
    for role, suffix in zip(roles, _CASE_FILE_SUFFIXES, strict=True):
        payload = payloads[role]
        target = directory / f"{case_id}_{suffix}"
        _atomic_bytes(target, payload)
        target.chmod(0o400)
    directory_descriptor = _owned_directory_descriptor(
        directory,
        create=False,
        exact_mode=0o500,
    )
    os.close(directory_descriptor)
    paths = _case_paths(root, case_id)
    _require_case_input_identity(
        paths,
        receipt.input_artifact_sha256s_by_role,
    )
    return paths, receipt


def _case_paths(root: Path, case_id: str) -> dict[str, Path]:
    directory = root / case_id
    return {
        "directory": directory,
        "receptor": directory / f"{case_id}_protein.pdb",
        "reference": directory / f"{case_id}_ligands.sdf",
        "native": directory / f"{case_id}_ligand.sdf",
        "seed": directory / f"{case_id}_ligand_start_conf.sdf",
    }


def _require_case_input_identity(
    paths: dict[str, Path],
    expected_sha256s: dict[str, str],
) -> None:
    if set(expected_sha256s) != {"receptor", "reference", "native", "seed"}:
        raise PublicRedockingRunnerError("expected case input hashes are incomplete")
    try:
        directory = paths["directory"]
        directory_status = directory.lstat()
        if (
            directory.is_symlink()
            or not stat.S_ISDIR(directory_status.st_mode)
            or stat.S_IMODE(directory_status.st_mode) != 0o500
            or (hasattr(os, "geteuid") and directory_status.st_uid != os.geteuid())
        ):
            raise PublicRedockingRunnerError(
                "materialized case directory is not private and read-only"
            )
        for role in ("receptor", "reference", "native", "seed"):
            path = paths[role]
            file_status = path.lstat()
            if (
                path.is_symlink()
                or not stat.S_ISREG(file_status.st_mode)
                or stat.S_IMODE(file_status.st_mode) != 0o400
                or (hasattr(os, "geteuid") and file_status.st_uid != os.geteuid())
            ):
                raise PublicRedockingRunnerError(
                    f"materialized {role} input is not a read-only regular file"
                )
        observed = _input_sha256s(paths)
    except OSError as exc:
        raise PublicRedockingRunnerError(
            "materialized case input cannot be reverified"
        ) from exc
    if observed != expected_sha256s:
        raise PublicRedockingRunnerError(
            "materialized case bytes do not match the verified archive receipt"
        )


def _remove_materialized_case_inputs(
    paths: dict[str, Path],
    expected_sha256s: dict[str, str],
) -> None:
    _require_case_input_identity(paths, expected_sha256s)
    directory = paths["directory"]
    directory_descriptor = -1
    parent_descriptor = -1
    try:
        directory_descriptor = _owned_directory_descriptor(
            directory,
            create=False,
            exact_mode=0o700,
        )
        directory_status = os.fstat(directory_descriptor)
        expected_names = {
            paths[role].name for role in ("receptor", "reference", "native", "seed")
        }
        if set(os.listdir(directory_descriptor)) != expected_names:
            raise PublicRedockingRunnerError(
                "materialized case directory contains unexpected entries"
            )
        for role in ("receptor", "reference", "native", "seed"):
            os.unlink(paths[role].name, dir_fd=directory_descriptor)
        os.fsync(directory_descriptor)
        os.close(directory_descriptor)
        directory_descriptor = -1
        parent_descriptor = _owned_directory_descriptor(
            directory.parent,
            create=False,
        )
        current_status = os.stat(
            directory.name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        if (current_status.st_dev, current_status.st_ino) != (
            directory_status.st_dev,
            directory_status.st_ino,
        ):
            raise PublicRedockingRunnerError(
                "materialized case directory changed before cleanup"
            )
        os.rmdir(directory.name, dir_fd=parent_descriptor)
        os.fsync(parent_descriptor)
    except OSError as exc:
        raise PublicRedockingRunnerError(
            "materialized case directory cannot be removed safely"
        ) from exc
    finally:
        if directory_descriptor >= 0:
            os.close(directory_descriptor)
        if parent_descriptor >= 0:
            os.close(parent_descriptor)


def _serialize_pose_records(
    source_ligand: Path,
    coordinates: Sequence[torch.Tensor],
    *,
    case_id: str,
) -> tuple[bytes, ...]:
    Chem, _, _ = _load_rdkit_modules()
    template = _first_molecule(source_ligand)
    atom_count = int(template.GetNumAtoms())
    records: list[bytes] = []
    for rank, values in enumerate(coordinates, start=1):
        tensor = values.detach().to(dtype=torch.float64, device="cpu")
        if tuple(tensor.shape) != (atom_count, 3) or not torch.isfinite(tensor).all():
            raise InvalidRankedPoseSet(
                "Engine V2 pose coordinates do not match the source ligand"
            )
        molecule = Chem.Mol(template)
        molecule.RemoveAllConformers()
        conformer = Chem.Conformer(atom_count)
        for atom_index, point in enumerate(tensor.tolist()):
            conformer.SetAtomPosition(
                atom_index, tuple(float(value) for value in point)
            )
        molecule.AddConformer(conformer, assignId=True)
        molecule.SetProp("_Name", f"{case_id}_engine_v2_rank_{rank}")
        block = Chem.MolToMolBlock(
            molecule,
            confId=0,
            includeStereo=True,
            kekulize=True,
        )
        records.append((block.rstrip("\n") + "\n$$$$\n").encode("ascii"))
    return tuple(records)


def _write_engine_v2_poses(
    output: Path,
    source_ligand: Path,
    coordinates: Sequence[torch.Tensor],
    *,
    case_id: str,
) -> tuple[bytes, tuple[str, ...]]:
    records = _serialize_pose_records(
        source_ligand,
        coordinates,
        case_id=case_id,
    )
    if len(records) != 5:
        raise IncompleteRankedPoseSet(
            "Engine V2 must serialize exactly five ranked poses"
        )
    payload = b"".join(records)
    _atomic_bytes(output, payload)
    read_flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(output, read_flags)
    except OSError as exc:
        raise PublicRedockingRunnerError(
            "Engine V2 SDF could not be pinned after serialization"
        ) from exc
    try:
        output_status = os.fstat(descriptor)
        if not stat.S_ISREG(output_status.st_mode):
            raise PublicRedockingRunnerError(
                "Engine V2 SDF output is not a regular file"
            )
        persisted_payload = _bytes_from_descriptor(descriptor)
    finally:
        os.close(descriptor)
    if persisted_payload != payload or _split_sdf_records(persisted_payload) != records:
        raise PublicRedockingRunnerError("Engine V2 SDF round trip changed")
    return (
        persisted_payload,
        tuple(_sha256_bytes(record) for record in records),
    )


def _load_rdkit_modules():
    try:
        from rdkit import Chem, rdBase
        from rdkit.Chem import Lipinski, rdMolDescriptors
    except ImportError as exc:
        raise PublicRedockingRunnerError(
            "RDKit is required for the public run"
        ) from exc
    if rdBase.rdkitVersion != RDKit_VERSION:
        raise PublicRedockingRunnerError(
            f"RDKit {RDKit_VERSION} is required for the frozen profiles"
        )
    return Chem, Lipinski, rdMolDescriptors


def _load_posebusters():
    try:
        from posebusters import PoseBusters
    except ImportError as exc:
        raise PublicRedockingRunnerError(
            "PoseBusters is required for the public run"
        ) from exc
    if metadata.version("posebusters") != POSEBUSTERS_VERSION:
        raise PublicRedockingRunnerError(
            f"PoseBusters {POSEBUSTERS_VERSION} is required for evaluation"
        )
    return PoseBusters


def _first_molecule(path: Path):
    Chem, _, _ = _load_rdkit_modules()
    supplier = Chem.SDMolSupplier(str(path), removeHs=False, sanitize=True)
    molecule = next((value for value in supplier if value is not None), None)
    if molecule is None:
        raise PublicRedockingRunnerError("ligand SDF contains no valid molecule")
    return molecule


def _with_benchmark_partial_charges(
    system: AllAtomSystem,
    *,
    charges: Sequence[float],
    formal_charges: Sequence[int],
    method_id: str,
) -> AllAtomSystem:
    if (
        len(charges) != system.atom_count
        or len(formal_charges) != system.atom_count
        or any(not math.isfinite(float(value)) for value in charges)
    ):
        raise EngineV2CaseFailure("partial charge assignment is incomplete")
    if not math.isclose(
        sum(float(value) for value in charges),
        float(sum(int(value) for value in formal_charges)),
        abs_tol=1.0e-8,
    ):
        raise EngineV2CaseFailure("partial charge assignment does not conserve charge")
    charge_sha256 = _sha256_bytes(
        _canonical_bytes(
            {
                "method_id": method_id,
                "partial_charge_binary64_hex": [
                    float(value).hex() for value in charges
                ],
                "formal_charges": [int(value) for value in formal_charges],
            }
        )
    )
    atoms = tuple(
        replace(
            atom,
            formal_charge=int(formal_charge),
            partial_charge_e=float(charge),
            metadata={
                **dict(atom.metadata),
                "partial_charge_method_id": method_id,
                "partial_charge_assignment_sha256": charge_sha256,
                "partial_charge_scientifically_validated": False,
            },
        )
        for atom, charge, formal_charge in zip(
            system.atoms,
            charges,
            formal_charges,
            strict=True,
        )
    )
    provenance_metadata = {
        **dict(system.provenance.metadata),
        "partial_charge_method_id": method_id,
        "partial_charge_assignment_sha256": charge_sha256,
        "partial_charge_scientifically_validated": False,
    }
    return replace(
        system,
        atoms=atoms,
        provenance=replace(
            system.provenance,
            operations=(*system.provenance.operations, method_id),
            transformation_chain_verified=False,
            chemistry_validated=False,
            scientifically_validated=False,
            product_qualified=False,
            metadata=provenance_metadata,
        ),
        metadata={
            **dict(system.metadata),
            "partial_charge_method_id": method_id,
            "partial_charge_assignment_sha256": charge_sha256,
        },
    )


def _assign_receptor_proxy_charges(system: AllAtomSystem) -> AllAtomSystem:
    charges = [float(atom.formal_charge) for atom in system.atoms]
    formal_charges = [int(atom.formal_charge) for atom in system.atoms]
    residue_rules = {
        "ASP": (("OD1", "OD2"), -1),
        "GLU": (("OE1", "OE2"), -1),
        "LYS": (("NZ",), 1),
        "ARG": (("NH1", "NH2"), 1),
        "HIP": (("ND1", "NE2"), 1),
        "HSP": (("ND1", "NE2"), 1),
    }
    for residue in system.residues:
        rule = residue_rules.get(residue.name)
        if rule is None:
            continue
        atom_names, total_charge = rule
        indices = [
            index
            for index in residue.atom_indices
            if system.atoms[index].name.upper() in atom_names
        ]
        if not indices:
            continue
        for index in indices:
            charges[index] = float(total_charge) / len(indices)
            formal_charges[index] = 0
        formal_charges[indices[0]] = total_charge
    return _with_benchmark_partial_charges(
        system,
        charges=charges,
        formal_charges=formal_charges,
        method_id=RECEPTOR_CHARGE_METHOD_ID,
    )


def _assign_ligand_gasteiger_charges(
    system: AllAtomSystem,
    source_ligand: Path,
) -> AllAtomSystem:
    from rdkit.Chem import AllChem

    molecule = _first_molecule(source_ligand)
    if molecule.GetNumAtoms() != system.atom_count or any(
        molecule.GetAtomWithIdx(index).GetAtomicNum() != atom.atomic_number
        for index, atom in enumerate(system.atoms)
    ):
        raise EngineV2CaseFailure(
            "ligand charge assignment atom order does not match parsed input"
        )
    try:
        AllChem.ComputeGasteigerCharges(
            molecule,
            nIter=12,
            throwOnParamFailure=True,
        )
        charges = [
            float(atom.GetProp("_GasteigerCharge"))
            + float(atom.GetProp("_GasteigerHCharge"))
            for atom in molecule.GetAtoms()
        ]
    except (RuntimeError, ValueError) as exc:
        raise EngineV2CaseFailure("ligand partial charge assignment failed") from exc
    if any(not math.isfinite(value) for value in charges):
        raise EngineV2CaseFailure("ligand partial charge assignment is non-finite")
    formal_charges = [int(atom.formal_charge) for atom in system.atoms]
    residual = float(sum(formal_charges)) - sum(charges)
    correction_index = max(range(len(charges)), key=lambda index: abs(charges[index]))
    charges[correction_index] += residual
    return _with_benchmark_partial_charges(
        system,
        charges=charges,
        formal_charges=formal_charges,
        method_id=LIGAND_CHARGE_METHOD_ID,
    )


def _profile(
    case_id: str,
    paths: dict[str, Path],
    expected: PublicRedockingCaseProfile,
) -> PublicRedockingCaseProfile:
    _, Lipinski, rdMolDescriptors = _load_rdkit_modules()
    molecule = _first_molecule(paths["native"])
    observed = PublicRedockingCaseProfile(
        case_id=case_id,
        heavy_atom_count=sum(atom.GetAtomicNum() > 1 for atom in molecule.GetAtoms()),
        rotor_count=int(Lipinski.NumRotatableBonds(molecule)),
        ring_count=int(rdMolDescriptors.CalcNumRings(molecule)),
        ligand_artifact_sha256=_sha256_path(paths["native"]),
    )
    if observed != expected:
        raise PublicRedockingRunnerError(
            f"frozen ligand profile does not match source bytes: {case_id}"
        )
    return expected


def _posebusters_molecules(
    *,
    output_payload: bytes,
    native_payload: bytes,
    receptor_payload: bytes,
    expected_pose_count: int = 5,
) -> tuple[tuple[object, ...], object, object]:
    """Decode pinned bytes with the exact PoseBusters 0.3.1 redock policy."""
    Chem, _, _ = _load_rdkit_modules()
    try:
        predicted = tuple(
            Chem.ForwardSDMolSupplier(
                BytesIO(output_payload),
                sanitize=False,
                removeHs=True,
                strictParsing=True,
            )
        )
        native_supplier = Chem.ForwardSDMolSupplier(
            BytesIO(native_payload),
            sanitize=False,
            removeHs=False,
            strictParsing=False,
        )
        native = None
        for candidate in native_supplier:
            if candidate is None:
                continue
            if native is None:
                native = candidate
            else:
                native.AddConformer(candidate.GetConformer(), assignId=True)
        receptor = Chem.MolFromPDBBlock(
            receptor_payload.decode("ascii"),
            sanitize=False,
            removeHs=False,
            proximityBonding=False,
        )
        if receptor is not None:
            Chem.AssignStereochemistryFrom3D(receptor)
    except (OSError, RuntimeError, UnicodeError, ValueError) as exc:
        raise PublicRedockingRunnerError(
            "PoseBusters inputs could not be decoded from pinned bytes"
        ) from exc
    if (
        len(predicted) != expected_pose_count
        or any(molecule is None for molecule in predicted)
    ):
        raise PublicRedockingRunnerError(
            "PoseBusters could not decode the expected predicted molecules"
        )
    if native is None or receptor is None:
        raise PublicRedockingRunnerError(
            "PoseBusters could not decode native ligand and receptor"
        )
    return predicted, native, receptor


def _posebusters_outcomes(
    output_payload: bytes,
    *,
    native_payload: bytes,
    receptor_payload: bytes,
    expected_pose_count: int = 5,
) -> tuple[tuple[float, ...], tuple[bool, ...], tuple[bool, ...]]:
    PoseBusters = _load_posebusters()
    predicted, native, receptor = _posebusters_molecules(
        output_payload=output_payload,
        native_payload=native_payload,
        receptor_payload=receptor_payload,
        expected_pose_count=expected_pose_count,
    )
    report = PoseBusters(config="redock", top_n=expected_pose_count).bust(
        predicted,
        native,
        receptor,
        full_report=True,
    )
    if len(report) != expected_pose_count:
        raise PublicRedockingRunnerError(
            "PoseBusters did not retain the expected pose count"
        )
    required = {"rmsd", *CHEMICAL_COLUMNS, *GEOMETRIC_COLUMNS}
    if not required.issubset(report.columns):
        raise PublicRedockingRunnerError("PoseBusters report columns are incomplete")
    rmsds = tuple(float(value) for value in report["rmsd"].tolist())
    if any(not math.isfinite(value) or value < 0.0 for value in rmsds):
        raise PublicRedockingRunnerError("PoseBusters RMSD is invalid")
    boolean_values = {
        column: report[column].tolist()
        for column in (*CHEMICAL_COLUMNS, *GEOMETRIC_COLUMNS)
    }

    def required_boolean(index: int, column: str) -> bool:
        value = boolean_values[column][index]
        if type(value) is not bool:
            raise PublicRedockingRunnerError(
                f"PoseBusters check is not an evaluated boolean: {column}"
            )
        return value

    chemical = tuple(
        all(tuple(required_boolean(index, column) for column in CHEMICAL_COLUMNS))
        for index in range(expected_pose_count)
    )
    geometric = tuple(
        all(tuple(required_boolean(index, column) for column in GEOMETRIC_COLUMNS))
        for index in range(expected_pose_count)
    )
    return rmsds, geometric, chemical


def _verified_case_execution(
    row: PublicRedockingCaseResult,
    *,
    command: Sequence[str],
    execution_policy: dict[str, object],
    input_sha256s: dict[str, str],
    materialization_receipt_sha256: str,
    implementation_sha256: str,
    evaluation_pipeline_sha256: str,
    execution_environment_sha256: str,
) -> VerifiedPublicRedockingCaseExecution:
    expected_inputs = _result_input_fields(input_sha256s)
    if any(
        getattr(row, field_name) != digest
        for field_name, digest in expected_inputs.items()
    ):
        raise PublicRedockingRunnerError("result row input hashes are cross-wired")
    if row.execution_command != tuple(command):
        raise PublicRedockingRunnerError("result row command is cross-wired")
    if row.execution_policy != _execution_policy_tokens(execution_policy):
        raise PublicRedockingRunnerError("result row execution policy is cross-wired")
    if len(materialization_receipt_sha256) != 64 or any(
        value not in "0123456789abcdef" for value in materialization_receipt_sha256
    ):
        raise PublicRedockingRunnerError("materialization receipt SHA-256 is invalid")
    return VerifiedPublicRedockingCaseExecution._from_fresh_execution(
        result=row,
        materialization_receipt_sha256=materialization_receipt_sha256,
        implementation_sha256=implementation_sha256,
        evaluation_pipeline_sha256=evaluation_pipeline_sha256,
        execution_environment_sha256=execution_environment_sha256,
        verification_authority=benchmark_contract._VERIFIED_EXECUTION_AUTHORITY,
    )


def _row_payload(
    row: PublicRedockingCaseResult,
    *,
    command: Sequence[str],
    execution_policy: dict[str, object],
    input_sha256s: dict[str, str],
    materialization_receipt_sha256: str,
    implementation_sha256: str,
    evaluation_pipeline_sha256: str,
    execution_environment_sha256: str,
) -> dict[str, object]:
    return _verified_case_execution(
        row,
        command=command,
        execution_policy=execution_policy,
        input_sha256s=input_sha256s,
        materialization_receipt_sha256=materialization_receipt_sha256,
        implementation_sha256=implementation_sha256,
        evaluation_pipeline_sha256=evaluation_pipeline_sha256,
        execution_environment_sha256=execution_environment_sha256,
    ).to_dict()


def _load_cached_row(
    path: Path,
    *,
    case_id: str,
    engine_id: str,
    command: Sequence[str],
    execution_policy: dict[str, object],
    pose_output: Path,
    input_sha256s: dict[str, str],
    materialization_receipt_sha256: str,
    implementation_sha256: str,
    evaluation_pipeline_sha256: str,
    execution_environment_sha256: str,
    timed_cache_reusable: bool,
) -> PublicRedockingCaseResult | None:
    # A checksum stored beside mutable row data is not a trust anchor. Until an
    # operator supplies an independently protected signature/manifest, every
    # benchmark invocation executes fresh rows and cached JSON is diagnostic
    # evidence only.
    del (
        path,
        case_id,
        engine_id,
        command,
        execution_policy,
        pose_output,
        input_sha256s,
        materialization_receipt_sha256,
        implementation_sha256,
        evaluation_pipeline_sha256,
        execution_environment_sha256,
        timed_cache_reusable,
    )
    return None


def _engine_source_sha256(
    repo_root: Path,
    *,
    runner_path: Path | None = None,
) -> str:
    package_root = repo_root / "betelgeuze_engine_v2"
    active_runner = Path(__file__).resolve() if runner_path is None else runner_path
    paths = tuple(sorted(package_root.rglob("*.py"))) + (active_runner,)
    if not paths or any(not path.is_file() for path in paths):
        raise PublicRedockingRunnerError(
            "Engine V2 implementation source closure is incomplete"
        )
    projection = [
        (path.relative_to(repo_root).as_posix(), _sha256_path(path)) for path in paths
    ]
    return hashlib.sha256(_canonical_bytes(projection)).hexdigest()


def _evaluation_pipeline_sha256(
    repo_root: Path,
    *,
    evaluator_versions: dict[str, str] | None = None,
) -> str:
    paths = (
        repo_root / "betelgeuze_engine_v2/benchmark/public_redocking_benchmark.py",
        Path(__file__).resolve(),
    )
    projection = {
        "runner_id": RUNNER_ID,
        "evaluator_distribution_versions": (
            _evaluator_environment_versions()
            if evaluator_versions is None
            else dict(sorted(evaluator_versions.items()))
        ),
        "evaluator_distribution_payload_sha256s": (
            _evaluator_distribution_payload_sha256s()
        ),
        "chemical_columns": list(CHEMICAL_COLUMNS),
        "geometric_columns": list(GEOMETRIC_COLUMNS),
        "source_sha256s": [
            (path.relative_to(repo_root).as_posix(), _sha256_path(path))
            for path in paths
        ],
    }
    return hashlib.sha256(_canonical_bytes(projection)).hexdigest()


def _verify_external_binary(binary: PinnedExternalBinary) -> str:
    if binary._closed:
        raise PublicRedockingRunnerError("staged GNINA descriptor is closed")
    try:
        file_status = binary.path.lstat()
        descriptor_status = os.fstat(binary.descriptor)
    except OSError as exc:
        raise PublicRedockingRunnerError("staged GNINA binary is unavailable") from exc
    if (
        binary.path.is_symlink()
        or not binary.path.is_file()
        or not stat.S_ISREG(file_status.st_mode)
        or not stat.S_ISREG(descriptor_status.st_mode)
        or (file_status.st_dev, file_status.st_ino)
        != (descriptor_status.st_dev, descriptor_status.st_ino)
        or bool(file_status.st_mode & 0o222)
        or bool(descriptor_status.st_mode & 0o222)
    ):
        raise PublicRedockingRunnerError(
            "staged GNINA binary is not a regular immutable-stage file"
        )
    observed = _sha256_descriptor(binary.descriptor)
    if observed != binary.sha256:
        raise PublicRedockingRunnerError(
            "staged GNINA binary changed during the benchmark"
        )
    return observed


def _stage_external_binary(
    source: Path,
    *,
    output_root: Path,
) -> PinnedExternalBinary:
    try:
        source_status = source.stat()
    except OSError as exc:
        raise PublicRedockingRunnerError("GNINA binary is missing") from exc
    if not stat.S_ISREG(source_status.st_mode):
        raise PublicRedockingRunnerError("GNINA binary must be a regular file")
    initial_sha256 = _sha256_path(source)
    stage_root = output_root / "private-external-binary"
    stage_descriptor = _owned_directory_descriptor(
        stage_root,
        create=True,
        exact_mode=0o700,
    )
    staged_path = stage_root / initial_sha256
    temporary_name = f".{initial_sha256}.{uuid.uuid4().hex}.tmp"
    try:
        try:
            staged_status = os.stat(
                initial_sha256,
                dir_fd=stage_descriptor,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            staged_status = None
        if staged_status is not None:
            if not stat.S_ISREG(staged_status.st_mode):
                raise PublicRedockingRunnerError(
                    "GNINA staged SHA-256 path is not a regular file"
                )
        else:
            try:
                descriptor = os.open(
                    temporary_name,
                    os.O_WRONLY
                    | os.O_CREAT
                    | os.O_EXCL
                    | getattr(os, "O_CLOEXEC", 0)
                    | getattr(os, "O_NOFOLLOW", 0),
                    0o500,
                    dir_fd=stage_descriptor,
                )
                with (
                    source.open("rb") as source_handle,
                    os.fdopen(
                        descriptor,
                        "wb",
                    ) as target_handle,
                ):
                    shutil.copyfileobj(source_handle, target_handle)
                    target_handle.flush()
                    os.fsync(target_handle.fileno())
                    os.fchmod(target_handle.fileno(), 0o500)
                temporary_descriptor = os.open(
                    temporary_name,
                    os.O_RDONLY
                    | getattr(os, "O_CLOEXEC", 0)
                    | getattr(os, "O_NOFOLLOW", 0),
                    dir_fd=stage_descriptor,
                )
                try:
                    if _sha256_descriptor(temporary_descriptor) != initial_sha256:
                        raise PublicRedockingRunnerError(
                            "copied GNINA binary hash does not match its staged name"
                        )
                finally:
                    os.close(temporary_descriptor)
                try:
                    os.link(
                        temporary_name,
                        initial_sha256,
                        src_dir_fd=stage_descriptor,
                        dst_dir_fd=stage_descriptor,
                        follow_symlinks=False,
                    )
                except FileExistsError:
                    pass
                os.fsync(stage_descriptor)
            except OSError as exc:
                raise PublicRedockingRunnerError(
                    "GNINA binary could not be copied to its private immutable stage"
                ) from exc
        pinned = PinnedExternalBinary(staged_path, initial_sha256)
        _verify_external_binary(pinned)
    finally:
        try:
            os.unlink(temporary_name, dir_fd=stage_descriptor)
        except OSError:
            pass
        os.close(stage_descriptor)
    if _sha256_path(source) != initial_sha256:
        raise PublicRedockingRunnerError(
            "GNINA source binary changed while it was staged"
        )
    return pinned


def _binary_version(binary: PinnedExternalBinary) -> str:
    _verify_external_binary(binary)
    try:
        completed = subprocess.run(
            (binary.execution_path, "--version"),
            check=False,
            capture_output=True,
            pass_fds=(binary.descriptor,),
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise PublicRedockingRunnerError("GNINA version probe failed") from exc
    output = (
        (completed.stdout + completed.stderr)
        .decode(
            "utf-8",
            errors="replace",
        )
        .strip()
    )
    if completed.returncode != 0 or not output or len(output) > 1_024:
        raise PublicRedockingRunnerError("GNINA version probe returned invalid output")
    _verify_external_binary(binary)
    return " ".join(output.split())


def _external_command(
    case_id: str,
    engine_id: str,
    paths: dict[str, Path],
    *,
    binary: Path,
    output: Path,
    seed: int,
) -> tuple[str, ...]:
    if engine_id not in {"vina", "gnina"}:
        raise PublicRedockingRunnerError("unsupported external engine")
    command = [
        str(binary),
        "--receptor",
        str(paths["receptor"]),
        "--ligand",
        str(paths["seed"]),
        "--autobox_ligand",
        str(paths["native"]),
        "--autobox_add",
        "4",
        "--num_modes",
        "5",
        "--exhaustiveness",
        "1",
        "--cpu",
        "1",
        "--no_gpu",
        "--seed",
        str(seed),
        "--out",
        str(output),
    ]
    if engine_id == "vina":
        command.extend(("--scoring", "vina", "--cnn_scoring", "none"))
    else:
        command.extend(
            (
                "--scoring",
                "vina",
                "--cnn_scoring",
                "rescore",
                "--cnn",
                "crossdock_default2018",
            )
        )
    return tuple(command)


def _engine_v2_command(
    case_id: str,
    paths: dict[str, Path],
    *,
    output: Path,
    seed: int,
) -> tuple[str, ...]:
    return (
        RUNNER_ID,
        "engine_v2",
        "--case-id",
        case_id,
        "--receptor",
        str(paths["receptor"]),
        "--ligand",
        str(paths["seed"]),
        "--pocket-source",
        str(paths["native"]),
        "--candidate-count",
        str(ENGINE_V2_CANDIDATE_COUNT),
        "--cpu",
        "1",
        "--seed",
        str(seed),
        "--out",
        str(output),
    )


def _benchmark_ranked_proposals(search) -> tuple[object, ...]:
    rows = [
        row
        for row in search.rows
        if row.status == "success"
        and row.proposal is not None
        and row.score is not None
        and math.isfinite(float(row.score))
    ]
    rows.sort(key=lambda row: (float(row.score), row.proposal_index))
    if len(rows) < 5:
        raise IncompleteRankedPoseSet(
            "Engine V2 did not produce five score-ranked proposals"
        )
    return tuple(row.proposal for row in rows[:5])


def _engine_v2_pose_coordinates(
    case_id: str,
    paths: dict[str, Path],
    *,
    seed: int,
) -> EngineV2PoseSearchOutcome:
    try:
        receptor_bytes = paths["receptor"].read_bytes()
        seed_bytes = paths["seed"].read_bytes()
        native_bytes = paths["native"].read_bytes()
        receptor = parse_pdb(
            receptor_bytes,
            source_id=f"{case_id}:receptor",
            dtype=torch.float64,
            device="cpu",
            connectivity_policy="record_unrepresented",
            unit_cell_policy="ignore",
        )
        ligand = parse_sdf_v2000(
            seed_bytes.decode("ascii"),
            source_id=f"{case_id}:seed",
            dtype=torch.float64,
            device="cpu",
        )
        native = parse_sdf_v2000(
            native_bytes.decode("ascii"),
            source_id=f"{case_id}:native",
            dtype=torch.float64,
            device="cpu",
        )
    except (PDBParseError, SDFParseError, UnicodeDecodeError) as exc:
        raise EngineV2PreparationFailure(
            "input_parse_unsupported",
            "Engine V2 input parsing is unsupported",
            failure_code="engine_v2_input_unsupported",
        ) from exc
    try:
        receptor = _assign_receptor_proxy_charges(receptor)
        ligand = _assign_ligand_gasteiger_charges(ligand, paths["seed"])
    except EngineV2CaseFailure as exc:
        raise EngineV2PreparationFailure(
            "partial_charge_assignment_failed",
            "Engine V2 partial-charge preparation failed",
        ) from exc
    native_coordinates = native.coordinates[0]
    center = native_coordinates.mean(dim=0)
    radius = max(
        6.0,
        float(
            torch.linalg.vector_norm(
                native_coordinates - center,
                dim=-1,
            )
            .max()
            .item()
        )
        + 4.0,
    )
    pocket = PocketDefinition(
        scope=DockingScope.KNOWN_POCKET,
        method_id="posebusters-crystal-redocking-sphere",
        method_version="1.0.0",
        coordinate_frame_id="posebusters-receptor-frame-v1",
        center=center,
        radius_angstrom=radius,
        source_artifact_sha256=_sha256_bytes(native_bytes),
        implementation_source_sha256=_sha256_bytes(
            b"posebusters-crystal-redocking-sphere/1.0.0"
        ),
    )
    try:
        authority = build_element_aware_authenticated_known_pocket_docking_problem(
            receptor,
            ligand,
            pocket,
            receptor_margin_angstrom=4.0,
        )
        scorer = ChemistryPoseScorerV1(
            authority,
            receptor,
            ligand,
            implementation_source_sha256=_sha256_bytes(
                b"engine-v2-public-redocking-scorer-v1"
            ),
        )
        context = build_guided_placement_context(authority, receptor, ligand)
    except (
        DockingAuthorityError,
        ElementAwareValidityError,
        ScorerV1Error,
    ) as exc:
        raise EngineV2PreparationFailure(
            "docking_context_preparation_failed",
            "Engine V2 docking-context preparation failed",
        ) from exc
    budget = DockingBudget(
        candidate_count=ENGINE_V2_CANDIDATE_COUNT,
        top_k=5,
        max_torsions=32,
        max_refinement_steps=0,
        translation_radius_angstrom=min(4.0, radius),
        seed=seed,
    )
    preparation_counts = {
        "receptor_atom_count": receptor.atom_count,
        "ligand_atom_count": ligand.atom_count,
        "receptor_partial_charge_count": sum(
            atom.partial_charge_e is not None for atom in receptor.atoms
        ),
        "ligand_partial_charge_count": sum(
            atom.partial_charge_e is not None for atom in ligand.atoms
        ),
        "receptor_donor_count": len(scorer.context.receptor_donors),
        "receptor_acceptor_count": len(scorer.context.receptor_acceptors),
        "ligand_donor_count": len(scorer.context.ligand_donors),
        "ligand_acceptor_count": len(scorer.context.ligand_acceptors),
    }

    def search_failure_diagnostics(
        error_code: str,
    ) -> PublicRedockingEngineV2Diagnostics:
        return PublicRedockingEngineV2Diagnostics(
            preparation_status="success",
            **preparation_counts,
            candidates=tuple(
                PublicRedockingEngineV2CandidateDiagnostic(
                    proposal_index=index,
                    status="failure",
                    error_code=error_code,
                )
                for index in range(ENGINE_V2_CANDIDATE_COUNT)
            ),
        )

    try:
        result = run_authenticated_scorer_v1_guided_search(
            authority,
            budget,
            scorer,
            context,
            receptor_system=receptor,
            ligand_system=ligand,
            diversity_rmsd_angstrom=0.0,
        )
    except (
        DockingAuthorityError,
        DockingSearchError,
        ElementAwareValidityError,
        ScorerV1Error,
    ) as exc:
        raise EngineV2SearchCaseFailure(
            "Engine V2 candidate search failed",
            diagnostics=search_failure_diagnostics("search_execution_failed"),
        ) from exc
    search = result.guided_search_result.authenticated_search_result.search_result
    if (
        len(search.rows) != ENGINE_V2_CANDIDATE_COUNT
        or len(result.rows) != ENGINE_V2_CANDIDATE_COUNT
        or tuple(row.proposal_index for row in search.rows)
        != tuple(range(ENGINE_V2_CANDIDATE_COUNT))
    ):
        raise EngineV2SearchCaseFailure(
            "Engine V2 search did not retain the fixed candidate denominator",
            diagnostics=search_failure_diagnostics(
                "candidate_denominator_incomplete"
            ),
        )
    term_rows = {row.proposal_index: row for row in result.rows}
    successful_rows = tuple(
        sorted(
            (
                row
                for row in search.rows
                if row.status == "success"
                and row.proposal is not None
                and row.score is not None
                and math.isfinite(float(row.score))
            ),
            key=lambda row: (float(row.score), row.proposal_index),
        )
    )
    evaluated_by_index: dict[
        int, tuple[float, bool, bool, str]
    ] = {}
    diagnostic_evaluation_seconds = 0.0
    if successful_rows:
        diagnostic_evaluation_started = time.perf_counter()
        records = _serialize_pose_records(
            paths["seed"],
            tuple(row.proposal.coordinates for row in successful_rows),
            case_id=case_id,
        )
        rmsds, geometric, chemical = _posebusters_outcomes(
            b"".join(records),
            native_payload=native_bytes,
            receptor_payload=receptor_bytes,
            expected_pose_count=len(successful_rows),
        )
        diagnostic_evaluation_seconds = (
            time.perf_counter() - diagnostic_evaluation_started
        )
        evaluated_by_index = {
            row.proposal_index: (
                rmsd,
                geometric_valid,
                chemical_valid,
                _sha256_bytes(record),
            )
            for row, rmsd, geometric_valid, chemical_valid, record in zip(
                successful_rows,
                rmsds,
                geometric,
                chemical,
                records,
                strict=True,
            )
        }
    candidate_rows: list[PublicRedockingEngineV2CandidateDiagnostic] = []
    for row in search.rows:
        if row.proposal_index in evaluated_by_index:
            terms = term_rows[row.proposal_index].terms
            if terms is None or row.proposal is None or row.score is None:
                raise PublicRedockingRunnerError(
                    "successful Engine V2 candidate lacks retained score terms"
                )
            rmsd, geometric_valid, chemical_valid, artifact_sha256 = (
                evaluated_by_index[row.proposal_index]
            )
            candidate_rows.append(
                PublicRedockingEngineV2CandidateDiagnostic(
                    proposal_index=row.proposal_index,
                    status="success",
                    proposal_fingerprint_sha256=(
                        row.proposal.fingerprint_sha256
                    ),
                    score=float(row.score),
                    rmsd_angstrom=rmsd,
                    geometric_valid=geometric_valid,
                    chemical_valid=chemical_valid,
                    pose_artifact_sha256=artifact_sha256,
                    score_terms_receipt_sha256=terms.receipt_sha256,
                    hbond_count=terms.hbond_count,
                )
            )
        else:
            candidate_rows.append(
                PublicRedockingEngineV2CandidateDiagnostic(
                    proposal_index=row.proposal_index,
                    status="failure",
                    error_code=str(row.error_code or "candidate_failed"),
                )
            )
    diagnostics = PublicRedockingEngineV2Diagnostics(
        preparation_status="success",
        **preparation_counts,
        candidates=tuple(candidate_rows),
        diagnostic_evaluation_seconds=diagnostic_evaluation_seconds,
    )
    try:
        proposals = _benchmark_ranked_proposals(search)
    except IncompleteRankedPoseSet as exc:
        raise EngineV2SearchCaseFailure(
            str(exc),
            diagnostics=diagnostics,
            failure_code=exc.failure_code,
            diagnostic_evaluation_seconds=diagnostic_evaluation_seconds,
        ) from exc
    return EngineV2PoseSearchOutcome(
        ranked_coordinates=tuple(proposal.coordinates for proposal in proposals),
        diagnostics=diagnostics,
        diagnostic_evaluation_seconds=diagnostic_evaluation_seconds,
    )


def _engine_v2_failure_code(exc: Exception) -> str:
    if isinstance(exc, EngineV2CaseFailure):
        return exc.failure_code
    if isinstance(exc, (PDBParseError, SDFParseError, UnicodeDecodeError)):
        return "engine_v2_input_unsupported"
    return "engine_v2_case_failed"


def _engine_v2_result(
    case_id: str,
    paths: dict[str, Path],
    *,
    logical_paths: dict[str, Path] | None = None,
    input_sha256s: dict[str, str],
    output: Path,
    seed: int,
) -> PublicRedockingCaseResult:
    _quarantine_managed_regular_file(
        output,
        label="stale Engine V2 pose output",
        required_mode=0o600,
    )
    started = time.perf_counter()
    command = _engine_v2_command(
        case_id,
        paths if logical_paths is None else logical_paths,
        output=output,
        seed=seed,
    )
    execution_policy = _execution_policy_tokens(ENGINE_V2_CPU_POLICY)
    diagnostics: PublicRedockingEngineV2Diagnostics | None = None
    diagnostic_evaluation_seconds = 0.0
    try:
        outcome = _engine_v2_pose_coordinates(case_id, paths, seed=seed)
        if type(outcome) is not EngineV2PoseSearchOutcome:
            raise PublicRedockingRunnerError(
                "Engine V2 search did not return typed diagnostics"
            )
        diagnostics = outcome.diagnostics
        diagnostic_evaluation_seconds = outcome.diagnostic_evaluation_seconds
        pose_payload, artifacts = _write_engine_v2_poses(
            output,
            paths["seed"],
            outcome.ranked_coordinates,
            case_id=case_id,
        )
    except _ENGINE_V2_CASE_EXCEPTIONS as exc:
        if isinstance(exc, EngineV2SearchCaseFailure):
            diagnostics = exc.diagnostics
            diagnostic_evaluation_seconds = exc.diagnostic_evaluation_seconds
        elif isinstance(exc, EngineV2PreparationFailure):
            diagnostics = PublicRedockingEngineV2Diagnostics(
                preparation_status="failure",
                preparation_failure_code=exc.preparation_failure_code,
                receptor_atom_count=0,
                ligand_atom_count=0,
                receptor_partial_charge_count=0,
                ligand_partial_charge_count=0,
                receptor_donor_count=0,
                receptor_acceptor_count=0,
                ligand_donor_count=0,
                ligand_acceptor_count=0,
            )
        elif diagnostics is None:
            diagnostics = PublicRedockingEngineV2Diagnostics(
                preparation_status="failure",
                preparation_failure_code="unclassified_engine_v2_case_failure",
                receptor_atom_count=0,
                ligand_atom_count=0,
                receptor_partial_charge_count=0,
                ligand_partial_charge_count=0,
                receptor_donor_count=0,
                receptor_acceptor_count=0,
                ligand_donor_count=0,
                ligand_acceptor_count=0,
            )
        return PublicRedockingCaseResult(
            case_id=case_id,
            engine_id="engine_v2",
            status="failure",
            runtime_seconds=max(
                0.0,
                time.perf_counter()
                - started
                - diagnostic_evaluation_seconds,
            ),
            **_result_input_fields(input_sha256s),
            execution_command=command,
            execution_policy=execution_policy,
            failure_code=_engine_v2_failure_code(exc),
            engine_v2_diagnostics=diagnostics,
        )
    runtime = max(
        0.0,
        time.perf_counter() - started - diagnostic_evaluation_seconds,
    )
    rmsds, geometric, chemical = _posebusters_outcomes(
        pose_payload,
        native_payload=paths["native"].read_bytes(),
        receptor_payload=paths["receptor"].read_bytes(),
    )
    return PublicRedockingCaseResult(
        case_id=case_id,
        engine_id="engine_v2",
        status="success",
        runtime_seconds=runtime,
        **_result_input_fields(input_sha256s),
        execution_command=command,
        execution_policy=execution_policy,
        rmsd_angstroms=rmsds,
        geometric_valid=geometric,
        chemical_valid=chemical,
        pose_artifact_sha256s=artifacts,
        engine_v2_diagnostics=diagnostics,
    )


def _external_result(
    case_id: str,
    engine_id: str,
    paths: dict[str, Path],
    *,
    binary: PinnedExternalBinary,
    input_descriptors: Sequence[int] = (),
    input_sha256s: dict[str, str],
    external_paths: dict[str, Path] | None = None,
    logical_paths: dict[str, Path] | None = None,
    output: Path,
    seed: int,
    timeout_seconds: int,
) -> tuple[PublicRedockingCaseResult, tuple[str, ...]]:
    _verify_external_binary(binary)
    active_external_paths = paths if external_paths is None else external_paths
    command = _external_command(
        case_id,
        engine_id,
        paths if logical_paths is None else logical_paths,
        binary=binary.path,
        output=output,
        seed=seed,
    )
    with ExitStack() as stack:
        output_directory_descriptor = _owned_directory_descriptor(
            output.parent,
            create=True,
        )
        stack.callback(os.close, output_directory_descriptor)
        try:
            stale_status = os.stat(
                output.name,
                dir_fd=output_directory_descriptor,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            stale_status = None
        if stale_status is not None:
            if not stat.S_ISREG(stale_status.st_mode):
                raise PublicRedockingRunnerError(
                    "stale external pose output is not a regular file"
                )
            os.rename(
                output.name,
                f"{output.name}.stale-{time.time_ns()}",
                src_dir_fd=output_directory_descriptor,
                dst_dir_fd=output_directory_descriptor,
            )
        executed_command = list(command)
        executed_command[0] = binary.execution_path
        for option, role in (
            ("--receptor", "receptor"),
            ("--ligand", "seed"),
            ("--autobox_ligand", "native"),
        ):
            option_index = executed_command.index(option)
            executed_command[option_index + 1] = str(active_external_paths[role])
        output_index = executed_command.index("--out")
        executed_command[output_index + 1] = (
            f"/proc/self/fd/{output_directory_descriptor}/{output.name}"
        )
        execution_policy = _execution_policy_tokens(
            _external_execution_policy(timeout_seconds)
        )
        started = time.perf_counter()
        try:
            completed = subprocess.run(
                tuple(executed_command),
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                pass_fds=tuple(
                    dict.fromkeys(
                        (
                            binary.descriptor,
                            output_directory_descriptor,
                            *input_descriptors,
                        )
                    )
                ),
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return (
                PublicRedockingCaseResult(
                    case_id=case_id,
                    engine_id=engine_id,
                    status="failure",
                    runtime_seconds=time.perf_counter() - started,
                    **_result_input_fields(input_sha256s),
                    execution_command=command,
                    execution_policy=execution_policy,
                    failure_code="external_timeout",
                ),
                command,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise PublicRedockingRunnerError(
                "external engine infrastructure failed"
            ) from exc
        finally:
            _verify_external_binary(binary)
        runtime = time.perf_counter() - started
        if completed.returncode != 0:
            return (
                PublicRedockingCaseResult(
                    case_id=case_id,
                    engine_id=engine_id,
                    status="failure",
                    runtime_seconds=runtime,
                    **_result_input_fields(input_sha256s),
                    execution_command=command,
                    execution_policy=execution_policy,
                    failure_code="external_process_failed",
                ),
                command,
            )
        try:
            output_descriptor = os.open(
                output.name,
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=output_directory_descriptor,
            )
        except FileNotFoundError:
            return (
                PublicRedockingCaseResult(
                    case_id=case_id,
                    engine_id=engine_id,
                    status="failure",
                    runtime_seconds=runtime,
                    **_result_input_fields(input_sha256s),
                    execution_command=command,
                    execution_policy=execution_policy,
                    failure_code="external_process_failed",
                ),
                command,
            )
        stack.callback(os.close, output_descriptor)
        if not stat.S_ISREG(os.fstat(output_descriptor).st_mode):
            raise PublicRedockingRunnerError(
                "external pose output is not a regular file"
            )
        output_payload = _bytes_from_descriptor(output_descriptor)
        try:
            records = _split_sdf_records(output_payload)
        except PublicRedockingRunnerError:
            return (
                PublicRedockingCaseResult(
                    case_id=case_id,
                    engine_id=engine_id,
                    status="failure",
                    runtime_seconds=runtime,
                    **_result_input_fields(input_sha256s),
                    execution_command=command,
                    execution_policy=execution_policy,
                    failure_code="external_pose_output_invalid",
                ),
                command,
            )
        if len(records) != 5:
            return (
                PublicRedockingCaseResult(
                    case_id=case_id,
                    engine_id=engine_id,
                    status="failure",
                    runtime_seconds=runtime,
                    **_result_input_fields(input_sha256s),
                    execution_command=command,
                    execution_policy=execution_policy,
                    failure_code="external_pose_count_incomplete",
                ),
                command,
            )
        artifacts = tuple(_sha256_bytes(record) for record in records)
        rmsds, geometric, chemical = _posebusters_outcomes(
            output_payload,
            native_payload=paths["native"].read_bytes(),
            receptor_payload=paths["receptor"].read_bytes(),
        )
        return (
            PublicRedockingCaseResult(
                case_id=case_id,
                engine_id=engine_id,
                status="success",
                runtime_seconds=runtime,
                **_result_input_fields(input_sha256s),
                execution_command=command,
                execution_policy=execution_policy,
                rmsd_angstroms=rmsds,
                geometric_valid=geometric,
                chemical_valid=chemical,
                pose_artifact_sha256s=artifacts,
            ),
            command,
        )


def _input_sha256s(paths: dict[str, Path]) -> dict[str, str]:
    return {
        role: _sha256_path(paths[role])
        for role in ("receptor", "reference", "native", "seed")
    }


def _result_input_fields(input_sha256s: dict[str, str]) -> dict[str, str]:
    if set(input_sha256s) != {"receptor", "reference", "native", "seed"}:
        raise PublicRedockingRunnerError("case input hash roles are incomplete")
    return {
        "receptor_artifact_sha256": input_sha256s["receptor"],
        "reference_artifact_sha256": input_sha256s["reference"],
        "native_artifact_sha256": input_sha256s["native"],
        "seed_artifact_sha256": input_sha256s["seed"],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--source-identifiers", type=Path, required=True)
    parser.add_argument("--gnina", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--bootstrap-samples", type=int, default=2_000)
    parser.add_argument(
        "--case-subset",
        choices=("all", "engineering-smoke", "primary-blind-holdout"),
        default="all",
    )
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--limit", type=int, default=0)
    return parser


def _evaluation_policy_from_arguments(
    arguments: argparse.Namespace,
) -> PublicRedockingEvaluationPolicy:
    return PublicRedockingEvaluationPolicy(
        bootstrap_samples=arguments.bootstrap_samples,
        bootstrap_seed=arguments.seed,
        external_timeout_seconds=arguments.timeout_seconds,
        cpu_count=1,
    )


def _case_ids_from_arguments(arguments: argparse.Namespace) -> tuple[str, ...]:
    all_case_ids = FROZEN_PUBLIC_REDOCKING_CASE_IDS
    if arguments.case_subset != "all":
        if arguments.start_index != 0 or arguments.limit != 0:
            raise PublicRedockingRunnerError(
                "explicit case subsets cannot be combined with start-index or limit"
            )
        return (
            PUBLIC_REDOCKING_ENGINEERING_SMOKE_CASE_IDS
            if arguments.case_subset == "engineering-smoke"
            else PUBLIC_REDOCKING_PRIMARY_BLIND_HOLDOUT_CASE_IDS
        )
    if not 0 <= arguments.start_index < len(all_case_ids):
        raise PublicRedockingRunnerError("start-index is outside the cohort")
    end_index = len(all_case_ids)
    if arguments.limit:
        if arguments.limit < 1:
            raise PublicRedockingRunnerError("limit is outside the cohort")
        end_index = min(end_index, arguments.start_index + arguments.limit)
    return all_case_ids[arguments.start_index : end_index]


def _partial_summary_filename(
    case_subset: str,
    case_ids: Sequence[str],
) -> str:
    selection_sha256 = hashlib.sha256(
        _canonical_bytes(list(case_ids))
    ).hexdigest()
    return (
        f"partial-summary-{case_subset}-{len(case_ids):03d}-"
        f"{selection_sha256[:16]}.json"
    )


def _report_engine_identities(
    *,
    binary: Path,
    binary_version: str,
    binary_sha256: str,
    engine_source_sha256: str,
    evaluation_pipeline_sha256: str,
    timeout_seconds: int,
) -> tuple[PublicRedockingEngineIdentity, ...]:
    return (
        PublicRedockingEngineIdentity(
            engine_id="engine_v2",
            version=(f"source-stage7; torch {ENGINE_V2_CPU_POLICY['torch_version']}"),
            implementation_sha256=engine_source_sha256,
            evaluation_pipeline_sha256=evaluation_pipeline_sha256,
            command=(
                RUNNER_ID,
                "engine_v2",
                "--candidate-count",
                str(ENGINE_V2_CANDIDATE_COUNT),
                "--cpu",
                "1",
                "--torch-version",
                str(ENGINE_V2_CPU_POLICY["torch_version"]),
            ),
        ),
        PublicRedockingEngineIdentity(
            engine_id="vina",
            version=f"{binary_version}; vina scoring; CNN disabled",
            implementation_sha256=binary_sha256,
            evaluation_pipeline_sha256=evaluation_pipeline_sha256,
            command=(
                str(binary),
                "--scoring",
                "vina",
                "--cnn_scoring",
                "none",
                "--cpu",
                "1",
                "--no_gpu",
                "--timeout-seconds",
                str(timeout_seconds),
            ),
        ),
        PublicRedockingEngineIdentity(
            engine_id="gnina",
            version=f"{binary_version}; crossdock_default2018 CNN rescore",
            implementation_sha256=binary_sha256,
            evaluation_pipeline_sha256=evaluation_pipeline_sha256,
            command=(
                str(binary),
                "--scoring",
                "vina",
                "--cnn_scoring",
                "rescore",
                "--cnn",
                "crossdock_default2018",
                "--cpu",
                "1",
                "--no_gpu",
                "--timeout-seconds",
                str(timeout_seconds),
            ),
        ),
    )


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    archive_path = arguments.archive.resolve()
    source_identifiers = arguments.source_identifiers.resolve()
    source_binary = arguments.gnina.resolve()
    output_root = Path(os.path.abspath(arguments.output_root))
    output_root_descriptor = _owned_directory_descriptor(
        output_root,
        create=True,
        exact_mode=0o700,
    )
    os.close(output_root_descriptor)
    _quarantine_managed_regular_file(
        output_root / "public-redocking-report.json",
        label="prior public redocking report",
        required_mode=0o600,
    )
    if not source_identifiers.is_file():
        raise PublicRedockingRunnerError(
            "published 308-case identifier document is missing"
        )
    verify_public_redocking_source_identifiers(source_identifiers.read_bytes())
    pinned_binary = _stage_external_binary(
        source_binary,
        output_root=output_root,
    )
    _verify_external_binary(pinned_binary)
    _load_rdkit_modules()
    _load_posebusters()
    evaluator_versions = _evaluator_environment_versions()
    _configure_engine_v2_cpu()
    if (
        type(arguments.seed) is not int
        or arguments.seed != PUBLIC_REDOCKING_CASE_SEED_BASE
    ):
        raise PublicRedockingRunnerError(
            "seed must equal the frozen public redocking case-seed base"
        )
    evaluation_policy = _evaluation_policy_from_arguments(arguments)
    binary_version = _binary_version(pinned_binary)
    _verify_external_binary(pinned_binary)
    engine_source_sha256 = _engine_source_sha256(repo_root)
    evaluation_pipeline_sha256 = _evaluation_pipeline_sha256(
        repo_root,
        evaluator_versions=evaluator_versions,
    )
    execution_environment = _execution_environment_identity()
    all_case_ids = FROZEN_PUBLIC_REDOCKING_CASE_IDS
    case_ids = _case_ids_from_arguments(arguments)
    partial_run = tuple(case_ids) != all_case_ids

    profiles: list[PublicRedockingCaseProfile] = []
    materializations: list[VerifiedCaseMaterialization] = []
    frozen_profiles = {
        profile.case_id: profile for profile in frozen_public_redocking_profiles()
    }
    rows_by_engine: dict[str, list[PublicRedockingCaseResult]] = {
        engine_id: [] for engine_id in PUBLIC_REDOCKING_PRIMARY_ENGINES
    }
    executions_by_engine: dict[
        str, list[VerifiedPublicRedockingCaseExecution]
    ] = {engine_id: [] for engine_id in PUBLIC_REDOCKING_PRIMARY_ENGINES}
    with VerifiedPublicRedockingArchive.open(archive_path) as archive:
        for case_id in case_ids:
            index = all_case_ids.index(case_id)
            paths, materialization = _materialize_case_inputs(
                archive,
                case_id,
                output_root / "inputs",
            )
            materializations.append(materialization)
            _atomic_json(
                output_root / "receipts" / "materializations" / f"{case_id}.json",
                materialization.to_dict(),
            )
            inputs = materialization.input_artifact_sha256s_by_role
            _require_case_input_identity(paths, inputs)
            case_seed = frozen_public_redocking_case_seed(case_id)
            print(f"[{index + 1}/{len(all_case_ids)}] {case_id}", flush=True)
            with PinnedCaseInputs(paths, inputs) as pinned_inputs:
                execution_paths = pinned_inputs.execution_paths
                with pinned_inputs.verified_window():
                    profiles.append(
                        _profile(
                            case_id,
                            execution_paths,
                            frozen_profiles[case_id],
                        )
                    )

                engine_output = output_root / "poses" / "engine_v2" / f"{case_id}.sdf"
                engine_command = _engine_v2_command(
                    case_id,
                    paths,
                    output=engine_output,
                    seed=case_seed,
                )
                engine_receipt = (
                    output_root / "receipts" / "engine_v2" / f"{case_id}.json"
                )
                with pinned_inputs.verified_window():
                    engine_row = _engine_v2_result(
                        case_id,
                        execution_paths,
                        logical_paths=paths,
                        input_sha256s=inputs,
                        output=engine_output,
                        seed=case_seed,
                    )
                pinned_inputs.verify()
                engine_execution = _verified_case_execution(
                    engine_row,
                    command=engine_command,
                    execution_policy=ENGINE_V2_CPU_POLICY,
                    input_sha256s=inputs,
                    materialization_receipt_sha256=(materialization.receipt_sha256),
                    implementation_sha256=engine_source_sha256,
                    evaluation_pipeline_sha256=(evaluation_pipeline_sha256),
                    execution_environment_sha256=(execution_environment.sha256),
                )
                _atomic_json(
                    engine_receipt,
                    engine_execution.to_dict(),
                )
                rows_by_engine["engine_v2"].append(engine_row)
                executions_by_engine["engine_v2"].append(engine_execution)

                for engine_id in ("vina", "gnina"):
                    pose_output = output_root / "poses" / engine_id / f"{case_id}.sdf"
                    receipt = output_root / "receipts" / engine_id / f"{case_id}.json"
                    with pinned_inputs.verified_window():
                        row, command = _external_result(
                            case_id,
                            engine_id,
                            execution_paths,
                            binary=pinned_binary,
                            input_descriptors=pinned_inputs.descriptors,
                            input_sha256s=inputs,
                            external_paths=pinned_inputs.external_execution_paths,
                            logical_paths=paths,
                            output=pose_output,
                            seed=case_seed,
                            timeout_seconds=arguments.timeout_seconds,
                        )
                    pinned_inputs.verify()
                    execution = _verified_case_execution(
                        row,
                        command=command,
                        execution_policy=_external_execution_policy(
                            arguments.timeout_seconds
                        ),
                        input_sha256s=inputs,
                        materialization_receipt_sha256=(
                            materialization.receipt_sha256
                        ),
                        implementation_sha256=pinned_binary.sha256,
                        evaluation_pipeline_sha256=(evaluation_pipeline_sha256),
                        execution_environment_sha256=(execution_environment.sha256),
                    )
                    _atomic_json(
                        receipt,
                        execution.to_dict(),
                    )
                    rows_by_engine[engine_id].append(row)
                    executions_by_engine[engine_id].append(execution)
                pinned_inputs.verify()
            _require_case_input_identity(paths, inputs)
            _remove_materialized_case_inputs(paths, inputs)

    if partial_run:
        _verify_external_binary(pinned_binary)
        if tuple(case_ids) == PUBLIC_REDOCKING_ENGINEERING_SMOKE_CASE_IDS:
            analysis_scope = "engineering_smoke"
        elif all(
            case_id in PUBLIC_REDOCKING_PRIMARY_BLIND_HOLDOUT_CASE_IDS
            for case_id in case_ids
        ):
            analysis_scope = "primary_blind_holdout_partial"
        else:
            analysis_scope = "mixed_nonclaimable_partial"
        summary = {
            "runner_id": RUNNER_ID,
            "partial_case_count": len(case_ids),
            "analysis_scope": analysis_scope,
            "primary_claim_eligible": False,
            "materializations": [
                materialization.to_dict() for materialization in materializations
            ],
            "rows": [
                row.to_dict()
                for engine_id in PUBLIC_REDOCKING_PRIMARY_ENGINES
                for row in rows_by_engine[engine_id]
            ],
            "execution_receipts": [
                execution.to_dict()
                for engine_id in PUBLIC_REDOCKING_PRIMARY_ENGINES
                for execution in executions_by_engine[engine_id]
            ],
            "claim_safe": False,
        }
        _atomic_json(
            output_root
            / _partial_summary_filename(arguments.case_subset, case_ids),
            summary,
        )
        pinned_binary.close()
        return 0

    _verify_external_binary(pinned_binary)
    identities = _report_engine_identities(
        binary=pinned_binary.path,
        binary_version=binary_version,
        binary_sha256=pinned_binary.sha256,
        engine_source_sha256=engine_source_sha256,
        evaluation_pipeline_sha256=evaluation_pipeline_sha256,
        timeout_seconds=arguments.timeout_seconds,
    )
    ordered_executions = tuple(
        execution
        for engine_id in PUBLIC_REDOCKING_PRIMARY_ENGINES
        for execution in executions_by_engine[engine_id]
    )
    report = build_public_redocking_benchmark_report(
        tuple(profiles),
        identities,
        ordered_executions,
        materializations=tuple(materializations),
        policy=evaluation_policy,
    )
    _verify_external_binary(pinned_binary)
    _atomic_json(output_root / "public-redocking-report.json", report.to_dict())
    print(report.fingerprint_sha256)
    pinned_binary.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
