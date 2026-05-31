#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SOURCE_ROUTE_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_first_slot_source_route_board_current.json"
)
DEFAULT_OPERATOR_PACKET_JSON = "casp17/casp17_strict_blind_source_gate_operator_packet_current.json"
DEFAULT_LOCAL_CANDIDATE_JSON = (
    "casp17/casp17_historical_seed_strict_blind_replacement_first_slot_local_candidate_board_current.json"
)
DEFAULT_REQUEST_DIR = "casp17/strict_blind_source_gate_source_request_packet"
DEFAULT_OUT_JSON = "casp17/casp17_strict_blind_source_gate_source_request_packet_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_strict_blind_source_gate_source_request_packet_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_STRICT_BLIND_SOURCE_GATE_SOURCE_REQUEST_PACKET.md"

ROW_COLUMNS = [
    "request_id",
    "request_status",
    "request_kind",
    "candidate_target_id",
    "candidate_scope",
    "candidate_rank",
    "route_id",
    "route_status",
    "candidate_status",
    "first_blocker",
    "prediction_created_at",
    "native_release_date",
    "current_prediction_pdb",
    "current_native_pdb",
    "native_authority_ref",
    "required_operator_fields",
    "request_folder",
    "next_action",
]
OPERATOR_TEMPLATE_COLUMNS = [
    "field_key",
    "operator_value",
    "operator_evidence_ref",
    "required_format",
    "source_request_note",
]
CLAIM_BOUNDARY = (
    "Local CASP17 strict-blind source-gate source request packet only. It converts fail-closed first-slot source "
    "routes into operator source-acquisition request folders. It does not fetch external archives, create "
    "prediction/native files, approve provenance, mutate source manifests, compute CASP metrics, push remotes, or "
    "submit to CASP."
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


def _operator_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("operator_rows")
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


def _safe_name(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_") or "unknown"


def _input_blockers(args: argparse.Namespace) -> list[str]:
    blockers = []
    for name in ["source_route_json", "operator_packet_json", "local_candidate_json"]:
        if not _resolve(getattr(args, name)).exists():
            blockers.append(f"{name}_missing")
    return blockers


def _candidate_by_target(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {_text(row.get("target_id")): row for row in rows if _text(row.get("target_id"))}


def _operator_field_text(operator_rows: list[dict[str, Any]]) -> str:
    fields = []
    for row in operator_rows:
        field_key = _text(row.get("field_key"))
        if field_key:
            fields.append(field_key)
    return ",".join(fields)


def _request_kind(route: dict[str, Any]) -> str:
    if _text(route.get("in_first_slot_scope")) != "True":
        return "candidate_replacement_required"
    if _int(route.get("external_required_action_count")):
        return "pre_native_prediction_source_required"
    return "operator_evidence_repair_required"


def _request_status(route: dict[str, Any]) -> str:
    if _text(route.get("allowed_for_first_slot")) == "True":
        return "source_request_not_needed"
    if _text(route.get("in_first_slot_scope")) != "True":
        return "out_of_scope_replace_candidate"
    return "awaiting_pre_native_source_or_replacement"


def _next_action(route: dict[str, Any], candidate: dict[str, Any]) -> str:
    if _text(route.get("in_first_slot_scope")) != "True":
        return "replace this out-of-scope candidate with a monomer candidate or move it to the proper complex/ligand lane"
    if _text(route.get("first_blocker")) == "prediction_not_before_native":
        return "attach a prediction artifact created before the authoritative native release date, with timestamp and no-leak evidence"
    if not _text(candidate.get("native_authority_ref")):
        return "attach authoritative native source reference before operator clearance"
    return "fill the source-gate operator packet after source evidence is attached"


def _build_rows(
    args: argparse.Namespace,
    route_rows: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
    operator_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    candidates = _candidate_by_target(candidate_rows)
    required_operator_fields = _operator_field_text(operator_rows)
    rows: list[dict[str, Any]] = []
    for route in route_rows:
        candidate = candidates.get(_text(route.get("target_id")), {})
        request_id = f"source_request_{len(rows) + 1:03d}"
        folder = _resolve(args.request_dir) / request_id
        rows.append(
            {
                "request_id": request_id,
                "request_status": _request_status(route),
                "request_kind": _request_kind(route),
                "candidate_target_id": _text(route.get("target_id")),
                "candidate_scope": _text(route.get("scope")),
                "candidate_rank": _int(candidate.get("candidate_rank")),
                "route_id": _text(route.get("route_id")),
                "route_status": _text(route.get("route_status")),
                "candidate_status": _text(route.get("candidate_status")),
                "first_blocker": _text(route.get("first_blocker")),
                "prediction_created_at": _text(route.get("prediction_created_at")),
                "native_release_date": _text(route.get("native_release_date")),
                "current_prediction_pdb": _text(candidate.get("prediction_pdb")),
                "current_native_pdb": _text(candidate.get("native_pdb")),
                "native_authority_ref": _text(candidate.get("native_authority_ref")),
                "required_operator_fields": required_operator_fields,
                "request_folder": _artifact(folder),
                "next_action": _next_action(route, candidate),
            }
        )
    return rows


def _status(input_blockers: list[str], rows: list[dict[str, Any]]) -> str:
    if input_blockers:
        return "blocked_missing_inputs"
    if any(row["request_status"] == "awaiting_pre_native_source_or_replacement" for row in rows):
        return "awaiting_pre_native_source_or_candidate_replacement"
    if any(row["request_status"] == "out_of_scope_replace_candidate" for row in rows):
        return "awaiting_candidate_scope_replacement"
    return "source_request_packet_clear"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    route_payload = _read_json(args.source_route_json)
    operator_payload = _read_json(args.operator_packet_json)
    candidate_payload = _read_json(args.local_candidate_json)
    input_blockers = _input_blockers(args)
    rows = [] if input_blockers else _build_rows(args, _rows(route_payload), _rows(candidate_payload), _operator_rows(operator_payload))
    first_open = next((row for row in rows if row["request_status"] != "source_request_not_needed"), rows[0] if rows else {})
    summary = {
        "packet_type": "casp17_strict_blind_source_gate_source_request_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_request_packet_status": _status(input_blockers, rows),
        "required_benchmark_id": _text(_summary(route_payload).get("required_benchmark_id")),
        "required_target_id": _text(_summary(route_payload).get("required_target_id")),
        "required_scope": _text(_summary(route_payload).get("required_scope")),
        "source_route_board_status": _text(
            _summary(route_payload).get("strict_blind_replacement_first_slot_source_route_board_status")
        ),
        "operator_packet_status": _text(_summary(operator_payload).get("source_gate_operator_packet_status")),
        "operator_csv": _text(_summary(operator_payload).get("operator_csv")),
        "request_count": len(rows),
        "pre_native_source_required_count": sum(
            1 for row in rows if row["request_kind"] == "pre_native_prediction_source_required"
        ),
        "candidate_replacement_required_count": sum(
            1 for row in rows if row["request_kind"] == "candidate_replacement_required"
        ),
        "operator_evidence_repair_required_count": sum(
            1 for row in rows if row["request_kind"] == "operator_evidence_repair_required"
        ),
        "monomer_request_count": sum(1 for row in rows if row["candidate_scope"] == "monomer"),
        "complex_request_count": sum(1 for row in rows if row["candidate_scope"] == "complex"),
        "first_request_id": _text(first_open.get("request_id")),
        "first_request_target_id": _text(first_open.get("candidate_target_id")),
        "first_request_kind": _text(first_open.get("request_kind")),
        "first_request_blocker": _text(first_open.get("first_blocker")),
        "first_next_action": _text(first_open.get("next_action")),
        "request_dir": _artifact(args.request_dir),
        "input_blockers": ",".join(input_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _operator_template_rows(row: dict[str, Any]) -> list[dict[str, Any]]:
    fields = [field for field in row["required_operator_fields"].split(",") if field]
    rows: list[dict[str, Any]] = []
    for field in fields:
        note = "fill after acquiring strict-blind source evidence"
        if field == "prediction_pdb":
            note = "path to acquired pre-native prediction PDB"
        elif field == "source_id":
            note = f"internal source id for {row['candidate_target_id']}"
        elif field == "prediction_created_at":
            note = f"must be before native_release_date {row['native_release_date'] or 'UNKNOWN'}"
        rows.append(
            {
                "field_key": field,
                "operator_value": "",
                "operator_evidence_ref": "",
                "required_format": "",
                "source_request_note": note,
            }
        )
    return rows


def _write_request_folders(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    for row in payload["rows"]:
        folder = _resolve(row["request_folder"])
        folder.mkdir(parents=True, exist_ok=True)
        _write_csv(folder / "operator_source_values_template.csv", _operator_template_rows(row), OPERATOR_TEMPLATE_COLUMNS)
        lines = [
            "# CASP17 Strict-Blind Source Gate Source Request",
            "",
            f"- request: `{row['request_id']}` `{row['request_status']}` `{row['request_kind']}`",
            f"- candidate: `{row['candidate_target_id']}` `{row['candidate_scope']}` rank `{row['candidate_rank']}`",
            f"- route: `{row['route_id']}` `{row['route_status']}` blocker `{row['first_blocker'] or '-'}`",
            f"- prediction/native dates: `{row['prediction_created_at'] or '-'}` / `{row['native_release_date'] or '-'}`",
            f"- current prediction: `{row['current_prediction_pdb'] or '-'}`",
            f"- current native: `{row['current_native_pdb'] or '-'}`",
            f"- native authority: `{row['native_authority_ref'] or '-'}`",
            f"- operator fields: `{row['required_operator_fields']}`",
            f"- next action: {row['next_action']}",
            "",
            CLAIM_BOUNDARY,
            "",
        ]
        (folder / "SOURCE_REQUEST.md").write_text("\n".join(lines), encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Strict-Blind Source Gate Source Request Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['source_request_packet_status']}`",
        f"- required benchmark/target/scope: `{summary['required_benchmark_id']}` `{summary['required_target_id']}` `{summary['required_scope']}`",
        f"- route/operator status: `{summary['source_route_board_status']}` `{summary['operator_packet_status']}`",
        f"- requests pre-native/replacement/operator-repair/total: `{summary['pre_native_source_required_count']}/{summary['candidate_replacement_required_count']}/{summary['operator_evidence_repair_required_count']}/{summary['request_count']}`",
        f"- monomer/complex requests: `{summary['monomer_request_count']}/{summary['complex_request_count']}`",
        f"- first request: `{summary['first_request_id'] or '-'}` `{summary['first_request_target_id'] or '-'}` `{summary['first_request_kind'] or '-'}` `{summary['first_request_blocker'] or '-'}`",
        "",
        "## Requests",
        "",
        "| request | target | scope | kind | blocker | dates | next action |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['request_id']}` | `{row['candidate_target_id']}` | `{row['candidate_scope']}` | "
            f"`{row['request_kind']}` | `{row['first_blocker'] or '-'}` | "
            f"`{row['prediction_created_at'] or '-'}/{row['native_release_date'] or '-'}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | - | - | - | - |")
    lines.extend(["", CLAIM_BOUNDARY, ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)
    _write_request_folders(args, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 first-slot source-gate source request packet.")
    parser.add_argument("--source-route-json", default=DEFAULT_SOURCE_ROUTE_JSON)
    parser.add_argument("--operator-packet-json", default=DEFAULT_OPERATOR_PACKET_JSON)
    parser.add_argument("--local-candidate-json", default=DEFAULT_LOCAL_CANDIDATE_JSON)
    parser.add_argument("--request-dir", default=DEFAULT_REQUEST_DIR)
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
