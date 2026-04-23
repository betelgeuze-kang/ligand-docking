#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, write_artifact

DEFAULT_BRIEF_INDEX_JSON = "runs/wetlab_wave1_target_brief_index_current.json"
DEFAULT_RENDER_SUITE_JSON = "runs/sarscov2_plpro_render_suite_current.json"
DEFAULT_EXPORT_JSON = "runs/sarscov2_plpro_readdi_export_current.json"
DEFAULT_CONDITION_CARD_JSON = "runs/sarscov2_plpro_condition_card_current.json"
DEFAULT_OUT_MD = "runs/sarscov2_plpro_launch_packet_current.md"


def _rows_by_target(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("target_id", "")): dict(row)
        for row in payload.get("rows", []) or []
        if str(row.get("target_id", "")).strip()
    }


def build_payload(brief_index: dict[str, Any], render_suite: dict[str, Any], export_payload: dict[str, Any], condition_card: dict[str, Any]) -> dict[str, Any]:
    brief = _rows_by_target(brief_index)["SARS-CoV-2 PLpro"]
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
                if str(row.get("artifact_kind", "")).strip() in {"host_dub_panel", "selectivity_panel"}
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
            "status": "sarscov2_plpro_launch_packet_ready",
            "target_id": "SARS-CoV-2 PLpro",
            "serialized_queue_rank": 2,
            "serialized_run_order": "2_of_3_after_priority3",
            "execution_mode": "serialized_by_protein_target",
            "parallel_prep_allowed": True,
            "partner_track_id": str(suite_s.get("partner_track_id", export_s.get("partner_track_id", "READDI_Korea"))).strip() or "READDI_Korea",
            "render_suite_status": str(suite_s.get("status", "")).strip(),
            "export_status": str(export_s.get("status", "")).strip(),
            "required_artifact_count": len(rows),
            "host_dub_focus": str(condition_s.get("primary_risk", "")).strip(),
            "launch_readiness": "ready_for_serialized_execution",
            "execution_goal": "Open the PLpro companion antiviral packet only after Cruzain clears, with human-DUB cleanup fixed from the start.",
            "blocking_rule": "Do not start ALK2 until this PLpro packet reaches result-ready or explicit hold.",
            "next_target_on_success": "ALK2",
            "next_target_on_hold": "ALK2",
            "headline": str(brief.get("headline", "")).strip(),
            "next_required_step": "Launch PLpro second in the next3 serialized queue after Cruzain reaches result-ready or explicit hold, while ALK2 remains prep-only.",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the serialized execution launch packet for SARS-CoV-2 PLpro.")
    parser.add_argument("--brief-index-json", default=DEFAULT_BRIEF_INDEX_JSON)
    parser.add_argument("--render-suite-json", default=DEFAULT_RENDER_SUITE_JSON)
    parser.add_argument("--export-json", default=DEFAULT_EXPORT_JSON)
    parser.add_argument("--condition-card-json", default=DEFAULT_CONDITION_CARD_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(load_json(args.brief_index_json), load_json(args.render_suite_json), load_json(args.export_json), load_json(args.condition_card_json))
    write_artifact(DEFAULT_OUT_MD, "SARS-CoV-2 PLpro Launch Packet", payload)


if __name__ == "__main__":
    main()
