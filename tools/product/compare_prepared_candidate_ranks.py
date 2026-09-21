"""Prespecified rank evaluation layered on the existing four-arm CPU runner.

The runner, training/role guards, engine and binary-label evaluator are unchanged.
This adapter freezes comparisons before any predictions and reads concentration
outcomes only after revalidating completed, source-bound predictions and costs.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
from pathlib import Path
import time

from betelgeuze_engine.product import censored_rank_metrics as legacy_metric
from betelgeuze_engine.product import paired_rank_metrics as metric
from betelgeuze_product import public_assay_components, residual_evidence
from tools.product import compare_prepared_candidate_policies as runner

PLAN_SCHEMA = "prepared_rank_plan_v1"
DIRECTIONS = {"similarity": "higher_is_better", "engine": "lower_is_better",
              "ai_engine": "lower_is_better", "similarity_engine": "lower_is_better"}


def _implementations():
    return {name: hashlib.sha256(Path(path).read_bytes()).hexdigest() for name, path in (
        ("adapter", __file__), ("metrics", metric.__file__), ("legacy_metrics", legacy_metric.__file__),
        ("runner", runner.__file__), ("components", public_assay_components.__file__),
        ("residual_evidence", residual_evidence.__file__))}


def _plan(plan, frozen):
    fields = {"schema_version", "target_annotation", "endpoint", "unit", "domain_id", "assay_ids",
              "comparisons", "score_directions", "max_pair_work"}
    if type(plan) is not dict or set(plan) != fields or plan["schema_version"] != PLAN_SCHEMA:
        raise ValueError("invalid_rank_plan")
    if (plan["endpoint"] not in {"IC50", "Ki", "Kd"} or plan["unit"] != "nM"
            or any(type(plan[key]) is not str or not plan[key].strip() for key in ("target_annotation", "domain_id"))
            or plan["score_directions"] != DIRECTIONS):
        raise ValueError("invalid_rank_scope_or_direction")
    assays = sorted({r["assay_id"] for r in frozen["rows"] if r["record_id"] in frozen["pool"]})
    if plan["assay_ids"] != assays:
        raise ValueError("rank_plan_assay_coverage_mismatch")
    # Validate combinations and worst-case work before engine execution or labels.
    metric.compare_cohort({rid: None for rid in frozen["pool"]},
        {arm: {} for arm in runner.ARMS}, plan["comparisons"], max_pair_work=plan["max_pair_work"])
    if frozen["protocol"]["source"]["kind"] == "chembl_fit_intake":
        from tools.product.train_public_chembl_selector import load_intake
        source = frozen["protocol"]["source"]
        _, _, scope, _ = load_intake(Path(source["input_dir"]), source["summary_sha256"], "fit")
        if scope["target_annotation"] != plan["target_annotation"] or scope["endpoint"] != plan["endpoint"]:
            raise ValueError("rank_native_scope_mismatch")
    return plan


def run(protocol, plan, output_dir, *, resume=False):
    start = time.perf_counter()
    frozen, _ = runner.freeze(protocol)
    _plan(plan, frozen)
    envelope = {"plan": plan, "frozen_sha256": runner.sha(frozen),
                "implementations": _implementations(), "plan_frozen_before_predictions": True}
    root = Path(output_dir).resolve()
    if not resume:
        root.mkdir(mode=0o700)
        runner.publish(root / "rank-plan.json", envelope)
    elif runner.read(root / "rank-plan.json") != envelope:
        raise ValueError("rank_resume_plan_or_implementation_changed")
    result = runner.run(protocol, root / "execution", resume=resume)
    if result["binding"] != envelope["frozen_sha256"] or _implementations() != envelope["implementations"]:
        raise ValueError("rank_execution_binding_changed")
    receipt = {"schema_version": "prepared_rank_ready_v1",
        "plan": runner.file_ref(root / "rank-plan.json"),
        "comparison": runner.file_ref(root / "execution/comparison.json"),
        "frozen": runner.file_ref(root / "execution/frozen.json")}
    if (root / "ready.json").exists():
        if runner.read(root / "ready.json") != receipt:
            raise ValueError("rank_ready_binding_changed")
    else:
        runner.publish(root / "ready.json", receipt)
        runner.publish(root / "run-cost.json", {"observed_wrapper_wall_seconds": time.perf_counter() - start,
            "includes": ["plan_preflight", "runner_validation", "all_sequential_arms", "ready_publication"],
            "excludes": ["upstream_preparation", "later_label_evaluation", "this_cost_publication"],
            "is_sum_of_arm_budgets": False})
    return runner.file_ref(root / "ready.json")


def _validated_predictions(ready_ref):
    ready = runner.bound(ready_ref)
    if set(ready) != {"schema_version", "plan", "comparison", "frozen"} or ready["schema_version"] != "prepared_rank_ready_v1":
        raise ValueError("invalid_rank_ready_receipt")
    envelope = runner.bound(ready["plan"])
    result, frozen_document = runner.bound(ready["comparison"]), runner.bound(ready["frozen"])
    frozen = frozen_document["payload"]
    binding = runner.sha(frozen)
    if (set(envelope) != {"plan", "frozen_sha256", "implementations", "plan_frozen_before_predictions"}
            or envelope["plan_frozen_before_predictions"] is not True
            or binding != frozen_document["sha256"] or result["binding"] != binding
            or envelope["frozen_sha256"] != binding or _implementations() != envelope["implementations"]
            or result["pool"] != frozen["pool"] or set(result["arms"]) != set(runner.ARMS)):
        raise ValueError("rank_frozen_prediction_mismatch")
    _plan(envelope["plan"], frozen)
    current, _ = runner.freeze(frozen["protocol"])
    if current != frozen:
        raise ValueError("rank_input_or_runtime_changed")
    root = Path(ready["comparison"]["path"]).parent
    for arm in runner.ARMS:
        complete = runner.read(root / arm / "completion.json")
        if (complete["binding"] != binding
                or runner._arm_summary(root / arm, frozen, binding, complete) != result["arms"][arm]):
            raise ValueError("rank_committed_predictions_changed")
    return ready, envelope["plan"], frozen, result


def _native_endpoint(row, endpoint):
    observation = row["observation"]
    # Exact-point restrictions are relaxed ONLY for this post-freeze descriptive
    # strict-bound diagnostic, never in intake, fitting, binary labels or policy.
    allowed = {"measurement_not_exact", "measurement_not_supported_exact_point"}
    if observation is None:
        return None, "missing_observation"
    if set(row["admission_issues"]) - allowed:
        return None, "source_or_identity_not_admitted"
    if (observation["endpoint"] != endpoint or observation["status"] not in {"exact", "censored"}
            or observation["relation"] not in {"=", ">"} or observation["upper_value_nm"] is not None
            or observation["issues"]):
        return None, "unsupported_or_ambiguous_observation"
    value = {"relation": observation["relation"], "value": observation["value_nm"]}
    legacy_metric._endpoint(value)
    return value, "exact" if value["relation"] == "=" else "strict_right_censored"


def _native_outcomes(frozen, result, plan, directory, summary_sha256):
    from tools.product.train_public_chembl_selector import load_intake
    summary = runner.bound({"path": str(Path(directory) / "summary.json"), "sha256": summary_sha256})
    for key in ("split_plan_sha256", "intake_scope_sha256"):
        if summary.get(key) != frozen["provenance"][key]:
            raise ValueError("rank_evaluation_role_scope_mismatch")
    _, _, scope, records = load_intake(Path(directory), summary_sha256, "evaluation")
    if scope["target_annotation"] != plan["target_annotation"] or scope["endpoint"] != plan["endpoint"]:
        raise ValueError("rank_evaluation_target_scope_mismatch")
    rows = {r["record_id"]: r for r in records if r["assigned_role"] == "development_test"}
    if set(rows) != set(result["pool"]):
        raise ValueError("rank_evaluation_denominator_mismatch")
    identities = {r["record_id"]: r for r in frozen["rows"]}
    outcomes, reasons = {}, {}
    for rid, row in rows.items():
        if any(row[key] != identities[rid][key] for key in ("component_id", "assay_id")):
            raise ValueError("rank_evaluation_identity_changed")
        outcomes[rid], reasons[rid] = _native_endpoint(row, plan["endpoint"])
    return outcomes, reasons


def evaluate(ready_ref, output_dir, *, synthetic_ref=None, evaluation_dir=None,
             summary_sha256=None, details=False):
    """No generic native-label JSON override; native intake must pass its own guards."""
    if type(details) is not bool:
        raise ValueError("rank_details_flag_must_be_boolean")
    if Path(output_dir).exists():
        raise FileExistsError("refuse_existing_rank_evaluation")
    start = time.perf_counter()
    ready, plan, frozen, result = _validated_predictions(ready_ref)
    validation_seconds = time.perf_counter() - start
    source_kind = frozen["protocol"]["source"]["kind"]
    label_start = time.perf_counter()
    if source_kind == "synthetic_constants" and synthetic_ref is not None and evaluation_dir is None:
        payload = runner.bound(synthetic_ref)  # First endpoint access is after validation.
        if (set(payload) != {"schema_version", "plan_sha256", "endpoints"}
                or payload["schema_version"] != "synthetic_rank_endpoints_v1"
                or payload["plan_sha256"] != runner.sha(plan)):
            raise ValueError("synthetic_rank_scope_mismatch")
        outcomes = payload["endpoints"]
        reasons = {rid: "missing_observation" if value is None else "synthetic_observation"
                   for rid, value in outcomes.items()}
        evidence_kind = "synthetic_contract_test"
    elif source_kind == "chembl_fit_intake" and synthetic_ref is None and evaluation_dir is not None:
        outcomes, reasons = _native_outcomes(frozen, result, plan, evaluation_dir, summary_sha256)
        evidence_kind = "source_bound_catalogue_development"
    else:
        raise ValueError("rank_evaluation_source_kind_mismatch")
    if set(outcomes) != set(result["pool"]):
        raise ValueError("rank_endpoint_denominator_mismatch")
    outcome_seconds = time.perf_counter() - label_start
    identities = {r["record_id"]: r for r in frozen["rows"]}
    root = Path(output_dir)
    root.mkdir(mode=0o700)
    metrics, metric_start = {}, time.perf_counter()
    for assay in plan["assay_ids"]:
        pool = [rid for rid in result["pool"] if identities[rid]["assay_id"] == assay]
        scores = {}
        for arm in runner.ARMS:
            direction = 1 if plan["score_directions"][arm] == "higher_is_better" else -1
            scores[arm] = {row["record_id"]: direction * row["score"]
                          for row in result["arms"][arm]["rows"]
                          if row["record_id"] in pool and row["status"] == "evaluated"}
        chunks = []
        def sink(rows):
            path = root / (runner.sha(assay) + f"-{len(chunks):06d}.json")
            runner.publish(path, rows)
            chunks.append(runner.file_ref(path))
        summary = metric.compare_cohort({rid: outcomes[rid] for rid in pool}, scores,
            plan["comparisons"], max_pair_work=plan["max_pair_work"], detail_sink=sink if details else None)
        metrics[assay] = {"summary": summary, "detail_chunks": chunks,
            "endpoint_status_counts": dict(Counter(reasons[rid] for rid in pool))}
    metric_seconds = time.perf_counter() - metric_start
    # Check sources/results again before publishing a completion receipt.
    ready_again, _, _, result_again = _validated_predictions(ready_ref)
    if ready_again != ready or result_again != result:
        raise ValueError("rank_evidence_changed_during_evaluation")
    if synthetic_ref is not None and runner.bound(synthetic_ref) != payload:
        raise ValueError("rank_endpoints_changed_during_evaluation")
    if evaluation_dir is not None:
        later = _native_outcomes(frozen, result, plan, evaluation_dir, summary_sha256)
        if later != (outcomes, reasons):
            raise ValueError("rank_native_endpoints_changed_during_evaluation")
    report = {"schema_version": "prepared_rank_evaluation_v1", "ready": ready_ref,
        "frozen_binding": result["binding"], "plan": plan, "evidence_kind": evidence_kind,
        "endpoint_source": synthetic_ref if synthetic_ref is not None else
            {"evaluation_dir": str(evaluation_dir), "summary_sha256": summary_sha256},
        "metrics_by_assay": metrics, "full_candidate_denominator": len(result["pool"]),
        "arm_denominators": {a: result["arms"][a]["denominator"] for a in runner.ARMS},
        "arm_costs": {a: result["arms"][a]["cost"] for a in runner.ARMS},
        "worker_observations": {a: result["arms"][a]["worker_observations"] for a in runner.ARMS},
        "common_validation_seconds": result["common_validation_seconds"],
        "orchestrator_wall_seconds": result["orchestrator_wall_seconds"],
        "evaluation_cost": {"initial_prediction_validation_seconds": validation_seconds,
            "initial_outcome_read_seconds": outcome_seconds, "metrics_and_detail_publication_seconds": metric_seconds,
            "total_before_report_publication_seconds": time.perf_counter() - start},
        "same_wall_time_guaranteed": False, "end_to_end_upstream_cost_measured": False,
        "labels_read_after_frozen_predictions": True, "same_prepared_assay_state_verified": False,
        "heldout_blindness_verified": False, "scientifically_validated": False, "ai_advantage_claimed": False}
    runner.publish(root / "report.json", report)
    runner.publish(root / "complete.json", {"report": runner.file_ref(root / "report.json"),
        "scientifically_validated": False})
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    launch = sub.add_parser("run")
    launch.add_argument("--protocol", type=Path, required=True)
    launch.add_argument("--plan", type=Path, required=True)
    launch.add_argument("--output-dir", type=Path, required=True)
    launch.add_argument("--resume", action="store_true")
    ev = sub.add_parser("evaluate")
    ev.add_argument("--ready", type=Path, required=True)
    ev.add_argument("--ready-sha256", required=True)
    ev.add_argument("--output-dir", type=Path, required=True)
    ev.add_argument("--synthetic", type=Path)
    ev.add_argument("--synthetic-sha256")
    ev.add_argument("--evaluation-dir", type=Path)
    ev.add_argument("--summary-sha256")
    ev.add_argument("--details", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "run":
        print(runner.canonical(run(runner.read(args.protocol), runner.read(args.plan), args.output_dir, resume=args.resume)))
    else:
        synthetic = None if args.synthetic is None else {"path": str(args.synthetic), "sha256": args.synthetic_sha256}
        evaluate({"path": str(args.ready), "sha256": args.ready_sha256}, args.output_dir,
                 synthetic_ref=synthetic, evaluation_dir=args.evaluation_dir,
                 summary_sha256=args.summary_sha256, details=args.details)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
