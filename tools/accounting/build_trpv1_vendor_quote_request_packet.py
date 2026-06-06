#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_VENDOR_WEB_CHECK_JSON = "runs/trpv1_ion_channel_vendor_web_check_current.json"
DEFAULT_VENDOR_WEB_CHECK_MERGED_JSON = "runs/trpv1_ion_channel_vendor_web_check_merged_current.json"
DEFAULT_SOURCING_STATUS_JSON = "runs/trpv1_ion_channel_sourcing_status_current.json"
DEFAULT_SOURCING_REQUEST_CSV = "docs/wetlab_packets/trpv1_ion_channel_sourcing_request.csv"
DEFAULT_OUT_JSON = "runs/trpv1_ion_channel_vendor_quote_request_packet_current.json"
DEFAULT_OUT_CSV = "runs/trpv1_ion_channel_vendor_quote_request_packet_current.csv"
DEFAULT_OUT_MD = "runs/trpv1_ion_channel_vendor_quote_request_packet_current.md"
DEFAULT_RESPONSE_TEMPLATE_CSV = "runs/trpv1_ion_channel_vendor_quote_response_template_current.csv"
DEFAULT_RESPONSE_INPUT_CSV = "runs/trpv1_ion_channel_vendor_quote_response_current.csv"


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


def _preferred_vendor_json(path_like: str) -> str:
    if path_like == DEFAULT_VENDOR_WEB_CHECK_JSON:
        merged = _resolve(DEFAULT_VENDOR_WEB_CHECK_MERGED_JSON)
        if merged.exists():
            return str(merged)
    return path_like


def build_payload(
    vendor_payload: dict[str, Any],
    sourcing_payload: dict[str, Any],
    sourcing_request_frame: pd.DataFrame | None = None,
) -> dict[str, Any]:
    sourcing_rows = {
        str(row.get("chembl_id", "")).strip(): dict(row)
        for row in (sourcing_payload.get("rows", []) or [])
        if str(row.get("chembl_id", "")).strip()
    }
    request_frame = sourcing_request_frame if sourcing_request_frame is not None else pd.DataFrame()
    sourcing_request_rows = {
        str(row.get("chembl_id", "")).strip(): dict(row)
        for row in (request_frame.fillna("").to_dict(orient="records"))
        if str(row.get("chembl_id", "")).strip()
    }
    quote_rows: list[dict[str, Any]] = []
    for vendor_row in vendor_payload.get("rows", []) or []:
        chembl_id = str(vendor_row.get("chembl_id", "")).strip()
        if not chembl_id:
            continue
        if bool(vendor_row.get("vendor_purchase_confirmed", False)):
            continue
        if str(vendor_row.get("quote_portal_status", "")).strip() != "portal_query_page_visible":
            continue
        source_row = sourcing_rows.get(chembl_id, {})
        request_row = sourcing_request_rows.get(chembl_id, {})
        quote_rows.append(
            {
                "request_rank": len(quote_rows) + 1,
                "target_id": "TRPV1_ION_CHANNEL_BLIND",
                "chembl_id": chembl_id,
                "normalized_name": str(source_row.get("normalized_name", "") or request_row.get("normalized_name", "")).strip(),
                "inchi_key": str(source_row.get("inchi_key", "") or request_row.get("inchi_key", "")).strip(),
                "smiles": str(source_row.get("smiles", "") or request_row.get("smiles", "")).strip(),
                "standard_type": str(source_row.get("standard_type", "") or request_row.get("standard_type", "")).strip(),
                "pchembl": source_row.get("pchembl", request_row.get("pchembl", "")),
                "reference_binding_kcal_mol": source_row.get("reference_binding_kcal_mol", request_row.get("reference_binding_kcal_mol", "")),
                "binding_score_composite_v5": source_row.get("binding_score_composite_v5", request_row.get("binding_score_composite_v5", "")),
                "quote_portal_source": str(vendor_row.get("quote_portal_source", "")).strip(),
                "quote_portal_url": str(vendor_row.get("quote_portal_url", "")).strip(),
                "quote_request_goal": "Confirm exact catalog availability, purity, lead time, quote, and pack size for TRPV1 pilot sourcing.",
                "preferred_pack_size_mg": "5-10",
                "preferred_purity": ">=95%",
                "required_vendor_response_fields": "catalog_id; purchasable; purity; pack_size_mg; lead_time_days; quote_currency; quote_amount; coa_available; shipping_region",
                "note": str(vendor_row.get("quote_portal_note", "")).strip(),
            }
        )

    summary = {
        "status": "trpv1_vendor_quote_request_packet_ready",
        "target_id": "TRPV1_ION_CHANNEL_BLIND",
        "quote_request_count": len(quote_rows),
        "manual_follow_up_required": len(quote_rows) > 0,
        "primary_blocker": "Two TRPV1 positives remain below vendor-confirmed status and need manual quote confirmation.",
        "next_required_step": "Submit the quote requests for CHEMBL2385220 and CHEMBL2177440, then promote either row to `quoted` or `purchasable` only after a vendor responds with an exact product-level confirmation.",
    }
    structured = {
        "submission_rule": "Portal search visibility alone is insufficient. Promote only after an exact product-level vendor response or authenticated quote confirmation is in hand.",
        "response_fields": "catalog_id; purchasable; purity; pack_size_mg; lead_time_days; quote_currency; quote_amount; coa_available; shipping_region",
    }
    email_subject = "TRPV1 pilot compound quote request: CHEMBL2385220 / CHEMBL2177440"
    compound_lines = [
        f"- {row['chembl_id']} | {row['normalized_name']} | InChIKey {row['inchi_key']}"
        for row in quote_rows
    ]
    email_body = "\n".join(
        [
            "Hello,",
            "",
            "We are requesting a sourcing quote for the following TRPV1 pilot compounds:",
            *compound_lines,
            "",
            "Please confirm for each compound:",
            "- exact catalog or product identifier",
            "- whether the compound is currently purchasable",
            "- purity specification",
            "- smallest available pack size in mg",
            "- lead time",
            "- quote amount and currency",
            "- whether a COA is available",
            "",
            "Target use case: small ion-channel pilot assay panel.",
            "",
            "Thank you.",
        ]
    )
    return {
        "summary": summary,
        "structured": structured,
        "rows": quote_rows,
        "response_template_fields": [
            "chembl_id",
            "catalog_id",
            "purchasable",
            "purity",
            "pack_size_mg",
            "lead_time_days",
            "quote_currency",
            "quote_amount",
            "coa_available",
            "shipping_region",
            "notes",
        ],
        "email_template": {
            "subject": email_subject,
            "body": email_body,
        },
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    email = payload["email_template"]
    lines = [
        "# TRPV1 Vendor Quote Request Packet",
        "",
        f"- status: `{summary['status']}`",
        f"- target_id: `{summary['target_id']}`",
        f"- quote_request_count: `{summary['quote_request_count']}`",
        f"- manual_follow_up_required: `{summary['manual_follow_up_required']}`",
        "",
        f"- {summary['primary_blocker']}",
        "",
        "## Quote Rows",
        "",
        "| request_rank | chembl_id | quote_portal_source | quote_portal_url | preferred_pack_size_mg | preferred_purity |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['request_rank']}` | `{row['chembl_id']}` | `{row['quote_portal_source']}` | {row['quote_portal_url']} | `{row['preferred_pack_size_mg']}` | `{row['preferred_purity']}` |"
        )
    lines.extend(
        [
            "",
            "## Email Subject",
            "",
            f"`{email['subject']}`",
            "",
            "## Response Template Fields",
            "",
            "- chembl_id",
            "- catalog_id",
            "- purchasable",
            "- purity",
            "- pack_size_mg",
            "- lead_time_days",
            "- quote_currency",
            "- quote_amount",
            "- coa_available",
            "- shipping_region",
            "- notes",
            "",
            "## Email Body",
            "",
            "```text",
            email["body"],
            "```",
            "",
            "## Next Step",
            "",
            f"- {summary['next_required_step']}",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a manual vendor quote-request packet for unresolved TRPV1 positives.")
    parser.add_argument("--vendor-web-check-json", default=DEFAULT_VENDOR_WEB_CHECK_JSON)
    parser.add_argument("--sourcing-status-json", default=DEFAULT_SOURCING_STATUS_JSON)
    parser.add_argument("--sourcing-request-csv", default=DEFAULT_SOURCING_REQUEST_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--response-template-csv", default=DEFAULT_RESPONSE_TEMPLATE_CSV)
    parser.add_argument("--response-input-csv", default=DEFAULT_RESPONSE_INPUT_CSV)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(_preferred_vendor_json(args.vendor_web_check_json)),
        _load_json(args.sourcing_status_json),
        pd.read_csv(_resolve(args.sourcing_request_csv)),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_template_csv = _resolve(args.response_template_csv)
    out_input_csv = _resolve(args.response_input_csv)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    response_rows = [
        {
            "chembl_id": row["chembl_id"],
            "catalog_id": "",
            "purchasable": "",
            "purity": "",
            "pack_size_mg": "",
            "lead_time_days": "",
            "quote_currency": "",
            "quote_amount": "",
            "coa_available": "",
            "shipping_region": "",
            "notes": "",
        }
        for row in payload["rows"]
    ]
    write_csv_rows(out_template_csv, response_rows)
    if not out_input_csv.exists():
        write_csv_rows(out_input_csv, response_rows)
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
