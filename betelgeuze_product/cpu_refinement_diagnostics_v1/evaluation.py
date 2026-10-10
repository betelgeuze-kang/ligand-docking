"""Reuse admitted internal physics; differentiate only the two cross leaves.

This diagnostic graph never supplies optimizer forces. It reproduces the
original receptor-block order and differentiated quintic switching function.
Internal leaf energies are explanatory subdivisions, not additional totals.
"""
from dataclasses import asdict
import time

import torch

from betelgeuze_engine_v2.geometry import RadiusGraphConfig, build_compact_radius_graph
from betelgeuze_engine_v2.molecular import canonical_topology_sha256
from betelgeuze_engine_v2.physics.reference_parameters import COULOMB_KCAL_ANGSTROM_PER_MOL_E2
from betelgeuze_product.cpu_refinement_fourier_v1.evaluation import (
    FourierFixedEvaluator, FourierInternalEvaluator,
)
from betelgeuze_product.cpu_refinement_linear_angle_v1.evaluation import (
    LinearAngleFixedEvaluator, LinearAngleInternalEvaluator,
)
from betelgeuze_product.cpu_refinement_v1_2.provenance import (
    coordinates_hex, decode_coordinates, digest, finite,
)
from betelgeuze_product.cpu_refinement_v1_3.kernel import scalar, validate_observation
from .contracts import COMPONENTS, RECORD_SCHEMA, DiagnosticConfig, empty_work, require
from .geometry import geometry_changes


def split_cross(fixed, ligand, parameters, work):
    """Return separate ligand forces; full owning cross admission runs first."""
    params = fixed.validate_ligand(ligand, parameters)
    xyz = ligand.coordinates[0].detach().clone().requires_grad_(True)
    receptor = fixed.receptor.coordinates[0].detach().clone()
    energies = {name: torch.zeros((), dtype=torch.float64) for name in COMPONENTS[1:]}
    forces = {name: torch.zeros_like(xyz) for name in COMPONENTS[1:]}
    lp = torch.tensor([[a.sigma_angstrom, a.epsilon_kcal_per_mol, a.charge_e]
                       for a in params], dtype=torch.float64)
    work['cross_passes'] += 1
    for start in range(0, fixed.receptor.atom_count, fixed.cross.receptor_block_size):
        work['cross_blocks_visited'] += 1
        end = min(start + fixed.cross.receptor_block_size, fixed.receptor.atom_count)
        distances = torch.linalg.vector_norm(xyz[:, None, :] - receptor[None, start:end, :], dim=-1)
        require(bool(torch.isfinite(distances).all()), 'nonfinite diagnostic cross distance')
        require(not bool((distances < fixed.cross.minimum_distance_angstrom).any()),
                'diagnostic cross distance outside admitted domain')
        left, right = torch.nonzero(distances < fixed.cross.cutoff_angstrom, as_tuple=True)
        if not left.numel():
            continue
        work['cross_blocks_active'] += 1
        r = distances[left, right]
        rp = torch.tensor([[a.sigma_angstrom, a.epsilon_kcal_per_mol, a.charge_e]
                           for a in fixed.cross.receptor_atoms[start:end]], dtype=torch.float64)
        sigma = .5 * (lp[left, 0] + rp[right, 0])
        epsilon = torch.sqrt(lp[left, 1] * rp[right, 1])
        ratio6 = (sigma / r).pow(6)
        pair_lj = 4 * epsilon * (ratio6.pow(2) - ratio6)
        pair_q = (COULOMB_KCAL_ANGSTROM_PER_MOL_E2 * lp[left, 2] * rp[right, 2]
                  * torch.exp(-fixed.cross.screening_kappa_per_angstrom * r)
                  / (fixed.cross.dielectric * r))
        t = ((r - fixed.cross.switch_start_angstrom)
             / (fixed.cross.cutoff_angstrom - fixed.cross.switch_start_angstrom)).clamp(0., 1.)
        switch = 1 - 10*t.pow(3) + 15*t.pow(4) - 6*t.pow(5)
        values = ((pair_lj * switch).sum(), (pair_q * switch).sum())
        for index, (name, value) in enumerate(zip(COMPONENTS[1:], values)):
            work['cross_component_gradient_calls'] += 1
            gradient = torch.autograd.grad(value, xyz, retain_graph=index == 0)[0]
            require(bool(torch.isfinite(value)) and bool(torch.isfinite(gradient).all()),
                    'nonfinite diagnostic cross component')
            energies[name] += value.detach()
            forces[name] -= gradient.detach()
    fixed.assert_intact()
    return energies, {name: force.unsqueeze(0) for name, force in forces.items()}


def _component(energy, forces, atoms):
    require(bool(torch.isfinite(forces).all()), 'nonfinite diagnostic forces')
    norms = torch.linalg.vector_norm(forces[0], dim=-1)
    index = int(torch.argmax(norms))  # First index is the deterministic tie break.
    rows = coordinates_hex(forces)
    return {'energy': finite(float(energy)).hex(), 'forces': rows,
            'forces_sha256': digest(rows), 'maximum_atom_force': finite(float(norms[index])).hex(),
            'highest_force_atom': atoms[index],
            'force_l2_norm': finite(float(torch.linalg.vector_norm(forces))).hex(),
            'net_force': [finite(float(v)).hex() for v in forces[0].sum(dim=0)]}


def _parity(actual, expected, atol=1.e-9, rtol=1.e-10):
    a = torch.as_tensor(actual, dtype=torch.float64)
    b = torch.as_tensor(expected, dtype=torch.float64)
    require(a.shape == b.shape and bool(torch.isfinite(a).all()) and bool(torch.isfinite(b).all()),
            'invalid diagnostic parity operands')
    error = (a - b).abs()
    scale = torch.maximum(a.abs(), b.abs())
    return {'passed': bool((error <= atol + rtol * scale).all()),
            'maximum_absolute_error': float(error.max()).hex(),
            'maximum_scaled_error': float((error / torch.maximum(scale, torch.ones_like(scale))).max()).hex()}


def diagnose_observation(original, evaluator, solver_config, observation, *,
                         observation_ref, diagnostic_config=DiagnosticConfig(), shape_profile=None):
    """Single-point diagnostics only; caller must separately verify source evidence.

    Shape observations require their admitted owning ShapeProfile. This helper
    does not authenticate a journal or grant preparation/selection authority.
    """
    require(type(diagnostic_config) is DiagnosticConfig, 'explicit diagnostic configuration required')
    require(type(evaluator) in (FourierFixedEvaluator, LinearAngleFixedEvaluator),
            'supported exact prepared evaluator required')
    validator = validate_observation if shape_profile is None else shape_profile.validate_observation
    observed = validator(observation, original.atom_count)
    base = observed if shape_profile is None else observed['base_observation']
    xyz = decode_coordinates(observed['coordinates'], original.atom_count)
    trial = original.with_coordinates(xyz, operation='read_only_force_geometry_diagnostics_v1')
    evaluator.fixed.validate_ligand(trial, evaluator.parameters)
    atoms = [{'source_index': atom.index, 'element': atom.element,
              'atom_metadata_sha256': digest(asdict(atom))} for atom in trial.atoms]
    work = empty_work()
    started = time.perf_counter_ns()
    record = {'schema_id': RECORD_SCHEMA, 'observation_ref': observation_ref,
              'observation_sha256': digest(observed), 'coordinates_sha256': digest(observed['coordinates']),
              'topology_sha256': canonical_topology_sha256(trial), 'atoms': atoms,
              'evaluator': evaluator.identity(), 'source_evidence_verified': False,
              'status': 'failed', 'components': {}, 'internal_component_energies': {},
              'parity': {}, 'geometry': None, 'failure_code': None}
    try:
        work['graph_calls'] += 1
        neighbors = build_compact_radius_graph(xyz, RadiusGraphConfig(
            cutoff_angstrom=evaluator.parameters.base_parameters.cutoff_angstrom,
            max_neighbors=solver_config.max_neighbors, max_atoms_per_cell=solver_config.max_atoms_per_cell))
        internal_type = (FourierInternalEvaluator if type(evaluator) is FourierFixedEvaluator
                         else LinearAngleInternalEvaluator)
        work['internal_evaluator_calls'] += 1
        internal = internal_type(evaluator.parameters).evaluate(trial, neighbors)
        energies, forces = split_cross(evaluator.fixed, trial, evaluator.parameters, work)
        energies['ligand_internal'] = internal.term.energy[0]
        forces['ligand_internal'] = internal.term.forces
        record['internal_component_energies'] = {
            name: finite(float(value[0])).hex() for name, value in internal.component_energies.items()}
        record['internal_component_energy_semantics'] = 'subdivision_of_ligand_internal_not_additional_terms'
        record['internal_component_forces_available'] = False
        record['components'] = {name: _component(energies[name], forces[name], atoms) for name in COMPONENTS}
        total_energy = sum((energies[name] for name in COMPONENTS), torch.zeros((), dtype=torch.float64))
        total_force = forces['ligand_internal'] + (forces['cross_lennard_jones'] + forces['cross_screened_coulomb'])
        parity = {name + '_energy': _parity(energies[name], scalar(base['components'][name])) for name in COMPONENTS}
        parity['internal_leaf_energy_sum'] = _parity(
            sum(internal.component_energies.values(), torch.zeros_like(internal.term.energy))[0],
            internal.term.energy[0])
        parity['unpenalized_energy'] = _parity(total_energy, scalar(base['energy']))
        parity['unpenalized_forces'] = _parity(total_force, decode_coordinates(base['forces'], original.atom_count))
        # Cross-only parity against the retained total minus the unchanged internal force.
        parity['cross_force_sum'] = _parity(forces['cross_lennard_jones'] + forces['cross_screened_coulomb'],
            decode_coordinates(base['forces'], original.atom_count) - internal.term.forces)
        record['unpenalized_total'] = _component(total_energy, total_force, atoms)
        if shape_profile is not None:
            shape = decode_coordinates(observed['restraint_forces'], original.atom_count)
            penalty = scalar(observed['components']['parent_shape_restraint'])
            record['components']['parent_shape_restraint'] = _component(penalty, shape, atoms)
            work['retained_shape_reuses'] += 1
            combined = total_force if shape_profile.strength == 0 else total_force + shape
            combined_energy = total_energy if shape_profile.strength == 0 else total_energy + penalty
            parity['augmented_energy'] = _parity(combined_energy, scalar(observed['energy']))
            parity['augmented_forces'] = _parity(combined, decode_coordinates(observed['forces'], original.atom_count))
            record['augmented_total'] = _component(combined_energy, combined, atoms)
        record['geometry'] = geometry_changes(original, trial, evaluator.parameters)
        require(coordinates_hex(trial.coordinates) == observed['coordinates'], 'diagnostic trial mutation')
        record['parity'] = parity
        record['status'] = 'evaluated' if all(row['passed'] for row in parity.values()) else 'parity_failed'
    except Exception as exc:
        work['failed_evaluations'] += 1
        record['failure_code'] = type(exc).__name__[:128]
    record['work'] = work
    record['wall_ns'] = time.perf_counter_ns() - started
    return {**record, 'record_sha256': digest(record)}
