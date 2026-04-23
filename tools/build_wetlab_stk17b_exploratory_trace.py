#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from tools.wetlab_target_render_utils import load_json, maybe_load_json, write_artifact

ROOT = Path(__file__).resolve().parents[1]
TARGET_ID = "STK17B (DRAK2)"
TARGET_SLUG = "stk17b_drak2"
DEFAULT_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_execution_queue_current.json"
DEFAULT_EXPLORATORY_LANE_JSON = "runs/wetlab_stk17b_exploratory_retry_lane_current.json"
DEFAULT_OUT_MD = "runs/wetlab_stk17b_exploratory_trace_current.md"


def _text(*values: Any) -> str:
    for value in values:
        if value not in {None, ""}:
            return str(value).strip()
    return ""


def _shard_number(shard_id: str) -> int:
    head = _text(shard_id).split("_of_", 1)[0]
    return int(head) if head.isdigit() else 0


def _shard_id(number: int, total: int = 20) -> str:
    return f"{number:02d}_of_{total:02d}"


def _summary_candidates(shard_id: str) -> list[Path]:
    base = ROOT / "runs" / "wetlab_broad_screen_throughput" / TARGET_SLUG / shard_id
    return [
        base / "throughput_run_gate45_summary.json",
        base / "throughput_run_gate55_summary.json",
        base / "throughput_run_summary.json",
    ]


def _detect_summary(shard_id: str) -> tuple[str, dict[str, Any], str]:
    for path in _summary_candidates(shard_id):
        payload = maybe_load_json(str(path)) or {}
        if path.exists():
            if path.name == "throughput_run_gate45_summary.json":
                return str(path), payload, "gate45_exploratory"
            if path.name == "throughput_run_gate55_summary.json":
                return str(path), payload, "gate55_tuned"
            return str(path), payload, "standard_auto"
    return str(_summary_candidates(shard_id)[-1]), {}, "standard_auto"


def _service(payload: dict[str, Any]) -> dict[str, Any]:
    return dict(payload.get("service_result", {}) or {})


def _stage6(payload: dict[str, Any]) -> dict[str, Any]:
    return dict((payload.get("stages", {}) or {}).get("stage6_operational_gate", {}) or {})


def _failed_metric(stage6_payload: dict[str, Any]) -> tuple[float, float]:
    failed_metrics = list(stage6_payload.get("failed_metrics", []) or [])
    if failed_metrics:
        first = dict(failed_metrics[0] or {})
        return (
            float(first.get("value", stage6_payload.get("mean_min_distance_A", 0.0)) or 0.0),
            float(first.get("threshold", stage6_payload.get("gate_threshold_A", 0.0)) or 0.0),
        )
    return (
        float(stage6_payload.get("mean_min_distance_A", 0.0) or 0.0),
        float(stage6_payload.get("gate_threshold_A", 0.0) or 0.0),
    )


def _launch_basis(shard_id: str, success_shard_id: str, command_family: str, queue_status: str) -> str:
    if shard_id == success_shard_id and command_family == "gate45_exploratory":
        return "manual_exploratory_retry"
    if _shard_number(shard_id) > _shard_number(success_shard_id) and command_family == "gate45_exploratory":
        return "manual_exploratory_followup_retry"
    if _shard_number(shard_id) > _shard_number(success_shard_id):
        if queue_status == "explicit_hold":
            return "watcher_autostart_after_exploratory_success_default_lane"
        if queue_status == "running":
            return "watcher_autostart_followup_default_lane"
    return "queue_residual_state"


def _campaign_trace_shards(campaign_start_number: int, total: int = 20) -> list[str]:
    start = campaign_start_number if campaign_start_number > 0 else 13
    return [_shard_id(number, total=total) for number in range(start, total + 1)]


def _find_success_row(rows: list[dict[str, Any]], fallback_shard_id: str, fallback_threshold: float) -> dict[str, Any]:
    for row in rows:
        if (
            str(row.get("command_family", "")).strip() == "gate45_exploratory"
            and str(row.get("service_status", "")).strip() == "ok"
        ):
            return row
    return {
        "shard_id": fallback_shard_id,
        "command_family": "gate45_exploratory" if fallback_shard_id else "",
        "threshold_observed_A": fallback_threshold,
    }


def build_payload(
    execution_queue_payload: dict[str, Any],
    exploratory_lane_payload: dict[str, Any],
) -> dict[str, Any]:
    lane_summary = dict(exploratory_lane_payload.get("summary", {}) or {})
    campaign_start_shard_id = _text(lane_summary.get("campaign_start_shard_id")) or "13_of_20"
    campaign_start_number = _shard_number(campaign_start_shard_id) or 13
    trace_shards = _campaign_trace_shards(campaign_start_number)

    queue_rows = {
        _text(row.get("shard_id")): dict(row)
        for row in (execution_queue_payload.get("rows", []) or [])
        if _text(row.get("target_id")) == TARGET_ID and _text(row.get("shard_id")) in trace_shards
    }

    rows: list[dict[str, Any]] = []
    for shard_id in trace_shards:
        queue_row = queue_rows.get(shard_id, {})
        summary_json, payload, command_family = _detect_summary(shard_id)
        service = _service(payload)
        stage6_payload = _stage6(payload)
        metric_value, threshold = _failed_metric(stage6_payload)
        if command_family == "gate45_exploratory" and not threshold:
            threshold = float(lane_summary.get("selected_threshold_A", 0.0) or 0.0)
        queue_status = _text(queue_row.get("queue_status"))
        rows.append(
            {
                "target_id": TARGET_ID,
                "shard_id": shard_id,
                "queue_status": queue_status,
                "notes": _text(queue_row.get("notes")),
                "summary_json": summary_json,
                "command_family": command_family,
                "service_status": _text(service.get("status"), payload.get("status")),
                "error_code": _text(service.get("error_code"), payload.get("error_code")),
                "failed_stage": _text(service.get("failed_stage"), payload.get("failed_stage")),
                "mean_min_distance_A": float(stage6_payload.get("mean_min_distance_A", metric_value) or metric_value),
                "threshold_observed_A": threshold,
                "stage6_pass": bool(stage6_payload.get("pass", False)),
            }
        )

    fallback_success_shard_id = _text(lane_summary.get("shard_id")) or "17_of_20"
    success_row = _find_success_row(
        rows,
        fallback_success_shard_id,
        float(lane_summary.get("selected_threshold_A", 0.0) or 0.0),
    )
    success_shard_id = _text(success_row.get("shard_id")) or fallback_success_shard_id
    success_number = _shard_number(success_shard_id) or 17
    for row in rows:
        row["launch_basis"] = _launch_basis(
            str(row.get("shard_id", "")),
            success_shard_id,
            str(row.get("command_family", "")),
            str(row.get("queue_status", "")),
        )
    followup_rows = [row for row in rows if _shard_number(str(row.get("shard_id", ""))) > success_number]
    standard_auto_followup = [row for row in followup_rows if row.get("command_family") == "standard_auto"]
    hold_followup = [row for row in followup_rows if row.get("queue_status") == "explicit_hold"]
    gate45_followup = [row for row in followup_rows if row.get("command_family") == "gate45_exploratory"]
    gate45_followup_success = [row for row in gate45_followup if row.get("service_status") == "ok"]

    if followup_rows and len(gate45_followup_success) == len(followup_rows):
        next_required_step = (
            "Keep the STK17B (DRAK2) default lane closed and continue this target only through the gate4.5 exploratory lane; follow-up shards 18_of_20;19_of_20;20_of_20 now have end-to-end gate4.5 evidence."
        )
    else:
        next_required_step = (
            "Keep STK17B exploratory auto-start frozen after the gate4.5 success; shards 18-20 were standard-auto follow-ups under the default gate and should be reviewed separately before reopening."
        )

    return {
        "summary": {
            "status": "wetlab_stk17b_exploratory_trace_ready",
            "target_id": TARGET_ID,
            "campaign_start_shard_id": campaign_start_shard_id,
            "exploratory_success_shard_id": _text(success_row.get("shard_id")) or success_shard_id,
            "exploratory_success_command_family": _text(success_row.get("command_family")),
            "exploratory_success_threshold_A": float(success_row.get("threshold_observed_A", lane_summary.get("selected_threshold_A", 0.0)) or 0.0),
            "post_success_followup_shard_count": len(followup_rows),
            "post_success_standard_auto_shard_count": len(standard_auto_followup),
            "post_success_hold_shard_count": len(hold_followup),
            "post_success_gate45_followup_count": len(gate45_followup),
            "post_success_gate45_followup_success_count": len(gate45_followup_success),
            "next_required_step": next_required_step,
        },
        "structured": {
            "execution_queue_artifact": "runs/wetlab_broad_screen_execution_queue_current.md",
            "exploratory_retry_lane_artifact": "runs/wetlab_stk17b_exploratory_retry_lane_current.md",
            "success_summary_artifact": "runs/wetlab_broad_screen_throughput/stk17b_drak2/17_of_20/throughput_run_gate45_summary.json",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a trace surface for the STK17B exploratory gate4.5 retry and the follow-up auto-start behavior.")
    parser.add_argument("--execution-queue-json", default=DEFAULT_EXECUTION_QUEUE_JSON)
    parser.add_argument("--exploratory-lane-json", default=DEFAULT_EXPLORATORY_LANE_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    write_artifact(
        args.out_md,
        "Wet-Lab STK17B Exploratory Trace",
        build_payload(
            load_json(args.execution_queue_json),
            load_json(args.exploratory_lane_json),
        ),
    )


if __name__ == "__main__":
    main()
