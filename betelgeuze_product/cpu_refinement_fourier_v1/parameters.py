"""Explicit opt-in signed Fourier model; legacy parameter types remain unchanged."""

from dataclasses import dataclass, field, fields
from typing import Mapping
from betelgeuze_engine_v2.physics.reference_parameters import (
    HarmonicBondParameter,
    HarmonicAngleParameter,
    PairScalingParameter,
    ReferenceApplicabilityDomain,
    _freeze_json,
    _thaw_json,
)
from betelgeuze_product.cpu_refinement_v1_2.provenance import (
    ResearchError,
    finite,
    integer,
    digest,
    require_digest,
    exact_fields,
)

PARAMETER_SCHEMA = "cpu_prepared_fourier_parameters/1.0.0"
CROSS_SCHEMA = "cpu_prepared_fourier_cross/1.0.0"


@dataclass(frozen=True)
class NonbondedParameter:
    atom_index: int
    sigma_angstrom: float
    epsilon_kcal_per_mol: float
    charge_e: float

    def __post_init__(self):
        integer(self.atom_index, 0, 8191)
        for name in ("sigma_angstrom", "epsilon_kcal_per_mol", "charge_e"):
            object.__setattr__(self, name, finite(getattr(self, name)))
        if not (
            0 <= self.sigma_angstrom <= 100
            and 0 <= self.epsilon_kcal_per_mol <= 1e6
            and abs(self.charge_e) <= 100
        ):
            raise ResearchError("Fourier nonbonded parameter outside bounds")
        if self.sigma_angstrom == 0 and self.epsilon_kcal_per_mol != 0:
            raise ResearchError("zero sigma requires original zero epsilon")

    def to_dict(self):
        return {f.name: getattr(self, f.name) for f in fields(self)}


@dataclass(frozen=True)
class SignedPeriodicTorsionParameter:
    atom_i: int
    atom_j: int
    atom_k: int
    atom_l: int
    periodicity: int
    phase_radians: float
    amplitude_kcal_per_mol: float

    def __post_init__(self):
        indices = (self.atom_i, self.atom_j, self.atom_k, self.atom_l)
        for i in indices:
            integer(i, 0, 255)
        if len(set(indices)) != 4:
            raise ResearchError("Fourier atom indices must be distinct")
        integer(self.periodicity, 1, 12)
        for name in ("phase_radians", "amplitude_kcal_per_mol"):
            object.__setattr__(self, name, finite(getattr(self, name)))
        if abs(self.phase_radians) > 1e6 or abs(self.amplitude_kcal_per_mol) > 1e6:
            raise ResearchError("Fourier coefficient outside bounds")

    def to_dict(self):
        return {f.name: getattr(self, f.name) for f in fields(self)}


@dataclass(frozen=True)
class OrderedPeriodicImproperParameter(SignedPeriodicTorsionParameter):
    star_center: int = 0

    def __post_init__(self):
        super().__post_init__()
        integer(self.star_center, 0, 255)
        if self.star_center not in (self.atom_i, self.atom_j, self.atom_k, self.atom_l):
            raise ResearchError("periodic improper center must be one ordered atom")


@dataclass(frozen=True)
class ListedPairParameter:
    atom_i: int
    atom_j: int
    sigma_angstrom: float
    epsilon_kcal_per_mol: float
    electrostatic_scale: float

    def __post_init__(self):
        integer(self.atom_i, 0, 255)
        integer(self.atom_j, 0, 255)
        if self.atom_i >= self.atom_j:
            raise ResearchError("canonical listed pair required")
        for name in ("sigma_angstrom", "epsilon_kcal_per_mol", "electrostatic_scale"):
            object.__setattr__(
                self, name, finite(getattr(self, name), nonnegative=True)
            )
        if (
            self.sigma_angstrom > 100
            or self.epsilon_kcal_per_mol > 1e6
            or self.electrostatic_scale > 1
        ):
            raise ResearchError("listed pair outside bounds")
        if self.sigma_angstrom == 0 and self.epsilon_kcal_per_mol != 0:
            raise ResearchError("zero listed sigma requires zero epsilon")

    def to_dict(self):
        return {f.name: getattr(self, f.name) for f in fields(self)}


@dataclass(frozen=True)
class FourierParameters:
    parameter_set_id: str
    parameter_set_version: str
    topology_sha256: str
    atom_parameters: tuple[NonbondedParameter, ...]
    bonds: tuple[HarmonicBondParameter, ...] = ()
    angles: tuple[HarmonicAngleParameter, ...] = ()
    torsions: tuple[SignedPeriodicTorsionParameter, ...] = ()
    periodic_impropers: tuple[OrderedPeriodicImproperParameter, ...] = ()
    excluded_pairs: tuple[tuple[int, int], ...] = ()
    scaled_pairs: tuple[PairScalingParameter, ...] = ()
    listed_pairs: tuple[ListedPairParameter, ...] = ()
    cutoff_angstrom: float = 10.0
    switch_start_angstrom: float = 8.0
    dielectric: float = 1.0
    screening_kappa_per_angstrom: float = 0.0
    applicability_domain: ReferenceApplicabilityDomain = field(
        default_factory=ReferenceApplicabilityDomain
    )
    metadata: Mapping = field(default_factory=dict)
    schema_id: str = PARAMETER_SCHEMA

    def __post_init__(self):
        if self.schema_id != PARAMETER_SCHEMA:
            raise ResearchError("explicit Fourier parameter schema required")
        for name in ("parameter_set_id", "parameter_set_version"):
            value = getattr(self, name)
            if type(value) is not str or not value.strip() or len(value) > 512:
                raise ResearchError("bounded parameter identity required")
        require_digest(self.topology_sha256)
        kinds = {
            "atom_parameters": NonbondedParameter,
            "bonds": HarmonicBondParameter,
            "angles": HarmonicAngleParameter,
            "torsions": SignedPeriodicTorsionParameter,
            "periodic_impropers": OrderedPeriodicImproperParameter,
            "scaled_pairs": PairScalingParameter,
            "listed_pairs": ListedPairParameter,
        }
        for name, kind in kinds.items():
            value = getattr(self, name)
            if type(value) is not tuple or any(type(row) is not kind for row in value):
                raise ResearchError("exact Fourier parameter row type/tuple required")
        if (
            not 1 <= len(self.atom_parameters) <= 256
            or len(self.periodic_impropers) > 4096
        ):
            raise ResearchError("Fourier parameter capacity exceeded")
        if [r.atom_index for r in self.atom_parameters] != list(
            range(len(self.atom_parameters))
        ):
            raise ResearchError("complete ordered atom parameter coverage required")
        keys = [tuple(sorted((r.atom_i, r.atom_j))) for r in self.bonds]
        angle_keys = [
            (min(r.atom_i, r.atom_k), r.atom_j, max(r.atom_i, r.atom_k))
            for r in self.angles
        ]
        proper_keys = [
            (
                min(
                    (r.atom_i, r.atom_j, r.atom_k, r.atom_l),
                    (r.atom_l, r.atom_k, r.atom_j, r.atom_i),
                ),
                r.periodicity,
                r.phase_radians,
            )
            for r in self.torsions
        ]
        improper_keys = [
            (
                r.atom_i,
                r.atom_j,
                r.atom_k,
                r.atom_l,
                r.star_center,
                r.periodicity,
                r.phase_radians,
            )
            for r in self.periodic_impropers
        ]
        for values in (keys, angle_keys, proper_keys, improper_keys):
            if len(values) != len(set(values)):
                raise ResearchError("duplicate Fourier term definition")
        if type(self.excluded_pairs) is not tuple:
            raise ResearchError("explicit excluded pair tuple required")
        exclusions = []
        for pair in self.excluded_pairs:
            if type(pair) is not tuple or len(pair) != 2:
                raise ResearchError("invalid excluded pair")
            i, j = pair
            integer(i, 0, 255)
            integer(j, 0, 255)
            if i >= j:
                raise ResearchError("canonical excluded pair required")
            exclusions.append(pair)
        scale_keys = [(r.atom_i, r.atom_j) for r in self.scaled_pairs]
        if (
            len(exclusions) != len(set(exclusions))
            or len(scale_keys) != len(set(scale_keys))
            or set(exclusions) & set(scale_keys)
        ):
            raise ResearchError("duplicate or overlapping pair policy")
        listed_keys = [(r.atom_i, r.atom_j) for r in self.listed_pairs]
        if (
            len(listed_keys) != len(set(listed_keys))
            or not set(listed_keys) <= set(exclusions)
            or set(listed_keys) & set(scale_keys)
        ):
            raise ResearchError(
                "listed pairs must uniquely replace excluded ordinary pairs"
            )
        if len(listed_keys) > 32640:
            raise ResearchError("listed pair capacity exceeded")
        for name in (
            "cutoff_angstrom",
            "switch_start_angstrom",
            "dielectric",
            "screening_kappa_per_angstrom",
        ):
            object.__setattr__(
                self, name, finite(getattr(self, name), nonnegative=True)
            )
        if (
            not 0 <= self.switch_start_angstrom < self.cutoff_angstrom <= 1000
            or not 0 < self.dielectric <= 1e6
            or self.screening_kappa_per_angstrom > 100
        ):
            raise ResearchError("unsupported Fourier nonbonded convention")
        if type(self.applicability_domain) is not ReferenceApplicabilityDomain:
            raise ResearchError("explicit applicability domain required")
        if not isinstance(self.metadata, Mapping):
            raise ResearchError("metadata mapping required")
        object.__setattr__(self, "metadata", _freeze_json(self.metadata))
        digest(self.to_dict())

    @property
    def atom_parameter_map(self):
        return {r.atom_index: r for r in self.atom_parameters}

    @property
    def pair_scaling_map(self):
        return {(r.atom_i, r.atom_j): r for r in self.scaled_pairs}

    @property
    def base_parameters(self):
        return self

    @property
    def constraints(self):
        return ()

    @property
    def scientifically_validated(self):
        return False

    def to_dict(self):
        result = {f.name: getattr(self, f.name) for f in fields(self)}
        for name in (
            "atom_parameters",
            "bonds",
            "angles",
            "torsions",
            "periodic_impropers",
            "scaled_pairs",
            "listed_pairs",
        ):
            result[name] = [r.to_dict() for r in result[name]]
        result["excluded_pairs"] = [list(p) for p in self.excluded_pairs]
        result["applicability_domain"] = self.applicability_domain.to_dict()
        result["metadata"] = _thaw_json(self.metadata)
        return result

    @property
    def fingerprint_sha256(self):
        return digest(self.to_dict())

    @classmethod
    def from_dict(cls, value):
        exact_fields(value, {f.name for f in fields(cls)})
        data = dict(value)
        for name, kind in (
            ("atom_parameters", NonbondedParameter),
            ("bonds", HarmonicBondParameter),
            ("angles", HarmonicAngleParameter),
            ("torsions", SignedPeriodicTorsionParameter),
            ("periodic_impropers", OrderedPeriodicImproperParameter),
            ("scaled_pairs", PairScalingParameter),
            ("listed_pairs", ListedPairParameter),
        ):
            data[name] = tuple(kind(**row) for row in data[name])
        data["excluded_pairs"] = tuple(tuple(p) for p in data["excluded_pairs"])
        data["applicability_domain"] = ReferenceApplicabilityDomain(
            **data["applicability_domain"]
        )
        result = cls(**data)
        if result.to_dict() != value:
            raise ResearchError("noncanonical Fourier parameter document")
        return result
