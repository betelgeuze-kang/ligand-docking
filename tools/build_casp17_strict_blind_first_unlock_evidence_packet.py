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

DEFAULT_FIRST_UNLOCK_HANDOFF_JSON = "casp17/casp17_strict_blind_first_unlock_handoff_current.json"
DEFAULT_PACKET_ROOT = "casp17/strict_blind_first_unlock_evidence_packet"
DEFAULT_OUT_JSON = "casp17/casp17_strict_blind_first_unlock_evidence_packet_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_strict_blind_first_unlock_evidence_packet_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_STRICT_BLIND_FIRST_UNLOCK_EVIDENCE_PACKET.md"

ROW_COLUMNS = [
    "field_order",
    "field_key",
    "fill_kind",
    "operator_status",
    "required_evidence_kind",
    "required_operator_value_format",
    "accepted_evidence_examples",
    "rejected_sources",
    "destination",
    "operator_template_csv",
    "evidence_stub_md",
    "packet_status",
    "blocker",
    "next_action",
]

TEMPLATE_COLUMNS = [
    "field_key",
    "operator_value",
    "operator_evidence_ref",
    "operator_clearance",
    "operator_id",
    "required_operator_value_format",
    "evidence_stub_md",
    "destination",
    "notes",
]

DROPZONE_COLUMNS = [
    "field_key",
    "dropzone_kind",
    "expected_path_or_destination",
    "evidence_stub_md",
    "dropzone_status",
    "next_action",
]

CLAIM_BOUNDARY = (
    "Local CASP17 strict-blind first-unlock evidence packet only. It creates operator-facing "
    "evidence stubs and templates for the first source-request handoff. It does not fill operator "
    "values, copy prediction files, approve provenance, compute CASP metrics, push remotes, or submit to CASP."
)

READY_STATUSES = {
    "field_ready_for_fulfillment_gate",
    "operator_value_present",
    "file_present",
    "file_ready",
    "derived_date_order_ready",
}

FIELD_GUIDANCE = {
    "source_id": {
        "kind": "internal_source_identifier",
        "format": "internal source id; must not start official_archive/casp_official/massivefold_external",
        "examples": "internal run ledger id tied to a pre-native prediction package",
        "reject": "official CASP archive; MassiveFold external pool; other-team model id; blank local nickname",
    },
    "prediction_pdb": {
        "kind": "pre_native_prediction_pdb",
        "format": "local pre-native prediction PDB path with ATOM/HETATM records",
        "examples": "archived internal prediction PDB plus independent creation timestamp evidence",
        "reject": "post-native prediction; native PDB; official archive model; file without atom records",
    },
    "prediction_pdb_dropzone": {
        "kind": "verified_prediction_dropzone_copy",
        "format": "first-slot prediction dropzone PDB copy path",
        "examples": "copy of the verified internal prediction PDB into the first-slot dropzone",
        "reject": "path exists but differs from verified source; symlink to external pool; empty placeholder",
    },
    "prediction_created_at": {
        "kind": "authoritative_prediction_creation_date",
        "format": "YYYY-MM-DD prediction creation date",
        "examples": "immutable job ledger; archived run manifest; signed lab notebook entry",
        "reject": "current file mtime only; copied folder date; after-native date",
    },
    "native_release_date": {
        "kind": "authoritative_native_release_date",
        "format": "YYYY-MM-DD authoritative native release date",
        "examples": "RCSB release date; official structure archive release; source publication record",
        "reject": "download date; local file mtime; unreferenced memory",
    },
    "prediction_created_at/native_release_date": {
        "kind": "chronology_comparison",
        "format": "derived: prediction_created_at < native_release_date",
        "examples": "explicit date comparison using independently evidenced dates",
        "reject": "true without source dates; post-native prediction; current CASP target leakage",
    },
    "native_authority_ref": {
        "kind": "native_authority_reference",
        "format": "artifact path or URI for authoritative native source",
        "examples": "RCSB accession plus release-date evidence; official archive native manifest",
        "reject": "unverified local native file; generated reference without authority",
    },
    "creation_evidence_ref": {
        "kind": "prediction_timestamp_evidence",
        "format": "artifact path or URI for independent prediction timestamp evidence",
        "examples": "immutable run manifest; lab notebook; archived CI/job metadata",
        "reject": "mtime only; generated markdown after the fact; operator memory only",
    },
    "no_leak_evidence_ref": {
        "kind": "no_leak_provenance_evidence",
        "format": "artifact path or URI for no-leak provenance evidence",
        "examples": "run input manifest proving no native/templates/other-team models; negative controls",
        "reject": "local filename only; broad assertion; unknown template policy",
    },
    "method_summary": {
        "kind": "method_source_summary",
        "format": "short internal prediction method/source summary",
        "examples": "method, inputs, data cutoff, and exclusion policy linked to source evidence",
        "reject": "vague one-word method; external-pool rerank without explicit policy",
    },
    "operator_clearance": {
        "kind": "operator_signoff",
        "format": "approved/clear/cleared/true/yes/operator_clear/operator_approved",
        "examples": "operator-approved after checking source, chronology, and no-leak dossier",
        "reject": "auto; blank; implied by script output",
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


def _int(value: Any) -> int:
    try:
        return int(float(_text(value)))
    except (TypeError, ValueError):
        return 0


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip()).strip("._")
    return slug.lower() or "field"


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


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _packet_folder(packet_root: str | Path, summary: dict[str, Any]) -> Path:
    request = _slug(_text(summary.get("request_id")) or "source_request")
    target = _slug(_text(summary.get("candidate_target_id")) or "target")
    return _resolve(packet_root) / f"{request}_{target}"


def _row_ready(row: dict[str, Any]) -> bool:
    return _text(row.get("fill_status")) in READY_STATUSES or _text(row.get("operator_status")) in READY_STATUSES


def _guidance(field_key: str, required_format: str) -> dict[str, str]:
    if field_key in FIELD_GUIDANCE:
        return FIELD_GUIDANCE[field_key]
    return {
        "kind": "operator_field_evidence",
        "format": required_format or "non-empty operator value with evidence reference",
        "examples": "operator supplied value plus evidence reference",
        "reject": "blank; auto-filled; local mtime only",
    }


def _packet_row(row: dict[str, Any], packet_folder: Path) -> dict[str, Any]:
    field_key = _text(row.get("field_key"))
    guidance = _guidance(field_key, _text(row.get("required_format")))
    evidence_stub = packet_folder / "field_evidence" / f"{_slug(field_key)}.md"
    ready = _row_ready(row)
    return {
        "field_order": _int(row.get("field_order")),
        "field_key": field_key,
        "fill_kind": _text(row.get("fill_kind")),
        "operator_status": _text(row.get("operator_status")),
        "required_evidence_kind": guidance["kind"],
        "required_operator_value_format": guidance["format"],
        "accepted_evidence_examples": guidance["examples"],
        "rejected_sources": guidance["reject"],
        "destination": _artifact(row.get("destination")),
        "operator_template_csv": _artifact(row.get("operator_template_csv")),
        "evidence_stub_md": _artifact(evidence_stub),
        "packet_status": "evidence_ready_for_operator_review" if ready else "awaiting_operator_evidence",
        "blocker": "" if ready else (_text(row.get("blocker")) or _text(row.get("operator_status"))),
        "next_action": (
            f"review accepted evidence for {field_key} before source-gate promotion"
            if ready
            else f"collect evidence in {_artifact(evidence_stub)}, then fill operator_value and operator_evidence_ref for {field_key}"
        ),
    }


def _status(input_missing: bool, handoff_rows: list[dict[str, Any]], packet_rows: list[dict[str, Any]]) -> str:
    if input_missing:
        return "blocked_first_unlock_handoff_missing"
    if not handoff_rows:
        return "blocked_first_unlock_handoff_rows_missing"
    if packet_rows and all(row["packet_status"] == "evidence_ready_for_operator_review" for row in packet_rows):
        return "first_unlock_evidence_packet_ready_for_source_gate_review"
    return "awaiting_first_unlock_evidence_collection"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    handoff_path = _resolve(args.first_unlock_handoff_json)
    handoff_payload = _read_json(handoff_path)
    handoff_summary = _summary(handoff_payload)
    handoff_rows = _rows(handoff_payload)
    packet_folder = _packet_folder(args.packet_root, handoff_summary)
    rows = [_packet_row(row, packet_folder) for row in handoff_rows]
    open_rows = [row for row in rows if row["packet_status"] != "evidence_ready_for_operator_review"]
    ready_rows = [row for row in rows if row["packet_status"] == "evidence_ready_for_operator_review"]
    first_open = open_rows[0] if open_rows else {}
    file_rows = [
        row
        for row in rows
        if row["fill_kind"] == "file" or row["field_key"] in {"prediction_pdb", "prediction_pdb_dropzone"}
    ]
    summary = {
        "packet_type": "casp17_strict_blind_first_unlock_evidence_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "first_unlock_evidence_packet_status": _status(not handoff_path.exists(), handoff_rows, rows),
        "first_unlock_handoff_json": _artifact(args.first_unlock_handoff_json),
        "first_unlock_handoff_status": _text(handoff_summary.get("first_unlock_handoff_status")),
        "required_benchmark_id": _text(handoff_summary.get("required_benchmark_id")),
        "required_target_id": _text(handoff_summary.get("required_target_id")),
        "request_id": _text(handoff_summary.get("request_id")),
        "candidate_target_id": _text(handoff_summary.get("candidate_target_id")),
        "candidate_scope": _text(handoff_summary.get("candidate_scope")),
        "packet_folder": _artifact(packet_folder),
        "action_md": _artifact(packet_folder / "ACTION.md"),
        "operator_evidence_template_csv": _artifact(packet_folder / "operator_evidence_template.csv"),
        "dropzone_manifest_csv": _artifact(packet_folder / "dropzone_manifest.csv"),
        "field_count": len(rows),
        "open_field_count": len(open_rows),
        "ready_field_count": len(ready_rows),
        "evidence_stub_count": len(rows),
        "file_field_count": len(file_rows),
        "first_open_field": _text(first_open.get("field_key")),
        "first_blocker": _text(first_open.get("blocker")),
        "first_next_action": _text(first_open.get("next_action")),
        "operator_template_csv": _text(handoff_summary.get("operator_template_csv")),
        "prediction_dropzone": _text(handoff_summary.get("prediction_dropzone")),
        "current_prediction_created_at": _text(handoff_summary.get("current_prediction_created_at")),
        "current_native_release_date": _text(handoff_summary.get("current_native_release_date")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"rows": rows, "summary": summary}


def _template_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "field_key": row["field_key"],
            "operator_value": "",
            "operator_evidence_ref": row["evidence_stub_md"],
            "operator_clearance": "",
            "operator_id": "",
            "required_operator_value_format": row["required_operator_value_format"],
            "evidence_stub_md": row["evidence_stub_md"],
            "destination": row["destination"],
            "notes": "Fill manually from independent evidence; do not auto-fill from weak local hints.",
        }
        for row in rows
    ]


def _dropzone_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dropzone_rows = []
    for row in rows:
        if row["fill_kind"] != "file" and row["field_key"] not in {"prediction_pdb", "prediction_pdb_dropzone"}:
            continue
        dropzone_rows.append(
            {
                "field_key": row["field_key"],
                "dropzone_kind": row["required_evidence_kind"],
                "expected_path_or_destination": row["destination"],
                "evidence_stub_md": row["evidence_stub_md"],
                "dropzone_status": "awaiting_file_or_evidence",
                "next_action": row["next_action"],
            }
        )
    return dropzone_rows


def _write_stub(row: dict[str, Any]) -> None:
    path = _resolve(row["evidence_stub_md"])
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Evidence Stub: {row['field_key']}",
        "",
        f"- field: `{row['field_key']}`",
        f"- evidence kind: `{row['required_evidence_kind']}`",
        f"- status: `{row['packet_status']}`",
        f"- blocker: `{row['blocker'] or '-'}`",
        f"- required format: `{row['required_operator_value_format']}`",
        f"- accepted evidence examples: {row['accepted_evidence_examples']}",
        f"- rejected sources: {row['rejected_sources']}",
        f"- destination: `{row['destination'] or '-'}`",
        f"- next action: {row['next_action']}",
        "",
        "## Operator Evidence",
        "",
        "- operator_value:",
        "- operator_evidence_ref:",
        "- operator_clearance:",
        "- operator_id:",
        "",
        "## Claim Boundary",
        "",
        CLAIM_BOUNDARY,
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_action(packet_folder: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    path = packet_folder / "ACTION.md"
    lines = [
        "# CASP17 Strict-Blind First Unlock Evidence Action",
        "",
        f"- status: `{summary['first_unlock_evidence_packet_status']}`",
        f"- request/target: `{summary['request_id']}` `{summary['candidate_target_id']}`",
        f"- fields ready/open/total: `{summary['ready_field_count']}/{summary['open_field_count']}/{summary['field_count']}`",
        f"- first open field: `{summary['first_open_field'] or '-'}` `{summary['first_blocker'] or '-'}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        f"- operator evidence template: `{summary['operator_evidence_template_csv']}`",
        f"- dropzone manifest: `{summary['dropzone_manifest_csv']}`",
        "",
        "## Claim Boundary",
        "",
        summary["claim_boundary"],
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    rows = payload["rows"]
    lines = [
        "# CASP17 Strict-Blind First Unlock Evidence Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['first_unlock_evidence_packet_status']}`",
        f"- request/target: `{summary['request_id']}` `{summary['candidate_target_id']}`",
        f"- fields ready/open/total: `{summary['ready_field_count']}/{summary['open_field_count']}/{summary['field_count']}`",
        f"- file fields: `{summary['file_field_count']}`",
        f"- first open field: `{summary['first_open_field'] or '-'}` `{summary['first_blocker'] or '-'}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        f"- packet folder: `{summary['packet_folder']}`",
        f"- operator evidence template: `{summary['operator_evidence_template_csv']}`",
        f"- dropzone manifest: `{summary['dropzone_manifest_csv']}`",
        "",
        "## Fields",
        "",
        "| order | field | evidence kind | status | blocker | stub |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {order} | `{field}` | `{kind}` | `{status}` | `{blocker}` | `{stub}` |".format(
                order=row["field_order"],
                field=row["field_key"],
                kind=row["required_evidence_kind"],
                status=row["packet_status"],
                blocker=row["blocker"] or "-",
                stub=row["evidence_stub_md"],
            )
        )
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    packet_folder = _resolve(payload["summary"]["packet_folder"])
    packet_folder.mkdir(parents=True, exist_ok=True)
    for row in payload["rows"]:
        _write_stub(row)
    _write_action(packet_folder, payload)
    _write_csv(packet_folder / "operator_evidence_template.csv", _template_rows(payload["rows"]), TEMPLATE_COLUMNS)
    _write_csv(packet_folder / "dropzone_manifest.csv", _dropzone_rows(payload["rows"]), DROPZONE_COLUMNS)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first-unlock-handoff-json", default=DEFAULT_FIRST_UNLOCK_HANDOFF_JSON)
    parser.add_argument("--packet-root", default=DEFAULT_PACKET_ROOT)
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
