#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, maybe_load_json, write_artifact

DEFAULT_PORTFOLIO_JSON = "runs/wetlab_partner_target_portfolio_current.json"
DEFAULT_BULK_RESULTS_JSON = "runs/wetlab_broad_screen_bulk_results_current.json"
DEFAULT_BRIDGE_JSON = "runs/wetlab_broad_screen_bridge_current.json"
DEFAULT_OUT_MD = "runs/wetlab_broad_screen_repurposing_autofill_current.md"


def _summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict((payload or {}).get("summary", {}) or {})


def _bulk_rows_by_target(payload: dict[str, Any] | None) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in ((payload or {}).get("rows", []) or []):
        target_id = str(row.get("target_id", "")).strip()
        if not target_id:
            continue
        grouped.setdefault(target_id, []).append(dict(row))
    return grouped


def _sort_target_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            int(row.get("bulk_rank", row.get("rank", 10**9)) or 10**9),
            -float(row.get("bulk_score", row.get("score", 0.0)) or 0.0),
            str(row.get("compound_name", row.get("preferred_name", ""))).strip().lower(),
        ),
    )


def build_payload(
    portfolio: dict[str, Any],
    bridge_payload: dict[str, Any],
    bulk_results: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bulk_by_target = _bulk_rows_by_target(bulk_results)
    portfolio_rows = [dict(row) for row in (portfolio.get("rows", []) or []) if str(row.get("target_id", "")).strip() and str(row.get("target_id", "")).strip() != "CA XII"]

    rows: list[dict[str, Any]] = []
    override_target_count = 0
    for priority_rank, target_row in enumerate(portfolio_rows, start=1):
        target_id = str(target_row["target_id"]).strip()
        ranked = _sort_target_rows(bulk_by_target.get(target_id, []))
        if len(ranked) < 3:
            continue
        override_target_count += 1
        for slot_rank, raw in enumerate(ranked[:3], start=1):
            compound_name = str(raw.get("compound_name", raw.get("preferred_name", raw.get("name", "")))).strip()
            rows.append(
                {
                    "priority_rank": priority_rank,
                    "target_id": target_id,
                    "slot_rank": slot_rank,
                    "compound_name": compound_name,
                    "bulk_rank": int(raw.get("bulk_rank", raw.get("rank", slot_rank)) or slot_rank),
                    "bulk_score": float(raw.get("bulk_score", raw.get("score", 0.0)) or 0.0),
                    "seed_status": str(raw.get("seed_status", "bulk_screen_autofill")).strip() or "bulk_screen_autofill",
                    "brief_slot_name": f"repurposing_{slot_rank}",
                    "first_contact_use_mode": str(raw.get("first_contact_use_mode", "proceed_now" if slot_rank == 1 else "comparator_only")).strip(),
                    "vendor_check_required": bool(raw.get("vendor_check_required", False)),
                    "cost_check_required": bool(raw.get("cost_check_required", False)),
                    "selectivity_note": str(raw.get("selectivity_note", "Bulk-screen-derived row; preserve the target-specific anti-target panel in the first packet.")).strip(),
                    "usage_rationale": str(raw.get("usage_rationale", "Automatically promoted from the broad-screen rerank as one of the current top repurposing candidates.")).strip(),
                    "must_not_do": str(raw.get("must_not_do", "Do not claim target validation until the wet-lab packet and counterscreens resolve.")).strip(),
                    "source_anchor": str(raw.get("source_anchor", "broad_screen_bulk_result")).strip() or "broad_screen_bulk_result",
                    "source_url": "runs/wetlab_broad_screen_repurposing_autofill_current.md",
                    "autofill_source": "broad_screen_bulk_result",
                    "row_status": "bulk_override_ready",
                }
            )

    bridge_summary = _summary(bridge_payload)
    bulk_result_present = bool((bulk_results or {}).get("rows"))
    return {
        "summary": {
            "status": "wetlab_broad_screen_repurposing_autofill_ready",
            "bulk_result_source_present": bulk_result_present,
            "override_target_count": override_target_count,
            "override_row_count": len(rows),
            "bridge_final_packet_shape": str(bridge_summary.get("final_packet_shape", "")).strip(),
            "manual_fill_replacement_ready": override_target_count > 0,
            "next_required_step": (
                "Rebuild the repurposing fill maps so bulk-derived rows replace the manual top-3 packets for the covered targets."
                if rows
                else "No bulk result rows are present yet; ingest target-level broad-screen results first, then rerun this autofill builder."
            ),
        },
        "structured": {
            "portfolio_artifact": "runs/wetlab_partner_target_portfolio_current.md",
            "bridge_artifact": "runs/wetlab_broad_screen_bridge_current.md",
            "bulk_result_source_artifact": "runs/wetlab_broad_screen_bulk_results_current.md",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the bulk-result-derived repurposing autofill rows for wet-lab packets.")
    parser.add_argument("--portfolio-json", default=DEFAULT_PORTFOLIO_JSON)
    parser.add_argument("--bridge-json", default=DEFAULT_BRIDGE_JSON)
    parser.add_argument("--bulk-results-json", default=DEFAULT_BULK_RESULTS_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    write_artifact(
        args.out_md,
        "Wet-Lab Broad Screen Repurposing Autofill",
        build_payload(
            load_json(args.portfolio_json),
            load_json(args.bridge_json),
            maybe_load_json(args.bulk_results_json),
        ),
    )
