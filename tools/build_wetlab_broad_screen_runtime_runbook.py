#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, write_artifact

DEFAULT_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_execution_queue_current.json"
DEFAULT_OUT_MD = "runs/wetlab_broad_screen_runtime_runbook_current.md"


def build_payload(execution_queue: dict[str, Any]) -> dict[str, Any]:
    queue_summary = dict(execution_queue.get("summary", {}) or {})
    actionable = next(
        (
            dict(row)
            for row in (execution_queue.get("rows", []) or [])
            if str(row.get("queue_status", "")).startswith("ready") or "running" in str(row.get("queue_status", ""))
        ),
        {},
    )
    target_id = str(actionable.get("target_id", "")).strip()
    shard_id = str(actionable.get("shard_id", "")).strip()
    actionable_status = str(actionable.get("queue_status", "")).strip()
    commands = []
    if target_id and shard_id:
        commands = [
            {
                "step_rank": 1,
                "step_id": "start_first_actionable_shard",
                "target_id": target_id,
                "shard_id": shard_id,
                "command": str(actionable.get("launch_command", "")).strip(),
            },
            {
                "step_rank": 2,
                "step_id": "complete_first_actionable_shard",
                "target_id": target_id,
                "shard_id": shard_id,
                "command": str(actionable.get("complete_command", "")).strip(),
            },
            {
                "step_rank": 3,
                "step_id": "hold_first_actionable_shard",
                "target_id": target_id,
                "shard_id": shard_id,
                "command": str(actionable.get("hold_command", "")).strip(),
            },
            {
                "step_rank": 4,
                "step_id": "reset_first_actionable_shard",
                "target_id": target_id,
                "shard_id": shard_id,
                "command": str(actionable.get("reset_command", "")).strip(),
            },
        ]
    return {
        "summary": {
            "status": "wetlab_broad_screen_runtime_runbook_ready",
            "queue_row_count": int(queue_summary.get("queue_row_count", 0) or 0),
            "ready_now_row_count": int(queue_summary.get("ready_now_row_count", 0) or 0),
            "running_row_count": int(queue_summary.get("running_row_count", 0) or 0),
            "first_actionable_target_id": target_id,
            "first_actionable_shard_id": shard_id,
            "command_row_count": len(commands),
            "next_required_step": (
                f"Use the heartbeat or complete command for {target_id} shard {shard_id} while the active shard is running."
                if target_id and shard_id and "running" in actionable_status
                else f"Use the start command for {target_id} shard {shard_id}, then mark completion shard-by-shard until a target-level bulk result can be aggregated."
                if target_id and shard_id
                else "No actionable shard is open; resolve progress state or regenerate the broad-screen execution queue."
            ),
        },
        "structured": {
            "execution_queue_artifact": "runs/wetlab_broad_screen_execution_queue_current.md",
        },
        "rows": commands,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a runtime runbook for the broad 100k wet-lab screen.")
    parser.add_argument("--execution-queue-json", default=DEFAULT_EXECUTION_QUEUE_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    write_artifact(
        args.out_md,
        "Wet-Lab Broad Screen Runtime Runbook",
        build_payload(load_json(args.execution_queue_json)),
    )
