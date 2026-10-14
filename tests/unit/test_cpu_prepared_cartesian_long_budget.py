"""Synthetic contract coverage only; no physical qualification claims."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest
import torch

from betelgeuze_product import cpu_prepared_cartesian_long_budget as workflow
from betelgeuze_product.cpu_prepared_cartesian_budget_v3 import workflow as legacy
from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError
from betelgeuze_product.cpu_refinement_v1_3 import minimization as execution
from tests.unit.test_cpu_prepared_cartesian_budget_v3 import (
    _arguments as legacy_arguments, _files, _forbid_numerical_work, _write_json,
    single_cpu_thread,
)


def _arguments(tmp_path, algorithm="sd", restarts=0):
    arguments = legacy_arguments(tmp_path, algorithm=algorithm, restart_verifications=restarts)
    arguments.pop("accepted_steps")
    arguments["profile"] = workflow.PROFILE_ID
    arguments["solver"] = workflow.budget_config(algorithm, profile=workflow.PROFILE_ID,
                                                restart_verifications=restarts)
    return arguments


def _prepared(tmp_path, algorithm="sd", restarts=0):
    arguments = _arguments(tmp_path, algorithm, restarts)
    return workflow.prepare(**arguments), {name: arguments[name] for name in
                                           ("profile", "model", "restart_verifications")}


def _call(action, sealed, selection, directory=None, **options):
    args = [sealed["protocol_path"], sealed["protocol_sha256"]]
    if directory is not None:
        args.append(directory)
    return action(*args, **{**selection, **options})


@pytest.mark.parametrize("algorithm", ["sd", "lbfgs"])
@pytest.mark.parametrize("restarts", [0, 1])
def test_only_accepted_ceiling_changes_and_preflight_is_force_free(tmp_path, monkeypatch, algorithm, restarts):
    _forbid_numerical_work(monkeypatch)
    sealed, selection = _prepared(tmp_path, algorithm, restarts)
    old = legacy.budget_config(algorithm, 160, restart_verifications=restarts)
    expected = replace(old, max_accepted_steps=600)
    assert workflow.budget_config(algorithm, profile=workflow.PROFILE_ID,
                                  restart_verifications=restarts) == expected
    receipt = _call(workflow.preflight, sealed, selection)
    assert receipt == sealed["preflight"]
    assert receipt["profile_id"] == workflow.PROFILE_ID
    assert receipt["solver"]["max_objective_attempts"] == 641
    assert receipt["solver"]["max_accepted_steps"] == 600
    assert receipt["geometry"]["force_calls"] == receipt["geometry"]["energy_calls"] == 0
    assert receipt["boundary"] == legacy.BOUNDARY
    assert receipt["coordinate_frame_authenticity_verified"] is False
    assert legacy.ACCEPTED_STEP_BUDGETS == (40, 80, 160)
    with pytest.raises(ResearchError):
        legacy.budget_config(algorithm, 600, restart_verifications=restarts)


@pytest.mark.parametrize("change", [{"profile": None}, {"profile": "long"},
    {"profile": legacy.PROFILE_ID}, {"model": "shape"}, {"model": "linear_angle"},
    {"restart_verifications": 1}, {"restart_verifications": True}])
def test_wrong_selection_rejected_before_work(tmp_path, monkeypatch, change):
    sealed, selection = _prepared(tmp_path)
    _forbid_numerical_work(monkeypatch)
    for action in (workflow.preflight, workflow.run, workflow.verify):
        with pytest.raises(ResearchError):
            _call(action, sealed, selection, None if action is workflow.preflight else tmp_path / "run", **change)
    assert not (tmp_path / "run").exists()


@pytest.mark.parametrize("field,value", [("max_accepted_steps", 160), ("max_objective_attempts", 2401),
    ("force_tolerance", .002), ("max_backtracks", 4), ("max_restart_verifications", 1)])
def test_nonfrozen_controls_rejected(tmp_path, field, value):
    args = _arguments(tmp_path)
    args["solver"] = replace(args["solver"], **{field: value})
    with pytest.raises(ResearchError):
        workflow.prepare(**args)
    assert not args["output"].exists()


def test_profile_required_and_legacy_protocol_not_reinterpreted(tmp_path, monkeypatch):
    with pytest.raises(TypeError):
        workflow.budget_config("sd", restart_verifications=0)
    old = legacy.prepare(**legacy_arguments(tmp_path))
    _forbid_numerical_work(monkeypatch)
    with pytest.raises(ResearchError):
        workflow.preflight(old["protocol_path"], old["protocol_sha256"],
            profile=workflow.PROFILE_ID, model="fourier", restart_verifications=0)


@pytest.mark.parametrize("stage", ["objective", "restart"])
def test_unknown_pending_work_is_retained_never_reissued(tmp_path, monkeypatch, stage):
    sealed, selection = _prepared(tmp_path, restarts=1)
    directory = tmp_path / "run"
    known = 0
    if stage == "restart":
        paused = _call(workflow.run, sealed, selection, directory, pause_after_objective_attempts=2)
        known = paused["work"]["actual_force_calls"]
    class Interrupted(BaseException):
        pass
    def interrupted(*args, **kwargs):
        raise Interrupted()
    monkeypatch.setattr(execution, "_invoke", interrupted)
    with pytest.raises(Interrupted):
        _call(workflow.run, sealed, selection, directory, resume=stage == "restart")
    before = _files(directory)
    _forbid_numerical_work(monkeypatch)
    for action, options in ((workflow.verify, {}), (workflow.run, {"resume": True})):
        with pytest.raises(execution.PendingWorkError) as caught:
            _call(action, sealed, selection, directory, **options)
        assert caught.value.work["unknown_pending_attempts"] == 1
        assert caught.value.work["known_completed_force_calls"] == known
        assert caught.value.work["actual_force_calls"] is None
        assert caught.value.work["max_total_force_calls"] == 642
    assert before == _files(directory)


@pytest.mark.parametrize("restarts", [0, 1])
def test_resume_allowance_is_separate_and_cumulative(tmp_path, monkeypatch, restarts):
    sealed, selection = _prepared(tmp_path, restarts=restarts)
    directory = tmp_path / "run"
    paused = _call(workflow.run, sealed, selection, directory, pause_after_objective_attempts=2)
    if restarts:
        paused = _call(workflow.run, sealed, selection, directory, resume=True, pause_after_objective_attempts=3)
        assert paused["work"]["optimizer_objective_attempts"] == 3
        assert paused["work"]["restart_verification_attempts"] == 1
        assert paused["work"]["actual_force_calls"] == 4
    before = _files(directory)
    _forbid_numerical_work(monkeypatch)
    with pytest.raises(ResearchError, match="restart.*allowance"):
        _call(workflow.run, sealed, selection, directory, resume=True)
    assert _call(workflow.verify, sealed, selection, directory) == paused
    assert _files(directory) == before


def test_synthetic_direct_and_resumed_endpoints_and_zero_work_replay(tmp_path, monkeypatch):
    sealed, selection = _prepared(tmp_path, restarts=1)
    direct = _call(workflow.run, sealed, selection, tmp_path / "direct")
    directory = tmp_path / "resumed"
    _call(workflow.run, sealed, selection, directory, pause_after_objective_attempts=4)
    resumed = _call(workflow.run, sealed, selection, directory, resume=True)
    assert direct["checkpoint"]["state"] == resumed["checkpoint"]["state"]
    assert direct["status"] == resumed["status"]
    assert resumed["work"]["optimizer_objective_attempts"] == direct["work"]["optimizer_objective_attempts"] <= 641
    assert resumed["work"]["actual_force_calls"] == direct["work"]["actual_force_calls"] + 1 <= 642
    assert resumed["checkpoint"]["state"]["accepted"] == 600
    assert resumed["status"] == "max_accepted_steps_reached"
    assert resumed["converged"] is False
    assert direct["work"]["optimizer_objective_attempts"] == 601
    assert resumed["work"]["actual_force_calls"] == 602
    for key in ("scientifically_validated", "claim_safe", "customer_execution_allowed"):
        assert resumed[key] is False
    before = _files(directory)
    _forbid_numerical_work(monkeypatch)
    assert _call(workflow.verify, sealed, selection, directory) == resumed
    assert _call(workflow.run, sealed, selection, directory, resume=True) == resumed
    assert _files(directory) == before


@pytest.mark.parametrize("mutation", ["profile", "model", "source", "solver", "boundary", "extra"])
def test_rehashed_protocol_mutation_rejected(tmp_path, monkeypatch, mutation):
    sealed, selection = _prepared(tmp_path)
    document = json.loads(Path(sealed["protocol_path"]).read_bytes())
    if mutation == "profile": document["profile_id"] = legacy.PROFILE_ID
    elif mutation == "model": document["model"] = "linear_angle"
    elif mutation == "source": document["implementation_sha256"] = "0" * 64
    elif mutation == "solver": document["solver"]["max_objective_attempts"] = 2401
    elif mutation == "boundary": document["boundary"]["scientifically_validated"] = True
    else: document["shape"] = True
    sealed["protocol_sha256"] = _write_json(sealed["protocol_path"], document)
    _forbid_numerical_work(monkeypatch)
    with pytest.raises(ResearchError):
        _call(workflow.run, sealed, selection, tmp_path / "run")
    assert not (tmp_path / "run").exists()


def test_source_manifest_binds_new_adapter_and_existing_closure():
    sources = legacy._profile_sources(workflow._PROFILE)
    assert sources.items() >= legacy.implementation_sources().items()
    key = "betelgeuze_product/cpu_prepared_cartesian_long_budget.py"
    assert sources[key] == hashlib.sha256(Path(workflow.__file__).read_bytes()).hexdigest()


def test_profile_definition_is_immutable():
    from dataclasses import FrozenInstanceError
    with pytest.raises(FrozenInstanceError):
        workflow._PROFILE.objective_attempts = 2401


def test_runtime_change_blocks_replay_and_resume(tmp_path, monkeypatch):
    sealed, selection = _prepared(tmp_path, restarts=1)
    directory = tmp_path / "run"
    _call(workflow.run, sealed, selection, directory, pause_after_objective_attempts=2)
    changed = {**legacy.environment(), "python": "changed-runtime"}
    monkeypatch.setattr(legacy, "environment", lambda: changed)
    monkeypatch.setattr(execution, "environment", lambda: changed)
    before = _files(directory)
    _forbid_numerical_work(monkeypatch)
    for action, options in ((workflow.verify, {}), (workflow.run, {"resume": True})):
        with pytest.raises(ResearchError, match="binding changed"):
            _call(action, sealed, selection, directory, **options)
    assert _files(directory) == before


def test_linear_angle_model_admits_runs_and_replays_without_fourier(tmp_path, monkeypatch):
    from betelgeuze_engine_v2.molecular.serialization import canonical_system_json_bytes
    from betelgeuze_product.cpu_refinement_fourier_v1.evaluation import FourierFixedEvaluator
    from betelgeuze_product.cpu_refinement_linear_angle_v1.evaluation import LinearAngleFixedEvaluator
    from tests.unit.test_cpu_parent_shape_linear_base import _inputs
    from tests.unit.test_cpu_prepared_cartesian_budget_v3 import _forbidden
    args = _arguments(tmp_path)
    ligand, parameters, _, fixed, _ = _inputs()
    args["model"] = "linear_angle"
    Path(args["ligand"]).write_bytes(canonical_system_json_bytes(ligand))
    Path(args["receptor"]).write_bytes(canonical_system_json_bytes(fixed.receptor))
    _write_json(args["parameters"], parameters.to_dict())
    _write_json(args["cross"], fixed.cross.to_dict())
    monkeypatch.setattr(FourierFixedEvaluator, "evaluate", _forbidden)
    sealed = workflow.prepare(**args)
    selection = {name: args[name] for name in ("profile", "model", "restart_verifications")}
    assert len(sealed["preflight"]["geometry"]["linear_angles"]) == 1
    directory = tmp_path / "run"
    result = _call(workflow.run, sealed, selection, directory)
    assert result["status"] == "force_converged"
    assert result["work"]["actual_force_calls"] == 1
    before = _files(directory)
    _forbid_numerical_work(monkeypatch)
    monkeypatch.setattr(LinearAngleFixedEvaluator, "evaluate", _forbidden)
    assert _call(workflow.verify, sealed, selection, directory) == result
    assert _files(directory) == before


def test_cli_full_contract_and_required_explicit_profile(tmp_path, capsys):
    arguments = _arguments(tmp_path, restarts=1)
    selection = ["--model", "fourier", "--profile", workflow.PROFILE_ID, "--restart-verifications", "1"]
    prepare = ["prepare", *selection, "--candidate-id", arguments["candidate_id"],
               "--evidence-kind", arguments["evidence_kind"], "--algorithm", "lbfgs",
               "--output", str(arguments["output"])]
    for name in legacy.REFS:
        prepare.extend(["--" + name.replace("_", "-"), arguments[name]])
    assert workflow.main(prepare) == 0
    sealed = json.loads(capsys.readouterr().out)
    bound = [*selection, "--protocol", sealed["protocol_path"],
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
    for flag in ("--profile", "--model", "--restart-verifications"):
        missing = ["preflight", *bound]
        index = missing.index(flag)
        del missing[index:index + 2]
        with pytest.raises(SystemExit) as caught:
            workflow.main(missing)
        assert caught.value.code == 2
        assert flag in capsys.readouterr().err
