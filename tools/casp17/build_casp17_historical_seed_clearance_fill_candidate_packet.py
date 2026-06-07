#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_OPERATOR_CLEARANCE_CSV = "runs/casp17_historical_identity_seed_operator_clearance_current.csv"
DEFAULT_NO_LEAK_DOSSIERS_JSON = "casp17/casp17_historical_seed_no_leak_provenance_dossiers_current.json"
DEFAULT_ABLATION_CANDIDATES_JSON = "casp17/casp17_historical_seed_ablation_candidate_manifests_current.json"
DEFAULT_CALIBRATION_FIELD_CANDIDATES_JSON = (
    "casp17/casp17_historical_seed_calibration_field_candidates_current.json"
)
DEFAULT_FIELD_DIR = "casp17/historical_seed_clearance_fill_candidates"
DEFAULT_OUT_JSON = "casp17/casp17_historical_seed_clearance_fill_candidate_packet_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_historical_seed_clearance_fill_candidate_packet_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_HISTORICAL_SEED_CLEARANCE_FILL_CANDIDATE_PACKET.md"

NO_LEAK_FIELDS = [
    "no_leak_evidence_ref",
    "leakage_clearance",
    "operator_clearance",
    "operator",
    "prediction_created_at",
    "native_release_date",
    "prediction_generated_before_native_release",
    "public_template_or_native_used_for_prediction",
    "other_team_model_used",
    "post_release_information_used",
]

ROW_COLUMNS = [
    "row_rank",
    "target_id",
    "benchmark_id",
    "scope",
    "clearance_fill_candidate_status",
    "field_candidate_csv",
    "field_count",
    "proposed_field_count",
    "already_matching_field_count",
    "operator_required_field_count",
    "blocked_field_count",
    "conflict_field_count",
    "calibration_candidate_count",
    "ablation_candidate_count",
    "no_leak_manual_field_count",
    "next_action",
    "blockers",
]

FIELD_COLUMNS = [
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

CLAIM_BOUNDARY = (
    "Local CASP17 historical seed clearance fill candidate packet only. It consolidates existing no-leak, "
    "ablation, and calibration review packets into per-row operator fill surfaces. It does not mutate operator "
    "CSVs, clear no-leak provenance, approve ablation coverage, prove historical eligibility, compute official "
    "CASP metrics, fetch structures, run predictors, or submit to CASP."
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


def _read_csv(path_like: str | Path) -> tuple[list[dict[str, str]], list[str]]:
    path = _resolve(path_like)
    if not path.exists():
        return [], [f"{_artifact(path)}_missing"]
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = list(reader.fieldnames or [])
    blockers: list[str] = []
    if not fields:
        blockers.append(f"{_artifact(path)}_header_missing")
    return rows, blockers


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


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


def _safe_name(target_id: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in target_id).strip("_") or "unknown"


def _placeholder(value: Any) -> bool:
    text = _text(value)
    return not text or text.upper().startswith("REQUIRED") or text == "YYYY-MM-DD"


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _field_rows_by_target(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    raw = payload.get("field_rows_by_target")
    if not isinstance(raw, dict):
        return {}
    return {str(key).upper(): [row for row in value if isinstance(row, dict)] for key, value in raw.items() if isinstance(value, list)}


def _no_leak_rows(
    operator_row: dict[str, str],
    no_leak_row: dict[str, Any],
    target_id: str,
    benchmark_id: str,
    scope: str,
) -> list[dict[str, Any]]:
    open_fields = {
        field
        for field in _text(no_leak_row.get("operator_required_open_fields")).split(",")
        if field
    }
    evidence_source = _text(no_leak_row.get("dossier_md"))
    rows: list[dict[str, Any]] = []
    for field_name in NO_LEAK_FIELDS:
        current_value = _text(operator_row.get(field_name))
        is_open = field_name in open_fields or _placeholder(current_value)
        rows.append(
            {
                "target_id": target_id,
                "benchmark_id": benchmark_id,
                "scope": scope,
                "lane": "no_leak_provenance",
                "field_name": field_name,
                "current_value": current_value,
                "proposed_value": "",
                "evidence_source": evidence_source,
                "candidate_status": "operator_required" if is_open else "operator_entered",
                "blockers": "operator_no_leak_evidence_required" if is_open else "",
                "notes": "manual provenance field; local dossier is review context, not clearance",
            }
        )
    return rows


def _calibration_rows(
    calibration_rows: list[dict[str, Any]],
    target_id: str,
    benchmark_id: str,
    scope: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in calibration_rows:
        status = _text(source.get("candidate_status"))
        blockers = _text(source.get("blockers"))
        rows.append(
            {
                "target_id": target_id,
                "benchmark_id": benchmark_id,
                "scope": scope,
                "lane": "calibration",
                "field_name": _text(source.get("field_name")),
                "current_value": _text(source.get("current_value")),
                "proposed_value": _text(source.get("proposed_value")),
                "evidence_source": _text(source.get("evidence_source")),
                "candidate_status": status or "blocked",
                "blockers": blockers,
                "notes": "calibration candidate from internal/native review packet; apply after no-leak clearance",
            }
        )
    return rows


def _ablation_row(
    operator_row: dict[str, str],
    ablation_row: dict[str, Any],
    target_id: str,
    benchmark_id: str,
    scope: str,
) -> dict[str, Any]:
    current_value = _text(operator_row.get("ablation_manifest_ref"))
    proposed_value = _text(ablation_row.get("candidate_manifest_csv"))
    baseline_count = _int(ablation_row.get("baseline_candidate_count"))
    selected_present = bool(ablation_row.get("selected_prediction_present"))
    native_present = bool(ablation_row.get("native_reference_present"))
    if not selected_present or not native_present:
        status = "blocked"
        blockers = "ablation_core_inputs_missing"
        proposed = ""
    elif baseline_count <= 0:
        status = "blocked"
        blockers = "ablation_layer_evidence_missing"
        proposed = ""
    elif _placeholder(current_value):
        status = "proposed"
        blockers = ""
        proposed = proposed_value
    elif current_value == proposed_value:
        status = "already_matching"
        blockers = ""
        proposed = proposed_value
    else:
        status = "conflict"
        blockers = "existing_ablation_manifest_ref_differs_from_candidate"
        proposed = proposed_value
    return {
        "target_id": target_id,
        "benchmark_id": benchmark_id,
        "scope": scope,
        "lane": "ablation",
        "field_name": "ablation_manifest_ref",
        "current_value": current_value,
        "proposed_value": proposed,
        "evidence_source": proposed_value,
        "candidate_status": status,
        "blockers": blockers,
        "notes": "ablation manifest ref candidate requires real layer evidence and operator review",
    }


def _status(field_rows: list[dict[str, Any]]) -> tuple[str, str]:
    proposed = sum(1 for row in field_rows if row["candidate_status"] == "proposed")
    matching = sum(1 for row in field_rows if row["candidate_status"] == "already_matching")
    operator_required = sum(1 for row in field_rows if row["candidate_status"] == "operator_required")
    blocked = sum(1 for row in field_rows if row["candidate_status"] == "blocked")
    conflicts = sum(1 for row in field_rows if row["candidate_status"] == "conflict")
    blockers: list[str] = []
    if operator_required:
        blockers.append("operator_no_leak_fields_required")
    if blocked:
        blockers.append("blocked_field_candidates")
    if conflicts:
        blockers.append("field_candidate_conflict")
    if conflicts:
        return "blocked_field_candidate_conflict", "resolve conflicting operator field values before applying candidates"
    if operator_required and blocked and (proposed or matching):
        return (
            "partial_candidates_operator_provenance_and_ablation_required",
            "complete no-leak provenance and repair blocked ablation fields before any cleared manifest promotion",
        )
    if operator_required and (proposed or matching):
        return (
            "partial_candidates_operator_provenance_required",
            "complete no-leak provenance, then review and apply ready field candidates",
        )
    if blocked:
        return "blocked_field_candidates", "repair blocked candidate evidence before applying operator fields"
    if proposed + matching == len(field_rows) and field_rows:
        return "clearance_fields_ready_for_operator_apply", "operator may apply all candidates after final review"
    return "operator_field_review_required", "review field candidates and provide missing operator evidence"


def _build_row(
    operator_row: dict[str, str],
    no_leak_row: dict[str, Any],
    ablation_row: dict[str, Any],
    calibration_rows: list[dict[str, Any]],
    row_rank: int,
    field_dir: str | Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    target_id = _text(operator_row.get("target_id")).upper()
    benchmark_id = _text(operator_row.get("benchmark_id"))
    scope = _text(operator_row.get("scope"))
    field_rows: list[dict[str, Any]] = []
    field_rows.extend(_no_leak_rows(operator_row, no_leak_row, target_id, benchmark_id, scope))
    field_rows.extend(_calibration_rows(calibration_rows, target_id, benchmark_id, scope))
    field_rows.append(_ablation_row(operator_row, ablation_row, target_id, benchmark_id, scope))
    status, next_action = _status(field_rows)
    field_csv = _resolve(field_dir) / f"{row_rank:02d}_{_safe_name(target_id)}" / "clearance_fill_candidates.csv"
    _write_csv(field_csv, field_rows, FIELD_COLUMNS)
    blocker_items = [
        blocker
        for row in field_rows
        for blocker in _text(row.get("blockers")).split(",")
        if blocker
    ]
    if status == "blocked_field_candidate_conflict":
        blocker_items.append("field_candidate_conflict")
    blockers = ",".join(dict.fromkeys(blocker_items))
    summary_row = {
        "row_rank": row_rank,
        "target_id": target_id,
        "benchmark_id": benchmark_id,
        "scope": scope,
        "clearance_fill_candidate_status": status,
        "field_candidate_csv": _artifact(field_csv),
        "field_count": len(field_rows),
        "proposed_field_count": sum(1 for row in field_rows if row["candidate_status"] == "proposed"),
        "already_matching_field_count": sum(1 for row in field_rows if row["candidate_status"] == "already_matching"),
        "operator_required_field_count": sum(1 for row in field_rows if row["candidate_status"] == "operator_required"),
        "blocked_field_count": sum(1 for row in field_rows if row["candidate_status"] == "blocked"),
        "conflict_field_count": sum(1 for row in field_rows if row["candidate_status"] == "conflict"),
        "calibration_candidate_count": sum(
            1 for row in field_rows if row["lane"] == "calibration" and row["candidate_status"] in {"proposed", "already_matching"}
        ),
        "ablation_candidate_count": sum(
            1 for row in field_rows if row["lane"] == "ablation" and row["candidate_status"] in {"proposed", "already_matching"}
        ),
        "no_leak_manual_field_count": sum(
            1 for row in field_rows if row["lane"] == "no_leak_provenance" and row["candidate_status"] == "operator_required"
        ),
        "next_action": next_action,
        "blockers": blockers,
    }
    return summary_row, field_rows


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    operator_rows, operator_blockers = _read_csv(args.operator_clearance_csv)
    no_leak_payload = _read_json(args.no_leak_dossiers_json)
    ablation_payload = _read_json(args.ablation_candidates_json)
    calibration_payload = _read_json(args.calibration_field_candidates_json)
    no_leak_by_target = {_text(row.get("target_id")).upper(): row for row in _rows(no_leak_payload)}
    ablation_by_target = {_text(row.get("target_id")).upper(): row for row in _rows(ablation_payload)}
    calibration_by_target = _field_rows_by_target(calibration_payload)
    rows: list[dict[str, Any]] = []
    field_rows_by_target: dict[str, list[dict[str, Any]]] = {}
    for index, operator_row in enumerate(operator_rows, start=1):
        target_id = _text(operator_row.get("target_id")).upper()
        summary_row, field_rows = _build_row(
            operator_row,
            no_leak_by_target.get(target_id, {}),
            ablation_by_target.get(target_id, {}),
            calibration_by_target.get(target_id, []),
            index,
            args.field_dir,
        )
        rows.append(summary_row)
        field_rows_by_target[target_id] = field_rows
    input_blockers = list(operator_blockers)
    for label, path_like in [
        ("no_leak_dossiers", args.no_leak_dossiers_json),
        ("ablation_candidates", args.ablation_candidates_json),
        ("calibration_field_candidates", args.calibration_field_candidates_json),
    ]:
        if not _resolve(path_like).exists():
            input_blockers.append(f"{label}_missing")
    if input_blockers:
        status = "blocked_missing_input"
    elif not rows:
        status = "blocked_missing_operator_rows"
    elif any(row["clearance_fill_candidate_status"] == "blocked_field_candidate_conflict" for row in rows):
        status = "blocked_field_candidate_conflict"
    elif any(row["clearance_fill_candidate_status"] != "clearance_fields_ready_for_operator_apply" for row in rows):
        status = "operator_provenance_required_with_field_candidates"
    else:
        status = "clearance_fields_ready_for_operator_apply"
    first_open = next(
        (row for row in rows if row["clearance_fill_candidate_status"] != "clearance_fields_ready_for_operator_apply"),
        rows[0] if rows else {},
    )
    summary = {
        "packet_type": "casp17_historical_seed_clearance_fill_candidate_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "clearance_fill_candidate_status": status,
        "operator_clearance_csv": _artifact(args.operator_clearance_csv),
        "no_leak_dossiers_json": _artifact(args.no_leak_dossiers_json),
        "ablation_candidates_json": _artifact(args.ablation_candidates_json),
        "calibration_field_candidates_json": _artifact(args.calibration_field_candidates_json),
        "field_dir": _artifact(args.field_dir),
        "seed_row_count": len(rows),
        "field_count": sum(_int(row.get("field_count")) for row in rows),
        "proposed_field_count": sum(_int(row.get("proposed_field_count")) for row in rows),
        "already_matching_field_count": sum(_int(row.get("already_matching_field_count")) for row in rows),
        "operator_required_field_count": sum(_int(row.get("operator_required_field_count")) for row in rows),
        "blocked_field_count": sum(_int(row.get("blocked_field_count")) for row in rows),
        "conflict_field_count": sum(_int(row.get("conflict_field_count")) for row in rows),
        "calibration_candidate_count": sum(_int(row.get("calibration_candidate_count")) for row in rows),
        "ablation_candidate_count": sum(_int(row.get("ablation_candidate_count")) for row in rows),
        "no_leak_manual_field_count": sum(_int(row.get("no_leak_manual_field_count")) for row in rows),
        "partial_candidate_row_count": sum(
            1 for row in rows if _text(row.get("clearance_fill_candidate_status")).startswith("partial_candidates")
        ),
        "full_clearance_ready_row_count": sum(
            1 for row in rows if row["clearance_fill_candidate_status"] == "clearance_fields_ready_for_operator_apply"
        ),
        "blocked_row_count": sum(
            1 for row in rows if row["clearance_fill_candidate_status"] != "clearance_fields_ready_for_operator_apply"
        ),
        "first_open_target_id": _text(first_open.get("target_id")),
        "first_next_action": _text(first_open.get("next_action")) or "provide seed operator rows",
        "input_blockers": ",".join(input_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows, "field_rows_by_target": field_rows_by_target}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Seed Clearance Fill Candidate Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- clearance_fill_candidate_status: `{summary['clearance_fill_candidate_status']}`",
        f"- seed rows/fields: `{summary['seed_row_count']}/{summary['field_count']}`",
        f"- proposed/matching/operator-required/blocked/conflict: `{summary['proposed_field_count']}/{summary['already_matching_field_count']}/{summary['operator_required_field_count']}/{summary['blocked_field_count']}/{summary['conflict_field_count']}`",
        f"- calibration/ablation/no-leak-manual: `{summary['calibration_candidate_count']}/{summary['ablation_candidate_count']}/{summary['no_leak_manual_field_count']}`",
        f"- partial/full-ready/blocked rows: `{summary['partial_candidate_row_count']}/{summary['full_clearance_ready_row_count']}/{summary['blocked_row_count']}`",
        f"- first open: `{summary['first_open_target_id'] or '-'}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        "",
        "## Seed Rows",
        "",
        "| rank | target | scope | status | fields | proposed | manual | blocked | calibration | ablation | csv | blockers |",
        "| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['row_rank']} | `{row['target_id']}` | `{row['scope']}` | "
            f"`{row['clearance_fill_candidate_status']}` | {row['field_count']} | "
            f"{row['proposed_field_count']} | {row['operator_required_field_count']} | "
            f"{row['blocked_field_count']} | {row['calibration_candidate_count']} | "
            f"{row['ablation_candidate_count']} | `{row['field_candidate_csv']}` | `{row['blockers'] or '-'}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | `blocked_missing_operator_rows` | 0 | 0 | 0 | 0 | 0 | 0 | - | provide operator CSV |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 historical seed clearance fill candidate packet.")
    parser.add_argument("--operator-clearance-csv", default=DEFAULT_OPERATOR_CLEARANCE_CSV)
    parser.add_argument("--no-leak-dossiers-json", default=DEFAULT_NO_LEAK_DOSSIERS_JSON)
    parser.add_argument("--ablation-candidates-json", default=DEFAULT_ABLATION_CANDIDATES_JSON)
    parser.add_argument("--calibration-field-candidates-json", default=DEFAULT_CALIBRATION_FIELD_CANDIDATES_JSON)
    parser.add_argument("--field-dir", default=DEFAULT_FIELD_DIR)
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
