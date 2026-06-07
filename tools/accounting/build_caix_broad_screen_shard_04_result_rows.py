#!/usr/bin/env python3
from __future__ import annotations

import argparse

from tools.wetlab_target_render_utils import write_artifact

DEFAULT_OUT_MD = "runs/caix_broad_screen_shard_04_result_rows_current.md"


def build_payload() -> dict:
    rows = [
        {
            "target_id": "CA IX",
            "compound_name": "Dichlorphenamide",
            "bulk_rank": 3,
            "bulk_score": 97.0,
            "shard_id": "04_of_20",
            "seed_status": "broad_screen_runtime_validation_result",
            "first_contact_use_mode": "benchmark_control",
            "vendor_check_required": False,
            "cost_check_required": False,
            "selectivity_note": "Third CA benchmark carried into the shard-04 result row so the acidic-buffer packet can move from partial to full bulk-derived top-3 coverage.",
            "usage_rationale": "Promotes the final benchmark control into the same shard-result source shape as the first two CA IX rows without changing the existing rank order.",
            "must_not_do": "Do not treat this runtime-validation row as a wet-lab measurement claim; use it as the target-local broad-screen result record for packet generation only.",
            "source_anchor": "caix_broad_screen_shard_04_runtime_validation",
            "source_url": "runs/caix_broad_screen_shard_04_result_rows_current.md",
        }
    ]
    return {
        "summary": {
            "status": "caix_broad_screen_shard_04_result_rows_ready",
            "target_id": "CA IX",
            "shard_id": "04_of_20",
            "row_count": len(rows),
            "next_required_step": "Merge this shard-04 row into the broad-screen source, then rerun bulk results, autofill, and target rerank surfaces.",
        },
        "structured": {
            "merge_target_artifact": "runs/wetlab_broad_screen_bulk_results_source_current.md",
            "merge_command": "python3 tools/build_wetlab_broad_screen_bulk_results_source_merge.py --rows-json runs/caix_broad_screen_shard_04_result_rows_current.json",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the CA IX shard-04 broad-screen result row artifact.")
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    write_artifact(args.out_md, "CA IX Broad Screen Shard 04 Result Rows", build_payload())
