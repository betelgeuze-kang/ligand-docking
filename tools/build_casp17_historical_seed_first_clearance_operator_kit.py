#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_EXECUTION_BOARD_JSON = "casp17/casp17_historical_seed_clearance_execution_board_current.json"
DEFAULT_FILL_CANDIDATES_JSON = "casp17/casp17_historical_seed_clearance_fill_candidate_packet_current.json"
DEFAULT_NO_LEAK_GAP_REPAIR_JSON = "casp17/casp17_historical_seed_no_leak_gap_repair_plan_current.json"
DEFAULT_OPERATOR_CLEARANCE_CSV = "runs/casp17_historical_identity_seed_operator_clearance_current.csv"
DEFAULT_KIT_DIR = "casp17/historical_seed_first_clearance_operator_kit"
DEFAULT_OUT_JSON = "casp17/casp17_historical_seed_first_clearance_operator_kit_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_historical_seed_first_clearance_operator_kit_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_HISTORICAL_SEED_FIRST_CLEARANCE_OPERATOR_KIT.md"

NO_LEAK_COLUMNS = [
    "field_name",
    "current_value",
    "required_value_policy",
    "weak_local_hint",
    "weak_local_hint_source",
    "evidence_ref",
    "operator_value",
    "operator_clearance",
    "notes",
]

READY_FIELD_COLUMNS = [
    "target_id",
    "benchmark_id",
    "scope",
    "lane",
    "field_name",
    "current_value",
    "proposed_value",
    "evidence_source",
    "candidate_status",
    "blockers",
    "notes",
]

KIT_ROW_COLUMNS = [
    "target_id",
    "benchmark_id",
    "scope",
    "first_clearance_kit_status",
    "no_leak_field_count",
    "ready_candidate_field_count",
    "calibration_candidate_count",
    "ablation_candidate_count",
    "weak_hint_count",
    "promotion_preview_status",
    "kit_folder",
    "no_leak_operator_intake_csv",
    "ready_field_candidates_csv",
    "promotion_preview_csv",
    "action_md",
    "next_action",
]

POLICIES = {
    "no_leak_evidence_ref": "independent_no_leak_evidence_ref_required",
    "leakage_clearance": "clear",
    "operator_clearance": "operator_cleared",
    "operator": "operator_id",
    "prediction_created_at": "iso_date",
    "native_release_date": "authoritative_release_iso_date",
    "prediction_generated_before_native_release": "true",
    "public_template_or_native_used_for_prediction": "false",
    "other_team_model_used": "false",
    "post_release_information_used": "false",
}

CLAIM_BOUNDARY = (
    "Local CASP17 first historical seed clearance operator kit only. It prepares a manual no-leak "
    "operator intake and a non-mutating promotion preview for the shortest-path seed row. It does not "
    "mutate operator CSVs, clear no-leak provenance, approve ablation evidence, prove historical "
    "eligibility, compute official CASP metrics, or submit to CASP."
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


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _read_csv(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _csv_fieldnames(path_like: str | Path) -> list[str]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or [])


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


def _safe_folder_name(target_id: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in target_id).strip("_") or "UNKNOWN"


def _first_execution_row(board_payload: dict[str, Any]) -> dict[str, Any]:
    rows = _rows(board_payload)
    for row in rows:
        if _text(row.get("execution_status")) == "operator_no_leak_only":
            return row
    return rows[0] if rows else {}


def _field_rows_for_target(fill_payload: dict[str, Any], target_id: str) -> list[dict[str, Any]]:
    by_target = fill_payload.get("field_rows_by_target")
    if isinstance(by_target, dict):
        rows = by_target.get(target_id)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def _repair_rows_for_target(no_leak_payload: dict[str, Any], target_id: str, repair_csv: str) -> list[dict[str, str]]:
    rows = _read_csv(repair_csv) if repair_csv else []
    if rows:
        return rows
    for row in _rows(no_leak_payload):
        if _text(row.get("target_id")) == target_id and _text(row.get("repair_csv")):
            return _read_csv(_text(row.get("repair_csv")))
    return []


def _operator_row(operator_rows: list[dict[str, str]], target_id: str) -> dict[str, str]:
    for row in operator_rows:
        if _text(row.get("target_id")) == target_id:
            return dict(row)
    return {}


def _build_no_leak_rows(
    field_rows: list[dict[str, Any]],
    repair_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    repair_by_field = {_text(row.get("field_name")): row for row in repair_rows}
    intake_rows: list[dict[str, Any]] = []
    for row in field_rows:
        if _text(row.get("lane")) != "no_leak_provenance":
            continue
        field_name = _text(row.get("field_name"))
        repair = repair_by_field.get(field_name, {})
        weak_hint = _text(repair.get("weak_local_candidate_value"))
        weak_source = _text(repair.get("weak_local_candidate_source"))
        intake_rows.append(
            {
                "field_name": field_name,
                "current_value": _text(row.get("current_value")),
                "required_value_policy": POLICIES.get(field_name, "operator_required"),
                "weak_local_hint": weak_hint,
                "weak_local_hint_source": weak_source,
                "evidence_ref": _text(row.get("evidence_source")),
                "operator_value": "",
                "operator_clearance": "",
                "notes": _text(repair.get("notes")) or _text(row.get("notes")),
            }
        )
    return intake_rows


def _build_ready_candidate_rows(field_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ready_rows: list[dict[str, Any]] = []
    for row in field_rows:
        if _text(row.get("candidate_status")) != "proposed":
            continue
        ready_rows.append({key: _text(row.get(key)) for key in READY_FIELD_COLUMNS})
    return ready_rows


def _promotion_preview(
    operator_row: dict[str, str],
    operator_fieldnames: list[str],
    ready_rows: list[dict[str, Any]],
    no_leak_count: int,
) -> tuple[list[dict[str, Any]], list[str], str]:
    preview = dict(operator_row)
    applied_fields: list[str] = []
    for row in ready_rows:
        field_name = _text(row.get("field_name"))
        proposed_value = _text(row.get("proposed_value"))
        if field_name and proposed_value and field_name in preview:
            preview[field_name] = proposed_value
            applied_fields.append(field_name)
    preview_status = "waiting_on_operator_no_leak_fields" if no_leak_count else "ready_for_operator_review"
    preview["promotion_preview_status"] = preview_status
    preview["prefilled_field_count"] = str(len(applied_fields))
    preview["prefilled_fields"] = ",".join(applied_fields)
    preview["operator_no_leak_fields_remaining"] = str(no_leak_count)
    fieldnames = list(operator_fieldnames)
    for extra in [
        "promotion_preview_status",
        "prefilled_field_count",
        "prefilled_fields",
        "operator_no_leak_fields_remaining",
    ]:
        if extra not in fieldnames:
            fieldnames.append(extra)
    return [preview], fieldnames, preview_status


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    board_payload = _read_json(args.execution_board_json)
    fill_payload = _read_json(args.fill_candidates_json)
    no_leak_payload = _read_json(args.no_leak_gap_repair_json)
    first = _first_execution_row(board_payload)

    target_id = _text(first.get("target_id"))
    benchmark_id = _text(first.get("benchmark_id"))
    scope = _text(first.get("scope"))
    kit_folder = _resolve(args.kit_dir) / _safe_folder_name(target_id)

    field_rows = _field_rows_for_target(fill_payload, target_id)
    repair_rows = _repair_rows_for_target(no_leak_payload, target_id, _text(first.get("no_leak_repair_csv")))
    no_leak_rows = _build_no_leak_rows(field_rows, repair_rows)
    ready_rows = _build_ready_candidate_rows(field_rows)
    operator_rows = _read_csv(args.operator_clearance_csv)
    operator_row = _operator_row(operator_rows, target_id)
    operator_fieldnames = _csv_fieldnames(args.operator_clearance_csv)
    preview_rows, preview_fieldnames, preview_status = _promotion_preview(
        operator_row,
        operator_fieldnames,
        ready_rows,
        len(no_leak_rows),
    )

    no_leak_csv = kit_folder / "no_leak_operator_intake.csv"
    ready_csv = kit_folder / "ready_field_candidates.csv"
    preview_csv = kit_folder / "promotion_preview.csv"
    action_md = kit_folder / "ACTION.md"

    weak_hint_count = sum(1 for row in no_leak_rows if _text(row.get("weak_local_hint")))
    calibration_count = sum(1 for row in ready_rows if _text(row.get("lane")) == "calibration")
    ablation_count = sum(1 for row in ready_rows if _text(row.get("lane")) == "ablation")
    status = (
        "operator_no_leak_intake_ready"
        if target_id and no_leak_rows and ready_rows and operator_row
        else "blocked_missing_first_clearance_inputs"
    )
    next_action = (
        "fill no_leak_operator_intake.csv with independent evidence, then review promotion_preview.csv"
        if status == "operator_no_leak_intake_ready"
        else "restore execution board, field candidates, no-leak repair rows, and operator clearance input"
    )

    kit_row = {
        "target_id": target_id,
        "benchmark_id": benchmark_id,
        "scope": scope,
        "first_clearance_kit_status": status,
        "no_leak_field_count": len(no_leak_rows),
        "ready_candidate_field_count": len(ready_rows),
        "calibration_candidate_count": calibration_count,
        "ablation_candidate_count": ablation_count,
        "weak_hint_count": weak_hint_count,
        "promotion_preview_status": preview_status,
        "kit_folder": _artifact(kit_folder),
        "no_leak_operator_intake_csv": _artifact(no_leak_csv),
        "ready_field_candidates_csv": _artifact(ready_csv),
        "promotion_preview_csv": _artifact(preview_csv),
        "action_md": _artifact(action_md),
        "next_action": next_action,
    }
    summary = {
        "packet_type": "casp17_historical_seed_first_clearance_operator_kit",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "first_clearance_kit_status": status,
        "target_id": target_id,
        "benchmark_id": benchmark_id,
        "scope": scope,
        "no_leak_field_count": len(no_leak_rows),
        "ready_candidate_field_count": len(ready_rows),
        "total_field_count": len(no_leak_rows) + len(ready_rows),
        "calibration_candidate_count": calibration_count,
        "ablation_candidate_count": ablation_count,
        "weak_hint_count": weak_hint_count,
        "promotion_preview_status": preview_status,
        "kit_folder": _artifact(kit_folder),
        "no_leak_operator_intake_csv": _artifact(no_leak_csv),
        "ready_field_candidates_csv": _artifact(ready_csv),
        "promotion_preview_csv": _artifact(preview_csv),
        "action_md": _artifact(action_md),
        "operator_clearance_csv": _artifact(args.operator_clearance_csv),
        "execution_board_json": _artifact(args.execution_board_json),
        "fill_candidates_json": _artifact(args.fill_candidates_json),
        "no_leak_gap_repair_json": _artifact(args.no_leak_gap_repair_json),
        "next_action": next_action,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {
        "summary": summary,
        "rows": [kit_row],
        "no_leak_operator_intake_rows": no_leak_rows,
        "ready_field_candidate_rows": ready_rows,
        "promotion_preview_rows": preview_rows,
        "promotion_preview_fieldnames": preview_fieldnames,
    }


def _write_action_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        f"# CASP17 First Historical Seed Clearance Kit: {summary['target_id']}",
        "",
        f"- status: `{summary['first_clearance_kit_status']}`",
        f"- benchmark: `{summary['benchmark_id']}`",
        f"- scope: `{summary['scope']}`",
        f"- no-leak operator fields: `{summary['no_leak_field_count']}`",
        f"- ready calibration/ablation fields: `{summary['calibration_candidate_count']}/{summary['ablation_candidate_count']}`",
        f"- weak chronology hints: `{summary['weak_hint_count']}`",
        f"- promotion preview: `{summary['promotion_preview_status']}`",
        f"- no-leak intake: `{summary['no_leak_operator_intake_csv']}`",
        f"- ready candidates: `{summary['ready_field_candidates_csv']}`",
        f"- preview: `{summary['promotion_preview_csv']}`",
        "",
        "## Operator Step",
        "",
        "Fill the no-leak intake with independent evidence and authoritative dates before promoting the preview.",
        "Weak local hints are review aids only and are not clearance authority.",
        "",
        "## Claim Boundary",
        "",
        str(summary["claim_boundary"]),
        "",
    ]
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Seed First Clearance Operator Kit",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['first_clearance_kit_status']}`",
        f"- target: `{summary['target_id']}`",
        f"- benchmark: `{summary['benchmark_id']}`",
        f"- no-leak/ready/weak: `{summary['no_leak_field_count']}/{summary['ready_candidate_field_count']}/{summary['weak_hint_count']}`",
        f"- calibration/ablation: `{summary['calibration_candidate_count']}/{summary['ablation_candidate_count']}`",
        f"- promotion preview: `{summary['promotion_preview_status']}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Files",
        "",
        f"- kit folder: `{summary['kit_folder']}`",
        f"- no-leak intake: `{summary['no_leak_operator_intake_csv']}`",
        f"- ready candidates: `{summary['ready_field_candidates_csv']}`",
        f"- promotion preview: `{summary['promotion_preview_csv']}`",
        "",
        "## Claim Boundary",
        "",
        str(summary["claim_boundary"]),
        "",
    ]
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], KIT_ROW_COLUMNS)
    _write_csv(summary["no_leak_operator_intake_csv"], payload["no_leak_operator_intake_rows"], NO_LEAK_COLUMNS)
    _write_csv(summary["ready_field_candidates_csv"], payload["ready_field_candidate_rows"], READY_FIELD_COLUMNS)
    _write_csv(
        summary["promotion_preview_csv"],
        payload["promotion_preview_rows"],
        payload["promotion_preview_fieldnames"],
    )
    _write_action_md(summary["action_md"], payload)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 first historical seed clearance operator kit.")
    parser.add_argument("--execution-board-json", default=DEFAULT_EXECUTION_BOARD_JSON)
    parser.add_argument("--fill-candidates-json", default=DEFAULT_FILL_CANDIDATES_JSON)
    parser.add_argument("--no-leak-gap-repair-json", default=DEFAULT_NO_LEAK_GAP_REPAIR_JSON)
    parser.add_argument("--operator-clearance-csv", default=DEFAULT_OPERATOR_CLEARANCE_CSV)
    parser.add_argument("--kit-dir", default=DEFAULT_KIT_DIR)
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
