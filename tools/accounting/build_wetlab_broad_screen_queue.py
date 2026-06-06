#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, write_artifact

DEFAULT_PORTFOLIO_JSON = "runs/wetlab_partner_target_portfolio_current.json"
DEFAULT_LIBRARY_SPEC_JSON = "runs/wetlab_broad_screen_library_spec_current.json"
DEFAULT_OUT_MD = "runs/wetlab_broad_screen_queue_current.md"
SHARD_SIZE = 5000


def _summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict((payload or {}).get("summary", {}) or {})


def build_payload(portfolio: dict[str, Any], library_spec: dict[str, Any]) -> dict[str, Any]:
    ls = _summary(library_spec)
    broad_size = int(ls.get("broad_lane_target_size", 100000) or 100000)
    shard_count = (broad_size + SHARD_SIZE - 1) // SHARD_SIZE
    targets = [
        dict(row)
        for row in portfolio.get("rows", []) or []
        if str(row.get("target_id", "")).strip() and str(row.get("target_id", "")).strip() != "CA XII"
    ]

    rows: list[dict[str, Any]] = []
    for target_rank, target in enumerate(targets, start=1):
        for shard_idx in range(shard_count):
            start = shard_idx * SHARD_SIZE + 1
            end = min((shard_idx + 1) * SHARD_SIZE, broad_size)
            rows.append(
                {
                    "queue_rank": len(rows) + 1,
                    "target_rank": target_rank,
                    "target_id": str(target.get("target_id", "")).strip(),
                    "wave": str(target.get("wave", "")).strip(),
                    "library_lane": "broad_procurement_100k",
                    "shard_id": f"{shard_idx + 1:02d}_of_{shard_count:02d}",
                    "compound_index_start": start,
                    "compound_index_end": end,
                    "shard_size": end - start + 1,
                    "queue_status": "ready_for_bulk_screen",
                }
            )

    return {
        "summary": {
            "status": "wetlab_broad_screen_queue_ready",
            "target_count": len(targets),
            "library_lane": "broad_procurement_100k",
            "library_size": broad_size,
            "shard_size": SHARD_SIZE,
            "shard_count_per_target": shard_count,
            "total_queue_rows": len(rows),
            "next_required_step": "Run target-by-target serialized execution while processing library shards within each target, then bridge bulk results into the existing bounded shortlist packets.",
        },
        "structured": {
            "portfolio_artifact": "runs/wetlab_partner_target_portfolio_current.md",
            "library_spec_artifact": "runs/wetlab_broad_screen_library_spec_current.md",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the target-by-shard queue for the 100k broad procurement screen.")
    parser.add_argument("--portfolio-json", default=DEFAULT_PORTFOLIO_JSON)
    parser.add_argument("--library-spec-json", default=DEFAULT_LIBRARY_SPEC_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    payload = build_payload(load_json(args.portfolio_json), load_json(args.library_spec_json))
    write_artifact(args.out_md, "Wet-Lab Broad Screen Queue", payload)
