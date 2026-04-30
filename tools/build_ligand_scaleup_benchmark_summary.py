#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
import statistics
from typing import Any, Dict, List, Optional, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PILOT_JSON = "runs/ligand_scaleup_100k_pilot_current.json"
DEFAULT_KPI_JSON = "runs/ligand_scaleup_kpi_current.json"
DEFAULT_COMPARISON_JSON = "runs/biorxiv_run_comparison_2026-03-23_scaleup_100k_pilot_v2r2_vs_current/summary.json"
DEFAULT_BASELINE_SUMMARY_JSON = "runs/external_validation_blind_runs/external_validation_blind_runs_2026-03-22_biorxiv_v7r1/summary.json"
DEFAULT_CANDIDATE_SUMMARY_JSON = (
    "runs/external_validation_blind_runs/external_validation_blind_runs_2026-03-23_scaleup_100k_pilot_v2r2/summary.json"
)


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


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _safe_int(value: Any) -> Optional[int]:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except Exception:
        return None


def _count_pass_sets(summary: Dict[str, Any]) -> Optional[int]:
    sets = summary.get("sets")
    if not isinstance(sets, list):
        return None
    return int(sum(1 for row in sets if bool(row.get("pass", False))))


def _safe_task_id(value: Any) -> str:
    return str(value or "").strip()


def _iter_ligand_task_rows(run_summary: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    sets = run_summary.get("sets")
    if not isinstance(sets, list):
        return out
    for set_row in sets:
        if not isinstance(set_row, dict):
            continue
        tasks = set_row.get("tasks")
        if not isinstance(tasks, list):
            continue
        for task in tasks:
            if not isinstance(task, dict):
                continue
            if str(task.get("kind", "")).strip() != "ligand_stress":
                continue
            row = dict(task)
            row["set_id"] = str(set_row.get("set_id", row.get("set_id", "")) or "")
            row["set_pass"] = bool(set_row.get("pass", False))
            out.append(row)
    return out


def _pipeline_sla_metrics(summary_json: str) -> Dict[str, Any]:
    payload = _read_json_if_exists(summary_json)
    sla = ((payload.get("stages") or {}).get("stage8_sla") or {})
    if not isinstance(sla, dict):
        sla = {}
    return {
        "total_latency_sec": _safe_float(sla.get("total_latency_sec")),
        "queue_rate_stage2_rows_per_sec": _safe_float(sla.get("queue_rate_stage2_rows_per_sec")),
        "queue_rate_stage3_rows_per_sec": _safe_float(sla.get("queue_rate_stage3_rows_per_sec")),
        "queue_rows": _safe_float(sla.get("queue_rows")),
        "stage2_latency_sec": _safe_float(((sla.get("durations_sec") or {}).get("stage2_trajectory_sec"))),
    }


def _safe_ratio(numer: Optional[float], denom: Optional[float]) -> Optional[float]:
    if numer is None or denom is None:
        return None
    if denom <= 0:
        return None
    return float(numer / denom)


def _measured_speedup_summary(
    *,
    baseline_summary: Dict[str, Any],
    candidate_summary: Dict[str, Any],
    slowest_task_id: str,
) -> Dict[str, Any]:
    baseline_rows = {
        _safe_task_id(row.get("task_id")): row
        for row in _iter_ligand_task_rows(baseline_summary)
        if _safe_task_id(row.get("task_id"))
    }
    candidate_rows = {
        _safe_task_id(row.get("task_id")): row
        for row in _iter_ligand_task_rows(candidate_summary)
        if _safe_task_id(row.get("task_id"))
    }
    common_ids = sorted(set(baseline_rows) & set(candidate_rows))
    task_rows: List[Dict[str, Any]] = []
    stage2_speedups: List[float] = []
    end_to_end_speedups: List[float] = []
    for task_id in common_ids:
        base_task = baseline_rows[task_id]
        cand_task = candidate_rows[task_id]
        base_sla = _pipeline_sla_metrics(str(base_task.get("pipeline_summary_json", "")))
        cand_sla = _pipeline_sla_metrics(str(cand_task.get("pipeline_summary_json", "")))
        stage2_speedup = _safe_ratio(base_sla.get("stage2_latency_sec"), cand_sla.get("stage2_latency_sec"))
        end_to_end_speedup = _safe_ratio(base_sla.get("total_latency_sec"), cand_sla.get("total_latency_sec"))
        if isinstance(stage2_speedup, float):
            stage2_speedups.append(stage2_speedup)
        if isinstance(end_to_end_speedup, float):
            end_to_end_speedups.append(end_to_end_speedup)
        task_rows.append(
            {
                "task_id": task_id,
                "domain": str(cand_task.get("domain", base_task.get("domain", "")) or ""),
                "baseline_stage2_latency_sec": base_sla.get("stage2_latency_sec"),
                "candidate_stage2_latency_sec": cand_sla.get("stage2_latency_sec"),
                "baseline_total_latency_sec": base_sla.get("total_latency_sec"),
                "candidate_total_latency_sec": cand_sla.get("total_latency_sec"),
                "baseline_stage2_rows_per_sec": base_sla.get("queue_rate_stage2_rows_per_sec"),
                "candidate_stage2_rows_per_sec": cand_sla.get("queue_rate_stage2_rows_per_sec"),
                "stage2_latency_speedup": stage2_speedup,
                "end_to_end_speedup": end_to_end_speedup,
                "baseline_pipeline_summary_json": str(base_task.get("pipeline_summary_json", "")),
                "candidate_pipeline_summary_json": str(cand_task.get("pipeline_summary_json", "")),
            }
        )

    slowest = next((row for row in task_rows if row.get("task_id") == slowest_task_id), {})
    return {
        "common_task_count": int(len(common_ids)),
        "tasks_with_stage2_speedup": int(sum(1 for row in task_rows if isinstance(row.get("stage2_latency_speedup"), float))),
        "tasks_with_end_to_end_speedup": int(sum(1 for row in task_rows if isinstance(row.get("end_to_end_speedup"), float))),
        "median_stage2_speedup": float(statistics.median(stage2_speedups)) if stage2_speedups else None,
        "median_end_to_end_speedup": float(statistics.median(end_to_end_speedups)) if end_to_end_speedups else None,
        "max_stage2_speedup": float(max(stage2_speedups)) if stage2_speedups else None,
        "max_end_to_end_speedup": float(max(end_to_end_speedups)) if end_to_end_speedups else None,
        "slowest_task_measured": bool(slowest),
        "slowest_task": slowest,
        "task_rows": task_rows,
    }


def _comparison_metrics(summary: Dict[str, Any]) -> Dict[str, Any]:
    rows = summary.get("task_rows")
    if not isinstance(rows, list):
        return {}
    ligand_rows = [row for row in rows if str(row.get("kind", "")).strip() == "ligand_stress"]
    pass_to_fail = 0
    max_pr_drop = None
    max_top20_drop = None
    worst_pr_task = ""
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
        "pass_to_fail_count": int(pass_to_fail),
        "max_pr_auc_drop": max_pr_drop,
        "worst_pr_auc_task": worst_pr_task,
        "max_top20_hit_rate_drop": max_top20_drop,
        "worst_top20_task": worst_top20_task,
        "tasks_with_pr_improvement": int(summary.get("tasks_with_pr_improvement", 0) or 0),
        "tasks_with_pr_regression": int(summary.get("tasks_with_pr_regression", 0) or 0),
        "profile_changed_task_count": int(summary.get("profile_changed_task_count", 0) or 0),
    }


def _regression_diagnostics(summary: Dict[str, Any]) -> Dict[str, Any]:
    rows = summary.get("task_rows")
    if not isinstance(rows, list):
        rows = []
    ligand_rows = [row for row in rows if isinstance(row, dict) and str(row.get("kind", "")).strip() == "ligand_stress"]
    pass_to_fail_rows = [
        row for row in ligand_rows if bool(row.get("baseline_pass", False)) and not bool(row.get("candidate_pass", False))
    ]
    pass_to_fail_task_ids = [str(row.get("task_id", "") or "") for row in pass_to_fail_rows if str(row.get("task_id", "") or "")]

    def _worst_row(metric: str) -> Dict[str, Any]:
        with_values = [(row, _safe_float(row.get(metric))) for row in ligand_rows]
        with_values = [(row, value) for row, value in with_values if value is not None]
        if not with_values:
            return {}
        return dict(min(with_values, key=lambda item: item[1])[0])

    worst_pr_row = _worst_row("delta_pr_auc")
    worst_top20_row = _worst_row("delta_top20_hit_rate")
    primary = pass_to_fail_rows[0] if pass_to_fail_rows else (worst_pr_row or worst_top20_row or {})
    primary_task = str(primary.get("task_id", "") or "")
    primary_is_pass_to_fail = primary_task in set(pass_to_fail_task_ids)
    primary_is_worst_pr = bool(primary_task and primary_task == str(worst_pr_row.get("task_id", "") or ""))
    primary_is_worst_top20 = bool(primary_task and primary_task == str(worst_top20_row.get("task_id", "") or ""))
    reason_parts: List[str] = []
    if primary_is_pass_to_fail:
        reason_parts.append("pass_to_fail")
    if primary_is_worst_pr:
        reason_parts.append("worst_pr_auc")
    if primary_is_worst_top20:
        reason_parts.append("worst_top20")
    primary_reason = "_and_".join(reason_parts) if reason_parts else "ranking_regression"

    def _trim(row: Dict[str, Any]) -> Dict[str, Any]:
        keys = [
            "task_id",
            "domain",
            "baseline_pass",
            "candidate_pass",
            "baseline_pr_auc",
            "candidate_pr_auc",
            "delta_pr_auc",
            "baseline_top20_hit_rate",
            "candidate_top20_hit_rate",
            "delta_top20_hit_rate",
        ]
        return {key: row.get(key) for key in keys if key in row}

    return {
        "pass_to_fail_task_ids": pass_to_fail_task_ids,
        "pass_to_fail_count": int(len(pass_to_fail_task_ids)),
        "worst_pr_auc_task": str(worst_pr_row.get("task_id", "") or ""),
        "worst_pr_auc_delta": _safe_float(worst_pr_row.get("delta_pr_auc")),
        "worst_top20_task": str(worst_top20_row.get("task_id", "") or ""),
        "worst_top20_delta": _safe_float(worst_top20_row.get("delta_top20_hit_rate")),
        "primary_regression": _trim(dict(primary)) if primary else {},
        "primary_regression_task_id": primary_task,
        "primary_regression_domain": str(primary.get("domain", "") or ""),
        "primary_regression_reason": primary_reason,
    }


def _build_guardrail_rows(
    pilot: Dict[str, Any],
    comparison: Dict[str, Any],
    baseline_summary: Dict[str, Any],
    candidate_summary: Dict[str, Any],
    measured_speedup: Dict[str, Any],
) -> List[Dict[str, Any]]:
    comparison_metrics = _comparison_metrics(comparison) if comparison else {}
    baseline_pass_sets = _count_pass_sets(baseline_summary)
    candidate_pass_sets = _count_pass_sets(candidate_summary)
    rows: List[Dict[str, Any]] = []
    for row in pilot.get("guardrail_rows", []) if isinstance(pilot.get("guardrail_rows"), list) else []:
        guardrail_id = str(row.get("guardrail_id", "")).strip()
        observed_value = "pending"
        passed: Optional[bool] = None
        note = ""
        if comparison_metrics:
            if guardrail_id == "no_pass_to_fail":
                observed_value = str(comparison_metrics.get("pass_to_fail_count", 0))
                passed = int(comparison_metrics.get("pass_to_fail_count", 0)) == 0
                note = "candidate comparison available"
            elif guardrail_id == "pr_auc_drop_max_0p02":
                value = comparison_metrics.get("max_pr_auc_drop")
                observed_value = f"{value:.4f}" if isinstance(value, float) else "n/a"
                passed = (value is not None) and (value >= -0.02)
                worst = str(comparison_metrics.get("worst_pr_auc_task", "")).strip()
                if worst:
                    note = f"worst task: {worst}"
            elif guardrail_id == "top20_hit_drop_max_1":
                value = comparison_metrics.get("max_top20_hit_rate_drop")
                observed_value = f"{value:.4f}" if isinstance(value, float) else "n/a"
                passed = (value is not None) and (value >= -0.05)
                worst = str(comparison_metrics.get("worst_top20_task", "")).strip()
                if worst:
                    note = f"worst task: {worst}"
            elif guardrail_id == "slowest_domain_speedup_min_1p8x":
                slowest_row = measured_speedup.get("slowest_task", {}) if isinstance(measured_speedup.get("slowest_task"), dict) else {}
                value = _safe_float(slowest_row.get("end_to_end_speedup"))
                if value is None:
                    observed_value = "pending speed evidence"
                    passed = None
                    note = "needs measured baseline/candidate pipeline summaries for the slowest task"
                else:
                    observed_value = f"{value:.3f}x"
                    passed = bool(value >= 1.8)
                    task_id = str(slowest_row.get("task_id", "") or "").strip()
                    note = f"slowest task: {task_id}" if task_id else "derived from slowest task measured throughput"
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
    pilot_json: str,
    kpi_json: str,
    comparison_json: str,
    baseline_summary_json: str,
    candidate_summary_json: str,
) -> Dict[str, Any]:
    pilot = _read_json_if_exists(pilot_json)
    kpi = _read_json_if_exists(kpi_json)
    comparison = _read_json_if_exists(comparison_json)
    baseline_summary = _read_json_if_exists(baseline_summary_json)
    candidate_summary = _read_json_if_exists(candidate_summary_json)

    baseline_ready = bool(baseline_summary)
    candidate_ready = bool(candidate_summary)
    comparison_ready = bool(comparison)
    comparison_metrics = _comparison_metrics(comparison) if comparison_ready else {}
    regression_diagnostics = _regression_diagnostics(comparison) if comparison_ready else {}

    if comparison_ready:
        benchmark_stage = "post_run_comparison"
    elif candidate_ready:
        benchmark_stage = "candidate_run_ready_no_comparison"
    else:
        benchmark_stage = "prelaunch_scaffold"

    scope_summary = pilot.get("scope_summary", {}) if isinstance(pilot.get("scope_summary"), dict) else {}
    kpi_summary = kpi.get("summary", {}) if isinstance(kpi.get("summary"), dict) else {}
    slowest = kpi_summary.get("slowest_task_at_1m", {}) if isinstance(kpi_summary.get("slowest_task_at_1m"), dict) else {}
    measured_speedup = _measured_speedup_summary(
        baseline_summary=baseline_summary,
        candidate_summary=candidate_summary,
        slowest_task_id=str(slowest.get("task_id", "") or ""),
    )
    guardrail_rows = _build_guardrail_rows(pilot, comparison, baseline_summary, candidate_summary, measured_speedup)
    guardrail_pass_rows = [row for row in guardrail_rows if row.get("pass") is True]
    guardrail_fail_rows = [row for row in guardrail_rows if row.get("pass") is False]
    guardrail_pending_rows = [row for row in guardrail_rows if row.get("pass") is None]
    claim_safe = None
    claim_safe_status = "pending"
    if comparison_ready:
        claim_safe = bool(
            (comparison_metrics.get("pass_to_fail_count", 0) == 0)
            and all(row.get("pass") is not False for row in guardrail_rows if row.get("guardrail_id") != "slowest_domain_speedup_min_1p8x")
        )
        speed_row = next((row for row in guardrail_rows if row.get("guardrail_id") == "slowest_domain_speedup_min_1p8x"), None)
        if claim_safe is False:
            claim_safe_status = "regression_guardrail_failed"
        elif isinstance(speed_row, dict) and speed_row.get("pass") is True:
            claim_safe_status = "claim_safe_with_measured_speedup"
        elif isinstance(speed_row, dict) and speed_row.get("pass") is False:
            claim_safe_status = "claim_safe_but_speedup_guardrail_failed"
        else:
            claim_safe_status = "claim_safe_pending_speed_evidence"

    next_action = "collect_baseline_and_candidate_run artifacts"
    speed_row = next((row for row in guardrail_rows if row.get("guardrail_id") == "slowest_domain_speedup_min_1p8x"), None)
    if comparison_ready and claim_safe is False:
        primary_task = str(regression_diagnostics.get("primary_regression_task_id", "") or "")
        if primary_task:
            next_action = (
                f"guardrails failed on {primary_task}; inspect PR-AUC and top20 regressions before scaling further"
            )
        else:
            next_action = "guardrails failed; inspect worst PR-AUC and top20 regressions before scaling further"
    elif comparison_ready and isinstance(speed_row, dict) and speed_row.get("pass") is None:
        next_action = (
            "quality guardrails are claim-safe; attach measured throughput and artifact-size evidence "
            "to close the speedup guardrail"
        )
    elif comparison_ready and isinstance(speed_row, dict) and speed_row.get("pass") is False and claim_safe:
        next_action = "quality guardrails hold, but measured speedup is below threshold; tune the slowest domain before larger launch"
    elif comparison_ready and claim_safe and isinstance(speed_row, dict) and speed_row.get("pass") is True:
        next_action = "benchmark remains claim-safe with measured speedup; candidate is ready for larger-scale throughput runs"
    elif comparison_ready and claim_safe:
        next_action = "benchmark remains claim-safe; next step is measured throughput and artifact-size evidence"
    elif candidate_ready and not comparison_ready:
        next_action = "run comparison against the frozen baseline"

    return {
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "benchmark_stage": benchmark_stage,
        "comparison_kind": str(pilot.get("comparison_kind", "size_shift_operational_regression")),
        "baseline_artifact_ready": baseline_ready,
        "candidate_artifact_ready": candidate_ready,
        "comparison_artifact_ready": comparison_ready,
        "claim_safe": claim_safe,
        "claim_safe_status": claim_safe_status,
        "scope_summary": scope_summary,
        "kpi_summary": kpi_summary,
        "slowest_task_at_1m": slowest,
        "comparison_metrics": comparison_metrics,
        "regression_diagnostics": regression_diagnostics,
        "primary_regression_task_id": regression_diagnostics.get("primary_regression_task_id", ""),
        "primary_regression_domain": regression_diagnostics.get("primary_regression_domain", ""),
        "primary_regression_reason": regression_diagnostics.get("primary_regression_reason", ""),
        "measured_speedup_summary": measured_speedup,
        "guardrail_rows": guardrail_rows,
        "guardrail_pass_count": int(len(guardrail_pass_rows)),
        "guardrail_fail_count": int(len(guardrail_fail_rows)),
        "guardrail_pending_count": int(len(guardrail_pending_rows)),
        "preflight_notes": list(pilot.get("preflight_notes", []) if isinstance(pilot.get("preflight_notes"), list) else []),
        "recommended_next_action": next_action,
        "input_artifacts": {
            "pilot_json": str(_resolve_repo_path(pilot_json)),
            "kpi_json": str(_resolve_repo_path(kpi_json)),
            "comparison_json": str(_resolve_repo_path(comparison_json)),
            "baseline_summary_json": str(_resolve_repo_path(baseline_summary_json)),
            "candidate_summary_json": str(_resolve_repo_path(candidate_summary_json)),
        },
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a commercialization-oriented guardrail summary for the ligand scale-up benchmark."
    )
    parser.add_argument("--pilot-json", default=DEFAULT_PILOT_JSON)
    parser.add_argument("--kpi-json", default=DEFAULT_KPI_JSON)
    parser.add_argument("--comparison-json", default=DEFAULT_COMPARISON_JSON)
    parser.add_argument("--baseline-summary-json", default=DEFAULT_BASELINE_SUMMARY_JSON)
    parser.add_argument("--candidate-summary-json", default=DEFAULT_CANDIDATE_SUMMARY_JSON)
    parser.add_argument("--out-json", default="runs/ligand_scaleup_benchmark_summary_current.json")
    parser.add_argument("--out-csv", default="runs/ligand_scaleup_benchmark_summary_current.csv")
    parser.add_argument("--out-md", default="runs/ligand_scaleup_benchmark_summary_current.md")
    args = parser.parse_args(argv)

    payload = build_payload(
        pilot_json=args.pilot_json,
        kpi_json=args.kpi_json,
        comparison_json=args.comparison_json,
        baseline_summary_json=args.baseline_summary_json,
        candidate_summary_json=args.candidate_summary_json,
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
    lines = [
        "# Ligand Scale-Up Benchmark Summary",
        "",
        f"- generated_at_local: `{payload.get('generated_at_local', '')}`",
        f"- benchmark_stage: `{payload.get('benchmark_stage', '')}`",
        f"- comparison_kind: `{payload.get('comparison_kind', '')}`",
        f"- baseline_artifact_ready: `{payload.get('baseline_artifact_ready')}`",
        f"- candidate_artifact_ready: `{payload.get('candidate_artifact_ready')}`",
        f"- comparison_artifact_ready: `{payload.get('comparison_artifact_ready')}`",
        f"- claim_safe: `{payload.get('claim_safe')}`",
        f"- claim_safe_status: `{payload.get('claim_safe_status', '')}`",
        f"- recommended_next_action: `{payload.get('recommended_next_action', '')}`",
        f"- primary_regression_task_id: `{payload.get('primary_regression_task_id', '')}`",
        f"- primary_regression_domain: `{payload.get('primary_regression_domain', '')}`",
        f"- primary_regression_reason: `{payload.get('primary_regression_reason', '')}`",
        "",
        "## Scope",
        "",
        f"- full_task_count_100k: `{payload.get('scope_summary', {}).get('full_task_count_100k', '')}`",
        f"- smoke_task_count_unchanged: `{payload.get('scope_summary', {}).get('smoke_task_count_unchanged', '')}`",
        f"- domains_touched: `{payload.get('scope_summary', {}).get('domains_touched', [])}`",
        "",
        "## Slowest Task",
        "",
        f"- task_id: `{slowest.get('task_id', '')}`",
        f"- domain: `{slowest.get('domain', '')}`",
        f"- projected_1m_wall_hr: `{slowest.get('projected_1m_wall_hr', '')}`",
        f"- stage2_share_pct: `{slowest.get('stage2_share_pct', '')}`",
        "",
        "## Measured Speed Evidence",
        "",
        f"- common_task_count: `{payload.get('measured_speedup_summary', {}).get('common_task_count', '')}`",
        f"- tasks_with_stage2_speedup: `{payload.get('measured_speedup_summary', {}).get('tasks_with_stage2_speedup', '')}`",
        f"- tasks_with_end_to_end_speedup: `{payload.get('measured_speedup_summary', {}).get('tasks_with_end_to_end_speedup', '')}`",
        f"- median_stage2_speedup: `{payload.get('measured_speedup_summary', {}).get('median_stage2_speedup', '')}`",
        f"- median_end_to_end_speedup: `{payload.get('measured_speedup_summary', {}).get('median_end_to_end_speedup', '')}`",
        f"- slowest_task_measured: `{payload.get('measured_speedup_summary', {}).get('slowest_task_measured', '')}`",
        f"- slowest_task_measured_speedup: `{payload.get('measured_speedup_summary', {}).get('slowest_task', {}).get('end_to_end_speedup', '')}`",
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
