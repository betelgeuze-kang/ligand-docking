#!/usr/bin/env python3
from __future__ import annotations

import argparse

from tools.wetlab_run_writer_utils import RESULT_SUMMARY_STATUSES, build_result_summary_payload
from tools.wetlab_target_render_utils import load_json, write_artifact

DEFAULT_LAUNCH_JSON = "runs/dengue_ns2b_ns3_protease_launch_packet_current.json"
DEFAULT_GO_NO_GO_JSON = "runs/dengue_ns2b_ns3_protease_go_no_go_card_current.json"
DEFAULT_OUT_MD = "runs/dengue_ns2b_ns3_protease_result_summary_current.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write the canonical Dengue NS2B-NS3 protease result-summary artifact.")
    parser.add_argument("--launch-json", default=DEFAULT_LAUNCH_JSON)
    parser.add_argument("--go-no-go-json", default=DEFAULT_GO_NO_GO_JSON)
    parser.add_argument("--status", choices=RESULT_SUMMARY_STATUSES, default="not_ready")
    parser.add_argument("--decision-case", default="")
    parser.add_argument("--action", default="")
    parser.add_argument("--started-at", default="")
    parser.add_argument("--updated-at", default="")
    parser.add_argument("--completed-at", default="")
    parser.add_argument("--notes", default="")
    return parser.parse_args()


def build_payload(launch_payload: dict, go_no_go_payload: dict, status: str = "not_ready", decision_case: str = "", action: str = "", started_at: str = "", updated_at: str = "", completed_at: str = "", notes: str = "") -> dict:
    launch_s = dict(launch_payload.get("summary", {}) or {})
    go_s = dict(go_no_go_payload.get("summary", {}) or {})
    return build_result_summary_payload(
        target_id="Dengue NS2B-NS3 protease",
        partner_track_id=str(launch_s.get("partner_track_id", "IPK_dengue")).strip() or "IPK_dengue",
        launch_artifact="runs/dengue_ns2b_ns3_protease_launch_packet_current.md",
        launch_status=str(launch_s.get("status", "")).strip(),
        go_no_go_artifact="runs/dengue_ns2b_ns3_protease_go_no_go_card_current.md",
        go_no_go_status=str(go_s.get("status", "")).strip(),
        status=status,
        decision_case=decision_case,
        action=action,
        started_at=started_at,
        updated_at=updated_at,
        completed_at=completed_at,
        notes=notes,
    )


def main() -> None:
    args = parse_args()
    payload = build_payload(
        load_json(args.launch_json),
        load_json(args.go_no_go_json),
        status=args.status,
        decision_case=args.decision_case,
        action=args.action,
        started_at=args.started_at,
        updated_at=args.updated_at,
        completed_at=args.completed_at,
        notes=args.notes,
    )
    write_artifact(DEFAULT_OUT_MD, "Dengue NS2B-NS3 Protease Result Summary", payload)


if __name__ == "__main__":
    main()
