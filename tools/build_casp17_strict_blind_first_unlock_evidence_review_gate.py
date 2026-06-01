#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_EVIDENCE_PACKET_JSON = "casp17/casp17_strict_blind_first_unlock_evidence_packet_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_strict_blind_first_unlock_evidence_review_gate_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_strict_blind_first_unlock_evidence_review_gate_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_STRICT_BLIND_FIRST_UNLOCK_EVIDENCE_REVIEW_GATE.md"

ROW_COLUMNS = [
    "field_order",
    "field_key",
    "required_evidence_kind",
    "required_operator_value_format",
    "template_operator_value",
    "template_operator_evidence_ref",
    "template_operator_clearance",
    "template_operator_id",
    "evidence_stub_md",
    "stub_exists",
    "stub_operator_value",
    "stub_operator_evidence_ref",
    "stub_operator_clearance",
    "stub_operator_id",
    "template_value_status",
    "template_evidence_ref_status",
    "template_clearance_status",
    "template_operator_id_status",
    "stub_status",
    "stub_evidence_status",
    "policy_status",
    "file_status",
    "review_gate_status",
    "first_blocker",
    "next_action",
]

ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
BAD_SOURCE_PREFIXES = ("official_archive", "casp_official", "massivefold_external")
CLEAR_VALUES = {"approved", "clear", "cleared", "true", "yes", "operator_clear", "operator_approved"}
TRUE_VALUES = {"true", "yes", "y", "1", "pass", "passed"}

CLAIM_BOUNDARY = (
    "Local CASP17 strict-blind first-unlock evidence review gate only. It validates whether the "
    "first-unlock evidence packet template and field stubs contain evidence-shaped operator values "
    "for source-gate review. It does not copy values into manifests, copy prediction files, approve "
    "provenance, compute CASP metrics, push remotes, or submit to CASP."
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


def _read_csv(path_like: str | Path) -> list[dict[str, str]]:
    if not str(path_like).strip():
        return []
    path = _resolve(path_like)
    if not path.is_file():
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


def _parse_stub(path_like: str | Path) -> dict[str, str]:
    fields = {
        "operator_value": "",
        "operator_evidence_ref": "",
        "operator_clearance": "",
        "operator_id": "",
    }
    path = _resolve(path_like)
    if not path.is_file():
        return fields
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return fields
    for line in lines:
        stripped = line.strip()
        for key in list(fields):
            prefix = f"- {key}:"
            if stripped.startswith(prefix):
                fields[key] = stripped[len(prefix) :].strip()
        if stripped.startswith("- evidence_ref:") and not fields["operator_evidence_ref"]:
            fields["operator_evidence_ref"] = stripped[len("- evidence_ref:") :].strip()
    return fields


def _pdb_has_atom_records(path_like: str) -> bool:
    if not path_like:
        return False
    path = _resolve(path_like)
    if not path.is_file():
        return False
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            return any(line.startswith(("ATOM  ", "HETATM")) for line in handle)
    except OSError:
        return False


def _policy_status(field_key: str, value: str) -> str:
    lowered = value.lower()
    if not value:
        return "policy_not_checked_value_missing"
    if field_key == "source_id":
        if lowered.startswith(BAD_SOURCE_PREFIXES):
            return "policy_fail_external_or_official_source_id"
        return "policy_pass"
    if field_key in {"prediction_created_at", "native_release_date"}:
        return "policy_pass" if ISO_DATE_PATTERN.match(value) else "policy_fail_expected_iso_date"
    if field_key == "prediction_created_at/native_release_date":
        return "policy_pass" if lowered in TRUE_VALUES or "<" in value else "policy_fail_expected_before_native"
    if field_key == "operator_clearance":
        return "policy_pass" if lowered in CLEAR_VALUES else "policy_fail_expected_operator_clearance"
    return "policy_pass"


def _file_status(field_key: str, value: str) -> str:
    if field_key not in {"prediction_pdb", "prediction_pdb_dropzone"}:
        return "file_not_required"
    if not value:
        return "file_path_missing"
    if not _resolve(value).is_file():
        return "file_missing"
    if not _pdb_has_atom_records(value):
        return "pdb_atom_records_missing"
    return "file_present_with_atom_records"


def _next_action(row: dict[str, Any], blockers: list[str]) -> str:
    field_key = row["field_key"]
    first = blockers[0] if blockers else ""
    if first == "template_operator_value_missing":
        return f"fill operator_value for {field_key} in operator_evidence_template.csv"
    if first == "template_operator_evidence_ref_missing":
        return f"fill operator_evidence_ref for {field_key} in operator_evidence_template.csv"
    if first == "template_operator_clearance_missing":
        return f"fill operator_clearance for {field_key} in operator_evidence_template.csv"
    if first == "template_operator_id_missing":
        return f"fill operator_id for {field_key} in operator_evidence_template.csv"
    if first == "stub_missing":
        return f"restore evidence stub {row['evidence_stub_md']}"
    if first.startswith("stub_"):
        return f"fill {first.removeprefix('stub_').removesuffix('_missing')} in {row['evidence_stub_md']}"
    if first.startswith("policy_fail"):
        return f"revise operator_value for {field_key} to satisfy strict-blind source policy"
    if first in {"file_path_missing", "file_missing", "pdb_atom_records_missing"}:
        return f"attach a valid PDB file with atom records for {field_key}"
    return f"review accepted evidence for {field_key}, then sync into the source gate"


def _review_row(packet_row: dict[str, Any], template_by_field: dict[str, dict[str, str]]) -> dict[str, Any]:
    field_key = _text(packet_row.get("field_key"))
    template = template_by_field.get(field_key, {})
    operator_value = _text(template.get("operator_value"))
    operator_evidence_ref = _text(template.get("operator_evidence_ref"))
    operator_clearance = _text(template.get("operator_clearance"))
    operator_id = _text(template.get("operator_id"))
    stub_path = _text(packet_row.get("evidence_stub_md") or template.get("evidence_stub_md"))
    stub_exists = _resolve(stub_path).is_file() if stub_path else False
    stub_fields = _parse_stub(stub_path)
    template_value_status = "template_operator_value_present" if operator_value else "template_operator_value_missing"
    template_evidence_ref_status = (
        "template_operator_evidence_ref_present"
        if operator_evidence_ref
        else "template_operator_evidence_ref_missing"
    )
    template_clearance_status = (
        "template_operator_clearance_present" if operator_clearance else "template_operator_clearance_missing"
    )
    template_operator_id_status = "template_operator_id_present" if operator_id else "template_operator_id_missing"
    stub_status = "stub_present" if stub_exists else "stub_missing"
    stub_blockers = [
        f"stub_{key}_missing"
        for key, value in stub_fields.items()
        if not _text(value)
    ]
    policy_status = _policy_status(field_key, operator_value)
    file_status = _file_status(field_key, operator_value)
    blocker_candidates = [
        template_value_status,
        template_evidence_ref_status,
        template_clearance_status,
        template_operator_id_status,
        stub_status,
        *stub_blockers,
        policy_status,
        file_status,
    ]
    pass_statuses = {
        "template_operator_value_present",
        "template_operator_evidence_ref_present",
        "template_operator_clearance_present",
        "template_operator_id_present",
        "stub_present",
        "policy_pass",
        "file_not_required",
        "file_present_with_atom_records",
    }
    blockers = [status for status in blocker_candidates if status not in pass_statuses]
    row = {
        "field_order": _int(packet_row.get("field_order")),
        "field_key": field_key,
        "required_evidence_kind": _text(packet_row.get("required_evidence_kind")),
        "required_operator_value_format": _text(packet_row.get("required_operator_value_format")),
        "template_operator_value": operator_value,
        "template_operator_evidence_ref": operator_evidence_ref,
        "template_operator_clearance": operator_clearance,
        "template_operator_id": operator_id,
        "evidence_stub_md": stub_path,
        "stub_exists": str(stub_exists).lower(),
        "stub_operator_value": _text(stub_fields.get("operator_value")),
        "stub_operator_evidence_ref": _text(stub_fields.get("operator_evidence_ref")),
        "stub_operator_clearance": _text(stub_fields.get("operator_clearance")),
        "stub_operator_id": _text(stub_fields.get("operator_id")),
        "template_value_status": template_value_status,
        "template_evidence_ref_status": template_evidence_ref_status,
        "template_clearance_status": template_clearance_status,
        "template_operator_id_status": template_operator_id_status,
        "stub_status": stub_status,
        "stub_evidence_status": ",".join(stub_blockers) if stub_blockers else "stub_evidence_present",
        "policy_status": policy_status,
        "file_status": file_status,
        "review_gate_status": "field_ready_for_source_gate_sync" if not blockers else "awaiting_operator_evidence",
        "first_blocker": blockers[0] if blockers else "",
    }
    row["next_action"] = _next_action(row, blockers)
    return row


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    packet_path = _resolve(args.evidence_packet_json)
    packet_payload = _read_json(packet_path)
    packet_summary = _summary(packet_payload)
    packet_rows = _rows(packet_payload)
    template_csv = _text(packet_summary.get("operator_evidence_template_csv"))
    template_rows = _read_csv(template_csv)
    template_by_field = {_text(row.get("field_key")): row for row in template_rows if _text(row.get("field_key"))}
    rows = [_review_row(row, template_by_field) for row in packet_rows]
    blocked = [row for row in rows if row["review_gate_status"] != "field_ready_for_source_gate_sync"]
    ready = [row for row in rows if row["review_gate_status"] == "field_ready_for_source_gate_sync"]
    first_blocked = blocked[0] if blocked else {}
    if not packet_path.exists():
        status = "blocked_first_unlock_evidence_packet_missing"
    elif not packet_rows:
        status = "blocked_first_unlock_evidence_packet_rows_missing"
    elif blocked:
        status = "awaiting_first_unlock_evidence_review"
    else:
        status = "first_unlock_evidence_ready_for_source_gate_sync"
    summary = {
        "packet_type": "casp17_strict_blind_first_unlock_evidence_review_gate",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "first_unlock_evidence_review_gate_status": status,
        "evidence_packet_json": _artifact(args.evidence_packet_json),
        "evidence_packet_status": _text(packet_summary.get("first_unlock_evidence_packet_status")),
        "request_id": _text(packet_summary.get("request_id")),
        "candidate_target_id": _text(packet_summary.get("candidate_target_id")),
        "field_count": len(rows),
        "ready_field_count": len(ready),
        "blocked_field_count": len(blocked),
        "template_operator_value_missing_count": sum(
            row["template_value_status"] == "template_operator_value_missing" for row in rows
        ),
        "template_operator_evidence_ref_missing_count": sum(
            row["template_evidence_ref_status"] == "template_operator_evidence_ref_missing" for row in rows
        ),
        "template_operator_clearance_missing_count": sum(
            row["template_clearance_status"] == "template_operator_clearance_missing" for row in rows
        ),
        "template_operator_id_missing_count": sum(
            row["template_operator_id_status"] == "template_operator_id_missing" for row in rows
        ),
        "stub_present_count": sum(row["stub_status"] == "stub_present" for row in rows),
        "stub_evidence_missing_count": sum(row["stub_evidence_status"] != "stub_evidence_present" for row in rows),
        "policy_pass_count": sum(row["policy_status"] == "policy_pass" for row in rows),
        "policy_blocked_count": sum(row["policy_status"] != "policy_pass" for row in rows),
        "file_ready_count": sum(row["file_status"] == "file_present_with_atom_records" for row in rows),
        "file_blocked_count": sum(
            row["file_status"] not in {"file_present_with_atom_records", "file_not_required"} for row in rows
        ),
        "first_blocked_field": _text(first_blocked.get("field_key")),
        "first_blocker": _text(first_blocked.get("first_blocker")),
        "first_next_action": _text(first_blocked.get("next_action")),
        "operator_evidence_template_csv": _text(packet_summary.get("operator_evidence_template_csv")),
        "packet_folder": _text(packet_summary.get("packet_folder")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"rows": rows, "summary": summary}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Strict-Blind First Unlock Evidence Review Gate",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['first_unlock_evidence_review_gate_status']}`",
        f"- request/target: `{summary['request_id']}` `{summary['candidate_target_id']}`",
        f"- fields ready/blocked/total: `{summary['ready_field_count']}/{summary['blocked_field_count']}/{summary['field_count']}`",
        f"- template value/evidence/clearance/id missing: `{summary['template_operator_value_missing_count']}/{summary['template_operator_evidence_ref_missing_count']}/{summary['template_operator_clearance_missing_count']}/{summary['template_operator_id_missing_count']}`",
        f"- stubs present/evidence-missing: `{summary['stub_present_count']}/{summary['stub_evidence_missing_count']}`",
        f"- policy pass/blocked: `{summary['policy_pass_count']}/{summary['policy_blocked_count']}`",
        f"- file ready/blocked: `{summary['file_ready_count']}/{summary['file_blocked_count']}`",
        f"- first blocked: `{summary['first_blocked_field'] or '-'}` `{summary['first_blocker'] or '-'}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        "",
        "## Fields",
        "",
        "| order | field | status | blocker | policy | file | next action |",
        "| ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            "| {order} | `{field}` | `{status}` | `{blocker}` | `{policy}` | `{file}` | {next_action} |".format(
                order=row["field_order"],
                field=row["field_key"],
                status=row["review_gate_status"],
                blocker=row["first_blocker"] or "-",
                policy=row["policy_status"],
                file=row["file_status"],
                next_action=row["next_action"],
            )
        )
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-packet-json", default=DEFAULT_EVIDENCE_PACKET_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
