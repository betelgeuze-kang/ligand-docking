#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SOURCE_REQUEST_PACKET_JSON = (
    "casp17/casp17_strict_blind_source_gate_source_request_packet_current.json"
)
DEFAULT_FULFILLMENT_GATE_JSON = "casp17/casp17_strict_blind_source_request_fulfillment_gate_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_strict_blind_source_request_operator_fill_worklist_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_strict_blind_source_request_operator_fill_worklist_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_STRICT_BLIND_SOURCE_REQUEST_OPERATOR_FILL_WORKLIST.md"

ROW_COLUMNS = [
    "fill_id",
    "request_id",
    "candidate_target_id",
    "candidate_scope",
    "request_kind",
    "field_key",
    "operator_template_csv",
    "operator_value",
    "operator_evidence_ref",
    "value_status",
    "evidence_status",
    "fill_status",
    "first_blocker",
    "next_action",
]
EVIDENCE_REQUIRED_FIELDS = {
    "source_id",
    "prediction_pdb",
    "prediction_created_at",
    "native_release_date",
    "native_authority_ref",
    "creation_evidence_ref",
    "no_leak_evidence_ref",
    "method_summary",
    "operator_clearance",
}
FIELD_ORDER = [
    "source_id",
    "prediction_pdb",
    "prediction_pdb_dropzone",
    "prediction_created_at",
    "native_release_date",
    "prediction_created_at/native_release_date",
    "native_authority_ref",
    "creation_evidence_ref",
    "no_leak_evidence_ref",
    "method_summary",
    "operator_clearance",
]
CLAIM_BOUNDARY = (
    "Local CASP17 strict-blind source-request operator fill worklist only. It expands source request templates "
    "into one operator-fill surface and preserves existing values. It does not approve provenance, mutate source "
    "manifests, copy files, compute CASP metrics, push remotes, or submit to CASP."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    if not str(path_like):
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


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _read_csv_rows(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists() or not path.is_file():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _input_blockers(args: argparse.Namespace) -> list[str]:
    blockers = []
    for name in ["source_request_packet_json", "fulfillment_gate_json"]:
        if not _resolve(getattr(args, name)).exists():
            blockers.append(f"{name}_missing")
    return blockers


def _template_csv(request: dict[str, Any]) -> str:
    explicit = _text(request.get("operator_template_csv"))
    if explicit:
        return explicit
    folder = _text(request.get("request_folder"))
    return _artifact(_resolve(folder) / "operator_source_values_template.csv") if folder else ""


def _required_fields(request: dict[str, Any]) -> list[str]:
    fields = [field for field in _text(request.get("required_operator_fields")).split(",") if field]
    order = {field: index for index, field in enumerate(FIELD_ORDER)}
    return sorted(fields, key=lambda field: order.get(field, len(order)))


def _template_by_field(template_csv: str) -> dict[str, dict[str, str]]:
    return {_text(row.get("field_key")): row for row in _read_csv_rows(template_csv) if _text(row.get("field_key"))}


def _next_action(field_key: str, value_status: str, evidence_status: str, request_kind: str) -> str:
    if request_kind == "candidate_replacement_required":
        return "replace this out-of-scope candidate with a strict-blind monomer candidate before filling source fields"
    if value_status != "value_present":
        return f"fill operator_value for {field_key}"
    if evidence_status == "evidence_required_missing":
        return f"attach operator_evidence_ref for {field_key}"
    return "field is filled for source request fulfillment review"


def _build_rows(source_request_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for request in source_request_rows:
        template_csv = _template_csv(request)
        template_by_field = _template_by_field(template_csv)
        for field in _required_fields(request):
            template_row = template_by_field.get(field, {})
            operator_value = _text(template_row.get("operator_value"))
            operator_evidence_ref = _text(template_row.get("operator_evidence_ref"))
            value_status = "value_present" if operator_value else "operator_value_missing"
            if field not in EVIDENCE_REQUIRED_FIELDS:
                evidence_status = "evidence_not_required"
            elif operator_evidence_ref:
                evidence_status = "evidence_present"
            else:
                evidence_status = "evidence_required_missing"
            if _text(request.get("request_kind")) == "candidate_replacement_required":
                first_blocker = "candidate_replacement_required"
                fill_status = "blocked_candidate_replacement_required"
            elif value_status != "value_present":
                first_blocker = value_status
                fill_status = "awaiting_operator_value"
            elif evidence_status == "evidence_required_missing":
                first_blocker = evidence_status
                fill_status = "awaiting_operator_evidence"
            else:
                first_blocker = ""
                fill_status = "field_ready_for_fulfillment_gate"
            rows.append(
                {
                    "fill_id": f"source_request_operator_fill_{len(rows) + 1:03d}",
                    "request_id": _text(request.get("request_id")),
                    "candidate_target_id": _text(request.get("candidate_target_id")),
                    "candidate_scope": _text(request.get("candidate_scope")),
                    "request_kind": _text(request.get("request_kind")),
                    "field_key": field,
                    "operator_template_csv": template_csv,
                    "operator_value": operator_value,
                    "operator_evidence_ref": operator_evidence_ref,
                    "value_status": value_status,
                    "evidence_status": evidence_status,
                    "fill_status": fill_status,
                    "first_blocker": first_blocker,
                    "next_action": _next_action(field, value_status, evidence_status, _text(request.get("request_kind"))),
                }
            )
    return rows


def _status(input_blockers: list[str], rows: list[dict[str, Any]]) -> str:
    if input_blockers:
        return "blocked_missing_inputs"
    if not rows:
        return "blocked_no_source_request_fields"
    if any(row["fill_status"] == "awaiting_operator_value" for row in rows):
        return "awaiting_source_request_operator_values"
    if any(row["fill_status"] == "awaiting_operator_evidence" for row in rows):
        return "awaiting_source_request_operator_evidence"
    if any(row["fill_status"] == "blocked_candidate_replacement_required" for row in rows):
        return "awaiting_candidate_replacement_or_lane_move"
    return "source_request_operator_fill_worklist_ready"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    source_request_payload = _read_json(args.source_request_packet_json)
    fulfillment_payload = _read_json(args.fulfillment_gate_json)
    input_blockers = _input_blockers(args)
    rows = [] if input_blockers else _build_rows(_rows(source_request_payload))
    first = next((row for row in rows if row["fill_status"] != "field_ready_for_fulfillment_gate"), rows[0] if rows else {})
    summary = {
        "packet_type": "casp17_strict_blind_source_request_operator_fill_worklist",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_request_operator_fill_worklist_status": _status(input_blockers, rows),
        "source_request_packet_status": _text(_summary(source_request_payload).get("source_request_packet_status")),
        "fulfillment_gate_status": _text(_summary(fulfillment_payload).get("source_request_fulfillment_gate_status")),
        "request_count": len({row["request_id"] for row in rows}),
        "field_action_count": len(rows),
        "field_ready_count": sum(1 for row in rows if row["fill_status"] == "field_ready_for_fulfillment_gate"),
        "operator_value_missing_count": sum(1 for row in rows if row["value_status"] != "value_present"),
        "operator_evidence_missing_count": sum(1 for row in rows if row["evidence_status"] == "evidence_required_missing"),
        "candidate_replacement_field_count": sum(
            1 for row in rows if row["fill_status"] == "blocked_candidate_replacement_required"
        ),
        "first_fill_id": _text(first.get("fill_id")),
        "first_request_id": _text(first.get("request_id")),
        "first_target_id": _text(first.get("candidate_target_id")),
        "first_field_key": _text(first.get("field_key")),
        "first_blocker": _text(first.get("first_blocker")),
        "first_template_csv": _text(first.get("operator_template_csv")),
        "first_next_action": _text(first.get("next_action")),
        "input_blockers": ",".join(input_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Strict-Blind Source Request Operator Fill Worklist",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['source_request_operator_fill_worklist_status']}`",
        f"- source request/fulfillment: `{summary['source_request_packet_status'] or '-'}` `{summary['fulfillment_gate_status'] or '-'}`",
        f"- fields ready/value-missing/evidence-missing/total: `{summary['field_ready_count']}/{summary['operator_value_missing_count']}/{summary['operator_evidence_missing_count']}/{summary['field_action_count']}`",
        f"- candidate-replacement fields: `{summary['candidate_replacement_field_count']}`",
        f"- first fill: `{summary['first_fill_id'] or '-'}` `{summary['first_request_id'] or '-'}` `{summary['first_target_id'] or '-'}` `{summary['first_field_key'] or '-'}` `{summary['first_blocker'] or '-'}`",
        f"- first template: `{summary['first_template_csv'] or '-'}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        "",
        "## Fields",
        "",
        "| fill | request | target | field | status | value | evidence | template | next action |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"][:80]:
        lines.append(
            f"| `{row['fill_id']}` | `{row['request_id']}` | `{row['candidate_target_id']}` | "
            f"`{row['field_key']}` | `{row['fill_status']}` | `{row['value_status']}` | "
            f"`{row['evidence_status']}` | `{row['operator_template_csv']}` | {row['next_action']} |"
        )
    if len(payload["rows"]) > 80:
        lines.append(f"| ... | ... | ... | ... | ... | ... | ... | ... | {len(payload['rows']) - 80} more rows in CSV |")
    if not payload["rows"]:
        lines.append("| - | - | - | - | - | - | - | - | - |")
    lines.extend(["", CLAIM_BOUNDARY, ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 source-request operator fill worklist.")
    parser.add_argument("--source-request-packet-json", default=DEFAULT_SOURCE_REQUEST_PACKET_JSON)
    parser.add_argument("--fulfillment-gate-json", default=DEFAULT_FULFILLMENT_GATE_JSON)
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
