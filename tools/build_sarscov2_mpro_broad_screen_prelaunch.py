#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import maybe_load_json, write_artifact

DEFAULT_INTAKE_JSON = "runs/sarscov2_mpro_broad_screen_shard_01_intake_packet_current.json"
DEFAULT_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_execution_queue_current.json"
DEFAULT_ANTITARGET_QUEUE_JSON = "runs/wetlab_broad_screen_antitarget_execution_queue_current.json"
DEFAULT_NEXT_TARGET_JSON = "runs/wetlab_broad_screen_next_target_extension_current.json"
DEFAULT_OUT_MD = "runs/sarscov2_mpro_broad_screen_prelaunch_current.md"


def build_payload(
    intake_payload: dict[str, Any] | None = None,
    execution_queue: dict[str, Any] | None = None,
    antitarget_execution_queue: dict[str, Any] | None = None,
    next_target_extension: dict[str, Any] | None = None,
) -> dict[str, Any]:
    intake_summary = dict((intake_payload or {}).get("summary", {}) or {})
    queue_rows = [
        dict(row)
        for row in ((execution_queue or {}).get("rows", []) or [])
        if str(row.get("target_id", "")).strip() == "SARS-CoV-2 Mpro"
    ]
    antitarget_rows = [
        dict(row)
        for row in ((antitarget_execution_queue or {}).get("rows", []) or [])
        if str(row.get("primary_target_id", "")).strip() == "SARS-CoV-2 Mpro"
    ]
    next_summary = dict((next_target_extension or {}).get("summary", {}) or {})
    first_primary = queue_rows[0] if queue_rows else {}
    first_antitarget = antitarget_rows[0] if antitarget_rows else {}
    return {
        "summary": {
            "status": "sarscov2_mpro_broad_screen_prelaunch_ready",
            "target_id": "SARS-CoV-2 Mpro",
            "primary_shard_id": str(first_primary.get("shard_id", "")).strip(),
            "primary_queue_status": str(first_primary.get("queue_status", "")).strip(),
            "anti_target_id": str(first_antitarget.get("anti_target_id", "")).strip(),
            "anti_target_queue_status": str(first_antitarget.get("queue_status", "")).strip(),
            "required_field_count": int(intake_summary.get("required_field_count", 0) or 0),
            "optional_field_count": int(intake_summary.get("optional_field_count", 0) or 0),
            "next_target_extension_ready": bool(str(next_summary.get("status", "")).strip() == "wetlab_broad_screen_next_target_extension_ready"),
            "next_required_step": "Keep primary and anti-target intake packets ready so Mpro can start immediately after CA IX clears the serialized broad-screen lane.",
        },
        "structured": {
            "intake_packet_artifact": "runs/sarscov2_mpro_broad_screen_shard_01_intake_packet_current.md",
            "next_target_extension_artifact": "runs/wetlab_broad_screen_next_target_extension_current.md",
            "execution_queue_artifact": "runs/wetlab_broad_screen_execution_queue_current.md",
            "antitarget_execution_queue_artifact": "runs/wetlab_broad_screen_antitarget_execution_queue_current.md",
        },
        "rows": [
            {
                "primary_shard_id": str(first_primary.get("shard_id", "")).strip(),
                "primary_queue_status": str(first_primary.get("queue_status", "")).strip(),
                "anti_target_id": str(first_antitarget.get("anti_target_id", "")).strip(),
                "anti_target_queue_status": str(first_antitarget.get("queue_status", "")).strip(),
                "existing_target_rows_in_source": int(intake_summary.get("existing_target_rows_in_source", 0) or 0),
            }
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a prelaunch packet for broad-screen SARS-CoV-2 Mpro entry.")
    parser.add_argument("--intake-json", default=DEFAULT_INTAKE_JSON)
    parser.add_argument("--execution-queue-json", default=DEFAULT_EXECUTION_QUEUE_JSON)
    parser.add_argument("--antitarget-execution-queue-json", default=DEFAULT_ANTITARGET_QUEUE_JSON)
    parser.add_argument("--next-target-json", default=DEFAULT_NEXT_TARGET_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    write_artifact(
        args.out_md,
        "SARS-CoV-2 Mpro Broad Screen Prelaunch",
        build_payload(
            intake_payload=maybe_load_json(args.intake_json),
            execution_queue=maybe_load_json(args.execution_queue_json),
            antitarget_execution_queue=maybe_load_json(args.antitarget_execution_queue_json),
            next_target_extension=maybe_load_json(args.next_target_json),
        ),
    )
