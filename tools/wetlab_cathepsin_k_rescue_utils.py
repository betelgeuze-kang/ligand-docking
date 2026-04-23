#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from tools.wetlab_target_render_utils import maybe_load_json

ROOT = Path(__file__).resolve().parents[1]
TARGET_ID = "Cathepsin K"
TARGET_SLUG = "cathepsin_k"
DEFAULT_SELECTED_COMMAND_KIND = "throughput_preflight_tuned_gate45"
SOURCE_GATE_THRESHOLD_A = 4.5
STRICT_THRESHOLD_A = 2.5
NEAR_THRESHOLD_A = 3.0
PROMOTED_PACKET_SIZE = 4
PROMOTED_TOPK_PER_SHARD = 8
MIN_SUCCESSFUL_SHARDS_FOR_BRANCH = 3
MIN_STRICT_CANDIDATES_FOR_BRANCH = 2
MIN_PROMOTED_CANDIDATES_FOR_BRANCH = PROMOTED_PACKET_SIZE

MaybeLoadJson = Callable[[str], dict[str, Any]]


def summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict((payload or {}).get("summary", {}) or {})


def text(*values: Any, default: str = "") -> str:
    for value in values:
        candidate = str(value or "").strip()
        if candidate:
            return candidate
    return default


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in {None, ""}:
            return default
        return float(value)
    except Exception:
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in {None, ""}:
            return default
        return int(value)
    except Exception:
        return default


def shard_ordinal(shard_id: Any) -> int:
    candidate = text(shard_id)
    if "_of_" not in candidate:
        return 0
    try:
        return int(candidate.split("_of_", 1)[0])
    except Exception:
        return 0


def gate45_summary_path(shard_id: str) -> Path:
    return ROOT / "runs" / "wetlab_broad_screen_throughput" / TARGET_SLUG / shard_id / "throughput_run_gate45_summary.json"


def gate45_stage3_summary_path(shard_id: str) -> Path:
    return ROOT / "runs" / "wetlab_broad_screen_throughput" / TARGET_SLUG / shard_id / "throughput_run_gate45_stage3_summary.json"


def _stage6_threshold(stage6: dict[str, Any]) -> float:
    threshold = safe_float(stage6.get("gate_threshold_A"))
    if threshold > 0:
        return threshold
    failed_metrics = list(stage6.get("failed_metrics", []) or [])
    if failed_metrics:
        threshold = safe_float(dict(failed_metrics[0] or {}).get("threshold"))
    return threshold if threshold > 0 else SOURCE_GATE_THRESHOLD_A


def collect_successful_gate45_shards(
    execution_queue_payload: dict[str, Any],
    *,
    maybe_load_json_fn: MaybeLoadJson = maybe_load_json,
) -> list[dict[str, Any]]:
    queue_rows = [
        dict(row or {})
        for row in (execution_queue_payload.get("rows", []) or [])
        if text((row or {}).get("target_id")) == TARGET_ID and text((row or {}).get("queue_status")) == "result_ready"
    ]
    queue_rows.sort(key=lambda row: shard_ordinal(row.get("shard_id")))

    successful_rows: list[dict[str, Any]] = []
    for row in queue_rows:
        shard_id = text(row.get("shard_id"))
        if not shard_id:
            continue
        summary_path = gate45_summary_path(shard_id)
        gate45_payload = maybe_load_json_fn(str(summary_path))
        stage6 = dict((gate45_payload.get("stages", {}) or {}).get("stage6_operational_gate", {}) or {})
        if not bool(stage6.get("pass", False)):
            continue
        service = dict(gate45_payload.get("service_result", {}) or {})
        successful_rows.append(
            {
                "target_id": TARGET_ID,
                "shard_id": shard_id,
                "queue_status": text(row.get("queue_status")),
                "selected_command_kind": DEFAULT_SELECTED_COMMAND_KIND,
                "source_gate_threshold_A": _stage6_threshold(stage6),
                "source_gate_mean_min_distance_A": safe_float(stage6.get("mean_min_distance_A")),
                "source_gate_metric_source": text(stage6.get("mean_min_distance_A_source")),
                "service_status": text(service.get("status")),
                "error_code": text(service.get("error_code")),
                "gate45_summary_json": str(summary_path),
                "gate45_stage3_summary_json": str(gate45_stage3_summary_path(shard_id)),
            }
        )
    return successful_rows


def _sorted_stage3_topk_rows(stage3_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [dict(row or {}) for row in (stage3_payload.get("topk", []) or [])[:PROMOTED_TOPK_PER_SHARD]]
    rows.sort(
        key=lambda row: (
            safe_float(row.get("mean_min_distance_A"), 999.0) if safe_float(row.get("mean_min_distance_A")) > 0 else 999.0,
            -safe_float(row.get("stability_score")),
            text(row.get("ligand_id")),
        )
    )
    return rows


def collect_promoted_review_rows(
    successful_gate45_shards: list[dict[str, Any]],
    *,
    maybe_load_json_fn: MaybeLoadJson = maybe_load_json,
) -> list[dict[str, Any]]:
    promoted_rows: list[dict[str, Any]] = []
    for shard_row in successful_gate45_shards:
        shard_id = text(shard_row.get("shard_id"))
        stage3_payload = maybe_load_json_fn(text(shard_row.get("gate45_stage3_summary_json")))
        for shard_priority_rank, row in enumerate(_sorted_stage3_topk_rows(stage3_payload), start=1):
            mean_min_distance = safe_float(row.get("mean_min_distance_A"))
            if mean_min_distance <= 0 or mean_min_distance > NEAR_THRESHOLD_A:
                continue
            review_band = "strict_under_2p5A" if mean_min_distance <= STRICT_THRESHOLD_A else "near_under_3p0A"
            promoted_rows.append(
                {
                    "row_kind": "cathepsin_k_rescue_review_candidate",
                    "target_id": TARGET_ID,
                    "source_shard_id": shard_id,
                    "priority_rank_within_shard": shard_priority_rank,
                    "rescue_review_band": review_band,
                    "review_action": (
                        "strict_promote_rescue_only_branch"
                        if review_band == "strict_under_2p5A"
                        else "near_band_manual_review_rescue_only_branch"
                    ),
                    "selected_command_kind": DEFAULT_SELECTED_COMMAND_KIND,
                    "source_gate_threshold_A": safe_float(shard_row.get("source_gate_threshold_A"), SOURCE_GATE_THRESHOLD_A),
                    "source_gate_mean_min_distance_A": safe_float(shard_row.get("source_gate_mean_min_distance_A")),
                    "ligand_id": text(row.get("ligand_id")),
                    "mean_min_distance_A": round(mean_min_distance, 3),
                    "binding_energy_proxy": safe_float(row.get("binding_energy_proxy")),
                    "stability_score": safe_float(row.get("stability_score")),
                    "contact_fraction": safe_float(row.get("contact_fraction")),
                    "trajectory_frames": safe_int(row.get("trajectory_frames")),
                    "ligand_model": text(row.get("ligand_model"), "2bead"),
                    "queue_id": text(row.get("queue_id")),
                    "trajectory_npz": text(row.get("trajectory_npz")),
                    "score_json": text(row.get("score_json")),
                    "source_gate45_summary_json": text(shard_row.get("gate45_summary_json")),
                    "source_gate45_stage3_summary_json": text(shard_row.get("gate45_stage3_summary_json")),
                }
            )
    promoted_rows.sort(
        key=lambda row: (
            safe_float(row.get("mean_min_distance_A"), 999.0),
            -safe_float(row.get("stability_score")),
            text(row.get("ligand_id")),
            shard_ordinal(row.get("source_shard_id")),
        )
    )
    for priority_rank, row in enumerate(promoted_rows, start=1):
        row["priority_rank"] = priority_rank
    return promoted_rows


def build_rescue_review_snapshot(
    *,
    stage6_tuning_surface_payload: dict[str, Any] | None,
    exploratory_retry_lane_payload: dict[str, Any] | None,
    exploratory_retry_runner_payload: dict[str, Any] | None,
    execution_queue_payload: dict[str, Any],
    maybe_load_json_fn: MaybeLoadJson = maybe_load_json,
) -> dict[str, Any]:
    tuning = summary(stage6_tuning_surface_payload)
    lane = summary(exploratory_retry_lane_payload)
    runner = summary(exploratory_retry_runner_payload)

    successful_gate45_shards = collect_successful_gate45_shards(
        execution_queue_payload,
        maybe_load_json_fn=maybe_load_json_fn,
    )
    promoted_rows = collect_promoted_review_rows(
        successful_gate45_shards,
        maybe_load_json_fn=maybe_load_json_fn,
    )

    strict_rows = [row for row in promoted_rows if safe_float(row.get("mean_min_distance_A")) <= STRICT_THRESHOLD_A]
    near_rows = [
        row for row in promoted_rows
        if STRICT_THRESHOLD_A < safe_float(row.get("mean_min_distance_A")) <= NEAR_THRESHOLD_A
    ]
    best_row = promoted_rows[0] if promoted_rows else {}
    latest_success_shard_id = text(successful_gate45_shards[-1].get("shard_id")) if successful_gate45_shards else ""
    focus_shard_id = text(latest_success_shard_id, runner.get("shard_id"), lane.get("shard_id"))
    selected_command_kind = text(
        lane.get("selected_command_kind"),
        runner.get("selected_command_kind"),
        tuning.get("immediately_runnable_command_kind"),
        DEFAULT_SELECTED_COMMAND_KIND,
    )
    recommended_observed_threshold_A = safe_float(tuning.get("recommended_observed_threshold_A"))
    branch_to_rescue_only = bool(
        selected_command_kind == DEFAULT_SELECTED_COMMAND_KIND
        and (recommended_observed_threshold_A <= 0 or recommended_observed_threshold_A <= SOURCE_GATE_THRESHOLD_A)
        and len(successful_gate45_shards) >= MIN_SUCCESSFUL_SHARDS_FOR_BRANCH
        and len(promoted_rows) >= MIN_PROMOTED_CANDIDATES_FOR_BRANCH
        and len(strict_rows) >= MIN_STRICT_CANDIDATES_FOR_BRANCH
    )

    return {
        "target_id": TARGET_ID,
        "focus_shard_id": focus_shard_id,
        "latest_success_shard_id": latest_success_shard_id,
        "source_runner_shard_id": text(runner.get("shard_id")),
        "selected_command_kind": selected_command_kind,
        "source_gate_threshold_A": SOURCE_GATE_THRESHOLD_A,
        "strict_threshold_A": STRICT_THRESHOLD_A,
        "near_threshold_A": NEAR_THRESHOLD_A,
        "recommended_observed_threshold_A": recommended_observed_threshold_A,
        "successful_gate45_shard_count": len(successful_gate45_shards),
        "successful_gate45_shard_ids": ";".join(text(row.get("shard_id")) for row in successful_gate45_shards),
        "successful_gate45_shards": successful_gate45_shards,
        "promoted_rows": promoted_rows,
        "review_packet_rows": promoted_rows[:PROMOTED_PACKET_SIZE],
        "promoted_candidate_count": len(promoted_rows),
        "strict_candidate_count": len(strict_rows),
        "near_candidate_count": len(near_rows),
        "best_row": best_row,
        "best_ligand_id": text(best_row.get("ligand_id")),
        "best_mean_min_distance_A": round(safe_float(best_row.get("mean_min_distance_A")), 3),
        "review_packet_ready": branch_to_rescue_only and bool(promoted_rows[:PROMOTED_PACKET_SIZE]),
        "branch_to_rescue_only": branch_to_rescue_only,
        "exploratory_retry_lane_status": text(lane.get("status")),
        "exploratory_retry_runner_status": text(runner.get("status")),
        "stage6_tuning_status": text(tuning.get("status")),
    }


def build_branch_evidence_payload(
    review_surface_payload: dict[str, Any] | None,
    exploratory_retry_lane_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    review = summary(review_surface_payload)
    lane = summary(exploratory_retry_lane_payload)
    branch_to_rescue_only = bool(review.get("branch_to_rescue_only", False))
    return {
        "summary": {
            "status": (
                "wetlab_cathepsin_k_branch_evidence_ready"
                if branch_to_rescue_only
                else "wetlab_cathepsin_k_branch_evidence_pending_review"
            ),
            "target_id": text(review.get("target_id"), lane.get("target_id"), TARGET_ID),
            "shard_id": text(review.get("focus_shard_id"), review.get("latest_success_shard_id"), lane.get("shard_id")),
            "selected_command_kind": text(
                review.get("selected_command_kind"),
                lane.get("selected_command_kind"),
                DEFAULT_SELECTED_COMMAND_KIND,
            ),
            "selected_threshold_A": safe_float(review.get("source_gate_threshold_A"), SOURCE_GATE_THRESHOLD_A),
            "execution_mode": (
                "exploratory_gate45_result_review"
                if branch_to_rescue_only
                else "exploratory_gate45_operator_review"
            ),
            "scoring_status": (
                "promoted_gate45_top4_packet_ready"
                if branch_to_rescue_only
                else "promoted_gate45_top4_operator_review_only"
            ),
        }
    }
