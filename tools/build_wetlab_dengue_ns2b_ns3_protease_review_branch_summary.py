#!/usr/bin/env python3
from __future__ import annotations

import argparse

from tools.build_wetlab_dengue_ns2b_ns3_protease_operator_packet import TEMPLATE
from tools.wetlab_hard_target_branch_builder import build_branch_summary_payload
from tools.wetlab_target_render_utils import load_json, write_artifact

DEFAULT_OPERATOR_PACKET_JSON = "runs/wetlab_dengue_ns2b_ns3_protease_operator_packet_current.json"
DEFAULT_RESULT_SUMMARY_JSON = "runs/dengue_ns2b_ns3_protease_result_summary_current.json"
DEFAULT_RESULT_REVIEW_JSON = "runs/dengue_ns2b_ns3_protease_result_review_current.json"
DEFAULT_RUN_RECORD_JSON = "runs/dengue_ns2b_ns3_protease_run_record_current.json"
DEFAULT_TUNING_SURFACE_JSON = "runs/wetlab_dengue_ns2b_ns3_protease_stage6_tuning_surface_current.json"
DEFAULT_RETRY_LANE_JSON = "runs/wetlab_dengue_ns2b_ns3_protease_exploratory_retry_lane_current.json"
DEFAULT_OUT_MD = "runs/wetlab_dengue_ns2b_ns3_protease_review_branch_summary_current.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Dengue NS2B-NS3 protease review branch summary.")
    parser.add_argument("--operator-packet-json", default=DEFAULT_OPERATOR_PACKET_JSON)
    parser.add_argument("--result-summary-json", default=DEFAULT_RESULT_SUMMARY_JSON)
    parser.add_argument("--result-review-json", default=DEFAULT_RESULT_REVIEW_JSON)
    parser.add_argument("--run-record-json", default=DEFAULT_RUN_RECORD_JSON)
    parser.add_argument("--tuning-surface-json", default=DEFAULT_TUNING_SURFACE_JSON)
    parser.add_argument("--retry-lane-json", default=DEFAULT_RETRY_LANE_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def build_payload(
    operator_packet_payload: dict,
    result_summary_payload: dict,
    result_review_payload: dict,
    run_record_payload: dict,
    tuning_surface_payload: dict,
    retry_lane_payload: dict,
) -> dict:
    return build_branch_summary_payload(
        TEMPLATE,
        operator_packet_payload=operator_packet_payload,
        result_summary_payload=result_summary_payload,
        result_review_payload=result_review_payload,
        run_record_payload=run_record_payload,
        tuning_surface_payload=tuning_surface_payload,
        retry_lane_payload=retry_lane_payload,
    )


def main() -> None:
    args = parse_args()
    payload = build_payload(
        load_json(args.operator_packet_json),
        load_json(args.result_summary_json),
        load_json(args.result_review_json),
        load_json(args.run_record_json),
        load_json(args.tuning_surface_json),
        load_json(args.retry_lane_json),
    )
    write_artifact(args.out_md, "Wet-Lab Dengue NS2B-NS3 Protease Review Branch Summary", payload)


if __name__ == "__main__":
    main()
