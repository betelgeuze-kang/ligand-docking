#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, write_artifact

DEFAULT_MASTER_QUEUE_JSON = "runs/wetlab_master_execution_queue_current.json"
DEFAULT_MASTER_CONSOLE_JSON = "runs/wetlab_master_execution_console_current.json"
DEFAULT_PARTNER_EXPORT_JSON = "runs/wetlab_partner_first_contact_export_bundle_current.json"
DEFAULT_OUTREACH_TRACKS_JSON = "runs/wetlab_partner_outreach_tracks_current.json"
DEFAULT_OUT_MD = "runs/wetlab_master_terminal_review_current.md"


def _summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict((payload or {}).get("summary", {}) or {})


def build_payload(
    master_queue: dict[str, Any],
    master_console: dict[str, Any],
    partner_export_bundle: dict[str, Any],
    outreach_tracks: dict[str, Any],
) -> dict[str, Any]:
    mqs = _summary(master_queue)
    mcs = _summary(master_console)
    pes = _summary(partner_export_bundle)
    ots = _summary(outreach_tracks)

    stack_gate_states = dict(mqs.get("stack_gate_states", {}) or mcs.get("stack_gate_states", {}) or {})
    rows: list[dict[str, Any]] = []
    all_chains_resolved = True
    for chain_id, state in stack_gate_states.items():
        chain_state = dict(state or {})
        chain_resolved = bool(chain_state.get("all_rows_resolved", False))
        all_chains_resolved = all_chains_resolved and chain_resolved
        rows.append(
            {
                "chain_id": chain_id,
                "chain_rank": int(chain_state.get("chain_rank", 0) or 0),
                "queue_target_count": int(chain_state.get("queue_target_count", 0) or 0),
                "resolved_target_count": int(chain_state.get("resolved_target_count", 0) or 0),
                "all_rows_resolved": chain_resolved,
                "active_target_id": str(chain_state.get("active_target_id", "")).strip(),
                "active_target_queue_status": str(chain_state.get("active_target_queue_status", "")).strip(),
                "active_target_execution_state": str(chain_state.get("active_target_execution_state", "")).strip(),
                "terminal_state": "complete" if chain_resolved else "pending",
            }
        )

    rows.sort(key=lambda row: (row["chain_rank"], row["chain_id"]))

    queue_target_count = int(mqs.get("queue_target_count", 0) or 0)
    resolved_target_count = int(mqs.get("resolved_target_count", 0) or 0)
    running_target_count = int(mqs.get("running_target_count", 0) or 0)
    ready_now_target_count = int(mqs.get("ready_now_target_count", 0) or 0)
    active_target_id = str(mqs.get("active_target_id", "") or mcs.get("active_target_id", "")).strip()

    campaign_terminal_state = (
        "complete"
        if all_chains_resolved
        and queue_target_count > 0
        and resolved_target_count == queue_target_count
        and running_target_count == 0
        and ready_now_target_count == 0
        and active_target_id == ""
        else "pending"
    )

    ready_tracks = [
        str(row.get("track_id", "")).strip()
        for row in partner_export_bundle.get("rows", []) or []
        if str(row.get("status", "")).strip() == "ready_to_send"
    ]

    return {
        "summary": {
            "status": "wetlab_master_terminal_review_ready",
            "campaign_terminal_state": campaign_terminal_state,
            "chain_count": len(rows),
            "queue_target_count": queue_target_count,
            "resolved_target_count": resolved_target_count,
            "running_target_count": running_target_count,
            "ready_now_target_count": ready_now_target_count,
            "active_target_id": active_target_id,
            "all_chains_resolved": all_chains_resolved,
            "ready_to_send_track_count": int(pes.get("ready_to_send_count", 0) or 0),
            "ready_to_send_tracks": "; ".join(ready_tracks),
            "canonical_track_order": str(ots.get("primary_track_order", "")).strip(),
            "next_required_step": (
                "Use the final campaign summary and outbound execution priority board to drive partner-facing handoff."
                if campaign_terminal_state == "complete"
                else "Keep resolving serialized chains until the active target clears and every chain reports all_rows_resolved=true."
            ),
        },
        "structured": {
            "master_queue_artifact": "runs/wetlab_master_execution_queue_current.md",
            "master_console_artifact": "runs/wetlab_master_execution_console_current.md",
            "partner_export_bundle_artifact": "runs/wetlab_partner_first_contact_export_bundle_current.md",
            "outreach_tracks_artifact": "runs/wetlab_partner_outreach_tracks_current.md",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the wet-lab master terminal review artifact.")
    parser.add_argument("--master-queue-json", default=DEFAULT_MASTER_QUEUE_JSON)
    parser.add_argument("--master-console-json", default=DEFAULT_MASTER_CONSOLE_JSON)
    parser.add_argument("--partner-export-json", default=DEFAULT_PARTNER_EXPORT_JSON)
    parser.add_argument("--outreach-tracks-json", default=DEFAULT_OUTREACH_TRACKS_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    payload = build_payload(
        load_json(args.master_queue_json),
        load_json(args.master_console_json),
        load_json(args.partner_export_json),
        load_json(args.outreach_tracks_json),
    )
    write_artifact(args.out_md, "Wet-Lab Master Terminal Review", payload)
