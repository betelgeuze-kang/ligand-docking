#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_UPLOAD_REVIEW_PACKET_JSON = "casp17/casp17_current_upload_review_packet_current.json"
DEFAULT_UPLOAD_OPERATOR_DECISION_KIT_JSON = "casp17/casp17_current_upload_operator_decision_kit_current.json"
DEFAULT_QUEUE_ROLLOVER_HYGIENE_AUDIT_JSON = "casp17/casp17_current_queue_rollover_hygiene_audit_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_current_upload_active_manifest_lock_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_current_upload_active_manifest_lock_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_CURRENT_UPLOAD_ACTIVE_MANIFEST_LOCK.md"

OPERATOR_FIELDS = [
    "operator_decision",
    "operator_id",
    "operator_decision_ref",
    "author_serialization_status",
    "final_upload_filename",
    "operator_notes",
]
ROW_COLUMNS = [
    "row_kind",
    "lock_status",
    "target_id",
    "queue_rank",
    "folder_path",
    "source_surface_id",
    "manifest_status",
    "operator_value_count",
    "operator_value_fields",
    "first_operator_value_field",
    "blockers",
    "next_action",
]
CLAIM_BOUNDARY = (
    "CASP17 current upload active-manifest lock only. It verifies that active upload decisions are tied to "
    "the current upload review/decision manifests and that retained stale generated folders remain read-only "
    "with no operator decision, author serialization, or final upload filename values. It does not delete "
    "folders, submit to CASP, serialize an author code, compute native accuracy, or mark strict-blind "
    "competitive proof."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: Any) -> str:
    if path_like is None or not str(path_like).strip():
        return ""
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(_text(value)))
    except (TypeError, ValueError):
        return 0


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(payload: dict[str, Any], key: str = "rows") -> list[dict[str, Any]]:
    rows = payload.get(key)
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ROW_COLUMNS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _operator_values_from_csv(folder: str) -> tuple[dict[str, str], list[str]]:
    path = _resolve(folder) / "operator_decision_row.csv"
    if not path.exists() or not path.is_file():
        return {}, []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except OSError:
        return {}, []
    row = dict(rows[0]) if rows else {}
    filled = [field for field in OPERATOR_FIELDS if _text(row.get(field))]
    return row, filled


def _operator_values_from_row(row: dict[str, Any]) -> list[str]:
    return [field for field in OPERATOR_FIELDS if _text(row.get(field))]


def _hygiene_stale_rows(hygiene_payload: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for surface in _rows(hygiene_payload):
        surface_id = _text(surface.get("surface_id"))
        stale_folders = surface.get("stale_extra_folders")
        if not isinstance(stale_folders, list):
            continue
        for folder in stale_folders:
            rows.append(
                {
                    "surface_id": surface_id,
                    "folder_path": _artifact(folder),
                }
            )
    return rows


def _active_target_row(review_row: dict[str, Any], decision_by_target: dict[str, dict[str, Any]]) -> dict[str, Any]:
    target_id = _text(review_row.get("target_id")).upper()
    decision = decision_by_target.get(target_id, {})
    folder = _text(decision.get("decision_packet_folder"))
    review_folder = _text(review_row.get("packet_folder"))
    operator_fields = _operator_values_from_row(decision)
    blockers: list[str] = []
    if not decision:
        blockers.append("active_decision_row_missing")
    if folder and not _resolve(folder).is_dir():
        blockers.append("active_decision_folder_missing")
    if review_folder and not _resolve(review_folder).is_dir():
        blockers.append("active_review_folder_missing")
    if blockers:
        status = "blocked_active_manifest_mismatch"
        next_action = "regenerate active upload review and decision surfaces before operator upload work"
    elif operator_fields:
        status = "active_manifest_locked_with_operator_values"
        next_action = "verify the operator values against the active manifest before any runtime upload"
    else:
        status = "active_manifest_locked_awaiting_operator_decision"
        next_action = "enter operator decision only in the active decision intake row"
    return {
        "row_kind": "active_upload_target",
        "lock_status": status,
        "target_id": target_id,
        "queue_rank": _int(review_row.get("queue_rank")),
        "folder_path": _artifact(folder),
        "source_surface_id": "current_upload_operator_decision_kit",
        "manifest_status": "active_manifest",
        "operator_value_count": len(operator_fields),
        "operator_value_fields": ",".join(operator_fields),
        "first_operator_value_field": operator_fields[0] if operator_fields else "",
        "blockers": ";".join(blockers),
        "next_action": next_action,
    }


def _stale_folder_row(stale: dict[str, str]) -> dict[str, Any]:
    folder = stale["folder_path"]
    operator_row, operator_fields = _operator_values_from_csv(folder)
    target_id = _text(operator_row.get("target_id")).upper()
    if operator_fields:
        status = "blocked_stale_operator_value_present"
        blockers = "stale_operator_value_present"
        next_action = "do not use this stale folder for upload; move values into the active manifest only after operator review"
    else:
        status = "stale_folder_readonly_no_operator_values"
        blockers = ""
        next_action = "keep stale folder read-only or clean it up only after operator approval"
    return {
        "row_kind": "stale_generated_folder",
        "lock_status": status,
        "target_id": target_id,
        "queue_rank": 0,
        "folder_path": folder,
        "source_surface_id": stale["surface_id"],
        "manifest_status": "stale_not_active_manifest",
        "operator_value_count": len(operator_fields),
        "operator_value_fields": ",".join(operator_fields),
        "first_operator_value_field": operator_fields[0] if operator_fields else "",
        "blockers": blockers,
        "next_action": next_action,
    }


def _status(input_missing: bool, rows: list[dict[str, Any]]) -> str:
    if input_missing:
        return "blocked_active_manifest_lock_missing_inputs"
    if not rows:
        return "blocked_active_manifest_lock_no_rows"
    if any(row["lock_status"] == "blocked_active_manifest_mismatch" for row in rows):
        return "blocked_active_manifest_mismatch"
    if any(row["lock_status"] == "blocked_stale_operator_value_present" for row in rows):
        return "blocked_stale_operator_decision_values_present"
    if any(row["row_kind"] == "stale_generated_folder" for row in rows):
        return "current_upload_active_manifest_lock_pass_stale_readonly"
    return "current_upload_active_manifest_lock_pass"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    review_payload = _read_json(args.upload_review_packet_json)
    decision_payload = _read_json(args.upload_operator_decision_kit_json)
    hygiene_payload = _read_json(args.queue_rollover_hygiene_audit_json)
    review_rows = _rows(review_payload)
    decision_rows = _rows(decision_payload)
    decision_by_target = {_text(row.get("target_id")).upper(): row for row in decision_rows}
    active_rows = [_active_target_row(row, decision_by_target) for row in review_rows]
    stale_rows = [_stale_folder_row(row) for row in _hygiene_stale_rows(hygiene_payload)]
    rows = active_rows + stale_rows

    missing_inputs = not review_payload or not decision_payload or not hygiene_payload
    blocked_rows = [row for row in rows if row["lock_status"].startswith("blocked_")]
    stale_blocked = [row for row in rows if row["lock_status"] == "blocked_stale_operator_value_present"]
    active_blocked = [row for row in rows if row["lock_status"] == "blocked_active_manifest_mismatch"]
    active_value_rows = [
        row
        for row in rows
        if row["row_kind"] == "active_upload_target" and row["operator_value_count"]
    ]
    stale_value_rows = [
        row
        for row in rows
        if row["row_kind"] == "stale_generated_folder" and row["operator_value_count"]
    ]
    first_blocked = blocked_rows[0] if blocked_rows else {}
    first_active = next((row for row in rows if row["row_kind"] == "active_upload_target"), {})
    first_stale = next((row for row in rows if row["row_kind"] == "stale_generated_folder"), {})

    summary = {
        "packet_type": "casp17_current_upload_active_manifest_lock",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "active_manifest_lock_status": _status(missing_inputs, rows),
        "active_target_count": len(active_rows),
        "active_locked_count": sum(
            1 for row in active_rows if row["lock_status"] != "blocked_active_manifest_mismatch"
        ),
        "active_blocked_count": len(active_blocked),
        "active_operator_value_row_count": len(active_value_rows),
        "stale_folder_count": len(stale_rows),
        "stale_readonly_count": sum(
            1 for row in stale_rows if row["lock_status"] == "stale_folder_readonly_no_operator_values"
        ),
        "stale_operator_value_folder_count": len(stale_value_rows),
        "stale_blocked_count": len(stale_blocked),
        "blocked_row_count": len(blocked_rows),
        "first_active_target_id": _text(first_active.get("target_id")),
        "first_stale_folder": _text(first_stale.get("folder_path")),
        "first_blocked_folder": _text(first_blocked.get("folder_path")),
        "first_blocked_target_id": _text(first_blocked.get("target_id")),
        "first_blocker": _text(first_blocked.get("blockers")),
        "review_packet_status": _text(_summary(review_payload).get("review_packet_status")),
        "decision_kit_status": _text(_summary(decision_payload).get("decision_kit_status")),
        "queue_rollover_hygiene_status": _text(_summary(hygiene_payload).get("status")),
        "upload_review_packet_json": _artifact(args.upload_review_packet_json),
        "upload_operator_decision_kit_json": _artifact(args.upload_operator_decision_kit_json),
        "queue_rollover_hygiene_audit_json": _artifact(args.queue_rollover_hygiene_audit_json),
        "claim_boundary": CLAIM_BOUNDARY,
        "next_action": (
            "work only the active 8-row operator decision intake; keep retained stale folders read-only until "
            "operator-approved cleanup"
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Current Upload Active Manifest Lock",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['active_manifest_lock_status']}`",
        f"- active targets locked/blocked/total: `{summary['active_locked_count']}/{summary['active_blocked_count']}/{summary['active_target_count']}`",
        f"- stale folders readonly/with-values/total: `{summary['stale_readonly_count']}/{summary['stale_operator_value_folder_count']}/{summary['stale_folder_count']}`",
        f"- first active target: `{summary['first_active_target_id'] or '-'}`",
        f"- first stale folder: `{summary['first_stale_folder'] or '-'}`",
        f"- first blocker: `{summary['first_blocked_target_id'] or '-'}` `{summary['first_blocker'] or '-'}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Rows",
        "",
        "| kind | status | target | folder | operator values | blocker | next action |",
        "| --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['row_kind']}` | `{row['lock_status']}` | `{row['target_id'] or '-'}` | "
            f"`{row['folder_path'] or '-'}` | {row['operator_value_count']} | "
            f"`{row['blockers'] or '-'}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | `blocked_active_manifest_lock_no_rows` | - | - | 0 | `no_rows` | provide inputs |")
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 active-manifest upload decision lock audit.")
    parser.add_argument("--upload-review-packet-json", default=DEFAULT_UPLOAD_REVIEW_PACKET_JSON)
    parser.add_argument("--upload-operator-decision-kit-json", default=DEFAULT_UPLOAD_OPERATOR_DECISION_KIT_JSON)
    parser.add_argument("--queue-rollover-hygiene-audit-json", default=DEFAULT_QUEUE_ROLLOVER_HYGIENE_AUDIT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
