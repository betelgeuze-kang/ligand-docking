#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, write_artifact

DEFAULT_BRIEF_INDEX_JSON = "runs/wetlab_wave1_target_brief_index_current.json"
DEFAULT_RENDER_SUITE_JSON = "runs/alk2_render_suite_current.json"
DEFAULT_EXPORT_JSON = "runs/alk2_m4k_export_current.json"
DEFAULT_CONDITION_CARD_JSON = "runs/alk2_condition_card_current.json"
DEFAULT_OUT_MD = "runs/alk2_launch_packet_current.md"


def _rows_by_target(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("target_id", "")): dict(row)
        for row in payload.get("rows", []) or []
        if str(row.get("target_id", "")).strip()
    }


def build_payload(brief_index: dict[str, Any], render_suite: dict[str, Any], export_payload: dict[str, Any], condition_card: dict[str, Any]) -> dict[str, Any]:
    brief = _rows_by_target(brief_index)["ALK2"]
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
            "status": "alk2_launch_packet_ready",
            "target_id": "ALK2",
            "serialized_queue_rank": 3,
            "serialized_run_order": "3_of_3_after_priority3",
            "execution_mode": "serialized_by_protein_target",
            "parallel_prep_allowed": True,
            "partner_track_id": str(suite_s.get("partner_track_id", export_s.get("partner_track_id", "M4K_open_science"))).strip() or "M4K_open_science",
            "render_suite_status": str(suite_s.get("status", "")).strip(),
            "export_status": str(export_s.get("status", "")).strip(),
            "required_artifact_count": len(rows),
            "mutant_context": str(condition_s.get("mutant_context", "")).strip(),
            "launch_readiness": "ready_for_serialized_execution",
            "execution_goal": "Close the next3 sequence with the mutant-aware ALK2 packet after Cruzain and PLpro are already resolved.",
            "blocking_rule": "This launch packet opens only after Cruzain and PLpro both reach result-ready or explicit hold in the serialized next3 queue.",
            "headline": str(brief.get("headline", "")).strip(),
            "next_required_step": "Launch ALK2 last in the next3 serialized queue, only after the Cruzain and PLpro packets have been resolved.",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the serialized execution launch packet for ALK2.")
    parser.add_argument("--brief-index-json", default=DEFAULT_BRIEF_INDEX_JSON)
    parser.add_argument("--render-suite-json", default=DEFAULT_RENDER_SUITE_JSON)
    parser.add_argument("--export-json", default=DEFAULT_EXPORT_JSON)
    parser.add_argument("--condition-card-json", default=DEFAULT_CONDITION_CARD_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(load_json(args.brief_index_json), load_json(args.render_suite_json), load_json(args.export_json), load_json(args.condition_card_json))
    write_artifact(DEFAULT_OUT_MD, "ALK2 Launch Packet", payload)


if __name__ == "__main__":
    main()
