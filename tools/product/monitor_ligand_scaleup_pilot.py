#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any

from tools.monitor_ui import (
    BOLD,
    BLUE,
    CYAN,
    DIM,
    GRAY,
    GREEN,
    MAGENTA,
    RED,
    RESET,
    YELLOW,
    human_duration as _ui_human_duration,
    progress_bar as _ui_progress_bar,
    shorten as _ui_shorten,
    style as _ui_style,
)


ROOT = Path(__file__).resolve().parents[2]
TASK_PROGRESS_STALE_SEC_DEFAULT = 15 * 60
TASK_PROGRESS_STALE_SEC_HARD_DECOY = 10 * 60
TASK_PROGRESS_STALE_SEC_STAGE2 = 10 * 60


def _style(enabled: bool, text: str, *codes: str) -> str:
    return _ui_style(enabled, text, *codes)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_dt(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return dt.datetime.fromisoformat(value)
    except Exception:
        return None


def _human_duration(seconds: float | None) -> str:
    return _ui_human_duration(seconds, include_days=True)


def _file_mtime_dt(path: Path) -> dt.datetime | None:
    try:
        return dt.datetime.fromtimestamp(path.stat().st_mtime)
    except Exception:
        return None


def _coerce_now(now: dt.datetime, reference: dt.datetime) -> dt.datetime:
    if reference.tzinfo is not None and now.tzinfo is None:
        return now.replace(tzinfo=reference.tzinfo)
    if reference.tzinfo is None and now.tzinfo is not None:
        return now.replace(tzinfo=None)
    return now


def _progress_snapshot_meta(
    *,
    source: str,
    payload: dict[str, Any] | None,
    path: Path | None,
    now: dt.datetime | None,
    terminal: bool = False,
    idle: bool = False,
) -> dict[str, Any]:
    payload = payload or {}
    updated = _parse_dt(payload.get("updated_at_local")) or _parse_dt(payload.get("generated_at_local"))
    if updated is None and path is not None:
        updated = _file_mtime_dt(path)
    age_sec: float | None = None
    if updated is not None:
        ref_now = _coerce_now(now or dt.datetime.now(updated.tzinfo), updated)
        age_sec = max(0.0, (ref_now - updated).total_seconds())
    stale_sec = TASK_PROGRESS_STALE_SEC_DEFAULT
    if source == "hard_decoy_progress":
        stale_sec = TASK_PROGRESS_STALE_SEC_HARD_DECOY
    elif source == "stage2_traj_progress":
        stale_sec = TASK_PROGRESS_STALE_SEC_STAGE2
    return {
        "progress_source": source,
        "progress_updated_at": updated.isoformat() if updated is not None else "",
        "progress_age_sec": age_sec,
        "progress_age_text": _human_duration(age_sec),
        "freshness": "done" if terminal else ("idle" if idle else ("stale" if age_sec is not None and age_sec > stale_sec else "fresh")),
        "stale_threshold_sec": stale_sec,
    }


def _progress_bar(done: int, total: int, *, width: int = 28, color: bool = False, bar_color: str = CYAN) -> str:
    return _ui_progress_bar(done, total, width=width, color=color, bar_color=bar_color)


def _proc_lines(pattern: str) -> list[str]:
    try:
        out = subprocess.check_output(["pgrep", "-af", pattern], text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return []
    rows: list[str] = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        if "pgrep -af" in line:
            continue
        if "monitor_ligand_scaleup_pilot.py" in line:
            continue
        rows.append(line)
    return rows


def _proc_lines_for_tag(tag: str, task_rows: list[dict[str, Any]] | None = None) -> list[str]:
    tag = str(tag).strip()
    if not tag:
        return []
    proc_pattern = (
        "product/run_ligand_scaleup_100k_pilot_current.py|run_external_validation_blind_sets.py|"
        "run_ligand_stress_validation.py|run_ligand_htvs_pipeline.py|generate_ligand_trajectory_engine.py|"
        "build_ligand_mapping_queue.py|run_ligand_backmapping_scoring.py|"
        "run_idp_3bead_release_smoke_current.py|run_idp_3bead_holdout_pipeline.py|run_idp_3bead_evaluator.py"
    )
    rows = _proc_lines(proc_pattern)
    keep: list[str] = []
    markers = [
        tag,
        f"external_validation_{tag}_",
        f"external_validation_blind_runs_{tag}",
    ]
    for row in task_rows or []:
        suffix = str(row.get("date_tag_suffix", "")).strip()
        if suffix:
            markers.append(suffix)
    for line in rows:
        if any(marker in line for marker in markers):
            keep.append(line)
    return keep


def _extract_arg(cmdline: str, flag: str) -> str:
    try:
        parts = shlex.split(cmdline)
    except Exception:
        parts = cmdline.split()
    for idx, part in enumerate(parts):
        if part == flag and idx + 1 < len(parts):
            return parts[idx + 1]
    return ""


def _shorten(text: str, limit: int = 120) -> str:
    return _ui_shorten(text, limit=limit)


def _fmt_metric(value: Any, digits: int = 3) -> str:
    try:
        if value in (None, ""):
            return "-"
        return f"{float(value):.{digits}f}".rstrip("0").rstrip(".")
    except Exception:
        return str(value)


def _artifact_lines(paths: list[str], *, limit: int = 4) -> list[str]:
    out: list[str] = []
    for item in paths:
        path = ROOT / item
        if path.exists():
            out.append(path.name)
        if len(out) >= limit:
            break
    return out


def _resolve_repo_path(path_str: str) -> Path:
    path = Path(path_str)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _load_task_rows(dryrun_json: Path) -> list[dict[str, Any]]:
    if not dryrun_json.exists():
        return []
    payload = _read_json(dryrun_json)
    rows = payload.get("task_rows") or []
    return [row for row in rows if isinstance(row, dict)]


def _load_run_summary(run_root: Path) -> dict[str, Any]:
    summary_json = run_root / "summary.json"
    if summary_json.exists():
        return _read_json(summary_json)
    state_json = run_root / "state.json"
    if state_json.exists():
        return _read_json(state_json)
    return {}


def _collect_completed_tasks(run_summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    completed: dict[str, dict[str, Any]] = {}
    for set_row in run_summary.get("sets", []):
        for task in set_row.get("tasks", []):
            task_id = str(task.get("task_id", "")).strip()
            if task_id:
                completed[task_id] = task
    return completed


def _collect_task_terminal_summaries(tag: str, task_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    completed: dict[str, dict[str, Any]] = {}
    for row in task_rows:
        task_id = str(row.get("task_id", "")).strip()
        if not task_id:
            continue
        summary_json = Path(f"{_task_out_prefix(tag, row)}_summary.json")
        if not summary_json.exists():
            continue
        try:
            payload = _read_json(summary_json)
        except Exception:
            continue
        if isinstance(payload, dict) and any(k in payload for k in ("pass", "raw_pass", "strict_gate_pass", "operational_gate_pass")):
            completed[task_id] = payload
    return completed


def _find_active_task(task_rows: list[dict[str, Any]], proc_lines: list[str]) -> tuple[str, str]:
    for line in proc_lines:
        if "run_ligand_stress_validation.py" not in line:
            continue
        for row in task_rows:
            suffix = str(row.get("date_tag_suffix", "")).strip()
            if suffix and suffix in line:
                return str(row.get("task_id", "")).strip(), line
        date_tag = _extract_arg(line, "--date-tag")
        if date_tag:
            return date_tag, line
    return "", ""


def _find_external_activity(proc_lines: list[str]) -> tuple[str, str]:
    for line in proc_lines:
        if "run_idp_3bead_release_smoke_current.py" in line:
            return "idp_smoke_current", line
        if "run_idp_3bead_holdout_pipeline.py" in line:
            return "idp_holdout_pipeline", line
    return "", ""


def _classify_status(run_summary: dict[str, Any], proc_lines: list[str]) -> tuple[str, str]:
    status = str(run_summary.get("status", "")).strip().lower()
    if status == "completed":
        return "completed", GREEN
    if proc_lines:
        return "running", CYAN
    updated = _parse_dt(run_summary.get("updated_at_local"))
    if status == "running" and updated is not None:
        age = (dt.datetime.now(updated.tzinfo) - updated).total_seconds()
        if age > 900:
            return "stale", YELLOW
        return "stopped", RED
    if status:
        return status, YELLOW
    return "unknown", GRAY


def _task_state_rows(
    task_rows: list[dict[str, Any]],
    completed: dict[str, dict[str, Any]],
    active_task_id: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in task_rows:
        task_id = str(row.get("task_id", "")).strip()
        if task_id in completed:
            task = completed[task_id]
            rows.append(
                {
                    "task_id": task_id,
                    "set_id": row.get("set_id", ""),
                    "domain": row.get("domain", ""),
                    "ligand_sizes": row.get("ligand_sizes", ""),
                    "state": "pass" if task.get("pass") is True else "fail",
                    "metrics": task.get("metrics") or task.get("ranking_metrics") or {},
                }
            )
        elif active_task_id and active_task_id == task_id:
            rows.append(
                {
                    "task_id": task_id,
                    "set_id": row.get("set_id", ""),
                    "domain": row.get("domain", ""),
                    "ligand_sizes": row.get("ligand_sizes", ""),
                    "state": "running",
                    "metrics": {},
                }
            )
        else:
            rows.append(
                {
                    "task_id": task_id,
                    "set_id": row.get("set_id", ""),
                    "domain": row.get("domain", ""),
                    "ligand_sizes": row.get("ligand_sizes", ""),
                    "state": "pending",
                    "metrics": {},
                }
            )
    return rows


def _task_out_prefix(tag: str, row: dict[str, Any]) -> Path:
    return ROOT / "runs" / f"external_validation_{tag}_{row.get('set_id', '')}_{row.get('task_id', '')}"


def _safe_ratio(value: Any, fallback_num: Any = None, fallback_den: Any = None) -> float | None:
    try:
        ratio = float(value)
        if 0.0 <= ratio <= 1.0:
            return ratio
    except Exception:
        pass
    try:
        num = float(fallback_num)
        den = float(fallback_den)
        if den > 0:
            ratio = num / den
            if 0.0 <= ratio <= 1.0:
                return ratio
    except Exception:
        pass
    return None


def _task_subprocess_candidate(out_prefix: Path, proc_lines: list[str] | None, now: dt.datetime | None) -> dict[str, Any] | None:
    if not proc_lines:
        return None
    out_prefix_str = str(out_prefix)
    probes = [
        ("build_ligand_mapping_queue.py", "stage1_queue_builder", "stage1_queue_build", "mapping queue builder running"),
        ("generate_ligand_trajectory_engine.py", "stage2_engine_subprocess", "stage2_trajectory", "trajectory engine worker running"),
        ("run_ligand_backmapping_scoring.py", "stage3_scoring_subprocess", "stage3_scoring", "backmapping/scoring worker running"),
    ]
    for line in proc_lines:
        if out_prefix_str not in line:
            continue
        for needle, source, phase, detail in probes:
            if needle in line:
                return {
                    "pct": 0.0,
                    "phase": phase,
                    "detail": detail,
                    **_progress_snapshot_meta(source=source, payload=None, path=None, now=now),
                }
    return None


def _task_progress_hint(
    tag: str,
    row: dict[str, Any],
    completed: dict[str, dict[str, Any]],
    *,
    now: dt.datetime | None = None,
    proc_lines: list[str] | None = None,
) -> dict[str, Any]:
    task_id = str(row.get("task_id", "")).strip()
    ligand_sizes = str(row.get("ligand_sizes", "")).strip()
    if task_id in completed:
        return {
            "pct": 100.0,
            "phase": "completed",
            "detail": "task finished",
            **_progress_snapshot_meta(source="run_summary", payload=completed.get(task_id), path=None, now=now, terminal=True),
        }

    out_prefix = _task_out_prefix(tag, row)
    progress_candidates: list[dict[str, Any]] = []

    hard_progress_json = Path(f"{out_prefix}_hard_decoy_progress.json")
    if hard_progress_json.exists():
        payload = _read_json(hard_progress_json)
        ratio = _safe_ratio(payload.get("progress_ratio"), payload.get("generated_total"), payload.get("requested_total"))
        if ratio is not None:
            detail = f"{int(payload.get('generated_total', 0))}/{int(payload.get('requested_total', 0) or 0)} decoys"
            current_target = str(payload.get("current_target", "")).strip()
            if current_target:
                detail += f" target={current_target}"
            progress_candidates.append(
                {
                    "pct": ratio * 100.0,
                    "phase": str(payload.get("phase", "hard_decoy")).strip() or "hard_decoy",
                    "detail": detail,
                    **_progress_snapshot_meta(source="hard_decoy_progress", payload=payload, path=hard_progress_json, now=now),
                }
            )

    planned_key = f"p0_n{ligand_sizes}_r1"
    stage2_progress_json = Path(f"{out_prefix}_{planned_key}_stage2_traj_progress.json")
    if stage2_progress_json.exists():
        payload = _read_json(stage2_progress_json)
        ratio = _safe_ratio(payload.get("progress_ratio"), payload.get("processed_rows"), payload.get("queue_rows_total"))
        if ratio is not None:
            detail = f"{int(payload.get('processed_rows', 0))}/{int(payload.get('queue_rows_total', 0) or 0)} rows"
            current_target = str(payload.get("current_target", "")).strip()
            if current_target:
                detail += f" target={current_target}"
            current_ligand = str(payload.get("current_ligand_id", "")).strip()
            if current_ligand:
                detail += f" ligand={current_ligand}"
            progress_candidates.append(
                {
                    "pct": ratio * 100.0,
                    "phase": str(payload.get("phase", "stage2_trajectory")).strip() or "stage2_trajectory",
                    "detail": detail,
                    **_progress_snapshot_meta(source="stage2_traj_progress", payload=payload, path=stage2_progress_json, now=now),
                }
            )

    subprocess_candidate = _task_subprocess_candidate(out_prefix, proc_lines, now)
    if subprocess_candidate is not None:
        progress_candidates.append(subprocess_candidate)

    if progress_candidates:
        if len(progress_candidates) == 1:
            return progress_candidates[0]

        def _candidate_rank(candidate: dict[str, Any]) -> tuple[int, int, float]:
            source = str(candidate.get("progress_source", "")).strip()
            phase = str(candidate.get("phase", "")).strip().lower()
            freshness = str(candidate.get("freshness", "")).strip().lower()
            updated_at = _parse_dt(candidate.get("progress_updated_at"))
            updated_ts = updated_at.timestamp() if updated_at is not None else 0.0

            # Prefer downstream stage2 progress once hard-decoy generation has completed,
            # then prefer fresher and newer signals.
            source_priority = 0
            if source == "stage2_traj_progress":
                source_priority = 3 if phase != "pending" else 1
            elif source == "hard_decoy_progress":
                source_priority = 2 if phase not in {"complete", "completed"} else 0
            elif source in {"stage1_queue_builder", "stage2_engine_subprocess", "stage3_scoring_subprocess"}:
                source_priority = 2

            freshness_priority = {
                "fresh": 3,
                "done": 2,
                "stale": 1,
                "idle": 0,
            }.get(freshness, 0)
            return (source_priority, freshness_priority, updated_ts)

        return max(progress_candidates, key=_candidate_rank)

    state_json = Path(f"{out_prefix}_state.json")
    if state_json.exists():
        try:
            payload = _read_json(state_json)
            current = payload.get("current") or {}
            current_status = str(current.get("status", "")).strip()
            if current_status:
                return {
                    "pct": 0.0,
                    "phase": current_status,
                    "detail": "task initialized",
                    **_progress_snapshot_meta(source="task_state", payload=payload, path=state_json, now=now),
                }
        except Exception:
            pass

    return {
        "pct": 0.0,
        "phase": "pending",
        "detail": "",
        **_progress_snapshot_meta(source="none", payload=None, path=None, now=now, idle=True),
    }


def _set_progress(task_states: list[dict[str, Any]]) -> list[dict[str, Any]]:
    set_order = ["set3_operational_smoke", "set1_core_blind", "set2_expanded_ood"]
    rows: list[dict[str, Any]] = []
    for set_id in set_order:
        items = [row for row in task_states if row["set_id"] == set_id]
        if not items:
            continue
        done = sum(1 for row in items if row["state"] in {"pass", "fail"})
        passed = sum(1 for row in items if row["state"] == "pass")
        failed = sum(1 for row in items if row["state"] == "fail")
        running = any(row["state"] == "running" for row in items)
        if done == len(items):
            label = "PASS" if failed == 0 else "FAIL"
        elif running:
            label = "running"
        else:
            label = "pending"
        rows.append(
            {
                "set_id": set_id,
                "done": done,
                "total": len(items),
                "passed": passed,
                "failed": failed,
                "label": label,
            }
        )
    return rows


def _active_task_signal(progress: dict[str, Any] | None) -> tuple[str, str]:
    if not progress:
        return "RUN(alive)", CYAN
    freshness = str(progress.get("freshness", "")).strip().lower()
    progress_label = {
        "stale": "STALE(progress)",
        "fresh": "FRESH(progress)",
        "done": "DONE(progress)",
        "idle": "IDLE(progress)",
    }.get(freshness, "UNKNOWN(progress)")
    color = RED if freshness == "stale" else (GREEN if freshness == "done" else (CYAN if freshness == "fresh" else GRAY))
    return f"RUN(alive)/{progress_label}", color


def _render(args: argparse.Namespace) -> str:
    run_root = _resolve_repo_path(args.run_root)
    dryrun_json = _resolve_repo_path(args.dryrun_json)
    pilot_json = _resolve_repo_path(args.pilot_json)

    run_summary = _load_run_summary(run_root)
    dryrun_payload = _read_json(dryrun_json) if dryrun_json.exists() else {}
    pilot_payload = _read_json(pilot_json) if pilot_json.exists() else {}
    task_rows = _load_task_rows(dryrun_json)
    updated = _parse_dt(run_summary.get("updated_at_local"))
    generated = _parse_dt(run_summary.get("generated_at_local"))
    now = dt.datetime.now(updated.tzinfo) if updated is not None else dt.datetime.now()

    tag = run_root.name.replace("external_validation_blind_runs_", "")
    proc_lines = _proc_lines_for_tag(tag, task_rows)
    status, status_color = _classify_status(run_summary, proc_lines)
    active_task_id, active_cmd = _find_active_task(task_rows, proc_lines)
    external_task_id, external_cmd = _find_external_activity(proc_lines)
    completed = _collect_completed_tasks(run_summary)
    task_terminal = _collect_task_terminal_summaries(tag, task_rows)
    for task_id, payload in task_terminal.items():
        completed.setdefault(task_id, payload)
    task_states = _task_state_rows(task_rows, completed, active_task_id)
    protein_progress_rows = [
        {
            **row,
            "progress": _task_progress_hint(tag, row, completed, now=now, proc_lines=proc_lines),
        }
        for row in task_rows
        if str(row.get("ligand_sizes", "")).strip() == "100000"
    ]
    progress_by_task_id = {row["task_id"]: row["progress"] for row in protein_progress_rows}
    if active_task_id and active_task_id not in progress_by_task_id:
        active_row = next((row for row in task_rows if str(row.get("task_id", "")).strip() == active_task_id), None)
        if active_row is not None:
            progress_by_task_id[active_task_id] = _task_progress_hint(tag, active_row, completed, now=now, proc_lines=proc_lines)
    set_rows = _set_progress(task_states)

    total_tasks = len(task_states)
    done_tasks = sum(1 for row in task_states if row["state"] in {"pass", "fail"})
    last_update_age = _human_duration((now - updated).total_seconds()) if updated is not None else "unknown"
    elapsed = _human_duration((now - generated).total_seconds()) if generated is not None else "unknown"

    launch = dryrun_payload.get("launch_readiness") or {}
    drift = dryrun_payload.get("selected_drift_audit") or {}
    guardrails = dryrun_payload.get("guardrail_summary") or []
    domains = (dryrun_payload.get("selected_scope_summary") or {}).get("domains_touched") or []
    comparison_enabled = bool(dryrun_payload.get("comparison_enabled"))
    compact = bool(getattr(args, "compact", False))

    lines: list[str] = []
    lines.append(_style(args.color, "Ligand Scale-Up 100k Pilot Monitor", BOLD, CYAN))
    lines.append(f"run_root: {run_root}")
    lines.append(f"tag: {tag}")
    lines.append(
        "status: "
        + _style(args.color, status, BOLD, status_color)
        + f"  updated={run_summary.get('updated_at_local', 'unknown')}  age={last_update_age}"
    )
    lines.append(f"elapsed: {elapsed}")
    lines.append("")

    if compact:
        lines.append(
            f"contract full={pilot_payload.get('full_task_count_100k', 'NA')}@100k"
            f" smoke={pilot_payload.get('smoke_task_count_unchanged', 'NA')}@64"
            f" | launch={launch.get('status', 'unknown')}"
            f" | drift={'ok' if drift.get('ok') else 'check'}"
            f" | cmp={'on' if comparison_enabled else 'off'}"
        )
        lines.append("")
    else:
        lines.append(_style(args.color, "Pilot Contract", BOLD, MAGENTA))
        lines.append(
            f"shape: full={pilot_payload.get('full_task_count_100k', 'NA')} tasks at 100000, "
            f"smoke={pilot_payload.get('smoke_task_count_unchanged', 'NA')} tasks at 64"
        )
        lines.append(f"domains: {', '.join(domains) if domains else 'unknown'}")
        lines.append(
            "launch_readiness: "
            + _style(args.color, str(launch.get('status', 'unknown')), BOLD, GREEN if launch.get("ready") else YELLOW)
            + f"  blockers={launch.get('blocking_issue_count', 'NA')}  comparison={'on' if comparison_enabled else 'off'}"
        )
        lines.append(
            f"drift_audit: {'ok' if drift.get('ok') else 'check'}  "
            f"nonstandard={drift.get('nonstandard_ligand_size_count', 'NA')}  "
            f"missing_intent={drift.get('profile_missing_intent_count', 'NA')}"
        )
        lines.append("")

    lines.append(_style(args.color, "Overall Progress", BOLD, MAGENTA))
    lines.append(
        f"tasks: {_progress_bar(done_tasks, total_tasks, color=args.color, bar_color=CYAN)} "
        f"{done_tasks}/{total_tasks}"
    )
    lines.append(
        f"sets:  {_progress_bar(sum(1 for row in set_rows if row['done'] == row['total']), len(set_rows), color=args.color, bar_color=BLUE)} "
        f"{sum(1 for row in set_rows if row['done'] == row['total'])}/{len(set_rows)}"
    )
    for row in set_rows:
        label_color = GREEN if row["label"] == "PASS" else (RED if row["label"] == "FAIL" else (CYAN if row["label"] == "running" else GRAY))
        lines.append(
            f"- {row['set_id']}: "
            + _style(args.color, row["label"], BOLD, label_color)
            + f"  {row['done']}/{row['total']}  pass={row['passed']} fail={row['failed']}"
        )
    lines.append("")

    lines.append(_style(args.color, "Current Activity", BOLD, MAGENTA))
    if active_task_id:
        lines.append(f"active_task: {_style(args.color, active_task_id, BOLD, YELLOW)}")
        signal_text, signal_color = _active_task_signal(progress_by_task_id.get(active_task_id))
        lines.append(f"task_signal: {_style(args.color, signal_text, BOLD, signal_color)}")
        active_progress = progress_by_task_id.get(active_task_id) or {}
        active_age = str(active_progress.get("progress_age_text", "")).strip()
        active_updated = str(active_progress.get("progress_updated_at", "")).strip()
        if active_age and active_age != "unknown":
            lines.append(f"task_progress_age: {active_age}  updated={active_updated or 'unknown'}")
        lines.append(f"active_cmd: {_shorten(active_cmd, 160)}")
    else:
        if external_task_id and status != "completed":
            lines.append(f"active_task: {_style(args.color, external_task_id, BOLD, YELLOW)}")
            lines.append("task_scope: outside_ligand_9task_contract")
            lines.append(f"active_cmd: {_shorten(external_cmd, 160)}")
        else:
            lines.append("active_task: none")
    lines.append(f"live_process_count: {len(proc_lines)}")
    if proc_lines:
        for line in proc_lines[:4]:
            lines.append(f"  { _shorten(line, 140) }")
    else:
        lines.append(f"  {_style(args.color, 'no run-tag-bound processes', DIM, GRAY)}")
    lines.append("")

    if compact and status == "completed":
        lines.append(_style(args.color, "Highlights", BOLD, MAGENTA))
        failed_rows = [row for row in task_states if row["state"] == "fail"]
        if failed_rows:
            for row in failed_rows:
                metrics = row.get("metrics") or {}
                lines.append(
                    f"- {_style(args.color, 'FAIL', BOLD, RED)}  {row['task_id']} [{row['domain']}]"
                    f"  PR={_fmt_metric(metrics.get('ranking_pr_auc'), 4)}"
                    f"  EF1={_fmt_metric(metrics.get('ranking_ef1'), 2)}"
                )
        else:
            lines.append(f"- {_style(args.color, 'no failing tasks', GREEN)}")
        domain_summary: list[str] = []
        for domain in ["gpcr", "ion_channel", "kinase"]:
            rows = [row for row in task_states if row["domain"] == domain and row["state"] in {"pass", "fail"}]
            if not rows:
                continue
            ok = sum(1 for row in rows if row["state"] == "pass")
            bad = sum(1 for row in rows if row["state"] == "fail")
            domain_summary.append(f"{domain} {ok}p/{bad}f")
        if domain_summary:
            lines.append("domains: " + " | ".join(domain_summary))
        lines.append("")
    else:
        lines.append(_style(args.color, "Task Board", BOLD, MAGENTA))
        for row in task_states:
            if row["state"] == "pass":
                state_text = _style(args.color, "PASS", BOLD, GREEN)
            elif row["state"] == "fail":
                state_text = _style(args.color, "FAIL", BOLD, RED)
            elif row["state"] == "running":
                state_text = _style(args.color, "RUN", BOLD, CYAN)
            else:
                state_text = _style(args.color, "PEND", DIM, GRAY)
            metrics = row.get("metrics") or {}
            metric_bits: list[str] = []
            if "ranking_pr_auc" in metrics:
                metric_bits.append(f"PR={metrics['ranking_pr_auc']:.4f}")
            if "ranking_ef1" in metrics:
                metric_bits.append(f"EF1={metrics['ranking_ef1']:.2f}")
            if "strict_gate_pass" in metrics:
                metric_bits.append(f"strict={metrics['strict_gate_pass']}")
            metric_suffix = f"  {'  '.join(metric_bits)}" if metric_bits else ""
            lines.append(
                f"- {state_text}  {row['task_id']}  [{row['set_id']}]  n={row['ligand_sizes']}  domain={row['domain']}{metric_suffix}"
            )
        lines.append("")

        lines.append(_style(args.color, "100k Protein Progress", BOLD, MAGENTA))
        freshness_counts = {
            "fresh": sum(1 for row in protein_progress_rows if row["progress"].get("freshness") == "fresh"),
            "stale": sum(1 for row in protein_progress_rows if row["progress"].get("freshness") == "stale"),
            "done": sum(1 for row in protein_progress_rows if row["progress"].get("freshness") == "done"),
            "idle": sum(1 for row in protein_progress_rows if row["progress"].get("freshness") == "idle"),
        }
        lines.append(
            "freshness: "
            f"fresh={freshness_counts['fresh']}  stale={freshness_counts['stale']}  "
            f"done={freshness_counts['done']}  idle={freshness_counts['idle']}"
        )
        for row in protein_progress_rows:
            progress = row["progress"]
            pct = float(progress.get("pct", 0.0) or 0.0)
            if pct >= 100.0:
                pct_text = _style(args.color, f"{pct:5.1f}%", BOLD, GREEN)
            elif pct > 0.0:
                pct_text = _style(args.color, f"{pct:5.1f}%", BOLD, YELLOW)
            else:
                pct_text = _style(args.color, f"{pct:5.1f}%", DIM, GRAY)
            phase = str(progress.get("phase", "")).strip()
            detail = str(progress.get("detail", "")).strip()
            freshness = str(progress.get("freshness", "")).strip()
            freshness_color = GREEN if freshness == "done" else (RED if freshness == "stale" else (CYAN if freshness == "fresh" else GRAY))
            freshness_text = _style(args.color, freshness or "unknown", BOLD if freshness in {"fresh", "stale", "done"} else DIM, freshness_color)
            age_text = str(progress.get("progress_age_text", "")).strip()
            suffix = f"  phase={phase}" if phase else ""
            suffix += f"  progress={freshness_text}"
            if age_text and age_text != "unknown":
                suffix += f"  age={age_text}"
            if detail:
                suffix += f"  {detail}"
            lines.append(f"- {pct_text}  {row['task_id']}  [{row['domain']}]{suffix}")
        lines.append("")

    if not compact:
        lines.append(_style(args.color, "Guardrails", BOLD, MAGENTA))
        for row in guardrails:
            lines.append(f"- {row.get('guardrail_id', 'unknown')}: {row.get('threshold', '')} ({row.get('scope', '')})")
    else:
        compact_guardrails = [str(row.get("guardrail_id", "unknown")) for row in guardrails[:4]]
        lines.append("guardrails: " + (", ".join(compact_guardrails) if compact_guardrails else "-"))

    artifact_names = _artifact_lines(
        [
            "runs/ligand_scaleup_100k_test_audit_current.md",
            "runs/ligand_scaleup_100k_decoy_proof_current.md",
        ],
        limit=4,
    )
    if artifact_names:
        lines.append("")
        lines.append(_style(args.color, "Next Artifacts", BOLD, MAGENTA))
        lines.append("  " + " | ".join(artifact_names))
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Detailed status window for the 100k ligand scale-up pilot.")
    ap.add_argument(
        "--run-root",
        default="runs/external_validation_blind_runs/external_validation_blind_runs_2026-03-23_scaleup_100k_pilot_v1",
    )
    ap.add_argument("--pilot-json", default="runs/ligand_scaleup_100k_pilot_current.json")
    ap.add_argument("--dryrun-json", default="runs/ligand_scaleup_100k_pilot_dryrun_current.json")
    ap.add_argument("--loop", action=argparse.BooleanOptionalAction, default=False)
    ap.add_argument("--interval-sec", type=float, default=5.0)
    ap.add_argument("--clear-screen", action=argparse.BooleanOptionalAction, default=False)
    ap.add_argument("--color", action=argparse.BooleanOptionalAction, default=False)
    ap.add_argument("--compact", action=argparse.BooleanOptionalAction, default=False)
    args = ap.parse_args()

    while True:
        if args.clear_screen:
            print("\033[2J\033[H", end="")
        print(_render(args))
        if not args.loop:
            break
        time.sleep(max(1.0, float(args.interval_sec)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
