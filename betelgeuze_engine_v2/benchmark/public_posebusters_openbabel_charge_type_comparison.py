"""Independent Open Babel charge and PDBQT atom-type comparison.

This module consumes the exact failure-inclusive PoseBusters external
preparation receipt and its private ligand PDBQT artifacts.  For every
strictly prepared ligand it parses the embedded Meeko SMILES mapping, asks a
separately distributed Open Babel implementation to calculate Gasteiger
charges, and asks Open Babel's PDBQT writer to assign AutoDock atom types.

The comparison is descriptive.  It has no preregistered accuracy threshold,
does not establish either implementation as a scientific oracle, and does not
promote a docking or chemistry-validation claim.  All 308 upstream rows and
all comparison failures remain in the canonical private receipt.
"""

from __future__ import annotations

from collections import Counter, defaultdict
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
    POSEBUSTERS_EXTERNAL_PREPARATION_MAX_DEPENDENCY_BYTES,
    POSEBUSTERS_EXTERNAL_PREPARATION_MAX_DEPENDENCY_FILE_BYTES,
    POSEBUSTERS_EXTERNAL_PREPARATION_MAX_DEPENDENCY_FILES,
    PoseBustersExternalPreparationError,
    _hash_regular_file,
)
from .public_posebusters_intake import _read_exact_regular_file
from .public_posebusters_prepared_ligand_diagnostic import (
    POSEBUSTERS_PREPARED_LIGAND_CHARGE_TOLERANCE,
    POSEBUSTERS_PREPARED_LIGAND_MAX_ATOMS_PER_CASE,
    _ParsedLigand,
    _parse_ligand_pdbqt,
)
from .public_posebusters_vina_execution import (
    PoseBustersVinaExecutionError,
    _PreparedCaseView,
    _case_id,
    _digest,
    _load_preparation_receipt,
)


POSEBUSTERS_OPENBABEL_RUNTIME_PAYLOAD_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_openbabel_runtime_payload/1.0.0"
)
POSEBUSTERS_OPENBABEL_RUNTIME_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_openbabel_runtime/1.0.0"
)
POSEBUSTERS_OPENBABEL_ATOM_COMPARISON_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_openbabel_atom_comparison/1.0.0"
)
POSEBUSTERS_OPENBABEL_CASE_COMPARISON_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_openbabel_case_comparison/1.0.0"
)
POSEBUSTERS_OPENBABEL_METRIC_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_openbabel_metric/1.0.0"
)
POSEBUSTERS_OPENBABEL_COMPARISON_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_openbabel_comparison/1.0.0"
)

POSEBUSTERS_OPENBABEL_VERSION = "3.2.1"
POSEBUSTERS_OPENBABEL_SOURCE_COMMIT = (
    "0e94434fa75c9f61095023e3c12e0d5f2ac035ff"
)
POSEBUSTERS_OPENBABEL_WHEEL_FILENAME = (
    "openbabel-3.2.1-cp310-cp310-manylinux2014_x86_64."
    "manylinux_2_17_x86_64.whl"
)
POSEBUSTERS_OPENBABEL_WHEEL_SHA256 = (
    "ca6345ca6cc66522208c45355a90472d657be78dec7706757d477bfb0c105413"
)
POSEBUSTERS_OPENBABEL_PYPI_URL = (
    "https://pypi.org/project/openbabel/3.2.1/"
)
POSEBUSTERS_OPENBABEL_RELEASE_URL = (
    "https://github.com/openbabel/openbabel/releases/tag/openbabel-3-2-1"
)
POSEBUSTERS_OPENBABEL_MAX_RECEIPT_BYTES = 16 * 1024 * 1024
POSEBUSTERS_OPENBABEL_CONFIDENCE_LEVEL = 0.95
POSEBUSTERS_OPENBABEL_Z = 1.959963984540054

POSEBUSTERS_OPENBABEL_CONFIGURATION = {
    "charge_comparison": {
        "acceptance_threshold": None,
        "algorithm": "openbabel_obchargemodel_gasteiger",
        "interpretation": "descriptive_cross_implementation_difference",
        "meeko_charge_source": "prepared_ligand_pdbqt_three_decimal_field",
        "openbabel_charge_source": "full_precision_partial_charge",
    },
    "embedded_mapping_sources": ["REMARK_SMILES_IDX", "REMARK_H_PARENT"],
    "hydrogen_policy": {
        "meeko": "prepared_pdbqt_mapping",
        "openbabel": "delete_nonpolar_hydrogens_and_merge_charge_to_parent",
        "retained_hydrogen_mapping": "parent_then_openbabel_atom_order",
    },
    "input_chemistry": "exact_embedded_meeko_smiles",
    "openbabel_release": {
        "distribution": "openbabel",
        "source_commit": POSEBUSTERS_OPENBABEL_SOURCE_COMMIT,
        "version": POSEBUSTERS_OPENBABEL_VERSION,
        "wheel_filename": POSEBUSTERS_OPENBABEL_WHEEL_FILENAME,
        "wheel_sha256": POSEBUSTERS_OPENBABEL_WHEEL_SHA256,
    },
    "pdbqt_type_source": "openbabel_pdbqt_writer",
    "pdbqt_writer_options": ["c", "p", "r"],
    "pseudoatom_policy": "meeko_G0_rows_retained_but_excluded_from_openbabel_comparison",
    "runtime_networking": False,
}
POSEBUSTERS_OPENBABEL_CONFIGURATION_SHA256 = _canonical_sha256(
    POSEBUSTERS_OPENBABEL_CONFIGURATION
)

POSEBUSTERS_OPENBABEL_SCIENTIFIC_BLOCKERS = (
    "openbabel_gasteiger_is_an_independent_implementation_comparison_not_a_quantum_charge_oracle",
    "no_preregistered_cross_implementation_charge_accuracy_threshold",
    "embedded_smiles_to_source_sdf_chemistry_equivalence_not_independently_verified",
    "openbabel_and_meeko_ad4_type_differences_have_not_been_scientifically_dispositioned",
    "receptor_partial_charges_and_atom_types_not_audited",
    "prepared_subset_is_not_representative_of_the_308_case_public_corpus",
    "unsupported_metals_cofactors_and_chemistry_remain_abstentions",
    "transitive_system_native_libraries_not_individually_fingerprinted",
    "second_cpu_host_reproduction_missing",
    "independent_scientific_review_missing",
)

_DEPENDENCY_METADATA_EXCLUSIONS = {
    "direct_url.json",
    "INSTALLER",
    "RECORD",
    "REQUESTED",
}
_MEEKO_CHARGE_PATTERN = re.compile(r"-?[0-9]+\.[0-9]{3}\Z")
_OPENBABEL_CHARGE_PATTERN = re.compile(r"[+-]?[0-9]+\.[0-9]{3}\Z")
_ATOM_TYPE_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9]{0,7}\Z")
_CASE_STATUSES = {
    "abstain_chemistry_scope",
    "blocked_preparation_failure",
    "blocked_upstream_failure",
    "comparison_failure",
    "evaluated",
}
_ATOM_ROLES = {
    "macrocycle_closure_pseudoatom",
    "retained_polar_hydrogen",
    "source_atom",
}


class PoseBustersOpenBabelComparisonError(ValueError):
    """Open Babel runtime, input, comparison, or receipt is invalid."""


def _hash_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _bounded_ascii(value: object, *, name: str, maximum: int = 512) -> str:
    if not isinstance(value, str):
        raise PoseBustersOpenBabelComparisonError(f"{name} must be text")
    result = value.strip()
    if (
        not result
        or len(result) > maximum
        or not result.isascii()
        or any(ord(character) < 32 or ord(character) > 126 for character in result)
    ):
        raise PoseBustersOpenBabelComparisonError(
            f"{name} must be bounded printable ASCII"
        )
    return result


def _canonical_float_hex(value: object, *, name: str) -> str:
    if not isinstance(value, str):
        raise PoseBustersOpenBabelComparisonError(f"{name} must be hexadecimal")
    try:
        number = float.fromhex(value)
    except ValueError as exc:
        raise PoseBustersOpenBabelComparisonError(
            f"{name} must be canonical binary64 hexadecimal"
        ) from exc
    if not math.isfinite(number) or number.hex() != value:
        raise PoseBustersOpenBabelComparisonError(
            f"{name} must be canonical finite binary64 hexadecimal"
        )
    return value


def _utc_timestamp(value: object) -> str:
    text = _bounded_ascii(value, name="observation UTC", maximum=40)
    if not text.endswith("Z"):
        raise PoseBustersOpenBabelComparisonError(
            "observation UTC must end in Z"
        )
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as exc:
        raise PoseBustersOpenBabelComparisonError(
            "observation UTC is invalid"
        ) from exc
    if parsed.tzinfo != timezone.utc:
        raise PoseBustersOpenBabelComparisonError(
            "observation UTC must use UTC"
        )
    return parsed.isoformat(timespec="seconds").replace("+00:00", "Z")


def _normalized_error(error: BaseException) -> bytes:
    text = " ".join(str(error).split())
    if not text:
        text = type(error).__name__
    return text[:4096].encode("utf-8", errors="backslashreplace")


def _hash_regular(path: Path, *, maximum_bytes: int) -> tuple[str, int, int]:
    try:
        return _hash_regular_file(path, maximum_bytes=maximum_bytes)
    except PoseBustersExternalPreparationError as exc:
        raise PoseBustersOpenBabelComparisonError(
            "runtime payload could not be hashed as a bounded regular file"
        ) from exc


def _atomic_write_new(
    output_path: str | os.PathLike[str],
    payload: Mapping[str, Any],
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    source = _canonical_bytes(dict(payload)) + b"\n"
    if len(source) > POSEBUSTERS_OPENBABEL_MAX_RECEIPT_BYTES:
        raise PoseBustersOpenBabelComparisonError(
            "Open Babel comparison receipt exceeds its size bound"
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
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel comparison receipt output already exists"
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
        raise PoseBustersOpenBabelComparisonError(
            "metric numerator exceeds denominator"
        )
    fraction = successes / total
    z2 = POSEBUSTERS_OPENBABEL_Z**2
    denominator = 1.0 + z2 / total
    center = (fraction + z2 / (2.0 * total)) / denominator
    margin = (
        POSEBUSTERS_OPENBABEL_Z
        * math.sqrt(fraction * (1.0 - fraction) / total + z2 / (4.0 * total**2))
        / denominator
    )
    return max(0.0, center - margin).hex(), min(1.0, center + margin).hex()


@dataclass(frozen=True, slots=True)
class PoseBustersOpenBabelRuntimePayload:
    distribution_name: str
    distribution_version: str
    payload_sha256: str
    payload_file_count: int
    payload_size_bytes: int
    schema_id: str = POSEBUSTERS_OPENBABEL_RUNTIME_PAYLOAD_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_OPENBABEL_RUNTIME_PAYLOAD_SCHEMA_ID:
            raise PoseBustersOpenBabelComparisonError(
                "unsupported Open Babel runtime-payload schema"
            )
        name = _bounded_ascii(
            self.distribution_name,
            name="Open Babel distribution name",
            maximum=128,
        )
        version = _bounded_ascii(
            self.distribution_version,
            name="Open Babel distribution version",
            maximum=128,
        )
        if name.lower() != "openbabel" or version != POSEBUSTERS_OPENBABEL_VERSION:
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel distribution pin is invalid"
            )
        object.__setattr__(self, "distribution_name", name)
        object.__setattr__(self, "distribution_version", version)
        object.__setattr__(
            self,
            "payload_sha256",
            _digest(self.payload_sha256, name="Open Babel distribution payload"),
        )
        object.__setattr__(
            self,
            "payload_file_count",
            _positive_int(self.payload_file_count, name="payload file count"),
        )
        object.__setattr__(
            self,
            "payload_size_bytes",
            _positive_int(self.payload_size_bytes, name="payload size"),
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
class PoseBustersOpenBabelRuntimeIdentity:
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
    openbabel_release_version: str
    openbabel_source_commit: str
    wheel_filename: str
    wheel_sha256: str
    wheel_size_bytes: int
    distribution_payload: PoseBustersOpenBabelRuntimePayload
    charge_model_id: str
    schema_id: str = POSEBUSTERS_OPENBABEL_RUNTIME_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_OPENBABEL_RUNTIME_SCHEMA_ID:
            raise PoseBustersOpenBabelComparisonError(
                "unsupported Open Babel runtime schema"
            )
        for field_name in (
            "python_implementation",
            "python_version",
            "python_cache_tag",
            "platform_system",
            "platform_machine",
            "filesystem_encoding",
            "charge_model_id",
        ):
            object.__setattr__(
                self,
                field_name,
                _bounded_ascii(
                    getattr(self, field_name),
                    name=field_name.replace("_", " "),
                    maximum=256,
                ),
            )
        for field_name in ("libc_name", "libc_version"):
            value = str(getattr(self, field_name)).strip()
            if len(value) > 128 or not value.isascii():
                raise PoseBustersOpenBabelComparisonError(
                    f"{field_name} must be bounded ASCII"
                )
            object.__setattr__(self, field_name, value)
        if (
            self.python_implementation != "CPython"
            or self.python_cache_tag != "cpython-310"
            or self.platform_system != "Linux"
            or self.platform_machine not in {"x86_64", "AMD64"}
        ):
            raise PoseBustersOpenBabelComparisonError(
                "runtime does not match the frozen CPython 3.10 Linux x86-64 wheel"
            )
        if self.openbabel_release_version != POSEBUSTERS_OPENBABEL_VERSION:
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel runtime version is not frozen"
            )
        if self.openbabel_source_commit != POSEBUSTERS_OPENBABEL_SOURCE_COMMIT:
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel source commit is not frozen"
            )
        if self.wheel_filename != POSEBUSTERS_OPENBABEL_WHEEL_FILENAME:
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel wheel filename is not frozen"
            )
        object.__setattr__(
            self,
            "wheel_sha256",
            _digest(self.wheel_sha256, name="Open Babel wheel"),
        )
        if self.wheel_sha256 != POSEBUSTERS_OPENBABEL_WHEEL_SHA256:
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel wheel digest is not frozen"
            )
        object.__setattr__(
            self,
            "wheel_size_bytes",
            _positive_int(self.wheel_size_bytes, name="Open Babel wheel size"),
        )
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
        if not isinstance(
            self.distribution_payload,
            PoseBustersOpenBabelRuntimePayload,
        ):
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel distribution payload is missing"
            )
        if self.charge_model_id != "gasteiger":
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel charge model is not frozen"
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
            "openbabel_release_version": self.openbabel_release_version,
            "openbabel_source_commit": self.openbabel_source_commit,
            "openbabel_release_url": POSEBUSTERS_OPENBABEL_RELEASE_URL,
            "wheel_filename": self.wheel_filename,
            "wheel_sha256": self.wheel_sha256,
            "wheel_size_bytes": self.wheel_size_bytes,
            "wheel_pypi_url": POSEBUSTERS_OPENBABEL_PYPI_URL,
            "wheel_pypi_trusted_publishing_attestation_claimed_by_registry": True,
            "wheel_pypi_attestation_cryptographically_reverified_here": False,
            "distribution_payload": self.distribution_payload.to_dict(),
            "charge_model_id": self.charge_model_id,
            "smiles_reader_available": True,
            "pdbqt_writer_available": True,
            "transitive_system_native_libraries_individually_fingerprinted": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


def _distribution_payload(
    distribution: importlib.metadata.Distribution,
) -> PoseBustersOpenBabelRuntimePayload:
    distribution_name = distribution.metadata.get("Name")
    if not isinstance(distribution_name, str) or not distribution_name:
        raise PoseBustersOpenBabelComparisonError(
            "Open Babel distribution name is unavailable"
        )
    files = distribution.files
    if files is None:
        raise PoseBustersOpenBabelComparisonError(
            "Open Babel distribution file inventory is unavailable"
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
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel distribution payload file is missing"
            ) from exc
        if not stat.S_ISREG(metadata.st_mode):
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel distribution contains a non-regular payload file"
            )
        digest, size, mode = _hash_regular(
            path,
            maximum_bytes=POSEBUSTERS_EXTERNAL_PREPARATION_MAX_DEPENDENCY_FILE_BYTES,
        )
        key = relative.as_posix()
        if key in payload:
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel distribution contains a duplicate payload path"
            )
        payload[key] = {"mode": mode, "sha256": digest, "size_bytes": size}
        total_size += size
        if (
            len(payload) > POSEBUSTERS_EXTERNAL_PREPARATION_MAX_DEPENDENCY_FILES
            or total_size > POSEBUSTERS_EXTERNAL_PREPARATION_MAX_DEPENDENCY_BYTES
        ):
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel distribution payload exceeds its bounds"
            )
    if not payload or total_size < 1:
        raise PoseBustersOpenBabelComparisonError(
            "Open Babel distribution payload is empty"
        )
    return PoseBustersOpenBabelRuntimePayload(
        distribution_name=distribution_name,
        distribution_version=distribution.version,
        payload_sha256=_canonical_sha256(payload),
        payload_file_count=len(payload),
        payload_size_bytes=total_size,
    )


def _openbabel_distribution(
    package_module: Any,
) -> importlib.metadata.Distribution:
    module_file = getattr(package_module, "__file__", None)
    if not isinstance(module_file, str) or not module_file:
        raise PoseBustersOpenBabelComparisonError(
            "Open Babel module file identity is unavailable"
        )
    try:
        observed = Path(module_file).resolve(strict=True)
        distribution = importlib.metadata.distribution("openbabel")
    except (OSError, importlib.metadata.PackageNotFoundError) as exc:
        raise PoseBustersOpenBabelComparisonError(
            "Open Babel distribution ownership is unavailable"
        ) from exc
    if distribution.version != POSEBUSTERS_OPENBABEL_VERSION:
        raise PoseBustersOpenBabelComparisonError(
            "Open Babel installed distribution version is not frozen"
        )
    for package_path in distribution.files or ():
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
    raise PoseBustersOpenBabelComparisonError(
        "Open Babel import is not owned by the frozen distribution inventory"
    )


@dataclass(frozen=True, slots=True)
class _OpenBabelAtomObservation:
    role: str
    source_index: int | None
    parent_source_index: int | None
    parent_hydrogen_ordinal: int | None
    atomic_number: int
    element_symbol: str
    aromatic: bool | None
    internal_atom_type: str
    charge: float
    writer_charge_token: str
    writer_charge: float
    writer_atom_type: str

    def __post_init__(self) -> None:
        if self.role not in {"source_atom", "retained_polar_hydrogen"}:
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel atom observation role is invalid"
            )
        if self.role == "source_atom":
            _positive_int(self.source_index, name="source atom index")
            if self.parent_source_index is not None or self.parent_hydrogen_ordinal is not None:
                raise PoseBustersOpenBabelComparisonError(
                    "source atom observation contains hydrogen mapping"
                )
        else:
            if self.source_index is not None:
                raise PoseBustersOpenBabelComparisonError(
                    "hydrogen observation contains a source index"
                )
            _positive_int(self.parent_source_index, name="hydrogen parent index")
            _positive_int(
                self.parent_hydrogen_ordinal,
                name="parent hydrogen ordinal",
            )
        atomic_number = _positive_int(self.atomic_number, name="atomic number")
        if atomic_number > 118 or (self.role == "retained_polar_hydrogen") != (
            atomic_number == 1
        ):
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel atom observation element is inconsistent"
            )
        _bounded_ascii(self.element_symbol, name="element symbol", maximum=3)
        _bounded_ascii(
            self.internal_atom_type,
            name="Open Babel internal atom type",
            maximum=32,
        )
        if not _OPENBABEL_CHARGE_PATTERN.fullmatch(self.writer_charge_token):
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel writer charge token is invalid"
            )
        if not _ATOM_TYPE_PATTERN.fullmatch(self.writer_atom_type):
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel writer atom type is invalid"
            )
        for name, value in (("charge", self.charge), ("writer charge", self.writer_charge)):
            if not math.isfinite(float(value)):
                raise PoseBustersOpenBabelComparisonError(f"{name} must be finite")
        if float(self.writer_charge_token) != float(self.writer_charge):
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel writer charge token is inconsistent"
            )
        if abs(float(self.writer_charge) - float(self.charge)) > (
            POSEBUSTERS_PREPARED_LIGAND_CHARGE_TOLERANCE
        ):
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel writer charge is inconsistent with full precision"
            )


@dataclass(frozen=True, slots=True)
class _OpenBabelMoleculeObservation:
    formal_charge: int
    source_atoms: tuple[_OpenBabelAtomObservation, ...]
    retained_hydrogens: tuple[_OpenBabelAtomObservation, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.formal_charge, int) or abs(self.formal_charge) > 32:
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel formal charge is invalid"
            )
        sources = tuple(self.source_atoms)
        hydrogens = tuple(self.retained_hydrogens)
        if not sources or tuple(row.source_index for row in sources) != tuple(
            range(1, len(sources) + 1)
        ):
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel source atom order is not contiguous"
            )
        hydrogen_keys = tuple(
            (row.parent_source_index, row.parent_hydrogen_ordinal)
            for row in hydrogens
        )
        if tuple(sorted(hydrogen_keys)) != hydrogen_keys or len(set(hydrogen_keys)) != len(
            hydrogen_keys
        ):
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel retained hydrogen mapping is not canonical"
            )


class _OpenBabelRuntimeProtocol(Protocol):
    identity: PoseBustersOpenBabelRuntimeIdentity

    def observe_smiles(self, smiles: str) -> _OpenBabelMoleculeObservation: ...


class _OpenBabelRuntime:
    def __init__(
        self,
        wheel_path: str | os.PathLike[str],
        *,
        expected_wheel_sha256: str,
    ) -> None:
        expected = _digest(expected_wheel_sha256, name="expected Open Babel wheel")
        if expected != POSEBUSTERS_OPENBABEL_WHEEL_SHA256:
            raise PoseBustersOpenBabelComparisonError(
                "expected Open Babel wheel digest is not the frozen official digest"
            )
        wheel = Path(wheel_path)
        if wheel.name != POSEBUSTERS_OPENBABEL_WHEEL_FILENAME:
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel wheel filename is not frozen"
            )
        wheel_sha, wheel_size, _wheel_mode = _hash_regular(
            wheel,
            maximum_bytes=POSEBUSTERS_EXTERNAL_PREPARATION_MAX_DEPENDENCY_FILE_BYTES,
        )
        if wheel_sha != expected:
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel wheel does not match its frozen digest"
            )
        try:
            import openbabel as openbabel_package
            from openbabel import openbabel
        except ImportError as exc:
            raise PoseBustersOpenBabelComparisonError(
                "frozen Open Babel Python bindings are unavailable"
            ) from exc
        release_version = str(openbabel.OBReleaseVersion())
        if release_version != POSEBUSTERS_OPENBABEL_VERSION:
            raise PoseBustersOpenBabelComparisonError(
                "loaded Open Babel library version is not frozen"
            )
        distribution = _openbabel_distribution(openbabel_package)
        payload = _distribution_payload(distribution)
        charge_model = openbabel.OBChargeModel.FindType("gasteiger")
        if charge_model is None or str(charge_model.GetID()) != "gasteiger":
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel Gasteiger charge model is unavailable"
            )
        reader_probe = openbabel.OBConversion()
        writer_probe = openbabel.OBConversion()
        if not reader_probe.SetInFormat("smi") or not writer_probe.SetOutFormat(
            "pdbqt"
        ):
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel SMILES reader or PDBQT writer is unavailable"
            )
        executable = Path(sys.executable).resolve(strict=True)
        executable_sha, executable_size, _mode = _hash_regular(
            executable,
            maximum_bytes=POSEBUSTERS_EXTERNAL_PREPARATION_MAX_DEPENDENCY_FILE_BYTES,
        )
        cache_tag = getattr(sys.implementation, "cache_tag", None)
        if not isinstance(cache_tag, str) or not cache_tag:
            raise PoseBustersOpenBabelComparisonError(
                "Python runtime does not expose a cache tag"
            )
        libc_name, libc_version = platform.libc_ver()
        self.identity = PoseBustersOpenBabelRuntimeIdentity(
            python_implementation=platform.python_implementation(),
            python_version=platform.python_version(),
            python_cache_tag=cache_tag,
            python_executable_sha256=executable_sha,
            python_executable_size_bytes=executable_size,
            platform_system=platform.system(),
            platform_machine=platform.machine(),
            libc_name=libc_name,
            libc_version=libc_version,
            filesystem_encoding=sys.getfilesystemencoding(),
            openbabel_release_version=release_version,
            openbabel_source_commit=POSEBUSTERS_OPENBABEL_SOURCE_COMMIT,
            wheel_filename=wheel.name,
            wheel_sha256=wheel_sha,
            wheel_size_bytes=wheel_size,
            distribution_payload=payload,
            charge_model_id=str(charge_model.GetID()),
        )
        self._ob = openbabel
        self._charge_model = charge_model

    def _writer_rows(
        self,
        molecule: Any,
    ) -> tuple[tuple[int, str, float, str], ...]:
        conversion = self._ob.OBConversion()
        if not conversion.SetOutFormat("pdbqt"):
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel PDBQT writer became unavailable"
            )
        for option in ("c", "p", "r"):
            conversion.AddOption(option, self._ob.OBConversion.OUTOPTIONS)
        output = conversion.WriteString(molecule)
        if (
            not isinstance(output, str)
            or not output
            or len(output.encode("ascii", errors="strict")) > 4 * 1024 * 1024
        ):
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel PDBQT writer output is invalid"
            )
        rows: list[tuple[int, str, float, str]] = []
        for line in output.splitlines():
            if not line.startswith(("ATOM  ", "HETATM")):
                continue
            if len(line) < 79:
                raise PoseBustersOpenBabelComparisonError(
                    "Open Babel PDBQT atom record is truncated"
                )
            try:
                serial = int(line[6:11])
                token = line[70:76].strip()
                charge = float(token)
            except ValueError as exc:
                raise PoseBustersOpenBabelComparisonError(
                    "Open Babel PDBQT atom record is invalid"
                ) from exc
            atom_type = line[77:].strip()
            if (
                not _OPENBABEL_CHARGE_PATTERN.fullmatch(token)
                or not math.isfinite(charge)
                or not _ATOM_TYPE_PATTERN.fullmatch(atom_type)
            ):
                raise PoseBustersOpenBabelComparisonError(
                    "Open Babel PDBQT charge or atom type is invalid"
                )
            rows.append((serial, token, charge, atom_type))
        if not rows or tuple(row[0] for row in rows) != tuple(
            range(1, len(rows) + 1)
        ):
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel PDBQT writer atom order is not contiguous"
            )
        return tuple(rows)

    def observe_smiles(self, smiles: str) -> _OpenBabelMoleculeObservation:
        source = _bounded_ascii(smiles, name="embedded SMILES", maximum=16_384)
        conversion = self._ob.OBConversion()
        if not conversion.SetInFormat("smi"):
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel SMILES reader became unavailable"
            )
        molecule = self._ob.OBMol()
        if not conversion.ReadString(molecule, source):
            raise PoseBustersOpenBabelComparisonError(
                "embedded SMILES failed Open Babel parsing"
            )
        source_count = int(molecule.NumAtoms())
        if (
            source_count < 1
            or source_count > POSEBUSTERS_PREPARED_LIGAND_MAX_ATOMS_PER_CASE
            or any(
                molecule.GetAtom(index).GetAtomicNum() == 1
                for index in range(1, source_count + 1)
            )
        ):
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel source atom inventory is invalid"
            )
        if not molecule.AddHydrogens():
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel explicit-hydrogen expansion failed"
            )
        if any(
            molecule.GetAtom(index).GetAtomicNum() != 1
            for index in range(source_count + 1, molecule.NumAtoms() + 1)
        ):
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel hydrogen expansion changed source atom ordering"
            )
        if not self._charge_model.ComputeCharges(molecule):
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel Gasteiger charge calculation failed"
            )
        nonpolar_by_parent: dict[int, list[tuple[int, float]]] = defaultdict(list)
        retained_by_parent: dict[int, list[tuple[int, float, str]]] = defaultdict(list)
        for atom_index in range(source_count + 1, molecule.NumAtoms() + 1):
            atom = molecule.GetAtom(atom_index)
            neighbors = tuple(self._ob.OBAtomAtomIter(atom))
            if len(neighbors) != 1 or neighbors[0].GetIdx() > source_count:
                raise PoseBustersOpenBabelComparisonError(
                    "Open Babel hydrogen parent mapping is invalid"
                )
            charge = float(atom.GetPartialCharge())
            if not math.isfinite(charge):
                raise PoseBustersOpenBabelComparisonError(
                    "Open Babel hydrogen charge is not finite"
                )
            parent = int(neighbors[0].GetIdx())
            if atom.IsNonPolarHydrogen():
                nonpolar_by_parent[parent].append((atom_index, charge))
            else:
                retained_by_parent[parent].append(
                    (atom_index, charge, str(atom.GetType()))
                )
        writer_rows = self._writer_rows(molecule)
        retained_flat = tuple(
            (parent, atom_index, charge, internal_type)
            for parent in sorted(retained_by_parent)
            for atom_index, charge, internal_type in sorted(
                retained_by_parent[parent], key=lambda row: row[0]
            )
        )
        if len(writer_rows) != source_count + len(retained_flat):
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel PDBQT writer hydrogen suppression is inconsistent"
            )
        source_rows: list[_OpenBabelAtomObservation] = []
        for source_index in range(1, source_count + 1):
            atom = molecule.GetAtom(source_index)
            charge = float(atom.GetPartialCharge()) + math.fsum(
                value for _atom_index, value in nonpolar_by_parent.get(source_index, ())
            )
            _serial, token, writer_charge, writer_type = writer_rows[source_index - 1]
            source_rows.append(
                _OpenBabelAtomObservation(
                    role="source_atom",
                    source_index=source_index,
                    parent_source_index=None,
                    parent_hydrogen_ordinal=None,
                    atomic_number=int(atom.GetAtomicNum()),
                    element_symbol=str(self._ob.GetSymbol(atom.GetAtomicNum())),
                    aromatic=bool(atom.IsAromatic()),
                    internal_atom_type=str(atom.GetType()),
                    charge=charge,
                    writer_charge_token=token,
                    writer_charge=writer_charge,
                    writer_atom_type=writer_type,
                )
            )
        hydrogen_rows: list[_OpenBabelAtomObservation] = []
        ordinal_by_parent: Counter[int] = Counter()
        for offset, (parent, _atom_index, charge, internal_type) in enumerate(
            retained_flat,
            start=source_count,
        ):
            ordinal_by_parent[parent] += 1
            _serial, token, writer_charge, writer_type = writer_rows[offset]
            hydrogen_rows.append(
                _OpenBabelAtomObservation(
                    role="retained_polar_hydrogen",
                    source_index=None,
                    parent_source_index=parent,
                    parent_hydrogen_ordinal=ordinal_by_parent[parent],
                    atomic_number=1,
                    element_symbol="H",
                    aromatic=None,
                    internal_atom_type=internal_type,
                    charge=charge,
                    writer_charge_token=token,
                    writer_charge=writer_charge,
                    writer_atom_type=writer_type,
                )
            )
        return _OpenBabelMoleculeObservation(
            formal_charge=int(molecule.GetTotalCharge()),
            source_atoms=tuple(source_rows),
            retained_hydrogens=tuple(hydrogen_rows),
        )


def _load_openbabel_runtime(
    wheel_path: str | os.PathLike[str],
    *,
    expected_wheel_sha256: str,
) -> _OpenBabelRuntimeProtocol:
    return _OpenBabelRuntime(
        wheel_path,
        expected_wheel_sha256=expected_wheel_sha256,
    )


@dataclass(frozen=True, slots=True)
class PoseBustersOpenBabelAtomComparison:
    pdbqt_serial: int
    pdbqt_atom_name: str
    role: str
    source_smiles_atom_index: int | None
    source_parent_smiles_atom_index: int | None
    atomic_number: int
    element_symbol: str
    aromatic: bool | None
    meeko_ad4_atom_type: str
    openbabel_ad4_atom_type: str | None
    ad4_atom_type_exact_match: bool | None
    openbabel_internal_atom_type: str | None
    meeko_charge_token: str
    meeko_charge_binary64_hex: str
    openbabel_charge_binary64_hex: str | None
    signed_charge_delta_binary64_hex: str | None
    absolute_charge_delta_binary64_hex: str | None
    openbabel_writer_charge_token: str | None
    openbabel_writer_charge_binary64_hex: str | None
    openbabel_writer_self_consistency_pass: bool | None
    schema_id: str = POSEBUSTERS_OPENBABEL_ATOM_COMPARISON_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_OPENBABEL_ATOM_COMPARISON_SCHEMA_ID:
            raise PoseBustersOpenBabelComparisonError(
                "unsupported Open Babel atom-comparison schema"
            )
        object.__setattr__(
            self,
            "pdbqt_serial",
            _positive_int(self.pdbqt_serial, name="PDBQT atom serial"),
        )
        object.__setattr__(
            self,
            "pdbqt_atom_name",
            _bounded_ascii(self.pdbqt_atom_name, name="PDBQT atom name", maximum=4),
        )
        if self.role not in _ATOM_ROLES:
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel atom-comparison role is invalid"
            )
        object.__setattr__(
            self,
            "meeko_charge_binary64_hex",
            _canonical_float_hex(
                self.meeko_charge_binary64_hex,
                name="Meeko charge",
            ),
        )
        if (
            not _MEEKO_CHARGE_PATTERN.fullmatch(self.meeko_charge_token)
            or float(self.meeko_charge_token)
            != float.fromhex(self.meeko_charge_binary64_hex)
        ):
            raise PoseBustersOpenBabelComparisonError(
                "Meeko charge token and binary64 value are inconsistent"
            )
        if not _ATOM_TYPE_PATTERN.fullmatch(self.meeko_ad4_atom_type):
            raise PoseBustersOpenBabelComparisonError(
                "Meeko AutoDock4 atom type is invalid"
            )
        if self.role == "macrocycle_closure_pseudoatom":
            if (
                self.source_smiles_atom_index is not None
                or self.source_parent_smiles_atom_index is not None
                or self.atomic_number != 0
                or self.element_symbol != "G"
                or self.aromatic is not None
                or self.meeko_ad4_atom_type != "G0"
                or float.fromhex(self.meeko_charge_binary64_hex) != 0.0
                or any(
                    value is not None
                    for value in (
                        self.openbabel_ad4_atom_type,
                        self.ad4_atom_type_exact_match,
                        self.openbabel_internal_atom_type,
                        self.openbabel_charge_binary64_hex,
                        self.signed_charge_delta_binary64_hex,
                        self.absolute_charge_delta_binary64_hex,
                        self.openbabel_writer_charge_token,
                        self.openbabel_writer_charge_binary64_hex,
                        self.openbabel_writer_self_consistency_pass,
                    )
                )
            ):
                raise PoseBustersOpenBabelComparisonError(
                    "macrocycle pseudoatom comparison must remain excluded"
                )
            return
        atomic_number = _positive_int(self.atomic_number, name="atomic number")
        if atomic_number > 118:
            raise PoseBustersOpenBabelComparisonError("atomic number is invalid")
        if self.role == "source_atom":
            _positive_int(
                self.source_smiles_atom_index,
                name="source SMILES atom index",
            )
            if (
                self.source_parent_smiles_atom_index is not None
                or atomic_number == 1
                or not isinstance(self.aromatic, bool)
            ):
                raise PoseBustersOpenBabelComparisonError(
                    "source atom comparison mapping is inconsistent"
                )
        else:
            _positive_int(
                self.source_parent_smiles_atom_index,
                name="source parent SMILES atom index",
            )
            if (
                self.source_smiles_atom_index is not None
                or atomic_number != 1
                or self.aromatic is not None
            ):
                raise PoseBustersOpenBabelComparisonError(
                    "retained hydrogen comparison mapping is inconsistent"
                )
        _bounded_ascii(self.element_symbol, name="element symbol", maximum=3)
        if (
            not isinstance(self.openbabel_ad4_atom_type, str)
            or not _ATOM_TYPE_PATTERN.fullmatch(self.openbabel_ad4_atom_type)
            or self.ad4_atom_type_exact_match
            != (self.meeko_ad4_atom_type == self.openbabel_ad4_atom_type)
            or not isinstance(self.openbabel_internal_atom_type, str)
        ):
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel atom-type comparison is inconsistent"
            )
        _bounded_ascii(
            self.openbabel_internal_atom_type,
            name="Open Babel internal atom type",
            maximum=32,
        )
        openbabel_charge = _canonical_float_hex(
            self.openbabel_charge_binary64_hex,
            name="Open Babel charge",
        )
        signed_delta = _canonical_float_hex(
            self.signed_charge_delta_binary64_hex,
            name="signed charge delta",
        )
        absolute_delta = _canonical_float_hex(
            self.absolute_charge_delta_binary64_hex,
            name="absolute charge delta",
        )
        meeko_value = float.fromhex(self.meeko_charge_binary64_hex)
        openbabel_value = float.fromhex(openbabel_charge)
        if (
            (openbabel_value - meeko_value).hex() != signed_delta
            or abs(openbabel_value - meeko_value).hex() != absolute_delta
        ):
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel charge delta is inconsistent"
            )
        writer_charge = _canonical_float_hex(
            self.openbabel_writer_charge_binary64_hex,
            name="Open Babel writer charge",
        )
        if (
            not isinstance(self.openbabel_writer_charge_token, str)
            or not _OPENBABEL_CHARGE_PATTERN.fullmatch(
                self.openbabel_writer_charge_token
            )
            or float(self.openbabel_writer_charge_token)
            != float.fromhex(writer_charge)
        ):
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel writer charge token is inconsistent"
            )
        writer_pass = abs(float.fromhex(writer_charge) - openbabel_value) <= (
            POSEBUSTERS_PREPARED_LIGAND_CHARGE_TOLERANCE
        )
        if self.openbabel_writer_self_consistency_pass is not writer_pass:
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel writer self-consistency flag is invalid"
            )
        object.__setattr__(
            self,
            "openbabel_charge_binary64_hex",
            openbabel_charge,
        )
        object.__setattr__(
            self,
            "signed_charge_delta_binary64_hex",
            signed_delta,
        )
        object.__setattr__(
            self,
            "absolute_charge_delta_binary64_hex",
            absolute_delta,
        )
        object.__setattr__(
            self,
            "openbabel_writer_charge_binary64_hex",
            writer_charge,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "pdbqt_serial": self.pdbqt_serial,
            "pdbqt_atom_name": self.pdbqt_atom_name,
            "role": self.role,
            "source_smiles_atom_index": self.source_smiles_atom_index,
            "source_parent_smiles_atom_index": (
                self.source_parent_smiles_atom_index
            ),
            "atomic_number": self.atomic_number,
            "element_symbol": self.element_symbol,
            "aromatic": self.aromatic,
            "meeko_ad4_atom_type": self.meeko_ad4_atom_type,
            "openbabel_ad4_atom_type": self.openbabel_ad4_atom_type,
            "ad4_atom_type_exact_match": self.ad4_atom_type_exact_match,
            "openbabel_internal_atom_type": self.openbabel_internal_atom_type,
            "meeko_charge_token": self.meeko_charge_token,
            "meeko_charge_binary64_hex": self.meeko_charge_binary64_hex,
            "openbabel_charge_binary64_hex": self.openbabel_charge_binary64_hex,
            "signed_charge_delta_binary64_hex": (
                self.signed_charge_delta_binary64_hex
            ),
            "absolute_charge_delta_binary64_hex": (
                self.absolute_charge_delta_binary64_hex
            ),
            "openbabel_writer_charge_token": self.openbabel_writer_charge_token,
            "openbabel_writer_charge_binary64_hex": (
                self.openbabel_writer_charge_binary64_hex
            ),
            "openbabel_writer_self_consistency_pass": (
                self.openbabel_writer_self_consistency_pass
            ),
        }


def _type_pair_counts(
    rows: Sequence[PoseBustersOpenBabelAtomComparison],
) -> tuple[tuple[str, str, int], ...]:
    counts = Counter(
        (row.meeko_ad4_atom_type, row.openbabel_ad4_atom_type)
        for row in rows
        if row.openbabel_ad4_atom_type is not None
    )
    return tuple(
        (meeko_type, openbabel_type, count)
        for (meeko_type, openbabel_type), count in sorted(counts.items())
    )


@dataclass(frozen=True, slots=True)
class PoseBustersOpenBabelCaseComparison:
    case_id: str
    status: str
    disposition_code: str
    preparation_status: str
    preparation_disposition_code: str
    comparison_attempted: bool = False
    prepared_ligand_sha256: str | None = None
    prepared_ligand_size_bytes: int | None = None
    embedded_smiles_sha256: str | None = None
    openbabel_formal_charge: int | None = None
    atom_rows: tuple[PoseBustersOpenBabelAtomComparison, ...] = ()
    meeko_total_charge_binary64_hex: str | None = None
    openbabel_total_charge_binary64_hex: str | None = None
    signed_total_charge_delta_binary64_hex: str | None = None
    mean_absolute_charge_delta_binary64_hex: str | None = None
    root_mean_square_charge_delta_binary64_hex: str | None = None
    maximum_absolute_charge_delta_binary64_hex: str | None = None
    error_code: str | None = None
    error_type: str | None = None
    error_message_sha256: str | None = None
    schema_id: str = POSEBUSTERS_OPENBABEL_CASE_COMPARISON_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_OPENBABEL_CASE_COMPARISON_SCHEMA_ID:
            raise PoseBustersOpenBabelComparisonError(
                "unsupported Open Babel case-comparison schema"
            )
        object.__setattr__(self, "case_id", _case_id(self.case_id))
        if self.status not in _CASE_STATUSES:
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel case-comparison status is invalid"
            )
        object.__setattr__(
            self,
            "disposition_code",
            _token(self.disposition_code, name="comparison disposition"),
        )
        object.__setattr__(
            self,
            "preparation_disposition_code",
            _token(
                self.preparation_disposition_code,
                name="preparation disposition",
            ),
        )
        if self.preparation_status not in {
            "abstain_chemistry_scope",
            "preparation_failure",
            "prepared",
            "upstream_failure",
        }:
            raise PoseBustersOpenBabelComparisonError(
                "preparation status is invalid"
            )
        rows = tuple(self.atom_rows)
        object.__setattr__(self, "atom_rows", rows)
        artifact_fields = (
            self.prepared_ligand_sha256,
            self.prepared_ligand_size_bytes,
            self.embedded_smiles_sha256,
        )
        statistic_fields = (
            self.meeko_total_charge_binary64_hex,
            self.openbabel_total_charge_binary64_hex,
            self.signed_total_charge_delta_binary64_hex,
            self.mean_absolute_charge_delta_binary64_hex,
            self.root_mean_square_charge_delta_binary64_hex,
            self.maximum_absolute_charge_delta_binary64_hex,
        )
        error_fields = (self.error_code, self.error_type, self.error_message_sha256)
        if self.status == "evaluated":
            if (
                self.preparation_status != "prepared"
                or self.comparison_attempted is not True
                or any(value is None for value in artifact_fields)
                or any(value is None for value in statistic_fields)
                or any(value is not None for value in error_fields)
                or type(self.openbabel_formal_charge) is not int
                or abs(self.openbabel_formal_charge) > 32
                or not rows
                or tuple(row.pdbqt_serial for row in rows)
                != tuple(range(1, len(rows) + 1))
            ):
                raise PoseBustersOpenBabelComparisonError(
                    "evaluated Open Babel case is incomplete"
                )
            object.__setattr__(
                self,
                "prepared_ligand_sha256",
                _digest(self.prepared_ligand_sha256, name="prepared ligand"),
            )
            object.__setattr__(
                self,
                "prepared_ligand_size_bytes",
                _positive_int(
                    self.prepared_ligand_size_bytes,
                    name="prepared ligand size",
                ),
            )
            object.__setattr__(
                self,
                "embedded_smiles_sha256",
                _digest(self.embedded_smiles_sha256, name="embedded SMILES"),
            )
            compared = tuple(
                row
                for row in rows
                if row.role != "macrocycle_closure_pseudoatom"
            )
            if not compared or any(
                row.openbabel_writer_self_consistency_pass is not True
                for row in compared
            ):
                raise PoseBustersOpenBabelComparisonError(
                    "evaluated Open Babel atoms are incomplete"
                )
            meeko = tuple(
                float.fromhex(row.meeko_charge_binary64_hex) for row in compared
            )
            openbabel = tuple(
                float.fromhex(row.openbabel_charge_binary64_hex) for row in compared
            )
            deltas = tuple(
                openbabel_value - meeko_value
                for meeko_value, openbabel_value in zip(
                    meeko,
                    openbabel,
                    strict=True,
                )
            )
            expected_statistics = (
                math.fsum(meeko).hex(),
                math.fsum(openbabel).hex(),
                math.fsum(deltas).hex(),
                (math.fsum(abs(value) for value in deltas) / len(deltas)).hex(),
                math.sqrt(
                    math.fsum(value * value for value in deltas) / len(deltas)
                ).hex(),
                max(abs(value) for value in deltas).hex(),
            )
            normalized_statistics = tuple(
                _canonical_float_hex(value, name="case charge statistic")
                for value in statistic_fields
            )
            if normalized_statistics != expected_statistics:
                raise PoseBustersOpenBabelComparisonError(
                    "Open Babel case charge statistics are inconsistent"
                )
        elif self.status == "comparison_failure":
            if (
                self.preparation_status != "prepared"
                or self.comparison_attempted is not True
                or any(value is None for value in artifact_fields[:2])
                or self.embedded_smiles_sha256 is not None
                or self.openbabel_formal_charge is not None
                or rows
                or any(value is not None for value in statistic_fields)
                or any(value is None for value in error_fields)
            ):
                raise PoseBustersOpenBabelComparisonError(
                    "Open Babel comparison-failure case is inconsistent"
                )
            object.__setattr__(
                self,
                "prepared_ligand_sha256",
                _digest(self.prepared_ligand_sha256, name="prepared ligand"),
            )
            object.__setattr__(
                self,
                "prepared_ligand_size_bytes",
                _positive_int(
                    self.prepared_ligand_size_bytes,
                    name="prepared ligand size",
                ),
            )
            object.__setattr__(
                self,
                "error_code",
                _token(self.error_code, name="comparison error code"),
            )
            object.__setattr__(
                self,
                "error_type",
                _bounded_ascii(self.error_type, name="comparison error type", maximum=256),
            )
            object.__setattr__(
                self,
                "error_message_sha256",
                _digest(self.error_message_sha256, name="comparison error message"),
            )
        else:
            expected_preparation_status = {
                "abstain_chemistry_scope": "abstain_chemistry_scope",
                "blocked_preparation_failure": "preparation_failure",
                "blocked_upstream_failure": "upstream_failure",
            }[self.status]
            if (
                self.preparation_status != expected_preparation_status
                or self.comparison_attempted is not False
                or any(value is not None for value in artifact_fields)
                or self.openbabel_formal_charge is not None
                or rows
                or any(value is not None for value in statistic_fields)
                or any(value is not None for value in error_fields)
            ):
                raise PoseBustersOpenBabelComparisonError(
                    "blocked Open Babel comparison case is inconsistent"
                )

    @property
    def compared_atom_count(self) -> int:
        return sum(
            row.role != "macrocycle_closure_pseudoatom" for row in self.atom_rows
        )

    @property
    def pseudoatom_count(self) -> int:
        return sum(
            row.role == "macrocycle_closure_pseudoatom" for row in self.atom_rows
        )

    @property
    def source_atom_count(self) -> int:
        return sum(row.role == "source_atom" for row in self.atom_rows)

    @property
    def retained_hydrogen_count(self) -> int:
        return sum(row.role == "retained_polar_hydrogen" for row in self.atom_rows)

    @property
    def type_match_count(self) -> int:
        return sum(row.ad4_atom_type_exact_match is True for row in self.atom_rows)

    @property
    def type_mismatch_count(self) -> int:
        return sum(row.ad4_atom_type_exact_match is False for row in self.atom_rows)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "case_id": self.case_id,
            "status": self.status,
            "disposition_code": self.disposition_code,
            "preparation_status": self.preparation_status,
            "preparation_disposition_code": self.preparation_disposition_code,
            "comparison_attempted": self.comparison_attempted,
            "prepared_ligand_sha256": self.prepared_ligand_sha256,
            "prepared_ligand_size_bytes": self.prepared_ligand_size_bytes,
            "embedded_smiles_sha256": self.embedded_smiles_sha256,
            "openbabel_formal_charge": self.openbabel_formal_charge,
            "source_atom_count": self.source_atom_count,
            "retained_polar_hydrogen_count": self.retained_hydrogen_count,
            "macrocycle_pseudoatom_count": self.pseudoatom_count,
            "compared_atom_count": self.compared_atom_count,
            "ad4_atom_type_exact_match_count": self.type_match_count,
            "ad4_atom_type_mismatch_count": self.type_mismatch_count,
            "ad4_atom_type_pair_counts": [
                {
                    "meeko_ad4_atom_type": meeko_type,
                    "openbabel_ad4_atom_type": openbabel_type,
                    "count": count,
                }
                for meeko_type, openbabel_type, count in _type_pair_counts(
                    self.atom_rows
                )
            ],
            "meeko_total_charge_binary64_hex": (
                self.meeko_total_charge_binary64_hex
            ),
            "openbabel_total_charge_binary64_hex": (
                self.openbabel_total_charge_binary64_hex
            ),
            "signed_total_charge_delta_binary64_hex": (
                self.signed_total_charge_delta_binary64_hex
            ),
            "mean_absolute_charge_delta_binary64_hex": (
                self.mean_absolute_charge_delta_binary64_hex
            ),
            "root_mean_square_charge_delta_binary64_hex": (
                self.root_mean_square_charge_delta_binary64_hex
            ),
            "maximum_absolute_charge_delta_binary64_hex": (
                self.maximum_absolute_charge_delta_binary64_hex
            ),
            "charge_accuracy_threshold_preregistered": False,
            "charge_accuracy_pass": None,
            "atom_rows": [row.to_dict() for row in self.atom_rows],
            "error_code": self.error_code,
            "error_type": self.error_type,
            "error_message_sha256": self.error_message_sha256,
        }


@dataclass(frozen=True, slots=True)
class PoseBustersOpenBabelMetric:
    metric_id: str
    population: str
    numerator: int
    denominator: int
    schema_id: str = POSEBUSTERS_OPENBABEL_METRIC_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_OPENBABEL_METRIC_SCHEMA_ID:
            raise PoseBustersOpenBabelComparisonError(
                "unsupported Open Babel metric schema"
            )
        object.__setattr__(
            self,
            "metric_id",
            _token(self.metric_id, name="metric ID"),
        )
        object.__setattr__(
            self,
            "population",
            _token(self.population, name="metric population"),
        )
        numerator = _positive_int(
            self.numerator,
            name="metric numerator",
            allow_zero=True,
        )
        denominator = _positive_int(self.denominator, name="metric denominator")
        if numerator > denominator:
            raise PoseBustersOpenBabelComparisonError(
                "metric numerator exceeds denominator"
            )
        object.__setattr__(self, "numerator", numerator)
        object.__setattr__(self, "denominator", denominator)

    def to_dict(self) -> dict[str, Any]:
        low, high = _wilson_interval(self.numerator, self.denominator)
        return {
            "schema_id": self.schema_id,
            "metric_id": self.metric_id,
            "population": self.population,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "rate_binary64_hex": (self.numerator / self.denominator).hex(),
            "confidence_level_binary64_hex": (
                POSEBUSTERS_OPENBABEL_CONFIDENCE_LEVEL.hex()
            ),
            "confidence_interval_method": "wilson_score_binomial",
            "wilson_low_binary64_hex": low,
            "wilson_high_binary64_hex": high,
        }


def _blocked_case(
    prepared: _PreparedCaseView,
) -> PoseBustersOpenBabelCaseComparison:
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
    return PoseBustersOpenBabelCaseComparison(
        case_id=prepared.case_id,
        status=status,
        disposition_code=disposition,
        preparation_status=prepared.status,
        preparation_disposition_code=prepared.disposition_code,
    )


def _compared_atom_row(
    *,
    pdbqt_atom: Any,
    role: str,
    source_index: int | None,
    parent_source_index: int | None,
    observation: _OpenBabelAtomObservation,
) -> PoseBustersOpenBabelAtomComparison:
    meeko_charge = float(pdbqt_atom.observed_charge)
    openbabel_charge = float(observation.charge)
    signed_delta = openbabel_charge - meeko_charge
    writer_pass = abs(float(observation.writer_charge) - openbabel_charge) <= (
        POSEBUSTERS_PREPARED_LIGAND_CHARGE_TOLERANCE
    )
    return PoseBustersOpenBabelAtomComparison(
        pdbqt_serial=pdbqt_atom.serial,
        pdbqt_atom_name=pdbqt_atom.atom_name,
        role=role,
        source_smiles_atom_index=source_index,
        source_parent_smiles_atom_index=parent_source_index,
        atomic_number=observation.atomic_number,
        element_symbol=observation.element_symbol,
        aromatic=observation.aromatic,
        meeko_ad4_atom_type=pdbqt_atom.atom_type,
        openbabel_ad4_atom_type=observation.writer_atom_type,
        ad4_atom_type_exact_match=(
            pdbqt_atom.atom_type == observation.writer_atom_type
        ),
        openbabel_internal_atom_type=observation.internal_atom_type,
        meeko_charge_token=pdbqt_atom.observed_charge_token,
        meeko_charge_binary64_hex=meeko_charge.hex(),
        openbabel_charge_binary64_hex=openbabel_charge.hex(),
        signed_charge_delta_binary64_hex=signed_delta.hex(),
        absolute_charge_delta_binary64_hex=abs(signed_delta).hex(),
        openbabel_writer_charge_token=observation.writer_charge_token,
        openbabel_writer_charge_binary64_hex=(
            float(observation.writer_charge).hex()
        ),
        openbabel_writer_self_consistency_pass=writer_pass,
    )


def _pseudoatom_row(pdbqt_atom: Any) -> PoseBustersOpenBabelAtomComparison:
    return PoseBustersOpenBabelAtomComparison(
        pdbqt_serial=pdbqt_atom.serial,
        pdbqt_atom_name=pdbqt_atom.atom_name,
        role="macrocycle_closure_pseudoatom",
        source_smiles_atom_index=None,
        source_parent_smiles_atom_index=None,
        atomic_number=0,
        element_symbol="G",
        aromatic=None,
        meeko_ad4_atom_type=pdbqt_atom.atom_type,
        openbabel_ad4_atom_type=None,
        ad4_atom_type_exact_match=None,
        openbabel_internal_atom_type=None,
        meeko_charge_token=pdbqt_atom.observed_charge_token,
        meeko_charge_binary64_hex=float(pdbqt_atom.observed_charge).hex(),
        openbabel_charge_binary64_hex=None,
        signed_charge_delta_binary64_hex=None,
        absolute_charge_delta_binary64_hex=None,
        openbabel_writer_charge_token=None,
        openbabel_writer_charge_binary64_hex=None,
        openbabel_writer_self_consistency_pass=None,
    )


def _evaluate_prepared_ligand(
    prepared: _PreparedCaseView,
    *,
    artifact_sha256: str,
    artifact_size: int,
    payload: bytes,
    runtime: _OpenBabelRuntimeProtocol,
) -> PoseBustersOpenBabelCaseComparison:
    parsed: _ParsedLigand = _parse_ligand_pdbqt(payload)
    observation = runtime.observe_smiles(parsed.smiles)
    source_to_serial = dict(parsed.source_to_serial)
    expected_source_indexes = set(range(1, len(observation.source_atoms) + 1))
    if (
        set(source_to_serial) != expected_source_indexes
        or tuple(row.source_index for row in observation.source_atoms)
        != tuple(range(1, len(observation.source_atoms) + 1))
    ):
        raise PoseBustersOpenBabelComparisonError(
            "embedded SMILES mapping does not match Open Babel source atoms"
        )
    meeko_hydrogens: dict[int, list[int]] = defaultdict(list)
    for parent, serial in parsed.parent_to_hydrogen_serial:
        if parent not in expected_source_indexes:
            raise PoseBustersOpenBabelComparisonError(
                "Meeko retained hydrogen references an unknown Open Babel parent"
            )
        meeko_hydrogens[parent].append(serial)
    for serials in meeko_hydrogens.values():
        serials.sort()
    openbabel_hydrogens: dict[int, list[_OpenBabelAtomObservation]] = defaultdict(
        list
    )
    for row in observation.retained_hydrogens:
        if row.parent_source_index not in expected_source_indexes:
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel retained hydrogen references an unknown source parent"
            )
        openbabel_hydrogens[row.parent_source_index].append(row)
    for rows in openbabel_hydrogens.values():
        rows.sort(key=lambda row: row.parent_hydrogen_ordinal or 0)
    meeko_counts = {
        parent: len(serials) for parent, serials in sorted(meeko_hydrogens.items())
    }
    openbabel_counts = {
        parent: len(rows) for parent, rows in sorted(openbabel_hydrogens.items())
    }
    if meeko_counts != openbabel_counts:
        raise PoseBustersOpenBabelComparisonError(
            "Meeko and Open Babel retained-hydrogen parent counts differ"
        )
    rows_by_serial: dict[int, PoseBustersOpenBabelAtomComparison] = {}
    for source in observation.source_atoms:
        if source.source_index is None:
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel source observation is missing its source index"
            )
        serial = source_to_serial[source.source_index]
        rows_by_serial[serial] = _compared_atom_row(
            pdbqt_atom=parsed.atoms[serial - 1],
            role="source_atom",
            source_index=source.source_index,
            parent_source_index=None,
            observation=source,
        )
    for parent in sorted(meeko_hydrogens):
        for serial, hydrogen in zip(
            meeko_hydrogens[parent],
            openbabel_hydrogens[parent],
            strict=True,
        ):
            rows_by_serial[serial] = _compared_atom_row(
                pdbqt_atom=parsed.atoms[serial - 1],
                role="retained_polar_hydrogen",
                source_index=None,
                parent_source_index=parent,
                observation=hydrogen,
            )
    for pdbqt_atom in parsed.atoms:
        if pdbqt_atom.serial not in rows_by_serial:
            rows_by_serial[pdbqt_atom.serial] = _pseudoatom_row(pdbqt_atom)
    if set(rows_by_serial) != set(range(1, len(parsed.atoms) + 1)):
        raise PoseBustersOpenBabelComparisonError(
            "Open Babel comparison did not account for every PDBQT atom"
        )
    atom_rows = tuple(rows_by_serial[serial] for serial in sorted(rows_by_serial))
    compared = tuple(
        row for row in atom_rows if row.role != "macrocycle_closure_pseudoatom"
    )
    meeko_charges = tuple(
        float.fromhex(row.meeko_charge_binary64_hex) for row in compared
    )
    openbabel_charges = tuple(
        float.fromhex(row.openbabel_charge_binary64_hex) for row in compared
    )
    deltas = tuple(
        openbabel_value - meeko_value
        for meeko_value, openbabel_value in zip(
            meeko_charges,
            openbabel_charges,
            strict=True,
        )
    )
    return PoseBustersOpenBabelCaseComparison(
        case_id=prepared.case_id,
        status="evaluated",
        disposition_code=(
            "independent_openbabel_charge_and_ad4_type_comparison_complete"
        ),
        preparation_status=prepared.status,
        preparation_disposition_code=prepared.disposition_code,
        comparison_attempted=True,
        prepared_ligand_sha256=artifact_sha256,
        prepared_ligand_size_bytes=artifact_size,
        embedded_smiles_sha256=parsed.smiles_sha256,
        openbabel_formal_charge=observation.formal_charge,
        atom_rows=atom_rows,
        meeko_total_charge_binary64_hex=math.fsum(meeko_charges).hex(),
        openbabel_total_charge_binary64_hex=math.fsum(openbabel_charges).hex(),
        signed_total_charge_delta_binary64_hex=math.fsum(deltas).hex(),
        mean_absolute_charge_delta_binary64_hex=(
            math.fsum(abs(value) for value in deltas) / len(deltas)
        ).hex(),
        root_mean_square_charge_delta_binary64_hex=math.sqrt(
            math.fsum(value * value for value in deltas) / len(deltas)
        ).hex(),
        maximum_absolute_charge_delta_binary64_hex=max(
            abs(value) for value in deltas
        ).hex(),
    )


def _compare_case(
    prepared: _PreparedCaseView,
    prepared_payloads: Mapping[str, bytes],
    runtime: _OpenBabelRuntimeProtocol,
) -> PoseBustersOpenBabelCaseComparison:
    if prepared.status != "prepared":
        return _blocked_case(prepared)
    artifacts = {row.role: row for row in prepared.artifacts}
    ligand = artifacts["prepared_ligand_pdbqt"]
    payload = prepared_payloads[ligand.relative_path]
    try:
        return _evaluate_prepared_ligand(
            prepared,
            artifact_sha256=ligand.sha256,
            artifact_size=ligand.size_bytes,
            payload=payload,
            runtime=runtime,
        )
    except Exception as exc:
        return PoseBustersOpenBabelCaseComparison(
            case_id=prepared.case_id,
            status="comparison_failure",
            disposition_code="openbabel_charge_type_comparison_failed",
            preparation_status=prepared.status,
            preparation_disposition_code=prepared.disposition_code,
            comparison_attempted=True,
            prepared_ligand_sha256=ligand.sha256,
            prepared_ligand_size_bytes=ligand.size_bytes,
            error_code="openbabel_charge_type_comparison_failed",
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
                "openbabel_charge_type_comparison": _source_file_sha256(__file__),
                "preparation_receipt_loader": _source_file_sha256(
                    Path(__file__).with_name("public_posebusters_vina_execution.py")
                ),
                "prepared_ligand_pdbqt_parser": _source_file_sha256(
                    Path(__file__).with_name(
                        "public_posebusters_prepared_ligand_diagnostic.py"
                    )
                ),
            }.items()
        )
    )


def _summary_metrics(
    rows: Sequence[PoseBustersOpenBabelCaseComparison],
) -> tuple[PoseBustersOpenBabelMetric, ...]:
    all_case_denominator = len(rows)
    compared_rows = tuple(
        atom
        for row in rows
        if row.status == "evaluated"
        for atom in row.atom_rows
        if atom.role != "macrocycle_closure_pseudoatom"
    )
    all_case_metrics = (
        PoseBustersOpenBabelMetric(
            metric_id="comparison_attempt_rate_all_cases",
            population="all_cases",
            numerator=sum(row.comparison_attempted for row in rows),
            denominator=all_case_denominator,
        ),
        PoseBustersOpenBabelMetric(
            metric_id="comparison_completion_rate_all_cases",
            population="all_cases",
            numerator=sum(row.status == "evaluated" for row in rows),
            denominator=all_case_denominator,
        ),
        PoseBustersOpenBabelMetric(
            metric_id="comparison_failure_rate_all_cases",
            population="all_cases",
            numerator=sum(row.status == "comparison_failure" for row in rows),
            denominator=all_case_denominator,
        ),
        PoseBustersOpenBabelMetric(
            metric_id="exact_ad4_type_match_case_rate_all_cases",
            population="all_cases",
            numerator=sum(
                row.status == "evaluated" and row.type_mismatch_count == 0
                for row in rows
            ),
            denominator=all_case_denominator,
        ),
    )
    if not compared_rows:
        return all_case_metrics
    return all_case_metrics + (
        PoseBustersOpenBabelMetric(
            metric_id="exact_ad4_type_match_rate_compared_atoms",
            population="compared_real_pdbqt_atoms",
            numerator=sum(
                row.ad4_atom_type_exact_match is True for row in compared_rows
            ),
            denominator=len(compared_rows),
        ),
        PoseBustersOpenBabelMetric(
            metric_id="ad4_type_mismatch_rate_compared_atoms",
            population="compared_real_pdbqt_atoms",
            numerator=sum(
                row.ad4_atom_type_exact_match is False for row in compared_rows
            ),
            denominator=len(compared_rows),
        ),
    )


@dataclass(frozen=True, slots=True)
class PoseBustersOpenBabelComparisonReceipt:
    observation_utc: str
    preparation_receipt_sha256: str
    preparation_receipt_file_sha256: str
    preparation_artifact_set_sha256: str
    preparation_runtime_identity: Mapping[str, Any]
    preparation_runtime_identity_sha256: str
    runtime_identity: PoseBustersOpenBabelRuntimeIdentity
    implementation_source_members: tuple[tuple[str, str], ...]
    case_rows: tuple[PoseBustersOpenBabelCaseComparison, ...]
    metrics: tuple[PoseBustersOpenBabelMetric, ...]
    schema_id: str = POSEBUSTERS_OPENBABEL_COMPARISON_SCHEMA_ID
    configuration_sha256: str = POSEBUSTERS_OPENBABEL_CONFIGURATION_SHA256

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_OPENBABEL_COMPARISON_SCHEMA_ID:
            raise PoseBustersOpenBabelComparisonError(
                "unsupported Open Babel comparison receipt schema"
            )
        if self.configuration_sha256 != (
            POSEBUSTERS_OPENBABEL_CONFIGURATION_SHA256
        ):
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel comparison configuration identity is invalid"
            )
        object.__setattr__(self, "observation_utc", _utc_timestamp(self.observation_utc))
        for field_name in (
            "preparation_receipt_sha256",
            "preparation_receipt_file_sha256",
            "preparation_artifact_set_sha256",
            "preparation_runtime_identity_sha256",
        ):
            object.__setattr__(
                self,
                field_name,
                _digest(getattr(self, field_name), name=field_name),
            )
        preparation_runtime = dict(self.preparation_runtime_identity)
        if (
            not preparation_runtime
            or _canonical_sha256(preparation_runtime)
            != self.preparation_runtime_identity_sha256
        ):
            raise PoseBustersOpenBabelComparisonError(
                "preparation runtime identity is inconsistent"
            )
        object.__setattr__(
            self,
            "preparation_runtime_identity",
            preparation_runtime,
        )
        if not isinstance(
            self.runtime_identity,
            PoseBustersOpenBabelRuntimeIdentity,
        ):
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel runtime identity is missing"
            )
        sources = tuple(self.implementation_source_members)
        if (
            not sources
            or tuple(sorted(sources)) != sources
            or len({name for name, _digest_value in sources}) != len(sources)
        ):
            raise PoseBustersOpenBabelComparisonError(
                "implementation source members are not canonical"
            )
        for name, digest in sources:
            _token(name, name="implementation source member")
            _digest(digest, name="implementation source digest")
        if sources != _implementation_source_members():
            raise PoseBustersOpenBabelComparisonError(
                "implementation source members do not match the current source tree"
            )
        rows = tuple(self.case_rows)
        if (
            not rows
            or tuple(row.case_id for row in rows)
            != tuple(sorted(row.case_id for row in rows))
            or len({row.case_id for row in rows}) != len(rows)
        ):
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel comparison rows must be canonical unique cases"
            )
        expected_metrics = _summary_metrics(rows)
        if tuple(metric.to_dict() for metric in self.metrics) != tuple(
            metric.to_dict() for metric in expected_metrics
        ):
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel comparison metrics are inconsistent"
            )
        object.__setattr__(self, "implementation_source_members", sources)
        object.__setattr__(self, "case_rows", rows)
        object.__setattr__(self, "metrics", expected_metrics)

    @property
    def evaluated_rows(self) -> tuple[PoseBustersOpenBabelCaseComparison, ...]:
        return tuple(row for row in self.case_rows if row.status == "evaluated")

    @property
    def compared_atom_rows(self) -> tuple[PoseBustersOpenBabelAtomComparison, ...]:
        return tuple(
            atom
            for row in self.evaluated_rows
            for atom in row.atom_rows
            if atom.role != "macrocycle_closure_pseudoatom"
        )

    def _payload(self) -> dict[str, Any]:
        compared = self.compared_atom_rows
        deltas = tuple(
            float.fromhex(row.signed_charge_delta_binary64_hex) for row in compared
        )
        if deltas:
            mean_absolute_delta = (
                math.fsum(abs(value) for value in deltas) / len(deltas)
            ).hex()
            root_mean_square_delta = math.sqrt(
                math.fsum(value * value for value in deltas) / len(deltas)
            ).hex()
            maximum_absolute_delta = max(abs(value) for value in deltas).hex()
            signed_mean_delta = (math.fsum(deltas) / len(deltas)).hex()
        else:
            mean_absolute_delta = None
            root_mean_square_delta = None
            maximum_absolute_delta = None
            signed_mean_delta = None
        source_members = dict(self.implementation_source_members)
        return {
            "schema_id": self.schema_id,
            "observation_utc": self.observation_utc,
            "preparation_receipt_sha256": self.preparation_receipt_sha256,
            "preparation_receipt_file_sha256": (
                self.preparation_receipt_file_sha256
            ),
            "preparation_artifact_set_sha256": (
                self.preparation_artifact_set_sha256
            ),
            "preparation_runtime_identity": self.preparation_runtime_identity,
            "preparation_runtime_identity_sha256": (
                self.preparation_runtime_identity_sha256
            ),
            "openbabel_runtime_identity": self.runtime_identity.to_dict(),
            "openbabel_runtime_identity_sha256": (
                self.runtime_identity.fingerprint_sha256
            ),
            "implementation_source_members": source_members,
            "implementation_source_sha256": _canonical_sha256(source_members),
            "configuration": POSEBUSTERS_OPENBABEL_CONFIGURATION,
            "configuration_sha256": self.configuration_sha256,
            "all_case_denominator": len(self.case_rows),
            "prepared_case_count": sum(
                row.preparation_status == "prepared" for row in self.case_rows
            ),
            "comparison_attempted_case_count": sum(
                row.comparison_attempted for row in self.case_rows
            ),
            "evaluated_case_count": len(self.evaluated_rows),
            "comparison_failure_case_count": sum(
                row.status == "comparison_failure" for row in self.case_rows
            ),
            "chemistry_scope_abstention_case_count": sum(
                row.status == "abstain_chemistry_scope" for row in self.case_rows
            ),
            "preparation_failure_blocked_case_count": sum(
                row.status == "blocked_preparation_failure"
                for row in self.case_rows
            ),
            "upstream_failure_blocked_case_count": sum(
                row.status == "blocked_upstream_failure" for row in self.case_rows
            ),
            "compared_real_pdbqt_atom_count": len(compared),
            "macrocycle_pseudoatom_excluded_count": sum(
                row.pseudoatom_count for row in self.evaluated_rows
            ),
            "ad4_atom_type_exact_match_count": sum(
                row.ad4_atom_type_exact_match is True for row in compared
            ),
            "ad4_atom_type_mismatch_count": sum(
                row.ad4_atom_type_exact_match is False for row in compared
            ),
            "ad4_atom_type_pair_counts": [
                {
                    "meeko_ad4_atom_type": meeko_type,
                    "openbabel_ad4_atom_type": openbabel_type,
                    "count": count,
                }
                for meeko_type, openbabel_type, count in _type_pair_counts(compared)
            ],
            "mean_absolute_charge_delta_binary64_hex": mean_absolute_delta,
            "root_mean_square_charge_delta_binary64_hex": (
                root_mean_square_delta
            ),
            "maximum_absolute_charge_delta_binary64_hex": (
                maximum_absolute_delta
            ),
            "signed_mean_charge_delta_binary64_hex": signed_mean_delta,
            "charge_accuracy_threshold_preregistered": False,
            "charge_accuracy_pass": None,
            "case_rows": [row.to_dict() for row in self.case_rows],
            "metrics": [row.to_dict() for row in self.metrics],
            "independent_external_charge_implementation_comparison_performed": (
                len(self.evaluated_rows) > 0
            ),
            "independent_external_ad4_type_implementation_comparison_performed": (
                len(self.evaluated_rows) > 0
            ),
            "independent_charge_oracle_executed": False,
            "benchmark_executed": False,
            "scientific_blockers": list(POSEBUSTERS_OPENBABEL_SCIENTIFIC_BLOCKERS),
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


def materialize_posebusters_openbabel_charge_type_comparison(
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    openbabel_wheel_path: str | os.PathLike[str],
    *,
    expected_preparation_receipt_sha256: str,
    expected_openbabel_wheel_sha256: str,
    observation_utc: str,
) -> PoseBustersOpenBabelComparisonReceipt:
    try:
        preparation, prepared_payloads = _load_preparation_receipt(
            preparation_receipt_path,
            preparation_artifact_root,
            expected_receipt_sha256=expected_preparation_receipt_sha256,
        )
    except PoseBustersVinaExecutionError as exc:
        raise PoseBustersOpenBabelComparisonError(
            "external-preparation receipt failed exact verification"
        ) from exc
    runtime = _load_openbabel_runtime(
        openbabel_wheel_path,
        expected_wheel_sha256=expected_openbabel_wheel_sha256,
    )
    rows = tuple(
        _compare_case(prepared, prepared_payloads, runtime)
        for prepared in preparation.case_rows
    )
    sources = _implementation_source_members()
    return PoseBustersOpenBabelComparisonReceipt(
        observation_utc=observation_utc,
        preparation_receipt_sha256=preparation.receipt_sha256,
        preparation_receipt_file_sha256=preparation.receipt_file_sha256,
        preparation_artifact_set_sha256=preparation.artifact_set_sha256,
        preparation_runtime_identity=preparation.runtime_identity,
        preparation_runtime_identity_sha256=(preparation.runtime_identity_sha256),
        runtime_identity=runtime.identity,
        implementation_source_members=sources,
        case_rows=rows,
        metrics=_summary_metrics(rows),
    )


def _read_canonical_receipt(
    receipt_path: str | os.PathLike[str],
    *,
    expected_receipt_sha256: str,
) -> tuple[dict[str, Any], bytes]:
    expected = _digest(expected_receipt_sha256, name="expected receipt")
    source = _read_exact_regular_file(
        receipt_path,
        maximum_bytes=POSEBUSTERS_OPENBABEL_MAX_RECEIPT_BYTES,
    )
    try:
        metadata = Path(receipt_path).stat(follow_symlinks=False)
    except OSError as exc:
        raise PoseBustersOpenBabelComparisonError(
            "Open Babel comparison receipt metadata is unavailable"
        ) from exc
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise PoseBustersOpenBabelComparisonError(
            "Open Babel comparison receipt must remain mode 0600"
        )
    try:
        raw = json.loads(source)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PoseBustersOpenBabelComparisonError(
            "Open Babel comparison receipt is not canonical JSON"
        ) from exc
    if not isinstance(raw, dict) or source != _canonical_bytes(raw) + b"\n":
        raise PoseBustersOpenBabelComparisonError(
            "Open Babel comparison receipt bytes are not canonical"
        )
    receipt_sha = raw.get("receipt_sha256")
    payload = dict(raw)
    payload.pop("receipt_sha256", None)
    if (
        raw.get("schema_id") != POSEBUSTERS_OPENBABEL_COMPARISON_SCHEMA_ID
        or not isinstance(receipt_sha, str)
        or _canonical_sha256(payload) != receipt_sha
        or receipt_sha != expected
        or raw.get("configuration_sha256")
        != POSEBUSTERS_OPENBABEL_CONFIGURATION_SHA256
    ):
        raise PoseBustersOpenBabelComparisonError(
            "Open Babel comparison receipt fingerprint or contract is invalid"
        )
    return raw, source


def verify_posebusters_openbabel_charge_type_comparison_receipt(
    receipt_path: str | os.PathLike[str],
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    openbabel_wheel_path: str | os.PathLike[str],
    *,
    expected_receipt_sha256: str,
    expected_preparation_receipt_sha256: str,
    expected_openbabel_wheel_sha256: str,
) -> PoseBustersOpenBabelComparisonReceipt:
    raw, source = _read_canonical_receipt(
        receipt_path,
        expected_receipt_sha256=expected_receipt_sha256,
    )
    expected = materialize_posebusters_openbabel_charge_type_comparison(
        preparation_receipt_path,
        preparation_artifact_root,
        openbabel_wheel_path,
        expected_preparation_receipt_sha256=(
            expected_preparation_receipt_sha256
        ),
        expected_openbabel_wheel_sha256=expected_openbabel_wheel_sha256,
        observation_utc=raw.get("observation_utc"),
    )
    if source != _canonical_bytes(expected.to_dict()) + b"\n":
        raise PoseBustersOpenBabelComparisonError(
            "Open Babel comparison failed exact source-tree reexecution"
        )
    return expected


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2-posebusters-openbabel-compare",
        description=(
            "Create a failure-inclusive independent Open Babel charge and "
            "PDBQT AD4-type comparison without claiming a scientific oracle."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("observe", "verify"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--preparation-receipt", required=True)
        subparser.add_argument("--preparation-artifact-root", required=True)
        subparser.add_argument(
            "--expected-preparation-receipt-sha256",
            required=True,
        )
        subparser.add_argument("--openbabel-wheel", required=True)
        subparser.add_argument(
            "--expected-openbabel-wheel-sha256",
            required=True,
        )
    observe = subparsers.choices["observe"]
    observe.add_argument("--observation-utc", required=True)
    observe.add_argument("--output", required=True)
    verify = subparsers.choices["verify"]
    verify.add_argument("--comparison-receipt", required=True)
    verify.add_argument("--expected-comparison-receipt-sha256", required=True)
    return parser


def _summary(receipt: PoseBustersOpenBabelComparisonReceipt) -> dict[str, Any]:
    payload = receipt.to_dict()
    return {
        "receipt_sha256": receipt.fingerprint_sha256,
        "all_case_denominator": payload["all_case_denominator"],
        "evaluated_case_count": payload["evaluated_case_count"],
        "comparison_failure_case_count": payload[
            "comparison_failure_case_count"
        ],
        "compared_real_pdbqt_atom_count": payload[
            "compared_real_pdbqt_atom_count"
        ],
        "ad4_atom_type_exact_match_count": payload[
            "ad4_atom_type_exact_match_count"
        ],
        "ad4_atom_type_mismatch_count": payload[
            "ad4_atom_type_mismatch_count"
        ],
        "mean_absolute_charge_delta_binary64_hex": payload[
            "mean_absolute_charge_delta_binary64_hex"
        ],
        "root_mean_square_charge_delta_binary64_hex": payload[
            "root_mean_square_charge_delta_binary64_hex"
        ],
        "maximum_absolute_charge_delta_binary64_hex": payload[
            "maximum_absolute_charge_delta_binary64_hex"
        ],
        "charge_accuracy_threshold_preregistered": False,
        "independent_charge_oracle_executed": False,
        "claim_safe": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "observe":
        if Path(args.output).exists():
            raise PoseBustersOpenBabelComparisonError(
                "Open Babel comparison output already exists"
            )
        receipt = materialize_posebusters_openbabel_charge_type_comparison(
            args.preparation_receipt,
            args.preparation_artifact_root,
            args.openbabel_wheel,
            expected_preparation_receipt_sha256=(
                args.expected_preparation_receipt_sha256
            ),
            expected_openbabel_wheel_sha256=(
                args.expected_openbabel_wheel_sha256
            ),
            observation_utc=args.observation_utc,
        )
        receipt.write_json(args.output)
    else:
        receipt = verify_posebusters_openbabel_charge_type_comparison_receipt(
            args.comparison_receipt,
            args.preparation_receipt,
            args.preparation_artifact_root,
            args.openbabel_wheel,
            expected_receipt_sha256=(
                args.expected_comparison_receipt_sha256
            ),
            expected_preparation_receipt_sha256=(
                args.expected_preparation_receipt_sha256
            ),
            expected_openbabel_wheel_sha256=(
                args.expected_openbabel_wheel_sha256
            ),
        )
    print(json.dumps(_summary(receipt), sort_keys=True))
    return 0


__all__ = [
    "POSEBUSTERS_OPENBABEL_ATOM_COMPARISON_SCHEMA_ID",
    "POSEBUSTERS_OPENBABEL_CASE_COMPARISON_SCHEMA_ID",
    "POSEBUSTERS_OPENBABEL_COMPARISON_SCHEMA_ID",
    "POSEBUSTERS_OPENBABEL_CONFIGURATION",
    "POSEBUSTERS_OPENBABEL_CONFIGURATION_SHA256",
    "POSEBUSTERS_OPENBABEL_METRIC_SCHEMA_ID",
    "POSEBUSTERS_OPENBABEL_RUNTIME_PAYLOAD_SCHEMA_ID",
    "POSEBUSTERS_OPENBABEL_RUNTIME_SCHEMA_ID",
    "POSEBUSTERS_OPENBABEL_SCIENTIFIC_BLOCKERS",
    "POSEBUSTERS_OPENBABEL_SOURCE_COMMIT",
    "POSEBUSTERS_OPENBABEL_VERSION",
    "POSEBUSTERS_OPENBABEL_WHEEL_FILENAME",
    "POSEBUSTERS_OPENBABEL_WHEEL_SHA256",
    "PoseBustersOpenBabelAtomComparison",
    "PoseBustersOpenBabelCaseComparison",
    "PoseBustersOpenBabelComparisonError",
    "PoseBustersOpenBabelComparisonReceipt",
    "PoseBustersOpenBabelMetric",
    "PoseBustersOpenBabelRuntimeIdentity",
    "PoseBustersOpenBabelRuntimePayload",
    "main",
    "materialize_posebusters_openbabel_charge_type_comparison",
    "verify_posebusters_openbabel_charge_type_comparison_receipt",
]


if __name__ == "__main__":
    raise SystemExit(main())
