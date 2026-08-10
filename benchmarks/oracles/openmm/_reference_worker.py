"""Standalone isolated worker for the OpenMM Reference oracle.

The parent copies this bounded, hash-pinned source into ``python -c``.  This
module intentionally imports no Betelgeuze package and discovers OpenMM and
NumPy only from the exact search roots in its canonical request.
"""

from __future__ import annotations

import hashlib
from importlib import metadata, util
import json
import math
import os
from pathlib import Path, PurePosixPath
import stat
import struct
import sys
from typing import Any


_REQUEST_SCHEMA_ID = "betelgeuze.openmm_reference_worker_request/4.0.0"
_RESULT_SCHEMA_ID = "betelgeuze.openmm_reference_state/3.0.0"
_RUNTIME_SCHEMA_ID = "betelgeuze.openmm_runtime_dependency_distributions/3.0.0"
_DISTRIBUTION_NAMES = ("OpenMM", "numpy")
_INSTALL_GENERATED_METADATA_NAMES = frozenset(
    {"INSTALLER", "RECORD", "REQUESTED", "direct_url.json"}
)
_REFERENCE_PLATFORM = "Reference"
_SHA256_LENGTH = 64
_MAX_INPUT_BYTES = 64 * 1024
_IDENTITY_FIELDS = (
    "st_dev",
    "st_ino",
    "st_mode",
    "st_size",
    "st_mtime_ns",
    "st_ctime_ns",
)


class _WorkerFailure(RuntimeError):
    pass


class _DependencySpec:
    __slots__ = ("name", "version", "search_root")

    def __init__(self, name: str, version: str, search_root: Path) -> None:
        self.name = name
        self.version = version
        self.search_root = search_root


class _PinnedArtifact:
    __slots__ = (
        "distribution_name",
        "relative_path",
        "path",
        "descriptor",
        "identity",
        "sha256",
    )

    def __init__(
        self,
        distribution_name: str,
        relative_path: str,
        path: Path,
    ) -> None:
        descriptor = -1
        try:
            before_path = path.lstat()
            if stat.S_ISLNK(before_path.st_mode) or not stat.S_ISREG(
                before_path.st_mode
            ):
                raise _WorkerFailure
            flags = (
                os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
            )
            descriptor = os.open(path, flags)
            before_descriptor = os.fstat(descriptor)
            if not stat.S_ISREG(before_descriptor.st_mode) or not _same_identity(
                before_path, before_descriptor
            ):
                raise _WorkerFailure
            digest = _descriptor_sha256(descriptor)
            after_descriptor = os.fstat(descriptor)
            after_path = path.lstat()
            if (
                stat.S_ISLNK(after_path.st_mode)
                or not _same_identity(before_descriptor, after_descriptor)
                or not _same_identity(before_descriptor, after_path)
            ):
                raise _WorkerFailure
        except BaseException:
            if descriptor >= 0:
                os.close(descriptor)
            raise
        self.distribution_name = distribution_name
        self.relative_path = relative_path
        self.path = path
        self.descriptor = descriptor
        self.identity = before_descriptor
        self.sha256 = digest

    def verify(self) -> None:
        try:
            before_descriptor = os.fstat(self.descriptor)
            before_path = self.path.lstat()
            digest = _descriptor_sha256(self.descriptor)
            after_descriptor = os.fstat(self.descriptor)
            after_path = self.path.lstat()
        except OSError as exc:
            raise _WorkerFailure from exc
        if (
            stat.S_ISLNK(before_path.st_mode)
            or stat.S_ISLNK(after_path.st_mode)
            or not _same_identity(self.identity, before_descriptor)
            or not _same_identity(self.identity, before_path)
            or not _same_identity(self.identity, after_descriptor)
            or not _same_identity(self.identity, after_path)
            or digest != self.sha256
        ):
            raise _WorkerFailure

    def close(self) -> None:
        try:
            os.close(self.descriptor)
        except OSError:
            pass


def _canonical_json_bytes(payload: Any) -> bytes:
    try:
        return (
            json.dumps(
                payload,
                allow_nan=False,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise _WorkerFailure from exc


def _sha256_payload(payload: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def _require_sha256(value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != _SHA256_LENGTH
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise _WorkerFailure
    return value


def _same_identity(left: os.stat_result, right: os.stat_result) -> bool:
    return all(
        getattr(left, field) == getattr(right, field) for field in _IDENTITY_FIELDS
    )


def _descriptor_sha256(descriptor: int) -> str:
    digest = hashlib.sha256()
    offset = 0
    try:
        while chunk := os.pread(descriptor, 1024 * 1024, offset):
            digest.update(chunk)
            offset += len(chunk)
    except OSError as exc:
        raise _WorkerFailure from exc
    return digest.hexdigest()


def _normalized_relative_path(value: object) -> str:
    if not isinstance(value, str):
        raise _WorkerFailure
    rendered = value.replace("\\", "/")
    candidate = PurePosixPath(rendered)
    normalized = candidate.as_posix()
    parts = candidate.parts
    if (
        not rendered
        or "\x00" in rendered
        or candidate.is_absolute()
        or rendered != normalized
        or not parts
        or parts[-1] == ".."
        or any(
            part == ".." and any(previous != ".." for previous in parts[:index])
            for index, part in enumerate(parts)
        )
    ):
        raise _WorkerFailure
    return normalized


def _runtime_artifact_relative_path(
    search_root: Path,
    located: Path,
) -> str | None:
    try:
        relative = located.relative_to(search_root)
    except ValueError:
        return None
    parts = relative.parts
    if not parts:
        raise _WorkerFailure
    if "__pycache__" in parts and parts[-1].endswith(".pyc"):
        return None
    if parts[-1] in _INSTALL_GENERATED_METADATA_NAMES and any(
        part.endswith(".dist-info") for part in parts[:-1]
    ):
        return None
    return PurePosixPath(*parts).as_posix()


def _read_request() -> dict[str, Any]:
    raw = sys.stdin.buffer.read(_MAX_INPUT_BYTES + 1)
    if not raw or len(raw) > _MAX_INPUT_BYTES:
        raise _WorkerFailure
    try:
        payload = json.loads(raw.decode("utf-8", errors="strict"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise _WorkerFailure from exc
    if not isinstance(payload, dict) or _canonical_json_bytes(payload) != raw:
        raise _WorkerFailure
    required = {
        "schema_id",
        "expected_runtime_sha256",
        "python_executable_sha256",
        "worker_sha256",
        "runtime_dependency_distributions",
        "pycache_prefix",
        "prepared_system_sha256",
        "parameters",
    }
    if set(payload) != required or payload["schema_id"] != _REQUEST_SCHEMA_ID:
        raise _WorkerFailure
    return payload


def _dependency_specs(payload: dict[str, Any]) -> list[_DependencySpec]:
    raw_dependencies = payload["runtime_dependency_distributions"]
    if not isinstance(raw_dependencies, list) or len(raw_dependencies) != len(
        _DISTRIBUTION_NAMES
    ):
        raise _WorkerFailure
    specs: list[_DependencySpec] = []
    for expected_name, raw in zip(_DISTRIBUTION_NAMES, raw_dependencies, strict=True):
        if not isinstance(raw, dict) or set(raw) != {
            "distribution",
            "version",
            "search_root",
        }:
            raise _WorkerFailure
        name = raw["distribution"]
        version = raw["version"]
        root_value = raw["search_root"]
        if name != expected_name:
            raise _WorkerFailure
        if not isinstance(version, str) or not version or "\x00" in version:
            raise _WorkerFailure
        if not isinstance(root_value, str) or not root_value or "\x00" in root_value:
            raise _WorkerFailure
        search_root = Path(root_value)
        if not search_root.is_absolute():
            raise _WorkerFailure
        specs.append(_DependencySpec(name, version, search_root))
    return specs


def _metadata_entries(spec: _DependencySpec) -> list[tuple[str, Path]]:
    try:
        distribution = metadata.distribution(spec.name)
    except Exception as exc:
        raise _WorkerFailure from exc
    if " ".join(str(distribution.version or "").split()) != spec.version:
        raise _WorkerFailure
    try:
        observed_root = Path(os.path.abspath(distribution.locate_file("")))
    except Exception as exc:
        raise _WorkerFailure from exc
    if observed_root != spec.search_root:
        raise _WorkerFailure
    files = distribution.files
    if not files:
        raise _WorkerFailure
    entries: list[tuple[str, Path]] = []
    names: set[str] = set()
    for entry in files:
        relative_path = _normalized_relative_path(str(entry))
        try:
            located = Path(os.path.abspath(distribution.locate_file(entry)))
        except Exception as exc:
            raise _WorkerFailure from exc
        if located != Path(os.path.abspath(spec.search_root / relative_path)):
            raise _WorkerFailure
        canonical_path = _runtime_artifact_relative_path(spec.search_root, located)
        if canonical_path is None:
            continue
        if canonical_path in names:
            continue
        names.add(canonical_path)
        entries.append((canonical_path, located))
    if sum(path.endswith(".dist-info/METADATA") for path in names) != 1:
        raise _WorkerFailure
    entries.sort(key=lambda item: item[0])
    return entries


def _capture_runtime(
    specs: list[_DependencySpec], expected_sha256: str
) -> tuple[list[_PinnedArtifact], str]:
    artifacts: list[_PinnedArtifact] = []
    paths: set[Path] = set()
    try:
        for spec in specs:
            for relative_path, path in _metadata_entries(spec):
                if path in paths:
                    raise _WorkerFailure
                paths.add(path)
                artifacts.append(_PinnedArtifact(spec.name, relative_path, path))
    except BaseException:
        for artifact in artifacts:
            artifact.close()
        raise
    observed = _runtime_digest(specs, artifacts)
    if observed != expected_sha256:
        for artifact in artifacts:
            artifact.close()
        raise _WorkerFailure
    return artifacts, observed


def _runtime_digest(
    specs: list[_DependencySpec], artifacts: list[_PinnedArtifact]
) -> str:
    return _sha256_payload(
        {
            "schema_id": _RUNTIME_SCHEMA_ID,
            "runtime_dependency_distributions": [
                {
                    "distribution": spec.name,
                    "version": spec.version,
                    "artifacts": [
                        {
                            "path": artifact.relative_path,
                            "size": artifact.identity.st_size,
                            "sha256": artifact.sha256,
                        }
                        for artifact in artifacts
                        if artifact.distribution_name == spec.name
                    ],
                }
                for spec in specs
            ],
        }
    )


def _verify_distribution_metadata(
    specs: list[_DependencySpec], artifacts: list[_PinnedArtifact]
) -> None:
    for spec in specs:
        observed = _metadata_entries(spec)
        expected = [
            (artifact.relative_path, artifact.path)
            for artifact in artifacts
            if artifact.distribution_name == spec.name
        ]
        if observed != expected:
            raise _WorkerFailure


def _verify_worker_and_python(payload: dict[str, Any]) -> None:
    if (
        len(sys.argv) != 2
        or sys.argv[0] != "-c"
        or _require_sha256(sys.argv[1]) != _require_sha256(payload["worker_sha256"])
    ):
        raise _WorkerFailure
    executable = Path(sys.executable)
    if not executable.is_absolute():
        raise _WorkerFailure
    python_artifact = _PinnedArtifact("", "python_executable", executable)
    try:
        if python_artifact.sha256 != _require_sha256(
            payload["python_executable_sha256"]
        ):
            raise _WorkerFailure
        python_artifact.verify()
    finally:
        python_artifact.close()


def _require_clean_import_state() -> None:
    if any(
        name == prefix or name.startswith(f"{prefix}.")
        for name in sys.modules
        for prefix in ("openmm", "numpy", "simtk")
    ):
        raise _WorkerFailure


def _require_initial_import_origins(specs: list[_DependencySpec]) -> None:
    roots = {spec.name: spec.search_root for spec in specs}
    expected = {
        "openmm": roots["OpenMM"] / "openmm" / "__init__.py",
        "numpy": roots["numpy"] / "numpy" / "__init__.py",
    }
    for module_name, expected_origin in expected.items():
        specification = util.find_spec(module_name)
        if specification is None or specification.origin is None:
            raise _WorkerFailure
        if os.path.abspath(specification.origin) != os.path.abspath(expected_origin):
            raise _WorkerFailure


def _require_loaded_module_origins(artifacts: list[_PinnedArtifact]) -> None:
    expected = {os.path.abspath(artifact.path): artifact for artifact in artifacts}
    for name, module in tuple(sys.modules.items()):
        if not (
            name == "openmm"
            or name.startswith("openmm.")
            or name == "numpy"
            or name.startswith("numpy.")
        ):
            continue
        origin = getattr(module, "__file__", None)
        if not isinstance(origin, str) or not origin or "\x00" in origin:
            raise _WorkerFailure
        candidate = Path(os.path.abspath(origin))
        artifact = expected.get(os.path.abspath(candidate))
        if artifact is None:
            raise _WorkerFailure
        try:
            current = candidate.lstat()
        except OSError as exc:
            raise _WorkerFailure from exc
        if stat.S_ISLNK(current.st_mode) or not _same_identity(
            artifact.identity, current
        ):
            raise _WorkerFailure


def _finite_parameter(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _WorkerFailure
    normalized = float(value)
    if not math.isfinite(normalized):
        raise _WorkerFailure
    return normalized


def _parameters(payload: dict[str, Any]) -> dict[str, float]:
    value = payload["parameters"]
    names = {
        "distance_angstrom",
        "equilibrium_angstrom",
        "force_constant_kcal_per_mol_angstrom2",
    }
    if not isinstance(value, dict) or set(value) != names:
        raise _WorkerFailure
    result = {name: _finite_parameter(value[name]) for name in sorted(names)}
    if result["distance_angstrom"] <= 0.0 or result["equilibrium_angstrom"] <= 0.0:
        raise _WorkerFailure
    if result["force_constant_kcal_per_mol_angstrom2"] < 0.0:
        raise _WorkerFailure
    return result


def _f64_bits(value: float) -> str:
    return f"{struct.unpack('>Q', struct.pack('>d', value))[0]:016x}"


def _evaluate(
    mm: Any, unit: Any, parameters: dict[str, float]
) -> tuple[float, tuple[float, float]]:
    try:
        platform = mm.Platform.getPlatformByName(_REFERENCE_PLATFORM)
    except Exception as exc:
        raise _WorkerFailure from exc
    if str(platform.getName()) != _REFERENCE_PLATFORM:
        raise _WorkerFailure
    system = mm.System()
    system.addParticle(1.0 * unit.dalton)
    system.addParticle(1.0 * unit.dalton)
    force = mm.HarmonicBondForce()
    force.addBond(
        0,
        1,
        parameters["equilibrium_angstrom"] * unit.angstrom,
        parameters["force_constant_kcal_per_mol_angstrom2"]
        * unit.kilocalorie_per_mole
        / (unit.angstrom**2),
    )
    system.addForce(force)
    integrator = mm.VerletIntegrator(1.0 * unit.femtosecond)
    try:
        context = mm.Context(system, integrator, platform)
        context.setPositions(
            [
                (0.0, 0.0, 0.0),
                (parameters["distance_angstrom"], 0.0, 0.0),
            ]
            * unit.angstrom
        )
        state = context.getState(getEnergy=True, getForces=True)
        energy = float(
            state.getPotentialEnergy().value_in_unit(unit.kilocalorie_per_mole)
        )
        forces = state.getForces(asNumpy=True).value_in_unit(
            unit.kilocalorie_per_mole / unit.angstrom
        )
        force_x = (float(forces[0][0]), float(forces[1][0]))
    except Exception as exc:
        raise _WorkerFailure from exc
    finally:
        if "context" in locals():
            del context
        del integrator
    if not math.isfinite(energy) or any(not math.isfinite(value) for value in force_x):
        raise _WorkerFailure
    return energy, force_x


def _dependency_summary(
    specs: list[_DependencySpec], artifacts: list[_PinnedArtifact]
) -> list[dict[str, Any]]:
    return [
        {
            "distribution": spec.name,
            "version": spec.version,
            "artifact_count": sum(
                artifact.distribution_name == spec.name for artifact in artifacts
            ),
        }
        for spec in specs
    ]


def _main() -> int:
    payload = _read_request()
    if not sys.flags.isolated or not sys.flags.no_site or not sys.dont_write_bytecode:
        raise _WorkerFailure
    pycache_prefix = payload["pycache_prefix"]
    if not isinstance(pycache_prefix, str) or sys.pycache_prefix != pycache_prefix:
        raise _WorkerFailure
    _require_clean_import_state()
    _verify_worker_and_python(payload)
    specs = _dependency_specs(payload)
    search_roots: list[str] = []
    for spec in specs:
        rendered = os.fspath(spec.search_root)
        if rendered not in search_roots:
            search_roots.append(rendered)
    sys.path[0:0] = search_roots
    _require_clean_import_state()
    expected_runtime_sha256 = _require_sha256(payload["expected_runtime_sha256"])
    artifacts, runtime_sha256 = _capture_runtime(specs, expected_runtime_sha256)
    try:
        _verify_distribution_metadata(specs, artifacts)
        _require_initial_import_origins(specs)
        import numpy as np
        import openmm as mm
        from openmm import unit

        if not getattr(np, "__version__", ""):
            raise _WorkerFailure
        parameters = _parameters(payload)
        energy, force_x = _evaluate(mm, unit, parameters)
        _require_loaded_module_origins(artifacts)
        version = " ".join(str(getattr(mm.version, "version", "")).split())
        if not version:
            raise _WorkerFailure
        _verify_distribution_metadata(specs, artifacts)
        for artifact in artifacts:
            artifact.verify()
        if _runtime_digest(specs, artifacts) != runtime_sha256:
            raise _WorkerFailure
        result = {
            "schema_id": _RESULT_SCHEMA_ID,
            "runtime_sha256": runtime_sha256,
            "runtime_dependency_manifest_schema_id": _RUNTIME_SCHEMA_ID,
            "runtime_dependency_distributions": _dependency_summary(specs, artifacts),
            "openmm_version": version,
            "platform": _REFERENCE_PLATFORM,
            "prepared_system_sha256": _require_sha256(
                payload["prepared_system_sha256"]
            ),
            "energy_kcal_per_mol": energy,
            "force_x_kcal_per_mol_angstrom": force_x,
            "energy_f64_bits": _f64_bits(energy),
            "force_x_f64_bits": tuple(_f64_bits(value) for value in force_x),
        }
        sys.stdout.buffer.write(_canonical_json_bytes(result))
        return 0
    finally:
        for artifact in artifacts:
            artifact.close()


if __name__ == "__main__":
    try:
        raise SystemExit(_main())
    except SystemExit:
        raise
    except BaseException:
        sys.stderr.write("openmm_reference_worker_failed\n")
        raise SystemExit(2) from None
