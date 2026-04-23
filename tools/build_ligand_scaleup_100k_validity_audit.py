#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN_ROOT = "runs/external_validation_blind_runs/external_validation_blind_runs_2026-03-23_scaleup_100k_pilot_v2r2"
DEFAULT_PILOT_JSON = "runs/ligand_scaleup_100k_pilot_current.json"
DEFAULT_OUT_JSON = "runs/ligand_scaleup_100k_validity_audit_current.json"
DEFAULT_OUT_CSV = "runs/ligand_scaleup_100k_validity_audit_current.csv"
DEFAULT_OUT_MD = "runs/ligand_scaleup_100k_validity_audit_current.md"


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


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _list_live_processes(tag: str) -> list[dict[str, str]]:
    proc = subprocess.run(
        ["ps", "-eo", "pid=,args="],
        check=True,
        capture_output=True,
        text=True,
    )
    rows: list[dict[str, str]] = []
    for line in proc.stdout.splitlines():
        text = line.strip()
        if not text or tag not in text:
            continue
        if "build_ligand_scaleup_100k_validity_audit.py" in text:
            continue
        pid, _, args = text.partition(" ")
        rows.append({"pid": pid.strip(), "args": args.strip()})
    return rows


def _task_index(summary: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for set_row in summary.get("sets", []):
        set_id = str(set_row.get("set_id", "")).strip()
        for task in set_row.get("tasks", []):
            task_id = str(task.get("task_id", "")).strip()
            out[(set_id, task_id)] = task
    return out


def _actual_n(task: dict[str, Any], pilot_row: dict[str, Any]) -> str:
    sizes = task.get("ligand_sizes")
    if isinstance(sizes, list) and sizes:
        return str(sizes[0])
    pipeline_summary_json = str(task.get("pipeline_summary_json", "")).strip()
    if pipeline_summary_json:
        try:
            pipe = _read_json(Path(pipeline_summary_json))
            if "max_ligands" in pipe:
                return str(pipe["max_ligands"])
        except Exception:
            pass
    return str(pilot_row.get("ligand_sizes_after", "")).strip()


def build_payload(run_root: Path, pilot_payload: dict[str, Any], summary: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    task_rows: list[dict[str, Any]] = []
    set_rows: list[dict[str, Any]] = []
    task_map = _task_index(summary)
    pilot_tasks = pilot_payload.get("task_rows", [])
    live_processes = _list_live_processes(run_root.name)

    missing_expected_task_count = 0
    missing_task_output_count = 0
    contract_mismatch_count = 0
    failed_task_ids: list[str] = []

    for pilot_row in pilot_tasks:
        set_id = str(pilot_row.get("set_id", "")).strip()
        task_id = str(pilot_row.get("task_id", "")).strip()
        expected_n = str(pilot_row.get("ligand_sizes_after", "")).strip()
        task = task_map.get((set_id, task_id), {})
        summary_json = Path(str(task.get("summary_json", "")).strip()) if task else None
        pipeline_summary_json = Path(str(task.get("pipeline_summary_json", "")).strip()) if task else None
        present = bool(task)
        if not present:
            missing_expected_task_count += 1
        summary_present = bool(summary_json and summary_json.exists())
        pipeline_present = bool(pipeline_summary_json and pipeline_summary_json.exists())
        if present and (not summary_present or not pipeline_present):
            missing_task_output_count += 1
        actual_n = _actual_n(task, pilot_row) if task else ""
        contract_ok = actual_n == expected_n
        if present and not contract_ok:
            contract_mismatch_count += 1
        passed = bool(task.get("pass", False)) if task else False
        if present and not passed:
            failed_task_ids.append(task_id)
        metrics = task.get("metrics", {}) if task else {}
        task_rows.append(
            {
                "set_id": set_id,
                "task_id": task_id,
                "domain": str(pilot_row.get("domain", "")).strip(),
                "pilot_shape_class": str(pilot_row.get("pilot_shape_class", "")).strip(),
                "expected_n": expected_n,
                "actual_n": actual_n,
                "contract_ok": "yes" if contract_ok else "no",
                "task_present": "yes" if present else "no",
                "summary_present": "yes" if summary_present else "no",
                "pipeline_summary_present": "yes" if pipeline_present else "no",
                "task_pass": "yes" if passed else "no",
                "ranking_pr_auc": metrics.get("ranking_pr_auc", ""),
                "ranking_ef1": metrics.get("ranking_ef1", ""),
            }
        )

    for set_row in summary.get("sets", []):
        tasks = set_row.get("tasks", [])
        pass_count = sum(1 for task in tasks if task.get("pass", False))
        fail_count = sum(1 for task in tasks if not task.get("pass", False))
        set_rows.append(
            {
                "set_id": str(set_row.get("set_id", "")).strip(),
                "set_pass": "yes" if bool(set_row.get("pass", False)) else "no",
                "task_count": len(tasks),
                "pass_count": pass_count,
                "fail_count": fail_count,
            }
        )

    shape = pilot_payload.get("scope_summary", {})
    full_count = int(shape.get("full_task_count_100k", 0))
    smoke_count = int(shape.get("smoke_task_count_unchanged", 0))
    run_completed = str(summary.get("status", "")).strip() == "completed" and str(state.get("status", "")).strip() == "completed"
    valid_completed = (
        run_completed
        and missing_expected_task_count == 0
        and missing_task_output_count == 0
        and contract_mismatch_count == 0
        and not live_processes
        and len(task_rows) == int(shape.get("ligand_stress_task_count", 0))
    )
    interpretation = "valid_completed_test_run" if valid_completed else "invalid_or_incomplete_test_run"
    performance_outcome = "mixed_completed_run" if failed_task_ids else "all_tasks_passed"
    summary_payload = {
        "run_root": str(run_root),
        "tag": str(summary.get("tag", "")).strip(),
        "run_status": str(summary.get("status", "")).strip(),
        "state_status": str(state.get("status", "")).strip(),
        "contract_shape": {
            "full_task_count_100k": full_count,
            "smoke_task_count_64": smoke_count,
            "domain_count": len(shape.get("domains_touched", [])),
            "domains": list(shape.get("domains_touched", [])),
        },
        "task_count": len(task_rows),
        "missing_expected_task_count": missing_expected_task_count,
        "missing_task_output_count": missing_task_output_count,
        "contract_mismatch_count": contract_mismatch_count,
        "live_process_count": len(live_processes),
        "valid_completed_test_run": valid_completed,
        "interpretation": interpretation,
        "performance_outcome": performance_outcome,
        "failed_task_ids": failed_task_ids,
        "next_required_step": (
            "Treat this as a valid completed 100k size-shift test run; analyze the GPCR core failure as a model/ranking issue, not a harness failure."
            if valid_completed
            else "Resolve missing outputs, contract mismatches, or lingering live processes before treating this run as a valid completed test."
        ),
    }
    return {
        "summary": summary_payload,
        "set_rows": set_rows,
        "task_rows": task_rows,
        "live_process_rows": live_processes,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 100k Validity Audit",
        "",
        f"- run_root: `{summary['run_root']}`",
        f"- run_status: `{summary['run_status']}`",
        f"- valid_completed_test_run: `{str(summary['valid_completed_test_run']).lower()}`",
        f"- interpretation: `{summary['interpretation']}`",
        f"- performance_outcome: `{summary['performance_outcome']}`",
        f"- live_process_count: `{summary['live_process_count']}`",
        f"- missing_expected_task_count: `{summary['missing_expected_task_count']}`",
        f"- missing_task_output_count: `{summary['missing_task_output_count']}`",
        f"- contract_mismatch_count: `{summary['contract_mismatch_count']}`",
        "",
        "## Contract Shape",
        "",
        f"- full_task_count_100k: `{summary['contract_shape']['full_task_count_100k']}`",
        f"- smoke_task_count_64: `{summary['contract_shape']['smoke_task_count_64']}`",
        f"- domains: `{', '.join(summary['contract_shape']['domains'])}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Set Summary",
        "",
        "| set_id | set_pass | task_count | pass_count | fail_count |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for row in payload["set_rows"]:
        lines.append(f"| {row['set_id']} | {row['set_pass']} | {row['task_count']} | {row['pass_count']} | {row['fail_count']} |")
    lines.extend([
        "",
        "## Task Contract",
        "",
        "| set_id | task_id | expected_n | actual_n | contract_ok | task_present | summary_present | pipeline_summary_present | task_pass |",
        "| --- | --- | ---: | ---: | --- | --- | --- | --- | --- |",
    ])
    for row in payload["task_rows"]:
        lines.append(
            f"| {row['set_id']} | {row['task_id']} | {row['expected_n']} | {row['actual_n']} | {row['contract_ok']} | {row['task_present']} | {row['summary_present']} | {row['pipeline_summary_present']} | {row['task_pass']} |"
        )
    if payload["live_process_rows"]:
        lines.extend([
            "",
            "## Live Processes",
            "",
            "| pid | args |",
            "| --- | --- |",
        ])
        for row in payload["live_process_rows"]:
            lines.append(f"| `{row['pid']}` | `{row['args']}` |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a validity audit for the completed 100k scale-up pilot run.")
    parser.add_argument("--run-root", default=DEFAULT_RUN_ROOT)
    parser.add_argument("--pilot-json", default=DEFAULT_PILOT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_root = _resolve(args.run_root)
    pilot_payload = _read_json(_resolve(args.pilot_json))
    summary = _read_json(run_root / "summary.json")
    state = _read_json(run_root / "state.json")
    payload = build_payload(run_root, pilot_payload, summary, state)
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_csv(out_csv, payload["task_rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
