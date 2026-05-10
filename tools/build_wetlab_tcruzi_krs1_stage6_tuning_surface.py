#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_stage6_tuning_utils import (
    build_stage6_tuning_payload,
    infer_gate_threshold,
    load_summary,
    safe_float,
    safe_int,
    shard_ordinal,
    text,
)
from tools.wetlab_target_render_utils import load_json, maybe_load_json, write_artifact

TARGET_ID = "T. cruzi KRS1"
TARGET_SLUG = "t_cruzi_krs1"
DEFAULT_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_execution_queue_current.json"
DEFAULT_THROUGHPUT_BRIDGE_JSON = "runs/wetlab_broad_screen_throughput_bridge_current.json"
DEFAULT_OUT_MD = "runs/wetlab_tcruzi_krs1_stage6_tuning_surface_current.md"


def _target_rows(execution_queue_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        dict(row or {})
        for row in execution_queue_payload.get("rows", []) or []
        if text((row or {}).get("target_id")) == TARGET_ID
    ]
    rows.sort(key=lambda row: shard_ordinal(text(row.get("shard_id"))))
    return rows


def _gate51_validation_rows(
    execution_queue_payload: dict[str, Any],
    maybe_load_json_fn,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in _target_rows(execution_queue_payload):
        if text(row.get("queue_status")) != "result_ready":
            continue
        shard_id = text(row.get("shard_id"))
        payload, summary_path = load_summary(TARGET_SLUG, shard_id, maybe_load_json_fn)
        if "gate51" not in summary_path:
            continue
        service = dict(payload.get("service_result", {}) or {})
        stage6 = dict((payload.get("stages", {}) or {}).get("stage6_operational_gate", {}) or {})
        pass_value = payload.get("pass") is True and service.get("status") == "ok" and stage6.get("pass") is True
        observed = safe_float(stage6.get("mean_min_distance_A"))
        if observed <= 0:
            continue
        threshold = infer_gate_threshold(summary_path, stage6)
        rows.append(
            {
                "row_kind": "gate51_validation_observation",
                "target_id": TARGET_ID,
                "shard_id": shard_id,
                "queue_status": text(row.get("queue_status")),
                "service_status": text(service.get("status")),
                "pass": bool(pass_value),
                "mean_min_distance_A": observed,
                "gate_threshold_A": threshold,
                "mean_min_distance_A_source": text(stage6.get("mean_min_distance_A_source")),
                "min_frames_observed": safe_int(stage6.get("min_frames_observed")),
                "summary_json": summary_path,
            }
        )
    return rows


def _post_hold_rows(execution_queue_payload: dict[str, Any]) -> list[dict[str, Any]]:
    target_rows = _target_rows(execution_queue_payload)
    last_hold_index = max(
        (idx for idx, row in enumerate(target_rows) if text(row.get("queue_status")) == "explicit_hold"),
        default=-1,
    )
    return target_rows[last_hold_index + 1 :] if last_hold_index >= 0 else []


def _augment_gate51_validation(
    payload: dict[str, Any],
    execution_queue_payload: dict[str, Any],
    maybe_load_json_fn,
) -> dict[str, Any]:
    validation_rows = _gate51_validation_rows(execution_queue_payload, maybe_load_json_fn)
    post_hold_rows = _post_hold_rows(execution_queue_payload)
    post_hold_shards = {text(row.get("shard_id")) for row in post_hold_rows}
    success_rows = [row for row in validation_rows if row.get("pass") is True]
    success_shards = {text(row.get("shard_id")) for row in success_rows}
    branch_validated = bool(post_hold_shards) and post_hold_shards == success_shards
    values = [safe_float(row.get("mean_min_distance_A")) for row in success_rows if safe_float(row.get("mean_min_distance_A")) > 0]
    summary = payload["summary"]
    summary.update(
        {
            "gate51_validation_row_count": len(validation_rows),
            "gate51_validation_success_count": len(success_rows),
            "gate51_validation_all_post_hold_success": branch_validated,
            "gate51_validation_start_shard_id": text(success_rows[0].get("shard_id")) if success_rows else "",
            "gate51_validation_end_shard_id": text(success_rows[-1].get("shard_id")) if success_rows else "",
            "gate51_validation_observed_metric_min_A": round(min(values), 3) if values else 0.0,
            "gate51_validation_observed_metric_mean_A": round(sum(values) / len(values), 3) if values else 0.0,
            "gate51_validation_observed_metric_max_A": round(max(values), 3) if values else 0.0,
        }
    )
    if branch_validated:
        summary["stage6_tuning_state"] = "guarded_gate51_validated_default_lane_closed"
        summary["next_retry_shard_id"] = ""
        summary["next_required_step"] = (
            "Promote T. cruzi KRS1 guarded gate5.1 as validated, keep the default lane closed, "
            "and allow LRRK2 to continue as the successor broad lane."
        )
    else:
        summary["stage6_tuning_state"] = "guarded_gate51_review_default_lane_closed"
    payload["rows"] = list(payload.get("rows", [])) + validation_rows
    return payload


def build_payload(execution_queue_payload: dict, throughput_bridge_payload: dict) -> dict:
    payload = build_stage6_tuning_payload(
        target_id=TARGET_ID,
        target_slug=TARGET_SLUG,
        status="wetlab_tcruzi_krs1_stage6_tuning_surface_ready",
        execution_queue_payload=execution_queue_payload,
        throughput_bridge_payload=throughput_bridge_payload,
        maybe_load_json=maybe_load_json,
        candidate_thresholds=[
            ("candidate_5.0", 5.0),
            ("candidate_5.05", 5.05),
            ("candidate_5.1", 5.1),
            ("candidate_5.5", 5.5),
        ],
        next_step_template=(
            "Run the {target_id} exploratory gate{immediately_runnable_threshold} retry for {shard_id}; "
            "use gate{immediately_runnable_threshold} as the immediately runnable family for the observed {recommended_threshold}A band "
            "and keep the default lane closed until the result is reviewed."
        ),
    )
    payload["structured"] = {
        "execution_queue_artifact": "runs/wetlab_broad_screen_execution_queue_current.md",
        "throughput_bridge_artifact": "runs/wetlab_broad_screen_throughput_bridge_current.md",
    }
    return _augment_gate51_validation(payload, execution_queue_payload, maybe_load_json)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the T. cruzi KRS1 stage6 tuning surface.")
    parser.add_argument("--execution-queue-json", default=DEFAULT_EXECUTION_QUEUE_JSON)
    parser.add_argument("--throughput-bridge-json", default=DEFAULT_THROUGHPUT_BRIDGE_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    write_artifact(
        args.out_md,
        "Wet-Lab T. cruzi KRS1 Stage6 Tuning Surface",
        build_payload(load_json(args.execution_queue_json), load_json(args.throughput_bridge_json)),
    )


if __name__ == "__main__":
    main()
