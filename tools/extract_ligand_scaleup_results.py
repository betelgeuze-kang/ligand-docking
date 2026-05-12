#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


ROOT = Path(__file__).resolve().parents[1]


def _resolve_repo_path(path_str: str) -> Path:
    path = Path(path_str)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _read_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _read_json_if_exists(path_str: str) -> Dict[str, Any]:
    if not str(path_str).strip():
        return {}
    path = _resolve_repo_path(path_str)
    if not path.exists():
        return {}
    return _read_json(path)


def _copied_artifact_path(task_payload: Dict[str, Any], path_str: str) -> str:
    if not str(path_str).strip():
        return ""
    expected_name = Path(str(path_str)).name
    for row in task_payload.get("copied_files", []) if isinstance(task_payload.get("copied_files"), list) else []:
        if not isinstance(row, dict):
            continue
        src = str(row.get("src") or "").strip()
        dst = str(row.get("dst") or "").strip()
        if not dst:
            continue
        if src == path_str or Path(src).name == expected_name or Path(dst).name == expected_name:
            return dst
    return ""


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _stage_duration_from_pipeline(pipeline_summary: Dict[str, Any], stage_key: str) -> Optional[float]:
    stages = pipeline_summary.get("stages", {}) if isinstance(pipeline_summary.get("stages"), dict) else {}
    stage = stages.get(stage_key, {}) if isinstance(stages.get(stage_key), dict) else {}
    return _safe_float(stage.get("duration_sec"))


def _stage_duration_from_task_log(task_payload: Dict[str, Any], stage_key: str) -> Optional[float]:
    log_path = str(task_payload.get("run_log") or "").strip()
    if not log_path:
        return None
    path = _resolve_repo_path(log_path)
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None
    marker = f'"{stage_key}"'
    idx = text.find(marker)
    if idx < 0:
        return None
    match = re.search(r'"duration_sec"\s*:\s*([0-9.eE+-]+)', text[idx : idx + 50000])
    if not match:
        return None
    return _safe_float(match.group(1))


def _extract_sla_metrics(task_payload: Dict[str, Any]) -> Dict[str, Any]:
    pipeline_summary_json = str(task_payload.get("pipeline_summary_json") or "").strip()
    if not pipeline_summary_json:
        return {}
    pipeline_summary = _read_json_if_exists(pipeline_summary_json)
    if not pipeline_summary:
        copied_pipeline = _copied_artifact_path(task_payload, pipeline_summary_json)
        if copied_pipeline:
            pipeline_summary = _read_json_if_exists(copied_pipeline)
            if pipeline_summary:
                pipeline_summary_json = copied_pipeline
    artifacts = pipeline_summary.get("artifacts", {}) if isinstance(pipeline_summary.get("artifacts"), dict) else {}
    sla_summary_json = str(artifacts.get("sla_summary_json") or "").strip()
    stage8_sla = pipeline_summary.get("stages", {}).get("stage8_sla", {}) if isinstance(pipeline_summary.get("stages"), dict) else {}
    if not sla_summary_json and not isinstance(stage8_sla, dict):
        return {}
    sla_summary = _read_json_if_exists(sla_summary_json)
    if not sla_summary and isinstance(stage8_sla, dict):
        sla_summary = stage8_sla
    durations = sla_summary.get("durations_sec", {}) if isinstance(sla_summary.get("durations_sec"), dict) else {}
    stage2_sec = _safe_float(durations.get("stage2_trajectory_sec"))
    if stage2_sec in (None, 0.0):
        stage2_sec = _stage_duration_from_pipeline(pipeline_summary, "stage2_trajectory_generation")
    if stage2_sec in (None, 0.0):
        stage2_sec = _stage_duration_from_task_log(task_payload, "stage2_trajectory_generation")
    total_sec = _safe_float(sla_summary.get("total_latency_sec"))
    queue_rows = _safe_float(sla_summary.get("queue_rows"))
    stage2_share_pct = None
    if stage2_sec is not None and total_sec not in (None, 0.0):
        stage2_share_pct = 100.0 * stage2_sec / total_sec
    return {
        "pipeline_summary_json": pipeline_summary_json,
        "sla_summary_json": sla_summary_json,
        "queue_rows": queue_rows,
        "stage2_runtime_sec": stage2_sec,
        "total_runtime_sec": total_sec,
        "stage2_share_pct": stage2_share_pct,
        "queue_rate_stage2_rows_per_sec": _safe_float(sla_summary.get("queue_rate_stage2_rows_per_sec")),
        "queue_rate_stage3_rows_per_sec": _safe_float(sla_summary.get("queue_rate_stage3_rows_per_sec")),
    }


def _task_index_from_run_root(run_root: str) -> Dict[Tuple[str, str], Dict[str, Any]]:
    if not str(run_root).strip():
        return {}
    summary_json = _resolve_repo_path(str(Path(run_root) / "summary.json"))
    if not summary_json.exists():
        return {}
    summary = _read_json(summary_json)
    index: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for set_row in summary.get("sets", []) if isinstance(summary.get("sets"), list) else []:
        set_id = str(set_row.get("set_id", "")).strip()
        for task in set_row.get("tasks", []) if isinstance(set_row.get("tasks"), list) else []:
            if str(task.get("kind", "")).strip() != "ligand_stress":
                continue
            task_id = str(task.get("task_id", "")).strip()
            if not set_id or not task_id:
                continue
            metrics = _extract_sla_metrics(task)
            index[(set_id, task_id)] = {
                "set_id": set_id,
                "task_id": task_id,
                "domain": str(task.get("domain", "")).strip(),
                "pass": bool(task.get("pass", False)),
                **metrics,
            }
    return index


def _comparison_index(comparison_json: str) -> Dict[Tuple[str, str], Dict[str, Any]]:
    payload = _read_json_if_exists(comparison_json)
    rows = payload.get("task_rows", []) if isinstance(payload.get("task_rows"), list) else []
    index: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for row in rows:
        if str(row.get("kind", "")).strip() != "ligand_stress":
            continue
        set_id = str(row.get("set_id", "")).strip()
        task_id = str(row.get("task_id", "")).strip()
        if not set_id or not task_id:
            continue
        index[(set_id, task_id)] = {
            "set_id": set_id,
            "task_id": task_id,
            "domain": str(row.get("domain", "")).strip(),
            "baseline_pass": bool(row.get("baseline_pass", False)),
            "candidate_pass": bool(row.get("candidate_pass", False)),
            "delta_pr_auc": _safe_float(row.get("delta_pr_auc")),
            "delta_top20_hit_rate": _safe_float(row.get("delta_top20_hit_rate")),
        }
    return index


def build_payload(*, baseline_run_root: str = "", candidate_run_root: str = "", comparison_json: str = "") -> Dict[str, Any]:
    baseline_index = _task_index_from_run_root(baseline_run_root)
    candidate_index = _task_index_from_run_root(candidate_run_root)
    comparison_index = _comparison_index(comparison_json)
    keys = sorted(set(baseline_index) | set(candidate_index) | set(comparison_index))
    rows: List[Dict[str, Any]] = []
    measured_stage2_speedup_count = 0
    measured_total_speedup_count = 0
    for key in keys:
        base = baseline_index.get(key, {})
        cand = candidate_index.get(key, {})
        comp = comparison_index.get(key, {})
        stage2_speedup = None
        total_speedup = None
        base_stage2 = _safe_float(base.get("stage2_runtime_sec"))
        cand_stage2 = _safe_float(cand.get("stage2_runtime_sec"))
        if base_stage2 not in (None, 0.0) and cand_stage2 not in (None, 0.0):
            stage2_speedup = base_stage2 / cand_stage2
            measured_stage2_speedup_count += 1
        base_total = _safe_float(base.get("total_runtime_sec"))
        cand_total = _safe_float(cand.get("total_runtime_sec"))
        if base_total not in (None, 0.0) and cand_total not in (None, 0.0):
            total_speedup = base_total / cand_total
            measured_total_speedup_count += 1
        rows.append(
            {
                "set_id": key[0],
                "task_id": key[1],
                "domain": str(base.get("domain") or cand.get("domain") or comp.get("domain") or ""),
                "baseline_pass": base.get("pass"),
                "candidate_pass": cand.get("pass"),
                "comparison_baseline_pass": comp.get("baseline_pass"),
                "comparison_candidate_pass": comp.get("candidate_pass"),
                "baseline_queue_rows": base.get("queue_rows"),
                "candidate_queue_rows": cand.get("queue_rows"),
                "baseline_stage2_runtime_sec": base.get("stage2_runtime_sec"),
                "candidate_stage2_runtime_sec": cand.get("stage2_runtime_sec"),
                "baseline_total_runtime_sec": base.get("total_runtime_sec"),
                "candidate_total_runtime_sec": cand.get("total_runtime_sec"),
                "baseline_stage2_share_pct": base.get("stage2_share_pct"),
                "candidate_stage2_share_pct": cand.get("stage2_share_pct"),
                "baseline_queue_rate_stage2_rows_per_sec": base.get("queue_rate_stage2_rows_per_sec"),
                "candidate_queue_rate_stage2_rows_per_sec": cand.get("queue_rate_stage2_rows_per_sec"),
                "baseline_queue_rate_stage3_rows_per_sec": base.get("queue_rate_stage3_rows_per_sec"),
                "candidate_queue_rate_stage3_rows_per_sec": cand.get("queue_rate_stage3_rows_per_sec"),
                "measured_stage2_speedup": stage2_speedup,
                "measured_total_speedup": total_speedup,
                "delta_pr_auc": comp.get("delta_pr_auc"),
                "delta_top20_hit_rate": comp.get("delta_top20_hit_rate"),
                "baseline_pipeline_summary_json": base.get("pipeline_summary_json"),
                "candidate_pipeline_summary_json": cand.get("pipeline_summary_json"),
                "baseline_sla_summary_json": base.get("sla_summary_json"),
                "candidate_sla_summary_json": cand.get("sla_summary_json"),
            }
        )

    return {
        "baseline_run_root": str(_resolve_repo_path(baseline_run_root)) if str(baseline_run_root).strip() else "",
        "candidate_run_root": str(_resolve_repo_path(candidate_run_root)) if str(candidate_run_root).strip() else "",
        "comparison_json": str(_resolve_repo_path(comparison_json)) if str(comparison_json).strip() else "",
        "task_count": len(rows),
        "measured_stage2_speedup_count": measured_stage2_speedup_count,
        "measured_total_speedup_count": measured_total_speedup_count,
        "rows": rows,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract per-task commercialization/scalability runtime metrics from baseline/candidate run roots and comparison artifacts."
    )
    parser.add_argument("--baseline-run-root", default="")
    parser.add_argument("--candidate-run-root", default="")
    parser.add_argument("--comparison-json", default="")
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-csv", default="")
    args = parser.parse_args(argv)

    payload = build_payload(
        baseline_run_root=args.baseline_run_root,
        candidate_run_root=args.candidate_run_root,
        comparison_json=args.comparison_json,
    )

    if args.out_json:
        out_json = _resolve_repo_path(args.out_json)
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))

    if args.out_csv:
        out_csv = _resolve_repo_path(args.out_csv)
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        with out_csv.open("w", encoding="utf-8", newline="") as fh:
            fieldnames = list(payload["rows"][0].keys()) if payload["rows"] else ["set_id", "task_id", "domain"]
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for row in payload["rows"]:
                writer.writerow(row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
