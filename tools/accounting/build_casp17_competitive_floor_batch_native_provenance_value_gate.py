#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any

from tools import build_casp17_competitive_floor_batch_native_provenance_unlock_kit as batch
from tools.casp17 import build_casp17_competitive_floor_target_identity_clearance_operator_intake as intake


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_BATCH_KIT_JSON = "casp17/casp17_competitive_floor_batch_native_provenance_unlock_kit_current.json"
DEFAULT_BATCH_COMPLETION_AUDIT_JSON = (
    "casp17/casp17_competitive_floor_batch_native_provenance_unlock_kit_completion_audit_current.json"
)
DEFAULT_OUT_JSON = "casp17/casp17_competitive_floor_batch_native_provenance_value_gate_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_competitive_floor_batch_native_provenance_value_gate_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_COMPETITIVE_FLOOR_BATCH_NATIVE_PROVENANCE_VALUE_GATE.md"

REQUIRED_VALUE_COLUMNS = [column for column in batch.first.INTAKE_COLUMNS if column != "target_id"]
BLOCKING_VALUE_COLUMNS = [column for column in REQUIRED_VALUE_COLUMNS if column != "notes"]
ROW_COLUMNS = [
    "target_id",
    "target_name",
    "gate_status",
    "required_field_count",
    "ready_value_count",
    "blocked_value_count",
    "native_source_pdb",
    "native_source_status",
    "no_leak_evidence_ref",
    "no_leak_evidence_ref_status",
    "evidence_ref_sha256",
    "leakage_clearance_status",
    "operator_clearance_status",
    "operator_status",
    "prediction_created_at_status",
    "native_release_date_status",
    "prediction_generated_before_native_release_status",
    "public_template_or_native_used_for_prediction_status",
    "other_team_model_used_status",
    "post_release_information_used_status",
    "current_casp17_target_status",
    "notes_status",
    "coordinate_copy_count",
    "blocker_count",
    "blockers",
    "next_action",
    "competitive_proof_eligible",
    "author_serialized",
]
CLAIM_BOUNDARY = (
    "CASP17 competitive-floor batch native/provenance value gate only. It dry-validates operator-filled batch "
    "native PDB paths, no-leak evidence files, provenance dates, and true/false controls against the same local "
    "rules as target identity operator intake. It does not apply values, copy coordinates, fetch native structures, "
    "clear no-leak provenance, compute native accuracy, serialize a CASP author code, or submit to CASP."
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


def _read_csv_rows(path_like: str | Path) -> tuple[list[dict[str, str]], list[str]]:
    path = _resolve(path_like)
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader], list(reader.fieldnames or [])


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


def _status(ok: bool, label: str = "ready") -> str:
    return label if ok else "blocked"


def _field_status(row: dict[str, str], column: str) -> str:
    return "ready" if not intake._contains_placeholder(row.get(column)) else "blocked"


def _provenance_field_blockers(row: dict[str, str]) -> dict[str, list[str]]:
    blockers: dict[str, list[str]] = {column: [] for column in REQUIRED_VALUE_COLUMNS}
    if intake._contains_placeholder(row.get("operator")):
        blockers["operator"].append("operator_required")
    if _text(row.get("leakage_clearance")).lower() not in intake.CLEAR_VALUES:
        blockers["leakage_clearance"].append("leakage_clearance_required")
    if _text(row.get("operator_clearance")).lower() not in intake.CLEAR_VALUES:
        blockers["operator_clearance"].append("operator_clearance_required")
    prediction_date = intake._date_or_none(row.get("prediction_created_at"))
    native_date = intake._date_or_none(row.get("native_release_date"))
    if prediction_date is None:
        blockers["prediction_created_at"].append("prediction_created_at_required_iso_date")
    if native_date is None:
        blockers["native_release_date"].append("native_release_date_required_iso_date")
    if prediction_date is not None and native_date is not None and prediction_date >= native_date:
        blockers["prediction_created_at"].append("prediction_date_not_before_native_release")
        blockers["native_release_date"].append("prediction_date_not_before_native_release")
    if _text(row.get("prediction_generated_before_native_release")).lower() not in intake.TRUE_VALUES:
        blockers["prediction_generated_before_native_release"].append(
            "prediction_generated_before_native_release_required"
        )
    for column in [
        "public_template_or_native_used_for_prediction",
        "other_team_model_used",
        "post_release_information_used",
        "current_casp17_target",
    ]:
        if _text(row.get(column)).lower() not in intake.FALSE_VALUES:
            blockers[column].append(f"{column}_must_be_false")
    if intake._contains_placeholder(row.get("notes")):
        blockers["notes"].append("notes_required")
    return blockers


def _target_by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {batch.first._text(row.get("target_id")).upper(): row for row in rows if batch.first._text(row.get("target_id"))}


def _intake_by_id(rows: list[dict[str, str]]) -> tuple[dict[str, dict[str, str]], list[str]]:
    by_id: dict[str, dict[str, str]] = {}
    duplicates: list[str] = []
    for row in rows:
        target_id = _text(row.get("target_id")).upper()
        if not target_id:
            continue
        if target_id in by_id:
            duplicates.append(target_id)
        by_id[target_id] = row
    return by_id, sorted(set(duplicates))


def _native_blockers(intake_row: dict[str, str], target_row: dict[str, Any]) -> list[str]:
    native_source = _text(intake_row.get("native_source_pdb"))
    blockers = intake._pdb_blockers(native_source, role="native_source")
    if blockers:
        return blockers
    prediction_pdb = _text(target_row.get("prediction_pdb")) or _text(target_row.get("ts_prediction_pdb"))
    return intake._native_prediction_identity_blockers(native_source, prediction_pdb)


def _target_row(
    target_row: dict[str, Any],
    intake_row: dict[str, str],
    *,
    global_blockers: list[str],
) -> dict[str, Any]:
    target_id = _text(target_row.get("target_id")).upper()
    blockers = list(global_blockers)
    field_blockers = _provenance_field_blockers(intake_row)

    native_blockers = _native_blockers(intake_row, target_row)
    field_blockers["native_source_pdb"].extend(native_blockers)
    evidence_blockers, evidence_sha = intake._evidence_blockers(
        intake_row.get("no_leak_evidence_ref", ""), target_id=target_id
    )
    field_blockers["no_leak_evidence_ref"].extend(evidence_blockers)

    coordinate_count = batch.first._coordinate_file_count(target_row.get("kit_folder", ""))
    if coordinate_count:
        blockers.append("target_unlock_kit_coordinate_copy_present")
    if _text(target_row.get("competitive_proof_eligible")).lower() != "false":
        blockers.append("competitive_proof_boundary_not_false")
    if _text(target_row.get("author_serialized")).lower() != "false":
        blockers.append("author_boundary_not_false")

    ready_value_count = sum(1 for column in REQUIRED_VALUE_COLUMNS if not field_blockers[column])
    blocked_value_count = len(REQUIRED_VALUE_COLUMNS) - ready_value_count
    blocking_field_blockers = [
        blocker
        for column in BLOCKING_VALUE_COLUMNS
        for blocker in field_blockers[column]
        if blocker
    ]
    blockers.extend(blocking_field_blockers)
    blockers = list(dict.fromkeys(blockers))
    gate_status = "ready_for_operator_intake_apply" if not blockers else "blocked_awaiting_operator_values"
    return {
        "target_id": target_id,
        "target_name": _text(target_row.get("target_name")),
        "gate_status": gate_status,
        "required_field_count": len(REQUIRED_VALUE_COLUMNS),
        "ready_value_count": ready_value_count,
        "blocked_value_count": blocked_value_count,
        "native_source_pdb": _text(intake_row.get("native_source_pdb")),
        "native_source_status": _status(not field_blockers["native_source_pdb"]),
        "no_leak_evidence_ref": _text(intake_row.get("no_leak_evidence_ref")),
        "no_leak_evidence_ref_status": _status(not field_blockers["no_leak_evidence_ref"]),
        "evidence_ref_sha256": evidence_sha,
        "leakage_clearance_status": _status(not field_blockers["leakage_clearance"]),
        "operator_clearance_status": _status(not field_blockers["operator_clearance"]),
        "operator_status": _status(not field_blockers["operator"]),
        "prediction_created_at_status": _status(not field_blockers["prediction_created_at"]),
        "native_release_date_status": _status(not field_blockers["native_release_date"]),
        "prediction_generated_before_native_release_status": _status(
            not field_blockers["prediction_generated_before_native_release"]
        ),
        "public_template_or_native_used_for_prediction_status": _status(
            not field_blockers["public_template_or_native_used_for_prediction"]
        ),
        "other_team_model_used_status": _status(not field_blockers["other_team_model_used"]),
        "post_release_information_used_status": _status(not field_blockers["post_release_information_used"]),
        "current_casp17_target_status": _status(not field_blockers["current_casp17_target"]),
        "notes_status": _status(not field_blockers["notes"]),
        "coordinate_copy_count": coordinate_count,
        "blocker_count": len(blockers),
        "blockers": ",".join(blockers),
        "next_action": _next_action(gate_status),
        "competitive_proof_eligible": "false",
        "author_serialized": "false",
    }


def _next_action(gate_status: str) -> str:
    if gate_status == "ready_for_operator_intake_apply":
        return "review this value gate, then run target identity operator intake dry-run/apply."
    return "fill batch native_source_pdb, no_leak_evidence_ref, operator, dates, and true/false provenance controls."


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    batch_payload = _read_json(args.batch_kit_json)
    batch_summary = _summary(batch_payload)
    batch_rows = _rows(batch_payload)
    completion_audit_payload = _read_json(args.batch_completion_audit_json)
    completion_audit_summary = _summary(completion_audit_payload)
    batch_intake_csv = _text(args.batch_intake_csv) or _text(batch_summary.get("batch_operator_fill_intake_csv"))
    intake_rows, intake_fields = _read_csv_rows(batch_intake_csv)
    intake_by_target, duplicates = _intake_by_id(intake_rows)
    target_by_id = _target_by_id(batch_rows)

    global_blockers: list[str] = []
    missing_columns = [column for column in batch.first.INTAKE_COLUMNS if column not in intake_fields]
    if missing_columns:
        global_blockers.append("batch_intake_required_columns_missing:" + "|".join(missing_columns))
    if duplicates:
        global_blockers.append("batch_intake_duplicate_targets:" + "|".join(duplicates))
    if _text(batch_summary.get("batch_unlock_kit_status")) != (
        "casp17_competitive_floor_batch_native_provenance_unlock_kit_ready_for_operator_fill"
    ):
        global_blockers.append("batch_unlock_kit_not_ready_for_operator_fill")
    completion_status = _text(completion_audit_summary.get("batch_unlock_kit_completion_audit_status"))
    if completion_status and completion_status != (
        "casp17_competitive_floor_batch_native_provenance_unlock_kit_completion_audit_pass"
    ):
        global_blockers.append("batch_unlock_kit_completion_audit_not_pass")
    batch_coordinate_count = batch.first._coordinate_file_count(batch_summary.get("batch_folder", ""))
    if batch_coordinate_count:
        global_blockers.append("batch_unlock_kit_coordinate_copy_present")

    rows: list[dict[str, Any]] = []
    for target_row in batch_rows:
        target_id = _text(target_row.get("target_id")).upper()
        intake_row = intake_by_target.get(target_id, {"target_id": target_id})
        target_blockers = list(global_blockers)
        if target_id not in intake_by_target:
            target_blockers.append("batch_intake_target_row_missing")
        if target_id and target_id not in target_by_id:
            target_blockers.append("batch_kit_target_row_missing")
        rows.append(_target_row(target_row, intake_row, global_blockers=target_blockers))

    blocked_rows = [row for row in rows if row["gate_status"] != "ready_for_operator_intake_apply"]
    status = "casp17_competitive_floor_batch_native_provenance_value_gate_ready_for_operator_intake_apply"
    if blocked_rows or global_blockers or not rows:
        status = "casp17_competitive_floor_batch_native_provenance_value_gate_blocked_awaiting_operator_values"
    first_row = rows[0] if rows else {}
    first_blocked = blocked_rows[0] if blocked_rows else {}
    clearance_ready_count = sum(
        1
        for row in rows
        if row["leakage_clearance_status"] == "ready" and row["operator_clearance_status"] == "ready"
    )
    date_ready_count = sum(
        1
        for row in rows
        if row["prediction_created_at_status"] == "ready" and row["native_release_date_status"] == "ready"
    )
    boolean_ready_count = sum(
        1
        for row in rows
        if row["prediction_generated_before_native_release_status"] == "ready"
        and row["public_template_or_native_used_for_prediction_status"] == "ready"
        and row["other_team_model_used_status"] == "ready"
        and row["post_release_information_used_status"] == "ready"
        and row["current_casp17_target_status"] == "ready"
    )
    summary = {
        "packet_type": "casp17_competitive_floor_batch_native_provenance_value_gate",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "batch_native_provenance_value_gate_status": status,
        "batch_kit_json": _artifact(args.batch_kit_json),
        "batch_completion_audit_json": _artifact(args.batch_completion_audit_json),
        "batch_completion_audit_status": completion_status,
        "batch_operator_fill_intake_csv": _artifact(batch_intake_csv),
        "target_count": len(rows),
        "target_ready_count": len(rows) - len(blocked_rows),
        "target_blocked_count": len(blocked_rows),
        "required_field_per_target_count": len(REQUIRED_VALUE_COLUMNS),
        "required_field_total_count": len(REQUIRED_VALUE_COLUMNS) * len(rows),
        "ready_value_count": sum(_int(row.get("ready_value_count")) for row in rows),
        "blocked_value_count": sum(_int(row.get("blocked_value_count")) for row in rows),
        "native_source_ready_count": sum(1 for row in rows if row["native_source_status"] == "ready"),
        "evidence_ref_ready_count": sum(1 for row in rows if row["no_leak_evidence_ref_status"] == "ready"),
        "clearance_ready_count": clearance_ready_count,
        "date_ready_count": date_ready_count,
        "boolean_ready_count": boolean_ready_count,
        "coordinate_copy_count": batch_coordinate_count,
        "target_coordinate_copy_count": sum(_int(row.get("coordinate_copy_count")) for row in rows),
        "competitive_proof_eligible_count": 0,
        "author_serialized_count": 0,
        "first_target_id": _text(first_row.get("target_id")),
        "first_blocked_target_id": _text(first_blocked.get("target_id")),
        "first_blocker": _text(first_blocked.get("blockers")).split(",")[0] if first_blocked else "",
        "target_ids": ",".join(row["target_id"] for row in rows),
        "next_action": (
            "Run target identity operator intake dry-run/apply after operator review."
            if not blocked_rows and rows
            else "Fill blocked batch native/provenance values, then rerun this value gate."
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Competitive Floor Batch Native/Provenance Value Gate",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['batch_native_provenance_value_gate_status']}`",
        f"- targets ready/blocked/total: `{summary['target_ready_count']}/{summary['target_blocked_count']}/{summary['target_count']}`",
        f"- fields per-target/total: `{summary['required_field_per_target_count']}/{summary['required_field_total_count']}`",
        f"- values ready/blocked: `{summary['ready_value_count']}/{summary['blocked_value_count']}`",
        f"- native/evidence ready: `{summary['native_source_ready_count']}/{summary['evidence_ref_ready_count']}`",
        f"- clearance/date/boolean ready: `{summary['clearance_ready_count']}/{summary['date_ready_count']}/{summary['boolean_ready_count']}`",
        f"- coordinate copies batch/target: `{summary['coordinate_copy_count']}/{summary['target_coordinate_copy_count']}`",
        f"- proof/author: `{summary['competitive_proof_eligible_count']}/{summary['author_serialized_count']}`",
        f"- first blocked: `{summary['first_blocked_target_id'] or '-'}` `{summary['first_blocker'] or '-'}`",
        f"- batch intake: `{summary['batch_operator_fill_intake_csv']}`",
        "",
        "## Targets",
        "",
        "| target | status | values | native | evidence | clearance | date | boolean | blockers |",
        "| --- | --- | ---: | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        clearance_ready = int(row["leakage_clearance_status"] == "ready") + int(
            row["operator_clearance_status"] == "ready"
        )
        date_ready = int(row["prediction_created_at_status"] == "ready") + int(
            row["native_release_date_status"] == "ready"
        )
        boolean_ready = sum(
            int(row[column] == "ready")
            for column in [
                "prediction_generated_before_native_release_status",
                "public_template_or_native_used_for_prediction_status",
                "other_team_model_used_status",
                "post_release_information_used_status",
                "current_casp17_target_status",
            ]
        )
        lines.append(
            f"| `{row['target_id']}` | `{row['gate_status']}` | `{row['ready_value_count']}/{row['blocked_value_count']}` | "
            f"`{row['native_source_status']}` | `{row['no_leak_evidence_ref_status']}` | "
            f"`{clearance_ready}/2` | `{date_ready}/2` | `{boolean_ready}/5` | `{row['blockers'] or '-'}` |"
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dry-validate CASP17 batch native/provenance operator values.")
    parser.add_argument("--batch-kit-json", default=DEFAULT_BATCH_KIT_JSON)
    parser.add_argument("--batch-completion-audit-json", default=DEFAULT_BATCH_COMPLETION_AUDIT_JSON)
    parser.add_argument("--batch-intake-csv", default="")
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
