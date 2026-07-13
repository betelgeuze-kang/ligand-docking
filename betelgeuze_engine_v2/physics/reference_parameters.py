"""Explicit, versioned parameter contracts for the CPU reference force field."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from typing import Any, Mapping

REFERENCE_PARAMETER_SCHEMA_ID = "betelgeuze.engine_v2_reference_parameters/1.0.0"
COULOMB_KCAL_ANGSTROM_PER_MOL_E2 = 332.063713299


class ReferenceParameterError(ValueError):
    """Parameter values or applicability bounds are incomplete or inconsistent."""


def _finite_positive(value: float, *, name: str, allow_zero: bool = False) -> float:
    number = float(value)
    if not math.isfinite(number) or (number < 0.0 if allow_zero else number <= 0.0):
        relation = "non-negative" if allow_zero else "positive"
        raise ReferenceParameterError(f"{name} must be finite and {relation}")
    return number


def _canonical_sha256(payload: object) -> str:
    try:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ReferenceParameterError("parameter payload is not canonical JSON") from exc
    return hashlib.sha256(encoded).hexdigest()


def _pair(first: int, second: int) -> tuple[int, int]:
    i, j = sorted((int(first), int(second)))
    if i < 0 or i == j:
        raise ReferenceParameterError("pair indices must be distinct and non-negative")
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
        indices = (int(self.atom_i), int(self.atom_j), int(self.atom_k))
        if len(set(indices)) != 3 or min(indices) < 0:
            raise ReferenceParameterError("angle indices must be distinct and non-negative")
        if not math.isfinite(float(self.equilibrium_radians)) or not 0.0 < float(self.equilibrium_radians) < math.pi:
            raise ReferenceParameterError("equilibrium_radians must be in (0,pi)")
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
        indices = tuple(int(value) for value in (self.atom_i, self.atom_j, self.atom_k, self.atom_l))
        if len(set(indices)) != 4 or min(indices) < 0:
            raise ReferenceParameterError("torsion indices must be distinct and non-negative")
        if int(self.periodicity) < 1 or int(self.periodicity) > 12:
            raise ReferenceParameterError("torsion periodicity must be in [1,12]")
        if not math.isfinite(float(self.phase_radians)):
            raise ReferenceParameterError("torsion phase must be finite")
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
        if int(self.atom_index) < 0:
            raise ReferenceParameterError("atom_index must be non-negative")
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
        if not math.isfinite(float(self.charge_e)):
            raise ReferenceParameterError("charge_e must be finite")

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
            value = float(getattr(self, name))
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ReferenceParameterError(f"{name} must be in [0,1]")

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
            if int(getattr(self, name)) < 0:
                raise ReferenceParameterError(f"{name} must be non-negative")
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
        if self.schema_id != REFERENCE_PARAMETER_SCHEMA_ID:
            raise ReferenceParameterError("unsupported reference parameter schema")
        if not str(self.parameter_set_id or "").strip() or not str(self.parameter_set_version or "").strip():
            raise ReferenceParameterError("parameter set ID and version must be non-empty")
        atom_parameters = tuple(self.atom_parameters)
        indices = [row.atom_index for row in atom_parameters]
        if len(indices) != len(set(indices)):
            raise ReferenceParameterError("atom nonbonded parameter indices must be unique")
        excluded = tuple(sorted({_pair(*pair) for pair in self.excluded_pairs}))
        scaled = tuple(self.scaled_pairs)
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
        object.__setattr__(self, "bonds", tuple(self.bonds))
        object.__setattr__(self, "angles", tuple(self.angles))
        object.__setattr__(self, "torsions", tuple(self.torsions))
        object.__setattr__(self, "excluded_pairs", excluded)
        object.__setattr__(self, "scaled_pairs", scaled)
        metadata = dict(self.metadata)
        _canonical_sha256(metadata)
        object.__setattr__(self, "metadata", metadata)
        evidence = str(self.validation_evidence_sha256 or "").lower()
        if self.scientifically_validated:
            if len(evidence) != 64 or any(char not in "0123456789abcdef" for char in evidence):
                raise ReferenceParameterError(
                    "scientifically validated parameters require validation_evidence_sha256"
                )
        elif evidence:
            raise ReferenceParameterError(
                "validation_evidence_sha256 cannot be supplied while scientifically_validated is false"
            )
        object.__setattr__(self, "validation_evidence_sha256", evidence)

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
            "metadata": dict(self.metadata),
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
