"""Opt-in Cartesian registered D3 policy bridge outside the frozen solver sources.

Candidate chemistry and original charge-token admission belong to the outer
native comparator. This bridge executes only an explicitly converted 1.3
request and replays retained score and numerical evidence without rescoring.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from .cpu_refinement_v1_2.provenance import ResearchError, canonical
from .cpu_refinement_v1_2.scoring_profile import REGISTERED_PROPOSAL_POLICY
from .cpu_refinement_v1_2.work import WorkMeter
from .cpu_refinement_v1_3 import workflow

BACKEND = "registered_cartesian_pose_fixed_receptor_d3_v4"
RESULT_SCHEMA = "policy_candidate_registered_cartesian_pose_d3_v4"
SCORE_QUANTITY = workflow.SCORE_QUANTITY
WORK_KEYS = (*workflow.CALL_FIELDS, "known_completed_force_calls",
             "unknown_pending_attempts", "score_evaluation_calls",
             "force_evaluations_reserved", "pose_candidates_in_both_arms")


def input_binding(request):
    return workflow.input_binding(request)


def _result(value, request=None):
    if (type(value) is not dict or set(value) != {
            "schema_version", "backend", "request", "comparison", "invocation"}
            or value["schema_version"] != RESULT_SCHEMA or value["backend"] != BACKEND):
        raise ResearchError("invalid_registered_Cartesian_policy_result")
    actual = workflow._request(value["request"])[0]
    if request is not None and canonical(actual) != canonical(workflow._request(request)[0]):
        raise ResearchError("registered_Cartesian_policy_result_request_mismatch")
    report = value["comparison"]
    workflow._check_seal(report, "result_sha256")
    if (report.get("schema_id") != workflow.RESULT_SCHEMA
            or report.get("execution_complete") is not True):
        raise ResearchError("complete_registered_Cartesian_result_required")
    invocation = value["invocation"]
    if (type(invocation) is not dict
            or invocation.get("schema_id") != workflow.RESULT_SCHEMA + "/invocation"
            or invocation.get("completed_result_sha256") != report["result_sha256"]):
        raise ResearchError("registered_Cartesian_invocation_result_mismatch")
    return actual, report


def summarize(value, request=None, *, run_dir):
    """Require durable evidence, original files and live geometry; no molecular calls."""
    actual, report = _result(value, request)
    directory = Path(run_dir).absolute()
    verified = workflow.verify_output(actual, directory)
    if (verified["result_sha256"] != report["result_sha256"]
            or workflow._read_json(directory / "result.json") != report):
        raise ResearchError("registered_Cartesian_durable_result_mismatch")
    index = value["invocation"].get("index")
    if type(index) is not int or index < 0:
        raise ResearchError("registered_Cartesian_invocation_index_invalid")
    if workflow._read_json(directory / f"invocation-{index:06d}.end.json") != value["invocation"]:
        raise ResearchError("registered_Cartesian_durable_invocation_mismatch")
    binding = input_binding(actual)
    if binding != report["binding"]:
        raise ResearchError("registered_Cartesian_binding_mismatch")
    selected = report["final_selection"]["selected_candidates"]
    attempt = report["attempt"]
    work = {key: report["force_work"][key]
            for key in (*workflow.CALL_FIELDS, "known_completed_force_calls", "unknown_pending_attempts")}
    work.update(score_evaluation_calls=report["score_calls"],
                force_evaluations_reserved=binding["solver"]["max_objective_attempts"]
                + binding["solver"]["max_restart_verifications"],
                pose_candidates_in_both_arms=2)
    return {
        "status": "evaluated" if selected else "failed",
        "reason": None if selected else "no_policy_eligible_D3_or_original_pose",
        "score": min((row["score"] for row in selected), default=None),
        "score_quantity": SCORE_QUANTITY, "score_descriptor": binding["score_descriptor"],
        "proposal_policy_id": REGISTERED_PROPOSAL_POLICY,
        "selected_candidates": deepcopy(selected), "refinement_attempts": 1,
        "refinement_failures": int(attempt["status"] != "success"),
        "refinement_converged": int(attempt["status"] == "success" and attempt["converged"]),
        "original_selected_count": sum(row["variant"] == "baseline" for row in selected),
        "refined_selected_count": sum(row["variant"] == "refined" for row in selected),
        "work": work,
        "numerical_status": report["numerical_result"]["status"],
        "numerical_timings_ns": deepcopy(report["numerical_result"]["timings_ns"]),
        "score_evaluation_work": {arm: None if receipt is None else deepcopy(receipt["work"])
                                  for arm, receipt in report["score_receipts"].items()},
        "workflow_invocation_work": {key: deepcopy(value["invocation"][key]) for key in (
            "new_numerical_call_counts", "new_force_calls", "score_work",
            "setup_and_verification_work", "whole_wall_ns_before_receipt_publication")},
        "durations_are_inclusive_do_not_sum": True,
        "physical_affinity_computed": False, "candidate_source_admission_verified": False,
        "scientifically_validated": False,
    }


def evaluate(request, run_dir, *, resume=False):
    actual = workflow._request(request)[0]
    outcome = workflow.evaluate(actual, run_dir, resume=resume)
    if not outcome["result"]["execution_complete"]:
        raise ResearchError("terminal_registered_Cartesian_policy_result_required")
    result = {"schema_version": RESULT_SCHEMA, "backend": BACKEND,
              "request": actual, "comparison": outcome["result"],
              "invocation": outcome["invocation"]}
    summarize(result, request=actual, run_dir=run_dir)
    return result


def inspect_partial_work(request, run_dir):
    """Retain unknown calls after interruption; a saved prefix is only known work.

    Missing request/binding/numerical evidence is never a zero-cost claim.
    The caller forfeits this arm budget instead of rerunning this candidate.
    """
    directory = Path(run_dir).absolute()
    result = {"numerical_work": None, "numerical_timings_ns": None,
              "committed_score_work": {}, "committed_score_calls": 0,
              "unknown_score_attempts": None, "unfinished_invocations": None,
              "all_candidate_molecular_work_recorded": False,
              "reason": None, "scoring_reexecuted": False,
              "numerical_evaluation_reexecuted": False}
    try:
        admitted = workflow._admit(request, WorkMeter())
        if (workflow._read_json(directory / "request.json") != admitted.request
                or workflow._read_json(directory / "binding.json") != admitted.binding):
            raise ResearchError("partial_Cartesian_input_binding_mismatch")
        indices, unfinished, problems = workflow._invocation_inventory(directory)
        workflow._validate_invocation_history(directory, admitted.request, indices, problems)
        result["unfinished_invocations"] = unfinished
        # Reserved but uncommitted scoring is unknown even if its numerical
        # sibling has a complete prefix. Never reissue a reserved score call.
        unknown = 0
        counters = workflow._counters()
        for arm in ("baseline", "refined"):
            intent = directory / f"{arm}-score-intent.json"
            receipt = directory / f"{arm}-score.json"
            if intent.exists() and not receipt.exists():
                unknown += 1
            elif receipt.exists():
                if not intent.exists():
                    raise ResearchError("partial_Cartesian_score_intent_missing")
                if arm == "baseline":
                    current = admitted.proposal
                else:
                    numerical = workflow._numerical_verify(admitted, directory)
                    current = workflow._refined(admitted, workflow._attempt(admitted, numerical))
                workflow._score(admitted, directory, arm, current, execute=False, counters=counters)
                result["committed_score_calls"] += 1
                result["committed_score_work"][arm] = deepcopy(workflow._read_json(receipt)["work"])
        result["unknown_score_attempts"] = unknown
        reservation = directory / "numerical-start-intent.json"
        if reservation.exists() or (directory / "numerical").exists():
            workflow._numerical_reservation(admitted, directory)
            numerical = workflow._numerical_verify(admitted, directory)
            result["numerical_work"] = deepcopy(numerical["work"])
            result["numerical_timings_ns"] = deepcopy(numerical["timings_ns"])
        unresolved = workflow._unresolved_numerical_invocations(directory, indices)
        if unfinished or unresolved or unknown:
            result["reason"] = "interrupted_candidate_work_not_fully_observed"
        workflow._intact(admitted, WorkMeter())
    except (OSError, ValueError, TypeError, KeyError, OverflowError) as exc:
        if isinstance(getattr(exc, "work", None), dict):
            result["numerical_work"] = deepcopy(exc.work)
        result["reason"] = "unverified_partial_work:" + type(exc).__name__ + ":" + str(exc)
    return result
