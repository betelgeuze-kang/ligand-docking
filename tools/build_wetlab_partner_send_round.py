#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, rows_by_track, write_artifact

DEFAULT_OUTBOUND_BOARD_JSON = "runs/wetlab_outbound_execution_priority_board_current.json"
DEFAULT_EXPORT_BUNDLE_JSON = "runs/wetlab_partner_first_contact_export_bundle_current.json"
DEFAULT_OUT_MD = "runs/wetlab_partner_send_round_current.md"


def _summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict((payload or {}).get("summary", {}) or {})


def build_payload(
    outbound_board: dict[str, Any],
    export_bundle: dict[str, Any],
) -> dict[str, Any]:
    obs = _summary(outbound_board)
    ebs = _summary(export_bundle)
    export_rows = rows_by_track(export_bundle)

    rows: list[dict[str, Any]] = []
    for board_row in outbound_board.get("rows", []) or []:
        track_id = str(board_row.get("track_id", "")).strip()
        export_row = export_rows.get(track_id, {})
        if not track_id or not export_row:
            continue
        rows.append(
            {
                "dispatch_rank": int(board_row.get("priority_rank", 0) or 0),
                "track_id": track_id,
                "track_label": str(export_row.get("track_label", "")).strip(),
                "dispatch_status": "send_ready_manual_dispatch"
                if str(export_row.get("status", "")).strip() == "ready_to_send"
                else "hold",
                "lead_targets": str(export_row.get("lead_targets", "")).strip(),
                "email_subject": str(export_row.get("email_subject", "")).strip(),
                "proposal_title": str(export_row.get("proposal_title", "")).strip(),
                "attachment_artifacts": str(export_row.get("attachment_artifacts", "")).strip(),
                "sender_name": str(ebs.get("sender_name", "")).strip(),
                "sender_affiliation": str(ebs.get("sender_affiliation", "")).strip(),
                "dispatch_note": (
                    "Use the email body from the export bundle as-is; this round is already copy-polished."
                    if str(export_row.get("status", "")).strip() == "ready_to_send"
                    else "Do not send yet."
                ),
            }
        )

    rows.sort(key=lambda row: (row["dispatch_rank"], row["track_id"]))

    return {
        "summary": {
            "status": "wetlab_partner_send_round_ready",
            "dispatch_track_count": len(rows),
            "send_ready_track_count": sum(1 for row in rows if row["dispatch_status"] == "send_ready_manual_dispatch"),
            "first_dispatch_track_id": rows[0]["track_id"] if rows else "",
            "first_dispatch_lead_targets": rows[0]["lead_targets"] if rows else "",
            "sender_name": str(ebs.get("sender_name", "")).strip(),
            "sender_affiliation": str(ebs.get("sender_affiliation", "")).strip(),
            "next_required_step": "Dispatch the tracks in rank order using the export bundle email bodies and attachment sets, starting with DNDi/IPK.",
        },
        "structured": {
            "outbound_priority_board_artifact": "runs/wetlab_outbound_execution_priority_board_current.md",
            "partner_export_bundle_artifact": "runs/wetlab_partner_first_contact_export_bundle_current.md",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the wet-lab partner send round artifact.")
    parser.add_argument("--outbound-board-json", default=DEFAULT_OUTBOUND_BOARD_JSON)
    parser.add_argument("--export-bundle-json", default=DEFAULT_EXPORT_BUNDLE_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    payload = build_payload(
        load_json(args.outbound_board_json),
        load_json(args.export_bundle_json),
    )
    write_artifact(args.out_md, "Wet-Lab Partner Send Round", payload)
