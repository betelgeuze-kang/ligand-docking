"""Differentiable CPU reference force-field terms with fail-closed applicability."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math

import torch

from betelgeuze_engine_v2.contracts import QuantityDescriptor
from betelgeuze_engine_v2.geometry import CompactNeighborList
from betelgeuze_engine_v2.molecular import AllAtomSystem, canonical_system_sha256
from .composition import EnergyTermResult
from .reference_parameters import (
    COULOMB_KCAL_ANGSTROM_PER_MOL_E2,
    ReferenceForceFieldParameters,
)


class ReferencePhysicsApplicabilityError(RuntimeError):
    """The explicit parameter set cannot safely evaluate the supplied system."""


@dataclass(frozen=True)
class ReferencePhysicsEvaluation:
    term: EnergyTermResult
    component_energies: dict[str, torch.Tensor]
    applicability_blockers: tuple[str, ...]
    scientific_blockers: tuple[str, ...]
    parameter_fingerprint_sha256: str

    @property
    def execution_complete(self) -> bool:
        return not self.applicability_blockers

    @property
    def scientifically_validated(self) -> bool:
        return not self.scientific_blockers

    def to_dict(self) -> dict[str, object]:
        return {
            "execution_complete": self.execution_complete,
            "scientifically_validated": self.scientifically_validated,
            "validated_for_composition": self.term.validated_for_composition,
            "component_names": sorted(self.component_energies),
            "applicability_blockers": list(self.applicability_blockers),
            "scientific_blockers": list(self.scientific_blockers),
            "parameter_fingerprint_sha256": self.parameter_fingerprint_sha256,
        }


def _minimum_image(delta: torch.Tensor, system: AllAtomSystem) -> torch.Tensor:
    if system.cell is None:
        return delta
    lengths = system.cell.orthorhombic_lengths().to(dtype=delta.dtype, device=delta.device)
    periodic = torch.tensor(system.cell.periodic, dtype=torch.bool, device=delta.device)
    safe_lengths = torch.where(periodic, lengths, torch.ones_like(lengths))
    wrapped = delta - torch.round(delta / safe_lengths) * safe_lengths
    return torch.where(periodic, wrapped, delta)


def _vector(coordinates: torch.Tensor, system: AllAtomSystem, first: int, second: int) -> torch.Tensor:
    return _minimum_image(coordinates[:, first] - coordinates[:, second], system)


def _angle(first: torch.Tensor, second: torch.Tensor) -> torch.Tensor:
    first_norm = torch.linalg.vector_norm(first, dim=-1)
    second_norm = torch.linalg.vector_norm(second, dim=-1)
    if bool((first_norm <= 1.0e-12).any().item()) or bool((second_norm <= 1.0e-12).any().item()):
        raise ReferencePhysicsApplicabilityError("angle contains a zero-length vector")
    cosine = (first * second).sum(dim=-1) / (first_norm * second_norm)
    return torch.acos(cosine.clamp(-1.0 + 1.0e-12, 1.0 - 1.0e-12))


def _torsion_angle(
    coordinates: torch.Tensor,
    system: AllAtomSystem,
    atom_i: int,
    atom_j: int,
    atom_k: int,
    atom_l: int,
) -> torch.Tensor:
    b0 = _vector(coordinates, system, atom_i, atom_j)
    b1 = _vector(coordinates, system, atom_k, atom_j)
    b2 = _vector(coordinates, system, atom_l, atom_k)
    b1_norm = torch.linalg.vector_norm(b1, dim=-1, keepdim=True)
    if bool((b1_norm <= 1.0e-12).any().item()):
        raise ReferencePhysicsApplicabilityError("torsion contains a zero-length central bond")
    axis = b1 / b1_norm
    v = b0 - (b0 * axis).sum(dim=-1, keepdim=True) * axis
    w = b2 - (b2 * axis).sum(dim=-1, keepdim=True) * axis
    v_norm = torch.linalg.vector_norm(v, dim=-1)
    w_norm = torch.linalg.vector_norm(w, dim=-1)
    if bool((v_norm <= 1.0e-12).any().item()) or bool((w_norm <= 1.0e-12).any().item()):
        raise ReferencePhysicsApplicabilityError("torsion is undefined for collinear atoms")
    x = (v * w).sum(dim=-1)
    y = (torch.cross(axis, v, dim=-1) * w).sum(dim=-1)
    return torch.atan2(y, x)


def _switch(distance: torch.Tensor, start: float, cutoff: float) -> torch.Tensor:
    x = ((distance - start) / (cutoff - start)).clamp(0.0, 1.0)
    smooth = 1.0 - 10.0 * x.pow(3) + 15.0 * x.pow(4) - 6.0 * x.pow(5)
    return torch.where(distance <= start, torch.ones_like(distance), torch.where(distance < cutoff, smooth, torch.zeros_like(distance)))


def _validate_indices(parameters: ReferenceForceFieldParameters, atom_count: int) -> tuple[str, ...]:
    blockers: list[str] = []
    expected = set(range(atom_count))
    if set(parameters.atom_parameter_map) != expected:
        blockers.append("nonbonded_parameters_do_not_cover_all_atoms")
    for row in parameters.bonds:
        if max(row.atom_i, row.atom_j) >= atom_count:
            blockers.append("bond_parameter_index_out_of_range")
    for row in parameters.angles:
        if max(row.atom_i, row.atom_j, row.atom_k) >= atom_count:
            blockers.append("angle_parameter_index_out_of_range")
    for row in parameters.torsions:
        if max(row.atom_i, row.atom_j, row.atom_k, row.atom_l) >= atom_count:
            blockers.append("torsion_parameter_index_out_of_range")
    for pair in parameters.excluded_pairs:
        if max(pair) >= atom_count:
            blockers.append("excluded_pair_index_out_of_range")
    for row in parameters.scaled_pairs:
        if max(row.atom_i, row.atom_j) >= atom_count:
            blockers.append("scaled_pair_index_out_of_range")
    return tuple(dict.fromkeys(blockers))


def _applicability_blockers(
    system: AllAtomSystem,
    neighbors: CompactNeighborList,
    parameters: ReferenceForceFieldParameters,
) -> tuple[str, ...]:
    domain = parameters.applicability_domain
    blockers: list[str] = list(_validate_indices(parameters, system.atom_count))
    if system.atom_count > domain.max_atoms:
        blockers.append("atom_count_outside_applicability_domain")
    if len(parameters.bonds) > domain.max_bonds:
        blockers.append("bond_count_outside_applicability_domain")
    if len(parameters.angles) > domain.max_angles:
        blockers.append("angle_count_outside_applicability_domain")
    if len(parameters.torsions) > domain.max_torsions:
        blockers.append("torsion_count_outside_applicability_domain")
    if neighbors.pair_count // 2 > domain.max_nonbonded_pairs:
        blockers.append("nonbonded_pair_count_outside_applicability_domain")
    if float(neighbors.diagnostics.cutoff_angstrom) + 1.0e-12 < parameters.cutoff_angstrom:
        blockers.append("neighbor_cutoff_shorter_than_parameter_cutoff")
    if system.cell is not None:
        if not domain.periodic_orthorhombic_supported:
            blockers.append("periodic_system_outside_applicability_domain")
        else:
            try:
                system.cell.orthorhombic_lengths()
            except ValueError:
                blockers.append("nonorthorhombic_cell_not_supported")
    return tuple(dict.fromkeys(blockers))


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
    batch_size = int(coordinates.shape[0])
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
        calibrated=bool(parameters.scientifically_validated),
        reference_method=reference_method if parameters.scientifically_validated else None,
    )
    force_descriptor = QuantityDescriptor(
        name="reference_force_field_force",
        unit="kcal/mol/angstrom",
        semantics="negative_coordinate_gradient_of_reference_force_field_energy",
        physical_quantity=True,
        calibrated=bool(parameters.scientifically_validated),
        reference_method=reference_method if parameters.scientifically_validated else None,
    )
    provenance_payload = {
        "parameter_fingerprint_sha256": parameters.fingerprint_sha256,
        "system_sha256": canonical_system_sha256(system),
        "neighbor_schema": neighbors.diagnostics.schema_version,
        "neighbor_cutoff_angstrom": neighbors.diagnostics.cutoff_angstrom,
        "directed_pair_count": neighbors.diagnostics.directed_pair_count,
    }
    provenance_sha256 = hashlib.sha256(
        json.dumps(provenance_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    scientific_blockers = () if parameters.scientifically_validated else (
        "reference_parameter_set_not_scientifically_validated",
        "applicability_domain_evidence_missing",
        "public_force_energy_validation_missing",
    )
    term = EnergyTermResult(
        name=f"reference_force_field:{reference_method}",
        energy=total.detach(),
        forces=forces.detach(),
        energy_descriptor=energy_descriptor,
        force_descriptor=force_descriptor,
        validated_for_composition=bool(parameters.scientifically_validated),
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
    provider_version = "1.0.0"

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


__all__ = [
    "ReferenceForceFieldProvider",
    "ReferencePhysicsApplicabilityError",
    "ReferencePhysicsEvaluation",
    "evaluate_reference_force_field",
]
