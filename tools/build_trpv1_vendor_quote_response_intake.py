#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_BASE_VENDOR_WEB_CHECK_JSON = "runs/trpv1_ion_channel_vendor_web_check_current.json"
DEFAULT_QUOTE_RESPONSE_CSV = "runs/trpv1_ion_channel_vendor_quote_response_current.csv"
DEFAULT_QUOTE_RESPONSE_TEMPLATE_CSV = "runs/trpv1_ion_channel_vendor_quote_response_template_current.csv"
DEFAULT_OUT_JSON = "runs/trpv1_ion_channel_vendor_web_check_merged_current.json"
DEFAULT_OUT_CSV = "runs/trpv1_ion_channel_vendor_web_check_merged_current.csv"
DEFAULT_OUT_MD = "runs/trpv1_ion_channel_vendor_quote_response_intake_current.md"
DEFAULT_VALIDATION_JSON = "runs/trpv1_ion_channel_vendor_quote_response_validation_current.json"
DEFAULT_VALIDATION_MD = "runs/trpv1_ion_channel_vendor_quote_response_validation_current.md"


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


def _preferred_response_csv(path_like: str) -> Path:
    resolved = _resolve(path_like)
    if resolved.exists():
        return resolved
    default_resolved = _resolve(DEFAULT_QUOTE_RESPONSE_CSV)
    if resolved == default_resolved or resolved.name == default_resolved.name:
        template = _resolve(DEFAULT_QUOTE_RESPONSE_TEMPLATE_CSV)
        if template.exists():
            return template
    return resolved


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value).strip()


def _truthy(value: Any) -> bool:
    normalized = _normalize_text(value)
    return normalized in {"1", "true", "yes", "y", "purchasable", "available", "in_stock"}


def _has_response_data(response_row: dict[str, Any]) -> bool:
    for key, value in response_row.items():
        if key == "chembl_id":
            continue
        if _stringify(value):
            return True
    return False


def _has_strong_quote_evidence(response_row: dict[str, Any]) -> bool:
    strong_fields = (
        "catalog_id",
        "quote_amount",
        "lead_time_days",
        "purity",
    )
    return any(_stringify(response_row.get(field, "")) for field in strong_fields)


def _has_purchasable_evidence(response_row: dict[str, Any]) -> bool:
    return _truthy(response_row.get("purchasable", "")) and any(
        _stringify(response_row.get(field, "")) for field in ("catalog_id", "quote_amount")
    )


def build_validation_payload(base_vendor_payload: dict[str, Any], response_frame: pd.DataFrame) -> dict[str, Any]:
    base_ids = {
        _normalize_text(row.get("chembl_id", "")): str(row.get("chembl_id", "")).strip()
        for row in (base_vendor_payload.get("rows", []) or [])
        if _normalize_text(row.get("chembl_id", ""))
    }
    response_records = response_frame.fillna("").to_dict(orient="records")
    seen_counts: dict[str, int] = {}
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    warnings: list[str] = []

    for idx, row in enumerate(response_records, start=1):
        chembl_key = _normalize_text(row.get("chembl_id", ""))
        if not chembl_key:
            continue
        seen_counts[chembl_key] = seen_counts.get(chembl_key, 0) + 1
        has_data = _has_response_data(row)
        strong_evidence = _has_strong_quote_evidence(row)
        purchasable_evidence = _has_purchasable_evidence(row)
        issue_codes: list[str] = []
        if chembl_key not in base_ids:
            issue_codes.append("unknown_chembl_id")
            errors.append(f"Unknown chembl_id in quote response CSV: {row.get('chembl_id', '')}")
        if has_data and not strong_evidence:
            issue_codes.append("weak_quote_evidence")
            warnings.append(f"Weak quote evidence for {row.get('chembl_id', '')}; no promotion will occur.")
        rows.append(
            {
                "row_index": idx,
                "chembl_id": str(row.get("chembl_id", "")).strip(),
                "response_row_has_data": has_data,
                "strong_quote_evidence": strong_evidence,
                "purchasable_evidence": purchasable_evidence,
                "issue_codes": "; ".join(issue_codes),
            }
        )

    for chembl_key, count in seen_counts.items():
        if count > 1:
            errors.append(f"Duplicate chembl_id in quote response CSV: {base_ids.get(chembl_key, chembl_key)}")
            for row in rows:
                if _normalize_text(row.get("chembl_id", "")) == chembl_key:
                    row["issue_codes"] = "; ".join(
                        sorted(
                            {code for code in [part.strip() for part in str(row.get("issue_codes", "")).split(";")] if code}
                            | {"duplicate_chembl_id"}
                        )
                    )

    summary = {
        "status": "trpv1_vendor_quote_response_validation_ready" if not errors else "trpv1_vendor_quote_response_validation_failed",
        "row_count": len(rows),
        "error_count": len(errors),
        "warning_count": len(warnings),
    }
    return {"summary": summary, "rows": rows, "errors": errors, "warnings": warnings}


def _response_note(response_row: dict[str, Any]) -> str:
    parts = []
    if _stringify(response_row.get("catalog_id", "")):
        parts.append(f"catalog_id={_stringify(response_row['catalog_id'])}")
    if _stringify(response_row.get("purity", "")):
        parts.append(f"purity={_stringify(response_row['purity'])}")
    if _stringify(response_row.get("pack_size_mg", "")):
        parts.append(f"pack_size_mg={_stringify(response_row['pack_size_mg'])}")
    if _stringify(response_row.get("lead_time_days", "")):
        parts.append(f"lead_time_days={_stringify(response_row['lead_time_days'])}")
    if _stringify(response_row.get("quote_currency", "")) or _stringify(response_row.get("quote_amount", "")):
        parts.append(
            "quote="
            + " ".join(
                part for part in [_stringify(response_row.get("quote_currency", "")), _stringify(response_row.get("quote_amount", ""))] if part
            )
        )
    if _stringify(response_row.get("coa_available", "")):
        parts.append(f"coa_available={_stringify(response_row['coa_available'])}")
    if _stringify(response_row.get("shipping_region", "")):
        parts.append(f"shipping_region={_stringify(response_row['shipping_region'])}")
    if _stringify(response_row.get("notes", "")):
        parts.append(f"notes={_stringify(response_row['notes'])}")
    return "; ".join(parts)


def build_payload(base_vendor_payload: dict[str, Any], response_frame: pd.DataFrame) -> dict[str, Any]:
    validation_payload = build_validation_payload(base_vendor_payload, response_frame)
    if validation_payload["errors"]:
        raise ValueError(" ; ".join(validation_payload["errors"]))
    response_rows = {
        _normalize_text(row.get("chembl_id", "")): dict(row)
        for row in response_frame.fillna("").to_dict(orient="records")
        if _normalize_text(row.get("chembl_id", ""))
    }

    merged_rows: list[dict[str, Any]] = []
    response_update_count = 0
    quoted_count = 0
    purchasable_count = 0
    unchanged_count = 0
    weak_response_count = 0

    for base_row in base_vendor_payload.get("rows", []) or []:
        chembl_key = _normalize_text(base_row.get("chembl_id", ""))
        response_row = response_rows.get(chembl_key, {})
        has_response = _has_response_data(response_row)
        merged_row = dict(base_row)
        merged_row.update(
            {
                "quote_response_received": has_response,
                "quote_response_catalog_id": _stringify(response_row.get("catalog_id", "")),
                "quote_response_purchasable": _truthy(response_row.get("purchasable", "")),
                "quote_response_purity": _stringify(response_row.get("purity", "")),
                "quote_response_pack_size_mg": _stringify(response_row.get("pack_size_mg", "")),
                "quote_response_lead_time_days": _stringify(response_row.get("lead_time_days", "")),
                "quote_response_currency": _stringify(response_row.get("quote_currency", "")),
                "quote_response_amount": _stringify(response_row.get("quote_amount", "")),
                "quote_response_coa_available": _stringify(response_row.get("coa_available", "")),
                "quote_response_shipping_region": _stringify(response_row.get("shipping_region", "")),
                "quote_response_notes": _stringify(response_row.get("notes", "")),
            }
        )
        if not has_response:
            unchanged_count += 1
            merged_rows.append(merged_row)
            continue

        strong_quote_evidence = _has_strong_quote_evidence(response_row)
        purchasable_evidence = _has_purchasable_evidence(response_row)
        if not strong_quote_evidence:
            weak_response_count += 1
            merged_row["quote_response_validation"] = "weak_quote_evidence"
            merged_row["quote_portal_note"] = (
                "Authenticated response row is present but below the minimum evidence threshold. "
                "At least one strong quote field is required for promotion."
            )
            unchanged_count += 1
            merged_rows.append(merged_row)
            continue

        response_update_count += 1
        is_purchasable = purchasable_evidence
        merged_row["vendor_status"] = "purchasable" if is_purchasable else "quoted"
        merged_row["vendor_purchase_confirmed"] = is_purchasable
        merged_row["vendor_evidence_source"] = (
            "manual_vendor_quote_response_purchasable" if is_purchasable else "manual_vendor_quote_response_quoted"
        )
        merged_row["vendor_evidence_url"] = _stringify(base_row.get("quote_portal_url", "")) or _stringify(base_row.get("vendor_evidence_url", ""))
        merged_row["vendor_evidence_note"] = _response_note(response_row)
        merged_row["vendor_purchase_url"] = _stringify(base_row.get("vendor_purchase_url", "")) or _stringify(base_row.get("quote_portal_url", ""))
        merged_row["vendor_web_check_date"] = date.today().isoformat()
        merged_row["quote_portal_status"] = "response_received"
        merged_row["quote_portal_note"] = (
            "Authenticated vendor response received. "
            + ("Compound marked purchasable." if is_purchasable else "Quote details received, but purchasable flag not yet confirmed.")
        )
        merged_row["manual_follow_up_required"] = not is_purchasable
        merged_row["quote_response_validation"] = "strong_quote_evidence"
        if is_purchasable:
            purchasable_count += 1
        else:
            quoted_count += 1
        merged_rows.append(merged_row)

    base_positive_count = int((base_vendor_payload.get("summary", {}) or {}).get("checked_positive_count", len(merged_rows)) or len(merged_rows))
    summary = {
        "status": "trpv1_vendor_quote_response_intake_ready",
        "target_id": "TRPV1_ION_CHANNEL_BLIND",
        "checked_on": date.today().isoformat(),
        "base_vendor_row_count": len(base_vendor_payload.get("rows", []) or []),
        "checked_positive_count": base_positive_count,
        "response_row_count": len(response_rows),
        "response_update_count": response_update_count,
        "weak_response_count": weak_response_count,
        "quoted_positive_count": quoted_count,
        "purchasable_positive_count": purchasable_count,
        "vendor_evidence_positive_count": sum(
            1
            for row in merged_rows
            if bool(row.get("vendor_purchase_confirmed", False))
            or _normalize_text(row.get("vendor_status", "")) in {"quoted", "purchasable", "catalog_live", "catalog_indexed_pubchem"}
        ),
        "manual_follow_up_required_count": sum(1 for row in merged_rows if bool(row.get("manual_follow_up_required", False))),
        "note": "Merged vendor evidence prefers authenticated quote responses over public web-check placeholders. `quoted` counts as exact product-level confirmation, while `purchasable` also confirms immediate availability.",
    }
    structured = {
        "promotion_rule": "Promote to `quoted` when an authenticated exact-product response exists. Promote to `purchasable` only when the vendor explicitly confirms purchasability or availability.",
        "downstream_rule": "Sourcing and CRO packet builders should prefer this merged artifact whenever it exists.",
    }
    return {"summary": summary, "structured": structured, "rows": merged_rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# TRPV1 Vendor Quote Response Intake",
        "",
        f"- status: `{summary['status']}`",
        f"- target_id: `{summary['target_id']}`",
        f"- checked_on: `{summary['checked_on']}`",
        f"- response_row_count: `{summary['response_row_count']}`",
        f"- response_update_count: `{summary['response_update_count']}`",
        f"- quoted_positive_count: `{summary['quoted_positive_count']}`",
        f"- purchasable_positive_count: `{summary['purchasable_positive_count']}`",
        f"- vendor_evidence_positive_count: `{summary['vendor_evidence_positive_count']}`",
        f"- manual_follow_up_required_count: `{summary['manual_follow_up_required_count']}`",
        "",
        f"- {summary['note']}",
        "",
        "| chembl_id | vendor_status | vendor_purchase_confirmed | catalog_id | quote_amount | manual_follow_up_required |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        quote_amount = " ".join(
            part for part in [str(row.get("quote_response_currency", "")).strip(), str(row.get("quote_response_amount", "")).strip()] if part
        )
        lines.append(
            f"| `{row.get('chembl_id', '')}` | `{row.get('vendor_status', '')}` | `{row.get('vendor_purchase_confirmed', False)}` | `{row.get('quote_response_catalog_id', '')}` | `{quote_amount}` | `{row.get('manual_follow_up_required', False)}` |"
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_validation_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# TRPV1 Vendor Quote Response Validation",
        "",
        f"- status: `{summary['status']}`",
        f"- row_count: `{summary['row_count']}`",
        f"- error_count: `{summary['error_count']}`",
        f"- warning_count: `{summary['warning_count']}`",
        "",
        "## Errors",
        "",
    ]
    if payload["errors"]:
        lines.extend(f"- {item}" for item in payload["errors"])
    else:
        lines.append("- none")
    lines.extend(["", "## Warnings", ""])
    if payload["warnings"]:
        lines.extend(f"- {item}" for item in payload["warnings"])
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "| row_index | chembl_id | response_row_has_data | strong_quote_evidence | purchasable_evidence | issue_codes |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            f"| `{row['row_index']}` | `{row['chembl_id']}` | `{row['response_row_has_data']}` | `{row['strong_quote_evidence']}` | `{row['purchasable_evidence']}` | `{row['issue_codes']}` |"
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _refresh_downstream(merged_vendor_json: Path) -> None:
    subprocess.run(
        [
            "python3",
            "tools/build_trpv1_vendor_quote_request_packet.py",
            "--vendor-web-check-json",
            str(merged_vendor_json),
        ],
        check=True,
    )
    subprocess.run(
        [
            "python3",
            "tools/build_trpv1_sourcing_status_sheet.py",
            "--vendor-web-check-json",
            str(merged_vendor_json),
        ],
        check=True,
    )
    subprocess.run(
        [
            "python3",
            "tools/build_wetlab_cro_delivery_packets.py",
            "--trpv1-vendor-web-check-json",
            str(merged_vendor_json),
        ],
        check=True,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge authenticated TRPV1 vendor quote responses into the curated vendor evidence artifact.")
    parser.add_argument("--base-vendor-web-check-json", default=DEFAULT_BASE_VENDOR_WEB_CHECK_JSON)
    parser.add_argument("--quote-response-csv", default=DEFAULT_QUOTE_RESPONSE_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--validation-json", default=DEFAULT_VALIDATION_JSON)
    parser.add_argument("--validation-md", default=DEFAULT_VALIDATION_MD)
    parser.add_argument(
        "--refresh-downstream",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Rebuild quote-request, sourcing-status, and CRO packet artifacts after writing the merged vendor evidence.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base_vendor_payload = _load_json(args.base_vendor_web_check_json)
    response_frame = pd.read_csv(_preferred_response_csv(args.quote_response_csv))
    validation_payload = build_validation_payload(base_vendor_payload, response_frame)
    validation_json = _resolve(args.validation_json)
    validation_md = _resolve(args.validation_md)
    validation_json.parent.mkdir(parents=True, exist_ok=True)
    validation_json.write_text(json.dumps(validation_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_validation_markdown(validation_md, validation_payload)
    if validation_payload["errors"]:
        raise ValueError(" ; ".join(validation_payload["errors"]))
    payload = build_payload(base_vendor_payload, response_frame)
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)
    if args.refresh_downstream:
        _refresh_downstream(out_json)


if __name__ == "__main__":
    main()
