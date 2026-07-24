"""Pinned OpenMM Reference adapter for offline S0 evidence.

The module intentionally does not import OpenMM at import time.  The optional
solver is loaded only by an explicit offline observation call, and only the
``Reference`` platform is accepted.  No product route imports this package.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from importlib import import_module, metadata
import json
import math
import os
from pathlib import Path
import platform as host_platform
import stat
import struct
import sys
from typing import Any, Mapping, Sequence

from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    canonical_system_sha256,
    canonical_topology_sha256,
)
from betelgeuze_engine_v2.physics.reference_forcefield_v2 import (
    ReferenceForceFieldV2Parameters,
)
from betelgeuze_engine_v2.physics.reference_parameters import (
    COULOMB_KCAL_ANGSTROM_PER_MOL_E2,
    ReferenceForceFieldParameters,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_materializer import (
    cpu_minimization_validation_materialization_manifest_document,
    materialize_frozen_cpu_minimization_validation_case,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_protocol import (
    cpu_minimization_validation_protocol_document,
)
from betelgeuze_engine_v2.physics.reference_solvation import (
    FixedBornPolarSolvationParameters,
)
from betelgeuze_engine_v2.physics.reference_validation_materializer import (
    materialize_frozen_reference_validation_case,
    reference_validation_materialization_manifest_document,
)
from betelgeuze_engine_v2.physics.reference_validation_protocol import (
    frozen_cpu_reference_validation_protocol,
)


OPENMM_REFERENCE_OFFLINE_ORACLE_ID = "engine_v2_openmm_reference_offline_oracle/1.0.0"
OPENMM_REFERENCE_MAPPING_CONTRACT_SCHEMA_ID = (
    "betelgeuze.engine_v2_openmm_reference_mapping_contract/1.3.0"
)
OPENMM_REFERENCE_MAPPING_CONTRACT_VERSION = "1.3.0"
OPENMM_REFERENCE_RUNTIME_IDENTITY_SCHEMA_ID = (
    "betelgeuze.engine_v2_openmm_reference_runtime_identity/1.0.0"
)
OPENMM_REFERENCE_EVALUATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_openmm_reference_evaluation/1.0.0"
)
OPENMM_REFERENCE_NATIVE_MINIMIZATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_openmm_reference_native_minimization_endpoint/2.0.0"
)
OPENMM_REFERENCE_REQUIRED_DISTRIBUTION_NAME = "OpenMM"
OPENMM_REFERENCE_REQUIRED_DISTRIBUTION_VERSION = "8.4.0.post2"
OPENMM_REFERENCE_REQUIRED_FULL_VERSION = "8.4.0.dev-4768436"
OPENMM_REFERENCE_REQUIRED_GIT_REVISION = "47684368dbbe4185d068be77d32a962059cfc37c"
OPENMM_REFERENCE_REQUIRED_PLATFORM = "Reference"
OPENMM_REFERENCE_ENERGY_MAX_RMS_THRESHOLD_KCAL_PER_MOL = 1.0e-10
OPENMM_REFERENCE_FORCE_MAX_RMS_THRESHOLD_KCAL_PER_MOL_ANGSTROM = 1.0e-8
OPENMM_REFERENCE_MAX_DISTRIBUTION_FILES = 2_048
OPENMM_REFERENCE_MAX_DISTRIBUTION_BYTES = 1024**3
OPENMM_REFERENCE_MAX_FILE_BYTES = 256 * 1024**2
OPENMM_REFERENCE_MAX_ATOMS = 16

_KJ_PER_KCAL = 4.184
_NM_PER_ANGSTROM = 0.1
_KJ_PER_NM_TO_KCAL_PER_ANGSTROM = 41.84

OPENMM_REFERENCE_FORCE_GROUPS = (
    ("harmonic_bond", 0, "HarmonicBondForce"),
    ("harmonic_angle", 1, "HarmonicAngleForce"),
    ("periodic_torsion", 2, "PeriodicTorsionForce"),
    ("lennard_jones", 3, "CustomBondForce"),
    ("screened_coulomb", 4, "CustomBondForce"),
    ("harmonic_out_of_plane_improper", 5, "CustomCompoundBondForce"),
    ("fixed_born_self_polar", 6, "CustomExternalForce"),
    ("fixed_born_pair_polar", 7, "CustomBondForce"),
)

_SWITCH_COORDINATE = "min(1,max(0,(r-rs)/(rc-rs)))"
OPENMM_REFERENCE_LJ_EXPRESSION = (
    "scale*4*epsilon*((sigma/r)^12-(sigma/r)^6)*"
    f"(1-10*({_SWITCH_COORDINATE})^3+15*({_SWITCH_COORDINATE})^4-"
    f"6*({_SWITCH_COORDINATE})^5)"
)
OPENMM_REFERENCE_SCREENED_COULOMB_EXPRESSION = (
    "scale*coulomb*qprod*exp(-kappa*r)/(dielectric*r)*"
    f"(1-10*({_SWITCH_COORDINATE})^3+15*({_SWITCH_COORDINATE})^4-"
    f"6*({_SWITCH_COORDINATE})^5)"
)
OPENMM_REFERENCE_IMPROPER_EXPRESSION = (
    "0.5*k*(asin(min(1,max(-1,sraw)))-theta0)^2;"
    "sraw=dotprod/sqrt(out2*normal2);"
    "dotprod=ox*nx+oy*ny+oz*nz;"
    "out2=ox*ox+oy*oy+oz*oz;"
    "normal2=nx*nx+ny*ny+nz*nz;"
    "nx=aiy*ajz-aiz*ajy;"
    "ny=aiz*ajx-aix*ajz;"
    "nz=aix*ajy-aiy*ajx;"
    "aix=x2-x1;aiy=y2-y1;aiz=z2-z1;"
    "ajx=x3-x1;ajy=y3-y1;ajz=z3-z1;"
    "ox=x4-x1;oy=y4-y1;oz=z4-z1"
)
OPENMM_REFERENCE_FIXED_BORN_SELF_EXPRESSION = "coefficient*q*q/alpha"
OPENMM_REFERENCE_FIXED_BORN_PAIR_EXPRESSION = (
    "coefficient*2*qprod/sqrt(r^2+alpha_product*exp(-r^2/(4*alpha_product)))"
)

# The legacy hash remains a verifiable lineage anchor for the mapping bound to
# CPU minimization protocol 2.1.0.
FROZEN_LEGACY_OPENMM_REFERENCE_MAPPING_CONTRACT_SHA256_V1 = (
    "0bfc077eded6637ac4cec41fa863ead9bec16ad6665758e1642d12abfb958b43"
)
FROZEN_LEGACY_OPENMM_REFERENCE_MAPPING_CONTRACT_SHA256_V1_1 = (
    "6b55bdcf50d398ee0d62f5093f2cdf903ea384da6fd4d257633200923840c3c0"
)

# Filled after the 1.1 projection was reviewed.  The hash binds protocol and
# materializer identities, every 27/59 disposition, expressions, groups, and
# predefined thresholds.  It does not contain any observed result.
FROZEN_LEGACY_OPENMM_REFERENCE_MAPPING_CONTRACT_SHA256_V1_2 = (
    "342b8b8538b92875ede9399833561a3987c55bf7ea7384c87ea2f10ddfddbc97"
)
FROZEN_OPENMM_REFERENCE_MAPPING_CONTRACT_SHA256 = (
    "4f0163ff1ef9630d2fcac730cacae8ce6237ae0bf0ad53e031b93e17acc5eeda"
)


class OpenMMReferenceOfflineOracleError(RuntimeError):
    """The pinned offline OpenMM mapping or identity is unavailable."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise OpenMMReferenceOfflineOracleError(
            "OpenMM reference payload is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    digest = str(value)
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise OpenMMReferenceOfflineOracleError(
            f"{name} must be a lowercase SHA-256 digest"
        )
    return digest


def _finite(value: object, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OpenMMReferenceOfflineOracleError(f"{name} must be a real number")
    result = float(value)
    if not math.isfinite(result):
        raise OpenMMReferenceOfflineOracleError(f"{name} must be finite")
    return result


def _hash_regular_file(
    path: Path,
    *,
    maximum_bytes: int = OPENMM_REFERENCE_MAX_FILE_BYTES,
) -> tuple[str, int]:
    try:
        before = path.lstat()
    except OSError as exc:
        raise OpenMMReferenceOfflineOracleError(
            "OpenMM dependency file is unavailable"
        ) from exc
    if path.is_symlink() or not stat.S_ISREG(before.st_mode):
        raise OpenMMReferenceOfflineOracleError(
            "OpenMM dependency entry is not a regular non-symlink file"
        )
    if before.st_size < 0 or before.st_size > maximum_bytes:
        raise OpenMMReferenceOfflineOracleError(
            "OpenMM dependency file exceeds its byte bound"
        )
    digest = hashlib.sha256()
    observed = 0
    try:
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(min(1024 * 1024, before.st_size + 1 - observed))
                if not chunk:
                    break
                observed += len(chunk)
                if observed > before.st_size:
                    raise OpenMMReferenceOfflineOracleError(
                        "OpenMM dependency file changed while being hashed"
                    )
                digest.update(chunk)
        after = path.stat()
    except OSError as exc:
        raise OpenMMReferenceOfflineOracleError(
            "OpenMM dependency file cannot be read"
        ) from exc
    if observed != before.st_size or (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    ) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ):
        raise OpenMMReferenceOfflineOracleError(
            "OpenMM dependency file changed while being hashed"
        )
    return digest.hexdigest(), observed


def _require_openmm_reference() -> tuple[Any, Any, Any]:
    try:
        distribution = metadata.distribution("openmm")
        openmm = import_module("openmm")
        openmm_unit = import_module("openmm.unit")
    except (ImportError, metadata.PackageNotFoundError) as exc:
        raise OpenMMReferenceOfflineOracleError(
            "the pinned OpenMM distribution is unavailable"
        ) from exc
    if distribution.metadata.get("Name") != OPENMM_REFERENCE_REQUIRED_DISTRIBUTION_NAME:
        raise OpenMMReferenceOfflineOracleError("OpenMM distribution name drifted")
    if distribution.version != OPENMM_REFERENCE_REQUIRED_DISTRIBUTION_VERSION:
        raise OpenMMReferenceOfflineOracleError("OpenMM distribution version drifted")
    version = getattr(openmm, "version", None)
    if (
        version is None
        or getattr(version, "full_version", None)
        != OPENMM_REFERENCE_REQUIRED_FULL_VERSION
        or getattr(version, "git_revision", None)
        != OPENMM_REFERENCE_REQUIRED_GIT_REVISION
    ):
        raise OpenMMReferenceOfflineOracleError("OpenMM native build identity drifted")
    platform_names = tuple(
        openmm.Platform.getPlatform(index).getName()
        for index in range(openmm.Platform.getNumPlatforms())
    )
    if OPENMM_REFERENCE_REQUIRED_PLATFORM not in platform_names:
        raise OpenMMReferenceOfflineOracleError(
            "the OpenMM Reference platform is unavailable"
        )
    reference = openmm.Platform.getPlatformByName(OPENMM_REFERENCE_REQUIRED_PLATFORM)
    if reference.getName() != OPENMM_REFERENCE_REQUIRED_PLATFORM:
        raise OpenMMReferenceOfflineOracleError(
            "OpenMM platform selection did not resolve to Reference"
        )
    return openmm, openmm_unit, reference


def observe_openmm_reference_runtime_identity() -> dict[str, Any]:
    """Hash the exact installed OpenMM wheel payload and active Python runtime."""

    openmm, _, reference = _require_openmm_reference()
    distribution = metadata.distribution("openmm")
    root = Path(distribution.locate_file("")).resolve(strict=True)
    paths = tuple(distribution.files or ())
    if not paths or len(paths) > OPENMM_REFERENCE_MAX_DISTRIBUTION_FILES:
        raise OpenMMReferenceOfflineOracleError(
            "OpenMM distribution file manifest is missing or exceeds its bound"
        )
    rows: list[dict[str, object]] = []
    total_bytes = 0
    previous = ""
    for package_path in sorted(paths, key=lambda item: str(item)):
        relative = str(package_path).replace(os.sep, "/")
        if (
            not relative
            or relative <= previous
            or relative.startswith("/")
            or "\\" in relative
        ):
            raise OpenMMReferenceOfflineOracleError(
                "OpenMM distribution path manifest is not canonical"
            )
        previous = relative
        path = Path(distribution.locate_file(package_path))
        try:
            resolved = path.resolve(strict=True)
        except OSError as exc:
            raise OpenMMReferenceOfflineOracleError(
                "OpenMM distribution payload is unavailable"
            ) from exc
        if not resolved.is_relative_to(root):
            raise OpenMMReferenceOfflineOracleError(
                "OpenMM distribution payload escaped its installation root"
            )
        digest, size = _hash_regular_file(resolved)
        total_bytes += size
        if total_bytes > OPENMM_REFERENCE_MAX_DISTRIBUTION_BYTES:
            raise OpenMMReferenceOfflineOracleError(
                "OpenMM distribution exceeds its aggregate byte bound"
            )
        rows.append({"path": relative, "sha256": digest, "size": size})

    wrapper_path = Path(openmm.__file__).resolve(strict=True)
    native_module = import_module("openmm._openmm")
    native_path = Path(native_module.__file__).resolve(strict=True)
    path_rows = {str(row["path"]): row for row in rows}

    def critical_row(path: Path, *, name: str) -> dict[str, object]:
        try:
            relative = path.relative_to(root).as_posix()
            row = path_rows[relative]
        except (ValueError, KeyError) as exc:
            raise OpenMMReferenceOfflineOracleError(
                f"OpenMM {name} is not bound by its distribution manifest"
            ) from exc
        return dict(row)

    python_digest, python_size = _hash_regular_file(
        Path(sys.executable).resolve(strict=True)
    )
    distribution_projection = {
        "distribution_name": distribution.metadata.get("Name"),
        "distribution_version": distribution.version,
        "file_count": len(rows),
        "total_bytes": total_bytes,
        "files": rows,
    }
    environment = {
        "python_version": host_platform.python_version(),
        "python_implementation": host_platform.python_implementation(),
        "python_cache_tag": sys.implementation.cache_tag,
        "python_byteorder": sys.byteorder,
        "python_executable": {
            "basename": Path(sys.executable).name,
            "sha256": python_digest,
            "size": python_size,
        },
        "operating_system": host_platform.system(),
        "kernel_release": host_platform.release(),
        "machine": host_platform.machine(),
        "libc": list(host_platform.libc_ver()),
    }
    projection = {
        "schema_id": OPENMM_REFERENCE_RUNTIME_IDENTITY_SCHEMA_ID,
        "oracle_id": OPENMM_REFERENCE_OFFLINE_ORACLE_ID,
        "distribution": {
            **distribution_projection,
            "manifest_sha256": _sha256(distribution_projection),
        },
        "native_build": {
            "full_version": openmm.version.full_version,
            "short_version": openmm.version.short_version,
            "git_revision": openmm.version.git_revision,
            "release_build": bool(openmm.version.release),
            "openmm_library_api_version": openmm.Platform.getOpenMMVersion(),
            "python_wrapper": critical_row(wrapper_path, name="Python wrapper"),
            "native_extension": critical_row(native_path, name="native extension"),
        },
        "platform": {
            "selected_name": reference.getName(),
            "available_names": [
                openmm.Platform.getPlatform(index).getName()
                for index in range(openmm.Platform.getNumPlatforms())
            ],
            "property_names": list(reference.getPropertyNames()),
            "cpu_substitution_allowed": False,
        },
        "environment": environment,
        "environment_sha256": _sha256(environment),
        "path_values_disclosed": False,
        "scientifically_validated": False,
        "claim_safe": False,
    }
    return {**projection, "runtime_identity_sha256": _sha256(projection)}


def require_openmm_reference_runtime_identity_document(
    value: Mapping[str, Any],
    *,
    reobserve: bool = False,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise OpenMMReferenceOfflineOracleError(
            "OpenMM runtime identity must be a mapping"
        )
    observed = json.loads(_canonical_bytes(dict(value)).decode("ascii"))
    if set(observed) != {
        "schema_id",
        "oracle_id",
        "distribution",
        "native_build",
        "platform",
        "environment",
        "environment_sha256",
        "path_values_disclosed",
        "scientifically_validated",
        "claim_safe",
        "runtime_identity_sha256",
    }:
        raise OpenMMReferenceOfflineOracleError(
            "OpenMM runtime identity fields are invalid"
        )
    digest = _require_sha256(
        observed.get("runtime_identity_sha256"),
        name="runtime identity",
    )
    projection = {
        key: item for key, item in observed.items() if key != "runtime_identity_sha256"
    }
    if digest != _sha256(projection):
        raise OpenMMReferenceOfflineOracleError(
            "OpenMM runtime identity digest mismatch"
        )
    distribution = observed.get("distribution")
    native = observed.get("native_build")
    platform_identity = observed.get("platform")
    if not all(
        isinstance(item, dict) for item in (distribution, native, platform_identity)
    ):
        raise OpenMMReferenceOfflineOracleError(
            "OpenMM runtime identity nested fields are invalid"
        )
    if (
        observed.get("schema_id") != OPENMM_REFERENCE_RUNTIME_IDENTITY_SCHEMA_ID
        or observed.get("oracle_id") != OPENMM_REFERENCE_OFFLINE_ORACLE_ID
        or platform_identity.get("selected_name") != OPENMM_REFERENCE_REQUIRED_PLATFORM
        or distribution.get("distribution_version")
        != OPENMM_REFERENCE_REQUIRED_DISTRIBUTION_VERSION
        or distribution.get("distribution_name")
        != OPENMM_REFERENCE_REQUIRED_DISTRIBUTION_NAME
        or native.get("full_version") != OPENMM_REFERENCE_REQUIRED_FULL_VERSION
        or native.get("git_revision") != OPENMM_REFERENCE_REQUIRED_GIT_REVISION
        or observed.get("path_values_disclosed") is not False
        or observed.get("scientifically_validated") is not False
        or observed.get("claim_safe") is not False
    ):
        raise OpenMMReferenceOfflineOracleError(
            "OpenMM runtime identity does not match the frozen solver"
        )
    if set(distribution) != {
        "distribution_name",
        "distribution_version",
        "file_count",
        "total_bytes",
        "files",
        "manifest_sha256",
    }:
        raise OpenMMReferenceOfflineOracleError(
            "OpenMM distribution identity fields are invalid"
        )
    manifest_digest = _require_sha256(
        distribution.get("manifest_sha256"),
        name="OpenMM distribution manifest",
    )
    manifest_projection = {
        key: item for key, item in distribution.items() if key != "manifest_sha256"
    }
    files = distribution.get("files")
    if (
        manifest_digest != _sha256(manifest_projection)
        or not isinstance(files, list)
        or not files
        or len(files) > OPENMM_REFERENCE_MAX_DISTRIBUTION_FILES
        or distribution.get("file_count") != len(files)
    ):
        raise OpenMMReferenceOfflineOracleError(
            "OpenMM distribution manifest digest or coverage is invalid"
        )
    previous = ""
    total_bytes = 0
    file_map: dict[str, dict[str, object]] = {}
    for row in files:
        if not isinstance(row, dict) or set(row) != {"path", "sha256", "size"}:
            raise OpenMMReferenceOfflineOracleError(
                "OpenMM distribution file row is invalid"
            )
        path = row.get("path")
        size = row.get("size")
        if (
            not isinstance(path, str)
            or not path
            or path <= previous
            or path.startswith("/")
            or "\\" in path
            or any(part in {"", ".", ".."} for part in path.split("/"))
            or isinstance(size, bool)
            or not isinstance(size, int)
            or size < 0
            or size > OPENMM_REFERENCE_MAX_FILE_BYTES
        ):
            raise OpenMMReferenceOfflineOracleError(
                "OpenMM distribution file row is invalid"
            )
        previous = path
        total_bytes += size
        _require_sha256(row.get("sha256"), name="OpenMM distribution file")
        file_map[path] = row
    if (
        total_bytes != distribution.get("total_bytes")
        or total_bytes > OPENMM_REFERENCE_MAX_DISTRIBUTION_BYTES
    ):
        raise OpenMMReferenceOfflineOracleError(
            "OpenMM distribution byte coverage is invalid"
        )
    if (
        set(native)
        != {
            "full_version",
            "short_version",
            "git_revision",
            "release_build",
            "openmm_library_api_version",
            "python_wrapper",
            "native_extension",
        }
        or native.get("short_version") != "8.4.0"
        or native.get("release_build") is not False
        or native.get("openmm_library_api_version") != "8.4"
    ):
        raise OpenMMReferenceOfflineOracleError("OpenMM native build fields drifted")
    for key in ("python_wrapper", "native_extension"):
        critical = native.get(key)
        if (
            not isinstance(critical, dict)
            or file_map.get(str(critical.get("path"))) != critical
        ):
            raise OpenMMReferenceOfflineOracleError(
                "OpenMM critical binary identity is not bound to the manifest"
            )
    environment = observed.get("environment")
    if (
        not isinstance(environment, dict)
        or set(environment)
        != {
            "python_version",
            "python_implementation",
            "python_cache_tag",
            "python_byteorder",
            "python_executable",
            "operating_system",
            "kernel_release",
            "machine",
            "libc",
        }
        or observed.get("environment_sha256") != _sha256(environment)
    ):
        raise OpenMMReferenceOfflineOracleError(
            "OpenMM environment identity digest mismatch"
        )
    python_executable = environment.get("python_executable")
    if (
        not isinstance(python_executable, dict)
        or set(python_executable) != {"basename", "sha256", "size"}
        or not isinstance(python_executable.get("basename"), str)
        or not python_executable["basename"]
        or isinstance(python_executable.get("size"), bool)
        or not isinstance(python_executable.get("size"), int)
        or python_executable["size"] <= 0
        or python_executable["size"] > OPENMM_REFERENCE_MAX_FILE_BYTES
    ):
        raise OpenMMReferenceOfflineOracleError(
            "OpenMM Python executable identity is invalid"
        )
    _require_sha256(
        python_executable.get("sha256"),
        name="OpenMM Python executable",
    )
    if (
        set(platform_identity)
        != {
            "selected_name",
            "available_names",
            "property_names",
            "cpu_substitution_allowed",
        }
        or platform_identity.get("cpu_substitution_allowed") is not False
        or not isinstance(platform_identity.get("available_names"), list)
        or not isinstance(platform_identity.get("property_names"), list)
        or any(
            not isinstance(item, str)
            for item in (
                platform_identity["available_names"]
                + platform_identity["property_names"]
            )
        )
        or OPENMM_REFERENCE_REQUIRED_PLATFORM
        not in platform_identity["available_names"]
        or len(set(platform_identity["available_names"]))
        != len(platform_identity["available_names"])
    ):
        raise OpenMMReferenceOfflineOracleError("OpenMM platform identity is invalid")
    if reobserve and observed != observe_openmm_reference_runtime_identity():
        raise OpenMMReferenceOfflineOracleError(
            "OpenMM runtime identity does not match the active environment"
        )
    return observed


def _atom_order_rows(system: AllAtomSystem) -> list[dict[str, object]]:
    rows = [
        {
            "ordinal": ordinal,
            "atom_index": atom.index,
            "name": atom.name,
            "element": atom.element,
            "atomic_number": atom.atomic_number,
            "residue_index": atom.residue_index,
        }
        for ordinal, atom in enumerate(system.atoms)
    ]
    if any(row["ordinal"] != row["atom_index"] for row in rows):
        raise OpenMMReferenceOfflineOracleError(
            "OpenMM mapping requires atom indices to equal canonical order"
        )
    return rows


def atom_order_sha256(system: AllAtomSystem) -> str:
    return _sha256({"atom_order": _atom_order_rows(system)})


def _cell_mapping(system: AllAtomSystem) -> dict[str, object]:
    if system.cell is None:
        return {"mode": "nonperiodic", "lengths_angstrom": None}
    try:
        lengths = [
            float(value) for value in system.cell.orthorhombic_lengths().tolist()
        ]
    except (TypeError, ValueError, RuntimeError) as exc:
        raise OpenMMReferenceOfflineOracleError(
            "OpenMM mapping requires an orthorhombic cell"
        ) from exc
    if tuple(system.cell.periodic) != (True, True, True):
        raise OpenMMReferenceOfflineOracleError(
            "OpenMM mapping supports only fully periodic orthorhombic cells"
        )
    return {"mode": "orthorhombic_full_pbc", "lengths_angstrom": lengths}


def _variant_mapping_row(case: Any, variant: Any) -> dict[str, Any]:
    system = variant.system
    parameters = variant.parameters
    base = {
        "variant_id": variant.variant_id,
        "runtime_input_sha256": variant.runtime_input_sha256,
        "system_sha256": canonical_system_sha256(system),
        "topology_sha256": canonical_topology_sha256(system),
        "parameter_fingerprint_sha256": parameters.fingerprint_sha256,
        "atom_count": system.atom_count,
        "atom_order_sha256": atom_order_sha256(system),
        "cell": _cell_mapping(system),
        "excluded_pairs": [list(row) for row in parameters.excluded_pairs],
        "scaled_pairs": [row.to_dict() for row in parameters.scaled_pairs],
    }
    if case.expected_outcome == "fail_closed":
        return {
            **base,
            "disposition": "not_applicable_engine_contract",
            "expected_error_code": case.expected_error_code,
            "openmm_evaluation_allowed": False,
        }
    return {
        **base,
        "disposition": "mapped_openmm_reference",
        "expected_error_code": None,
        "openmm_evaluation_allowed": True,
        "component_force_groups": [
            {
                "component": name,
                "force_group": group,
                "openmm_force_class": force_class,
            }
            for name, group, force_class in OPENMM_REFERENCE_FORCE_GROUPS[:5]
        ],
    }


def _mapping_contract_projection() -> dict[str, Any]:
    protocol = frozen_cpu_reference_validation_protocol()
    materialization = reference_validation_materialization_manifest_document(protocol)
    minimization_protocol = cpu_minimization_validation_protocol_document()
    minimization_materialization = (
        cpu_minimization_validation_materialization_manifest_document(
            minimization_protocol
        )
    )
    case_rows = []
    for case in protocol.cases:
        materialized = materialize_frozen_reference_validation_case(
            case.case_id,
            protocol,
        )
        case_rows.append(
            {
                "case_id": case.case_id,
                "case_input_sha256": case.input_sha256,
                "expected_outcome": case.expected_outcome,
                "expected_error_code": case.expected_error_code,
                "variants": [
                    _variant_mapping_row(materialized, variant)
                    for variant in materialized.variants
                ],
            }
        )
    minimization_case_rows = []
    for case in minimization_protocol["case_manifest"]["cases"]:
        materialized = materialize_frozen_cpu_minimization_validation_case(
            case["case_id"],
            minimization_protocol,
        )
        mapped = case["expected_outcome"] == "pass"
        components = list(OPENMM_REFERENCE_FORCE_GROUPS[:5])
        if materialized.v2_parameters is not None:
            components.append(OPENMM_REFERENCE_FORCE_GROUPS[5])
        if materialized.solvation_parameters is not None:
            components.extend(OPENMM_REFERENCE_FORCE_GROUPS[6:])
        minimization_case_rows.append(
            {
                "case_id": case["case_id"],
                "case_input_sha256": case["input_sha256"],
                "runtime_input_sha256": materialized.runtime_input_sha256,
                "expected_outcome": case["expected_outcome"],
                "expected_error_code": case["expected_error_code"],
                "evaluator_scope": case["evaluator_scope"],
                "disposition": (
                    "mapped_openmm_reference_trace_coordinates"
                    if mapped
                    else "not_applicable_engine_contract"
                ),
                "openmm_evaluation_allowed": mapped,
                "system_sha256": canonical_system_sha256(materialized.system),
                "topology_sha256": canonical_topology_sha256(materialized.system),
                "atom_count": materialized.system.atom_count,
                "atom_order_sha256": atom_order_sha256(materialized.system),
                "cell": _cell_mapping(materialized.system),
                "base_parameter_fingerprint_sha256": (
                    materialized.base_parameters.fingerprint_sha256
                ),
                "v2_parameter_fingerprint_sha256": (
                    None
                    if materialized.v2_parameters is None
                    else materialized.v2_parameters.fingerprint_sha256
                ),
                "solvation_parameter_fingerprint_sha256": (
                    None
                    if materialized.solvation_parameters is None
                    else materialized.solvation_parameters.fingerprint_sha256
                ),
                "constraint_count": (
                    0
                    if materialized.v2_parameters is None
                    else len(materialized.v2_parameters.constraints)
                ),
                "improper_count": (
                    0
                    if materialized.v2_parameters is None
                    else len(materialized.v2_parameters.impropers)
                ),
                "component_force_groups": [
                    {
                        "component": name,
                        "force_group": group,
                        "openmm_force_class": force_class,
                    }
                    for name, group, force_class in components
                ],
            }
        )
    return {
        "schema_id": OPENMM_REFERENCE_MAPPING_CONTRACT_SCHEMA_ID,
        "oracle_id": OPENMM_REFERENCE_OFFLINE_ORACLE_ID,
        "contract_version": OPENMM_REFERENCE_MAPPING_CONTRACT_VERSION,
        "superseded_contract_sha256": (
            FROZEN_LEGACY_OPENMM_REFERENCE_MAPPING_CONTRACT_SHA256_V1_2
        ),
        "legacy_contract_chain_sha256s": [
            FROZEN_LEGACY_OPENMM_REFERENCE_MAPPING_CONTRACT_SHA256_V1_1,
            FROZEN_LEGACY_OPENMM_REFERENCE_MAPPING_CONTRACT_SHA256_V1
        ],
        "refreeze_reason": (
            "bind_energy_force_protocol_1_2_0_and_minimization_protocol_2_2_0"
        ),
        "required_runtime": {
            "distribution_name": OPENMM_REFERENCE_REQUIRED_DISTRIBUTION_NAME,
            "distribution_version": OPENMM_REFERENCE_REQUIRED_DISTRIBUTION_VERSION,
            "full_version": OPENMM_REFERENCE_REQUIRED_FULL_VERSION,
            "git_revision": OPENMM_REFERENCE_REQUIRED_GIT_REVISION,
            "platform": OPENMM_REFERENCE_REQUIRED_PLATFORM,
            "cpu_fallback_allowed": False,
            "customer_runtime_dependency": False,
        },
        "bound_protocols": {
            "energy_force_protocol_sha256": protocol.protocol_sha256,
            "energy_force_fixture_manifest_sha256": protocol.fixture_manifest_sha256,
            "energy_force_materialization_manifest_sha256": materialization[
                "materialization_manifest_sha256"
            ],
            "minimization_protocol_sha256": minimization_protocol["protocol_sha256"],
            "minimization_case_manifest_sha256": minimization_protocol["case_manifest"][
                "case_manifest_sha256"
            ],
            "minimization_materialization_manifest_sha256": (
                minimization_materialization["materialization_manifest_sha256"]
            ),
        },
        "coverage": {
            "case_count": len(case_rows),
            "variant_count": sum(len(row["variants"]) for row in case_rows),
            "mapped_variant_count": sum(
                variant["disposition"] == "mapped_openmm_reference"
                for row in case_rows
                for variant in row["variants"]
            ),
            "not_applicable_engine_contract_variant_count": sum(
                variant["disposition"] == "not_applicable_engine_contract"
                for row in case_rows
                for variant in row["variants"]
            ),
            "skipped_variant_count": 0,
            "all_failure_rows_retained": True,
            "minimization_case_count": len(minimization_case_rows),
            "mapped_minimization_case_count": sum(
                row["openmm_evaluation_allowed"] for row in minimization_case_rows
            ),
            "not_applicable_minimization_case_count": sum(
                not row["openmm_evaluation_allowed"] for row in minimization_case_rows
            ),
        },
        "unit_mapping": {
            "input_coordinates": "angstrom_to_nanometer_exact_factor_0.1",
            "input_energy_parameters": "kcal_per_mol_to_kj_per_mol_exact_factor_4.184",
            "output_energy": "kj_per_mol_to_kcal_per_mol_exact_factor_1_over_4.184",
            "output_force": "kj_per_mol_per_nm_to_kcal_per_mol_per_angstrom_exact_factor_1_over_41.84",
            "atom_order_permutation": "identity",
        },
        "force_mapping": {
            "native_terms": [
                "HarmonicBondForce",
                "HarmonicAngleForce",
                "PeriodicTorsionForce",
            ],
            "custom_terms": {
                "lennard_jones": OPENMM_REFERENCE_LJ_EXPRESSION,
                "screened_coulomb": OPENMM_REFERENCE_SCREENED_COULOMB_EXPRESSION,
                "harmonic_out_of_plane_improper": OPENMM_REFERENCE_IMPROPER_EXPRESSION,
                "fixed_born_self_polar": OPENMM_REFERENCE_FIXED_BORN_SELF_EXPRESSION,
                "fixed_born_pair_polar": OPENMM_REFERENCE_FIXED_BORN_PAIR_EXPRESSION,
            },
            "all_nonbonded_pairs_enumerated": True,
            "excluded_pairs_use_zero_scale": True,
            "scaled_pairs_use_explicit_per_pair_scale": True,
            "quintic_switch_embedded_in_custom_expression": True,
            "force_groups": [
                {
                    "component": name,
                    "force_group": group,
                    "openmm_force_class": force_class,
                }
                for name, group, force_class in OPENMM_REFERENCE_FORCE_GROUPS
            ],
        },
        "predefined_acceptance": {
            "energy_error_max_kcal_per_mol": (
                OPENMM_REFERENCE_ENERGY_MAX_RMS_THRESHOLD_KCAL_PER_MOL
            ),
            "energy_error_rms_kcal_per_mol": (
                OPENMM_REFERENCE_ENERGY_MAX_RMS_THRESHOLD_KCAL_PER_MOL
            ),
            "force_error_max_kcal_per_mol_angstrom": (
                OPENMM_REFERENCE_FORCE_MAX_RMS_THRESHOLD_KCAL_PER_MOL_ANGSTROM
            ),
            "force_error_rms_kcal_per_mol_angstrom": (
                OPENMM_REFERENCE_FORCE_MAX_RMS_THRESHOLD_KCAL_PER_MOL_ANGSTROM
            ),
            "thresholds_predefined_before_observation": True,
            "post_observation_tuning_allowed": False,
        },
        "native_minimization_boundary": {
            "endpoint_benchmark_is_separate": True,
            "algorithm": "OpenMM LocalEnergyMinimizer L-BFGS",
            "engine_armijo_jacobi_trace_equivalence_claimed": False,
            "checkpoint_restart_equality_claimed": False,
        },
        "cases": case_rows,
        "minimization_cases": minimization_case_rows,
        "production_execution_authorized": False,
        "scientific_or_product_promotion_authorized": False,
        "scientifically_validated": False,
        "claim_safe": False,
    }


def openmm_reference_mapping_contract_document() -> dict[str, Any]:
    projection = _mapping_contract_projection()
    document = {**projection, "contract_sha256": _sha256(projection)}
    if (
        FROZEN_OPENMM_REFERENCE_MAPPING_CONTRACT_SHA256
        and document["contract_sha256"]
        != FROZEN_OPENMM_REFERENCE_MAPPING_CONTRACT_SHA256
    ):
        raise OpenMMReferenceOfflineOracleError(
            "frozen OpenMM Reference mapping contract drifted"
        )
    return json.loads(_canonical_bytes(document).decode("ascii"))


def require_openmm_reference_mapping_contract_document(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise OpenMMReferenceOfflineOracleError(
            "OpenMM mapping contract must be a mapping"
        )
    observed = json.loads(_canonical_bytes(dict(value)).decode("ascii"))
    if observed != openmm_reference_mapping_contract_document():
        raise OpenMMReferenceOfflineOracleError(
            "OpenMM mapping contract does not match the frozen document"
        )
    return observed


def _coordinate_rows(
    value: Sequence[Sequence[object]],
    *,
    atom_count: int,
) -> tuple[tuple[float, float, float], ...]:
    try:
        rows = tuple(
            tuple(_finite(item, name="coordinate") for item in row) for row in value
        )
    except TypeError as exc:
        raise OpenMMReferenceOfflineOracleError(
            "coordinates must be a sequence"
        ) from exc
    if len(rows) != atom_count or any(len(row) != 3 for row in rows):
        raise OpenMMReferenceOfflineOracleError(
            "coordinates must have exact [atom,3] shape"
        )
    return tuple((row[0], row[1], row[2]) for row in rows)


def coordinate_f64le_sha256(
    coordinates: Sequence[Sequence[object]],
) -> str:
    rows = _coordinate_rows(coordinates, atom_count=len(coordinates))
    payload = bytearray(8 * 3 * len(rows))
    offset = 0
    for row in rows:
        for value in row:
            struct.pack_into("<d", payload, offset, value)
            offset += 8
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class OpenMMReferenceEvaluation:
    coordinate_f64le_sha256: str
    atom_order_sha256: str
    system_topology_sha256: str
    base_parameter_fingerprint_sha256: str
    v2_parameter_fingerprint_sha256: str | None
    solvation_parameter_fingerprint_sha256: str | None
    component_energies_kcal_per_mol: tuple[tuple[str, float], ...]
    total_energy_kcal_per_mol: float
    forces_kcal_per_mol_angstrom: tuple[tuple[float, float, float], ...]
    evaluation_sha256: str
    schema_id: str = OPENMM_REFERENCE_EVALUATION_SCHEMA_ID

    def projection(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "oracle_id": OPENMM_REFERENCE_OFFLINE_ORACLE_ID,
            "platform": OPENMM_REFERENCE_REQUIRED_PLATFORM,
            "coordinate_f64le_sha256": self.coordinate_f64le_sha256,
            "atom_order_sha256": self.atom_order_sha256,
            "system_topology_sha256": self.system_topology_sha256,
            "base_parameter_fingerprint_sha256": (
                self.base_parameter_fingerprint_sha256
            ),
            "v2_parameter_fingerprint_sha256": (self.v2_parameter_fingerprint_sha256),
            "solvation_parameter_fingerprint_sha256": (
                self.solvation_parameter_fingerprint_sha256
            ),
            "component_energies": [
                {"name": name, "value": value, "unit": "kcal/mol"}
                for name, value in self.component_energies_kcal_per_mol
            ],
            "total_energy": {
                "value": self.total_energy_kcal_per_mol,
                "unit": "kcal/mol",
            },
            "forces": {
                "values": [list(row) for row in self.forces_kcal_per_mol_angstrom],
                "unit": "kcal/mol/angstrom",
                "definition": "negative_coordinate_gradient_of_total_energy",
                "f64le_sha256": coordinate_f64le_sha256(
                    self.forces_kcal_per_mol_angstrom
                ),
            },
            "scientifically_validated": False,
            "claim_safe": False,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.projection(), "evaluation_sha256": self.evaluation_sha256}


class OpenMMReferenceSession:
    """One reusable Reference context for exact static energy/force observations."""

    def __init__(
        self,
        system: AllAtomSystem,
        base_parameters: ReferenceForceFieldParameters,
        *,
        v2_parameters: ReferenceForceFieldV2Parameters | None = None,
        solvation_parameters: FixedBornPolarSolvationParameters | None = None,
    ) -> None:
        if not isinstance(system, AllAtomSystem):
            raise OpenMMReferenceOfflineOracleError("system must be an AllAtomSystem")
        if system.model_count != 1 or system.atom_count > OPENMM_REFERENCE_MAX_ATOMS:
            raise OpenMMReferenceOfflineOracleError(
                "OpenMM offline mapping requires one bounded coordinate model"
            )
        if not isinstance(base_parameters, ReferenceForceFieldParameters):
            raise OpenMMReferenceOfflineOracleError(
                "base_parameters must be ReferenceForceFieldParameters"
            )
        topology = canonical_topology_sha256(system)
        if base_parameters.topology_sha256 != topology:
            raise OpenMMReferenceOfflineOracleError(
                "OpenMM mapping topology identity mismatch"
            )
        if v2_parameters is not None and (
            not isinstance(v2_parameters, ReferenceForceFieldV2Parameters)
            or v2_parameters.base_parameters.fingerprint_sha256
            != base_parameters.fingerprint_sha256
        ):
            raise OpenMMReferenceOfflineOracleError("OpenMM v2 mapping is cross-wired")
        if solvation_parameters is not None:
            if v2_parameters is None:
                raise OpenMMReferenceOfflineOracleError(
                    "fixed Born mapping requires v2 parameters"
                )
            if (
                solvation_parameters.topology_sha256 != topology
                or solvation_parameters.charge_parameter_fingerprint_sha256
                != v2_parameters.fingerprint_sha256
            ):
                raise OpenMMReferenceOfflineOracleError(
                    "OpenMM fixed Born mapping is cross-wired"
                )
        _atom_order_rows(system)
        cell = _cell_mapping(system)
        if (
            cell["mode"] != "nonperiodic"
            and v2_parameters is not None
            and v2_parameters.impropers
        ):
            raise OpenMMReferenceOfflineOracleError(
                "periodic ordered-star improper mapping is outside the frozen scope"
            )
        if cell["mode"] != "nonperiodic" and solvation_parameters is not None:
            raise OpenMMReferenceOfflineOracleError(
                "fixed Born mapping does not support periodic cells"
            )

        openmm, openmm_unit, reference = _require_openmm_reference()
        self._openmm = openmm
        self._unit = openmm_unit
        self._reference = reference
        self._source_system = system
        self._base_parameters = base_parameters
        self._v2_parameters = v2_parameters
        self._solvation_parameters = solvation_parameters
        self._atom_order_sha256 = atom_order_sha256(system)
        self._topology_sha256 = topology
        self._component_groups: list[tuple[str, int]] = []
        self._system = self._build_system()
        self._integrator = openmm.VerletIntegrator(0.001)
        self._context = openmm.Context(
            self._system,
            self._integrator,
            reference,
        )
        if self._context.getPlatform().getName() != OPENMM_REFERENCE_REQUIRED_PLATFORM:
            raise OpenMMReferenceOfflineOracleError(
                "OpenMM context did not use the Reference platform"
            )
        self._closed = False

    def _build_system(self) -> Any:
        openmm = self._openmm
        source = self._source_system
        parameters = self._base_parameters
        result = openmm.System()
        for atom in source.atoms:
            mass = 1.0 if atom.mass_da is None or atom.mass_da <= 0.0 else atom.mass_da
            result.addParticle(float(mass))
        if source.cell is not None:
            lengths = source.cell.orthorhombic_lengths().tolist()
            result.setDefaultPeriodicBoxVectors(
                openmm.Vec3(float(lengths[0]) * _NM_PER_ANGSTROM, 0.0, 0.0),
                openmm.Vec3(0.0, float(lengths[1]) * _NM_PER_ANGSTROM, 0.0),
                openmm.Vec3(0.0, 0.0, float(lengths[2]) * _NM_PER_ANGSTROM),
            )

        bond_force = openmm.HarmonicBondForce()
        for row in parameters.bonds:
            bond_force.addBond(
                row.atom_i,
                row.atom_j,
                row.equilibrium_angstrom * _NM_PER_ANGSTROM,
                row.force_constant_kcal_per_mol_angstrom2
                * _KJ_PER_KCAL
                / (_NM_PER_ANGSTROM**2),
            )
        bond_force.setForceGroup(0)
        result.addForce(bond_force)
        self._component_groups.append(("harmonic_bond", 0))

        angle_force = openmm.HarmonicAngleForce()
        for row in parameters.angles:
            angle_force.addAngle(
                row.atom_i,
                row.atom_j,
                row.atom_k,
                row.equilibrium_radians,
                row.force_constant_kcal_per_mol_radian2 * _KJ_PER_KCAL,
            )
        angle_force.setForceGroup(1)
        result.addForce(angle_force)
        self._component_groups.append(("harmonic_angle", 1))

        torsion_force = openmm.PeriodicTorsionForce()
        for row in parameters.torsions:
            torsion_force.addTorsion(
                row.atom_i,
                row.atom_j,
                row.atom_k,
                row.atom_l,
                row.periodicity,
                row.phase_radians,
                row.amplitude_kcal_per_mol * _KJ_PER_KCAL,
            )
        torsion_force.setForceGroup(2)
        result.addForce(torsion_force)
        self._component_groups.append(("periodic_torsion", 2))

        lj_force = openmm.CustomBondForce(OPENMM_REFERENCE_LJ_EXPRESSION)
        for name in ("sigma", "epsilon", "scale"):
            lj_force.addPerBondParameter(name)
        lj_force.addGlobalParameter(
            "rs", parameters.switch_start_angstrom * _NM_PER_ANGSTROM
        )
        lj_force.addGlobalParameter("rc", parameters.cutoff_angstrom * _NM_PER_ANGSTROM)
        electrostatic_force = openmm.CustomBondForce(
            OPENMM_REFERENCE_SCREENED_COULOMB_EXPRESSION
        )
        for name in ("qprod", "scale"):
            electrostatic_force.addPerBondParameter(name)
        electrostatic_force.addGlobalParameter(
            "coulomb",
            COULOMB_KCAL_ANGSTROM_PER_MOL_E2 * _KJ_PER_KCAL * _NM_PER_ANGSTROM,
        )
        electrostatic_force.addGlobalParameter(
            "kappa",
            parameters.screening_kappa_per_angstrom / _NM_PER_ANGSTROM,
        )
        electrostatic_force.addGlobalParameter("dielectric", parameters.dielectric)
        electrostatic_force.addGlobalParameter(
            "rs", parameters.switch_start_angstrom * _NM_PER_ANGSTROM
        )
        electrostatic_force.addGlobalParameter(
            "rc", parameters.cutoff_angstrom * _NM_PER_ANGSTROM
        )
        if source.cell is not None:
            lj_force.setUsesPeriodicBoundaryConditions(True)
            electrostatic_force.setUsesPeriodicBoundaryConditions(True)
        atom_map = parameters.atom_parameter_map
        scaling_map = parameters.pair_scaling_map
        excluded = set(parameters.excluded_pairs)
        for atom_i in range(source.atom_count):
            for atom_j in range(atom_i + 1, source.atom_count):
                pair = (atom_i, atom_j)
                first = atom_map[atom_i]
                second = atom_map[atom_j]
                if pair in excluded:
                    lj_scale, electrostatic_scale = 0.0, 0.0
                elif pair in scaling_map:
                    scaling = scaling_map[pair]
                    lj_scale = scaling.lj_scale
                    electrostatic_scale = scaling.electrostatic_scale
                else:
                    lj_scale, electrostatic_scale = 1.0, 1.0
                lj_force.addBond(
                    atom_i,
                    atom_j,
                    [
                        0.5
                        * (first.sigma_angstrom + second.sigma_angstrom)
                        * _NM_PER_ANGSTROM,
                        math.sqrt(
                            first.epsilon_kcal_per_mol * second.epsilon_kcal_per_mol
                        )
                        * _KJ_PER_KCAL,
                        lj_scale,
                    ],
                )
                electrostatic_force.addBond(
                    atom_i,
                    atom_j,
                    [first.charge_e * second.charge_e, electrostatic_scale],
                )
        lj_force.setForceGroup(3)
        electrostatic_force.setForceGroup(4)
        result.addForce(lj_force)
        result.addForce(electrostatic_force)
        self._component_groups.extend((("lennard_jones", 3), ("screened_coulomb", 4)))

        if self._v2_parameters is not None:
            for row in self._v2_parameters.constraints:
                result.addConstraint(
                    row.atom_i,
                    row.atom_j,
                    row.target_distance_angstrom * _NM_PER_ANGSTROM,
                )
            improper_force = openmm.CustomCompoundBondForce(
                4,
                OPENMM_REFERENCE_IMPROPER_EXPRESSION,
            )
            improper_force.addPerBondParameter("theta0")
            improper_force.addPerBondParameter("k")
            for row in self._v2_parameters.impropers:
                improper_force.addBond(
                    [
                        row.center_atom,
                        row.plane_atom_i,
                        row.plane_atom_j,
                        row.out_of_plane_atom,
                    ],
                    [
                        row.equilibrium_radians,
                        row.force_constant_kcal_per_mol_radian2 * _KJ_PER_KCAL,
                    ],
                )
            improper_force.setForceGroup(5)
            result.addForce(improper_force)
            self._component_groups.append(("harmonic_out_of_plane_improper", 5))

        if self._solvation_parameters is not None:
            solvation = self._solvation_parameters
            coefficient = (
                -0.5
                * COULOMB_KCAL_ANGSTROM_PER_MOL_E2
                * _KJ_PER_KCAL
                * _NM_PER_ANGSTROM
                * (
                    1.0 / solvation.solute_dielectric
                    - 1.0 / solvation.solvent_dielectric
                )
            )
            radii = {
                row.atom_index: row.effective_born_radius_angstrom * _NM_PER_ANGSTROM
                for row in solvation.atom_parameters
            }
            self_force = openmm.CustomExternalForce(
                OPENMM_REFERENCE_FIXED_BORN_SELF_EXPRESSION
            )
            self_force.addPerParticleParameter("q")
            self_force.addPerParticleParameter("alpha")
            self_force.addGlobalParameter("coefficient", coefficient)
            for atom_index in range(source.atom_count):
                self_force.addParticle(
                    atom_index,
                    [atom_map[atom_index].charge_e, radii[atom_index]],
                )
            pair_force = openmm.CustomBondForce(
                OPENMM_REFERENCE_FIXED_BORN_PAIR_EXPRESSION
            )
            pair_force.addPerBondParameter("qprod")
            pair_force.addPerBondParameter("alpha_product")
            pair_force.addGlobalParameter("coefficient", coefficient)
            for atom_i in range(source.atom_count):
                for atom_j in range(atom_i + 1, source.atom_count):
                    pair_force.addBond(
                        atom_i,
                        atom_j,
                        [
                            atom_map[atom_i].charge_e * atom_map[atom_j].charge_e,
                            radii[atom_i] * radii[atom_j],
                        ],
                    )
            self_force.setForceGroup(6)
            pair_force.setForceGroup(7)
            result.addForce(self_force)
            result.addForce(pair_force)
            self._component_groups.extend(
                (("fixed_born_self_polar", 6), ("fixed_born_pair_polar", 7))
            )
        return result

    def evaluate(
        self,
        coordinates_angstrom: Sequence[Sequence[object]] | None = None,
    ) -> OpenMMReferenceEvaluation:
        if self._closed:
            raise OpenMMReferenceOfflineOracleError(
                "OpenMM Reference session is closed"
            )
        source_rows = (
            self._source_system.coordinates[0].detach().cpu().tolist()
            if coordinates_angstrom is None
            else coordinates_angstrom
        )
        rows = _coordinate_rows(
            source_rows,
            atom_count=self._source_system.atom_count,
        )
        positions = [
            self._openmm.Vec3(
                row[0] * _NM_PER_ANGSTROM,
                row[1] * _NM_PER_ANGSTROM,
                row[2] * _NM_PER_ANGSTROM,
            )
            for row in rows
        ]
        self._context.setPositions(positions)
        component_rows: list[tuple[str, float]] = []
        for name, group in self._component_groups:
            state = self._context.getState(getEnergy=True, groups=1 << group)
            value = state.getPotentialEnergy().value_in_unit(
                self._unit.kilojoule_per_mole
            )
            component_rows.append((name, float(value) / _KJ_PER_KCAL))
        state = self._context.getState(getEnergy=True, getForces=True)
        total = (
            float(
                state.getPotentialEnergy().value_in_unit(self._unit.kilojoule_per_mole)
            )
            / _KJ_PER_KCAL
        )
        force_values = state.getForces().value_in_unit(
            self._unit.kilojoule_per_mole / self._unit.nanometer
        )
        forces = tuple(
            (
                float(row[0]) / _KJ_PER_NM_TO_KCAL_PER_ANGSTROM,
                float(row[1]) / _KJ_PER_NM_TO_KCAL_PER_ANGSTROM,
                float(row[2]) / _KJ_PER_NM_TO_KCAL_PER_ANGSTROM,
            )
            for row in force_values
        )
        values = {
            "coordinate_f64le_sha256": coordinate_f64le_sha256(rows),
            "atom_order_sha256": self._atom_order_sha256,
            "system_topology_sha256": self._topology_sha256,
            "base_parameter_fingerprint_sha256": (
                self._base_parameters.fingerprint_sha256
            ),
            "v2_parameter_fingerprint_sha256": (
                None
                if self._v2_parameters is None
                else self._v2_parameters.fingerprint_sha256
            ),
            "solvation_parameter_fingerprint_sha256": (
                None
                if self._solvation_parameters is None
                else self._solvation_parameters.fingerprint_sha256
            ),
            "component_energies_kcal_per_mol": tuple(component_rows),
            "total_energy_kcal_per_mol": total,
            "forces_kcal_per_mol_angstrom": forces,
        }
        provisional = OpenMMReferenceEvaluation(
            **values,
            evaluation_sha256="0" * 64,
        )
        return OpenMMReferenceEvaluation(
            **values,
            evaluation_sha256=_sha256(provisional.projection()),
        )

    def native_minimize_endpoint(
        self,
        *,
        tolerance_kcal_per_mol_angstrom: float,
        maximum_iterations: int,
        constraint_tolerance_relative: float,
    ) -> dict[str, Any]:
        """Run the separate OpenMM L-BFGS endpoint without trace equivalence."""

        tolerance = _finite(
            tolerance_kcal_per_mol_angstrom,
            name="native minimization tolerance",
        )
        if tolerance <= 0.0:
            raise OpenMMReferenceOfflineOracleError(
                "native minimization tolerance must be positive"
            )
        if (
            isinstance(maximum_iterations, bool)
            or not isinstance(maximum_iterations, int)
            or maximum_iterations < 0
            or maximum_iterations > 1_000_000
        ):
            raise OpenMMReferenceOfflineOracleError(
                "native minimization iteration bound is invalid"
            )
        constraint_tolerance = _finite(
            constraint_tolerance_relative,
            name="native minimization relative constraint tolerance",
        )
        if constraint_tolerance <= 0.0 or constraint_tolerance > 1.0:
            raise OpenMMReferenceOfflineOracleError(
                "native minimization relative constraint tolerance is invalid"
            )
        self._integrator.setConstraintTolerance(constraint_tolerance)
        initial = self.evaluate()
        self._openmm.LocalEnergyMinimizer.minimize(
            self._context,
            tolerance * _KJ_PER_NM_TO_KCAL_PER_ANGSTROM,
            maximum_iterations,
        )
        self._context.applyConstraints(constraint_tolerance)
        state = self._context.getState(getPositions=True)
        position_values = state.getPositions().value_in_unit(self._unit.nanometer)
        final_coordinates = tuple(
            (
                float(row[0]) / _NM_PER_ANGSTROM,
                float(row[1]) / _NM_PER_ANGSTROM,
                float(row[2]) / _NM_PER_ANGSTROM,
            )
            for row in position_values
        )
        final = self.evaluate(final_coordinates)
        projection = {
            "schema_id": OPENMM_REFERENCE_NATIVE_MINIMIZATION_SCHEMA_ID,
            "oracle_id": OPENMM_REFERENCE_OFFLINE_ORACLE_ID,
            "platform": OPENMM_REFERENCE_REQUIRED_PLATFORM,
            "algorithm": "OpenMM LocalEnergyMinimizer L-BFGS",
            "tolerance_kcal_per_mol_angstrom": tolerance,
            "maximum_iterations": maximum_iterations,
            "constraint_tolerance_relative": constraint_tolerance,
            "final_context_constraint_projection_applied": True,
            "initial_evaluation": initial.to_dict(),
            "final_coordinates_angstrom_hex": [
                [value.hex() for value in row] for row in final_coordinates
            ],
            "final_evaluation": final.to_dict(),
            "engine_trace_equivalence_claimed": False,
            "checkpoint_restart_equality_claimed": False,
            "scientifically_validated": False,
            "claim_safe": False,
        }
        return {**projection, "endpoint_sha256": _sha256(projection)}

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            del self._context
            del self._integrator

    def __enter__(self) -> "OpenMMReferenceSession":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def evaluate_openmm_reference(
    system: AllAtomSystem,
    base_parameters: ReferenceForceFieldParameters,
    *,
    v2_parameters: ReferenceForceFieldV2Parameters | None = None,
    solvation_parameters: FixedBornPolarSolvationParameters | None = None,
    coordinates_angstrom: Sequence[Sequence[object]] | None = None,
) -> OpenMMReferenceEvaluation:
    with OpenMMReferenceSession(
        system,
        base_parameters,
        v2_parameters=v2_parameters,
        solvation_parameters=solvation_parameters,
    ) as session:
        return session.evaluate(coordinates_angstrom)


__all__ = [
    "FROZEN_LEGACY_OPENMM_REFERENCE_MAPPING_CONTRACT_SHA256_V1",
    "FROZEN_LEGACY_OPENMM_REFERENCE_MAPPING_CONTRACT_SHA256_V1_1",
    "FROZEN_OPENMM_REFERENCE_MAPPING_CONTRACT_SHA256",
    "OPENMM_REFERENCE_ENERGY_MAX_RMS_THRESHOLD_KCAL_PER_MOL",
    "OPENMM_REFERENCE_EVALUATION_SCHEMA_ID",
    "OPENMM_REFERENCE_FIXED_BORN_PAIR_EXPRESSION",
    "OPENMM_REFERENCE_FIXED_BORN_SELF_EXPRESSION",
    "OPENMM_REFERENCE_FORCE_GROUPS",
    "OPENMM_REFERENCE_FORCE_MAX_RMS_THRESHOLD_KCAL_PER_MOL_ANGSTROM",
    "OPENMM_REFERENCE_IMPROPER_EXPRESSION",
    "OPENMM_REFERENCE_LJ_EXPRESSION",
    "OPENMM_REFERENCE_MAPPING_CONTRACT_SCHEMA_ID",
    "OPENMM_REFERENCE_MAPPING_CONTRACT_VERSION",
    "OPENMM_REFERENCE_NATIVE_MINIMIZATION_SCHEMA_ID",
    "OPENMM_REFERENCE_OFFLINE_ORACLE_ID",
    "OPENMM_REFERENCE_REQUIRED_DISTRIBUTION_VERSION",
    "OPENMM_REFERENCE_REQUIRED_FULL_VERSION",
    "OPENMM_REFERENCE_REQUIRED_GIT_REVISION",
    "OPENMM_REFERENCE_REQUIRED_PLATFORM",
    "OPENMM_REFERENCE_RUNTIME_IDENTITY_SCHEMA_ID",
    "OPENMM_REFERENCE_SCREENED_COULOMB_EXPRESSION",
    "OpenMMReferenceEvaluation",
    "OpenMMReferenceOfflineOracleError",
    "OpenMMReferenceSession",
    "atom_order_sha256",
    "coordinate_f64le_sha256",
    "evaluate_openmm_reference",
    "observe_openmm_reference_runtime_identity",
    "openmm_reference_mapping_contract_document",
    "require_openmm_reference_mapping_contract_document",
    "require_openmm_reference_runtime_identity_document",
]
