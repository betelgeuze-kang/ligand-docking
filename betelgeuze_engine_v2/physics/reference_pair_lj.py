"""Explicit pair LJ replacements around the unchanged V1 CPU evaluator.

This supports source-assigned mixed pair values (for example NBFIX or 1-4 LJ).
It does not assign atom types, infer exclusions, or reproduce a CHARMM Hamiltonian.
"""

from dataclasses import dataclass, replace
import hashlib
import json
import math
from numbers import Real
import operator
import re

import torch

from .reference_forcefield import (
    ReferencePhysicsEvaluation,
    _switch,
    evaluate_reference_force_field,
)
from .reference_parameters import ReferenceForceFieldParameters

SCHEMA_ID = "betelgeuze.engine_v2_explicit_pair_lj/1.0.0"
MAX_OVERRIDES = 200_000


def _require(condition, message):
    if not condition:
        raise ValueError(message)


@dataclass(frozen=True)
class PairLJOverride:
    atom_i: int
    atom_j: int
    sigma_angstrom: float
    epsilon_kcal_per_mol: float

    def __post_init__(self):
        indices = []
        for value in (self.atom_i, self.atom_j):
            _require(not isinstance(value, bool), "pair index must be an integer")
            try:
                indices.append(operator.index(value))
            except TypeError:
                raise ValueError("pair index must be an integer") from None
        i, j = sorted(indices)
        _require(0 <= i < j, "pair indices must be nonnegative and distinct")
        object.__setattr__(self, "atom_i", i)
        object.__setattr__(self, "atom_j", j)
        for name in ("sigma_angstrom", "epsilon_kcal_per_mol"):
            value = getattr(self, name)
            _require(isinstance(value, Real) and not isinstance(value, bool), "finite real LJ value required")
            value = float(value)
            _require(math.isfinite(value), "finite LJ value required")
            _require(value > 0 if name == "sigma_angstrom" else value >= 0, "invalid LJ value")
            object.__setattr__(self, name, value)

    @property
    def pair(self):
        return self.atom_i, self.atom_j

    def to_dict(self):
        return {"atom_i": self.atom_i, "atom_j": self.atom_j,
                "sigma_angstrom": self.sigma_angstrom,
                "epsilon_kcal_per_mol": self.epsilon_kcal_per_mol}


@dataclass(frozen=True)
class ReferencePairLJParameters:
    base_parameters: ReferenceForceFieldParameters
    overrides: tuple[PairLJOverride, ...]
    source_sha256: str

    def __post_init__(self):
        _require(isinstance(self.base_parameters, ReferenceForceFieldParameters), "V1 base parameters required")
        rows = tuple(self.overrides)
        _require(len(rows) <= MAX_OVERRIDES, "pair LJ override capacity exceeded")
        _require(all(isinstance(row, PairLJOverride) for row in rows), "typed pair LJ overrides required")
        pairs = [row.pair for row in rows]
        _require(len(pairs) == len(set(pairs)), "duplicate pair LJ override")
        atoms = self.base_parameters.atom_parameter_map
        excluded = set(self.base_parameters.excluded_pairs)
        for pair in pairs:
            _require(all(i in atoms for i in pair), "pair LJ atom missing from base parameters")
            _require(pair not in excluded, "cannot override an excluded pair")
        _require(isinstance(self.source_sha256, str) and
                 re.fullmatch(r"[0-9a-f]{64}", self.source_sha256) is not None,
                 "explicit pair source SHA256 required")
        object.__setattr__(self, "overrides", tuple(sorted(rows, key=lambda row: row.pair)))

    @property
    def fingerprint_sha256(self):
        payload = {"schema_id": SCHEMA_ID,
                   "base_fingerprint_sha256": self.base_parameters.fingerprint_sha256,
                   "source_sha256": self.source_sha256,
                   "overrides": [row.to_dict() for row in self.overrides]}
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                        allow_nan=False).encode()).hexdigest()


def evaluate_reference_force_field_with_pair_lj(system, neighbors, parameters):
    """Replace only the indicated mixed LJ values; retain base scaling and switch.

    Forces are the negative gradient of the same corrected scalar energy.
    All V1 admission, neighbor and topology checks still execute. No periodic
    extension or scientific/customer approval is implied.
    """
    _require(isinstance(parameters, ReferencePairLJParameters), "pair LJ parameters required")
    _require(system.cell is None, "pair LJ extension currently requires nonperiodic coordinates")
    base = parameters.base_parameters
    result = evaluate_reference_force_field(system, neighbors, base)
    coordinates = system.coordinates.detach().clone().requires_grad_(True)
    correction = coordinates.sum(dim=(1, 2)) * 0.0
    rows = parameters.overrides
    if rows:
        first = [row.atom_i for row in rows]
        second = [row.atom_j for row in rows]
        distance = torch.linalg.vector_norm(coordinates[:, first] - coordinates[:, second], dim=-1)
        _require(bool((distance >= base.applicability_domain.minimum_pair_distance_angstrom).all()),
                 "pair LJ distance below minimum")
        atom_map, scale_map = base.atom_parameter_map, base.pair_scaling_map
        def tensor(values):
            return torch.tensor(values, dtype=coordinates.dtype, device=coordinates.device)
        sigma = tensor([row.sigma_angstrom for row in rows])
        epsilon = tensor([row.epsilon_kcal_per_mol for row in rows])
        old_sigma = tensor([(atom_map[i].sigma_angstrom + atom_map[j].sigma_angstrom) / 2
                            for i, j in zip(first, second)])
        old_epsilon = tensor([math.sqrt(atom_map[i].epsilon_kcal_per_mol * atom_map[j].epsilon_kcal_per_mol)
                              for i, j in zip(first, second)])
        scales = tensor([scale_map[row.pair].lj_scale if row.pair in scale_map else 1.0 for row in rows])
        new_ratio6 = (sigma / distance).pow(6)
        old_ratio6 = (old_sigma / distance).pow(6)
        delta = 4 * (epsilon * (new_ratio6.pow(2) - new_ratio6)
                     - old_epsilon * (old_ratio6.pow(2) - old_ratio6))
        correction = (delta * scales * _switch(distance, base.switch_start_angstrom,
                                               base.cutoff_angstrom)).sum(dim=1)
    correction_forces = -torch.autograd.grad(correction.sum(), coordinates)[0]
    components = dict(result.component_energies)
    components["lennard_jones"] = components["lennard_jones"] + correction.detach()
    fingerprint = parameters.fingerprint_sha256
    provenance = hashlib.sha256((result.term.provenance_sha256 + fingerprint).encode()).hexdigest()
    term = replace(result.term, name="reference_force_field_explicit_pair_lj",
                   energy=result.term.energy + correction.detach(),
                   forces=result.term.forces + correction_forces.detach(),
                   provenance_sha256=provenance,
                   energy_descriptor=replace(result.term.energy_descriptor,
                       semantics="base_reference_energy_with_explicit_pair_LJ_replacements"),
                   force_descriptor=replace(result.term.force_descriptor,
                       semantics="negative_coordinate_gradient_of_pair_LJ_corrected_reference_energy"))
    return ReferencePhysicsEvaluation(
        term=term, component_energies=components, applicability_blockers=result.applicability_blockers,
        scientific_blockers=result.scientific_blockers + ("explicit_pair_LJ_source_not_scientifically_validated",),
        parameter_fingerprint_sha256=fingerprint)
