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
import multiprocessing
import os
from pathlib import Path
import stat
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
    REFERENCE_MINIMIZATION_VALIDATION_LOGICAL_RUNNER_ARGV,
    reference_minimization_validation_bootstrap_path,
    reference_minimization_validation_execution_source_sha256,
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
    cpu_minimization_validation_protocol_document,
)
from .reference_minimization_validation_run_start import (
    _require_reference_minimization_validation_root_outside_checkout,
    require_reference_minimization_validation_execution_environment_receipt_for_runner,
)


REFERENCE_MINIMIZATION_VALIDATION_RUNNER_CONTRACT_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_validation_runner_contract/1.0.0"
)
REFERENCE_MINIMIZATION_VALIDATION_RUNNER_START_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_validation_runner_start/1.0.0"
)
REFERENCE_MINIMIZATION_VALIDATION_RUN_OBSERVATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_validation_run_observation/1.0.0"
)
REFERENCE_MINIMIZATION_VALIDATION_RUNNER_CONTRACT_ID = (
    "cpu_reference_minimization_validation_bounded_runner/1.0.0"
)
REFERENCE_MINIMIZATION_VALIDATION_RUNNER_CONTRACT_VERSION = "1.0.0"
REFERENCE_MINIMIZATION_VALIDATION_RUNNER_CONTRACT_FROZEN_AT_UTC = (
    "2026-07-18T09:00:00Z"
)
REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_RECEIPT_AGE = timedelta(minutes=5)
REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_WALL_SECONDS = 120.0
REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_CASES = 14
REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_START_RECORD_BYTES = 65_536
REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_WORKER_OUTPUT_BYTES = 8 * 1_048_576
REFERENCE_MINIMIZATION_VALIDATION_RUNNER_START_PREFIX = (
    "reference-minimization-validation-runner-start-"
)
FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RUNNER_CONTRACT_SHA256 = (
    "26e3ad464ee57111f75d7e6e2d497d7c9b78db87f8e0dcd50b15746ba4eedfb1"
)


class ReferenceMinimizationValidationRunnerError(RuntimeError):
    """The bounded runner contract or execution preflight failed."""


class ReferenceMinimizationValidationRunnerAlreadyStartedError(
    ReferenceMinimizationValidationRunnerError
):
    """The authorization nonce already has a durable runner-start marker."""


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
    return value.astimezone(timezone.utc).replace(microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
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


def _require_isolated_python_bootstrap_runtime() -> tuple[Path, ...]:
    """Make the stdlib trust bootstrap mandatory for every real run."""

    state = getattr(
        sys, REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_STATE_ATTRIBUTE, None
    )
    expected_bootstrap = Path(
        reference_minimization_validation_bootstrap_path()
    )
    expected_repository = Path(__file__).resolve(strict=True).parents[2]
    if (
        sys.flags.isolated != 1
        or sys.flags.ignore_environment != 1
        or sys.flags.no_site != 1
        or sys.flags.no_user_site != 1
        or sys.flags.dont_write_bytecode != 1
        or sys.dont_write_bytecode is not True
        or sys.pycache_prefix != "/dev/null"
        or not isinstance(state, tuple)
        or len(state) != 4
    ):
        raise ReferenceMinimizationValidationRunnerError(
            "minimization runner requires the isolated trust bootstrap"
        )
    bootstrap_path, repository_root, raw_dependency_roots, frozen_sys_path = state
    if (
        bootstrap_path != os.fspath(expected_bootstrap)
        or repository_root != os.fspath(expected_repository)
        or not isinstance(raw_dependency_roots, tuple)
        or not raw_dependency_roots
        or not isinstance(frozen_sys_path, tuple)
        or tuple(sys.path) != frozen_sys_path
        or not sys.path
        or sys.path[0] != os.fspath(expected_repository)
    ):
        raise ReferenceMinimizationValidationRunnerError(
            "minimization runner bootstrap state is invalid"
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


def _contract_projection() -> dict[str, Any]:
    protocol = cpu_minimization_validation_protocol_document()
    return {
        "schema_id": REFERENCE_MINIMIZATION_VALIDATION_RUNNER_CONTRACT_SCHEMA_ID,
        "contract_id": REFERENCE_MINIMIZATION_VALIDATION_RUNNER_CONTRACT_ID,
        "contract_version": REFERENCE_MINIMIZATION_VALIDATION_RUNNER_CONTRACT_VERSION,
        "frozen_at_utc": REFERENCE_MINIMIZATION_VALIDATION_RUNNER_CONTRACT_FROZEN_AT_UTC,
        "protocol_sha256": FROZEN_CPU_MINIMIZATION_VALIDATION_PROTOCOL_SHA256,
        "bounds": {
            "case_count": REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_CASES,
            "maximum_wall_seconds": REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_WALL_SECONDS,
            "skipped_cases_allowed": False,
            "partial_results_allowed": False,
        },
        "case_order": [
            row["case_id"] for row in protocol["case_manifest"]["cases"]
        ],
        "trust_boundary": {
            "stdlib_only_isolated_bootstrap_required": True,
            "source_only_imports_required": True,
            "caller_supplied_trust_keys_allowed": False,
            "external_root_owned_mode_0600_trust_store_required": True,
            "clean_git_head_measured": True,
            "git_replacement_refs_rejected": True,
            "bootstrap_and_runner_source_identity_measured": True,
            "dependency_roots_root_owned_read_only": True,
        },
        "worker": {
            "fresh_spawn_process": True,
            "parent_supervised": True,
            "native_stall_hard_kill": True,
            "failure_complete_timeout_observation": True,
        },
        "observation": {
            "in_memory_only": True,
            "failure_inclusive": True,
            "failed_metrics_and_cases_retained": True,
            "result_receipt_written": False,
        },
        "start_marker": {
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
    metric_values: tuple[tuple[str, float], ...]
    case_passed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "accepted_energy_ledger": list(self.accepted_energy_ledger),
            "metric_values": [
                {"metric_id": key, "value": value}
                for key, value in self.metric_values
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
                "failed_case_count": sum(not row.case_passed for row in self.case_results),
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
        (abs(float(left) - float(right)) for a, b in zip(first, second, strict=True)
         for left, right in zip(a, b, strict=True)),
        default=0.0,
    )


def _operational_result_sha256(result: object) -> str:
    return _sha256(result.to_dict())  # type: ignore[attr-defined]


def _run_operational(case: Any, *, pause: int | None = None, checkpoint: Any = None) -> Any:
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


def _threshold_pass(operator: str, value: float, threshold: float) -> bool:
    if operator == "equal":
        return value == threshold
    if operator == "less_than_or_equal":
        return value <= threshold
    if operator == "greater_than_or_equal":
        return value >= threshold
    raise ReferenceMinimizationValidationRunnerError("unknown metric threshold")


def _evaluate_case(ordinal: int, protocol_row: Mapping[str, Any]) -> ReferenceMinimizationValidationCaseObservation:
    case = materialize_frozen_cpu_minimization_validation_case(protocol_row["case_id"])
    independent_source = replace(
        case.independent_oracle_input, pause_after_accepted_iterations=None
    )
    independent = evaluate_independent_minimization_oracle(
        case.independent_oracle_input
        if case.expected_outcome == "fail_closed"
        else independent_source
    )
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
            metric_values=(),
            case_passed=passed,
        )

    operational = _run_operational(case)
    checkpoint_equal = 1.0
    if case.pause_after_accepted_iterations is not None:
        paused = _run_operational(
            case, pause=case.pause_after_accepted_iterations
        )
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
        operational_force = float(
            operational.final_max_force_kcal_per_mol_angstrom
        )
    else:
        operational_force = float(
            operational.final_max_tangent_force_kcal_per_mol_angstrom
        )
    final_force = abs(
        operational_force
        - independent.final_max_force_kcal_per_mol_angstrom
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
                        "runner_case_exception:"
                        + exc.__class__.__name__.lower()
                    ),
                    operational_result_sha256=None,
                    independent_result_sha256=None,
                    accepted_iteration_count=0,
                    rejected_step_count=0,
                    energy_force_evaluation_count=0,
                    accepted_energy_ledger=(),
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
            energy_force_evaluation_count=int(
                value["energy_force_evaluation_count"]
            ),
            accepted_energy_ledger=tuple(float(item) for item in ledger),
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


def _matrix_worker_main(connection: Any) -> None:
    try:
        payload = _canonical_bytes(
            [row.to_dict() for row in _run_case_matrix_in_process()]
        )
        connection.send_bytes(payload)
    finally:
        connection.close()


def _run_supervised_case_matrix(
    *, deadline: float
) -> tuple[ReferenceMinimizationValidationCaseObservation, ...]:
    """Hard-stop a fixed child on deadline, including native-code stalls."""

    remaining = deadline - time.monotonic()
    if remaining <= 0.0:
        return _failure_complete_matrix("runner_wall_time_exhausted")
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    process = context.Process(target=_matrix_worker_main, args=(child,))
    process.start()
    child.close()
    try:
        if not parent.poll(remaining):
            process.terminate()
            process.join(timeout=5.0)
            if process.is_alive():
                process.kill()
                process.join(timeout=5.0)
            return _failure_complete_matrix("runner_wall_time_exhausted")
        try:
            raw = parent.recv_bytes(
                maxlength=(
                    REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_WORKER_OUTPUT_BYTES
                )
            )
        except (EOFError, OSError):
            return _failure_complete_matrix("runner_worker_output_invalid")
    finally:
        parent.close()
        process.join(timeout=5.0)
        if process.is_alive():
            process.terminate()
            process.join(timeout=5.0)
    try:
        payload = json.loads(raw.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _failure_complete_matrix("runner_worker_output_invalid")
    if (
        not isinstance(payload, list)
        or len(payload) != REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_CASES
        or raw != _canonical_bytes(payload)
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
    payload = _canonical_bytes({**projection, "runner_start_record_sha256": record_sha256})
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
    except (OSError, ValueError, ReferenceMinimizationValidationNonceReservationError) as exc:
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
    _require_isolated_python_bootstrap_runtime()
    _require_source_only_python_runtime()
    receipt = require_reference_minimization_validation_execution_environment_receipt_for_runner(
        artifact_output_root,
        nonce,
        expected_receipt_sha256=expected_receipt,
    )
    started = _parse_utc(receipt.started_at_utc, name="environment receipt start")
    now = _utc_now()
    if now < started or now - started > REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_RECEIPT_AGE:
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
    started_at = _format_utc(now)
    deadline = time.monotonic() + REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_WALL_SECONDS
    marker = _persist_runner_start(
        artifact_output_root,
        nonce=nonce,
        environment_receipt_sha256=expected_receipt,
        code_commit_sha=expected_commit,
        runner_source_sha256=source_sha256,
        started_at_utc=started_at,
    )
    case_results = _run_supervised_case_matrix(deadline=deadline)
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
        "production_runner_start_consumed": False,
        "production_validation_execution_authorized": False,
        "production_validation_results_collected": False,
        "result_receipt_writer_implemented": False,
        **_closed_claim_policy(),
    }


def _main_from_canonical_request(raw: bytes) -> int:
    """Fail closed until the next slice adds the result-receipt writer."""

    del raw
    raise ReferenceMinimizationValidationRunnerError(
        "minimization result receipt writer is not implemented"
    )


def main() -> int:
    return _main_from_canonical_request(sys.stdin.buffer.read(1_048_577))


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RUNNER_CONTRACT_SHA256",
    "REFERENCE_MINIMIZATION_VALIDATION_RUNNER_CONTRACT_SCHEMA_ID",
    "REFERENCE_MINIMIZATION_VALIDATION_LOGICAL_RUNNER_ARGV",
    "REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_CASES",
    "REFERENCE_MINIMIZATION_VALIDATION_RUNNER_START_SCHEMA_ID",
    "ReferenceMinimizationValidationCaseObservation",
    "ReferenceMinimizationValidationRunObservation",
    "ReferenceMinimizationValidationRunnerAlreadyStartedError",
    "ReferenceMinimizationValidationRunnerError",
    "reference_minimization_validation_checked_out_code_commit_sha",
    "reference_minimization_validation_runner_contract_decision",
    "reference_minimization_validation_runner_contract_document",
    "reference_minimization_validation_runner_source_sha256",
    "read_reference_minimization_validation_runner_start_record",
    "require_reference_minimization_validation_runner_contract_document",
    "run_bounded_cpu_reference_minimization_validation",
]
