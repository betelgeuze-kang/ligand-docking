"""D2: bit-identical call-local geometry and independent tangent checks."""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest
import torch

from betelgeuze_engine_v2.molecular import UnitCell
from betelgeuze_engine_v2.physics.reference_constrained_minimization import (
    _project_forces_to_constraint_tangent as historical,
    ReferenceConstrainedMinimizationError,
)
from betelgeuze_engine_v2.physics.reference_forcefield_v2 import DistanceConstraintParameter
from betelgeuze_product.cpu_refinement_v1_2 import tangent_projection as module
from betelgeuze_product.cpu_refinement_v1_2.minimization import SolverConfig, minimize_extended
from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError
from tests.unit.test_engine_v2_reference_forcefield_v2 import _star_system, _star_v2_parameters
from tests.unit.test_cpu_refinement_v1_2_physics import near_linear


def fixture(seed=0, periodic=False):
    generator = torch.Generator().manual_seed(91000 + seed)
    system = _star_system()
    xyz = system.coordinates + .08 * torch.rand(system.coordinates.shape, generator=generator, dtype=torch.float64)
    if periodic:
        xyz[0, 1, 0] += 8.
        system = replace(system, cell=UnitCell(vectors=torch.eye(3, dtype=torch.float64) * 8.))
    system = system.with_coordinates(xyz, operation="test_projection")
    params = replace(_star_v2_parameters(_star_system()), constraints=tuple(
        DistanceConstraintParameter(0, j, 1.) for j in (1, 2, 3)))
    forces = 40 * torch.rand(xyz.shape, generator=generator, dtype=torch.float64) - 20
    return system, params, forces


@pytest.mark.parametrize("seed", range(12))
@pytest.mark.parametrize("sweeps", [1, 100, 200])
@pytest.mark.parametrize("periodic", [False, True])
def test_exact_historical_tensor_residual_sweeps_and_status(seed, sweeps, periodic):
    system, params, forces = fixture(seed, periodic)
    config = SolverConfig(force_projection_max_sweeps=sweeps)
    before = forces.clone(), system.coordinates.clone()
    expected = historical(system, system.coordinates, forces, params, config)
    actual = module.project_tangent_forces(system, system.coordinates, forces, params, config)
    assert torch.equal(expected[0], actual[0])
    assert expected[1:] == actual[1:]
    assert torch.equal(forces, before[0]) and torch.equal(system.coordinates, before[1])


def test_geometry_built_once_per_constraint_and_rebuilt_for_new_coordinates(monkeypatch):
    system, params, forces = fixture()
    real = module._constraint_vector
    calls = 0
    def vector(*args):
        nonlocal calls
        calls += 1
        return real(*args)
    monkeypatch.setattr(module, "_constraint_vector", vector)
    config = SolverConfig(force_projection_max_sweeps=200)
    first = module.project_tangent_forces(system, system.coordinates, forces, params, config)
    assert first[3] > 1 and calls == len(params.constraints)
    xyz = system.coordinates.clone()
    xyz[0, 1, 1] += .5
    second = module.project_tangent_forces(system, xyz, forces, params, config)
    assert calls == 2 * len(params.constraints)
    reference = historical(system, xyz, forces, params, config)
    assert torch.equal(second[0], reference[0])
    assert not torch.equal(first[0], second[0])


@pytest.mark.parametrize("constrained", [False, True])
def test_nearly_linear_and_zero_force_parity(constrained):
    system, params, _, config = near_linear(constrained=constrained)
    for force in (torch.zeros_like(system.coordinates), torch.ones_like(system.coordinates)):
        old = historical(system, system.coordinates, force, params, config)
        new = module.project_tangent_forces(system, system.coordinates, force, params, config)
        assert torch.equal(old[0], new[0]) and old[1:] == new[1:]


def test_zero_distance_rejected_like_historical():
    system, params, force = fixture()
    xyz = system.coordinates.clone()
    xyz[0, 1] = xyz[0, 0]
    for implementation in (historical, module.project_tangent_forces):
        with pytest.raises(ReferenceConstrainedMinimizationError, match="zero pair distance"):
            implementation(system, xyz, force, params, SolverConfig())


@pytest.mark.parametrize("kind", ["float32", "nan", "inf", "shape", "boolean_sweeps"])
def test_bad_projection_input_is_not_silently_accepted(kind):
    system, params, force = fixture()
    config = SolverConfig()
    if kind == "float32":
        force = force.float()
    elif kind == "nan":
        force[0, 0, 0] = float("nan")
    elif kind == "inf":
        force[0, 0, 0] = float("inf")
    elif kind == "shape":
        force = force[0]
    else:
        config = SimpleNamespace(force_projection_max_sweeps=True,
                                 force_projection_tolerance_kcal_per_mol_angstrom=1.e-8)
    with pytest.raises(ResearchError):
        module.project_tangent_forces(system, system.coordinates, force, params, config)


def test_independent_svd_reference_with_redundant_collinear_constraints():
    system, params, force = fixture()
    xyz = torch.tensor([[[0., 0., 0.], [1., 0., 0.], [2., 0., 0.], [3., 0., 0.]]], dtype=torch.float64)
    params = replace(params, constraints=tuple(
        DistanceConstraintParameter(i, j, float(j-i)) for i, j in ((0, 1), (0, 2), (1, 2), (2, 3))))
    rows = []
    for c in params.constraints:
        direction = xyz[0, c.atom_i] - xyz[0, c.atom_j]
        direction = direction / torch.linalg.vector_norm(direction)
        row = torch.zeros(12, dtype=torch.float64)
        row[3*c.atom_i:3*c.atom_i+3] = direction
        row[3*c.atom_j:3*c.atom_j+3] = -direction
        rows.append(row)
    jacobian = torch.stack(rows)
    # Independent rank-revealing orthogonal projection; not a runtime fallback.
    _, singular, vh = torch.linalg.svd(jacobian, full_matrices=False)
    rank = int((singular > singular[0] * 1.e-12).sum())
    basis = vh[:rank]
    expected = force.reshape(-1) - basis.T @ (basis @ force.reshape(-1))
    result = module.project_tangent_forces(system, xyz, force, params,
                                          SolverConfig(force_projection_max_sweeps=500))
    assert result[4]
    assert float((jacobian @ result[0].reshape(-1)).abs().max()) <= 1.e-8
    torch.testing.assert_close(result[0].reshape(-1), expected, atol=5.e-8, rtol=0.)
    assert rank < jacobian.shape[0]


def test_exhaustion_is_visible_without_relaxing_tolerance():
    system, params, force = fixture(3)
    short = module.project_tangent_forces(system, system.coordinates, force, params,
                                         SolverConfig(force_projection_max_sweeps=1))
    long = module.project_tangent_forces(system, system.coordinates, force, params,
                                        SolverConfig(force_projection_max_sweeps=200))
    assert not short[4] and short[3] == 1
    assert long[4] and long[2] <= 1.e-8


def test_actual_solver_observes_sweep_work_and_replays_checkpoint():
    system, params, solvent, config = near_linear(charged=True)
    full = minimize_extended(system, params, config, solvation=solvent)
    paused = minimize_extended(system, params, config, solvation=solvent, pause_after_accepted_iterations=1)
    resumed = minimize_extended(system, params, config, solvation=solvent, checkpoint=paused.checkpoint)
    assert full.checkpoint.to_dict() == resumed.checkpoint.to_dict()
    for run in (full, paused, resumed):
        work = run.execution["work"]
        counts = work["counters"]
        assert counts["tangent_projection_sweeps"] > 0
        assert counts["tangent_projection_completed"] + counts["tangent_projection_exhausted"] == work["stages"]["force.project"]["completed"]
    assert "tangent_projection_sweeps" not in str(full.checkpoint.to_dict())


@pytest.mark.parametrize("solvated", [False, True])
def test_complete_solver_numerical_ledger_matches_historical_projection(monkeypatch, solvated):
    from betelgeuze_product.cpu_refinement_v1_2 import minimization
    system, params, solvent, config = near_linear(charged=solvated)
    optimized = minimize_extended(system, params, config, solvation=solvent if solvated else None)
    # Test-only substitution; source identities are not migrated or changed.
    monkeypatch.setattr(minimization, "_project_forces_to_constraint_tangent", historical)
    reference = minimize_extended(system, params, config, solvation=solvent if solvated else None)
    assert optimized.checkpoint.to_dict() == reference.checkpoint.to_dict()
    assert optimized.execution["work"]["counters"] == reference.execution["work"]["counters"]
