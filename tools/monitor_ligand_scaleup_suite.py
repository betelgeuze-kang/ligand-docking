#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import shlex
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
CYAN = "\033[36m"
GRAY = "\033[90m"


def _style(enabled: bool, text: str, *codes: str) -> str:
    if not enabled or not codes:
        return text
    return "".join(codes) + text + RESET


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


def _resolve_repo_path(path_str: str) -> Path:
    path = Path(path_str)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


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
        if "monitor_ligand_scaleup_suite.py" in line:
            continue
        rows.append(line)
    return rows


def _extract_arg(cmdline: str, flag: str) -> str:
    try:
        parts = shlex.split(cmdline)
    except Exception:
        parts = cmdline.split()
    for idx, part in enumerate(parts):
        if part == flag and idx + 1 < len(parts):
            return parts[idx + 1]
    return ""


def _load_json_if_exists(path_str: str) -> dict[str, Any]:
    if not path_str:
        return {}
    path = _resolve_repo_path(path_str)
    if not path.exists():
        return {}
    return _read_json(path)


def _safe_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _stage_plan_map(suite_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = suite_payload.get("stages")
    if not isinstance(rows, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        stage_id = str(row.get("stage_id", "")).strip()
        if stage_id:
            out[stage_id] = row
    return out


def _stage_result_map(suite_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = suite_payload.get("stage_results")
    if not isinstance(rows, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        stage_id = str(row.get("stage_id", "")).strip()
        if stage_id:
            out[stage_id] = row
    return out


def _stage_refresh_map(suite_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = suite_payload.get("suite_status_refreshes")
    if not isinstance(rows, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        stage_id = str(row.get("stage_id", "")).strip()
        if stage_id:
            out[stage_id] = row
    return out


def _load_run_summary(run_root: Path | None) -> dict[str, Any]:
    if run_root is None:
        return {}
    summary_json = run_root / "summary.json"
    if summary_json.exists():
        return _read_json(summary_json)
    state_json = run_root / "state.json"
    if state_json.exists():
        return _read_json(state_json)
    return {}


def _infer_run_root(*payloads: dict[str, Any], explicit_run_root: str = "") -> Path | None:
    if explicit_run_root.strip():
        return _resolve_repo_path(explicit_run_root.strip())
    for payload in payloads:
        for key in ("candidate_run_root", "run_root"):
            value = str(payload.get(key, "")).strip()
            if value:
                return _resolve_repo_path(value)
    return None


def _benchmark_matches_stage(stage_id: str, payload: dict[str, Any]) -> bool:
    if not payload:
        return False
    kind = str(payload.get("comparison_kind", "")).strip()
    inputs = payload.get("input_artifacts") or {}
    if stage_id == "speedpack_ab":
        return kind == "equal_size_speedpack_ab" or bool(inputs.get("ab_json"))
    pilot_json = str(inputs.get("pilot_json", "")).strip().lower()
    if stage_id == "pilot_100k":
        return "100k" in pilot_json
    if stage_id == "pilot_1m":
        return "1m" in pilot_json
    return False


def _refresh_status_text(current_payload: dict[str, Any], benchmark_payload: dict[str, Any], stage_summary: dict[str, Any]) -> str:
    if benchmark_payload or stage_summary:
        return "summary_attached"
    refresh = current_payload.get("post_run_refresh")
    if isinstance(refresh, dict) and bool(refresh.get("attempted", False)):
        return "refresh_ok" if bool(refresh.get("ok", False)) else "refresh_failed"
    if isinstance(refresh, dict) and ("enabled" in refresh):
        return "refresh_planned" if bool(refresh.get("enabled", False)) else "refresh_disabled"
    return "missing"


def _readiness_payload(*payloads: dict[str, Any]) -> dict[str, Any]:
    for payload in payloads:
        readiness = payload.get("launch_readiness")
        if isinstance(readiness, dict) and readiness:
            return readiness
    return {}


def _coerce_now(now: dt.datetime, reference: dt.datetime) -> dt.datetime:
    if reference.tzinfo is not None and now.tzinfo is None:
        return now.replace(tzinfo=reference.tzinfo)
    if reference.tzinfo is None and now.tzinfo is not None:
        return now.replace(tzinfo=None)
    return now


def _classify_live_status(run_summary: dict[str, Any], proc_lines: list[str]) -> tuple[str, str]:
    status = str(run_summary.get("status", "")).strip().lower()
    if status == "completed":
        return "completed", GREEN
    if proc_lines:
        return "running", CYAN
    updated = _parse_dt(run_summary.get("updated_at_local"))
    if status == "running" and updated is not None:
        age = (_coerce_now(dt.datetime.now(updated.tzinfo), updated) - updated).total_seconds()
        if age > 900:
            return "stale", YELLOW
        return "stopped", RED
    if status:
        return status, YELLOW
    return "unknown", GRAY


def _stage_stage_text(
    *,
    stage_id: str,
    readiness: dict[str, Any],
    current_payload: dict[str, Any],
    benchmark_summary: dict[str, Any],
    stage_summary: dict[str, Any],
    run_summary: dict[str, Any],
    proc_lines: list[str],
) -> tuple[str, str]:
    if benchmark_summary:
        if bool(benchmark_summary.get("comparison_artifact_ready", False)):
            return "comparison_ready", GREEN
        benchmark_stage = str(benchmark_summary.get("benchmark_stage", "")).strip()
        if benchmark_stage:
            return benchmark_stage, CYAN
    if current_payload:
        refresh = current_payload.get("post_run_refresh")
        if isinstance(refresh, dict) and bool(refresh.get("attempted", False)):
            if bool(refresh.get("ok", False)):
                return "post_run_refreshed", GREEN
            return "post_run_refresh_failed", YELLOW
        if bool(current_payload.get("ok")) and str(current_payload.get("candidate_run_root", "")).strip():
            if bool(current_payload.get("comparison_skipped", False)):
                return "post_run_no_compare", CYAN
            return "post_run_partial", CYAN
    if run_summary:
        return _classify_live_status(run_summary, proc_lines)
    if readiness:
        if bool(readiness.get("ready", False)):
            return "prelaunch_ready", CYAN
        return "blocked_prelaunch", YELLOW
    if stage_summary:
        benchmark_stage = str(stage_summary.get("benchmark_stage", "")).strip()
        if benchmark_stage:
            return benchmark_stage, CYAN
        return "scaffold_only", GRAY
    return "not_launched", GRAY


def _stage_proc_lines(stage_id: str, all_proc_lines: list[str], run_root: Path | None) -> list[str]:
    hints = {
        "speedpack_ab": ("run_ligand_speedpack_ab_current.py",),
        "pilot_100k": ("run_ligand_scaleup_100k_pilot_current.py",),
        "pilot_1m": ("run_ligand_scaleup_1m_pilot_current.py",),
    }
    rows: list[str] = []
    run_root_str = str(run_root) if run_root is not None else ""
    for line in all_proc_lines:
        if any(tok in line for tok in hints.get(stage_id, ())):
            rows.append(line)
            continue
        candidate = _extract_arg(line, "--run-root")
        if run_root_str and candidate and _resolve_repo_path(candidate) == run_root:
            rows.append(line)
    return rows


def _render_readiness(readiness: dict[str, Any]) -> str:
    if not readiness:
        return "unknown"
    status = str(readiness.get("status", "")).strip() or ("ready" if bool(readiness.get("ready", False)) else "blocked")
    count = int(readiness.get("blocking_issue_count", 0) or 0)
    if count > 0:
        return f"{status} ({count} blockers)"
    return status


def _benchmark_claim_text(payload: dict[str, Any]) -> str:
    if not payload:
        return "n/a"
    status = str(payload.get("claim_safe_status", "")).strip()
    if status:
        return status
    claim_safe = payload.get("claim_safe")
    if isinstance(claim_safe, bool):
        return "claim_safe" if claim_safe else "claim_not_safe"
    return "pending"


def _suite_runner_summary(suite_dryrun: dict[str, Any], suite_execute: dict[str, Any]) -> dict[str, Any]:
    latest = suite_execute or suite_dryrun
    return {
        "artifact_state": "missing" if (not suite_dryrun and not suite_execute) else ("present" if (suite_dryrun and suite_execute) else "partial"),
        "latest_kind": "execute" if suite_execute else ("dry_run" if suite_dryrun else "missing"),
        "latest_generated_at_local": str(latest.get("generated_at_local", "") or ""),
        "dry_run_present": bool(suite_dryrun),
        "execute_present": bool(suite_execute),
        "dry_run_enabled_stage_count": int(suite_dryrun.get("enabled_stage_count", 0) or 0) if suite_dryrun else 0,
        "execute_completed_stage_count": int(suite_execute.get("completed_stage_count", 0) or 0) if suite_execute else 0,
        "execute_ok": _safe_bool(suite_execute.get("ok")) if suite_execute else None,
        "execute_failed_stage_id": str(suite_execute.get("failed_stage_id", "") or "") if suite_execute else "",
    }


def _comparison_text(stage_summary: dict[str, Any], benchmark_summary: dict[str, Any], readiness: dict[str, Any]) -> str:
    payload = benchmark_summary or stage_summary
    if payload:
        if bool(payload.get("comparison_artifact_ready", False)):
            return "ready"
        if "comparison_artifact_ready" in payload:
            return "pending"
    if readiness and bool(readiness.get("comparison_enabled", False)):
        return "planned"
    return "n/a"


def _run_age_text(run_summary: dict[str, Any]) -> str:
    updated = _parse_dt(run_summary.get("updated_at_local"))
    if updated is None:
        return "n/a"
    age = (_coerce_now(dt.datetime.now(updated.tzinfo), updated) - updated).total_seconds()
    return _human_duration(max(0.0, age))


def _make_stage_snapshot(
    *,
    stage_id: str,
    label: str,
    current_json: str = "",
    runtime_json: str = "",
    summary_json: str = "",
    dryrun_json: str = "",
    benchmark_summary_json: str = "",
    suite_stage_plan: dict[str, Any] | None = None,
    suite_stage_result: dict[str, Any] | None = None,
    suite_stage_refresh: dict[str, Any] | None = None,
    explicit_run_root: str = "",
    all_proc_lines: list[str],
) -> dict[str, Any]:
    suite_stage_plan = suite_stage_plan or {}
    suite_stage_result = suite_stage_result or {}
    suite_stage_refresh = suite_stage_refresh or {}
    current_payload = _load_json_if_exists(current_json)
    runtime_payload = _load_json_if_exists(runtime_json)
    summary_payload = _load_json_if_exists(summary_json)
    dryrun_payload = _load_json_if_exists(dryrun_json)
    benchmark_payload = _load_json_if_exists(benchmark_summary_json)
    if benchmark_payload and not _benchmark_matches_stage(stage_id, benchmark_payload):
        benchmark_payload = {}

    readiness = _readiness_payload(runtime_payload, current_payload, dryrun_payload)
    run_root = _infer_run_root(runtime_payload, current_payload, dryrun_payload, explicit_run_root=explicit_run_root)
    run_summary = _load_run_summary(run_root)
    proc_lines = _stage_proc_lines(stage_id, all_proc_lines, run_root)
    status, color = _stage_stage_text(
        stage_id=stage_id,
        readiness=readiness,
        current_payload=current_payload,
        benchmark_summary=benchmark_payload,
        stage_summary=summary_payload,
        run_summary=run_summary,
        proc_lines=proc_lines,
    )
    refresh_status = _refresh_status_text(current_payload, benchmark_payload, summary_payload)
    if refresh_status == "missing":
        refresh = suite_stage_result.get("suite_status_refresh")
        if isinstance(refresh, dict):
            ok = _safe_bool(refresh.get("ok"))
            if ok is not None:
                refresh_status = "refresh_ok" if ok else "refresh_failed"
        elif suite_stage_refresh:
            ok = _safe_bool(suite_stage_refresh.get("ok"))
            if ok is not None:
                refresh_status = "refresh_ok" if ok else "refresh_failed"
    summary_stage = str(summary_payload.get("benchmark_stage", "") or "").strip().lower()
    benchmark_stage = str(benchmark_payload.get("benchmark_stage", "") or "").strip().lower()
    if benchmark_payload and benchmark_stage.startswith("prelaunch"):
        progress_status = "prelaunch_scaffold"
    elif benchmark_payload:
        progress_status = "post_run_with_summary"
    elif summary_payload and summary_stage.startswith("prelaunch"):
        progress_status = "prelaunch_scaffold"
    elif bool(current_payload.get("ok")) and str(current_payload.get("candidate_run_root", "")).strip():
        progress_status = "post_run_partial"
    elif suite_stage_result:
        if _safe_bool(suite_stage_result.get("skipped")) is True:
            progress_status = "suite_execute_skipped"
        elif _safe_bool(suite_stage_result.get("ok")) is True:
            progress_status = "suite_execute_ok"
        else:
            progress_status = "suite_execute_failed"
    elif suite_stage_plan:
        progress_status = "suite_dry_run_planned" if _safe_bool(suite_stage_plan.get("enabled")) is not False else "suite_stage_disabled"
    else:
        progress_status = "prelaunch" if (current_payload or dryrun_payload or summary_payload) else "missing"

    if not current_payload and not runtime_payload and not summary_payload and not dryrun_payload:
        if suite_stage_result:
            if _safe_bool(suite_stage_result.get("skipped")) is True:
                status, color = "suite_execute_skipped", YELLOW
            elif _safe_bool(suite_stage_result.get("ok")) is True:
                status, color = "suite_execute_ok", GREEN
            else:
                status, color = "suite_execute_failed", RED
        elif suite_stage_plan:
            if _safe_bool(suite_stage_plan.get("enabled")) is False:
                status, color = "suite_stage_disabled", GRAY
            else:
                status, color = "suite_dry_run_planned", CYAN

    return {
        "stage_id": stage_id,
        "label": label,
        "status": status,
        "status_color": color,
        "progress_status": progress_status,
        "refresh_status": refresh_status,
        "readiness": _render_readiness(readiness),
        "comparison": _comparison_text(summary_payload, benchmark_payload, readiness),
        "claim_safe_status": _benchmark_claim_text(benchmark_payload or summary_payload),
        "run_root": str(run_root) if run_root is not None else "",
        "run_age": _run_age_text(run_summary),
        "artifacts_present": {
            "current": bool(current_payload),
            "runtime": bool(runtime_payload),
            "summary": bool(summary_payload),
            "dryrun": bool(dryrun_payload),
            "benchmark_summary": bool(benchmark_payload),
        },
        "notes": [
            note
            for note in [
                str((benchmark_payload or summary_payload).get("recommended_next_action", "")).strip(),
                str((benchmark_payload or summary_payload).get("benchmark_stage", "")).strip(),
                str(suite_stage_plan.get("note", "")).strip(),
                str(suite_stage_result.get("reason", "")).strip(),
            ]
            if note
        ],
    }


def build_suite_payload(args: argparse.Namespace) -> dict[str, Any]:
    suite_dryrun = _load_json_if_exists(getattr(args, "suite_dryrun_json", "runs/ligand_scaleup_suite_dryrun_current.json"))
    suite_execute = _load_json_if_exists(getattr(args, "suite_execute_json", "runs/ligand_scaleup_suite_current.json"))
    suite_stage_plans = _stage_plan_map(suite_dryrun)
    suite_stage_results = _stage_result_map(suite_execute)
    suite_stage_refreshes = _stage_refresh_map(suite_execute)
    pattern = (
        "run_ligand_scaleup_suite_current.py|run_ligand_speedpack_ab_current.py|"
        "run_ligand_scaleup_100k_pilot_current.py|run_ligand_scaleup_1m_pilot_current.py|"
        "run_external_validation_blind_sets.py|run_ligand_stress_validation.py|"
        "run_ligand_htvs_pipeline.py|generate_ligand_trajectory_engine.py"
    )
    all_proc_lines = _proc_lines(pattern)
    rows = [
        _make_stage_snapshot(
            stage_id="speedpack_ab",
            label="Speedpack A/B",
            current_json=args.ab_current_json,
            runtime_json=args.ab_runtime_json,
            summary_json=args.ab_summary_json,
            benchmark_summary_json=args.ab_summary_json,
            suite_stage_plan=suite_stage_plans.get("speedpack_ab", {}),
            suite_stage_result=suite_stage_results.get("speedpack_ab", {}),
            suite_stage_refresh=suite_stage_refreshes.get("speedpack_ab", {}),
            explicit_run_root=args.ab_run_root,
            all_proc_lines=all_proc_lines,
        ),
        _make_stage_snapshot(
            stage_id="pilot_100k",
            label="100k Pilot",
            current_json=args.pilot_100k_json,
            dryrun_json=args.pilot_100k_dryrun_json,
            benchmark_summary_json=args.benchmark_summary_json,
            suite_stage_plan=suite_stage_plans.get("pilot_100k", {}),
            suite_stage_result=suite_stage_results.get("pilot_100k", {}),
            suite_stage_refresh=suite_stage_refreshes.get("pilot_100k", {}),
            explicit_run_root=args.pilot_100k_run_root,
            all_proc_lines=all_proc_lines,
        ),
        _make_stage_snapshot(
            stage_id="pilot_1m",
            label="1M Pilot",
            current_json=args.pilot_1m_json,
            dryrun_json=args.pilot_1m_dryrun_json,
            benchmark_summary_json=args.benchmark_summary_json,
            suite_stage_plan=suite_stage_plans.get("pilot_1m", {}),
            suite_stage_result=suite_stage_results.get("pilot_1m", {}),
            suite_stage_refresh=suite_stage_refreshes.get("pilot_1m", {}),
            explicit_run_root=args.pilot_1m_run_root,
            all_proc_lines=all_proc_lines,
        ),
    ]
    status_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
    return {
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "suite_id": "ligand_scaleup_suite_monitor_current",
        "suite_runner": _suite_runner_summary(suite_dryrun, suite_execute),
        "status_counts": status_counts,
        "stage_count": len(rows),
        "stages": rows,
    }


def _render_table(payload: dict[str, Any], *, color: bool) -> str:
    lines = []
    suite_runner = payload.get("suite_runner") if isinstance(payload.get("suite_runner"), dict) else {}
    lines.append(_style(color, "Ligand Scale-up Suite Monitor", BOLD))
    lines.append(f"Generated: {payload.get('generated_at_local', '')}")
    lines.append(
        f"Suite runner: artifacts={suite_runner.get('artifact_state', 'missing')} | "
        f"latest={suite_runner.get('latest_kind', 'missing')} | "
        f"execute_ok={suite_runner.get('execute_ok', 'n/a')} | "
        f"enabled(dry-run)={suite_runner.get('dry_run_enabled_stage_count', 0)} | "
        f"completed(execute)={suite_runner.get('execute_completed_stage_count', 0)}"
    )
    failed_stage_id = str(suite_runner.get("execute_failed_stage_id", "") or "").strip()
    if failed_stage_id:
        lines.append(_style(color, f"Suite runner failed_stage_id: {failed_stage_id}", YELLOW))
    lines.append("")
    header = f"{'Stage':18} {'Status':22} {'Refresh':18} {'Comparison':12} {'Claim':38} {'Run Age':10}"
    lines.append(_style(color, header, DIM))
    for row in payload.get("stages", []):
        status = _style(color, str(row["status"]), row.get("status_color", GRAY))
        claim = str(row.get("claim_safe_status", "n/a"))
        lines.append(
            f"{str(row['label'])[:18]:18} "
            f"{status[:22] if False else status:22} "
            f"{str(row.get('refresh_status', 'n/a'))[:18]:18} "
            f"{str(row['comparison'])[:12]:12} "
            f"{claim[:38]:38} "
            f"{str(row['run_age'])[:10]:10}"
        )
        lines.append(_style(color, f"  progress: {row.get('progress_status', 'n/a')} | readiness: {row.get('readiness', 'n/a')}", DIM))
        run_root = str(row.get("run_root", "")).strip()
        if run_root:
            lines.append(_style(color, f"  run_root: {run_root}", DIM))
        for note in row.get("notes") or []:
            lines.append(_style(color, f"  note: {_truncate(note, 140)}", DIM))
    return "\n".join(lines)


def _truncate(text: str, limit: int = 140) -> str:
    text = str(text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Monitor suite-level commercialization scale-up readiness/status for A/B, 100k, and 1M.")
    ap.add_argument("--suite-dryrun-json", default="runs/ligand_scaleup_suite_dryrun_current.json")
    ap.add_argument("--suite-execute-json", default="runs/ligand_scaleup_suite_current.json")
    ap.add_argument("--ab-current-json", default="runs/ligand_speedpack_ab_current.json")
    ap.add_argument("--ab-runtime-json", default="runs/ligand_speedpack_ab_runtime_current.json")
    ap.add_argument("--ab-summary-json", default="runs/ligand_speedpack_ab_summary_current.json")
    ap.add_argument("--ab-run-root", default="")

    ap.add_argument("--pilot-100k-json", default="runs/ligand_scaleup_100k_pilot_current.json")
    ap.add_argument("--pilot-100k-dryrun-json", default="runs/ligand_scaleup_100k_pilot_dryrun_current.json")
    ap.add_argument("--pilot-100k-run-root", default="")

    ap.add_argument("--pilot-1m-json", default="runs/ligand_scaleup_1m_pilot_current.json")
    ap.add_argument("--pilot-1m-dryrun-json", default="runs/ligand_scaleup_1m_pilot_dryrun_current.json")
    ap.add_argument("--pilot-1m-run-root", default="")

    ap.add_argument("--benchmark-summary-json", default="runs/ligand_scaleup_benchmark_summary_current.json")
    ap.add_argument("--json", action=argparse.BooleanOptionalAction, default=False)
    ap.add_argument("--loop", action=argparse.BooleanOptionalAction, default=False)
    ap.add_argument("--interval-sec", type=float, default=5.0)
    ap.add_argument("--clear-screen", action=argparse.BooleanOptionalAction, default=False)
    ap.add_argument("--color", action=argparse.BooleanOptionalAction, default=False)
    args = ap.parse_args(argv)

    while True:
        payload = build_suite_payload(args)
        if args.clear_screen:
            print("\033[2J\033[H", end="")
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(_render_table(payload, color=bool(args.color)))
        if not args.loop:
            return 0
        time.sleep(max(0.5, float(args.interval_sec)))


if __name__ == "__main__":
    raise SystemExit(main())
