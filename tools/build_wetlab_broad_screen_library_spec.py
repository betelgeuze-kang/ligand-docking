#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import write_artifact

DEFAULT_OUT_MD = "runs/wetlab_broad_screen_library_spec_current.md"


def build_payload() -> dict[str, Any]:
    rows = [
        {
            "lane_id": "approved_strict",
            "target_library_size": 3000,
            "scope": "strict_fda_approved_parent_drugs_only",
            "usage": "regulatory-clean benchmarking lane",
            "enabled": True,
        },
        {
            "lane_id": "broad_procurement_100k",
            "target_library_size": 100000,
            "scope": "approved_plus_global_off_patent_plus_clinically_used_plus_commodity_analogs",
            "usage": "real high-coverage repurposing-first discovery lane",
            "enabled": True,
        },
    ]
    return {
        "summary": {
            "status": "wetlab_broad_screen_library_spec_ready",
            "strict_fda_only_feasible_at_100k": False,
            "recommended_execution_lane": "broad_procurement_100k",
            "strict_lane_target_size": 3000,
            "broad_lane_target_size": 100000,
            "next_required_step": "Use broad_procurement_100k for the real screen, then reduce bulk results into the existing top-3 repurposing plus top-3 novelty packet layer.",
        },
        "structured": {
            "reason_for_split": "FDA-approved-only is too small for a true 100k library, so keep a strict regulatory benchmark lane and a separate broad procurement lane.",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the broad screening library spec for wet-lab repurposing discovery.")
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    write_artifact(args.out_md, "Wet-Lab Broad Screen Library Spec", build_payload())
