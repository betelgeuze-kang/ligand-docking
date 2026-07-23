"""Standalone binary64 constrained trajectory oracle.

The module deliberately imports only the Python standard library.  A caller
supplies a force callback, which lets the offline evidence adapter use OpenMM
Reference energy and forces without importing or reusing Engine v2 NVE,
SHAKE/RATTLE, neighbor-list, or force implementations here.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from numbers import Real
from typing import Callable, Mapping, Sequence


OPENMM_FORCE_DOUBLE_RATTLE_ALGORITHM_ID = (
    "stdlib_binary64_sequential_previous_vector_shake_rattle/1.1.0"
)
OPENMM_FORCE_DOUBLE_RATTLE_CONFIG_SCHEMA_ID = (
    "betelgeuze.engine_v2_openmm_force_double_rattle_config/1.0.0"
)
OPENMM_FORCE_DOUBLE_RATTLE_CHECKPOINT_SCHEMA_ID = (
    "betelgeuze.engine_v2_openmm_force_double_rattle_checkpoint/1.0.0"
)
OPENMM_FORCE_DOUBLE_RATTLE_FRAME_SCHEMA_ID = (
    "betelgeuze.engine_v2_openmm_force_double_rattle_frame/1.0.0"
)

OPENMM_FORCE_DOUBLE_RATTLE_ACCELERATION_FACTOR = 418.4
OPENMM_FORCE_DOUBLE_RATTLE_MAX_ATOMS = 16
OPENMM_FORCE_DOUBLE_RATTLE_MAX_CONSTRAINTS = 48
OPENMM_FORCE_DOUBLE_RATTLE_MAX_STEPS = 10_000
OPENMM_FORCE_DOUBLE_RATTLE_MAX_SWEEPS = 500


class OpenMMForceDoubleRattleError(ValueError):
    """The standalone oracle input, projection, or checkpoint failed closed."""


ForceEvaluator = Callable[
    [tuple[tuple[float, float, float], ...]],
    tuple[float, Sequence[Sequence[float]]],
]


def _canonical_bytes(value: object) -> bytes:
    try:
        return (
            json.dumps(
                value,
                allow_nan=False,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise OpenMMForceDoubleRattleError(
            "double-RATTLE payload is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _digest(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise OpenMMForceDoubleRattleError(
            f"{name} must be a lowercase SHA-256 digest"
        )
    return value


def _finite(
    value: object,
    *,
    name: str,
    positive: bool = False,
    nonnegative: bool = False,
) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise OpenMMForceDoubleRattleError(f"{name} must be a finite real")
    result = float(value)
    if not math.isfinite(result):
        raise OpenMMForceDoubleRattleError(f"{name} must be finite")
    if positive and result <= 0.0:
        raise OpenMMForceDoubleRattleError(f"{name} must be positive")
    if nonnegative and result < 0.0:
        raise OpenMMForceDoubleRattleError(f"{name} must be non-negative")
    return result


def _integer(
    value: object,
    *,
    name: str,
    minimum: int,
    maximum: int,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise OpenMMForceDoubleRattleError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise OpenMMForceDoubleRattleError(
            f"{name} must be in [{minimum},{maximum}]"
        )
    return value


def _float_hex(value: object, *, name: str) -> float:
    if not isinstance(value, str):
        raise OpenMMForceDoubleRattleError(
            f"{name} must be canonical binary64 hex"
        )
    try:
        result = float.fromhex(value)
    except ValueError:
        raise OpenMMForceDoubleRattleError(
            f"{name} must be canonical binary64 hex"
        ) from None
    if not math.isfinite(result) or result.hex() != value:
        raise OpenMMForceDoubleRattleError(
            f"{name} must be canonical finite binary64 hex"
        )
    return result


def _vectors(
    value: object,
    *,
    name: str,
    count: int | None = None,
) -> tuple[tuple[float, float, float], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise OpenMMForceDoubleRattleError(
            f"{name} must be a sequence of three-vectors"
        )
    rows = tuple(value)
    if count is not None and len(rows) != count:
        raise OpenMMForceDoubleRattleError(f"{name} length is invalid")
    if not 1 <= len(rows) <= OPENMM_FORCE_DOUBLE_RATTLE_MAX_ATOMS:
        raise OpenMMForceDoubleRattleError(
            f"{name} exceeds the bounded atom domain"
        )
    result = []
    for row_index, row in enumerate(rows):
        if (
            not isinstance(row, Sequence)
            or isinstance(row, (str, bytes))
            or len(row) != 3
        ):
            raise OpenMMForceDoubleRattleError(
                f"{name}[{row_index}] must be a three-vector"
            )
        result.append(
            tuple(
                _finite(item, name=f"{name}[{row_index}][{axis}]")
                for axis, item in enumerate(row)
            )
        )
    return tuple(result)  # type: ignore[return-value]


def _hex_vectors(
    value: Sequence[Sequence[float]],
) -> list[list[str]]:
    return [[float(item).hex() for item in row] for row in value]


def _vectors_from_hex(
    value: object,
    *,
    name: str,
    count: int,
) -> tuple[tuple[float, float, float], ...]:
    if not isinstance(value, list) or len(value) != count:
        raise OpenMMForceDoubleRattleError(f"{name} length is invalid")
    rows = []
    for row_index, row in enumerate(value):
        if not isinstance(row, list) or len(row) != 3:
            raise OpenMMForceDoubleRattleError(
                f"{name}[{row_index}] must be a three-vector"
            )
        rows.append(
            tuple(
                _float_hex(
                    item,
                    name=f"{name}[{row_index}][{axis}]",
                )
                for axis, item in enumerate(row)
            )
        )
    return tuple(rows)  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class DoubleRattleDistanceConstraint:
    atom_i: int
    atom_j: int
    target_distance_angstrom: float

    def __post_init__(self) -> None:
        first = _integer(
            self.atom_i,
            name="constraint atom_i",
            minimum=0,
            maximum=OPENMM_FORCE_DOUBLE_RATTLE_MAX_ATOMS - 1,
        )
        second = _integer(
            self.atom_j,
            name="constraint atom_j",
            minimum=0,
            maximum=OPENMM_FORCE_DOUBLE_RATTLE_MAX_ATOMS - 1,
        )
        if first >= second:
            raise OpenMMForceDoubleRattleError(
                "constraint atoms must be canonical and distinct"
            )
        object.__setattr__(
            self,
            "target_distance_angstrom",
            _finite(
                self.target_distance_angstrom,
                name="constraint target distance",
                positive=True,
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "atom_i": self.atom_i,
            "atom_j": self.atom_j,
            "target_distance_angstrom_hex": (
                self.target_distance_angstrom.hex()
            ),
        }

    @classmethod
    def from_dict(cls, value: object) -> "DoubleRattleDistanceConstraint":
        if not isinstance(value, Mapping) or set(value) != {
            "atom_i",
            "atom_j",
            "target_distance_angstrom_hex",
        }:
            raise OpenMMForceDoubleRattleError(
                "constraint payload is invalid"
            )
        return cls(
            atom_i=_integer(
                value["atom_i"],
                name="constraint atom_i",
                minimum=0,
                maximum=OPENMM_FORCE_DOUBLE_RATTLE_MAX_ATOMS - 1,
            ),
            atom_j=_integer(
                value["atom_j"],
                name="constraint atom_j",
                minimum=0,
                maximum=OPENMM_FORCE_DOUBLE_RATTLE_MAX_ATOMS - 1,
            ),
            target_distance_angstrom=_float_hex(
                value["target_distance_angstrom_hex"],
                name="constraint target distance",
            ),
        )


@dataclass(frozen=True, slots=True)
class OpenMMForceDoubleRattleConfig:
    timestep_ps: float
    box_lengths_angstrom: tuple[float, float, float]
    position_tolerance_angstrom: float = 1.0e-12
    velocity_tolerance_angstrom_per_ps: float = 1.0e-12
    max_position_sweeps: int = OPENMM_FORCE_DOUBLE_RATTLE_MAX_SWEEPS
    max_velocity_sweeps: int = OPENMM_FORCE_DOUBLE_RATTLE_MAX_SWEEPS
    max_pair_position_correction_angstrom: float = 0.1
    schema_id: str = OPENMM_FORCE_DOUBLE_RATTLE_CONFIG_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != OPENMM_FORCE_DOUBLE_RATTLE_CONFIG_SCHEMA_ID:
            raise OpenMMForceDoubleRattleError(
                "unsupported double-RATTLE config schema"
            )
        object.__setattr__(
            self,
            "timestep_ps",
            _finite(self.timestep_ps, name="timestep_ps", positive=True),
        )
        if self.timestep_ps > 0.1:
            raise OpenMMForceDoubleRattleError(
                "timestep_ps exceeds the bounded limit"
            )
        if (
            not isinstance(self.box_lengths_angstrom, tuple)
            or len(self.box_lengths_angstrom) != 3
        ):
            raise OpenMMForceDoubleRattleError(
                "box_lengths_angstrom must be a three-tuple"
            )
        lengths = tuple(
            _finite(item, name=f"box length {axis}", positive=True)
            for axis, item in enumerate(self.box_lengths_angstrom)
        )
        object.__setattr__(self, "box_lengths_angstrom", lengths)
        object.__setattr__(
            self,
            "position_tolerance_angstrom",
            _finite(
                self.position_tolerance_angstrom,
                name="position tolerance",
                positive=True,
            ),
        )
        object.__setattr__(
            self,
            "velocity_tolerance_angstrom_per_ps",
            _finite(
                self.velocity_tolerance_angstrom_per_ps,
                name="velocity tolerance",
                positive=True,
            ),
        )
        if (
            self.position_tolerance_angstrom > 1.0e-6
            or self.velocity_tolerance_angstrom_per_ps > 1.0e-6
        ):
            raise OpenMMForceDoubleRattleError(
                "double-RATTLE internal tolerance exceeds its bound"
            )
        object.__setattr__(
            self,
            "max_position_sweeps",
            _integer(
                self.max_position_sweeps,
                name="max_position_sweeps",
                minimum=1,
                maximum=OPENMM_FORCE_DOUBLE_RATTLE_MAX_SWEEPS,
            ),
        )
        object.__setattr__(
            self,
            "max_velocity_sweeps",
            _integer(
                self.max_velocity_sweeps,
                name="max_velocity_sweeps",
                minimum=1,
                maximum=OPENMM_FORCE_DOUBLE_RATTLE_MAX_SWEEPS,
            ),
        )
        object.__setattr__(
            self,
            "max_pair_position_correction_angstrom",
            _finite(
                self.max_pair_position_correction_angstrom,
                name="max pair position correction",
                positive=True,
            ),
        )
        if self.max_pair_position_correction_angstrom > 1.0:
            raise OpenMMForceDoubleRattleError(
                "max pair position correction exceeds its bound"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "algorithm_id": OPENMM_FORCE_DOUBLE_RATTLE_ALGORITHM_ID,
            "timestep_ps_hex": self.timestep_ps.hex(),
            "box_lengths_angstrom_hex": [
                item.hex() for item in self.box_lengths_angstrom
            ],
            "position_tolerance_angstrom_hex": (
                self.position_tolerance_angstrom.hex()
            ),
            "velocity_tolerance_angstrom_per_ps_hex": (
                self.velocity_tolerance_angstrom_per_ps.hex()
            ),
            "max_position_sweeps": self.max_position_sweeps,
            "max_velocity_sweeps": self.max_velocity_sweeps,
            "max_pair_position_correction_angstrom_hex": (
                self.max_pair_position_correction_angstrom.hex()
            ),
        }

    @classmethod
    def from_dict(cls, value: object) -> "OpenMMForceDoubleRattleConfig":
        expected = {
            "schema_id",
            "algorithm_id",
            "timestep_ps_hex",
            "box_lengths_angstrom_hex",
            "position_tolerance_angstrom_hex",
            "velocity_tolerance_angstrom_per_ps_hex",
            "max_position_sweeps",
            "max_velocity_sweeps",
            "max_pair_position_correction_angstrom_hex",
        }
        if not isinstance(value, Mapping) or set(value) != expected:
            raise OpenMMForceDoubleRattleError(
                "double-RATTLE config payload is invalid"
            )
        if value["algorithm_id"] != OPENMM_FORCE_DOUBLE_RATTLE_ALGORITHM_ID:
            raise OpenMMForceDoubleRattleError(
                "unsupported double-RATTLE algorithm"
            )
        raw_lengths = value["box_lengths_angstrom_hex"]
        if not isinstance(raw_lengths, list) or len(raw_lengths) != 3:
            raise OpenMMForceDoubleRattleError(
                "box length payload is invalid"
            )
        return cls(
            schema_id=value["schema_id"],  # type: ignore[arg-type]
            timestep_ps=_float_hex(
                value["timestep_ps_hex"],
                name="timestep_ps",
            ),
            box_lengths_angstrom=tuple(
                _float_hex(item, name=f"box length {axis}")
                for axis, item in enumerate(raw_lengths)
            ),  # type: ignore[arg-type]
            position_tolerance_angstrom=_float_hex(
                value["position_tolerance_angstrom_hex"],
                name="position tolerance",
            ),
            velocity_tolerance_angstrom_per_ps=_float_hex(
                value["velocity_tolerance_angstrom_per_ps_hex"],
                name="velocity tolerance",
            ),
            max_position_sweeps=_integer(
                value["max_position_sweeps"],
                name="max_position_sweeps",
                minimum=1,
                maximum=OPENMM_FORCE_DOUBLE_RATTLE_MAX_SWEEPS,
            ),
            max_velocity_sweeps=_integer(
                value["max_velocity_sweeps"],
                name="max_velocity_sweeps",
                minimum=1,
                maximum=OPENMM_FORCE_DOUBLE_RATTLE_MAX_SWEEPS,
            ),
            max_pair_position_correction_angstrom=_float_hex(
                value["max_pair_position_correction_angstrom_hex"],
                name="max pair position correction",
            ),
        )

    @property
    def fingerprint_sha256(self) -> str:
        return _sha256(self.to_dict())


def _mass_document(masses: Sequence[float]) -> dict[str, object]:
    if (
        not isinstance(masses, Sequence)
        or isinstance(masses, (str, bytes))
        or not 1 <= len(masses) <= OPENMM_FORCE_DOUBLE_RATTLE_MAX_ATOMS
    ):
        raise OpenMMForceDoubleRattleError(
            "masses exceed the bounded atom domain"
        )
    values = tuple(
        _finite(item, name=f"mass {index}", positive=True)
        for index, item in enumerate(masses)
    )
    projection = {"mass_da_hex": [item.hex() for item in values]}
    return {**projection, "mass_fingerprint_sha256": _sha256(projection)}


def _constraint_document(
    constraints: Sequence[DoubleRattleDistanceConstraint],
    *,
    atom_count: int,
    lengths: tuple[float, float, float],
) -> dict[str, object]:
    if (
        not isinstance(constraints, Sequence)
        or isinstance(constraints, (str, bytes))
        or not 1 <= len(constraints) <= OPENMM_FORCE_DOUBLE_RATTLE_MAX_CONSTRAINTS
    ):
        raise OpenMMForceDoubleRattleError(
            "constraints exceed the bounded domain"
        )
    rows = tuple(constraints)
    if any(
        not isinstance(row, DoubleRattleDistanceConstraint)
        for row in rows
    ):
        raise OpenMMForceDoubleRattleError(
            "constraints must be DoubleRattleDistanceConstraint values"
        )
    pairs = [(row.atom_i, row.atom_j) for row in rows]
    if len(set(pairs)) != len(pairs) or pairs != sorted(pairs):
        raise OpenMMForceDoubleRattleError(
            "constraints must be unique canonical-pair sorted"
        )
    for row in rows:
        if row.atom_j >= atom_count:
            raise OpenMMForceDoubleRattleError(
                "constraint atom index is outside the system"
            )
        if row.target_distance_angstrom >= 0.5 * min(lengths):
            raise OpenMMForceDoubleRattleError(
                "constraint target is ambiguous under minimum image"
            )
    projection = {"constraints": [row.to_dict() for row in rows]}
    return {
        **projection,
        "constraint_fingerprint_sha256": _sha256(projection),
    }


def _minimum_image(value: float, length: float) -> float:
    return value - round(value / length) * length


def _wrap(value: float, length: float) -> float:
    return value - math.floor(value / length) * length


def _position_residual(
    coordinates: Sequence[Sequence[float]],
    constraints: Sequence[DoubleRattleDistanceConstraint],
    lengths: tuple[float, float, float],
) -> float:
    result = 0.0
    for row in constraints:
        displacement = tuple(
            _minimum_image(
                coordinates[row.atom_i][axis]
                - coordinates[row.atom_j][axis],
                lengths[axis],
            )
            for axis in range(3)
        )
        distance = math.sqrt(
            math.fsum(item * item for item in displacement)
        )
        result = max(
            result,
            abs(distance - row.target_distance_angstrom),
        )
    return result


def _velocity_residual(
    coordinates: Sequence[Sequence[float]],
    velocities: Sequence[Sequence[float]],
    constraints: Sequence[DoubleRattleDistanceConstraint],
    lengths: tuple[float, float, float],
) -> float:
    result = 0.0
    for row in constraints:
        displacement = tuple(
            _minimum_image(
                coordinates[row.atom_i][axis]
                - coordinates[row.atom_j][axis],
                lengths[axis],
            )
            for axis in range(3)
        )
        relative = tuple(
            velocities[row.atom_i][axis]
            - velocities[row.atom_j][axis]
            for axis in range(3)
        )
        radial = math.fsum(
            displacement[axis] * relative[axis]
            for axis in range(3)
        ) / row.target_distance_angstrom
        result = max(result, abs(radial))
    return result


def _project_positions(
    coordinates: Sequence[Sequence[float]],
    masses: Sequence[float],
    constraints: Sequence[DoubleRattleDistanceConstraint],
    config: OpenMMForceDoubleRattleConfig,
    *,
    reference_coordinates: Sequence[Sequence[float]] | None = None,
) -> tuple[tuple[tuple[float, float, float], ...], int, float, float]:
    current = [list(row) for row in coordinates]
    reference = (
        [list(row) for row in coordinates]
        if reference_coordinates is None
        else [
            list(row)
            for row in _vectors(
                reference_coordinates,
                name="position projection reference coordinates",
                count=len(current),
            )
        ]
    )
    lengths = config.box_lengths_angstrom
    residual = _position_residual(current, constraints, lengths)
    if residual <= config.position_tolerance_angstrom:
        return tuple(tuple(row) for row in current), 0, residual, 0.0
    inverse_masses = tuple(1.0 / item for item in masses)
    maximum_correction = 0.0
    for sweep in range(1, config.max_position_sweeps + 1):
        for row in constraints:
            first, second = row.atom_i, row.atom_j
            current_displacement = tuple(
                _minimum_image(
                    current[first][axis] - current[second][axis],
                    lengths[axis],
                )
                for axis in range(3)
            )
            reference_displacement = tuple(
                _minimum_image(
                    reference[first][axis] - reference[second][axis],
                    lengths[axis],
                )
                for axis in range(3)
            )
            squared = math.fsum(
                item * item for item in current_displacement
            )
            if squared <= 1.0e-24:
                raise OpenMMForceDoubleRattleError(
                    "position projection encountered a degenerate pair"
                )
            inverse_sum = inverse_masses[first] + inverse_masses[second]
            denominator = 2.0 * inverse_sum * math.fsum(
                current_displacement[axis]
                * reference_displacement[axis]
                for axis in range(3)
            )
            if abs(denominator) <= 1.0e-24:
                raise OpenMMForceDoubleRattleError(
                    "position projection reference direction is singular"
                )
            multiplier = (
                squared - row.target_distance_angstrom**2
            ) / denominator
            first_correction = tuple(
                -inverse_masses[first] * multiplier * item
                for item in reference_displacement
            )
            second_correction = tuple(
                inverse_masses[second] * multiplier * item
                for item in reference_displacement
            )
            pair_correction = max(
                math.sqrt(
                    math.fsum(item * item for item in first_correction)
                ),
                math.sqrt(
                    math.fsum(item * item for item in second_correction)
                ),
            )
            if (
                not math.isfinite(pair_correction)
                or pair_correction
                > config.max_pair_position_correction_angstrom
            ):
                raise OpenMMForceDoubleRattleError(
                    "position projection exceeded the pair-correction bound"
                )
            maximum_correction = max(maximum_correction, pair_correction)
            for axis in range(3):
                current[first][axis] = _wrap(
                    current[first][axis] + first_correction[axis],
                    lengths[axis],
                )
                current[second][axis] = _wrap(
                    current[second][axis] + second_correction[axis],
                    lengths[axis],
                )
        residual = _position_residual(current, constraints, lengths)
        if residual <= config.position_tolerance_angstrom:
            return (
                tuple(tuple(row) for row in current),
                sweep,
                residual,
                maximum_correction,
            )
    raise OpenMMForceDoubleRattleError(
        "position projection exhausted the sweep budget; "
        f"residual={residual.hex()}"
    )


def _project_velocities(
    coordinates: Sequence[Sequence[float]],
    velocities: Sequence[Sequence[float]],
    masses: Sequence[float],
    constraints: Sequence[DoubleRattleDistanceConstraint],
    config: OpenMMForceDoubleRattleConfig,
) -> tuple[tuple[tuple[float, float, float], ...], int, float]:
    current = [list(row) for row in velocities]
    lengths = config.box_lengths_angstrom
    residual = _velocity_residual(
        coordinates,
        current,
        constraints,
        lengths,
    )
    if residual <= config.velocity_tolerance_angstrom_per_ps:
        return tuple(tuple(row) for row in current), 0, residual
    inverse_masses = tuple(1.0 / item for item in masses)
    for sweep in range(1, config.max_velocity_sweeps + 1):
        for row in constraints:
            first, second = row.atom_i, row.atom_j
            displacement = tuple(
                _minimum_image(
                    coordinates[first][axis]
                    - coordinates[second][axis],
                    lengths[axis],
                )
                for axis in range(3)
            )
            squared = math.fsum(item * item for item in displacement)
            if squared <= 1.0e-24:
                raise OpenMMForceDoubleRattleError(
                    "velocity projection encountered a degenerate pair"
                )
            relative = tuple(
                current[first][axis] - current[second][axis]
                for axis in range(3)
            )
            inverse_sum = inverse_masses[first] + inverse_masses[second]
            multiplier = math.fsum(
                displacement[axis] * relative[axis]
                for axis in range(3)
            ) / (inverse_sum * squared)
            for axis in range(3):
                current[first][axis] -= (
                    inverse_masses[first]
                    * multiplier
                    * displacement[axis]
                )
                current[second][axis] += (
                    inverse_masses[second]
                    * multiplier
                    * displacement[axis]
                )
        residual = _velocity_residual(
            coordinates,
            current,
            constraints,
            lengths,
        )
        if residual <= config.velocity_tolerance_angstrom_per_ps:
            return tuple(tuple(row) for row in current), sweep, residual
    raise OpenMMForceDoubleRattleError(
        "velocity projection exhausted the sweep budget; "
        f"residual={residual.hex()}"
    )


def _evaluate(
    evaluator: ForceEvaluator,
    coordinates: tuple[tuple[float, float, float], ...],
) -> tuple[float, tuple[tuple[float, float, float], ...]]:
    try:
        result = evaluator(coordinates)
    except OpenMMForceDoubleRattleError:
        raise
    except Exception as exc:
        raise OpenMMForceDoubleRattleError(
            "force evaluator failed"
        ) from exc
    if not isinstance(result, tuple) or len(result) != 2:
        raise OpenMMForceDoubleRattleError(
            "force evaluator must return an energy/forces tuple"
        )
    energy = _finite(result[0], name="potential energy")
    forces = _vectors(
        result[1],
        name="forces",
        count=len(coordinates),
    )
    return energy, forces


def _kinetic_energy(
    velocities: Sequence[Sequence[float]],
    masses: Sequence[float],
) -> float:
    return 0.5 * math.fsum(
        masses[index] * component * component
        for index, row in enumerate(velocities)
        for component in row
    ) / OPENMM_FORCE_DOUBLE_RATTLE_ACCELERATION_FACTOR


def _frame(
    *,
    step: int,
    coordinates: tuple[tuple[float, float, float], ...],
    velocities: tuple[tuple[float, float, float], ...],
    forces: tuple[tuple[float, float, float], ...],
    potential_energy: float,
    masses: tuple[float, ...],
    constraints: tuple[DoubleRattleDistanceConstraint, ...],
    config: OpenMMForceDoubleRattleConfig,
    position_sweeps: int,
    velocity_sweeps: int,
    maximum_pair_position_correction_angstrom: float,
    cumulative_position_sweeps: int,
    cumulative_velocity_sweeps: int,
    initial_total_energy: float,
) -> dict[str, object]:
    kinetic = _kinetic_energy(velocities, masses)
    total = potential_energy + kinetic
    position_residual = _position_residual(
        coordinates,
        constraints,
        config.box_lengths_angstrom,
    )
    velocity_residual = _velocity_residual(
        coordinates,
        velocities,
        constraints,
        config.box_lengths_angstrom,
    )
    projection = {
        "schema_id": OPENMM_FORCE_DOUBLE_RATTLE_FRAME_SCHEMA_ID,
        "implementation": "openmm_reference_force_double_rattle",
        "step": step,
        "time_ps_hex": (step * config.timestep_ps).hex(),
        "coordinates_angstrom_hex": _hex_vectors(coordinates),
        "velocities_angstrom_per_ps_hex": _hex_vectors(velocities),
        "forces_kcal_per_mol_angstrom_hex": _hex_vectors(forces),
        "potential_energy_kcal_per_mol_hex": potential_energy.hex(),
        "kinetic_energy_kcal_per_mol_hex": kinetic.hex(),
        "total_energy_kcal_per_mol_hex": total.hex(),
        "energy_drift_kcal_per_mol_hex": (
            total - initial_total_energy
        ).hex(),
        "position_constraint_residual_angstrom_hex": (
            position_residual.hex()
        ),
        "velocity_constraint_residual_angstrom_per_ps_hex": (
            velocity_residual.hex()
        ),
        "position_sweeps": position_sweeps,
        "velocity_sweeps": velocity_sweeps,
        "maximum_pair_position_correction_angstrom_hex": (
            maximum_pair_position_correction_angstrom.hex()
        ),
        "cumulative_position_sweeps": cumulative_position_sweeps,
        "cumulative_velocity_sweeps": cumulative_velocity_sweeps,
    }
    return {**projection, "frame_sha256": _sha256(projection)}


def _trajectory_head(
    previous: str,
    frame_sha256: str,
    evaluated_frame_count: int,
) -> str:
    return _sha256(
        {
            "previous_trajectory_head_sha256": previous,
            "frame_sha256": frame_sha256,
            "evaluated_frame_count": evaluated_frame_count,
        }
    )


@dataclass(frozen=True, slots=True)
class OpenMMForceDoubleRattleCheckpoint:
    system_sha256: str
    force_configuration_sha256: str
    mass_fingerprint_sha256: str
    constraint_fingerprint_sha256: str
    config: OpenMMForceDoubleRattleConfig
    step: int
    coordinates: tuple[tuple[float, float, float], ...]
    velocities: tuple[tuple[float, float, float], ...]
    forces: tuple[tuple[float, float, float], ...]
    potential_energy_kcal_per_mol: float
    initial_total_energy_kcal_per_mol: float
    max_abs_energy_drift_kcal_per_mol: float
    max_abs_position_constraint_residual_angstrom: float
    max_abs_velocity_constraint_residual_angstrom_per_ps: float
    cumulative_position_sweeps: int
    cumulative_velocity_sweeps: int
    last_position_sweeps: int
    last_velocity_sweeps: int
    last_maximum_pair_position_correction_angstrom: float
    evaluated_frame_count: int
    trajectory_head_sha256: str
    current_frame_sha256: str
    schema_id: str = OPENMM_FORCE_DOUBLE_RATTLE_CHECKPOINT_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != OPENMM_FORCE_DOUBLE_RATTLE_CHECKPOINT_SCHEMA_ID:
            raise OpenMMForceDoubleRattleError(
                "unsupported double-RATTLE checkpoint schema"
            )
        for name in (
            "system_sha256",
            "force_configuration_sha256",
            "mass_fingerprint_sha256",
            "constraint_fingerprint_sha256",
            "trajectory_head_sha256",
            "current_frame_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _digest(getattr(self, name), name=name),
            )
        if not isinstance(self.config, OpenMMForceDoubleRattleConfig):
            raise OpenMMForceDoubleRattleError(
                "checkpoint config is invalid"
            )
        coordinates = _vectors(
            self.coordinates,
            name="checkpoint coordinates",
        )
        object.__setattr__(self, "coordinates", coordinates)
        object.__setattr__(
            self,
            "velocities",
            _vectors(
                self.velocities,
                name="checkpoint velocities",
                count=len(coordinates),
            ),
        )
        object.__setattr__(
            self,
            "forces",
            _vectors(
                self.forces,
                name="checkpoint forces",
                count=len(coordinates),
            ),
        )
        object.__setattr__(
            self,
            "potential_energy_kcal_per_mol",
            _finite(
                self.potential_energy_kcal_per_mol,
                name="checkpoint potential energy",
            ),
        )
        object.__setattr__(
            self,
            "initial_total_energy_kcal_per_mol",
            _finite(
                self.initial_total_energy_kcal_per_mol,
                name="checkpoint initial total energy",
            ),
        )
        for name in (
            "max_abs_energy_drift_kcal_per_mol",
            "max_abs_position_constraint_residual_angstrom",
            "max_abs_velocity_constraint_residual_angstrom_per_ps",
            "last_maximum_pair_position_correction_angstrom",
        ):
            object.__setattr__(
                self,
                name,
                _finite(
                    getattr(self, name),
                    name=name,
                    nonnegative=True,
                ),
            )
        object.__setattr__(
            self,
            "step",
            _integer(
                self.step,
                name="checkpoint step",
                minimum=0,
                maximum=OPENMM_FORCE_DOUBLE_RATTLE_MAX_STEPS,
            ),
        )
        count_bound = (
            (self.step + 1) * OPENMM_FORCE_DOUBLE_RATTLE_MAX_SWEEPS
        )
        for name in (
            "cumulative_position_sweeps",
            "cumulative_velocity_sweeps",
        ):
            object.__setattr__(
                self,
                name,
                _integer(
                    getattr(self, name),
                    name=name,
                    minimum=0,
                    maximum=count_bound,
                ),
            )
        for name in ("last_position_sweeps", "last_velocity_sweeps"):
            object.__setattr__(
                self,
                name,
                _integer(
                    getattr(self, name),
                    name=name,
                    minimum=0,
                    maximum=OPENMM_FORCE_DOUBLE_RATTLE_MAX_SWEEPS,
                ),
            )
        object.__setattr__(
            self,
            "evaluated_frame_count",
            _integer(
                self.evaluated_frame_count,
                name="evaluated_frame_count",
                minimum=1,
                maximum=OPENMM_FORCE_DOUBLE_RATTLE_MAX_STEPS + 1,
            ),
        )
        if self.evaluated_frame_count != self.step + 1:
            raise OpenMMForceDoubleRattleError(
                "checkpoint frame count does not match its step"
            )

    def to_dict(self) -> dict[str, object]:
        projection = {
            "schema_id": self.schema_id,
            "algorithm_id": OPENMM_FORCE_DOUBLE_RATTLE_ALGORITHM_ID,
            "system_sha256": self.system_sha256,
            "force_configuration_sha256": self.force_configuration_sha256,
            "mass_fingerprint_sha256": self.mass_fingerprint_sha256,
            "constraint_fingerprint_sha256": (
                self.constraint_fingerprint_sha256
            ),
            "config": self.config.to_dict(),
            "step": self.step,
            "coordinates_angstrom_hex": _hex_vectors(self.coordinates),
            "velocities_angstrom_per_ps_hex": _hex_vectors(self.velocities),
            "forces_kcal_per_mol_angstrom_hex": _hex_vectors(self.forces),
            "potential_energy_kcal_per_mol_hex": (
                self.potential_energy_kcal_per_mol.hex()
            ),
            "initial_total_energy_kcal_per_mol_hex": (
                self.initial_total_energy_kcal_per_mol.hex()
            ),
            "max_abs_energy_drift_kcal_per_mol_hex": (
                self.max_abs_energy_drift_kcal_per_mol.hex()
            ),
            "max_abs_position_constraint_residual_angstrom_hex": (
                self.max_abs_position_constraint_residual_angstrom.hex()
            ),
            "max_abs_velocity_constraint_residual_angstrom_per_ps_hex": (
                self.max_abs_velocity_constraint_residual_angstrom_per_ps.hex()
            ),
            "cumulative_position_sweeps": self.cumulative_position_sweeps,
            "cumulative_velocity_sweeps": self.cumulative_velocity_sweeps,
            "last_position_sweeps": self.last_position_sweeps,
            "last_velocity_sweeps": self.last_velocity_sweeps,
            "last_maximum_pair_position_correction_angstrom_hex": (
                self.last_maximum_pair_position_correction_angstrom.hex()
            ),
            "evaluated_frame_count": self.evaluated_frame_count,
            "trajectory_head_sha256": self.trajectory_head_sha256,
            "current_frame_sha256": self.current_frame_sha256,
        }
        return {**projection, "checkpoint_sha256": _sha256(projection)}

    @property
    def checkpoint_sha256(self) -> str:
        return self.to_dict()["checkpoint_sha256"]  # type: ignore[return-value]

    @classmethod
    def from_dict(
        cls,
        value: object,
    ) -> "OpenMMForceDoubleRattleCheckpoint":
        expected = {
            "schema_id",
            "algorithm_id",
            "system_sha256",
            "force_configuration_sha256",
            "mass_fingerprint_sha256",
            "constraint_fingerprint_sha256",
            "config",
            "step",
            "coordinates_angstrom_hex",
            "velocities_angstrom_per_ps_hex",
            "forces_kcal_per_mol_angstrom_hex",
            "potential_energy_kcal_per_mol_hex",
            "initial_total_energy_kcal_per_mol_hex",
            "max_abs_energy_drift_kcal_per_mol_hex",
            "max_abs_position_constraint_residual_angstrom_hex",
            "max_abs_velocity_constraint_residual_angstrom_per_ps_hex",
            "cumulative_position_sweeps",
            "cumulative_velocity_sweeps",
            "last_position_sweeps",
            "last_velocity_sweeps",
            "last_maximum_pair_position_correction_angstrom_hex",
            "evaluated_frame_count",
            "trajectory_head_sha256",
            "current_frame_sha256",
            "checkpoint_sha256",
        }
        if not isinstance(value, Mapping) or set(value) != expected:
            raise OpenMMForceDoubleRattleError(
                "double-RATTLE checkpoint payload is invalid"
            )
        projection = {
            key: item
            for key, item in value.items()
            if key != "checkpoint_sha256"
        }
        if _digest(
            value["checkpoint_sha256"],
            name="checkpoint_sha256",
        ) != _sha256(projection):
            raise OpenMMForceDoubleRattleError(
                "double-RATTLE checkpoint digest mismatch"
            )
        if (
            value["schema_id"]
            != OPENMM_FORCE_DOUBLE_RATTLE_CHECKPOINT_SCHEMA_ID
            or value["algorithm_id"]
            != OPENMM_FORCE_DOUBLE_RATTLE_ALGORITHM_ID
        ):
            raise OpenMMForceDoubleRattleError(
                "unsupported double-RATTLE checkpoint"
            )
        config = OpenMMForceDoubleRattleConfig.from_dict(value["config"])
        raw_coordinates = value["coordinates_angstrom_hex"]
        if not isinstance(raw_coordinates, list):
            raise OpenMMForceDoubleRattleError(
                "checkpoint coordinates are invalid"
            )
        atom_count = len(raw_coordinates)
        return cls(
            schema_id=value["schema_id"],  # type: ignore[arg-type]
            system_sha256=_digest(
                value["system_sha256"],
                name="system_sha256",
            ),
            force_configuration_sha256=_digest(
                value["force_configuration_sha256"],
                name="force_configuration_sha256",
            ),
            mass_fingerprint_sha256=_digest(
                value["mass_fingerprint_sha256"],
                name="mass_fingerprint_sha256",
            ),
            constraint_fingerprint_sha256=_digest(
                value["constraint_fingerprint_sha256"],
                name="constraint_fingerprint_sha256",
            ),
            config=config,
            step=_integer(
                value["step"],
                name="checkpoint step",
                minimum=0,
                maximum=OPENMM_FORCE_DOUBLE_RATTLE_MAX_STEPS,
            ),
            coordinates=_vectors_from_hex(
                raw_coordinates,
                name="checkpoint coordinates",
                count=atom_count,
            ),
            velocities=_vectors_from_hex(
                value["velocities_angstrom_per_ps_hex"],
                name="checkpoint velocities",
                count=atom_count,
            ),
            forces=_vectors_from_hex(
                value["forces_kcal_per_mol_angstrom_hex"],
                name="checkpoint forces",
                count=atom_count,
            ),
            potential_energy_kcal_per_mol=_float_hex(
                value["potential_energy_kcal_per_mol_hex"],
                name="checkpoint potential energy",
            ),
            initial_total_energy_kcal_per_mol=_float_hex(
                value["initial_total_energy_kcal_per_mol_hex"],
                name="checkpoint initial total energy",
            ),
            max_abs_energy_drift_kcal_per_mol=_float_hex(
                value["max_abs_energy_drift_kcal_per_mol_hex"],
                name="checkpoint maximum energy drift",
            ),
            max_abs_position_constraint_residual_angstrom=_float_hex(
                value[
                    "max_abs_position_constraint_residual_angstrom_hex"
                ],
                name="checkpoint maximum position residual",
            ),
            max_abs_velocity_constraint_residual_angstrom_per_ps=_float_hex(
                value[
                    "max_abs_velocity_constraint_residual_angstrom_per_ps_hex"
                ],
                name="checkpoint maximum velocity residual",
            ),
            cumulative_position_sweeps=_integer(
                value["cumulative_position_sweeps"],
                name="cumulative_position_sweeps",
                minimum=0,
                maximum=OPENMM_FORCE_DOUBLE_RATTLE_MAX_STEPS
                * OPENMM_FORCE_DOUBLE_RATTLE_MAX_SWEEPS,
            ),
            cumulative_velocity_sweeps=_integer(
                value["cumulative_velocity_sweeps"],
                name="cumulative_velocity_sweeps",
                minimum=0,
                maximum=(OPENMM_FORCE_DOUBLE_RATTLE_MAX_STEPS + 1)
                * OPENMM_FORCE_DOUBLE_RATTLE_MAX_SWEEPS,
            ),
            last_position_sweeps=_integer(
                value["last_position_sweeps"],
                name="last_position_sweeps",
                minimum=0,
                maximum=OPENMM_FORCE_DOUBLE_RATTLE_MAX_SWEEPS,
            ),
            last_velocity_sweeps=_integer(
                value["last_velocity_sweeps"],
                name="last_velocity_sweeps",
                minimum=0,
                maximum=OPENMM_FORCE_DOUBLE_RATTLE_MAX_SWEEPS,
            ),
            last_maximum_pair_position_correction_angstrom=_float_hex(
                value[
                    "last_maximum_pair_position_correction_angstrom_hex"
                ],
                name="last maximum pair position correction",
            ),
            evaluated_frame_count=_integer(
                value["evaluated_frame_count"],
                name="evaluated_frame_count",
                minimum=1,
                maximum=OPENMM_FORCE_DOUBLE_RATTLE_MAX_STEPS + 1,
            ),
            trajectory_head_sha256=_digest(
                value["trajectory_head_sha256"],
                name="trajectory_head_sha256",
            ),
            current_frame_sha256=_digest(
                value["current_frame_sha256"],
                name="current_frame_sha256",
            ),
        )


@dataclass(frozen=True, slots=True)
class OpenMMForceDoubleRattleResult:
    frames: tuple[dict[str, object], ...]
    checkpoint: OpenMMForceDoubleRattleCheckpoint


def _validate_common(
    *,
    masses: Sequence[float],
    constraints: Sequence[DoubleRattleDistanceConstraint],
    config: OpenMMForceDoubleRattleConfig,
    atom_count: int,
) -> tuple[
    tuple[float, ...],
    tuple[DoubleRattleDistanceConstraint, ...],
    dict[str, object],
    dict[str, object],
]:
    if not isinstance(config, OpenMMForceDoubleRattleConfig):
        raise OpenMMForceDoubleRattleError(
            "config must be OpenMMForceDoubleRattleConfig"
        )
    mass_document = _mass_document(masses)
    values = tuple(
        _finite(item, name=f"mass {index}", positive=True)
        for index, item in enumerate(masses)
    )
    if len(values) != atom_count:
        raise OpenMMForceDoubleRattleError(
            "mass count does not match the coordinate atom count"
        )
    rows = tuple(constraints)
    constraint_document = _constraint_document(
        rows,
        atom_count=atom_count,
        lengths=config.box_lengths_angstrom,
    )
    return values, rows, mass_document, constraint_document


def _checkpoint(
    *,
    system_sha256: str,
    force_configuration_sha256: str,
    mass_fingerprint_sha256: str,
    constraint_fingerprint_sha256: str,
    config: OpenMMForceDoubleRattleConfig,
    step: int,
    coordinates: tuple[tuple[float, float, float], ...],
    velocities: tuple[tuple[float, float, float], ...],
    forces: tuple[tuple[float, float, float], ...],
    potential_energy: float,
    initial_total_energy: float,
    max_energy_drift: float,
    max_position_residual: float,
    max_velocity_residual: float,
    cumulative_position_sweeps: int,
    cumulative_velocity_sweeps: int,
    last_position_sweeps: int,
    last_velocity_sweeps: int,
    last_maximum_correction: float,
    evaluated_frame_count: int,
    trajectory_head: str,
    current_frame_sha256: str,
) -> OpenMMForceDoubleRattleCheckpoint:
    return OpenMMForceDoubleRattleCheckpoint(
        system_sha256=system_sha256,
        force_configuration_sha256=force_configuration_sha256,
        mass_fingerprint_sha256=mass_fingerprint_sha256,
        constraint_fingerprint_sha256=constraint_fingerprint_sha256,
        config=config,
        step=step,
        coordinates=coordinates,
        velocities=velocities,
        forces=forces,
        potential_energy_kcal_per_mol=potential_energy,
        initial_total_energy_kcal_per_mol=initial_total_energy,
        max_abs_energy_drift_kcal_per_mol=max_energy_drift,
        max_abs_position_constraint_residual_angstrom=max_position_residual,
        max_abs_velocity_constraint_residual_angstrom_per_ps=(
            max_velocity_residual
        ),
        cumulative_position_sweeps=cumulative_position_sweeps,
        cumulative_velocity_sweeps=cumulative_velocity_sweeps,
        last_position_sweeps=last_position_sweeps,
        last_velocity_sweeps=last_velocity_sweeps,
        last_maximum_pair_position_correction_angstrom=(
            last_maximum_correction
        ),
        evaluated_frame_count=evaluated_frame_count,
        trajectory_head_sha256=trajectory_head,
        current_frame_sha256=current_frame_sha256,
    )


def _continue(
    *,
    evaluator: ForceEvaluator,
    masses: tuple[float, ...],
    constraints: tuple[DoubleRattleDistanceConstraint, ...],
    checkpoint: OpenMMForceDoubleRattleCheckpoint,
    additional_steps: int,
) -> OpenMMForceDoubleRattleResult:
    steps = _integer(
        additional_steps,
        name="additional_steps",
        minimum=0,
        maximum=OPENMM_FORCE_DOUBLE_RATTLE_MAX_STEPS,
    )
    if checkpoint.step + steps > OPENMM_FORCE_DOUBLE_RATTLE_MAX_STEPS:
        raise OpenMMForceDoubleRattleError(
            "resumed step count exceeds its bound"
        )
    config = checkpoint.config
    coordinates = checkpoint.coordinates
    velocities = checkpoint.velocities
    forces = checkpoint.forces
    potential = checkpoint.potential_energy_kcal_per_mol
    initial_total = checkpoint.initial_total_energy_kcal_per_mol
    max_drift = checkpoint.max_abs_energy_drift_kcal_per_mol
    max_position = (
        checkpoint.max_abs_position_constraint_residual_angstrom
    )
    max_velocity = (
        checkpoint.max_abs_velocity_constraint_residual_angstrom_per_ps
    )
    cumulative_position = checkpoint.cumulative_position_sweeps
    cumulative_velocity = checkpoint.cumulative_velocity_sweeps
    frame_count = checkpoint.evaluated_frame_count
    trajectory_head = checkpoint.trajectory_head_sha256
    current_frame = _frame(
        step=checkpoint.step,
        coordinates=coordinates,
        velocities=velocities,
        forces=forces,
        potential_energy=potential,
        masses=masses,
        constraints=constraints,
        config=config,
        position_sweeps=checkpoint.last_position_sweeps,
        velocity_sweeps=checkpoint.last_velocity_sweeps,
        maximum_pair_position_correction_angstrom=(
            checkpoint.last_maximum_pair_position_correction_angstrom
        ),
        cumulative_position_sweeps=cumulative_position,
        cumulative_velocity_sweeps=cumulative_velocity,
        initial_total_energy=initial_total,
    )
    if current_frame["frame_sha256"] != checkpoint.current_frame_sha256:
        raise OpenMMForceDoubleRattleError(
            "checkpoint does not reproduce its current frame"
        )
    frames = [current_frame]
    timestep = config.timestep_ps
    lengths = config.box_lengths_angstrom
    for offset in range(1, steps + 1):
        half_velocity = [
            [
                velocities[index][axis]
                + 0.5
                * timestep
                * forces[index][axis]
                * OPENMM_FORCE_DOUBLE_RATTLE_ACCELERATION_FACTOR
                / masses[index]
                for axis in range(3)
            ]
            for index in range(len(masses))
        ]
        predicted = tuple(
            tuple(
                _wrap(
                    coordinates[index][axis]
                    + timestep * half_velocity[index][axis],
                    lengths[axis],
                )
                for axis in range(3)
            )
            for index in range(len(masses))
        )
        (
            next_coordinates,
            position_sweeps,
            position_residual,
            maximum_correction,
        ) = _project_positions(
            predicted,
            masses,
            constraints,
            config,
            reference_coordinates=coordinates,
        )
        for index in range(len(masses)):
            for axis in range(3):
                displacement = _minimum_image(
                    next_coordinates[index][axis]
                    - predicted[index][axis],
                    lengths[axis],
                )
                half_velocity[index][axis] += displacement / timestep
        next_potential, next_forces = _evaluate(
            evaluator,
            next_coordinates,
        )
        next_velocities_unprojected = tuple(
            tuple(
                half_velocity[index][axis]
                + 0.5
                * timestep
                * next_forces[index][axis]
                * OPENMM_FORCE_DOUBLE_RATTLE_ACCELERATION_FACTOR
                / masses[index]
                for axis in range(3)
            )
            for index in range(len(masses))
        )
        (
            next_velocities,
            velocity_sweeps,
            velocity_residual,
        ) = _project_velocities(
            next_coordinates,
            next_velocities_unprojected,
            masses,
            constraints,
            config,
        )
        cumulative_position += position_sweeps
        cumulative_velocity += velocity_sweeps
        max_position = max(max_position, position_residual)
        max_velocity = max(max_velocity, velocity_residual)
        coordinates = next_coordinates
        velocities = next_velocities
        forces = next_forces
        potential = next_potential
        step = checkpoint.step + offset
        frame = _frame(
            step=step,
            coordinates=coordinates,
            velocities=velocities,
            forces=forces,
            potential_energy=potential,
            masses=masses,
            constraints=constraints,
            config=config,
            position_sweeps=position_sweeps,
            velocity_sweeps=velocity_sweeps,
            maximum_pair_position_correction_angstrom=maximum_correction,
            cumulative_position_sweeps=cumulative_position,
            cumulative_velocity_sweeps=cumulative_velocity,
            initial_total_energy=initial_total,
        )
        drift = abs(
            _float_hex(
                frame["energy_drift_kcal_per_mol_hex"],
                name="frame energy drift",
            )
        )
        max_drift = max(max_drift, drift)
        frame_count += 1
        trajectory_head = _trajectory_head(
            trajectory_head,
            frame["frame_sha256"],  # type: ignore[arg-type]
            frame_count,
        )
        frames.append(frame)
    final = frames[-1]
    result_checkpoint = _checkpoint(
        system_sha256=checkpoint.system_sha256,
        force_configuration_sha256=(
            checkpoint.force_configuration_sha256
        ),
        mass_fingerprint_sha256=checkpoint.mass_fingerprint_sha256,
        constraint_fingerprint_sha256=(
            checkpoint.constraint_fingerprint_sha256
        ),
        config=config,
        step=checkpoint.step + steps,
        coordinates=coordinates,
        velocities=velocities,
        forces=forces,
        potential_energy=potential,
        initial_total_energy=initial_total,
        max_energy_drift=max_drift,
        max_position_residual=max_position,
        max_velocity_residual=max_velocity,
        cumulative_position_sweeps=cumulative_position,
        cumulative_velocity_sweeps=cumulative_velocity,
        last_position_sweeps=int(final["position_sweeps"]),
        last_velocity_sweeps=int(final["velocity_sweeps"]),
        last_maximum_correction=_float_hex(
            final[
                "maximum_pair_position_correction_angstrom_hex"
            ],
            name="frame maximum pair position correction",
        ),
        evaluated_frame_count=frame_count,
        trajectory_head=trajectory_head,
        current_frame_sha256=final["frame_sha256"],  # type: ignore[arg-type]
    )
    return OpenMMForceDoubleRattleResult(
        frames=tuple(frames),
        checkpoint=result_checkpoint,
    )


def run_openmm_force_double_rattle(
    *,
    system_sha256: str,
    force_configuration_sha256: str,
    coordinates: Sequence[Sequence[float]],
    velocities_angstrom_per_ps: Sequence[Sequence[float]],
    masses_da: Sequence[float],
    constraints: Sequence[DoubleRattleDistanceConstraint],
    config: OpenMMForceDoubleRattleConfig,
    steps: int,
    evaluator: ForceEvaluator,
) -> OpenMMForceDoubleRattleResult:
    """Run a fresh bounded trajectory using only the supplied force callback."""

    system_digest = _digest(system_sha256, name="system_sha256")
    force_digest = _digest(
        force_configuration_sha256,
        name="force_configuration_sha256",
    )
    initial_coordinates = _vectors(
        coordinates,
        name="coordinates",
    )
    initial_velocities = _vectors(
        velocities_angstrom_per_ps,
        name="velocities",
        count=len(initial_coordinates),
    )
    masses, constraint_rows, mass_document, constraint_document = (
        _validate_common(
            masses=masses_da,
            constraints=constraints,
            config=config,
            atom_count=len(initial_coordinates),
        )
    )
    step_count = _integer(
        steps,
        name="steps",
        minimum=0,
        maximum=OPENMM_FORCE_DOUBLE_RATTLE_MAX_STEPS,
    )
    (
        projected_coordinates,
        initial_position_sweeps,
        initial_position_residual,
        initial_maximum_correction,
    ) = _project_positions(
        initial_coordinates,
        masses,
        constraint_rows,
        config,
    )
    (
        projected_velocities,
        initial_velocity_sweeps,
        initial_velocity_residual,
    ) = _project_velocities(
        projected_coordinates,
        initial_velocities,
        masses,
        constraint_rows,
        config,
    )
    potential, forces = _evaluate(evaluator, projected_coordinates)
    initial_total = potential + _kinetic_energy(
        projected_velocities,
        masses,
    )
    frame = _frame(
        step=0,
        coordinates=projected_coordinates,
        velocities=projected_velocities,
        forces=forces,
        potential_energy=potential,
        masses=masses,
        constraints=constraint_rows,
        config=config,
        position_sweeps=initial_position_sweeps,
        velocity_sweeps=initial_velocity_sweeps,
        maximum_pair_position_correction_angstrom=(
            initial_maximum_correction
        ),
        cumulative_position_sweeps=initial_position_sweeps,
        cumulative_velocity_sweeps=initial_velocity_sweeps,
        initial_total_energy=initial_total,
    )
    trajectory_head = _trajectory_head(
        "",
        frame["frame_sha256"],  # type: ignore[arg-type]
        1,
    )
    checkpoint = _checkpoint(
        system_sha256=system_digest,
        force_configuration_sha256=force_digest,
        mass_fingerprint_sha256=mass_document[
            "mass_fingerprint_sha256"
        ],  # type: ignore[arg-type]
        constraint_fingerprint_sha256=constraint_document[
            "constraint_fingerprint_sha256"
        ],  # type: ignore[arg-type]
        config=config,
        step=0,
        coordinates=projected_coordinates,
        velocities=projected_velocities,
        forces=forces,
        potential_energy=potential,
        initial_total_energy=initial_total,
        max_energy_drift=0.0,
        max_position_residual=initial_position_residual,
        max_velocity_residual=initial_velocity_residual,
        cumulative_position_sweeps=initial_position_sweeps,
        cumulative_velocity_sweeps=initial_velocity_sweeps,
        last_position_sweeps=initial_position_sweeps,
        last_velocity_sweeps=initial_velocity_sweeps,
        last_maximum_correction=initial_maximum_correction,
        evaluated_frame_count=1,
        trajectory_head=trajectory_head,
        current_frame_sha256=frame["frame_sha256"],  # type: ignore[arg-type]
    )
    return _continue(
        evaluator=evaluator,
        masses=masses,
        constraints=constraint_rows,
        checkpoint=checkpoint,
        additional_steps=step_count,
    )


def resume_openmm_force_double_rattle(
    *,
    system_sha256: str,
    force_configuration_sha256: str,
    masses_da: Sequence[float],
    constraints: Sequence[DoubleRattleDistanceConstraint],
    config: OpenMMForceDoubleRattleConfig,
    checkpoint: OpenMMForceDoubleRattleCheckpoint | Mapping[str, object],
    additional_steps: int,
    evaluator: ForceEvaluator,
) -> OpenMMForceDoubleRattleResult:
    """Resume only after exact identity and current-force re-evaluation."""

    active = (
        checkpoint
        if isinstance(checkpoint, OpenMMForceDoubleRattleCheckpoint)
        else OpenMMForceDoubleRattleCheckpoint.from_dict(checkpoint)
    )
    system_digest = _digest(system_sha256, name="system_sha256")
    force_digest = _digest(
        force_configuration_sha256,
        name="force_configuration_sha256",
    )
    masses, constraint_rows, mass_document, constraint_document = (
        _validate_common(
            masses=masses_da,
            constraints=constraints,
            config=config,
            atom_count=len(active.coordinates),
        )
    )
    expected = {
        "system_sha256": system_digest,
        "force_configuration_sha256": force_digest,
        "mass_fingerprint_sha256": mass_document[
            "mass_fingerprint_sha256"
        ],
        "constraint_fingerprint_sha256": constraint_document[
            "constraint_fingerprint_sha256"
        ],
        "config_fingerprint_sha256": config.fingerprint_sha256,
    }
    observed = {
        "system_sha256": active.system_sha256,
        "force_configuration_sha256": (
            active.force_configuration_sha256
        ),
        "mass_fingerprint_sha256": active.mass_fingerprint_sha256,
        "constraint_fingerprint_sha256": (
            active.constraint_fingerprint_sha256
        ),
        "config_fingerprint_sha256": active.config.fingerprint_sha256,
    }
    if observed != expected:
        raise OpenMMForceDoubleRattleError(
            "double-RATTLE checkpoint identity mismatch"
        )
    reevaluated_energy, reevaluated_forces = _evaluate(
        evaluator,
        active.coordinates,
    )
    if (
        reevaluated_energy.hex()
        != active.potential_energy_kcal_per_mol.hex()
        or _hex_vectors(reevaluated_forces)
        != _hex_vectors(active.forces)
    ):
        raise OpenMMForceDoubleRattleError(
            "double-RATTLE checkpoint force state does not reproduce"
        )
    return _continue(
        evaluator=evaluator,
        masses=masses,
        constraints=constraint_rows,
        checkpoint=active,
        additional_steps=additional_steps,
    )


__all__ = [
    "DoubleRattleDistanceConstraint",
    "ForceEvaluator",
    "OPENMM_FORCE_DOUBLE_RATTLE_ALGORITHM_ID",
    "OPENMM_FORCE_DOUBLE_RATTLE_CHECKPOINT_SCHEMA_ID",
    "OPENMM_FORCE_DOUBLE_RATTLE_CONFIG_SCHEMA_ID",
    "OPENMM_FORCE_DOUBLE_RATTLE_FRAME_SCHEMA_ID",
    "OPENMM_FORCE_DOUBLE_RATTLE_MAX_ATOMS",
    "OpenMMForceDoubleRattleCheckpoint",
    "OpenMMForceDoubleRattleConfig",
    "OpenMMForceDoubleRattleError",
    "OpenMMForceDoubleRattleResult",
    "resume_openmm_force_double_rattle",
    "run_openmm_force_double_rattle",
]
