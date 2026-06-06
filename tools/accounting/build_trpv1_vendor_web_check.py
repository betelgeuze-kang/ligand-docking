#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_OUT_JSON = "runs/trpv1_ion_channel_vendor_web_check_current.json"
DEFAULT_OUT_MD = "runs/trpv1_ion_channel_vendor_web_check_current.md"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def build_payload() -> dict[str, Any]:
    rows = [
        {
            "chembl_id": "CHEMBL2385220",
            "vendor_status": "quote_portal_unconfirmed",
            "vendor_purchase_confirmed": False,
            "vendor_evidence_source": "PubChem chemical vendors check + vendor portal search",
            "vendor_evidence_url": "https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/71698721/JSON/?heading=Chemical-Vendors",
            "vendor_evidence_note": "PubChem Chemical Vendors returned no data for CID 71698721. An unauthenticated TargetMol search page exists for the exact CHEMBL identifier, but no exact purchasable product card or catalog listing was confirmed from the public session.",
            "vendor_purchase_url": "",
            "vendor_web_check_date": "2026-04-13",
            "quote_portal_source": "TargetMol search portal",
            "quote_portal_status": "portal_query_page_visible",
            "quote_portal_url": "https://www.targetmol.com/search?keyword=CHEMBL2385220",
            "quote_portal_note": "Search portal page is reachable, but this is still below vendor-confirmed or quoted status. Manual login or direct quote submission is still required.",
            "manual_follow_up_required": True,
        },
        {
            "chembl_id": "CHEMBL3427109",
            "vendor_status": "catalog_indexed_pubchem",
            "vendor_purchase_confirmed": True,
            "vendor_evidence_source": "PubChem chemical vendors check",
            "vendor_evidence_url": "https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/25102898/JSON/?heading=Chemical-Vendors",
            "vendor_evidence_note": "PubChem CID 25102898 exposes a Chemical Vendors section, so at least one catalog vendor is indexed for this compound.",
            "vendor_purchase_url": "https://pubchem.ncbi.nlm.nih.gov/compound/25102898#section=Chemical-Vendors",
            "vendor_web_check_date": "2026-04-13",
            "quote_portal_source": "",
            "quote_portal_status": "",
            "quote_portal_url": "",
            "quote_portal_note": "",
            "manual_follow_up_required": False,
        },
        {
            "chembl_id": "CHEMBL2177440",
            "vendor_status": "quote_portal_unconfirmed",
            "vendor_purchase_confirmed": False,
            "vendor_evidence_source": "PubChem chemical vendors check + vendor portal search",
            "vendor_evidence_url": "https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/16223644/JSON/?heading=Chemical-Vendors",
            "vendor_evidence_note": "PubChem Chemical Vendors returned no data for CID 16223644. An unauthenticated TargetMol search page exists for the exact CHEMBL identifier, but no exact purchasable product card or catalog listing was confirmed from the public session.",
            "vendor_purchase_url": "",
            "vendor_web_check_date": "2026-04-13",
            "quote_portal_source": "TargetMol search portal",
            "quote_portal_status": "portal_query_page_visible",
            "quote_portal_url": "https://www.targetmol.com/search?keyword=CHEMBL2177440",
            "quote_portal_note": "Search portal page is reachable, but this is still below vendor-confirmed or quoted status. Manual login or direct quote submission is still required.",
            "manual_follow_up_required": True,
        },
    ]
    summary = {
        "status": "trpv1_vendor_web_check_ready",
        "target_id": "TRPV1_ION_CHANNEL_BLIND",
        "checked_on": "2026-04-13",
        "checked_positive_count": 3,
        "vendor_evidence_positive_count": sum(1 for row in rows if row["vendor_purchase_confirmed"]),
        "quote_portal_candidate_count": sum(1 for row in rows if row["quote_portal_status"]),
        "note": "Only CHEMBL3427109 is vendor-confirmed from public catalog evidence. CHEMBL2385220 and CHEMBL2177440 have portal-query evidence but still require manual login or direct quote confirmation.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# TRPV1 Vendor Web Check",
        "",
        f"- status: `{summary['status']}`",
        f"- target_id: `{summary['target_id']}`",
        f"- checked_on: `{summary['checked_on']}`",
        f"- checked_positive_count: `{summary['checked_positive_count']}`",
        f"- vendor_evidence_positive_count: `{summary['vendor_evidence_positive_count']}`",
        f"- quote_portal_candidate_count: `{summary['quote_portal_candidate_count']}`",
        "",
        f"- {summary['note']}",
        "",
        "| chembl_id | vendor_status | vendor_purchase_confirmed | quote_portal_status | vendor_evidence_url | quote_portal_url |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['chembl_id']}` | `{row['vendor_status']}` | `{row['vendor_purchase_confirmed']}` | `{row['quote_portal_status']}` | {row['vendor_evidence_url']} | {row['quote_portal_url']} |"
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write the curated TRPV1 vendor web-check artifact.")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload()
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
