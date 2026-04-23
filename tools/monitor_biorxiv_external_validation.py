#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
GRAY = "\033[90m"


def _default_resume_cmd(run_root: Path) -> list[str]:
    return [
        "python3",
        str(ROOT / "tools/resume_biorxiv_external_validation.py"),
        "--run-root",
        str(run_root),
    ]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def _resolve_path(path_like: str | os.PathLike[str] | None) -> Path | None:
    if not path_like:
        return None
    path = Path(path_like)
    if path.is_absolute():
        return path.resolve()
    return (ROOT / path).resolve()


def _parse_dt(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return dt.datetime.fromisoformat(value)
    except Exception:
        return None


def _style(enabled: bool, text: str, *codes: str) -> str:
    if not enabled or not codes:
        return text
    return "".join(codes) + text + RESET


def _fmt_bool(v: Any) -> str:
    if v is True:
        return 'PASS'
    if v is False:
        return 'FAIL'
    return 'NA'


def _truncate(text: str, limit: int = 96) -> str:
    text = str(text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _failure_tag(reason: str) -> tuple[str, str]:
    text = str(reason).lower()
    if any(key in text for key in ["memory access fault", "page not present", "out of memory", "oom", "gpu"]):
        return "gpu", RED
    if any(key in text for key in ["heavy_artifacts_root", "mount", "permission denied", "no such file", "missing", "disk", "filesystem"]):
        return "infra", YELLOW
    if any(key in text for key in ["leakage_audit", "operational_gate", "strict_gate", "ranking", "integrity", "calibration"]):
        return "gate", MAGENTA
    if any(key in text for key in ["timeout", "timed out"]):
        return "timeout", YELLOW
    return "error", RED


def _proc_lines(tag: str) -> list[str]:
    if not tag.strip():
        return []
    try:
        out = subprocess.check_output(
            ["pgrep", "-af", tag],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        rows = []
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            if "pgrep -af" in line:
                continue
            if "monitor_biorxiv_external_validation.py" in line:
                continue
            rows.append(line)
        return rows
    except Exception:
        return []


def _status_color(status: str) -> str:
    return {
        "completed": GREEN,
        "running": CYAN,
        "stale": YELLOW,
        "failed": RED,
        "failed_validation_packaged": MAGENTA,
        "completed_unfinalized": BLUE,
    }.get(status, GRAY)


def _phase_color(phase: str) -> str:
    if phase in {"validation", "package_build", "partial_package_build"}:
        return BLUE
    if phase in {"done", "partial_package_built"}:
        return GREEN
    return GRAY


def _human_duration(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "unknown"
    sec = int(round(seconds))
    days, sec = divmod(sec, 86400)
    hours, sec = divmod(sec, 3600)
    mins, sec = divmod(sec, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if mins:
        parts.append(f"{mins}m")
    if sec or not parts:
        parts.append(f"{sec}s")
    return " ".join(parts[:3])


def _progress_bar(
    done: int,
    total: int,
    *,
    width: int = 28,
    active: bool = False,
    color: bool = False,
    bar_color: str = CYAN,
) -> str:
    if total <= 0:
        bar = "[" + ("." * width) + "]"
        return _style(color, bar, DIM)
    frac = max(0.0, min(1.0, done / total))
    filled = int(frac * width)
    cells = []
    for idx in range(width):
        if idx < filled:
            cells.append("█")
        elif active and idx == filled and filled < width:
            cells.append(">")
        else:
            cells.append("·")
    bar = "[" + "".join(cells) + "]"
    return _style(color, bar, bar_color)


def _extract_arg(cmdline: str, flag: str) -> str:
    parts = cmdline.split()
    for idx, part in enumerate(parts):
        if part == flag and idx + 1 < len(parts):
            return parts[idx + 1]
    return ""


def _short_profile_name(profile: str) -> str:
    if not profile:
        return ""
    name = Path(profile).name
    for prefix in ["ligand_htvs_", "real_drug_targets_", "config_"]:
        if name.startswith(prefix):
            name = name[len(prefix):]
    if name.endswith(".json"):
        name = name[:-5]
    return name


def _compact_context_label(value: str) -> str:
    if not value:
        return ""
    name = Path(value).name
    name = name.replace("_stage1_queue.csv", "")
    name = name.replace("_summary.json", "")
    name = name.replace(".csv", "")
    name = name.replace(".json", "")
    if len(name) > 72:
        return name[:69] + "..."
    return name


def _infer_ligand_stage_from_out_prefix(out_prefix: str) -> tuple[str, str]:
    if not out_prefix:
        return "", ""
    prefix = Path(out_prefix)
    checks = [
        ("_stage5_ranking_summary.json", "stage5 ranking"),
        ("_stage45_integrity_summary.json", "stage45 integrity"),
        ("_stage3_summary.json", "stage3 backmapping"),
        ("_stage2_traj_progress.json", "stage2 trajectory"),
        ("_stage2_traj_summary.json", "stage2 trajectory"),
        ("_stage2_summary.json", "stage2 active learning"),
        ("_stage1_summary.json", "stage1 queue build"),
        ("_stage0_leakage_summary.json", "stage0 leakage audit"),
    ]
    for suffix, label in checks:
        path = Path(str(prefix) + suffix)
        if path.exists():
            return label, path.name
    return "", ""


def _infer_context_from_cmdline(cmdline: str) -> str:
    for flag in ["--targets", "--holdouts", "--date-tag"]:
        value = _extract_arg(cmdline, flag)
        if value:
            return value
    profile = _extract_arg(cmdline, "--profile-json")
    if profile:
        return _short_profile_name(profile)
    out_prefix = _extract_arg(cmdline, "--out-prefix")
    if out_prefix:
        return _compact_context_label(out_prefix)
    queue_csv = _extract_arg(cmdline, "--queue-csv")
    if queue_csv:
        return _compact_context_label(queue_csv)
    return ""


def _preferred_global_context(proc_lines: list[str]) -> str:
    preferred_scripts = [
        "run_ligand_htvs_pipeline.py",
        "run_ligand_stress_validation.py",
        "run_idp_3bead_release_smoke_current.py",
        "generate_ligand_trajectory_engine.py",
    ]
    for script in preferred_scripts:
        for line in proc_lines:
            if script not in line:
                continue
            for flag in ["--targets", "--holdouts"]:
                value = _extract_arg(line, flag)
                if value:
                    return value
            value = _extract_arg(line, "--profile-json")
            if value:
                return _short_profile_name(value)
    for line in proc_lines:
        context = _infer_context_from_cmdline(line)
        if context:
            return context
    return ""


def _load_set_defs(run_root: Path, status: dict[str, Any] | None, top_state: dict[str, Any] | None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    spec_path = None
    if isinstance(status, dict):
        spec_path = _resolve_path(str(status.get("set_spec_json", "")).strip())
    if spec_path is None and isinstance(top_state, dict):
        spec_path = _resolve_path(str(top_state.get("set_spec_json", "")).strip())
    if spec_path is None:
        provenance_json = run_root / "provenance.json"
        if provenance_json.exists():
            provenance = _read_json(provenance_json)
            spec_path = _resolve_path(str(provenance.get("spec_json", "")).strip())
    if spec_path is None or not spec_path.exists():
        return [], {}
    spec = _read_json(spec_path)
    set_defs = spec.get("sets")
    if not isinstance(set_defs, list):
        return [], spec
    return set_defs, spec


def _load_selected_set_ids(status: dict[str, Any] | None, top_state: dict[str, Any] | None, spec: dict[str, Any]) -> list[str]:
    if isinstance(status, dict) and isinstance(status.get("sets"), list):
        return [str(x).strip() for x in status.get("sets", []) if str(x).strip()]
    if isinstance(top_state, dict) and isinstance(top_state.get("selected_sets"), list):
        return [str(x).strip() for x in top_state.get("selected_sets", []) if str(x).strip()]
    set_defs = spec.get("sets")
    if isinstance(set_defs, list):
        return [str(x.get("set_id", "")).strip() for x in set_defs if str(x.get("set_id", "")).strip()]
    return []


def _collect_progress(
    run_root: Path,
    set_defs: list[dict[str, Any]],
    selected_set_ids: list[str],
    effective_status: str,
) -> dict[str, Any]:
    set_map = {str(x.get("set_id", "")).strip(): x for x in set_defs}
    selected_defs = [set_map[sid] for sid in selected_set_ids if sid in set_map]
    total_sets = len(selected_defs)
    total_tasks = sum(len(x.get("tasks", [])) for x in selected_defs)
    completed_sets = 0
    completed_tasks = 0
    rows: list[dict[str, Any]] = []
    completed_history: list[dict[str, Any]] = []
    failed_history: list[dict[str, Any]] = []

    active_set_id = ""
    active_task: dict[str, Any] | None = None

    for set_def in selected_defs:
        set_id = str(set_def.get("set_id", "")).strip()
        tasks = set_def.get("tasks", []) if isinstance(set_def.get("tasks"), list) else []
        set_root = run_root / set_id
        manifest_json = set_root / "manifest.json"
        state_json = set_root / "state.json"
        row: dict[str, Any] = {
            "set_id": set_id,
            "title": str(set_def.get("title", "")).strip(),
            "task_total": len(tasks),
            "task_done": 0,
            "generated_at": None,
            "status": "pending",
            "pass": None,
            "fail_brief": "",
            "active_task_id": "",
            "active_task_domain": "",
            "active_task_kind": "",
            "failed_task": None,
        }
        if manifest_json.exists():
            manifest = _read_json(manifest_json)
            row["status"] = "complete"
            row["pass"] = manifest.get("pass")
            row["task_done"] = len(tasks)
            completed_sets += 1
            completed_tasks += len(tasks)
            manifest_tasks = manifest.get("tasks", []) if isinstance(manifest.get("tasks"), list) else []
            failed_results = [t for t in manifest_tasks if isinstance(t, dict) and t.get("pass") is False]
            if failed_results:
                first_failed = failed_results[0]
                reason = (
                    str(first_failed.get("service_failed_stage", "")).strip()
                    or str(first_failed.get("acceptance_note", "")).strip()
                    or "task failed"
                )
                row["fail_brief"] = _truncate(
                    f"{first_failed.get('task_id')} ({first_failed.get('domain')}): {reason}"
                )
            if state_json.exists():
                state = _read_json(state_json)
                row["generated_at"] = _parse_dt(state.get("generated_at_local"))
                task_state = state.get("tasks", {}) if isinstance(state.get("tasks"), dict) else {}
                for task_id, rec in task_state.items():
                    if not isinstance(rec, dict) or not rec.get("done"):
                        continue
                    updated = _parse_dt(rec.get("updated_at_local"))
                    if updated is None:
                        continue
                    result = rec.get("result", {}) if isinstance(rec.get("result"), dict) else {}
                    candidate = {
                        "updated_at": updated,
                        "set_id": set_id,
                        "task_id": str(task_id).strip(),
                        "domain": str(result.get("domain", "")).strip(),
                        "kind": str(result.get("kind", "")).strip(),
                        "pass": result.get("pass"),
                    }
                    completed_history.append(candidate)
                failed_task = state.get("failed_task") if isinstance(state.get("failed_task"), dict) else None
                if failed_task:
                    updated = _parse_dt(failed_task.get("updated_at_local"))
                    if updated is not None:
                        candidate_failed = {
                            "updated_at": updated,
                            "set_id": set_id,
                            "task_id": str(failed_task.get("task_id", "")).strip(),
                            "domain": str(failed_task.get("domain", "")).strip(),
                            "kind": str(failed_task.get("kind", "")).strip(),
                            "error": str(failed_task.get("error", "")).strip(),
                        }
                        failed_history.append(candidate_failed)
        elif state_json.exists():
            state = _read_json(state_json)
            row["generated_at"] = _parse_dt(state.get("generated_at_local"))
            task_state = state.get("tasks", {}) if isinstance(state.get("tasks"), dict) else {}
            done_ids = {
                str(task_id).strip()
                for task_id, rec in task_state.items()
                if isinstance(rec, dict) and rec.get("done")
            }
            row["task_done"] = sum(1 for task in tasks if str(task.get("task_id", "")).strip() in done_ids)
            completed_tasks += int(row["task_done"])
            row["failed_task"] = state.get("failed_task") if isinstance(state.get("failed_task"), dict) else None
            row["status"] = "failed" if row["failed_task"] else "partial"
            if isinstance(row["failed_task"], dict):
                fail_reason = str(row["failed_task"].get("error", "")).strip() or "task failed"
                row["fail_brief"] = _truncate(
                    f"{row['failed_task'].get('task_id')} ({row['failed_task'].get('domain')}): {fail_reason}"
                )
            for task_id, rec in task_state.items():
                if not isinstance(rec, dict) or not rec.get("done"):
                    continue
                updated = _parse_dt(rec.get("updated_at_local"))
                if updated is None:
                    continue
                result = rec.get("result", {}) if isinstance(rec.get("result"), dict) else {}
                candidate = {
                    "updated_at": updated,
                    "set_id": set_id,
                    "task_id": str(task_id).strip(),
                    "domain": str(result.get("domain", "")).strip(),
                    "kind": str(result.get("kind", "")).strip(),
                    "pass": result.get("pass"),
                }
                completed_history.append(candidate)
            if row["task_done"] == len(tasks):
                row["status"] = "complete"
                completed_sets += 1
            else:
                next_task = next(
                    (
                        task
                        for task in tasks
                        if str(task.get("task_id", "")).strip() not in done_ids
                    ),
                    None,
                )
                if next_task:
                    row["active_task_id"] = str(next_task.get("task_id", "")).strip()
                    row["active_task_domain"] = str(next_task.get("domain", "")).strip()
                    row["active_task_kind"] = str(next_task.get("kind", "")).strip()
                    if not active_set_id and effective_status == "running":
                        active_set_id = set_id
                        active_task = next_task
            failed_task = row["failed_task"] if isinstance(row["failed_task"], dict) else None
            if failed_task:
                updated = _parse_dt(failed_task.get("updated_at_local"))
                if updated is not None:
                    candidate_failed = {
                        "updated_at": updated,
                        "set_id": set_id,
                        "task_id": str(failed_task.get("task_id", "")).strip(),
                        "domain": str(failed_task.get("domain", "")).strip(),
                        "kind": str(failed_task.get("kind", "")).strip(),
                        "error": str(failed_task.get("error", "")).strip(),
                    }
                    failed_history.append(candidate_failed)
        else:
            if not active_set_id and effective_status == "running":
                next_task = tasks[0] if tasks else None
                if next_task:
                    row["active_task_id"] = str(next_task.get("task_id", "")).strip()
                    row["active_task_domain"] = str(next_task.get("domain", "")).strip()
                    row["active_task_kind"] = str(next_task.get("kind", "")).strip()
                    active_set_id = set_id
                    active_task = next_task
        rows.append(row)

    return {
        "total_sets": total_sets,
        "total_tasks": total_tasks,
        "completed_sets": completed_sets,
        "completed_tasks": completed_tasks,
        "rows": rows,
        "active_set_id": active_set_id,
        "active_task": active_task,
        "recent_completed": sorted(
            completed_history,
            key=lambda x: x["updated_at"],
            reverse=True,
        )[:3],
        "recent_failed": sorted(
            failed_history,
            key=lambda x: x["updated_at"],
            reverse=True,
        )[:3],
    }


def _infer_active_process(proc_lines: list[str]) -> dict[str, str]:
    candidates = [
        ("generate_ligand_trajectory_engine.py", "stage2 trajectory"),
        ("run_ligand_htvs_pipeline.py", "HTVS pipeline"),
        ("run_ligand_stress_validation.py", "stress orchestrator"),
        ("run_idp_3bead_release_smoke_current.py", "IDP smoke"),
        ("run_external_validation_blind_sets.py", "set orchestrator"),
        ("run_biorxiv_external_validation_current.py", "one-shot wrapper"),
        ("resume_biorxiv_external_validation.py", "resume wrapper"),
    ]
    global_context = _preferred_global_context(proc_lines)
    for script, label in candidates:
        for line in proc_lines:
            if script in line:
                context = _infer_context_from_cmdline(line) or global_context
                if script == "generate_ligand_trajectory_engine.py" and global_context:
                    context = global_context
                detail = ""
                detail_src = ""
                if script == "run_ligand_htvs_pipeline.py":
                    out_prefix = _extract_arg(line, "--out-prefix")
                    detail, detail_src = _infer_ligand_stage_from_out_prefix(out_prefix)
                elif script == "run_ligand_stress_validation.py":
                    profile = _extract_arg(line, "--profile-json")
                    if profile:
                        detail = "profile " + _short_profile_name(profile)
                elif script == "run_idp_3bead_release_smoke_current.py":
                    holdouts = _extract_arg(line, "--holdouts")
                    if holdouts:
                        detail = "holdouts " + holdouts
                return {
                    "label": label,
                    "script": script,
                    "context": context,
                    "cmdline": line,
                    "detail": detail,
                    "detail_src": detail_src,
                }
    return {"label": "", "script": "", "context": "", "cmdline": "", "detail": "", "detail_src": ""}


def _print_snapshot(run_root: Path, color: bool) -> None:
    print(_style(color, "BioRxiv External Validation Monitor", BOLD, CYAN))
    print(f"run_root: {run_root}")
    print(f"updated_at: {dt.datetime.now().isoformat(timespec='seconds')}")

    status_json = run_root / 'oneshot_status.json'
    tag = ""
    effective_status = "unknown"
    status: dict[str, Any] | None = None
    proc_lines: list[str] = []
    if status_json.exists():
        status = _read_json(status_json)
        tag = str(status.get('tag', '')).strip()
        proc_lines = _proc_lines(tag)
        effective_status = status.get('status')
        if effective_status == 'running' and not proc_lines:
            effective_status = 'stale'
        print(
            "status: "
            + _style(color, str(effective_status), BOLD, _status_color(str(effective_status)))
            + f"  phase: {_style(color, str(status.get('phase')), BOLD, _phase_color(str(status.get('phase'))))}  tag: {tag}"
        )
        if status.get("last_heartbeat_local"):
            print(f"last_heartbeat_local: {_style(color, str(status.get('last_heartbeat_local')), DIM)}")
        if status.get("child_pid"):
            print(f"child_pid: {status.get('child_pid')}")
        if status.get("validation_log"):
            print(f"validation_log: {_style(color, str(status.get('validation_log')), DIM)}")
        if status.get("package_log"):
            print(f"package_log: {_style(color, str(status.get('package_log')), DIM)}")
        if proc_lines:
            print(f"matching_processes: {_style(color, str(len(proc_lines)), BOLD, GREEN)}")
        if effective_status in {"stale", "failed", "failed_validation_packaged"}:
            resume_cmd = status.get("resume_cmd")
            if not (isinstance(resume_cmd, list) and resume_cmd):
                resume_cmd = _default_resume_cmd(run_root)
            print(_style(color, "resume_command:", BOLD, YELLOW))
            print("  " + _style(color, " ".join(str(x) for x in resume_cmd), YELLOW))
    else:
        print(_style(color, 'status: no oneshot_status.json', BOLD, RED))

    top_state = _read_json(run_root / "state.json") if (run_root / "state.json").exists() else None
    set_defs, spec = _load_set_defs(run_root, status, top_state)
    selected_set_ids = _load_selected_set_ids(status, top_state, spec)
    progress = _collect_progress(run_root, set_defs, selected_set_ids, str(effective_status))
    start_dt = None
    if isinstance(top_state, dict):
        start_dt = _parse_dt(top_state.get("generated_at_local"))
    if start_dt is None:
        provenance_json = run_root / "provenance.json"
        if provenance_json.exists():
            start_dt = _parse_dt(_read_json(provenance_json).get("generated_at_local"))
    now = dt.datetime.now(start_dt.tzinfo) if start_dt and start_dt.tzinfo else dt.datetime.now()
    elapsed_sec = (now - start_dt).total_seconds() if start_dt else None
    eta_sec = None
    total_tasks = int(progress["total_tasks"])
    completed_tasks = int(progress["completed_tasks"])
    active_task = progress.get("active_task")
    if elapsed_sec is not None and completed_tasks > 0 and total_tasks > completed_tasks:
        eta_sec = max(0.0, elapsed_sec / completed_tasks * (total_tasks - completed_tasks))
    avg_task_sec = (elapsed_sec / completed_tasks) if (elapsed_sec is not None and completed_tasks > 0) else None
    active_process = _infer_active_process(proc_lines)

    if total_tasks:
        overall_pct = 100.0 * completed_tasks / total_tasks
        sets_done = int(progress["completed_sets"])
        total_sets = int(progress["total_sets"])
        print()
        print(_style(color, "Overall Progress", BOLD, MAGENTA))
        print(
            f"tasks: {_progress_bar(completed_tasks, total_tasks, active=bool(active_task and str(effective_status) == 'running'), color=color, bar_color=CYAN)} "
            + _style(color, f"{completed_tasks}/{total_tasks}", BOLD, CYAN)
            + f"  ({overall_pct:.1f}%)"
        )
        print(
            f"sets:  {_progress_bar(sets_done, total_sets, active=bool(active_task and str(effective_status) == 'running'), color=color, bar_color=BLUE)} "
            + _style(color, f"{sets_done}/{total_sets}", BOLD, BLUE)
            + (f"  ({100.0 * sets_done / total_sets:.1f}%)" if total_sets else "")
        )
        if elapsed_sec is not None:
            print(
                f"elapsed: {_style(color, _human_duration(elapsed_sec), BOLD, GREEN)}"
                + f"  eta: {_style(color, _human_duration(eta_sec), BOLD, YELLOW)}"
            )
        if active_task:
            current_line = (
                f"{progress.get('active_set_id')} / "
                f"{active_task.get('task_id')} "
                f"({active_task.get('domain')}, {active_task.get('kind')})"
            )
            print("current_task: " + _style(color, current_line, BOLD, CYAN))
        elif str(effective_status) == "completed":
            print("current_task: " + _style(color, "completed", BOLD, GREEN))
        else:
            print("current_task: " + _style(color, "unknown", BOLD, YELLOW))
        if active_process.get("label"):
            stage_line = active_process["label"]
            if active_process.get("context"):
                stage_line += f"  [{active_process['context']}]"
            if active_process.get("detail"):
                stage_line += f"  - {active_process['detail']}"
            print("current_stage: " + _style(color, stage_line, BOLD, MAGENTA))
        recent_completed = progress.get("recent_completed")
        if isinstance(recent_completed, list) and recent_completed:
            print(_style(color, "recent_completed:", BOLD, GREEN))
            for item in recent_completed:
                if not isinstance(item, dict) or not item.get("task_id"):
                    continue
                pass_text = _fmt_bool(item.get("pass"))
                pass_color = GREEN if pass_text == "PASS" else RED if pass_text == "FAIL" else GRAY
                completed_line = (
                    f"{item.get('set_id')} / {item.get('task_id')} "
                    f"({item.get('domain')}, {item.get('kind')})"
                )
                print(
                    "  - "
                    + _style(color, completed_line, BOLD, GREEN)
                    + "  pass="
                    + _style(color, pass_text, BOLD, pass_color)
                    + "  at "
                    + _style(
                        color,
                        item["updated_at"].isoformat(timespec="seconds"),
                        DIM,
                    )
                )
        recent_failed = progress.get("recent_failed")
        if isinstance(recent_failed, list) and recent_failed:
            print(_style(color, "recent_failed:", BOLD, RED))
            for item in recent_failed:
                if not isinstance(item, dict) or not item.get("task_id"):
                    continue
                failed_line = (
                    f"{item.get('set_id')} / {item.get('task_id')} "
                    f"({item.get('domain')}, {item.get('kind')})"
                )
                print(
                    "  - "
                    + _style(color, failed_line, BOLD, RED)
                    + "  at "
                    + _style(
                        color,
                        item["updated_at"].isoformat(timespec="seconds"),
                        DIM,
                    )
                )
                if item.get("error"):
                    err = str(item["error"])
                    if len(err) > 120:
                        err = err[:117] + "..."
                    print("    " + _style(color, f"error: {err}", RED))

    summary_json = run_root / 'summary.json'
    if summary_json.exists():
        summary = _read_json(summary_json)
        sets = summary.get('sets', []) if isinstance(summary.get('sets'), list) else []
        print()
        print(_style(color, f'summary_sets: {len(sets)}', BOLD, GREEN))
        for s in sets:
            pass_text = _fmt_bool(s.get('pass'))
            pass_color = GREEN if pass_text == "PASS" else RED if pass_text == "FAIL" else GRAY
            fail_brief = ""
            tasks = s.get("tasks", []) if isinstance(s.get("tasks"), list) else []
            failed_results = [t for t in tasks if isinstance(t, dict) and t.get("pass") is False]
            if failed_results:
                first_failed = failed_results[0]
                reason = (
                    str(first_failed.get("service_failed_stage", "")).strip()
                    or str(first_failed.get("acceptance_note", "")).strip()
                    or "task failed"
                )
                fail_brief = _truncate(
                    f"{first_failed.get('task_id')} ({first_failed.get('domain')}): {reason}"
                )
            print(
                f"- {s.get('set_id')}: "
                + _style(color, pass_text, BOLD, pass_color)
                + f"  zip={Path(str(s.get('zip_path',''))).name}"
                + (
                    f"  reason={_style(color, '[' + _failure_tag(fail_brief)[0] + ']', BOLD, _failure_tag(fail_brief)[1])} "
                    + _style(color, fail_brief, RED if _failure_tag(fail_brief)[0] != 'infra' else YELLOW)
                    if fail_brief and pass_text == "FAIL"
                    else ""
                )
            )
    else:
        print(_style(color, 'summary: not written yet', BOLD, YELLOW))

    if progress["rows"]:
        print()
        print(_style(color, "sets:", BOLD, MAGENTA))
    for row in progress["rows"]:
        status_text = str(row["status"])
        status_color = {
            "complete": GREEN,
            "partial": YELLOW,
            "failed": RED,
            "pending": GRAY,
        }.get(status_text, GRAY)
        set_bar = _progress_bar(
            int(row["task_done"]),
            int(row["task_total"]),
            active=bool(row.get("active_task_id") and str(effective_status) == "running"),
            color=color,
            bar_color=status_color,
        )
        line = (
            f"set {row['set_id']}: "
            + _style(color, status_text, BOLD, status_color)
            + f"  {set_bar}  {row['task_done']}/{row['task_total']}"
        )
        set_eta_sec = None
        if status_text == "complete":
            set_eta_sec = 0.0
        elif status_text in {"partial", "failed"}:
            started_at = row.get("generated_at")
            if isinstance(started_at, dt.datetime):
                local_now = dt.datetime.now(started_at.tzinfo) if started_at.tzinfo else dt.datetime.now()
                set_elapsed_sec = max(0.0, (local_now - started_at).total_seconds())
                if int(row["task_done"]) > 0 and int(row["task_total"]) > int(row["task_done"]):
                    set_eta_sec = set_elapsed_sec / int(row["task_done"]) * (int(row["task_total"]) - int(row["task_done"]))
                elif int(row["task_done"]) == 0 and avg_task_sec is not None:
                    set_eta_sec = avg_task_sec * int(row["task_total"])
            elif avg_task_sec is not None:
                remaining = max(0, int(row["task_total"]) - int(row["task_done"]))
                set_eta_sec = avg_task_sec * remaining
        elif status_text == "pending" and avg_task_sec is not None:
            set_eta_sec = avg_task_sec * int(row["task_total"])
        if row["pass"] is not None:
            pass_text = _fmt_bool(row["pass"])
            pass_color = GREEN if pass_text == "PASS" else RED if pass_text == "FAIL" else GRAY
            line += "  pass=" + _style(color, pass_text, BOLD, pass_color)
            if pass_text == "FAIL" and row.get("fail_brief"):
                tag, tag_color = _failure_tag(str(row["fail_brief"]))
                line += "  reason=" + _style(color, f"[{tag}]", BOLD, tag_color) + " " + _style(
                    color,
                    str(row["fail_brief"]),
                    RED if tag != "infra" else YELLOW,
                )
        if set_eta_sec is not None:
            eta_color = GREEN if status_text == "complete" else YELLOW if status_text in {"partial", "pending"} else RED
            line += "  eta=" + _style(color, _human_duration(set_eta_sec), BOLD, eta_color)
        if row.get("active_task_id"):
            line += (
                "  active="
                + _style(
                    color,
                    f"{row['active_task_id']} ({row['active_task_domain']}, {row['active_task_kind']})",
                    CYAN,
                )
            )
        print(line)
        failed_task = row.get("failed_task") if isinstance(row.get("failed_task"), dict) else None
        if failed_task:
            print(
                "  "
                + _style(
                    color,
                    f"failed_task: {failed_task.get('task_id')} "
                    f"domain={failed_task.get('domain')} kind={failed_task.get('kind')}",
                    RED,
                )
            )


def main() -> int:
    ap = argparse.ArgumentParser(description='Show status for a bioRxiv external validation run root.')
    ap.add_argument('--run-root', required=True)
    ap.add_argument('--loop', action=argparse.BooleanOptionalAction, default=False)
    ap.add_argument('--interval-sec', type=float, default=5.0)
    ap.add_argument('--clear-screen', action=argparse.BooleanOptionalAction, default=False)
    ap.add_argument('--color', action=argparse.BooleanOptionalAction, default=True)
    args = ap.parse_args()

    run_root = (ROOT / args.run_root).resolve() if not Path(args.run_root).is_absolute() else Path(args.run_root).resolve()

    while True:
        if args.clear_screen:
            print("\033[2J\033[H", end="")
        _print_snapshot(run_root, bool(args.color))
        if not args.loop:
            break
        time.sleep(max(0.2, float(args.interval_sec)))
        print()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
