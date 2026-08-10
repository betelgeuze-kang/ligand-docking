"""Prepared-input-only GNINA benchmark adapter.

The adapter freezes GNINA to Vina empirical scoring plus CNN rescoring with the
``crossdock_default2018`` model.  Input preparation and every product dispatch
path remain outside this external-oracle package.
"""

from __future__ import annotations

from collections.abc import Mapping
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
CNN_SCORING_MODE = "rescore"
CNN_MODEL = "crossdock_default2018"
ORACLE_TASK = "docking"
_ERROR_CODES = frozenset({"binary_missing", "timeout", "nonzero", "malformed"})
_VERSION_RE = re.compile(
    r"\bgnina\s+v?([0-9]+(?:\.[0-9]+)+(?:[-+._A-Za-z0-9]*)?)\b", re.I
)
_PROPERTY_RE = re.compile(r"^>\s*<([^>]+)>\s*$")
_RECEPTOR_SUFFIXES = frozenset({".pdb", ".pdbqt"})
_LIGAND_SUFFIXES = frozenset({".sdf", ".mol", ".mol2", ".pdbqt"})


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
            raise ValueError("unsupported GNINA adapter error code")
        super().__init__(message)
        self.code = code
        self.provenance = provenance


@dataclass(frozen=True)
class CommandOutput:
    argv: tuple[str, ...]
    stdout: str
    stderr: str


@dataclass(frozen=True)
class GninaIdentity:
    executable: str
    version: str
    scoring: str = SCORING_MODE
    cnn_scoring: str = CNN_SCORING_MODE
    cnn_model: str = CNN_MODEL


@dataclass(frozen=True)
class GninaScore:
    rank: int
    affinity_kcal_mol: float
    intramolecular_energy_kcal_mol: float
    cnn_pose_score: float
    cnn_affinity: float


@dataclass(frozen=True)
class GninaPose:
    rank: int
    affinity_kcal_mol: float
    cnn_pose_score: float
    cnn_affinity: float
    atom_count: int


@dataclass(frozen=True)
class GninaResult:
    scores: tuple[GninaScore, ...]
    poses: tuple[GninaPose, ...]


@dataclass(frozen=True)
class GninaRun:
    identity: GninaIdentity
    command: CommandOutput
    result: GninaResult
    pose_sdf: bytes
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
                engine_id="gnina",
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
        f"GNINA high-assurance execution failed: {source_code}",
        provenance=provenance,
    )


def _decoded(output: ExecutionOutput) -> CommandOutput:
    try:
        stdout = output.stdout.decode("utf-8", errors="strict")
        stderr = output.stderr.decode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise OracleAdapterError(
            "malformed", "GNINA command output is malformed"
        ) from exc
    return CommandOutput(argv=output.argv, stdout=stdout, stderr=stderr)


def _text(value: str | Path, *, name: str) -> str:
    if not isinstance(value, (str, Path)):
        raise OracleAdapterError("malformed", f"GNINA {name} is malformed")
    rendered = str(value)
    if not rendered or "\x00" in rendered:
        raise OracleAdapterError("malformed", f"GNINA {name} is malformed")
    return rendered


def _prepared_path(
    value: str | Path,
    *,
    name: str,
    suffixes: frozenset[str],
) -> str:
    rendered = _text(value, name=name)
    if Path(rendered).suffix.lower() not in suffixes:
        raise OracleAdapterError(
            "malformed", f"GNINA {name} is not an accepted prepared structure path"
        )
    return rendered


def _positive_timeout(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OracleAdapterError("malformed", "GNINA timeout is malformed")
    timeout = float(value)
    if not math.isfinite(timeout) or timeout <= 0.0:
        raise OracleAdapterError("malformed", "GNINA timeout is malformed")
    return timeout


def _bounded_int(value: int, *, name: str, minimum: int, maximum: int) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < minimum
        or value > maximum
    ):
        raise OracleAdapterError("malformed", f"GNINA {name} is malformed")
    return value


def _finite_float(value: object, *, name: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise OracleAdapterError("malformed", f"GNINA {name} is malformed") from exc
    if not math.isfinite(parsed):
        raise OracleAdapterError("malformed", f"GNINA {name} is malformed")
    return parsed


def _positive_float(value: object, *, name: str) -> float:
    parsed = _finite_float(value, name=name)
    if parsed <= 0.0:
        raise OracleAdapterError("malformed", f"GNINA {name} is malformed")
    return parsed


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


def parse_version(version_text: str, *, executable: str = "gnina") -> GninaIdentity:
    """Parse a GNINA version string and attach the frozen scoring identity."""

    if not isinstance(version_text, str):
        raise OracleAdapterError("malformed", "GNINA version output is malformed")
    match = _VERSION_RE.search(version_text)
    if match is None:
        raise OracleAdapterError("malformed", "GNINA version output is malformed")
    return GninaIdentity(
        executable=_text(executable, name="binary"), version=match.group(1)
    )


def probe_identity(
    binary: str | Path = "gnina",
    *,
    timeout_seconds: float = 10.0,
    runner: Runner = subprocess.run,
) -> GninaIdentity:
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
    receptor: str | Path,
    ligand: str | Path,
    autobox_ligand: str | Path,
    output_sdf: str | Path,
    autobox_add_angstrom: float = 4.0,
    exhaustiveness: int = 8,
    num_modes: int = 9,
    seed: int = 0,
    cpu: int = 1,
    scoring: str = SCORING_MODE,
    cnn_scoring: str = CNN_SCORING_MODE,
    cnn_model: str = CNN_MODEL,
) -> tuple[str, ...]:
    """Build canonical CPU GNINA argv from already prepared structures."""

    if (
        scoring != SCORING_MODE
        or cnn_scoring != CNN_SCORING_MODE
        or cnn_model != CNN_MODEL
    ):
        raise OracleAdapterError("malformed", "GNINA scoring identity is malformed")
    receptor_path = _prepared_path(
        receptor, name="receptor path", suffixes=_RECEPTOR_SUFFIXES
    )
    ligand_path = _prepared_path(ligand, name="ligand path", suffixes=_LIGAND_SUFFIXES)
    autobox_path = _prepared_path(
        autobox_ligand, name="autobox ligand path", suffixes=_LIGAND_SUFFIXES
    )
    output_path = _prepared_path(
        output_sdf, name="output path", suffixes=frozenset({".sdf"})
    )
    if output_path in {receptor_path, ligand_path, autobox_path}:
        raise OracleAdapterError("malformed", "GNINA output path aliases an input")
    autobox_add = _positive_float(autobox_add_angstrom, name="autobox padding")
    return (
        _text(binary, name="binary"),
        "--receptor",
        receptor_path,
        "--ligand",
        ligand_path,
        "--autobox_ligand",
        autobox_path,
        "--autobox_add",
        _number(autobox_add),
        "--scoring",
        SCORING_MODE,
        "--cnn_scoring",
        CNN_SCORING_MODE,
        "--cnn",
        CNN_MODEL,
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
        "--no_gpu",
        "--out",
        output_path,
    )


build_gnina_command = build_command


def build_prepared_redocking_command(
    case_id: str,
    engine_id: str,
    paths: Mapping[str, str | Path],
    *,
    binary: str | Path,
    output: str | Path,
    seed: int,
) -> tuple[str, ...]:
    """Build the frozen public-redocking command for either GNINA mode.

    The ``vina`` lane intentionally uses the pinned GNINA executable with CNN
    scoring disabled.  This preserves a common prepared-input and process
    environment while making the empirical-only and CNN-rescored identities
    explicit.  The argument order is part of the frozen benchmark contract.
    """

    _text(case_id, name="case id")
    if engine_id not in {"vina", "gnina"}:
        raise OracleAdapterError("malformed", "GNINA redocking mode is malformed")
    if not isinstance(paths, Mapping):
        raise OracleAdapterError("malformed", "GNINA redocking paths are malformed")
    try:
        receptor = _prepared_path(
            paths["receptor"], name="receptor path", suffixes=_RECEPTOR_SUFFIXES
        )
        ligand = _prepared_path(
            paths["seed"], name="ligand path", suffixes=_LIGAND_SUFFIXES
        )
        autobox = _prepared_path(
            paths["native"], name="autobox ligand path", suffixes=_LIGAND_SUFFIXES
        )
    except KeyError as exc:
        raise OracleAdapterError(
            "malformed", "GNINA redocking paths are malformed"
        ) from exc
    output_path = _prepared_path(
        output, name="output path", suffixes=frozenset({".sdf"})
    )
    if output_path in {receptor, ligand, autobox}:
        raise OracleAdapterError("malformed", "GNINA output path aliases an input")
    command = [
        _text(binary, name="binary"),
        "--receptor",
        receptor,
        "--ligand",
        ligand,
        "--autobox_ligand",
        autobox,
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
        str(_bounded_int(seed, name="seed", minimum=0, maximum=2_147_483_647)),
        "--out",
        output_path,
    ]
    if engine_id == "vina":
        command.extend(("--scoring", SCORING_MODE, "--cnn_scoring", "none"))
    else:
        command.extend(
            (
                "--scoring",
                SCORING_MODE,
                "--cnn_scoring",
                CNN_SCORING_MODE,
                "--cnn",
                CNN_MODEL,
            )
        )
    return tuple(command)


def parse_score_table(stdout: str) -> tuple[GninaScore, ...]:
    """Parse finite GNINA empirical and CNN values for each ranked mode."""

    if not isinstance(stdout, str):
        raise OracleAdapterError("malformed", "GNINA score output is malformed")
    lines = stdout.splitlines()
    header_index = next(
        (
            index
            for index, line in enumerate(lines)
            if "mode" in line.lower()
            and "affinity" in line.lower()
            and "cnn" in line.lower()
        ),
        None,
    )
    if header_index is None:
        raise OracleAdapterError("malformed", "GNINA score output is malformed")
    scores: list[GninaScore] = []
    for line in lines[header_index + 1 :]:
        tokens = line.split()
        if len(tokens) != 5:
            continue
        try:
            rank = int(tokens[0], 10)
        except ValueError:
            continue
        score = GninaScore(
            rank=rank,
            affinity_kcal_mol=_finite_float(tokens[1], name="affinity"),
            intramolecular_energy_kcal_mol=_finite_float(
                tokens[2], name="intramolecular energy"
            ),
            cnn_pose_score=_finite_float(tokens[3], name="CNN pose score"),
            cnn_affinity=_finite_float(tokens[4], name="CNN affinity"),
        )
        if not 0.0 <= score.cnn_pose_score <= 1.0:
            raise OracleAdapterError("malformed", "GNINA CNN pose score is malformed")
        scores.append(score)
    if not scores:
        raise OracleAdapterError("malformed", "GNINA score output is malformed")
    if any(score.rank != rank for rank, score in enumerate(scores, start=1)):
        raise OracleAdapterError("malformed", "GNINA score ranks are malformed")
    return tuple(scores)


def _split_sdf_records(sdf_text: str) -> tuple[tuple[str, ...], ...]:
    if not isinstance(sdf_text, str) or not sdf_text.strip():
        raise OracleAdapterError("malformed", "GNINA pose output is malformed")
    records: list[tuple[str, ...]] = []
    current: list[str] = []
    for line in sdf_text.splitlines():
        if line.strip() == "$$$$":
            if not any(item.strip() for item in current):
                raise OracleAdapterError("malformed", "GNINA SDF records are malformed")
            records.append(tuple(current))
            current = []
        else:
            current.append(line)
    if any(line.strip() for line in current) or not records:
        raise OracleAdapterError("malformed", "GNINA SDF records are malformed")
    return tuple(records)


def _properties(lines: Sequence[str]) -> dict[str, str]:
    properties: dict[str, str] = {}
    index = 0
    while index < len(lines):
        match = _PROPERTY_RE.match(lines[index])
        if match is None:
            index += 1
            continue
        name = match.group(1).strip().lower()
        if name in properties:
            raise OracleAdapterError("malformed", "GNINA SDF properties are malformed")
        index += 1
        values: list[str] = []
        while index < len(lines) and lines[index].strip():
            if _PROPERTY_RE.match(lines[index]) is not None:
                break
            values.append(lines[index].strip())
            index += 1
        if len(values) != 1:
            raise OracleAdapterError("malformed", "GNINA SDF properties are malformed")
        properties[name] = values[0]
    return properties


def _parse_sdf_pose(lines: Sequence[str], *, rank: int) -> GninaPose:
    if len(lines) < 4:
        raise OracleAdapterError("malformed", "GNINA SDF molecule is malformed")
    counts = lines[3]
    if len(counts) < 6:
        raise OracleAdapterError("malformed", "GNINA SDF counts are malformed")
    try:
        atom_count = int(counts[0:3])
        bond_count = int(counts[3:6])
    except ValueError as exc:
        raise OracleAdapterError("malformed", "GNINA SDF counts are malformed") from exc
    if atom_count < 1 or bond_count < 0 or len(lines) < 4 + atom_count + bond_count:
        raise OracleAdapterError("malformed", "GNINA SDF counts are malformed")
    for line in lines[4 : 4 + atom_count]:
        tokens = line.split()
        if len(tokens) < 4:
            raise OracleAdapterError("malformed", "GNINA SDF atom row is malformed")
        for token in tokens[:3]:
            _finite_float(token, name="pose coordinate")

    properties = _properties(lines[4 + atom_count + bond_count :])
    required = ("minimizedaffinity", "cnnscore", "cnnaffinity")
    if any(name not in properties for name in required):
        raise OracleAdapterError(
            "malformed", "GNINA SDF scoring properties are malformed"
        )
    cnn_pose_score = _finite_float(properties["cnnscore"], name="CNN pose score")
    if not 0.0 <= cnn_pose_score <= 1.0:
        raise OracleAdapterError("malformed", "GNINA CNN pose score is malformed")
    return GninaPose(
        rank=rank,
        affinity_kcal_mol=_finite_float(
            properties["minimizedaffinity"], name="pose affinity"
        ),
        cnn_pose_score=cnn_pose_score,
        cnn_affinity=_finite_float(properties["cnnaffinity"], name="CNN affinity"),
        atom_count=atom_count,
    )


def validate_pose_text(sdf_text: str) -> tuple[GninaPose, ...]:
    """Validate finite V2000 SDF coordinates and GNINA scoring properties."""

    return tuple(
        _parse_sdf_pose(lines, rank=rank)
        for rank, lines in enumerate(_split_sdf_records(sdf_text), start=1)
    )


def parse_output(stdout: str, sdf_text: str) -> GninaResult:
    """Cross-check GNINA's table with the scoring properties in output SDF."""

    scores = parse_score_table(stdout)
    poses = validate_pose_text(sdf_text)
    if len(scores) != len(poses):
        raise OracleAdapterError("malformed", "GNINA score and pose counts disagree")
    for score, pose in zip(scores, poses):
        if score.rank != pose.rank or not all(
            (
                math.isclose(
                    score.affinity_kcal_mol,
                    pose.affinity_kcal_mol,
                    rel_tol=0.0,
                    abs_tol=1.0e-3,
                ),
                math.isclose(
                    score.cnn_pose_score,
                    pose.cnn_pose_score,
                    rel_tol=0.0,
                    abs_tol=1.0e-3,
                ),
                math.isclose(
                    score.cnn_affinity,
                    pose.cnn_affinity,
                    rel_tol=0.0,
                    abs_tol=1.0e-3,
                ),
            )
        ):
            raise OracleAdapterError(
                "malformed", "GNINA score and pose values disagree"
            )
    return GninaResult(scores=scores, poses=poses)


parse_gnina_output = parse_output


def run_gnina(
    binary: str | Path,
    *,
    request: OracleRequest,
    expected_executable_sha256: str,
    receptor: str | Path,
    ligand: str | Path,
    autobox_ligand: str | Path,
    autobox_add_angstrom: float = 4.0,
    exhaustiveness: int = 8,
    num_modes: int = 9,
    timeout_seconds: float = 300.0,
    max_pose_bytes: int = DEFAULT_MAX_ARTIFACT_BYTES,
) -> GninaRun:
    """Return a SHA-bound result and bounded pose bytes without publishing files."""

    autobox_add = _positive_float(autobox_add_angstrom, name="autobox padding")
    expected_parameters = {
        "autobox_add_angstrom": autobox_add,
        "exhaustiveness": exhaustiveness,
        "num_modes": num_modes,
        "scoring": SCORING_MODE,
        "cnn_scoring": CNN_SCORING_MODE,
        "cnn_model": CNN_MODEL,
        "no_gpu": True,
    }
    if (
        not isinstance(request, OracleRequest)
        or dict(request.parameters) != expected_parameters
    ):
        raise OracleAdapterError("malformed", "GNINA request parameters are mismatched")
    inputs = {
        "receptor": receptor,
        "ligand": ligand,
        "autobox_ligand": autobox_ligand,
    }
    original_executable = Path(binary)
    engine_version = "unverified"
    failure_hashes: dict[str, str] = {}
    try:
        with pinned_oracle_workspace(
            binary,
            expected_executable_sha256,
            request,
            inputs,
            engine_id="gnina",
            task=ORACLE_TASK,
        ) as workspace:
            executable_hash = workspace.executable_sha256
            workspace_output = workspace.output_path("poses.sdf")
            argv = build_command(
                workspace.executable,
                receptor=workspace.inputs["receptor"],
                ligand=workspace.inputs["ligand"],
                autobox_ligand=workspace.inputs["autobox_ligand"],
                output_sdf=workspace_output,
                autobox_add_angstrom=autobox_add,
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
            failure_hashes["poses_sdf"] = pose_artifact.sha256
            sdf_text = pose_artifact.data.decode("utf-8", errors="strict")
            result = parse_output(completed.stdout, sdf_text)
            if not (
                1 <= len(result.scores) <= num_modes
                and 1 <= len(result.poses) <= num_modes
            ):
                raise OracleAdapterError(
                    "malformed", "GNINA output mode count exceeds the request"
                )
            verify_request_inputs(request, inputs, engine_id="gnina", task=ORACLE_TASK)
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
        engine_id="gnina",
        engine_version=identity.version,
        executable_sha256=executable_hash,
        status="success",
        values={
            "scoring": SCORING_MODE,
            "cnn_scoring": CNN_SCORING_MODE,
            "cnn_model": CNN_MODEL,
            "affinity_kcal_mol": tuple(
                score.affinity_kcal_mol for score in result.scores
            ),
            "cnn_pose_score": tuple(score.cnn_pose_score for score in result.scores),
            "cnn_affinity": tuple(score.cnn_affinity for score in result.scores),
            "pose_atom_count": tuple(pose.atom_count for pose in result.poses),
        },
        raw_output_sha256={
            "version_stdout": version_output.stdout_sha256,
            "version_stderr": version_output.stderr_sha256,
            "docking_stdout": command_output.stdout_sha256,
            "docking_stderr": command_output.stderr_sha256,
            "poses_sdf": pose_artifact.sha256,
        },
    )
    return GninaRun(
        identity=identity,
        command=completed,
        result=result,
        pose_sdf=pose_artifact.data,
        provenance=provenance,
    )


run = run_gnina


__all__ = [
    "CNN_MODEL",
    "CNN_SCORING_MODE",
    "CommandOutput",
    "GninaIdentity",
    "GninaPose",
    "GninaResult",
    "GninaRun",
    "GninaScore",
    "OracleAdapterError",
    "ORACLE_TASK",
    "SCORING_MODE",
    "build_command",
    "build_gnina_command",
    "build_prepared_redocking_command",
    "parse_gnina_output",
    "parse_output",
    "parse_score_table",
    "parse_version",
    "probe_identity",
    "run",
    "run_gnina",
    "validate_pose_text",
]
