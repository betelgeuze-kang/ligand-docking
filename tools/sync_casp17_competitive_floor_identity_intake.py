#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_INTAKE_CSV = "casp17/casp17_competitive_floor_identity_intake_bundle_current.csv"
DEFAULT_KIT_CSV = "casp17/casp17_competitive_floor_identity_unlock_kit_current.csv"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_identity_intake_sync_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_identity_intake_sync_current.csv"
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_IDENTITY_INTAKE_SYNC.md"

REQUIRED_FIELDS = ["proposed_benchmark_id", "proposed_target_id", "evidence_ref", "operator_clearance"]
SYNC_COLUMNS = [
    "dropzone_id",
    "operator_priority",
    "row_rank",
    "scope",
    "sync_status",
    "missing_field_count",
    "kit_mismatch_count",
    "intake_proposed_benchmark_id",
    "intake_proposed_target_id",
    "intake_evidence_ref",
    "intake_operator_clearance",
    "kit_proposed_benchmark_id",
    "kit_proposed_target_id",
    "kit_evidence_ref",
    "kit_operator_clearance",
    "next_action",
]
CLAIM_BOUNDARY = (
    "Local competitive-floor identity intake sync only. It copies operator-entered identity intake values into "
    "the identity unlock kit CSV when --apply is explicitly provided, so the existing identity validation/apply "
    "round can consume them. It does not choose targets, clear no-leak provenance, fetch native structures, score "
    "native accuracy, run predictors, mutate row_fill.csv, import evidence, or submit to CASP."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def _contains_placeholder(value: Any) -> bool:
    text = _text(value)
    upper = text.upper()
    return not text or upper.startswith("REQUIRED") or "REQUIRED_" in upper or "YYYY-MM-DD" in upper


def _read_csv(path_like: str | Path) -> tuple[list[dict[str, str]], list[str], list[str]]:
    path = _resolve(path_like)
    if not path.exists():
        return [], [], [f"{path.name}_missing"]
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    blockers: list[str] = []
    if not fieldnames:
        blockers.append(f"{path.name}_header_missing")
    if not rows:
        blockers.append(f"{path.name}_empty")
    return rows, fieldnames, blockers


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], *, fieldnames: list[str] | None = None) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    resolved = list(fieldnames or [])
    for row in rows:
        for key in row:
            if key not in resolved:
                resolved.append(key)
    if not resolved:
        resolved = SYNC_COLUMNS
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=resolved, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _by_dropzone(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {_text(row.get("dropzone_id")): row for row in rows if _text(row.get("dropzone_id"))}


def _missing_fields(row: dict[str, str]) -> list[str]:
    return [field for field in REQUIRED_FIELDS if _contains_placeholder(row.get(field))]


def _kit_mismatch_count(intake: dict[str, str], kit: dict[str, str]) -> int:
    return sum(1 for field in REQUIRED_FIELDS if _text(intake.get(field)) != _text(kit.get(field)))


def _sync_status(intake: dict[str, str], kit: dict[str, str]) -> str:
    if not kit:
        return "blocked_missing_kit_row"
    if _missing_fields(intake):
        return "awaiting_intake"
    return "synced" if _kit_mismatch_count(intake, kit) == 0 else "ready_to_sync"


def _next_action(status: str) -> str:
    if status == "awaiting_intake":
        return "fill proposed_benchmark_id, proposed_target_id, evidence_ref, and operator_clearance in the intake bundle"
    if status == "ready_to_sync":
        return "run this tool with --apply to copy intake identity values into the identity unlock kit"
    if status == "synced":
        return "run the identity unlock round with --apply-identity after review"
    if status == "blocked_missing_kit_row":
        return "rebuild the identity unlock kit so this dropzone has a target identity row"
    return "review this identity sync row"


def _apply_sync(args: argparse.Namespace, sync_rows: list[dict[str, Any]]) -> int:
    kit_rows, fieldnames, blockers = _read_csv(args.kit_csv)
    if blockers:
        return 0
    intake_rows, _intake_fields, intake_blockers = _read_csv(args.intake_csv)
    if intake_blockers:
        return 0
    intake_by_id = _by_dropzone(intake_rows)
    ready = {row["dropzone_id"] for row in sync_rows if row["sync_status"] == "ready_to_sync"}
    applied = 0
    for row in kit_rows:
        dropzone_id = _text(row.get("dropzone_id"))
        if dropzone_id not in ready:
            continue
        intake = intake_by_id.get(dropzone_id, {})
        for field in REQUIRED_FIELDS:
            row[field] = _text(intake.get(field))
        applied += 1
    _write_csv(args.kit_csv, kit_rows, fieldnames=fieldnames)
    return applied


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    intake_rows, _intake_fields, intake_blockers = _read_csv(args.intake_csv)
    kit_rows, _kit_fields, kit_blockers = _read_csv(args.kit_csv)
    intake_by_id = _by_dropzone(intake_rows)
    kit_by_id = _by_dropzone(kit_rows)
    dropzone_ids = sorted(set(intake_by_id) | set(kit_by_id))
    rows: list[dict[str, Any]] = []
    for dropzone_id in dropzone_ids:
        intake = intake_by_id.get(dropzone_id, {})
        kit = kit_by_id.get(dropzone_id, {})
        missing = _missing_fields(intake)
        status = _sync_status(intake, kit)
        rows.append(
            {
                "dropzone_id": dropzone_id,
                "operator_priority": _int(intake.get("operator_priority") or kit.get("operator_priority")),
                "row_rank": _int(intake.get("row_rank") or kit.get("row_rank")),
                "scope": _text(intake.get("scope") or kit.get("scope")),
                "sync_status": status,
                "missing_field_count": len(missing),
                "kit_mismatch_count": _kit_mismatch_count(intake, kit) if kit else 0,
                "intake_proposed_benchmark_id": _text(intake.get("proposed_benchmark_id")),
                "intake_proposed_target_id": _text(intake.get("proposed_target_id")),
                "intake_evidence_ref": _text(intake.get("evidence_ref")),
                "intake_operator_clearance": _text(intake.get("operator_clearance")),
                "kit_proposed_benchmark_id": _text(kit.get("proposed_benchmark_id")),
                "kit_proposed_target_id": _text(kit.get("proposed_target_id")),
                "kit_evidence_ref": _text(kit.get("evidence_ref")),
                "kit_operator_clearance": _text(kit.get("operator_clearance")),
                "next_action": _next_action(status),
            }
        )
    applied = _apply_sync(args, rows) if args.apply else 0
    by_status: dict[str, int] = {}
    for row in rows:
        by_status[row["sync_status"]] = by_status.get(row["sync_status"], 0) + 1
    if not rows:
        sync_status = "ready"
    elif intake_blockers or kit_blockers or by_status.get("blocked_missing_kit_row", 0):
        sync_status = "blocked"
    elif by_status.get("ready_to_sync", 0):
        sync_status = "ready_to_sync"
    elif by_status.get("awaiting_intake", 0):
        sync_status = "awaiting_intake"
    elif by_status.get("synced", 0) == len(rows):
        sync_status = "synced"
    else:
        sync_status = "awaiting_intake"
    first_open = next((row for row in rows if row["sync_status"] != "synced"), rows[0] if rows else {})
    summary = {
        "packet_type": "casp17_competitive_floor_identity_intake_sync",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "identity_intake_sync_status": sync_status,
        "apply_mode": "applied" if args.apply else "dry_run",
        "intake_csv": _artifact(args.intake_csv),
        "kit_csv": _artifact(args.kit_csv),
        "row_count": len(rows),
        "synced_count": by_status.get("synced", 0),
        "ready_to_sync_count": by_status.get("ready_to_sync", 0),
        "awaiting_intake_count": by_status.get("awaiting_intake", 0),
        "blocked_count": by_status.get("blocked_missing_kit_row", 0),
        "missing_field_count": sum(_int(row.get("missing_field_count")) for row in rows),
        "kit_mismatch_count": sum(_int(row.get("kit_mismatch_count")) for row in rows),
        "applied_sync_count": applied,
        "first_open_dropzone_id": _text(first_open.get("dropzone_id")),
        "first_open_status": _text(first_open.get("sync_status")),
        "first_open_next_action": _text(first_open.get("next_action")),
        "post_sync_validate_command": "python3 tools/run_casp17_competitive_floor_identity_unlock_round.py --apply-identity",
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Competitive-Floor Identity Intake Sync",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- identity_intake_sync_status: `{summary['identity_intake_sync_status']}`",
        f"- apply_mode: `{summary['apply_mode']}`",
        f"- rows synced/ready/awaiting/blocked: `{summary['synced_count']}/{summary['ready_to_sync_count']}/{summary['awaiting_intake_count']}/{summary['blocked_count']}`",
        f"- missing fields: `{summary['missing_field_count']}`",
        f"- kit mismatches: `{summary['kit_mismatch_count']}`",
        f"- applied sync rows: `{summary['applied_sync_count']}`",
        f"- first open: `{summary['first_open_dropzone_id'] or '-'}` `{summary['first_open_status'] or '-'}`",
        f"- next action: {summary['first_open_next_action'] or '-'}",
        f"- validate/apply command: `{summary['post_sync_validate_command']}`",
        "",
        "## Sync Rows",
        "",
        "| priority | dropzone | status | missing | mismatches | intake benchmark | intake target | kit benchmark | kit target | next action |",
        "| ---: | --- | --- | ---: | ---: | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['operator_priority']} | `{row['dropzone_id']}` | `{row['sync_status']}` | "
            f"{row['missing_field_count']} | {row['kit_mismatch_count']} | "
            f"`{row['intake_proposed_benchmark_id'] or '-'}` | `{row['intake_proposed_target_id'] or '-'}` | "
            f"`{row['kit_proposed_benchmark_id'] or '-'}` | `{row['kit_proposed_target_id'] or '-'}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | `ready` | 0 | 0 | - | - | - | - | no sync rows |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], fieldnames=SYNC_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync CASP17 identity intake values into the identity unlock kit.")
    parser.add_argument("--intake-csv", default=DEFAULT_INTAKE_CSV)
    parser.add_argument("--kit-csv", default=DEFAULT_KIT_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
