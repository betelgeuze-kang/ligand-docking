#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_broad_screen_watch_utils import consecutive_auto_hold_streak
from tools.wetlab_target_render_utils import load_json, write_artifact

DEFAULT_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_execution_queue_current.json"
DEFAULT_OUT_MD = "runs/wetlab_primary_hold_guard_surface_current.md"
DEFAULT_GUARD_LIMIT = 3


def _auto_hold_rows(rows: list[dict[str, Any]], *, target_id: str) -> list[dict[str, Any]]:
    target = str(target_id or "").strip()
    return [
        dict(row)
        for row in rows
        if str(row.get("target_id", "")).strip() == target
        and str(row.get("queue_status", "")).strip() == "explicit_hold"
        and "auto_hold_from_primary_watcher" in str(row.get("notes", "")).strip()
    ]



def _first_unresolved_target_row(rows: list[dict[str, Any]], *, target_id: str) -> dict[str, Any]:
    target = str(target_id or "").strip()
    target_rows = sorted(
        [dict(row) for row in rows if str(row.get("target_id", "")).strip() == target],
        key=lambda row: int(row.get("queue_rank", 0) or 0),
    )
    for row in target_rows:
        status = str(row.get("queue_status", "")).strip()
        if "result_ready" in status or "explicit_hold" in status:
            continue
        return dict(row)
    return {}



def _recommended_policy_action(*, total_auto_hold_count: int, streak: int, guard_limit: int, guard_triggered_now: bool, first_unresolved_row: dict[str, Any]) -> str:
    unresolved = bool(first_unresolved_row)
    unresolved_status = str(first_unresolved_row.get("queue_status", "")).strip()
    if guard_triggered_now:
        return "pause_target_autostart_and_review_retry_preset"
    if total_auto_hold_count == 0:
        return "continue_default_primary_watcher_policy"
    if unresolved and streak == guard_limit - 1:
        return "prepare_target_specific_retry_preset_before_next_auto_start"
    if unresolved and unresolved_status.startswith("running"):
        return "watch_active_retry_row_before_policy_change"
    if unresolved:
        return "continue_with_caution_and_monitor_next_auto_hold"
    return "target_fully_resolved_no_guard_action_needed"



def build_payload(execution_queue_payload: dict[str, Any], *, guard_limit: int = DEFAULT_GUARD_LIMIT) -> dict[str, Any]:
    rows = [dict(row) for row in (execution_queue_payload.get("rows", []) or [])]
    target_ids = sorted({str(row.get("target_id", "")).strip() for row in rows if str(row.get("target_id", "")).strip()})
    guard_rows: list[dict[str, Any]] = []
    triggered_count = 0

    for target_id in target_ids:
        auto_hold_rows = _auto_hold_rows(rows, target_id=target_id)
        first_unresolved = _first_unresolved_target_row(rows, target_id=target_id)
        first_unresolved_shard_id = str(first_unresolved.get("shard_id", "")).strip()
        streak = consecutive_auto_hold_streak(
            {"rows": rows},
            target_id=target_id,
            before_shard_id=first_unresolved_shard_id,
        )
        last_auto_hold_shard_id = str(auto_hold_rows[-1].get("shard_id", "")).strip() if auto_hold_rows else ""
        guard_triggered_now = bool(first_unresolved and streak >= int(guard_limit or 0))
        if guard_triggered_now:
            triggered_count += 1
        guard_rows.append(
            {
                "target_id": target_id,
                "total_auto_hold_count": len(auto_hold_rows),
                "recent_consecutive_auto_hold_streak": streak,
                "guard_limit": int(guard_limit or 0),
                "guard_triggered_now": guard_triggered_now,
                "last_auto_hold_shard_id": last_auto_hold_shard_id,
                "recommended_policy_action": _recommended_policy_action(
                    total_auto_hold_count=len(auto_hold_rows),
                    streak=streak,
                    guard_limit=int(guard_limit or 0),
                    guard_triggered_now=guard_triggered_now,
                    first_unresolved_row=first_unresolved,
                ),
            }
        )

    return {
        "summary": {
            "status": "wetlab_primary_hold_guard_surface_ready",
            "target_count": len(guard_rows),
            "guard_limit": int(guard_limit or 0),
            "triggered_target_count": triggered_count,
            "targets_with_any_auto_hold_count": sum(1 for row in guard_rows if int(row.get("total_auto_hold_count", 0) or 0) > 0),
            "next_required_step": "Review targets with guard_triggered_now=true before allowing further primary auto-start.",
        },
        "structured": {
            "execution_queue_artifact": "runs/wetlab_broad_screen_execution_queue_current.md",
        },
        "rows": guard_rows,
    }



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a target-level guard surface for repeated primary auto-holds.")
    parser.add_argument("--execution-queue-json", default=DEFAULT_EXECUTION_QUEUE_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--guard-limit", type=int, default=DEFAULT_GUARD_LIMIT)
    return parser.parse_args()



def main() -> None:
    args = parse_args()
    write_artifact(
        args.out_md,
        "Wet-Lab Primary Hold Guard Surface",
        build_payload(load_json(args.execution_queue_json), guard_limit=args.guard_limit),
    )



if __name__ == "__main__":
    main()
