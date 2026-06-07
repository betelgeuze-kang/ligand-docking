#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPURPOSING_FILL_MAP_JSON = "runs/wetlab_priority3_repurposing_fill_map_current.json"
DEFAULT_OUT_JSON = "runs/wetlab_mpro_vendor_cost_check_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_mpro_vendor_cost_check_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_mpro_vendor_cost_check_current.md"

VENDOR_SPECS: dict[str, dict[str, str | bool]] = {
    "Nirmatrelvir": {
        "vendor_name": "MedKoo Biosciences",
        "vendor_url": "https://www.medkoo.com/products/46293",
        "catalog_number": "MedKoo Cat# 555985",
        "listed_pack_size": "25mg",
        "listed_price": "150.00",
        "listed_currency": "USD",
        "availability_status": "Ready to ship",
        "estimated_lead_time_days": "not_listed",
        "procurement_risk": "medium",
        "procurement_note": "Good benchmark control, but it should stay benchmark-only in the outbound packet because pricing is no longer the cheapest route for a low-friction first screen.",
        "source_anchor": "MedKoo Nirmatrelvir product page checked 2026-03-29",
        "source_url": "https://www.medkoo.com/products/46293",
    },
    "Boceprevir": {
        "vendor_name": "MedKoo Biosciences",
        "vendor_url": "https://www.medkoo.com/products/4604",
        "catalog_number": "MedKoo Cat# 300235",
        "listed_pack_size": "50mg",
        "listed_price": "150.00",
        "listed_currency": "USD",
        "availability_status": "Ready to ship",
        "estimated_lead_time_days": "not_listed",
        "procurement_risk": "medium",
        "procurement_note": "Still practical for a research packet, but the minimum listed pack is bigger than a tiny pilot and should be called out before outbound routing.",
        "source_anchor": "MedKoo Boceprevir product page checked 2026-03-29",
        "source_url": "https://www.medkoo.com/products/4604",
    },
    "Telaprevir": {
        "vendor_name": "MedKoo Biosciences",
        "vendor_url": "https://www.medkoo.com/products/6532",
        "catalog_number": "MedKoo Cat# 315233",
        "listed_pack_size": "25mg",
        "listed_price": "150.00",
        "listed_currency": "USD",
        "availability_status": "Ready to ship",
        "estimated_lead_time_days": "not_listed",
        "procurement_risk": "medium_high",
        "procurement_note": "Procurement looks straightforward for research use, but the older discontinued clinical scaffold should be framed as a follow-on comparator, not a headline cheap lead.",
        "source_anchor": "MedKoo Telaprevir product page checked 2026-03-29",
        "source_url": "https://www.medkoo.com/products/6532",
    },
}


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _maybe_load_json(path_like: str) -> dict[str, Any] | None:
    path = _resolve(path_like)
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def build_payload(repurposing_fill_map: dict[str, Any] | None = None) -> dict[str, Any]:
    rows = []
    fill_rows = sorted(
        [
            dict(row)
            for row in (repurposing_fill_map or {}).get("rows", []) or []
            if str(row.get("target_id", "")).strip() == "SARS-CoV-2 Mpro"
        ],
        key=lambda item: int(item.get("slot_rank", 0) or 0),
    )
    for fill_row in fill_rows:
        compound_name = str(fill_row.get("compound_name", "")).strip()
        vendor_spec = dict(VENDOR_SPECS.get(compound_name, {}))
        out = {
            "slot_rank": fill_row["slot_rank"],
            "compound_name": compound_name,
            "procurement_action": fill_row.get("first_contact_use_mode", ""),
            "vendor_check_required": bool(fill_row.get("vendor_check_required", False)),
            "cost_check_required": bool(fill_row.get("cost_check_required", False)),
            "source_priority_fill_anchor": str(fill_row.get("source_anchor", "")).strip(),
            "source_priority_fill_url": str(fill_row.get("source_url", "")).strip(),
        }
        out.update(vendor_spec)
        out["check_status"] = "verified_current_vendor_page"
        out["row_status"] = "checked"
        rows.append(out)
    ready_count = sum(1 for row in rows if row["procurement_action"] in {"benchmark_only", "proceed_now"})
    summary = {
        "status": "wetlab_mpro_vendor_cost_check_ready",
        "target_id": "SARS-CoV-2 Mpro",
        "source_priority3_repurposing_fill_map_artifact": "runs/wetlab_priority3_repurposing_fill_map_current.md",
        "row_count": len(rows),
        "vendor_check_required_count": sum(1 for row in rows if row["vendor_check_required"]),
        "cost_check_required_count": sum(1 for row in rows if row["cost_check_required"]),
        "ready_for_first_contact_count": ready_count,
        "next_required_step": "Use Boceprevir and Telaprevir as proceed-now repurposing seeds with explicit procurement notes, keep Nirmatrelvir as benchmark-only, then route the READDI_Korea first-contact packet.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Wet-Lab Mpro Vendor/Cost Check",
        "",
        f"- status: `{s['status']}`",
        f"- target_id: `{s['target_id']}`",
        f"- source_priority3_repurposing_fill_map_artifact: `{s['source_priority3_repurposing_fill_map_artifact']}`",
        f"- row_count: `{s['row_count']}`",
        f"- vendor_check_required_count: `{s['vendor_check_required_count']}`",
        f"- cost_check_required_count: `{s['cost_check_required_count']}`",
        f"- ready_for_first_contact_count: `{s['ready_for_first_contact_count']}`",
        "",
        "| slot_rank | compound_name | procurement_action | vendor_name | listed_pack_size | listed_price | availability_status | procurement_risk |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['slot_rank']}` | `{row['compound_name']}` | `{row['procurement_action']}` | `{row['vendor_name']}` | `{row['listed_pack_size']}` | `{row['listed_currency']} {row['listed_price']}` | `{row['availability_status']}` | `{row['procurement_risk']}` |"
        )
    lines.extend(["", "## Procurement Notes", ""])
    for row in payload["rows"]:
        lines.extend(
            [
                f"### {row['slot_rank']}. `{row['compound_name']}`",
                "",
                f"- vendor_name: `{row['vendor_name']}`",
                f"- vendor_url: {row['vendor_url']}",
                f"- catalog_number: `{row['catalog_number']}`",
                f"- listed_pack_size: `{row['listed_pack_size']}`",
                f"- listed_price: `{row['listed_currency']} {row['listed_price']}`",
                f"- availability_status: `{row['availability_status']}`",
                f"- procurement_note: {row['procurement_note']}",
                f"- source_anchor: `{row['source_anchor']}`",
                "",
            ]
        )
    lines.extend(["## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Mpro vendor/cost gate for the three repurposing compounds.")
    parser.add_argument("--repurposing-fill-map-json", default=DEFAULT_REPURPOSING_FILL_MAP_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(_maybe_load_json(args.repurposing_fill_map_json))
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
