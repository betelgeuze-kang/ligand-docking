#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import maybe_load_json, write_artifact

DEFAULT_STK17B_RENDER_JSON = "runs/stk17b_render_suite_current.json"
DEFAULT_LBDHODH_RENDER_JSON = "runs/lbdhodh_render_suite_current.json"
DEFAULT_STK17B_LAUNCH_JSON = "runs/stk17b_launch_packet_current.json"
DEFAULT_LBDHODH_LAUNCH_JSON = "runs/lbdhodh_launch_packet_current.json"
DEFAULT_STK17B_RUN_RECORD_JSON = "runs/stk17b_run_record_current.json"
DEFAULT_LBDHODH_RUN_RECORD_JSON = "runs/lbdhodh_run_record_current.json"
DEFAULT_STK17B_RUN_STATUS_JSON = "runs/stk17b_run_status_current.json"
DEFAULT_LBDHODH_RESULT_REVIEW_JSON = "runs/lbdhodh_result_review_current.json"
DEFAULT_QUEUE_JSON = "runs/wetlab_wave1_tail_protein_run_queue_current.json"
DEFAULT_NEXT3_FINAL_REVIEW_JSON = "runs/alk2_result_review_current.json"
DEFAULT_OUT_MD = "runs/wetlab_wave1_tail_chain_stack_current.md"


def _summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict((payload or {}).get("summary", {}) or {})


def build_payload(
    stk17b_render: dict[str, Any] | None,
    lbdhodh_render: dict[str, Any] | None,
    stk17b_launch: dict[str, Any] | None,
    lbdhodh_launch: dict[str, Any] | None,
    stk17b_run_record: dict[str, Any] | None,
    lbdhodh_run_record: dict[str, Any] | None,
    stk17b_run_status: dict[str, Any] | None,
    lbdhodh_result_review: dict[str, Any] | None,
    tail_queue: dict[str, Any] | None,
    next3_final_review: dict[str, Any] | None,
) -> dict[str, Any]:
    srs = _summary(stk17b_render)
    drs = _summary(lbdhodh_render)
    sls = _summary(stk17b_launch)
    dls = _summary(lbdhodh_launch)
    srr = _summary(stk17b_run_record)
    drr = _summary(lbdhodh_run_record)
    sstatus = _summary(stk17b_run_status)
    dreview = _summary(lbdhodh_result_review)
    qs = _summary(tail_queue)
    n3 = _summary(next3_final_review)

    rows = [
        {
            "chain_item": "next3_final_review",
            "artifact_path": "runs/alk2_result_review_current.md",
            "current_signal": str(n3.get("next_queue_release_gate_status", "")).strip() or str(n3.get("status", "")).strip() or "missing",
            "queue_effect": "must_open_before_stk17b_can_leave_blocked_on_previous_review",
        },
        {
            "chain_item": "stk17b_run_status",
            "artifact_path": "runs/stk17b_run_status_current.md",
            "current_signal": str(sstatus.get("queue_status_now", "")).strip() or "missing",
            "queue_effect": "first_active_slot_in_wave1_tail",
        },
        {
            "chain_item": "lbdhodh_result_review",
            "artifact_path": "runs/lbdhodh_result_review_current.md",
            "current_signal": str(dreview.get("queue_status_now", "")).strip() or "missing",
            "queue_effect": "second_slot_gate_after_stk17b_resolution",
        },
        {
            "chain_item": "wave1_tail_protein_run_queue",
            "artifact_path": "runs/wetlab_wave1_tail_protein_run_queue_current.md",
            "current_signal": str(qs.get("status", "")).strip() or "missing",
            "queue_effect": "serialized_queue_source_of_truth_for_wave1_tail",
        },
    ]

    stk17b_run_record_ready = bool(
        str(srr.get("artifact_kind", "")).strip() == "run_record"
        and str(srr.get("target_id", "")).strip() == "STK17B (DRAK2)"
    )
    lbdhodh_run_record_ready = bool(
        str(drr.get("artifact_kind", "")).strip() == "run_record"
        and str(drr.get("target_id", "")).strip() == "Leishmania braziliensis DHODH"
    )

    return {
        "summary": {
            "status": "wetlab_wave1_tail_chain_stack_ready",
            "target_count": 2,
            "artifact_kind": "chain_stack",
            "next3_final_review_ready": bool(str(n3.get("status", "")).strip() == "alk2_result_review_ready"),
            "next3_final_gate_open": not bool(n3.get("next_queue_release_blocked", True)),
            "stk17b_render_suite_ready": bool(str(srs.get("status", "")).strip() == "stk17b_render_suite_ready"),
            "lbdhodh_render_suite_ready": bool(str(drs.get("status", "")).strip() == "lbdhodh_render_suite_ready"),
            "stk17b_launch_packet_ready": bool(str(sls.get("status", "")).strip() == "stk17b_launch_packet_ready"),
            "lbdhodh_launch_packet_ready": bool(str(dls.get("status", "")).strip() == "lbdhodh_launch_packet_ready"),
            "stk17b_run_record_ready": stk17b_run_record_ready,
            "lbdhodh_run_record_ready": lbdhodh_run_record_ready,
            "stk17b_run_status_ready": bool(str(sstatus.get("status", "")).strip() == "stk17b_run_status_ready"),
            "lbdhodh_result_review_ready": bool(str(dreview.get("status", "")).strip() == "lbdhodh_result_review_ready"),
            "wave1_tail_queue_ready": bool(str(qs.get("status", "")).strip() == "wetlab_wave1_tail_protein_run_queue_ready"),
            "stk17b_queue_status": str(sstatus.get("queue_status_now", "")).strip(),
            "lbdhodh_queue_status": str(dreview.get("queue_status_now", "")).strip(),
            "ready_now_target_count": int(qs.get("ready_now_target_count", 0) or 0),
            "blocked_on_previous_review_count": int(qs.get("blocked_on_previous_review_count", 0) or 0),
            "running_target_count": int(qs.get("running_target_count", 0) or 0),
            "resolved_target_count": int(qs.get("resolved_target_count", 0) or 0),
            "next_required_step": "Once the next3 final review opens the tail chain, run STK17B first, let LbDHODH open only after the STK17B live result resolves, and treat the LbDHODH review as the tail closer for Wave 1.",
        },
        "structured": {
            "execution_policy": "serialized_by_target_after_next3",
            "queue_artifact": "runs/wetlab_wave1_tail_protein_run_queue_current.md",
            "runtime_runbook_artifact": "runs/wetlab_wave1_tail_runtime_runbook_current.md",
            "execution_console_artifact": "runs/wetlab_wave1_tail_execution_console_current.md",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Wave 1 tail chain stack for STK17B -> LbDHODH.")
    parser.add_argument("--stk17b-render-json", default=DEFAULT_STK17B_RENDER_JSON)
    parser.add_argument("--lbdhodh-render-json", default=DEFAULT_LBDHODH_RENDER_JSON)
    parser.add_argument("--stk17b-launch-json", default=DEFAULT_STK17B_LAUNCH_JSON)
    parser.add_argument("--lbdhodh-launch-json", default=DEFAULT_LBDHODH_LAUNCH_JSON)
    parser.add_argument("--stk17b-run-record-json", default=DEFAULT_STK17B_RUN_RECORD_JSON)
    parser.add_argument("--lbdhodh-run-record-json", default=DEFAULT_LBDHODH_RUN_RECORD_JSON)
    parser.add_argument("--stk17b-run-status-json", default=DEFAULT_STK17B_RUN_STATUS_JSON)
    parser.add_argument("--lbdhodh-result-review-json", default=DEFAULT_LBDHODH_RESULT_REVIEW_JSON)
    parser.add_argument("--queue-json", default=DEFAULT_QUEUE_JSON)
    parser.add_argument("--next3-final-review-json", default=DEFAULT_NEXT3_FINAL_REVIEW_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        maybe_load_json(args.stk17b_render_json),
        maybe_load_json(args.lbdhodh_render_json),
        maybe_load_json(args.stk17b_launch_json),
        maybe_load_json(args.lbdhodh_launch_json),
        maybe_load_json(args.stk17b_run_record_json),
        maybe_load_json(args.lbdhodh_run_record_json),
        maybe_load_json(args.stk17b_run_status_json),
        maybe_load_json(args.lbdhodh_result_review_json),
        maybe_load_json(args.queue_json),
        maybe_load_json(args.next3_final_review_json),
    )
    write_artifact(DEFAULT_OUT_MD, "Wet-Lab Wave1 Tail Chain Stack", payload)


if __name__ == "__main__":
    main()
