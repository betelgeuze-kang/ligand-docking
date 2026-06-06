#!/usr/bin/env python3
from __future__ import annotations

import argparse

from tools.wetlab_target_render_utils import load_json, write_artifact

DEFAULT_RENDER_SUITE_JSON = "runs/cathepsin_k_render_suite_current.json"
DEFAULT_CONDITION_CARD_JSON = "runs/cathepsin_k_condition_card_current.json"
DEFAULT_REPURPOSING_FILL_JSON = "runs/wetlab_cathepsin_k_repurposing_fill_map_current.json"
DEFAULT_NOVELTY_FILL_JSON = "runs/wetlab_cathepsin_k_novelty_fill_map_current.json"
DEFAULT_OUT_MD = "runs/cathepsin_k_launch_packet_current.md"


def build_payload(
    render_suite: dict,
    condition_card: dict,
    repurposing_fill_map: dict | None = None,
    novelty_fill_map: dict | None = None,
) -> dict:
    suite_s = dict(render_suite.get("summary", {}) or {})
    condition_s = dict(condition_card.get("structured", {}) or {})
    suite_rows = [dict(row) for row in render_suite.get("rows", []) or []]
    rep_rows = [
        dict(row)
        for row in ((repurposing_fill_map or {}).get("rows", []) or [])
        if str(row.get("target_id", "")).strip() == "Cathepsin K"
    ]
    nov_rows = [
        dict(row)
        for row in ((novelty_fill_map or {}).get("rows", []) or [])
        if str(row.get("target_id", "")).strip() == "Cathepsin K"
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
                "wet_lab_context"
                if str(row.get("artifact_kind", "")).strip() == "condition_card"
                else "selectivity_panel"
                if str(row.get("artifact_kind", "")).strip() == "selectivity_panel"
                else "execution_stack"
                if str(row.get("artifact_kind", "")).strip() == "assay_packet"
                else "decision_gate"
                if str(row.get("artifact_kind", "")).strip() == "go_no_go_card"
                else "partner_export"
            ),
        }
        for idx, row in enumerate(suite_rows, start=1)
    ]

    return {
        "summary": {
            "status": "cathepsin_k_launch_packet_ready",
            "target_id": "Cathepsin K",
            "serialized_queue_rank": 1,
            "serialized_run_order": "1_of_5_after_final2",
            "execution_mode": "serialized_by_protein_target",
            "parallel_prep_allowed": True,
            "partner_track_id": str(suite_s.get("partner_track_id", "acidic_protease_wave2")).strip() or "acidic_protease_wave2",
            "render_suite_status": str(suite_s.get("status", "")).strip(),
            "export_status": "cathepsin_k_acidic_protease_export_ready",
            "required_artifact_count": len(rows),
            "acidic_primary_arm": str(condition_s.get("acidic_primary_arm", "")).strip(),
            "neutral_contrast_arm": str(condition_s.get("neutral_contrast_arm", "")).strip(),
            "repurposing_filled_slot_count": rep_filled,
            "novelty_filled_slot_count": nov_filled,
            "repurposing_fill_status": "repurposing_ready" if rep_filled >= 3 else "repurposing_pending",
            "novelty_fill_status": "novelty_ready" if nov_filled >= 3 else "novelty_pending",
            "launch_readiness": launch_readiness,
            "execution_goal": "Open Wave 2 with Cathepsin K only after the final2 tail is resolved and the acidic-protease compound lanes are actually filled.",
            "blocking_rule": "Do not start Cathepsin K live execution until LbDHODH resolves and the repurposing plus novelty lanes are both filled.",
            "next_target_on_success": "Dengue NS2B-NS3 protease",
            "next_target_on_hold": "Dengue NS2B-NS3 protease",
            "headline": "Acidic-context Cathepsin K packet designed to separate true Cathepsin K signal from broader related-cathepsin activity.",
            "next_required_step": (
                "Keep Cathepsin K as the first Wave 2 slot and wait only for final2 release before launch."
                if launch_readiness == "ready_for_serialized_execution"
                else "Keep Cathepsin K as the first Wave 2 slot, but do not launch until final2 resolves and the missing compound lanes are filled."
            ),
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Cathepsin K serialized launch packet for Wave 2.")
    parser.add_argument("--render-suite-json", default=DEFAULT_RENDER_SUITE_JSON)
    parser.add_argument("--condition-card-json", default=DEFAULT_CONDITION_CARD_JSON)
    parser.add_argument("--repurposing-fill-json", default=DEFAULT_REPURPOSING_FILL_JSON)
    parser.add_argument("--novelty-fill-json", default=DEFAULT_NOVELTY_FILL_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        load_json(args.render_suite_json),
        load_json(args.condition_card_json),
        load_json(args.repurposing_fill_json),
        load_json(args.novelty_fill_json),
    )
    write_artifact(DEFAULT_OUT_MD, "Cathepsin K Launch Packet", payload)


if __name__ == "__main__":
    main()
