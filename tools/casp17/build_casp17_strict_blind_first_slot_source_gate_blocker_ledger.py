#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_SOURCE_GATE_JSON = "casp17/casp17_strict_blind_internal_prediction_source_gate_current.json"
DEFAULT_FIELD_BOARD_JSON = "casp17/casp17_strict_blind_source_gate_field_board_current.json"
DEFAULT_OPERATOR_PACKET_JSON = "casp17/casp17_strict_blind_source_gate_operator_packet_current.json"
DEFAULT_EVIDENCE_REVIEW_GATE_JSON = "casp17/casp17_strict_blind_first_unlock_evidence_review_gate_current.json"
DEFAULT_OUT_DIR = "casp17/strict_blind_first_slot_source_gate_blocker_ledger"
DEFAULT_OUT_JSON = "casp17/casp17_strict_blind_first_slot_source_gate_blocker_ledger_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_strict_blind_first_slot_source_gate_blocker_ledger_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_STRICT_BLIND_FIRST_SLOT_SOURCE_GATE_BLOCKER_LEDGER.md"

CLAIM_BOUNDARY = (
    "Local CASP17 strict-blind first-slot source-gate blocker ledger only. It merges source-gate "
    "checks, field actions, operator packet state, and first-unlock evidence review state into one "
    "closure ledger. It does not fill operator values, copy prediction files, approve provenance, "
    "compute CASP metrics, push remotes, or submit to CASP."
)
LEDGER_RULE_ID = "strict_blind_first_slot_source_gate_blocker_ledger_v1"

ROW_COLUMNS = [
    "ledger_rank",
    "ledger_status",
    "field_key",
    "fill_kind",
    "priority_class",
    "affected_check_ids",
    "gate_blocked_check_count",
    "gate_pass_check_count",
    "gate_blockers",
    "current_value",
    "destination",
    "review_gate_status",
    "review_first_blocker",
    "template_value_status",
    "template_evidence_ref_status",
    "template_clearance_status",
    "template_operator_id_status",
    "stub_status",
    "stub_evidence_status",
    "policy_status",
    "file_status",
    "evidence_stub_md",
    "next_action",
    "blockers",
    "ledger_rule_id",
    "claim_boundary",
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    if not str(path_like).strip():
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
        return int(float(str(value).strip()))
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
    if rows is None:
        rows = payload.get("checks")
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


def _priority_class(field_key: str) -> str:
    if field_key == "source_id":
        return "01_source_identity"
    if field_key == "prediction_pdb":
        return "02_prediction_file"
    if field_key == "prediction_pdb_dropzone":
        return "03_prediction_dropzone_copy"
    if field_key in {"prediction_created_at", "native_release_date", "prediction_created_at/native_release_date"}:
        return "04_chronology"
    if field_key == "native_authority_ref":
        return "05_native_authority"
    if field_key in {"creation_evidence_ref", "no_leak_evidence_ref", "method_summary"}:
        return "06_provenance"
    if field_key == "operator_clearance":
        return "07_operator_clearance"
    return "99_review"


def _review_index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {_text(row.get("field_key")): row for row in _rows(payload) if _text(row.get("field_key"))}


def _row_blockers(field_row: dict[str, Any], review_row: dict[str, Any]) -> str:
    blockers = []
    gate_blockers = _text(field_row.get("blockers"))
    if gate_blockers:
        blockers.append(gate_blockers)
    for key in (
        "template_value_status",
        "template_clearance_status",
        "template_operator_id_status",
        "policy_status",
        "file_status",
    ):
        value = _text(review_row.get(key))
        if value and not value.endswith("_present") and value not in {
            "policy_pass",
            "file_not_required",
            "file_present_with_atom_records",
        }:
            blockers.append(value)
    stub = _text(review_row.get("stub_evidence_status"))
    if stub:
        blockers.append(stub)
    return ",".join(blockers)


def _build_rows(field_payload: dict[str, Any], review_payload: dict[str, Any]) -> list[dict[str, Any]]:
    review_by_field = _review_index(review_payload)
    rows: list[dict[str, Any]] = []
    for field_row in _rows(field_payload):
        field_key = _text(field_row.get("field_key"))
        review_row = review_by_field.get(field_key, {})
        blockers = _row_blockers(field_row, review_row)
        rows.append(
            {
                "ledger_rank": 0,
                "ledger_status": "blocked_source_gate_field" if blockers else "ready_source_gate_field",
                "field_key": field_key,
                "fill_kind": _text(field_row.get("fill_kind")),
                "priority_class": _priority_class(field_key),
                "affected_check_ids": _text(field_row.get("affected_check_ids")),
                "gate_blocked_check_count": _int(field_row.get("blocked_check_count")),
                "gate_pass_check_count": _int(field_row.get("pass_check_count")),
                "gate_blockers": _text(field_row.get("blockers")),
                "current_value": _text(field_row.get("current_value")),
                "destination": _text(field_row.get("destination")),
                "review_gate_status": _text(review_row.get("review_gate_status")),
                "review_first_blocker": _text(review_row.get("first_blocker")),
                "template_value_status": _text(review_row.get("template_value_status")),
                "template_evidence_ref_status": _text(review_row.get("template_evidence_ref_status")),
                "template_clearance_status": _text(review_row.get("template_clearance_status")),
                "template_operator_id_status": _text(review_row.get("template_operator_id_status")),
                "stub_status": _text(review_row.get("stub_status")),
                "stub_evidence_status": _text(review_row.get("stub_evidence_status")),
                "policy_status": _text(review_row.get("policy_status")),
                "file_status": _text(review_row.get("file_status")),
                "evidence_stub_md": _text(review_row.get("evidence_stub_md")),
                "next_action": _text(review_row.get("next_action")) or _text(field_row.get("next_action")),
                "blockers": blockers,
                "ledger_rule_id": LEDGER_RULE_ID,
                "claim_boundary": CLAIM_BOUNDARY,
            }
        )
    return sorted(rows, key=lambda row: (row["priority_class"], row["field_key"]))


def _write_field_packets(out_dir: str | Path, rows: list[dict[str, Any]]) -> None:
    base = _resolve(out_dir)
    for row in rows:
        target_dir = base / f"{int(row['ledger_rank']):02d}_{row['field_key'].replace('/', '_')}"
        target_dir.mkdir(parents=True, exist_ok=True)
        _write_csv(target_dir / "source_gate_blocker_row.csv", [row])
        lines = [
            f"# {row['field_key']} Source Gate Blocker",
            "",
            f"- ledger_rank: `{row['ledger_rank']}`",
            f"- status: `{row['ledger_status']}`",
            f"- priority_class: `{row['priority_class']}`",
            f"- affected_check_ids: `{row['affected_check_ids'] or '-'}`",
            f"- gate_blockers: `{row['gate_blockers'] or '-'}`",
            f"- review_first_blocker: `{row['review_first_blocker'] or '-'}`",
            f"- file_status: `{row['file_status'] or '-'}`",
            f"- evidence_stub_md: `{row['evidence_stub_md'] or '-'}`",
            f"- next_action: {row['next_action']}",
            "",
            "## Claim Boundary",
            "",
            CLAIM_BOUNDARY,
        ]
        (target_dir / "SOURCE_GATE_BLOCKER.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    source_gate_payload = _read_json(args.source_gate_json)
    field_payload = _read_json(args.field_board_json)
    operator_payload = _read_json(args.operator_packet_json)
    review_payload = _read_json(args.evidence_review_gate_json)
    source_summary = _summary(source_gate_payload)
    field_summary = _summary(field_payload)
    operator_summary = _summary(operator_payload)
    review_summary = _summary(review_payload)
    rows = _build_rows(field_payload, review_payload)
    for rank, row in enumerate(rows, start=1):
        row["ledger_rank"] = rank
    ready_rows = [row for row in rows if not row["blockers"]]
    first = next((row for row in rows if row["blockers"]), rows[0] if rows else {})
    summary = {
        "packet_type": "casp17_strict_blind_first_slot_source_gate_blocker_ledger",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "strict_blind_first_slot_source_gate_blocker_ledger_status": (
            "strict_blind_first_slot_source_gate_ready"
            if rows and len(ready_rows) == len(rows)
            else "awaiting_first_slot_source_gate_operator_evidence"
        ),
        "source_gate_json": _artifact(args.source_gate_json),
        "field_board_json": _artifact(args.field_board_json),
        "operator_packet_json": _artifact(args.operator_packet_json),
        "evidence_review_gate_json": _artifact(args.evidence_review_gate_json),
        "required_benchmark_id": _text(source_summary.get("required_benchmark_id"))
        or _text(field_summary.get("required_benchmark_id")),
        "required_target_id": _text(source_summary.get("required_target_id"))
        or _text(field_summary.get("required_target_id")),
        "required_scope": _text(source_summary.get("required_scope")) or _text(field_summary.get("required_scope")),
        "ledger_field_count": len(rows),
        "ready_field_count": len(ready_rows),
        "blocked_field_count": len(rows) - len(ready_rows),
        "source_gate_pass_count": _int(source_summary.get("pass_count")),
        "source_gate_blocked_count": _int(source_summary.get("blocked_count")),
        "source_gate_check_count": _int(source_summary.get("check_count")),
        "operator_ready_count": _int(operator_summary.get("operator_ready_count")),
        "operator_awaiting_count": _int(operator_summary.get("operator_awaiting_count")),
        "review_ready_field_count": _int(review_summary.get("ready_field_count")),
        "review_blocked_field_count": _int(review_summary.get("blocked_field_count")),
        "template_operator_value_missing_count": _int(review_summary.get("template_operator_value_missing_count")),
        "template_operator_clearance_missing_count": _int(
            review_summary.get("template_operator_clearance_missing_count")
        ),
        "template_operator_id_missing_count": _int(review_summary.get("template_operator_id_missing_count")),
        "stub_present_count": _int(review_summary.get("stub_present_count")),
        "stub_evidence_missing_count": _int(review_summary.get("stub_evidence_missing_count")),
        "file_ready_count": _int(review_summary.get("file_ready_count")),
        "file_blocked_count": _int(review_summary.get("file_blocked_count")),
        "manifest_value_field_count": sum(1 for row in rows if row["fill_kind"] == "manifest_value"),
        "file_field_count": sum(1 for row in rows if row["fill_kind"] == "file"),
        "first_blocked_field": _text(first.get("field_key")),
        "first_blocker": _text(first.get("review_first_blocker")) or _text(source_summary.get("first_blocker")),
        "first_next_action": _text(first.get("next_action")) or _text(source_summary.get("first_next_action")),
        "ledger_rule_id": LEDGER_RULE_ID,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Strict-Blind First Slot Source Gate Blocker Ledger",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['strict_blind_first_slot_source_gate_blocker_ledger_status']}`",
        f"- required: `{summary['required_benchmark_id']}` `{summary['required_target_id']}` `{summary['required_scope']}`",
        f"- fields ready/blocked/total: `{summary['ready_field_count']}/{summary['blocked_field_count']}/{summary['ledger_field_count']}`",
        f"- source gate pass/blocked/total: `{summary['source_gate_pass_count']}/{summary['source_gate_blocked_count']}/{summary['source_gate_check_count']}`",
        f"- operator ready/awaiting: `{summary['operator_ready_count']}/{summary['operator_awaiting_count']}`",
        f"- review ready/blocked: `{summary['review_ready_field_count']}/{summary['review_blocked_field_count']}`",
        f"- template missing value/clearance/id: `{summary['template_operator_value_missing_count']}/{summary['template_operator_clearance_missing_count']}/{summary['template_operator_id_missing_count']}`",
        f"- stub present/missing: `{summary['stub_present_count']}/{summary['stub_evidence_missing_count']}`",
        f"- file ready/blocked: `{summary['file_ready_count']}/{summary['file_blocked_count']}`",
        f"- first blocked: `{summary['first_blocked_field'] or '-'}` `{summary['first_blocker'] or '-'}`",
        f"- next action: {summary['first_next_action']}",
        "",
        "## Ledger",
        "",
        "| rank | field | priority | gate blockers | review blocker | file | next action |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['ledger_rank']}` | `{row['field_key']}` | `{row['priority_class']}` | "
            f"`{row['gate_blockers'] or '-'}` | `{row['review_first_blocker'] or '-'}` | "
            f"`{row['file_status'] or '-'}` | {row['next_action']} |"
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_field_packets(args.out_dir, payload["rows"])
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 first-slot source-gate blocker ledger.")
    parser.add_argument("--source-gate-json", default=DEFAULT_SOURCE_GATE_JSON)
    parser.add_argument("--field-board-json", default=DEFAULT_FIELD_BOARD_JSON)
    parser.add_argument("--operator-packet-json", default=DEFAULT_OPERATOR_PACKET_JSON)
    parser.add_argument("--evidence-review-gate-json", default=DEFAULT_EVIDENCE_REVIEW_GATE_JSON)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)
    print(
        json.dumps(
            {
                "status": payload["summary"]["strict_blind_first_slot_source_gate_blocker_ledger_status"],
                "fields": payload["summary"]["ledger_field_count"],
                "ready": payload["summary"]["ready_field_count"],
                "blocked": payload["summary"]["blocked_field_count"],
                "first": payload["summary"]["first_blocked_field"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
