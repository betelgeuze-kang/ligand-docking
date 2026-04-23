#!/usr/bin/env python3
from __future__ import annotations

import argparse

from tools.wetlab_hard_target_branch_builder import HardTargetBranchTemplate, build_operator_packet_payload
from tools.wetlab_target_render_utils import load_json, write_artifact

TEMPLATE = HardTargetBranchTemplate(
    branch_key="cathepsin_k_tuned",
    target_id="Cathepsin K",
    branch_label="cathepsin_k_tuned_branch",
    branch_state="promotion_ready_default_lane_closed",
    packet_scope="partner_operator_tuned_branch_review",
    operator_packet_status="wetlab_cathepsin_k_tuned_operator_packet_ready",
    branch_summary_status="wetlab_cathepsin_k_tuned_branch_summary_ready",
    review_unit_label="tuned branch operator packet",
    selected_command_kind="throughput_preflight_tuned_gate45",
    selected_threshold_a=4.5,
    default_lane_policy="keep_default_closed_branch_gate45_only",
    branch_mode="promote_tuned_branch",
    branch_summary_next_step="Promote Cathepsin K through the tuned gate4.5 branch, keep the default lane closed, and use the tuned operator packet as the review unit before any reopen decision.",
    operator_packet_next_step="Use the Cathepsin K tuned operator packet as the partner/operator review unit, keep the default lane closed, and treat gate4.5 as the active tuned branch while promotion is finalized.",
    operator_packet_surface_label="cathepsin_k_tuned_operator_packet",
)

DEFAULT_RESULT_SUMMARY_JSON = "runs/cathepsin_k_result_summary_current.json"
DEFAULT_RESULT_REVIEW_JSON = "runs/cathepsin_k_result_review_current.json"
DEFAULT_RUN_RECORD_JSON = "runs/cathepsin_k_run_record_current.json"
DEFAULT_TUNING_SURFACE_JSON = "runs/wetlab_cathepsin_k_stage6_tuning_surface_current.json"
DEFAULT_RETRY_LANE_JSON = "runs/wetlab_cathepsin_k_exploratory_retry_lane_current.json"
DEFAULT_OUT_MD = "runs/wetlab_cathepsin_k_tuned_operator_packet_current.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Cathepsin K tuned operator packet.")
    parser.add_argument("--result-summary-json", default=DEFAULT_RESULT_SUMMARY_JSON)
    parser.add_argument("--result-review-json", default=DEFAULT_RESULT_REVIEW_JSON)
    parser.add_argument("--run-record-json", default=DEFAULT_RUN_RECORD_JSON)
    parser.add_argument("--tuning-surface-json", default=DEFAULT_TUNING_SURFACE_JSON)
    parser.add_argument("--retry-lane-json", default=DEFAULT_RETRY_LANE_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def build_payload(
    result_summary_payload: dict,
    result_review_payload: dict,
    run_record_payload: dict,
    tuning_surface_payload: dict,
    retry_lane_payload: dict,
) -> dict:
    return build_operator_packet_payload(
        TEMPLATE,
        result_summary_payload=result_summary_payload,
        result_review_payload=result_review_payload,
        run_record_payload=run_record_payload,
        tuning_surface_payload=tuning_surface_payload,
        retry_lane_payload=retry_lane_payload,
    )


def main() -> None:
    args = parse_args()
    payload = build_payload(
        load_json(args.result_summary_json),
        load_json(args.result_review_json),
        load_json(args.run_record_json),
        load_json(args.tuning_surface_json),
        load_json(args.retry_lane_json),
    )
    write_artifact(args.out_md, "Wet-Lab Cathepsin K Tuned Operator Packet", payload)


if __name__ == "__main__":
    main()
