"""Strict, failure-inclusive Meeko preparation for PoseBusters 308.

This module turns the verified PoseBusters archive and corpus-audit receipts
into exact receptor/ligand PDBQT artifacts for the bounded chemistry subset.
Cases outside that subset remain explicit abstentions, and strict receptor
template failures remain failure rows.  ``allow_bad_res`` is never enabled.

The native crystal ligand is used only to define a frozen redocking-box
centroid.  Ligand preparation consumes the supplied start conformer.  No
external docking engine is launched and no docking or pose-validity claim is
made here.
"""

from __future__ import annotations

from dataclasses import dataclass
import argparse
import ast
import copy
import contextlib
import hashlib
import importlib
import importlib.metadata
import json
import math
import os
from pathlib import Path, PurePosixPath
import platform
import re
import stat
import sys
import tempfile
from typing import Any, Callable, Protocol, Sequence
import zipfile

from betelgeuze_engine_v2.io import SDFParseError, parse_sdf_v2000

from .public_external_baseline import PUBLIC_EXTERNAL_BASELINE_BOX_SIZE_ANGSTROM
from .public_posebusters_corpus_audit import (
    PoseBustersCorpusAuditError,
    PoseBustersCorpusAuditReceipt,
    _canonical_bytes,
    _canonical_sha256,
    _positive_int,
    _read_member,
    _source_file_sha256,
    _token,
    verify_posebusters_corpus_audit_receipt,
)
from .public_posebusters_intake import (
    OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT,
    PoseBustersArchiveContract,
    PoseBustersArchiveIntakeError,
    _hash_descriptor,
    _read_exact_regular_file,
    _regular_file_descriptor,
    verify_posebusters_archive_intake_receipt,
)


POSEBUSTERS_EXTERNAL_PREPARATION_ARTIFACT_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_external_preparation_artifact/1.0.0"
)
POSEBUSTERS_EXTERNAL_PREPARATION_CASE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_external_preparation_case/1.0.0"
)
POSEBUSTERS_EXTERNAL_PREPARATION_DEPENDENCY_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_external_preparation_dependency/1.0.0"
)
POSEBUSTERS_EXTERNAL_PREPARATION_RUNTIME_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_external_preparation_runtime/1.0.0"
)
POSEBUSTERS_EXTERNAL_PREPARATION_METRIC_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_external_preparation_metric/1.0.0"
)
POSEBUSTERS_EXTERNAL_PREPARATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_external_preparation/1.0.0"
)
POSEBUSTERS_EXTERNAL_PREPARATION_MAX_RECEIPT_BYTES = 4 * 1024 * 1024
POSEBUSTERS_EXTERNAL_PREPARATION_MAX_ARTIFACT_BYTES = 32 * 1024 * 1024
POSEBUSTERS_EXTERNAL_PREPARATION_MAX_DEPENDENCY_FILE_BYTES = 512 * 1024 * 1024
POSEBUSTERS_EXTERNAL_PREPARATION_MAX_DEPENDENCY_FILES = 100_000
POSEBUSTERS_EXTERNAL_PREPARATION_MAX_DEPENDENCY_BYTES = 2 * 1024 * 1024 * 1024
POSEBUSTERS_EXTERNAL_PREPARATION_CONFIDENCE_LEVEL = 0.95
POSEBUSTERS_EXTERNAL_PREPARATION_Z = 1.959963984540054
POSEBUSTERS_EXTERNAL_PREPARATION_CONFIGURATION = {
    "add_atom_types": None,
    "add_index_map": False,
    "charge_atom_prop": None,
    "charge_model": "gasteiger",
    "dihedral_model": None,
    "double_bond_penalty": 50,
    "flexible_amides": False,
    "hydrate": False,
    "input_atom_params": None,
    "input_offatom_params": None,
    "keep_chorded_rings": False,
    "keep_equivalent_rings": False,
    "load_atom_params": "ad4_types",
    "load_offatom_params": None,
    "macrocycle_allow_A": False,
    "max_ring_size": 33,
    "merge_these_atom_types": ("H",),
    "min_ring_size": 7,
    "reactive_smarts": None,
    "reactive_smarts_idx": None,
    "remove_smiles": False,
    "rigid_macrocycles": False,
    "rigidify_bonds_indices": [],
    "rigidify_bonds_smarts": [],
    "untyped_macrocycles": False,
}
POSEBUSTERS_EXTERNAL_PREPARATION_CONFIGURATION_SHA256 = (
    "43612516a9516d4eb084590a8bcaef7c34c3762ca226ea828997cfa5269f9229"
)
POSEBUSTERS_EXTERNAL_PREPARATION_DEPENDENCY_PINS = {
    "gemmi": "0.7.5",
    "meeko": "0.7.1",
    "numpy": "1.26.4",
    "rdkit": "2025.9.6",
    "scipy": "1.12.0",
    "tqdm": "4.67.1",
}
POSEBUSTERS_EXTERNAL_PREPARATION_BLOCKERS = (
    "strict_meeko_preparation_not_independently_audited",
    "default_ad4_atom_types_and_gasteiger_charges_not_scientifically_validated",
    "strict_receptor_template_failures_not_repaired",
    "unsupported_metals_cofactors_and_chemistry_remain_abstentions",
    "native_crystal_ligand_used_only_for_redocking_box_center",
    "external_vina_gnina_smina_execution_results_missing",
    "generated_pose_validity_and_symmetry_rmsd_receipts_missing",
    "target_family_and_leakage_receipts_missing",
    "independent_external_rerun_missing",
    "scientific_review_missing",
)

_CANDIDATE_SCOPE_STATUS = "blocked_parameters_and_partial_charges_missing"
_ARTIFACT_ROLES = (
    "prepared_ligand_pdbqt",
    "prepared_receptor_pdbqt",
)
_CASE_STATUSES = {
    "abstain_chemistry_scope",
    "prepared",
    "preparation_failure",
    "upstream_failure",
}
_DEPENDENCY_METADATA_EXCLUSIONS = {
    "direct_url.json",
    "INSTALLER",
    "RECORD",
    "REQUESTED",
}
_SHA256_CHARACTERS = frozenset("0123456789abcdef")
_TEMPLATE_FAILURE_PATTERN = re.compile(
    r"Template matching failed for:\s*(\[[^\]]*\])",
    flags=re.DOTALL,
)


class PoseBustersExternalPreparationError(ValueError):
    """External preparation input, runtime, artifact, or receipt is invalid."""


class PoseBustersExternalPreparationExecutionError(RuntimeError):
    """One strict preparation attempt failed with a bounded disposition."""

    def __init__(
        self,
        *,
        stage: str,
        error_code: str,
        error_type: str,
        error_message_sha256: str,
        failing_residue_keys: Sequence[str] = (),
        ligand_preparation_succeeded: bool = False,
        diagnostic_sha256: str,
        diagnostic_size_bytes: int,
    ) -> None:
        super().__init__(error_code)
        self.stage = _token(stage, name="preparation failure stage")
        self.error_code = _token(error_code, name="preparation error code")
        self.error_type = _identifier(error_type, name="preparation error type")
        self.error_message_sha256 = _digest_value(
            error_message_sha256,
            name="preparation error message",
        )
        self.failing_residue_keys = _residue_keys(failing_residue_keys)
        self.ligand_preparation_succeeded = bool(ligand_preparation_succeeded)
        self.diagnostic_sha256 = _digest_value(
            diagnostic_sha256,
            name="preparation diagnostic",
        )
        self.diagnostic_size_bytes = _positive_int(
            diagnostic_size_bytes,
            name="preparation diagnostic size",
            allow_zero=True,
        )


def _digest_value(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in _SHA256_CHARACTERS for character in value)
    ):
        raise PoseBustersExternalPreparationError(
            f"{name} must be a lowercase SHA-256"
        )
    return value


def _case_id(value: object) -> str:
    if not isinstance(value, str):
        raise PoseBustersExternalPreparationError("case ID must be text")
    result = value.strip()
    parts = result.split("_")
    if (
        len(parts) != 2
        or len(parts[0]) != 4
        or len(parts[1]) != 3
        or not all(
            part.isascii() and part.isalnum() and part.upper() == part
            for part in parts
        )
    ):
        raise PoseBustersExternalPreparationError(
            "case ID must use uppercase PDB4_CCD3 form"
        )
    return result


def _identifier(value: object, *, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise PoseBustersExternalPreparationError(f"{name} must be non-empty text")
    if (
        not value.isascii()
        or not (value[0].isalpha() or value[0] == "_")
        or any(not (character.isalnum() or character == "_") for character in value)
    ):
        raise PoseBustersExternalPreparationError(f"{name} must be an identifier")
    return value


def _relative_path(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise PoseBustersExternalPreparationError(
            "prepared artifact path must be non-empty text"
        )
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise PoseBustersExternalPreparationError(
            "prepared artifact path must remain below artifact root"
        )
    return path.as_posix()


def _finite_hex(value: float, *, name: str) -> str:
    number = float(value)
    if not math.isfinite(number):
        raise PoseBustersExternalPreparationError(f"{name} must be finite")
    return number.hex()


def _validate_hex(value: object, *, name: str) -> str:
    if not isinstance(value, str):
        raise PoseBustersExternalPreparationError(
            f"{name} must be hexadecimal binary64"
        )
    try:
        number = float.fromhex(value)
    except ValueError as exc:
        raise PoseBustersExternalPreparationError(
            f"{name} must be hexadecimal binary64"
        ) from exc
    if not math.isfinite(number) or number.hex() != value:
        raise PoseBustersExternalPreparationError(
            f"{name} must be canonical finite binary64"
        )
    return value


def _residue_keys(values: Sequence[str]) -> tuple[str, ...]:
    rows = tuple(str(value).strip() for value in values)
    if (
        len(rows) > 10_000
        or len(set(rows)) != len(rows)
        or any(
            not value
            or len(value) > 64
            or not value.isascii()
            or any(ord(character) < 33 or ord(character) > 126 for character in value)
            for value in rows
        )
    ):
        raise PoseBustersExternalPreparationError(
            "failing residue keys are not bounded canonical text"
        )
    return rows


def _hash_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _hash_regular_file(path: Path, *, maximum_bytes: int) -> tuple[str, int, int]:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    except (OSError, TypeError) as exc:
        raise PoseBustersExternalPreparationError(
            "runtime payload file could not be opened without following links"
        ) from exc
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_size < 0
            or metadata.st_size > maximum_bytes
        ):
            raise PoseBustersExternalPreparationError(
                "runtime payload file is not a bounded regular file"
            )
        digest = hashlib.sha256()
        observed = 0
        while True:
            chunk = os.read(descriptor, min(1024 * 1024, metadata.st_size - observed))
            if not chunk:
                break
            digest.update(chunk)
            observed += len(chunk)
        if observed != metadata.st_size:
            raise PoseBustersExternalPreparationError(
                "runtime payload file changed while hashing"
            )
        return digest.hexdigest(), observed, stat.S_IMODE(metadata.st_mode)
    finally:
        os.close(descriptor)


@dataclass(frozen=True, slots=True)
class PoseBustersExternalPreparationDependency:
    distribution_name: str
    version: str
    payload_sha256: str
    payload_file_count: int
    payload_size_bytes: int
    schema_id: str = POSEBUSTERS_EXTERNAL_PREPARATION_DEPENDENCY_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_EXTERNAL_PREPARATION_DEPENDENCY_SCHEMA_ID:
            raise PoseBustersExternalPreparationError(
                "unsupported external-preparation dependency schema"
            )
        name = _token(self.distribution_name, name="distribution name")
        version = str(self.version).strip()
        if not version or len(version) > 128 or not version.isascii():
            raise PoseBustersExternalPreparationError(
                "dependency version must be bounded ASCII text"
            )
        object.__setattr__(self, "distribution_name", name)
        object.__setattr__(self, "version", version)
        object.__setattr__(
            self,
            "payload_sha256",
            _digest_value(self.payload_sha256, name=f"{name} payload"),
        )
        object.__setattr__(
            self,
            "payload_file_count",
            _positive_int(self.payload_file_count, name=f"{name} payload file count"),
        )
        object.__setattr__(
            self,
            "payload_size_bytes",
            _positive_int(self.payload_size_bytes, name=f"{name} payload size"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "distribution_name": self.distribution_name,
            "version": self.version,
            "payload_sha256": self.payload_sha256,
            "payload_file_count": self.payload_file_count,
            "payload_size_bytes": self.payload_size_bytes,
            "payload_policy": (
                "distribution_files_regular_no_parent_paths_no_pyc_no_mutable_install_metadata"
            ),
        }


@dataclass(frozen=True, slots=True)
class PoseBustersExternalPreparationRuntime:
    python_implementation: str
    python_version: str
    python_cache_tag: str
    python_executable_sha256: str
    python_executable_size_bytes: int
    platform_system: str
    platform_machine: str
    libc_name: str
    libc_version: str
    filesystem_encoding: str
    torch_version: str
    dependencies: tuple[PoseBustersExternalPreparationDependency, ...]
    schema_id: str = POSEBUSTERS_EXTERNAL_PREPARATION_RUNTIME_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_EXTERNAL_PREPARATION_RUNTIME_SCHEMA_ID:
            raise PoseBustersExternalPreparationError(
                "unsupported external-preparation runtime schema"
            )
        for field_name in (
            "python_implementation",
            "python_version",
            "python_cache_tag",
            "platform_system",
            "platform_machine",
            "filesystem_encoding",
            "torch_version",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value or len(value) > 512 or not value.isascii():
                raise PoseBustersExternalPreparationError(
                    f"{field_name} must be bounded ASCII runtime identity"
                )
            object.__setattr__(self, field_name, value)
        for field_name in ("libc_name", "libc_version"):
            value = str(getattr(self, field_name)).strip()
            if len(value) > 128 or not value.isascii():
                raise PoseBustersExternalPreparationError(
                    f"{field_name} must be bounded ASCII runtime identity"
                )
            object.__setattr__(self, field_name, value)
        object.__setattr__(
            self,
            "python_executable_sha256",
            _digest_value(
                self.python_executable_sha256,
                name="Python executable",
            ),
        )
        object.__setattr__(
            self,
            "python_executable_size_bytes",
            _positive_int(
                self.python_executable_size_bytes,
                name="Python executable size",
            ),
        )
        dependencies = tuple(self.dependencies)
        if (
            not dependencies
            or tuple(row.distribution_name for row in dependencies)
            != tuple(sorted(row.distribution_name for row in dependencies))
            or len({row.distribution_name for row in dependencies}) != len(dependencies)
        ):
            raise PoseBustersExternalPreparationError(
                "runtime dependencies must be canonical unique rows"
            )
        object.__setattr__(self, "dependencies", dependencies)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "python_implementation": self.python_implementation,
            "python_version": self.python_version,
            "python_cache_tag": self.python_cache_tag,
            "python_executable_sha256": self.python_executable_sha256,
            "python_executable_size_bytes": self.python_executable_size_bytes,
            "platform_system": self.platform_system,
            "platform_machine": self.platform_machine,
            "libc_name": self.libc_name,
            "libc_version": self.libc_version,
            "filesystem_encoding": self.filesystem_encoding,
            "torch_version": self.torch_version,
            "dependencies": [row.to_dict() for row in self.dependencies],
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


class _DigestingTextSink:
    def __init__(self) -> None:
        self._digest = hashlib.sha256()
        self.size_bytes = 0

    def write(self, value: str) -> int:
        if not isinstance(value, str):
            raise TypeError("diagnostic sink accepts text")
        source = value.encode("utf-8", errors="backslashreplace")
        self._digest.update(source)
        self.size_bytes += len(source)
        return len(value)

    def flush(self) -> None:
        return None

    @property
    def sha256(self) -> str:
        return self._digest.hexdigest()


@dataclass(frozen=True, slots=True)
class PoseBustersExternalPreparedBytes:
    receptor_pdbqt: bytes
    ligand_pdbqt: bytes
    diagnostic_sha256: str
    diagnostic_size_bytes: int

    def __post_init__(self) -> None:
        for name in ("receptor_pdbqt", "ligand_pdbqt"):
            value = getattr(self, name)
            if (
                not isinstance(value, bytes)
                or not value
                or len(value) > POSEBUSTERS_EXTERNAL_PREPARATION_MAX_ARTIFACT_BYTES
                or b"\x00" in value
            ):
                raise PoseBustersExternalPreparationError(
                    f"{name} must be bounded non-empty PDBQT bytes"
                )
        object.__setattr__(
            self,
            "diagnostic_sha256",
            _digest_value(self.diagnostic_sha256, name="preparation diagnostic"),
        )
        object.__setattr__(
            self,
            "diagnostic_size_bytes",
            _positive_int(
                self.diagnostic_size_bytes,
                name="preparation diagnostic size",
                allow_zero=True,
            ),
        )


class _PreparationRuntimeProtocol(Protocol):
    identity: PoseBustersExternalPreparationRuntime
    configuration_sha256: str

    def prepare(
        self,
        receptor_pdb: bytes,
        ligand_start_sdf: bytes,
    ) -> PoseBustersExternalPreparedBytes: ...


def _normalize_error_message(error: BaseException) -> bytes:
    value = str(error).replace("\r\n", "\n").replace("\r", "\n").strip()
    return value.encode("utf-8", errors="backslashreplace")


def _failing_residue_keys(error: BaseException) -> tuple[str, ...]:
    match = _TEMPLATE_FAILURE_PATTERN.search(str(error))
    if match is None:
        return ()
    try:
        parsed = ast.literal_eval(match.group(1))
    except (SyntaxError, ValueError):
        return ()
    if not isinstance(parsed, list) or not all(isinstance(value, str) for value in parsed):
        return ()
    try:
        return _residue_keys(parsed)
    except PoseBustersExternalPreparationError:
        return ()


def _execution_error(
    *,
    stage: str,
    error_code: str,
    error: BaseException,
    ligand_preparation_succeeded: bool,
    sink: _DigestingTextSink,
) -> PoseBustersExternalPreparationExecutionError:
    return PoseBustersExternalPreparationExecutionError(
        stage=stage,
        error_code=error_code,
        error_type=type(error).__name__,
        error_message_sha256=_hash_bytes(_normalize_error_message(error)),
        failing_residue_keys=_failing_residue_keys(error),
        ligand_preparation_succeeded=ligand_preparation_succeeded,
        diagnostic_sha256=sink.sha256,
        diagnostic_size_bytes=sink.size_bytes,
    )


def _dependency_payload(
    distribution_name: str,
    expected_version: str,
) -> PoseBustersExternalPreparationDependency:
    try:
        distribution = importlib.metadata.distribution(distribution_name)
    except importlib.metadata.PackageNotFoundError as exc:
        raise PoseBustersExternalPreparationError(
            f"required external preparation dependency is missing: {distribution_name}"
        ) from exc
    version = distribution.version
    if version != expected_version:
        raise PoseBustersExternalPreparationError(
            f"external preparation dependency pin mismatch: {distribution_name}"
        )
    files = distribution.files
    if files is None:
        raise PoseBustersExternalPreparationError(
            f"external preparation dependency has no file inventory: {distribution_name}"
        )
    payload: dict[str, dict[str, Any]] = {}
    total_size = 0
    for package_path in sorted(files, key=lambda value: str(value)):
        relative = PurePosixPath(str(package_path))
        if relative.is_absolute() or ".." in relative.parts:
            continue
        if "__pycache__" in relative.parts or relative.suffix == ".pyc":
            continue
        if relative.name in _DEPENDENCY_METADATA_EXCLUSIONS and any(
            part.endswith(".dist-info") for part in relative.parts
        ):
            continue
        path = Path(distribution.locate_file(package_path))
        try:
            metadata = path.lstat()
        except OSError as exc:
            raise PoseBustersExternalPreparationError(
                f"external preparation dependency file is missing: {distribution_name}"
            ) from exc
        if not stat.S_ISREG(metadata.st_mode):
            raise PoseBustersExternalPreparationError(
                f"external preparation dependency has non-regular payload: {distribution_name}"
            )
        digest, size, mode = _hash_regular_file(
            path,
            maximum_bytes=POSEBUSTERS_EXTERNAL_PREPARATION_MAX_DEPENDENCY_FILE_BYTES,
        )
        key = relative.as_posix()
        if key in payload:
            raise PoseBustersExternalPreparationError(
                f"external preparation dependency has duplicate payload: {distribution_name}"
            )
        payload[key] = {"sha256": digest, "size_bytes": size, "mode": mode}
        total_size += size
        if (
            len(payload) > POSEBUSTERS_EXTERNAL_PREPARATION_MAX_DEPENDENCY_FILES
            or total_size > POSEBUSTERS_EXTERNAL_PREPARATION_MAX_DEPENDENCY_BYTES
        ):
            raise PoseBustersExternalPreparationError(
                f"external preparation dependency payload is unbounded: {distribution_name}"
            )
    if not payload or total_size < 1:
        raise PoseBustersExternalPreparationError(
            f"external preparation dependency payload is empty: {distribution_name}"
        )
    return PoseBustersExternalPreparationDependency(
        distribution_name=distribution_name,
        version=version,
        payload_sha256=_canonical_sha256(payload),
        payload_file_count=len(payload),
        payload_size_bytes=total_size,
    )


def _runtime_identity(torch_version: str) -> PoseBustersExternalPreparationRuntime:
    executable = Path(sys.executable).resolve(strict=True)
    executable_sha256, executable_size, _mode = _hash_regular_file(
        executable,
        maximum_bytes=POSEBUSTERS_EXTERNAL_PREPARATION_MAX_DEPENDENCY_FILE_BYTES,
    )
    dependencies = tuple(
        _dependency_payload(name, version)
        for name, version in sorted(
            POSEBUSTERS_EXTERNAL_PREPARATION_DEPENDENCY_PINS.items()
        )
    )
    libc_name, libc_version = platform.libc_ver()
    cache_tag = getattr(sys.implementation, "cache_tag", None)
    if not isinstance(cache_tag, str) or not cache_tag:
        raise PoseBustersExternalPreparationError(
            "Python runtime does not expose a cache tag"
        )
    return PoseBustersExternalPreparationRuntime(
        python_implementation=platform.python_implementation(),
        python_version=platform.python_version(),
        python_cache_tag=cache_tag,
        python_executable_sha256=executable_sha256,
        python_executable_size_bytes=executable_size,
        platform_system=platform.system(),
        platform_machine=platform.machine(),
        libc_name=libc_name,
        libc_version=libc_version,
        filesystem_encoding=sys.getfilesystemencoding(),
        torch_version=torch_version,
        dependencies=dependencies,
    )


def _require_import_owned_by_distribution(
    module: Any,
    distribution_name: str,
) -> None:
    module_file = getattr(module, "__file__", None)
    if not isinstance(module_file, str) or not module_file:
        raise PoseBustersExternalPreparationError(
            f"external preparation import has no file identity: {distribution_name}"
        )
    try:
        observed = Path(module_file).resolve(strict=True)
        distribution = importlib.metadata.distribution(distribution_name)
    except (OSError, importlib.metadata.PackageNotFoundError) as exc:
        raise PoseBustersExternalPreparationError(
            f"external preparation import identity failed: {distribution_name}"
        ) from exc
    files = distribution.files
    if files is None:
        raise PoseBustersExternalPreparationError(
            f"external preparation distribution has no file inventory: {distribution_name}"
        )
    owned = False
    for package_path in files:
        relative = PurePosixPath(str(package_path))
        if relative.is_absolute() or ".." in relative.parts:
            continue
        try:
            candidate = Path(distribution.locate_file(package_path)).resolve(strict=True)
        except OSError:
            continue
        if candidate == observed:
            owned = True
            break
    if not owned:
        raise PoseBustersExternalPreparationError(
            f"external preparation import is not owned by its pinned distribution: {distribution_name}"
        )


class _MeekoPreparationRuntime:
    def __init__(
        self,
        *,
        Chem: Any,
        MoleculePreparation: Any,
        PDBQTWriterLegacy: Any,
        Polymer: Any,
        PolymerCreationError: type[BaseException],
        ResidueChemTemplates: Any,
        identity: PoseBustersExternalPreparationRuntime,
    ) -> None:
        self._Chem = Chem
        self._MoleculePreparation = MoleculePreparation
        self._PDBQTWriterLegacy = PDBQTWriterLegacy
        self._Polymer = Polymer
        self._PolymerCreationError = PolymerCreationError
        self._ResidueChemTemplates = ResidueChemTemplates
        self.identity = identity
        self.configuration_sha256 = (
            POSEBUSTERS_EXTERNAL_PREPARATION_CONFIGURATION_SHA256
        )

    def prepare(
        self,
        receptor_pdb: bytes,
        ligand_start_sdf: bytes,
    ) -> PoseBustersExternalPreparedBytes:
        sink = _DigestingTextSink()
        try:
            ligand_text = ligand_start_sdf.decode("ascii")
        except UnicodeDecodeError as exc:
            raise _execution_error(
                stage="ligand_decode",
                error_code="strict_ligand_ascii_decode_failed",
                error=exc,
                ligand_preparation_succeeded=False,
                sink=sink,
            ) from exc
        try:
            with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
                molecule = self._Chem.MolFromMolBlock(
                    ligand_text,
                    sanitize=True,
                    removeHs=False,
                    strictParsing=True,
                )
                if molecule is None:
                    raise ValueError("strict RDKit SDF parse returned None")
                if not any(atom.GetAtomicNum() == 1 for atom in molecule.GetAtoms()):
                    raise ValueError("ligand start conformer has no explicit hydrogen")
                ligand_preparator = self._MoleculePreparation.from_config(
                    copy.deepcopy(POSEBUSTERS_EXTERNAL_PREPARATION_CONFIGURATION)
                )
                setups = ligand_preparator.prepare(molecule, rename_atoms=False)
                if len(setups) != 1:
                    raise ValueError(
                        f"strict ligand preparation expected one setup, got {len(setups)}"
                    )
                ligand_pdbqt, success, error_message = (
                    self._PDBQTWriterLegacy.write_string(
                        setups[0],
                        bad_charge_ok=False,
                        add_index_map=False,
                    )
                )
                if not success:
                    raise ValueError(f"ligand PDBQT writer failed: {error_message}")
                ligand_source = ligand_pdbqt.encode("ascii")
        except PoseBustersExternalPreparationExecutionError:
            raise
        except Exception as exc:
            raise _execution_error(
                stage="ligand_preparation",
                error_code="strict_ligand_preparation_failed",
                error=exc,
                ligand_preparation_succeeded=False,
                sink=sink,
            ) from exc

        try:
            receptor_text = receptor_pdb.decode("ascii")
        except UnicodeDecodeError as exc:
            raise _execution_error(
                stage="receptor_decode",
                error_code="strict_receptor_ascii_decode_failed",
                error=exc,
                ligand_preparation_succeeded=True,
                sink=sink,
            ) from exc
        try:
            with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
                receptor_preparator = self._MoleculePreparation.from_config(
                    copy.deepcopy(POSEBUSTERS_EXTERNAL_PREPARATION_CONFIGURATION)
                )
                templates = self._ResidueChemTemplates.create_from_defaults()
                polymer = self._Polymer.from_pdb_string(
                    receptor_text,
                    templates,
                    receptor_preparator,
                    {},
                    [],
                    False,
                    blunt_ends=[],
                    wanted_altloc=None,
                    default_altloc=None,
                )
                receptor_pdbqt, flexible = (
                    self._PDBQTWriterLegacy.write_from_polymer(polymer)
                )
                if flexible:
                    raise ValueError("strict rigid receptor produced flexible output")
                receptor_source = receptor_pdbqt.encode("ascii")
        except self._PolymerCreationError as exc:
            raise _execution_error(
                stage="receptor_preparation",
                error_code="strict_receptor_template_match_failed",
                error=exc,
                ligand_preparation_succeeded=True,
                sink=sink,
            ) from exc
        except Exception as exc:
            raise _execution_error(
                stage="receptor_preparation",
                error_code="strict_receptor_polymer_construction_failed",
                error=exc,
                ligand_preparation_succeeded=True,
                sink=sink,
            ) from exc
        return PoseBustersExternalPreparedBytes(
            receptor_pdbqt=receptor_source,
            ligand_pdbqt=ligand_source,
            diagnostic_sha256=sink.sha256,
            diagnostic_size_bytes=sink.size_bytes,
        )


def _load_meeko_runtime() -> _PreparationRuntimeProtocol:
    try:
        import torch
        import gemmi
        import meeko
        import numpy
        import rdkit
        import scipy
        import tqdm
        from rdkit import Chem
        from meeko import (
            MoleculePreparation,
            PDBQTWriterLegacy,
            Polymer,
            PolymerCreationError,
            ResidueChemTemplates,
        )
    except ImportError as exc:
        raise PoseBustersExternalPreparationError(
            "strict external preparation requires the pinned optional Meeko runtime"
        ) from exc
    imported_dependencies = {
        "gemmi": gemmi,
        "meeko": meeko,
        "numpy": numpy,
        "rdkit": rdkit,
        "scipy": scipy,
        "tqdm": tqdm,
    }
    for distribution_name, module in sorted(imported_dependencies.items()):
        _require_import_owned_by_distribution(module, distribution_name)
    defaults = MoleculePreparation.get_defaults_dict()
    if (
        _canonical_sha256(defaults)
        != POSEBUSTERS_EXTERNAL_PREPARATION_CONFIGURATION_SHA256
        or defaults != POSEBUSTERS_EXTERNAL_PREPARATION_CONFIGURATION
    ):
        raise PoseBustersExternalPreparationError(
            "Meeko defaults do not match the frozen preparation configuration"
        )
    identity = _runtime_identity(str(torch.__version__))
    return _MeekoPreparationRuntime(
        Chem=Chem,
        MoleculePreparation=MoleculePreparation,
        PDBQTWriterLegacy=PDBQTWriterLegacy,
        Polymer=Polymer,
        PolymerCreationError=PolymerCreationError,
        ResidueChemTemplates=ResidueChemTemplates,
        identity=identity,
    )


@dataclass(frozen=True, slots=True)
class PoseBustersExternalPreparedArtifact:
    role: str
    relative_path: str
    sha256: str
    size_bytes: int
    source_role: str
    source_sha256: str
    schema_id: str = POSEBUSTERS_EXTERNAL_PREPARATION_ARTIFACT_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_EXTERNAL_PREPARATION_ARTIFACT_SCHEMA_ID:
            raise PoseBustersExternalPreparationError(
                "unsupported external-preparation artifact schema"
            )
        if self.role not in _ARTIFACT_ROLES:
            raise PoseBustersExternalPreparationError(
                "external-preparation artifact role is invalid"
            )
        expected_source = {
            "prepared_ligand_pdbqt": "ligand_start_conformer_sdf",
            "prepared_receptor_pdbqt": "receptor_pdb",
        }[self.role]
        if self.source_role != expected_source:
            raise PoseBustersExternalPreparationError(
                "prepared artifact source role is inconsistent"
            )
        object.__setattr__(self, "relative_path", _relative_path(self.relative_path))
        object.__setattr__(
            self,
            "sha256",
            _digest_value(self.sha256, name="prepared artifact"),
        )
        object.__setattr__(
            self,
            "size_bytes",
            _positive_int(self.size_bytes, name="prepared artifact size"),
        )
        if self.size_bytes > POSEBUSTERS_EXTERNAL_PREPARATION_MAX_ARTIFACT_BYTES:
            raise PoseBustersExternalPreparationError(
                "prepared artifact exceeds its bounded size"
            )
        object.__setattr__(
            self,
            "source_sha256",
            _digest_value(self.source_sha256, name="prepared artifact source"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "role": self.role,
            "relative_path": self.relative_path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "media_type": "chemical/x-pdbqt",
            "source_role": self.source_role,
            "source_sha256": self.source_sha256,
        }


@dataclass(frozen=True, slots=True)
class PoseBustersExternalPreparationCase:
    case_id: str
    status: str
    disposition_code: str
    reference_scorer_scope_status: str
    reference_scorer_scope_blockers: tuple[str, ...]
    preparation_attempted: bool = False
    ligand_preparation_succeeded: bool = False
    receptor_preparation_succeeded: bool = False
    artifacts: tuple[PoseBustersExternalPreparedArtifact, ...] = ()
    pocket_center_binary64_hex: tuple[str, ...] = ()
    error_stage: str = ""
    error_code: str = ""
    error_type: str = ""
    error_message_sha256: str = ""
    failing_residue_keys: tuple[str, ...] = ()
    diagnostic_sha256: str = ""
    diagnostic_size_bytes: int = 0
    schema_id: str = POSEBUSTERS_EXTERNAL_PREPARATION_CASE_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_EXTERNAL_PREPARATION_CASE_SCHEMA_ID:
            raise PoseBustersExternalPreparationError(
                "unsupported external-preparation case schema"
            )
        case_id = _case_id(self.case_id)
        if self.status not in _CASE_STATUSES:
            raise PoseBustersExternalPreparationError(
                "external-preparation case status is invalid"
            )
        disposition = _token(self.disposition_code, name="preparation disposition")
        scope_status = _token(
            self.reference_scorer_scope_status,
            name="reference scorer scope status",
        )
        scope_blockers = tuple(
            _token(value, name="reference scorer scope blocker")
            for value in self.reference_scorer_scope_blockers
        )
        if len(set(scope_blockers)) != len(scope_blockers):
            raise PoseBustersExternalPreparationError(
                "reference scorer scope blockers must be unique"
            )
        artifacts = tuple(self.artifacts)
        if (
            tuple(row.role for row in artifacts) != tuple(sorted(row.role for row in artifacts))
            or len({row.role for row in artifacts}) != len(artifacts)
        ):
            raise PoseBustersExternalPreparationError(
                "prepared artifacts must be canonical unique roles"
            )
        center = tuple(
            _validate_hex(value, name="pocket center")
            for value in self.pocket_center_binary64_hex
        )
        if center and len(center) != 3:
            raise PoseBustersExternalPreparationError(
                "pocket center must contain three binary64 values"
            )
        diagnostic_size = _positive_int(
            self.diagnostic_size_bytes,
            name="preparation diagnostic size",
            allow_zero=True,
        )
        attempted = bool(self.preparation_attempted)
        ligand_ok = bool(self.ligand_preparation_succeeded)
        receptor_ok = bool(self.receptor_preparation_succeeded)
        error_fields = (
            self.error_stage,
            self.error_code,
            self.error_type,
            self.error_message_sha256,
        )
        if self.status == "prepared":
            valid = (
                scope_status == _CANDIDATE_SCOPE_STATUS
                and attempted
                and ligand_ok
                and receptor_ok
                and tuple(row.role for row in artifacts) == _ARTIFACT_ROLES
                and len(center) == 3
                and not any(error_fields)
                and not self.failing_residue_keys
                and bool(self.diagnostic_sha256)
            )
        elif self.status == "preparation_failure":
            valid = (
                scope_status == _CANDIDATE_SCOPE_STATUS
                and attempted
                and not receptor_ok
                and not artifacts
                and len(center) == 3
                and all(error_fields)
                and bool(self.diagnostic_sha256)
            )
        elif self.status == "abstain_chemistry_scope":
            valid = (
                scope_status != _CANDIDATE_SCOPE_STATUS
                and not attempted
                and not ligand_ok
                and not receptor_ok
                and not artifacts
                and not center
                and not any(error_fields)
                and not self.failing_residue_keys
                and not self.diagnostic_sha256
                and diagnostic_size == 0
            )
        else:
            valid = (
                not attempted
                and not ligand_ok
                and not receptor_ok
                and not artifacts
                and not center
                and bool(self.error_code)
                and not self.diagnostic_sha256
                and diagnostic_size == 0
            )
        if not valid:
            raise PoseBustersExternalPreparationError(
                "external-preparation case disposition is inconsistent"
            )
        if self.diagnostic_sha256:
            diagnostic_sha = _digest_value(
                self.diagnostic_sha256,
                name="preparation diagnostic",
            )
        else:
            diagnostic_sha = ""
        if self.error_message_sha256:
            error_sha = _digest_value(
                self.error_message_sha256,
                name="preparation error message",
            )
        else:
            error_sha = ""
        error_stage = (
            _token(self.error_stage, name="preparation error stage")
            if self.error_stage
            else ""
        )
        error_code = (
            _token(self.error_code, name="preparation error code")
            if self.error_code
            else ""
        )
        error_type = (
            _identifier(self.error_type, name="preparation error type")
            if self.error_type
            else ""
        )
        object.__setattr__(self, "case_id", case_id)
        object.__setattr__(self, "disposition_code", disposition)
        object.__setattr__(self, "reference_scorer_scope_status", scope_status)
        object.__setattr__(self, "reference_scorer_scope_blockers", scope_blockers)
        object.__setattr__(self, "preparation_attempted", attempted)
        object.__setattr__(self, "ligand_preparation_succeeded", ligand_ok)
        object.__setattr__(self, "receptor_preparation_succeeded", receptor_ok)
        object.__setattr__(self, "artifacts", artifacts)
        object.__setattr__(self, "pocket_center_binary64_hex", center)
        object.__setattr__(self, "error_stage", error_stage)
        object.__setattr__(self, "error_code", error_code)
        object.__setattr__(self, "error_type", error_type)
        object.__setattr__(self, "error_message_sha256", error_sha)
        object.__setattr__(
            self,
            "failing_residue_keys",
            _residue_keys(self.failing_residue_keys),
        )
        object.__setattr__(self, "diagnostic_sha256", diagnostic_sha)
        object.__setattr__(self, "diagnostic_size_bytes", diagnostic_size)

    @property
    def prepared_input_pair_materialized(self) -> bool:
        return self.status == "prepared"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "case_id": self.case_id,
            "status": self.status,
            "disposition_code": self.disposition_code,
            "reference_scorer_scope_status": self.reference_scorer_scope_status,
            "reference_scorer_scope_blockers": list(
                self.reference_scorer_scope_blockers
            ),
            "preparation_attempted": self.preparation_attempted,
            "ligand_preparation_succeeded": self.ligand_preparation_succeeded,
            "receptor_preparation_succeeded": self.receptor_preparation_succeeded,
            "prepared_input_pair_materialized": (
                self.prepared_input_pair_materialized
            ),
            "artifacts": [row.to_dict() for row in self.artifacts],
            "pocket_center_binary64_hex": list(self.pocket_center_binary64_hex),
            "box_size_angstrom": list(PUBLIC_EXTERNAL_BASELINE_BOX_SIZE_ANGSTROM),
            "native_reference_used_for_box_center_only": bool(
                self.preparation_attempted
            ),
            "native_reference_used_for_ligand_preparation": False,
            "ligand_start_conformer_used_for_preparation": bool(
                self.preparation_attempted
            ),
            "strict_bad_residue_deletion_allowed": False,
            "error_stage": self.error_stage,
            "error_code": self.error_code,
            "error_type": self.error_type,
            "error_message_sha256": self.error_message_sha256,
            "failing_residue_keys": list(self.failing_residue_keys),
            "failing_residue_count": len(self.failing_residue_keys),
            "diagnostic_sha256": self.diagnostic_sha256,
            "diagnostic_size_bytes": self.diagnostic_size_bytes,
            "external_engine_executed": False,
            "docking_result_present": False,
        }


@dataclass(frozen=True, slots=True)
class PoseBustersExternalPreparationMetric:
    metric_id: str
    numerator: int
    denominator: int
    estimate: float
    confidence_interval_low: float
    confidence_interval_high: float
    schema_id: str = POSEBUSTERS_EXTERNAL_PREPARATION_METRIC_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_EXTERNAL_PREPARATION_METRIC_SCHEMA_ID:
            raise PoseBustersExternalPreparationError(
                "unsupported external-preparation metric schema"
            )
        metric_id = _token(self.metric_id, name="metric_id")
        numerator = _positive_int(self.numerator, name="numerator", allow_zero=True)
        denominator = _positive_int(self.denominator, name="denominator")
        values = tuple(
            float(value)
            for value in (
                self.estimate,
                self.confidence_interval_low,
                self.confidence_interval_high,
            )
        )
        if (
            numerator > denominator
            or any(not math.isfinite(value) or value < 0.0 or value > 1.0 for value in values)
            or not values[1] <= values[0] <= values[2]
            or not math.isclose(values[0], numerator / denominator, abs_tol=1.0e-15)
        ):
            raise PoseBustersExternalPreparationError(
                "external-preparation metric is inconsistent"
            )
        object.__setattr__(self, "metric_id", metric_id)
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
            "confidence_level": POSEBUSTERS_EXTERNAL_PREPARATION_CONFIDENCE_LEVEL,
            "confidence_interval_method": "wilson_score_binomial",
            "confidence_interval_low": self.confidence_interval_low,
            "confidence_interval_high": self.confidence_interval_high,
        }


def _metric(
    metric_id: str,
    numerator: int,
    denominator: int,
) -> PoseBustersExternalPreparationMetric:
    proportion = numerator / denominator
    z2 = POSEBUSTERS_EXTERNAL_PREPARATION_Z**2
    scale = 1.0 + z2 / denominator
    center = (proportion + z2 / (2.0 * denominator)) / scale
    radius = (
        POSEBUSTERS_EXTERNAL_PREPARATION_Z
        * math.sqrt(
            proportion * (1.0 - proportion) / denominator
            + z2 / (4.0 * denominator**2)
        )
        / scale
    )
    return PoseBustersExternalPreparationMetric(
        metric_id=metric_id,
        numerator=numerator,
        denominator=denominator,
        estimate=proportion,
        confidence_interval_low=min(proportion, max(0.0, center - radius)),
        confidence_interval_high=max(proportion, min(1.0, center + radius)),
    )


def _summary_metrics(
    rows: Sequence[PoseBustersExternalPreparationCase],
) -> tuple[PoseBustersExternalPreparationMetric, ...]:
    predicates: tuple[
        tuple[str, Callable[[PoseBustersExternalPreparationCase], bool]], ...
    ] = (
        (
            "upstream_corpus_ready_rate",
            lambda row: row.status != "upstream_failure",
        ),
        (
            "reference_scorer_chemistry_candidate_rate",
            lambda row: row.reference_scorer_scope_status == _CANDIDATE_SCOPE_STATUS,
        ),
        (
            "chemistry_scope_abstention_rate",
            lambda row: row.status == "abstain_chemistry_scope",
        ),
        (
            "strict_preparation_attempt_rate",
            lambda row: row.preparation_attempted,
        ),
        (
            "strict_ligand_preparation_success_rate",
            lambda row: row.ligand_preparation_succeeded,
        ),
        (
            "strict_receptor_preparation_success_rate",
            lambda row: row.receptor_preparation_succeeded,
        ),
        (
            "prepared_input_pair_materialization_rate",
            lambda row: row.prepared_input_pair_materialized,
        ),
        (
            "strict_preparation_failure_rate",
            lambda row: row.status == "preparation_failure",
        ),
        (
            "external_engine_execution_rate",
            lambda _row: False,
        ),
        (
            "docking_result_rate",
            lambda _row: False,
        ),
    )
    denominator = len(rows)
    return tuple(
        _metric(metric_id, sum(bool(predicate(row)) for row in rows), denominator)
        for metric_id, predicate in predicates
    )


@dataclass(frozen=True, slots=True)
class PoseBustersExternalPreparationReceipt:
    corpus_audit_receipt_sha256: str
    archive_intake_receipt_sha256: str
    archive_contract_sha256: str
    implementation_source_sha256: str
    implementation_source_members: tuple[tuple[str, str], ...]
    runtime_identity: PoseBustersExternalPreparationRuntime
    configuration_sha256: str
    case_rows: tuple[PoseBustersExternalPreparationCase, ...]
    metrics: tuple[PoseBustersExternalPreparationMetric, ...]
    artifact_set_sha256: str
    schema_id: str = POSEBUSTERS_EXTERNAL_PREPARATION_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_EXTERNAL_PREPARATION_SCHEMA_ID:
            raise PoseBustersExternalPreparationError(
                "unsupported external-preparation receipt schema"
            )
        for name in (
            "corpus_audit_receipt_sha256",
            "archive_intake_receipt_sha256",
            "archive_contract_sha256",
            "implementation_source_sha256",
            "configuration_sha256",
            "artifact_set_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _digest_value(getattr(self, name), name=name),
            )
        if self.configuration_sha256 != (
            POSEBUSTERS_EXTERNAL_PREPARATION_CONFIGURATION_SHA256
        ):
            raise PoseBustersExternalPreparationError(
                "external-preparation configuration identity is invalid"
            )
        members = tuple(
            (
                _token(role, name="implementation source role"),
                _digest_value(digest, name=f"{role} implementation source"),
            )
            for role, digest in self.implementation_source_members
        )
        if (
            not members
            or tuple(sorted(members)) != members
            or len({role for role, _digest_sha in members}) != len(members)
            or self.implementation_source_sha256 != _canonical_sha256(dict(members))
        ):
            raise PoseBustersExternalPreparationError(
                "external-preparation implementation identity is inconsistent"
            )
        if not isinstance(
            self.runtime_identity,
            PoseBustersExternalPreparationRuntime,
        ):
            raise PoseBustersExternalPreparationError(
                "external-preparation runtime identity is missing"
            )
        rows = tuple(self.case_rows)
        if (
            not rows
            or tuple(row.case_id for row in rows)
            != tuple(sorted(row.case_id for row in rows))
            or len({row.case_id for row in rows}) != len(rows)
        ):
            raise PoseBustersExternalPreparationError(
                "external-preparation rows must be canonical unique cases"
            )
        expected_metrics = _summary_metrics(rows)
        if tuple(metric.to_dict() for metric in self.metrics) != tuple(
            metric.to_dict() for metric in expected_metrics
        ):
            raise PoseBustersExternalPreparationError(
                "external-preparation metrics do not match all-case rows"
            )
        if self.artifact_set_sha256 != _artifact_set_sha256(rows):
            raise PoseBustersExternalPreparationError(
                "external-preparation artifact-set identity is inconsistent"
            )
        object.__setattr__(self, "implementation_source_members", members)
        object.__setattr__(self, "case_rows", rows)
        object.__setattr__(self, "metrics", expected_metrics)

    @property
    def prepared_case_count(self) -> int:
        return sum(row.prepared_input_pair_materialized for row in self.case_rows)

    @property
    def attempted_case_count(self) -> int:
        return sum(row.preparation_attempted for row in self.case_rows)

    @property
    def failed_case_count(self) -> int:
        return sum(row.status.endswith("failure") for row in self.case_rows)

    @property
    def abstained_case_count(self) -> int:
        return sum(row.status == "abstain_chemistry_scope" for row in self.case_rows)

    def _payload(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "corpus_audit_receipt_sha256": self.corpus_audit_receipt_sha256,
            "archive_intake_receipt_sha256": self.archive_intake_receipt_sha256,
            "archive_contract_sha256": self.archive_contract_sha256,
            "implementation_source_sha256": self.implementation_source_sha256,
            "implementation_source_members": dict(self.implementation_source_members),
            "runtime_identity": self.runtime_identity.to_dict(),
            "runtime_identity_sha256": self.runtime_identity.fingerprint_sha256,
            "configuration": POSEBUSTERS_EXTERNAL_PREPARATION_CONFIGURATION,
            "configuration_sha256": self.configuration_sha256,
            "preparation_contract": {
                "tool": "meeko",
                "ligand_input_role": "ligand_start_conformer_sdf",
                "receptor_input_role": "receptor_pdb",
                "box_center_input_role": "reference_ligand_sdf",
                "box_center_policy": (
                    "centroid_of_native_reference_heavy_atoms_in_raw_receptor_frame"
                ),
                "box_size_angstrom": list(
                    PUBLIC_EXTERNAL_BASELINE_BOX_SIZE_ANGSTROM
                ),
                "receptor_allow_bad_res": False,
                "receptor_delete_residues": [],
                "receptor_set_template": {},
                "receptor_blunt_ends": [],
                "receptor_wanted_altloc": None,
                "receptor_default_altloc": None,
                "receptor_flexible_residues": [],
                "ligand_remove_hydrogens": False,
                "ligand_requires_explicit_hydrogen": True,
                "ligand_bad_charge_ok": False,
                "ligand_add_index_map": False,
                "archive_access": "CRC_checked_member_streaming_without_extraction",
                "artifact_write": "private_mode_0600_no_overwrite",
            },
            "all_case_denominator": len(self.case_rows),
            "attempted_case_count": self.attempted_case_count,
            "prepared_case_count": self.prepared_case_count,
            "failed_case_count": self.failed_case_count,
            "abstained_case_count": self.abstained_case_count,
            "case_rows": [row.to_dict() for row in self.case_rows],
            "metrics": [metric.to_dict() for metric in self.metrics],
            "artifact_set_sha256": self.artifact_set_sha256,
            "archive_extracted": False,
            "strict_bad_residue_deletion_allowed": False,
            "native_reference_used_for_ligand_preparation": False,
            "native_reference_used_for_box_center_only": True,
            "external_engine_executed": False,
            "generated_pose_evaluated": False,
            "posebusters_external_oracle_executed": False,
            "benchmark_executed": False,
            "scientific_blockers": list(
                POSEBUSTERS_EXTERNAL_PREPARATION_BLOCKERS
            ),
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
                raise PoseBustersExternalPreparationError(
                    "PoseBusters external-preparation output already exists"
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


def _artifact_set_sha256(
    rows: Sequence[PoseBustersExternalPreparationCase],
) -> str:
    payload = {
        f"{row.case_id}/{artifact.role}": artifact.to_dict()
        for row in rows
        for artifact in row.artifacts
    }
    return _canonical_sha256(payload)


def _native_heavy_centroid(
    source: bytes,
    *,
    case_id: str,
) -> tuple[str, str, str]:
    try:
        ligand = parse_sdf_v2000(
            source,
            source_id=f"{case_id}:native_box_center",
        )
    except SDFParseError as exc:
        raise PoseBustersExternalPreparationError(
            "native reference failed strict box-center parsing"
        ) from exc
    indices = tuple(
        index
        for index, atom in enumerate(ligand.atoms)
        if atom.atomic_number != 1
    )
    coordinates = ligand.coordinates
    if not indices or tuple(coordinates.shape) != (1, ligand.atom_count, 3):
        raise PoseBustersExternalPreparationError(
            "native reference has no bounded heavy-atom coordinate model"
        )
    center = tuple(
        math.fsum(float(coordinates[0, index, axis].item()) for index in indices)
        / len(indices)
        for axis in range(3)
    )
    return tuple(
        _finite_hex(value, name="native heavy-atom centroid") for value in center
    )  # type: ignore[return-value]


def _source_artifacts(intake_row: Any) -> dict[str, Any]:
    return {artifact.role: artifact for artifact in intake_row.artifacts}


def _prepared_artifact(
    *,
    case_id: str,
    role: str,
    source_artifact: Any,
    payload: bytes,
) -> PoseBustersExternalPreparedArtifact:
    filename = {
        "prepared_ligand_pdbqt": "ligand.pdbqt",
        "prepared_receptor_pdbqt": "receptor.pdbqt",
    }[role]
    return PoseBustersExternalPreparedArtifact(
        role=role,
        relative_path=f"{case_id}/{filename}",
        sha256=_hash_bytes(payload),
        size_bytes=len(payload),
        source_role=source_artifact.role,
        source_sha256=source_artifact.sha256,
    )


def _upstream_failure_row(
    corpus_row: Any,
    *,
    error_code: str,
) -> PoseBustersExternalPreparationCase:
    return PoseBustersExternalPreparationCase(
        case_id=corpus_row.case_id,
        status="upstream_failure",
        disposition_code="upstream_input_contract_failure",
        reference_scorer_scope_status=corpus_row.reference_scorer_scope_status,
        reference_scorer_scope_blockers=corpus_row.reference_scorer_scope_blockers,
        error_code=error_code,
    )


def _prepare_case(
    archive: zipfile.ZipFile,
    intake_row: Any,
    corpus_row: Any,
    runtime: _PreparationRuntimeProtocol,
) -> tuple[PoseBustersExternalPreparationCase, dict[str, bytes]]:
    if corpus_row.status != "audited":
        return _upstream_failure_row(
            corpus_row,
            error_code="upstream_corpus_audit_case_failed",
        ), {}
    if corpus_row.reference_scorer_scope_status != _CANDIDATE_SCOPE_STATUS:
        return PoseBustersExternalPreparationCase(
            case_id=corpus_row.case_id,
            status="abstain_chemistry_scope",
            disposition_code="reference_scorer_chemistry_scope_abstention",
            reference_scorer_scope_status=corpus_row.reference_scorer_scope_status,
            reference_scorer_scope_blockers=(
                corpus_row.reference_scorer_scope_blockers
            ),
        ), {}
    source_artifacts = _source_artifacts(intake_row)
    sources: dict[str, bytes] = {}
    for role in (
        "receptor_pdb",
        "reference_ligand_sdf",
        "ligand_start_conformer_sdf",
    ):
        artifact = source_artifacts.get(role)
        if artifact is None:
            return _upstream_failure_row(
                corpus_row,
                error_code=f"{role}_artifact_identity_missing",
            ), {}
        try:
            sources[role] = _read_member(
                archive,
                artifact.member_path,
                expected_sha256=artifact.sha256,
                expected_size=artifact.size_bytes,
            )
        except PoseBustersCorpusAuditError:
            return _upstream_failure_row(
                corpus_row,
                error_code=f"{role}_artifact_identity_verification_failed",
            ), {}
    try:
        center = _native_heavy_centroid(
            sources["reference_ligand_sdf"],
            case_id=corpus_row.case_id,
        )
    except PoseBustersExternalPreparationError:
        return _upstream_failure_row(
            corpus_row,
            error_code="native_reference_box_center_failed",
        ), {}
    try:
        prepared = runtime.prepare(
            sources["receptor_pdb"],
            sources["ligand_start_conformer_sdf"],
        )
    except PoseBustersExternalPreparationExecutionError as exc:
        return PoseBustersExternalPreparationCase(
            case_id=corpus_row.case_id,
            status="preparation_failure",
            disposition_code=exc.error_code,
            reference_scorer_scope_status=corpus_row.reference_scorer_scope_status,
            reference_scorer_scope_blockers=(
                corpus_row.reference_scorer_scope_blockers
            ),
            preparation_attempted=True,
            ligand_preparation_succeeded=exc.ligand_preparation_succeeded,
            receptor_preparation_succeeded=False,
            pocket_center_binary64_hex=center,
            error_stage=exc.stage,
            error_code=exc.error_code,
            error_type=exc.error_type,
            error_message_sha256=exc.error_message_sha256,
            failing_residue_keys=exc.failing_residue_keys,
            diagnostic_sha256=exc.diagnostic_sha256,
            diagnostic_size_bytes=exc.diagnostic_size_bytes,
        ), {}
    except Exception as exc:
        message = _normalize_error_message(exc)
        empty_diagnostic = _hash_bytes(b"")
        return PoseBustersExternalPreparationCase(
            case_id=corpus_row.case_id,
            status="preparation_failure",
            disposition_code="unclassified_preparation_runtime_failure",
            reference_scorer_scope_status=corpus_row.reference_scorer_scope_status,
            reference_scorer_scope_blockers=(
                corpus_row.reference_scorer_scope_blockers
            ),
            preparation_attempted=True,
            ligand_preparation_succeeded=False,
            receptor_preparation_succeeded=False,
            pocket_center_binary64_hex=center,
            error_stage="runtime",
            error_code="unclassified_preparation_runtime_failure",
            error_type=type(exc).__name__,
            error_message_sha256=_hash_bytes(message),
            diagnostic_sha256=empty_diagnostic,
            diagnostic_size_bytes=0,
        ), {}
    artifacts = tuple(
        sorted(
            (
                _prepared_artifact(
                    case_id=corpus_row.case_id,
                    role="prepared_receptor_pdbqt",
                    source_artifact=source_artifacts["receptor_pdb"],
                    payload=prepared.receptor_pdbqt,
                ),
                _prepared_artifact(
                    case_id=corpus_row.case_id,
                    role="prepared_ligand_pdbqt",
                    source_artifact=source_artifacts[
                        "ligand_start_conformer_sdf"
                    ],
                    payload=prepared.ligand_pdbqt,
                ),
            ),
            key=lambda row: row.role,
        )
    )
    payloads = {
        artifacts[0].relative_path: prepared.ligand_pdbqt,
        artifacts[1].relative_path: prepared.receptor_pdbqt,
    }
    return PoseBustersExternalPreparationCase(
        case_id=corpus_row.case_id,
        status="prepared",
        disposition_code="strict_meeko_prepared_input_pair",
        reference_scorer_scope_status=corpus_row.reference_scorer_scope_status,
        reference_scorer_scope_blockers=corpus_row.reference_scorer_scope_blockers,
        preparation_attempted=True,
        ligand_preparation_succeeded=True,
        receptor_preparation_succeeded=True,
        artifacts=artifacts,
        pocket_center_binary64_hex=center,
        diagnostic_sha256=prepared.diagnostic_sha256,
        diagnostic_size_bytes=prepared.diagnostic_size_bytes,
    ), payloads


def _implementation_source_members(
    corpus: PoseBustersCorpusAuditReceipt,
) -> tuple[tuple[str, str], ...]:
    members = dict(corpus.implementation_source_members)
    members.update(
        {
            "external_preparation": _source_file_sha256(__file__),
            "external_work_order_contract": _source_file_sha256(
                Path(__file__).with_name("public_external_baseline.py")
            ),
        }
    )
    return tuple(sorted(members.items()))


def _write_exact_file(path: Path, source: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as exc:
        raise PoseBustersExternalPreparationError(
            "prepared artifact could not be created without overwrite"
        ) from exc
    try:
        observed = 0
        while observed < len(source):
            written = os.write(descriptor, source[observed:])
            if written < 1:
                raise PoseBustersExternalPreparationError(
                    "prepared artifact write made no progress"
                )
            observed += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_artifact_tree(
    artifact_root: Path,
    payloads: dict[str, bytes],
) -> None:
    artifact_root.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        artifact_root.mkdir(mode=0o700)
    except FileExistsError as exc:
        raise PoseBustersExternalPreparationError(
            "external-preparation artifact root already exists"
        ) from exc
    case_ids = tuple(sorted({PurePosixPath(path).parts[0] for path in payloads}))
    for case_id in case_ids:
        (artifact_root / case_id).mkdir(mode=0o700)
    for relative_path, source in sorted(payloads.items()):
        _write_exact_file(artifact_root / PurePosixPath(relative_path), source)
    for case_id in case_ids:
        descriptor = os.open(
            artifact_root / case_id,
            os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
        )
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    descriptor = os.open(
        artifact_root,
        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _verify_artifact_tree(
    artifact_root: Path,
    payloads: dict[str, bytes],
) -> None:
    try:
        root_metadata = artifact_root.lstat()
    except OSError as exc:
        raise PoseBustersExternalPreparationError(
            "external-preparation artifact root is missing"
        ) from exc
    if (
        not stat.S_ISDIR(root_metadata.st_mode)
        or stat.S_ISLNK(root_metadata.st_mode)
        or stat.S_IMODE(root_metadata.st_mode) != 0o700
    ):
        raise PoseBustersExternalPreparationError(
            "external-preparation artifact root must be a private real directory"
        )
    expected_by_case: dict[str, set[str]] = {}
    for relative_path in payloads:
        parts = PurePosixPath(relative_path).parts
        expected_by_case.setdefault(parts[0], set()).add(parts[1])
    try:
        root_entries = tuple(sorted(os.scandir(artifact_root), key=lambda row: row.name))
    except OSError as exc:
        raise PoseBustersExternalPreparationError(
            "external-preparation artifact root could not be enumerated"
        ) from exc
    if tuple(row.name for row in root_entries) != tuple(sorted(expected_by_case)):
        raise PoseBustersExternalPreparationError(
            "external-preparation artifact root contains missing or extra cases"
        )
    for entry in root_entries:
        if entry.is_symlink() or not entry.is_dir(follow_symlinks=False):
            raise PoseBustersExternalPreparationError(
                "external-preparation case artifact entry is not a real directory"
            )
        case_path = artifact_root / entry.name
        if stat.S_IMODE(case_path.stat(follow_symlinks=False).st_mode) != 0o700:
            raise PoseBustersExternalPreparationError(
                "external-preparation case directory is not private"
            )
        entries = tuple(sorted(os.scandir(case_path), key=lambda row: row.name))
        if tuple(row.name for row in entries) != tuple(
            sorted(expected_by_case[entry.name])
        ):
            raise PoseBustersExternalPreparationError(
                "external-preparation case contains missing or extra artifacts"
            )
        for artifact_entry in entries:
            if artifact_entry.is_symlink() or not artifact_entry.is_file(
                follow_symlinks=False
            ):
                raise PoseBustersExternalPreparationError(
                    "external-preparation artifact is not a real regular file"
                )
            relative_path = f"{entry.name}/{artifact_entry.name}"
            expected = payloads[relative_path]
            observed = _read_exact_regular_file(
                artifact_root / relative_path,
                maximum_bytes=POSEBUSTERS_EXTERNAL_PREPARATION_MAX_ARTIFACT_BYTES,
            )
            mode = stat.S_IMODE(
                (artifact_root / relative_path).stat(follow_symlinks=False).st_mode
            )
            if mode != 0o600 or observed != expected:
                raise PoseBustersExternalPreparationError(
                    "external-preparation artifact does not match exact reexecution"
                )


def _build_preparation(
    archive_path: str | os.PathLike[str],
    selection_path: str | os.PathLike[str],
    intake_receipt_path: str | os.PathLike[str],
    corpus_audit_receipt_path: str | os.PathLike[str],
    *,
    contract: PoseBustersArchiveContract,
) -> tuple[
    PoseBustersExternalPreparationReceipt,
    dict[str, bytes],
]:
    try:
        corpus = verify_posebusters_corpus_audit_receipt(
            corpus_audit_receipt_path,
            archive_path,
            selection_path,
            intake_receipt_path,
            contract=contract,
        )
        intake = verify_posebusters_archive_intake_receipt(
            intake_receipt_path,
            archive_path,
            selection_path,
            contract=contract,
        )
    except (PoseBustersCorpusAuditError, PoseBustersArchiveIntakeError) as exc:
        raise PoseBustersExternalPreparationError(
            "external preparation requires exact verified corpus and intake receipts"
        ) from exc
    if tuple(row.case_id for row in corpus.case_rows) != tuple(
        row.case_id for row in intake.case_rows
    ):
        raise PoseBustersExternalPreparationError(
            "corpus and intake case identities disagree"
        )
    runtime = _load_meeko_runtime()
    if (
        _canonical_sha256(POSEBUSTERS_EXTERNAL_PREPARATION_CONFIGURATION)
        != POSEBUSTERS_EXTERNAL_PREPARATION_CONFIGURATION_SHA256
    ):
        raise PoseBustersExternalPreparationError(
            "external preparation frozen configuration was mutated"
        )
    if runtime.configuration_sha256 != (
        POSEBUSTERS_EXTERNAL_PREPARATION_CONFIGURATION_SHA256
    ):
        raise PoseBustersExternalPreparationError(
            "external preparation runtime configuration is not frozen"
        )
    corpus_rows = {row.case_id: row for row in corpus.case_rows}
    descriptor, size = _regular_file_descriptor(
        archive_path,
        maximum_bytes=contract.archive_size_bytes,
    )
    payloads: dict[str, bytes] = {}
    try:
        if (
            size != contract.archive_size_bytes
            or _hash_descriptor(descriptor, size) != contract.archive_sha256
        ):
            raise PoseBustersExternalPreparationError(
                "external-preparation archive changed after receipt verification"
            )
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            try:
                with zipfile.ZipFile(handle, "r") as archive:
                    rows_list: list[PoseBustersExternalPreparationCase] = []
                    for intake_row in intake.case_rows:
                        row, case_payloads = _prepare_case(
                            archive,
                            intake_row,
                            corpus_rows[intake_row.case_id],
                            runtime,
                        )
                        rows_list.append(row)
                        overlap = set(payloads).intersection(case_payloads)
                        if overlap:
                            raise PoseBustersExternalPreparationError(
                                "external-preparation artifact paths are duplicated"
                            )
                        payloads.update(case_payloads)
                    rows = tuple(rows_list)
            except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
                raise PoseBustersExternalPreparationError(
                    "external preparation failed bounded ZIP access"
                ) from exc
    finally:
        os.close(descriptor)
    source_members = _implementation_source_members(corpus)
    metrics = _summary_metrics(rows)
    receipt = PoseBustersExternalPreparationReceipt(
        corpus_audit_receipt_sha256=corpus.fingerprint_sha256,
        archive_intake_receipt_sha256=intake.fingerprint_sha256,
        archive_contract_sha256=contract.fingerprint_sha256,
        implementation_source_sha256=_canonical_sha256(dict(source_members)),
        implementation_source_members=source_members,
        runtime_identity=runtime.identity,
        configuration_sha256=POSEBUSTERS_EXTERNAL_PREPARATION_CONFIGURATION_SHA256,
        case_rows=rows,
        metrics=metrics,
        artifact_set_sha256=_artifact_set_sha256(rows),
    )
    expected_paths = {
        artifact.relative_path
        for row in rows
        for artifact in row.artifacts
    }
    if set(payloads) != expected_paths:
        raise PoseBustersExternalPreparationError(
            "external-preparation artifact payload set is incomplete"
        )
    return receipt, payloads


def materialize_posebusters_external_preparation(
    archive_path: str | os.PathLike[str],
    selection_path: str | os.PathLike[str],
    intake_receipt_path: str | os.PathLike[str],
    corpus_audit_receipt_path: str | os.PathLike[str],
    artifact_root: str | os.PathLike[str],
    *,
    contract: PoseBustersArchiveContract = OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT,
) -> PoseBustersExternalPreparationReceipt:
    """Prepare strict PDBQT artifacts and retain all 308 case dispositions."""

    receipt, payloads = _build_preparation(
        archive_path,
        selection_path,
        intake_receipt_path,
        corpus_audit_receipt_path,
        contract=contract,
    )
    _write_artifact_tree(Path(artifact_root), payloads)
    return receipt


def verify_posebusters_external_preparation_receipt(
    preparation_receipt_path: str | os.PathLike[str],
    archive_path: str | os.PathLike[str],
    selection_path: str | os.PathLike[str],
    intake_receipt_path: str | os.PathLike[str],
    corpus_audit_receipt_path: str | os.PathLike[str],
    artifact_root: str | os.PathLike[str],
    *,
    contract: PoseBustersArchiveContract = OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT,
) -> PoseBustersExternalPreparationReceipt:
    """Require exact runtime reexecution, receipt bytes, and private artifacts."""

    source = _read_exact_regular_file(
        preparation_receipt_path,
        maximum_bytes=POSEBUSTERS_EXTERNAL_PREPARATION_MAX_RECEIPT_BYTES,
    )
    expected, payloads = _build_preparation(
        archive_path,
        selection_path,
        intake_receipt_path,
        corpus_audit_receipt_path,
        contract=contract,
    )
    _verify_artifact_tree(Path(artifact_root), payloads)
    if source != _canonical_bytes(expected.to_dict()) + b"\n":
        raise PoseBustersExternalPreparationError(
            "PoseBusters external-preparation receipt does not match exact reexecution"
        )
    return expected


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2-posebusters-external-prepare",
        description=(
            "Strictly prepare PoseBusters PDBQT inputs without extraction or docking."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    materialize = subparsers.add_parser("materialize")
    materialize.add_argument("--archive", required=True)
    materialize.add_argument("--selection", required=True)
    materialize.add_argument("--intake-receipt", required=True)
    materialize.add_argument("--corpus-audit-receipt", required=True)
    materialize.add_argument("--artifact-root", required=True)
    materialize.add_argument("--output", required=True)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--archive", required=True)
    verify.add_argument("--selection", required=True)
    verify.add_argument("--intake-receipt", required=True)
    verify.add_argument("--corpus-audit-receipt", required=True)
    verify.add_argument("--artifact-root", required=True)
    verify.add_argument("--preparation-receipt", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "materialize":
        if Path(args.output).exists():
            raise PoseBustersExternalPreparationError(
                "PoseBusters external-preparation output already exists"
            )
        receipt = materialize_posebusters_external_preparation(
            args.archive,
            args.selection,
            args.intake_receipt,
            args.corpus_audit_receipt,
            args.artifact_root,
        )
        receipt.write_json(args.output)
    else:
        receipt = verify_posebusters_external_preparation_receipt(
            args.preparation_receipt,
            args.archive,
            args.selection,
            args.intake_receipt,
            args.corpus_audit_receipt,
            args.artifact_root,
        )
    print(
        json.dumps(
            {
                "receipt_sha256": receipt.fingerprint_sha256,
                "all_case_denominator": len(receipt.case_rows),
                "attempted_case_count": receipt.attempted_case_count,
                "prepared_case_count": receipt.prepared_case_count,
                "failed_case_count": receipt.failed_case_count,
                "abstained_case_count": receipt.abstained_case_count,
                "external_engine_executed": False,
                "benchmark_executed": False,
                "claim_safe": False,
            },
            sort_keys=True,
        )
    )
    return 0


__all__ = [
    "POSEBUSTERS_EXTERNAL_PREPARATION_ARTIFACT_SCHEMA_ID",
    "POSEBUSTERS_EXTERNAL_PREPARATION_BLOCKERS",
    "POSEBUSTERS_EXTERNAL_PREPARATION_CASE_SCHEMA_ID",
    "POSEBUSTERS_EXTERNAL_PREPARATION_CONFIDENCE_LEVEL",
    "POSEBUSTERS_EXTERNAL_PREPARATION_CONFIGURATION",
    "POSEBUSTERS_EXTERNAL_PREPARATION_CONFIGURATION_SHA256",
    "POSEBUSTERS_EXTERNAL_PREPARATION_DEPENDENCY_PINS",
    "POSEBUSTERS_EXTERNAL_PREPARATION_DEPENDENCY_SCHEMA_ID",
    "POSEBUSTERS_EXTERNAL_PREPARATION_MAX_ARTIFACT_BYTES",
    "POSEBUSTERS_EXTERNAL_PREPARATION_MAX_RECEIPT_BYTES",
    "POSEBUSTERS_EXTERNAL_PREPARATION_METRIC_SCHEMA_ID",
    "POSEBUSTERS_EXTERNAL_PREPARATION_RUNTIME_SCHEMA_ID",
    "POSEBUSTERS_EXTERNAL_PREPARATION_SCHEMA_ID",
    "PoseBustersExternalPreparationCase",
    "PoseBustersExternalPreparationDependency",
    "PoseBustersExternalPreparationError",
    "PoseBustersExternalPreparationExecutionError",
    "PoseBustersExternalPreparationMetric",
    "PoseBustersExternalPreparationReceipt",
    "PoseBustersExternalPreparationRuntime",
    "PoseBustersExternalPreparedArtifact",
    "PoseBustersExternalPreparedBytes",
    "main",
    "materialize_posebusters_external_preparation",
    "verify_posebusters_external_preparation_receipt",
]


if __name__ == "__main__":
    raise SystemExit(main())
