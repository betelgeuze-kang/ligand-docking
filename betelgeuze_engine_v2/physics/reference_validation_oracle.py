"""Independent scalar analytic oracle for frozen CPU validation fixtures.

This source intentionally uses only the Python standard library.  It does not
import the Engine v2 reference evaluator, validation protocol, Torch, NumPy, or
any molecular-solver package.  Forces are exact derivatives of the scalar
equations below, propagated with a small forward-mode dual-number kernel.

The module is an implementation artifact, not a validation result.  It does
not compare itself with the reference evaluator, authorize protocol execution,
fit parameters, or make a scientific or product claim.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from numbers import Real
from typing import Any


INDEPENDENT_ANALYTIC_ORACLE_SCHEMA_ID = "betelgeuze.engine_v2_independent_analytic_oracle/1.0.0"
INDEPENDENT_ANALYTIC_ORACLE_ID = "cpu_reference_validation_independent_analytic_oracle/1.0.0"
INDEPENDENT_ANALYTIC_ORACLE_VERSION = "1.0.0"

# This constant is duplicated deliberately instead of importing the runtime
# parameter module.  The artifact binding records and hashes this exact source.
COULOMB_KCAL_ANGSTROM_PER_MOL_E2 = 332.063713299

_COMPONENT_NAMES = (
    "harmonic_bond",
    "harmonic_angle",
    "periodic_torsion",
    "lennard_jones",
    "screened_coulomb",
)


class IndependentAnalyticOracleError(ValueError):
    """The independent input or analytic evaluation is invalid."""


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
        raise IndependentAnalyticOracleError("independent oracle payload is not canonical JSON") from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _finite(value: Real, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise IndependentAnalyticOracleError(f"{name} must be a real number")
    number = float(value)
    if not math.isfinite(number):
        raise IndependentAnalyticOracleError(f"{name} must be finite")
    return number


def _positive(value: Real, *, name: str, allow_zero: bool = False) -> float:
    number = _finite(value, name=name)
    if (number < 0.0) if allow_zero else (number <= 0.0):
        relation = "non-negative" if allow_zero else "positive"
        raise IndependentAnalyticOracleError(f"{name} must be {relation}")
    return number


def _index(value: int, *, name: str, atom_count: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise IndependentAnalyticOracleError(f"{name} must be an integer")
    result = int(value)
    if result < 0 or result >= atom_count:
        raise IndependentAnalyticOracleError(f"{name} is outside the atom range")
    return result


def _pair(first: int, second: int, *, atom_count: int) -> tuple[int, int]:
    atom_i = _index(first, name="pair atom index", atom_count=atom_count)
    atom_j = _index(second, name="pair atom index", atom_count=atom_count)
    if atom_i == atom_j:
        raise IndependentAnalyticOracleError("pair atom indices must be distinct")
    return tuple(sorted((atom_i, atom_j)))


@dataclass(frozen=True, slots=True)
class IndependentAnalyticOracleInput:
    """Primitive-only input for the independent scalar equations."""

    coordinates_angstrom: tuple[tuple[float, float, float], ...]
    topology_bonds: tuple[tuple[int, int], ...]
    atom_nonbonded: tuple[tuple[int, float, float, float], ...]
    bonds: tuple[tuple[int, int, float, float], ...] = ()
    angles: tuple[tuple[int, int, int, float, float], ...] = ()
    torsions: tuple[tuple[int, int, int, int, int, float, float], ...] = ()
    excluded_pairs: tuple[tuple[int, int], ...] = ()
    scaled_pairs: tuple[tuple[int, int, float, float], ...] = ()
    cutoff_angstrom: float = 10.0
    switch_start_angstrom: float = 8.0
    dielectric: float = 1.0
    screening_kappa_per_angstrom: float = 0.0
    orthorhombic_cell_angstrom: tuple[float, float, float] | None = None
    periodic_axes: tuple[bool, bool, bool] = (False, False, False)
    minimum_pair_distance_angstrom: float = 1.0e-6
    schema_id: str = INDEPENDENT_ANALYTIC_ORACLE_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != INDEPENDENT_ANALYTIC_ORACLE_SCHEMA_ID:
            raise IndependentAnalyticOracleError("unsupported independent analytic oracle input schema")
        coordinates = tuple(
            tuple(_finite(value, name="coordinate") for value in row) for row in self.coordinates_angstrom
        )
        if not coordinates or any(len(row) != 3 for row in coordinates):
            raise IndependentAnalyticOracleError("coordinates must have non-empty [atom,3] shape")
        atom_count = len(coordinates)
        topology_bonds = tuple(_pair(*row, atom_count=atom_count) for row in self.topology_bonds)
        if len(topology_bonds) != len(set(topology_bonds)):
            raise IndependentAnalyticOracleError("topology bonds must be unique")

        atom_rows: list[tuple[int, float, float, float]] = []
        for row in self.atom_nonbonded:
            if len(row) != 4:
                raise IndependentAnalyticOracleError("atom nonbonded rows must contain four values")
            atom_rows.append(
                (
                    _index(row[0], name="nonbonded atom index", atom_count=atom_count),
                    _positive(row[1], name="sigma_angstrom"),
                    _positive(row[2], name="epsilon_kcal_per_mol", allow_zero=True),
                    _finite(row[3], name="charge_e"),
                )
            )
        if sorted(row[0] for row in atom_rows) != list(range(atom_count)):
            raise IndependentAnalyticOracleError("atom nonbonded rows must exactly cover every atom")

        bond_rows: list[tuple[int, int, float, float]] = []
        for row in self.bonds:
            if len(row) != 4:
                raise IndependentAnalyticOracleError("bond rows must contain four values")
            atom_i, atom_j = _pair(row[0], row[1], atom_count=atom_count)
            bond_rows.append(
                (
                    atom_i,
                    atom_j,
                    _positive(row[2], name="bond equilibrium"),
                    _positive(row[3], name="bond force constant"),
                )
            )

        angle_rows: list[tuple[int, int, int, float, float]] = []
        for row in self.angles:
            if len(row) != 5:
                raise IndependentAnalyticOracleError("angle rows must contain five values")
            indices = tuple(_index(value, name="angle atom index", atom_count=atom_count) for value in row[:3])
            if len(set(indices)) != 3:
                raise IndependentAnalyticOracleError("angle atom indices must be distinct")
            equilibrium = _finite(row[3], name="angle equilibrium")
            if not 0.0 < equilibrium < math.pi:
                raise IndependentAnalyticOracleError("angle equilibrium must lie in (0,pi)")
            angle_rows.append(
                (
                    indices[0],
                    indices[1],
                    indices[2],
                    equilibrium,
                    _positive(row[4], name="angle force constant"),
                )
            )

        torsion_rows: list[tuple[int, int, int, int, int, float, float]] = []
        for row in self.torsions:
            if len(row) != 7:
                raise IndependentAnalyticOracleError("torsion rows must contain seven values")
            indices = tuple(_index(value, name="torsion atom index", atom_count=atom_count) for value in row[:4])
            if len(set(indices)) != 4:
                raise IndependentAnalyticOracleError("torsion atom indices must be distinct")
            periodicity = row[4]
            if isinstance(periodicity, bool) or not isinstance(periodicity, int):
                raise IndependentAnalyticOracleError("torsion periodicity must be an integer")
            if periodicity < 1 or periodicity > 12:
                raise IndependentAnalyticOracleError("torsion periodicity must lie in [1,12]")
            torsion_rows.append(
                (
                    indices[0],
                    indices[1],
                    indices[2],
                    indices[3],
                    int(periodicity),
                    _finite(row[5], name="torsion phase"),
                    _positive(row[6], name="torsion amplitude", allow_zero=True),
                )
            )

        excluded = tuple(_pair(*row, atom_count=atom_count) for row in self.excluded_pairs)
        if len(excluded) != len(set(excluded)):
            raise IndependentAnalyticOracleError("excluded pairs must be unique")
        scaled_rows: list[tuple[int, int, float, float]] = []
        for row in self.scaled_pairs:
            if len(row) != 4:
                raise IndependentAnalyticOracleError("scaled pair rows must contain four values")
            atom_i, atom_j = _pair(row[0], row[1], atom_count=atom_count)
            scaled_rows.append(
                (
                    atom_i,
                    atom_j,
                    _positive(row[2], name="LJ scale", allow_zero=True),
                    _positive(row[3], name="electrostatic scale", allow_zero=True),
                )
            )
        scaled_keys = [(row[0], row[1]) for row in scaled_rows]
        if len(scaled_keys) != len(set(scaled_keys)):
            raise IndependentAnalyticOracleError("scaled pairs must be unique")
        if set(excluded) & set(scaled_keys):
            raise IndependentAnalyticOracleError("a pair cannot be both excluded and scaled")

        cutoff = _positive(self.cutoff_angstrom, name="cutoff_angstrom")
        switch_start = _positive(
            self.switch_start_angstrom,
            name="switch_start_angstrom",
            allow_zero=True,
        )
        if switch_start >= cutoff:
            raise IndependentAnalyticOracleError("switch_start_angstrom must be below cutoff_angstrom")
        periodic_axes = tuple(self.periodic_axes)
        if len(periodic_axes) != 3 or not all(isinstance(value, bool) for value in periodic_axes):
            raise IndependentAnalyticOracleError("periodic_axes must contain three booleans")
        cell = self.orthorhombic_cell_angstrom
        if cell is None:
            if any(periodic_axes):
                raise IndependentAnalyticOracleError("periodic axes require an orthorhombic cell")
            normalized_cell = None
        else:
            normalized_cell = tuple(_positive(value, name="orthorhombic cell length") for value in cell)
            if len(normalized_cell) != 3:
                raise IndependentAnalyticOracleError("orthorhombic cell must have three lengths")

        object.__setattr__(self, "coordinates_angstrom", coordinates)
        object.__setattr__(self, "topology_bonds", tuple(sorted(topology_bonds)))
        object.__setattr__(self, "atom_nonbonded", tuple(sorted(atom_rows)))
        object.__setattr__(self, "bonds", tuple(bond_rows))
        object.__setattr__(self, "angles", tuple(angle_rows))
        object.__setattr__(self, "torsions", tuple(torsion_rows))
        object.__setattr__(self, "excluded_pairs", tuple(sorted(excluded)))
        object.__setattr__(self, "scaled_pairs", tuple(sorted(scaled_rows)))
        object.__setattr__(self, "cutoff_angstrom", cutoff)
        object.__setattr__(self, "switch_start_angstrom", switch_start)
        object.__setattr__(self, "dielectric", _positive(self.dielectric, name="dielectric"))
        object.__setattr__(
            self,
            "screening_kappa_per_angstrom",
            _positive(
                self.screening_kappa_per_angstrom,
                name="screening_kappa_per_angstrom",
                allow_zero=True,
            ),
        )
        object.__setattr__(self, "orthorhombic_cell_angstrom", normalized_cell)
        object.__setattr__(self, "periodic_axes", periodic_axes)
        object.__setattr__(
            self,
            "minimum_pair_distance_angstrom",
            _positive(
                self.minimum_pair_distance_angstrom,
                name="minimum_pair_distance_angstrom",
            ),
        )

    @property
    def atom_count(self) -> int:
        return len(self.coordinates_angstrom)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "coordinates_angstrom": [list(row) for row in self.coordinates_angstrom],
            "topology_bonds": [list(row) for row in self.topology_bonds],
            "atom_nonbonded": [list(row) for row in self.atom_nonbonded],
            "bonds": [list(row) for row in self.bonds],
            "angles": [list(row) for row in self.angles],
            "torsions": [list(row) for row in self.torsions],
            "excluded_pairs": [list(row) for row in self.excluded_pairs],
            "scaled_pairs": [list(row) for row in self.scaled_pairs],
            "cutoff_angstrom": self.cutoff_angstrom,
            "switch_start_angstrom": self.switch_start_angstrom,
            "dielectric": self.dielectric,
            "screening_kappa_per_angstrom": self.screening_kappa_per_angstrom,
            "orthorhombic_cell_angstrom": (
                None if self.orthorhombic_cell_angstrom is None else list(self.orthorhombic_cell_angstrom)
            ),
            "periodic_axes": list(self.periodic_axes),
            "minimum_pair_distance_angstrom": (self.minimum_pair_distance_angstrom),
            "parameter_origin": "synthetic_protocol_values_not_fit_data",
            "scientifically_validated": False,
        }

    @property
    def input_sha256(self) -> str:
        return _sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class IndependentAnalyticOracleEvaluation:
    """One in-memory oracle evaluation; never a validation receipt."""

    input_sha256: str
    component_energies_kcal_per_mol: tuple[tuple[str, float], ...]
    total_energy_kcal_per_mol: float
    forces_kcal_per_mol_angstrom: tuple[tuple[float, float, float], ...]
    schema_id: str = INDEPENDENT_ANALYTIC_ORACLE_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != INDEPENDENT_ANALYTIC_ORACLE_SCHEMA_ID:
            raise IndependentAnalyticOracleError("unsupported independent oracle evaluation schema")
        if len(self.input_sha256) != 64 or any(character not in "0123456789abcdef" for character in self.input_sha256):
            raise IndependentAnalyticOracleError("oracle input identity must be a lowercase SHA-256")
        if tuple(name for name, _ in self.component_energies_kcal_per_mol) != (_COMPONENT_NAMES):
            raise IndependentAnalyticOracleError("oracle component order does not match the frozen equation order")
        values = [value for _, value in self.component_energies_kcal_per_mol] + [
            self.total_energy_kcal_per_mol,
            *(value for row in self.forces_kcal_per_mol_angstrom for value in row),
        ]
        if any(not math.isfinite(float(value)) for value in values):
            raise IndependentAnalyticOracleError("oracle evaluation contains a non-finite value")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "oracle_id": INDEPENDENT_ANALYTIC_ORACLE_ID,
            "oracle_version": INDEPENDENT_ANALYTIC_ORACLE_VERSION,
            "input_sha256": self.input_sha256,
            "component_energies": [
                {"name": name, "value": value, "unit": "kcal/mol"}
                for name, value in self.component_energies_kcal_per_mol
            ],
            "total_energy": {
                "value": self.total_energy_kcal_per_mol,
                "unit": "kcal/mol",
            },
            "forces": {
                "values": [list(row) for row in self.forces_kcal_per_mol_angstrom],
                "unit": "kcal/mol/angstrom",
                "definition": "negative_exact_forward_mode_derivative_of_total_energy",
            },
            "validation_receipt": False,
            "scientifically_validated": False,
            "claim_safe": False,
        }


@dataclass(frozen=True, slots=True)
class _Dual:
    value: float
    derivative: tuple[float, ...]

    @classmethod
    def constant(cls, value: Real, width: int) -> _Dual:
        return cls(float(value), (0.0,) * width)

    def _coerce(self, other: _Dual | Real) -> _Dual:
        if isinstance(other, _Dual):
            if len(other.derivative) != len(self.derivative):
                raise IndependentAnalyticOracleError("dual derivative widths do not match")
            return other
        return _Dual.constant(_finite(other, name="dual scalar"), len(self.derivative))

    def __add__(self, other: _Dual | Real) -> _Dual:
        right = self._coerce(other)
        return _Dual(
            self.value + right.value,
            tuple(a + b for a, b in zip(self.derivative, right.derivative)),
        )

    __radd__ = __add__

    def __sub__(self, other: _Dual | Real) -> _Dual:
        right = self._coerce(other)
        return _Dual(
            self.value - right.value,
            tuple(a - b for a, b in zip(self.derivative, right.derivative)),
        )

    def __rsub__(self, other: _Dual | Real) -> _Dual:
        return self._coerce(other).__sub__(self)

    def __neg__(self) -> _Dual:
        return _Dual(-self.value, tuple(-value for value in self.derivative))

    def __mul__(self, other: _Dual | Real) -> _Dual:
        right = self._coerce(other)
        return _Dual(
            self.value * right.value,
            tuple(self.value * b + right.value * a for a, b in zip(self.derivative, right.derivative)),
        )

    __rmul__ = __mul__

    def __truediv__(self, other: _Dual | Real) -> _Dual:
        right = self._coerce(other)
        if right.value == 0.0:
            raise IndependentAnalyticOracleError("dual division by zero")
        denominator = right.value * right.value
        return _Dual(
            self.value / right.value,
            tuple((a * right.value - self.value * b) / denominator for a, b in zip(self.derivative, right.derivative)),
        )

    def __rtruediv__(self, other: _Dual | Real) -> _Dual:
        return self._coerce(other).__truediv__(self)

    def __pow__(self, exponent: int) -> _Dual:
        if isinstance(exponent, bool) or not isinstance(exponent, int):
            raise IndependentAnalyticOracleError("dual exponent must be an integer")
        if exponent == 0:
            return _Dual.constant(1.0, len(self.derivative))
        if self.value == 0.0 and exponent < 1:
            raise IndependentAnalyticOracleError("invalid dual power at zero")
        value = self.value**exponent
        factor = exponent * (self.value ** (exponent - 1))
        return _Dual(value, tuple(factor * item for item in self.derivative))


def _sqrt(value: _Dual) -> _Dual:
    if value.value <= 0.0:
        raise IndependentAnalyticOracleError("analytic derivative is undefined for a zero-length vector")
    root = math.sqrt(value.value)
    return _Dual(root, tuple(item / (2.0 * root) for item in value.derivative))


def _exp(value: _Dual) -> _Dual:
    result = math.exp(value.value)
    return _Dual(result, tuple(result * item for item in value.derivative))


def _cos(value: _Dual) -> _Dual:
    return _Dual(
        math.cos(value.value),
        tuple(-math.sin(value.value) * item for item in value.derivative),
    )


def _acos(value: _Dual) -> _Dual:
    if value.value <= -1.0 or value.value >= 1.0:
        raise IndependentAnalyticOracleError("analytic acos derivative requires an interior cosine")
    factor = -1.0 / math.sqrt(1.0 - value.value * value.value)
    return _Dual(math.acos(value.value), tuple(factor * item for item in value.derivative))


def _atan2(y_value: _Dual, x_value: _Dual) -> _Dual:
    denominator = x_value.value * x_value.value + y_value.value * y_value.value
    if denominator <= 0.0:
        raise IndependentAnalyticOracleError("analytic atan2 derivative is undefined at the origin")
    derivative = tuple(
        (x_value.value * dy - y_value.value * dx) / denominator
        for dy, dx in zip(y_value.derivative, x_value.derivative)
    )
    return _Dual(math.atan2(y_value.value, x_value.value), derivative)


def _dot(first: tuple[_Dual, _Dual, _Dual], second: tuple[_Dual, _Dual, _Dual]) -> _Dual:
    return sum((a * b for a, b in zip(first, second)), first[0] * 0.0)


def _cross(
    first: tuple[_Dual, _Dual, _Dual],
    second: tuple[_Dual, _Dual, _Dual],
) -> tuple[_Dual, _Dual, _Dual]:
    return (
        first[1] * second[2] - first[2] * second[1],
        first[2] * second[0] - first[0] * second[2],
        first[0] * second[1] - first[1] * second[0],
    )


def _norm(vector: tuple[_Dual, _Dual, _Dual]) -> _Dual:
    return _sqrt(_dot(vector, vector))


def _scale(vector: tuple[_Dual, _Dual, _Dual], scalar: _Dual | Real) -> tuple[_Dual, _Dual, _Dual]:
    return tuple(value * scalar for value in vector)  # type: ignore[return-value]


def _subtract(
    first: tuple[_Dual, _Dual, _Dual],
    second: tuple[_Dual, _Dual, _Dual],
) -> tuple[_Dual, _Dual, _Dual]:
    return tuple(a - b for a, b in zip(first, second))  # type: ignore[return-value]


def _minimum_image(
    vector: tuple[_Dual, _Dual, _Dual],
    cell: tuple[float, float, float] | None,
    periodic_axes: tuple[bool, bool, bool],
) -> tuple[_Dual, _Dual, _Dual]:
    if cell is None:
        return vector
    result: list[_Dual] = []
    for axis, component in enumerate(vector):
        if periodic_axes[axis]:
            image = round(component.value / cell[axis])
            result.append(component - image * cell[axis])
        else:
            result.append(component)
    return result[0], result[1], result[2]


def _vector(
    coordinates: tuple[tuple[_Dual, _Dual, _Dual], ...],
    first: int,
    second: int,
    source: IndependentAnalyticOracleInput,
) -> tuple[_Dual, _Dual, _Dual]:
    return _minimum_image(
        _subtract(coordinates[first], coordinates[second]),
        source.orthorhombic_cell_angstrom,
        source.periodic_axes,
    )


def _angle(first: tuple[_Dual, _Dual, _Dual], second: tuple[_Dual, _Dual, _Dual]) -> _Dual:
    first_squared = _dot(first, first)
    second_squared = _dot(second, second)
    if first_squared.value <= 1.0e-24 or second_squared.value <= 1.0e-24:
        raise IndependentAnalyticOracleError("angle_zero_length_vector")
    first_norm = _sqrt(first_squared)
    second_norm = _sqrt(second_squared)
    cosine = _dot(first, second) / (first_norm * second_norm)
    lower = -1.0 + 1.0e-12
    upper = 1.0 - 1.0e-12
    if cosine.value <= lower:
        cosine = _Dual.constant(lower, len(cosine.derivative))
    elif cosine.value >= upper:
        cosine = _Dual.constant(upper, len(cosine.derivative))
    return _acos(cosine)


def _torsion_angle(
    coordinates: tuple[tuple[_Dual, _Dual, _Dual], ...],
    atom_i: int,
    atom_j: int,
    atom_k: int,
    atom_l: int,
    source: IndependentAnalyticOracleInput,
) -> _Dual:
    b0 = _vector(coordinates, atom_i, atom_j, source)
    b1 = _vector(coordinates, atom_k, atom_j, source)
    b2 = _vector(coordinates, atom_l, atom_k, source)
    b1_squared = _dot(b1, b1)
    if b1_squared.value <= 1.0e-24:
        raise IndependentAnalyticOracleError("torsion_zero_length_central_bond")
    b1_norm = _sqrt(b1_squared)
    axis = _scale(b1, 1.0 / b1_norm)
    v = _subtract(b0, _scale(axis, _dot(b0, axis)))
    w = _subtract(b2, _scale(axis, _dot(b2, axis)))
    if _dot(v, v).value <= 1.0e-24 or _dot(w, w).value <= 1.0e-24:
        raise IndependentAnalyticOracleError("torsion_undefined_for_collinear_atoms")
    return _atan2(_dot(_cross(axis, v), w), _dot(v, w))


def _switch(distance: _Dual, start: float, cutoff: float) -> _Dual:
    if distance.value <= start:
        return _Dual.constant(1.0, len(distance.derivative))
    if distance.value >= cutoff:
        return _Dual.constant(0.0, len(distance.derivative))
    x_value = (distance - start) / (cutoff - start)
    return 1.0 - 10.0 * (x_value**3) + 15.0 * (x_value**4) - 6.0 * (x_value**5)


def evaluate_independent_analytic_oracle(
    source: IndependentAnalyticOracleInput,
) -> IndependentAnalyticOracleEvaluation:
    """Evaluate independent scalar equations and their exact analytic forces."""

    if not isinstance(source, IndependentAnalyticOracleInput):
        raise IndependentAnalyticOracleError("source must be an IndependentAnalyticOracleInput")
    width = source.atom_count * 3
    coordinates: list[tuple[_Dual, _Dual, _Dual]] = []
    for atom_index, row in enumerate(source.coordinates_angstrom):
        dual_row: list[_Dual] = []
        for axis, value in enumerate(row):
            derivative = [0.0] * width
            derivative[3 * atom_index + axis] = 1.0
            dual_row.append(_Dual(value, tuple(derivative)))
        coordinates.append((dual_row[0], dual_row[1], dual_row[2]))
    coordinate_rows = tuple(coordinates)
    zero = _Dual.constant(0.0, width)
    components = {name: zero for name in _COMPONENT_NAMES}

    for atom_i, atom_j, equilibrium, force_constant in source.bonds:
        distance = _norm(_vector(coordinate_rows, atom_i, atom_j, source))
        components["harmonic_bond"] = components["harmonic_bond"] + (
            0.5 * force_constant * ((distance - equilibrium) ** 2)
        )

    for atom_i, atom_j, atom_k, equilibrium, force_constant in source.angles:
        value = _angle(
            _vector(coordinate_rows, atom_i, atom_j, source),
            _vector(coordinate_rows, atom_k, atom_j, source),
        )
        components["harmonic_angle"] = components["harmonic_angle"] + (
            0.5 * force_constant * ((value - equilibrium) ** 2)
        )

    for (
        atom_i,
        atom_j,
        atom_k,
        atom_l,
        periodicity,
        phase,
        amplitude,
    ) in source.torsions:
        phi = _torsion_angle(coordinate_rows, atom_i, atom_j, atom_k, atom_l, source)
        components["periodic_torsion"] = components["periodic_torsion"] + (
            amplitude * (1.0 + _cos(periodicity * phi - phase))
        )

    atom_parameters = {row[0]: (row[1], row[2], row[3]) for row in source.atom_nonbonded}
    excluded = set(source.excluded_pairs)
    scaled = {(row[0], row[1]): (row[2], row[3]) for row in source.scaled_pairs}
    for atom_i in range(source.atom_count):
        for atom_j in range(atom_i + 1, source.atom_count):
            pair_vector = _vector(coordinate_rows, atom_i, atom_j, source)
            squared_distance = _dot(pair_vector, pair_vector)
            if squared_distance.value < source.minimum_pair_distance_angstrom**2:
                raise IndependentAnalyticOracleError("nonbonded_pair_below_minimum_pair_distance_angstrom")
            distance = _sqrt(squared_distance)
            if distance.value > source.cutoff_angstrom:
                continue
            first = atom_parameters[atom_i]
            second = atom_parameters[atom_j]
            pair = (atom_i, atom_j)
            if pair in excluded:
                lj_scale = 0.0
                electrostatic_scale = 0.0
            else:
                lj_scale, electrostatic_scale = scaled.get(pair, (1.0, 1.0))
            sigma = 0.5 * (first[0] + second[0])
            epsilon = math.sqrt(first[1] * second[1])
            ratio6 = (sigma / distance) ** 6
            pair_lj = 4.0 * epsilon * ((ratio6**2) - ratio6) * lj_scale
            pair_electrostatic = (
                COULOMB_KCAL_ANGSTROM_PER_MOL_E2
                * first[2]
                * second[2]
                * _exp(-source.screening_kappa_per_angstrom * distance)
                / (source.dielectric * distance)
                * electrostatic_scale
            )
            switch_value = _switch(
                distance,
                source.switch_start_angstrom,
                source.cutoff_angstrom,
            )
            components["lennard_jones"] = components["lennard_jones"] + (pair_lj * switch_value)
            components["screened_coulomb"] = components["screened_coulomb"] + (pair_electrostatic * switch_value)

    total = sum((components[name] for name in _COMPONENT_NAMES), zero)
    forces = tuple(
        tuple(-total.derivative[3 * atom_index + axis] for axis in range(3)) for atom_index in range(source.atom_count)
    )
    return IndependentAnalyticOracleEvaluation(
        input_sha256=source.input_sha256,
        component_energies_kcal_per_mol=tuple((name, components[name].value) for name in _COMPONENT_NAMES),
        total_energy_kcal_per_mol=total.value,
        forces_kcal_per_mol_angstrom=forces,
    )


__all__ = [
    "COULOMB_KCAL_ANGSTROM_PER_MOL_E2",
    "INDEPENDENT_ANALYTIC_ORACLE_ID",
    "INDEPENDENT_ANALYTIC_ORACLE_SCHEMA_ID",
    "INDEPENDENT_ANALYTIC_ORACLE_VERSION",
    "IndependentAnalyticOracleError",
    "IndependentAnalyticOracleEvaluation",
    "IndependentAnalyticOracleInput",
    "evaluate_independent_analytic_oracle",
]
