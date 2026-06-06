#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_PENDING_POLICY_NOTE_JSON = "runs/pxr_pending_policy_note_current.json"
DEFAULT_NEXT_VERIFICATION_SLICE_JSON = "runs/pxr_next_verification_slice_current.json"
DEFAULT_PACKET_FILL_READINESS_JSON = "runs/pxr_packet_fill_readiness_current.json"
DEFAULT_PENDING_ROW_DISPOSITION_JSON = "runs/pxr_pending_row_disposition_current.json"
DEFAULT_MANUAL_REVIEW_QUEUE_JSON = "runs/pxr_manual_review_queue_current.json"
DEFAULT_OUT_JSON = "runs/pxr_pending_resolution_packet_current.json"
DEFAULT_OUT_CSV = "runs/pxr_pending_resolution_packet_current.csv"
DEFAULT_OUT_MD = "runs/pxr_pending_resolution_packet_current.md"


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


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _keyed(rows: list[dict[str, Any]], key_name: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get(key_name, "")).strip()
        if key:
            out[key] = dict(row)
    return out


def _readiness_lookup(readiness_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return _keyed(readiness_payload.get("readiness_rows", []) or [], "packet_step")


def _row_from_sources(
    *,
    packet_step: str,
    slice_row: dict[str, Any],
    disposition: dict[str, Any],
    queue_row: dict[str, Any],
    readiness: dict[str, Any],
    selected_in_next_slice: bool,
) -> dict[str, Any]:
    ligand = str(slice_row.get("replacement_ligand_id", "")).strip() or str(queue_row.get("ligand", "")).strip() or str(queue_row.get("replacement_ligand_id", "")).strip()
    replacement_is_binder = (
        str(slice_row.get("replacement_is_binder", "")).strip()
        or str(queue_row.get("binder", "")).strip()
        or str(queue_row.get("replacement_is_binder", "")).strip()
    )
    verification_status = str(slice_row.get("verification_status", "")).strip() or str(queue_row.get("verification_status", "")).strip()
    review_reason = str(slice_row.get("review_reason", "")).strip() or str(queue_row.get("notes", "")).strip() or str(disposition.get("notes", "")).strip()
    disposition_value = str(disposition.get("disposition", "")).strip() or str(queue_row.get("review_bucket", "")).strip()
    next_required_action = (
        str(slice_row.get("next_required_action", "")).strip()
        or str(disposition.get("next_required_action", "")).strip()
        or str(queue_row.get("next_required_action", "")).strip()
    )
    readiness_missing_fields = str(readiness.get("required_missing_fields", "")).strip() or str(readiness.get("missing_fields", "")).strip()
    ready_for_apply = str(slice_row.get("ready_for_authoritative_apply", "")).strip() or str(readiness.get("ready_for_apply", "")).strip()
    return {
        "priority_rank": str(slice_row.get("priority_rank", "")).strip() or str(queue_row.get("priority_rank", "")).strip(),
        "packet_step": packet_step,
        "ligand": ligand,
        "replacement_is_binder": replacement_is_binder,
        "verification_status": verification_status,
        "disposition": disposition_value,
        "assay_type_honesty": str(slice_row.get("assay_type_honesty", "")).strip() or str(queue_row.get("assay_type_honesty", "")).strip(),
        "review_reason": review_reason,
        "promotion_blocker": str(disposition.get("promotion_blocker", "")).strip(),
        "next_required_action": next_required_action,
        "readiness_missing_fields": readiness_missing_fields,
        "ready_for_authoritative_apply": ready_for_apply,
        "selected_in_next_verification_slice": "yes" if selected_in_next_slice else "no",
    }


def build_payload(
    pending_policy_note: dict[str, Any],
    next_verification_slice: dict[str, Any],
    packet_fill_readiness: dict[str, Any],
    pending_row_disposition: dict[str, Any],
    manual_review_queue: dict[str, Any],
) -> dict[str, Any]:
    readiness_by_step = _readiness_lookup(packet_fill_readiness)
    disposition_by_step = _keyed(pending_row_disposition.get("rows", []) or [], "packet_step")
    review_queue_by_step = _keyed(manual_review_queue.get("rows", []) or [], "packet_step")

    rows: list[dict[str, Any]] = []
    selected_steps: set[str] = set()
    for row in next_verification_slice.get("rows", []) or []:
        step = str(row.get("packet_step", "")).strip()
        if not step:
            continue
        rows.append(
            _row_from_sources(
                packet_step=step,
                slice_row=dict(row),
                disposition=disposition_by_step.get(step, {}),
                queue_row=review_queue_by_step.get(step, {}),
                readiness=readiness_by_step.get(step, {}),
                selected_in_next_slice=True,
            )
        )
        selected_steps.add(step)

    deferred_rows = sorted(
        manual_review_queue.get("rows", []) or [],
        key=lambda row: int(str(row.get("priority_rank", "999")).strip() or 999),
    )
    for queue_row in deferred_rows:
        step = str(queue_row.get("packet_step", "")).strip()
        if not step or step in selected_steps:
            continue
        rows.append(
            _row_from_sources(
                packet_step=step,
                slice_row={},
                disposition=disposition_by_step.get(step, {}),
                queue_row=dict(queue_row),
                readiness=readiness_by_step.get(step, {}),
                selected_in_next_slice=False,
            )
        )

    review_only_count = sum(1 for row in rows if "review_only" in row["disposition"])
    defer_count = sum(1 for row in rows if "defer" in row["disposition"])
    binder_gap_count = sum(
        1
        for row in rows
        if row["replacement_is_binder"] == "1"
        and str(row.get("promotion_blocker", "")).strip()
        in {"no_local_target_activity_curated", "quantitative_binding_value_or_activity_proxy_missing"}
    )
    supportive_binder_review_count = sum(
        1
        for row in rows
        if row["replacement_is_binder"] == "1"
        and str(row.get("promotion_blocker", "")).strip() == "activity_present_manual_confirmation_required"
    )
    confirmed_binder_quantitative_gap_count = sum(
        1
        for row in rows
        if row["replacement_is_binder"] == "1"
        and str(row.get("promotion_blocker", "")).strip() == "quantitative_binding_value_or_activity_proxy_missing"
    )

    summary = {
        "family": "pxr",
        "target": str(packet_fill_readiness.get("target", "PXR_NR1I2_BLIND")).strip(),
        "pending_resolution_row_count": len(rows),
        "selected_next_slice_row_count": sum(1 for row in rows if row["selected_in_next_verification_slice"] == "yes"),
        "manual_queue_only_row_count": sum(1 for row in rows if row["selected_in_next_verification_slice"] != "yes"),
        "review_only_row_count": review_only_count,
        "defer_row_count": defer_count,
        "binder_gap_count": binder_gap_count,
        "supportive_binder_review_count": supportive_binder_review_count,
        "confirmed_binder_quantitative_gap_count": confirmed_binder_quantitative_gap_count,
        "ready_for_apply_row_count": int(packet_fill_readiness.get("summary", {}).get("ready_for_apply_row_count", 0) or 0),
        "blocked_row_count": int(packet_fill_readiness.get("summary", {}).get("blocked_row_count", 0) or 0),
        "policy_line": str(pending_policy_note.get("summary", {}).get("policy_line", "")).strip(),
        "next_required_step": (
            "Work the current next-verification slice first, keep literature-supported binder rows deferred pending manual confirmation, and keep the remaining unresolved manual-review rows on the same deferred/review-only ledger until target-specific human PXR evidence changes their status."
            if supportive_binder_review_count
            else "Work the current next-verification slice first, keep literature-confirmed binder rows deferred until quantitative provenance is curated, and keep the remaining unresolved manual-review rows on the same deferred/review-only ledger until target-specific human PXR evidence changes their status."
            if confirmed_binder_quantitative_gap_count
            else "Work the current next-verification slice first, but keep the remaining unresolved manual-review rows on the same deferred/review-only ledger until target-specific human PXR evidence changes their status."
            if any(row["selected_in_next_verification_slice"] != "yes" for row in rows)
            else str(next_verification_slice.get("summary", {}).get("next_required_step", "")).strip()
            or str(pending_policy_note.get("summary", {}).get("next_required_step", "")).strip()
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# PXR Pending Resolution Packet",
        "",
        f"- family: `{s['family']}`",
        f"- target: `{s['target']}`",
        f"- pending_resolution_row_count: `{s['pending_resolution_row_count']}`",
        f"- selected_next_slice_row_count: `{s['selected_next_slice_row_count']}`",
        f"- manual_queue_only_row_count: `{s['manual_queue_only_row_count']}`",
        f"- review_only_row_count: `{s['review_only_row_count']}`",
        f"- defer_row_count: `{s['defer_row_count']}`",
        f"- binder_gap_count: `{s['binder_gap_count']}`",
        f"- supportive_binder_review_count: `{s['supportive_binder_review_count']}`",
        f"- confirmed_binder_quantitative_gap_count: `{s['confirmed_binder_quantitative_gap_count']}`",
        f"- ready_for_apply_row_count: `{s['ready_for_apply_row_count']}`",
        f"- blocked_row_count: `{s['blocked_row_count']}`",
        "",
        "## Policy Line",
        "",
        f"- {s['policy_line']}",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Pending Rows",
        "",
        "| priority_rank | packet_step | ligand | binder | disposition | in_next_slice | assay_type_honesty | promotion_blocker | next_required_action | ready_for_authoritative_apply |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['priority_rank']} | `{row['packet_step']}` | `{row['ligand']}` | `{row['replacement_is_binder']}` | "
            f"`{row['disposition']}` | `{row['selected_in_next_verification_slice']}` | `{row['assay_type_honesty']}` | `{row['promotion_blocker']}` | "
            f"`{row['next_required_action']}` | `{row['ready_for_authoritative_apply']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an operator-facing PXR pending-resolution packet from current policy and readiness artifacts.")
    parser.add_argument("--pending-policy-note-json", default=DEFAULT_PENDING_POLICY_NOTE_JSON)
    parser.add_argument("--next-verification-slice-json", default=DEFAULT_NEXT_VERIFICATION_SLICE_JSON)
    parser.add_argument("--packet-fill-readiness-json", default=DEFAULT_PACKET_FILL_READINESS_JSON)
    parser.add_argument("--pending-row-disposition-json", default=DEFAULT_PENDING_ROW_DISPOSITION_JSON)
    parser.add_argument("--manual-review-queue-json", default=DEFAULT_MANUAL_REVIEW_QUEUE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.pending_policy_note_json),
        _load_json(args.next_verification_slice_json),
        _load_json(args.packet_fill_readiness_json),
        _load_json(args.pending_row_disposition_json),
        _load_json(args.manual_review_queue_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
