"""Explicit, versioned parameter contracts for the CPU reference force field."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from numbers import Real
import operator
from types import MappingProxyType
from typing import Any, Mapping

REFERENCE_PARAMETER_SCHEMA_ID = "betelgeuze.engine_v2_reference_parameters/1.0.0"
COULOMB_KCAL_ANGSTROM_PER_MOL_E2 = 332.063713299


class ReferenceParameterError(ValueError):
    """Parameter values or applicability bounds are incomplete or inconsistent."""


def _finite_float(value: float, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ReferenceParameterError(f"{name} must be a real number")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ReferenceParameterError(f"{name} must be a finite real number") from None
    if not math.isfinite(number):
        raise ReferenceParameterError(f"{name} must be finite")
    return number


def _finite_positive(value: float, *, name: str, allow_zero: bool = False) -> float:
    number = _finite_float(value, name=name)
    if not math.isfinite(number) or (number < 0.0 if allow_zero else number <= 0.0):
        relation = "non-negative" if allow_zero else "positive"
        raise ReferenceParameterError(f"{name} must be finite and {relation}")
    return number


def _exact_int(
    value: int,
    *,
    name: str,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    if isinstance(value, bool):
        raise ReferenceParameterError(f"{name} must be an integer")
    try:
        integer = operator.index(value)
    except TypeError:
        if not isinstance(value, Real):
            raise ReferenceParameterError(f"{name} must be an integer") from None
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError):
            raise ReferenceParameterError(f"{name} must be an integer") from None
        if not math.isfinite(number) or not number.is_integer():
            raise ReferenceParameterError(f"{name} must be an integer")
        integer = int(number)
    integer = int(integer)
    if minimum is not None and integer < minimum:
        raise ReferenceParameterError(f"{name} must be at least {minimum}")
    if maximum is not None and integer > maximum:
        raise ReferenceParameterError(f"{name} must be at most {maximum}")
    return integer


def _exact_bool(value: bool, *, name: str) -> bool:
    if not isinstance(value, bool):
        raise ReferenceParameterError(f"{name} must be a boolean")
    return value


def _digest(value: str, *, name: str) -> str:
    if not isinstance(value, str):
        raise ReferenceParameterError(f"{name} must be a SHA-256 digest string")
    digest = value.strip().lower()
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ReferenceParameterError(f"{name} must be a lowercase SHA-256 digest")
    return digest


def _freeze_json(value: Any, *, path: str = "metadata") -> Any:
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ReferenceParameterError(f"{path} contains a non-finite float")
        return float(value)
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise ReferenceParameterError(f"{path} keys must be strings")
        normalized: dict[str, Any] = {}
        for key in sorted(value):
            normalized[key] = _freeze_json(value[key], path=f"{path}.{key}")
        return MappingProxyType(normalized)
    if isinstance(value, (tuple, list)):
        return tuple(
            _freeze_json(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        )
    raise ReferenceParameterError(
        f"{path} contains unsupported JSON value {type(value).__name__}"
    )


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def _canonical_sha256(payload: object) -> str:
    try:
        encoded = json.dumps(
            _thaw_json(payload),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ReferenceParameterError("parameter payload is not canonical JSON") from exc
    return hashlib.sha256(encoded).hexdigest()


def _pair(first: int, second: int) -> tuple[int, int]:
    i, j = sorted(
        (
            _exact_int(first, name="pair atom index", minimum=0),
            _exact_int(second, name="pair atom index", minimum=0),
        )
    )
    if i == j:
        raise ReferenceParameterError("pair indices must be distinct")
    return i, j


@dataclass(frozen=True)
class HarmonicBondParameter:
    atom_i: int
    atom_j: int
    equilibrium_angstrom: float
    force_constant_kcal_per_mol_angstrom2: float

    def __post_init__(self) -> None:
        i, j = _pair(self.atom_i, self.atom_j)
        object.__setattr__(self, "atom_i", i)
        object.__setattr__(self, "atom_j", j)
        object.__setattr__(
            self,
            "equilibrium_angstrom",
            _finite_positive(self.equilibrium_angstrom, name="equilibrium_angstrom"),
        )
        object.__setattr__(
            self,
            "force_constant_kcal_per_mol_angstrom2",
            _finite_positive(
                self.force_constant_kcal_per_mol_angstrom2,
                name="bond force constant",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "atom_i": self.atom_i,
            "atom_j": self.atom_j,
            "equilibrium_angstrom": self.equilibrium_angstrom,
            "force_constant_kcal_per_mol_angstrom2": self.force_constant_kcal_per_mol_angstrom2,
        }


@dataclass(frozen=True)
class HarmonicAngleParameter:
    atom_i: int
    atom_j: int
    atom_k: int
    equilibrium_radians: float
    force_constant_kcal_per_mol_radian2: float

    def __post_init__(self) -> None:
        indices = tuple(
            _exact_int(value, name="angle atom index", minimum=0)
            for value in (self.atom_i, self.atom_j, self.atom_k)
        )
        if len(set(indices)) != 3:
            raise ReferenceParameterError("angle indices must be distinct")
        equilibrium = _finite_float(
            self.equilibrium_radians,
            name="equilibrium_radians",
        )
        if not 0.0 < equilibrium < math.pi:
            raise ReferenceParameterError("equilibrium_radians must be in (0,pi)")
        object.__setattr__(self, "atom_i", indices[0])
        object.__setattr__(self, "atom_j", indices[1])
        object.__setattr__(self, "atom_k", indices[2])
        object.__setattr__(self, "equilibrium_radians", equilibrium)
        object.__setattr__(
            self,
            "force_constant_kcal_per_mol_radian2",
            _finite_positive(
                self.force_constant_kcal_per_mol_radian2,
                name="angle force constant",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "atom_i": int(self.atom_i),
            "atom_j": int(self.atom_j),
            "atom_k": int(self.atom_k),
            "equilibrium_radians": float(self.equilibrium_radians),
            "force_constant_kcal_per_mol_radian2": self.force_constant_kcal_per_mol_radian2,
        }


@dataclass(frozen=True)
class PeriodicTorsionParameter:
    atom_i: int
    atom_j: int
    atom_k: int
    atom_l: int
    periodicity: int
    phase_radians: float
    amplitude_kcal_per_mol: float

    def __post_init__(self) -> None:
        indices = tuple(
            _exact_int(value, name="torsion atom index", minimum=0)
            for value in (self.atom_i, self.atom_j, self.atom_k, self.atom_l)
        )
        if len(set(indices)) != 4:
            raise ReferenceParameterError("torsion indices must be distinct")
        periodicity = _exact_int(
            self.periodicity,
            name="torsion periodicity",
            minimum=1,
            maximum=12,
        )
        phase = _finite_float(self.phase_radians, name="torsion phase")
        object.__setattr__(self, "atom_i", indices[0])
        object.__setattr__(self, "atom_j", indices[1])
        object.__setattr__(self, "atom_k", indices[2])
        object.__setattr__(self, "atom_l", indices[3])
        object.__setattr__(self, "periodicity", periodicity)
        object.__setattr__(self, "phase_radians", phase)
        object.__setattr__(
            self,
            "amplitude_kcal_per_mol",
            _finite_positive(
                self.amplitude_kcal_per_mol,
                name="torsion amplitude",
                allow_zero=True,
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "atom_i": int(self.atom_i),
            "atom_j": int(self.atom_j),
            "atom_k": int(self.atom_k),
            "atom_l": int(self.atom_l),
            "periodicity": int(self.periodicity),
            "phase_radians": float(self.phase_radians),
            "amplitude_kcal_per_mol": self.amplitude_kcal_per_mol,
        }


@dataclass(frozen=True)
class AtomNonbondedParameter:
    atom_index: int
    sigma_angstrom: float
    epsilon_kcal_per_mol: float
    charge_e: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "atom_index",
            _exact_int(self.atom_index, name="atom_index", minimum=0),
        )
        object.__setattr__(
            self,
            "sigma_angstrom",
            _finite_positive(self.sigma_angstrom, name="sigma_angstrom"),
        )
        object.__setattr__(
            self,
            "epsilon_kcal_per_mol",
            _finite_positive(
                self.epsilon_kcal_per_mol,
                name="epsilon_kcal_per_mol",
                allow_zero=True,
            ),
        )
        object.__setattr__(
            self,
            "charge_e",
            _finite_float(self.charge_e, name="charge_e"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "atom_index": int(self.atom_index),
            "sigma_angstrom": self.sigma_angstrom,
            "epsilon_kcal_per_mol": self.epsilon_kcal_per_mol,
            "charge_e": float(self.charge_e),
        }


@dataclass(frozen=True)
class PairScalingParameter:
    atom_i: int
    atom_j: int
    lj_scale: float
    electrostatic_scale: float

    def __post_init__(self) -> None:
        i, j = _pair(self.atom_i, self.atom_j)
        object.__setattr__(self, "atom_i", i)
        object.__setattr__(self, "atom_j", j)
        for name in ("lj_scale", "electrostatic_scale"):
            value = _finite_float(getattr(self, name), name=name)
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ReferenceParameterError(f"{name} must be in [0,1]")
            object.__setattr__(self, name, value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "atom_i": self.atom_i,
            "atom_j": self.atom_j,
            "lj_scale": float(self.lj_scale),
            "electrostatic_scale": float(self.electrostatic_scale),
        }


@dataclass(frozen=True)
class ReferenceApplicabilityDomain:
    max_atoms: int = 10_000
    max_bonds: int = 40_000
    max_angles: int = 80_000
    max_torsions: int = 160_000
    max_nonbonded_pairs: int = 2_000_000
    periodic_orthorhombic_supported: bool = True
    minimum_pair_distance_angstrom: float = 0.35

    def __post_init__(self) -> None:
        for name in (
            "max_atoms",
            "max_bonds",
            "max_angles",
            "max_torsions",
            "max_nonbonded_pairs",
        ):
            object.__setattr__(
                self,
                name,
                _exact_int(getattr(self, name), name=name, minimum=0),
            )
        object.__setattr__(
            self,
            "periodic_orthorhombic_supported",
            _exact_bool(
                self.periodic_orthorhombic_supported,
                name="periodic_orthorhombic_supported",
            ),
        )
        object.__setattr__(
            self,
            "minimum_pair_distance_angstrom",
            _finite_positive(
                self.minimum_pair_distance_angstrom,
                name="minimum_pair_distance_angstrom",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_atoms": int(self.max_atoms),
            "max_bonds": int(self.max_bonds),
            "max_angles": int(self.max_angles),
            "max_torsions": int(self.max_torsions),
            "max_nonbonded_pairs": int(self.max_nonbonded_pairs),
            "periodic_orthorhombic_supported": bool(self.periodic_orthorhombic_supported),
            "minimum_pair_distance_angstrom": self.minimum_pair_distance_angstrom,
        }


@dataclass(frozen=True)
class ReferenceForceFieldParameters:
    parameter_set_id: str
    parameter_set_version: str
    topology_sha256: str
    atom_parameters: tuple[AtomNonbondedParameter, ...]
    bonds: tuple[HarmonicBondParameter, ...] = ()
    angles: tuple[HarmonicAngleParameter, ...] = ()
    torsions: tuple[PeriodicTorsionParameter, ...] = ()
    excluded_pairs: tuple[tuple[int, int], ...] = ()
    scaled_pairs: tuple[PairScalingParameter, ...] = ()
    cutoff_angstrom: float = 10.0
    switch_start_angstrom: float = 8.0
    dielectric: float = 1.0
    screening_kappa_per_angstrom: float = 0.0
    applicability_domain: ReferenceApplicabilityDomain = field(default_factory=ReferenceApplicabilityDomain)
    scientifically_validated: bool = False
    validation_evidence_sha256: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_id: str = REFERENCE_PARAMETER_SCHEMA_ID

    def __post_init__(self) -> None:
        if str(self.schema_id) != REFERENCE_PARAMETER_SCHEMA_ID:
            raise ReferenceParameterError("unsupported reference parameter schema")
        object.__setattr__(self, "schema_id", REFERENCE_PARAMETER_SCHEMA_ID)
        parameter_set_id = str(self.parameter_set_id or "").strip()
        parameter_set_version = str(self.parameter_set_version or "").strip()
        if not parameter_set_id or not parameter_set_version:
            raise ReferenceParameterError("parameter set ID and version must be non-empty")
        object.__setattr__(self, "parameter_set_id", parameter_set_id)
        object.__setattr__(self, "parameter_set_version", parameter_set_version)
        object.__setattr__(
            self,
            "topology_sha256",
            _digest(self.topology_sha256, name="topology_sha256"),
        )

        atom_parameters = tuple(self.atom_parameters)
        if not all(isinstance(row, AtomNonbondedParameter) for row in atom_parameters):
            raise ReferenceParameterError(
                "atom_parameters must contain AtomNonbondedParameter rows"
            )
        indices = [row.atom_index for row in atom_parameters]
        if len(indices) != len(set(indices)):
            raise ReferenceParameterError("atom nonbonded parameter indices must be unique")

        bonds = tuple(self.bonds)
        if not all(isinstance(row, HarmonicBondParameter) for row in bonds):
            raise ReferenceParameterError("bonds must contain HarmonicBondParameter rows")
        bond_pairs = [(row.atom_i, row.atom_j) for row in bonds]
        if len(bond_pairs) != len(set(bond_pairs)):
            raise ReferenceParameterError("bond parameter definitions must be unique")

        angles = tuple(self.angles)
        if not all(isinstance(row, HarmonicAngleParameter) for row in angles):
            raise ReferenceParameterError("angles must contain HarmonicAngleParameter rows")
        angle_keys = [
            (min(row.atom_i, row.atom_k), row.atom_j, max(row.atom_i, row.atom_k))
            for row in angles
        ]
        if len(angle_keys) != len(set(angle_keys)):
            raise ReferenceParameterError("angle parameter definitions must be unique")

        torsions = tuple(self.torsions)
        if not all(isinstance(row, PeriodicTorsionParameter) for row in torsions):
            raise ReferenceParameterError(
                "torsions must contain PeriodicTorsionParameter rows"
            )
        torsion_keys = []
        for row in torsions:
            forward = (row.atom_i, row.atom_j, row.atom_k, row.atom_l)
            reverse = tuple(reversed(forward))
            torsion_keys.append(
                (
                    min(forward, reverse),
                    row.periodicity,
                    row.phase_radians,
                )
            )
        if len(torsion_keys) != len(set(torsion_keys)):
            raise ReferenceParameterError("torsion parameter definitions must be unique")

        excluded_rows = tuple(_pair(*pair) for pair in self.excluded_pairs)
        if len(excluded_rows) != len(set(excluded_rows)):
            raise ReferenceParameterError("excluded pair definitions must be unique")
        excluded = tuple(sorted(excluded_rows))
        scaled = tuple(self.scaled_pairs)
        if not all(isinstance(row, PairScalingParameter) for row in scaled):
            raise ReferenceParameterError(
                "scaled_pairs must contain PairScalingParameter rows"
            )
        scaled_pairs = [(row.atom_i, row.atom_j) for row in scaled]
        if len(scaled_pairs) != len(set(scaled_pairs)):
            raise ReferenceParameterError("scaled pair definitions must be unique")
        if set(excluded) & set(scaled_pairs):
            raise ReferenceParameterError("a pair cannot be both excluded and scaled")
        cutoff = _finite_positive(self.cutoff_angstrom, name="cutoff_angstrom")
        switch = _finite_positive(self.switch_start_angstrom, name="switch_start_angstrom", allow_zero=True)
        if switch >= cutoff:
            raise ReferenceParameterError("switch_start_angstrom must be less than cutoff_angstrom")
        object.__setattr__(self, "cutoff_angstrom", cutoff)
        object.__setattr__(self, "switch_start_angstrom", switch)
        object.__setattr__(self, "dielectric", _finite_positive(self.dielectric, name="dielectric"))
        object.__setattr__(
            self,
            "screening_kappa_per_angstrom",
            _finite_positive(
                self.screening_kappa_per_angstrom,
                name="screening_kappa_per_angstrom",
                allow_zero=True,
            ),
        )
        object.__setattr__(self, "atom_parameters", atom_parameters)
        object.__setattr__(self, "bonds", bonds)
        object.__setattr__(self, "angles", angles)
        object.__setattr__(self, "torsions", torsions)
        object.__setattr__(self, "excluded_pairs", excluded)
        object.__setattr__(self, "scaled_pairs", scaled)
        if not isinstance(self.applicability_domain, ReferenceApplicabilityDomain):
            raise ReferenceParameterError(
                "applicability_domain must be ReferenceApplicabilityDomain"
            )
        if not isinstance(self.metadata, Mapping):
            raise ReferenceParameterError("metadata must be a mapping")
        metadata = _freeze_json(self.metadata)
        _canonical_sha256(metadata)
        object.__setattr__(self, "metadata", metadata)
        scientifically_validated = _exact_bool(
            self.scientifically_validated,
            name="scientifically_validated",
        )
        evidence = str(self.validation_evidence_sha256 or "").strip()
        if scientifically_validated or evidence:
            raise ReferenceParameterError(
                "scientific validation promotion is unavailable without a verified evidence receipt"
            )
        object.__setattr__(self, "scientifically_validated", False)
        object.__setattr__(self, "validation_evidence_sha256", "")

    @property
    def atom_parameter_map(self) -> dict[int, AtomNonbondedParameter]:
        return {row.atom_index: row for row in self.atom_parameters}

    @property
    def pair_scaling_map(self) -> dict[tuple[int, int], PairScalingParameter]:
        return {(row.atom_i, row.atom_j): row for row in self.scaled_pairs}

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "parameter_set_id": self.parameter_set_id,
            "parameter_set_version": self.parameter_set_version,
            "topology_sha256": self.topology_sha256,
            "atom_parameters": [row.to_dict() for row in self.atom_parameters],
            "bonds": [row.to_dict() for row in self.bonds],
            "angles": [row.to_dict() for row in self.angles],
            "torsions": [row.to_dict() for row in self.torsions],
            "excluded_pairs": [list(pair) for pair in self.excluded_pairs],
            "scaled_pairs": [row.to_dict() for row in self.scaled_pairs],
            "cutoff_angstrom": self.cutoff_angstrom,
            "switch_start_angstrom": self.switch_start_angstrom,
            "dielectric": self.dielectric,
            "screening_kappa_per_angstrom": self.screening_kappa_per_angstrom,
            "applicability_domain": self.applicability_domain.to_dict(),
            "scientifically_validated": bool(self.scientifically_validated),
            "validation_evidence_sha256": self.validation_evidence_sha256,
            "metadata": _thaw_json(self.metadata),
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


__all__ = [
    "COULOMB_KCAL_ANGSTROM_PER_MOL_E2",
    "REFERENCE_PARAMETER_SCHEMA_ID",
    "AtomNonbondedParameter",
    "HarmonicAngleParameter",
    "HarmonicBondParameter",
    "PairScalingParameter",
    "PeriodicTorsionParameter",
    "ReferenceApplicabilityDomain",
    "ReferenceForceFieldParameters",
    "ReferenceParameterError",
]
