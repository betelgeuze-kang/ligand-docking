"""Synthetic source-bound Cartesian orchestration; no physical accuracy claim.

Use the original registered fixture's declared inputs and source origins. The
Cartesian protocol explicitly converts those requests while retaining the
original source descriptors used for admission.
"""
from copy import deepcopy
import json
import platform
import shutil

import pytest

from betelgeuze_engine_v2.docking.scorer_v1 import ChemistryPoseScorerV1
from betelgeuze_product import installed_native_v4_cartesian_comparison as cartesian
from betelgeuze_product import installed_native_v4_comparison as native_cli
from betelgeuze_product import installed_synthetic_comparison as comparison
from betelgeuze_product import registered_cartesian_policy_adapter as adapter
from betelgeuze_product.cpu_refinement_v1_2 import registered_policy_adapter as original_adapter
from betelgeuze_product.cpu_refinement_v1_2.chemical_features import ExplicitGraphScorer
from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError
from betelgeuze_product.cpu_refinement_v1_3 import minimization, workflow
from betelgeuze_product.cpu_refinement_v1_3.contracts import SolverConfig
from tests.unit.test_installed_native_v4_registered_comparison import _document, _protocol as registered_protocol


def _protocol(directory):
    protocol = registered_protocol(directory)
    protocol["schema_version"] = cartesian.PROTOCOL
    protocol["cartesian_solver"] = SolverConfig(
        max_objective_attempts=2, max_accepted_steps=1,
        max_restart_verifications=1,
    ).to_dict()
    return protocol


def _forbid_execution(monkeypatch):
    """Permit input binding arithmetic, prohibit workers, forces, and scores."""
    platform.platform()  # Resolve Python's lazy uname subprocess beforehand.

    def forbidden(*args, **kwargs):
        pytest.fail("Cartesian admission/reuse unexpectedly performed numerical work or scoring")

    monkeypatch.setattr(comparison.subprocess, "Popen", forbidden)
    monkeypatch.setattr(adapter, "evaluate", forbidden)
    monkeypatch.setattr(workflow, "evaluate", forbidden)
    monkeypatch.setattr(minimization, "minimize", forbidden)
    monkeypatch.setattr(workflow.ExtendedEvaluator, "evaluate", forbidden)
    monkeypatch.setattr(workflow.FixedReceptorEvaluator, "evaluate", forbidden)
    monkeypatch.setattr(workflow.FixedReceptorEnvironment, "evaluate_cross", forbidden)
    monkeypatch.setattr(ExplicitGraphScorer, "score_terms", forbidden)
    for method in ("score", "score_terms", "score_batch", "score_terms_batch"):
        monkeypatch.setattr(ChemistryPoseScorerV1, method, forbidden)


def test_explicit_cartesian_freeze_retains_original_source_descriptors(tmp_path, monkeypatch):
    protocol = _protocol(tmp_path)
    before = deepcopy(protocol)
    original_requests = {rid: comparison._bound_json(ref)
                         for rid, ref in protocol["requests"].items()}
    _forbid_execution(monkeypatch)
    frozen = cartesian.freeze(protocol)
    assert protocol == before
    assert frozen["schema_version"] == cartesian.FROZEN
    assert frozen["protocol"] == before
    assert frozen["cartesian_solver"] == protocol["cartesian_solver"]
    assert frozen["original_requests"] == original_requests
    assert set(frozen["prepared_bindings"]) == set(original_requests)
    assert all(item["candidate_prepared_identity_bound"]
               for item in frozen["prepared_bindings"].values())
    for rid, original in original_requests.items():
        converted = frozen["requests"][rid]
        assert converted == workflow.prepare_cartesian_request(
            original, SolverConfig.from_dict(protocol["cartesian_solver"]))
        assert converted["schema_id"] == workflow.REQUEST_SCHEMA
        assert "max_refinement_steps" not in converted["budget"]
        assert frozen["original_source_inputs"][rid] == original_adapter.input_binding(original)
        for name in workflow.FILE_FIELDS:
            assert converted[name] == original[name]
        assert frozen["source_inputs"][rid] == adapter.input_binding(converted)
    assert frozen["evaluation_labels_read"] == 0
    assert frozen["scientifically_validated"] is False
    assert frozen["same_prepared_assay_state_verified"] is False


def test_native_cli_preflight_v4_freezes_without_execution(tmp_path, monkeypatch, capsys):
    protocol = _protocol(tmp_path / "input")
    draft = _document(tmp_path / "draft.json", protocol)
    output = tmp_path / "admitted-protocol.json"
    _forbid_execution(monkeypatch)
    assert native_cli.main(["preflight-v4", "--protocol", draft["path"],
                            "--output-protocol", str(output)]) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["status"] == "ready"
    assert receipt["candidate_count"] == 2
    assert receipt["evaluation_labels_read"] == 0
    assert receipt["scientifically_validated"] is False
    assert comparison._read_protocol(output) == protocol


@pytest.mark.parametrize("change", ["missing_solver", "legacy_solver", "weaker_force",
                                    "swapped_requests", "missing_candidate", "call_cap"])
def test_cartesian_opt_in_cannot_bypass_source_or_solver_admission(tmp_path, monkeypatch, change):
    protocol = _protocol(tmp_path / "input")
    ids = list(protocol["requests"])
    if change == "missing_solver":
        protocol.pop("cartesian_solver")
    elif change == "legacy_solver":
        protocol["cartesian_solver"] = comparison._bound_json(protocol["requests"][ids[0]])["solver"]
    elif change == "weaker_force":
        protocol["cartesian_solver"] = SolverConfig(force_tolerance=.01).to_dict()
    elif change == "swapped_requests":
        protocol["requests"][ids[0]], protocol["requests"][ids[1]] = (
            protocol["requests"][ids[1]], protocol["requests"][ids[0]])
    elif change == "missing_candidate":
        protocol["requests"].pop(ids[0])
    else:
        protocol["max_engine_calls_per_arm"] = 1
    _forbid_execution(monkeypatch)
    with pytest.raises((ValueError, ResearchError)):
        cartesian.freeze(protocol)
    run_dir = tmp_path / "must-not-run"
    with pytest.raises((ValueError, ResearchError)):
        cartesian.run(protocol, run_dir)
    assert not run_dir.exists()


def test_adapter_requires_explicit_cartesian_request(tmp_path, monkeypatch):
    protocol = _protocol(tmp_path)
    old = comparison._bound_json(next(iter(protocol["requests"].values())))
    before = deepcopy(old)
    _forbid_execution(monkeypatch)
    with pytest.raises((ValueError, ResearchError)):
        adapter.input_binding(old)
    assert old == before
    explicit = workflow.prepare_cartesian_request(old, SolverConfig.from_dict(protocol["cartesian_solver"]))
    binding = adapter.input_binding(explicit)
    assert binding["score_quantity"] == workflow.SCORE_QUANTITY
    assert binding["candidate_source_admission_verified"] is False
    assert explicit["schema_id"] == workflow.REQUEST_SCHEMA


@pytest.fixture(scope="module")
def completed(tmp_path_factory):
    root = tmp_path_factory.mktemp("native-cartesian-integration")
    protocol = _protocol(root / "input")
    run_dir = root / "run"
    return protocol, run_dir, cartesian.run(protocol, run_dir)


def test_two_candidates_four_arms_preserve_identity_scores_and_work(completed):
    protocol, run_dir, result = completed
    assert result["schema_version"] == cartesian.RESULT
    assert set(result["arms"]) == set(comparison.ARMS)
    assert set(result["pool"]) == set(protocol["requests"])
    assert result["evaluation_labels_read"] == 0
    assert result["scientifically_validated"] is False
    for name, arm in result["arms"].items():
        assert arm["completion"]["status"] == "complete"
        assert arm["denominator"] == {"requested": 2, "evaluated": 2}
        assert {row["record_id"] for row in arm["rows"]} == set(protocol["requests"])
        assert arm["worker_complete"]["engine_calls"] == (0 if name == "similarity" else 2)
        if name == "similarity":
            assert all("registered_summary" not in row for row in arm["rows"])
            continue
        assert arm["score_quantity"] == workflow.SCORE_QUANTITY
        for row in arm["rows"]:
            summary = row["registered_summary"]
            assert row["score"] == summary["score"]
            assert summary["work"]["actual_force_calls"] == 1
            assert summary["work"]["known_completed_force_calls"] == 1
            assert summary["work"]["unknown_pending_attempts"] == 0
            assert summary["work"]["score_evaluation_calls"] == 2
            assert summary["candidate_source_admission_verified"] is False
            candidate_dir = run_dir / name / (comparison._sha(row["record_id"]) + ".cartesian")
            request = json.loads((candidate_dir / "request.json").read_bytes())
            assert request["schema_id"] == workflow.REQUEST_SCHEMA
            assert request["solver"] == protocol["cartesian_solver"]
            assert workflow.verify_output(request, candidate_dir)["structural_verification_passed"]
        counters = arm["registered_work"]["recorded_call_counters"]
        assert counters["actual_force_calls"] == 2
        assert counters["score_evaluation_calls"] == 4
    assert cartesian.verify_run(protocol, run_dir)["status"] == "verified"


def test_completed_verify_and_resume_do_not_execute_workers_forces_or_scores(completed, monkeypatch):
    protocol, run_dir, result = completed
    before = {path.relative_to(run_dir): path.read_bytes()
              for path in run_dir.rglob("*") if path.is_file()}
    _forbid_execution(monkeypatch)
    receipt = cartesian.verify_run(protocol, run_dir)
    assert receipt["status"] == "verified"
    assert receipt["execution_performed"] is False
    assert cartesian.run(protocol, run_dir, resume=True) == result
    after = {path.relative_to(run_dir): path.read_bytes()
             for path in run_dir.rglob("*") if path.is_file()}
    assert after == before


@pytest.mark.parametrize("change", ["row_summary", "missing_numerical_reservation"])
def test_resealed_work_tampering_or_missing_cartesian_history_is_rejected(
        completed, tmp_path, monkeypatch, change):
    protocol, original, result = completed
    run_dir = tmp_path / "copied-run"
    shutil.copytree(original, run_dir)
    row = result["arms"]["engine"]["rows"][0]
    rid_hash = comparison._sha(row["record_id"])
    if change == "row_summary":
        path = run_dir / "engine" / (rid_hash + ".row.json")
        wrapped = json.loads(path.read_bytes())
        wrapped["payload"]["registered_summary"]["work"]["actual_force_calls"] += 1
        wrapped["sha256"] = comparison._sha(wrapped["payload"])
        path.write_bytes(comparison._canonical(wrapped) + b"\n")
    else:
        (run_dir / "engine" / (rid_hash + ".cartesian") / "numerical-start-intent.json").unlink()
    _forbid_execution(monkeypatch)
    receipt = cartesian.verify_run(protocol, run_dir)
    assert receipt["status"] != "verified"
    assert receipt["exit_code"] != 0
    with pytest.raises((ValueError, ResearchError)):
        cartesian.run(protocol, run_dir, resume=True)


def test_interrupted_arm_forfeits_budget_without_restarting_candidate_work(completed, tmp_path, monkeypatch):
    protocol, original, _ = completed
    run_dir = tmp_path / "interrupted-copy"
    shutil.copytree(original, run_dir)
    (run_dir / "comparison.json").unlink()
    (run_dir / "engine" / "completion.json").unlink()
    _forbid_execution(monkeypatch)
    result = cartesian.run(protocol, run_dir, resume=True)
    completion = result["arms"]["engine"]["completion"]
    assert completion["status"] == "interrupted_budget_forfeited"
    assert completion["measured_process_wall_seconds"] is None
    assert completion["termination_overhead_seconds"] is None
    assert result["arms"]["engine"]["denominator"] == {"requested": 2, "evaluated": 2}
    assert cartesian.verify_run(protocol, run_dir)["status"] == "verified"


def test_expired_arm_budget_retains_every_candidate_in_denominator(tmp_path):
    protocol = _protocol(tmp_path / "input")
    protocol["budget_seconds_per_arm"] = .000001
    run_dir = tmp_path / "expired-run"
    result = cartesian.run(protocol, run_dir)
    for arm in result["arms"].values():
        assert arm["completion"]["status"] == "budget_exhausted"
        assert arm["denominator"]["requested"] == 2
        assert sum(count for key, count in arm["denominator"].items() if key != "requested") == 2
        assert {row["record_id"] for row in arm["rows"]} == set(protocol["requests"])
        assert all(row["score"] is None for row in arm["rows"])
    assert cartesian.verify_run(protocol, run_dir)["status"] == "verified"


@pytest.mark.parametrize("pending", ["force", "score"])
def test_interrupted_candidate_retains_unknown_reserved_work_without_retry(
        completed, tmp_path, monkeypatch, pending):
    protocol, original, _ = completed
    run_dir = tmp_path / ("pending-" + pending)
    shutil.copytree(original, run_dir)
    (run_dir / "comparison.json").unlink()
    engine_dir = run_dir / "engine"
    priority = json.loads((engine_dir / "priority.json").read_bytes())
    rid = priority["order"][0]
    rid_hash = comparison._sha(rid)
    candidate_intent = rid_hash + ".candidate-intent.json"
    retained = {"attempt.json", "worker.lock", "priority.json", "worker.log", candidate_intent}
    assert (engine_dir / candidate_intent).is_file()
    for path in engine_dir.iterdir():
        if path.name in retained:
            continue
        if path.is_dir():
            shutil.rmtree(path)  # Copied tiny synthetic test artifacts only.
        else:
            path.unlink()
    frozen = json.loads((run_dir / "frozen.json").read_bytes())["payload"]
    request = frozen["requests"][rid]
    candidate_dir = engine_dir / (rid_hash + ".cartesian")
    calls = []
    if pending == "force":
        original_evaluate = workflow.FixedReceptorEvaluator.evaluate

        def interrupt_force(*args, **kwargs):
            original_evaluate(*args, **kwargs)
            calls.append("force")
            raise KeyboardInterrupt("synthetic worker interruption after force evaluation")

        monkeypatch.setattr(workflow.FixedReceptorEvaluator, "evaluate", interrupt_force)
    else:
        def interrupt_score(*args, **kwargs):
            calls.append("score")
            raise KeyboardInterrupt("synthetic worker interruption during score evaluation")

        monkeypatch.setattr(ExplicitGraphScorer, "score_terms", interrupt_score)
    with pytest.raises(KeyboardInterrupt):
        workflow.evaluate(request, candidate_dir)
    assert calls == [pending]
    # Emulate a worker killed before outer invocation bookkeeping is durable;
    # the nested objective/score reservation survives and cannot become zero.
    (candidate_dir / "invocation-000000.end.json").unlink()
    _forbid_execution(monkeypatch)
    result = cartesian.run(protocol, run_dir, resume=True)
    arm = result["arms"]["engine"]
    assert arm["completion"]["status"] == "interrupted_budget_forfeited"
    assert arm["denominator"]["requested"] == 2
    assert arm["worker_complete"] is None
    retained_work = arm["registered_work"]
    assert retained_work["candidate_calls_without_returned_report"] is None
    assert retained_work["candidate_call_denominator_complete"] is False
    assert retained_work["all_candidate_molecular_work_recorded"] is False
    assert retained_work["known_candidate_reservations_without_report"] == 1
    partial = arm["cartesian_partial_work"][rid]
    assert partial["unfinished_invocations"] == 1
    assert partial["all_candidate_molecular_work_recorded"] is False
    if pending == "force":
        assert partial["numerical_work"]["actual_force_calls"] is None
        assert partial["numerical_work"]["unknown_pending_attempts"] == 1
        assert partial["numerical_work"]["known_completed_force_calls"] == 0
        assert partial["committed_score_calls"] == 1
    else:
        assert partial["unknown_score_attempts"] == 1
        assert partial["committed_score_calls"] == 0
    assert cartesian.verify_run(protocol, run_dir)["status"] == "verified"
    assert cartesian.run(protocol, run_dir, resume=True) == result
    assert calls == [pending]
