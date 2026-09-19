"""Explicit fixed-receptor LJ/screened-Coulomb objective for CPU research.

Only receptor--ligand pairs are included, once each. Both terms use the same
quintic switch, including its derivative. Deterministic 32x128 blocks bound
scratch memory; every admitted pair is still visited (not an O(N) claim).
No receptor flexibility, covalent docking, reaction field, PME or parameter
inference is provided. Coordinates/energy use angstrom and kcal/mol.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from types import MappingProxyType

import torch

from betelgeuze_engine_v2.contracts import QuantityDescriptor
from betelgeuze_engine_v2.molecular import AllAtomSystem, canonical_system_sha256, canonical_topology_sha256
from betelgeuze_engine_v2.physics.composition import EnergyTermResult
from betelgeuze_engine_v2.physics.reference_parameters import AtomNonbondedParameter, COULOMB_KCAL_ANGSTROM_PER_MOL_E2
from betelgeuze_product.cpu_refinement.reference_forcefield_v1_1 import ReferencePhysicsApplicabilityError
from .evaluation import ExtendedEvaluation, ExtendedEvaluator
from .provenance import ResearchError, canonical, digest, exact_fields, finite, integer, require_digest

CROSS_SCHEMA = "explicit_fixed_receptor_cross_parameters/1.0.0"
FIXED_EVALUATOR_ID = "cpu_corrected_fixed_receptor_reference/1.0.0"
FIXED_REPORT_SCHEMA = "cpu_fixed_receptor_comparison/1.0.0"
FIXED_REQUEST_SCHEMA = "cpu_fixed_receptor_comparison_request/1.0.0"
FIXED_ATTEMPT_SCHEMA = "cpu_fixed_receptor_refinement_attempt/1.0.0"
FIXED_POLICY_ID = "fixed_total_descent_with_explicit_ligand_strain_limit/1.0.0"
COMPONENT_NAMES = ("ligand_internal", "ligand_polar_solvation", "ligand_reference",
                   "cross_lennard_jones", "cross_screened_coulomb", "total")
LIGAND_BLOCK = 32
RECEPTOR_BLOCK = 128


def _bounded(value, low, high, name):
    number = finite(value)
    if not low <= number <= high:
        raise ResearchError(f"{name} must be in [{low},{high}]")
    return number


@dataclass(frozen=True)
class CrossPairScaling:
    """Distinct local index spaces. (ligand, receptor), not an unordered pair."""
    ligand_index: int
    receptor_index: int
    lj_scale: float
    electrostatic_scale: float

    def __post_init__(self):
        integer(self.ligand_index, 0, 255)
        integer(self.receptor_index, 0, 8191)
        for name in ("lj_scale", "electrostatic_scale"):
            object.__setattr__(self, name, _bounded(getattr(self, name), 0., 1., name))

    def to_dict(self):
        return dict(vars(self))


@dataclass(frozen=True)
class CrossParameters:
    """All physical choices explicit; ligand parameters are bound, not duplicated."""
    parameter_set_id: str
    parameter_set_version: str
    parameter_source_sha256: str
    receptor_system_sha256: str
    ligand_topology_sha256: str
    ligand_parameter_fingerprint_sha256: str
    coordinate_frame_id: str
    receptor_atom_parameters: tuple[AtomNonbondedParameter, ...]
    pair_scalings: tuple[CrossPairScaling, ...]
    cutoff_angstrom: float
    switch_start_angstrom: float
    dielectric: float
    screening_kappa_per_angstrom: float
    minimum_pair_distance_angstrom: float

    def __post_init__(self):
        for name in ("parameter_set_id", "parameter_set_version", "coordinate_frame_id"):
            if type(getattr(self, name)) is not str or not getattr(self, name).strip():
                raise ResearchError(f"explicit {name} required")
        for name in ("parameter_source_sha256", "receptor_system_sha256", "ligand_topology_sha256",
                     "ligand_parameter_fingerprint_sha256"):
            require_digest(getattr(self, name))
        atoms = self.receptor_atom_parameters
        if type(atoms) is not tuple or not 1 <= len(atoms) <= 8192:
            raise ResearchError("1..8192 explicit receptor atom parameters required")
        for index, atom in enumerate(atoms):
            if type(atom) is not AtomNonbondedParameter or atom.atom_index != index:
                raise ResearchError("receptor atom parameters must exactly cover ordered atom indices")
            _validate_atom(atom)
        if type(self.pair_scalings) is not tuple or len(self.pair_scalings) > 65536:
            raise ResearchError("bounded immutable cross-pair exceptions required")
        keys = []
        for row in self.pair_scalings:
            if type(row) is not CrossPairScaling or row.receptor_index >= len(atoms):
                raise ResearchError("invalid cross-pair scaling")
            keys.append((row.ligand_index, row.receptor_index))
        if keys != sorted(set(keys)):
            raise ResearchError("cross-pair exceptions must be sorted and unique")
        for name, low, high in (("cutoff_angstrom", .01, 100.), ("switch_start_angstrom", 0., 100.),
                               ("dielectric", 1., 1000.), ("screening_kappa_per_angstrom", 0., 100.),
                               ("minimum_pair_distance_angstrom", 1.e-6, 10.)):
            object.__setattr__(self, name, _bounded(getattr(self, name), low, high, name))
        if not self.minimum_pair_distance_angstrom < self.cutoff_angstrom:
            raise ResearchError("minimum pair distance must be below cutoff")
        if not self.switch_start_angstrom < self.cutoff_angstrom:
            raise ResearchError("switch must start below cutoff")

    def to_dict(self):
        return {**{f.name: getattr(self, f.name) for f in fields(self)
                   if f.name not in {"receptor_atom_parameters", "pair_scalings"}},
                "receptor_atom_parameters": [a.to_dict() for a in self.receptor_atom_parameters],
                "pair_scalings": [p.to_dict() for p in self.pair_scalings],
                "schema_id": CROSS_SCHEMA, "mixing_rule": "lorentz_berthelot_sigma_arithmetic_epsilon_geometric",
                "switch_policy": "quintic_on_both_terms_including_force_derivative",
                "pair_domain": "full_nonperiodic_receptor_ligand_cartesian_product",
                "long_range_correction": False, "scientifically_validated": False}

    @property
    def fingerprint_sha256(self):
        return digest(self.to_dict())

    @classmethod
    def from_dict(cls, document):
        if type(document) is not dict:
            raise ResearchError("complete cross-parameter document required")
        try:
            values = {f.name: document[f.name] for f in fields(cls)}
            values["receptor_atom_parameters"] = tuple(AtomNonbondedParameter(**row)
                                                       for row in document["receptor_atom_parameters"])
            values["pair_scalings"] = tuple(CrossPairScaling(**row) for row in document["pair_scalings"])
            result = cls(**values)
            if canonical(result.to_dict()) != canonical(document):
                raise ResearchError("noncanonical cross-parameter document")
            return result
        except (KeyError, TypeError) as exc:
            raise ResearchError("incomplete cross-parameter document") from exc


def _validate_atom(atom):
    _bounded(atom.sigma_angstrom, 1.e-6, 100., "sigma")
    _bounded(atom.epsilon_kcal_per_mol, 0., 1.e6, "epsilon")
    _bounded(atom.charge_e, -100., 100., "charge")


def _validate_state(system, maximum):
    if (not isinstance(system, AllAtomSystem) or system.model_count != 1
            or not 1 <= system.atom_count <= maximum or system.cell is not None
            or system.coordinate_unit != "angstrom" or system.coordinates.device.type != "cpu"
            or system.coordinates.dtype != torch.float64 or not bool(torch.isfinite(system.coordinates).all())):
        raise ResearchError("bounded nonperiodic single-model CPU binary64 angstrom state required")


@dataclass(frozen=True)
class FixedReceptorEnvironment:
    receptor: AllAtomSystem
    parameters: CrossParameters

    def __post_init__(self):
        if type(self.parameters) is not CrossParameters:
            raise ResearchError("explicit cross parameters required")
        self.assert_integrity()

    def assert_integrity(self):
        _validate_state(self.receptor, 8192)
        try:
            receptor_digest = canonical_system_sha256(self.receptor)
        except (ValueError, RuntimeError) as exc:
            raise ResearchError("fixed receptor system identity changed") from exc
        if receptor_digest != self.parameters.receptor_system_sha256:
            raise ResearchError("fixed receptor system identity changed or cross-wired")
        if self.receptor.atom_count != len(self.parameters.receptor_atom_parameters):
            raise ResearchError("receptor parameter coverage mismatch")
        for atom, param in zip(self.receptor.atoms, self.parameters.receptor_atom_parameters, strict=True):
            if atom.partial_charge_e is None or float(atom.partial_charge_e) != param.charge_e:
                raise ResearchError("receptor charge does not match prepared state")

    def identity(self):
        self.assert_integrity()
        return {"receptor_system_sha256": self.parameters.receptor_system_sha256,
                "cross_parameter_fingerprint_sha256": self.parameters.fingerprint_sha256,
                "coordinate_frame_id": self.parameters.coordinate_frame_id}

    def validate_ligand(self, ligand, ligand_parameters):
        """Admit identities/coverage/charges without evaluating initial cross distances."""
        self.assert_integrity()
        _validate_state(ligand, 256)
        p = self.parameters
        if (canonical_topology_sha256(ligand) != p.ligand_topology_sha256
                or ligand_parameters.fingerprint_sha256 != p.ligand_parameter_fingerprint_sha256):
            raise ResearchError("cross interaction ligand/parameter identity mismatch")
        la = ligand_parameters.atom_parameters
        if len(la) != ligand.atom_count or [a.atom_index for a in la] != list(range(ligand.atom_count)):
            raise ResearchError("ligand parameter coverage mismatch")
        for atom, param in zip(ligand.atoms, la, strict=True):
            _validate_atom(param)
            if atom.partial_charge_e is None or float(atom.partial_charge_e) != param.charge_e:
                raise ResearchError("ligand charge does not match prepared state")
        if any(row.ligand_index >= ligand.atom_count for row in p.pair_scalings):
            raise ResearchError("cross exception ligand index outside source")
        return la

    def evaluate_cross(self, ligand, ligand_parameters):
        """Analytic negative gradient, including switching; fixed bounded scratch."""
        before = self.identity()
        la = self.validate_ligand(ligand, ligand_parameters)
        p = self.parameters
        # Immutable explicit parameters, small vectors; no N_ligand*N_receptor cache.
        lp = torch.tensor([[a.sigma_angstrom, a.epsilon_kcal_per_mol, a.charge_e] for a in la], dtype=torch.float64)
        rp = torch.tensor([[a.sigma_angstrom, a.epsilon_kcal_per_mol, a.charge_e]
                           for a in p.receptor_atom_parameters], dtype=torch.float64)
        xyz = ligand.coordinates[0].detach()
        receptor_xyz = self.receptor.coordinates[0].detach()
        output_force = torch.zeros_like(xyz)
        lj_total = torch.zeros((), dtype=torch.float64)
        electro_total = torch.zeros((), dtype=torch.float64)
        active_count = 0
        # Bucket exceptions by computational block once, not once per pair.
        exceptions = {}
        for row in p.pair_scalings:
            exceptions.setdefault((row.ligand_index // LIGAND_BLOCK, row.receptor_index // RECEPTOR_BLOCK), []).append(row)
        for li in range(0, ligand.atom_count, LIGAND_BLOCK):
            lxyz = xyz[li:li + LIGAND_BLOCK]
            left = lp[li:li + LIGAND_BLOCK]
            for ri in range(0, self.receptor.atom_count, RECEPTOR_BLOCK):
                right = rp[ri:ri + RECEPTOR_BLOCK]
                vector = lxyz[:, None, :] - receptor_xyz[None, ri:ri + RECEPTOR_BLOCK, :]
                radius = torch.linalg.vector_norm(vector, dim=-1)
                if not bool(torch.isfinite(radius).all()):
                    raise FloatingPointError("nonfinite cross-pair distance")
                ls = torch.ones_like(radius)
                es = torch.ones_like(radius)
                for row in exceptions.get((li // LIGAND_BLOCK, ri // RECEPTOR_BLOCK), ()):
                    ls[row.ligand_index - li, row.receptor_index - ri] = row.lj_scale
                    es[row.ligand_index - li, row.receptor_index - ri] = row.electrostatic_scale
                included = (ls != 0.) | (es != 0.)
                if bool(((radius < p.minimum_pair_distance_angstrom) & included).any()):
                    raise ReferencePhysicsApplicabilityError("cross pair below explicit minimum distance")
                active = included & (radius < p.cutoff_angstrom)
                active_count += int(active.sum())
                # Evaluate inactive pairs at finite cutoff; masked zeros never hide 0/0.
                r = torch.where(active, radius, torch.full_like(radius, p.cutoff_angstrom))
                sigma = .5 * (left[:, None, 0] + right[None, :, 0])
                epsilon = torch.sqrt(left[:, None, 1] * right[None, :, 1])
                ratio6 = (sigma / r).pow(6)
                lj = 4. * epsilon * (ratio6.pow(2) - ratio6) * ls
                el = (COULOMB_KCAL_ANGSTROM_PER_MOL_E2 * left[:, None, 2] * right[None, :, 2]
                      * torch.exp(-p.screening_kappa_per_angstrom * r) / (p.dielectric * r)) * es
                derivative = (24. * epsilon * (ratio6 - 2. * ratio6.pow(2)) / r * ls
                              - el * (p.screening_kappa_per_angstrom + 1. / r))
                t = ((r - p.switch_start_angstrom) / (p.cutoff_angstrom - p.switch_start_angstrom)).clamp(0., 1.)
                switch = 1. - 10. * t.pow(3) + 15. * t.pow(4) - 6. * t.pow(5)
                ds = (-30. * t.pow(2) + 60. * t.pow(3) - 30. * t.pow(4)) / (p.cutoff_angstrom - p.switch_start_angstrom)
                pair_force = -(switch * derivative + ds * (lj + el)) / r
                pair_force = torch.where(active, pair_force, torch.zeros_like(pair_force))
                output_force[li:li + len(lxyz)] += (pair_force[..., None] * vector).sum(dim=1)
                lj_total += torch.where(active, switch * lj, torch.zeros_like(lj)).sum()
                electro_total += torch.where(active, switch * el, torch.zeros_like(el)).sum()
        if not bool(torch.isfinite(output_force).all()) or not bool(torch.isfinite(lj_total + electro_total)):
            raise FloatingPointError("nonfinite cross energy or force")
        if self.identity() != before:
            raise ResearchError("fixed environment changed during evaluation")
        return lj_total.reshape(1), electro_total.reshape(1), output_force.unsqueeze(0), active_count


@dataclass(frozen=True)
class FixedReceptorEvaluator:
    base: ExtendedEvaluator
    environment: FixedReceptorEnvironment

    def __post_init__(self):
        if type(self.base) is not ExtendedEvaluator or type(self.environment) is not FixedReceptorEnvironment:
            raise ResearchError("explicit corrected base and fixed receptor environment required")
        p = self.environment.parameters
        if (p.ligand_parameter_fingerprint_sha256 != self.base.parameters.base_parameters.fingerprint_sha256
                or p.ligand_topology_sha256 != self.base.parameters.topology_sha256):
            raise ResearchError("fixed environment is not bound to ligand base parameters")
        self.environment.assert_integrity()

    @property
    def parameters(self):
        return self.base.parameters

    @property
    def solvation(self):
        return self.base.solvation

    def identity(self):
        return {**self.base.identity(), "evaluator_id": FIXED_EVALUATOR_ID, **self.environment.identity()}

    @property
    def fingerprint_sha256(self):
        return digest(self.identity())

    def evaluate(self, system, neighbors):
        identity = self.identity()
        base = self.base.evaluate(system, neighbors)
        lj, electrostatic, cross_forces, _ = self.environment.evaluate_cross(system, self.parameters.base_parameters)
        total = base.term.energy + lj + electrostatic
        internal = torch.zeros_like(base.term.energy)
        polar = torch.zeros_like(base.term.energy)
        for name, value in base.component_energies.items():
            if name.startswith("fixed_born_"):
                polar = polar + value
            else:
                internal = internal + value
        if not bool(torch.isfinite(total).all()) or not bool(torch.isfinite(base.term.forces + cross_forces).all()):
            raise FloatingPointError("nonfinite combined fixed-receptor energy or force")
        term = EnergyTermResult(name=FIXED_EVALUATOR_ID, energy=total, forces=base.term.forces + cross_forces,
            energy_descriptor=QuantityDescriptor(name="fixed_receptor_energy", unit="kcal/mol",
                semantics="ligand_reference_plus_fixed_receptor_lj_and_screened_coulomb", physical_quantity=True,
                calibrated=False, reference_method=None),
            force_descriptor=QuantityDescriptor(name="fixed_receptor_ligand_force", unit="kcal/mol/angstrom",
                semantics="negative_total_energy_gradient_for_movable_ligand_only", physical_quantity=True,
                calibrated=False, reference_method=None), validated_for_composition=False,
            provenance_sha256=digest({"evaluator": identity, "base": base.term.provenance_sha256,
                                      "ligand_state": canonical_system_sha256(system)}))
        return ExtendedEvaluation(term, MappingProxyType(dict(zip(COMPONENT_NAMES,
            (internal, polar, base.term.energy, lj, electrostatic, total), strict=True))), base.constraint_observations,
            self.fingerprint_sha256, (*base.scientific_blockers, "fixed_cross_model_not_scientifically_validated"))


def verify_components(row, total):
    exact_fields(row, set(COMPONENT_NAMES))
    for value in row.values():
        finite(value)
    if row["ligand_internal"] + row["ligand_polar_solvation"] != row["ligand_reference"]:
        raise ResearchError("ligand internal/solvation component mismatch")
    if row["total"] != total or row["ligand_reference"] + row["cross_lennard_jones"] + row["cross_screened_coulomb"] != total:
        raise ResearchError("objective component sum mismatch")
