#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_BINDER_LEDGER_JSON = "runs/transporter_binder_slot_ledger_current.json"
DEFAULT_NEGATIVE_DAY_PLAN_JSON = "runs/transporter_negative_reviewer_day_plan_current.json"
DEFAULT_APPLY_DRAFT_JSON = "runs/transporter_apply_draft_status_current.json"
DEFAULT_DONOR_BLOCKER_JSON = "runs/transporter_donor_policy_blocker_packet_current.json"
DEFAULT_OUT_JSON = "runs/transporter_blocker_capture_sheet_current.json"
DEFAULT_OUT_CSV = "runs/transporter_blocker_capture_sheet_current.csv"
DEFAULT_OUT_MD = "runs/transporter_blocker_capture_sheet_current.md"


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


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _existing_by_key(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    out: dict[str, dict[str, str]] = {}
    for row in _read_csv(path):
        key = "::".join(
            [
                str(row.get("target_id", "")).strip(),
                str(row.get("lane_type", "")).strip(),
                str(row.get("packet_step", "")).strip(),
            ]
        )
        if key.strip(":"):
            out[key] = row
    return out


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_payload(
    binder_ledger_payload: dict[str, Any],
    negative_day_plan_payload: dict[str, Any],
    apply_draft_payload: dict[str, Any],
    donor_blocker_payload: dict[str, Any],
    existing_sheet: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    existing_sheet = existing_sheet or {}
    rows: list[dict[str, Any]] = []
    for row in binder_ledger_payload.get("rows", []) or []:
        target_id = str(row.get("target_id", "")).strip()
        packet_step = str(row.get("packet_step", "")).strip()
        key = "::".join([target_id, "binder_seed", packet_step])
        existing = existing_sheet.get(key, {})
        rows.append(
            {
                "target_id": target_id,
                "lane_type": "binder_seed",
                "wave_label": str(row.get("wave_label", "")).strip(),
                "packet_step": packet_step,
                "placeholder_or_candidate": str(row.get("candidate_name", row.get("current_ligand_id", ""))).strip(),
                "promotion_blocker": str(row.get("promotion_blocker", "")).strip(),
                "evidence_anchor": str(row.get("evidence_anchor", "")).strip(),
                "supports_target_specific_packet_evidence": str(existing.get("supports_target_specific_packet_evidence", "")).strip(),
                "source_title": str(existing.get("source_title", "")).strip(),
                "source_url": str(existing.get("source_url", "")).strip(),
                "replacement_identifier": str(existing.get("replacement_identifier", "")).strip(),
                "replacement_source": str(existing.get("replacement_source", "")).strip(),
                "capture_status": str(existing.get("capture_status", "pending_capture")).strip(),
                "next_required_action": str(existing.get("next_required_action", row.get("next_required_action", ""))).strip(),
                "note": str(existing.get("note", row.get("notes", ""))).strip(),
            }
        )
    for row in negative_day_plan_payload.get("review_rows", []) or []:
        if str(row.get("review_phase", "")).strip() != "negative_slots_first":
            continue
        target_id = str(row.get("target_id", "")).strip()
        packet_step = str(row.get("packet_step", "")).strip()
        key = "::".join([target_id, "negative_slot", packet_step])
        existing = existing_sheet.get(key, {})
        rows.append(
            {
                "target_id": target_id,
                "lane_type": "negative_slot",
                "wave_label": str(row.get("wave_priority", "")).strip(),
                "packet_step": packet_step,
                "placeholder_or_candidate": str(row.get("candidate_or_label", "")).strip(),
                "promotion_blocker": str(row.get("promotion_blocker", "")).strip(),
                "evidence_anchor": str(existing.get("evidence_anchor", "")).strip(),
                "supports_target_specific_packet_evidence": str(existing.get("supports_target_specific_packet_evidence", "")).strip(),
                "source_title": str(existing.get("source_title", "")).strip(),
                "source_url": str(existing.get("source_url", "")).strip(),
                "replacement_identifier": str(existing.get("replacement_identifier", "")).strip(),
                "replacement_source": str(existing.get("replacement_source", "")).strip(),
                "capture_status": str(existing.get("capture_status", "pending_capture")).strip(),
                "next_required_action": str(existing.get("next_required_action", row.get("next_required_action", ""))).strip(),
                "note": str(existing.get("note", "")).strip(),
            }
        )

    source_linked_count = sum(1 for row in rows if str(row.get("source_title", "")).strip() or str(row.get("source_url", "")).strip())
    supportive_count = sum(
        1 for row in rows if str(row.get("supports_target_specific_packet_evidence", "")).strip().lower() in {"yes", "true", "1"}
    )
    summary = {
        "family": "transporter",
        "row_count": len(rows),
        "binder_seed_row_count": sum(1 for row in rows if row["lane_type"] == "binder_seed"),
        "negative_slot_row_count": sum(1 for row in rows if row["lane_type"] == "negative_slot"),
        "source_linked_count": source_linked_count,
        "supportive_target_specific_packet_evidence_count": supportive_count,
        "pending_capture_count": sum(1 for row in rows if str(row.get("capture_status", "")).strip() == "pending_capture"),
        "placeholder_driven_rows": int(apply_draft_payload.get("summary", {}).get("placeholder_driven_rows", 0) or 0),
        "donor_policy_reopen_ready": bool(donor_blocker_payload.get("summary", {}).get("reopen_ready", False)),
        "next_required_step": "Capture transporter-specific packet evidence for binder seed rows and negative slots before reopening donor policy or promoting any authoritative transporter apply row.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Transporter Blocker Capture Sheet",
        "",
        f"- family: `{summary['family']}`",
        f"- row_count: `{summary['row_count']}`",
        f"- binder_seed_row_count: `{summary['binder_seed_row_count']}`",
        f"- negative_slot_row_count: `{summary['negative_slot_row_count']}`",
        f"- source_linked_count: `{summary['source_linked_count']}`",
        f"- supportive_target_specific_packet_evidence_count: `{summary['supportive_target_specific_packet_evidence_count']}`",
        f"- pending_capture_count: `{summary['pending_capture_count']}`",
        f"- placeholder_driven_rows: `{summary['placeholder_driven_rows']}`",
        f"- donor_policy_reopen_ready: `{summary['donor_policy_reopen_ready']}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Rows",
        "",
        "| target_id | lane_type | packet_step | placeholder_or_candidate | capture_status | supportive | source_title | source_url | replacement_identifier |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['lane_type']}` | `{row['packet_step']}` | "
            f"`{row['placeholder_or_candidate']}` | `{row['capture_status']}` | "
            f"`{row['supports_target_specific_packet_evidence'] or '-'}` | `{row['source_title'] or '-'}` | "
            f"`{row['source_url'] or '-'}` | `{row['replacement_identifier'] or '-'}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a transporter blocker capture sheet for binder seed rows and negative slots.")
    parser.add_argument("--binder-ledger-json", default=DEFAULT_BINDER_LEDGER_JSON)
    parser.add_argument("--negative-day-plan-json", default=DEFAULT_NEGATIVE_DAY_PLAN_JSON)
    parser.add_argument("--apply-draft-json", default=DEFAULT_APPLY_DRAFT_JSON)
    parser.add_argument("--donor-blocker-json", default=DEFAULT_DONOR_BLOCKER_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_csv = _resolve(args.out_csv)
    payload = build_payload(
        _load_json(args.binder_ledger_json),
        _load_json(args.negative_day_plan_json),
        _load_json(args.apply_draft_json),
        _load_json(args.donor_blocker_json),
        existing_sheet=_existing_by_key(out_csv),
    )
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
