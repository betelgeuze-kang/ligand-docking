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

DEFAULT_FIRST_CLEARANCE_KIT_JSON = "casp17/casp17_historical_seed_first_clearance_operator_kit_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_historical_seed_first_clearance_no_leak_gate_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_historical_seed_first_clearance_no_leak_gate_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_HISTORICAL_SEED_FIRST_CLEARANCE_NO_LEAK_GATE.md"

ROW_COLUMNS = [
    "target_id",
    "benchmark_id",
    "field_name",
    "required_value_policy",
    "current_value",
    "weak_local_hint",
    "weak_local_hint_source",
    "evidence_ref",
    "operator_value",
    "operator_clearance",
    "value_status",
    "clearance_status",
    "policy_status",
    "field_gate_status",
    "first_blocker",
    "next_action",
]

TRUE_VALUES = {"true", "yes", "y", "1"}
FALSE_VALUES = {"false", "no", "n", "0"}
CLEAR_VALUES = {"clear", "cleared", "no_leak_clear", "no_leak_cleared"}
OPERATOR_CLEAR_VALUES = {"operator_cleared", "cleared", "clear", "approved"}
ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

CLAIM_BOUNDARY = (
    "Local CASP17 first-clearance no-leak gate only. It validates whether the manual no-leak "
    "operator intake for the shortest-path historical seed has operator values, clearances, and "
    "policy-shaped entries. It does not fill values, approve evidence, mutate clearance CSVs, "
    "compute CASP metrics, or submit to CASP."
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
    if policy in {"operator_id", "independent_no_leak_evidence_ref_required", "operator_required"}:
        return "policy_pass"
    return "policy_pass"


def _next_action(field_name: str, value_status: str, clearance_status: str, policy_status: str) -> str:
    if value_status != "operator_value_present":
        return f"fill operator_value for {field_name}"
    if clearance_status != "operator_clearance_present":
        return f"fill operator_clearance for {field_name}"
    if policy_status != "policy_pass":
        return f"revise operator_value for {field_name} to satisfy {policy_status}"
    return "field ready for no-leak promotion review"


def _gate_row(row: dict[str, str], summary: dict[str, Any]) -> dict[str, Any]:
    field_name = _text(row.get("field_name"))
    operator_value = _text(row.get("operator_value"))
    operator_clearance = _text(row.get("operator_clearance"))
    value_status = "operator_value_present" if operator_value else "operator_value_missing"
    clearance_status = "operator_clearance_present" if operator_clearance else "operator_clearance_missing"
    policy_status = _policy_status(_text(row.get("required_value_policy")), operator_value)
    blockers = [
        status
        for status in [value_status, clearance_status, policy_status]
        if status not in {"operator_value_present", "operator_clearance_present", "policy_pass"}
    ]
    return {
        "target_id": _text(summary.get("target_id")),
        "benchmark_id": _text(summary.get("benchmark_id")),
        "field_name": field_name,
        "required_value_policy": _text(row.get("required_value_policy")),
        "current_value": _text(row.get("current_value")),
        "weak_local_hint": _text(row.get("weak_local_hint")),
        "weak_local_hint_source": _text(row.get("weak_local_hint_source")),
        "evidence_ref": _text(row.get("evidence_ref")),
        "operator_value": operator_value,
        "operator_clearance": operator_clearance,
        "value_status": value_status,
        "clearance_status": clearance_status,
        "policy_status": policy_status,
        "field_gate_status": "ready_for_no_leak_review" if not blockers else "awaiting_operator_input",
        "first_blocker": blockers[0] if blockers else "",
        "next_action": _next_action(field_name, value_status, clearance_status, policy_status),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    kit_path = _resolve(args.first_clearance_kit_json)
    kit_payload = _read_json(kit_path)
    kit_summary = _summary(kit_payload)
    intake_csv = _text(kit_summary.get("no_leak_operator_intake_csv"))
    intake_rows = _read_csv(intake_csv)
    rows = [_gate_row(row, kit_summary) for row in intake_rows]
    ready_rows = [row for row in rows if row["field_gate_status"] == "ready_for_no_leak_review"]
    blocked_rows = [row for row in rows if row["field_gate_status"] != "ready_for_no_leak_review"]
    first_blocked = blocked_rows[0] if blocked_rows else {}
    status = "first_clearance_no_leak_ready_for_promotion_review"
    if not kit_path.exists():
        status = "blocked_first_clearance_kit_missing"
    elif _text(kit_summary.get("first_clearance_kit_status")) != "operator_no_leak_intake_ready":
        status = "blocked_first_clearance_kit_not_ready"
    elif not intake_rows:
        status = "blocked_no_leak_intake_missing"
    elif blocked_rows:
        status = "awaiting_operator_no_leak_values"
    summary = {
        "packet_type": "casp17_historical_seed_first_clearance_no_leak_gate",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "first_clearance_no_leak_gate_status": status,
        "first_clearance_kit_json": _artifact(args.first_clearance_kit_json),
        "first_clearance_kit_status": _text(kit_summary.get("first_clearance_kit_status")),
        "target_id": _text(kit_summary.get("target_id")),
        "benchmark_id": _text(kit_summary.get("benchmark_id")),
        "no_leak_operator_intake_csv": _artifact(intake_csv),
        "promotion_preview_csv": _artifact(kit_summary.get("promotion_preview_csv")),
        "field_count": len(rows),
        "ready_field_count": len(ready_rows),
        "blocked_field_count": len(blocked_rows),
        "operator_value_present_count": sum(1 for row in rows if row["value_status"] == "operator_value_present"),
        "operator_value_missing_count": sum(1 for row in rows if row["value_status"] != "operator_value_present"),
        "operator_clearance_present_count": sum(
            1 for row in rows if row["clearance_status"] == "operator_clearance_present"
        ),
        "operator_clearance_missing_count": sum(
            1 for row in rows if row["clearance_status"] != "operator_clearance_present"
        ),
        "policy_pass_count": sum(1 for row in rows if row["policy_status"] == "policy_pass"),
        "policy_blocked_count": sum(1 for row in rows if row["policy_status"] != "policy_pass"),
        "weak_hint_count": sum(1 for row in rows if _text(row.get("weak_local_hint"))),
        "evidence_ref_count": sum(1 for row in rows if _text(row.get("evidence_ref"))),
        "first_blocked_field": _text(first_blocked.get("field_name")),
        "first_blocker": _text(first_blocked.get("first_blocker")),
        "next_action": (
            "fill all operator_value and operator_clearance cells in the no-leak intake with independent "
            "evidence-shaped values before reviewing the promotion preview"
            if blocked_rows
            else "review promotion_preview.csv, then sync only after operator no-leak clearance is accepted"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Seed First Clearance No-Leak Gate",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['first_clearance_no_leak_gate_status']}`",
        f"- target/benchmark: `{summary['target_id']}` `{summary['benchmark_id']}`",
        f"- fields ready/blocked/total: `{summary['ready_field_count']}/{summary['blocked_field_count']}/{summary['field_count']}`",
        f"- operator value present/missing: `{summary['operator_value_present_count']}/{summary['operator_value_missing_count']}`",
        f"- operator clearance present/missing: `{summary['operator_clearance_present_count']}/{summary['operator_clearance_missing_count']}`",
        f"- policy pass/blocked: `{summary['policy_pass_count']}/{summary['policy_blocked_count']}`",
        f"- weak hints/evidence refs: `{summary['weak_hint_count']}/{summary['evidence_ref_count']}`",
        f"- first blocked: `{summary['first_blocked_field'] or '-'}` `{summary['first_blocker'] or '-'}`",
        f"- intake: `{summary['no_leak_operator_intake_csv']}`",
        f"- promotion preview: `{summary['promotion_preview_csv']}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Fields",
        "",
        "| field | policy | value | clearance | policy status | gate | next action |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['field_name']}` | `{row['required_value_policy']}` | `{row['value_status']}` | "
            f"`{row['clearance_status']}` | `{row['policy_status']}` | `{row['field_gate_status']}` | "
            f"{row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | - | - | `blocked` | no no-leak intake rows |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the first clearance no-leak operator intake.")
    parser.add_argument("--first-clearance-kit-json", default=DEFAULT_FIRST_CLEARANCE_KIT_JSON)
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
