"""Analytic (not implementation-differenced) regressions for angular forces."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math

import pytest
import torch

from betelgeuze_engine_v2.geometry import RadiusGraphConfig, build_compact_radius_graph
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem, Atom, Bond, Chain, Residue, StructureProvenance,
    canonical_topology_sha256,
)
from betelgeuze_engine_v2.physics.reference_forcefield_v1_1 import (
    ReferencePhysicsApplicabilityError, _angle, evaluate_reference_force_field,
)
from betelgeuze_engine_v2.physics.reference_minimization_v1_1 import (
    ReferenceMinimizationConfig, ReferenceMinimizationError,
    minimize_reference_force_field, require_reference_minimization_checkpoint_document,
)
from betelgeuze_engine_v2.physics.reference_parameters import (
    AtomNonbondedParameter, HarmonicAngleParameter, HarmonicBondParameter,
    ReferenceApplicabilityDomain, ReferenceForceFieldParameters,
)


def angle_system(theta: float):
    """Three atoms with equilibrium bond lengths; only the angle is displaced."""
    second_length = 2. if theta < .1 else 1.
    xyz = torch.tensor([[[1., 0., 0.], [0., 0., 0.],
                         [second_length * math.cos(theta), second_length * math.sin(theta), 0.]]], dtype=torch.float64)
    system = AllAtomSystem(
        system_id="synthetic-angle-boundary",
        atoms=tuple(Atom(index=i, name=f"C{i}", element="C", atomic_number=6,
                         residue_index=0, partial_charge_e=0.) for i in range(3)),
        bonds=(Bond(index=0, atom_i=0, atom_j=1), Bond(index=1, atom_i=1, atom_j=2)),
        residues=(Residue(index=0, name="LIG", chain_index=0, sequence_number=1,
                          atom_indices=(0, 1, 2), entity_type="non_polymer", hetero=True),),
        chains=(Chain(index=0, chain_id="L", residue_indices=(0,)),),
        coordinates=xyz,
        provenance=StructureProvenance(source_format="unit", source_id="angle-boundary",
                                      source_sha256="a" * 64, parser_name="unit", parser_version="1"),
    )
    parameters = ReferenceForceFieldParameters(
        parameter_set_id="synthetic-angle-boundary", parameter_set_version="1.0.0",
        topology_sha256=canonical_topology_sha256(system),
        atom_parameters=tuple(AtomNonbondedParameter(i, 1., 0., 0.) for i in range(3)),
        bonds=(HarmonicBondParameter(0, 1, 1., 100.), HarmonicBondParameter(1, 2, second_length, 100.)),
        angles=(HarmonicAngleParameter(0, 1, 2, math.pi / 2, 100.),),
        excluded_pairs=((0, 1), (0, 2), (1, 2)), cutoff_angstrom=4., switch_start_angstrom=3.,
        applicability_domain=ReferenceApplicabilityDomain(max_atoms=4),
    )
    return system, parameters


def evaluate(system, parameters):
    neighbors = build_compact_radius_graph(system.coordinates, RadiusGraphConfig(
        cutoff_angstrom=4., max_neighbors=4, max_atoms_per_cell=4))
    return evaluate_reference_force_field(system, neighbors, parameters)


def config():
    return ReferenceMinimizationConfig(max_iterations=3, max_neighbors=4, max_atoms_per_cell=4)


@pytest.mark.parametrize("theta", [1e-10, 1e-7, 1e-6, 1e-3, .7, 2.2,
                                    math.pi - 1e-3, math.pi - 1e-6,
                                    math.pi - 1e-7, math.pi - 1e-10])
def test_energy_and_force_match_closed_form(theta):
    system, parameters = angle_system(theta)
    result = evaluate(system, parameters)
    slope = 100. * (theta - math.pi / 2)
    # Analytic derivatives of the polar angle for unit length vectors.
    first = torch.tensor([0., slope, 0.], dtype=torch.float64)
    second_length = 2. if theta < .1 else 1.
    third = torch.tensor([slope * math.sin(theta), -slope * math.cos(theta), 0.],
                         dtype=torch.float64) / second_length
    expected_force = torch.stack((first, -first - third, third)).unsqueeze(0)
    assert result.term.energy.item() == pytest.approx(.5 * 100 * (theta-math.pi/2)**2,
                                                    rel=1e-12, abs=1e-12)
    torch.testing.assert_close(result.term.forces, expected_force, rtol=1e-11, atol=1e-10)


@pytest.mark.parametrize("delta", [1e-6, 1e-7, 1e-10])
def test_nearly_linear_angle_does_not_false_converge(delta):
    system, parameters = angle_system(math.pi - delta)
    result = minimize_reference_force_field(system, parameters, config())
    assert result.initial_max_force_kcal_per_mol_angstrom > 300.
    assert result.accepted_iterations > 0
    assert not torch.equal(result.system.coordinates, system.coordinates)
    assert result.final_energy_kcal_per_mol < result.initial_energy_kcal_per_mol


@pytest.mark.parametrize("other", [[1., 0., 0.], [-1., 0., 0.], [0., 0., 0.]])
def test_singular_angles_are_rejected_not_flattened(other):
    with pytest.raises(ReferencePhysicsApplicabilityError):
        _angle(torch.tensor([[1., 0., 0.]], dtype=torch.float64),
               torch.tensor([other], dtype=torch.float64))


def test_rotated_translated_force_and_zero_net_force_and_torque():
    system, parameters = angle_system(math.pi - 1e-7)
    original = evaluate(system, parameters)
    rotation = torch.tensor([[.36, -.48, .8], [.8, .6, 0.], [-.48, .64, .6]], dtype=torch.float64)
    moved = system.with_coordinates(system.coordinates @ rotation.T + .25,
                                    operation="unit_rigid_transform")
    result = evaluate(moved, parameters)
    torch.testing.assert_close(result.term.energy, original.term.energy, rtol=1e-12, atol=1e-12)
    torch.testing.assert_close(result.term.forces, original.term.forces @ rotation.T,
                               rtol=1e-8, atol=2e-7)
    torch.testing.assert_close(result.term.forces.sum(dim=1), torch.zeros((1, 3), dtype=torch.float64),
                               rtol=0., atol=1e-10)
    torque = torch.linalg.cross(moved.coordinates, result.term.forces, dim=-1).sum(dim=1)
    torch.testing.assert_close(torque, torch.zeros_like(torque), rtol=0., atol=1e-10)


def test_angle_autograd_check_away_from_singular_points():
    first = torch.tensor([[1., .2, -.3]], dtype=torch.float64, requires_grad=True)
    second = torch.tensor([[-.2, .9, .5]], dtype=torch.float64, requires_grad=True)
    assert torch.autograd.gradcheck(_angle, (first, second))


def test_restart_new_numerics_exact_and_reject_old_algorithm():
    system, parameters = angle_system(math.pi - 1e-7)
    full = minimize_reference_force_field(system, parameters, config())
    paused = minimize_reference_force_field(system, parameters, config(), pause_after_accepted_iterations=1)
    resumed = minimize_reference_force_field(system, parameters, config(), checkpoint=paused.checkpoint)
    assert full.checkpoint.to_dict() == resumed.checkpoint.to_dict()
    old = deepcopy(paused.checkpoint.to_dict())
    old['algorithm_id'] = 'betelgeuze.engine_v2_reference_force_steepest_descent/1.0.0'
    payload = {k: v for k, v in old.items() if k != 'checkpoint_sha256'}
    old['checkpoint_sha256'] = hashlib.sha256(json.dumps(payload, allow_nan=False,
        ensure_ascii=True, separators=(',', ':'), sort_keys=True).encode('ascii')).hexdigest()
    with pytest.raises(ReferenceMinimizationError, match='algorithm'):
        require_reference_minimization_checkpoint_document(old)


def test_real_checkpoints_cannot_cross_numerics_versions():
    from betelgeuze_engine_v2.physics import reference_minimization as legacy
    system, parameters = angle_system(2.)
    old = legacy.minimize_reference_force_field(
        system, parameters, legacy.ReferenceMinimizationConfig(max_iterations=2),
        pause_after_accepted_iterations=0)
    with pytest.raises(ReferenceMinimizationError, match="algorithm"):
        minimize_reference_force_field(system, parameters,
            ReferenceMinimizationConfig(max_iterations=2), checkpoint=old.checkpoint.to_dict())
    new = minimize_reference_force_field(system, parameters,
        ReferenceMinimizationConfig(max_iterations=2), pause_after_accepted_iterations=0)
    with pytest.raises(legacy.ReferenceMinimizationError, match="algorithm"):
        legacy.minimize_reference_force_field(system, parameters,
            legacy.ReferenceMinimizationConfig(max_iterations=2), checkpoint=new.checkpoint.to_dict())


def test_frozen_historical_protocol_identity_is_unchanged():
    from betelgeuze_engine_v2.physics.reference_minimization_validation_protocol import (
        FROZEN_CPU_MINIMIZATION_VALIDATION_PROTOCOL_SHA256,
        cpu_minimization_validation_protocol_document,
        require_cpu_minimization_validation_protocol_document,
    )
    doc = cpu_minimization_validation_protocol_document()
    assert doc["protocol_sha256"] == FROZEN_CPU_MINIMIZATION_VALIDATION_PROTOCOL_SHA256
    assert require_cpu_minimization_validation_protocol_document(doc) == doc
    assert doc["claim_policy"]["scientifically_validated"] is False
