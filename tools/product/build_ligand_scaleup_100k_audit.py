#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RUN_GLOB = "external_validation_blind_runs/external_validation_blind_runs_*scaleup_100k_pilot*"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


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


def _discover_latest_run_root() -> Path:
    candidates = []
    base = ROOT / "runs"
    for path in sorted(base.glob(RUN_GLOB)):
        summary_json = path / "summary.json"
        state_json = path / "state.json"
        ref = summary_json if summary_json.exists() else state_json
        if not ref.exists():
            continue
        candidates.append((ref.stat().st_mtime, path))
    if not candidates:
        raise FileNotFoundError("No completed 100k scale-up pilot run root could be discovered under runs/.")
    return max(candidates, key=lambda item: item[0])[1]


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
        if "build_ligand_scaleup_100k_audit.py" in line:
            continue
        rows.append(line)
    return rows


def _task_rows_from_run_summary(run_summary: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for set_row in run_summary.get("sets", []):
        set_id = str(set_row.get("set_id", "")).strip()
        for task in set_row.get("tasks", []):
            if str(task.get("kind", "")).strip() != "ligand_stress":
                continue
            rows.append(
                {
                    "set_id": set_id,
                    "task_id": str(task.get("task_id", "")).strip(),
                    "domain": str(task.get("domain", "")).strip(),
                    "pass": bool(task.get("pass")),
                    "summary_json": str(task.get("summary_json", "")).strip(),
                    "pipeline_summary_json": str(task.get("pipeline_summary_json", "")).strip(),
                    "profile_json": str(task.get("profile_json", "")).strip(),
                    "ligand_sizes": ",".join(str(x) for x in task.get("ligand_sizes", []) if str(x).strip()),
                    "metrics": task.get("metrics") if isinstance(task.get("metrics"), dict) else {},
                }
            )
    return rows


def _task_audit_rows(task_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    audited: list[dict[str, Any]] = []
    for row in task_rows:
        summary_path = _resolve(row["summary_json"]) if row["summary_json"] else None
        pipeline_summary_path = _resolve(row["pipeline_summary_json"]) if row["pipeline_summary_json"] else None
        ranking_pr_auc = row["metrics"].get("ranking_pr_auc", "")
        ranking_ef1 = row["metrics"].get("ranking_ef1", "")
        strict_gate_pass = row["metrics"].get("strict_gate_pass", "")
        operational_gate_pass = row["metrics"].get("operational_gate_pass", "")
        audited.append(
            {
                "set_id": row["set_id"],
                "task_id": row["task_id"],
                "domain": row["domain"],
                "ligand_sizes": row["ligand_sizes"],
                "task_pass": "yes" if row["pass"] else "no",
                "summary_json_present": "yes" if summary_path and summary_path.exists() else "no",
                "pipeline_summary_present": "yes" if pipeline_summary_path and pipeline_summary_path.exists() else "no",
                "ranking_pr_auc": ranking_pr_auc,
                "ranking_ef1": ranking_ef1,
                "strict_gate_pass": strict_gate_pass,
                "operational_gate_pass": operational_gate_pass,
            }
        )
    return audited


def build_payload(run_root: Path, pilot_payload: dict[str, Any], run_summary: dict[str, Any]) -> dict[str, Any]:
    task_rows = _task_rows_from_run_summary(run_summary)
    audited_rows = _task_audit_rows(task_rows)
    proc_lines = _proc_lines(run_root.name)
    expected_task_count = int(pilot_payload.get("scope_summary", {}).get("ligand_stress_task_count", 0))
    expected_full_count = int(pilot_payload.get("scope_summary", {}).get("full_task_count_100k", 0))
    expected_smoke_count = int(pilot_payload.get("scope_summary", {}).get("smoke_task_count_unchanged", 0))
    set_rows = list(run_summary.get("sets", []))
    set_pass_count = sum(1 for row in set_rows if bool(row.get("pass")))
    set_fail_count = sum(1 for row in set_rows if not bool(row.get("pass")))
    summary_present_count = sum(1 for row in audited_rows if row["summary_json_present"] == "yes")
    pipeline_present_count = sum(1 for row in audited_rows if row["pipeline_summary_present"] == "yes")
    contract_shape = {
        "expected_task_count": expected_task_count,
        "observed_task_count": len(audited_rows),
        "expected_full_task_count_100k": expected_full_count,
        "observed_full_task_count_100k": sum(1 for row in audited_rows if row["ligand_sizes"] == "100000"),
        "expected_smoke_task_count_64": expected_smoke_count,
        "observed_smoke_task_count_64": sum(1 for row in audited_rows if row["ligand_sizes"] == "64"),
        "drift_audit_ok": bool(pilot_payload.get("drift_audit", {}).get("ok")),
        "launch_readiness_ready": bool(pilot_payload.get("launch_readiness", {}).get("ready")),
    }
    contract_shape_ok = (
        contract_shape["expected_task_count"] == contract_shape["observed_task_count"]
        and contract_shape["expected_full_task_count_100k"] == contract_shape["observed_full_task_count_100k"]
        and contract_shape["expected_smoke_task_count_64"] == contract_shape["observed_smoke_task_count_64"]
        and contract_shape["drift_audit_ok"]
        and contract_shape["launch_readiness_ready"]
    )
    expected_outputs = {
        "run_summary_present": (run_root / "summary.json").exists(),
        "run_state_present": (run_root / "state.json").exists(),
        "all_task_summary_json_present": summary_present_count == len(audited_rows),
        "all_task_pipeline_summary_present": pipeline_present_count == len(audited_rows),
    }
    expected_outputs_ok = all(expected_outputs.values())
    run_status = str(run_summary.get("status", "")).strip().lower()
    live_process_count = len(proc_lines)
    valid_completed_test_run = bool(
        run_status == "completed"
        and contract_shape_ok
        and expected_outputs_ok
        and live_process_count == 0
    )
    failed_tasks = [row["task_id"] for row in audited_rows if row["task_pass"] == "no"]
    if valid_completed_test_run:
        result_interpretation = "valid_completed_run_mixed_outcome" if failed_tasks else "valid_completed_run_all_pass"
    else:
        result_interpretation = "invalid_or_incomplete_run"
    summary = {
        "run_root": str(run_root.resolve()),
        "run_tag": run_root.name.replace("external_validation_blind_runs_", ""),
        "run_status": run_status,
        "valid_completed_test_run": valid_completed_test_run,
        "result_interpretation": result_interpretation,
        "live_process_count": live_process_count,
        "live_processes": proc_lines,
        "set_count": len(set_rows),
        "set_pass_count": set_pass_count,
        "set_fail_count": set_fail_count,
        "task_count": len(audited_rows),
        "task_pass_count": sum(1 for row in audited_rows if row["task_pass"] == "yes"),
        "task_fail_count": len(failed_tasks),
        "failed_task_ids": failed_tasks,
        "contract_shape_ok": contract_shape_ok,
        "expected_outputs_ok": expected_outputs_ok,
        "next_required_step": (
            "Treat this as a valid completed 100k test run. Use failed tasks for quality analysis, not as evidence of run corruption."
            if valid_completed_test_run
            else "Do not interpret scientific outcomes yet; first fix completion or output-integrity issues."
        ),
    }
    return {
        "summary": summary,
        "contract_shape": contract_shape,
        "expected_outputs": expected_outputs,
        "task_rows": audited_rows,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    contract = payload["contract_shape"]
    outputs = payload["expected_outputs"]
    lines = [
        "# 100k Pilot Audit",
        "",
        f"- run_tag: `{summary['run_tag']}`",
        f"- run_status: `{summary['run_status']}`",
        f"- valid_completed_test_run: `{str(summary['valid_completed_test_run']).lower()}`",
        f"- result_interpretation: `{summary['result_interpretation']}`",
        f"- live_process_count: `{summary['live_process_count']}`",
        f"- set_pass_count: `{summary['set_pass_count']}` / `{summary['set_count']}`",
        f"- task_pass_count: `{summary['task_pass_count']}` / `{summary['task_count']}`",
        "",
        "## Contract Shape",
        "",
        f"- expected_task_count: `{contract['expected_task_count']}`",
        f"- observed_task_count: `{contract['observed_task_count']}`",
        f"- expected_full_task_count_100k: `{contract['expected_full_task_count_100k']}`",
        f"- observed_full_task_count_100k: `{contract['observed_full_task_count_100k']}`",
        f"- expected_smoke_task_count_64: `{contract['expected_smoke_task_count_64']}`",
        f"- observed_smoke_task_count_64: `{contract['observed_smoke_task_count_64']}`",
        f"- drift_audit_ok: `{str(contract['drift_audit_ok']).lower()}`",
        f"- launch_readiness_ready: `{str(contract['launch_readiness_ready']).lower()}`",
        f"- contract_shape_ok: `{str(summary['contract_shape_ok']).lower()}`",
        "",
        "## Expected Outputs",
        "",
        f"- run_summary_present: `{str(outputs['run_summary_present']).lower()}`",
        f"- run_state_present: `{str(outputs['run_state_present']).lower()}`",
        f"- all_task_summary_json_present: `{str(outputs['all_task_summary_json_present']).lower()}`",
        f"- all_task_pipeline_summary_present: `{str(outputs['all_task_pipeline_summary_present']).lower()}`",
        f"- expected_outputs_ok: `{str(summary['expected_outputs_ok']).lower()}`",
        "",
        "## Task Outcomes",
        "",
        "| set_id | task_id | domain | n | task_pass | PR-AUC | EF1 | strict_gate_pass | operational_gate_pass |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["task_rows"]:
        lines.append(
            f"| {row['set_id']} | `{row['task_id']}` | {row['domain']} | {row['ligand_sizes']} | {row['task_pass']} | {row['ranking_pr_auc']} | {row['ranking_ef1']} | {row['strict_gate_pass']} | {row['operational_gate_pass']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            f"- {summary['next_required_step']}",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an audit report stating whether the current 100k pilot is a valid completed test run.")
    parser.add_argument("--run-root", default="")
    parser.add_argument("--pilot-json", default="runs/ligand_scaleup_100k_pilot_current.json")
    parser.add_argument("--out-json", default="runs/ligand_scaleup_100k_audit_current.json")
    parser.add_argument("--out-csv", default="runs/ligand_scaleup_100k_audit_current.csv")
    parser.add_argument("--out-md", default="runs/ligand_scaleup_100k_audit_current.md")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_root = _resolve(args.run_root) if str(args.run_root).strip() else _discover_latest_run_root()
    pilot_payload = _read_json(_resolve(args.pilot_json))
    run_summary = _read_json(run_root / "summary.json")
    payload = build_payload(run_root, pilot_payload, run_summary)
    _write_json(_resolve(args.out_json), payload)
    _write_csv(_resolve(args.out_csv), payload["task_rows"])
    _write_markdown(_resolve(args.out_md), payload)


if __name__ == "__main__":
    main()
