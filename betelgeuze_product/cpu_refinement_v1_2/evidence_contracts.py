"""Shared admission and cross-field checks; no scoring or filesystem writes.

These checks establish consistency of retained evidence, not authenticity or
independent physical validation. Missing legacy evidence is never synthesized.
"""
from __future__ import annotations

from dataclasses import fields, replace
from pathlib import PurePosixPath

from betelgeuze_engine_v2.docking import DockingBudget
from betelgeuze_product.cpu_refinement.refinement_comparison import (
    RefinementComparisonConfig, plan_refinement_comparison,
)
from .minimization import SolverConfig
from .provenance import ResearchError, canonical, exact_fields, finite, integer, require_digest
from .selection import SelectionConfig
from .work import STAGES
from .fixed_receptor import FIXED_REPORT_SCHEMA, FIXED_REQUEST_SCHEMA, FIXED_EVALUATOR_ID, FIXED_ATTEMPT_SCHEMA, verify_components

REPORT_SCHEMA = "cpu_extended_comparison/1.2.1"
LEGACY_REPORT_SCHEMA = "cpu_extended_comparison/1.2.0"
POLICY_ID = "valid_nonincreasing_refinement_with_explicit_convergence/1.0.0"


def same(actual, expected, name: str) -> None:
    if canonical(actual) != canonical(expected):
        raise ResearchError(f"{name} is inconsistent")


def boolean(value) -> bool:
    if type(value) is not bool:
        raise ResearchError("exact boolean required")
    return value


def count(value) -> int:
    return integer(value, 0, 2**63 - 1)


def execution_plan(budget_doc, solver_doc, comparison_doc):
    exact_fields(budget_doc, {f.name for f in fields(DockingBudget)})
    for name, value in budget_doc.items():
        if name == "translation_radius_angstrom":
            finite(value, nonnegative=True)
        else:
            count(value)
    budget = DockingBudget(**budget_doc)
    solver = SolverConfig.from_dict(solver_doc)
    exact_fields(comparison_doc, {f.name for f in fields(RefinementComparisonConfig)})
    comparison = RefinementComparisonConfig(**comparison_doc)
    before, after, bound = plan_refinement_comparison(budget, solver.minimization, comparison)
    effective_solver = replace(solver, minimization=replace(
        solver.minimization, max_iterations=budget.max_refinement_steps))
    return budget, solver, comparison, before, after, bound, effective_solver


def selection_config(document, top_k: int) -> SelectionConfig:
    exact_fields(document, set(SelectionConfig(top_k).to_dict()))
    result = SelectionConfig(document["top_k"], document["diversity_rmsd_angstrom"])
    same(document, result.to_dict(), "selection configuration")
    same(result.top_k, top_k, "selection K and budget K")
    return result


def request_binding(request: dict) -> dict:
    """Validate portable request metadata without reopening another host's paths."""
    names = {"schema_id", "backend", "receptor", "ligand", "parameters", "extensions",
             "solvation", "pocket", "receptor_margin_angstrom", "budget", "solver",
             "comparison", "selection"}
    fixed = request.get("schema_id") == FIXED_REQUEST_SCHEMA
    if fixed:
        names |= {"cross_parameters", "max_internal_increase_kcal_per_mol"}
    exact_fields(request, names)
    if (request["schema_id"] not in {"cpu_extended_comparison_request/1.2.0", FIXED_REQUEST_SCHEMA}
            or request["backend"] != "python_cpu_reference"):
        raise ResearchError("unsupported prepared request")
    budget, *_ = execution_plan(request["budget"], request["solver"], request["comparison"])
    if budget.candidate_count > 64:
        raise ResearchError("CLI candidate capacity exceeded")
    selection_config(request["selection"], budget.top_k)
    for name in (("receptor", "ligand", "parameters", "extensions", "solvation") + (("cross_parameters",) if fixed else ())):
        ref = request[name]
        if name == "solvation" and ref is None:
            continue
        exact_fields(ref, {"path", "sha256"})
        require_digest(ref["sha256"])
        if type(ref["path"]) is not str or not PurePosixPath(ref["path"]).is_absolute():
            raise ResearchError("retained input path must be absolute")
    pocket = request["pocket"]
    exact_fields(pocket, {"center_angstrom", "radius_angstrom", "coordinate_frame_id",
                          "source_artifact_sha256", "method_id", "method_version"})
    if type(pocket["center_angstrom"]) is not list or len(pocket["center_angstrom"]) != 3:
        raise ResearchError("pocket must have three coordinates")
    for value in pocket["center_angstrom"]:
        finite(value)
    for value in (pocket["radius_angstrom"], request["receptor_margin_angstrom"]):
        if finite(value) <= 0:
            raise ResearchError("positive pocket radius and margin required")
    require_digest(pocket["source_artifact_sha256"])
    for name in ("coordinate_frame_id", "method_id", "method_version"):
        if type(pocket[name]) is not str or not pocket[name].strip():
            raise ResearchError("explicit pocket identity required")
    if fixed:
        if finite(request["max_internal_increase_kcal_per_mol"], nonnegative=True) > 1.e6:
            raise ResearchError("ligand strain cap outside range")
    return {key: request[key] for key in sorted(names - {"budget", "solver", "comparison", "selection"})}


def verify_request_settings(request: dict, result: dict) -> None:
    binding = request_binding(request)
    fixed = request["schema_id"] == FIXED_REQUEST_SCHEMA
    same(result["schema_id"] == FIXED_REPORT_SCHEMA, fixed, "request/result objective")
    if fixed:
        same(request["max_internal_increase_kcal_per_mol"], result["max_internal_increase_kcal_per_mol"], "request/result strain cap")
    for name in ("budget", "solver", "comparison"):
        same(request[name], result[name], f"request/result {name}")
    selected = (result["selection_config"] if result["schema_id"] in {REPORT_SCHEMA, FIXED_REPORT_SCHEMA}
                else result["per_arm_selection"]["baseline"]["config"])
    same(request["selection"], selected, "request/result selection")
    if result["schema_id"] in {REPORT_SCHEMA, FIXED_REPORT_SCHEMA}:
        same(result["request_binding"], binding, "admitted input binding")


def verify_work(document: dict) -> dict:
    exact_fields(document, {"schema_id", "stages", "counters", "durations_are_inclusive",
                            "timing_is_numerical_identity"})
    if (document["schema_id"] != "cpu_execution_work/1.2.0"
            or document["durations_are_inclusive"] is not True
            or document["timing_is_numerical_identity"] is not False):
        raise ResearchError("invalid work semantics")
    stages, counters = document["stages"], document["counters"]
    if type(stages) is not dict or not set(stages) <= STAGES:
        raise ResearchError("unknown work stage")
    for row in stages.values():
        exact_fields(row, {"calls", "completed", "failed", "wall_ns", "cpu_ns"})
        for value in row.values():
            count(value)
        same(row["calls"], row["completed"] + row["failed"], "stage call accounting")
    if type(counters) is not dict or not set(counters) <= {"input_bytes_verified", "tangent_projection_sweeps",
                                                    "tangent_projection_completed", "tangent_projection_exhausted"}:
        raise ResearchError("unknown work counter")
    for value in counters.values():
        count(value)
    projection_keys = {"tangent_projection_sweeps", "tangent_projection_completed", "tangent_projection_exhausted"}
    present = projection_keys & set(counters)
    if present:
        if present != projection_keys:
            raise ResearchError("incomplete tangent projection observations")
        same(counters["tangent_projection_completed"] + counters["tangent_projection_exhausted"],
             stages.get("force.project", {}).get("completed", 0), "projection outcome counts")
    return stages


def calls(stages: dict, name: str, field: str = "calls") -> int:
    return stages.get(name, {}).get(field, 0)


def verify_numerical_work(document: dict, bound: int) -> None:
    exact_fields(document, {"force_evaluation_calls", "failed_force_evaluation_calls",
        "restart_verification_calls", "constraint_projection_calls", "work"})
    stages = verify_work(document["work"])
    for field, stage, metric in (
        ("force_evaluation_calls", "force.evaluate", "calls"),
        ("failed_force_evaluation_calls", "force.evaluate", "failed"),
        ("restart_verification_calls", "restart.verify", "calls"),
        ("constraint_projection_calls", "constraint.project", "calls"),
    ):
        count(document[field])
        same(document[field], calls(stages, stage, metric), field)
    if document["force_evaluation_calls"] > bound:
        raise ResearchError("force evaluation reservation exceeded")
    # This comparison path never resumes candidates; standalone solver work may.
    if document["restart_verification_calls"] != 0:
        raise ResearchError("comparison contains unexpected restart work")
    same(calls(stages, "force.evaluate"), calls(stages, "geometry.build", "completed"),
         "geometry/force calls")
    same(calls(stages, "force.project"), calls(stages, "force.evaluate", "completed"),
         "force/tangent calls")
    if calls(stages, "geometry.build") > calls(stages, "constraint.project", "completed"):
        raise ResearchError("geometry called without completed projection")


CHECK_BLOCKERS = {
    "proper_rotation": "rigid_rotation_not_proper_orthogonal",
    "bond_lengths_preserved": "bond_length_preservation_failed",
    "ligand_self_clash_free": "ligand_self_clash_detected",
    "receptor_ligand_clash_free": "receptor_ligand_clash_detected",
    "declared_chirality_preserved": "declared_chirality_not_preserved",
    "inside_declared_pocket": "pose_outside_declared_pocket",
    "element_vdw_ligand_overlap_free": "element_vdw_ligand_severe_overlap_detected",
    "element_vdw_receptor_overlap_free": "element_vdw_receptor_severe_overlap_detected",
}


def verify_pose_row(row: dict, atom_count: int) -> None:
    exact_fields(row, {"candidate_id", "coordinates_binary64_hex", "coordinates_sha256", "error_code",
        "error_message", "pose_valid", "pose_validity", "private_error_byte_length", "private_error_sha256",
        "problem_fingerprint_sha256", "proposal_fingerprint_sha256", "proposal_index", "refined",
        "result_proposal_fingerprint_sha256", "score", "search_space_fingerprint_sha256", "selection_eligible",
        "status", "succeeded", "terms", "validity_complete", "validity_context_fingerprint_sha256"})
    for name in ("succeeded", "refined", "pose_valid", "validity_complete", "selection_eligible"):
        boolean(row[name])
    if row["succeeded"] != (row["status"] == "success") or row["status"] not in {"success", "failure"}:
        raise ResearchError("row success/status mismatch")
    count(row["private_error_byte_length"])
    if not row["succeeded"]:
        if any(row[name] is not None for name in ("score", "pose_validity", "coordinates_sha256", "coordinates_binary64_hex")):
            raise ResearchError("failed row fabricated a result")
        if any(row[name] for name in ("pose_valid", "validity_complete", "selection_eligible")):
            raise ResearchError("failed row is selection eligible")
        return
    pose = row["pose_validity"]
    exact_fields(pose, {"valid", "checks", "evaluated_checks", "complete", "valid_within_evaluated_scope",
                        "measurements", "blockers", "not_evaluated_reasons", "claim_safe"})
    checks, evaluated = pose["checks"], pose["evaluated_checks"]
    exact_fields(checks, set(CHECK_BLOCKERS))
    exact_fields(evaluated, set(CHECK_BLOCKERS))
    for value in (*checks.values(), *evaluated.values()):
        boolean(value)
    complete = all(evaluated.values())
    valid_scope = all(checks[name] for name in checks if evaluated[name])
    valid = complete and valid_scope
    for name, value in (("complete", complete), ("valid_within_evaluated_scope", valid_scope),
                        ("valid", valid), ("claim_safe", False)):
        same(pose[name], value, f"detailed validity {name}")
    for name, value in (("validity_complete", complete), ("pose_valid", valid), ("selection_eligible", valid)):
        same(row[name], value, f"upper/detailed validity {name}")
    missing = {name for name in checks if not evaluated[name]}
    exact_fields(pose["not_evaluated_reasons"], missing)
    if any(type(reason) is not str or not reason for reason in pose["not_evaluated_reasons"].values()):
        raise ResearchError("missing unevaluated reason")
    expected = {CHECK_BLOCKERS[name] for name in checks if evaluated[name] and not checks[name]}
    blockers = pose["blockers"]
    if type(blockers) is not list or any(type(value) is not str for value in blockers) or set(blockers) != expected or len(set(blockers)) != len(blockers):
        raise ResearchError("validity blockers/checks mismatch")
    measurements = pose["measurements"]
    if type(measurements) is not dict:
        raise ResearchError("missing validity measurements")
    same(measurements.get("atom_count"), atom_count, "validity atom count")
    for name, value in measurements.items():
        if name.endswith("_count"):
            count(value)
        else:
            finite(value)
    for entity in ("ligand", "receptor"):
        name = f"element_vdw_{entity}_overlap_free"
        key = f"element_vdw_{entity}_severe_overlap_count"
        if evaluated[name]:
            same(checks[name], count(measurements[key]) == 0, "overlap observation/check")


def verify_execution_evidence(report: dict) -> None:
    """Recompute derived budgets/counts without confusing trials with actual work."""
    names = {"arms", "atom_count", "attempts", "authority_input_receipt_sha256", "budget", "claim_safe",
        "comparison", "customer_execution_allowed", "equal_elapsed_cpu_time_claimed", "evaluator",
        "failure_rows_retained", "final_selection", "force_evaluation_bound_per_candidate",
        "implementation_source_sha256", "mode", "paired_decisions", "per_arm_selection",
        "receptor_ligand_interaction_energy_minimized", "refinement_work", "report_sha256", "schema_id",
        "scientifically_validated", "solver", "timing_excludes", "timing_scope"}
    fixed = report["schema_id"] == FIXED_REPORT_SCHEMA
    if fixed:
        names.add("max_internal_increase_kcal_per_mol")
        if finite(report["max_internal_increase_kcal_per_mol"], nonnegative=True) > 1.e6:
            raise ResearchError("ligand strain cap outside range")
    if report["schema_id"] in {REPORT_SCHEMA, FIXED_REPORT_SCHEMA}:
        names |= {"selection_config", "selection_policy_id", "raw_per_arm_selection", "request_binding"}
        if report["request_binding"] is not None:
            combined = {**report["request_binding"], **{name: report[name] for name in ("budget", "solver", "comparison")},
                        "selection": report["selection_config"]}
            same(report["request_binding"], request_binding(combined), "request binding metadata")
            if fixed:
                same(combined["max_internal_increase_kcal_per_mol"], report["max_internal_increase_kcal_per_mol"], "bound strain cap")
        exact_fields(report["raw_per_arm_selection"], {"baseline", "refined"})
    exact_fields(report, names)
    exact_fields(report["arms"], {"baseline", "refined"})
    exact_fields(report["per_arm_selection"], {"baseline", "refined"})
    budget, solver, comparison, before, after, bound, effective = execution_plan(
        report["budget"], report["solver"], report["comparison"])
    same(report["mode"], comparison.mode, "comparison mode")
    same(report["force_evaluation_bound_per_candidate"], bound, "force bound")
    count(report["force_evaluation_bound_per_candidate"])
    for name in ("implementation_source_sha256", "authority_input_receipt_sha256", "report_sha256"):
        require_digest(report[name])
    evaluator_fields = {"evaluator_id", "parameter_fingerprint_sha256", "solvation_fingerprint_sha256"}
    if fixed:
        evaluator_fields |= {"receptor_system_sha256", "cross_parameter_fingerprint_sha256", "coordinate_frame_id"}
        for name in ("receptor_system_sha256", "cross_parameter_fingerprint_sha256"):
            require_digest(report["evaluator"][name])
        if type(report["evaluator"]["coordinate_frame_id"]) is not str or not report["evaluator"]["coordinate_frame_id"].strip():
            raise ResearchError("fixed receptor frame missing")
        if report["request_binding"] is not None:
            same(report["evaluator"]["coordinate_frame_id"], report["request_binding"]["pocket"]["coordinate_frame_id"], "fixed receptor frame")
    exact_fields(report["evaluator"], evaluator_fields)
    same(report["evaluator"]["evaluator_id"], FIXED_EVALUATOR_ID if fixed else "cpu_corrected_extended_reference/1.2.0", "evaluator")
    require_digest(report["evaluator"]["parameter_fingerprint_sha256"])
    if report["evaluator"]["solvation_fingerprint_sha256"] is not None:
        require_digest(report["evaluator"]["solvation_fingerprint_sha256"])
    same(report["failure_rows_retained"], True, "failure inclusion")
    same(report["receptor_ligand_interaction_energy_minimized"], fixed, "objective minimization scope")
    same(report["equal_elapsed_cpu_time_claimed"], False, "equal_elapsed_cpu_time_claimed")
    for name, planned in (("baseline", before), ("refined", after)):
        arm = report["arms"][name]
        fields_expected = {"candidate_count", "success_count", "failure_count", "valid_pose_count",
            "valid_pose_fraction_all_candidates", "work_units_reserved", "force_evaluations_reserved",
            "elapsed_seconds", "execution_work", "score_evaluation_calls", "failed_score_evaluation_calls",
            "rows", "actual_force_evaluation_calls"}
        if name == "refined":
            fields_expected.add("failed_force_evaluation_calls")
        exact_fields(arm, fields_expected)
        rows = arm["rows"]
        if type(rows) is not list:
            raise ResearchError("candidate rows must be a list")
        same(count(arm["candidate_count"]), planned.candidate_count, "planned candidate count")
        same(len(rows), planned.candidate_count, "candidate denominator")
        for index, row in enumerate(rows):
            same(count(row["proposal_index"]), index, "candidate ordering")
            if type(row["candidate_id"]) is not str or not row["candidate_id"]:
                raise ResearchError("nonempty candidate identity required")
            for key in ("proposal_fingerprint_sha256", "problem_fingerprint_sha256",
                        "search_space_fingerprint_sha256", "validity_context_fingerprint_sha256"):
                require_digest(row[key])
            verify_pose_row(row, report["atom_count"])
        for key in ("success_count", "failure_count", "valid_pose_count", "score_evaluation_calls",
                    "failed_score_evaluation_calls", "work_units_reserved", "force_evaluations_reserved",
                    "actual_force_evaluation_calls"):
            count(arm[key])
        same(arm["valid_pose_count"], sum(row["pose_valid"] for row in rows), "valid pose count")
        same(finite(arm["valid_pose_fraction_all_candidates"]), arm["valid_pose_count"] / len(rows), "valid fraction")
        finite(arm["elapsed_seconds"], nonnegative=True)
        reserve = 0 if name == "baseline" else len(rows) * bound
        same(arm["force_evaluations_reserved"], reserve, "force reservation")
        work = len(rows) * comparison.score_evaluation_weight + reserve * comparison.force_evaluation_weight
        same(arm["work_units_reserved"], work, "weighted work reservation")
        if comparison.work_units_per_arm is not None and work > comparison.work_units_per_arm:
            raise ResearchError("work limit exceeded")
        stages = verify_work(arm["execution_work"])
        same(arm["score_evaluation_calls"], calls(stages, "score.evaluate"), "score calls")
        same(arm["failed_score_evaluation_calls"], calls(stages, "score.evaluate", "failed"), "score failures")
        if not (arm["success_count"] <= calls(stages, "score.evaluate", "completed")
                <= arm["score_evaluation_calls"] <= len(rows)):
            raise ResearchError("score calls do not support observed rows")
        for stage in ("scorer.construct", "context.construct", "search.execute"):
            same(calls(stages, stage), 1, f"{stage} count")
            same(calls(stages, stage, "completed"), 1, f"{stage} completion")
    same(report["arms"]["baseline"]["actual_force_evaluation_calls"], 0, "baseline force calls")
    attempts, works = report["attempts"], report["refinement_work"]
    if type(attempts) is not list or type(works) is not list or len(works) != len(attempts) or len(works) != after.candidate_count:
        raise ResearchError("refinement work denominator mismatch")
    effective_doc = effective.to_dict()
    for attempt, work in zip(attempts, works, strict=True):
        fields_expected = {"schema_id", "candidate_id", "proposal_index", "source_proposal_fingerprint_sha256",
            "pre_coordinates_sha256", "pre_coordinates_binary64_hex", "evaluator", "solver",
            "implementation_source_sha256", "status", "receipt_sha256"}
        if attempt["status"] == "success":
            fields_expected |= {"post_coordinates_sha256", "post_coordinates_binary64_hex", "initial_energy",
                "final_energy", "energy_delta", "maximum_displacement_angstrom", "converged", "minimization_status",
                "max_tangent_force", "max_constraint_residual", "accepted_iterations", "evaluation_count", "checkpoint_sha256"}
        else:
            fields_expected |= {"public_error_code", "private_error_sha256", "private_error_byte_length"}
        if fixed and attempt["status"] == "success":
            fields_expected |= {"initial_objective_components", "final_objective_components"}
            verify_components(attempt["initial_objective_components"], attempt["initial_energy"])
            verify_components(attempt["final_objective_components"], attempt["final_energy"])
        exact_fields(attempt, fields_expected)
        same(attempt["schema_id"], FIXED_ATTEMPT_SCHEMA if fixed else "cpu_extended_refinement_attempt/1.2.0", "attempt schema")
        same(attempt["solver"], effective_doc, "effective candidate solver")
        verify_numerical_work(work, bound)
        counters = work["work"]["counters"]
        completed_projections = calls(work["work"]["stages"], "force.project", "completed")
        if report["schema_id"] in {REPORT_SCHEMA, FIXED_REPORT_SCHEMA} and completed_projections:
            if "tangent_projection_sweeps" not in counters:
                raise ResearchError("missing new tangent projection observations")
            if counters["tangent_projection_sweeps"] > completed_projections * solver.force_projection_max_sweeps:
                raise ResearchError("tangent projection sweep budget exceeded")
        if attempt["status"] == "success":
            for name in ("initial_energy", "final_energy", "energy_delta"):
                finite(attempt[name])
            for name in ("maximum_displacement_angstrom", "max_tangent_force", "max_constraint_residual"):
                finite(attempt[name], nonnegative=True)
            accepted = integer(attempt["accepted_iterations"], 0, budget.max_refinement_steps)
            evaluations = integer(attempt["evaluation_count"], 1, bound)
            require_digest(attempt["checkpoint_sha256"])
            boolean(attempt["converged"])
            status = attempt["minimization_status"]
            if status not in {"converged", "max_iterations_reached", "line_search_failed"}:
                raise ResearchError("invalid terminal minimization status")
            same(attempt["converged"], status == "converged", "minimization convergence")
            same(attempt["converged"], attempt["max_tangent_force"] <= solver.minimization.force_tolerance_kcal_per_mol_angstrom,
                 "force/convergence status")
            if status == "max_iterations_reached" and accepted != budget.max_refinement_steps:
                raise ResearchError("iteration exhaustion without exhausted budget")
            if status == "line_search_failed" and accepted >= budget.max_refinement_steps:
                raise ResearchError("line search failure after exhausted budget")
            if not accepted + 1 <= work["force_evaluation_calls"] <= evaluations:
                raise ResearchError("force calls do not support accepted iterations")
            # Logical trial ledger includes projections rejected BEFORE force calls.
            same(work["constraint_projection_calls"], evaluations, "trial/projection accounting")
            if attempt["maximum_displacement_angstrom"] > budget.max_refinement_steps * solver.minimization.maximum_atom_displacement_angstrom + 1.e-10:
                raise ResearchError("refinement displacement exceeded bound")
        elif attempt["status"] == "failure":
            count(attempt["private_error_byte_length"])
            require_digest(attempt["private_error_sha256"])
        else:
            raise ResearchError("unknown refinement status")
    refined = report["arms"]["refined"]
    count(refined["failed_force_evaluation_calls"])
    same(refined["actual_force_evaluation_calls"], sum(w["force_evaluation_calls"] for w in works), "force call total")
    same(refined["failed_force_evaluation_calls"], sum(w["failed_force_evaluation_calls"] for w in works), "failed force total")
