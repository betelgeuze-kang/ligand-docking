"""D1 regressions: rehashed contradictions, valid failures, legacy and admission."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from betelgeuze_product.cpu_refinement_v1_2 import workflow
from betelgeuze_product.cpu_refinement_v1_2.evidence_contracts import LEGACY_REPORT_SCHEMA
from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError, digest
from betelgeuze_product.cpu_refinement_v1_2.verification import verify_report
from tests.unit.test_cpu_refinement_v1_2_selection import real_run
from tests.unit.test_cpu_refinement_v1_2_workflow import request_fixture


@pytest.fixture(scope="module")
def original():
    return real_run()


def seal(report):
    report["report_sha256"] = digest({key: value for key, value in report.items() if key != "report_sha256"})
    return report


def reseal_attempt(attempt):
    attempt["receipt_sha256"] = digest({key: value for key, value in attempt.items() if key != "receipt_sha256"})


@pytest.mark.parametrize("change", [
    "validity", "overlap", "blocker", "unevaluated", "negative_force", "ratio", "valid_count",
    "budget", "solver", "missing_work", "weight", "mode", "fractional_count", "boolean_count",
    "unknown_stage", "negative_time", "stage_total", "force_total", "force_failed_total",
    "numerical_count", "restart", "calls_without_geometry", "unknown_field", "missing_field",
    "policy", "bound", "reservation", "force_reservation", "candidate_index", "descriptor",
    "attempt_solver", "attempt_convergence", "accepted_count", "trial_count", "negative_force_value",
    "overlap_count", "score_count", "selection_config", "timing_semantics",
])
def test_rehashed_contradiction_rejected(original, change):
    report = deepcopy(original)
    arm = report["arms"]["refined"]
    row = next(row for row in report["arms"]["baseline"]["rows"] if row["selection_eligible"])
    work = report["refinement_work"][0]
    if change == "validity":
        row["pose_validity"]["valid"] = False
    elif change == "overlap":
        row["pose_validity"]["checks"]["receptor_ligand_clash_free"] = False
    elif change == "blocker":
        row["pose_validity"]["blockers"] = ["receptor_ligand_clash_detected"]
    elif change == "unevaluated":
        row["pose_validity"]["evaluated_checks"]["proper_rotation"] = False
    elif change == "negative_force":
        arm["actual_force_evaluation_calls"] = -1
    elif change == "ratio":
        arm["valid_pose_fraction_all_candidates"] = 2.5
    elif change == "valid_count":
        arm["valid_pose_count"] += 1
    elif change == "budget":
        report["budget"]["candidate_count"] = 1
    elif change == "solver":
        report["solver"]["minimization"]["max_iterations"] = 1
    elif change == "missing_work":
        report["refinement_work"] = []
    elif change == "weight":
        report["comparison"]["force_evaluation_weight"] = -1
    elif change == "mode":
        report["comparison"]["mode"] = "equal_work_budget"
        report["comparison"]["work_units_per_arm"] = 100
    elif change in {"fractional_count", "boolean_count"}:
        arm["candidate_count"] = 4.0 if change == "fractional_count" else True
    elif change == "unknown_stage":
        work["work"]["stages"]["unobserved"] = {}
    elif change == "negative_time":
        work["work"]["stages"]["force.evaluate"]["wall_ns"] = -1
    elif change == "stage_total":
        work["work"]["stages"]["force.evaluate"]["completed"] += 1
    elif change in {"force_total", "force_failed_total", "score_count"}:
        name = {"force_total": "actual_force_evaluation_calls", "force_failed_total": "failed_force_evaluation_calls",
                "score_count": "score_evaluation_calls"}[change]
        arm[name] += 1
    elif change == "numerical_count":
        work["force_evaluation_calls"] += 1
    elif change == "restart":
        work["restart_verification_calls"] = 1
    elif change == "calls_without_geometry":
        work["work"]["stages"].pop("geometry.build")
    elif change == "unknown_field":
        report["silent_default"] = True
    elif change == "missing_field":
        del report["refinement_work"]
    elif change == "policy":
        report["selection_policy_id"] = "relaxed"
    elif change == "bound":
        report["force_evaluation_bound_per_candidate"] += 1
    elif change in {"reservation", "force_reservation"}:
        arm["work_units_reserved" if change == "reservation" else "force_evaluations_reserved"] -= 1
    elif change == "candidate_index":
        arm["rows"][0]["proposal_index"] = True
    elif change == "descriptor":
        report["per_arm_selection"]["baseline"]["score_descriptor"]["direction"] = "maximize"
    elif change.startswith("attempt_") or change in {"accepted_count", "trial_count", "negative_force_value"}:
        attempt = report["attempts"][0]
        if change == "attempt_solver":
            attempt["solver"]["minimization"]["max_iterations"] = 1
        elif change == "attempt_convergence":
            attempt["converged"] = not attempt["converged"]
        elif change == "accepted_count":
            attempt["accepted_iterations"] = 99
        elif change == "trial_count":
            attempt["evaluation_count"] += 1
        else:
            attempt["max_tangent_force"] = -1
        reseal_attempt(attempt)
    elif change == "overlap_count":
        row["pose_validity"]["measurements"]["element_vdw_receptor_severe_overlap_count"] = 10
    elif change == "selection_config":
        report["selection_config"]["top_k"] = 1
    else:
        work["work"]["timing_is_numerical_identity"] = True
    with pytest.raises(ResearchError):
        verify_report(seal(report))


def test_raw_and_admitted_equal_budget_lists_are_distinct():
    report = real_run(equal_budget=True)
    assert report["comparison"]["require_convergence_for_selection"] is True
    raw = report["raw_per_arm_selection"]["refined"]["selected_candidates"]
    attempts = {row["candidate_id"]: row for row in report["attempts"]}
    assert any(not attempts[row["candidate_id"]]["converged"] for row in raw)
    selected = report["per_arm_selection"]["refined"]["selected_candidates"]
    assert all(attempts[row["candidate_id"]]["converged"] for row in selected)
    assert report["final_selection"] is None
    verify_report(report)


def test_explicit_exploratory_policy_remains_supported(original):
    from betelgeuze_product.cpu_refinement_v1_2.selection import refinement_admissible
    row = original["arms"]["refined"]["rows"][1]
    attempt = original["attempts"][1]
    assert not attempt["converged"] and row["selection_eligible"]
    assert not refinement_admissible(row, attempt, True)
    assert refinement_admissible(row, attempt, False)


def test_legacy_readability_does_not_pretend_new_policy_was_applied(original):
    legacy = deepcopy(original)
    legacy["schema_id"] = LEGACY_REPORT_SCHEMA
    legacy["per_arm_selection"] = legacy.pop("raw_per_arm_selection")
    for name in ("selection_config", "selection_policy_id", "request_binding"):
        legacy.pop(name)
    result = verify_report(seal(legacy))
    assert result["legacy_per_arm_selection_is_diagnostic"] is True
    assert result["input_binding_evidence_present"] is False
    legacy["refinement_work"] = []
    with pytest.raises(ResearchError):
        verify_report(seal(legacy))


@pytest.mark.parametrize("change", ["seed", "solver", "comparison", "selection", "input", "pocket"])
def test_request_semantics_checked_even_after_outer_rehash(tmp_path, change):
    out = tmp_path / "out"
    workflow.run_request(request_fixture(tmp_path), out)
    request = json.loads((out / "request.json").read_bytes())
    report = json.loads((out / "report.json").read_bytes())
    if change == "seed":
        request["budget"]["seed"] += 987
    elif change == "solver":
        request["solver"]["minimization"]["max_iterations"] += 1
    elif change == "comparison":
        request["comparison"]["require_convergence_for_selection"] = False
    elif change == "selection":
        request["selection"]["diversity_rmsd_angstrom"] += 1
    elif change == "input":
        request["ligand"]["sha256"] = "a" * 64
    else:
        request["pocket"]["center_angstrom"][0] += 1
    report["request_sha256"] = digest(request)
    (out / "request.json").write_text(json.dumps(request))
    data = json.dumps(report).encode()
    (out / "report.json").write_bytes(data)
    completion = json.loads((out / "complete.json").read_bytes())
    completion["report_sha256"] = hashlib.sha256(data).hexdigest()
    (out / "complete.json").write_text(json.dumps(completion))
    with pytest.raises(ResearchError):
        workflow.verify_output(out)


def test_readonly_verification_needs_no_original_input_files(tmp_path):
    request = request_fixture(tmp_path)
    out = tmp_path / "out"
    workflow.run_request(request, out)
    for name in ("receptor", "ligand", "parameters", "extensions"):
        Path(request[name]["path"]).unlink()
    before = {p.name: p.read_bytes() for p in out.iterdir() if p.is_file()}
    assert workflow.verify_output(out)["input_binding_evidence_present"] is True
    assert before == {p.name: p.read_bytes() for p in out.iterdir() if p.is_file()}


def test_publication_work_cannot_be_silently_changed(tmp_path):
    out = tmp_path / "out"
    workflow.run_request(request_fixture(tmp_path), out)
    path = out / "complete.json"
    completion = json.loads(path.read_bytes())
    completion["execution_work"]["stages"]["force.evaluate"] = {
        "calls": 1, "completed": 1, "failed": 0, "wall_ns": 10, "cpu_ns": 10}
    path.write_text(json.dumps(completion))
    with pytest.raises(ResearchError):
        workflow.verify_output(out)


@pytest.mark.parametrize("field", ["tangent_projection_sweeps", "tangent_projection_completed", "tangent_projection_exhausted"])
def test_tangent_observation_corruption_rejected(original, field):
    report = deepcopy(original)
    counters = report["refinement_work"][0]["work"]["counters"]
    counters[field] += 1_000_000
    with pytest.raises(ResearchError):
        verify_report(seal(report))


def test_new_report_cannot_drop_tangent_observations(original):
    report = deepcopy(original)
    report["refinement_work"][0]["work"]["counters"] = {}
    with pytest.raises(ResearchError):
        verify_report(seal(report))
