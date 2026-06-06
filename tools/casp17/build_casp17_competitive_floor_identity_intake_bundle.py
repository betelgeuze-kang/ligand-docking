#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_IDENTITY_KIT_JSON = "casp17/casp17_competitive_floor_identity_unlock_kit_current.json"
DEFAULT_READINESS_GATE_JSON = "casp17/casp17_competitive_floor_readiness_gate_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_identity_intake_bundle_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_identity_intake_bundle_current.csv"
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_IDENTITY_INTAKE_BUNDLE.md"

REQUIRED_FIELDS = ["proposed_benchmark_id", "proposed_target_id", "evidence_ref", "operator_clearance"]
INTAKE_COLUMNS = [
    "dropzone_id",
    "operator_priority",
    "row_rank",
    "scope",
    "current_benchmark_id",
    "current_target_id",
    "proposed_benchmark_id",
    "proposed_target_id",
    "evidence_ref",
    "operator_clearance",
    "identity_status",
    "missing_field_count",
    "blockers",
    "file_actions_unlocked",
    "readiness_gate_status",
    "apply_identity_command",
    "verify_command",
    "next_action",
]
CLAIM_BOUNDARY = (
    "Local competitive-floor identity intake bundle only. It exposes the operator-entered benchmark_id/target_id "
    "identity fields needed to unlock downstream file and value evidence plans. It does not choose historical "
    "targets, clear no-leak provenance, fetch native structures, score native accuracy, run predictors, mutate "
    "row_fill.csv, apply imports, or submit to CASP."
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


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


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
        resolved = INTAKE_COLUMNS
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=resolved, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _missing_fields(row: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for field in REQUIRED_FIELDS:
        if _contains_placeholder(row.get(field)):
            missing.append(field)
    return missing


def _apply_identity_command() -> str:
    return "python3 tools/run_casp17_competitive_floor_identity_unlock_round.py --apply-identity"


def _verify_command() -> str:
    return (
        "python3 tools/build_casp17_competitive_floor_execution_board.py && "
        "python3 tools/casp17/build_casp17_competitive_floor_readiness_gate.py"
    )


def _next_action(status: str, missing: list[str], blockers: str) -> str:
    if status == "ready_for_import":
        return "review identity values, then run the apply_identity_command"
    if status == "blocked_identity":
        return "fix identity blockers before applying: " + (blockers or "blocked_identity")
    if missing:
        return "fill " + ", ".join(missing)
    return "review identity row"


def _sort_key(row: dict[str, Any]) -> tuple[int, str]:
    return _int(row.get("operator_priority")) or _int(row.get("row_rank")), _text(row.get("dropzone_id"))


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    identity_payload = _read_json(args.identity_kit_json)
    gate_payload = _read_json(args.readiness_gate_json)
    identity_summary = _summary(identity_payload)
    gate_summary = _summary(gate_payload)
    readiness_status = _text(gate_summary.get("readiness_gate_status"))
    rows: list[dict[str, Any]] = []
    for source in _rows(identity_payload):
        missing = _missing_fields(source)
        status = _text(source.get("identity_status")) or "awaiting_identity"
        blockers = _text(source.get("blockers")) or ",".join(missing)
        rows.append(
            {
                "dropzone_id": _text(source.get("dropzone_id")),
                "operator_priority": _int(source.get("operator_priority")),
                "row_rank": _int(source.get("row_rank")),
                "scope": _text(source.get("scope")),
                "current_benchmark_id": _text(source.get("current_benchmark_id")),
                "current_target_id": _text(source.get("current_target_id")),
                "proposed_benchmark_id": _text(source.get("proposed_benchmark_id")),
                "proposed_target_id": _text(source.get("proposed_target_id")),
                "evidence_ref": _text(source.get("evidence_ref")),
                "operator_clearance": _text(source.get("operator_clearance")),
                "identity_status": status,
                "missing_field_count": len(missing),
                "blockers": blockers,
                "file_actions_unlocked": _int(source.get("file_actions_unlocked")),
                "readiness_gate_status": readiness_status,
                "apply_identity_command": _apply_identity_command(),
                "verify_command": _verify_command(),
                "next_action": _next_action(status, missing, blockers),
            }
        )
    rows.sort(key=_sort_key)
    ready_count = sum(1 for row in rows if row["identity_status"] == "ready_for_import")
    awaiting_count = sum(1 for row in rows if row["identity_status"] == "awaiting_identity")
    blocked_count = sum(1 for row in rows if row["identity_status"] == "blocked_identity")
    missing_field_count = sum(_int(row.get("missing_field_count")) for row in rows)
    if not rows:
        intake_status = "ready"
    elif blocked_count:
        intake_status = "blocked_identity"
    elif ready_count == len(rows):
        intake_status = "ready_for_identity_apply"
    elif ready_count:
        intake_status = "partial_identity_ready"
    else:
        intake_status = "awaiting_identity"
    first_open = next((row for row in rows if row["identity_status"] != "ready_for_import"), rows[0] if rows else {})
    summary = {
        "packet_type": "casp17_competitive_floor_identity_intake_bundle",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "identity_intake_status": intake_status,
        "identity_kit_json": _artifact(args.identity_kit_json),
        "readiness_gate_json": _artifact(args.readiness_gate_json),
        "identity_kit_status": _text(identity_summary.get("identity_unlock_status")),
        "readiness_gate_status": readiness_status,
        "row_count": len(rows),
        "ready_for_identity_apply_count": ready_count,
        "awaiting_identity_count": awaiting_count,
        "blocked_identity_count": blocked_count,
        "missing_field_count": missing_field_count,
        "file_actions_unlocked_count": sum(_int(row.get("file_actions_unlocked")) for row in rows),
        "first_open_dropzone_id": _text(first_open.get("dropzone_id")),
        "first_open_status": _text(first_open.get("identity_status")),
        "first_open_missing_field_count": _int(first_open.get("missing_field_count")),
        "first_open_next_action": _text(first_open.get("next_action")),
        "apply_identity_command": _apply_identity_command(),
        "verify_command": _verify_command(),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Competitive-Floor Identity Intake Bundle",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- identity_intake_status: `{summary['identity_intake_status']}`",
        f"- identity/readiness status: `{summary['identity_kit_status'] or '-'}` `{summary['readiness_gate_status'] or '-'}`",
        f"- rows ready/awaiting/blocked: `{summary['ready_for_identity_apply_count']}/{summary['awaiting_identity_count']}/{summary['blocked_identity_count']}`",
        f"- missing fields: `{summary['missing_field_count']}`",
        f"- file actions unlocked: `{summary['file_actions_unlocked_count']}`",
        f"- first open: `{summary['first_open_dropzone_id'] or '-'}` `{summary['first_open_status'] or '-'}` missing `{summary['first_open_missing_field_count']}`",
        f"- apply identity: `{summary['apply_identity_command']}`",
        f"- verify: `{summary['verify_command']}`",
        "",
        "## Intake Rows",
        "",
        "| priority | dropzone | status | missing | current benchmark | current target | proposed benchmark | proposed target | evidence ref | clearance | next action |",
        "| ---: | --- | --- | ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['operator_priority']} | `{row['dropzone_id']}` | `{row['identity_status']}` | "
            f"{row['missing_field_count']} | `{row['current_benchmark_id']}` | `{row['current_target_id']}` | "
            f"`{row['proposed_benchmark_id'] or '-'}` | `{row['proposed_target_id'] or '-'}` | "
            f"`{row['evidence_ref'] or '-'}` | `{row['operator_clearance'] or '-'}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | `ready` | 0 | - | - | - | - | - | - | no identity rows |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], fieldnames=INTAKE_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a CASP17 competitive-floor identity intake bundle.")
    parser.add_argument("--identity-kit-json", default=DEFAULT_IDENTITY_KIT_JSON)
    parser.add_argument("--readiness-gate-json", default=DEFAULT_READINESS_GATE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
