#!/usr/bin/env python3
from __future__ import annotations

import argparse

from tools.wetlab_run_writer_utils import LIVE_PROGRESS_STATUSES, build_live_progress_payload
from tools.wetlab_target_render_utils import load_json, write_artifact

DEFAULT_LAUNCH_JSON = "runs/dpre1_launch_packet_current.json"
DEFAULT_OUT_MD = "runs/dpre1_live_progress_current.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write the canonical DprE1 live-progress artifact.")
    parser.add_argument("--launch-json", default=DEFAULT_LAUNCH_JSON)
    parser.add_argument("--status", choices=LIVE_PROGRESS_STATUSES, default="not_started")
    parser.add_argument("--active-stage-label", default="")
    parser.add_argument("--started-at", default="")
    parser.add_argument("--updated-at", default="")
    parser.add_argument("--notes", default="")
    return parser.parse_args()


def build_payload(launch_payload: dict, status: str = "not_started", active_stage_label: str = "", started_at: str = "", updated_at: str = "", notes: str = "") -> dict:
    launch_s = dict(launch_payload.get("summary", {}) or {})
    return build_live_progress_payload(
        target_id="DprE1",
        partner_track_id=str(launch_s.get("partner_track_id", "TB_Alliance")).strip() or "TB_Alliance",
        launch_artifact="runs/dpre1_launch_packet_current.md",
        launch_status=str(launch_s.get("status", "")).strip(),
        status=status,
        active_stage_label=active_stage_label,
        started_at=started_at,
        updated_at=updated_at,
        notes=notes,
    )


def main() -> None:
    args = parse_args()
    payload = build_payload(load_json(args.launch_json), status=args.status, active_stage_label=args.active_stage_label, started_at=args.started_at, updated_at=args.updated_at, notes=args.notes)
    write_artifact(DEFAULT_OUT_MD, "DprE1 Live Progress", payload)


if __name__ == "__main__":
    main()
