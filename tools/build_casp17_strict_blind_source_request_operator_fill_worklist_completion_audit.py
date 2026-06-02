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
DEFAULT_OPERATOR_FILL_WORKLIST_JSON = (
    "casp17/casp17_strict_blind_source_request_operator_fill_worklist_current.json"
)
DEFAULT_OUT_JSON = (
    "casp17/casp17_strict_blind_source_request_operator_fill_worklist_completion_audit_current.json"
)
DEFAULT_OUT_CSV = (
    "casp17/casp17_strict_blind_source_request_operator_fill_worklist_completion_audit_current.csv"
)
DEFAULT_OUT_MD = "casp17/CASP17_STRICT_BLIND_SOURCE_REQUEST_OPERATOR_FILL_WORKLIST_COMPLETION_AUDIT.md"

ROW_COLUMNS = [
    "request_id",
    "candidate_target_id",
    "candidate_scope",
    "request_kind",
    "audit_status",
    "request_folder",
    "source_request_md_present",
    "operator_template_csv",
    "operator_template_csv_present",
    "expected_field_count",
    "template_csv_row_count",
    "worklist_row_count",
    "template_missing_field_count",
    "operator_value_missing_count",
    "operator_evidence_missing_count",
    "candidate_replacement_field_count",
    "coordinate_copy_count",
    "proof_marker_count",
    "author_marker_count",
    "blockers",
    "next_action",
]

CLAIM_BOUNDARY = (
    "CASP17 strict-blind source-request operator-fill worklist completion audit only. It verifies "
    "that source request folders, SOURCE_REQUEST.md files, operator templates, worklist rows, and "
    "field-key coverage are synchronized. It reports missing operator values and evidence refs but "
    "does not fill them, approve provenance, copy coordinates, compute CASP metrics, serialize a "
    "CASP author code, push remotes, or submit to CASP."
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


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ROW_COLUMNS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _is_file(path_like: str | Path) -> bool:
    return bool(_text(path_like)) and _resolve(path_like).is_file()


def _is_dir(path_like: str | Path) -> bool:
    return bool(_text(path_like)) and _resolve(path_like).is_dir()


def _coordinate_file_count(path_like: str | Path) -> int:
    path = _resolve(path_like)
    if not path.exists():
        return 0
    return sum(1 for item in path.rglob("*") if item.is_file() and item.suffix.lower() in {".pdb", ".cif"})


def _boundary_marker_count(rows: list[dict[str, Any]], key: str) -> int:
    count = 0
    for row in rows:
        value = _text(row.get(key)).lower()
        if value and value not in {"false", "0", "no"}:
            count += 1
    return count


def _required_fields(request: dict[str, Any]) -> list[str]:
    return [field for field in _text(request.get("required_operator_fields")).split(",") if field]


def _rows_by_request(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        request_id = _text(row.get("request_id"))
        if request_id:
            grouped.setdefault(request_id, []).append(row)
    return grouped


def _request_folder(request: dict[str, Any]) -> str:
    folder = _text(request.get("request_folder"))
    if folder:
        return folder
    template = _text(request.get("operator_template_csv"))
    return _artifact(_resolve(template).parent) if template else ""


def _operator_template_csv(request: dict[str, Any]) -> str:
    explicit = _text(request.get("operator_template_csv"))
    if explicit:
        return explicit
    folder = _request_folder(request)
    return _artifact(_resolve(folder) / "operator_source_values_template.csv") if folder else ""


def _audit_request(
    request: dict[str, Any],
    *,
    worklist_rows_by_request: dict[str, list[dict[str, Any]]],
    global_blockers: list[str],
) -> dict[str, Any]:
    request_id = _text(request.get("request_id"))
    folder = _request_folder(request)
    source_request_md = _resolve(folder) / "SOURCE_REQUEST.md" if folder else Path("")
    template_csv = _operator_template_csv(request)
    required_fields = _required_fields(request)
    template_rows = _read_csv_rows(template_csv) if _is_file(template_csv) else []
    template_fields = {_text(row.get("field_key")) for row in template_rows if _text(row.get("field_key"))}
    worklist_rows = worklist_rows_by_request.get(request_id, [])
    worklist_fields = {_text(row.get("field_key")) for row in worklist_rows if _text(row.get("field_key"))}
    missing_from_template = [field for field in required_fields if field not in template_fields]
    missing_from_worklist = [field for field in required_fields if field not in worklist_fields]
    blockers = list(global_blockers)
    if not _is_dir(folder):
        blockers.append("request_folder_missing")
    if not _is_file(source_request_md):
        blockers.append("source_request_md_missing")
    if not _is_file(template_csv):
        blockers.append("operator_template_csv_missing")
    if len(template_rows) != len(required_fields):
        blockers.append("operator_template_csv_row_count_mismatch")
    if len(worklist_rows) != len(required_fields):
        blockers.append("worklist_row_count_mismatch")
    if missing_from_template:
        blockers.append("operator_template_missing_required_fields")
    if missing_from_worklist:
        blockers.append("worklist_missing_required_fields")
    coordinate_count = _coordinate_file_count(folder)
    if coordinate_count:
        blockers.append("request_coordinate_copy_present")
    proof_marker_count = _boundary_marker_count(template_rows + worklist_rows, "competitive_proof_eligible")
    author_marker_count = _boundary_marker_count(template_rows + worklist_rows, "author_serialized")
    if proof_marker_count:
        blockers.append("competitive_proof_marker_present")
    if author_marker_count:
        blockers.append("author_marker_present")
    blockers = list(dict.fromkeys(blockers))
    first_blocker = blockers[0] if blockers else ""
    return {
        "request_id": request_id,
        "candidate_target_id": _text(request.get("candidate_target_id")),
        "candidate_scope": _text(request.get("candidate_scope")),
        "request_kind": _text(request.get("request_kind")),
        "audit_status": "pass" if not blockers else "blocked",
        "request_folder": _artifact(folder),
        "source_request_md_present": int(_is_file(source_request_md)),
        "operator_template_csv": _artifact(template_csv),
        "operator_template_csv_present": int(_is_file(template_csv)),
        "expected_field_count": len(required_fields),
        "template_csv_row_count": len(template_rows),
        "worklist_row_count": len(worklist_rows),
        "template_missing_field_count": len(missing_from_template),
        "operator_value_missing_count": sum(1 for row in worklist_rows if _text(row.get("value_status")) != "value_present"),
        "operator_evidence_missing_count": sum(
            1 for row in worklist_rows if _text(row.get("evidence_status")) == "evidence_required_missing"
        ),
        "candidate_replacement_field_count": sum(
            1 for row in worklist_rows if _text(row.get("fill_status")) == "blocked_candidate_replacement_required"
        ),
        "coordinate_copy_count": coordinate_count,
        "proof_marker_count": proof_marker_count,
        "author_marker_count": author_marker_count,
        "blockers": ",".join(blockers),
        "next_action": (
            f"repair {first_blocker} for {request_id}"
            if first_blocker
            else "fill operator values and evidence refs; rerun fulfillment, sync, and source gate"
        ),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    source_request_path = _resolve(args.source_request_packet_json)
    worklist_path = _resolve(args.operator_fill_worklist_json)
    source_request_payload = _read_json(args.source_request_packet_json)
    worklist_payload = _read_json(args.operator_fill_worklist_json)
    source_request_summary = _summary(source_request_payload)
    worklist_summary = _summary(worklist_payload)
    source_request_rows = _rows(source_request_payload)
    worklist_rows = _rows(worklist_payload)
    global_blockers: list[str] = []
    if not source_request_path.exists():
        global_blockers.append("source_request_packet_json_missing")
    if not worklist_path.exists():
        global_blockers.append("operator_fill_worklist_json_missing")
    if len(source_request_rows) != _int(source_request_summary.get("request_count")):
        global_blockers.append("source_request_row_count_mismatch")
    if len(worklist_rows) != _int(worklist_summary.get("field_action_count")):
        global_blockers.append("worklist_row_count_mismatch")
    worklist_rows_by_request = _rows_by_request(worklist_rows)
    rows = [
        _audit_request(
            request,
            worklist_rows_by_request=worklist_rows_by_request,
            global_blockers=global_blockers,
        )
        for request in source_request_rows
    ]
    blocked = [row for row in rows if row["audit_status"] != "pass"]
    first_blocked = blocked[0] if blocked else {}
    total_expected_fields = sum(_int(row.get("expected_field_count")) for row in rows)
    total_template_rows = sum(_int(row.get("template_csv_row_count")) for row in rows)
    total_worklist_rows = sum(_int(row.get("worklist_row_count")) for row in rows)
    status = "casp17_strict_blind_source_request_operator_fill_worklist_completion_audit_pass"
    if not rows:
        status = "casp17_strict_blind_source_request_operator_fill_worklist_completion_audit_blocked_no_requests"
    elif blocked:
        status = "casp17_strict_blind_source_request_operator_fill_worklist_completion_audit_blocked"
    summary = {
        "packet_type": "casp17_strict_blind_source_request_operator_fill_worklist_completion_audit",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_request_operator_fill_worklist_completion_audit_status": status,
        "source_request_packet_status": _text(source_request_summary.get("source_request_packet_status")),
        "operator_fill_worklist_status": _text(
            worklist_summary.get("source_request_operator_fill_worklist_status")
        ),
        "request_count": len(rows),
        "request_pass_count": len(rows) - len(blocked),
        "request_blocked_count": len(blocked),
        "expected_field_count": total_expected_fields,
        "template_csv_row_count": total_template_rows,
        "worklist_row_count": total_worklist_rows,
        "field_row_mismatch_count": sum(
            1
            for row in rows
            if _int(row.get("expected_field_count")) != _int(row.get("template_csv_row_count"))
            or _int(row.get("expected_field_count")) != _int(row.get("worklist_row_count"))
        ),
        "template_missing_field_count": sum(_int(row.get("template_missing_field_count")) for row in rows),
        "operator_value_missing_count": sum(_int(row.get("operator_value_missing_count")) for row in rows),
        "operator_evidence_missing_count": sum(_int(row.get("operator_evidence_missing_count")) for row in rows),
        "candidate_replacement_field_count": sum(_int(row.get("candidate_replacement_field_count")) for row in rows),
        "request_folder_present_count": sum(1 for row in rows if _is_dir(row.get("request_folder", ""))),
        "source_request_md_present_count": sum(_int(row.get("source_request_md_present")) for row in rows),
        "operator_template_csv_present_count": sum(_int(row.get("operator_template_csv_present")) for row in rows),
        "coordinate_copy_count": sum(_int(row.get("coordinate_copy_count")) for row in rows),
        "proof_marker_count": sum(_int(row.get("proof_marker_count")) for row in rows),
        "author_marker_count": sum(_int(row.get("author_marker_count")) for row in rows),
        "first_blocked_request_id": _text(first_blocked.get("request_id")),
        "first_blocked_target_id": _text(first_blocked.get("candidate_target_id")),
        "first_blocker": _text(first_blocked.get("blockers")).split(",", 1)[0] if first_blocked else "",
        "next_action": (
            "fill operator values/evidence refs and rerun source request fulfillment"
            if not blocked
            else _text(first_blocked.get("next_action"))
        ),
        "input_blockers": ",".join(global_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Strict-Blind Source Request Operator Fill Worklist Completion Audit",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['source_request_operator_fill_worklist_completion_audit_status']}`",
        f"- source request/worklist: `{summary['source_request_packet_status'] or '-'}` `{summary['operator_fill_worklist_status'] or '-'}`",
        f"- requests pass/blocked/total: `{summary['request_pass_count']}/{summary['request_blocked_count']}/{summary['request_count']}`",
        f"- fields expected/template/worklist: `{summary['expected_field_count']}/{summary['template_csv_row_count']}/{summary['worklist_row_count']}`",
        f"- mismatches/missing-template-fields: `{summary['field_row_mismatch_count']}/{summary['template_missing_field_count']}`",
        f"- operator value/evidence missing: `{summary['operator_value_missing_count']}/{summary['operator_evidence_missing_count']}`",
        f"- candidate replacement fields: `{summary['candidate_replacement_field_count']}`",
        f"- files folder/source-md/template: `{summary['request_folder_present_count']}/{summary['source_request_md_present_count']}/{summary['operator_template_csv_present_count']}`",
        f"- hygiene coordinate/proof/author: `{summary['coordinate_copy_count']}/{summary['proof_marker_count']}/{summary['author_marker_count']}`",
        f"- first blocked: `{summary['first_blocked_request_id'] or '-'}` `{summary['first_blocked_target_id'] or '-'}` `{summary['first_blocker'] or '-'}`",
        f"- next action: {summary['next_action'] or '-'}",
        "",
        "## Claim Boundary",
        "",
        CLAIM_BOUNDARY,
        "",
        "## Requests",
        "",
        "| request | target | status | fields | value missing | evidence missing | blockers |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['request_id']}` | `{row['candidate_target_id']}` | `{row['audit_status']}` | "
            f"`{row['expected_field_count']}/{row['template_csv_row_count']}/{row['worklist_row_count']}` | "
            f"`{row['operator_value_missing_count']}` | `{row['operator_evidence_missing_count']}` | "
            f"`{row['blockers'] or '-'}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | - | - | - | - |")
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit CASP17 strict-blind source-request operator fill worklist completion."
    )
    parser.add_argument("--source-request-packet-json", default=DEFAULT_SOURCE_REQUEST_PACKET_JSON)
    parser.add_argument("--operator-fill-worklist-json", default=DEFAULT_OPERATOR_FILL_WORKLIST_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    write_outputs(args, build_payload(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
