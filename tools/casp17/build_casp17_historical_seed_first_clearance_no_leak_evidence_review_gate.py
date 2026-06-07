#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_EVIDENCE_PACKET_JSON = "casp17/casp17_historical_seed_first_clearance_no_leak_evidence_packet_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_historical_seed_first_clearance_no_leak_evidence_review_gate_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_historical_seed_first_clearance_no_leak_evidence_review_gate_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_HISTORICAL_SEED_FIRST_CLEARANCE_NO_LEAK_EVIDENCE_REVIEW_GATE.md"

ROW_COLUMNS = [
    "target_id",
    "benchmark_id",
    "field_name",
    "required_value_policy",
    "required_operator_value_format",
    "template_operator_value",
    "template_operator_evidence_ref",
    "template_operator_clearance",
    "template_operator_id",
    "evidence_stub_md",
    "stub_exists",
    "stub_evidence_ref",
    "stub_operator_value",
    "stub_operator_clearance",
    "stub_operator_id",
    "template_value_status",
    "template_evidence_ref_status",
    "template_clearance_status",
    "template_operator_id_status",
    "stub_status",
    "stub_evidence_status",
    "policy_status",
    "review_gate_status",
    "first_blocker",
    "next_action",
]

TRUE_VALUES = {"true", "yes", "y", "1"}
FALSE_VALUES = {"false", "no", "n", "0"}
CLEAR_VALUES = {"clear", "cleared", "no_leak_clear", "no_leak_cleared"}
OPERATOR_CLEAR_VALUES = {"operator_cleared", "cleared", "clear", "approved"}
ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

CLAIM_BOUNDARY = (
    "Local CASP17 first-clearance no-leak evidence review gate only. It validates whether the "
    "operator evidence packet template and field stubs have enough manually supplied evidence-shaped "
    "values for review. It does not copy values into the no-leak intake, approve provenance, compute "
    "CASP metrics, mutate evidence files, or submit to CASP."
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


def _policy_status(policy: str, value: str) -> str:
    lowered = value.lower()
    if not value:
        return "policy_not_checked_value_missing"
    if policy == "true":
        return "policy_pass" if lowered in TRUE_VALUES else "policy_fail_expected_true"
    if policy == "false":
        return "policy_pass" if lowered in FALSE_VALUES else "policy_fail_expected_false"
    if policy == "clear":
        return "policy_pass" if lowered in CLEAR_VALUES else "policy_fail_expected_clear"
    if policy == "operator_cleared":
        return "policy_pass" if lowered in OPERATOR_CLEAR_VALUES else "policy_fail_expected_operator_cleared"
    if policy in {"iso_date", "authoritative_release_iso_date"}:
        return "policy_pass" if ISO_DATE_PATTERN.match(value) else "policy_fail_expected_iso_date"
    return "policy_pass"


def _parse_stub(path_like: str | Path) -> dict[str, str]:
    path = _resolve(path_like)
    fields = {
        "evidence_ref": "",
        "operator_value": "",
        "operator_clearance": "",
        "operator_id": "",
    }
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
    return fields


def _next_action(row: dict[str, Any], statuses: list[str]) -> str:
    field_name = row["field_name"]
    first = statuses[0] if statuses else ""
    if first == "template_operator_value_missing":
        return f"fill operator_value for {field_name} in operator_evidence_template.csv"
    if first == "template_operator_evidence_ref_missing":
        return f"fill operator_evidence_ref for {field_name} in operator_evidence_template.csv"
    if first == "template_operator_clearance_missing":
        return f"fill operator_clearance for {field_name} in operator_evidence_template.csv"
    if first == "template_operator_id_missing":
        return f"fill operator_id for {field_name} in operator_evidence_template.csv"
    if first == "stub_missing":
        return f"restore evidence stub {row['evidence_stub_md']}"
    if first.startswith("stub_"):
        return f"fill {first.removeprefix('stub_').removesuffix('_missing')} in {row['evidence_stub_md']}"
    if first.startswith("policy_fail"):
        return f"revise operator_value for {field_name} to satisfy {row['required_value_policy']}"
    return f"review evidence for {field_name}, then copy accepted values into the no-leak intake"


def _review_row(packet_row: dict[str, Any], template_by_field: dict[str, dict[str, str]]) -> dict[str, Any]:
    field_name = _text(packet_row.get("field_name"))
    template = template_by_field.get(field_name, {})
    operator_value = _text(template.get("operator_value"))
    operator_evidence_ref = _text(template.get("operator_evidence_ref"))
    operator_clearance = _text(template.get("operator_clearance"))
    operator_id = _text(template.get("operator_id"))
    stub_path = _text(packet_row.get("evidence_stub_md") or template.get("evidence_stub_md"))
    stub_exists = _resolve(stub_path).is_file() if stub_path else False
    stub_fields = _parse_stub(stub_path)
    statuses = []
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
    stub_evidence_statuses = []
    for key, value in stub_fields.items():
        if not _text(value):
            stub_evidence_statuses.append(f"stub_{key}_missing")
    policy_status = _policy_status(_text(packet_row.get("required_value_policy")), operator_value)
    for status in [
        template_value_status,
        template_evidence_ref_status,
        template_clearance_status,
        template_operator_id_status,
        stub_status,
        *stub_evidence_statuses,
        policy_status,
    ]:
        if status not in {
            "template_operator_value_present",
            "template_operator_evidence_ref_present",
            "template_operator_clearance_present",
            "template_operator_id_present",
            "stub_present",
            "policy_pass",
        }:
            statuses.append(status)
    row = {
        "target_id": _text(packet_row.get("target_id")),
        "benchmark_id": _text(packet_row.get("benchmark_id")),
        "field_name": field_name,
        "required_value_policy": _text(packet_row.get("required_value_policy")),
        "required_operator_value_format": _text(packet_row.get("required_operator_value_format")),
        "template_operator_value": operator_value,
        "template_operator_evidence_ref": operator_evidence_ref,
        "template_operator_clearance": operator_clearance,
        "template_operator_id": operator_id,
        "evidence_stub_md": stub_path,
        "stub_exists": str(stub_exists).lower(),
        "stub_evidence_ref": _text(stub_fields.get("evidence_ref")),
        "stub_operator_value": _text(stub_fields.get("operator_value")),
        "stub_operator_clearance": _text(stub_fields.get("operator_clearance")),
        "stub_operator_id": _text(stub_fields.get("operator_id")),
        "template_value_status": template_value_status,
        "template_evidence_ref_status": template_evidence_ref_status,
        "template_clearance_status": template_clearance_status,
        "template_operator_id_status": template_operator_id_status,
        "stub_status": stub_status,
        "stub_evidence_status": ",".join(stub_evidence_statuses) if stub_evidence_statuses else "stub_evidence_present",
        "policy_status": policy_status,
        "review_gate_status": "ready_for_no_leak_gate_operator_fill" if not statuses else "awaiting_operator_evidence",
        "first_blocker": statuses[0] if statuses else "",
    }
    row["next_action"] = _next_action(row, statuses)
    return row


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    packet_path = _resolve(args.evidence_packet_json)
    packet_payload = _read_json(packet_path)
    packet_summary = _summary(packet_payload)
    packet_rows = _rows(packet_payload)
    template_csv = _text(packet_summary.get("operator_evidence_template_csv"))
    template_rows = _read_csv(template_csv)
    template_by_field = {_text(row.get("field_name")): row for row in template_rows}
    rows = [_review_row(row, template_by_field) for row in packet_rows]
    ready_rows = [row for row in rows if row["review_gate_status"] == "ready_for_no_leak_gate_operator_fill"]
    blocked_rows = [row for row in rows if row["review_gate_status"] != "ready_for_no_leak_gate_operator_fill"]
    first_blocked = blocked_rows[0] if blocked_rows else {}
    status = "first_clearance_no_leak_evidence_ready_for_operator_fill"
    if not packet_path.exists():
        status = "blocked_evidence_packet_missing"
    elif not packet_rows:
        status = "blocked_evidence_packet_rows_missing"
    elif not template_rows:
        status = "blocked_operator_evidence_template_missing"
    elif blocked_rows:
        status = "awaiting_first_clearance_no_leak_evidence_review"
    summary = {
        "packet_type": "casp17_historical_seed_first_clearance_no_leak_evidence_review_gate",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "first_clearance_no_leak_evidence_review_gate_status": status,
        "evidence_packet_json": _artifact(args.evidence_packet_json),
        "evidence_packet_status": _text(packet_summary.get("first_clearance_no_leak_evidence_packet_status")),
        "target_id": _text(packet_summary.get("target_id")),
        "benchmark_id": _text(packet_summary.get("benchmark_id")),
        "operator_evidence_template_csv": _artifact(template_csv),
        "packet_folder": _text(packet_summary.get("packet_folder")),
        "field_count": len(rows),
        "ready_field_count": len(ready_rows),
        "blocked_field_count": len(blocked_rows),
        "template_row_count": len(template_rows),
        "template_operator_value_missing_count": sum(
            1 for row in rows if row["template_value_status"] != "template_operator_value_present"
        ),
        "template_operator_evidence_ref_missing_count": sum(
            1 for row in rows if row["template_evidence_ref_status"] != "template_operator_evidence_ref_present"
        ),
        "template_operator_clearance_missing_count": sum(
            1 for row in rows if row["template_clearance_status"] != "template_operator_clearance_present"
        ),
        "template_operator_id_missing_count": sum(
            1 for row in rows if row["template_operator_id_status"] != "template_operator_id_present"
        ),
        "stub_present_count": sum(1 for row in rows if row["stub_status"] == "stub_present"),
        "stub_missing_count": sum(1 for row in rows if row["stub_status"] != "stub_present"),
        "stub_evidence_missing_count": sum(
            1 for row in rows if row["stub_evidence_status"] != "stub_evidence_present"
        ),
        "policy_pass_count": sum(1 for row in rows if row["policy_status"] == "policy_pass"),
        "policy_blocked_count": sum(1 for row in rows if row["policy_status"] != "policy_pass"),
        "first_blocked_field": _text(first_blocked.get("field_name")),
        "first_blocker": _text(first_blocked.get("first_blocker")),
        "next_action": (
            _text(first_blocked.get("next_action"))
            if blocked_rows
            else "copy accepted operator evidence into the no-leak intake, then rerun the no-leak gate"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Seed First Clearance No-Leak Evidence Review Gate",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['first_clearance_no_leak_evidence_review_gate_status']}`",
        f"- target/benchmark: `{summary['target_id']}` `{summary['benchmark_id']}`",
        f"- fields ready/blocked/total: `{summary['ready_field_count']}/{summary['blocked_field_count']}/{summary['field_count']}`",
        f"- template rows: `{summary['template_row_count']}`",
        f"- template missing value/evidence/clearance/operator: `{summary['template_operator_value_missing_count']}/{summary['template_operator_evidence_ref_missing_count']}/{summary['template_operator_clearance_missing_count']}/{summary['template_operator_id_missing_count']}`",
        f"- stubs present/missing/evidence-missing: `{summary['stub_present_count']}/{summary['stub_missing_count']}/{summary['stub_evidence_missing_count']}`",
        f"- policy pass/blocked: `{summary['policy_pass_count']}/{summary['policy_blocked_count']}`",
        f"- first blocked: `{summary['first_blocked_field'] or '-'}` `{summary['first_blocker'] or '-'}`",
        f"- template: `{summary['operator_evidence_template_csv']}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Fields",
        "",
        "| field | template value | template clearance | stub evidence | policy | gate | next action |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['field_name']}` | `{row['template_value_status']}` | "
            f"`{row['template_clearance_status']}` | `{row['stub_evidence_status']}` | "
            f"`{row['policy_status']}` | `{row['review_gate_status']}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | - | - | `blocked` | no evidence packet rows |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review the first clearance no-leak evidence packet.")
    parser.add_argument("--evidence-packet-json", default=DEFAULT_EVIDENCE_PACKET_JSON)
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
