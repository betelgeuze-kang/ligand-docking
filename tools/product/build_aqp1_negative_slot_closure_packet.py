#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_NEGATIVE_HANDOFF_JSON = "runs/aqp1_negative_review_handoff_packet_current.json"
DEFAULT_NEGATIVE_SOURCE_EXCLUSION_JSON = "runs/aqp1_negative_source_exclusion_packet_current.json"
DEFAULT_MANUAL_QUEUE_JSON = "runs/aqp1_manual_review_queue_current.json"
DEFAULT_NEXT_SLICE_JSON = "runs/aqp1_next_verification_slice_current.json"
DEFAULT_OUT_JSON = "runs/aqp1_negative_slot_closure_packet_current.json"
DEFAULT_OUT_CSV = "runs/aqp1_negative_slot_closure_packet_current.csv"
DEFAULT_OUT_MD = "runs/aqp1_negative_slot_closure_packet_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str | Path) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _index_by(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        value = _text(row.get(key))
        if value:
            out[value] = dict(row)
    return out


def build_payload(
    negative_handoff_payload: dict[str, Any],
    negative_source_exclusion_payload: dict[str, Any],
    manual_queue_payload: dict[str, Any],
    next_slice_payload: dict[str, Any],
) -> dict[str, Any]:
    handoff_rows = list((negative_handoff_payload or {}).get("rows", []) or [])
    manual_rows = list((manual_queue_payload or {}).get("rows", []) or [])
    next_rows = list((next_slice_payload or {}).get("rows", []) or [])

    handoff_by_step = _index_by(handoff_rows, "packet_step")
    next_by_step = _index_by(next_rows, "packet_step")

    blocker_rows = [
        row for row in handoff_rows if _text(row.get("section")) == "local_blocker_signal"
    ]
    blocker_signal_ids = ",".join(
        _text(row.get("packet_step")) for row in blocker_rows if _text(row.get("packet_step"))
    )
    blocker_notes = " | ".join(
        _text(row.get("notes")) for row in blocker_rows if _text(row.get("notes"))
    )

    rows: list[dict[str, Any]] = []
    negative_slots = sorted(
        (
            row
            for row in manual_rows
            if _text(row.get("packet_step")).startswith("core_non_binder_")
        ),
        key=lambda row: _int(row.get("priority_rank")),
    )
    exclusion_summary = dict((negative_source_exclusion_payload or {}).get("summary", {}) or {})

    for slot_rank, manual_row in enumerate(negative_slots, start=1):
        packet_step = _text(manual_row.get("packet_step"))
        next_row = next_by_step.get(packet_step, {})
        handoff_row = handoff_by_step.get(packet_step, {})
        rows.append(
            {
                "slot_rank": slot_rank,
                "queue_priority_rank": _int(manual_row.get("priority_rank")),
                "packet_step": packet_step,
                "current_ligand_id": _text(manual_row.get("current_ligand_id")) or _text(handoff_row.get("label")),
                "review_bucket": _text(manual_row.get("review_bucket")) or _text(handoff_row.get("review_bucket")),
                "recommended_resolution": _text(manual_row.get("recommended_resolution"))
                or _text(handoff_row.get("recommended_resolution")),
                "promotion_blocker": _text(manual_row.get("promotion_blocker"))
                or _text(handoff_row.get("promotion_blocker")),
                "required_missing_fields": _text(manual_row.get("required_missing_fields")),
                "next_action": _text(next_row.get("next_action"))
                or _text(manual_row.get("next_required_action"))
                or _text(handoff_row.get("next_action")),
                "notes": _text(next_row.get("notes"))
                or _text(manual_row.get("notes"))
                or _text(handoff_row.get("notes")),
                "closure_status": "review_only_slot_pending_direct_negative_evidence",
                "state_change_potential": "low",
                "authoritative_apply_allowed": False,
                "exclusion_context_artifact": _text(exclusion_summary.get("packet_artifact"))
                or "runs/aqp1_negative_source_exclusion_packet_current.md",
                "exclusion_context_primary_focus_ligand": _text(exclusion_summary.get("primary_focus_ligand")),
                "exclusion_exact_target_pair_absent_count": _int(
                    exclusion_summary.get("exact_target_pair_absent_count")
                ),
                "shared_blocker_signal_ids": blocker_signal_ids,
                "shared_blocker_signal_count": len(blocker_rows),
                "shared_blocker_notes": blocker_notes,
            }
        )

    summary = {
        "family": "aqp1",
        "target_id": _text(negative_handoff_payload.get("summary", {}).get("target_id")) or "AQP1_TRANSPORT_BLIND",
        "row_count": len(rows),
        "review_only_slot_count": len(rows),
        "shared_blocker_signal_count": len(blocker_rows),
        "exclusion_reference_row_count": _int(exclusion_summary.get("row_count")),
        "exclusion_exact_target_pair_absent_count": _int(exclusion_summary.get("exact_target_pair_absent_count")),
        "primary_focus_ligand": _text(rows[0]["current_ligand_id"]) if rows else "",
        "top_packet_step": _text(rows[0]["packet_step"]) if rows else "",
        "packet_artifact": "runs/aqp1_negative_slot_closure_packet_current.md",
        "authoritative_negative_apply_allowed": False,
        "next_required_step": (
            "Open core_non_binder_01 through core_non_binder_03 as slot-level review-only closures. "
            "Keep tetraethylammonium and acetazolamide in the exclusion-context packet only, "
            "and do not promote any AQP1 negative slot until direct transporter-specific quantitative negative evidence is curated."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# AQP1 Negative Slot Closure Packet",
        "",
        f"- family: `{s['family']}`",
        f"- target_id: `{s['target_id']}`",
        f"- row_count: `{s['row_count']}`",
        f"- review_only_slot_count: `{s['review_only_slot_count']}`",
        f"- shared_blocker_signal_count: `{s['shared_blocker_signal_count']}`",
        f"- exclusion_reference_row_count: `{s['exclusion_reference_row_count']}`",
        f"- exclusion_exact_target_pair_absent_count: `{s['exclusion_exact_target_pair_absent_count']}`",
        f"- primary_focus_ligand: `{s['primary_focus_ligand']}`",
        f"- top_packet_step: `{s['top_packet_step']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Slot Rows",
        "",
        "| slot_rank | packet_step | current_ligand_id | review_bucket | promotion_blocker | next_action | exclusion_context_primary_focus_ligand |",
        "| ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['slot_rank']} | `{row['packet_step']}` | `{row['current_ligand_id']}` | "
            f"`{row['review_bucket']}` | `{row['promotion_blocker']}` | `{row['next_action']}` | "
            f"`{row['exclusion_context_primary_focus_ligand']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the AQP1 negative slot closure packet.")
    parser.add_argument("--negative-handoff-json", default=DEFAULT_NEGATIVE_HANDOFF_JSON)
    parser.add_argument("--negative-source-exclusion-json", default=DEFAULT_NEGATIVE_SOURCE_EXCLUSION_JSON)
    parser.add_argument("--manual-queue-json", default=DEFAULT_MANUAL_QUEUE_JSON)
    parser.add_argument("--next-slice-json", default=DEFAULT_NEXT_SLICE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.negative_handoff_json),
        _load_json(args.negative_source_exclusion_json),
        _load_json(args.manual_queue_json),
        _load_json(args.next_slice_json),
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
