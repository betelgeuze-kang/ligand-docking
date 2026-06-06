#!/usr/bin/env python3
from __future__ import annotations

import argparse

from tools.wetlab_target_render_utils import load_json, write_artifact

DEFAULT_QUEUE_JSON = "runs/wetlab_final2_protein_run_queue_current.json"
DEFAULT_OUT_MD = "runs/wetlab_final2_runtime_runbook_current.md"


def build_payload(queue_payload: dict) -> dict:
    qs = dict(queue_payload.get("summary", {}) or {})
    rows = [
        {"command_rank": 1, "target_id": "STK17B (DRAK2)", "event": "start", "command": "python3 tools/run_wetlab_final2_runtime_event.py --target stk17b --event start --active-stage-label dsf_or_biochemical_entry --started-at <iso> --updated-at <iso>", "queue_note": "first final2 slot once next3 resolves"},
        {"command_rank": 2, "target_id": "STK17B (DRAK2)", "event": "complete", "command": "python3 tools/run_wetlab_final2_runtime_event.py --target stk17b --event complete --active-stage-label dsf_or_biochemical_entry --decision-case promote_clean_stk17b_favored --action promote --started-at <iso> --updated-at <iso> --completed-at <iso>", "queue_note": "opens LbDHODH review if resolved or explicit hold"},
        {"command_rank": 3, "target_id": "STK17B (DRAK2)", "event": "hold", "command": "python3 tools/run_wetlab_final2_runtime_event.py --target stk17b --event hold --active-stage-label dsf_or_biochemical_entry --decision-case hold_probe_frame_ambiguous --action hold --started-at <iso> --updated-at <iso> --completed-at <iso>", "queue_note": "keeps final2 honest while still allowing review transition"},
        {"command_rank": 4, "target_id": "Leishmania braziliensis DHODH", "event": "start", "command": "python3 tools/run_wetlab_final2_runtime_event.py --target lbdhodh --event start --active-stage-label recombinant_dhodh_primary_assay --started-at <iso> --updated-at <iso>", "queue_note": "only valid after STK17B resolves and compound fill is complete"},
        {"command_rank": 5, "target_id": "Leishmania braziliensis DHODH", "event": "complete", "command": "python3 tools/run_wetlab_final2_runtime_event.py --target lbdhodh --event complete --active-stage-label recombinant_dhodh_primary_assay --decision-case promote_clean_lbdhodh_favored --action promote --started-at <iso> --updated-at <iso> --completed-at <iso>", "queue_note": "closes the final Wave 1 tail release gate"},
        {"command_rank": 6, "target_id": "Leishmania braziliensis DHODH", "event": "hold", "command": "python3 tools/run_wetlab_final2_runtime_event.py --target lbdhodh --event hold --active-stage-label recombinant_dhodh_primary_assay --decision-case hold_pending_compound_fill --action hold --started-at <iso> --updated-at <iso> --completed-at <iso>", "queue_note": "use when content-fill or host-separation review is still unresolved"},
        {"command_rank": 7, "target_id": "all_final2", "event": "reset", "command": "python3 tools/run_wetlab_final2_runtime_event.py --target stk17b --event reset && python3 tools/run_wetlab_final2_runtime_event.py --target lbdhodh --event reset", "queue_note": "reset the final2 runtime chain safely"},
    ]
    return {
        "summary": {
            "status": "wetlab_final2_runtime_runbook_ready",
            "target_count": 2,
            "command_row_count": len(rows),
            "ready_now_target_count": int(qs.get("ready_now_target_count", 0) or 0),
            "blocked_on_previous_review_count": int(qs.get("blocked_on_previous_review_count", 0) or 0),
            "blocked_on_target_content_count": int(qs.get("blocked_on_target_content_count", 0) or 0),
            "next_required_step": "Use this runbook only after next3 resolves; LbDHODH start remains invalid until compound fill is complete.",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the final2 runtime runbook.")
    parser.add_argument("--queue-json", default=DEFAULT_QUEUE_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(load_json(args.queue_json))
    write_artifact(DEFAULT_OUT_MD, "Wet-Lab Final2 Runtime Runbook", payload)


if __name__ == "__main__":
    main()
