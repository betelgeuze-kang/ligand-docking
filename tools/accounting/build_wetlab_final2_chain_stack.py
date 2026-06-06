#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, maybe_load_json, write_artifact

DEFAULT_STK17B_RENDER_JSON = "runs/stk17b_render_suite_current.json"
DEFAULT_LBDHODH_RENDER_JSON = "runs/lbdhodh_render_suite_current.json"
DEFAULT_STK17B_LAUNCH_JSON = "runs/stk17b_launch_packet_current.json"
DEFAULT_LBDHODH_LAUNCH_JSON = "runs/lbdhodh_launch_packet_current.json"
DEFAULT_STK17B_RUN_RECORD_JSON = "runs/stk17b_run_record_current.json"
DEFAULT_LBDHODH_RUN_RECORD_JSON = "runs/lbdhodh_run_record_current.json"
DEFAULT_STK17B_RUN_STATUS_JSON = "runs/stk17b_run_status_current.json"
DEFAULT_LBDHODH_RESULT_REVIEW_JSON = "runs/lbdhodh_result_review_current.json"
DEFAULT_QUEUE_JSON = "runs/wetlab_final2_protein_run_queue_current.json"
DEFAULT_NEXT3_FINAL_REVIEW_JSON = "runs/alk2_result_review_current.json"
DEFAULT_OUT_MD = "runs/wetlab_final2_chain_stack_current.md"


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
    final2_queue: dict[str, Any] | None,
    next3_final_review: dict[str, Any] | None,
) -> dict[str, Any]:
    srs = _summary(stk17b_render)
    lrs = _summary(lbdhodh_render)
    sls = _summary(stk17b_launch)
    lls = _summary(lbdhodh_launch)
    srr = _summary(stk17b_run_record)
    lrr = _summary(lbdhodh_run_record)
    sst = _summary(stk17b_run_status)
    lrv = _summary(lbdhodh_result_review)
    qs = _summary(final2_queue)
    n3 = _summary(next3_final_review)

    rows = [
        {"chain_item": "next3_final_review", "artifact_path": "runs/alk2_result_review_current.md", "current_signal": str(n3.get("next_queue_release_gate_status", "")).strip() or str(n3.get("status", "")).strip() or "missing", "queue_effect": "must_open_before_stk17b_can_leave_blocked_on_previous_review"},
        {"chain_item": "stk17b_run_status", "artifact_path": "runs/stk17b_run_status_current.md", "current_signal": str(sst.get("queue_status_now", "")).strip() or "missing", "queue_effect": "first_active_slot_in_final2"},
        {"chain_item": "lbdhodh_result_review", "artifact_path": "runs/lbdhodh_result_review_current.md", "current_signal": str(lrv.get("queue_status_now", "")).strip() or "missing", "queue_effect": "second_slot_gate_after_stk17b_resolution_and_content_fill"},
        {"chain_item": "final2_protein_run_queue", "artifact_path": "runs/wetlab_final2_protein_run_queue_current.md", "current_signal": str(qs.get("status", "")).strip() or "missing", "queue_effect": "serialized_tail_queue_state"},
    ]
    stack_gate_states = {
        "stk17b": {
            "queue_status": str(sst.get("queue_status_now", "")).strip(),
            "execution_state": str(sst.get("execution_state", "")).strip(),
        },
        "lbdhodh": {
            "queue_status": str(lrv.get("queue_status_now", "")).strip(),
            "execution_state": str(lrr.get("execution_state", "")).strip(),
            "content_ready": str(lls.get("launch_readiness", "")).strip() == "ready_for_serialized_execution",
            "upstream_gate_open": not bool(n3.get("next_queue_release_blocked", True)),
        },
    }
    lbdhodh_blockers = {
        "upstream_stk17b_result_review": "blocked" if bool(n3.get("next_queue_release_blocked", True)) else "clear",
        "compound_fill": "blocked" if str(lls.get("launch_readiness", "")).strip() != "ready_for_serialized_execution" else "clear",
    }
    return {
        "summary": {
            "status": "wetlab_final2_chain_stack_ready",
            "priority3_final_review_ready": True,
            "next3_final_review_ready": bool(n3),
            "next3_final_gate_open": not bool(n3.get("next_queue_release_blocked", True)),
            "stk17b_render_ready": str(srs.get("status", "")).strip() == "stk17b_render_suite_ready",
            "lbdhodh_render_ready": str(lrs.get("status", "")).strip() == "lbdhodh_render_suite_ready",
            "stk17b_launch_ready": str(sls.get("status", "")).strip() == "stk17b_launch_packet_ready",
            "lbdhodh_launch_ready": str(lls.get("status", "")).strip() == "lbdhodh_launch_packet_ready",
            "stk17b_run_record_ready": bool(srr.get("artifact_kind", "") == "run_record" and srr.get("target_id", "") == "STK17B (DRAK2)"),
            "lbdhodh_run_record_ready": bool(lrr.get("artifact_kind", "") == "run_record" and lrr.get("target_id", "") == "Leishmania braziliensis DHODH"),
            "stk17b_run_status_ready": str(sst.get("status", "")).strip() == "stk17b_run_status_ready",
            "lbdhodh_result_review_ready": str(lrv.get("status", "")).strip() == "lbdhodh_result_review_ready",
            "final2_queue_ready": str(qs.get("status", "")).strip() == "wetlab_final2_protein_run_queue_ready",
            "lbdhodh_content_ready": str(lls.get("launch_readiness", "")).strip() == "ready_for_serialized_execution",
            "stk17b_queue_status": str(sst.get("queue_status_now", "")).strip(),
            "stk17b_execution_state": str(sst.get("execution_state", "")).strip(),
            "lbdhodh_queue_status": str(lrv.get("queue_status_now", "")).strip(),
            "lbdhodh_execution_state": str(lrr.get("execution_state", "")).strip(),
            "stack_gate_states": stack_gate_states,
            "lbdhodh_blockers": lbdhodh_blockers,
            "next_required_step": "Finish priority3 and next3 first, then continue into the final2 tail through STK17B -> LbDHODH while keeping LbDHODH blocked until compound fill is real.",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build the final2 chain stack summary.")
    p.add_argument("--stk17b-render-json", default=DEFAULT_STK17B_RENDER_JSON)
    p.add_argument("--lbdhodh-render-json", default=DEFAULT_LBDHODH_RENDER_JSON)
    p.add_argument("--stk17b-launch-json", default=DEFAULT_STK17B_LAUNCH_JSON)
    p.add_argument("--lbdhodh-launch-json", default=DEFAULT_LBDHODH_LAUNCH_JSON)
    p.add_argument("--stk17b-run-record-json", default=DEFAULT_STK17B_RUN_RECORD_JSON)
    p.add_argument("--lbdhodh-run-record-json", default=DEFAULT_LBDHODH_RUN_RECORD_JSON)
    p.add_argument("--stk17b-run-status-json", default=DEFAULT_STK17B_RUN_STATUS_JSON)
    p.add_argument("--lbdhodh-result-review-json", default=DEFAULT_LBDHODH_RESULT_REVIEW_JSON)
    p.add_argument("--queue-json", default=DEFAULT_QUEUE_JSON)
    p.add_argument("--next3-final-review-json", default=DEFAULT_NEXT3_FINAL_REVIEW_JSON)
    return p.parse_args()


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
    write_artifact(DEFAULT_OUT_MD, "Wet-Lab Final2 Chain Stack", payload)


if __name__ == "__main__":
    main()
