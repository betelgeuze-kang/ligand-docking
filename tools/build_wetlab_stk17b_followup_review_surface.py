#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from statistics import median
from typing import Any

from tools.wetlab_target_render_utils import load_json, maybe_load_json, write_artifact

ROOT = Path(__file__).resolve().parents[1]
TARGET_ID = "STK17B (DRAK2)"
DEFAULT_TRACE_JSON = "runs/wetlab_stk17b_exploratory_trace_current.json"
DEFAULT_FOLLOWUP_LANE_JSON = "runs/wetlab_stk17b_exploratory_followup_lane_current.json"
DEFAULT_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_execution_queue_current.json"
DEFAULT_OUT_MD = "runs/wetlab_stk17b_followup_review_surface_current.md"


def _summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict((payload or {}).get("summary", {}) or {})


def _text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in {None, ""}:
            return default
        return float(value)
    except Exception:
        return default


def _summary_path(shard_id: str) -> Path:
    base = ROOT / "runs" / "wetlab_broad_screen_throughput" / "stk17b_drak2" / shard_id
    gate45 = base / "throughput_run_gate45_summary.json"
    default = base / "throughput_run_summary.json"
    return gate45 if gate45.exists() else default


def _queue_row(execution_queue_payload: dict[str, Any], shard_id: str) -> dict[str, Any]:
    for row in execution_queue_payload.get("rows", []) or []:
        candidate = dict(row or {})
        if _text(candidate.get("target_id")) == TARGET_ID and _text(candidate.get("shard_id")) == shard_id:
            return candidate
    return {}


def _threshold(stage6: dict[str, Any], default: float) -> float:
    failed_metrics = list(stage6.get("failed_metrics", []) or [])
    if failed_metrics:
        return _safe_float(dict(failed_metrics[0] or {}).get("threshold"), default)
    return _safe_float(stage6.get("gate_threshold_A"), default)


def _row_for_shard(shard_id: str, execution_queue_payload: dict[str, Any], exploratory_threshold: float) -> dict[str, Any]:
    summary_path = _summary_path(shard_id)
    payload = maybe_load_json(str(summary_path))
    service = dict(payload.get("service_result", {}) or {})
    stage6 = dict((payload.get("stages", {}) or {}).get("stage6_operational_gate", {}) or {})
    queue_row = _queue_row(execution_queue_payload, shard_id)
    observed = _safe_float(stage6.get("mean_min_distance_A"))
    threshold = _threshold(stage6, exploratory_threshold)
    gate45_summary = "gate45" in summary_path.name
    stage6_pass = bool(stage6.get("pass", False))
    if gate45_summary and stage6_pass:
        classification = "exploratory_gate45_followup_success"
    elif gate45_summary and not stage6_pass:
        classification = "exploratory_gate45_followup_hold"
    elif not stage6_pass and observed and exploratory_threshold and observed <= exploratory_threshold:
        classification = "default_gate_hold_inside_gate45_band"
    elif not stage6_pass:
        classification = "default_gate_hold_outside_gate45_band"
    else:
        classification = "other"
    return {
        "row_kind": "followup_review_row",
        "target_id": TARGET_ID,
        "shard_id": shard_id,
        "queue_status": _text(queue_row.get("queue_status")),
        "execution_state": _text(queue_row.get("execution_state")),
        "notes": _text(queue_row.get("notes")),
        "service_status": _text(service.get("status")),
        "error_code": _text(service.get("error_code")),
        "failed_stage": _text(service.get("failed_stage")),
        "stage6_pass": stage6_pass,
        "mean_min_distance_A": observed,
        "gate_threshold_A": threshold,
        "distance_vs_threshold_A": round(observed - threshold, 3) if observed and threshold else 0.0,
        "mean_min_distance_A_source": _text(stage6.get("mean_min_distance_A_source")),
        "min_frames_observed": int(_safe_float(stage6.get("min_frames_observed"), 0)),
        "summary_json": str(summary_path),
        "followup_gate_classification": classification,
    }


def build_payload(
    trace_payload: dict[str, Any],
    followup_lane_payload: dict[str, Any],
    execution_queue_payload: dict[str, Any],
) -> dict[str, Any]:
    trace = _summary(trace_payload)
    followup = _summary(followup_lane_payload)
    exploratory_success_shard_id = _text(trace.get("exploratory_success_shard_id"))
    exploratory_threshold = _safe_float(
        followup.get("selected_threshold_A"),
        _safe_float(trace.get("exploratory_success_threshold_A"), 4.5),
    )
    followup_shard_ids = [part.strip() for part in _text(followup.get("followup_shard_ids")).split(";") if part.strip()]
    shard_ids = [exploratory_success_shard_id] + followup_shard_ids
    rows = [_row_for_shard(shard_id, execution_queue_payload, exploratory_threshold) for shard_id in shard_ids if shard_id]

    success_rows = [row for row in rows if row["shard_id"] == exploratory_success_shard_id]
    followup_rows = [row for row in rows if row["shard_id"] in followup_shard_ids]
    followup_holds = [row for row in followup_rows if row.get("queue_status") == "explicit_hold"]
    followup_default_gate_holds = [
        row for row in followup_holds if row.get("followup_gate_classification") == "default_gate_hold_inside_gate45_band"
    ]
    followup_gate45_rows = [
        row for row in followup_rows if str(row.get("followup_gate_classification", "")).startswith("exploratory_gate45_followup")
    ]
    followup_gate45_successes = [
        row for row in followup_gate45_rows if row.get("followup_gate_classification") == "exploratory_gate45_followup_success"
    ]
    followup_gate45_holds = [
        row for row in followup_gate45_rows if row.get("followup_gate_classification") == "exploratory_gate45_followup_hold"
    ]
    hold_values = [float(row.get("mean_min_distance_A", 0.0) or 0.0) for row in followup_holds if row.get("mean_min_distance_A")]
    hold_median = round(float(median(hold_values)), 3) if hold_values else 0.0
    success_mean = round(_safe_float(success_rows[0].get("mean_min_distance_A")), 3) if success_rows else 0.0
    gap = round(hold_median - success_mean, 3) if hold_values and success_rows else 0.0

    if success_rows and len(followup_gate45_successes) == len(followup_shard_ids) and followup_shard_ids:
        default_lane_reopen_allowed = False
        branch_to_gate45_only = True
        decision = "branch_to_gate45_only_keep_default_closed"
        rationale = (
            "17_of_20 and follow-up shards 18-20 all succeeded under the 4.5A exploratory gate, so the default 2.5A lane should remain closed and STK17B should stay on the gate4.5 branch."
        )
        next_required_step = (
            "Keep the STK17B (DRAK2) default lane closed and continue this target only through the gate4.5 exploratory lane; the follow-up set 18_of_20;19_of_20;20_of_20 now has end-to-end gate4.5 evidence."
        )
    elif success_rows and len(followup_gate45_rows) == len(followup_shard_ids) and followup_shard_ids:
        default_lane_reopen_allowed = False
        branch_to_gate45_only = True
        decision = "keep_default_closed_review_gate45_followup"
        rationale = (
            "17_of_20 succeeded under the 4.5A exploratory gate and follow-up shards 18-20 were re-evaluated under the same gate4.5 path, so the default lane should stay closed while the gate4.5 follow-up outcome is reviewed."
        )
        next_required_step = (
            "Keep the STK17B (DRAK2) default lane closed and review the gate4.5 follow-up outcomes for 18_of_20;19_of_20;20_of_20 before reopening any STK17B auto-start."
        )
    else:
        default_lane_reopen_allowed = not (
            success_rows
            and len(followup_holds) == len(followup_shard_ids)
            and len(followup_default_gate_holds) == len(followup_shard_ids)
        )
        branch_to_gate45_only = not default_lane_reopen_allowed
        decision = "branch_to_gate45_only_keep_default_closed" if branch_to_gate45_only else "review_more_before_reopen"
        rationale = (
            "17_of_20 succeeded under the 4.5A exploratory gate, while follow-up shards 18-20 all held under the default 2.5A stage6 gate even though their observed mean_min_distance stayed inside the 4.5A band."
            if branch_to_gate45_only
            else "The follow-up pattern is mixed enough that reopening the default lane still needs operator review."
        )
        next_required_step = (
            "Keep the STK17B (DRAK2) default lane closed and branch this target into the gate4.5 exploratory lane only; treat 18_of_20;19_of_20;20_of_20 as default-gate follow-up holds, not as evidence against the 4.5A path, until the follow-up runner preserves the 4.5A threshold end-to-end."
            if branch_to_gate45_only
            else "Hold the STK17B (DRAK2) default lane closed until the 18-20 follow-up review is completed and the threshold path is confirmed."
        )

    return {
        "summary": {
            "status": "wetlab_stk17b_followup_review_surface_ready",
            "target_id": TARGET_ID,
            "exploratory_success_shard_id": exploratory_success_shard_id,
            "followup_shard_ids": ";".join(followup_shard_ids),
            "exploratory_threshold_A": exploratory_threshold,
            "exploratory_success_count": len(success_rows),
            "followup_row_count": len(followup_rows),
            "followup_hold_count": len(followup_holds),
            "followup_default_gate_hold_count": len(followup_default_gate_holds),
            "followup_gate45_row_count": len(followup_gate45_rows),
            "followup_gate45_success_count": len(followup_gate45_successes),
            "followup_gate45_hold_count": len(followup_gate45_holds),
            "exploratory_success_mean_min_distance_A": success_mean,
            "followup_hold_median_mean_min_distance_A": hold_median,
            "success_vs_followup_hold_gap_A": gap,
            "default_lane_reopen_allowed": default_lane_reopen_allowed,
            "branch_to_gate45_only": branch_to_gate45_only,
            "decision": decision,
            "decision_rationale": rationale,
            "next_required_step": next_required_step,
        },
        "structured": {
            "exploratory_trace_artifact": "runs/wetlab_stk17b_exploratory_trace_current.md",
            "exploratory_followup_lane_artifact": "runs/wetlab_stk17b_exploratory_followup_lane_current.md",
            "stage6_tuning_surface_artifact": "runs/wetlab_stk17b_stage6_tuning_surface_current.md",
            "execution_queue_artifact": "runs/wetlab_broad_screen_execution_queue_current.md",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the STK17B exploratory follow-up review surface.")
    parser.add_argument("--trace-json", default=DEFAULT_TRACE_JSON)
    parser.add_argument("--followup-lane-json", default=DEFAULT_FOLLOWUP_LANE_JSON)
    parser.add_argument("--execution-queue-json", default=DEFAULT_EXECUTION_QUEUE_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    write_artifact(
        args.out_md,
        "Wet-Lab STK17B Follow-Up Review Surface",
        build_payload(
            load_json(args.trace_json),
            load_json(args.followup_lane_json),
            load_json(args.execution_queue_json),
        ),
    )


if __name__ == "__main__":
    main()
