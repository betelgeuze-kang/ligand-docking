#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.build_gpcr_residual_ab_comparison import (
    _delta,
    _residual_meta,
    _resolve,
    _safe_metrics,
    _task_map,
    _write_csv,
    _write_json,
)

DEFAULT_BASELINE_RUN_ROOT = "runs/external_validation_blind_runs/external_validation_blind_runs_2026-03-22_biorxiv_v7r1"
DEFAULT_SHADOW_RUN_ROOT = "runs/external_validation_blind_runs/external_validation_blind_runs_2026-03-25_gpcr_residual_ab_lockeddecoy_v1"
DEFAULT_APPLY_RUN_ROOT = "runs/external_validation_blind_runs/external_validation_blind_runs_2026-03-25_gpcr_residual_ab_apply_lockeddecoy_v1"
DEFAULT_OUT_JSON = "runs/gpcr_residual_mode_comparison_current.json"
DEFAULT_OUT_CSV = "runs/gpcr_residual_mode_comparison_current.csv"
DEFAULT_OUT_MD = "runs/gpcr_residual_mode_comparison_current.md"

TASK_IDS = ("gpcr_core_full", "gpcr_chembl50_full")


def _task_complete(task: dict[str, Any]) -> bool:
    complete = bool(task) and (str(task.get("service_failed_stage", "") or "") != "" or bool(task.get("summary_json")))
    if task and Path(str(task.get("summary_json", "") or "")).exists():
        complete = True
    return bool(complete)


def build_payload(*, baseline_run_root: Path, shadow_run_root: Path, apply_run_root: Path) -> dict[str, Any]:
    baseline_tasks = _task_map(baseline_run_root / "state.json")
    shadow_tasks = _task_map(shadow_run_root / "state.json")
    apply_tasks = _task_map(apply_run_root / "state.json")
    rows: list[dict[str, Any]] = []
    completed_apply = 0
    for task_id in TASK_IDS:
        baseline = baseline_tasks.get(task_id, {})
        shadow = shadow_tasks.get(task_id, {})
        apply = apply_tasks.get(task_id, {})
        b = _safe_metrics(baseline)
        s = _safe_metrics(shadow)
        a = _safe_metrics(apply)
        shadow_res = _residual_meta(shadow)
        apply_res = _residual_meta(apply)
        apply_complete = _task_complete(apply)
        if apply_complete:
            completed_apply += 1
        rows.append(
            {
                "task_id": task_id,
                "baseline_pass": b["pass"],
                "shadow_pass": s["pass"] if shadow else None,
                "apply_pass": a["pass"] if apply else None,
                "shadow_complete": _task_complete(shadow),
                "apply_complete": apply_complete,
                "baseline_pr_auc": b["ranking_pr_auc"],
                "shadow_pr_auc": s["ranking_pr_auc"] if shadow else None,
                "apply_pr_auc": a["ranking_pr_auc"] if apply else None,
                "delta_pr_auc_shadow_vs_baseline": _delta(s["ranking_pr_auc"], b["ranking_pr_auc"]) if shadow else None,
                "delta_pr_auc_apply_vs_baseline": _delta(a["ranking_pr_auc"], b["ranking_pr_auc"]) if apply else None,
                "delta_pr_auc_apply_vs_shadow": _delta(a["ranking_pr_auc"], s["ranking_pr_auc"]) if shadow and apply else None,
                "baseline_ef1": b["ranking_ef1"],
                "shadow_ef1": s["ranking_ef1"] if shadow else None,
                "apply_ef1": a["ranking_ef1"] if apply else None,
                "delta_ef1_shadow_vs_baseline": _delta(s["ranking_ef1"], b["ranking_ef1"]) if shadow else None,
                "delta_ef1_apply_vs_baseline": _delta(a["ranking_ef1"], b["ranking_ef1"]) if apply else None,
                "delta_ef1_apply_vs_shadow": _delta(a["ranking_ef1"], s["ranking_ef1"]) if shadow and apply else None,
                "shadow_residual_mode": str(shadow_res.get("mode", "") or ""),
                "apply_residual_mode": str(apply_res.get("mode", "") or ""),
                "shadow_residual_positive_delta_count": shadow_res.get("positive_delta_count"),
                "apply_residual_positive_delta_count": apply_res.get("positive_delta_count"),
                "shadow_residual_mean_delta": shadow_res.get("mean_delta"),
                "apply_residual_mean_delta": apply_res.get("mean_delta"),
                "shadow_residual_status": str(shadow_res.get("status", "") or ""),
                "apply_residual_status": str(apply_res.get("status", "") or ""),
            }
        )

    return {
        "baseline_run_root": str(baseline_run_root.resolve()),
        "shadow_run_root": str(shadow_run_root.resolve()),
        "apply_run_root": str(apply_run_root.resolve()),
        "task_count": len(rows),
        "completed_apply_tasks": completed_apply,
        "all_apply_tasks_complete": completed_apply == len(rows),
        "rows": rows,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# GPCR Residual Mode Comparison",
        "",
        f"- baseline_run_root: `{payload['baseline_run_root']}`",
        f"- shadow_run_root: `{payload['shadow_run_root']}`",
        f"- apply_run_root: `{payload['apply_run_root']}`",
        f"- task_count: `{payload['task_count']}`",
        f"- completed_apply_tasks: `{payload['completed_apply_tasks']}`",
        f"- all_apply_tasks_complete: `{payload['all_apply_tasks_complete']}`",
        "",
        "| task_id | shadow_pass | apply_pass | d_pr_shadow_base | d_pr_apply_base | d_pr_apply_shadow | d_ef1_shadow_base | d_ef1_apply_base | d_ef1_apply_shadow | shadow_mean_delta | apply_mean_delta |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['task_id']} | {row['shadow_pass']} | {row['apply_pass']} | "
            f"{row['delta_pr_auc_shadow_vs_baseline']} | {row['delta_pr_auc_apply_vs_baseline']} | {row['delta_pr_auc_apply_vs_shadow']} | "
            f"{row['delta_ef1_shadow_vs_baseline']} | {row['delta_ef1_apply_vs_baseline']} | {row['delta_ef1_apply_vs_shadow']} | "
            f"{row['shadow_residual_mean_delta']} | {row['apply_residual_mean_delta']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build a 3-way baseline/shadow/apply comparison for the current GPCR locked-decoy experiments.")
    p.add_argument("--baseline-run-root", default=DEFAULT_BASELINE_RUN_ROOT)
    p.add_argument("--shadow-run-root", default=DEFAULT_SHADOW_RUN_ROOT)
    p.add_argument("--apply-run-root", default=DEFAULT_APPLY_RUN_ROOT)
    p.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    p.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    p.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        baseline_run_root=_resolve(args.baseline_run_root),
        shadow_run_root=_resolve(args.shadow_run_root),
        apply_run_root=_resolve(args.apply_run_root),
    )
    _write_json(_resolve(args.out_json), payload)
    _write_csv(_resolve(args.out_csv), payload["rows"])
    _write_markdown(_resolve(args.out_md), payload)


if __name__ == "__main__":
    main()
