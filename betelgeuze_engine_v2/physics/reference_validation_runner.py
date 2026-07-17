"""Bounded CPU runner for the frozen synthetic validation protocol.

The runner accepts only a freshly reverified execution-environment receipt,
atomically consumes a one-time runner-start marker, verifies the frozen source
binding, and evaluates exactly twenty-seven cases and fifty-nine variants.  It
returns an in-memory failure-inclusive observation.  It does not write a result
receipt, authorize a production run, accept parameter-fitting data, or promote
scientific, benchmark, product, publication, or customer claims.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import time
from typing import Any, Mapping

from .reference_validation_nonce_reservation import (
    ReferenceValidationNonceReservationError,
    _open_secure_reservation_root,
    _validate_reservation_file_stat,
)
from .reference_validation_protocol import (
    FROZEN_CPU_REFERENCE_VALIDATION_PROTOCOL_SHA256,
    CPUReferenceValidationCase,
    CPUReferenceValidationMetric,
    frozen_cpu_reference_validation_protocol,
)
from .reference_validation_receipts import (
    FROZEN_REFERENCE_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256,
)
from .reference_validation_run_start import (
    FROZEN_REFERENCE_VALIDATION_RUN_START_CONTRACT_SHA256,
    REFERENCE_VALIDATION_LOGICAL_RUNNER_ARGV,
    ReferenceValidationExecutionEnvironmentReceipt,
    ReferenceValidationRunStartError,
    require_reference_validation_execution_environment_receipt_for_runner,
)


REFERENCE_VALIDATION_RUNNER_CONTRACT_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_validation_runner_contract/1.0.0"
)
REFERENCE_VALIDATION_RUNNER_START_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_validation_runner_start/1.0.0"
)
REFERENCE_VALIDATION_RUN_OBSERVATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_validation_run_observation/1.0.0"
)
REFERENCE_VALIDATION_RUNNER_CONTRACT_ID = (
    "cpu_reference_validation_bounded_runner/1.0.0"
)
REFERENCE_VALIDATION_RUNNER_CONTRACT_VERSION = "1.0.0"
REFERENCE_VALIDATION_RUNNER_CONTRACT_FROZEN_AT_UTC = "2026-07-17T08:08:00Z"
REFERENCE_VALIDATION_RUNNER_MAX_RECEIPT_AGE = timedelta(minutes=5)
REFERENCE_VALIDATION_RUNNER_MAX_WALL_SECONDS = 120.0
REFERENCE_VALIDATION_RUNNER_MAX_CASES = 27
REFERENCE_VALIDATION_RUNNER_MAX_VARIANTS = 59
REFERENCE_VALIDATION_RUNNER_MAX_START_RECORD_BYTES = 65_536
REFERENCE_VALIDATION_CENTRAL_DIFFERENCE_STEP_ANGSTROM = 1.0e-5

FROZEN_REFERENCE_VALIDATION_RUNNER_CONTRACT_SHA256 = (
    "a3f198edbdeefcd92d5cd30ef2089acce3a289c0ebb6ce17b4544d6292778531"
)

_ROTATION_MATRIX = (
    (0.0, -1.0, 0.0),
    (1.0, 0.0, 0.0),
    (0.0, 0.0, 1.0),
)
_PERMUTATION_NEW_TO_OLD = (3, 1, 0, 2)
_AXIS_INDEX = {"x": 0, "y": 1, "z": 2}
_POST_RUN_BLOCKERS = (
    "production_validation_result_not_collected",
    "result_receipt_writer_not_implemented",
    "independent_result_review_missing",
    "parameter_fitting_not_authorized",
    "minimization_validation_protocol_missing",
    "scientific_validation_missing",
    "product_integration_not_qualified",
)
_CURRENT_BLOCKERS = (
    "independent_scientific_review_missing",
    "signed_independent_scientific_review_attestation_missing",
    "trusted_independent_scientific_reviewer_key_not_provided",
    "signed_execution_authorization_receipt_missing",
    "trusted_authorization_operator_key_not_provided",
    "authorization_nonce_not_atomically_reserved",
    "production_environment_receipt_missing",
    "result_receipt_writer_not_implemented",
    "validation_execution_not_authorized",
    "validation_results_not_collected",
    "parameter_fitting_not_authorized",
    "scientific_validation_missing",
    "product_integration_not_qualified",
)


class ReferenceValidationRunnerError(RuntimeError):
    """The bounded runner preflight, execution, or observation failed."""


class ReferenceValidationRunnerAlreadyStartedError(ReferenceValidationRunnerError):
    """The one-time runner-start path for the authorization nonce exists."""


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
        raise ReferenceValidationRunnerError(
            "runner observation is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ReferenceValidationRunnerError(f"{name} must be a lowercase SHA-256")
    return value


def _require_commit_sha(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 40
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ReferenceValidationRunnerError(
            f"{name} must be a lowercase forty-character commit SHA"
        )
    return value


def _format_utc(value: datetime, *, name: str) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ReferenceValidationRunnerError(f"{name} must be timezone-aware")
    normalized = value.astimezone(timezone.utc)
    if normalized.microsecond:
        raise ReferenceValidationRunnerError(f"{name} must use second resolution")
    return normalized.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_utc(value: object, *, name: str) -> datetime:
    if not isinstance(value, str):
        raise ReferenceValidationRunnerError(f"{name} must be UTC text")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise ReferenceValidationRunnerError(
            f"{name} must use second-resolution UTC"
        ) from exc


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _normalize_dependency_rows(
    rows: Mapping[str, str] | tuple[tuple[str, str], ...],
) -> tuple[tuple[str, str], ...]:
    if isinstance(rows, Mapping):
        raw_rows: tuple[object, ...] = tuple(rows.items())
        canonicalize = True
    elif isinstance(rows, tuple):
        raw_rows = rows
        canonicalize = False
    else:
        raise ReferenceValidationRunnerError(
            "runner dependency rows must be a mapping or canonical tuple"
        )
    normalized_rows: list[tuple[str, str]] = []
    for row in raw_rows:
        if not isinstance(row, tuple) or len(row) != 2:
            raise ReferenceValidationRunnerError(
                "runner dependency rows must contain identity and digest pairs"
            )
        artifact_id, digest = row
        if not isinstance(artifact_id, str) or not isinstance(digest, str):
            raise ReferenceValidationRunnerError(
                "runner dependency rows must contain text identities and digests"
            )
        normalized_rows.append((artifact_id, digest))
    normalized = tuple(
        sorted(normalized_rows) if canonicalize else normalized_rows
    )
    if not normalized or (
        not canonicalize and tuple(sorted(normalized)) != normalized
    ):
        raise ReferenceValidationRunnerError(
            "runner dependency rows must be non-empty and sorted"
        )
    if len({row[0] for row in normalized}) != len(normalized):
        raise ReferenceValidationRunnerError(
            "runner dependency artifact identities must be unique"
        )
    for artifact_id, digest in normalized:
        if (
            not isinstance(artifact_id, str)
            or not artifact_id
            or len(artifact_id) > 200
            or not all(
                character.isascii()
                and (character.isalnum() or character in "._-")
                for character in artifact_id
            )
        ):
            raise ReferenceValidationRunnerError(
                "runner dependency artifact identity is invalid"
            )
        _require_sha256(digest, name=f"runner dependency {artifact_id}")
    return normalized


def reference_validation_runner_source_sha256() -> str:
    """Return the exact regular-file identity used by an authorization receipt."""

    source = Path(__file__)
    if source.is_symlink():
        raise ReferenceValidationRunnerError("runner source must not be a symlink")
    try:
        resolved = source.resolve(strict=True)
        file_stat = resolved.stat()
    except OSError as exc:
        raise ReferenceValidationRunnerError("runner source is unavailable") from exc
    if (
        resolved.name != "reference_validation_runner.py"
        or resolved.parent.name != "physics"
        or resolved.parent.parent.name != "betelgeuze_engine_v2"
        or not stat.S_ISREG(file_stat.st_mode)
        or file_stat.st_nlink != 1
    ):
        raise ReferenceValidationRunnerError(
            "runner source does not satisfy the regular-file policy"
        )
    try:
        return hashlib.sha256(resolved.read_bytes()).hexdigest()
    except OSError as exc:
        raise ReferenceValidationRunnerError("runner source cannot be read") from exc


def _force_array_sha256(values: tuple[tuple[float, float, float], ...]) -> str:
    return _sha256(
        {
            "shape": [len(values), 3],
            "dtype": "float64",
            "unit": "kcal/mol/angstrom",
            "values_hex": [[float(value).hex() for value in row] for row in values],
        }
    )


def _finite(value: object, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReferenceValidationRunnerError(f"{name} must be a real number")
    result = float(value)
    if not math.isfinite(result):
        raise ReferenceValidationRunnerError(f"{name} must be finite")
    return result


@dataclass(frozen=True, slots=True)
class ReferenceValidationMetricObservation:
    metric_id: str
    observed: bool
    value: float | bool | None
    unit: str
    threshold_operator: str
    threshold_value: float
    passed: bool

    def __post_init__(self) -> None:
        if type(self.observed) is not bool or type(self.passed) is not bool:
            raise ReferenceValidationRunnerError(
                "metric observation flags must be booleans"
            )
        if not self.metric_id or not self.unit:
            raise ReferenceValidationRunnerError(
                "metric observation identity and unit must be non-empty"
            )
        _finite(self.threshold_value, name="metric threshold")
        if self.threshold_operator not in {"less_than_or_equal", "equal"}:
            raise ReferenceValidationRunnerError(
                "metric observation threshold operator is invalid"
            )
        if self.observed:
            if isinstance(self.value, bool):
                pass
            else:
                _finite(self.value, name="metric observation value")
        elif self.value is not None or self.passed:
            raise ReferenceValidationRunnerError(
                "missing metric observations cannot contain a value or pass"
            )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "metric_id": self.metric_id,
            "observed": self.observed,
            "unit": self.unit,
            "threshold_operator": self.threshold_operator,
            "threshold_value": self.threshold_value,
            "passed": self.passed,
        }
        if self.observed:
            payload["value"] = self.value
        else:
            payload["error_code"] = "metric_not_observed"
        return payload


@dataclass(frozen=True, slots=True)
class ReferenceValidationVariantObservation:
    ordinal: int
    variant_id: str
    runtime_input_sha256: str
    oracle_input_sha256: str | None
    observed_status: str
    observed_error_code: str | None
    component_energies_kcal_per_mol: tuple[tuple[str, float], ...] = ()
    total_energy_kcal_per_mol: float | None = None
    forces_kcal_per_mol_angstrom: tuple[tuple[float, float, float], ...] = ()
    force_array_sha256: str | None = None
    oracle_total_energy_kcal_per_mol: float | None = None
    oracle_forces_kcal_per_mol_angstrom: tuple[tuple[float, float, float], ...] = ()
    oracle_force_array_sha256: str | None = None

    def __post_init__(self) -> None:
        if type(self.ordinal) is not int or self.ordinal < 0 or not self.variant_id:
            raise ReferenceValidationRunnerError(
                "variant observation ordinal or identity is invalid"
            )
        _require_sha256(self.runtime_input_sha256, name="variant runtime input")
        if self.oracle_input_sha256 is not None:
            _require_sha256(self.oracle_input_sha256, name="variant oracle input")
        if self.observed_status == "success":
            if self.observed_error_code is not None:
                raise ReferenceValidationRunnerError(
                    "successful variant cannot contain an error code"
                )
            if (
                self.total_energy_kcal_per_mol is None
                or not self.component_energies_kcal_per_mol
                or not self.forces_kcal_per_mol_angstrom
                or self.force_array_sha256 is None
                or self.oracle_total_energy_kcal_per_mol is None
                or not self.oracle_forces_kcal_per_mol_angstrom
                or self.oracle_force_array_sha256 is None
            ):
                raise ReferenceValidationRunnerError(
                    "successful variant observation is incomplete"
                )
            _finite(self.total_energy_kcal_per_mol, name="variant total energy")
            _finite(
                self.oracle_total_energy_kcal_per_mol,
                name="variant oracle total energy",
            )
            for name, value in self.component_energies_kcal_per_mol:
                if not name:
                    raise ReferenceValidationRunnerError(
                        "variant component energy identity is empty"
                    )
                _finite(value, name="variant component energy")
            if tuple(sorted(self.component_energies_kcal_per_mol)) != (
                self.component_energies_kcal_per_mol
            ):
                raise ReferenceValidationRunnerError(
                    "variant component energies must be canonical"
                )
            for array_name, array in (
                ("reference", self.forces_kcal_per_mol_angstrom),
                ("oracle", self.oracle_forces_kcal_per_mol_angstrom),
            ):
                if not array or any(len(row) != 3 for row in array):
                    raise ReferenceValidationRunnerError(
                        f"{array_name} force array shape is invalid"
                    )
                for row in array:
                    for value in row:
                        _finite(value, name=f"{array_name} force component")
            if len(self.forces_kcal_per_mol_angstrom) != len(
                self.oracle_forces_kcal_per_mol_angstrom
            ):
                raise ReferenceValidationRunnerError(
                    "reference and oracle force shapes diverged"
                )
            if self.force_array_sha256 != _force_array_sha256(
                self.forces_kcal_per_mol_angstrom
            ) or self.oracle_force_array_sha256 != _force_array_sha256(
                self.oracle_forces_kcal_per_mol_angstrom
            ):
                raise ReferenceValidationRunnerError(
                    "variant force array identity is cross-wired"
                )
        elif self.observed_status in {
            "fail_closed",
            "unexpected_error",
            "unexpected_success",
            "time_budget_exhausted",
        }:
            if not self.observed_error_code:
                raise ReferenceValidationRunnerError(
                    "non-success variant requires an error code"
                )
            if any(
                (
                    self.component_energies_kcal_per_mol,
                    self.total_energy_kcal_per_mol is not None,
                    self.forces_kcal_per_mol_angstrom,
                    self.force_array_sha256 is not None,
                    self.oracle_total_energy_kcal_per_mol is not None,
                    self.oracle_forces_kcal_per_mol_angstrom,
                    self.oracle_force_array_sha256 is not None,
                )
            ):
                raise ReferenceValidationRunnerError(
                    "non-success variant cannot retain numeric results"
                )
        else:
            raise ReferenceValidationRunnerError(
                "variant observation status is invalid"
            )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ordinal": self.ordinal,
            "variant_id": self.variant_id,
            "runtime_input_sha256": self.runtime_input_sha256,
            "oracle_input_sha256": self.oracle_input_sha256,
            "observed_status": self.observed_status,
            "observed_error_code": self.observed_error_code,
        }
        if self.observed_status == "success":
            payload.update(
                {
                    "component_energy_values_and_units": [
                        {
                            "name": name,
                            "value": value,
                            "unit": "kcal/mol",
                        }
                        for name, value in self.component_energies_kcal_per_mol
                    ],
                    "total_energy_value": self.total_energy_kcal_per_mol,
                    "total_energy_unit": "kcal/mol",
                    "force_array_shape": [
                        len(self.forces_kcal_per_mol_angstrom),
                        3,
                    ],
                    "force_array_dtype": "float64",
                    "force_array_unit": "kcal/mol/angstrom",
                    "force_array_sha256": self.force_array_sha256,
                    "force_array_values": [
                        list(row) for row in self.forces_kcal_per_mol_angstrom
                    ],
                    "oracle_total_energy_value": (
                        self.oracle_total_energy_kcal_per_mol
                    ),
                    "oracle_total_energy_unit": "kcal/mol",
                    "oracle_force_array_sha256": self.oracle_force_array_sha256,
                    "oracle_force_array_values": [
                        list(row)
                        for row in self.oracle_forces_kcal_per_mol_angstrom
                    ],
                }
            )
        return payload


@dataclass(frozen=True, slots=True)
class ReferenceValidationCaseObservation:
    ordinal: int
    case_id: str
    case_input_sha256: str
    materialization_sha256: str
    expected_outcome: str
    observed_status: str
    expected_error_code: str | None
    observed_error_code: str | None
    variant_results: tuple[ReferenceValidationVariantObservation, ...]
    metric_values: tuple[ReferenceValidationMetricObservation, ...]
    case_passed: bool

    def __post_init__(self) -> None:
        if type(self.case_passed) is not bool:
            raise ReferenceValidationRunnerError("case pass flag must be boolean")
        if type(self.ordinal) is not int or self.ordinal < 0 or not self.case_id:
            raise ReferenceValidationRunnerError(
                "case observation ordinal or identity is invalid"
            )
        _require_sha256(self.case_input_sha256, name="case input")
        _require_sha256(self.materialization_sha256, name="case materialization")
        if not self.variant_results:
            raise ReferenceValidationRunnerError(
                "case observation must retain every variant row"
            )
        if tuple(row.ordinal for row in self.variant_results) != tuple(
            range(len(self.variant_results))
        ):
            raise ReferenceValidationRunnerError(
                "case variant observation order is invalid"
            )
        if len({row.variant_id for row in self.variant_results}) != len(
            self.variant_results
        ):
            raise ReferenceValidationRunnerError(
                "case variant observation identities are not unique"
            )
        if len({row.metric_id for row in self.metric_values}) != len(
            self.metric_values
        ):
            raise ReferenceValidationRunnerError(
                "case metric observation identities are not unique"
            )
        if self.expected_outcome == "pass":
            if self.expected_error_code is not None or not self.metric_values:
                raise ReferenceValidationRunnerError(
                    "pass case expectation is incomplete"
                )
        elif self.expected_outcome == "fail_closed":
            if not self.expected_error_code or self.metric_values:
                raise ReferenceValidationRunnerError(
                    "fail-closed case expectation is incomplete"
                )
        else:
            raise ReferenceValidationRunnerError(
                "case expected outcome is invalid"
            )
        if self.observed_status not in {
            "metrics_passed",
            "metric_threshold_failed",
            "fail_closed_as_expected",
            "unexpected_success",
            "unexpected_error",
            "time_budget_exhausted",
        }:
            raise ReferenceValidationRunnerError(
                "case observation status is invalid"
            )
        if self.case_passed != (
            self.observed_status in {"metrics_passed", "fail_closed_as_expected"}
        ):
            raise ReferenceValidationRunnerError(
                "case pass flag and observed status diverged"
            )
        if self.observed_status in {"metrics_passed", "metric_threshold_failed"}:
            if self.observed_error_code is not None:
                raise ReferenceValidationRunnerError(
                    "metric case cannot contain an observed error"
                )
        elif not self.observed_error_code:
            raise ReferenceValidationRunnerError(
                "non-metric case requires an observed error"
            )
        if (
            self.observed_status == "fail_closed_as_expected"
            and self.observed_error_code != self.expected_error_code
        ):
            raise ReferenceValidationRunnerError(
                "fail-closed case error does not match its expectation"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "case_id": self.case_id,
            "case_input_sha256": self.case_input_sha256,
            "materialization_sha256": self.materialization_sha256,
            "expected_outcome": self.expected_outcome,
            "observed_status": self.observed_status,
            "expected_error_code": self.expected_error_code,
            "observed_error_code": self.observed_error_code,
            "variant_results": [row.to_dict() for row in self.variant_results],
            "metric_values": [row.to_dict() for row in self.metric_values],
            "case_passed": self.case_passed,
        }


@dataclass(frozen=True, slots=True)
class ReferenceValidationRunObservation:
    runner_start_record_sha256: str
    execution_environment_receipt_sha256: str
    environment_fingerprint_sha256: str
    authorization_receipt_sha256: str
    authorization_nonce_sha256: str
    code_commit_sha: str
    runner_source_sha256: str
    dependency_artifact_sha256_rows: tuple[tuple[str, str], ...]
    command_argv: tuple[str, ...]
    seed: int
    started_at_utc: str
    completed_at_utc: str
    case_results: tuple[ReferenceValidationCaseObservation, ...]
    blockers: tuple[str, ...] = _POST_RUN_BLOCKERS

    def __post_init__(self) -> None:
        for name, value in (
            ("runner start record", self.runner_start_record_sha256),
            ("environment receipt", self.execution_environment_receipt_sha256),
            ("environment fingerprint", self.environment_fingerprint_sha256),
            ("authorization receipt", self.authorization_receipt_sha256),
            ("authorization nonce", self.authorization_nonce_sha256),
            ("runner source", self.runner_source_sha256),
        ):
            _require_sha256(value, name=name)
        _require_commit_sha(self.code_commit_sha, name="run observation code commit")
        if self.command_argv != REFERENCE_VALIDATION_LOGICAL_RUNNER_ARGV:
            raise ReferenceValidationRunnerError("run observation argv drifted")
        if type(self.seed) is not int or not 0 <= self.seed <= 2**63 - 1:
            raise ReferenceValidationRunnerError("run observation seed is invalid")
        if _normalize_dependency_rows(self.dependency_artifact_sha256_rows) != (
            self.dependency_artifact_sha256_rows
        ):
            raise ReferenceValidationRunnerError(
                "run observation dependency rows drifted"
            )
        started = _parse_utc(self.started_at_utc, name="run started_at")
        completed = _parse_utc(self.completed_at_utc, name="run completed_at")
        if completed < started:
            raise ReferenceValidationRunnerError(
                "run completion precedes its start"
            )
        if len(self.case_results) != REFERENCE_VALIDATION_RUNNER_MAX_CASES:
            raise ReferenceValidationRunnerError(
                "run observation must retain all twenty-seven cases"
            )
        if tuple(row.ordinal for row in self.case_results) != tuple(
            range(REFERENCE_VALIDATION_RUNNER_MAX_CASES)
        ):
            raise ReferenceValidationRunnerError(
                "run observation case order drifted"
            )
        protocol_cases = frozen_cpu_reference_validation_protocol().cases
        expected_case_rows = tuple(
            (
                row.case_id,
                row.input_sha256,
                row.expected_outcome,
                row.expected_error_code,
            )
            for row in protocol_cases
        )
        observed_case_rows = tuple(
            (
                row.case_id,
                row.case_input_sha256,
                row.expected_outcome,
                row.expected_error_code,
            )
            for row in self.case_results
        )
        if observed_case_rows != expected_case_rows:
            raise ReferenceValidationRunnerError(
                "run observation cases do not match the frozen protocol"
            )
        if sum(len(row.variant_results) for row in self.case_results) != (
            REFERENCE_VALIDATION_RUNNER_MAX_VARIANTS
        ):
            raise ReferenceValidationRunnerError(
                "run observation must retain all fifty-nine variants"
            )
        if self.blockers != _POST_RUN_BLOCKERS:
            raise ReferenceValidationRunnerError(
                "run observation downstream blockers drifted"
            )

    @property
    def observation_sha256(self) -> str:
        return _sha256(self.projection())

    def projection(self) -> dict[str, Any]:
        passed = sum(row.case_passed for row in self.case_results)
        return {
            "schema_id": REFERENCE_VALIDATION_RUN_OBSERVATION_SCHEMA_ID,
            "runner_contract_sha256": (
                FROZEN_REFERENCE_VALIDATION_RUNNER_CONTRACT_SHA256
            ),
            "result_contract_sha256": (
                FROZEN_REFERENCE_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256
            ),
            "protocol_sha256": FROZEN_CPU_REFERENCE_VALIDATION_PROTOCOL_SHA256,
            "run_start_contract_sha256": (
                FROZEN_REFERENCE_VALIDATION_RUN_START_CONTRACT_SHA256
            ),
            "runner_start_record_sha256": self.runner_start_record_sha256,
            "execution_environment_receipt_sha256": (
                self.execution_environment_receipt_sha256
            ),
            "environment_fingerprint_sha256": self.environment_fingerprint_sha256,
            "authorization_receipt_sha256": self.authorization_receipt_sha256,
            "authorization_nonce_sha256": self.authorization_nonce_sha256,
            "code_commit_sha": self.code_commit_sha,
            "runner_source_sha256": self.runner_source_sha256,
            "dependency_artifact_sha256_rows": [
                {"artifact_id": artifact_id, "sha256": digest}
                for artifact_id, digest in self.dependency_artifact_sha256_rows
            ],
            "command_argv": list(self.command_argv),
            "seed": self.seed,
            "started_at_utc": self.started_at_utc,
            "completed_at_utc": self.completed_at_utc,
            "case_results": [row.to_dict() for row in self.case_results],
            "coverage_summary": {
                "case_count": len(self.case_results),
                "variant_count": sum(
                    len(row.variant_results) for row in self.case_results
                ),
                "case_pass_count": passed,
                "case_failure_count": len(self.case_results) - passed,
                "all_cases_retained": True,
                "all_variants_retained": True,
                "skipped_cases": 0,
            },
            "in_memory_observation_created": True,
            "production_validation_results_collected": False,
            "result_receipt_written": False,
            "parameter_fitting_proposal_authorized": False,
            "parameter_fitting_authorized": False,
            "scientifically_validated": False,
            "claim_safe": False,
            "blockers": list(self.blockers),
        }

    def to_dict(self) -> dict[str, Any]:
        payload = self.projection()
        payload["observation_sha256"] = self.observation_sha256
        return payload


def _closed_claim_policy() -> dict[str, bool]:
    return {
        "bounded_validation_runner_implemented": True,
        "production_validation_execution_authorized": False,
        "production_validation_results_collected": False,
        "result_receipt_writer_implemented": False,
        "force_or_energy_validated": False,
        "parameter_fitting_proposal_authorized": False,
        "parameter_fitting_authorized": False,
        "scientifically_validated": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
    }


def _contract_projection() -> dict[str, Any]:
    return {
        "schema_id": REFERENCE_VALIDATION_RUNNER_CONTRACT_SCHEMA_ID,
        "contract_id": REFERENCE_VALIDATION_RUNNER_CONTRACT_ID,
        "contract_version": REFERENCE_VALIDATION_RUNNER_CONTRACT_VERSION,
        "frozen_at_utc": REFERENCE_VALIDATION_RUNNER_CONTRACT_FROZEN_AT_UTC,
        "purpose": {
            "lane": "synthetic_implementation_mathematics_only",
            "bounded_runner_primitive_only": True,
            "production_execution_performed": False,
            "production_results_collected": False,
            "result_receipt_written": False,
        },
        "preflight": {
            "persisted_environment_receipt_reread_required": True,
            "live_environment_fingerprint_reverification_required": True,
            "maximum_environment_receipt_age_seconds": int(
                REFERENCE_VALIDATION_RUNNER_MAX_RECEIPT_AGE.total_seconds()
            ),
            "exact_code_runner_dependency_identity_required": True,
            "frozen_artifact_binding_reverification_required": True,
            "one_time_runner_start_marker_required": True,
            "duplicate_runner_start_fails_closed": True,
            "release_or_delete_api_provided": False,
        },
        "bounds": {
            "device": "cpu",
            "coordinate_dtype": "float64",
            "case_count": REFERENCE_VALIDATION_RUNNER_MAX_CASES,
            "variant_count": REFERENCE_VALIDATION_RUNNER_MAX_VARIANTS,
            "maximum_wall_seconds": REFERENCE_VALIDATION_RUNNER_MAX_WALL_SECONDS,
            "case_order_matches_protocol": True,
            "variant_order_matches_materialization_manifest": True,
            "all_failure_rows_retained": True,
            "skipped_cases_allowed": False,
            "network_access_allowed": False,
            "subprocess_execution_allowed": False,
        },
        "observation": {
            "in_memory_only": True,
            "success_variant_energy_force_and_oracle_values_retained": True,
            "failure_variant_numeric_values_retained": False,
            "all_predefined_metrics_evaluated_or_marked_missing": True,
            "failed_metrics_and_cases_retained": True,
            "canonical_observation_sha256_required": True,
            "result_receipt_writer_implemented": False,
        },
        "current_state": {
            "bounded_validation_runner_implemented": True,
            "production_environment_receipt_present": False,
            "production_validation_execution_authorized": False,
            "production_validation_results_collected": False,
            "production_result_receipt_present": False,
        },
        "claim_policy": _closed_claim_policy(),
        "blockers": list(_CURRENT_BLOCKERS),
    }


def reference_validation_runner_contract_document() -> dict[str, Any]:
    document = _contract_projection()
    document["contract_sha256"] = _sha256(document)
    if document["contract_sha256"] != (
        FROZEN_REFERENCE_VALIDATION_RUNNER_CONTRACT_SHA256
    ):
        raise ReferenceValidationRunnerError(
            "frozen validation runner contract SHA-256 drifted"
        )
    return document


def require_reference_validation_runner_contract_document(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ReferenceValidationRunnerError(
            "validation runner contract document must be a mapping"
        )
    observed = json.loads(_canonical_bytes(dict(payload)).decode("ascii"))
    expected = reference_validation_runner_contract_document()
    if observed != expected:
        raise ReferenceValidationRunnerError(
            "validation runner contract document does not match the frozen record"
        )
    return observed


def _runner_start_projection(
    receipt: ReferenceValidationExecutionEnvironmentReceipt,
    *,
    runner_source_sha256: str,
    started_at_utc: str,
) -> dict[str, Any]:
    return {
        "schema_id": REFERENCE_VALIDATION_RUNNER_START_SCHEMA_ID,
        "runner_contract_sha256": FROZEN_REFERENCE_VALIDATION_RUNNER_CONTRACT_SHA256,
        "environment_receipt_sha256": receipt.receipt_sha256,
        "environment_fingerprint_sha256": receipt.environment_fingerprint_sha256,
        "authorization_receipt_sha256": receipt.authorization_receipt_sha256,
        "authorization_nonce_sha256": receipt.authorization_nonce_sha256,
        "code_commit_sha": receipt.code_commit_sha,
        "runner_source_sha256": runner_source_sha256,
        "dependency_artifact_sha256_rows": [
            {"artifact_id": artifact_id, "sha256": digest}
            for artifact_id, digest in receipt.dependency_artifact_sha256_rows
        ],
        "started_at_utc": started_at_utc,
        "one_time_runner_start_consumed": True,
        "result_values_present": False,
        "result_receipt_written": False,
        "parameter_fitting_authorized": False,
        "scientifically_validated": False,
        "claim_safe": False,
    }


def _persist_runner_start(
    artifact_output_root: str | os.PathLike[str],
    receipt: ReferenceValidationExecutionEnvironmentReceipt,
    *,
    runner_source_sha256: str,
    started_at_utc: str,
) -> str:
    projection = _runner_start_projection(
        receipt,
        runner_source_sha256=runner_source_sha256,
        started_at_utc=started_at_utc,
    )
    payload = dict(projection)
    payload["runner_start_record_sha256"] = _sha256(projection)
    encoded = _canonical_bytes(payload) + b"\n"
    if len(encoded) > REFERENCE_VALIDATION_RUNNER_MAX_START_RECORD_BYTES:
        raise ReferenceValidationRunnerError("runner-start record is too large")
    try:
        root_fd = _open_secure_reservation_root(artifact_output_root)
    except ReferenceValidationNonceReservationError as exc:
        raise ReferenceValidationRunnerError(
            "runner artifact root does not satisfy the private POSIX policy"
        ) from exc
    filename = f"{receipt.authorization_nonce_sha256}.runner-start.json"
    descriptor: int | None = None
    try:
        try:
            descriptor = os.open(
                filename,
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | os.O_NOFOLLOW
                | os.O_CLOEXEC,
                0o600,
                dir_fd=root_fd,
            )
        except FileExistsError as exc:
            raise ReferenceValidationRunnerAlreadyStartedError(
                "bounded validation runner already started for this nonce"
            ) from exc
        except (OSError, ValueError) as exc:
            raise ReferenceValidationRunnerError(
                "runner-start record cannot be created securely"
            ) from exc
        try:
            _validate_reservation_file_stat(os.fstat(descriptor))
            remaining = memoryview(encoded)
            while remaining:
                written = os.write(descriptor, remaining)
                if written <= 0:
                    raise OSError("runner-start write made no progress")
                remaining = remaining[written:]
            os.fsync(descriptor)
        except Exception as exc:
            raise ReferenceValidationRunnerError(
                "runner-start persistence failed; the path remains consumed"
            ) from exc
        os.close(descriptor)
        descriptor = None
        try:
            os.fsync(root_fd)
        except OSError as exc:
            raise ReferenceValidationRunnerError(
                "runner-start durability failed; the path remains consumed"
            ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(root_fd)
    return payload["runner_start_record_sha256"]


def read_reference_validation_runner_start_record(
    artifact_output_root: str | os.PathLike[str],
    authorization_nonce_sha256: str,
    *,
    expected_record_sha256: str,
    expected_environment_receipt_sha256: str,
    expected_runner_source_sha256: str,
) -> dict[str, Any]:
    """Read and verify the consumed runner-start marker without releasing it."""

    nonce = _require_sha256(
        authorization_nonce_sha256,
        name="runner-start authorization nonce",
    )
    expected_record = _require_sha256(
        expected_record_sha256,
        name="expected runner-start record",
    )
    expected_environment = _require_sha256(
        expected_environment_receipt_sha256,
        name="expected runner-start environment receipt",
    )
    expected_source = _require_sha256(
        expected_runner_source_sha256,
        name="expected runner-start source",
    )
    try:
        root_fd = _open_secure_reservation_root(artifact_output_root)
    except ReferenceValidationNonceReservationError as exc:
        raise ReferenceValidationRunnerError(
            "runner-start artifact root does not satisfy the private POSIX policy"
        ) from exc
    descriptor: int | None = None
    try:
        try:
            descriptor = os.open(
                f"{nonce}.runner-start.json",
                os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=root_fd,
            )
            _validate_reservation_file_stat(os.fstat(descriptor))
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = os.read(descriptor, 8192)
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > REFERENCE_VALIDATION_RUNNER_MAX_START_RECORD_BYTES:
                    raise ReferenceValidationRunnerError(
                        "runner-start record exceeds the size limit"
                    )
        except (OSError, ValueError, ReferenceValidationNonceReservationError) as exc:
            raise ReferenceValidationRunnerError(
                "runner-start record cannot be read securely"
            ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(root_fd)
    raw = b"".join(chunks)

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ReferenceValidationRunnerError(
                    "runner-start record contains a duplicate JSON key"
                )
            result[key] = value
        return result

    try:
        if not raw.endswith(b"\n"):
            raise ReferenceValidationRunnerError(
                "runner-start record is not canonical JSON"
            )
        payload = json.loads(
            raw[:-1].decode("ascii"),
            object_pairs_hook=reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReferenceValidationRunnerError(
            "runner-start record is not canonical JSON"
        ) from exc
    if not isinstance(payload, dict) or _canonical_bytes(payload) + b"\n" != raw:
        raise ReferenceValidationRunnerError(
            "runner-start record is not canonical JSON"
        )
    observed_record = payload.pop("runner_start_record_sha256", None)
    if (
        observed_record != _sha256(payload)
        or observed_record != expected_record
    ):
        raise ReferenceValidationRunnerError(
            "runner-start record identity is cross-wired"
        )
    expected_keys = {
        "schema_id",
        "runner_contract_sha256",
        "environment_receipt_sha256",
        "environment_fingerprint_sha256",
        "authorization_receipt_sha256",
        "authorization_nonce_sha256",
        "code_commit_sha",
        "runner_source_sha256",
        "dependency_artifact_sha256_rows",
        "started_at_utc",
        "one_time_runner_start_consumed",
        "result_values_present",
        "result_receipt_written",
        "parameter_fitting_authorized",
        "scientifically_validated",
        "claim_safe",
    }
    if set(payload) != expected_keys:
        raise ReferenceValidationRunnerError(
            "runner-start record fields are invalid"
        )
    if (
        payload["schema_id"] != REFERENCE_VALIDATION_RUNNER_START_SCHEMA_ID
        or payload["runner_contract_sha256"]
        != FROZEN_REFERENCE_VALIDATION_RUNNER_CONTRACT_SHA256
        or payload["environment_receipt_sha256"] != expected_environment
        or payload["authorization_nonce_sha256"] != nonce
        or payload["runner_source_sha256"] != expected_source
        or payload["one_time_runner_start_consumed"] is not True
        or any(
            payload[name] is not False
            for name in (
                "result_values_present",
                "result_receipt_written",
                "parameter_fitting_authorized",
                "scientifically_validated",
                "claim_safe",
            )
        )
    ):
        raise ReferenceValidationRunnerError(
            "runner-start record does not match the bounded runner contract"
        )
    result = dict(payload)
    result["runner_start_record_sha256"] = observed_record
    return result


def _normalize_physics_error(error: Exception) -> str:
    message = str(error)
    prefix = "reference parameter applicability failed: "
    if message.startswith(prefix):
        first = message[len(prefix) :].split(", ", 1)[0]
        if first:
            return first
    exact = {
        "nonbonded pair is below minimum_pair_distance_angstrom": (
            "nonbonded_pair_below_minimum_pair_distance_angstrom"
        ),
        "angle contains a zero-length vector": "angle_zero_length_vector",
        "torsion is undefined for collinear atoms": (
            "torsion_undefined_for_collinear_atoms"
        ),
    }
    return exact.get(message, "unclassified_reference_physics_error")


def _failure_variant(
    ordinal: int,
    variant: Any,
    *,
    status: str,
    error_code: str,
) -> ReferenceValidationVariantObservation:
    return ReferenceValidationVariantObservation(
        ordinal=ordinal,
        variant_id=variant.variant_id,
        runtime_input_sha256=variant.runtime_input_sha256,
        oracle_input_sha256=(
            None if variant.oracle_input is None else variant.oracle_input.input_sha256
        ),
        observed_status=status,
        observed_error_code=error_code,
    )


def _success_variant(
    ordinal: int,
    variant: Any,
    evaluation: Any,
    oracle: Any,
) -> ReferenceValidationVariantObservation:
    forces = tuple(
        tuple(float(value) for value in row)
        for row in evaluation.term.forces[0].detach().cpu().tolist()
    )
    oracle_forces = tuple(
        tuple(float(value) for value in row)
        for row in oracle.forces_kcal_per_mol_angstrom
    )
    components = tuple(
        sorted(
            (
                name,
                float(value[0].detach().cpu().item()),
            )
            for name, value in evaluation.component_energies.items()
        )
    )
    return ReferenceValidationVariantObservation(
        ordinal=ordinal,
        variant_id=variant.variant_id,
        runtime_input_sha256=variant.runtime_input_sha256,
        oracle_input_sha256=variant.oracle_input.input_sha256,
        observed_status="success",
        observed_error_code=None,
        component_energies_kcal_per_mol=components,
        total_energy_kcal_per_mol=float(
            evaluation.term.energy[0].detach().cpu().item()
        ),
        forces_kcal_per_mol_angstrom=forces,
        force_array_sha256=_force_array_sha256(forces),
        oracle_total_energy_kcal_per_mol=float(oracle.total_energy_kcal_per_mol),
        oracle_forces_kcal_per_mol_angstrom=oracle_forces,
        oracle_force_array_sha256=_force_array_sha256(oracle_forces),
    )


def _max_abs(first: list[float], second: list[float]) -> float:
    if len(first) != len(second) or not first:
        raise ReferenceValidationRunnerError("metric arrays are empty or misaligned")
    return max(abs(a - b) for a, b in zip(first, second))


def _max_rel(
    observed: list[float],
    independent_reference: list[float],
) -> float:
    if len(observed) != len(independent_reference) or not observed:
        raise ReferenceValidationRunnerError("relative metric arrays are misaligned")
    return max(
        abs(value - reference) / max(abs(reference), 1.0e-12)
        for value, reference in zip(observed, independent_reference)
    )


def _flatten_force(
    values: tuple[tuple[float, float, float], ...],
) -> list[float]:
    return [value for row in values for value in row]


def _success_map(
    rows: tuple[ReferenceValidationVariantObservation, ...],
) -> dict[str, ReferenceValidationVariantObservation]:
    return {row.variant_id: row for row in rows if row.observed_status == "success"}


def _oracle_metric_values(
    rows: tuple[ReferenceValidationVariantObservation, ...],
) -> dict[str, float]:
    successes = tuple(row for row in rows if row.observed_status == "success")
    if not successes:
        return {}
    energies = [float(row.total_energy_kcal_per_mol) for row in successes]
    oracle_energies = [
        float(row.oracle_total_energy_kcal_per_mol) for row in successes
    ]
    forces = [value for row in successes for value in _flatten_force(row.forces_kcal_per_mol_angstrom)]
    oracle_forces = [
        value
        for row in successes
        for value in _flatten_force(row.oracle_forces_kcal_per_mol_angstrom)
    ]
    return {
        "energy_oracle_max_abs_error": _max_abs(energies, oracle_energies),
        "energy_oracle_max_rel_error": _max_rel(energies, oracle_energies),
        "force_oracle_max_component_abs_error": _max_abs(forces, oracle_forces),
        "force_oracle_max_component_rel_error": _max_rel(forces, oracle_forces),
    }


def _net_force_norm(row: ReferenceValidationVariantObservation) -> float:
    totals = [
        sum(atom[axis] for atom in row.forces_kcal_per_mol_angstrom)
        for axis in range(3)
    ]
    return math.sqrt(sum(value * value for value in totals))


def _case_metric_values(
    case: CPUReferenceValidationCase,
    rows: tuple[ReferenceValidationVariantObservation, ...],
) -> dict[str, float | bool]:
    values: dict[str, float | bool] = _oracle_metric_values(rows)
    by_id = _success_map(rows)
    if case.case_id == "quintic_switch_window_and_cutoff" and len(by_id) == 3:
        values["switch_cutoff_energy_abs"] = max(
            abs(float(row.total_energy_kcal_per_mol)) for row in by_id.values()
        )
        values["switch_cutoff_force_max_abs"] = max(
            abs(value)
            for row in by_id.values()
            for value in _flatten_force(row.forces_kcal_per_mol_angstrom)
        )
    elif case.case_id == "orthorhombic_minimum_image" and len(by_id) == 2:
        periodic = by_id["periodic-minimum-image"]
        direct = by_id["direct-equivalent"]
        values["minimum_image_energy_abs_error"] = abs(
            float(periodic.total_energy_kcal_per_mol)
            - float(direct.total_energy_kcal_per_mol)
        )
        values["minimum_image_force_max_abs_error"] = _max_abs(
            _flatten_force(periodic.forces_kcal_per_mol_angstrom),
            _flatten_force(direct.forces_kcal_per_mol_angstrom),
        )
    elif case.case_id == "full_five_term_composition" and by_id:
        values["net_force_norm"] = max(_net_force_norm(row) for row in by_id.values())
    elif case.case_id == "full_force_central_difference" and len(by_id) == 25:
        baseline = by_id["baseline"]
        numerical: list[float] = []
        reference: list[float] = []
        for atom_index, force_row in enumerate(
            baseline.forces_kcal_per_mol_angstrom
        ):
            for axis_name, axis in _AXIS_INDEX.items():
                minus = by_id[f"atom-{atom_index}-{axis_name}-minus"]
                plus = by_id[f"atom-{atom_index}-{axis_name}-plus"]
                numerical_force = -(
                    float(plus.total_energy_kcal_per_mol)
                    - float(minus.total_energy_kcal_per_mol)
                ) / (2.0 * REFERENCE_VALIDATION_CENTRAL_DIFFERENCE_STEP_ANGSTROM)
                numerical.append(numerical_force)
                reference.append(force_row[axis])
        values["finite_difference_force_max_abs_error"] = _max_abs(
            reference,
            numerical,
        )
        values["finite_difference_force_max_rel_error"] = _max_rel(
            reference,
            numerical,
        )
    elif case.case_id == "rigid_translation_invariance" and len(by_id) == 2:
        baseline = by_id["baseline"]
        translated = by_id["translated"]
        values["translation_energy_abs_drift"] = abs(
            float(baseline.total_energy_kcal_per_mol)
            - float(translated.total_energy_kcal_per_mol)
        )
        values["translation_force_max_abs_drift"] = _max_abs(
            _flatten_force(baseline.forces_kcal_per_mol_angstrom),
            _flatten_force(translated.forces_kcal_per_mol_angstrom),
        )
        values["net_force_norm"] = max(
            _net_force_norm(baseline),
            _net_force_norm(translated),
        )
    elif case.case_id == "rigid_rotation_invariance" and len(by_id) == 2:
        baseline = by_id["baseline"]
        rotated = by_id["rotated"]
        covariant = [
            sum(_ROTATION_MATRIX[axis][column] * row[column] for column in range(3))
            for row in baseline.forces_kcal_per_mol_angstrom
            for axis in range(3)
        ]
        values["rotation_energy_abs_drift"] = abs(
            float(baseline.total_energy_kcal_per_mol)
            - float(rotated.total_energy_kcal_per_mol)
        )
        values["rotation_force_covariance_max_abs_error"] = _max_abs(
            _flatten_force(rotated.forces_kcal_per_mol_angstrom),
            covariant,
        )
    elif case.case_id == "atom_permutation_equivariance" and len(by_id) == 2:
        baseline = by_id["baseline"]
        permuted = by_id["permuted"]
        expected = [
            value
            for old_index in _PERMUTATION_NEW_TO_OLD
            for value in baseline.forces_kcal_per_mol_angstrom[old_index]
        ]
        values["permutation_energy_abs_drift"] = abs(
            float(baseline.total_energy_kcal_per_mol)
            - float(permuted.total_energy_kcal_per_mol)
        )
        values["permutation_force_equivariance_max_abs_error"] = _max_abs(
            _flatten_force(permuted.forces_kcal_per_mol_angstrom),
            expected,
        )
    elif case.case_id == "same_environment_repeat_determinism" and len(by_id) == 3:
        ordered = [by_id[f"repeat-{index}"] for index in (1, 2, 3)]
        values["repeat_energy_bitwise_equal"] = len(
            {float(row.total_energy_kcal_per_mol).hex() for row in ordered}
        ) == 1
        values["repeat_force_bitwise_equal"] = len(
            {
                tuple(value.hex() for value in _flatten_force(row.forces_kcal_per_mol_angstrom))
                for row in ordered
            }
        ) == 1
    return values


def _metric_observations(
    case: CPUReferenceValidationCase,
    rows: tuple[ReferenceValidationVariantObservation, ...],
    metric_map: Mapping[str, CPUReferenceValidationMetric],
) -> tuple[ReferenceValidationMetricObservation, ...]:
    values = _case_metric_values(case, rows)
    observations: list[ReferenceValidationMetricObservation] = []
    for metric_id in case.required_metric_ids:
        metric = metric_map[metric_id]
        value = values.get(metric_id)
        if value is None:
            observations.append(
                ReferenceValidationMetricObservation(
                    metric_id=metric_id,
                    observed=False,
                    value=None,
                    unit=metric.unit,
                    threshold_operator=metric.threshold_operator,
                    threshold_value=metric.threshold_value,
                    passed=False,
                )
            )
            continue
        if metric.threshold_operator == "equal":
            passed = isinstance(value, bool) and value == bool(metric.threshold_value)
        else:
            passed = not isinstance(value, bool) and float(value) <= metric.threshold_value
        observations.append(
            ReferenceValidationMetricObservation(
                metric_id=metric_id,
                observed=True,
                value=value,
                unit=metric.unit,
                threshold_operator=metric.threshold_operator,
                threshold_value=metric.threshold_value,
                passed=passed,
            )
        )
    return tuple(observations)


def _evaluate_case(
    ordinal: int,
    case: CPUReferenceValidationCase,
    materialized: Any,
    *,
    metric_map: Mapping[str, CPUReferenceValidationMetric],
    deadline: float,
    evaluate_reference_force_field: Any,
    reference_error_type: type[Exception],
    evaluate_independent_analytic_oracle: Any,
) -> ReferenceValidationCaseObservation:
    rows: list[ReferenceValidationVariantObservation] = []
    for variant_ordinal, variant in enumerate(materialized.variants):
        if time.monotonic() > deadline:
            rows.append(
                _failure_variant(
                    variant_ordinal,
                    variant,
                    status="time_budget_exhausted",
                    error_code="runner_time_budget_exhausted",
                )
            )
            continue
        try:
            evaluation = evaluate_reference_force_field(
                variant.system,
                variant.neighbors,
                variant.parameters,
            )
        except reference_error_type as exc:
            status = (
                "fail_closed"
                if case.expected_outcome == "fail_closed"
                else "unexpected_error"
            )
            rows.append(
                _failure_variant(
                    variant_ordinal,
                    variant,
                    status=status,
                    error_code=_normalize_physics_error(exc),
                )
            )
            continue
        except Exception:
            rows.append(
                _failure_variant(
                    variant_ordinal,
                    variant,
                    status="unexpected_error",
                    error_code="unexpected_reference_evaluator_error",
                )
            )
            continue
        if case.expected_outcome == "fail_closed":
            rows.append(
                _failure_variant(
                    variant_ordinal,
                    variant,
                    status="unexpected_success",
                    error_code="expected_fail_closed_variant_executed",
                )
            )
            continue
        try:
            oracle = evaluate_independent_analytic_oracle(variant.oracle_input)
            rows.append(_success_variant(variant_ordinal, variant, evaluation, oracle))
        except Exception:
            rows.append(
                _failure_variant(
                    variant_ordinal,
                    variant,
                    status="unexpected_error",
                    error_code="unexpected_independent_oracle_error",
                )
            )
    variant_rows = tuple(rows)
    if case.expected_outcome == "fail_closed":
        error_codes = {row.observed_error_code for row in variant_rows}
        expected = (
            all(row.observed_status == "fail_closed" for row in variant_rows)
            and error_codes == {case.expected_error_code}
        )
        if expected:
            status = "fail_closed_as_expected"
            observed_error = case.expected_error_code
        elif any(row.observed_status == "time_budget_exhausted" for row in variant_rows):
            status = "time_budget_exhausted"
            observed_error = "runner_time_budget_exhausted"
        elif any(row.observed_status == "unexpected_success" for row in variant_rows):
            status = "unexpected_success"
            observed_error = "expected_fail_closed_variant_executed"
        else:
            status = "unexpected_error"
            observed_error = next(iter(error_codes)) if len(error_codes) == 1 else (
                "multiple_or_unexpected_error_codes"
            )
        metrics: tuple[ReferenceValidationMetricObservation, ...] = ()
    else:
        metrics = _metric_observations(case, variant_rows, metric_map)
        if any(row.observed_status == "time_budget_exhausted" for row in variant_rows):
            status = "time_budget_exhausted"
        elif any(row.observed_status != "success" for row in variant_rows):
            status = "unexpected_error"
        elif all(row.passed for row in metrics):
            status = "metrics_passed"
        else:
            status = "metric_threshold_failed"
        observed_error = (
            None
            if status in {"metrics_passed", "metric_threshold_failed"}
            else next(
                (
                    row.observed_error_code
                    for row in variant_rows
                    if row.observed_error_code is not None
                ),
                "metric_not_observed",
            )
        )
    return ReferenceValidationCaseObservation(
        ordinal=ordinal,
        case_id=case.case_id,
        case_input_sha256=case.input_sha256,
        materialization_sha256=materialized.materialization_sha256,
        expected_outcome=case.expected_outcome,
        observed_status=status,
        expected_error_code=case.expected_error_code,
        observed_error_code=observed_error,
        variant_results=variant_rows,
        metric_values=metrics,
        case_passed=status in {"metrics_passed", "fail_closed_as_expected"},
    )


def run_bounded_cpu_reference_validation(
    artifact_output_root: str | os.PathLike[str],
    authorization_nonce_sha256: str,
    *,
    expected_environment_receipt_sha256: str,
    expected_code_commit_sha: str,
    expected_dependency_artifact_sha256_rows: Mapping[str, str],
) -> ReferenceValidationRunObservation:
    """Consume one runner start and evaluate the exact frozen synthetic matrix."""

    started = _utc_now()
    try:
        receipt = require_reference_validation_execution_environment_receipt_for_runner(
            artifact_output_root,
            authorization_nonce_sha256,
            expected_receipt_sha256=expected_environment_receipt_sha256,
        )
    except ReferenceValidationRunStartError as exc:
        raise ReferenceValidationRunnerError(
            "runner execution-environment re-verification failed"
        ) from exc
    receipt_started = _parse_utc(
        receipt.started_at_utc,
        name="environment receipt started_at",
    )
    if not receipt_started <= started <= (
        receipt_started + REFERENCE_VALIDATION_RUNNER_MAX_RECEIPT_AGE
    ):
        raise ReferenceValidationRunnerError(
            "execution environment receipt is not fresh enough for the runner"
        )
    _require_commit_sha(expected_code_commit_sha, name="expected runner code commit")
    if receipt.code_commit_sha != expected_code_commit_sha:
        raise ReferenceValidationRunnerError("runner code commit is cross-wired")
    dependencies = _normalize_dependency_rows(
        expected_dependency_artifact_sha256_rows
    )
    if receipt.dependency_artifact_sha256_rows != dependencies:
        raise ReferenceValidationRunnerError(
            "runner dependency artifact rows are cross-wired"
        )
    runner_source = reference_validation_runner_source_sha256()
    if receipt.runner_source_sha256 != runner_source:
        raise ReferenceValidationRunnerError(
            "runner source does not match the signed authorization chain"
        )

    from .reference_validation_artifact_binding import (
        frozen_reference_validation_artifact_binding,
    )
    from .reference_validation_materializer import (
        materialize_frozen_reference_validation_case,
        reference_validation_materialization_manifest_document,
    )
    from .reference_validation_oracle import (
        evaluate_independent_analytic_oracle,
    )

    frozen_reference_validation_artifact_binding()
    manifest = reference_validation_materialization_manifest_document()
    if manifest["coverage"] != {
        "fixture_count": 7,
        "mutation_count": 20,
        "case_count": REFERENCE_VALIDATION_RUNNER_MAX_CASES,
        "variant_count": REFERENCE_VALIDATION_RUNNER_MAX_VARIANTS,
        "expected_pass_case_count": 15,
        "expected_fail_closed_case_count": 12,
    }:
        raise ReferenceValidationRunnerError(
            "runner materialization coverage drifted"
        )
    protocol = frozen_cpu_reference_validation_protocol()
    if len(protocol.cases) != REFERENCE_VALIDATION_RUNNER_MAX_CASES:
        raise ReferenceValidationRunnerError("runner protocol case bound drifted")

    started_at_utc = _format_utc(started, name="runner started_at")
    start_record_sha256 = _persist_runner_start(
        artifact_output_root,
        receipt,
        runner_source_sha256=runner_source,
        started_at_utc=started_at_utc,
    )

    from .reference_forcefield import (
        ReferencePhysicsApplicabilityError,
        evaluate_reference_force_field,
    )

    deadline = time.monotonic() + REFERENCE_VALIDATION_RUNNER_MAX_WALL_SECONDS
    metric_map = {row.metric_id: row for row in protocol.metrics}
    case_results = tuple(
        _evaluate_case(
            ordinal,
            case,
            materialize_frozen_reference_validation_case(case.case_id, protocol),
            metric_map=metric_map,
            deadline=deadline,
            evaluate_reference_force_field=evaluate_reference_force_field,
            reference_error_type=ReferencePhysicsApplicabilityError,
            evaluate_independent_analytic_oracle=(
                evaluate_independent_analytic_oracle
            ),
        )
        for ordinal, case in enumerate(protocol.cases)
    )
    completed_at_utc = _format_utc(_utc_now(), name="runner completed_at")
    return ReferenceValidationRunObservation(
        runner_start_record_sha256=start_record_sha256,
        execution_environment_receipt_sha256=receipt.receipt_sha256,
        environment_fingerprint_sha256=receipt.environment_fingerprint_sha256,
        authorization_receipt_sha256=receipt.authorization_receipt_sha256,
        authorization_nonce_sha256=receipt.authorization_nonce_sha256,
        code_commit_sha=receipt.code_commit_sha,
        runner_source_sha256=runner_source,
        dependency_artifact_sha256_rows=receipt.dependency_artifact_sha256_rows,
        command_argv=receipt.command_argv,
        seed=receipt.application_seed,
        started_at_utc=started_at_utc,
        completed_at_utc=completed_at_utc,
        case_results=case_results,
    )


def reference_validation_runner_contract_decision() -> dict[str, Any]:
    contract = reference_validation_runner_contract_document()
    return {
        "contract_sha256": contract["contract_sha256"],
        "bounded_validation_runner_implemented": True,
        "production_environment_receipt_present": False,
        "production_runner_start_consumed": False,
        "production_validation_execution_authorized": False,
        "production_validation_results_collected": False,
        "result_receipt_writer_implemented": False,
        "parameter_fitting_authorized": False,
        "blockers": list(_CURRENT_BLOCKERS),
    }


def require_reference_validation_run_observation_document(
    payload: Mapping[str, Any],
) -> ReferenceValidationRunObservation:
    """Reconstruct and verify an exact canonical bounded-run observation."""

    if not isinstance(payload, Mapping):
        raise ReferenceValidationRunnerError(
            "validation run observation document must be a mapping"
        )
    try:
        observed = json.loads(_canonical_bytes(dict(payload)).decode("ascii"))
        cases: list[ReferenceValidationCaseObservation] = []
        for case_payload in observed["case_results"]:
            metrics: list[ReferenceValidationMetricObservation] = []
            for metric_payload in case_payload["metric_values"]:
                if metric_payload["observed"]:
                    metric_value = metric_payload["value"]
                else:
                    if metric_payload.get("error_code") != "metric_not_observed":
                        raise ReferenceValidationRunnerError(
                            "missing metric observation error is invalid"
                        )
                    metric_value = None
                metrics.append(
                    ReferenceValidationMetricObservation(
                        metric_id=metric_payload["metric_id"],
                        observed=metric_payload["observed"],
                        value=metric_value,
                        unit=metric_payload["unit"],
                        threshold_operator=metric_payload["threshold_operator"],
                        threshold_value=metric_payload["threshold_value"],
                        passed=metric_payload["passed"],
                    )
                )
            variants: list[ReferenceValidationVariantObservation] = []
            for variant_payload in case_payload["variant_results"]:
                success = variant_payload["observed_status"] == "success"
                components = (
                    tuple(
                        (row["name"], row["value"])
                        for row in variant_payload[
                            "component_energy_values_and_units"
                        ]
                    )
                    if success
                    else ()
                )
                forces = (
                    tuple(
                        tuple(row)
                        for row in variant_payload["force_array_values"]
                    )
                    if success
                    else ()
                )
                oracle_forces = (
                    tuple(
                        tuple(row)
                        for row in variant_payload["oracle_force_array_values"]
                    )
                    if success
                    else ()
                )
                variants.append(
                    ReferenceValidationVariantObservation(
                        ordinal=variant_payload["ordinal"],
                        variant_id=variant_payload["variant_id"],
                        runtime_input_sha256=variant_payload[
                            "runtime_input_sha256"
                        ],
                        oracle_input_sha256=variant_payload[
                            "oracle_input_sha256"
                        ],
                        observed_status=variant_payload["observed_status"],
                        observed_error_code=variant_payload[
                            "observed_error_code"
                        ],
                        component_energies_kcal_per_mol=components,
                        total_energy_kcal_per_mol=(
                            variant_payload["total_energy_value"]
                            if success
                            else None
                        ),
                        forces_kcal_per_mol_angstrom=forces,
                        force_array_sha256=(
                            variant_payload["force_array_sha256"]
                            if success
                            else None
                        ),
                        oracle_total_energy_kcal_per_mol=(
                            variant_payload["oracle_total_energy_value"]
                            if success
                            else None
                        ),
                        oracle_forces_kcal_per_mol_angstrom=oracle_forces,
                        oracle_force_array_sha256=(
                            variant_payload["oracle_force_array_sha256"]
                            if success
                            else None
                        ),
                    )
                )
            cases.append(
                ReferenceValidationCaseObservation(
                    ordinal=case_payload["ordinal"],
                    case_id=case_payload["case_id"],
                    case_input_sha256=case_payload["case_input_sha256"],
                    materialization_sha256=case_payload[
                        "materialization_sha256"
                    ],
                    expected_outcome=case_payload["expected_outcome"],
                    observed_status=case_payload["observed_status"],
                    expected_error_code=case_payload["expected_error_code"],
                    observed_error_code=case_payload["observed_error_code"],
                    variant_results=tuple(variants),
                    metric_values=tuple(metrics),
                    case_passed=case_payload["case_passed"],
                )
            )
        dependencies = tuple(
            (row["artifact_id"], row["sha256"])
            for row in observed["dependency_artifact_sha256_rows"]
        )
        result = ReferenceValidationRunObservation(
            runner_start_record_sha256=observed[
                "runner_start_record_sha256"
            ],
            execution_environment_receipt_sha256=observed[
                "execution_environment_receipt_sha256"
            ],
            environment_fingerprint_sha256=observed[
                "environment_fingerprint_sha256"
            ],
            authorization_receipt_sha256=observed[
                "authorization_receipt_sha256"
            ],
            authorization_nonce_sha256=observed[
                "authorization_nonce_sha256"
            ],
            code_commit_sha=observed["code_commit_sha"],
            runner_source_sha256=observed["runner_source_sha256"],
            dependency_artifact_sha256_rows=dependencies,
            command_argv=tuple(observed["command_argv"]),
            seed=observed["seed"],
            started_at_utc=observed["started_at_utc"],
            completed_at_utc=observed["completed_at_utc"],
            case_results=tuple(cases),
            blockers=tuple(observed["blockers"]),
        )
    except ReferenceValidationRunnerError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise ReferenceValidationRunnerError(
            "validation run observation document is invalid"
        ) from exc
    if result.to_dict() != observed:
        raise ReferenceValidationRunnerError(
            "validation run observation document is not canonical or exact"
        )
    return result


def main() -> int:
    """Keep direct CLI execution closed; an in-process verified chain is required."""

    return 2


__all__ = [
    "FROZEN_REFERENCE_VALIDATION_RUNNER_CONTRACT_SHA256",
    "REFERENCE_VALIDATION_CENTRAL_DIFFERENCE_STEP_ANGSTROM",
    "REFERENCE_VALIDATION_RUNNER_CONTRACT_ID",
    "REFERENCE_VALIDATION_RUNNER_CONTRACT_SCHEMA_ID",
    "REFERENCE_VALIDATION_RUNNER_CONTRACT_VERSION",
    "REFERENCE_VALIDATION_RUNNER_MAX_CASES",
    "REFERENCE_VALIDATION_RUNNER_MAX_RECEIPT_AGE",
    "REFERENCE_VALIDATION_RUNNER_MAX_START_RECORD_BYTES",
    "REFERENCE_VALIDATION_RUNNER_MAX_VARIANTS",
    "REFERENCE_VALIDATION_RUNNER_MAX_WALL_SECONDS",
    "REFERENCE_VALIDATION_RUNNER_START_SCHEMA_ID",
    "REFERENCE_VALIDATION_RUN_OBSERVATION_SCHEMA_ID",
    "ReferenceValidationCaseObservation",
    "ReferenceValidationMetricObservation",
    "ReferenceValidationRunObservation",
    "ReferenceValidationRunnerAlreadyStartedError",
    "ReferenceValidationRunnerError",
    "ReferenceValidationVariantObservation",
    "reference_validation_runner_contract_decision",
    "reference_validation_runner_contract_document",
    "reference_validation_runner_source_sha256",
    "read_reference_validation_runner_start_record",
    "require_reference_validation_run_observation_document",
    "require_reference_validation_runner_contract_document",
    "run_bounded_cpu_reference_validation",
]


if __name__ == "__main__":
    raise SystemExit(main())
