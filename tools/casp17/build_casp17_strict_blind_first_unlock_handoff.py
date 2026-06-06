#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_UNLOCK_PLAN_JSON = "casp17/casp17_historical_winner_normalized_unlock_plan_current.json"
DEFAULT_CLOSURE_BOARD_JSON = "casp17/casp17_strict_blind_source_request_closure_board_current.json"
DEFAULT_SOURCE_REQUEST_PACKET_JSON = "casp17/casp17_strict_blind_source_gate_source_request_packet_current.json"
DEFAULT_OPERATOR_FILL_WORKLIST_JSON = (
    "casp17/casp17_strict_blind_source_request_operator_fill_worklist_current.json"
)
DEFAULT_SOURCE_GATE_OPERATOR_PACKET_JSON = "casp17/casp17_strict_blind_source_gate_operator_packet_current.json"
DEFAULT_INTERNAL_SOURCE_GATE_JSON = "casp17/casp17_strict_blind_internal_prediction_source_gate_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_strict_blind_first_unlock_handoff_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_strict_blind_first_unlock_handoff_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_STRICT_BLIND_FIRST_UNLOCK_HANDOFF.md"

ROW_COLUMNS = [
    "field_order",
    "field_key",
    "fill_kind",
    "operator_status",
    "fill_status",
    "value_status",
    "evidence_status",
    "required_format",
    "destination",
    "operator_template_csv",
    "operator_value",
    "operator_evidence_ref",
    "blocker",
    "next_action",
]

CLAIM_BOUNDARY = (
    "Local CASP17 strict-blind first-unlock handoff only. It consolidates the first source-request "
    "operator fields needed before the first historical strict-blind slot can pass the internal "
    "prediction source gate. It does not fill operator values, copy prediction files, approve "
    "provenance, compute CASP metrics, push remotes, or submit to CASP."
)

READY_OPERATOR_STATUSES = {
    "operator_value_present",
    "file_present",
    "file_ready",
    "derived_date_order_ready",
}
READY_FILL_STATUSES = {"field_ready_for_fulfillment_gate"}


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


def _rows(payload: dict[str, Any], key: str = "rows") -> list[dict[str, Any]]:
    rows = payload.get(key)
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


def _input_blockers(args: argparse.Namespace) -> list[str]:
    blockers = []
    for name in [
        "unlock_plan_json",
        "closure_board_json",
        "source_request_packet_json",
        "operator_fill_worklist_json",
        "source_gate_operator_packet_json",
        "internal_source_gate_json",
    ]:
        if not _resolve(getattr(args, name)).exists():
            blockers.append(f"{name}_missing")
    return blockers


def _first_source_request(source_rows: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [
        row
        for row in source_rows
        if _text(row.get("request_kind")) == "pre_native_prediction_source_required"
        and _text(row.get("candidate_scope")) == "monomer"
    ]
    if not candidates:
        candidates = source_rows
    return sorted(candidates, key=lambda row: (_int(row.get("candidate_rank")) or 999999, _text(row.get("request_id"))))[0] if candidates else {}


def _by_field(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {_text(row.get("field_key")): row for row in rows if _text(row.get("field_key"))}


def _row_ready(row: dict[str, Any]) -> bool:
    if _text(row.get("fill_status")) in READY_FILL_STATUSES:
        return True
    return _text(row.get("operator_status")) in READY_OPERATOR_STATUSES


def _build_rows(
    first_request: dict[str, Any],
    fill_rows: list[dict[str, Any]],
    operator_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    request_id = _text(first_request.get("request_id"))
    fills = _by_field([row for row in fill_rows if _text(row.get("request_id")) == request_id])
    fields = [field for field in _text(first_request.get("required_operator_fields")).split(",") if field]
    if not fields:
        fields = [_text(row.get("field_key")) for row in operator_rows if _text(row.get("field_key"))]
    operator_by_field = _by_field(operator_rows)
    rows: list[dict[str, Any]] = []
    for index, field in enumerate(fields, start=1):
        fill = fills.get(field, {})
        operator = operator_by_field.get(field, {})
        blocker = _text(fill.get("first_blocker")) or _text(operator.get("operator_status"))
        if _row_ready({**operator, **fill}):
            blocker = ""
        rows.append(
            {
                "field_order": index,
                "field_key": field,
                "fill_kind": _text(operator.get("fill_kind")),
                "operator_status": _text(operator.get("operator_status")) or _text(fill.get("fill_status")),
                "fill_status": _text(fill.get("fill_status")),
                "value_status": _text(fill.get("value_status")),
                "evidence_status": _text(fill.get("evidence_status")),
                "required_format": _text(operator.get("required_format")),
                "destination": _artifact(operator.get("destination")),
                "operator_template_csv": _artifact(fill.get("operator_template_csv") or first_request.get("operator_template_csv")),
                "operator_value": _text(operator.get("operator_value") or fill.get("operator_value")),
                "operator_evidence_ref": _text(operator.get("operator_evidence_ref") or fill.get("operator_evidence_ref")),
                "blocker": blocker,
                "next_action": _text(fill.get("next_action")) or _text(operator.get("next_action")),
            }
        )
    return rows


def _status(input_blockers: list[str], rows: list[dict[str, Any]]) -> str:
    if input_blockers:
        return "blocked_missing_inputs"
    if rows and all(_row_ready(row) for row in rows):
        return "first_unlock_handoff_ready_for_source_gate_review"
    return "awaiting_first_unlock_operator_values"


def _build_summary(
    args: argparse.Namespace,
    input_blockers: list[str],
    first_request: dict[str, Any],
    rows: list[dict[str, Any]],
    summaries: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    blocked_rows = [row for row in rows if not _row_ready(row)]
    first_blocked = blocked_rows[0] if blocked_rows else {}
    ready_count = len(rows) - len(blocked_rows)
    return {
        "packet_type": "casp17_strict_blind_first_unlock_handoff",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "first_unlock_handoff_status": _status(input_blockers, rows),
        "input_blockers": ",".join(input_blockers),
        "required_benchmark_id": _text(summaries["closure"].get("required_benchmark_id")),
        "required_target_id": _text(summaries["closure"].get("required_target_id")),
        "required_scope": _text(summaries["closure"].get("required_scope")),
        "unlock_plan_status": _text(summaries["unlock"].get("historical_winner_normalized_unlock_plan_status")),
        "unlock_first_blocked_action": _text(summaries["unlock"].get("first_blocked_action_id")),
        "closure_board_status": _text(summaries["closure"].get("strict_blind_source_request_closure_board_status")),
        "internal_source_gate_status": _text(summaries["gate"].get("internal_prediction_source_gate_status")),
        "request_id": _text(first_request.get("request_id")),
        "candidate_target_id": _text(first_request.get("candidate_target_id")),
        "candidate_scope": _text(first_request.get("candidate_scope")),
        "candidate_rank": _int(first_request.get("candidate_rank")),
        "current_prediction_pdb": _artifact(first_request.get("current_prediction_pdb")),
        "current_native_pdb": _artifact(first_request.get("current_native_pdb")),
        "native_authority_ref": _text(first_request.get("native_authority_ref")),
        "current_prediction_created_at": _text(first_request.get("prediction_created_at")),
        "current_native_release_date": _text(first_request.get("native_release_date")),
        "current_blocker": _text(first_request.get("first_blocker")),
        "field_count": len(rows),
        "ready_field_count": ready_count,
        "blocked_field_count": len(blocked_rows),
        "first_blocked_field_key": _text(first_blocked.get("field_key")),
        "first_blocker": _text(first_blocked.get("blocker")) or _text(first_request.get("first_blocker")),
        "first_next_action": _text(first_blocked.get("next_action")) or _text(first_request.get("next_action")),
        "operator_template_csv": _artifact(first_request.get("operator_template_csv")),
        "source_gate_operator_packet_json": _artifact(args.source_gate_operator_packet_json),
        "internal_source_manifest_csv": "casp17/strict_blind_internal_prediction_source_audit/hist_REQUIRED_MONOMER_001/internal_prediction_source_manifest_template.csv",
        "prediction_dropzone": "casp17/historical_seed_strict_blind_replacement_evidence_dropzones/01_hist_required_monomer_001/prediction/replacement_prediction.pdb",
        "claim_boundary": CLAIM_BOUNDARY,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    input_blockers = _input_blockers(args)
    unlock_payload = _read_json(args.unlock_plan_json)
    closure_payload = _read_json(args.closure_board_json)
    source_payload = _read_json(args.source_request_packet_json)
    fill_payload = _read_json(args.operator_fill_worklist_json)
    operator_payload = _read_json(args.source_gate_operator_packet_json)
    gate_payload = _read_json(args.internal_source_gate_json)
    first_request = _first_source_request(_rows(source_payload))
    rows = _build_rows(first_request, _rows(fill_payload), _rows(operator_payload, "operator_rows"))
    summaries = {
        "unlock": _summary(unlock_payload),
        "closure": _summary(closure_payload),
        "gate": _summary(gate_payload),
    }
    return {
        "rows": rows,
        "summary": _build_summary(args, input_blockers, first_request, rows, summaries),
    }


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    rows = payload["rows"]
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# CASP17 Strict-Blind First Unlock Handoff",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['first_unlock_handoff_status']}`",
        f"- benchmark/target/scope: `{summary['required_benchmark_id']}` `{summary['required_target_id']}` `{summary['required_scope']}`",
        f"- source request: `{summary['request_id']}` `{summary['candidate_target_id']}` rank `{summary['candidate_rank']}`",
        f"- fields ready/blocked/total: `{summary['ready_field_count']}/{summary['blocked_field_count']}/{summary['field_count']}`",
        f"- current chronology blocker: `{summary['current_blocker']}` prediction/native `{summary['current_prediction_created_at']}` / `{summary['current_native_release_date']}`",
        f"- first blocked field: `{summary['first_blocked_field_key'] or '-'}` `{summary['first_blocker'] or '-'}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        f"- operator template: `{summary['operator_template_csv']}`",
        f"- source manifest: `{summary['internal_source_manifest_csv']}`",
        f"- prediction dropzone: `{summary['prediction_dropzone']}`",
        "",
        "## Fields",
        "",
        "| order | field | status | blocker | destination | next action |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {order} | `{field}` | `{status}` | `{blocker}` | `{destination}` | {next_action} |".format(
                order=row["field_order"],
                field=row["field_key"],
                status=row["operator_status"] or row["fill_status"] or "-",
                blocker=row["blocker"] or "-",
                destination=row["destination"] or "-",
                next_action=row["next_action"] or "-",
            )
        )
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unlock-plan-json", default=DEFAULT_UNLOCK_PLAN_JSON)
    parser.add_argument("--closure-board-json", default=DEFAULT_CLOSURE_BOARD_JSON)
    parser.add_argument("--source-request-packet-json", default=DEFAULT_SOURCE_REQUEST_PACKET_JSON)
    parser.add_argument("--operator-fill-worklist-json", default=DEFAULT_OPERATOR_FILL_WORKLIST_JSON)
    parser.add_argument("--source-gate-operator-packet-json", default=DEFAULT_SOURCE_GATE_OPERATOR_PACKET_JSON)
    parser.add_argument("--internal-source-gate-json", default=DEFAULT_INTERNAL_SOURCE_GATE_JSON)
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
