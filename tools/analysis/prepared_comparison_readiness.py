"""Report observed four-arm candidate coverage and work without reading outcomes.

This command consumes an already published prepared-rank ready receipt. It does
not run an arm, decode an assay outcome, or decide scientific eligibility.
"""

from __future__ import annotations

import argparse
import hashlib
import math
from pathlib import Path

from tools.product import compare_prepared_candidate_policies as runner
from tools.product import compare_prepared_candidate_ranks as ranks


SCHEMA = "prepared_comparison_readiness_v1"
ENVELOPE_SCHEMA = "prepared_comparison_readiness_receipt_v1"
STATUSES = ("evaluated", "unsupported", "failed", "not_processed")
D3_WORK = (
    "actual_force_evaluation_calls",
    "failed_force_evaluation_calls",
    "score_evaluation_calls",
    "force_evaluations_reserved",
    "pose_candidates_in_both_arms",
)


def _number(value):
    if type(value) not in (float, int) or not math.isfinite(value) or value < 0:
        raise ValueError("invalid_readiness_cost_observation")
    return value


def _work(name, rows, protocol, engine_calls):
    if name == "similarity":
        return {"status": "not_applicable", "observed_candidate_ids": [],
                "observed_sums": None, "calls_without_observation": None}
    if protocol["schema_version"] != runner.D3_SCHEMA:
        return {"status": "not_reported_by_cross_backend", "observed_candidate_ids": [],
                "observed_sums": None, "calls_without_observation": None}
    observed = []
    totals = dict.fromkeys(D3_WORK, 0)
    for row in rows:
        summary = row.get("d3_summary")
        if summary is None:
            continue
        values = summary["work"]
        if set(values) != set(D3_WORK):
            raise ValueError("unexpected_D3_work_observation")
        for key in D3_WORK:
            value = values[key]
            if type(value) is not int or value < 0:
                raise ValueError("invalid_D3_work_observation")
            totals[key] += value
        observed.append(row["record_id"])
    if engine_calls is not None and len(observed) > engine_calls:
        raise ValueError("D3_work_exceeds_observed_engine_calls")
    missing = None if engine_calls is None else engine_calls - len(observed)
    status = ("complete" if missing == 0 else
              "partial" if observed else "unavailable")
    return {"status": status, "observed_candidate_ids": observed,
            "observed_sums": totals if observed or engine_calls == 0 else None,
            "calls_without_observation": missing}


def _source_output_bytes_sha256(comparison_path, name, pool):
    """Bind raw committed row/worker observation bytes, including absent files."""
    directory = Path(comparison_path).parent / name
    filenames = ("completion.json", "priority.json", "worker-complete.json")
    filenames += tuple(runner.sha(rid) + ".row.json" for rid in pool)
    manifest = []
    for filename in filenames:
        path = directory / filename
        if path.exists():
            with path.open("rb") as stream:
                raw = stream.read(runner.MAX_BYTES + 1)
            if len(raw) > runner.MAX_BYTES:
                raise ValueError("readiness_source_output_too_large")
            digest = hashlib.sha256(raw).hexdigest()
        else:
            digest = None
        manifest.append((filename, digest))
    return runner.sha(manifest)


def _arm(name, arm, pool, prepared, protocol):
    rows = arm["rows"]
    if len(rows) != len(pool) or [row["record_id"] for row in rows] != pool:
        raise ValueError("readiness_arm_pool_mismatch")
    by_status = {status: [] for status in STATUSES}
    scored = []
    row_wall = row_cpu = 0.0
    observed_row_cost_ids = []
    for row in rows:
        status = row["status"]
        if status not in by_status:
            raise ValueError("unknown_readiness_arm_status")
        by_status[status].append(row["record_id"])
        if status == "evaluated":
            score = row["score"]
            if type(score) not in (float, int) or not math.isfinite(score):
                raise ValueError("invalid_evaluated_readiness_score")
            scored.append(row["record_id"])
        elif row["score"] is not None:
            raise ValueError("unranked_readiness_score_present")
        cost = row.get("cost")
        if cost is not None:
            row_wall += _number(cost["wall_seconds"])
            row_cpu += _number(cost["cpu_seconds"])
            observed_row_cost_ids.append(row["record_id"])
    observations = arm["worker_observations"]
    completed = observations.get("worker-complete.json")
    engine_calls = None if completed is None else completed["engine_calls"]
    if engine_calls is not None and (type(engine_calls) is not int or engine_calls < 0):
        raise ValueError("invalid_readiness_engine_calls")
    completion = arm["cost"]
    work = _work(name, rows, protocol, engine_calls)
    return {
        "status_ids": by_status,
        "scored_ids": scored,
        "scored_without_prepared_request_ids": [rid for rid in scored if rid not in prepared],
        "counts": {"requested": len(pool), "scored": len(scored),
                   **{status: len(by_status[status]) for status in STATUSES}},
        "observed_cost": {
            "completion_status": completion["status"],
            "budget_seconds": _number(completion["budget_seconds"]),
            "measured_process_wall_seconds": None if completion["measured_process_wall_seconds"] is None
                else _number(completion["measured_process_wall_seconds"]),
            "termination_overhead_seconds": None if completion["termination_overhead_seconds"] is None
                else _number(completion["termination_overhead_seconds"]),
            "process_cpu_seconds": None if completed is None else _number(completed["process_cpu_seconds"]),
            "process_peak_rss_kib": None if completed is None else _number(completed["process_peak_rss_kib"]),
            "outer_engine_calls": engine_calls,
            "committed_row_wall_seconds_observed_sum": row_wall if observed_row_cost_ids else None,
            "committed_row_cpu_seconds_observed_sum": row_cpu if observed_row_cost_ids else None,
            "committed_row_cost_ids": observed_row_cost_ids,
            "row_cost_is_a_subset_of_process_cost": True,
            "nested_costs_added_to_process_cost": False,
        },
        "nested_D3_work": work,
    }


def build(ready_ref):
    """Verify the frozen result and committed rows before deriving diagnostics."""
    ready, plan, frozen, comparison = ranks._validated_predictions(ready_ref)
    pool = comparison["pool"]
    prepared = [rid for rid in pool if frozen["requests"][rid] is not None]
    prepared_set = set(prepared)
    arms = {}
    for name in runner.ARMS:
        arms[name] = _arm(name, comparison["arms"][name], pool, prepared_set, frozen["protocol"])
        arms[name]["source_output_bytes_sha256"] = _source_output_bytes_sha256(
            ready["comparison"]["path"], name, pool)
    common = [rid for rid in pool if all(rid in arms[name]["scored_ids"] for name in runner.ARMS)]
    return {
        "schema_version": SCHEMA,
        "source_bindings": {"ready": ready_ref, "plan": ready["plan"],
                            "frozen": ready["frozen"], "comparison": ready["comparison"],
                            "frozen_binding_sha256": comparison["binding"],
                            "protocol_sha256": runner.sha(frozen["protocol"]),
                            "diagnostic_code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        "source_kind": frozen["protocol"]["source"]["kind"],
        "calculation_backend": frozen["protocol"].get("calculation", {"backend": "prepared_rigid_cross_v1"})["backend"],
        "requested_pool_ids": pool,
        "prepared_request_present_ids": prepared,
        "prepared_request_missing_ids": [rid for rid in pool if rid not in prepared_set],
        "prepared_request_presence_is_quality_or_assay_admission": False,
        "arms": arms,
        "four_arm_common_scored_ids": common,
        "four_arm_common_scored_count": len(common),
        "same_prepared_assay_state_verified": False,
        "heldout_blindness_verified": False,
        "scientifically_validated": False,
        "ai_advantage_claimed": False,
        "eligible_source_state_join_count": None,
        "upstream_acquisition_preparation_pose_generation_cost": None,
        "comparison_scope": "provided_preparation_policy_execution_diagnostic_only",
    }


def report(ready_ref, output):
    first = build(ready_ref)
    if build(ready_ref) != first:
        raise ValueError("readiness_source_changed_before_publication")
    envelope = {"schema_version": ENVELOPE_SCHEMA, "payload": first,
                "payload_sha256": runner.sha(first)}
    runner.publish(output, envelope)
    return runner.file_ref(output)


def verify(report_ref):
    envelope = runner.bound(report_ref)
    if (type(envelope) is not dict or set(envelope) != {"schema_version", "payload", "payload_sha256"}
            or envelope["schema_version"] != ENVELOPE_SCHEMA
            or runner.sha(envelope["payload"]) != envelope["payload_sha256"]):
        raise ValueError("invalid_readiness_receipt")
    payload = envelope["payload"]
    if build(payload["source_bindings"]["ready"]) != payload:
        raise ValueError("readiness_source_or_diagnostic_changed")
    return payload


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("report")
    create.add_argument("--ready", type=Path, required=True)
    create.add_argument("--ready-sha256", required=True)
    create.add_argument("--output", type=Path, required=True)
    check = sub.add_parser("verify")
    check.add_argument("--report", type=Path, required=True)
    check.add_argument("--report-sha256", required=True)
    args = parser.parse_args(argv)
    if args.command == "report":
        reference = report({"path": str(args.ready.resolve()), "sha256": args.ready_sha256}, args.output)
        print(runner.canonical(reference))
    else:
        payload = verify({"path": str(args.report.resolve()), "sha256": args.report_sha256})
        print(runner.canonical({"status": "passed", "four_arm_common_scored_count": payload["four_arm_common_scored_count"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
