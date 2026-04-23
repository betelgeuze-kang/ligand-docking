#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_cathepsin_k_rescue_utils import (
    TARGET_ID,
    build_rescue_review_snapshot,
    maybe_load_json,
)
from tools.wetlab_target_render_utils import load_json, write_artifact

DEFAULT_STAGE6_TUNING_SURFACE_JSON = "runs/wetlab_cathepsin_k_stage6_tuning_surface_current.json"
DEFAULT_EXPLORATORY_RETRY_LANE_JSON = "runs/wetlab_cathepsin_k_exploratory_retry_lane_current.json"
DEFAULT_EXPLORATORY_RETRY_RUNNER_JSON = "runs/wetlab_cathepsin_k_exploratory_retry_runner_current.json"
DEFAULT_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_execution_queue_current.json"
DEFAULT_OUT_MD = "runs/wetlab_cathepsin_k_rescue_review_surface_current.md"


def build_payload(
    stage6_tuning_surface_payload: dict[str, Any] | None,
    exploratory_retry_lane_payload: dict[str, Any] | None,
    exploratory_retry_runner_payload: dict[str, Any] | None,
    execution_queue_payload: dict[str, Any],
) -> dict[str, Any]:
    snapshot = build_rescue_review_snapshot(
        stage6_tuning_surface_payload=stage6_tuning_surface_payload,
        exploratory_retry_lane_payload=exploratory_retry_lane_payload,
        exploratory_retry_runner_payload=exploratory_retry_runner_payload,
        execution_queue_payload=execution_queue_payload,
    )

    if snapshot["branch_to_rescue_only"]:
        decision = "promote_rescue_only_branch_keep_default_closed"
        decision_rationale = (
            f"Cathepsin K produced {snapshot['successful_gate45_shard_count']} successful gate4.5 exploratory shards and "
            f"{snapshot['strict_candidate_count']} strict candidate(s) at or below 2.5A plus "
            f"{snapshot['near_candidate_count']} additional near-band candidate(s) at or below 3.0A, so the default lane "
            "should stay closed and the target should advance through a dedicated rescue-only review branch."
        )
        next_required_step = (
            f"Operate {TARGET_ID} as a rescue-only branch, keep the default lane closed, and review the promoted gate4.5 "
            f"top-4 packet sourced from {snapshot['successful_gate45_shard_count']} successful exploratory shards."
        )
    elif snapshot["promoted_candidate_count"] > 0:
        decision = "review_promoted_gate45_packet_keep_default_closed"
        decision_rationale = (
            f"Cathepsin K produced {snapshot['promoted_candidate_count']} promoted gate4.5 rescue candidate(s), but the "
            "current exploratory evidence is not yet strong enough to authorize a dedicated rescue-only branch."
        )
        next_required_step = (
            f"Keep the {TARGET_ID} default lane closed and use the promoted gate4.5 top-4 packet as the operator review "
            "surface before any rescue-only branch decision."
        )
    else:
        decision = "review_more_before_reopen_keep_default_closed"
        decision_rationale = (
            "Cathepsin K has no promoted gate4.5 rescue candidates to review yet, so the default lane must remain closed "
            "until stronger exploratory evidence is available."
        )
        next_required_step = (
            f"Keep the {TARGET_ID} default lane closed and refresh the gate4.5 exploratory evidence before attempting a "
            "rescue-only branch decision."
        )

    return {
        "summary": {
            "status": "wetlab_cathepsin_k_rescue_review_surface_ready",
            "target_id": TARGET_ID,
            "focus_shard_id": snapshot["focus_shard_id"],
            "latest_success_shard_id": snapshot["latest_success_shard_id"],
            "successful_gate45_shard_ids": snapshot["successful_gate45_shard_ids"],
            "successful_gate45_shard_count": snapshot["successful_gate45_shard_count"],
            "selected_command_kind": snapshot["selected_command_kind"],
            "source_gate_threshold_A": snapshot["source_gate_threshold_A"],
            "strict_threshold_A": snapshot["strict_threshold_A"],
            "near_threshold_A": snapshot["near_threshold_A"],
            "recommended_observed_threshold_A": snapshot["recommended_observed_threshold_A"],
            "promoted_candidate_count": snapshot["promoted_candidate_count"],
            "strict_candidate_count": snapshot["strict_candidate_count"],
            "under_2p5_candidate_count": snapshot["strict_candidate_count"],
            "near_candidate_count": snapshot["near_candidate_count"],
            "best_ligand_id": snapshot["best_ligand_id"],
            "best_mean_min_distance_A": snapshot["best_mean_min_distance_A"],
            "best_source_shard_id": snapshot["best_row"].get("source_shard_id", ""),
            "stage6_tuning_status": snapshot["stage6_tuning_status"],
            "exploratory_retry_lane_status": snapshot["exploratory_retry_lane_status"],
            "exploratory_retry_runner_status": snapshot["exploratory_retry_runner_status"],
            "surface_label": "cathepsin_k_rescue_review",
            "review_packet_ready": snapshot["review_packet_ready"],
            "default_lane_reopen_allowed": False,
            "branch_to_rescue_only": snapshot["branch_to_rescue_only"],
            "decision": decision,
            "decision_rationale": decision_rationale,
            "next_required_step": next_required_step,
        },
        "structured": {
            "stage6_tuning_surface_artifact": "runs/wetlab_cathepsin_k_stage6_tuning_surface_current.md",
            "exploratory_retry_lane_artifact": "runs/wetlab_cathepsin_k_exploratory_retry_lane_current.md",
            "exploratory_retry_runner_artifact": "runs/wetlab_cathepsin_k_exploratory_retry_runner_current.md",
            "execution_queue_artifact": "runs/wetlab_broad_screen_execution_queue_current.md",
        },
        "rows": snapshot["promoted_rows"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Cathepsin K rescue review surface from stage6 exploratory evidence.")
    parser.add_argument("--stage6-tuning-surface-json", default=DEFAULT_STAGE6_TUNING_SURFACE_JSON)
    parser.add_argument("--exploratory-retry-lane-json", default=DEFAULT_EXPLORATORY_RETRY_LANE_JSON)
    parser.add_argument("--exploratory-retry-runner-json", default=DEFAULT_EXPLORATORY_RETRY_RUNNER_JSON)
    parser.add_argument("--execution-queue-json", default=DEFAULT_EXECUTION_QUEUE_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        maybe_load_json(args.stage6_tuning_surface_json),
        maybe_load_json(args.exploratory_retry_lane_json),
        maybe_load_json(args.exploratory_retry_runner_json),
        load_json(args.execution_queue_json),
    )
    write_artifact(args.out_md, "Wet-Lab Cathepsin K Rescue Review Surface", payload)


if __name__ == "__main__":
    main()
