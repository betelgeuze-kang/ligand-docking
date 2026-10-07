"""Versioned explicit Fourier evaluation, preserving original signed coefficients."""

from dataclasses import dataclass, fields, replace
from types import MappingProxyType
import torch
from betelgeuze_engine_v2.contracts import QuantityDescriptor
from betelgeuze_engine_v2.molecular import (
    canonical_system_sha256,
    canonical_topology_sha256,
)
from betelgeuze_engine_v2.physics.reference_parameters import (
    COULOMB_KCAL_ANGSTROM_PER_MOL_E2,
)
from betelgeuze_engine_v2.physics.reference_forcefield import (
    _applicability_blockers,
    _torsion_angle,
    ReferencePhysicsApplicabilityError,
)
from betelgeuze_product.cpu_refinement.reference_forcefield_v1_1 import (
    _evaluate_validated_reference_terms,
)
from betelgeuze_product.cpu_refinement_v1_2.evaluation import ExtendedEvaluation
from betelgeuze_product.cpu_refinement_v1_2.fixed_receptor import (
    require_system,
    _evaluate_validated_cross_terms,
)
from betelgeuze_product.cpu_refinement_v1_2.provenance import (
    ResearchError,
    finite,
    integer,
    require_digest,
    digest,
    exact_fields,
)
from .parameters import FourierParameters, NonbondedParameter, CROSS_SCHEMA

INTERNAL_ID = "cpu_prepared_signed_fourier_internal/1.0.0"
FIXED_ID = "cpu_prepared_signed_fourier_fixed/1.0.0"
ENERGY_BASIS = "signed_proper_plus_ordered_periodic_improper_plus_bond_angle_nonbonded_plus_fixed_cross"


@dataclass(frozen=True)
class FourierInternalEvaluator:
    parameters: FourierParameters

    def __post_init__(self):
        if type(self.parameters) is not FourierParameters:
            raise ResearchError("explicit Fourier model required")

    def identity(self):
        return {
            "evaluator_id": INTERNAL_ID,
            "parameter_fingerprint_sha256": self.parameters.fingerprint_sha256,
        }

    @property
    def fingerprint_sha256(self):
        return digest(self.identity())

    def evaluate(self, system, neighbors):
        _require_fourier_topology(system, neighbors, self.parameters)
        return _evaluate_validated_fourier_terms(
            system, neighbors, self.parameters, self.identity()
        )


def _require_fourier_topology(system, neighbors, parameters):
    """Owning profiles supply the complete parameter view before arithmetic."""
    require_system(system, 256)
    blockers = _applicability_blockers(system, neighbors, parameters)
    if blockers:
        raise ReferencePhysicsApplicabilityError(
            "Fourier base applicability failed: " + ",".join(blockers)
        )
    bonds = {tuple(sorted((r.atom_i, r.atom_j))) for r in system.bonds}
    for row in parameters.periodic_impropers:
        indices = (row.atom_i, row.atom_j, row.atom_k, row.atom_l)
        if max(indices) >= system.atom_count or any(
            tuple(sorted((row.star_center, i))) not in bonds
            for i in indices
            if i != row.star_center
        ):
            raise ReferencePhysicsApplicabilityError(
                "ordered periodic improper lacks declared bonded star"
            )


def _evaluate_validated_fourier_terms(system, neighbors, parameters, identity):
    """Private arithmetic seam. Caller must admit the complete owning model."""
    base = _evaluate_validated_reference_terms(system, neighbors, parameters)
    xyz = system.coordinates.detach().clone().requires_grad_(True)
    improper = xyz.sum(dim=(1, 2)) * 0.0
    for row in parameters.periodic_impropers:
        phi = _torsion_angle(
            xyz, system, row.atom_i, row.atom_j, row.atom_k, row.atom_l
        )
        improper = improper + row.amplitude_kcal_per_mol * (
            1.0 + torch.cos(row.periodicity * phi - row.phase_radians)
        )
    listed_lj = xyz.sum(dim=(1, 2)) * 0.0
    listed_qq = xyz.sum(dim=(1, 2)) * 0.0
    for row in parameters.listed_pairs:
        if max(row.atom_i, row.atom_j) >= system.atom_count:
            raise ReferencePhysicsApplicabilityError(
                "listed pair index outside ligand"
            )
        distance = torch.linalg.vector_norm(
            xyz[:, row.atom_i] - xyz[:, row.atom_j], dim=-1
        )
        if bool(
            (
                distance
                < parameters.applicability_domain.minimum_pair_distance_angstrom
            ).any()
        ):
            raise ReferencePhysicsApplicabilityError(
                "listed pair distance outside applicability"
            )
        ratio6 = (row.sigma_angstrom / distance).pow(6)
        listed_lj = listed_lj + 4.0 * row.epsilon_kcal_per_mol * (
            ratio6.square() - ratio6
        )
        qi = parameters.atom_parameters[row.atom_i].charge_e
        qj = parameters.atom_parameters[row.atom_j].charge_e
        listed_qq = (
            listed_qq
            + COULOMB_KCAL_ANGSTROM_PER_MOL_E2
            * row.electrostatic_scale
            * qi
            * qj
            / distance
        )
    extra = improper + listed_lj + listed_qq
    extra_force = -torch.autograd.grad(extra.sum(), xyz)[0]
    energy = base.term.energy + extra.detach()
    forces = base.term.forces + extra_force.detach()
    if not bool(torch.isfinite(energy).all()) or not bool(
        torch.isfinite(forces).all()
    ):
        raise ReferencePhysicsApplicabilityError("nonfinite Fourier result")
    term = replace(
        base.term,
        name=INTERNAL_ID,
        energy=energy,
        forces=forces,
        energy_descriptor=QuantityDescriptor(
            name="prepared_fourier_internal_energy",
            unit="kcal/mol",
            semantics="declared_signed_periodic_proper_and_ordered_periodic_improper_model",
            physical_quantity=True,
            calibrated=False,
            reference_method=None,
        ),
        provenance_sha256=digest(
            {
                "evaluator": identity,
                "system": canonical_system_sha256(system),
            }
        ),
    )
    components = {
        **base.component_energies,
        "ordered_periodic_improper": improper.detach(),
        "listed_pair_lennard_jones": listed_lj.detach(),
        "listed_pair_coulomb": listed_qq.detach(),
    }
    return ExtendedEvaluation(
        term,
        MappingProxyType(components),
        (),
        digest(identity),
        (
            *base.scientific_blockers,
            "prepared_fourier_model_not_scientifically_validated",
        ),
    )


@dataclass(frozen=True)
class FourierCrossParameters:
    parameter_set_id: str
    parameter_source_sha256: str
    receptor_system_sha256: str
    ligand_topology_sha256: str
    ligand_base_parameters_sha256: str
    coordinate_frame_id: str
    receptor_atoms: tuple[NonbondedParameter, ...]
    cutoff_angstrom: float
    switch_start_angstrom: float
    minimum_distance_angstrom: float
    dielectric: float
    screening_kappa_per_angstrom: float
    receptor_block_size: int
    max_internal_increase_kcal_per_mol: float
    pair_policy: str = "all_non_covalent_cross_pairs_no_exclusions"
    mixing_rule: str = "lorentz_berthelot"
    schema_id: str = CROSS_SCHEMA

    def __post_init__(self):
        if (
            self.schema_id != CROSS_SCHEMA
            or self.pair_policy != "all_non_covalent_cross_pairs_no_exclusions"
            or self.mixing_rule != "lorentz_berthelot"
        ):
            raise ResearchError("explicit Fourier cross model required")
        for name in ("parameter_set_id", "coordinate_frame_id"):
            value = getattr(self, name)
            if (
                type(value) is not str
                or not value.strip()
                or value != value.strip()
                or len(value) > 512
            ):
                raise ResearchError("bounded cross identity required")
        for name in (
            "parameter_source_sha256",
            "receptor_system_sha256",
            "ligand_topology_sha256",
            "ligand_base_parameters_sha256",
        ):
            require_digest(getattr(self, name))
        if (
            type(self.receptor_atoms) is not tuple
            or not 1 <= len(self.receptor_atoms) <= 8192
            or any(
                type(r) is not NonbondedParameter or r.atom_index != i
                for i, r in enumerate(self.receptor_atoms)
            )
        ):
            raise ResearchError("complete Fourier receptor parameter rows required")
        for name in (
            "cutoff_angstrom",
            "switch_start_angstrom",
            "minimum_distance_angstrom",
            "dielectric",
            "screening_kappa_per_angstrom",
            "max_internal_increase_kcal_per_mol",
        ):
            object.__setattr__(
                self, name, finite(getattr(self, name), nonnegative=True)
            )
        if (
            not 0
            < self.minimum_distance_angstrom
            < self.switch_start_angstrom
            < self.cutoff_angstrom
            <= 1000
            or not 0 < self.dielectric <= 1e6
            or self.screening_kappa_per_angstrom > 100
            or self.max_internal_increase_kcal_per_mol > 1e6
        ):
            raise ResearchError("unsupported Fourier cross bounds")
        integer(self.receptor_block_size, 1, 512)

    def to_dict(self):
        return {
            **{
                f.name: getattr(self, f.name)
                for f in fields(self)
                if f.name != "receptor_atoms"
            },
            "receptor_atoms": [r.to_dict() for r in self.receptor_atoms],
        }

    @property
    def fingerprint_sha256(self):
        return digest(self.to_dict())

    @classmethod
    def from_dict(cls, value):
        exact_fields(value, {f.name for f in fields(cls)})
        result = cls(
            **{
                **value,
                "receptor_atoms": tuple(
                    NonbondedParameter(**r) for r in value["receptor_atoms"]
                ),
            }
        )
        if result.to_dict() != value:
            raise ResearchError("noncanonical Fourier cross document")
        return result


@dataclass(frozen=True)
class FourierEnvironment:
    receptor: object
    cross: FourierCrossParameters

    def __post_init__(self):
        if type(self.cross) is not FourierCrossParameters:
            raise ResearchError("explicit Fourier cross parameters required")
        self.assert_intact()

    def assert_intact(self):
        require_system(self.receptor, 8192)
        if canonical_system_sha256(
            self.receptor
        ) != self.cross.receptor_system_sha256 or self.receptor.atom_count != len(
            self.cross.receptor_atoms
        ):
            raise ResearchError("Fourier receptor identity/coverage mismatch")
        for atom, row in zip(
            self.receptor.atoms, self.cross.receptor_atoms, strict=True
        ):
            if (
                atom.partial_charge_e is None
                or float(atom.partial_charge_e).hex() != row.charge_e.hex()
            ):
                raise ResearchError("Fourier receptor charge mismatch")

    def validate_ligand(self, ligand, parameters):
        self.assert_intact()
        require_system(ligand, 256)
        if (
            type(parameters) is not FourierParameters
            or canonical_topology_sha256(ligand) != self.cross.ligand_topology_sha256
            or parameters.fingerprint_sha256 != self.cross.ligand_base_parameters_sha256
            or len(parameters.atom_parameters) != ligand.atom_count
        ):
            raise ResearchError("Fourier ligand parameter identity/coverage mismatch")
        for atom, row in zip(ligand.atoms, parameters.atom_parameters, strict=True):
            if (
                atom.partial_charge_e is None
                or float(atom.partial_charge_e).hex() != row.charge_e.hex()
            ):
                raise ResearchError("Fourier ligand charge mismatch")
        return parameters.atom_parameters

    def evaluate_cross(self, ligand, parameters):
        return _evaluate_validated_cross_terms(
            self, ligand, self.validate_ligand(ligand, parameters)
        )


@dataclass(frozen=True)
class FourierFixedEvaluator:
    parameters: FourierParameters
    fixed: FourierEnvironment

    def __post_init__(self):
        if (
            type(self.parameters) is not FourierParameters
            or type(self.fixed) is not FourierEnvironment
        ):
            raise ResearchError("explicit Fourier fixed evaluator required")

    def identity(self):
        return {
            "evaluator_id": FIXED_ID,
            "parameter_fingerprint_sha256": self.parameters.fingerprint_sha256,
            "cross_parameters_sha256": self.fixed.cross.fingerprint_sha256,
        }

    @property
    def fingerprint_sha256(self):
        return digest(self.identity())

    def evaluate(self, system, neighbors):
        self.fixed.validate_ligand(system, self.parameters)
        base = FourierInternalEvaluator(self.parameters).evaluate(system, neighbors)
        cross, force, _ = self.fixed.evaluate_cross(system, self.parameters)
        components = {"ligand_internal": base.term.energy, **cross}
        term = replace(
            base.term,
            name=FIXED_ID,
            energy=sum(components.values(), torch.zeros_like(base.term.energy)),
            forces=base.term.forces + force,
            energy_descriptor=replace(
                base.term.energy_descriptor,
                name="prepared_fourier_fixed_energy",
                semantics=ENERGY_BASIS,
            ),
            provenance_sha256=digest(
                {
                    "evaluator": self.identity(),
                    "system": canonical_system_sha256(system),
                }
            ),
        )
        return ExtendedEvaluation(
            term,
            MappingProxyType(components),
            (),
            self.fingerprint_sha256,
            base.scientific_blockers,
        )

