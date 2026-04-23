#!/usr/bin/env python3
from __future__ import annotations

import argparse

from tools.wetlab_target_render_utils import write_artifact


def _bool_arg(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"invalid boolean value: {value}")


def build_payload(
    *,
    target_id: str,
    shard_id: str,
    compound_name: str,
    bulk_rank: int,
    bulk_score: float,
    seed_status: str,
    first_contact_use_mode: str,
    vendor_check_required: bool,
    cost_check_required: bool,
    selectivity_note: str,
    usage_rationale: str,
    must_not_do: str,
    source_anchor: str,
    source_url: str,
) -> dict:
    rows = [
        {
            "target_id": target_id,
            "compound_name": compound_name,
            "bulk_rank": bulk_rank,
            "bulk_score": bulk_score,
            "shard_id": shard_id,
            "seed_status": seed_status,
            "first_contact_use_mode": first_contact_use_mode,
            "vendor_check_required": vendor_check_required,
            "cost_check_required": cost_check_required,
            "selectivity_note": selectivity_note,
            "usage_rationale": usage_rationale,
            "must_not_do": must_not_do,
            "source_anchor": source_anchor,
            "source_url": source_url,
        }
    ]
    return {
        "summary": {
            "status": "wetlab_broad_screen_result_rows_ready",
            "target_id": target_id,
            "shard_id": shard_id,
            "row_count": len(rows),
            "next_required_step": "Merge this shard row into the broad-screen source, then rerun bulk results, autofill, and target rerank surfaces.",
        },
        "structured": {
            "merge_target_artifact": "runs/wetlab_broad_screen_bulk_results_source_current.md",
            "merge_command": f"python3 tools/build_wetlab_broad_screen_bulk_results_source_merge.py --rows-json {source_url.replace('.md', '.json')}",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a single broad-screen shard result row artifact.")
    parser.add_argument("--target-id", required=True)
    parser.add_argument("--shard-id", required=True)
    parser.add_argument("--compound-name", required=True)
    parser.add_argument("--bulk-rank", type=int, required=True)
    parser.add_argument("--bulk-score", type=float, required=True)
    parser.add_argument("--seed-status", default="broad_screen_runtime_validation_result")
    parser.add_argument("--first-contact-use-mode", default="benchmark_control")
    parser.add_argument("--vendor-check-required", type=_bool_arg, default=False)
    parser.add_argument("--cost-check-required", type=_bool_arg, default=False)
    parser.add_argument("--selectivity-note", default="")
    parser.add_argument("--usage-rationale", default="")
    parser.add_argument("--must-not-do", default="Do not treat this runtime-validation row as a wet-lab measurement claim.")
    parser.add_argument("--source-anchor", required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--out-md", required=True)
    parser.add_argument("--title", default="Wet-Lab Broad Screen Result Rows")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    write_artifact(
        args.out_md,
        args.title,
        build_payload(
            target_id=args.target_id,
            shard_id=args.shard_id,
            compound_name=args.compound_name,
            bulk_rank=args.bulk_rank,
            bulk_score=args.bulk_score,
            seed_status=args.seed_status,
            first_contact_use_mode=args.first_contact_use_mode,
            vendor_check_required=args.vendor_check_required,
            cost_check_required=args.cost_check_required,
            selectivity_note=args.selectivity_note,
            usage_rationale=args.usage_rationale,
            must_not_do=args.must_not_do,
            source_anchor=args.source_anchor,
            source_url=args.source_url,
        ),
    )
