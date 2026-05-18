#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_RUN_ROOT = "runs/external_validation_blind_runs/external_validation_blind_runs_2026-03-23_scaleup_100k_pilot_v2r2"
DEFAULT_PILOT_SPEC_JSON = "config/external_validation_biorxiv_scaleup_100k_pilot_v1.json"
DEFAULT_PILOT_BUILD_JSON = "runs/ligand_scaleup_100k_pilot_current.json"
DEFAULT_OUT_JSON = "runs/ligand_scaleup_100k_test_audit_current.json"
DEFAULT_OUT_CSV = "runs/ligand_scaleup_100k_test_audit_current.csv"
DEFAULT_OUT_MD = "runs/ligand_scaleup_100k_test_audit_current.md"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _copied_file_path(task: dict[str, Any], original_path: str) -> Path | None:
    if not original_path:
        return None
    original_name = Path(original_path).name
    for copied in task.get("copied_files", []) or []:
        src = str(copied.get("src", "")).strip()
        dst = str(copied.get("dst", "")).strip()
        if not dst:
            continue
        if src == original_path or Path(src).name == original_name or Path(dst).name == original_name:
            candidate = Path(dst)
            if candidate.exists():
                return candidate
    return None


def _task_artifact_path(task: dict[str, Any], field: str) -> Path | None:
    raw_path = str(task.get(field, "")).strip()
    if not raw_path:
        return None
    resolved = _resolve(raw_path)
    if resolved.exists():
        return resolved
    return _copied_file_path(task, raw_path)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _flatten_task_index(run_summary: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    task_index: dict[str, dict[str, Any]] = {}
    outside_contract_candidates: list[str] = []
    for set_row in run_summary.get("sets", []):
        for task in set_row.get("tasks", []):
            task_id = str(task.get("task_id", "")).strip()
            if not task_id:
                continue
            task_index[task_id] = task
            outside_contract_candidates.append(task_id)
    return task_index, outside_contract_candidates


def _task_summary_metrics(task_summary: dict[str, Any]) -> dict[str, Any]:
    run0 = {}
    runs = task_summary.get("runs") or []
    if runs:
        run0 = runs[0]
    return {
        "raw_pass": bool(task_summary.get("pass")),
        "ranking_pr_auc": run0.get("ranking_pr_auc"),
        "ranking_ef1": run0.get("ranking_ef1"),
        "topk_hit_rate": run0.get("topk_hit_rate"),
        "strict_gate_pass": run0.get("strict_gate_pass"),
        "operational_gate_pass": run0.get("operational_gate_pass"),
        "ligand_size": run0.get("ligand_size"),
        "traj_prod_enabled": bool(task_summary.get("traj_prod", {}).get("enabled", False)),
    }


def _live_process_lines(tag: str) -> list[str]:
    completed = subprocess.run(["pgrep", "-af", tag], capture_output=True, text=True, check=False)
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    return lines


def _pipeline_prefix_from_summary_path(path: Path) -> Path:
    text = str(path)
    return Path(re.sub(r"_p\d+_n\d+_r\d+_summary\.json$", "", text))


def _cmd_value(cmd: list[Any], flag: str) -> str:
    for idx, item in enumerate(cmd):
        if str(item) == flag and idx + 1 < len(cmd):
            return str(cmd[idx + 1])
    return ""


def _infer_hard_decoys_from_task_summary(task_summary: dict[str, Any]) -> tuple[int | None, int | None, str]:
    pre_stage = dict(task_summary.get("pre_stage_hard_decoy", {}) or {})
    cmd = list(pre_stage.get("cmd", []) or [])
    try:
        returncode = int(pre_stage.get("returncode", 1))
    except (TypeError, ValueError):
        returncode = 1
    if not (pre_stage.get("ok") is True and returncode == 0):
        return None, None, ""
    if "--synthesize-unique-decoys" not in [str(item) for item in cmd]:
        return None, None, ""
    requested_raw = _cmd_value(cmd, "--synth-total-decoys")
    if not requested_raw:
        return None, None, ""
    try:
        requested = int(requested_raw)
    except ValueError:
        return None, None, ""
    allow_shortfall = "--no-synth-allow-shortfall" not in [str(item) for item in cmd]
    generated = requested if not allow_shortfall else None
    return requested, generated, "task_summary_pre_stage_hard_decoy_command"


def build_payload(run_root: Path, pilot_spec: dict[str, Any], pilot_build: dict[str, Any], run_summary: dict[str, Any], run_state: dict[str, Any]) -> dict[str, Any]:
    contract_tasks = set(pilot_build.get("full_task_ids_100k", [])) | set(pilot_build.get("smoke_task_ids_baseline", []))
    expected_sizes = dict(pilot_build.get("pilot_ligand_sizes", {}))
    task_index, wrapper_task_ids = _flatten_task_index(run_summary)
    wrapper_task_ids_set = set(wrapper_task_ids)
    contract_rows: list[dict[str, Any]] = []

    for set_row in pilot_spec.get("sets", []):
        set_id = str(set_row.get("set_id", "")).strip()
        for task_cfg in set_row.get("tasks", []):
            task_id = str(task_cfg.get("task_id", "")).strip()
            if task_id not in contract_tasks:
                continue
            task = task_index.get(task_id, {})
            task_summary_path = _task_artifact_path(task, "summary_json") if task else None
            task_summary_exists = bool(task_summary_path and task_summary_path.exists())
            task_summary = _load_json(task_summary_path) if task_summary_exists else {}
            task_metrics = _task_summary_metrics(task_summary) if task_summary else {}
            pipeline_summary_path = _task_artifact_path(task, "pipeline_summary_json") if task else None
            pipeline_summary_exists = bool(pipeline_summary_path and pipeline_summary_path.exists())
            state_path = _task_artifact_path(task, "state_json") if task else None
            state_exists = bool(state_path and state_path.exists())

            expected_key = f"{set_id}::{task_id}"
            expected_size = str(expected_sizes.get(expected_key, "")).strip()
            observed_sizes = [str(v) for v in (task.get("ligand_sizes") or [])]
            size_matches = expected_size in observed_sizes if expected_size else False

            hard_decoy_summary_path = None
            hard_decoy_exists = False
            hard_decoys_requested = None
            hard_decoys_generated = None
            hard_decoy_evidence_source = ""
            if pipeline_summary_exists and expected_size == "100000":
                prefix = _pipeline_prefix_from_summary_path(pipeline_summary_path)
                candidate = Path(str(prefix) + "_hard_decoy_summary.json")
                if candidate.exists():
                    hard_decoy_summary_path = candidate
                    hard_decoy_exists = True
                    hard_summary = _load_json(candidate)
                    synth = hard_summary.get("synthetic_decoys", {})
                    hard_decoys_requested = synth.get("requested")
                    hard_decoys_generated = synth.get("generated")
                    hard_decoy_evidence_source = "hard_decoy_summary_json"
                else:
                    hard_decoys_requested, hard_decoys_generated, hard_decoy_evidence_source = (
                        _infer_hard_decoys_from_task_summary(task_summary)
                    )

            row = {
                "set_id": set_id,
                "task_id": task_id,
                "domain": str(task.get("domain", task_cfg.get("domain", ""))).strip(),
                "expected_ligand_size": expected_size,
                "observed_ligand_sizes": ",".join(observed_sizes),
                "size_matches": "yes" if size_matches else "no",
                "task_present_in_run_summary": "yes" if task else "no",
                "task_summary_exists": "yes" if task_summary_exists else "no",
                "pipeline_summary_exists": "yes" if pipeline_summary_exists else "no",
                "state_json_exists": "yes" if state_exists else "no",
                "hard_decoy_summary_exists": "yes" if hard_decoy_exists else "no",
                "hard_decoy_evidence_source": hard_decoy_evidence_source,
                "hard_decoys_requested": hard_decoys_requested if hard_decoys_requested is not None else "",
                "hard_decoys_generated": hard_decoys_generated if hard_decoys_generated is not None else "",
                "traj_prod_enabled": "yes" if task_metrics.get("traj_prod_enabled") else "no",
                "task_pass": "yes" if bool(task.get("pass")) else "no",
                "task_raw_pass": "yes" if task_metrics.get("raw_pass") else "no",
                "ranking_pr_auc": task_metrics.get("ranking_pr_auc", ""),
                "ranking_ef1": task_metrics.get("ranking_ef1", ""),
                "topk_hit_rate": task_metrics.get("topk_hit_rate", ""),
                "strict_gate_pass": task_metrics.get("strict_gate_pass", ""),
                "operational_gate_pass": task_metrics.get("operational_gate_pass", ""),
                "contract_artifacts_complete": "yes" if all([
                    task,
                    task_summary_exists,
                    pipeline_summary_exists,
                    size_matches,
                    (hard_decoys_requested == 100000 and hard_decoys_generated == 100000) if expected_size == "100000" else True,
                ]) else "no",
            }
            contract_rows.append(row)

    outside_contract = sorted(wrapper_task_ids_set - contract_tasks)
    live_process_lines = _live_process_lines(run_root.name)

    contract_complete = all(row["contract_artifacts_complete"] == "yes" for row in contract_rows)
    full_rows = [row for row in contract_rows if row["expected_ligand_size"] == "100000"]
    smoke_rows = [row for row in contract_rows if row["expected_ligand_size"] == "64"]
    contract_pass_count = sum(1 for row in contract_rows if row["task_pass"] == "yes")
    contract_fail_count = sum(1 for row in contract_rows if row["task_pass"] != "yes")
    interpretation = (
        "valid_completed_test_run_with_mixed_outcome"
        if contract_complete and contract_fail_count > 0
        else "valid_completed_test_run_all_contract_tasks_passed"
        if contract_complete
        else "invalid_or_incomplete_test_run"
    )

    summary = {
        "run_tag": run_root.name,
        "run_status": run_summary.get("status", ""),
        "state_status": run_state.get("status", ""),
        "run_completed": run_summary.get("status") == "completed" and run_state.get("status") == "completed",
        "contract_task_count": len(contract_rows),
        "full_task_count_100k": len(full_rows),
        "smoke_task_count_64": len(smoke_rows),
        "contract_tasks_found_count": sum(1 for row in contract_rows if row["task_present_in_run_summary"] == "yes"),
        "contract_pass_count": contract_pass_count,
        "contract_fail_count": contract_fail_count,
        "full_task_size_match_count": sum(1 for row in full_rows if row["size_matches"] == "yes"),
        "full_task_hard_decoy_100k_count": sum(1 for row in full_rows if row["hard_decoys_requested"] == 100000 and row["hard_decoys_generated"] == 100000),
        "full_task_traj_prod_enabled_count": sum(1 for row in full_rows if row["traj_prod_enabled"] == "yes"),
        "live_process_count": len(live_process_lines),
        "outside_contract_task_count": len(outside_contract),
        "outside_contract_tasks": outside_contract,
        "valid_completed_test_run": bool(
            run_summary.get("status") == "completed"
            and run_state.get("status") == "completed"
            and len(live_process_lines) == 0
            and contract_complete
        ),
        "interpretation": interpretation,
        "next_required_step": (
            "Treat this as a valid completed 100k regression run. Investigate contract task failures separately from execution validity."
            if contract_complete else
            "Repair missing contract artifacts or size mismatches before treating this run as a valid completed 100k test."
        ),
    }
    return {
        "summary": summary,
        "contract_rows": contract_rows,
        "live_process_lines": live_process_lines,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Ligand Scale-Up 100k Test Audit",
        "",
        f"- run_tag: `{summary['run_tag']}`",
        f"- run_status: `{summary['run_status']}`",
        f"- state_status: `{summary['state_status']}`",
        f"- valid_completed_test_run: `{summary['valid_completed_test_run']}`",
        f"- interpretation: `{summary['interpretation']}`",
        f"- contract_task_count: `{summary['contract_task_count']}`",
        f"- contract_pass_count: `{summary['contract_pass_count']}`",
        f"- contract_fail_count: `{summary['contract_fail_count']}`",
        f"- full_task_hard_decoy_100k_count: `{summary['full_task_hard_decoy_100k_count']}`",
        f"- full_task_traj_prod_enabled_count: `{summary['full_task_traj_prod_enabled_count']}`",
        f"- live_process_count: `{summary['live_process_count']}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Contract Rows",
        "",
        "| set_id | task_id | expected_ligand_size | observed_ligand_sizes | size_matches | hard_decoys_generated | hard_decoy_evidence_source | traj_prod_enabled | task_pass | contract_artifacts_complete |",
        "| --- | --- | ---: | --- | --- | ---: | --- | --- | --- | --- |",
    ]
    for row in payload["contract_rows"]:
        lines.append(
            f"| {row['set_id']} | {row['task_id']} | {row['expected_ligand_size']} | `{row['observed_ligand_sizes']}` | {row['size_matches']} | {row['hard_decoys_generated']} | `{row.get('hard_decoy_evidence_source', '') or '-'}` | {row['traj_prod_enabled']} | {row['task_pass']} | {row['contract_artifacts_complete']} |"
        )
    lines.extend(["", "## Live Process Check", ""])
    if payload["live_process_lines"]:
        lines.append("```text")
        lines.extend(payload["live_process_lines"])
        lines.append("```")
    else:
        lines.append("- no live processes matched the run tag")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit whether the 100k scale-up pilot completed as a valid test run, distinct from whether all tasks passed.")
    parser.add_argument("--run-root", default=DEFAULT_RUN_ROOT)
    parser.add_argument("--pilot-spec-json", default=DEFAULT_PILOT_SPEC_JSON)
    parser.add_argument("--pilot-build-json", default=DEFAULT_PILOT_BUILD_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_root = _resolve(args.run_root)
    run_summary = _load_json(run_root / "summary.json")
    run_state = _load_json(run_root / "state.json")
    pilot_spec = _load_json(_resolve(args.pilot_spec_json))
    pilot_build = _load_json(_resolve(args.pilot_build_json))
    payload = build_payload(run_root, pilot_spec, pilot_build, run_summary, run_state)
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_csv(out_csv, payload["contract_rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
