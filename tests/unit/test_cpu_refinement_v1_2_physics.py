"""Independent angle forces, extended terms, constraints and versioned restarts."""
from __future__ import annotations

from dataclasses import asdict, replace
import math

import pytest
import torch

from betelgeuze_engine_v2.geometry import RadiusGraphConfig, build_compact_radius_graph
from betelgeuze_engine_v2.physics.reference_forcefield_v2 import (
    DistanceConstraintParameter, ReferenceForceFieldV2Parameters,
)
from betelgeuze_engine_v2.physics.reference_solvation import (
    FixedBornAtomParameter, FixedBornPolarSolvationParameters,
    evaluate_fixed_born_polar_solvation,
)
from betelgeuze_product.cpu_refinement.reference_minimization_v1_1 import ReferenceMinimizationConfig
from betelgeuze_product.cpu_refinement_v1_2.evaluation import ExtendedEvaluator
from betelgeuze_product.cpu_refinement_v1_2.minimization import (
    SolverConfig, minimize_extended, require_checkpoint,
)
from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError, digest
from tests.unit.test_engine_v2_reference_angle_boundary import angle_system
from tests.unit.test_engine_v2_reference_forcefield_v2 import (
    _star_system, _star_v2_parameters, _neighbors,
)
from tests.unit.test_engine_v2_reference_constrained_minimization import (
    _angle_system, _angle_parameters, _angle_solvation_parameters, _config,
)


def near_linear(*, constrained=True, charged=False):
    system, base = angle_system(math.pi - 1.e-7)
    if charged:
        base = replace(base, atom_parameters=tuple(
            replace(row, charge_e=charge) for row, charge in zip(base.atom_parameters, (.2, -.4, .2), strict=True)))
    constraints = ((DistanceConstraintParameter(0, 1, 1., tolerance_angstrom=1.e-10),
                    DistanceConstraintParameter(1, 2, 1., tolerance_angstrom=1.e-10))
                   if constrained else ())
    parameters = ReferenceForceFieldV2Parameters(base, constraints=constraints)
    solvation = FixedBornPolarSolvationParameters(
        parameter_set_id="synthetic-1.2", parameter_set_version="1", parameter_source_sha256="b" * 64,
        topology_sha256=parameters.topology_sha256,
        charge_parameter_fingerprint_sha256=parameters.fingerprint_sha256,
        atom_parameters=tuple(FixedBornAtomParameter(i, 1.5 + .1 * i) for i in range(3)))
    config = SolverConfig(minimization=ReferenceMinimizationConfig(
        max_iterations=3, max_neighbors=4, max_atoms_per_cell=4))
    return system, parameters, solvation, config


def evaluate(system, parameters, solvation=None):
    neighbors = build_compact_radius_graph(system.coordinates, RadiusGraphConfig(
        cutoff_angstrom=parameters.base_parameters.cutoff_angstrom, max_neighbors=16, max_atoms_per_cell=16))
    return ExtendedEvaluator(parameters, solvation).evaluate(system, neighbors)


@pytest.mark.parametrize("constrained", [False, True])
@pytest.mark.parametrize("solvated", [False, True])
def test_near_linear_angle_correct_in_every_new_path(constrained, solvated):
    system, parameters, solvent, config = near_linear(constrained=constrained)
    solvent = solvent if solvated else None
    result = evaluate(system, parameters, solvent)
    maximum = float(torch.linalg.vector_norm(result.term.forces, dim=-1).max())
    delta = math.pi - 1.e-7 - math.pi / 2
    assert maximum == pytest.approx(200 * delta * math.cos(.5e-7), rel=1.e-12)
    run = minimize_extended(system, parameters, config, solvation=solvent)
    doc = run.checkpoint.to_dict()
    assert doc["accepted_iterations"] > 0
    assert doc["current_energy"] < doc["initial_energy"]
    assert doc["initial_max_tangent_force"] > 300
    assert evaluate(run.system, parameters, solvent).constraints_satisfied
    assert not run.to_dict()["scientifically_validated"]


@pytest.mark.parametrize("charged", [False, True])
def test_fixed_born_added_to_corrected_base_not_legacy(charged):
    system, parameters, solvent, _ = near_linear(charged=charged)
    dry = evaluate(system, parameters)
    wet = evaluate(system, parameters, solvent)
    gb = evaluate_fixed_born_polar_solvation(system, parameters, solvent)
    torch.testing.assert_close(wet.term.energy, dry.term.energy + gb.term.energy, rtol=0, atol=0)
    torch.testing.assert_close(wet.term.forces, dry.term.forces + gb.term.forces, rtol=0, atol=0)
    assert not wet.term.validated_for_composition


@pytest.mark.parametrize("solvated", [False, True])
def test_improper_and_optional_solvation_force_match_finite_difference(solvated):
    system = _star_system()
    parameters = _star_v2_parameters(system)
    solvent = None
    if solvated:
        solvent = FixedBornPolarSolvationParameters(
            parameter_set_id="star-gb", parameter_set_version="1", parameter_source_sha256="c" * 64,
            topology_sha256=parameters.topology_sha256,
            charge_parameter_fingerprint_sha256=parameters.fingerprint_sha256,
            atom_parameters=tuple(FixedBornAtomParameter(i, 1.5) for i in range(4)))
    original = evaluate(system, parameters, solvent)
    step = 1.e-6
    for atom in range(4):
        for axis in range(3):
            left, right = system.coordinates.clone(), system.coordinates.clone()
            left[0, atom, axis] -= step
            right[0, atom, axis] += step
            ep = evaluate(system.with_coordinates(right, operation="fd+"), parameters, solvent).term.energy.item()
            em = evaluate(system.with_coordinates(left, operation="fd-"), parameters, solvent).term.energy.item()
            assert original.term.forces[0, atom, axis].item() == pytest.approx(-(ep-em)/(2*step), rel=2.e-5, abs=2.e-5)


def test_rigid_transform_covariance_and_balance():
    system = _star_system()
    parameters = _star_v2_parameters(system)
    old = evaluate(system, parameters)
    rotation = torch.tensor([[.36, -.48, .8], [.8, .6, 0.], [-.48, .64, .6]], dtype=torch.float64)
    moved = system.with_coordinates(system.coordinates @ rotation.T + .25, operation="rigid")
    new = evaluate(moved, parameters)
    torch.testing.assert_close(old.term.energy, new.term.energy, rtol=1.e-11, atol=1.e-11)
    torch.testing.assert_close(old.term.forces @ rotation.T, new.term.forces, rtol=1.e-9, atol=1.e-9)
    torch.testing.assert_close(new.term.forces.sum(dim=1), torch.zeros((1, 3), dtype=torch.float64), rtol=0, atol=1.e-10)


@pytest.mark.parametrize("solvated", [False, True])
@pytest.mark.parametrize("pause_at", [0, 1, 2])
def test_restart_is_bit_exact_but_invocation_work_is_separate(solvated, pause_at):
    system, parameters, solvent, config = near_linear(charged=solvated)
    solvent = solvent if solvated else None
    full = minimize_extended(system, parameters, config, solvation=solvent)
    paused = minimize_extended(system, parameters, config, solvation=solvent,
                               pause_after_accepted_iterations=pause_at)
    resumed = minimize_extended(system, parameters, config, solvation=solvent, checkpoint=paused.checkpoint)
    assert full.checkpoint.to_dict() == resumed.checkpoint.to_dict()
    assert paused.execution["force_evaluation_calls"] + resumed.execution["force_evaluation_calls"] == full.execution["force_evaluation_calls"] + 1
    assert resumed.execution["restart_verification_calls"] == 1


def test_normal_constrained_solvated_case_converges_and_preserves_distances():
    system = _angle_system()
    parameters = _angle_parameters(system, charges=(.2, -.4, .2))
    solvent = _angle_solvation_parameters(system, parameters)
    old = _config(max_iterations=60)
    config = SolverConfig(ReferenceMinimizationConfig(**asdict(old.minimization)),
        old.constraint_projection, old.force_projection_max_sweeps,
        old.force_projection_tolerance_kcal_per_mol_angstrom)
    result = minimize_extended(system, parameters, config, solvation=solvent)
    assert result.converged
    assert result.checkpoint.to_dict()["current_constraint_residual"] <= 1.e-10


@pytest.mark.parametrize("change", ["algorithm", "coordinate", "summary", "count", "row", "trial", "status", "extra", "boolean", "step"])
def test_rehashed_malformed_checkpoints_rejected(change):
    system, parameters, _, config = near_linear()
    doc = minimize_extended(system, parameters, config, pause_after_accepted_iterations=1).checkpoint.to_dict()
    if change == "algorithm":
        doc["algorithm_id"] = "legacy/1.0.0"
    elif change == "coordinate":
        doc["coordinates"][0][0] = (99.).hex()
    elif change == "summary":
        doc["current_energy"] += 1
    elif change == "count":
        doc["evaluation_count"] += 1
    elif change == "row":
        doc["observations"][1]["iteration"] = 2
    elif change == "trial":
        doc["observations"][1]["trial"] = 1
    elif change == "status":
        doc["status"] = "converged"
    elif change == "step":
        doc["observations"][1]["step"] *= 2
    elif change == "extra":
        doc["extra"] = "not canonical"
    else:
        doc["accepted_iterations"] = True
    doc["checkpoint_sha256"] = digest({k: v for k, v in doc.items() if k != "checkpoint_sha256"})
    with pytest.raises(ResearchError):
        require_checkpoint(doc)


@pytest.mark.parametrize("change", ["parameter", "solvent", "environment", "source", "config", "implementation"])
def test_restart_identity_crosswiring_rejected(change):
    system, parameters, solvent, config = near_linear()
    doc = minimize_extended(system, parameters, config, solvation=solvent,
                            pause_after_accepted_iterations=1).checkpoint.to_dict()
    if change == "parameter":
        parameters = replace(parameters, metadata={"new": True})
        solvent = replace(solvent, charge_parameter_fingerprint_sha256=parameters.fingerprint_sha256)
    elif change == "solvent":
        solvent = replace(solvent, solvent_dielectric=70.)
    elif change == "source":
        system = system.with_coordinates(system.coordinates + .1, operation="changed")
    elif change == "config":
        config = replace(config, minimization=replace(config.minimization, max_iterations=4))
    elif change == "environment":
        doc["environment"]["torch"] = "different"
    else:
        doc["implementation_sha256"] = "a" * 64
    doc["checkpoint_sha256"] = digest({k: v for k, v in doc.items() if k != "checkpoint_sha256"})
    with pytest.raises(ResearchError, match="identity mismatch"):
        minimize_extended(system, parameters, config, solvation=solvent, checkpoint=doc)


def test_checkpoint_document_cannot_mutate_result():
    system, parameters, _, config = near_linear()
    result = minimize_extended(system, parameters, config)
    first = result.checkpoint.to_dict()
    other = result.checkpoint.to_dict()
    other["coordinates"][0][0] = "bad"
    assert result.checkpoint.to_dict() == first


def test_actual_old_checkpoint_rejected_without_relabeling():
    from betelgeuze_product.cpu_refinement.reference_minimization_v1_1 import minimize_reference_force_field
    system, parameters, _, config = near_linear(constrained=False)
    old = minimize_reference_force_field(system, parameters.base_parameters, config.minimization)
    with pytest.raises(ResearchError):
        minimize_extended(system, parameters, config, checkpoint=old.checkpoint.to_dict())


@pytest.mark.parametrize("change", ["singular", "float32", "stale_neighbors", "solvation_identity"])
def test_invalid_evaluation_fails_closed(change):
    system, parameters, solvent, _ = near_linear()
    if change == "singular":
        xyz = system.coordinates.clone()
        xyz[0, 2] = torch.tensor([-1., 0., 0.])
        system = system.with_coordinates(xyz, operation="singular")
    elif change == "float32":
        system = system.with_coordinates(system.coordinates.float(), operation="float32")
    elif change == "solvation_identity":
        solvent = replace(solvent, charge_parameter_fingerprint_sha256="0" * 64)
    if change == "stale_neighbors":
        neighbors = _neighbors(system)
        system = system.with_coordinates(system.coordinates + .1, operation="stale")
        with pytest.raises(Exception, match="stale|coordinate|current"):
            ExtendedEvaluator(parameters).evaluate(system, neighbors)
    else:
        with pytest.raises(Exception):
            evaluate(system, parameters, solvent)


def test_source_drift_does_not_publish_checkpoint(monkeypatch):
    from betelgeuze_product.cpu_refinement_v1_2 import minimization as module
    system, parameters, _, config = near_linear()
    real = module.source_manifest
    calls = 0
    def manifest():
        nonlocal calls
        calls += 1
        result = real()
        if calls > 1:
            result["changed.py"] = "0" * 64
        return result
    monkeypatch.setattr(module, "source_manifest", manifest)
    with pytest.raises(ResearchError, match="changed during execution"):
        minimize_extended(system, parameters, config)
