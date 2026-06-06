#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[1]


def _resolve_repo_path(path_str: str) -> Path:
    path = Path(path_str)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _read_json_if_exists(path_str: str) -> Dict[str, Any]:
    path = _resolve_repo_path(path_str)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _build_scope_summary_from_spec(spec: Dict[str, Any]) -> Dict[str, Any]:
    sets = spec.get("sets")
    if not isinstance(sets, list):
        return {}
    task_rows: List[Dict[str, Any]] = []
    for set_row in sets:
        set_id = str(set_row.get("set_id", "")).strip()
        for task in set_row.get("tasks", []) or []:
            if str(task.get("kind", "")).strip() != "ligand_stress":
                continue
            ligand_sizes = str(task.get("ligand_sizes", "")).strip()
            task_rows.append(
                {
                    "set_id": set_id,
                    "task_id": str(task.get("task_id", "")).strip(),
                    "domain": str(task.get("domain", "")).strip(),
                    "is_smoke": bool(ligand_sizes == "64"),
                }
            )
    full_rows = [row for row in task_rows if not bool(row["is_smoke"])]
    smoke_rows = [row for row in task_rows if bool(row["is_smoke"])]
    return {
        "ligand_task_count": int(len(task_rows)),
        "selected_task_count": int(len(task_rows)),
        "selected_full_task_count": int(len(full_rows)),
        "selected_smoke_task_count": int(len(smoke_rows)),
        "selected_set_ids": sorted({row["set_id"] for row in task_rows}),
        "domains_touched": sorted({row["domain"] for row in task_rows if str(row["domain"]).strip()}),
        "slow_domain_task_ids": [row["task_id"] for row in task_rows],
    }


def _load_ab_surface(ab_json: str, ab_spec_json: str) -> Dict[str, Any]:
    ab = _read_json_if_exists(ab_json)
    spec = _read_json_if_exists(ab_spec_json)
    out = dict(ab) if ab else {}
    if spec:
        governance = spec.get("global_governance", {}) if isinstance(spec.get("global_governance"), dict) else {}
        if "comparison_kind" not in out and isinstance(governance.get("comparison_kind"), str):
            out["comparison_kind"] = str(governance.get("comparison_kind"))
        if "scope_summary" not in out or not isinstance(out.get("scope_summary"), dict):
            scope_summary = _build_scope_summary_from_spec(spec)
            if scope_summary:
                out["scope_summary"] = scope_summary
        if "task_rows" not in out and isinstance(spec.get("sets"), list):
            out["task_rows"] = [
                {
                    "set_id": str(set_row.get("set_id", "")).strip(),
                    "task_id": str(task.get("task_id", "")).strip(),
                    "domain": str(task.get("domain", "")).strip(),
                    "ligand_sizes": str(task.get("ligand_sizes", "")).strip(),
                }
                for set_row in spec.get("sets", [])
                for task in (set_row.get("tasks", []) or [])
                if str(task.get("kind", "")).strip() == "ligand_stress"
            ]
        notes = list(out.get("preflight_notes", []) if isinstance(out.get("preflight_notes"), list) else [])
        fallback_note = "A/B metadata JSON unavailable; scope was reconstructed from candidate spec."
        if spec and (not ab) and fallback_note not in notes:
            notes.append(fallback_note)
        if notes:
            out["preflight_notes"] = notes
    return out


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _count_pass_sets(summary: Dict[str, Any]) -> Optional[int]:
    sets = summary.get("sets")
    if not isinstance(sets, list):
        return None
    return int(sum(1 for row in sets if bool(row.get("pass", False))))


def _default_guardrail_rows() -> List[Dict[str, str]]:
    return [
        {
            "guardrail_id": "no_pass_to_fail",
            "metric": "set_pass_transition",
            "threshold": "0 pass->fail transitions",
            "scope": "equal-size regression slice",
        },
        {
            "guardrail_id": "pr_auc_drop_max_0p01",
            "metric": "ranking_pr_auc_delta",
            "threshold": ">= -0.01 absolute",
            "scope": "equal-size regression slice",
        },
        {
            "guardrail_id": "top20_hit_rate_drop_max_0p05",
            "metric": "top20_hit_rate_delta",
            "threshold": ">= -0.05 absolute",
            "scope": "equal-size regression slice",
        },
        {
            "guardrail_id": "stage2_speedup_min_1p2x",
            "metric": "stage2_latency_speedup",
            "threshold": ">= 1.2x on measured A/B task",
            "scope": "operational throughput",
        },
    ]


def _comparison_metrics(summary: Dict[str, Any]) -> Dict[str, Any]:
    rows = summary.get("task_rows")
    if not isinstance(rows, list):
        return {}
    ligand_rows = [row for row in rows if str(row.get("kind", "")).strip() == "ligand_stress"]
    domains = sorted({str(row.get("domain", "")).strip() for row in ligand_rows if str(row.get("domain", "")).strip()})
    pass_to_fail = 0
    max_pr_drop = None
    worst_pr_task = ""
    max_top20_drop = None
    worst_top20_task = ""
    for row in ligand_rows:
        if bool(row.get("baseline_pass", False)) and (not bool(row.get("candidate_pass", False))):
            pass_to_fail += 1
        delta_pr = _safe_float(row.get("delta_pr_auc"))
        if delta_pr is not None and (max_pr_drop is None or delta_pr < max_pr_drop):
            max_pr_drop = delta_pr
            worst_pr_task = str(row.get("task_id", ""))
        delta_top20 = _safe_float(row.get("delta_top20_hit_rate"))
        if delta_top20 is not None and (max_top20_drop is None or delta_top20 < max_top20_drop):
            max_top20_drop = delta_top20
            worst_top20_task = str(row.get("task_id", ""))
    return {
        "ligand_task_count": int(len(ligand_rows)),
        "domains_touched": domains,
        "pass_to_fail_count": int(pass_to_fail),
        "max_pr_auc_drop": max_pr_drop,
        "worst_pr_auc_task": worst_pr_task,
        "max_top20_hit_rate_drop": max_top20_drop,
        "worst_top20_task": worst_top20_task,
        "tasks_with_pr_improvement": int(summary.get("tasks_with_pr_improvement", 0) or 0),
        "tasks_with_pr_regression": int(summary.get("tasks_with_pr_regression", 0) or 0),
        "profile_changed_task_count": int(summary.get("profile_changed_task_count", 0) or 0),
    }


def _sla_metrics(baseline_sla: Dict[str, Any], candidate_sla: Dict[str, Any]) -> Dict[str, Any]:
    if not baseline_sla or not candidate_sla:
        return {}
    baseline_total = _safe_float(baseline_sla.get("total_latency_sec"))
    candidate_total = _safe_float(candidate_sla.get("total_latency_sec"))
    baseline_stage2 = _safe_float(baseline_sla.get("durations_sec", {}).get("stage2_trajectory_sec"))
    candidate_stage2 = _safe_float(candidate_sla.get("durations_sec", {}).get("stage2_trajectory_sec"))
    baseline_stage2_rate = _safe_float(baseline_sla.get("queue_rate_stage2_rows_per_sec"))
    candidate_stage2_rate = _safe_float(candidate_sla.get("queue_rate_stage2_rows_per_sec"))
    total_speedup = None
    if baseline_total and candidate_total and candidate_total > 0:
        total_speedup = baseline_total / candidate_total
    stage2_speedup = None
    if baseline_stage2 and candidate_stage2 and candidate_stage2 > 0:
        stage2_speedup = baseline_stage2 / candidate_stage2
    return {
        "baseline_total_latency_sec": baseline_total,
        "candidate_total_latency_sec": candidate_total,
        "baseline_stage2_latency_sec": baseline_stage2,
        "candidate_stage2_latency_sec": candidate_stage2,
        "baseline_stage2_rows_per_sec": baseline_stage2_rate,
        "candidate_stage2_rows_per_sec": candidate_stage2_rate,
        "total_latency_speedup": total_speedup,
        "stage2_latency_speedup": stage2_speedup,
    }


def _runtime_sla_metrics(runtime: Dict[str, Any]) -> Dict[str, Any]:
    rows = runtime.get("rows", []) if isinstance(runtime.get("rows"), list) else []
    stage2_speeds: List[float] = []
    total_speeds: List[float] = []
    stage2_rates: List[float] = []
    task_ids: List[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        speed = _safe_float(row.get("measured_stage2_speedup"))
        if speed is None:
            baseline_stage2 = _safe_float(row.get("baseline_stage2_runtime_sec"))
            candidate_stage2 = _safe_float(row.get("candidate_stage2_runtime_sec"))
            if baseline_stage2 not in (None, 0.0) and candidate_stage2 not in (None, 0.0):
                speed = baseline_stage2 / candidate_stage2
        if speed is not None:
            stage2_speeds.append(float(speed))
            task_ids.append(str(row.get("task_id", "")).strip())
        total_speed = _safe_float(row.get("measured_total_speedup"))
        if total_speed is not None:
            total_speeds.append(float(total_speed))
        stage2_rate = _safe_float(row.get("candidate_queue_rate_stage2_rows_per_sec"))
        if stage2_rate is not None:
            stage2_rates.append(float(stage2_rate))
    if not stage2_speeds and not total_speeds:
        return {}
    out: Dict[str, Any] = {
        "source": "runtime_json",
        "runtime_task_count": int(len(rows)),
        "measured_stage2_speedup_count": int(len(stage2_speeds)),
        "measured_total_speedup_count": int(len(total_speeds)),
        "stage2_speedup_task_ids": [task_id for task_id in task_ids if task_id],
    }
    if stage2_speeds:
        out["stage2_latency_speedup"] = float(min(stage2_speeds))
        out["stage2_latency_speedup_min"] = float(min(stage2_speeds))
        out["stage2_latency_speedup_max"] = float(max(stage2_speeds))
    if total_speeds:
        out["total_latency_speedup"] = float(min(total_speeds))
        out["total_latency_speedup_min"] = float(min(total_speeds))
        out["total_latency_speedup_max"] = float(max(total_speeds))
    if stage2_rates:
        out["candidate_stage2_rows_per_sec"] = float(min(stage2_rates))
    return out


def _build_scope_summary(ab: Dict[str, Any], comparison_metrics: Dict[str, Any], baseline_summary: Dict[str, Any]) -> Dict[str, Any]:
    scope = ab.get("scope_summary", {}) if isinstance(ab.get("scope_summary"), dict) else {}
    if scope:
        return scope
    summary: Dict[str, Any] = {}
    if comparison_metrics:
        summary["ligand_task_count"] = comparison_metrics.get("ligand_task_count", 0)
        summary["domains_touched"] = comparison_metrics.get("domains_touched", [])
    sets = baseline_summary.get("sets")
    if isinstance(sets, list):
        summary["set_count"] = int(len(sets))
    return summary


def _build_guardrail_rows(
    ab: Dict[str, Any],
    comparison: Dict[str, Any],
    baseline_summary: Dict[str, Any],
    candidate_summary: Dict[str, Any],
    sla_metrics: Dict[str, Any],
) -> List[Dict[str, Any]]:
    comparison_metrics = _comparison_metrics(comparison) if comparison else {}
    baseline_pass_sets = _count_pass_sets(baseline_summary)
    candidate_pass_sets = _count_pass_sets(candidate_summary)
    rows: List[Dict[str, Any]] = []
    source_rows = ab.get("guardrail_rows")
    if not isinstance(source_rows, list) or not source_rows:
        source_rows = _default_guardrail_rows()
    for row in source_rows:
        guardrail_id = str(row.get("guardrail_id", "")).strip()
        observed_value = "pending"
        passed: Optional[bool] = None
        note = ""
        if comparison_metrics:
            if guardrail_id == "no_pass_to_fail":
                observed_value = str(comparison_metrics.get("pass_to_fail_count", 0))
                passed = int(comparison_metrics.get("pass_to_fail_count", 0)) == 0
                note = "comparison available"
            elif guardrail_id == "pr_auc_drop_max_0p01":
                value = comparison_metrics.get("max_pr_auc_drop")
                observed_value = f"{value:.4f}" if isinstance(value, float) else "n/a"
                passed = (value is not None) and (value >= -0.01)
                worst = str(comparison_metrics.get("worst_pr_auc_task", "")).strip()
                if worst:
                    note = f"worst task: {worst}"
            elif guardrail_id == "top20_hit_rate_drop_max_0p05":
                value = comparison_metrics.get("max_top20_hit_rate_drop")
                observed_value = f"{value:.4f}" if isinstance(value, float) else "n/a"
                passed = None if value is None else bool(value >= -0.05)
                worst = str(comparison_metrics.get("worst_top20_task", "")).strip()
                if worst:
                    note = f"worst task: {worst}"
        if guardrail_id == "stage2_speedup_min_1p2x":
            speed = sla_metrics.get("stage2_latency_speedup")
            observed_value = f"{speed:.3f}x" if isinstance(speed, float) else "pending"
            passed = None if speed is None else bool(speed >= 1.2)
            if passed is None:
                note = "needs baseline and candidate SLA summaries"
        rows.append(
            {
                "guardrail_id": guardrail_id,
                "metric": str(row.get("metric", "")),
                "threshold": str(row.get("threshold", "")),
                "scope": str(row.get("scope", "")),
                "observed_value": observed_value,
                "pass": passed,
                "note": note,
            }
        )
    if baseline_pass_sets is not None or candidate_pass_sets is not None:
        rows.append(
            {
                "guardrail_id": "set_pass_counts",
                "metric": "set_pass_count",
                "threshold": "candidate should preserve baseline set pass count",
                "scope": "top-level run summary",
                "observed_value": f"baseline={baseline_pass_sets if baseline_pass_sets is not None else 'n/a'}, candidate={candidate_pass_sets if candidate_pass_sets is not None else 'n/a'}",
                "pass": None if baseline_pass_sets is None or candidate_pass_sets is None else bool(candidate_pass_sets >= baseline_pass_sets),
                "note": "derived from baseline/candidate summary.json",
            }
        )
    return rows


def build_payload(
    *,
    ab_json: str,
    ab_spec_json: str,
    comparison_json: str,
    baseline_summary_json: str,
    candidate_summary_json: str,
    baseline_sla_json: str,
    candidate_sla_json: str,
    kpi_json: str,
    runtime_json: str = "",
) -> Dict[str, Any]:
    ab = _load_ab_surface(ab_json, ab_spec_json)
    comparison = _read_json_if_exists(comparison_json)
    baseline_summary = _read_json_if_exists(baseline_summary_json)
    candidate_summary = _read_json_if_exists(candidate_summary_json)
    baseline_sla = _read_json_if_exists(baseline_sla_json)
    candidate_sla = _read_json_if_exists(candidate_sla_json)
    runtime = _read_json_if_exists(runtime_json)
    kpi = _read_json_if_exists(kpi_json)

    comparison_ready = bool(comparison)
    baseline_ready = bool(baseline_summary)
    candidate_ready = bool(candidate_summary)
    runtime_sla_metrics = _runtime_sla_metrics(runtime)
    sla_ready = bool((baseline_sla and candidate_sla) or runtime_sla_metrics)
    comparison_metrics = _comparison_metrics(comparison) if comparison_ready else {}
    sla_metrics = _sla_metrics(baseline_sla, candidate_sla) or runtime_sla_metrics
    guardrail_rows = _build_guardrail_rows(ab, comparison, baseline_summary, candidate_summary, sla_metrics)
    guardrail_pass_rows = [row for row in guardrail_rows if row.get("pass") is True]
    guardrail_fail_rows = [row for row in guardrail_rows if row.get("pass") is False]
    guardrail_pending_rows = [row for row in guardrail_rows if row.get("pass") is None]

    if comparison_ready and sla_ready:
        benchmark_stage = "post_run_ab_with_speed"
    elif comparison_ready:
        benchmark_stage = "post_run_ab_no_speed"
    elif candidate_ready:
        benchmark_stage = "candidate_run_ready_no_comparison"
    else:
        benchmark_stage = "prelaunch_ab_scaffold"

    scope_summary = _build_scope_summary(ab, comparison_metrics, baseline_summary)
    kpi_summary = kpi.get("summary", {}) if isinstance(kpi.get("summary"), dict) else {}
    slowest = kpi_summary.get("slowest_task_at_1m", {}) if isinstance(kpi_summary.get("slowest_task_at_1m"), dict) else {}
    claim_safe = None
    commercialization_ready = None
    if comparison_ready:
        claim_safe = bool(
            comparison_metrics.get("pass_to_fail_count", 0) == 0
            and all(row.get("pass") is not False for row in guardrail_rows if row.get("guardrail_id") != "stage2_speedup_min_1p2x")
        )
    if comparison_ready and sla_ready:
        commercialization_ready = bool(claim_safe and all(row.get("pass") is not False for row in guardrail_rows))

    next_action = "prepare equal-size A/B baseline and candidate artifacts"
    if comparison_ready and not sla_ready:
        next_action = "attach baseline/candidate SLA summaries to evaluate measured stage2 speedup"
    elif comparison_ready and claim_safe and commercialization_ready:
        next_action = "A/B is claim-safe and speed-positive; ready to promote into broader 100k/1M throughput benchmarking"
    elif comparison_ready and claim_safe and not commercialization_ready:
        next_action = "quality is preserved, but measured speedup guardrail is not yet closed"
    elif comparison_ready and claim_safe is False:
        next_action = "A/B quality guardrails failed; inspect worst equal-size regressions before rollout"

    return {
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "comparison_kind": str(ab.get("comparison_kind", "equal_size_speedpack_ab")),
        "benchmark_stage": benchmark_stage,
        "baseline_artifact_ready": baseline_ready,
        "candidate_artifact_ready": candidate_ready,
        "comparison_artifact_ready": comparison_ready,
        "sla_artifact_ready": sla_ready,
        "claim_safe": claim_safe,
        "commercialization_ready": commercialization_ready,
        "scope_summary": scope_summary,
        "kpi_summary": kpi_summary,
        "slowest_task_at_1m": slowest,
        "comparison_metrics": comparison_metrics,
        "sla_metrics": sla_metrics,
        "guardrail_rows": guardrail_rows,
        "guardrail_pass_count": int(len(guardrail_pass_rows)),
        "guardrail_fail_count": int(len(guardrail_fail_rows)),
        "guardrail_pending_count": int(len(guardrail_pending_rows)),
        "preflight_notes": list(ab.get("preflight_notes", []) if isinstance(ab.get("preflight_notes"), list) else []),
        "recommended_next_action": next_action,
        "input_artifacts": {
            "ab_json": str(_resolve_repo_path(ab_json)),
            "ab_spec_json": str(_resolve_repo_path(ab_spec_json)),
            "comparison_json": str(_resolve_repo_path(comparison_json)),
            "baseline_summary_json": str(_resolve_repo_path(baseline_summary_json)),
            "candidate_summary_json": str(_resolve_repo_path(candidate_summary_json)),
            "baseline_sla_json": str(_resolve_repo_path(baseline_sla_json)),
            "candidate_sla_json": str(_resolve_repo_path(candidate_sla_json)),
            "runtime_json": str(_resolve_repo_path(runtime_json)),
            "kpi_json": str(_resolve_repo_path(kpi_json)),
        },
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a commercialization-oriented guardrail summary for equal-size stage2 speedpack A/B runs."
    )
    parser.add_argument("--ab-json", default="runs/ligand_speedpack_ab_current.json")
    parser.add_argument("--ab-spec-json", default="runs/ligand_speedpack_ab_current/specs/ligand_speedpack_ab_current_v1.json")
    parser.add_argument("--comparison-json", default="runs/ligand_speedpack_ab_comparison_current.json")
    parser.add_argument("--baseline-summary-json", default="runs/ligand_speedpack_ab_baseline_summary_current.json")
    parser.add_argument("--candidate-summary-json", default="runs/ligand_speedpack_ab_candidate_summary_current.json")
    parser.add_argument("--baseline-sla-json", default="runs/ligand_speedpack_ab_baseline_sla_current.json")
    parser.add_argument("--candidate-sla-json", default="runs/ligand_speedpack_ab_candidate_sla_current.json")
    parser.add_argument("--runtime-json", default="runs/ligand_speedpack_ab_runtime_current.json")
    parser.add_argument("--kpi-json", default="runs/ligand_scaleup_kpi_current.json")
    parser.add_argument("--out-json", default="runs/ligand_speedpack_ab_summary_current.json")
    parser.add_argument("--out-csv", default="runs/ligand_speedpack_ab_summary_current.csv")
    parser.add_argument("--out-md", default="runs/ligand_speedpack_ab_summary_current.md")
    args = parser.parse_args(argv)

    payload = build_payload(
        ab_json=args.ab_json,
        ab_spec_json=args.ab_spec_json,
        comparison_json=args.comparison_json,
        baseline_summary_json=args.baseline_summary_json,
        candidate_summary_json=args.candidate_summary_json,
        baseline_sla_json=args.baseline_sla_json,
        candidate_sla_json=args.candidate_sla_json,
        runtime_json=args.runtime_json,
        kpi_json=args.kpi_json,
    )

    out_json = _resolve_repo_path(args.out_json)
    out_csv = _resolve_repo_path(args.out_csv)
    out_md = _resolve_repo_path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    rows = payload.get("guardrail_rows", [])
    with out_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "guardrail_id",
                "metric",
                "threshold",
                "scope",
                "observed_value",
                "pass",
                "note",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    slowest = payload.get("slowest_task_at_1m", {}) if isinstance(payload.get("slowest_task_at_1m"), dict) else {}
    sla = payload.get("sla_metrics", {}) if isinstance(payload.get("sla_metrics"), dict) else {}
    lines = [
        "# Ligand Speedpack A/B Summary",
        "",
        f"- generated_at_local: `{payload.get('generated_at_local', '')}`",
        f"- benchmark_stage: `{payload.get('benchmark_stage', '')}`",
        f"- comparison_kind: `{payload.get('comparison_kind', '')}`",
        f"- baseline_artifact_ready: `{payload.get('baseline_artifact_ready')}`",
        f"- candidate_artifact_ready: `{payload.get('candidate_artifact_ready')}`",
        f"- comparison_artifact_ready: `{payload.get('comparison_artifact_ready')}`",
        f"- sla_artifact_ready: `{payload.get('sla_artifact_ready')}`",
        f"- claim_safe: `{payload.get('claim_safe')}`",
        f"- commercialization_ready: `{payload.get('commercialization_ready')}`",
        f"- recommended_next_action: `{payload.get('recommended_next_action', '')}`",
        "",
        "## Scope",
        "",
        f"- ligand_task_count: `{payload.get('scope_summary', {}).get('ligand_task_count', '')}`",
        f"- domains_touched: `{payload.get('scope_summary', {}).get('domains_touched', [])}`",
        "",
        "## Measured Speed",
        "",
        f"- stage2_latency_speedup: `{sla.get('stage2_latency_speedup', '')}`",
        f"- total_latency_speedup: `{sla.get('total_latency_speedup', '')}`",
        f"- baseline_stage2_rows_per_sec: `{sla.get('baseline_stage2_rows_per_sec', '')}`",
        f"- candidate_stage2_rows_per_sec: `{sla.get('candidate_stage2_rows_per_sec', '')}`",
        "",
        "## Slowest Task Context",
        "",
        f"- task_id: `{slowest.get('task_id', '')}`",
        f"- domain: `{slowest.get('domain', '')}`",
        f"- projected_1m_wall_hr: `{slowest.get('projected_1m_wall_hr', '')}`",
        "",
        "## Guardrails",
        "",
        "| guardrail_id | threshold | observed_value | pass | note |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['guardrail_id']} | {row['threshold']} | {row['observed_value']} | {row['pass']} | {row['note']} |"
        )
    preflight_notes = payload.get("preflight_notes", [])
    if preflight_notes:
        lines.extend(["", "## Preflight Notes", ""])
        for note in preflight_notes:
            lines.append(f"- {note}")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
