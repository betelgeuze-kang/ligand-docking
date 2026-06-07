#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab.wetlab_cathepsin_k_rescue_utils import PROMOTED_PACKET_SIZE, TARGET_ID, summary, text
from tools.wetlab_target_render_utils import maybe_load_json, write_artifact

DEFAULT_REVIEW_SURFACE_JSON = "runs/wetlab_cathepsin_k_rescue_review_surface_current.json"
DEFAULT_EXPLORATORY_RETRY_LANE_JSON = "runs/wetlab_cathepsin_k_exploratory_retry_lane_current.json"
DEFAULT_OUT_MD = "runs/wetlab_cathepsin_k_promoted_top4_review_packet_current.md"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in {"", None}:
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in {"", None}:
            return default
        return int(value)
    except Exception:
        return default


def build_payload(
    review_surface_payload: dict[str, Any],
    exploratory_retry_lane_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    review = summary(review_surface_payload)
    lane = summary(exploratory_retry_lane_payload)
    review_rows = [dict(row or {}) for row in (review_surface_payload.get("rows", []) or [])]
    promoted_rows = review_rows[:PROMOTED_PACKET_SIZE]

    branch_to_rescue_only = bool(review.get("branch_to_rescue_only", False))
    packet_rows: list[dict[str, Any]] = []
    for packet_rank, row in enumerate(promoted_rows, start=1):
        mean_min_distance = round(_safe_float(row.get("mean_min_distance_A")), 3)
        packet_rows.append(
            {
                "row_kind": "cathepsin_k_promoted_top4_packet_row",
                "packet_rank": packet_rank,
                "target_id": text(review.get("target_id"), TARGET_ID),
                "shard_id": text(review.get("focus_shard_id"), review.get("latest_success_shard_id"), lane.get("shard_id")),
                "source_shard_id": text(row.get("source_shard_id")),
                "ligand_id": text(row.get("ligand_id")),
                "promotion_band": text(row.get("rescue_review_band")),
                "mean_min_distance_A": mean_min_distance,
                "binding_energy_proxy": _safe_float(row.get("binding_energy_proxy")),
                "stability_score": _safe_float(row.get("stability_score")),
                "contact_fraction": _safe_float(row.get("contact_fraction")),
                "trajectory_frames": _safe_int(row.get("trajectory_frames")),
                "queue_id": text(row.get("queue_id")),
                "ligand_model": text(row.get("ligand_model")),
                "review_action": text(row.get("review_action")),
            }
        )

    strict_threshold = _safe_float(review.get("strict_threshold_A"), 2.5)
    near_threshold = _safe_float(review.get("near_threshold_A"), 3.0)
    best_row = packet_rows[0] if packet_rows else {}
    packet_ready = bool(packet_rows)
    review_packet_ready = packet_ready and branch_to_rescue_only

    next_required_step = (
        "Use this promoted gate4.5 top-4 packet as the Cathepsin K rescue-only review unit, keep the default lane closed, and route all operator decisions through this packet before any reopen decision."
        if review_packet_ready
        else "Keep the Cathepsin K default lane closed and use this promoted gate4.5 top-4 packet for operator review before any rescue-only branch decision."
        if packet_ready
        else "No promoted gate4.5 Cathepsin K rescue candidates are available yet."
    )

    return {
        "summary": {
            "status": "wetlab_cathepsin_k_promoted_top4_review_packet_ready" if packet_ready else "wetlab_cathepsin_k_promoted_top4_review_packet_empty",
            "target_id": text(review.get("target_id"), TARGET_ID),
            "shard_id": text(review.get("focus_shard_id"), review.get("latest_success_shard_id"), lane.get("shard_id")),
            "source_shard_ids": text(review.get("successful_gate45_shard_ids")),
            "packet_scope": "promoted_top4_gate45_rescue_review",
            "packet_ready": packet_ready,
            "packet_ready_for_operator_review": packet_ready,
            "review_packet_ready": review_packet_ready,
            "rescue_only_branch": branch_to_rescue_only,
            "default_lane_reopen_allowed": False,
            "branch_to_rescue_only": branch_to_rescue_only,
            "selected_command_kind": text(review.get("selected_command_kind"), lane.get("selected_command_kind")),
            "source_gate_threshold_A": _safe_float(review.get("source_gate_threshold_A"), 4.5),
            "strict_threshold_A": strict_threshold,
            "near_threshold_A": near_threshold,
            "source_successful_shard_count": _safe_int(review.get("successful_gate45_shard_count")),
            "review_packet_candidate_count": len(packet_rows),
            "promoted_candidate_count": len(packet_rows),
            "strict_candidate_count": sum(
                1 for row in packet_rows if 0 < _safe_float(row.get("mean_min_distance_A")) <= strict_threshold
            ),
            "under_2p5_candidate_count": sum(
                1 for row in packet_rows if 0 < _safe_float(row.get("mean_min_distance_A")) <= strict_threshold
            ),
            "near_candidate_count": sum(
                1 for row in packet_rows if strict_threshold < _safe_float(row.get("mean_min_distance_A")) <= near_threshold
            ),
            "best_ligand_id": text(best_row.get("ligand_id")),
            "best_mean_min_distance_A": round(_safe_float(best_row.get("mean_min_distance_A")), 3),
            "best_binding_energy_proxy": _safe_float(best_row.get("binding_energy_proxy")),
            "best_stability_score": _safe_float(best_row.get("stability_score")),
            "next_required_step": next_required_step,
        },
        "structured": {
            "rescue_review_surface_artifact": "runs/wetlab_cathepsin_k_rescue_review_surface_current.md",
            "exploratory_retry_lane_artifact": "runs/wetlab_cathepsin_k_exploratory_retry_lane_current.md",
        },
        "rows": packet_rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Cathepsin K promoted top-4 rescue review packet.")
    parser.add_argument("--review-surface-json", default=DEFAULT_REVIEW_SURFACE_JSON)
    parser.add_argument("--exploratory-retry-lane-json", default=DEFAULT_EXPLORATORY_RETRY_LANE_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        maybe_load_json(args.review_surface_json),
        maybe_load_json(args.exploratory_retry_lane_json),
    )
    write_artifact(args.out_md, "Wet-Lab Cathepsin K Promoted Top-4 Review Packet", payload)


if __name__ == "__main__":
    main()
