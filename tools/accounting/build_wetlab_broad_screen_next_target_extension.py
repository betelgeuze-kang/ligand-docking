#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, maybe_load_json, write_artifact

DEFAULT_QUEUE_JSON = "runs/wetlab_broad_screen_queue_current.json"
DEFAULT_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_execution_queue_current.json"
DEFAULT_ANTITARGET_QUEUE_JSON = "runs/wetlab_broad_screen_antitarget_queue_current.json"
DEFAULT_ACTUAL_APPEND_JSON = "runs/wetlab_broad_screen_actual_append_current.json"
DEFAULT_OUT_MD = "runs/wetlab_broad_screen_next_target_extension_current.md"


def _slug(target_id: str) -> str:
    return (
        target_id.lower()
        .replace(".", "")
        .replace("-", "_")
        .replace("/", "_")
        .replace("(", "")
        .replace(")", "")
        .replace(" ", "_")
    )


def build_payload(
    broad_queue: dict[str, Any],
    execution_queue: dict[str, Any],
    antitarget_queue: dict[str, Any] | None = None,
    actual_append: dict[str, Any] | None = None,
) -> dict[str, Any]:
    queue_rows = [dict(row) for row in (broad_queue.get("rows", []) or [])]
    target_order: list[str] = []
    for row in queue_rows:
        target_id = str(row.get("target_id", "")).strip()
        if target_id and target_id not in target_order:
            target_order.append(target_id)

    next_target_id = target_order[1] if len(target_order) > 1 else ""
    target_rows = [row for row in queue_rows if str(row.get("target_id", "")).strip() == next_target_id]
    target_exec_rows = [
        dict(row)
        for row in ((execution_queue or {}).get("rows", []) or [])
        if str(row.get("target_id", "")).strip() == next_target_id
    ]
    target_antitarget_rows = [
        dict(row)
        for row in ((antitarget_queue or {}).get("rows", []) or [])
        if str(row.get("primary_target_id", "")).strip() == next_target_id
    ]

    first_primary_shard_id = str(target_rows[0].get("shard_id", "")).strip() if target_rows else ""
    first_primary_exec_status = str(target_exec_rows[0].get("queue_status", "")).strip() if target_exec_rows else ""
    first_antitarget_id = str(target_antitarget_rows[0].get("anti_target_id", "")).strip() if target_antitarget_rows else ""
    first_antitarget_status = str(target_antitarget_rows[0].get("queue_status", "")).strip() if target_antitarget_rows else ""

    return {
        "summary": {
            "status": "wetlab_broad_screen_next_target_extension_ready",
            "next_target_id": next_target_id,
            "primary_shard_id": first_primary_shard_id,
            "primary_queue_status": first_primary_exec_status,
            "anti_target_id": first_antitarget_id,
            "anti_target_queue_status": first_antitarget_status,
            "auto_append_ready": bool(
                str((actual_append or {}).get("summary", {}).get("status", "")).strip().startswith("wetlab_broad_screen_actual_append_")
            ),
            "next_required_step": (
                f"Keep {next_target_id} shard {first_primary_shard_id} intake packet ready so the same broad-screen pattern can extend immediately after the current target resolves."
                if next_target_id and first_primary_shard_id
                else "No next primary target is available to extend yet."
            ),
        },
        "structured": {
            "primary_intake_packet_artifact": f"runs/{_slug(next_target_id)}_broad_screen_shard_01_intake_packet_current.md" if next_target_id else "",
            "execution_queue_artifact": "runs/wetlab_broad_screen_execution_queue_current.md",
            "antitarget_queue_artifact": "runs/wetlab_broad_screen_antitarget_queue_current.md",
            "actual_append_artifact": "runs/wetlab_broad_screen_actual_append_current.md",
        },
        "rows": [
            {
                "target_id": next_target_id,
                "first_primary_shard_id": first_primary_shard_id,
                "first_primary_queue_status": first_primary_exec_status,
                "first_antitarget_id": first_antitarget_id,
                "first_antitarget_queue_status": first_antitarget_status,
                "target_row_count": len(target_rows),
                "antitarget_row_count": len(target_antitarget_rows),
            }
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a next-target extension surface for the broad-screen pattern.")
    parser.add_argument("--queue-json", default=DEFAULT_QUEUE_JSON)
    parser.add_argument("--execution-queue-json", default=DEFAULT_EXECUTION_QUEUE_JSON)
    parser.add_argument("--antitarget-queue-json", default=DEFAULT_ANTITARGET_QUEUE_JSON)
    parser.add_argument("--actual-append-json", default=DEFAULT_ACTUAL_APPEND_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    write_artifact(
        args.out_md,
        "Wet-Lab Broad Screen Next Target Extension",
        build_payload(
            broad_queue=load_json(args.queue_json),
            execution_queue=load_json(args.execution_queue_json),
            antitarget_queue=maybe_load_json(args.antitarget_queue_json),
            actual_append=maybe_load_json(args.actual_append_json),
        ),
    )
