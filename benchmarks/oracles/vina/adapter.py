"""Prepared-input-only AutoDock Vina benchmark adapter.

This module does not prepare receptors, protonate ligands, assign charges, or
dispatch any product work.  It accepts canonical PDBQT inputs and freezes the
oracle identity to Vina scoring with no CNN contribution.
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
    ExecutionOutput,
    pinned_oracle_workspace,
    read_fresh_output,
    require_pinned_executable,
    run_argv,
    sanitized_environment,
    verify_request_inputs,
)


SCORING_MODE = "vina"
CNN_SCORING_MODE = "none"
ORACLE_TASK = "docking"
_ERROR_CODES = frozenset({"binary_missing", "timeout", "nonzero", "malformed"})
_VERSION_RE = re.compile(
    r"\bAutoDock\s+Vina\s+v?([0-9]+(?:\.[0-9]+)+(?:[-+._A-Za-z0-9]*)?)\b", re.I
)
_RESULT_RE = re.compile(
    r"^\s*REMARK\s+VINA\s+RESULT\s*:\s*"
    r"(\S+)\s+(\S+)\s+(\S+)(?:\s+.*)?$",
    re.I,
)


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
            raise ValueError("unsupported Vina adapter error code")
        super().__init__(message)
        self.code = code
        self.provenance = provenance


@dataclass(frozen=True)
class CommandOutput:
    argv: tuple[str, ...]
    stdout: str
    stderr: str


@dataclass(frozen=True)
class VinaIdentity:
    executable: str
    version: str
    scoring: str = SCORING_MODE
    cnn_scoring: str = CNN_SCORING_MODE


@dataclass(frozen=True)
class VinaScore:
    rank: int
    affinity_kcal_mol: float
    rmsd_lower_bound_angstrom: float
    rmsd_upper_bound_angstrom: float


@dataclass(frozen=True)
class VinaPose:
    rank: int
    affinity_kcal_mol: float
    atom_count: int


@dataclass(frozen=True)
class VinaResult:
    scores: tuple[VinaScore, ...]
    poses: tuple[VinaPose, ...]


@dataclass(frozen=True)
class VinaRun:
    identity: VinaIdentity
    command: CommandOutput
    result: VinaResult
    pose_pdbqt: bytes
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
                engine_id="vina",
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
        f"Vina high-assurance execution failed: {source_code}",
        provenance=provenance,
    )


def _decoded(output: ExecutionOutput) -> CommandOutput:
    try:
        stdout = output.stdout.decode("utf-8", errors="strict")
        stderr = output.stderr.decode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise OracleAdapterError(
            "malformed", "Vina command output is malformed"
        ) from exc
    return CommandOutput(argv=output.argv, stdout=stdout, stderr=stderr)


def _text(value: str | Path, *, name: str) -> str:
    if not isinstance(value, (str, Path)):
        raise OracleAdapterError("malformed", f"Vina {name} is malformed")
    rendered = str(value)
    if not rendered or "\x00" in rendered:
        raise OracleAdapterError("malformed", f"Vina {name} is malformed")
    return rendered


def _pdbqt(value: str | Path, *, name: str) -> str:
    rendered = _text(value, name=name)
    if Path(rendered).suffix.lower() != ".pdbqt":
        raise OracleAdapterError(
            "malformed", f"Vina {name} must be an already prepared PDBQT path"
        )
    return rendered


def _positive_timeout(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OracleAdapterError("malformed", "Vina timeout is malformed")
    timeout = float(value)
    if not math.isfinite(timeout) or timeout <= 0.0:
        raise OracleAdapterError("malformed", "Vina timeout is malformed")
    return timeout


def _bounded_int(value: int, *, name: str, minimum: int, maximum: int) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < minimum
        or value > maximum
    ):
        raise OracleAdapterError("malformed", f"Vina {name} is malformed")
    return value


def _finite_float(value: object, *, name: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise OracleAdapterError("malformed", f"Vina {name} is malformed") from exc
    if not math.isfinite(parsed):
        raise OracleAdapterError("malformed", f"Vina {name} is malformed")
    return parsed


def _triple(
    value: Sequence[float], *, name: str, positive: bool
) -> tuple[float, float, float]:
    if isinstance(value, (str, bytes)):
        raise OracleAdapterError("malformed", f"Vina {name} is malformed")
    try:
        items = tuple(value)
    except TypeError as exc:
        raise OracleAdapterError("malformed", f"Vina {name} is malformed") from exc
    if len(items) != 3:
        raise OracleAdapterError("malformed", f"Vina {name} is malformed")
    parsed = tuple(_finite_float(item, name=name) for item in items)
    if positive and any(item <= 0.0 for item in parsed):
        raise OracleAdapterError("malformed", f"Vina {name} is malformed")
    return parsed  # type: ignore[return-value]


def _number(value: float) -> str:
    return "0" if value == 0.0 else format(value, ".17g")


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


def parse_version(version_text: str, *, executable: str = "vina") -> VinaIdentity:
    """Parse an AutoDock Vina version string and freeze the scoring identity."""

    if not isinstance(version_text, str):
        raise OracleAdapterError("malformed", "Vina version output is malformed")
    match = _VERSION_RE.search(version_text)
    if match is None:
        raise OracleAdapterError("malformed", "Vina version output is malformed")
    return VinaIdentity(
        executable=_text(executable, name="binary"), version=match.group(1)
    )


def probe_identity(
    binary: str | Path = "vina",
    *,
    timeout_seconds: float = 10.0,
    runner: Runner = subprocess.run,
) -> VinaIdentity:
    executable = _text(binary, name="binary")
    completed = _run(
        (executable, "--version"),
        timeout_seconds=timeout_seconds,
        runner=runner,
    )
    return parse_version(
        "\n".join(part for part in (completed.stdout, completed.stderr) if part),
        executable=executable,
    )


def build_command(
    binary: str | Path,
    *,
    receptor_pdbqt: str | Path,
    ligand_pdbqt: str | Path,
    output_pdbqt: str | Path,
    center_angstrom: Sequence[float],
    size_angstrom: Sequence[float],
    exhaustiveness: int = 8,
    num_modes: int = 9,
    seed: int = 0,
    cpu: int = 1,
    scoring: str = SCORING_MODE,
    cnn_scoring: str = CNN_SCORING_MODE,
    log_path: str | Path | None = None,
) -> tuple[str, ...]:
    """Build canonical Vina argv from prepared PDBQT inputs only.

    ``cnn_scoring`` is an identity assertion rather than a Vina CLI option:
    AutoDock Vina has no CNN scorer.  Supplying any mode other than ``none``
    fails closed instead of silently changing the benchmark.
    """

    if scoring != SCORING_MODE or cnn_scoring != CNN_SCORING_MODE:
        raise OracleAdapterError("malformed", "Vina scoring identity is malformed")
    receptor = _pdbqt(receptor_pdbqt, name="receptor path")
    ligand = _pdbqt(ligand_pdbqt, name="ligand path")
    output = _pdbqt(output_pdbqt, name="output path")
    if len({receptor, ligand, output}) != 3:
        raise OracleAdapterError("malformed", "Vina input and output paths must differ")
    center = _triple(center_angstrom, name="box center", positive=False)
    size = _triple(size_angstrom, name="box size", positive=True)
    command = [
        _text(binary, name="binary"),
        "--receptor",
        receptor,
        "--ligand",
        ligand,
        "--center_x",
        _number(center[0]),
        "--center_y",
        _number(center[1]),
        "--center_z",
        _number(center[2]),
        "--size_x",
        _number(size[0]),
        "--size_y",
        _number(size[1]),
        "--size_z",
        _number(size[2]),
        "--scoring",
        SCORING_MODE,
        "--exhaustiveness",
        str(
            _bounded_int(
                exhaustiveness, name="exhaustiveness", minimum=1, maximum=1_000_000
            )
        ),
        "--num_modes",
        str(_bounded_int(num_modes, name="mode count", minimum=1, maximum=1000)),
        "--seed",
        str(_bounded_int(seed, name="seed", minimum=0, maximum=2_147_483_647)),
        "--cpu",
        str(_bounded_int(cpu, name="CPU count", minimum=1, maximum=65_536)),
        "--out",
        output,
    ]
    if log_path is not None:
        log = _text(log_path, name="log path")
        if log in {receptor, ligand, output}:
            raise OracleAdapterError("malformed", "Vina log path aliases another path")
        command.extend(("--log", log))
    return tuple(command)


build_vina_command = build_command


def parse_score_table(stdout: str) -> tuple[VinaScore, ...]:
    """Parse the ranked affinity table printed by AutoDock Vina."""

    if not isinstance(stdout, str):
        raise OracleAdapterError("malformed", "Vina score output is malformed")
    lines = stdout.splitlines()
    header_index = next(
        (
            index
            for index, line in enumerate(lines)
            if "mode" in line.lower() and "affinity" in line.lower()
        ),
        None,
    )
    if header_index is None or not any(
        "rmsd" in line.lower() for line in lines[header_index : header_index + 3]
    ):
        raise OracleAdapterError("malformed", "Vina score output is malformed")
    scores: list[VinaScore] = []
    for line in lines[header_index + 1 :]:
        tokens = line.split()
        if len(tokens) != 4:
            continue
        try:
            rank = int(tokens[0], 10)
        except ValueError:
            continue
        score = VinaScore(
            rank=rank,
            affinity_kcal_mol=_finite_float(tokens[1], name="affinity"),
            rmsd_lower_bound_angstrom=_finite_float(tokens[2], name="RMSD lower bound"),
            rmsd_upper_bound_angstrom=_finite_float(tokens[3], name="RMSD upper bound"),
        )
        scores.append(score)
    if not scores:
        raise OracleAdapterError("malformed", "Vina score output is malformed")
    for expected_rank, score in enumerate(scores, start=1):
        if score.rank != expected_rank:
            raise OracleAdapterError("malformed", "Vina score ranks are malformed")
        if (
            score.rmsd_lower_bound_angstrom < 0.0
            or score.rmsd_upper_bound_angstrom < score.rmsd_lower_bound_angstrom
        ):
            raise OracleAdapterError("malformed", "Vina score RMSD is malformed")
    if any(
        current.affinity_kcal_mol < previous.affinity_kcal_mol
        for previous, current in zip(scores, scores[1:])
    ):
        raise OracleAdapterError("malformed", "Vina affinity ordering is malformed")
    return tuple(scores)


def _atom_coordinates(line: str) -> tuple[float, float, float]:
    if len(line) < 54:
        raise OracleAdapterError("malformed", "Vina pose atom row is malformed")
    return (
        _finite_float(line[30:38].strip(), name="pose coordinate"),
        _finite_float(line[38:46].strip(), name="pose coordinate"),
        _finite_float(line[46:54].strip(), name="pose coordinate"),
    )


def _pose_from_lines(lines: Sequence[str], *, rank: int) -> VinaPose:
    result_rows = [
        match for line in lines if (match := _RESULT_RE.match(line)) is not None
    ]
    if len(result_rows) != 1:
        raise OracleAdapterError("malformed", "Vina pose score annotation is malformed")
    affinity = _finite_float(result_rows[0].group(1), name="pose affinity")
    _finite_float(result_rows[0].group(2), name="pose RMSD")
    _finite_float(result_rows[0].group(3), name="pose RMSD")
    atom_count = 0
    for line in lines:
        if line.startswith(("ATOM  ", "HETATM")):
            _atom_coordinates(line)
            atom_count += 1
    if atom_count < 1:
        raise OracleAdapterError("malformed", "Vina pose has no finite atoms")
    return VinaPose(rank=rank, affinity_kcal_mol=affinity, atom_count=atom_count)


def validate_pose_text(pose_text: str) -> tuple[VinaPose, ...]:
    """Validate PDBQT models, score annotations, and finite atom coordinates."""

    if not isinstance(pose_text, str) or not pose_text.strip():
        raise OracleAdapterError("malformed", "Vina pose output is malformed")
    lines = pose_text.splitlines()
    has_models = any(line.startswith("MODEL") for line in lines)
    if not has_models:
        return (_pose_from_lines(lines, rank=1),)

    poses: list[VinaPose] = []
    active: list[str] | None = None
    active_rank = 0
    for line in lines:
        if line.startswith("MODEL"):
            if active is not None:
                raise OracleAdapterError("malformed", "Vina pose models are malformed")
            tokens = line.split()
            if len(tokens) != 2:
                raise OracleAdapterError(
                    "malformed", "Vina pose model rank is malformed"
                )
            try:
                active_rank = int(tokens[1], 10)
            except ValueError as exc:
                raise OracleAdapterError(
                    "malformed", "Vina pose model rank is malformed"
                ) from exc
            if active_rank != len(poses) + 1:
                raise OracleAdapterError(
                    "malformed", "Vina pose model rank is malformed"
                )
            active = []
        elif line.startswith("ENDMDL"):
            if active is None:
                raise OracleAdapterError("malformed", "Vina pose models are malformed")
            poses.append(_pose_from_lines(active, rank=active_rank))
            active = None
        elif active is not None:
            active.append(line)
        elif line.strip() and not line.startswith(
            ("REMARK", "ROOT", "ENDROOT", "TORSDOF")
        ):
            raise OracleAdapterError("malformed", "Vina pose models are malformed")
    if active is not None or not poses:
        raise OracleAdapterError("malformed", "Vina pose models are malformed")
    return tuple(poses)


def parse_output(stdout: str, pose_text: str) -> VinaResult:
    """Cross-check Vina's score table against its PDBQT pose artifact."""

    scores = parse_score_table(stdout)
    poses = validate_pose_text(pose_text)
    if len(scores) != len(poses):
        raise OracleAdapterError("malformed", "Vina score and pose counts disagree")
    for score, pose in zip(scores, poses):
        if score.rank != pose.rank or not math.isclose(
            score.affinity_kcal_mol,
            pose.affinity_kcal_mol,
            rel_tol=0.0,
            abs_tol=1.0e-3,
        ):
            raise OracleAdapterError(
                "malformed", "Vina score and pose affinities disagree"
            )
    return VinaResult(scores=scores, poses=poses)


parse_vina_output = parse_output


def run_vina(
    binary: str | Path,
    *,
    request: OracleRequest,
    expected_executable_sha256: str,
    receptor_pdbqt: str | Path,
    ligand_pdbqt: str | Path,
    center_angstrom: Sequence[float],
    size_angstrom: Sequence[float],
    exhaustiveness: int = 8,
    num_modes: int = 9,
    timeout_seconds: float = 300.0,
    max_pose_bytes: int = DEFAULT_MAX_ARTIFACT_BYTES,
) -> VinaRun:
    """Return a SHA-bound result and bounded pose bytes without publishing files."""

    center = _triple(center_angstrom, name="box center", positive=False)
    size = _triple(size_angstrom, name="box size", positive=True)
    expected_parameters = {
        "center_angstrom": center,
        "size_angstrom": size,
        "exhaustiveness": exhaustiveness,
        "num_modes": num_modes,
        "scoring": SCORING_MODE,
        "cnn_scoring": CNN_SCORING_MODE,
    }
    if (
        not isinstance(request, OracleRequest)
        or dict(request.parameters) != expected_parameters
    ):
        raise OracleAdapterError("malformed", "Vina request parameters are mismatched")
    inputs = {"receptor": receptor_pdbqt, "ligand": ligand_pdbqt}
    original_executable = Path(binary)
    engine_version = "unverified"
    failure_hashes: dict[str, str] = {}
    try:
        with pinned_oracle_workspace(
            binary,
            expected_executable_sha256,
            request,
            inputs,
            engine_id="vina",
            task=ORACLE_TASK,
        ) as workspace:
            executable_hash = workspace.executable_sha256
            workspace_output = workspace.output_path("poses.pdbqt")
            argv = build_command(
                workspace.executable,
                receptor_pdbqt=workspace.inputs["receptor"],
                ligand_pdbqt=workspace.inputs["ligand"],
                output_pdbqt=workspace_output,
                center_angstrom=center,
                size_angstrom=size,
                exhaustiveness=exhaustiveness,
                num_modes=num_modes,
                seed=request.seed,
                cpu=request.thread_count,
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
            identity = parse_version(
                "\n".join(
                    part
                    for part in (version_command.stdout, version_command.stderr)
                    if part
                ),
                executable=str(original_executable),
            )
            engine_version = identity.version
            command_output = run_argv(
                argv,
                timeout_seconds=timeout_seconds,
                expected_executable_sha256=executable_hash,
                env=environment,
                pass_fds=workspace.pass_fds,
                writable_directory_fds=workspace.writable_directory_fds,
                integrity_check=workspace.verify_unchanged,
            )
            failure_hashes.update(
                docking_stdout=command_output.stdout_sha256,
                docking_stderr=command_output.stderr_sha256,
            )
            completed = _decoded(command_output)
            pose_artifact = read_fresh_output(
                workspace_output, max_bytes=max_pose_bytes
            )
            failure_hashes["poses_pdbqt"] = pose_artifact.sha256
            pose_text = pose_artifact.data.decode("utf-8", errors="strict")
            result = parse_output(completed.stdout, pose_text)
            if not (
                1 <= len(result.scores) <= num_modes
                and 1 <= len(result.poses) <= num_modes
            ):
                raise OracleAdapterError(
                    "malformed", "Vina output mode count exceeds the request"
                )
            verify_request_inputs(request, inputs, engine_id="vina", task=ORACLE_TASK)
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
        engine_id="vina",
        engine_version=identity.version,
        executable_sha256=executable_hash,
        status="success",
        values={
            "scoring": SCORING_MODE,
            "cnn_scoring": CNN_SCORING_MODE,
            "affinity_kcal_mol": tuple(
                score.affinity_kcal_mol for score in result.scores
            ),
            "pose_atom_count": tuple(pose.atom_count for pose in result.poses),
        },
        raw_output_sha256={
            "version_stdout": version_output.stdout_sha256,
            "version_stderr": version_output.stderr_sha256,
            "docking_stdout": command_output.stdout_sha256,
            "docking_stderr": command_output.stderr_sha256,
            "poses_pdbqt": pose_artifact.sha256,
        },
    )
    return VinaRun(
        identity=identity,
        command=completed,
        result=result,
        pose_pdbqt=pose_artifact.data,
        provenance=provenance,
    )


run = run_vina


__all__ = [
    "CNN_SCORING_MODE",
    "CommandOutput",
    "OracleAdapterError",
    "ORACLE_TASK",
    "SCORING_MODE",
    "VinaIdentity",
    "VinaPose",
    "VinaResult",
    "VinaRun",
    "VinaScore",
    "build_command",
    "build_vina_command",
    "parse_output",
    "parse_score_table",
    "parse_version",
    "parse_vina_output",
    "probe_identity",
    "run",
    "run_vina",
    "validate_pose_text",
]
