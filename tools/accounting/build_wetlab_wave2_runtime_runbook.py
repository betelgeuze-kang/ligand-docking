#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, write_artifact

DEFAULT_QUEUE_JSON = "runs/wetlab_wave2_protein_run_queue_current.json"
DEFAULT_OUT_MD = "runs/wetlab_wave2_runtime_runbook_current.md"


def build_payload(queue_payload: dict[str, Any]) -> dict[str, Any]:
    qs = dict(queue_payload.get("summary", {}) or {})
    rows = []
    next_rank = 1
    for row in queue_payload.get("rows", []) or []:
        target_id = str(row.get("target_id", "")).strip()
        slug = target_id.lower().replace(" ", "_").replace(".", "").replace("-", "_").replace("/", "_")
        placeholder_state = str(row.get("placeholder_state", "")).strip()
        queue_status = str(row.get("queue_status", "")).strip()
        if target_id == "Cathepsin K" and placeholder_state == "live_target_specific_packet_present":
            stage_label = "acidic_primary_protease_assay"
            complete_case = "promote_clean_cathepsin_k_acidic_bias"
            if queue_status in {"ready_first", "ready_after_previous_review"}:
                queue_note = "Cathepsin K is the live first Wave 2 slot; use start when the acidic-primary assay is actually beginning"
            elif "running" in queue_status:
                queue_note = "Cathepsin K is already running; use complete or hold only when the active run is actually being closed"
            else:
                queue_note = "Cathepsin K is real, but it stays blocked until the final2 release gate opens"
        elif target_id == "Dengue NS2B-NS3 protease" and placeholder_state == "live_target_specific_packet_present":
            stage_label = "flaviviral_shallow_pocket_primary_assay"
            complete_case = "promote_clean_dengue_shallow_pocket_bias"
            if queue_status in {"ready_first", "ready_after_previous_review"}:
                queue_note = "Dengue NS2B-NS3 is the live second Wave 2 slot; use start when the bounded shallow-pocket assay is actually beginning"
            elif "running" in queue_status:
                queue_note = "Dengue NS2B-NS3 is already running; use complete or hold only when the active shallow-pocket run is actually being closed"
            else:
                queue_note = "Dengue NS2B-NS3 is real, but it stays blocked until Cathepsin K resolves"
        else:
            stage_label = "pending_target_specific_packet"
            complete_case = "promote_clean_wave2_target"
            queue_note = "only valid once predecessor gates resolve and a real target packet exists"

        rows.append({"command_rank": next_rank, "target_id": target_id, "event": "start", "command": f"python3 tools/run_wetlab_wave2_runtime_event.py --target {slug} --event start --active-stage-label {stage_label}", "queue_note": queue_note})
        next_rank += 1
        rows.append({"command_rank": next_rank, "target_id": target_id, "event": "complete", "command": f"python3 tools/run_wetlab_wave2_runtime_event.py --target {slug} --event complete --active-stage-label {stage_label} --decision-case {complete_case} --action promote", "queue_note": queue_note})
        next_rank += 1
        rows.append({"command_rank": next_rank, "target_id": target_id, "event": "hold", "command": f"python3 tools/run_wetlab_wave2_runtime_event.py --target {slug} --event hold --active-stage-label {stage_label} --decision-case explicit_hold --action hold", "queue_note": queue_note})
        next_rank += 1
    rows.append({"command_rank": next_rank, "target_id": "all_wave2", "event": "reset", "command": "python3 tools/run_wetlab_wave2_runtime_event.py --target all_wave2 --event reset", "queue_note": "reset the whole Wave 2 chain"})
    return {
        "summary": {
            "status": "wetlab_wave2_runtime_runbook_ready",
            "target_count": int(qs.get("queue_target_count", 0) or 0),
            "command_row_count": len(rows),
            "ready_now_target_count": int(qs.get("ready_now_target_count", 0) or 0),
            "blocked_on_previous_review_count": int(qs.get("blocked_on_previous_review_count", 0) or 0),
            "blocked_on_target_content_count": int(qs.get("blocked_on_target_content_count", 0) or 0),
            "next_required_step": str(qs.get("next_required_step", "")).strip()
            or "Use the active queue row before issuing Wave 2 runtime commands.",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Wave 2 runtime runbook.")
    parser.add_argument("--queue-json", default=DEFAULT_QUEUE_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(load_json(args.queue_json))
    write_artifact(DEFAULT_OUT_MD, "Wet-Lab Wave2 Runtime Runbook", payload)


if __name__ == "__main__":
    main()
