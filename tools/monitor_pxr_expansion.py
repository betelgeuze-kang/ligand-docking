#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import run_pxr_expansion_scaffold_check as scaffold

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

DEFAULT_TEMPLATE_JSON = "config/external_validation_biorxiv_nuclear_receptor_pxr_v1_template.json"
DEFAULT_BOOTSTRAP_JSON = "runs/pxr_runnable_packet_bootstrap_current.json"
DEFAULT_PENDING_PACKET_JSON = "runs/pxr_pending_resolution_packet_current.json"


TASK_ORDER = [
    ("set1_core_blind", "nuclear_receptor_pxr_core_full"),
    ("set2_expanded_ood", "nuclear_receptor_pxr_chembl50_full"),
    ("set3_operational_smoke", "nuclear_receptor_pxr_smoke"),
]


def _style(enabled: bool, text: str, *codes: str) -> str:
    if not enabled or not codes:
        return text
    return "".join(codes) + text + RESET


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_repo_path(path_like: str | os.PathLike[str] | None) -> Path | None:
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


def _proc_lines(pattern: str) -> list[str]:
    if not pattern.strip():
        return []
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
        if "monitor_pxr_expansion.py" in line:
            continue
        rows.append(line)
    return rows


def _shorten(text: str, limit: int = 120) -> str:
    text = str(text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _auto_find_run_root() -> Path | None:
    base = ROOT / "runs" / "external_validation_blind_runs"
    if not base.exists():
        return None
    candidates = sorted(base.glob("external_validation_blind_runs_*pxr*"), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    return candidates[0].resolve() if candidates else None


def _bootstrap_step_map(bootstrap: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = bootstrap.get("workbook_rows") or []
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, dict):
            step_id = str(row.get("step_id", "")).strip()
            if step_id:
                out[step_id] = row
    return out


def _step_ready(step: dict[str, Any] | None) -> bool:
    if not step:
        return False
    status = str(step.get("status", "")).strip().lower()
    if status in {"ready", "packet_ready", "ready_for_packet", "frozen", "complete", "complete_ready"}:
        return True
    placeholder_count = int(step.get("placeholder_row_count") or 0)
    zero_pocket_count = int(step.get("zero_pocket_row_count") or 0)
    return status not in {"template_only", "scaffold_only", "blocked"} and placeholder_count == 0 and zero_pocket_count == 0


def _set_readiness(bootstrap: dict[str, Any]) -> dict[str, dict[str, Any]]:
    summary = bootstrap.get("summary") or {}
    steps = _bootstrap_step_map(bootstrap)
    target_ready = _step_ready(steps.get("pxr_target_packet")) and _step_ready(steps.get("pxr_target_metadata"))
    fit_ready = bool(summary.get("fit_donor_policy_frozen"))
    core_ready = target_ready and bool(summary.get("core_packet_ready")) and fit_ready
    ood_ready = target_ready and bool(summary.get("ood_packet_ready")) and fit_ready
    smoke_ready = target_ready and bool(summary.get("core_packet_ready")) and fit_ready

    def blockers(*items: tuple[str, bool]) -> str:
        missing = [label for label, ok in items if not ok]
        return ", ".join(missing) if missing else "ready"

    return {
        "set1_core_blind": {
            "ready": core_ready,
            "state": "ready" if core_ready else "blocked",
            "blockers": blockers(("target_packet", target_ready), ("core_packet", bool(summary.get("core_packet_ready"))), ("fit_donor_policy", fit_ready)),
        },
        "set2_expanded_ood": {
            "ready": ood_ready,
            "state": "ready" if ood_ready else "blocked",
            "blockers": blockers(("target_packet", target_ready), ("ood_packet", bool(summary.get("ood_packet_ready"))), ("fit_donor_policy", fit_ready)),
        },
        "set3_operational_smoke": {
            "ready": smoke_ready,
            "state": "ready" if smoke_ready else "blocked",
            "blockers": blockers(("target_packet", target_ready), ("core_packet", bool(summary.get("core_packet_ready"))), ("fit_donor_policy", fit_ready)),
        },
    }


def _load_run_summary(run_root: Path | None) -> dict[str, Any]:
    if run_root is None:
        return {}
    for name in ["summary.json", "state.json"]:
        path = run_root / name
        if path.exists():
            return _read_json(path)
    return {}


def _collect_completed_tasks(run_summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    completed: dict[str, dict[str, Any]] = {}
    for set_row in run_summary.get("sets", []) or []:
        for task in set_row.get("tasks", []) or []:
            task_id = str(task.get("task_id", "")).strip()
            if task_id:
                completed[task_id] = task
    return completed


def _extract_active_task_id(run_summary: dict[str, Any], proc_lines: list[str]) -> str:
    for key in ["current_task_id", "active_task_id"]:
        value = str(run_summary.get(key, "")).strip()
        if value:
            return value
    current_task = run_summary.get("current_task")
    if isinstance(current_task, dict):
        value = str(current_task.get("task_id", "")).strip()
        if value:
            return value
    for line in proc_lines:
        for _, task_id in TASK_ORDER:
            if task_id in line:
                return task_id
        for suffix in ["pxr-core-full", "pxr-chembl50-full", "pxr-smoke"]:
            if suffix in line:
                if suffix == "pxr-core-full":
                    return "nuclear_receptor_pxr_core_full"
                if suffix == "pxr-chembl50-full":
                    return "nuclear_receptor_pxr_chembl50_full"
                if suffix == "pxr-smoke":
                    return "nuclear_receptor_pxr_smoke"
    return ""


def _classify_run_status(run_root: Path | None, run_summary: dict[str, Any], proc_lines: list[str]) -> tuple[str, str]:
    if run_root is None:
        return "scaffold_only", MAGENTA
    status = str(run_summary.get("status", "")).strip().lower()
    if status == "completed":
        return "completed", GREEN
    if proc_lines:
        return "running", CYAN
    if run_root.exists():
        updated = _parse_dt(run_summary.get("updated_at_local") or run_summary.get("generated_at_local"))
        if updated is not None:
            age = (dt.datetime.now(updated.tzinfo) - updated).total_seconds()
            if age > 900:
                return "stale", YELLOW
        return "stopped", RED
    return "not_started", GRAY


def _task_rows(template: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for set_row in template.get("sets", []) or []:
        set_id = str(set_row.get("set_id", "")).strip()
        title = str(set_row.get("title", "")).strip()
        for task in set_row.get("tasks", []) or []:
            row = dict(task)
            row["set_id"] = set_id
            row["set_title"] = title
            rows.append(row)
    return rows


def _task_board(template: dict[str, Any], bootstrap: dict[str, Any], run_summary: dict[str, Any], proc_lines: list[str]) -> list[dict[str, Any]]:
    readiness = _set_readiness(bootstrap)
    completed = _collect_completed_tasks(run_summary)
    active_task_id = _extract_active_task_id(run_summary, proc_lines)
    out: list[dict[str, Any]] = []
    for row in _task_rows(template):
        set_id = str(row.get("set_id", "")).strip()
        task_id = str(row.get("task_id", "")).strip()
        base = readiness.get(set_id, {"ready": False, "state": "blocked", "blockers": "unknown"})
        state = base["state"]
        detail = f"blocked_by={base['blockers']}" if state == "blocked" else "launch_ready"
        metrics = {}
        if task_id in completed:
            task = completed[task_id]
            state = "pass" if task.get("pass") is True else "fail"
            metrics = task.get("metrics") or {}
            pr = metrics.get("ranking_pr_auc")
            ef1 = metrics.get("ranking_ef1")
            pieces = []
            if pr is not None:
                pieces.append(f"PR={float(pr):.4f}")
            if ef1 is not None:
                pieces.append(f"EF1={float(ef1):.2f}")
            detail = "  ".join(pieces) if pieces else detail
        elif active_task_id and active_task_id == task_id:
            state = "running"
            detail = "active"
        out.append({
            "set_id": set_id,
            "set_title": row.get("set_title", ""),
            "task_id": task_id,
            "ligand_sizes": row.get("ligand_sizes", ""),
            "state": state,
            "detail": detail,
            "profile_json": row.get("profile_json", ""),
        })
    return out


def _state_color(state: str) -> str:
    return {
        "pass": GREEN,
        "fail": RED,
        "running": CYAN,
        "ready": BLUE,
        "blocked": YELLOW,
    }.get(state, GRAY)


def _fmt_bool(value: Any) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return "n/a"


def _render(args: argparse.Namespace) -> str:
    template_path = _resolve_repo_path(args.template_json)
    bootstrap_path = _resolve_repo_path(args.bootstrap_json)
    pending_packet_path = _resolve_repo_path(getattr(args, "pending_packet_json", DEFAULT_PENDING_PACKET_JSON))
    run_root = _resolve_repo_path(args.run_root) if args.run_root else _auto_find_run_root()

    template = _read_json(template_path) if template_path and template_path.exists() else {}
    bootstrap = _read_json(bootstrap_path) if bootstrap_path and bootstrap_path.exists() else {}
    pending_packet = _read_json(pending_packet_path) if pending_packet_path and pending_packet_path.exists() else {}
    scaffold_payload = (
        scaffold._build_payload(scaffold.ROOT, template_json=args.template_json)  # pyright: ignore[reportPrivateUsage]
        if template
        else {"pass": False, "summary": {"total_checks": 0, "passed_checks": 0, "failed_checks": 0}}
    )
    run_summary = _load_run_summary(run_root)
    proc_pattern = run_root.name if run_root is not None else "pxr"
    proc_lines = _proc_lines(proc_pattern)
    status, status_color = _classify_run_status(run_root, run_summary, proc_lines)
    board = _task_board(template, bootstrap, run_summary, proc_lines) if template and bootstrap else []
    bsum = bootstrap.get("summary") or {}
    ssum = scaffold_payload.get("summary") or {}
    if status == "scaffold_only" and int(bsum.get("curated_freeze_row_count", 0) or 0) > 0:
        status, status_color = "partial_curated_prelaunch", BLUE

    lines: list[str] = []
    lines.append(_style(args.color, "PXR Expansion Monitor", BOLD))
    lines.append(f"status: {_style(args.color, status, status_color, BOLD)}")
    lines.append(f"template_json: {args.template_json}")
    lines.append(f"bootstrap_json: {args.bootstrap_json}")
    lines.append(f"run_root: {run_root if run_root is not None else '(none yet)'}")
    lines.append("")

    if template:
        primary = template.get("primary_candidate") or {}
        lines.append(_style(args.color, "Protocol", BOLD, BLUE))
        lines.append(f"protocol_id: {template.get('protocol_id', '')}")
        lines.append(f"template_status: {template.get('status', '')}")
        lines.append(f"primary_target: {primary.get('target', '')}")
        lines.append(f"native_pdb_path: {_shorten(str(primary.get('native_pdb_path', '')), 110)}")
        lines.append("")

    lines.append(_style(args.color, "Scaffold Check", BOLD, BLUE))
    if "total_checks" in ssum:
        lines.append(
            f"checks: {ssum.get('passed_checks', 0)}/{ssum.get('total_checks', 0)} passed  failed={ssum.get('failed_checks', 0)}  pass={_fmt_bool(scaffold_payload.get('pass'))}"
        )
    else:
        lines.append(
            "artifacts: "
            f"current={ssum.get('current_required_artifact_exists_count', 0)}/{ssum.get('current_required_artifact_count', 0)}  "
            f"deferred={ssum.get('deferred_artifact_exists_count', 0)}/{ssum.get('deferred_artifact_count', 0)}  "
            f"errors={ssum.get('error_count', 0)}  warnings={ssum.get('warning_count', 0)}  "
            f"pass={_fmt_bool(ssum.get('pass', scaffold_payload.get('pass')))}"
        )
    failed_checks = [row for row in scaffold_payload.get("checks", []) if not row.get("ok")]
    for row in failed_checks[:5]:
        lines.append(f"- {_shorten(str(row.get('check_id', '')), 48)}  {_shorten(str(row.get('detail', '')), 110)}")
    lines.append("")

    lines.append(_style(args.color, "Runnable Packet Bootstrap", BOLD, BLUE))
    lines.append(
        "summary: "
        f"ready_rows={bsum.get('ready_row_count', 0)}  blocked_rows={bsum.get('blocked_row_count', 0)}  "
        f"core_packet_ready={_fmt_bool(bsum.get('core_packet_ready'))}  "
        f"ood_packet_ready={_fmt_bool(bsum.get('ood_packet_ready'))}  "
        f"fit_donor_policy_frozen={_fmt_bool(bsum.get('fit_donor_policy_frozen'))}"
    )
    if "curated_freeze_row_count" in bsum:
        lines.append(
            "curated_freeze: "
            f"ready_rows={bsum.get('curated_freeze_row_count', 0)}  "
            f"blocked_rows={bsum.get('curated_freeze_blocked_row_count', 0)}  "
            f"partial_claim_support_ready={_fmt_bool(bsum.get('partial_claim_support_ready'))}"
        )
    lines.append(f"runnable_before_data: {_fmt_bool(bsum.get('runnable_before_data'))}")
    if bsum.get("next_required_step"):
        lines.append(f"next_required_step: {_shorten(str(bsum.get('next_required_step')), 140)}")
    lines.append("")

    pending_summary = dict(pending_packet.get("summary", {}) or {})
    lines.append(_style(args.color, "Pending Resolution", BOLD, BLUE))
    if pending_summary:
        lines.append(
            "rows: "
            f"unresolved={pending_summary.get('pending_resolution_row_count', 0)}  "
            f"review_only={pending_summary.get('review_only_row_count', 0)}  "
            f"defer={pending_summary.get('defer_row_count', 0)}  "
            f"binder_gap={pending_summary.get('binder_gap_count', 0)}"
        )
        if pending_summary.get("next_required_step"):
            lines.append(f"next_required_step: {_shorten(str(pending_summary.get('next_required_step')), 140)}")
    else:
        lines.append("rows: unresolved packet not available yet")
    lines.append("")

    lines.append(_style(args.color, "Set Board", BOLD, BLUE))
    for row in board:
        state = str(row.get("state", ""))
        state_text = _style(args.color, state.upper(), _state_color(state), BOLD)
        lines.append(
            f"- {row.get('set_id', '')}: {state_text}  task={row.get('task_id', '')}  n={row.get('ligand_sizes', '')}  {row.get('detail', '')}"
        )
    if not board:
        lines.append("- no PXR task board available yet")
    lines.append("")

    lines.append(_style(args.color, "Processes", BOLD, BLUE))
    if proc_lines:
        lines.append(f"live_process_count: {len(proc_lines)}")
        for line in proc_lines[:8]:
            lines.append(f"- {_shorten(line, 160)}")
    else:
        lines.append("live_process_count: 0")
        lines.append("- no active PXR run process detected")
    lines.append("")

    lines.append(_style(args.color, "Commands", BOLD, BLUE))
    lines.append(
        "scaffold_check: python3 tools/run_pxr_expansion_scaffold_check.py --template-json "
        f"{args.template_json} --verbose"
    )
    lines.append(
        "monitor: python3 tools/monitor_pxr_expansion.py --template-json "
        f"{args.template_json} --bootstrap-json {args.bootstrap_json} --loop --interval-sec 5 --clear-screen --color"
    )
    lines.append("freeze_helper: python3 tools/build_pxr_curated_packet_freeze.py")
    if run_root is not None:
        lines.append(
            "3set_monitor: python3 tools/monitor_biorxiv_external_validation.py --run-root "
            f"{run_root} --loop --interval-sec 5 --clear-screen --color"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Monitor PXR scaffold/bootstrap readiness and future 3-set PXR runs in one view.")
    ap.add_argument("--template-json", default=DEFAULT_TEMPLATE_JSON)
    ap.add_argument("--bootstrap-json", default=DEFAULT_BOOTSTRAP_JSON)
    ap.add_argument("--pending-packet-json", default=DEFAULT_PENDING_PACKET_JSON)
    ap.add_argument("--run-root", default="")
    ap.add_argument("--loop", action=argparse.BooleanOptionalAction, default=False)
    ap.add_argument("--interval-sec", type=float, default=5.0)
    ap.add_argument("--clear-screen", action=argparse.BooleanOptionalAction, default=False)
    ap.add_argument("--color", action=argparse.BooleanOptionalAction, default=False)
    args = ap.parse_args(argv)

    while True:
        if args.clear_screen:
            print("\033[2J\033[H", end="")
        print(_render(args))
        if not args.loop:
            return 0
        time.sleep(max(0.2, float(args.interval_sec)))


if __name__ == "__main__":
    raise SystemExit(main())
