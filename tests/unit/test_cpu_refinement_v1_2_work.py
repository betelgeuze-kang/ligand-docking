"""Observed work survives failure; numerical identities exclude timing."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from betelgeuze_product.cpu_refinement_v1_2 import minimization, workflow
from betelgeuze_product.cpu_refinement_v1_2.evaluation import ExtendedEvaluator
from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError
from betelgeuze_product.cpu_refinement_v1_2.work import WorkMeter, verify_admitted_bytes
from tests.unit.test_cpu_refinement_v1_2_physics import near_linear
from tests.unit.test_cpu_refinement_v1_2_selection import real_run
from tests.unit.test_cpu_refinement_v1_2_workflow import request_fixture


def test_work_meter_records_failed_calls_without_exception_details():
    meter = WorkMeter()
    with pytest.raises(RuntimeError):
        with meter.measure("force.evaluate"):
            raise RuntimeError("private failure detail")
    row = meter.counts("force.evaluate")
    assert row["calls"] == row["failed"] == 1
    assert row["completed"] == 0
    assert row["wall_ns"] >= 0 and row["cpu_ns"] >= 0
    assert "private failure detail" not in json.dumps(meter.snapshot())
    copy = meter.snapshot()
    copy["stages"]["force.evaluate"]["calls"] = 999
    assert meter.counts("force.evaluate")["calls"] == 1
    with pytest.raises(ResearchError):
        with meter.measure("silent_unknown"):
            pass


def test_actual_force_calls_include_restart_verification():
    system, parameters, solvent, config = near_linear(charged=True)
    full_meter, pause_meter, resume_meter = WorkMeter(), WorkMeter(), WorkMeter()
    full = minimization.minimize_extended(system, parameters, config, solvation=solvent, meter=full_meter)
    paused = minimization.minimize_extended(system, parameters, config, solvation=solvent,
                                          meter=pause_meter, pause_after_accepted_iterations=1)
    resumed = minimization.minimize_extended(system, parameters, config, solvation=solvent,
                                           meter=resume_meter, checkpoint=paused.checkpoint)
    assert full.checkpoint.to_dict() == resumed.checkpoint.to_dict()
    assert full_meter.counts("force.evaluate")["calls"] == 4
    assert pause_meter.counts("force.evaluate")["calls"] + resume_meter.counts("force.evaluate")["calls"] == 5
    assert resume_meter.counts("restart.verify")["calls"] == 1
    assert resumed.checkpoint.to_dict()["evaluation_count"] == 4
    assert "wall_ns" not in json.dumps(full.checkpoint.to_dict())
    assert full.execution["work"] == full_meter.snapshot()


def test_caller_observes_failed_force_evaluation_when_solver_raises(monkeypatch):
    system, parameters, _, config = near_linear()
    meter = WorkMeter()
    def fail(*args):
        raise FloatingPointError("synthetic force failure")
    monkeypatch.setattr(ExtendedEvaluator, "evaluate", fail)
    with pytest.raises(ResearchError, match="not evaluable"):
        minimization.minimize_extended(system, parameters, config, meter=meter)
    assert meter.counts("force.evaluate")["calls"] == 1
    assert meter.counts("force.evaluate")["failed"] == 1
    assert meter.counts("constraint.project")["calls"] == 1


def test_failed_geometry_is_not_counted_as_force_evaluation(monkeypatch):
    system, parameters, _, config = near_linear()
    meter = WorkMeter()
    def fail(*args):
        raise RuntimeError("synthetic graph failure")
    monkeypatch.setattr(minimization, "build_compact_radius_graph", fail)
    with pytest.raises(RuntimeError):
        minimization.minimize_extended(system, parameters, config, meter=meter)
    assert meter.counts("force.evaluate")["calls"] == 0
    assert meter.counts("geometry.build")["failed"] == 1


def test_failed_constraint_trial_keeps_ledger_without_fake_force_call(monkeypatch):
    system, parameters, _, config = near_linear()
    config = replace(config, minimization=replace(config.minimization, max_backtracks=0))
    original = minimization.project_distance_constraints
    calls = 0
    def project(*args, **kwargs):
        nonlocal calls
        calls += 1
        result = original(*args, **kwargs)
        return result if calls == 1 else replace(result, status="max_iterations_reached", failure_code="synthetic_projection_failure")
    monkeypatch.setattr(minimization, "project_distance_constraints", project)
    result = minimization.minimize_extended(system, parameters, config)
    assert result.status == "line_search_failed"
    assert result.checkpoint.to_dict()["evaluation_count"] == 2
    assert result.execution["force_evaluation_calls"] == 1
    assert result.checkpoint.to_dict()["observations"][-1]["outcome"] == "rejected_projection"


def test_failed_force_attempts_preserve_reservation_and_exact_counts(monkeypatch):
    def fail(*args):
        raise FloatingPointError("private force failure")
    monkeypatch.setattr(ExtendedEvaluator, "evaluate", fail)
    report = real_run()
    work = report["refinement_work"]
    assert all(row["force_evaluation_calls"] == row["failed_force_evaluation_calls"] == 1 for row in work)
    assert report["arms"]["refined"]["actual_force_evaluation_calls"] == len(work)
    assert report["arms"]["refined"]["force_evaluations_reserved"] > len(work)
    assert report["arms"]["refined"]["failure_count"] == len(work)
    assert "private force failure" not in json.dumps(report)


def test_score_failures_and_successes_are_actual_calls(monkeypatch):
    from betelgeuze_engine_v2.docking.scorer_v1 import ChemistryPoseScorerV1
    original = ChemistryPoseScorerV1._score_terms_python
    def score(self, proposal):
        if proposal.refinement_receipt_sha256:
            raise RuntimeError("synthetic rescoring failure")
        return original(self, proposal)
    monkeypatch.setattr(ChemistryPoseScorerV1, "_score_terms_python", score)
    report = real_run()
    for name in ("baseline", "refined"):
        arm = report["arms"][name]
        assert arm["score_evaluation_calls"] == arm["candidate_count"]
        assert arm["failed_score_evaluation_calls"] == (arm["candidate_count"] if name == "refined" else 0)


def test_timing_does_not_change_numeric_attempts_or_selection():
    first, second = real_run(), real_run()
    assert first["attempts"] == second["attempts"]
    assert first["final_selection"] == second["final_selection"]
    assert first["refinement_work"][0]["work"]["timing_is_numerical_identity"] is False


def test_full_byte_recheck_does_not_decode_again(tmp_path, monkeypatch):
    request = request_fixture(tmp_path)
    original = workflow.run_comparison
    def run_then_disable_parser(*args, **kwargs):
        result = original(*args, **kwargs)
        def forbidden(*args):
            pytest.fail("post-admission bytes were parsed again")
        monkeypatch.setattr(workflow, "_bound", forbidden)
        return result
    monkeypatch.setattr(workflow, "run_comparison", run_then_disable_parser)
    report = workflow.run_request(request, tmp_path / "out")
    work = report["execution_work_before_report_publication"]
    assert work["stages"]["inputs.verify_bytes"]["calls"] == 4
    expected = sum(Path(request[name]["path"]).stat().st_size for name in ("receptor", "ligand", "parameters", "extensions"))
    assert work["counters"]["input_bytes_verified"] == expected
    complete = json.loads((tmp_path / "out" / "complete.json").read_bytes())
    assert complete["execution_work"]["stages"]["report.publish"]["calls"] == 1


@pytest.mark.parametrize("change", ["end_byte", "symlink", "digest", "extra", "relative"])
def test_byte_recheck_retains_full_hash_and_safe_file_contract(tmp_path, change):
    path = tmp_path / "input.json"
    raw = json.dumps({"data": [0] * 10000}).encode()
    path.write_bytes(raw)
    ref = {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()}
    assert verify_admitted_bytes(ref) == len(raw)
    if change == "end_byte":
        path.write_bytes(raw[:-1] + b" ")
    elif change == "symlink":
        link = tmp_path / "link.json"
        link.symlink_to(path)
        ref["path"] = str(link)
    elif change == "digest":
        ref["sha256"] = "0" * 64
    elif change == "extra":
        ref["silent"] = True
    else:
        ref["path"] = "input.json"
    with pytest.raises((ValueError, OSError)):
        verify_admitted_bytes(ref)


@pytest.mark.parametrize("field,value", [("execution_complete", False), ("scientifically_validated", True),
                                        ("candidate_failure_count", True), ("candidate_failure_count", 999)])
def test_completion_marker_claims_and_failure_counts_checked(tmp_path, field, value):
    workflow.run_request(request_fixture(tmp_path), tmp_path / "out")
    path = tmp_path / "out" / "complete.json"
    row = deepcopy(json.loads(path.read_bytes()))
    row[field] = value
    path.write_text(json.dumps(row))
    with pytest.raises(ResearchError, match="completion marker"):
        workflow.verify_output(tmp_path / "out")
