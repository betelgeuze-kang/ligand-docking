"""Import-separated independent oracle for constrained stationarity.

The numerical path in this module uses Python ``float`` and tuple arithmetic.
It deliberately does not import Torch, NumPy, an Engine evaluator, an Engine
constraint projector, or the operational stationarity implementation.  The
scalar energy/force formulas come from the pre-existing independent analytic
oracle through the import-separated minimization oracle.

This is a claim-closed implementation artifact, not a validation receipt.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from numbers import Real

from .reference_minimization_independent_oracle import (
    Coordinates,
    Forces,
    IndependentMinimizationOracleError,
    IndependentMinimizationOracleInput,
    _add,
    _dot,
    _evaluate,
    _norm,
    _pair_vector,
    _scale,
    _subtract,
)


INDEPENDENT_CONSTRAINT_STATIONARITY_ORACLE_ID = (
    "cpu_reference_constraint_stationarity_independent_oracle/1.0.0"
)
INDEPENDENT_CONSTRAINT_STATIONARITY_CONFIG_SCHEMA_ID = (
    "betelgeuze.engine_v2_independent_constraint_stationarity_config/1.0.0"
)
INDEPENDENT_CONSTRAINT_STATIONARITY_CHECKPOINT_SCHEMA_ID = (
    "betelgeuze.engine_v2_independent_constraint_stationarity_checkpoint/1.0.0"
)
INDEPENDENT_CONSTRAINT_STATIONARITY_RESULT_SCHEMA_ID = (
    "betelgeuze.engine_v2_independent_constraint_stationarity_result/1.0.0"
)
INDEPENDENT_CONSTRAINT_STATIONARITY_DEFAULT_CONFIG_SHA256 = (
    "fccc490f763d28f7c20491ac07313a409fee388a066a9c6c1c917e5f36ef0ab7"
)
INDEPENDENT_CONSTRAINT_STATIONARITY_SCIENTIFIC_BLOCKERS = (
    "successor_protocol_not_a_frozen_production_receipt",
    "same_scalar_forcefield_formulas_as_prior_independent_oracle",
    "equal_weight_constraints_ignore_atomic_masses",
    "two_cpu_host_reproduction_missing",
    "independent_review_missing",
    "scientific_validation_missing",
)

_ACCEPTED_OUTCOMES = {
    "accepted_armijo",
    "accepted_stationarity_polish",
}
_REJECTED_OUTCOMES = {
    "rejected_constraint_projection",
    "rejected_displacement",
    "rejected_tangent_projection",
    "rejected_acceptance",
    "rejected_evaluation",
}
_VALID_OUTCOMES = {"initial", *_ACCEPTED_OUTCOMES, *_REJECTED_OUTCOMES}


class IndependentConstraintStationarityError(ValueError):
    """The independent stationarity request or state is invalid."""


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
        raise IndependentConstraintStationarityError(
            "independent stationarity payload is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _finite(
    value: object,
    *,
    name: str,
    minimum: float | None = None,
    maximum: float | None = None,
    inclusive_minimum: bool = False,
) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise IndependentConstraintStationarityError(
            f"{name} must be a finite real number"
        )
    number = float(value)
    if not math.isfinite(number):
        raise IndependentConstraintStationarityError(f"{name} must be finite")
    if minimum is not None:
        invalid = number < minimum if inclusive_minimum else number <= minimum
        if invalid:
            relation = ">=" if inclusive_minimum else ">"
            raise IndependentConstraintStationarityError(
                f"{name} must be {relation} {minimum}"
            )
    if maximum is not None and number > maximum:
        raise IndependentConstraintStationarityError(
            f"{name} must be <= {maximum}"
        )
    return number


def _integer(
    value: object,
    *,
    name: str,
    minimum: int = 0,
    maximum: int = 1_000_000,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise IndependentConstraintStationarityError(f"{name} must be an integer")
    if value < minimum or value > maximum:
        raise IndependentConstraintStationarityError(
            f"{name} must be in [{minimum},{maximum}]"
        )
    return value


def _coordinate_sha256(value: Coordinates) -> str:
    return _sha256([[float(item).hex() for item in row] for row in value])


def _coordinate_hex(value: Coordinates) -> list[list[str]]:
    return [[float(item).hex() for item in row] for row in value]


@dataclass(frozen=True, slots=True)
class IndependentConstraintStationarityConfig:
    """Numerical bounds independent from the operational config class."""

    max_iterations: int = 512
    max_backtracks: int = 24
    initial_step_size_angstrom2_mol_per_kcal: float = 1.0e-3
    backtrack_factor: float = 0.5
    armijo_constant: float = 1.0e-4
    maximum_atom_displacement_angstrom: float = 5.0e-2
    tangent_force_tolerance_kcal_per_mol_angstrom: float = 1.0e-8
    constraint_acceptance_tolerance_angstrom: float = 1.0e-10
    strict_projection_tolerance_angstrom: float = 1.0e-14
    projection_max_sweeps: int = 1_000
    projection_max_pair_correction_angstrom: float = 0.25
    tangent_projection_max_sweeps: int = 1_000
    tangent_projection_tolerance_kcal_per_mol_angstrom: float = 1.0e-12
    stationarity_energy_relaxation_kcal_per_mol: float = 1.0e-10
    schema_id: str = INDEPENDENT_CONSTRAINT_STATIONARITY_CONFIG_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != INDEPENDENT_CONSTRAINT_STATIONARITY_CONFIG_SCHEMA_ID:
            raise IndependentConstraintStationarityError(
                "unsupported independent stationarity config schema"
            )
        for field_name in (
            "max_iterations",
            "projection_max_sweeps",
            "tangent_projection_max_sweeps",
        ):
            object.__setattr__(
                self,
                field_name,
                _integer(getattr(self, field_name), name=field_name, minimum=1),
            )
        object.__setattr__(
            self,
            "max_backtracks",
            _integer(self.max_backtracks, name="max_backtracks"),
        )
        for field_name in (
            "initial_step_size_angstrom2_mol_per_kcal",
            "maximum_atom_displacement_angstrom",
            "tangent_force_tolerance_kcal_per_mol_angstrom",
            "constraint_acceptance_tolerance_angstrom",
            "strict_projection_tolerance_angstrom",
            "projection_max_pair_correction_angstrom",
            "tangent_projection_tolerance_kcal_per_mol_angstrom",
            "stationarity_energy_relaxation_kcal_per_mol",
        ):
            object.__setattr__(
                self,
                field_name,
                _finite(getattr(self, field_name), name=field_name, minimum=0.0),
            )
        object.__setattr__(
            self,
            "backtrack_factor",
            _finite(
                self.backtrack_factor,
                name="backtrack_factor",
                minimum=0.0,
                maximum=1.0,
            ),
        )
        object.__setattr__(
            self,
            "armijo_constant",
            _finite(
                self.armijo_constant,
                name="armijo_constant",
                minimum=0.0,
                maximum=0.5,
            ),
        )
        if self.backtrack_factor >= 1.0:
            raise IndependentConstraintStationarityError(
                "backtrack_factor must be less than one"
            )
        if (
            self.strict_projection_tolerance_angstrom
            > self.constraint_acceptance_tolerance_angstrom
        ):
            raise IndependentConstraintStationarityError(
                "strict projection tolerance exceeds acceptance tolerance"
            )
        if (
            self.tangent_projection_tolerance_kcal_per_mol_angstrom
            > self.tangent_force_tolerance_kcal_per_mol_angstrom
        ):
            raise IndependentConstraintStationarityError(
                "tangent projection tolerance exceeds force tolerance"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "oracle_id": INDEPENDENT_CONSTRAINT_STATIONARITY_ORACLE_ID,
            "max_iterations": self.max_iterations,
            "max_backtracks": self.max_backtracks,
            "initial_step_size_angstrom2_mol_per_kcal": (
                self.initial_step_size_angstrom2_mol_per_kcal
            ),
            "backtrack_factor": self.backtrack_factor,
            "armijo_constant": self.armijo_constant,
            "maximum_atom_displacement_angstrom": (
                self.maximum_atom_displacement_angstrom
            ),
            "tangent_force_tolerance_kcal_per_mol_angstrom": (
                self.tangent_force_tolerance_kcal_per_mol_angstrom
            ),
            "constraint_acceptance_tolerance_angstrom": (
                self.constraint_acceptance_tolerance_angstrom
            ),
            "strict_projection_tolerance_angstrom": (
                self.strict_projection_tolerance_angstrom
            ),
            "projection_max_sweeps": self.projection_max_sweeps,
            "projection_max_pair_correction_angstrom": (
                self.projection_max_pair_correction_angstrom
            ),
            "tangent_projection_max_sweeps": (
                self.tangent_projection_max_sweeps
            ),
            "tangent_projection_tolerance_kcal_per_mol_angstrom": (
                self.tangent_projection_tolerance_kcal_per_mol_angstrom
            ),
            "stationarity_energy_relaxation_kcal_per_mol": (
                self.stationarity_energy_relaxation_kcal_per_mol
            ),
            "constraint_weighting": "equal_weight_without_atomic_masses",
            "numeric_backend": "python_binary64_tuple_arithmetic",
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class IndependentConstraintStationarityObservation:
    """One complete independent initial, accepted, or rejected attempt."""

    attempt_index: int
    iteration: int
    trial: int
    outcome: str
    raw_coordinates_angstrom: Coordinates
    evaluated_coordinates_angstrom: Coordinates
    step_size_angstrom2_mol_per_kcal: float
    energy_kcal_per_mol: float | None
    best_energy_kcal_per_mol: float
    max_tangent_force_kcal_per_mol_angstrom: float | None
    max_constraint_residual_angstrom: float
    max_constraint_force_residual_kcal_per_mol_angstrom: float | None
    projection_sweeps: int
    tangent_projection_sweeps: int | None
    directional_derivative_kcal_per_mol: float | None
    armijo_limit_kcal_per_mol: float | None
    failure_code: str | None

    def __post_init__(self) -> None:
        if self.outcome not in _VALID_OUTCOMES:
            raise IndependentConstraintStationarityError(
                f"unsupported observation outcome {self.outcome!r}"
            )
        rejected = self.outcome in _REJECTED_OUTCOMES
        if rejected != (self.failure_code is not None):
            raise IndependentConstraintStationarityError(
                "only rejected observations require failure_code"
            )

    @property
    def coordinates_sha256(self) -> str:
        return _coordinate_sha256(self.evaluated_coordinates_angstrom)

    def to_dict(self) -> dict[str, object]:
        return {
            "attempt_index": self.attempt_index,
            "iteration": self.iteration,
            "trial": self.trial,
            "outcome": self.outcome,
            "raw_coordinates_angstrom_hex": _coordinate_hex(
                self.raw_coordinates_angstrom
            ),
            "raw_coordinates_sha256": _coordinate_sha256(
                self.raw_coordinates_angstrom
            ),
            "evaluated_coordinates_angstrom_hex": _coordinate_hex(
                self.evaluated_coordinates_angstrom
            ),
            "coordinates_sha256": self.coordinates_sha256,
            "step_size_angstrom2_mol_per_kcal": (
                self.step_size_angstrom2_mol_per_kcal
            ),
            "energy_kcal_per_mol": self.energy_kcal_per_mol,
            "best_energy_kcal_per_mol": self.best_energy_kcal_per_mol,
            "max_tangent_force_kcal_per_mol_angstrom": (
                self.max_tangent_force_kcal_per_mol_angstrom
            ),
            "max_constraint_residual_angstrom": (
                self.max_constraint_residual_angstrom
            ),
            "max_constraint_force_residual_kcal_per_mol_angstrom": (
                self.max_constraint_force_residual_kcal_per_mol_angstrom
            ),
            "projection_sweeps": self.projection_sweeps,
            "tangent_projection_sweeps": self.tangent_projection_sweeps,
            "directional_derivative_kcal_per_mol": (
                self.directional_derivative_kcal_per_mol
            ),
            "armijo_limit_kcal_per_mol": self.armijo_limit_kcal_per_mol,
            "failure_code": self.failure_code,
        }


@dataclass(frozen=True, slots=True)
class IndependentConstraintStationarityCheckpoint:
    """Canonical, replay-verifiable independent restart state."""

    input_sha256: str
    config_fingerprint_sha256: str
    coordinates_angstrom: Coordinates
    accepted_iterations: int
    rejected_trials: int
    energy_evaluation_count: int
    current_energy_kcal_per_mol: float
    best_energy_kcal_per_mol: float
    current_max_tangent_force_kcal_per_mol_angstrom: float
    current_max_constraint_residual_angstrom: float
    observations: tuple[IndependentConstraintStationarityObservation, ...]
    schema_id: str = INDEPENDENT_CONSTRAINT_STATIONARITY_CHECKPOINT_SCHEMA_ID

    def projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "oracle_id": INDEPENDENT_CONSTRAINT_STATIONARITY_ORACLE_ID,
            "input_sha256": self.input_sha256,
            "config_fingerprint_sha256": self.config_fingerprint_sha256,
            "coordinates_angstrom_hex": _coordinate_hex(self.coordinates_angstrom),
            "coordinates_sha256": _coordinate_sha256(self.coordinates_angstrom),
            "accepted_iterations": self.accepted_iterations,
            "rejected_trials": self.rejected_trials,
            "energy_evaluation_count": self.energy_evaluation_count,
            "current_energy_kcal_per_mol": self.current_energy_kcal_per_mol,
            "best_energy_kcal_per_mol": self.best_energy_kcal_per_mol,
            "current_max_tangent_force_kcal_per_mol_angstrom": (
                self.current_max_tangent_force_kcal_per_mol_angstrom
            ),
            "current_max_constraint_residual_angstrom": (
                self.current_max_constraint_residual_angstrom
            ),
            "observations": [row.to_dict() for row in self.observations],
        }

    @property
    def checkpoint_sha256(self) -> str:
        return _sha256(self.projection())

    def to_dict(self) -> dict[str, object]:
        return {**self.projection(), "checkpoint_sha256": self.checkpoint_sha256}


@dataclass(frozen=True, slots=True)
class IndependentConstraintStationarityResult:
    """One bounded independent result retaining every attempted state."""

    input_sha256: str
    config_fingerprint_sha256: str
    status: str
    failure_code: str | None
    initial_energy_kcal_per_mol: float
    final_energy_kcal_per_mol: float
    best_energy_kcal_per_mol: float
    initial_max_tangent_force_kcal_per_mol_angstrom: float
    final_max_tangent_force_kcal_per_mol_angstrom: float
    final_max_constraint_residual_angstrom: float
    final_coordinates_angstrom: Coordinates
    accepted_iterations: int
    accepted_armijo_iterations: int
    accepted_stationarity_polish_iterations: int
    rejected_trials: int
    energy_evaluation_count: int
    checkpoint: IndependentConstraintStationarityCheckpoint
    schema_id: str = INDEPENDENT_CONSTRAINT_STATIONARITY_RESULT_SCHEMA_ID

    @property
    def converged(self) -> bool:
        return self.status == "converged"

    @property
    def observations(self) -> tuple[IndependentConstraintStationarityObservation, ...]:
        return self.checkpoint.observations

    @property
    def accepted_energy_trace_kcal_per_mol(self) -> tuple[float, ...]:
        return tuple(
            row.energy_kcal_per_mol
            for row in self.observations
            if row.outcome == "initial" or row.outcome in _ACCEPTED_OUTCOMES
            if row.energy_kcal_per_mol is not None
        )

    def projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "oracle_id": INDEPENDENT_CONSTRAINT_STATIONARITY_ORACLE_ID,
            "input_sha256": self.input_sha256,
            "config_fingerprint_sha256": self.config_fingerprint_sha256,
            "status": self.status,
            "failure_code": self.failure_code,
            "converged": self.converged,
            "initial_energy_kcal_per_mol": self.initial_energy_kcal_per_mol,
            "final_energy_kcal_per_mol": self.final_energy_kcal_per_mol,
            "best_energy_kcal_per_mol": self.best_energy_kcal_per_mol,
            "initial_max_tangent_force_kcal_per_mol_angstrom": (
                self.initial_max_tangent_force_kcal_per_mol_angstrom
            ),
            "final_max_tangent_force_kcal_per_mol_angstrom": (
                self.final_max_tangent_force_kcal_per_mol_angstrom
            ),
            "final_max_constraint_residual_angstrom": (
                self.final_max_constraint_residual_angstrom
            ),
            "final_coordinates_angstrom_hex": _coordinate_hex(
                self.final_coordinates_angstrom
            ),
            "final_coordinates_sha256": _coordinate_sha256(
                self.final_coordinates_angstrom
            ),
            "accepted_iterations": self.accepted_iterations,
            "accepted_armijo_iterations": self.accepted_armijo_iterations,
            "accepted_stationarity_polish_iterations": (
                self.accepted_stationarity_polish_iterations
            ),
            "rejected_trials": self.rejected_trials,
            "energy_evaluation_count": self.energy_evaluation_count,
            "accepted_energy_trace_kcal_per_mol": list(
                self.accepted_energy_trace_kcal_per_mol
            ),
            "all_observations": [row.to_dict() for row in self.observations],
            "checkpoint": self.checkpoint.to_dict(),
            "scientifically_validated": False,
            "claim_safe": False,
            "scientific_blockers": list(
                INDEPENDENT_CONSTRAINT_STATIONARITY_SCIENTIFIC_BLOCKERS
            ),
        }

    @property
    def result_sha256(self) -> str:
        return _sha256(self.projection())

    def to_dict(self) -> dict[str, object]:
        return {**self.projection(), "result_sha256": self.result_sha256}


@dataclass(frozen=True, slots=True)
class _Projection:
    coordinates: Coordinates
    max_residual: float
    sweeps: int
    converged: bool
    failure_code: str | None


@dataclass(frozen=True, slots=True)
class _Evaluation:
    energy: float
    tangent_forces: Forces
    max_tangent_force: float
    max_constraint_force_residual: float
    tangent_projection_sweeps: int


def _project_constraints(
    coordinates: Coordinates,
    source: IndependentMinimizationOracleInput,
    config: IndependentConstraintStationarityConfig,
) -> _Projection:
    current = coordinates
    degrees = [0] * source.energy_input.atom_count
    for atom_i, atom_j, _, _ in source.constraints:
        degrees[atom_i] += 1
        degrees[atom_j] += 1
    relaxation = float(max(degrees, default=1))
    maximum = math.inf
    for sweep in range(config.projection_max_sweeps + 1):
        residuals: list[float] = []
        for atom_i, atom_j, target, _ in source.constraints:
            vector = _pair_vector(
                current,
                atom_i,
                atom_j,
                source.energy_input,
            )
            distance = _norm(vector)
            residuals.append(abs(distance - target))
            if distance <= 1.0e-12:
                return _Projection(
                    current,
                    max(residuals, default=0.0),
                    sweep,
                    False,
                    "constraint_pair_has_zero_distance",
                )
        maximum = max(residuals, default=0.0)
        if maximum <= config.strict_projection_tolerance_angstrom:
            return _Projection(current, maximum, sweep, True, None)
        if sweep == config.projection_max_sweeps:
            break
        updates = [(0.0, 0.0, 0.0) for _ in current]
        for atom_i, atom_j, target, _ in source.constraints:
            vector = _pair_vector(
                current,
                atom_i,
                atom_j,
                source.energy_input,
            )
            distance = _norm(vector)
            residual = distance - target
            correction = max(
                -config.projection_max_pair_correction_angstrom,
                min(config.projection_max_pair_correction_angstrom, residual),
            )
            direction = _scale(vector, 1.0 / distance)
            updates[atom_i] = _add(
                updates[atom_i],
                _scale(direction, -0.5 * correction),
            )
            updates[atom_j] = _add(
                updates[atom_j],
                _scale(direction, 0.5 * correction),
            )
        current = tuple(
            _add(row, _scale(update, 1.0 / relaxation))
            for row, update in zip(current, updates)
        )
    return _Projection(
        current,
        maximum,
        config.projection_max_sweeps,
        False,
        "strict_constraint_projection_budget_exhausted",
    )


def _project_tangent(
    coordinates: Coordinates,
    forces: Forces,
    source: IndependentMinimizationOracleInput,
    config: IndependentConstraintStationarityConfig,
) -> tuple[Forces, float, float, int, bool]:
    projected = forces
    degrees = [0] * source.energy_input.atom_count
    for atom_i, atom_j, _, _ in source.constraints:
        degrees[atom_i] += 1
        degrees[atom_j] += 1
    relaxation = float(max(degrees, default=1))
    maximum_residual = math.inf
    for sweep in range(1, config.tangent_projection_max_sweeps + 1):
        updates = [(0.0, 0.0, 0.0) for _ in projected]
        for atom_i, atom_j, _, _ in source.constraints:
            vector = _pair_vector(
                coordinates,
                atom_i,
                atom_j,
                source.energy_input,
            )
            distance = _norm(vector)
            if distance <= 1.0e-12:
                raise IndependentConstraintStationarityError(
                    "constraint tangent is undefined at zero pair distance"
                )
            direction = _scale(vector, 1.0 / distance)
            relative = _dot(
                _subtract(projected[atom_i], projected[atom_j]),
                direction,
            )
            correction = _scale(direction, 0.5 * relative)
            updates[atom_i] = _subtract(updates[atom_i], correction)
            updates[atom_j] = _add(updates[atom_j], correction)
        projected = tuple(
            _add(row, _scale(update, 1.0 / relaxation))
            for row, update in zip(projected, updates)
        )
        residuals = []
        for atom_i, atom_j, _, _ in source.constraints:
            vector = _pair_vector(
                coordinates,
                atom_i,
                atom_j,
                source.energy_input,
            )
            direction = _scale(vector, 1.0 / _norm(vector))
            residuals.append(
                abs(
                    _dot(
                        _subtract(projected[atom_i], projected[atom_j]),
                        direction,
                    )
                )
            )
        maximum_residual = max(residuals, default=0.0)
        maximum_force = max((_norm(row) for row in projected), default=0.0)
        if (
            maximum_residual
            <= config.tangent_projection_tolerance_kcal_per_mol_angstrom
        ):
            return projected, maximum_force, maximum_residual, sweep, True
    maximum_force = max((_norm(row) for row in projected), default=0.0)
    return (
        projected,
        maximum_force,
        maximum_residual,
        config.tangent_projection_max_sweeps,
        False,
    )


def _evaluate_stationarity(
    coordinates: Coordinates,
    source: IndependentMinimizationOracleInput,
    config: IndependentConstraintStationarityConfig,
) -> _Evaluation:
    energy, forces = _evaluate(source, coordinates)
    tangent, maximum, residual, sweeps, converged = _project_tangent(
        coordinates,
        forces,
        source,
        config,
    )
    if not converged:
        raise IndependentConstraintStationarityError(
            "constraint tangent projection exhausted its budget"
        )
    return _Evaluation(energy, tangent, maximum, residual, sweeps)


def _observation(
    *,
    attempt_index: int,
    iteration: int,
    trial: int,
    outcome: str,
    raw_coordinates: Coordinates,
    coordinates: Coordinates,
    step: float,
    energy: float | None,
    best_energy: float,
    tangent_force: float | None,
    constraint_residual: float,
    constraint_force_residual: float | None,
    projection_sweeps: int,
    tangent_projection_sweeps: int | None,
    directional_derivative: float | None,
    armijo_limit: float | None,
    failure_code: str | None = None,
) -> IndependentConstraintStationarityObservation:
    return IndependentConstraintStationarityObservation(
        attempt_index=attempt_index,
        iteration=iteration,
        trial=trial,
        outcome=outcome,
        raw_coordinates_angstrom=raw_coordinates,
        evaluated_coordinates_angstrom=coordinates,
        step_size_angstrom2_mol_per_kcal=step,
        energy_kcal_per_mol=energy,
        best_energy_kcal_per_mol=best_energy,
        max_tangent_force_kcal_per_mol_angstrom=tangent_force,
        max_constraint_residual_angstrom=constraint_residual,
        max_constraint_force_residual_kcal_per_mol_angstrom=(
            constraint_force_residual
        ),
        projection_sweeps=projection_sweeps,
        tangent_projection_sweeps=tangent_projection_sweeps,
        directional_derivative_kcal_per_mol=directional_derivative,
        armijo_limit_kcal_per_mol=armijo_limit,
        failure_code=failure_code,
    )


def _checkpoint(
    source: IndependentMinimizationOracleInput,
    config: IndependentConstraintStationarityConfig,
    coordinates: Coordinates,
    accepted_iterations: int,
    rejected_trials: int,
    energy_evaluation_count: int,
    current_energy: float,
    best_energy: float,
    current_tangent_force: float,
    current_constraint_residual: float,
    observations: list[IndependentConstraintStationarityObservation],
) -> IndependentConstraintStationarityCheckpoint:
    return IndependentConstraintStationarityCheckpoint(
        input_sha256=source.input_sha256,
        config_fingerprint_sha256=config.fingerprint_sha256,
        coordinates_angstrom=coordinates,
        accepted_iterations=accepted_iterations,
        rejected_trials=rejected_trials,
        energy_evaluation_count=energy_evaluation_count,
        current_energy_kcal_per_mol=current_energy,
        best_energy_kcal_per_mol=best_energy,
        current_max_tangent_force_kcal_per_mol_angstrom=current_tangent_force,
        current_max_constraint_residual_angstrom=current_constraint_residual,
        observations=tuple(observations),
    )


def evaluate_independent_constraint_stationarity(
    source: IndependentMinimizationOracleInput,
    config: IndependentConstraintStationarityConfig | None = None,
    *,
    pause_after_accepted_iterations: int | None = None,
    checkpoint: IndependentConstraintStationarityCheckpoint | None = None,
) -> IndependentConstraintStationarityResult:
    """Run the bounded tuple-arithmetic stationarity implementation."""

    if not isinstance(source, IndependentMinimizationOracleInput):
        raise IndependentConstraintStationarityError(
            "source must be an IndependentMinimizationOracleInput"
        )
    config = (
        IndependentConstraintStationarityConfig() if config is None else config
    )
    if not isinstance(config, IndependentConstraintStationarityConfig):
        raise IndependentConstraintStationarityError(
            "config must be IndependentConstraintStationarityConfig"
        )
    if source.expected_outcome != "pass" or not source.constraints:
        raise IndependentConstraintStationarityError(
            "independent stationarity requires a passing constrained input"
        )
    if source.fixed_born_radii_angstrom is not None and (
        source.energy_input.orthorhombic_cell_angstrom is not None
        or any(source.energy_input.periodic_axes)
    ):
        raise IndependentConstraintStationarityError(
            "periodic fixed-Born stationarity is unsupported"
        )
    pause_at = None
    if pause_after_accepted_iterations is not None:
        pause_at = _integer(
            pause_after_accepted_iterations,
            name="pause_after_accepted_iterations",
            maximum=config.max_iterations,
        )

    if checkpoint is None:
        projection = _project_constraints(
            source.energy_input.coordinates_angstrom,
            source,
            config,
        )
        if not projection.converged:
            raise IndependentConstraintStationarityError(
                "initial strict constraint projection failed: "
                f"{projection.failure_code}"
            )
        coordinates = projection.coordinates
        evaluated = _evaluate_stationarity(coordinates, source, config)
        current_energy = evaluated.energy
        current_forces = evaluated.tangent_forces
        current_tangent_force = evaluated.max_tangent_force
        current_constraint_residual = projection.max_residual
        best_energy = current_energy
        observations = [
            _observation(
                attempt_index=0,
                iteration=0,
                trial=0,
                outcome="initial",
                raw_coordinates=source.energy_input.coordinates_angstrom,
                coordinates=coordinates,
                step=0.0,
                energy=current_energy,
                best_energy=best_energy,
                tangent_force=current_tangent_force,
                constraint_residual=current_constraint_residual,
                constraint_force_residual=(
                    evaluated.max_constraint_force_residual
                ),
                projection_sweeps=projection.sweeps,
                tangent_projection_sweeps=(
                    evaluated.tangent_projection_sweeps
                ),
                directional_derivative=None,
                armijo_limit=None,
            )
        ]
        accepted_iterations = 0
        rejected_trials = 0
        evaluation_count = 1
        initial_energy = current_energy
        initial_tangent_force = current_tangent_force
    else:
        if not isinstance(
            checkpoint,
            IndependentConstraintStationarityCheckpoint,
        ):
            raise IndependentConstraintStationarityError(
                "checkpoint must be an independent stationarity checkpoint"
            )
        if (
            checkpoint.input_sha256 != source.input_sha256
            or checkpoint.config_fingerprint_sha256
            != config.fingerprint_sha256
        ):
            raise IndependentConstraintStationarityError(
                "checkpoint input or config identity mismatch"
            )
        if pause_at is not None and pause_at < checkpoint.accepted_iterations:
            raise IndependentConstraintStationarityError(
                "pause precedes checkpoint progress"
            )
        replay = evaluate_independent_constraint_stationarity(
            source,
            config,
            pause_after_accepted_iterations=checkpoint.accepted_iterations,
        )
        if replay.checkpoint.to_dict() != checkpoint.to_dict():
            raise IndependentConstraintStationarityError(
                "checkpoint history does not replay exactly"
            )
        verification_projection = _project_constraints(
            checkpoint.coordinates_angstrom,
            source,
            config,
        )
        if (
            not verification_projection.converged
            or verification_projection.coordinates
            != checkpoint.coordinates_angstrom
        ):
            raise IndependentConstraintStationarityError(
                "checkpoint coordinates are not projection-idempotent"
            )
        coordinates = checkpoint.coordinates_angstrom
        evaluated = _evaluate_stationarity(coordinates, source, config)
        if (
            evaluated.energy != checkpoint.current_energy_kcal_per_mol
            or evaluated.max_tangent_force
            != checkpoint.current_max_tangent_force_kcal_per_mol_angstrom
        ):
            raise IndependentConstraintStationarityError(
                "checkpoint state does not reproduce exactly"
            )
        current_energy = evaluated.energy
        current_forces = evaluated.tangent_forces
        current_tangent_force = evaluated.max_tangent_force
        current_constraint_residual = (
            checkpoint.current_max_constraint_residual_angstrom
        )
        best_energy = checkpoint.best_energy_kcal_per_mol
        observations = list(checkpoint.observations)
        accepted_iterations = checkpoint.accepted_iterations
        rejected_trials = checkpoint.rejected_trials
        evaluation_count = checkpoint.energy_evaluation_count
        initial = observations[0]
        assert initial.energy_kcal_per_mol is not None
        assert initial.max_tangent_force_kcal_per_mol_angstrom is not None
        initial_energy = initial.energy_kcal_per_mol
        initial_tangent_force = (
            initial.max_tangent_force_kcal_per_mol_angstrom
        )

    status = "max_iterations_reached"
    failure_code: str | None = "maximum_iteration_budget_exhausted"
    while accepted_iterations < config.max_iterations:
        if (
            current_tangent_force
            <= config.tangent_force_tolerance_kcal_per_mol_angstrom
            and current_constraint_residual
            <= config.constraint_acceptance_tolerance_angstrom
        ):
            status = "converged"
            failure_code = None
            break
        if pause_at is not None and accepted_iterations >= pause_at:
            status = "checkpointed"
            failure_code = None
            break
        iteration = accepted_iterations + 1
        step = config.initial_step_size_angstrom2_mol_per_kcal
        direction = current_forces
        raw_max_displacement = step * current_tangent_force
        if raw_max_displacement > config.maximum_atom_displacement_angstrom:
            scale = (
                config.maximum_atom_displacement_angstrom
                / raw_max_displacement
            )
            direction = tuple(_scale(row, scale) for row in direction)
        accepted = False
        for trial in range(config.max_backtracks + 1):
            raw_coordinates = tuple(
                _add(row, _scale(delta, step))
                for row, delta in zip(coordinates, direction)
            )
            projected = _project_constraints(
                raw_coordinates,
                source,
                config,
            )
            attempt_index = len(observations)
            if not projected.converged:
                rejected_trials += 1
                observations.append(
                    _observation(
                        attempt_index=attempt_index,
                        iteration=iteration,
                        trial=trial,
                        outcome="rejected_constraint_projection",
                        raw_coordinates=raw_coordinates,
                        coordinates=projected.coordinates,
                        step=step,
                        energy=None,
                        best_energy=best_energy,
                        tangent_force=None,
                        constraint_residual=projected.max_residual,
                        constraint_force_residual=None,
                        projection_sweeps=projected.sweeps,
                        tangent_projection_sweeps=None,
                        directional_derivative=None,
                        armijo_limit=None,
                        failure_code=(
                            projected.failure_code
                            or "strict_constraint_projection_failed"
                        ),
                    )
                )
                step *= config.backtrack_factor
                continue
            trial_coordinates = projected.coordinates
            maximum_displacement = max(
                (
                    _norm(_subtract(trial_row, current_row))
                    for trial_row, current_row in zip(
                        trial_coordinates,
                        coordinates,
                    )
                ),
                default=0.0,
            )
            if (
                maximum_displacement
                > config.maximum_atom_displacement_angstrom + 1.0e-12
            ):
                rejected_trials += 1
                observations.append(
                    _observation(
                        attempt_index=attempt_index,
                        iteration=iteration,
                        trial=trial,
                        outcome="rejected_displacement",
                        raw_coordinates=raw_coordinates,
                        coordinates=trial_coordinates,
                        step=step,
                        energy=None,
                        best_energy=best_energy,
                        tangent_force=None,
                        constraint_residual=projected.max_residual,
                        constraint_force_residual=None,
                        projection_sweeps=projected.sweeps,
                        tangent_projection_sweeps=None,
                        directional_derivative=None,
                        armijo_limit=None,
                        failure_code="projected_displacement_bound_exceeded",
                    )
                )
                step *= config.backtrack_factor
                continue
            try:
                trial_evaluated = _evaluate_stationarity(
                    trial_coordinates,
                    source,
                    config,
                )
            except (
                IndependentConstraintStationarityError,
                IndependentMinimizationOracleError,
                FloatingPointError,
            ):
                rejected_trials += 1
                observations.append(
                    _observation(
                        attempt_index=attempt_index,
                        iteration=iteration,
                        trial=trial,
                        outcome="rejected_evaluation",
                        raw_coordinates=raw_coordinates,
                        coordinates=trial_coordinates,
                        step=step,
                        energy=None,
                        best_energy=best_energy,
                        tangent_force=None,
                        constraint_residual=projected.max_residual,
                        constraint_force_residual=None,
                        projection_sweeps=projected.sweeps,
                        tangent_projection_sweeps=None,
                        directional_derivative=None,
                        armijo_limit=None,
                        failure_code="independent_reference_evaluation_failed",
                    )
                )
                step *= config.backtrack_factor
                continue
            evaluation_count += 1
            displacement = tuple(
                _subtract(trial_row, current_row)
                for trial_row, current_row in zip(
                    trial_coordinates,
                    coordinates,
                )
            )
            directional_derivative = -sum(
                _dot(force, delta)
                for force, delta in zip(current_forces, displacement)
            )
            armijo_limit = (
                current_energy
                + config.armijo_constant * directional_derivative
            )
            armijo_accepted = (
                directional_derivative < 0.0
                and trial_evaluated.energy <= armijo_limit
            )
            stationarity_accepted = (
                not armijo_accepted
                and trial_evaluated.max_tangent_force
                < current_tangent_force
                and trial_evaluated.energy
                <= (
                    best_energy
                    + config.stationarity_energy_relaxation_kcal_per_mol
                )
            )
            if not armijo_accepted and not stationarity_accepted:
                rejected_trials += 1
                observations.append(
                    _observation(
                        attempt_index=attempt_index,
                        iteration=iteration,
                        trial=trial,
                        outcome="rejected_acceptance",
                        raw_coordinates=raw_coordinates,
                        coordinates=trial_coordinates,
                        step=step,
                        energy=trial_evaluated.energy,
                        best_energy=best_energy,
                        tangent_force=trial_evaluated.max_tangent_force,
                        constraint_residual=projected.max_residual,
                        constraint_force_residual=(
                            trial_evaluated.max_constraint_force_residual
                        ),
                        projection_sweeps=projected.sweeps,
                        tangent_projection_sweeps=(
                            trial_evaluated.tangent_projection_sweeps
                        ),
                        directional_derivative=directional_derivative,
                        armijo_limit=armijo_limit,
                        failure_code=(
                            "armijo_and_stationarity_polish_not_satisfied"
                        ),
                    )
                )
                step *= config.backtrack_factor
                continue
            outcome = (
                "accepted_armijo"
                if armijo_accepted
                else "accepted_stationarity_polish"
            )
            updated_best = min(best_energy, trial_evaluated.energy)
            observations.append(
                _observation(
                    attempt_index=attempt_index,
                    iteration=iteration,
                    trial=trial,
                    outcome=outcome,
                    raw_coordinates=raw_coordinates,
                    coordinates=trial_coordinates,
                    step=step,
                    energy=trial_evaluated.energy,
                    best_energy=updated_best,
                    tangent_force=trial_evaluated.max_tangent_force,
                    constraint_residual=projected.max_residual,
                    constraint_force_residual=(
                        trial_evaluated.max_constraint_force_residual
                    ),
                    projection_sweeps=projected.sweeps,
                    tangent_projection_sweeps=(
                        trial_evaluated.tangent_projection_sweeps
                    ),
                    directional_derivative=directional_derivative,
                    armijo_limit=armijo_limit,
                )
            )
            coordinates = trial_coordinates
            current_energy = trial_evaluated.energy
            current_forces = trial_evaluated.tangent_forces
            current_tangent_force = trial_evaluated.max_tangent_force
            current_constraint_residual = projected.max_residual
            best_energy = updated_best
            accepted_iterations += 1
            accepted = True
            break
        if not accepted:
            status = "line_search_failed"
            failure_code = "bounded_stationarity_backtracking_exhausted"
            break
    else:
        status = "max_iterations_reached"
        failure_code = "maximum_iteration_budget_exhausted"

    if (
        current_tangent_force
        <= config.tangent_force_tolerance_kcal_per_mol_angstrom
        and current_constraint_residual
        <= config.constraint_acceptance_tolerance_angstrom
    ):
        status = "converged"
        failure_code = None

    state = _checkpoint(
        source,
        config,
        coordinates,
        accepted_iterations,
        rejected_trials,
        evaluation_count,
        current_energy,
        best_energy,
        current_tangent_force,
        current_constraint_residual,
        observations,
    )
    return IndependentConstraintStationarityResult(
        input_sha256=source.input_sha256,
        config_fingerprint_sha256=config.fingerprint_sha256,
        status=status,
        failure_code=failure_code,
        initial_energy_kcal_per_mol=initial_energy,
        final_energy_kcal_per_mol=current_energy,
        best_energy_kcal_per_mol=best_energy,
        initial_max_tangent_force_kcal_per_mol_angstrom=initial_tangent_force,
        final_max_tangent_force_kcal_per_mol_angstrom=current_tangent_force,
        final_max_constraint_residual_angstrom=current_constraint_residual,
        final_coordinates_angstrom=coordinates,
        accepted_iterations=accepted_iterations,
        accepted_armijo_iterations=sum(
            row.outcome == "accepted_armijo" for row in observations
        ),
        accepted_stationarity_polish_iterations=sum(
            row.outcome == "accepted_stationarity_polish"
            for row in observations
        ),
        rejected_trials=rejected_trials,
        energy_evaluation_count=evaluation_count,
        checkpoint=state,
    )


def independent_constraint_stationarity_default_configuration_document() -> (
    dict[str, object]
):
    """Return and self-check the result-free independent configuration."""

    config = IndependentConstraintStationarityConfig()
    if (
        config.fingerprint_sha256
        != INDEPENDENT_CONSTRAINT_STATIONARITY_DEFAULT_CONFIG_SHA256
    ):
        raise IndependentConstraintStationarityError(
            "independent stationarity default configuration drifted"
        )
    return {
        **config.to_dict(),
        "configuration_sha256": config.fingerprint_sha256,
        "scientifically_validated": False,
        "claim_safe": False,
    }


__all__ = [
    "INDEPENDENT_CONSTRAINT_STATIONARITY_CHECKPOINT_SCHEMA_ID",
    "INDEPENDENT_CONSTRAINT_STATIONARITY_CONFIG_SCHEMA_ID",
    "INDEPENDENT_CONSTRAINT_STATIONARITY_DEFAULT_CONFIG_SHA256",
    "INDEPENDENT_CONSTRAINT_STATIONARITY_ORACLE_ID",
    "INDEPENDENT_CONSTRAINT_STATIONARITY_RESULT_SCHEMA_ID",
    "IndependentConstraintStationarityCheckpoint",
    "IndependentConstraintStationarityConfig",
    "IndependentConstraintStationarityError",
    "IndependentConstraintStationarityObservation",
    "IndependentConstraintStationarityResult",
    "evaluate_independent_constraint_stationarity",
    "independent_constraint_stationarity_default_configuration_document",
]
