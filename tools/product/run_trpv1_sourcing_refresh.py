#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

import pandas as pd

from tools import build_trpv1_sourcing_status_sheet as sourcing_mod
from tools import build_trpv1_sendable_negative_panel as sendable_negative_mod
from tools import build_trpv1_vendor_quote_request_packet as quote_request_mod
from tools import build_trpv1_vendor_quote_response_intake as quote_response_mod
from tools import build_wetlab_cro_delivery_packets as cro_mod

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_OUT_JSON = "runs/trpv1_sourcing_refresh_current.json"
DEFAULT_OUT_MD = "runs/trpv1_sourcing_refresh_current.md"


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


def _quote_response_rows_with_data(path_like: str) -> int:
    frame = pd.read_csv(quote_response_mod._preferred_response_csv(path_like)).fillna("")
    count = 0
    for row in frame.to_dict(orient="records"):
        if any(str(value).strip() for key, value in row.items() if key != "chembl_id"):
            count += 1
    return count


def _preferred_vendor_json(base_vendor_json: str, merged_vendor_json: str) -> str:
    merged = _resolve(merged_vendor_json)
    return str(merged) if merged.exists() else str(_resolve(base_vendor_json))


def build_command_plan(
    *,
    base_vendor_json: str,
    quote_response_csv: str,
    merged_vendor_json: str,
) -> list[list[str]]:
    selected_vendor_json = str(_resolve(merged_vendor_json))
    return [
        [
            "python3",
            "tools/build_trpv1_sendable_negative_panel.py",
        ],
        [
            "python3",
            "tools/build_trpv1_vendor_quote_response_intake.py",
            "--base-vendor-web-check-json",
            str(_resolve(base_vendor_json)),
            "--quote-response-csv",
            str(_resolve(quote_response_csv)),
            "--out-json",
            str(_resolve(merged_vendor_json)),
            "--no-refresh-downstream",
        ],
        [
            "python3",
            "tools/build_trpv1_vendor_quote_request_packet.py",
            "--vendor-web-check-json",
            selected_vendor_json,
        ],
        [
            "python3",
            "tools/build_trpv1_sourcing_status_sheet.py",
            "--vendor-web-check-json",
            selected_vendor_json,
        ],
        [
            "python3",
            "tools/build_wetlab_cro_delivery_packets.py",
            "--trpv1-vendor-web-check-json",
            selected_vendor_json,
        ],
    ]


def build_payload(
    *,
    selected_vendor_json: str,
    quote_response_rows_with_data: int,
    merged_vendor_payload: dict[str, Any],
    quote_request_payload: dict[str, Any],
    sourcing_payload: dict[str, Any],
    cro_payload: dict[str, Any],
) -> dict[str, Any]:
    trpv1_cro_row = next(
        (row for row in (cro_payload.get("rows", []) or []) if str(row.get("target_id", "")).strip() == "TRPV1_ION_CHANNEL_BLIND"),
        {},
    )
    summary = {
        "status": "trpv1_sourcing_refresh_ready",
        "selected_vendor_json": selected_vendor_json,
        "quote_response_rows_with_data": quote_response_rows_with_data,
        "vendor_evidence_positive_count": int((merged_vendor_payload.get("summary", {}) or {}).get("vendor_evidence_positive_count", 0) or 0),
        "quote_request_count": int((quote_request_payload.get("summary", {}) or {}).get("quote_request_count", 0) or 0),
        "vendor_confirmed_positive_count": int((sourcing_payload.get("summary", {}) or {}).get("vendor_confirmed_positive_count", 0) or 0),
        "matched_negative_slot_count_locked": int((sourcing_payload.get("summary", {}) or {}).get("matched_negative_slot_count_locked", 0) or 0),
        "matched_negative_panel_mode": str((sourcing_payload.get("summary", {}) or {}).get("matched_negative_panel_mode", "")).strip(),
        "cro_ready_for_send": bool(trpv1_cro_row.get("ready_for_send", False)),
        "cro_missing_slot_count": int(trpv1_cro_row.get("missing_slot_count", 0) or 0),
        "next_required_step": str((sourcing_payload.get("summary", {}) or {}).get("next_required_step", "")).strip(),
    }
    rows = [
        {
            "step": "vendor_feasible_negative_panel",
            "artifact": str(_resolve(sendable_negative_mod.DEFAULT_OUT_JSON)),
            "status": str((_load_json(sendable_negative_mod.DEFAULT_OUT_JSON).get("summary", {}) or {}).get("status", "")).strip()
            if _resolve(sendable_negative_mod.DEFAULT_OUT_JSON).exists()
            else "",
        },
        {
            "step": "vendor_quote_response_intake",
            "artifact": str(_resolve(quote_response_mod.DEFAULT_OUT_JSON)),
            "status": str((merged_vendor_payload.get("summary", {}) or {}).get("status", "")).strip(),
        },
        {
            "step": "vendor_quote_request_packet",
            "artifact": str(_resolve(quote_request_mod.DEFAULT_OUT_JSON)),
            "status": str((quote_request_payload.get("summary", {}) or {}).get("status", "")).strip(),
        },
        {
            "step": "sourcing_status",
            "artifact": str(_resolve(sourcing_mod.DEFAULT_OUT_JSON)),
            "status": str((sourcing_payload.get("summary", {}) or {}).get("status", "")).strip(),
        },
        {
            "step": "cro_delivery_packet",
            "artifact": str(_resolve(cro_mod.DEFAULT_OUT_INDEX_JSON)),
            "status": str(trpv1_cro_row.get("packet_status", "")).strip(),
        },
    ]
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# TRPV1 Sourcing Refresh",
        "",
        f"- status: `{summary['status']}`",
        f"- selected_vendor_json: `{summary['selected_vendor_json']}`",
        f"- quote_response_rows_with_data: `{summary['quote_response_rows_with_data']}`",
        f"- vendor_evidence_positive_count: `{summary['vendor_evidence_positive_count']}`",
        f"- quote_request_count: `{summary['quote_request_count']}`",
        f"- vendor_confirmed_positive_count: `{summary['vendor_confirmed_positive_count']}`",
        f"- matched_negative_slot_count_locked: `{summary['matched_negative_slot_count_locked']}`",
        f"- cro_ready_for_send: `{summary['cro_ready_for_send']}`",
        f"- cro_missing_slot_count: `{summary['cro_missing_slot_count']}`",
        "",
        "## Step Artifacts",
        "",
        "| step | status | artifact |",
        "| --- | --- | --- |",
    ]
    for row in payload.get("rows", []) or []:
        lines.append(f"| `{row['step']}` | `{row['status']}` | `{row['artifact']}` |")
    lines.extend(["", "## Next Step", "", f"- {summary['next_required_step']}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh the TRPV1 sourcing workflow in one command.")
    parser.add_argument("--base-vendor-web-check-json", default=quote_response_mod.DEFAULT_BASE_VENDOR_WEB_CHECK_JSON)
    parser.add_argument("--quote-response-csv", default=quote_response_mod.DEFAULT_QUOTE_RESPONSE_CSV)
    parser.add_argument("--merged-vendor-json", default=quote_response_mod.DEFAULT_OUT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    command_plan = build_command_plan(
        base_vendor_json=args.base_vendor_web_check_json,
        quote_response_csv=args.quote_response_csv,
        merged_vendor_json=args.merged_vendor_json,
    )
    for command in command_plan:
        subprocess.run(command, check=True)

    selected_vendor_json = _preferred_vendor_json(args.base_vendor_web_check_json, args.merged_vendor_json)
    payload = build_payload(
        selected_vendor_json=selected_vendor_json,
        quote_response_rows_with_data=_quote_response_rows_with_data(args.quote_response_csv),
        merged_vendor_payload=_load_json(args.merged_vendor_json),
        quote_request_payload=_load_json(quote_request_mod.DEFAULT_OUT_JSON),
        sourcing_payload=_load_json(sourcing_mod.DEFAULT_OUT_JSON),
        cro_payload=_load_json(cro_mod.DEFAULT_OUT_INDEX_JSON),
    )
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
