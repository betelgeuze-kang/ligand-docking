#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SHORTLIST_CSV = "docs/wetlab_packets/trpv1_ion_channel_candidate_shortlist.csv"
DEFAULT_SOURCING_REQUEST_CSV = "docs/wetlab_packets/trpv1_ion_channel_sourcing_request.csv"
DEFAULT_VENDOR_WEB_CHECK_JSON = "runs/trpv1_ion_channel_vendor_web_check_current.json"
DEFAULT_VENDOR_WEB_CHECK_MERGED_JSON = "runs/trpv1_ion_channel_vendor_web_check_merged_current.json"
DEFAULT_MATCHED_NEGATIVE_PANEL_JSON = "runs/trpv1_ion_channel_matched_negative_panel_current.json"
DEFAULT_VENDOR_FEASIBLE_NEGATIVE_PANEL_JSON = "runs/trpv1_ion_channel_vendor_feasible_negative_panel_resolved_current.json"
DEFAULT_VENDOR_QUOTE_PACKET_JSON = "runs/trpv1_ion_channel_vendor_quote_request_packet_current.json"
DEFAULT_OUT_JSON = "runs/trpv1_ion_channel_sourcing_status_current.json"
DEFAULT_OUT_CSV = "runs/trpv1_ion_channel_sourcing_status_current.csv"
DEFAULT_OUT_MD = "runs/trpv1_ion_channel_sourcing_status_current.md"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _load_json(path_like: str) -> dict[str, Any]:
    return json.loads(_resolve(path_like).read_text(encoding="utf-8"))


def _preferred_vendor_json(path_like: str) -> str:
    if path_like == DEFAULT_VENDOR_WEB_CHECK_JSON:
        merged = _resolve(DEFAULT_VENDOR_WEB_CHECK_MERGED_JSON)
        if merged.exists():
            return str(merged)
    return path_like


def _preferred_matched_negative_json(path_like: str) -> str:
    if path_like == DEFAULT_MATCHED_NEGATIVE_PANEL_JSON:
        preferred = _resolve(DEFAULT_VENDOR_FEASIBLE_NEGATIVE_PANEL_JSON)
        if preferred.exists():
            try:
                payload = json.loads(preferred.read_text(encoding="utf-8"))
                if bool(((payload.get("summary", {}) or {}).get("matched_negative_panel_sendable", False))):
                    return str(preferred)
            except Exception:
                pass
    return path_like


def build_payload(
    shortlist_frame: pd.DataFrame,
    sourcing_frame: pd.DataFrame,
    vendor_web_check_payload: dict[str, Any] | None = None,
    matched_negative_panel_payload: dict[str, Any] | None = None,
    vendor_quote_packet_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    shortlist = shortlist_frame.copy()
    sourcing = sourcing_frame.copy()
    shortlist["chembl_key"] = shortlist.get("chembl_id", "").map(_normalize_text)
    sourcing["chembl_key"] = sourcing.get("chembl_id", "").map(_normalize_text)
    vendor_rows = {
        _normalize_text(row.get("chembl_id", "")): dict(row)
        for row in ((vendor_web_check_payload or {}).get("rows", []) or [])
        if _normalize_text(row.get("chembl_id", ""))
    }
    vendor_summary = dict((vendor_web_check_payload or {}).get("summary", {}) or {})
    vendor_evidence_mode = "merged_quote_response" if str(vendor_summary.get("status", "")).strip() == "trpv1_vendor_quote_response_intake_ready" else "public_web_check"

    sourcing_cols = {
        col: f"sourcing_{col}"
        for col in sourcing.columns
        if col not in {"chembl_key"}
    }
    sourcing = sourcing.rename(columns=sourcing_cols)
    merged = shortlist.merge(sourcing, how="left", left_on="chembl_key", right_on="chembl_key")
    merged = merged.sort_values("priority_rank").copy()

    matched_negative_rows = list((matched_negative_panel_payload or {}).get("rows", []) or [])
    matched_negative_summary = dict((matched_negative_panel_payload or {}).get("summary", {}) or {})
    matched_negative_panel_locked = bool(matched_negative_summary.get("matched_negative_panel_locked", False))
    matched_negative_panel_sendable = bool(matched_negative_summary.get("matched_negative_panel_sendable", False))
    matched_negative_panel_mode = str(matched_negative_summary.get("panel_kind", "")).strip()

    rows: list[dict[str, Any]] = []
    for idx, (_, row) in enumerate(merged.iterrows(), start=1):
        priority_rank = int(row.get("priority_rank", idx))
        chembl_id = str(row.get("chembl_id", "")).strip()
        vendor_override = vendor_rows.get(_normalize_text(chembl_id), {})
        candidate_tier = (
            "proposed_positive_control"
            if priority_rank <= 3
            else "reserve_positive_pool"
            if priority_rank <= 6
            else "long_tail_candidate_pool"
        )
        vendor_status = (
            str(vendor_override.get("vendor_status", "")).strip()
            or str(row.get("vendor_status", "") or row.get("sourcing_vendor_status", "")).strip()
            or "vendor_check_pending"
        )
        vendor_confirmed = bool(vendor_override.get("vendor_purchase_confirmed", False)) or vendor_status in {
            "purchasable",
            "quoted",
            "catalog_live",
            "catalog_indexed_pubchem",
        }
        panel_lock_status = "locked" if priority_rank <= 3 and vendor_confirmed else "unlocked_vendor_pending" if priority_rank <= 3 else "reserve_only"
        blocker_codes = []
        if priority_rank <= 3 and not vendor_confirmed:
            blocker_codes.append("vendor_confirmation_missing")
        if matched_negative_panel_locked and not matched_negative_panel_sendable:
            blocker_codes.append("matched_negative_panel_internal_only")
        elif not matched_negative_panel_locked:
            blocker_codes.append("matched_negative_panel_missing")

        if priority_rank <= 3 and not vendor_confirmed and matched_negative_panel_locked and not matched_negative_panel_sendable:
            next_required_action = "confirm_vendor_quote_then_replace_internal_negative_panel"
        elif priority_rank <= 3 and not vendor_confirmed:
            next_required_action = "confirm_vendor_quote_then_select_matched_negative_controls"
        elif priority_rank <= 3 and matched_negative_panel_locked and not matched_negative_panel_sendable:
            next_required_action = "replace_internal_negative_panel_with_vendor_feasible_controls"
        else:
            next_required_action = "keep_as_reserve_candidate_until_top3_vendor_lock"
        rows.append(
            {
                "target_id": "TRPV1_ION_CHANNEL_BLIND",
                "priority_rank": priority_rank,
                "chembl_id": chembl_id,
                "normalized_name": str(row.get("normalized_name", "")).strip(),
                "inchi_key": str(row.get("inchi_key", "")).strip(),
                "candidate_tier": candidate_tier,
                "panel_slot": f"positive_{priority_rank}" if priority_rank <= 3 else "",
                "identity_status": str(row.get("identity_status", "")).strip() or "identity_normalized",
                "vendor_status": vendor_status,
                "vendor_purchase_confirmed": bool(vendor_confirmed),
                "vendor_purchase_url": str(vendor_override.get("vendor_purchase_url", "")).strip() or str(row.get("chembl_api_url", "")).strip(),
                "vendor_evidence_source": str(vendor_override.get("vendor_evidence_source", "")).strip(),
                "vendor_evidence_url": str(vendor_override.get("vendor_evidence_url", "")).strip(),
                "vendor_evidence_note": str(vendor_override.get("vendor_evidence_note", "")).strip(),
                "vendor_web_check_date": str(vendor_override.get("vendor_web_check_date", "")).strip(),
                "quote_portal_source": str(vendor_override.get("quote_portal_source", "")).strip(),
                "quote_portal_status": str(vendor_override.get("quote_portal_status", "")).strip(),
                "quote_portal_url": str(vendor_override.get("quote_portal_url", "")).strip(),
                "quote_portal_note": str(vendor_override.get("quote_portal_note", "")).strip(),
                "pubchem_property_url": str(row.get("pubchem_property_url", "")).strip(),
                "binding_score_composite_v5": row.get("binding_score_composite_v5", ""),
                "reference_binding_kcal_mol": row.get("reference_binding_kcal_mol", ""),
                "pchembl": row.get("pchembl", ""),
                "standard_type": str(row.get("standard_type", "")).strip(),
                "panel_lock_status": panel_lock_status,
                "positive_control_locked": bool(priority_rank <= 3 and vendor_confirmed),
                "negative_control_locked": False,
                "control_panel_locked": False,
                "blocker_codes": "; ".join(blocker_codes),
                "next_required_action": next_required_action,
                "readiness_note": str(row.get("readiness_note", "")).strip(),
            }
        )

    top3_rows = [row for row in rows if row["priority_rank"] <= 3]
    vendor_confirmed_positive_count = sum(1 for row in top3_rows if row["vendor_purchase_confirmed"])
    positive_control_panel_locked = vendor_confirmed_positive_count == 3
    matched_negative_slot_count_locked = int(matched_negative_summary.get("matched_negative_slot_count_locked", 0) or 0)
    control_panel_locked = positive_control_panel_locked and matched_negative_panel_locked and matched_negative_panel_sendable
    for row in rows:
        row["control_panel_locked"] = control_panel_locked
    if control_panel_locked:
        blocking_reason = ""
        next_required_step = "TRPV1 control panel is fully locked and the CRO packet can be sent."
    elif not positive_control_panel_locked and matched_negative_panel_locked and not matched_negative_panel_sendable:
        blocking_reason = (
            "two of the proposed TRPV1 positives still lack vendor-confirmed purchasability and the matched negative panel is only locked as an internal synthetic-decoy control set"
        )
        next_required_step = (
            "Convert CHEMBL2385220 and CHEMBL2177440 to quoted or purchasable status, then replace the internal synthetic matched negatives with vendor-feasible controls before external CRO send."
        )
    elif not positive_control_panel_locked:
        blocking_reason = "vendor confirmation is still missing for the proposed top-3 positives and no matched negative panel is locked yet"
        next_required_step = "Confirm vendor purchasability for the proposed top-3 positives, then lock three matched negatives before promoting TRPV1 to assay-ready CRO delivery."
    elif matched_negative_panel_locked and not matched_negative_panel_sendable:
        blocking_reason = "the matched negative panel is locked only as an internal synthetic-decoy set and is not externally sendable yet"
        next_required_step = "Replace the internal synthetic matched negatives with vendor-feasible controls before external CRO send."
    else:
        blocking_reason = "vendor confirmation is still missing for the proposed top-3 positives and no matched negative panel is locked yet"
        next_required_step = "Confirm vendor purchasability for the proposed top-3 positives, then lock three matched negatives before promoting TRPV1 to assay-ready CRO delivery."
    summary = {
        "status": "trpv1_ion_channel_sourcing_status_ready",
        "target_id": "TRPV1_ION_CHANNEL_BLIND",
        "candidate_count": len(rows),
        "proposed_positive_control_count": len(top3_rows),
        "vendor_confirmed_positive_count": vendor_confirmed_positive_count,
        "matched_negative_slot_count_required": 3,
        "matched_negative_slot_count_locked": matched_negative_slot_count_locked,
        "matched_negative_panel_locked_internal": matched_negative_panel_locked,
        "matched_negative_panel_sendable": matched_negative_panel_sendable,
        "positive_control_panel_locked": positive_control_panel_locked,
        "control_panel_locked": control_panel_locked,
        "vendor_evidence_mode": vendor_evidence_mode,
        "vendor_evidence_source_json": str(_resolve(_preferred_vendor_json(DEFAULT_VENDOR_WEB_CHECK_JSON))) if vendor_web_check_payload else "",
        "vendor_quote_response_received_count": int(vendor_summary.get("response_update_count", 0) or 0),
        "blocking_reason": blocking_reason,
        "next_required_step": next_required_step,
        "vendor_quote_request_packet_ready": bool((vendor_quote_packet_payload or {}).get("summary", {}).get("status")),
        "vendor_quote_request_count": int((vendor_quote_packet_payload or {}).get("summary", {}).get("quote_request_count", 0) or 0),
        "vendor_quote_request_packet_json": str(_resolve(DEFAULT_VENDOR_QUOTE_PACKET_JSON)) if vendor_quote_packet_payload else "",
        "matched_negative_panel_mode": matched_negative_panel_mode,
        "matched_negative_panel_source_json": str(_resolve(_preferred_matched_negative_json(DEFAULT_MATCHED_NEGATIVE_PANEL_JSON))) if matched_negative_panel_payload else "",
    }
    structured = {
        "vendor_status_rule": "Only `purchasable`, `quoted`, `catalog_live`, or `catalog_indexed_pubchem` count as vendor-confirmed.",
        "panel_lock_rule": "TRPV1 remains externally blocked until three positive controls are vendor-confirmed and three matched negatives are both locked and vendor-feasible.",
        "internal_negative_rule": "Synthetic hard-decoy negatives can count as internal matched-negative locks, but not as externally sendable CRO controls.",
    }
    return {"summary": summary, "structured": structured, "rows": rows, "matched_negative_rows": matched_negative_rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# TRPV1 Ion-Channel Sourcing Status",
        "",
        f"- status: `{summary['status']}`",
        f"- target_id: `{summary['target_id']}`",
        f"- candidate_count: `{summary['candidate_count']}`",
        f"- proposed_positive_control_count: `{summary['proposed_positive_control_count']}`",
        f"- vendor_confirmed_positive_count: `{summary['vendor_confirmed_positive_count']}`",
        f"- matched_negative_slot_count_required: `{summary['matched_negative_slot_count_required']}`",
        f"- matched_negative_slot_count_locked: `{summary['matched_negative_slot_count_locked']}`",
        f"- matched_negative_panel_locked_internal: `{summary['matched_negative_panel_locked_internal']}`",
        f"- matched_negative_panel_sendable: `{summary['matched_negative_panel_sendable']}`",
        f"- positive_control_panel_locked: `{summary['positive_control_panel_locked']}`",
        f"- control_panel_locked: `{summary['control_panel_locked']}`",
        f"- vendor_evidence_mode: `{summary['vendor_evidence_mode']}`",
        f"- vendor_quote_response_received_count: `{summary['vendor_quote_response_received_count']}`",
        f"- vendor_quote_request_packet_ready: `{summary['vendor_quote_request_packet_ready']}`",
        f"- vendor_quote_request_count: `{summary['vendor_quote_request_count']}`",
        "",
        "## Blocker",
        "",
        f"- {summary['blocking_reason']}",
        "",
        "## Candidate Table",
        "",
        "| priority_rank | chembl_id | candidate_tier | vendor_status | panel_lock_status | blocker_codes | next_required_action |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['priority_rank']}` | `{row['chembl_id']}` | `{row['candidate_tier']}` | `{row['vendor_status']}` | `{row['panel_lock_status']}` | `{row['blocker_codes']}` | `{row['next_required_action']}` |"
        )
    matched_negative_rows = payload.get("matched_negative_rows", []) or []
    if matched_negative_rows:
        lines.extend(
            [
                "",
                "## Matched Negative Panel",
                "",
                "| panel_slot | compound_id | negative_control_kind | mean_min_distance_A | binding_score_composite_v5 | external_send_ready |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for row in matched_negative_rows:
            lines.append(
                f"| `{row['panel_slot']}` | `{row['compound_id']}` | `{row['negative_control_kind']}` | `{row['mean_min_distance_A']}` | `{row['binding_score_composite_v5']}` | `{row['external_send_ready']}` |"
            )
    lines.extend(["", "## Next Step", "", f"- {summary['next_required_step']}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a TRPV1 sourcing status sheet from the normalized shortlist and sourcing request.")
    parser.add_argument("--shortlist-csv", default=DEFAULT_SHORTLIST_CSV)
    parser.add_argument("--sourcing-request-csv", default=DEFAULT_SOURCING_REQUEST_CSV)
    parser.add_argument("--vendor-web-check-json", default=DEFAULT_VENDOR_WEB_CHECK_JSON)
    parser.add_argument("--matched-negative-json", default=DEFAULT_MATCHED_NEGATIVE_PANEL_JSON)
    parser.add_argument("--vendor-quote-packet-json", default=DEFAULT_VENDOR_QUOTE_PACKET_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    vendor_web_check_json = _preferred_vendor_json(args.vendor_web_check_json)
    vendor_web_check_payload = _load_json(vendor_web_check_json) if _resolve(vendor_web_check_json).exists() else None
    matched_negative_json = _preferred_matched_negative_json(args.matched_negative_json)
    payload = build_payload(
        pd.read_csv(_resolve(args.shortlist_csv)),
        pd.read_csv(_resolve(args.sourcing_request_csv)),
        vendor_web_check_payload,
        _load_json(matched_negative_json) if _resolve(matched_negative_json).exists() else None,
        _load_json(args.vendor_quote_packet_json) if _resolve(args.vendor_quote_packet_json).exists() else None,
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
