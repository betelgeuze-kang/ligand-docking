#!/usr/bin/env python3
from __future__ import annotations

from tools.wetlab_target_render_utils import load_json, write_artifact

DEFAULT_QUEUE_JSON = "runs/wetlab_wave1_tail_protein_run_queue_current.json"
DEFAULT_REFRESH_JSON = "runs/wetlab_wave1_tail_gate_refresh_current.json"
DEFAULT_OUT_MD = "runs/wetlab_wave1_tail_runtime_runbook_current.md"


def build_payload(queue_payload: dict, refresh_payload: dict) -> dict:
    queue_s = dict(queue_payload.get("summary", {}) or {})
    refresh_s = dict(refresh_payload.get("summary", {}) or {})

    rows = [
        {
            "run_order": 1,
            "target_id": "STK17B (DRAK2)",
            "event": "start",
            "precondition": "queue_status=ready_after_previous_review",
            "command": "python3 tools/wetlab/run_wetlab_wave1_tail_runtime_event.py --target stk17b --event start --active-stage-label open_set_dark_kinase_primary_assay --started-at <started_at_iso> --updated-at <started_at_iso>",
            "expected_gate_artifact": "runs/stk17b_run_status_current.md",
            "expected_effect": "STK17B stays active_slot; LbDHODH remains blocked",
        },
        {
            "run_order": 2,
            "target_id": "STK17B (DRAK2)",
            "event": "complete",
            "precondition": "STK17B live run finished cleanly",
            "command": "python3 tools/wetlab/run_wetlab_wave1_tail_runtime_event.py --target stk17b --event complete --active-stage-label open_set_dark_kinase_primary_assay --decision-case stk17b_open_set_pass --action promote --started-at <started_at_iso> --updated-at <completed_at_iso> --completed-at <completed_at_iso>",
            "expected_gate_artifact": "runs/lbdhodh_result_review_current.md",
            "expected_effect": "LbDHODH gate opens for serialized tail slot 2",
        },
        {
            "run_order": 3,
            "target_id": "STK17B (DRAK2)",
            "event": "hold",
            "precondition": "STK17B needs explicit hold instead of clean completion",
            "command": "python3 tools/wetlab/run_wetlab_wave1_tail_runtime_event.py --target stk17b --event hold --active-stage-label open_set_dark_kinase_primary_assay --decision-case explicit_hold --action hold --started-at <started_at_iso> --updated-at <completed_at_iso> --completed-at <completed_at_iso>",
            "expected_gate_artifact": "runs/lbdhodh_result_review_current.md",
            "expected_effect": "LbDHODH gate still opens, but STK17B is carried as explicit_hold",
        },
        {
            "run_order": 4,
            "target_id": "Leishmania braziliensis DHODH",
            "event": "start",
            "precondition": "LbDHODH gate open after STK17B result-ready or explicit_hold",
            "command": "python3 tools/wetlab/run_wetlab_wave1_tail_runtime_event.py --target lbdhodh --event start --active-stage-label parasite_dhodh_primary_assay --started-at <started_at_iso> --updated-at <started_at_iso>",
            "expected_gate_artifact": "runs/lbdhodh_result_review_current.md",
            "expected_effect": "LbDHODH occupies the final serialized Wave 1 tail slot",
        },
        {
            "run_order": 5,
            "target_id": "Leishmania braziliensis DHODH",
            "event": "complete",
            "precondition": "LbDHODH result is ready",
            "command": "python3 tools/wetlab/run_wetlab_wave1_tail_runtime_event.py --target lbdhodh --event complete --active-stage-label parasite_dhodh_primary_assay --decision-case lbdhodh_host_separation_pass --action advance_to_wave1_completion_review --started-at <started_at_iso> --updated-at <completed_at_iso> --completed-at <completed_at_iso>",
            "expected_gate_artifact": "runs/lbdhodh_result_review_current.md",
            "expected_effect": "Wave 1 tail closes after LbDHODH result_ready",
        },
        {
            "run_order": 6,
            "target_id": "Leishmania braziliensis DHODH",
            "event": "hold",
            "precondition": "LbDHODH needs explicit hold instead of clean completion",
            "command": "python3 tools/wetlab/run_wetlab_wave1_tail_runtime_event.py --target lbdhodh --event hold --active-stage-label parasite_dhodh_primary_assay --decision-case explicit_hold --action hold --started-at <started_at_iso> --updated-at <completed_at_iso> --completed-at <completed_at_iso>",
            "expected_gate_artifact": "runs/lbdhodh_result_review_current.md",
            "expected_effect": "Wave 1 tail closes after LbDHODH explicit_hold",
        },
        {
            "run_order": 7,
            "target_id": "any",
            "event": "reset",
            "precondition": "use before a fresh dry-run or to clear stale writer state",
            "command": "python3 tools/wetlab/run_wetlab_wave1_tail_runtime_event.py --target <stk17b|lbdhodh> --event reset",
            "expected_gate_artifact": "runs/wetlab_wave1_tail_gate_refresh_current.md",
            "expected_effect": "resets writer state for the chosen target and rebuilds the serialized Wave 1 tail gate chain",
        },
    ]

    return {
        "summary": {
            "status": "wetlab_wave1_tail_runtime_runbook_ready",
            "target_count": 2,
            "command_row_count": len(rows),
            "queue_status": str(queue_s.get("status", "")).strip(),
            "ready_now_target_count": int(queue_s.get("ready_now_target_count", 0) or 0),
            "blocked_on_previous_review_count": int(queue_s.get("blocked_on_previous_review_count", 0) or 0),
            "refresh_status": str(refresh_s.get("status", "")).strip(),
            "stk17b_execution_state": str(refresh_s.get("stk17b_execution_state", "")).strip(),
            "lbdhodh_review_state": str(refresh_s.get("lbdhodh_review_state", "")).strip(),
            "next_required_step": "Use the STK17B start/complete events first. Once the refresh artifact shows the LbDHODH gate open, switch to the LbDHODH commands.",
        },
        "structured": {
            "runtime_event_artifact": "runs/wetlab_wave1_tail_runtime_event_current.md",
            "refresh_artifact": "runs/wetlab_wave1_tail_gate_refresh_current.md",
            "queue_artifact": "runs/wetlab_wave1_tail_protein_run_queue_current.md",
            "execution_policy": "serialized_by_target_with_parallel_prep_only",
        },
        "rows": rows,
    }


def main() -> None:
    payload = build_payload(load_json(DEFAULT_QUEUE_JSON), load_json(DEFAULT_REFRESH_JSON))
    write_artifact(DEFAULT_OUT_MD, "Wet-Lab Wave1 Tail Runtime Runbook", payload)


if __name__ == "__main__":
    main()
