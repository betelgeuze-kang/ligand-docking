#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_OPERATOR_GATE_JSON = "casp17/casp17_historical_seed_strict_blind_replacement_operator_value_gate_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_historical_seed_strict_blind_replacement_operator_action_board_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_historical_seed_strict_blind_replacement_operator_action_board_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_HISTORICAL_SEED_STRICT_BLIND_REPLACEMENT_OPERATOR_ACTION_BOARD.md"

OPERATOR_FIELDS = [
    "replacement_target_id",
    "replacement_benchmark_id",
    "target_identity_non_current_historical",
    "prediction_created_at",
    "native_release_date",
    "prediction_generated_before_native_release",
    "public_template_or_native_used_for_prediction",
    "other_team_model_used",
    "post_release_information_used",
    "operator_clearance",
]
ROW_COLUMNS = [
    "action_id",
    "queue_rank",
    "required_benchmark_id",
    "field_name",
    "required_policy",
    "action_status",
    "gate_status",
    "operator_value_present",
    "evidence_ref_present",
    "operator_clearance_present",
    "operator_values_csv",
    "destination_intake_csv",
    "blockers",
    "verify_command",
    "next_action",
]
CLAIM_BOUNDARY = (
    "Local CASP17 strict-blind replacement operator action board only. It expands operator-value gate rows into "
    "field-level operator actions and counts missing values, evidence references, and clearances. It does not "
    "create evidence, approve no-leak provenance, choose replacement targets, mutate intake CSVs, compute CASP "
    "metrics, or submit to CASP."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
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


def _blocker_set(row: dict[str, Any]) -> set[str]:
    return {part.strip() for part in _text(row.get("blockers")).split(",") if part.strip()}


def _present(flag_blocker: str, row: dict[str, Any], value_key: str) -> str:
    blockers = _blocker_set(row)
    value = _text(row.get(value_key))
    return "false" if flag_blocker in blockers or not value or value.upper().startswith("REQUIRED") else "true"


def _action_status(row: dict[str, Any]) -> str:
    gate_status = _text(row.get("gate_status"))
    blockers = _blocker_set(row)
    if gate_status in {"ready_to_apply", "already_applied", "applied"}:
        return gate_status
    if gate_status.startswith("blocked"):
        return gate_status
    if "operator_value_required" in blockers:
        return "open_operator_value"
    if "evidence_ref_required" in blockers:
        return "open_evidence_ref"
    if "operator_clearance_required" in blockers:
        return "open_operator_clearance"
    if gate_status.startswith("awaiting"):
        return gate_status
    return "blocked_operator_action_review"


def _next_action(status: str, row: dict[str, Any]) -> str:
    field = _text(row.get("field_name"))
    if status == "open_operator_value":
        return f"fill operator_value for {field} in replacement_operator_values.csv"
    if status == "open_evidence_ref":
        return f"attach evidence_ref for {field} in replacement_operator_values.csv"
    if status == "open_operator_clearance":
        return f"set operator_clearance for {field} after review"
    if status == "ready_to_apply":
        return "run operator value gate with --apply"
    if status in {"already_applied", "applied"}:
        return "rerun strict-blind replacement intake preflight"
    return "repair operator value row and rerun operator value gate"


def _action_rows(operator_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(operator_rows, start=1):
        status = _action_status(row)
        rows.append(
            {
                "action_id": f"strict_blind_operator_{index:03d}",
                "queue_rank": _int(row.get("queue_rank")),
                "required_benchmark_id": _text(row.get("required_benchmark_id")),
                "field_name": _text(row.get("field_name")),
                "required_policy": _text(row.get("required_policy")),
                "action_status": status,
                "gate_status": _text(row.get("gate_status")),
                "operator_value_present": _present("operator_value_required", row, "operator_value"),
                "evidence_ref_present": _present("evidence_ref_required", row, "evidence_ref"),
                "operator_clearance_present": _present("operator_clearance_required", row, "operator_clearance"),
                "operator_values_csv": _text(row.get("operator_values_csv")),
                "destination_intake_csv": _text(row.get("destination_intake_csv")),
                "blockers": _text(row.get("blockers")),
                "verify_command": "python3 tools/build_casp17_historical_seed_strict_blind_replacement_operator_value_gate.py",
                "next_action": _next_action(status, row),
            }
        )
    return rows


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    operator_payload = _read_json(args.operator_gate_json)
    input_blockers: list[str] = []
    if not _resolve(args.operator_gate_json).exists():
        input_blockers.append("strict_blind_replacement_operator_value_gate_json_missing")
    rows = _action_rows(_rows(operator_payload))
    summary = _build_summary(args, rows, input_blockers, operator_payload)
    return {"summary": summary, "rows": rows}


def _build_summary(
    args: argparse.Namespace,
    rows: list[dict[str, Any]],
    input_blockers: list[str],
    operator_payload: dict[str, Any],
) -> dict[str, Any]:
    open_rows = [row for row in rows if row["action_status"] not in {"ready_to_apply", "already_applied", "applied"}]
    first_open = open_rows[0] if open_rows else {}
    field_missing = {
        field: sum(
            1
            for row in rows
            if row["field_name"] == field and row["operator_value_present"] == "false"
        )
        for field in OPERATOR_FIELDS
    }
    ready = sum(1 for row in rows if row["action_status"] == "ready_to_apply")
    applied = sum(1 for row in rows if row["action_status"] == "applied")
    already = sum(1 for row in rows if row["action_status"] == "already_applied")
    open_value = sum(1 for row in rows if row["operator_value_present"] == "false")
    open_evidence = sum(1 for row in rows if row["evidence_ref_present"] == "false")
    open_clearance = sum(1 for row in rows if row["operator_clearance_present"] == "false")
    blocked = sum(1 for row in rows if _text(row.get("action_status")).startswith("blocked"))
    summary = {
        "packet_type": "casp17_historical_seed_strict_blind_replacement_operator_action_board",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "strict_blind_replacement_operator_action_board_status": _overall_status(rows, input_blockers),
        "operator_gate_json": _artifact(args.operator_gate_json),
        "operator_gate_status": _text(
            _summary(operator_payload).get("strict_blind_replacement_operator_value_gate_status")
        ),
        "action_count": len(rows),
        "ready_for_apply_count": ready,
        "applied_count": applied,
        "already_applied_count": already,
        "open_operator_value_count": open_value,
        "open_evidence_ref_count": open_evidence,
        "open_operator_clearance_count": open_clearance,
        "blocked_count": blocked,
        "replacement_target_id_missing_count": field_missing["replacement_target_id"],
        "replacement_benchmark_id_missing_count": field_missing["replacement_benchmark_id"],
        "target_identity_non_current_missing_count": field_missing["target_identity_non_current_historical"],
        "prediction_created_at_missing_count": field_missing["prediction_created_at"],
        "native_release_date_missing_count": field_missing["native_release_date"],
        "prediction_before_native_missing_count": field_missing["prediction_generated_before_native_release"],
        "public_template_false_missing_count": field_missing["public_template_or_native_used_for_prediction"],
        "other_team_false_missing_count": field_missing["other_team_model_used"],
        "post_release_false_missing_count": field_missing["post_release_information_used"],
        "operator_clearance_value_missing_count": field_missing["operator_clearance"],
        "first_open_action_id": _text(first_open.get("action_id")),
        "first_open_benchmark_id": _text(first_open.get("required_benchmark_id")),
        "first_open_field": _text(first_open.get("field_name")),
        "first_open_status": _text(first_open.get("action_status")),
        "first_next_action": _text(first_open.get("next_action")) or "provide strict-blind operator values",
        "input_blockers": ",".join(input_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return summary


def _overall_status(rows: list[dict[str, Any]], input_blockers: list[str]) -> str:
    if input_blockers:
        return "blocked_missing_input"
    if not rows:
        return "blocked_missing_operator_actions"
    if any(_text(row.get("action_status")).startswith("blocked") for row in rows):
        return "blocked_operator_action_review"
    if any(_text(row.get("action_status")).startswith("open_") for row in rows):
        return "awaiting_strict_blind_operator_actions"
    if any(row.get("action_status") == "ready_to_apply" for row in rows):
        return "strict_blind_operator_actions_ready_for_apply"
    return "strict_blind_operator_actions_clear"


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Seed Strict-Blind Replacement Operator Action Board",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['strict_blind_replacement_operator_action_board_status']}`",
        f"- actions ready/applied/already/total: `{summary['ready_for_apply_count']}/{summary['applied_count']}/{summary['already_applied_count']}/{summary['action_count']}`",
        f"- open value/evidence/clearance: `{summary['open_operator_value_count']}/{summary['open_evidence_ref_count']}/{summary['open_operator_clearance_count']}`",
        f"- missing target/benchmark/non-current/pred-date/native-date/before-native: `{summary['replacement_target_id_missing_count']}/{summary['replacement_benchmark_id_missing_count']}/{summary['target_identity_non_current_missing_count']}/{summary['prediction_created_at_missing_count']}/{summary['native_release_date_missing_count']}/{summary['prediction_before_native_missing_count']}`",
        f"- missing false-controls/public/other-team/post-release/operator-clearance: `{summary['public_template_false_missing_count']}/{summary['other_team_false_missing_count']}/{summary['post_release_false_missing_count']}/{summary['operator_clearance_value_missing_count']}`",
        f"- first open: `{summary['first_open_action_id'] or '-'}` `{summary['first_open_benchmark_id'] or '-'}` `{summary['first_open_field'] or '-'}` `{summary['first_open_status'] or '-'}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        "",
        "## Open Actions",
        "",
        "| action | benchmark | field | status | value | evidence | clearance | next action |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    open_rows = [
        row for row in payload["rows"] if row["action_status"] not in {"ready_to_apply", "already_applied", "applied"}
    ]
    for row in open_rows[:100]:
        lines.append(
            f"| `{row['action_id']}` | `{row['required_benchmark_id']}` | `{row['field_name']}` | "
            f"`{row['action_status']}` | `{row['operator_value_present']}` | `{row['evidence_ref_present']}` | "
            f"`{row['operator_clearance_present']}` | {row['next_action']} |"
        )
    if len(open_rows) > 100:
        lines.append(f"| ... | ... | ... | ... | ... | ... | ... | `{len(open_rows) - 100} more actions in CSV` |")
    if not open_rows:
        lines.append("| - | - | - | `clear` | true | true | true | rerun operator value gate |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 strict-blind operator action board.")
    parser.add_argument("--operator-gate-json", default=DEFAULT_OPERATOR_GATE_JSON)
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
