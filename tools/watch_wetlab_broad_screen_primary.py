#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import errno
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from tools import run_wetlab_broad_screen_runtime_event as primary_event
from tools.wetlab_target_render_utils import maybe_load_json, resolve, write_artifact

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_QUEUE_JSON = ROOT / "runs/wetlab_broad_screen_execution_queue_current.json"
DEFAULT_PROGRESS_JSON = ROOT / "runs/wetlab_broad_screen_progress_current.json"
DEFAULT_THROUGHPUT_BRIDGE_JSON = ROOT / "runs/wetlab_broad_screen_throughput_bridge_current.json"
DEFAULT_WATCHER_STATE_JSON = ROOT / "runs/wetlab_broad_screen_primary_watcher_state_current.json"
DEFAULT_OUT_MD = ROOT / "runs/wetlab_broad_screen_primary_watcher_current.md"
DEFAULT_RUNTIME_DIR = ROOT / "runs/wetlab_broad_screen_primary_watcher"
DEFAULT_HEARTBEAT_LAUNCHER = ROOT / "tools/launch_wetlab_broad_screen_heartbeat_loop.py"
DEFAULT_HEARTBEAT_PID = DEFAULT_RUNTIME_DIR / "heartbeat_loop.pid"
DEFAULT_HEARTBEAT_LOG = DEFAULT_RUNTIME_DIR / "heartbeat_loop.log"
DEFAULT_STAGE_LABEL = "broad_screen_primary_shard"
DEFAULT_STAGE_LABEL_TUNED = "broad_screen_primary_shard_tuned"
DEFAULT_STAGE_LABEL_TUNED_GATE51 = "broad_screen_primary_shard_tuned_gate51"
DEFAULT_STAGE_LABEL_TUNED_GATE55 = "broad_screen_primary_shard_tuned_gate55"
DEFAULT_PREFLIGHT_KIND_ORDER = [
    "throughput_preflight_tuned_gate51",
    "throughput_preflight_tuned_gate55",
    "throughput_preflight_tuned",
    "throughput_preflight",
]


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = resolve(str(path_like))
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = resolve(str(path_like))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _parse_ts(value: Any) -> dt.datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return dt.datetime.fromisoformat(text)
    except Exception:
        return None


def _now_text() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _target_slug(target_id: str) -> str:
    return (
        str(target_id or "")
        .lower()
        .replace(".", "")
        .replace("-", "_")
        .replace("/", "_")
        .replace("(", "")
        .replace(")", "")
        .replace(" ", "_")
    )


def _progress_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(row) for row in (payload.get("rows", []) or [])]


def _queue_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(row) for row in (payload.get("rows", []) or [])]


def _row_key(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("target_id", "")).strip(), str(row.get("shard_id", "")).strip())


def _queue_row_by_key(queue_payload: dict[str, Any], target_id: str, shard_id: str) -> dict[str, Any]:
    for row in _queue_rows(queue_payload):
        if _row_key(row) == (target_id, shard_id):
            return row
    return {}


def _active_or_focus_row(queue_payload: dict[str, Any], progress_payload: dict[str, Any]) -> dict[str, Any]:
    for progress_row in _progress_rows(progress_payload):
        if "running" in str(progress_row.get("queue_status", "")).strip():
            target_id, shard_id = _row_key(progress_row)
            return {
                "target_id": target_id,
                "shard_id": shard_id,
                "queue_row": _queue_row_by_key(queue_payload, target_id, shard_id),
                "progress_row": progress_row,
            }

    summary = dict(queue_payload.get("summary", {}) or {})
    target_id = str(summary.get("first_actionable_target_id", "")).strip()
    shard_id = str(summary.get("first_actionable_shard_id", "")).strip()
    if target_id and shard_id:
        return {
            "target_id": target_id,
            "shard_id": shard_id,
            "queue_row": _queue_row_by_key(queue_payload, target_id, shard_id),
            "progress_row": next(
                (row for row in _progress_rows(progress_payload) if _row_key(row) == (target_id, shard_id)),
                {},
            ),
        }
    return {"target_id": "", "shard_id": "", "queue_row": {}, "progress_row": {}}


def _first_ready_row(queue_payload: dict[str, Any]) -> dict[str, Any]:
    for row in _queue_rows(queue_payload):
        if str(row.get("queue_status", "")).strip().startswith("ready"):
            return row
    return {}


def _throughput_dir_for_row(active_row: dict[str, Any], throughput_bridge: dict[str, Any]) -> Path | None:
    target_id = str(active_row.get("target_id", "")).strip()
    shard_id = str(active_row.get("shard_id", "")).strip()
    if not target_id or not shard_id:
        return None

    summary = dict(throughput_bridge.get("summary", {}) or {})
    if (
        str(summary.get("target_id", "")).strip() == target_id
        and str(summary.get("shard_id", "")).strip() == shard_id
    ):
        structured = dict(throughput_bridge.get("structured", {}) or {})
        out_prefix = str(structured.get("out_prefix", "")).strip()
        if out_prefix:
            return resolve(out_prefix).parent

    return ROOT / "runs" / "wetlab_broad_screen_throughput" / _target_slug(target_id) / shard_id


def _is_final_summary_name(path: Path) -> bool:
    name = path.name
    return (
        name.startswith("throughput_run")
        and name.endswith("_summary.json")
        and "_stage" not in name
        and "_sla_" not in name
        and "_claim_split" not in name
    )


def _detect_compute_summary(
    throughput_dir: Path | None,
    *,
    prefer_token: str = "",
) -> dict[str, Any]:
    result = {
        "throughput_dir": str(throughput_dir) if throughput_dir else "",
        "summary_present": False,
        "summary_path": "",
        "summary_generated_at": "",
        "summary_pass": None,
        "summary_failed_stage": "",
        "stage2_progress_done": False,
        "stage2_progress_path": "",
        "stage3_summary_present": False,
        "stage3_summary_path": "",
    }
    if throughput_dir is None or not throughput_dir.exists():
        return result

    final_candidates: list[tuple[tuple[Any, ...], Path, dict[str, Any]]] = []
    for path in throughput_dir.glob("throughput_run*_summary.json"):
        if not _is_final_summary_name(path):
            continue
        payload = maybe_load_json(str(path))
        if not payload:
            continue
        stamp = _parse_ts(
            payload.get("generated_at_local")
            or payload.get("generated_at")
            or payload.get("completed_at")
            or payload.get("finished_at")
        )
        final_candidates.append(
            (
                (
                    1 if prefer_token and prefer_token in path.name else 0,
                    stamp or dt.datetime.min,
                    path.stat().st_mtime,
                ),
                path,
                payload,
            )
        )

    if final_candidates:
        _, path, payload = max(final_candidates, key=lambda item: item[0])
        result["summary_present"] = True
        result["summary_path"] = str(path)
        result["summary_generated_at"] = str(
            payload.get("generated_at_local")
            or payload.get("generated_at")
            or payload.get("completed_at")
            or payload.get("finished_at")
            or ""
        ).strip()
        result["summary_pass"] = payload.get("pass")
        result["summary_failed_stage"] = str(payload.get("failed_stage", "")).strip()

    stage2_candidates = sorted(throughput_dir.glob("throughput_run*_stage2_traj_progress.json"))
    if stage2_candidates:
        stage2_path = stage2_candidates[-1]
        stage2_payload = maybe_load_json(str(stage2_path))
        result["stage2_progress_path"] = str(stage2_path)
        result["stage2_progress_done"] = str(stage2_payload.get("status", "")).strip() == "done"

    stage3_candidates = sorted(throughput_dir.glob("throughput_run*_stage3_summary.json"))
    if stage3_candidates:
        result["stage3_summary_present"] = True
        result["stage3_summary_path"] = str(stage3_candidates[-1])

    return result


def _pid_is_running(pid: int) -> bool:
    if int(pid or 0) <= 0:
        return False
    try:
        os.kill(int(pid), 0)
    except OSError as exc:
        if exc.errno == errno.ESRCH:
            return False
        return True
    return True


def _matching_managed_run(state: dict[str, Any], target_id: str, shard_id: str) -> dict[str, Any]:
    managed = dict(state.get("managed_run", {}) or {})
    if (
        str(managed.get("target_id", "")).strip() == target_id
        and str(managed.get("shard_id", "")).strip() == shard_id
    ):
        return managed
    return {}


def _compute_state(
    *,
    active_row: dict[str, Any],
    managed_run: dict[str, Any],
    summary_info: dict[str, Any],
) -> dict[str, Any]:
    pid = int(managed_run.get("compute_pid", 0) or 0)
    heartbeat_pid = int(managed_run.get("heartbeat_pid", 0) or 0)
    compute_pid_running = _pid_is_running(pid) if pid else False
    heartbeat_pid_running = _pid_is_running(heartbeat_pid) if heartbeat_pid else False
    target_id = str(active_row.get("target_id", "")).strip()
    shard_id = str(active_row.get("shard_id", "")).strip()

    if summary_info.get("summary_present"):
        status = "summary_complete"
    elif pid and not compute_pid_running:
        status = "pid_exited_no_summary"
    elif pid and compute_pid_running:
        status = "running_under_watcher"
    elif summary_info.get("stage2_progress_done") or summary_info.get("stage3_summary_present"):
        status = "artifacts_present_final_summary_pending"
    elif target_id and shard_id:
        status = "running_untracked"
    else:
        status = "idle"

    return {
        "status": status,
        "compute_pid": pid,
        "compute_pid_running": compute_pid_running,
        "heartbeat_pid": heartbeat_pid,
        "heartbeat_pid_running": heartbeat_pid_running,
    }


def _preferred_preflight_row(
    throughput_bridge: dict[str, Any],
    *,
    target_id: str,
    shard_id: str,
) -> dict[str, Any]:
    summary = dict(throughput_bridge.get("summary", {}) or {})
    if (
        str(summary.get("target_id", "")).strip() != target_id
        or str(summary.get("shard_id", "")).strip() != shard_id
    ):
        return {}
    rows = [dict(row) for row in (throughput_bridge.get("rows", []) or [])]
    for command_kind in DEFAULT_PREFLIGHT_KIND_ORDER:
        for row in rows:
            if str(row.get("command_kind", "")).strip() == command_kind and bool(row.get("enabled", False)):
                return row
    return {}


def _stage_label_for_command_kind(command_kind: str) -> str:
    text = str(command_kind or "").strip()
    if text.endswith("_tuned_gate51"):
        return DEFAULT_STAGE_LABEL_TUNED_GATE51
    if text.endswith("_tuned_gate55"):
        return DEFAULT_STAGE_LABEL_TUNED_GATE55
    if text.endswith("_tuned"):
        return DEFAULT_STAGE_LABEL_TUNED
    return DEFAULT_STAGE_LABEL


def _preferred_summary_token(active_stage_label: str, compute_command_kind: str) -> str:
    text = " ".join(
        part for part in (str(active_stage_label or "").strip(), str(compute_command_kind or "").strip()) if part
    )
    for token in ("gate51", "gate55", "gate45"):
        if token in text:
            return token
    return ""


def _relativize(path_like: str | Path) -> str:
    path = Path(path_like)
    try:
        return str(path.resolve().relative_to(ROOT))
    except Exception:
        return str(path)


def _run_primary_event(
    *,
    target_id: str,
    shard_id: str,
    event: str,
    python_bin: str,
    active_stage_label: str = "",
    started_at: str = "",
    updated_at: str = "",
    completed_at: str = "",
    notes: str = "",
) -> dict[str, Any]:
    return primary_event.run_event(
        target_id=target_id,
        shard_id=shard_id,
        event=event,
        python_bin=python_bin,
        active_stage_label=active_stage_label,
        started_at=started_at,
        updated_at=updated_at,
        completed_at=completed_at,
        notes=notes,
    )


def _launch_heartbeat_loop(
    *,
    target_id: str,
    shard_id: str,
    active_stage_label: str,
    notes: str,
    python_bin: str,
    interval_sec: float,
    pid_file: Path = DEFAULT_HEARTBEAT_PID,
    log_file: Path = DEFAULT_HEARTBEAT_LOG,
) -> dict[str, Any]:
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        python_bin,
        str(DEFAULT_HEARTBEAT_LAUNCHER),
        "--target-id",
        target_id,
        "--shard-id",
        shard_id,
        "--active-stage-label",
        active_stage_label,
        "--interval-sec",
        str(interval_sec),
        "--pid-file",
        str(pid_file),
        "--log-file",
        str(log_file),
        "--replace",
    ]
    if notes:
        cmd.extend(["--notes", notes])
    completed = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True)
    stdout_lines = [line.strip() for line in (completed.stdout or "").splitlines() if line.strip()]
    pid = int(stdout_lines[-1]) if stdout_lines and stdout_lines[-1].isdigit() else 0
    return {
        "pid": pid,
        "pid_file": str(pid_file),
        "log_file": str(log_file),
        "command": shlex.join(cmd),
    }


def _launch_compute_command(*, command: str, log_file: Path) -> dict[str, Any]:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    handle = log_file.open("ab")
    proc = subprocess.Popen(
        shlex.split(command),
        cwd=ROOT,
        stdout=handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    return {"pid": proc.pid, "log_file": str(log_file), "command": command}


def _completion_notes(summary_info: dict[str, Any]) -> str:
    summary_path = str(summary_info.get("summary_path", "")).strip()
    summary_pass = summary_info.get("summary_pass")
    parts = ["watcher_auto_complete_from_compute_summary"]
    if summary_path:
        parts.append(f"summary={_relativize(summary_path)}")
    if summary_pass is not None:
        parts.append(f"pass={str(bool(summary_pass)).lower()}")
    failed_stage = str(summary_info.get("summary_failed_stage", "")).strip()
    if failed_stage:
        parts.append(f"failed_stage={failed_stage}")
    return " ".join(parts)


def _start_notes(command_kind: str) -> str:
    suffix = str(command_kind or "").strip() or "throughput_preflight"
    return f"watcher_auto_started_{suffix}"


def _build_rows(
    *,
    active_row: dict[str, Any],
    queue_row: dict[str, Any],
    progress_row: dict[str, Any],
    next_ready_row: dict[str, Any],
    managed_run: dict[str, Any],
    summary_info: dict[str, Any],
    compute_state: dict[str, Any],
    actions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    target_id = str(active_row.get("target_id", "")).strip()
    shard_id = str(active_row.get("shard_id", "")).strip()
    if target_id and shard_id:
        rows.append(
            {
                "role": "active_primary",
                "target_id": target_id,
                "shard_id": shard_id,
                "queue_status": str(queue_row.get("queue_status", "")).strip(),
                "progress_status": str(progress_row.get("queue_status", "")).strip(),
                "active_stage_label": str(progress_row.get("active_stage_label", "")).strip(),
                "compute_state": str(compute_state.get("status", "")).strip(),
                "compute_pid": int(compute_state.get("compute_pid", 0) or 0),
                "compute_pid_running": bool(compute_state.get("compute_pid_running", False)),
                "heartbeat_pid": int(compute_state.get("heartbeat_pid", 0) or 0),
                "heartbeat_pid_running": bool(compute_state.get("heartbeat_pid_running", False)),
                "compute_command_kind": str(managed_run.get("compute_command_kind", "")).strip(),
                "compute_log_path": _relativize(str(managed_run.get("compute_log_path", "")).strip()) if managed_run else "",
                "summary_present": bool(summary_info.get("summary_present", False)),
                "summary_pass": summary_info.get("summary_pass"),
                "summary_path": _relativize(str(summary_info.get("summary_path", "")).strip()) if summary_info.get("summary_path") else "",
                "throughput_dir": _relativize(str(summary_info.get("throughput_dir", "")).strip()) if summary_info.get("throughput_dir") else "",
            }
        )

    next_target = str(next_ready_row.get("target_id", "")).strip()
    next_shard = str(next_ready_row.get("shard_id", "")).strip()
    if next_target and next_shard and (next_target, next_shard) != (target_id, shard_id):
        rows.append(
            {
                "role": "next_ready",
                "target_id": next_target,
                "shard_id": next_shard,
                "queue_status": str(next_ready_row.get("queue_status", "")).strip(),
                "progress_status": "",
                "active_stage_label": "",
                "compute_state": "",
                "compute_pid": 0,
                "compute_pid_running": False,
                "heartbeat_pid": 0,
                "heartbeat_pid_running": False,
                "compute_command_kind": "",
                "compute_log_path": "",
                "summary_present": False,
                "summary_pass": "",
                "summary_path": "",
                "throughput_dir": "",
            }
        )

    for action in actions:
        rows.append(
            {
                "role": "action",
                "target_id": str(action.get("target_id", "")).strip(),
                "shard_id": str(action.get("shard_id", "")).strip(),
                "queue_status": str(action.get("action_kind", "")).strip(),
                "progress_status": str(action.get("status", "")).strip(),
                "active_stage_label": str(action.get("active_stage_label", "")).strip(),
                "compute_state": str(action.get("detail", "")).strip(),
                "compute_pid": int(action.get("compute_pid", 0) or 0),
                "compute_pid_running": bool(action.get("compute_pid_running", False)),
                "heartbeat_pid": int(action.get("heartbeat_pid", 0) or 0),
                "heartbeat_pid_running": bool(action.get("heartbeat_pid_running", False)),
                "compute_command_kind": str(action.get("compute_command_kind", "")).strip(),
                "compute_log_path": _relativize(str(action.get("compute_log_path", "")).strip()) if action.get("compute_log_path") else "",
                "summary_present": "",
                "summary_pass": "",
                "summary_path": "",
                "throughput_dir": "",
            }
        )
    return rows


def _next_required_step(
    *,
    active_row: dict[str, Any],
    next_ready_row: dict[str, Any],
    summary_info: dict[str, Any],
    compute_state: dict[str, Any],
    auto_complete_active: bool,
    auto_start_next: bool,
    actions: list[dict[str, Any]],
    managed_run: dict[str, Any],
) -> str:
    target_id = str(active_row.get("target_id", "")).strip()
    shard_id = str(active_row.get("shard_id", "")).strip()
    next_target = str(next_ready_row.get("target_id", "")).strip()
    next_shard = str(next_ready_row.get("shard_id", "")).strip()
    compute_status = str(compute_state.get("status", "")).strip()

    if compute_status == "pid_exited_no_summary":
        log_path = str(managed_run.get("compute_log_path", "")).strip()
        if log_path:
            return (
                f"Compute PID exited for {target_id} shard {shard_id} before a final summary appeared; inspect `{_relativize(log_path)}` and decide whether to reset, hold, or relaunch."
            )
        return (
            f"Compute PID exited for {target_id} shard {shard_id} before a final summary appeared; inspect the throughput launch and decide whether to reset, hold, or relaunch."
        )
    if compute_status == "summary_complete" and not auto_complete_active:
        return f"Final throughput summary is present for {target_id} shard {shard_id}; complete the row when ready."
    if any(action.get("status") == "error" for action in actions):
        return "Watcher hit an orchestration error; inspect the action rows and relaunch the failed step explicitly."
    if target_id and shard_id and str(active_row.get("progress_status", "")).strip() == "running":
        return f"Continue monitoring {target_id} shard {shard_id} until the final throughput summary lands."
    if next_target and next_shard and not auto_start_next:
        return f"Start {next_target} shard {next_shard} and launch its throughput preflight when ready."
    if next_target and next_shard and auto_start_next:
        return f"Watcher started {next_target} shard {next_shard}; keep the heartbeat loop and throughput preflight under observation."
    return "No actionable primary shard is waiting; refresh the queue and inspect downstream counterscreen or result aggregation tasks."


def run_once(
    *,
    queue_json: str | Path = DEFAULT_QUEUE_JSON,
    progress_json: str | Path = DEFAULT_PROGRESS_JSON,
    throughput_bridge_json: str | Path = DEFAULT_THROUGHPUT_BRIDGE_JSON,
    watcher_state_json: str | Path = DEFAULT_WATCHER_STATE_JSON,
    out_md: str | Path = DEFAULT_OUT_MD,
    python_bin: str = sys.executable,
    auto_complete_active: bool = False,
    auto_start_next: bool = False,
    heartbeat_interval_sec: float = 30.0,
    runtime_dir: str | Path = DEFAULT_RUNTIME_DIR,
) -> dict[str, Any]:
    runtime_dir = resolve(str(runtime_dir))
    runtime_dir.mkdir(parents=True, exist_ok=True)

    queue_payload = _read_json(queue_json)
    progress_payload = _read_json(progress_json)
    throughput_bridge = _read_json(throughput_bridge_json)
    state = _read_json(watcher_state_json)
    state.setdefault("managed_run", {})

    actions: list[dict[str, Any]] = []

    active = _active_or_focus_row(queue_payload, progress_payload)
    target_id = str(active.get("target_id", "")).strip()
    shard_id = str(active.get("shard_id", "")).strip()
    queue_row = dict(active.get("queue_row", {}) or {})
    progress_row = dict(active.get("progress_row", {}) or {})
    active["queue_status"] = str(queue_row.get("queue_status", "")).strip()
    active["progress_status"] = str(progress_row.get("queue_status", "")).strip()
    active["active_stage_label"] = str(progress_row.get("active_stage_label", "")).strip()

    managed_run = _matching_managed_run(state, target_id, shard_id) if target_id and shard_id else {}
    prefer_token = _preferred_summary_token(active["active_stage_label"], str(managed_run.get("compute_command_kind", "")).strip())
    summary_info = _detect_compute_summary(_throughput_dir_for_row(active, throughput_bridge), prefer_token=prefer_token)
    compute_state = _compute_state(active_row=active, managed_run=managed_run, summary_info=summary_info)

    if (
        auto_complete_active
        and target_id
        and shard_id
        and active["progress_status"] == "running"
        and bool(summary_info.get("summary_present"))
    ):
        completed_at = str(summary_info.get("summary_generated_at", "")).strip() or _now_text()
        completion_action = _run_primary_event(
            target_id=target_id,
            shard_id=shard_id,
            event="complete",
            python_bin=python_bin,
            active_stage_label=active["active_stage_label"] or DEFAULT_STAGE_LABEL,
            completed_at=completed_at,
            updated_at=completed_at,
            notes=_completion_notes(summary_info),
        )
        actions.append(
            {
                "action_kind": "auto_complete",
                "status": "ok",
                "target_id": target_id,
                "shard_id": shard_id,
                "active_stage_label": active["active_stage_label"] or DEFAULT_STAGE_LABEL,
                "detail": completion_action.get("event", "complete"),
            }
        )
        if managed_run:
            state["last_completed_run"] = managed_run
            state["managed_run"] = {}
            managed_run = {}
        queue_payload = _read_json(queue_json)
        progress_payload = _read_json(progress_json)
        throughput_bridge = _read_json(throughput_bridge_json)
        active = _active_or_focus_row(queue_payload, progress_payload)
        target_id = str(active.get("target_id", "")).strip()
        shard_id = str(active.get("shard_id", "")).strip()
        queue_row = dict(active.get("queue_row", {}) or {})
        progress_row = dict(active.get("progress_row", {}) or {})
        active["queue_status"] = str(queue_row.get("queue_status", "")).strip()
        active["progress_status"] = str(progress_row.get("queue_status", "")).strip()
        active["active_stage_label"] = str(progress_row.get("active_stage_label", "")).strip()
        managed_run = _matching_managed_run(state, target_id, shard_id) if target_id and shard_id else {}
        prefer_token = _preferred_summary_token(active["active_stage_label"], str(managed_run.get("compute_command_kind", "")).strip())
        summary_info = _detect_compute_summary(_throughput_dir_for_row(active, throughput_bridge), prefer_token=prefer_token)
        compute_state = _compute_state(active_row=active, managed_run=managed_run, summary_info=summary_info)

    if auto_start_next and not any("running" in str(row.get("queue_status", "")).strip() for row in _progress_rows(progress_payload)):
        next_ready_row = _first_ready_row(queue_payload)
        next_target = str(next_ready_row.get("target_id", "")).strip()
        next_shard = str(next_ready_row.get("shard_id", "")).strip()
        if next_target and next_shard:
            preflight_row = _preferred_preflight_row(
                throughput_bridge,
                target_id=next_target,
                shard_id=next_shard,
            )
            if preflight_row:
                command_kind = str(preflight_row.get("command_kind", "")).strip()
                stage_label = _stage_label_for_command_kind(command_kind)
                started_at = _now_text()
                _run_primary_event(
                    target_id=next_target,
                    shard_id=next_shard,
                    event="start",
                    python_bin=python_bin,
                    active_stage_label=stage_label,
                    started_at=started_at,
                    updated_at=started_at,
                    notes=_start_notes(command_kind),
                )
                heartbeat_info = _launch_heartbeat_loop(
                    target_id=next_target,
                    shard_id=next_shard,
                    active_stage_label=stage_label,
                    notes=_start_notes(command_kind),
                    python_bin=python_bin,
                    interval_sec=heartbeat_interval_sec,
                    pid_file=runtime_dir / "heartbeat_loop.pid",
                    log_file=runtime_dir / "heartbeat_loop.log",
                )
                target_runtime_dir = runtime_dir / _target_slug(next_target) / next_shard
                compute_log_file = target_runtime_dir / f"{command_kind}.log"
                compute_info = _launch_compute_command(
                    command=str(preflight_row.get("command", "")).strip(),
                    log_file=compute_log_file,
                )
                state["managed_run"] = {
                    "target_id": next_target,
                    "shard_id": next_shard,
                    "active_stage_label": stage_label,
                    "compute_pid": int(compute_info.get("pid", 0) or 0),
                    "compute_command_kind": command_kind,
                    "compute_command": str(compute_info.get("command", "")).strip(),
                    "compute_log_path": str(compute_info.get("log_file", "")).strip(),
                    "heartbeat_pid": int(heartbeat_info.get("pid", 0) or 0),
                    "heartbeat_pid_file": str(heartbeat_info.get("pid_file", "")).strip(),
                    "heartbeat_log_file": str(heartbeat_info.get("log_file", "")).strip(),
                    "launched_at": started_at,
                }
                actions.extend(
                    [
                        {
                            "action_kind": "auto_start",
                            "status": "ok",
                            "target_id": next_target,
                            "shard_id": next_shard,
                            "active_stage_label": stage_label,
                            "detail": "primary_row_started",
                        },
                        {
                            "action_kind": "launch_heartbeat",
                            "status": "ok",
                            "target_id": next_target,
                            "shard_id": next_shard,
                            "active_stage_label": stage_label,
                            "detail": _relativize(str(heartbeat_info.get("log_file", "")).strip()),
                            "heartbeat_pid": int(heartbeat_info.get("pid", 0) or 0),
                            "heartbeat_pid_running": _pid_is_running(int(heartbeat_info.get("pid", 0) or 0)),
                        },
                        {
                            "action_kind": "launch_compute_preflight",
                            "status": "ok",
                            "target_id": next_target,
                            "shard_id": next_shard,
                            "active_stage_label": stage_label,
                            "detail": command_kind,
                            "compute_pid": int(compute_info.get("pid", 0) or 0),
                            "compute_pid_running": _pid_is_running(int(compute_info.get("pid", 0) or 0)),
                            "compute_command_kind": command_kind,
                            "compute_log_path": str(compute_info.get("log_file", "")).strip(),
                        },
                    ]
                )
                queue_payload = _read_json(queue_json)
                progress_payload = _read_json(progress_json)
                throughput_bridge = _read_json(throughput_bridge_json)
            else:
                actions.append(
                    {
                        "action_kind": "auto_start",
                        "status": "error",
                        "target_id": next_target,
                        "shard_id": next_shard,
                        "active_stage_label": "",
                        "detail": "no_enabled_preflight_command_for_first_ready_row",
                    }
                )

    active = _active_or_focus_row(queue_payload, progress_payload)
    target_id = str(active.get("target_id", "")).strip()
    shard_id = str(active.get("shard_id", "")).strip()
    queue_row = dict(active.get("queue_row", {}) or {})
    progress_row = dict(active.get("progress_row", {}) or {})
    active["queue_status"] = str(queue_row.get("queue_status", "")).strip()
    active["progress_status"] = str(progress_row.get("queue_status", "")).strip()
    active["active_stage_label"] = str(progress_row.get("active_stage_label", "")).strip()

    managed_run = _matching_managed_run(state, target_id, shard_id) if target_id and shard_id else {}
    prefer_token = _preferred_summary_token(active["active_stage_label"], str(managed_run.get("compute_command_kind", "")).strip())
    summary_info = _detect_compute_summary(_throughput_dir_for_row(active, throughput_bridge), prefer_token=prefer_token)
    compute_state = _compute_state(active_row=active, managed_run=managed_run, summary_info=summary_info)
    next_ready_row = _first_ready_row(queue_payload)

    state["last_cycle"] = {
        "generated_at": _now_text(),
        "active_target_id": target_id,
        "active_shard_id": shard_id,
        "compute_state": str(compute_state.get("status", "")).strip(),
        "summary_path": str(summary_info.get("summary_path", "")).strip(),
    }
    _write_json(watcher_state_json, state)

    payload = {
        "summary": {
            "status": "wetlab_broad_screen_primary_watcher_ready",
            "generated_at": _now_text(),
            "active_target_id": target_id,
            "active_shard_id": shard_id,
            "active_queue_status": str(queue_row.get("queue_status", "")).strip(),
            "active_progress_status": str(progress_row.get("queue_status", "")).strip(),
            "active_stage_label": str(progress_row.get("active_stage_label", "")).strip(),
            "compute_state": str(compute_state.get("status", "")).strip(),
            "compute_summary_present": bool(summary_info.get("summary_present", False)),
            "compute_summary_pass": summary_info.get("summary_pass"),
            "compute_summary_path": _relativize(str(summary_info.get("summary_path", "")).strip()) if summary_info.get("summary_path") else "",
            "compute_pid": int(compute_state.get("compute_pid", 0) or 0),
            "compute_pid_running": bool(compute_state.get("compute_pid_running", False)),
            "heartbeat_pid": int(compute_state.get("heartbeat_pid", 0) or 0),
            "heartbeat_pid_running": bool(compute_state.get("heartbeat_pid_running", False)),
            "managed_compute_command_kind": str(managed_run.get("compute_command_kind", "")).strip(),
            "actions_taken_count": len(actions),
            "auto_complete_active": auto_complete_active,
            "auto_start_next": auto_start_next,
            "next_ready_target_id": str(next_ready_row.get("target_id", "")).strip(),
            "next_ready_shard_id": str(next_ready_row.get("shard_id", "")).strip(),
            "next_required_step": _next_required_step(
                active_row=active,
                next_ready_row=next_ready_row,
                summary_info=summary_info,
                compute_state=compute_state,
                auto_complete_active=auto_complete_active,
                auto_start_next=auto_start_next,
                actions=actions,
                managed_run=managed_run,
            ),
        },
        "structured": {
            "execution_queue_artifact": _relativize(str(resolve(str(queue_json)))),
            "progress_artifact": _relativize(str(resolve(str(progress_json)))),
            "throughput_bridge_artifact": _relativize(str(resolve(str(throughput_bridge_json)))),
            "watcher_state_json": _relativize(str(resolve(str(watcher_state_json)))),
            "heartbeat_pid_file": _relativize(str(runtime_dir / "heartbeat_loop.pid")),
            "heartbeat_log_file": _relativize(str(runtime_dir / "heartbeat_loop.log")),
            "managed_compute_log_path": _relativize(str(managed_run.get("compute_log_path", "")).strip()) if managed_run else "",
        },
        "rows": _build_rows(
            active_row=active,
            queue_row=queue_row,
            progress_row=progress_row,
            next_ready_row=next_ready_row,
            managed_run=managed_run,
            summary_info=summary_info,
            compute_state=compute_state,
            actions=actions,
        ),
    }
    write_artifact(str(out_md), "Wet-Lab Broad Screen Primary Watcher", payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect and optionally orchestrate the active wet-lab broad-screen primary shard.")
    parser.add_argument("--queue-json", default=str(DEFAULT_QUEUE_JSON))
    parser.add_argument("--progress-json", default=str(DEFAULT_PROGRESS_JSON))
    parser.add_argument("--throughput-bridge-json", default=str(DEFAULT_THROUGHPUT_BRIDGE_JSON))
    parser.add_argument("--watcher-state-json", default=str(DEFAULT_WATCHER_STATE_JSON))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    parser.add_argument("--runtime-dir", default=str(DEFAULT_RUNTIME_DIR))
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--heartbeat-interval-sec", type=float, default=30.0)
    parser.add_argument("--auto-complete-active", action="store_true")
    parser.add_argument("--auto-start-next", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval-sec", type=float, default=30.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.loop:
        payload = run_once(
            queue_json=args.queue_json,
            progress_json=args.progress_json,
            throughput_bridge_json=args.throughput_bridge_json,
            watcher_state_json=args.watcher_state_json,
            out_md=args.out_md,
            python_bin=args.python_bin,
            auto_complete_active=args.auto_complete_active,
            auto_start_next=args.auto_start_next,
            heartbeat_interval_sec=args.heartbeat_interval_sec,
            runtime_dir=args.runtime_dir,
        )
        print(json.dumps(payload.get("summary", {}), ensure_ascii=False))
        return 0

    while True:
        run_once(
            queue_json=args.queue_json,
            progress_json=args.progress_json,
            throughput_bridge_json=args.throughput_bridge_json,
            watcher_state_json=args.watcher_state_json,
            out_md=args.out_md,
            python_bin=args.python_bin,
            auto_complete_active=args.auto_complete_active,
            auto_start_next=args.auto_start_next,
            heartbeat_interval_sec=args.heartbeat_interval_sec,
            runtime_dir=args.runtime_dir,
        )
        time.sleep(max(args.interval_sec, 1.0))


if __name__ == "__main__":
    raise SystemExit(main())
