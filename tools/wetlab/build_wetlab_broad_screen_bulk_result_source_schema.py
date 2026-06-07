#!/usr/bin/env python3
from __future__ import annotations

import argparse

from tools.wetlab_target_render_utils import write_artifact

DEFAULT_OUT_MD = "runs/wetlab_broad_screen_bulk_result_source_schema_current.md"


def build_payload() -> dict:
    rows = [
        {
            "field_name": "target_id",
            "required": True,
            "field_type": "string",
            "example": "CA IX",
            "meaning": "Canonical target identifier used by the wet-lab portfolio and autofill bridge.",
        },
        {
            "field_name": "compound_name",
            "required": True,
            "field_type": "string",
            "example": "Acetazolamide",
            "meaning": "Human-readable compound identifier that will appear in the repurposing fill maps and outreach packets.",
        },
        {
            "field_name": "bulk_rank",
            "required": True,
            "field_type": "integer",
            "example": "1",
            "meaning": "Rank within the target-level broad screen after shard aggregation and any target-specific rerank.",
        },
        {
            "field_name": "bulk_score",
            "required": True,
            "field_type": "float",
            "example": "92.4",
            "meaning": "Comparable scalar score used to sort candidates inside a target before the top-3 repurposing reduction.",
        },
        {
            "field_name": "shard_id",
            "required": False,
            "field_type": "string",
            "example": "02_of_20",
            "meaning": "Shard provenance for the row's strongest evidence or for the current screening slice that produced it.",
        },
        {
            "field_name": "seed_status",
            "required": False,
            "field_type": "string",
            "example": "broad_screen_autofill",
            "meaning": "Optional status string passed through to the fill-map row for packet rendering.",
        },
        {
            "field_name": "first_contact_use_mode",
            "required": False,
            "field_type": "string",
            "example": "proceed_now",
            "meaning": "Optional packet intent override. If absent, autofill defaults to proceed_now for rank1 and comparator_only for later rows.",
        },
        {
            "field_name": "vendor_check_required",
            "required": False,
            "field_type": "boolean",
            "example": "false",
            "meaning": "Optional procurement flag propagated into the repurposing packet.",
        },
        {
            "field_name": "cost_check_required",
            "required": False,
            "field_type": "boolean",
            "example": "true",
            "meaning": "Optional cost-review flag propagated into the repurposing packet.",
        },
        {
            "field_name": "selectivity_note",
            "required": False,
            "field_type": "string",
            "example": "Preserve CA II and CA XII counterscreens in the first packet.",
            "meaning": "Optional target-facing note kept verbatim in the autofilled repurposing row.",
        },
        {
            "field_name": "usage_rationale",
            "required": False,
            "field_type": "string",
            "example": "Promoted from the broad acidic-buffer screen as one of the current top repurposing rows.",
            "meaning": "Optional rationale surfaced in the downstream packet.",
        },
        {
            "field_name": "must_not_do",
            "required": False,
            "field_type": "string",
            "example": "Do not claim target validation before counterscreens resolve.",
            "meaning": "Optional guardrail text carried through to the downstream packet.",
        },
        {
            "field_name": "source_anchor",
            "required": False,
            "field_type": "string",
            "example": "caix_broad_screen_shard_02",
            "meaning": "Optional provenance label for the evidence source.",
        },
        {
            "field_name": "source_url",
            "required": False,
            "field_type": "string",
            "example": "runs/wetlab_broad_screen_bulk_results_source_current.md",
            "meaning": "Optional provenance URL or local artifact reference.",
        },
    ]
    return {
        "summary": {
            "status": "wetlab_broad_screen_bulk_result_source_schema_ready",
            "required_field_count": 4,
            "optional_field_count": len(rows) - 4,
            "row_count": len(rows),
            "next_required_step": "Write actual target-level bulk rows with the four required fields, then materialize bulk results and rerun the autofill bridge.",
        },
        "structured": {
            "required_fields": "target_id ; compound_name ; bulk_rank ; bulk_score",
            "recommended_provenance_fields": "shard_id ; source_anchor ; source_url",
            "recommended_packet_fields": "first_contact_use_mode ; vendor_check_required ; cost_check_required ; selectivity_note ; usage_rationale ; must_not_do",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the schema reference for broad-screen bulk result source rows.")
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    write_artifact(args.out_md, "Wet-Lab Broad Screen Bulk Result Source Schema", build_payload())
