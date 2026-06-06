#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, write_artifact

DEFAULT_LIBRARY_SPEC_JSON = "runs/wetlab_broad_screen_library_spec_current.json"
DEFAULT_QUEUE_JSON = "runs/wetlab_broad_screen_queue_current.json"
DEFAULT_OUT_MD = "runs/wetlab_broad_screen_bridge_current.md"


def _summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict((payload or {}).get("summary", {}) or {})


def build_payload(library_spec: dict[str, Any], broad_queue: dict[str, Any]) -> dict[str, Any]:
    ls = _summary(library_spec)
    qs = _summary(broad_queue)
    rows = [
        {
            "bridge_stage": "bulk_screen",
            "input": "100k broad_procurement lane",
            "output": "raw target-by-compound scores",
            "topk_policy": "keep top_200_per_target",
        },
        {
            "bridge_stage": "anti_target_filter",
            "input": "top_200_per_target",
            "output": "deselected target-specific shortlist",
            "topk_policy": "keep top_50_per_target",
        },
        {
            "bridge_stage": "condition_rerank",
            "input": "top_50_per_target",
            "output": "condition-aware repurposing shortlist",
            "topk_policy": "keep top_10_per_target",
        },
        {
            "bridge_stage": "packet_binding",
            "input": "top_10_per_target",
            "output": "top-3 repurposing + top-3 novelty",
            "topk_policy": "bind into existing launch/export packets",
        },
    ]
    return {
        "summary": {
            "status": "wetlab_broad_screen_bridge_ready",
            "library_lane": str(ls.get("recommended_execution_lane", "")).strip(),
            "library_size": int(ls.get("broad_lane_target_size", 0) or 0),
            "queue_row_count": int(qs.get("total_queue_rows", 0) or 0),
            "final_packet_shape": "top-3 repurposing + top-3 novelty",
            "next_required_step": "Implement score ingestion per shard and use this bridge to replace manual repurposing fill maps with bulk-screen-derived rows.",
        },
        "structured": {
            "library_spec_artifact": "runs/wetlab_broad_screen_library_spec_current.md",
            "broad_queue_artifact": "runs/wetlab_broad_screen_queue_current.md",
            "packet_binding_targets": "runs/wetlab_partner_send_round_current.md ; runs/wetlab_final_campaign_summary_current.md",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the bridge from the 100k broad screen to bounded partner packets.")
    parser.add_argument("--library-spec-json", default=DEFAULT_LIBRARY_SPEC_JSON)
    parser.add_argument("--queue-json", default=DEFAULT_QUEUE_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    payload = build_payload(load_json(args.library_spec_json), load_json(args.queue_json))
    write_artifact(args.out_md, "Wet-Lab Broad Screen Bridge", payload)
