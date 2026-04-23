#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_BASELINE_RUN_ROOT = "runs/external_validation_blind_runs/external_validation_blind_runs_2026-03-22_biorxiv_v7r1"
DEFAULT_CANDIDATE_RUN_ROOT = "runs/external_validation_blind_runs/external_validation_blind_runs_2026-03-25_gpcr_residual_ab_shadow_v1"
DEFAULT_OUT_JSON = "runs/gpcr_residual_ab_comparison_current.json"
DEFAULT_OUT_CSV = "runs/gpcr_residual_ab_comparison_current.csv"
DEFAULT_OUT_MD = "runs/gpcr_residual_ab_comparison_current.md"

TASK_IDS = ("gpcr_core_full", "gpcr_chembl50_full")


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _task_map(state_json: Path) -> dict[str, dict[str, Any]]:
    state = _read_json(state_json)
    out: dict[str, dict[str, Any]] = {}
    for set_row in state.get("sets", []):
        for task in set_row.get("tasks", []):
            task_id = str(task.get("task_id", "")).strip()
            if task_id in TASK_IDS:
                row = dict(task)
                row["set_id"] = str(set_row.get("set_id", "")).strip()
                out[task_id] = row
    return out


def _safe_metrics(task: dict[str, Any]) -> dict[str, Any]:
    metrics = task.get("metrics", {}) if isinstance(task.get("metrics"), dict) else {}
    return {
        "pass": bool(task.get("pass", False)),
        "run_ok": bool(task.get("run_ok", False)),
        "ranking_unique_auc": metrics.get("ranking_unique_auc"),
        "ranking_pr_auc": metrics.get("ranking_pr_auc"),
        "ranking_ef1": metrics.get("ranking_ef1"),
        "operational_gate_pass": metrics.get("operational_gate_pass"),
        "strict_gate_pass": metrics.get("strict_gate_pass"),
    }


def _residual_meta(task: dict[str, Any]) -> dict[str, Any]:
    pipeline_summary_json = str(task.get("pipeline_summary_json", "") or "").strip()
    if not pipeline_summary_json:
        return {}
    path = Path(pipeline_summary_json)
    if not path.exists():
        return {}
    payload = _read_json(path)
    summary = payload.get("summary", payload) if isinstance(payload, dict) else {}
    res = summary.get("residual_prototype", {}) if isinstance(summary, dict) else {}
    if isinstance(res, dict) and res:
        return dict(res)

    if not isinstance(payload, dict):
        return {}
    stage3 = ((payload.get("stages") or {}).get("stage3_backmapping_scoring") or {})
    if not isinstance(stage3, dict):
        return {}
    cmd = stage3.get("cmd", [])
    stage3_summary_json = ""
    if isinstance(cmd, list):
        for idx, item in enumerate(cmd):
            if str(item) == "--out-summary-json" and idx + 1 < len(cmd):
                stage3_summary_json = str(cmd[idx + 1])
                break
    if not stage3_summary_json:
        return {}
    stage3_path = Path(stage3_summary_json)
    if not stage3_path.exists():
        return {}
    stage3_payload = _read_json(stage3_path)
    stage3_summary = stage3_payload.get("summary", stage3_payload) if isinstance(stage3_payload, dict) else {}
    res = stage3_summary.get("residual_prototype", {}) if isinstance(stage3_summary, dict) else {}
    return dict(res) if isinstance(res, dict) else {}


def _delta(candidate: Any, baseline: Any) -> float | None:
    try:
        if candidate is None or baseline is None:
            return None
        return float(candidate) - float(baseline)
    except Exception:
        return None


def build_payload(*, baseline_run_root: Path, candidate_run_root: Path) -> dict[str, Any]:
    baseline_tasks = _task_map(baseline_run_root / "state.json")
    candidate_tasks = _task_map(candidate_run_root / "state.json")
    rows: list[dict[str, Any]] = []
    completed = 0
    candidate_with_shadow = 0
    for task_id in TASK_IDS:
        baseline = baseline_tasks.get(task_id, {})
        candidate = candidate_tasks.get(task_id, {})
        b = _safe_metrics(baseline)
        c = _safe_metrics(candidate)
        residual = _residual_meta(candidate)
        candidate_complete = bool(candidate) and str(candidate.get("service_failed_stage", "") or "") != "" or bool(candidate.get("summary_json"))
        if candidate and Path(str(candidate.get("summary_json", "") or "")).exists():
            candidate_complete = True
        if candidate_complete:
            completed += 1
        if residual.get("enabled"):
            candidate_with_shadow += 1
        rows.append(
            {
                "task_id": task_id,
                "set_id": str(candidate.get("set_id", baseline.get("set_id", "")) or ""),
                "baseline_pass": b["pass"],
                "candidate_pass": c["pass"] if candidate else None,
                "candidate_complete": bool(candidate_complete),
                "baseline_pr_auc": b["ranking_pr_auc"],
                "candidate_pr_auc": c["ranking_pr_auc"] if candidate else None,
                "delta_pr_auc": _delta(c["ranking_pr_auc"], b["ranking_pr_auc"]) if candidate else None,
                "baseline_ef1": b["ranking_ef1"],
                "candidate_ef1": c["ranking_ef1"] if candidate else None,
                "delta_ef1": _delta(c["ranking_ef1"], b["ranking_ef1"]) if candidate else None,
                "baseline_unique_auc": b["ranking_unique_auc"],
                "candidate_unique_auc": c["ranking_unique_auc"] if candidate else None,
                "delta_unique_auc": _delta(c["ranking_unique_auc"], b["ranking_unique_auc"]) if candidate else None,
                "baseline_operational_gate_pass": b["operational_gate_pass"],
                "candidate_operational_gate_pass": c["operational_gate_pass"] if candidate else None,
                "residual_enabled": bool(residual.get("enabled", False)),
                "residual_mode": str(residual.get("mode", "") or ""),
                "residual_status": str(residual.get("status", "") or ""),
                "residual_positive_delta_count": residual.get("positive_delta_count"),
                "residual_yellow_band_count": residual.get("yellow_band_count"),
                "residual_mean_delta": residual.get("mean_delta"),
                "residual_max_delta": residual.get("max_delta"),
            }
        )

    payload = {
        "baseline_run_root": str(baseline_run_root.resolve()),
        "candidate_run_root": str(candidate_run_root.resolve()),
        "task_count": len(rows),
        "completed_candidate_tasks": completed,
        "candidate_with_shadow_rows": candidate_with_shadow,
        "all_candidate_tasks_complete": completed == len(rows),
        "rows": rows,
    }
    return payload


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# GPCR Residual A/B Comparison",
        "",
        f"- baseline_run_root: `{payload['baseline_run_root']}`",
        f"- candidate_run_root: `{payload['candidate_run_root']}`",
        f"- task_count: `{payload['task_count']}`",
        f"- completed_candidate_tasks: `{payload['completed_candidate_tasks']}`",
        f"- candidate_with_shadow_rows: `{payload['candidate_with_shadow_rows']}`",
        f"- all_candidate_tasks_complete: `{payload['all_candidate_tasks_complete']}`",
        "",
        "| task_id | candidate_complete | baseline_pass | candidate_pass | delta_pr_auc | delta_ef1 | residual_positive_delta_count | residual_mean_delta | residual_status |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['task_id']} | {row['candidate_complete']} | {row['baseline_pass']} | {row['candidate_pass']} | "
            f"{row['delta_pr_auc']} | {row['delta_ef1']} | {row['residual_positive_delta_count']} | "
            f"{row['residual_mean_delta']} | {row['residual_status']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build a partial-safe comparison for the current GPCR residual equal-size A/B run.")
    p.add_argument("--baseline-run-root", default=DEFAULT_BASELINE_RUN_ROOT)
    p.add_argument("--candidate-run-root", default=DEFAULT_CANDIDATE_RUN_ROOT)
    p.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    p.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    p.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        baseline_run_root=_resolve(args.baseline_run_root),
        candidate_run_root=_resolve(args.candidate_run_root),
    )
    _write_json(_resolve(args.out_json), payload)
    _write_csv(_resolve(args.out_csv), payload["rows"])
    _write_markdown(_resolve(args.out_md), payload)


if __name__ == "__main__":
    main()
