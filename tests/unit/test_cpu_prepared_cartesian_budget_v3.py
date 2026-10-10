"""Bounded adapter contracts using real, explicitly synthetic molecular inputs.

Longer execution is development coverage, not evidence of docking accuracy,
force-field validation, source authentication, or customer readiness.
"""
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest
import torch

from betelgeuze_engine_v2.physics.reference_forcefield import ReferencePhysicsApplicabilityError
from betelgeuze_product.cpu_prepared_cartesian_budget_v3 import workflow
from betelgeuze_product.cpu_refinement_fourier_v1 import cartesian as fourier
from betelgeuze_product.cpu_refinement_fourier_v1.evaluation import FourierFixedEvaluator
from betelgeuze_product.cpu_refinement_linear_angle_v1 import cartesian as linear
from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError, canonical
from betelgeuze_product.cpu_refinement_v1_3 import minimization as execution
from tests.unit.test_cpu_parent_shape_cartesian import inputs as fourier_inputs
from tests.unit.test_cpu_parent_shape_linear_base import _inputs as linear_inputs
from tests.unit.test_cpu_refinement_fourier_v1_workflow import protocol as source_protocol


@pytest.fixture(autouse=True)
def single_cpu_thread():
    previous = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(previous)


def _arguments(tmp_path, *, algorithm="sd", accepted_steps=40, restart_verifications=0):
    source = source_protocol(tmp_path)
    return {
        "model": "fourier", "accepted_steps": accepted_steps,
        "restart_verifications": restart_verifications,
        "candidate_id": source["candidate_id"], "evidence_kind": source["evidence_kind"],
        **{name: source[name]["path"] for name in workflow.REFS},
        "solver": workflow.budget_config(
            algorithm, accepted_steps, restart_verifications=restart_verifications),
        "output": tmp_path / "prepared.json",
    }


def _prepared(tmp_path, **options):
    arguments = _arguments(tmp_path, **options)
    sealed = workflow.prepare(**arguments)
    selection = {name: arguments[name]
                 for name in ("model", "accepted_steps", "restart_verifications")}
    return sealed, selection


def _call(action, sealed, selection, directory=None, **options):
    arguments = [sealed["protocol_path"], sealed["protocol_sha256"]]
    if directory is not None:
        arguments.append(directory)
    return action(*arguments, **{**selection, **options})


def _files(directory):
    return {path.relative_to(directory).as_posix(): path.read_bytes()
            for path in directory.rglob("*") if path.is_file()}


def _write_json(path, document):
    raw = (canonical(document) + "\n").encode("ascii")
    Path(path).write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def _forbidden(*args, **kwargs):
    pytest.fail("unexpected numerical work during admission or replay")


def _forbid_numerical_work(monkeypatch):
    monkeypatch.setattr(execution, "_invoke", _forbidden)
    monkeypatch.setattr(execution, "build_compact_radius_graph", _forbidden)
    monkeypatch.setattr(FourierFixedEvaluator, "evaluate", _forbidden)


@pytest.mark.parametrize("algorithm", ["sd", "lbfgs"])
@pytest.mark.parametrize("accepted_steps,objective_attempts", [(40, 161), (80, 321), (160, 641)])
@pytest.mark.parametrize("restart_verifications", [0, 1])
def test_frozen_budget_and_force_free_admission(
        tmp_path, monkeypatch, algorithm, accepted_steps, objective_attempts,
        restart_verifications):
    _forbid_numerical_work(monkeypatch)
    sealed, selection = _prepared(tmp_path, algorithm=algorithm, accepted_steps=accepted_steps,
                                  restart_verifications=restart_verifications)
    prepared = json.loads(Path(sealed["protocol_path"]).read_bytes())
    assert prepared["schema_version"] == workflow.PROTOCOL
    assert prepared["profile_id"] == workflow.PROFILE_ID
    assert workflow.PROFILE_ID.endswith("/3.0.0")
    result = _call(workflow.preflight, sealed, selection)
    assert result == sealed["preflight"]
    assert result["status"] == "admitted_for_bounded_development_execution"
    config = result["solver"]
    assert config["algorithm"] == algorithm
    assert config["max_accepted_steps"] == accepted_steps
    assert config["max_objective_attempts"] == objective_attempts
    assert config["max_restart_verifications"] == restart_verifications
    assert config["max_backtracks"] == 3
    assert config["initial_step_size"] == .001
    assert config["maximum_atom_displacement"] == .05
    assert config["force_tolerance"] == .001
    assert result["geometry"]["force_calls"] == 0
    assert result["geometry"]["energy_calls"] == 0
    assert result["boundary"] == workflow.BOUNDARY
    assert result["coordinate_frame_authenticity_verified"] is False


@pytest.mark.parametrize("accepted_steps", [True, False, 40.0, "40", None, 4, 39, 41, 0, 320])
def test_noncanonical_step_budgets_are_rejected(accepted_steps):
    with pytest.raises(ResearchError):
        workflow.budget_config("sd", accepted_steps, restart_verifications=0)


@pytest.mark.parametrize("restart_verifications", [True, False, 0.0, 1.0, "1", None, -1, 2])
def test_restart_budget_requires_exact_zero_or_one(restart_verifications):
    with pytest.raises(ResearchError):
        workflow.budget_config("sd", 40, restart_verifications=restart_verifications)


@pytest.mark.parametrize("algorithm", [None, True, 1, "SD", "shape", "fire"])
def test_algorithm_must_be_explicit_supported_cartesian_name(algorithm):
    with pytest.raises(ResearchError):
        workflow.budget_config(algorithm, 40, restart_verifications=0)


def test_restart_selection_is_required_on_every_public_entrypoint(tmp_path):
    with pytest.raises(TypeError):
        workflow.budget_config("sd", 40)
    arguments = _arguments(tmp_path)
    arguments.pop("restart_verifications")
    with pytest.raises(TypeError):
        workflow.prepare(**arguments)
    assert not arguments["output"].exists()
    sealed, selection = _prepared(tmp_path)
    selection.pop("restart_verifications")
    for action in (workflow.preflight, workflow.run, workflow.verify):
        with pytest.raises(TypeError):
            _call(action, sealed, selection,
                  None if action is workflow.preflight else tmp_path / "never-created")
    assert not (tmp_path / "never-created").exists()


@pytest.mark.parametrize("field,value", [
    ("max_accepted_steps", 41), ("max_objective_attempts", 160),
    ("max_restart_verifications", 1), ("max_backtracks", 4),
    ("initial_step_size", .002), ("maximum_atom_displacement", .1),
    ("force_tolerance", .002), ("history_size", 9),
    ("max_neighbors", 255), ("max_atoms_per_cell", 255),
])
def test_prepare_rejects_nonfrozen_controls_before_publication(tmp_path, field, value):
    arguments = _arguments(tmp_path)
    arguments["solver"] = replace(arguments["solver"], **{field: value})
    with pytest.raises(ResearchError):
        workflow.prepare(**arguments)
    assert not arguments["output"].exists()


@pytest.mark.parametrize("selection_change", [
    {"model": "linear_angle"}, {"model": "shape"}, {"model": "fourier_shape"},
    {"model": None}, {"accepted_steps": 80}, {"accepted_steps": 40.0},
    {"restart_verifications": 1}, {"restart_verifications": False},
])
def test_selection_must_match_protocol_before_any_work(tmp_path, monkeypatch, selection_change):
    sealed, selection = _prepared(tmp_path)
    _forbid_numerical_work(monkeypatch)
    for action in (workflow.preflight, workflow.run, workflow.verify):
        with pytest.raises(ResearchError):
            _call(action, sealed, selection,
                  None if action is workflow.preflight else tmp_path / "never-created",
                  **selection_change)
    assert not (tmp_path / "never-created").exists()


@pytest.mark.parametrize("model", ["shape", "fourier_shape", "linear_angle_shape", None, True])
def test_shape_or_implicit_model_cannot_be_prepared(tmp_path, model):
    arguments = _arguments(tmp_path)
    arguments["model"] = model
    with pytest.raises(ResearchError):
        workflow.prepare(**arguments)
    assert not arguments["output"].exists()


@pytest.mark.parametrize("model", ["fourier", "linear_angle"])
def test_existing_four_step_wrappers_still_reject_long_budget(tmp_path, model):
    wrapper = fourier if model == "fourier" else linear
    ligand, parameters, _, fixed, binding = (fourier_inputs() if model == "fourier"
                                            else linear_inputs())
    config = workflow.budget_config("sd", 40, restart_verifications=1)
    with pytest.raises(ResearchError, match="bounded"):
        wrapper.minimize_cartesian(ligand, parameters, config, fixed_environment=fixed,
                                   binding=binding, run_dir=tmp_path / "never-created")
    assert not (tmp_path / "never-created").exists()


@pytest.mark.parametrize("algorithm", ["sd", "lbfgs"])
def test_real_synthetic_run_exceeds_four_steps_and_terminal_replay_is_zero_work(
        tmp_path, monkeypatch, algorithm):
    sealed, selection = _prepared(tmp_path, algorithm=algorithm)
    directory = tmp_path / "run"
    result = _call(workflow.run, sealed, selection, directory)
    assert result["schema_id"] == workflow.RESULT_SCHEMA
    assert result["status"] != "checkpointed"
    state, work = result["checkpoint"]["state"], result["work"]
    assert 4 < state["accepted"] <= 40
    assert 5 < work["optimizer_objective_attempts"] <= 161
    assert work["restart_verification_attempts"] == 0
    assert work["actual_force_calls"] == work["optimizer_force_calls"]
    assert work["actual_force_calls"] <= work["max_total_force_calls"] == 161
    assert result["scientifically_validated"] is False
    assert result["claim_safe"] is False
    assert result["customer_execution_allowed"] is False
    if algorithm == "sd":
        assert state["accepted"] == 40
        assert result["status"] == "max_accepted_steps_reached"
        assert result["converged"] is False
    before = _files(directory)
    _forbid_numerical_work(monkeypatch)
    assert _call(workflow.verify, sealed, selection, directory) == result
    assert _call(workflow.run, sealed, selection, directory, resume=True) == result
    assert _files(directory) == before


def test_safe_pause_resume_performs_exactly_one_separate_restart_verification(tmp_path, monkeypatch):
    sealed, selection = _prepared(tmp_path, restart_verifications=1)
    directory = tmp_path / "run"
    paused = _call(workflow.run, sealed, selection, directory, pause_after_objective_attempts=6)
    assert paused["status"] == "checkpointed"
    assert paused["checkpoint"]["state"]["accepted"] == 5
    assert paused["work"]["optimizer_objective_attempts"] == 6
    assert paused["work"]["restart_verification_attempts"] == 0
    before = _files(directory)
    with monkeypatch.context() as patch:
        _forbid_numerical_work(patch)
        assert _call(workflow.verify, sealed, selection, directory) == paused
        assert _call(workflow.run, sealed, selection, directory, resume=True,
                     pause_after_objective_attempts=6) == paused
    assert _files(directory) == before
    result = _call(workflow.run, sealed, selection, directory, resume=True)
    assert result["work"]["optimizer_objective_attempts"] == 41
    assert result["work"]["restart_verification_attempts"] == 1
    assert result["work"]["restart_graph_calls"] == 1
    assert result["work"]["restart_force_calls"] == 1
    assert result["work"]["actual_force_calls"] == 42
    assert result["work"]["max_total_force_calls"] == 162
    assert result["checkpoint"]["state"]["accepted"] == 40
    events = [json.loads(line) for line in (directory / "events.jsonl").read_text().splitlines()]
    assert sum(event["kind"] == "restart_started" for event in events) == 1
    assert sum(event["kind"] == "restart_finished" for event in events) == 1
    _forbid_numerical_work(monkeypatch)
    before = _files(directory)
    assert _call(workflow.verify, sealed, selection, directory) == result
    assert _call(workflow.run, sealed, selection, directory, resume=True) == result
    assert _files(directory) == before


def test_zero_restart_allowance_rejects_actual_continuation_without_work(tmp_path, monkeypatch):
    sealed, selection = _prepared(tmp_path)
    directory = tmp_path / "run"
    paused = _call(workflow.run, sealed, selection, directory, pause_after_objective_attempts=2)
    before = _files(directory)
    _forbid_numerical_work(monkeypatch)
    assert _call(workflow.verify, sealed, selection, directory) == paused
    with pytest.raises(ResearchError, match="restart.*allowance"):
        _call(workflow.run, sealed, selection, directory, resume=True)
    assert _files(directory) == before


def test_restart_allowance_is_cumulative_not_per_invocation(tmp_path, monkeypatch):
    sealed, selection = _prepared(tmp_path, restart_verifications=1)
    directory = tmp_path / "run"
    _call(workflow.run, sealed, selection, directory, pause_after_objective_attempts=2)
    paused = _call(workflow.run, sealed, selection, directory, resume=True,
                   pause_after_objective_attempts=3)
    assert paused["work"]["restart_verification_attempts"] == 1
    before = _files(directory)
    _forbid_numerical_work(monkeypatch)
    with pytest.raises(ResearchError, match="restart.*allowance"):
        _call(workflow.run, sealed, selection, directory, resume=True)
    assert _call(workflow.verify, sealed, selection, directory) == paused
    assert _files(directory) == before


@pytest.mark.parametrize("pending_stage", ["objective", "restart"])
def test_unfinished_reservation_is_unknown_and_never_reissued(tmp_path, monkeypatch, pending_stage):
    sealed, selection = _prepared(tmp_path, restart_verifications=1)
    directory = tmp_path / "run"
    known = 0
    if pending_stage == "restart":
        paused = _call(workflow.run, sealed, selection, directory,
                       pause_after_objective_attempts=2)
        known = paused["work"]["actual_force_calls"]

    class Interrupted(BaseException):
        pass

    def interrupted(*args, **kwargs):
        raise Interrupted()

    monkeypatch.setattr(execution, "_invoke", interrupted)
    with pytest.raises(Interrupted):
        _call(workflow.run, sealed, selection, directory, resume=pending_stage == "restart")
    before = _files(directory)
    events = [json.loads(line) for line in (directory / "events.jsonl").read_text().splitlines()]
    assert events[-1]["kind"] == pending_stage + "_started"
    _forbid_numerical_work(monkeypatch)
    for action, options in ((workflow.verify, {}), (workflow.run, {"resume": True})):
        with pytest.raises(execution.PendingWorkError) as caught:
            _call(action, sealed, selection, directory, **options)
        assert caught.value.work["unknown_pending_attempts"] == 1
        assert caught.value.work["known_completed_force_calls"] == known
        assert caught.value.work["actual_force_calls"] is None
    assert _files(directory) == before


@pytest.mark.parametrize("name", ["ligand", "receptor", "parameters", "cross", "source_evidence"])
def test_bound_input_byte_mutation_rejected_without_journal_changes(tmp_path, monkeypatch, name):
    sealed, selection = _prepared(tmp_path, restart_verifications=1)
    directory = tmp_path / "run"
    _call(workflow.run, sealed, selection, directory, pause_after_objective_attempts=2)
    document = json.loads(Path(sealed["protocol_path"]).read_bytes())
    path = Path(document[name]["path"])
    path.write_bytes(path.read_bytes() + b" ")
    before = _files(directory)
    _forbid_numerical_work(monkeypatch)
    for action, options in ((workflow.verify, {}), (workflow.run, {"resume": True})):
        with pytest.raises(ResearchError, match="bytes changed"):
            _call(action, sealed, selection, directory, **options)
    assert _files(directory) == before


def test_protocol_byte_mutation_is_rejected_even_when_json_value_is_unchanged(tmp_path, monkeypatch):
    sealed, selection = _prepared(tmp_path)
    path = Path(sealed["protocol_path"])
    path.write_bytes(path.read_bytes() + b" ")
    _forbid_numerical_work(monkeypatch)
    with pytest.raises(ResearchError, match="protocol bytes changed"):
        _call(workflow.preflight, sealed, selection)


@pytest.mark.parametrize("mutation", ["candidate", "authority", "shape", "solver", "old_schema"])
def test_rehashed_protocol_cannot_change_admission_or_existing_run(tmp_path, monkeypatch, mutation):
    sealed, selection = _prepared(tmp_path, restart_verifications=1)
    directory = tmp_path / "run"
    _call(workflow.run, sealed, selection, directory, pause_after_objective_attempts=2)
    document = json.loads(Path(sealed["protocol_path"]).read_bytes())
    if mutation == "candidate":
        document["candidate_id"] = "different-candidate"
    elif mutation == "authority":
        document["boundary"]["scientifically_validated"] = True
    elif mutation == "shape":
        document["shape_reference"] = {"strength": 100.0}
    elif mutation == "solver":
        document["solver"]["max_accepted_steps"] = 41
    else:
        document["schema_version"] = workflow.PROTOCOL.replace("/3.0.0", "/2.0.0")
    sealed["protocol_sha256"] = _write_json(sealed["protocol_path"], document)
    before = _files(directory)
    _forbid_numerical_work(monkeypatch)
    for action, options in ((workflow.verify, {}), (workflow.run, {"resume": True})):
        with pytest.raises(ResearchError):
            _call(action, sealed, selection, directory, **options)
    assert _files(directory) == before


def test_implementation_manifest_mutation_is_rejected(tmp_path, monkeypatch):
    sealed, selection = _prepared(tmp_path, restart_verifications=1)
    directory = tmp_path / "run"
    _call(workflow.run, sealed, selection, directory, pause_after_objective_attempts=2)
    changed = {**workflow.implementation_sources(), "unexpected-source.py": "a" * 64}
    monkeypatch.setattr(workflow, "implementation_sources", lambda: changed)
    _forbid_numerical_work(monkeypatch)
    before = _files(directory)
    for action in (workflow.preflight, workflow.verify, workflow.run):
        with pytest.raises(ResearchError, match="implementation changed"):
            _call(action, sealed, selection, None if action is workflow.preflight else directory,
                  **({"resume": True} if action is workflow.run else {}))
    assert _files(directory) == before


def test_runtime_identity_mutation_blocks_resume_and_replay(tmp_path, monkeypatch):
    sealed, selection = _prepared(tmp_path, restart_verifications=1)
    directory = tmp_path / "run"
    _call(workflow.run, sealed, selection, directory, pause_after_objective_attempts=2)
    changed = {**workflow.environment(), "python": "changed-runtime"}
    monkeypatch.setattr(workflow, "environment", lambda: changed)
    monkeypatch.setattr(execution, "environment", lambda: changed)
    _forbid_numerical_work(monkeypatch)
    before = _files(directory)
    for action, options in ((workflow.verify, {}), (workflow.run, {"resume": True})):
        with pytest.raises(ResearchError, match="binding changed"):
            _call(action, sealed, selection, directory, **options)
    assert _files(directory) == before


def test_saved_result_mutation_is_not_repaired_or_trusted(tmp_path, monkeypatch):
    sealed, selection = _prepared(tmp_path)
    directory = tmp_path / "run"
    _call(workflow.run, sealed, selection, directory)
    path = directory / "result.json"
    document = json.loads(path.read_bytes())
    document["result"]["scientifically_validated"] = True
    _write_json(path, document)
    before = _files(directory)
    _forbid_numerical_work(monkeypatch)
    for action, options in ((workflow.verify, {}), (workflow.run, {"resume": True})):
        with pytest.raises(ResearchError):
            _call(action, sealed, selection, directory, **options)
    assert _files(directory) == before


@pytest.mark.parametrize("changes", [
    {"source_authenticated": True},
    {"original_simulation_hamiltonian_reproduced": True},
    {"evidence_kind": "prepared_real_development"},
])
def test_source_evidence_authority_or_kind_cannot_be_promoted(tmp_path, changes):
    arguments = _arguments(tmp_path)
    path = Path(arguments["source_evidence"])
    evidence = json.loads(path.read_bytes())
    _write_json(path, {**evidence, **changes})
    with pytest.raises(ResearchError, match="evidence boundary"):
        workflow.prepare(**arguments)
    assert not arguments["output"].exists()


def test_prepared_real_evidence_requires_original_source_references(tmp_path):
    arguments = _arguments(tmp_path)
    arguments["evidence_kind"] = "prepared_real_development"
    path = Path(arguments["source_evidence"])
    evidence = json.loads(path.read_bytes())
    _write_json(path, {**evidence, "evidence_kind": "prepared_real_development"})
    with pytest.raises(ResearchError, match="source references"):
        workflow.prepare(**arguments)
    assert not arguments["output"].exists()


def test_original_source_reference_is_rechecked_during_replay(tmp_path, monkeypatch):
    arguments = _arguments(tmp_path, restart_verifications=1)
    original = tmp_path / "original-source.txt"
    original.write_bytes(b"Explicitly synthetic original source\n")
    path = Path(arguments["source_evidence"])
    evidence = json.loads(path.read_bytes())
    evidence["source_files"] = [{"path": str(original.resolve()),
        "sha256": hashlib.sha256(original.read_bytes()).hexdigest()}]
    _write_json(path, evidence)
    sealed = workflow.prepare(**arguments)
    selection = {name: arguments[name]
                 for name in ("model", "accepted_steps", "restart_verifications")}
    directory = tmp_path / "run"
    _call(workflow.run, sealed, selection, directory, pause_after_objective_attempts=2)
    original.write_bytes(b"Changed source\n")
    before = _files(directory)
    _forbid_numerical_work(monkeypatch)
    for action, options in ((workflow.verify, {}), (workflow.run, {"resume": True})):
        with pytest.raises(ResearchError, match="bytes changed"):
            _call(action, sealed, selection, directory, **options)
    assert _files(directory) == before


def test_exact_prepared_charge_rows_cannot_be_rebound_away(tmp_path):
    from betelgeuze_product.cpu_refinement_fourier_v1.parameters import FourierParameters

    arguments = _arguments(tmp_path)
    parameter_path, cross_path = Path(arguments["parameters"]), Path(arguments["cross"])
    parameters = json.loads(parameter_path.read_bytes())
    parameters["atom_parameters"][0]["charge_e"] = 0.125
    changed = FourierParameters.from_dict(parameters)
    _write_json(parameter_path, parameters)
    cross = json.loads(cross_path.read_bytes())
    cross["ligand_base_parameters_sha256"] = changed.fingerprint_sha256
    _write_json(cross_path, cross)
    with pytest.raises(ResearchError, match="ligand charge mismatch"):
        workflow.prepare(**arguments)
    assert not arguments["output"].exists()


def test_incomplete_covalent_topology_is_rejected_before_protocol_publication(tmp_path):
    from betelgeuze_engine_v2.molecular.serialization import canonical_system_json_bytes

    arguments = _arguments(tmp_path)
    ligand, parameters, _, fixed, _ = fourier_inputs()
    # This admission fixture has a covalent bond and no corresponding bond row.
    Path(arguments["ligand"]).write_bytes(canonical_system_json_bytes(ligand))
    Path(arguments["receptor"]).write_bytes(canonical_system_json_bytes(fixed.receptor))
    _write_json(arguments["parameters"], parameters.to_dict())
    _write_json(arguments["cross"], fixed.cross.to_dict())
    with pytest.raises(ReferencePhysicsApplicabilityError, match="bond_parameters_do_not_exactly_cover"):
        workflow.prepare(**arguments)
    assert not arguments["output"].exists()


def test_linear_angle_admission_and_replay_use_explicit_linear_model(tmp_path, monkeypatch):
    from betelgeuze_engine_v2.molecular.serialization import canonical_system_json_bytes
    from betelgeuze_product.cpu_refinement_linear_angle_v1.evaluation import LinearAngleFixedEvaluator

    arguments = _arguments(tmp_path)
    ligand, parameters, _, fixed, _ = linear_inputs()
    arguments["model"] = "linear_angle"
    Path(arguments["ligand"]).write_bytes(canonical_system_json_bytes(ligand))
    Path(arguments["receptor"]).write_bytes(canonical_system_json_bytes(fixed.receptor))
    _write_json(arguments["parameters"], parameters.to_dict())
    _write_json(arguments["cross"], fixed.cross.to_dict())
    monkeypatch.setattr(FourierFixedEvaluator, "evaluate", _forbidden)
    sealed = workflow.prepare(**arguments)
    selection = {name: arguments[name]
                 for name in ("model", "accepted_steps", "restart_verifications")}
    assert sealed["preflight"]["geometry"]["ordinary_angle_count"] == 0
    assert len(sealed["preflight"]["geometry"]["linear_angles"]) == 1
    directory = tmp_path / "run"
    result = _call(workflow.run, sealed, selection, directory)
    assert result["work"]["optimizer_force_calls"] == 1
    assert result["status"] == "force_converged"
    before = _files(directory)
    _forbid_numerical_work(monkeypatch)
    monkeypatch.setattr(LinearAngleFixedEvaluator, "evaluate", _forbidden)
    assert _call(workflow.verify, sealed, selection, directory) == result
    assert _files(directory) == before


@pytest.mark.parametrize("options", [
    {"resume": 0}, {"resume": "false"},
    {"pause_after_objective_attempts": True}, {"pause_after_objective_attempts": 0},
    {"pause_after_objective_attempts": 1.0}, {"pause_after_objective_attempts": 162},
])
def test_execution_flags_are_strict_and_invalid_flags_leave_no_run(tmp_path, monkeypatch, options):
    sealed, selection = _prepared(tmp_path)
    _forbid_numerical_work(monkeypatch)
    with pytest.raises(ResearchError):
        _call(workflow.run, sealed, selection, tmp_path / "never-created", **options)
    assert not (tmp_path / "never-created").exists()


def test_cli_prepare_preflight_run_resume_verify_and_explicit_restart_selection(tmp_path, capsys):
    arguments = _arguments(tmp_path, restart_verifications=1)
    shared = ["--model", "fourier", "--accepted-steps", "40", "--restart-verifications", "1"]
    prepare = ["prepare", *shared, "--candidate-id", arguments["candidate_id"],
               "--evidence-kind", arguments["evidence_kind"], "--algorithm", "sd",
               "--output", str(arguments["output"])]
    for name in workflow.REFS:
        prepare.extend(["--" + name.replace("_", "-"), arguments[name]])
    assert workflow.main(prepare) == 0
    sealed = json.loads(capsys.readouterr().out)
    bound = [*shared, "--protocol", sealed["protocol_path"],
             "--expected-protocol-sha256", sealed["protocol_sha256"]]
    assert workflow.main(["preflight", *bound]) == 0
    assert json.loads(capsys.readouterr().out) == sealed["preflight"]
    run = [*bound, "--run-dir", str(tmp_path / "run")]
    assert workflow.main(["run", *run, "--pause-after-objective-attempts", "2"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "checkpointed"
    assert workflow.main(["resume", *run]) == 0
    complete = json.loads(capsys.readouterr().out)
    assert complete["work"]["restart_verification_attempts"] == 1
    before = _files(tmp_path / "run")
    assert workflow.main(["verify", *run]) == 0
    assert json.loads(capsys.readouterr().out) == complete
    assert _files(tmp_path / "run") == before
    missing_restart = ["preflight", *bound]
    index = missing_restart.index("--restart-verifications")
    del missing_restart[index:index + 2]
    with pytest.raises(SystemExit) as caught:
        workflow.main(missing_restart)
    assert caught.value.code == 2
    assert "--restart-verifications" in capsys.readouterr().err
