"""Explicit D3 backend for the existing budgeted candidate-policy runner.

One outer candidate call performs the existing matched baseline/D3 pose search.
The score is uncalibrated ScorerV1 on the actually selected coordinates, never
cross energy or affinity. No chemistry/parameters are inferred or migrated.
"""
from __future__ import annotations

from .comparison import run_comparison
from .evidence_contracts import request_binding, verify_request_settings
from .fixed_receptor import CrossParameters, FixedReceptorEnvironment, FIXED_REQUEST_SCHEMA
from .provenance import ResearchError, canonical, digest, source_manifest
from .verification import verify_report
from .workflow import REQUEST_SCHEMA, load_request, _bound
from .work import verify_admitted_bytes

BACKEND = "fixed_receptor_d3_v1"
SCORE_QUANTITY = "uncalibrated_scorer_v1_dimensionless_minimize"
RESULT_SCHEMA = "policy_candidate_fixed_receptor_d3_v1"
FILE_FIELDS = ("receptor", "ligand", "parameters", "extensions", "cross_parameters")


def _admit(request):
    request_binding(request)
    if request["schema_id"] != FIXED_REQUEST_SCHEMA or request["solvation"] is not None:
        raise ResearchError("policy_backend_requires_explicit_fixed_receptor_request")
    if request["comparison"]["mode"] != "same_candidates":
        raise ResearchError("D3_policy_backend_requires_matched_source_poses")
    sources = source_manifest()
    implementation = digest(sources)
    prepared = {key: value for key, value in request.items() if key != "cross_parameters"}
    prepared["schema_id"] = REQUEST_SCHEMA
    admitted = load_request(prepared, implementation)
    authority, receptor, ligand, parameters, _, _, _, _, _ = admitted
    fixed = FixedReceptorEnvironment(receptor, CrossParameters.from_dict(_bound(request["cross_parameters"])))
    fixed.validate_ligand(ligand, parameters.base_parameters)
    if fixed.cross.coordinate_frame_id != authority.pocket.coordinate_frame_id:
        raise ResearchError("D3_policy_backend_coordinate_frame_mismatch")
    return admitted, fixed, sources


def input_binding(request):
    """Admit complete state/parameters before a worker budget; run no physics."""
    admitted, fixed, sources = _admit(request)
    authority, _, _, parameters, budget, solver, _, _, _ = admitted
    return {"backend": BACKEND, "request_sha256": digest(request),
        "input_files": {name: dict(request[name]) for name in FILE_FIELDS},
        "implementation_sha256": digest(sources), "authority_sha256": authority.input_receipt_sha256,
        "parameters_sha256": parameters.fingerprint_sha256,
        "cross_parameters_sha256": fixed.cross.fingerprint_sha256,
        "pose_budget": budget.to_dict(), "solver": solver.to_dict(), "score_quantity": SCORE_QUANTITY}


def summarize(result, *, request=None):
    if (type(result) is not dict or set(result) != {"schema_version", "backend", "request", "comparison"}
            or result["schema_version"] != RESULT_SCHEMA or result["backend"] != BACKEND):
        raise ResearchError("invalid_D3_policy_result")
    actual_request = result["request"]
    if request is not None and canonical(request) != canonical(actual_request):
        raise ResearchError("D3_policy_result_request_mismatch")
    report = result["comparison"]
    verify_request_settings(actual_request, report)
    verify_report(report)
    if report["receptor_ligand_interaction_energy_minimized"] is not True:
        raise ResearchError("D3_policy_result_missing_fixed_environment")
    selected = report["final_selection"]["selected_candidates"]
    attempts = report["attempts"]
    score = min((row["score"] for row in selected), default=None)
    return {"status": "evaluated" if selected else "failed",
        "reason": None if selected else "no_policy_eligible_D3_or_original_pose",
        "score": score, "score_quantity": SCORE_QUANTITY,
        "selected_candidates": selected,
        "refinement_attempts": len(attempts),
        "refinement_failures": sum(a["status"] != "success" for a in attempts),
        "refinement_converged": sum(a["status"] == "success" and a["converged"] for a in attempts),
        "original_selected_count": sum(row["variant"] == "baseline" for row in selected),
        "refined_selected_count": sum(row["variant"] == "refined" for row in selected),
        "work": {"actual_force_evaluation_calls": report["arms"]["refined"]["actual_force_evaluation_calls"],
            "failed_force_evaluation_calls": report["arms"]["refined"]["failed_force_evaluation_calls"],
            "score_evaluation_calls": sum(a["score_evaluation_calls"] for a in report["arms"].values()),
            "force_evaluations_reserved": report["arms"]["refined"]["force_evaluations_reserved"],
            "pose_candidates_in_both_arms": sum(a["candidate_count"] for a in report["arms"].values())},
        "physical_affinity_computed": False}


def evaluate(request):
    admitted, fixed, sources = _admit(request)
    authority, receptor, ligand, parameters, budget, solver, _, comparison, selection = admitted
    report = run_comparison(authority, budget, receptor_system=receptor, ligand_system=ligand,
        parameters=parameters, solver=solver, comparison=comparison, selection=selection,
        fixed_environment=fixed)
    report["request_binding"] = request_binding(request)
    report["report_sha256"] = digest({key: value for key, value in report.items() if key != "report_sha256"})
    for name in FILE_FIELDS:
        verify_admitted_bytes(request[name])
    if source_manifest() != sources:
        raise ResearchError("D3_policy_implementation_changed")
    result = {"schema_version": RESULT_SCHEMA, "backend": BACKEND, "request": request, "comparison": report}
    summarize(result, request=request)
    return result
