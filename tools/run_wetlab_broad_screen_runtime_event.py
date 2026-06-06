#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.wetlab_target_render_utils import maybe_load_json, write_artifact

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROGRESS_MD = "runs/wetlab_broad_screen_progress_current.md"
DEFAULT_EXECUTION_QUEUE_SCRIPT = "tools/build_wetlab_broad_screen_execution_queue.py"
DEFAULT_RUNBOOK_SCRIPT = "tools/wetlab/wetlab/build_wetlab_broad_screen_runtime_runbook.py"
DEFAULT_THROUGHPUT_BRIDGE_SCRIPT = "tools/build_wetlab_broad_screen_throughput_bridge.py"
DEFAULT_APPEND_SCRIPT = "tools/run_wetlab_broad_screen_actual_append.py"
DEFAULT_APPEND_BATCH_MD = "runs/wetlab_broad_screen_actual_append_batch_current.md"
DEFAULT_LOG_PATH = ROOT / "runs/wetlab_broad_screen_runtime_event_log.jsonl"
DEFAULT_STAGE_LABEL = "broad_screen_primary_shard"


def _progress_index(rows: list[dict[str, Any]]) -> dict[tuple[str, str], int]:
    return {
        (str(row.get("target_id", "")).strip(), str(row.get("shard_id", "")).strip()): idx
        for idx, row in enumerate(rows)
        if str(row.get("target_id", "")).strip() and str(row.get("shard_id", "")).strip()
    }


def _write_progress(rows: list[dict[str, Any]]) -> None:
    running_count = sum(1 for row in rows if "running" in str(row.get("queue_status", "")))
    resolved_count = sum(1 for row in rows if "result_ready" in str(row.get("queue_status", "")) or "explicit_hold" in str(row.get("queue_status", "")))
    payload = {
        "summary": {
            "status": "wetlab_broad_screen_progress_ready",
            "row_count": len(rows),
            "running_row_count": running_count,
            "resolved_row_count": resolved_count,
            "next_required_step": "Rebuild the broad-screen execution queue after each shard event so the next actionable shard becomes visible.",
        },
        "rows": rows,
    }
    write_artifact(DEFAULT_PROGRESS_MD, "Wet-Lab Broad Screen Progress", payload)


def _append_log(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _rebuild_support(python_bin: str, *, event: str) -> None:
    scripts = [DEFAULT_EXECUTION_QUEUE_SCRIPT]
    if event != "heartbeat":
        scripts.extend([DEFAULT_RUNBOOK_SCRIPT, DEFAULT_THROUGHPUT_BRIDGE_SCRIPT])
    for script in scripts:
        subprocess.run([python_bin, str(ROOT / script)], cwd=ROOT, check=True)


def apply_event(
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
    rows_json: str = "",
    append_mode: str = "immediate",
    append_refresh_tier: str = "minimal",
    append_batch_md: str = DEFAULT_APPEND_BATCH_MD,
    log_path: Path = DEFAULT_LOG_PATH,
) -> dict[str, Any]:
    progress_payload = maybe_load_json(DEFAULT_PROGRESS_MD.replace(".md", ".json"))
    rows = [dict(row) for row in (progress_payload.get("rows", []) or [])]
    index = _progress_index(rows)
    key = (target_id.strip(), shard_id.strip())

    if event == "reset":
        if key in index:
            rows.pop(index[key])
    else:
        row = rows[index[key]] if key in index else {"target_id": target_id, "shard_id": shard_id}
        heartbeat_count = int(row.get("heartbeat_count", 0) or 0)
        event_count = int(row.get("event_count", 0) or 0)
        timestamp = completed_at or updated_at or started_at or datetime.now().isoformat(timespec="seconds")
        if event == "start":
            previous_status = str(row.get("queue_status", "")).strip()
            fresh_start = previous_status != "running"
            start_ts = started_at or datetime.now().isoformat(timespec="seconds")
            row["queue_status"] = "running"
            row["active_stage_label"] = active_stage_label or row.get("active_stage_label", "") or DEFAULT_STAGE_LABEL
            row["started_at"] = start_ts if fresh_start else (row.get("started_at", "") or start_ts)
            row["updated_at"] = updated_at or start_ts
            row["completed_at"] = ""
            row["notes"] = notes
            row["heartbeat_count"] = 0 if fresh_start else heartbeat_count
            row["event_count"] = 1 if fresh_start else (event_count + 1)
            row["run_attempt"] = int(row.get("run_attempt", 0) or 0) + (1 if fresh_start else 0)
            row["last_event"] = "start"
            row["last_event_at"] = timestamp
        elif event == "heartbeat":
            row["queue_status"] = "running"
            row["active_stage_label"] = active_stage_label or row.get("active_stage_label", "") or DEFAULT_STAGE_LABEL
            row["updated_at"] = updated_at or datetime.now().isoformat(timespec="seconds")
            row["notes"] = notes or row.get("notes", "")
            row["heartbeat_count"] = heartbeat_count + 1
            row["event_count"] = event_count + 1
            row["last_event"] = "heartbeat"
            row["last_event_at"] = timestamp
        elif event == "complete":
            row["queue_status"] = "result_ready"
            row["active_stage_label"] = active_stage_label or row.get("active_stage_label", "") or DEFAULT_STAGE_LABEL
            row["started_at"] = started_at or row.get("started_at", "")
            row["updated_at"] = updated_at or completed_at or datetime.now().isoformat(timespec="seconds")
            row["completed_at"] = completed_at or datetime.now().isoformat(timespec="seconds")
            row["notes"] = notes
            row["event_count"] = event_count + 1
            row["last_event"] = "complete"
            row["last_event_at"] = timestamp
        elif event == "hold":
            row["queue_status"] = "explicit_hold"
            row["active_stage_label"] = active_stage_label or row.get("active_stage_label", "") or DEFAULT_STAGE_LABEL
            row["started_at"] = started_at or row.get("started_at", "")
            row["updated_at"] = updated_at or datetime.now().isoformat(timespec="seconds")
            row["completed_at"] = completed_at or row.get("completed_at", "")
            row["notes"] = notes
            row["event_count"] = event_count + 1
            row["last_event"] = "hold"
            row["last_event_at"] = timestamp
        else:
            raise ValueError(f"unsupported event: {event}")
        if key in index:
            rows[index[key]] = row
        else:
            rows.append(row)

    rows = sorted(rows, key=lambda row: (str(row.get("target_id", "")), str(row.get("shard_id", ""))))
    _write_progress(rows)
    _rebuild_support(python_bin, event=event)
    if rows_json and event == "complete":
        subprocess.run(
            [
                python_bin,
                str(ROOT / DEFAULT_APPEND_SCRIPT),
                "--rows-json",
                rows_json,
                "--mode",
                append_mode,
                "--refresh-tier",
                append_refresh_tier,
                "--batch-md",
                append_batch_md,
            ],
            cwd=ROOT,
            check=True,
        )

    log_row = {
        "target_id": target_id,
        "shard_id": shard_id,
        "event": event,
        "active_stage_label": active_stage_label,
        "started_at": started_at,
        "updated_at": updated_at,
        "completed_at": completed_at,
        "notes": notes,
        "rows_json": rows_json,
        "event_timestamp": completed_at or updated_at or started_at or datetime.now().isoformat(timespec="seconds"),
    }
    _append_log(log_path, log_row)
    return log_row


def run_event(
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
    rows_json: str = "",
    append_mode: str = "immediate",
    append_refresh_tier: str = "minimal",
    append_batch_md: str = DEFAULT_APPEND_BATCH_MD,
    log_path: Path = DEFAULT_LOG_PATH,
    loop: bool = False,
    interval_sec: float = 30.0,
    max_heartbeats: int = 0,
) -> dict[str, Any]:
    if not loop:
        return apply_event(
            target_id=target_id,
            shard_id=shard_id,
            event=event,
            python_bin=python_bin,
            active_stage_label=active_stage_label,
            started_at=started_at,
            updated_at=updated_at,
            completed_at=completed_at,
            notes=notes,
            rows_json=rows_json,
            append_mode=append_mode,
            append_refresh_tier=append_refresh_tier,
            append_batch_md=append_batch_md,
            log_path=log_path,
        )

    if event != "heartbeat":
        raise ValueError("--loop is only supported with --event heartbeat")

    pulses = 0
    last_row: dict[str, Any] = {}
    try:
        while True:
            now_text = datetime.now().isoformat(timespec="seconds")
            last_row = apply_event(
                target_id=target_id,
                shard_id=shard_id,
                event="heartbeat",
                python_bin=python_bin,
                active_stage_label=active_stage_label,
                started_at=started_at,
                updated_at=now_text,
                completed_at=completed_at,
                notes=notes,
                rows_json="",
                append_mode=append_mode,
                append_refresh_tier=append_refresh_tier,
                append_batch_md=append_batch_md,
                log_path=log_path,
            )
            pulses += 1
            if max_heartbeats > 0 and pulses >= max_heartbeats:
                break
            time.sleep(max(interval_sec, 0.5))
    except KeyboardInterrupt:
        return {
            "event": "heartbeat_loop_stopped",
            "target_id": target_id,
            "shard_id": shard_id,
            "pulse_count": pulses,
            "last_row": last_row,
        }
    return {
        "event": "heartbeat_loop_complete",
        "target_id": target_id,
        "shard_id": shard_id,
        "pulse_count": pulses,
        "last_row": last_row,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update one broad-screen shard event and rebuild queue/runbook surfaces.")
    parser.add_argument("--target-id", required=True)
    parser.add_argument("--shard-id", required=True)
    parser.add_argument("--event", choices=("reset", "start", "heartbeat", "complete", "hold"), required=True)
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--active-stage-label", default="")
    parser.add_argument("--started-at", default="")
    parser.add_argument("--updated-at", default="")
    parser.add_argument("--completed-at", default="")
    parser.add_argument("--notes", default="")
    parser.add_argument("--rows-json", default="")
    parser.add_argument("--append-mode", choices=("immediate", "enqueue", "flush"), default="immediate")
    parser.add_argument("--append-refresh-tier", choices=("minimal", "full"), default="minimal")
    parser.add_argument("--append-batch-md", default=DEFAULT_APPEND_BATCH_MD)
    parser.add_argument("--log-path", default=str(DEFAULT_LOG_PATH))
    parser.add_argument("--loop", action="store_true", help="Repeat heartbeat events until interrupted.")
    parser.add_argument("--interval-sec", type=float, default=30.0)
    parser.add_argument("--max-heartbeats", type=int, default=0, help="Optional finite heartbeat loop for testing.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    result = run_event(
        target_id=args.target_id,
        shard_id=args.shard_id,
        event=args.event,
        python_bin=args.python_bin,
        active_stage_label=args.active_stage_label,
        started_at=args.started_at,
        updated_at=args.updated_at,
        completed_at=args.completed_at,
        notes=args.notes,
        rows_json=args.rows_json,
        append_mode=args.append_mode,
        append_refresh_tier=args.append_refresh_tier,
        append_batch_md=args.append_batch_md,
        log_path=Path(args.log_path),
        loop=args.loop,
        interval_sec=args.interval_sec,
        max_heartbeats=args.max_heartbeats,
    )
    if args.loop:
        print(json.dumps(result, ensure_ascii=False))
