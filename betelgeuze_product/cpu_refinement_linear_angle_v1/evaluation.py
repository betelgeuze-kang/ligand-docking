"""Complete combined admission and opt-in source-preserving linear angle energy."""

from dataclasses import dataclass, replace
from types import MappingProxyType
import torch

from betelgeuze_engine_v2.molecular import canonical_system_sha256, canonical_topology_sha256
from betelgeuze_engine_v2.physics.reference_forcefield import (
    _vector, ReferencePhysicsApplicabilityError,
)
from betelgeuze_product.cpu_refinement_fourier_v1.evaluation import (
    _require_fourier_topology, _evaluate_validated_fourier_terms, FourierEnvironment,
)
from betelgeuze_product.cpu_refinement_v1_2.evaluation import ExtendedEvaluation
from betelgeuze_product.cpu_refinement_v1_2.fixed_receptor import require_system
from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError, digest
from .parameters import LinearAngleParameters
from .geometry import harmonic_linear_angle_energy

INTERNAL_ID = "cpu_prepared_linear_harmonic_internal/1.0.0"
FIXED_ID = "cpu_prepared_linear_harmonic_fixed/1.0.0"
ENERGY_BASIS = "source_harmonic_angles_including_pi_plus_signed_fourier_and_nonbonded_plus_fixed_cross"


@dataclass(frozen=True)
class LinearAngleInternalEvaluator:
    parameters: LinearAngleParameters

    def __post_init__(self):
        if type(self.parameters) is not LinearAngleParameters:
            raise ResearchError("explicit linear harmonic model required")

    def identity(self):
        return {"evaluator_id": INTERNAL_ID,
                "parameter_fingerprint_sha256": self.parameters.fingerprint_sha256}

    @property
    def fingerprint_sha256(self):
        return digest(self.identity())

    def evaluate(self, system, neighbors):
        # Admission MUST see all source angles before the arithmetic-only base
        # evaluates the remaining terms. Neither partial model is public input.
        _require_fourier_topology(system, neighbors, self.parameters)
        base = _evaluate_validated_fourier_terms(
            system, neighbors, self.parameters.base_parameters, self.identity()
        )
        xyz = system.coordinates.detach().clone().requires_grad_(True)
        linear = xyz.sum(dim=(1, 2)) * 0.0
        for row in self.parameters.linear_angles:
            linear = linear + harmonic_linear_angle_energy(
                _vector(xyz, system, row.atom_i, row.atom_j),
                _vector(xyz, system, row.atom_k, row.atom_j),
                row.force_constant_kcal_per_mol_radian2,
            )
        force = -torch.autograd.grad(linear.sum(), xyz)[0]
        energy = base.term.energy + linear.detach()
        forces = base.term.forces + force.detach()
        if not bool(torch.isfinite(energy).all()) or not bool(torch.isfinite(forces).all()):
            raise ReferencePhysicsApplicabilityError("nonfinite linear harmonic result")
        term = replace(
            base.term, name=INTERNAL_ID, energy=energy, forces=forces,
            energy_descriptor=replace(base.term.energy_descriptor,
                                     name="prepared_linear_harmonic_internal_energy",
                                     semantics="source_harmonic_angle_with_removable_pi_endpoint"),
            provenance_sha256=digest({"evaluator": self.identity(),
                                      "system": canonical_system_sha256(system)}),
        )
        components = {**base.component_energies}
        components["harmonic_angle"] = components["harmonic_angle"] + linear.detach()
        return ExtendedEvaluation(term, MappingProxyType(components), (), self.fingerprint_sha256,
                                  (*base.scientific_blockers,
                                   "linear_harmonic_model_not_scientifically_validated"))


@dataclass(frozen=True)
class LinearAngleEnvironment(FourierEnvironment):
    """Same declared cross physics, explicitly bound to the full new model hash."""

    def validate_ligand(self, ligand, parameters):
        self.assert_intact()
        require_system(ligand, 256)
        if (type(parameters) is not LinearAngleParameters
                or canonical_topology_sha256(ligand) != self.cross.ligand_topology_sha256
                or parameters.fingerprint_sha256 != self.cross.ligand_base_parameters_sha256
                or len(parameters.atom_parameters) != ligand.atom_count):
            raise ResearchError("linear harmonic ligand identity/coverage mismatch")
        for atom, row in zip(ligand.atoms, parameters.atom_parameters, strict=True):
            if (atom.partial_charge_e is None
                    or float(atom.partial_charge_e).hex() != row.charge_e.hex()):
                raise ResearchError("linear harmonic ligand charge mismatch")
        return parameters.atom_parameters


@dataclass(frozen=True)
class LinearAngleFixedEvaluator:
    parameters: LinearAngleParameters
    fixed: LinearAngleEnvironment

    def __post_init__(self):
        if (type(self.parameters) is not LinearAngleParameters
                or type(self.fixed) is not LinearAngleEnvironment):
            raise ResearchError("explicit linear harmonic fixed evaluator required")

    def identity(self):
        return {"evaluator_id": FIXED_ID,
                "parameter_fingerprint_sha256": self.parameters.fingerprint_sha256,
                "cross_parameters_sha256": self.fixed.cross.fingerprint_sha256}

    @property
    def fingerprint_sha256(self):
        return digest(self.identity())

    def evaluate(self, system, neighbors):
        self.fixed.validate_ligand(system, self.parameters)
        base = LinearAngleInternalEvaluator(self.parameters).evaluate(system, neighbors)
        cross, force, _ = self.fixed.evaluate_cross(system, self.parameters)
        components = {"ligand_internal": base.term.energy, **cross}
        term = replace(base.term, name=FIXED_ID,
                       energy=sum(components.values(), torch.zeros_like(base.term.energy)),
                       forces=base.term.forces + force,
                       energy_descriptor=replace(base.term.energy_descriptor,
                                                 name="prepared_linear_harmonic_fixed_energy",
                                                 semantics=ENERGY_BASIS),
                       provenance_sha256=digest({"evaluator": self.identity(),
                                                 "system": canonical_system_sha256(system)}))
        return ExtendedEvaluation(term, MappingProxyType(components), (),
                                  self.fingerprint_sha256, base.scientific_blockers)
