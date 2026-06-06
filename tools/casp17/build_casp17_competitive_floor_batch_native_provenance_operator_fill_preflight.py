#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any

from tools import build_casp17_competitive_floor_batch_native_provenance_value_action_board as action_board
from tools import build_casp17_competitive_floor_batch_native_provenance_value_gate as value_gate


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_VALUE_GATE_JSON = "casp17/casp17_competitive_floor_batch_native_provenance_value_gate_current.json"
DEFAULT_ACTION_BOARD_JSON = (
    "casp17/casp17_competitive_floor_batch_native_provenance_value_action_board_current.json"
)
DEFAULT_ACTION_BOARD_COMPLETION_AUDIT_JSON = (
    "casp17/casp17_competitive_floor_batch_native_provenance_value_action_board_completion_audit_current.json"
)
DEFAULT_OUT_DIR = "casp17/competitive_floor_batch_native_provenance_operator_fill_preflight"
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_batch_native_provenance_operator_fill_preflight_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_batch_native_provenance_operator_fill_preflight_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_COMPETITIVE_FLOOR_BATCH_NATIVE_PROVENANCE_OPERATOR_FILL_PREFLIGHT.md"

INTAKE_COLUMNS = ["target_id", *value_gate.REQUIRED_VALUE_COLUMNS]
FIELD_POLICY_COLUMNS = [
    "target_id",
    "field_name",
    "field_group",
    "blocker",
    "required_value_policy",
    "current_value",
    "next_action",
]
ROW_COLUMNS = [
    "target_id",
    "target_name",
    "preflight_status",
    "target_preflight_folder",
    "operator_fill_template_csv",
    "field_policy_csv",
    "open_action_count",
    "native_action_count",
    "evidence_action_count",
    "clearance_action_count",
    "operator_action_count",
    "date_action_count",
    "boolean_action_count",
    "review_action_count",
    "batch_operator_fill_intake_csv",
    "value_gate_status",
    "action_board_completion_audit_status",
    "coordinate_copy_count",
    "competitive_proof_eligible",
    "author_serialized",
    "blockers",
    "next_action",
]
CLAIM_BOUNDARY = (
    "CASP17 competitive-floor batch native/provenance operator-fill preflight only. It packages the existing "
    "batch intake placeholders, field-level policies, and validation commands into target-named folders before "
    "operator fill. It does not fill values, fetch native structures, copy coordinate files, clear no-leak "
    "provenance, compute native accuracy, serialize a CASP author code, or submit to CASP."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    text = str(path_like or "").strip()
    if not text:
        return ""
    path = _resolve(text).resolve()
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


def _read_csv_rows(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
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


def _coordinate_file_count(path_like: str | Path) -> int:
    path = _resolve(path_like)
    if not path.exists():
        return 0
    return sum(1 for item in path.rglob("*") if item.is_file() and item.suffix.lower() in {".pdb", ".cif"})


def _intake_by_target(intake_csv: str | Path) -> dict[str, dict[str, str]]:
    rows = _read_csv_rows(intake_csv)
    return {_text(row.get("target_id")).upper(): row for row in rows if _text(row.get("target_id"))}


def _rows_by_target(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_target: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        target_id = _text(row.get("target_id")).upper()
        if target_id:
            by_target.setdefault(target_id, []).append(row)
    return by_target


def _single_rows_by_target(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {_text(row.get("target_id")).upper(): row for row in rows if _text(row.get("target_id"))}


def _target_folder(out_dir: str | Path, target_id: str, target_name: str) -> str:
    slug = action_board._safe_slug(target_name or target_id)
    return _artifact(_resolve(out_dir) / f"{target_id}_{slug}")


def _lane_count(rows: list[dict[str, Any]], lane: str) -> int:
    return sum(1 for row in rows if _text(row.get("field_group")) == lane)


def _target_preflight_row(
    *,
    target_id: str,
    gate_row: dict[str, Any],
    action_rows: list[dict[str, Any]],
    intake_row: dict[str, str],
    batch_intake_csv: str,
    audit_status: str,
    out_dir: str | Path,
    global_blockers: list[str],
) -> dict[str, Any]:
    target_name = _text(gate_row.get("target_name")) or _text(action_rows[0].get("target_name") if action_rows else "")
    folder = _target_folder(out_dir, target_id, target_name)
    blockers = list(global_blockers)
    if not intake_row:
        blockers.append("batch_intake_target_row_missing")
    if not action_rows and _text(gate_row.get("gate_status")) != "ready_for_operator_intake_apply":
        blockers.append("target_action_rows_missing")
    if audit_status != "casp17_competitive_floor_batch_native_provenance_value_action_board_completion_audit_pass":
        blockers.append("value_action_board_completion_audit_not_pass")
    coordinate_count = _coordinate_file_count(folder)
    if coordinate_count:
        blockers.append("target_preflight_coordinate_copy_present")
    blockers = list(dict.fromkeys(blockers))
    status = "ready_for_operator_fill" if not blockers else "blocked_preflight"
    return {
        "target_id": target_id,
        "target_name": target_name,
        "preflight_status": status,
        "target_preflight_folder": folder,
        "operator_fill_template_csv": _artifact(_resolve(folder) / "operator_fill_template.csv"),
        "field_policy_csv": _artifact(_resolve(folder) / "field_policy.csv"),
        "open_action_count": len(action_rows),
        "native_action_count": _lane_count(action_rows, "native_file"),
        "evidence_action_count": _lane_count(action_rows, "evidence"),
        "clearance_action_count": _lane_count(action_rows, "clearance"),
        "operator_action_count": _lane_count(action_rows, "operator"),
        "date_action_count": _lane_count(action_rows, "date"),
        "boolean_action_count": _lane_count(action_rows, "boolean"),
        "review_action_count": _lane_count(action_rows, "review"),
        "batch_operator_fill_intake_csv": batch_intake_csv,
        "value_gate_status": _text(gate_row.get("gate_status")),
        "action_board_completion_audit_status": audit_status,
        "coordinate_copy_count": coordinate_count,
        "competitive_proof_eligible": "false",
        "author_serialized": "false",
        "blockers": ",".join(blockers),
        "next_action": _next_action(action_rows, batch_intake_csv),
    }


def _next_action(action_rows: list[dict[str, Any]], batch_intake_csv: str) -> str:
    first = action_rows[0] if action_rows else {}
    field_name = _text(first.get("field_name")) or "native/provenance fields"
    return f"Fill {field_name} in {batch_intake_csv}, then rerun value gate and operator intake dry-run."


def _field_policy_rows(target_id: str, action_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "target_id": target_id,
            "field_name": _text(row.get("field_name")),
            "field_group": _text(row.get("field_group")),
            "blocker": _text(row.get("blocker")),
            "required_value_policy": _text(row.get("required_value_policy")),
            "current_value": _text(row.get("current_value")),
            "next_action": _text(row.get("next_action")),
        }
        for row in action_rows
    ]


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    gate_payload = _read_json(args.value_gate_json)
    action_payload = _read_json(args.action_board_json)
    audit_payload = _read_json(args.action_board_completion_audit_json)
    gate_summary = _summary(gate_payload)
    audit_summary = _summary(audit_payload)
    gate_rows = _rows(gate_payload)
    action_rows = _rows(action_payload)
    gate_by_target = _single_rows_by_target(gate_rows)
    action_by_target = _rows_by_target(action_rows)
    batch_intake_csv = _text(gate_summary.get("batch_operator_fill_intake_csv"))
    intake_by_target = _intake_by_target(batch_intake_csv) if batch_intake_csv else {}
    global_blockers: list[str] = []
    if not _resolve(args.value_gate_json).exists():
        global_blockers.append("value_gate_json_missing")
    if not _resolve(args.action_board_json).exists():
        global_blockers.append("value_action_board_json_missing")
    if not _resolve(args.action_board_completion_audit_json).exists():
        global_blockers.append("value_action_board_completion_audit_json_missing")
    if not batch_intake_csv:
        global_blockers.append("batch_operator_fill_intake_csv_missing")
    elif not _resolve(batch_intake_csv).exists():
        global_blockers.append("batch_operator_fill_intake_csv_not_found")
    audit_status = _text(
        audit_summary.get("batch_native_provenance_value_action_board_completion_audit_status")
    )
    target_ids = sorted(set(gate_by_target) | set(action_by_target))
    rows = [
        _target_preflight_row(
            target_id=target_id,
            gate_row=gate_by_target.get(target_id, {}),
            action_rows=action_by_target.get(target_id, []),
            intake_row=intake_by_target.get(target_id, {}),
            batch_intake_csv=batch_intake_csv,
            audit_status=audit_status,
            out_dir=args.out_dir,
            global_blockers=global_blockers,
        )
        for target_id in target_ids
    ]
    blocked_rows = [row for row in rows if row["preflight_status"] != "ready_for_operator_fill"]
    coordinate_count = _coordinate_file_count(args.out_dir)
    status = "casp17_competitive_floor_batch_native_provenance_operator_fill_preflight_ready_for_operator_fill"
    if blocked_rows or global_blockers or not rows:
        status = "casp17_competitive_floor_batch_native_provenance_operator_fill_preflight_blocked"
    summary = {
        "packet_type": "casp17_competitive_floor_batch_native_provenance_operator_fill_preflight",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "batch_native_provenance_operator_fill_preflight_status": status,
        "value_gate_json": _artifact(args.value_gate_json),
        "action_board_json": _artifact(args.action_board_json),
        "action_board_completion_audit_json": _artifact(args.action_board_completion_audit_json),
        "action_board_completion_audit_status": audit_status,
        "batch_operator_fill_intake_csv": batch_intake_csv,
        "out_dir": _artifact(args.out_dir),
        "target_count": len(rows),
        "target_ready_for_fill_count": len(rows) - len(blocked_rows),
        "target_blocked_count": len(blocked_rows),
        "open_action_count": sum(_int(row.get("open_action_count")) for row in rows),
        "native_action_count": sum(_int(row.get("native_action_count")) for row in rows),
        "evidence_action_count": sum(_int(row.get("evidence_action_count")) for row in rows),
        "clearance_action_count": sum(_int(row.get("clearance_action_count")) for row in rows),
        "operator_action_count": sum(_int(row.get("operator_action_count")) for row in rows),
        "date_action_count": sum(_int(row.get("date_action_count")) for row in rows),
        "boolean_action_count": sum(_int(row.get("boolean_action_count")) for row in rows),
        "review_action_count": sum(_int(row.get("review_action_count")) for row in rows),
        "coordinate_copy_count": coordinate_count,
        "target_coordinate_copy_count": sum(_int(row.get("coordinate_copy_count")) for row in rows),
        "competitive_proof_eligible_count": 0,
        "author_serialized_count": 0,
        "first_ready_target_id": _text(rows[0].get("target_id")) if rows else "",
        "first_blocked_target_id": _text(blocked_rows[0].get("target_id")) if blocked_rows else "",
        "first_blocker": _text(blocked_rows[0].get("blockers")).split(",")[0] if blocked_rows else "",
        "next_action": "Fill the target operator templates or batch intake CSV, then rerun the value gate.",
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_target_files(payload: dict[str, Any], gate_payload: dict[str, Any], action_payload: dict[str, Any]) -> None:
    gate_summary = _summary(gate_payload)
    batch_intake_csv = _text(gate_summary.get("batch_operator_fill_intake_csv"))
    intake_by_target = _intake_by_target(batch_intake_csv) if batch_intake_csv else {}
    action_by_target = _rows_by_target(_rows(action_payload))
    out_dir = _resolve(payload["summary"]["out_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    for row in payload["rows"]:
        target_id = row["target_id"]
        folder = _resolve(row["target_preflight_folder"])
        folder.mkdir(parents=True, exist_ok=True)
        intake_row = dict(intake_by_target.get(target_id, {"target_id": target_id}))
        for column in INTAKE_COLUMNS:
            intake_row.setdefault(column, "")
        _write_csv(folder / "operator_fill_template.csv", [intake_row], INTAKE_COLUMNS)
        _write_csv(folder / "field_policy.csv", _field_policy_rows(target_id, action_by_target.get(target_id, [])), FIELD_POLICY_COLUMNS)
        readme_lines = [
            f"# CASP17 Batch Native/Provenance Operator Fill Preflight: {target_id}",
            "",
            f"- status: `{row['preflight_status']}`",
            f"- target: `{target_id}` `{row['target_name']}`",
            f"- actions native/evidence/clearance/operator/date/boolean/review: `{row['native_action_count']}/{row['evidence_action_count']}/{row['clearance_action_count']}/{row['operator_action_count']}/{row['date_action_count']}/{row['boolean_action_count']}/{row['review_action_count']}`",
            f"- batch intake: `{row['batch_operator_fill_intake_csv']}`",
            f"- template: `{row['operator_fill_template_csv']}`",
            f"- field policy: `{row['field_policy_csv']}`",
            "",
            "## Verify",
            "",
            "```bash",
            "python3 tools/build_casp17_competitive_floor_batch_native_provenance_value_gate.py",
            "python3 tools/build_casp17_competitive_floor_batch_native_provenance_value_action_board.py",
            "python3 tools/casp17/build_casp17_competitive_floor_batch_native_provenance_value_action_board_completion_audit.py",
            "```",
            "",
            "## Claim Boundary",
            "",
            CLAIM_BOUNDARY,
            "",
        ]
        (folder / "README.md").write_text("\n".join(readme_lines), encoding="utf-8")
    manifest = {
        "packet_type": "casp17_competitive_floor_batch_native_provenance_operator_fill_preflight_manifest",
        "target_ids": [row["target_id"] for row in payload["rows"]],
        "open_action_count": payload["summary"]["open_action_count"],
        "claim_boundary": CLAIM_BOUNDARY,
    }
    _write_json(out_dir / "manifest.json", manifest)


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Competitive Floor Batch Native/Provenance Operator Fill Preflight",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['batch_native_provenance_operator_fill_preflight_status']}`",
        f"- targets ready/blocked/total: `{summary['target_ready_for_fill_count']}/{summary['target_blocked_count']}/{summary['target_count']}`",
        f"- actions native/evidence/clearance/operator/date/boolean/review: `{summary['native_action_count']}/{summary['evidence_action_count']}/{summary['clearance_action_count']}/{summary['operator_action_count']}/{summary['date_action_count']}/{summary['boolean_action_count']}/{summary['review_action_count']}`",
        f"- coordinate copies preflight/target: `{summary['coordinate_copy_count']}/{summary['target_coordinate_copy_count']}`",
        f"- proof/author: `{summary['competitive_proof_eligible_count']}/{summary['author_serialized_count']}`",
        f"- first ready: `{summary['first_ready_target_id'] or '-'}`",
        f"- first blocked: `{summary['first_blocked_target_id'] or '-'}` `{summary['first_blocker'] or '-'}`",
        f"- out dir: `{summary['out_dir']}`",
        "",
        "## Targets",
        "",
        "| target | status | actions | folder | blockers |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['preflight_status']}` | `{row['open_action_count']}` | "
            f"`{row['target_preflight_folder']}` | `{row['blockers'] or '-'}` |"
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    gate_payload = _read_json(args.value_gate_json)
    action_payload = _read_json(args.action_board_json)
    _write_target_files(payload, gate_payload, action_payload)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build CASP17 batch native/provenance operator-fill preflight packet."
    )
    parser.add_argument("--value-gate-json", default=DEFAULT_VALUE_GATE_JSON)
    parser.add_argument("--action-board-json", default=DEFAULT_ACTION_BOARD_JSON)
    parser.add_argument("--action-board-completion-audit-json", default=DEFAULT_ACTION_BOARD_COMPLETION_AUDIT_JSON)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
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
