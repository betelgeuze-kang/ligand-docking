"""Registered-pose D3 execution for an externally admitted candidate policy.

This adapter binds declared prepared inputs to one unchanged initial pose and
the explicit-graph scorer. It does not admit an assay candidate, authenticate
an experimental source, assign source roles, or establish scientific validity.
One outer candidate call retains the baseline/refined decision of the existing
workflow; energy changes never replace the selected dimensionless pose score.
"""
from __future__ import annotations

from copy import deepcopy

from .comparison import run_comparison
from .evaluation import ExtendedEvaluator
from .evidence_contracts import request_binding, same, verify_request_settings
from .fixed_receptor import CrossParameters, FixedReceptorEnvironment, FixedReceptorEvaluator
from .provenance import ResearchError, canonical, digest, source_manifest
from .registered_pose import generate_registered_pose
from .scoring_profile import (
    EXPLICIT_MODEL, REGISTERED_PROPOSAL_POLICY, REGISTERED_REPORT_SCHEMA,
    REGISTERED_REQUEST_SCHEMA, descriptor, request_model, request_policy,
    scorer_class,
)
from .verification import verify_report
from .workflow import REQUEST_SCHEMA, _bound, load_request
from .work import verify_admitted_bytes


BACKEND = "registered_pose_fixed_receptor_d3_v1"
SCORE_QUANTITY = "uncalibrated_explicit_graph_scorer_dimensionless_minimize"
RESULT_SCHEMA = "policy_candidate_registered_pose_fixed_receptor_d3_v1"
FILE_FIELDS = ("receptor", "ligand", "parameters", "extensions", "cross_parameters")


def _request(request):
    if type(request) is not dict or request.get("schema_id") != REGISTERED_REQUEST_SCHEMA:
        raise ResearchError("policy_backend_requires_registered_pose_request")
    request_binding(request)
    return deepcopy(request)


def _verify_sources(request, sources):
    for name in FILE_FIELDS:
        verify_admitted_bytes(request[name])
    if source_manifest() != sources:
        raise ResearchError("registered_D3_policy_implementation_changed")


def _admit(request):
    sources = source_manifest()
    implementation = digest(sources)
    prepared = {key: value for key, value in request.items() if key != "cross_parameters"}
    prepared["schema_id"] = REQUEST_SCHEMA
    admitted = load_request(prepared, implementation)
    authority, receptor, ligand, parameters, budget, solver, _, _, _ = admitted
    fixed = FixedReceptorEnvironment(receptor, CrossParameters.from_dict(_bound(request["cross_parameters"])))
    fixed.validate_ligand(ligand, parameters.base_parameters)
    if fixed.cross.coordinate_frame_id != authority.pocket.coordinate_frame_id:
        raise ResearchError("registered_D3_policy_coordinate_frame_mismatch")
    # Construction validates the graph and includes reference intraligand
    # arithmetic. Admission makes no score_terms, force-evaluator or minimizer
    # calls; constructor work remains part of the caller's validation/setup cost.
    scorer = scorer_class(EXPLICIT_MODEL)(
        authority, receptor, ligand, implementation_source_sha256=implementation)
    _, receipt = generate_registered_pose(authority, budget, ligand)
    evaluator = FixedReceptorEvaluator(ExtendedEvaluator(parameters), fixed)
    binding = {
        "backend": BACKEND,
        "request_sha256": digest(request),
        "input_files": {name: dict(request[name]) for name in FILE_FIELDS},
        "implementation_sha256": implementation,
        "authority_sha256": authority.input_receipt_sha256,
        "parameters_sha256": parameters.fingerprint_sha256,
        "cross_parameters_sha256": fixed.cross.fingerprint_sha256,
        "pose_budget": budget.to_dict(),
        "solver": solver.to_dict(),
        "score_quantity": SCORE_QUANTITY,
        "score_descriptor": descriptor(EXPLICIT_MODEL).to_dict(),
        "scorer": {
            "feature_model_id": EXPLICIT_MODEL,
            "context": scorer.context.fingerprint_sha256,
            "config": scorer.config.fingerprint_sha256,
            "backend": scorer.backend_receipt_sha256,
        },
        "proposal_policy": receipt.to_dict(),
        "evaluator": evaluator.identity(),
        "candidate_source_admission_verified": False,
        "scientifically_validated": False,
    }
    _verify_sources(request, sources)
    return admitted, fixed, binding, sources


def input_binding(request):
    """Bind inputs without score_terms, force-evaluator or minimizer calls.

    Scorer initialization includes reference intraligand arithmetic; it is not
    a zero-arithmetic operation and its setup cost must remain accounted for.
    """
    return _admit(_request(request))[2]


def summarize(result, request=None):
    """Verify saved evidence against retained inputs without rescoring/refining.

    Source bytes are reopened to bind the proposal, evaluator and scorer to the
    request, including scorer initialization's reference intraligand arithmetic.
    Internal consistency is not proof of historical execution or an independent
    numerical/physical validation.
    """
    if (type(result) is not dict
            or set(result) != {"schema_version", "backend", "request", "comparison"}
            or result["schema_version"] != RESULT_SCHEMA or result["backend"] != BACKEND):
        raise ResearchError("invalid_registered_D3_policy_result")
    actual_request = _request(result["request"])
    if request is not None and canonical(_request(request)) != canonical(actual_request):
        raise ResearchError("registered_D3_policy_result_request_mismatch")
    report = result["comparison"]
    if type(report) is not dict or report.get("schema_id") != REGISTERED_REPORT_SCHEMA:
        raise ResearchError("registered_D3_policy_report_schema_mismatch")
    verify_request_settings(actual_request, report)
    verify_report(report)
    _, fixed, binding, _ = _admit(actual_request)
    for field, expected in (
        ("implementation_source_sha256", binding["implementation_sha256"]),
        ("authority_input_receipt_sha256", binding["authority_sha256"]),
        ("proposal_policy", binding["proposal_policy"]),
        ("scorer", binding["scorer"]),
        ("evaluator", binding["evaluator"]),
        ("cross_parameters", fixed.cross.to_dict()),
    ):
        same(report[field], expected, "registered D3 request/report " + field)
    if report["receptor_ligand_interaction_energy_minimized"] is not True:
        raise ResearchError("registered_D3_policy_missing_fixed_environment")
    selected = report["final_selection"]["selected_candidates"]
    attempts = report["attempts"]
    return {
        "status": "evaluated" if selected else "failed",
        "reason": None if selected else "no_policy_eligible_D3_or_original_pose",
        "score": min((row["score"] for row in selected), default=None),
        "score_quantity": SCORE_QUANTITY,
        "score_descriptor": binding["score_descriptor"],
        "proposal_policy_id": REGISTERED_PROPOSAL_POLICY,
        "selected_candidates": deepcopy(selected),
        "refinement_attempts": len(attempts),
        "refinement_failures": sum(a["status"] != "success" for a in attempts),
        "refinement_converged": sum(a["status"] == "success" and a["converged"] for a in attempts),
        "original_selected_count": sum(row["variant"] == "baseline" for row in selected),
        "refined_selected_count": sum(row["variant"] == "refined" for row in selected),
        "work": {
            "actual_force_evaluation_calls": report["arms"]["refined"]["actual_force_evaluation_calls"],
            "failed_force_evaluation_calls": report["arms"]["refined"]["failed_force_evaluation_calls"],
            "score_evaluation_calls": sum(a["score_evaluation_calls"] for a in report["arms"].values()),
            "force_evaluations_reserved": report["arms"]["refined"]["force_evaluations_reserved"],
            "pose_candidates_in_both_arms": sum(a["candidate_count"] for a in report["arms"].values()),
        },
        "physical_affinity_computed": False,
        "candidate_source_admission_verified": False,
        "scientifically_validated": False,
    }


def evaluate(request):
    request = _request(request)
    admitted, fixed, _, sources = _admit(request)
    authority, receptor, ligand, parameters, budget, solver, _, comparison, selection = admitted
    report = run_comparison(
        authority, budget, receptor_system=receptor, ligand_system=ligand,
        parameters=parameters, solver=solver, comparison=comparison, selection=selection,
        fixed_environment=fixed, scoring_model=request_model(request),
        proposal_policy=request_policy(request),
    )
    report["request_binding"] = request_binding(request)
    report["report_sha256"] = digest({key: value for key, value in report.items() if key != "report_sha256"})
    _verify_sources(request, sources)
    result = {"schema_version": RESULT_SCHEMA, "backend": BACKEND,
              "request": request, "comparison": report}
    summarize(result, request=request)
    return result
