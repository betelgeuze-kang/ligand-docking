"""Opt-in 1.1 CPU numerics: stable angular forces, no historical resealing.

The frozen 1.0 evaluator remains byte-identical for its archived validation
protocol. Applicability, topology, switching and torsion helpers are reused;
only this explicit evaluator's angular geometry and provenance are different.
This is not scientific validation or a change to default product routing.
"""
from __future__ import annotations

import hashlib
import json
import math
import torch

from betelgeuze_engine_v2.contracts import QuantityDescriptor
from betelgeuze_engine_v2.geometry import CompactNeighborList
from betelgeuze_engine_v2.molecular import AllAtomSystem, canonical_system_sha256
from .composition import EnergyTermResult
from .reference_parameters import COULOMB_KCAL_ANGSTROM_PER_MOL_E2, ReferenceForceFieldParameters
from .reference_forcefield import (
    ReferencePhysicsApplicabilityError, ReferencePhysicsEvaluation,
    _applicability_blockers, _vector, _torsion_angle, _switch,
)

REFERENCE_FORCE_FIELD_NUMERICS_ID = "explicit_reference_force_field/1.1.0"


def _angle(first: torch.Tensor, second: torch.Tensor) -> torch.Tensor:
    # acos(clamp(cos(theta))) flattens a finite region near 0 and pi,
    # returning zero forces and false convergence for non-collinear angles.
    # Normalize before the cross product to avoid multiplying bond lengths.
    first_norm = torch.linalg.vector_norm(first, dim=-1, keepdim=True)
    second_norm = torch.linalg.vector_norm(second, dim=-1, keepdim=True)
    if not bool(torch.isfinite(first_norm).all().item()) or not bool(
        torch.isfinite(second_norm).all().item()
    ):
        raise ReferencePhysicsApplicabilityError("angle contains a non-finite vector norm")
    if bool((first_norm <= 1.0e-12).any().item()) or bool((second_norm <= 1.0e-12).any().item()):
        raise ReferencePhysicsApplicabilityError("angle contains a zero-length vector")
    left, right = first / first_norm, second / second_norm
    sine = torch.linalg.vector_norm(torch.linalg.cross(left, right, dim=-1), dim=-1)
    cosine = (left * right).sum(dim=-1)
    # The angular direction is undefined at collinearity. Reject the
    # roundoff-scale region explicitly; never substitute a flat energy or force.
    if bool((sine <= 8.0 * torch.finfo(sine.dtype).eps).any().item()):
        raise ReferencePhysicsApplicabilityError(
            "angle is undefined for numerically collinear vectors"
        )
    return torch.atan2(sine, cosine)


def evaluate_reference_force_field(
    system: AllAtomSystem,
    neighbors: CompactNeighborList,
    parameters: ReferenceForceFieldParameters,
) -> ReferencePhysicsEvaluation:
    """Evaluate explicit terms and derive conservative forces by autograd."""

    blockers = _applicability_blockers(system, neighbors, parameters)
    if blockers:
        raise ReferencePhysicsApplicabilityError(
            "reference parameter applicability failed: " + ", ".join(blockers)
        )
    coordinates = system.coordinates.detach().clone().requires_grad_(True)
    zero = coordinates.sum(dim=(1, 2)) * 0.0
    bond_energy = zero.clone()
    angle_energy = zero.clone()
    torsion_energy = zero.clone()
    lj_energy = zero.clone()
    electrostatic_energy = zero.clone()

    for row in parameters.bonds:
        distance = torch.linalg.vector_norm(
            _vector(coordinates, system, row.atom_i, row.atom_j),
            dim=-1,
        )
        bond_energy = bond_energy + 0.5 * row.force_constant_kcal_per_mol_angstrom2 * (
            distance - row.equilibrium_angstrom
        ).pow(2)

    for row in parameters.angles:
        value = _angle(
            _vector(coordinates, system, row.atom_i, row.atom_j),
            _vector(coordinates, system, row.atom_k, row.atom_j),
        )
        angle_energy = angle_energy + 0.5 * row.force_constant_kcal_per_mol_radian2 * (
            value - row.equilibrium_radians
        ).pow(2)

    for row in parameters.torsions:
        phi = _torsion_angle(
            coordinates,
            system,
            row.atom_i,
            row.atom_j,
            row.atom_k,
            row.atom_l,
        )
        torsion_energy = torsion_energy + row.amplitude_kcal_per_mol * (
            1.0 + torch.cos(row.periodicity * phi - row.phase_radians)
        )

    upper = neighbors.upper_mask()
    batch_index, source_index, slot = torch.nonzero(upper, as_tuple=True)
    target_index = neighbors.indices[batch_index, source_index, slot]
    pair_count = int(batch_index.numel())
    if pair_count:
        raw = coordinates[batch_index, source_index] - coordinates[batch_index, target_index]
        if system.cell is not None:
            shifts = neighbors.image_shifts[batch_index, source_index, slot].to(
                dtype=coordinates.dtype,
                device=coordinates.device,
            )
            vectors = system.cell.vectors.to(dtype=coordinates.dtype, device=coordinates.device)
            raw = raw - shifts @ vectors
        distance = torch.linalg.vector_norm(raw, dim=-1)
        if bool((distance < parameters.applicability_domain.minimum_pair_distance_angstrom).any().item()):
            raise ReferencePhysicsApplicabilityError("nonbonded pair is below minimum_pair_distance_angstrom")

        atom_map = parameters.atom_parameter_map
        scaling_map = parameters.pair_scaling_map
        excluded = set(parameters.excluded_pairs)
        sigma_values: list[float] = []
        epsilon_values: list[float] = []
        charge_products: list[float] = []
        lj_scales: list[float] = []
        electrostatic_scales: list[float] = []
        for source, target in zip(source_index.detach().cpu().tolist(), target_index.detach().cpu().tolist()):
            pair = tuple(sorted((int(source), int(target))))
            first = atom_map[int(source)]
            second = atom_map[int(target)]
            sigma_values.append(0.5 * (first.sigma_angstrom + second.sigma_angstrom))
            epsilon_values.append(math.sqrt(first.epsilon_kcal_per_mol * second.epsilon_kcal_per_mol))
            charge_products.append(first.charge_e * second.charge_e)
            if pair in excluded:
                lj_scales.append(0.0)
                electrostatic_scales.append(0.0)
            elif pair in scaling_map:
                scaling = scaling_map[pair]
                lj_scales.append(scaling.lj_scale)
                electrostatic_scales.append(scaling.electrostatic_scale)
            else:
                lj_scales.append(1.0)
                electrostatic_scales.append(1.0)

        dtype = coordinates.dtype
        device = coordinates.device
        sigma = torch.tensor(sigma_values, dtype=dtype, device=device)
        epsilon = torch.tensor(epsilon_values, dtype=dtype, device=device)
        charge_product = torch.tensor(charge_products, dtype=dtype, device=device)
        lj_scale = torch.tensor(lj_scales, dtype=dtype, device=device)
        electrostatic_scale = torch.tensor(electrostatic_scales, dtype=dtype, device=device)
        ratio6 = (sigma / distance).pow(6)
        pair_lj = 4.0 * epsilon * (ratio6.pow(2) - ratio6) * lj_scale
        pair_electrostatic = (
            COULOMB_KCAL_ANGSTROM_PER_MOL_E2
            * charge_product
            * torch.exp(-parameters.screening_kappa_per_angstrom * distance)
            / (parameters.dielectric * distance)
            * electrostatic_scale
        )
        switch = _switch(
            distance,
            parameters.switch_start_angstrom,
            parameters.cutoff_angstrom,
        )
        pair_lj = pair_lj * switch
        pair_electrostatic = pair_electrostatic * switch
        lj_energy = lj_energy.scatter_add(0, batch_index, pair_lj)
        electrostatic_energy = electrostatic_energy.scatter_add(
            0,
            batch_index,
            pair_electrostatic,
        )

    components = {
        "harmonic_bond": bond_energy,
        "harmonic_angle": angle_energy,
        "periodic_torsion": torsion_energy,
        "lennard_jones": lj_energy,
        "screened_coulomb": electrostatic_energy,
    }
    total = sum(components.values(), zero)
    gradient = torch.autograd.grad(total.sum(), coordinates, create_graph=False)[0]
    forces = -gradient

    reference_method = (
        f"{parameters.parameter_set_id}/{parameters.parameter_set_version}"
    )
    energy_descriptor = QuantityDescriptor(
        name="reference_force_field_energy",
        unit="kcal/mol",
        semantics="explicit_bond_angle_torsion_lj_screened_coulomb_total",
        physical_quantity=True,
        calibrated=False,
        reference_method=None,
    )
    force_descriptor = QuantityDescriptor(
        name="reference_force_field_force",
        unit="kcal/mol/angstrom",
        semantics="negative_coordinate_gradient_of_reference_force_field_energy",
        physical_quantity=True,
        calibrated=False,
        reference_method=None,
    )
    provenance_payload = {
        "numerics_id": REFERENCE_FORCE_FIELD_NUMERICS_ID,
        "parameter_fingerprint_sha256": parameters.fingerprint_sha256,
        "topology_sha256": parameters.topology_sha256,
        "system_sha256": canonical_system_sha256(system),
        "neighbor_schema": neighbors.diagnostics.schema_version,
        "neighbor_cutoff_angstrom": neighbors.diagnostics.cutoff_angstrom,
        "directed_pair_count": neighbors.diagnostics.directed_pair_count,
    }
    provenance_sha256 = hashlib.sha256(
        json.dumps(provenance_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    scientific_blockers = (
        "reference_parameter_set_not_scientifically_validated",
        "applicability_domain_evidence_missing",
        "public_force_energy_validation_missing",
        "verified_validation_receipt_not_implemented",
    )
    term = EnergyTermResult(
        name=f"reference_force_field:{reference_method}",
        energy=total.detach(),
        forces=forces.detach(),
        energy_descriptor=energy_descriptor,
        force_descriptor=force_descriptor,
        validated_for_composition=False,
        provenance_sha256=provenance_sha256,
    )
    return ReferencePhysicsEvaluation(
        term=term,
        component_energies={name: value.detach() for name, value in components.items()},
        applicability_blockers=(),
        scientific_blockers=scientific_blockers,
        parameter_fingerprint_sha256=parameters.fingerprint_sha256,
    )


class ReferenceForceFieldProvider:
    """IndependentPhysicsTerm implementation for one immutable parameter set."""

    provider_id = "engine_v2_reference_force_field"
    provider_version = "1.1.0"

    def __init__(self, parameters: ReferenceForceFieldParameters):
        self.parameters = parameters
        self.parameter_fingerprint_sha256 = parameters.fingerprint_sha256
        self.config_fingerprint_sha256 = parameters.fingerprint_sha256

    def evaluate(
        self,
        system: AllAtomSystem,
        neighbors: CompactNeighborList,
    ) -> EnergyTermResult:
        return evaluate_reference_force_field(system, neighbors, self.parameters).term
