#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_INPUT_CSV = "runs/trpv1_ion_channel_vendor_feasible_negative_panel_current.csv"
DEFAULT_OUT_JSON = "runs/trpv1_ion_channel_vendor_feasible_negative_panel_resolved_current.json"
DEFAULT_OUT_CSV = "runs/trpv1_ion_channel_vendor_feasible_negative_panel_resolved_current.csv"
DEFAULT_OUT_MD = "runs/trpv1_ion_channel_vendor_feasible_negative_panel_resolved_current.md"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value).strip()


def _truthy(value: Any) -> bool:
    return _stringify(value).lower() in {"1", "true", "yes", "y", "quoted", "purchasable", "catalog_live"}


def _ensure_input_template(path: Path) -> None:
    if path.exists():
        return
    rows = [
        {
            "panel_slot": f"negative_{idx}",
            "compound_id": "",
            "compound_name": "",
            "chembl_id": "",
            "vendor_name": "",
            "catalog_id": "",
            "vendor_status": "",
            "purchasable": "",
            "purity": "",
            "pack_size_mg": "",
            "lead_time_days": "",
            "quote_currency": "",
            "quote_amount": "",
            "coa_available": "",
            "shipping_region": "",
            "smiles": "",
            "scaffold": "",
            "molecular_weight": "",
            "logp": "",
            "h_donors": "",
            "h_acceptors": "",
            "rot_bonds": "",
            "selection_rule": "",
            "note": "",
        }
        for idx in range(1, 4)
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    write_csv_rows(path, rows)


def build_payload(input_frame: pd.DataFrame) -> dict[str, Any]:
    ready_count = 0
    rows: list[dict[str, Any]] = []
    for _, raw in input_frame.fillna("").iterrows():
        panel_slot = _stringify(raw.get("panel_slot", ""))
        if not panel_slot:
            continue
        vendor_status = _stringify(raw.get("vendor_status", "")).lower()
        vendor_confirmed = _truthy(raw.get("purchasable", "")) or vendor_status in {
            "quoted",
            "purchasable",
            "catalog_live",
            "catalog_indexed_pubchem",
        }
        external_send_ready = bool(
            _stringify(raw.get("compound_id", ""))
            and _stringify(raw.get("vendor_name", ""))
            and _stringify(raw.get("catalog_id", ""))
            and vendor_confirmed
        )
        if external_send_ready:
            ready_count += 1
        rows.append(
            {
                "target_id": "TRPV1_ION_CHANNEL_BLIND",
                "panel_slot": panel_slot,
                "compound_id": _stringify(raw.get("compound_id", "")),
                "compound_name": _stringify(raw.get("compound_name", "")),
                "chembl_id": _stringify(raw.get("chembl_id", "")),
                "expected_class": "matched_negative_control_vendor_feasible",
                "expected_direction": "lower_activity_than_positive_panel",
                "negative_control_locked": external_send_ready,
                "external_send_ready": external_send_ready,
                "negative_control_kind": "vendor_feasible_negative_control",
                "vendor_name": _stringify(raw.get("vendor_name", "")),
                "catalog_id": _stringify(raw.get("catalog_id", "")),
                "vendor_status": vendor_status,
                "purchasable": _truthy(raw.get("purchasable", "")),
                "purity": _stringify(raw.get("purity", "")),
                "pack_size_mg": _stringify(raw.get("pack_size_mg", "")),
                "lead_time_days": _stringify(raw.get("lead_time_days", "")),
                "quote_currency": _stringify(raw.get("quote_currency", "")),
                "quote_amount": _stringify(raw.get("quote_amount", "")),
                "coa_available": _stringify(raw.get("coa_available", "")),
                "shipping_region": _stringify(raw.get("shipping_region", "")),
                "smiles": _stringify(raw.get("smiles", "")),
                "scaffold": _stringify(raw.get("scaffold", "")),
                "molecular_weight": _stringify(raw.get("molecular_weight", "")),
                "logp": _stringify(raw.get("logp", "")),
                "h_donors": _stringify(raw.get("h_donors", "")),
                "h_acceptors": _stringify(raw.get("h_acceptors", "")),
                "rot_bonds": _stringify(raw.get("rot_bonds", "")),
                "selection_rule": _stringify(raw.get("selection_rule", "")),
                "note": _stringify(raw.get("note", "")),
            }
        )

    summary = {
        "status": "trpv1_vendor_feasible_negative_panel_ready",
        "target_id": "TRPV1_ION_CHANNEL_BLIND",
        "selected_negative_count": len(rows),
        "matched_negative_slot_count_required": 3,
        "matched_negative_slot_count_locked": ready_count,
        "matched_negative_panel_locked": ready_count == 3,
        "matched_negative_panel_sendable": ready_count == 3,
        "panel_kind": "vendor_feasible_negative_control_panel" if ready_count == 3 else "vendor_feasible_negative_control_template_pending",
        "next_required_step": (
            "Vendor-feasible matched negatives are locked and can be used for external CRO send."
            if ready_count == 3
            else "Fill three vendor-feasible matched negatives with vendor name, catalog_id, and quoted/purchasable confirmation."
        ),
    }
    structured = {
        "lock_rule": "A row counts as externally sendable only when compound_id, vendor_name, catalog_id, and quoted/purchasable status are all present.",
        "template_csv": str(_resolve(DEFAULT_INPUT_CSV)),
    }
    return {"summary": summary, "structured": structured, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# TRPV1 Vendor-Feasible Negative Panel",
        "",
        f"- status: `{summary['status']}`",
        f"- target_id: `{summary['target_id']}`",
        f"- selected_negative_count: `{summary['selected_negative_count']}`",
        f"- matched_negative_slot_count_locked: `{summary['matched_negative_slot_count_locked']}`",
        f"- matched_negative_panel_sendable: `{summary['matched_negative_panel_sendable']}`",
        "",
        "| panel_slot | compound_id | vendor_name | catalog_id | vendor_status | external_send_ready |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload.get("rows", []) or []:
        lines.append(
            f"| `{row['panel_slot']}` | `{row['compound_id']}` | `{row['vendor_name']}` | `{row['catalog_id']}` | `{row['vendor_status']}` | `{row['external_send_ready']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {summary['next_required_step']}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve the TRPV1 vendor-feasible matched negative panel from an operator-maintained CSV.")
    parser.add_argument("--input-csv", default=DEFAULT_INPUT_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_csv = _resolve(args.input_csv)
    _ensure_input_template(input_csv)
    payload = build_payload(pd.read_csv(input_csv))
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload.get("rows", []) or [])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
