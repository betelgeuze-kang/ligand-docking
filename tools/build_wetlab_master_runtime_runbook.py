#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, write_artifact

DEFAULT_PRIORITY3_RUNBOOK_JSON = "runs/wetlab_priority3_runtime_runbook_current.json"
DEFAULT_NEXT3_RUNBOOK_JSON = "runs/wetlab_next3_runtime_runbook_current.json"
DEFAULT_FINAL2_RUNBOOK_JSON = "runs/wetlab_final2_runtime_runbook_current.json"
DEFAULT_WAVE2_RUNBOOK_JSON = "runs/wetlab_wave2_runtime_runbook_current.json"
DEFAULT_MASTER_QUEUE_JSON = "runs/wetlab_master_execution_queue_current.json"
DEFAULT_OUT_MD = "runs/wetlab_master_runtime_runbook_current.md"


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    return dict(payload.get("summary", {}) or {})


def _chain_rows(payload: dict[str, Any], chain_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in payload.get("rows", []) or []:
        item = dict(row)
        item["chain_id"] = chain_id
        rows.append(item)
    return rows


def build_payload(
    master_queue: dict[str, Any],
    priority3_runbook: dict[str, Any],
    next3_runbook: dict[str, Any],
    final2_runbook: dict[str, Any],
    wave2_runbook: dict[str, Any] | None = None,
) -> dict[str, Any]:
    mqs = _summary(master_queue)
    rows = [
        *_chain_rows(priority3_runbook, "priority3"),
        *_chain_rows(next3_runbook, "next3"),
        *_chain_rows(final2_runbook, "final2"),
        *_chain_rows(wave2_runbook or {}, "wave2"),
    ]
    return {
        "summary": {
            "status": "wetlab_master_runtime_runbook_ready",
            "chain_count": 4 if wave2_runbook is not None else 3,
            "command_row_count": len(rows),
            "ready_now_target_count": int(mqs.get("ready_now_target_count", 0) or 0),
            "blocked_on_previous_review_count": int(mqs.get("blocked_on_previous_review_count", 0) or 0),
            "blocked_on_target_content_count": int(mqs.get("blocked_on_target_content_count", 0) or 0),
            "wave2_release_gate_status": str(mqs.get("wave2_release_gate_status", "")).strip(),
            "wave2_release_blocked": bool(mqs.get("wave2_release_blocked", True)),
            "wave2_ready": bool(mqs.get("wave2_ready", False)),
            "wave2_queue_status": str(mqs.get("wave2_queue_status", "")).strip(),
            "next_required_step": "Use the chain-specific runtime command for the first actionable target shown in the master queue, and keep every downstream chain blocked until upstream reviews resolve.",
        },
        "structured": {
            "master_queue_artifact": "runs/wetlab_master_execution_queue_current.md",
            "priority3_runbook_artifact": "runs/wetlab_priority3_runtime_runbook_current.md",
            "next3_runbook_artifact": "runs/wetlab_next3_runtime_runbook_current.md",
            "final2_runbook_artifact": "runs/wetlab_final2_runtime_runbook_current.md",
            "wave2_runbook_artifact": "runs/wetlab_wave2_runtime_runbook_current.md",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the master runtime runbook across all serialized wet-lab chains.")
    parser.add_argument("--master-queue-json", default=DEFAULT_MASTER_QUEUE_JSON)
    parser.add_argument("--priority3-runbook-json", default=DEFAULT_PRIORITY3_RUNBOOK_JSON)
    parser.add_argument("--next3-runbook-json", default=DEFAULT_NEXT3_RUNBOOK_JSON)
    parser.add_argument("--final2-runbook-json", default=DEFAULT_FINAL2_RUNBOOK_JSON)
    parser.add_argument("--wave2-runbook-json", default=DEFAULT_WAVE2_RUNBOOK_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        load_json(args.master_queue_json),
        load_json(args.priority3_runbook_json),
        load_json(args.next3_runbook_json),
        load_json(args.final2_runbook_json),
        load_json(args.wave2_runbook_json),
    )
    write_artifact(DEFAULT_OUT_MD, "Wet-Lab Master Runtime Runbook", payload)


if __name__ == "__main__":
    main()
