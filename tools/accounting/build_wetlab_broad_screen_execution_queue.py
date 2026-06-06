#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
from typing import Any

from tools.wetlab_target_render_utils import load_json, maybe_load_json, write_artifact

DEFAULT_QUEUE_JSON = "runs/wetlab_broad_screen_queue_current.json"
DEFAULT_UNIVERSE_JSON = "runs/wetlab_broad_screen_compound_universe_current.json"
DEFAULT_PROGRESS_JSON = "runs/wetlab_broad_screen_progress_current.json"
DEFAULT_OUT_MD = "runs/wetlab_broad_screen_execution_queue_current.md"
DEFAULT_STALE_MINUTES = 20.0


def _summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict((payload or {}).get("summary", {}) or {})


def _progress_rows(payload: dict[str, Any] | None) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (str(row.get("target_id", "")).strip(), str(row.get("shard_id", "")).strip()): dict(row)
        for row in ((payload or {}).get("rows", []) or [])
        if str(row.get("target_id", "")).strip() and str(row.get("shard_id", "")).strip()
    }


def _is_resolved(status: str) -> bool:
    return "result_ready" in status or "explicit_hold" in status


def _parse_ts(value: Any) -> dt.datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return dt.datetime.fromisoformat(text)
    except Exception:
        return None


def _minutes_since(value: Any, now: dt.datetime) -> float:
    stamp = _parse_ts(value)
    if stamp is None:
        return 0.0
    return max((now - stamp).total_seconds() / 60.0, 0.0)


def _target_slug(target_id: str) -> str:
    return (
        target_id.lower()
        .replace(".", "")
        .replace("-", "_")
        .replace("/", "_")
        .replace("(", "")
        .replace(")", "")
        .replace(" ", "_")
    )


def _row_command(target_id: str, shard_id: str, event: str) -> str:
    return (
        "python3 tools/run_wetlab_broad_screen_runtime_event.py "
        f"--target-id \"{target_id}\" --shard-id {shard_id} --event {event}"
    )


def build_payload(
    broad_queue: dict[str, Any],
    compound_universe: dict[str, Any],
    progress_payload: dict[str, Any] | None = None,
    stale_minutes: float = DEFAULT_STALE_MINUTES,
) -> dict[str, Any]:
    universe_summary = _summary(compound_universe)
    progress_map = _progress_rows(progress_payload)
    source_rows = [dict(row) for row in (broad_queue.get("rows", []) or [])]
    now = dt.datetime.now()

    persisted_statuses: list[str] = []
    for row in source_rows:
        persisted = progress_map.get((str(row.get("target_id", "")).strip(), str(row.get("shard_id", "")).strip()), {})
        status = str(persisted.get("queue_status", "")).strip()
        if "running" in status:
            update_age_minutes = _minutes_since(persisted.get("updated_at") or persisted.get("started_at"), now)
            if update_age_minutes > float(stale_minutes):
                status = "stale_running_needs_recovery"
        persisted_statuses.append(status)

    stale_index = next((idx for idx, status in enumerate(persisted_statuses) if "stale_running" in status), None)
    running_index = next((idx for idx, status in enumerate(persisted_statuses) if "running" in status), None)
    if stale_index is not None:
        actionable_index = stale_index
        actionable_status = "stale_running_needs_recovery"
    elif running_index is not None:
        actionable_index = running_index
        actionable_status = "running"
    else:
        actionable_index = next((idx for idx, status in enumerate(persisted_statuses) if not _is_resolved(status)), None)
        if actionable_index is None:
            actionable_status = ""
        elif actionable_index == 0:
            actionable_status = "ready_first_shard"
        else:
            prev_target = str(source_rows[actionable_index - 1].get("target_id", "")).strip()
            current_target = str(source_rows[actionable_index].get("target_id", "")).strip()
            actionable_status = "ready_after_previous_shard" if prev_target == current_target else "ready_after_previous_target"

    rows: list[dict[str, Any]] = []
    for idx, row in enumerate(source_rows):
        target_id = str(row.get("target_id", "")).strip()
        shard_id = str(row.get("shard_id", "")).strip()
        persisted = progress_map.get((target_id, shard_id), {})
        queue_status = str(persisted.get("queue_status", "")).strip()
        progress_update_age_minutes = _minutes_since(persisted.get("updated_at") or persisted.get("started_at"), now)
        if "running" in queue_status and progress_update_age_minutes > float(stale_minutes):
            queue_status = "stale_running_needs_recovery"

        if not queue_status:
            if actionable_index is None:
                queue_status = "result_ready"
            elif idx < actionable_index:
                queue_status = "result_ready"
            elif idx == actionable_index:
                queue_status = actionable_status
            else:
                prev_target = str(source_rows[actionable_index].get("target_id", "")).strip()
                queue_status = "blocked_on_previous_shard" if target_id == prev_target else "blocked_on_previous_target"

        rows.append(
            {
                **row,
                "queue_status": queue_status,
                "execution_state": (
                    "running"
                    if "running" in queue_status
                    else "stale"
                    if "stale_running" in queue_status
                    else "result_ready"
                    if _is_resolved(queue_status) and "explicit_hold" not in queue_status
                    else "explicit_hold"
                    if "explicit_hold" in queue_status
                    else "blocked"
                    if queue_status.startswith("blocked")
                    else "ready_to_launch"
                ),
                "target_slug": _target_slug(target_id),
                "progress_started_at": str(persisted.get("started_at", "")).strip(),
                "progress_updated_at": str(persisted.get("updated_at", "")).strip(),
                "progress_completed_at": str(persisted.get("completed_at", "")).strip(),
                "progress_update_age_minutes": round(progress_update_age_minutes, 1),
                "notes": str(persisted.get("notes", "")).strip(),
                "launch_command": _row_command(target_id, shard_id, "start"),
                "complete_command": _row_command(target_id, shard_id, "complete"),
                "hold_command": _row_command(target_id, shard_id, "hold"),
                "reset_command": _row_command(target_id, shard_id, "reset"),
            }
        )

    first_actionable = next(
        (
            row
            for row in rows
            if str(row.get("queue_status", "")).startswith("ready")
            or "running" in str(row.get("queue_status", ""))
            or "stale_running" in str(row.get("queue_status", ""))
        ),
        None,
    )
    first_actionable_status = str(first_actionable.get("queue_status", "")).strip() if first_actionable else ""
    if first_actionable and "running" in first_actionable_status:
        next_required_step = (
            f"Continue or complete {first_actionable['target_id']} shard {first_actionable['shard_id']} through the broad-screen runtime runner."
        )
    elif first_actionable and "stale_running" in first_actionable_status:
        next_required_step = (
            f"Recover stale {first_actionable['target_id']} shard {first_actionable['shard_id']} with reset or hold, then relaunch it."
        )
    elif first_actionable:
        next_required_step = (
            f"Dispatch {first_actionable['target_id']} shard {first_actionable['shard_id']} through the broad-screen runtime runner."
        )
    else:
        next_required_step = "Broad-screen execution queue is fully resolved; aggregate bulk results into the autofill bridge."

    return {
        "summary": {
            "status": "wetlab_broad_screen_execution_queue_ready",
            "library_lane": str(_summary(broad_queue).get("library_lane", "broad_procurement_100k")).strip(),
            "target_library_size": int(universe_summary.get("target_library_size", 100000) or 100000),
            "ingested_compound_count": int(universe_summary.get("deduped_compound_count", 0) or 0),
            "coverage_gap_to_target_size": int(universe_summary.get("coverage_gap_to_target_size", 0) or 0),
            "queue_row_count": len(rows),
            "ready_now_row_count": sum(1 for row in rows if str(row["queue_status"]).startswith("ready")),
            "running_row_count": sum(1 for row in rows if str(row["queue_status"]) == "running"),
            "stale_row_count": sum(1 for row in rows if "stale_running" in str(row["queue_status"])),
            "resolved_row_count": sum(1 for row in rows if _is_resolved(str(row["queue_status"]))),
            "first_actionable_target_id": str(first_actionable.get("target_id", "")).strip() if first_actionable else "",
            "first_actionable_shard_id": str(first_actionable.get("shard_id", "")).strip() if first_actionable else "",
            "first_actionable_queue_status": first_actionable_status,
            "next_required_step": next_required_step,
        },
        "structured": {
            "broad_queue_artifact": "runs/wetlab_broad_screen_queue_current.md",
            "compound_universe_artifact": "runs/wetlab_broad_screen_compound_universe_current.md",
            "progress_artifact": "runs/wetlab_broad_screen_progress_current.md",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the execution queue for the 100k broad screen.")
    parser.add_argument("--queue-json", default=DEFAULT_QUEUE_JSON)
    parser.add_argument("--compound-universe-json", default=DEFAULT_UNIVERSE_JSON)
    parser.add_argument("--progress-json", default=DEFAULT_PROGRESS_JSON)
    parser.add_argument("--stale-minutes", type=float, default=DEFAULT_STALE_MINUTES)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    write_artifact(
        args.out_md,
        "Wet-Lab Broad Screen Execution Queue",
        build_payload(
            load_json(args.queue_json),
            load_json(args.compound_universe_json),
            maybe_load_json(args.progress_json),
            stale_minutes=args.stale_minutes,
        ),
    )
