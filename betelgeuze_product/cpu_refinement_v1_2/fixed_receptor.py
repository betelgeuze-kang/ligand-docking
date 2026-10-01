"""Opt-in noncovalent fixed-receptor LJ + screened electrostatic objective.

Angstrom / kcal mol-1 / elementary charge, CPU binary64, nonperiodic. Every
receptor-ligand pair is considered exactly once, in receptor blocks; there are
no intra-receptor terms, hidden exclusions, inferred charges, soft-core clamps,
long-range correction, solvent model or receptor flexibility. The quintic switch
multiplies BOTH pair energies and is differentiated as part of that energy.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, replace
from types import MappingProxyType

import torch

from betelgeuze_engine_v2.molecular import AllAtomSystem, canonical_system_sha256, canonical_topology_sha256
from betelgeuze_engine_v2.stack_round3_molecular import MolecularIntegrityError
from betelgeuze_engine_v2.physics.reference_parameters import AtomNonbondedParameter, ReferenceForceFieldParameters, COULOMB_KCAL_ANGSTROM_PER_MOL_E2
from betelgeuze_product.cpu_refinement.reference_forcefield_v1_1 import ReferencePhysicsApplicabilityError
from .evaluation import ExtendedEvaluation, ExtendedEvaluator
from .provenance import ResearchError, canonical, digest, exact_fields, finite, integer, require_digest

FIXED_EVALUATOR_ID = "cpu_fixed_receptor_reference/1.0.0"
FIXED_REPORT_SCHEMA = "cpu_fixed_receptor_comparison/1.0.0"
FIXED_REQUEST_SCHEMA = "cpu_fixed_receptor_request/1.0.0"
FIXED_POLICY_ID = "fixed_receptor_total_decrease_with_ligand_strain_limit/1.0.0"
FIXED_ATTEMPT_SCHEMA = "cpu_fixed_receptor_attempt/1.0.0"
ENERGY_BASIS = "ligand_internal_plus_cross_lj_plus_cross_screened_coulomb"
COMPONENTS = ("ligand_internal", "cross_lennard_jones", "cross_screened_coulomb")


def require_system(system: AllAtomSystem, maximum: int) -> None:
    if (not isinstance(system, AllAtomSystem) or system.model_count != 1
            or not 1 <= system.atom_count <= maximum or system.cell is not None
            or [a.index for a in system.atoms] != list(range(system.atom_count))
            or system.coordinate_unit != "angstrom" or system.coordinates.device.type != "cpu"
            or system.coordinates.dtype != torch.float64
            or tuple(system.coordinates.shape) != (1, system.atom_count, 3)
            or not bool(torch.isfinite(system.coordinates).all())):
        raise ResearchError("bounded nonperiodic single-model CPU float64 angstrom system required")


@dataclass(frozen=True)
class CrossParameters:
    """Explicit environment identity and complete receptor nonbonded parameters."""
    parameter_set_id: str
    parameter_source_sha256: str
    receptor_system_sha256: str
    ligand_topology_sha256: str
    ligand_base_parameters_sha256: str
    coordinate_frame_id: str
    receptor_atoms: tuple[AtomNonbondedParameter, ...]
    cutoff_angstrom: float
    switch_start_angstrom: float
    minimum_distance_angstrom: float
    dielectric: float
    screening_kappa_per_angstrom: float
    receptor_block_size: int
    max_internal_increase_kcal_per_mol: float
    pair_policy: str = "all_non_covalent_cross_pairs_no_exclusions"
    mixing_rule: str = "lorentz_berthelot"
    schema_id: str = "fixed_receptor_cross_parameters/1.0.0"

    def __post_init__(self) -> None:
        for name in ("parameter_set_id", "coordinate_frame_id"):
            value = getattr(self, name)
            if type(value) is not str or not value.strip() or value != value.strip():
                raise ResearchError(f"explicit canonical {name} required")
        for name in ("parameter_source_sha256", "receptor_system_sha256", "ligand_topology_sha256", "ligand_base_parameters_sha256"):
            require_digest(getattr(self, name))
        if (self.pair_policy != "all_non_covalent_cross_pairs_no_exclusions"
                or self.mixing_rule != "lorentz_berthelot"
                or self.schema_id != "fixed_receptor_cross_parameters/1.0.0"):
            raise ResearchError("unsupported cross interaction model or pair policy")
        if type(self.receptor_atoms) is not tuple or not 1 <= len(self.receptor_atoms) <= 8192:
            raise ResearchError("complete ordered tuple of 1..8192 receptor atoms required")
        for index, atom in enumerate(self.receptor_atoms):
            if type(atom) is not AtomNonbondedParameter or atom.atom_index != index:
                raise ResearchError("receptor parameter coverage/order mismatch")
            # Bound unphysical input magnitudes rather than allowing overflow.
            if not (0 < atom.sigma_angstrom <= 100 and 0 <= atom.epsilon_kcal_per_mol <= 1.e6
                    and abs(atom.charge_e) <= 100):
                raise ResearchError("receptor nonbonded parameter outside supported bounds")
        for name in ("cutoff_angstrom", "switch_start_angstrom", "minimum_distance_angstrom", "dielectric",
                     "screening_kappa_per_angstrom", "max_internal_increase_kcal_per_mol"):
            object.__setattr__(self, name, finite(getattr(self, name), nonnegative=True))
        if not (0 < self.minimum_distance_angstrom < self.switch_start_angstrom < self.cutoff_angstrom <= 1000):
            raise ResearchError("require 0 < minimum distance < switch start < cutoff <= 1000 A")
        if not (0 < self.dielectric <= 1.e6 and self.screening_kappa_per_angstrom <= 100
                and self.max_internal_increase_kcal_per_mol <= 1.e6):
            raise ResearchError("interaction or strain parameter outside supported bounds")
        integer(self.receptor_block_size, 1, 512)

    def to_dict(self) -> dict:
        return {**{f.name: getattr(self, f.name) for f in fields(self) if f.name != "receptor_atoms"},
                "receptor_atoms": [atom.to_dict() for atom in self.receptor_atoms]}

    @classmethod
    def from_dict(cls, value: object) -> "CrossParameters":
        exact_fields(value, {f.name for f in fields(cls)})
        rows = value["receptor_atoms"]
        if type(rows) is not list or not 1 <= len(rows) <= 8192:
            raise ResearchError("bounded receptor parameter list required")
        atoms = []
        for index, row in enumerate(rows):
            exact_fields(row, {f.name for f in fields(AtomNonbondedParameter)})
            if integer(row["atom_index"], 0, 8191) != index:
                raise ResearchError("receptor atom index mismatch")
            atoms.append(AtomNonbondedParameter(**row))
        result = cls(**{**value, "receptor_atoms": tuple(atoms)})
        if canonical(result.to_dict()) != canonical(value):
            raise ResearchError("noncanonical cross parameter document")
        return result

    @property
    def fingerprint_sha256(self) -> str:
        return digest(self.to_dict())


@dataclass(frozen=True)
class FixedReceptorEnvironment:
    receptor: AllAtomSystem
    cross: CrossParameters

    def __post_init__(self) -> None:
        if type(self.cross) is not CrossParameters:
            raise ResearchError("explicit cross parameter object required")
        self.assert_intact()

    def assert_intact(self) -> None:
        require_system(self.receptor, 8192)
        try:
            receptor_hash = canonical_system_sha256(self.receptor)
        except MolecularIntegrityError as exc:
            raise ResearchError("fixed receptor state changed after admission") from exc
        if (receptor_hash != self.cross.receptor_system_sha256
                or len(self.cross.receptor_atoms) != self.receptor.atom_count):
            raise ResearchError("fixed receptor coordinates/identity/parameter coverage changed")
        for atom, param in zip(self.receptor.atoms, self.cross.receptor_atoms, strict=True):
            if atom.partial_charge_e is None or float(atom.partial_charge_e).hex() != param.charge_e.hex():
                raise ResearchError("receptor declared charges disagree with explicit parameters")

    def validate_ligand(self, ligand: AllAtomSystem, base_parameters) -> tuple:
        """Reject globally incompatible ligand inputs without evaluating physics."""
        self.assert_intact()
        require_system(ligand, 256)
        if type(base_parameters) is not ReferenceForceFieldParameters:
            raise ResearchError("explicit ligand reference parameters required")
        if (canonical_topology_sha256(ligand) != self.cross.ligand_topology_sha256
                or base_parameters.fingerprint_sha256 != self.cross.ligand_base_parameters_sha256
                or len(base_parameters.atom_parameters) != ligand.atom_count):
            raise ResearchError("ligand topology/base parameters do not match cross model")
        params = sorted(base_parameters.atom_parameters, key=lambda a: a.atom_index)
        if [a.atom_index for a in params] != list(range(ligand.atom_count)):
            raise ResearchError("ligand nonbonded coverage is incomplete")
        for atom, param in zip(ligand.atoms, params, strict=True):
            if not (0 < param.sigma_angstrom <= 100 and 0 <= param.epsilon_kcal_per_mol <= 1.e6
                    and abs(param.charge_e) <= 100):
                raise ResearchError("ligand nonbonded parameter outside supported bounds")
            if atom.partial_charge_e is None or float(atom.partial_charge_e).hex() != param.charge_e.hex():
                raise ResearchError("ligand declared charges disagree with cross parameters")
        return tuple(params)

    def evaluate_cross(self, ligand: AllAtomSystem, base_parameters) -> tuple[dict, torch.Tensor, int]:
        """Bounded peak pair memory; O(N_ligand*N_receptor) work, not an O(N) claim."""
        params = self.validate_ligand(ligand, base_parameters)
        xyz = ligand.coordinates[0].detach().clone().requires_grad_(True)
        receptor_xyz = self.receptor.coordinates[0].detach().clone()
        lj_sum = torch.zeros((), dtype=torch.float64)
        q_sum = torch.zeros((), dtype=torch.float64)
        force = torch.zeros_like(xyz)
        lp = torch.tensor([[a.sigma_angstrom, a.epsilon_kcal_per_mol, a.charge_e] for a in params], dtype=torch.float64)
        count = 0
        # Block size is part of the checkpoint identity; different sums need not be bit-identical.
        for start in range(0, self.receptor.atom_count, self.cross.receptor_block_size):
            end = min(start + self.cross.receptor_block_size, self.receptor.atom_count)
            distances = torch.linalg.vector_norm(xyz[:, None, :] - receptor_xyz[None, start:end, :], dim=-1)
            if not bool(torch.isfinite(distances).all()):
                raise ReferencePhysicsApplicabilityError("nonfinite receptor-ligand distance")
            if bool((distances < self.cross.minimum_distance_angstrom).any()):
                raise ReferencePhysicsApplicabilityError("cross pair below explicit minimum distance")
            active = distances < self.cross.cutoff_angstrom
            left, right = torch.nonzero(active, as_tuple=True)
            count += int(left.numel())
            if not left.numel():
                continue
            r = distances[left, right]
            rp = torch.tensor([[a.sigma_angstrom, a.epsilon_kcal_per_mol, a.charge_e]
                               for a in self.cross.receptor_atoms[start:end]], dtype=torch.float64)
            sigma = .5 * (lp[left, 0] + rp[right, 0])
            epsilon = torch.sqrt(lp[left, 1] * rp[right, 1])
            ratio6 = (sigma / r).pow(6)
            pair_lj = 4 * epsilon * (ratio6.pow(2) - ratio6)
            pair_q = (COULOMB_KCAL_ANGSTROM_PER_MOL_E2 * lp[left, 2] * rp[right, 2]
                      * torch.exp(-self.cross.screening_kappa_per_angstrom * r) / (self.cross.dielectric * r))
            t = ((r - self.cross.switch_start_angstrom) /
                 (self.cross.cutoff_angstrom - self.cross.switch_start_angstrom)).clamp(0., 1.)
            switch = 1 - 10*t.pow(3) + 15*t.pow(4) - 6*t.pow(5)
            lj, electro = (pair_lj * switch).sum(), (pair_q * switch).sum()
            gradient = torch.autograd.grad(lj + electro, xyz)[0]
            if not (bool(torch.isfinite(lj)) and bool(torch.isfinite(electro)) and bool(torch.isfinite(gradient).all())):
                raise FloatingPointError("nonfinite fixed receptor energy or gradient")
            force -= gradient.detach()
            lj_sum += lj.detach()
            q_sum += electro.detach()
        self.assert_intact()
        return {"cross_lennard_jones": lj_sum.reshape(1), "cross_screened_coulomb": q_sum.reshape(1)}, force.unsqueeze(0), count


@dataclass(frozen=True)
class FixedReceptorEvaluator:
    internal: ExtendedEvaluator
    fixed: FixedReceptorEnvironment

    def __post_init__(self) -> None:
        if type(self.internal) is not ExtendedEvaluator or type(self.fixed) is not FixedReceptorEnvironment:
            raise ResearchError("explicit fixed-receptor evaluator composition required")
        if self.internal.solvation is not None:
            raise ResearchError("first fixed-receptor model does not compose a ligand-only GB solvent model")
        if self.internal.parameters.base_parameters.fingerprint_sha256 != self.fixed.cross.ligand_base_parameters_sha256:
            raise ResearchError("internal/cross ligand parameter mismatch")
        self.fixed.assert_intact()

    @property
    def parameters(self):
        return self.internal.parameters

    @property
    def solvation(self):
        return self.internal.solvation

    def identity(self) -> dict:
        self.fixed.assert_intact()
        return {**self.internal.identity(), "evaluator_id": FIXED_EVALUATOR_ID,
                "receptor_system_sha256": self.fixed.cross.receptor_system_sha256,
                "cross_parameters_sha256": self.fixed.cross.fingerprint_sha256}

    @property
    def fingerprint_sha256(self) -> str:
        return digest(self.identity())

    def evaluate(self, system, neighbors) -> ExtendedEvaluation:
        base = self.internal.evaluate(system, neighbors)
        components, forces, _ = self.fixed.evaluate_cross(system, self.internal.parameters.base_parameters)
        components = {"ligand_internal": base.term.energy, **components}
        energy = sum(components.values(), torch.zeros_like(base.term.energy))
        force = base.term.forces + forces
        if not bool(torch.isfinite(energy).all()) or not bool(torch.isfinite(force).all()):
            raise FloatingPointError("nonfinite total fixed-receptor objective")
        term = replace(base.term, name=FIXED_EVALUATOR_ID, energy=energy, forces=force,
                       energy_descriptor=replace(base.term.energy_descriptor, name="fixed_receptor_energy", semantics=ENERGY_BASIS),
                       force_descriptor=replace(base.term.force_descriptor, name="fixed_receptor_ligand_force",
                                                semantics="negative_ligand_coordinate_gradient_of_fixed_receptor_total"),
                       provenance_sha256=digest({"evaluator": self.identity(), "internal": base.term.provenance_sha256,
                                                 "ligand": canonical_system_sha256(system)}))
        return ExtendedEvaluation(term, MappingProxyType(components), base.constraint_observations,
                                  self.fingerprint_sha256, (*base.scientific_blockers, "fixed_receptor_model_not_scientifically_validated"))


def components_document(evaluation: ExtendedEvaluation) -> dict:
    return {**{name: float(evaluation.component_energies[name][0]) for name in COMPONENTS},
            "total": float(evaluation.term.energy[0])}


def validate_components(value: dict, total: float) -> None:
    exact_fields(value, {*COMPONENTS, "total"})
    values = [finite(value[name]) for name in COMPONENTS]
    finite(value["total"])
    if (float(value["total"]).hex() != float(total).hex()
            or abs(sum(values) - float(total)) > 1.e-10 * max(1., abs(float(total)))):
        raise ResearchError("fixed-receptor component energy accounting mismatch")
