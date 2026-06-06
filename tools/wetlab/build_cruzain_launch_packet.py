#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, write_artifact

DEFAULT_RENDER_SUITE_JSON = "runs/cruzain_render_suite_current.json"
DEFAULT_EXPORT_JSON = "runs/cruzain_dndi_ipk_export_current.json"
DEFAULT_OUT_MD = "runs/cruzain_launch_packet_current.md"


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    return dict(payload.get("summary", {}) or {})


def build_payload(render_suite: dict[str, Any], partner_export: dict[str, Any]) -> dict[str, Any]:
    suite_s = _summary(render_suite)
    export_s = _summary(partner_export)
    suite_rows = [dict(row) for row in render_suite.get("rows", []) or []]
    rows = [
        {
            "launch_step_rank": idx,
            "artifact_kind": row["artifact_kind"],
            "artifact_path": row["artifact_path"],
            "artifact_status": row["status"],
            "launch_role": (
                "fix_assay_context"
                if row["artifact_kind"] == "condition_card"
                else "clear_host_liability"
                if row["artifact_kind"] == "host_protease_panel"
                else "run_primary_stack"
                if row["artifact_kind"] == "assay_packet"
                else "classify_outcomes"
                if row["artifact_kind"] == "go_no_go_card"
                else "freeze_partner_export"
            ),
        }
        for idx, row in enumerate(suite_rows, start=1)
    ]
    return {
        "summary": {
            "status": "cruzain_launch_packet_ready",
            "target_id": "Cruzain",
            "serialized_queue_rank": 1,
            "serialized_run_order": "1_of_3_after_priority3",
            "execution_mode": "serialized_by_protein_target",
            "parallel_prep_allowed": True,
            "partner_track_id": str(suite_s.get("partner_track_id", export_s.get("partner_track_id", "DNDi_IPK"))).strip() or "DNDi_IPK",
            "render_suite_status": str(suite_s.get("status", "")).strip(),
            "export_status": str(export_s.get("status", "")).strip(),
            "required_artifact_count": len(rows),
            "launch_readiness": "ready_after_priority3_resolution",
            "execution_goal": "Open the next3 chain with Cruzain only after the priority3 final gate resolves, then keep PLpro blocked behind the live Cruzain outcome.",
            "blocking_rule": "Do not start SARS-CoV-2 PLpro until Cruzain reaches result-ready or explicit hold.",
            "next_target_on_success": "SARS-CoV-2 PLpro",
            "next_target_on_hold": "SARS-CoV-2 PLpro",
            "next_required_step": "Launch Cruzain first in the next3 serialized queue after the priority3 final review resolves, while PLpro and ALK2 remain blocked.",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the serialized launch packet for Cruzain.")
    parser.add_argument("--render-suite-json", default=DEFAULT_RENDER_SUITE_JSON)
    parser.add_argument("--partner-export-json", default=DEFAULT_EXPORT_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(load_json(args.render_suite_json), load_json(args.partner_export_json))
    write_artifact(DEFAULT_OUT_MD, "Cruzain Launch Packet", payload)


if __name__ == "__main__":
    main()
