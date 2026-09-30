"""Tiny synthetic water execution, durable restart and semantic replay attacks.

These tests establish numerical/accounting behavior, never scientific accuracy.
Hash-consistent fabricated history is distinct from live endpoint verification.
"""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import shutil

import pytest
import torch

from betelgeuze_product.cpu_refinement_v1_2.fixed_receptor import (
    CrossParameters, FixedReceptorEnvironment, FixedReceptorEvaluator,
)
from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError, canonical, digest
from betelgeuze_product.cpu_refinement_v1_2.workflow import REQUEST_SCHEMA, load_request
from betelgeuze_product.cpu_refinement_v1_3 import minimization
from betelgeuze_product.cpu_refinement_v1_3.contracts import SolverConfig
from betelgeuze_product.cpu_refinement_v1_3.journal import TrialJournal
from tests.unit.test_cpu_registered_pose_workflow import request_fixture


def _read(path):
    return json.loads(Path(path).read_bytes())


def _write(path, value):
    # Preserve the production journal's canonical byte encoding and file mode.
    Path(path).write_text(canonical(value) + "\n", encoding="ascii")


def _reseal(value, field):
    value[field] = digest({key: item for key, item in value.items() if key != field})


def _events(path):
    return [json.loads(line) for line in (path / "events.jsonl").read_bytes().splitlines()]


def _files(path):
    return {str(item.relative_to(path)): item.read_bytes()
            for item in path.rglob("*") if item.is_file()}


def _forbidden(*args, **kwargs):
    pytest.fail("read-only replay or completed reuse invoked graph/force work")


@pytest.fixture(scope="module")
def prepared(tmp_path_factory):
    directory = tmp_path_factory.mktemp("cartesian-synthetic-water")
    request, _ = request_fixture(directory, strained=True)
    old = {key: value for key, value in request.items() if key != "cross_parameters"}
    old["schema_id"] = REQUEST_SCHEMA
    _, receptor, ligand, parameters, *_ = load_request(old, digest(minimization.source_manifest()))
    fixed = FixedReceptorEnvironment(receptor, CrossParameters.from_dict(
        _read(request["cross_parameters"]["path"])))
    return ligand, parameters, fixed, {"synthetic_request_sha256": digest(request)}


def _config(**updates):
    return SolverConfig(**{"max_objective_attempts": 6, "max_accepted_steps": 5,
                           "force_tolerance": 1.e-12, "history_size": 2, **updates})


def _run(prepared, path, config, **kwargs):
    ligand, parameters, fixed, binding = prepared
    return minimization.minimize(ligand, parameters, config, fixed_environment=fixed,
                                 run_dir=path, binding=binding, **kwargs)


def _verify(prepared, path, config):
    ligand, parameters, fixed, binding = prepared
    return minimization.verify_run(ligand, parameters, config, fixed_environment=fixed,
                                   run_dir=path, binding=binding)


@pytest.fixture(scope="module")
def paused(prepared, tmp_path_factory):
    path = tmp_path_factory.mktemp("cartesian-paused") / "run"
    config = _config()
    result = _run(prepared, path, config, pause_after_objective_attempts=3)
    assert result["status"] == "checkpointed"
    assert len(result["checkpoint"]["state"]["history"]) == 2
    return path, config, result


@pytest.fixture(scope="module")
def completed(prepared, tmp_path_factory):
    path = tmp_path_factory.mktemp("cartesian-completed") / "run"
    config = _config()
    result = _run(prepared, path, config)
    assert result["status"] != "checkpointed"
    return path, config, result


@pytest.mark.parametrize("algorithm", ["sd", "lbfgs"])
def test_rejected_trial_resume_matches_continuous_state_and_separate_work(prepared, tmp_path, algorithm):
    config = _config(algorithm=algorithm, initial_step_size=1., maximum_atom_displacement=.1,
                     max_objective_attempts=8, max_accepted_steps=7)
    full = _run(prepared, tmp_path / "full", config)
    partial = _run(prepared, tmp_path / "split", config, pause_after_objective_attempts=2)
    state = partial["checkpoint"]["state"]
    assert state["line_search"]["trial"] == 1
    assert state["current"]["attempt"] == 1
    assert _events(tmp_path / "split")[-1]["payload"]["decision"]["outcome"] == "rejected_armijo"
    resumed = _run(prepared, tmp_path / "split", config, resume=True)
    assert full["checkpoint"]["state"] == resumed["checkpoint"]["state"]
    assert full["work"]["optimizer_objective_attempts"] == resumed["work"]["optimizer_objective_attempts"] == 8
    assert full["work"]["restart_force_calls"] == 0
    assert resumed["work"]["restart_force_calls"] == 1
    assert resumed["work"]["actual_force_calls"] == full["work"]["actual_force_calls"] + 1
    assert resumed["work"]["actual_force_calls"] <= config.max_total_force_calls
    assert _verify(prepared, tmp_path / "split", config) == resumed


def test_cumulative_restart_allowance_is_not_reset_per_invocation(prepared, tmp_path, monkeypatch):
    config = _config(max_restart_verifications=2)
    path = tmp_path / "run"
    first = _run(prepared, path, config, pause_after_objective_attempts=1)
    second = _run(prepared, path, config, pause_after_objective_attempts=2, resume=True)
    third = _run(prepared, path, config, pause_after_objective_attempts=3, resume=True)
    assert [row["work"]["actual_force_calls"] for row in (first, second, third)] == [1, 3, 5]
    assert third["work"]["restart_verification_attempts"] == 2
    before = _files(path)
    monkeypatch.setattr(FixedReceptorEvaluator, "evaluate", _forbidden)
    with pytest.raises(ResearchError, match="allowance exhausted"):
        _run(prepared, path, config, resume=True)
    assert _files(path) == before


def test_no_progress_resume_and_verification_spend_no_restart_allowance(prepared, tmp_path, monkeypatch):
    config = _config(max_restart_verifications=0)
    path = tmp_path / "run"
    first = _run(prepared, path, config, pause_after_objective_attempts=1)
    before = _files(path)
    monkeypatch.setattr(FixedReceptorEvaluator, "evaluate", _forbidden)
    monkeypatch.setattr(minimization, "build_compact_radius_graph", _forbidden)
    assert _verify(prepared, path, config) == first
    assert _run(prepared, path, config, pause_after_objective_attempts=1, resume=True) == first
    with pytest.raises(ResearchError, match="allowance exhausted"):
        _run(prepared, path, config, resume=True)
    assert _files(path) == before


def test_completed_verification_and_reuse_have_zero_new_force_graph_calls(prepared, completed, monkeypatch):
    path, config, result = completed
    before = _files(path)
    monkeypatch.setattr(FixedReceptorEvaluator, "evaluate", _forbidden)
    monkeypatch.setattr(minimization, "build_compact_radius_graph", _forbidden)
    assert _verify(prepared, path, config) == result
    assert _run(prepared, path, config, resume=True) == result
    assert _files(path) == before


def test_restart_checks_full_force_direction_not_only_its_norm(prepared, paused, tmp_path, monkeypatch):
    source, config, initial = paused
    path = tmp_path / "run"
    shutil.copytree(source, path)
    original = FixedReceptorEvaluator.evaluate
    calls = []

    def flipped(self, system, graph):
        evaluated = original(self, system, graph)
        replacement = -evaluated.term.forces
        assert torch.equal(torch.linalg.vector_norm(replacement, dim=-1),
                           torch.linalg.vector_norm(evaluated.term.forces, dim=-1))
        calls.append(1)
        return replace(evaluated, term=replace(evaluated.term, forces=replacement))

    monkeypatch.setattr(FixedReceptorEvaluator, "evaluate", flipped)
    with pytest.raises(ResearchError, match="full energy/force verification failed") as caught:
        _run(prepared, path, config, resume=True)
    assert calls == [1]
    work = caught.value.work
    assert work["optimizer_objective_attempts"] == initial["work"]["optimizer_objective_attempts"]
    assert work["restart_force_calls"] == 1 and work["failed_restart_force_calls"] == 0
    assert work["actual_force_calls"] == initial["work"]["actual_force_calls"] + 1
    before = _files(path)
    monkeypatch.setattr(FixedReceptorEvaluator, "evaluate", _forbidden)
    with pytest.raises(ResearchError, match="recorded restart"):
        _run(prepared, path, config, resume=True)
    assert _files(path) == before


@pytest.mark.parametrize("mutation", ["history_pair", "history_order", "history_source", "force_direction"])
def test_resealed_checkpoint_cannot_replace_journal_derived_history(prepared, paused, tmp_path, mutation):
    source, config, _ = paused
    path = tmp_path / "run"
    shutil.copytree(source, path)
    checkpoint_path = sorted((path / "checkpoints").glob("*.json"))[-1]
    checkpoint = _read(checkpoint_path)
    state = checkpoint["state"]
    if mutation == "history_pair":
        pair = state["history"][0]
        for key in ("s", "y"):
            pair[key] = [[(-float.fromhex(value)).hex() for value in xyz] for xyz in pair[key]]
        # Same shape, finite data and positive curvature; the actual transition differs.
    elif mutation == "history_order":
        state["history"].reverse()
    elif mutation == "history_source":
        state["history"][0]["source_attempt"] += 1
    else:
        state["current"]["forces"] = [
            [(-float.fromhex(value)).hex() for value in xyz] for xyz in state["current"]["forces"]]
    _reseal(checkpoint, "checkpoint_sha256")
    _write(checkpoint_path, checkpoint)
    with pytest.raises(ResearchError, match="checkpoint differs from replayed"):
        _verify(prepared, path, config)


@pytest.mark.parametrize("mutation", ["force_count", "claim", "status", "timing"])
def test_resealed_terminal_result_must_reproduce_all_fields(prepared, completed, tmp_path, mutation):
    source, config, _ = completed
    path = tmp_path / "run"
    shutil.copytree(source, path)
    envelope = _read(path / "result.json")
    result = envelope["result"]
    if mutation == "force_count":
        result["work"]["actual_force_calls"] += 1
    elif mutation == "claim":
        result["scientifically_validated"] = True
    elif mutation == "status":
        result["status"] = "force_converged"
        result["converged"] = True
    else:
        result["timings_ns"]["optimizer_force_ns"] += 1
    _reseal(result, "result_sha256")
    _reseal(envelope, "result_sha256")
    _write(path / "result.json", envelope)
    with pytest.raises(ResearchError, match="cached Cartesian result does not reproduce"):
        _verify(prepared, path, config)


def test_finished_observation_without_checkpoint_recovers_without_repeating_it(prepared, tmp_path, monkeypatch):
    config = _config(max_objective_attempts=3, max_accepted_steps=2)
    path = tmp_path / "run"
    original = TrialJournal.save_checkpoint

    def interrupt(self, state):
        raise KeyboardInterrupt("synthetic crash after durable finish, before checkpoint")

    monkeypatch.setattr(TrialJournal, "save_checkpoint", interrupt)
    with pytest.raises(KeyboardInterrupt):
        _run(prepared, path, config)
    assert len(_events(path)) == 2
    assert list((path / "checkpoints").iterdir()) == []
    monkeypatch.setattr(TrialJournal, "save_checkpoint", original)
    replayed = _verify(prepared, path, config)
    assert replayed["work"]["actual_force_calls"] == 1
    result = _run(prepared, path, config, resume=True)
    assert result["work"]["optimizer_objective_attempts"] == 3
    assert result["work"]["restart_force_calls"] == 1
    assert result["work"]["actual_force_calls"] == 4
    initial_starts = [event for event in _events(path) if event["kind"] == "objective_started"
                      and event["payload"]["attempt"] == 1]
    assert len(initial_starts) == 1


@pytest.mark.parametrize("during_restart", [False, True])
def test_start_only_unknown_work_is_preserved_and_never_retried(prepared, tmp_path, monkeypatch, during_restart):
    config = _config()
    path = tmp_path / "run"
    if during_restart:
        _run(prepared, path, config, pause_after_objective_attempts=1)
    calls = []

    def interrupt(*args):
        calls.append(1)
        raise KeyboardInterrupt("synthetic interrupted force")

    monkeypatch.setattr(FixedReceptorEvaluator, "evaluate", interrupt)
    with pytest.raises(KeyboardInterrupt):
        _run(prepared, path, config, resume=during_restart)
    assert calls == [1]
    before = _files(path)
    for operation in (_verify, lambda fixture, directory, cfg: _run(fixture, directory, cfg, resume=True)):
        with pytest.raises(minimization.PendingWorkError) as caught:
            operation(prepared, path, config)
        work = caught.value.work
        assert work["unknown_pending_attempts"] == 1
        assert work["actual_force_calls"] is None
        assert work["known_completed_force_calls"] == int(during_restart)
        assert work["optimizer_objective_attempts"] == 1
        assert work["restart_verification_attempts"] == int(during_restart)
    assert calls == [1]
    assert _files(path) == before


@pytest.mark.parametrize("stage", ["graph", "force"])
def test_graph_and_force_failures_keep_distinct_denominators(prepared, tmp_path, monkeypatch, stage):
    def fail(*args, **kwargs):
        raise FloatingPointError("synthetic failure")
    if stage == "graph":
        monkeypatch.setattr(minimization, "build_compact_radius_graph", fail)
    else:
        monkeypatch.setattr(FixedReceptorEvaluator, "evaluate", fail)
    config = _config()
    result = _run(prepared, tmp_path / "run", config)
    assert result["status"] == "evaluation_failed"
    work = result["work"]
    assert work["optimizer_objective_attempts"] == work["optimizer_graph_calls"] == 1
    expected_force = int(stage == "force")
    assert work["optimizer_force_calls"] == work["failed_optimizer_force_calls"] == expected_force
    assert work["actual_force_calls"] == work["known_completed_force_calls"] == expected_force
    assert work["unknown_pending_attempts"] == 0
    assert _verify(prepared, tmp_path / "run", config) == result


def test_changed_implementation_binding_blocks_resume_before_work(prepared, paused, tmp_path, monkeypatch):
    source, config, _ = paused
    path = tmp_path / "run"
    shutil.copytree(source, path)
    before = _files(path)
    changed = {**minimization.source_manifest(), "synthetic_changed_module.py": "0" * 64}
    monkeypatch.setattr(minimization, "source_manifest", lambda: changed)
    monkeypatch.setattr(FixedReceptorEvaluator, "evaluate", _forbidden)
    monkeypatch.setattr(minimization, "build_compact_radius_graph", _forbidden)
    with pytest.raises(ResearchError, match="journal binding changed"):
        _run(prepared, path, config, resume=True)
    assert _files(path) == before


def test_implementation_change_before_publication_preserves_work_but_blocks_result(prepared, tmp_path, monkeypatch):
    original = minimization.source_manifest
    unchanged = original()
    changed = {**unchanged, "synthetic_changed_module.py": "0" * 64}
    calls = []

    def manifest():
        calls.append(1)
        return unchanged if len(calls) == 1 else changed

    config = _config(max_objective_attempts=1)
    path = tmp_path / "run"
    monkeypatch.setattr(minimization, "source_manifest", manifest)
    with pytest.raises(ResearchError, match="Cartesian implementation changed"):
        _run(prepared, path, config)
    assert len(calls) == 2
    assert len(_events(path)) == 2
    assert not (path / "result.json").exists()
    monkeypatch.setattr(minimization, "source_manifest", original)
    monkeypatch.setattr(FixedReceptorEvaluator, "evaluate", _forbidden)
    replayed = _verify(prepared, path, config)
    assert replayed["work"]["actual_force_calls"] == 1
    assert replayed["status"] == "objective_budget_exhausted"


@pytest.mark.parametrize("field", ["state_sha256", "work"])
def test_resealed_event_chain_still_checks_completed_cross_fields(prepared, tmp_path, field):
    path, config = tmp_path / "run", _config()
    _run(prepared, path, config, pause_after_objective_attempts=1)
    events = _events(path)
    payload = events[-1]["payload"]
    if field == "state_sha256":
        payload[field] = "0" * 64
    else:
        payload[field]["force_calls"] = 0  # Full returned observation requires one force call.
    _reseal(events[-1], "event_sha256")
    (path / "events.jsonl").write_text("".join(canonical(event) + "\n" for event in events))
    checkpoint_path, = (path / "checkpoints").glob("*.json")
    checkpoint = _read(checkpoint_path)
    checkpoint["journal_sha256"] = events[-1]["event_sha256"]
    _reseal(checkpoint, "checkpoint_sha256")
    _write(checkpoint_path, checkpoint)
    with pytest.raises(ResearchError, match="state digest changed|work denominator is inconsistent"):
        _verify(prepared, path, config)


def test_self_consistent_fabricated_saved_force_needs_live_resume_verification(prepared, tmp_path):
    """A local checksum is not an external attestation of historical physics."""
    path, config = tmp_path / "run", _config()
    original = _run(prepared, path, config, pause_after_objective_attempts=1)
    events = _events(path)
    payload = events[-1]["payload"]
    observation = payload["observation"]
    observation["forces"] = [
        [(-float.fromhex(value)).hex() for value in xyz] for xyz in observation["forces"]]
    forged_state = deepcopy(original["checkpoint"]["state"])
    forged_state["initial"] = deepcopy(observation)
    forged_state["current"] = deepcopy(observation)
    payload["state_sha256"] = digest(forged_state)
    _reseal(events[-1], "event_sha256")
    (path / "events.jsonl").write_text("".join(canonical(event) + "\n" for event in events))
    checkpoint_path, = (path / "checkpoints").glob("*.json")
    checkpoint = _read(checkpoint_path)
    checkpoint.update(state=forged_state, journal_sha256=events[-1]["event_sha256"])
    _reseal(checkpoint, "checkpoint_sha256")
    _write(checkpoint_path, checkpoint)

    # All structural relationships were forged consistently; file replay alone
    # must not be described as re-evaluating or authenticating the objective.
    replayed = _verify(prepared, path, config)
    assert replayed["checkpoint"]["state"] == forged_state
    assert replayed["scientifically_validated"] is False
    assert (forged_state["current"]["maximum_raw_atom_force"] ==
            original["checkpoint"]["state"]["current"]["maximum_raw_atom_force"])
    with pytest.raises(ResearchError, match="full energy/force verification failed") as caught:
        _run(prepared, path, config, resume=True)
    assert caught.value.work["optimizer_objective_attempts"] == 1
    assert caught.value.work["restart_force_calls"] == 1
    assert caught.value.work["actual_force_calls"] == 2
