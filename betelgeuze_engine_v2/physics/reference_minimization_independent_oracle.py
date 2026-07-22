"""Import-separated independent minimization oracle.

This implementation depends only on the Python standard library and the
already-audited scalar analytic oracle.  It does not import an Engine v2
evaluator, minimizer, constraint implementation, solvation implementation,
materializer, protocol, Torch, NumPy, or an external molecular solver.

The oracle is an implementation artifact.  Test executions are not production
validation results and cannot authorize scientific or product promotion.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import math
from numbers import Real
from typing import Any

from .reference_validation_oracle import (
    COULOMB_KCAL_ANGSTROM_PER_MOL_E2,
    IndependentAnalyticOracleInput,
    evaluate_independent_analytic_oracle,
)


INDEPENDENT_MINIMIZATION_ORACLE_SCHEMA_ID = (
    "betelgeuze.engine_v2_independent_minimization_oracle/2.1.0"
)
INDEPENDENT_MINIMIZATION_ORACLE_INPUT_SCHEMA_ID = (
    "betelgeuze.engine_v2_independent_minimization_oracle_input/1.1.0"
)
INDEPENDENT_MINIMIZATION_ORACLE_CHECKPOINT_SCHEMA_ID = (
    "betelgeuze.engine_v2_independent_minimization_oracle_checkpoint/2.1.0"
)
INDEPENDENT_MINIMIZATION_ORACLE_ID = (
    "cpu_reference_minimization_independent_oracle/2.1.0"
)
INDEPENDENT_MINIMIZATION_ORACLE_VERSION = "2.1.0"
INDEPENDENT_MINIMIZATION_CONSTRAINT_PROJECTION_CONVERGENCE_TOLERANCE_SCALE = 0.5


class IndependentMinimizationOracleError(ValueError):
    """The independent minimization input or state is invalid."""


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
        raise IndependentMinimizationOracleError(
            "independent minimization payload is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _finite(value: Real, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise IndependentMinimizationOracleError(f"{name} must be a real number")
    number = float(value)
    if not math.isfinite(number):
        raise IndependentMinimizationOracleError(f"{name} must be finite")
    return number


def _positive(value: Real, *, name: str, allow_zero: bool = False) -> float:
    number = _finite(value, name=name)
    if number < 0.0 if allow_zero else number <= 0.0:
        relation = "non-negative" if allow_zero else "positive"
        raise IndependentMinimizationOracleError(f"{name} must be {relation}")
    return number


def _integer(
    value: int,
    *,
    name: str,
    minimum: int = 0,
    maximum: int = 1_000_000,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise IndependentMinimizationOracleError(f"{name} must be an integer")
    result = int(value)
    if result < minimum or result > maximum:
        raise IndependentMinimizationOracleError(
            f"{name} must be in [{minimum},{maximum}]"
        )
    return result


def _digest(value: str | None, *, name: str, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise IndependentMinimizationOracleError(f"{name} must be a lowercase SHA-256")
    return value


Coordinates = tuple[tuple[float, float, float], ...]
Forces = tuple[tuple[float, float, float], ...]


def _coordinates(value: object, *, atom_count: int) -> Coordinates:
    if not isinstance(value, (tuple, list)) or len(value) != atom_count:
        raise IndependentMinimizationOracleError(
            "coordinates must exactly cover every atom"
        )
    rows = tuple(
        tuple(_finite(item, name="coordinate") for item in row)  # type: ignore[arg-type]
        for row in value
    )
    if any(len(row) != 3 for row in rows):
        raise IndependentMinimizationOracleError("coordinates must have [atom,3] shape")
    return rows  # type: ignore[return-value]


def _coordinate_sha256(value: Coordinates) -> str:
    return _sha256([[float(item).hex() for item in row] for row in value])


@dataclass(frozen=True, slots=True)
class IndependentMinimizationCoordinateTraceStep:
    """One exact independent-oracle evaluation coordinate state."""

    evaluation_index: int
    iteration: int
    trial: int
    outcome: str
    raw_coordinates_angstrom: Coordinates
    evaluated_coordinates_angstrom: Coordinates
    energy_kcal_per_mol: float | None

    def __post_init__(self) -> None:
        _integer(self.evaluation_index, name="trace evaluation index", minimum=1)
        _integer(self.iteration, name="trace iteration")
        _integer(self.trial, name="trace trial")
        if self.outcome not in {
            "initial",
            "accepted",
            "rejected_constraint_projection",
            "rejected_projected_displacement",
            "rejected_force_projection",
            "rejected_non_descent",
            "rejected_armijo",
        }:
            raise IndependentMinimizationOracleError(
                "coordinate trace outcome is invalid"
            )
        atom_count = len(self.raw_coordinates_angstrom)
        if atom_count < 1:
            raise IndependentMinimizationOracleError(
                "coordinate trace must cover every atom"
            )
        object.__setattr__(
            self,
            "raw_coordinates_angstrom",
            _coordinates(self.raw_coordinates_angstrom, atom_count=atom_count),
        )
        object.__setattr__(
            self,
            "evaluated_coordinates_angstrom",
            _coordinates(self.evaluated_coordinates_angstrom, atom_count=atom_count),
        )
        if self.energy_kcal_per_mol is not None:
            object.__setattr__(
                self,
                "energy_kcal_per_mol",
                _finite(self.energy_kcal_per_mol, name="trace energy"),
            )

    def projection(self) -> dict[str, Any]:
        raw_hex = [
            [float(item).hex() for item in row]
            for row in self.raw_coordinates_angstrom
        ]
        evaluated_hex = [
            [float(item).hex() for item in row]
            for row in self.evaluated_coordinates_angstrom
        ]
        return {
            "evaluation_index": self.evaluation_index,
            "iteration": self.iteration,
            "trial": self.trial,
            "outcome": self.outcome,
            "raw_coordinates_angstrom_hex": raw_hex,
            "raw_coordinates_sha256": _sha256(raw_hex),
            "evaluated_coordinates_angstrom_hex": evaluated_hex,
            "evaluated_coordinates_sha256": _sha256(evaluated_hex),
            "energy_kcal_per_mol": self.energy_kcal_per_mol,
        }

    @property
    def step_identity_sha256(self) -> str:
        return _sha256(self.projection())

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.projection(),
            "step_identity_sha256": self.step_identity_sha256,
        }


_REJECTED_COORDINATE_TRACE_OUTCOMES = frozenset(
    {
        "rejected_constraint_projection",
        "rejected_projected_displacement",
        "rejected_force_projection",
        "rejected_non_descent",
        "rejected_armijo",
    }
)


def _validate_coordinate_trace(
    coordinate_trace: tuple[IndependentMinimizationCoordinateTraceStep, ...],
    *,
    accepted_iterations: int,
    rejected_evaluations: int,
    evaluation_count: int,
    accepted_energy_trace_kcal_per_mol: tuple[float, ...],
    state_coordinates_angstrom: Coordinates | None,
    initial_energy_kcal_per_mol: float | None,
    current_energy_kcal_per_mol: float | None,
    context: str,
) -> None:
    """Validate trace order, counters, ledger, and current-state identity."""

    _integer(accepted_iterations, name=f"{context} accepted iterations")
    _integer(rejected_evaluations, name=f"{context} rejected evaluations")
    _integer(evaluation_count, name=f"{context} evaluation count")
    if not isinstance(coordinate_trace, tuple) or any(
        not isinstance(row, IndependentMinimizationCoordinateTraceStep)
        for row in coordinate_trace
    ):
        raise IndependentMinimizationOracleError(
            f"{context} coordinate trace must contain exact trace steps"
        )
    if len(coordinate_trace) != evaluation_count or [
        row.evaluation_index for row in coordinate_trace
    ] != list(range(1, evaluation_count + 1)):
        raise IndependentMinimizationOracleError(
            f"{context} coordinate trace evaluation sequence is invalid"
        )
    if not coordinate_trace:
        if (
            accepted_iterations != 0
            or rejected_evaluations != 0
            or accepted_energy_trace_kcal_per_mol
            or state_coordinates_angstrom is not None
            or initial_energy_kcal_per_mol is not None
            or current_energy_kcal_per_mol is not None
        ):
            raise IndependentMinimizationOracleError(
                f"empty {context} coordinate trace disagrees with evaluation state"
            )
        return

    initial = coordinate_trace[0]
    if (
        initial.outcome != "initial"
        or initial.iteration != 0
        or initial.trial != 0
        or initial.energy_kcal_per_mol is None
    ):
        raise IndependentMinimizationOracleError(
            f"{context} coordinate trace initial step is invalid"
        )
    atom_count = len(initial.evaluated_coordinates_angstrom)
    expected_iteration = 1
    expected_trial = 0
    accepted_rows = [initial]
    rejected_count = 0
    for row in coordinate_trace[1:]:
        if (
            len(row.raw_coordinates_angstrom) != atom_count
            or len(row.evaluated_coordinates_angstrom) != atom_count
        ):
            raise IndependentMinimizationOracleError(
                f"{context} coordinate trace atom count drifted"
            )
        if row.iteration != expected_iteration or row.trial != expected_trial:
            raise IndependentMinimizationOracleError(
                f"{context} coordinate trace iteration or trial order is invalid"
            )
        if row.outcome == "accepted":
            if row.energy_kcal_per_mol is None:
                raise IndependentMinimizationOracleError(
                    f"{context} accepted coordinate trace step requires energy"
                )
            accepted_rows.append(row)
            expected_iteration += 1
            expected_trial = 0
        elif row.outcome in _REJECTED_COORDINATE_TRACE_OUTCOMES:
            if row.outcome in {
                "rejected_constraint_projection",
                "rejected_projected_displacement",
            }:
                if row.energy_kcal_per_mol is not None:
                    raise IndependentMinimizationOracleError(
                        f"{context} pre-energy rejected trace step must omit energy"
                    )
            elif row.energy_kcal_per_mol is None:
                raise IndependentMinimizationOracleError(
                    f"{context} evaluated rejected trace step requires energy"
                )
            rejected_count += 1
            expected_trial += 1
        else:
            raise IndependentMinimizationOracleError(
                f"{context} coordinate trace contains a repeated initial step"
            )
    if len(accepted_rows) != accepted_iterations + 1:
        raise IndependentMinimizationOracleError(
            f"{context} coordinate trace accepted count is inconsistent"
        )
    if rejected_count != rejected_evaluations:
        raise IndependentMinimizationOracleError(
            f"{context} coordinate trace rejected count is inconsistent"
        )
    observed_energy_trace = tuple(
        row.energy_kcal_per_mol for row in accepted_rows
    )
    if observed_energy_trace != accepted_energy_trace_kcal_per_mol:
        raise IndependentMinimizationOracleError(
            f"{context} coordinate and energy traces are inconsistent"
        )
    if (
        initial_energy_kcal_per_mol != initial.energy_kcal_per_mol
        or current_energy_kcal_per_mol != accepted_rows[-1].energy_kcal_per_mol
    ):
        raise IndependentMinimizationOracleError(
            f"{context} coordinate trace energy endpoints are inconsistent"
        )
    if state_coordinates_angstrom is None:
        raise IndependentMinimizationOracleError(
            f"{context} evaluated coordinate trace requires current coordinates"
        )
    normalized_state = _coordinates(
        state_coordinates_angstrom,
        atom_count=atom_count,
    )
    if normalized_state != accepted_rows[-1].evaluated_coordinates_angstrom:
        raise IndependentMinimizationOracleError(
            f"{context} current coordinates do not match the last accepted trace step"
        )


@dataclass(frozen=True, slots=True)
class IndependentMinimizationOracleInput:
    """Primitive, result-free input for one independent minimization case."""

    case_id: str
    case_input_sha256: str
    expected_outcome: str
    expected_error_code: str | None
    energy_input: IndependentAnalyticOracleInput
    constraints: tuple[tuple[int, int, float, float], ...] = ()
    fixed_born_radii_angstrom: tuple[float, ...] | None = None
    fixed_born_solute_dielectric: float = 1.0
    fixed_born_solvent_dielectric: float = 78.5
    max_iterations: int = 64
    max_backtracks: int = 16
    initial_step_size_angstrom2_mol_per_kcal: float = 1.0e-3
    backtrack_factor: float = 0.5
    armijo_constant: float = 1.0e-4
    maximum_atom_displacement_angstrom: float = 0.05
    force_tolerance_kcal_per_mol_angstrom: float = 1.0e-8
    constraint_projection_max_iterations: int = 100
    constraint_max_pair_correction_angstrom: float = 0.25
    force_projection_max_sweeps: int = 100
    force_projection_tolerance_kcal_per_mol_angstrom: float = 1.0e-8
    pause_after_accepted_iterations: int | None = None
    checkpoint_topology_sha256: str | None = None
    runtime_topology_sha256: str | None = None
    checkpoint_parameter_sha256: str | None = None
    runtime_parameter_sha256: str | None = None
    checkpoint_solvation_sha256: str | None = None
    runtime_solvation_sha256: str | None = None
    schema_id: str = INDEPENDENT_MINIMIZATION_ORACLE_INPUT_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != INDEPENDENT_MINIMIZATION_ORACLE_INPUT_SCHEMA_ID:
            raise IndependentMinimizationOracleError(
                "unsupported independent minimization input schema"
            )
        if not isinstance(self.case_id, str) or not self.case_id:
            raise IndependentMinimizationOracleError("case_id must be non-empty")
        object.__setattr__(
            self,
            "case_input_sha256",
            _digest(self.case_input_sha256, name="case input identity"),
        )
        if self.expected_outcome not in {"pass", "fail_closed"}:
            raise IndependentMinimizationOracleError(
                "expected_outcome must be pass or fail_closed"
            )
        if self.expected_outcome == "pass" and self.expected_error_code is not None:
            raise IndependentMinimizationOracleError(
                "passing input cannot declare an error code"
            )
        if self.expected_outcome == "fail_closed" and not self.expected_error_code:
            raise IndependentMinimizationOracleError(
                "fail-closed input requires an error code"
            )
        if not isinstance(self.energy_input, IndependentAnalyticOracleInput):
            raise IndependentMinimizationOracleError(
                "energy_input must be an IndependentAnalyticOracleInput"
            )
        constraints: list[tuple[int, int, float, float]] = []
        for row in self.constraints:
            if len(row) != 4:
                raise IndependentMinimizationOracleError(
                    "constraint rows must contain four values"
                )
            atom_i = _integer(
                row[0],
                name="constraint atom_i",
                maximum=self.energy_input.atom_count - 1,
            )
            atom_j = _integer(
                row[1],
                name="constraint atom_j",
                maximum=self.energy_input.atom_count - 1,
            )
            if atom_i == atom_j:
                raise IndependentMinimizationOracleError(
                    "constraint atom indices must be distinct"
                )
            constraints.append(
                (
                    min(atom_i, atom_j),
                    max(atom_i, atom_j),
                    _positive(row[2], name="constraint target"),
                    _positive(row[3], name="constraint tolerance"),
                )
            )
        if len({row[:2] for row in constraints}) != len(constraints):
            raise IndependentMinimizationOracleError("constraints must be unique")
        object.__setattr__(self, "constraints", tuple(constraints))

        radii = self.fixed_born_radii_angstrom
        if radii is not None:
            normalized = tuple(
                _positive(value, name="fixed Born radius") for value in radii
            )
            if len(normalized) != self.energy_input.atom_count:
                raise IndependentMinimizationOracleError(
                    "fixed Born radii must cover every atom"
                )
            object.__setattr__(self, "fixed_born_radii_angstrom", normalized)
        solute = _positive(
            self.fixed_born_solute_dielectric,
            name="fixed Born solute dielectric",
        )
        solvent = _positive(
            self.fixed_born_solvent_dielectric,
            name="fixed Born solvent dielectric",
        )
        if solvent <= solute:
            raise IndependentMinimizationOracleError(
                "fixed Born solvent dielectric must exceed solute dielectric"
            )
        object.__setattr__(self, "fixed_born_solute_dielectric", solute)
        object.__setattr__(self, "fixed_born_solvent_dielectric", solvent)

        for name in (
            "max_iterations",
            "constraint_projection_max_iterations",
            "force_projection_max_sweeps",
        ):
            object.__setattr__(
                self,
                name,
                _integer(getattr(self, name), name=name, minimum=1),
            )
        object.__setattr__(
            self,
            "max_backtracks",
            _integer(self.max_backtracks, name="max_backtracks", minimum=0),
        )
        for name in (
            "initial_step_size_angstrom2_mol_per_kcal",
            "maximum_atom_displacement_angstrom",
            "force_tolerance_kcal_per_mol_angstrom",
            "constraint_max_pair_correction_angstrom",
            "force_projection_tolerance_kcal_per_mol_angstrom",
        ):
            object.__setattr__(
                self,
                name,
                _positive(getattr(self, name), name=name),
            )
        backtrack = _positive(self.backtrack_factor, name="backtrack_factor")
        armijo = _positive(self.armijo_constant, name="armijo_constant")
        if backtrack >= 1.0 or armijo >= 1.0:
            raise IndependentMinimizationOracleError(
                "backtrack_factor and armijo_constant must be below one"
            )
        object.__setattr__(self, "backtrack_factor", backtrack)
        object.__setattr__(self, "armijo_constant", armijo)
        if self.pause_after_accepted_iterations is not None:
            object.__setattr__(
                self,
                "pause_after_accepted_iterations",
                _integer(
                    self.pause_after_accepted_iterations,
                    name="pause_after_accepted_iterations",
                    maximum=self.max_iterations,
                ),
            )
        for name in (
            "checkpoint_topology_sha256",
            "runtime_topology_sha256",
            "checkpoint_parameter_sha256",
            "runtime_parameter_sha256",
            "checkpoint_solvation_sha256",
            "runtime_solvation_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _digest(getattr(self, name), name=name, optional=True),
            )

    def compatibility_projection(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "oracle_id": INDEPENDENT_MINIMIZATION_ORACLE_ID,
            "oracle_version": INDEPENDENT_MINIMIZATION_ORACLE_VERSION,
            "case_id": self.case_id,
            "case_input_sha256": self.case_input_sha256,
            "expected_outcome": self.expected_outcome,
            "expected_error_code": self.expected_error_code,
            "energy_input": self.energy_input.to_dict(),
            "constraints": [list(row) for row in self.constraints],
            "fixed_born_radii_angstrom": (
                None
                if self.fixed_born_radii_angstrom is None
                else list(self.fixed_born_radii_angstrom)
            ),
            "fixed_born_solute_dielectric": self.fixed_born_solute_dielectric,
            "fixed_born_solvent_dielectric": self.fixed_born_solvent_dielectric,
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
            "force_tolerance_kcal_per_mol_angstrom": (
                self.force_tolerance_kcal_per_mol_angstrom
            ),
            "constraint_projection_max_iterations": (
                self.constraint_projection_max_iterations
            ),
            "constraint_max_pair_correction_angstrom": (
                self.constraint_max_pair_correction_angstrom
            ),
            "constraint_projection_convergence_tolerance_scale": (
                INDEPENDENT_MINIMIZATION_CONSTRAINT_PROJECTION_CONVERGENCE_TOLERANCE_SCALE
            ),
            "force_projection_max_sweeps": self.force_projection_max_sweeps,
            "force_projection_tolerance_kcal_per_mol_angstrom": (
                self.force_projection_tolerance_kcal_per_mol_angstrom
            ),
            "checkpoint_topology_sha256": self.checkpoint_topology_sha256,
            "runtime_topology_sha256": self.runtime_topology_sha256,
            "checkpoint_parameter_sha256": self.checkpoint_parameter_sha256,
            "runtime_parameter_sha256": self.runtime_parameter_sha256,
            "checkpoint_solvation_sha256": self.checkpoint_solvation_sha256,
            "runtime_solvation_sha256": self.runtime_solvation_sha256,
            "parameter_origin": "synthetic_protocol_values_not_fit_data",
            "scientifically_validated": False,
        }

    @property
    def compatibility_sha256(self) -> str:
        return _sha256(self.compatibility_projection())

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.compatibility_projection(),
            "pause_after_accepted_iterations": self.pause_after_accepted_iterations,
        }

    @property
    def input_sha256(self) -> str:
        return _sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class IndependentMinimizationCheckpoint:
    """Canonical in-memory restart state for the independent oracle."""

    compatibility_sha256: str
    coordinates_angstrom: Coordinates
    accepted_iterations: int
    rejected_evaluations: int
    evaluation_count: int
    initial_energy_kcal_per_mol: float
    initial_max_force_kcal_per_mol_angstrom: float
    current_energy_kcal_per_mol: float
    current_max_force_kcal_per_mol_angstrom: float
    current_constraint_residual_angstrom: float
    accepted_energy_trace_kcal_per_mol: tuple[float, ...]
    coordinate_trace: tuple[IndependentMinimizationCoordinateTraceStep, ...]
    checkpoint_sha256: str
    schema_id: str = INDEPENDENT_MINIMIZATION_ORACLE_CHECKPOINT_SCHEMA_ID

    def projection(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "oracle_id": INDEPENDENT_MINIMIZATION_ORACLE_ID,
            "compatibility_sha256": self.compatibility_sha256,
            "coordinates_angstrom_hex": [
                [float(value).hex() for value in row]
                for row in self.coordinates_angstrom
            ],
            "coordinates_sha256": _coordinate_sha256(self.coordinates_angstrom),
            "accepted_iterations": self.accepted_iterations,
            "rejected_evaluations": self.rejected_evaluations,
            "evaluation_count": self.evaluation_count,
            "initial_energy_kcal_per_mol": self.initial_energy_kcal_per_mol,
            "initial_max_force_kcal_per_mol_angstrom": (
                self.initial_max_force_kcal_per_mol_angstrom
            ),
            "current_energy_kcal_per_mol": self.current_energy_kcal_per_mol,
            "current_max_force_kcal_per_mol_angstrom": (
                self.current_max_force_kcal_per_mol_angstrom
            ),
            "current_constraint_residual_angstrom": (
                self.current_constraint_residual_angstrom
            ),
            "accepted_energy_trace_kcal_per_mol": list(
                self.accepted_energy_trace_kcal_per_mol
            ),
            "coordinate_trace": [row.to_dict() for row in self.coordinate_trace],
            "coordinate_trace_sha256": _sha256(
                [row.to_dict() for row in self.coordinate_trace]
            ),
        }

    def __post_init__(self) -> None:
        if self.schema_id != INDEPENDENT_MINIMIZATION_ORACLE_CHECKPOINT_SCHEMA_ID:
            raise IndependentMinimizationOracleError(
                "unsupported independent checkpoint schema"
            )
        _digest(self.compatibility_sha256, name="checkpoint compatibility")
        _digest(self.checkpoint_sha256, name="checkpoint identity")
        _validate_coordinate_trace(
            self.coordinate_trace,
            accepted_iterations=self.accepted_iterations,
            rejected_evaluations=self.rejected_evaluations,
            evaluation_count=self.evaluation_count,
            accepted_energy_trace_kcal_per_mol=(
                self.accepted_energy_trace_kcal_per_mol
            ),
            state_coordinates_angstrom=self.coordinates_angstrom,
            initial_energy_kcal_per_mol=self.initial_energy_kcal_per_mol,
            current_energy_kcal_per_mol=self.current_energy_kcal_per_mol,
            context="checkpoint",
        )
        if _sha256(self.projection()) != self.checkpoint_sha256:
            raise IndependentMinimizationOracleError("checkpoint digest mismatch")

    def to_dict(self) -> dict[str, Any]:
        return {**self.projection(), "checkpoint_sha256": self.checkpoint_sha256}


@dataclass(frozen=True, slots=True)
class IndependentMinimizationOracleResult:
    """One independent in-memory result; never a validation receipt."""

    input_sha256: str
    status: str
    failure_code: str | None
    initial_energy_kcal_per_mol: float | None
    final_energy_kcal_per_mol: float | None
    initial_max_force_kcal_per_mol_angstrom: float | None
    final_max_force_kcal_per_mol_angstrom: float | None
    final_constraint_residual_angstrom: float | None
    accepted_iterations: int
    rejected_evaluations: int
    evaluation_count: int
    final_coordinates_angstrom: Coordinates | None
    accepted_energy_trace_kcal_per_mol: tuple[float, ...]
    coordinate_trace: tuple[IndependentMinimizationCoordinateTraceStep, ...]
    checkpoint: IndependentMinimizationCheckpoint | None
    schema_id: str = INDEPENDENT_MINIMIZATION_ORACLE_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != INDEPENDENT_MINIMIZATION_ORACLE_SCHEMA_ID:
            raise IndependentMinimizationOracleError(
                "unsupported independent minimization result schema"
            )
        _validate_coordinate_trace(
            self.coordinate_trace,
            accepted_iterations=self.accepted_iterations,
            rejected_evaluations=self.rejected_evaluations,
            evaluation_count=self.evaluation_count,
            accepted_energy_trace_kcal_per_mol=(
                self.accepted_energy_trace_kcal_per_mol
            ),
            state_coordinates_angstrom=self.final_coordinates_angstrom,
            initial_energy_kcal_per_mol=self.initial_energy_kcal_per_mol,
            current_energy_kcal_per_mol=self.final_energy_kcal_per_mol,
            context="result",
        )
        if self.checkpoint is not None and (
            self.checkpoint.coordinate_trace != self.coordinate_trace
            or self.checkpoint.coordinates_angstrom != self.final_coordinates_angstrom
            or self.checkpoint.accepted_iterations != self.accepted_iterations
            or self.checkpoint.rejected_evaluations != self.rejected_evaluations
            or self.checkpoint.evaluation_count != self.evaluation_count
            or self.checkpoint.accepted_energy_trace_kcal_per_mol
            != self.accepted_energy_trace_kcal_per_mol
        ):
            raise IndependentMinimizationOracleError(
                "result coordinate trace disagrees with its checkpoint"
            )

    @property
    def converged(self) -> bool:
        return self.status == "converged"

    def projection(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "oracle_id": INDEPENDENT_MINIMIZATION_ORACLE_ID,
            "oracle_version": INDEPENDENT_MINIMIZATION_ORACLE_VERSION,
            "input_sha256": self.input_sha256,
            "status": self.status,
            "failure_code": self.failure_code,
            "converged": self.converged,
            "initial_energy_kcal_per_mol": self.initial_energy_kcal_per_mol,
            "final_energy_kcal_per_mol": self.final_energy_kcal_per_mol,
            "initial_max_force_kcal_per_mol_angstrom": (
                self.initial_max_force_kcal_per_mol_angstrom
            ),
            "final_max_force_kcal_per_mol_angstrom": (
                self.final_max_force_kcal_per_mol_angstrom
            ),
            "final_constraint_residual_angstrom": (
                self.final_constraint_residual_angstrom
            ),
            "accepted_iterations": self.accepted_iterations,
            "rejected_evaluations": self.rejected_evaluations,
            "evaluation_count": self.evaluation_count,
            "final_coordinates_angstrom_hex": (
                None
                if self.final_coordinates_angstrom is None
                else [
                    [float(value).hex() for value in row]
                    for row in self.final_coordinates_angstrom
                ]
            ),
            "final_coordinates_sha256": (
                None
                if self.final_coordinates_angstrom is None
                else _coordinate_sha256(self.final_coordinates_angstrom)
            ),
            "accepted_energy_trace_kcal_per_mol": list(
                self.accepted_energy_trace_kcal_per_mol
            ),
            "coordinate_trace": [row.to_dict() for row in self.coordinate_trace],
            "coordinate_trace_sha256": _sha256(
                [row.to_dict() for row in self.coordinate_trace]
            ),
            "checkpoint_sha256": (
                None if self.checkpoint is None else self.checkpoint.checkpoint_sha256
            ),
            "validation_receipt": False,
            "scientifically_validated": False,
            "product_qualified": False,
            "claim_safe": False,
        }

    @property
    def result_sha256(self) -> str:
        return _sha256(self.projection())

    def to_dict(self) -> dict[str, Any]:
        return {**self.projection(), "result_sha256": self.result_sha256}


def _subtract(
    first: tuple[float, float, float], second: tuple[float, float, float]
) -> tuple[float, float, float]:
    return (
        first[0] - second[0],
        first[1] - second[1],
        first[2] - second[2],
    )


def _add(
    first: tuple[float, float, float], second: tuple[float, float, float]
) -> tuple[float, float, float]:
    return (
        first[0] + second[0],
        first[1] + second[1],
        first[2] + second[2],
    )


def _scale(
    vector: tuple[float, float, float], scalar: float
) -> tuple[float, float, float]:
    return vector[0] * scalar, vector[1] * scalar, vector[2] * scalar


def _dot(
    first: tuple[float, float, float], second: tuple[float, float, float]
) -> float:
    return first[0] * second[0] + first[1] * second[1] + first[2] * second[2]


def _norm(vector: tuple[float, float, float]) -> float:
    return math.sqrt(_dot(vector, vector))


def _minimum_image(
    vector: tuple[float, float, float],
    source: IndependentAnalyticOracleInput,
) -> tuple[float, float, float]:
    if source.orthorhombic_cell_angstrom is None:
        return vector
    return tuple(
        component
        - (
            round(component / source.orthorhombic_cell_angstrom[axis])
            * source.orthorhombic_cell_angstrom[axis]
            if source.periodic_axes[axis]
            else 0.0
        )
        for axis, component in enumerate(vector)
    )  # type: ignore[return-value]


def _pair_vector(
    coordinates: Coordinates,
    atom_i: int,
    atom_j: int,
    source: IndependentAnalyticOracleInput,
) -> tuple[float, float, float]:
    return _minimum_image(_subtract(coordinates[atom_i], coordinates[atom_j]), source)


def _constraint_residual(
    coordinates: Coordinates,
    row: tuple[int, int, float, float],
    source: IndependentAnalyticOracleInput,
) -> float:
    return _norm(_pair_vector(coordinates, row[0], row[1], source)) - row[2]


def _project_constraints(
    coordinates: Coordinates,
    source: IndependentMinimizationOracleInput,
) -> tuple[Coordinates, float, bool, str | None]:
    if not source.constraints:
        return coordinates, 0.0, True, None
    current = coordinates
    degrees = [0] * source.energy_input.atom_count
    for atom_i, atom_j, _, _ in source.constraints:
        degrees[atom_i] += 1
        degrees[atom_j] += 1
    relaxation = max(degrees, default=1)
    for iteration in range(source.constraint_projection_max_iterations + 1):
        residuals = tuple(
            _constraint_residual(current, row, source.energy_input)
            for row in source.constraints
        )
        maximum = max((abs(value) for value in residuals), default=0.0)
        if all(
            abs(value)
            <= (
                INDEPENDENT_MINIMIZATION_CONSTRAINT_PROJECTION_CONVERGENCE_TOLERANCE_SCALE
                * row[3]
            )
            for value, row in zip(residuals, source.constraints)
        ):
            return current, maximum, True, None
        if iteration == source.constraint_projection_max_iterations:
            return current, maximum, False, "constraint_projection_exhausted"
        updates = [(0.0, 0.0, 0.0) for _ in current]
        for row, residual in zip(source.constraints, residuals):
            atom_i, atom_j = row[0], row[1]
            vector = _pair_vector(current, atom_i, atom_j, source.energy_input)
            distance = _norm(vector)
            if distance <= 1.0e-12:
                return current, maximum, False, "constraint_pair_has_zero_distance"
            correction = max(
                -source.constraint_max_pair_correction_angstrom,
                min(source.constraint_max_pair_correction_angstrom, residual),
            )
            direction = _scale(vector, 1.0 / distance)
            updates[atom_i] = _add(
                updates[atom_i], _scale(direction, -0.5 * correction)
            )
            updates[atom_j] = _add(updates[atom_j], _scale(direction, 0.5 * correction))
        current = tuple(
            _add(row, _scale(update, 1.0 / relaxation))
            for row, update in zip(current, updates)
        )
    raise AssertionError("constraint projection loop must return")


def _fixed_born(
    source: IndependentMinimizationOracleInput,
    coordinates: Coordinates,
) -> tuple[float, Forces]:
    radii = source.fixed_born_radii_angstrom
    atom_count = source.energy_input.atom_count
    zero_forces = tuple((0.0, 0.0, 0.0) for _ in range(atom_count))
    if radii is None:
        return 0.0, zero_forces
    if source.energy_input.orthorhombic_cell_angstrom is not None or any(
        source.energy_input.periodic_axes
    ):
        raise IndependentMinimizationOracleError("periodic_fixed_born_not_supported")
    charges = tuple(row[3] for row in source.energy_input.atom_nonbonded)
    coefficient = (
        -0.5
        * COULOMB_KCAL_ANGSTROM_PER_MOL_E2
        * (
            1.0 / source.fixed_born_solute_dielectric
            - 1.0 / source.fixed_born_solvent_dielectric
        )
    )
    energy = coefficient * sum(
        charge * charge / radius for charge, radius in zip(charges, radii)
    )
    forces = [list(row) for row in zero_forces]
    for atom_i in range(atom_count):
        for atom_j in range(atom_i + 1, atom_count):
            vector = _subtract(coordinates[atom_i], coordinates[atom_j])
            distance_squared = _dot(vector, vector)
            if distance_squared < (
                source.energy_input.minimum_pair_distance_angstrom**2
            ):
                raise IndependentMinimizationOracleError(
                    "fixed_born_pair_below_minimum_distance"
                )
            radius_product = radii[atom_i] * radii[atom_j]
            exponential = math.exp(-distance_squared / (4.0 * radius_product))
            pair_function = math.sqrt(distance_squared + radius_product * exponential)
            charge_product = charges[atom_i] * charges[atom_j]
            energy += 2.0 * coefficient * charge_product / pair_function
            derivative_factor = 1.0 - 0.25 * exponential
            force_scale = (
                2.0
                * coefficient
                * charge_product
                * derivative_factor
                / (pair_function**3)
            )
            pair_force = _scale(vector, force_scale)
            for axis in range(3):
                forces[atom_i][axis] += pair_force[axis]
                forces[atom_j][axis] -= pair_force[axis]
    return energy, tuple(tuple(row) for row in forces)  # type: ignore[return-value]


def _evaluate(
    source: IndependentMinimizationOracleInput,
    coordinates: Coordinates,
) -> tuple[float, Forces]:
    analytic_input = replace(
        source.energy_input,
        coordinates_angstrom=coordinates,
    )
    base = evaluate_independent_analytic_oracle(analytic_input)
    born_energy, born_forces = _fixed_born(source, coordinates)
    forces = tuple(
        tuple(
            base_value + born_value
            for base_value, born_value in zip(base_row, born_row)
        )
        for base_row, born_row in zip(
            base.forces_kcal_per_mol_angstrom,
            born_forces,
        )
    )
    energy = base.total_energy_kcal_per_mol + born_energy
    if not math.isfinite(energy) or any(
        not math.isfinite(value) for row in forces for value in row
    ):
        raise IndependentMinimizationOracleError("nonfinite_energy_or_force")
    return energy, forces  # type: ignore[return-value]


def _project_forces(
    source: IndependentMinimizationOracleInput,
    coordinates: Coordinates,
    forces: Forces,
) -> tuple[Forces, float, bool]:
    projected = forces
    if not source.constraints:
        maximum = max((_norm(row) for row in projected), default=0.0)
        return projected, maximum, True
    degrees = [0] * source.energy_input.atom_count
    for atom_i, atom_j, _, _ in source.constraints:
        degrees[atom_i] += 1
        degrees[atom_j] += 1
    relaxation = max(degrees, default=1)
    for _ in range(source.force_projection_max_sweeps):
        updates = [(0.0, 0.0, 0.0) for _ in projected]
        for atom_i, atom_j, _, _ in source.constraints:
            vector = _pair_vector(coordinates, atom_i, atom_j, source.energy_input)
            distance = _norm(vector)
            if distance <= 1.0e-12:
                raise IndependentMinimizationOracleError(
                    "constraint_tangent_zero_distance"
                )
            direction = _scale(vector, 1.0 / distance)
            relative = _dot(_subtract(projected[atom_i], projected[atom_j]), direction)
            correction = _scale(direction, 0.5 * relative)
            updates[atom_i] = _subtract(updates[atom_i], correction)
            updates[atom_j] = _add(updates[atom_j], correction)
        projected = tuple(
            _add(row, _scale(update, 1.0 / relaxation))
            for row, update in zip(projected, updates)
        )
        residuals = []
        for atom_i, atom_j, _, _ in source.constraints:
            vector = _pair_vector(coordinates, atom_i, atom_j, source.energy_input)
            direction = _scale(vector, 1.0 / _norm(vector))
            residuals.append(
                abs(_dot(_subtract(projected[atom_i], projected[atom_j]), direction))
            )
        if max(residuals, default=0.0) <= (
            source.force_projection_tolerance_kcal_per_mol_angstrom
        ):
            maximum = max((_norm(row) for row in projected), default=0.0)
            return projected, maximum, True
    maximum = max((_norm(row) for row in projected), default=0.0)
    return projected, maximum, False


def _fail_closed(
    source: IndependentMinimizationOracleInput,
    code: str,
    *,
    initial_energy: float | None = None,
    initial_max_force: float | None = None,
    current_energy: float | None = None,
    current_max_force: float | None = None,
    constraint_residual: float | None = None,
    accepted_iterations: int = 0,
    rejected_evaluations: int = 0,
    evaluation_count: int = 0,
    coordinates: Coordinates | None = None,
    energy_trace: tuple[float, ...] = (),
    coordinate_trace: tuple[IndependentMinimizationCoordinateTraceStep, ...] = (),
) -> IndependentMinimizationOracleResult:
    return IndependentMinimizationOracleResult(
        input_sha256=source.input_sha256,
        status="fail_closed",
        failure_code=code,
        initial_energy_kcal_per_mol=initial_energy,
        final_energy_kcal_per_mol=current_energy,
        initial_max_force_kcal_per_mol_angstrom=initial_max_force,
        final_max_force_kcal_per_mol_angstrom=current_max_force,
        final_constraint_residual_angstrom=constraint_residual,
        accepted_iterations=accepted_iterations,
        rejected_evaluations=rejected_evaluations,
        evaluation_count=evaluation_count,
        final_coordinates_angstrom=coordinates,
        accepted_energy_trace_kcal_per_mol=energy_trace,
        coordinate_trace=coordinate_trace,
        checkpoint=None,
    )


def _checkpoint(
    source: IndependentMinimizationOracleInput,
    coordinates: Coordinates,
    accepted_iterations: int,
    rejected_evaluations: int,
    evaluation_count: int,
    initial_energy: float,
    initial_max_force: float,
    current_energy: float,
    current_max_force: float,
    constraint_residual: float,
    energy_trace: tuple[float, ...],
    coordinate_trace: tuple[IndependentMinimizationCoordinateTraceStep, ...],
) -> IndependentMinimizationCheckpoint:
    values = {
        "compatibility_sha256": source.compatibility_sha256,
        "coordinates_angstrom": coordinates,
        "accepted_iterations": accepted_iterations,
        "rejected_evaluations": rejected_evaluations,
        "evaluation_count": evaluation_count,
        "initial_energy_kcal_per_mol": initial_energy,
        "initial_max_force_kcal_per_mol_angstrom": initial_max_force,
        "current_energy_kcal_per_mol": current_energy,
        "current_max_force_kcal_per_mol_angstrom": current_max_force,
        "current_constraint_residual_angstrom": constraint_residual,
        "accepted_energy_trace_kcal_per_mol": energy_trace,
        "coordinate_trace": coordinate_trace,
    }
    projection = {
        "schema_id": INDEPENDENT_MINIMIZATION_ORACLE_CHECKPOINT_SCHEMA_ID,
        "oracle_id": INDEPENDENT_MINIMIZATION_ORACLE_ID,
        "compatibility_sha256": source.compatibility_sha256,
        "coordinates_angstrom_hex": [
            [float(value).hex() for value in row] for row in coordinates
        ],
        "coordinates_sha256": _coordinate_sha256(coordinates),
        "accepted_iterations": accepted_iterations,
        "rejected_evaluations": rejected_evaluations,
        "evaluation_count": evaluation_count,
        "initial_energy_kcal_per_mol": initial_energy,
        "initial_max_force_kcal_per_mol_angstrom": initial_max_force,
        "current_energy_kcal_per_mol": current_energy,
        "current_max_force_kcal_per_mol_angstrom": current_max_force,
        "current_constraint_residual_angstrom": constraint_residual,
        "accepted_energy_trace_kcal_per_mol": list(energy_trace),
        "coordinate_trace": [row.to_dict() for row in coordinate_trace],
        "coordinate_trace_sha256": _sha256(
            [row.to_dict() for row in coordinate_trace]
        ),
    }
    return IndependentMinimizationCheckpoint(
        **values,
        checkpoint_sha256=_sha256(projection),
    )


def evaluate_independent_minimization_oracle(
    source: IndependentMinimizationOracleInput,
    *,
    checkpoint: IndependentMinimizationCheckpoint | None = None,
) -> IndependentMinimizationOracleResult:
    """Run the bounded independent minimization implementation in memory."""

    if not isinstance(source, IndependentMinimizationOracleInput):
        raise IndependentMinimizationOracleError(
            "source must be an IndependentMinimizationOracleInput"
        )
    for checkpoint_name, runtime_name, code in (
        (
            "checkpoint_topology_sha256",
            "runtime_topology_sha256",
            "checkpoint_topology_fingerprint_mismatch",
        ),
        (
            "checkpoint_parameter_sha256",
            "runtime_parameter_sha256",
            "checkpoint_parameter_fingerprint_mismatch",
        ),
        (
            "checkpoint_solvation_sha256",
            "runtime_solvation_sha256",
            "checkpoint_solvation_parameter_fingerprint_mismatch",
        ),
    ):
        checkpoint_identity = getattr(source, checkpoint_name)
        runtime_identity = getattr(source, runtime_name)
        if (
            checkpoint_identity is not None
            and runtime_identity is not None
            and checkpoint_identity != runtime_identity
        ):
            return _fail_closed(source, code)
    if source.fixed_born_radii_angstrom is not None and (
        source.energy_input.orthorhombic_cell_angstrom is not None
        or any(source.energy_input.periodic_axes)
    ):
        return _fail_closed(source, "periodic_fixed_born_not_supported")

    if checkpoint is None:
        coordinates = source.energy_input.coordinates_angstrom
        coordinates, constraint_residual, projected, projection_code = (
            _project_constraints(coordinates, source)
        )
        if not projected:
            return _fail_closed(
                source, projection_code or "constraint_projection_exhausted"
            )
        current_energy, raw_forces = _evaluate(source, coordinates)
        current_forces, current_max_force, force_projected = _project_forces(
            source, coordinates, raw_forces
        )
        if not force_projected:
            return _fail_closed(source, "constraint_force_projection_exhausted")
        accepted_iterations = 0
        rejected_evaluations = 0
        evaluation_count = 1
        initial_energy = current_energy
        initial_max_force = current_max_force
        energy_trace = (current_energy,)
        coordinate_trace = (
            IndependentMinimizationCoordinateTraceStep(
                evaluation_index=1,
                iteration=0,
                trial=0,
                outcome="initial",
                raw_coordinates_angstrom=source.energy_input.coordinates_angstrom,
                evaluated_coordinates_angstrom=coordinates,
                energy_kcal_per_mol=current_energy,
            ),
        )
    else:
        if not isinstance(checkpoint, IndependentMinimizationCheckpoint):
            raise IndependentMinimizationOracleError(
                "checkpoint must be an IndependentMinimizationCheckpoint"
            )
        if checkpoint.compatibility_sha256 != source.compatibility_sha256:
            raise IndependentMinimizationOracleError(
                "checkpoint compatibility identity mismatch"
            )
        if checkpoint.coordinate_trace[-1].outcome.startswith("rejected_"):
            raise IndependentMinimizationOracleError(
                "terminal failed line-search checkpoint cannot be resumed"
            )
        replayed = evaluate_independent_minimization_oracle(
            replace(
                source,
                pause_after_accepted_iterations=checkpoint.accepted_iterations,
            )
        )
        if (
            replayed.checkpoint is None
            or replayed.checkpoint.to_dict() != checkpoint.to_dict()
        ):
            raise IndependentMinimizationOracleError(
                "checkpoint history does not replay exactly from the source input"
            )
        coordinates = checkpoint.coordinates_angstrom
        accepted_iterations = checkpoint.accepted_iterations
        rejected_evaluations = checkpoint.rejected_evaluations
        evaluation_count = checkpoint.evaluation_count
        initial_energy = checkpoint.initial_energy_kcal_per_mol
        initial_max_force = checkpoint.initial_max_force_kcal_per_mol_angstrom
        energy_trace = checkpoint.accepted_energy_trace_kcal_per_mol
        coordinate_trace = checkpoint.coordinate_trace
        constraint_residual = checkpoint.current_constraint_residual_angstrom
        current_energy, raw_forces = _evaluate(source, coordinates)
        current_forces, current_max_force, force_projected = _project_forces(
            source, coordinates, raw_forces
        )
        if not force_projected:
            raise IndependentMinimizationOracleError(
                "checkpoint force projection is not reproducible"
            )
        if (
            current_energy != checkpoint.current_energy_kcal_per_mol
            or current_max_force != checkpoint.current_max_force_kcal_per_mol_angstrom
        ):
            raise IndependentMinimizationOracleError(
                "checkpoint energy or force is not reproducible"
            )

    status = "max_iterations_reached"
    failure_code: str | None = "maximum_iteration_budget_exhausted"
    while accepted_iterations < source.max_iterations:
        if current_max_force <= source.force_tolerance_kcal_per_mol_angstrom:
            status = "converged"
            failure_code = None
            break
        if (
            source.pause_after_accepted_iterations is not None
            and accepted_iterations >= source.pause_after_accepted_iterations
        ):
            status = "checkpointed"
            failure_code = None
            break
        step = source.initial_step_size_angstrom2_mol_per_kcal
        direction = current_forces
        raw_max_displacement = step * current_max_force
        if raw_max_displacement > source.maximum_atom_displacement_angstrom:
            direction = tuple(
                _scale(
                    row,
                    source.maximum_atom_displacement_angstrom / raw_max_displacement,
                )
                for row in direction
            )
        unconstrained_directional_derivative = -sum(
            _dot(force, row) for force, row in zip(current_forces, direction)
        )
        accepted = False
        iteration = accepted_iterations + 1
        for trial in range(source.max_backtracks + 1):
            raw_coordinates = tuple(
                _add(row, _scale(delta, step))
                for row, delta in zip(coordinates, direction)
            )
            trial_coordinates, trial_residual, projected, _ = _project_constraints(
                raw_coordinates, source
            )
            evaluation_count += 1
            if not projected:
                coordinate_trace = (
                    *coordinate_trace,
                    IndependentMinimizationCoordinateTraceStep(
                        evaluation_index=evaluation_count,
                        iteration=iteration,
                        trial=trial,
                        outcome="rejected_constraint_projection",
                        raw_coordinates_angstrom=raw_coordinates,
                        evaluated_coordinates_angstrom=trial_coordinates,
                        energy_kcal_per_mol=None,
                    ),
                )
                rejected_evaluations += 1
                step *= source.backtrack_factor
                continue
            maximum_displacement = max(
                (
                    _norm(_subtract(trial, current))
                    for trial, current in zip(trial_coordinates, coordinates)
                ),
                default=0.0,
            )
            if maximum_displacement > (
                source.maximum_atom_displacement_angstrom + 1.0e-12
            ):
                coordinate_trace = (
                    *coordinate_trace,
                    IndependentMinimizationCoordinateTraceStep(
                        evaluation_index=evaluation_count,
                        iteration=iteration,
                        trial=trial,
                        outcome="rejected_projected_displacement",
                        raw_coordinates_angstrom=raw_coordinates,
                        evaluated_coordinates_angstrom=trial_coordinates,
                        energy_kcal_per_mol=None,
                    ),
                )
                rejected_evaluations += 1
                step *= source.backtrack_factor
                continue
            trial_energy, raw_trial_forces = _evaluate(source, trial_coordinates)
            trial_forces, trial_max_force, force_projected = _project_forces(
                source, trial_coordinates, raw_trial_forces
            )
            if not force_projected:
                coordinate_trace = (
                    *coordinate_trace,
                    IndependentMinimizationCoordinateTraceStep(
                        evaluation_index=evaluation_count,
                        iteration=iteration,
                        trial=trial,
                        outcome="rejected_force_projection",
                        raw_coordinates_angstrom=raw_coordinates,
                        evaluated_coordinates_angstrom=trial_coordinates,
                        energy_kcal_per_mol=trial_energy,
                    ),
                )
                rejected_evaluations += 1
                step *= source.backtrack_factor
                continue
            if source.constraints:
                displacement = tuple(
                    _subtract(trial, current)
                    for trial, current in zip(trial_coordinates, coordinates)
                )
                directional_derivative = -sum(
                    _dot(force, delta)
                    for force, delta in zip(current_forces, displacement)
                )
                armijo_limit = (
                    current_energy + source.armijo_constant * directional_derivative
                )
                descent = directional_derivative < 0.0
            else:
                armijo_limit = current_energy + (
                    source.armijo_constant * step * unconstrained_directional_derivative
                )
                descent = True
            if descent and trial_energy <= armijo_limit:
                coordinate_trace = (
                    *coordinate_trace,
                    IndependentMinimizationCoordinateTraceStep(
                        evaluation_index=evaluation_count,
                        iteration=iteration,
                        trial=trial,
                        outcome="accepted",
                        raw_coordinates_angstrom=raw_coordinates,
                        evaluated_coordinates_angstrom=trial_coordinates,
                        energy_kcal_per_mol=trial_energy,
                    ),
                )
                coordinates = trial_coordinates
                constraint_residual = trial_residual
                current_energy = trial_energy
                current_forces = trial_forces
                current_max_force = trial_max_force
                accepted_iterations += 1
                energy_trace = (*energy_trace, current_energy)
                accepted = True
                break
            coordinate_trace = (
                *coordinate_trace,
                IndependentMinimizationCoordinateTraceStep(
                    evaluation_index=evaluation_count,
                    iteration=iteration,
                    trial=trial,
                    outcome=(
                        "rejected_armijo" if descent else "rejected_non_descent"
                    ),
                    raw_coordinates_angstrom=raw_coordinates,
                    evaluated_coordinates_angstrom=trial_coordinates,
                    energy_kcal_per_mol=trial_energy,
                ),
            )
            rejected_evaluations += 1
            step *= source.backtrack_factor
        if not accepted:
            if source.expected_outcome == "fail_closed":
                return _fail_closed(
                    source,
                    "line_search_exhausted",
                    initial_energy=initial_energy,
                    initial_max_force=initial_max_force,
                    current_energy=current_energy,
                    current_max_force=current_max_force,
                    constraint_residual=constraint_residual,
                    accepted_iterations=accepted_iterations,
                    rejected_evaluations=rejected_evaluations,
                    evaluation_count=evaluation_count,
                    coordinates=coordinates,
                    energy_trace=energy_trace,
                    coordinate_trace=coordinate_trace,
                )
            status = "line_search_failed"
            failure_code = (
                "bounded_projected_backtracking_exhausted"
                if source.constraints
                else "bounded_backtracking_exhausted"
            )
            break
    else:
        status = "max_iterations_reached"
        failure_code = "maximum_iteration_budget_exhausted"
    if current_max_force <= source.force_tolerance_kcal_per_mol_angstrom:
        status = "converged"
        failure_code = None
    state = _checkpoint(
        source,
        coordinates,
        accepted_iterations,
        rejected_evaluations,
        evaluation_count,
        initial_energy,
        initial_max_force,
        current_energy,
        current_max_force,
        constraint_residual,
        energy_trace,
        coordinate_trace,
    )
    return IndependentMinimizationOracleResult(
        input_sha256=source.input_sha256,
        status=status,
        failure_code=failure_code,
        initial_energy_kcal_per_mol=initial_energy,
        final_energy_kcal_per_mol=current_energy,
        initial_max_force_kcal_per_mol_angstrom=initial_max_force,
        final_max_force_kcal_per_mol_angstrom=current_max_force,
        final_constraint_residual_angstrom=constraint_residual,
        accepted_iterations=accepted_iterations,
        rejected_evaluations=rejected_evaluations,
        evaluation_count=evaluation_count,
        final_coordinates_angstrom=coordinates,
        accepted_energy_trace_kcal_per_mol=energy_trace,
        coordinate_trace=coordinate_trace,
        checkpoint=state,
    )


__all__ = [
    "INDEPENDENT_MINIMIZATION_ORACLE_CHECKPOINT_SCHEMA_ID",
    "INDEPENDENT_MINIMIZATION_ORACLE_ID",
    "INDEPENDENT_MINIMIZATION_ORACLE_INPUT_SCHEMA_ID",
    "INDEPENDENT_MINIMIZATION_ORACLE_SCHEMA_ID",
    "INDEPENDENT_MINIMIZATION_ORACLE_VERSION",
    "IndependentMinimizationCheckpoint",
    "IndependentMinimizationCoordinateTraceStep",
    "IndependentMinimizationOracleError",
    "IndependentMinimizationOracleInput",
    "IndependentMinimizationOracleResult",
    "evaluate_independent_minimization_oracle",
]
