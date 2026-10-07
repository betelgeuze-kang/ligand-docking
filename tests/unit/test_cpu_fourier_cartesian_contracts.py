"""Software-only Fourier/Cartesian adapter contracts with an analytic mock.

No molecular objective, cross force, score, corpus, or docking calculation is
executed. The only objective is a three-coordinate diagonal quadratic; hard
sentinels guard the molecular evaluator entry points throughout each test.
"""

from dataclasses import replace
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from betelgeuze_engine_v2 import MolecularIntegrityError
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    Atom,
    Chain,
    Residue,
    StructureProvenance,
    canonical_system_sha256,
    canonical_topology_sha256,
)
from betelgeuze_engine_v2.physics.reference_forcefield_v2 import (
    ReferenceForceFieldV2Parameters,
)
from betelgeuze_engine_v2.physics.reference_parameters import (
    AtomNonbondedParameter,
    ReferenceForceFieldParameters,
)
from betelgeuze_product.cpu_refinement_v1_2 import evaluation as legacy_evaluation
from betelgeuze_product.cpu_refinement_v1_2 import fixed_receptor as legacy_fixed
from betelgeuze_product.cpu_refinement_v1_2.minimization import SolverConfig as LegacySolverConfig
from betelgeuze_product.cpu_refinement_v1_2.provenance import (
    ResearchError,
    coordinates_hex,
    digest,
)
from betelgeuze_product.cpu_refinement_v1_3 import minimization as execution
from betelgeuze_product.cpu_refinement_v1_3.contracts import SolverConfig
from betelgeuze_product.cpu_refinement_fourier_v1 import (
    FourierCrossParameters,
    FourierEnvironment,
    FourierFixedEvaluator,
    FourierInternalEvaluator,
    FourierParameters,
    NonbondedParameter,
)
from betelgeuze_product.cpu_refinement_fourier_v1 import cartesian


_REAL_IMPLEMENTATION_SOURCES = cartesian.implementation_sources

class ForbiddenMolecularEvaluation(BaseException):
    """Cannot be mistaken for an ordinary recoverable objective failure."""


class SimulatedInterruption(BaseException):
    """Leave an already-journaled objective reservation unfinished."""


def _forbid_molecular_evaluation(*args, **kwargs):
    raise ForbiddenMolecularEvaluation("real molecular evaluation is forbidden in this suite")


def _system(xyz, name):
    return AllAtomSystem(
        name,
        (Atom(index=0, name="C0", element="C", atomic_number=6,
              residue_index=0, partial_charge_e=0.0),),
        (),
        (Residue(index=0, name="LIG", chain_index=0, sequence_number=1,
                 atom_indices=(0,), entity_type="non_polymer", hetero=True),),
        (Chain(index=0, chain_id="L", residue_indices=(0,)),),
        torch.tensor([[xyz]], dtype=torch.float64),
        StructureProvenance(source_format="unit", source_id=name,
                            source_sha256="a" * 64, parser_name="synthetic",
                            parser_version="1"),
    )


def _inputs(algorithm="lbfgs"):
    ligand = _system([2.0, 0.25, -0.125], "mock-ligand")
    receptor = _system([0.0, 0.0, 0.0], "mock-receptor")
    model = FourierParameters(
        "synthetic-contract-only", "1", canonical_topology_sha256(ligand),
        (NonbondedParameter(0, 1.0, 0.5, 0.0),),
    )
    cross = FourierCrossParameters(
        "synthetic-cross-contract-only", "b" * 64,
        canonical_system_sha256(receptor), canonical_topology_sha256(ligand),
        model.fingerprint_sha256, "mock-frame",
        (NonbondedParameter(0, 1.0, 0.5, 0.0),),
        6.0, 4.0, 0.2, 4.0, 0.15, 2, 2.0,
    )
    config = SolverConfig(
        algorithm=algorithm, max_objective_attempts=17, max_accepted_steps=4,
        max_restart_verifications=2, max_backtracks=3,
        initial_step_size=0.03, maximum_atom_displacement=0.05,
        force_tolerance=0.001,
    )
    binding = {
        "schema_id": "cpu_prepared_fourier_cartesian_input/1.0.0",
        "candidate_id": "mock-contract-candidate",
        "prepared_protocol_sha256": "c" * 64,
        "initial_coordinates_sha256": digest(coordinates_hex(ligand.coordinates)),
    }
    return ligand, model, config, FourierEnvironment(receptor, cross), binding


@pytest.fixture(autouse=True)
def _software_only(monkeypatch):
    old_threads = torch.get_num_threads()
    torch.set_num_threads(1)
    for target, name in (
        (FourierInternalEvaluator, "evaluate"),
        (FourierEnvironment, "evaluate_cross"),
        (legacy_evaluation.ExtendedEvaluator, "evaluate"),
        (legacy_fixed.FixedReceptorEvaluator, "evaluate"),
        (legacy_fixed, "_evaluate_validated_cross_terms"),
    ):
        monkeypatch.setattr(target, name, _forbid_molecular_evaluation)
    monkeypatch.setattr(cartesian, "implementation_sources", lambda: {"mock-source.py": "d" * 64})
    yield
    torch.set_num_threads(old_threads)


@pytest.fixture
def mock_objective(monkeypatch):
    calls = SimpleNamespace(graph=[], force=[], components=0)
    graph_token = object()
    weights = torch.tensor([[[2.0, 3.0, 4.0]]], dtype=torch.float64)

    def graph(xyz, config):
        calls.graph.append(xyz.clone())
        return graph_token

    def evaluate(self, system, neighbors):
        assert neighbors is graph_token
        xyz = system.coordinates.detach().clone()
        calls.force.append(xyz)
        energy = (0.5 * weights * xyz.square()).sum().reshape(1)
        return SimpleNamespace(
            constraint_observations=(),
            term=SimpleNamespace(energy=energy, forces=-weights * xyz),
        )

    def components(evaluated):
        calls.components += 1
        energy = float(evaluated.term.energy[0])
        return {"total": energy, "ligand_internal": energy,
                "cross_lennard_jones": 0.0, "cross_screened_coulomb": 0.0}

    monkeypatch.setattr(execution, "build_compact_radius_graph", graph)
    monkeypatch.setattr(execution, "components_document", components)
    monkeypatch.setattr(FourierFixedEvaluator, "evaluate", evaluate)
    return calls


def _run(inputs, run_dir, **kwargs):
    ligand, model, config, fixed, binding = inputs
    return cartesian.minimize_cartesian(
        ligand, model, config, fixed_environment=fixed,
        run_dir=run_dir, binding=binding, **kwargs,
    )


def _verify(inputs, run_dir):
    ligand, model, config, fixed, binding = inputs
    return cartesian.verify_cartesian(
        ligand, model, config, fixed_environment=fixed,
        run_dir=run_dir, binding=binding,
    )


def _tree_bytes(path):
    return {str(item.relative_to(path)): item.read_bytes()
            for item in path.rglob("*") if item.is_file()}


@pytest.mark.parametrize("algorithm", ["sd", "lbfgs"])
def test_both_algorithms_start_at_exact_input_and_remain_bounded(tmp_path, mock_objective, algorithm):
    inputs = _inputs(algorithm)
    ligand, _, config, fixed, binding = inputs
    before_ligand = ligand.coordinates.clone()
    before_receptor = fixed.receptor.coordinates.clone()
    result = _run(inputs, tmp_path / "run")
    state = result["checkpoint"]["state"]

    assert result["schema_id"] == "cpu_prepared_fourier_cartesian_result/1.0.0"
    assert result["status"] == "max_accepted_steps_reached"
    assert result["converged"] is False
    assert result["scientifically_validated"] is False
    assert result["claim_safe"] is False
    assert result["customer_execution_allowed"] is False
    assert state["config"]["algorithm"] == algorithm
    assert state["original_coordinates"] == coordinates_hex(before_ligand)
    assert state["initial"]["coordinates"] == coordinates_hex(before_ligand)
    assert digest(state["initial"]["coordinates"]) == binding["initial_coordinates_sha256"]
    assert torch.equal(mock_objective.graph[0], before_ligand)
    assert torch.equal(mock_objective.force[0], before_ligand)
    assert torch.equal(ligand.coordinates, before_ligand)
    assert torch.equal(fixed.receptor.coordinates, before_receptor)
    assert state["accepted"] == config.max_accepted_steps
    assert state["attempts"] == 5
    assert float.fromhex(state["current"]["energy"]) < float.fromhex(state["initial"]["energy"])
    work = result["work"]
    assert work["optimizer_objective_attempts"] == work["optimizer_graph_calls"] == 5
    assert work["optimizer_force_calls"] == work["actual_force_calls"] == 5
    assert work["known_completed_force_calls"] == 5
    assert work["failed_optimizer_force_calls"] == work["restart_force_calls"] == 0
    assert work["unknown_pending_attempts"] == 0
    assert len(mock_objective.graph) == len(mock_objective.force) == mock_objective.components == 5
    assert work["actual_force_calls"] <= config.max_total_force_calls
    assert bool(state["history"]) is (algorithm == "lbfgs")


@pytest.mark.parametrize("algorithm", ["sd", "lbfgs"])
def test_resume_counts_verification_separately_and_matches_direct_state(tmp_path, mock_objective, algorithm):
    inputs = _inputs(algorithm)
    paused = _run(inputs, tmp_path / "resumed", pause_after_objective_attempts=2)
    assert paused["status"] == "checkpointed"
    assert paused["work"]["optimizer_objective_attempts"] == 2
    assert paused["work"]["restart_verification_attempts"] == 0
    resumed = _run(inputs, tmp_path / "resumed", resume=True)
    assert resumed["work"]["optimizer_objective_attempts"] == 5
    assert resumed["work"]["optimizer_force_calls"] == 5
    assert resumed["work"]["restart_verification_attempts"] == 1
    assert resumed["work"]["restart_graph_calls"] == resumed["work"]["restart_force_calls"] == 1
    assert resumed["work"]["actual_force_calls"] == resumed["work"]["known_completed_force_calls"] == 6
    assert len(mock_objective.force) == 6
    assert coordinates_hex(mock_objective.force[2]) == paused["checkpoint"]["state"]["current"]["coordinates"]
    direct = _run(inputs, tmp_path / "direct")
    assert resumed["checkpoint"]["state"] == direct["checkpoint"]["state"]


def test_cumulative_restart_allowance_does_not_reset(tmp_path, mock_objective):
    inputs = _inputs()
    run_dir = tmp_path / "run"
    _run(inputs, run_dir, pause_after_objective_attempts=1)
    once = _run(inputs, run_dir, resume=True, pause_after_objective_attempts=2)
    twice = _run(inputs, run_dir, resume=True, pause_after_objective_attempts=3)
    assert once["work"]["restart_verification_attempts"] == 1
    assert twice["work"]["restart_verification_attempts"] == 2
    assert twice["work"]["actual_force_calls"] == 5
    before = _tree_bytes(run_dir)
    count = len(mock_objective.force)
    with pytest.raises(ResearchError, match="restart.*allowance"):
        _run(inputs, run_dir, resume=True)
    assert len(mock_objective.force) == count
    assert _tree_bytes(run_dir) == before


@pytest.mark.parametrize("drift", ["model", "config", "protocol", "candidate", "coordinates", "source_system", "implementation"])
def test_identity_drift_is_rejected_before_any_resume_work(tmp_path, monkeypatch, mock_objective, drift):
    inputs = _inputs()
    run_dir = tmp_path / "run"
    _run(inputs, run_dir, pause_after_objective_attempts=2)
    ligand, model, config, fixed, binding = inputs
    if drift == "model":
        model = replace(model, parameter_set_version="2")
        fixed = replace(fixed, cross=replace(fixed.cross, ligand_base_parameters_sha256=model.fingerprint_sha256))
    elif drift == "config":
        config = replace(config, initial_step_size=0.02)
    elif drift == "protocol":
        binding = {**binding, "prepared_protocol_sha256": "e" * 64}
    elif drift == "candidate":
        binding = {**binding, "candidate_id": "another-mock-candidate"}
    elif drift == "coordinates":
        ligand = ligand.with_coordinates(ligand.coordinates + 0.001, operation="changed-input")
        binding = {**binding, "initial_coordinates_sha256": digest(coordinates_hex(ligand.coordinates))}
    elif drift == "source_system":
        ligand = replace(ligand, system_id="changed-source-identity")
    else:
        monkeypatch.setattr(cartesian, "implementation_sources", lambda: {"mock-source.py": "e" * 64})
    changed = ligand, model, config, fixed, binding
    before = _tree_bytes(run_dir)
    counts = len(mock_objective.graph), len(mock_objective.force)
    with pytest.raises(ResearchError):
        _run(changed, run_dir, resume=True)
    with pytest.raises(ResearchError):
        _verify(changed, run_dir)
    assert (len(mock_objective.graph), len(mock_objective.force)) == counts
    assert _tree_bytes(run_dir) == before


@pytest.mark.parametrize("algorithm", ["sd", "lbfgs"])
def test_terminal_verify_and_resume_do_zero_graph_or_force_work(tmp_path, monkeypatch, mock_objective, algorithm):
    inputs = _inputs(algorithm)
    run_dir = tmp_path / "run"
    result = _run(inputs, run_dir)
    before = _tree_bytes(run_dir)
    counts = len(mock_objective.graph), len(mock_objective.force), mock_objective.components
    monkeypatch.setattr(execution, "build_compact_radius_graph", _forbid_molecular_evaluation)
    monkeypatch.setattr(FourierFixedEvaluator, "evaluate", _forbid_molecular_evaluation)
    monkeypatch.setattr(execution, "components_document", _forbid_molecular_evaluation)
    assert _verify(inputs, run_dir) == result
    assert _run(inputs, run_dir, resume=True) == result
    assert (len(mock_objective.graph), len(mock_objective.force), mock_objective.components) == counts
    assert _tree_bytes(run_dir) == before


@pytest.mark.parametrize("phase", ["initial", "restart"])
def test_unknown_interrupted_work_is_retained_and_never_retried(tmp_path, monkeypatch, mock_objective, phase):
    inputs = _inputs()
    run_dir = tmp_path / "run"
    if phase == "restart":
        _run(inputs, run_dir, pause_after_objective_attempts=2)
    interrupted_calls = []

    def interrupt(*args, **kwargs):
        interrupted_calls.append(True)
        raise SimulatedInterruption("simulated interruption after durable reservation")

    monkeypatch.setattr(FourierFixedEvaluator, "evaluate", interrupt)
    with pytest.raises(SimulatedInterruption):
        _run(inputs, run_dir, resume=phase == "restart")
    events = [json.loads(line) for line in (run_dir / "events.jsonl").read_text().splitlines()]
    assert events[-1]["kind"] == ("objective_started" if phase == "initial" else "restart_started")
    before = _tree_bytes(run_dir)
    graphs = len(mock_objective.graph)
    for action in (lambda: _run(inputs, run_dir, resume=True), lambda: _verify(inputs, run_dir)):
        with pytest.raises(execution.PendingWorkError) as caught:
            action()
        assert caught.value.work["unknown_pending_attempts"] == 1
        assert caught.value.work["actual_force_calls"] is None
        assert caught.value.work["known_completed_force_calls"] == (0 if phase == "initial" else 2)
    assert interrupted_calls == [True]
    assert len(mock_objective.graph) == graphs
    assert _tree_bytes(run_dir) == before


@pytest.mark.parametrize("field,value", [
    ("max_objective_attempts", 18),
    ("max_accepted_steps", 5),
    ("max_backtracks", 4),
    ("max_restart_verifications", 3),
    ("force_tolerance", 0.0010001),
])
def test_slice_caps_reject_before_graph_or_force(tmp_path, mock_objective, field, value):
    ligand, model, config, fixed, binding = _inputs()
    with pytest.raises(ResearchError):
        _run((ligand, model, replace(config, **{field: value}), fixed, binding), tmp_path / "run")
    assert not mock_objective.graph and not mock_objective.force
    assert not (tmp_path / "run").exists()


@pytest.mark.parametrize("invalid", ["threads", "constraints"])
def test_unconstrained_single_thread_scope_is_required(tmp_path, monkeypatch, mock_objective, invalid):
    inputs = _inputs()
    if invalid == "threads":
        monkeypatch.setattr(torch, "get_num_threads", lambda: 2)
    else:
        monkeypatch.setattr(FourierParameters, "constraints", property(lambda self: (object(),)))
    with pytest.raises(ResearchError):
        _run(inputs, tmp_path / "run")
    assert not mock_objective.graph and not mock_objective.force
    assert not (tmp_path / "run").exists()


@pytest.mark.parametrize("invalid", ["schema", "missing", "extra", "coordinates", "protocol", "candidate"])
def test_explicit_exact_input_binding_is_required(tmp_path, mock_objective, invalid):
    ligand, model, config, fixed, binding = _inputs()
    binding = dict(binding)
    if invalid == "schema":
        binding["schema_id"] = "cpu_cartesian_run_binding/1.3.0"
    elif invalid == "missing":
        binding.pop("candidate_id")
    elif invalid == "extra":
        binding["unreviewed_data"] = True
    elif invalid == "coordinates":
        binding["initial_coordinates_sha256"] = "0" * 64
    elif invalid == "protocol":
        binding["prepared_protocol_sha256"] = "not-a-digest"
    else:
        binding["candidate_id"] = ""
    with pytest.raises(ResearchError):
        _run((ligand, model, config, fixed, binding), tmp_path / "run")
    assert not mock_objective.graph and not mock_objective.force
    assert not (tmp_path / "run").exists()


@pytest.mark.parametrize("legacy", ["parameters", "environment", "config", "parameter_subclass", "environment_subclass", "config_subclass"])
def test_legacy_and_structural_substitute_types_are_rejected(tmp_path, mock_objective, legacy):
    ligand, model, config, fixed, binding = _inputs()
    if legacy in {"parameters", "environment"}:
        base = ReferenceForceFieldParameters(
            "synthetic-legacy", "1", canonical_topology_sha256(ligand),
            (AtomNonbondedParameter(0, 1.0, 0.5, 0.0),),
        )
        if legacy == "parameters":
            model = ReferenceForceFieldV2Parameters(base)
        else:
            cross = legacy_fixed.CrossParameters(
                parameter_set_id="synthetic-legacy-cross", parameter_source_sha256="b" * 64,
                receptor_system_sha256=canonical_system_sha256(fixed.receptor),
                ligand_topology_sha256=canonical_topology_sha256(ligand),
                ligand_base_parameters_sha256=base.fingerprint_sha256,
                coordinate_frame_id="mock-frame", receptor_atoms=base.atom_parameters,
                cutoff_angstrom=6.0, switch_start_angstrom=4.0,
                minimum_distance_angstrom=0.2, dielectric=4.0,
                screening_kappa_per_angstrom=0.15, receptor_block_size=2,
                max_internal_increase_kcal_per_mol=2.0,
            )
            fixed = legacy_fixed.FixedReceptorEnvironment(fixed.receptor, cross)
    elif legacy == "config":
        config = LegacySolverConfig()
    elif legacy == "parameter_subclass":
        class ParameterSubclass(FourierParameters):
            pass
        model = ParameterSubclass(**{name: getattr(model, name) for name in model.__dataclass_fields__})
    elif legacy == "environment_subclass":
        class EnvironmentSubclass(FourierEnvironment):
            pass
        fixed = EnvironmentSubclass(fixed.receptor, fixed.cross)
    else:
        class ConfigSubclass(SolverConfig):
            pass
        config = ConfigSubclass(**{name: getattr(config, name) for name in config.__dataclass_fields__})
    with pytest.raises(ResearchError):
        _run((ligand, model, config, fixed, binding), tmp_path / "run")
    assert not mock_objective.graph and not mock_objective.force
    assert not (tmp_path / "run").exists()


def test_receptor_mutation_during_last_mock_objective_blocks_publication(tmp_path, monkeypatch, mock_objective):
    inputs = _inputs()
    fixed = inputs[3]
    analytic_evaluate = FourierFixedEvaluator.evaluate

    def mutate_on_last(self, system, neighbors):
        result = analytic_evaluate(self, system, neighbors)
        if len(mock_objective.force) == 5:
            fixed.receptor.coordinates[0, 0, 0] += 0.01
        return result

    monkeypatch.setattr(FourierFixedEvaluator, "evaluate", mutate_on_last)
    run_dir = tmp_path / "run"
    with pytest.raises(
        (ResearchError, MolecularIntegrityError),
        match="receptor identity|molecular system changed after construction",
    ):
        _run(inputs, run_dir)
    assert len(mock_objective.force) == 5
    assert not (run_dir / "result.json").exists()
    assert (run_dir / "events.jsonl").exists()


def test_real_source_closure_binds_cartesian_and_frozen_fourier_modules():
    sources = _REAL_IMPLEMENTATION_SOURCES()
    required = {
        "betelgeuze_product/cpu_refinement_v1_3/" + name
        for name in ("__init__.py", "contracts.py", "journal.py", "kernel.py", "minimization.py")
    }
    required.update(
        "betelgeuze_product/cpu_refinement_fourier_v1/" + name
        for name in ("cartesian.py", "evaluation.py", "parameters.py", "minimization.py")
    )
    required.add("betelgeuze_product/cpu_refinement_v1_2/fixed_receptor.py")
    assert required <= sources.keys()
    source_root = Path(cartesian.__file__).resolve().parents[2]
    for relative in sorted(required):
        path = source_root / relative
        assert path.is_file()
        assert sources[relative] == hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("entrypoint", [execution.minimize, execution.verify_run])
def test_legacy_public_entrypoints_still_reject_fourier(entrypoint, tmp_path, mock_objective):
    ligand, model, config, fixed, binding = _inputs()
    with pytest.raises(ResearchError, match="explicit Cartesian config and fixed receptor"):
        entrypoint(ligand, model, config, fixed_environment=fixed,
                   run_dir=tmp_path / "run", binding=binding)
    assert not mock_objective.graph and not mock_objective.force
    assert not (tmp_path / "run").exists()


@pytest.mark.parametrize("algorithm", ["sd", "lbfgs"])
def test_restart_rejects_changed_force_direction_with_same_energy_and_norm(
    tmp_path, monkeypatch, mock_objective, algorithm,
):
    inputs = _inputs(algorithm)
    run_dir = tmp_path / "run"
    paused = _run(inputs, run_dir, pause_after_objective_attempts=1)
    saved = paused["checkpoint"]["state"]["current"]
    analytic_evaluate = FourierFixedEvaluator.evaluate

    def changed_direction(self, system, neighbors):
        evaluated = analytic_evaluate(self, system, neighbors)
        evaluated.term.forces = -evaluated.term.forces
        return evaluated

    monkeypatch.setattr(FourierFixedEvaluator, "evaluate", changed_direction)
    with pytest.raises(ResearchError, match="restart full energy/force verification failed") as caught:
        _run(inputs, run_dir, resume=True)
    work = caught.value.work
    assert work["optimizer_objective_attempts"] == work["optimizer_force_calls"] == 1
    assert work["restart_verification_attempts"] == work["restart_force_calls"] == 1
    assert work["failed_restart_force_calls"] == 0  # Returned normally, but failed parity.
    assert work["actual_force_calls"] == work["known_completed_force_calls"] == 2
    assert work["unknown_pending_attempts"] == 0
    events = [json.loads(line) for line in (run_dir / "events.jsonl").read_text().splitlines()]
    assert [row["kind"] for row in events] == [
        "objective_started", "objective_finished", "restart_started", "restart_finished",
    ]
    receipt = events[-1]["payload"]
    observed = receipt["observation"]
    assert receipt["matched"] is False
    assert observed["coordinates"] == saved["coordinates"]
    assert observed["energy"] == saved["energy"]
    assert observed["components"] == saved["components"]
    assert observed["maximum_raw_atom_force"] == saved["maximum_raw_atom_force"]
    assert observed["forces"] != saved["forces"]
    assert receipt["state_sha256"] == digest(paused["checkpoint"]["state"])
    assert not (run_dir / "result.json").exists()
    retained = _tree_bytes(run_dir)
    count = len(mock_objective.force)
    for action in (lambda: _verify(inputs, run_dir), lambda: _run(inputs, run_dir, resume=True)):
        with pytest.raises(ResearchError, match="recorded restart energy/force verification failed") as replayed:
            action()
        assert replayed.value.work == work
        assert len(mock_objective.force) == count == 2
        assert _tree_bytes(run_dir) == retained
