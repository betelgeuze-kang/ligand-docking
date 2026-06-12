#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import subprocess
import sys
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
STALE_SEC = 15 * 60

TASK_ORDER = [
    ("set1_core_blind", "ion_trpv1_chembl20_full", "ion_channel"),
    ("set1_core_blind", "kinase_core_full", "kinase"),
    ("set2_expanded_ood", "ion_trpv1_chembl50_full", "ion_channel"),
    ("set2_expanded_ood", "kinase_strict_full", "kinase"),
]


def _latest_run_root() -> Path | None:
    run_paths = sorted(
        glob.glob(str((ROOT / "runs/external_validation_blind_runs/external_validation_blind_runs_*").resolve())),
        key=os.path.getmtime,
        reverse=True,
    )
    for run_path in run_paths:
        state_path = Path(run_path) / "state.json"
        if not state_path.exists():
            continue
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if str(state.get("protocol_id", "")).strip() == "cross_family_locked_decoy_shadow_v1":
            return Path(run_path).resolve()
    return None


def _run_tag(run_root: Path) -> str:
    prefix = "external_validation_blind_runs_"
    name = run_root.name
    return name[len(prefix) :] if name.startswith(prefix) else name


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _parse_dt(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return dt.datetime.fromisoformat(value)
    except Exception:
        return None


def _human_duration(seconds: float | None) -> str:
    return _ui_human_duration(seconds, include_days=False)


def _style(enabled: bool, text: str, *codes: str) -> str:
    return _ui_style(enabled, text, *codes)


def _progress_bar(done: int, total: int, *, width: int = 24, color: bool = False, bar_color: str = CYAN) -> str:
    return _ui_progress_bar(done, total, width=width, color=color, bar_color=bar_color)


def _shorten(text: str, limit: int = 40) -> str:
    return _ui_shorten(text, limit=limit)


def _task_brief(task_id: str) -> str:
    mapping = {
        "ion_trpv1_chembl20_full": "trpv1_20",
        "ion_trpv1_chembl50_full": "trpv1_50",
        "kinase_core_full": "kin_core",
        "kinase_strict_full": "kin_strict",
    }
    return mapping.get(task_id, task_id)


def _task_paths(tag: str, set_id: str, task_id: str) -> dict[str, Path]:
    base = ROOT / f"runs/external_validation_{tag}_{set_id}_{task_id}"
    return {
        "summary": Path(f"{base}_summary.json"),
        "state": Path(f"{base}_state.json"),
        "traj_progress": Path(f"{base}_p0_n10000_r1_stage2_traj_progress.json"),
        "ranking_summary": Path(f"{base}_p0_n10000_r1_stage5_ranking_summary.json"),
    }


def _task_status(tag: str, set_id: str, task_id: str) -> dict[str, Any]:
    paths = _task_paths(tag, set_id, task_id)
    summary = _load_json(paths["summary"])
    if summary:
        generated = _parse_dt(summary.get("generated_at_local"))
        age = (dt.datetime.now(generated.tzinfo) - generated).total_seconds() if generated is not None else None
        ranking_summary = _load_json(paths["ranking_summary"]) or {}
        ranking_metrics = ranking_summary.get("metrics", {}) if isinstance(ranking_summary, dict) else {}
        if not isinstance(ranking_metrics, dict):
            ranking_metrics = {}
        pr_auc = summary.get("ranking_pr_auc")
        if pr_auc in (None, ""):
            pr_auc = ranking_summary.get("ranking_pr_auc")
        if pr_auc in (None, ""):
            pr_auc = ranking_metrics.get("pr_auc", "")
        ef1 = summary.get("ranking_ef1")
        if ef1 in (None, ""):
            ef1 = ranking_summary.get("ranking_ef1")
        if ef1 in (None, ""):
            ef1 = ranking_metrics.get("ef1", "")
        detail_bits = []
        if pr_auc != "":
            detail_bits.append(f"PR={pr_auc}")
        if ef1 != "":
            detail_bits.append(f"EF1={ef1}")
        return {
            "status": "PASS" if bool(summary.get("pass", False)) else "FAIL",
            "detail": " ".join(detail_bits) if detail_bits else "ok",
            "phase": "completed",
            "updated_age": _human_duration(age),
            "freshness": "done",
            "eta": "done",
        }
    progress = _load_json(paths["traj_progress"])
    if progress:
        ratio = progress.get("progress_ratio")
        processed = progress.get("processed_rows")
        total = progress.get("total_rows") or 10000
        updated = _parse_dt(progress.get("updated_at_local")) or _parse_dt(progress.get("generated_at_local"))
        age = (dt.datetime.now(updated.tzinfo) - updated).total_seconds() if updated is not None else None
        state = _load_json(paths["state"])
        started = None
        if isinstance(state, dict):
            started = _parse_dt(state.get("started_at"))
        eta_seconds = None
        if isinstance(ratio, (int, float)) and ratio > 0 and started is not None:
            elapsed = (dt.datetime.now(started.tzinfo) - started).total_seconds()
            if elapsed > 0:
                eta_seconds = elapsed * (1.0 - float(ratio)) / float(ratio)
        detail = f"{processed}/{total or 10000} rows"
        if isinstance(ratio, (int, float)):
            detail = f"{ratio*100:.1f}% | {detail}"
        return {
            "status": "RUN",
            "detail": detail,
            "phase": str(progress.get("phase", "") or "stage2_trajectory"),
            "updated_age": _human_duration(age),
            "freshness": "stale" if age is not None and age > STALE_SEC else "fresh",
            "eta": _human_duration(eta_seconds) if eta_seconds is not None else "estimating",
        }
    state = _load_json(paths["state"])
    if state and isinstance(state.get("current"), dict):
        current = state["current"]
        state_status = str(current.get("status", "")).strip()
        if state_status:
            started = _parse_dt(state.get("started_at"))
            eta_seconds = None
            planned_keys = state.get("planned_keys", []) if isinstance(state.get("planned_keys"), list) else []
            completed_keys = state.get("completed_keys", []) if isinstance(state.get("completed_keys"), list) else []
            if started is not None and completed_keys and len(planned_keys) > len(completed_keys):
                elapsed = (dt.datetime.now(started.tzinfo) - started).total_seconds()
                completed_runs = max(1, len(completed_keys))
                remaining_runs = max(0, len(planned_keys) - len(completed_keys))
                if elapsed > 0 and remaining_runs > 0:
                    eta_seconds = (elapsed / completed_runs) * remaining_runs
            detail = state_status
            run_key = str(current.get("run_key", "")).strip()
            if planned_keys:
                detail = f"subruns {len(completed_keys)}/{len(planned_keys)}"
                if run_key:
                    detail = f"{detail} | current={run_key}"
            return {
                "status": "RUN" if "running" in state_status else "PEND",
                "detail": detail,
                "phase": state_status,
                "updated_age": "",
                "freshness": "unknown",
                "eta": _human_duration(eta_seconds) if eta_seconds is not None else "",
            }
    return {"status": "PEND", "detail": "", "phase": "pending", "updated_age": "", "freshness": "idle", "eta": ""}


def _proc_lines() -> list[str]:
    try:
        out = subprocess.check_output(
            [
                "bash",
                "-lc",
                "pgrep -af 'run_external_validation_blind_sets.py --set-spec-json runs/cross_family_locked_decoy_shadow_current/specs/cross_family_locked_decoy_shadow_current_v1.json|run_ligand_stress_validation.py --profile-json .*(crossfamshadow1)|run_ligand_htvs_pipeline.py --run-scope full --date-tag 2026-03-25_r1'",
            ],
            text=True,
        )
    except subprocess.CalledProcessError:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def _active_process_line(proc_lines: list[str]) -> str:
    for line in proc_lines:
        if "run_ligand_stress_validation.py" in line:
            return line
    return proc_lines[0] if proc_lines else ""


def _active_task_id(proc_lines: list[str]) -> str:
    line = _active_process_line(proc_lines)
    if "trpv1_chembl20" in line:
        return "ion_trpv1_chembl20_full"
    if "trpv1_chembl50" in line:
        return "ion_trpv1_chembl50_full"
    if "no_leak_v3_gatefix1_crossfamshadow1" in line:
        return "kinase_core_full"
    if "disjoint_strict_v3_gatefix1_crossfamshadow1" in line:
        return "kinase_strict_full"
    return ""


def _set_rows(task_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for set_id in ["set1_core_blind", "set2_expanded_ood"]:
        items = [row for row in task_rows if row["set_id"] == set_id]
        done = sum(1 for row in items if row["status"] in {"PASS", "FAIL"})
        failed = sum(1 for row in items if row["status"] == "FAIL")
        running = any(row["status"] == "RUN" for row in items)
        remaining = sum(1 for row in items if row["status"] not in {"PASS", "FAIL"})
        label = "PASS" if done == len(items) and failed == 0 else ("FAIL" if failed else ("RUN" if running else "PEND"))
        rows.append({"set_id": set_id, "done": done, "total": len(items), "label": label, "remaining": remaining})
    return rows


def _render(run_root: Path, *, color: bool = False) -> str:
    state = _load_json(run_root / "state.json") or {}
    tag = _run_tag(run_root)
    proc_lines = _proc_lines()
    active_line = _active_process_line(proc_lines)
    active_task = _active_task_id(proc_lines)
    task_rows = []
    for set_id, task_id, family in TASK_ORDER:
        info = _task_status(tag, set_id, task_id)
        task_rows.append({"set_id": set_id, "task_id": task_id, "family": family, **info})
    set_rows = _set_rows(task_rows)
    completed_tasks = sum(1 for row in task_rows if row["status"] in {"PASS", "FAIL"})
    remaining_tasks = len(task_rows) - completed_tasks
    active_task_row = next((row for row in task_rows if row["task_id"] == active_task), None)
    active_task_eta = active_task_row.get("eta", "") if active_task_row else ""
    status = str(state.get("status", "unknown")).strip().lower()
    status_color = CYAN if status == "running" else (GREEN if status == "completed" else YELLOW)
    done_sets = sum(1 for row in set_rows if row["done"] == row["total"])
    proc_roles = []
    for line in proc_lines:
        if "run_external_validation_blind_sets.py" in line and "wrapper" not in proc_roles:
            proc_roles.append("wrapper")
        if "run_ligand_stress_validation.py" in line and "stress" not in proc_roles:
            proc_roles.append("stress")
        if "run_ligand_htvs_pipeline.py" in line and "htvs" not in proc_roles:
            proc_roles.append("htvs")
        if "generate_ligand_trajectory_engine.py" in line and "traj" not in proc_roles:
            proc_roles.append("traj")
    roles_text = ",".join(proc_roles) if proc_roles else "-"

    lines = [
        _style(color, "=" * 88, CYAN),
        _style(color, "CROSSFAM SHADOW", BOLD, CYAN) + "  " + _style(color, status.upper(), BOLD, status_color),
        f"tag {tag} | task {_style(color, _task_brief(active_task) if active_task else 'none', BOLD, YELLOW if active_task else DIM)} | eta {_style(color, active_task_eta or '-', YELLOW)}",
        f"done {completed_tasks}/{len(task_rows)} | rem {remaining_tasks} | actors {len(proc_lines)} [{_style(color, roles_text, GREEN if proc_roles else DIM)}]",
        f"tasks {_progress_bar(completed_tasks, len(task_rows), color=color, bar_color=CYAN)} {completed_tasks}/{len(task_rows)} | sets {_progress_bar(done_sets, len(set_rows), color=color, bar_color=BLUE)} {done_sets}/{len(set_rows)}",
        _style(color, "-" * 88, GRAY),
        _style(color, "sets", BOLD),
    ]
    for row in set_rows:
        label_color = GREEN if row["label"] == "PASS" else (RED if row["label"] == "FAIL" else (CYAN if row["label"] == "RUN" else GRAY))
        lines.append(f"- {row['set_id']}: {_style(color, row['label'], BOLD, label_color)}  {row['done']}/{row['total']}  rem={row['remaining']}")
    lines.extend([
        _style(color, "-" * 88, GRAY),
        _style(color, "tasks", BOLD),
    ])
    for row in task_rows:
        row_status = str(row["status"]).strip().upper()
        row_color = GREEN if row_status == "PASS" else (RED if row_status == "FAIL" else (CYAN if row_status == "RUN" else GRAY))
        freshness = str(row.get("freshness", "")).strip()
        freshness_color = GREEN if freshness == "done" else (RED if freshness == "stale" else (CYAN if freshness == "fresh" else GRAY))
        detail = _shorten(row.get("detail", "") or "-", 48)
        lines.append(
            f"- {_style(color, row_status, BOLD, row_color)}  {_task_brief(row['task_id'])} [{row['family']}]"
            f"  {_style(color, freshness or '-', BOLD if freshness in {'fresh','stale','done'} else DIM, freshness_color)}"
            f"  {row.get('phase','-') or '-'}  eta={row.get('eta','-') or '-'}  {detail}"
        )
    if active_line:
        lines.extend([
            _style(color, "-" * 88, GRAY),
            _style(color, "pulse", BOLD),
            _shorten(active_line, 84),
        ])
    lines.append(_style(color, "=" * 88, CYAN))
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Monitor the cross-family locked-decoy shadow run.")
    p.add_argument("--run-root", default="")
    p.add_argument("--loop", action="store_true")
    p.add_argument("--interval-sec", type=float, default=5.0)
    p.add_argument("--clear-screen", action="store_true")
    p.add_argument("--color", action="store_true")
    p.add_argument("--no-color", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    run_root = Path(args.run_root).resolve() if args.run_root else _latest_run_root()
    if run_root is None:
        raise SystemExit("No cross-family locked-decoy shadow run found.")
    use_color = True
    if args.no_color:
        use_color = False
    elif args.color:
        use_color = True
    while True:
        text = _render(run_root, color=use_color)
        if args.clear_screen:
            sys.stdout.write("\033[2J\033[H")
        sys.stdout.write(text)
        sys.stdout.flush()
        if not args.loop:
            break
        time.sleep(max(0.5, float(args.interval_sec)))


if __name__ == "__main__":
    main()
