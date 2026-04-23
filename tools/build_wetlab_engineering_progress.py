#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import maybe_load_json, write_artifact

DEFAULT_PRECISION_MONITOR_JSON = "runs/wetlab_broad_screen_precision_monitor_current.json"
DEFAULT_RERANK_JSON = "runs/wetlab_broad_screen_target_rerank_current.json"
DEFAULT_SOURCE_JSON = "runs/wetlab_broad_screen_bulk_results_source_current.json"
DEFAULT_STABILITY_JSON = "runs/wetlab_broad_screen_stability_score_current.json"
DEFAULT_ANTITARGET_QUEUE_JSON = "runs/wetlab_broad_screen_antitarget_queue_current.json"
DEFAULT_ANTITARGET_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_antitarget_execution_queue_current.json"
DEFAULT_ACTUAL_APPEND_JSON = "runs/wetlab_broad_screen_actual_append_current.json"
DEFAULT_THROUGHPUT_BRIDGE_JSON = "runs/wetlab_broad_screen_throughput_bridge_current.json"
DEFAULT_OUT_MD = "runs/wetlab_engineering_progress_current.md"


def build_payload(
    precision_monitor: dict[str, Any] | None = None,
    rerank_payload: dict[str, Any] | None = None,
    source_payload: dict[str, Any] | None = None,
    stability_payload: dict[str, Any] | None = None,
    antitarget_queue_payload: dict[str, Any] | None = None,
    antitarget_execution_queue_payload: dict[str, Any] | None = None,
    actual_append_payload: dict[str, Any] | None = None,
    throughput_bridge_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    monitor_summary = dict((precision_monitor or {}).get("summary", {}) or {})
    rerank_summary = dict((rerank_payload or {}).get("summary", {}) or {})
    source_summary = dict((source_payload or {}).get("summary", {}) or {})
    stability_summary = dict((stability_payload or {}).get("summary", {}) or {})
    antitarget_summary = dict((antitarget_queue_payload or {}).get("summary", {}) or {})
    antitarget_execution_summary = dict((antitarget_execution_queue_payload or {}).get("summary", {}) or {})
    append_summary = dict((actual_append_payload or {}).get("summary", {}) or {})
    throughput_summary = dict((throughput_bridge_payload or {}).get("summary", {}) or {})
    append_status = str(append_summary.get("status", "")).strip()

    rows = [
        {
            "workstream": "monitor_refresh_lightening",
            "status": "implemented",
            "progress_pct": 100,
            "what_exists_now": "campaign monitor supports light/full/none refresh modes with periodic full refresh in loop mode",
            "missing_next": "",
        },
        {
            "workstream": "stability_score_design",
            "status": "implemented" if str(stability_summary.get("status", "")).strip() == "wetlab_broad_screen_stability_score_ready" else "designed_not_implemented",
            "progress_pct": 100 if str(stability_summary.get("status", "")).strip() == "wetlab_broad_screen_stability_score_ready" else 35,
            "what_exists_now": "target_rerank plus explicit target-level stability_score and stability_band",
            "missing_next": "" if str(stability_summary.get("status", "")).strip() == "wetlab_broad_screen_stability_score_ready" else "explicit stability score using top-k overlap, score margin, and shard churn",
        },
        {
            "workstream": "anti_target_bulk_queue_design",
            "status": "implemented" if str(antitarget_summary.get("status", "")).strip() == "wetlab_broad_screen_antitarget_queue_ready" else "designed_not_implemented",
            "progress_pct": 100 if str(antitarget_summary.get("status", "")).strip() == "wetlab_broad_screen_antitarget_queue_ready" else 25,
            "what_exists_now": "serialized anti-target queue plus execution view that can represent compute-attached counterscreen rows once primary full_bulk_top3_ready opens the panel",
            "missing_next": "" if str(antitarget_summary.get("status", "")).strip() == "wetlab_broad_screen_antitarget_queue_ready" else "serialized counterscreen queue that mirrors the main broad-screen queue",
        },
        {
            "workstream": "auto_append_pipeline",
            "status": "implemented" if append_status.startswith("wetlab_broad_screen_actual_append_") else "partially_implemented",
            "progress_pct": 100 if append_status.startswith("wetlab_broad_screen_actual_append_") else 70,
            "what_exists_now": "single-command append pipeline plus enqueue/flush batch mode with minimal/full refresh tiers",
            "missing_next": "" if append_status.startswith("wetlab_broad_screen_actual_append_") else "single-command append pipeline plus enqueue/flush batch mode",
        },
        {
            "workstream": "broad_screen_runtime_monitoring",
            "status": "implemented",
            "progress_pct": 100,
            "what_exists_now": "precision monitor artifact plus CLI loop renderer that keeps primary and counterscreen compute lanes visible",
            "missing_next": "",
        },
        {
            "workstream": "throughput_runner_bridge",
            "status": "implemented" if str(throughput_summary.get("status", "")).strip() == "wetlab_broad_screen_throughput_bridge_ready" else "designed_not_implemented",
            "progress_pct": 100 if str(throughput_summary.get("status", "")).strip() == "wetlab_broad_screen_throughput_bridge_ready" else 40,
            "what_exists_now": "current actionable broad-screen shard can be sliced into a ligand manifest and emitted as a speedpack HTVS launch packet",
            "missing_next": "" if str(throughput_summary.get("status", "")).strip() == "wetlab_broad_screen_throughput_bridge_ready" else "current actionable broad-screen shard to speedpack HTVS launch packet bridge",
        },
    ]

    return {
        "summary": {
            "status": "wetlab_engineering_progress_ready",
            "overall_progress_band": "active_buildout",
            "broad_screen_completion_pct": float(monitor_summary.get("completion_pct", 0.0) or 0.0),
            "broad_screen_resolved_shards": int(monitor_summary.get("resolved_shards", 0) or 0),
            "broad_screen_running_shards": int(monitor_summary.get("running_shards", 0) or 0),
            "full_bulk_ready_target_count": int(rerank_summary.get("full_bulk_ready_target_count", 0) or 0),
            "actual_row_count": int(source_summary.get("actual_row_count", 0) or 0),
            "stability_ready": bool(str(stability_summary.get("status", "")).strip() == "wetlab_broad_screen_stability_score_ready"),
            "anti_target_queue_ready": bool(str(antitarget_summary.get("status", "")).strip() == "wetlab_broad_screen_antitarget_queue_ready"),
            "anti_target_execution_queue_ready": bool(
                str(antitarget_execution_summary.get("status", "")).strip() == "wetlab_broad_screen_antitarget_execution_queue_ready"
            ),
            "anti_target_running_rows": int(antitarget_execution_summary.get("running_row_count", 0) or 0),
            "auto_append_ready": bool(append_status.startswith("wetlab_broad_screen_actual_append_")),
            "append_batch_pending_entry_count": int(append_summary.get("queued_pending_entry_count", 0) or 0),
            "throughput_bridge_ready": bool(str(throughput_summary.get("status", "")).strip() == "wetlab_broad_screen_throughput_bridge_ready"),
            "throughput_bridge_execute_ready": bool(throughput_summary.get("throughput_execute_ready", False)),
            "next_required_step": "Use light-refresh monitoring while the active shard runs; keep compute-attached counterscreen rows aligned with their watcher state, batch shard-row appends when possible, and hand the current actionable shard to the throughput bridge when you want speedpack execution.",
        },
        "structured": {
            "precision_monitor_artifact": "runs/wetlab_broad_screen_precision_monitor_current.md",
            "rerank_artifact": "runs/wetlab_broad_screen_target_rerank_current.md",
            "source_artifact": "runs/wetlab_broad_screen_bulk_results_source_current.md",
            "stability_artifact": "runs/wetlab_broad_screen_stability_score_current.md",
            "anti_target_queue_artifact": "runs/wetlab_broad_screen_antitarget_queue_current.md",
            "anti_target_execution_queue_artifact": "runs/wetlab_broad_screen_antitarget_execution_queue_current.md",
            "actual_append_artifact": "runs/wetlab_broad_screen_actual_append_current.md",
            "throughput_bridge_artifact": "runs/wetlab_broad_screen_throughput_bridge_current.md",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build engineering progress for the wet-lab broad-screen pipeline.")
    parser.add_argument("--precision-monitor-json", default=DEFAULT_PRECISION_MONITOR_JSON)
    parser.add_argument("--rerank-json", default=DEFAULT_RERANK_JSON)
    parser.add_argument("--source-json", default=DEFAULT_SOURCE_JSON)
    parser.add_argument("--stability-json", default=DEFAULT_STABILITY_JSON)
    parser.add_argument("--antitarget-queue-json", default=DEFAULT_ANTITARGET_QUEUE_JSON)
    parser.add_argument("--antitarget-execution-queue-json", default=DEFAULT_ANTITARGET_EXECUTION_QUEUE_JSON)
    parser.add_argument("--actual-append-json", default=DEFAULT_ACTUAL_APPEND_JSON)
    parser.add_argument("--throughput-bridge-json", default=DEFAULT_THROUGHPUT_BRIDGE_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    write_artifact(
        args.out_md,
        "Wet-Lab Engineering Progress",
        build_payload(
            precision_monitor=maybe_load_json(args.precision_monitor_json),
            rerank_payload=maybe_load_json(args.rerank_json),
            source_payload=maybe_load_json(args.source_json),
            stability_payload=maybe_load_json(args.stability_json),
            antitarget_queue_payload=maybe_load_json(args.antitarget_queue_json),
            antitarget_execution_queue_payload=maybe_load_json(args.antitarget_execution_queue_json),
            actual_append_payload=maybe_load_json(args.actual_append_json),
            throughput_bridge_payload=maybe_load_json(args.throughput_bridge_json),
        ),
    )
