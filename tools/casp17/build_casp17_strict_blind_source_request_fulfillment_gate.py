#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_SOURCE_REQUEST_PACKET_JSON = (
    "casp17/casp17_strict_blind_source_gate_source_request_packet_current.json"
)
DEFAULT_SOURCE_GATE_OPERATOR_PACKET_JSON = (
    "casp17/casp17_strict_blind_source_gate_operator_packet_current.json"
)
DEFAULT_OUT_JSON = "casp17/casp17_strict_blind_source_request_fulfillment_gate_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_strict_blind_source_request_fulfillment_gate_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_STRICT_BLIND_SOURCE_REQUEST_FULFILLMENT_GATE.md"

ROW_COLUMNS = [
    "request_id",
    "candidate_target_id",
    "candidate_scope",
    "request_kind",
    "fulfillment_status",
    "ready_for_operator_packet",
    "operator_template_csv",
    "operator_field_count",
    "operator_field_filled_count",
    "operator_field_missing_count",
    "operator_evidence_ref_count",
    "operator_evidence_ref_missing_count",
    "source_id",
    "source_classification_status",
    "prediction_pdb",
    "prediction_pdb_exists",
    "prediction_pdb_atom_count",
    "prediction_created_at",
    "native_release_date",
    "chronology_status",
    "first_blocker",
    "next_action",
]
REQUIRED_EVIDENCE_FIELDS = {
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
EXTERNAL_SOURCE_TOKENS = (
    "official_archive",
    "casp_official",
    "massivefold",
    "alphafold_server",
    "af3_server",
    "other_team",
)
CLEARANCE_VALUES = {"approved", "clear", "cleared", "true", "yes", "operator_clear", "operator_approved"}
CLAIM_BOUNDARY = (
    "Local CASP17 strict-blind source-request fulfillment gate only. It validates operator-filled source request "
    "templates for field completeness, evidence references, internal-source labeling, PDB atom records, and "
    "pre-native chronology. It does not apply values to the source-gate operator packet, copy files, approve "
    "provenance, compute CASP metrics, push remotes, or submit to CASP."
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


def _date(value: Any) -> dt.date | None:
    text = _text(value)
    if not text:
        return None
    try:
        return dt.date.fromisoformat(text[:10])
    except ValueError:
        return None


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
    for name in ["source_request_packet_json", "source_gate_operator_packet_json"]:
        if not _resolve(getattr(args, name)).exists():
            blockers.append(f"{name}_missing")
    return blockers


def _required_fields(request: dict[str, Any]) -> list[str]:
    return [field for field in _text(request.get("required_operator_fields")).split(",") if field]


def _template_csv(request: dict[str, Any]) -> str:
    explicit = _text(request.get("operator_template_csv"))
    if explicit:
        return explicit
    folder = _text(request.get("request_folder"))
    return _artifact(_resolve(folder) / "operator_source_values_template.csv") if folder else ""


def _field_rows(template_csv: str) -> dict[str, dict[str, str]]:
    return {_text(row.get("field_key")): row for row in _read_csv_rows(template_csv) if _text(row.get("field_key"))}


def _field_value(fields: dict[str, dict[str, str]], field_key: str) -> str:
    return _text(fields.get(field_key, {}).get("operator_value"))


def _field_evidence(fields: dict[str, dict[str, str]], field_key: str) -> str:
    return _text(fields.get(field_key, {}).get("operator_evidence_ref"))


def _pdb_atom_count(path_like: str) -> int:
    if not path_like:
        return 0
    path = _resolve(path_like)
    if not path.exists() or not path.is_file():
        return 0
    count = 0
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                if line.startswith(("ATOM  ", "HETATM")):
                    count += 1
    except OSError:
        return 0
    return count


def _source_classification_status(source_id: str) -> str:
    value = source_id.lower()
    if not value:
        return "source_id_missing"
    if any(token in value for token in EXTERNAL_SOURCE_TOKENS):
        return "external_source_not_allowed"
    if "internal" not in value:
        return "source_id_not_marked_internal"
    return "pass"


def _chronology_status(prediction_created_at: str, native_release_date: str) -> str:
    pred = _date(prediction_created_at)
    native = _date(native_release_date)
    if not pred or not native:
        return "date_missing_or_invalid"
    if pred < native:
        return "pass"
    return "prediction_not_before_native"


def _first_missing(fields: dict[str, dict[str, str]], required_fields: list[str]) -> str:
    for field in required_fields:
        if not _field_value(fields, field):
            return field
    return ""


def _first_missing_evidence(fields: dict[str, dict[str, str]], required_fields: list[str]) -> str:
    for field in required_fields:
        if field in REQUIRED_EVIDENCE_FIELDS and not _field_evidence(fields, field):
            return field
    return ""


def _next_action(first_blocker: str, request_kind: str) -> str:
    if request_kind == "candidate_replacement_required":
        return "replace this out-of-scope candidate with a strict-blind monomer candidate before first-slot use"
    if first_blocker == "operator_template_missing":
        return "restore or create operator_source_values_template.csv for this source request"
    if first_blocker.endswith("_missing"):
        return f"fill operator_value for {first_blocker.removesuffix('_missing')}"
    if first_blocker.endswith("_evidence_ref_missing"):
        return f"attach operator_evidence_ref for {first_blocker.removesuffix('_evidence_ref_missing')}"
    if first_blocker == "prediction_pdb_missing_or_invalid":
        return "point prediction_pdb at a local pre-native PDB with ATOM/HETATM records"
    if first_blocker == "prediction_not_before_native":
        return "provide prediction_created_at earlier than native_release_date"
    if first_blocker in {"source_id_missing", "source_id_not_marked_internal", "external_source_not_allowed"}:
        return "set source_id to an internal pre-native prediction source, not official archives or external pools"
    if first_blocker == "operator_clearance_missing":
        return "set operator_clearance only after source and provenance review"
    return "source request is ready to sync into the source-gate operator packet"


def _build_row(request: dict[str, Any]) -> dict[str, Any]:
    required_fields = _required_fields(request)
    template_csv = _template_csv(request)
    template_path = _resolve(template_csv)
    fields = _field_rows(template_csv)
    filled_count = sum(1 for field in required_fields if _field_value(fields, field))
    missing_count = max(len(required_fields) - filled_count, 0)
    evidence_fields = [field for field in required_fields if field in REQUIRED_EVIDENCE_FIELDS]
    evidence_count = sum(1 for field in evidence_fields if _field_evidence(fields, field))
    evidence_missing_count = max(len(evidence_fields) - evidence_count, 0)
    source_id = _field_value(fields, "source_id")
    prediction_pdb = _field_value(fields, "prediction_pdb")
    prediction_created_at = _field_value(fields, "prediction_created_at")
    native_release_date = _field_value(fields, "native_release_date")
    source_status = _source_classification_status(source_id)
    atom_count = _pdb_atom_count(prediction_pdb)
    chronology = _chronology_status(prediction_created_at, native_release_date)
    first_blocker = ""
    if _text(request.get("request_kind")) == "candidate_replacement_required":
        first_blocker = "candidate_replacement_required"
    elif not template_path.exists():
        first_blocker = "operator_template_missing"
    elif missing_count:
        first_blocker = f"{_first_missing(fields, required_fields)}_missing"
    elif evidence_missing_count:
        first_blocker = f"{_first_missing_evidence(fields, required_fields)}_evidence_ref_missing"
    elif source_status != "pass":
        first_blocker = source_status
    elif atom_count <= 0:
        first_blocker = "prediction_pdb_missing_or_invalid"
    elif chronology != "pass":
        first_blocker = chronology
    elif _field_value(fields, "operator_clearance").lower() not in CLEARANCE_VALUES:
        first_blocker = "operator_clearance_missing"
    ready = not first_blocker
    return {
        "request_id": _text(request.get("request_id")),
        "candidate_target_id": _text(request.get("candidate_target_id")),
        "candidate_scope": _text(request.get("candidate_scope")),
        "request_kind": _text(request.get("request_kind")),
        "fulfillment_status": "ready_for_source_gate_operator_packet" if ready else "blocked_on_source_request_fulfillment",
        "ready_for_operator_packet": str(ready),
        "operator_template_csv": template_csv,
        "operator_field_count": len(required_fields),
        "operator_field_filled_count": filled_count,
        "operator_field_missing_count": missing_count,
        "operator_evidence_ref_count": evidence_count,
        "operator_evidence_ref_missing_count": evidence_missing_count,
        "source_id": source_id,
        "source_classification_status": source_status,
        "prediction_pdb": prediction_pdb,
        "prediction_pdb_exists": str(_resolve(prediction_pdb).is_file() if prediction_pdb else False),
        "prediction_pdb_atom_count": atom_count,
        "prediction_created_at": prediction_created_at,
        "native_release_date": native_release_date,
        "chronology_status": chronology,
        "first_blocker": first_blocker,
        "next_action": _next_action(first_blocker, _text(request.get("request_kind"))),
    }


def _status(input_blockers: list[str], rows: list[dict[str, Any]]) -> str:
    if input_blockers:
        return "blocked_missing_inputs"
    if not rows:
        return "blocked_no_source_requests"
    ready = sum(1 for row in rows if row["ready_for_operator_packet"] == "True")
    if ready == len(rows):
        return "source_request_fulfillment_ready"
    if ready:
        return "source_request_fulfillment_ready_partial"
    if any(_int(row.get("operator_field_missing_count")) for row in rows):
        return "awaiting_source_request_operator_values"
    if any(_int(row.get("operator_evidence_ref_missing_count")) for row in rows):
        return "awaiting_source_request_operator_evidence"
    return "blocked_on_source_request_fulfillment_gate"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    source_request_payload = _read_json(args.source_request_packet_json)
    operator_packet_payload = _read_json(args.source_gate_operator_packet_json)
    source_request_summary = _summary(source_request_payload)
    operator_packet_summary = _summary(operator_packet_payload)
    input_blockers = _input_blockers(args)
    rows = [] if input_blockers else [_build_row(row) for row in _rows(source_request_payload)]
    first_blocked = next((row for row in rows if row["ready_for_operator_packet"] != "True"), rows[0] if rows else {})
    summary = {
        "packet_type": "casp17_strict_blind_source_request_fulfillment_gate",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_request_fulfillment_gate_status": _status(input_blockers, rows),
        "source_request_packet_status": _text(source_request_summary.get("source_request_packet_status")),
        "source_gate_operator_packet_status": _text(operator_packet_summary.get("source_gate_operator_packet_status")),
        "source_gate_operator_csv": _text(operator_packet_summary.get("operator_csv")),
        "request_count": len(rows),
        "ready_request_count": sum(1 for row in rows if row["ready_for_operator_packet"] == "True"),
        "blocked_request_count": sum(1 for row in rows if row["ready_for_operator_packet"] != "True"),
        "operator_field_count": sum(_int(row.get("operator_field_count")) for row in rows),
        "operator_field_filled_count": sum(_int(row.get("operator_field_filled_count")) for row in rows),
        "operator_field_missing_count": sum(_int(row.get("operator_field_missing_count")) for row in rows),
        "operator_evidence_ref_count": sum(_int(row.get("operator_evidence_ref_count")) for row in rows),
        "operator_evidence_ref_missing_count": sum(
            _int(row.get("operator_evidence_ref_missing_count")) for row in rows
        ),
        "prediction_pdb_valid_count": sum(1 for row in rows if _int(row.get("prediction_pdb_atom_count")) > 0),
        "chronology_pass_count": sum(1 for row in rows if row.get("chronology_status") == "pass"),
        "internal_source_pass_count": sum(1 for row in rows if row.get("source_classification_status") == "pass"),
        "first_blocked_request_id": _text(first_blocked.get("request_id")),
        "first_blocked_target_id": _text(first_blocked.get("candidate_target_id")),
        "first_blocker": _text(first_blocked.get("first_blocker")),
        "first_next_action": _text(first_blocked.get("next_action")),
        "input_blockers": ",".join(input_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Strict-Blind Source Request Fulfillment Gate",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['source_request_fulfillment_gate_status']}`",
        f"- source request/operator packet: `{summary['source_request_packet_status'] or '-'}` `{summary['source_gate_operator_packet_status'] or '-'}`",
        f"- requests ready/blocked/total: `{summary['ready_request_count']}/{summary['blocked_request_count']}/{summary['request_count']}`",
        f"- operator fields filled/missing/total: `{summary['operator_field_filled_count']}/{summary['operator_field_missing_count']}/{summary['operator_field_count']}`",
        f"- evidence refs present/missing: `{summary['operator_evidence_ref_count']}/{summary['operator_evidence_ref_missing_count']}`",
        f"- validation pass counts pdb/chronology/internal-source: `{summary['prediction_pdb_valid_count']}/{summary['chronology_pass_count']}/{summary['internal_source_pass_count']}`",
        f"- first blocker: `{summary['first_blocked_request_id'] or '-'}` `{summary['first_blocked_target_id'] or '-'}` `{summary['first_blocker'] or '-'}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        "",
        "## Requests",
        "",
        "| request | target | kind | status | fields | evidence | pdb atoms | chronology | source | first blocker |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['request_id']}` | `{row['candidate_target_id']}` | `{row['request_kind']}` | "
            f"`{row['fulfillment_status']}` | "
            f"`{row['operator_field_filled_count']}/{row['operator_field_missing_count']}/{row['operator_field_count']}` | "
            f"`{row['operator_evidence_ref_count']}/{row['operator_evidence_ref_missing_count']}` | "
            f"`{row['prediction_pdb_atom_count']}` | `{row['chronology_status']}` | "
            f"`{row['source_classification_status']}` | `{row['first_blocker'] or '-'}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | - | - | - | - | - | - | - |")
    lines.extend(["", CLAIM_BOUNDARY, ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 strict-blind source request fulfillment gate.")
    parser.add_argument("--source-request-packet-json", default=DEFAULT_SOURCE_REQUEST_PACKET_JSON)
    parser.add_argument("--source-gate-operator-packet-json", default=DEFAULT_SOURCE_GATE_OPERATOR_PACKET_JSON)
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
