#!/usr/bin/env python3
from __future__ import annotations

import argparse

from tools.wetlab_target_render_utils import load_json, write_artifact

DEFAULT_RENDER_SUITE_JSON = "runs/lbdhodh_render_suite_current.json"
DEFAULT_EXPORT_JSON = "runs/lbdhodh_dndi_ipk_export_current.json"
DEFAULT_CONDITION_CARD_JSON = "runs/lbdhodh_condition_card_current.json"
DEFAULT_REPURPOSING_FILL_JSON = "runs/wetlab_lbdhodh_repurposing_fill_map_current.json"
DEFAULT_NOVELTY_FILL_JSON = "runs/wetlab_lbdhodh_novelty_fill_map_current.json"
DEFAULT_OUT_MD = "runs/lbdhodh_launch_packet_current.md"
TARGET_ID = "Leishmania braziliensis DHODH"


def build_payload(render_suite: dict, export_payload: dict, condition_card: dict, repurposing_fill_map: dict | None = None, novelty_fill_map: dict | None = None) -> dict:
    suite_s = dict(render_suite.get("summary", {}) or {})
    export_s = dict(export_payload.get("summary", {}) or {})
    condition_s = dict(condition_card.get("structured", {}) or {})
    suite_rows = [dict(row) for row in render_suite.get("rows", []) or []]
    rep_rows = [
        dict(fill_row)
        for fill_row in ((repurposing_fill_map or {}).get("rows", []) or [])
        if str(fill_row.get("target_id", "")).strip() == TARGET_ID
    ]
    nov_rows = [
        dict(fill_row)
        for fill_row in ((novelty_fill_map or {}).get("rows", []) or [])
        if str(fill_row.get("target_id", "")).strip() == TARGET_ID
    ]
    rep_filled = len(rep_rows)
    nov_filled = len(nov_rows)
    launch_readiness = "ready_for_serialized_execution" if rep_filled >= 3 and nov_filled >= 3 else "blocked_on_compound_fill"
    rows = [
        {
            "requirement_rank": str(idx),
            "artifact_kind": str(row.get("artifact_kind", "")).strip(),
            "artifact_path": str(row.get("artifact_path", "")).strip(),
            "launch_requirement": "must_exist_before_run",
            "queue_blocking": "hard_block" if launch_readiness == "ready_for_serialized_execution" else "content_block",
            "handoff_role": (
                "wet_lab_context" if str(row.get("artifact_kind", "")).strip() == "condition_card" else
                "selectivity_panel" if str(row.get("artifact_kind", "")).strip() == "selectivity_panel" else
                "execution_stack" if str(row.get("artifact_kind", "")).strip() == "assay_packet" else
                "decision_gate" if str(row.get("artifact_kind", "")).strip() == "go_no_go_card" else
                "partner_export"
            ),
        }
        for idx, row in enumerate(suite_rows, start=1)
    ]
    return {
        "summary": {
            "status": "lbdhodh_launch_packet_ready",
            "target_id": TARGET_ID,
            "serialized_queue_rank": 2,
            "serialized_run_order": "2_of_2_after_next3",
            "execution_mode": "serialized_by_protein_target",
            "parallel_prep_allowed": True,
            "partner_track_id": str(suite_s.get("partner_track_id", "DNDi_IPK")).strip() or "DNDi_IPK",
            "render_suite_status": str(suite_s.get("status", "")).strip(),
            "export_status": str(export_s.get("status", "")).strip() or ("lbdhodh_dndi_ipk_export_ready" if launch_readiness == "ready_for_serialized_execution" else "lbdhodh_dndi_ipk_export_pending_compound_fill"),
            "required_artifact_count": len(rows),
            "host_counterframe": str(condition_s.get("host_counterframe", condition_s.get("host_counter_context", ""))).strip(),
            "repurposing_filled_slot_count": rep_filled,
            "novelty_filled_slot_count": nov_filled,
            "repurposing_fill_status": "repurposing_ready" if rep_filled >= 3 else "repurposing_pending",
            "novelty_fill_status": "novelty_ready" if nov_filled >= 3 else "novelty_pending",
            "launch_readiness": launch_readiness,
            "execution_goal": "Close the final2 sequence with LbDHODH only after STK17B is resolved and the neglected-enzyme content is actually filled.",
            "blocking_rule": "Do not start live LbDHODH execution until STK17B is resolved and the repurposing plus novelty lanes are both filled.",
            "headline": str(suite_s.get("headline", "")).strip() or "Neglected-disease DHODH packets that make host-enzyme separation part of the first experiment.",
            "next_required_step": (
                "LbDHODH content is fully filled; keep it in the second final2 slot and wait only for STK17B result resolution before launch."
                if launch_readiness == "ready_for_serialized_execution"
                else "Keep LbDHODH in the second final2 slot, but do not launch until STK17B resolves and the missing compound lanes are filled."
            ),
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the serialized execution launch packet for LbDHODH.")
    parser.add_argument("--render-suite-json", default=DEFAULT_RENDER_SUITE_JSON)
    parser.add_argument("--export-json", default=DEFAULT_EXPORT_JSON)
    parser.add_argument("--condition-card-json", default=DEFAULT_CONDITION_CARD_JSON)
    parser.add_argument("--repurposing-fill-json", default=DEFAULT_REPURPOSING_FILL_JSON)
    parser.add_argument("--novelty-fill-json", default=DEFAULT_NOVELTY_FILL_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        load_json(args.render_suite_json),
        load_json(args.export_json),
        load_json(args.condition_card_json),
        load_json(args.repurposing_fill_json),
        load_json(args.novelty_fill_json),
    )
    write_artifact(DEFAULT_OUT_MD, "LbDHODH Launch Packet", payload)


if __name__ == "__main__":
    main()
