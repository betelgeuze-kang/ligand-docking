#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_WORKORDER_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_replacement_workorder_current.json"
DEFAULT_AUDIT_JSON = (
    "casp17/casp17_competitive_floor_target_identity_clearance_replacement_workorder_audit_current.json"
)
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_target_identity_clearance_replacement_pickup_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_target_identity_clearance_replacement_pickup_current.csv"
DEFAULT_OUT_MD = "casp17/COMPETITIVE_FLOOR_TARGET_IDENTITY_CLEARANCE_REPLACEMENT_PICKUP.md"

REQUIRED_MARKERS = ("REQUIRED", "YYYY-MM-DD")
CLAIM_BOUNDARY = (
    "Local CASP17 replacement clearance pickup packet only. It consolidates already-materialized "
    "replacement workorders, native dropzones, provenance templates, manifest stubs, and audit blockers "
    "for operator execution. It does not fetch native structures, clear no-leak provenance, choose final "
    "targets, score native accuracy, mutate live intake files, or submit to CASP."
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


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _read_csv_one(path_like: str | Path) -> dict[str, str]:
    path_value = _text(path_like)
    if not path_value:
        return {}
    path = _resolve(path_value)
    if not path.is_file():
        return {}
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except OSError:
        return {}
    return dict(rows[0]) if rows else {}


def _required_fields(row: dict[str, str]) -> list[str]:
    fields: list[str] = []
    for key, value in row.items():
        text = _text(value)
        if any(marker in text for marker in REQUIRED_MARKERS):
            fields.append(key)
    return fields


def _path_status(path_like: str | Path, *, kind: str) -> str:
    value = _text(path_like)
    if not value:
        return "missing_path"
    path = _resolve(value)
    if kind == "dir":
        return "present" if path.is_dir() else "missing"
    return "present" if path.is_file() else "missing"


def _audit_key(row: dict[str, Any]) -> tuple[str, str]:
    return (_text(row.get("target_id")), _text(row.get("native_dropzone_pdb")))


def _audit_for(row: dict[str, Any], audit_rows: list[dict[str, Any]]) -> dict[str, Any]:
    exact = {
        _audit_key(audit_row): audit_row
        for audit_row in audit_rows
        if _text(audit_row.get("target_id"))
    }
    key = (_text(row.get("target_id")), _text(row.get("native_dropzone_pdb")))
    if key in exact:
        return exact[key]
    target_id = _text(row.get("target_id"))
    for audit_row in audit_rows:
        if _text(audit_row.get("target_id")) == target_id:
            return audit_row
    return {}


def _pickup_status(workorder_row: dict[str, Any], audit_row: dict[str, Any]) -> str:
    selection_status = _text(workorder_row.get("selection_status"))
    if selection_status != "selected_for_replacement_workorder":
        return selection_status or "blocked"
    audit_status = _text(audit_row.get("audit_status"))
    if audit_status == "pass":
        return "ready_for_operator_intake"
    return "awaiting_operator_pickup"


def _next_action(workorder_row: dict[str, Any], audit_row: dict[str, Any], required_fields: list[str]) -> str:
    selection_status = _text(workorder_row.get("selection_status"))
    if selection_status != "selected_for_replacement_workorder":
        return _text(workorder_row.get("next_action")) or "resolve replacement candidate selection blockers"
    if _text(audit_row.get("native_file_status")) != "present":
        return "place the cleared native PDB in the native dropzone"
    if required_fields:
        return "fill the provenance template required fields"
    if _text(audit_row.get("manifest_stub_status")) != "ready":
        return "rerun the replacement workorder audit and manifest sync"
    return "rerun operator intake for this replacement candidate"


def _operator_action_count(row: dict[str, Any], required_fields: list[str]) -> int:
    if _text(row.get("selection_status")) != "selected_for_replacement_workorder":
        return 1
    count = 0
    if _text(row.get("native_file_status")) != "present":
        count += 1
    if required_fields:
        count += 1
    if _text(row.get("manifest_stub_status")) != "ready":
        count += 1
    return count


def _render_workorder_pickup_md(row: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {row['replace_target_id']} -> {row['target_id']} Replacement Pickup",
            "",
            f"- pickup_status: `{row['pickup_status']}`",
            f"- next_action: {row['next_action']}",
            f"- native_dropzone_pdb: `{row['native_dropzone_pdb'] or '-'}`",
            f"- provenance_template_csv: `{row['provenance_template_csv'] or '-'}`",
            f"- manifest_stub_csv: `{row['manifest_stub_csv'] or '-'}`",
            f"- prediction_pdb: `{row['prediction_pdb'] or '-'}`",
            f"- audit_status: `{row['audit_status']}`",
            f"- native/provenance/manifest: `{row['native_file_status']}/{row['provenance_status']}/{row['manifest_stub_status']}`",
            f"- required provenance fields: `{row['required_provenance_fields'] or '-'}`",
            f"- blockers: `{row['blockers'] or '-'}`",
            "",
            "## Operator Sequence",
            "",
            "1. Place only an operator-cleared native PDB at the native dropzone path.",
            "2. Fill every required provenance field with no-leak evidence and operator clearance.",
            "3. Rerun the replacement workorder audit before any promotion or intake sync.",
            "",
            "## Claim Boundary",
            "",
            CLAIM_BOUNDARY,
            "",
        ]
    )


def _write_workorder_pickup(row: dict[str, Any]) -> str:
    folder = _text(row.get("workorder_folder"))
    if not folder or row["selection_status"] != "selected_for_replacement_workorder":
        return ""
    path = _resolve(folder) / "OPERATOR_PICKUP.md"
    path.write_text(_render_workorder_pickup_md(row), encoding="utf-8")
    return _artifact(path)


def _build_row(workorder_row: dict[str, Any], audit_row: dict[str, Any]) -> dict[str, Any]:
    provenance_template = _text(workorder_row.get("provenance_template_csv"))
    provenance_values = _read_csv_one(provenance_template)
    required_fields = _required_fields(provenance_values)
    native_dropzone = _text(workorder_row.get("native_dropzone_pdb"))
    native_file_status = _text(audit_row.get("native_file_status")) or _path_status(native_dropzone, kind="file")
    row = {
        "replace_target_id": _text(workorder_row.get("replace_target_id")),
        "replace_target_name": _text(workorder_row.get("replace_target_name")),
        "target_id": _text(workorder_row.get("target_id")),
        "target_name": _text(workorder_row.get("target_name")),
        "scope": _text(workorder_row.get("scope")),
        "selection_status": _text(workorder_row.get("selection_status")),
        "pickup_status": "",
        "workorder_folder": _text(workorder_row.get("workorder_folder")),
        "native_dropzone_pdb": native_dropzone,
        "native_file_status": native_file_status,
        "provenance_template_csv": provenance_template,
        "provenance_template_status": _path_status(provenance_template, kind="file"),
        "required_provenance_field_count": len(required_fields),
        "required_provenance_fields": ",".join(required_fields),
        "manifest_stub_csv": _text(workorder_row.get("manifest_stub_csv")),
        "manifest_stub_status": _text(audit_row.get("manifest_stub_status"))
        or _path_status(workorder_row.get("manifest_stub_csv"), kind="file"),
        "prediction_pdb": _text(workorder_row.get("prediction_pdb")),
        "prediction_file_status": _text(audit_row.get("prediction_file_status"))
        or _path_status(workorder_row.get("prediction_pdb"), kind="file"),
        "prediction_protein_atom_record_count": int(audit_row.get("prediction_protein_atom_record_count") or 0),
        "audit_status": _text(audit_row.get("audit_status")) or "missing",
        "provenance_status": _text(audit_row.get("provenance_status")) or "missing",
        "evidence_ref_status": _text(audit_row.get("evidence_ref_status")) or "missing",
        "operator_action_count": 0,
        "next_action": "",
        "blockers": _text(audit_row.get("blockers")) or _text(workorder_row.get("blockers")),
        "operator_pickup_md": "",
    }
    row["pickup_status"] = _pickup_status(workorder_row, audit_row)
    row["operator_action_count"] = _operator_action_count(row, required_fields)
    row["next_action"] = _next_action(workorder_row, audit_row, required_fields)
    row["operator_pickup_md"] = _write_workorder_pickup(row)
    return row


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    workorder_payload = _read_json(args.workorder_json)
    audit_payload = _read_json(args.audit_json)
    audit_rows = _rows(audit_payload)
    rows = [_build_row(row, _audit_for(row, audit_rows)) for row in _rows(workorder_payload)]
    selected_rows = [row for row in rows if row["selection_status"] == "selected_for_replacement_workorder"]
    pickup_ready_rows = [row for row in selected_rows if row["pickup_status"] == "ready_for_operator_intake"]
    awaiting_rows = [row for row in selected_rows if row["pickup_status"] == "awaiting_operator_pickup"]
    blocked_selection_rows = [
        row for row in rows if row["selection_status"] != "selected_for_replacement_workorder"
    ]
    first_open = next((row for row in rows if row["pickup_status"] != "ready_for_operator_intake"), None)
    summary = {
        "packet_type": "casp17_competitive_floor_target_identity_clearance_replacement_pickup",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "replacement_pickup_status": "ready" if selected_rows and not awaiting_rows and not blocked_selection_rows else "open_actions",
        "workorder_json": _artifact(args.workorder_json),
        "audit_json": _artifact(args.audit_json),
        "row_count": len(rows),
        "selected_count": len(selected_rows),
        "ready_for_operator_intake_count": len(pickup_ready_rows),
        "awaiting_operator_pickup_count": len(awaiting_rows),
        "blocked_selection_count": len(blocked_selection_rows),
        "native_missing_count": sum(1 for row in selected_rows if row["native_file_status"] != "present"),
        "provenance_required_field_count": sum(int(row["required_provenance_field_count"]) for row in rows),
        "operator_action_count": sum(int(row["operator_action_count"]) for row in rows),
        "first_open_replace_target_id": first_open["replace_target_id"] if first_open else "",
        "first_open_target_id": first_open["target_id"] if first_open else "",
        "first_open_next_action": first_open["next_action"] if first_open else "",
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows, "workorder_summary": _summary(workorder_payload), "audit_summary": _summary(audit_payload)}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    if not fieldnames:
        fieldnames = ["replace_target_id", "target_id", "pickup_status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Replacement Clearance Pickup Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- replacement_pickup_status: `{summary['replacement_pickup_status']}`",
        f"- selected/ready/awaiting/blocked-selection: `{summary['selected_count']}/{summary['ready_for_operator_intake_count']}/{summary['awaiting_operator_pickup_count']}/{summary['blocked_selection_count']}`",
        f"- native missing: `{summary['native_missing_count']}`",
        f"- required provenance fields: `{summary['provenance_required_field_count']}`",
        f"- operator actions: `{summary['operator_action_count']}`",
        f"- first open: `{summary['first_open_replace_target_id'] or '-'}` -> `{summary['first_open_target_id'] or '-'}`",
        f"- first open next action: {summary['first_open_next_action'] or '-'}",
        "",
        "## Pickup Rows",
        "",
        "| replace target | candidate target | pickup | native | required fields | actions | pickup md | next action | blockers |",
        "| --- | --- | --- | --- | ---: | ---: | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['replace_target_id']}` | `{row['target_id']}` | `{row['pickup_status']}` | "
            f"`{row['native_file_status']}` | {row['required_provenance_field_count']} | "
            f"{row['operator_action_count']} | `{row['operator_pickup_md'] or '-'}` | "
            f"{row['next_action']} | `{row['blockers'] or '-'}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | `blocked` | - | 0 | 0 | - | create replacement workorders first | no rows |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a CASP17 replacement clearance operator pickup packet.")
    parser.add_argument("--workorder-json", default=DEFAULT_WORKORDER_JSON)
    parser.add_argument("--audit-json", default=DEFAULT_AUDIT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
