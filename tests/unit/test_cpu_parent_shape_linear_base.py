"""Synthetic integration of the shape wrapper with the frozen linear-angle API.

Canonical admission objects include an exact-pi angle, but every molecular
evaluator and radius graph is replaced or forbidden. Only a declared analytic
quadratic and the shape restraint's distance arithmetic may supply forces.
These tests do not run a molecular arm or make a scientific-validation claim.
"""
from copy import deepcopy
from dataclasses import replace
import json
import math
from types import SimpleNamespace

import pytest
import torch

from betelgeuze_engine_v2 import geometry
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem, Atom, Bond, Chain, Residue, StructureProvenance,
    canonical_system_sha256, canonical_topology_sha256,
)
from betelgeuze_engine_v2.physics.reference_parameters import HarmonicBondParameter
from betelgeuze_product.cpu_refinement_fourier_v1.evaluation import (
    FourierCrossParameters, FourierEnvironment, FourierFixedEvaluator,
    FourierInternalEvaluator,
)
from betelgeuze_product.cpu_refinement_fourier_v1.parameters import (
    FourierParameters, NonbondedParameter,
)
from betelgeuze_product.cpu_refinement_linear_angle_v1 import cartesian as linear
from betelgeuze_product.cpu_refinement_linear_angle_v1 import evaluation as linear_evaluation
from betelgeuze_product.cpu_refinement_linear_angle_v1.evaluation import (
    LinearAngleEnvironment, LinearAngleFixedEvaluator, LinearAngleInternalEvaluator,
)
from betelgeuze_product.cpu_refinement_linear_angle_v1.parameters import (
    LinearAngleParameters, LinearHarmonicAngleParameter,
)
from betelgeuze_product.cpu_refinement_shape_v1 import cartesian as shape
from betelgeuze_product.cpu_refinement_shape_v1.reference import ShapeContractError
from betelgeuze_product.cpu_refinement_v1_2.provenance import (
    ResearchError, coordinates_hex, digest,
)
from betelgeuze_product.cpu_refinement_v1_3 import minimization as execution
from betelgeuze_product.cpu_refinement_v1_3.contracts import SolverConfig


def _system(xyz, name):
    count = len(xyz)
    return AllAtomSystem(
        system_id=name,
        atoms=tuple(Atom(index=i, name=f"C{i}", element="C", atomic_number=6,
                         residue_index=0, partial_charge_e=0.) for i in range(count)),
        bonds=tuple(Bond(index=i, atom_i=i, atom_j=i + 1) for i in range(count - 1)),
        residues=(Residue(index=0, name="LIG", chain_index=0, sequence_number=1,
                          atom_indices=tuple(range(count)), entity_type="non_polymer",
                          hetero=True),),
        chains=(Chain(index=0, chain_id="L", residue_indices=(0,)),),
        coordinates=torch.tensor([xyz], dtype=torch.float64),
        provenance=StructureProvenance(
            source_format="unit", source_id=name, source_sha256="a" * 64,
            parser_name="synthetic-combined-shape", parser_version="1"),
    )


def _inputs(algorithm="lbfgs"):
    # Nonzero, unequal arm lengths and exact opposite rays at atom 1. The
    # source angle is pi, never replaced by an interior Fourier angle.
    ligand = _system([[1., 0., 0.], [0., 0., 0.], [-2., 0., 0.]], "synthetic-parent")
    receptor = _system([[5., 3., 2.]], "synthetic-fixed-receptor")
    fourier = FourierParameters(
        "synthetic-combined-shape", "1", canonical_topology_sha256(ligand),
        tuple(NonbondedParameter(i, 1., 0., 0.) for i in range(3)),
        bonds=(HarmonicBondParameter(0, 1, 1., 100.),
               HarmonicBondParameter(1, 2, 2., 100.)),
        angles=(), excluded_pairs=((0, 1), (0, 2), (1, 2)),
        cutoff_angstrom=4., switch_start_angstrom=3.,
    )
    parameters = LinearAngleParameters(
        fourier, (LinearHarmonicAngleParameter(0, 1, 2, math.pi, 100.),))
    cross = FourierCrossParameters(
        "synthetic-combined-cross", "b" * 64, canonical_system_sha256(receptor),
        canonical_topology_sha256(ligand), parameters.fingerprint_sha256,
        "synthetic-frame", (NonbondedParameter(0, 1., 0., 0.),),
        7., 6., .2, 1., 0., 1, 10.,
    )
    config = SolverConfig(
        algorithm=algorithm, max_objective_attempts=17, max_accepted_steps=4,
        max_backtracks=3, max_restart_verifications=2,
        max_neighbors=8, max_atoms_per_cell=8,
    )
    binding = {
        "schema_id": linear.INPUT_SCHEMA, "candidate_id": "synthetic-combined-shape",
        "prepared_protocol_sha256": "c" * 64,
        "initial_coordinates_sha256": digest(coordinates_hex(ligand.coordinates)),
    }
    return ligand, parameters, config, LinearAngleEnvironment(receptor, cross), binding


def _forbidden(*args, **kwargs):
    pytest.fail("molecular arithmetic or an unexpected graph/force dispatch is forbidden")


@pytest.fixture(autouse=True)
def analytic_only(monkeypatch):
    previous_threads = torch.get_num_threads()
    torch.set_num_threads(1)
    calls = SimpleNamespace(graph=[], base=[], shape=[])
    graph_token = object()
    target = torch.tensor([[[1.25, .15, 0.], [.05, -.1, .1], [-1.65, .1, -.1]]],
                          dtype=torch.float64)
    weights = torch.tensor([1., 2., 3.], dtype=torch.float64).reshape(1, 3, 1)

    # The real fixed evaluator entry point is replaced below. All constituent
    # molecular routes remain hard sentinels, including a wrong-base fallback.
    for evaluator in (LinearAngleInternalEvaluator, FourierInternalEvaluator,
                      FourierFixedEvaluator):
        monkeypatch.setattr(evaluator, "evaluate", _forbidden)
    monkeypatch.setattr(FourierEnvironment, "evaluate_cross", _forbidden)
    monkeypatch.setattr(linear_evaluation, "harmonic_linear_angle_energy", _forbidden)
    monkeypatch.setattr(linear_evaluation, "_evaluate_validated_fourier_terms", _forbidden)
    monkeypatch.setattr(geometry, "build_compact_radius_graph", _forbidden)

    def graph(xyz, config):
        assert config.cutoff_angstrom == 4.
        calls.graph.append(coordinates_hex(xyz))
        return graph_token

    def analytic(self, system, neighbors):
        assert neighbors is graph_token
        assert type(self.parameters) is LinearAngleParameters
        assert self.parameters.linear_angles[0].equilibrium_radians == math.pi
        calls.base.append(coordinates_hex(system.coordinates))
        delta = system.coordinates - target
        return SimpleNamespace(
            constraint_observations=(),
            term=SimpleNamespace(energy=(.5 * weights * delta.square()).sum().reshape(1),
                                 forces=-weights * delta),
        )

    def components(evaluated):
        energy = float(evaluated.term.energy[0])
        return {"ligand_internal": energy, "cross_lennard_jones": 0.,
                "cross_screened_coulomb": 0., "total": energy}

    calculate = shape._calculate

    def tracked_shape(contract, xyz, strength, **identities):
        calls.shape.append([[float(value).hex() for value in row] for row in xyz])
        return calculate(contract, xyz, strength, **identities)

    monkeypatch.setattr(execution, "build_compact_radius_graph", graph)
    monkeypatch.setattr(LinearAngleFixedEvaluator, "evaluate", analytic)
    monkeypatch.setattr(execution, "components_document", components)
    monkeypatch.setattr(shape, "_calculate", tracked_shape)
    try:
        yield calls
    finally:
        torch.set_num_threads(previous_threads)


def _shape_run(values, path, strength, *, reference=None, verify=False, **kwargs):
    ligand, parameters, config, environment, binding = values
    if reference is None:
        reference = shape.prepare_reference(ligand, binding)
    action = shape.verify_shape if verify else shape.minimize_shape
    return action(ligand, parameters, config, fixed_environment=environment,
                  run_dir=path, binding=binding, base_profile="linear_angle",
                  reference=reference, strength=strength, **kwargs)


def _events(path):
    return [json.loads(line) for line in (path / "events.jsonl").read_text().splitlines()]


def _forbid_dispatch(monkeypatch):
    monkeypatch.setattr(execution, "build_compact_radius_graph", _forbidden)
    monkeypatch.setattr(LinearAngleFixedEvaluator, "evaluate", _forbidden)
    monkeypatch.setattr(shape, "_calculate", _forbidden)


@pytest.mark.parametrize("algorithm", ["sd", "lbfgs"])
@pytest.mark.parametrize("strength", [0., 100., 1000.])
def test_linear_base_public_run_and_dispatch_free_replay(
        tmp_path, monkeypatch, analytic_only, algorithm, strength):
    values = _inputs(algorithm)
    path = tmp_path / "shape-linear"
    result = _shape_run(values, path, strength)
    assert result["schema_id"] == shape.RESULT_SCHEMA
    assert result["checkpoint"]["schema_id"] == "cpu_parent_shape_checkpoint/1.0.0"
    assert result["status"] not in {"checkpointed", "evaluation_failed", "line_search_failed"}
    assert result["checkpoint"]["state"]["accepted"] > 0
    assert analytic_only.graph == analytic_only.base
    work = result["work"]
    assert work["optimizer_base_force_calls"] == work["optimizer_force_calls"] == len(analytic_only.base)
    assert work["optimizer_graph_calls"] == len(analytic_only.graph)
    assert work["optimizer_shape_calls"] == len(analytic_only.shape)
    assert work["optimizer_shape_calls"] == (0 if strength == 0 else len(analytic_only.base))
    assert work["optimizer_failed_base_force_calls"] == work["optimizer_failed_shape_calls"] == 0
    assert result["pose_selection_admitted"] is False
    assert result["scientifically_validated"] is False
    assert result["internal_energy_gate_basis"] == "unpenalized_ligand_internal_only"
    binding = json.loads((path / "meta.json").read_text())["binding"]
    assert binding["base_profile"] == "linear_angle"
    assert binding["base_binding"]["schema_id"] == linear.BINDING_SCHEMA
    assert binding["evaluator"]["evaluator_id"] == linear_evaluation.FIXED_ID
    assert binding["evaluator"]["parameter_fingerprint_sha256"] == values[1].fingerprint_sha256
    assert binding["shape_reference_sha256"] == shape.prepare_reference(values[0], values[4]).digest
    sources = shape.implementation_sources("linear_angle")
    for package in ("cpu_refinement_linear_angle_v1", "cpu_refinement_shape_v1"):
        assert any(key.startswith(f"betelgeuze_product/{package}/") for key in sources)
    observations = [event["payload"]["observation"] for event in _events(path)
                    if event["kind"] == "objective_finished"]
    assert float.fromhex(observations[0]["components"]["parent_shape_restraint"]) == 0.
    if strength:
        assert any(float.fromhex(row["components"]["parent_shape_restraint"]) > 0.
                   for row in observations[1:])
    _forbid_dispatch(monkeypatch)
    assert _shape_run(values, path, strength, verify=True) == result
    assert _shape_run(values, path, strength, resume=True) == result


@pytest.mark.parametrize("algorithm", ["sd", "lbfgs"])
def test_zero_matches_every_linear_base_trial_and_work_counter(
        tmp_path, monkeypatch, analytic_only, algorithm):
    values = _inputs(algorithm)
    ligand, parameters, config, environment, binding = values
    base_path, shape_path = tmp_path / "linear", tmp_path / "shape-zero"
    base = linear.minimize_cartesian(ligand, parameters, config,
        fixed_environment=environment, run_dir=base_path, binding=binding)
    base_graph, base_calls = deepcopy(analytic_only.graph), deepcopy(analytic_only.base)
    analytic_only.graph.clear()
    analytic_only.base.clear()
    monkeypatch.setattr(shape, "_calculate", _forbidden)
    wrapped = _shape_run(values, shape_path, 0.)
    assert analytic_only.graph == base_graph
    assert analytic_only.base == base_calls
    assert analytic_only.shape == []
    assert wrapped["work"]["optimizer_shape_calls"] == 0
    assert wrapped["status"] == base["status"]
    assert wrapped["converged"] == base["converged"]
    for key, value in base["work"].items():
        assert wrapped["work"][key] == value
    # Exact binary64 fields, history, line-search direction, counters and stop
    # state must match. Only the explicitly versioned wrapper is removed.
    normalized = deepcopy(wrapped["checkpoint"]["state"])
    normalized["schema_id"] = base["checkpoint"]["state"]["schema_id"]
    for key in ("initial", "current"):
        observation = normalized[key]
        assert observation["energy"] == observation["base_observation"]["energy"]
        assert observation["forces"] == observation["base_observation"]["forces"]
        normalized[key] = observation["base_observation"]
    assert normalized == base["checkpoint"]["state"]
    original, augmented = _events(base_path), _events(shape_path)
    assert len(original) == len(augmented)
    for left, right in zip(original, augmented, strict=True):
        assert left["kind"] == right["kind"]
        a, b = left["payload"], right["payload"]
        if left["kind"] == "objective_started":
            assert a == b
        else:
            assert a["observation"] == b["observation"]["base_observation"]
            for key in ("attempt", "decision", "work", "failure", "error_type"):
                assert a[key] == b[key]


@pytest.mark.parametrize("algorithm", ["sd", "lbfgs"])
@pytest.mark.parametrize("strength", [0., 100., 1000.])
def test_original_reference_and_exact_trajectory_survive_resume(
        tmp_path, monkeypatch, analytic_only, algorithm, strength):
    values = _inputs(algorithm)
    reference = shape.prepare_reference(values[0], values[4])
    original = reference.to_json()
    whole = _shape_run(values, tmp_path / "whole", strength, reference=reference)
    whole_calls = deepcopy(analytic_only.base)
    analytic_only.base.clear()
    analytic_only.graph.clear()
    analytic_only.shape.clear()
    path = tmp_path / "resumed"
    paused = _shape_run(values, path, strength, reference=reference,
                        pause_after_objective_attempts=2)
    assert paused["status"] == "checkpointed"
    assert reference.to_json() == original
    assert _shape_run(values, path, strength, reference=reference, verify=True) == paused
    before = len(analytic_only.base)
    current = paused["checkpoint"]["state"]["current"]["coordinates"]
    resumed = _shape_run(values, path, strength, reference=reference, resume=True)
    assert resumed["checkpoint"]["state"] == whole["checkpoint"]["state"]
    assert analytic_only.base == whole_calls[:before] + [current] + whole_calls[before:]
    assert analytic_only.graph == analytic_only.base
    assert analytic_only.shape == ([] if strength == 0 else analytic_only.base)
    assert resumed["work"]["restart_verification_attempts"] == 1
    assert resumed["work"]["restart_base_force_calls"] == 1
    assert resumed["work"]["restart_shape_calls"] == int(strength != 0)
    assert reference.to_json() == original
    retained = json.loads((path / "meta.json").read_text())["binding"]
    assert retained["shape_reference"] == reference.to_document()
    assert retained["shape_reference_sha256"] == reference.digest
    _forbid_dispatch(monkeypatch)
    assert _shape_run(values, path, strength, reference=reference, verify=True) == resumed


@pytest.mark.parametrize("source", ["linear", "shape"])
@pytest.mark.parametrize("verify", [False, True], ids=["resume", "replay"])
def test_source_closure_drift_rejected_before_dispatch(tmp_path, monkeypatch, source, verify):
    values = _inputs()
    path = tmp_path / "source-bound"
    _shape_run(values, path, 100., pause_after_objective_attempts=2)
    module = linear if source == "linear" else shape
    original = module.implementation_sources

    def changed_sources(*args):
        return {**original(*args), "synthetic-source-drift": "d" * 64}

    monkeypatch.setattr(module, "implementation_sources", changed_sources)
    _forbid_dispatch(monkeypatch)
    with pytest.raises(ResearchError, match="journal binding changed"):
        _shape_run(values, path, 100., verify=verify, **({} if verify else {"resume": True}))


@pytest.mark.parametrize("drift", ["source", "coordinates", "prepared_protocol"])
@pytest.mark.parametrize("verify", [False, True], ids=["resume", "replay"])
def test_reference_or_source_substitution_rejected_before_dispatch(
        tmp_path, monkeypatch, drift, verify):
    values = _inputs()
    reference = shape.prepare_reference(values[0], values[4])
    path = tmp_path / "reference-bound"
    _shape_run(values, path, 1000., reference=reference, pause_after_objective_attempts=2)
    if drift == "source":
        changed = replace(reference, source_digest="d" * 64)
    elif drift == "coordinates":
        changed = replace(reference, coordinates=((1.1, 0., 0.), (0., 0., 0.), (-2., 0., 0.)))
    else:
        # A self-consistent new protocol/reference still cannot inherit the
        # existing journal's source identity.
        values = (*values[:4], {**values[4], "prepared_protocol_sha256": "d" * 64})
        changed = shape.prepare_reference(values[0], values[4])
    _forbid_dispatch(monkeypatch)
    with pytest.raises((ResearchError, ShapeContractError)):
        _shape_run(values, path, 1000., reference=changed, verify=verify,
                   **({} if verify else {"resume": True}))
