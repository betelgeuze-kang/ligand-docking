"""Bounded, failure-inclusive runner for the frozen minimization matrix.

The runner consumes one persisted run-start environment receipt, creates one
durable start marker, and evaluates all fourteen frozen cases.  Its return
value is an in-memory observation, never a validation result receipt.  No
scientific, product, benchmark, or customer-execution claim is opened here.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import stat
import struct
import subprocess
import sys
import time
from typing import Any, Mapping, Sequence

from .reference_constrained_minimization import (
    minimize_reference_force_field_v2_constrained,
)
from .reference_minimization import minimize_reference_force_field
from .reference_minimization_independent_oracle import (
    evaluate_independent_minimization_oracle,
)
from .reference_minimization_validation_bootstrap import (
    REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_STATE_ATTRIBUTE,
    REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_MAX_REQUEST_BYTES,
    REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_RUNNER_REQUEST_SCHEMA_ID,
    REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_TRUST_STORE_MAX_BYTES,
    REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_TRUST_STORE_PATH,
    REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_TRUST_STORE_SCHEMA_ID,
    REFERENCE_MINIMIZATION_VALIDATION_CONTROLLED_INNER_STAGE_ENV,
    REFERENCE_MINIMIZATION_VALIDATION_CONTROLLED_INNER_STATE,
    REFERENCE_MINIMIZATION_VALIDATION_LOGICAL_RUNNER_ARGV,
    REFERENCE_MINIMIZATION_VALIDATION_TRUSTED_OUTER_LAUNCHER_ARGV,
    reference_minimization_validation_bootstrap_path,
    reference_minimization_validation_controlled_inner_environment,
    reference_minimization_validation_execution_source_sha256,
)
from .reference_minimization_validation_dependency_identity import (
    REFERENCE_MINIMIZATION_VALIDATION_REQUIRED_DEPENDENCY_ARTIFACT_IDS,
    ReferenceMinimizationValidationDependencyIdentityError,
    observed_reference_minimization_validation_dependency_artifact_sha256_rows,
)
from .reference_minimization_validation_materializer import (
    cpu_minimization_validation_materialization_manifest_document,
    materialize_frozen_cpu_minimization_validation_case,
)
from .reference_minimization_validation_nonce_reservation import (
    ReferenceMinimizationValidationNonceReservationError,
    _open_secure_root,
    _stable_record_identity,
    _validate_record_stat,
)
from .reference_minimization_validation_protocol import (
    FROZEN_CPU_MINIMIZATION_VALIDATION_PROTOCOL_SHA256,
    cpu_minimization_validation_case_atom_count,
    cpu_minimization_validation_protocol_document,
)
from .reference_minimization_validation_run_start import (
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RUN_START_CONTRACT_SHA256,
    REFERENCE_MINIMIZATION_VALIDATION_APPLICATION_SEED_ENV,
    ReferenceMinimizationValidationRunStartError,
    _require_reference_minimization_validation_root_outside_checkout,
    require_reference_minimization_validation_execution_environment_receipt_for_runner,
)


REFERENCE_MINIMIZATION_VALIDATION_RUNNER_CONTRACT_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_validation_runner_contract/3.0.0"
)
REFERENCE_MINIMIZATION_VALIDATION_RUNNER_START_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_validation_runner_start/2.0.0"
)
REFERENCE_MINIMIZATION_VALIDATION_RUN_OBSERVATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_validation_run_observation/2.0.0"
)
REFERENCE_MINIMIZATION_VALIDATION_RUNNER_CONTRACT_ID = (
    "cpu_reference_minimization_validation_bounded_runner/3.0.0"
)
REFERENCE_MINIMIZATION_VALIDATION_RUNNER_CONTRACT_VERSION = "3.0.0"
REFERENCE_MINIMIZATION_VALIDATION_RUNNER_CONTRACT_FROZEN_AT_UTC = "2026-07-19T08:00:00Z"
REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_RECEIPT_AGE = timedelta(minutes=5)
REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_WALL_SECONDS = 120.0
REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_CASES = 14
REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_START_RECORD_BYTES = 65_536
REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_WORKER_OUTPUT_BYTES = 8 * 1_048_576
REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_REQUEST_BYTES = (
    REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_MAX_REQUEST_BYTES
)
REFERENCE_MINIMIZATION_VALIDATION_TRUST_STORE_MAX_BYTES = (
    REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_TRUST_STORE_MAX_BYTES
)
REFERENCE_MINIMIZATION_VALIDATION_TRUST_STORE_PATH = (
    REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_TRUST_STORE_PATH
)
REFERENCE_MINIMIZATION_VALIDATION_RUNNER_REQUEST_SCHEMA_ID = (
    REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_RUNNER_REQUEST_SCHEMA_ID
)
REFERENCE_MINIMIZATION_VALIDATION_RUNNER_RESPONSE_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_validation_runner_response/1.0.0"
)
REFERENCE_MINIMIZATION_VALIDATION_MATRIX_WORKER_REQUEST_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_validation_matrix_worker_request/2.0.0"
)
_REFERENCE_MINIMIZATION_VALIDATION_FIXED_WORKER_BOOTSTRAP = (
    "from betelgeuze_engine_v2.physics import "
    "reference_minimization_validation_runner as worker;"
    "raise SystemExit(worker._matrix_worker_main_from_standard_streams())"
)
_REFERENCE_MINIMIZATION_VALIDATION_WORKER_ENVIRONMENT_NAMES = frozenset(
    {
        REFERENCE_MINIMIZATION_VALIDATION_APPLICATION_SEED_ENV,
        "CUDA_VISIBLE_DEVICES",
        "HIP_VISIBLE_DEVICES",
        "HOME",
        "LANG",
        "LC_ALL",
        "MKL_NUM_THREADS",
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "PATH",
        "PYTHONDONTWRITEBYTECODE",
        "PYTHONHASHSEED",
        "PYTHONNOUSERSITE",
        "PYTHONPATH",
        "PYTHONPYCACHEPREFIX",
        "ROCR_VISIBLE_DEVICES",
        "TZ",
    }
)
REFERENCE_MINIMIZATION_VALIDATION_TRUST_STORE_SCHEMA_ID = (
    REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_TRUST_STORE_SCHEMA_ID
)
REFERENCE_MINIMIZATION_VALIDATION_RUNNER_START_PREFIX = (
    "reference-minimization-validation-runner-start-"
)
FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RUNNER_CONTRACT_SHA256 = (
    "980f0110ce7849795110f2cf034717ae7b71704d5e4a0a8a1520a99f6aee3c7b"
)

REFERENCE_MINIMIZATION_VALIDATION_TRACE_SOURCES = (
    "operational",
    "independent_oracle",
)
REFERENCE_MINIMIZATION_VALIDATION_TRACE_STATES = (
    "evaluated",
    "not_evaluated_expected_fail_closed",
    "not_evaluated_unexpected_failure",
)
REFERENCE_MINIMIZATION_VALIDATION_COORDINATE_ENCODING = "python_float_hex"
REFERENCE_MINIMIZATION_VALIDATION_COORDINATE_DIGEST_ALGORITHM = "sha256_f64le"


class ReferenceMinimizationValidationRunnerError(RuntimeError):
    """The bounded runner contract or execution preflight failed."""


class ReferenceMinimizationValidationRunnerAlreadyStartedError(
    ReferenceMinimizationValidationRunnerError
):
    """The authorization nonce already has a durable runner-start marker."""


def _require_runner_root_outside_checkout(
    root: str | os.PathLike[str],
    *,
    name: str,
) -> None:
    try:
        _require_reference_minimization_validation_root_outside_checkout(
            root,
            name=name,
        )
    except ReferenceMinimizationValidationRunStartError as exc:
        raise ReferenceMinimizationValidationRunnerError(
            f"{name} must be outside the source checkout"
        ) from exc


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise ReferenceMinimizationValidationRunnerError(
            "runner artifact is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ReferenceMinimizationValidationRunnerError(
            f"{name} must be a lowercase SHA-256"
        )
    return value


def _require_commit(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 40
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ReferenceMinimizationValidationRunnerError(
            f"{name} must be a lowercase Git commit SHA"
        )
    return value


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _format_utc(value: datetime) -> str:
    return (
        value.astimezone(timezone.utc)
        .replace(microsecond=0)
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )


def _parse_utc(value: object, *, name: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ReferenceMinimizationValidationRunnerError(
            f"{name} must be second-resolution UTC"
        )
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise ReferenceMinimizationValidationRunnerError(
            f"{name} must be second-resolution UTC"
        ) from exc


def reference_minimization_validation_runner_source_sha256() -> str:
    """Return the exact bootstrap-plus-runner source identity."""

    return reference_minimization_validation_execution_source_sha256()


def _require_source_only_python_runtime() -> None:
    if (
        os.environ.get("PYTHONDONTWRITEBYTECODE") != "1"
        or os.environ.get("PYTHONPYCACHEPREFIX") != "/dev/null"
        or sys.flags.dont_write_bytecode != 1
        or sys.dont_write_bytecode is not True
        or sys.pycache_prefix != "/dev/null"
    ):
        raise ReferenceMinimizationValidationRunnerError(
            "minimization runner requires source-only Python imports"
        )
    null_stat = os.lstat("/dev/null")
    if (
        not stat.S_ISCHR(null_stat.st_mode)
        or null_stat.st_uid != 0
        or os.major(null_stat.st_rdev) != 1
        or os.minor(null_stat.st_rdev) != 3
    ):
        raise ReferenceMinimizationValidationRunnerError(
            "source-only Python cache sink is invalid"
        )


def _require_trusted_dependency_roots(
    raw_dependency_roots: object,
) -> tuple[Path, ...]:
    if not isinstance(raw_dependency_roots, tuple) or not raw_dependency_roots:
        raise ReferenceMinimizationValidationRunnerError(
            "minimization runner dependency roots are invalid"
        )
    dependency_roots: list[Path] = []
    for raw_root in raw_dependency_roots:
        if not isinstance(raw_root, str) or not raw_root or os.pathsep in raw_root:
            raise ReferenceMinimizationValidationRunnerError(
                "minimization runner dependency root is invalid"
            )
        candidate = Path(raw_root)
        file_stat = candidate.lstat()
        resolved = candidate.resolve(strict=True)
        if (
            not candidate.is_absolute()
            or candidate.is_symlink()
            or resolved != candidate
            or not stat.S_ISDIR(file_stat.st_mode)
            or file_stat.st_uid != 0
            or stat.S_IMODE(file_stat.st_mode) & 0o022
        ):
            raise ReferenceMinimizationValidationRunnerError(
                "minimization runner dependency root is not trusted"
            )
        dependency_roots.append(resolved)
    import numpy
    import torch

    for dependency, name in ((numpy, "NumPy"), (torch, "Torch")):
        module_path = Path(dependency.__file__).resolve(strict=True)
        if not any(module_path.is_relative_to(root) for root in dependency_roots):
            raise ReferenceMinimizationValidationRunnerError(
                f"minimization runner {name} was not imported from a trusted root"
            )
    return tuple(dependency_roots)


def _require_isolated_python_bootstrap_runtime() -> tuple[Path, ...]:
    """Make the stdlib trust bootstrap mandatory for every real run."""

    state = getattr(
        sys, REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_STATE_ATTRIBUTE, None
    )
    expected_bootstrap = Path(reference_minimization_validation_bootstrap_path())
    expected_repository = Path(__file__).resolve(strict=True).parents[2]
    if (
        sys.flags.isolated != 0
        or sys.flags.ignore_environment != 0
        or sys.flags.no_site != 1
        or sys.flags.no_user_site != 1
        or sys.flags.dont_write_bytecode != 1
        or sys.dont_write_bytecode is not True
        or sys.pycache_prefix != "/dev/null"
        or not isinstance(state, tuple)
        or len(state) != 5
    ):
        raise ReferenceMinimizationValidationRunnerError(
            "minimization runner requires the seeded controlled trust bootstrap"
        )
    (
        state_marker,
        bootstrap_path,
        repository_root,
        raw_dependency_roots,
        frozen_sys_path,
    ) = state
    expected_orig_argv = (
        os.path.realpath(sys.executable),
        *REFERENCE_MINIMIZATION_VALIDATION_LOGICAL_RUNNER_ARGV[1:-1],
        os.fspath(expected_bootstrap),
    )
    try:
        expected_environment = (
            reference_minimization_validation_controlled_inner_environment()
        )
    except Exception as exc:
        raise ReferenceMinimizationValidationRunnerError(
            "minimization runner controlled environment is invalid"
        ) from exc
    if (
        state_marker != REFERENCE_MINIMIZATION_VALIDATION_CONTROLLED_INNER_STATE
        or bootstrap_path != os.fspath(expected_bootstrap)
        or repository_root != os.fspath(expected_repository)
        or not isinstance(frozen_sys_path, tuple)
        or tuple(sys.path) != frozen_sys_path
        or not sys.path
        or sys.path[0] != os.fspath(expected_repository)
        or tuple(getattr(sys, "orig_argv", ())) != expected_orig_argv
        or sys.argv != [os.fspath(expected_bootstrap)]
        or os.getcwd() != "/"
        or dict(os.environ) != expected_environment
        or os.environ.get(REFERENCE_MINIMIZATION_VALIDATION_CONTROLLED_INNER_STAGE_ENV)
        != REFERENCE_MINIMIZATION_VALIDATION_CONTROLLED_INNER_STATE
    ):
        raise ReferenceMinimizationValidationRunnerError(
            "minimization runner bootstrap state is invalid"
        )
    return _require_trusted_dependency_roots(raw_dependency_roots)


def _observe_dependency_artifact_sha256_rows(
    dependency_roots: tuple[Path, ...],
) -> dict[str, str]:
    try:
        return (
            observed_reference_minimization_validation_dependency_artifact_sha256_rows(
                dependency_roots
            )
        )
    except ReferenceMinimizationValidationDependencyIdentityError as exc:
        raise ReferenceMinimizationValidationRunnerError(
            "runner dependency bytes cannot be measured"
        ) from exc


def _python_hash_probe_sha256() -> str:
    return _sha256(
        {
            "bytes": hash(b"betelgeuze-engine-v2-worker-seed-probe"),
            "string": hash("betelgeuze-engine-v2-worker-seed-probe"),
            "tuple": hash(("betelgeuze-engine-v2-worker-seed-probe", 17)),
        }
    )


def _require_worker_seed(value: object, *, name: str, maximum: int) -> int:
    if type(value) is not int or not 0 <= value <= maximum:
        raise ReferenceMinimizationValidationRunnerError(
            f"{name} is outside the frozen range"
        )
    return value


def _configure_deterministic_torch_runtime(application_seed: int | None = None) -> None:
    import torch

    try:
        if application_seed is not None:
            torch.manual_seed(
                _require_worker_seed(
                    application_seed,
                    name="matrix worker application seed",
                    maximum=2**63 - 1,
                )
            )
        torch.set_num_threads(1)
        torch.set_num_interop_threads(1)
        torch.use_deterministic_algorithms(True)
    except RuntimeError as exc:
        raise ReferenceMinimizationValidationRunnerError(
            "minimization runner deterministic single-thread runtime cannot be configured"
        ) from exc


def reference_minimization_validation_checked_out_code_commit_sha() -> str:
    """Resolve HEAD without accepting Git replacement objects."""

    environment = {
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "HOME": "/nonexistent",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": "/usr/bin:/bin",
    }
    try:
        result = subprocess.run(
            [
                "/usr/bin/git",
                "-c",
                "core.fsmonitor=false",
                "-c",
                "core.hooksPath=/dev/null",
                "rev-parse",
                "--verify",
                "HEAD",
            ],
            cwd=Path(__file__).resolve().parents[2],
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ReferenceMinimizationValidationRunnerError(
            "checked-out code commit is unavailable"
        ) from exc
    if result.returncode != 0:
        raise ReferenceMinimizationValidationRunnerError(
            "checked-out code commit is unavailable"
        )
    return _require_commit(result.stdout.decode("ascii").strip(), name="checkout")


def _require_clean_checked_out_code_commit(expected_commit_sha: str) -> None:
    expected = _require_commit(expected_commit_sha, name="expected checkout")
    if not hmac.compare_digest(
        reference_minimization_validation_checked_out_code_commit_sha(), expected
    ):
        raise ReferenceMinimizationValidationRunnerError(
            "checked-out code commit is cross-wired"
        )
    environment = {
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "HOME": "/nonexistent",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": "/usr/bin:/bin",
    }
    result = subprocess.run(
        [
            "/usr/bin/git",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "core.hooksPath=/dev/null",
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ],
        cwd=Path(__file__).resolve().parents[2],
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=10,
        check=False,
    )
    if result.returncode or result.stdout:
        raise ReferenceMinimizationValidationRunnerError(
            "validation checkout is not clean"
        )
    replacements = subprocess.run(
        [
            "/usr/bin/git",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "core.hooksPath=/dev/null",
            "replace",
            "--list",
        ],
        cwd=Path(__file__).resolve().parents[2],
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=10,
        check=False,
    )
    if replacements.returncode or replacements.stdout:
        raise ReferenceMinimizationValidationRunnerError(
            "validation checkout has replacement refs"
        )


def _closed_claim_policy() -> dict[str, bool]:
    return {
        "validation_receipt": False,
        "minimization_validated": False,
        "scientifically_validated": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
    }


def _exact_nonnegative_int(value: object, *, name: str) -> int:
    if type(value) is not int or value < 0:
        raise ReferenceMinimizationValidationRunnerError(
            f"{name} must be an exact nonnegative integer"
        )
    return value


def _coordinate_hex_rows(
    value: object,
    *,
    atom_count: int,
    name: str,
) -> tuple[tuple[str, str, str], ...]:
    if not isinstance(value, (list, tuple)) or len(value) != atom_count:
        raise ReferenceMinimizationValidationRunnerError(
            f"{name} must exactly cover every atom"
        )
    normalized: list[tuple[str, str, str]] = []
    for row in value:
        if not isinstance(row, (list, tuple)) or len(row) != 3:
            raise ReferenceMinimizationValidationRunnerError(
                f"{name} must have [atom,3] shape"
            )
        values: list[str] = []
        for item in row:
            if not isinstance(item, str):
                raise ReferenceMinimizationValidationRunnerError(
                    f"{name} must use canonical binary64 hex"
                )
            try:
                number = float.fromhex(item)
            except ValueError as exc:
                raise ReferenceMinimizationValidationRunnerError(
                    f"{name} must use canonical binary64 hex"
                ) from exc
            if not math.isfinite(number) or number.hex() != item:
                raise ReferenceMinimizationValidationRunnerError(
                    f"{name} must use canonical finite binary64 hex"
                )
            values.append(item)
        normalized.append((values[0], values[1], values[2]))
    return tuple(normalized)


def _coordinate_f64le_sha256(
    rows: Sequence[Sequence[str]],
) -> str:
    raw = bytearray()
    for row in rows:
        for value in row:
            raw.extend(struct.pack("<d", float.fromhex(value)))
    return hashlib.sha256(raw).hexdigest()


def _finite_trace_energy(value: object, *, name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReferenceMinimizationValidationRunnerError(
            f"{name} must be a finite binary64 value or null"
        )
    result = float(value)
    if not math.isfinite(result):
        raise ReferenceMinimizationValidationRunnerError(
            f"{name} must be a finite binary64 value or null"
        )
    return result


@dataclass(frozen=True, slots=True)
class ReferenceMinimizationValidationCoordinateTraceStep:
    case_id: str
    trace_source: str
    trace_ordinal: int
    evaluation_index: int
    iteration: int
    trial: int
    outcome: str
    raw_coordinates_angstrom_hex: tuple[tuple[str, str, str], ...]
    raw_coordinates_f64le_sha256: str
    evaluated_coordinates_angstrom_hex: tuple[tuple[str, str, str], ...]
    evaluated_coordinates_f64le_sha256: str
    energy_kcal_per_mol: float | None
    step_identity_sha256: str

    def _projection(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "trace_source": self.trace_source,
            "trace_ordinal": self.trace_ordinal,
            "evaluation_index": self.evaluation_index,
            "iteration": self.iteration,
            "trial": self.trial,
            "outcome": self.outcome,
            "raw_coordinates_angstrom_hex": [
                list(row) for row in self.raw_coordinates_angstrom_hex
            ],
            "raw_coordinates_f64le_sha256": self.raw_coordinates_f64le_sha256,
            "evaluated_coordinates_angstrom_hex": [
                list(row) for row in self.evaluated_coordinates_angstrom_hex
            ],
            "evaluated_coordinates_f64le_sha256": (
                self.evaluated_coordinates_f64le_sha256
            ),
            "energy_kcal_per_mol": self.energy_kcal_per_mol,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._projection(), "step_identity_sha256": self.step_identity_sha256}

    @classmethod
    def create(
        cls,
        *,
        case_id: str,
        trace_source: str,
        trace_ordinal: int,
        evaluation_index: int,
        iteration: int,
        trial: int,
        outcome: str,
        raw_coordinates_angstrom_hex: object,
        evaluated_coordinates_angstrom_hex: object,
        energy_kcal_per_mol: object,
        atom_count: int,
    ) -> "ReferenceMinimizationValidationCoordinateTraceStep":
        raw_rows = _coordinate_hex_rows(
            raw_coordinates_angstrom_hex,
            atom_count=atom_count,
            name="raw trace coordinates",
        )
        evaluated_rows = _coordinate_hex_rows(
            evaluated_coordinates_angstrom_hex,
            atom_count=atom_count,
            name="evaluated trace coordinates",
        )
        values = {
            "case_id": case_id,
            "trace_source": trace_source,
            "trace_ordinal": _exact_nonnegative_int(
                trace_ordinal, name="trace ordinal"
            ),
            "evaluation_index": _exact_nonnegative_int(
                evaluation_index, name="trace evaluation index"
            ),
            "iteration": _exact_nonnegative_int(iteration, name="trace iteration"),
            "trial": _exact_nonnegative_int(trial, name="trace trial"),
            "outcome": outcome,
            "raw_coordinates_angstrom_hex": raw_rows,
            "raw_coordinates_f64le_sha256": _coordinate_f64le_sha256(raw_rows),
            "evaluated_coordinates_angstrom_hex": evaluated_rows,
            "evaluated_coordinates_f64le_sha256": _coordinate_f64le_sha256(
                evaluated_rows
            ),
            "energy_kcal_per_mol": _finite_trace_energy(
                energy_kcal_per_mol, name="trace energy"
            ),
        }
        projection = {
            **values,
            "raw_coordinates_angstrom_hex": [list(row) for row in raw_rows],
            "evaluated_coordinates_angstrom_hex": [list(row) for row in evaluated_rows],
        }
        return cls(**values, step_identity_sha256=_sha256(projection))

    @classmethod
    def from_dict(
        cls,
        value: object,
        *,
        atom_count: int,
    ) -> "ReferenceMinimizationValidationCoordinateTraceStep":
        if not isinstance(value, Mapping):
            raise ReferenceMinimizationValidationRunnerError(
                "coordinate trace step must be a mapping"
            )
        required = {
            "case_id",
            "trace_source",
            "trace_ordinal",
            "evaluation_index",
            "iteration",
            "trial",
            "outcome",
            "raw_coordinates_angstrom_hex",
            "raw_coordinates_f64le_sha256",
            "evaluated_coordinates_angstrom_hex",
            "evaluated_coordinates_f64le_sha256",
            "energy_kcal_per_mol",
            "step_identity_sha256",
        }
        if set(value) != required:
            raise ReferenceMinimizationValidationRunnerError(
                "coordinate trace step fields are invalid"
            )
        row = cls.create(
            case_id=str(value["case_id"]),
            trace_source=str(value["trace_source"]),
            trace_ordinal=value["trace_ordinal"],
            evaluation_index=value["evaluation_index"],
            iteration=value["iteration"],
            trial=value["trial"],
            outcome=str(value["outcome"]),
            raw_coordinates_angstrom_hex=value["raw_coordinates_angstrom_hex"],
            evaluated_coordinates_angstrom_hex=value[
                "evaluated_coordinates_angstrom_hex"
            ],
            energy_kcal_per_mol=value["energy_kcal_per_mol"],
            atom_count=atom_count,
        )
        if row.to_dict() != dict(value):
            raise ReferenceMinimizationValidationRunnerError(
                "coordinate trace step digest or canonical form is invalid"
            )
        return row


@dataclass(frozen=True, slots=True)
class ReferenceMinimizationValidationCoordinateTrace:
    case_id: str
    trace_source: str
    trace_state: str
    atom_count: int
    accepted_iteration_count: int
    rejected_step_count: int
    energy_force_evaluation_count: int
    accepted_energy_ledger: tuple[float, ...]
    steps: tuple[ReferenceMinimizationValidationCoordinateTraceStep, ...]
    trace_sha256: str
    coordinate_dtype: str = "float64"
    coordinate_unit: str = "angstrom"
    coordinate_encoding: str = REFERENCE_MINIMIZATION_VALIDATION_COORDINATE_ENCODING
    coordinate_digest_algorithm: str = (
        REFERENCE_MINIMIZATION_VALIDATION_COORDINATE_DIGEST_ALGORITHM
    )

    def _projection(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "trace_source": self.trace_source,
            "trace_state": self.trace_state,
            "coordinate_dtype": self.coordinate_dtype,
            "coordinate_unit": self.coordinate_unit,
            "coordinate_encoding": self.coordinate_encoding,
            "coordinate_digest_algorithm": self.coordinate_digest_algorithm,
            "atom_count": self.atom_count,
            "accepted_iteration_count": self.accepted_iteration_count,
            "rejected_step_count": self.rejected_step_count,
            "energy_force_evaluation_count": self.energy_force_evaluation_count,
            "trace_length": len(self.steps),
            "accepted_energy_ledger": list(self.accepted_energy_ledger),
            "steps": [row.to_dict() for row in self.steps],
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._projection(), "trace_sha256": self.trace_sha256}

    @classmethod
    def create(
        cls,
        *,
        case_id: str,
        trace_source: str,
        trace_state: str,
        atom_count: int,
        accepted_iteration_count: int,
        rejected_step_count: int,
        energy_force_evaluation_count: int,
        accepted_energy_ledger: Sequence[object],
        steps: Sequence[ReferenceMinimizationValidationCoordinateTraceStep],
    ) -> "ReferenceMinimizationValidationCoordinateTrace":
        if trace_source not in REFERENCE_MINIMIZATION_VALIDATION_TRACE_SOURCES:
            raise ReferenceMinimizationValidationRunnerError(
                "coordinate trace source is invalid"
            )
        if trace_state not in REFERENCE_MINIMIZATION_VALIDATION_TRACE_STATES:
            raise ReferenceMinimizationValidationRunnerError(
                "coordinate trace state is invalid"
            )
        atoms = _exact_nonnegative_int(atom_count, name="trace atom count")
        if atoms < 1:
            raise ReferenceMinimizationValidationRunnerError(
                "coordinate trace atom count must be positive"
            )
        accepted = _exact_nonnegative_int(
            accepted_iteration_count, name="trace accepted iteration count"
        )
        rejected = _exact_nonnegative_int(
            rejected_step_count, name="trace rejected step count"
        )
        evaluations = _exact_nonnegative_int(
            energy_force_evaluation_count, name="trace evaluation count"
        )
        ledger = tuple(
            _finite_trace_energy(value, name="accepted trace energy")
            for value in accepted_energy_ledger
        )
        if any(value is None for value in ledger):
            raise ReferenceMinimizationValidationRunnerError(
                "accepted trace energy ledger cannot contain null"
            )
        normalized_steps = tuple(steps)
        if (
            len(normalized_steps) != evaluations
            or [row.trace_ordinal for row in normalized_steps]
            != list(range(1, evaluations + 1))
            or [row.evaluation_index for row in normalized_steps]
            != list(range(1, evaluations + 1))
        ):
            raise ReferenceMinimizationValidationRunnerError(
                "coordinate trace length or evaluation sequence is invalid"
            )
        if any(
            row.case_id != case_id
            or row.trace_source != trace_source
            or len(row.raw_coordinates_angstrom_hex) != atoms
            or len(row.evaluated_coordinates_angstrom_hex) != atoms
            for row in normalized_steps
        ):
            raise ReferenceMinimizationValidationRunnerError(
                "coordinate trace step is cross-wired"
            )
        if normalized_steps:
            if trace_state != "evaluated":
                raise ReferenceMinimizationValidationRunnerError(
                    "non-empty coordinate trace must be evaluated"
                )
            if (
                normalized_steps[0].outcome != "initial"
                or normalized_steps[0].iteration != 0
                or normalized_steps[0].trial != 0
            ):
                raise ReferenceMinimizationValidationRunnerError(
                    "coordinate trace must begin with the initial evaluation"
                )
            expected_iteration = 1
            expected_trial = 0
            for row in normalized_steps[1:]:
                if row.iteration != expected_iteration or row.trial != expected_trial:
                    raise ReferenceMinimizationValidationRunnerError(
                        "coordinate trace iteration or trial sequence is invalid"
                    )
                if row.outcome == "accepted":
                    expected_iteration += 1
                    expected_trial = 0
                elif row.outcome.startswith("rejected_"):
                    expected_trial += 1
                else:
                    raise ReferenceMinimizationValidationRunnerError(
                        "coordinate trace outcome is invalid"
                    )
        elif trace_state == "evaluated":
            raise ReferenceMinimizationValidationRunnerError(
                "evaluated coordinate trace cannot be empty"
            )
        accepted_steps = tuple(
            row for row in normalized_steps if row.outcome in {"initial", "accepted"}
        )
        rejected_steps = tuple(
            row for row in normalized_steps if row.outcome.startswith("rejected_")
        )
        if len(accepted_steps) != accepted + (1 if normalized_steps else 0):
            raise ReferenceMinimizationValidationRunnerError(
                "coordinate trace accepted count is invalid"
            )
        if len(rejected_steps) != rejected:
            raise ReferenceMinimizationValidationRunnerError(
                "coordinate trace rejected count is invalid"
            )
        accepted_step_energies = tuple(
            row.energy_kcal_per_mol for row in accepted_steps
        )
        if accepted_step_energies != ledger:
            raise ReferenceMinimizationValidationRunnerError(
                "coordinate trace and accepted energy ledger disagree"
            )
        values = {
            "case_id": case_id,
            "trace_source": trace_source,
            "trace_state": trace_state,
            "atom_count": atoms,
            "accepted_iteration_count": accepted,
            "rejected_step_count": rejected,
            "energy_force_evaluation_count": evaluations,
            "accepted_energy_ledger": tuple(float(value) for value in ledger),
            "steps": normalized_steps,
        }
        provisional = cls(**values, trace_sha256="0" * 64)
        return cls(**values, trace_sha256=_sha256(provisional._projection()))

    @classmethod
    def from_dict(
        cls,
        value: object,
    ) -> "ReferenceMinimizationValidationCoordinateTrace":
        if not isinstance(value, Mapping):
            raise ReferenceMinimizationValidationRunnerError(
                "coordinate trace must be a mapping"
            )
        required = {
            "case_id",
            "trace_source",
            "trace_state",
            "coordinate_dtype",
            "coordinate_unit",
            "coordinate_encoding",
            "coordinate_digest_algorithm",
            "atom_count",
            "accepted_iteration_count",
            "rejected_step_count",
            "energy_force_evaluation_count",
            "trace_length",
            "accepted_energy_ledger",
            "steps",
            "trace_sha256",
        }
        if set(value) != required:
            raise ReferenceMinimizationValidationRunnerError(
                "coordinate trace fields are invalid"
            )
        atom_count = _exact_nonnegative_int(
            value["atom_count"], name="trace atom count"
        )
        steps_payload = value["steps"]
        if not isinstance(steps_payload, list):
            raise ReferenceMinimizationValidationRunnerError(
                "coordinate trace steps must be a list"
            )
        steps = tuple(
            ReferenceMinimizationValidationCoordinateTraceStep.from_dict(
                row, atom_count=atom_count
            )
            for row in steps_payload
        )
        ledger = value["accepted_energy_ledger"]
        if not isinstance(ledger, list):
            raise ReferenceMinimizationValidationRunnerError(
                "coordinate trace energy ledger must be a list"
            )
        trace = cls.create(
            case_id=str(value["case_id"]),
            trace_source=str(value["trace_source"]),
            trace_state=str(value["trace_state"]),
            atom_count=atom_count,
            accepted_iteration_count=value["accepted_iteration_count"],
            rejected_step_count=value["rejected_step_count"],
            energy_force_evaluation_count=value["energy_force_evaluation_count"],
            accepted_energy_ledger=ledger,
            steps=steps,
        )
        if trace.to_dict() != dict(value):
            raise ReferenceMinimizationValidationRunnerError(
                "coordinate trace digest, length, or canonical form is invalid"
            )
        return trace


def _contract_projection() -> dict[str, Any]:
    protocol = cpu_minimization_validation_protocol_document()
    return {
        "schema_id": REFERENCE_MINIMIZATION_VALIDATION_RUNNER_CONTRACT_SCHEMA_ID,
        "contract_id": REFERENCE_MINIMIZATION_VALIDATION_RUNNER_CONTRACT_ID,
        "contract_version": REFERENCE_MINIMIZATION_VALIDATION_RUNNER_CONTRACT_VERSION,
        "frozen_at_utc": REFERENCE_MINIMIZATION_VALIDATION_RUNNER_CONTRACT_FROZEN_AT_UTC,
        "protocol_sha256": FROZEN_CPU_MINIMIZATION_VALIDATION_PROTOCOL_SHA256,
        "run_start_contract_sha256": (
            FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RUN_START_CONTRACT_SHA256
        ),
        "bounds": {
            "case_count": REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_CASES,
            "maximum_wall_seconds": REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_WALL_SECONDS,
            "skipped_cases_allowed": False,
            "partial_results_allowed": False,
        },
        "case_order": [row["case_id"] for row in protocol["case_manifest"]["cases"]],
        "trust_boundary": {
            "stdlib_only_trusted_outer_bootstrap_required": True,
            "seeded_controlled_inner_exec_required": True,
            "python_hash_seed_applied_at_interpreter_initialization": True,
            "source_only_imports_required": True,
            "caller_supplied_trust_keys_allowed": False,
            "external_root_owned_mode_0600_trust_store_required": True,
            "clean_git_head_measured": True,
            "git_replacement_refs_rejected": True,
            "bootstrap_and_runner_source_identity_measured": True,
            "dependency_roots_root_owned_read_only": True,
            "dependency_payload_bytes_remeasured_before_evaluation": True,
            "required_dependency_artifact_ids": list(
                REFERENCE_MINIMIZATION_VALIDATION_REQUIRED_DEPENDENCY_ARTIFACT_IDS
            ),
        },
        "worker": {
            "fresh_fixed_subprocess": True,
            "multiprocessing_spawn_used": False,
            "parent_supervised": True,
            "native_stall_hard_kill": True,
            "failure_complete_timeout_observation": True,
            "failure_complete_start_error_observation": True,
            "failure_complete_communication_error_observation": True,
            "canonical_standard_stream_framing_required": True,
            "automatic_site_initialization_allowed": False,
            "fixed_source_only_python_flags_required": True,
            "child_source_only_runtime_reverified": True,
            "child_clean_commit_and_source_reverified": True,
            "child_dependency_roots_and_bytes_reverified": True,
            "child_deterministic_single_thread_runtime_required": True,
            "child_environment_derived_from_verified_receipt": True,
            "child_python_hash_seed_uint32_bound_to_receipt": True,
            "child_application_seed_bound_to_receipt": True,
            "parent_child_python_hash_probe_equality_required": True,
            "child_exact_argv_cwd_and_environment_reverified": True,
            "child_preflight_failure_rows_retained": True,
        },
        "entrypoint": {
            "logical_argv": list(REFERENCE_MINIMIZATION_VALIDATION_LOGICAL_RUNNER_ARGV),
            "trusted_outer_launcher_argv": list(
                REFERENCE_MINIMIZATION_VALIDATION_TRUSTED_OUTER_LAUNCHER_ARGV
            ),
            "direct_stdlib_only_bootstrap_required": True,
            "canonical_request_bounded_before_package_import": True,
            "operator_signature_verified_before_package_import": True,
            "expected_commit_and_source_verified_before_package_import": True,
            "trusted_outer_launcher_flags": [
                "-I",
                "-S",
                "-B",
                "-X",
                "pycache_prefix=/dev/null",
            ],
            "seeded_controlled_inner_flags": [
                "-S",
                "-B",
                "-X",
                "pycache_prefix=/dev/null",
                "-c",
            ],
            "environment_import_path_overrides_honored": False,
            "automatic_site_initialization_allowed": False,
            "clean_source_checkout_with_git_metadata_required": True,
            "reservation_and_artifact_roots_outside_checkout_required": True,
            "canonical_standard_input_request_schema_id": (
                REFERENCE_MINIMIZATION_VALIDATION_RUNNER_REQUEST_SCHEMA_ID
            ),
            "maximum_request_bytes": (
                REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_REQUEST_BYTES
            ),
            "secret_bearing_argv_allowed": False,
            "trust_keys_in_standard_input_allowed": False,
            "fixed_root_owned_mode_0600_trust_store_required": True,
            "trust_store_path": REFERENCE_MINIMIZATION_VALIDATION_TRUST_STORE_PATH,
            "repository_bundles_trust_store_or_keys": False,
            "trust_keys_retained_or_echoed": False,
            "environment_receipt_runner_and_result_writer_reachable": True,
            "result_receipt_finalized_in_same_verified_process": True,
            "response_contains_hashes_and_closed_claim_state_only": True,
        },
        "observation": {
            "in_memory_only": True,
            "failure_inclusive": True,
            "failed_metrics_and_cases_retained": True,
            "operational_and_independent_coordinate_traces_retained": True,
            "raw_and_evaluated_coordinates_retained_for_every_evaluation": True,
            "canonical_empty_trace_distinguishes_pre_evaluation_failure": True,
            "coordinate_trace_step_identity_includes_case_and_source": True,
            "coordinate_trace_length_order_counts_and_energy_ledger_verified": True,
            "coordinate_trace_sha256_required": True,
            "result_receipt_written": False,
        },
        "start_marker": {
            "schema_id": REFERENCE_MINIMIZATION_VALIDATION_RUNNER_START_SCHEMA_ID,
            "one_time_per_authorization_nonce": True,
            "mode": "0600",
            "exclusive_create": True,
            "deleted_by_runner": False,
        },
        "claim_policy": _closed_claim_policy(),
    }


def reference_minimization_validation_runner_contract_document() -> dict[str, Any]:
    document = _contract_projection()
    document["contract_sha256"] = _sha256(document)
    if (
        FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RUNNER_CONTRACT_SHA256
        and document["contract_sha256"]
        != FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RUNNER_CONTRACT_SHA256
    ):
        raise ReferenceMinimizationValidationRunnerError(
            "frozen minimization runner contract SHA-256 drifted"
        )
    return document


def require_reference_minimization_validation_runner_contract_document(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ReferenceMinimizationValidationRunnerError(
            "runner contract must be a mapping"
        )
    observed = dict(value)
    expected = reference_minimization_validation_runner_contract_document()
    if not hmac.compare_digest(_canonical_bytes(observed), _canonical_bytes(expected)):
        raise ReferenceMinimizationValidationRunnerError(
            "runner contract does not match the frozen record"
        )
    return observed


@dataclass(frozen=True, slots=True)
class ReferenceMinimizationValidationCaseObservation:
    ordinal: int
    case_id: str
    case_input_sha256: str
    runtime_input_sha256: str
    independent_oracle_input_sha256: str
    expected_outcome: str
    observed_status: str
    expected_error_code: str | None
    observed_error_code: str | None
    operational_result_sha256: str | None
    independent_result_sha256: str | None
    accepted_iteration_count: int
    rejected_step_count: int
    energy_force_evaluation_count: int
    accepted_energy_ledger: tuple[float, ...]
    coordinate_traces: tuple[ReferenceMinimizationValidationCoordinateTrace, ...]
    metric_values: tuple[tuple[str, float], ...]
    case_passed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "accepted_energy_ledger": list(self.accepted_energy_ledger),
            "coordinate_traces": [row.to_dict() for row in self.coordinate_traces],
            "metric_values": [
                {"metric_id": key, "value": value} for key, value in self.metric_values
            ],
        }


@dataclass(frozen=True, slots=True)
class ReferenceMinimizationValidationRunObservation:
    authorization_nonce_sha256: str
    environment_receipt_sha256: str
    environment_fingerprint_sha256: str
    code_commit_sha: str
    runner_source_sha256: str
    dependency_artifact_sha256_rows: tuple[tuple[str, str], ...]
    command_argv: tuple[str, ...]
    seed: int
    started_at_utc: str
    completed_at_utc: str
    runner_start_record_sha256: str
    case_results: tuple[ReferenceMinimizationValidationCaseObservation, ...]
    all_cases_observed: bool
    all_cases_passed: bool
    claim_policy: Mapping[str, bool]
    schema_id: str = REFERENCE_MINIMIZATION_VALIDATION_RUN_OBSERVATION_SCHEMA_ID

    @property
    def observation_sha256(self) -> str:
        return _sha256(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "protocol_sha256": FROZEN_CPU_MINIMIZATION_VALIDATION_PROTOCOL_SHA256,
            "runner_contract_sha256": (
                FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RUNNER_CONTRACT_SHA256
            ),
            "authorization_nonce_sha256": self.authorization_nonce_sha256,
            "environment_receipt_sha256": self.environment_receipt_sha256,
            "environment_fingerprint_sha256": self.environment_fingerprint_sha256,
            "code_commit_sha": self.code_commit_sha,
            "runner_source_sha256": self.runner_source_sha256,
            "dependency_artifact_sha256_rows": [
                {"artifact_id": key, "sha256": value}
                for key, value in self.dependency_artifact_sha256_rows
            ],
            "command_argv": list(self.command_argv),
            "seed": self.seed,
            "started_at_utc": self.started_at_utc,
            "completed_at_utc": self.completed_at_utc,
            "runner_start_record_sha256": self.runner_start_record_sha256,
            "case_results": [row.to_dict() for row in self.case_results],
            "coverage_summary": {
                "expected_case_count": 14,
                "observed_case_count": len(self.case_results),
                "all_cases_observed": self.all_cases_observed,
                "all_cases_passed": self.all_cases_passed,
                "failed_case_count": sum(
                    not row.case_passed for row in self.case_results
                ),
                "failure_rows_retained": True,
            },
            "in_memory_only": True,
            "result_receipt_written": False,
            "claim_policy": dict(self.claim_policy),
        }


def _coordinates(result: object) -> tuple[tuple[float, float, float], ...]:
    rows = result.system.coordinates[0].tolist()  # type: ignore[attr-defined]
    return tuple(tuple(float(value) for value in row) for row in rows)


def _maximum_coordinate_error(
    first: Sequence[Sequence[float]], second: Sequence[Sequence[float]]
) -> float:
    return max(
        (
            abs(float(left) - float(right))
            for a, b in zip(first, second, strict=True)
            for left, right in zip(a, b, strict=True)
        ),
        default=0.0,
    )


def _operational_result_sha256(result: object) -> str:
    return _sha256(result.to_dict())  # type: ignore[attr-defined]


def _run_operational(
    case: Any, *, pause: int | None = None, checkpoint: Any = None
) -> Any:
    if case.v2_parameters is None:
        return minimize_reference_force_field(
            case.system,
            case.base_parameters,
            case.minimization_config,
            checkpoint=checkpoint,
            pause_after_accepted_iterations=pause,
        )
    if case.constrained_config is None:
        raise ReferenceMinimizationValidationRunnerError(
            "materialized v2 case is missing constrained config"
        )
    return minimize_reference_force_field_v2_constrained(
        case.system,
        case.v2_parameters,
        case.constrained_config,
        solvation_parameters=case.solvation_parameters,
        checkpoint=checkpoint,
        pause_after_accepted_iterations=pause,
    )


def _accepted_energy_ledger(result: object) -> tuple[float, ...]:
    rows = []
    for observation in result.observations:  # type: ignore[attr-defined]
        if observation.outcome in {"initial", "accepted"}:
            energy = observation.energy_kcal_per_mol
            if energy is not None:
                rows.append(float(energy))
    return tuple(rows)


def _coordinate_hex_from_independent(
    rows: Sequence[Sequence[float]],
) -> tuple[tuple[str, str, str], ...]:
    return tuple(
        tuple(float(value).hex() for value in row)  # type: ignore[misc]
        for row in rows
    )


def _operational_coordinate_trace(
    case: Any,
    result: Any,
) -> ReferenceMinimizationValidationCoordinateTrace:
    steps: list[ReferenceMinimizationValidationCoordinateTraceStep] = []
    for ordinal, observation in enumerate(result.observations, start=1):
        if hasattr(observation, "raw_coordinates_angstrom_hex"):
            raw_rows = observation.raw_coordinates_angstrom_hex
            evaluated_rows = observation.projected_coordinates_angstrom_hex
        else:
            raw_rows = observation.coordinates_angstrom_hex
            evaluated_rows = observation.coordinates_angstrom_hex
        steps.append(
            ReferenceMinimizationValidationCoordinateTraceStep.create(
                case_id=case.case_id,
                trace_source="operational",
                trace_ordinal=ordinal,
                evaluation_index=observation.evaluation_index,
                iteration=observation.iteration,
                trial=observation.trial,
                outcome=observation.outcome,
                raw_coordinates_angstrom_hex=raw_rows,
                evaluated_coordinates_angstrom_hex=evaluated_rows,
                energy_kcal_per_mol=observation.energy_kcal_per_mol,
                atom_count=case.system.atom_count,
            )
        )
    return ReferenceMinimizationValidationCoordinateTrace.create(
        case_id=case.case_id,
        trace_source="operational",
        trace_state="evaluated",
        atom_count=case.system.atom_count,
        accepted_iteration_count=result.accepted_iterations,
        rejected_step_count=result.rejected_evaluations,
        energy_force_evaluation_count=result.evaluation_count,
        accepted_energy_ledger=_accepted_energy_ledger(result),
        steps=steps,
    )


def _independent_coordinate_trace(
    case: Any,
    result: Any,
) -> ReferenceMinimizationValidationCoordinateTrace:
    steps = tuple(
        ReferenceMinimizationValidationCoordinateTraceStep.create(
            case_id=case.case_id,
            trace_source="independent_oracle",
            trace_ordinal=ordinal,
            evaluation_index=row.evaluation_index,
            iteration=row.iteration,
            trial=row.trial,
            outcome=row.outcome,
            raw_coordinates_angstrom_hex=_coordinate_hex_from_independent(
                row.raw_coordinates_angstrom
            ),
            evaluated_coordinates_angstrom_hex=_coordinate_hex_from_independent(
                row.evaluated_coordinates_angstrom
            ),
            energy_kcal_per_mol=row.energy_kcal_per_mol,
            atom_count=case.system.atom_count,
        )
        for ordinal, row in enumerate(result.coordinate_trace, start=1)
    )
    return ReferenceMinimizationValidationCoordinateTrace.create(
        case_id=case.case_id,
        trace_source="independent_oracle",
        trace_state=("evaluated" if steps else "not_evaluated_expected_fail_closed"),
        atom_count=case.system.atom_count,
        accepted_iteration_count=result.accepted_iterations,
        rejected_step_count=result.rejected_evaluations,
        energy_force_evaluation_count=result.evaluation_count,
        accepted_energy_ledger=result.accepted_energy_trace_kcal_per_mol,
        steps=steps,
    )


def _empty_coordinate_trace(
    *,
    case_id: str,
    trace_source: str,
    atom_count: int,
    expected_fail_closed: bool,
) -> ReferenceMinimizationValidationCoordinateTrace:
    return ReferenceMinimizationValidationCoordinateTrace.create(
        case_id=case_id,
        trace_source=trace_source,
        trace_state=(
            "not_evaluated_expected_fail_closed"
            if expected_fail_closed
            else "not_evaluated_unexpected_failure"
        ),
        atom_count=atom_count,
        accepted_iteration_count=0,
        rejected_step_count=0,
        energy_force_evaluation_count=0,
        accepted_energy_ledger=(),
        steps=(),
    )


def _empty_coordinate_traces_for_protocol_row(
    protocol_row: Mapping[str, Any],
    *,
    expected_fail_closed: bool,
) -> tuple[ReferenceMinimizationValidationCoordinateTrace, ...]:
    atom_count = cpu_minimization_validation_case_atom_count(protocol_row["case_id"])
    return tuple(
        _empty_coordinate_trace(
            case_id=protocol_row["case_id"],
            trace_source=source,
            atom_count=atom_count,
            expected_fail_closed=expected_fail_closed,
        )
        for source in REFERENCE_MINIMIZATION_VALIDATION_TRACE_SOURCES
    )


def _threshold_pass(operator: str, value: float, threshold: float) -> bool:
    if operator == "equal":
        return value == threshold
    if operator == "less_than_or_equal":
        return value <= threshold
    if operator == "greater_than_or_equal":
        return value >= threshold
    raise ReferenceMinimizationValidationRunnerError("unknown metric threshold")


def _evaluate_case(
    ordinal: int, protocol_row: Mapping[str, Any]
) -> ReferenceMinimizationValidationCaseObservation:
    case = materialize_frozen_cpu_minimization_validation_case(protocol_row["case_id"])
    independent_source = replace(
        case.independent_oracle_input, pause_after_accepted_iterations=None
    )
    independent = evaluate_independent_minimization_oracle(
        case.independent_oracle_input
        if case.expected_outcome == "fail_closed"
        else independent_source
    )
    independent_trace = _independent_coordinate_trace(case, independent)
    if case.expected_outcome == "fail_closed":
        passed = (
            independent.status == "fail_closed"
            and independent.failure_code == case.expected_error_code
        )
        return ReferenceMinimizationValidationCaseObservation(
            ordinal=ordinal,
            case_id=case.case_id,
            case_input_sha256=case.case_input_sha256,
            runtime_input_sha256=_sha256(case.to_dict()),
            independent_oracle_input_sha256=case.independent_oracle_input.input_sha256,
            expected_outcome=case.expected_outcome,
            observed_status=independent.status,
            expected_error_code=case.expected_error_code,
            observed_error_code=independent.failure_code,
            operational_result_sha256=None,
            independent_result_sha256=independent.result_sha256,
            accepted_iteration_count=independent.accepted_iterations,
            rejected_step_count=independent.rejected_evaluations,
            energy_force_evaluation_count=independent.evaluation_count,
            accepted_energy_ledger=independent.accepted_energy_trace_kcal_per_mol,
            coordinate_traces=(
                _empty_coordinate_trace(
                    case_id=case.case_id,
                    trace_source="operational",
                    atom_count=case.system.atom_count,
                    expected_fail_closed=True,
                ),
                independent_trace,
            ),
            metric_values=(),
            case_passed=passed,
        )

    operational = _run_operational(case)
    operational_trace = _operational_coordinate_trace(case, operational)
    checkpoint_equal = 1.0
    if case.pause_after_accepted_iterations is not None:
        paused = _run_operational(case, pause=case.pause_after_accepted_iterations)
        resumed = _run_operational(case, checkpoint=paused.checkpoint)
        checkpoint_equal = float(
            _operational_result_sha256(resumed)
            == _operational_result_sha256(operational)
            and resumed.checkpoint.checkpoint_sha256
            == operational.checkpoint.checkpoint_sha256
        )
    coordinates = _coordinates(operational)
    if independent.final_coordinates_angstrom is None:
        raise ReferenceMinimizationValidationRunnerError(
            "passing independent result omitted coordinates"
        )
    ledger = _accepted_energy_ledger(operational)
    monotonic = float(
        all(next_value <= value for value, next_value in zip(ledger, ledger[1:]))
    )
    if independent.final_max_force_kcal_per_mol_angstrom is None:
        raise ReferenceMinimizationValidationRunnerError(
            "passing independent result omitted final force"
        )
    if hasattr(operational, "final_max_force_kcal_per_mol_angstrom"):
        operational_force = float(operational.final_max_force_kcal_per_mol_angstrom)
    else:
        operational_force = float(
            operational.final_max_tangent_force_kcal_per_mol_angstrom
        )
    final_force = abs(
        operational_force - independent.final_max_force_kcal_per_mol_angstrom
    )
    tangent_force = final_force
    constraint_residual = float(
        getattr(operational, "final_max_constraint_residual_angstrom", 0.0)
    )
    coordinate_error = _maximum_coordinate_error(
        independent.final_coordinates_angstrom, coordinates
    )
    if independent.final_energy_kcal_per_mol is None:
        raise ReferenceMinimizationValidationRunnerError(
            "passing independent result omitted energy"
        )
    metrics = {
        "accepted_energy_monotonic": monotonic,
        "final_energy_change": float(
            operational.final_energy_kcal_per_mol
            - operational.initial_energy_kcal_per_mol
        ),
        "minimum_required_energy_decrease": float(
            operational.initial_energy_kcal_per_mol
            - operational.final_energy_kcal_per_mol
        ),
        "final_force_max_abs": final_force,
        "final_tangent_force_max_abs": tangent_force,
        "constraint_max_abs_residual": constraint_residual,
        "checkpoint_resume_bitwise_equal": checkpoint_equal,
        "failure_ledger_complete": 1.0,
        "independent_reference_final_coordinate_max_abs_error": coordinate_error,
        "independent_reference_final_energy_abs_error": abs(
            independent.final_energy_kcal_per_mol
            - operational.final_energy_kcal_per_mol
        ),
    }
    protocol_metrics = {
        row["metric_id"]: row
        for row in cpu_minimization_validation_protocol_document()[
            "numerical_protocol"
        ]["metrics"]
    }
    required = tuple(protocol_row["required_metric_ids"])
    passed = (
        operational.status == independent.status
        and operational.failure_code == independent.failure_code
        and all(
            math.isfinite(metrics[metric_id])
            and _threshold_pass(
                protocol_metrics[metric_id]["threshold_operator"],
                metrics[metric_id],
                float(protocol_metrics[metric_id]["threshold_value"]),
            )
            for metric_id in required
        )
    )
    return ReferenceMinimizationValidationCaseObservation(
        ordinal=ordinal,
        case_id=case.case_id,
        case_input_sha256=case.case_input_sha256,
        runtime_input_sha256=_sha256(case.to_dict()),
        independent_oracle_input_sha256=case.independent_oracle_input.input_sha256,
        expected_outcome=case.expected_outcome,
        observed_status=operational.status,
        expected_error_code=None,
        observed_error_code=operational.failure_code,
        operational_result_sha256=_operational_result_sha256(operational),
        independent_result_sha256=independent.result_sha256,
        accepted_iteration_count=operational.accepted_iterations,
        rejected_step_count=operational.rejected_evaluations,
        energy_force_evaluation_count=operational.evaluation_count,
        accepted_energy_ledger=ledger,
        coordinate_traces=(operational_trace, independent_trace),
        metric_values=tuple((metric_id, metrics[metric_id]) for metric_id in required),
        case_passed=passed,
    )


def _run_case_matrix_in_process(
    protocol: Mapping[str, Any] | None = None,
    manifest_cases: Sequence[Mapping[str, Any]] | None = None,
    *,
    deadline: float | None = None,
) -> tuple[ReferenceMinimizationValidationCaseObservation, ...]:
    protocol = (
        cpu_minimization_validation_protocol_document()
        if protocol is None
        else protocol
    )
    rows = protocol["case_manifest"]["cases"]
    if len(rows) != REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_CASES:
        raise ReferenceMinimizationValidationRunnerError(
            "frozen minimization case count drifted"
        )
    observations: list[ReferenceMinimizationValidationCaseObservation] = []
    for ordinal, row in enumerate(rows, start=1):
        if deadline is not None and time.monotonic() >= deadline:
            observations.extend(
                ReferenceMinimizationValidationCaseObservation(
                    ordinal=index,
                    case_id=pending["case_id"],
                    case_input_sha256=pending["input_sha256"],
                    runtime_input_sha256="0" * 64,
                    independent_oracle_input_sha256="0" * 64,
                    expected_outcome=pending["expected_outcome"],
                    observed_status="fail_closed",
                    expected_error_code=pending.get("expected_error_code"),
                    observed_error_code="runner_wall_time_exhausted",
                    operational_result_sha256=None,
                    independent_result_sha256=None,
                    accepted_iteration_count=0,
                    rejected_step_count=0,
                    energy_force_evaluation_count=0,
                    accepted_energy_ledger=(),
                    coordinate_traces=_empty_coordinate_traces_for_protocol_row(
                        pending,
                        expected_fail_closed=False,
                    ),
                    metric_values=(),
                    case_passed=False,
                )
                for index, pending in enumerate(rows[ordinal - 1 :], start=ordinal)
            )
            break
        try:
            observations.append(_evaluate_case(ordinal, row))
        except Exception as exc:  # failure rows must remain in the denominator
            observations.append(
                ReferenceMinimizationValidationCaseObservation(
                    ordinal=ordinal,
                    case_id=row["case_id"],
                    case_input_sha256=row["input_sha256"],
                    runtime_input_sha256="0" * 64,
                    independent_oracle_input_sha256="0" * 64,
                    expected_outcome=row["expected_outcome"],
                    observed_status="fail_closed",
                    expected_error_code=row.get("expected_error_code"),
                    observed_error_code=(
                        "runner_case_exception:" + exc.__class__.__name__.lower()
                    ),
                    operational_result_sha256=None,
                    independent_result_sha256=None,
                    accepted_iteration_count=0,
                    rejected_step_count=0,
                    energy_force_evaluation_count=0,
                    accepted_energy_ledger=(),
                    coordinate_traces=_empty_coordinate_traces_for_protocol_row(
                        row,
                        expected_fail_closed=False,
                    ),
                    metric_values=(),
                    case_passed=False,
                )
            )
    return tuple(observations)


def _failure_complete_matrix(
    error_code: str,
) -> tuple[ReferenceMinimizationValidationCaseObservation, ...]:
    rows = cpu_minimization_validation_protocol_document()["case_manifest"]["cases"]
    return tuple(
        ReferenceMinimizationValidationCaseObservation(
            ordinal=ordinal,
            case_id=row["case_id"],
            case_input_sha256=row["input_sha256"],
            runtime_input_sha256="0" * 64,
            independent_oracle_input_sha256="0" * 64,
            expected_outcome=row["expected_outcome"],
            observed_status="fail_closed",
            expected_error_code=row.get("expected_error_code"),
            observed_error_code=error_code,
            operational_result_sha256=None,
            independent_result_sha256=None,
            accepted_iteration_count=0,
            rejected_step_count=0,
            energy_force_evaluation_count=0,
            accepted_energy_ledger=(),
            coordinate_traces=_empty_coordinate_traces_for_protocol_row(
                row,
                expected_fail_closed=False,
            ),
            metric_values=(),
            case_passed=False,
        )
        for ordinal, row in enumerate(rows, start=1)
    )


def _case_observation_from_payload(
    value: object,
) -> ReferenceMinimizationValidationCaseObservation:
    if not isinstance(value, Mapping):
        raise ReferenceMinimizationValidationRunnerError(
            "worker case observation must be a mapping"
        )
    expected_fields = {
        field.name
        for field in ReferenceMinimizationValidationCaseObservation.__dataclass_fields__.values()
    }
    if set(value) != expected_fields:
        raise ReferenceMinimizationValidationRunnerError(
            "worker case observation has unexpected fields"
        )
    metrics = value["metric_values"]
    if not isinstance(metrics, list) or any(
        not isinstance(row, Mapping) or set(row) != {"metric_id", "value"}
        for row in metrics
    ):
        raise ReferenceMinimizationValidationRunnerError(
            "worker case metrics are invalid"
        )
    ledger = value["accepted_energy_ledger"]
    if not isinstance(ledger, list):
        raise ReferenceMinimizationValidationRunnerError(
            "worker energy ledger is invalid"
        )
    coordinate_traces_payload = value["coordinate_traces"]
    if not isinstance(coordinate_traces_payload, list) or len(
        coordinate_traces_payload
    ) != len(REFERENCE_MINIMIZATION_VALIDATION_TRACE_SOURCES):
        raise ReferenceMinimizationValidationRunnerError(
            "worker coordinate traces are incomplete"
        )
    coordinate_traces = tuple(
        ReferenceMinimizationValidationCoordinateTrace.from_dict(item)
        for item in coordinate_traces_payload
    )
    if tuple(row.trace_source for row in coordinate_traces) != (
        REFERENCE_MINIMIZATION_VALIDATION_TRACE_SOURCES
    ):
        raise ReferenceMinimizationValidationRunnerError(
            "worker coordinate trace sources are reordered"
        )
    try:
        row = ReferenceMinimizationValidationCaseObservation(
            ordinal=int(value["ordinal"]),
            case_id=str(value["case_id"]),
            case_input_sha256=str(value["case_input_sha256"]),
            runtime_input_sha256=str(value["runtime_input_sha256"]),
            independent_oracle_input_sha256=str(
                value["independent_oracle_input_sha256"]
            ),
            expected_outcome=str(value["expected_outcome"]),
            observed_status=str(value["observed_status"]),
            expected_error_code=(
                None
                if value["expected_error_code"] is None
                else str(value["expected_error_code"])
            ),
            observed_error_code=(
                None
                if value["observed_error_code"] is None
                else str(value["observed_error_code"])
            ),
            operational_result_sha256=(
                None
                if value["operational_result_sha256"] is None
                else str(value["operational_result_sha256"])
            ),
            independent_result_sha256=(
                None
                if value["independent_result_sha256"] is None
                else str(value["independent_result_sha256"])
            ),
            accepted_iteration_count=int(value["accepted_iteration_count"]),
            rejected_step_count=int(value["rejected_step_count"]),
            energy_force_evaluation_count=int(value["energy_force_evaluation_count"]),
            accepted_energy_ledger=tuple(float(item) for item in ledger),
            coordinate_traces=coordinate_traces,
            metric_values=tuple(
                (str(item["metric_id"]), float(item["value"])) for item in metrics
            ),
            case_passed=value["case_passed"] is True,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ReferenceMinimizationValidationRunnerError(
            "worker case observation is invalid"
        ) from exc
    if row.to_dict() != dict(value):
        raise ReferenceMinimizationValidationRunnerError(
            "worker case observation is not canonical"
        )
    return row


def require_reference_minimization_validation_run_observation_document(
    value: object,
) -> ReferenceMinimizationValidationRunObservation:
    """Reconstruct and verify one canonical, failure-inclusive observation."""

    if not isinstance(value, Mapping):
        raise ReferenceMinimizationValidationRunnerError(
            "run observation must be a mapping"
        )
    expected_fields = {
        "schema_id",
        "protocol_sha256",
        "runner_contract_sha256",
        "authorization_nonce_sha256",
        "environment_receipt_sha256",
        "environment_fingerprint_sha256",
        "code_commit_sha",
        "runner_source_sha256",
        "dependency_artifact_sha256_rows",
        "command_argv",
        "seed",
        "started_at_utc",
        "completed_at_utc",
        "runner_start_record_sha256",
        "case_results",
        "coverage_summary",
        "in_memory_only",
        "result_receipt_written",
        "claim_policy",
    }
    if set(value) != expected_fields:
        raise ReferenceMinimizationValidationRunnerError(
            "run observation fields are invalid"
        )
    rows = value.get("case_results")
    dependencies = value.get("dependency_artifact_sha256_rows")
    command = value.get("command_argv")
    if (
        not isinstance(rows, list)
        or not isinstance(dependencies, list)
        or any(
            not isinstance(row, Mapping) or set(row) != {"artifact_id", "sha256"}
            for row in dependencies
        )
        or not isinstance(command, list)
        or any(not isinstance(item, str) for item in command)
    ):
        raise ReferenceMinimizationValidationRunnerError(
            "run observation collections are invalid"
        )
    case_results = tuple(_case_observation_from_payload(row) for row in rows)
    dependency_rows = tuple(
        (str(row["artifact_id"]), str(row["sha256"])) for row in dependencies
    )
    if dependency_rows != tuple(sorted(dependency_rows)):
        raise ReferenceMinimizationValidationRunnerError(
            "run observation dependency rows are not canonical"
        )
    try:
        observation = ReferenceMinimizationValidationRunObservation(
            authorization_nonce_sha256=_require_sha256(
                value["authorization_nonce_sha256"], name="authorization nonce"
            ),
            environment_receipt_sha256=_require_sha256(
                value["environment_receipt_sha256"], name="environment receipt"
            ),
            environment_fingerprint_sha256=_require_sha256(
                value["environment_fingerprint_sha256"],
                name="environment fingerprint",
            ),
            code_commit_sha=_require_commit(
                value["code_commit_sha"], name="code commit"
            ),
            runner_source_sha256=_require_sha256(
                value["runner_source_sha256"], name="runner source"
            ),
            dependency_artifact_sha256_rows=dependency_rows,
            command_argv=tuple(command),
            seed=value["seed"],
            started_at_utc=value["started_at_utc"],
            completed_at_utc=value["completed_at_utc"],
            runner_start_record_sha256=_require_sha256(
                value["runner_start_record_sha256"], name="runner-start record"
            ),
            case_results=case_results,
            all_cases_observed=value["coverage_summary"]["all_cases_observed"] is True,
            all_cases_passed=value["coverage_summary"]["all_cases_passed"] is True,
            claim_policy=dict(value["claim_policy"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ReferenceMinimizationValidationRunnerError(
            "run observation is invalid"
        ) from exc
    started = _parse_utc(observation.started_at_utc, name="observation start")
    completed = _parse_utc(observation.completed_at_utc, name="observation completion")
    protocol = cpu_minimization_validation_protocol_document()
    protocol_rows = protocol["case_manifest"]["cases"]
    metric_contract = {
        row["metric_id"]: row for row in protocol["numerical_protocol"]["metrics"]
    }
    for row, expected in zip(case_results, protocol_rows):
        required = tuple(expected["required_metric_ids"])
        observed_metric_ids = tuple(metric_id for metric_id, _ in row.metric_values)
        if (
            row.case_id != expected["case_id"]
            or row.case_input_sha256 != expected["input_sha256"]
            or row.expected_outcome != expected["expected_outcome"]
            or row.expected_error_code != expected.get("expected_error_code")
        ):
            raise ReferenceMinimizationValidationRunnerError(
                "run observation case identity is cross-wired"
            )
        if (
            len(row.coordinate_traces)
            != len(REFERENCE_MINIMIZATION_VALIDATION_TRACE_SOURCES)
            or tuple(trace.trace_source for trace in row.coordinate_traces)
            != REFERENCE_MINIMIZATION_VALIDATION_TRACE_SOURCES
            or any(trace.case_id != row.case_id for trace in row.coordinate_traces)
            or any(
                trace.atom_count
                != cpu_minimization_validation_case_atom_count(row.case_id)
                for trace in row.coordinate_traces
            )
        ):
            raise ReferenceMinimizationValidationRunnerError(
                "run observation coordinate traces are incomplete or cross-wired"
            )
        operational_trace, independent_trace = row.coordinate_traces
        selected_trace = (
            independent_trace
            if row.expected_outcome == "fail_closed"
            else operational_trace
        )
        if (
            selected_trace.accepted_iteration_count != row.accepted_iteration_count
            or selected_trace.rejected_step_count != row.rejected_step_count
            or selected_trace.energy_force_evaluation_count
            != row.energy_force_evaluation_count
            or selected_trace.accepted_energy_ledger != row.accepted_energy_ledger
        ):
            raise ReferenceMinimizationValidationRunnerError(
                "run observation coordinate trace disagrees with retained counts or energy ledger"
            )
        if row.expected_outcome == "fail_closed":
            semantic_pass = (
                row.observed_status == "fail_closed"
                and row.observed_error_code == row.expected_error_code
                and not row.metric_values
                and not operational_trace.steps
                and operational_trace.trace_state
                == "not_evaluated_expected_fail_closed"
                and independent_trace.trace_state
                in {"evaluated", "not_evaluated_expected_fail_closed"}
            )
        else:
            semantic_pass = (
                observed_metric_ids == required
                and operational_trace.trace_state == "evaluated"
                and independent_trace.trace_state == "evaluated"
                and all(
                    math.isfinite(value)
                    and _threshold_pass(
                        metric_contract[metric_id]["threshold_operator"],
                        value,
                        float(metric_contract[metric_id]["threshold_value"]),
                    )
                    for metric_id, value in row.metric_values
                )
            )
        if row.case_passed is not semantic_pass:
            raise ReferenceMinimizationValidationRunnerError(
                "run observation case status contradicts retained metrics"
            )
    if (
        completed < started
        or type(observation.seed) is not int
        or not 0 <= observation.seed <= 2**63 - 1
        or len(case_results) != REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_CASES
        or tuple(row.ordinal for row in case_results) != tuple(range(1, 15))
        or len({row.case_id for row in case_results}) != 14
        or value.get("schema_id")
        != REFERENCE_MINIMIZATION_VALIDATION_RUN_OBSERVATION_SCHEMA_ID
        or value.get("protocol_sha256")
        != FROZEN_CPU_MINIMIZATION_VALIDATION_PROTOCOL_SHA256
        or value.get("runner_contract_sha256")
        != FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RUNNER_CONTRACT_SHA256
        or value.get("in_memory_only") is not True
        or value.get("result_receipt_written") is not False
        or observation.claim_policy != _closed_claim_policy()
        or observation.all_cases_observed is not (len(case_results) == 14)
        or observation.all_cases_passed
        is not all(row.case_passed for row in case_results)
        or observation.to_dict() != dict(value)
    ):
        raise ReferenceMinimizationValidationRunnerError(
            "run observation does not match the bounded runner contract"
        )
    return observation


def _read_matrix_worker_process_argv() -> tuple[str, ...]:
    try:
        raw = Path("/proc/self/cmdline").read_bytes()
        decoded = tuple(
            token.decode("utf-8") for token in raw.rstrip(b"\0").split(b"\0")
        )
    except (OSError, UnicodeDecodeError) as exc:
        raise ReferenceMinimizationValidationRunnerError(
            "matrix worker process argv is unavailable"
        ) from exc
    if not raw.endswith(b"\0") or not decoded or any(not token for token in decoded):
        raise ReferenceMinimizationValidationRunnerError(
            "matrix worker process argv is invalid"
        )
    return decoded


def _require_matrix_worker_preflight(request: Mapping[str, Any]) -> None:
    expected_fields = {
        "schema_id",
        "expected_code_commit_sha",
        "expected_runner_source_sha256",
        "expected_dependency_artifact_sha256_rows",
        "dependency_roots",
        "expected_environment_receipt_sha256",
        "expected_environment_fingerprint_sha256",
        "expected_python_hash_seed",
        "expected_application_seed",
        "expected_worker_environment",
        "expected_worker_environment_sha256",
        "expected_python_hash_probe_sha256",
    }
    if (
        not isinstance(request, Mapping)
        or set(request) != expected_fields
        or request.get("schema_id")
        != REFERENCE_MINIMIZATION_VALIDATION_MATRIX_WORKER_REQUEST_SCHEMA_ID
    ):
        raise ReferenceMinimizationValidationRunnerError(
            "matrix worker preflight request is invalid"
        )
    expected_commit = _require_commit(
        request["expected_code_commit_sha"],
        name="matrix worker code commit",
    )
    expected_source = _require_sha256(
        request["expected_runner_source_sha256"],
        name="matrix worker runner source",
    )
    raw_rows = request["expected_dependency_artifact_sha256_rows"]
    raw_roots = request["dependency_roots"]
    expected_environment = request["expected_worker_environment"]
    _require_sha256(
        request["expected_environment_receipt_sha256"],
        name="matrix worker environment receipt",
    )
    _require_sha256(
        request["expected_environment_fingerprint_sha256"],
        name="matrix worker environment fingerprint",
    )
    python_hash_seed = _require_worker_seed(
        request["expected_python_hash_seed"],
        name="matrix worker Python hash seed",
        maximum=2**32 - 1,
    )
    application_seed = _require_worker_seed(
        request["expected_application_seed"],
        name="matrix worker application seed",
        maximum=2**63 - 1,
    )
    expected_environment_sha256 = _require_sha256(
        request["expected_worker_environment_sha256"],
        name="matrix worker environment identity",
    )
    expected_hash_probe = _require_sha256(
        request["expected_python_hash_probe_sha256"],
        name="matrix worker hash probe",
    )
    if (
        not isinstance(raw_rows, dict)
        or not raw_rows
        or not isinstance(raw_roots, list)
        or not raw_roots
        or any(not isinstance(row, str) for row in raw_roots)
        or not isinstance(expected_environment, dict)
        or set(expected_environment)
        != _REFERENCE_MINIMIZATION_VALIDATION_WORKER_ENVIRONMENT_NAMES
        or any(
            not isinstance(name, str) or not isinstance(value, str)
            for name, value in expected_environment.items()
        )
    ):
        raise ReferenceMinimizationValidationRunnerError(
            "matrix worker preflight rows are invalid"
        )
    expected_rows = {
        key: _require_sha256(value, name=f"matrix worker dependency {key}")
        for key, value in raw_rows.items()
        if isinstance(key, str) and key
    }
    if len(expected_rows) != len(raw_rows):
        raise ReferenceMinimizationValidationRunnerError(
            "matrix worker dependency rows are invalid"
        )
    _require_source_only_python_runtime()
    expected_python_path = os.pathsep.join(raw_roots)
    expected_argv = (
        os.path.realpath(sys.executable),
        "-S",
        "-B",
        "-X",
        "pycache_prefix=/dev/null",
        "-c",
        _REFERENCE_MINIMIZATION_VALIDATION_FIXED_WORKER_BOOTSTRAP,
    )
    repository_root = Path(__file__).resolve(strict=True).parents[2]
    try:
        executable_stat = os.lstat(expected_argv[0])
        running_stat = os.stat("/proc/self/exe")
    except OSError as exc:
        raise ReferenceMinimizationValidationRunnerError(
            "matrix worker Python executable is unavailable"
        ) from exc
    if (
        not stat.S_ISREG(executable_stat.st_mode)
        or executable_stat.st_uid != 0
        or stat.S_IMODE(executable_stat.st_mode) & 0o022
        or (executable_stat.st_dev, executable_stat.st_ino)
        != (running_stat.st_dev, running_stat.st_ino)
        or sys.flags.isolated != 0
        or sys.flags.ignore_environment != 0
        or sys.flags.no_site != 1
        or sys.flags.no_user_site != 1
        or sys.flags.dont_write_bytecode != 1
        or sys.flags.hash_randomization != (0 if python_hash_seed == 0 else 1)
        or tuple(getattr(sys, "orig_argv", ())) != expected_argv
        or _read_matrix_worker_process_argv() != expected_argv
        or sys.argv != ["-c"]
        or Path.cwd().resolve(strict=True) != repository_root
        or dict(os.environ) != expected_environment
        or expected_environment.get("HOME") != "/nonexistent"
        or expected_environment.get("PATH") != "/usr/bin:/bin"
        or expected_environment.get("PYTHONNOUSERSITE") != "1"
        or expected_environment.get("PYTHONPATH") != expected_python_path
        or expected_environment.get("PYTHONHASHSEED") != str(python_hash_seed)
        or expected_environment.get(
            REFERENCE_MINIMIZATION_VALIDATION_APPLICATION_SEED_ENV
        )
        != str(application_seed)
        or _sha256(expected_environment) != expected_environment_sha256
        or _python_hash_probe_sha256() != expected_hash_probe
    ):
        raise ReferenceMinimizationValidationRunnerError(
            "matrix worker fixed runtime is invalid"
        )
    dependency_roots = _require_trusted_dependency_roots(tuple(raw_roots))
    _require_clean_checked_out_code_commit(expected_commit)
    if reference_minimization_validation_runner_source_sha256() != expected_source:
        raise ReferenceMinimizationValidationRunnerError(
            "matrix worker source does not match the supervisor"
        )
    if _observe_dependency_artifact_sha256_rows(dependency_roots) != expected_rows:
        raise ReferenceMinimizationValidationRunnerError(
            "matrix worker dependency bytes do not match the supervisor"
        )
    _configure_deterministic_torch_runtime(application_seed)


def _load_matrix_worker_request(raw: bytes) -> dict[str, Any]:
    if (
        not raw
        or len(raw) > REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_REQUEST_BYTES
        or not raw.endswith(b"\n")
    ):
        raise ReferenceMinimizationValidationRunnerError(
            "matrix worker request framing is invalid"
        )

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ReferenceMinimizationValidationRunnerError(
                    "matrix worker request contains a duplicate JSON key"
                )
            result[key] = value
        return result

    try:
        request = json.loads(
            raw[:-1].decode("ascii"),
            object_pairs_hook=reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReferenceMinimizationValidationRunnerError(
            "matrix worker request must be canonical ASCII JSON"
        ) from exc
    if not isinstance(request, dict) or _canonical_bytes(request) + b"\n" != raw:
        raise ReferenceMinimizationValidationRunnerError(
            "matrix worker request must be exact canonical JSON"
        )
    return request


def _matrix_worker_main_from_standard_streams() -> int:
    input_stream = getattr(sys.stdin, "buffer", sys.stdin)
    output_stream = getattr(sys.stdout, "buffer", sys.stdout)
    try:
        raw = input_stream.read(
            REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_REQUEST_BYTES + 1
        )
        if not isinstance(raw, bytes):
            return 2
        try:
            request = _load_matrix_worker_request(raw)
            _require_matrix_worker_preflight(request)
            rows = _run_case_matrix_in_process()
        except Exception:
            rows = _failure_complete_matrix("runner_worker_preflight_failed")
        output_stream.write(_canonical_bytes([row.to_dict() for row in rows]) + b"\n")
        output_stream.flush()
    except Exception:
        return 2
    return 0


def _matrix_worker_environment(
    environment_variable_rows: Sequence[tuple[str, str]],
    dependency_roots: Sequence[str],
) -> dict[str, str]:
    environment = dict(environment_variable_rows)
    expected_receipt_names = (
        _REFERENCE_MINIMIZATION_VALIDATION_WORKER_ENVIRONMENT_NAMES
        - {"HOME", "PATH", "PYTHONNOUSERSITE", "PYTHONPATH"}
    )
    if (
        set(environment) != expected_receipt_names
        or len(environment) != len(environment_variable_rows)
        or not dependency_roots
        or any(not isinstance(root, str) or not root for root in dependency_roots)
    ):
        raise ReferenceMinimizationValidationRunnerError(
            "matrix worker receipt environment is incomplete"
        )
    environment.update(
        {
            "HOME": "/nonexistent",
            "PATH": "/usr/bin:/bin",
            "PYTHONNOUSERSITE": "1",
            "PYTHONPATH": os.pathsep.join(dependency_roots),
        }
    )
    return environment


def _start_fixed_matrix_worker(request: Mapping[str, Any]) -> Any:
    raw_environment = request.get("expected_worker_environment")
    if (
        not isinstance(raw_environment, Mapping)
        or set(raw_environment)
        != _REFERENCE_MINIMIZATION_VALIDATION_WORKER_ENVIRONMENT_NAMES
        or any(not isinstance(value, str) for value in raw_environment.values())
    ):
        raise ReferenceMinimizationValidationRunnerError(
            "matrix worker launch binding is invalid"
        )
    executable = Path(os.path.realpath(sys.executable))
    try:
        executable_stat = executable.stat()
        running_stat = os.stat("/proc/self/exe")
    except OSError as exc:
        raise ReferenceMinimizationValidationRunnerError(
            "matrix worker Python executable is unavailable"
        ) from exc
    if (
        not executable.is_absolute()
        or not stat.S_ISREG(executable_stat.st_mode)
        or executable_stat.st_uid != 0
        or stat.S_IMODE(executable_stat.st_mode) & 0o022
        or (executable_stat.st_dev, executable_stat.st_ino)
        != (running_stat.st_dev, running_stat.st_ino)
    ):
        raise ReferenceMinimizationValidationRunnerError(
            "matrix worker Python executable does not match the supervisor"
        )
    repository_root = Path(__file__).resolve(strict=True).parents[2]
    try:
        return subprocess.Popen(
            [
                os.fspath(executable),
                "-S",
                "-B",
                "-X",
                "pycache_prefix=/dev/null",
                "-c",
                _REFERENCE_MINIMIZATION_VALIDATION_FIXED_WORKER_BOOTSTRAP,
            ],
            cwd=repository_root,
            env=dict(raw_environment),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except (OSError, ValueError) as exc:
        raise ReferenceMinimizationValidationRunnerError(
            "matrix worker process could not be started"
        ) from exc


def _communicate_fixed_matrix_worker(
    process: Any,
    request: Mapping[str, Any],
    *,
    deadline: float,
) -> tuple[bytes, bool, bool]:
    timed_out = False
    try:
        remaining = deadline - time.monotonic()
        if remaining <= 0.0:
            raise subprocess.TimeoutExpired(process.args, 0.0)
        output, _stderr = process.communicate(
            input=_canonical_bytes(dict(request)) + b"\n",
            timeout=remaining,
        )
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            process.kill()
        except OSError:
            pass
        try:
            output, _stderr = process.communicate(timeout=5.0)
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            raise ReferenceMinimizationValidationRunnerError(
                "matrix worker process could not be reaped after termination"
            ) from exc
    except (OSError, ValueError):
        try:
            process.kill()
        except OSError:
            pass
        try:
            process.communicate(timeout=5.0)
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            raise ReferenceMinimizationValidationRunnerError(
                "matrix worker process could not be reaped after communication failure"
            ) from exc
        return b"", False, False
    if not isinstance(output, bytes) or len(output) > (
        REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_WORKER_OUTPUT_BYTES + 1
    ):
        return b"", False, False
    return output, timed_out, process.returncode == 0


def _run_supervised_case_matrix(
    *,
    deadline: float,
    worker_preflight_request: Mapping[str, Any] | None = None,
) -> tuple[ReferenceMinimizationValidationCaseObservation, ...]:
    """Hard-stop a fixed child on deadline, including native-code stalls."""

    if deadline - time.monotonic() <= 0.0:
        return _failure_complete_matrix("runner_wall_time_exhausted")
    if worker_preflight_request is None:
        return _failure_complete_matrix("runner_worker_preflight_failed")
    raw_roots = worker_preflight_request.get("dependency_roots")
    raw_environment = worker_preflight_request.get("expected_worker_environment")
    if (
        not isinstance(raw_roots, list)
        or any(not isinstance(row, str) for row in raw_roots)
        or not isinstance(raw_environment, Mapping)
    ):
        return _failure_complete_matrix("runner_worker_preflight_failed")
    try:
        process = _start_fixed_matrix_worker(worker_preflight_request)
    except ReferenceMinimizationValidationRunnerError:
        return _failure_complete_matrix("runner_worker_start_failed")
    raw, timed_out, succeeded = _communicate_fixed_matrix_worker(
        process,
        worker_preflight_request,
        deadline=deadline,
    )
    if timed_out:
        return _failure_complete_matrix("runner_wall_time_exhausted")
    if not succeeded:
        return _failure_complete_matrix("runner_worker_output_invalid")
    if not raw.endswith(b"\n"):
        return _failure_complete_matrix("runner_worker_output_invalid")
    try:
        payload = json.loads(raw[:-1].decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _failure_complete_matrix("runner_worker_output_invalid")
    if (
        not isinstance(payload, list)
        or len(payload) != REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_CASES
        or raw != _canonical_bytes(payload) + b"\n"
    ):
        return _failure_complete_matrix("runner_worker_output_invalid")
    try:
        rows = tuple(_case_observation_from_payload(value) for value in payload)
    except ReferenceMinimizationValidationRunnerError:
        return _failure_complete_matrix("runner_worker_output_invalid")
    expected_ids = [
        row["case_id"]
        for row in cpu_minimization_validation_protocol_document()["case_manifest"][
            "cases"
        ]
    ]
    if [row.case_id for row in rows] != expected_ids or [
        row.ordinal for row in rows
    ] != list(range(1, 15)):
        return _failure_complete_matrix("runner_worker_output_crosswired")
    return rows


def _validate_manifest_before_start() -> None:
    protocol = cpu_minimization_validation_protocol_document()
    manifest = cpu_minimization_validation_materialization_manifest_document()
    protocol_ids = [row["case_id"] for row in protocol["case_manifest"]["cases"]]
    manifest_ids = [row["case_id"] for row in manifest["cases"]]
    if protocol_ids != manifest_ids or len(protocol_ids) != 14:
        raise ReferenceMinimizationValidationRunnerError(
            "materialized minimization manifest is cross-wired"
        )


def _runner_start_name(nonce: str) -> str:
    return f"{REFERENCE_MINIMIZATION_VALIDATION_RUNNER_START_PREFIX}{nonce}.json"


def _persist_runner_start(
    artifact_output_root: str | os.PathLike[str],
    *,
    nonce: str,
    environment_receipt_sha256: str,
    code_commit_sha: str,
    runner_source_sha256: str,
    started_at_utc: str,
) -> str:
    _require_reference_minimization_validation_root_outside_checkout(
        artifact_output_root, name="runner artifact root"
    )
    try:
        root_fd = _open_secure_root(artifact_output_root)
    except ReferenceMinimizationValidationNonceReservationError as exc:
        raise ReferenceMinimizationValidationRunnerError(
            "artifact output root must be an owned mode-0700 directory"
        ) from exc
    projection = {
        "schema_id": REFERENCE_MINIMIZATION_VALIDATION_RUNNER_START_SCHEMA_ID,
        "runner_contract_sha256": (
            FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RUNNER_CONTRACT_SHA256
        ),
        "protocol_sha256": FROZEN_CPU_MINIMIZATION_VALIDATION_PROTOCOL_SHA256,
        "authorization_nonce_sha256": nonce,
        "environment_receipt_sha256": environment_receipt_sha256,
        "code_commit_sha": code_commit_sha,
        "runner_source_sha256": runner_source_sha256,
        "started_at_utc": started_at_utc,
        "result_receipt_written": False,
        **_closed_claim_policy(),
    }
    record_sha256 = _sha256(projection)
    payload = _canonical_bytes(
        {**projection, "runner_start_record_sha256": record_sha256}
    )
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd: int | None = None
    try:
        try:
            fd = os.open(_runner_start_name(nonce), flags, 0o600, dir_fd=root_fd)
        except FileExistsError as exc:
            raise ReferenceMinimizationValidationRunnerAlreadyStartedError(
                "authorization nonce already has a runner-start record"
            ) from exc
        except (OSError, ValueError) as exc:
            raise ReferenceMinimizationValidationRunnerError(
                "runner-start record cannot be created securely"
            ) from exc
        try:
            _validate_record_stat(os.fstat(fd))
            remaining = memoryview(payload)
            while remaining:
                written = os.write(fd, remaining)
                if written <= 0:
                    raise OSError("runner-start write made no progress")
                remaining = remaining[written:]
            os.fsync(fd)
            _validate_record_stat(os.fstat(fd))
        except Exception as exc:
            raise ReferenceMinimizationValidationRunnerError(
                "runner-start persistence failed; the path remains consumed"
            ) from exc
        os.close(fd)
        fd = None
        os.fsync(root_fd)
    finally:
        if fd is not None:
            os.close(fd)
        os.close(root_fd)
    return record_sha256


def read_reference_minimization_validation_runner_start_record(
    artifact_output_root: str | os.PathLike[str],
    authorization_nonce_sha256: str,
    *,
    expected_record_sha256: str,
    expected_environment_receipt_sha256: str,
    expected_runner_source_sha256: str,
) -> dict[str, Any]:
    """Read a durable marker without releasing or deleting its nonce."""

    nonce = _require_sha256(authorization_nonce_sha256, name="authorization nonce")
    expected_record = _require_sha256(
        expected_record_sha256, name="runner-start record"
    )
    expected_environment = _require_sha256(
        expected_environment_receipt_sha256, name="environment receipt"
    )
    expected_source = _require_sha256(
        expected_runner_source_sha256, name="runner source"
    )
    _require_reference_minimization_validation_root_outside_checkout(
        artifact_output_root, name="runner artifact root"
    )
    try:
        root_fd = _open_secure_root(artifact_output_root)
    except ReferenceMinimizationValidationNonceReservationError as exc:
        raise ReferenceMinimizationValidationRunnerError(
            "runner artifact root does not satisfy the private POSIX policy"
        ) from exc
    descriptor: int | None = None
    try:
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(_runner_start_name(nonce), flags, dir_fd=root_fd)
        before = os.fstat(descriptor)
        _validate_record_stat(before)
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, 8192)
            if not chunk:
                break
            total += len(chunk)
            if total > REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_START_RECORD_BYTES:
                raise ReferenceMinimizationValidationRunnerError(
                    "runner-start record exceeds the size limit"
                )
            chunks.append(chunk)
        after = os.fstat(descriptor)
        _validate_record_stat(after)
        if _stable_record_identity(before) != _stable_record_identity(after):
            raise ReferenceMinimizationValidationRunnerError(
                "runner-start record changed while being read"
            )
    except (
        OSError,
        ValueError,
        ReferenceMinimizationValidationNonceReservationError,
    ) as exc:
        raise ReferenceMinimizationValidationRunnerError(
            "runner-start record cannot be read securely"
        ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(root_fd)
    raw = b"".join(chunks)

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ReferenceMinimizationValidationRunnerError(
                    "runner-start record contains a duplicate JSON key"
                )
            result[key] = value
        return result

    try:
        payload = json.loads(raw.decode("ascii"), object_pairs_hook=reject_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReferenceMinimizationValidationRunnerError(
            "runner-start record is not canonical JSON"
        ) from exc
    if not isinstance(payload, dict) or _canonical_bytes(payload) != raw:
        raise ReferenceMinimizationValidationRunnerError(
            "runner-start record is not canonical JSON"
        )
    observed_record = payload.pop("runner_start_record_sha256", None)
    if observed_record != _sha256(payload) or observed_record != expected_record:
        raise ReferenceMinimizationValidationRunnerError(
            "runner-start record identity is cross-wired"
        )
    if (
        payload.get("schema_id")
        != REFERENCE_MINIMIZATION_VALIDATION_RUNNER_START_SCHEMA_ID
        or payload.get("authorization_nonce_sha256") != nonce
        or payload.get("environment_receipt_sha256") != expected_environment
        or payload.get("runner_source_sha256") != expected_source
        or payload.get("result_receipt_written") is not False
        or any(payload.get(name) is not False for name in _closed_claim_policy())
    ):
        raise ReferenceMinimizationValidationRunnerError(
            "runner-start record does not match the bounded runner contract"
        )
    return {**payload, "runner_start_record_sha256": observed_record}


def run_bounded_cpu_reference_minimization_validation(
    artifact_output_root: str | os.PathLike[str],
    authorization_nonce_sha256: str,
    *,
    expected_environment_receipt_sha256: str,
    expected_code_commit_sha: str,
    expected_dependency_artifact_sha256_rows: Mapping[str, str],
) -> ReferenceMinimizationValidationRunObservation:
    """Consume one run start and evaluate the complete frozen matrix."""

    nonce = _require_sha256(authorization_nonce_sha256, name="authorization nonce")
    expected_receipt = _require_sha256(
        expected_environment_receipt_sha256, name="environment receipt"
    )
    expected_commit = _require_commit(expected_code_commit_sha, name="code commit")
    dependency_roots = _require_isolated_python_bootstrap_runtime()
    _require_source_only_python_runtime()
    receipt = require_reference_minimization_validation_execution_environment_receipt_for_runner(
        artifact_output_root,
        nonce,
        expected_receipt_sha256=expected_receipt,
    )
    started = _parse_utc(receipt.started_at_utc, name="environment receipt start")
    now = _utc_now()
    if (
        now < started
        or now - started > REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_RECEIPT_AGE
    ):
        raise ReferenceMinimizationValidationRunnerError(
            "execution environment receipt is outside the runner freshness window"
        )
    if receipt.code_commit_sha != expected_commit:
        raise ReferenceMinimizationValidationRunnerError(
            "environment receipt code commit is cross-wired"
        )
    expected_rows = tuple(sorted(expected_dependency_artifact_sha256_rows.items()))
    if receipt.dependency_artifact_sha256_rows != expected_rows:
        raise ReferenceMinimizationValidationRunnerError(
            "environment receipt dependency artifacts are cross-wired"
        )
    if (
        tuple(
            sorted(_observe_dependency_artifact_sha256_rows(dependency_roots).items())
        )
        != expected_rows
    ):
        raise ReferenceMinimizationValidationRunnerError(
            "live runner dependency bytes do not match the signed receipt"
        )
    source_sha256 = reference_minimization_validation_runner_source_sha256()
    if receipt.runner_source_sha256 != source_sha256:
        raise ReferenceMinimizationValidationRunnerError(
            "environment receipt runner source is cross-wired"
        )
    if tuple(receipt.command_argv) != (
        REFERENCE_MINIMIZATION_VALIDATION_LOGICAL_RUNNER_ARGV
    ):
        raise ReferenceMinimizationValidationRunnerError(
            "environment receipt runner argv is cross-wired"
        )
    _require_clean_checked_out_code_commit(expected_commit)
    _validate_manifest_before_start()
    raw_dependency_roots = [os.fspath(root) for root in dependency_roots]
    worker_environment = _matrix_worker_environment(
        receipt.environment_variable_rows,
        raw_dependency_roots,
    )
    worker_preflight_request = {
        "schema_id": (
            REFERENCE_MINIMIZATION_VALIDATION_MATRIX_WORKER_REQUEST_SCHEMA_ID
        ),
        "expected_code_commit_sha": expected_commit,
        "expected_runner_source_sha256": source_sha256,
        "expected_dependency_artifact_sha256_rows": dict(expected_rows),
        "dependency_roots": raw_dependency_roots,
        "expected_environment_receipt_sha256": receipt.receipt_sha256,
        "expected_environment_fingerprint_sha256": (
            receipt.environment_fingerprint_sha256
        ),
        "expected_python_hash_seed": _require_worker_seed(
            receipt.python_hash_seed,
            name="matrix worker Python hash seed",
            maximum=2**32 - 1,
        ),
        "expected_application_seed": _require_worker_seed(
            receipt.application_seed,
            name="matrix worker application seed",
            maximum=2**63 - 1,
        ),
        "expected_worker_environment": worker_environment,
        "expected_worker_environment_sha256": _sha256(worker_environment),
        "expected_python_hash_probe_sha256": _python_hash_probe_sha256(),
    }
    started_at = _format_utc(now)
    deadline = (
        time.monotonic() + REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_WALL_SECONDS
    )
    marker = _persist_runner_start(
        artifact_output_root,
        nonce=nonce,
        environment_receipt_sha256=expected_receipt,
        code_commit_sha=expected_commit,
        runner_source_sha256=source_sha256,
        started_at_utc=started_at,
    )
    case_results = _run_supervised_case_matrix(
        deadline=deadline,
        worker_preflight_request=worker_preflight_request,
    )
    all_observed = len(case_results) == 14
    return ReferenceMinimizationValidationRunObservation(
        authorization_nonce_sha256=nonce,
        environment_receipt_sha256=expected_receipt,
        environment_fingerprint_sha256=receipt.environment_fingerprint_sha256,
        code_commit_sha=expected_commit,
        runner_source_sha256=source_sha256,
        dependency_artifact_sha256_rows=expected_rows,
        command_argv=tuple(receipt.command_argv),
        seed=receipt.application_seed,
        started_at_utc=started_at,
        completed_at_utc=_format_utc(_utc_now()),
        runner_start_record_sha256=marker,
        case_results=case_results,
        all_cases_observed=all_observed,
        all_cases_passed=all_observed and all(row.case_passed for row in case_results),
        claim_policy=_closed_claim_policy(),
    )


def reference_minimization_validation_runner_contract_decision() -> dict[str, Any]:
    return {
        "runner_contract_sha256": (
            FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RUNNER_CONTRACT_SHA256
        ),
        "bounded_validation_runner_implemented": True,
        "production_process_entrypoint_wired": True,
        "preconfigured_trust_store_present": False,
        "production_runner_start_consumed": False,
        "production_validation_execution_authorized": False,
        "production_validation_results_collected": False,
        "result_receipt_writer_implemented": True,
        **_closed_claim_policy(),
    }


def _require_sha256_sequence(value: object, *, name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ReferenceMinimizationValidationRunnerError(
            f"{name} must be a JSON SHA-256 array"
        )
    rows = tuple(_require_sha256(row, name=f"{name} entry") for row in value)
    if rows != tuple(sorted(set(rows))):
        raise ReferenceMinimizationValidationRunnerError(
            f"{name} must be sorted and unique"
        )
    return rows


def _verification_key_from_hex(value: object, *, name: str) -> bytes:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ReferenceMinimizationValidationRunnerError(
            f"{name} must be an exact lowercase Ed25519 public key"
        )
    return bytes.fromhex(value)


def _trust_store_key_id(value: object, *, name: str) -> str:
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 128
        or any(character not in allowed for character in value)
    ):
        raise ReferenceMinimizationValidationRunnerError(
            f"{name} must contain 1 to 128 safe ASCII characters"
        )
    return value


def _trusted_reviewer_keys_from_store(value: object) -> dict[str, Any]:
    from .reference_minimization_validation_review import (
        MinimizationScientificReviewerTrustAnchor,
    )

    if not isinstance(value, list) or not value:
        raise ReferenceMinimizationValidationRunnerError(
            "preconfigured trust store reviewer keys must be a non-empty array"
        )
    result: dict[str, MinimizationScientificReviewerTrustAnchor] = {}
    for row in value:
        if not isinstance(row, dict) or set(row) != {
            "key_id",
            "reviewer_identity_sha256",
            "verification_key_hex",
        }:
            raise ReferenceMinimizationValidationRunnerError(
                "preconfigured trust store reviewer key fields are invalid"
            )
        key_id = _trust_store_key_id(
            row["key_id"],
            name="preconfigured reviewer key id",
        )
        if key_id in result:
            raise ReferenceMinimizationValidationRunnerError(
                "preconfigured trust store reviewer key ids are not unique"
            )
        try:
            result[key_id] = MinimizationScientificReviewerTrustAnchor(
                row["reviewer_identity_sha256"],
                _verification_key_from_hex(
                    row["verification_key_hex"],
                    name="trusted reviewer verification key",
                ),
            )
        except Exception as exc:
            raise ReferenceMinimizationValidationRunnerError(
                "preconfigured trust store reviewer key is invalid"
            ) from exc
    return result


def _trusted_operator_keys_from_store(value: object) -> dict[str, Any]:
    from .reference_minimization_validation_authorization import (
        MinimizationAuthorizationOperatorTrustAnchor,
    )

    if not isinstance(value, list) or not value:
        raise ReferenceMinimizationValidationRunnerError(
            "preconfigured trust store operator keys must be a non-empty array"
        )
    result: dict[str, MinimizationAuthorizationOperatorTrustAnchor] = {}
    for row in value:
        if not isinstance(row, dict) or set(row) != {
            "key_id",
            "operator_identity_sha256",
            "verification_key_hex",
        }:
            raise ReferenceMinimizationValidationRunnerError(
                "preconfigured trust store operator key fields are invalid"
            )
        key_id = _trust_store_key_id(
            row["key_id"],
            name="preconfigured operator key id",
        )
        if key_id in result:
            raise ReferenceMinimizationValidationRunnerError(
                "preconfigured trust store operator key ids are not unique"
            )
        try:
            result[key_id] = MinimizationAuthorizationOperatorTrustAnchor(
                row["operator_identity_sha256"],
                _verification_key_from_hex(
                    row["verification_key_hex"],
                    name="trusted operator verification key",
                ),
            )
        except Exception as exc:
            raise ReferenceMinimizationValidationRunnerError(
                "preconfigured trust store operator key is invalid"
            ) from exc
    return result


def _validate_preconfigured_trust_directory(file_stat: os.stat_result) -> None:
    if (
        not stat.S_ISDIR(file_stat.st_mode)
        or file_stat.st_uid != 0
        or stat.S_IMODE(file_stat.st_mode) & 0o022
    ):
        raise ReferenceMinimizationValidationRunnerError(
            "preconfigured trust-store directory policy failed"
        )


def _validate_preconfigured_trust_file(file_stat: os.stat_result) -> None:
    if (
        not stat.S_ISREG(file_stat.st_mode)
        or file_stat.st_uid != 0
        or stat.S_IMODE(file_stat.st_mode) != 0o600
        or file_stat.st_nlink != 1
        or not 0
        < file_stat.st_size
        <= REFERENCE_MINIMIZATION_VALIDATION_TRUST_STORE_MAX_BYTES
    ):
        raise ReferenceMinimizationValidationRunnerError(
            "preconfigured trust-store file policy failed"
        )


def _open_preconfigured_trust_store() -> int:
    required_flags = ("O_NOFOLLOW", "O_CLOEXEC", "O_DIRECTORY", "O_NONBLOCK")
    if (
        os.name != "posix"
        or any(not hasattr(os, name) for name in required_flags)
        or os.open not in os.supports_dir_fd
    ):
        raise ReferenceMinimizationValidationRunnerError(
            "secure preconfigured trust-store access is unavailable"
        )
    path = Path(REFERENCE_MINIMIZATION_VALIDATION_TRUST_STORE_PATH)
    if not path.is_absolute() or ".." in path.parts or path.anchor != os.sep:
        raise ReferenceMinimizationValidationRunnerError(
            "preconfigured trust-store path is invalid"
        )
    components = tuple(part for part in path.parts[1:] if part not in {"", "."})
    if len(components) < 2:
        raise ReferenceMinimizationValidationRunnerError(
            "preconfigured trust-store path is invalid"
        )
    directory_flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_DIRECTORY
    current_fd = -1
    file_fd = -1
    try:
        current_fd = os.open(os.sep, directory_flags)
        for component in components[:-1]:
            _validate_preconfigured_trust_directory(os.fstat(current_fd))
            next_fd = os.open(component, directory_flags, dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
        _validate_preconfigured_trust_directory(os.fstat(current_fd))
        file_fd = os.open(
            components[-1],
            os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=current_fd,
        )
        _validate_preconfigured_trust_file(os.fstat(file_fd))
        result_fd = file_fd
        file_fd = -1
        return result_fd
    except ReferenceMinimizationValidationRunnerError:
        raise
    except (OSError, ValueError) as exc:
        raise ReferenceMinimizationValidationRunnerError(
            "preconfigured trust store cannot be opened securely"
        ) from exc
    finally:
        if file_fd >= 0:
            os.close(file_fd)
        if current_fd >= 0:
            os.close(current_fd)


def _load_preconfigured_trust_anchors() -> tuple[dict[str, Any], dict[str, Any]]:
    descriptor = _open_preconfigured_trust_store()
    try:
        initial_stat = os.fstat(descriptor)
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, 8192)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > REFERENCE_MINIMIZATION_VALIDATION_TRUST_STORE_MAX_BYTES:
                raise ReferenceMinimizationValidationRunnerError(
                    "preconfigured trust store exceeds the size limit"
                )
        final_stat = os.fstat(descriptor)
        _validate_preconfigured_trust_file(final_stat)
    except ReferenceMinimizationValidationRunnerError:
        raise
    except OSError as exc:
        raise ReferenceMinimizationValidationRunnerError(
            "preconfigured trust store cannot be read securely"
        ) from exc
    finally:
        os.close(descriptor)
    raw = b"".join(chunks)
    if (
        initial_stat.st_dev != final_stat.st_dev
        or initial_stat.st_ino != final_stat.st_ino
        or initial_stat.st_size != final_stat.st_size
        or len(raw) != initial_stat.st_size
        or not raw.endswith(b"\n")
    ):
        raise ReferenceMinimizationValidationRunnerError(
            "preconfigured trust store changed or is not framed canonically"
        )

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ReferenceMinimizationValidationRunnerError(
                    "preconfigured trust store contains a duplicate JSON key"
                )
            result[key] = value
        return result

    try:
        payload = json.loads(
            raw[:-1].decode("ascii"),
            object_pairs_hook=reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReferenceMinimizationValidationRunnerError(
            "preconfigured trust store must be canonical ASCII JSON"
        ) from exc
    if (
        not isinstance(payload, dict)
        or set(payload) != {"schema_id", "reviewer_keys", "operator_keys"}
        or payload.get("schema_id")
        != REFERENCE_MINIMIZATION_VALIDATION_TRUST_STORE_SCHEMA_ID
        or _canonical_bytes(payload) + b"\n" != raw
    ):
        raise ReferenceMinimizationValidationRunnerError(
            "preconfigured trust store is not the exact canonical schema"
        )
    return (
        _trusted_reviewer_keys_from_store(payload["reviewer_keys"]),
        _trusted_operator_keys_from_store(payload["operator_keys"]),
    )


def _load_runner_request(raw: bytes) -> dict[str, Any]:
    if (
        not raw
        or len(raw) > REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_REQUEST_BYTES
        or not raw.endswith(b"\n")
    ):
        raise ReferenceMinimizationValidationRunnerError(
            "runner request size or framing is invalid"
        )

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ReferenceMinimizationValidationRunnerError(
                    "runner request contains a duplicate JSON key"
                )
            result[key] = value
        return result

    try:
        request = json.loads(
            raw[:-1].decode("ascii"),
            object_pairs_hook=reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReferenceMinimizationValidationRunnerError(
            "runner request must be canonical ASCII JSON"
        ) from exc
    if not isinstance(request, dict) or _canonical_bytes(request) + b"\n" != raw:
        raise ReferenceMinimizationValidationRunnerError(
            "runner request must be exact canonical JSON"
        )
    expected_fields = {
        "schema_id",
        "reservation_root",
        "artifact_output_root",
        "authorization_nonce_sha256",
        "authorization_receipt",
        "review_attestation",
        "expected_implementation_author_identity_sha256",
        "network_isolation_attestation",
        "expected_code_commit_sha",
        "expected_runner_source_sha256",
        "expected_dependency_artifact_sha256_rows",
        "revoked_authorization_receipt_sha256s",
        "revoked_review_attestation_sha256s",
        "externally_conflicting_nonce_sha256s",
        "revoked_network_attestation_sha256s",
    }
    if (
        set(request) != expected_fields
        or request.get("schema_id")
        != REFERENCE_MINIMIZATION_VALIDATION_RUNNER_REQUEST_SCHEMA_ID
    ):
        raise ReferenceMinimizationValidationRunnerError(
            "runner request fields are invalid"
        )
    for name in ("reservation_root", "artifact_output_root"):
        if not isinstance(request[name], str) or not request[name]:
            raise ReferenceMinimizationValidationRunnerError(
                f"runner request {name} must be non-empty text"
            )
    if (
        not isinstance(request["authorization_receipt"], dict)
        or not isinstance(request["review_attestation"], dict)
        or not isinstance(request["network_isolation_attestation"], dict)
    ):
        raise ReferenceMinimizationValidationRunnerError(
            "runner request signed artifacts must be JSON objects"
        )
    if not isinstance(request["expected_dependency_artifact_sha256_rows"], dict):
        raise ReferenceMinimizationValidationRunnerError(
            "runner request dependency rows must be a JSON object"
        )
    return request


def _execute_runner_request(request: Mapping[str, Any]) -> dict[str, Any]:
    from .reference_minimization_validation_result_writer import (
        write_reference_minimization_validation_result_receipt,
    )
    from .reference_minimization_validation_run_start import (
        create_reference_minimization_validation_execution_environment_receipt,
    )

    _require_runner_root_outside_checkout(
        request["reservation_root"],
        name="reservation root",
    )
    _require_runner_root_outside_checkout(
        request["artifact_output_root"],
        name="artifact output root",
    )
    nonce = _require_sha256(
        request["authorization_nonce_sha256"],
        name="runner request authorization nonce",
    )
    expected_author = _require_sha256(
        request["expected_implementation_author_identity_sha256"],
        name="runner request implementation author",
    )
    revoked_authorizations = _require_sha256_sequence(
        request["revoked_authorization_receipt_sha256s"],
        name="revoked authorization receipts",
    )
    revoked_reviews = _require_sha256_sequence(
        request["revoked_review_attestation_sha256s"],
        name="revoked review attestations",
    )
    conflicting_nonces = _require_sha256_sequence(
        request["externally_conflicting_nonce_sha256s"],
        name="externally conflicting nonces",
    )
    revoked_network = _require_sha256_sequence(
        request["revoked_network_attestation_sha256s"],
        name="revoked network attestations",
    )
    expected_commit = _require_commit(
        request["expected_code_commit_sha"],
        name="runner request code commit",
    )
    expected_source = _require_sha256(
        request["expected_runner_source_sha256"],
        name="runner request source",
    )
    raw_dependency_rows = request["expected_dependency_artifact_sha256_rows"]
    if not isinstance(raw_dependency_rows, dict) or not raw_dependency_rows:
        raise ReferenceMinimizationValidationRunnerError(
            "runner request dependency rows are invalid"
        )
    expected_dependency_rows = {
        key: _require_sha256(value, name=f"runner request dependency {key}")
        for key, value in raw_dependency_rows.items()
        if isinstance(key, str) and key
    }
    if len(expected_dependency_rows) != len(raw_dependency_rows):
        raise ReferenceMinimizationValidationRunnerError(
            "runner request dependency rows are invalid"
        )
    if (
        reference_minimization_validation_checked_out_code_commit_sha()
        != expected_commit
    ):
        raise ReferenceMinimizationValidationRunnerError(
            "runner request code commit does not match the checkout"
        )
    dependency_roots = _require_isolated_python_bootstrap_runtime()
    _require_source_only_python_runtime()
    _require_clean_checked_out_code_commit(expected_commit)
    if reference_minimization_validation_runner_source_sha256() != expected_source:
        raise ReferenceMinimizationValidationRunnerError(
            "runner request source does not match the loaded runner"
        )
    if (
        _observe_dependency_artifact_sha256_rows(dependency_roots)
        != expected_dependency_rows
    ):
        raise ReferenceMinimizationValidationRunnerError(
            "runner request dependency bytes do not match the loaded runtime"
        )
    reviewer_keys, operator_keys = _load_preconfigured_trust_anchors()
    _configure_deterministic_torch_runtime()

    environment = (
        create_reference_minimization_validation_execution_environment_receipt(
            request["reservation_root"],
            request["artifact_output_root"],
            authorization_nonce_sha256=nonce,
            authorization_receipt=request["authorization_receipt"],
            review_attestation=request["review_attestation"],
            trusted_reviewer_keys=reviewer_keys,
            expected_implementation_author_identity_sha256=expected_author,
            trusted_operator_keys=operator_keys,
            network_isolation_attestation=request["network_isolation_attestation"],
            expected_code_commit_sha=expected_commit,
            expected_runner_source_sha256=expected_source,
            expected_dependency_artifact_sha256_rows=expected_dependency_rows,
            revoked_receipt_sha256s=revoked_authorizations,
            revoked_review_attestation_sha256s=revoked_reviews,
            externally_conflicting_nonce_sha256s=conflicting_nonces,
            revoked_network_attestation_sha256s=revoked_network,
        )
    )
    observation = run_bounded_cpu_reference_minimization_validation(
        request["artifact_output_root"],
        nonce,
        expected_environment_receipt_sha256=environment.receipt_sha256,
        expected_code_commit_sha=expected_commit,
        expected_dependency_artifact_sha256_rows=expected_dependency_rows,
    )
    receipt = write_reference_minimization_validation_result_receipt(
        request["artifact_output_root"],
        nonce,
        observation,
        review_attestation=request["review_attestation"],
        authorization_receipt=request["authorization_receipt"],
        trusted_reviewer_keys=reviewer_keys,
        expected_implementation_author_identity_sha256=expected_author,
        trusted_operator_keys=operator_keys,
        revoked_authorization_receipt_sha256s=revoked_authorizations,
        revoked_review_attestation_sha256s=revoked_reviews,
        externally_conflicting_nonce_sha256s=conflicting_nonces,
    )
    return {
        "schema_id": REFERENCE_MINIMIZATION_VALIDATION_RUNNER_RESPONSE_SCHEMA_ID,
        "environment_receipt_sha256": environment.receipt_sha256,
        "observation_sha256": observation.observation_sha256,
        "result_receipt_sha256": receipt.receipt_sha256,
        "production_validation_results_collected": False,
        "parameter_fitting_authorized": False,
        "scientifically_validated": False,
        "claim_safe": False,
    }


def _main_from_canonical_request(raw: bytes) -> int:
    """Execute one request already bounded and verified by the bootstrap."""

    output_stream = getattr(sys.stdout, "buffer", sys.stdout)
    try:
        response = _execute_runner_request(_load_runner_request(raw))
        output_stream.write(_canonical_bytes(response) + b"\n")
        output_stream.flush()
    except Exception:
        return 2
    return 0


def _main_from_standard_streams() -> int:
    input_stream = getattr(sys.stdin, "buffer", sys.stdin)
    try:
        raw = input_stream.read(
            REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_REQUEST_BYTES + 1
        )
    except (AttributeError, OSError):
        return 2
    if not isinstance(raw, bytes):
        return 2
    return _main_from_canonical_request(raw)


def main() -> int:
    """Run the exact stdin-delivered, fail-closed minimization chain."""

    canonical_name = (
        "betelgeuze_engine_v2.physics.reference_minimization_validation_runner"
    )
    canonical_module = sys.modules.get(canonical_name)
    delegate = (
        __name__ == "__main__"
        and canonical_module is not None
        and canonical_module is not sys.modules.get(__name__)
    )
    implementation = canonical_module if delegate else sys.modules[__name__]
    return implementation._main_from_standard_streams()


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RUNNER_CONTRACT_SHA256",
    "REFERENCE_MINIMIZATION_VALIDATION_RUNNER_CONTRACT_ID",
    "REFERENCE_MINIMIZATION_VALIDATION_RUNNER_CONTRACT_SCHEMA_ID",
    "REFERENCE_MINIMIZATION_VALIDATION_RUNNER_CONTRACT_VERSION",
    "REFERENCE_MINIMIZATION_VALIDATION_LOGICAL_RUNNER_ARGV",
    "REFERENCE_MINIMIZATION_VALIDATION_MATRIX_WORKER_REQUEST_SCHEMA_ID",
    "REFERENCE_MINIMIZATION_VALIDATION_COORDINATE_DIGEST_ALGORITHM",
    "REFERENCE_MINIMIZATION_VALIDATION_COORDINATE_ENCODING",
    "REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_CASES",
    "REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_RECEIPT_AGE",
    "REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_REQUEST_BYTES",
    "REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_START_RECORD_BYTES",
    "REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_WALL_SECONDS",
    "REFERENCE_MINIMIZATION_VALIDATION_RUNNER_REQUEST_SCHEMA_ID",
    "REFERENCE_MINIMIZATION_VALIDATION_RUNNER_RESPONSE_SCHEMA_ID",
    "REFERENCE_MINIMIZATION_VALIDATION_RUNNER_START_SCHEMA_ID",
    "REFERENCE_MINIMIZATION_VALIDATION_RUN_OBSERVATION_SCHEMA_ID",
    "REFERENCE_MINIMIZATION_VALIDATION_TRUST_STORE_MAX_BYTES",
    "REFERENCE_MINIMIZATION_VALIDATION_TRUST_STORE_PATH",
    "REFERENCE_MINIMIZATION_VALIDATION_TRUST_STORE_SCHEMA_ID",
    "ReferenceMinimizationValidationCaseObservation",
    "ReferenceMinimizationValidationCoordinateTrace",
    "ReferenceMinimizationValidationCoordinateTraceStep",
    "ReferenceMinimizationValidationRunObservation",
    "ReferenceMinimizationValidationRunnerAlreadyStartedError",
    "ReferenceMinimizationValidationRunnerError",
    "reference_minimization_validation_checked_out_code_commit_sha",
    "reference_minimization_validation_runner_contract_decision",
    "reference_minimization_validation_runner_contract_document",
    "reference_minimization_validation_runner_source_sha256",
    "read_reference_minimization_validation_runner_start_record",
    "require_reference_minimization_validation_run_observation_document",
    "require_reference_minimization_validation_runner_contract_document",
    "run_bounded_cpu_reference_minimization_validation",
]
