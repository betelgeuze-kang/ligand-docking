"""Failure-inclusive charge and atom-type diagnostics for prepared ligands.

This module consumes the exact PoseBusters external-preparation receipt and
its private ligand PDBQT artifacts.  It independently parses the Meeko PDBQT
serialization and directly recomputes the *same* RDKit Gasteiger algorithm
from the embedded SMILES mapping.  The result detects mapping, serialization,
runtime-version, and coarse element/type inconsistencies; it is deliberately
not an independent scientific charge or AutoDock4 typing oracle.

Two observation receipts produced under the frozen RDKit runtimes can be
bound into a cross-version comparison receipt.  Runtime networking is never
used, every one of the 308 preparation rows remains visible, and receipts are
canonical, private, and no-overwrite.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import argparse
import hashlib
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
from typing import Any, Protocol

from .public_posebusters_corpus_audit import (
    _canonical_bytes,
    _canonical_sha256,
    _positive_int,
    _source_file_sha256,
    _token,
)
from .public_posebusters_external_preparation import (
    POSEBUSTERS_EXTERNAL_PREPARATION_MAX_ARTIFACT_BYTES,
    POSEBUSTERS_EXTERNAL_PREPARATION_MAX_DEPENDENCY_BYTES,
    POSEBUSTERS_EXTERNAL_PREPARATION_MAX_DEPENDENCY_FILE_BYTES,
    POSEBUSTERS_EXTERNAL_PREPARATION_MAX_DEPENDENCY_FILES,
    _hash_regular_file,
)
from .public_posebusters_intake import _read_exact_regular_file
from .public_posebusters_vina_execution import (
    PoseBustersVinaExecutionError,
    _PreparedCaseView,
    _case_id,
    _digest,
    _load_preparation_receipt,
    _validate_hex,
)


POSEBUSTERS_PREPARED_LIGAND_RUNTIME_PAYLOAD_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_prepared_ligand_runtime_payload/1.0.0"
)
POSEBUSTERS_PREPARED_LIGAND_RUNTIME_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_prepared_ligand_runtime/1.0.0"
)
POSEBUSTERS_PREPARED_LIGAND_ATOM_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_prepared_ligand_atom/1.0.0"
)
POSEBUSTERS_PREPARED_LIGAND_CASE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_prepared_ligand_case/1.0.0"
)
POSEBUSTERS_PREPARED_LIGAND_METRIC_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_prepared_ligand_metric/1.0.0"
)
POSEBUSTERS_PREPARED_LIGAND_OBSERVATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_prepared_ligand_observation/1.0.0"
)
POSEBUSTERS_PREPARED_LIGAND_COMPARISON_CASE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_prepared_ligand_comparison_case/1.0.0"
)
POSEBUSTERS_PREPARED_LIGAND_COMPARISON_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_prepared_ligand_comparison/1.0.0"
)

POSEBUSTERS_PREPARED_LIGAND_MAX_RECEIPT_BYTES = 16 * 1024 * 1024
POSEBUSTERS_PREPARED_LIGAND_MAX_ATOMS_PER_CASE = 10_000
POSEBUSTERS_PREPARED_LIGAND_CONFIDENCE_LEVEL = 0.95
POSEBUSTERS_PREPARED_LIGAND_Z = 1.959963984540054
POSEBUSTERS_PREPARED_LIGAND_SUPPORTED_RDKIT_VERSIONS = (
    "2022.09.5",
    "2025.09.6",
)
_RDKIT_DISTRIBUTION_VERSIONS = {
    "2022.09.5": frozenset({"2022.9.5"}),
    "2025.09.6": frozenset({"2025.9.6"}),
}
POSEBUSTERS_PREPARED_LIGAND_CHARGE_TOLERANCE = 0.0005

POSEBUSTERS_PREPARED_LIGAND_CONFIGURATION = {
    "aromatic_carbon_type_policy": {
        "aromatic": ["A"],
        "non_aromatic": ["C", "CG0"],
    },
    "charge_algorithm": "rdkit_compute_gasteiger_charges",
    "charge_iteration_count": 12,
    "charge_parameter_failure_raises": False,
    "charge_serialization_decimal_places": 3,
    "charge_serialization_tolerance_e": (POSEBUSTERS_PREPARED_LIGAND_CHARGE_TOLERANCE),
    "embedded_mapping_sources": ["REMARK_SMILES_IDX", "REMARK_H_PARENT"],
    "hydrogen_merge_policy": "merge_omitted_hydrogen_charge_into_parent",
    "pdbqt_atom_record_types": ["ATOM", "HETATM"],
    "pseudoatom_policy": "unmapped_G0_only_with_exact_zero_charge",
    "supported_rdkit_versions": list(
        POSEBUSTERS_PREPARED_LIGAND_SUPPORTED_RDKIT_VERSIONS
    ),
    "supported_rdkit_distribution_versions": {
        version: sorted(distribution_versions)
        for version, distribution_versions in sorted(
            _RDKIT_DISTRIBUTION_VERSIONS.items()
        )
    },
    "type_check_scope": "element_compatibility_and_aromatic_carbon_only",
}
POSEBUSTERS_PREPARED_LIGAND_CONFIGURATION_SHA256 = _canonical_sha256(
    POSEBUSTERS_PREPARED_LIGAND_CONFIGURATION
)

POSEBUSTERS_PREPARED_LIGAND_SCIENTIFIC_BLOCKERS = (
    "same_gasteiger_algorithm_recomputation_is_not_an_independent_charge_oracle",
    "embedded_smiles_to_source_sdf_chemistry_equivalence_not_independently_verified",
    "ad4_atom_type_semantics_not_independently_recomputed",
    "receptor_partial_charges_and_atom_types_not_audited",
    "transitive_system_native_libraries_not_individually_fingerprinted",
    "prepared_subset_is_not_representative_of_the_308_case_public_corpus",
    "unsupported_metals_cofactors_and_chemistry_remain_abstentions",
    "independent_external_charge_and_type_implementation_missing",
    "second_cpu_host_reproduction_missing",
    "independent_scientific_review_missing",
)

_DEPENDENCY_METADATA_EXCLUSIONS = {
    "direct_url.json",
    "INSTALLER",
    "RECORD",
    "REQUESTED",
}
_ATOM_TYPE_BY_ATOMIC_NUMBER = {
    1: frozenset({"H", "HD"}),
    6: frozenset({"A", "C", "CG0"}),
    7: frozenset({"N", "NA"}),
    8: frozenset({"O", "OA"}),
    9: frozenset({"F"}),
    15: frozenset({"P"}),
    16: frozenset({"S", "SA"}),
    17: frozenset({"Cl"}),
    35: frozenset({"Br"}),
    53: frozenset({"I"}),
}
_CASE_STATUSES = {
    "abstain_chemistry_scope",
    "blocked_preparation_failure",
    "blocked_upstream_failure",
    "diagnostic_failure",
    "evaluated",
}
_ATOM_ROLES = {
    "macrocycle_closure_pseudoatom",
    "retained_polar_hydrogen",
    "source_atom",
}
_COMPARISON_STATUSES = {
    "abstain_chemistry_scope",
    "blocked_preparation_failure",
    "blocked_upstream_failure",
    "comparable",
    "not_comparable_diagnostic_failure",
    "not_comparable_mapping_difference",
}
_DECIMAL_CHARGE_PATTERN = re.compile(r"-?[0-9]+\.[0-9]{3}\Z")
_ATOM_TYPE_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9]{0,7}\Z")


class PoseBustersPreparedLigandDiagnosticError(ValueError):
    """Prepared-ligand diagnostic input, runtime, or receipt is invalid."""


def _hash_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _finite_hex(value: float, *, name: str) -> str:
    number = float(value)
    if not math.isfinite(number):
        raise PoseBustersPreparedLigandDiagnosticError(f"{name} must be finite")
    return number.hex()


def _bounded_ascii(value: object, *, name: str, maximum: int = 512) -> str:
    if not isinstance(value, str):
        raise PoseBustersPreparedLigandDiagnosticError(f"{name} must be text")
    result = value.strip()
    if (
        not result
        or len(result) > maximum
        or not result.isascii()
        or any(ord(character) < 32 or ord(character) > 126 for character in result)
    ):
        raise PoseBustersPreparedLigandDiagnosticError(
            f"{name} must be bounded printable ASCII"
        )
    return result


def _identifier(value: object, *, name: str) -> str:
    result = _bounded_ascii(value, name=name, maximum=128)
    if not (result[0].isalpha() or result[0] == "_") or any(
        not (character.isalnum() or character == "_") for character in result
    ):
        raise PoseBustersPreparedLigandDiagnosticError(f"{name} must be an identifier")
    return result


def _utc_timestamp(value: object) -> str:
    text = _bounded_ascii(value, name="observation UTC", maximum=40)
    if not text.endswith("Z"):
        raise PoseBustersPreparedLigandDiagnosticError("observation UTC must end in Z")
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as exc:
        raise PoseBustersPreparedLigandDiagnosticError(
            "observation UTC is invalid"
        ) from exc
    if parsed.tzinfo != timezone.utc:
        raise PoseBustersPreparedLigandDiagnosticError("observation UTC must use UTC")
    return parsed.isoformat(timespec="seconds").replace("+00:00", "Z")


def _normalized_error(error: BaseException) -> bytes:
    text = " ".join(str(error).split())
    if not text:
        text = type(error).__name__
    return text[:4096].encode("utf-8", errors="backslashreplace")


def _atomic_write_new(
    output_path: str | os.PathLike[str],
    payload: Mapping[str, Any],
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    source = _canonical_bytes(dict(payload)) + b"\n"
    if len(source) > POSEBUSTERS_PREPARED_LIGAND_MAX_RECEIPT_BYTES:
        raise PoseBustersPreparedLigandDiagnosticError(
            "prepared-ligand receipt exceeds its size bound"
        )
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.",
        suffix=".tmp",
        dir=str(output.parent),
    )
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(source)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary_name, output, follow_symlinks=False)
        except FileExistsError as exc:
            raise PoseBustersPreparedLigandDiagnosticError(
                "prepared-ligand receipt output already exists"
            ) from exc
    finally:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
    return output


def _wilson_interval(successes: int, total: int) -> tuple[str, str]:
    successes = _positive_int(successes, name="metric numerator", allow_zero=True)
    total = _positive_int(total, name="metric denominator")
    if successes > total:
        raise PoseBustersPreparedLigandDiagnosticError(
            "metric numerator exceeds denominator"
        )
    fraction = successes / total
    z2 = POSEBUSTERS_PREPARED_LIGAND_Z**2
    denominator = 1.0 + z2 / total
    center = (fraction + z2 / (2.0 * total)) / denominator
    margin = (
        POSEBUSTERS_PREPARED_LIGAND_Z
        * math.sqrt(fraction * (1.0 - fraction) / total + z2 / (4.0 * total**2))
        / denominator
    )
    return max(0.0, center - margin).hex(), min(1.0, center + margin).hex()


@dataclass(frozen=True, slots=True)
class PoseBustersPreparedLigandRuntimePayload:
    distribution_name: str
    distribution_version: str
    payload_sha256: str
    payload_file_count: int
    payload_size_bytes: int
    schema_id: str = POSEBUSTERS_PREPARED_LIGAND_RUNTIME_PAYLOAD_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_PREPARED_LIGAND_RUNTIME_PAYLOAD_SCHEMA_ID:
            raise PoseBustersPreparedLigandDiagnosticError(
                "unsupported prepared-ligand runtime-payload schema"
            )
        object.__setattr__(
            self,
            "distribution_name",
            _bounded_ascii(
                self.distribution_name,
                name="RDKit distribution name",
                maximum=128,
            ),
        )
        object.__setattr__(
            self,
            "distribution_version",
            _bounded_ascii(
                self.distribution_version,
                name="RDKit distribution version",
                maximum=128,
            ),
        )
        object.__setattr__(
            self,
            "payload_sha256",
            _digest(self.payload_sha256, name="RDKit distribution payload"),
        )
        object.__setattr__(
            self,
            "payload_file_count",
            _positive_int(self.payload_file_count, name="RDKit payload file count"),
        )
        object.__setattr__(
            self,
            "payload_size_bytes",
            _positive_int(self.payload_size_bytes, name="RDKit payload size"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "distribution_name": self.distribution_name,
            "distribution_version": self.distribution_version,
            "payload_sha256": self.payload_sha256,
            "payload_file_count": self.payload_file_count,
            "payload_size_bytes": self.payload_size_bytes,
            "payload_policy": (
                "distribution_regular_files_no_parent_paths_no_pyc_"
                "no_mutable_install_metadata"
            ),
        }


@dataclass(frozen=True, slots=True)
class PoseBustersPreparedLigandRuntimeIdentity:
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
    rdkit_version: str
    rdkit_build: str
    boost_version: str
    rdkit_payload: PoseBustersPreparedLigandRuntimePayload
    schema_id: str = POSEBUSTERS_PREPARED_LIGAND_RUNTIME_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_PREPARED_LIGAND_RUNTIME_SCHEMA_ID:
            raise PoseBustersPreparedLigandDiagnosticError(
                "unsupported prepared-ligand runtime schema"
            )
        for field_name in (
            "python_implementation",
            "python_version",
            "python_cache_tag",
            "platform_system",
            "platform_machine",
            "filesystem_encoding",
            "rdkit_build",
            "boost_version",
        ):
            object.__setattr__(
                self,
                field_name,
                _bounded_ascii(
                    getattr(self, field_name),
                    name=field_name.replace("_", " "),
                    maximum=512,
                ),
            )
        for field_name in ("libc_name", "libc_version"):
            value = str(getattr(self, field_name)).strip()
            if len(value) > 128 or not value.isascii():
                raise PoseBustersPreparedLigandDiagnosticError(
                    f"{field_name} must be bounded ASCII"
                )
            object.__setattr__(self, field_name, value)
        version = _bounded_ascii(
            self.rdkit_version,
            name="RDKit version",
            maximum=128,
        )
        if version not in POSEBUSTERS_PREPARED_LIGAND_SUPPORTED_RDKIT_VERSIONS:
            raise PoseBustersPreparedLigandDiagnosticError(
                "RDKit version is outside the frozen diagnostic runtimes"
            )
        object.__setattr__(self, "rdkit_version", version)
        object.__setattr__(
            self,
            "python_executable_sha256",
            _digest(self.python_executable_sha256, name="Python executable"),
        )
        object.__setattr__(
            self,
            "python_executable_size_bytes",
            _positive_int(
                self.python_executable_size_bytes,
                name="Python executable size",
            ),
        )
        if (
            not isinstance(
                self.rdkit_payload,
                PoseBustersPreparedLigandRuntimePayload,
            )
            or self.rdkit_payload.distribution_version
            not in _RDKIT_DISTRIBUTION_VERSIONS[version]
        ):
            raise PoseBustersPreparedLigandDiagnosticError(
                "RDKit payload does not match its runtime version"
            )

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
            "rdkit_version": self.rdkit_version,
            "rdkit_build": self.rdkit_build,
            "boost_version": self.boost_version,
            "rdkit_payload": self.rdkit_payload.to_dict(),
            "transitive_system_native_libraries_individually_fingerprinted": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class _SourceAtomCharge:
    source_index: int
    atomic_number: int
    element_symbol: str
    aromatic: bool
    charge: float
    hydrogen_charges: tuple[float, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "source_index",
            _positive_int(self.source_index, name="source atom index"),
        )
        atomic_number = _positive_int(self.atomic_number, name="atomic number")
        if atomic_number > 118 or atomic_number == 1:
            raise PoseBustersPreparedLigandDiagnosticError(
                "embedded SMILES source atoms must be non-hydrogen elements"
            )
        object.__setattr__(self, "atomic_number", atomic_number)
        object.__setattr__(
            self,
            "element_symbol",
            _bounded_ascii(self.element_symbol, name="element symbol", maximum=3),
        )
        object.__setattr__(self, "aromatic", bool(self.aromatic))
        if not math.isfinite(float(self.charge)):
            raise PoseBustersPreparedLigandDiagnosticError(
                "source atom charge must be finite"
            )
        object.__setattr__(self, "charge", float(self.charge))
        hydrogens = tuple(float(value) for value in self.hydrogen_charges)
        if len(hydrogens) > 16 or any(not math.isfinite(value) for value in hydrogens):
            raise PoseBustersPreparedLigandDiagnosticError(
                "source hydrogen charges are invalid"
            )
        object.__setattr__(self, "hydrogen_charges", hydrogens)


class _ChargeRuntimeProtocol(Protocol):
    identity: PoseBustersPreparedLigandRuntimeIdentity

    def compute_source_atoms(self, smiles: str) -> tuple[_SourceAtomCharge, ...]: ...


def _distribution_payload(
    distribution: importlib.metadata.Distribution,
) -> PoseBustersPreparedLigandRuntimePayload:
    distribution_name = distribution.metadata.get("Name")
    if not isinstance(distribution_name, str) or not distribution_name:
        raise PoseBustersPreparedLigandDiagnosticError(
            "RDKit distribution name is unavailable"
        )
    files = distribution.files
    if files is None:
        raise PoseBustersPreparedLigandDiagnosticError(
            "RDKit distribution file inventory is unavailable"
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
            raise PoseBustersPreparedLigandDiagnosticError(
                "RDKit distribution payload file is missing"
            ) from exc
        if not stat.S_ISREG(metadata.st_mode):
            raise PoseBustersPreparedLigandDiagnosticError(
                "RDKit distribution contains a non-regular payload file"
            )
        digest, size, mode = _hash_regular_file(
            path,
            maximum_bytes=(POSEBUSTERS_EXTERNAL_PREPARATION_MAX_DEPENDENCY_FILE_BYTES),
        )
        key = relative.as_posix()
        if key in payload:
            raise PoseBustersPreparedLigandDiagnosticError(
                "RDKit distribution contains a duplicate payload path"
            )
        payload[key] = {
            "mode": mode,
            "sha256": digest,
            "size_bytes": size,
        }
        total_size += size
        if (
            len(payload) > POSEBUSTERS_EXTERNAL_PREPARATION_MAX_DEPENDENCY_FILES
            or total_size > POSEBUSTERS_EXTERNAL_PREPARATION_MAX_DEPENDENCY_BYTES
        ):
            raise PoseBustersPreparedLigandDiagnosticError(
                "RDKit distribution payload exceeds its bounds"
            )
    if not payload or total_size < 1:
        raise PoseBustersPreparedLigandDiagnosticError(
            "RDKit distribution payload is empty"
        )
    return PoseBustersPreparedLigandRuntimePayload(
        distribution_name=distribution_name,
        distribution_version=distribution.version,
        payload_sha256=_canonical_sha256(payload),
        payload_file_count=len(payload),
        payload_size_bytes=total_size,
    )


def _rdkit_distribution(
    rdkit_module: Any, version: str
) -> importlib.metadata.Distribution:
    module_file = getattr(rdkit_module, "__file__", None)
    if not isinstance(module_file, str) or not module_file:
        raise PoseBustersPreparedLigandDiagnosticError(
            "RDKit module file identity is unavailable"
        )
    try:
        observed = Path(module_file).resolve(strict=True)
    except OSError as exc:
        raise PoseBustersPreparedLigandDiagnosticError(
            "RDKit module file cannot be resolved"
        ) from exc
    candidates: list[importlib.metadata.Distribution] = []
    for name in ("rdkit", "rdkit-pypi"):
        try:
            distribution = importlib.metadata.distribution(name)
        except importlib.metadata.PackageNotFoundError:
            continue
        if distribution.version in _RDKIT_DISTRIBUTION_VERSIONS[version]:
            candidates.append(distribution)
    for distribution in candidates:
        files = distribution.files or ()
        for package_path in files:
            relative = PurePosixPath(str(package_path))
            if relative.is_absolute() or ".." in relative.parts:
                continue
            try:
                candidate = Path(distribution.locate_file(package_path)).resolve(
                    strict=True
                )
            except OSError:
                continue
            if candidate == observed:
                return distribution
    raise PoseBustersPreparedLigandDiagnosticError(
        "RDKit import is not owned by a supported distribution inventory"
    )


class _RdkitChargeRuntime:
    def __init__(self) -> None:
        try:
            import rdkit
            from rdkit import Chem, rdBase
            from rdkit.Chem import rdPartialCharges
        except ImportError as exc:
            raise PoseBustersPreparedLigandDiagnosticError(
                "prepared-ligand diagnostics require a frozen optional RDKit runtime"
            ) from exc
        version = str(rdBase.rdkitVersion)
        if version not in POSEBUSTERS_PREPARED_LIGAND_SUPPORTED_RDKIT_VERSIONS:
            raise PoseBustersPreparedLigandDiagnosticError(
                "RDKit version is outside the frozen diagnostic runtimes"
            )
        distribution = _rdkit_distribution(rdkit, version)
        payload = _distribution_payload(distribution)
        executable = Path(sys.executable).resolve(strict=True)
        executable_sha256, executable_size, _mode = _hash_regular_file(
            executable,
            maximum_bytes=(POSEBUSTERS_EXTERNAL_PREPARATION_MAX_DEPENDENCY_FILE_BYTES),
        )
        cache_tag = getattr(sys.implementation, "cache_tag", None)
        if not isinstance(cache_tag, str) or not cache_tag:
            raise PoseBustersPreparedLigandDiagnosticError(
                "Python runtime does not expose a cache tag"
            )
        libc_name, libc_version = platform.libc_ver()
        self.identity = PoseBustersPreparedLigandRuntimeIdentity(
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
            rdkit_version=version,
            rdkit_build=str(rdBase.rdkitBuild),
            boost_version=str(rdBase.boostVersion),
            rdkit_payload=payload,
        )
        self._Chem = Chem
        self._rdPartialCharges = rdPartialCharges

    def compute_source_atoms(self, smiles: str) -> tuple[_SourceAtomCharge, ...]:
        molecule = self._Chem.MolFromSmiles(smiles)
        if molecule is None:
            raise PoseBustersPreparedLigandDiagnosticError(
                "embedded SMILES failed strict RDKit parsing"
            )
        if molecule.GetNumAtoms() < 1 or any(
            atom.GetAtomicNum() == 1 for atom in molecule.GetAtoms()
        ):
            raise PoseBustersPreparedLigandDiagnosticError(
                "embedded SMILES must contain only implicit or bracket hydrogens"
            )
        molecule = self._Chem.AddHs(molecule)
        self._rdPartialCharges.ComputeGasteigerCharges(molecule, 12, False)
        rows: list[_SourceAtomCharge] = []
        source_count = sum(atom.GetAtomicNum() != 1 for atom in molecule.GetAtoms())
        for source_index in range(source_count):
            atom = molecule.GetAtomWithIdx(source_index)
            if atom.GetAtomicNum() == 1:
                raise PoseBustersPreparedLigandDiagnosticError(
                    "RDKit hydrogen expansion changed source atom ordering"
                )
            try:
                charge = atom.GetDoubleProp("_GasteigerCharge")
                hydrogen_charges = tuple(
                    neighbor.GetDoubleProp("_GasteigerCharge")
                    for neighbor in sorted(
                        (
                            candidate
                            for candidate in atom.GetNeighbors()
                            if candidate.GetAtomicNum() == 1
                        ),
                        key=lambda candidate: candidate.GetIdx(),
                    )
                )
            except (KeyError, RuntimeError) as exc:
                raise PoseBustersPreparedLigandDiagnosticError(
                    "RDKit Gasteiger charge property is unavailable"
                ) from exc
            rows.append(
                _SourceAtomCharge(
                    source_index=source_index + 1,
                    atomic_number=atom.GetAtomicNum(),
                    element_symbol=atom.GetSymbol(),
                    aromatic=atom.GetIsAromatic(),
                    charge=charge,
                    hydrogen_charges=hydrogen_charges,
                )
            )
        return tuple(rows)


def _load_rdkit_runtime() -> _ChargeRuntimeProtocol:
    return _RdkitChargeRuntime()


@dataclass(frozen=True, slots=True)
class _PdbqtAtom:
    serial: int
    atom_name: str
    observed_charge_token: str
    observed_charge: float
    atom_type: str


@dataclass(frozen=True, slots=True)
class _ParsedLigand:
    smiles: str
    smiles_sha256: str
    source_to_serial: tuple[tuple[int, int], ...]
    parent_to_hydrogen_serial: tuple[tuple[int, int], ...]
    atoms: tuple[_PdbqtAtom, ...]


def _parse_index_pairs(
    tokens: Sequence[str], *, name: str
) -> tuple[tuple[int, int], ...]:
    if not tokens or len(tokens) % 2:
        raise PoseBustersPreparedLigandDiagnosticError(
            f"{name} must contain positive integer pairs"
        )
    values: list[int] = []
    for token in tokens:
        if not token.isascii() or not token.isdigit():
            raise PoseBustersPreparedLigandDiagnosticError(
                f"{name} must contain decimal integers"
            )
        values.append(_positive_int(int(token), name=name))
    return tuple(zip(values[0::2], values[1::2], strict=True))


def _parse_ligand_pdbqt(payload: bytes) -> _ParsedLigand:
    if (
        not isinstance(payload, bytes)
        or not payload
        or len(payload) > POSEBUSTERS_EXTERNAL_PREPARATION_MAX_ARTIFACT_BYTES
        or b"\x00" in payload
        or not payload.endswith(b"\n")
        or b"\r" in payload
    ):
        raise PoseBustersPreparedLigandDiagnosticError(
            "prepared ligand PDBQT bytes are invalid"
        )
    try:
        lines = payload.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise PoseBustersPreparedLigandDiagnosticError(
            "prepared ligand PDBQT must be ASCII"
        ) from exc
    smiles_rows: list[str] = []
    source_to_serial: list[tuple[int, int]] = []
    parent_to_hydrogen: list[tuple[int, int]] = []
    atoms: list[_PdbqtAtom] = []
    for line in lines:
        if line.startswith("REMARK SMILES IDX "):
            source_to_serial.extend(
                _parse_index_pairs(
                    line[len("REMARK SMILES IDX ") :].split(),
                    name="SMILES IDX mapping",
                )
            )
        elif line.startswith("REMARK H PARENT "):
            parent_to_hydrogen.extend(
                _parse_index_pairs(
                    line[len("REMARK H PARENT ") :].split(),
                    name="H PARENT mapping",
                )
            )
        elif line.startswith("REMARK SMILES "):
            smiles_rows.append(
                _bounded_ascii(
                    line[len("REMARK SMILES ") :],
                    name="embedded SMILES",
                    maximum=16_384,
                )
            )
        elif line.startswith(("ATOM  ", "HETATM")):
            if len(line) < 78:
                raise PoseBustersPreparedLigandDiagnosticError(
                    "PDBQT atom record is truncated"
                )
            try:
                serial = int(line[6:11])
                observed_charge_token = line[70:76].strip()
                observed_charge = float(observed_charge_token)
            except ValueError as exc:
                raise PoseBustersPreparedLigandDiagnosticError(
                    "PDBQT atom serial or charge is invalid"
                ) from exc
            serial = _positive_int(serial, name="PDBQT atom serial")
            if not _DECIMAL_CHARGE_PATTERN.fullmatch(
                observed_charge_token
            ) or not math.isfinite(observed_charge):
                raise PoseBustersPreparedLigandDiagnosticError(
                    "PDBQT charge must be finite three-decimal text"
                )
            atom_type = line[77:].strip()
            if not _ATOM_TYPE_PATTERN.fullmatch(atom_type):
                raise PoseBustersPreparedLigandDiagnosticError(
                    "PDBQT AutoDock4 atom type is invalid"
                )
            atom_name = _bounded_ascii(
                line[12:16],
                name="PDBQT atom name",
                maximum=4,
            )
            atoms.append(
                _PdbqtAtom(
                    serial=serial,
                    atom_name=atom_name,
                    observed_charge_token=observed_charge_token,
                    observed_charge=observed_charge,
                    atom_type=atom_type,
                )
            )
    if len(smiles_rows) != 1:
        raise PoseBustersPreparedLigandDiagnosticError(
            "prepared ligand PDBQT must contain exactly one embedded SMILES"
        )
    atoms_tuple = tuple(atoms)
    if (
        not atoms_tuple
        or len(atoms_tuple) > POSEBUSTERS_PREPARED_LIGAND_MAX_ATOMS_PER_CASE
        or tuple(atom.serial for atom in atoms_tuple)
        != tuple(range(1, len(atoms_tuple) + 1))
    ):
        raise PoseBustersPreparedLigandDiagnosticError(
            "PDBQT atom serials must be bounded contiguous order"
        )
    source_tuple = tuple(source_to_serial)
    hydrogen_tuple = tuple(parent_to_hydrogen)
    mapped_serials = tuple(
        serial for _source, serial in (*source_tuple, *hydrogen_tuple)
    )
    if (
        not source_tuple
        or len({source for source, _serial in source_tuple}) != len(source_tuple)
        or len(set(mapped_serials)) != len(mapped_serials)
        or any(serial > len(atoms_tuple) for serial in mapped_serials)
    ):
        raise PoseBustersPreparedLigandDiagnosticError(
            "embedded PDBQT atom mappings are duplicated or out of range"
        )
    unmapped = set(range(1, len(atoms_tuple) + 1)).difference(mapped_serials)
    if any(atoms_tuple[serial - 1].atom_type != "G0" for serial in unmapped):
        raise PoseBustersPreparedLigandDiagnosticError(
            "only G0 macrocycle pseudoatoms may remain unmapped"
        )
    if any(atoms_tuple[serial - 1].atom_type == "G0" for serial in mapped_serials):
        raise PoseBustersPreparedLigandDiagnosticError(
            "G0 macrocycle pseudoatoms must not map to source chemistry"
        )
    smiles = smiles_rows[0]
    return _ParsedLigand(
        smiles=smiles,
        smiles_sha256=_hash_bytes(smiles.encode("ascii")),
        source_to_serial=source_tuple,
        parent_to_hydrogen_serial=hydrogen_tuple,
        atoms=atoms_tuple,
    )


@dataclass(frozen=True, slots=True)
class PoseBustersPreparedLigandAtom:
    pdbqt_serial: int
    pdbqt_atom_name: str
    role: str
    source_smiles_atom_index: int | None
    source_parent_smiles_atom_index: int | None
    atomic_number: int
    element_symbol: str
    aromatic: bool | None
    autodock4_atom_type: str
    observed_charge_token: str
    observed_charge_binary64_hex: str
    expected_gasteiger_charge_binary64_hex: str | None
    absolute_charge_delta_binary64_hex: str | None
    charge_serialization_tolerance_pass: bool | None
    element_type_compatible: bool
    aromatic_carbon_type_compatible: bool | None
    pseudoatom_zero_charge_pass: bool | None
    schema_id: str = POSEBUSTERS_PREPARED_LIGAND_ATOM_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_PREPARED_LIGAND_ATOM_SCHEMA_ID:
            raise PoseBustersPreparedLigandDiagnosticError(
                "unsupported prepared-ligand atom schema"
            )
        serial = _positive_int(self.pdbqt_serial, name="PDBQT atom serial")
        role = str(self.role)
        if role not in _ATOM_ROLES:
            raise PoseBustersPreparedLigandDiagnosticError(
                "prepared-ligand atom role is invalid"
            )
        atom_name = _bounded_ascii(
            self.pdbqt_atom_name,
            name="PDBQT atom name",
            maximum=4,
        )
        atom_type = _bounded_ascii(
            self.autodock4_atom_type,
            name="AutoDock4 atom type",
            maximum=8,
        )
        if not _ATOM_TYPE_PATTERN.fullmatch(atom_type):
            raise PoseBustersPreparedLigandDiagnosticError(
                "AutoDock4 atom type is invalid"
            )
        token = _bounded_ascii(
            self.observed_charge_token,
            name="observed charge token",
            maximum=16,
        )
        if not _DECIMAL_CHARGE_PATTERN.fullmatch(token):
            raise PoseBustersPreparedLigandDiagnosticError(
                "observed charge token is not three-decimal text"
            )
        observed = _validate_hex(
            self.observed_charge_binary64_hex,
            name="observed PDBQT charge",
        )
        source_index = self.source_smiles_atom_index
        parent_index = self.source_parent_smiles_atom_index
        if source_index is not None:
            source_index = _positive_int(source_index, name="source SMILES atom index")
        if parent_index is not None:
            parent_index = _positive_int(
                parent_index,
                name="source parent SMILES atom index",
            )
        atomic_number = _positive_int(
            self.atomic_number,
            name="diagnostic atomic number",
            allow_zero=True,
        )
        if atomic_number > 118:
            raise PoseBustersPreparedLigandDiagnosticError(
                "diagnostic atomic number exceeds 118"
            )
        element = _bounded_ascii(
            self.element_symbol,
            name="diagnostic element symbol",
            maximum=3,
        )
        expected = self.expected_gasteiger_charge_binary64_hex
        delta = self.absolute_charge_delta_binary64_hex
        if expected is not None:
            expected = _validate_hex(expected, name="expected Gasteiger charge")
        if delta is not None:
            delta = _validate_hex(delta, name="absolute charge delta")
            if float.fromhex(delta) < 0.0:
                raise PoseBustersPreparedLigandDiagnosticError(
                    "absolute charge delta must be non-negative"
                )
        aromatic = self.aromatic
        if aromatic is not None:
            aromatic = bool(aromatic)
        charge_pass = self.charge_serialization_tolerance_pass
        if charge_pass is not None:
            charge_pass = bool(charge_pass)
        aromatic_pass = self.aromatic_carbon_type_compatible
        if aromatic_pass is not None:
            aromatic_pass = bool(aromatic_pass)
        pseudo_pass = self.pseudoatom_zero_charge_pass
        if pseudo_pass is not None:
            pseudo_pass = bool(pseudo_pass)
        if role == "source_atom":
            valid = (
                source_index is not None
                and parent_index is None
                and 1 < atomic_number <= 118
                and aromatic is not None
                and expected is not None
                and delta is not None
                and charge_pass is not None
                and pseudo_pass is None
                and (
                    (atomic_number == 6 and aromatic_pass is not None)
                    or (atomic_number != 6 and aromatic_pass is None)
                )
            )
        elif role == "retained_polar_hydrogen":
            valid = (
                source_index is None
                and parent_index is not None
                and atomic_number == 1
                and element == "H"
                and aromatic is None
                and expected is not None
                and delta is not None
                and charge_pass is not None
                and aromatic_pass is None
                and pseudo_pass is None
            )
        else:
            valid = (
                source_index is None
                and parent_index is None
                and atomic_number == 0
                and element == "G"
                and aromatic is None
                and atom_type == "G0"
                and expected is None
                and delta is None
                and charge_pass is None
                and aromatic_pass is None
                and pseudo_pass is not None
            )
        if not valid:
            raise PoseBustersPreparedLigandDiagnosticError(
                "prepared-ligand atom fields do not match their role"
            )
        observed_number = float.fromhex(observed)
        if observed_number.hex() != float(token).hex():
            raise PoseBustersPreparedLigandDiagnosticError(
                "observed charge token and binary64 value differ"
            )
        if expected is not None and delta is not None:
            expected_number = float.fromhex(expected)
            calculated_delta = abs(observed_number - expected_number)
            if (
                delta != calculated_delta.hex()
                or charge_pass
                != (calculated_delta <= POSEBUSTERS_PREPARED_LIGAND_CHARGE_TOLERANCE)
                or bool(self.element_type_compatible)
                != _element_type_compatible(atomic_number, atom_type)
            ):
                raise PoseBustersPreparedLigandDiagnosticError(
                    "real-atom charge or element/type diagnostics are inconsistent"
                )
            expected_aromatic_pass = None
            if atomic_number == 6:
                expected_aromatic_pass = (
                    atom_type == "A" if aromatic else atom_type in {"C", "CG0"}
                )
            if aromatic_pass != expected_aromatic_pass:
                raise PoseBustersPreparedLigandDiagnosticError(
                    "aromatic-carbon type diagnostic is inconsistent"
                )
        elif (
            pseudo_pass != (atom_type == "G0" and observed_number == 0.0)
            or bool(self.element_type_compatible) != pseudo_pass
        ):
            raise PoseBustersPreparedLigandDiagnosticError(
                "macrocycle pseudoatom diagnostic is inconsistent"
            )
        object.__setattr__(self, "pdbqt_serial", serial)
        object.__setattr__(self, "pdbqt_atom_name", atom_name)
        object.__setattr__(self, "role", role)
        object.__setattr__(self, "source_smiles_atom_index", source_index)
        object.__setattr__(
            self,
            "source_parent_smiles_atom_index",
            parent_index,
        )
        object.__setattr__(self, "atomic_number", atomic_number)
        object.__setattr__(self, "element_symbol", element)
        object.__setattr__(self, "aromatic", aromatic)
        object.__setattr__(self, "autodock4_atom_type", atom_type)
        object.__setattr__(self, "observed_charge_token", token)
        object.__setattr__(self, "observed_charge_binary64_hex", observed)
        object.__setattr__(
            self,
            "expected_gasteiger_charge_binary64_hex",
            expected,
        )
        object.__setattr__(self, "absolute_charge_delta_binary64_hex", delta)
        object.__setattr__(
            self,
            "charge_serialization_tolerance_pass",
            charge_pass,
        )
        object.__setattr__(
            self, "element_type_compatible", bool(self.element_type_compatible)
        )
        object.__setattr__(
            self,
            "aromatic_carbon_type_compatible",
            aromatic_pass,
        )
        object.__setattr__(self, "pseudoatom_zero_charge_pass", pseudo_pass)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "pdbqt_serial": self.pdbqt_serial,
            "pdbqt_atom_name": self.pdbqt_atom_name,
            "role": self.role,
            "source_smiles_atom_index": self.source_smiles_atom_index,
            "source_parent_smiles_atom_index": (self.source_parent_smiles_atom_index),
            "atomic_number": self.atomic_number,
            "element_symbol": self.element_symbol,
            "aromatic": self.aromatic,
            "autodock4_atom_type": self.autodock4_atom_type,
            "observed_charge_token": self.observed_charge_token,
            "observed_charge_binary64_hex": self.observed_charge_binary64_hex,
            "expected_gasteiger_charge_binary64_hex": (
                self.expected_gasteiger_charge_binary64_hex
            ),
            "absolute_charge_delta_binary64_hex": (
                self.absolute_charge_delta_binary64_hex
            ),
            "charge_serialization_tolerance_pass": (
                self.charge_serialization_tolerance_pass
            ),
            "element_type_compatible": self.element_type_compatible,
            "aromatic_carbon_type_compatible": (self.aromatic_carbon_type_compatible),
            "pseudoatom_zero_charge_pass": self.pseudoatom_zero_charge_pass,
        }


@dataclass(frozen=True, slots=True)
class PoseBustersPreparedLigandCase:
    case_id: str
    status: str
    disposition_code: str
    preparation_status: str
    preparation_disposition_code: str
    diagnostic_attempted: bool = False
    prepared_ligand_sha256: str = ""
    prepared_ligand_size_bytes: int = 0
    embedded_smiles_sha256: str = ""
    atom_rows: tuple[PoseBustersPreparedLigandAtom, ...] = ()
    real_atom_count: int = 0
    pseudoatom_count: int = 0
    atom_type_counts: tuple[tuple[str, int], ...] = ()
    expected_total_charge_binary64_hex: str = ""
    observed_total_charge_binary64_hex: str = ""
    maximum_absolute_charge_delta_binary64_hex: str = ""
    all_real_atoms_within_charge_serialization_tolerance: bool | None = None
    all_atoms_element_type_compatible: bool | None = None
    all_aromatic_carbons_type_compatible: bool | None = None
    all_pseudoatoms_zero_charge: bool | None = None
    error_code: str = ""
    error_type: str = ""
    error_message_sha256: str = ""
    schema_id: str = POSEBUSTERS_PREPARED_LIGAND_CASE_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_PREPARED_LIGAND_CASE_SCHEMA_ID:
            raise PoseBustersPreparedLigandDiagnosticError(
                "unsupported prepared-ligand case schema"
            )
        case_id = _case_id(self.case_id)
        status = str(self.status)
        if status not in _CASE_STATUSES:
            raise PoseBustersPreparedLigandDiagnosticError(
                "prepared-ligand case status is invalid"
            )
        disposition = _token(self.disposition_code, name="diagnostic disposition")
        preparation_status = _token(
            self.preparation_status,
            name="preparation status",
        )
        preparation_disposition = _token(
            self.preparation_disposition_code,
            name="preparation disposition",
        )
        atoms = tuple(self.atom_rows)
        if (
            tuple(row.pdbqt_serial for row in atoms) != tuple(range(1, len(atoms) + 1))
            or len(atoms) > POSEBUSTERS_PREPARED_LIGAND_MAX_ATOMS_PER_CASE
        ):
            raise PoseBustersPreparedLigandDiagnosticError(
                "diagnostic atoms must use canonical contiguous serial order"
            )
        real_count = _positive_int(
            self.real_atom_count,
            name="real atom count",
            allow_zero=True,
        )
        pseudo_count = _positive_int(
            self.pseudoatom_count,
            name="pseudoatom count",
            allow_zero=True,
        )
        type_counts = tuple(
            (
                _bounded_ascii(atom_type, name="atom type count key", maximum=8),
                _positive_int(count, name="atom type count"),
            )
            for atom_type, count in self.atom_type_counts
        )
        if tuple(sorted(type_counts)) != type_counts or len(
            {atom_type for atom_type, _count in type_counts}
        ) != len(type_counts):
            raise PoseBustersPreparedLigandDiagnosticError(
                "atom type counts must be sorted unique rows"
            )
        ligand_size = _positive_int(
            self.prepared_ligand_size_bytes,
            name="prepared ligand size",
            allow_zero=True,
        )
        attempted = bool(self.diagnostic_attempted)
        flags = (
            self.all_real_atoms_within_charge_serialization_tolerance,
            self.all_atoms_element_type_compatible,
            self.all_aromatic_carbons_type_compatible,
            self.all_pseudoatoms_zero_charge,
        )
        error_fields = (self.error_code, self.error_type, self.error_message_sha256)
        if status == "evaluated":
            for row in atoms:
                if not isinstance(row, PoseBustersPreparedLigandAtom):
                    raise PoseBustersPreparedLigandDiagnosticError(
                        "evaluated case contains a non-atom row"
                    )
            valid = (
                preparation_status == "prepared"
                and attempted
                and bool(self.prepared_ligand_sha256)
                and ligand_size > 0
                and bool(self.embedded_smiles_sha256)
                and bool(atoms)
                and real_count
                == sum(row.role != "macrocycle_closure_pseudoatom" for row in atoms)
                and pseudo_count
                == sum(row.role == "macrocycle_closure_pseudoatom" for row in atoms)
                and sum(count for _atom_type, count in type_counts) == len(atoms)
                and all(flag is not None for flag in flags)
                and not any(error_fields)
            )
        elif status == "diagnostic_failure":
            valid = (
                preparation_status == "prepared"
                and attempted
                and bool(self.prepared_ligand_sha256)
                and ligand_size > 0
                and not atoms
                and real_count == 0
                and pseudo_count == 0
                and not type_counts
                and not self.embedded_smiles_sha256
                and all(flag is None for flag in flags)
                and all(error_fields)
            )
        else:
            expected_preparation = {
                "abstain_chemistry_scope": "abstain_chemistry_scope",
                "blocked_preparation_failure": "preparation_failure",
                "blocked_upstream_failure": "upstream_failure",
            }[status]
            valid = (
                preparation_status == expected_preparation
                and not attempted
                and not self.prepared_ligand_sha256
                and ligand_size == 0
                and not self.embedded_smiles_sha256
                and not atoms
                and real_count == 0
                and pseudo_count == 0
                and not type_counts
                and all(flag is None for flag in flags)
                and not any(error_fields)
            )
        if not valid:
            raise PoseBustersPreparedLigandDiagnosticError(
                "prepared-ligand case fields are inconsistent with status"
            )
        digest_fields = (
            "prepared_ligand_sha256",
            "embedded_smiles_sha256",
            "error_message_sha256",
        )
        for field_name in digest_fields:
            value = getattr(self, field_name)
            if value:
                object.__setattr__(
                    self,
                    field_name,
                    _digest(value, name=field_name.replace("_", " ")),
                )
        for field_name in (
            "expected_total_charge_binary64_hex",
            "observed_total_charge_binary64_hex",
            "maximum_absolute_charge_delta_binary64_hex",
        ):
            value = getattr(self, field_name)
            if status == "evaluated":
                object.__setattr__(
                    self,
                    field_name,
                    _validate_hex(value, name=field_name.replace("_", " ")),
                )
            elif value:
                raise PoseBustersPreparedLigandDiagnosticError(
                    "non-evaluated case contains charge aggregates"
                )
        if status == "evaluated":
            real_atoms = tuple(
                row
                for row in atoms
                if row.expected_gasteiger_charge_binary64_hex is not None
            )
            pseudoatoms = tuple(
                row for row in atoms if row.role == "macrocycle_closure_pseudoatom"
            )
            aromatic_carbons = tuple(
                row for row in atoms if row.aromatic_carbon_type_compatible is not None
            )
            expected_total = math.fsum(
                float.fromhex(row.expected_gasteiger_charge_binary64_hex)
                for row in real_atoms
                if row.expected_gasteiger_charge_binary64_hex is not None
            )
            observed_total = math.fsum(
                float.fromhex(row.observed_charge_binary64_hex) for row in real_atoms
            )
            maximum_delta = max(
                float.fromhex(row.absolute_charge_delta_binary64_hex)
                for row in real_atoms
                if row.absolute_charge_delta_binary64_hex is not None
            )
            actual_type_counts = tuple(
                sorted(Counter(row.autodock4_atom_type for row in atoms).items())
            )
            aggregates_valid = (
                self.expected_total_charge_binary64_hex == expected_total.hex()
                and self.observed_total_charge_binary64_hex == observed_total.hex()
                and self.maximum_absolute_charge_delta_binary64_hex
                == maximum_delta.hex()
                and type_counts == actual_type_counts
                and bool(self.all_real_atoms_within_charge_serialization_tolerance)
                == all(row.charge_serialization_tolerance_pass for row in real_atoms)
                and bool(self.all_atoms_element_type_compatible)
                == all(row.element_type_compatible for row in atoms)
                and bool(self.all_aromatic_carbons_type_compatible)
                == all(row.aromatic_carbon_type_compatible for row in aromatic_carbons)
                and bool(self.all_pseudoatoms_zero_charge)
                == all(row.pseudoatom_zero_charge_pass for row in pseudoatoms)
            )
            if not aggregates_valid:
                raise PoseBustersPreparedLigandDiagnosticError(
                    "prepared-ligand case aggregates are inconsistent with atom rows"
                )
        if status == "diagnostic_failure":
            object.__setattr__(
                self,
                "error_code",
                _token(self.error_code, name="diagnostic error code"),
            )
            object.__setattr__(
                self,
                "error_type",
                _identifier(self.error_type, name="diagnostic error type"),
            )
        object.__setattr__(self, "case_id", case_id)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "disposition_code", disposition)
        object.__setattr__(self, "preparation_status", preparation_status)
        object.__setattr__(
            self,
            "preparation_disposition_code",
            preparation_disposition,
        )
        object.__setattr__(self, "diagnostic_attempted", attempted)
        object.__setattr__(self, "prepared_ligand_size_bytes", ligand_size)
        object.__setattr__(self, "atom_rows", atoms)
        object.__setattr__(self, "real_atom_count", real_count)
        object.__setattr__(self, "pseudoatom_count", pseudo_count)
        object.__setattr__(self, "atom_type_counts", type_counts)
        for field_name in (
            "all_real_atoms_within_charge_serialization_tolerance",
            "all_atoms_element_type_compatible",
            "all_aromatic_carbons_type_compatible",
            "all_pseudoatoms_zero_charge",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, bool(value))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "case_id": self.case_id,
            "status": self.status,
            "disposition_code": self.disposition_code,
            "preparation_status": self.preparation_status,
            "preparation_disposition_code": self.preparation_disposition_code,
            "diagnostic_attempted": self.diagnostic_attempted,
            "prepared_ligand_sha256": self.prepared_ligand_sha256,
            "prepared_ligand_size_bytes": self.prepared_ligand_size_bytes,
            "embedded_smiles_sha256": self.embedded_smiles_sha256,
            "atom_rows": [row.to_dict() for row in self.atom_rows],
            "real_atom_count": self.real_atom_count,
            "pseudoatom_count": self.pseudoatom_count,
            "atom_type_counts": {
                atom_type: count for atom_type, count in self.atom_type_counts
            },
            "expected_total_charge_binary64_hex": (
                self.expected_total_charge_binary64_hex
            ),
            "observed_total_charge_binary64_hex": (
                self.observed_total_charge_binary64_hex
            ),
            "maximum_absolute_charge_delta_binary64_hex": (
                self.maximum_absolute_charge_delta_binary64_hex
            ),
            "all_real_atoms_within_charge_serialization_tolerance": (
                self.all_real_atoms_within_charge_serialization_tolerance
            ),
            "all_atoms_element_type_compatible": (
                self.all_atoms_element_type_compatible
            ),
            "all_aromatic_carbons_type_compatible": (
                self.all_aromatic_carbons_type_compatible
            ),
            "all_pseudoatoms_zero_charge": self.all_pseudoatoms_zero_charge,
            "error_code": self.error_code,
            "error_type": self.error_type,
            "error_message_sha256": self.error_message_sha256,
        }


@dataclass(frozen=True, slots=True)
class PoseBustersPreparedLigandMetric:
    metric_id: str
    numerator: int
    denominator: int
    schema_id: str = POSEBUSTERS_PREPARED_LIGAND_METRIC_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_PREPARED_LIGAND_METRIC_SCHEMA_ID:
            raise PoseBustersPreparedLigandDiagnosticError(
                "unsupported prepared-ligand metric schema"
            )
        metric = _token(self.metric_id, name="prepared-ligand metric ID")
        numerator = _positive_int(
            self.numerator,
            name="prepared-ligand metric numerator",
            allow_zero=True,
        )
        denominator = _positive_int(
            self.denominator,
            name="prepared-ligand metric denominator",
        )
        if numerator > denominator:
            raise PoseBustersPreparedLigandDiagnosticError(
                "prepared-ligand metric numerator exceeds denominator"
            )
        object.__setattr__(self, "metric_id", metric)
        object.__setattr__(self, "numerator", numerator)
        object.__setattr__(self, "denominator", denominator)

    def to_dict(self) -> dict[str, Any]:
        low, high = _wilson_interval(self.numerator, self.denominator)
        return {
            "schema_id": self.schema_id,
            "metric_id": self.metric_id,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "rate_binary64_hex": (self.numerator / self.denominator).hex(),
            "confidence_level_binary64_hex": (
                POSEBUSTERS_PREPARED_LIGAND_CONFIDENCE_LEVEL.hex()
            ),
            "wilson_low_binary64_hex": low,
            "wilson_high_binary64_hex": high,
        }


def _element_type_compatible(atomic_number: int, atom_type: str) -> bool:
    return atom_type in _ATOM_TYPE_BY_ATOMIC_NUMBER.get(atomic_number, frozenset())


def _evaluate_prepared_ligand(
    prepared: _PreparedCaseView,
    artifact_sha256: str,
    artifact_size: int,
    payload: bytes,
    runtime: _ChargeRuntimeProtocol,
) -> PoseBustersPreparedLigandCase:
    parsed = _parse_ligand_pdbqt(payload)
    source_atoms = runtime.compute_source_atoms(parsed.smiles)
    if tuple(row.source_index for row in source_atoms) != tuple(
        range(1, len(source_atoms) + 1)
    ) or {source for source, _serial in parsed.source_to_serial} != set(
        range(1, len(source_atoms) + 1)
    ):
        raise PoseBustersPreparedLigandDiagnosticError(
            "embedded SMILES IDX does not exactly cover source atoms"
        )
    source_by_index = {row.source_index: row for row in source_atoms}
    serial_by_source = dict(parsed.source_to_serial)
    hydrogen_serials_by_parent: dict[int, list[int]] = {}
    for parent, serial in parsed.parent_to_hydrogen_serial:
        if parent not in source_by_index:
            raise PoseBustersPreparedLigandDiagnosticError(
                "H PARENT mapping references an unknown source atom"
            )
        hydrogen_serials_by_parent.setdefault(parent, []).append(serial)
    for serials in hydrogen_serials_by_parent.values():
        serials.sort()

    expected: dict[
        int,
        tuple[str, int | None, int | None, int, str, bool | None, float],
    ] = {}
    for source in source_atoms:
        retained_serials = hydrogen_serials_by_parent.get(source.source_index, [])
        if len(retained_serials) > len(source.hydrogen_charges):
            raise PoseBustersPreparedLigandDiagnosticError(
                "H PARENT mapping exceeds source hydrogen count"
            )
        heavy_charge = source.charge + math.fsum(
            source.hydrogen_charges[len(retained_serials) :]
        )
        expected[serial_by_source[source.source_index]] = (
            "source_atom",
            source.source_index,
            None,
            source.atomic_number,
            source.element_symbol,
            source.aromatic,
            heavy_charge,
        )
        for serial, charge in zip(
            retained_serials,
            source.hydrogen_charges[: len(retained_serials)],
            strict=True,
        ):
            expected[serial] = (
                "retained_polar_hydrogen",
                None,
                source.source_index,
                1,
                "H",
                None,
                charge,
            )
    atom_rows: list[PoseBustersPreparedLigandAtom] = []
    real_expected: list[float] = []
    real_observed: list[float] = []
    real_deltas: list[float] = []
    for atom in parsed.atoms:
        if atom.serial not in expected:
            pseudo_pass = atom.atom_type == "G0" and atom.observed_charge == 0.0
            atom_rows.append(
                PoseBustersPreparedLigandAtom(
                    pdbqt_serial=atom.serial,
                    pdbqt_atom_name=atom.atom_name,
                    role="macrocycle_closure_pseudoatom",
                    source_smiles_atom_index=None,
                    source_parent_smiles_atom_index=None,
                    atomic_number=0,
                    element_symbol="G",
                    aromatic=None,
                    autodock4_atom_type=atom.atom_type,
                    observed_charge_token=atom.observed_charge_token,
                    observed_charge_binary64_hex=atom.observed_charge.hex(),
                    expected_gasteiger_charge_binary64_hex=None,
                    absolute_charge_delta_binary64_hex=None,
                    charge_serialization_tolerance_pass=None,
                    element_type_compatible=pseudo_pass,
                    aromatic_carbon_type_compatible=None,
                    pseudoatom_zero_charge_pass=pseudo_pass,
                )
            )
            continue
        (
            role,
            source_index,
            parent_index,
            atomic_number,
            element_symbol,
            aromatic,
            expected_charge,
        ) = expected[atom.serial]
        delta = abs(atom.observed_charge - expected_charge)
        serialization_pass = delta <= POSEBUSTERS_PREPARED_LIGAND_CHARGE_TOLERANCE
        element_pass = _element_type_compatible(atomic_number, atom.atom_type)
        aromatic_pass: bool | None = None
        if atomic_number == 6:
            aromatic_pass = (
                atom.atom_type == "A" if aromatic else atom.atom_type in {"C", "CG0"}
            )
        atom_rows.append(
            PoseBustersPreparedLigandAtom(
                pdbqt_serial=atom.serial,
                pdbqt_atom_name=atom.atom_name,
                role=role,
                source_smiles_atom_index=source_index,
                source_parent_smiles_atom_index=parent_index,
                atomic_number=atomic_number,
                element_symbol=element_symbol,
                aromatic=aromatic,
                autodock4_atom_type=atom.atom_type,
                observed_charge_token=atom.observed_charge_token,
                observed_charge_binary64_hex=atom.observed_charge.hex(),
                expected_gasteiger_charge_binary64_hex=expected_charge.hex(),
                absolute_charge_delta_binary64_hex=delta.hex(),
                charge_serialization_tolerance_pass=serialization_pass,
                element_type_compatible=element_pass,
                aromatic_carbon_type_compatible=aromatic_pass,
                pseudoatom_zero_charge_pass=None,
            )
        )
        real_expected.append(expected_charge)
        real_observed.append(atom.observed_charge)
        real_deltas.append(delta)
    if len(atom_rows) != len(parsed.atoms) or len(expected) != len(real_expected):
        raise PoseBustersPreparedLigandDiagnosticError(
            "prepared ligand atom mapping is incomplete"
        )
    type_counts = tuple(
        sorted(Counter(row.autodock4_atom_type for row in atom_rows).items())
    )
    pseudo_rows = tuple(
        row for row in atom_rows if row.role == "macrocycle_closure_pseudoatom"
    )
    aromatic_rows = tuple(
        row for row in atom_rows if row.aromatic_carbon_type_compatible is not None
    )
    return PoseBustersPreparedLigandCase(
        case_id=prepared.case_id,
        status="evaluated",
        disposition_code="same_algorithm_gasteiger_and_type_diagnostic_complete",
        preparation_status=prepared.status,
        preparation_disposition_code=prepared.disposition_code,
        diagnostic_attempted=True,
        prepared_ligand_sha256=artifact_sha256,
        prepared_ligand_size_bytes=artifact_size,
        embedded_smiles_sha256=parsed.smiles_sha256,
        atom_rows=tuple(atom_rows),
        real_atom_count=len(real_expected),
        pseudoatom_count=len(pseudo_rows),
        atom_type_counts=type_counts,
        expected_total_charge_binary64_hex=math.fsum(real_expected).hex(),
        observed_total_charge_binary64_hex=math.fsum(real_observed).hex(),
        maximum_absolute_charge_delta_binary64_hex=max(real_deltas).hex(),
        all_real_atoms_within_charge_serialization_tolerance=all(
            row.charge_serialization_tolerance_pass
            for row in atom_rows
            if row.charge_serialization_tolerance_pass is not None
        ),
        all_atoms_element_type_compatible=all(
            row.element_type_compatible for row in atom_rows
        ),
        all_aromatic_carbons_type_compatible=all(
            row.aromatic_carbon_type_compatible for row in aromatic_rows
        ),
        all_pseudoatoms_zero_charge=all(
            row.pseudoatom_zero_charge_pass for row in pseudo_rows
        ),
    )


def _blocked_case(prepared: _PreparedCaseView) -> PoseBustersPreparedLigandCase:
    status = {
        "abstain_chemistry_scope": "abstain_chemistry_scope",
        "preparation_failure": "blocked_preparation_failure",
        "upstream_failure": "blocked_upstream_failure",
    }[prepared.status]
    disposition = {
        "abstain_chemistry_scope": "chemistry_scope_abstention",
        "preparation_failure": "blocked_by_strict_preparation_failure",
        "upstream_failure": "blocked_by_upstream_preparation_failure",
    }[prepared.status]
    return PoseBustersPreparedLigandCase(
        case_id=prepared.case_id,
        status=status,
        disposition_code=disposition,
        preparation_status=prepared.status,
        preparation_disposition_code=prepared.disposition_code,
    )


def _diagnose_case(
    prepared: _PreparedCaseView,
    prepared_payloads: Mapping[str, bytes],
    runtime: _ChargeRuntimeProtocol,
) -> PoseBustersPreparedLigandCase:
    if prepared.status != "prepared":
        return _blocked_case(prepared)
    artifacts = {row.role: row for row in prepared.artifacts}
    ligand = artifacts["prepared_ligand_pdbqt"]
    payload = prepared_payloads[ligand.relative_path]
    try:
        return _evaluate_prepared_ligand(
            prepared,
            ligand.sha256,
            ligand.size_bytes,
            payload,
            runtime,
        )
    except Exception as exc:
        return PoseBustersPreparedLigandCase(
            case_id=prepared.case_id,
            status="diagnostic_failure",
            disposition_code="prepared_ligand_diagnostic_failed",
            preparation_status=prepared.status,
            preparation_disposition_code=prepared.disposition_code,
            diagnostic_attempted=True,
            prepared_ligand_sha256=ligand.sha256,
            prepared_ligand_size_bytes=ligand.size_bytes,
            error_code="prepared_ligand_diagnostic_failed",
            error_type=type(exc).__name__,
            error_message_sha256=_hash_bytes(_normalized_error(exc)),
        )


def _implementation_source_members() -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted(
            {
                "external_preparation_contract": _source_file_sha256(
                    Path(__file__).with_name(
                        "public_posebusters_external_preparation.py"
                    )
                ),
                "preparation_receipt_loader": _source_file_sha256(
                    Path(__file__).with_name("public_posebusters_vina_execution.py")
                ),
                "prepared_ligand_diagnostic": _source_file_sha256(__file__),
            }.items()
        )
    )


def _observation_metrics(
    rows: Sequence[PoseBustersPreparedLigandCase],
) -> tuple[PoseBustersPreparedLigandMetric, ...]:
    denominator = len(rows)
    evaluated = tuple(row for row in rows if row.status == "evaluated")
    values = {
        "all_atom_type_compatibility_pass_rate": sum(
            row.all_atoms_element_type_compatible is True for row in evaluated
        ),
        "aromatic_carbon_type_consistency_pass_rate": sum(
            row.all_aromatic_carbons_type_compatible is True for row in evaluated
        ),
        "charge_serialization_tolerance_pass_rate": sum(
            row.all_real_atoms_within_charge_serialization_tolerance is True
            for row in evaluated
        ),
        "diagnostic_failure_rate": sum(
            row.status == "diagnostic_failure" for row in rows
        ),
        "prepared_input_diagnostic_rate": len(evaluated),
        "prepared_input_pair_rate": sum(
            row.preparation_status == "prepared" for row in rows
        ),
        "pseudoatom_zero_charge_pass_rate": sum(
            row.all_pseudoatoms_zero_charge is True for row in evaluated
        ),
    }
    return tuple(
        PoseBustersPreparedLigandMetric(
            metric_id=metric_id,
            numerator=numerator,
            denominator=denominator,
        )
        for metric_id, numerator in sorted(values.items())
    )


@dataclass(frozen=True, slots=True)
class PoseBustersPreparedLigandObservationReceipt:
    observation_utc: str
    preparation_receipt_sha256: str
    preparation_receipt_file_sha256: str
    preparation_artifact_set_sha256: str
    preparation_runtime_identity: dict[str, Any]
    preparation_runtime_identity_sha256: str
    runtime_identity: PoseBustersPreparedLigandRuntimeIdentity
    implementation_source_members: tuple[tuple[str, str], ...]
    case_rows: tuple[PoseBustersPreparedLigandCase, ...]
    metrics: tuple[PoseBustersPreparedLigandMetric, ...]
    schema_id: str = POSEBUSTERS_PREPARED_LIGAND_OBSERVATION_SCHEMA_ID
    configuration_sha256: str = POSEBUSTERS_PREPARED_LIGAND_CONFIGURATION_SHA256

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_PREPARED_LIGAND_OBSERVATION_SCHEMA_ID:
            raise PoseBustersPreparedLigandDiagnosticError(
                "unsupported prepared-ligand observation schema"
            )
        if (
            self.configuration_sha256
            != POSEBUSTERS_PREPARED_LIGAND_CONFIGURATION_SHA256
        ):
            raise PoseBustersPreparedLigandDiagnosticError(
                "prepared-ligand observation configuration changed"
            )
        observed = _utc_timestamp(self.observation_utc)
        for field_name in (
            "preparation_receipt_sha256",
            "preparation_receipt_file_sha256",
            "preparation_artifact_set_sha256",
            "preparation_runtime_identity_sha256",
        ):
            object.__setattr__(
                self,
                field_name,
                _digest(getattr(self, field_name), name=field_name.replace("_", " ")),
            )
        preparation_runtime = dict(self.preparation_runtime_identity)
        if (
            not preparation_runtime
            or _canonical_sha256(preparation_runtime)
            != self.preparation_runtime_identity_sha256
        ):
            raise PoseBustersPreparedLigandDiagnosticError(
                "preparation runtime identity is inconsistent"
            )
        if not isinstance(
            self.runtime_identity,
            PoseBustersPreparedLigandRuntimeIdentity,
        ):
            raise PoseBustersPreparedLigandDiagnosticError(
                "prepared-ligand observation runtime identity is invalid"
            )
        source_members = tuple(self.implementation_source_members)
        if (
            not source_members
            or tuple(sorted(source_members)) != source_members
            or len({name for name, _digest_value in source_members})
            != len(source_members)
        ):
            raise PoseBustersPreparedLigandDiagnosticError(
                "implementation source members must be sorted unique rows"
            )
        for name, digest in source_members:
            _token(name, name="implementation source member")
            _digest(digest, name="implementation source member digest")
        rows = tuple(self.case_rows)
        if (
            not rows
            or tuple(row.case_id for row in rows)
            != tuple(sorted(row.case_id for row in rows))
            or len({row.case_id for row in rows}) != len(rows)
            or any(not isinstance(row, PoseBustersPreparedLigandCase) for row in rows)
        ):
            raise PoseBustersPreparedLigandDiagnosticError(
                "prepared-ligand observation cases are not canonical"
            )
        metrics = tuple(self.metrics)
        expected_metrics = _observation_metrics(rows)
        if (
            any(not isinstance(row, PoseBustersPreparedLigandMetric) for row in metrics)
            or metrics != expected_metrics
        ):
            raise PoseBustersPreparedLigandDiagnosticError(
                "prepared-ligand observation metrics are inconsistent"
            )
        object.__setattr__(self, "observation_utc", observed)
        object.__setattr__(
            self,
            "preparation_runtime_identity",
            preparation_runtime,
        )
        object.__setattr__(self, "implementation_source_members", source_members)
        object.__setattr__(self, "case_rows", rows)
        object.__setattr__(self, "metrics", metrics)

    def _payload(self) -> dict[str, Any]:
        evaluated = tuple(row for row in self.case_rows if row.status == "evaluated")
        atom_type_counts = Counter(
            atom.autodock4_atom_type for row in evaluated for atom in row.atom_rows
        )
        real_atoms = tuple(
            atom
            for row in evaluated
            for atom in row.atom_rows
            if atom.expected_gasteiger_charge_binary64_hex is not None
        )
        pseudoatoms = tuple(
            atom
            for row in evaluated
            for atom in row.atom_rows
            if atom.role == "macrocycle_closure_pseudoatom"
        )
        maximum_delta = max(
            (
                float.fromhex(atom.absolute_charge_delta_binary64_hex)
                for atom in real_atoms
                if atom.absolute_charge_delta_binary64_hex is not None
            ),
            default=0.0,
        )
        maximum_expected_total = max(
            (
                abs(float.fromhex(row.expected_total_charge_binary64_hex))
                for row in evaluated
            ),
            default=0.0,
        )
        maximum_observed_total = max(
            (
                abs(float.fromhex(row.observed_total_charge_binary64_hex))
                for row in evaluated
            ),
            default=0.0,
        )
        source_members = dict(self.implementation_source_members)
        return {
            "schema_id": self.schema_id,
            "observation_utc": self.observation_utc,
            "preparation_receipt_sha256": self.preparation_receipt_sha256,
            "preparation_receipt_file_sha256": (self.preparation_receipt_file_sha256),
            "preparation_artifact_set_sha256": (self.preparation_artifact_set_sha256),
            "preparation_runtime_identity": self.preparation_runtime_identity,
            "preparation_runtime_identity_sha256": (
                self.preparation_runtime_identity_sha256
            ),
            "runtime_identity": self.runtime_identity.to_dict(),
            "runtime_identity_sha256": self.runtime_identity.fingerprint_sha256,
            "implementation_source_members": source_members,
            "implementation_source_sha256": _canonical_sha256(source_members),
            "configuration": POSEBUSTERS_PREPARED_LIGAND_CONFIGURATION,
            "configuration_sha256": self.configuration_sha256,
            "all_case_denominator": len(self.case_rows),
            "prepared_case_count": sum(
                row.preparation_status == "prepared" for row in self.case_rows
            ),
            "evaluated_case_count": len(evaluated),
            "diagnostic_failure_case_count": sum(
                row.status == "diagnostic_failure" for row in self.case_rows
            ),
            "abstained_case_count": sum(
                row.status == "abstain_chemistry_scope" for row in self.case_rows
            ),
            "blocked_preparation_failure_case_count": sum(
                row.status == "blocked_preparation_failure" for row in self.case_rows
            ),
            "blocked_upstream_failure_case_count": sum(
                row.status == "blocked_upstream_failure" for row in self.case_rows
            ),
            "real_pdbqt_atom_count": len(real_atoms),
            "macrocycle_pseudoatom_count": len(pseudoatoms),
            "atom_type_counts": dict(sorted(atom_type_counts.items())),
            "maximum_absolute_charge_delta_binary64_hex": maximum_delta.hex(),
            "maximum_absolute_expected_total_charge_binary64_hex": (
                maximum_expected_total.hex()
            ),
            "maximum_absolute_observed_total_charge_binary64_hex": (
                maximum_observed_total.hex()
            ),
            "case_rows": [row.to_dict() for row in self.case_rows],
            "metrics": [row.to_dict() for row in self.metrics],
            "same_algorithm_direct_gasteiger_recomputation_performed": bool(evaluated),
            "independent_charge_oracle_executed": False,
            "independent_ad4_type_oracle_executed": False,
            "embedded_smiles_source_sdf_equivalence_verified": False,
            "receptor_charge_and_type_audited": False,
            "runtime_network_used": False,
            "external_docking_engine_executed": False,
            "benchmark_executed": False,
            "scientific_blockers": list(
                POSEBUSTERS_PREPARED_LIGAND_SCIENTIFIC_BLOCKERS
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
        return _atomic_write_new(output_path, self.to_dict())


def _build_observation(
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    *,
    expected_preparation_receipt_sha256: str,
    observation_utc: str,
) -> PoseBustersPreparedLigandObservationReceipt:
    try:
        preparation, prepared_payloads = _load_preparation_receipt(
            preparation_receipt_path,
            preparation_artifact_root,
            expected_receipt_sha256=expected_preparation_receipt_sha256,
        )
    except PoseBustersVinaExecutionError as exc:
        raise PoseBustersPreparedLigandDiagnosticError(
            "external-preparation receipt failed exact verification"
        ) from exc
    runtime = _load_rdkit_runtime()
    rows = tuple(
        _diagnose_case(prepared, prepared_payloads, runtime)
        for prepared in preparation.case_rows
    )
    sources = _implementation_source_members()
    return PoseBustersPreparedLigandObservationReceipt(
        observation_utc=observation_utc,
        preparation_receipt_sha256=preparation.receipt_sha256,
        preparation_receipt_file_sha256=preparation.receipt_file_sha256,
        preparation_artifact_set_sha256=preparation.artifact_set_sha256,
        preparation_runtime_identity=preparation.runtime_identity,
        preparation_runtime_identity_sha256=(preparation.runtime_identity_sha256),
        runtime_identity=runtime.identity,
        implementation_source_members=sources,
        case_rows=rows,
        metrics=_observation_metrics(rows),
    )


def materialize_posebusters_prepared_ligand_observation(
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    *,
    expected_preparation_receipt_sha256: str,
    observation_utc: str,
) -> PoseBustersPreparedLigandObservationReceipt:
    return _build_observation(
        preparation_receipt_path,
        preparation_artifact_root,
        expected_preparation_receipt_sha256=(expected_preparation_receipt_sha256),
        observation_utc=observation_utc,
    )


def _runtime_payload_from_raw(raw: object) -> PoseBustersPreparedLigandRuntimePayload:
    if not isinstance(raw, dict):
        raise PoseBustersPreparedLigandDiagnosticError(
            "RDKit runtime payload must be an object"
        )
    payload = PoseBustersPreparedLigandRuntimePayload(
        distribution_name=raw.get("distribution_name"),
        distribution_version=raw.get("distribution_version"),
        payload_sha256=raw.get("payload_sha256"),
        payload_file_count=raw.get("payload_file_count"),
        payload_size_bytes=raw.get("payload_size_bytes"),
        schema_id=raw.get("schema_id"),
    )
    if payload.to_dict() != raw:
        raise PoseBustersPreparedLigandDiagnosticError(
            "RDKit runtime payload contains unsupported fields"
        )
    return payload


def _runtime_from_raw(raw: object) -> PoseBustersPreparedLigandRuntimeIdentity:
    if not isinstance(raw, dict):
        raise PoseBustersPreparedLigandDiagnosticError(
            "prepared-ligand runtime identity must be an object"
        )
    runtime = PoseBustersPreparedLigandRuntimeIdentity(
        python_implementation=raw.get("python_implementation"),
        python_version=raw.get("python_version"),
        python_cache_tag=raw.get("python_cache_tag"),
        python_executable_sha256=raw.get("python_executable_sha256"),
        python_executable_size_bytes=raw.get("python_executable_size_bytes"),
        platform_system=raw.get("platform_system"),
        platform_machine=raw.get("platform_machine"),
        libc_name=raw.get("libc_name"),
        libc_version=raw.get("libc_version"),
        filesystem_encoding=raw.get("filesystem_encoding"),
        rdkit_version=raw.get("rdkit_version"),
        rdkit_build=raw.get("rdkit_build"),
        boost_version=raw.get("boost_version"),
        rdkit_payload=_runtime_payload_from_raw(raw.get("rdkit_payload")),
        schema_id=raw.get("schema_id"),
    )
    if runtime.to_dict() != raw:
        raise PoseBustersPreparedLigandDiagnosticError(
            "prepared-ligand runtime identity contains unsupported fields"
        )
    return runtime


def _atom_from_raw(raw: object) -> PoseBustersPreparedLigandAtom:
    if not isinstance(raw, dict):
        raise PoseBustersPreparedLigandDiagnosticError(
            "prepared-ligand atom row must be an object"
        )
    atom = PoseBustersPreparedLigandAtom(
        pdbqt_serial=raw.get("pdbqt_serial"),
        pdbqt_atom_name=raw.get("pdbqt_atom_name"),
        role=raw.get("role"),
        source_smiles_atom_index=raw.get("source_smiles_atom_index"),
        source_parent_smiles_atom_index=raw.get("source_parent_smiles_atom_index"),
        atomic_number=raw.get("atomic_number"),
        element_symbol=raw.get("element_symbol"),
        aromatic=raw.get("aromatic"),
        autodock4_atom_type=raw.get("autodock4_atom_type"),
        observed_charge_token=raw.get("observed_charge_token"),
        observed_charge_binary64_hex=raw.get("observed_charge_binary64_hex"),
        expected_gasteiger_charge_binary64_hex=raw.get(
            "expected_gasteiger_charge_binary64_hex"
        ),
        absolute_charge_delta_binary64_hex=raw.get(
            "absolute_charge_delta_binary64_hex"
        ),
        charge_serialization_tolerance_pass=raw.get(
            "charge_serialization_tolerance_pass"
        ),
        element_type_compatible=raw.get("element_type_compatible"),
        aromatic_carbon_type_compatible=raw.get("aromatic_carbon_type_compatible"),
        pseudoatom_zero_charge_pass=raw.get("pseudoatom_zero_charge_pass"),
        schema_id=raw.get("schema_id"),
    )
    if atom.to_dict() != raw:
        raise PoseBustersPreparedLigandDiagnosticError(
            "prepared-ligand atom row contains unsupported fields"
        )
    return atom


def _case_from_raw(raw: object) -> PoseBustersPreparedLigandCase:
    if not isinstance(raw, dict):
        raise PoseBustersPreparedLigandDiagnosticError(
            "prepared-ligand case row must be an object"
        )
    raw_atoms = raw.get("atom_rows")
    raw_type_counts = raw.get("atom_type_counts")
    if not isinstance(raw_atoms, list) or not isinstance(raw_type_counts, dict):
        raise PoseBustersPreparedLigandDiagnosticError(
            "prepared-ligand case atom payload is invalid"
        )
    case = PoseBustersPreparedLigandCase(
        case_id=raw.get("case_id"),
        status=raw.get("status"),
        disposition_code=raw.get("disposition_code"),
        preparation_status=raw.get("preparation_status"),
        preparation_disposition_code=raw.get("preparation_disposition_code"),
        diagnostic_attempted=raw.get("diagnostic_attempted"),
        prepared_ligand_sha256=raw.get("prepared_ligand_sha256"),
        prepared_ligand_size_bytes=raw.get("prepared_ligand_size_bytes"),
        embedded_smiles_sha256=raw.get("embedded_smiles_sha256"),
        atom_rows=tuple(_atom_from_raw(row) for row in raw_atoms),
        real_atom_count=raw.get("real_atom_count"),
        pseudoatom_count=raw.get("pseudoatom_count"),
        atom_type_counts=tuple(sorted(raw_type_counts.items())),
        expected_total_charge_binary64_hex=raw.get(
            "expected_total_charge_binary64_hex"
        ),
        observed_total_charge_binary64_hex=raw.get(
            "observed_total_charge_binary64_hex"
        ),
        maximum_absolute_charge_delta_binary64_hex=raw.get(
            "maximum_absolute_charge_delta_binary64_hex"
        ),
        all_real_atoms_within_charge_serialization_tolerance=raw.get(
            "all_real_atoms_within_charge_serialization_tolerance"
        ),
        all_atoms_element_type_compatible=raw.get("all_atoms_element_type_compatible"),
        all_aromatic_carbons_type_compatible=raw.get(
            "all_aromatic_carbons_type_compatible"
        ),
        all_pseudoatoms_zero_charge=raw.get("all_pseudoatoms_zero_charge"),
        error_code=raw.get("error_code"),
        error_type=raw.get("error_type"),
        error_message_sha256=raw.get("error_message_sha256"),
        schema_id=raw.get("schema_id"),
    )
    if case.to_dict() != raw:
        raise PoseBustersPreparedLigandDiagnosticError(
            "prepared-ligand case row contains unsupported fields"
        )
    return case


def _metric_from_raw(raw: object) -> PoseBustersPreparedLigandMetric:
    if not isinstance(raw, dict):
        raise PoseBustersPreparedLigandDiagnosticError(
            "prepared-ligand metric row must be an object"
        )
    metric = PoseBustersPreparedLigandMetric(
        metric_id=raw.get("metric_id"),
        numerator=raw.get("numerator"),
        denominator=raw.get("denominator"),
        schema_id=raw.get("schema_id"),
    )
    if metric.to_dict() != raw:
        raise PoseBustersPreparedLigandDiagnosticError(
            "prepared-ligand metric row contains unsupported fields"
        )
    return metric


def _observation_from_raw(
    raw: dict[str, Any],
) -> PoseBustersPreparedLigandObservationReceipt:
    raw_sources = raw.get("implementation_source_members")
    raw_cases = raw.get("case_rows")
    raw_metrics = raw.get("metrics")
    if (
        not isinstance(raw_sources, dict)
        or not isinstance(raw_cases, list)
        or not isinstance(raw_metrics, list)
    ):
        raise PoseBustersPreparedLigandDiagnosticError(
            "prepared-ligand observation collections are invalid"
        )
    if tuple(sorted(raw_sources.items())) != _implementation_source_members():
        raise PoseBustersPreparedLigandDiagnosticError(
            "prepared-ligand observation source identity is stale"
        )
    receipt = PoseBustersPreparedLigandObservationReceipt(
        observation_utc=raw.get("observation_utc"),
        preparation_receipt_sha256=raw.get("preparation_receipt_sha256"),
        preparation_receipt_file_sha256=raw.get("preparation_receipt_file_sha256"),
        preparation_artifact_set_sha256=raw.get("preparation_artifact_set_sha256"),
        preparation_runtime_identity=raw.get("preparation_runtime_identity"),
        preparation_runtime_identity_sha256=raw.get(
            "preparation_runtime_identity_sha256"
        ),
        runtime_identity=_runtime_from_raw(raw.get("runtime_identity")),
        implementation_source_members=tuple(sorted(raw_sources.items())),
        case_rows=tuple(_case_from_raw(row) for row in raw_cases),
        metrics=tuple(_metric_from_raw(row) for row in raw_metrics),
        schema_id=raw.get("schema_id"),
        configuration_sha256=raw.get("configuration_sha256"),
    )
    if receipt.to_dict() != raw:
        raise PoseBustersPreparedLigandDiagnosticError(
            "prepared-ligand observation receipt is internally inconsistent"
        )
    return receipt


def _read_canonical_receipt(
    receipt_path: str | os.PathLike[str],
    *,
    expected_receipt_sha256: str,
    expected_schema_id: str,
) -> tuple[dict[str, Any], bytes]:
    expected = _digest(expected_receipt_sha256, name="expected receipt")
    source = _read_exact_regular_file(
        receipt_path,
        maximum_bytes=POSEBUSTERS_PREPARED_LIGAND_MAX_RECEIPT_BYTES,
    )
    try:
        metadata = Path(receipt_path).stat(follow_symlinks=False)
    except OSError as exc:
        raise PoseBustersPreparedLigandDiagnosticError(
            "prepared-ligand receipt metadata is unavailable"
        ) from exc
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise PoseBustersPreparedLigandDiagnosticError(
            "prepared-ligand receipt must remain mode 0600"
        )
    try:
        raw = json.loads(source)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PoseBustersPreparedLigandDiagnosticError(
            "prepared-ligand receipt is not canonical JSON"
        ) from exc
    if not isinstance(raw, dict) or source != _canonical_bytes(raw) + b"\n":
        raise PoseBustersPreparedLigandDiagnosticError(
            "prepared-ligand receipt bytes are not canonical"
        )
    receipt_sha = raw.get("receipt_sha256")
    payload = dict(raw)
    payload.pop("receipt_sha256", None)
    if (
        raw.get("schema_id") != expected_schema_id
        or not isinstance(receipt_sha, str)
        or _canonical_sha256(payload) != receipt_sha
        or receipt_sha != expected
    ):
        raise PoseBustersPreparedLigandDiagnosticError(
            "prepared-ligand receipt fingerprint or schema is invalid"
        )
    return raw, source


def load_posebusters_prepared_ligand_observation_receipt(
    receipt_path: str | os.PathLike[str],
    *,
    expected_receipt_sha256: str,
) -> PoseBustersPreparedLigandObservationReceipt:
    raw, _source = _read_canonical_receipt(
        receipt_path,
        expected_receipt_sha256=expected_receipt_sha256,
        expected_schema_id=POSEBUSTERS_PREPARED_LIGAND_OBSERVATION_SCHEMA_ID,
    )
    return _observation_from_raw(raw)


def verify_posebusters_prepared_ligand_observation_receipt(
    receipt_path: str | os.PathLike[str],
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    *,
    expected_receipt_sha256: str,
    expected_preparation_receipt_sha256: str,
) -> PoseBustersPreparedLigandObservationReceipt:
    raw, source = _read_canonical_receipt(
        receipt_path,
        expected_receipt_sha256=expected_receipt_sha256,
        expected_schema_id=POSEBUSTERS_PREPARED_LIGAND_OBSERVATION_SCHEMA_ID,
    )
    loaded = _observation_from_raw(raw)
    expected = _build_observation(
        preparation_receipt_path,
        preparation_artifact_root,
        expected_preparation_receipt_sha256=(expected_preparation_receipt_sha256),
        observation_utc=loaded.observation_utc,
    )
    expected_source = _canonical_bytes(expected.to_dict()) + b"\n"
    if source != expected_source:
        raise PoseBustersPreparedLigandDiagnosticError(
            "prepared-ligand observation failed exact source-tree reexecution"
        )
    return expected


def _atom_mapping_projection(atom: PoseBustersPreparedLigandAtom) -> dict[str, Any]:
    return {
        "pdbqt_serial": atom.pdbqt_serial,
        "pdbqt_atom_name": atom.pdbqt_atom_name,
        "role": atom.role,
        "source_smiles_atom_index": atom.source_smiles_atom_index,
        "source_parent_smiles_atom_index": (atom.source_parent_smiles_atom_index),
        "atomic_number": atom.atomic_number,
        "element_symbol": atom.element_symbol,
        "aromatic": atom.aromatic,
        "autodock4_atom_type": atom.autodock4_atom_type,
        "observed_charge_token": atom.observed_charge_token,
        "observed_charge_binary64_hex": atom.observed_charge_binary64_hex,
        "element_type_compatible": atom.element_type_compatible,
        "aromatic_carbon_type_compatible": (atom.aromatic_carbon_type_compatible),
        "pseudoatom_zero_charge_pass": atom.pseudoatom_zero_charge_pass,
    }


def _case_mapping_sha256(case: PoseBustersPreparedLigandCase) -> str:
    return _canonical_sha256(
        [_atom_mapping_projection(atom) for atom in case.atom_rows]
    )


@dataclass(frozen=True, slots=True)
class PoseBustersPreparedLigandComparisonCase:
    case_id: str
    status: str
    disposition_code: str
    rdkit_2022_case_status: str
    rdkit_2025_case_status: str
    rdkit_2022_mapping_sha256: str = ""
    rdkit_2025_mapping_sha256: str = ""
    atom_mapping_equal: bool | None = None
    compared_real_atom_count: int = 0
    pseudoatom_count: int = 0
    bitwise_equal_expected_charge_count: int = 0
    maximum_absolute_expected_charge_delta_binary64_hex: str = ""
    all_expected_charges_bitwise_equal: bool | None = None
    schema_id: str = POSEBUSTERS_PREPARED_LIGAND_COMPARISON_CASE_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_PREPARED_LIGAND_COMPARISON_CASE_SCHEMA_ID:
            raise PoseBustersPreparedLigandDiagnosticError(
                "unsupported prepared-ligand comparison-case schema"
            )
        case_id = _case_id(self.case_id)
        status = str(self.status)
        if status not in _COMPARISON_STATUSES:
            raise PoseBustersPreparedLigandDiagnosticError(
                "prepared-ligand comparison status is invalid"
            )
        disposition = _token(
            self.disposition_code,
            name="prepared-ligand comparison disposition",
        )
        for field_name in ("rdkit_2022_case_status", "rdkit_2025_case_status"):
            value = str(getattr(self, field_name))
            if value not in _CASE_STATUSES:
                raise PoseBustersPreparedLigandDiagnosticError(
                    "observation case status in comparison is invalid"
                )
            object.__setattr__(self, field_name, value)
        compared = _positive_int(
            self.compared_real_atom_count,
            name="compared real atom count",
            allow_zero=True,
        )
        pseudo = _positive_int(
            self.pseudoatom_count,
            name="comparison pseudoatom count",
            allow_zero=True,
        )
        equal_count = _positive_int(
            self.bitwise_equal_expected_charge_count,
            name="bitwise-equal charge count",
            allow_zero=True,
        )
        if equal_count > compared:
            raise PoseBustersPreparedLigandDiagnosticError(
                "bitwise-equal charge count exceeds compared count"
            )
        mapping_equal = self.atom_mapping_equal
        if mapping_equal is not None:
            mapping_equal = bool(mapping_equal)
        all_equal = self.all_expected_charges_bitwise_equal
        if all_equal is not None:
            all_equal = bool(all_equal)
        if status in {"comparable", "not_comparable_mapping_difference"}:
            digest_2022 = _digest(
                self.rdkit_2022_mapping_sha256,
                name="RDKit 2022 mapping",
            )
            digest_2025 = _digest(
                self.rdkit_2025_mapping_sha256,
                name="RDKit 2025 mapping",
            )
        else:
            digest_2022 = self.rdkit_2022_mapping_sha256
            digest_2025 = self.rdkit_2025_mapping_sha256
            if digest_2022 or digest_2025:
                raise PoseBustersPreparedLigandDiagnosticError(
                    "non-evaluated comparison contains mapping digests"
                )
        if status == "comparable":
            delta = _validate_hex(
                self.maximum_absolute_expected_charge_delta_binary64_hex,
                name="maximum cross-version charge delta",
            )
            valid = (
                self.rdkit_2022_case_status == "evaluated"
                and self.rdkit_2025_case_status == "evaluated"
                and mapping_equal is True
                and compared > 0
                and all_equal is not None
                and all_equal == (equal_count == compared)
                and (
                    (all_equal and float.fromhex(delta) == 0.0)
                    or (not all_equal and float.fromhex(delta) > 0.0)
                )
            )
        elif status == "not_comparable_mapping_difference":
            delta = ""
            valid = (
                self.rdkit_2022_case_status == "evaluated"
                and self.rdkit_2025_case_status == "evaluated"
                and mapping_equal is False
                and compared == 0
                and pseudo == 0
                and equal_count == 0
                and all_equal is None
            )
        elif status == "not_comparable_diagnostic_failure":
            delta = ""
            valid = (
                "diagnostic_failure"
                in {self.rdkit_2022_case_status, self.rdkit_2025_case_status}
                and mapping_equal is None
                and compared == 0
                and pseudo == 0
                and equal_count == 0
                and all_equal is None
            )
        else:
            delta = ""
            expected_status = status
            valid = (
                self.rdkit_2022_case_status == expected_status
                and self.rdkit_2025_case_status == expected_status
                and mapping_equal is None
                and compared == 0
                and pseudo == 0
                and equal_count == 0
                and all_equal is None
            )
        if not valid:
            raise PoseBustersPreparedLigandDiagnosticError(
                "prepared-ligand comparison-case fields are inconsistent"
            )
        object.__setattr__(self, "case_id", case_id)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "disposition_code", disposition)
        object.__setattr__(self, "rdkit_2022_mapping_sha256", digest_2022)
        object.__setattr__(self, "rdkit_2025_mapping_sha256", digest_2025)
        object.__setattr__(self, "atom_mapping_equal", mapping_equal)
        object.__setattr__(self, "compared_real_atom_count", compared)
        object.__setattr__(self, "pseudoatom_count", pseudo)
        object.__setattr__(
            self,
            "bitwise_equal_expected_charge_count",
            equal_count,
        )
        object.__setattr__(
            self,
            "maximum_absolute_expected_charge_delta_binary64_hex",
            delta,
        )
        object.__setattr__(self, "all_expected_charges_bitwise_equal", all_equal)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "case_id": self.case_id,
            "status": self.status,
            "disposition_code": self.disposition_code,
            "rdkit_2022_case_status": self.rdkit_2022_case_status,
            "rdkit_2025_case_status": self.rdkit_2025_case_status,
            "rdkit_2022_mapping_sha256": self.rdkit_2022_mapping_sha256,
            "rdkit_2025_mapping_sha256": self.rdkit_2025_mapping_sha256,
            "atom_mapping_equal": self.atom_mapping_equal,
            "compared_real_atom_count": self.compared_real_atom_count,
            "pseudoatom_count": self.pseudoatom_count,
            "bitwise_equal_expected_charge_count": (
                self.bitwise_equal_expected_charge_count
            ),
            "maximum_absolute_expected_charge_delta_binary64_hex": (
                self.maximum_absolute_expected_charge_delta_binary64_hex
            ),
            "all_expected_charges_bitwise_equal": (
                self.all_expected_charges_bitwise_equal
            ),
        }


def _compare_case(
    case_2022: PoseBustersPreparedLigandCase,
    case_2025: PoseBustersPreparedLigandCase,
) -> PoseBustersPreparedLigandComparisonCase:
    if case_2022.case_id != case_2025.case_id:
        raise PoseBustersPreparedLigandDiagnosticError(
            "cross-version observation cases are misaligned"
        )
    if (
        case_2022.preparation_status != case_2025.preparation_status
        or case_2022.preparation_disposition_code
        != case_2025.preparation_disposition_code
        or case_2022.prepared_ligand_sha256 != case_2025.prepared_ligand_sha256
        or case_2022.prepared_ligand_size_bytes != case_2025.prepared_ligand_size_bytes
    ):
        raise PoseBustersPreparedLigandDiagnosticError(
            "cross-version observations do not share exact preparation inputs"
        )
    case_id = case_2022.case_id
    if "diagnostic_failure" in {case_2022.status, case_2025.status}:
        return PoseBustersPreparedLigandComparisonCase(
            case_id=case_id,
            status="not_comparable_diagnostic_failure",
            disposition_code="one_or_more_runtime_diagnostics_failed",
            rdkit_2022_case_status=case_2022.status,
            rdkit_2025_case_status=case_2025.status,
        )
    if case_2022.status != "evaluated" or case_2025.status != "evaluated":
        if case_2022.status != case_2025.status:
            raise PoseBustersPreparedLigandDiagnosticError(
                "non-evaluated cross-version statuses differ"
            )
        return PoseBustersPreparedLigandComparisonCase(
            case_id=case_id,
            status=case_2022.status,
            disposition_code="shared_non_evaluated_preparation_disposition",
            rdkit_2022_case_status=case_2022.status,
            rdkit_2025_case_status=case_2025.status,
        )
    if case_2022.embedded_smiles_sha256 != case_2025.embedded_smiles_sha256:
        raise PoseBustersPreparedLigandDiagnosticError(
            "cross-version observations use different embedded SMILES"
        )
    mapping_2022 = _case_mapping_sha256(case_2022)
    mapping_2025 = _case_mapping_sha256(case_2025)
    if mapping_2022 != mapping_2025:
        return PoseBustersPreparedLigandComparisonCase(
            case_id=case_id,
            status="not_comparable_mapping_difference",
            disposition_code="rdkit_runtime_atom_mapping_or_perception_differs",
            rdkit_2022_case_status=case_2022.status,
            rdkit_2025_case_status=case_2025.status,
            rdkit_2022_mapping_sha256=mapping_2022,
            rdkit_2025_mapping_sha256=mapping_2025,
            atom_mapping_equal=False,
        )
    charges_2022 = tuple(
        atom.expected_gasteiger_charge_binary64_hex
        for atom in case_2022.atom_rows
        if atom.expected_gasteiger_charge_binary64_hex is not None
    )
    charges_2025 = tuple(
        atom.expected_gasteiger_charge_binary64_hex
        for atom in case_2025.atom_rows
        if atom.expected_gasteiger_charge_binary64_hex is not None
    )
    if len(charges_2022) != len(charges_2025) or not charges_2022:
        raise PoseBustersPreparedLigandDiagnosticError(
            "cross-version expected-charge vectors are misaligned"
        )
    deltas = tuple(
        abs(float.fromhex(left) - float.fromhex(right))
        for left, right in zip(charges_2022, charges_2025, strict=True)
    )
    equal_count = sum(
        left == right for left, right in zip(charges_2022, charges_2025, strict=True)
    )
    return PoseBustersPreparedLigandComparisonCase(
        case_id=case_id,
        status="comparable",
        disposition_code="same_algorithm_cross_version_charge_vector_compared",
        rdkit_2022_case_status=case_2022.status,
        rdkit_2025_case_status=case_2025.status,
        rdkit_2022_mapping_sha256=mapping_2022,
        rdkit_2025_mapping_sha256=mapping_2025,
        atom_mapping_equal=True,
        compared_real_atom_count=len(charges_2022),
        pseudoatom_count=case_2022.pseudoatom_count,
        bitwise_equal_expected_charge_count=equal_count,
        maximum_absolute_expected_charge_delta_binary64_hex=max(deltas).hex(),
        all_expected_charges_bitwise_equal=equal_count == len(charges_2022),
    )


def _comparison_metrics(
    rows: Sequence[PoseBustersPreparedLigandComparisonCase],
) -> tuple[PoseBustersPreparedLigandMetric, ...]:
    denominator = len(rows)
    values = {
        "cross_version_bitwise_identical_case_rate": sum(
            row.all_expected_charges_bitwise_equal is True for row in rows
        ),
        "cross_version_comparable_case_rate": sum(
            row.status == "comparable" for row in rows
        ),
        "cross_version_mapping_equal_case_rate": sum(
            row.atom_mapping_equal is True for row in rows
        ),
    }
    return tuple(
        PoseBustersPreparedLigandMetric(
            metric_id=metric_id,
            numerator=numerator,
            denominator=denominator,
        )
        for metric_id, numerator in sorted(values.items())
    )


@dataclass(frozen=True, slots=True)
class PoseBustersPreparedLigandComparisonReceipt:
    observation_utc: str
    preparation_receipt_sha256: str
    preparation_receipt_file_sha256: str
    preparation_artifact_set_sha256: str
    rdkit_2022_observation_receipt_sha256: str
    rdkit_2022_observation_file_sha256: str
    rdkit_2022_runtime_identity: PoseBustersPreparedLigandRuntimeIdentity
    rdkit_2025_observation_receipt_sha256: str
    rdkit_2025_observation_file_sha256: str
    rdkit_2025_runtime_identity: PoseBustersPreparedLigandRuntimeIdentity
    implementation_source_members: tuple[tuple[str, str], ...]
    case_rows: tuple[PoseBustersPreparedLigandComparisonCase, ...]
    metrics: tuple[PoseBustersPreparedLigandMetric, ...]
    schema_id: str = POSEBUSTERS_PREPARED_LIGAND_COMPARISON_SCHEMA_ID
    configuration_sha256: str = POSEBUSTERS_PREPARED_LIGAND_CONFIGURATION_SHA256

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_PREPARED_LIGAND_COMPARISON_SCHEMA_ID:
            raise PoseBustersPreparedLigandDiagnosticError(
                "unsupported prepared-ligand comparison schema"
            )
        if (
            self.configuration_sha256
            != POSEBUSTERS_PREPARED_LIGAND_CONFIGURATION_SHA256
        ):
            raise PoseBustersPreparedLigandDiagnosticError(
                "prepared-ligand comparison configuration changed"
            )
        object.__setattr__(
            self,
            "observation_utc",
            _utc_timestamp(self.observation_utc),
        )
        for field_name in (
            "preparation_receipt_sha256",
            "preparation_receipt_file_sha256",
            "preparation_artifact_set_sha256",
            "rdkit_2022_observation_receipt_sha256",
            "rdkit_2022_observation_file_sha256",
            "rdkit_2025_observation_receipt_sha256",
            "rdkit_2025_observation_file_sha256",
        ):
            object.__setattr__(
                self,
                field_name,
                _digest(getattr(self, field_name), name=field_name.replace("_", " ")),
            )
        if (
            not isinstance(
                self.rdkit_2022_runtime_identity,
                PoseBustersPreparedLigandRuntimeIdentity,
            )
            or self.rdkit_2022_runtime_identity.rdkit_version != "2022.09.5"
            or not isinstance(
                self.rdkit_2025_runtime_identity,
                PoseBustersPreparedLigandRuntimeIdentity,
            )
            or self.rdkit_2025_runtime_identity.rdkit_version != "2025.09.6"
        ):
            raise PoseBustersPreparedLigandDiagnosticError(
                "comparison requires the exact frozen RDKit 2022 and 2025 runtimes"
            )
        sources = tuple(self.implementation_source_members)
        if (
            not sources
            or tuple(sorted(sources)) != sources
            or len({name for name, _digest_value in sources}) != len(sources)
        ):
            raise PoseBustersPreparedLigandDiagnosticError(
                "comparison source members are not canonical"
            )
        for name, digest in sources:
            _token(name, name="comparison source member")
            _digest(digest, name="comparison source member digest")
        rows = tuple(self.case_rows)
        if (
            not rows
            or tuple(row.case_id for row in rows)
            != tuple(sorted(row.case_id for row in rows))
            or len({row.case_id for row in rows}) != len(rows)
            or any(
                not isinstance(row, PoseBustersPreparedLigandComparisonCase)
                for row in rows
            )
        ):
            raise PoseBustersPreparedLigandDiagnosticError(
                "comparison case rows are not canonical"
            )
        metrics = tuple(self.metrics)
        if metrics != _comparison_metrics(rows):
            raise PoseBustersPreparedLigandDiagnosticError(
                "comparison metrics are inconsistent"
            )
        object.__setattr__(self, "implementation_source_members", sources)
        object.__setattr__(self, "case_rows", rows)
        object.__setattr__(self, "metrics", metrics)

    def _payload(self) -> dict[str, Any]:
        comparable = tuple(row for row in self.case_rows if row.status == "comparable")
        compared_atoms = sum(row.compared_real_atom_count for row in comparable)
        bitwise_equal_atoms = sum(
            row.bitwise_equal_expected_charge_count for row in comparable
        )
        maximum_delta = max(
            (
                float.fromhex(row.maximum_absolute_expected_charge_delta_binary64_hex)
                for row in comparable
            ),
            default=0.0,
        )
        source_members = dict(self.implementation_source_members)
        version_sensitivity = (
            any(
                row.status == "not_comparable_mapping_difference"
                for row in self.case_rows
            )
            or bitwise_equal_atoms != compared_atoms
        )
        return {
            "schema_id": self.schema_id,
            "observation_utc": self.observation_utc,
            "preparation_receipt_sha256": self.preparation_receipt_sha256,
            "preparation_receipt_file_sha256": (self.preparation_receipt_file_sha256),
            "preparation_artifact_set_sha256": (self.preparation_artifact_set_sha256),
            "rdkit_2022_observation_receipt_sha256": (
                self.rdkit_2022_observation_receipt_sha256
            ),
            "rdkit_2022_observation_file_sha256": (
                self.rdkit_2022_observation_file_sha256
            ),
            "rdkit_2022_runtime_identity": (self.rdkit_2022_runtime_identity.to_dict()),
            "rdkit_2022_runtime_identity_sha256": (
                self.rdkit_2022_runtime_identity.fingerprint_sha256
            ),
            "rdkit_2025_observation_receipt_sha256": (
                self.rdkit_2025_observation_receipt_sha256
            ),
            "rdkit_2025_observation_file_sha256": (
                self.rdkit_2025_observation_file_sha256
            ),
            "rdkit_2025_runtime_identity": (self.rdkit_2025_runtime_identity.to_dict()),
            "rdkit_2025_runtime_identity_sha256": (
                self.rdkit_2025_runtime_identity.fingerprint_sha256
            ),
            "implementation_source_members": source_members,
            "implementation_source_sha256": _canonical_sha256(source_members),
            "configuration": POSEBUSTERS_PREPARED_LIGAND_CONFIGURATION,
            "configuration_sha256": self.configuration_sha256,
            "all_case_denominator": len(self.case_rows),
            "comparable_case_count": len(comparable),
            "mapping_difference_case_count": sum(
                row.status == "not_comparable_mapping_difference"
                for row in self.case_rows
            ),
            "diagnostic_failure_case_count": sum(
                row.status == "not_comparable_diagnostic_failure"
                for row in self.case_rows
            ),
            "compared_real_atom_count": compared_atoms,
            "bitwise_equal_expected_charge_count": bitwise_equal_atoms,
            "maximum_absolute_expected_charge_delta_binary64_hex": (
                maximum_delta.hex()
            ),
            "version_sensitivity_detected": version_sensitivity,
            "case_rows": [row.to_dict() for row in self.case_rows],
            "metrics": [row.to_dict() for row in self.metrics],
            "same_algorithm_cross_version_comparison_performed": bool(comparable),
            "independent_charge_implementation_comparison_performed": False,
            "independent_ad4_type_implementation_comparison_performed": False,
            "runtime_network_used": False,
            "benchmark_executed": False,
            "scientific_blockers": list(
                POSEBUSTERS_PREPARED_LIGAND_SCIENTIFIC_BLOCKERS
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
        return _atomic_write_new(output_path, self.to_dict())


def _load_observation_with_file_identity(
    path: str | os.PathLike[str],
    expected_receipt_sha256: str,
) -> tuple[PoseBustersPreparedLigandObservationReceipt, str]:
    raw, source = _read_canonical_receipt(
        path,
        expected_receipt_sha256=expected_receipt_sha256,
        expected_schema_id=POSEBUSTERS_PREPARED_LIGAND_OBSERVATION_SCHEMA_ID,
    )
    return _observation_from_raw(raw), _hash_bytes(source)


def _build_comparison(
    rdkit_2022_observation_path: str | os.PathLike[str],
    rdkit_2025_observation_path: str | os.PathLike[str],
    *,
    expected_rdkit_2022_observation_sha256: str,
    expected_rdkit_2025_observation_sha256: str,
    observation_utc: str,
) -> PoseBustersPreparedLigandComparisonReceipt:
    observation_2022, file_sha_2022 = _load_observation_with_file_identity(
        rdkit_2022_observation_path,
        expected_rdkit_2022_observation_sha256,
    )
    observation_2025, file_sha_2025 = _load_observation_with_file_identity(
        rdkit_2025_observation_path,
        expected_rdkit_2025_observation_sha256,
    )
    if (
        observation_2022.runtime_identity.rdkit_version != "2022.09.5"
        or observation_2025.runtime_identity.rdkit_version != "2025.09.6"
    ):
        raise PoseBustersPreparedLigandDiagnosticError(
            "comparison observation paths are not the frozen RDKit version pair"
        )
    shared_2022 = (
        observation_2022.preparation_receipt_sha256,
        observation_2022.preparation_receipt_file_sha256,
        observation_2022.preparation_artifact_set_sha256,
        observation_2022.preparation_runtime_identity_sha256,
    )
    shared_2025 = (
        observation_2025.preparation_receipt_sha256,
        observation_2025.preparation_receipt_file_sha256,
        observation_2025.preparation_artifact_set_sha256,
        observation_2025.preparation_runtime_identity_sha256,
    )
    if shared_2022 != shared_2025:
        raise PoseBustersPreparedLigandDiagnosticError(
            "cross-version observations do not share exact preparation provenance"
        )
    if tuple(row.case_id for row in observation_2022.case_rows) != tuple(
        row.case_id for row in observation_2025.case_rows
    ):
        raise PoseBustersPreparedLigandDiagnosticError(
            "cross-version observation denominators differ"
        )
    rows = tuple(
        _compare_case(left, right)
        for left, right in zip(
            observation_2022.case_rows,
            observation_2025.case_rows,
            strict=True,
        )
    )
    sources = _implementation_source_members()
    return PoseBustersPreparedLigandComparisonReceipt(
        observation_utc=observation_utc,
        preparation_receipt_sha256=observation_2022.preparation_receipt_sha256,
        preparation_receipt_file_sha256=(
            observation_2022.preparation_receipt_file_sha256
        ),
        preparation_artifact_set_sha256=(
            observation_2022.preparation_artifact_set_sha256
        ),
        rdkit_2022_observation_receipt_sha256=(observation_2022.fingerprint_sha256),
        rdkit_2022_observation_file_sha256=file_sha_2022,
        rdkit_2022_runtime_identity=observation_2022.runtime_identity,
        rdkit_2025_observation_receipt_sha256=(observation_2025.fingerprint_sha256),
        rdkit_2025_observation_file_sha256=file_sha_2025,
        rdkit_2025_runtime_identity=observation_2025.runtime_identity,
        implementation_source_members=sources,
        case_rows=rows,
        metrics=_comparison_metrics(rows),
    )


def materialize_posebusters_prepared_ligand_comparison(
    rdkit_2022_observation_path: str | os.PathLike[str],
    rdkit_2025_observation_path: str | os.PathLike[str],
    *,
    expected_rdkit_2022_observation_sha256: str,
    expected_rdkit_2025_observation_sha256: str,
    observation_utc: str,
) -> PoseBustersPreparedLigandComparisonReceipt:
    return _build_comparison(
        rdkit_2022_observation_path,
        rdkit_2025_observation_path,
        expected_rdkit_2022_observation_sha256=(expected_rdkit_2022_observation_sha256),
        expected_rdkit_2025_observation_sha256=(expected_rdkit_2025_observation_sha256),
        observation_utc=observation_utc,
    )


def _comparison_case_from_raw(
    raw: object,
) -> PoseBustersPreparedLigandComparisonCase:
    if not isinstance(raw, dict):
        raise PoseBustersPreparedLigandDiagnosticError(
            "prepared-ligand comparison case must be an object"
        )
    row = PoseBustersPreparedLigandComparisonCase(
        case_id=raw.get("case_id"),
        status=raw.get("status"),
        disposition_code=raw.get("disposition_code"),
        rdkit_2022_case_status=raw.get("rdkit_2022_case_status"),
        rdkit_2025_case_status=raw.get("rdkit_2025_case_status"),
        rdkit_2022_mapping_sha256=raw.get("rdkit_2022_mapping_sha256"),
        rdkit_2025_mapping_sha256=raw.get("rdkit_2025_mapping_sha256"),
        atom_mapping_equal=raw.get("atom_mapping_equal"),
        compared_real_atom_count=raw.get("compared_real_atom_count"),
        pseudoatom_count=raw.get("pseudoatom_count"),
        bitwise_equal_expected_charge_count=raw.get(
            "bitwise_equal_expected_charge_count"
        ),
        maximum_absolute_expected_charge_delta_binary64_hex=raw.get(
            "maximum_absolute_expected_charge_delta_binary64_hex"
        ),
        all_expected_charges_bitwise_equal=raw.get(
            "all_expected_charges_bitwise_equal"
        ),
        schema_id=raw.get("schema_id"),
    )
    if row.to_dict() != raw:
        raise PoseBustersPreparedLigandDiagnosticError(
            "prepared-ligand comparison case contains unsupported fields"
        )
    return row


def _comparison_from_raw(
    raw: dict[str, Any],
) -> PoseBustersPreparedLigandComparisonReceipt:
    raw_sources = raw.get("implementation_source_members")
    raw_cases = raw.get("case_rows")
    raw_metrics = raw.get("metrics")
    if (
        not isinstance(raw_sources, dict)
        or not isinstance(raw_cases, list)
        or not isinstance(raw_metrics, list)
    ):
        raise PoseBustersPreparedLigandDiagnosticError(
            "prepared-ligand comparison collections are invalid"
        )
    if tuple(sorted(raw_sources.items())) != _implementation_source_members():
        raise PoseBustersPreparedLigandDiagnosticError(
            "prepared-ligand comparison source identity is stale"
        )
    receipt = PoseBustersPreparedLigandComparisonReceipt(
        observation_utc=raw.get("observation_utc"),
        preparation_receipt_sha256=raw.get("preparation_receipt_sha256"),
        preparation_receipt_file_sha256=raw.get("preparation_receipt_file_sha256"),
        preparation_artifact_set_sha256=raw.get("preparation_artifact_set_sha256"),
        rdkit_2022_observation_receipt_sha256=raw.get(
            "rdkit_2022_observation_receipt_sha256"
        ),
        rdkit_2022_observation_file_sha256=raw.get(
            "rdkit_2022_observation_file_sha256"
        ),
        rdkit_2022_runtime_identity=_runtime_from_raw(
            raw.get("rdkit_2022_runtime_identity")
        ),
        rdkit_2025_observation_receipt_sha256=raw.get(
            "rdkit_2025_observation_receipt_sha256"
        ),
        rdkit_2025_observation_file_sha256=raw.get(
            "rdkit_2025_observation_file_sha256"
        ),
        rdkit_2025_runtime_identity=_runtime_from_raw(
            raw.get("rdkit_2025_runtime_identity")
        ),
        implementation_source_members=tuple(sorted(raw_sources.items())),
        case_rows=tuple(_comparison_case_from_raw(row) for row in raw_cases),
        metrics=tuple(_metric_from_raw(row) for row in raw_metrics),
        schema_id=raw.get("schema_id"),
        configuration_sha256=raw.get("configuration_sha256"),
    )
    if receipt.to_dict() != raw:
        raise PoseBustersPreparedLigandDiagnosticError(
            "prepared-ligand comparison receipt is internally inconsistent"
        )
    return receipt


def load_posebusters_prepared_ligand_comparison_receipt(
    receipt_path: str | os.PathLike[str],
    *,
    expected_receipt_sha256: str,
) -> PoseBustersPreparedLigandComparisonReceipt:
    raw, _source = _read_canonical_receipt(
        receipt_path,
        expected_receipt_sha256=expected_receipt_sha256,
        expected_schema_id=POSEBUSTERS_PREPARED_LIGAND_COMPARISON_SCHEMA_ID,
    )
    return _comparison_from_raw(raw)


def verify_posebusters_prepared_ligand_comparison_receipt(
    receipt_path: str | os.PathLike[str],
    rdkit_2022_observation_path: str | os.PathLike[str],
    rdkit_2025_observation_path: str | os.PathLike[str],
    *,
    expected_receipt_sha256: str,
    expected_rdkit_2022_observation_sha256: str,
    expected_rdkit_2025_observation_sha256: str,
) -> PoseBustersPreparedLigandComparisonReceipt:
    raw, source = _read_canonical_receipt(
        receipt_path,
        expected_receipt_sha256=expected_receipt_sha256,
        expected_schema_id=POSEBUSTERS_PREPARED_LIGAND_COMPARISON_SCHEMA_ID,
    )
    loaded = _comparison_from_raw(raw)
    expected = _build_comparison(
        rdkit_2022_observation_path,
        rdkit_2025_observation_path,
        expected_rdkit_2022_observation_sha256=(expected_rdkit_2022_observation_sha256),
        expected_rdkit_2025_observation_sha256=(expected_rdkit_2025_observation_sha256),
        observation_utc=loaded.observation_utc,
    )
    if source != _canonical_bytes(expected.to_dict()) + b"\n":
        raise PoseBustersPreparedLigandDiagnosticError(
            "prepared-ligand comparison failed exact source-tree reexecution"
        )
    return expected


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2-posebusters-prepared-ligand-diagnostic",
        description=(
            "Create prepared ligand Gasteiger charge and atom-type diagnostics "
            "without claiming an independent scientific oracle."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("observe", "verify-observation"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--preparation-receipt", required=True)
        subparser.add_argument("--preparation-artifact-root", required=True)
        subparser.add_argument(
            "--expected-preparation-receipt-sha256",
            required=True,
        )
    observe = subparsers.choices["observe"]
    observe.add_argument("--observation-utc", required=True)
    observe.add_argument("--output", required=True)
    verify_observation = subparsers.choices["verify-observation"]
    verify_observation.add_argument("--observation-receipt", required=True)
    verify_observation.add_argument(
        "--expected-observation-receipt-sha256",
        required=True,
    )
    for command in ("compare", "verify-comparison"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--rdkit-2022-observation", required=True)
        subparser.add_argument(
            "--expected-rdkit-2022-observation-sha256",
            required=True,
        )
        subparser.add_argument("--rdkit-2025-observation", required=True)
        subparser.add_argument(
            "--expected-rdkit-2025-observation-sha256",
            required=True,
        )
    compare = subparsers.choices["compare"]
    compare.add_argument("--observation-utc", required=True)
    compare.add_argument("--output", required=True)
    verify_comparison = subparsers.choices["verify-comparison"]
    verify_comparison.add_argument("--comparison-receipt", required=True)
    verify_comparison.add_argument(
        "--expected-comparison-receipt-sha256",
        required=True,
    )
    return parser


def _observation_summary(
    receipt: PoseBustersPreparedLigandObservationReceipt,
) -> dict[str, Any]:
    payload = receipt.to_dict()
    return {
        "receipt_sha256": receipt.fingerprint_sha256,
        "rdkit_version": receipt.runtime_identity.rdkit_version,
        "all_case_denominator": len(receipt.case_rows),
        "evaluated_case_count": payload["evaluated_case_count"],
        "diagnostic_failure_case_count": payload["diagnostic_failure_case_count"],
        "real_pdbqt_atom_count": payload["real_pdbqt_atom_count"],
        "macrocycle_pseudoatom_count": payload["macrocycle_pseudoatom_count"],
        "maximum_absolute_charge_delta_binary64_hex": payload[
            "maximum_absolute_charge_delta_binary64_hex"
        ],
        "independent_charge_oracle_executed": False,
        "claim_safe": False,
    }


def _comparison_summary(
    receipt: PoseBustersPreparedLigandComparisonReceipt,
) -> dict[str, Any]:
    payload = receipt.to_dict()
    return {
        "receipt_sha256": receipt.fingerprint_sha256,
        "all_case_denominator": len(receipt.case_rows),
        "comparable_case_count": payload["comparable_case_count"],
        "compared_real_atom_count": payload["compared_real_atom_count"],
        "bitwise_equal_expected_charge_count": payload[
            "bitwise_equal_expected_charge_count"
        ],
        "maximum_absolute_expected_charge_delta_binary64_hex": payload[
            "maximum_absolute_expected_charge_delta_binary64_hex"
        ],
        "version_sensitivity_detected": payload["version_sensitivity_detected"],
        "independent_charge_implementation_comparison_performed": False,
        "claim_safe": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "observe":
        if Path(args.output).exists():
            raise PoseBustersPreparedLigandDiagnosticError(
                "prepared-ligand observation output already exists"
            )
        receipt: (
            PoseBustersPreparedLigandObservationReceipt
            | PoseBustersPreparedLigandComparisonReceipt
        ) = materialize_posebusters_prepared_ligand_observation(
            args.preparation_receipt,
            args.preparation_artifact_root,
            expected_preparation_receipt_sha256=(
                args.expected_preparation_receipt_sha256
            ),
            observation_utc=args.observation_utc,
        )
        receipt.write_json(args.output)
        summary = _observation_summary(receipt)
    elif args.command == "verify-observation":
        receipt = verify_posebusters_prepared_ligand_observation_receipt(
            args.observation_receipt,
            args.preparation_receipt,
            args.preparation_artifact_root,
            expected_receipt_sha256=(args.expected_observation_receipt_sha256),
            expected_preparation_receipt_sha256=(
                args.expected_preparation_receipt_sha256
            ),
        )
        summary = _observation_summary(receipt)
    elif args.command == "compare":
        if Path(args.output).exists():
            raise PoseBustersPreparedLigandDiagnosticError(
                "prepared-ligand comparison output already exists"
            )
        receipt = materialize_posebusters_prepared_ligand_comparison(
            args.rdkit_2022_observation,
            args.rdkit_2025_observation,
            expected_rdkit_2022_observation_sha256=(
                args.expected_rdkit_2022_observation_sha256
            ),
            expected_rdkit_2025_observation_sha256=(
                args.expected_rdkit_2025_observation_sha256
            ),
            observation_utc=args.observation_utc,
        )
        receipt.write_json(args.output)
        summary = _comparison_summary(receipt)
    else:
        receipt = verify_posebusters_prepared_ligand_comparison_receipt(
            args.comparison_receipt,
            args.rdkit_2022_observation,
            args.rdkit_2025_observation,
            expected_receipt_sha256=(args.expected_comparison_receipt_sha256),
            expected_rdkit_2022_observation_sha256=(
                args.expected_rdkit_2022_observation_sha256
            ),
            expected_rdkit_2025_observation_sha256=(
                args.expected_rdkit_2025_observation_sha256
            ),
        )
        summary = _comparison_summary(receipt)
    print(json.dumps(summary, sort_keys=True))
    return 0


__all__ = [
    "POSEBUSTERS_PREPARED_LIGAND_ATOM_SCHEMA_ID",
    "POSEBUSTERS_PREPARED_LIGAND_CASE_SCHEMA_ID",
    "POSEBUSTERS_PREPARED_LIGAND_CHARGE_TOLERANCE",
    "POSEBUSTERS_PREPARED_LIGAND_COMPARISON_CASE_SCHEMA_ID",
    "POSEBUSTERS_PREPARED_LIGAND_COMPARISON_SCHEMA_ID",
    "POSEBUSTERS_PREPARED_LIGAND_CONFIGURATION",
    "POSEBUSTERS_PREPARED_LIGAND_CONFIGURATION_SHA256",
    "POSEBUSTERS_PREPARED_LIGAND_METRIC_SCHEMA_ID",
    "POSEBUSTERS_PREPARED_LIGAND_OBSERVATION_SCHEMA_ID",
    "POSEBUSTERS_PREPARED_LIGAND_RUNTIME_PAYLOAD_SCHEMA_ID",
    "POSEBUSTERS_PREPARED_LIGAND_RUNTIME_SCHEMA_ID",
    "POSEBUSTERS_PREPARED_LIGAND_SCIENTIFIC_BLOCKERS",
    "POSEBUSTERS_PREPARED_LIGAND_SUPPORTED_RDKIT_VERSIONS",
    "PoseBustersPreparedLigandAtom",
    "PoseBustersPreparedLigandCase",
    "PoseBustersPreparedLigandComparisonCase",
    "PoseBustersPreparedLigandComparisonReceipt",
    "PoseBustersPreparedLigandDiagnosticError",
    "PoseBustersPreparedLigandMetric",
    "PoseBustersPreparedLigandObservationReceipt",
    "PoseBustersPreparedLigandRuntimeIdentity",
    "PoseBustersPreparedLigandRuntimePayload",
    "load_posebusters_prepared_ligand_comparison_receipt",
    "load_posebusters_prepared_ligand_observation_receipt",
    "main",
    "materialize_posebusters_prepared_ligand_comparison",
    "materialize_posebusters_prepared_ligand_observation",
    "verify_posebusters_prepared_ligand_comparison_receipt",
    "verify_posebusters_prepared_ligand_observation_receipt",
]


if __name__ == "__main__":
    raise SystemExit(main())
