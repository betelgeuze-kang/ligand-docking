"""Deterministic, benchmark-only GROMACS rerun adapter.

The product runtime must never import this module.  It describes a narrow
external-oracle lane: prove that the selected GROMACS driver is a
double-precision build, preprocess an already prepared system, and evaluate an
already prepared trajectory with ``mdrun -rerun``.  No topology or coordinate
preparation is performed here.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
import re
import subprocess
from typing import Callable, Sequence

from ..contract import OracleRequest, OracleResult
from ..errors import OracleContractError, OracleExecutionError
from ..execution import (
    DEFAULT_MAX_ARTIFACT_BYTES,
    DEFAULT_MAX_BINARY_ARTIFACT_BYTES,
    ExecutionOutput,
    pinned_oracle_workspace,
    read_fresh_output,
    require_pinned_executable,
    run_argv,
    sanitized_environment,
    sha256_output_file,
    verify_request_inputs,
)


_ERROR_CODES = frozenset({"binary_missing", "timeout", "nonzero", "malformed"})
ORACLE_TASK = "energy_force"
_VERSION_RE = re.compile(r"^\s*GROMACS\s+version\s*:\s*([^\s]+)\s*$", re.I | re.M)
_PRECISION_RE = re.compile(r"^\s*Precision\s*:\s*([^\s]+)\s*$", re.I | re.M)
_LEGEND_RE = re.compile(r'^\s*@\s+s(\d+)\s+legend\s+"([^"]+)"\s*$')
_KJ_PER_KCAL = 4.184
_ANGSTROM_PER_NM = 10.0
_FS_PER_PS = 1000.0


class OracleAdapterError(RuntimeError):
    """A sanitized and stable external-oracle adapter failure."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        provenance: OracleResult | None = None,
    ) -> None:
        if code not in _ERROR_CODES:
            raise ValueError("unsupported GROMACS adapter error code")
        super().__init__(message)
        self.code = code
        self.provenance = provenance


@dataclass(frozen=True)
class CommandOutput:
    """Captured text from one successfully completed command."""

    argv: tuple[str, ...]
    stdout: str
    stderr: str


@dataclass(frozen=True)
class GromacsIdentity:
    """Identity proven from ``gmx --version`` output."""

    executable: str
    version: str
    precision: str = "double"


@dataclass(frozen=True)
class EnergyFrame:
    """One energy row in pack-canonical units (fs and kcal/mol)."""

    time_fs: float
    values_kcal_mol: tuple[float, ...]

    @property
    def time_ps(self) -> float:
        """Compatibility view in the native GROMACS time unit."""

        return self.time_fs / _FS_PER_PS

    @property
    def values_kj_mol(self) -> tuple[float, ...]:
        """Compatibility view in the native GROMACS energy unit."""

        return tuple(value * _KJ_PER_KCAL for value in self.values_kcal_mol)


@dataclass(frozen=True)
class EnergySeries:
    """Validated energy legends and frames parsed from XVG text."""

    terms: tuple[str, ...]
    frames: tuple[EnergyFrame, ...]

    def values(self, term: str) -> tuple[float, ...]:
        """Return all values for an exact GROMACS legend."""

        try:
            index = self.terms.index(term)
        except ValueError as exc:
            raise OracleAdapterError(
                "malformed", "GROMACS energy output is missing a required term"
            ) from exc
        return tuple(frame.values_kcal_mol[index] for frame in self.frames)


@dataclass(frozen=True)
class ForceFrame:
    """One force row in pack-canonical units (fs and kcal/mol/angstrom)."""

    time_fs: float
    forces_kcal_mol_angstrom: tuple[tuple[float, float, float], ...]

    @property
    def time_ps(self) -> float:
        """Compatibility view in the native GROMACS time unit."""

        return self.time_fs / _FS_PER_PS

    @property
    def forces_kj_mol_nm(self) -> tuple[tuple[float, float, float], ...]:
        """Compatibility view in the native GROMACS force unit."""

        factor = _KJ_PER_KCAL * _ANGSTROM_PER_NM
        return tuple(
            tuple(component * factor for component in force)
            for force in self.forces_kcal_mol_angstrom
        )  # type: ignore[return-value]


@dataclass(frozen=True)
class RerunObservations:
    """Time-aligned energy and force observations from one rerun."""

    energies: EnergySeries
    forces: tuple[ForceFrame, ...]


@dataclass(frozen=True)
class RerunExecution:
    """A side-effect-free rerun result that survives workspace deletion.

    The bounded XVG artifacts are retained as immutable bytes.  Potentially
    large EDR/TRR artifacts (up to the configured 1 GiB bound) are deliberately
    digest-only and are represented solely by ``provenance.raw_output_sha256``.
    """

    identity: GromacsIdentity
    mdrun: CommandOutput
    energy_extract: CommandOutput
    force_extract: CommandOutput
    energy_xvg: bytes
    force_xvg: bytes
    observations: RerunObservations
    provenance: OracleResult


Runner = Callable[..., object]


def _execution_error(
    exc: BaseException,
    *,
    request: OracleRequest | None = None,
    executable_sha256: str = "",
    engine_version: str = "unverified",
    raw_output_sha256: dict[str, str] | None = None,
) -> OracleAdapterError:
    source_code = getattr(exc, "code", "malformed")
    if source_code == "timeout":
        code = "timeout"
    elif source_code == "nonzero_exit":
        code = "nonzero"
    elif source_code in {
        "binary_missing",
        "binary_invalid",
        "binary_unreadable",
        "launch_failed",
    }:
        code = "binary_missing"
    else:
        code = "malformed"
    provenance = None
    if isinstance(request, OracleRequest):
        stdout = getattr(exc, "stdout", b"")
        stderr = getattr(exc, "stderr", b"")
        try:
            failure_hashes = {
                "failure_stdout": hashlib.sha256(stdout).hexdigest(),
                "failure_stderr": hashlib.sha256(stderr).hexdigest(),
            }
            failure_hashes.update(raw_output_sha256 or {})
            provenance = OracleResult(
                request_sha256=request.sha256,
                engine_id="gromacs",
                engine_version=engine_version,
                executable_sha256=executable_sha256,
                status="failure",
                values={
                    "source_error_code": source_code,
                    "capture_complete": bool(
                        getattr(
                            exc,
                            "capture_complete",
                            not isinstance(exc, OracleExecutionError),
                        )
                    ),
                    "returncode": getattr(exc, "returncode", None),
                    "input_sha256": dict(request.input_sha256),
                },
                raw_output_sha256=failure_hashes,
                error_code=source_code,
            )
        except OracleContractError:
            provenance = None
    return OracleAdapterError(
        code,
        f"GROMACS high-assurance execution failed: {source_code}",
        provenance=provenance,
    )


def _decoded(output: ExecutionOutput) -> CommandOutput:
    try:
        stdout = output.stdout.decode("utf-8", errors="strict")
        stderr = output.stderr.decode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise OracleAdapterError(
            "malformed", "GROMACS command output is malformed"
        ) from exc
    return CommandOutput(argv=output.argv, stdout=stdout, stderr=stderr)


def _text(value: str | Path, *, name: str) -> str:
    if not isinstance(value, (str, Path)):
        raise OracleAdapterError("malformed", f"GROMACS {name} is malformed")
    rendered = str(value)
    if not rendered or "\x00" in rendered:
        raise OracleAdapterError("malformed", f"GROMACS {name} is malformed")
    return rendered


def _positive_timeout(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OracleAdapterError("malformed", "GROMACS timeout is malformed")
    timeout = float(value)
    if not math.isfinite(timeout) or timeout <= 0.0:
        raise OracleAdapterError("malformed", "GROMACS timeout is malformed")
    return timeout


def _positive_int(value: int, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise OracleAdapterError("malformed", f"GROMACS {name} is malformed")
    return value


def _run(
    argv: Sequence[str],
    *,
    timeout_seconds: float,
    runner: Runner = subprocess.run,
) -> CommandOutput:
    try:
        completed = run_argv(
            argv,
            timeout_seconds=_positive_timeout(timeout_seconds),
            runner=runner,
        )
    except (OracleExecutionError, OracleContractError) as exc:
        raise _execution_error(exc) from exc
    return _decoded(completed)


def parse_identity(version_text: str, *, executable: str = "gmx_d") -> GromacsIdentity:
    """Parse and require an explicit double-precision GROMACS identity."""

    if not isinstance(version_text, str):
        raise OracleAdapterError("malformed", "GROMACS version output is malformed")
    version_match = _VERSION_RE.search(version_text)
    precision_match = _PRECISION_RE.search(version_text)
    if version_match is None or precision_match is None:
        raise OracleAdapterError("malformed", "GROMACS version output is malformed")
    version = version_match.group(1)
    precision = precision_match.group(1).lower()
    if precision != "double":
        raise OracleAdapterError(
            "malformed", "GROMACS oracle must use a double-precision build"
        )
    return GromacsIdentity(
        executable=_text(executable, name="binary"),
        version=version,
        precision="double",
    )


def probe_identity(
    binary: str | Path = "gmx_d",
    *,
    timeout_seconds: float = 10.0,
    runner: Runner = subprocess.run,
) -> GromacsIdentity:
    """Execute ``--version`` and prove the binary's precision."""

    executable = _text(binary, name="binary")
    completed = _run(
        (executable, "--version"),
        timeout_seconds=timeout_seconds,
        runner=runner,
    )
    return parse_identity(
        "\n".join(part for part in (completed.stdout, completed.stderr) if part),
        executable=executable,
    )


def build_mdrun_rerun_command(
    binary: str | Path,
    *,
    tpr: str | Path,
    trajectory: str | Path,
    deffnm: str | Path,
    threads: int = 1,
) -> tuple[str, ...]:
    """Build a deterministic single-rank ``mdrun -rerun`` command."""

    thread_count = _positive_int(threads, name="thread count")
    return (
        _text(binary, name="binary"),
        "mdrun",
        "-s",
        _text(tpr, name="tpr path"),
        "-rerun",
        _text(trajectory, name="trajectory path"),
        "-deffnm",
        _text(deffnm, name="deffnm path"),
        "-ntmpi",
        "1",
        "-ntomp",
        str(thread_count),
        "-pin",
        "on",
        "-nb",
        "cpu",
        "-pme",
        "cpu",
        "-bonded",
        "cpu",
        "-update",
        "cpu",
        "-reprod",
    )


def build_energy_extract_command(
    binary: str | Path,
    *,
    energy_edr: str | Path,
    output_xvg: str | Path,
) -> tuple[str, ...]:
    """Build the non-shell GROMACS energy extraction command."""

    return (
        _text(binary, name="binary"),
        "energy",
        "-f",
        _text(energy_edr, name="energy path"),
        "-o",
        _text(output_xvg, name="energy xvg path"),
    )


def build_force_extract_command(
    binary: str | Path,
    *,
    tpr: str | Path,
    force_trajectory: str | Path,
    output_xvg: str | Path,
) -> tuple[str, ...]:
    """Build the non-shell GROMACS per-atom force extraction command."""

    return (
        _text(binary, name="binary"),
        "traj",
        "-s",
        _text(tpr, name="tpr path"),
        "-f",
        _text(force_trajectory, name="force trajectory path"),
        "-of",
        _text(output_xvg, name="force xvg path"),
    )


def run_rerun(
    binary: str | Path,
    *,
    request: OracleRequest,
    expected_executable_sha256: str,
    tpr: str | Path,
    trajectory: str | Path,
    energy_terms: Sequence[str] = ("Potential",),
    force_group: str = "System",
    timeout_seconds: float = 300.0,
    max_xvg_bytes: int = DEFAULT_MAX_ARTIFACT_BYTES,
    max_binary_output_bytes: int = DEFAULT_MAX_BINARY_ARTIFACT_BYTES,
) -> RerunExecution:
    """Rerun a self-contained hashed TPR and extract live observations.

    Topology preprocessing is deliberately excluded: a ``topol.top`` digest
    does not bind its transitive include closure.  Callers must prepare and
    hash the complete TPR before constructing the :class:`OracleRequest`.
    """

    if (
        isinstance(energy_terms, (str, bytes))
        or not energy_terms
        or any(
            not isinstance(term, str)
            or not term.strip()
            or "\n" in term
            or "\r" in term
            for term in energy_terms
        )
    ):
        raise OracleAdapterError("malformed", "GROMACS energy terms are malformed")
    normalized_terms = tuple(term.strip() for term in energy_terms)
    if (
        not isinstance(force_group, str)
        or not force_group.strip()
        or "\n" in force_group
        or "\r" in force_group
    ):
        raise OracleAdapterError("malformed", "GROMACS force group is malformed")
    normalized_force_group = force_group.strip()
    expected_parameters = {
        "mode": "rerun",
        "precision": "double",
        "energy_terms": normalized_terms,
        "force_group": normalized_force_group,
    }
    if (
        not isinstance(request, OracleRequest)
        or dict(request.parameters) != expected_parameters
    ):
        raise OracleAdapterError(
            "malformed", "GROMACS request parameters are mismatched"
        )
    inputs: dict[str, str | Path] = {"tpr": tpr, "trajectory": trajectory}
    original_executable = Path(binary)
    engine_version = "unverified"
    failure_hashes: dict[str, str] = {}
    try:
        with pinned_oracle_workspace(
            binary,
            expected_executable_sha256,
            request,
            inputs,
            engine_id="gromacs",
            task=ORACLE_TASK,
        ) as workspace:
            executable_hash = workspace.executable_sha256
            workspace_prefix = workspace.output_path("rerun")
            workspace_energy_edr = f"{workspace_prefix}.edr"
            workspace_force_trajectory = f"{workspace_prefix}.trr"
            workspace_energy_xvg = workspace.output_path("energy.xvg")
            workspace_force_xvg = workspace.output_path("force.xvg")
            mdrun_argv = build_mdrun_rerun_command(
                workspace.executable,
                tpr=workspace.inputs["tpr"],
                trajectory=workspace.inputs["trajectory"],
                deffnm=workspace_prefix,
                threads=request.thread_count,
            )
            energy_argv = build_energy_extract_command(
                workspace.executable,
                energy_edr=workspace_energy_edr,
                output_xvg=workspace_energy_xvg,
            )
            force_argv = build_force_extract_command(
                workspace.executable,
                tpr=workspace.inputs["tpr"],
                force_trajectory=workspace_force_trajectory,
                output_xvg=workspace_force_xvg,
            )
            environment = sanitized_environment(thread_count=request.thread_count)
            version_output = run_argv(
                (workspace.executable, "--version"),
                timeout_seconds=timeout_seconds,
                expected_executable_sha256=executable_hash,
                env=environment,
                pass_fds=workspace.pass_fds,
                writable_directory_fds=workspace.writable_directory_fds,
                integrity_check=workspace.verify_unchanged,
            )
            failure_hashes.update(
                version_stdout=version_output.stdout_sha256,
                version_stderr=version_output.stderr_sha256,
            )
            version_command = _decoded(version_output)
            identity = parse_identity(
                "\n".join(
                    part
                    for part in (version_command.stdout, version_command.stderr)
                    if part
                ),
                executable=str(original_executable),
            )
            engine_version = identity.version
            mdrun_output = run_argv(
                mdrun_argv,
                timeout_seconds=timeout_seconds,
                expected_executable_sha256=executable_hash,
                env=environment,
                pass_fds=workspace.pass_fds,
                writable_directory_fds=workspace.writable_directory_fds,
                integrity_check=workspace.verify_unchanged,
            )
            failure_hashes.update(
                mdrun_stdout=mdrun_output.stdout_sha256,
                mdrun_stderr=mdrun_output.stderr_sha256,
            )
            energy_output = run_argv(
                energy_argv,
                timeout_seconds=timeout_seconds,
                expected_executable_sha256=executable_hash,
                env=environment,
                pass_fds=workspace.pass_fds,
                writable_directory_fds=workspace.writable_directory_fds,
                integrity_check=workspace.verify_unchanged,
                input_bytes=("\n".join(normalized_terms) + "\n").encode("utf-8"),
            )
            failure_hashes.update(
                energy_stdout=energy_output.stdout_sha256,
                energy_stderr=energy_output.stderr_sha256,
            )
            force_output = run_argv(
                force_argv,
                timeout_seconds=timeout_seconds,
                expected_executable_sha256=executable_hash,
                env=environment,
                pass_fds=workspace.pass_fds,
                writable_directory_fds=workspace.writable_directory_fds,
                integrity_check=workspace.verify_unchanged,
                input_bytes=(normalized_force_group + "\n").encode("utf-8"),
            )
            failure_hashes.update(
                force_stdout=force_output.stdout_sha256,
                force_stderr=force_output.stderr_sha256,
            )
            energy_artifact = read_fresh_output(
                workspace_energy_xvg, max_bytes=max_xvg_bytes
            )
            force_artifact = read_fresh_output(
                workspace_force_xvg, max_bytes=max_xvg_bytes
            )
            failure_hashes.update(
                energy_xvg=energy_artifact.sha256,
                force_xvg=force_artifact.sha256,
            )
            edr_sha256 = sha256_output_file(
                workspace_energy_edr,
                max_bytes=max_binary_output_bytes,
            )
            trr_sha256 = sha256_output_file(
                workspace_force_trajectory,
                max_bytes=max_binary_output_bytes,
            )
            failure_hashes.update(
                energy_edr=edr_sha256,
                force_trr=trr_sha256,
            )
            energy_text = energy_artifact.data.decode("utf-8", errors="strict")
            force_text = force_artifact.data.decode("utf-8", errors="strict")
            observations = parse_rerun_text(
                energy_text, force_text, required_terms=normalized_terms
            )
            verify_request_inputs(
                request, inputs, engine_id="gromacs", task=ORACLE_TASK
            )
            require_pinned_executable(original_executable, executable_hash)
    except (
        OracleExecutionError,
        OracleContractError,
        OracleAdapterError,
        UnicodeError,
    ) as exc:
        raise _execution_error(
            exc,
            request=request,
            executable_sha256=expected_executable_sha256,
            engine_version=engine_version,
            raw_output_sha256=failure_hashes,
        ) from exc

    provenance = OracleResult(
        request_sha256=request.sha256,
        engine_id="gromacs",
        engine_version=identity.version,
        executable_sha256=executable_hash,
        status="success",
        values={
            "precision": "double",
            "energy_terms": observations.energies.terms,
            "time_fs": tuple(frame.time_fs for frame in observations.energies.frames),
            "energy_kcal_mol": tuple(
                frame.values_kcal_mol for frame in observations.energies.frames
            ),
            "force_kcal_mol_angstrom": tuple(
                frame.forces_kcal_mol_angstrom for frame in observations.forces
            ),
        },
        raw_output_sha256={
            "version_stdout": version_output.stdout_sha256,
            "version_stderr": version_output.stderr_sha256,
            "mdrun_stdout": mdrun_output.stdout_sha256,
            "mdrun_stderr": mdrun_output.stderr_sha256,
            "energy_stdout": energy_output.stdout_sha256,
            "energy_stderr": energy_output.stderr_sha256,
            "force_stdout": force_output.stdout_sha256,
            "force_stderr": force_output.stderr_sha256,
            "energy_edr": edr_sha256,
            "force_trr": trr_sha256,
            "energy_xvg": energy_artifact.sha256,
            "force_xvg": force_artifact.sha256,
        },
    )
    return RerunExecution(
        identity=identity,
        mdrun=_decoded(mdrun_output),
        energy_extract=_decoded(energy_output),
        force_extract=_decoded(force_output),
        energy_xvg=energy_artifact.data,
        force_xvg=force_artifact.data,
        observations=observations,
        provenance=provenance,
    )


def _finite_float(token: str, *, context: str) -> float:
    try:
        value = float(token.replace("D", "E").replace("d", "e"))
    except (AttributeError, ValueError) as exc:
        raise OracleAdapterError(
            "malformed", f"GROMACS {context} is malformed"
        ) from exc
    if not math.isfinite(value):
        raise OracleAdapterError("malformed", f"GROMACS {context} is malformed")
    return value


def _numeric_rows(text: str, *, context: str) -> list[tuple[float, ...]]:
    if not isinstance(text, str):
        raise OracleAdapterError("malformed", f"GROMACS {context} is malformed")
    rows: list[tuple[float, ...]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("#", "@", "&")):
            continue
        tokens = line.split()
        rows.append(tuple(_finite_float(token, context=context) for token in tokens))
    if not rows:
        raise OracleAdapterError("malformed", f"GROMACS {context} is malformed")
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise OracleAdapterError("malformed", f"GROMACS {context} is malformed")
    for previous, current in zip(rows, rows[1:]):
        if not current[0] > previous[0]:
            raise OracleAdapterError(
                "malformed", f"GROMACS {context} time is malformed"
            )
    return rows


def parse_energy_text(
    text: str,
    *,
    required_terms: Sequence[str] = ("Potential",),
) -> EnergySeries:
    """Parse GROMACS energy XVG into finite fs and kcal/mol observations."""

    legends: dict[int, str] = {}
    for line in text.splitlines() if isinstance(text, str) else ():
        match = _LEGEND_RE.match(line)
        if match is not None:
            index = int(match.group(1))
            if index in legends or not match.group(2).strip():
                raise OracleAdapterError(
                    "malformed", "GROMACS energy legends are malformed"
                )
            legends[index] = match.group(2).strip()
    rows = _numeric_rows(text, context="energy output")
    value_count = len(rows[0]) - 1
    if value_count < 1 or set(legends) != set(range(value_count)):
        raise OracleAdapterError("malformed", "GROMACS energy legends are malformed")
    terms = tuple(legends[index] for index in range(value_count))
    if len(set(terms)) != len(terms):
        raise OracleAdapterError("malformed", "GROMACS energy legends are malformed")
    for term in required_terms:
        if not isinstance(term, str) or term not in terms:
            raise OracleAdapterError(
                "malformed", "GROMACS energy output is missing a required term"
            )
    frames = tuple(
        EnergyFrame(
            time_fs=row[0] * _FS_PER_PS,
            values_kcal_mol=tuple(value / _KJ_PER_KCAL for value in row[1:]),
        )
        for row in rows
    )
    return EnergySeries(terms=terms, frames=frames)


def parse_force_text(text: str) -> tuple[ForceFrame, ...]:
    """Parse GROMACS force XVG into finite fs and kcal/mol/angstrom triples."""

    rows = _numeric_rows(text, context="force output")
    component_count = len(rows[0]) - 1
    if component_count < 3 or component_count % 3 != 0:
        raise OracleAdapterError("malformed", "GROMACS force columns are malformed")
    frames: list[ForceFrame] = []
    force_factor = _KJ_PER_KCAL * _ANGSTROM_PER_NM
    for row in rows:
        components = tuple(value / force_factor for value in row[1:])
        forces = tuple(
            (components[index], components[index + 1], components[index + 2])
            for index in range(0, len(components), 3)
        )
        frames.append(
            ForceFrame(
                time_fs=row[0] * _FS_PER_PS,
                forces_kcal_mol_angstrom=forces,
            )
        )
    return tuple(frames)


def parse_rerun_text(
    energy_text: str,
    force_text: str,
    *,
    required_terms: Sequence[str] = ("Potential",),
) -> RerunObservations:
    """Parse and require exact frame alignment between energies and forces."""

    energies = parse_energy_text(energy_text, required_terms=required_terms)
    forces = parse_force_text(force_text)
    if len(energies.frames) != len(forces):
        raise OracleAdapterError("malformed", "GROMACS rerun frame counts disagree")
    if any(
        energy.time_fs != force.time_fs
        for energy, force in zip(energies.frames, forces)
    ):
        raise OracleAdapterError("malformed", "GROMACS rerun frame times disagree")
    return RerunObservations(energies=energies, forces=forces)


__all__ = [
    "CommandOutput",
    "EnergyFrame",
    "EnergySeries",
    "ForceFrame",
    "GromacsIdentity",
    "OracleAdapterError",
    "ORACLE_TASK",
    "RerunExecution",
    "RerunObservations",
    "build_energy_extract_command",
    "build_force_extract_command",
    "build_mdrun_rerun_command",
    "parse_energy_text",
    "parse_force_text",
    "parse_identity",
    "parse_rerun_text",
    "probe_identity",
    "run_rerun",
]
