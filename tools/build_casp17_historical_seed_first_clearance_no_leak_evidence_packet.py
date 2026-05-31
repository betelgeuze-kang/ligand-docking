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

DEFAULT_NO_LEAK_GATE_JSON = "casp17/casp17_historical_seed_first_clearance_no_leak_gate_current.json"
DEFAULT_PACKET_ROOT = "casp17/historical_seed_first_clearance_no_leak_evidence_packet"
DEFAULT_OUT_JSON = "casp17/casp17_historical_seed_first_clearance_no_leak_evidence_packet_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_historical_seed_first_clearance_no_leak_evidence_packet_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_HISTORICAL_SEED_FIRST_CLEARANCE_NO_LEAK_EVIDENCE_PACKET.md"

ROW_COLUMNS = [
    "target_id",
    "benchmark_id",
    "field_name",
    "required_value_policy",
    "field_gate_status",
    "first_blocker",
    "operator_value_status",
    "operator_clearance_status",
    "policy_status",
    "evidence_request_kind",
    "required_operator_value_format",
    "accepted_value_examples",
    "unacceptable_sources",
    "weak_local_hint",
    "weak_local_hint_source",
    "intake_csv",
    "packet_folder",
    "evidence_stub_md",
    "packet_status",
    "next_action",
]

CLAIM_BOUNDARY = (
    "Local CASP17 first-clearance no-leak evidence packet only. It creates operator-facing "
    "evidence stubs, a template, and an action file for the first historical seed no-leak gate. "
    "It does not fill operator values, approve no-leak provenance, compute CASP metrics, mutate "
    "the intake CSV, or submit to CASP."
)

FIELD_GUIDANCE = {
    "no_leak_evidence_ref": {
        "kind": "independent_no_leak_evidence",
        "format": "path-or-uri for an independent no-leak provenance dossier",
        "examples": "internal run ledger; archived job record; signed lab notebook; immutable timestamp evidence",
        "reject": "local path name only; file mtime only; memory-only assertion",
    },
    "leakage_clearance": {
        "kind": "no_leak_clearance_decision",
        "format": "clear",
        "examples": "clear after evidence review and negative controls",
        "reject": "unclear; pass; unchecked; local timestamp only",
    },
    "operator_clearance": {
        "kind": "operator_signoff",
        "format": "operator_cleared",
        "examples": "operator_cleared with evidence reference and operator id",
        "reject": "blank; auto; implied by script output",
    },
    "operator": {
        "kind": "operator_identity",
        "format": "stable operator id or initials",
        "examples": "operator handle tied to the clearance record",
        "reject": "anonymous; script; system",
    },
    "prediction_created_at": {
        "kind": "authoritative_prediction_creation_date",
        "format": "YYYY-MM-DD",
        "examples": "pre-native job ledger date; archived filesystem snapshot date; signed run manifest date",
        "reject": "current file mtime; copied folder date without source evidence",
    },
    "native_release_date": {
        "kind": "authoritative_native_release_date",
        "format": "YYYY-MM-DD",
        "examples": "RCSB release date; journal/source release date; official structure archive date",
        "reject": "download date; local file mtime",
    },
    "prediction_generated_before_native_release": {
        "kind": "chronology_comparison",
        "format": "true",
        "examples": "true with prediction_created_at earlier than authoritative native_release_date",
        "reject": "true without dates; post-native prediction",
    },
    "public_template_or_native_used_for_prediction": {
        "kind": "negative_control_public_template",
        "format": "false",
        "examples": "false with method/run evidence showing no native/template use",
        "reject": "unknown; not checked",
    },
    "other_team_model_used": {
        "kind": "negative_control_other_team_model",
        "format": "false",
        "examples": "false with no external team model input in run manifest",
        "reject": "unknown; external model pool used",
    },
    "post_release_information_used": {
        "kind": "negative_control_post_release_information",
        "format": "false",
        "examples": "false with pre-native run evidence and no post-release sources",
        "reject": "unknown; post-release evidence leakage",
    },
}


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


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], columns: list[str] = ROW_COLUMNS) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip()).strip("._")
    return slug.lower() or "field"


def _target_packet_folder(packet_root: str | Path, target_id: str) -> Path:
    return _resolve(packet_root) / _slug(target_id or "unknown_target")


def _packet_status(row: dict[str, Any]) -> str:
    if _text(row.get("field_gate_status")) == "ready_for_no_leak_review":
        return "evidence_ready_for_operator_review"
    return "awaiting_operator_evidence"


def _guidance(field_name: str, policy: str) -> dict[str, str]:
    if field_name in FIELD_GUIDANCE:
        return FIELD_GUIDANCE[field_name]
    return {
        "kind": "operator_field_evidence",
        "format": policy or "non-empty operator value",
        "examples": "operator supplied evidence reference and clearance",
        "reject": "blank; auto-filled; local timestamp only",
    }


def _packet_row(row: dict[str, Any], summary: dict[str, Any], packet_folder: Path) -> dict[str, Any]:
    field_name = _text(row.get("field_name"))
    policy = _text(row.get("required_value_policy"))
    guidance = _guidance(field_name, policy)
    evidence_stub = packet_folder / "field_evidence" / f"{_slug(field_name)}.md"
    return {
        "target_id": _text(summary.get("target_id")),
        "benchmark_id": _text(summary.get("benchmark_id")),
        "field_name": field_name,
        "required_value_policy": policy,
        "field_gate_status": _text(row.get("field_gate_status")),
        "first_blocker": _text(row.get("first_blocker")),
        "operator_value_status": _text(row.get("value_status")),
        "operator_clearance_status": _text(row.get("clearance_status")),
        "policy_status": _text(row.get("policy_status")),
        "evidence_request_kind": guidance["kind"],
        "required_operator_value_format": guidance["format"],
        "accepted_value_examples": guidance["examples"],
        "unacceptable_sources": guidance["reject"],
        "weak_local_hint": _text(row.get("weak_local_hint")),
        "weak_local_hint_source": _text(row.get("weak_local_hint_source")),
        "intake_csv": _text(summary.get("no_leak_operator_intake_csv")),
        "packet_folder": _artifact(packet_folder),
        "evidence_stub_md": _artifact(evidence_stub),
        "packet_status": _packet_status(row),
        "next_action": (
            f"collect evidence in {_artifact(evidence_stub)}, then fill operator_value and operator_clearance "
            f"for {field_name} in the no-leak intake"
            if _packet_status(row) != "evidence_ready_for_operator_review"
            else f"review accepted evidence for {field_name} before promotion"
        ),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    gate_path = _resolve(args.no_leak_gate_json)
    gate_payload = _read_json(gate_path)
    gate_summary = _summary(gate_payload)
    gate_rows = _rows(gate_payload)
    target_id = _text(gate_summary.get("target_id"))
    packet_folder = _target_packet_folder(args.packet_root, target_id)
    rows = [_packet_row(row, gate_summary, packet_folder) for row in gate_rows]
    open_rows = [row for row in rows if row["packet_status"] != "evidence_ready_for_operator_review"]
    ready_rows = [row for row in rows if row["packet_status"] == "evidence_ready_for_operator_review"]
    first_open = open_rows[0] if open_rows else {}
    status = "first_clearance_no_leak_evidence_packet_ready_for_review"
    if not gate_path.exists():
        status = "blocked_no_leak_gate_missing"
    elif not gate_rows:
        status = "blocked_no_leak_gate_rows_missing"
    elif open_rows:
        status = "awaiting_first_clearance_no_leak_evidence_collection"
    summary = {
        "packet_type": "casp17_historical_seed_first_clearance_no_leak_evidence_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "first_clearance_no_leak_evidence_packet_status": status,
        "no_leak_gate_json": _artifact(args.no_leak_gate_json),
        "no_leak_gate_status": _text(gate_summary.get("first_clearance_no_leak_gate_status")),
        "target_id": target_id,
        "benchmark_id": _text(gate_summary.get("benchmark_id")),
        "packet_folder": _artifact(packet_folder),
        "action_md": _artifact(packet_folder / "ACTION.md"),
        "operator_evidence_template_csv": _artifact(packet_folder / "operator_evidence_template.csv"),
        "dropzone_manifest_csv": _artifact(packet_folder / "dropzone_manifest.csv"),
        "no_leak_operator_intake_csv": _text(gate_summary.get("no_leak_operator_intake_csv")),
        "field_count": len(rows),
        "open_field_count": len(open_rows),
        "ready_field_count": len(ready_rows),
        "evidence_stub_count": len(rows),
        "weak_hint_count": sum(1 for row in rows if _text(row.get("weak_local_hint"))),
        "first_open_field": _text(first_open.get("field_name")),
        "first_open_kind": _text(first_open.get("evidence_request_kind")),
        "first_blocker": _text(first_open.get("first_blocker")),
        "next_action": (
            f"collect evidence for {first_open.get('field_name')} in {first_open.get('evidence_stub_md')}"
            if open_rows
            else "review packet evidence and no-leak gate output before promotion"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_action_md(packet_folder: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        f"# First Clearance No-Leak Evidence Packet: {summary['target_id'] or 'UNKNOWN'}",
        "",
        f"- status: `{summary['first_clearance_no_leak_evidence_packet_status']}`",
        f"- benchmark: `{summary['benchmark_id'] or '-'}`",
        f"- gate: `{summary['no_leak_gate_status'] or '-'}`",
        f"- fields ready/open/total: `{summary['ready_field_count']}/{summary['open_field_count']}/{summary['field_count']}`",
        f"- weak hints: `{summary['weak_hint_count']}`",
        f"- operator intake: `{summary['no_leak_operator_intake_csv'] or '-'}`",
        f"- template: `{summary['operator_evidence_template_csv']}`",
        f"- first open: `{summary['first_open_field'] or '-'}` `{summary['first_open_kind'] or '-'}` `{summary['first_blocker'] or '-'}`",
        "",
        "## Operator Step",
        "",
        "Fill the evidence stubs first, then copy only independently supported values into the no-leak intake.",
        "Weak local hints are review aids only and are not clearance authority.",
        "",
        "## Field Evidence Stubs",
        "",
    ]
    for row in payload["rows"]:
        lines.append(
            f"- `{row['field_name']}`: `{row['evidence_request_kind']}` -> `{row['evidence_stub_md']}`"
        )
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    packet_folder.mkdir(parents=True, exist_ok=True)
    (packet_folder / "ACTION.md").write_text("\n".join(lines), encoding="utf-8")


def _write_stub_md(path: Path, row: dict[str, Any]) -> None:
    lines = [
        f"# Evidence Stub: {row['field_name']}",
        "",
        f"- target: `{row['target_id']}`",
        f"- benchmark: `{row['benchmark_id']}`",
        f"- field: `{row['field_name']}`",
        f"- policy: `{row['required_value_policy']}`",
        f"- request kind: `{row['evidence_request_kind']}`",
        f"- required operator value format: `{row['required_operator_value_format']}`",
        f"- accepted examples: {row['accepted_value_examples']}",
        f"- unacceptable sources: {row['unacceptable_sources']}",
        f"- weak local hint: `{row['weak_local_hint'] or '-'}`",
        f"- weak local hint source: `{row['weak_local_hint_source'] or '-'}`",
        "",
        "## Operator Evidence",
        "",
        "- evidence_ref:",
        "- operator_value:",
        "- operator_clearance:",
        "- operator_id:",
        "- notes:",
        "",
        "Do not treat this stub as clearance until the operator evidence fields above are filled.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_packet_files(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    if not payload["rows"]:
        return
    packet_folder = _resolve(summary["packet_folder"])
    _write_action_md(packet_folder, payload)
    template_columns = [
        "field_name",
        "operator_value",
        "operator_evidence_ref",
        "operator_clearance",
        "operator_id",
        "required_operator_value_format",
        "evidence_stub_md",
        "notes",
    ]
    template_rows = [
        {
            "field_name": row["field_name"],
            "operator_value": "",
            "operator_evidence_ref": row["evidence_stub_md"],
            "operator_clearance": "",
            "operator_id": "",
            "required_operator_value_format": row["required_operator_value_format"],
            "evidence_stub_md": row["evidence_stub_md"],
            "notes": "Fill manually from independent evidence; do not auto-fill from weak local hints.",
        }
        for row in payload["rows"]
    ]
    _write_csv(packet_folder / "operator_evidence_template.csv", template_rows, template_columns)
    _write_csv(packet_folder / "dropzone_manifest.csv", payload["rows"])
    for row in payload["rows"]:
        _write_stub_md(_resolve(row["evidence_stub_md"]), row)


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Seed First Clearance No-Leak Evidence Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['first_clearance_no_leak_evidence_packet_status']}`",
        f"- target/benchmark: `{summary['target_id']}` `{summary['benchmark_id']}`",
        f"- fields ready/open/total: `{summary['ready_field_count']}/{summary['open_field_count']}/{summary['field_count']}`",
        f"- evidence stubs: `{summary['evidence_stub_count']}`",
        f"- weak hints: `{summary['weak_hint_count']}`",
        f"- first open: `{summary['first_open_field'] or '-'}` `{summary['first_open_kind'] or '-'}` `{summary['first_blocker'] or '-'}`",
        f"- packet folder: `{summary['packet_folder']}`",
        f"- action: `{summary['action_md']}`",
        f"- template: `{summary['operator_evidence_template_csv']}`",
        f"- intake: `{summary['no_leak_operator_intake_csv'] or '-'}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Evidence Requests",
        "",
        "| field | request kind | value format | weak hint | status | next action |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['field_name']}` | `{row['evidence_request_kind']}` | "
            f"`{row['required_operator_value_format']}` | `{row['weak_local_hint'] or '-'}` | "
            f"`{row['packet_status']}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | - | `blocked` | no no-leak gate rows |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)
    _write_packet_files(args, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the first clearance no-leak evidence collection packet."
    )
    parser.add_argument("--no-leak-gate-json", default=DEFAULT_NO_LEAK_GATE_JSON)
    parser.add_argument("--packet-root", default=DEFAULT_PACKET_ROOT)
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
