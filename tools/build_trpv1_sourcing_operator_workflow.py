#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SOURCING_STATUS_JSON = "runs/trpv1_ion_channel_sourcing_status_current.json"
DEFAULT_VENDOR_QUOTE_PACKET_JSON = "runs/trpv1_ion_channel_vendor_quote_request_packet_current.json"
DEFAULT_VENDOR_MERGED_JSON = "runs/trpv1_ion_channel_vendor_web_check_merged_current.json"
DEFAULT_RESPONSE_INPUT_CSV = "runs/trpv1_ion_channel_vendor_quote_response_current.csv"
DEFAULT_RESPONSE_TEMPLATE_CSV = "runs/trpv1_ion_channel_vendor_quote_response_template_current.csv"
DEFAULT_OUT_JSON = "runs/trpv1_ion_channel_sourcing_operator_workflow_current.json"
DEFAULT_OUT_MD = "runs/trpv1_ion_channel_sourcing_operator_workflow_current.md"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str) -> dict[str, Any]:
    return json.loads(_resolve(path_like).read_text(encoding="utf-8"))


def build_payload(
    sourcing_payload: dict[str, Any],
    quote_packet_payload: dict[str, Any],
    merged_vendor_payload: dict[str, Any],
    response_input_csv: str,
    response_template_csv: str,
) -> dict[str, Any]:
    sourcing_summary = dict(sourcing_payload.get("summary", {}) or {})
    quote_summary = dict(quote_packet_payload.get("summary", {}) or {})
    merged_summary = dict(merged_vendor_payload.get("summary", {}) or {})
    quote_rows = list(quote_packet_payload.get("rows", []) or [])
    unresolved_rows = []
    merged_rows = {
        str(row.get("chembl_id", "")).strip(): dict(row)
        for row in (merged_vendor_payload.get("rows", []) or [])
        if str(row.get("chembl_id", "")).strip()
    }
    for row in quote_rows:
        chembl_id = str(row.get("chembl_id", "")).strip()
        merged_row = merged_rows.get(chembl_id, {})
        unresolved_rows.append(
            {
                "chembl_id": chembl_id,
                "normalized_name": str(row.get("normalized_name", "")).strip(),
                "current_vendor_status": str(merged_row.get("vendor_status", "")).strip(),
                "current_quote_response_received": bool(merged_row.get("quote_response_received", False)),
                "response_fields_to_fill": "catalog_id; purchasable; purity; pack_size_mg; lead_time_days; quote_currency; quote_amount; coa_available; shipping_region; notes",
                "promotion_rule": "Set `purchasable=yes` for immediate stock/availability. Leave it blank but fill quote fields for exact-product `quoted` status.",
            }
        )

    steps = [
        {
            "step": 1,
            "title": "Fill the vendor response CSV",
            "path": str(_resolve(response_input_csv)),
            "command": "",
            "expected_effect": "Populate exact product-level vendor responses for unresolved TRPV1 positives.",
        },
        {
            "step": 2,
            "title": "Refresh merged vendor evidence and downstream packets",
            "path": str(_resolve("tools/build_trpv1_vendor_quote_response_intake.py")),
            "command": "python3 tools/build_trpv1_vendor_quote_response_intake.py",
            "expected_effect": "Updates merged vendor evidence, quote-request packet, sourcing status, and CRO delivery packet in one run.",
        },
        {
            "step": 3,
            "title": "Inspect sourcing status",
            "path": str(_resolve(DEFAULT_SOURCING_STATUS_JSON)),
            "command": "",
            "expected_effect": "Check whether `vendor_confirmed_positive_count` increased and whether the blocker shifted from vendor confirmation to matched-negative replacement.",
        },
        {
            "step": 4,
            "title": "Inspect CRO delivery packet",
            "path": str(_resolve("runs/wetlab_cro_packets/trpv1_ion_channel_blind_cro_delivery_packet_current.json")),
            "command": "",
            "expected_effect": "Confirm `missing_slot_count` drops as positive slots become confirmed.",
        },
    ]

    transitions = [
        {
            "input_state": "response row left blank",
            "resulting_vendor_status": "quote_portal_unconfirmed",
            "counts_as_vendor_confirmed_positive": False,
            "follow_up_required": True,
        },
        {
            "input_state": "exact product quote filled, purchasable left blank or false",
            "resulting_vendor_status": "quoted",
            "counts_as_vendor_confirmed_positive": True,
            "follow_up_required": True,
        },
        {
            "input_state": "exact product response with purchasable=yes",
            "resulting_vendor_status": "purchasable",
            "counts_as_vendor_confirmed_positive": True,
            "follow_up_required": False,
        },
    ]

    summary = {
        "status": "trpv1_sourcing_operator_workflow_ready",
        "target_id": "TRPV1_ION_CHANNEL_BLIND",
        "response_input_csv": str(_resolve(response_input_csv)),
        "response_template_csv": str(_resolve(response_template_csv)),
        "quote_request_count": int(quote_summary.get("quote_request_count", 0) or 0),
        "vendor_confirmed_positive_count": int(sourcing_summary.get("vendor_confirmed_positive_count", 0) or 0),
        "matched_negative_slot_count_locked": int(sourcing_summary.get("matched_negative_slot_count_locked", 0) or 0),
        "control_panel_locked": bool(sourcing_summary.get("control_panel_locked", False)),
        "response_update_count": int(merged_summary.get("response_update_count", 0) or 0),
        "primary_blocker": str(sourcing_summary.get("blocking_reason", "")).strip() or str(quote_summary.get("primary_blocker", "")).strip(),
        "next_required_step": str(sourcing_summary.get("next_required_step", "")).strip() or str(quote_summary.get("next_required_step", "")).strip(),
    }
    return {
        "summary": summary,
        "steps": steps,
        "transitions": transitions,
        "unresolved_rows": unresolved_rows,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# TRPV1 Sourcing Operator Workflow",
        "",
        f"- status: `{summary['status']}`",
        f"- target_id: `{summary['target_id']}`",
        f"- response_input_csv: `{summary['response_input_csv']}`",
        f"- response_template_csv: `{summary['response_template_csv']}`",
        f"- vendor_confirmed_positive_count: `{summary['vendor_confirmed_positive_count']}`",
        f"- matched_negative_slot_count_locked: `{summary['matched_negative_slot_count_locked']}`",
        f"- control_panel_locked: `{summary['control_panel_locked']}`",
        f"- response_update_count: `{summary['response_update_count']}`",
        "",
        "## Current blocker",
        "",
        f"- {summary['primary_blocker']}",
        "",
        "## Operator steps",
        "",
    ]
    for step in payload["steps"]:
        lines.append(f"{step['step']}. {step['title']}")
        lines.append(f"   - path: `{step['path']}`")
        if step["command"]:
            lines.append(f"   - command: `{step['command']}`")
        lines.append(f"   - expected_effect: {step['expected_effect']}")
    lines.extend(
        [
            "",
            "## Status transition rules",
            "",
            "| input_state | resulting_vendor_status | counts_as_vendor_confirmed_positive | follow_up_required |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in payload["transitions"]:
        lines.append(
            f"| {row['input_state']} | `{row['resulting_vendor_status']}` | `{row['counts_as_vendor_confirmed_positive']}` | `{row['follow_up_required']}` |"
        )
    lines.extend(
        [
            "",
            "## Unresolved rows to fill now",
            "",
            "| chembl_id | current_vendor_status | current_quote_response_received | response_fields_to_fill |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in payload["unresolved_rows"]:
        lines.append(
            f"| `{row['chembl_id']}` | `{row['current_vendor_status']}` | `{row['current_quote_response_received']}` | `{row['response_fields_to_fill']}` |"
        )
    lines.extend(["", "## Next required step", "", f"- {summary['next_required_step']}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an operator-facing TRPV1 sourcing workflow artifact.")
    parser.add_argument("--sourcing-status-json", default=DEFAULT_SOURCING_STATUS_JSON)
    parser.add_argument("--vendor-quote-packet-json", default=DEFAULT_VENDOR_QUOTE_PACKET_JSON)
    parser.add_argument("--vendor-merged-json", default=DEFAULT_VENDOR_MERGED_JSON)
    parser.add_argument("--response-input-csv", default=DEFAULT_RESPONSE_INPUT_CSV)
    parser.add_argument("--response-template-csv", default=DEFAULT_RESPONSE_TEMPLATE_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.sourcing_status_json),
        _load_json(args.vendor_quote_packet_json),
        _load_json(args.vendor_merged_json),
        args.response_input_csv,
        args.response_template_csv,
    )
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
