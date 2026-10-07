"""New schema composed with unchanged Fourier v1 rows; no legacy π admission."""

from dataclasses import dataclass, fields
import math

from betelgeuze_product.cpu_refinement_fourier_v1.parameters import FourierParameters
from betelgeuze_product.cpu_refinement_v1_2.provenance import (
    ResearchError, finite, integer, exact_fields, canonical, digest,
)

PARAMETER_SCHEMA = "cpu_prepared_linear_harmonic_parameters/1.0.0"


@dataclass(frozen=True)
class LinearHarmonicAngleParameter:
    atom_i: int
    atom_j: int
    atom_k: int
    equilibrium_radians: float
    force_constant_kcal_per_mol_radian2: float

    def __post_init__(self):
        indices = (self.atom_i, self.atom_j, self.atom_k)
        for index in indices:
            integer(index, 0, 255)
        if len(set(indices)) != 3:
            raise ResearchError("linear angle indices must be distinct")
        equilibrium = finite(self.equilibrium_radians)
        constant = finite(self.force_constant_kcal_per_mol_radian2)
        if equilibrium != math.pi or constant <= 0:
            raise ResearchError("linear harmonic angle requires exact pi and positive source constant")
        object.__setattr__(self, "equilibrium_radians", equilibrium)
        object.__setattr__(self, "force_constant_kcal_per_mol_radian2", constant)

    def to_dict(self):
        return {f.name: getattr(self, f.name) for f in fields(self)}


@dataclass(frozen=True)
class LinearAngleParameters:
    base_parameters: FourierParameters
    linear_angles: tuple[LinearHarmonicAngleParameter, ...]
    schema_id: str = PARAMETER_SCHEMA

    def __post_init__(self):
        if (self.schema_id != PARAMETER_SCHEMA
                or type(self.base_parameters) is not FourierParameters
                or type(self.linear_angles) is not tuple
                or not self.linear_angles
                or any(type(row) is not LinearHarmonicAngleParameter for row in self.linear_angles)):
            raise ResearchError("explicit linear harmonic parameter schema and rows required")
        keys = [(min(r.atom_i, r.atom_k), r.atom_j, max(r.atom_i, r.atom_k))
                for r in self.angles]
        if len(keys) != len(set(keys)):
            raise ResearchError("duplicate or overlapping ordinary/linear angle definition")
        if len(keys) > self.applicability_domain.max_angles:
            raise ResearchError("combined angle count exceeds applicability domain")
        if any(max(r.atom_i, r.atom_j, r.atom_k) >= len(self.atom_parameters)
               for r in self.linear_angles):
            raise ResearchError("linear angle index outside atom parameters")
        digest(self.to_dict())

    def __getattr__(self, name):
        # Deliberate composition: all unmodified model/pair/topology fields are
        # inherited for shared complete admission, never a fake interior angle.
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self.base_parameters, name)

    @property
    def angles(self):
        return self.base_parameters.angles + self.linear_angles

    def to_dict(self):
        return {"schema_id": self.schema_id,
                "base_parameters": self.base_parameters.to_dict(),
                "linear_angles": [r.to_dict() for r in self.linear_angles]}

    @property
    def fingerprint_sha256(self):
        return digest(self.to_dict())

    @classmethod
    def from_dict(cls, value):
        exact_fields(value, {"schema_id", "base_parameters", "linear_angles"})
        if type(value["linear_angles"]) is not list:
            raise ResearchError("linear angle document list required")
        rows = []
        for row in value["linear_angles"]:
            exact_fields(row, {f.name for f in fields(LinearHarmonicAngleParameter)})
            rows.append(LinearHarmonicAngleParameter(**row))
        result = cls(FourierParameters.from_dict(value["base_parameters"]),
                     tuple(rows), value["schema_id"])
        if canonical(result.to_dict()) != canonical(value):
            raise ResearchError("noncanonical linear harmonic parameter document")
        return result
