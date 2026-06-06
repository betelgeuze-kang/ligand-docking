#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from tools.wetlab_target_render_utils import maybe_load_json, resolve, write_artifact

DEFAULT_SOURCE_JSONS = (
    "runs/wetlab_priority3_repurposing_fill_map_current.json",
    "runs/wetlab_next3_repurposing_fill_map_current.json",
    "runs/wetlab_stk17b_repurposing_fill_map_current.json",
    "runs/wetlab_lbdhodh_repurposing_fill_map_current.json",
    "runs/wetlab_cathepsin_k_repurposing_fill_map_current.json",
    "runs/wetlab_dengue_ns2b_ns3_protease_repurposing_fill_map_current.json",
    "runs/wetlab_dpre1_repurposing_fill_map_current.json",
    "runs/wetlab_tcruzi_krs1_repurposing_fill_map_current.json",
    "runs/wetlab_lrrk2_repurposing_fill_map_current.json",
)
DEFAULT_OUT_MD = "runs/wetlab_broad_screen_bulk_results_source_current.md"


def build_payload(source_payloads: list[dict[str, Any]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    target_count = 0

    for payload in source_payloads:
        raw_rows = [dict(row) for row in (payload.get("rows", []) or [])]
        if not raw_rows:
            continue
        target_count += 1
        for row in raw_rows:
            slot_rank = int(row.get("slot_rank", row.get("rank", 0)) or 0)
            rows.append(
                {
                    "target_id": str(row.get("target_id", "")).strip(),
                    "compound_name": str(row.get("compound_name", "")).strip(),
                    "bulk_rank": slot_rank,
                    "bulk_score": float(100 - slot_rank),
                    "seed_status": "bootstrap_from_manual_fill_map",
                    "first_contact_use_mode": str(row.get("first_contact_use_mode", "")).strip(),
                    "vendor_check_required": bool(row.get("vendor_check_required", False)),
                    "cost_check_required": bool(row.get("cost_check_required", False)),
                    "selectivity_note": str(row.get("selectivity_note", "")).strip(),
                    "usage_rationale": str(row.get("usage_rationale", "")).strip(),
                    "must_not_do": str(row.get("must_not_do", "")).strip(),
                    "source_anchor": "broad_screen_bootstrap_from_manual_fill_maps",
                    "source_url": "runs/wetlab_broad_screen_bulk_results_source_current.md",
                }
            )

    return {
        "summary": {
            "status": "wetlab_broad_screen_bulk_results_source_ready",
            "target_count": len({str(row.get("target_id", "")).strip() for row in rows if str(row.get("target_id", "")).strip()}),
            "row_count": len(rows),
            "bootstrap_mode": "manual_fill_map_seed",
            "next_required_step": "Materialize these bootstrap rows into bulk results, then rebuild the repurposing autofill and repurposing fill maps.",
        },
        "structured": {
            "source_artifacts": " ; ".join(DEFAULT_SOURCE_JSONS),
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a bootstrap broad-screen bulk result source from current repurposing fill maps.")
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    payloads = [maybe_load_json(path) for path in DEFAULT_SOURCE_JSONS]
    write_artifact(args.out_md, "Wet-Lab Broad Screen Bootstrap Bulk Results Source", build_payload(payloads))
