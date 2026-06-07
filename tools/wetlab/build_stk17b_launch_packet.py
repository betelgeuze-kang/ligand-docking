#!/usr/bin/env python3
from __future__ import annotations

import argparse

from tools.wetlab_target_render_utils import load_json, write_artifact

DEFAULT_BRIEF_INDEX_JSON = "runs/wetlab_wave1_target_brief_index_current.json"
DEFAULT_RENDER_SUITE_JSON = "runs/stk17b_render_suite_current.json"
DEFAULT_EXPORT_JSON = "runs/stk17b_sgc_export_current.json"
DEFAULT_CONDITION_CARD_JSON = "runs/stk17b_condition_card_current.json"
DEFAULT_OUT_MD = "runs/stk17b_launch_packet_current.md"
TARGET_ID = "STK17B (DRAK2)"


def _rows_by_target(payload: dict) -> dict[str, dict]:
    return {str(row.get("target_id", "")).strip(): dict(row) for row in payload.get("rows", []) or [] if str(row.get("target_id", "")).strip()}


def build_payload(brief_index: dict, render_suite: dict, export_payload: dict, condition_card: dict) -> dict:
    brief = _rows_by_target(brief_index)[TARGET_ID]
    suite_s = dict(render_suite.get("summary", {}) or {})
    export_s = dict(export_payload.get("summary", {}) or {})
    condition_s = dict(condition_card.get("structured", {}) or {})
    suite_rows = [dict(row) for row in render_suite.get("rows", []) or []]
    rows = [
        {
            "requirement_rank": str(idx),
            "artifact_kind": str(row.get("artifact_kind", "")).strip(),
            "artifact_path": str(row.get("artifact_path", "")).strip(),
            "launch_requirement": "must_exist_before_run",
            "queue_blocking": "hard_block",
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
            "status": "stk17b_launch_packet_ready",
            "target_id": TARGET_ID,
            "serialized_queue_rank": 1,
            "serialized_run_order": "1_of_2_after_next3",
            "execution_mode": "serialized_by_protein_target",
            "parallel_prep_allowed": True,
            "partner_track_id": str(suite_s.get("partner_track_id", export_s.get("partner_track_id", "SGC_dark_kinase"))).strip() or "SGC_dark_kinase",
            "render_suite_status": str(suite_s.get("status", "")).strip(),
            "export_status": str(export_s.get("status", "")).strip(),
            "required_artifact_count": len(rows),
            "probe_frame": str(condition_s.get("probe_frame", "")).strip(),
            "launch_readiness": "ready_after_next3_resolution",
            "execution_goal": "Open the final2 chain with STK17B only after next3 resolves, then keep LbDHODH blocked behind the live STK17B outcome.",
            "blocking_rule": "Do not start Leishmania braziliensis DHODH until STK17B reaches result-ready or explicit hold.",
            "next_target_on_success": "Leishmania braziliensis DHODH",
            "next_target_on_hold": "Leishmania braziliensis DHODH",
            "headline": str(brief.get("headline", "")).strip(),
            "next_required_step": "Launch STK17B first in the final2 serialized queue after the next3 final review resolves, while LbDHODH remains blocked.",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the serialized execution launch packet for STK17B.")
    parser.add_argument("--brief-index-json", default=DEFAULT_BRIEF_INDEX_JSON)
    parser.add_argument("--render-suite-json", default=DEFAULT_RENDER_SUITE_JSON)
    parser.add_argument("--export-json", default=DEFAULT_EXPORT_JSON)
    parser.add_argument("--condition-card-json", default=DEFAULT_CONDITION_CARD_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(load_json(args.brief_index_json), load_json(args.render_suite_json), load_json(args.export_json), load_json(args.condition_card_json))
    write_artifact(DEFAULT_OUT_MD, "STK17B Launch Packet", payload)


if __name__ == "__main__":
    main()
