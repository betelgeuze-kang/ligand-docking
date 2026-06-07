#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import glob
import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_SCAFFOLD_JSON = "runs/cross_family_locked_decoy_shadow_current.json"
DEFAULT_OUT_JSON = "runs/cross_family_locked_decoy_shadow_comparison_current.json"
DEFAULT_OUT_CSV = "runs/cross_family_locked_decoy_shadow_comparison_current.csv"
DEFAULT_OUT_MD = "runs/cross_family_locked_decoy_shadow_comparison_current.md"
TARGET_PROTOCOL_ID = "cross_family_locked_decoy_shadow_v1"


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


def _latest_candidate_run_root(protocol_id: str = TARGET_PROTOCOL_ID) -> Path:
    candidates: list[tuple[float, Path]] = []
    pattern = str((ROOT / "runs" / "external_validation_blind_runs" / "external_validation_blind_runs_*").resolve())
    for run_path_str in glob.glob(pattern):
        run_root = Path(run_path_str)
        state_json = run_root / "state.json"
        if not state_json.exists():
            continue
        try:
            state = _read_json(state_json)
        except Exception:
            continue
        if str(state.get("protocol_id", "")).strip() != protocol_id:
            continue
        candidates.append((state_json.stat().st_mtime, run_root))
    if not candidates:
        raise FileNotFoundError(f"No run root found for protocol_id={protocol_id}")
    return max(candidates, key=lambda item: item[0])[1]


def _task_map(state_json: Path, expected_task_ids: set[str]) -> dict[str, dict[str, Any]]:
    state = _read_json(state_json)
    out: dict[str, dict[str, Any]] = {}
    for set_row in state.get("sets", []):
        set_id = str(set_row.get("set_id", "")).strip()
        for task in set_row.get("tasks", []):
            task_id = str(task.get("task_id", "")).strip()
            if task_id not in expected_task_ids:
                continue
            row = dict(task)
            row["set_id"] = set_id
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
        "ranking_bedroc": metrics.get("ranking_bedroc"),
        "operational_gate_pass": metrics.get("operational_gate_pass"),
        "strict_gate_pass": metrics.get("strict_gate_pass"),
    }


def _task_complete(task: dict[str, Any]) -> bool:
    if not task:
        return False
    summary_json = str(task.get("summary_json", "") or "").strip()
    if summary_json and Path(summary_json).exists():
        return True
    if str(task.get("service_failed_stage", "") or "").strip():
        return True
    return False


def _residual_meta(task: dict[str, Any]) -> dict[str, Any]:
    pipeline_summary_json = str(task.get("pipeline_summary_json", "") or "").strip()
    if not pipeline_summary_json:
        return {}
    path = Path(pipeline_summary_json)
    if not path.exists():
        return {}
    payload = _read_json(path)
    summary = payload.get("summary", payload) if isinstance(payload, dict) else {}
    if isinstance(summary, dict):
        residual = summary.get("residual_prototype", {})
        if isinstance(residual, dict) and residual:
            return dict(residual)
    stages = payload.get("stages", {}) if isinstance(payload, dict) else {}
    stage3 = stages.get("stage3_backmapping_scoring", {}) if isinstance(stages, dict) else {}
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
    if not isinstance(stage3_summary, dict):
        return {}
    residual = stage3_summary.get("residual_prototype", {})
    return dict(residual) if isinstance(residual, dict) else {}


def _delta(candidate: Any, baseline: Any) -> float | None:
    try:
        if candidate is None or baseline is None:
            return None
        return float(candidate) - float(baseline)
    except Exception:
        return None


def _proc_lines(tag: str) -> list[str]:
    try:
        out = subprocess.check_output(["pgrep", "-af", tag], text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return []
    rows: list[str] = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        if "pgrep -af" in line:
            continue
        if "build_cross_family_locked_decoy_shadow_comparison.py" in line:
            continue
        if "monitor_cross_family_locked_decoy_shadow.py" in line:
            continue
        if "monitor_biorxiv_external_validation.py" in line:
            continue
        rows.append(line)
    return rows


def _family_rows(task_rows: list[dict[str, Any]], family_scope: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for family in family_scope:
        family_tasks = [row for row in task_rows if row["family"] == family]
        completed = [row for row in family_tasks if row["candidate_complete"]]
        deltas = [abs(row["delta_pr_auc"]) for row in completed if row["delta_pr_auc"] is not None]
        rows.append(
            {
                "family": family,
                "task_count": len(family_tasks),
                "completed_candidate_tasks": len(completed),
                "candidate_fail_count": sum(1 for row in completed if row["candidate_pass"] is False),
                "candidate_shadow_enabled_count": sum(1 for row in completed if row["residual_enabled"]),
                "max_abs_delta_pr_auc": max(deltas) if deltas else None,
            }
        )
    return rows


def _set_rows(task_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for set_id in sorted({row["set_id"] for row in task_rows}):
        set_tasks = [row for row in task_rows if row["set_id"] == set_id]
        completed = [row for row in set_tasks if row["candidate_complete"]]
        out.append(
            {
                "set_id": set_id,
                "task_count": len(set_tasks),
                "completed_candidate_tasks": len(completed),
                "candidate_fail_count": sum(1 for row in completed if row["candidate_pass"] is False),
            }
        )
    return out


def build_payload(*, scaffold_json: Path, baseline_run_root: Path | None = None, candidate_run_root: Path | None = None) -> dict[str, Any]:
    scaffold = _read_json(scaffold_json)
    expected_rows = list(scaffold.get("profile_rows", []))
    expected_task_ids = {str(row.get("task_id", "")).strip() for row in expected_rows if str(row.get("task_id", "")).strip()}
    if baseline_run_root is None:
        baseline_run_root = _resolve(str(scaffold.get("baseline_run_root", "")))
    if candidate_run_root is None:
        candidate_run_root = _latest_candidate_run_root(TARGET_PROTOCOL_ID)

    baseline_tasks = _task_map(baseline_run_root / "state.json", expected_task_ids)
    candidate_tasks = _task_map(candidate_run_root / "state.json", expected_task_ids)
    candidate_state = _read_json(candidate_run_root / "state.json")
    candidate_tag = str(candidate_state.get("tag", "") or "").strip()
    if not candidate_tag:
        prefix = "external_validation_blind_runs_"
        name = candidate_run_root.name
        candidate_tag = name[len(prefix) :] if name.startswith(prefix) else name
    live_processes = _proc_lines(candidate_tag)

    task_rows: list[dict[str, Any]] = []
    for expected in expected_rows:
        task_id = str(expected.get("task_id", "")).strip()
        baseline = baseline_tasks.get(task_id, {})
        candidate = candidate_tasks.get(task_id, {})
        b = _safe_metrics(baseline)
        c = _safe_metrics(candidate)
        residual = _residual_meta(candidate)
        candidate_complete = _task_complete(candidate)
        task_rows.append(
            {
                "set_id": str(expected.get("set_id", candidate.get("set_id", baseline.get("set_id", ""))) or ""),
                "task_id": task_id,
                "family": str(expected.get("family", "")).strip(),
                "domain": str(expected.get("domain", "")).strip(),
                "ligand_sizes": str(expected.get("ligand_sizes", "")).strip(),
                "locked_decoy_labels_csv": str(expected.get("locked_decoy_labels_csv", "")).strip(),
                "locked_decoy_split_csv": str(expected.get("locked_decoy_split_csv", "")).strip(),
                "baseline_complete": bool(baseline),
                "candidate_complete": candidate_complete,
                "baseline_pass": b["pass"] if baseline else None,
                "candidate_pass": c["pass"] if candidate else None,
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
                "residual_family": str(residual.get("family", "") or ""),
                "residual_status": str(residual.get("status", "") or ""),
                "residual_tuning_variant": str(residual.get("tuning_variant", "") or ""),
                "residual_positive_delta_count": residual.get("positive_delta_count"),
                "residual_yellow_band_count": residual.get("yellow_band_count"),
                "residual_mean_delta": residual.get("mean_delta"),
                "residual_max_delta": residual.get("max_delta"),
                "candidate_pipeline_summary_present": bool(str(candidate.get("pipeline_summary_json", "") or "").strip() and Path(str(candidate.get("pipeline_summary_json"))).exists()) if candidate else False,
                "candidate_summary_present": bool(str(candidate.get("summary_json", "") or "").strip() and Path(str(candidate.get("summary_json"))).exists()) if candidate else False,
            }
        )

    family_rows = _family_rows(task_rows, list(scaffold.get("family_scope", [])))
    set_rows = _set_rows(task_rows)
    completed_candidate_tasks = sum(1 for row in task_rows if row["candidate_complete"])
    candidate_fail_count = sum(1 for row in task_rows if row["candidate_complete"] and row["candidate_pass"] is False)
    summary = {
        "comparison_kind": str(scaffold.get("comparison_kind", "cross_family_locked_decoy_shadow")),
        "family_scope": list(scaffold.get("family_scope", [])),
        "baseline_run_root": str(baseline_run_root.resolve()),
        "candidate_run_root": str(candidate_run_root.resolve()),
        "candidate_run_status": str(candidate_state.get("status", "") or ""),
        "task_count": len(task_rows),
        "completed_candidate_tasks": completed_candidate_tasks,
        "candidate_fail_count": candidate_fail_count,
        "all_candidate_tasks_complete": completed_candidate_tasks == len(task_rows),
        "live_process_count": len(live_processes),
        "comparison_ready": bool(
            str(candidate_state.get("status", "")).strip().lower() == "completed"
            and completed_candidate_tasks == len(task_rows)
            and len(live_processes) == 0
        ),
        "next_required_step": (
            "Interpret completed ion/kinase shadow deltas and decide whether the global cross-family shell can remain shadow-only or needs a tighter noop-family contract."
            if str(candidate_state.get("status", "")).strip().lower() == "completed" and completed_candidate_tasks == len(task_rows) and len(live_processes) == 0
            else "Wait for the running cross-family shadow candidate to finish, then rerun this builder for final baseline-vs-candidate interpretation."
        ),
    }
    return {
        "summary": summary,
        "set_rows": set_rows,
        "family_rows": family_rows,
        "task_rows": task_rows,
        "live_processes": live_processes,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Cross-Family Locked-Decoy Shadow Comparison",
        "",
        f"- comparison_kind: `{summary['comparison_kind']}`",
        f"- baseline_run_root: `{summary['baseline_run_root']}`",
        f"- candidate_run_root: `{summary['candidate_run_root']}`",
        f"- candidate_run_status: `{summary['candidate_run_status']}`",
        f"- task_count: `{summary['task_count']}`",
        f"- completed_candidate_tasks: `{summary['completed_candidate_tasks']}`",
        f"- candidate_fail_count: `{summary['candidate_fail_count']}`",
        f"- live_process_count: `{summary['live_process_count']}`",
        f"- comparison_ready: `{summary['comparison_ready']}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Family Rollup",
        "",
        "| family | task_count | completed_candidate_tasks | candidate_fail_count | candidate_shadow_enabled_count | max_abs_delta_pr_auc |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["family_rows"]:
        lines.append(
            f"| {row['family']} | {row['task_count']} | {row['completed_candidate_tasks']} | {row['candidate_fail_count']} | {row['candidate_shadow_enabled_count']} | {row['max_abs_delta_pr_auc']} |"
        )
    lines.extend(
        [
            "",
            "## Task Rows",
            "",
            "| set_id | task_id | family | candidate_complete | baseline_pass | candidate_pass | delta_pr_auc | delta_ef1 | residual_status | residual_positive_delta_count | residual_mean_delta |",
            "| --- | --- | --- | --- | --- | --- | ---: | ---: | --- | ---: | ---: |",
        ]
    )
    for row in payload["task_rows"]:
        lines.append(
            f"| {row['set_id']} | {row['task_id']} | {row['family']} | {row['candidate_complete']} | {row['baseline_pass']} | {row['candidate_pass']} | {row['delta_pr_auc']} | {row['delta_ef1']} | {row['residual_status']} | {row['residual_positive_delta_count']} | {row['residual_mean_delta']} |"
        )
    lines.extend(["", "## Live Process Check", ""])
    if payload["live_processes"]:
        lines.append("```text")
        lines.extend(payload["live_processes"])
        lines.append("```")
    else:
        lines.append("- no live processes matched the candidate run tag")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build a partial-safe baseline-vs-shadow comparison for the cross-family locked-decoy ion/kinase run.")
    p.add_argument("--scaffold-json", default=DEFAULT_SCAFFOLD_JSON)
    p.add_argument("--baseline-run-root", default="")
    p.add_argument("--candidate-run-root", default="")
    p.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    p.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    p.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    scaffold_json = _resolve(args.scaffold_json)
    baseline_run_root = _resolve(args.baseline_run_root) if str(args.baseline_run_root).strip() else None
    candidate_run_root = _resolve(args.candidate_run_root) if str(args.candidate_run_root).strip() else None
    payload = build_payload(
        scaffold_json=scaffold_json,
        baseline_run_root=baseline_run_root,
        candidate_run_root=candidate_run_root,
    )
    _write_json(_resolve(args.out_json), payload)
    _write_csv(_resolve(args.out_csv), payload["task_rows"])
    _write_markdown(_resolve(args.out_md), payload)


if __name__ == "__main__":
    main()
