#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_RENDER_SUITE_JSON = "runs/sarscov2_mpro_render_suite_current.json"
DEFAULT_EXPORT_JSON = "runs/sarscov2_mpro_readdi_export_current.json"
DEFAULT_VENDOR_COST_JSON = "runs/wetlab_mpro_vendor_cost_check_current.json"
DEFAULT_OUT_JSON = "runs/sarscov2_mpro_launch_packet_current.json"
DEFAULT_OUT_CSV = "runs/sarscov2_mpro_launch_packet_current.csv"
DEFAULT_OUT_MD = "runs/sarscov2_mpro_launch_packet_current.md"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def build_payload(render_suite: dict[str, Any], partner_export: dict[str, Any], vendor_cost: dict[str, Any]) -> dict[str, Any]:
    render_summary = dict(render_suite.get("summary", {}) or {})
    export_summary = dict(partner_export.get("summary", {}) or {})
    vendor_summary = dict(vendor_cost.get("summary", {}) or {})
    render_rows = [dict(row) for row in render_suite.get("rows", []) or []]

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
        for idx, row in enumerate(render_rows, start=1)
    ]
    rows.append(
        {
            "launch_step_rank": len(rows) + 1,
            "artifact_kind": "vendor_cost_sheet",
            "artifact_path": "runs/wetlab_mpro_vendor_cost_check_current.md",
            "artifact_status": str(vendor_summary.get("status", "")).strip(),
            "launch_role": "keep_controls_procurement_ready",
        }
    )

    summary = {
        "status": "sarscov2_mpro_launch_packet_ready",
        "target_id": "SARS-CoV-2 Mpro",
        "execution_rank": 1,
        "serialized_execution_policy": "run first in the priority-three queue",
        "gate_to_start": "none",
        "partner_track_id": str(render_summary.get("partner_track_id", "")).strip(),
        "partner_export_status": str(export_summary.get("status", "")).strip(),
        "vendor_cost_status": str(vendor_summary.get("status", "")).strip(),
        "render_artifact": "runs/sarscov2_mpro_render_suite_current.md",
        "partner_export_artifact": "runs/sarscov2_mpro_readdi_export_current.md",
        "prep_lane_policy": "parallel artifact prep is allowed while this target is executing; do not edit partner export content",
        "row_count": len(rows),
        "next_required_step": "Launch SARS-CoV-2 Mpro first, keep CA IX and T. cruzi PDE queued behind it, and treat the READDI export as frozen while the execution packet is being worked.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# SARS-CoV-2 Mpro Launch Packet",
        "",
        f"- status: `{s['status']}`",
        f"- target_id: `{s['target_id']}`",
        f"- execution_rank: `{s['execution_rank']}`",
        f"- serialized_execution_policy: `{s['serialized_execution_policy']}`",
        f"- gate_to_start: `{s['gate_to_start']}`",
        f"- partner_track_id: `{s['partner_track_id']}`",
        f"- partner_export_status: `{s['partner_export_status']}`",
        f"- vendor_cost_status: `{s['vendor_cost_status']}`",
        f"- render_artifact: `{s['render_artifact']}`",
        f"- partner_export_artifact: `{s['partner_export_artifact']}`",
        f"- prep_lane_policy: {s['prep_lane_policy']}",
        f"- row_count: `{s['row_count']}`",
        "",
        "| launch_step_rank | artifact_kind | artifact_path | artifact_status | launch_role |",
        "| ---: | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['launch_step_rank']} | `{row['artifact_kind']}` | `{row['artifact_path']}` | `{row['artifact_status']}` | `{row['launch_role']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the serialized launch packet for SARS-CoV-2 Mpro.")
    parser.add_argument("--render-suite-json", default=DEFAULT_RENDER_SUITE_JSON)
    parser.add_argument("--partner-export-json", default=DEFAULT_EXPORT_JSON)
    parser.add_argument("--vendor-cost-json", default=DEFAULT_VENDOR_COST_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.render_suite_json),
        _load_json(args.partner_export_json),
        _load_json(args.vendor_cost_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
