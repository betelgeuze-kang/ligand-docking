#!/usr/bin/env python3
from __future__ import annotations

import argparse

from tools.wetlab_target_render_utils import write_artifact

DEFAULT_OUT_MD = "runs/wetlab_broad_screen_bulk_result_row_examples_current.md"


def build_payload() -> dict:
    rows = [
        {
            "target_id": "CA IX",
            "compound_name": "Acetazolamide",
            "bulk_rank": 1,
            "bulk_score": 92.4,
            "shard_id": "03_of_20",
            "seed_status": "broad_screen_actual_result_example",
            "first_contact_use_mode": "benchmark_control",
            "vendor_check_required": False,
            "cost_check_required": False,
            "selectivity_note": "Keep CA II and CA XII counterscreens attached when promoting acidic-buffer CA IX rows.",
            "usage_rationale": "Representative acidic-buffer broad-screen row showing how a known CA scaffold would be expressed in the source file before autofill reduction.",
            "must_not_do": "Do not treat this example row as proof of CA IX selectivity without counterscreen confirmation.",
            "source_anchor": "caix_broad_screen_shard_03_example",
            "source_url": "runs/wetlab_broad_screen_bulk_result_row_examples_current.md",
        },
        {
            "target_id": "CA IX",
            "compound_name": "Methazolamide",
            "bulk_rank": 2,
            "bulk_score": 89.1,
            "shard_id": "03_of_20",
            "seed_status": "broad_screen_actual_result_example",
            "first_contact_use_mode": "benchmark_control",
            "vendor_check_required": False,
            "cost_check_required": False,
            "selectivity_note": "Example follow-on CA row showing the same target-level source shape with a second clinically legible scaffold.",
            "usage_rationale": "Represents the second retained row after shard-level aggregation and target-local rerank.",
            "must_not_do": "Do not collapse this into a CA IX-only claim before CA II and CA XII counterscreens resolve.",
            "source_anchor": "caix_broad_screen_shard_03_example",
            "source_url": "runs/wetlab_broad_screen_bulk_result_row_examples_current.md",
        },
    ]
    return {
        "summary": {
            "status": "wetlab_broad_screen_bulk_result_row_examples_ready",
            "example_row_count": len(rows),
            "target_id": "CA IX",
            "schema_artifact": "runs/wetlab_broad_screen_bulk_result_source_schema_current.md",
            "next_required_step": "Copy these field shapes into the real bulk-result source file as shard-level or target-level results land.",
        },
        "structured": {
            "intended_source_json": "runs/wetlab_broad_screen_bulk_results_source_current.json",
            "current_active_shard": "CA IX 04_of_20",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build example bulk-result rows that conform to the broad-screen source schema.")
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    write_artifact(args.out_md, "Wet-Lab Broad Screen Bulk Result Row Examples", build_payload())
